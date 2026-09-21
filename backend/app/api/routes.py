from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.integrations.base import ProviderError
from app.schemas.route import RouteRequest, RouteResponse
from app.services import routing_service

router = APIRouter(prefix="/api/routes", tags=["routes"])


@router.post("", response_model=RouteResponse)
async def compute_route(payload: RouteRequest, db: Session = Depends(get_db)):
    try:
        return await routing_service.compute_route(db, payload.stops, payload.profile)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=f"Routing is temporarily unavailable ({exc.detail}).")
