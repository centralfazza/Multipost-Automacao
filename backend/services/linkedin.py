"""
LinkedIn publishing service.
Uses the LinkedIn Marketing API (UGC Posts) to publish to a personal profile or company page.
Docs: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/ugc-post-api
"""
from typing import Any, Optional
import httpx
from .base import BasePlatformService

BASE = "https://api.linkedin.com/v2"


class LinkedInService(BasePlatformService):
    async def publish(
        self,
        access_token: str,
        account_id: Optional[str],  # "urn:li:person:xxx" or "urn:li:organization:xxx"
        caption: str,
        media_urls: list[str],
        media_type: str,
        hashtags: Optional[str],
        extra_data: dict[str, Any],
    ) -> dict[str, Any]:
        full_caption = self._full_caption(caption, hashtags)
        author_urn = account_id  # must be urn:li:person:xxx or urn:li:organization:xxx
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            if media_type in ("image", "carousel") and media_urls:
                return await self._publish_with_image(client, headers, author_urn, full_caption, media_urls[0])
            elif media_type == "video" and media_urls:
                return await self._publish_with_video(client, headers, author_urn, full_caption, media_urls[0])
            else:
                return await self._publish_text(client, headers, author_urn, full_caption)

    async def _publish_text(self, client, headers, author, text) -> dict:
        payload = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        resp = await client.post(f"{BASE}/ugcPosts", headers=headers, json=payload)
        resp.raise_for_status()
        post_id = resp.headers.get("x-restli-id", resp.json().get("id", ""))
        return {"id": post_id, "url": f"https://www.linkedin.com/feed/update/{post_id}/"}

    async def _publish_with_image(self, client, headers, author, text, image_url) -> dict:
        # Step 1: Register upload
        reg_resp = await client.post(
            f"{BASE}/assets?action=registerUpload",
            headers=headers,
            json={
                "registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                    "owner": author,
                    "serviceRelationships": [
                        {"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}
                    ],
                }
            },
        )
        reg_resp.raise_for_status()
        reg_data = reg_resp.json()
        upload_url = reg_data["value"]["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        asset = reg_data["value"]["asset"]

        # Step 2: Download then upload image
        img_resp = await client.get(image_url)
        img_resp.raise_for_status()
        await client.put(
            upload_url,
            content=img_resp.content,
            headers={"Content-Type": "image/jpeg"},
        )

        # Step 3: Create post
        payload = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "IMAGE",
                    "media": [{"status": "READY", "media": asset}],
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        resp = await client.post(f"{BASE}/ugcPosts", headers=headers, json=payload)
        resp.raise_for_status()
        post_id = resp.headers.get("x-restli-id", "")
        return {"id": post_id, "url": f"https://www.linkedin.com/feed/update/{post_id}/"}

    async def _publish_with_video(self, client, headers, author, text, video_url) -> dict:
        # Step 1: Register video upload
        reg_resp = await client.post(
            f"{BASE}/assets?action=registerUpload",
            headers=headers,
            json={
                "registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-video"],
                    "owner": author,
                    "serviceRelationships": [
                        {"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}
                    ],
                    "supportedUploadMechanism": ["SYNCHRONOUS_UPLOAD"],
                }
            },
        )
        reg_resp.raise_for_status()
        reg_data = reg_resp.json()
        upload_url = reg_data["value"]["uploadMechanism"][
            "com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"
        ]["uploadUrl"]
        asset = reg_data["value"]["asset"]

        # Step 2: Download then upload video
        vid_resp = await client.get(video_url)
        vid_resp.raise_for_status()
        await client.put(
            upload_url,
            content=vid_resp.content,
            headers={"Content-Type": "video/mp4"},
        )

        # Step 3: Create post
        payload = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "VIDEO",
                    "media": [{"status": "READY", "media": asset}],
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        resp = await client.post(f"{BASE}/ugcPosts", headers=headers, json=payload)
        resp.raise_for_status()
        post_id = resp.headers.get("x-restli-id", "")
        return {"id": post_id, "url": f"https://www.linkedin.com/feed/update/{post_id}/"}
