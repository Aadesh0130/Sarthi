/* =========================================================
   Sārthi — shared behaviour
   Nav, theme, scroll-reveal, cart/bookings drawer, toasts.
   Exposes a small window.Sarthi API used by other scripts.
   ========================================================= */
(function () {
  "use strict";
  var LS_THEME = "sarthi.theme";
  var LS_CART = "sarthi.cart";

  /* ---------- Theme ---------- */
  function initTheme() {
    var saved = localStorage.getItem(LS_THEME);
    var prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    var theme = saved || (prefersDark ? "dark" : "light");
    document.documentElement.setAttribute("data-theme", theme);
  }
  function toggleTheme() {
    var cur = document.documentElement.getAttribute("data-theme");
    var next = cur === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem(LS_THEME, next);
  }

  /* ---------- Nav ---------- */
  function initNav() {
    var nav = document.querySelector(".nav");
    if (nav) {
      var onScroll = function () { nav.classList.toggle("is-scrolled", window.scrollY > 8); };
      onScroll();
      window.addEventListener("scroll", onScroll, { passive: true });
    }
    var toggle = document.querySelector(".nav__toggle");
    var links = document.querySelector(".nav__links");
    if (toggle && links) {
      toggle.addEventListener("click", function () { links.classList.toggle("is-open"); });
      links.querySelectorAll("a").forEach(function (a) {
        a.addEventListener("click", function () { links.classList.remove("is-open"); });
      });
    }
    var themeBtn = document.querySelector("[data-theme-toggle]");
    if (themeBtn) themeBtn.addEventListener("click", toggleTheme);
  }

  /* ---------- Scroll reveal ---------- */
  function initReveal() {
    var els = document.querySelectorAll(".reveal");
    if (!("IntersectionObserver" in window)) {
      els.forEach(function (el) { el.classList.add("is-visible"); });
      return;
    }
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("is-visible"); io.unobserve(e.target); }
      });
    }, { threshold: 0.12 });
    els.forEach(function (el) { io.observe(el); });
  }

  /* ---------- Toast ---------- */
  var toastWrap;
  function toast(msg, emoji) {
    if (!toastWrap) {
      toastWrap = document.createElement("div");
      toastWrap.className = "toast-wrap";
      document.body.appendChild(toastWrap);
    }
    var t = document.createElement("div");
    t.className = "toast";
    t.innerHTML = '<span class="em">' + (emoji || "✅") + "</span>" + msg;
    toastWrap.appendChild(t);
    setTimeout(function () {
      t.style.transition = "opacity .3s, transform .3s";
      t.style.opacity = "0";
      t.style.transform = "translateY(10px)";
      setTimeout(function () { t.remove(); }, 300);
    }, 2400);
  }

  /* ---------- Cart / Bookings ---------- */
  var cart = [];
  function loadCart() {
    try { cart = JSON.parse(localStorage.getItem(LS_CART)) || []; }
    catch (e) { cart = []; }
  }
  function saveCart() { localStorage.setItem(LS_CART, JSON.stringify(cart)); }

  function cartCount() { return cart.reduce(function (n, i) { return n + (i.qty || 1); }, 0); }
  function cartTotal() { return cart.reduce(function (s, i) { return s + i.price * (i.qty || 1); }, 0); }

  function addToCart(item) {
    var existing = cart.find(function (i) { return i.key === item.key; });
    if (existing) { existing.qty = (existing.qty || 1) + 1; }
    else { item.qty = 1; cart.push(item); }
    saveCart(); renderCart(); updateBadges();
    toast(item.name + " added to your trip", item.emoji || "🧳");
  }
  function removeFromCart(key) {
    cart = cart.filter(function (i) { return i.key !== key; });
    saveCart(); renderCart(); updateBadges();
  }

  function updateBadges() {
    document.querySelectorAll("[data-cart-count]").forEach(function (el) {
      var c = cartCount();
      el.textContent = c;
      el.setAttribute("data-count", c);
    });
  }

  function iconFor(type) {
    return type === "hotel" ? "🏨" : type === "trip" ? "🧭" : type === "experience" ? "🎒" : "📍";
  }

  function renderCart() {
    var body = document.querySelector("[data-cart-body]");
    var foot = document.querySelector("[data-cart-foot]");
    if (!body) return;
    if (!cart.length) {
      body.innerHTML = '<div class="cart-empty"><div class="big">🧳</div><p><b>Your trip is empty</b></p>' +
        '<p class="muted">Add stays, experiences or a full AI itinerary to see them here.</p></div>';
      if (foot) foot.innerHTML = "";
      return;
    }
    var html = "";
    cart.forEach(function (i) {
      html += '<div class="cart-item">' +
        '<div class="ci-ico">' + (i.emoji || iconFor(i.type)) + "</div>" +
        '<div class="ci-body"><b>' + i.name + "</b><span>" + (i.meta || "") +
        (i.qty > 1 ? " · ×" + i.qty : "") + "</span></div>" +
        '<div class="ci-price">' + SARTHI_DATA.inr(i.price * (i.qty || 1)) + "</div>" +
        '<button class="ci-remove" data-remove="' + i.key + '" aria-label="Remove">×</button>' +
        "</div>";
    });
    body.innerHTML = html;
    body.querySelectorAll("[data-remove]").forEach(function (b) {
      b.addEventListener("click", function () { removeFromCart(b.getAttribute("data-remove")); });
    });
    if (foot) {
      foot.innerHTML =
        '<div class="summary-line"><span>Subtotal</span><span>' + SARTHI_DATA.inr(cartTotal()) + "</span></div>" +
        '<div class="summary-line"><span>Taxes & fees (est.)</span><span>' + SARTHI_DATA.inr(cartTotal() * 0.05) + "</span></div>" +
        '<div class="summary-line total"><span>Total</span><span>' + SARTHI_DATA.inr(cartTotal() * 1.05) + "</span></div>" +
        '<button class="btn btn--primary btn--block btn--lg" data-checkout style="margin-top:14px">Confirm booking</button>' +
        '<p class="muted center" style="font-size:.78rem;margin-top:10px">Prototype demo — no real payment is taken.</p>';
      foot.querySelector("[data-checkout]").addEventListener("click", checkout);
    }
  }

  /* ---------- Drawer open/close ---------- */
  function openDrawer() {
    document.querySelector("[data-drawer]").classList.add("is-open");
    document.querySelector("[data-overlay]").classList.add("is-open");
    document.body.style.overflow = "hidden";
  }
  function closeDrawer() {
    document.querySelector("[data-drawer]").classList.remove("is-open");
    document.querySelector("[data-overlay]").classList.remove("is-open");
    document.body.style.overflow = "";
  }

  function checkout() {
    if (!cart.length) return;
    var modal = document.querySelector("[data-modal]");
    modal.querySelector("[data-modal-body]").innerHTML =
      '<div class="big">🎉</div><h3>Trip booked!</h3>' +
      '<p class="muted">Your ' + cartCount() + "-item itinerary totalling <b>" + SARTHI_DATA.inr(cartTotal() * 1.05) +
      "</b> is confirmed. A voucher would now be emailed with your local hosts' contacts.</p>" +
      '<button class="btn btn--primary btn--block" data-modal-close style="margin-top:20px">Done</button>';
    modal.classList.add("is-open");
    modal.querySelector("[data-modal-close]").addEventListener("click", function () {
      modal.classList.remove("is-open");
      cart = []; saveCart(); renderCart(); updateBadges(); closeDrawer();
    });
    // celebratory
    toast("Booking confirmed", "🎉");
  }

  function initDrawer() {
    var openBtn = document.querySelector("[data-cart-open]");
    var closeBtn = document.querySelector("[data-cart-close]");
    var overlay = document.querySelector("[data-overlay]");
    if (openBtn) openBtn.addEventListener("click", openDrawer);
    if (closeBtn) closeBtn.addEventListener("click", closeDrawer);
    if (overlay) overlay.addEventListener("click", closeDrawer);
    var modal = document.querySelector("[data-modal]");
    if (modal) modal.addEventListener("click", function (e) { if (e.target === modal) modal.classList.remove("is-open"); });
    renderCart();
  }

  /* ---------- Home destination search ---------- */
  function setHeroDestination(dest) {
    if (!dest) return;
    var hero = document.querySelector(".hero--destination");
    if (!hero) return;

    var imageMap = {
      jaipur: "https://images.unsplash.com/photo-1587474260584-136574528ed5?auto=format&fit=crop&w=1600&q=80",
      udaipur: "https://images.unsplash.com/photo-1516483638261-f4dbaf036963?auto=format&fit=crop&w=1600&q=80",
      goa: "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1600&q=80",
      rishikesh: "https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=1600&q=80",
      varanasi: "https://images.unsplash.com/photo-1548013146-72479768bada?auto=format&fit=crop&w=1600&q=80",
      munnar: "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1600&q=80",
      hampi: "https://images.unsplash.com/photo-1469474968028-56623f02e42e?auto=format&fit=crop&w=1600&q=80",
      leh: "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=1600&q=80",
      spiti: "https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=1600&q=80",
      andaman: "https://images.unsplash.com/photo-1500375592092-40eb2168fd21?auto=format&fit=crop&w=1600&q=80",
      ziro: "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=1600&q=80",
      gokarna: "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1600&q=80",
      darjeeling: "https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=1600&q=80",
      kutch: "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1600&q=80",
      coorg: "https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=1600&q=80",
      meghalaya: "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1600&q=80"
    };

    var start = dest.grad && dest.grad[0] ? dest.grad[0] : "#102d43";
    var end = dest.grad && dest.grad[1] ? dest.grad[1] : "#0f172a";
    var imageUrl = imageMap[dest.id] || "https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=1600&q=80";

    hero.style.background = "linear-gradient(135deg, rgba(4,18,30,.62), rgba(4,18,30,.18)), url('" + imageUrl + "') center/cover no-repeat, linear-gradient(135deg, " + start + " 0%, " + end + " 100%)";
    hero.style.backgroundBlendMode = "normal, normal, normal";
    hero.style.backgroundSize = "cover";
    hero.style.backgroundPosition = "center";
  }

  function initHomeDestinationSearch() {
    var form = document.querySelector("[data-home-search]");
    if (!form) return;
    var input = form.querySelector("[data-home-search-input]");
    var suggestions = form.querySelector("[data-home-suggestions]");
    var clearBtn = form.querySelector("[data-home-search-clear]");
    if (!input || !suggestions) return;

    function matches(q) {
      var query = (q || "").trim().toLowerCase();
      if (!query) return [];
      var data = window.SARTHI_DATA && window.SARTHI_DATA.destinations ? window.SARTHI_DATA.destinations : [];
      return data.filter(function (dest) {
        var haystack = [dest.name, dest.state, dest.id, dest.tags.join(" ")].join(" ").toLowerCase();
        return haystack.indexOf(query) !== -1;
      }).slice(0, 6);
    }

    function renderSuggestions(query) {
      var list = matches(query);
      if (!list.length) {
        suggestions.innerHTML = "";
        suggestions.classList.remove("is-open");
        return;
      }
      suggestions.innerHTML = list.map(function (dest) {
        return '<button type="button" class="destination-suggestion" data-destination-id="' + dest.id + '"><span class="destination-suggestion__icon">' + (dest.emoji || "📍") + '</span><span><strong>' + dest.name + '</strong><small>' + dest.state + '</small></span></button>';
      }).join("");
      suggestions.classList.add("is-open");
    }

    function selectDestination(dest) {
      if (!dest) return;
      input.value = dest.name;
      suggestions.classList.remove("is-open");
      setHeroDestination(dest);
      var href = "planner.html?dest=" + encodeURIComponent(dest.id);
      form.setAttribute("data-selected-destination", dest.id);
      form.setAttribute("data-next-url", href);
    }

    input.addEventListener("input", function (e) {
      renderSuggestions(e.target.value);
    });

    input.addEventListener("focus", function () {
      renderSuggestions(input.value);
    });

    clearBtn.addEventListener("click", function () {
      input.value = "";
      suggestions.innerHTML = "";
      suggestions.classList.remove("is-open");
      input.focus();
    });

    suggestions.addEventListener("click", function (event) {
      var btn = event.target.closest("[data-destination-id]");
      if (!btn) return;
      var dest = window.SARTHI_DATA.byId(btn.getAttribute("data-destination-id"));
      if (dest) selectDestination(dest);
    });

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var query = (input.value || "").trim();
      var found = matches(query)[0];
      if (found) {
        selectDestination(found);
      } else if (query) {
        window.location.href = "explore.html?q=" + encodeURIComponent(query);
      }
    });

    document.addEventListener("click", function (event) {
      if (!form.contains(event.target)) {
        suggestions.classList.remove("is-open");
      }
    });

    // Default to a featured destination on first load for a polished feel.
    var defaultDest = window.SARTHI_DATA.byId("spiti") || window.SARTHI_DATA.destinations[0];
    if (defaultDest) setHeroDestination(defaultDest);
  }

  /* ---------- Public API ---------- */
  window.Sarthi = {
    addToCart: addToCart,
    openDrawer: openDrawer,
    toast: toast,
    // build a stable key so duplicates merge
    makeKey: function (parts) { return parts.join("|").toLowerCase().replace(/\s+/g, "-"); }
  };

  /* ---------- Boot ---------- */
  initTheme();
  document.addEventListener("DOMContentLoaded", function () {
    initNav();
    initReveal();
    initHomeDestinationSearch();
    loadCart();
    initDrawer();
    updateBadges();
    // set active nav link by filename
    var page = (location.pathname.split("/").pop() || "index.html");
    document.querySelectorAll(".nav__link").forEach(function (a) {
      var href = a.getAttribute("href");
      if (href === page || (page === "" && href === "index.html")) a.classList.add("is-active");
    });
    // footer year
    var y = document.querySelector("[data-year]");
    if (y) y.textContent = new Date().getFullYear();
  });
})();
