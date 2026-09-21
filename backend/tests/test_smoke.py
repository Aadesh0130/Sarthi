"""
Smoke tests that exercise the full request/response cycle with the real
providers monkeypatched out (this sandbox has no route to the public
Nominatim/Overpass/OSRM/Open-Meteo endpoints). These check that:
  - the app boots and the DB schema creates cleanly
  - request/response shapes match the pydantic schemas end-to-end
  - caching writes/reads through api_cache without error
  - the recommendation engine produces a sane, explainable ranking
  - the itinerary CRUD + weather-based replan flow works
  - the AI endpoint reports "not configured" when no key is set (default)

Real-network verification against the live public APIs is done separately,
from the deployment machine (see README "Testing against the real APIs").

Note: TestClient must be used as a context manager (`with TestClient(app) as
client:`) so FastAPI's startup event (which creates the DB tables) actually
runs.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_sarthi.db")

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.place import GeocodeResult, Place
from app.schemas.route import RouteLeg, RouteResponse
from app.schemas.weather import CurrentWeather, WeatherResponse


def _mock_place(name="Golden Temple", category="religious", lat=31.62, lon=74.8765, place_id="node/111"):
    return Place(
        id=place_id, external_id=place_id.split("/")[1], source="overpass", source_url="https://osm.org",
        name=name, category=category, raw_tags={"name": name}, latitude=lat, longitude=lon,
        address="Amritsar, Punjab", rating=None, review_count=None, photos=[], opening_hours="24/7",
        website=None, phone=None, description=None,
    )


def test_health():
    with TestClient(app) as client:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["ai_configured"] is False  # OPENAI_API_KEY unset by default


def test_geocode_search_mocked(monkeypatch):
    from app.integrations.nominatim import NominatimProvider

    async def fake_search(self, query, limit=5):
        return [GeocodeResult(display_name="Amritsar, Punjab, India", latitude=31.634, longitude=74.8723, place_type="city")]

    monkeypatch.setattr(NominatimProvider, "search", fake_search)

    with TestClient(app) as client:
        resp = client.get("/api/geocode/search", params={"q": "Amritsar"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["latitude"] == pytest.approx(31.634, rel=1e-3)


def test_nearby_places_and_recommendations_mocked(monkeypatch):
    from app.integrations.overpass import OverpassProvider

    async def fake_nearby(self, latitude, longitude, radius_meters, categories):
        return [
            _mock_place("Golden Temple", "religious", 31.6200, 74.8765, "node/1"),
            _mock_place("Jallianwala Bagh", "historic", 31.6215, 74.8800, "node/2"),
            _mock_place("Kesar Da Dhaba", "restaurant", 31.6300, 74.8700, "node/3"),
        ]

    monkeypatch.setattr(OverpassProvider, "nearby", fake_nearby)

    async def fake_forecast(self, latitude, longitude):
        return WeatherResponse(
            latitude=latitude, longitude=longitude, timezone="Asia/Kolkata",
            current=CurrentWeather(temperature_c=22.0, condition_code=61, condition_text="Slight rain", is_day=True),
            hourly=[], daily=[], outdoor_suitability="poor",
        )

    from app.integrations.open_meteo import OpenMeteoProvider
    monkeypatch.setattr(OpenMeteoProvider, "forecast", fake_forecast)

    with TestClient(app) as client:
        resp = client.get("/api/places/nearby", params={"lat": 31.63, "lon": 74.87})
        assert resp.status_code == 200
        places = resp.json()
        assert len(places) == 3
        assert all(p["distance_meters"] is not None for p in places)

        resp2 = client.post(
            "/api/recommendations",
            json={"latitude": 31.63, "longitude": 74.87, "interests": ["spiritual"], "pace": "balanced", "budget": "comfort"},
        )
        assert resp2.status_code == 200
        rec = resp2.json()
        assert rec["is_machine_learning"] is False
        assert len(rec["results"]) == 3
        assert all(r["reasons"] for r in rec["results"])
        top_names = [r["place"]["name"] for r in rec["results"][:1]]
        assert "Golden Temple" in top_names


def test_route_mocked(monkeypatch):
    from app.integrations.osrm import OSRMProvider

    async def fake_route(self, stops, profile):
        return RouteResponse(
            profile=profile, total_distance_meters=1234.5, total_duration_seconds=600.0,
            geometry_geojson={"type": "LineString", "coordinates": [[74.87, 31.63], [74.88, 31.64]]},
            legs=[RouteLeg(from_name=stops[0].name or "A", to_name=stops[1].name or "B", distance_meters=1234.5, duration_seconds=600.0)],
        )

    monkeypatch.setattr(OSRMProvider, "route", fake_route)

    with TestClient(app) as client:
        resp = client.post(
            "/api/routes",
            json={"stops": [{"name": "Golden Temple", "latitude": 31.62, "longitude": 74.8765},
                             {"name": "Jallianwala Bagh", "latitude": 31.6215, "longitude": 74.88}]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_distance_meters"] == 1234.5
        assert body["geometry_geojson"]["type"] == "LineString"


def test_itinerary_crud_and_replan(monkeypatch):
    async def fake_forecast(self, latitude, longitude):
        return WeatherResponse(
            latitude=latitude, longitude=longitude, timezone="Asia/Kolkata",
            current=CurrentWeather(temperature_c=19.0, condition_code=65, condition_text="Heavy rain", is_day=True),
            hourly=[], daily=[], outdoor_suitability="poor",
        )

    from app.integrations.open_meteo import OpenMeteoProvider
    monkeypatch.setattr(OpenMeteoProvider, "forecast", fake_forecast)

    with TestClient(app) as client:
        create_resp = client.post(
            "/api/itineraries",
            json={
                "title": "1 day in Amritsar", "destination_query": "Amritsar", "days": 1, "travelers": 2,
                "items": [
                    {"day": 1, "place_id": "node/1", "name": "Golden Temple", "category": "religious", "latitude": 31.62, "longitude": 74.8765},
                    {"day": 1, "place_id": "node/2", "name": "Jallianwala Bagh", "category": "historic", "latitude": 31.6215, "longitude": 74.88},
                ],
            },
        )
        assert create_resp.status_code == 200
        itinerary = create_resp.json()
        assert len(itinerary["items"]) == 2
        itinerary_id = itinerary["id"]

        replan_resp = client.post(f"/api/itineraries/{itinerary_id}/replan", json={"reason": "weather"})
        assert replan_resp.status_code == 200
        replanned = replan_resp.json()
        assert replanned["items"][0]["category"] == "religious"


def test_ai_chat_not_configured():
    with TestClient(app) as client:
        resp = client.post("/api/ai/chat", json={"messages": [{"role": "user", "content": "Plan a day in Amritsar"}]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["configured"] is False
        assert "OPENAI_API_KEY" in body["message"]


def test_events_hotels_images_not_configured():
    """No TICKETMASTER_API_KEY/HOTELBEDS_API_KEY/UNSPLASH_ACCESS_KEY set by
    default -- every one of these must say so honestly, not silently return
    an empty (and therefore misleading) success."""
    with TestClient(app) as client:
        events_resp = client.get("/api/events", params={"lat": 31.63, "lon": 74.87})
        assert events_resp.status_code == 200
        assert events_resp.json()["configured"] is False

        hotels_resp = client.get("/api/hotels", params={"lat": 31.63, "lon": 74.87, "check_in": "2026-12-01", "check_out": "2026-12-03"})
        assert hotels_resp.status_code == 200
        assert hotels_resp.json()["configured"] is False

        images_resp = client.get("/api/images/search", params={"q": "Golden Temple"})
        assert images_resp.status_code == 200
        assert images_resp.json()["configured"] is False

        health = client.get("/api/health").json()
        assert health["events_configured"] is False
        assert health["hotels_configured"] is False
        assert health["images_configured"] is False


def test_events_configured_mocked(monkeypatch):
    """With a key set, TicketmasterProvider is exercised (mocked at the
    provider boundary, same pattern as the other real-network providers)."""
    from app.core import config as config_module
    from app.schemas.event import EventResult
    from app.services import events_service

    fake_settings = config_module.Settings(ticketmaster_api_key="fake-key")
    monkeypatch.setattr(events_service, "settings", fake_settings)

    async def fake_search(self, latitude, longitude, radius_km=25, keyword="", start_date=None, end_date=None):
        return [EventResult(id="evt1", name="Test Concert", source="ticketmaster", latitude=latitude, longitude=longitude)]

    from app.integrations.ticketmaster import TicketmasterProvider
    monkeypatch.setattr(TicketmasterProvider, "search", fake_search)

    with TestClient(app) as client:
        resp = client.get("/api/events", params={"lat": 31.63, "lon": 74.87})
        assert resp.status_code == 200
        body = resp.json()
        assert body["configured"] is True
        assert len(body["events"]) == 1
        assert body["events"][0]["name"] == "Test Concert"


def test_cultural_info_curated_and_external_fallback(monkeypatch):
    with TestClient(app) as client:
        # 1) Curated match -- exact behavior preserved from the original build.
        resp = client.get("/api/places/node/1/culture")
        assert resp.status_code == 200
        # place id doesn't exist via Overpass in this test run, so name falls back to osm_id ("1"),
        # which won't match the curated set -- confirm the honest "not found" path instead.
        body = resp.json()
        assert body["matched"] is False
        assert body["source"] == "none"

    # 2) Direct curated lookup via the top-level /api/culture/{id} route.
    with TestClient(app) as client:
        resp = client.get("/api/culture/some-id", params={"name": "Golden Temple, Amritsar"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["matched"] is True
        assert body["source"] == "curated"

    # 3) No curated match, Wikipedia mocked to return a result.
    from app.services import cultural_service

    async def fake_wikipedia(name):
        return {"title": "Fictional Fort", "extract": "A fictional fort used only for testing.", "source_url": "https://en.wikipedia.org/wiki/Fictional_Fort"}

    monkeypatch.setattr(cultural_service, "wikipedia_lookup", fake_wikipedia)

    with TestClient(app) as client:
        resp = client.get("/api/culture/some-id-2", params={"name": "Fictional Fort"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["matched"] is True
        assert body["source"] == "wikipedia"
        assert body["summary"] == "A fictional fort used only for testing."

    # 4) Neither curated nor Wikipedia nor Wikidata match -- honest fallback.
    async def none_lookup(name):
        return None

    monkeypatch.setattr(cultural_service, "wikipedia_lookup", none_lookup)
    monkeypatch.setattr(cultural_service, "wikidata_lookup", none_lookup)

    with TestClient(app) as client:
        resp = client.get("/api/culture/some-id-3", params={"name": "Totally Unknown Place XYZ"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["matched"] is False
        assert body["source"] == "none"
        assert body["fallback_message"]


def test_replan_new_trigger_reasons():
    with TestClient(app) as client:
        create_resp = client.post(
            "/api/itineraries",
            json={
                "title": "3-stop day", "destination_query": "Amritsar", "days": 1, "travelers": 1,
                "interests": ["heritage"],
                "items": [
                    {"day": 1, "place_id": "node/1", "name": "Golden Temple", "category": "religious", "latitude": 31.6200, "longitude": 74.8765, "estimated_duration_minutes": 90},
                    {"day": 1, "place_id": "node/2", "name": "Jallianwala Bagh", "category": "historic", "latitude": 31.6215, "longitude": 74.8800, "estimated_duration_minutes": 60},
                    {"day": 1, "place_id": "node/3", "name": "Kesar Da Dhaba", "category": "restaurant", "latitude": 31.6300, "longitude": 74.8700, "estimated_duration_minutes": 45},
                ],
            },
        )
        itinerary_id = create_resp.json()["id"]

        # remove_place
        resp = client.post(f"/api/itineraries/{itinerary_id}/replan", json={"reason": "remove_place", "remove_place_id": "node/3"})
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 2
        assert all(i["place_id"] != "node/3" for i in items)
        assert [i["order_index"] for i in items] == [0, 1]

        # time_limited: only 1.5 hours left -- Golden Temple (90 min) fits exactly, Jallianwala (60 min) doesn't
        resp2 = client.post(f"/api/itineraries/{itinerary_id}/replan", json={"reason": "time_limited", "day": 1, "new_available_hours": 1.5})
        assert resp2.status_code == 200
        items2 = resp2.json()["items"]
        assert len(items2) == 1
        assert "removed" in items2[0]["notes"]

        # preferences_changed: deterministic re-scoring, should not error
        resp3 = client.post(f"/api/itineraries/{itinerary_id}/replan", json={"reason": "preferences_changed", "new_interests": ["spiritual"]})
        assert resp3.status_code == 200

        # unsupported trigger is rejected with a clear explanation, not faked
        resp4 = client.post(f"/api/itineraries/{itinerary_id}/replan", json={"reason": "event_change"})
        assert resp4.status_code == 400
        assert "live" in resp4.json()["detail"].lower()


def test_ai_chat_tool_loop_mocked(monkeypatch):
    """Exercises the provider-agnostic multi-round tool-calling loop in
    ai_service.py without hitting a real LLM -- AIProvider.chat is mocked at
    the interface boundary shared by both OpenAI and Gemini."""
    from app.core import config as config_module
    from app.integrations.base import AIChatResult
    from app.services import ai_service

    fake_settings = config_module.Settings(openai_api_key="fake-key", ai_provider="openai")
    monkeypatch.setattr(ai_service, "get_settings", lambda: fake_settings)

    call_count = {"n": 0}

    async def fake_chat(self, system_prompt, messages, tools):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return AIChatResult(
                text=None,
                tool_calls=[{"id": "call_0", "name": "get_weather", "arguments": {"latitude": 31.62, "longitude": 74.87}}],
                assistant_message={"role": "assistant", "content": "", "tool_calls": [{"id": "call_0", "name": "get_weather", "arguments": {"latitude": 31.62, "longitude": 74.87}}]},
            )
        return AIChatResult(text="It's a good day to visit outdoor sites in Amritsar.")

    from app.integrations.openai_provider import OpenAIProvider
    monkeypatch.setattr(OpenAIProvider, "chat", fake_chat)

    async def fake_forecast(self, latitude, longitude):
        return WeatherResponse(
            latitude=latitude, longitude=longitude, timezone="Asia/Kolkata",
            current=CurrentWeather(temperature_c=27.0, condition_code=0, condition_text="Clear sky", is_day=True),
            hourly=[], daily=[], outdoor_suitability="good",
        )

    from app.integrations.open_meteo import OpenMeteoProvider
    monkeypatch.setattr(OpenMeteoProvider, "forecast", fake_forecast)

    with TestClient(app) as client:
        resp = client.post("/api/ai/chat", json={"messages": [{"role": "user", "content": "Should I go outside today?"}]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["configured"] is True
        assert body["provider"] == "openai"
        assert "outdoor" in body["reply"].lower()
        assert len(body["tool_calls"]) == 1
        assert body["tool_calls"][0]["name"] == "get_weather"


def test_crowd_pressure_all_signals_available(monkeypatch):
    """With live place-density and weather signals both mocked as succeeding
    (Ticketmaster left unconfigured, as in every other test here), the
    Tourism Pressure Index should compute a real 0-100 number with an
    explainable component breakdown -- never a fabricated live-crowd claim."""
    from app.integrations.overpass import OverpassProvider

    async def fake_nearby(self, latitude, longitude, radius_meters, categories):
        return [_mock_place(f"Place {i}", "attraction", 26.91 + i * 0.001, 75.78 + i * 0.001, f"node/{i}") for i in range(40)]

    monkeypatch.setattr(OverpassProvider, "nearby", fake_nearby)

    async def fake_forecast(self, latitude, longitude):
        return WeatherResponse(
            latitude=latitude, longitude=longitude, timezone="Asia/Kolkata",
            current=CurrentWeather(temperature_c=24.0, condition_code=0, condition_text="Clear sky", is_day=True),
            hourly=[], daily=[], outdoor_suitability="good",
        )

    from app.integrations.open_meteo import OpenMeteoProvider
    monkeypatch.setattr(OpenMeteoProvider, "forecast", fake_forecast)

    with TestClient(app) as client:
        resp = client.get("/api/crowd/pressure", params={"lat": 26.9124, "lon": 75.7873, "destination": "Jaipur, Rajasthan, India"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["data_type"] == "estimated"
        assert isinstance(body["pressure_index"], int)
        assert 0 <= body["pressure_index"] <= 100
        assert body["status"] in ("LOW", "MODERATE", "HIGH", "VERY HIGH")
        assert body["weather_suitability"] == "GOOD"
        assert body["components"]["place_density"]["used"] is True
        assert body["components"]["weather_suitability"]["used"] is True
        assert body["components"]["seasonal_pressure"]["data_type"] == "curated"
        assert body["components"]["event_pressure"]["used"] is False  # Ticketmaster not configured
        assert len(body["explanation"]) >= 3


def test_crowd_pressure_unavailable_when_live_signals_fail(monkeypatch):
    """When every live signal genuinely fails, the engine must say so plainly
    instead of inventing a number (spec: 'Missing crowd data' test case)."""
    from app.integrations.base import ProviderError
    from app.integrations.overpass import OverpassProvider

    async def failing_nearby(self, latitude, longitude, radius_meters, categories):
        raise ProviderError("overpass", "503 Service Unavailable")

    monkeypatch.setattr(OverpassProvider, "nearby", failing_nearby)

    async def failing_forecast(self, latitude, longitude):
        raise ProviderError("open-meteo", "timeout")

    from app.integrations.open_meteo import OpenMeteoProvider
    monkeypatch.setattr(OpenMeteoProvider, "forecast", failing_forecast)

    with TestClient(app) as client:
        resp = client.get("/api/crowd/pressure", params={"lat": 15.335, "lon": 76.46, "destination": "Hampi, Karnataka, India"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["pressure_index"] is None
        assert body["status"] is None
        assert body["data_type"] == "unavailable"
        assert "no reliable" in body["message"].lower()
