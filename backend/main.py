"""
FastAPI application — Multipost Automation Backend.
Handles posting content to multiple social platforms simultaneously.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .routes import auth, channels, posts, analytics
from .routes import oauth, media, cron


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Multipost Automation API",
    description="Post content to TikTok, Instagram, YouTube, Twitter, Facebook and LinkedIn in one shot.",
    version="2.0.0",
    lifespan=lifespan,
)

import os as _os
_ALLOWED_ORIGINS = [o.strip() for o in _os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=_ALLOWED_ORIGINS != ["*"],  # credentials only with explicit origins
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

# Core routes
app.include_router(auth.router,      prefix="/auth",      tags=["Auth"])
app.include_router(channels.router,  prefix="/channels",  tags=["Channels"])
app.include_router(posts.router,     prefix="/posts",     tags=["Posts"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])

# OAuth flows for all remaining platforms
app.include_router(oauth.router,     prefix="/oauth",     tags=["OAuth"])

# Media upload (Vercel Blob)
app.include_router(media.router,     prefix="/media",     tags=["Media"])

# Vercel Cron — scheduled post worker
app.include_router(cron.router,      prefix="/cron",      tags=["Cron"])


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "multipost-api", "version": "2.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
