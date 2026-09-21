# Explore Page Bug Fix — Final Report

Scope: fix the three reported Explore-page bugs (sparse "1 real place" near Amritsar, "No suitable nearby alternatives," and the misbehaving Leaflet map) by fixing the existing implementation — no rebuild, no destination-specific hardcoding, no new systems. All 12 files changed are listed below and have already been written into your connected project folder (`Sarthi (2)\Sarthi`). **Nothing was committed to git** — you still need to review and commit.

## 1. Root causes

**"Showing 1 real place near Amritsar, Punjab, India."** Not a places/Overpass bug. I recovered your live `sarthi.db` cache and found Nominatim had resolved the search to the **administrative boundary** result (the Amritsar tehsil/district polygon, centroid ≈31.7686, 74.8316) instead of the actual city point (≈31.6357, 74.8787) — about 18 km apart, landing in a genuinely rural spot (Ghukewali) with real but sparse OSM data. Every downstream step (nearby places, pressure, rebalancer) was working correctly on the *wrong coordinate*. This isn't Amritsar-specific: any Indian place name that collides with its own enclosing administrative area's name (district/tehsil sharing the city's name) is affected the same way.

**"No suitable nearby alternatives could be found."** Direct consequence of the same wrong coordinate (a rural spot has few real OSM settlements nearby) *plus* a separate, real logic bug: the pressure filter in `flow_rebalancer_service.py` rejected any candidate whose **status bucket** (LOW/MODERATE/HIGH/VERY HIGH) wasn't strictly lower than the requested destination's — so a candidate at HIGH-58 was wrongly excluded against a requested destination at HIGH-74, even though that's a genuine 16-point relief. Your own bug report described exactly this case.

**Leaflet map misbehaving.** Three real bugs in `js/real-explore.js`: (1) the map was created via `L.map()` while `[data-r-layout]` (the map's container) was still `hidden`, so Leaflet cached the wrong internal size and never fixed it — no `invalidateSize()` call existed anywhere; (2) `renderMarkers()`'s `fitBounds()` and `loadPlaces()`'s later `setView()` both ran on every search, and the second always overrode the first, causing a visible "jump"; (3) there was no marker at all for the requested destination itself.

## 2. Files changed

- `backend/app/integrations/nominatim.py` — geocoding re-rank fix (root cause #1)
- `backend/app/services/places_service.py` — radius escalation ("Radius Strategy")
- `backend/app/api/places.py` — expose actual-radius-used response headers
- `backend/app/services/flow_rebalancer_service.py` — numeric pressure comparison, adaptive settlement radius, honest messaging, dev-only diagnostics
- `js/real-explore.js` — map lifecycle, destination marker, unified viewport, radius-aware/loading messaging
- `js/api.js` — surface new radius headers to the frontend
- `.gitignore` — close a gap (`*.db-journal`/`*.db-wal`/`*.db-shm`)
- 5 test files (1 modified, 4 new) — see §6

## 3. Exact fixes made

**Nominatim (`nominatim.py`):** `NominatimProvider.search()` now always fetches at least 5 results internally (even when the caller wants 1), then runs `_prefer_precise_over_boundary()`, a stable re-rank that demotes an `"administrative"`-type result below any more location-precise result (city/town/village/attraction/...) in the *same* result set — unless the boundary is clearly far more prominent (importance margin of 0.05, so genuine region searches like "Kerala" or "Rajasthan," which have no more-precise same-name alternative, are correctly left alone). Nothing here names Amritsar or any other city in its logic — only comments documenting the incident that motivated it.

**Radius Strategy (`places_service.py` + `api/places.py`):** `nearby_places()` now tries the requested radius, then 2×, then 3× (capped at 15 km, matching the endpoint's own limit), stopping as soon as a tier returns ≥6 places. Each tier is cached under its own key. A wider tier that has neither a live response nor its own cache entry no longer turns an already-successful (even if stale) narrower-tier result into a hard failure — it just stops widening (this was a real bug I introduced during implementation and caught via the existing test suite; see §7). The actual radius used is now always exposed via `X-Sarthi-Requested-Radius-Meters` / `X-Sarthi-Effective-Radius-Meters` response headers, and the frontend shows it honestly ("search widened to 8 km — this area is sparse in OpenStreetMap") instead of ever implying the original radius when a wider one was actually used.

**Pressure comparison (`flow_rebalancer_service.py`):** The candidate filter now compares the actual numeric `pressure_index` when both requested and candidate have one, requiring at least a 5-point relief (guards against 1-2 point noise being read as "improvement") — falling back to the coarser status-bucket rank only when a numeric index is missing on either side. HIGH-74 vs HIGH-58 is now correctly eligible; HIGH-60 vs HIGH-59 is correctly still excluded. A candidate with no pressure signal at all is still never excluded on that basis alone (unchanged, already correct).

**Candidate discovery (`flow_rebalancer_service.py`):** `_discover_candidates()` already combined OSM settlements and curated destinations (not limited to the 16 curated entries — confirmed via test). I added one bounded radius widen (70 km → 150 km) when the normal-radius settlement search comes back sparse (<3 results), so a genuinely remote requested destination doesn't wrongly appear to have zero real alternatives nearby.

**Honest messaging:** the "genuinely zero candidates found" case now says *"Lower-pressure alternatives could not be confirmed from the available data for this location right now"* instead of the old, more absolute-sounding "No suitable nearby alternatives could be found" — distinct from the separate "candidates were found but didn't pass the pressure/weather filter" message, which was already appropriately worded.

**Dev-only diagnostics:** added `logging.getLogger(__name__).debug(...)` calls at every candidate-rejection point (by distance, by pressure, by weather, by geocoding failure, by dedup, by scoring exception) — DEBUG level only, never returned in any API response, inert unless a developer explicitly enables DEBUG logging for this logger.

**Leaflet lifecycle (`real-explore.js`):** sequencing is now search → data loads → `els.layout.hidden = false` → `map.invalidateSize()` → destination marker placed → nearby-place markers rendered → a single `updateMapView()` decides the viewport. `updateMapView()` collects the destination + all currently-visible nearby-place markers + all rebalancer alternative markers; if there are 2 or fewer points total (just the destination, or destination + one nearby place) it does a plain centered `setView(..., 13)` rather than an aggressive `fitBounds()` on a near-single point; otherwise it fits bounds around everything with sensible padding/`maxZoom`. This replaced the old competing `fitBounds()`/`setView()` calls entirely — there is now exactly one place in the code that decides the map view. A new 🔴 destination marker (same `leaflet-color-markers` icon pattern already used for the green alternative marker, just red, with the highest `zIndexOffset` so it's never hidden under other pins) is added via `renderDestinationMarker()` and is now always present once a location is set. `clearMarkers()`/`clearRebalanceMarkers()` separation (nearby-place vs. alternative markers) was already correct and is unchanged.

## 4. Behavior before / after

| | Before | After |
|---|---|---|
| API | `/nearby` always used exactly the requested radius, no escalation, no way to know if data was sparse for a structural reason | Escalates radius (capped), reports actual radius via headers, never silently caches a temporary provider failure as a permanent empty result |
| Map | Created while hidden → wrong cached size; `fitBounds()`/`setView()` raced; no destination marker | Sized correctly after becoming visible (`invalidateSize()`); one unified view function; 🔴 destination marker always present, distinct from 📍 nearby and 🟢 alternative markers |
| Rebalancer | Same-status-bucket candidates with real numeric relief wrongly excluded; "no candidates found" and "candidates filtered out" used similar-sounding messages | Numeric relief (≥5 points) makes a same-bucket candidate eligible; the two "no alternatives" cases now read differently and honestly |

## 5. Test destinations used

Given this sandbox has no route to the real Nominatim/Overpass/Open-Meteo/OSRM services (confirmed blocked, same as earlier phases of this project) and the linked Windows machine's local shell is currently unavailable (a known Windows-update-related platform bug, unrelated to this fix), **I could not run live end-to-end searches for Amritsar, Delhi, Jaipur, Manali, Goa, or Rishikesh from this session.** Instead I verified via:

- **Real captured data**: the exact Nominatim payload from your own cache for the Amritsar incident, replayed against the fixed code (`test_nominatim_precise_over_boundary.py`).
- **A mocked-backend Playwright run** against the real, unmodified `explore.html`/`js/real-explore.js`/`js/api.js` for a made-up destination ("Testchester") that appears nowhere in curated data or peak-season lookups — chosen specifically to prove the fix has no destination-specific behavior. Result: map sized correctly (584×520, not 0×0), all three marker types present with the correct distinct icons (red destination, default nearby, green alternative), 9 tiles requested, correct place count text, and a correctly rendered rebalancer alternative card. Screenshots were sent to you in this conversation.
- **Parametrized backend tests** (`test_rebalancer_for_arbitrary_destination`) across three more made-up destination names, each exercising the full `/api/flow/rebalance` pipeline end to end.

## 6. Test results

54 backend tests pass (37 pre-existing + 17 new/updated), run with a clean environment (no live API keys — see §8 on why that matters):

- New: `test_nominatim_precise_over_boundary.py` (3 tests — Amritsar-shaped payload, region-only search, prominence-margin guard)
- New: `test_flow_rebalancer_numeric_pressure.py` (5 tests — your exact HIGH-74/HIGH-58 example, VERY HIGH/HIGH cross-bucket, no-meaningful-relief still excluded, status fallback, unavailable-pressure not excluded)
- New: `test_flow_rebalancer_candidate_discovery.py` (6 tests — settlement radius widen/skip, not-limited-to-curated, 3× parametrized arbitrary-destination end-to-end)
- Extended `test_places_resilience.py` (+3 tests — radius escalation, max-radius cap, response headers)
- Updated `test_flow_rebalancer.py` (1 assertion updated for the new honest wording)

## 7. Provider limitations / honest process note

While implementing the radius escalation, I initially introduced a real regression: if a widened tier (never searched before) had neither a live response nor its own cache entry, it raised an error instead of gracefully returning the narrower tier's already-successful (possibly stale) result. Running the full existing test suite caught this immediately (`test_nearby_places_falls_back_to_stale_cache_when_every_mirror_fails` failed), and I fixed it — a wider tier's failure now only stops further widening, it never discards a result already found. This is exactly the kind of thing "run the tests before declaring done" is for, and I'm flagging it rather than glossing over it.

Also found during testing (not a code bug, an environment fact worth knowing): your `backend/.env` currently has real `GEMINI_API_KEY` and `TICKETMASTER_API_KEY` values configured, which flips several *other*, unrelated existing tests that assert "not configured" behavior. I ran the suite with those specific variables blanked to get a clean baseline — I did not modify your `.env` or those tests, and I never printed the key values.

## 8. Security check (Part 14)

Confirmed clean: `backend/.env`, `backend/sarthi.db`, and `backend/sarthi_verify.db`/`-journal` have never been committed to git in this repository (`git log --all --full-history` on each path returns nothing) and are not currently tracked. `.gitignore` now also excludes `*.db-journal`, `*.db-wal`, `*.db-shm` (previously only `*.db` itself was covered, leaving the journal file technically uncovered even though it was never actually committed). No secret values were printed anywhere in this session.

## 9. Remaining limitations

- No live end-to-end verification against the real Nominatim/Overpass/Open-Meteo/OSRM services was possible from this session (see §5) — please spot-check Amritsar and 2-3 other real destinations yourself once you pull these changes.
- The settlement-radius widen (70 km → 150 km) and place-radius escalation (×1/×2/×3, capped 15 km) thresholds are reasonable defaults, not tuned against real traffic — you may want to adjust `_SPARSE_MIN_RESULTS`, `_SETTLEMENT_SPARSE_MIN`, or the radius constants after seeing real usage.
- The Nominatim fix demotes `type == "administrative"` results specifically; if a future real-world report shows a different Nominatim `type` value causing the same city-vs-boundary confusion, the fix (in `_BROAD_BOUNDARY_TYPES`) is a one-line set to extend.
- I did not touch `backend/.venv2/` (a Python virtual environment I created in this sandbox purely to run the test suite) — it's untracked and now gitignored, safe to delete, not part of the actual project.

## 10. Delivery

All 12 changed/added files were written directly into your connected folder (`Sarthi (2)\Sarthi`) via the file bridge, since your machine's local shell link is currently down (the same Windows-update issue noted earlier). **Nothing was committed** — `git status`/`git diff` in that folder will show exactly what changed for you to review.
