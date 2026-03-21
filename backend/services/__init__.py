"""
Platform service registry.
Import get_platform_service() to get the right publisher for a platform name.
"""
from .base import BasePlatformService
from .instagram import InstagramService
from .tiktok import TikTokService
from .youtube import YouTubeService
from .twitter import TwitterService
from .facebook import FacebookService
from .linkedin import LinkedInService

_REGISTRY: dict[str, BasePlatformService] = {
    "instagram": InstagramService(),
    "tiktok": TikTokService(),
    "youtube": YouTubeService(),
    "twitter": TwitterService(),
    "facebook": FacebookService(),
    "linkedin": LinkedInService(),
}


def get_platform_service(platform: str) -> BasePlatformService:
    service = _REGISTRY.get(platform)
    if not service:
        raise ValueError(f"No service registered for platform '{platform}'")
    return service
