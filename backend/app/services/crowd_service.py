"""
Tourism Pressure Engine (SIH PS26204 -- Crowd Monitoring & Tourism Pressure
Engine). See app/integrations/crowd.py for the data-honesty rationale.

Combines, per destination:
  - seasonal_pressure   -- curated peak/shoulder/off-season lookup (always available)
  - demand_signal       -- how many times SARTHI'S OWN users have looked this
                            destination up through this app (always available,
                            even when the honest answer is "zero so far")
  - place_density       -- live OpenStreetMap tourism-place count nearby, via
                            the EXISTING places_service/OverpassProvider (so
                            this shares the same cache and never issues an
                            extra Overpass call beyond what Explore already
                            makes for the same location)
  - weather_suitability -- live Open-Meteo outdoor suitability, via the
                            EXISTING weather_service
  - event_pressure      -- live nearby event count via the EXISTING
                            events_service, only when Ticketmaster is configured

Each component is independently optional: if a live call fails, that
component is marked unavailable and the composite score is rebalanced across
whatever remains (never silently filled with a guess). If too few components
survive to produce a meaningful number, the whole response honestly reports
"no reliable estimate" instead of a number (spec: crowd-engine test case
"Missing crowd data").
"""
import hashlib
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.base import ProviderError
from app.integrations.crowd import EstimatedCrowdProvider
from app.models.crowd_demand import DestinationDemandLog
from app.schemas.crowd import CrowdComponent, CrowdPressureResponse
from app.services import events_service, places_service, weather_service

_provider = EstimatedCrowdProvider()

# Below this combined weight, the surviving components are too thin (usually
# both live signals -- place density and weather -- failed at once, e.g. a
# genuine network outage) to call the result a reliable planning estimate.
_MIN_RELIABLE_WEIGHT = 0.45

_PLACE_DENSITY_SOFT_CAP = 60  # ~this many mapped tourism-related OSM places within radius => 100
_DENSITY_RADIUS_M = 4000  # matches Explore's own nearby-places radius, so the Overpass cache is shared


def _status_for(index: int) -> str:
    if index <= 25:
        return "LOW"
    if index <= 50:
        return "MODERATE"
    if index <= 75:
        return "HIGH"
    return "VERY HIGH"


def _bucket_key(latitude: float, longitude: float) -> str:
    # ~1.1km grid cells at Indian latitudes -- coarse enough that repeat
    # lookups of "the same place" actually accumulate into one demand count.
    raw = f"{round(latitude, 2)},{round(longitude, 2)}"
    return hashlib.sha1(raw.encode()).hexdigest()[:32]


def _record_and_get_demand(db: Session, latitude: float, longitude: float) -> int:
    key = _bucket_key(latitude, longitude)
    row = db.execute(select(DestinationDemandLog).where(DestinationDemandLog.bucket_key == key)).scalar_one_or_none()
    now = time.time()
    if row is None:
        row = DestinationDemandLog(bucket_key=key, query_count=1, last_queried_at=now)
        db.add(row)
    else:
        row.query_count += 1
        row.last_queried_at = now
    db.commit()
    return row.query_count


def _demand_score(query_count: int) -> float:
    # Saturating curve -- documented, not fabricated precision. A prototype
    # with little real traffic will (honestly) show low numbers here.
    return min(100.0, query_count * 8.0)


async def get_pressure(db: Session, destination_label: str, latitude: float, longitude: float) -> CrowdPressureResponse:
    components: dict[str, CrowdComponent] = {}

    # --- Seasonal pressure (always available -- pure lookup, no network) ---
    seasonal_value, seasonal_label, seasonal_type = _provider.seasonal_pressure(
        destination_label, datetime.now(timezone.utc)
    )
    components["seasonal_pressure"] = CrowdComponent(
        value=seasonal_value, weight=0.35, used=True, data_type=seasonal_type, label=seasonal_label,
    )

    # --- Sarthi demand signal (always available -- local DB, no network) ---
    try:
        query_count = _record_and_get_demand(db, latitude, longitude)
        demand_value = _demand_score(query_count)
        demand_note = (
            f"Looked up {query_count} time(s) by Sarthi users so far"
            if query_count > 1 else "First recorded Sarthi lookup for this area"
        )
        components["demand_signal"] = CrowdComponent(
            value=demand_value, weight=0.10, used=True, data_type="estimated",
            label="Sarthi Demand Signal", note=demand_note,
        )
    except Exception:
        # DB hiccup -- degrade gracefully rather than failing the whole request.
        components["demand_signal"] = CrowdComponent(
            value=None, weight=0.10, used=False, data_type="unavailable",
            label="Sarthi Demand Signal", note="Could not read Sarthi's own usage data right now",
        )

    # --- Live place density (Overpass, via the existing places_service -- shares its cache) ---
    place_count = None
    try:
        nearby = await places_service.nearby_places(db, latitude, longitude, _DENSITY_RADIUS_M, [])
        place_count = len(nearby)
        density_value = min(100.0, (place_count / _PLACE_DENSITY_SOFT_CAP) * 100.0)
        components["place_density"] = CrowdComponent(
            value=density_value, weight=0.30, used=True, data_type="estimated",
            label="Tourism Place Density",
            note=f"{place_count} mapped tourism-related OpenStreetMap places within {_DENSITY_RADIUS_M / 1000:.0f} km "
                 "(attractions, museums, historic/religious sites, hotels, restaurants, cafes, shopping, parks) "
                 "-- a density signal, not an actual visitor count",
        )
    except ProviderError as exc:
        components["place_density"] = CrowdComponent(
            value=None, weight=0.30, used=False, data_type="unavailable",
            label="Tourism Place Density", note=f"OpenStreetMap place data unavailable ({exc.detail})",
        )

    # --- Weather suitability (Open-Meteo, via the existing weather_service) ---
    weather_suitability_label = None
    try:
        weather = await weather_service.get_weather(db, latitude, longitude)
        weather_suitability_label = weather.outdoor_suitability.upper()
        weather_value = {"good": 68.0, "fair": 50.0, "poor": 28.0}.get(weather.outdoor_suitability, 50.0)
        components["weather_suitability"] = CrowdComponent(
            value=weather_value, weight=0.15, used=True, data_type="estimated",
            label="Weather Suitability",
            note=f"Current outdoor visit suitability: {weather_suitability_label} "
                 f"({round(weather.current.temperature_c)}°C, {weather.current.condition_text}). "
                 "This nudges pressure only mildly -- weather is reported separately as visit suitability, "
                 "never treated as a crowd count.",
        )
    except ProviderError as exc:
        components["weather_suitability"] = CrowdComponent(
            value=None, weight=0.15, used=False, data_type="unavailable",
            label="Weather Suitability", note=f"Live weather unavailable ({exc.detail})",
        )

    # --- Event pressure (Ticketmaster, only if configured) ---
    try:
        event_res = await events_service.search_events(db, latitude, longitude, radius_km=20)
        if not event_res.configured:
            components["event_pressure"] = CrowdComponent(
                value=None, weight=0.10, used=False, data_type="unavailable",
                label="Event Pressure", note="Event provider (Ticketmaster) not configured",
            )
        else:
            n = len(event_res.events)
            event_value = 20.0 if n == 0 else min(100.0, 40.0 + n * 15.0)
            components["event_pressure"] = CrowdComponent(
                value=event_value, weight=0.10, used=True, data_type="estimated",
                label="Event Pressure",
                note=f"{n} live Ticketmaster event(s) found within 20 km" if n else "No live events found nearby",
            )
    except Exception:
        components["event_pressure"] = CrowdComponent(
            value=None, weight=0.10, used=False, data_type="unavailable",
            label="Event Pressure", note="Event data unavailable",
        )

    # --- Combine available components, rebalancing weight across what's left ---
    available = {k: c for k, c in components.items() if c.used and c.value is not None}
    total_weight = sum(c.weight for c in available.values())
    live_signal_present = any(k in available for k in ("place_density", "weather_suitability", "event_pressure"))

    if not available or total_weight < _MIN_RELIABLE_WEIGHT or not live_signal_present:
        return CrowdPressureResponse(
            destination=destination_label,
            latitude=latitude, longitude=longitude,
            pressure_index=None, status=None, data_type="unavailable",
            components=components,
            explanation=[],
            weather_suitability=weather_suitability_label,
            message="No reliable tourism-pressure estimate available right now "
                    "(too many live signals -- place data, weather -- are currently unreachable).",
        )

    weighted_sum = sum(c.value * (c.weight / total_weight) for c in available.values())
    pressure_index = max(0, min(100, round(weighted_sum)))
    status = _status_for(pressure_index)

    explanation = [c.note or c.label for c in available.values()]

    return CrowdPressureResponse(
        destination=destination_label,
        latitude=latitude, longitude=longitude,
        pressure_index=pressure_index, status=status, data_type="estimated",
        # How much of the composite's intended weight was actually backed by
        # a real, available signal this call (1.0 = every component came
        # through; lower when e.g. weather or events were unreachable and the
        # remaining components were reweighted to fill the gap).
        confidence=round(min(1.0, total_weight), 2),
        components=components,
        explanation=explanation,
        weather_suitability=weather_suitability_label,
        message="Estimated Tourism Pressure Index -- a planning signal built from seasonality, live OpenStreetMap "
                "place density, Sarthi's own usage, live weather and (when configured) live events. "
                "Not a live visitor count, CCTV feed, mobile-location panel or government statistic.",
    )
