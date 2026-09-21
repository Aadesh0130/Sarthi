import hashlib

from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
from app.core.config import get_settings
from app.integrations.open_meteo import OpenMeteoProvider
from app.schemas.weather import WeatherResponse

settings = get_settings()
_provider = OpenMeteoProvider()


async def get_weather(db: Session, latitude: float, longitude: float) -> WeatherResponse:
    key = f"weather:{hashlib.sha1(f'{latitude:.3f},{longitude:.3f}'.encode()).hexdigest()}"
    cached = cache_get(db, key)
    if cached is not None:
        return WeatherResponse(**cached)

    weather = await _provider.forecast(latitude, longitude)
    cache_set(db, key, weather.model_dump(), settings.cache_ttl_weather)
    return weather
