"""
Schemas for the Tourist Flow Rebalancer (SIH PS26204 core differentiator):
Sarthi doesn't only recommend places within a destination (that's
app/schemas/recommendation.py) -- when a requested DESTINATION itself is
under real tourism pressure, this scores and ranks nearby DESTINATION-level
alternatives so demand can be voluntarily redistributed, never silently.

Reuses CrowdPressureResponse directly (the existing Tourism Pressure Index)
rather than re-declaring pressure fields -- there is exactly one pressure
model in this codebase.
"""
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.crowd import CrowdPressureResponse


class RebalanceRequest(BaseModel):
    destination_query: str = Field("", description="Free-text destination name, e.g. 'Manali'. Optional if latitude/longitude are given.")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    interests: list[str] = Field(default_factory=list)
    budget: str = "comfort"  # budget | comfort | luxury -- accepted for forward-compat, not yet scored (see limitations)
    pace: str = "balanced"  # relaxed | balanced | packed -- accepted for forward-compat, not yet scored (see limitations)
    travel_date: Optional[str] = None
    max_alternatives: int = Field(5, ge=1, le=10)


class ScoreFactor(BaseModel):
    """One explainable input into an alternative's Rebalancing Score --
    mirrors the transparency pattern already used by CrowdComponent."""

    value: Optional[float] = Field(None, description="0-100, or null if this factor could not be computed")
    weight: float
    data_type: str = Field(..., description='"estimated" | "curated" | "live" | "unavailable"')
    note: str


class LocalOpportunitySignal(BaseModel):
    """Never a rupee figure -- an explainable signal from real OSM place
    counts (restaurants, stays, shops) near the candidate, per spec section
    'Local Economic Opportunity'."""

    score: float
    label: str
    business_count: int
    data_type: str = "estimated"


class CarryingCapacityInfo(BaseModel):
    """Modelled, not official -- see app/integrations/carrying_capacity.py."""

    score: float
    label: str
    data_type: str = "estimated"


class DestinationSummary(BaseModel):
    name: str
    latitude: float
    longitude: float
    state: Optional[str] = None
    district: Optional[str] = Field(
        None, description="Best-effort district/county name (Nominatim address breakdown, or OSM admin-boundary name for a district-source alternative)"
    )
    source: str = Field(
        ..., description='"geocoded" (any real place) | "curated-hidden-gem" | "curated-destination" | "osm-settlement" | "osm-district"'
    )


class RebalanceAlternative(BaseModel):
    destination: DestinationSummary
    experience_match: int = Field(..., description="0-100, real-data category/interest similarity to the requested destination")
    rebalancing_score: int = Field(..., description="0-100 explainable weighted composite -- see flow_rebalancer_service.py")
    tourism_pressure: CrowdPressureResponse
    distance_km: float
    travel_time_minutes: Optional[int] = Field(None, description="Real OSRM driving time when available, else null (never estimated as if real)")
    distance_source: str = Field("straight-line-estimate", description='"osrm" (real route) or "straight-line-estimate" (haversine, OSRM unavailable/not attempted)')
    local_opportunity: LocalOpportunitySignal
    carrying_capacity: CarryingCapacityInfo
    sustainability_score: float
    sustainability_data_type: str = Field(..., description='"curated" (from Sarthi\'s curated dataset) or "estimated" (modelled from place density)')
    is_hidden_gem: bool = False
    factors: dict[str, ScoreFactor] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)


class RebalanceResponse(BaseModel):
    requested_destination: Optional[DestinationSummary] = None
    tourism_pressure: Optional[CrowdPressureResponse] = None

    rebalancing_triggered: bool = Field(False, description="True when pressure is HIGH/VERY HIGH (or MODERATE and alternatives were still found) and alternatives are worth surfacing")
    pressure_check_only: bool = Field(False, description="True when pressure was LOW and no candidate search was performed at all -- performance: never hits Overpass/OSRM for a destination that doesn't need rebalancing")

    alternatives: list[RebalanceAlternative] = Field(default_factory=list)

    # "Nearby Similar Districts" (distinct from `alternatives` above, which
    # are individual settlements/curated destinations): coarser
    # administrative-area candidates discovered dynamically from OSM
    # boundary=administrative data -- see flow_rebalancer_service's
    # _discover_district_candidates. Reuses the exact same
    # RebalanceAlternative shape (and the exact same _score_candidate scoring
    # function) rather than a second, competing model -- only
    # `destination.source == "osm-district"` and `destination.district`
    # distinguish these from settlement/curated alternatives.
    district_alternatives: list[RebalanceAlternative] = Field(default_factory=list)
    # Set only when a district-level search genuinely ran and came back
    # empty/unhelpful -- kept separate from `message` (which covers the
    # settlement/curated alternatives above) so the Crowding Index and either
    # alternatives list can each honestly report their own outcome rather
    # than being forced to share one sentence.
    district_alternatives_message: Optional[str] = None

    method: str = "deterministic-weighted-scoring"
    is_machine_learning: bool = False
    message: Optional[str] = None
