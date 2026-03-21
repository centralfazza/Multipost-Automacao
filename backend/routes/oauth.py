"""
OAuth 2.0 flows for all platforms: YouTube, Twitter/X, LinkedIn, Facebook.
Security improvements:
  - State tokens are cryptographically random (not user IDs)
  - PKCE verifiers stored in database with TTL (not in-memory dict)
  - All callbacks validate state before processing
"""
import os
import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Channel, OAuthState
from .auth import get_current_user
from ..models import User

router = APIRouter()

STATE_TTL_MINUTES = 15  # OAuth states expire after 15 min


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_state(db: AsyncSession, user_id: str, platform: str, code_verifier: str | None = None) -> str:
    """Create a cryptographically random state token stored in the DB."""
    # Clean up expired states first
    await db.execute(
        delete(OAuthState).where(OAuthState.expires_at < datetime.now(timezone.utc))
    )
    state_token = secrets.token_urlsafe(48)
    db.add(OAuthState(
        user_id=user_id,
        platform=platform,
        state_token=state_token,
        code_verifier=code_verifier,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=STATE_TTL_MINUTES),
    ))
    await db.flush()
    return state_token


async def _consume_state(db: AsyncSession, state_token: str, platform: str) -> OAuthState:
    """Validate and consume a state token — raises 400 if invalid/expired."""
    result = await db.execute(
        select(OAuthState).where(
            OAuthState.state_token == state_token,
            OAuthState.platform == platform,
        )
    )
    state = result.scalar_one_or_none()
    if not state:
        raise HTTPException(400, "Invalid or expired OAuth state")
    if state.expires_at < datetime.now(timezone.utc):
        await db.delete(state)
        raise HTTPException(400, "OAuth state expired — please reconnect")
    await db.delete(state)  # consume once
    return state


async def _upsert_channel(db: AsyncSession, user_id: str, platform: str, account_id: str,
                          account_name: str, access_token: str, refresh_token: str | None = None) -> Channel:
    result = await db.execute(
        select(Channel).where(
            Channel.user_id == user_id,
            Channel.platform == platform,
            Channel.account_id == account_id,
        )
    )
    channel = result.scalar_one_or_none()
    if channel:
        channel.access_token = access_token
        channel.account_name = account_name
        if refresh_token:
            channel.refresh_token = refresh_token
    else:
        channel = Channel(
            user_id=user_id,
            platform=platform,
            account_id=account_id,
            account_name=account_name,
            access_token=access_token,
            refresh_token=refresh_token,
        )
        db.add(channel)
    await db.flush()
    return channel


# ---------------------------------------------------------------------------
# YouTube / Google
# ---------------------------------------------------------------------------

@router.get("/youtube/connect")
async def youtube_connect(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    state_token = await _create_state(db, current_user.id, "youtube")
    params = {
        "client_id": os.getenv("YOUTUBE_CLIENT_ID"),
        "redirect_uri": os.getenv("YOUTUBE_REDIRECT_URI"),
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube",
        "access_type": "offline",
        "prompt": "consent",
        "state": state_token,
    }
    return {"auth_url": "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)}


@router.get("/youtube/callback")
async def youtube_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
    oauth_state = await _consume_state(db, state, "youtube")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": os.getenv("YOUTUBE_CLIENT_ID"),
                "client_secret": os.getenv("YOUTUBE_CLIENT_SECRET"),
                "redirect_uri": os.getenv("YOUTUBE_REDIRECT_URI"),
                "grant_type": "authorization_code",
            },
        )
        resp.raise_for_status()
        tokens = resp.json()

        yt = await client.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "snippet", "mine": True},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        yt.raise_for_status()
        items = yt.json().get("items", [])
        channel_info = items[0] if items else {}

    channel = await _upsert_channel(
        db,
        user_id=oauth_state.user_id,
        platform="youtube",
        account_id=channel_info.get("id", ""),
        account_name=channel_info.get("snippet", {}).get("title", ""),
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
    )
    return {"message": "YouTube connected", "channel_id": channel.id}


# ---------------------------------------------------------------------------
# Twitter / X  (OAuth 2.0 PKCE)
# ---------------------------------------------------------------------------

@router.get("/twitter/connect")
async def twitter_connect(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()

    state_token = await _create_state(db, current_user.id, "twitter", code_verifier=code_verifier)

    params = {
        "response_type": "code",
        "client_id": os.getenv("TWITTER_CLIENT_ID"),
        "redirect_uri": os.getenv("TWITTER_REDIRECT_URI"),
        "scope": "tweet.read tweet.write users.read offline.access media.write",
        "state": state_token,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return {"auth_url": "https://twitter.com/i/oauth2/authorize?" + urlencode(params)}


@router.get("/twitter/callback")
async def twitter_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
    oauth_state = await _consume_state(db, state, "twitter")

    client_id = os.getenv("TWITTER_CLIENT_ID")
    client_secret = os.getenv("TWITTER_CLIENT_SECRET")
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.twitter.com/2/oauth2/token",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": os.getenv("TWITTER_REDIRECT_URI"),
                "code_verifier": oauth_state.code_verifier,
            },
        )
        resp.raise_for_status()
        tokens = resp.json()

        me = await client.get(
            "https://api.twitter.com/2/users/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        me.raise_for_status()
        me_data = me.json()["data"]

    channel = await _upsert_channel(
        db,
        user_id=oauth_state.user_id,
        platform="twitter",
        account_id=me_data["id"],
        account_name=me_data.get("name", ""),
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
    )
    return {"message": "Twitter connected", "channel_id": channel.id}


# ---------------------------------------------------------------------------
# LinkedIn
# ---------------------------------------------------------------------------

@router.get("/linkedin/connect")
async def linkedin_connect(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    state_token = await _create_state(db, current_user.id, "linkedin")
    params = {
        "response_type": "code",
        "client_id": os.getenv("LINKEDIN_CLIENT_ID"),
        "redirect_uri": os.getenv("LINKEDIN_REDIRECT_URI"),
        "scope": "openid profile email w_member_social",
        "state": state_token,
    }
    return {"auth_url": "https://www.linkedin.com/oauth/v2/authorization?" + urlencode(params)}


@router.get("/linkedin/callback")
async def linkedin_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
    oauth_state = await _consume_state(db, state, "linkedin")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": os.getenv("LINKEDIN_REDIRECT_URI"),
                "client_id": os.getenv("LINKEDIN_CLIENT_ID"),
                "client_secret": os.getenv("LINKEDIN_CLIENT_SECRET"),
            },
        )
        resp.raise_for_status()
        tokens = resp.json()

        me = await client.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        me.raise_for_status()
        me_data = me.json()

    channel = await _upsert_channel(
        db,
        user_id=oauth_state.user_id,
        platform="linkedin",
        account_id=f"urn:li:person:{me_data['sub']}",
        account_name=me_data.get("name", ""),
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
    )
    return {"message": "LinkedIn connected", "channel_id": channel.id}


# ---------------------------------------------------------------------------
# Facebook Pages
# ---------------------------------------------------------------------------

@router.get("/facebook/connect")
async def facebook_connect(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    state_token = await _create_state(db, current_user.id, "facebook")
    params = {
        "client_id": os.getenv("INSTAGRAM_APP_ID"),
        "redirect_uri": os.getenv("FACEBOOK_REDIRECT_URI"),
        "scope": "pages_show_list,pages_read_engagement,pages_manage_posts,publish_video",
        "response_type": "code",
        "state": state_token,
    }
    return {"auth_url": "https://www.facebook.com/v18.0/dialog/oauth?" + urlencode(params)}


@router.get("/facebook/callback")
async def facebook_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
    oauth_state = await _consume_state(db, state, "facebook")
    app_id = os.getenv("INSTAGRAM_APP_ID")
    app_secret = os.getenv("INSTAGRAM_APP_SECRET")
    redirect_uri = os.getenv("FACEBOOK_REDIRECT_URI")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://graph.facebook.com/v18.0/oauth/access_token",
            data={"client_id": app_id, "client_secret": app_secret,
                  "redirect_uri": redirect_uri, "code": code},
        )
        resp.raise_for_status()
        short_token = resp.json()["access_token"]

        resp2 = await client.get(
            "https://graph.facebook.com/v18.0/oauth/access_token",
            params={"grant_type": "fb_exchange_token", "client_id": app_id,
                    "client_secret": app_secret, "fb_exchange_token": short_token},
        )
        resp2.raise_for_status()
        long_token = resp2.json()["access_token"]

        pages_resp = await client.get(
            "https://graph.facebook.com/v18.0/me/accounts",
            params={"access_token": long_token},
        )
        pages_resp.raise_for_status()
        pages = pages_resp.json().get("data", [])

    created_ids = []
    for page in pages:
        channel = await _upsert_channel(
            db,
            user_id=oauth_state.user_id,
            platform="facebook",
            account_id=page["id"],
            account_name=page.get("name", ""),
            access_token=page.get("access_token", long_token),
        )
        created_ids.append(channel.id)

    return {"message": "Facebook connected", "channel_ids": created_ids}
