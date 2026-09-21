from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.db.database import Base


class OTPVerification(Base):
    __tablename__ = "otp_verifications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    phone_number = Column(String(20), index=True, nullable=False)
    otp_hash = Column(String(255), nullable=False)
    salt = Column(String(64), nullable=False)
    expires_at = Column(DateTime, index=True, nullable=False)
    attempts = Column(Integer, default=0, nullable=False)
    verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at
