"""
Tourist Flow Rebalancer (SIH PS26204 core differentiator).

Sarthi's existing Tourism Pressure Index (app/services/crowd_service.py)
already tells a traveller HOW crowded a destination estimatedly is. This
service is the natural next step it was always missing: when a requested
destination is under real pressure, find genuine nearby alternatives, score
them on the same real signals Sarthi already collects (tourism pressure,
weather, real distance, real nearby-place density), and rank them
explainably -- so demand can be *voluntarily* redistributed toward
lower-pressure places, without ever silently overriding what the traveller
actually asked for.

Deliberately reuses, rather than reimplements:
  - crowd_service.get_pressure           -- the ONE Tourism Pressure Index
  - places_service.nearby_places         -- real OSM tourism-POI density (also IS the
                                             candidate-category profile and local-opportunity signal)
  - places_service.nearby_settlements    -- real OSM towns/villages (candidate discovery)
  - geocoding_service.geocode_search     -- Nominatim, for the requested destination
                                             and for geocoding curated hidden-gem names
  - weather_service.get_weather          -- Open-Meteo outdoor suitability
  - routing_service.compute_route        -- OSRM, for the FINAL shortlist only (never
                                             called per-candidate -- see _enrich_travel_time)
  - recommendation_service.INTEREST_TO_CATEGORIES -- the SAME interest-tag vocabulary
                                             already used by the in-destination SmartScore engine
  - app.data.curated_destinations        -- the SAME 16 curated destinations/hidden gems
                                             already shown elsewhere in the app (see that
                                             module's docstring for why it's a mirror, not a
                                             second dataset)
  - app.integrations.carrying_capacity   -- the new, explicitly "modelled, not official" abstraction

This is deterministic weighted scoring, NOT machine learning (spec:
"Do not label the scoring system as AI/ML"), and every score is explainable
via the returned `factors` breakdown -- same transparency contract as
recommendation_service.score_places.
"""
import asyncio
import logging
import math

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.data.curated_destinations import CURATED_DESTINATIONS
from app.integrations.base import ProviderError
from app.integrations.carrying_capacity import EstimatedCarryingCapacityProvider
from app.schemas.crowd import CrowdPressureResponse
from app.schemas.flow_rebalance import (
    CarryingCapacityInfo,
    DestinationSummary,
    LocalOpportunitySignal,
    RebalanceAlternative,
    RebalanceRequest,
    RebalanceResponse,
    ScoreFactor,
)
from app.schemas.route import RouteStop
from app.services import crowd_service, geocoding_service, places_service, routing_service, weather_service
from app.services.recommendation_service import INTEREST_TO_CATEGORIES

settings = get_settings()
_capacity_provider = EstimatedCarryingCapacityProvider()

# Dev-only diagnostics for the candidate-discovery/scoring pipeline (spec:
# "add dev-only diagnostic logging... never exposed to users"). These are
# plain DEBUG-level log records -- nothing here is returned in any API
# response, and the default logging config only surfaces INFO+ in
# production, so this is inert unless a developer explicitly turns DEBUG
# logging on for this logger while investigating a "no alternatives" report.
logger = logging.getLogger(__name__)

_STATUS_RANK = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "VERY HIGH": 3}
# A candidate must beat the requested destination's numeric pressure index by
# at least this many points to count as "genuinely lower" (spec example:
# requested HIGH 74 vs candidate HIGH 58 -- a 16-point relief -- must be
# treated as eligible even though both share the same status bucket; this
# margin just guards against a trivial 1-2 point difference, which is noise
# rather than a meaningful relief, being treated as a real improvement).
_MIN_PRESSURE_RELIEF_INDEX = 5

# Only compute the (Overpass/weather/OSRM-backed) candidate search at all when
# pressure is at least MODERATE -- a LOW-pressure destination gets a normal
# experience with zero extra provider calls (spec: "LOW: Normal destination
# experience" + performance: "do not hammer Overpass/other public APIs").
_MIN_STATUS_TO_SEARCH = "MODERATE"
# HIGH/VERY HIGH "strongly surface" alternatives; MODERATE computes them too
# but the frontend treats rebalancing_triggered=False there as "available, not pushed".
_MIN_STATUS_TO_TRIGGER = "HIGH"

_SETTLEMENT_RADIUS_M = 70_000  # ~70km: "nearby, plausibly day-trip/relocatable" for road-based Indian tourism
# Adaptive radius (spec: "adaptive search radius by geographic context"): a
# genuinely remote requested destination (sparse OSM settlement data, e.g.
# deep in a national park or a sparsely-mapped rural area) can come back with
# almost no OSM settlements at 70km even though real towns exist further out
# -- widen once, capped, rather than either always querying a huge radius or
# permanently giving up on a sparse area.
_SETTLEMENT_SPARSE_MIN = 3
_SETTLEMENT_RADIUS_FALLBACK_M = 150_000
_CURATED_MAX_DISTANCE_KM = 250.0  # curated hidden gems are sparse (16 total) -- allow a wider net than raw OSM settlements
_MIN_DISTANCE_FROM_REQUESTED_KM = 8.0  # anything closer is essentially "the same place"
_MAX_CANDIDATES_SCORED = 8  # bounds total live provider calls per rebalance request
_LOCAL_OPPORTUNITY_CATEGORIES = {"restaurant", "cafe", "shopping", "hotel"}
_DENSITY_RADIUS_M = 4000  # matches crowd_service._DENSITY_RADIUS_M exactly, so this shares its Overpass/cache call

# "Nearby Similar Districts" (distinct from the settlement/curated
# `alternatives` above -- see module docstring and DestinationSummary.source):
# an administrative district is a much coarser area than a single settlement,
# so it needs its own, wider search radius and its own minimum
# distance-from-requested (a neighbouring district's centroid can easily be
# 20-30km away even though the districts are adjacent).
_DISTRICT_RADIUS_M = 120_000
_DISTRICT_SPARSE_MIN = 2  # fewer than this at the normal radius counts as sparse -- mirrors _SETTLEMENT_SPARSE_MIN
_DISTRICT_RADIUS_FALLBACK_M = 220_000
_MIN_DISTRICT_DISTANCE_KM = 15.0
_MAX_DISTRICT_DISTANCE_KM = 300.0  # geographic plausibility cap -- "nearby", not "the other side of India"
# Staged pipeline (spec: "Do not calculate detailed crowding for 50+
# districts... enrich only the best candidates"): discover cheaply, keep only
# the closest few by straight-line distance, and score (crowd_service +
# places_service + weather -- the expensive part) only those.
_MAX_DISTRICT_CANDIDATES_SCORED = 6


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlambda = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _category_profile(places: list) -> dict[str, float]:
    """Normalized (sums to 1.0) category distribution -- the real-data
    fingerprint of "what kind of place is this", used for experience-match
    without needing any curated tags at all."""
    if not places:
        return {}
    counts: dict[str, int] = {}
    for p in places:
        counts[p.category] = counts.get(p.category, 0) + 1
    total = sum(counts.values())
    return {cat: n / total for cat, n in counts.items()}


def _profile_similarity(profile_a: dict[str, float], profile_b: dict[str, float]) -> float:
    """Histogram intersection (0-1 -> 0-100): sum of the smaller share per
    category. 100 = identical category mix, 0 = no overlap at all."""
    if not profile_a or not profile_b:
        return 50.0  # neither profile is known well enough to compare -- neutral, not zero
    keys = set(profile_a) | set(profile_b)
    overlap = sum(min(profile_a.get(k, 0.0), profile_b.get(k, 0.0)) for k in keys)
    return round(overlap * 100, 1)


def _interest_alignment(profile: dict[str, float], interests: list[str]) -> float:
    if not interests:
        return 0.0  # signals "not applicable"; caller reweights to 0 in that case
    wanted: set[str] = set()
    for interest in interests:
        wanted.update(INTEREST_TO_CATEGORIES.get(interest.lower(), []))
    if not wanted or not profile:
        return 50.0
    covered = sum(share for cat, share in profile.items() if cat in wanted)
    return round(min(1.0, covered * 1.6) * 100, 1)  # *1.6: a place needn't be 100% wanted-category to feel aligned


def _local_opportunity(places: list) -> LocalOpportunitySignal:
    count = sum(1 for p in places if p.category in _LOCAL_OPPORTUNITY_CATEGORIES)
    if count == 0:
        return LocalOpportunitySignal(score=20.0, label="No confirmed local business signals nearby yet in OpenStreetMap", business_count=0)
    if count <= 4:
        return LocalOpportunitySignal(score=55.0, label="Some local experience availability nearby (restaurants/stays/shops on OpenStreetMap)", business_count=count)
    if count <= 14:
        return LocalOpportunitySignal(score=80.0, label="Strong local experience availability -- supports local tourism activity", business_count=count)
    return LocalOpportunitySignal(score=95.0, label="Well-established local tourism economy nearby", business_count=count)


def _distance_score(km: float) -> float:
    if km <= 15:
        return 95.0
    if km <= 40:
        return 85.0
    if km <= 80:
        return 70.0
    if km <= 150:
        return 50.0
    return 30.0


_WEATHER_SCORE = {"good": 90.0, "fair": 60.0, "poor": 25.0}


def _pressure_index_or_none(cp: CrowdPressureResponse) -> int | None:
    return cp.pressure_index


def _pressure_relief(requested: CrowdPressureResponse, candidate: CrowdPressureResponse) -> tuple[float, str]:
    req_idx = requested.pressure_index if requested.pressure_index is not None else 60
    cand_idx = candidate.pressure_index if candidate.pressure_index is not None else 50
    relief = req_idx - cand_idx
    score = max(0.0, min(100.0, 50 + relief))
    if candidate.pressure_index is None:
        note = "Candidate's live pressure signal is unavailable right now -- relief estimated conservatively"
    else:
        note = f"Estimated pressure {candidate.status or 'n/a'} ({candidate.pressure_index}/100) vs requested destination's {requested.status or 'n/a'} ({requested.pressure_index if requested.pressure_index is not None else 'n/a'}/100)"
    return score, note


async def _resolve_requested_destination(db: Session, req: RebalanceRequest) -> DestinationSummary | None:
    if req.latitude is not None and req.longitude is not None:
        # No forward-search GeocodeResult to read district/state off of --
        # reverse-geocode once (cached) so "Nearby Similar Districts" can
        # still exclude the destination's own district. A failure here is
        # not fatal to resolving the destination itself (best-effort only).
        district = state = None
        try:
            reverse = await geocoding_service.reverse_geocode(db, req.latitude, req.longitude)
        except ProviderError:
            reverse = None
        if reverse is not None:
            district, state = reverse.district, reverse.state
        return DestinationSummary(
            name=req.destination_query or "Selected location", latitude=req.latitude, longitude=req.longitude,
            state=state, district=district, source="geocoded",
        )
    if not req.destination_query.strip():
        return None
    results = await geocoding_service.geocode_search(db, req.destination_query, limit=1)
    if not results:
        return None
    g = results[0]
    return DestinationSummary(
        name=g.display_name, latitude=g.latitude, longitude=g.longitude,
        state=g.state, district=g.district, source="geocoded",
    )


def _plausibly_nearby_state(seed: dict, requested_label: str) -> bool:
    """Cheap pre-filter before spending Nominatim's throttled ~1req/s budget:
    a curated destination whose STATE doesn't appear anywhere in the
    requested destination's own geocoded label is extremely unlikely to be
    within _CURATED_MAX_DISTANCE_KM in a country the size of India. Coarse
    (state names occasionally differ in exact wording) but bounds the worst
    case to a handful of geocode calls instead of always doing all 16 --
    documented trade-off, not a silent omission (see final delivery notes)."""
    return seed["state"].lower() in requested_label.lower()


async def _geocode_curated_candidates(db: Session, requested_label: str) -> list[dict]:
    """Geocode curated destinations (Nominatim, cached 24h -- see
    config.cache_ttl_geocode) so they have real coordinates to be considered
    as candidates. Pre-filtered by state where possible to avoid needlessly
    walking Nominatim's throttled ~1req/s budget through all 16 curated
    entries on every cold-cache request; falls back to checking all 16 only
    when the coarse state filter matches nothing (never silently returns zero
    curated candidates because of a wording mismatch)."""
    candidates = [s for s in CURATED_DESTINATIONS if _plausibly_nearby_state(s, requested_label)]
    if not candidates:
        candidates = CURATED_DESTINATIONS
    out = []
    for seed in candidates:
        try:
            results = await geocoding_service.geocode_search(db, f"{seed['name']}, {seed['state']}, India", limit=1)
        except ProviderError:
            logger.debug("rejected-because-geocoding-failed: curated candidate %r could not be geocoded", seed["name"])
            continue
        if not results:
            logger.debug("rejected-because-geocoding-failed: curated candidate %r returned no geocode results", seed["name"])
            continue
        g = results[0]
        out.append({
            "name": seed["name"], "latitude": g.latitude, "longitude": g.longitude, "state": seed["state"],
            "source": "curated-hidden-gem" if seed["hidden_gem"] else "curated-destination",
            "tags": seed["tags"], "hidden_gem": seed["hidden_gem"], "sustainability": seed["sustainability"],
        })
    return out


async def _discover_candidates(db: Session, lat: float, lon: float, requested_label: str) -> list[dict]:
    candidates: list[dict] = []

    try:
        settlements = await places_service.nearby_settlements(db, lat, lon, _SETTLEMENT_RADIUS_M)
    except ProviderError:
        settlements = []
    if len(settlements) < _SETTLEMENT_SPARSE_MIN:
        # Sparse at the normal radius -- this destination itself may be
        # remote/rural rather than the data being wrong, so widen once
        # before falling back to curated destinations alone.
        logger.debug(
            "settlement discovery near (%s, %s) sparse at %sm (%d found) -- widening to %sm",
            lat, lon, _SETTLEMENT_RADIUS_M, len(settlements), _SETTLEMENT_RADIUS_FALLBACK_M,
        )
        try:
            wider = await places_service.nearby_settlements(db, lat, lon, _SETTLEMENT_RADIUS_FALLBACK_M)
        except ProviderError:
            wider = []
        # Merge rather than replace: the wider Overpass query can (depending
        # on provider paging/limits) occasionally miss something the tighter
        # one found, so keep the union rather than assuming strictly a superset.
        seen_ids = {(round(s.latitude, 4), round(s.longitude, 4)) for s in settlements}
        for s in wider:
            key = (round(s.latitude, 4), round(s.longitude, 4))
            if key not in seen_ids:
                seen_ids.add(key)
                settlements.append(s)
    logger.debug("candidate-discovered: %d OSM settlements near (%s, %s)", len(settlements), lat, lon)
    for s in settlements:
        candidates.append({
            "name": s.name, "latitude": s.latitude, "longitude": s.longitude, "state": s.state,
            "source": "osm-settlement", "tags": [], "hidden_gem": False, "sustainability": None,
        })

    curated = await _geocode_curated_candidates(db, requested_label)
    for c in curated:
        dist = _haversine_km(lat, lon, c["latitude"], c["longitude"])
        if dist <= _CURATED_MAX_DISTANCE_KM:
            candidates.append(c)

    # Dedupe: drop anything essentially co-located with the requested
    # destination itself, and collapse near-duplicate candidates (an OSM
    # settlement node and a curated entry that resolve to ~the same spot),
    # preferring the curated entry since it carries known tags/sustainability.
    deduped: list[dict] = []
    for c in sorted(candidates, key=lambda c: 0 if c["source"].startswith("curated") else 1):
        d_from_requested = _haversine_km(lat, lon, c["latitude"], c["longitude"])
        if d_from_requested < _MIN_DISTANCE_FROM_REQUESTED_KM:
            logger.debug("rejected-by-distance: %r is only %.1fkm from the requested destination (too close)", c["name"], d_from_requested)
            continue
        if any(_haversine_km(c["latitude"], c["longitude"], other["latitude"], other["longitude"]) < 3.0 for other in deduped):
            logger.debug("rejected-other: %r deduped as a near-duplicate of an already-kept candidate", c["name"])
            continue
        c["_distance_km"] = d_from_requested
        deduped.append(c)

    deduped.sort(key=lambda c: c["_distance_km"])
    logger.debug("candidate-discovered: %d candidates survived distance/dedup filtering near (%s, %s)", len(deduped), lat, lon)
    return deduped[: _MAX_CANDIDATES_SCORED * 2]  # a little slack before the pressure/weather filter below


def _normalize_district_name(name: str | None) -> str:
    return (name or "").strip().lower()


async def _discover_district_candidates(
    db: Session, lat: float, lon: float, current_district: str | None,
) -> list[dict]:
    """"Nearby Similar Districts" candidate discovery (spec Part 2) --
    genuinely distinct from _discover_candidates above: that finds individual
    settlements/curated destinations, this finds coarser OSM administrative
    districts (see OverpassProvider.nearby_districts / District schema).
    Nothing here is a manually maintained destination->district lookup; every
    candidate comes from a live (cached) Overpass query around the requested
    destination's own coordinates, so it works the same way for any Indian
    destination.

    Staged for performance (spec: "Do not calculate detailed crowding for
    50+ districts"): this function only discovers and cheaply filters by
    distance -- the expensive part (crowd_service.get_pressure,
    places_service.nearby_places, weather) happens later, in
    _score_candidate, and ONLY for the top _MAX_DISTRICT_CANDIDATES_SCORED
    candidates this returns."""
    try:
        districts = await places_service.nearby_districts(db, lat, lon, _DISTRICT_RADIUS_M)
    except ProviderError:
        districts = []
    if len(districts) < _DISTRICT_SPARSE_MIN:
        logger.debug(
            "district discovery near (%s, %s) sparse at %sm (%d found) -- widening to %sm",
            lat, lon, _DISTRICT_RADIUS_M, len(districts), _DISTRICT_RADIUS_FALLBACK_M,
        )
        try:
            wider = await places_service.nearby_districts(db, lat, lon, _DISTRICT_RADIUS_FALLBACK_M)
        except ProviderError:
            wider = []
        seen_ids = {d.id for d in districts}
        for d in wider:
            if d.id not in seen_ids:
                seen_ids.add(d.id)
                districts.append(d)
    logger.debug("candidate-discovered: %d OSM administrative districts near (%s, %s)", len(districts), lat, lon)

    current_norm = _normalize_district_name(current_district)
    deduped: list[dict] = []
    seen_names: set[str] = set()
    for d in districts:
        name_norm = _normalize_district_name(d.name)
        if current_norm and (name_norm == current_norm or current_norm in name_norm or name_norm in current_norm):
            logger.debug("rejected-other: district %r matches the requested destination's own district %r", d.name, current_district)
            continue
        if name_norm in seen_names:
            continue  # the same district can legitimately show up more than once (multiple admin_level tags on nearby relations)
        d_from_requested = _haversine_km(lat, lon, d.latitude, d.longitude)
        if d_from_requested < _MIN_DISTRICT_DISTANCE_KM:
            logger.debug("rejected-by-distance: district %r is only %.1fkm from the requested destination (too close)", d.name, d_from_requested)
            continue
        if d_from_requested > _MAX_DISTRICT_DISTANCE_KM:
            logger.debug("rejected-by-distance: district %r is %.1fkm away -- not geographically plausible as 'nearby'", d.name, d_from_requested)
            continue
        seen_names.add(name_norm)
        deduped.append({
            "name": d.name, "latitude": d.latitude, "longitude": d.longitude, "state": d.state,
            "district": d.name, "source": "osm-district", "tags": [], "hidden_gem": False, "sustainability": None,
            "_distance_km": d_from_requested,
        })

    deduped.sort(key=lambda c: c["_distance_km"])
    logger.debug("candidate-discovered: %d district candidates survived filtering near (%s, %s)", len(deduped), lat, lon)
    # Cheap filter stage is done -- only the closest few go on to the
    # expensive scoring stage (crowd/places/weather calls).
    return deduped[:_MAX_DISTRICT_CANDIDATES_SCORED]


async def _score_candidate(db: Session, requested_profile: dict, requested_pressure: CrowdPressureResponse, interests: list[str], candidate: dict) -> RebalanceAlternative | None:
    lat, lon = candidate["latitude"], candidate["longitude"]
    label = candidate["name"] + (f", {candidate['state']}" if candidate.get("state") else "")

    pressure = await crowd_service.get_pressure(db, label, lat, lon)

    # Filter: only offer alternatives that are genuinely lower-pressure than
    # requested (spec: "filter unsuitable destinations"). A candidate with no
    # live pressure signal at all isn't automatically excluded -- data
    # honesty cuts both ways, an unknown isn't a "worse".
    #
    # Real, reproduced bug: the old check compared STATUS BUCKETS only
    # (LOW/MODERATE/HIGH/VERY HIGH), so a requested destination at HIGH-74
    # and a candidate at HIGH-58 -- a genuine 16-point relief -- were wrongly
    # treated as "not lower" purely because they share a bucket. The actual
    # numeric pressure_index is the ground truth when both sides have one;
    # status-bucket rank is used only as a fallback when a numeric index
    # isn't available for one or both sides.
    req_idx = requested_pressure.pressure_index
    cand_idx = pressure.pressure_index
    if req_idx is not None and cand_idx is not None:
        if cand_idx > req_idx - _MIN_PRESSURE_RELIEF_INDEX:
            logger.debug(
                "rejected-because-pressure-not-lower: %r index %s vs requested index %s (needs >= %s relief)",
                candidate["name"], cand_idx, req_idx, _MIN_PRESSURE_RELIEF_INDEX,
            )
            return None
    elif requested_pressure.status and pressure.status:
        if _STATUS_RANK.get(pressure.status, 3) >= _STATUS_RANK.get(requested_pressure.status, 0):
            logger.debug(
                "rejected-because-pressure-not-lower: %r status %s vs requested status %s [no numeric index available, used status fallback]",
                candidate["name"], pressure.status, requested_pressure.status,
            )
            return None
    # else: no comparable pressure signal at all for one or both sides --
    # don't exclude on unknown data (spec: "never reject a candidate solely
    # because pressure is unavailable").

    try:
        candidate_places = await places_service.nearby_places(db, lat, lon, _DENSITY_RADIUS_M, [])
    except ProviderError:
        candidate_places = []
    candidate_profile = _category_profile(candidate_places)

    try:
        weather = await weather_service.get_weather(db, lat, lon)
        weather_label = weather.outdoor_suitability
    except ProviderError:
        weather_label = None
    # Weather filter: don't suggest a poor-weather alternative to escape a
    # destination whose own weather is fine.
    if weather_label == "poor" and requested_pressure.weather_suitability not in (None, "POOR"):
        logger.debug("rejected-because-weather-poor: %r has poor weather while requested destination does not", candidate["name"])
        return None

    similarity = _profile_similarity(requested_profile, candidate_profile)
    interest_score = _interest_alignment(candidate_profile, interests)
    experience_match = round(similarity if not interests else (0.6 * similarity + 0.4 * interest_score))

    distance_km = candidate.get("_distance_km", 0.0)
    distance_score = _distance_score(distance_km)

    relief_score, relief_note = _pressure_relief(requested_pressure, pressure)

    local_opp = _local_opportunity(candidate_places)

    if candidate.get("sustainability") is not None:
        sustainability_score, sustainability_type = float(candidate["sustainability"]), "curated"
    else:
        # No curated figure -- model a proxy from place density (lower tourism
        # density read as lower current footprint), clearly labelled estimated.
        density_penalty = min(60.0, len(candidate_places) * 1.5)
        sustainability_score, sustainability_type = max(20.0, 90.0 - density_penalty), "estimated"

    capacity_score, capacity_label, capacity_type = _capacity_provider.estimate(len(candidate_places))

    weather_score = _WEATHER_SCORE.get(weather_label, 50.0)

    factors = {
        "experience_match": ScoreFactor(value=experience_match, weight=0.28, data_type="estimated", note="Real-OSM category-mix similarity" + (" + your selected interests" if interests else "")),
        "pressure_relief": ScoreFactor(value=relief_score, weight=0.24, data_type=pressure.data_type, note=relief_note),
        "distance_accessibility": ScoreFactor(value=distance_score, weight=0.16, data_type="estimated", note=f"~{round(distance_km)} km from the requested destination"),
        "weather_suitability": ScoreFactor(value=weather_score, weight=0.10, data_type="estimated" if weather_label else "unavailable", note=f"Outdoor suitability: {weather_label or 'unavailable'}"),
        "sustainability": ScoreFactor(value=sustainability_score, weight=0.08, data_type=sustainability_type, note="Curated sustainability score" if sustainability_type == "curated" else "Modelled from tourism-place density"),
        "local_opportunity": ScoreFactor(value=local_opp.score, weight=0.08, data_type="estimated", note=local_opp.label),
        "carrying_capacity": ScoreFactor(value=capacity_score, weight=0.06, data_type="estimated", note=capacity_label),
    }
    rebalancing_score = round(sum((f.value or 0) * f.weight for f in factors.values()))
    rebalancing_score = max(0, min(100, rebalancing_score))

    reasons = []
    if similarity >= 65:
        reasons.append("✓ Similar real place-mix to the destination you searched")
    if interests and interest_score >= 65:
        reasons.append("✓ Matches your selected interests")
    if relief_score >= 65:
        reasons.append(f"✓ Lower estimated tourism pressure ({pressure.status or 'n/a'} vs {requested_pressure.status or 'n/a'})")
    if weather_score >= 70:
        reasons.append("✓ Good weather suitability right now")
    if distance_score >= 70:
        reasons.append(f"✓ Reasonably accessible (~{round(distance_km)} km away)")
    if local_opp.score >= 65:
        reasons.append(f"✓ {local_opp.label}")
    if sustainability_score >= 70:
        reasons.append("✓ Higher estimated sustainability" if sustainability_type == "estimated" else "✓ Higher curated sustainability score")
    if not reasons:
        reasons.append("Matches your general search area with lower estimated pressure")

    return RebalanceAlternative(
        destination=DestinationSummary(
            name=candidate["name"], latitude=lat, longitude=lon,
            state=candidate.get("state"), district=candidate.get("district"), source=candidate["source"],
        ),
        experience_match=int(experience_match),
        rebalancing_score=int(rebalancing_score),
        tourism_pressure=pressure,
        distance_km=round(distance_km, 1),
        travel_time_minutes=None,
        distance_source="straight-line-estimate",
        local_opportunity=local_opp,
        carrying_capacity=CarryingCapacityInfo(score=capacity_score, label=capacity_label, data_type=capacity_type),
        sustainability_score=sustainability_score,
        sustainability_data_type=sustainability_type,
        is_hidden_gem=bool(candidate.get("hidden_gem")),
        factors=factors,
        reasons=reasons,
    )


async def _enrich_travel_time(db: Session, requested: DestinationSummary, alternatives: list[RebalanceAlternative]) -> None:
    """Real OSRM route -- ONLY for the final shortlist actually being
    returned (never per-candidate during scoring), per the explicit
    performance requirement not to hammer public routing infrastructure."""
    for alt in alternatives:
        try:
            route = await routing_service.compute_route(
                db,
                [RouteStop(name=requested.name, latitude=requested.latitude, longitude=requested.longitude),
                 RouteStop(name=alt.destination.name, latitude=alt.destination.latitude, longitude=alt.destination.longitude)],
                "driving",
            )
        except ProviderError:
            continue  # keep the haversine estimate already set -- an honest fallback, not a failure
        alt.travel_time_minutes = round(route.total_duration_seconds / 60)
        alt.distance_km = round(route.total_distance_meters / 1000, 1)
        alt.distance_source = "osrm"


async def rebalance(db: Session, req: RebalanceRequest) -> RebalanceResponse:
    try:
        requested = await _resolve_requested_destination(db, req)
    except ProviderError as exc:
        return RebalanceResponse(message=f"Destination search is temporarily unavailable ({exc.detail}). Try again in a moment.")
    if requested is None:
        return RebalanceResponse(message=f"Couldn't find \"{req.destination_query}\" -- try a different spelling or a nearby larger town.")

    requested_pressure = await crowd_service.get_pressure(db, requested.name, requested.latitude, requested.longitude)

    status_rank = _STATUS_RANK.get(requested_pressure.status, -1)
    if status_rank < _STATUS_RANK[_MIN_STATUS_TO_SEARCH]:
        # LOW (or unavailable) pressure: normal destination experience, no
        # candidate search at all -- zero extra Overpass/weather/OSRM calls.
        return RebalanceResponse(
            requested_destination=requested, tourism_pressure=requested_pressure,
            rebalancing_triggered=False, pressure_check_only=True,
            message="Estimated tourism pressure is not elevated here -- no rebalancing needed.",
        )

    try:
        requested_places = await places_service.nearby_places(db, requested.latitude, requested.longitude, _DENSITY_RADIUS_M, [])
    except ProviderError:
        requested_places = []
    requested_profile = _category_profile(requested_places)

    # Two independent candidate pipelines, sharing the requested destination's
    # already-fetched places/profile/pressure above -- neither gates the
    # other, so a genuinely empty settlement search (spec: "Crowding Index
    # should always appear... this is better than hiding information because
    # alternatives failed") never silently suppresses district discovery, or
    # vice versa.
    #
    # Run them CONCURRENTLY (asyncio.gather), not one after another: each
    # pipeline already does its own internal fan-out (curated-candidate
    # geocoding, throttled ~1 req/s against Nominatim, plus per-candidate
    # crowd/places/weather scoring), so awaiting them sequentially made a
    # single /api/flow/rebalance call take roughly the SUM of both
    # pipelines' wall-clock time -- easily exceeding the frontend's request
    # timeout once district discovery was added on top of the pre-existing
    # settlement pipeline (real, reported bug: "Nearby Alternatives ...
    # Request timed out"). Running them side by side brings total latency
    # back down to roughly the SLOWER of the two, with no change to what
    # either pipeline actually returns.
    (shortlist, message), (district_shortlist, district_message) = await asyncio.gather(
        _rebalance_settlement_alternatives(db, req, requested, requested_profile, requested_pressure),
        _rebalance_district_alternatives(db, req, requested, requested_profile, requested_pressure),
    )

    # Same reasoning for the final-shortlist OSRM enrichment -- these two
    # calls never depended on each other.
    await asyncio.gather(
        _enrich_travel_time(db, requested, shortlist),
        _enrich_travel_time(db, requested, district_shortlist),
    )

    triggered = status_rank >= _STATUS_RANK[_MIN_STATUS_TO_TRIGGER] and bool(shortlist or district_shortlist)

    return RebalanceResponse(
        requested_destination=requested, tourism_pressure=requested_pressure,
        rebalancing_triggered=triggered, alternatives=shortlist, message=message,
        district_alternatives=district_shortlist, district_alternatives_message=district_message,
    )


async def _rebalance_settlement_alternatives(
    db: Session, req: RebalanceRequest, requested: DestinationSummary, requested_profile: dict, requested_pressure: CrowdPressureResponse,
) -> tuple[list[RebalanceAlternative], str]:
    """Settlement/curated-destination alternatives -- the original
    `alternatives` pipeline, unchanged in behavior, just factored out of
    `rebalance()` so it can run alongside (not gating, not gated by) the
    district pipeline below."""
    raw_candidates = await _discover_candidates(db, requested.latitude, requested.longitude, requested.name)
    if not raw_candidates:
        # Genuinely nothing to evaluate at all (no OSM settlements even after
        # the adaptive radius widen, and no curated destination within
        # range) -- distinct from the "candidates existed but none passed
        # the pressure/weather filter" case below (spec: distinguish
        # "confirmed none" from "could not be confirmed from the available data").
        return [], "Lower-pressure alternatives could not be confirmed from the available data for this location right now."

    scored = await asyncio.gather(
        *[_score_candidate(db, requested_profile, requested_pressure, req.interests, c) for c in raw_candidates],
        return_exceptions=True,
    )
    for c, s in zip(raw_candidates, scored):
        if isinstance(s, Exception):
            logger.debug("rejected-other: scoring %r raised %r", c["name"], s)
    alternatives = [a for a in scored if isinstance(a, RebalanceAlternative)]
    alternatives.sort(key=lambda a: a.rebalancing_score, reverse=True)
    shortlist = alternatives[: req.max_alternatives]

    if not shortlist:
        message = "Tourism pressure here is elevated, but no lower-pressure alternative could be confirmed nearby right now."
    elif _STATUS_RANK.get(requested_pressure.status, -1) >= _STATUS_RANK[_MIN_STATUS_TO_TRIGGER]:
        message = f"Estimated tourism pressure at {requested.name.split(',')[0]} is {requested_pressure.status} -- here are lower-pressure alternatives that may offer a similar experience."
    else:
        message = f"Estimated tourism pressure is {requested_pressure.status}. A few nearby alternatives are available if you'd like to explore."
    return shortlist, message


async def _rebalance_district_alternatives(
    db: Session, req: RebalanceRequest, requested: DestinationSummary, requested_profile: dict, requested_pressure: CrowdPressureResponse,
) -> tuple[list[RebalanceAlternative], str]:
    """"Nearby Similar Districts" -- an administrative-boundary-level
    alternative to the settlement/curated pipeline above, reusing the exact
    same _score_candidate scoring (only the candidate discovery differs)."""
    raw_districts = await _discover_district_candidates(db, requested.latitude, requested.longitude, requested.district)
    if not raw_districts:
        return [], "Lower-crowding district alternatives could not be confirmed from the available data for this location right now."

    scored = await asyncio.gather(
        *[_score_candidate(db, requested_profile, requested_pressure, req.interests, c) for c in raw_districts],
        return_exceptions=True,
    )
    for c, s in zip(raw_districts, scored):
        if isinstance(s, Exception):
            logger.debug("rejected-other: district scoring %r raised %r", c["name"], s)
    alternatives = [a for a in scored if isinstance(a, RebalanceAlternative)]
    alternatives.sort(key=lambda a: a.rebalancing_score, reverse=True)
    # "Prefer approximately 3-5 strong candidates" (spec) -- never padded out
    # to hit a target count when fewer genuinely qualify.
    shortlist = alternatives[: min(req.max_alternatives, 5)]

    if not shortlist:
        message = "Tourism pressure here is elevated, but no lower-crowding district alternative could be confirmed nearby right now."
    else:
        district_label = requested.district or requested.name.split(",")[0]
        message = f"Nearby districts with estimated lower tourism pressure than {district_label}."
    return shortlist, message
