"""
Hotelbeds (HBX Group) hotel provider (spec section 4D).

Auth is header-based, not mTLS: every request carries an `Api-key` header
plus an `X-Signature` header computed as
sha256(api_key + secret + current_unix_timestamp), per Hotelbeds' current
"Getting Started" documentation. No client certificate is required for the
Content/Booking APIs used here, so no *_CERT_PATH env var is defined --
if a future Hotelbeds product genuinely requires mTLS, that would need to be
added as a documented follow-up, not guessed at.

IMPORTANT LIMITATION (documented per spec section 24, not worked around):
a freshly self-registered Hotelbeds developer account is issued
evaluation-tier credentials capped at ~50 requests/day against the TEST
environment. There is no way to raise that from code -- it requires going
through Hotelbeds' certification process on their partner dashboard. This
provider is fully implemented and will work the moment HOTELBEDS_API_KEY/
HOTELBEDS_SECRET are set, but expect the evaluation quota to be tight.
"""
import hashlib
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.core.config import get_settings
from app.integrations.base import HotelProvider, ProviderError
from app.schemas.hotel import HotelRate, HotelRateCheck, HotelResult

settings = get_settings()


def _signature(api_key: str, secret: str) -> str:
    timestamp = str(int(time.time()))
    raw = f"{api_key}{secret}{timestamp}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _hotel_from_json(raw: dict) -> Optional[HotelResult]:
    code = raw.get("code")
    name = raw.get("name")
    if code is None or not name:
        return None

    rates: list[HotelRate] = []
    for room in raw.get("rooms", []) or []:
        for rate in room.get("rates", []) or []:
            rates.append(
                HotelRate(
                    rate_key=rate.get("rateKey", ""),
                    board_name=rate.get("boardName"),
                    room_type=room.get("name"),
                    net_price=float(rate["net"]) if rate.get("net") is not None else None,
                    currency=raw.get("currency"),
                    rate_class=rate.get("rateClass"),
                    requires_recheck=rate.get("rateType", "").upper() != "BOOKABLE",
                )
            )

    return HotelResult(
        id=str(code),
        source="hotelbeds",
        source_url=None,
        name=name,
        category_name=raw.get("categoryName"),
        latitude=raw.get("latitude"),
        longitude=raw.get("longitude"),
        address=(raw.get("address") or {}).get("content") if isinstance(raw.get("address"), dict) else raw.get("address"),
        description=None,
        facilities=[],
        images=[],
        rates=rates,
        retrieved_at=datetime.now(timezone.utc).isoformat(),
    )


class HotelbedsProvider(HotelProvider):
    def __init__(self):
        self.base_url = settings.hotelbeds_base_url
        self.api_key = settings.hotelbeds_api_key
        self.secret = settings.hotelbeds_secret

    def _headers(self) -> dict:
        return {
            "Api-key": self.api_key,
            "X-Signature": _signature(self.api_key, self.secret),
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def search(
        self, latitude: float, longitude: float, check_in: str, check_out: str,
        adults: int = 2, radius_km: int = 15,
    ) -> list[HotelResult]:
        body = {
            "stay": {"checkIn": check_in, "checkOut": check_out},
            "occupancies": [{"rooms": 1, "adults": adults, "children": 0}],
            "geolocation": {
                "latitude": latitude, "longitude": longitude,
                "radius": radius_km, "unit": "km",
            },
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    f"{self.base_url}/hotel-api/1.0/hotels",
                    json=body, headers=self._headers(),
                )
                if resp.status_code in (401, 403):
                    raise ProviderError("hotelbeds", f"Authentication failed ({resp.status_code}) -- check API key/secret and evaluation quota")
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError("hotelbeds", str(exc)) from exc

        hotels_raw = (data.get("hotels", {}) or {}).get("hotels", []) or []
        results = [_hotel_from_json(h) for h in hotels_raw]
        return [h for h in results if h is not None]

    async def get_content(self, hotel_code: str) -> Optional[HotelResult]:
        """Hotel Content API lookup (spec section 9: GET /api/hotels/{id}) --
        static descriptive content (name, address, facilities, images), not
        live rates. Uses the same Api-key/X-Signature auth as the Booking API."""
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(
                    f"{self.base_url}/hotel-content-api/1.0/hotels/{hotel_code}/details",
                    params={"language": "ENG"}, headers=self._headers(),
                )
                if resp.status_code == 404:
                    return None
                if resp.status_code in (401, 403):
                    raise ProviderError("hotelbeds", f"Authentication failed ({resp.status_code})")
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError("hotelbeds", str(exc)) from exc

        hotel = data.get("hotel", data)
        name = (hotel.get("name") or {}).get("content") if isinstance(hotel.get("name"), dict) else hotel.get("name")
        if not name:
            return None
        facilities = [
            (f.get("description") or {}).get("content", "")
            for f in hotel.get("facilities", []) or []
            if isinstance(f, dict)
        ]
        images = [
            f"https://photos.hotelbeds.com/giata/original/{img.get('path')}"
            for img in hotel.get("images", []) or []
            if img.get("path")
        ]
        return HotelResult(
            id=str(hotel_code),
            source="hotelbeds",
            source_url=None,
            name=name,
            category_name=(hotel.get("category") or {}).get("description", {}).get("content") if isinstance(hotel.get("category"), dict) else None,
            latitude=(hotel.get("coordinates") or {}).get("latitude"),
            longitude=(hotel.get("coordinates") or {}).get("longitude"),
            address=(hotel.get("address") or {}).get("content"),
            description=(hotel.get("description") or {}).get("content"),
            facilities=[f for f in facilities if f],
            images=images,
            rates=[],
            retrieved_at=datetime.now(timezone.utc).isoformat(),
        )

    async def check_rate(self, rate_key: str) -> HotelRateCheck:
        """Revalidate a rate before it's presented as bookable, per Hotelbeds
        policy and spec section 11 ('prefer revalidation before presenting
        the final offer'). A failed/expired rateKey is reported honestly as
        still_valid=False -- never re-used as if it were fresh."""
        body = {"rooms": [{"rateKey": rate_key}]}
        checked_at = datetime.now(timezone.utc).isoformat()
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(
                    f"{self.base_url}/hotel-api/1.0/checkrates",
                    json=body, headers=self._headers(),
                )
                if resp.status_code >= 400:
                    return HotelRateCheck(rate_key=rate_key, still_valid=False, checked_at=checked_at)
                data = resp.json()
        except httpx.HTTPError as exc:
            raise ProviderError("hotelbeds", str(exc)) from exc

        hotel = data.get("hotel", {}) or {}
        rooms = hotel.get("rooms", []) or []
        for room in rooms:
            for rate in room.get("rates", []) or []:
                if rate.get("rateKey") == rate_key or True:  # checkrates returns the (possibly re-keyed) rate directly
                    return HotelRateCheck(
                        rate_key=rate.get("rateKey", rate_key),
                        still_valid=True,
                        net_price=float(rate["net"]) if rate.get("net") is not None else None,
                        currency=hotel.get("currency"),
                        checked_at=checked_at,
                    )
        return HotelRateCheck(rate_key=rate_key, still_valid=False, checked_at=checked_at)
