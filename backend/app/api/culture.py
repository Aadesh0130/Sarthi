"""Top-level convenience route (spec section 9: GET /api/culture/{place_id}).

The nested /api/places/{osm_type}/{osm_id}/culture route (places.py) is the
one the frontend actually uses today, since it can resolve the place's name
from Sarthi's own place-details cache first. This route is for a caller that
already knows the place's display name (e.g. the AI assistant, or a client
that only has a name and no OSM id) and wants cultural info directly."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.cultural import CulturalInfoResponse
from app.services import cultural_service

router = APIRouter(prefix="/api/culture", tags=["culture"])


@router.get("/{place_id}", response_model=CulturalInfoResponse)
async def culture_by_id(
    place_id: str,
    name: str = Query(..., description="Display name to look up, e.g. 'Golden Temple'"),
    db: Session = Depends(get_db),
):
    return await cultural_service.get_cultural_info(db, place_id, name)
