"""
Tests for the Tourist Flow Rebalancer (app/services/flow_rebalancer_service.py
+ app/api/flow.py) -- SIH PS26204 core differentiator: given a destination,
check its REAL Tourism Pressure Index (the one already in
app/services/crowd_service.py -- this feature adds no second pressure
system) and, if elevated, return explainable lower-pressure alternatives.

Every provider is mocked at the same service-layer boundary the rest of the
suite uses (this sandbox has no route to the real public APIs) -- but
deliberately at the SERVICE layer (geocoding_service.geocode_search,
places_service.nearby_places/nearby_settlements, weather_service.get_weather,
routing_service.compute_route), not by mocking crowd_service.get_pressure
itself, so these tests exercise the REAL Tourism Pressure Index math and the
REAL rebalancer scoring logic together, end to end.

Coordinates are unique per test (never reused across tests or with any other
test module in this suite) so Sarthi's own real "demand signal" component
(a live DB counter, see crowd_service._record_and_get_demand) always starts
at a fresh, predictable count=1 regardless of test run order.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_sarthi.db")

from fastapi.testclient import TestClient

from app.integrations.base import ProviderError
from app.main import app
from app.schemas.place import GeocodeResult, Place, Settlement
from app.schemas.weather import CurrentWeather, WeatherResponse
from app.services import geocoding_service, places_service, routing_service, weather_service


def _place(name, place_id, lat, lon, category="attraction"):
    return Place(
        id=place_id, external_id=place_id.split("/")[1], source="overpass", source_url="https://osm.org",
        name=name, category=category, raw_tags={}, latitude=lat, longitude=lon,
        address=None, rating=None, review_count=None, photos=[], opening_hours=None,
        website=None, phone=None, description=None,
    )


def _places(lat, lon, count, category="attraction"):
    return [_place(f"{category} {i}", f"node/{category}-{lat}-{lon}-{i}", lat + i * 0.0001, lon, category) for i in range(count)]


def _weather(lat, lon, suitability="good"):
    temp = {"good": 24.0, "fair": 18.0, "poor": 12.0}[suitability]
    return WeatherResponse(
        latitude=lat, longitude=lon, timezone="Asia/Kolkata",
        current=CurrentWeather(temperature_c=temp, condition_code=0, condition_text="Clear", is_day=True),
        hourly=[], daily=[], outdoor_suitability=suitability,
    )


def _install_common_fakes(monkeypatch, geocode_map, places_map, settlements=None, weather_map=None, route_ok=True, districts=None):
    """geocode_map: {substring-in-query-lowercased: (display_name, lat, lon)}
    places_map: {(round(lat,2), round(lon,2)): list[Place]}
    weather_map: {(round(lat,2), round(lon,2)): "good"|"fair"|"poor"} (default good)
    districts: list[District], default none -- most of these tests exercise the
    settlement/curated pipeline and aren't about "Nearby Similar Districts";
    without this mock, _discover_district_candidates would fall through to the
    REAL (network-blocked-in-CI) OverpassProvider.nearby_districts, which is
    slow (multiple hedge/timeout cycles) even though it fails harmlessly.
    """
    weather_map = weather_map or {}

    async def fake_geocode(db, query, limit=5):
        q = query.lower()
        for needle, (display_name, lat, lon) in geocode_map.items():
            if needle in q:
                return [GeocodeResult(display_name=display_name, latitude=lat, longitude=lon)]
        return []

    async def fake_nearby_places(db, latitude, longitude, radius_meters, categories, meta=None):
        return places_map.get((round(latitude, 2), round(longitude, 2)), [])

    async def fake_nearby_settlements(db, latitude, longitude, radius_meters, meta=None):
        return settlements or []

    async def fake_nearby_districts(db, latitude, longitude, radius_meters, meta=None):
        return districts or []

    async def fake_get_weather(db, latitude, longitude):
        suit = weather_map.get((round(latitude, 2), round(longitude, 2)), "good")
        return _weather(latitude, longitude, suit)

    async def fake_compute_route(db, stops, profile):
        from app.schemas.route import RouteResponse
        if not route_ok:
            raise ProviderError("osrm", "simulated OSRM outage")
        a, b = stops[0], stops[1]
        km = ((a.latitude - b.latitude) ** 2 + (a.longitude - b.longitude) ** 2) ** 0.5 * 111.0
        return RouteResponse(
            profile=profile, total_distance_meters=km * 1000, total_duration_seconds=km * 1000 / 13.9,
            geometry_geojson={"type": "LineString", "coordinates": []}, legs=[],
        )

    monkeypatch.setattr(geocoding_service, "geocode_search", fake_geocode)
    monkeypatch.setattr(places_service, "nearby_places", fake_nearby_places)
    monkeypatch.setattr(places_service, "nearby_settlements", fake_nearby_settlements)
    monkeypatch.setattr(places_service, "nearby_districts", fake_nearby_districts)
    monkeypatch.setattr(weather_service, "get_weather", fake_get_weather)
    monkeypatch.setattr(routing_service, "compute_route", fake_compute_route)


def test_low_pressure_skips_candidate_search_entirely(monkeypatch):
    """Performance requirement: a destination whose pressure is not elevated
    must never trigger settlement discovery, candidate scoring, or OSRM --
    zero extra provider calls beyond the pressure check itself."""
    lat, lon = 10.1000, 76.1000  # unique to this test
    settlement_calls = []

    async def spy_settlements(db, latitude, longitude, radius_meters, meta=None):
        settlement_calls.append((latitude, longitude))
        return []

    _install_common_fakes(
        monkeypatch,
        # "Nagaland" deliberately doesn't substring-match any curated peak-season
        # key in app/integrations/crowd.py -- keeps the seasonal component at
        # the generic (low-ish, in September) fallback value for this test.
        geocode_map={"quietplace": ("Quietplace, Nagaland, India", lat, lon)},
        places_map={(round(lat, 2), round(lon, 2)): _places(lat, lon, 1)},  # very low density -> LOW pressure
    )
    monkeypatch.setattr(places_service, "nearby_settlements", spy_settlements)

    with TestClient(app) as client:
        resp = client.post("/api/flow/rebalance", json={"destination_query": "Quietplace"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["pressure_check_only"] is True
        assert body["rebalancing_triggered"] is False
        assert body["alternatives"] == []
        assert body["tourism_pressure"]["status"] == "LOW"
    assert settlement_calls == [], "LOW pressure must never trigger candidate discovery (Overpass settlement search)"


def test_high_pressure_generates_ranked_alternatives_without_replacing_destination(monkeypatch):
    req_lat, req_lon = 32.2400, 77.1900  # "Manali"-like
    jibhi = (31.9000, 77.3500)
    kasol = (32.0100, 77.3100)

    _install_common_fakes(
        monkeypatch,
        geocode_map={"crowdedtown": ("Crowdedtown, Himachal Pradesh, India", req_lat, req_lon)},
        places_map={
            (round(req_lat, 2), round(req_lon, 2)): _places(req_lat, req_lon, 65),  # dense -> HIGH
            (round(jibhi[0], 2), round(jibhi[1], 2)): _places(*jibhi, 6),
            (round(kasol[0], 2), round(kasol[1], 2)): _places(*kasol, 8),
        },
        settlements=[
            Settlement(id="node/1001", name="Jibhi", place_type="village", latitude=jibhi[0], longitude=jibhi[1]),
            Settlement(id="node/1002", name="Kasol", place_type="village", latitude=kasol[0], longitude=kasol[1]),
        ],
    )

    with TestClient(app) as client:
        resp = client.post("/api/flow/rebalance", json={"destination_query": "Crowdedtown"})
        assert resp.status_code == 200
        body = resp.json()

        assert body["tourism_pressure"]["status"] == "HIGH"
        assert body["rebalancing_triggered"] is True
        # The original destination is echoed back exactly, never swapped for an alternative.
        assert "Crowdedtown" in body["requested_destination"]["name"]

        names = [a["destination"]["name"] for a in body["alternatives"]]
        assert set(names) == {"Jibhi", "Kasol"}
        assert "Crowdedtown" not in names

        scores = [a["rebalancing_score"] for a in body["alternatives"]]
        assert scores == sorted(scores, reverse=True), "alternatives must be ranked highest-score first"
        for a in body["alternatives"]:
            assert 0 <= a["rebalancing_score"] <= 100
            assert 0 <= a["experience_match"] <= 100
            assert a["tourism_pressure"]["status"] in ("LOW", "MODERATE")  # strictly lower rank than requested's HIGH
            assert a["reasons"]
            assert a["travel_time_minutes"] is not None and a["distance_source"] == "osrm"  # shortlist gets real OSRM


def test_candidate_with_equal_or_worse_pressure_is_excluded(monkeypatch):
    req_lat, req_lon = 33.1000, 78.1000
    quiet = (32.8000, 78.3000)
    equally_crowded = (33.3000, 78.4000)

    _install_common_fakes(
        monkeypatch,
        geocode_map={"busyplace": ("Busyplace, Himachal Pradesh, India", req_lat, req_lon)},
        places_map={
            (round(req_lat, 2), round(req_lon, 2)): _places(req_lat, req_lon, 65),
            (round(quiet[0], 2), round(quiet[1], 2)): _places(*quiet, 6),
            (round(equally_crowded[0], 2), round(equally_crowded[1], 2)): _places(*equally_crowded, 65),
        },
        settlements=[
            Settlement(id="node/2001", name="Quietville", place_type="village", latitude=quiet[0], longitude=quiet[1]),
            Settlement(id="node/2002", name="Samepressureville", place_type="town", latitude=equally_crowded[0], longitude=equally_crowded[1]),
        ],
    )

    with TestClient(app) as client:
        resp = client.post("/api/flow/rebalance", json={"destination_query": "Busyplace"})
        body = resp.json()
        names = [a["destination"]["name"] for a in body["alternatives"]]
        assert "Quietville" in names
        assert "Samepressureville" not in names, "a candidate with pressure >= the requested destination's must be filtered out, not just ranked low"


def test_experience_match_reflects_interest_alignment(monkeypatch):
    req_lat, req_lon = 34.1000, 79.1000
    nature_spot = (33.8000, 79.3000)
    food_spot = (34.3000, 79.4000)

    _install_common_fakes(
        monkeypatch,
        geocode_map={"basetown": ("Basetown, Uttarakhand, India", req_lat, req_lon)},
        places_map={
            (round(req_lat, 2), round(req_lon, 2)): _places(req_lat, req_lon, 65),
            (round(nature_spot[0], 2), round(nature_spot[1], 2)): _places(*nature_spot, 8, category="park"),
            (round(food_spot[0], 2), round(food_spot[1], 2)): _places(*food_spot, 8, category="restaurant"),
        },
        settlements=[
            Settlement(id="node/3001", name="Natureville", place_type="village", latitude=nature_spot[0], longitude=nature_spot[1]),
            Settlement(id="node/3002", name="Foodville", place_type="village", latitude=food_spot[0], longitude=food_spot[1]),
        ],
    )

    with TestClient(app) as client:
        resp = client.post("/api/flow/rebalance", json={"destination_query": "Basetown", "interests": ["nature"]})
        body = resp.json()
        by_name = {a["destination"]["name"]: a for a in body["alternatives"]}
        assert by_name["Natureville"]["experience_match"] > by_name["Foodville"]["experience_match"], (
            "requesting 'nature' must score the park-dominated candidate higher than the restaurant-dominated one"
        )


def test_pressure_relief_factor_favors_lower_pressure_candidate(monkeypatch):
    req_lat, req_lon = 35.1000, 80.1000
    very_quiet = (34.8000, 80.3000)
    moderately_busy = (35.3000, 80.4000)

    _install_common_fakes(
        monkeypatch,
        geocode_map={"origintown": ("Origintown, Uttarakhand, India", req_lat, req_lon)},
        places_map={
            (round(req_lat, 2), round(req_lon, 2)): _places(req_lat, req_lon, 65),
            (round(very_quiet[0], 2), round(very_quiet[1], 2)): _places(*very_quiet, 2),
            (round(moderately_busy[0], 2), round(moderately_busy[1], 2)): _places(*moderately_busy, 22),
        },
        settlements=[
            Settlement(id="node/4001", name="Veryquietville", place_type="hamlet", latitude=very_quiet[0], longitude=very_quiet[1]),
            Settlement(id="node/4002", name="Somewhatbusyville", place_type="town", latitude=moderately_busy[0], longitude=moderately_busy[1]),
        ],
    )

    with TestClient(app) as client:
        resp = client.post("/api/flow/rebalance", json={"destination_query": "Origintown"})
        body = resp.json()
        by_name = {a["destination"]["name"]: a for a in body["alternatives"]}
        relief_quiet = by_name["Veryquietville"]["factors"]["pressure_relief"]["value"]
        relief_busy = by_name["Somewhatbusyville"]["factors"]["pressure_relief"]["value"]
        assert relief_quiet > relief_busy, "the much-lower-pressure candidate must score higher on the pressure_relief factor"


def test_provider_failure_degrades_gracefully_never_crashes(monkeypatch):
    lat, lon = 36.1000, 81.1000

    async def fake_geocode(db, query, limit=5):
        return [GeocodeResult(display_name="Failtown, Assam, India", latitude=lat, longitude=lon)]

    async def failing_nearby_places(db, latitude, longitude, radius_meters, categories, meta=None):
        raise ProviderError("overpass", "simulated total Overpass outage")

    async def failing_settlements(db, latitude, longitude, radius_meters, meta=None):
        raise ProviderError("overpass", "simulated total Overpass outage")

    monkeypatch.setattr(geocoding_service, "geocode_search", fake_geocode)
    monkeypatch.setattr(places_service, "nearby_places", failing_nearby_places)
    monkeypatch.setattr(places_service, "nearby_settlements", failing_settlements)

    with TestClient(app) as client:
        resp = client.post("/api/flow/rebalance", json={"destination_query": "Failtown"})
        assert resp.status_code == 200  # never a 500, whatever fails underneath
        body = resp.json()
        assert isinstance(body.get("message"), str) and body["message"]


def test_unavailable_pressure_data_skips_search_honestly(monkeypatch):
    """When Sarthi genuinely can't compute a reliable pressure estimate
    (every live signal failed), the rebalancer must not guess -- it should
    behave like a non-elevated destination (no candidate search), not
    silently treat 'unknown' as 'safe to search anyway'."""
    lat, lon = 37.1000, 82.1000

    async def fake_geocode(db, query, limit=5):
        return [GeocodeResult(display_name="Unknownpressuretown, Odisha, India", latitude=lat, longitude=lon)]

    async def failing_nearby_places(db, latitude, longitude, radius_meters, categories, meta=None):
        raise ProviderError("overpass", "down")

    async def failing_weather(db, latitude, longitude):
        raise ProviderError("open-meteo", "down")

    monkeypatch.setattr(geocoding_service, "geocode_search", fake_geocode)
    monkeypatch.setattr(places_service, "nearby_places", failing_nearby_places)
    monkeypatch.setattr(weather_service, "get_weather", failing_weather)

    with TestClient(app) as client:
        resp = client.post("/api/flow/rebalance", json={"destination_query": "Unknownpressuretown"})
        body = resp.json()
        assert body["tourism_pressure"]["data_type"] == "unavailable"
        assert body["tourism_pressure"]["status"] is None
        assert body["pressure_check_only"] is True
        assert body["alternatives"] == []


def test_missing_candidates_returns_honest_message_not_a_crash(monkeypatch):
    lat, lon = 38.1000, 83.1000
    _install_common_fakes(
        monkeypatch,
        geocode_map={"isolatedtown": ("Isolatedtown, Nagaland, India", lat, lon)},
        places_map={(round(lat, 2), round(lon, 2)): _places(lat, lon, 65)},  # HIGH pressure, but...
        settlements=[],  # ...genuinely no nearby real settlements
    )

    with TestClient(app) as client:
        resp = client.post("/api/flow/rebalance", json={"destination_query": "Isolatedtown"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["alternatives"] == []
        assert body["rebalancing_triggered"] is False
        # Honest data-availability wording (spec: "Say 'could not be confirmed
        # from the available data' when appropriate" -- never implies a
        # confirmed absence of alternatives, since none were even found to
        # evaluate).
        assert "could not be confirmed from the available data" in body["message"].lower()


def test_destination_not_found_is_honest_not_a_guess(monkeypatch):
    async def fake_geocode(db, query, limit=5):
        return []

    monkeypatch.setattr(geocoding_service, "geocode_search", fake_geocode)
    with TestClient(app) as client:
        resp = client.post("/api/flow/rebalance", json={"destination_query": "Totally Made Up Place Zzz"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["requested_destination"] is None
        assert "couldn't find" in body["message"].lower()


def test_api_response_schema_shape(monkeypatch):
    """The response always carries the documented Tourist Flow Rebalancer
    contract (method/is_machine_learning included) regardless of outcome --
    this is deterministic weighted scoring, never labelled AI/ML."""
    lat, lon = 39.1000, 84.1000
    _install_common_fakes(
        monkeypatch,
        geocode_map={"schematown": ("Schematown, Sikkim, India", lat, lon)},
        places_map={(round(lat, 2), round(lon, 2)): _places(lat, lon, 2)},
    )
    with TestClient(app) as client:
        resp = client.post("/api/flow/rebalance", json={"destination_query": "Schematown"})
        body = resp.json()
        for key in ("requested_destination", "tourism_pressure", "rebalancing_triggered", "pressure_check_only",
                    "alternatives", "method", "is_machine_learning", "message"):
            assert key in body
        assert body["method"] == "deterministic-weighted-scoring"
        assert body["is_machine_learning"] is False
