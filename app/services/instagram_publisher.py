"""
instagram_publisher.py
Serviço de publicação de mídia no Instagram via Graph API v21.0.
Suporta: IMAGE, VIDEO, CAROUSEL_ALBUM, REELS.
Credenciais: access_token por conta (nunca hardcodado).
"""
import time
import logging
import requests
from typing import Optional, List

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.instagram.com/v21.0"
MAX_POLL_ATTEMPTS = 15   # até 75 segundos aguardando container de vídeo
POLL_INTERVAL = 5        # segundos entre cada poll


class InstagramPublisherError(Exception):
    """Erro de publicação no Instagram."""
    pass


class InstagramPublisher:
    def __init__(self, access_token: str, ig_user_id: str):
        self.token = access_token
        self.user_id = ig_user_id

    # ─────────────────────────────────────────────────
    # INTERNAL HELPERS
    # ─────────────────────────────────────────────────

    def _params(self, extra: dict = {}) -> dict:
        return {"access_token": self.token, **extra}

    def _post(self, path: str, data: dict) -> dict:
        url = f"{GRAPH_BASE}/{path}"
        resp = requests.post(url, json=data, params={"access_token": self.token}, timeout=30)
        result = resp.json()
        if "error" in result:
            raise InstagramPublisherError(result["error"].get("message", str(result["error"])))
        return result

    def _get(self, path: str, params: dict = {}) -> dict:
        url = f"{GRAPH_BASE}/{path}"
        resp = requests.get(url, params=self._params(params), timeout=30)
        return resp.json()

    # ─────────────────────────────────────────────────
    # CONTAINERS
    # ─────────────────────────────────────────────────

    def create_image_container(
        self,
        image_url: str,
        caption: Optional[str] = None,
        is_carousel_item: bool = False,
    ) -> str:
        """Cria container para imagem. Retorna container_id."""
        data: dict = {"image_url": image_url}
        if caption and not is_carousel_item:
            data["caption"] = caption
        if is_carousel_item:
            data["is_carousel_item"] = True
        result = self._post(f"{self.user_id}/media", data)
        return result["id"]

    def create_video_container(
        self,
        video_url: str,
        caption: Optional[str] = None,
        is_reel: bool = False,
        is_carousel_item: bool = False,
    ) -> str:
        """Cria container para vídeo/reel. Aguarda STATUS=FINISHED. Retorna container_id."""
        data: dict = {"video_url": video_url}
        if is_reel:
            data["media_type"] = "REELS"
        if caption and not is_carousel_item:
            data["caption"] = caption
        if is_carousel_item:
            data["is_carousel_item"] = True
        result = self._post(f"{self.user_id}/media", data)
        container_id = result["id"]
        self._wait_for_video_container(container_id)
        return container_id

    def _wait_for_video_container(self, container_id: str):
        """Polls container até status FINISHED ou lança exceção."""
        for attempt in range(MAX_POLL_ATTEMPTS):
            status_data = self._get(container_id, {"fields": "status_code,status"})
            status_code = status_data.get("status_code", "")
            if status_code == "FINISHED":
                return
            if status_code == "ERROR":
                raise InstagramPublisherError(f"Container de vídeo com erro: {status_data}")
            logger.info(f"Container {container_id} status={status_code}, aguardando...")
            time.sleep(POLL_INTERVAL)
        raise InstagramPublisherError(f"Timeout aguardando container {container_id}")

    def create_carousel_container(
        self,
        children_ids: List[str],
        caption: Optional[str] = None,
    ) -> str:
        """Cria container carousel com filhos já criados. Retorna container_id."""
        data: dict = {
            "media_type": "CAROUSEL_ALBUM",
            "children": ",".join(children_ids),
        }
        if caption:
            data["caption"] = caption
        result = self._post(f"{self.user_id}/media", data)
        return result["id"]

    def publish_container(self, container_id: str) -> str:
        """Publica um container no feed. Retorna ig_media_id."""
        result = self._post(f"{self.user_id}/media_publish", {"creation_id": container_id})
        return result["id"]

    # ─────────────────────────────────────────────────
    # PONTO DE ENTRADA PRINCIPAL
    # ─────────────────────────────────────────────────

    def publish_post(
        self,
        media_urls: List[str],
        media_type: str,
        caption: Optional[str] = None,
    ) -> str:
        """
        Orquestra criação de container e publicação.
        Retorna ig_media_id em caso de sucesso.
        Lança InstagramPublisherError em caso de falha.
        """
        media_type = media_type.upper()

        if media_type == "IMAGE":
            if not media_urls:
                raise InstagramPublisherError("media_urls vazio para post de imagem.")
            container_id = self.create_image_container(media_urls[0], caption)

        elif media_type in ("VIDEO", "REELS"):
            if not media_urls:
                raise InstagramPublisherError("media_urls vazio para post de vídeo.")
            container_id = self.create_video_container(
                media_urls[0], caption, is_reel=(media_type == "REELS")
            )

        elif media_type == "CAROUSEL_ALBUM":
            if len(media_urls) < 2:
                raise InstagramPublisherError("Carousel precisa de pelo menos 2 mídias.")
            children = []
            for url in media_urls:
                # Heurística: se termina com extensão de vídeo, é vídeo
                if url.lower().split("?")[0].endswith((".mp4", ".mov", ".avi")):
                    cid = self.create_video_container(url, is_carousel_item=True)
                else:
                    cid = self.create_image_container(url, is_carousel_item=True)
                children.append(cid)
            container_id = self.create_carousel_container(children, caption)

        else:
            raise InstagramPublisherError(f"media_type inválido: {media_type}")

        ig_media_id = self.publish_container(container_id)
        logger.info(f"Publicado com sucesso! ig_media_id={ig_media_id}")
        return ig_media_id

    # ─────────────────────────────────────────────────
    # TOKEN — Renovar token de longa duração
    # ─────────────────────────────────────────────────

    @staticmethod
    def refresh_long_lived_token(token: str, app_id: str, app_secret: str) -> dict:
        """
        Renova token de longa duração.
        Retorna dict com access_token, token_type, expires_in.
        """
        resp = requests.get(
            "https://graph.instagram.com/refresh_access_token",
            params={
                "grant_type": "ig_refresh_token",
                "access_token": token,
            },
            timeout=15,
        )
        data = resp.json()
        if "error" in data:
            raise InstagramPublisherError(data["error"].get("message", str(data)))
        return data
