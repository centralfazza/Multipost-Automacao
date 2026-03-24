"""
batch_posts.py
Batch operations for creating and publishing multiple posts.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..models import Channel, Post, PostResult, User
from ..schemas import PostOut
from .auth import get_current_user
from .posts import _run_publish, _build_channel_result_map

router = APIRouter()


class BatchPostItem(BaseModel):
    caption: Optional[str] = None
    media_urls: list[str] = []
    media_type: Optional[str] = None
    hashtags: Optional[str] = None
    channel_ids: list[str]
    extra_data: Optional[dict] = None


class BatchPostCreate(BaseModel):
    posts: list[BatchPostItem]


class BatchPublish(BaseModel):
    post_ids: list[str]


@router.post("/batch/create", status_code=201)
async def create_batch_posts(
    body: BatchPostCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create multiple posts in one request."""
    if not body.posts:
        raise HTTPException(400, "posts list is empty")
    if len(body.posts) > 100:
        raise HTTPException(400, "Maximum 100 posts per batch")

    created = []
    errors = []

    for idx, item in enumerate(body.posts):
        try:
            # Validate channels
            result = await db.execute(
                select(Channel).where(
                    Channel.id.in_(item.channel_ids),
                    Channel.user_id == current_user.id,
                    Channel.is_active == True,
                )
            )
            channels = result.scalars().all()
            if not channels:
                errors.append({"index": idx, "error": "No valid channels found"})
                continue

            post = Post(
                user_id=current_user.id,
                caption=item.caption,
                media_urls=item.media_urls,
                media_type=item.media_type,
                hashtags=item.hashtags,
                extra_data=item.extra_data,
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

            created.append({"index": idx, "post_id": post.id, "status": "pending"})
        except Exception as exc:
            errors.append({"index": idx, "error": str(exc)})

    return {
        "total_requested": len(body.posts),
        "created": len(created),
        "failed": len(errors),
        "posts": created,
        "errors": errors,
    }


@router.post("/batch/publish")
async def publish_batch_posts(
    body: BatchPublish,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Publish multiple posts in background."""
    if not body.post_ids:
        raise HTTPException(400, "post_ids is empty")
    if len(body.post_ids) > 50:
        raise HTTPException(400, "Maximum 50 posts per batch")

    result = await db.execute(
        select(Post)
        .options(selectinload(Post.results))
        .where(Post.id.in_(body.post_ids), Post.user_id == current_user.id)
    )
    posts = result.scalars().all()

    if not posts:
        raise HTTPException(404, "No posts found")

    for post in posts:
        channel_ids = [r.channel_id for r in post.results]
        ch_result = await db.execute(select(Channel).where(Channel.id.in_(channel_ids)))
        channels = ch_result.scalars().all()

        result_by_channel = {r.channel_id: r.id for r in post.results}
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

    return {
        "total_posts": len(posts),
        "status": "publishing",
        "message": f"{len(posts)} posts queued for publishing",
    }
