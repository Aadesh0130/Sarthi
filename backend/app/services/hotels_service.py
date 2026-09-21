"""Hotels service (spec section 4D) -- wraps HotelbedsProvider. Rates get a
deliberately short cache TTL (spec section 11: "never cache live prices for
an inappropriate duration") and check_rate is never cached at all -- it must
hit Hotelbeds fresh every time, since its entire purpose is revalidation."""
import hashlib
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
from app.core.config import get_settings
from app.integrations.base import ProviderError
from app.integrations.hotelbeds import HotelbedsProvider
from app.schemas.hotel import HotelRateCheck, HotelResult, HotelSearchResponse

settings = get_settings()
_provider = HotelbedsProvider()


def _key(*parts: str) -> str:
    return "hotels:" + hashlib.sha1("|".join(parts).encode()).hexdigest()


async def search_hotels(
    db: Session, latitude: float, longitude: float, check_in: str, check_out: str,
    adults: int = 2, radius_km: int = 15,
) -> HotelSearchResponse:
    if not settings.hotels_configured:
        return HotelSearchResponse(
            configured=False,
            message="Hotels aren't configured yet. Set HOTELBEDS_API_KEY and HOTELBEDS_SECRET in backend/.env to enable real hotel search.",
        )

    key = _key(f"{latitude:.3f}", f"{longitude:.3f}", check_in, check_out, str(adults), str(radius_km))
    cached = cache_get(db, key)
    if cached is not None:
        return HotelSearchResponse(configured=True, hotels=[HotelResult(**h) for h in cached], retrieved_at=cached[0]["retrieved_at"] if cached else None)

    try:
        hotels = await _provider.search(latitude, longitude, check_in, check_out, adults, radius_km)
    except ProviderError as exc:
        return HotelSearchResponse(configured=True, message=f"Hotel availability is temporarily unavailable ({exc.detail}).")

    cache_set(db, key, [h.model_dump() for h in hotels], settings.cache_ttl_hotels)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    message = None if hotels else "No Hotelbeds hotels matched this area/date range."
    return HotelSearchResponse(configured=True, hotels=hotels, message=message, retrieved_at=retrieved_at)


async def get_hotel_content(db: Session, hotel_id: str) -> HotelResult | None:
    if not settings.hotels_configured:
        return None
    key = _key("content", hotel_id)
    cached = cache_get(db, key)
    if cached is not None:
        return HotelResult(**cached) if cached else None
    content = await _provider.get_content(hotel_id)
    cache_set(db, key, content.model_dump() if content else None, settings.cache_ttl_hotels * 24)
    return content


async def check_rate(db: Session, rate_key: str) -> HotelRateCheck:
    """Always a live call -- never served from cache (see module docstring)."""
    if not settings.hotels_configured:
        return HotelRateCheck(rate_key=rate_key, still_valid=False, checked_at=datetime.now(timezone.utc).isoformat())
    return await _provider.check_rate(rate_key)
