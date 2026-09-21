/* =========================================================
   Sārthi — AI Trip Planner engine
   Generates a personalised, day-by-day itinerary from the
   destination knowledge base. Deterministic + explainable.
   ========================================================= */
(function () {
  "use strict";
  var D = window.SARTHI_DATA;

  var state = {
    destId: "",
    days: 4,
    budget: "comfort",     // budget | comfort | luxury | custom
    customBudget: 25000,
    travelers: 2,
    pace: "balanced",      // relaxed | balanced | packed
    interests: [],
    avoidCrowds: false
  };

  var SLOT_LABELS = [
    { t: "Morning", s: "8:00 – 12:00" },
    { t: "Afternoon", s: "12:30 – 16:30" },
    { t: "Evening", s: "17:00 – 20:00" },
    { t: "Night", s: "20:30 – 22:30" }
  ];
  var PACE_ACTS = { relaxed: 2, balanced: 3, packed: 4 };
  var FOOD_PER_DAY = { budget: 600, comfort: 1200, luxury: 2500 };
  var LOCAL_TRANSPORT_PER_DAY = { budget: 300, comfort: 700, luxury: 1600 };

  function effectiveBudgetTier() {
    if (state.budget !== "custom") return state.budget;
    var perPersonDay = state.customBudget / Math.max(1, state.days * state.travelers);
    return perPersonDay < 1800 ? "budget" : perPersonDay >= 4200 ? "luxury" : "comfort";
  }

  function syncCustomBudgetVisibility() {
    var wrap = document.querySelector("#budget-input-wrap");
    if (wrap) wrap.hidden = state.budget !== "custom";
  }

  /* seeded pseudo-random so the same inputs give a stable plan,
     but "regenerate" nudges the seed for fresh variety */
  var seedOffset = 0;
  function makeRng(seedStr) {
    var h = 2166136261 ^ seedOffset;
    for (var i = 0; i < seedStr.length; i++) { h = Math.imul(h ^ seedStr.charCodeAt(i), 16777619); }
    return function () {
      h += 0x6D2B79F5; var t = h;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function shuffle(arr, rng) {
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(rng() * (i + 1));
      var tmp = a[i]; a[i] = a[j]; a[j] = tmp;
    }
    return a;
  }

  /* ---------- Destination selection ---------- */
  /* Upgraded to Sārthi SmartScore multi-factor engine */
  function scoreDestination(d) {
    return D.calculateSmartScore(d, state).total;
  }
  function pickBestDestination() {
    var ranked = D.destinations.slice().sort(function (a, b) { return scoreDestination(b) - scoreDestination(a); });
    return ranked[0];
  }

  /* ---------- Cost / score helpers ---------- */
  function hotelFor(dest) {
    return dest.hotels.find(function (h) { return h.type === effectiveBudgetTier(); }) || dest.hotels[1] || dest.hotels[0];
  }
  function greenScore(dest, localCount, hotel) {
    var s = dest.sustainability;
    s += Math.min(localCount * 3, 18);        // rewarding local experiences
    if (hotel.type === "budget") s += 6;       // homestays / hostels lighter footprint
    if (hotel.type === "luxury") s -= 8;
    if (state.avoidCrowds) s += 4;
    return Math.max(0, Math.min(100, Math.round(s)));
  }
  function greenLabel(v) {
    return v >= 80 ? "Excellent" : v >= 65 ? "Great" : v >= 50 ? "Fair" : "Heavy footprint";
  }

  /* ---------- Form & State synchronization ---------- */
  function syncStateFromDOM() {
    var destSel = document.querySelector("#f-dest");
    if (destSel) {
      var val = (destSel.value || "").trim();
      if (val) {
        var matched = D.byId(val);
        state.destId = matched ? matched.id : val;
      } else {
        state.destId = "";
      }
    }

    var daysInput = document.querySelector("#f-days-input");
    if (daysInput && !isNaN(parseInt(daysInput.value, 10))) {
      state.days = Math.max(1, Math.min(14, parseInt(daysInput.value, 10)));
    }

    var travInput = document.querySelector("#f-trav-input");
    if (travInput && !isNaN(parseInt(travInput.value, 10))) {
      state.travelers = Math.max(1, Math.min(12, parseInt(travInput.value, 10)));
    }

    var avoid = document.querySelector("#f-avoid");
    if (avoid) {
      state.avoidCrowds = !!avoid.checked;
    }

    var budgetBtn = document.querySelector("#f-budget button.is-active");
    if (budgetBtn && budgetBtn.getAttribute("data-val")) {
      state.budget = budgetBtn.getAttribute("data-val");
    }
    var customBudget = document.querySelector("#f-budget-amount");
    if (customBudget && !isNaN(Number(customBudget.value))) {
      state.customBudget = Math.max(3000, Number(customBudget.value));
    }
    syncCustomBudgetVisibility();

    var paceBtn = document.querySelector("#f-pace button.is-active");
    if (paceBtn && paceBtn.getAttribute("data-val")) {
      state.pace = paceBtn.getAttribute("data-val");
    }

    var activeChips = document.querySelectorAll("#f-interests .chip.is-active");
    if (activeChips && activeChips.length > 0) {
      state.interests = Array.prototype.slice.call(activeChips).map(function (c) {
        return c.textContent.trim();
      });
    }
  }

  /* ---------- Itinerary builder ---------- */
  function build() {
    // 1. Sync all form states from DOM
    syncStateFromDOM();

    var dest = null;
    var isDiscoveryMode = false;

    // 2. Explicit destination selection: If user picked a destination, it MUST be used.
    if (state.destId) {
      dest = D.byId(state.destId);
    }

    // 3. Recommendation/Discovery mode ("Surprise me"):
    // SmartScore ranks destinations ONLY when no explicit destination is selected (or invalid).
    if (!dest) {
      dest = pickBestDestination();
      isDiscoveryMode = true;
    }

    // Never replace the user's explicit choice. Keep state.destId normalized.
    // If in discovery mode, do NOT permanently overwrite state.destId so subsequent filter
    // changes remain in dynamic discovery mode until user explicitly picks a destination.
    if (!isDiscoveryMode) {
      state.destId = dest.id;
      var destSel = document.querySelector("#f-dest");
      if (destSel && destSel.value !== dest.id) {
        destSel.value = dest.id;
      }
    }

    var rng = makeRng(dest.id + state.days + state.pace + state.budget + state.interests.join(""));

    var perDay = PACE_ACTS[state.pace];
    // pool: attractions first (prefer interest matches), then local experiences interleaved
    var atts = shuffle(dest.attractions, rng);
    // bias interest-matching attractions to the front
    atts.sort(function (a, b) {
      var am = state.interests.indexOf(a.type) >= 0 ? 1 : 0;
      var bm = state.interests.indexOf(b.type) >= 0 ? 1 : 0;
      return bm - am;
    });
    var exps = shuffle(dest.experiences, rng);

    var pool = [];
    var ai = 0, ei = 0;
    // interleave ~1 local experience every ~2 activities to boost local economy
    var total = state.days * perDay;
    for (var k = 0; k < total; k++) {
      var useExp = (k % 3 === 2) && ei < exps.length;
      if (useExp) { pool.push(wrapExp(exps[ei++])); }
      else if (ai < atts.length) { pool.push(wrapAtt(atts[ai++])); }
      else if (ei < exps.length) { pool.push(wrapExp(exps[ei++])); }
      else { // recycle attractions if we run out (long trips), tag as leisure
        var recy = atts[ai % atts.length]; ai++;
        pool.push(wrapAtt(recy, true));
      }
    }

    // distribute into days
    var days = [];
    var idx = 0;
    for (var day = 0; day < state.days; day++) {
      var slots = [];
      for (var sPos = 0; sPos < perDay; sPos++) {
        if (idx >= pool.length) break;
        var item = pool[idx++];
        item.slot = SLOT_LABELS[Math.min(sPos, SLOT_LABELS.length - 1)];
        slots.push(item);
      }
      days.push({ title: dayTitle(day, state.days, slots, dest), slots: slots });
    }

    var localCount = pool.filter(function (p) { return p.local; }).length;
    var hotel = hotelFor(dest);
    var nights = Math.max(1, state.days - 1);
    var rooms = Math.max(1, Math.ceil(state.travelers / 2));

    var actCost = pool.reduce(function (s, p) { return s + (p.cost || 0); }, 0) * state.travelers;
    var stayCost = hotel.pricePerNight * nights * rooms;
    var budgetTier = effectiveBudgetTier();
    var foodCost = FOOD_PER_DAY[budgetTier] * state.days * state.travelers;
    var transCost = LOCAL_TRANSPORT_PER_DAY[budgetTier] * state.days;
    var total$ = actCost + stayCost + foodCost + transCost;

    var green = greenScore(dest, localCount, hotel);
    var localSpend = pool.filter(function (p) { return p.local; }).reduce(function (s, p) { return s + p.cost; }, 0) * state.travelers + Math.round(stayCost * (hotel.type === "budget" ? 0.7 : 0.35));

    // Calculate Sārthi SmartScore and check for Smart Alternative
    var smartScore = D.calculateSmartScore(dest, state);
    var smartAlt = D.findSmartAlternative(dest, state);

    return {
      dest: dest, days: days, hotel: hotel, nights: nights, rooms: rooms,
      cost: { activities: actCost, stay: stayCost, food: foodCost, transport: transCost, total: total$ },
      green: green, greenLabel: greenLabel(green),
      localCount: localCount, localSpend: localSpend,
      smartScore: smartScore,
      smartAlt: smartAlt,
      alt: smartAlt ? smartAlt.destination : null
    };
  }

  function wrapAtt(a, leisure) {
    return {
      name: a.name, type: a.type, hrs: a.hrs, cost: a.cost, local: false, eco: false, leisure: !!leisure,
      desc: leisure ? "Revisit a favourite / free leisure time" : capitalize(a.type) + " · about " + a.hrs + " hrs"
    };
  }
  function wrapExp(e) {
    return {
      name: e.name, type: "experience", hrs: 2.5, cost: e.price, local: !!e.local, eco: !!e.eco,
      desc: "Local experience" + (e.eco ? " · community-run" : "")
    };
  }

  function dayTitle(i, n, slots, dest) {
    if (i === 0) return "Arrival & first impressions";
    if (i === n - 1) return "Farewell & last stops";
    var themes = slots.map(function (s) { return s.type; });
    if (themes.indexOf("adventure") >= 0) return "Adventure day";
    if (themes.indexOf("spiritual") >= 0) return "Culture & calm";
    if (themes.indexOf("nature") >= 0) return "Into nature";
    if (themes.indexOf("beach") >= 0) return "Coast & leisure";
    return "Explore " + dest.name;
  }

  function capitalize(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

  /* Helper for 6-factor SmartScore progress bar */
  function factorBar(title, score, max, pct, label) {
    return '<div class="factor-card">' +
      '<div class="factor-card__top">' +
      '<span class="factor-card__title">' + title + '</span>' +
      '<b class="factor-card__score">' + score + '/' + max + ' pts</b>' +
      '</div>' +
      '<div class="factor-bar"><div class="factor-bar__fill" style="width:' + Math.min(100, Math.max(0, pct)) + '%"></div></div>' +
      '<div class="factor-card__lbl">' + label + '</div>' +
      '</div>';
  }

  /* ---------- Rendering ---------- */
  function render(plan) {
    var dest = plan.dest;
    var out = document.querySelector("[data-itinerary]");

    var tilesHtml =
      tile("SmartScore", plan.smartScore.total + "/100") +
      tile("Est. total", D.inr(plan.cost.total)) +
      tile("GreenTrip", plan.green + "/100") +
      tile("Local hosts", plan.localCount + " included");

    var heroStyle = "background:linear-gradient(130deg," + dest.grad[0] + "," + dest.grad[1] + ")";
    var hero =
      '<div class="trip-hero" style="' + heroStyle + '">' +
      '<div style="font-size:2.4rem">' + dest.emoji + "</div>" +
      "<h2>" + state.days + " days in " + dest.name + "</h2>" +
      '<div class="loc">' + dest.state + " · " + dest.region + " India · best in " + dest.bestSeason + "</div>" +
      '<div class="trip-tiles">' + tilesHtml + "</div>" +
      "</div>";

    // "Why Sārthi recommended this?" section
    var b = plan.smartScore.breakdown;
    var whyHtml =
      '<div class="why-rec reveal">' +
      '<div class="why-rec__head">' +
      '<div class="why-rec__badge score-' + plan.smartScore.scoreLevel + '">' +
      '<span class="why-rec__num">' + plan.smartScore.total + '</span>' +
      '<span class="why-rec__denom">/100</span>' +
      '<span class="why-rec__level">SmartScore</span>' +
      '</div>' +
      '<div class="why-rec__intro">' +
      '<span class="eyebrow" style="margin-bottom:4px">💡 Explainable Recommendation</span>' +
      '<h3 style="font-family:var(--font-head);margin-bottom:6px;font-size:1.25rem">Why Sārthi recommended ' + dest.name + '?</h3>' +
      '<p class="why-rec__expl">' + plan.smartScore.explanation + '</p>' +
      '</div>' +
      '</div>' +
      '<div class="why-rec__grid">' +
      factorBar("🎯 Preference Match (30%)", b.preferenceMatch.score, b.preferenceMatch.max, b.preferenceMatch.pct, b.preferenceMatch.label) +
      factorBar("💰 Budget Fit (20%)", b.budgetFit.score, b.budgetFit.max, b.budgetFit.pct, b.budgetFit.label) +
      factorBar("⚖️ Crowd Balance (15%)", b.crowdBalance.score, b.crowdBalance.max, b.crowdBalance.pct, b.crowdBalance.label) +
      factorBar("🌱 Sustainability (15%)", b.sustainability.score, b.sustainability.max, b.sustainability.pct, b.sustainability.label) +
      factorBar("🤝 Local Impact (10%)", b.localEconomicImpact.score, b.localEconomicImpact.max, b.localEconomicImpact.pct, b.localEconomicImpact.label) +
      factorBar("★ Rating (10%)", b.rating.score, b.rating.max, b.rating.pct, b.rating.label) +
      '</div>' +
      '</div>';

    // Smart Alternative Comparison card (when popularity >= 75)
    var smartAltHtml = "";
    if (plan.smartAlt) {
      var altDest = plan.smartAlt.destination;
      smartAltHtml =
        '<div class="smart-alt-card reveal">' +
        '<div class="smart-alt__badge">🌿 Sārthi Smart Alternative</div>' +
        '<div class="smart-alt__heading">' +
        '<h4>High crowd pressure detected at ' + dest.name + ' (' + dest.popularity + '% crowd index)</h4>' +
        '<p class="muted">Looking for a calmer, more sustainable trip with similar highlights? Sārthi recommends this balanced alternative:</p>' +
        '</div>' +
        '<div class="smart-alt__table">' +
        '<div class="alt-col alt-col--current">' +
        '<span class="alt-col__tag">Selected Destination</span>' +
        '<div class="alt-col__name">' + dest.emoji + ' ' + dest.name + '</div>' +
        '<div class="alt-stat"><span class="lbl">Crowd</span><b class="val crowd-high">' + dest.popularity + '%</b></div>' +
        '<div class="alt-stat"><span class="lbl">Avg Cost</span><b>' + D.inr(dest.avgDailyCost) + '/day</b></div>' +
        '<div class="alt-stat"><span class="lbl">Eco</span><b>' + dest.sustainability + '/100</b></div>' +
        '</div>' +
        '<div class="alt-arrow">' +
        '<div class="arrow-sym">↓</div>' +
        '<span class="smart-tag">Smart Alternative</span>' +
        '<div class="diff-chips">' +
        '<span class="diff-chip crowd">−' + plan.smartAlt.crowdRelief + '% crowd</span>' +
        (plan.smartAlt.costDiff > 0 ? '<span class="diff-chip cost">Save ' + D.inr(plan.smartAlt.costDiff) + '/day</span>' : '') +
        (plan.smartAlt.sustDiff > 0 ? '<span class="diff-chip eco">+' + plan.smartAlt.sustDiff + ' Eco</span>' : '') +
        '</div>' +
        '</div>' +
        '<div class="alt-col alt-col--suggested">' +
        '<span class="alt-col__tag reco">Recommended Balance</span>' +
        '<div class="alt-col__name">' + altDest.emoji + ' ' + altDest.name + '</div>' +
        '<div class="alt-stat"><span class="lbl">Crowd</span><b class="val crowd-low">' + altDest.popularity + '%</b></div>' +
        '<div class="alt-stat"><span class="lbl">Avg Cost</span><b>' + D.inr(altDest.avgDailyCost) + '/day</b></div>' +
        '<div class="alt-stat"><span class="lbl">Eco</span><b>' + altDest.sustainability + '/100</b></div>' +
        '</div>' +
        '</div>' +
        '<div class="smart-alt__reason">' +
        '<b>Reason:</b> “' + plan.smartAlt.reason + '”' +
        '</div>' +
        '<div class="smart-alt__cta">' +
        '<button type="button" class="btn btn--primary btn--sm" data-switch-alt="' + altDest.id + '">' +
        '✨ Switch to ' + altDest.name + ' &amp; Replan' +
        '</button>' +
        '</div>' +
        '</div>';
    }

    // insights
    var insights = '<div class="insight-row">';
    insights += insight("local", "🤝", "Boosts local livelihoods",
      "Your plan routes about <b>" + D.inr(plan.localSpend) + "</b> to local guides, homestays & artisans through " + plan.localCount + " community experiences.");
    insights += insight("eco", "🌱", "GreenTrip score: " + plan.green + "/100 (" + plan.greenLabel + ")",
      "Based on the destination's sustainability, your stay type and community-run activities. Lighter stays raise it.");
    if (plan.alt) {
      insights += insight("crowd", "⚖️", dest.name + " gets busy (" + dest.popularity + "% crowd index)",
        "Travelling in shoulder season helps. Prefer calm? Try nearby <b>" + plan.alt.name + "</b> — a hidden gem at only " + plan.alt.popularity + "% crowd.");
    } else {
      insights += insight("crowd", "🧭", "Well-balanced choice",
        dest.name + " sits at a comfortable " + dest.popularity + "% crowd index — you'll enjoy it without the crush.");
    }
    insights += "</div>";

    // days
    var daysHtml = "";
    plan.days.forEach(function (d, i) {
      var slots = "";
      var dayCost = 0;
      d.slots.forEach(function (s) {
        dayCost += s.cost * state.travelers;
        var tags = "";
        if (s.local) tags += '<span class="pill local">Local host</span>';
        if (s.eco) tags += '<span class="pill eco">Eco</span>';
        if (!s.local && !s.leisure) tags += '<span class="pill">' + capitalize(s.type) + "</span>";
        slots +=
          '<div class="slot">' +
          '<div class="slot__time">' + s.slot.t + "<span>" + s.slot.s + "</span></div>" +
          '<div class="slot__body"><b>' + s.name + "</b>" +
          '<div class="desc">' + s.desc + "</div>" +
          '<div class="slot__tags">' + tags + "</div>" +
          "</div>" +
          '<div class="slot__cost">' + (s.cost ? D.inr(s.cost * state.travelers) : "Free") + "</div>" +
          "</div>";
      });
      daysHtml +=
        '<div class="day reveal">' +
        '<div class="day__head">' +
        '<div class="day__num"><small>DAY</small>' + (i + 1) + "</div>" +
        '<div class="day__title">' + d.title + "</div>" +
        '<div class="day__meta">' + d.slots.length + " stops · " + D.inr(dayCost) + "</div>" +
        "</div>" + slots +
        "</div>";
    });

    // stay
    var stay =
      '<div class="stay-card reveal">' +
      '<div class="ico">🏨</div>' +
      "<div><b>" + plan.hotel.name + "</b><div class=\"muted\" style=\"font-size:.88rem\">" +
      capitalize(plan.hotel.type) + " stay · ★ " + plan.hotel.rating + " · " + plan.nights + " nights · " + plan.rooms + " room(s)</div></div>" +
      '<div class="price"><b>' + D.inr(plan.hotel.pricePerNight) + '</b><div class="muted" style="font-size:.8rem">/ night</div></div>' +
      "</div>";

    // cost breakdown
    var costRows =
      row("Stay (" + plan.nights + " nights)", plan.cost.stay) +
      row("Activities & experiences", plan.cost.activities) +
      row("Food (est.)", plan.cost.food) +
      row("Local transport", plan.cost.transport);
    var costCard =
      '<div class="day reveal"><div class="day__head"><div class="day__title">💰 Estimated budget</div>' +
      '<div class="day__meta">' + state.travelers + " traveller(s)</div></div>" + costRows +
      '<div class="slot" style="border-top:2px solid var(--border)"><div class="slot__body"><b>Total trip cost</b>' +
      '<div class="desc">All-in estimate · ' + D.inr(plan.cost.total / state.travelers) + " per person</div></div>" +
      '<div class="slot__cost" style="color:var(--brand-600);font-size:1.2rem">' + D.inr(plan.cost.total) + "</div></div></div>";

    // actions
    var actions =
      '<div class="result-actions">' +
      '<button class="btn btn--primary" data-book-trip>🧳 Add whole trip to bookings</button>' +
      '<button class="btn btn--ghost" data-regen>🔄 Regenerate</button>' +
      '<button class="btn btn--outline" data-print>🖨️ Save / print</button>' +
      "</div>";

    out.innerHTML = hero + whyHtml + smartAltHtml + insights +
      '<h3 style="font-family:var(--font-head);margin:6px 0 14px;font-size:1.3rem">🗺️ Your day-by-day plan</h3>' +
      daysHtml + '<h3 style="font-family:var(--font-head);margin:20px 0 14px;font-size:1.3rem">🏨 Where you\'ll stay</h3>' +
      stay + costCard + actions;

    // wire actions
    out.querySelector("[data-regen]").addEventListener("click", function () { seedOffset++; regenerate(); });
    out.querySelector("[data-print]").addEventListener("click", function () { window.print(); });
    out.querySelector("[data-book-trip]").addEventListener("click", function () {
      window.Sarthi.addToCart({
        key: window.Sarthi.makeKey(["trip", dest.id, state.days]),
        type: "trip", emoji: "🧭",
        name: state.days + "-day " + dest.name + " trip",
        meta: plan.hotel.name + " · " + plan.localCount + " local experiences",
        price: Math.round(plan.cost.total * 1.05)
      });
      window.Sarthi.openDrawer();
    });

    // Wire Smart Alternative switch button
    var switchBtn = out.querySelector("[data-switch-alt]");
    if (switchBtn) {
      switchBtn.addEventListener("click", function () {
        var altId = switchBtn.getAttribute("data-switch-alt");
        var altObj = D.byId(altId);
        if (!altObj) return;
        state.destId = altId;
        var destSel = document.querySelector("#f-dest");
        if (destSel) destSel.value = altId;
        if (window.Sarthi && window.Sarthi.toast) {
          window.Sarthi.toast("Switched to " + altObj.name + "! Itinerary updated.", "🌿");
        }
        regenerate();
      });
    }

    // reveal newly-added
    out.querySelectorAll(".reveal").forEach(function (el) { el.classList.add("is-visible"); });
    // persist
    try { localStorage.setItem("sarthi.lastPlan", JSON.stringify(state)); } catch (e) { }
    // scroll to result on small screens
    if (window.innerWidth < 980) out.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function tile(label, val) { return '<div class="trip-tile"><span>' + label + "</span><b>" + val + "</b></div>"; }
  function insight(cls, em, title, body) {
    return '<div class="insight ' + cls + '"><div class="em">' + em + "</div><div><b>" + title + "</b><p>" + body + "</p></div></div>";
  }
  function row(label, val) {
    return '<div class="slot"><div class="slot__body"><b style="font-weight:600;font-family:var(--font-body)">' + label +
      '</b></div><div class="slot__cost">' + D.inr(val) + "</div></div>";
  }

  function regenerate() {
    syncStateFromDOM();
    render(build());
  }

  /* ---------- Form wiring ---------- */
  function initForm() {
    var destSel = document.querySelector("#f-dest");
    if (!destSel) return;

    // populate destinations
    var opts = '<option value="">✨ Surprise me (AI picks best match)</option>';
    D.destinations.slice().sort(function (a, b) { return a.name.localeCompare(b.name); }).forEach(function (d) {
      opts += '<option value="' + d.id + '">' + d.emoji + " " + d.name + " · " + d.state + "</option>";
    });
    destSel.innerHTML = opts;

    // preselect via ?dest=
    var params = new URLSearchParams(location.search);
    var destParam = params.get("dest");
    if (destParam) {
      var matchedParam = D.byId(destParam);
      if (matchedParam) {
        destSel.value = matchedParam.id;
        state.destId = matchedParam.id;
      }
    } else {
      // Sync in case browser restored form state from cache/refresh
      if (destSel.value) {
        var matchedRestored = D.byId(destSel.value);
        if (matchedRestored) {
          destSel.value = matchedRestored.id;
          state.destId = matchedRestored.id;
        }
      }
    }

    // Listen to changes on destination select (both change and input)
    destSel.addEventListener("change", function () {
      syncStateFromDOM();
    });
    destSel.addEventListener("input", function () {
      syncStateFromDOM();
    });

    // interests chips
    var chipWrap = document.querySelector("#f-interests");
    if (chipWrap) {
      chipWrap.innerHTML = "";
      D.interests.forEach(function (tag) {
        var b = document.createElement("button");
        b.type = "button"; b.className = "chip"; b.textContent = tag;
        b.addEventListener("click", function () {
          var i = state.interests.indexOf(tag);
          if (i >= 0) { state.interests.splice(i, 1); b.classList.remove("is-active"); }
          else { state.interests.push(tag); b.classList.add("is-active"); }
        });
        chipWrap.appendChild(b);
      });
    }

    // segmented controls
    wireSegmented("#f-budget", function (v) {
      state.budget = v;
      syncCustomBudgetVisibility();
    });
    wireSegmented("#f-pace", function (v) { state.pace = v; });

    var customBudgetInput = document.querySelector("#f-budget-amount");
    if (customBudgetInput) customBudgetInput.addEventListener("input", function () {
      state.customBudget = Math.max(3000, Number(customBudgetInput.value) || 3000);
    });

    // days + travelers steppers
    wireStepper("#f-days", 1, 14, function (v) { state.days = v; });
    wireStepper("#f-travelers", 1, 12, function (v) { state.travelers = v; });

    // avoid crowds
    var avoid = document.querySelector("#f-avoid");
    if (avoid) avoid.addEventListener("change", function () { state.avoidCrowds = avoid.checked; });

    // Initial sync from DOM
    syncStateFromDOM();

    // generate button
    var genBtn = document.querySelector("[data-generate]");
    if (genBtn) {
      genBtn.addEventListener("click", function () {
        syncStateFromDOM();
        seedOffset = 0;
        regenerate();
      });
    }

    // auto-generate if arriving with a destination preselected
    if (destParam) {
      setTimeout(function () {
        syncStateFromDOM();
        regenerate();
      }, 150);
    }
  }

  function wireSegmented(sel, cb) {
    var wrap = document.querySelector(sel);
    if (!wrap) return;
    wrap.querySelectorAll("button").forEach(function (b) {
      b.addEventListener("click", function () {
        wrap.querySelectorAll("button").forEach(function (x) { x.classList.remove("is-active"); });
        b.classList.add("is-active");
        cb(b.getAttribute("data-val"));
      });
    });
  }
  function wireStepper(sel, min, max, cb) {
    var wrap = document.querySelector(sel);
    if (!wrap) return;
    var input = wrap.querySelector("input");
    var clamp = function (v) { return Math.max(min, Math.min(max, v)); };
    wrap.querySelector("[data-dec]").addEventListener("click", function () { input.value = clamp(+input.value - 1); cb(+input.value); });
    wrap.querySelector("[data-inc]").addEventListener("click", function () { input.value = clamp(+input.value + 1); cb(+input.value); });
    input.addEventListener("change", function () { input.value = clamp(+input.value || min); cb(+input.value); });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initForm);
  } else {
    initForm();
  }
})();
