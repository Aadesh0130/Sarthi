"""Images service (spec section 4F) -- wraps UnsplashProvider with caching.
Caching the returned URLs/attribution metadata (not the images themselves)
is within Unsplash's guidelines; Sarthi never downloads or re-hosts photos."""
import hashlib

from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
from app.core.config import get_settings
from app.integrations.base import ProviderError
from app.integrations.unsplash import UnsplashProvider
from app.schemas.image import ImageResult, ImageSearchResponse

settings = get_settings()
_provider = UnsplashProvider()


def _key(*parts: str) -> str:
    return "images:" + hashlib.sha1("|".join(parts).encode()).hexdigest()


async def search_images(db: Session, query: str, count: int = 3) -> ImageSearchResponse:
    if not settings.images_configured:
        return ImageSearchResponse(
            configured=False,
            message="Images aren't configured yet. Set UNSPLASH_ACCESS_KEY in backend/.env to enable real destination photos.",
        )

    key = _key(query.lower().strip(), str(count))
    cached = cache_get(db, key)
    if cached is not None:
        return ImageSearchResponse(configured=True, images=[ImageResult(**i) for i in cached])

    try:
        images = await _provider.search(query, count)
    except ProviderError as exc:
        return ImageSearchResponse(configured=True, message=f"Images are temporarily unavailable ({exc.detail}).")

    cache_set(db, key, [i.model_dump() for i in images], settings.cache_ttl_images)
    message = None if images else "No relevant Unsplash photo found for this query."
    return ImageSearchResponse(configured=True, images=images, message=message)
