# Sārthi — Frontend + Backend Integration: Final Report

No git commit or push was made anywhere in this work, per your explicit instruction. Everything below lives only in the plain project folder `SarthiUnified/Sarthi` (delivered as a zip) so you can inspect it before deciding what to do with it.

## 1. Frontend files changed
`explore.html`, `planner.html` — each gained a new "REAL …" section (live search+map on Explore, real trip builder on Planner) inserted next to the existing curated section, plus new script tags. `index.html`, `flights.html`, `food.html`, `guides.html`, `services.html` — added a "Sign in" nav button, the shared login modal shell, and the `config.js`/`api.js`/`auth.js` script includes. `css/styles.css` — grew from 804 to ~2,370 lines by appending two whole ported blocks (SmartScore "Why recommended" + the entire real-data-layer component set) plus a small new auth-modal block; nothing existing was edited or removed. `js/main.js`, `js/data.js`, `js/explore.js`, `js/planner.js`, `js/hidden-gems.js`, `js/flights.js`, `js/food.js`, `js/guides.js`, `js/services.js` — untouched.

## 2. Backend files changed
`app/main.py` (added the auth router), `app/core/config.py` (added the auth settings fields onto the existing lowercase `Settings` class), `app/db/database.py` (added the auth models to the one `init_db()` import list), `app/models/user.py` / `otp.py` / `trip.py` / `__init__.py` (one import-path line each, logic untouched), `app/core/security.py` and `app/services/auth_service.py` / `sms_service.py` (import lines only), `requirements.txt` (added `python-jose`, `email-validator`, `google-auth`, `twilio`), `.env` / `.env.example` (appended the new `AUTH_*`/`JWT_*`/`SMS_*` variables). `app/database.py` and `app/config.py` (the uploaded project's own standalone auth-only config/DB modules) were deleted — fully superseded by the merged versions above.

## 3. Existing functionality reused (not rebuilt)
The entire tourism engine — geocoding, places, weather, routing, events, hotels, images, culture, recommendations, itineraries, AI assistant, Tourism Crowding Index, Tourist Flow Rebalancer, District Discovery — is the same backend code already built in the earlier "Sarthi2" work, copied in wholesale with zero duplication. The entire visual frontend (layout, branding, colours, cards, nav, planner form, curated Explore grid, flights/food/guides/services pages) is the uploaded project's own HTML/CSS, untouched except for the additive insertions described above. The existing generic modal (`[data-modal]`, already used for the checkout confirmation) is what the new login UI reuses — no new modal chrome was invented.

## 4. New integrations added this pass
Real phone-OTP + JWT authentication, wired end-to-end from a new nav "Sign in" button through a new `js/auth.js` login modal to the existing (previously unwired) auth backend (`models/user.py`, `otp.py`, `trip.py`, `services/auth_service.py`, `sms_service.py`, `core/security.py`) via one new router, `app/api/auth.py`.

## 5. API endpoints used (already existed, now actually called by the frontend)
`/api/geocode/search`, `/api/places/nearby`, `/api/places/{id}`, `/api/places/{id}/culture`, `/api/weather`, `/api/routes`, `/api/recommendations`, `/api/itineraries` (+ update/replan), `/api/ai/chat`, `/api/events`, `/api/hotels` (+ check-rate), `/api/images/search`, `/api/culture/{id}`, `/api/crowd/pressure`, `/api/flow/rebalance`.

## 6. API endpoints added
`POST /api/auth/phone/request-otp`, `POST /api/auth/phone/resend-otp`, `POST /api/auth/phone/verify-otp`, `POST /api/auth/google`, `GET /api/auth/me`, `POST /api/auth/onboarding`, `PUT /api/auth/profile`, `POST /api/auth/logout`, `GET /api/auth/status`.

## 7. Static data converted to dynamic
Everything under the new "REAL …" sections on Explore and Planner: destination resolution, nearby places, weather, the Crowding Index, Tourist Flow alternatives, District Discovery, events, hotels, images, culture, itinerary generation/replanning, and now sign-in/session state. All of it was already dynamic from the earlier backend work; this pass's job was wiring it into the uploaded frontend's actual pages rather than converting new curated data.

## 8. Remaining curated fallback data (left as-is, by design)
The original Explore destination-grid section (`js/explore.js` + `js/data.js`'s `SARTHI_DATA`), the curated AI Planner form above the real trip builder, and `flights.html`/`food.html`/`guides.html`/`services.html` are all still fully curated/example content. This is intentional, not an oversight — see point 23.

## 9. Crowding Index implementation
Unchanged from the existing `crowd_service.py`: an "Estimated Tourism Pressure" composite of real OSM place density, seasonality, live weather, Sarthi's own usage, and (when configured) live Ticketmaster events — never a live visitor count, never `Math.random()`. Now reachable from Explore's real search flow.

## 10. Tourist Flow Rebalancer implementation
Unchanged deterministic weighted-scoring engine (`flow_rebalancer_service.py`) over real Tourism Pressure + OSM data — confirmed via `grep` that no `if destination ==`/`destinationMap`-style hardcoding exists anywhere in it or in the frontend wiring.

## 11. District Discovery implementation
Same `/api/flow/rebalance` response's `district_alternatives[]`, rendered by a dedicated "Nearby Similar Districts" card/marker set, independent of the settlement-alternative list (an empty one never hides the other).

## 12. Planner implementation
The new "Real Trip Builder" section on `planner.html` (`js/real-planner.js`) organizes real places you add from Explore by day, computes a real OSRM route, checks real weather, and calls the existing `POST /api/itineraries` + `/replan` endpoints — all additive next to (not replacing) the original curated AI Planner form, whose "Custom" budget option was verified still present after the merge.

## 13. Weather integration
Open-Meteo, unchanged — now driving both the Explore search results and the Real Trip Builder's day-by-day suitability.

## 14. Routing integration
OSRM, unchanged — the Real Trip Builder's "Optimize route" button now calls it for real, showing "Travel time unavailable" on failure rather than a fabricated number.

## 15. Events integration
Ticketmaster, unchanged — shown on both Explore and the Real Trip Builder, with an honest "no matching Ticketmaster-listed events" message rather than "nothing is happening."

## 16. AI integration
Backend-mediated only (Gemini, per `ai_provider` config) — the frontend never calls Gemini/OpenAI directly; unchanged from the existing `ai.py`/`ai-assistant.js`.

## 17. Authentication integration (new this pass)
Real phone-OTP flow: 6-digit OTP generated server-side (`secrets.randbelow`), HMAC-hashed with a per-record salt, rate-limited (60s resend cooldown, 5 attempts), 5-minute expiry, JWT issued on success (`python-jose`), dual auth support (Bearer token, primary; httpOnly cookie, defense-in-depth). Verified for real against the running backend: request → OTP printed only to the **server console** (dev mode, no Twilio configured) → verify → real JWT → authenticated `/me` → onboarding → logout → `/me` correctly returns 401 afterward. The OTP never appears in any HTTP response body (asserted by test and confirmed by direct inspection of the real response). Google Sign-In is wired in the backend (`google-auth` library) but has no `GOOGLE_CLIENT_ID` configured, so `/api/auth/status` honestly reports it as unavailable rather than faking it — no Google button is shown on the frontend in that state.

## 18. Database changes
One SQLite database (`sarthi.db`), one `Base`, one `init_db()`. Verified directly: after a real signup, the file contains all 8 tables — `users`, `otp_verifications`, `saved_trips` (auth) alongside `api_cache`, `destination_demand`, `itineraries`, `itinerary_items`, `cultural_information` (tourism) — no second database, no MongoDB, exactly as required.

## 19. Environment variables required
Existing (unchanged): `DATABASE_URL`, `NOMINATIM_*`/`OVERPASS_*`/`OSRM_*`/`OPEN_METEO_*` (all free, no key), `AI_PROVIDER` + `OPENAI_API_KEY`/`GEMINI_API_KEY`, `TICKETMASTER_API_KEY`, `HOTELBEDS_API_KEY`/`HOTELBEDS_SECRET`, `UNSPLASH_ACCESS_KEY`, `CORS_ORIGINS`. New this pass: `JWT_SECRET`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_DAYS`, `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`, `AUTH_DEV_MODE`, `SMS_PROVIDER`, `SMS_ACCOUNT_SID`/`SMS_AUTH_TOKEN`/`SMS_FROM_NUMBER`, `OTP_EXPIRE_MINUTES`, `RESEND_COOLDOWN_SECONDS`, `MAX_OTP_ATTEMPTS`, `OTP_SALT`. **Flag, not alarm:** `backend/.env`/`.env.example` already contain real-looking Gemini/Ticketmaster/Hotelbeds/Unsplash keys carried over from your own earlier prototype — they were left as-is (not regenerated or scrubbed) since that's pre-existing project data, but you may want to rotate/redact them before sharing this zip further.

## 20. Tests performed
Backend: full pytest suite, 65 passed. 6 tests fail in *this sandbox only* — and reproduce identically when run against the unmodified reference backend — because `.env`'s real keys make `ai_configured`/`events_configured`/etc. report `True` where those specific tests assume a keyless environment; this is a pre-existing environment artifact, not a regression (the app's actual behavior — "configured" when a key is actually present — is correct). New: 6 auth tests (`test_auth.py`) covering OTP-never-in-response, full login→JWT→protected-endpoint flow, wrong-OTP rejection, unauthenticated 401, invalid-phone rejection, honest dev-mode status reporting — all pass.

## 21. Browser tests performed
Real backend (port 8000) + real static frontend server + headless Chromium via Playwright: confirmed both `js/config.js`/`js/api.js`/`js/auth.js` load on every page; confirmed the sign-in modal opens, accepts a phone number, and renders the OTP-entry step after a real (non-mocked) request to the backend; confirmed the Explore search input is wired to a real `/api/geocode/search` call and shows an honest error status rather than nothing when that call fails; confirmed the Planner's "Custom" budget option survived the merge; confirmed the Real Trip Builder correctly shows/hides based on real localStorage trip data; confirmed zero uncaught JavaScript exceptions on any page. **A real bug was found and fixed during this testing** — see point 24.

## 22. Destinations tested
Full functional testing of the crowding/rebalancer/planner engines against real destinations was already done in the earlier backend-only work (Amritsar, Jaipur, Goa, Manali, Munnar, Mysuru, Hampi, Darjeeling, Kolkata, Shillong, Gangtok, Shimla, Leh, plus a non-curated destination, per that session's test suite). This pass's testing focused on the *integration* — confirming the frontend actually reaches these same, already-verified backend code paths. **Live network calls to Nominatim/Overpass/Open-Meteo cannot be exercised from this sandbox** (its outbound network returns `403 Forbidden` from Nominatim — a sandbox limitation, not a code issue; the code's own test suite already documents this: "this sandbox has no route to the public Nominatim/Overpass/OSRM/Open-Meteo endpoints"). Please re-run a real search on your own machine, which has normal internet access, to confirm the live-provider path end-to-end.

## 23. Provider limitations (honest, as required)
Flights/trains/buses (`flights.html`), local-artisan/food story pages (`food.html`, `guides.html`), and the services hub (`services.html`) have **no matching backend today** — Sarthi's providers cover geocoding/places/weather/routing/events/hotels/images/culture, not flight/train/bus booking or a bespoke "food story"/"guide" API. Per your explicit instruction not to invent an unrelated API, these four pages were left as clearly-labelled prototype/demo content (the site's own footer already says "prototype... no real bookings or payments"); they now at least share the same sign-in system as the rest of the site. This is genuinely remaining integration work, not something skipped by accident. Also: Google Sign-In needs a real `GOOGLE_CLIENT_ID` before it can appear; SMS delivery needs real Twilio credentials before OTPs leave the server console; Leaflet/Google Fonts/Unsplash all load from third-party CDNs and need outbound internet (see point 24 for what happens when they don't).

## 24. Remaining issues / a bug found and fixed
While testing, I found that both `js/real-explore.js` and `js/real-planner.js` had a hard `if (!window.L) return` at the very top — meaning if the Leaflet map library's CDN script ever failed to load for *any* reason (slow network, corporate firewall, ad-blocker, CDN outage — exactly what this sandbox's network hits), the **entire** real-data search/weather/crowding/rebalancer/trip-builder feature set silently went dead, not just the map. I fixed this: both files now only require the backend API client, and every Leaflet-specific call site (`initMap`, marker/circle rendering, route-line drawing) is individually guarded, with an honest "🗺️ Map temporarily unavailable" note in the map's place. Retested: with Leaflet blocked (this sandbox's actual condition), search/weather/crowding/rebalancer/districts/trip-builder all now work correctly and show real error states instead of doing nothing. This should also make the site more robust on a real network with a flaky CDN. No other functional defects were found. Two things I did not attempt, both correctly out of scope per your own instructions: (a) wiring flights/food/guides/services to real APIs that don't exist (point 23), and (b) fixing the 6 pre-existing key-dependent test assumptions (point 20) — happy to do either if you'd like.

---

## Addendum — continuation pass (audit + your real-machine crash)

**1. Your backend crash, diagnosed and fixed.** Your real `uvicorn` run crashed with `ModuleNotFoundError: No module named 'email_validator'`. Root cause: `backend/requirements.txt` gained four new packages during the auth merge (`python-jose[cryptography]`, `email-validator`, `google-auth`, `twilio`), but your actual `.venv` at `backend\.venv` hadn't had `pip install -r requirements.txt` re-run since. This isn't something I can run for you remotely — the remote shell this session can reach your files with runs in an isolated Linux VM, which is the wrong platform for installing packages into a native Windows `.venv` anyway. Run this yourself in PowerShell:
```powershell
cd "C:\Users\hii\Downloads\Sarthi (2)\Sarthi\backend"
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
then restart `uvicorn app.main:app --reload --port 8000`.

**2. Security finding, fixed: `backend/.env.example` contained real API keys, not placeholders.** Unlike `.env` (which is correctly gitignored), `.env.example` is a template file that's *meant* to be committed — and it had your actual Gemini, Ticketmaster, Hotelbeds, and Unsplash keys typed in as the default values instead of blanks. I've replaced all four with empty placeholders and pushed the corrected file to your machine (it's already overwritten on disk at `backend/.env.example`). **You should check whether the old version was ever committed** — from your project folder, run `git log --oneline -- backend/.env.example`. If any commit shows up, those four keys were exposed in your git history (and doubly so if you've ever pushed) and should be rotated: Gemini (aistudio.google.com/apikey), Ticketmaster (developer-acct.ticketmaster.com), Hotelbeds (developer.hotelbeds.com), Unsplash (unsplash.com/developers). I could not check your git history myself — the remote shell into your machine is currently down (see point 5).

**3. Codebase sweep (Phase 29/1 of your continuation spec): clean.** Searched the entire frontend (`js/`) and backend (`backend/app/`) for `Math.random()`, Python `random.*`, and any destination-name conditionals (`if city == "..."` etc.). Found zero instances of randomness or hardcoding in real tourism-intelligence code. The one seeded-RNG usage found (`js/planner.js`) belongs to the pre-existing *curated* static planner (shuffles order among a fixed curated activity pool for the demo itinerary, not live crowd/weather/price data) and is unrelated to the real-data layer — this was already true before this session and is documented, not something I introduced. No `AGENTS.md`/`PROJECT_SPEC.md`/`ARCHITECTURE.md`/`DATABASE_SCHEMA.md`/`API_CONTRACT.md`/`TASKS.md` exist in the project beyond your own `README.md`/`AUDIT_TOURISM_PRESSURE.md`/`EXPLORE_BUGFIX_REPORT.md` and prior Claude session reports — nothing else to audit there.

**4. API contract audit (Phase 25): matches, with one real gap found.** Cross-checked every call in `js/api.js` against the backend's actual routes (paths, methods, prefixes) — geocode, places, weather, routes, recommendations, itineraries/replan, events, hotels, images, culture, crowd/pressure, flow/rebalance, and the full auth set all line up exactly. One genuine gap: the backend has real, implemented `/api/ai/plan-trip`, `/api/ai/replan-trip`, and `/api/ai/analyze-image` endpoints (AI-reasoned full itinerary generation/replanning, and Gemini-vision photo place-identification) that **no frontend code calls at all** — `js/api.js` doesn't expose them and nothing references those paths. They're real, working, non-trivial services (283 and 135 lines respectively), just not wired to any UI yet. I did not wire them up this pass — adding new UI for a full AI-itinerary flow and a photo-upload flow is a real feature addition, not a bug fix, and your spec is explicit that reliability comes before adding features. Flagging it as the clearest piece of "backend built, frontend not yet caught up" work remaining. The AI chat assistant (`/api/ai/chat`) itself is real and tool-grounded — it can call `search_places`, `get_nearby_places`, `get_weather`, `get_recommendations`, `get_events`, `get_hotels`, `get_cultural_info`, and `rebalance_destination` (all hitting the same real services as the REST API, never inventing data) — though its tool names/coverage differ somewhat from the exact list in your latest spec message (e.g. no standalone `calculate_route` or `get_hidden_gems` tool, and itinerary generation isn't in its tool loop — it lives in the separate, unwired `plan-trip` endpoint above).

**5. Full end-to-end regression (Phases 32-38) — blocked right now, not skipped.** Your continuation spec asks for real multi-destination browser testing against a genuinely running app. Two things are blocking that today: (a) your backend can't start until you run the `pip install` in point 1, and (b) the remote shell this session uses to act on your machine is currently down — a Windows update from September 8 is preventing it from reaching your files (this is a known issue being tracked, not specific to this project; file reads/writes still work, just not running commands). Once you've run the pip install and confirmed `uvicorn` starts cleanly, tell me — I'll either resume the remote shell if it's back, or walk you through the same 13-destination + live-provider checklist so we get real results either way, rather than me declaring it done without actually having run it.

Nothing in this addendum touched git — no commits, no pushes, no branch changes.
