from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.integrations.base import ProviderError
from app.schemas.weather import WeatherResponse
from app.services import weather_service

router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.get("", response_model=WeatherResponse)
async def weather(lat: float, lon: float, db: Session = Depends(get_db)):
    try:
        return await weather_service.get_weather(db, lat, lon)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=f"Weather data is temporarily unavailable ({exc.detail}).")
