"""
Provider abstractions (project spec section 26).

Every external data source Sarthi uses today (Nominatim, Overpass, OSRM,
Open-Meteo) is accessed only through one of these interfaces. Swapping to a
paid provider later (Google, Mapbox, HERE, OpenWeather, ...) means writing a
new class that implements the same interface -- no change needed anywhere
else in the app.
"""
from abc import ABC, abstractmethod
from typing import Optional

from app.schemas.event import EventResult
from app.schemas.hotel import HotelRateCheck, HotelResult
from app.schemas.image import ImageResult
from app.schemas.place import GeocodeResult, Place, PlaceDetails
from app.schemas.route import RouteResponse, RouteStop
from app.schemas.weather import WeatherResponse


class GeocodingProvider(ABC):
    @abstractmethod
    async def search(self, query: str, limit: int = 5) -> list[GeocodeResult]:
        ...

    @abstractmethod
    async def reverse(self, latitude: float, longitude: float) -> Optional[GeocodeResult]:
        ...


class PlacesProvider(ABC):
    @abstractmethod
    async def nearby(
        self, latitude: float, longitude: float, radius_meters: int, categories: list[str]
    ) -> list[Place]:
        ...

    @abstractmethod
    async def get_details(self, place_id: str) -> Optional[PlaceDetails]:
        ...


class RoutingProvider(ABC):
    @abstractmethod
    async def route(self, stops: list[RouteStop], profile: str) -> RouteResponse:
        ...


class WeatherProvider(ABC):
    @abstractmethod
    async def forecast(self, latitude: float, longitude: float) -> WeatherResponse:
        ...


class EventProvider(ABC):
    """Real event listings (spec section 4C). Coverage varies a lot by
    market -- an empty result is a valid, honest answer, never a reason to
    invent an event."""

    @abstractmethod
    async def search(
        self, latitude: float, longitude: float, radius_km: int = 25,
        keyword: str = "", start_date: Optional[str] = None, end_date: Optional[str] = None,
    ) -> list[EventResult]:
        ...

    @abstractmethod
    async def get_details(self, event_id: str) -> Optional[EventResult]:
        ...


class HotelProvider(ABC):
    """Hotel content/availability/rate-check (spec section 4D). Search and
    content are safe to show broadly; live rates must be re-validated
    ("check-rate") before being presented as bookable, per provider policy."""

    @abstractmethod
    async def search(
        self, latitude: float, longitude: float, check_in: str, check_out: str,
        adults: int = 2, radius_km: int = 15,
    ) -> list[HotelResult]:
        ...

    @abstractmethod
    async def check_rate(self, rate_key: str) -> HotelRateCheck:
        ...


class ImageProvider(ABC):
    """Attribution-carrying destination/attraction imagery (spec section 4F).
    Never returns a fabricated URL -- an empty list means "no relevant photo
    found", and the caller falls back to a local placeholder."""

    @abstractmethod
    async def search(self, query: str, count: int = 3) -> list[ImageResult]:
        ...


class AIChatResult:
    """Normalized result of one round of LLM chat-with-tools, independent of
    which provider produced it.

    `assistant_message` is the generic-form assistant turn the caller should
    append to its running history before the next round: e.g.
    {"role": "assistant", "content": "...", "tool_calls": [{"id", "name", "arguments"}]}.
    """

    def __init__(self, text: str | None = None, tool_calls: list[dict] | None = None, assistant_message: dict | None = None):
        self.text = text
        self.tool_calls = tool_calls or []  # [{"id": str, "name": str, "arguments": dict}]
        self.assistant_message = assistant_message or {"role": "assistant", "content": text or ""}


class AIProvider(ABC):
    """A conversational LLM backend for the AI Travel Assistant (spec
    section 4E), restricted to Sarthi's own tool functions. Two
    implementations exist (OpenAI, Gemini) selected by AI_PROVIDER so either
    can be the active assistant without touching app/services/ai_service.py
    or app/ai/tools.py.

    `messages` is a provider-agnostic history using a simplified OpenAI-like
    shape (see AIChatResult docstring); each provider translates the full
    history into its own native request format on every call. `tools` is a
    bare list of {"name", "description", "parameters"} (no OpenAI/Gemini
    wrapper) that each provider wraps as its API requires.
    """

    name: str = "unknown"

    @abstractmethod
    async def chat(self, system_prompt: str, messages: list[dict], tools: list[dict]) -> AIChatResult:
        ...

    async def analyze_image(self, image_bytes: bytes, mime_type: str, prompt: str) -> AIChatResult:
        """Vision analysis for photo-based place identification (spec section 15).
        Default: not supported -- a provider must opt in by overriding this.
        Returns plain text (expected to be a JSON string); the caller parses it."""
        raise ProviderError(self.name, "This AI provider does not support image analysis.")


class ProviderError(RuntimeError):
    """Raised when an upstream provider is unavailable, rate-limited or
    returns something we can't parse. Callers turn this into a clear
    'temporarily unavailable' API response -- never into fabricated data.
    """

    def __init__(self, provider: str, detail: str):
        self.provider = provider
        # Guard at the source: a blank/whitespace-only detail (some httpx
        # exceptions stringify to "") must never reach the user as a malformed
        # message like "temporarily unavailable ( ; ; )." -- always fall back
        # to something a person can actually read.
        self.detail = detail.strip() if detail and detail.strip() else f"{provider} reported no further detail"
        super().__init__(f"{provider}: {self.detail}")
