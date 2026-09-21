"""
Cultural information service (spec section 5).

Lookup order, cheapest/most-authoritative first, none of it ever invented:
  1. Sarthi's own small curated dataset (hand-written, source-cited) --
     CURATED below.
  2. Wikipedia summary extract (sourced, quoted as-is, never rewritten).
  3. Wikidata short description (last resort, usually a single line).
  4. matched=False with an honest fallback message.

Every result carries `source` + `source_url` so the frontend can show
exactly where the text came from (spec section 11: "clearly indicate
provider/source"). Results are cached (TTL: settings.cache_ttl_culture)
since cultural facts don't change day to day and Wikipedia/Wikidata ask
callers not to hammer their public endpoints.
"""
import hashlib
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
from app.core.config import get_settings
from app.integrations.base import ProviderError
from app.integrations.wikimedia import wikidata_lookup, wikipedia_lookup
from app.schemas.cultural import CulturalInfoResponse

settings = get_settings()

CURATED: dict[str, dict] = {
    "goldentemple": {
        "display_name": "Golden Temple (Sri Harmandir Sahib), Amritsar",
        "historical_significance": (
            "Founded by the fourth Sikh Guru, Guru Ram Das, in the 16th century and completed under "
            "Guru Arjan in 1604, who also installed the Adi Granth (the first version of the Guru "
            "Granth Sahib) inside. It has been rebuilt and embellished several times, notably with gold "
            "plating sponsored by Maharaja Ranjit Singh in the early 19th century."
        ),
        "cultural_significance": (
            "The holiest Gurdwara of Sikhism and a symbol of human brotherhood and equality -- its four "
            "entrances, open to all faiths, represent the Sikh belief that everyone is welcome regardless "
            "of religion, caste or background."
        ),
        "architectural_significance": (
            "Built lower than the surrounding land so worshippers descend to enter in humility, with a "
            "gold-plated dome and marble inlay blending Mughal and Sikh architectural styles, set amid the "
            "sacred Amrit Sarovar (pool of nectar)."
        ),
        "traditions": "Continuous recitation of the Guru Granth Sahib, daily Palki Sahib processions, and the world's largest free community kitchen (langar), serving all visitors regardless of background.",
        "etiquette": "Cover your head, remove footwear before entering, avoid alcohol/tobacco nearby, and photography of the sanctum interior is restricted in some areas.",
        "visitor_guidance": "Visit early morning or late evening for a quieter experience; volunteering in the langar kitchen is open to visitors.",
        "sources": [
            "https://www.sgpc.net (Shiromani Gurdwara Parbandhak Committee)",
            "https://whc.unesco.org (UNESCO tentative list entry for the Golden Temple)",
            "https://www.incredibleindia.gov.in",
        ],
    },
    "jallianwalabagh": {
        "display_name": "Jallianwala Bagh, Amritsar",
        "historical_significance": (
            "Site of the 13 April 1919 massacre where British Indian Army troops under General Dyer "
            "fired on an unarmed crowd gathered for Baisakhi and a peaceful protest, killing hundreds. It "
            "became a turning point that galvanised India's independence movement."
        ),
        "cultural_significance": "A national memorial to the sacrifice of those killed and injured, and a solemn site of remembrance in India's freedom struggle.",
        "architectural_significance": "The garden preserves the original well and bullet-marked walls, with a Flame of Liberty memorial added in 1961.",
        "traditions": "Annual commemorations are held on 13 April.",
        "etiquette": "Maintain a respectful, quiet demeanour; it is a memorial site, not a leisure park.",
        "visitor_guidance": "Allow 45-60 minutes; the small museum on-site documents the events of 1919.",
        "sources": [
            "https://www.incredibleindia.gov.in",
            "Ministry of Culture, Government of India -- Jallianwala Bagh National Memorial Trust",
        ],
    },
    "tajmahal": {
        "display_name": "Taj Mahal, Agra",
        "historical_significance": (
            "Commissioned in 1632 by Mughal emperor Shah Jahan as a mausoleum for his wife Mumtaz Mahal, "
            "completed around 1653 after roughly 20,000 artisans worked on it."
        ),
        "cultural_significance": "Regarded as the finest example of Mughal architecture and a global symbol of love; a UNESCO World Heritage Site since 1983.",
        "architectural_significance": "Built of white Makrana marble with pietra dura inlay work, symmetrical charbagh gardens, and a central dome flanked by four minarets.",
        "traditions": "Closed on Fridays for prayers at the adjoining mosque; illuminated for a limited number of nights around the full moon.",
        "etiquette": "Footwear covers are provided/required near the mausoleum; large bags, food, and tripods are restricted.",
        "visitor_guidance": "Sunrise entry avoids the biggest crowds and the harshest heat.",
        "sources": ["https://whc.unesco.org/en/list/252", "https://www.incredibleindia.gov.in"],
    },
    "amberfort": {
        "display_name": "Amber Fort, Jaipur",
        "historical_significance": "Built starting 1592 by Raja Man Singh I as the residence of Rajput Maharajas, expanded over subsequent generations.",
        "cultural_significance": "Reflects the Rajput-Mughal architectural fusion and courtly life of Rajasthan; part of the UNESCO World Heritage 'Hill Forts of Rajasthan'.",
        "architectural_significance": "Sandstone and marble palace complex with the Sheesh Mahal (mirror palace), courtyards and artificial lakes.",
        "traditions": "Sound-and-light shows narrate the fort's history in the evenings.",
        "etiquette": "Elephant rides up the ramp have drawn animal-welfare concerns; many visitors now prefer the jeep or walking route.",
        "visitor_guidance": "Arrive early to avoid tour-bus crowds; combine with a stop at nearby Jaigarh Fort.",
        "sources": ["https://whc.unesco.org/en/list/247", "https://www.incredibleindia.gov.in"],
    },
    "hawamahal": {
        "display_name": "Hawa Mahal, Jaipur",
        "historical_significance": "Built in 1799 by Maharaja Sawai Pratap Singh, designed by Lal Chand Ustad.",
        "cultural_significance": "Allowed royal women to observe street life from behind carved screens (jharokhas) while remaining unseen, per purdah customs of the era.",
        "architectural_significance": "Five-storey pink sandstone facade with 953 small windows (jharokhas) in a honeycomb pattern, designed to catch cooling breezes -- hence 'Palace of Winds'.",
        "traditions": "",
        "etiquette": "Best photographed from across the street in the morning light.",
        "visitor_guidance": "The interior can be visited via the rear entrance from the City Palace side; allow 30-45 minutes.",
        "sources": ["https://www.incredibleindia.gov.in", "Rajasthan Tourism (https://www.tourism.rajasthan.gov.in)"],
    },
}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _cache_key(place_name: str) -> str:
    return "culture:" + hashlib.sha1(_slug(place_name).encode()).hexdigest()


async def get_cultural_info(db: Session, place_id: str, place_name: str) -> CulturalInfoResponse:
    target = _slug(place_name)
    for slug, entry in CURATED.items():
        if slug in target or target in slug:
            return CulturalInfoResponse(place_id=place_id, matched=True, source="curated", **entry)

    key = _cache_key(place_name)
    cached = cache_get(db, key)
    if cached is not None:
        return CulturalInfoResponse(place_id=place_id, **cached)

    result = await _lookup_external(place_id, place_name)
    cache_set(db, key, result.model_dump(exclude={"place_id"}), settings.cache_ttl_culture)
    return result


async def _lookup_external(place_id: str, place_name: str) -> CulturalInfoResponse:
    retrieved_at = datetime.now(timezone.utc).isoformat()

    try:
        wiki = await wikipedia_lookup(place_name)
    except ProviderError:
        wiki = None
    if wiki:
        return CulturalInfoResponse(
            place_id=place_id, matched=True, source="wikipedia",
            display_name=wiki["title"], summary=wiki["extract"],
            sources=[wiki["source_url"]], source_name="Wikipedia", source_url=wiki["source_url"],
            retrieved_at=retrieved_at,
        )

    try:
        wikidata = await wikidata_lookup(place_name)
    except ProviderError:
        wikidata = None
    if wikidata:
        return CulturalInfoResponse(
            place_id=place_id, matched=True, source="wikidata",
            display_name=wikidata["title"], summary=wikidata["extract"],
            sources=[wikidata["source_url"]], source_name="Wikidata", source_url=wikidata["source_url"],
            retrieved_at=retrieved_at,
        )

    return CulturalInfoResponse(
        place_id=place_id, matched=False, source="none",
        fallback_message=(
            "Sarthi couldn't find sourced cultural information for this place -- neither in its own "
            "curated dataset nor on Wikipedia/Wikidata. Nothing is shown here rather than guessing."
        ),
        retrieved_at=retrieved_at,
    )
