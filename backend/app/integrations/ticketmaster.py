"""
Ticketmaster Discovery API event provider (spec section 4C).

Requires TICKETMASTER_API_KEY (free self-serve signup at
developer-acct.ticketmaster.com). Coverage is genuinely patchy outside
North America/Europe -- for many Indian destinations this will legitimately
return zero events. That is reported as-is; Sarthi never invents an event
to fill the gap (spec section 16).
"""
from typing import Optional

import httpx

from app.core.config import get_settings
from app.integrations.base import EventProvider, ProviderError
from app.schemas.event import EventResult

settings = get_settings()


def _event_from_json(raw: dict) -> Optional[EventResult]:
    event_id = raw.get("id")
    name = raw.get("name")
    if not event_id or not name:
        return None

    dates = raw.get("dates", {}) or {}
    start = dates.get("start", {}) or {}
    end = dates.get("end", {}) or {}
    status = (dates.get("status", {}) or {}).get("code")

    venues = (raw.get("_embedded", {}) or {}).get("venues", []) or []
    venue = venues[0] if venues else {}
    location = venue.get("location", {}) or {}
    address = venue.get("address", {}) or {}
    city = venue.get("city", {}) or {}
    venue_address = ", ".join(p for p in [address.get("line1"), city.get("name")] if p) or None

    classifications = raw.get("classifications", []) or []
    classification = None
    if classifications:
        segment = (classifications[0].get("segment") or {}).get("name")
        genre = (classifications[0].get("genre") or {}).get("name")
        classification = " / ".join(p for p in [segment, genre] if p and p != "Undefined") or None

    images = raw.get("images", []) or []
    image_url = images[0]["url"] if images else None

    price_ranges = raw.get("priceRanges", []) or []
    min_price = price_ranges[0].get("min") if price_ranges else None
    max_price = price_ranges[0].get("max") if price_ranges else None
    currency = price_ranges[0].get("currency") if price_ranges else None

    lat = location.get("latitude")
    lon = location.get("longitude")

    return EventResult(
        id=event_id,
        source="ticketmaster",
        source_url=raw.get("url"),
        name=name,
        description=raw.get("info") or raw.get("pleaseNote"),
        start_datetime=start.get("dateTime") or (f"{start.get('localDate')}T{start.get('localTime')}" if start.get("localDate") and start.get("localTime") else start.get("localDate")),
        end_datetime=end.get("dateTime"),
        venue_name=venue.get("name"),
        venue_address=venue_address,
        latitude=float(lat) if lat else None,
        longitude=float(lon) if lon else None,
        classification=classification,
        image_url=image_url,
        min_price=min_price,
        max_price=max_price,
        currency=currency,
        status=status,
        url=raw.get("url"),
    )


class TicketmasterProvider(EventProvider):
    def __init__(self):
        self.base_url = settings.ticketmaster_base_url
        self.api_key = settings.ticketmaster_api_key

    async def search(
        self, latitude: float, longitude: float, radius_km: int = 25,
        keyword: str = "", start_date: Optional[str] = None, end_date: Optional[str] = None,
    ) -> list[EventResult]:
        params = {
            "apikey": self.api_key,
            "latlong": f"{latitude},{longitude}",
            "radius": str(radius_km),
            "unit": "km",
            "size": "20",
            "sort": "date,asc",
        }
        if keyword:
            params["keyword"] = keyword
        if start_date:
            params["startDateTime"] = f"{start_date}T00:00:00Z"
        if end_date:
            params["endDateTime"] = f"{end_date}T23:59:59Z"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{self.base_url}/events.json", params=params)
                if resp.status_code == 401:
                    raise ProviderError("ticketmaster", "Invalid or unauthorized API key")
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return []  # Discovery API 404s on "no results" for some query shapes -- treat as empty, not an error
            raise ProviderError("ticketmaster", str(exc)) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("ticketmaster", str(exc)) from exc

        raw_events = (data.get("_embedded", {}) or {}).get("events", []) or []
        results = [_event_from_json(e) for e in raw_events]
        return [e for e in results if e is not None]

    async def get_details(self, event_id: str) -> Optional[EventResult]:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{self.base_url}/events/{event_id}.json", params={"apikey": self.api_key})
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError("ticketmaster", str(exc)) from exc
        return _event_from_json(data)
