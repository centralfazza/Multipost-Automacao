"""
Analytics routes — summary stats across posts and platforms.
"""
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Post, PostResult
from ..schemas import AnalyticsSummary
from .auth import get_current_user
from ..models import User

router = APIRouter()


@router.get("/summary", response_model=AnalyticsSummary)
async def summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Post)
        .options(selectinload(Post.results))
        .where(Post.user_id == current_user.id)
    )
    posts = result.scalars().all()

    total = len(posts)
    successful = sum(1 for p in posts if p.status == "done")
    failed = sum(1 for p in posts if p.status == "failed")
    pending = sum(1 for p in posts if p.status in ("pending", "publishing"))

    by_platform: dict[str, dict[str, int]] = defaultdict(lambda: {"total": 0, "success": 0, "failed": 0})
    for post in posts:
        for r in post.results:
            by_platform[r.platform]["total"] += 1
            if r.status == "success":
                by_platform[r.platform]["success"] += 1
            elif r.status == "failed":
                by_platform[r.platform]["failed"] += 1

    return AnalyticsSummary(
        total_posts=total,
        successful=successful,
        failed=failed,
        pending=pending,
        by_platform=dict(by_platform),
    )


@router.get("/posts", response_model=list[dict])
async def recent_results(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the most recent PostResults with post caption."""
    result = await db.execute(
        select(PostResult)
        .join(Post)
        .where(Post.user_id == current_user.id)
        .order_by(PostResult.created_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "post_id": r.post_id,
            "platform": r.platform,
            "status": r.status,
            "platform_url": r.platform_url,
            "error_message": r.error_message,
            "published_at": r.published_at,
        }
        for r in rows
    ]
