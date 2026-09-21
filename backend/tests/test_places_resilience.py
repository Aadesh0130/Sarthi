"""
Tests for the places-nearby resilience fix (2026-09-15 real-world report: all
three original Overpass mirrors -- overpass-api.de, kumi.systems,
openstreetmap.ru -- failed at the same time for the same real query, giving
the user a hard "temporarily unavailable" even though a previous successful
search for that exact spot already existed in Sarthi's own cache).

These prove the actual behavior, not just intent:
  1. When every live mirror fails but an earlier successful fetch for the
     same spot is still within the emergency grace window, real (if
     slightly older) results are served instead of a hard failure, and the
     caller is told this happened via `meta`/a response header -- never
     silently presented as fresh live data.
  2. When nothing is cached (or the only cached entry is far older than the
     grace window) and every mirror fails, the honest failure is preserved
     -- this is a resilience improvement, not a promise that a live lookup
     always succeeds.
  3. The public HTTP route (/api/places/nearby) surfaces the same fallback
     via X-Sarthi-Data-Freshness / X-Sarthi-Cache-Age-Seconds headers
     without changing the response body shape.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_sarthi.db")

import pytest
from fastapi.testclient import TestClient

from app.core.cache import cache_set
from app.core.config import get_settings
from app.db.database import SessionLocal, init_db
from app.integrations.base import ProviderError
from app.integrations.overpass import OverpassProvider
from app.main import app
from app.schemas.place import Place
from app.services import places_service


def _place(name, place_id, lat, lon, category="attraction"):
    return Place(
        id=place_id, external_id=place_id.split("/")[1], source="overpass", source_url="https://osm.org",
        name=name, category=category, raw_tags={"name": name}, latitude=lat, longitude=lon,
        address=None, rating=None, review_count=None, photos=[], opening_hours=None,
        website=None, phone=None, description=None,
    )


async def _always_fails(self, latitude, longitude, radius_meters, categories):
    raise ProviderError(
        "overpass",
        "overpass-api.de: Server error '504 Gateway Timeout'; overpass.kumi.systems: ReadTimeout; "
        "overpass.openstreetmap.ru: ConnectTimeout; overpass.osm.ch: ConnectTimeout",
    )


def test_nearby_places_falls_back_to_stale_cache_when_every_mirror_fails(monkeypatch):
    init_db()
    settings = get_settings()
    db = SessionLocal()
    try:
        lat, lon, radius = 12.3456, 56.7890, 4000
        key = places_service._key("nearby", f"{lat:.4f}", f"{lon:.4f}", str(radius), "")
        real_place = _place("Old But Real Fort", "node/777", lat, lon, "historic")
        # Written as already expired for normal ("live-fresh") reads, but
        # still well inside cache_stale_grace_places -- simulates a place
        # someone successfully searched a while ago.
        cache_set(db, key, [real_place.model_dump()], ttl_seconds=-settings.cache_ttl_places)

        monkeypatch.setattr(OverpassProvider, "nearby", _always_fails)

        meta: dict = {}
        places = asyncio.run(places_service.nearby_places(db, lat, lon, radius, [], meta=meta))

        assert len(places) == 1
        assert places[0].name == "Old But Real Fort"
        assert places[0].id == "node/777"
        assert "stale_seconds" in meta, "must tell the caller this was a fallback, not a live result"
        assert 0 < meta["stale_seconds"] < settings.cache_stale_grace_places
    finally:
        db.close()


def test_nearby_places_still_raises_when_cache_entry_is_older_than_grace_window(monkeypatch):
    """The fallback is bounded, not unlimited -- a years-old cache entry must
    not be handed out as if it were still usable."""
    init_db()
    settings = get_settings()
    db = SessionLocal()
    try:
        lat, lon, radius = 21.111, 82.222, 4000
        key = places_service._key("nearby", f"{lat:.4f}", f"{lon:.4f}", str(radius), "")
        ancient_place = _place("Ancient Cache Entry", "node/1", lat, lon)
        too_old_ttl = -(settings.cache_stale_grace_places + settings.cache_ttl_places + 3600)
        cache_set(db, key, [ancient_place.model_dump()], ttl_seconds=too_old_ttl)

        monkeypatch.setattr(OverpassProvider, "nearby", _always_fails)

        with pytest.raises(ProviderError):
            asyncio.run(places_service.nearby_places(db, lat, lon, radius, []))
    finally:
        db.close()


def test_nearby_places_still_raises_when_nothing_cached_at_all(monkeypatch):
    """A location nobody has ever successfully searched before still gets an
    honest failure when every mirror is down -- the fallback can't invent
    data that was never fetched."""
    init_db()
    db = SessionLocal()
    try:
        monkeypatch.setattr(OverpassProvider, "nearby", _always_fails)
        with pytest.raises(ProviderError):
            asyncio.run(places_service.nearby_places(db, 1.0001, 2.0002, 4000, []))
    finally:
        db.close()


def test_places_nearby_endpoint_marks_stale_response_via_header(monkeypatch):
    """End-to-end: the actual /api/places/nearby route a browser hits returns
    200 with real (older) data plus an honest freshness header, instead of a
    503, when this exact fallback condition applies."""
    init_db()
    settings = get_settings()
    lat, lon, radius = 33.3333, 44.4444, 3000
    key = places_service._key("nearby", f"{lat:.4f}", f"{lon:.4f}", str(radius), "")
    cached_place = _place("Cached Palace", "node/900", lat, lon)

    db = SessionLocal()
    try:
        cache_set(db, key, [cached_place.model_dump()], ttl_seconds=-settings.cache_ttl_places)
    finally:
        db.close()

    monkeypatch.setattr(OverpassProvider, "nearby", _always_fails)

    with TestClient(app) as client:
        resp = client.get("/api/places/nearby", params={"lat": lat, "lon": lon, "radius_meters": radius})
        assert resp.status_code == 200
        assert resp.headers.get("X-Sarthi-Data-Freshness") == "cached-stale"
        assert int(resp.headers["X-Sarthi-Cache-Age-Seconds"]) > 0
        body = resp.json()
        assert len(body) == 1
        assert body[0]["name"] == "Cached Palace"


def test_places_nearby_endpoint_returns_503_when_no_fallback_available(monkeypatch):
    """The honest-failure path must still work exactly as before for a truly
    cold, never-before-fetched location -- this fix narrows the gap, it
    doesn't paper over every possible outage."""
    init_db()
    monkeypatch.setattr(OverpassProvider, "nearby", _always_fails)

    with TestClient(app) as client:
        resp = client.get("/api/places/nearby", params={"lat": 9.9999, "lon": 8.8888, "radius_meters": 3000})
        assert resp.status_code == 503
        assert "temporarily unavailable" in resp.json()["detail"].lower()
        assert "X-Sarthi-Data-Freshness" not in resp.headers


# ---------------------------------------------------------------------------
# Radius Strategy (2026-09-16 real-world report: searching "Amritsar, Punjab,
# India" showed only 1 real place). Part of that report's root cause was a
# genuinely sparse resolved coordinate, but the search itself also never
# tried a wider radius before giving up, and never told the caller when it
# did widen -- these tests cover the escalation added to fix that half of it
# (see app/services/places_service.py: _RADIUS_FALLBACK_MULTIPLIERS).
# ---------------------------------------------------------------------------

def test_nearby_places_escalates_radius_when_sparse(monkeypatch):
    init_db()
    db = SessionLocal()
    try:
        lat, lon = 55.1110, 66.2220
        calls = []

        async def fake_nearby(self, latitude, longitude, radius_meters, categories):
            calls.append(radius_meters)
            if radius_meters <= 3000:
                return [_place("Only Nearby Place", "node/1", latitude, longitude)]
            # A wider radius genuinely turns up more real places -- e.g. this
            # spot is at the edge of a sparsely-mapped area.
            return [_place(f"Place {i}", f"node/{i}", latitude + i * 0.001, longitude) for i in range(8)]

        monkeypatch.setattr(OverpassProvider, "nearby", fake_nearby)

        meta: dict = {}
        places = asyncio.run(places_service.nearby_places(db, lat, lon, 3000, [], meta=meta))

        assert calls == [3000, 6000], "must stop widening as soon as a tier is no longer sparse, not walk every tier regardless"
        assert len(places) == 8
        assert meta["requested_radius_meters"] == 3000
        assert meta["effective_radius_meters"] == 6000, "must report the radius actually used, not the originally-requested one"
    finally:
        db.close()


def test_nearby_places_stops_at_max_radius_even_if_still_sparse(monkeypatch):
    """The escalation is bounded -- a genuinely remote spot with almost no
    OSM data anywhere nearby must not cause runaway widening past the
    endpoint's own documented radius cap."""
    init_db()
    db = SessionLocal()
    try:
        lat, lon = 60.5000, 70.6000
        calls = []

        async def always_sparse(self, latitude, longitude, radius_meters, categories):
            calls.append(radius_meters)
            return [_place("Lone Place", "node/1", latitude, longitude)]

        monkeypatch.setattr(OverpassProvider, "nearby", always_sparse)

        meta: dict = {}
        places = asyncio.run(places_service.nearby_places(db, lat, lon, 5000, [], meta=meta))

        assert calls == [5000, 10000, 15000], "should try all three tiers, capped at the 15km max, then honestly give up widening"
        assert len(places) == 1
        assert meta["effective_radius_meters"] == 15000
    finally:
        db.close()


def test_places_nearby_endpoint_exposes_radius_headers(monkeypatch):
    """The actual radius used must reach the frontend so it can say so
    honestly (spec: "must clearly indicate the ACTUAL radius used")."""
    init_db()

    async def fake_nearby(self, latitude, longitude, radius_meters, categories):
        return [_place("Some Place", "node/55", latitude, longitude)]

    monkeypatch.setattr(OverpassProvider, "nearby", fake_nearby)

    with TestClient(app) as client:
        resp = client.get("/api/places/nearby", params={"lat": 1.2340, "lon": 5.6780, "radius_meters": 2000})
        assert resp.status_code == 200
        assert resp.headers.get("X-Sarthi-Requested-Radius-Meters") == "2000"
        # Never non-sparse (always 1 place) -- escalates through every tier: 2000 -> 4000 -> 6000.
        assert resp.headers.get("X-Sarthi-Effective-Radius-Meters") == "6000"
