"""
Tests for the master-upgrade AI features: the real-data-grounded AI trip
planner (spec sections 13/14/21/22) and AI photo identification with
independent verification (spec sections 15/16).

Every provider call (Overpass, Open-Meteo, Nominatim, Gemini/OpenAI) is
mocked at the same integration boundary the existing smoke tests use (this
sandbox has no route to any of those real services). The point of these
tests is specifically to prove the GROUNDING/VALIDATION logic works, not to
re-test Overpass/Nominatim/weather themselves.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_sarthi.db")

from fastapi.testclient import TestClient

from app.integrations.base import AIChatResult
from app.main import app
from app.schemas.place import GeocodeResult, Place


def _place(name, place_id, lat, lon, category="attraction"):
    return Place(
        id=place_id, external_id=place_id.split("/")[1], source="overpass", source_url="https://osm.org",
        name=name, category=category, raw_tags={"name": name}, latitude=lat, longitude=lon,
        address=None, rating=None, review_count=None, photos=[], opening_hours=None,
        website=None, phone=None, description=None,
    )


def test_plan_trip_drops_hallucinated_place_id_and_hydrates_from_real_data(monkeypatch):
    """The core honesty guarantee of the AI planner: if the model cites a
    place_id that was never actually retrieved, that stop must be dropped
    (removed_unverified_count incremented), and any stop that DOES survive
    must show Sarthi's own retrieved name/coords -- not whatever text the
    model attached to it."""
    from app.core import config as config_module
    from app.services import ai_planner_service

    fake_settings = config_module.Settings(gemini_api_key="fake-key", ai_provider="gemini")
    monkeypatch.setattr(ai_planner_service, "get_settings", lambda: fake_settings)

    from app.services import geocoding_service
    async def fake_geocode(db, query, limit=5):
        return [GeocodeResult(display_name="Jaipur, Rajasthan, India", latitude=26.9124, longitude=75.7873, source="nominatim")]
    monkeypatch.setattr(geocoding_service, "geocode_search", fake_geocode)

    real_places = [_place("Amber Fort", "node/1", 26.98, 75.85), _place("Hawa Mahal", "node/2", 26.92, 75.82)]
    from app.services import places_service
    async def fake_nearby(db, lat, lon, radius, categories):
        return real_places
    monkeypatch.setattr(places_service, "nearby_places", fake_nearby)

    from app.services import weather_service
    async def fake_weather(db, lat, lon):
        from app.schemas.weather import CurrentWeather, WeatherResponse
        return WeatherResponse(latitude=lat, longitude=lon, timezone="Asia/Kolkata",
                                current=CurrentWeather(temperature_c=28.0, condition_code=0, condition_text="Clear", is_day=True),
                                hourly=[], daily=[], outdoor_suitability="good")
    monkeypatch.setattr(weather_service, "get_weather", fake_weather)

    from app.services import events_service
    async def fake_events(db, lat, lon, **kw):
        from app.schemas.event import EventSearchResponse
        return EventSearchResponse(configured=False)
    monkeypatch.setattr(events_service, "search_events", fake_events)

    # The model cites ONE real place_id (node/1) and ONE it made up (node/999) with a
    # fabricated name/description that must NOT leak into the response even for node/1.
    model_json = json.dumps({
        "days": [{
            "day": 1, "title": "Heritage day",
            "stops": [
                {"place_id": "node/1", "time_of_day": "Morning", "reason": "Iconic heritage site"},
                {"place_id": "node/999", "time_of_day": "Afternoon", "reason": "A place that was never actually retrieved"},
            ],
        }],
        "notes": "Great heritage day trip.",
    })

    async def fake_chat(self, system_prompt, messages, tools):
        return AIChatResult(text=model_json)

    from app.integrations.gemini import GeminiProvider
    monkeypatch.setattr(GeminiProvider, "chat", fake_chat)

    with TestClient(app) as client:
        resp = client.post("/api/ai/plan-trip", json={"destination_query": "Jaipur", "days": 1, "interests": ["heritage"]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["configured"] is True
        assert body["removed_unverified_count"] == 1, "the hallucinated node/999 stop must be dropped, not shown"
        assert len(body["days"]) == 1
        stops = body["days"][0]["stops"]
        assert len(stops) == 1
        assert stops[0]["place_id"] == "node/1"
        assert stops[0]["name"] == "Amber Fort", "displayed name must come from Sarthi's own retrieved Place, not the model's text"
        assert stops[0]["latitude"] == 26.98


def test_plan_trip_not_configured_gives_clear_message_not_an_error(monkeypatch):
    from app.core import config as config_module
    from app.services import ai_planner_service
    fake_settings = config_module.Settings(gemini_api_key="", openai_api_key="", ai_provider="gemini")
    monkeypatch.setattr(ai_planner_service, "get_settings", lambda: fake_settings)

    with TestClient(app) as client:
        resp = client.post("/api/ai/plan-trip", json={"destination_query": "Jaipur"})
        assert resp.status_code == 200  # never a 500 -- an honest, structured "not configured" response
        body = resp.json()
        assert body["configured"] is False
        assert "GEMINI_API_KEY" in body["message"]


def test_analyze_image_verified_when_geocoder_confirms_the_guess(monkeypatch):
    from app.core import config as config_module
    from app.services import photo_id_service
    fake_settings = config_module.Settings(gemini_api_key="fake-key", ai_provider="gemini")
    monkeypatch.setattr(photo_id_service, "get_settings", lambda: fake_settings)

    vision_json = json.dumps({
        "likely_place": "Gobindgarh Fort", "confidence": 0.82, "category": "historic_site",
        "possible_destination": "Amritsar", "visual_clues": ["brick fort walls"], "cultural_clues": ["Sikh-era fort"],
        "alternatives": [{"name": "Ram Bagh", "confidence": 0.1}],
    })

    async def fake_analyze_image(self, image_bytes, mime_type, prompt):
        return AIChatResult(text=vision_json)

    from app.integrations.gemini import GeminiProvider
    monkeypatch.setattr(GeminiProvider, "analyze_image", fake_analyze_image)

    from app.services import geocoding_service
    async def fake_geocode(db, query, limit=5):
        return [GeocodeResult(display_name="Gobindgarh Fort, Amritsar, Punjab, India", latitude=31.627, longitude=74.860, source="nominatim")]
    monkeypatch.setattr(geocoding_service, "geocode_search", fake_geocode)

    from app.services import places_service
    async def fake_nearby(db, lat, lon, radius, categories):
        return [_place("Gobindgarh Fort", "node/5093950623", lat, lon, "attraction")]
    monkeypatch.setattr(places_service, "nearby_places", fake_nearby)

    with TestClient(app) as client:
        resp = client.post("/api/ai/analyze-image", files={"file": ("test.jpg", b"\xff\xd8\xff\xfake-jpeg-bytes", "image/jpeg")})
        assert resp.status_code == 200
        body = resp.json()
        assert body["configured"] is True
        assert body["likely_place"] == "Gobindgarh Fort"
        assert body["confidence_label"] == "Likely match"
        assert body["verified"] is True
        assert body["verified_location"]["latitude"] == 31.627
        assert len(body["nearby_attractions"]) == 1
        assert body["data_type"] == "ai-inferred"


def test_analyze_image_unverified_when_geocoder_finds_nothing(monkeypatch):
    """The critical honesty case: Gemini is confident, but no real geocoder
    result backs it up -- the response must say unverified, not confirmed."""
    from app.core import config as config_module
    from app.services import photo_id_service
    fake_settings = config_module.Settings(gemini_api_key="fake-key", ai_provider="gemini")
    monkeypatch.setattr(photo_id_service, "get_settings", lambda: fake_settings)

    vision_json = json.dumps({
        "likely_place": "A Completely Made Up Monument Name", "confidence": 0.55, "category": "historic_site",
        "possible_destination": "Nowhere", "visual_clues": [], "cultural_clues": [], "alternatives": [],
    })

    async def fake_analyze_image(self, image_bytes, mime_type, prompt):
        return AIChatResult(text=vision_json)

    from app.integrations.gemini import GeminiProvider
    monkeypatch.setattr(GeminiProvider, "analyze_image", fake_analyze_image)

    from app.services import geocoding_service
    async def fake_geocode_empty(db, query, limit=5):
        return []
    monkeypatch.setattr(geocoding_service, "geocode_search", fake_geocode_empty)

    with TestClient(app) as client:
        resp = client.post("/api/ai/analyze-image", files={"file": ("test.jpg", b"\xff\xd8\xff\xfake-jpeg-bytes", "image/jpeg")})
        assert resp.status_code == 200
        body = resp.json()
        assert body["verified"] is False
        assert body["verified_location"] is None
        assert body["nearby_attractions"] == []
        assert body["likely_place"] == "A Completely Made Up Monument Name"  # still shown, but honestly unverified


def test_analyze_image_rejects_unsupported_file_type():
    with TestClient(app) as client:
        resp = client.post("/api/ai/analyze-image", files={"file": ("test.txt", b"not an image", "text/plain")})
        assert resp.status_code == 415
