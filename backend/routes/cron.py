"""
Vercel Cron Job endpoint — fires every minute to publish scheduled posts.

Vercel calls GET /cron/publish-scheduled with:
  Authorization: Bearer {CRON_SECRET}

Configure in vercel.json:
  "crons": [{ "path": "/cron/publish-scheduled", "schedule": "* * * * *" }]
"""
import os
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Post, PostResult, Channel

router = APIRouter()
logger = logging.getLogger(__name__)


def _verify_cron(authorization: str = Header(default="")):
    """Reject requests that don't come from Vercel's cron system."""
    secret = os.getenv("CRON_SECRET", "")
    expected = f"Bearer {secret}" if secret else ""
    if secret and authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/publish-scheduled", dependencies=[Depends(_verify_cron)])
async def publish_scheduled(db: AsyncSession = Depends(get_db)):
    """
    Finds all pending posts whose scheduled_at <= now and triggers publishing.
    Safe to run every minute — only picks up posts that are due.
    """
    from ..routes.posts import _run_publish   # local import avoids circular deps

    now = datetime.now(timezone.utc)

    result = await db.execute(
        select(Post)
        .options(selectinload(Post.results))
        .where(
            Post.status == "pending",
            Post.scheduled_at != None,
            Post.scheduled_at <= now,
        )
    )
    due_posts = result.scalars().all()

    # Recover posts stuck in "publishing" for more than 15 minutes
    stale_cutoff = now - timedelta(minutes=15)
    stale_result = await db.execute(
        select(Post).where(
            Post.status == "publishing",
            Post.scheduled_at != None,
            Post.scheduled_at <= stale_cutoff,
        )
    )
    stale_posts = stale_result.scalars().all()
    recovered = 0
    for post in stale_posts:
        post.status = "failed"
        recovered += 1
        logger.warning("Recovered stale publishing post %s — marked as failed", post.id)
    if recovered:
        await db.commit()

    if not due_posts:
        return {"triggered": 0, "recovered": recovered}

    triggered = 0
    for post in due_posts:
        # Fetch channels for this post's results
        channel_ids = [r.channel_id for r in post.results]
        ch_res = await db.execute(
            select(Channel).where(Channel.id.in_(channel_ids), Channel.is_active == True)
        )
        channels = {ch.id: ch for ch in ch_res.scalars().all()}

        if not channels:
            continue

        result_by_channel = {r.channel_id: r.id for r in post.results}
        channel_result_map = [
            {
                "channel_id": ch.id,
                "platform": ch.platform,
                "access_token": ch.access_token,
                "account_id": ch.account_id,
                "result_id": result_by_channel[ch.id],
            }
            for ch in channels.values()
            if ch.id in result_by_channel
        ]

        # Mark as publishing to prevent double-trigger
        post.status = "publishing"
        await db.commit()

        # Fire concurrently (non-blocking — cron will finish fast)
        import asyncio
        asyncio.create_task(
            _run_publish(
                post.id,
                post.caption or "",
                post.media_urls or [],
                post.media_type or "image",
                post.hashtags,
                post.extra_data,
                channel_result_map,
            )
        )
        triggered += 1
        logger.info("Triggered scheduled post %s", post.id)

    return {"triggered": triggered, "recovered": recovered, "post_ids": [p.id for p in due_posts]}
