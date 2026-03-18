"""
validators.py
Validações de segurança para URLs, entrada do usuário, etc.
"""
import re
from urllib.parse import urlparse
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

# Domínios permitidos para URLs de mídia
ALLOWED_DOMAINS = {
    "instagram.com",
    "cdninstagram.com",
    "cloudinary.com",
    "storage.googleapis.com",
    "s3.amazonaws.com",
    "imgur.com",
}

# Padrão para URL válida
URL_PATTERN = re.compile(
    r'^https?://'
    r'(?:(?:[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9\-]*[a-z0-9])?|'  # Domain...
    r'localhost|'  # ...or localhost
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or IP
    r'(?::\d+)?'  # Optional port
    r'(?:/[^\s]*)?$', re.IGNORECASE
)

def validate_media_url(url: str, strict: bool = True) -> bool:
    """
    Valida URL de mídia.

    Args:
        url: URL a validar
        strict: Se True, apenas domínios permitidos. Se False, qualquer HTTPS.

    Returns:
        True se válida, levanta HTTPException se inválida.
    """
    if not url or not isinstance(url, str):
        raise HTTPException(status_code=400, detail="URL deve ser string não-vazia")

    # Validar formato básico
    if not URL_PATTERN.match(url):
        logger.warning(f"Invalid URL format: {url}")
        raise HTTPException(status_code=400, detail="Formato de URL inválido")

    try:
        parsed = urlparse(url)

        # Rejeitar URLs locais/privadas (SSRF prevention)
        if parsed.hostname in ("localhost", "127.0.0.1", "0.0.0.0"):
            logger.warning(f"Attempted SSRF with localhost: {url}")
            raise HTTPException(status_code=400, detail="URLs localhost não permitidas")

        # Rejeitar IPs privados (10.x.x.x, 172.16.x.x, 192.168.x.x)
        if parsed.hostname:
            octets = parsed.hostname.split(".")
            if len(octets) == 4 and all(o.isdigit() for o in octets):
                first = int(octets[0])
                if first in (10, 172, 192):
                    logger.warning(f"Attempted SSRF with private IP: {url}")
                    raise HTTPException(status_code=400, detail="IPs privados não permitidos")

        # Validação estrita: apenas domínios permitidos
        if strict and parsed.hostname:
            domain_valid = any(
                parsed.hostname.endswith(allowed) or parsed.hostname == allowed
                for allowed in ALLOWED_DOMAINS
            )
            if not domain_valid:
                logger.warning(f"Domain not in whitelist: {parsed.hostname}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Domínio não permitido. Use um de: {', '.join(ALLOWED_DOMAINS)}"
                )

        return True
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"URL validation error: {str(e)}")
        raise HTTPException(status_code=400, detail="Erro ao validar URL")

def validate_media_urls(urls: list, media_type: str) -> bool:
    """Valida lista de URLs."""
    if not urls or not isinstance(urls, list):
        raise HTTPException(status_code=400, detail="media_urls deve ser lista não-vazia")

    if media_type.upper() == "CAROUSEL_ALBUM" and len(urls) < 2:
        raise HTTPException(status_code=400, detail="CAROUSEL_ALBUM precisa de pelo menos 2 URLs")

    for url in urls:
        validate_media_url(url, strict=False)  # Menos restritivo para múltiplas URLs

    return True

def sanitize_caption(caption: str, max_length: int = 2200) -> str:
    """
    Sanitiza caption (remove caracteres perigosos, limita tamanho).
    Instagram limit: 2200 caracteres.
    """
    if not caption:
        return ""

    if not isinstance(caption, str):
        raise HTTPException(status_code=400, detail="Caption deve ser string")

    # Remover caracteres de controle perigosos (não ASCII)
    caption = "".join(char for char in caption if ord(char) >= 32 or char in "\n\r\t")

    # Limitar tamanho
    if len(caption) > max_length:
        raise HTTPException(status_code=400, detail=f"Caption não pode exceder {max_length} caracteres")

    return caption.strip()
