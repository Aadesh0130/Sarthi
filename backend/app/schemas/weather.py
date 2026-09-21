from typing import Optional

from pydantic import BaseModel


class CurrentWeather(BaseModel):
    temperature_c: float
    apparent_temperature_c: Optional[float] = None
    condition_code: int
    condition_text: str
    is_day: bool
    wind_speed_kmh: Optional[float] = None
    precipitation_mm: Optional[float] = None


class HourlyForecastEntry(BaseModel):
    time: str
    temperature_c: float
    precipitation_probability_pct: Optional[int] = None
    condition_code: int
    condition_text: str


class DailyForecastEntry(BaseModel):
    date: str
    temperature_max_c: float
    temperature_min_c: float
    precipitation_probability_max_pct: Optional[int] = None
    condition_code: int
    condition_text: str


class WeatherResponse(BaseModel):
    latitude: float
    longitude: float
    timezone: str
    source: str = "open-meteo"
    data_type: str = "REAL"  # REAL (live fetch) -- never PREDICTED/fabricated
    current: CurrentWeather
    hourly: list[HourlyForecastEntry] = []
    daily: list[DailyForecastEntry] = []
    outdoor_suitability: str  # "good" | "fair" | "poor" -- deterministic, explained in recommendation service
