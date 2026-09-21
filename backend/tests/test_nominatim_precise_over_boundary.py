"""
Tests for NominatimProvider._prefer_precise_over_boundary (real, reproduced
bug, 2026-09-16): searching "Amritsar, Punjab, India" resolved to an
ADMINISTRATIVE boundary result (the district/tehsil polygon, centroid ~18km
from the actual city) instead of the actual city point, which made every
downstream call (nearby places, Tourism Pressure, the Flow Rebalancer)
correctly and honestly analyze the wrong, genuinely rural spot.

The fixture payload below mirrors the real cached Nominatim response
recovered from the live incident (see the investigation notes in
app/integrations/nominatim.py) -- same display names, coordinates, types and
importance scores, trimmed to only the fields the provider actually reads.

This is deliberately tested with more than one place name (Amritsar AND a
region-only search AND a synthetic "prominent boundary" case) to prove the
fix is a general re-ranking rule, not anything specific to Amritsar --
per the project's explicit "no destination-specific hardcoding" requirement,
there is nothing in nominatim.py that even mentions a specific city by name
in its logic (the Amritsar mentions there are incident-history comments only).

No real network calls are made -- httpx.AsyncClient is replaced with a fake
that returns canned JSON, matching the pattern already used in
test_overpass_hedging.py.
"""
import asyncio

import httpx

from app.integrations.nominatim import NominatimProvider


class _FakeResponse:
    def __init__(self, json_data):
        self._json = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


def _fake_client_returning(payload):
    class _FakeClient:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None, headers=None):
            return _FakeResponse(payload)

    return _FakeClient


# Raw-ordered with the ADMINISTRATIVE result first, exactly as recovered from
# the live incident, to prove the fix actually reorders rather than merely
# passing through whatever Nominatim happened to return.
_AMRITSAR_PAYLOAD = [
    {
        "display_name": "Amritsar, Punjab, India",
        "lat": "31.7685759", "lon": "74.8315603",
        "type": "administrative", "importance": 0.5399602457890736,
        "boundingbox": ["31.5", "32.0", "74.6", "75.1"],
    },
    {
        "display_name": "Amritsar, Amritsar I Tahsil, Amritsar, Punjab, 143001, India",
        "lat": "31.6356659", "lon": "74.8787496",
        "type": "city", "importance": 0.5740136743893479,
        "boundingbox": ["31.6", "31.7", "74.8", "74.9"],
    },
    {
        "display_name": "Amritsar, Punjab, India",
        "lat": "31.5000", "lon": "75.0000",
        "type": "county", "importance": 0.24,
        "boundingbox": ["31.0", "32.0", "74.5", "75.5"],
    },
]


def test_precise_city_ranked_ahead_of_administrative_boundary_same_name(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _fake_client_returning(_AMRITSAR_PAYLOAD))

    provider = NominatimProvider()
    # limit=1 deliberately -- this is the real Enter-to-search path (a bare
    # single-result request); the fix must still see and prefer the more
    # precise result even though the caller only wants one back.
    results = asyncio.run(provider.search("Amritsar, Punjab, India", limit=1))

    assert len(results) == 1
    assert results[0].place_type == "city"
    assert round(results[0].latitude, 4) == 31.6357, "must resolve to the actual city, not the ~18km-away district centroid"
    assert round(results[0].longitude, 4) == 74.8787


def test_administrative_result_kept_when_no_more_precise_alternative_exists(monkeypatch):
    """A genuine region/state search (e.g. "Kerala", "Rajasthan") has no
    more-precise same-name alternative on offer -- the administrative
    boundary IS the best available point and must not be dropped or
    demoted."""
    kerala_payload = [
        {
            "display_name": "Kerala, India", "lat": "10.8505", "lon": "76.2711",
            "type": "administrative", "importance": 0.75,
            "boundingbox": ["8.0", "13.0", "74.0", "77.5"],
        },
    ]
    monkeypatch.setattr(httpx, "AsyncClient", _fake_client_returning(kerala_payload))

    provider = NominatimProvider()
    results = asyncio.run(provider.search("Kerala", limit=1))

    assert len(results) == 1
    assert results[0].place_type == "administrative"
    assert results[0].display_name == "Kerala, India"


def test_prominent_boundary_not_demoted_by_obscure_same_name_precise_result(monkeypatch):
    """A genuinely obscure, low-importance same-name settlement/suburb must
    never bump a well-known, clearly-more-prominent administrative region --
    the demotion only applies when the precise alternative is at least
    comparably important."""
    payload = [
        {
            "display_name": "Rajasthan, India", "lat": "27.0", "lon": "74.0",
            "type": "administrative", "importance": 0.85,
            "boundingbox": ["23.0", "30.0", "69.0", "78.0"],
        },
        {
            "display_name": "Rajasthan Colony, Some City, India", "lat": "26.0", "lon": "75.0",
            "type": "suburb", "importance": 0.1,
            "boundingbox": ["25.9", "26.1", "74.9", "75.1"],
        },
    ]
    monkeypatch.setattr(httpx, "AsyncClient", _fake_client_returning(payload))

    provider = NominatimProvider()
    results = asyncio.run(provider.search("Rajasthan", limit=5))

    assert results[0].place_type == "administrative"
    assert results[0].display_name == "Rajasthan, India"
