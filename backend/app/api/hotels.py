from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.integrations.base import ProviderError
from app.schemas.hotel import CheckRateRequest, HotelRateCheck, HotelResult, HotelSearchResponse
from app.services import hotels_service

router = APIRouter(prefix="/api/hotels", tags=["hotels"])


@router.get("", response_model=HotelSearchResponse)
async def search_hotels(
    lat: float,
    lon: float,
    check_in: str = Query(..., description="YYYY-MM-DD"),
    check_out: str = Query(..., description="YYYY-MM-DD"),
    adults: int = Query(2, ge=1, le=10),
    radius_km: int = Query(15, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return await hotels_service.search_hotels(db, lat, lon, check_in, check_out, adults, radius_km)


@router.get("/{hotel_id}", response_model=HotelResult)
async def hotel_content(hotel_id: str, db: Session = Depends(get_db)):
    settings = get_settings()
    if not settings.hotels_configured:
        raise HTTPException(status_code=503, detail="Hotels aren't configured yet. Set HOTELBEDS_API_KEY and HOTELBEDS_SECRET in backend/.env.")
    try:
        hotel = await hotels_service.get_hotel_content(db, hotel_id)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=f"Hotel content is temporarily unavailable ({exc.detail}).")
    if hotel is None:
        raise HTTPException(status_code=404, detail="Hotel not found")
    return hotel


@router.post("/check-rate", response_model=HotelRateCheck)
async def check_rate(payload: CheckRateRequest, db: Session = Depends(get_db)):
    """Always a live revalidation call to Hotelbeds -- never cached (spec
    section 11: rates must be re-checked before being presented as final)."""
    return await hotels_service.check_rate(db, payload.rate_key)
