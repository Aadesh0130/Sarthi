/* =========================================================
   Sarthi — API client for the real-data backend.
   Talks to the FastAPI backend (see /backend). Every call
   fails soft: on any network/provider error it returns
   { ok:false, error } instead of throwing, so pages can show
   an honest "temporarily unavailable" state (spec section 28)
   rather than crashing or inventing data.
   ========================================================= */
(function () {
  "use strict";

  // Change this if your backend runs somewhere other than localhost:8000.
  var BACKEND_URL = window.SARTHI_BACKEND_URL || "http://localhost:8000";

  function qs(params) {
    var parts = [];
    Object.keys(params || {}).forEach(function (k) {
      if (params[k] === undefined || params[k] === null || params[k] === "") return;
      parts.push(encodeURIComponent(k) + "=" + encodeURIComponent(params[k]));
    });
    return parts.length ? "?" + parts.join("&") : "";
  }

  // ---------- Auth token storage (see js/auth.js for the login UI itself) ----------
  // The backend also accepts an httpOnly `sarthi_token` cookie (defense in
  // depth for same-origin deployments -- app/core/security.py checks
  // either), but the frontend's PRIMARY auth mechanism is this bearer
  // token: the site is normally opened as a static file or from a
  // different port than the API, and a cross-origin cookie would need
  // `allow_credentials=true` plus an exact-origin CORS allowlist instead of
  // the current "*" -- a bigger, separate change. A token in localStorage
  // works identically regardless of how the frontend happens to be served.
  var TOKEN_KEY = "sarthi.authToken";
  function getToken() {
    try { return localStorage.getItem(TOKEN_KEY); } catch (e) { return null; }
  }
  function setToken(token) {
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    } catch (e) { /* private-browsing storage can throw -- session still works for this tab */ }
  }

  function request(path, options) {
    options = options || {};
    var url = BACKEND_URL + path;
    var controller = typeof AbortController !== "undefined" ? new AbortController() : null;
    var headers = { "Content-Type": "application/json" };
    var token = getToken();
    if (token) headers.Authorization = "Bearer " + token;
    var opts = {
      method: options.method || "GET",
      headers: headers,
      signal: controller ? controller.signal : undefined,
    };
    if (options.body) opts.body = JSON.stringify(options.body);

    var timeoutMs = options.timeoutMs || 12000;
    var timer = controller ? setTimeout(function () { controller.abort(); }, timeoutMs) : null;

    return fetch(url, opts)
      .then(function (res) {
        if (timer) clearTimeout(timer);
        if (!res.ok) {
          return res
            .json()
            .catch(function () { return {}; })
            .then(function (body) {
              return { ok: false, status: res.status, error: (body && body.detail) || ("HTTP " + res.status) };
            });
        }
        // Some endpoints (places/nearby, places/search) mark a response as
        // served from an out-of-date cache -- last resort for when every
        // live provider failed -- via this header, never by silently
        // pretending stale data is fresh. See backend/app/api/places.py.
        var staleAgeHeader = res.headers.get("X-Sarthi-Cache-Age-Seconds");
        // Same endpoints also always report the actual radius searched (spec:
        // "Radius Strategy" -- "must clearly indicate the ACTUAL radius
        // used"), since a sparse area can make the backend silently widen
        // past the radius the caller originally asked for.
        var requestedRadiusHeader = res.headers.get("X-Sarthi-Requested-Radius-Meters");
        var effectiveRadiusHeader = res.headers.get("X-Sarthi-Effective-Radius-Meters");
        return res.json().then(function (data) {
          return {
            ok: true,
            data: data,
            staleSeconds: staleAgeHeader != null ? parseInt(staleAgeHeader, 10) : null,
            requestedRadiusMeters: requestedRadiusHeader != null ? parseInt(requestedRadiusHeader, 10) : null,
            effectiveRadiusMeters: effectiveRadiusHeader != null ? parseInt(effectiveRadiusHeader, 10) : null,
          };
        });
      })
      .catch(function (err) {
        if (timer) clearTimeout(timer);
        var msg = err && err.name === "AbortError" ? "Request timed out" : "Network error — is the Sarthi backend running?";
        return { ok: false, status: 0, error: msg };
      });
  }

  var API = {
    backendUrl: BACKEND_URL,

    health: function () {
      return request("/api/health");
    },
    geocodeSearch: function (q, limit) {
      return request("/api/geocode/search" + qs({ q: q, limit: limit || 5 }));
    },
    placesNearby: function (lat, lon, radiusMeters, categories) {
      return request(
        "/api/places/nearby" + qs({ lat: lat, lon: lon, radius_meters: radiusMeters || 3000, categories: (categories || []).join(",") }),
        // Real-world fix (2026-09-16): this used to budget ~35s, sized for a SINGLE
        // hedged Overpass request (4 mirrors, up to ~27s worst case -- see
        // backend/app/integrations/overpass.py: _post). It didn't account for
        // backend/app/services/places_service.py's own radius-escalation retry: a
        // sparse first attempt (fewer than 6 results) triggers a SECOND full hedge
        // cycle at 2x the radius, and a THIRD at 3x if that's still sparse -- each one
        // a genuinely new live request, run one after another, not in parallel. Worst
        // case is therefore up to ~3x a single hedge cycle (~80s), not ~27s. A 35s
        // frontend timeout was aborting -- and reporting as "unavailable" -- searches
        // the backend would have honestly answered if just given the time its own
        // documented retry strategy needs. This was cutting off real, in-progress,
        // eventually-successful answers, not just genuine failures.
        { timeoutMs: 95000 }
      );
    },
    placeDetails: function (placeId) {
      return request("/api/places/" + placeId); // placeId already "node/123" style
    },
    placeCulture: function (placeId) {
      return request("/api/places/" + placeId + "/culture");
    },
    weather: function (lat, lon) {
      return request("/api/weather" + qs({ lat: lat, lon: lon }));
    },
    route: function (stops, profile) {
      return request("/api/routes", { method: "POST", body: { stops: stops, profile: profile || "driving" } });
    },
    recommendations: function (payload) {
      return request("/api/recommendations", { method: "POST", body: payload });
    },
    createItinerary: function (payload) {
      return request("/api/itineraries", { method: "POST", body: payload });
    },
    updateItinerary: function (id, payload) {
      return request("/api/itineraries/" + id, { method: "PUT", body: payload });
    },
    replanItinerary: function (id, payload) {
      // payload: { reason, remove_place_id?, new_interests?, new_pace?, new_budget?, day?, new_available_hours? }
      if (typeof payload === "string") payload = { reason: payload }; // backward-compatible with the old (id, "weather") call style
      return request("/api/itineraries/" + id + "/replan", { method: "POST", body: payload || { reason: "weather" } });
    },
    aiChat: function (messages) {
      return request("/api/ai/chat", { method: "POST", body: { messages: messages }, timeoutMs: 30000 });
    },
    events: function (lat, lon, opts) {
      opts = opts || {};
      return request("/api/events" + qs({ lat: lat, lon: lon, radius_km: opts.radiusKm, keyword: opts.keyword, start_date: opts.startDate, end_date: opts.endDate }));
    },
    hotels: function (lat, lon, checkIn, checkOut, opts) {
      opts = opts || {};
      return request("/api/hotels" + qs({ lat: lat, lon: lon, check_in: checkIn, check_out: checkOut, adults: opts.adults, radius_km: opts.radiusKm }));
    },
    checkHotelRate: function (rateKey) {
      return request("/api/hotels/check-rate", { method: "POST", body: { rate_key: rateKey } });
    },
    searchImages: function (query, count) {
      return request("/api/images/search" + qs({ q: query, count: count || 1 }));
    },
    cultureByName: function (placeId, name) {
      return request("/api/culture/" + encodeURIComponent(placeId) + qs({ name: name }));
    },
    crowdPressure: function (destination, lat, lon) {
      // Real-world fix (2026-09-16), same root cause as placesNearby above: this calls
      // backend/app/services/crowd_service.py's get_pressure(), which itself calls
      // places_service.nearby_places() -- the SAME radius-escalating (up to 3 sequential
      // hedge cycles, ~80s worst case), not a cheaper one-shot lookup -- plus its own
      // events call on top. The old 35s budget assumed a single ~25s hedge cycle and was
      // aborting genuinely-in-progress (and often eventually successful) requests.
      return request("/api/crowd/pressure" + qs({ destination: destination, lat: lat, lon: lon }), { timeoutMs: 95000 });
    },
    rebalanceDestination: function (payload) {
      // Tourist Flow Rebalancer (spec: TOURIST FLOW REBALANCER). payload:
      // { destination_query, latitude?, longitude?, interests?, pace?, budget?, max_alternatives? }
      // Involves crowd_service.get_pressure() for the requested destination (itself up to
      // ~80s worst case, see crowdPressure above) followed by ANOTHER places_service call
      // for the requested destination's own place density, then settlement + district
      // discovery and per-candidate scoring -- several of these steps chain sequentially
      // rather than all running at once, so the real worst case is a multiple of a single
      // hedge cycle, not a fraction of one. 60s was undersized for the same reason the
      // other two were; give this the most room of the three since it does the most work.
      return request("/api/flow/rebalance", { method: "POST", body: payload, timeoutMs: 130000 });
    },

    /* ---------- Auth (real backend: phone OTP + Google + JWT sessions) ---------- */
    authStatus: function () {
      return request("/api/auth/status");
    },
    requestOtp: function (phone) {
      return request("/api/auth/phone/request-otp", { method: "POST", body: { phone: phone } });
    },
    resendOtp: function (phone) {
      return request("/api/auth/phone/resend-otp", { method: "POST", body: { phone: phone } });
    },
    verifyOtp: function (phone, otp) {
      return request("/api/auth/phone/verify-otp", { method: "POST", body: { phone: phone, otp: otp } }).then(function (res) {
        if (res.ok && res.data.token) setToken(res.data.token);
        return res;
      });
    },
    googleAuth: function (credential) {
      return request("/api/auth/google", { method: "POST", body: { credential: credential } }).then(function (res) {
        if (res.ok && res.data.token) setToken(res.data.token);
        return res;
      });
    },
    me: function () {
      return request("/api/auth/me");
    },
    completeOnboarding: function (payload) {
      return request("/api/auth/onboarding", { method: "POST", body: payload });
    },
    updateProfile: function (payload) {
      return request("/api/auth/profile", { method: "PUT", body: payload });
    },
    logout: function () {
      setToken(null);
      return request("/api/auth/logout", { method: "POST" });
    },
    isLoggedIn: function () {
      return !!getToken();
    },
  };

  /* ---------- debounce helper ---------- */
  API.debounce = function (fn, delay) {
    var t;
    return function () {
      var args = arguments, ctx = this;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(ctx, args); }, delay);
    };
  };

  /* ---------- category metadata shared across pages ---------- */
  API.CATEGORY_META = {
    attraction: { label: "Attraction", icon: "🎯" },
    museum: { label: "Museum", icon: "🏛️" },
    historic: { label: "Historic site", icon: "🏺" },
    religious: { label: "Religious site", icon: "🛕" },
    park: { label: "Park / nature", icon: "🌳" },
    restaurant: { label: "Restaurant", icon: "🍽️" },
    cafe: { label: "Cafe", icon: "☕" },
    shopping: { label: "Shopping", icon: "🛍️" },
    hotel: { label: "Hotel", icon: "🏨" },
    other: { label: "Place", icon: "📍" },
  };

  window.SarthiAPI = API;
})();
