from datetime import datetime
import json
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String(120), nullable=True)
    email = Column(String(255), unique=True, index=True, nullable=True)
    phone_number = Column(String(20), unique=True, index=True, nullable=True)
    profile_image = Column(String(500), nullable=True)
    auth_provider = Column(String(30), default="phone")  # "phone", "google"
    google_id = Column(String(255), unique=True, index=True, nullable=True)
    
    phone_verified = Column(Boolean, default=False, nullable=False)
    email_verified = Column(Boolean, default=False, nullable=False)
    onboarding_completed = Column(Boolean, default=False, nullable=False)
    
    preferred_language = Column(String(50), default="English", nullable=False)
    _travel_interests = Column("travel_interests", Text, default="[]", nullable=False)
    home_city = Column(String(100), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, default=datetime.utcnow, nullable=False)

    saved_trips = relationship("SavedTrip", back_populates="user", cascade="all, delete-orphan")

    @property
    def travel_interests(self) -> list[str]:
        if not self._travel_interests:
            return []
        try:
            return json.loads(self._travel_interests)
        except Exception:
            return [x.strip() for x in self._travel_interests.split(",") if x.strip()]

    @travel_interests.setter
    def travel_interests(self, val):
        if isinstance(val, list):
            self._travel_interests = json.dumps(val)
        elif isinstance(val, str):
            self._travel_interests = val
        else:
            self._travel_interests = "[]"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "phone_number": self.phone_number,
            "profile_image": self.profile_image,
            "auth_provider": self.auth_provider,
            "google_id": self.google_id,
            "phone_verified": self.phone_verified,
            "email_verified": self.email_verified,
            "onboarding_completed": self.onboarding_completed,
            "preferred_language": self.preferred_language,
            "travel_interests": self.travel_interests,
            "home_city": self.home_city,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }
