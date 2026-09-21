import hashlib

from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
from app.core.config import get_settings
from app.integrations.nominatim import NominatimProvider
from app.schemas.place import GeocodeResult

settings = get_settings()
_provider = NominatimProvider()


def _key(prefix: str, *parts: str) -> str:
    raw = "|".join(parts)
    return f"{prefix}:{hashlib.sha1(raw.encode()).hexdigest()}"


async def geocode_search(db: Session, query: str, limit: int = 5) -> list[GeocodeResult]:
    key = _key("geocode", query.strip().lower(), str(limit))
    cached = cache_get(db, key)
    if cached is not None:
        return [GeocodeResult(**item) for item in cached]

    results = await _provider.search(query, limit=limit)
    cache_set(db, key, [r.model_dump() for r in results], settings.cache_ttl_geocode)
    return results


async def reverse_geocode(db: Session, latitude: float, longitude: float) -> GeocodeResult | None:
    key = _key("reverse", f"{latitude:.5f}", f"{longitude:.5f}")
    cached = cache_get(db, key)
    if cached is not None:
        return GeocodeResult(**cached) if cached else None

    result = await _provider.reverse(latitude, longitude)
    cache_set(db, key, result.model_dump() if result else None, settings.cache_ttl_geocode)
    return result
