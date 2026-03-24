"""
Media upload endpoint.
Accepts files directly and stores them on Vercel Blob.
Returns a public URL ready to be used in POST /posts.

Requires env var: BLOB_READ_WRITE_TOKEN (from Vercel Blob storage)
"""
import os
import mimetypes
import uuid
import logging

import httpx
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException

from .auth import get_current_user
from ..models import User
from ..utils.media_validator import PLATFORM_IMAGE_SPECS, PLATFORM_VIDEO_SPECS

router = APIRouter()
logger = logging.getLogger(__name__)

BLOB_BASE = "https://blob.vercel-storage.com"
MAX_UPLOAD_MB = 500   # global upload cap before platform-specific checks


@router.post("/upload")
async def upload_media(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a media file to Vercel Blob.
    Returns: { url, filename, size_mb, content_type }
    """
    blob_token = os.getenv("BLOB_READ_WRITE_TOKEN")
    if not blob_token:
        raise HTTPException(
            501,
            "Media upload not configured — set BLOB_READ_WRITE_TOKEN in environment variables.",
        )

    # Read file
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)

    if size_mb > MAX_UPLOAD_MB:
        raise HTTPException(413, f"File too large: {size_mb:.1f} MB (max {MAX_UPLOAD_MB} MB)")

    # Build a unique filename
    ext = ""
    if file.filename and "." in file.filename:
        ext = "." + file.filename.rsplit(".", 1)[-1].lower()
    blob_filename = f"{current_user.id}/{uuid.uuid4()}{ext}"

    content_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"

    # Upload to Vercel Blob REST API
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.put(
            f"{BLOB_BASE}/{blob_filename}",
            content=content,
            headers={
                "Authorization": f"Bearer {blob_token}",
                "Content-Type": content_type,
                "x-api-version": "7",
            },
        )
        if resp.status_code not in (200, 201):
            logger.error("Vercel Blob upload failed: %s %s", resp.status_code, resp.text)
            raise HTTPException(502, "Failed to upload file to storage")

        try:
            data = resp.json()
        except Exception:
            logger.error("Vercel Blob returned non-JSON response: %s", resp.text[:200])
            raise HTTPException(502, "Storage returned an invalid response")

        public_url = data.get("url")
        if not public_url:
            logger.error("Vercel Blob response missing 'url': %s", data)
            raise HTTPException(502, "Storage did not return a file URL")

    return {
        "url": public_url,
        "filename": blob_filename,
        "size_mb": round(size_mb, 2),
        "content_type": content_type,
    }


@router.get("/specs")
async def platform_specs():
    """Returns media specs for all supported platforms — useful for frontend validation."""
    return {
        "video": {
            platform: {
                "max_size_mb": spec.max_size_mb,
                "max_duration_seconds": spec.max_duration_s,
                "min_duration_seconds": spec.min_duration_s,
                "allowed_formats": list(spec.allowed_formats),
                "min_resolution": f"{spec.min_width}x{spec.min_height}",
            }
            for platform, spec in PLATFORM_VIDEO_SPECS.items()
        },
        "image": {
            platform: {
                "max_size_mb": spec.max_size_mb,
                "allowed_formats": list(spec.allowed_formats),
                "min_resolution": f"{spec.min_width}x{spec.min_height}",
                "max_images_carousel": spec.max_images_carousel,
            }
            for platform, spec in PLATFORM_IMAGE_SPECS.items()
        },
    }
