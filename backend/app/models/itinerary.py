from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Itinerary(Base):
    __tablename__ = "itineraries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), default="My Sarthi trip")
    destination_query: Mapped[str] = mapped_column(String(200), default="")
    start_date: Mapped[str] = mapped_column(String(20), default="")
    days: Mapped[int] = mapped_column(Integer, default=1)
    travelers: Mapped[int] = mapped_column(Integer, default=1)
    budget: Mapped[str] = mapped_column(String(20), default="comfort")
    pace: Mapped[str] = mapped_column(String(20), default="balanced")
    interests: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    items: Mapped[list["ItineraryItem"]] = relationship(
        back_populates="itinerary", cascade="all, delete-orphan", order_by="ItineraryItem.order_index"
    )


class ItineraryItem(Base):
    __tablename__ = "itinerary_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    itinerary_id: Mapped[int] = mapped_column(ForeignKey("itineraries.id"))
    day: Mapped[int] = mapped_column(Integer, default=1)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    place_id: Mapped[str] = mapped_column(String(120))  # normalized "osm_type/osm_id"
    name: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(80), default="")
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)

    suggested_time: Mapped[str] = mapped_column(String(40), default="")
    estimated_duration_minutes: Mapped[int] = mapped_column(Integer, default=90)
    notes: Mapped[str] = mapped_column(String(500), default="")

    itinerary: Mapped["Itinerary"] = relationship(back_populates="items")
