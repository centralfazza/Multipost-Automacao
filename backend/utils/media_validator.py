"""
Platform-specific media validation.
Checks format, file size, duration and dimensions before attempting to publish.
Raises ValueError with a clear message if content doesn't meet platform specs.
"""
import ipaddress
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Platform specs (official, as of 2025)
# ---------------------------------------------------------------------------

@dataclass
class VideoSpec:
    max_size_mb: int
    max_duration_s: int
    min_duration_s: int
    allowed_formats: tuple
    min_width: int
    min_height: int

@dataclass
class ImageSpec:
    max_size_mb: int
    allowed_formats: tuple
    min_width: int
    min_height: int
    max_images_carousel: int


PLATFORM_VIDEO_SPECS: dict[str, VideoSpec] = {
    "instagram": VideoSpec(
        max_size_mb=1000,
        max_duration_s=90 * 60,   # Reels: 90 min
        min_duration_s=3,
        allowed_formats=("mp4", "mov"),
        min_width=500,
        min_height=888,
    ),
    "tiktok": VideoSpec(
        max_size_mb=4096,
        max_duration_s=60 * 60,   # 60 min
        min_duration_s=3,
        allowed_formats=("mp4", "webm", "mov"),
        min_width=360,
        min_height=360,
    ),
    "youtube": VideoSpec(
        max_size_mb=256 * 1024,   # 256 GB
        max_duration_s=12 * 60 * 60,
        min_duration_s=1,
        allowed_formats=("mp4", "mov", "avi", "wmv", "flv", "webm", "mkv"),
        min_width=426,
        min_height=240,
    ),
    "twitter": VideoSpec(
        max_size_mb=512,
        max_duration_s=140,
        min_duration_s=1,
        allowed_formats=("mp4", "mov"),
        min_width=32,
        min_height=32,
    ),
    "facebook": VideoSpec(
        max_size_mb=10240,
        max_duration_s=240 * 60,  # 4 hours
        min_duration_s=1,
        allowed_formats=("mp4", "mov", "avi"),
        min_width=120,
        min_height=120,
    ),
    "linkedin": VideoSpec(
        max_size_mb=5120,
        max_duration_s=10 * 60,   # 10 min
        min_duration_s=3,
        allowed_formats=("mp4", "mov", "avi"),
        min_width=360,
        min_height=360,
    ),
}

PLATFORM_IMAGE_SPECS: dict[str, ImageSpec] = {
    "instagram": ImageSpec(
        max_size_mb=8,
        allowed_formats=("jpg", "jpeg", "png"),
        min_width=320,
        min_height=320,
        max_images_carousel=10,
    ),
    "tiktok": ImageSpec(
        max_size_mb=20,
        allowed_formats=("jpg", "jpeg", "png", "webp"),
        min_width=360,
        min_height=360,
        max_images_carousel=35,
    ),
    "youtube": ImageSpec(
        max_size_mb=2,
        allowed_formats=("jpg", "jpeg", "png"),
        min_width=1280,
        min_height=720,
        max_images_carousel=1,
    ),
    "twitter": ImageSpec(
        max_size_mb=5,
        allowed_formats=("jpg", "jpeg", "png", "gif", "webp"),
        min_width=1,
        min_height=1,
        max_images_carousel=4,
    ),
    "facebook": ImageSpec(
        max_size_mb=4,
        allowed_formats=("jpg", "jpeg", "png"),
        min_width=200,
        min_height=200,
        max_images_carousel=10,
    ),
    "linkedin": ImageSpec(
        max_size_mb=8,
        allowed_formats=("jpg", "jpeg", "png"),
        min_width=400,
        min_height=400,
        max_images_carousel=9,
    ),
}

# ---------------------------------------------------------------------------
# Caption / text limits per platform
# ---------------------------------------------------------------------------

CAPTION_LIMITS: dict[str, int] = {
    "instagram": 2200,
    "tiktok": 2200,
    "youtube": 5000,
    "twitter": 280,
    "facebook": 63206,
    "linkedin": 3000,
}


def _is_safe_url(url: str) -> bool:
    """Return False if the URL could reach private/internal infrastructure (SSRF guard)."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("https",):
            return False
        hostname = parsed.hostname or ""
        # Block localhost and metadata endpoints
        if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            return False
        # Block common cloud metadata endpoints
        if hostname in ("169.254.169.254", "metadata.google.internal"):
            return False
        # Block private IP ranges
        try:
            addr = ipaddress.ip_address(hostname)
            if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved:
                return False
        except ValueError:
            pass  # hostname is a domain name, not an IP — allow it
        return True
    except Exception:
        return False


def validate_media(
    platform: str,
    media_type: str,      # "image" | "video" | "carousel"
    media_urls: list[str],
    caption: Optional[str] = None,
    file_sizes_mb: Optional[list[float]] = None,  # if known upfront
) -> list[str]:
    """
    Returns a list of validation warnings/errors.
    Does NOT raise — callers decide whether to block or just warn.
    An empty list means all checks passed.
    """
    warnings: list[str] = []

    # SSRF guard — all URLs must be public HTTPS
    for url in media_urls:
        if not _is_safe_url(url):
            warnings.append(f"Unsafe or non-HTTPS URL rejected: {url}")

    # Caption length
    if caption and platform in CAPTION_LIMITS:
        limit = CAPTION_LIMITS[platform]
        if len(caption) > limit:
            warnings.append(
                f"{platform}: caption too long ({len(caption)} chars, max {limit})"
            )

    # URL count
    if not media_urls:
        if media_type in ("image", "video", "carousel"):
            warnings.append(f"{platform}: no media URLs provided")
        return warnings

    if media_type == "video":
        spec = PLATFORM_VIDEO_SPECS.get(platform)
        if spec and len(media_urls) > 1:
            warnings.append(f"{platform}: only 1 video per post (got {len(media_urls)})")

        # File extension check from URL
        url = media_urls[0]
        ext = url.split("?")[0].rsplit(".", 1)[-1].lower()
        if spec and ext and ext not in spec.allowed_formats:
            warnings.append(
                f"{platform}: video format '.{ext}' not supported. Allowed: {spec.allowed_formats}"
            )

    elif media_type in ("image", "carousel"):
        spec_img = PLATFORM_IMAGE_SPECS.get(platform)
        if spec_img:
            if len(media_urls) > spec_img.max_images_carousel:
                warnings.append(
                    f"{platform}: too many images ({len(media_urls)}, max {spec_img.max_images_carousel})"
                )
            for url in media_urls:
                ext = url.split("?")[0].rsplit(".", 1)[-1].lower()
                if ext and ext not in spec_img.allowed_formats:
                    warnings.append(
                        f"{platform}: image format '.{ext}' not supported. Allowed: {spec_img.allowed_formats}"
                    )

    # File size (if provided)
    if file_sizes_mb:
        if media_type == "video":
            spec_v = PLATFORM_VIDEO_SPECS.get(platform)
            if spec_v:
                for i, size in enumerate(file_sizes_mb):
                    if size > spec_v.max_size_mb:
                        warnings.append(
                            f"{platform}: video #{i+1} too large ({size:.1f} MB, max {spec_v.max_size_mb} MB)"
                        )
        else:
            spec_i = PLATFORM_IMAGE_SPECS.get(platform)
            if spec_i:
                for i, size in enumerate(file_sizes_mb):
                    if size > spec_i.max_size_mb:
                        warnings.append(
                            f"{platform}: image #{i+1} too large ({size:.1f} MB, max {spec_i.max_size_mb} MB)"
                        )

    return warnings
