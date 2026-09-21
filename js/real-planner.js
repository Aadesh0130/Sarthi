/* =========================================================
   Sarthi — Real Trip Builder (planner.html).
   Takes the real places a traveller added from Explore
   (stored in localStorage by js/real-explore.js), lets them
   organise it into days, shows it on a live Leaflet map,
   computes a real OSRM route, checks real weather, and offers
   explainable recommendations for more nearby places to add.
   Fully additive to the existing curated AI Planner above it.
   ========================================================= */
(function () {
  "use strict";
  // Only SarthiAPI is hard-required -- Leaflet (window.L) comes from a
  // third-party CDN and can fail to load independently of everything else
  // here (day organisation, real weather, recommendations, save/replan are
  // all unrelated to the map). See the matching comment in real-explore.js.
  if (!window.SarthiAPI) return;
  var API = window.SarthiAPI;
  var LS_KEY = "sarthi.realTripPlaces";
  var LS_ITINERARY_ID = "sarthi.realItineraryId";

  var els = {};
  var map, markers = [], routeLine;

  function $(sel) { return document.querySelector(sel); }

  function load() {
    try { return JSON.parse(localStorage.getItem(LS_KEY)) || []; } catch (e) { return []; }
  }
  function save(list) { localStorage.setItem(LS_KEY, JSON.stringify(list)); }

  function cacheEls() {
    els.root = $("[data-real-planner]");
    els.empty = $("[data-rp-empty]");
    els.content = $("[data-rp-content]");
    els.list = $("[data-rp-list]");
    els.mapDiv = $("#p-map");
    els.weather = $("[data-rp-weather]");
    els.events = $("[data-rp-events]");
    els.hotels = $("[data-rp-hotels]");
    els.recs = $("[data-rp-recs]");
    els.saveBtn = $("[data-rp-save]");
    els.replanBtn = $("[data-rp-replan]");
    els.replanReason = $("[data-rp-replan-reason]");
    els.routeInfo = $("[data-rp-route]");
    els.status = $("[data-rp-status]");
  }

  function categoryIcon(cat) { return (API.CATEGORY_META[cat] || API.CATEGORY_META.other).icon; }
  function categoryLabel(cat) { return (API.CATEGORY_META[cat] || API.CATEGORY_META.other).label; }

  function render() {
    var list = load();
    if (!list.length) {
      els.empty.hidden = false;
      els.content.hidden = true;
      return;
    }
    els.empty.hidden = true;
    els.content.hidden = false;

    var byDay = {};
    list.forEach(function (p) { (byDay[p.day] = byDay[p.day] || []).push(p); });
    var days = Object.keys(byDay).map(Number).sort(function (a, b) { return a - b; });

    var html = "";
    days.forEach(function (day) {
      html += '<div class="rp-day"><div class="rp-day__head">Day ' + day + "</div>";
      byDay[day].forEach(function (p) {
        html +=
          '<div class="rp-item" data-id="' + p.place_id + '">' +
          '<span class="rp-item__icon">' + categoryIcon(p.category) + "</span>" +
          '<span class="rp-item__name">' + escapeHtml(p.name) + '<small>' + categoryLabel(p.category) + "</small></span>" +
          '<select class="rp-item__day" data-day-select="' + p.place_id + '">' +
          [1, 2, 3, 4, 5, 6, 7].map(function (d) { return '<option value="' + d + '"' + (d === day ? " selected" : "") + ">Day " + d + "</option>"; }).join("") +
          "</select>" +
          '<button class="ci-remove" data-remove="' + p.place_id + '" aria-label="Remove">×</button>' +
          "</div>";
      });
      html += "</div>";
    });
    els.list.innerHTML = html;

    els.list.querySelectorAll("[data-remove]").forEach(function (b) {
      b.addEventListener("click", function () {
        var placeId = b.getAttribute("data-remove");
        var itineraryId = localStorage.getItem(LS_ITINERARY_ID);
        if (itineraryId) {
          // Itinerary is already saved -- go through the real deterministic
          // replan endpoint (reason=remove_place) instead of just editing
          // localStorage, so the backend copy stays in sync too.
          setStatus("Removing and re-sequencing…", "info");
          API.replanItinerary(itineraryId, { reason: "remove_place", remove_place_id: placeId }).then(function (res) {
            applyReplanResult(res, "Removed and re-sequenced the remaining stops.");
          });
        } else {
          save(load().filter(function (p) { return p.place_id !== placeId; }));
          render();
          drawMap();
        }
      });
    });
    els.list.querySelectorAll("[data-day-select]").forEach(function (sel) {
      sel.addEventListener("change", function () {
        var id = sel.getAttribute("data-day-select");
        var updated = load().map(function (p) { return p.place_id === id ? Object.assign({}, p, { day: +sel.value }) : p; });
        save(updated);
        render();
      });
    });

    drawMap();
    loadWeatherAndRecs(list);
    loadEventsAndHotels(list);
  }

  function initMap() {
    if (map || !els.mapDiv) return;
    if (!window.L) {
      // Leaflet's CDN script didn't load -- the day list, weather,
      // recommendations, events/hotels and save/replan below are all
      // unaffected; say so honestly instead of leaving a blank box.
      els.mapDiv.innerHTML = '<p class="muted" style="padding:16px;text-align:center">🗺️ Map temporarily unavailable.</p>';
      return;
    }
    map = L.map(els.mapDiv).setView([22.9734, 78.6569], 5);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 19,
    }).addTo(map);
  }

  function drawMap() {
    initMap();
    if (!map) return;
    markers.forEach(function (m) { map.removeLayer(m); });
    markers = [];
    if (routeLine) { map.removeLayer(routeLine); routeLine = null; }

    var list = load();
    if (!list.length) return;
    var bounds = [];
    list.forEach(function (p) {
      var m = L.marker([p.latitude, p.longitude]).addTo(map).bindPopup("<b>" + escapeHtml(p.name) + "</b><br>Day " + p.day);
      markers.push(m);
      bounds.push([p.latitude, p.longitude]);
    });
    map.fitBounds(bounds, { padding: [30, 30], maxZoom: 14 });
  }

  function centroid(list) {
    var lat = list.reduce(function (s, p) { return s + p.latitude; }, 0) / list.length;
    var lon = list.reduce(function (s, p) { return s + p.longitude; }, 0) / list.length;
    return { lat: lat, lon: lon };
  }

  function selectedInterests() {
    var chips = document.querySelectorAll("#f-interests .chip.is-active");
    return Array.prototype.slice.call(chips).map(function (c) { return c.textContent.trim(); });
  }

  function loadWeatherAndRecs(list) {
    var c = centroid(list);
    API.weather(c.lat, c.lon).then(function (res) {
      if (!res.ok) { els.weather.innerHTML = '<p class="muted">Weather temporarily unavailable.</p>'; return; }
      var w = res.data;
      var suitLabel = { good: "Good outdoor weather", fair: "Mixed — keep an indoor backup", poor: "Poor for outdoors today" }[w.outdoor_suitability];
      els.weather.innerHTML =
        '<span class="live-badge">● REAL · Open-Meteo</span> ' +
        "<b>" + Math.round(w.current.temperature_c) + "°C</b> · " + escapeHtml(w.current.condition_text) +
        ' <span class="real-weather__suit real-weather__suit--' + w.outdoor_suitability + '">' + suitLabel + "</span>";
    });

    API.recommendations({
      latitude: c.lat, longitude: c.lon, interests: selectedInterests(),
      pace: activeSegment("#f-pace") || "balanced", budget: activeSegment("#f-budget") || "comfort",
    }).then(function (res) {
      if (!res.ok) { els.recs.innerHTML = '<p class="muted">Recommendations temporarily unavailable.</p>'; return; }
      var addedIds = list.map(function (p) { return p.place_id; });
      var candidates = res.data.results.filter(function (r) { return addedIds.indexOf(r.place.id) < 0; }).slice(0, 6);
      if (!candidates.length) { els.recs.innerHTML = '<p class="muted">No further nearby suggestions right now.</p>'; return; }
      els.recs.innerHTML = candidates.map(function (r) {
        return (
          '<div class="rec-item">' +
          '<div class="rec-item__head"><b>' + categoryIcon(r.place.category) + " " + escapeHtml(r.place.name) + '</b><span class="smartscore-label">🎯 ' + r.smart_score + "</span></div>" +
          '<div class="rec-item__reasons">' + r.reasons.map(function (x) { return "<span>" + escapeHtml(x) + "</span>"; }).join("") + "</div>" +
          '<button class="btn btn--ghost btn--sm" data-add-rec=\'' + JSON.stringify(r.place).replace(/'/g, "&#39;") + "'>+ Add to trip</button>" +
          "</div>"
        );
      }).join("");
      els.recs.querySelectorAll("[data-add-rec]").forEach(function (btn) {
        btn.addEventListener("click", function () {
          var place = JSON.parse(btn.getAttribute("data-add-rec"));
          var list2 = load();
          list2.push({ place_id: place.id, name: place.name, category: place.category, latitude: place.latitude, longitude: place.longitude, day: 1 });
          save(list2);
          render();
        });
      });
    });
  }

  /* ---------- Events + hotels near the trip's centroid (optional providers) ---------- */
  function isoDate(daysFromNow) {
    var d = new Date();
    d.setDate(d.getDate() + daysFromNow);
    return d.toISOString().slice(0, 10);
  }

  function loadEventsAndHotels(list) {
    var c = centroid(list);

    if (els.events) {
      API.events(c.lat, c.lon, { radiusKm: 30 }).then(function (res) {
        if (!res.ok || !res.data.configured) { els.events.innerHTML = ""; return; }
        if (!res.data.events.length) { els.events.innerHTML = ""; return; }
        els.events.innerHTML = '<span class="live-badge">● REAL · Ticketmaster</span> ' +
          res.data.events.slice(0, 3).map(function (e) { return "🎟️ " + escapeHtml(e.name); }).join(" &nbsp;·&nbsp; ");
      });
    }

    if (els.hotels) {
      var checkIn = isoDate(7), checkOut = isoDate(9); // a representative near-future stay, purely for a live demo search
      API.hotels(c.lat, c.lon, checkIn, checkOut, { radiusKm: 15 }).then(function (res) {
        if (!res.ok || !res.data.configured) { els.hotels.innerHTML = ""; return; }
        if (!res.data.hotels.length) {
          els.hotels.innerHTML = '<span class="live-badge">● REAL · Hotelbeds</span> <span class="muted">No hotels returned for ' + checkIn + " → " + checkOut + "</span>";
          return;
        }
        els.hotels.innerHTML = '<span class="live-badge">● REAL · Hotelbeds · ' + checkIn + " → " + checkOut + '</span> ' +
          res.data.hotels.slice(0, 3).map(function (h) {
            var rate = h.rates && h.rates[0];
            return "🏨 " + escapeHtml(h.name) + (rate && rate.net_price ? " (" + (rate.currency || "") + " " + rate.net_price + (rate.requires_recheck ? ", needs re-check" : "") + ")" : "");
          }).join(" &nbsp;·&nbsp; ");
      });
    }
  }

  function activeSegment(sel) {
    var btn = document.querySelector(sel + " button.is-active");
    return btn ? btn.getAttribute("data-val") : null;
  }

  function setStatus(msg, kind) {
    if (!els.status) return;
    if (!msg) { els.status.hidden = true; return; }
    els.status.hidden = false;
    els.status.className = "real-status" + (kind ? " real-status--" + kind : "");
    els.status.textContent = msg;
  }

  function optimizeRoute() {
    var list = load();
    if (list.length < 2) { setStatus("Add at least 2 places to compute a route.", "warn"); return; }
    var stops = list
      .slice()
      .sort(function (a, b) { return a.day - b.day; })
      .map(function (p) { return { name: p.name, latitude: p.latitude, longitude: p.longitude }; });
    setStatus("Calculating a real driving route via OSRM…", "info");
    API.route(stops, "driving").then(function (res) {
      if (!res.ok) { setStatus("Routing is temporarily unavailable (" + res.error + ").", "error"); return; }
      setStatus("");
      initMap();
      if (map) {
        if (routeLine) map.removeLayer(routeLine);
        var coords = res.data.geometry_geojson.coordinates.map(function (c) { return [c[1], c[0]]; });
        routeLine = L.polyline(coords, { color: "#f2551f", weight: 4, opacity: 0.85 }).addTo(map);
        map.fitBounds(routeLine.getBounds(), { padding: [30, 30] });
      }
      var km = (res.data.total_distance_meters / 1000).toFixed(1);
      var mins = Math.round(res.data.total_duration_seconds / 60);
      els.routeInfo.hidden = false;
      els.routeInfo.innerHTML =
        '<span class="live-badge">● REAL · OSRM</span> Total route: <b>' + km + " km</b> · <b>" + mins + " min</b> driving " +
        '<span class="muted">(' + res.data.provider_note + ")</span>";
    });
  }

  function saveItinerary() {
    var list = load();
    if (!list.length) { setStatus("Add some places first.", "warn"); return; }
    var days = Math.max.apply(null, list.map(function (p) { return p.day; }));
    var payload = {
      title: (document.querySelector("#f-dest")?.selectedOptions?.[0]?.textContent || "My Sarthi trip") + " (real places)",
      destination_query: "", days: days,
      travelers: +(document.querySelector("#f-trav-input")?.value || 1),
      budget: activeSegment("#f-budget") || "comfort",
      pace: activeSegment("#f-pace") || "balanced",
      interests: selectedInterests(),
      items: list.map(function (p, i) {
        return {
          day: p.day, place_id: p.place_id, name: p.name, category: p.category,
          latitude: p.latitude, longitude: p.longitude, suggested_time: "", estimated_duration_minutes: 90, notes: "",
        };
      }),
    };
    setStatus("Saving itinerary…", "info");
    API.createItinerary(payload).then(function (res) {
      if (!res.ok) { setStatus("Couldn't save the itinerary (" + res.error + ").", "error"); return; }
      localStorage.setItem(LS_ITINERARY_ID, res.data.id);
      setStatus("Saved! Itinerary #" + res.data.id + " — you can now replan it for weather.", "success");
      els.replanBtn.disabled = false;
    });
  }

  function applyReplanResult(res, successMsg) {
    if (!res.ok) { setStatus("Replan failed (" + res.error + ").", "error"); return; }
    var newList = res.data.items.map(function (it) {
      return { place_id: it.place_id, name: it.name, category: it.category, latitude: it.latitude, longitude: it.longitude, day: it.day };
    });
    save(newList);
    render();
    setStatus(successMsg, "success");
  }

  function replan() {
    var id = localStorage.getItem(LS_ITINERARY_ID);
    if (!id) { setStatus("Save the itinerary first.", "warn"); return; }
    var reason = els.replanReason ? els.replanReason.value : "weather";

    if (reason === "weather") {
      setStatus("Checking real weather for each day and replanning…", "info");
      API.replanItinerary(id, { reason: "weather" }).then(function (res) {
        applyReplanResult(res, "Replanned using the real forecast — indoor places were moved earlier on any poor-weather day.");
      });
    } else if (reason === "preferences_changed") {
      setStatus("Re-scoring your itinerary against your current interests/pace/budget…", "info");
      API.replanItinerary(id, {
        reason: "preferences_changed", new_interests: selectedInterests(),
        new_pace: activeSegment("#f-pace"), new_budget: activeSegment("#f-budget"),
      }).then(function (res) {
        applyReplanResult(res, "Re-ordered each day using Sarthi's deterministic SmartScore against your updated preferences.");
      });
    } else if (reason === "time_limited") {
      var list = load();
      var uniqueDays = [];
      list.forEach(function (p) { if (uniqueDays.indexOf(p.day) < 0) uniqueDays.push(p.day); });
      var days = uniqueDays.length ? uniqueDays : [1];
      var day = +(prompt("Which day number has less time available?", days[0] || 1) || days[0] || 1);
      var hours = +(prompt("How many hours are available on day " + day + " now?", "3") || 3);
      if (!hours) return;
      setStatus("Trimming day " + day + " to fit " + hours + " hour(s)…", "info");
      API.replanItinerary(id, { reason: "time_limited", day: day, new_available_hours: hours }).then(function (res) {
        applyReplanResult(res, "Trimmed day " + day + " to fit the reduced time -- lower-priority stops were dropped, not silently kept in an impossible schedule.");
      });
    }
  }

  function escapeHtml(s) {
    var d = document.createElement("div");
    d.textContent = s == null ? "" : String(s);
    return d.innerHTML;
  }

  function init() {
    cacheEls();
    if (!els.root) return;
    els.replanBtn.disabled = !localStorage.getItem(LS_ITINERARY_ID);
    document.querySelector("[data-rp-optimize]").addEventListener("click", optimizeRoute);
    els.saveBtn.addEventListener("click", saveItinerary);
    els.replanBtn.addEventListener("click", replan);
    render();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
