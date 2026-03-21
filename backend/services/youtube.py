"""
YouTube publishing service.
Uses the YouTube Data API v3 to upload videos.
Docs: https://developers.google.com/youtube/v3/docs/videos/insert
"""
from typing import Any, Optional
import httpx
from .base import BasePlatformService


class YouTubeService(BasePlatformService):
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
        if not media_urls:
            raise ValueError("YouTube requires at least one video URL")

        video_url = media_urls[0]
        full_caption = self._full_caption(caption, hashtags)

        # YouTube requires uploading the video bytes — we download then upload
        async with httpx.AsyncClient(timeout=300) as client:
            # Download the video
            video_resp = await client.get(video_url)
            video_resp.raise_for_status()
            video_bytes = video_resp.content

            # Resumable upload metadata
            metadata = {
                "snippet": {
                    "title": extra_data.get("title", caption[:100]),
                    "description": full_caption,
                    "tags": extra_data.get("tags", []),
                    "categoryId": extra_data.get("category_id", "22"),  # 22 = People & Blogs
                },
                "status": {
                    "privacyStatus": extra_data.get("privacy_status", "public"),
                    "selfDeclaredMadeForKids": extra_data.get("made_for_kids", False),
                },
            }

            # Step 1: initiate resumable upload
            init_resp = await client.post(
                "https://www.googleapis.com/upload/youtube/v3/videos",
                params={"uploadType": "resumable", "part": "snippet,status"},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json; charset=UTF-8",
                    "X-Upload-Content-Type": "video/*",
                    "X-Upload-Content-Length": str(len(video_bytes)),
                },
                json=metadata,
            )
            init_resp.raise_for_status()
            upload_url = init_resp.headers["Location"]

            # Step 2: upload video bytes
            upload_resp = await client.put(
                upload_url,
                content=video_bytes,
                headers={"Content-Type": "video/*"},
            )
            upload_resp.raise_for_status()
            video_id = upload_resp.json()["id"]

        return {
            "id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
        }
