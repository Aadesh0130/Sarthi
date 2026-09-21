from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.crowd import CrowdPressureResponse
from app.services import crowd_service

router = APIRouter(prefix="/api/crowd", tags=["crowd"])


@router.get("/pressure", response_model=CrowdPressureResponse)
async def crowd_pressure(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    destination: str = Query("", description="Destination label, e.g. 'Jaipur, Rajasthan, India' -- improves seasonal matching"),
    db: Session = Depends(get_db),
):
    # This endpoint deliberately never raises -- an unreachable live signal
    # (Overpass, Open-Meteo, Ticketmaster) degrades that one component rather
    # than failing the whole crowd estimate, and a genuinely unexpected error
    # still comes back as an honest "unavailable" response so Explore/Planner
    # never break because of this feature (spec: error handling).
    try:
        return await crowd_service.get_pressure(db, destination or "this area", lat, lon)
    except Exception:
        from app.schemas.crowd import CrowdPressureResponse as _R
        return _R(
            destination=destination or "this area", latitude=lat, longitude=lon,
            pressure_index=None, status=None, data_type="unavailable",
            message="Tourism pressure unavailable right now.",
        )
