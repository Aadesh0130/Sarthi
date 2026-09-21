"""
Wikidata / Wikipedia cultural-fallback lookups (spec section 5).

Free, no API key. Used only as a fallback when Sarthi's own curated
cultural dataset (app/services/cultural_service.py) has no entry for a
place. Both functions return None on "no match" -- a soft miss, not an
error -- so the caller can fall through to the next source instead of
inventing anything. Text returned here is quoted/extracted from the source,
never rewritten or embellished.
"""
from typing import Optional

import httpx

from app.core.config import get_settings
from app.integrations.base import ProviderError

settings = get_settings()


async def wikipedia_lookup(name: str) -> Optional[dict]:
    """Search Wikipedia for `name`, then fetch the top result's summary
    extract. Returns {"title", "extract", "source_url"} or None."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            search_resp = await client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "query", "list": "search", "srsearch": name,
                    "format": "json", "srlimit": 1,
                },
                headers={"User-Agent": settings.nominatim_user_agent},
            )
            search_resp.raise_for_status()
            hits = (search_resp.json().get("query", {}) or {}).get("search", [])
            if not hits:
                return None
            title = hits[0]["title"]

            summary_resp = await client.get(
                f"{settings.wikipedia_base_url}/page/summary/{title.replace(' ', '_')}",
                headers={"User-Agent": settings.nominatim_user_agent},
            )
            if summary_resp.status_code == 404:
                return None
            summary_resp.raise_for_status()
            summary = summary_resp.json()
    except httpx.HTTPError as exc:
        raise ProviderError("wikipedia", str(exc)) from exc

    extract = summary.get("extract")
    if not extract:
        return None
    return {
        "title": summary.get("title", title),
        "extract": extract,
        "source_url": (summary.get("content_urls", {}).get("desktop", {}) or {}).get("page")
        or f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
    }


async def wikidata_lookup(name: str) -> Optional[dict]:
    """Search Wikidata for `name`, returning its short description if found.
    Used only as a last-resort fallback below Wikipedia (which usually has
    richer text) -- returns {"title", "extract", "source_url"} or None."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                settings.wikidata_base_url,
                params={
                    "action": "wbsearchentities", "search": name, "language": "en",
                    "type": "item", "format": "json", "limit": 1,
                },
                headers={"User-Agent": settings.nominatim_user_agent},
            )
            resp.raise_for_status()
            hits = resp.json().get("search", [])
    except httpx.HTTPError as exc:
        raise ProviderError("wikidata", str(exc)) from exc

    if not hits:
        return None
    hit = hits[0]
    description = hit.get("description")
    if not description:
        return None
    return {
        "title": hit.get("label", name),
        "extract": description,
        "source_url": f"https://www.wikidata.org/wiki/{hit['id']}",
    }
