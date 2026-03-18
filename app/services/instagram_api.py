"""
instagram_api.py
API Instagram com tratamento de erro, timeout e logging.
"""
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.instagram.com/v21.0"
REQUEST_TIMEOUT = 15  # segundos

class InstagramAPIError(Exception):
    """Erro de API do Instagram."""
    pass

class InstagramAPI:
    def __init__(self, token: str):
        if not token:
            raise InstagramAPIError("Token não pode ser vazio")
        self.token = token

    def _request(self, method: str, path: str, **kwargs) -> dict:
        """Faz requisição com tratamento de erro e timeout."""
        url = f"{GRAPH_BASE}/{path}"
        params = kwargs.pop("params", {})
        params["access_token"] = self.token

        try:
            if method.upper() == "POST":
                resp = requests.post(url, params=params, timeout=REQUEST_TIMEOUT, **kwargs)
            else:
                resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT, **kwargs)

            resp.raise_for_status()
            data = resp.json()

            if "error" in data:
                error_msg = data["error"].get("message", str(data["error"]))
                logger.error(f"Instagram API Error: {error_msg}")
                raise InstagramAPIError(error_msg)

            return data
        except requests.Timeout:
            logger.error(f"Instagram API Timeout: {path}")
            raise InstagramAPIError("Timeout ao conectar com Instagram")
        except requests.RequestException as e:
            logger.error(f"Instagram API RequestException: {str(e)}")
            raise InstagramAPIError(f"Erro ao conectar com Instagram: {str(e)}")

    def reply_to_comment(self, comment_id: str, text: str) -> dict:
        """Responder a um comentário."""
        if not text or not text.strip():
            raise InstagramAPIError("Texto de resposta não pode ser vazio")
        return self._request("POST", f"{comment_id}/replies", json={"message": text})

    def send_dm(self, user_id: str, text: str) -> dict:
        """Enviar DM para um usuário."""
        if not user_id:
            raise InstagramAPIError("user_id não pode ser vazio")
        if not text or not text.strip():
            raise InstagramAPIError("Mensagem não pode ser vazia")
        return self._request(
            "POST",
            "me/messages",
            json={"recipient": {"id": user_id}, "message": {"text": text}}
        )
