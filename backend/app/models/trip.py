from datetime import datetime
import json
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.database import Base


class SavedTrip(Base):
    __tablename__ = "saved_trips"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    destination_id = Column(String(50), nullable=False)
    title = Column(String(200), nullable=False)
    days = Column(Integer, default=1, nullable=False)
    budget_style = Column(String(50), default="comfort", nullable=False)
    total_cost = Column(Integer, default=0, nullable=False)
    _trip_data = Column("trip_data", Text, default="{}", nullable=False)
    status = Column(String(50), default="saved", nullable=False)  # "saved", "booked"
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="saved_trips")

    @property
    def trip_data(self) -> dict:
        try:
            return json.loads(self._trip_data)
        except Exception:
            return {}

    @trip_data.setter
    def trip_data(self, val: dict):
        self._trip_data = json.dumps(val)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "destination_id": self.destination_id,
            "title": self.title,
            "days": self.days,
            "budget_style": self.budget_style,
            "total_cost": self.total_cost,
            "trip_data": self.trip_data,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
