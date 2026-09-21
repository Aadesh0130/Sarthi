from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr


class PhoneRequestOTP(BaseModel):
    phone: str = Field(..., description="Phone number with country code, e.g. +919876543210")


class PhoneVerifyOTP(BaseModel):
    phone: str = Field(..., description="Phone number with country code, e.g. +919876543210")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")


class PhoneResendOTP(BaseModel):
    phone: str = Field(..., description="Phone number with country code, e.g. +919876543210")


class GoogleAuthRequest(BaseModel):
    credential: str = Field(..., description="Google ID token credential from Google Identity Services")


class OnboardingRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    profile_image: Optional[str] = None
    preferred_language: str = Field(default="English", max_length=50)
    travel_interests: List[str] = Field(default_factory=list)
    home_city: Optional[str] = Field(default=None, max_length=100)


class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    profile_image: Optional[str] = None
    preferred_language: Optional[str] = None
    travel_interests: Optional[List[str]] = None
    home_city: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    profile_image: Optional[str] = None
    auth_provider: str
    google_id: Optional[str] = None
    phone_verified: bool
    email_verified: bool
    onboarding_completed: bool
    preferred_language: str
    travel_interests: List[str]
    home_city: Optional[str] = None
    created_at: Optional[str] = None
    last_login: Optional[str] = None


class TokenResponse(BaseModel):
    success: bool = True
    message: str = "Authentication successful"
    token: str
    user: UserResponse
    is_new_user: bool = False


class OTPRequestResponse(BaseModel):
    success: bool = True
    message: str = "OTP sent successfully"
    expires_in: int = 300
    resend_cooldown: int = 60


class GenericResponse(BaseModel):
    success: bool
    message: str
