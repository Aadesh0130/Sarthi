/* =========================================================
   Sarthi — Real Explore engine.
   Genuine destination search (Nominatim) + live map (Leaflet/
   OpenStreetMap) + real nearby places (Overpass) + real
   weather (Open-Meteo). Everything here is either fetched
   live from the backend or explicitly marked unavailable —
   nothing is invented (spec sections 3–11, 40).
   ========================================================= */
(function () {
  "use strict";
  // Only SarthiAPI is hard-required. Leaflet (window.L) is loaded from a
  // third-party CDN (unpkg.com) -- a slow network, corporate firewall, ad
  // blocker or CDN outage can make it fail to load even though everything
  // else on the page works fine. Search, weather, the Crowding Index, the
  // Tourist Flow Rebalancer and District Discovery are all independent of
  // the map and must keep working with an honest "map unavailable" note
  // rather than the whole real-data layer silently going dead (spec:
  // "every provider failure must degrade gracefully without collapsing the
  // whole site" / "no avoidable... failed imports").
  if (!window.SarthiAPI) return;
  var API = window.SarthiAPI;

  var els = {};
  var state = {
    lat: null, lon: null, label: "",
    allPlaces: [], activeCategories: [], selectedPlaceId: null,
    map: null, markers: {}, weather: null, crowdCircle: null,
    // The requested destination itself -- distinct from `markers` (nearby
    // places) and `rebalanceMarkers` (alternatives), so it's never confused
    // with either. Cleared/replaced by renderDestinationMarker().
    destinationMarker: null,
    // Separate from `markers` (the nearby-places pins) so category-chip re-renders --
    // which call clearMarkers()/renderMarkers() -- never wipe the rebalancer's own
    // alternative-destination pins. Cleared explicitly by clearRebalanceMarkers().
    rebalanceMarkers: [],
    // "Nearby Similar Districts" markers -- a distinct array from
    // rebalanceMarkers (settlement/curated alternatives) so the two lists can
    // each be cleared/re-rendered independently (spec: "district markers
    // remain separate from POI markers" -- and, just as importantly here,
    // separate from the settlement-alternative markers too, since they come
    // from a genuinely different discovery pipeline).
    districtMarkers: [],
    effectiveRadiusMeters: null, requestedRadiusMeters: null,
  };

  var CATEGORY_ORDER = ["attraction", "museum", "historic", "religious", "park", "restaurant", "cafe", "shopping", "hotel"];

  function $(sel) { return document.querySelector(sel); }

  function cacheEls() {
    els.search = $("#r-search");
    els.suggest = $("[data-r-suggest]");
    els.geolocate = $("[data-r-geolocate]");
    els.categories = $("[data-r-categories]");
    els.status = $("[data-r-status]");
    els.layout = $("[data-r-layout]");
    els.empty = $("[data-r-empty]");
    els.weather = $("[data-r-weather]");
    els.crowd = $("[data-r-crowd]");
    els.rebalance = $("[data-r-rebalance]");
    els.districts = $("[data-r-districts]");
    els.events = $("[data-r-events]");
    els.count = $("[data-r-count]");
    els.cards = $("[data-r-cards]");
    els.mapDiv = $("#r-map");
    els.panel = $("[data-place-panel]");
    els.panelBody = $("[data-place-body]");
    els.panelClose = $("[data-place-close]");
    els.panelOverlay = $("[data-place-overlay]");
  }

  function setStatus(msg, kind) {
    if (!msg) { els.status.hidden = true; return; }
    els.status.hidden = false;
    els.status.className = "real-status" + (kind ? " real-status--" + kind : "");
    els.status.textContent = msg;
  }

  /* ---------- Map ---------- */
  function initMap() {
    // minZoom bounds how far updateMapView()'s fitBounds() is ever allowed to
    // zoom OUT (a destination plus a handful of very spread-out alternatives
    // should never zoom out past a sensible country-region scale); maxZoom
    // per-call in fitBounds()/setView() below bounds zooming IN too far.
    state.map = L.map(els.mapDiv, { scrollWheelZoom: true, minZoom: 4 }).setView([22.9734, 78.6569], 5);

    var osmAttribution = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
    var primary = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: osmAttribution,
      maxZoom: 19,
    }).addTo(state.map);

    // Some ISPs/networks block the official OSM tile subdomains outright (a real, documented
    // issue in parts of India and elsewhere) -- that shows up as a totally blank grey map with
    // no visible error anywhere. Detect it two ways (explicit tile errors, or simply zero tiles
    // ever loading) and fail over to a different free, no-key tile source rather than staying
    // silently blank.
    var tilesLoaded = 0, tileErrors = 0, switchedTiles = false;
    function useFallbackTiles(reason) {
      if (switchedTiles) return;
      switchedTiles = true;
      state.map.removeLayer(primary);
      L.tileLayer("https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png", {
        attribution: osmAttribution + ' &copy; <a href="https://carto.com/attributions">CARTO</a>',
        maxZoom: 20,
        subdomains: "abcd",
      }).addTo(state.map);
      setStatus("Switched to a backup map source (" + reason + ").", "warn");
    }
    primary.on("tileload", function () { tilesLoaded++; });
    primary.on("tileerror", function () {
      tileErrors++;
      if (tileErrors >= 4) useFallbackTiles("the primary OpenStreetMap tile server didn't respond");
    });
    setTimeout(function () {
      if (tilesLoaded === 0) useFallbackTiles("map tiles were blocked or too slow on your network");
    }, 7000);
  }

  function categoryIcon(cat) {
    return (API.CATEGORY_META[cat] || API.CATEGORY_META.other).icon;
  }

  function clearMarkers() {
    if (!state.map) return;
    Object.keys(state.markers).forEach(function (id) { state.map.removeLayer(state.markers[id]); });
    state.markers = {};
  }

  function renderMarkers(places) {
    clearMarkers();
    if (!state.map) return; // Leaflet unavailable -- cards below still show every real place
    places.forEach(function (p) {
      var marker = L.marker([p.latitude, p.longitude], {
        title: p.name,
      }).addTo(state.map);
      marker.bindPopup(popupHtml(p));
      marker.on("click", function () { openPlace(p); });
      state.markers[p.id] = marker;
    });
    // View fitting happens once, centrally, in updateMapView() -- not here --
    // so a fitBounds() from nearby-place markers can never race against/get
    // clobbered by a later setView() from loadPlaces(), and so the view can
    // also account for the destination marker and any rebalancer
    // alternatives already on the map (see updateMapView()).
  }

  // 🔴 the requested destination itself -- always present once a location is
  // set, always visually distinct from a 📍 nearby place or a 🟢 alternative
  // (spec: "Do not confuse the requested destination with an alternative").
  var destinationRedIcon = window.L
    ? L.icon({
        iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png",
        shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
        iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41],
      })
    : null;

  function renderDestinationMarker() {
    if (!state.map) return;
    if (state.destinationMarker) { state.map.removeLayer(state.destinationMarker); state.destinationMarker = null; }
    if (state.lat == null) return;
    state.destinationMarker = L.marker([state.lat, state.lon], {
      icon: destinationRedIcon || undefined,
      title: state.label || "Selected destination",
      zIndexOffset: 1000, // above both nearby-place (default) and alternative (500) markers
    }).addTo(state.map);
    state.destinationMarker.bindPopup(
      "<b>🔴 " + escapeHtml(state.label || "Selected destination") + "</b><br>" +
        '<span style="color:#8b8880;font-size:.82rem">Your searched destination</span>'
    );
  }

  // Single source of truth for the map's viewport, called after the
  // destination, nearby places, and/or rebalancer alternatives change (spec:
  // "choose a sensible unified viewport... fit bounds around
  // destination+places(+alternatives)... if only one nearby place exists,
  // keep centered on destination rather than zooming aggressively to that
  // single marker"). This replaces the old renderMarkers()-fitBounds() vs
  // loadPlaces()-setView() conflict, which made the map visibly "jump"
  // because the second call always overrode the first.
  function updateMapView() {
    if (!state.map || state.lat == null) return;
    var points = [[state.lat, state.lon]];
    Object.keys(state.markers).forEach(function (id) { points.push(state.markers[id].getLatLng()); });
    state.rebalanceMarkers.forEach(function (m) { points.push(m.getLatLng()); });
    state.districtMarkers.forEach(function (m) { points.push(m.getLatLng()); });

    if (points.length <= 2) {
      // Just the destination, or the destination plus a single nearby place --
      // a tight fitBounds() around two points (or one) zooms in far more
      // aggressively than is useful. A plain, centered destination view at a
      // sensible fixed zoom reads much better.
      state.map.setView([state.lat, state.lon], 13);
      return;
    }
    state.map.fitBounds(points, { padding: [40, 40], maxZoom: 15 });
  }

  function popupHtml(p) {
    return '<b>' + categoryIcon(p.category) + " " + escapeHtml(p.name) + "</b><br>" +
      '<span style="color:#8b8880;font-size:.82rem">' + (API.CATEGORY_META[p.category] || API.CATEGORY_META.other).label + "</span>";
  }

  /* ---------- Search / geocode ---------- */
  var doGeocode = API.debounce(function (q) {
    if (!q || q.trim().length < 2) { els.suggest.hidden = true; return; }
    API.geocodeSearch(q, 6).then(function (res) {
      if (!res.ok) { els.suggest.hidden = true; return; } // live-typing suggestions fail quietly; Enter/submit below always shows a real error
      renderSuggestions(res.data);
    });
  }, 450);

  // Explicit search (Enter key, or no suggestion was ever clicked). Always fetches fresh and
  // always tells the user what happened -- unlike the quiet live-suggestion path above, this one
  // must never fail silently, since it's the only way to search if suggestions never rendered.
  function submitSearch() {
    var q = (els.search.value || "").trim();
    if (!q) return;
    els.suggest.hidden = true;
    setStatus("Searching for “" + q + "”…", "info");
    API.geocodeSearch(q, 1).then(function (res) {
      if (!res.ok) {
        setStatus("Destination search is temporarily unavailable (" + res.error + "). Try again in a moment.", "error");
        return;
      }
      if (!res.data.length) {
        setStatus("Couldn’t find “" + q + "”. Try a different spelling or a nearby larger town.", "warn");
        return;
      }
      var top = res.data[0];
      els.search.value = top.display_name;
      setLocation(top.latitude, top.longitude, top.display_name);
    });
  }

  function renderSuggestions(results) {
    if (!results.length) { els.suggest.hidden = true; return; }
    els.suggest.innerHTML = results
      .map(function (r, i) {
        return '<button type="button" class="r-suggest__item" data-idx="' + i + '">📍 ' + escapeHtml(r.display_name) + "</button>";
      })
      .join("");
    els.suggest.hidden = false;
    els.suggest.querySelectorAll("[data-idx]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var r = results[+btn.getAttribute("data-idx")];
        els.search.value = r.display_name;
        els.suggest.hidden = true;
        setLocation(r.latitude, r.longitude, r.display_name);
      });
    });
  }

  function setLocation(lat, lon, label) {
    state.lat = lat; state.lon = lon; state.label = label || "";
    loadPlaces();
  }

  /* ---------- Places + weather ---------- */
  // Perf note (2026-09-16): this used to gate weather, tourism-pressure and
  // events behind `Promise.all([placesPromise, weatherPromise])`, then only
  // fired the pressure/events fetches (each with their own real network
  // round trip) AFTER that had already resolved -- so every page felt as
  // slow as the single slowest step (nearby-places, which hedges across
  // multiple public Overpass mirrors and can genuinely take a while,
  // especially for a small/sparse locality that also triggers the radius
  // escalation in backend/app/services/places_service.py). None of weather,
  // pressure or events actually depend on the places result, so there was no
  // real reason to serialize them. Now every independent fetch starts
  // immediately and renders itself the moment it resolves -- the map and
  // destination pin appear right away too, instead of waiting on Overpass.
  // This does not (and honestly cannot) make the free public Overpass
  // service itself faster -- see the honest "still searching" status below
  // for genuinely slow/sparse cases.
  function loadPlaces() {
    if (state.lat == null) return;
    setStatus("Finding real places near “" + (state.label || "your destination") + "”…", "info");
    els.empty.hidden = true;

    // Map + destination pin depend only on lat/lon, never on the places
    // list -- show them immediately rather than leaving the whole layout
    // hidden while Overpass is still working.
    els.layout.hidden = false;
    if (state.map) {
      state.map.invalidateSize();
      state.map.setView([state.lat, state.lon], 13);
    }
    renderDestinationMarker();

    // These each hit their own backend endpoint and don't need the places
    // list either -- start them in parallel, not after places finishes.
    API.weather(state.lat, state.lon).then(function (weatherRes) {
      state.weather = weatherRes.ok ? weatherRes.data : null;
      renderWeather();
    });
    renderCrowdPressure();
    renderEvents();

    // A free, shared, rate-limited public service can genuinely take a while
    // -- the backend itself can retry up to 3 progressively wider radius
    // tiers (see js/api.js placesNearby's own comment on why its timeout is
    // now 95s, not 35s), each a real live fetch. Say so honestly in stages
    // instead of leaving the original "Finding real places..." message
    // sitting there for up to a minute-plus looking frozen.
    var stillSearchingTimers = [
      setTimeout(function () {
        setStatus(
          "Still searching “" + (state.label || "your destination") + "”… free live map data (OpenStreetMap) can take longer for smaller or less-mapped areas.",
          "info"
        );
      }, 6000),
      setTimeout(function () {
        setStatus(
          "Still working on “" + (state.label || "your destination") + "”… the free OpenStreetMap service is responding slowly right now. Real results should still arrive shortly.",
          "info"
        );
      }, 25000),
    ];
    function clearSearchTimers() { stillSearchingTimers.forEach(clearTimeout); }

    API.placesNearby(state.lat, state.lon, 4000, []).then(function (placesRes) {
      clearSearchTimers();

      if (!placesRes.ok) {
        setStatus("Live place data is temporarily unavailable (" + placesRes.error + "). Try again in a moment.", "error");
        return;
      }
      state.allPlaces = placesRes.data;
      state.requestedRadiusMeters = placesRes.requestedRadiusMeters;
      state.effectiveRadiusMeters = placesRes.effectiveRadiusMeters;

      if (!state.allPlaces.length) {
        setStatus(radiusAwareEmptyMessage(), "warn");
        applyFilterAndRender();
        return;
      }

      // Live Overpass fetch failed for this request, but a previously-fetched
      // result for this spot was still recent enough to show (see
      // backend/app/core/config.py cache_stale_grace_places) -- say so
      // honestly rather than presenting it as freshly live, and rather than
      // showing a needless hard error when real (if slightly older) data is
      // actually available.
      if (placesRes.staleSeconds != null) {
        setStatus(
          "Live OpenStreetMap data couldn't be refreshed just now, so these are real results from a previous fetch, " +
            formatCacheAge(placesRes.staleSeconds) + " ago. Reload to try live data again.",
          "warn"
        );
      } else {
        setStatus("");
      }

      applyFilterAndRender(); // renders cards + nearby-place markers, then calls updateMapView()
    });
  }

  // "Showing 1 real place near X" was misleading whenever the backend had to
  // widen past the originally-requested radius to find anything at all --
  // this says the actual radius searched instead of silently implying the
  // original (spec: "Radius Strategy" -- "must clearly indicate the ACTUAL
  // radius used... never claim 4km if 8km was used").
  function radiusAwareEmptyMessage() {
    var effective = state.effectiveRadiusMeters, requested = state.requestedRadiusMeters;
    var radiusNote = effective != null && effective !== requested
      ? "within " + (effective / 1000) + " km (widened from the usual " + (requested / 1000) + " km since the area is sparse)"
      : "within " + ((effective || requested || 4000) / 1000) + " km";
    return "No mapped tourist places found from OpenStreetMap " + radiusNote + " of “" + state.label + "”. Try a nearby town or a broader search.";
  }

  /* ---------- Tourism Pressure (estimated -- see backend/app/services/crowd_service.py) ---------- */
  var CROWD_STATUS_META = {
    LOW: { color: "#22a35b", ring: "#22a35b" },
    MODERATE: { color: "#c98a12", ring: "#e0a613" },
    HIGH: { color: "#e0691e", ring: "#e0691e" },
    "VERY HIGH": { color: "#d63b3b", ring: "#d63b3b" },
  };

  function renderCrowdPressure() {
    if (!els.crowd) return;
    els.crowd.innerHTML = '<div class="crowd-card"><p class="muted">Checking tourism pressure…</p></div>';
    if (state.crowdCircle) { state.map.removeLayer(state.crowdCircle); state.crowdCircle = null; }
    clearRebalancer();

    API.crowdPressure(state.label, state.lat, state.lon).then(function (res) {
      if (!res.ok || res.data.pressure_index == null) {
        var reason = res.ok ? (res.data.message || "No reliable estimate available.") : res.error;
        els.crowd.innerHTML =
          '<div class="crowd-card crowd-card--unavailable">' +
          '<span class="crowd-card__title">📊 Tourism Crowding Index</span>' +
          '<p class="muted">Tourism pressure unavailable — ' + escapeHtml(reason) + "</p>" +
          "</div>";
        return; // pressure unavailable -- rebalancer already cleared above, don't guess
      }
      var d = res.data;
      var meta = CROWD_STATUS_META[d.status] || CROWD_STATUS_META.MODERATE;
      var bullets = (d.explanation || []).slice(0, 4).map(function (e) { return "<li>" + escapeHtml(e) + "</li>"; }).join("");

      // data_type/confidence come straight from crowd_service.py (never
      // invented here) -- "Estimated" is the honest default since Sarthi has
      // no live CCTV/mobile-location feed; "confidence" is how much of the
      // composite's intended weight actually had a real signal behind it
      // this call (e.g. lower when weather or events were unreachable).
      var dataTypeLabel = d.data_type === "curated" ? "Curated" : d.data_type === "live" ? "Live" : "Estimated";
      var confidencePct = d.confidence != null ? Math.round(d.confidence * 100) : null;

      var recommendation = "";
      if (d.status === "HIGH" || d.status === "VERY HIGH") {
        recommendation = "Tourism pressure here is elevated — see Nearby Similar Districts below for places with a similar experience and lower estimated pressure.";
      } else if (d.status === "MODERATE") {
        recommendation = "Tourism pressure is moderate — a normal visit, with a few lower-pressure alternatives shown below if you're curious.";
      }

      var componentRows = Object.keys(d.components || {})
        .map(function (key) {
          var c = d.components[key];
          var valueText = c.value != null ? Math.round(c.value) + "/100" : "unavailable";
          return (
            '<div class="crowd-card__component' + (c.used ? "" : " crowd-card__component--unused") + '">' +
            '<div class="crowd-card__component-head"><b>' + escapeHtml(c.label) + "</b><span>" + valueText + " · weight " + Math.round(c.weight * 100) + "%</span></div>" +
            (c.note ? '<p class="muted">' + escapeHtml(c.note) + "</p>" : "") +
            "</div>"
          );
        })
        .join("");

      els.crowd.innerHTML =
        '<div class="crowd-card">' +
        '<div class="crowd-card__head">' +
        '<span class="crowd-card__title">📊 Tourism Crowding Index</span>' +
        '<span class="crowd-card__badge" style="background:' + meta.color + '">' + d.pressure_index + '/100 · ' + d.status + '</span>' +
        "</div>" +
        '<div class="crowd-card__datatype">' + dataTypeLabel + " data" + (confidencePct != null ? " · " + confidencePct + "% confidence" : "") + "</div>" +
        (bullets ? '<ul class="crowd-card__why">' + bullets + "</ul>" : "") +
        (d.weather_suitability ? '<div class="crowd-card__suit">Visit suitability: <b>' + escapeHtml(d.weather_suitability) + "</b> (reported separately from pressure)</div>" : "") +
        (recommendation ? '<div class="crowd-card__recommendation">💡 ' + escapeHtml(recommendation) + "</div>" : "") +
        (componentRows
          ? '<button type="button" class="crowd-card__toggle" data-crowd-toggle>How is this calculated? ▾</button>' +
            '<div class="crowd-card__components" data-crowd-components hidden>' + componentRows + "</div>"
          : "") +
        '<p class="crowd-card__disclaimer">Estimated Tourism Crowding Index — a planning signal built from real OpenStreetMap place density, seasonality, Sarthi\'s own usage, live weather and (when configured) live events. Not a live visitor count, CCTV feed, mobile-location panel or government statistic.</p>' +
        "</div>";

      var crowdToggle = els.crowd.querySelector("[data-crowd-toggle]");
      var crowdComponents = els.crowd.querySelector("[data-crowd-components]");
      if (crowdToggle && crowdComponents) {
        crowdToggle.addEventListener("click", function () {
          crowdComponents.hidden = !crowdComponents.hidden;
          crowdToggle.textContent = "How is this calculated? " + (crowdComponents.hidden ? "▾" : "▴");
        });
      }

      // Phase 15 (optional): a soft visual indicator on the map, clearly labelled
      // as an estimate, never implying live human-density tracking. Skipped
      // outright when the map itself isn't available -- the card above already
      // carries the same information in text.
      if (state.map) {
        state.crowdCircle = L.circle([state.lat, state.lon], {
          radius: 1500, color: meta.ring, weight: 2, fillColor: meta.ring, fillOpacity: 0.08,
        }).addTo(state.map);
        state.crowdCircle.bindPopup("Estimated Tourism Pressure: " + d.status + " (" + d.pressure_index + "/100)");
      }

      // Tourist Flow Rebalancer: only worth asking the backend when pressure is
      // at least MODERATE -- a LOW/unavailable destination is a normal experience
      // and this avoids a pointless extra request (backend would just report
      // pressure_check_only itself, but skipping it here saves a round trip).
      if (d.status && d.status !== "LOW") {
        renderRebalancer();
      } else {
        clearRebalancer();
      }
    });
  }

  /* ---------- Tourist Flow Rebalancer ----------
     Sarthi doesn't just recommend places WITHIN a destination (the cards/map
     above) -- when the searched destination itself is under real tourism
     pressure, this surfaces genuine nearby alternatives scored on real data
     (same Tourism Pressure Index above, real OSM place-mix, real distance).
     The requested destination is NEVER silently replaced: alternatives are
     only ever adopted when the traveller explicitly clicks "Explore" on one. */
  function clearRebalanceMarkers() {
    state.rebalanceMarkers.forEach(function (m) { state.map.removeLayer(m); });
    state.rebalanceMarkers = [];
    updateMapView(); // alternatives just left the map -- viewport may need to shrink back
  }

  function clearDistrictMarkers() {
    state.districtMarkers.forEach(function (m) { state.map.removeLayer(m); });
    state.districtMarkers = [];
    updateMapView();
  }

  function clearRebalancer() {
    if (els.rebalance) els.rebalance.innerHTML = "";
    if (els.districts) els.districts.innerHTML = "";
    clearRebalanceMarkers();
    clearDistrictMarkers();
  }

  var altGreenIcon = window.L
    ? L.icon({
        iconUrl: "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png",
        shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png",
        iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41],
      })
    : null;

  function alternativeCardHtml(alt, idx) {
    var p = alt.tourism_pressure || {};
    var pMeta = CROWD_STATUS_META[p.status] || CROWD_STATUS_META.MODERATE;
    var dist = alt.distance_km != null ? alt.distance_km + " km" : "";
    var time = alt.travel_time_minutes != null ? " · ~" + alt.travel_time_minutes + " min drive" : "";
    var reasons = (alt.reasons || []).slice(0, 4).map(function (r) { return "<li>" + escapeHtml(r) + "</li>"; }).join("");
    return (
      '<div class="rebalance-alt" data-alt-idx="' + idx + '">' +
      '<div class="rebalance-alt__head">' +
      '<span class="rebalance-alt__name">📍 ' + escapeHtml(alt.destination.name) +
      (alt.is_hidden_gem ? '<span class="rebalance-alt__gem">💎 Hidden gem</span>' : "") +
      "</span>" +
      '<span class="rebalance-alt__match">' + alt.experience_match + "% experience match</span>" +
      "</div>" +
      '<div class="rebalance-alt__meta">' +
      '<span style="color:' + pMeta.color + '">● ' + escapeHtml(p.status || "n/a") + " tourism pressure</span>" +
      (dist ? "<span>📏 " + dist + time + "</span>" : "") +
      "<span>⚖️ Rebalancing score " + alt.rebalancing_score + "/100</span>" +
      "</div>" +
      '<div class="rebalance-alt__signals">' +
      '<span class="rebalance-alt__signal">🏪 ' + escapeHtml(alt.local_opportunity.label) + "</span>" +
      '<span class="rebalance-alt__signal">🌱 Sustainability ' + Math.round(alt.sustainability_score) + "/100 (" + alt.sustainability_data_type + ")</span>" +
      '<span class="rebalance-alt__signal">🧭 Carrying capacity: ' + escapeHtml(alt.carrying_capacity.label) + "</span>" +
      "</div>" +
      (reasons ? '<ul class="rebalance-alt__reasons">' + reasons + "</ul>" : "") +
      '<button type="button" class="btn btn--primary btn--sm rebalance-alt__cta" data-explore-alt="' + idx + '">🧭 Explore ' + escapeHtml(alt.destination.name.split(",")[0]) + "</button>" +
      "</div>"
    );
  }

  function wireAlternativeActions(data) {
    if (!els.rebalance) return;
    els.rebalance.querySelectorAll("[data-explore-alt]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var alt = data.alternatives[+btn.getAttribute("data-explore-alt")];
        if (!alt) return;
        // Explicit traveller choice only -- setLocation() is the exact same
        // mechanism used for a normal search, so everything downstream
        // (map, weather, places, pressure, "Add to trip") behaves identically
        // for the alternative as it would for any other searched destination.
        els.search.value = alt.destination.name;
        setLocation(alt.destination.latitude, alt.destination.longitude, alt.destination.name);
        if (window.Sarthi && window.Sarthi.toast) window.Sarthi.toast("Now exploring " + alt.destination.name.split(",")[0], "🧭");
      });
    });
  }

  function renderRebalanceMarkers(data) {
    clearRebalanceMarkers();
    if (!state.map || !altGreenIcon) return; // cards above already list every alternative
    (data.alternatives || []).forEach(function (alt, idx) {
      var marker = L.marker([alt.destination.latitude, alt.destination.longitude], {
        icon: altGreenIcon, title: alt.destination.name, zIndexOffset: 500,
      }).addTo(state.map);
      var popupBtn = '<div>' +
        "<b>" + escapeHtml(alt.destination.name) + "</b><br>" +
        alt.experience_match + "% experience match · " + escapeHtml((alt.tourism_pressure || {}).status || "n/a") + " pressure<br>" +
        '<button type="button" class="btn btn--primary btn--sm" data-popup-explore-alt="' + idx + '" style="margin-top:6px">🧭 Explore this</button>' +
        "</div>";
      marker.bindPopup(popupBtn);
      marker.on("popupopen", function () {
        var b = document.querySelector('[data-popup-explore-alt="' + idx + '"]');
        if (b) {
          b.addEventListener("click", function () {
            els.search.value = alt.destination.name;
            setLocation(alt.destination.latitude, alt.destination.longitude, alt.destination.name);
          });
        }
      });
      state.rebalanceMarkers.push(marker);
    });
    updateMapView(); // include the new alternative markers in the unified viewport
  }

  function renderSettlementAlternatives(data) {
    if (!els.rebalance) return;
    if (data.pressure_check_only || !data.alternatives || !data.alternatives.length) {
      // Pressure wasn't actually elevated enough to search (or none survived
      // filtering) -- say so plainly rather than showing an empty card.
      els.rebalance.innerHTML =
        '<div class="rebalance-card rebalance-card--empty"><span class="rebalance-card__title">🧭 Nearby Alternatives</span>' +
        '<p class="muted">' + escapeHtml(data.message || "No lower-pressure alternatives to surface right now.") + "</p></div>";
      clearRebalanceMarkers();
      return;
    }

    var cards = data.alternatives.map(alternativeCardHtml).join("");
    els.rebalance.innerHTML =
      '<div class="rebalance-card' + (data.rebalancing_triggered ? " rebalance-card--triggered" : "") + '">' +
      '<span class="rebalance-card__title">🧭 Nearby Alternatives</span>' +
      '<p class="rebalance-card__intro">' + escapeHtml(data.message || "") + "</p>" +
      '<div class="rebalance-alt-list">' + cards + "</div>" +
      '<p class="crowd-card__disclaimer">Deterministic weighted scoring over real data (not AI/ML) — your searched destination stays selected unless you explicitly choose one of these.</p>' +
      "</div>";
    wireAlternativeActions(data);
    renderRebalanceMarkers(data);
  }

  /* ---------- "Nearby Similar Districts" (spec Part 2) ----------
     Distinct from the settlement/curated alternatives above: these are
     coarser, dynamically-discovered OSM administrative districts (see
     backend/app/services/flow_rebalancer_service.py's
     _discover_district_candidates). Reuses the exact same
     /api/flow/rebalance response already fetched for settlement
     alternatives -- never a second network round trip -- and the exact same
     card/marker visual language as the settlement alternatives above, so
     this reads as an extension of the existing design system rather than a
     new one. Never gated by, and never gates, the settlement alternatives:
     an empty settlement list must not hide a genuinely-found district list,
     or vice versa (spec: "Crowding Index (and either alternatives list)
     should always be separate"). */
  function districtCardHtml(alt, idx) {
    var p = alt.tourism_pressure || {};
    var pMeta = CROWD_STATUS_META[p.status] || CROWD_STATUS_META.MODERATE;
    var pressureText = p.pressure_index != null
      ? escapeHtml(p.status || "n/a") + " (" + p.pressure_index + "/100)"
      : "Crowding unavailable"; // never assumed to be "low" just because it's unknown (spec)
    var dist = alt.distance_km != null ? alt.distance_km + " km" : "";
    var time = alt.travel_time_minutes != null ? " · ~" + alt.travel_time_minutes + " min drive" : (dist ? " · drive time unavailable" : "");
    var reasons = (alt.reasons || []).slice(0, 4).map(function (r) { return "<li>" + escapeHtml(r) + "</li>"; }).join("");
    var districtLabel = alt.destination.district || alt.destination.name;
    return (
      '<div class="rebalance-alt" data-district-idx="' + idx + '">' +
      '<div class="rebalance-alt__head">' +
      '<span class="rebalance-alt__name">🗺️ ' + escapeHtml(districtLabel) +
      (alt.destination.state ? '<span class="muted" style="font-weight:400"> · ' + escapeHtml(alt.destination.state) + "</span>" : "") +
      "</span>" +
      '<span class="rebalance-alt__match">' + alt.experience_match + "% experience match</span>" +
      "</div>" +
      '<div class="rebalance-alt__meta">' +
      '<span style="color:' + pMeta.color + '">● ' + pressureText + " estimated pressure</span>" +
      (dist ? "<span>📏 " + dist + time + "</span>" : "") +
      "<span>⚖️ Rebalancing score " + alt.rebalancing_score + "/100</span>" +
      "</div>" +
      (reasons ? '<ul class="rebalance-alt__reasons">' + reasons + "</ul>" : "") +
      '<button type="button" class="btn btn--primary btn--sm rebalance-alt__cta" data-explore-district="' + idx + '">🧭 Explore ' + escapeHtml(districtLabel) + "</button>" +
      "</div>"
    );
  }

  function wireDistrictActions(data) {
    if (!els.districts) return;
    els.districts.querySelectorAll("[data-explore-district]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var alt = data.district_alternatives[+btn.getAttribute("data-explore-district")];
        if (!alt) return;
        // Explicit traveller choice only, exactly like a settlement
        // alternative -- setLocation() is the same mechanism a normal search
        // uses, so the destination, coordinates, district, crowding index,
        // nearby places, weather and map all update through the existing
        // planner/explore pipeline (spec: "must NOT silently replace the
        // destination without explicit user interaction").
        els.search.value = alt.destination.name;
        setLocation(alt.destination.latitude, alt.destination.longitude, alt.destination.name);
        if (window.Sarthi && window.Sarthi.toast) window.Sarthi.toast("Now exploring " + (alt.destination.district || alt.destination.name.split(",")[0]), "🗺️");
      });
    });
  }

  function renderDistrictMarkers(data) {
    clearDistrictMarkers();
    if (!state.map || !altGreenIcon) return; // cards above already list every district
    (data.district_alternatives || []).forEach(function (alt, idx) {
      var marker = L.marker([alt.destination.latitude, alt.destination.longitude], {
        icon: altGreenIcon, title: alt.destination.district || alt.destination.name, zIndexOffset: 500,
      }).addTo(state.map);
      var p = alt.tourism_pressure || {};
      var pressureText = p.pressure_index != null ? escapeHtml(p.status || "n/a") + " (" + p.pressure_index + "/100)" : "crowding unavailable";
      var popupBtn = '<div>' +
        "<b>🗺️ " + escapeHtml(alt.destination.district || alt.destination.name) + "</b><br>" +
        alt.experience_match + "% experience match · " + pressureText + "<br>" +
        (alt.distance_km != null ? alt.distance_km + " km" + (alt.travel_time_minutes != null ? " · ~" + alt.travel_time_minutes + " min drive" : "") + "<br>" : "") +
        '<button type="button" class="btn btn--primary btn--sm" data-popup-explore-district="' + idx + '" style="margin-top:6px">🧭 Explore this</button>' +
        "</div>";
      marker.bindPopup(popupBtn);
      marker.on("popupopen", function () {
        var b = document.querySelector('[data-popup-explore-district="' + idx + '"]');
        if (b) {
          b.addEventListener("click", function () {
            els.search.value = alt.destination.name;
            setLocation(alt.destination.latitude, alt.destination.longitude, alt.destination.name);
          });
        }
      });
      state.districtMarkers.push(marker);
    });
    updateMapView(); // include the new district markers in the unified viewport
  }

  function renderDistrictAlternatives(data) {
    if (!els.districts) return;
    if (!data.district_alternatives || !data.district_alternatives.length) {
      // Distinguishes "confirmed none" from "could not be confirmed" via
      // whatever honest message the backend already produced -- never
      // fabricated here, and the rest of the page (Crowding Index, nearby
      // places, settlement alternatives) continues to work normally.
      els.districts.innerHTML =
        '<div class="rebalance-card rebalance-card--empty"><span class="rebalance-card__title">🗺️ Nearby Similar Districts</span>' +
        '<p class="muted">' + escapeHtml(data.district_alternatives_message || "Lower-crowding district alternatives could not be confirmed from the available data.") + "</p></div>";
      clearDistrictMarkers();
      return;
    }

    var cards = data.district_alternatives.map(districtCardHtml).join("");
    els.districts.innerHTML =
      '<div class="rebalance-card">' +
      '<span class="rebalance-card__title">🗺️ Nearby Similar Districts</span>' +
      '<p class="rebalance-card__intro">' + escapeHtml(data.district_alternatives_message || "") + "</p>" +
      '<div class="rebalance-alt-list">' + cards + "</div>" +
      '<p class="crowd-card__disclaimer">Districts are real OpenStreetMap administrative areas discovered dynamically around your destination — never a fixed list. Selecting one only updates your search when you tap Explore.</p>' +
      "</div>";
    wireDistrictActions(data);
    renderDistrictMarkers(data);
  }

  function renderRebalancer() {
    if (!els.rebalance) return;
    els.rebalance.innerHTML = '<div class="rebalance-card"><p class="muted">Looking for lower-pressure alternatives…</p></div>';
    if (els.districts) els.districts.innerHTML = '<div class="rebalance-card"><p class="muted">Checking nearby districts for lower tourism pressure…</p></div>';

    API.rebalanceDestination({
      destination_query: state.label, latitude: state.lat, longitude: state.lon,
      interests: [], max_alternatives: 5,
    }).then(function (res) {
      if (!res.ok) {
        els.rebalance.innerHTML =
          '<div class="rebalance-card rebalance-card--unavailable"><span class="rebalance-card__title">🧭 Nearby Alternatives</span>' +
          '<p class="muted">Temporarily unavailable — ' + escapeHtml(res.error) + "</p></div>";
        if (els.districts) {
          els.districts.innerHTML =
            '<div class="rebalance-card rebalance-card--unavailable"><span class="rebalance-card__title">🗺️ Nearby Similar Districts</span>' +
            '<p class="muted">Temporarily unavailable — ' + escapeHtml(res.error) + "</p></div>";
        }
        return;
      }
      // Two independent pipelines, one shared response -- neither gates the
      // other's rendering (see renderDistrictAlternatives' comment above).
      var data = res.data;
      renderSettlementAlternatives(data);
      renderDistrictAlternatives(data);
    });
  }

  /* ---------- Events (Ticketmaster, optional) ---------- */
  function renderEvents() {
    if (!els.events) return;
    els.events.innerHTML = '<p class="muted">Checking for nearby events…</p>';
    API.events(state.lat, state.lon, { radiusKm: 30 }).then(function (res) {
      if (!res.ok) { els.events.innerHTML = ""; return; }
      var data = res.data;
      if (!data.configured) { els.events.innerHTML = ""; return; } // don't clutter the page when the feature simply isn't set up
      if (!data.events.length) {
        els.events.innerHTML = '<div class="real-events__card"><span class="live-badge">● REAL · Ticketmaster</span> ' +
          '<span class="muted">No listed events found nearby. ' + escapeHtml(data.coverage_note || "") + "</span></div>";
        return;
      }
      els.events.innerHTML = '<div class="real-events__card"><span class="live-badge">● REAL · Ticketmaster</span>' +
        '<div class="real-events__list">' +
        data.events.slice(0, 4).map(function (e) {
          return '<a class="real-events__item" href="' + escapeAttr(e.url || "#") + '" target="_blank" rel="noopener">' +
            "🎟️ <b>" + escapeHtml(e.name) + "</b>" +
            (e.start_datetime ? " <span class=\"muted\">" + escapeHtml(e.start_datetime.slice(0, 10)) + "</span>" : "") +
            (e.venue_name ? " <span class=\"muted\">· " + escapeHtml(e.venue_name) + "</span>" : "") +
            "</a>";
        }).join("") + "</div></div>";
    });
  }

  function renderWeather() {
    if (!state.weather) {
      els.weather.innerHTML = '<div class="real-weather__unavailable">🌤️ Weather is temporarily unavailable.</div>';
      return;
    }
    var w = state.weather;
    var suitLabel = { good: "Great for outdoor plans", fair: "Mixed — plan a backup indoor option", poor: "Poor for outdoors — prioritize indoor places" }[w.outdoor_suitability];
    els.weather.innerHTML =
      '<div class="real-weather__card">' +
      '<span class="live-badge">● REAL · Open-Meteo</span>' +
      '<div class="real-weather__main"><b>' + Math.round(w.current.temperature_c) + "°C</b><span>" + escapeHtml(w.current.condition_text) + "</span></div>" +
      '<div class="real-weather__meta">' +
      (w.current.wind_speed_kmh != null ? "💨 " + Math.round(w.current.wind_speed_kmh) + " km/h &nbsp;" : "") +
      (w.current.precipitation_mm != null ? "🌧️ " + w.current.precipitation_mm + " mm" : "") +
      "</div>" +
      '<div class="real-weather__suit real-weather__suit--' + w.outdoor_suitability + '">' + suitLabel + "</div>" +
      "</div>";
  }

  function applyFilterAndRender() {
    var filtered = state.activeCategories.length
      ? state.allPlaces.filter(function (p) { return state.activeCategories.indexOf(p.category) >= 0; })
      : state.allPlaces;
    var effective = state.effectiveRadiusMeters, requested = state.requestedRadiusMeters;
    // Honest radius disclosure (spec: "Radius Strategy") -- only mentioned
    // when the backend actually had to widen past the requested radius, so
    // the normal (non-sparse) case reads exactly as it always did.
    var radiusSuffix = effective != null && requested != null && effective !== requested
      ? " (search widened to " + (effective / 1000) + " km — this area is sparse in OpenStreetMap)"
      : "";
    els.count.innerHTML = "Showing <b>" + filtered.length + "</b> real place" + (filtered.length === 1 ? "" : "s") +
      " near “" + escapeHtml(state.label) + "”" + radiusSuffix;
    renderCards(filtered);
    renderMarkers(filtered);
    updateMapView();
  }

  // Timing/price shown on a card are only ever what OpenStreetMap actually recorded for that
  // specific place (opening_hours, and the fee/charge tags) -- most OSM places simply have
  // neither, and this deliberately shows nothing rather than a fabricated "9am-5pm" or "₹50".
  function feeLabel(p) {
    var tags = p.raw_tags || {};
    if (tags.charge) return "🎫 " + tags.charge;
    if (tags.fee === "no") return "🎫 Free entry";
    if (tags.fee === "yes") return "🎫 Entry fee applies";
    return null;
  }

  function renderCards(places) {
    if (!places.length) {
      els.cards.innerHTML = '<div class="itinerary-empty"><div class="big">🔍</div><b>No places match this filter</b></div>';
      return;
    }
    els.cards.innerHTML = places
      .map(function (p) {
        var meta = API.CATEGORY_META[p.category] || API.CATEGORY_META.other;
        var dist = p.distance_meters != null ? (p.distance_meters < 1000 ? Math.round(p.distance_meters) + " m" : (p.distance_meters / 1000).toFixed(1) + " km") : "";
        var fee = feeLabel(p);
        var extras = [];
        if (p.opening_hours) extras.push('<span>🕒 ' + escapeHtml(p.opening_hours) + "</span>");
        if (fee) extras.push("<span>" + escapeHtml(fee) + "</span>");
        return (
          '<article class="real-card" data-place="' + p.id + '">' +
          '<div class="real-card__icon">' + meta.icon + "</div>" +
          '<div class="real-card__body">' +
          "<b>" + escapeHtml(p.name) + "</b>" +
          '<div class="real-card__meta">' + meta.label + (dist ? " · " + dist : "") + "</div>" +
          (p.address ? '<div class="real-card__addr">' + escapeHtml(p.address) + "</div>" : "") +
          (extras.length ? '<div class="real-card__extra">' + extras.join("") + "</div>" : "") +
          "</div>" +
          '<button class="btn btn--ghost btn--sm" data-open="' + p.id + '">Details</button>' +
          "</article>"
        );
      })
      .join("");
    els.cards.querySelectorAll("[data-open]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var p = places.find(function (x) { return x.id === btn.getAttribute("data-open"); });
        if (p) openPlace(p);
      });
    });
  }

  /* ---------- Place details panel ---------- */
  function openPlace(place) {
    state.selectedPlaceId = place.id;
    var marker = state.markers[place.id];
    if (marker) { state.map.panTo(marker.getLatLng()); marker.openPopup(); }

    els.panel.classList.add("is-open");
    els.panelOverlay.classList.add("is-open");
    els.panelBody.innerHTML = placeDetailSkeleton(place);

    wirePanelActions(place);

    API.placeDetails(place.id).then(function (res) {
      if (!res.ok) return; // keep skeleton (already has the fields we had from the list call)
      renderPlaceDetail(place, res.data);
      wirePanelActions(place);
    });
  }

  function placeDetailSkeleton(p) {
    return renderPlaceDetail(p, p);
  }

  function ratingHtml(details) {
    if (details.rating != null) return "★ " + details.rating + (details.review_count ? " (" + details.review_count + " reviews)" : "");
    return '<span class="muted">Not available — OpenStreetMap doesn\'t carry traveller ratings for most places</span>';
  }

  function renderPlaceDetail(base, details) {
    var meta = API.CATEGORY_META[details.category] || API.CATEGORY_META.other;
    var html =
      '<div class="place-detail">' +
      '<div class="place-detail__photo" data-panel-photo></div>' +
      '<div class="place-detail__icon">' + meta.icon + "</div>" +
      "<h3>" + escapeHtml(details.name) + "</h3>" +
      '<div class="place-detail__cat">' + meta.label + "</div>" +
      '<div class="place-detail__row"><b>Rating</b><span>' + ratingHtml(details) + "</span></div>" +
      (details.address ? '<div class="place-detail__row"><b>Address</b><span>' + escapeHtml(details.address) + "</span></div>" : "") +
      '<div class="place-detail__row"><b>Coordinates</b><span>' + details.latitude.toFixed(5) + ", " + details.longitude.toFixed(5) + "</span></div>" +
      (details.opening_hours
        ? '<div class="place-detail__row"><b>Opening hours</b><span>' + escapeHtml(details.opening_hours) + " <small class=\"muted\">(OSM opening_hours syntax)</small></span></div>"
        : '<div class="place-detail__row"><b>Opening hours</b><span class="muted">Not recorded in OpenStreetMap</span></div>') +
      (details.website ? '<div class="place-detail__row"><b>Website</b><span><a href="' + escapeAttr(details.website) + '" target="_blank" rel="noopener">' + escapeHtml(details.website) + "</a></span></div>" : "") +
      (details.phone ? '<div class="place-detail__row"><b>Phone</b><span>' + escapeHtml(details.phone) + "</span></div>" : "") +
      (details.description ? '<p class="place-detail__desc">' + escapeHtml(details.description) + "</p>" : "") +
      '<div class="place-detail__source">Source: <a href="' + escapeAttr(details.source_url || "#") + '" target="_blank" rel="noopener">OpenStreetMap</a></div>' +
      '<div class="place-detail__actions">' +
      '<button class="btn btn--primary btn--sm" data-panel-add>🧳 Add to trip</button>' +
      '<button class="btn btn--ghost btn--sm" data-panel-culture>🏺 Cultural significance</button>' +
      "</div>" +
      '<div class="place-detail__culture" data-panel-culture-body hidden></div>' +
      "</div>";
    return html;
  }

  function loadPanelPhoto(place) {
    var photoBox = els.panelBody.querySelector("[data-panel-photo]");
    if (!photoBox) return;
    API.searchImages(place.name + " India", 1).then(function (res) {
      if (!res.ok || !res.data.configured || !res.data.images.length) { photoBox.remove(); return; }
      var img = res.data.images[0];
      photoBox.innerHTML =
        '<img src="' + escapeAttr(img.url) + '" alt="' + escapeAttr(img.description || place.name) + '" loading="lazy" />' +
        '<div class="place-detail__photo-credit">Photo: <a href="' + escapeAttr(img.photographer_profile_url) + '" target="_blank" rel="noopener">' + escapeHtml(img.photographer_name) + '</a> on <a href="' + escapeAttr(img.unsplash_url) + '" target="_blank" rel="noopener">Unsplash</a></div>';
    });
  }

  function wirePanelActions(place) {
    loadPanelPhoto(place);
    var addBtn = els.panelBody.querySelector("[data-panel-add]");
    if (addBtn) {
      addBtn.addEventListener("click", function () {
        addToRealTrip(place);
        addBtn.textContent = "✓ Added to trip";
        addBtn.disabled = true;
        if (window.Sarthi && window.Sarthi.toast) window.Sarthi.toast(place.name + " added to your real-places trip", "🧳");
      });
    }
    var cultureBtn = els.panelBody.querySelector("[data-panel-culture]");
    var cultureBody = els.panelBody.querySelector("[data-panel-culture-body]");
    if (cultureBtn && cultureBody) {
      cultureBtn.addEventListener("click", function () {
        if (!cultureBody.hidden) { cultureBody.hidden = true; return; }
        cultureBody.hidden = false;
        cultureBody.innerHTML = '<p class="muted">Loading…</p>';
        API.placeCulture(place.id).then(function (res) {
          if (!res.ok) { cultureBody.innerHTML = '<p class="muted">Cultural info temporarily unavailable.</p>'; return; }
          cultureBody.innerHTML = renderCulture(res.data);
        });
      });
    }
  }

  function renderCulture(c) {
    if (!c.matched) {
      return '<p class="muted">' + escapeHtml(c.fallback_message || "No sourced cultural information for this place yet.") + "</p>";
    }
    var sourceBadge = { curated: "📚 Sārthi curated", wikipedia: "🌐 Wikipedia", wikidata: "🌐 Wikidata" }[c.source] || "";
    var html = sourceBadge ? '<span class="live-badge">' + sourceBadge + "</span>" : "";
    if (c.summary) html += "<p>" + escapeHtml(c.summary) + "</p>";
    var rows = [
      ["Historical significance", c.historical_significance],
      ["Cultural significance", c.cultural_significance],
      ["Architectural significance", c.architectural_significance],
      ["Traditions", c.traditions],
      ["Etiquette", c.etiquette],
      ["Visitor guidance", c.visitor_guidance],
    ];
    rows.forEach(function (r) {
      if (r[1]) html += "<p><b>" + r[0] + ":</b> " + escapeHtml(r[1]) + "</p>";
    });
    if (c.sources && c.sources.length) {
      html += '<p class="muted" style="margin-top:10px"><b>Sources:</b> ' + c.sources.map(escapeHtml).join(" · ") + "</p>";
    }
    return html;
  }

  /* ---------- Add-to-trip bridge (localStorage, read by the Planner page) ---------- */
  function addToRealTrip(place) {
    var LS_KEY = "sarthi.realTripPlaces";
    var list = [];
    try { list = JSON.parse(localStorage.getItem(LS_KEY)) || []; } catch (e) { list = []; }
    if (!list.some(function (p) { return p.place_id === place.id; })) {
      list.push({
        place_id: place.id, name: place.name, category: place.category,
        latitude: place.latitude, longitude: place.longitude, day: 1,
      });
      localStorage.setItem(LS_KEY, JSON.stringify(list));
    }
  }

  function closePanel() {
    els.panel.classList.remove("is-open");
    els.panelOverlay.classList.remove("is-open");
  }

  /* ---------- Category chips ---------- */
  function initCategoryChips() {
    els.categories.innerHTML = CATEGORY_ORDER.map(function (c) {
      var meta = API.CATEGORY_META[c];
      return '<button type="button" class="chip" data-cat="' + c + '">' + meta.icon + " " + meta.label + "</button>";
    }).join("");
    els.categories.querySelectorAll("[data-cat]").forEach(function (chip) {
      chip.addEventListener("click", function () {
        var cat = chip.getAttribute("data-cat");
        var i = state.activeCategories.indexOf(cat);
        if (i >= 0) { state.activeCategories.splice(i, 1); chip.classList.remove("is-active"); }
        else { state.activeCategories.push(cat); chip.classList.add("is-active"); }
        if (state.allPlaces.length) applyFilterAndRender();
      });
    });
  }

  function escapeHtml(s) {
    var d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }
  function escapeAttr(s) { return escapeHtml(s).replace(/"/g, "&quot;"); }

  function formatCacheAge(seconds) {
    if (seconds < 120) return "under 2 minutes";
    var minutes = Math.round(seconds / 60);
    if (minutes < 60) return minutes + " minutes";
    var hours = Math.round(minutes / 60);
    if (hours < 48) return hours + (hours === 1 ? " hour" : " hours");
    return Math.round(hours / 24) + " days";
  }

  function init() {
    cacheEls();
    if (!els.mapDiv) return; // this page doesn't have the real-explore section
    if (window.L) {
      initMap();
    } else {
      // Leaflet's own CDN script failed to load -- search, weather, the
      // Crowding Index, the Tourist Flow Rebalancer and District Discovery
      // all still work below; only the visual map is affected, and this says
      // so honestly rather than leaving a permanently blank box.
      els.mapDiv.innerHTML = '<p class="muted" style="padding:16px;text-align:center">🗺️ Map temporarily unavailable — real places, weather and alternatives still show below as lists.</p>';
    }
    initCategoryChips();

    els.search.addEventListener("input", function () { doGeocode(els.search.value); });
    els.search.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { e.preventDefault(); submitSearch(); }
    });
    document.addEventListener("click", function (e) {
      if (!els.suggest.contains(e.target) && e.target !== els.search) els.suggest.hidden = true;
    });

    els.geolocate.addEventListener("click", function () {
      if (!navigator.geolocation) { setStatus("Your browser doesn't support geolocation.", "error"); return; }
      setStatus("Getting your location…", "info");
      navigator.geolocation.getCurrentPosition(
        function (pos) { setLocation(pos.coords.latitude, pos.coords.longitude, "Your location"); },
        function () { setStatus("Location permission denied — search a destination by name instead.", "warn"); }
      );
    });

    els.panelClose.addEventListener("click", closePanel);
    els.panelOverlay.addEventListener("click", closePanel);

    // deep link support: explore.html?q=Amritsar&lat=..&lon=..
    var params = new URLSearchParams(location.search);
    var lat = parseFloat(params.get("lat"));
    var lon = parseFloat(params.get("lon"));
    var q = params.get("q");
    if (!isNaN(lat) && !isNaN(lon)) {
      els.search.value = q || "";
      setLocation(lat, lon, q || "Selected location");
    } else if (q) {
      els.search.value = q;
      API.geocodeSearch(q, 1).then(function (res) {
        if (res.ok && res.data.length) setLocation(res.data[0].latitude, res.data[0].longitude, res.data[0].display_name);
        else setStatus("Couldn't find “" + q + "”. Try a different spelling.", "warn");
      });
    }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
