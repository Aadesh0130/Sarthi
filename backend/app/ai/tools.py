"""
Tool definitions for the AI Travel Assistant (spec sections 4E/17).

The LLM never has raw database or internet access -- it can only call these
named tools, each of which goes through the same services/providers as the
REST API. This keeps the assistant's answers grounded in real Sarthi data
instead of free-form generation, and lets it be swapped between OpenAI and
Gemini (app/integrations/openai_provider.py, app/integrations/gemini.py)
without changing anything here.

TOOL_SPECS is intentionally in bare {"name","description","parameters"} form
(no OpenAI/Gemini wrapper) -- each provider wraps it into its own API shape.
"""
from sqlalchemy.orm import Session

from app.schemas.flow_rebalance import RebalanceRequest
from app.schemas.place import Place
from app.schemas.recommendation import RecommendationCriteria
from app.services import (
    cultural_service,
    events_service,
    flow_rebalancer_service,
    geocoding_service,
    hotels_service,
    places_service,
    recommendation_service,
    weather_service,
)

TOOL_SPECS = [
    {
        "name": "search_places",
        "description": "Geocode a destination name (e.g. a city) to coordinates.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Destination name, e.g. 'Amritsar'"}},
            "required": ["query"],
        },
    },
    {
        "name": "get_nearby_places",
        "description": "Find real nearby tourist places (attractions, museums, temples, food, etc.) around a coordinate, from OpenStreetMap.",
        "parameters": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
                "categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Any of: attraction, museum, historic, religious, park, restaurant, cafe, shopping, hotel",
                },
                "radius_meters": {"type": "integer"},
            },
            "required": ["latitude", "longitude"],
        },
    },
    {
        "name": "get_weather",
        "description": "Get the real current weather and short forecast for a coordinate (Open-Meteo).",
        "parameters": {
            "type": "object",
            "properties": {"latitude": {"type": "number"}, "longitude": {"type": "number"}},
            "required": ["latitude", "longitude"],
        },
    },
    {
        "name": "get_recommendations",
        "description": "Rank a set of nearby places for the traveller using Sarthi's explainable SmartScore, given their interests/pace/budget and the current weather.",
        "parameters": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
                "interests": {"type": "array", "items": {"type": "string"}},
                "pace": {"type": "string"},
                "budget": {"type": "string"},
                "available_hours": {"type": "number"},
            },
            "required": ["latitude", "longitude"],
        },
    },
    {
        "name": "get_events",
        "description": "Find real events (concerts, shows, sports) near a coordinate via Ticketmaster. May report 'not configured' or an empty list -- Ticketmaster coverage for many Indian cities is limited, and that's reported honestly rather than invented.",
        "parameters": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
                "keyword": {"type": "string"},
            },
            "required": ["latitude", "longitude"],
        },
    },
    {
        "name": "get_hotels",
        "description": "Find real hotels with live availability/rates near a coordinate via Hotelbeds for given check-in/check-out dates. May report 'not configured' if Hotelbeds credentials aren't set.",
        "parameters": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number"},
                "longitude": {"type": "number"},
                "check_in": {"type": "string", "description": "YYYY-MM-DD"},
                "check_out": {"type": "string", "description": "YYYY-MM-DD"},
                "adults": {"type": "integer"},
            },
            "required": ["latitude", "longitude", "check_in", "check_out"],
        },
    },
    {
        "name": "get_cultural_info",
        "description": "Get sourced cultural/historical significance for a named place (Sarthi's curated dataset, falling back to Wikipedia/Wikidata). Never invents facts -- reports 'not found' honestly if no source has it.",
        "parameters": {
            "type": "object",
            "properties": {"place_name": {"type": "string"}},
            "required": ["place_name"],
        },
    },
    {
        "name": "rebalance_destination",
        "description": (
            "Tourist Flow Rebalancer: check a destination's real estimated Tourism Pressure Index and, if it is "
            "elevated (MODERATE/HIGH/VERY HIGH), get explainable real-data alternatives nearby with genuinely "
            "lower pressure. Use this when the traveller asks things like 'X seems crowded, what else can I "
            "visit?' or 'is there somewhere quieter near X?'. This tool is the ONLY source of truth for pressure, "
            "alternatives, distance, weather and scores here -- never invent or adjust any of these numbers "
            "yourself, and never claim an alternative exists that this tool didn't return."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "destination_query": {"type": "string", "description": "Destination name, e.g. 'Manali'"},
                "interests": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["destination_query"],
        },
    },
]


async def dispatch_tool(db: Session, name: str, arguments: dict) -> dict:
    if name == "search_places":
        results = await geocoding_service.geocode_search(db, arguments["query"], limit=3)
        return {"results": [r.model_dump() for r in results]}

    if name == "get_nearby_places":
        categories = arguments.get("categories", [])
        radius = int(arguments.get("radius_meters", 3000))
        places = await places_service.nearby_places(db, arguments["latitude"], arguments["longitude"], radius, categories)
        return {"places": [p.model_dump() for p in places[:20]]}

    if name == "get_weather":
        weather = await weather_service.get_weather(db, arguments["latitude"], arguments["longitude"])
        return weather.model_dump()

    if name == "get_recommendations":
        places = await places_service.nearby_places(db, arguments["latitude"], arguments["longitude"], 3000, [])
        weather = await weather_service.get_weather(db, arguments["latitude"], arguments["longitude"])
        criteria = RecommendationCriteria(
            latitude=arguments["latitude"],
            longitude=arguments["longitude"],
            interests=arguments.get("interests", []),
            pace=arguments.get("pace", "balanced"),
            budget=arguments.get("budget", "comfort"),
            available_hours=arguments.get("available_hours"),
            weather_condition=weather.outdoor_suitability,
            candidate_places=[Place(**p.model_dump()) for p in places],
        )
        response = recommendation_service.score_places(criteria)
        return {"results": [r.model_dump() for r in response.results[:10]]}

    if name == "get_events":
        result = await events_service.search_events(db, arguments["latitude"], arguments["longitude"], keyword=arguments.get("keyword", ""))
        return result.model_dump()

    if name == "get_hotels":
        result = await hotels_service.search_hotels(
            db, arguments["latitude"], arguments["longitude"],
            arguments["check_in"], arguments["check_out"], adults=arguments.get("adults", 2),
        )
        return result.model_dump()

    if name == "get_cultural_info":
        info = await cultural_service.get_cultural_info(db, "ai-lookup", arguments["place_name"])
        return info.model_dump()

    if name == "rebalance_destination":
        req = RebalanceRequest(destination_query=arguments["destination_query"], interests=arguments.get("interests", []), max_alternatives=5)
        result = await flow_rebalancer_service.rebalance(db, req)
        # Trim to what the model needs -- same "bounded tool result" pattern as get_recommendations above.
        return {
            "requested_destination": result.requested_destination.model_dump() if result.requested_destination else None,
            "tourism_pressure": result.tourism_pressure.model_dump() if result.tourism_pressure else None,
            "rebalancing_triggered": result.rebalancing_triggered,
            "message": result.message,
            "alternatives": [
                {
                    "name": a.destination.name,
                    "experience_match": a.experience_match,
                    "rebalancing_score": a.rebalancing_score,
                    "pressure_status": a.tourism_pressure.status,
                    "distance_km": a.distance_km,
                    "travel_time_minutes": a.travel_time_minutes,
                    "reasons": a.reasons,
                }
                for a in result.alternatives
            ],
        }

    return {"error": f"Unknown tool: {name}"}
