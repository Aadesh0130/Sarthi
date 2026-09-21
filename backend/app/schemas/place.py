from typing import Optional

from pydantic import BaseModel, Field


class Place(BaseModel):
    """Normalized place model. Every field is either real provider data or
    explicitly null -- nothing here is invented. See project spec section 7.
    """

    id: str = Field(..., description='Normalized id, e.g. "node/123456"')
    external_id: str
    source: str = Field(..., description='"overpass" or "nominatim"')
    source_url: Optional[str] = None

    name: str
    category: str = Field(..., description="Normalized category, e.g. attraction/museum/temple/restaurant")
    raw_tags: dict = Field(default_factory=dict)

    latitude: float
    longitude: float
    address: Optional[str] = None

    rating: Optional[float] = None
    review_count: Optional[int] = None
    photos: list[str] = Field(default_factory=list)
    opening_hours: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    description: Optional[str] = None

    distance_meters: Optional[float] = None


class GeocodeResult(BaseModel):
    display_name: str
    latitude: float
    longitude: float
    place_type: Optional[str] = None
    importance: Optional[float] = None
    bounding_box: Optional[list[float]] = None
    source: str = "nominatim"
    # Nominatim's own address breakdown (addressdetails=1), when it could be
    # parsed -- used by the Tourist Flow Rebalancer to know which district the
    # requested destination is actually in, so "nearby similar districts" can
    # exclude the current one. Never guessed when Nominatim didn't provide it.
    district: Optional[str] = Field(None, description="Best-effort district/county name from Nominatim's address breakdown")
    state: Optional[str] = None


class PlaceDetails(Place):
    open_now: Optional[bool] = Field(
        None, description="null when opening_hours data is unavailable/unparseable -- never guessed"
    )


class Settlement(BaseModel):
    """A real OpenStreetMap-mapped town/village/hamlet node -- used by the
    Tourist Flow Rebalancer to discover genuine nearby-destination candidates
    (not tourist POIs; see OverpassProvider.nearby_settlements). `population`
    is only ever OSM's own `population` tag when present -- never estimated
    or invented when absent."""

    id: str
    name: str
    place_type: str = Field(..., description='OSM "place" tag value, e.g. "town" | "village" | "hamlet"')
    latitude: float
    longitude: float
    population: Optional[int] = Field(None, description="OSM population tag, when present -- never estimated")
    state: Optional[str] = None


class District(BaseModel):
    """A real OpenStreetMap administrative boundary (boundary=administrative,
    roughly district-level) -- used by the Tourist Flow Rebalancer's "Nearby
    Similar Districts" discovery (see flow_rebalancer_service.py). Distinct
    from Settlement: a Settlement is one town/village point; a District is
    the coarser administrative area that can absorb tourism demand across
    many settlements. `admin_level` is OSM's own tag -- India's admin levels
    for "district" are not perfectly consistent across states (see
    OverpassProvider.nearby_districts), so this is treated as an approximate
    signal, never a guarantee of exact administrative rank."""

    id: str
    name: str
    admin_level: Optional[str] = None
    latitude: float
    longitude: float
    state: Optional[str] = None
