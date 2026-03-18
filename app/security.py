"""
security.py
Autenticação e autorização via API Key.
"""
import os
from fastapi import HTTPException, Depends, Header
from typing import Optional

API_KEY = os.getenv("API_KEY", "your-secret-api-key-change-in-production")

async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Valida API Key em headers."""
    if not x_api_key or x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API Key inválida ou ausente.")
    return x_api_key
