"""
post_publisher.py
Publicador com retry logic, exponential backoff e error tracking.
"""
import logging
import time
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from ..models import MediaPost, PostResult, InstagramAccount
from .instagram_publisher import InstagramPublisher, InstagramPublisherError

logger = logging.getLogger(__name__)

# Configuração de retry
MAX_RETRIES = 3
RETRY_DELAYS = [2, 5, 10]  # segundos entre cada tentativa
TRANSIENT_ERRORS = {
    "timeout",
    "connection",
    "temporarily_blocked",
    "rate_limit",
    "service_unavailable",
}


class PostPublisherError(Exception):
    """Erro na publicação de post."""
    def __init__(self, message: str, transient: bool = False):
        self.message = message
        self.transient = transient
        super().__init__(message)


class PostPublisher:
    """
    Publicador de posts com retry automático e tracking.
    """

    def __init__(self, db: Session):
        self.db = db

    def publish_post(
        self,
        post_id: str,
        account_id: str,
    ) -> PostResult:
        """
        Publica um post em uma conta com retry automático.
        Retorna PostResult com status e detalhes.
        """
        post = self.db.query(MediaPost).filter(MediaPost.id == post_id).first()
        if not post:
            raise PostPublisherError("Post não encontrado")

        account = self.db.query(InstagramAccount).filter(
            InstagramAccount.id == account_id
        ).first()
        if not account:
            raise PostPublisherError("Conta não encontrada")

        result = PostResult(post_id=post_id, account_id=account_id)

        for attempt in range(MAX_RETRIES):
            try:
                logger.info(
                    f"Tentativa {attempt + 1}/{MAX_RETRIES} publicar post "
                    f"{post_id} em conta {account.username}"
                )

                publisher = InstagramPublisher(
                    account.access_token, account.instagram_user_id
                )
                ig_media_id = publisher.publish_post(
                    media_urls=post.media_urls,
                    media_type=post.media_type,
                    caption=post.caption,
                )

                result.ig_media_id = ig_media_id
                result.status = "success"
                result.published_at = datetime.utcnow()
                logger.info(
                    f"✅ Post {post_id} publicado em @{account.username} "
                    f"→ {ig_media_id}"
                )
                return result

            except InstagramPublisherError as exc:
                is_transient = self._is_transient_error(str(exc))
                result.error_message = str(exc)

                if attempt < MAX_RETRIES - 1 and is_transient:
                    delay = RETRY_DELAYS[attempt]
                    logger.warning(
                        f"⚠️ Erro transiente na tentativa {attempt + 1}: {exc}. "
                        f"Aguardando {delay}s antes de retry..."
                    )
                    time.sleep(delay)
                else:
                    result.status = "error"
                    logger.error(
                        f"❌ Falha final publicando post {post_id} em "
                        f"@{account.username}: {exc}"
                    )
                    return result

        return result

    def publish_to_all_accounts(self, post_id: str) -> bool:
        """
        Publica um post em todas as contas alvo.
        Retorna True se todas tiveram sucesso, False se houver qualquer falha.
        """
        post = self.db.query(MediaPost).filter(MediaPost.id == post_id).first()
        if not post:
            raise PostPublisherError("Post não encontrado")

        target_ids = post.target_account_ids or []
        if not target_ids:
            logger.warning(f"Post {post_id} sem contas alvo")
            return False

        accounts = self.db.query(InstagramAccount).filter(
            InstagramAccount.id.in_(target_ids),
            InstagramAccount.is_active == True,
        ).all()

        all_success = True
        for account in accounts:
            try:
                result = self.publish_post(post_id, account.id)
                self.db.add(result)
                if result.status != "success":
                    all_success = False
            except Exception as exc:
                logger.error(f"Erro publicando em {account.username}: {exc}")
                all_success = False

        self.db.commit()
        return all_success

    @staticmethod
    def _is_transient_error(error_msg: str) -> bool:
        """Detecta se erro é transiente (pode ser refeito) ou permanente."""
        error_lower = error_msg.lower()
        return any(keyword in error_lower for keyword in TRANSIENT_ERRORS)
