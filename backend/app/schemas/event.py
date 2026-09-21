from typing import Optional

from pydantic import BaseModel


class EventResult(BaseModel):
    """A normalized event, regardless of upstream provider (spec section 9:
    'normalize external data into Sarthi domain models'). Never fabricated --
    every field here comes straight from the provider response."""

    id: str
    source: str = "ticketmaster"
    source_url: Optional[str] = None
    name: str
    description: Optional[str] = None
    start_datetime: Optional[str] = None  # ISO 8601, local to the venue, as provided
    end_datetime: Optional[str] = None
    venue_name: Optional[str] = None
    venue_address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    classification: Optional[str] = None  # e.g. "Music", "Sports"
    image_url: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    currency: Optional[str] = None
    status: Optional[str] = None  # onsale | offsale | cancelled | postponed, as provided
    url: Optional[str] = None


class EventSearchResponse(BaseModel):
    configured: bool
    events: list[EventResult] = []
    message: Optional[str] = None
    coverage_note: str = (
        "Event coverage depends entirely on Ticketmaster's market presence. An empty result means no "
        "Ticketmaster-listed events matched -- it does not mean there is nothing happening nearby."
    )
