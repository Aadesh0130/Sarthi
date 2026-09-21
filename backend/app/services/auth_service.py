from datetime import datetime, timedelta
from typing import Tuple, Optional
from fastapi import HTTPException, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    generate_secure_otp,
    generate_salt,
    hash_otp,
    verify_otp_hash,
    create_access_token,
)
from app.models.otp import OTPVerification
from app.models.user import User
from app.schemas.auth import OnboardingRequest, ProfileUpdateRequest
from app.services.sms_service import SMSService
from app.utils.validators import normalize_and_validate_phone

settings = get_settings()


class AuthService:
    @staticmethod
    def request_phone_otp(raw_phone: str, db: Session) -> dict:
        """
        Validates phone number, enforces rate-limiting and cooldown,
        generates and stores hashed OTP, and triggers SMS delivery.
        """
        phone = normalize_and_validate_phone(raw_phone)
        now = datetime.utcnow()

        # Check resend cooldown
        cooldown_threshold = now - timedelta(seconds=settings.RESEND_COOLDOWN_SECONDS)
        recent_otp = (
            db.query(OTPVerification)
            .filter(
                OTPVerification.phone_number == phone,
                OTPVerification.created_at > cooldown_threshold,
                OTPVerification.verified == False,
            )
            .order_by(OTPVerification.created_at.desc())
            .first()
        )
        if recent_otp:
            seconds_elapsed = int((now - recent_otp.created_at).total_seconds())
            remaining = max(1, settings.RESEND_COOLDOWN_SECONDS - seconds_elapsed)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {remaining} seconds before requesting a new code.",
            )

        # Check hourly rate limit (max 5 requests per hour)
        hour_ago = now - timedelta(hours=1)
        recent_count = (
            db.query(OTPVerification)
            .filter(
                OTPVerification.phone_number == phone,
                OTPVerification.created_at > hour_ago,
            )
            .count()
        )
        if recent_count >= 10:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many verification attempts for this number today. Please try again later.",
            )

        # Invalidate existing active OTPs for this phone
        db.query(OTPVerification).filter(
            OTPVerification.phone_number == phone,
            OTPVerification.verified == False,
        ).update({"verified": True})

        # Generate secure OTP and per-record salt
        plain_otp = generate_secure_otp(6)
        salt = generate_salt(16)
        hashed_otp = hash_otp(plain_otp, salt)
        expires_at = now + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)

        new_otp_record = OTPVerification(
            phone_number=phone,
            otp_hash=hashed_otp,
            salt=salt,
            expires_at=expires_at,
            attempts=0,
            verified=False,
            created_at=now,
        )
        db.add(new_otp_record)
        db.commit()

        # Send OTP via SMS service (or dev console)
        SMSService.send_otp(phone, plain_otp, settings.OTP_EXPIRE_MINUTES)

        return {
            "success": True,
            "message": "Verification code sent successfully.",
            "expires_in": settings.OTP_EXPIRE_MINUTES * 60,
            "resend_cooldown": settings.RESEND_COOLDOWN_SECONDS,
        }

    @staticmethod
    def verify_phone_otp(raw_phone: str, submitted_otp: str, db: Session) -> Tuple[str, User, bool]:
        """
        Verifies submitted OTP against hashed database record.
        On success, logs in or creates user and issues JWT.
        Returns: (jwt_token, user_object, is_new_user)
        """
        phone = normalize_and_validate_phone(raw_phone)
        now = datetime.utcnow()

        # Retrieve the latest active OTP record
        otp_record = (
            db.query(OTPVerification)
            .filter(
                OTPVerification.phone_number == phone,
                OTPVerification.verified == False,
            )
            .order_by(OTPVerification.created_at.desc())
            .first()
        )

        if not otp_record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No pending verification code found. Please request a new OTP.",
            )

        if otp_record.is_expired:
            otp_record.verified = True
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code has expired. Please request a new code.",
            )

        if otp_record.attempts >= settings.MAX_OTP_ATTEMPTS:
            otp_record.verified = True
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many failed attempts. This code has been invalidated. Please request a new OTP.",
            )

        # Constant-time comparison
        is_valid = verify_otp_hash(submitted_otp, otp_record.salt, otp_record.otp_hash)

        if not is_valid:
            otp_record.attempts += 1
            db.commit()
            remaining = settings.MAX_OTP_ATTEMPTS - otp_record.attempts
            if remaining <= 0:
                otp_record.verified = True
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Too many failed attempts. Please request a new verification code.",
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid verification code. Please try again. ({remaining} attempt{'s' if remaining > 1 else ''} remaining)",
            )

        # Mark OTP as verified
        otp_record.verified = True
        db.commit()

        # Find or create user
        user = db.query(User).filter(User.phone_number == phone).first()
        is_new_user = False

        if user:
            user.phone_verified = True
            user.last_login = now
            is_new_user = not user.onboarding_completed
        else:
            user = User(
                phone_number=phone,
                phone_verified=True,
                auth_provider="phone",
                onboarding_completed=False,
                created_at=now,
                last_login=now,
            )
            db.add(user)
            is_new_user = True

        db.commit()
        db.refresh(user)

        token = create_access_token({"sub": str(user.id), "phone": user.phone_number})
        return token, user, is_new_user

    @staticmethod
    def verify_google_auth(credential: str, db: Session) -> Tuple[str, User, bool]:
        """
        Verifies Google Identity Services ID token using Google's public keys.
        Creates or links user account and returns JWT token.
        """
        now = datetime.utcnow()
        try:
            # When GOOGLE_CLIENT_ID is set, verify against it; otherwise verify signature
            client_id = settings.GOOGLE_CLIENT_ID if settings.GOOGLE_CLIENT_ID else None
            id_info = id_token.verify_oauth2_token(
                credential,
                google_requests.Request(),
                client_id
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid Google authentication token: {str(e)}",
            )

        google_id = id_info.get("sub")
        email = id_info.get("email")
        name = id_info.get("name")
        picture = id_info.get("picture")

        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Google account did not provide an email address.",
            )

        # Check existing user by google_id or email
        user = db.query(User).filter(
            (User.google_id == google_id) | (User.email == email)
        ).first()

        is_new_user = False

        if user:
            if not user.google_id:
                user.google_id = google_id
            if not user.profile_image and picture:
                user.profile_image = picture
            if not user.full_name and name:
                user.full_name = name
            user.email_verified = True
            user.last_login = now
            is_new_user = not user.onboarding_completed
        else:
            user = User(
                google_id=google_id,
                email=email,
                full_name=name,
                profile_image=picture,
                auth_provider="google",
                email_verified=True,
                onboarding_completed=False,
                created_at=now,
                last_login=now,
            )
            db.add(user)
            is_new_user = True

        db.commit()
        db.refresh(user)

        token = create_access_token({"sub": str(user.id), "email": user.email})
        return token, user, is_new_user

    @staticmethod
    def complete_onboarding(user: User, data: OnboardingRequest, db: Session) -> User:
        """
        Updates profile for first-time user and marks onboarding as completed.
        """
        user.full_name = data.full_name.strip()
        user.preferred_language = data.preferred_language
        user.travel_interests = data.travel_interests
        if data.home_city:
            user.home_city = data.home_city.strip()
        if data.profile_image:
            user.profile_image = data.profile_image

        # Handle optional email update if user registered via phone
        if data.email and not user.email:
            existing = db.query(User).filter(User.email == data.email, User.id != user.id).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This email address is already linked to another account.",
                )
            user.email = str(data.email)

        # Handle optional phone update if user registered via Google
        if data.phone_number and not user.phone_number:
            normalized = normalize_and_validate_phone(data.phone_number)
            existing = db.query(User).filter(User.phone_number == normalized, User.id != user.id).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This phone number is already linked to another account.",
                )
            user.phone_number = normalized

        user.onboarding_completed = True
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def update_profile(user: User, data: ProfileUpdateRequest, db: Session) -> User:
        """Updates user profile information."""
        if data.full_name is not None:
            user.full_name = data.full_name.strip()
        if data.profile_image is not None:
            user.profile_image = data.profile_image
        if data.preferred_language is not None:
            user.preferred_language = data.preferred_language
        if data.travel_interests is not None:
            user.travel_interests = data.travel_interests
        if data.home_city is not None:
            user.home_city = data.home_city.strip()

        if data.email is not None and data.email != user.email:
            existing = db.query(User).filter(User.email == data.email, User.id != user.id).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="This email address is already associated with another account.",
                )
            user.email = str(data.email)

        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        return user
