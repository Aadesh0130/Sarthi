(function () {
  "use strict";
  var D = window.SARTHI_DATA;

  var indianAirports = [
    { city: "Agartala", code: "IXA" }, { city: "Agatti", code: "AGX" }, { city: "Ahmedabad", code: "AMD" },
    { city: "Amritsar", code: "ATQ" }, { city: "Aurangabad / Chhatrapati Sambhajinagar", code: "IXU" }, { city: "Ayodhya", code: "AYJ" },
    { city: "Bagdogra", code: "IXB" }, { city: "Bengaluru", code: "BLR" }, { city: "Belagavi", code: "IXG" },
    { city: "Bhopal", code: "BHO" }, { city: "Bhubaneswar", code: "BBI" }, { city: "Bhuj", code: "BHJ" },
    { city: "Bikaner", code: "BKB" }, { city: "Bilaspur", code: "PAB" }, { city: "Chandigarh", code: "IXC" },
    { city: "Chennai", code: "MAA" }, { city: "Coimbatore", code: "CJB" }, { city: "Dehradun", code: "DED" },
    { city: "Delhi", code: "DEL", dest: "jaipur" }, { city: "Deoghar", code: "DGH" }, { city: "Dibrugarh", code: "DIB" },
    { city: "Dimapur", code: "DMU" }, { city: "Diu", code: "DIU" }, { city: "Durgapur", code: "RDP" },
    { city: "Gaya", code: "GAY" }, { city: "Goa - Dabolim", code: "GOI", dest: "goa" }, { city: "Goa - Mopa", code: "GOX", dest: "goa" },
    { city: "Gondia", code: "GDB" }, { city: "Gorakhpur", code: "GOP" }, { city: "Guwahati", code: "GAU" },
    { city: "Gwalior", code: "GWL" }, { city: "Hubballi", code: "HBX" }, { city: "Hyderabad", code: "HYD" },
    { city: "Imphal", code: "IMF" }, { city: "Indore", code: "IDR" }, { city: "Itanagar / Donyi Polo", code: "HGI" },
    { city: "Jabalpur", code: "JLR" }, { city: "Jagdalpur", code: "JGB" }, { city: "Jaipur", code: "JAI", dest: "jaipur" },
    { city: "Jaisalmer", code: "JSA" }, { city: "Jammu", code: "IXJ" }, { city: "Jamnagar", code: "JGA" },
    { city: "Jharsuguda", code: "JRG" }, { city: "Jodhpur", code: "JDH" }, { city: "Jorhat", code: "JRH" },
    { city: "Kadapa", code: "CDP" }, { city: "Kalaburagi", code: "GBI" }, { city: "Kandla", code: "IXY" },
    { city: "Kangra / Dharamshala", code: "DHM" }, { city: "Kannur", code: "CNN" }, { city: "Kanpur", code: "KNU" },
    { city: "Keshod", code: "IXK" }, { city: "Khajuraho", code: "HJR" }, { city: "Kishangarh / Ajmer", code: "KQH" },
    { city: "Kochi / Cochin", code: "COK" }, { city: "Kolkata", code: "CCU" }, { city: "Kolhapur", code: "KLH" },
    { city: "Kullu-Manali / Bhuntar", code: "KUU" }, { city: "Kushinagar", code: "KBK" }, { city: "Leh", code: "IXL", dest: "leh" },
    { city: "Lilabari", code: "IXI" }, { city: "Lucknow", code: "LKO" }, { city: "Ludhiana", code: "LUH" },
    { city: "Madurai", code: "IXM" }, { city: "Mangaluru", code: "IXE" }, { city: "Mumbai", code: "BOM" },
    { city: "Mysuru", code: "MYQ" }, { city: "Nagpur", code: "NAG" }, { city: "Nanded", code: "NDC" },
    { city: "Navi Mumbai", code: "NMI" }, { city: "Pantnagar", code: "PGH" }, { city: "Patna", code: "PAT" },
    { city: "Pathankot", code: "IXP" }, { city: "Pithoragarh", code: "NNS" }, { city: "Porbandar", code: "PBD" },
    { city: "Port Blair", code: "IXZ", dest: "andaman" }, { city: "Prayagraj", code: "IXD" }, { city: "Pune", code: "PNQ" },
    { city: "Purnea", code: "PUR" }, { city: "Raipur", code: "RPR" }, { city: "Rajahmundry", code: "RJA" },
    { city: "Rajkot", code: "HSR" }, { city: "Ranchi", code: "IXR" }, { city: "Rewa", code: "REW" },
    { city: "Rourkela", code: "RRK" }, { city: "Rupsi", code: "RUP" }, { city: "Salem", code: "SXV" },
    { city: "Shillong", code: "SHL" }, { city: "Shimla", code: "SLV" }, { city: "Shirdi", code: "SAG" },
    { city: "Shivamogga", code: "SWR" }, { city: "Silchar", code: "IXS" }, { city: "Srinagar", code: "SXR" },
    { city: "Surat", code: "STV" }, { city: "Tezpur", code: "TEZ" }, { city: "Tezu", code: "TEI" },
    { city: "Thiruvananthapuram", code: "TRV" }, { city: "Tiruchirappalli", code: "TRZ" }, { city: "Tirupati", code: "TIR" },
    { city: "Tuticorin / Thoothukudi", code: "TCR" }, { city: "Udaipur", code: "UDR" }, { city: "Vadodara", code: "BDQ" },
    { city: "Varanasi", code: "VNS" }, { city: "Vijayawada", code: "VGA" }, { city: "Visakhapatnam", code: "VTZ" }
  ];

  var serviceData = {
    hotels: {
      title: "Hotels & homestays",
      subtitle: "Choose your destination and find stays that match your budget and vibe.",
      builder: function (dest) {
        return [
          { label: "Destination", value: dest.name + " · " + dest.state },
          { label: "Budget", value: "Budget / Comfort / Luxury" },
          { label: "Style", value: "Homestays, boutique stays, family-run hotels" },
          { label: "Ideal for", value: "Couples, friends, families, remote work" }
        ];
      },
      cta: "Find stays"
    },
    transport: {
      title: "Travel & transport",
      subtitle: "Pick your route and travel mode to move around the destination smoothly.",
      builder: function (dest) {
        return [
          { label: "Destination", value: dest.name + " · " + dest.state },
          { label: "Modes", value: "Flight / Train / Bus / Local cab" },
          { label: "Route", value: "From nearest airport or station" },
          { label: "Best for", value: "Fast travel, scenic routes, affordable trips" }
        ];
      },
      cta: "Find flights"
    },
    food: {
      title: "Food & culture",
      subtitle: "Explore famous local dishes and food experiences tied to the place.",
      builder: function (dest) {
        var foods = dest.tags.includes("food") ? "Local signature dishes and café culture" : "Signature foods, snacks and cultural dining experiences";
        return [
          { label: "Destination", value: dest.name + " · " + dest.state },
          { label: "Famous food", value: foods },
          { label: "Experience", value: "Street food, home dining, heritage meals" },
          { label: "Best for", value: "Food lovers, cultural travellers, slow dining" }
        ];
      },
      cta: "Explore food"
    },
    guides: {
      title: "Local artisans & guides",
      subtitle: "Choose a destination and discover people, skills, stories and experiences rooted in the place.",
      builder: function (dest) {
        return [
          { label: "Destination", value: dest.name + " · " + dest.state },
          { label: "Meet", value: "Artisans, storytellers and local guides" },
          { label: "Experience", value: "Hands-on workshops, walks, markets and village life" },
          { label: "Best for", value: "Curious travellers, families and culture lovers" }
        ];
      },
      cta: "Find local experiences"
    }
  };

  function makeDestinationOptions() {
    return D.destinations.map(function (d) {
      return '<option value="' + d.id + '">' + d.name + ' · ' + d.state + '</option>';
    }).join("");
  }

  function makeAirportOptions(defaultCode) {
    return indianAirports.map(function (airport) {
      return '<option value="' + airport.code + '" data-destination="' + airport.dest + '"' + (airport.code === defaultCode ? ' selected' : '') + '>' + airport.city + ' · ' + airport.code + ' · ' + airport.airport + '</option>';
    }).join("");
  }

  function makeAirportSuggestions() {
    return indianAirports.map(function (airport) {
      return '<option value="' + airport.city + ' · ' + airport.code + '">' + airport.city + ' (' + airport.code + ')</option>';
    }).join("");
  }

  function makeGuideGroups() {
    var groups = [
      ["🎨", "Local Artisans", ["Potters", "Weavers", "Painters", "Handicraft makers", "Jewellery makers"]],
      ["🧑‍🏫", "Local Guides", ["Heritage guides", "Cultural guides", "Nature guides", "Food guides", "Walking-tour guides"]],
      ["🧵", "Workshops", ["Pottery", "Painting", "Weaving", "Cooking", "Traditional crafts"]],
      ["🚶", "Cultural Experiences", ["Heritage walks", "Village experiences", "Folk performances", "Local food experiences"]],
      ["🛍️", "Local Markets", ["Handicraft markets", "Traditional bazaars", "Artisan shops"]]
    ];
    return '<div class="guide-groups">' + groups.map(function (group) {
      return '<section class="guide-group"><h3>' + group[0] + ' ' + group[1] + '</h3><div class="guide-tags">' + group[2].map(function (item) {
        return '<span class="guide-tag">' + item + '</span>';
      }).join("") + '</div></section>';
    }).join("") + '</div>';
  }

  function findAirport(value) {
    var query = (value || "").trim().toLowerCase();
    return indianAirports.find(function (airport) {
      return airport.code.toLowerCase() === query || airport.city.toLowerCase() === query || (airport.city + " · " + airport.code).toLowerCase() === query;
    });
  }

  function dateValue(date) {
    var year = date.getFullYear();
    var month = String(date.getMonth() + 1).padStart(2, "0");
    var day = String(date.getDate()).padStart(2, "0");
    return year + "-" + month + "-" + day;
  }

  function calendarMonth(monthDate, whenValue, tillValue) {
    var year = monthDate.getFullYear();
    var month = monthDate.getMonth();
    var firstDay = new Date(year, month, 1);
    var daysInMonth = new Date(year, month + 1, 0).getDate();
    var dayNames = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
    var html = '<section class="date-calendar"><h3>' + monthDate.toLocaleDateString("en-IN", { month: "long", year: "numeric" }) + '</h3><div class="date-weekdays">' + dayNames.map(function (day) { return '<span>' + day + '</span>'; }).join("") + '</div><div class="date-grid">';
    for (var blank = 0; blank < firstDay.getDay(); blank += 1) html += '<span></span>';
    for (var day = 1; day <= daysInMonth; day += 1) {
      var current = new Date(year, month, day);
      var value = dateValue(current);
      var selected = value === whenValue || value === tillValue;
      var inRange = whenValue && tillValue && value > whenValue && value < tillValue;
      html += '<button type="button" class="date-day' + (selected ? ' is-selected' : '') + (inRange ? ' is-in-range' : '') + '" data-calendar-date="' + value + '">' + day + '</button>';
    }
    return html + '</div></section>';
  }

  function getSelectedDestination(value) {
    return D.byId(value) || D.destinations[0];
  }

  function setServiceBackground(serviceKey, mode) {
    var page = document.querySelector(".service-page");
    if (!page) return;

    var visuals = {
      hotels: {
        image: "https://images.unsplash.com/photo-1505693416388-ac5ce068fe85?auto=format&fit=crop&w=1600&q=80"
      },
      transport: {
        Flight: {
          image: "https://images.unsplash.com/photo-1436491865332-7a61a109cc05?auto=format&fit=crop&w=1600&q=80"
        },
        Train: {
          image: "https://images.unsplash.com/photo-1514565131-fce0801e5785?auto=format&fit=crop&w=1600&q=80"
        },
        Bus: {
          image: "https://images.unsplash.com/photo-1558980664-10e7170b5df9?auto=format&fit=crop&w=1600&q=80"
        }
      },
      food: {
        image: "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=1600&q=80"
      },
      guides: {
        image: "https://images.unsplash.com/photo-1529156069898-49953e39b3ac?auto=format&fit=crop&w=1600&q=80"
      }
    };

    var chosen = serviceKey === "transport" ? (visuals.transport[mode || "Flight"] || visuals.transport.Flight) : (visuals[serviceKey] || visuals.hotels);
    var background = chosen.image;

    page.style.background = "linear-gradient(135deg, rgba(10, 17, 25, 0.7), rgba(10, 17, 25, 0.42)), url('" + background + "') center/cover no-repeat";
    page.style.transition = "background .35s ease";
  }

  function renderService(serviceKey) {
    var info = serviceData[serviceKey] || serviceData.hotels;
    var panel = document.getElementById("servicePanel");
    var title = document.getElementById("serviceTitle");
    var subtitle = document.getElementById("serviceSubtitle");

    title.textContent = info.title;
    subtitle.textContent = info.subtitle;

    var defaultDest = D.destinations[0];
    var destId = defaultDest.id;

    var transportModes = serviceKey === "transport" ?
      '<div class="service-route-grid">' +
      '  <div class="service-form-row">' +
      '    <label class="service-label">From</label>' +
      '    <input class="service-select" type="text" list="india-airports" value="Delhi · DEL" data-from-place aria-label="From airport" placeholder="Type a city or airport" />' +
      '  </div>' +
      '  <div class="service-form-row">' +
      '    <label class="service-label">To</label>' +
      '    <input class="service-select" type="text" list="india-airports" value="Jaipur · JAI" data-to-airport aria-label="To airport" placeholder="Type a city or airport" />' +
      '  </div>' +
      '  <datalist id="india-airports">' + makeAirportSuggestions() + '</datalist>' +
      '</div>' +
      '<div class="service-date-grid">' +
      '  <div class="service-form-row">' +
      '    <label class="service-label" for="transportWhen">When</label>' +
      '    <input class="service-select date-display" id="transportWhenDisplay" type="text" data-when-display readonly aria-label="Departure date" />' +
      '    <input id="transportWhen" type="hidden" data-when-date />' +
      '  </div>' +
      '  <div class="service-form-row">' +
      '    <label class="service-label" for="transportTill">Till</label>' +
      '    <input class="service-select date-display" id="transportTillDisplay" type="text" data-till-display readonly aria-label="Return date" />' +
      '    <input id="transportTill" type="hidden" data-till-date />' +
      '  </div>' +
      '</div>' +
      '<div class="date-picker" data-date-picker></div>' +
      '<div class="service-choice-grid">' +
      '<button class="choice-button is-selected" type="button" data-mode="Flight">✈️ Flight</button>' +
      '<button class="choice-button" type="button" data-mode="Train">🚆 Train</button>' +
      '<button class="choice-button" type="button" data-mode="Bus">🚌 Bus</button>' +
      '</div>' : "";

    var foodList = serviceKey === "food" ?
      '<div class="food-preview">' +
      '<div class="food-pill">Local favourites</div>' +
      '<div class="food-pill">Street markets</div>' +
      '<div class="food-pill">Home-cooked culture</div>' +
      '</div>' : "";

    var guideList = serviceKey === "guides" ? makeGuideGroups() : "";

    var hotelControls = serviceKey === "hotels" ?
      '<div class="service-choice-fields">' +
      '  <div class="service-form-row">' +
      '    <label class="service-label" for="hotelStyle">Style</label>' +
      '    <select class="service-select" id="hotelStyle" data-hotel-style aria-label="Choose stay style">' +
      '      <option value="Homestays">Homestays</option>' +
      '      <option value="Boutique stays">Boutique stays</option>' +
      '      <option value="Family-run hotels">Family-run hotels</option>' +
      '    </select>' +
      '  </div>' +
      '  <div class="service-form-row">' +
      '    <label class="service-label" for="hotelIdealFor">Ideal for</label>' +
      '    <select class="service-select" id="hotelIdealFor" data-hotel-ideal aria-label="Choose who the stay is ideal for">' +
      '      <option value="Couples">Couples</option>' +
      '      <option value="Friends">Friends</option>' +
      '      <option value="Families">Families</option>' +
      '      <option value="Remote work">Remote work</option>' +
      '    </select>' +
      '  </div>' +
      '</div>' : "";

    panel.innerHTML = '' +
      '<div class="service-form-card">' +
      (serviceKey === "transport" ? '' :
      '  <div class="service-form-row">' +
      '    <label class="service-label">Where do you want to go?</label>' +
      '    <select class="service-select" data-destination-select aria-label="Select destination">' +
      makeDestinationOptions() +
      '    </select>' +
      '  </div>') +
      transportModes +
      hotelControls +
      foodList +
      guideList +
      '  <div class="service-summary">' +
      '    <h3>Trip details</h3>' +
      '    <div class="service-summary-grid"></div>' +
      '  </div>' +
      '  <div class="service-actions">' +
      '    <button class="btn btn--primary" type="button" data-service-submit>' + info.cta + '</button>' +
      '    <a class="btn btn--ghost" href="explore.html?interest=' + (serviceKey === "hotels" ? "heritage" : serviceKey === "transport" ? "adventure" : serviceKey === "guides" ? "culture" : "food") + '">Browse all</a>' +
      '  </div>' +
      '</div>';

    var select = panel.querySelector("[data-destination-select]") || panel.querySelector("[data-to-airport]");
    var summaryGrid = panel.querySelector(".service-summary-grid");
    var submit = panel.querySelector("[data-service-submit]");
    var fromPlace = panel.querySelector("[data-from-place]");
    var whenDate = panel.querySelector("[data-when-date]");
    var tillDate = panel.querySelector("[data-till-date]");
    var whenDisplay = panel.querySelector("[data-when-display]");
    var tillDisplay = panel.querySelector("[data-till-display]");
    var datePicker = panel.querySelector("[data-date-picker]");
    var hotelStyle = panel.querySelector("[data-hotel-style]");
    var hotelIdeal = panel.querySelector("[data-hotel-ideal]");
    var selectedMode = null;

    function getFormDestination() {
      if (!select) return getSelectedDestination(destId);
      if (select.hasAttribute("data-to-airport")) {
        var airport = findAirport(select.value);
        return getSelectedDestination(airport ? airport.dest : destId);
      }
      return getSelectedDestination(select.value);
    }

    function renderSummary() {
      var list = info.builder(getFormDestination());
      summaryGrid.innerHTML = list.map(function (row) {
        if (row.label === "Style" || row.label === "Ideal for") return "";
        return '<div class="summary-item"><span>' + row.label + '</span><strong>' + row.value + '</strong></div>';
      }).join("");
    }

    renderSummary();

    if (whenDate && tillDate) {
      var today = new Date();
      var tomorrow = new Date(today);
      tomorrow.setDate(today.getDate() + 1);
      whenDate.value = dateValue(today);
      tillDate.value = dateValue(tomorrow);
      whenDisplay.value = today.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
      tillDisplay.value = tomorrow.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
      var calendarStart = new Date(today.getFullYear(), today.getMonth(), 1);
      function renderDatePicker() {
        var nextMonth = new Date(calendarStart.getFullYear(), calendarStart.getMonth() + 1, 1);
        datePicker.innerHTML = calendarMonth(calendarStart, whenDate.value, tillDate.value) + calendarMonth(nextMonth, whenDate.value, tillDate.value);
      }
      datePicker.addEventListener("click", function (event) {
        var button = event.target.closest("[data-calendar-date]");
        if (!button) return;
        var value = button.getAttribute("data-calendar-date");
        if (!whenDate.value || (whenDate.value && tillDate.value)) {
          whenDate.value = value;
          tillDate.value = "";
        } else if (value < whenDate.value) {
          whenDate.value = value;
        } else {
          tillDate.value = value;
        }
        whenDisplay.value = whenDate.value ? new Date(whenDate.value + "T00:00:00").toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "";
        tillDisplay.value = tillDate.value ? new Date(tillDate.value + "T00:00:00").toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "";
        renderDatePicker();
      });
      renderDatePicker();
    }

    if (serviceKey === "transport") {
      selectedMode = "Flight";
      submit.textContent = "Find flights";
      setServiceBackground(serviceKey, selectedMode);
    } else {
      setServiceBackground(serviceKey, "");
    }

    panel.querySelectorAll("[data-mode]").forEach(function (button) {
      button.addEventListener("click", function () {
        panel.querySelectorAll("[data-mode]").forEach(function (btn) { btn.classList.remove("is-selected"); });
        button.classList.add("is-selected");
        selectedMode = button.getAttribute("data-mode");
        submit.textContent = "Find " + (selectedMode === "Bus" ? "buses" : selectedMode.toLowerCase() + "s");
        setServiceBackground(serviceKey, selectedMode);
      });
    });

    if (select) {
      select.addEventListener("change", function () {
        renderSummary();
      });
    }

    [hotelStyle, hotelIdeal].forEach(function (control) {
      if (control) control.addEventListener("change", renderSummary);
    });

    submit.addEventListener("click", function () {
      var airport = select ? findAirport(select.value) : null;
      var dest = getSelectedDestination(airport ? airport.dest : (select ? select.value : destId));
      var params = new URLSearchParams();
      params.set("dest", dest.id);
      if (serviceKey === "transport") {
        if (whenDate && tillDate && (!whenDate.value || !tillDate.value || tillDate.value < whenDate.value)) {
          whenDate.reportValidity();
          tillDate.reportValidity();
          return;
        }
        params.set("mode", (selectedMode || "Flight").toLowerCase());
        params.set("from", (fromPlace ? fromPlace.value : "Delhi").trim() || "Delhi");
        params.set("to", (select ? select.value : dest.name).trim() || dest.name);
        params.set("when", whenDate ? whenDate.value : "");
        params.set("till", tillDate ? tillDate.value : "");
        params.set("interest", "adventure");
        window.location.href = "flights.html?" + params.toString();
        return;
      }
      if (serviceKey === "food") {
        window.location.href = "food.html?dest=" + encodeURIComponent(dest.id);
        return;
      }
      if (serviceKey === "hotels") params.set("interest", "heritage");
      if (serviceKey === "guides") {
        window.location.href = "guides.html?dest=" + encodeURIComponent(dest.id);
        return;
      }
      window.location.href = "planner.html?" + params.toString();
    });
  }

  function initTabs() {
    var tabs = document.querySelectorAll("[data-service-tab]");
    var params = new URLSearchParams(window.location.search);
    var requested = params.get("service");
    var defaultKey = requested === "transport" || requested === "hotels" || requested === "food" || requested === "guides" ? requested : "hotels";

    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        tabs.forEach(function (t) { t.classList.remove("is-active"); });
        tab.classList.add("is-active");
        renderService(tab.getAttribute("data-service-tab"));
      });
    });

    renderService(defaultKey);
    var selectedTab = document.querySelector('[data-service-tab="' + defaultKey + '"]');
    if (selectedTab) {
      tabs.forEach(function (t) { t.classList.remove("is-active"); });
      selectedTab.classList.add("is-active");
    }
  }

  document.addEventListener("DOMContentLoaded", initTabs);
})();
