from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.integrations.base import ProviderError
from app.schemas.itinerary import ItineraryCreate, ItineraryOut, ItineraryUpdate, ReplanRequest
from app.services import itinerary_service, weather_service

router = APIRouter(prefix="/api/itineraries", tags=["itineraries"])


@router.post("", response_model=ItineraryOut)
def create_itinerary(payload: ItineraryCreate, db: Session = Depends(get_db)):
    return itinerary_service.create_itinerary(db, payload)


@router.get("", response_model=list[ItineraryOut])
def list_itineraries(db: Session = Depends(get_db)):
    return itinerary_service.list_itineraries(db)


@router.get("/{itinerary_id}", response_model=ItineraryOut)
def get_itinerary(itinerary_id: int, db: Session = Depends(get_db)):
    itinerary = itinerary_service.get_itinerary(db, itinerary_id)
    if itinerary is None:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    return itinerary


@router.put("/{itinerary_id}", response_model=ItineraryOut)
def update_itinerary(itinerary_id: int, payload: ItineraryUpdate, db: Session = Depends(get_db)):
    itinerary = itinerary_service.update_itinerary(db, itinerary_id, payload)
    if itinerary is None:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    return itinerary


@router.delete("/{itinerary_id}")
def delete_itinerary(itinerary_id: int, db: Session = Depends(get_db)):
    ok = itinerary_service.delete_itinerary(db, itinerary_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Itinerary not found")
    return {"deleted": True}


SUPPORTED_REPLAN_REASONS = {"weather", "remove_place", "preferences_changed", "time_limited"}
UNSUPPORTED_REPLAN_REASONS = {
    "event_change": "Sarthi doesn't have a live 'this event changed' signal -- check Explore's Events section for current listings instead.",
    "hotel_change": "Sarthi doesn't have a live 'this hotel changed' signal -- re-run hotel search for current availability instead.",
    "route_impractical": "Sarthi doesn't automatically detect an 'impractical' route -- use the Optimize Route action to recompute a real OSRM route instead.",
}


@router.post("/{itinerary_id}/replan", response_model=ItineraryOut)
async def replan_itinerary(itinerary_id: int, payload: ReplanRequest, db: Session = Depends(get_db)):
    """Deterministic replanning (spec section 8). Every trigger below is
    backed by either real data (weather) or a genuine deterministic
    recomputation (remove_place, preferences_changed, time_limited) -- none
    of it is faked. Triggers Sarthi has no real signal for
    (event_change/hotel_change/route_impractical) are rejected with a clear
    explanation rather than pretending to react to them.
    """
    itinerary = itinerary_service.get_itinerary(db, itinerary_id)
    if itinerary is None:
        raise HTTPException(status_code=404, detail="Itinerary not found")

    reason = payload.reason

    if reason in UNSUPPORTED_REPLAN_REASONS:
        raise HTTPException(status_code=400, detail=UNSUPPORTED_REPLAN_REASONS[reason])

    if reason not in SUPPORTED_REPLAN_REASONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown replan reason '{reason}'. Supported: {', '.join(sorted(SUPPORTED_REPLAN_REASONS))}.",
        )

    if reason == "remove_place":
        if not payload.remove_place_id:
            raise HTTPException(status_code=400, detail="remove_place_id is required for reason=remove_place")
        result = itinerary_service.replan_remove_place(db, itinerary_id, payload.remove_place_id)
        return result if result is not None else itinerary

    if reason == "preferences_changed":
        result = itinerary_service.replan_preferences_changed(
            db, itinerary_id, payload.new_interests, payload.new_pace, payload.new_budget,
        )
        return result if result is not None else itinerary

    if reason == "time_limited":
        if payload.day is None or payload.new_available_hours is None:
            raise HTTPException(status_code=400, detail="day and new_available_hours are required for reason=time_limited")
        result = itinerary_service.replan_time_limited(db, itinerary_id, payload.day, payload.new_available_hours)
        return result if result is not None else itinerary

    # reason == "weather": checks the REAL Open-Meteo forecast for each day's
    # first item and reorders that day toward indoor places if the outdoor
    # suitability is 'poor'.
    poor_days: set[int] = set()
    seen_days: set[int] = set()
    for item in itinerary.items:
        if item.day in seen_days:
            continue
        seen_days.add(item.day)
        try:
            w = await weather_service.get_weather(db, item.latitude, item.longitude)
        except ProviderError:
            continue
        if w.outdoor_suitability == "poor":
            poor_days.add(item.day)

    if not poor_days:
        return itinerary

    return itinerary_service.replan_for_weather(db, itinerary_id, poor_days)
