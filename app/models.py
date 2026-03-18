from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, Text, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from .database import Base

class Company(Base):
    __tablename__ = "companies"
    id = Column(String, primary_key=True)
    name = Column(String)
    instagram_account_id = Column(String, nullable=True)
    instagram_access_token = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    automations = relationship("Automation", back_populates="company")

class Automation(Base):
    __tablename__ = "automations"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(String, ForeignKey("companies.id"))
    name = Column(String)
    platform = Column(String, default="instagram")
    triggers = Column(JSON)
    actions = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    company = relationship("Company", back_populates="automations")

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(String, ForeignKey("companies.id"))
    platform = Column(String)
    external_id = Column(String, index=True)
    contact_username = Column(String)
    last_message_at = Column(DateTime, default=datetime.utcnow)

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    sender_type = Column(String)
    content = Column(Text)
    sent_at = Column(DateTime, default=datetime.utcnow)

class Contact(Base):
    __tablename__ = "contacts"
    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(String)
    platform = Column(String)
    external_id = Column(String, index=True)
    username = Column(String)
    tags = Column(JSON, default=[])

class AnalyticsLog(Base):
    __tablename__ = "analytics_logs"
    id = Column(Integer, primary_key=True, index=True)
    automation_id = Column(Integer)
    executed_at = Column(DateTime, default=datetime.utcnow)
    success = Column(Boolean)
    trigger_data = Column(JSON)

# ─────────────────────────────────────────────
# MULTIPOST — Contas Instagram
# ─────────────────────────────────────────────
class InstagramAccount(Base):
    __tablename__ = "instagram_accounts"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String, nullable=False, index=True)
    username = Column(String, nullable=False)
    instagram_user_id = Column(String, unique=True, nullable=False)
    access_token = Column(Text, nullable=False)
    token_expires_at = Column(DateTime, nullable=True)
    account_type = Column(String, default="BUSINESS")  # BUSINESS | CREATOR
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    posts = relationship("MediaPost", secondary="post_results", viewonly=True)
    results = relationship("PostResult", back_populates="account", cascade="all, delete-orphan")

# ─────────────────────────────────────────────
# MULTIPOST — Posts Agendados
# ─────────────────────────────────────────────
class MediaPost(Base):
    __tablename__ = "media_posts"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String, nullable=False, index=True)
    caption = Column(Text, nullable=True)
    media_urls = Column(JSON, default=list)         # lista de URLs de mídia
    media_type = Column(String, default="IMAGE")    # IMAGE | VIDEO | CAROUSEL_ALBUM | REELS
    target_account_ids = Column(JSON, default=list) # lista de IDs de contas
    scheduled_at = Column(DateTime, nullable=True)  # None = publicar na hora
    status = Column(String, default="draft")        # draft|scheduled|publishing|done|error
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    results = relationship("PostResult", back_populates="post", cascade="all, delete-orphan")

# ─────────────────────────────────────────────
# MULTIPOST — Resultado por Conta
# ─────────────────────────────────────────────
class PostResult(Base):
    __tablename__ = "post_results"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    post_id = Column(String, ForeignKey("media_posts.id", ondelete="CASCADE"), nullable=False)
    account_id = Column(String, ForeignKey("instagram_accounts.id", ondelete="CASCADE"), nullable=False)
    ig_media_id = Column(String, nullable=True)      # ID retornado pelo Instagram
    status = Column(String, default="pending")        # pending | success | error
    error_message = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    post = relationship("MediaPost", back_populates="results")
    account = relationship("InstagramAccount", back_populates="results")
