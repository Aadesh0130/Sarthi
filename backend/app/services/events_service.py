"""Events service (spec section 4C) -- wraps TicketmasterProvider with
caching and the honest not-configured/empty-result reporting spec sections
13/16 require."""
import hashlib

from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
from app.core.config import get_settings
from app.integrations.base import ProviderError
from app.integrations.ticketmaster import TicketmasterProvider
from app.schemas.event import EventResult, EventSearchResponse

settings = get_settings()
_provider = TicketmasterProvider()


def _key(*parts: str) -> str:
    return "events:" + hashlib.sha1("|".join(parts).encode()).hexdigest()


async def search_events(
    db: Session, latitude: float, longitude: float, radius_km: int = 25, keyword: str = "",
    start_date: str | None = None, end_date: str | None = None,
) -> EventSearchResponse:
    if not settings.events_configured:
        return EventSearchResponse(
            configured=False,
            message="Events aren't configured yet. Set TICKETMASTER_API_KEY in backend/.env to enable real event search.",
        )

    key = _key(f"{latitude:.3f}", f"{longitude:.3f}", str(radius_km), keyword, start_date or "", end_date or "")
    cached = cache_get(db, key)
    if cached is not None:
        return EventSearchResponse(configured=True, events=[EventResult(**e) for e in cached])

    try:
        events = await _provider.search(latitude, longitude, radius_km, keyword, start_date, end_date)
    except ProviderError as exc:
        return EventSearchResponse(configured=True, message=f"Events are temporarily unavailable ({exc.detail}).")

    cache_set(db, key, [e.model_dump() for e in events], settings.cache_ttl_events)
    message = None if events else "No Ticketmaster-listed events matched this area/date range."
    return EventSearchResponse(configured=True, events=events, message=message)
