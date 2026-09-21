from sqlalchemy.orm import Session, joinedload

from app.models.itinerary import Itinerary, ItineraryItem
from app.schemas.itinerary import ItineraryCreate, ItineraryUpdate
from app.schemas.place import Place
from app.schemas.recommendation import RecommendationCriteria
from app.services import recommendation_service


def create_itinerary(db: Session, data: ItineraryCreate) -> Itinerary:
    itinerary = Itinerary(
        title=data.title,
        destination_query=data.destination_query,
        start_date=data.start_date,
        days=data.days,
        travelers=data.travelers,
        budget=data.budget,
        pace=data.pace,
        interests=data.interests,
    )
    db.add(itinerary)
    db.flush()
    for idx, item in enumerate(data.items):
        db.add(ItineraryItem(itinerary_id=itinerary.id, order_index=idx, **item.model_dump()))
    db.commit()
    db.refresh(itinerary)
    return get_itinerary(db, itinerary.id)


def get_itinerary(db: Session, itinerary_id: int) -> Itinerary | None:
    return (
        db.query(Itinerary)
        .options(joinedload(Itinerary.items))
        .filter(Itinerary.id == itinerary_id)
        .first()
    )


def list_itineraries(db: Session) -> list[Itinerary]:
    return db.query(Itinerary).options(joinedload(Itinerary.items)).order_by(Itinerary.updated_at.desc()).all()


def update_itinerary(db: Session, itinerary_id: int, data: ItineraryUpdate) -> Itinerary | None:
    itinerary = db.query(Itinerary).filter(Itinerary.id == itinerary_id).first()
    if itinerary is None:
        return None

    for field in ("title", "days", "travelers", "budget", "pace", "interests"):
        value = getattr(data, field)
        if value is not None:
            setattr(itinerary, field, value)

    if data.items is not None:
        db.query(ItineraryItem).filter(ItineraryItem.itinerary_id == itinerary_id).delete()
        for idx, item in enumerate(data.items):
            db.add(ItineraryItem(itinerary_id=itinerary_id, order_index=idx, **item.model_dump()))

    db.commit()
    return get_itinerary(db, itinerary_id)


def delete_itinerary(db: Session, itinerary_id: int) -> bool:
    itinerary = db.query(Itinerary).filter(Itinerary.id == itinerary_id).first()
    if itinerary is None:
        return False
    db.delete(itinerary)
    db.commit()
    return True


# Categories treated as indoor-friendly for weather-triggered replanning.
_INDOOR = {"museum", "restaurant", "cafe", "shopping", "hotel", "religious"}


def replan_for_weather(db: Session, itinerary_id: int, poor_weather_days: set[int]) -> Itinerary | None:
    """Deterministic replanning: on a day flagged as poor-weather, indoor
    items are moved earlier in that day's order and a note is attached.
    This is NOT a live/real-time trigger by itself -- callers decide which
    days are "poor weather" using the real Open-Meteo forecast (see
    api/itineraries.py) and pass that in explicitly, per spec section 18
    ('sensible deterministic replanning', 'never fake real-time changes').
    """
    itinerary = get_itinerary(db, itinerary_id)
    if itinerary is None:
        return None

    for day_num in poor_weather_days:
        day_items = [i for i in itinerary.items if i.day == day_num]
        day_items.sort(key=lambda i: (0 if i.category in _INDOOR else 1, i.order_index))
        for idx, item in enumerate(day_items):
            item.order_index = idx
            if item.category not in _INDOOR:
                item.notes = (item.notes + " " if item.notes else "") + "[Sarthi: consider swapping -- outdoor spot on a poor-weather day]"
    db.commit()
    return get_itinerary(db, itinerary_id)


def replan_remove_place(db: Session, itinerary_id: int, place_id: str) -> Itinerary | None:
    """Drop a place the traveller no longer wants and re-sequence the day(s)
    it was in (spec section 8: 'user removes a destination'). Deterministic:
    no data is fetched, items are simply re-indexed."""
    itinerary = get_itinerary(db, itinerary_id)
    if itinerary is None:
        return None

    removed = [i for i in itinerary.items if i.place_id == place_id]
    if not removed:
        return itinerary

    affected_days = {i.day for i in removed}
    for item in removed:
        db.delete(item)
    db.flush()

    remaining = [i for i in itinerary.items if i.place_id != place_id]
    for day_num in affected_days:
        day_items = sorted([i for i in remaining if i.day == day_num], key=lambda i: i.order_index)
        for idx, item in enumerate(day_items):
            item.order_index = idx
    db.commit()
    return get_itinerary(db, itinerary_id)


def replan_time_limited(db: Session, itinerary_id: int, day: int, new_available_hours: float) -> Itinerary | None:
    """Trim a day's plan to fit fewer available hours (spec section 8: 'time
    becomes limited'). Keeps items in their existing priority order (lowest
    order_index first) until the running total would exceed the new budget,
    dropping the rest and explaining why on the last kept item -- never
    silently producing an impossible schedule."""
    itinerary = get_itinerary(db, itinerary_id)
    if itinerary is None:
        return None

    day_items = sorted([i for i in itinerary.items if i.day == day], key=lambda i: i.order_index)
    if not day_items:
        return itinerary

    budget_minutes = new_available_hours * 60
    running = 0.0
    to_drop = []
    for item in day_items:
        running += item.estimated_duration_minutes
        if running > budget_minutes:
            to_drop.append(item)

    if to_drop:
        kept = [i for i in day_items if i not in to_drop]
        if kept:
            kept[-1].notes = (
                (kept[-1].notes + " " if kept[-1].notes else "")
                + f"[Sarthi: {len(to_drop)} later stop(s) removed -- only {new_available_hours:.1f}h available today]"
            )
        for item in to_drop:
            db.delete(item)
        db.flush()
        for idx, item in enumerate(kept):
            item.order_index = idx

    db.commit()
    return get_itinerary(db, itinerary_id)


def replan_preferences_changed(
    db: Session, itinerary_id: int, new_interests: list[str] | None, new_pace: str | None, new_budget: str | None,
) -> Itinerary | None:
    """Re-score every remaining item against updated interests/pace/budget
    and reorder each day accordingly (spec section 8: 'user changes
    preferences'). Uses the same deterministic SmartScore engine as the
    real-data recommendations -- no live data is fetched, only re-weighting
    of what's already in the itinerary."""
    itinerary = get_itinerary(db, itinerary_id)
    if itinerary is None:
        return None

    interests = new_interests if new_interests is not None else itinerary.interests
    pace = new_pace or itinerary.pace
    budget = new_budget or itinerary.budget
    itinerary.interests = interests
    itinerary.pace = pace
    itinerary.budget = budget

    days = {i.day for i in itinerary.items}
    for day_num in days:
        day_items = [i for i in itinerary.items if i.day == day_num]
        places = [
            Place(
                id=i.place_id, external_id=i.place_id, source="itinerary", source_url=None,
                name=i.name, category=i.category or "other", latitude=i.latitude, longitude=i.longitude,
            )
            for i in day_items
        ]
        if not places:
            continue
        criteria = RecommendationCriteria(
            latitude=places[0].latitude, longitude=places[0].longitude,
            interests=interests, pace=pace, budget=budget, candidate_places=places,
        )
        scored = recommendation_service.score_places(criteria)
        score_by_id = {sp.place.id: sp.smart_score for sp in scored.results}
        day_items.sort(key=lambda i: score_by_id.get(i.place_id, 0), reverse=True)
        for idx, item in enumerate(day_items):
            item.order_index = idx
            item.notes = (
                (item.notes + " " if item.notes and "[Sarthi: re-ordered" not in item.notes else "")
                + f"[Sarthi: re-ordered for updated preferences -- SmartScore {score_by_id.get(item.place_id, 0)}]"
            )
    db.commit()
    return get_itinerary(db, itinerary_id)
