(function () {
  "use strict";

  var params = new URLSearchParams(window.location.search);
  var data = window.SARTHI_DATA;
  var destination = data.byId(params.get("dest")) || data.destinations[0];
  var images = {
    jaipur: ["https://images.unsplash.com/photo-1601050690597-df0568f70950?auto=format&fit=crop&w=1000&q=85", "https://images.unsplash.com/photo-1596797038530-2c107229654b?auto=format&fit=crop&w=1000&q=85", "https://images.unsplash.com/photo-1533777857889-4be7c70b33f7?auto=format&fit=crop&w=1000&q=85", "https://images.unsplash.com/photo-1556911220-e15b29be8c8f?auto=format&fit=crop&w=1000&q=85", "https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=1000&q=85", "https://images.unsplash.com/photo-1515003197210-e0cd71810b5f?auto=format&fit=crop&w=1000&q=85", "https://images.unsplash.com/photo-1473093295043-cdd812d0e601?auto=format&fit=crop&w=1000&q=85"],
    goa: ["https://images.unsplash.com/photo-1512343879784-a960bf40e7f2?auto=format&fit=crop&w=1000&q=85", "https://images.unsplash.com/photo-1518509562904-e7ef99cdcc86?auto=format&fit=crop&w=1000&q=85", "https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=1000&q=85", "https://images.unsplash.com/photo-1556911220-e15b29be8c8f?auto=format&fit=crop&w=1000&q=85", "https://images.unsplash.com/photo-1505253716362-afaea1d3d1af?auto=format&fit=crop&w=1000&q=85", "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=1000&q=85", "https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=1000&q=85"],
    default: ["https://images.unsplash.com/photo-1547592180-85f173990554?auto=format&fit=crop&w=1000&q=85", "https://images.unsplash.com/photo-1505253716362-afaea1d3d1af?auto=format&fit=crop&w=1000&q=85", "https://images.unsplash.com/photo-1533777857889-4be7c70b33f7?auto=format&fit=crop&w=1000&q=85", "https://images.unsplash.com/photo-1556911220-e15b29be8c8f?auto=format&fit=crop&w=1000&q=85", "https://images.unsplash.com/photo-1515003197210-e0cd71810b5f?auto=format&fit=crop&w=1000&q=85", "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=1000&q=85", "https://images.unsplash.com/photo-1473093295043-cdd812d0e601?auto=format&fit=crop&w=1000&q=85"]
  };
  var sections = [
    { icon: "🍛", title: "Traditional Dishes", text: "Iconic foods of this destination and the cultural importance they carry." },
    { icon: "🏺", title: "Food History & Origins", text: "How local dishes developed through the region's communities, trade and landscape." },
    { icon: "🎉", title: "Festival Foods", text: "Special dishes prepared during local festivals, rituals and celebrations." },
    { icon: "👨‍🍳", title: "Traditional Cooking Methods", text: "Local techniques, utensils, firewood cooking and preparation styles." },
    { icon: "🌾", title: "Local Ingredients", text: "Region-specific ingredients and why they matter to local food culture." },
    { icon: "👪", title: "Food Customs & Traditions", text: "Eating habits, serving traditions, hospitality and cultural practices." },
    { icon: "🧑‍🎨", title: "Food Heritage", text: "Famous recipes passed down through generations and the destination's culinary heritage." }
  ];
  var destinationImages = images[destination.id] || images.default;
  var heading = document.querySelector("[data-food-destination]");
  var results = document.querySelector("[data-food-results]");
  heading.textContent = destination.name;
  results.innerHTML = sections.map(function (section, index) {
    return '<article class="food-result-card" style="--food-image:url(\'' + destinationImages[index] + '\')"><div class="food-result-card__shade"></div><div class="food-result-card__content"><span class="food-result-card__icon">' + section.icon + '</span><h2>' + section.title + '</h2><p>' + section.text + '</p><button class="btn btn--primary btn--sm" type="button" data-food-action>Explore this story</button></div></article>';
  }).join("");

  results.querySelectorAll("[data-food-action]").forEach(function (button) {
    button.addEventListener("click", function () {
      button.textContent = "Added to your trip";
      button.disabled = true;
      if (window.Sarthi && window.Sarthi.toast) window.Sarthi.toast("Food story added", "🍛");
    });
  });
})();
