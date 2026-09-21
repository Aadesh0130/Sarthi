from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter()


@router.get("/api/health")
def health():
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "ai_configured": settings.ai_configured,
        "ai_provider": settings.ai_provider,
        "events_configured": settings.events_configured,
        "hotels_configured": settings.hotels_configured,
        "images_configured": settings.images_configured,
        "providers": {
            "geocoding": "nominatim",
            "places": "overpass",
            "routing": "osrm",
            "weather": "open-meteo",
            "culture_fallback": "wikipedia/wikidata",
            "events": "ticketmaster" if settings.events_configured else "not configured",
            "hotels": "hotelbeds" if settings.hotels_configured else "not configured",
            "images": "unsplash" if settings.images_configured else "not configured",
            "ai": settings.ai_provider if settings.ai_configured else "not configured",
            "crowd_pressure": "estimated (no live crowd provider connected)",
            "tourist_flow_rebalancer": "deterministic weighted scoring over real Tourism Pressure Index + OSM data (not AI/ML)",
            "ai_trip_planner": f"{settings.ai_provider} (real places + weather, grounded)" if settings.ai_configured else "not configured",
            "ai_photo_identification": f"{settings.ai_provider} vision + Nominatim verification" if settings.ai_configured else "not configured",
        },
    }
