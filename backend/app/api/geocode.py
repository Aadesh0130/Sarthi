from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.integrations.base import ProviderError
from app.schemas.place import GeocodeResult
from app.services import geocoding_service

router = APIRouter(prefix="/api/geocode", tags=["geocode"])


@router.get("/search", response_model=list[GeocodeResult])
async def geocode_search(
    q: str = Query(..., min_length=2, description="Destination or place name, e.g. 'Amritsar'"),
    limit: int = Query(5, ge=1, le=10),
    db: Session = Depends(get_db),
):
    try:
        return await geocoding_service.geocode_search(db, q, limit)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=f"Geocoding is temporarily unavailable ({exc.detail}).")


@router.get("/reverse", response_model=GeocodeResult | None)
async def geocode_reverse(lat: float, lon: float, db: Session = Depends(get_db)):
    try:
        return await geocoding_service.reverse_geocode(db, lat, lon)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=f"Reverse geocoding is temporarily unavailable ({exc.detail}).")
