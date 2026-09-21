from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables if they don't exist. No destructive migrations are run.

    For the Postgres+PostGIS deployment described in the project spec, swap
    DATABASE_URL in .env and run this the same way -- the schema here uses
    plain lat/lon float columns so it works identically on SQLite (zero-setup
    local dev) and Postgres (production), with PostGIS geometry left as a
    documented future upgrade rather than a hard requirement.
    """
    from app.models import cache_entry, itinerary, cultural, crowd_demand  # noqa: F401
    # Auth models (merged from the uploaded frontend project's own auth
    # backend -- see app/core/config.py's comment on the same merge). These
    # share this exact Base/engine, not a second database.
    from app.models import user, otp, trip  # noqa: F401

    Base.metadata.create_all(bind=engine)
