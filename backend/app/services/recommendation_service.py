"""
Explainable SmartScore recommendation engine for real places (project spec
section 14). This mirrors the spirit of the existing curated-destination
SmartScore in js/data.js, but scores real OSM places returned by Overpass.

This is deterministic weighted scoring, NOT machine learning, and the code
says so explicitly in the response (`is_machine_learning: False`) so nobody
mistakes it for something it isn't. The weights and factors are documented
here so the architecture can grow into a learned model later without
changing the API shape.
"""
from app.schemas.place import Place
from app.schemas.recommendation import RecommendationCriteria, RecommendationResponse, ScoredPlace

# Rough category -> interest tag mapping so "heritage", "food" etc. from the
# UI can match real OSM categories.
INTEREST_TO_CATEGORIES: dict[str, list[str]] = {
    "heritage": ["historic", "museum", "attraction"],
    "culture": ["museum", "religious", "historic"],
    "history": ["historic", "museum"],
    "spiritual": ["religious"],
    "nature": ["park"],
    "food": ["restaurant", "cafe"],
    "shopping": ["shopping"],
    "adventure": ["park", "attraction"],
    "offbeat": ["attraction", "historic"],
    "beach": ["attraction", "park"],
    "romantic": ["park", "attraction"],
    "nightlife": ["restaurant", "cafe"],
}

# Indoor/outdoor classification used against current weather suitability.
INDOOR_CATEGORIES = {"museum", "restaurant", "cafe", "shopping", "hotel"}
OUTDOOR_CATEGORIES = {"park", "historic", "attraction"}
FLEXIBLE_CATEGORIES = {"religious", "other"}

DEFAULT_DURATION_MINUTES = {
    "attraction": 90, "museum": 90, "historic": 75, "religious": 45,
    "park": 60, "restaurant": 60, "cafe": 30, "shopping": 45, "hotel": 0, "other": 60,
}


def _interest_match_score(place: Place, interests: list[str]) -> tuple[int, str]:
    if not interests:
        return 70, "No specific interests selected -- broad appeal baseline"
    wanted_categories: set[str] = set()
    for interest in interests:
        wanted_categories.update(INTEREST_TO_CATEGORIES.get(interest.lower(), []))
    if place.category in wanted_categories:
        return 100, f"Matches your interest in {', '.join(i for i in interests if place.category in INTEREST_TO_CATEGORIES.get(i.lower(), []))}"
    return 25, f"Different vibe from your selected interests ({place.category})"


def _proximity_score(distance_m: float | None, radius_m: float = 3000.0) -> tuple[int, str]:
    if distance_m is None:
        return 50, "Distance unknown"
    ratio = max(0.0, min(1.0, 1 - (distance_m / radius_m)))
    score = round(40 + ratio * 60)
    if distance_m < 500:
        label = f"Very close ({round(distance_m)} m away)"
    elif distance_m < 1500:
        label = f"Close by ({distance_m / 1000:.1f} km away)"
    else:
        label = f"{distance_m / 1000:.1f} km away"
    return score, label


def _weather_score(place: Place, weather_condition: str | None) -> tuple[int, str]:
    if not weather_condition:
        return 70, "Weather not factored in"
    if place.category in INDOOR_CATEGORIES:
        if weather_condition == "poor":
            return 100, "Indoor option -- great choice while the weather is poor"
        return 70, "Indoor option"
    if place.category in OUTDOOR_CATEGORIES:
        if weather_condition == "poor":
            return 25, "Outdoor spot -- current weather is poor for this"
        if weather_condition == "good":
            return 100, "Outdoor spot -- fits today's good weather"
        return 60, "Outdoor spot -- weather is only fair right now"
    return 70, "Weather-flexible"


def _time_fit_score(place: Place, available_hours: float | None) -> tuple[int, str]:
    duration_min = DEFAULT_DURATION_MINUTES.get(place.category, 60)
    if available_hours is None:
        return 70, f"Typical visit ~{duration_min} min"
    available_min = available_hours * 60
    if duration_min <= available_min:
        return 100, f"Fits your available time (~{duration_min} min visit)"
    return 30, f"May not fit your remaining time (~{duration_min} min needed)"


def _rating_score(place: Place) -> tuple[int, str]:
    if place.rating is None:
        return 70, "No traveller rating available from OpenStreetMap"
    score = round((place.rating / 5.0) * 100)
    return score, f"★ {place.rating} rating"


def _distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import atan2, cos, radians, sin, sqrt
    r = 6371.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return r * 2 * atan2(sqrt(a), sqrt(1 - a))


def _context_bonus(place: Place, criteria: RecommendationCriteria) -> tuple[int, list[str]]:
    """Small additive bonus (spec section 6) from live event/hotel context,
    when Ticketmaster/Hotelbeds are configured and returned something near
    this place. Capped so it can only ever push a score up, never replace
    the core weighted factors above -- and it's a no-op (0, []) whenever
    nearby_events/nearby_hotels are empty, which is also the honest state
    when those providers aren't configured."""
    bonus = 0
    reasons: list[str] = []

    for event in criteria.nearby_events:
        if event.latitude is None or event.longitude is None:
            continue
        if _distance_km(place.latitude, place.longitude, event.latitude, event.longitude) <= 1.0:
            bonus += 4
            reasons.append(f"🎉 A live event ({event.name}) is happening nearby")
            break

    for hotel in criteria.nearby_hotels:
        if hotel.latitude is None or hotel.longitude is None:
            continue
        if hotel.rates and _distance_km(place.latitude, place.longitude, hotel.latitude, hotel.longitude) <= 1.5:
            bonus += 3
            reasons.append(f"🏨 A hotel with available rates ({hotel.name}) is close by")
            break

    return min(bonus, 8), reasons


def score_places(criteria: RecommendationCriteria) -> RecommendationResponse:
    weights = {
        "interest_match": 0.35,
        "proximity": 0.20,
        "weather_fit": 0.20,
        "time_fit": 0.15,
        "rating": 0.10,
    }
    scored: list[ScoredPlace] = []
    for place in criteria.candidate_places:
        interest_s, interest_l = _interest_match_score(place, criteria.interests)
        prox_s, prox_l = _proximity_score(place.distance_meters)
        weather_s, weather_l = _weather_score(place, criteria.weather_condition)
        time_s, time_l = _time_fit_score(place, criteria.available_hours)
        rating_s, rating_l = _rating_score(place)

        breakdown = {
            "interest_match": round(interest_s * weights["interest_match"]),
            "proximity": round(prox_s * weights["proximity"]),
            "weather_fit": round(weather_s * weights["weather_fit"]),
            "time_fit": round(time_s * weights["time_fit"]),
            "rating": round(rating_s * weights["rating"]),
        }
        bonus, bonus_reasons = _context_bonus(place, criteria)
        breakdown["context_bonus"] = bonus
        total = max(0, min(100, sum(breakdown.values())))

        reasons = []
        if interest_s >= 70:
            reasons.append(f"✓ {interest_l}")
        if prox_s >= 70:
            reasons.append(f"✓ {prox_l}")
        if weather_s >= 70:
            reasons.append(f"✓ {weather_l}")
        if time_s >= 70:
            reasons.append(f"✓ {time_l}")
        if place.rating is not None and rating_s >= 70:
            reasons.append(f"✓ {rating_l}")
        reasons.extend(bonus_reasons)
        if not reasons:
            reasons.append("Matches your general search area")

        scored.append(ScoredPlace(place=place, smart_score=total, reasons=reasons, breakdown=breakdown))

    scored.sort(key=lambda sp: sp.smart_score, reverse=True)
    return RecommendationResponse(
        criteria_echo=criteria.model_dump(exclude={"candidate_places"}),
        results=scored,
    )
