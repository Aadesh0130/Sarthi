import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import get_db
from app.models.user import User

settings = get_settings()

security_scheme = HTTPBearer(auto_error=False)


def generate_secure_otp(length: int = 6) -> str:
    """Generates a cryptographically secure numeric OTP."""
    # e.g., 6 digits between 100000 and 999999
    return str(secrets.randbelow(900000) + 100000)


def generate_salt(length: int = 16) -> str:
    """Generates a random hex salt."""
    return secrets.token_hex(length)


def hash_otp(otp: str, salt: str) -> str:
    """
    Hashes OTP using HMAC-SHA256 with application secret and per-OTP salt.
    Ensures OTP is never stored in plaintext in the database.
    """
    key = (settings.JWT_SECRET + settings.OTP_SALT + salt).encode("utf-8")
    return hmac.new(key, otp.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_otp_hash(plain_otp: str, salt: str, hashed_otp: str) -> bool:
    """Constant-time verification of OTP hash to prevent timing attacks."""
    calculated_hash = hash_otp(plain_otp, salt)
    return secrets.compare_digest(calculated_hash, hashed_otp)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a signed JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=settings.ACCESS_TOKEN_EXPIRE_DAYS)

    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """Decodes and verifies a JWT token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate authentication credentials or session expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    request: Request,
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Retrieves the currently authenticated user from Bearer header or HTTP-only cookie.
    Raises 401 if missing, invalid, or expired.
    """
    token = None
    if auth_header and auth_header.credentials:
        token = auth_header.credentials
    elif "sarthi_token" in request.cookies:
        token = request.cookies.get("sarthi_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
