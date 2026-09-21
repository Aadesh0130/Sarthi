import hashlib

from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_get_stale, cache_set
from app.core.config import get_settings
from app.integrations.base import ProviderError
from app.integrations.overpass import OverpassProvider
from app.schemas.place import District, Place, PlaceDetails, Settlement

settings = get_settings()
_provider = OverpassProvider()

# Radius fallback (spec: "Radius Strategy" -- primary radius first, only
# escalate when genuinely sparse, cap the number of extra Overpass calls,
# cache every tier independently). A destination's own requested radius is
# always tier 1; tiers 2/3 widen it, capped at the API's own documented
# upper bound (see Query(..., le=15000) in app/api/places.py) so a fallback
# search never asks for more than the endpoint itself would ever accept.
_SPARSE_MIN_RESULTS = 6
_RADIUS_FALLBACK_MULTIPLIERS = (1, 2, 3)
_MAX_RADIUS_METERS = 15000


def _key(prefix: str, *parts: str) -> str:
    raw = "|".join(parts)
    return f"{prefix}:{hashlib.sha1(raw.encode()).hexdigest()}"


def _distance_meters(lat1, lon1, lat2, lon2) -> float:
    from math import atan2, cos, radians, sin, sqrt
    r = 6371000.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return r * 2 * atan2(sqrt(a), sqrt(1 - a))


async def _nearby_places_at_radius(
    db: Session, latitude: float, longitude: float, radius_meters: int, categories: list[str],
    meta: dict | None,
) -> list[Place]:
    """One radius tier's worth of the actual fetch-cache-filter pipeline --
    factored out so the escalation loop in nearby_places() below can call it
    once per tier, each tier cached under its own key exactly as before."""
    key = _key("nearby", f"{latitude:.4f}", f"{longitude:.4f}", str(radius_meters), ",".join(sorted(categories)))
    cached = cache_get(db, key)
    if cached is not None:
        places = [Place(**item) for item in cached]
    else:
        try:
            places = await _provider.nearby(latitude, longitude, radius_meters, categories)
        except ProviderError:
            stale = cache_get_stale(db, key, settings.cache_ttl_places, settings.cache_stale_grace_places)
            if stale is None:
                raise  # nothing live, nothing cached either -- an honest failure, not a guess
            payload, age_seconds = stale
            places = [Place(**item) for item in payload]
            if meta is not None:
                meta["stale_seconds"] = age_seconds
        else:
            cache_set(db, key, [p.model_dump() for p in places], settings.cache_ttl_places)

    for p in places:
        p.distance_meters = round(_distance_meters(latitude, longitude, p.latitude, p.longitude), 1)

    # Overpass's "around:" filter guarantees every matched element genuinely has some part
    # of its geometry within the radius -- but for a way/relation (a long ghat, a river, an
    # administrative boundary...) the "out center" coordinate it hands back is the bounding-
    # box centroid of the WHOLE feature, which can land far outside the radius even though
    # only a sliver of it actually matched nearby. That shows up as a real OSM place plotted
    # hundreds of km from the searched destination. Rather than surface that centroid
    # artifact as a "nearby" result, drop anything whose computed distance is well past the
    # radius actually asked for.
    max_distance = radius_meters * 1.5
    places = [p for p in places if p.distance_meters is not None and p.distance_meters <= max_distance]

    places.sort(key=lambda p: p.distance_meters or 0)
    return places


async def nearby_places(
    db: Session, latitude: float, longitude: float, radius_meters: int, categories: list[str],
    meta: dict | None = None,
) -> list[Place]:
    """`meta`, when passed as an empty dict, is filled in with:
    - `stale_seconds` when the result had to fall back to an out-of-date cache
      entry because every live mirror failed on the call that ultimately
      produced these results (see cache_get_stale);
    - `requested_radius_meters` / `effective_radius_meters`, always, so a
      caller that escalated past the caller's own requested radius (see
      below) can say so honestly instead of claiming the original figure.
    Callers that don't care about either can simply omit `meta` and get the
    same resilience/escalation for free.

    Radius escalation (spec: "Radius Strategy"): a genuinely sparse result at
    the requested radius does not necessarily mean the area has no more
    tourism places -- it may just mean the radius was too tight. Rather than
    permanently under-serving a destination or (the opposite mistake) always
    querying a huge radius regardless of density, this tries progressively
    wider tiers (1x, 2x, 3x the requested radius, capped at
    _MAX_RADIUS_METERS) ONLY when the previous tier came back with fewer than
    _SPARSE_MIN_RESULTS places, stopping at the first tier that is no longer
    sparse. Each tier is cached under its own key, so a repeated search for
    the same genuinely-sparse spot never re-does all three live fetches.

    A wider tier can genuinely have neither a live provider response nor its
    own cache entry (it's a radius nobody has ever searched from this exact
    spot before) even when a narrower tier just successfully served a
    (possibly stale) result -- that must never turn an already-real partial
    success into a hard failure. Only the very FIRST tier's failure is
    allowed to propagate as an honest ProviderError (see
    _nearby_places_at_radius's own "nothing live, nothing cached either"
    comment); any later tier's failure just stops the widening and returns
    whatever the last successful tier already found."""
    tried_radii: set[int] = set()
    places: list[Place] = []
    effective_radius = radius_meters
    found_any_tier = False
    for multiplier in _RADIUS_FALLBACK_MULTIPLIERS:
        radius = min(radius_meters * multiplier, _MAX_RADIUS_METERS)
        if radius in tried_radii:
            break  # already capped out at _MAX_RADIUS_METERS -- widening further would repeat the same query
        tried_radii.add(radius)
        try:
            tier_places = await _nearby_places_at_radius(db, latitude, longitude, radius, categories, meta)
        except ProviderError:
            if not found_any_tier:
                raise  # the requested radius itself has nothing live and nothing cached -- an honest failure, not a guess
            break  # a wider tier we've never searched before just isn't available right now -- keep the earlier result
        places = tier_places
        effective_radius = radius
        found_any_tier = True
        if len(places) >= _SPARSE_MIN_RESULTS or radius >= _MAX_RADIUS_METERS:
            break

    if meta is not None:
        meta["requested_radius_meters"] = radius_meters
        meta["effective_radius_meters"] = effective_radius
    return places


async def nearby_settlements(
    db: Session, latitude: float, longitude: float, radius_meters: int, meta: dict | None = None,
) -> list[Settlement]:
    """Real nearby towns/villages (not tourist POIs) -- candidate discovery
    for the Tourist Flow Rebalancer. Same cache-then-live-then-stale-fallback
    pattern as nearby_places, under its own cache-key prefix so it never
    collides with (or duplicates a request already made by) the POI cache."""
    key = _key("settlements", f"{latitude:.4f}", f"{longitude:.4f}", str(radius_meters))
    cached = cache_get(db, key)
    if cached is not None:
        settlements = [Settlement(**item) for item in cached]
    else:
        try:
            settlements = await _provider.nearby_settlements(latitude, longitude, radius_meters)
        except ProviderError:
            stale = cache_get_stale(db, key, settings.cache_ttl_places, settings.cache_stale_grace_places)
            if stale is None:
                raise
            payload, age_seconds = stale
            settlements = [Settlement(**item) for item in payload]
            if meta is not None:
                meta["stale_seconds"] = age_seconds
        else:
            cache_set(db, key, [s.model_dump() for s in settlements], settings.cache_ttl_places)
    return settlements


async def nearby_districts(
    db: Session, latitude: float, longitude: float, radius_meters: int, meta: dict | None = None,
) -> list[District]:
    """Real nearby administrative districts (Tourist Flow Rebalancer's
    "Nearby Similar Districts" candidate discovery) -- same
    cache-then-live-then-stale-fallback pattern as nearby_settlements, under
    its own cache-key prefix. A bad/empty provider response is never cached
    as a successful result (cache_set only runs in the success branch below,
    same as every other provider call in this file)."""
    key = _key("districts", f"{latitude:.4f}", f"{longitude:.4f}", str(radius_meters))
    cached = cache_get(db, key)
    if cached is not None:
        districts = [District(**item) for item in cached]
    else:
        try:
            districts = await _provider.nearby_districts(latitude, longitude, radius_meters)
        except ProviderError:
            stale = cache_get_stale(db, key, settings.cache_ttl_places, settings.cache_stale_grace_places)
            if stale is None:
                raise
            payload, age_seconds = stale
            districts = [District(**item) for item in payload]
            if meta is not None:
                meta["stale_seconds"] = age_seconds
        else:
            cache_set(db, key, [d.model_dump() for d in districts], settings.cache_ttl_places)
    return districts


async def get_place_details(db: Session, place_id: str) -> PlaceDetails | None:
    key = _key("details", place_id)
    cached = cache_get(db, key)
    if cached is not None:
        return PlaceDetails(**cached) if cached else None

    details = await _provider.get_details(place_id)
    cache_set(db, key, details.model_dump() if details else None, settings.cache_ttl_places)
    return details
