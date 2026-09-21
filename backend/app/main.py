from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import ai, auth, crowd, culture, events, flow, geocode, health, hotels, images, itineraries, places, recommendations, routes, weather
from app.core.config import get_settings
from app.db.database import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description=(
        "Real-data backend for Sarthi (SIH PS 26204) -- geocoding (Nominatim), nearby places (Overpass/"
        "OpenStreetMap), weather (Open-Meteo), routing (OSRM), events (Ticketmaster), hotels (Hotelbeds), "
        "images (Unsplash), cultural information (curated + Wikipedia/Wikidata), explainable "
        "recommendations, trip itineraries with deterministic replanning, an estimated Tourism Pressure "
        "Index (seasonality + live place density + weather + Sarthi's own usage -- never a live crowd feed), "
        "an AI Travel Assistant (OpenAI or Gemini, whichever is configured), an AI-reasoned real-data trip "
        "planner with dynamic replanning, AI photo-based place identification with independent "
        "Nominatim verification, and a Tourist Flow Rebalancer that detects tourism pressure and suggests "
        "explainable, real-data lower-pressure alternatives without ever silently replacing the traveller's "
        "chosen destination."
    ),
    version="0.5.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(geocode.router)
app.include_router(places.router)
app.include_router(weather.router)
app.include_router(routes.router)
app.include_router(events.router)
app.include_router(hotels.router)
app.include_router(images.router)
app.include_router(culture.router)
app.include_router(recommendations.router)
app.include_router(itineraries.router)
app.include_router(ai.router)
app.include_router(crowd.router)
app.include_router(flow.router)
