"""
Schemas for AI photo-based place identification (master-upgrade spec
sections 15/16). Gemini vision proposes a candidate; Sarthi then tries to
independently verify it against real Nominatim geocoding before it is ever
presented as anything more than a guess -- see photo_id_service.py.
"""
from typing import Optional

from pydantic import BaseModel


class PhotoAlternative(BaseModel):
    name: str
    confidence: float  # 0-1, model-reported


class VerifiedLocation(BaseModel):
    display_name: str
    latitude: float
    longitude: float
    source: str = "nominatim"


class NearbyAttraction(BaseModel):
    place_id: str
    name: str
    category: str
    latitude: float
    longitude: float
    distance_meters: Optional[float] = None


class PhotoIdentificationResponse(BaseModel):
    configured: bool
    provider: Optional[str] = None

    likely_place: Optional[str] = None
    confidence: Optional[float] = None  # 0-1, model-reported -- never invented as "certain"
    confidence_label: Optional[str] = None  # "Likely match" / "Possible match" / "Low-confidence identification"
    category: Optional[str] = None
    possible_destination: Optional[str] = None
    visual_clues: list[str] = []
    cultural_clues: list[str] = []
    alternatives: list[PhotoAlternative] = []

    verified: bool = False
    verified_location: Optional[VerifiedLocation] = None
    nearby_attractions: list[NearbyAttraction] = []

    data_type: str = "ai-inferred"  # always -- this is never "confirmed" purely from image analysis
    disclaimer: str = (
        "AI-inferred identification from image analysis, independently checked against real OpenStreetMap "
        "geocoding where possible. This is not a certain identification -- verify important details "
        "yourself, especially before travelling based on it."
    )
    message: Optional[str] = None  # set when configured=False or analysis failed honestly
