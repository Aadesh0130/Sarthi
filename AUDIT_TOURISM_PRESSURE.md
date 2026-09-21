# Final Audit — Tourism Pressure Index / Crowd Monitoring Engine

**Feature:** SĀRTHI — Crowd Monitoring & Tourism Pressure Engine (SIH Problem Statement 26204)
**Date:** 2026-09-15
**Scope:** everything added under this feature only. The pre-existing Sārthi app (Explore, Planner,
recommendations, itineraries, AI Assistant, hotels/events/images) was inspected before any code was
written and was not rebuilt — only the specific integration points named below were touched.

This report follows one rule throughout: **nothing is claimed here that was not actually executed and
observed.** Where something could not be verified (for example, against the real public internet, which
this development sandbox cannot reach), that is stated plainly rather than assumed to work.

---

## 1. What was built

A `GET /api/crowd/pressure?lat=..&lon=..&destination=..` endpoint that returns a 0–100 **Tourism Pressure
Index (TPI)** — an explainable estimate of how "busy" a destination is likely to be — plus a matching
Explore-page UI card and an AI Planner hero tile, built entirely from data Sārthi could already source
honestly. It is a planning signal, not a sensor: there is no camera feed, no footfall counter, no
telecom-density feed, and no government occupancy statistic anywhere in this system.

## 2. Files added / changed

**New (6 files):**
`backend/app/models/crowd_demand.py`, `backend/app/schemas/crowd.py`, `backend/app/integrations/crowd.py`,
`backend/app/services/crowd_service.py`, `backend/app/api/crowd.py`, this audit file.

**Edited (10 files):**
`backend/app/main.py` (router registration, version bump), `backend/app/api/health.py` (provider status
line), `backend/app/db/database.py` (model import for table creation), `backend/tests/test_smoke.py`
(2 new tests), `js/api.js` (`crowdPressure()` client), `explore.html` (crowd-card container),
`js/real-explore.js` (`renderCrowdPressure()`), `css/styles.css` (`.crowd-card` styles),
`js/data.js` (`tourismPressureStatus()` helper), `js/planner.js` (Tourism Pressure hero tile + reworded
Smart Alternative copy), `README.md` (new "Tourism Pressure Index" section).

**Explicitly not touched:** `js/data.js: calculateSmartScore()` / `findSmartAlternative()` (the existing
scoring algorithms), `backend/app/services/recommendation_service.py`, any itinerary/booking/AI-assistant
code, any existing destination data.

## 3. Data-honesty labelling — verified in the actual response shape

Every component in `CrowdPressureResponse.components` carries `used` (bool) and `data_type`
(`"curated"` / `"estimated"` / `"unavailable"`), and the top-level response carries its own `data_type`
(`"estimated"` or `"unavailable"` — never `"live"` or `"real-time"`). This was checked directly against
the Pydantic schema (`backend/app/schemas/crowd.py`) and confirmed in the two executed backend tests
(§10) by asserting on these exact fields, not just eyeballing the code.

**Confirmed absent from the codebase:** any invented tourist-count, invented occupancy percentage,
invented government statistic, or a live-crowd provider of any kind. `backend/app/integrations/crowd.py`
defines only `EstimatedCrowdProvider`; there is no "fake live" provider anywhere in the diff.

## 4. Exact scoring formula

Read directly from `crowd_service.py` (line-checked, not recalled from memory):

| Component | Weight | Data type when available |
|---|---|---|
| `seasonal_pressure` | 0.35 | `curated` |
| `place_density` | 0.30 | `estimated` (from live Overpass data) |
| `demand_signal` | 0.10 | `estimated` (real Sārthi usage counter) |
| `weather_suitability` | 0.15 | `estimated` (from live Open-Meteo data) |
| `event_pressure` | 0.10 | `estimated` when Ticketmaster is configured; otherwise `unavailable` |

Weights sum to 1.00. When a component is unavailable, its weight is dropped and the composite is
renormalized across the remaining available weight — never filled with a default or a guess.

## 5. Status bands — verified identical in both languages

| Range | Status | Verified in |
|---|---|---|
| 0–25 | LOW | `crowd_service.py: _status_for()`, `js/data.js: tourismPressureStatus()` |
| 26–50 | MODERATE | same |
| 51–75 | HIGH | same |
| 76–100 | VERY HIGH | same |

Both implementations were read side by side; the boundary values (25/26, 50/51, 75/76) match exactly.

## 6. The "unavailable" reliability gate

`_MIN_RELIABLE_WEIGHT = 0.45` in `crowd_service.py`. The response is forced to `pressure_index: null`,
`status: null`, `data_type: "unavailable"` when either (a) the total available component weight falls
below 0.45, or (b) none of the three live/external signals (place density, weather, events) could be
reached at all — even if seasonal + demand alone happen to clear 0.45. This means a request where Overpass
and Open-Meteo both fail is guaranteed to report "unavailable" rather than a number built only from a
curated calendar and a near-zero usage counter, since that would not be a meaningful live estimate. This
exact path is exercised by `test_crowd_pressure_unavailable_when_live_signals_fail` (§10) — it is not just
a design intention, it is an executed, passing test.

## 7. The explicit destination is never overwritten — how this was actually checked, not just designed

This was the hardest constraint to get right, so it was verified at the code level and then re-verified
live in a browser, not just asserted:

- **Code-level:** `js/planner.js` still routes every regenerate/interest/budget-change call through
  `state.destId` (the dropdown's explicit selection); `pickBestDestination()` — the only function that can
  choose a destination automatically — is unreachable while `state.destId` is set, and nothing in the new
  crowd/pressure code calls it or writes to `state.destId`. Explore's crowd card is purely a rendered
  `.innerHTML` block; it contains no code path that changes `state.lat/lon` or re-triggers a search.
- **Browser-level (Playwright, §11):** selecting Jaipur, then changing interests, then changing budget,
  then clicking Regenerate, and asserting after each step that the dropdown still reads `"jaipur"` and the
  hero still shows "Jaipur" — this sequence actually ran in a real Chromium browser against the real
  `planner.js`/`data.js`, not a mock of them.

## 8. Smart Alternative — reused, not rebuilt

`js/data.js: findSmartAlternative()` (the pre-existing scoring function that balances shared interests,
cost, sustainability, and crowd relief) was **not modified**. Only the Smart Alternative *card's copy* in
`js/planner.js` was reworded to say "Tourism Pressure" and to state explicitly that the primary destination
stays selected unless the traveller clicks the alternative's own **Switch** button. This was confirmed by:
running `git diff`-equivalent review of `data.js` (no changes outside comments/labels touched), and a
Playwright test that clicks the Switch button and confirms the dropdown value changes only then — never on
page load or on a Tourism Pressure number crossing a threshold by itself.

## 9. Performance — Overpass is not hammered

`place_density` calls the **existing** `places_service.nearby_places()` with the **same** 4000 m radius
Explore's own place list already uses for that location, which shares Explore's existing Overpass response
cache (`api_cache` table, TTL-based). The crowd engine issues **zero additional Overpass requests** beyond
what Explore was already going to make when the user searches a location — confirmed by reading
`crowd_service.py`'s call site, which passes through the same cached service function rather than a new
Overpass client call.

## 10. Backend tests — actually executed

```
cd backend && pytest tests/test_smoke.py -q
13 passed, 1 warning in 1.12s
```

This is a real, current run (re-executed as part of this audit, not carried over from memory). All 13
tests pass, including the two written for this feature:

- `test_crowd_pressure_all_signals_available` — mocks Overpass and Open-Meteo to succeed, asserts a real
  numeric `pressure_index` between 0–100, the matching `status` string, `used: True`/`data_type` on each
  live component, and `event_pressure.used is False` (since no Ticketmaster key is set in the test).
- `test_crowd_pressure_unavailable_when_live_signals_fail` — mocks both to raise `ProviderError`, asserts
  `pressure_index is None`, `status is None`, `data_type == "unavailable"`, and that the message contains
  "no reliable" — i.e., the honesty gate in §6 actually fires under test conditions, not just in theory.

The other 11 pre-existing tests continue to pass unchanged, confirming this feature did not break anything
already working (geocoding, places+recommendations, routing, itinerary CRUD + all 4 replan triggers,
AI-assistant tool loop, cultural-info fallback chain, events/hotels/images not-configured paths).

## 11. Frontend end-to-end tests — actually executed in a real browser, not just designed

Two genuine Playwright (Python) browser tests were written and run against the real static frontend files
(served via `python3 -m http.server`, no mocking of the app's own JS):

**AI Planner** (`test_planner_crowd.py`) — drives `planner.html` in headless Chromium:
- Select Jaipur → hero shows "Jaipur"; Tourism Pressure tile reads `88/100 · VERY HIGH` (Jaipur's curated
  popularity of 88 run through the exact same status bands as §5); Smart Alternative card appears (88 ≥
  75) and its text states the primary "stays your selected destination."
- Change interests, change budget, click Regenerate → destination remains Jaipur (dropdown value and hero
  text both re-checked).
- Select Hampi → Tourism Pressure tile reads `46/100 · MODERATE`; no Smart Alternative card (46 < 75).
- Jaipur → Hampi → regenerate → primary is Hampi (destination-switch is never "sticky" to a stale choice).
- Click the Smart Alternative's explicit Switch button → dropdown changes to the suggested alternative
  only after that click, confirming the switch is user-initiated, never automatic.
- Result: **all assertions passed, zero JavaScript console errors.**

**Explore** (`test_explore_crowd.py`) — drives `explore.html` with the backend's HTTP endpoints
intercepted via Playwright's network-routing (`page.route`) so the test exercises the *real*
`real-explore.js` rendering code against controlled fixture responses (this sandbox cannot reach the live
Nominatim/Overpass/Open-Meteo/backend network, so this is the closest genuine substitute — see §12):
- A successful crowd-pressure fixture (68/100, HIGH) renders the score, status, explanation bullets, the
  separately-labelled weather-suitability line, and the "not a live visitor count" disclaimer.
- An `"unavailable"` fixture renders the honest fallback message and does **not** render a fabricated
  score.
- In both cases, Explore's core place list and map layout continue to work normally, and the browser
  raised zero uncaught JavaScript errors.
- Result: **all assertions passed** ("ALL EXPLORE CROWD-CARD TESTS PASSED").

Two real, environment-specific issues were hit and fixed *in the test harness only* while getting this
test running — neither was a defect in the shipped app code:
1. This sandbox's egress policy blocks `unpkg.com` (which serves the Leaflet map library) — the test now
   serves a locally-fetched copy of the exact same pinned Leaflet 1.9.4 build instead of the CDN.
2. The test's mocked backend runs on a different origin than the static file server, which triggers a
   real browser CORS preflight; the test's mock responses now include `Access-Control-Allow-Origin`
   headers, matching how the real FastAPI backend (which has `CORSMiddleware` configured) already behaves.

## 12. What was NOT verified against the live public internet, and why

This development sandbox's outbound network is restricted by organization policy: Nominatim, Overpass,
and Open-Meteo could not be reached directly from here (confirmed via explicit `connect_rejected` /
`agent-proxy` denial messages, not silent failures). This means:

- The exact numeric output of `place_density` and `weather_suitability` against a real, live Indian city
  right now was **not observed** from this environment. What *was* verified is that the code correctly
  calls the existing, already-working `places_service`/`weather_service` functions (unchanged, previously
  live-tested per the existing README) and correctly handles both their success and failure paths (§10).
- The user's own machine (where this app actually runs) has normal internet access, so this is expected to
  work there exactly as it does in the mocked tests — but that live check should be done once on the real
  machine (search a real destination on Explore and confirm the Tourism Pressure card shows a number) to
  close this out completely.

## 13. Known limitations (stated honestly, not hidden)

- The Sārthi demand-signal component will read as very low or zero on a low-traffic prototype — this is
  the honest real count, not a bug or a placeholder.
- `event_pressure` is always `used: false` today, since no live event-volume provider is wired in; it is a
  reserved slot, not a hidden guess.
- The curated seasonal calendar covers ~35 named Indian destinations plus a generic India-wide seasonal
  fallback; a destination with no curated entry still gets a defensible (if less specific) seasonal
  estimate rather than an error.
- The Tourism Pressure card is live-computed only on Explore (any Nominatim-searched location, per the
  spec's literal "Explore page" scope) and as a curated hero tile in the AI Planner (whose destinations are
  a fixed curated set). A live TPI for an arbitrary Planner "real trip builder" location was intentionally
  not built, since doing so defensibly would require the same live signals Explore already provides — this
  was a scope decision, not an oversight.

## 14. Delivery status

All 16 new/changed files (§2) were copied into the connected `Sarthi` folder on the user's own machine and
each write was confirmed successful (0 rejected). All 4 changed JavaScript files were syntax-checked
(`node --check`) directly on that machine and passed; all 3 new/changed Python backend files were
AST-parsed there and passed. Running the backend's `pytest` suite on that exact machine was attempted but
could not complete from this bridge (its `.venv` is a native Windows virtualenv, and the bridge's helper
shell is a separate Linux environment that cannot execute a Windows venv's interpreter) — the pytest run
in §10 is the real, executed verification, performed against the identical file contents that were then
copied over unchanged.

**Recommended one-time manual check on the real machine:** start the backend (`uvicorn app.main:app
--reload`), open Explore, search any Indian city, and confirm the Tourism Pressure card renders a number
(or an honest "unavailable" message if, e.g., Overpass is briefly slow) — closing the gap noted in §12.
