"""
Automatic token refresh for all supported platforms.
Called before publishing if the token is close to expiry (or already expired).
Updates the Channel record in the database.
"""
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

REFRESH_THRESHOLD_DAYS = 7   # refresh if token expires within 7 days


async def _needs_refresh(expires_at: Optional[datetime]) -> bool:
    if expires_at is None:
        return False
    now = datetime.now(timezone.utc)
    return expires_at <= now + timedelta(days=REFRESH_THRESHOLD_DAYS)


async def refresh_instagram_token(channel) -> Optional[str]:
    """Instagram long-lived tokens last 60 days and can be refreshed anytime."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            "https://graph.instagram.com/refresh_access_token",
            params={
                "grant_type": "ig_refresh_token",
                "access_token": channel.access_token,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("access_token")


async def refresh_tiktok_token(channel) -> Optional[dict]:
    """TikTok uses refresh_token to get a new access_token."""
    if not channel.refresh_token:
        logger.warning("TikTok channel %s has no refresh_token", channel.id)
        return None

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            data={
                "client_key": os.getenv("TIKTOK_CLIENT_KEY"),
                "client_secret": os.getenv("TIKTOK_CLIENT_SECRET"),
                "grant_type": "refresh_token",
                "refresh_token": channel.refresh_token,
            },
        )
        resp.raise_for_status()
        data = resp.json().get("data", resp.json())
        return {
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token"),
        }


async def refresh_google_token(channel) -> Optional[dict]:
    """YouTube / Google OAuth2 refresh."""
    if not channel.refresh_token:
        logger.warning("YouTube channel %s has no refresh_token", channel.id)
        return None

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": os.getenv("YOUTUBE_CLIENT_ID"),
                "client_secret": os.getenv("YOUTUBE_CLIENT_SECRET"),
                "grant_type": "refresh_token",
                "refresh_token": channel.refresh_token,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "access_token": data.get("access_token"),
            "refresh_token": channel.refresh_token,  # Google doesn't rotate refresh tokens
        }


async def refresh_twitter_token(channel) -> Optional[dict]:
    """Twitter/X OAuth2 PKCE refresh."""
    if not channel.refresh_token:
        logger.warning("Twitter channel %s has no refresh_token", channel.id)
        return None

    import base64
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
                "grant_type": "refresh_token",
                "refresh_token": channel.refresh_token,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token", channel.refresh_token),
        }


async def refresh_linkedin_token(channel) -> Optional[dict]:
    """LinkedIn OAuth2 refresh."""
    if not channel.refresh_token:
        logger.warning("LinkedIn channel %s has no refresh_token", channel.id)
        return None

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "grant_type": "refresh_token",
                "refresh_token": channel.refresh_token,
                "client_id": os.getenv("LINKEDIN_CLIENT_ID"),
                "client_secret": os.getenv("LINKEDIN_CLIENT_SECRET"),
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token", channel.refresh_token),
        }


async def refresh_facebook_token(channel) -> Optional[str]:
    """Facebook long-lived token exchange."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            "https://graph.facebook.com/v18.0/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": os.getenv("INSTAGRAM_APP_ID"),
                "client_secret": os.getenv("INSTAGRAM_APP_SECRET"),
                "fb_exchange_token": channel.access_token,
            },
        )
        resp.raise_for_status()
        return resp.json().get("access_token")


_REFRESHERS = {
    "instagram": refresh_instagram_token,
    "tiktok": refresh_tiktok_token,
    "youtube": refresh_google_token,
    "twitter": refresh_twitter_token,
    "linkedin": refresh_linkedin_token,
    "facebook": refresh_facebook_token,
}


async def ensure_fresh_token(channel, db: AsyncSession) -> str:
    """
    Returns a valid access token for `channel`.
    Refreshes and persists if the token is close to expiry.
    Always returns the best available token (even if refresh fails).
    """
    if not await _needs_refresh(channel.token_expires_at):
        return channel.access_token

    refresher = _REFRESHERS.get(channel.platform)
    if not refresher:
        return channel.access_token

    try:
        result = await refresher(channel)
        if result is None:
            return channel.access_token

        if isinstance(result, dict):
            channel.access_token = result["access_token"]
            if result.get("refresh_token"):
                channel.refresh_token = result["refresh_token"]
        else:
            channel.access_token = result

        # Reset expiry — most platforms give 60 days
        from datetime import timedelta
        channel.token_expires_at = datetime.now(timezone.utc) + timedelta(days=60)
        await db.commit()
        logger.info("Refreshed token for %s channel %s", channel.platform, channel.id)

    except Exception as exc:
        logger.error("Failed to refresh token for channel %s: %s", channel.id, exc)

    return channel.access_token
