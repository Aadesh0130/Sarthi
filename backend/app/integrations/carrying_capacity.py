"""
Carrying-capacity abstraction for the Tourist Flow Rebalancer.

IMPORTANT -- data honesty: Sarthi has no access to any official carrying-
capacity dataset for Indian destinations (no state tourism department feed,
no UNESCO/ASI visitor-cap register, no protected-area quota API). Nothing
here claims to be one. `EstimatedCarryingCapacityProvider` below computes a
defensible, clearly-labelled *modelled* signal from a real number Sarthi
already has for the candidate: how many tourism-related places OpenStreetMap
maps nearby (the exact same place-density figure already computed for the
Tourism Pressure Index, so this reuses that call rather than issuing a new
one). The abstraction exists so a real authoritative source (a government
tourism department's visitor-cap dataset, a protected-area quota API, etc.)
can be plugged in later as a second `CarryingCapacityProvider` implementation
without any caller needing to change.
"""
from abc import ABC, abstractmethod


class CarryingCapacityProvider(ABC):
    @abstractmethod
    def estimate(self, place_count: int) -> tuple[float, str, str]:
        """Return (0-100 suitability score -- higher means more real
        infrastructure signal to sustainably absorb redirected visitors,
        human-readable note, data_type). Pure calculation, never a network
        call, so this can never itself be "unavailable"."""
        raise NotImplementedError


class EstimatedCarryingCapacityProvider(CarryingCapacityProvider):
    """The only provider implemented right now. Always returns
    data_type="estimated" -- this is a modelled planning heuristic, never an
    official capacity figure, and callers must label it accordingly rather
    than presenting a specific number as authoritative."""

    def estimate(self, place_count: int) -> tuple[float, str, str]:
        if place_count < 3:
            return (
                35.0,
                "Very few mapped tourism-related places nearby -- limited visible infrastructure "
                "to sustainably absorb additional visitors (modelled estimate, not an official capacity figure)",
                "estimated",
            )
        if place_count <= 25:
            return (
                85.0,
                "A moderate number of mapped tourism-related places (stays, eateries, attractions) suggests "
                "reasonable real infrastructure to support additional visitors (modelled estimate)",
                "estimated",
            )
        return (
            50.0,
            "Already has considerable mapped tourism density -- real headroom for substantially more "
            "visitors here is less certain (modelled estimate, not an official capacity figure)",
            "estimated",
        )
