"""
multipost.py
Rotas CRUD de posts + ações de publicação imediata e agendamento.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from ..database import get_db
from ..models import MediaPost, InstagramAccount, PostResult
from ..security import verify_api_key
from ..validators import validate_media_urls, sanitize_caption
from ..rate_limiter import limiter, RATE_LIMITS

logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────

class PostCreate(BaseModel):
    company_id: str
    caption: Optional[str] = None
    media_urls: list[str]
    media_type: str = "IMAGE"          # IMAGE | VIDEO | CAROUSEL_ALBUM | REELS
    target_account_ids: list[str] = []


class PostUpdate(BaseModel):
    caption: Optional[str] = None
    media_urls: Optional[list[str]] = None
    media_type: Optional[str] = None
    target_account_ids: Optional[list[str]] = None


class ScheduleBody(BaseModel):
    scheduled_at: datetime    # ISO 8601, ex: 2026-03-20T15:00:00


# ─────────────────────────────────────────────────
# CRUD
# ─────────────────────────────────────────────────

@router.post("/", status_code=201)
def create_post(body: PostCreate, db: Session = Depends(get_db), api_key: str = Depends(verify_api_key)):
    """Cria um post como draft. Requer API Key."""
    _validate_media_type(body.media_type)
    validate_media_urls(body.media_urls, body.media_type)

    post = MediaPost(
        company_id=body.company_id,
        caption=sanitize_caption(body.caption) if body.caption else None,
        media_urls=body.media_urls,
        media_type=body.media_type.upper(),
        target_account_ids=body.target_account_ids,
        status="draft",
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return _serialize_post(post)


@router.get("/")
def list_posts(company_id: str, status: Optional[str] = None, db: Session = Depends(get_db), api_key: str = Depends(verify_api_key)):
    """Lista posts da empresa, filtrado opcionalmente por status. Requer API Key."""
    q = db.query(MediaPost).filter(MediaPost.company_id == company_id)
    if status:
        q = q.filter(MediaPost.status == status)
    posts = q.order_by(MediaPost.created_at.desc()).all()
    return [_serialize_post(p) for p in posts]


@router.get("/{post_id}")
def get_post(post_id: str, db: Session = Depends(get_db)):
    """Detalhe do post com resultados por conta."""
    post = _get_or_404(db, post_id)
    return {**_serialize_post(post), "results": _serialize_results(post.results)}


@router.put("/{post_id}")
def update_post(post_id: str, body: PostUpdate, db: Session = Depends(get_db)):
    """Edita post — apenas se draft ou scheduled."""
    post = _get_or_404(db, post_id)
    if post.status not in ("draft", "scheduled"):
        raise HTTPException(status_code=400, detail=f"Post com status '{post.status}' não pode ser editado.")

    if body.caption is not None:
        post.caption = body.caption
    if body.media_urls is not None:
        post.media_urls = body.media_urls
    if body.media_type is not None:
        _validate_media_type(body.media_type)
        post.media_type = body.media_type.upper()
    if body.target_account_ids is not None:
        post.target_account_ids = body.target_account_ids

    db.commit()
    db.refresh(post)
    return _serialize_post(post)


@router.delete("/{post_id}")
def delete_post(post_id: str, db: Session = Depends(get_db)):
    """Remove post se draft ou scheduled. Cancela agendamento."""
    post = _get_or_404(db, post_id)
    if post.status in ("publishing", "done"):
        raise HTTPException(status_code=400, detail="Não é possível deletar post em publicação ou já publicado.")
    db.delete(post)
    db.commit()
    return {"status": "deleted"}


# ─────────────────────────────────────────────────
# AÇÕES
# ─────────────────────────────────────────────────

@router.post("/{post_id}/publish")
@limiter.limit(RATE_LIMITS["api_publish"])
def publish_now(post_id: str, request=None, background_tasks: BackgroundTasks = None, db: Session = Depends(get_db), api_key: str = Depends(verify_api_key)):
    """
    Dispara publicação imediata em todas as contas alvo.
    A publicação ocorre em background para não bloquear o request.
    Requer API Key.
    """
    post = _get_or_404(db, post_id)
    if post.status not in ("draft", "scheduled", "error"):
        raise HTTPException(status_code=400, detail=f"Post com status '{post.status}' não pode ser publicado agora.")
    if not post.target_account_ids:
        raise HTTPException(status_code=400, detail="Nenhuma conta alvo definida no post.")

    # Marcar como publicando e devolver resposta imediata
    post.status = "publishing"
    db.commit()

    background_tasks.add_task(_publish_background, post_id)
    return {"status": "publishing", "post_id": post_id, "message": "Publicação iniciada em background."}


@router.post("/{post_id}/schedule")
def schedule_post(post_id: str, body: ScheduleBody, db: Session = Depends(get_db)):
    """Agenda o post para hora específica."""
    post = _get_or_404(db, post_id)
    if post.status not in ("draft", "scheduled", "error"):
        raise HTTPException(status_code=400, detail=f"Post com status '{post.status}' não pode ser agendado.")
    if body.scheduled_at <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="scheduled_at deve ser no futuro.")
    if not post.target_account_ids:
        raise HTTPException(status_code=400, detail="Nenhuma conta alvo definida no post.")

    post.scheduled_at = body.scheduled_at
    post.status = "scheduled"
    db.commit()
    db.refresh(post)
    return _serialize_post(post)


@router.post("/{post_id}/cancel")
def cancel_schedule(post_id: str, db: Session = Depends(get_db)):
    """Cancela agendamento e volta para draft."""
    post = _get_or_404(db, post_id)
    if post.status != "scheduled":
        raise HTTPException(status_code=400, detail="Post não está agendado.")
    post.status = "draft"
    post.scheduled_at = None
    db.commit()
    db.refresh(post)
    return _serialize_post(post)


@router.get("/{post_id}/results")
def get_results(post_id: str, db: Session = Depends(get_db)):
    """Resultados de publicação por conta."""
    post = _get_or_404(db, post_id)
    return _serialize_results(post.results)


# ─────────────────────────────────────────────────
# BACKGROUND TASK — publicação real
# ─────────────────────────────────────────────────

def _publish_background(post_id: str):
    """Executa a publicação no Instagram em background tasks do FastAPI com retry logic."""
    from ..database import SessionLocal
    from ..services.post_publisher import PostPublisher

    db = SessionLocal()
    try:
        logger.info(f"🚀 Iniciando publicação de post {post_id}")

        post = db.query(MediaPost).filter(MediaPost.id == post_id).first()
        if not post:
            logger.error(f"Post {post_id} não encontrado")
            return

        target_ids = post.target_account_ids or []
        if not target_ids:
            logger.warning(f"Post {post_id} sem contas alvo")
            post.status = "error"
            db.commit()
            return

        accounts = db.query(InstagramAccount).filter(
            InstagramAccount.id.in_(target_ids),
            InstagramAccount.is_active == True,
        ).all()

        logger.info(f"Post {post_id} será publicado em {len(accounts)} conta(s)")

        publisher = PostPublisher(db)
        all_success = publisher.publish_to_all_accounts(post_id)

        post.status = "done" if all_success else "error"
        db.commit()

        logger.info(f"✅ Post {post_id} finalizado com sucesso={all_success}")
    except Exception as exc:
        logger.error(f"❌ Erro ao publicar post {post_id}: {exc}", exc_info=True)
        post = db.query(MediaPost).filter(MediaPost.id == post_id).first()
        if post:
            post.status = "error"
            db.commit()
    finally:
        db.close()


# ─────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────

VALID_TYPES = {"IMAGE", "VIDEO", "CAROUSEL_ALBUM", "REELS"}

def _validate_media_type(mt: str):
    if mt.upper() not in VALID_TYPES:
        raise HTTPException(status_code=400, detail=f"media_type inválido. Use: {', '.join(VALID_TYPES)}")

def _validate_media_urls(urls: list, mt: str):
    if not urls:
        raise HTTPException(status_code=400, detail="media_urls não pode ser vazio.")
    if mt.upper() == "CAROUSEL_ALBUM" and len(urls) < 2:
        raise HTTPException(status_code=400, detail="CAROUSEL_ALBUM precisa de pelo menos 2 URLs.")

def _get_or_404(db: Session, post_id: str) -> MediaPost:
    post = db.query(MediaPost).filter(MediaPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post não encontrado.")
    return post

def _serialize_post(post: MediaPost) -> dict:
    return {
        "id": post.id,
        "company_id": post.company_id,
        "caption": post.caption,
        "media_urls": post.media_urls,
        "media_type": post.media_type,
        "target_account_ids": post.target_account_ids,
        "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None,
        "status": post.status,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "updated_at": post.updated_at.isoformat() if post.updated_at else None,
    }

def _serialize_results(results) -> list:
    return [
        {
            "id": r.id,
            "account_id": r.account_id,
            "ig_media_id": r.ig_media_id,
            "status": r.status,
            "error_message": r.error_message,
            "published_at": r.published_at.isoformat() if r.published_at else None,
        }
        for r in (results or [])
    ]
