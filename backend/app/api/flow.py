from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.flow_rebalance import RebalanceRequest, RebalanceResponse
from app.services import flow_rebalancer_service

router = APIRouter(prefix="/api/flow", tags=["flow"])


@router.post("/rebalance", response_model=RebalanceResponse)
async def rebalance(payload: RebalanceRequest, db: Session = Depends(get_db)):
    """Tourist Flow Rebalancer (SIH PS26204 core differentiator): given a
    requested destination, checks its real Tourism Pressure Index and, when
    elevated, returns explainable lower-pressure alternatives. Deliberately
    never raises -- a provider failure degrades one factor of the scoring
    (same pattern as /api/crowd/pressure), never the whole response, so
    Explore can never break because of this feature."""
    try:
        return await flow_rebalancer_service.rebalance(db, payload)
    except Exception:
        return RebalanceResponse(message="The Tourist Flow Rebalancer is temporarily unavailable. Try again in a moment.")
