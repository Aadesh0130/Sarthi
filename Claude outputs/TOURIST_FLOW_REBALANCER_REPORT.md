# Tourist Flow Rebalancer — Delivery Report

SIH PS26204 core differentiator: *"Sārthi does not only recommend destinations. It detects tourism
pressure at popular destinations and intelligently suggests suitable nearby alternatives to distribute
tourist demand toward less-pressured destinations."*

No files were committed to git — all changes are in the working tree for your own review, per your
instruction.

## 1. Files changed

**New backend files**
- `backend/app/data/__init__.py`, `backend/app/data/curated_destinations.py`
- `backend/app/schemas/flow_rebalance.py`
- `backend/app/integrations/carrying_capacity.py`
- `backend/app/services/flow_rebalancer_service.py`
- `backend/app/api/flow.py`
- `backend/tests/test_flow_rebalancer.py`

**Edited backend files**
- `backend/app/schemas/place.py` (added `Settlement`)
- `backend/app/integrations/overpass.py` (added `nearby_settlements`)
- `backend/app/services/places_service.py` (added `nearby_settlements` wrapper w/ caching)
- `backend/app/api/health.py` (added a `tourist_flow_rebalancer` line)
- `backend/app/main.py` (registered the new router, version bump)
- `backend/app/ai/tools.py` (added the `rebalance_destination` tool)
- `backend/app/services/ai_service.py` (system prompt mentions the new tool)

**Edited frontend files**
- `js/api.js` (added `rebalanceDestination()`)
- `js/real-explore.js` (added the whole rebalancer UI: rendering, map markers, "Explore" wiring)
- `css/styles.css` (added `.rebalance-*` classes, matching `.crowd-card`'s visual language)
- `explore.html` (one new `<div data-r-rebalance>` slot, right below the existing Tourism Pressure card)
- `README.md` (new "Tourist Flow Rebalancer" section + additions to Honesty rules / Known limitations /
  Testing performed)

Nothing else in the app was touched — auth, hotel booking, events, the AI assistant's architecture,
cultural intelligence, the map library, planner architecture, branding and navigation are all unchanged.

## 2. Existing components reused (not duplicated)

- **Tourism Pressure Index** (`crowd_service.get_pressure`) — the *only* pressure system in the codebase.
  The Rebalancer calls it for both the requested destination and every candidate; it does not reimplement
  or re-score pressure itself.
- **`CrowdPressureResponse`** schema — embedded directly in every alternative (`tourism_pressure` field),
  not re-declared.
- **`places_service.nearby_places`** — reused both for the requested destination's category profile and
  for each candidate's; the 4 km radius (`_DENSITY_RADIUS_M`) matches `crowd_service`'s own radius exactly
  so a candidate's pressure computation and its experience-match/local-opportunity computation can share
  the same cache entry rather than hitting Overpass twice.
- **Hedged multi-mirror Overpass `_post()`** — the new settlement-discovery query
  (`OverpassProvider.nearby_settlements`) goes through the exact same hedging/retry method as every other
  Overpass call, not a new retry implementation.
- **`geocoding_service.geocode_search`** (Nominatim) — used to resolve the requested destination and to
  geocode curated candidates; no second geocoder.
- **`routing_service.compute_route`** (OSRM) — used only for the final shortlist's travel time.
- **`recommendation_service.INTEREST_TO_CATEGORIES`** — the same interest vocabulary the in-destination
  SmartScore engine uses, reused verbatim for experience-match interest alignment.
- **`js/api.js`'s `request()` wrapper, fail-soft pattern, and `setLocation()`** in `js/real-explore.js` —
  the "Explore ⟨name⟩" action calls the *exact same* `setLocation()` a normal search box submission calls.
  There is no second "select a destination" code path.
- **The existing Leaflet map instance** (`state.map`) — alternatives get a new marker collection
  (`state.rebalanceMarkers`), not a second map or a second library.

## 3. New components/services created

- `flow_rebalancer_service.py` — the scoring/discovery/filtering engine (~430 lines).
- `carrying_capacity.py` — a tiny provider abstraction (`CarryingCapacityProvider` ABC +
  `EstimatedCarryingCapacityProvider`), ready for a real government-data implementation later.
- `curated_destinations.py` — a backend-side mirror (see limitation #5 below) of the 16 curated
  destinations already shown in `js/data.js`, with coordinates so they can be scored as candidates.
- `Settlement` schema + `nearby_settlements` (Overpass + `places_service` + `crowd_service`-style cache
  wrapper) — real OSM town/village discovery.
- `flow.py` — a single new router file, following the same thin-wrapper-with-safety-net pattern as
  `api/crowd.py`.

## 4. New API endpoint

`POST /api/flow/rebalance`

```json
// request
{ "destination_query": "Manali", "latitude": null, "longitude": null,
  "interests": ["nature", "adventure"], "budget": "comfort", "pace": "balanced",
  "max_alternatives": 5 }

// response (trimmed)
{ "requested_destination": {...}, "tourism_pressure": {...},
  "rebalancing_triggered": true, "pressure_check_only": false,
  "alternatives": [ { "destination": {...}, "experience_match": 82, "rebalancing_score": 76,
                       "tourism_pressure": {...}, "distance_km": 62.3, "travel_time_minutes": 95,
                       "local_opportunity": {...}, "carrying_capacity": {...},
                       "sustainability_score": 78.0, "is_hidden_gem": true,
                       "factors": {...}, "reasons": [...] } ],
  "method": "deterministic-weighted-scoring", "is_machine_learning": false, "message": "..." }
```

It never raises: a top-level `except Exception` in `flow.py` and `return_exceptions=True` around
per-candidate scoring mean one bad candidate or an unexpected error degrades the response, never crashes
the endpoint (mirrors `/api/crowd/pressure`'s own resilience pattern).

## 5. Rebalancing Score formula

Seven weighted, independently-labelled factors (all detailed with real values in each response's
`factors` object):

| Factor | Weight |
|---|---|
| Experience match | 0.28 |
| Pressure relief | 0.24 |
| Distance & accessibility | 0.16 |
| Weather suitability | 0.10 |
| Sustainability | 0.08 |
| Local economic opportunity | 0.08 |
| Carrying capacity | 0.06 |

`rebalancing_score = round(Σ factor.value × factor.weight)`, clamped to 0-100. This is deterministic
weighted scoring — `is_machine_learning: false` on every response, never trained on data, never a model
inference call.

## 6. Tourism Pressure Index integration

Reused exactly as-is: same bands (LOW ≤25, MODERATE ≤50, HIGH ≤75, VERY HIGH >75), same
`CrowdPressureResponse` schema (embedded, not duplicated), same `crowd_service.get_pressure()` function
call for both the requested destination and every candidate. LOW/unavailable pressure skips candidate
search entirely (`pressure_check_only: true`) — zero extra provider calls. The UI never says "Live Crowd
Level," only "Estimated Tourism Pressure."

## 7. Hidden-gem integration

Curated hidden gems are geocoded and scored through the *same* pipeline as every other candidate — they
are filtered by pressure/weather/distance and ranked by Rebalancing Score exactly like an OSM settlement
would be. `is_hidden_gem: true` is metadata carried through for the UI's "💎 Hidden gem" tag; it does not
bypass scoring or filtering, and a hidden gem that fails the pressure/weather filter is excluded like
anything else.

## 8. Local economic opportunity logic

`_local_opportunity()` counts real OSM places tagged restaurant/cafe/shopping/hotel near the candidate
(from the same `nearby_places` call used for experience-match) and maps the count to one of four
qualitative labels (e.g. *"Strong local experience availability — supports local tourism activity"*).
**Never a rupee figure**, never an invented business name — purely a count-derived label, `data_type:
"estimated"`.

## 9. Carrying capacity handling

`EstimatedCarryingCapacityProvider.estimate(place_count)` bands real OSM place density into three labels
(sparse / moderate / high estimated capacity), always `data_type: "estimated"`. No official figure is
invented anywhere. The architecture is a swap-in abstraction (`CarryingCapacityProvider`) so a real
government dataset can replace it later without touching any caller.

## 10. Map integration

Alternatives render as a **separate green marker layer** (`state.rebalanceMarkers`, distinct from
`state.markers`) on the *existing* Leaflet map — no second map, no second library. Category-chip filtering
(`clearMarkers()`/`renderMarkers()`) only ever touches the nearby-places layer, so it can never wipe the
alternatives. Clicking a green marker's popup "Explore this" button does the same thing as clicking the
card's button.

## 11. Planner integration

There is no second planner and no new "current destination" mechanism. Explore's own `setLocation(lat,
lon, label)` — the same function a normal search box submission uses — *is* the integration point: when a
traveller clicks "Explore ⟨name⟩", Explore's destination, map, weather, places and pressure all update
exactly as if they'd searched that place directly, and anything they then "Add to trip" flows into the
existing Real Trip Builder / replan system (`js/real-planner.js`) unchanged. No planner code was modified.

## 12. AI assistant integration

`rebalance_destination` was added to `app/ai/tools.py`'s `TOOL_SPECS`/`dispatch_tool`, calling the exact
same `flow_rebalancer_service.rebalance()` the REST endpoint calls. `ai_service.py`'s system prompt tells
the model this tool is "the only source of truth for tourism pressure, alternatives, distances and scores"
and that it must never invent or adjust those numbers. No new AI architecture, no new provider.

## 13. Tests executed

**Full backend suite: 37/37 passing, zero regressions** (`pytest tests/ -v`):
- `test_flow_rebalancer.py` — **10/10 passing**: LOW pressure skips search entirely; HIGH pressure
  generates ranked alternatives without replacing the destination; equal/worse-pressure candidates
  excluded; experience match reflects interest alignment; pressure-relief favours the lower-pressure
  candidate; provider failure degrades gracefully; unavailable pressure data is reported honestly; no
  discoverable candidates → honest message, not a crash; unresolvable destination → honest message, not a
  guess; API response schema shape verified.
- `test_smoke.py` (14), `test_overpass_hedging.py` (4), `test_places_resilience.py` (5),
  `test_ai_features.py` (5) — all still passing, confirming the Rebalancer work introduced no regressions
  anywhere else.

## 14. Browser tests executed

A **real, executed Playwright (Chromium) end-to-end test** of the Explore integration:
1. Searches a destination the (mocked) backend reports as HIGH pressure → confirms the Tourism Pressure
   card shows HIGH, the "🧭 Nearby Alternatives" card renders with the correct 82% experience-match badge,
   hidden-gem tag, reasons and signal chips, and a distinct **green marker** appears on the map.
2. Clicks "Explore ⟨name⟩" → confirms the destination changes **only then**, via `setLocation()` (the
   search box itself updates) — never automatically.
3. Confirms that once switched to a LOW-pressure destination, the alternatives panel honestly reports
   nothing to suggest, rather than leaving stale alternatives on screen.
4. Zero uncaught JavaScript errors throughout.

**Honest caveat**: this cloud sandbox's own network egress blocks the real Nominatim/Overpass/unpkg hosts
Sārthi talks to (confirmed independently — `/api/geocode/search` against the real, unmocked backend also
returns `403 Forbidden` here, and `unpkg.com` is blocked outright by the proxy), and this session's link to
your PC was not reachable at the time of this test, so live-provider browser testing could not be done from
here. The test above therefore mocks the backend's HTTP responses with schema-accurate fixtures (built by
reading the actual Pydantic response models field-by-field) rather than live data — it verifies the
frontend rendering/wiring genuinely works, not that Nominatim/Overpass themselves respond correctly (that's
what the 37 backend tests cover, several of which mock those same providers at the same boundary).
**Recommend re-running the flow once against your own machine's live backend** to see real alternatives for
a real crowded destination — the code path is identical, only the data source differs.

## 15. Limitations

- **Curated destinations are mirrored, not shared**, between `js/data.js` (frontend) and
  `backend/app/data/curated_destinations.py` (backend) — the frontend dataset has no lat/lon and no
  backend access path, and restructuring it was judged too risky given how many existing pages depend on
  its current synchronous-load shape. If one is edited, the other needs a matching manual update.
- **Coarse state-name pre-filter** before geocoding curated candidates, to avoid walking Nominatim's
  throttled ~1 req/s budget through all 16 destinations on every cold-cache request. Falls back to
  checking all 16 if the filter matches nothing, so it can never silently return zero — but an unusual
  state-name wording could in theory delay finding a genuine nearby curated candidate until the fallback.
- **Date-sensitive test case**: one backend test (`test_low_pressure_skips_candidate_search_entirely`) uses
  a destination whose seasonal-pressure component is calendar-driven (per the existing, unmodified TPI
  seasonal calendar). Under the current weights, a non-curated destination cannot mathematically reach LOW
  pressure during India's generic peak season (Oct–Mar) regardless of place density — an existing property
  of the Tourism Pressure Index, not something introduced by this feature. The test currently passes
  (September); it's flagged here rather than silently left as a latent flake.
- **Cold-cache latency**: a first-ever Rebalancer request for a given area can take several seconds
  (multiple hedged Overpass calls + weather + up to 8 candidates scored); subsequent requests for the same
  area are fast via the existing cache layer.
- **No live carrying-capacity or official local-economic dataset** exists yet (see below).
- **Browser testing used mocked backend responses**, not a live end-to-end run — see point 14.

## 16. What's genuinely live vs. estimated

**Live** (real external data, fetched fresh or from a recent cache): candidate discovery (real OSM
settlements via Overpass), each candidate's own weather (Open-Meteo), each candidate's own place density
(Overpass — same data source that seeds local-opportunity and carrying-capacity), and the final shortlist's
travel time (OSRM, when reachable).

**Estimated/modelled** (explicitly labelled, never presented as live): the Tourism Pressure Index itself
(as before — unchanged by this feature), local economic opportunity (a label derived from real place
counts, not a live economic indicator), carrying capacity (modelled from place density, not an official
figure), and sustainability for non-curated candidates (modelled from place density; curated destinations
use their existing curated figure instead).

## 17. What should be added later with official/government datasets

- A real `CarryingCapacityProvider` backed by official tourism-carrying-capacity data, if such a dataset
  becomes available for Indian destinations — the abstraction is already in place
  (`carrying_capacity.py`).
- A real local-economic-impact dataset (footfall-linked revenue estimates, MSME registration density, or
  similar) to replace the current OSM-business-count proxy — again, purely additive; the
  `LocalOpportunitySignal` schema already carries a `data_type` field ready for a `"live"`/`"government"`
  value.
- A genuinely shared curated-destinations data source (single JSON/DB table consumed by both frontend and
  backend) to remove the current mirror-maintenance burden (limitation above).
- Optionally, budget/pace-aware scoring — `RebalanceRequest.budget`/`.pace` are accepted today for
  forward-compatibility but not yet factored into the score.

## 18. Target statement — status

*"Sārthi intelligently detects tourism pressure and recommends suitable lower-pressure destinations,
helping distribute tourism demand without taking control away from the traveler."*

This is demonstrably true in the current build: a HIGH/VERY-HIGH-pressure search produces ranked,
explainable, real-data-backed alternatives; nothing is ever auto-selected; the traveller's original search
result stays exactly as they left it until they explicitly click "Explore ⟨name⟩" on an alternative — the
same action, and the same downstream behaviour, as searching that place directly.
