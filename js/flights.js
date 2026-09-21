(function () {
  "use strict";

  var params = new URLSearchParams(window.location.search);
  var from = params.get("from") || "Delhi · DEL";
  var to = params.get("to") || "Jaipur · JAI";
  var when = params.get("when") || "";
  var till = params.get("till") || "";
  var mode = (params.get("mode") || "flight").toLowerCase();

  function prettyDate(value) {
    if (!value) return "Select date";
    var date = new Date(value + "T00:00:00");
    return date.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
  }

  function safeText(value) {
    return String(value).replace(/[&<>"']/g, function (character) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[character];
    });
  }

  function getCity(value) {
    return value.split(" · ")[0];
  }

  var route = document.querySelector("[data-flight-route]");
  var summary = document.querySelector("[data-flight-summary]");
  var list = document.querySelector("[data-flight-list]");
  var fromCity = getCity(from);
  var toCity = getCity(to);

  var travelDetails = {
    flight: {
      title: "Available flights",
      icon: "✈",
      summary: "Non-stop options",
      items: [
        { operator: "IndiGo", code: "6E 2042", depart: "06:20", arrive: "08:10", duration: "1h 50m", price: "₹4,899", note: "Economy · cabin bag included" },
        { operator: "Air India Express", code: "IX 1412", depart: "10:35", arrive: "12:30", duration: "1h 55m", price: "₹5,420", note: "Economy · 15 kg baggage" },
        { operator: "Akasa Air", code: "QP 1375", depart: "16:15", arrive: "18:05", duration: "1h 50m", price: "₹5,876", note: "Economy · cabin bag included" },
        { operator: "Air India", code: "AI 612", depart: "20:40", arrive: "22:35", duration: "1h 55m", price: "₹6,240", note: "Economy · 15 kg baggage" }
      ]
    },
    train: {
      title: "Available trains",
      icon: "🚆",
      summary: "Direct and connecting trains",
      items: [
        { operator: "Rajdhani Express", code: "12952", depart: "16:55", arrive: "05:25", duration: "12h 30m", price: "₹2,145", note: "2A · meal included" },
        { operator: "Shatabdi Express", code: "12015", depart: "06:00", arrive: "10:45", duration: "4h 45m", price: "₹1,320", note: "CC · chair car" },
        { operator: "Intercity Express", code: "12416", depart: "05:30", arrive: "12:15", duration: "6h 45m", price: "₹845", note: "3A · confirmed seats" },
        { operator: "Duronto Express", code: "12264", depart: "22:10", arrive: "08:05", duration: "9h 55m", price: "₹1,780", note: "3A · meal included" }
      ]
    },
    bus: {
      title: "Available buses",
      icon: "🚌",
      summary: "AC and sleeper buses",
      items: [
        { operator: "IntrCity SmartBus", code: "IS 401", depart: "21:30", arrive: "05:45", duration: "8h 15m", price: "₹899", note: "AC sleeper · charging point" },
        { operator: "RedBus Partner", code: "RB 218", depart: "20:15", arrive: "06:30", duration: "10h 15m", price: "₹760", note: "AC seater · live tracking" },
        { operator: "Zingbus", code: "ZG 118", depart: "22:00", arrive: "06:10", duration: "8h 10m", price: "₹1,050", note: "AC sleeper · blanket included" },
        { operator: "State Roadways", code: "RS 72", depart: "07:45", arrive: "16:30", duration: "8h 45m", price: "₹580", note: "AC seater · luggage included" }
      ]
    }
  };

  var selectedTravel = travelDetails[mode] || travelDetails.flight;
  var travelImages = {
    flight: "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?auto=format&fit=crop&w=1800&q=80",
    train: "https://images.unsplash.com/photo-1474487548417-781cb71495f3?auto=format&fit=crop&w=1800&q=80",
    bus: "https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?auto=format&fit=crop&w=1800&q=80"
  };
  var resultsPage = document.querySelector(".flight-page");
  if (resultsPage) {
    resultsPage.style.background = "linear-gradient(135deg, rgba(8, 16, 25, .82), rgba(8, 16, 25, .48)), url('" + (travelImages[mode] || travelImages.flight) + "') center/cover fixed no-repeat";
  }

  route.textContent = fromCity + " to " + toCity;
  summary.innerHTML = [
    "✈ " + mode.charAt(0).toUpperCase() + mode.slice(1),
    "When: " + prettyDate(when),
    "Till: " + prettyDate(till),
    selectedTravel.summary
  ].map(function (item) { return '<span class="flight-summary-pill">' + safeText(item) + "</span>"; }).join("");

  document.querySelector("[data-travel-title]").textContent = selectedTravel.title;

  list.innerHTML = selectedTravel.items.map(function (travel) {
    return '<article class="flight-card">' +
      '<div class="flight-airline"><span class="flight-airline-icon">' + selectedTravel.icon + '</span><div><strong>' + safeText(travel.operator) + '</strong><small>' + safeText(travel.code) + '</small></div></div>' +
      '<div class="flight-times"><div class="flight-time"><strong>' + travel.depart + '</strong><small>' + safeText(fromCity) + '</small></div><div><div class="flight-line"><span>' + selectedTravel.icon + '</span></div><small>' + travel.duration + '</small></div><div class="flight-time"><strong>' + travel.arrive + '</strong><small>' + safeText(toCity) + '</small></div></div>' +
      '<div class="flight-price"><strong>' + travel.price + '</strong><small>' + safeText(travel.note) + '</small><button class="btn btn--primary btn--sm" type="button" data-select-flight>Choose ' + mode + '</button></div>' +
      '</article>';
  }).join("");

  list.querySelectorAll("[data-select-flight]").forEach(function (button) {
    button.addEventListener("click", function () {
      button.textContent = "Selected";
      button.disabled = true;
      if (window.Sarthi && window.Sarthi.toast) window.Sarthi.toast(selectedTravel.title.replace("Available ", "").replace(/s$/, "") + " added to your trip", selectedTravel.icon);
    });
  });
})();
