"""
Posts routes — create, list, get, and publish multipost jobs.
Publishing fires platform services concurrently with asyncio.gather(),
with exponential-backoff retry, automatic token refresh, and media validation.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db, AsyncSessionLocal
from ..models import Channel, Post, PostResult, User
from ..schemas import PostCreate, PostOut
from .auth import get_current_user
from ..services import get_platform_service
from ..services.token_refresh import ensure_fresh_token
from ..utils.retry import with_retry
from ..utils.media_validator import validate_media

router = APIRouter()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core publishing logic
# ---------------------------------------------------------------------------

async def _publish_to_channel(
    post_id: str,
    result_id: str,
    channel_id: str,
    platform: str,
    caption: str,
    media_urls: list[str],
    media_type: str,
    hashtags: Optional[str],
    extra_data: Optional[dict],
    access_token: str,
    account_id: Optional[str],
):
    """
    Publish to one platform and update PostResult.
    - Refreshes token if close to expiry
    - Validates media specs before attempting upload
    - Retries with exponential backoff on transient errors
    - Runs inside its own DB session (background-task safe)
    """
    async with AsyncSessionLocal() as db:
        # Load the PostResult and Channel (to refresh token if needed)
        res = await db.execute(select(PostResult).where(PostResult.id == result_id))
        post_result = res.scalar_one_or_none()
        if not post_result:
            return

        ch_res = await db.execute(select(Channel).where(Channel.id == channel_id))
        channel = ch_res.scalar_one_or_none()

        # Refresh token if needed
        if channel:
            try:
                access_token = await ensure_fresh_token(channel, db)
            except Exception as exc:
                logger.warning("Token refresh failed for channel %s: %s", channel_id, exc)

        # Validate media specs — log warnings but don't block publishing
        warnings = validate_media(
            platform=platform,
            media_type=media_type,
            media_urls=media_urls,
            caption=caption,
        )
        if warnings:
            logger.warning("Media validation warnings for %s: %s", platform, warnings)

        try:
            service = get_platform_service(platform)

            platform_response = await with_retry(
                service.publish,
                max_attempts=4,
                access_token=access_token,
                account_id=account_id,
                caption=caption,
                media_urls=media_urls,
                media_type=media_type,
                hashtags=hashtags,
                extra_data=extra_data or {},
            )

            post_result.status = "success"
            post_result.platform_post_id = platform_response.get("id")
            post_result.platform_url = platform_response.get("url")
            post_result.published_at = datetime.now(timezone.utc)
            post_result.error_message = None

            if warnings:
                post_result.error_message = "Published with warnings: " + "; ".join(warnings)

        except Exception as exc:
            post_result.status = "failed"
            post_result.error_message = str(exc)
            logger.error("Publish failed [%s / %s]: %s", platform, post_id, exc)

        await db.commit()

    # Update parent Post overall status
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(PostResult).where(PostResult.post_id == post_id))
        all_results = res.scalars().all()
        statuses = {r.status for r in all_results}

        post_q = await db.execute(select(Post).where(Post.id == post_id))
        post = post_q.scalar_one_or_none()
        if post:
            if "pending" in statuses or "publishing" in statuses:
                post.status = "publishing"
            elif "success" in statuses:
                post.status = "done"
                post.published_at = datetime.now(timezone.utc)
            else:
                post.status = "failed"
            await db.commit()


async def _run_publish(
    post_id: str,
    caption: str,
    media_urls: list[str],
    media_type: str,
    hashtags: Optional[str],
    extra_data: Optional[dict],
    channel_result_map: list[dict],
):
    """Fire all platform publishes concurrently. Receives plain data — no detached ORM objects."""
    tasks = [
        _publish_to_channel(
            post_id=post_id,
            result_id=item["result_id"],
            channel_id=item["channel_id"],
            platform=item["platform"],
            caption=caption,
            media_urls=media_urls,
            media_type=media_type,
            hashtags=hashtags,
            extra_data=extra_data,
            access_token=item["access_token"],
            account_id=item["account_id"],
        )
        for item in channel_result_map
    ]
    await asyncio.gather(*tasks, return_exceptions=True)


def _build_channel_result_map(channels, result_by_channel: dict) -> list[dict]:
    return [
        {
            "channel_id": ch.id,
            "platform": ch.platform,
            "access_token": ch.access_token,
            "account_id": ch.account_id,
            "result_id": result_by_channel[ch.id],
        }
        for ch in channels
        if ch.id in result_by_channel
    ]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[PostOut])
async def list_posts(
    status: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(Post)
        .options(selectinload(Post.results))
        .where(Post.user_id == current_user.id)
        .order_by(Post.created_at.desc())
    )
    if status:
        q = q.where(Post.status == status)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{post_id}", response_model=PostOut)
async def get_post(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Post)
        .options(selectinload(Post.results))
        .where(Post.id == post_id, Post.user_id == current_user.id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "Post not found")
    return post


@router.post("", response_model=PostOut, status_code=201)
async def create_post(
    body: PostCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a multipost job and optionally publish immediately.
    - `channel_ids`: which connected accounts to post to
    - `scheduled_at`: if set, publishing is deferred (Vercel Cron picks it up)
    - `media_urls`: public URLs of already-uploaded media (use /media/upload first)
    """
    result = await db.execute(
        select(Channel).where(
            Channel.id.in_(body.channel_ids),
            Channel.user_id == current_user.id,
            Channel.is_active == True,
        )
    )
    channels = result.scalars().all()
    if not channels:
        raise HTTPException(400, "No valid active channels found for the provided channel_ids")

    post = Post(
        user_id=current_user.id,
        caption=body.caption,
        media_urls=body.media_urls,
        media_type=body.media_type,
        hashtags=body.hashtags,
        extra_data=body.extra_data,
        scheduled_at=body.scheduled_at,
        status="pending",
    )
    db.add(post)
    await db.flush()

    for ch in channels:
        db.add(PostResult(
            post_id=post.id,
            channel_id=ch.id,
            platform=ch.platform,
            status="pending",
        ))
    await db.flush()

    result2 = await db.execute(
        select(Post)
        .options(selectinload(Post.results))
        .where(Post.id == post.id)
    )
    post = result2.scalar_one()

    result_by_channel = {r.channel_id: r.id for r in post.results}
    channel_result_map = _build_channel_result_map(channels, result_by_channel)

    if not body.scheduled_at:
        background_tasks.add_task(
            _run_publish,
            post.id,
            post.caption or "",
            post.media_urls or [],
            post.media_type or "image",
            post.hashtags,
            post.extra_data,
            channel_result_map,
        )

    return post


@router.post("/{post_id}/publish", response_model=PostOut)
async def publish_now(
    post_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger (or re-trigger) publishing for any post."""
    result = await db.execute(
        select(Post)
        .options(selectinload(Post.results))
        .where(Post.id == post_id, Post.user_id == current_user.id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "Post not found")

    channel_ids = [r.channel_id for r in post.results]
    ch_result = await db.execute(select(Channel).where(Channel.id.in_(channel_ids)))
    channels = ch_result.scalars().all()

    post.status = "pending"
    result_by_channel = {r.channel_id: r.id for r in post.results}
    for r in post.results:
        r.status = "pending"
        r.error_message = None

    channel_result_map = _build_channel_result_map(channels, result_by_channel)

    background_tasks.add_task(
        _run_publish,
        post.id,
        post.caption or "",
        post.media_urls or [],
        post.media_type or "image",
        post.hashtags,
        post.extra_data,
        channel_result_map,
    )
    return post


@router.delete("/{post_id}", status_code=204)
async def delete_post(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Post).where(Post.id == post_id, Post.user_id == current_user.id)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(404, "Post not found")
    await db.delete(post)
