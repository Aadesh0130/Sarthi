"""
Small persistent cache used to respect the usage policies of the free
providers (Nominatim, Overpass, OSRM, Open-Meteo) -- see project spec
sections 25/26. Backed by a single SQL table (api_cache) so it survives
restarts, instead of an in-memory dict that would hammer the public APIs
again every time the server reboots.
"""
import json
import time
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cache_entry import ApiCacheEntry


def cache_get(db: Session, key: str) -> Optional[Any]:
    row = db.execute(select(ApiCacheEntry).where(ApiCacheEntry.key == key)).scalar_one_or_none()
    if row is None:
        return None
    if row.expires_at < time.time():
        # Deliberately NOT deleted here: an expired row is still ignored for
        # every normal (fresh) read below, but it is left in place so
        # cache_get_stale() (a last-resort fallback for when every live
        # provider is genuinely down) can still find it. cache_set() below
        # overwrites it in place the next time a live fetch succeeds, so
        # nothing is retained forever.
        return None
    try:
        return json.loads(row.payload)
    except (json.JSONDecodeError, TypeError):
        return None


def cache_get_stale(db: Session, key: str, original_ttl_seconds: int, max_age_seconds: int) -> Optional[tuple[Any, float]]:
    """Last-resort fallback for when a live provider call has just failed:
    return a cache row even though it's past its normal freshness TTL, as
    long as it isn't older than `max_age_seconds`, plus its real age in
    seconds so the caller can label it honestly (never silently presented
    as live/fresh).

    Only ever called from a provider's except-ProviderError branch -- a
    normal cache_get() miss with a healthy provider always does a real live
    fetch first. Intended for data that stays materially true for a long
    time (e.g. which attractions/temples/museums exist near a point), never
    for anything time-sensitive like weather or hotel rates.

    The row doesn't store its own creation time, so age is derived from the
    TTL that was actually used to write it (`original_ttl_seconds`, the same
    constant the caller always passes to cache_set for this kind of key).
    """
    row = db.execute(select(ApiCacheEntry).where(ApiCacheEntry.key == key)).scalar_one_or_none()
    if row is None:
        return None
    age_seconds = time.time() - (row.expires_at - original_ttl_seconds)
    if age_seconds > max_age_seconds:
        return None
    try:
        value = json.loads(row.payload)
    except (json.JSONDecodeError, TypeError):
        return None
    return value, max(0.0, age_seconds)


def cache_set(db: Session, key: str, value: Any, ttl_seconds: int) -> None:
    payload = json.dumps(value)
    expires_at = time.time() + ttl_seconds
    row = db.execute(select(ApiCacheEntry).where(ApiCacheEntry.key == key)).scalar_one_or_none()
    if row is None:
        row = ApiCacheEntry(key=key, payload=payload, expires_at=expires_at)
        db.add(row)
    else:
        row.payload = payload
        row.expires_at = expires_at
    db.commit()
