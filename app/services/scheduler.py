"""
scheduler.py
APScheduler para processar posts agendados automaticamente.
Job recorrente: verifica media_posts com status='scheduled' a cada 60 segundos.
"""
import logging
from datetime import datetime
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

# Singleton do scheduler — iniciado na startup do FastAPI
_scheduler: Optional[BackgroundScheduler] = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    return _scheduler


def start_scheduler(db_factory):
    """
    Inicia o scheduler e registra o job de processamento.
    db_factory: callable que retorna uma sessão SQLAlchemy (ex: SessionLocal).
    """
    scheduler = get_scheduler()
    if scheduler.running:
        return

    scheduler.add_job(
        func=_process_scheduled_posts,
        trigger=IntervalTrigger(seconds=60),
        args=[db_factory],
        id="multipost_scheduled_processor",
        replace_existing=True,
        name="Processa posts agendados",
    )
    scheduler.start()
    logger.info("Scheduler iniciado — verificando posts agendados a cada 60s")


def stop_scheduler():
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler encerrado")


def _process_scheduled_posts(db_factory):
    """
    Busca posts com status='scheduled' e scheduled_at <= agora,
    e dispara a publicação em cada conta alvo.
    """
    from ..models import MediaPost, InstagramAccount, PostResult
    from .instagram_publisher import InstagramPublisher, InstagramPublisherError

    db = db_factory()
    try:
        now = datetime.utcnow()
        posts = (
            db.query(MediaPost)
            .filter(MediaPost.status == "scheduled", MediaPost.scheduled_at <= now)
            .all()
        )

        for post in posts:
            logger.info(f"Processando post agendado id={post.id}")
            _publish_post_to_accounts(db, post)

    except Exception as e:
        logger.error(f"Erro no job de posts agendados: {e}", exc_info=True)
    finally:
        db.close()


def _publish_post_to_accounts(db, post):
    """Publica um MediaPost em todas as contas alvo e registra resultados."""
    from ..models import InstagramAccount, PostResult
    from .instagram_publisher import InstagramPublisher, InstagramPublisherError

    post.status = "publishing"
    db.commit()

    target_ids = post.target_account_ids or []
    if not target_ids:
        logger.warning(f"Post {post.id} sem contas alvo, marcando como erro.")
        post.status = "error"
        db.commit()
        return

    accounts = db.query(InstagramAccount).filter(
        InstagramAccount.id.in_(target_ids),
        InstagramAccount.is_active == True,
    ).all()

    all_success = True
    for account in accounts:
        result = PostResult(post_id=post.id, account_id=account.id)
        try:
            publisher = InstagramPublisher(account.access_token, account.instagram_user_id)
            ig_media_id = publisher.publish_post(
                media_urls=post.media_urls,
                media_type=post.media_type,
                caption=post.caption,
            )
            result.ig_media_id = ig_media_id
            result.status = "success"
            result.published_at = datetime.utcnow()
            logger.info(f"✅ Post {post.id} publicado em @{account.username} → {ig_media_id}")
        except InstagramPublisherError as exc:
            result.status = "error"
            result.error_message = str(exc)
            all_success = False
            logger.error(f"❌ Erro publicando post {post.id} em @{account.username}: {exc}")
        finally:
            db.add(result)

    post.status = "done" if all_success else "error"
    db.commit()
