from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.ai import ChatRequest, ChatResponse
from app.schemas.ai_plan import AIPlanRequest, AIPlanResponse, AIReplanRequest
from app.schemas.photo_id import PhotoIdentificationResponse
from app.services import ai_planner_service, photo_id_service
from app.services.ai_service import run_chat

router = APIRouter(prefix="/api/ai", tags=["ai"])

MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8MB -- generous for a phone photo, small enough to keep Gemini calls fast
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    return await run_chat(db, payload.messages)


@router.post("/plan-trip", response_model=AIPlanResponse)
async def plan_trip(payload: AIPlanRequest, db: Session = Depends(get_db)):
    """AI-reasoned itinerary over real retrieved places (spec sections 13/14).
    Always returns 200 with a clear `message`/`configured` on any failure --
    never a 500 with a raw traceback (spec section 28)."""
    return await ai_planner_service.generate_trip(db, payload)


@router.post("/replan-trip", response_model=AIPlanResponse)
async def replan_trip(payload: AIReplanRequest, db: Session = Depends(get_db)):
    """Dynamic AI replanning from a free-text instruction (spec section 22)."""
    return await ai_planner_service.replan_trip(db, payload)


@router.post("/analyze-image", response_model=PhotoIdentificationResponse)
async def analyze_image(db: Session = Depends(get_db), file: UploadFile = File(...)):
    """Photo-based place identification with independent verification (spec
    sections 15/16). multipart/form-data, field name "file"."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported image type '{file.content_type}'. Use JPEG, PNG, WEBP or HEIC.")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail=f"Image is too large (max {MAX_IMAGE_BYTES // (1024 * 1024)}MB).")
    return await photo_id_service.identify_place(db, data, file.content_type)
