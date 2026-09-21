"""
Nominatim geocoding provider (https://nominatim.org).

Respects Nominatim's usage policy: identifies itself with a descriptive
User-Agent, sends at most one in-flight request at a time from this process,
and every result is cached (see app/services/geocoding_service.py) so the
same query is never re-sent on every keystroke.
"""
import asyncio

import httpx

from app.core.config import get_settings
from app.integrations.base import GeocodingProvider, ProviderError
from app.schemas.place import GeocodeResult

settings = get_settings()

# Nominatim's policy asks for max ~1 request/second from a given client.
_throttle_lock = asyncio.Lock()
_min_interval = 1.05
_last_request_ts = 0.0

# Real, reproduced bug (2026-09-16): searching "Amritsar, Punjab, India" made
# Nominatim rank the ADMINISTRATIVE boundary result (type="administrative",
# the Amritsar tehsil/district polygon, centroid ~18km from the actual city --
# confirmed against the district's own cached Nominatim response, lat/lon
# 31.7686/74.8316) ahead of the actual city point (type="city",
# 31.6357/74.8787, ~500m from the Golden Temple). Every downstream call --
# nearby places, weather, Tourism Pressure, the Flow Rebalancer -- then
# correctly and honestly analyzed that wrong, genuinely rural spot, which is
# why it looked "broken" (near-zero real places, no alternatives found): the
# pipeline was working correctly on the wrong coordinate. A district/tehsil
# boundary is essentially never what a tourism search means when a
# point-like place of the same name is also on offer, so results of type
# "administrative" are demoted below any more location-precise result
# (city/town/village/attraction/...) with comparable importance -- but never
# reordered when no such precise alternative exists (e.g. "Kerala" or
# "Rajasthan" correctly still resolve to their state boundary, since that IS
# the best available point). This fixes destination resolution in general,
# not just for Amritsar -- any Indian place name that collides with an
# enclosing administrative area's own name is affected the same way.
_BROAD_BOUNDARY_TYPES = {"administrative"}
_BOUNDARY_DEMOTION_MARGIN = 0.05

# Nominatim's `address` breakdown (addressdetails=1) doesn't use one single
# consistent key for "district" across India's differently-mapped states --
# tried in priority order, first non-empty wins. This is intentionally
# generic (no state/city names anywhere in this list) so it works the same
# way for any Indian destination, not just ones seen during development.
_DISTRICT_ADDRESS_KEYS = ("state_district", "county", "city_district", "district")


def _extract_district(address: dict) -> str | None:
    for key in _DISTRICT_ADDRESS_KEYS:
        value = address.get(key)
        if value:
            return value
    return None


def _extract_state(address: dict) -> str | None:
    return address.get("state") or None


async def _throttle():
    global _last_request_ts
    async with _throttle_lock:
        loop = asyncio.get_event_loop()
        now = loop.time()
        wait = _min_interval - (now - _last_request_ts)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_request_ts = loop.time()


def _prefer_precise_over_boundary(results: list["GeocodeResult"]) -> list["GeocodeResult"]:
    """Stable re-rank: move any 'administrative' boundary result below the
    more location-precise results in the SAME result set, unless it is
    clearly the most prominent match by a wide importance margin (so a
    genuinely obscure same-name settlement never bumps a well-known region).
    See the module-level comment above for the real incident this fixes."""
    precise = [r for r in results if r.place_type not in _BROAD_BOUNDARY_TYPES]
    if not precise:
        return results  # nothing more precise on offer -- the boundary result is the best we have
    best_precise_importance = max((r.importance or 0.0) for r in precise)

    kept, demoted = [], []
    for r in results:
        is_broad = r.place_type in _BROAD_BOUNDARY_TYPES
        if is_broad and (r.importance or 0.0) <= best_precise_importance + _BOUNDARY_DEMOTION_MARGIN:
            demoted.append(r)
        else:
            kept.append(r)
    return kept + demoted


class NominatimProvider(GeocodingProvider):
    def __init__(self):
        self.base_url = settings.nominatim_base_url
        self.headers = {"User-Agent": settings.nominatim_user_agent}

    async def search(self, query: str, limit: int = 5) -> list[GeocodeResult]:
        if not query or not query.strip():
            return []
        await _throttle()
        # Always ask Nominatim for a few more than the caller wants: the
        # administrative-boundary-vs-precise-place re-ranking below (see
        # _prefer_precise_over_boundary) can only correct an ordering it can
        # actually see -- a bare limit=1 request (e.g. the Enter-to-search
        # path) would never even receive the better alternative to prefer.
        # The extra rows are trimmed back to `limit` before returning, so the
        # caller's contract (a list of at most `limit` results) is unchanged.
        fetch_limit = max(limit, 5)
        params = {
            "q": query.strip(),
            "format": "jsonv2",
            "limit": str(fetch_limit),
            # addressdetails=1 costs nothing extra request-wise (same call,
            # more fields) and lets the Tourist Flow Rebalancer know which
            # district a destination is actually in without a second,
            # separately-throttled reverse-geocode call for every search.
            "addressdetails": "1",
            "countrycodes": "in",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.base_url}/search", params=params, headers=self.headers)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError("nominatim", str(exc)) from exc

        results = []
        for item in data:
            try:
                bbox = [float(x) for x in item.get("boundingbox", [])] if item.get("boundingbox") else None
                address = item.get("address") or {}
                results.append(
                    GeocodeResult(
                        display_name=item["display_name"],
                        latitude=float(item["lat"]),
                        longitude=float(item["lon"]),
                        place_type=item.get("type"),
                        importance=item.get("importance"),
                        bounding_box=bbox,
                        district=_extract_district(address),
                        state=_extract_state(address),
                    )
                )
            except (KeyError, ValueError):
                continue
        return _prefer_precise_over_boundary(results)[:limit]

    async def reverse(self, latitude: float, longitude: float):
        await _throttle()
        params = {"lat": str(latitude), "lon": str(longitude), "format": "jsonv2", "addressdetails": "1"}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.base_url}/reverse", params=params, headers=self.headers)
                resp.raise_for_status()
                item = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError("nominatim", str(exc)) from exc
        if not item or "lat" not in item:
            return None
        address = item.get("address") or {}
        return GeocodeResult(
            display_name=item.get("display_name", ""),
            latitude=float(item["lat"]),
            longitude=float(item["lon"]),
            place_type=item.get("type"),
            district=_extract_district(address),
            state=_extract_state(address),
        )
