from typing import Optional

from pydantic import BaseModel


class HotelRate(BaseModel):
    rate_key: str
    board_name: Optional[str] = None
    room_type: Optional[str] = None
    net_price: Optional[float] = None
    currency: Optional[str] = None
    rate_class: Optional[str] = None  # provider's own label, e.g. "NOR" (non-refundable)
    requires_recheck: bool = True  # Hotelbeds: rates not flagged safe-to-book must be revalidated


class HotelResult(BaseModel):
    """A normalized hotel (spec section 9). Prices/availability here are a
    search-time snapshot -- callers must call check_rate before treating a
    price as bookable (spec section 11: 'never cache live prices for an
    inappropriate duration')."""

    id: str
    source: str = "hotelbeds"
    source_url: Optional[str] = None
    name: str
    category_name: Optional[str] = None  # e.g. "4 STARS"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    description: Optional[str] = None
    facilities: list[str] = []
    images: list[str] = []
    rates: list[HotelRate] = []
    retrieved_at: Optional[str] = None  # ISO timestamp of this search snapshot


class HotelSearchResponse(BaseModel):
    configured: bool
    hotels: list[HotelResult] = []
    message: Optional[str] = None
    retrieved_at: Optional[str] = None


class HotelRateCheck(BaseModel):
    rate_key: str
    still_valid: bool
    net_price: Optional[float] = None
    currency: Optional[str] = None
    checked_at: str


class CheckRateRequest(BaseModel):
    rate_key: str
