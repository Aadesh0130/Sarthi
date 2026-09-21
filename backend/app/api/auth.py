"""
Authentication API -- wires the frontend's login UI to the REAL auth backend
that was already built in this project (app/models/user.py, otp.py, trip.py,
app/services/auth_service.py, sms_service.py, app/core/security.py). This
router is the one piece that was missing: everything else here already
existed and works exactly as written before this integration.

Real phone-OTP + Google Sign-In flow, JWT sessions, PostgreSQL/SQLite
persistence via SQLAlchemy -- no client-generated OTP, no OTP ever returned
in a response body or printed to the browser console (see sms_service.py:
it prints to the BACKEND SERVER's own stdout only, and only in dev mode /
when no real SMS provider is configured).
"""
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.auth import (
    GenericResponse,
    GoogleAuthRequest,
    OnboardingRequest,
    OTPRequestResponse,
    PhoneRequestOTP,
    PhoneResendOTP,
    PhoneVerifyOTP,
    ProfileUpdateRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_response(user: User) -> UserResponse:
    return UserResponse(**user.to_dict())


@router.post("/phone/request-otp", response_model=OTPRequestResponse)
def request_phone_otp(payload: PhoneRequestOTP, db: Session = Depends(get_db)):
    return AuthService.request_phone_otp(payload.phone, db)


@router.post("/phone/resend-otp", response_model=OTPRequestResponse)
def resend_phone_otp(payload: PhoneResendOTP, db: Session = Depends(get_db)):
    # Same cooldown/rate-limit path as the initial request -- there is only
    # one OTP-issuing code path, not a separate/looser "resend" one.
    return AuthService.request_phone_otp(payload.phone, db)


@router.post("/phone/verify-otp", response_model=TokenResponse)
def verify_phone_otp(payload: PhoneVerifyOTP, response: Response, db: Session = Depends(get_db)):
    token, user, is_new_user = AuthService.verify_phone_otp(payload.phone, payload.otp, db)
    # Bearer token in the JSON body is what the frontend actually uses (see
    # js/auth.js) so it works the same way whether the frontend is opened as
    # a static file, from a different port, or from a different origin than
    # the backend, without needing cross-origin cookie/credential
    # configuration. The httpOnly cookie is set as a defense-in-depth extra
    # for same-origin deployments -- app/core/security.py already accepts
    # either.
    response.set_cookie(
        "sarthi_token", token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 7,
    )
    return TokenResponse(token=token, user=_user_response(user), is_new_user=is_new_user)


@router.post("/google", response_model=TokenResponse)
def google_auth(payload: GoogleAuthRequest, response: Response, db: Session = Depends(get_db)):
    token, user, is_new_user = AuthService.verify_google_auth(payload.credential, db)
    response.set_cookie(
        "sarthi_token", token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 7,
    )
    return TokenResponse(token=token, user=_user_response(user), is_new_user=is_new_user)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return _user_response(current_user)


@router.post("/onboarding", response_model=UserResponse)
def complete_onboarding(
    payload: OnboardingRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    user = AuthService.complete_onboarding(current_user, payload, db)
    return _user_response(user)


@router.put("/profile", response_model=UserResponse)
def update_profile(
    payload: ProfileUpdateRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    user = AuthService.update_profile(current_user, payload, db)
    return _user_response(user)


@router.post("/logout", response_model=GenericResponse)
def logout(response: Response):
    response.delete_cookie("sarthi_token")
    return GenericResponse(success=True, message="Logged out.")


@router.get("/status")
def auth_status(db: Session = Depends(get_db)):
    """Not from AuthService -- a small honest capability check the frontend
    can call to know whether real SMS delivery is configured, so the login
    UI can say so plainly instead of silently behaving differently."""
    from app.core.config import get_settings

    settings = get_settings()
    has_twilio = bool(settings.SMS_ACCOUNT_SID and settings.SMS_AUTH_TOKEN and settings.SMS_FROM_NUMBER)
    return {
        "phone_auth_available": True,
        "sms_provider_configured": has_twilio and not settings.AUTH_DEV_MODE,
        "google_auth_configured": bool(settings.GOOGLE_CLIENT_ID),
        "dev_mode": settings.AUTH_DEV_MODE or not has_twilio,
    }
