"""
batch_posts.py
Processamento em lote de posts.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uuid

from ..database import get_db
from ..models import MediaPost, InstagramAccount
from ..security import verify_api_key
from ..validators import validate_media_urls, sanitize_caption
from ..services.post_publisher import PostPublisher

router = APIRouter()


class BatchPostCreate(BaseModel):
    company_id: str
    posts: List[dict]  # [{"caption": "...", "media_urls": [...], ...}, ...]
    target_account_ids: List[str] = []


class BatchPostSchedule(BaseModel):
    post_ids: List[str]
    scheduled_at: datetime


def _validate_post_item(item: dict) -> tuple[dict, Optional[str]]:
    """Valida um item de post em lote. Retorna (item validado, erro)."""
    try:
        caption = item.get("caption")
        media_urls = item.get("media_urls", [])
        media_type = item.get("media_type", "IMAGE").upper()

        if not media_urls:
            return None, "media_urls vazio"

        validate_media_urls(media_urls, media_type)

        return {
            "caption": sanitize_caption(caption) if caption else None,
            "media_urls": media_urls,
            "media_type": media_type,
        }, None
    except Exception as exc:
        return None, str(exc)


@router.post("/batch", status_code=201)
def create_batch_posts(
    body: BatchPostCreate,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    """
    Cria múltiplos posts em lote.
    Retorna lista com IDs dos posts criados e erros (se houver).
    """
    if not body.posts:
        raise HTTPException(status_code=400, detail="posts vazio")

    if len(body.posts) > 100:
        raise HTTPException(status_code=400, detail="Máximo 100 posts por lote")

    # Validar accounts
    if body.target_account_ids:
        accounts = db.query(InstagramAccount).filter(
            InstagramAccount.id.in_(body.target_account_ids)
        ).all()
        if len(accounts) != len(body.target_account_ids):
            raise HTTPException(status_code=400, detail="Uma ou mais contas não encontradas")

    created_posts = []
    errors = []

    for idx, post_item in enumerate(body.posts):
        validated, error = _validate_post_item(post_item)

        if error:
            errors.append({"index": idx, "error": error})
            continue

        try:
            post = MediaPost(
                company_id=body.company_id,
                caption=validated.get("caption"),
                media_urls=validated.get("media_urls"),
                media_type=validated.get("media_type"),
                target_account_ids=body.target_account_ids,
                status="draft",
            )
            db.add(post)
            db.flush()
            created_posts.append({
                "index": idx,
                "post_id": post.id,
                "status": "draft",
            })
        except Exception as exc:
            errors.append({"index": idx, "error": str(exc)})

    db.commit()

    return {
        "total_requested": len(body.posts),
        "created": len(created_posts),
        "failed": len(errors),
        "posts": created_posts,
        "errors": errors,
    }


@router.post("/batch-schedule")
def schedule_batch_posts(
    body: BatchPostSchedule,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    """
    Agenda múltiplos posts para a mesma hora.
    """
    if not body.post_ids:
        raise HTTPException(status_code=400, detail="post_ids vazio")

    if len(body.post_ids) > 100:
        raise HTTPException(status_code=400, detail="Máximo 100 posts por lote")

    if body.scheduled_at <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="scheduled_at deve ser no futuro")

    posts = db.query(MediaPost).filter(MediaPost.id.in_(body.post_ids)).all()
    scheduled = 0
    errors = []

    for post in posts:
        try:
            if post.status not in ("draft", "scheduled", "error"):
                errors.append({"post_id": post.id, "error": f"Status {post.status} não pode ser agendado"})
                continue

            if not post.target_account_ids:
                errors.append({"post_id": post.id, "error": "Nenhuma conta alvo"})
                continue

            post.scheduled_at = body.scheduled_at
            post.status = "scheduled"
            scheduled += 1
        except Exception as exc:
            errors.append({"post_id": post.id, "error": str(exc)})

    db.commit()

    return {
        "total_requested": len(body.post_ids),
        "scheduled": scheduled,
        "failed": len(errors),
        "scheduled_at": body.scheduled_at.isoformat(),
        "errors": errors,
    }


@router.post("/batch-publish")
def publish_batch_posts(
    post_ids: List[str],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key),
):
    """
    Publica múltiplos posts em background.
    Cada post é publicado com delay para respeitar rate limits.
    """
    if not post_ids:
        raise HTTPException(status_code=400, detail="post_ids vazio")

    if len(post_ids) > 50:
        raise HTTPException(status_code=400, detail="Máximo 50 posts por lote")

    posts = db.query(MediaPost).filter(MediaPost.id.in_(post_ids)).all()

    for post in posts:
        if post.status not in ("draft", "scheduled", "error"):
            raise HTTPException(
                status_code=400,
                detail=f"Post {post.id} com status {post.status} não pode ser publicado"
            )
        if not post.target_account_ids:
            raise HTTPException(
                status_code=400,
                detail=f"Post {post.id} sem contas alvo"
            )
        post.status = "publishing"

    db.commit()

    # Adicionar delay entre posts para respeitar rate limits
    for idx, post_id in enumerate(post_ids):
        delay_seconds = idx * 5  # 5s delay entre cada post
        background_tasks.add_task(_publish_with_delay, post_id, delay_seconds)

    return {
        "total_posts": len(posts),
        "status": "publishing",
        "message": f"{len(posts)} posts agendados para publicação com delay de 5s entre cada um",
    }


def _publish_with_delay(post_id: str, delay_seconds: int):
    """Helper para publicar com delay."""
    import time
    from ..database import SessionLocal
    from .multipost import _publish_background

    if delay_seconds > 0:
        time.sleep(delay_seconds)

    _publish_background(post_id)
