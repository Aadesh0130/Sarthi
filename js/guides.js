(function () {
  "use strict";

  var params = new URLSearchParams(window.location.search);
  var destinations = window.SARTHI_DATA;
  var destination = destinations.byId(params.get("dest")) || destinations.destinations[0];
  var imageSets = {
    jaipur: ["https://images.unsplash.com/photo-1599661046289-e31897846e41?auto=format&fit=crop&w=900&q=85", "https://images.unsplash.com/photo-1548013146-72479768bada?auto=format&fit=crop&w=900&q=85", "https://images.unsplash.com/photo-1539650116574-75c0c6d73f6e?auto=format&fit=crop&w=900&q=85", "https://images.unsplash.com/photo-1518002054494-3a6f94352e9d?auto=format&fit=crop&w=900&q=85", "https://images.unsplash.com/photo-1516026672322-bc52d61a55d5?auto=format&fit=crop&w=900&q=85"],
    goa: ["https://images.unsplash.com/photo-1518509562904-e7ef99cdcc86?auto=format&fit=crop&w=900&q=85", "https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?auto=format&fit=crop&w=900&q=85", "https://images.unsplash.com/photo-1500534623283-312aade485b7?auto=format&fit=crop&w=900&q=85", "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=900&q=85", "https://images.unsplash.com/photo-1544551763-46a013bb70d5?auto=format&fit=crop&w=900&q=85"],
    spiti: ["https://images.unsplash.com/photo-1501785888041-af3ef285b470?auto=format&fit=crop&w=900&q=85", "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=900&q=85", "https://images.unsplash.com/photo-1518002054494-3a6f94352e9d?auto=format&fit=crop&w=900&q=85", "https://images.unsplash.com/photo-1486911278844-a81c5267e227?auto=format&fit=crop&w=900&q=85", "https://images.unsplash.com/photo-1470770841072-f978cf4d019e?auto=format&fit=crop&w=900&q=85"],
    default: ["https://images.unsplash.com/photo-1529156069898-49953e39b3ac?auto=format&fit=crop&w=900&q=85", "https://images.unsplash.com/photo-1522202176988-66273c2fd55f?auto=format&fit=crop&w=900&q=85", "https://images.unsplash.com/photo-1521737711867-e3b97375f902?auto=format&fit=crop&w=900&q=85", "https://images.unsplash.com/photo-1531482615713-2afd69097998?auto=format&fit=crop&w=900&q=85", "https://images.unsplash.com/photo-1441986300917-64674bd600d8?auto=format&fit=crop&w=900&q=85"]
  };
  var categories = [
    { icon: "🎨", title: "Local Artisans", text: "Potters, weavers, painters, handicraft and jewellery makers", action: "Meet the makers" },
    { icon: "🧑‍🏫", title: "Local Guides", text: "Heritage, cultural, nature, food and walking-tour guides", action: "Find a guide" },
    { icon: "🧵", title: "Workshops", text: "Pottery, painting, weaving, cooking and traditional crafts", action: "Join a workshop" },
    { icon: "🚶", title: "Cultural Experiences", text: "Heritage walks, village life, folk performances and local food", action: "Explore experiences" },
    { icon: "🛍️", title: "Local Markets", text: "Handicraft markets, traditional bazaars and artisan shops", action: "Browse markets" }
  ];
  var images = imageSets[destination.id] || imageSets.default;
  var heading = document.querySelector("[data-guide-destination]");
  var results = document.querySelector("[data-guide-results]");
  heading.textContent = destination.name;
  results.innerHTML = categories.map(function (category, index) {
    return '<article class="guide-result-card" style="--guide-image:url(\'' + images[index] + '\')"><div class="guide-result-card__shade"></div><div class="guide-result-card__content"><span class="guide-result-card__icon">' + category.icon + '</span><h2>' + category.title + '</h2><p>' + category.text + '</p><button class="btn btn--primary btn--sm" type="button" data-guide-action>' + category.action + '</button></div></article>';
  }).join("");

  results.querySelectorAll("[data-guide-action]").forEach(function (button) {
    button.addEventListener("click", function () {
      button.textContent = "Added to your trip";
      button.disabled = true;
      if (window.Sarthi && window.Sarthi.toast) window.Sarthi.toast("Local experience added", "🎒");
    });
  });
})();
