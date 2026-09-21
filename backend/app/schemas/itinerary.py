from typing import Optional

from pydantic import BaseModel, Field


class ItineraryItemIn(BaseModel):
    day: int = 1
    place_id: str
    name: str
    category: str = ""
    latitude: float
    longitude: float
    suggested_time: str = ""
    estimated_duration_minutes: int = 90
    notes: str = ""


class ItineraryItemOut(ItineraryItemIn):
    id: int
    order_index: int


class ItineraryCreate(BaseModel):
    title: str = "My Sarthi trip"
    destination_query: str = ""
    start_date: str = ""
    days: int = 1
    travelers: int = 1
    budget: str = "comfort"
    pace: str = "balanced"
    interests: list[str] = []
    items: list[ItineraryItemIn] = []


class ItineraryUpdate(BaseModel):
    title: Optional[str] = None
    days: Optional[int] = None
    travelers: Optional[int] = None
    budget: Optional[str] = None
    pace: Optional[str] = None
    interests: Optional[list[str]] = None
    items: Optional[list[ItineraryItemIn]] = None


class ItineraryOut(BaseModel):
    id: int
    title: str
    destination_query: str
    start_date: str
    days: int
    travelers: int
    budget: str
    pace: str
    interests: list[str]
    items: list[ItineraryItemOut]


class ReplanRequest(BaseModel):
    reason: str = Field(
        default="weather",
        description=(
            "One of: weather (reorder a day toward indoor places using real forecast), "
            "remove_place (drop a place and re-sequence), preferences_changed (re-score remaining "
            "places against new interests/pace/budget), time_limited (trim the day to fit fewer "
            "available hours). event_change/hotel_change/route_impractical are recognized but rejected "
            "with a clear explanation unless Ticketmaster/Hotelbeds/OSRM data actually supports them."
        ),
    )
    remove_place_id: Optional[str] = None  # required when reason == "remove_place"
    new_interests: Optional[list[str]] = None  # used when reason == "preferences_changed"
    new_pace: Optional[str] = None
    new_budget: Optional[str] = None
    day: Optional[int] = None  # which day new_available_hours applies to, for time_limited
    new_available_hours: Optional[float] = None  # used when reason == "time_limited"
