"""
Unsplash image provider (spec section 4F).

Requires UNSPLASH_ACCESS_KEY (free "Demo" tier, self-serve at
unsplash.com/developers -- rate-limited to 50 requests/hour on Demo).
Images are hotlinked using the URLs the API returns; Sarthi never downloads,
re-hosts or trains on them, and every result carries the photographer +
Unsplash attribution the API guidelines require.

KNOWN LIMITATION (documented, not worked around): Unsplash's guidelines ask
apps to ping a `download_location` tracking endpoint when a photo is
actually used/downloaded by a person. Sarthi only displays search results
(no "save this photo" feature exists yet), so that tracking call is not
implemented -- see the final report.
"""
from typing import Optional

import httpx

from app.core.config import get_settings
from app.integrations.base import ImageProvider, ProviderError
from app.schemas.image import ImageResult

settings = get_settings()


class UnsplashProvider(ImageProvider):
    def __init__(self):
        self.base_url = settings.unsplash_base_url
        self.access_key = settings.unsplash_access_key

    async def search(self, query: str, count: int = 3) -> list[ImageResult]:
        headers = {"Authorization": f"Client-ID {self.access_key}", "Accept-Version": "v1"}
        params = {"query": query, "per_page": str(min(count, 10)), "orientation": "landscape"}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{self.base_url}/search/photos", params=params, headers=headers)
                if resp.status_code == 401:
                    raise ProviderError("unsplash", "Invalid Unsplash access key")
                if resp.status_code == 403:
                    raise ProviderError("unsplash", "Unsplash rate limit exceeded (Demo tier: 50 req/hour)")
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError("unsplash", str(exc)) from exc

        results: list[ImageResult] = []
        for photo in data.get("results", []) or []:
            urls = photo.get("urls", {}) or {}
            user = photo.get("user", {}) or {}
            user_links = user.get("links", {}) or {}
            links = photo.get("links", {}) or {}
            if not urls.get("regular") or not user.get("name"):
                continue
            results.append(
                ImageResult(
                    id=photo.get("id", ""),
                    url=urls["regular"],
                    thumb_url=urls.get("thumb", urls["regular"]),
                    width=photo.get("width", 0),
                    height=photo.get("height", 0),
                    description=photo.get("description") or photo.get("alt_description"),
                    photographer_name=user["name"],
                    photographer_profile_url=user_links.get("html", "https://unsplash.com"),
                    unsplash_url=links.get("html", "https://unsplash.com"),
                )
            )
        return results
