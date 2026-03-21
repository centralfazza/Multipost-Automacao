"""
rate_limiter.py
Configuração de rate limiting com slowapi.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, HTTPException
import logging

logger = logging.getLogger(__name__)

# Instância global do limiter
limiter = Limiter(key_func=get_remote_address)

# Definições de rate limits
RATE_LIMITS = {
    "global": "1000/hour",           # 1000 requests por hora (global)
    "api_publish": "100/hour",       # 100 publicações por hora
    "api_batch": "20/hour",          # 20 batch operations por hora
    "api_account": "50/hour",        # 50 account operations por hora
    "api_analytics": "200/hour",     # 200 analytics queries por hora
}


def rate_limit_error_handler(request: Request, exc: RateLimitExceeded):
    """Handler customizado para erros de rate limit."""
    logger.warning(f"Rate limit exceeded for {request.client.host}: {exc.detail}")
    return {
        "error": "rate_limited",
        "message": "Muitas requisições. Tente novamente mais tarde.",
        "retry_after": "60",
    }
