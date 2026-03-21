"""
SQLAlchemy ORM models for the Multipost automation backend.
"""
import os
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

# Use JSONB on PostgreSQL, plain JSON on SQLite
_DATABASE_URL = os.getenv("DATABASE_URL", "")
if "postgresql" in _DATABASE_URL or "postgres" in _DATABASE_URL:
    from sqlalchemy.dialects.postgresql import JSONB
    JsonType = JSONB
else:
    JsonType = JSON


def utcnow():
    return datetime.now(timezone.utc)


def new_uuid():
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    channels: Mapped[list["Channel"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    posts: Mapped[list["Post"]] = relationship(back_populates="user", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Channel  (one per connected social account)
# ---------------------------------------------------------------------------

SUPPORTED_PLATFORMS = ("instagram", "tiktok", "youtube", "twitter", "facebook", "linkedin")

class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)   # instagram | tiktok | ...
    account_id: Mapped[str] = mapped_column(String(255), nullable=True)  # platform-side user/page ID
    account_name: Mapped[str] = mapped_column(String(255), nullable=True)
    access_token: Mapped[str] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[str] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    extra: Mapped[dict] = mapped_column(JsonType, nullable=True)         # platform-specific metadata
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship(back_populates="channels")
    post_results: Mapped[list["PostResult"]] = relationship(back_populates="channel", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Post  (a multipost job — one per publish action)
# ---------------------------------------------------------------------------

class Post(Base):
    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)

    # Content
    caption: Mapped[str] = mapped_column(Text, nullable=True)
    media_urls: Mapped[list] = mapped_column(JsonType, nullable=True)    # list of media URLs/paths
    media_type: Mapped[str] = mapped_column(String(20), nullable=True)   # image | video | carousel
    hashtags: Mapped[str] = mapped_column(Text, nullable=True)
    extra_data: Mapped[dict] = mapped_column(JsonType, nullable=True)    # platform-specific overrides

    # Scheduling
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # State
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | publishing | done | failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="posts")
    results: Mapped[list["PostResult"]] = relationship(back_populates="post", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# PostResult  (result per platform for each Post)
# ---------------------------------------------------------------------------

class PostResult(Base):
    __tablename__ = "post_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    post_id: Mapped[str] = mapped_column(String(36), ForeignKey("posts.id"), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(36), ForeignKey("channels.id"), nullable=False)

    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")   # pending | success | failed
    platform_post_id: Mapped[str] = mapped_column(String(255), nullable=True)  # ID returned by platform
    platform_url: Mapped[str] = mapped_column(Text, nullable=True)       # public URL of the post
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    post: Mapped["Post"] = relationship(back_populates="results")
    channel: Mapped["Channel"] = relationship(back_populates="post_results")
