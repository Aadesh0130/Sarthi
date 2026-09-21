/* =========================================================
   Sārthi — Discovery / Explore engine
   Filters, search, sort + crowd-balancing meters.
   Renders destination cards from the knowledge base.
   ========================================================= */
(function () {
  "use strict";
  var D = window.SARTHI_DATA;

  var filter = { q: "", selectedState: "", region: "", interests: [], budget: "", gemsOnly: false, sort: "recommended" };

  var destinationImages = {
    phawngpui: "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=900&q=85",
    jaipur: "https://images.unsplash.com/photo-1599661046289-e31897846e41?auto=format&fit=crop&w=900&q=85",
    udaipur: "https://images.unsplash.com/photo-1602643163986-7b7a0f8f7f5c?auto=format&fit=crop&w=900&q=85",
    goa: "https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?auto=format&fit=crop&w=900&q=85",
    rishikesh: "https://images.unsplash.com/photo-1531501410720-c8d437636169?auto=format&fit=crop&w=900&q=85",
    varanasi: "https://images.unsplash.com/photo-1561361058-c24cecae35ca?auto=format&fit=crop&w=900&q=85",
    munnar: "https://images.unsplash.com/photo-1602216056096-3b40cc0c9944?auto=format&fit=crop&w=900&q=85",
    hampi: "https://images.unsplash.com/photo-1600100397608-f010f7b82f9b?auto=format&fit=crop&w=900&q=85",
    leh: "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=900&q=85",
    spiti: "https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=900&q=85",
    andaman: "https://images.unsplash.com/photo-1500375592092-40eb2168fd21?auto=format&fit=crop&w=900&q=85",
    ziro: "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=900&q=85",
    gokarna: "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=900&q=85",
    darjeeling: "https://images.unsplash.com/photo-1544735716-392fe2489ffa?auto=format&fit=crop&w=900&q=85",
    kutch: "https://images.unsplash.com/photo-1470214304380-aadaedcfff1b?auto=format&fit=crop&w=900&q=85",
    coorg: "https://images.unsplash.com/photo-1593693397690-362cb9666fc2?auto=format&fit=crop&w=900&q=85",
    meghalaya: "https://images.unsplash.com/photo-1500534623283-312aade485b7?auto=format&fit=crop&w=900&q=85"
  };
  var fallbackImage = "https://images.unsplash.com/photo-1469474968028-56623f02e42e?auto=format&fit=crop&w=900&q=85";
  var hiddenGemImagePool = [
    "https://images.unsplash.com/photo-1473448912268-2022ce9509d8?auto=format&fit=crop&w=900&q=85",
    "https://images.unsplash.com/photo-1500534623283-312aade485b7?auto=format&fit=crop&w=900&q=85",
    "https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=900&q=85",
    "https://images.unsplash.com/photo-1469474968028-56623f02e42e?auto=format&fit=crop&w=900&q=85",
    "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?auto=format&fit=crop&w=900&q=85",
    "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=900&q=85",
    "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=900&q=85",
    "https://images.unsplash.com/photo-1511497584788-876760111969?auto=format&fit=crop&w=900&q=85",
    "https://images.unsplash.com/photo-1519681393784-d120267933ba?auto=format&fit=crop&w=900&q=85",
    "https://images.unsplash.com/photo-1470770841072-f978cf4d019e?auto=format&fit=crop&w=900&q=85"
  ];

  function hiddenGemImage(state, index) {
    var hash = state.split("").reduce(function (total, character) { return total + character.charCodeAt(0); }, 0);
    return hiddenGemImagePool[(hash + index) % hiddenGemImagePool.length];
  }

  function hiddenGemsForState(query) {
    var catalog = window.SARTHI_HIDDEN_GEMS || {};
    var clean = (query || "").trim().toLowerCase();
    if (!clean) return [];
    var states = Object.keys(catalog).filter(function (state) {
      return state.toLowerCase() === clean || state.toLowerCase().indexOf(clean) === 0;
    });
    return states.reduce(function (all, state) {
      var names = catalog[state].split("|");
      return all.concat(names.map(function (name, index) {
        return {
          id: "hidden-" + state.toLowerCase().replace(/[^a-z0-9]+/g, "-") + "-" + index,
          name: name,
          state: state,
          region: "Hidden gem",
          tags: ["hidden gem", "nature", "offbeat"],
          hiddenGem: true,
          popularity: 15 + (index % 28),
          rating: 4.4 + ((index % 6) / 10),
          avgDailyCost: 1400 + ((index % 5) * 350),
          sustainability: 82 + (index % 17),
          experiences: [],
          blurb: "A lesser-known place to discover in " + state + ".",
          image: hiddenGemImage(state, index),
          isHiddenGem: true
        };
      }));
    }, []);
  }

  function crowdClass(p) { return p >= 70 ? "high" : p >= 45 ? "mid" : "low"; }
  function crowdLabel(p, gem) {
    if (gem) return "Hidden gem · peaceful";
    return p >= 80 ? "Very crowded" : p >= 70 ? "Busy" : p >= 45 ? "Moderate" : "Uncrowded";
  }
  function budgetBand(cost) { return cost < 2400 ? "budget" : cost > 3200 ? "luxury" : "comfort"; }
  function budgetLabel(cost) { var b = budgetBand(cost); return b === "budget" ? "Budget-friendly" : b === "luxury" ? "Premium" : "Mid-range"; }

  function apply() {
    if (filter.selectedState) {
      render(hiddenGemsForState(filter.selectedState));
      return;
    }
    var list = D.destinations.filter(function (d) {
      if (filter.q) {
        var hay = (d.name + " " + d.state + " " + d.tags.join(" ") + " " + d.blurb).toLowerCase();
        if (hay.indexOf(filter.q.toLowerCase()) < 0) return false;
      }
      if (filter.region && d.region !== filter.region) return false;
      if (filter.gemsOnly && !d.hiddenGem) return false;
      if (filter.budget && budgetBand(d.avgDailyCost) !== filter.budget) return false;
      if (filter.interests.length) {
        var ok = filter.interests.some(function (t) { return d.tags.indexOf(t) >= 0; });
        if (!ok) return false;
      }
      return true;
    });
    var stateGems = hiddenGemsForState(filter.q);
    if (stateGems.length) list = stateGems;

    list.sort(function (a, b) {
      switch (filter.sort) {
        case "crowd-low": return a.popularity - b.popularity;
        case "crowd-high": return b.popularity - a.popularity;
        case "rating": return b.rating - a.rating;
        case "cost-low": return a.avgDailyCost - b.avgDailyCost;
        case "cost-high": return b.avgDailyCost - a.avgDailyCost;
        default: // recommended = Ranked by Sārthi SmartScore multi-factor engine
          var scoreB = D.calculateSmartScore(b, { interests: filter.interests, budget: filter.budget, avoidCrowds: filter.gemsOnly }).total;
          var scoreA = D.calculateSmartScore(a, { interests: filter.interests, budget: filter.budget, avoidCrowds: filter.gemsOnly }).total;
          return scoreB - scoreA;
      }
    });
    render(list);
  }

  function card(d) {
    var cc = crowdClass(d.popularity);
    var tags = d.tags.slice(0, 3).map(function (t) { return '<span class="tag">' + t + "</span>"; }).join("");
    var badge = "";
    var image = d.image || destinationImages[d.id] || fallbackImage;
    var planUrl = d.isHiddenGem ? "explore.html?q=" + encodeURIComponent(d.name) : "planner.html?dest=" + d.id;

    // Dynamic Sārthi SmartScore for explore card
    var scoreObj = D.calculateSmartScore(d, {
      interests: filter.interests,
      budget: filter.budget,
      avoidCrowds: filter.gemsOnly
    });

    return '' +
      '<article class="dest-card reveal">' +
      '<div class="dest-card__media" style="background-image:linear-gradient(180deg,rgba(5,15,25,.08),rgba(5,15,25,.7)),url(\'' + image + '\')">' +
      badge +
      '<div class="dest-card__loc">' + d.name + "<small>" + d.state + " · " + d.region + " India</small></div>" +
      "</div>" +
      '<div class="dest-card__body">' +
      '<p class="text-2" style="font-size:.92rem">' + d.blurb + "</p>" +
      '<div class="tags">' + tags + "</div>" +
      "<div>" +
      '<div class="meter-row"><span class="label">Crowd level</span><span>' + crowdLabel(d.popularity, d.hiddenGem) + "</span></div>" +
      '<div class="meter meter--' + cc + '"><div class="meter__fill" style="width:' + d.popularity + '%"></div></div>' +
      "</div>" +
      '<div class="dest-card__meta">' +
      '<span>From <b>' + D.inr(d.avgDailyCost) + "</b>/day</span>" +
      '<span>🌱 Eco ' + d.sustainability + "/100</span>" +
      "</div>" +
      '<div class="dest-card__actions">' +
      '<a class="btn btn--primary btn--sm" href="' + planUrl + '">' + (d.isHiddenGem ? "Explore this gem" : "Plan this trip") + '</a>' +
      (d.isHiddenGem ? "" : '<button class="btn btn--ghost btn--sm" data-add="' + d.id + '">+ Stay</button>') +
      "</div>" +
      "</div>" +
      "</article>";
  }

  function render(list) {
    var grid = document.querySelector("[data-dest-grid]");
    var count = document.querySelector("[data-result-count]");
    var showingGems = list.length && list[0].isHiddenGem;
    if (count) count.innerHTML = showingGems ? "Showing <b>" + list.length + "</b> hidden gems for this state" : "Showing <b>" + list.length + "</b> of " + D.destinations.length + " destinations";
    if (!list.length) {
      grid.innerHTML = '<div class="itinerary-empty" style="grid-column:1/-1"><div class="big">🔍</div><b>No destinations match</b><p class="muted">Try clearing a filter or turning off “hidden gems only”.</p></div>';
      return;
    }
    grid.innerHTML = list.map(card).join("");
    grid.querySelectorAll(".reveal").forEach(function (el) { el.classList.add("is-visible"); });
    grid.querySelectorAll("[data-add]").forEach(function (b) {
      b.addEventListener("click", function () {
        var d = D.byId(b.getAttribute("data-add"));
        var h = d.hotels[1] || d.hotels[0];
        window.Sarthi.addToCart({
          key: window.Sarthi.makeKey(["hotel", d.id]),
          type: "hotel", emoji: "🏨",
          name: h.name, meta: d.name + " · " + h.type + " stay / night",
          price: h.pricePerNight
        });
      });
    });
  }

  function initFilters() {
    var search = document.querySelector("#x-search");
    if (search) search.addEventListener("input", function () {
      filter.q = search.value;
      var stateSelect = document.querySelector("#x-state");
      var typedStateGems = hiddenGemsForState(search.value);
      filter.selectedState = typedStateGems.length ? search.value : "";
      if (stateSelect) stateSelect.value = filter.selectedState;
      if (typedStateGems.length) {
        render(typedStateGems);
        return;
      }
      apply();
    });

    var stateSelect = document.querySelector("#x-state");
    if (stateSelect && window.SARTHI_HIDDEN_GEMS) {
      Object.keys(window.SARTHI_HIDDEN_GEMS).sort().forEach(function (state) {
        stateSelect.insertAdjacentHTML("beforeend", '<option value="' + state.replace(/&/g, "&amp;") + '">' + state + '</option>');
      });
      stateSelect.addEventListener("change", function () {
        filter.q = stateSelect.value;
        filter.selectedState = stateSelect.value;
        filter.region = "";
        filter.budget = "";
        filter.interests = [];
        filter.gemsOnly = false;
        var regionSelect = document.querySelector("#x-region");
        var budgetSelect = document.querySelector("#x-budget");
        var gemsCheckbox = document.querySelector("#x-gems");
        if (regionSelect) regionSelect.value = "";
        if (budgetSelect) budgetSelect.value = "";
        if (gemsCheckbox) gemsCheckbox.checked = false;
        document.querySelectorAll("#x-interests .chip").forEach(function (chip) { chip.classList.remove("is-active"); });
        if (search) search.value = stateSelect.value;
        render(hiddenGemsForState(filter.selectedState));
      });
    }

    var region = document.querySelector("#x-region");
    if (region) {
      var ro = '<option value="">All regions</option>';
      D.regions.forEach(function (r) { ro += '<option value="' + r + '">' + r + " India</option>"; });
      region.innerHTML = ro;
      region.addEventListener("change", function () { filter.region = region.value; apply(); });
    }

    var sort = document.querySelector("#x-sort");
    if (sort) sort.addEventListener("change", function () { filter.sort = sort.value; apply(); });

    var chipWrap = document.querySelector("#x-interests");
    if (chipWrap) {
      D.interests.forEach(function (t) {
        var b = document.createElement("button");
        b.className = "chip"; b.textContent = t; b.type = "button";
        b.addEventListener("click", function () {
          var i = filter.interests.indexOf(t);
          if (i >= 0) { filter.interests.splice(i, 1); b.classList.remove("is-active"); }
          else { filter.interests.push(t); b.classList.add("is-active"); }
          apply();
        });
        chipWrap.appendChild(b);
      });
    }

    var budget = document.querySelector("#x-budget");
    if (budget) budget.addEventListener("change", function () { filter.budget = budget.value; apply(); });

    var gems = document.querySelector("#x-gems");
    if (gems) gems.addEventListener("change", function () { filter.gemsOnly = gems.checked; apply(); });

    // deep link ?gems=1 or ?interest=
    var params = new URLSearchParams(location.search);
    if (params.get("gems") === "1" && gems) { gems.checked = true; filter.gemsOnly = true; }
    if (params.get("interest") && chipWrap) {
      var target = params.get("interest");
      chipWrap.querySelectorAll(".chip").forEach(function (c) {
        if (c.textContent === target) { c.classList.add("is-active"); filter.interests.push(target); }
      });
    }

    apply();
  }

  document.addEventListener("DOMContentLoaded", initFilters);
})();
