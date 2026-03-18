"""
accounts.py
Rotas para gerenciar contas Instagram conectadas via OAuth.
"""
import os
import requests
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta

from ..database import get_db
from ..models import InstagramAccount

router = APIRouter()

INSTAGRAM_APP_ID = os.getenv("INSTAGRAM_APP_ID", "")
INSTAGRAM_APP_SECRET = os.getenv("INSTAGRAM_APP_SECRET", "")
INSTAGRAM_REDIRECT_URI = os.getenv("INSTAGRAM_REDIRECT_URI", "")

# ─────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────

class AccountConnect(BaseModel):
    code: str           # código OAuth retornado pelo Instagram
    company_id: str

class AccountUpdate(BaseModel):
    is_active: Optional[bool] = None


# ─────────────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────────────

@router.get("/oauth-url")
def get_oauth_url():
    """Retorna a URL de autorização do Instagram para conectar uma conta."""
    if not INSTAGRAM_APP_ID or not INSTAGRAM_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="INSTAGRAM_APP_ID ou INSTAGRAM_REDIRECT_URI não configurados.")
    scope = "instagram_basic,instagram_content_publish,pages_read_engagement"
    url = (
        f"https://api.instagram.com/oauth/authorize"
        f"?client_id={INSTAGRAM_APP_ID}"
        f"&redirect_uri={INSTAGRAM_REDIRECT_URI}"
        f"&scope={scope}"
        f"&response_type=code"
    )
    return {"oauth_url": url}


@router.post("/connect")
def connect_account(body: AccountConnect, db: Session = Depends(get_db)):
    """
    Troca o code OAuth por token de curta duração,
    depois converte para token de longa duração (60 dias),
    busca dados do usuário e salva a conta.
    """
    # 1. Trocar code por short-lived token
    token_resp = requests.post(
        "https://api.instagram.com/oauth/access_token",
        data={
            "client_id": INSTAGRAM_APP_ID,
            "client_secret": INSTAGRAM_APP_SECRET,
            "grant_type": "authorization_code",
            "redirect_uri": INSTAGRAM_REDIRECT_URI,
            "code": body.code,
        },
        timeout=15,
    ).json()

    if "error_type" in token_resp:
        raise HTTPException(status_code=400, detail=token_resp.get("error_message", "Erro OAuth"))

    short_token = token_resp["access_token"]
    ig_user_id = str(token_resp["user_id"])

    # 2. Converter para long-lived token
    ll_resp = requests.get(
        "https://graph.instagram.com/access_token",
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": INSTAGRAM_APP_SECRET,
            "access_token": short_token,
        },
        timeout=15,
    ).json()

    if "error" in ll_resp:
        raise HTTPException(status_code=400, detail=ll_resp["error"].get("message", "Erro token longa duração"))

    long_token = ll_resp["access_token"]
    expires_in = ll_resp.get("expires_in", 5184000)  # default 60 dias
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    # 3. Buscar dados do usuário
    user_resp = requests.get(
        f"https://graph.instagram.com/{ig_user_id}",
        params={"fields": "id,username,account_type", "access_token": long_token},
        timeout=15,
    ).json()

    username = user_resp.get("username", "unknown")
    account_type = user_resp.get("account_type", "BUSINESS")

    # 4. Upsert no banco
    existing = db.query(InstagramAccount).filter(
        InstagramAccount.instagram_user_id == ig_user_id
    ).first()

    if existing:
        existing.access_token = long_token
        existing.token_expires_at = expires_at
        existing.username = username
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return {"status": "updated", "account": _serialize(existing)}
    else:
        account = InstagramAccount(
            company_id=body.company_id,
            username=username,
            instagram_user_id=ig_user_id,
            access_token=long_token,
            token_expires_at=expires_at,
            account_type=account_type,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        return {"status": "connected", "account": _serialize(account)}


@router.get("/")
def list_accounts(company_id: str, db: Session = Depends(get_db)):
    """Lista todas as contas da empresa."""
    accounts = db.query(InstagramAccount).filter(
        InstagramAccount.company_id == company_id
    ).all()
    return [_serialize(a) for a in accounts]


@router.get("/{account_id}")
def get_account(account_id: str, db: Session = Depends(get_db)):
    """Detalhe de uma conta específica."""
    account = db.query(InstagramAccount).filter(InstagramAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    return _serialize(account)


@router.patch("/{account_id}")
def update_account(account_id: str, body: AccountUpdate, db: Session = Depends(get_db)):
    """Ativa/desativa uma conta."""
    account = db.query(InstagramAccount).filter(InstagramAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    if body.is_active is not None:
        account.is_active = body.is_active
    db.commit()
    db.refresh(account)
    return _serialize(account)


@router.post("/{account_id}/refresh")
def refresh_token(account_id: str, db: Session = Depends(get_db)):
    """Renova o token de longa duração de uma conta."""
    from ..services.instagram_publisher import InstagramPublisher, InstagramPublisherError
    account = db.query(InstagramAccount).filter(InstagramAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    try:
        data = InstagramPublisher.refresh_long_lived_token(
            account.access_token, INSTAGRAM_APP_ID, INSTAGRAM_APP_SECRET
        )
        account.access_token = data["access_token"]
        account.token_expires_at = datetime.utcnow() + timedelta(seconds=data.get("expires_in", 5184000))
        db.commit()
        return {"status": "refreshed", "expires_at": account.token_expires_at}
    except InstagramPublisherError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{account_id}")
def delete_account(account_id: str, db: Session = Depends(get_db)):
    """Remove uma conta. Posts existentes mantêm histórico."""
    account = db.query(InstagramAccount).filter(InstagramAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Conta não encontrada")
    db.delete(account)
    db.commit()
    return {"status": "deleted"}


# ─────────────────────────────────────────────────
# HELPER — serializar sem expor o token
# ─────────────────────────────────────────────────

def _serialize(account: InstagramAccount) -> dict:
    return {
        "id": account.id,
        "company_id": account.company_id,
        "username": account.username,
        "instagram_user_id": account.instagram_user_id,
        "account_type": account.account_type,
        "is_active": account.is_active,
        "token_expires_at": account.token_expires_at.isoformat() if account.token_expires_at else None,
        "created_at": account.created_at.isoformat() if account.created_at else None,
    }
