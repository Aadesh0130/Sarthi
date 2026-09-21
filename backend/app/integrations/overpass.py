"""
Overpass API places provider (OpenStreetMap POI data).

Supports the category set described in the project spec section 6:
attractions, museums, monuments/historic sites, temples/religious places,
parks, restaurants, cafes, shopping and hotels. Every returned Place is
built only from OSM tags that were actually present -- nothing is guessed.

The public Overpass instances are shared, free infrastructure and routinely
return 504/502/503 under load, independent of anything this app does. Two
real mitigations, not a workaround that hides the problem:
  1. The query itself is built to be as cheap as possible for the Overpass
     server to plan and run -- one regex-consolidated selector per OSM key
     using the "nwr" combined node/way/relation type, instead of a separate
     clause per (key, value, element-type) triple. For the default "every
     category" search this cuts the query from dozens of clauses to about
     nine.
  2. If the primary instance is slow or erroring, the request is HEDGED onto
     the next public mirror in `OVERPASS_MIRRORS` (run concurrently, not
     tried one after another) rather than given up on -- these are
     independently run, independently loaded servers, so a timeout on one is
     not evidence the others will fail too. Hedging (not sequential retry)
     matters here: waiting out each mirror's full timeout one after another
     would make the worst case 3x as long, which is itself enough to trip a
     client-side abort before the backend ever gets to answer.
  3. Real-world report (2026-09-15): all three original mirrors failed at
     once for the same query (overpass-api.de: 504, kumi.systems:
     ReadTimeout, openstreetmap.ru: ConnectTimeout) -- these are shared free
     instances and can all be under load simultaneously, so redundancy alone
     can't guarantee an answer every time. A fourth independent mirror
     (overpass.osm.ch) was added for better odds, and a places_service-level
     stale-cache fallback (see cache_stale_grace_places in config.py) covers
     the case where a location was fetched successfully before but every
     mirror fails on this particular request.
"""
import asyncio
import re

import httpx

from app.core.config import get_settings
from app.integrations.base import PlacesProvider, ProviderError
from app.schemas.place import District, Place, PlaceDetails, Settlement

settings = get_settings()

# Independently-run public Overpass instances (no API key, same query language).
# The configured OVERPASS_BASE_URL (default overpass-api.de, the largest/most
# well-known instance) is always tried first; these are only used as a fallback
# when it errors or times out, never in place of it.
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
]

# category -> list of (key, value) OSM tag filters. value=None means "key exists".
CATEGORY_TAGS: dict[str, list[tuple[str, str | None]]] = {
    "attraction": [("tourism", "attraction"), ("tourism", "viewpoint"), ("tourism", "artwork")],
    "museum": [("tourism", "museum"), ("tourism", "gallery")],
    "historic": [
        ("historic", "monument"), ("historic", "memorial"), ("historic", "castle"),
        ("historic", "ruins"), ("historic", "archaeological_site"), ("historic", "fort"),
        ("historic", "citadel"), ("historic", "tomb"),
    ],
    "religious": [("amenity", "place_of_worship")],
    "park": [("leisure", "park"), ("leisure", "garden"), ("leisure", "nature_reserve")],
    "restaurant": [("amenity", "restaurant")],
    "cafe": [("amenity", "cafe")],
    "shopping": [("shop", None)],
    "hotel": [("tourism", "hotel"), ("tourism", "guest_house"), ("tourism", "hostel")],
}

ALL_CATEGORIES = list(CATEGORY_TAGS.keys())


def _normalize_category(tags: dict) -> str:
    for category, filters in CATEGORY_TAGS.items():
        for key, value in filters:
            if key in tags and (value is None or tags[key] == value):
                return category
    return "other"


def _build_query(lat: float, lon: float, radius_m: int, categories: list[str]) -> str:
    cats = categories or ALL_CATEGORIES

    # Group every (key, value) filter that applies by OSM key, so each key gets ONE
    # "nwr" (node+way+relation combined) clause with a regex value-alternation instead
    # of a separate node/way/relation line per individual tag value. For the default
    # "every category" search this takes the query from dozens of clauses down to about
    # nine -- a much cheaper query for the (free, shared, easily overloaded) public
    # Overpass servers to plan and execute, which is the main real-world cause of the
    # timeouts/504s this radius+category combination can otherwise trigger.
    values_by_key: dict[str, set[str | None]] = {}
    for cat in cats:
        for key, value in CATEGORY_TAGS.get(cat, []):
            values_by_key.setdefault(key, set()).add(value)

    clauses = []
    for key, values in values_by_key.items():
        if None in values:
            selector = f'["{key}"]'  # any value for this key (e.g. shop=*)
        elif len(values) == 1:
            selector = f'["{key}"="{next(iter(values))}"]'
        else:
            pattern = "^(" + "|".join(re.escape(v) for v in sorted(values)) + ")$"
            selector = f'["{key}"~"{pattern}"]'
        clauses.append(f'nwr{selector}(around:{radius_m},{lat},{lon});')
    body = "\n  ".join(clauses)
    # A lower server-side timeout means an overloaded mirror gives up and returns an
    # honest error sooner, so the client-side per-mirror budget below can move on to the
    # next mirror instead of the whole request stalling on one slow server.
    return f"""
[out:json][timeout:12];
(
  {body}
);
out center tags 60;
""".strip()


def _build_settlement_query(lat: float, lon: float, radius_m: int) -> str:
    """Real nearby towns/villages/hamlets (Tourist Flow Rebalancer candidate
    discovery -- spec: "find nearby alternatives"), NOT tourist POIs. Nodes
    only (settlements are essentially always mapped as a single point in
    OSM), so this is cheaper than the tourism-POI query above -- no `nwr`,
    no `out center`, just a direct node selector."""
    return f"""
[out:json][timeout:12];
node["place"~"^(town|village|hamlet)$"](around:{radius_m},{lat},{lon});
out tags 100;
""".strip()


def _build_district_query(lat: float, lon: float, radius_m: int) -> str:
    """Real nearby administrative districts (Tourist Flow Rebalancer's
    "Nearby Similar Districts" -- spec: "an administrative/geographic
    destination area that can absorb tourism demand", explicitly distinct
    from Settlement/nearby-places). India's own OSM administrative-boundary
    tagging is not perfectly consistent state-to-state (spec: "Do not assume
    every OSM region has perfectly consistent administrative tagging"), so
    this deliberately queries a RANGE of admin_levels (5-7 covers "division",
    "district" and, in some states, "district"-equivalent sub-divisions)
    rather than a single exact level, in one cheap consolidated query -- the
    same regex-alternation pattern _build_query uses for category tags.
    `out center tags` only (no full polygon geometry): a district relation's
    boundary can be huge, and the discovery step only ever needs a
    representative point + name, never the full shape (spec: "Do NOT load
    enormous administrative geometries unnecessarily")."""
    return f"""
[out:json][timeout:15];
relation["boundary"="administrative"]["admin_level"~"^(5|6|7)$"](around:{radius_m},{lat},{lon});
out center tags 40;
""".strip()


def _district_from_element(el: dict) -> District | None:
    tags = el.get("tags", {})
    name = tags.get("name")
    if not name:
        return None
    center = el.get("center", {})
    lat, lon = center.get("lat"), center.get("lon")
    if lat is None or lon is None:
        return None
    return District(
        id=f"{el['type']}/{el['id']}", name=name, admin_level=tags.get("admin_level"),
        latitude=lat, longitude=lon,
        state=tags.get("is_in:state") or tags.get("addr:state"),
    )


def _settlement_from_element(el: dict) -> Settlement | None:
    tags = el.get("tags", {})
    name = tags.get("name")
    place_type = tags.get("place")
    lat, lon = el.get("lat"), el.get("lon")
    if not name or not place_type or lat is None or lon is None:
        return None
    population = None
    if tags.get("population", "").strip().isdigit():
        population = int(tags["population"])
    return Settlement(
        id=f"{el['type']}/{el['id']}", name=name, place_type=place_type,
        latitude=lat, longitude=lon, population=population,
        state=tags.get("addr:state") or tags.get("is_in:state"),
    )


def _describe_exc(exc: Exception) -> str:
    """str(exc) is empty for some httpx exceptions (e.g. a bare ConnectError
    with no underlying OS message) -- always fall back to the exception's
    class name so a real, non-blank reason reaches the user. This is the fix
    for the "(  ;  ; )" malformed-error report: three genuinely-empty
    messages joined together used to look like nothing was wrong at all."""
    msg = str(exc).strip()
    return msg if msg else exc.__class__.__name__


def _short_host(url: str) -> str:
    try:
        return url.split("//", 1)[1].split("/", 1)[0]
    except IndexError:
        return url


def _place_from_element(el: dict) -> Place | None:
    tags = el.get("tags", {})
    name = tags.get("name")
    if not name:
        return None
    if el["type"] == "node":
        lat, lon = el.get("lat"), el.get("lon")
    else:
        center = el.get("center", {})
        lat, lon = center.get("lat"), center.get("lon")
    if lat is None or lon is None:
        return None

    category = _normalize_category(tags)
    address_parts = [
        tags.get("addr:housenumber"), tags.get("addr:street"),
        tags.get("addr:suburb"), tags.get("addr:city"), tags.get("addr:postcode"),
    ]
    address = ", ".join(p for p in address_parts if p) or None

    photos = []
    if tags.get("image"):
        photos.append(tags["image"])
    if tags.get("wikimedia_commons"):
        photos.append(f"https://commons.wikimedia.org/wiki/{tags['wikimedia_commons']}")

    place_id = f"{el['type']}/{el['id']}"
    return Place(
        id=place_id,
        external_id=str(el["id"]),
        source="overpass",
        source_url=f"https://www.openstreetmap.org/{el['type']}/{el['id']}",
        name=name,
        category=category,
        raw_tags=tags,
        latitude=lat,
        longitude=lon,
        address=address,
        rating=None,       # OSM does not carry traveller ratings -- left null, never invented
        review_count=None,
        photos=photos,
        opening_hours=tags.get("opening_hours"),
        website=tags.get("website") or tags.get("contact:website"),
        phone=tags.get("phone") or tags.get("contact:phone"),
        description=tags.get("description"),
    )


class OverpassProvider(PlacesProvider):
    def __init__(self):
        # Configured URL first (defaults to overpass-api.de), then the other public
        # mirrors, de-duplicated -- see OVERPASS_MIRRORS above.
        self.mirrors = list(dict.fromkeys([settings.overpass_base_url, *OVERPASS_MIRRORS]))
        # Identify ourselves like a real client, not a bare library default -- the public
        # OSM ecosystem (Overpass included) fair-use policy leans on this to tell apart
        # legitimate small apps from anonymous scraping traffic.
        self.headers = {"User-Agent": settings.nominatim_user_agent}

    async def _post(self, query: str, per_mirror_timeout: float, hedge_delay: float = 5.0) -> dict:
        # Mirrors are HEDGED, not tried one after another: the first mirror starts
        # immediately, and each next one only joins in if nothing has succeeded within
        # `hedge_delay` seconds -- so a healthy primary answers in normal time with only
        # one request ever sent (no extra load on the other mirrors), while a slow/dead
        # primary is covered by a second/third request running concurrently instead of
        # after it. This bounds the worst case at roughly
        # hedge_delay * (mirrors - 1) + per_mirror_timeout, NOT the sum of every mirror's
        # timeout -- trying mirrors strictly one-after-another (an earlier version of
        # this fix) could take 3x as long overall, which is what was actually causing the
        # frontend's own abort to fire before the backend ever got to answer.
        async def attempt(url: str):
            async with httpx.AsyncClient(timeout=per_mirror_timeout) as client:
                resp = await client.post(url, data={"data": query}, headers=self.headers)
                resp.raise_for_status()
                return resp.json()

        # NOTE on a real bug fixed here (2026-09-16): when two hedged mirrors landed in
        # the SAME `asyncio.wait` batch -- e.g. one succeeded while another failed with a
        # 429/timeout at nearly the same moment, which is exactly what happens under real
        # public-Overpass load -- the old code did `for task in done: return task.result()`
        # and returned on the FIRST task processed, leaving any other task in that same
        # batch (including a failed one) with its exception never called via `.result()`.
        # asyncio then logs that as "Task exception was never retrieved" plus a full
        # traceback dump straight to the console the moment the task is garbage-collected
        # -- harmless to the request (it already got its answer from the winning mirror),
        # but alarming to read and easy to mistake for the server crashing. Fix: always
        # call `.result()`/catch on EVERY task in a `done` batch before deciding what to
        # return, and explicitly await cancellation of anything left pending so its
        # exception (including a bare CancelledError) is retrieved too.
        def _harvest(done_tasks) -> object | None:
            winner = None
            for task in done_tasks:
                try:
                    result = task.result()
                except (httpx.HTTPError, ValueError) as exc:
                    errors[tasks[task]] = _describe_exc(exc)
                else:
                    if winner is None:
                        winner = result
            return winner

        tasks: dict[asyncio.Task, str] = {}
        errors: dict[str, str] = {}
        try:
            for i, url in enumerate(self.mirrors):
                tasks[asyncio.create_task(attempt(url))] = url
                is_last_mirror = i == len(self.mirrors) - 1
                done, pending = await asyncio.wait(
                    tasks.keys(),
                    timeout=None if is_last_mirror else hedge_delay,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                winner = _harvest(done)
                if winner is not None:
                    return winner
                # Nothing succeeded yet (and nothing failed outright either, or every
                # failure so far was recoverable) -- fall through and hedge in the next
                # mirror rather than waiting the full per_mirror_timeout on this one.

            # All mirrors are now in flight; wait out whichever finishes first.
            pending = {t for t in tasks if not t.done()}
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                winner = _harvest(done)
                if winner is not None:
                    return winner
        finally:
            still_pending = [t for t in tasks if not t.done()]
            for task in still_pending:
                task.cancel()
            if still_pending:
                # Actually wait for cancellation to land and collect whatever each task
                # raises (CancelledError or otherwise) instead of firing-and-forgetting --
                # this is the other half of the fix above.
                await asyncio.gather(*still_pending, return_exceptions=True)

        # Never surface a blank/malformed message like "( ; ; )" -- every mirror's
        # failure is guaranteed non-empty by _describe_exc, and a mirror that was never
        # actually tried (e.g. cancelled before it got a chance) is called out as such
        # rather than silently omitted.
        for url in self.mirrors:
            errors.setdefault(url, "not attempted")
        detail = "; ".join(f"{_short_host(url)}: {msg}" for url, msg in errors.items())
        raise ProviderError("overpass", detail or "all mirrors failed with no further detail")

    async def nearby(self, latitude: float, longitude: float, radius_meters: int, categories: list[str]) -> list[Place]:
        query = _build_query(latitude, longitude, radius_meters, categories)
        # Each mirror gets up to ~15s (a couple seconds more than the query's own
        # [timeout:12], so we get back Overpass's own honest timeout error rather than an
        # abrupt client abort) -- but mirrors are hedged concurrently with a 4s stagger
        # (see _post), so with 4 mirrors the real worst case is ~4s*3 + 15s = 27s, not
        # 4x15s. Matched with headroom on the frontend side (see js/api.js placesNearby
        # timeoutMs=35000) so the browser doesn't give up before the backend has had its
        # full real chance.
        data = await self._post(query, per_mirror_timeout=15.0, hedge_delay=4.0)

        seen_ids = set()
        places: list[Place] = []
        for el in data.get("elements", []):
            place = _place_from_element(el)
            if place is None or place.id in seen_ids:
                continue
            seen_ids.add(place.id)
            places.append(place)
        return places

    async def nearby_settlements(self, latitude: float, longitude: float, radius_meters: int) -> list[Settlement]:
        """Real nearby towns/villages (Tourist Flow Rebalancer candidate
        discovery). Shares the same hedged multi-mirror `_post` as `nearby()`
        -- no separate retry/fallback logic to maintain."""
        query = _build_settlement_query(latitude, longitude, radius_meters)
        data = await self._post(query, per_mirror_timeout=15.0, hedge_delay=4.0)

        seen_ids, settlements = set(), []
        for el in data.get("elements", []):
            s = _settlement_from_element(el)
            if s is None or s.id in seen_ids:
                continue
            seen_ids.add(s.id)
            settlements.append(s)
        return settlements

    async def nearby_districts(self, latitude: float, longitude: float, radius_meters: int) -> list[District]:
        """Real nearby administrative districts (Tourist Flow Rebalancer
        candidate discovery for "Nearby Similar Districts"). Shares the same
        hedged multi-mirror `_post` as `nearby()`/`nearby_settlements()`."""
        query = _build_district_query(latitude, longitude, radius_meters)
        data = await self._post(query, per_mirror_timeout=15.0, hedge_delay=4.0)

        seen_ids, districts = set(), []
        for el in data.get("elements", []):
            d = _district_from_element(el)
            if d is None or d.id in seen_ids:
                continue
            seen_ids.add(d.id)
            districts.append(d)
        return districts

    async def get_details(self, place_id: str) -> PlaceDetails | None:
        try:
            osm_type, osm_id = place_id.split("/", 1)
        except ValueError:
            return None
        if osm_type not in ("node", "way", "relation"):
            return None

        query = f"""
[out:json][timeout:10];
{osm_type}({osm_id});
out center tags 1;
""".strip()
        data = await self._post(query, per_mirror_timeout=13.0, hedge_delay=4.0)

        elements = data.get("elements", [])
        if not elements:
            return None
        el = elements[0]
        el.setdefault("type", osm_type)
        el.setdefault("id", int(osm_id))
        place = _place_from_element(el)
        if place is None:
            return None
        return PlaceDetails(**place.model_dump(), open_now=None)
