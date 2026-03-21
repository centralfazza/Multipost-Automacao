"""
Twitter / X publishing service.
Uses the Twitter API v2 to create tweets with media.
Docs: https://developer.twitter.com/en/docs/twitter-api/tweets/manage-tweets/api-reference/post-tweets
"""
from typing import Any, Optional
import httpx
from .base import BasePlatformService

UPLOAD_BASE = "https://upload.twitter.com/1.1"
API_BASE = "https://api.twitter.com/2"


class TwitterService(BasePlatformService):
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
        full_text = self._full_caption(caption, hashtags)[:280]  # Twitter limit
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=120) as client:
            media_ids = []
            for url in media_urls[:4]:  # Twitter allows max 4 images or 1 video
                media_id = await self._upload_media(client, headers, url, media_type)
                media_ids.append(media_id)

            payload: dict[str, Any] = {"text": full_text}
            if media_ids:
                payload["media"] = {"media_ids": media_ids}

            resp = await client.post(
                f"{API_BASE}/tweets",
                headers={**headers, "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            tweet_id = resp.json()["data"]["id"]

        return {
            "id": tweet_id,
            "url": f"https://twitter.com/i/web/status/{tweet_id}",
        }

    async def _upload_media(self, client, headers, media_url, media_type) -> str:
        """Upload media via chunked INIT/APPEND/FINALIZE flow."""
        # Download media
        dl = await client.get(media_url)
        dl.raise_for_status()
        media_bytes = dl.content
        total_bytes = len(media_bytes)

        media_category = "tweet_video" if media_type == "video" else "tweet_image"
        content_type = "video/mp4" if media_type == "video" else "image/jpeg"

        # INIT
        init_resp = await client.post(
            f"{UPLOAD_BASE}/media/upload.json",
            headers=headers,
            data={
                "command": "INIT",
                "total_bytes": total_bytes,
                "media_type": content_type,
                "media_category": media_category,
            },
        )
        init_resp.raise_for_status()
        media_id = init_resp.json()["media_id_string"]

        # APPEND (single chunk — fine for most files; add chunking for large videos)
        append_resp = await client.post(
            f"{UPLOAD_BASE}/media/upload.json",
            headers=headers,
            data={"command": "APPEND", "media_id": media_id, "segment_index": 0},
            files={"media": media_bytes},
        )
        append_resp.raise_for_status()

        # FINALIZE
        fin_resp = await client.post(
            f"{UPLOAD_BASE}/media/upload.json",
            headers=headers,
            data={"command": "FINALIZE", "media_id": media_id},
        )
        fin_resp.raise_for_status()

        return media_id
