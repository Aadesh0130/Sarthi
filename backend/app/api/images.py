from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.image import ImageSearchResponse
from app.services import images_service

router = APIRouter(prefix="/api/images", tags=["images"])


@router.get("/search", response_model=ImageSearchResponse)
async def search_images(q: str = Query(..., min_length=1), count: int = Query(3, ge=1, le=10), db: Session = Depends(get_db)):
    return await images_service.search_images(db, q, count)
