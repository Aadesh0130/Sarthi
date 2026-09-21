import hashlib

from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
from app.core.config import get_settings
from app.integrations.osrm import OSRMProvider
from app.schemas.route import RouteResponse, RouteStop

settings = get_settings()
_provider = OSRMProvider()


async def compute_route(db: Session, stops: list[RouteStop], profile: str) -> RouteResponse:
    raw = profile + "|" + "|".join(f"{s.latitude:.5f},{s.longitude:.5f}" for s in stops)
    key = f"route:{hashlib.sha1(raw.encode()).hexdigest()}"
    cached = cache_get(db, key)
    if cached is not None:
        return RouteResponse(**cached)

    route = await _provider.route(stops, profile)
    cache_set(db, key, route.model_dump(), settings.cache_ttl_route)
    return route
