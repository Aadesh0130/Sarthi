from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class ApiCacheEntry(Base):
    """Generic TTL cache row for geocode / places / weather / route responses."""

    __tablename__ = "api_cache"

    key: Mapped[str] = mapped_column(String(512), primary_key=True)
    payload: Mapped[str] = mapped_column(String)  # JSON-encoded
    expires_at: Mapped[float] = mapped_column(Float, index=True)
