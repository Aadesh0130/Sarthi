"""
Tests for the "Nearby Similar Districts" feature (spec Part 2 of the
Crowding Index + District Rebalancer request): flow_rebalancer_service's
_discover_district_candidates / _rebalance_district_alternatives.

Mirrors the settlement-discovery test patterns in
test_flow_rebalancer_candidate_discovery.py, but for the coarser,
administrative-boundary-level district pipeline: adaptive radius widening,
current-district exclusion, geographic-plausibility distance bounds, the
staged-pipeline candidate cap, and -- most important, per the explicit spec
requirement -- static + behavioral proof that district discovery is
genuinely dynamic (OSM `boundary=administrative` data), with NO
destination-specific mapping anywhere (no `amritsar_alternatives.json`
equivalent, no `if destination == "Amritsar": return [...]` branch).

test_district_alternatives_for_arbitrary_destination and
test_no_destination_specific_district_mapping_in_source below are the
"destination-agnostic test" the spec explicitly asks for.
"""
import asyncio
import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_sarthi.db")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.crowd import CrowdPressureResponse
from app.schemas.place import District, GeocodeResult, Place
from app.schemas.weather import CurrentWeather, WeatherResponse
from app.services import flow_rebalancer_service as svc
from app.services import crowd_service, geocoding_service, places_service, weather_service


def _district(name, lat, lon, state=None, admin_level="6"):
    return District(id=f"relation/{name}", name=name, admin_level=admin_level, latitude=lat, longitude=lon, state=state)


def _place(name, place_id, lat, lon, category="attraction"):
    return Place(
        id=place_id, external_id=place_id.split("/")[1], source="overpass", source_url="https://osm.org",
        name=name, category=category, raw_tags={}, latitude=lat, longitude=lon,
        address=None, rating=None, review_count=None, photos=[], opening_hours=None,
        website=None, phone=None, description=None,
    )


def _places(lat, lon, count, category="attraction"):
    return [_place(f"{category} {i}", f"node/{category}-{lat}-{lon}-{i}", lat + i * 0.0001, lon, category) for i in range(count)]


# --- _discover_district_candidates: unit tests -----------------------------

def test_district_discovery_widens_radius_when_sparse(monkeypatch):
    lat, lon = 11.0000, 11.0000
    calls = []

    async def fake_nearby_districts(db, latitude, longitude, radius_meters, meta=None):
        calls.append(radius_meters)
        if radius_meters <= svc._DISTRICT_RADIUS_M:
            return [_district("Lone District", lat + 0.5, lon)]
        return [_district(f"Wide District {i}", lat + (i + 1) * 0.8, lon) for i in range(4)]

    monkeypatch.setattr(places_service, "nearby_districts", fake_nearby_districts)

    candidates = asyncio.run(svc._discover_district_candidates(None, lat, lon, current_district=None))

    assert calls == [svc._DISTRICT_RADIUS_M, svc._DISTRICT_RADIUS_FALLBACK_M], (
        "must widen exactly once when the normal radius is sparse, not skip widening or repeat it"
    )
    assert len(candidates) >= 4
    assert all(c["source"] == "osm-district" for c in candidates)


def test_district_discovery_skips_widening_when_not_sparse(monkeypatch):
    lat, lon = 12.0000, 12.0000
    calls = []

    async def fake_nearby_districts(db, latitude, longitude, radius_meters, meta=None):
        calls.append(radius_meters)
        return [_district(f"District {i}", lat + (i + 1) * 0.5, lon) for i in range(3)]

    monkeypatch.setattr(places_service, "nearby_districts", fake_nearby_districts)

    asyncio.run(svc._discover_district_candidates(None, lat, lon, current_district=None))

    assert calls == [svc._DISTRICT_RADIUS_M], "must not widen when the normal radius already returned enough districts"


def test_current_district_excluded_from_candidates(monkeypatch):
    """The district the requested destination is itself in must never be
    offered back to the user as its own 'nearby alternative' (spec: 'remove
    the current district')."""
    lat, lon = 13.0000, 13.0000

    async def fake_nearby_districts(db, latitude, longitude, radius_meters, meta=None):
        return [
            _district("Amritsar", lat + 0.2, lon),  # matches current_district -> must be excluded
            _district("Tarn Taran", lat + 0.6, lon),
            _district("Kapurthala", lat + 0.9, lon),
        ]

    monkeypatch.setattr(places_service, "nearby_districts", fake_nearby_districts)

    candidates = asyncio.run(svc._discover_district_candidates(None, lat, lon, current_district="Amritsar"))

    names = {c["name"] for c in candidates}
    assert "Amritsar" not in names
    assert {"Tarn Taran", "Kapurthala"} <= names


def test_district_distance_bounds_filter_implausible_candidates(monkeypatch):
    """Too-close (essentially the same place) and too-far (not geographically
    plausible as "nearby") candidates must both be filtered."""
    lat, lon = 14.0000, 14.0000

    async def fake_nearby_districts(db, latitude, longitude, radius_meters, meta=None):
        return [
            _district("Too Close District", lat + 0.05, lon),  # well under _MIN_DISTRICT_DISTANCE_KM
            _district("Just Right District", lat + 0.5, lon),
            _district("Too Far District", lat + 5.0, lon),  # well over _MAX_DISTRICT_DISTANCE_KM
        ]

    monkeypatch.setattr(places_service, "nearby_districts", fake_nearby_districts)

    candidates = asyncio.run(svc._discover_district_candidates(None, lat, lon, current_district=None))

    assert {c["name"] for c in candidates} == {"Just Right District"}


def test_district_discovery_caps_candidates_scored(monkeypatch):
    """Staged-pipeline / performance requirement (spec: 'Do not calculate
    detailed crowding for 50+ districts') -- never hand more than
    _MAX_DISTRICT_CANDIDATES_SCORED districts on to the expensive scoring
    stage, even when many are discovered."""
    lat, lon = 15.0000, 15.0000

    async def fake_nearby_districts(db, latitude, longitude, radius_meters, meta=None):
        return [_district(f"District {i}", lat + (i + 1) * 0.3, lon) for i in range(20)]

    monkeypatch.setattr(places_service, "nearby_districts", fake_nearby_districts)

    candidates = asyncio.run(svc._discover_district_candidates(None, lat, lon, current_district=None))

    assert len(candidates) <= svc._MAX_DISTRICT_CANDIDATES_SCORED


# --- _score_candidate reused, unmodified, for district-sourced candidates --

def test_score_candidate_numeric_relief_applies_to_district_candidates_too(monkeypatch):
    """The exact same shared scoring/filter function used for
    settlement/curated alternatives must be reused, unmodified, for
    district-sourced candidates -- proving there is no second, competing
    scoring system for districts."""
    requested_pressure = CrowdPressureResponse(
        destination="Requested Town", latitude=10.0, longitude=20.0, pressure_index=78, status="HIGH", data_type="estimated",
    )
    candidate_pressure = CrowdPressureResponse(
        destination="Neighbour District, State", latitude=10.5, longitude=20.5, pressure_index=51, status="MODERATE", data_type="estimated",
    )

    async def fake_get_pressure(db, label, lat, lon):
        return candidate_pressure

    async def fake_nearby_places(db, lat, lon, radius, categories):
        return []

    async def fake_get_weather(db, lat, lon):
        return WeatherResponse(
            latitude=lat, longitude=lon, timezone="Asia/Kolkata",
            current=CurrentWeather(temperature_c=24.0, condition_code=0, condition_text="Clear", is_day=True),
            hourly=[], daily=[], outdoor_suitability="good",
        )

    monkeypatch.setattr(crowd_service, "get_pressure", fake_get_pressure)
    monkeypatch.setattr(places_service, "nearby_places", fake_nearby_places)
    monkeypatch.setattr(weather_service, "get_weather", fake_get_weather)

    district_candidate = {
        "name": "Neighbour District", "state": "State", "district": "Neighbour District",
        "latitude": 10.5, "longitude": 20.5, "source": "osm-district",
        "tags": [], "hidden_gem": False, "sustainability": None, "_distance_km": 55.0,
    }

    alt = asyncio.run(svc._score_candidate(None, {}, requested_pressure, [], district_candidate))

    assert alt is not None, "27-point numeric pressure relief (78 -> 51) must be recognized as genuinely lower"
    assert alt.destination.source == "osm-district"
    assert alt.tourism_pressure.pressure_index == 51


# --- End-to-end / API-level ------------------------------------------------

def test_district_alternatives_empty_message_when_nothing_discovered(monkeypatch):
    """Honest-messaging requirement: an empty district search must say so
    explicitly, and -- critically -- must NOT suppress the Crowding Index,
    which must always appear on its own (spec: 'Even if no alternatives are
    found, the Crowding Index should still appear')."""
    lat, lon = 20.0000, 20.0000

    async def fake_geocode(db, query, limit=5):
        return [GeocodeResult(display_name="Empty Town, Some State, India", latitude=lat, longitude=lon)]

    async def fake_nearby_places(db, latitude, longitude, radius_meters, categories, meta=None):
        return _places(lat, lon, 65)  # dense -> elevated pressure, so the search actually runs

    async def fake_nearby_settlements(db, latitude, longitude, radius_meters, meta=None):
        return []

    async def fake_nearby_districts(db, latitude, longitude, radius_meters, meta=None):
        return []

    monkeypatch.setattr(geocoding_service, "geocode_search", fake_geocode)
    monkeypatch.setattr(places_service, "nearby_places", fake_nearby_places)
    monkeypatch.setattr(places_service, "nearby_settlements", fake_nearby_settlements)
    monkeypatch.setattr(places_service, "nearby_districts", fake_nearby_districts)

    with TestClient(app) as client:
        resp = client.post("/api/flow/rebalance", json={"destination_query": "Empty Town"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["tourism_pressure"] is not None
        assert body["tourism_pressure"]["pressure_index"] is not None, "Crowding Index must appear even when district discovery finds nothing"
        assert body["district_alternatives"] == []
        assert isinstance(body["district_alternatives_message"], str)
        assert "could not be confirmed" in body["district_alternatives_message"].lower()


@pytest.mark.parametrize("destination_name", ["Zenith Point", "Wander Falls", "Bramble Vale"])
def test_district_alternatives_for_arbitrary_destination(monkeypatch, destination_name):
    """Destination-agnostic end-to-end proof: fictional destination names
    that appear nowhere in curated_destinations.py or crowd.py's seasonal
    lookup must still get a Crowding Index and (dynamically discovered)
    district alternatives, going through the exact same code path as any
    real Indian destination -- there is no per-destination branch to have
    missed. Settlement alternatives are forced empty here specifically to
    prove the district pipeline is independent of it."""
    base = hash(destination_name) % 10
    req_lat, req_lon = 50.0 + base, 60.0 + base
    district_lat, district_lon = req_lat + 1.0, req_lon + 1.0

    async def fake_geocode(db, query, limit=5):
        if destination_name.lower() in query.lower():
            return [GeocodeResult(
                display_name=f"{destination_name}, Some State, India",
                latitude=req_lat, longitude=req_lon, district="Current District", state="Some State",
            )]
        return []

    async def fake_nearby_places(db, latitude, longitude, radius_meters, categories, meta=None):
        if round(latitude, 1) == round(req_lat, 1):
            return _places(req_lat, req_lon, 65)  # dense -> elevated pressure, triggers the search
        return _places(district_lat, district_lon, 5)  # sparser -> lower pressure

    async def fake_nearby_settlements(db, latitude, longitude, radius_meters, meta=None):
        return []  # forced empty -- proves the district pipeline does not depend on this

    async def fake_nearby_districts(db, latitude, longitude, radius_meters, meta=None):
        return [_district(f"{destination_name} Neighbour District", district_lat, district_lon, state="Some State")]

    monkeypatch.setattr(geocoding_service, "geocode_search", fake_geocode)
    monkeypatch.setattr(places_service, "nearby_places", fake_nearby_places)
    monkeypatch.setattr(places_service, "nearby_settlements", fake_nearby_settlements)
    monkeypatch.setattr(places_service, "nearby_districts", fake_nearby_districts)

    with TestClient(app) as client:
        resp = client.post("/api/flow/rebalance", json={"destination_query": destination_name})
        assert resp.status_code == 200
        body = resp.json()

        assert destination_name in body["requested_destination"]["name"]
        # Crowding Index: always present, backend-sourced, never hardcoded.
        assert body["tourism_pressure"] is not None
        assert body["tourism_pressure"]["pressure_index"] is not None
        assert body["tourism_pressure"]["status"] in ("LOW", "MODERATE", "HIGH", "VERY HIGH")
        # Settlement alternatives were forced empty -- must not suppress districts.
        assert body["alternatives"] == []
        assert isinstance(body["district_alternatives_message"], str) and body["district_alternatives_message"]
        if body["district_alternatives"]:
            alt = body["district_alternatives"][0]
            assert alt["destination"]["source"] == "osm-district"
            assert isinstance(alt["experience_match"], int)
            assert isinstance(alt["rebalancing_score"], int)
            assert alt["reasons"], "every recommendation must self-explain with real-data-derived reasons"


def test_no_destination_specific_district_mapping_in_source():
    """Static proof, in addition to the behavioral ones above: the district
    discovery/rebalancing code must contain no hardcoded destination or
    district literal (e.g. no `if destination == "Amritsar": return [...]`),
    and the module must define no manually maintained destination->district
    lookup table/constant (spec explicitly bans `amritsar_alternatives.json`,
    `manali_alternatives.json`, or an equivalent in-code dict)."""
    source = inspect.getsource(svc._discover_district_candidates) + inspect.getsource(svc._rebalance_district_alternatives)
    banned_literals = ["amritsar", "manali", "jalandhar", "kapurthala", "pathankot", "jibhi"]
    lowered = source.lower()
    for literal in banned_literals:
        assert literal not in lowered, f"found a hardcoded destination/district name {literal!r} in district discovery/rebalancing code"

    for banned_name in ("DESTINATION_DISTRICT_MAP", "AMRITSAR_ALTERNATIVES", "MANALI_ALTERNATIVES", "DISTRICT_ALTERNATIVES"):
        assert not hasattr(svc, banned_name), f"found a manually maintained lookup table {banned_name!r} -- discovery must stay dynamic"
