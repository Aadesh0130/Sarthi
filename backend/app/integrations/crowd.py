"""
Crowd / Tourism Pressure provider abstraction (SIH PS26204 -- Crowd
Monitoring & Tourism Pressure Engine).

IMPORTANT -- data honesty: nothing in this file or its callers has access to
real-time human crowd data (no CCTV feed, no telecom footfall data, no
government tourism statistics, no live GPS density). `EstimatedCrowdProvider`
below computes a defensible *planning* index from signals Sarthi genuinely
has: general Indian tourism seasonality, live OpenStreetMap place density,
Sarthi's own real (if sparse) usage, live weather, and live event listings
when configured. The abstraction exists so a real live-crowd data source
(a municipal footfall API, a telecom-derived density feed, etc.) could be
plugged in later as a second `CrowdProvider` implementation without any
caller needing to change -- see `app/services/crowd_service.py`.
"""
from abc import ABC, abstractmethod
from datetime import datetime


class CrowdProvider(ABC):
    @abstractmethod
    def seasonal_pressure(self, destination_label: str, when: datetime) -> tuple[float, str, str]:
        """Return (0-100 score, human label, data_type) for how "in-season" a
        destination is right now. Pure lookup/heuristic -- never a network call,
        so this can never itself be "unavailable"."""
        raise NotImplementedError


# Peak-season months (1=Jan .. 12=Dec) for well-known Indian destinations,
# reflecting widely published general tourism-season guidance (the same kind
# of "best season" fact already curated in js/data.js for the AI Planner's
# destination set) -- NOT live analytics, NOT a claim about this year
# specifically. Matched against the destination label by substring, so
# "Jaipur, Rajasthan, India" from Nominatim still matches "jaipur".
_PEAK_SEASON: dict[str, list[int]] = {
    "jaipur": [10, 11, 12, 1, 2, 3],
    "udaipur": [9, 10, 11, 12, 1, 2, 3],
    "jodhpur": [10, 11, 12, 1, 2, 3],
    "jaisalmer": [11, 12, 1, 2],
    "bikaner": [10, 11, 12, 1, 2],
    "bundi": [10, 11, 12, 1, 2, 3],
    "agra": [10, 11, 12, 1, 2, 3],
    "delhi": [10, 11, 12, 1, 2, 3],
    "amritsar": [10, 11, 12, 1, 2, 3],
    "goa": [11, 12, 1, 2],
    "rishikesh": [9, 10, 11, 3, 4, 5],
    "haridwar": [9, 10, 11, 3, 4, 5],
    "varanasi": [10, 11, 12, 1, 2, 3],
    "munnar": [9, 10, 11, 12, 1, 2, 3],
    "kerala": [9, 10, 11, 12, 1, 2, 3],
    "alleppey": [9, 10, 11, 12, 1, 2],
    "alappuzha": [9, 10, 11, 12, 1, 2],
    "hampi": [10, 11, 12, 1, 2],
    "mysuru": [10, 11, 12, 1, 2],
    "mysore": [10, 11, 12, 1, 2],
    "coorg": [10, 11, 12, 1, 2, 3],
    "gokarna": [10, 11, 12, 1, 2, 3],
    "leh": [5, 6, 7, 8, 9],
    "ladakh": [5, 6, 7, 8, 9],
    "spiti": [6, 7, 8, 9],
    "manali": [4, 5, 6, 12, 1],
    "shimla": [4, 5, 6, 12, 1],
    "darjeeling": [10, 11, 12, 3, 4, 5],
    "gangtok": [10, 11, 12, 3, 4, 5],
    "sikkim": [10, 11, 12, 3, 4, 5],
    "meghalaya": [9, 10, 11, 12, 1, 2, 3, 4],
    "shillong": [9, 10, 11, 12, 1, 2, 3, 4],
    "andaman": [10, 11, 12, 1, 2, 3, 4, 5],
    "port blair": [10, 11, 12, 1, 2, 3, 4, 5],
    "ziro": [3, 4, 5, 6, 7, 8, 9, 10],
    "kutch": [11, 12, 1, 2],
    "mumbai": [10, 11, 12, 1, 2],
    "kolkata": [10, 11, 12, 1, 2],
    "chennai": [11, 12, 1, 2],
    "ooty": [4, 5, 6, 9, 10, 11, 12],
    "kodaikanal": [4, 5, 6, 9, 10, 11, 12],
}


class EstimatedCrowdProvider(CrowdProvider):
    """The only provider implemented right now. Everything it returns is
    labelled "estimated" (or "curated" for the pure lookup pieces) -- never
    "live"."""

    def seasonal_pressure(self, destination_label: str, when: datetime) -> tuple[float, str, str]:
        label = (destination_label or "").lower()
        month = when.month

        matched_key = None
        for key in _PEAK_SEASON:
            if key in label:
                matched_key = key
                break

        if matched_key:
            peak_months = _PEAK_SEASON[matched_key]
            if month in peak_months:
                return 78.0, f"Peak travel season for {matched_key.title()}", "curated"
            # "shoulder" = one calendar month adjacent to a peak month
            shoulder = {((m - 2) % 12) + 1 for m in peak_months} | {(m % 12) + 1 for m in peak_months}
            if month in shoulder:
                return 52.0, f"Shoulder season for {matched_key.title()}", "curated"
            return 24.0, f"Off-peak season for {matched_key.title()}", "curated"

        # No curated match -- fall back to the broad, widely-published pattern
        # for Indian tourism generally (cool/dry Oct-Mar peak, hot Apr-Jun,
        # monsoon Jul-Sep quieter for most non-monsoon-tourism destinations).
        if month in (10, 11, 12, 1, 2, 3):
            return 60.0, "General North/Central India peak season (Oct-Mar)", "curated"
        if month in (4, 5, 6):
            return 40.0, "Hot season -- generally lighter tourism for most of India", "curated"
        return 30.0, "Monsoon season -- generally lighter tourism for most of India", "curated"
