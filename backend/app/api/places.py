from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.integrations.base import ProviderError
from app.integrations.overpass import ALL_CATEGORIES
from app.schemas.cultural import CulturalInfoResponse
from app.schemas.place import Place, PlaceDetails
from app.services import cultural_service, places_service

router = APIRouter(prefix="/api/places", tags=["places"])


def _mark_if_stale(response: Response, meta: dict) -> None:
    """When nearby_places had to fall back to an out-of-date cache entry
    (every live Overpass mirror failed for this call), say so honestly via a
    response header rather than silently presenting old data as fresh --
    the body shape (list[Place]) stays unchanged so existing callers still
    work, but the frontend can show "showing cached results from N ago"
    instead of either a false success or a needless hard failure."""
    if "stale_seconds" in meta:
        response.headers["X-Sarthi-Data-Freshness"] = "cached-stale"
        response.headers["X-Sarthi-Cache-Age-Seconds"] = str(int(meta["stale_seconds"]))


def _add_radius_headers(response: Response, meta: dict) -> None:
    """Expose the honest actual search radius (spec: "Radius Strategy" --
    "the response must clearly indicate the ACTUAL radius used... never
    claim 4km if 8km was used"). nearby_places() always populates both keys
    in `meta` now, whether or not escalation actually happened, so these
    headers are always set -- the frontend can compare the two values to
    tell whether a widen actually occurred instead of guessing."""
    if "requested_radius_meters" in meta:
        response.headers["X-Sarthi-Requested-Radius-Meters"] = str(meta["requested_radius_meters"])
    if "effective_radius_meters" in meta:
        response.headers["X-Sarthi-Effective-Radius-Meters"] = str(meta["effective_radius_meters"])


@router.get("/categories")
def categories():
    return {"categories": ALL_CATEGORIES}


@router.get("/nearby", response_model=list[Place])
async def places_nearby(
    response: Response,
    lat: float,
    lon: float,
    radius_meters: int = Query(3000, ge=200, le=15000),
    categories: str = Query("", description="Comma-separated categories; empty = all"),
    db: Session = Depends(get_db),
):
    cats = [c.strip() for c in categories.split(",") if c.strip()]
    meta: dict = {}
    try:
        results = await places_service.nearby_places(db, lat, lon, radius_meters, cats, meta=meta)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=f"Nearby-places data is temporarily unavailable ({exc.detail}).")
    _mark_if_stale(response, meta)
    _add_radius_headers(response, meta)
    return results


@router.get("/search", response_model=list[Place])
async def places_search(
    response: Response,
    lat: float,
    lon: float,
    q: str = Query(..., min_length=1),
    radius_meters: int = Query(5000, ge=200, le=20000),
    db: Session = Depends(get_db),
):
    meta: dict = {}
    try:
        results = await places_service.nearby_places(db, lat, lon, radius_meters, [], meta=meta)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=f"Place search is temporarily unavailable ({exc.detail}).")
    _mark_if_stale(response, meta)
    _add_radius_headers(response, meta)
    needle = q.strip().lower()
    return [p for p in results if needle in p.name.lower()]


@router.get("/{osm_type}/{osm_id}", response_model=PlaceDetails)
async def place_details(osm_type: str, osm_id: str, db: Session = Depends(get_db)):
    try:
        details = await places_service.get_place_details(db, f"{osm_type}/{osm_id}")
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=f"Place details are temporarily unavailable ({exc.detail}).")
    if details is None:
        raise HTTPException(status_code=404, detail="Place not found")
    return details


@router.get("/{osm_type}/{osm_id}/culture", response_model=CulturalInfoResponse)
async def place_culture(osm_type: str, osm_id: str, db: Session = Depends(get_db)):
    place_id = f"{osm_type}/{osm_id}"
    try:
        details = await places_service.get_place_details(db, place_id)
    except ProviderError:
        details = None
    name = details.name if details else osm_id
    return await cultural_service.get_cultural_info(db, place_id, name)
