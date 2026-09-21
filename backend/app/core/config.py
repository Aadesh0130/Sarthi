"""
Central configuration for the Sarthi backend.

Free, no-key providers: Nominatim (geocoding), Overpass (nearby places),
OSRM (routing), Open-Meteo (weather), Wikidata/Wikipedia (cultural
fallback). Everything else below is optional and left blank by default --
each feature honestly reports itself as "not configured" instead of
pretending to work when its key is missing (spec: "never fake live data or
AI activity").
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Sarthi API"
    environment: str = "development"
    cors_origins: str = "*"

    database_url: str = "sqlite:///./sarthi.db"

    # --- Free map/geo stack (no keys required) ---
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str = "SarthiTravelApp/1.0 (SIH PS26204 prototype; contact: aadeshkaruna1@gmail.com)"
    overpass_base_url: str = "https://overpass-api.de/api/interpreter"
    osrm_base_url: str = "https://router.project-osrm.org"
    open_meteo_base_url: str = "https://api.open-meteo.com/v1/forecast"

    # --- Free cultural fallback (no keys required) ---
    wikidata_base_url: str = "https://www.wikidata.org/w/api.php"
    wikipedia_base_url: str = "https://en.wikipedia.org/api/rest_v1"

    cache_ttl_geocode: int = 86400
    cache_ttl_places: int = 3600
    cache_ttl_weather: int = 1800
    cache_ttl_route: int = 3600
    cache_ttl_events: int = 3600
    cache_ttl_hotels: int = 900  # kept short -- these are prices, per spec section 11
    cache_ttl_images: int = 86400
    cache_ttl_culture: int = 604800  # cultural facts don't change; cache a week

    # Last-resort fallback ONLY: if every live Overpass mirror fails at request
    # time, a place-search result already cached from an earlier successful
    # fetch may be reused even though it's past cache_ttl_places, up to this
    # age -- which places exist near a point doesn't meaningfully change
    # week to week. Never used instead of a live attempt, only after one has
    # already failed; the response is always labeled as cached, never shown
    # as live. A location that has never been fetched successfully before
    # still gets an honest failure if every mirror is down at that moment --
    # this narrows the free public Overpass infrastructure's real
    # reliability gaps, it can't eliminate them.
    cache_stale_grace_places: int = 604800

    # --- AI Travel Assistant: choose "openai" or "gemini" ---
    ai_provider: str = "openai"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"

    # --- Events (Ticketmaster Discovery API) ---
    ticketmaster_api_key: str = ""
    ticketmaster_base_url: str = "https://app.ticketmaster.com/discovery/v2"

    # --- Hotels (Hotelbeds / HBX Group) ---
    hotelbeds_api_key: str = ""
    hotelbeds_secret: str = ""
    hotelbeds_base_url: str = "https://api.test.hotelbeds.com"

    # --- Images (Unsplash) ---
    unsplash_access_key: str = ""
    unsplash_base_url: str = "https://api.unsplash.com"

    # --- Authentication (merged from the uploaded frontend project's own
    # auth backend -- app/models/user.py, otp.py, trip.py, services/
    # auth_service.py, sms_service.py, core/security.py all import THESE
    # settings now, not a second Settings class. Field names are kept
    # UPPERCASE, matching that project's own auth code, specifically so
    # security.py/auth_service.py/sms_service.py needed no logic changes --
    # only their `from app.config import settings` import line changed to
    # `from app.core.config import get_settings` -- one Settings class, one
    # .env, one source of truth for both subsystems. ---
    JWT_SECRET: str = "sarthi_super_secret_jwt_key_2026_change_in_production_min32chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_DAYS: int = 7

    # Google OAuth (Sign in with Google)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # SMS / OTP delivery. AUTH_DEV_MODE (or missing Twilio credentials)
    # prints the OTP to the BACKEND SERVER CONSOLE only -- never to the
    # browser console or any API response -- see sms_service.py.
    AUTH_DEV_MODE: bool = True
    SMS_PROVIDER: str = "twilio"
    SMS_ACCOUNT_SID: str = ""
    SMS_AUTH_TOKEN: str = ""
    SMS_FROM_NUMBER: str = ""

    OTP_EXPIRE_MINUTES: int = 5
    RESEND_COOLDOWN_SECONDS: int = 60
    MAX_OTP_ATTEMPTS: int = 5
    OTP_SALT: str = "sarthi_secure_otp_salt_2026"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def active_ai_key(self) -> str:
        return self.gemini_api_key if self.ai_provider.lower() == "gemini" else self.openai_api_key

    @property
    def ai_configured(self) -> bool:
        return bool(self.active_ai_key and self.active_ai_key.strip())

    @property
    def events_configured(self) -> bool:
        return bool(self.ticketmaster_api_key and self.ticketmaster_api_key.strip())

    @property
    def hotels_configured(self) -> bool:
        return bool(
            self.hotelbeds_api_key and self.hotelbeds_api_key.strip()
            and self.hotelbeds_secret and self.hotelbeds_secret.strip()
        )

    @property
    def images_configured(self) -> bool:
        return bool(self.unsplash_access_key and self.unsplash_access_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
