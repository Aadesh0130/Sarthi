from app.db.database import Base
from app.models.user import User
from app.models.otp import OTPVerification
from app.models.trip import SavedTrip

__all__ = ["Base", "User", "OTPVerification", "SavedTrip"]
