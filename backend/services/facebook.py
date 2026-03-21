"""
Facebook publishing service.
Uses the Graph API to post to a Facebook Page (photo or video).
Docs: https://developers.facebook.com/docs/graph-api/reference/page/photos
"""
import json
from typing import Any, Optional
import httpx
from .base import BasePlatformService

BASE = "https://graph.facebook.com/v18.0"


class FacebookService(BasePlatformService):
    async def publish(
        self,
        access_token: str,
        account_id: Optional[str],  # Facebook Page ID
        caption: str,
        media_urls: list[str],
        media_type: str,
        hashtags: Optional[str],
        extra_data: dict[str, Any],
    ) -> dict[str, Any]:
        full_caption = self._full_caption(caption, hashtags)
        page_id = account_id

        async with httpx.AsyncClient(timeout=120) as client:
            if media_type == "video":
                return await self._publish_video(client, page_id, access_token, full_caption, media_urls[0])
            elif media_type == "carousel" and len(media_urls) > 1:
                return await self._publish_multi_photo(client, page_id, access_token, full_caption, media_urls)
            else:
                return await self._publish_photo(client, page_id, access_token, full_caption, media_urls[0])

    async def _publish_photo(self, client, page_id, token, caption, image_url) -> dict:
        resp = await client.post(
            f"{BASE}/{page_id}/photos",
            params={"url": image_url, "caption": caption, "access_token": token},
        )
        resp.raise_for_status()
        post_id = resp.json()["id"]
        return {"id": post_id, "url": f"https://www.facebook.com/{post_id}"}

    async def _publish_multi_photo(self, client, page_id, token, caption, image_urls) -> dict:
        # Upload each photo without publishing
        photo_ids = []
        for url in image_urls:
            resp = await client.post(
                f"{BASE}/{page_id}/photos",
                params={"url": url, "published": False, "access_token": token},
            )
            resp.raise_for_status()
            photo_ids.append({"media_fbid": resp.json()["id"]})

        # Create feed post linking all photos
        resp = await client.post(
            f"{BASE}/{page_id}/feed",
            params={
                "message": caption,
                "access_token": token,
                "attached_media": json.dumps(photo_ids),  # must be valid JSON, not Python repr
            },
        )
        resp.raise_for_status()
        post_id = resp.json()["id"]
        return {"id": post_id, "url": f"https://www.facebook.com/{post_id}"}

    async def _publish_video(self, client, page_id, token, caption, video_url) -> dict:
        resp = await client.post(
            f"{BASE}/{page_id}/videos",
            params={"file_url": video_url, "description": caption, "access_token": token},
        )
        resp.raise_for_status()
        video_id = resp.json()["id"]
        return {"id": video_id, "url": f"https://www.facebook.com/video/{video_id}"}
