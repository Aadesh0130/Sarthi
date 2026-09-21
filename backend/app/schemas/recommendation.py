from typing import Optional

from pydantic import BaseModel

from app.schemas.event import EventResult
from app.schemas.hotel import HotelResult
from app.schemas.place import Place


class RecommendationCriteria(BaseModel):
    latitude: float
    longitude: float
    interests: list[str] = []
    pace: str = "balanced"  # relaxed | balanced | packed
    budget: str = "comfort"  # budget | comfort | luxury
    available_hours: Optional[float] = None
    weather_condition: Optional[str] = None  # "good" | "fair" | "poor" (outdoor suitability)
    candidate_places: list[Place] = []
    # Optional context signals (spec section 6). Left empty when Ticketmaster/
    # Hotelbeds aren't configured or returned nothing -- the scorer treats an
    # empty list as "no context available", never as "nothing is happening".
    nearby_events: list[EventResult] = []
    nearby_hotels: list[HotelResult] = []


class RecommendationReason(BaseModel):
    matched: bool
    label: str


class ScoredPlace(BaseModel):
    place: Place
    smart_score: int
    reasons: list[str]
    breakdown: dict[str, int]


class RecommendationResponse(BaseModel):
    criteria_echo: dict
    results: list[ScoredPlace]
    method: str = "deterministic-weighted-scoring"
    is_machine_learning: bool = False
