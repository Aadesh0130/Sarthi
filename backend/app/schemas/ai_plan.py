"""
Schemas for the AI-generated real-data itinerary (master-upgrade spec
sections 13/14/21/22): Gemini/OpenAI reasons over places Sarthi already
retrieved live from OpenStreetMap -- it never gets to invent a place. Every
AIPlanStop's name/category/coordinates/address are re-hydrated straight from
the retrieved Place after generation (see ai_planner_service.py), never
trusted verbatim from the model's own output -- only `place_id` is used as
the model's "vote".
"""
from typing import Optional

from pydantic import BaseModel


class AIPlanRequest(BaseModel):
    destination_query: str
    days: int = 3
    interests: list[str] = []
    pace: str = "balanced"  # relaxed | balanced | packed
    budget: str = "comfort"  # budget | comfort | luxury
    travelers: int = 2
    avoid_crowds: bool = False


class AIPlanStop(BaseModel):
    place_id: str
    name: str
    category: str
    latitude: float
    longitude: float
    address: Optional[str] = None
    distance_meters: Optional[float] = None
    time_of_day: str  # e.g. "Morning", "Afternoon", "Evening"
    reason: str  # short, concrete, model-provided justification
    source: str = "overpass"  # every stop is a real retrieved Place -- never invented


class AIPlanDay(BaseModel):
    day: int
    title: str
    stops: list[AIPlanStop]
    long_hop_warning: Optional[str] = None  # set when consecutive stops imply a long, possibly-impractical hop


class AIPlanResponse(BaseModel):
    configured: bool
    provider: Optional[str] = None
    destination: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    days: list[AIPlanDay] = []
    removed_unverified_count: int = 0  # how many model-proposed stops were dropped for citing an unknown place_id
    weather_note: Optional[str] = None
    events_configured: bool = False
    hotels_configured: bool = False
    disclaimer: str = (
        "AI-reasoned itinerary: Gemini/OpenAI selects and orders from real places Sarthi already retrieved "
        "live from OpenStreetMap -- it cannot invent a place, and every stop shown was independently "
        "verified against that retrieved list. Not a substitute for checking current opening hours."
    )
    message: Optional[str] = None  # set when configured=False, or when generation failed honestly
    raw_model_notes: Optional[str] = None  # any free-text notes the model returned alongside the plan


class AIReplanRequest(BaseModel):
    destination_query: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    instruction: str  # free text: "make it cheaper", "add more historical places", "it's going to rain", ...
    previous_plan: AIPlanResponse
    interests: list[str] = []
    pace: str = "balanced"
    budget: str = "comfort"
    travelers: int = 2
    avoid_crowds: bool = False
