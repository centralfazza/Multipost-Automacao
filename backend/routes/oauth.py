"""
OAuth 2.0 flows for all remaining platforms:
YouTube, Twitter/X, LinkedIn, Facebook (Pages).

Each platform follows the same pattern:
  GET /{platform}/connect  → returns { auth_url }
  GET /{platform}/callback → exchanges code → stores Channel
"""
import os
import base64
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Channel
from .auth import get_current_user
from ..models import User

router = APIRouter()


# ---------------------------------------------------------------------------
# YouTube / Google
# ---------------------------------------------------------------------------

@router.get("/youtube/connect")
async def youtube_connect(current_user: User = Depends(get_current_user)):
    params = {
        "client_id": os.getenv("YOUTUBE_CLIENT_ID"),
        "redirect_uri": os.getenv("YOUTUBE_REDIRECT_URI"),
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube",
        "access_type": "offline",
        "prompt": "consent",   # force refresh_token every time
        "state": current_user.id,
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    return {"auth_url": url}


@router.get("/youtube/callback")
async def youtube_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
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

        # Get YouTube channel info
        yt = await client.get(
            "https://www.googleapis.com/youtube/v3/channels",
            params={"part": "snippet", "mine": True},
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        yt.raise_for_status()
        yt_data = yt.json()
        items = yt_data.get("items", [])
        channel_info = items[0] if items else {}
        yt_channel_id = channel_info.get("id", "")
        yt_channel_name = channel_info.get("snippet", {}).get("title", "")

    result = await db.execute(
        select(Channel).where(
            Channel.user_id == state,
            Channel.platform == "youtube",
            Channel.account_id == yt_channel_id,
        )
    )
    channel = result.scalar_one_or_none()
    if channel:
        channel.access_token = tokens["access_token"]
        channel.refresh_token = tokens.get("refresh_token", channel.refresh_token)
        channel.account_name = yt_channel_name
    else:
        channel = Channel(
            user_id=state,
            platform="youtube",
            account_id=yt_channel_id,
            account_name=yt_channel_name,
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
        )
        db.add(channel)

    await db.flush()
    return {"message": "YouTube connected", "channel_id": channel.id}


# ---------------------------------------------------------------------------
# Twitter / X  (OAuth 2.0 PKCE)
# ---------------------------------------------------------------------------

# In-memory PKCE verifier store (production: use Redis or DB)
_twitter_verifiers: dict[str, str] = {}


@router.get("/twitter/connect")
async def twitter_connect(current_user: User = Depends(get_current_user)):
    code_verifier = secrets.token_urlsafe(64)
    _twitter_verifiers[current_user.id] = code_verifier

    import hashlib
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).rstrip(b"=").decode()

    params = {
        "response_type": "code",
        "client_id": os.getenv("TWITTER_CLIENT_ID"),
        "redirect_uri": os.getenv("TWITTER_REDIRECT_URI"),
        "scope": "tweet.read tweet.write users.read offline.access media.write",
        "state": current_user.id,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    url = "https://twitter.com/i/oauth2/authorize?" + urlencode(params)
    return {"auth_url": url}


@router.get("/twitter/callback")
async def twitter_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
    code_verifier = _twitter_verifiers.pop(state, None)
    if not code_verifier:
        raise HTTPException(400, "Invalid or expired OAuth state")

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
                "code_verifier": code_verifier,
            },
        )
        resp.raise_for_status()
        tokens = resp.json()

        # Get user info
        me = await client.get(
            "https://api.twitter.com/2/users/me",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        me.raise_for_status()
        me_data = me.json()["data"]

    result = await db.execute(
        select(Channel).where(
            Channel.user_id == state,
            Channel.platform == "twitter",
            Channel.account_id == me_data["id"],
        )
    )
    channel = result.scalar_one_or_none()
    if channel:
        channel.access_token = tokens["access_token"]
        channel.refresh_token = tokens.get("refresh_token", channel.refresh_token)
    else:
        channel = Channel(
            user_id=state,
            platform="twitter",
            account_id=me_data["id"],
            account_name=me_data.get("name"),
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
        )
        db.add(channel)

    await db.flush()
    return {"message": "Twitter connected", "channel_id": channel.id}


# ---------------------------------------------------------------------------
# LinkedIn
# ---------------------------------------------------------------------------

@router.get("/linkedin/connect")
async def linkedin_connect(current_user: User = Depends(get_current_user)):
    params = {
        "response_type": "code",
        "client_id": os.getenv("LINKEDIN_CLIENT_ID"),
        "redirect_uri": os.getenv("LINKEDIN_REDIRECT_URI"),
        "scope": "openid profile email w_member_social",
        "state": current_user.id,
    }
    url = "https://www.linkedin.com/oauth/v2/authorization?" + urlencode(params)
    return {"auth_url": url}


@router.get("/linkedin/callback")
async def linkedin_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
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

        # Get profile info
        me = await client.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        me.raise_for_status()
        me_data = me.json()

    li_id = f"urn:li:person:{me_data['sub']}"
    li_name = me_data.get("name", "")

    result = await db.execute(
        select(Channel).where(
            Channel.user_id == state,
            Channel.platform == "linkedin",
            Channel.account_id == li_id,
        )
    )
    channel = result.scalar_one_or_none()
    if channel:
        channel.access_token = tokens["access_token"]
        channel.refresh_token = tokens.get("refresh_token", channel.refresh_token)
        channel.account_name = li_name
    else:
        channel = Channel(
            user_id=state,
            platform="linkedin",
            account_id=li_id,
            account_name=li_name,
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
        )
        db.add(channel)

    await db.flush()
    return {"message": "LinkedIn connected", "channel_id": channel.id}


# ---------------------------------------------------------------------------
# Facebook Pages
# ---------------------------------------------------------------------------

@router.get("/facebook/connect")
async def facebook_connect(current_user: User = Depends(get_current_user)):
    params = {
        "client_id": os.getenv("INSTAGRAM_APP_ID"),  # same Meta app
        "redirect_uri": os.getenv("FACEBOOK_REDIRECT_URI"),
        "scope": "pages_show_list,pages_read_engagement,pages_manage_posts,publish_video",
        "response_type": "code",
        "state": current_user.id,
    }
    url = "https://www.facebook.com/v18.0/dialog/oauth?" + urlencode(params)
    return {"auth_url": url}


@router.get("/facebook/callback")
async def facebook_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
    app_id = os.getenv("INSTAGRAM_APP_ID")
    app_secret = os.getenv("INSTAGRAM_APP_SECRET")
    redirect_uri = os.getenv("FACEBOOK_REDIRECT_URI")

    async with httpx.AsyncClient(timeout=30) as client:
        # Short-lived token
        resp = await client.post(
            "https://graph.facebook.com/v18.0/oauth/access_token",
            data={
                "client_id": app_id,
                "client_secret": app_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
        )
        resp.raise_for_status()
        short_token = resp.json()["access_token"]

        # Long-lived token
        resp2 = await client.get(
            "https://graph.facebook.com/v18.0/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": app_secret,
                "fb_exchange_token": short_token,
            },
        )
        resp2.raise_for_status()
        long_token = resp2.json()["access_token"]

        # List managed pages → create one Channel per page
        pages_resp = await client.get(
            "https://graph.facebook.com/v18.0/me/accounts",
            params={"access_token": long_token},
        )
        pages_resp.raise_for_status()
        pages = pages_resp.json().get("data", [])

    created_ids = []
    for page in pages:
        page_token = page.get("access_token", long_token)
        page_id = page["id"]

        result = await db.execute(
            select(Channel).where(
                Channel.user_id == state,
                Channel.platform == "facebook",
                Channel.account_id == page_id,
            )
        )
        channel = result.scalar_one_or_none()
        if channel:
            channel.access_token = page_token
            channel.account_name = page.get("name")
        else:
            channel = Channel(
                user_id=state,
                platform="facebook",
                account_id=page_id,
                account_name=page.get("name"),
                access_token=page_token,
            )
            db.add(channel)
            await db.flush()

        created_ids.append(channel.id)

    if not created_ids:
        # No pages found — store personal account token
        result = await db.execute(
            select(Channel).where(
                Channel.user_id == state,
                Channel.platform == "facebook",
            )
        )
        channel = result.scalar_one_or_none()
        if not channel:
            channel = Channel(
                user_id=state,
                platform="facebook",
                access_token=long_token,
            )
            db.add(channel)
            await db.flush()
        created_ids.append(channel.id)

    return {"message": "Facebook connected", "channel_ids": created_ids}
