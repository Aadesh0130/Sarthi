"""
AI photo-based place identification (master-upgrade spec sections 15/16).

Pipeline: uploaded photo -> Gemini/OpenAI vision -> candidate place name ->
independently re-checked against real Nominatim geocoding -> only then shown
as "verified", with a real coordinate and real nearby places pulled from
Overpass. If Gemini's guess can't be found by a real geocoder, it is shown
as an unverified guess, never dressed up as confirmed.
"""
import json
import re

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.base import AIProvider, ProviderError
from app.integrations.gemini import GeminiProvider
from app.integrations.openai_provider import OpenAIProvider
from app.schemas.photo_id import NearbyAttraction, PhotoAlternative, PhotoIdentificationResponse, VerifiedLocation
from app.services import geocoding_service, places_service

ANALYSIS_PROMPT = """You are looking at a tourism photo, most likely taken in India (but not necessarily).
Identify what landmark, monument, building or natural feature this most likely shows, using only what is
visibly in the image (architecture style, signage, script, terrain, monument type, etc.).

Respond with ONLY valid JSON (no markdown fences, no commentary), in exactly this shape:
{
  "likely_place": "your best single guess at the specific place name, or null if you truly cannot tell",
  "confidence": 0.0,
  "category": "e.g. historic_site, temple, fort, natural_landmark, museum, other",
  "possible_destination": "the city/region you believe this is in, or null",
  "visual_clues": ["short phrase", "short phrase"],
  "cultural_clues": ["short phrase", "short phrase"],
  "alternatives": [{"name": "another possible place", "confidence": 0.0}]
}
confidence is your own honest 0-1 estimate of how sure you are -- use a LOW number (below 0.4) if the image
is generic or ambiguous (e.g. a plain building, a common style of architecture with no distinguishing
feature). Never report high confidence for a generic scene. If you cannot identify anything specific,
set likely_place to null and confidence to 0."""


def _get_provider() -> AIProvider | None:
    settings = get_settings()
    if not settings.ai_configured:
        return None
    return GeminiProvider() if settings.ai_provider.lower() == "gemini" else OpenAIProvider()


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    candidate = fence.group(1).strip() if fence else text
    try:
        return json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        pass
    start, end = candidate.find("{"), candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(candidate[start : end + 1])
        except (json.JSONDecodeError, ValueError):
            return None
    return None


def _confidence_label(confidence: float) -> str:
    if confidence >= 0.7:
        return "Likely match"
    if confidence >= 0.4:
        return "Possible match"
    return "Low-confidence identification"


async def identify_place(db: Session, image_bytes: bytes, mime_type: str) -> PhotoIdentificationResponse:
    provider = _get_provider()
    if provider is None:
        settings = get_settings()
        env_var = "GEMINI_API_KEY" if settings.ai_provider.lower() == "gemini" else "OPENAI_API_KEY"
        return PhotoIdentificationResponse(configured=False, message=f"Photo identification isn't configured -- set {env_var} in backend/.env.")

    try:
        result = await provider.analyze_image(image_bytes, mime_type, ANALYSIS_PROMPT)
    except ProviderError as exc:
        return PhotoIdentificationResponse(configured=True, provider=provider.name, message=f"Image analysis is temporarily unavailable ({exc.detail}).")

    parsed = _extract_json(result.text or "")
    if parsed is None:
        return PhotoIdentificationResponse(configured=True, provider=provider.name, message="The AI couldn't produce a readable analysis of this image -- try a clearer or more distinctive photo.")

    likely_place = parsed.get("likely_place") or None
    confidence = float(parsed.get("confidence") or 0.0)
    confidence = max(0.0, min(1.0, confidence))
    alternatives = [
        PhotoAlternative(name=str(a.get("name", "")), confidence=max(0.0, min(1.0, float(a.get("confidence") or 0.0))))
        for a in (parsed.get("alternatives") or []) if a.get("name")
    ]

    response = PhotoIdentificationResponse(
        configured=True, provider=provider.name,
        likely_place=likely_place, confidence=confidence if likely_place else None,
        confidence_label=_confidence_label(confidence) if likely_place else None,
        category=parsed.get("category") or None,
        possible_destination=parsed.get("possible_destination") or None,
        visual_clues=[str(c) for c in (parsed.get("visual_clues") or [])][:6],
        cultural_clues=[str(c) for c in (parsed.get("cultural_clues") or [])][:6],
        alternatives=alternatives[:4],
    )

    if not likely_place:
        return response

    # Independent verification step (spec section 16): a name Gemini "recognized"
    # means nothing until a real geocoder can actually find it.
    query = likely_place if not response.possible_destination else f"{likely_place}, {response.possible_destination}"
    try:
        geocoded = await geocoding_service.geocode_search(db, query, limit=1)
    except ProviderError:
        geocoded = []

    if geocoded:
        g = geocoded[0]
        response.verified = True
        response.verified_location = VerifiedLocation(display_name=g.display_name, latitude=g.latitude, longitude=g.longitude)
        try:
            nearby = await places_service.nearby_places(db, g.latitude, g.longitude, 2000, [])
            response.nearby_attractions = [
                NearbyAttraction(place_id=p.id, name=p.name, category=p.category, latitude=p.latitude, longitude=p.longitude, distance_meters=p.distance_meters)
                for p in nearby[:8]
            ]
        except ProviderError:
            pass

    return response
