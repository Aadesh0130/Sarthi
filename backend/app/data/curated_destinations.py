"""
Mirror of js/data.js's SARTHI_DATA.destinations (Sarthi's single curated
16-destination dataset), limited to the fields the Tourist Flow Rebalancer
needs to consider a curated destination as a candidate alternative: id,
display name, state, region, interest tags, the existing hiddenGem flag,
and the existing popularity/sustainability scores.

WHY THIS FILE EXISTS (read before "fixing" the duplication):
js/data.js is plain browser JavaScript with no build step and no HTTP
endpoint of its own -- the FastAPI backend has no way to read it at request
time. Rather than inventing a second, different set of "hidden gem"
destinations for the backend (explicitly forbidden by the project spec) or
restructuring the whole curated dataset into a fetched-JSON asset (a bigger,
riskier change to a working page-load path that several existing pages
depend on synchronously), this file mirrors the identifying fields of the
SAME 16 named entries, kept in the same order, and is used only as a
candidate SEED for the rebalancer -- never displayed as-is. Every actual
number shown to a user for one of these (tourism pressure, weather, distance,
travel time, real place counts) is computed live for its geocoded
coordinates, exactly like any other candidate; only the name/tags/hiddenGem/
popularity/sustainability identity comes from here.

Known limitation (see final delivery report): if js/data.js's destination
list changes, this file must be updated to match by hand. A follow-up
improvement would extract both to one shared JSON file so they can never
drift -- tracked as a "should be added later" item, not silently duplicated
business logic (no scoring/recommendation logic lives here, only the same
static identity fields already public in the curated dataset).
"""
from typing import TypedDict


class CuratedDestinationSeed(TypedDict):
    id: str
    name: str
    state: str
    region: str
    tags: list[str]
    hidden_gem: bool
    popularity: int
    sustainability: int


CURATED_DESTINATIONS: list[CuratedDestinationSeed] = [
    {"id": "jaipur", "name": "Jaipur", "state": "Rajasthan", "region": "North",
     "tags": ["heritage", "culture", "food"], "hidden_gem": False, "popularity": 88, "sustainability": 62},
    {"id": "udaipur", "name": "Udaipur", "state": "Rajasthan", "region": "North",
     "tags": ["heritage", "romantic", "culture"], "hidden_gem": False, "popularity": 80, "sustainability": 65},
    {"id": "goa", "name": "Goa", "state": "Goa", "region": "West",
     "tags": ["beach", "nightlife", "food"], "hidden_gem": False, "popularity": 92, "sustainability": 48},
    {"id": "rishikesh", "name": "Rishikesh", "state": "Uttarakhand", "region": "North",
     "tags": ["spiritual", "adventure", "nature"], "hidden_gem": False, "popularity": 78, "sustainability": 70},
    {"id": "varanasi", "name": "Varanasi", "state": "Uttar Pradesh", "region": "North",
     "tags": ["spiritual", "heritage", "culture"], "hidden_gem": False, "popularity": 82, "sustainability": 55},
    {"id": "munnar", "name": "Munnar", "state": "Kerala", "region": "South",
     "tags": ["nature", "romantic", "offbeat"], "hidden_gem": False, "popularity": 72, "sustainability": 78},
    {"id": "hampi", "name": "Hampi", "state": "Karnataka", "region": "South",
     "tags": ["heritage", "offbeat", "culture"], "hidden_gem": True, "popularity": 46, "sustainability": 80},
    {"id": "leh", "name": "Leh–Ladakh", "state": "Ladakh", "region": "North",
     "tags": ["adventure", "nature", "spiritual"], "hidden_gem": False, "popularity": 68, "sustainability": 60},
    {"id": "spiti", "name": "Spiti Valley", "state": "Himachal Pradesh", "region": "North",
     "tags": ["offbeat", "adventure", "spiritual"], "hidden_gem": True, "popularity": 34, "sustainability": 88},
    {"id": "andaman", "name": "Andaman Islands", "state": "Andaman & Nicobar", "region": "Islands",
     "tags": ["beach", "adventure", "nature"], "hidden_gem": False, "popularity": 70, "sustainability": 66},
    {"id": "ziro", "name": "Ziro Valley", "state": "Arunachal Pradesh", "region": "Northeast",
     "tags": ["offbeat", "nature", "culture"], "hidden_gem": True, "popularity": 22, "sustainability": 92},
    {"id": "gokarna", "name": "Gokarna", "state": "Karnataka", "region": "West",
     "tags": ["beach", "spiritual", "offbeat"], "hidden_gem": True, "popularity": 40, "sustainability": 74},
    {"id": "darjeeling", "name": "Darjeeling", "state": "West Bengal", "region": "Northeast",
     "tags": ["nature", "heritage", "romantic"], "hidden_gem": False, "popularity": 74, "sustainability": 68},
    {"id": "kutch", "name": "Rann of Kutch", "state": "Gujarat", "region": "West",
     "tags": ["offbeat", "culture", "heritage"], "hidden_gem": True, "popularity": 38, "sustainability": 76},
    {"id": "coorg", "name": "Coorg (Kodagu)", "state": "Karnataka", "region": "South",
     "tags": ["nature", "romantic", "adventure"], "hidden_gem": False, "popularity": 66, "sustainability": 79},
    {"id": "meghalaya", "name": "Meghalaya", "state": "Meghalaya", "region": "Northeast",
     "tags": ["offbeat", "nature", "adventure"], "hidden_gem": True, "popularity": 44, "sustainability": 90},
]
