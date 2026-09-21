from typing import Optional

from pydantic import BaseModel, Field


class CrowdComponent(BaseModel):
    """One signal that fed into (or was excluded from) the Tourism Pressure
    Index. `value` is 0-100 or null when this signal genuinely could not be
    computed -- never a guessed placeholder (spec: data honesty rules)."""

    value: Optional[float] = None
    weight: float = Field(..., description="Share of the composite score this component was given, 0-1")
    used: bool = Field(..., description="False when this component was unavailable and excluded from the score")
    data_type: str = Field(..., description='"estimated" | "curated" | "live" | "unavailable"')
    label: str
    note: Optional[str] = None


class CrowdPressureResponse(BaseModel):
    destination: str
    latitude: float
    longitude: float

    pressure_index: Optional[int] = Field(None, description="0-100 Tourism Pressure Index, or null if unreliable")
    status: Optional[str] = Field(None, description='"LOW" | "MODERATE" | "HIGH" | "VERY HIGH", or null')
    data_type: str = Field(
        "estimated",
        description='"estimated" (default -- no live crowd provider is connected), "curated", or "unavailable"',
    )
    confidence: Optional[float] = Field(
        None,
        description="0-1 -- share of the composite's total weight that came from components which were actually "
                     "available for this call (e.g. 0.90 when only live events were missing). Null alongside a null "
                     "pressure_index -- there is no score to have confidence in.",
    )

    components: dict[str, CrowdComponent] = Field(default_factory=dict)
    explanation: list[str] = Field(default_factory=list)

    weather_suitability: Optional[str] = Field(
        None, description="GOOD | FAIR | POOR -- current outdoor visit suitability, reported separately from pressure"
    )

    message: Optional[str] = Field(
        None, description="Set when pressure_index is null, or to add an honest caveat alongside a real score"
    )
