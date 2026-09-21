from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.integrations.base import ProviderError
from app.integrations.ticketmaster import TicketmasterProvider
from app.schemas.event import EventResult, EventSearchResponse
from app.services import events_service

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=EventSearchResponse)
async def search_events(
    lat: float,
    lon: float,
    radius_km: int = Query(25, ge=1, le=200),
    keyword: str = "",
    start_date: str | None = Query(None, description="YYYY-MM-DD"),
    end_date: str | None = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db),
):
    return await events_service.search_events(db, lat, lon, radius_km, keyword, start_date, end_date)


@router.get("/{event_id}", response_model=EventResult | None)
async def event_details(event_id: str):
    settings = get_settings()
    if not settings.events_configured:
        raise HTTPException(status_code=503, detail="Events aren't configured yet. Set TICKETMASTER_API_KEY in backend/.env.")
    try:
        event = await TicketmasterProvider().get_details(event_id)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=f"Event details are temporarily unavailable ({exc.detail}).")
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event
