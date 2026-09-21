"""Open-Meteo weather provider. No API key required."""
import httpx

from app.core.config import get_settings
from app.integrations.base import ProviderError, WeatherProvider
from app.schemas.weather import CurrentWeather, DailyForecastEntry, HourlyForecastEntry, WeatherResponse

settings = get_settings()

# WMO weather interpretation codes used by Open-Meteo -> human text.
_WMO_TEXT = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}


def _wmo_text(code: int) -> str:
    return _WMO_TEXT.get(code, "Unknown conditions")


def _outdoor_suitability(condition_code: int, precip_prob: int | None, wind_kmh: float | None) -> str:
    """Deterministic, explainable rule -- NOT a model. See recommendation_service
    for how this feeds into place suggestions (spec section 11 / 14)."""
    if condition_code in (65, 67, 75, 82, 95, 96, 99) or (precip_prob is not None and precip_prob >= 70):
        return "poor"
    if condition_code in (51, 53, 55, 61, 63, 66, 71, 73, 80, 81) or (precip_prob is not None and precip_prob >= 40):
        return "fair"
    if wind_kmh is not None and wind_kmh >= 45:
        return "fair"
    return "good"


class OpenMeteoProvider(WeatherProvider):
    def __init__(self):
        self.base_url = settings.open_meteo_base_url

    async def forecast(self, latitude: float, longitude: float) -> WeatherResponse:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,is_day",
            "hourly": "temperature_2m,precipitation_probability,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
            "forecast_days": 3,
            "timezone": "auto",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self.base_url, params=params)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError("open-meteo", str(exc)) from exc

        cur = data.get("current", {})
        code = int(cur.get("weather_code", -1))
        current = CurrentWeather(
            temperature_c=cur.get("temperature_2m", 0.0),
            apparent_temperature_c=cur.get("apparent_temperature"),
            condition_code=code,
            condition_text=_wmo_text(code),
            is_day=bool(cur.get("is_day", 1)),
            wind_speed_kmh=cur.get("wind_speed_10m"),
            precipitation_mm=cur.get("precipitation"),
        )

        hourly = []
        h = data.get("hourly", {})
        times = h.get("time", [])[:12]
        for i, t in enumerate(times):
            hc = int(h.get("weather_code", [0] * len(times))[i])
            hourly.append(
                HourlyForecastEntry(
                    time=t,
                    temperature_c=h.get("temperature_2m", [0] * len(times))[i],
                    precipitation_probability_pct=h.get("precipitation_probability", [None] * len(times))[i],
                    condition_code=hc,
                    condition_text=_wmo_text(hc),
                )
            )

        daily = []
        d = data.get("daily", {})
        dtimes = d.get("time", [])
        for i, dt in enumerate(dtimes):
            dc = int(d.get("weather_code", [0] * len(dtimes))[i])
            daily.append(
                DailyForecastEntry(
                    date=dt,
                    temperature_max_c=d.get("temperature_2m_max", [0] * len(dtimes))[i],
                    temperature_min_c=d.get("temperature_2m_min", [0] * len(dtimes))[i],
                    precipitation_probability_max_pct=d.get("precipitation_probability_max", [None] * len(dtimes))[i],
                    condition_code=dc,
                    condition_text=_wmo_text(dc),
                )
            )

        precip_prob_now = hourly[0].precipitation_probability_pct if hourly else None
        suitability = _outdoor_suitability(code, precip_prob_now, current.wind_speed_kmh)

        return WeatherResponse(
            latitude=latitude,
            longitude=longitude,
            timezone=data.get("timezone", "auto"),
            current=current,
            hourly=hourly,
            daily=daily,
            outdoor_suitability=suitability,
        )
