"""
FastAPI application — Multipost Automation Backend.
Handles posting content to multiple social platforms simultaneously.
"""
import mimetypes
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .routes import auth, channels, posts, analytics


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Multipost Automation API",
    description="Post content to TikTok, Instagram, YouTube, Twitter, Facebook and LinkedIn in one shot.",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow any origin — tighten this in production if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router,      prefix="/auth",      tags=["Auth"])
app.include_router(channels.router,  prefix="/channels",  tags=["Channels"])
app.include_router(posts.router,     prefix="/posts",     tags=["Posts"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "service": "multipost-api"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
