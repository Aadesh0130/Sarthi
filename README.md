# Sārthi — SIH PS 26204

Sārthi is a smart tourism platform: an existing static-prototype frontend (kept intact) now wired to a
real FastAPI backend for **live** geocoding, nearby places, weather, routing, events, hotels and
imagery, plus an explainable recommendation engine, sourced cultural information, a real trip planner
with deterministic replanning, and an AI Travel Assistant (OpenAI or Gemini, whichever you configure).

## What's real vs. what's curated

Sārthi has two layers that work side by side:

1. **Real-data layer** (new) — Explore's "Search any place in India" section and Planner's "Real trip
   builder" section. Every place, coordinate, weather reading, route, event, hotel and photo here comes
   live from a public provider at request time (see below). Nothing here is pre-baked.
2. **Curated layer** (existing, preserved) — the original 16 hand-picked destination guides, the AI
   Planner's day-by-day itinerary generator, the SmartScore engine, the cart/booking demo and GreenTrip
   score. This is deterministic, offline, sourced from `js/data.js`, and is labelled "estimated" /
   "curated" wherever it previously read like a live number (e.g. crowd index).

## Providers

| Purpose | Provider | Key required? | Notes |
|---|---|---|---|
| Geocoding | [Nominatim](https://nominatim.org) | No | Rate-limited to ~1 req/s from the backend, cached |
| Nearby places | [Overpass API](https://overpass-api.de) (OpenStreetMap) | No | attraction, museum, historic, religious, park, restaurant, cafe, shopping, hotel |
| Weather | [Open-Meteo](https://open-meteo.com) | No | Current + hourly + daily |
| Routing | [OSRM](https://router.project-osrm.org) (public demo server) | No | Driving/walking/cycling |
| Map tiles | OpenStreetMap + [Leaflet](https://leafletjs.com) | No | Standard OSM tile usage policy applies |
| Cultural info fallback | Wikipedia / Wikidata | No | Only used when Sārthi's own curated dataset has no entry |
| Events | [Ticketmaster Discovery API](https://developer-acct.ticketmaster.com) | **Yes** (free, self-serve) | Indian-market coverage is genuinely limited |
| Hotels | [Hotelbeds / HBX Group](https://developer.hotelbeds.com) | **Yes** (free sandbox, self-serve — but capped) | See "Hotelbeds limitation" below |
| Images | [Unsplash](https://unsplash.com/developers) | **Yes** (free "Demo" app, self-serve) | 50 req/hour on the Demo tier |
| AI Travel Assistant | OpenAI **or** Google Gemini (your choice) | **Yes** (either one) | Chooses via `AI_PROVIDER` |

All of these sit behind small provider interfaces in `backend/app/integrations/` (see `base.py`) so a
different provider can be swapped in later without touching the rest of the app.

### Nearby-places reliability (Overpass API)

Overpass's public instances are shared, free infrastructure with no uptime guarantee, and can genuinely
be overloaded or down — including all of them at once, which was observed live during this build
(`overpass-api.de` 504, `overpass.kumi.systems` ReadTimeout, `overpass.openstreetmap.ru` ConnectTimeout,
all for the same query). Sārthi mitigates this with three real, layered measures rather than a single
retry:

1. **Cheaper queries** — one regex-consolidated OSM-key clause per category group instead of one clause
   per (key, value, element-type) triple (`backend/app/integrations/overpass.py: _build_query`).
2. **Hedged multi-mirror racing** — up to 4 independent public Overpass instances are raced concurrently
   (not tried one after another), so one slow/dead mirror doesn't multiply the worst-case wait
   (`OverpassProvider._post`; see `backend/tests/test_overpass_hedging.py`).
3. **Last-resort stale-cache fallback** — if every mirror still fails, and this exact spot was
   successfully searched before (by anyone, since the place cache is shared), Sārthi serves that earlier
   real result instead of a hard failure, for up to `cache_stale_grace_places` (7 days by default — POI
   existence doesn't meaningfully change week to week). This is never silently presented as live: the
   `/api/places/nearby` response carries an `X-Sarthi-Data-Freshness: cached-stale` header and the age in
   `X-Sarthi-Cache-Age-Seconds`, and Explore shows an honest "showing results from N ago" notice instead
   of either a false success or a needless error (see `backend/tests/test_places_resilience.py`).

This narrows the free public Overpass infrastructure's real reliability gaps; it can't eliminate them —
a location nobody has ever successfully searched before still gets an honest "temporarily unavailable"
if every mirror happens to be down at that exact moment, because there is nothing real to fall back to.

### Hotelbeds limitation (read this before expecting hotel results)

Hotelbeds' sandbox signup is genuinely self-serve — you get an API key + secret the same day at
<https://developer.hotelbeds.com>. But a freshly registered account only gets **"evaluation"**
credentials, capped at **~50 requests/day** against the TEST environment (`api.test.hotelbeds.com`).
Raising that requires going through Hotelbeds' certification process on their partner dashboard — there
is no way around this from code, and it's unlikely to complete during a hackathon timeline. The
`HotelbedsProvider` (`backend/app/integrations/hotelbeds.py`) is fully implemented — hotel search, room
availability and rate-check-before-booking (`POST /api/hotels/check-rate`) — and will work the moment you
add real credentials; just expect the daily quota to be tight.

### Ticketmaster coverage limitation

Ticketmaster's Discovery API is comprehensive for North America/Europe but has real gaps for many Indian
cities. An empty `events: []` result for, say, a smaller city is an honest "nothing listed", not a bug —
`coverage_note` in the API response says so explicitly, and the UI never invents an event to fill the gap.

## Tourism Pressure Index (crowd-monitoring engine)

Sārthi PS 26204 asks for a way to warn travellers when a destination is under heavy tourism pressure —
without ever fabricating a live crowd count that doesn't exist. This build adds a **Tourism Pressure
Index (TPI)**: a 0-100 explainable estimate, never a sensor reading.

**This is not real-time crowd monitoring.** There is no camera feed, no footfall sensor, no government
occupancy data, and no live visitor count anywhere in this system. Every number the TPI produces is
either a curated seasonal pattern, a live-but-indirect proxy (how many tourist places OpenStreetMap
records nearby, or today's real weather), or Sārthi's own honest usage counter. The UI says so on every
card: *"Estimated planning signal — not a live visitor count."*

### How the score is built

`GET /api/crowd/pressure?lat=..&lon=..&destination=..` (client: `API.crowdPressure()` in `js/api.js`)
combines up to five independently-optional components, each carrying its own `data_type` label:

| Component | Weight | Source | `data_type` |
|---|---|---|---|
| Seasonal pressure | 0.35 | Curated peak/shoulder/off-season calendar for ~35 Indian destinations (`backend/app/integrations/crowd.py`), with a generic Oct–Mar/Apr–Jun/Jul–Sep India-wide fallback for anywhere else | `curated` |
| Live place density | 0.30 | The same Overpass/OpenStreetMap nearby-places call Explore already makes (`places_service.nearby_places()`, 4 km radius, same cache) — more mapped attractions/restaurants/hotels nearby → higher pressure | `estimated` (from live data) |
| Sārthi demand signal | 0.10 | A real counter of how many times *this* Sārthi instance has been asked about this area (`DestinationDemandLog` table, bucketed to ~1 km) — this is genuinely low or zero for a prototype, and that's shown honestly, not padded | `estimated` (real usage) |
| Weather suitability | 0.15 | The same Open-Meteo forecast Explore already shows — poor outdoor weather modestly lowers *outdoor* tourism pressure | `estimated` (from live data) |
| Live event pressure | 0.10 | Reserved for a future ticketed-event-volume signal; currently always `used: false` since no such provider is wired up — never guessed | n/a (not fabricated) |

Weights are **renormalized across only the components actually available** for that request (e.g. if
Overpass is down, its 0.30 weight is dropped and the rest are scaled up proportionally). If the total
available weight falls below 0.45, or none of the three live/external signals (place density, weather,
events) could be reached, the endpoint reports `pressure_index: null`, `status: null`,
`data_type: "unavailable"` — it never guesses a number to fill the gap. See
`backend/app/services/crowd_service.py: _MIN_RELIABLE_WEIGHT`.

### Status bands (identical in `crowd_service.py` and `js/data.js: tourismPressureStatus()`)

| Range | Status |
|---|---|
| 0 – 25 | LOW |
| 26 – 50 | MODERATE |
| 51 – 75 | HIGH |
| 76 – 100 | VERY HIGH |

### Where it shows up

- **Explore** (`js/real-explore.js: renderCrowdPressure()`): a card next to Weather/Events showing the
  score, status badge, up to four plain-language reasons, the separately-reported weather suitability
  line, the disclaimer, and a soft colour-coded circle on the map (never implying live human tracking) —
  or an honest "unavailable" message when the reliability gate isn't met.
- **AI Planner** (curated destinations only, `js/planner.js`): a fifth "Tourism Pressure" hero tile reading
  the destination's curated popularity score through the same `tourismPressureStatus()` bands, and the
  existing **Smart Alternative** card's copy was reworded to say "Tourism Pressure" and explicitly state
  the primary destination is never auto-replaced.

### The explicit destination always wins

The crowd engine only **warns and suggests** — it can never overwrite the traveller's choice.

- In Explore, the TPI card is informational only; it never redirects the map or the search.
- In the AI Planner, `js/planner.js` still keeps `state.destId` (the dropdown's explicit selection) as the
  single source of truth for the primary destination through every regenerate/interest/budget change; the
  crowd/pressure numbers never feed into `pickBestDestination()` or otherwise replace it.
- The existing **Smart Alternative** system (`js/data.js: findSmartAlternative()`, only triggered at
  popularity/TPI ≥ 75) is reused as-is — it already balances shared interests, cost, sustainability and
  crowd relief rather than "just pick the lowest-crowd option," and it only switches the primary
  destination when the traveller clicks the alternative's own **Switch** button. Nothing in this feature
  changed that scoring algorithm.

### Adding a real live-crowd provider later

`backend/app/integrations/crowd.py` defines `CrowdProvider` as an abstract base with one required method
(`seasonal_pressure()`); `EstimatedCrowdProvider` is the only implementation today. A future real provider
(a government footfall API, a ticketed-entry system, a telecom density feed) would implement the same
interface and be swapped in `crowd_service.py` — no caller (`api/crowd.py`, `js/api.js`, `real-explore.js`)
would need to change. Until such a provider exists, this codebase deliberately contains no live-crowd
provider — implementing a fake one was explicitly out of scope for this feature.

## Tourist Flow Rebalancer

The TPI above answers "is this destination under pressure?" The **Tourist Flow Rebalancer** is the
natural next step Sārthi was missing: when the answer is yes, it finds genuine nearby destinations with
lower estimated pressure, scores them explainably on real data, and lets the traveller *choose* to shift
their plan — demand is redistributed **voluntarily**, never silently.

`POST /api/flow/rebalance` (client: `API.rebalanceDestination()` in `js/api.js`, engine:
`backend/app/services/flow_rebalancer_service.py`) reuses the exact same Tourism Pressure Index above —
there is exactly one pressure system in this codebase, not two. It is **deterministic weighted scoring,
not machine learning** (`method: "deterministic-weighted-scoring"`, `is_machine_learning: false`
on every response) — the same explainable-scoring pattern already used by the in-destination SmartScore
engine (`recommendation_service.score_places`), just applied at the destination level instead of the
place level.

### What triggers a search

| Requested destination's TPI status | Behaviour |
|---|---|
| LOW / unavailable | Normal experience. `pressure_check_only: true`, zero extra Overpass/weather/OSRM calls — nothing to search for. |
| MODERATE | Alternatives are computed and returned, but `rebalancing_triggered: false` — available if the traveller wants them, not pushed. |
| HIGH / VERY HIGH | Alternatives are computed **and** `rebalancing_triggered: true` — the Explore UI surfaces them prominently. |

### How a candidate becomes an "alternative"

1. **Discovery** (`_discover_candidates`): real OpenStreetMap settlements within ~70 km
   (`OverpassProvider.nearby_settlements`, the same hedged multi-mirror `_post()` as every other Overpass
   call) plus Sārthi's existing 16 curated destinations/hidden gems (mirrored with coordinates into
   `backend/app/data/curated_destinations.py` — see that file's docstring for why it's a mirror, not a
   second dataset — and geocoded via Nominatim, pre-filtered by state to avoid needlessly walking
   Nominatim's throttled ~1 req/s budget through all 16 every time). Anything within 8 km of the requested
   destination (essentially "the same place") or within 3 km of an already-picked candidate is dropped.
2. **Filtering**: a candidate must have a strictly lower TPI status than the requested destination, and
   poor-weather candidates are excluded unless the requested destination's own weather is also poor/unknown.
3. **Scoring** (`_score_candidate`) — seven explainable, independently-labelled factors, each returned in
   full in the response's `factors` object so nothing is a black box:

   | Factor | Weight | What it measures |
   |---|---|---|
   | Experience match | 0.28 | Real-OSM category-mix similarity to the requested destination (histogram intersection), blended with the traveller's selected interests via the same `INTEREST_TO_CATEGORIES` table the SmartScore engine uses |
   | Pressure relief | 0.24 | How much lower the candidate's real TPI is than the requested destination's |
   | Distance & accessibility | 0.16 | Straight-line distance, banded (closer scores higher) |
   | Weather suitability | 0.10 | The candidate's own real Open-Meteo outdoor suitability |
   | Sustainability | 0.08 | Curated figure for the 16 known destinations, else modelled from tourism-place density for anywhere else — never invented |
   | Local economic opportunity | 0.08 | A qualitative label from real nearby restaurant/stay/shop counts on OpenStreetMap (e.g. *"Strong local experience availability"*) — **never a rupee figure** |
   | Carrying capacity | 0.06 | A modelled/estimated band from place density (`backend/app/integrations/carrying_capacity.py`) — explicitly not an official figure; see "Adding real carrying-capacity data" below |

   The weighted sum is the 0-100 **Rebalancing Score**; `experience_match` is also reported on its own
   0-100 scale since it answers a different question ("will I like it as much?") than the composite does
   ("should demand shift here?").
4. **Shortlisting**: the top `max_alternatives` (default 5) candidates by Rebalancing Score are kept, and
   only *those* get a real OSRM route call for travel time — routing is deliberately never called
   per-candidate during scoring, to avoid hammering the public OSRM instance.
5. Every alternative also carries its own full `tourism_pressure` object (the same `CrowdPressureResponse`
   shape as the TPI card, embedded rather than duplicated) and a `reasons` list generated from the actual
   scoring factors above — never hardcoded copy.

### Where it shows up

- **Explore** (`js/real-explore.js: renderRebalancer()`): a "🧭 Nearby Alternatives" card directly below
  the Tourism Pressure card, in the same visual language (`.rebalance-card` mirrors `.crowd-card` in
  `css/styles.css`) — one alternative per card with its match %, pressure badge, distance/travel time,
  local-opportunity/sustainability/carrying-capacity chips, reasons, and an **"Explore ⟨name⟩"** button.
  Alternatives get their own green map markers (`.rebalance-alt-marker`, a separate Leaflet layer from the
  nearby-places pins so category-chip filtering never wipes them) versus the requested destination's normal
  marker.
- **The destination is never silently replaced.** Nothing here runs automatically — clicking "Explore
  ⟨name⟩" (card button or map-marker popup) is the *only* way the destination changes, and it does so
  through the exact same `setLocation()` function a normal search uses, so everything downstream (map,
  weather, places, pressure, "Add to trip") behaves identically to searching that place directly. This is
  also the entire "planner integration": there's no second planner or new destination-state mechanism —
  switching Explore's destination via `setLocation()` *is* the integration point, and the existing
  Real Trip Builder / replan flow (`js/real-planner.js`) picks up whatever places get added from there.
- **AI Assistant** (`app/ai/tools.py: rebalance_destination`): when a traveller asks things like *"Manali
  feels crowded, what else is nearby?"*, the assistant calls this same endpoint — the system prompt is
  explicit that it is "the only source of truth for tourism pressure, alternatives, distances and scores"
  and the model must never invent or adjust any of those numbers itself.

### Honesty rules specific to this feature

- The UI never says "Live Crowd Level" — always "Estimated Tourism Pressure", matching the TPI card above.
- Local economic opportunity is always a qualitative label backed by a real OSM business count — never a
  rupee amount, and never a named/invented business.
- Carrying capacity is always labelled `estimated`/modelled — this build has no official government
  capacity dataset.
- A provider failure degrades gracefully: `/api/flow/rebalance` has a top-level exception guard that
  returns an honest "temporarily unavailable" message rather than a 500, and inside the scoring pipeline a
  single failed candidate (`asyncio.gather(..., return_exceptions=True)`) is simply dropped rather than
  failing the whole request.

### Adding real carrying-capacity data later

`backend/app/integrations/carrying_capacity.py` defines `CarryingCapacityProvider` as an abstract base
(`estimate(place_count) -> (score, label, data_type)`); `EstimatedCarryingCapacityProvider` is the only
implementation today, modelling capacity from OSM place density. A future provider backed by real
government tourism-carrying-capacity data would implement the same interface and be swapped in
`flow_rebalancer_service.py` — no caller would need to change.

## Running it

### 1. Backend (FastAPI)

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env             # edit to add optional keys — the core app works with none of them set
uvicorn app.main:app --reload --port 8000
```

The backend defaults to a local SQLite file (`backend/sarthi.db`, created automatically) — zero database
setup required. For the PostgreSQL + PostGIS setup described in the original project brief, install
Postgres, create a database, and set `DATABASE_URL` in `backend/.env`:

```
DATABASE_URL=postgresql+psycopg2://sarthi:sarthi@localhost:5432/sarthi
```

(you'll also need `pip install psycopg2-binary`). The schema (`backend/app/models/`) uses plain lat/lon
float columns so it runs unchanged on both SQLite and Postgres; a real PostGIS `geometry` column is a
documented follow-up, not required for this to work.

Check it's running: <http://localhost:8000/api/health> (lists exactly which optional providers are
configured) or <http://localhost:8000/docs> (interactive API docs for every endpoint).

### 2. Frontend (static site)

No build step — it's the same static site as before, just serve it:

```bash
# from the repo root, in a second terminal
python -m http.server 5500
```

Then open <http://localhost:5500/index.html>. Opening the HTML files directly via `file://` can trigger
browser CORS restrictions — use a local server.

By default the frontend talks to the backend at `http://localhost:8000` (see `js/config.js`).

### 3. Try the SIH demo flow

1. On the homepage, search **"Amritsar"** (or open Explore directly).
2. Real places load from OpenStreetMap with a live map; real current weather appears; if
   `TICKETMASTER_API_KEY` is set, nearby real events appear too.
3. Click **Golden Temple** → real address/coordinates/opening-hours, a real Unsplash photo (if
   `UNSPLASH_ACCESS_KEY` is set) → **Cultural significance** for sourced historical context (curated, or
   Wikipedia/Wikidata as a fallback).
4. Click **Add to trip**, open **Planner**, scroll to **"Real trip builder"** — the place is there on a
   live map, alongside nearby real events/hotels for that area (if configured).
5. Add 1-2 more places, **Optimize route** (real OSRM), **Save itinerary** (persists to the database),
   then try **Replan**: pick *Weather* (reorders using the real forecast), *Preferences changed*
   (re-scores every stop against updated interests/pace/budget) or *Time limited* (trims the day to fit
   fewer hours, explaining what was dropped and why).
6. The ranked "recommendations" panel shows Sārthi's explainable SmartScore for nearby real places —
   with a small bonus when a live event or an available-rate hotel is nearby, when those are configured.
7. Click the ✨ chat bubble for the AI Assistant — it says plainly that it needs a key
   (`OPENAI_API_KEY` or `GEMINI_API_KEY`, depending on `AI_PROVIDER`) until you set one.

### 4. Enabling optional features

Everything in this section is off by default and each feature reports itself as "not configured" — never
fakes a result — until you add the key.

```
# backend/.env

# --- AI Travel Assistant: pick ONE ---
AI_PROVIDER=openai        # or: gemini
OPENAI_API_KEY=           # https://platform.openai.com/api-keys
GEMINI_API_KEY=           # https://aistudio.google.com/apikey (free tier)

# --- Events ---
TICKETMASTER_API_KEY=     # https://developer-acct.ticketmaster.com/user/register

# --- Hotels (see "Hotelbeds limitation" above) ---
HOTELBEDS_API_KEY=
HOTELBEDS_SECRET=

# --- Images ---
UNSPLASH_ACCESS_KEY=      # https://unsplash.com/developers
```

Set the key(s) you want and restart the backend. The AI assistant can only call Sārthi's own tools
(`search_places`, `get_nearby_places`, `get_weather`, `get_recommendations`, `get_events`, `get_hotels`,
`get_cultural_info` — see `backend/app/ai/tools.py`); it has no raw database or internet access, and it
never invents a place, rating, price, event date or weather reading. Swapping `AI_PROVIDER` between
`openai` and `gemini` changes nothing else in the app — both implement the same internal interface
(`app/integrations/base.py: AIProvider`).

### 5. Running the backend tests

```bash
cd backend
source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install pytest
pytest tests/ -v
```

These exercise the full FastAPI request/response cycle with every external provider mocked at its
integration boundary (this repo's dev sandbox had no route to the public APIs — see "Known limitations"
below), including the not-configured paths for events/hotels/images/AI, the curated → Wikipedia →
Wikidata cultural fallback chain, and every replan trigger (weather, remove_place, preferences_changed,
time_limited, and the explicit rejection of unsupported triggers).

## Project layout

```
Sarthi/
├── index.html, explore.html, planner.html   ← existing pages, extended in place
├── css/styles.css                            ← existing design system, extended in place
├── js/
│   ├── data.js, main.js, explore.js, planner.js   ← existing curated engine (preserved)
│   ├── config.js                              ← backend URL config
│   ├── api.js                                 ← fetch client for the backend
│   ├── real-explore.js                        ← live search + map + real places + events + photos +
│   │                                             Tourism Pressure card (renderCrowdPressure)
│   ├── real-planner.js                        ← real trip builder + events/hotels + replanning
│   └── ai-assistant.js                        ← floating AI chat widget
└── backend/
    ├── requirements.txt, .env.example
    └── app/
        ├── main.py
        ├── core/            (settings, cache)
        ├── db/              (SQLAlchemy session/engine)
        ├── models/          (itineraries, cultural info, api cache, crowd_demand.py — demand-signal log)
        ├── schemas/         (pydantic request/response models: place, event, hotel, image, cultural,
        │                     crowd.py, ...)
        ├── integrations/    (Nominatim, Overpass, OSRM, Open-Meteo, Ticketmaster, Hotelbeds, Unsplash,
        │                     Wikipedia/Wikidata, OpenAI, Gemini, crowd.py — one file per provider)
        ├── services/        (business logic + caching, one per domain, incl. crowd_service.py)
        ├── ai/tools.py       (tool functions the AI assistant is allowed to call)
        └── api/              (FastAPI routers: geocode, places, weather, routes, events, hotels,
                                images, culture, recommendations, itineraries, ai, health, crowd)
```

## Honesty rules this build follows

- Nothing here fakes live weather, crowd data, ratings, opening hours, maps, routes, event listings,
  hotel prices/availability, or AI activity.
- The curated destinations' "crowd index" is explicitly labelled an **estimated** planning signal — it
  was never a live sensor claim, and the labelling says so.
- OpenStreetMap doesn't carry traveller ratings for most places; the UI says exactly that.
- The recommendation engine is explicit deterministic weighted scoring (`is_machine_learning: false`) —
  never described as AI or ML. A live event/hotel context adds only a small, capped bonus, and only when
  that provider is actually configured and returned something nearby.
- The AI Assistant reports itself as "not configured" rather than pretending to respond when no key is
  set for the selected `AI_PROVIDER`.
- The Tourism Pressure Index is explicitly labelled `data_type: "estimated"` (or `"unavailable"`) —
  never "live crowd count," never sourced from any invented tourist-count, occupancy, or government
  statistic. When too few of its signals are reachable it reports `null`/"unavailable" rather than
  guessing a number. It only ever warns/suggests; it can never overwrite the traveller's chosen
  destination (see "Tourism Pressure Index" above).
- The Tourist Flow Rebalancer is explicit deterministic weighted scoring (`is_machine_learning: false`,
  `method: "deterministic-weighted-scoring"`) — never described as AI/ML. Local economic opportunity is
  always a qualitative label from real OSM business counts, never a rupee figure or an invented business;
  carrying capacity is always labelled `estimated`/modelled, never presented as an official government
  figure. It only ever suggests alternatives; the requested destination changes only when the traveller
  explicitly clicks "Explore ⟨name⟩" (see "Tourist Flow Rebalancer" above).
- Cultural information tries Sārthi's own small curated dataset first, then Wikipedia, then Wikidata —
  every result says which source it came from (`source`, `source_url`); if none match, the API says so
  instead of generating text.
- Ticketmaster/Hotelbeds/Unsplash each report `configured: false` with a clear message when their key is
  unset — they never silently return an empty result that could be mistaken for "nothing nearby".
- Itinerary replanning only supports triggers Sārthi can back with real data or a genuine deterministic
  recomputation (`weather`, `remove_place`, `preferences_changed`, `time_limited`); triggers with no real
  signal (`event_change`, `hotel_change`, `route_impractical`) are rejected with a clear explanation
  rather than faked.
- Hotel rates from search are a snapshot — `POST /api/hotels/check-rate` always makes a fresh Hotelbeds
  call (never cached) before a price should be treated as bookable.

## Known limitations

- **Hotelbeds evaluation quota** (~50 req/day) — see above. Hotel search/rate-check code is complete and
  correct against Hotelbeds' documented API shape, but could not be verified against live data from this
  environment (no credentials were available — see "Testing performed").
- **Ticketmaster coverage** for many Indian cities is sparse — expected, not a bug.
- **Unsplash download-tracking**: Unsplash's guidelines ask apps to ping a tracking endpoint when a photo
  is actually *downloaded* by a user. Sārthi only displays search results (no save-photo feature exists),
  so that ping isn't implemented — a documented gap, not a workaround.
- **No user accounts** — itineraries aren't scoped to a signed-in user; anyone with the itinerary ID can
  view/edit it. Fine for a single-demo-machine SIH prototype, not for a multi-user deployment.
- **PostGIS** is supported (swap `DATABASE_URL`) but not required or auto-configured; geometry columns
  are plain lat/lon floats today, per the original build's decision to keep zero-setup SQLite as the
  default rather than requiring a local Postgres install.
- **Curated destinations are mirrored, not shared, between frontend and backend.** `js/data.js`'s 16
  curated destinations have no lat/lon and no backend access path, so `backend/app/data/curated_destinations.py`
  duplicates their identity fields (name/state/tags/hidden-gem/sustainability) for the Rebalancer to use.
  Restructuring `js/data.js` to be backend-fetched was judged too risky for the many existing pages that
  depend on its current synchronous-load shape — a genuine trade-off, documented rather than hidden. If
  one dataset is ever edited, the other needs a matching update; there's no automated check for drift yet.
- **Coarse state pre-filter for curated candidates**: to avoid walking Nominatim's throttled ~1 req/s
  budget through all 16 curated destinations on every cold-cache Rebalancer request, candidates are
  pre-filtered by a state-name substring match before geocoding, falling back to checking all 16 only when
  that filter matches nothing. Occasionally-differing state-name wording could in theory skip a genuine
  nearby curated candidate — bounded, never silent (it always falls back rather than returning zero).
- **No live carrying-capacity or official local-economic-impact dataset** — both are modelled from real
  OSM place density, clearly labelled `estimated`, pending a real government data source (see "Adding real
  carrying-capacity data later" above).
- **Cold-cache latency**: a Rebalancer request for a destination whose density/weather/settlement data
  isn't cached yet can take several seconds (multiple hedged Overpass calls, weather, and up to
  `_MAX_CANDIDATES_SCORED` candidate scoring passes) before alternatives appear — subsequent requests for
  the same area are fast via the existing cache layer.

## Testing performed

- Backend unit/integration tests (`backend/tests/test_smoke.py`) — **13 tests, all passing** (verified by
  running `pytest` — see the Final Audit in the delivery notes for the exact run) — cover every router
  with providers mocked at the integration boundary: geocoding, places, weather, routing, recommendations
  (including the event/hotel context bonus), itinerary CRUD, all four replan triggers, cultural info's
  three-source fallback chain, the AI assistant's provider-agnostic tool-calling loop (mocked at the
  `AIProvider.chat` interface, so it equally validates the OpenAI and Gemini code paths), and the two
  Tourism Pressure Index cases: a normal estimate when the live signals succeed, and the honest
  `"unavailable"` response when they don't.
- Two real, executed Playwright end-to-end browser tests for the Tourism Pressure feature (not just unit
  tests): one drives the AI Planner (curated destinations) confirming the Tourism Pressure tile shows the
  correct score/status per destination, that changing interests/budget/regenerating never changes the
  selected destination, and that the Smart Alternative card only switches the primary destination on an
  explicit click; the other drives Explore with the backend's HTTP responses mocked, confirming the crowd
  card renders correctly for both a successful estimate and an honest "unavailable" response, with zero
  JavaScript errors and the rest of Explore (search, place cards, map) still working in both cases.
- A full boot test of the real (unmocked) FastAPI app confirming every new route is registered and
  responds correctly, including the honest `configured: false` responses for Ticketmaster/Hotelbeds/
  Unsplash/AI when no key is set.
- The already-working real-data layer (Nominatim/Overpass/OSRM/Open-Meteo) was previously verified
  against the live public APIs; see the delivery notes for that history. Ticketmaster/Hotelbeds/Unsplash/
  Gemini could not be live-tested from this environment since no credentials for them exist yet — set
  your own keys and the `/api/health` endpoint will confirm each one is wired up before you test it
  manually against real data.
- **Tourist Flow Rebalancer backend** (`backend/tests/test_flow_rebalancer.py`) — **10 tests, all
  passing**, mocked at the service layer (Overpass/Nominatim/Open-Meteo/OSRM), covering: LOW pressure
  skips candidate search entirely (zero extra provider calls); HIGH pressure generates ranked alternatives
  without ever replacing the requested destination; a candidate with equal-or-worse pressure is excluded;
  experience match reflects interest alignment; the pressure-relief factor favours the lower-pressure
  candidate; a provider failure degrades gracefully instead of crashing; unavailable pressure data is
  reported honestly (no search attempted); a destination with no discoverable candidates returns an honest
  message, not a crash; an unresolvable destination query is reported honestly, not guessed; and the API
  response matches its declared schema. Combined with the existing suites, the **full backend test suite
  is 37/37 passing** with zero regressions.
- **Real, executed Playwright browser test of the full Explore integration** (Chromium, not just unit
  tests): searches a destination the mocked backend reports as HIGH pressure, confirms the Tourism
  Pressure card shows HIGH, confirms the "🧭 Nearby Alternatives" card renders the ranked alternative with
  its correct experience-match %, hidden-gem tag, reasons and signals, confirms a real green marker
  (distinct from the request's own places) appears on the Leaflet map, clicks its "Explore ⟨name⟩" button
  and confirms the destination only changes at that point (via the same `setLocation()` a normal search
  uses — the search box, not just internal state, updates), then confirms that once switched to a
  LOW-pressure destination the alternatives panel honestly reports nothing further to suggest rather than
  lingering with stale alternatives — all with zero uncaught JavaScript errors. (This sandbox's own network
  egress blocks the real Nominatim/Overpass/unpkg hosts Sārthi normally talks to — confirmed independently,
  since `/api/geocode/search` against the real, unmocked backend also returns 403 here — so this test mocks
  the backend's HTTP responses with schema-accurate fixtures rather than live provider data; the backend
  side of that same data path is what the 37 backend tests above verify. A live end-to-end run against real
  Nominatim/Overpass data should be re-confirmed on a machine with normal internet access, e.g. your own.)

## Remaining SIH-track improvements (not required, just ideas)

- Get Hotelbeds certification-tier credentials for a real (non-50/day-capped) demo.
- Swap in PostGIS geometry columns for proper spatial queries at scale.
- Add user accounts so itineraries are private per traveller.
- Expand the curated cultural dataset; the Wikipedia/Wikidata fallback covers the rest reasonably well
  already.
- Add the Unsplash download-tracking ping if a "save this photo" feature is ever built.
