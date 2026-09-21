/* =========================================================
   Sārthi — Destination knowledge base
   Curated dataset of Indian destinations. Powers the AI
   planner, discovery engine and booking demo. Fully offline.
   ========================================================= */

window.SARTHI_DATA = {
  // gradient palettes used to render destination "photos" offline (no external images)
  destinations: [
    {
      id: "jaipur", name: "Jaipur", state: "Rajasthan", region: "North",
      emoji: "🏰", grad: ["#ff8a5c", "#f2551f"],
      tags: ["heritage", "culture", "food"], hiddenGem: false,
      popularity: 88, rating: 4.6, avgDailyCost: 3200, sustainability: 62,
      bestSeason: "Oct – Mar", airport: "Jaipur (JAI)", station: "Jaipur Jn",
      blurb: "The Pink City — royal forts, bazaars and Rajputana grandeur.",
      attractions: [
        { name: "Amber Fort & elephant courtyard", type: "heritage", hrs: 3, cost: 500 },
        { name: "City Palace & Chandra Mahal", type: "heritage", hrs: 2, cost: 700 },
        { name: "Hawa Mahal photo walk", type: "sightseeing", hrs: 1, cost: 200 },
        { name: "Jantar Mantar observatory", type: "heritage", hrs: 1.5, cost: 200 },
        { name: "Nahargarh Fort sunset", type: "nature", hrs: 2, cost: 200 }
      ],
      experiences: [
        { name: "Block-printing workshop with local artisans", price: 900, local: true, eco: true },
        { name: "Old-city food trail with a home chef", price: 1200, local: true, eco: true },
        { name: "Puppet & folk-dance evening", price: 600, local: true, eco: false }
      ],
      hotels: [
        { name: "Zostel Jaipur", type: "budget", pricePerNight: 900, rating: 4.3 },
        { name: "Umaid Mahal Heritage", type: "comfort", pricePerNight: 3200, rating: 4.4 },
        { name: "Rambagh Palace", type: "luxury", pricePerNight: 24000, rating: 4.9 }
      ]
    },
    {
      id: "udaipur", name: "Udaipur", state: "Rajasthan", region: "North",
      emoji: "🛶", grad: ["#5eb0e8", "#0ea5a4"],
      tags: ["heritage", "romantic", "culture"], hiddenGem: false,
      popularity: 80, rating: 4.7, avgDailyCost: 3600, sustainability: 65,
      bestSeason: "Sep – Mar", airport: "Udaipur (UDR)", station: "Udaipur City",
      blurb: "City of Lakes — palaces mirrored on shimmering water.",
      attractions: [
        { name: "Lake Pichola sunset boat ride", type: "nature", hrs: 1.5, cost: 700 },
        { name: "City Palace complex", type: "heritage", hrs: 2.5, cost: 500 },
        { name: "Saheliyon ki Bari gardens", type: "nature", hrs: 1, cost: 100 },
        { name: "Bagore ki Haveli museum", type: "culture", hrs: 1.5, cost: 200 },
        { name: "Monsoon Palace viewpoint", type: "sightseeing", hrs: 2, cost: 300 }
      ],
      experiences: [
        { name: "Miniature-painting class with a master", price: 1100, local: true, eco: true },
        { name: "Vintage-car & royal cuisine dinner", price: 2200, local: true, eco: false },
        { name: "Village cycling tour to Badi Lake", price: 800, local: true, eco: true }
      ],
      hotels: [
        { name: "Bunkyard Hostel", type: "budget", pricePerNight: 1000, rating: 4.4 },
        { name: "Jagat Niwas Lake Palace", type: "comfort", pricePerNight: 4200, rating: 4.6 },
        { name: "Taj Lake Palace", type: "luxury", pricePerNight: 38000, rating: 4.9 }
      ]
    },
    {
      id: "goa", name: "Goa", state: "Goa", region: "West",
      emoji: "🏖️", grad: ["#ffd166", "#ff8a5c"],
      tags: ["beach", "nightlife", "food"], hiddenGem: false,
      popularity: 92, rating: 4.4, avgDailyCost: 3800, sustainability: 48,
      bestSeason: "Nov – Feb", airport: "Dabolim (GOI)", station: "Madgaon",
      blurb: "Sun, sand and susegad — beaches, cafés and Portuguese charm.",
      attractions: [
        { name: "Old Goa churches (UNESCO)", type: "heritage", hrs: 2, cost: 0 },
        { name: "Dudhsagar waterfall jeep trip", type: "nature", hrs: 4, cost: 1500 },
        { name: "Fontainhas Latin quarter walk", type: "culture", hrs: 1.5, cost: 0 },
        { name: "Palolem beach day", type: "beach", hrs: 3, cost: 0 },
        { name: "Fort Aguada sunset", type: "sightseeing", hrs: 1.5, cost: 50 }
      ],
      experiences: [
        { name: "Sunrise kayaking through mangroves", price: 1300, local: true, eco: true },
        { name: "Goan-Catholic home kitchen class", price: 1600, local: true, eco: true },
        { name: "Spice-plantation lunch tour", price: 900, local: true, eco: true }
      ],
      hotels: [
        { name: "The Hosteller Anjuna", type: "budget", pricePerNight: 1100, rating: 4.2 },
        { name: "Acron Waterfront Resort", type: "comfort", pricePerNight: 4800, rating: 4.4 },
        { name: "Taj Fort Aguada", type: "luxury", pricePerNight: 26000, rating: 4.8 }
      ]
    },
    {
      id: "rishikesh", name: "Rishikesh", state: "Uttarakhand", region: "North",
      emoji: "🧘", grad: ["#3fd07f", "#0ea5a4"],
      tags: ["spiritual", "adventure", "nature"], hiddenGem: false,
      popularity: 78, rating: 4.5, avgDailyCost: 2400, sustainability: 70,
      bestSeason: "Sep – Nov, Mar – May", airport: "Dehradun (DED)", station: "Rishikesh",
      blurb: "Yoga capital on the Ganga — rapids, ashrams and river aartis.",
      attractions: [
        { name: "Triveni Ghat Ganga aarti", type: "spiritual", hrs: 1.5, cost: 0 },
        { name: "Lakshman Jhula & Ram Jhula walk", type: "sightseeing", hrs: 2, cost: 0 },
        { name: "Beatles Ashram murals", type: "culture", hrs: 1.5, cost: 150 },
        { name: "Neer Garh waterfall trek", type: "nature", hrs: 3, cost: 100 }
      ],
      experiences: [
        { name: "White-water rafting (16 km)", price: 1200, local: true, eco: false },
        { name: "Sunrise yoga & meditation by the river", price: 500, local: true, eco: true },
        { name: "Himalayan cooking with a local family", price: 800, local: true, eco: true }
      ],
      hotels: [
        { name: "Live Free Hostel", type: "budget", pricePerNight: 700, rating: 4.3 },
        { name: "Aloha on the Ganges", type: "comfort", pricePerNight: 4500, rating: 4.5 },
        { name: "Taj Rishikesh Resort", type: "luxury", pricePerNight: 22000, rating: 4.8 }
      ]
    },
    {
      id: "varanasi", name: "Varanasi", state: "Uttar Pradesh", region: "North",
      emoji: "🪔", grad: ["#f5a524", "#f2551f"],
      tags: ["spiritual", "heritage", "culture"], hiddenGem: false,
      popularity: 82, rating: 4.5, avgDailyCost: 2200, sustainability: 55,
      bestSeason: "Oct – Mar", airport: "Varanasi (VNS)", station: "Varanasi Jn",
      blurb: "The eternal city — ghats, silk and the soul of the Ganga.",
      attractions: [
        { name: "Dashashwamedh Ghat Ganga aarti", type: "spiritual", hrs: 1.5, cost: 0 },
        { name: "Sunrise boat ride on the Ganga", type: "nature", hrs: 1.5, cost: 400 },
        { name: "Kashi Vishwanath corridor", type: "spiritual", hrs: 2, cost: 0 },
        { name: "Sarnath Buddhist stupa", type: "heritage", hrs: 2, cost: 250 }
      ],
      experiences: [
        { name: "Banarasi-silk weaving visit", price: 700, local: true, eco: true },
        { name: "Heritage-lane food walk (kachori, lassi)", price: 900, local: true, eco: true },
        { name: "Classical sitar session at a ghat", price: 800, local: true, eco: false }
      ],
      hotels: [
        { name: "Stops Hostel Varanasi", type: "budget", pricePerNight: 750, rating: 4.4 },
        { name: "BrijRama Palace (river-facing)", type: "comfort", pricePerNight: 6500, rating: 4.6 },
        { name: "Taj Nadesar Palace", type: "luxury", pricePerNight: 20000, rating: 4.8 }
      ]
    },
    {
      id: "munnar", name: "Munnar", state: "Kerala", region: "South",
      emoji: "🍃", grad: ["#3fd07f", "#149a5b"],
      tags: ["nature", "romantic", "offbeat"], hiddenGem: false,
      popularity: 72, rating: 4.6, avgDailyCost: 2800, sustainability: 78,
      bestSeason: "Sep – Mar", airport: "Kochi (COK)", station: "Aluva",
      blurb: "Rolling tea gardens wrapped in Western-Ghats mist.",
      attractions: [
        { name: "Tea plantations & museum", type: "nature", hrs: 2.5, cost: 300 },
        { name: "Eravikulam National Park (Nilgiri tahr)", type: "nature", hrs: 3, cost: 400 },
        { name: "Top Station viewpoint", type: "sightseeing", hrs: 2, cost: 100 },
        { name: "Attukad waterfalls", type: "nature", hrs: 1.5, cost: 50 }
      ],
      experiences: [
        { name: "Tea-tasting with a plantation family", price: 700, local: true, eco: true },
        { name: "Guided spice-garden & cardamom walk", price: 600, local: true, eco: true },
        { name: "Sunrise trek to Kolukkumalai", price: 1400, local: true, eco: true }
      ],
      hotels: [
        { name: "Zostel Munnar", type: "budget", pricePerNight: 850, rating: 4.4 },
        { name: "Tea Valley Resort", type: "comfort", pricePerNight: 3800, rating: 4.5 },
        { name: "Fragrant Nature Munnar", type: "luxury", pricePerNight: 12000, rating: 4.7 }
      ]
    },
    {
      id: "hampi", name: "Hampi", state: "Karnataka", region: "South",
      emoji: "🗿", grad: ["#e8a15e", "#c26b2d"],
      tags: ["heritage", "offbeat", "culture"], hiddenGem: true,
      popularity: 46, rating: 4.7, avgDailyCost: 1800, sustainability: 80,
      bestSeason: "Oct – Feb", airport: "Hubli (HBX)", station: "Hospet Jn",
      blurb: "A boulder-strewn Vijayanagara ruin-scape frozen in time.",
      attractions: [
        { name: "Virupaksha Temple & bazaar", type: "heritage", hrs: 2, cost: 50 },
        { name: "Vittala Temple & stone chariot", type: "heritage", hrs: 2, cost: 400 },
        { name: "Matanga Hill sunrise", type: "nature", hrs: 2, cost: 0 },
        { name: "Coracle ride on the Tungabhadra", type: "nature", hrs: 1, cost: 300 }
      ],
      experiences: [
        { name: "Boulder-scramble guided by a local", price: 700, local: true, eco: true },
        { name: "Heritage cycling across the ruins", price: 500, local: true, eco: true },
        { name: "Banana-plantation farm lunch", price: 450, local: true, eco: true }
      ],
      hotels: [
        { name: "Hampi's Boulders Homestay", type: "budget", pricePerNight: 650, rating: 4.5 },
        { name: "Evolve Back Hampi (comfort wing)", type: "comfort", pricePerNight: 5200, rating: 4.7 },
        { name: "Evolve Back Kamalapura Palace", type: "luxury", pricePerNight: 18000, rating: 4.9 }
      ]
    },
    {
      id: "leh", name: "Leh–Ladakh", state: "Ladakh", region: "North",
      emoji: "🏔️", grad: ["#6a45f0", "#0ea5a4"],
      tags: ["adventure", "nature", "spiritual"], hiddenGem: false,
      popularity: 68, rating: 4.8, avgDailyCost: 3400, sustainability: 60,
      bestSeason: "May – Sep", airport: "Leh (IXL)", station: "—",
      blurb: "High-desert monasteries, blue lakes and thin mountain air.",
      attractions: [
        { name: "Pangong Tso lake day trip", type: "nature", hrs: 5, cost: 800 },
        { name: "Thiksey & Hemis monasteries", type: "spiritual", hrs: 3, cost: 200 },
        { name: "Nubra Valley & sand dunes", type: "adventure", hrs: 6, cost: 1200 },
        { name: "Leh Palace & old town", type: "heritage", hrs: 2, cost: 100 }
      ],
      experiences: [
        { name: "Homestay night in a Ladakhi village", price: 1500, local: true, eco: true },
        { name: "Guided acclimatisation hike", price: 900, local: true, eco: true },
        { name: "Butter-tea & momo cooking session", price: 700, local: true, eco: true }
      ],
      hotels: [
        { name: "Zostel Leh", type: "budget", pricePerNight: 1100, rating: 4.4 },
        { name: "The Grand Dragon Ladakh", type: "comfort", pricePerNight: 6500, rating: 4.6 },
        { name: "The Ultimate Travelling Camp", type: "luxury", pricePerNight: 30000, rating: 4.9 }
      ]
    },
    {
      id: "spiti", name: "Spiti Valley", state: "Himachal Pradesh", region: "North",
      emoji: "🛕", grad: ["#8b9dc3", "#5a6f9e"],
      tags: ["offbeat", "adventure", "spiritual"], hiddenGem: true,
      popularity: 34, rating: 4.9, avgDailyCost: 2600, sustainability: 88,
      bestSeason: "Jun – Sep", airport: "Bhuntar (KUU)", station: "—",
      blurb: "A cold-desert 'middle land' of cliff-top monasteries and fossils.",
      attractions: [
        { name: "Key Monastery viewpoint", type: "spiritual", hrs: 2, cost: 100 },
        { name: "Chandratal 'Moon Lake' visit", type: "nature", hrs: 4, cost: 200 },
        { name: "Hikkim — world's highest post office", type: "offbeat", hrs: 2, cost: 0 },
        { name: "Dhankar fort-monastery hike", type: "adventure", hrs: 3, cost: 150 }
      ],
      experiences: [
        { name: "Farm-stay with a Spitian family", price: 1200, local: true, eco: true },
        { name: "Yak-cheese & seabuckthorn tasting", price: 500, local: true, eco: true },
        { name: "Village astronomy night (clear skies)", price: 800, local: true, eco: true }
      ],
      hotels: [
        { name: "Zostel Spiti (Kaza)", type: "budget", pricePerNight: 950, rating: 4.6 },
        { name: "Spiti Heritage Homestay", type: "comfort", pricePerNight: 2800, rating: 4.7 },
        { name: "The Himalayan Village Sojha", type: "luxury", pricePerNight: 9000, rating: 4.8 }
      ]
    },
    {
      id: "andaman", name: "Andaman Islands", state: "Andaman & Nicobar", region: "Islands",
      emoji: "🐠", grad: ["#22c1c3", "#0e7c96"],
      tags: ["beach", "adventure", "nature"], hiddenGem: false,
      popularity: 70, rating: 4.7, avgDailyCost: 4200, sustainability: 66,
      bestSeason: "Oct – May", airport: "Port Blair (IXZ)", station: "—",
      blurb: "Turquoise water, coral reefs and India's cleanest beaches.",
      attractions: [
        { name: "Radhanagar Beach (Havelock)", type: "beach", hrs: 3, cost: 0 },
        { name: "Cellular Jail light-and-sound show", type: "heritage", hrs: 1.5, cost: 300 },
        { name: "Elephant Beach snorkelling", type: "nature", hrs: 3, cost: 1500 },
        { name: "Ross Island heritage walk", type: "heritage", hrs: 2, cost: 250 }
      ],
      experiences: [
        { name: "Beginner scuba dive with reef guide", price: 3500, local: true, eco: true },
        { name: "Mangrove kayak with a naturalist", price: 1400, local: true, eco: true },
        { name: "Island seafood dinner with fishers", price: 1200, local: true, eco: true }
      ],
      hotels: [
        { name: "DoubleTree-free Beach Hostel", type: "budget", pricePerNight: 1300, rating: 4.1 },
        { name: "SeaShell Havelock", type: "comfort", pricePerNight: 6000, rating: 4.5 },
        { name: "Taj Exotica Andamans", type: "luxury", pricePerNight: 34000, rating: 4.9 }
      ]
    },
    {
      id: "ziro", name: "Ziro Valley", state: "Arunachal Pradesh", region: "Northeast",
      emoji: "🌾", grad: ["#84c14e", "#3d8b3d"],
      tags: ["offbeat", "nature", "culture"], hiddenGem: true,
      popularity: 22, rating: 4.8, avgDailyCost: 2100, sustainability: 92,
      bestSeason: "Mar – Oct", airport: "Lilabari (IXI)", station: "Naharlagun",
      blurb: "Emerald rice terraces and Apatani culture — a UNESCO-tentative gem.",
      attractions: [
        { name: "Apatani rice-fish terrace walk", type: "nature", hrs: 3, cost: 0 },
        { name: "Talley Valley wildlife trek", type: "adventure", hrs: 5, cost: 400 },
        { name: "Old Ziro tribal village visit", type: "culture", hrs: 2, cost: 200 },
        { name: "Pine-grove & Kile Pakho ridge", type: "nature", hrs: 2, cost: 0 }
      ],
      experiences: [
        { name: "Apatani homestay & millet-beer evening", price: 1000, local: true, eco: true },
        { name: "Bamboo-craft workshop", price: 600, local: true, eco: true },
        { name: "Guided birdwatching morning", price: 700, local: true, eco: true }
      ],
      hotels: [
        { name: "Ziro Valley Homestay", type: "budget", pricePerNight: 800, rating: 4.6 },
        { name: "Blaa Homestay (heritage)", type: "comfort", pricePerNight: 2400, rating: 4.7 },
        { name: "Kabak Eco Retreat", type: "luxury", pricePerNight: 5500, rating: 4.8 }
      ]
    },
    {
      id: "gokarna", name: "Gokarna", state: "Karnataka", region: "West",
      emoji: "🌊", grad: ["#ffb36b", "#0ea5a4"],
      tags: ["beach", "spiritual", "offbeat"], hiddenGem: true,
      popularity: 40, rating: 4.5, avgDailyCost: 1900, sustainability: 74,
      bestSeason: "Oct – Mar", airport: "Goa (GOI)", station: "Gokarna Road",
      blurb: "Goa's laid-back cousin — temple town meets untouched coves.",
      attractions: [
        { name: "Beach trek: Om → Half-Moon → Paradise", type: "adventure", hrs: 4, cost: 0 },
        { name: "Mahabaleshwar Temple", type: "spiritual", hrs: 1.5, cost: 0 },
        { name: "Kudle Beach sunset", type: "beach", hrs: 2, cost: 0 },
        { name: "Yana caves rock formations", type: "nature", hrs: 3, cost: 100 }
      ],
      experiences: [
        { name: "Dawn yoga on a quiet cove", price: 500, local: true, eco: true },
        { name: "Local Konkani thali cooking", price: 700, local: true, eco: true },
        { name: "Fishing-boat dolphin spotting", price: 900, local: true, eco: true }
      ],
      hotels: [
        { name: "Namaste Sanjeevini (beach huts)", type: "budget", pricePerNight: 700, rating: 4.3 },
        { name: "SwaSwara wellness (comfort)", type: "comfort", pricePerNight: 5000, rating: 4.6 },
        { name: "Kahani Paradise", type: "luxury", pricePerNight: 15000, rating: 4.8 }
      ]
    },
    {
      id: "darjeeling", name: "Darjeeling", state: "West Bengal", region: "Northeast",
      emoji: "🚂", grad: ["#7fb069", "#3a7d44"],
      tags: ["nature", "heritage", "romantic"], hiddenGem: false,
      popularity: 74, rating: 4.4, avgDailyCost: 2500, sustainability: 68,
      bestSeason: "Oct – Dec, Mar – May", airport: "Bagdogra (IXB)", station: "New Jalpaiguri",
      blurb: "Toy trains, tea estates and Kanchenjunga at dawn.",
      attractions: [
        { name: "Tiger Hill sunrise over Kanchenjunga", type: "nature", hrs: 2.5, cost: 200 },
        { name: "Darjeeling Himalayan 'toy train' ride", type: "heritage", hrs: 2, cost: 1500 },
        { name: "Happy Valley tea estate tour", type: "nature", hrs: 2, cost: 300 },
        { name: "Padmaja Naidu Himalayan Zoo", type: "nature", hrs: 2, cost: 150 }
      ],
      experiences: [
        { name: "Tea-tasting with an estate planter", price: 800, local: true, eco: true },
        { name: "Nepali-Gorkha kitchen experience", price: 900, local: true, eco: true },
        { name: "Sunrise photography walk", price: 600, local: true, eco: false }
      ],
      hotels: [
        { name: "Revolver (boutique hostel)", type: "budget", pricePerNight: 1000, rating: 4.4 },
        { name: "Mayfair Darjeeling", type: "comfort", pricePerNight: 5500, rating: 4.5 },
        { name: "Glenburn Tea Estate", type: "luxury", pricePerNight: 20000, rating: 4.9 }
      ]
    },
    {
      id: "kutch", name: "Rann of Kutch", state: "Gujarat", region: "West",
      emoji: "🐫", grad: ["#e0c097", "#b08968"],
      tags: ["offbeat", "culture", "heritage"], hiddenGem: true,
      popularity: 38, rating: 4.6, avgDailyCost: 2300, sustainability: 76,
      bestSeason: "Nov – Feb (Rann Utsav)", airport: "Bhuj (BHJ)", station: "Bhuj",
      blurb: "An endless white salt desert that glows under the full moon.",
      attractions: [
        { name: "White Rann full-moon sunset", type: "nature", hrs: 3, cost: 100 },
        { name: "Kalo Dungar (Black Hill) viewpoint", type: "sightseeing", hrs: 2, cost: 50 },
        { name: "Handicraft villages (Nirona, Ajrakhpur)", type: "culture", hrs: 3, cost: 0 },
        { name: "Bhuj heritage & Aina Mahal", type: "heritage", hrs: 2, cost: 150 }
      ],
      experiences: [
        { name: "Rogan-art & Ajrakh block-print visit", price: 800, local: true, eco: true },
        { name: "Kutchi embroidery with artisan women", price: 700, local: true, eco: true },
        { name: "Camel-cart ride across the salt flats", price: 600, local: true, eco: true }
      ],
      hotels: [
        { name: "Rann Tent City (budget bhunga)", type: "budget", pricePerNight: 1500, rating: 4.2 },
        { name: "Gateway to Rann Resort", type: "comfort", pricePerNight: 4000, rating: 4.4 },
        { name: "The White Rann Resort (premium)", type: "luxury", pricePerNight: 11000, rating: 4.7 }
      ]
    },
    {
      id: "coorg", name: "Coorg (Kodagu)", state: "Karnataka", region: "South",
      emoji: "☕", grad: ["#5a8f5a", "#2f6b3c"],
      tags: ["nature", "romantic", "adventure"], hiddenGem: false,
      popularity: 66, rating: 4.5, avgDailyCost: 2700, sustainability: 79,
      bestSeason: "Oct – Mar", airport: "Mangaluru (IXE)", station: "Mysuru",
      blurb: "The Scotland of India — coffee estates, mist and misty hills.",
      attractions: [
        { name: "Abbey Falls & coffee estate walk", type: "nature", hrs: 2, cost: 100 },
        { name: "Dubare elephant camp (river-side)", type: "nature", hrs: 2.5, cost: 300 },
        { name: "Namdroling 'Golden Temple' monastery", type: "spiritual", hrs: 1.5, cost: 0 },
        { name: "Mandalpatti jeep sunrise", type: "adventure", hrs: 3, cost: 500 }
      ],
      experiences: [
        { name: "Coffee-plantation stay & bean-roasting", price: 900, local: true, eco: true },
        { name: "Kodava-cuisine cooking (pandi curry)", price: 800, local: true, eco: true },
        { name: "River rafting on the Barapole", price: 1300, local: true, eco: false }
      ],
      hotels: [
        { name: "Coorg Jungle Hostel", type: "budget", pricePerNight: 900, rating: 4.3 },
        { name: "Club Mahindra Madikeri", type: "comfort", pricePerNight: 4500, rating: 4.4 },
        { name: "Evolve Back Coorg", type: "luxury", pricePerNight: 19000, rating: 4.9 }
      ]
    },
    {
      id: "phawngpui", name: "Phawngpui (Blue Mountain)", state: "Mizoram", region: "Northeast",
      emoji: "⛰️", grad: ["#5c83a8", "#1b435d"],
      tags: ["nature", "offbeat", "adventure"], hiddenGem: false,
      popularity: 18, rating: 4.8, avgDailyCost: 2400, sustainability: 92,
      bestSeason: "Oct – Apr", airport: "Lengpui (AJL)", station: "No rail connection",
      blurb: "Mizoram's Blue Mountain — cloud-wrapped ridges, orchids and quiet trails.",
      attractions: [
        { name: "Phawngpui Peak sunrise trail", type: "nature", hrs: 4, cost: 200 },
        { name: "Thlazuang Khâm waterfall", type: "nature", hrs: 2, cost: 100 },
        { name: "Blue Mountain orchid walk", type: "nature", hrs: 2, cost: 150 },
        { name: "Mizo village and culture visit", type: "culture", hrs: 3, cost: 300 }
      ],
      experiences: [
        { name: "Community-led Blue Mountain trek", price: 900, local: true, eco: true },
        { name: "Mizo home-cooking experience", price: 700, local: true, eco: true },
        { name: "Birdwatching with a local guide", price: 600, local: true, eco: true }
      ],
      hotels: [
        { name: "Phawngpui Community Homestay", type: "budget", pricePerNight: 900, rating: 4.5 },
        { name: "Blue Mountain Nature Lodge", type: "comfort", pricePerNight: 2600, rating: 4.6 },
        { name: "Mizoram Hills Retreat", type: "luxury", pricePerNight: 6500, rating: 4.7 }
      ]
    },
    {
      id: "meghalaya", name: "Meghalaya", state: "Meghalaya", region: "Northeast",
      emoji: "🌉", grad: ["#2fa78b", "#146356"],
      tags: ["offbeat", "nature", "adventure"], hiddenGem: true,
      popularity: 44, rating: 4.8, avgDailyCost: 2600, sustainability: 90,
      bestSeason: "Sep – Apr", airport: "Shillong (SHL)", station: "Guwahati",
      blurb: "Abode of clouds — living root bridges and crystal streams.",
      attractions: [
        { name: "Double-decker living root bridge trek", type: "adventure", hrs: 5, cost: 200 },
        { name: "Dawki river (glass-clear water)", type: "nature", hrs: 3, cost: 600 },
        { name: "Nohkalikai — India's tallest plunge fall", type: "nature", hrs: 2, cost: 100 },
        { name: "Mawlynnong — Asia's cleanest village", type: "culture", hrs: 2, cost: 50 }
      ],
      experiences: [
        { name: "Khasi homestay & bamboo-dance evening", price: 1000, local: true, eco: true },
        { name: "Caving with a village guide", price: 900, local: true, eco: true },
        { name: "Root-bridge conservation walk", price: 700, local: true, eco: true }
      ],
      hotels: [
        { name: "By The Way Hostel Shillong", type: "budget", pricePerNight: 900, rating: 4.4 },
        { name: "Polo Orchid Cherrapunjee", type: "comfort", pricePerNight: 4200, rating: 4.5 },
        { name: "Ri Kynjai Serenity resort", type: "luxury", pricePerNight: 12000, rating: 4.8 }
      ]
    }
  ],

  // static content reused across pages
  interests: ["heritage", "nature", "adventure", "spiritual", "beach", "culture", "food", "offbeat", "romantic", "nightlife"],
  regions: ["North", "South", "West", "Northeast", "Islands"],

  // helper: attach an INR formatter here so every page shares one
  inr(n) {
    return "₹" + Math.round(n).toLocaleString("en-IN");
  },

  byId(id) {
    if (!id) return null;
    var raw = id.toString().trim();
    if (!raw) return null;
    var clean = raw.toLowerCase();
    var alphaClean = clean.replace(/[^a-z0-9]/g, "");
    // 1. Exact id match (case-insensitive)
    var match = this.destinations.find(function (d) { return d.id.toLowerCase() === clean; });
    if (match) return match;
    // 2. Exact name match (case-insensitive)
    match = this.destinations.find(function (d) { return d.name.toLowerCase() === clean; });
    if (match) return match;
    // 3. Alphanumeric match on id or name
    match = this.destinations.find(function (d) {
      return d.id.toLowerCase().replace(/[^a-z0-9]/g, "") === alphaClean ||
        d.name.toLowerCase().replace(/[^a-z0-9]/g, "") === alphaClean;
    });
    if (match) return match;
    // 4. Starts with / includes match
    match = this.destinations.find(function (d) {
      var dName = d.name.toLowerCase();
      var dId = d.id.toLowerCase();
      return dName.indexOf(clean) === 0 || clean.indexOf(dId) === 0 || clean.indexOf(dName) === 0;
    });
    return match || null;
  },

  /* =========================================================
     Sārthi SmartScore Recommendation Engine
     Multi-factor explainable recommendation score (0–100):
       1. User Preference Match   — 30%
       2. Budget Fit              — 20%
       3. Crowd Balance           — 15%
       4. Sustainability          — 15%
       5. Local Economic Impact   — 10%
       6. Rating                  — 10%
     Fully offline, grounded in actual SARTHI_DATA values.
     ========================================================= */
  calculateSmartScore(dest, criteria) {
    if (!dest) return null;
    criteria = criteria || {};
    var userInterests = criteria.interests || [];
    var budgetTier = criteria.budget || "";
    var avoidCrowds = !!criteria.avoidCrowds;

    /* 1. User Preference Match — 30% (Max 30 pts) */
    var matchedTags = [];
    var prefScore = 80; // Baseline when no interests specified
    if (userInterests.length > 0) {
      matchedTags = userInterests.filter(function (t) { return dest.tags.indexOf(t) >= 0; });
      var matchRatio = matchedTags.length / userInterests.length;
      prefScore = matchedTags.length > 0 ? Math.round(matchRatio * 100) : 20;
    }
    var prefPts = Math.round((prefScore / 100) * 30);
    var prefLabel = userInterests.length > 0
      ? (matchedTags.length > 0
        ? "Matches " + matchedTags.length + " of " + userInterests.length + " interests (" + matchedTags.join(", ") + ")"
        : "Different vibe from selected tags (" + dest.tags.slice(0, 2).join(", ") + ")")
      : "Broad appeal across " + dest.tags.slice(0, 3).join(", ");

    /* 2. Budget Fit — 20% (Max 20 pts) */
    var budgetScore = 85; // Baseline when no budget filter
    if (budgetTier === "budget") {
      if (dest.avgDailyCost <= 2300) {
        budgetScore = 100;
      } else if (dest.avgDailyCost <= 3200) {
        budgetScore = Math.round(100 - ((dest.avgDailyCost - 2300) / 900) * 40);
      } else {
        budgetScore = Math.max(20, Math.round(60 - ((dest.avgDailyCost - 3200) / 1000) * 35));
      }
    } else if (budgetTier === "comfort") {
      if (dest.avgDailyCost >= 2300 && dest.avgDailyCost <= 3500) {
        budgetScore = 100;
      } else if (dest.avgDailyCost < 2300) {
        budgetScore = 90; // Spending less than comfort ceiling is advantageous
      } else {
        budgetScore = Math.max(50, Math.round(100 - ((dest.avgDailyCost - 3500) / 700) * 35));
      }
    } else if (budgetTier === "luxury") {
      if (dest.avgDailyCost >= 3200) {
        budgetScore = 100;
      } else if (dest.avgDailyCost >= 2500) {
        budgetScore = 78;
      } else {
        budgetScore = 55;
      }
    }
    var budgetPts = Math.round((budgetScore / 100) * 20);
    var budgetLabel = this.inr(dest.avgDailyCost) + "/day · " +
      (budgetTier ? (budgetTier.charAt(0).toUpperCase() + budgetTier.slice(1) + " fit") : "Balanced cost");

    /* 3. Crowd Balance — 15% (Max 15 pts) */
    var crowdScore = 70;
    if (avoidCrowds) {
      crowdScore = 100 - dest.popularity;
      if (dest.hiddenGem) crowdScore += 8;
      crowdScore = Math.max(10, Math.min(100, crowdScore));
    } else {
      if (dest.popularity <= 70) {
        crowdScore = Math.round(80 + (1 - Math.abs(50 - dest.popularity) / 50) * 20);
      } else {
        crowdScore = Math.max(30, Math.round(100 - (dest.popularity - 70) * 2.8));
      }
    }
    var crowdPts = Math.round((crowdScore / 100) * 15);
    var crowdLabel = dest.popularity + "% crowd index (" +
      (dest.popularity >= 80 ? "High crowd" : dest.popularity >= 70 ? "Busy" : dest.popularity >= 45 ? "Moderate" : "Peaceful") + ")";

    /* 4. Sustainability — 15% (Max 15 pts) */
    var sustScore = Math.max(0, Math.min(100, dest.sustainability));
    var sustPts = Math.round((sustScore / 100) * 15);
    var sustLabel = "Eco score " + dest.sustainability + "/100 (" +
      (dest.sustainability >= 80 ? "Excellent" : dest.sustainability >= 65 ? "Great" : "Fair") + ")";

    /* 5. Local Economic Impact — 10% (Max 10 pts) */
    var localExps = dest.experiences.filter(function (e) { return e.local; });
    var ecoExps = dest.experiences.filter(function (e) { return e.eco; });
    var localRatio = dest.experiences.length > 0 ? (localExps.length / dest.experiences.length) : 0.7;
    var localScore = Math.round(
      (localRatio * 70) +
      Math.min(20, ecoExps.length * 7) +
      (dest.hiddenGem ? 10 : 0)
    );
    localScore = Math.max(30, Math.min(100, localScore));
    var localPts = Math.round((localScore / 100) * 10);
    var localLabel = localExps.length + " community experiences (" + ecoExps.length + " eco-run)";

    /* 6. Rating — 10% (Max 10 pts) */
    var ratingScore = Math.round((dest.rating / 5.0) * 100);
    var ratingPts = Math.round((ratingScore / 100) * 10);
    var ratingLabel = "★ " + dest.rating + " traveller rating";

    /* Total SmartScore (0–100) */
    var total = Math.max(0, Math.min(100, prefPts + budgetPts + crowdPts + sustPts + localPts + ratingPts));
    var scoreLevel = total >= 80 ? "high" : total >= 65 ? "mid" : "fair";

    var breakdown = {
      preferenceMatch: { score: prefPts, max: 30, pct: prefScore, label: prefLabel },
      budgetFit: { score: budgetPts, max: 20, pct: budgetScore, label: budgetLabel },
      crowdBalance: { score: crowdPts, max: 15, pct: crowdScore, label: crowdLabel },
      sustainability: { score: sustPts, max: 15, pct: sustScore, label: sustLabel },
      localEconomicImpact: { score: localPts, max: 10, pct: localScore, label: localLabel },
      rating: { score: ratingPts, max: 10, pct: ratingScore, label: ratingLabel }
    };

    var explanation = this.generateExplanation(dest, criteria, { total: total, breakdown: breakdown });

    return {
      total: total,
      scoreLevel: scoreLevel,
      breakdown: breakdown,
      explanation: explanation
    };
  },

  /* Generate explainable justification covering all 6 dimensions */
  generateExplanation(dest, criteria, scoreObj) {
    criteria = criteria || {};
    var userInterests = criteria.interests || [];
    var matched = userInterests.filter(function (t) { return dest.tags.indexOf(t) >= 0; });

    // 1. Preference
    var prefText = "";
    if (matched.length > 0) {
      prefText = "it matches your " + matched.join(" & ") + " interests";
    } else if (userInterests.length > 0) {
      prefText = "it offers vibrant experiences across " + dest.tags.slice(0, 2).join(" & ");
    } else {
      prefText = "it delivers an ideal blend of " + dest.tags.slice(0, 2).join(" & ");
    }

    // 2. Budget
    var budgetStyle = criteria.budget || "comfort";
    var budgetText = "";
    if (budgetStyle === "budget") {
      budgetText = "fits your budget style at " + this.inr(dest.avgDailyCost) + "/day";
    } else if (budgetStyle === "luxury") {
      budgetText = "matches luxury expectations with heritage suites and fine stays";
    } else {
      budgetText = "fits your budget comfortably at " + this.inr(dest.avgDailyCost) + "/day";
    }

    // 3. Crowd condition
    var crowdText = "";
    if (criteria.avoidCrowds) {
      if (dest.popularity < 50) {
        crowdText = "has low crowd pressure (" + dest.popularity + "% crowd index) for peaceful exploration";
      } else {
        crowdText = "enjoys shoulder-season crowd relief (" + dest.popularity + "% crowd index)";
      }
    } else {
      if (dest.popularity >= 80) {
        crowdText = "is a high-demand iconic hub (" + dest.popularity + "% popularity)";
      } else if (dest.popularity >= 50) {
        crowdText = "maintains a comfortable, lively crowd balance (" + dest.popularity + "% crowd)";
      } else {
        crowdText = "has low crowd pressure (" + dest.popularity + "% crowd index)";
      }
    }

    // 4. Sustainability
    var sustText = dest.sustainability >= 75
      ? "excels in eco-sustainability (" + dest.sustainability + "/100)"
      : "maintains a " + dest.sustainability + "/100 sustainability index";

    // 5. Local experience availability
    var localCount = dest.experiences.filter(function (e) { return e.local; }).length;
    var localText = "provides " + localCount + " community-run experiences";

    // 6. Rating
    var ratingText = "carries a strong ★ " + dest.rating + " traveller rating";

    return "Recommended because " + prefText + ", " + budgetText + ", " + crowdText + ", " + sustText + ", " + localText + ", and " + ratingText + ".";
  },

  /* Find a better-balanced Smart Alternative when popularity >= 75 */
  findSmartAlternative(dest, criteria) {
    if (!dest || dest.popularity < 75) return null;
    var self = this;
    criteria = criteria || {};

    var candidates = this.destinations.filter(function (d) {
      if (d.id === dest.id) return false;
      // Must have lower popularity
      if (d.popularity >= dest.popularity) return false;
      // Reasonable rating threshold
      if (d.rating < 4.2) return false;
      return true;
    });

    if (!candidates.length) return null;

    var scored = candidates.map(function (c) {
      var sharedTags = c.tags.filter(function (t) { return dest.tags.indexOf(t) >= 0; });
      var userTags = (criteria.interests || []).filter(function (t) { return c.tags.indexOf(t) >= 0; });
      var crowdRelief = dest.popularity - c.popularity;
      var costDiff = dest.avgDailyCost - c.avgDailyCost;
      var costScore = costDiff >= 0 ? 25 : Math.max(-20, (costDiff / dest.avgDailyCost) * 35);
      var sustDiff = c.sustainability - dest.sustainability;
      var sustScore = sustDiff >= 0 ? sustDiff * 0.8 : sustDiff * 0.3;
      var gemBonus = c.hiddenGem ? 18 : 0;
      var regionBonus = c.region === dest.region ? 12 : 0;

      var total = (sharedTags.length * 35) + (userTags.length * 15) + (crowdRelief * 0.5) + costScore + sustScore + gemBonus + regionBonus;

      return {
        dest: c,
        score: total,
        sharedTags: sharedTags,
        crowdRelief: crowdRelief,
        costDiff: costDiff,
        sustDiff: sustDiff
      };
    });

    scored.sort(function (a, b) { return b.score - a.score; });
    var top = scored[0];
    if (!top) return null;

    var alt = top.dest;
    var shared = top.sharedTags;
    var themePhrase = shared.length > 0 ? ("Similar " + shared.join(" and ") + " experiences") : "A serene and enriching alternative";
    var crowdPhrase = top.crowdRelief > 0
      ? ("significantly lower crowd pressure (" + alt.popularity + "% vs " + dest.popularity + "%)")
      : "calmer crowd conditions";
    var sustPhrase = top.sustDiff > 0
      ? ("stronger sustainability (" + alt.sustainability + " vs " + dest.sustainability + ")")
      : ("sustainable local footprint (" + alt.sustainability + "/100)");
    var costPhrase = top.costDiff > 0
      ? ("with estimated daily savings of " + self.inr(top.costDiff) + "/day")
      : ("at " + self.inr(alt.avgDailyCost) + "/day");

    var reason = themePhrase + " with " + crowdPhrase + ", " + sustPhrase + ", and " + costPhrase + ".";

    return {
      destination: alt,
      current: dest,
      crowdRelief: top.crowdRelief,
      costDiff: top.costDiff,
      sustDiff: top.sustDiff,
      sharedTags: shared,
      reason: reason
    };
  },

  /* Rank all destinations by SmartScore */
  rankDestinations(criteria) {
    var self = this;
    return this.destinations.map(function (d) {
      return {
        destination: d,
        smartScore: self.calculateSmartScore(d, criteria)
      };
    }).sort(function (a, b) {
      return b.smartScore.total - a.smartScore.total;
    });
  }
};
