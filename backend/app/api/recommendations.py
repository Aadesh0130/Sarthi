from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.integrations.base import ProviderError
from app.schemas.recommendation import RecommendationCriteria, RecommendationResponse
from app.services import places_service, recommendation_service, weather_service

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.post("", response_model=RecommendationResponse)
async def recommendations(payload: RecommendationCriteria, db: Session = Depends(get_db)):
    criteria = payload
    if not criteria.candidate_places:
        try:
            places = await places_service.nearby_places(db, criteria.latitude, criteria.longitude, 3000, [])
        except ProviderError as exc:
            raise HTTPException(status_code=503, detail=f"Place data is temporarily unavailable ({exc.detail}).")
        criteria = criteria.model_copy(update={"candidate_places": places})

    if criteria.weather_condition is None:
        try:
            weather = await weather_service.get_weather(db, criteria.latitude, criteria.longitude)
            criteria = criteria.model_copy(update={"weather_condition": weather.outdoor_suitability})
        except ProviderError:
            pass  # weather is a bonus factor -- proceed without it rather than failing the whole request

    return recommendation_service.score_places(criteria)
