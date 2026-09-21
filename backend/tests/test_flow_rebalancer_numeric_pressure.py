"""
Direct, white-box tests for flow_rebalancer_service._score_candidate's
pressure filter (real, reported bug, 2026-09-16): the filter used to compare
only STATUS BUCKETS (LOW/MODERATE/HIGH/VERY HIGH), so a candidate at
HIGH-58 was wrongly excluded against a requested destination at HIGH-74 --
a genuine 16-point relief -- purely because both share the "HIGH" bucket.
The user's own bug report used exactly this example.

These call _score_candidate directly (rather than going through the full
/api/flow/rebalance + real crowd_service.get_pressure pipeline the way
test_flow_rebalancer.py does) because the real Tourism Pressure Index
formula's own weighting/caps make it awkward to reliably manufacture two
*specific* same-bucket index values (74 and 58) end-to-end -- this is a
deliberate, narrower unit test of just the comparison logic itself, with
crowd_service.get_pressure mocked to return exact, controlled index values.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_sarthi.db")

from app.schemas.crowd import CrowdPressureResponse
from app.schemas.weather import CurrentWeather, WeatherResponse
from app.services import crowd_service, flow_rebalancer_service as svc, places_service, weather_service


def _pressure(label, lat, lon, index, status):
    return CrowdPressureResponse(destination=label, latitude=lat, longitude=lon, pressure_index=index, status=status, data_type="estimated")


def _candidate(lat=10.5, lon=20.5, distance_km=40.0):
    return {
        "name": "Candidate Town", "state": "State", "latitude": lat, "longitude": lon,
        "source": "osm-settlement", "tags": [], "hidden_gem": False, "sustainability": None,
        "_distance_km": distance_km,
    }


def _install_fakes(monkeypatch, candidate_pressure):
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


def test_same_status_bucket_candidate_with_meaningful_relief_is_kept(monkeypatch):
    """The user's exact reported example: requested HIGH-74, candidate
    HIGH-58 -- both HIGH, but a genuine 16-point relief -- must be eligible."""
    requested_pressure = _pressure("Requested Town", 10.0, 20.0, 74, "HIGH")
    candidate_pressure = _pressure("Candidate Town, State", 10.5, 20.5, 58, "HIGH")
    _install_fakes(monkeypatch, candidate_pressure)

    alt = asyncio.run(svc._score_candidate(None, {}, requested_pressure, [], _candidate()))

    assert alt is not None, "a same-bucket candidate with a meaningful numeric pressure relief must not be excluded"
    assert alt.tourism_pressure.pressure_index == 58


def test_very_high_vs_high_with_relief_is_kept(monkeypatch):
    """A second, unrelated example from the spec: VERY HIGH 82 vs HIGH 68
    must clearly be eligible (different buckets AND a numeric improvement,
    so this must never regress even under the new logic)."""
    requested_pressure = _pressure("Requested Town", 11.0, 21.0, 82, "VERY HIGH")
    candidate_pressure = _pressure("Candidate Town, State", 11.5, 21.5, 68, "HIGH")
    _install_fakes(monkeypatch, candidate_pressure)

    alt = asyncio.run(svc._score_candidate(None, {}, requested_pressure, [], _candidate(11.5, 21.5)))

    assert alt is not None


def test_same_status_bucket_candidate_without_meaningful_relief_is_still_excluded(monkeypatch):
    """Not "always allow same bucket" -- a candidate only trivially lower (or
    not lower at all) must still be filtered out; this is noise, not relief."""
    requested_pressure = _pressure("Requested Town", 12.0, 22.0, 60, "HIGH")
    candidate_pressure = _pressure("Candidate Town, State", 12.5, 22.5, 59, "HIGH")
    _install_fakes(monkeypatch, candidate_pressure)

    alt = asyncio.run(svc._score_candidate(None, {}, requested_pressure, [], _candidate(12.5, 22.5)))

    assert alt is None


def test_status_fallback_used_only_when_numeric_index_unavailable(monkeypatch):
    """When the candidate's numeric index genuinely isn't available, fall
    back to the coarser status-bucket rank rather than treating the
    comparison as impossible (an unavailable index isn't automatically
    "better than requested" -- same-bucket-or-worse is still excluded)."""
    requested_pressure = _pressure("Requested Town", 13.0, 23.0, 70, "HIGH")
    candidate_pressure = CrowdPressureResponse(
        destination="Candidate Town", latitude=13.5, longitude=23.5,
        pressure_index=None, status="HIGH", data_type="estimated",
    )
    _install_fakes(monkeypatch, candidate_pressure)

    alt = asyncio.run(svc._score_candidate(None, {}, requested_pressure, [], _candidate(13.5, 23.5)))

    assert alt is None, "same-status HIGH vs HIGH with no numeric candidate index must still fall back to status-rank exclusion"


def test_unavailable_candidate_pressure_is_not_excluded_on_that_basis_alone(monkeypatch):
    """Data honesty cuts both ways (spec: "never reject a candidate solely
    because pressure is unavailable") -- a candidate with NO pressure signal
    at all (neither index nor status) must not be excluded by this filter,
    though it may still score lower on other factors."""
    requested_pressure = _pressure("Requested Town", 14.0, 24.0, 70, "HIGH")
    candidate_pressure = CrowdPressureResponse(
        destination="Candidate Town", latitude=14.5, longitude=24.5,
        pressure_index=None, status=None, data_type="unavailable",
        message="No reliable tourism-pressure estimate available right now.",
    )
    _install_fakes(monkeypatch, candidate_pressure)

    alt = asyncio.run(svc._score_candidate(None, {}, requested_pressure, [], _candidate(14.5, 24.5)))

    assert alt is not None
