"""Initial schema — users, channels, posts, post_results, oauth_states.

Revision ID: 001
Revises: —
Create Date: 2026-03-24
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "channels",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("account_id", sa.String(255), nullable=True),
        sa.Column("account_name", sa.String(255), nullable=True),
        sa.Column("access_token", sa.Text(), nullable=True),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "posts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("media_urls", sa.JSON(), nullable=True),
        sa.Column("media_type", sa.String(20), nullable=True),
        sa.Column("hashtags", sa.Text(), nullable=True),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "post_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("post_id", sa.String(36), sa.ForeignKey("posts.id"), nullable=False),
        sa.Column("channel_id", sa.String(36), sa.ForeignKey("channels.id"), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("platform_post_id", sa.String(255), nullable=True),
        sa.Column("platform_url", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "oauth_states",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("state_token", sa.String(128), nullable=False, unique=True, index=True),
        sa.Column("code_verifier", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("oauth_states")
    op.drop_table("post_results")
    op.drop_table("posts")
    op.drop_table("channels")
    op.drop_table("users")
