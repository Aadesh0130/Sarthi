# Crowding Index + Nearby Similar Districts — Implementation Report

Sārthi Tourist Flow Rebalancer, Part 2 (SIH PS26204). Covers exactly the two
gaps you flagged: the Crowding Index wasn't visible on the destination page,
and "Nearby Similar Districts" (coarser administrative-area alternatives, as
opposed to the individual-POI "Nearby Places") didn't exist at all.

**Nothing in this delivery was committed to git** — all files were written
directly into your connected folder (`Sarthi (2)/Sarthi`) for you to review
and commit yourself, per your instruction.

---

## 1. Why the Crowding Index was missing

The backend already computed a full Tourism Pressure Index in
`crowd_service.get_pressure()` and the Explore page already called
`/api/crowd/pressure` and rendered a `.crowd-card` — so the *engine* existed,
but two things were missing before it could be called a proper "Crowding
Index" per your spec: (1) the API response had no **confidence** figure, so
the frontend couldn't say how much of the score was backed by real signals
vs. reweighted around gaps, and (2) there was no explorable "how is this
calculated" breakdown — the `components` dict was already being returned by
the schema but the frontend never rendered it, so a user had no way to see
*why* a score was what it was. This delivery closes both gaps by extending
the existing response/UI rather than replacing anything.

## 2. Where the crowding calculation comes from

Exactly one source of truth, unchanged: `backend/app/services/crowd_service.py`
→ `get_pressure()`, backed by `backend/app/integrations/crowd.py`
(`EstimatedCrowdProvider`) and schemas in `backend/app/schemas/crowd.py`. No
second/competing crowding calculation was created anywhere in this delivery.
The API route (`backend/app/api/crowd.py`, unchanged) and the Explore page's
existing `API.crowdPressure()` call were both left exactly as they were.

## 3. Exact Crowding Index formula/signals

Weighted composite of five independently-optional components, rebalanced
across whatever actually succeeds this call:

| Component | Weight | Source |
|---|---|---|
| Seasonal pressure | 0.35 | Curated peak/shoulder/off-season lookup (always available) |
| Tourism place density | 0.30 | Live OpenStreetMap (Overpass) place count within 4 km — shared cache with Explore's own nearby-places call |
| Weather suitability | 0.15 | Live Open-Meteo outdoor suitability |
| Sarthi demand signal | 0.10 | How many times Sarthi's own users have looked this spot up |
| Event pressure | 0.10 | Live Ticketmaster event count (only if configured) |

`pressure_index = round(Σ(component.value × component.weight / total_weight))`,
clamped 0–100. Status buckets: LOW ≤25, MODERATE ≤50, HIGH ≤75, VERY HIGH
>75 (unchanged, existing thresholds — I did not introduce new ones).

**New field added, not a new formula:** `confidence = round(min(1.0,
total_weight), 2)` — the share of the composite's *intended* weight that
actually came from a component available this call (e.g. 0.90 when only
events were missing). This directly reuses the `total_weight` variable
`get_pressure()` already computed for the rebalancing step — no new metric
was invented. If total available weight drops below 0.45, or no live signal
(place density/weather/events) is present at all, the whole response
honestly reports "unavailable" rather than a number, same as before.

## 4. How district candidates are discovered

Entirely dynamic, in `flow_rebalancer_service._discover_district_candidates()`:

1. Query OpenStreetMap Overpass for `boundary=administrative` relations with
   `admin_level` in **5, 6, or 7** (a *range*, not one exact level — India's
   districts are tagged inconsistently across states) within 120 km of the
   requested destination's coordinates, fetching only `out center tags`
   (centroid + tags, never full polygon geometry — this is also why boundary
   polygons aren't rendered on the map; see limitations).
2. If fewer than 2 districts come back, widen once to 220 km (mirrors the
   existing settlement-discovery sparse-radius pattern) and merge results.
3. Exclude the destination's own current district (resolved via Nominatim's
   address breakdown — `district`/`state` fields added to `GeocodeResult`).
4. Drop candidates under 15 km (same place) or over 300 km (not "nearby")
   from the requested destination.
5. Sort by distance, keep only the closest 6 (staged pipeline — cheap
   discovery/filtering happens here; expensive scoring happens only for
   these few, next).

No destination is ever looked up in a lookup table — there is no
`amritsar_alternatives.json` equivalent, and `test_flow_rebalancer_districts.py::test_no_destination_specific_district_mapping_in_source`
statically greps the actual source of this function for banned literals
(`amritsar`, `manali`, `jalandhar`, etc.) and for banned lookup-table names,
so this can't silently regress later.

## 5. How district similarity is calculated

Reuses the exact same `_score_candidate()` function used for settlement
alternatives — no second scoring system. Experience Match comes from a
real-data category-mix comparison: `_category_profile()` turns each
location's actual nearby OSM places (attraction/museum/historic/religious/
park/restaurant/etc.) into a normalized histogram, and `_profile_similarity()`
computes histogram intersection between the requested destination's profile
and the candidate district's profile (0–100). A heritage-heavy destination
therefore naturally favors districts whose own nearby places skew
historic/religious/museum, and a nature-heavy one favors districts skewing
park/attraction — derived from live data every time, never a hardcoded
"Manali → Jibhi"-style mapping.

## 6. How lower crowding is determined

Same filter as settlement alternatives, and it uses the **numeric**
pressure index whenever both sides have one (not just status-bucket
comparison) — this was a real, previously-fixed bug (`requested HIGH-74 vs
candidate HIGH-58` used to be wrongly rejected for sharing the "HIGH"
bucket). A candidate must beat the requested destination's index by at
least 5 points to count as genuine relief; falls back to status-rank
comparison only when a numeric index isn't available for one/both sides;
and a candidate with **no** pressure signal at all is never excluded on
that basis alone (marked "Crowding unavailable" in the UI, never assumed
low). `test_score_candidate_numeric_relief_applies_to_district_candidates_too`
proves this explicitly for district-sourced candidates (78 vs 51 = kept).

## 7. Rebalancing Score formula

Unchanged, reused for districts: a weighted sum of seven factors — experience
match (0.28), pressure relief (0.24), distance/accessibility (0.16), weather
suitability (0.10), sustainability (0.08), local opportunity (0.08), carrying
capacity (0.06) — each independently explainable via the returned `factors`
dict, clamped 0–100. This is deterministic weighted scoring, explicitly
labelled `"method": "deterministic-weighted-scoring"`, `"is_machine_learning":
false` in the API response — never presented as AI/ML.

## 8. Files changed

Backend:
- `backend/app/schemas/place.py` — added `District` model; added
  `district`/`state` to `GeocodeResult`.
- `backend/app/integrations/nominatim.py` — `addressdetails=1` on
  search/reverse; extract `district`/`state` from the address breakdown.
- `backend/app/integrations/overpass.py` — new `nearby_districts()` query
  (admin_level 5–7 range, centroid-only).
- `backend/app/services/places_service.py` — new `nearby_districts()`
  service wrapper (same cache/stale-fallback pattern as `nearby_settlements`).
- `backend/app/schemas/crowd.py` — added `confidence` to
  `CrowdPressureResponse`.
- `backend/app/services/crowd_service.py` — populate `confidence` from the
  already-computed `total_weight`.
- `backend/app/schemas/flow_rebalance.py` — added `district`/`source` to
  `DestinationSummary`; added `district_alternatives` /
  `district_alternatives_message` to `RebalanceResponse`.
- `backend/app/services/flow_rebalancer_service.py` — district constants,
  `_discover_district_candidates()`, `_rebalance_district_alternatives()`,
  restructured `rebalance()` to run settlement and district pipelines
  independently.
- `backend/tests/test_flow_rebalancer.py` — mocked the new
  `nearby_districts` call so existing tests stay hermetic/fast.
- `backend/tests/test_flow_rebalancer_districts.py` — **new**, 11 tests (see
  §12–13).

Frontend:
- `explore.html` — added `<div class="real-districts" data-r-districts>`
  container.
- `js/real-explore.js` — enhanced `renderCrowdPressure()` (Crowding Index
  title, data-type/confidence line, recommendation line, expandable "How is
  this calculated?" component breakdown); added `renderDistrictAlternatives()`,
  `districtCardHtml()`, `wireDistrictActions()`, `renderDistrictMarkers()`,
  `clearDistrictMarkers()`, `state.districtMarkers`; split the old
  `renderRebalancer()` into `renderSettlementAlternatives()` (unchanged
  behavior) + `renderDistrictAlternatives()` (new), both fed by one shared
  `/api/flow/rebalance` call.
- `css/styles.css` — added `.crowd-card__datatype`, `.crowd-card__recommendation`,
  `.crowd-card__toggle`, `.crowd-card__components`, `.crowd-card__component*`
  (district cards reuse the existing `.rebalance-card`/`.rebalance-alt`
  classes as-is — no new visual language was introduced).

`js/api.js` was **not** changed — `rebalanceDestination()` already passes
through the full parsed JSON body, so the new `district_alternatives`/
`district_alternatives_message` fields needed no client-side plumbing.

## 9. API changes

No new endpoints. `GET /api/crowd/pressure` now also returns `confidence`
(nullable float). `POST /api/flow/rebalance` now also returns
`district_alternatives: RebalanceAlternative[]` and
`district_alternatives_message: string | null` alongside the existing
`alternatives`/`message` — the exact same `RebalanceAlternative` shape,
distinguished only by `destination.source == "osm-district"` and
`destination.district`.

## 10. Frontend changes

Crowding Index card: title changed to "📊 Tourism Crowding Index"; new
data-type/confidence line ("Estimated data · 90% confidence"); a dynamic
recommendation line when pressure is MODERATE/HIGH/VERY HIGH pointing at the
districts section below; a collapsible "How is this calculated?" toggle
revealing every component (label, value/100, weight%, note) — collapsed by
default so the card stays compact. New "🗺️ Nearby Similar Districts" card
below "🧭 Nearby Alternatives", visually identical in structure (same
`.rebalance-card`/`.rebalance-alt` classes), each district card showing name
+ state, experience match %, pressure status ("Crowding unavailable" when
genuinely unknown — never assumed low), distance/drive-time, rebalancing
score, up to 4 real-data-derived reasons, and an `[Explore]` button.

## 11. Map changes

New `state.districtMarkers` array, kept separate from both the nearby-POI
markers and the settlement-alternative markers, cleared/redrawn
independently. District markers reuse the existing green alternative icon
(same visual family as settlement alternatives, distinct from 🔴 destination
and default POI pins) and are folded into `updateMapView()`'s unified
viewport. Clicking a district marker's popup shows name, experience match,
pressure, distance/time, and its own `[Explore this]` button. Administrative
boundary **polygons are deliberately not rendered** — see Limitations §16.

## 12. Test destinations

Automated (mocked) coverage — see §13 — uses fictional names never present
in `curated_destinations.py` or `crowd.py`'s seasonal lookup, specifically to
prove there's no hidden per-destination branch: **Zenith Point, Wander
Falls, Bramble Vale** (backend, parametrized), plus **Zenithburg** (frontend
Playwright run) and **Testchester** (the prior phase's existing map-fix
verification, still passing). Real, network-dependent end-to-end testing
against Amritsar, Manali, Jaipur, Delhi, Goa, Rishikesh, Munnar, Darjeeling,
Leh etc. was **not** possible from this sandbox — outbound calls to
Nominatim/Overpass/OSRM are blocked here, same limitation already disclosed
in the prior map/places bugfix report. Every code path that would run for
those real destinations is exercised by the mocked tests instead.

## 13. Test results

`cd backend && pytest tests/ -q` → **65 passed** (54 pre-existing + 11 new in
`test_flow_rebalancer_districts.py`), ~22s, zero regressions. New tests
cover: adaptive radius widening/skipping for district discovery, current-
district exclusion, min/max distance-plausibility filtering, the
staged-pipeline candidate cap, numeric-pressure-relief reuse for
district-sourced candidates, honest empty-district messaging (with the
Crowding Index still appearing), the destination-agnostic end-to-end proof
(3 fictional destinations, settlement pipeline forced empty to prove
independence), and the explicit static "no hardcoded destination→district
mapping" source-inspection test.

Frontend: a mocked-backend Playwright run against `explore.html` (Chromium,
all backend/tile/Leaflet requests intercepted, zero real network) confirmed:
Crowding Index renders with score/status/confidence/factors; the "How is
this calculated?" toggle opens and shows all 5 components; the Nearby
Similar Districts card renders independently alongside (not instead of) the
Nearby Alternatives card, both populated from one shared API call; 4 map
markers appear (destination + nearby POI + settlement-alt + district-alt);
clicking a district's `[Explore]` button updates the search box to the
district's own name and fires a fresh round of places/weather/crowd/rebalance
requests (5→10 requests observed) — proving selection goes through the
normal `setLocation()` pipeline rather than a silent swap. No console/page
errors from Sarthi's own code (only expected sandbox-network failures for
Google Fonts/OSM tiles, unrelated to this feature).

## 14. Which data is real

Tourism place density (live OpenStreetMap/Overpass), district discovery
(live OpenStreetMap `boundary=administrative` via Overpass), weather (live
Open-Meteo), district/state resolution (live Nominatim address breakdown),
distance/drive-time on the final shortlist (live OSRM), events when
configured (live Ticketmaster), Sarthi's own usage counts (real local DB).

## 15. Which data is estimated

The Crowding Index itself is explicitly and only ever "estimated" —
Sārthi has no live CCTV/mobile-location feed, and the UI now says so plainly
("Estimated Tourism Crowding Index... Not a live visitor count, CCTV feed,
mobile-location panel or government statistic"). Local opportunity,
carrying capacity, and sustainability (when no curated figure exists) are
modelled proxies from real place-density data, each labelled `estimated` in
`factors`/`data_type`, never presented as measured.

## 16. Remaining limitations

- **No live end-to-end run against real Indian destinations** — this
  sandbox blocks outbound calls to Nominatim/Overpass/OSRM/Open-Meteo, so
  verification relied on mocked/parametrized tests + one full mocked
  Playwright run rather than hitting the actual named destinations you
  listed. I'd recommend a quick manual smoke test (Amritsar, Manali, a
  Northeast/coastal destination) once you have this running with real
  network access.
- **District boundary polygons are not rendered on the map** — only
  centroid markers. This was a deliberate choice: your spec explicitly
  sanctions a centroid fallback and explicitly bans loading "enormous
  administrative geometries unnecessarily," and Overpass's `out center tags`
  query (centroid + tags only) is what keeps district discovery cheap. Full
  polygon rendering could be added later as a genuinely optional enhancement
  if you want it, at the cost of a heavier per-candidate Overpass query.
- **District-level Nominatim/OSM tagging is not perfectly uniform across
  India** — the code queries a *range* of admin_levels (5–7) and a
  priority-ordered list of address keys specifically to absorb this, but a
  handful of areas with unusual or missing tagging may still produce sparse
  or no district results; in that case the page honestly says "Lower-crowding
  district alternatives could not be confirmed from the available data"
  rather than guessing, and the rest of the page (Crowding Index, nearby
  places, settlement alternatives) continues to work normally.
- **`js/api.js` untouched** was a deliberate no-op, not an oversight — the
  existing generic pass-through already covers the new fields.
