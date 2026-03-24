"""
TikTok publishing service.
Uses the TikTok Content Posting API v2.
Docs: https://developers.tiktok.com/doc/content-posting-api-get-started
"""
import asyncio
import logging
from typing import Any, Optional

import httpx
from .base import BasePlatformService

BASE = "https://open.tiktokapis.com/v2"
logger = logging.getLogger(__name__)

# Status polling: check up to 10 times with 3s intervals
_POLL_MAX_ATTEMPTS = 10
_POLL_INTERVAL_S = 3


class TikTokService(BasePlatformService):
    async def publish(
        self,
        access_token: str,
        account_id: Optional[str],
        caption: str,
        media_urls: list[str],
        media_type: str,
        hashtags: Optional[str],
        extra_data: dict[str, Any],
    ) -> dict[str, Any]:
        full_caption = self._full_caption(caption, hashtags)

        async with httpx.AsyncClient(timeout=120) as client:
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"}

            if media_type == "video":
                result = await self._publish_video(client, headers, full_caption, media_urls[0], extra_data)
            else:
                result = await self._publish_photo(client, headers, full_caption, media_urls, extra_data)
            return result

    async def _poll_publish_status(self, client, headers, publish_id: str) -> dict:
        """Poll TikTok publish status to get the final post ID and URL."""
        for attempt in range(_POLL_MAX_ATTEMPTS):
            await asyncio.sleep(_POLL_INTERVAL_S)
            try:
                resp = await client.post(
                    f"{BASE}/post/publish/status/fetch/",
                    headers=headers,
                    json={"publish_id": publish_id},
                )
                resp.raise_for_status()
                data = resp.json().get("data", {})
                status = data.get("status", "")

                if status == "PUBLISH_COMPLETE":
                    tiktok_post_id = data.get("publicaly_available_post_id", [None])[0]
                    url = f"https://www.tiktok.com/@/video/{tiktok_post_id}" if tiktok_post_id else ""
                    return {"id": tiktok_post_id or publish_id, "url": url}
                elif status == "FAILED":
                    fail_reason = data.get("fail_reason", "Unknown error")
                    raise RuntimeError(f"TikTok publish failed: {fail_reason}")
            except httpx.HTTPStatusError:
                logger.warning("TikTok status poll attempt %d failed for %s", attempt + 1, publish_id)

        # Timed out waiting — return publish_id without URL
        logger.warning("TikTok publish status polling timed out for %s", publish_id)
        return {"id": publish_id, "url": ""}

    async def _publish_video(self, client, headers, caption, video_url, extra_data) -> dict:
        payload = {
            "post_info": {
                "title": caption[:2200],
                "privacy_level": extra_data.get("privacy_level", "PUBLIC_TO_EVERYONE"),
                "disable_duet": extra_data.get("disable_duet", False),
                "disable_comment": extra_data.get("disable_comment", False),
                "disable_stitch": extra_data.get("disable_stitch", False),
            },
            "source_info": {
                "source": "PULL_FROM_URL",
                "video_url": video_url,
            },
        }

        resp = await client.post(f"{BASE}/post/publish/video/init/", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        publish_id = data.get("publish_id", "")

        if not publish_id:
            raise RuntimeError("TikTok did not return a publish_id")

        return await self._poll_publish_status(client, headers, publish_id)

    async def _publish_photo(self, client, headers, caption, image_urls, extra_data) -> dict:
        payload = {
            "post_info": {
                "title": caption[:2200],
                "privacy_level": extra_data.get("privacy_level", "PUBLIC_TO_EVERYONE"),
                "disable_comment": extra_data.get("disable_comment", False),
            },
            "source_info": {
                "source": "PULL_FROM_URL",
                "photo_cover_index": 0,
                "photo_images": image_urls,
            },
            "post_mode": "DIRECT_POST",
            "media_type": "PHOTO",
        }

        resp = await client.post(f"{BASE}/post/publish/content/init/", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        publish_id = data.get("publish_id", "")

        if not publish_id:
            raise RuntimeError("TikTok did not return a publish_id")

        return await self._poll_publish_status(client, headers, publish_id)
