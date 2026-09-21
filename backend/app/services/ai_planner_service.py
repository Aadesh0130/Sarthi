"""
AI-reasoned, real-data-grounded trip generation (master-upgrade spec
sections 13/14/21/22).

The model (Gemini or OpenAI, whichever AI_PROVIDER selects -- same
provider-agnostic pattern as ai_service.py) is given:
  - real nearby places, already retrieved live from OpenStreetMap
    (places_service, same provider/cache Explore uses)
  - real current weather (weather_service)
  - whether events/hotels providers are configured (for honest framing --
    full hotel/event integration into the plan is a documented limitation,
    see README)

and asked to REASON over that retrieved data: pick which places best fit the
traveller's interests/budget/pace, in what order, across how many days.

Critically, the model's output is never trusted verbatim. Every stop it
proposes is checked against the actual retrieved candidate list by
`place_id`; a `place_id` the model didn't actually see is dropped rather
than shown as a confirmed recommendation. Every displayed field (name,
category, coordinates, address) is then re-populated from Sarthi's own
retrieved Place object, not from whatever text the model produced -- so
even a hallucinated name/address attached to a *real* id can't leak through.
"""
import json
import math
import re

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.base import AIProvider, ProviderError
from app.integrations.gemini import GeminiProvider
from app.integrations.openai_provider import OpenAIProvider
from app.schemas.ai_plan import AIPlanDay, AIPlanRequest, AIPlanResponse, AIPlanStop, AIReplanRequest
from app.schemas.place import Place
from app.services import events_service, geocoding_service, hotels_service, places_service, weather_service

PACE_GUIDANCE = {
    "relaxed": "about 2 stops per day, unhurried",
    "balanced": "about 3 stops per day",
    "packed": "4-5 stops per day, efficiently ordered",
}

# A single hop longer than this within one day is flagged, not blocked --
# the model has no real routing data to reason about travel time precisely
# (full OSRM per-hop integration is a documented limitation; the existing
# manual real-trip-builder "Optimize route" button already does real OSRM
# routing separately and is untouched by this feature).
LONG_HOP_KM = 25.0


def _get_provider() -> AIProvider | None:
    settings = get_settings()
    if not settings.ai_configured:
        return None
    return GeminiProvider() if settings.ai_provider.lower() == "gemini" else OpenAIProvider()


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _extract_json(text: str) -> dict | None:
    """Models often wrap JSON in ```json fences or add a stray sentence --
    pull out the first {...} block rather than failing outright."""
    if not text:
        return None
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    candidate = fence.group(1).strip() if fence else text
    try:
        return json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        pass
    # last resort: widest {...} span
    start, end = candidate.find("{"), candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(candidate[start : end + 1])
        except (json.JSONDecodeError, ValueError):
            return None
    return None


def _build_prompt(
    destination_label: str, candidates: list[Place], weather_summary: str,
    req_days: int, req_interests: list[str], req_pace: str, req_budget: str,
    req_travelers: int, req_avoid_crowds: bool, replan_instruction: str | None, previous_plan_summary: str | None,
) -> str:
    candidate_lines = "\n".join(
        f'- id="{p.id}" name="{p.name}" category={p.category} distance_m={round(p.distance_meters or 0)}'
        + (f' tags={",".join(k for k in (p.raw_tags or {}) if k in ("cuisine", "religion", "historic", "tourism"))}' if p.raw_tags else "")
        for p in candidates
    )
    base = f"""You are planning a {req_days}-day trip to {destination_label} for {req_travelers} traveller(s).
Budget style: {req_budget}. Pace: {req_pace} ({PACE_GUIDANCE.get(req_pace, "a reasonable number of stops per day")}).
Interests: {", ".join(req_interests) if req_interests else "no specific interests given -- use broad appeal"}.
Avoid crowded places: {"yes, prefer quieter options" if req_avoid_crowds else "no particular preference"}.
Current weather: {weather_summary}

CANDIDATE PLACES (the ONLY places you may use -- you must not invent any place or use any id not listed here):
{candidate_lines}
"""
    if replan_instruction and previous_plan_summary:
        base += f"""
The traveller already has this plan and wants a change:
{previous_plan_summary}

Requested change: "{replan_instruction}"

Produce a REVISED full plan honoring this request, still using ONLY the candidate place ids above.
"""
    base += """
Respond with ONLY valid JSON (no markdown fences, no commentary), in exactly this shape:
{
  "days": [
    {
      "day": 1,
      "title": "short theme for the day",
      "stops": [
        {"place_id": "<one of the candidate ids above, EXACTLY as given>", "time_of_day": "Morning", "reason": "one short concrete sentence"}
      ]
    }
  ],
  "notes": "any brief overall note, or empty string"
}
Only use place_id values copied exactly from the candidate list. Do not include a place_id that is not listed above. Do not invent a name, address or coordinate -- Sarthi already knows those; only choose which real places to visit, in what order, and why.
"""
    return base


async def _run_model(provider: AIProvider, prompt: str) -> tuple[dict | None, str | None]:
    try:
        result = await provider.chat("You are a careful, grounded travel-planning assistant.", [{"role": "user", "content": prompt}], [])
    except ProviderError as exc:
        return None, f"The AI planner is temporarily unavailable ({exc.detail})."
    parsed = _extract_json(result.text or "")
    if parsed is None:
        return None, "The AI planner returned a response that couldn't be parsed as a plan -- please try again."
    return parsed, None


def _validate_and_hydrate(parsed: dict, candidates_by_id: dict[str, Place]) -> tuple[list[AIPlanDay], int, str | None]:
    days: list[AIPlanDay] = []
    removed = 0
    for d in parsed.get("days", []):
        stops: list[AIPlanStop] = []
        prev_place: Place | None = None
        long_hop_note = None
        for s in d.get("stops", []):
            pid = s.get("place_id")
            place = candidates_by_id.get(pid)
            if place is None:
                removed += 1
                continue  # never show a stop the model invented or mis-cited
            if prev_place is not None:
                km = _haversine_km(prev_place.latitude, prev_place.longitude, place.latitude, place.longitude)
                if km > LONG_HOP_KM:
                    long_hop_note = f"One hop this day (~{round(km)} km straight-line) may need significant travel time -- consider checking a real route."
            prev_place = place
            stops.append(AIPlanStop(
                place_id=place.id, name=place.name, category=place.category,
                latitude=place.latitude, longitude=place.longitude, address=place.address,
                distance_meters=place.distance_meters,
                time_of_day=str(s.get("time_of_day") or "Flexible"),
                reason=str(s.get("reason") or "").strip() or "Selected as a good fit for this trip.",
                source=place.source,
            ))
        if stops:
            days.append(AIPlanDay(day=int(d.get("day") or len(days) + 1), title=str(d.get("title") or f"Day {len(days) + 1}"), stops=stops, long_hop_warning=long_hop_note))
    return days, removed, parsed.get("notes") or None


async def generate_trip(db: Session, req: AIPlanRequest) -> AIPlanResponse:
    provider = _get_provider()
    if provider is None:
        settings = get_settings()
        env_var = "GEMINI_API_KEY" if settings.ai_provider.lower() == "gemini" else "OPENAI_API_KEY"
        return AIPlanResponse(configured=False, message=f"The AI trip planner isn't configured -- set {env_var} in backend/.env.")

    geocoded = await geocoding_service.geocode_search(db, req.destination_query, limit=1)
    if not geocoded:
        return AIPlanResponse(configured=True, provider=provider.name, message=f"Couldn't find \"{req.destination_query}\" -- try a different spelling or a nearby larger town.")
    dest = geocoded[0]

    try:
        candidates = await places_service.nearby_places(db, dest.latitude, dest.longitude, 5000, [])
    except ProviderError as exc:
        return AIPlanResponse(configured=True, provider=provider.name, destination=dest.display_name, latitude=dest.latitude, longitude=dest.longitude,
                               message=f"Real place data is temporarily unavailable ({exc.detail}) -- can't ground an AI plan without it. Try again shortly.")
    if not candidates:
        return AIPlanResponse(configured=True, provider=provider.name, destination=dest.display_name, latitude=dest.latitude, longitude=dest.longitude,
                               message="No mapped tourist places were found near this destination in OpenStreetMap, so there is nothing real to plan from.")
    candidates = candidates[:50]
    candidates_by_id = {p.id: p for p in candidates}

    weather_summary = "unavailable"
    try:
        weather = await weather_service.get_weather(db, dest.latitude, dest.longitude)
        weather_summary = f"{weather.current.condition_text}, {round(weather.current.temperature_c)}C, outdoor suitability: {weather.outdoor_suitability}"
    except ProviderError:
        pass

    events_configured = False
    try:
        ev = await events_service.search_events(db, dest.latitude, dest.longitude)
        events_configured = ev.configured
    except ProviderError:
        pass
    hotels_configured = get_settings().hotels_configured

    prompt = _build_prompt(dest.display_name, candidates, weather_summary, req.days, req.interests, req.pace, req.budget, req.travelers, req.avoid_crowds, None, None)
    parsed, error = await _run_model(provider, prompt)
    if error:
        return AIPlanResponse(configured=True, provider=provider.name, destination=dest.display_name, latitude=dest.latitude, longitude=dest.longitude, message=error)

    days, removed, notes = _validate_and_hydrate(parsed, candidates_by_id)
    if not days:
        return AIPlanResponse(configured=True, provider=provider.name, destination=dest.display_name, latitude=dest.latitude, longitude=dest.longitude,
                               message="The AI planner didn't produce any verifiable stops from the real places available here -- try again or a different destination.")

    return AIPlanResponse(
        configured=True, provider=provider.name, destination=dest.display_name, latitude=dest.latitude, longitude=dest.longitude,
        days=days, removed_unverified_count=removed, weather_note=weather_summary,
        events_configured=events_configured, hotels_configured=hotels_configured, raw_model_notes=notes,
    )


async def replan_trip(db: Session, req: AIReplanRequest) -> AIPlanResponse:
    provider = _get_provider()
    if provider is None:
        settings = get_settings()
        env_var = "GEMINI_API_KEY" if settings.ai_provider.lower() == "gemini" else "OPENAI_API_KEY"
        return AIPlanResponse(configured=False, message=f"The AI trip planner isn't configured -- set {env_var} in backend/.env.")

    if req.latitude is not None and req.longitude is not None:
        lat, lon, label = req.latitude, req.longitude, req.destination_query
    else:
        geocoded = await geocoding_service.geocode_search(db, req.destination_query, limit=1)
        if not geocoded:
            return AIPlanResponse(configured=True, provider=provider.name, message=f"Couldn't find \"{req.destination_query}\".")
        lat, lon, label = geocoded[0].latitude, geocoded[0].longitude, geocoded[0].display_name

    try:
        candidates = (await places_service.nearby_places(db, lat, lon, 5000, []))[:50]
    except ProviderError as exc:
        return AIPlanResponse(configured=True, provider=provider.name, destination=label, latitude=lat, longitude=lon,
                               message=f"Real place data is temporarily unavailable ({exc.detail}).")
    candidates_by_id = {p.id: p for p in candidates}

    weather_summary = "unavailable"
    try:
        weather = await weather_service.get_weather(db, lat, lon)
        weather_summary = f"{weather.current.condition_text}, {round(weather.current.temperature_c)}C, outdoor suitability: {weather.outdoor_suitability}"
    except ProviderError:
        pass

    prev_summary = "; ".join(
        f"Day {d.day} ({d.title}): " + ", ".join(s.name for s in d.stops)
        for d in req.previous_plan.days
    ) or "no previous plan"

    prompt = _build_prompt(label, candidates, weather_summary, len(req.previous_plan.days) or 3, req.interests, req.pace, req.budget, req.travelers, req.avoid_crowds, req.instruction, prev_summary)
    parsed, error = await _run_model(provider, prompt)
    if error:
        return AIPlanResponse(configured=True, provider=provider.name, destination=label, latitude=lat, longitude=lon, message=error)

    days, removed, notes = _validate_and_hydrate(parsed, candidates_by_id)
    if not days:
        return AIPlanResponse(configured=True, provider=provider.name, destination=label, latitude=lat, longitude=lon,
                               message="The AI planner couldn't produce a verifiable revised plan -- try rephrasing the request.")

    return AIPlanResponse(
        configured=True, provider=provider.name, destination=label, latitude=lat, longitude=lon,
        days=days, removed_unverified_count=removed, weather_note=weather_summary,
        events_configured=req.previous_plan.events_configured, hotels_configured=req.previous_plan.hotels_configured, raw_model_notes=notes,
    )
