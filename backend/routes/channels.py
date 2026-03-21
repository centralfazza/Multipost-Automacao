"""
Channel routes — manage connected social accounts.
Each "channel" = one authenticated account on one platform.
"""
import os
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Channel, User, SUPPORTED_PLATFORMS
from ..schemas import ChannelCreate, ChannelUpdate, ChannelOut
from .auth import get_current_user

router = APIRouter()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ChannelOut])
async def list_channels(
    platform: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Channel).where(Channel.user_id == current_user.id)
    if platform:
        q = q.where(Channel.platform == platform)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("", response_model=ChannelOut, status_code=201)
async def create_channel(
    body: ChannelCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(400, f"Platform must be one of: {SUPPORTED_PLATFORMS}")

    channel = Channel(user_id=current_user.id, **body.model_dump())
    db.add(channel)
    await db.flush()
    return channel


@router.get("/{channel_id}", response_model=ChannelOut)
async def get_channel(
    channel_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Channel).where(Channel.id == channel_id, Channel.user_id == current_user.id)
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(404, "Channel not found")
    return channel


@router.patch("/{channel_id}", response_model=ChannelOut)
async def update_channel(
    channel_id: str,
    body: ChannelUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Channel).where(Channel.id == channel_id, Channel.user_id == current_user.id)
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(404, "Channel not found")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(channel, field, value)
    return channel


@router.delete("/{channel_id}", status_code=204)
async def delete_channel(
    channel_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Channel).where(Channel.id == channel_id, Channel.user_id == current_user.id)
    )
    channel = result.scalar_one_or_none()
    if not channel:
        raise HTTPException(404, "Channel not found")
    await db.delete(channel)


# ---------------------------------------------------------------------------
# Instagram OAuth
# ---------------------------------------------------------------------------

@router.get("/instagram/connect")
async def instagram_connect(current_user: User = Depends(get_current_user)):
    """Redirect user to Meta's OAuth consent screen."""
    params = {
        "client_id": os.getenv("INSTAGRAM_APP_ID"),
        "redirect_uri": os.getenv("INSTAGRAM_REDIRECT_URI"),
        "scope": "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement",
        "response_type": "code",
        "state": current_user.id,
    }
    url = "https://www.facebook.com/v18.0/dialog/oauth?" + urlencode(params)
    return {"auth_url": url}


@router.get("/instagram/callback")
async def instagram_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Exchange code → short-lived → long-lived token, store channel."""
    app_id = os.getenv("INSTAGRAM_APP_ID")
    app_secret = os.getenv("INSTAGRAM_APP_SECRET")
    redirect_uri = os.getenv("INSTAGRAM_REDIRECT_URI")

    async with httpx.AsyncClient() as client:
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

        # Get IG business account info
        me = await client.get(
            "https://graph.facebook.com/v18.0/me",
            params={"fields": "id,name,instagram_business_account", "access_token": long_token},
        )
        me.raise_for_status()
        me_data = me.json()

    ig_id = me_data.get("instagram_business_account", {}).get("id") or me_data["id"]

    # Upsert channel
    q = select(Channel).where(
        Channel.user_id == state,
        Channel.platform == "instagram",
        Channel.account_id == ig_id,
    )
    result = await db.execute(q)
    channel = result.scalar_one_or_none()

    if channel:
        channel.access_token = long_token
        channel.account_name = me_data.get("name")
    else:
        channel = Channel(
            user_id=state,
            platform="instagram",
            account_id=ig_id,
            account_name=me_data.get("name"),
            access_token=long_token,
        )
        db.add(channel)

    await db.flush()
    return {"message": "Instagram connected", "channel_id": channel.id}


# ---------------------------------------------------------------------------
# TikTok OAuth
# ---------------------------------------------------------------------------

@router.get("/tiktok/connect")
async def tiktok_connect(current_user: User = Depends(get_current_user)):
    """Redirect user to TikTok's OAuth consent screen."""
    params = {
        "client_key": os.getenv("TIKTOK_CLIENT_KEY"),
        "redirect_uri": os.getenv("TIKTOK_REDIRECT_URI"),
        "scope": "user.info.basic,video.publish,video.upload",
        "response_type": "code",
        "state": current_user.id,
    }
    url = "https://www.tiktok.com/v2/auth/authorize?" + urlencode(params)
    return {"auth_url": url}


@router.get("/tiktok/callback")
async def tiktok_callback(code: str, state: str, db: AsyncSession = Depends(get_db)):
    """Exchange code → access token, store channel."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            data={
                "client_key": os.getenv("TIKTOK_CLIENT_KEY"),
                "client_secret": os.getenv("TIKTOK_CLIENT_SECRET"),
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": os.getenv("TIKTOK_REDIRECT_URI"),
            },
        )
        resp.raise_for_status()
        data = resp.json().get("data", resp.json())
        access_token = data["access_token"]
        open_id = data["open_id"]

    q = select(Channel).where(
        Channel.user_id == state,
        Channel.platform == "tiktok",
        Channel.account_id == open_id,
    )
    result = await db.execute(q)
    channel = result.scalar_one_or_none()

    if channel:
        channel.access_token = access_token
    else:
        channel = Channel(
            user_id=state,
            platform="tiktok",
            account_id=open_id,
            access_token=access_token,
        )
        db.add(channel)

    await db.flush()
    return {"message": "TikTok connected", "channel_id": channel.id}
