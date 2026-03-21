"""
Pydantic schemas for request / response validation.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, EmailStr, ConfigDict


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    name: str
    is_active: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Channel
# ---------------------------------------------------------------------------

class ChannelCreate(BaseModel):
    platform: str
    account_id: Optional[str] = None
    account_name: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    extra: Optional[dict[str, Any]] = None


class ChannelUpdate(BaseModel):
    account_name: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None
    extra: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class ChannelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    platform: str
    account_id: Optional[str]
    account_name: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Post
# ---------------------------------------------------------------------------

class PostCreate(BaseModel):
    caption: Optional[str] = None
    media_urls: list[str] = []
    media_type: Optional[str] = None        # image | video | carousel
    hashtags: Optional[str] = None
    channel_ids: list[str]                  # which channels to post to
    scheduled_at: Optional[datetime] = None
    extra_data: Optional[dict[str, Any]] = None  # per-platform overrides


class PostResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    platform: str
    status: str
    platform_post_id: Optional[str]
    platform_url: Optional[str]
    error_message: Optional[str]
    published_at: Optional[datetime]
    created_at: datetime


class PostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    caption: Optional[str]
    media_urls: Optional[list]
    media_type: Optional[str]
    hashtags: Optional[str]
    status: str
    scheduled_at: Optional[datetime]
    published_at: Optional[datetime]
    created_at: datetime
    results: list[PostResultOut] = []


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------

class AnalyticsSummary(BaseModel):
    total_posts: int
    successful: int
    failed: int
    pending: int
    by_platform: dict[str, dict[str, int]]
