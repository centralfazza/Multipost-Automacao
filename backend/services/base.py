"""
Base class for all platform publishing services.
Each service must implement the `publish` method.
"""
from abc import ABC, abstractmethod
from typing import Any, Optional


class BasePlatformService(ABC):
    """
    Contract for a platform publisher.

    publish() must return a dict with at least:
        {
            "id": "<platform post id>",
            "url": "<public url of the post>"   # optional
        }
    """

    @abstractmethod
    async def publish(
        self,
        access_token: str,
        account_id: Optional[str],
        caption: str,
        media_urls: list[str],
        media_type: str,         # "image" | "video" | "carousel"
        hashtags: Optional[str],
        extra_data: dict[str, Any],
    ) -> dict[str, Any]:
        ...

    def _full_caption(self, caption: str, hashtags: Optional[str]) -> str:
        if hashtags:
            return f"{caption}\n\n{hashtags}"
        return caption
