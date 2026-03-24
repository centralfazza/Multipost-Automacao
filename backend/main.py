"""
FastAPI application — Multipost Automation Backend.
Handles posting content to multiple social platforms simultaneously.
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .rate_limiter import limiter
from .routes import auth, channels, posts, analytics
from .routes import oauth, media, cron, batch_posts

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment validation
# ---------------------------------------------------------------------------

_REQUIRED_ENV = ["SECRET_KEY", "DATABASE_URL"]

_OAUTH_ENV = {
    "instagram": ["INSTAGRAM_APP_ID", "INSTAGRAM_APP_SECRET", "INSTAGRAM_REDIRECT_URI"],
    "tiktok": ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REDIRECT_URI"],
    "youtube": ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REDIRECT_URI"],
    "twitter": ["TWITTER_CLIENT_ID", "TWITTER_CLIENT_SECRET", "TWITTER_REDIRECT_URI"],
    "linkedin": ["LINKEDIN_CLIENT_ID", "LINKEDIN_CLIENT_SECRET", "LINKEDIN_REDIRECT_URI"],
    "facebook": ["FACEBOOK_REDIRECT_URI"],  # shares Instagram app credentials
}


def _validate_env():
    """Log warnings for missing environment variables at startup."""
    missing_required = [v for v in _REQUIRED_ENV if not os.getenv(v)]
    if missing_required:
        logger.warning(
            "MISSING REQUIRED ENV VARS: %s — the app may not work correctly",
            ", ".join(missing_required),
        )

    for platform, keys in _OAUTH_ENV.items():
        missing = [k for k in keys if not os.getenv(k)]
        if missing:
            logger.warning(
                "OAuth for %s is disabled — missing: %s",
                platform,
                ", ".join(missing),
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _validate_env()
    await init_db()
    yield


app = FastAPI(
    title="Multipost Automation API",
    description="Post content to TikTok, Instagram, YouTube, Twitter, Facebook and LinkedIn in one shot.",
    version="3.0.0",
    lifespan=lifespan,
)

_ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=_ALLOWED_ORIGINS != ["*"],  # credentials only with explicit origins
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

# Apply rate limiter
app.state.limiter = limiter

# Core routes
app.include_router(auth.router,      prefix="/auth",      tags=["Auth"])
app.include_router(channels.router,  prefix="/channels",  tags=["Channels"])
app.include_router(posts.router,     prefix="/posts",     tags=["Posts"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])

# Batch operations
app.include_router(batch_posts.router, prefix="/posts", tags=["Batch Posts"])

# OAuth flows for all remaining platforms
app.include_router(oauth.router,     prefix="/oauth",     tags=["OAuth"])

# Media upload (Vercel Blob)
app.include_router(media.router,     prefix="/media",     tags=["Media"])

# Vercel Cron — scheduled post worker
app.include_router(cron.router,      prefix="/cron",      tags=["Cron"])


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "multipost-api", "version": "3.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
