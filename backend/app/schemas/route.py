from pydantic import BaseModel, Field


class RouteStop(BaseModel):
    name: str = ""
    latitude: float
    longitude: float


class RouteRequest(BaseModel):
    stops: list[RouteStop] = Field(..., min_length=2)
    profile: str = Field("driving", description='"driving" | "walking" | "cycling"')


class RouteLeg(BaseModel):
    from_name: str
    to_name: str
    distance_meters: float
    duration_seconds: float


class RouteResponse(BaseModel):
    profile: str
    total_distance_meters: float
    total_duration_seconds: float
    geometry_geojson: dict  # GeoJSON LineString, straight from OSRM -- for Leaflet
    legs: list[RouteLeg]
    source: str = "osrm"
    provider_note: str = "Routed via the public OSRM demo server (router.project-osrm.org)."
