from typing import Optional

from pydantic import BaseModel


class CulturalInfoResponse(BaseModel):
    place_id: str
    matched: bool
    source: str = "none"  # "curated" | "wikidata" | "wikipedia" | "none"
    display_name: Optional[str] = None
    summary: Optional[str] = None
    historical_significance: Optional[str] = None
    cultural_significance: Optional[str] = None
    architectural_significance: Optional[str] = None
    traditions: Optional[str] = None
    etiquette: Optional[str] = None
    visitor_guidance: Optional[str] = None
    sources: list[str] = []
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    retrieved_at: Optional[str] = None
    fallback_message: Optional[str] = None
