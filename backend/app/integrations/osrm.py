"""OSRM routing provider (public demo server: router.project-osrm.org)."""
import httpx

from app.core.config import get_settings
from app.integrations.base import ProviderError, RoutingProvider
from app.schemas.route import RouteLeg, RouteResponse, RouteStop

settings = get_settings()

_PROFILE_MAP = {"driving": "driving", "walking": "foot", "cycling": "bike"}


class OSRMProvider(RoutingProvider):
    def __init__(self):
        self.base_url = settings.osrm_base_url

    async def route(self, stops: list[RouteStop], profile: str = "driving") -> RouteResponse:
        if len(stops) < 2:
            raise ProviderError("osrm", "At least two stops are required for a route")
        osrm_profile = _PROFILE_MAP.get(profile, "driving")
        coords = ";".join(f"{s.longitude},{s.latitude}" for s in stops)
        url = f"{self.base_url}/route/v1/{osrm_profile}/{coords}"
        params = {"overview": "full", "geometries": "geojson", "steps": "false"}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError("osrm", str(exc)) from exc

        if data.get("code") != "Ok" or not data.get("routes"):
            raise ProviderError("osrm", data.get("message", "No route found between the given stops"))

        route = data["routes"][0]
        legs_data = route.get("legs", [])
        legs = []
        for i, leg in enumerate(legs_data):
            legs.append(
                RouteLeg(
                    from_name=stops[i].name or f"Stop {i + 1}",
                    to_name=stops[i + 1].name or f"Stop {i + 2}",
                    distance_meters=leg.get("distance", 0.0),
                    duration_seconds=leg.get("duration", 0.0),
                )
            )

        return RouteResponse(
            profile=profile,
            total_distance_meters=route.get("distance", 0.0),
            total_duration_seconds=route.get("duration", 0.0),
            geometry_geojson=route.get("geometry", {}),
            legs=legs,
        )
