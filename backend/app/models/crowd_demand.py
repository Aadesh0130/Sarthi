from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class DestinationDemandLog(Base):
    """Counts real lookups of the crowd-pressure endpoint per destination
    bucket (see app/services/crowd_service.py). This is the ONLY 'demand'
    signal Sarthi has any right to report: how many times SARTHI'S OWN users
    have actually looked a place up through this app. It is never conflated
    with national tourism footfall, hotel occupancy, or any other real-world
    statistic Sarthi has no access to (spec: crowd monitoring engine, data
    honesty rules)."""

    __tablename__ = "destination_demand"

    bucket_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    query_count: Mapped[int] = mapped_column(Integer, default=0)
    last_queried_at: Mapped[float] = mapped_column(Float, default=0.0)
