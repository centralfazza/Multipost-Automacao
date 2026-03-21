"""
Instagram publishing service.
Uses the Instagram Graph API (Content Publishing API).
Docs: https://developers.facebook.com/docs/instagram-api/guides/content-publishing
"""
from typing import Any, Optional
import httpx
from .base import BasePlatformService

BASE = "https://graph.facebook.com/v18.0"


class InstagramService(BasePlatformService):
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

        async with httpx.AsyncClient(timeout=60) as client:
            if media_type == "carousel" and len(media_urls) > 1:
                return await self._publish_carousel(client, access_token, account_id, full_caption, media_urls)
            elif media_type == "video":
                return await self._publish_video(client, access_token, account_id, full_caption, media_urls[0])
            else:
                return await self._publish_image(client, access_token, account_id, full_caption, media_urls[0])

    async def _publish_image(self, client, token, ig_id, caption, image_url) -> dict:
        # Step 1: Create container
        resp = await client.post(
            f"{BASE}/{ig_id}/media",
            params={
                "image_url": image_url,
                "caption": caption,
                "access_token": token,
            },
        )
        resp.raise_for_status()
        container_id = resp.json()["id"]

        # Step 2: Publish
        return await self._publish_container(client, token, ig_id, container_id)

    async def _publish_video(self, client, token, ig_id, caption, video_url) -> dict:
        resp = await client.post(
            f"{BASE}/{ig_id}/media",
            params={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "access_token": token,
            },
        )
        resp.raise_for_status()
        container_id = resp.json()["id"]
        return await self._publish_container(client, token, ig_id, container_id)

    async def _publish_carousel(self, client, token, ig_id, caption, media_urls) -> dict:
        # Step 1: Create item containers
        item_ids = []
        for url in media_urls:
            resp = await client.post(
                f"{BASE}/{ig_id}/media",
                params={"image_url": url, "is_carousel_item": True, "access_token": token},
            )
            resp.raise_for_status()
            item_ids.append(resp.json()["id"])

        # Step 2: Create carousel container
        resp = await client.post(
            f"{BASE}/{ig_id}/media",
            params={
                "media_type": "CAROUSEL",
                "children": ",".join(item_ids),
                "caption": caption,
                "access_token": token,
            },
        )
        resp.raise_for_status()
        container_id = resp.json()["id"]
        return await self._publish_container(client, token, ig_id, container_id)

    async def _publish_container(self, client, token, ig_id, container_id) -> dict:
        resp = await client.post(
            f"{BASE}/{ig_id}/media_publish",
            params={"creation_id": container_id, "access_token": token},
        )
        resp.raise_for_status()
        post_id = resp.json()["id"]
        return {
            "id": post_id,
            "url": f"https://www.instagram.com/p/{post_id}/",
        }
