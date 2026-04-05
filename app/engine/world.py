"""
World building engine — constructs the World object from JSON (Opus output)
and provides a hand-crafted starter world for testing without any API calls.

Handles:
- Parsing the World Builder's JSON into a Location tree (continent → region → city)
- Populating cities with background NPCs (using stats.py / npc.py)
- Creating Road connections between cities with distance/danger estimates
- A hand-crafted starter world for testing without any API calls
"""
import random
import math

from app.data import World, Location, Road, NPC, Stats, Relationship
from app.engine.stats import generate_npc_stats
from app.engine.npc import create_npc, select_npc_model, populate_location, SCHEDULE_TEMPLATES


def build_world_from_json(world_json):
    """
    Take the massive JSON blob from the World Builder (Opus) and turn it
    into a fully populated World object with a spatial tree of locations,
    roads, factions, history, etc.

    Args:
        world_json: dict — the parsed JSON output from the World Builder model.

    Returns:
        A World object with all locations, roads, and metadata populated.
        NPCs are NOT created here — they get created separately via populate_location.
    """
    world = World()

    # --- Basic info ---
    world.name = world_json.get("world", {}).get("name", world_json.get("name", "Unknown World"))
    world.era = world_json.get("world", {}).get("era", world_json.get("era", ""))
    world.tone = world_json.get("world", {}).get("tone", world_json.get("tone", ""))
    world.themes = world_json.get("world", {}).get("themes", world_json.get("themes", []))

    # --- Factions ---
    factions_list = world_json.get("factions", [])
    for fac in factions_list:
        if isinstance(fac, dict):
            fac_name = fac.get("name", "Unknown Faction")
            world.factions[fac_name] = fac

    # --- History ---
    world.history = world_json.get("history", {})

    # --- Intellectual traditions ---
    world.intellectual_traditions = world_json.get("intellectual_traditions", [])

    # --- Religion ---
    world.religion = world_json.get("religion", {})

    # --- Economy ---
    world.economy_info = world_json.get("economy", {})

    # --- Naming conventions ---
    naming = world_json.get("naming_conventions", {})
    world.naming_conventions = naming.get("rules", "") if isinstance(naming, dict) else str(naming)

    # --- Antagonist ---
    world.antagonist = world_json.get("the_antagonist", world_json.get("antagonist", {}))

    # --- Active conflicts ---
    world.active_conflicts = world_json.get("active_conflicts", [])

    # --- Build the spatial tree (continents → regions → cities → buildings) ---
    continents = world_json.get("continents", [])
    for continent in continents:
        if not isinstance(continent, dict):
            continue

        cont_id = f"cont_{continent.get('name', 'unknown').lower().replace(' ', '_')}"
        cont_loc = Location(
            id=cont_id,
            name=continent.get("name", "Unknown"),
            type="continent",
            description=continent.get("cultural_flavor", ""),
            terrain=continent.get("terrain_type", ""),
        )

        regions = continent.get("regions", [])
        for region in regions:
            if not isinstance(region, dict):
                continue

            reg_id = f"reg_{region.get('name', 'unknown').lower().replace(' ', '_')}"
            reg_loc = Location(
                id=reg_id,
                name=region.get("name", "Unknown"),
                type="region",
                description=region.get("geography", ""),
                parent_id=cont_id,
                danger_rating=region.get("danger_rating", 20),
                economy=region.get("economy", ""),
                terrain=region.get("geography", ""),
            )
            cont_loc.children_ids.append(reg_id)
            world.locations[reg_id] = reg_loc

            cities = region.get("cities", [])
            for city in cities:
                if not isinstance(city, dict):
                    continue

                city_id = f"city_{city.get('name', 'unknown').lower().replace(' ', '_')}"
                city_loc = Location(
                    id=city_id,
                    name=city.get("name", "Unknown"),
                    type="city",
                    description=city.get("notable_features", [""])[0] if city.get("notable_features") else "",
                    parent_id=reg_id,
                    economy=city.get("economy", ""),
                    features=city.get("notable_features", []),
                    mood=city.get("mood", ""),
                )
                reg_loc.children_ids.append(city_id)
                world.locations[city_id] = city_loc

        world.locations[cont_id] = cont_loc

    # --- Connect cities with roads ---
    all_cities = [loc for loc in world.locations.values() if loc.type == "city"]
    connect_cities(world, all_cities)

    # --- Create NPCs from named_characters ---
    named_chars = world_json.get("named_characters", [])
    for char_data in named_chars:
        if not isinstance(char_data, dict):
            continue

        # Find or guess location
        char_location = char_data.get("location", "")
        location_id = _resolve_location(world, char_location)
        if not location_id:
            # Just use the first city
            for loc_id, loc in world.locations.items():
                if loc.type == "city":
                    location_id = loc_id
                    break

        fate = char_data.get("fate", 0.3)
        occupation = char_data.get("occupation", "merchant")
        social_class = _guess_social_class(occupation, fate)

        npc = create_npc(
            world, location_id,
            fate=fate,
            occupation=occupation,
            social_class=social_class,
            name=char_data.get("name", ""),
            age=char_data.get("age", None),
        )

        # Apply extra data from the world builder
        if char_data.get("faction"):
            npc.faction = char_data["faction"]
        if char_data.get("secret"):
            npc.secret = char_data["secret"]
        if char_data.get("brief_description"):
            npc.backstory = char_data["brief_description"]

    # --- Populate cities with background NPCs ---
    for city in all_cities:
        populate_city(world, city)

    return world


def _guess_social_class(occupation, fate):
    """Rough mapping from occupation + fate to social class."""
    class_map = {
        "noble": "noble", "king": "royal", "queen": "royal", "prince": "royal",
        "princess": "royal", "lord": "noble", "lady": "noble", "general": "noble",
        "merchant": "merchant", "scholar": "merchant", "priest": "merchant",
        "spy": "merchant", "healer": "merchant",
        "soldier": "working", "farmer": "working", "blacksmith": "working",
        "thief": "working", "artist": "working",
        "beggar": "destitute",
    }
    sc = class_map.get(occupation.lower(), "working")
    # High-fate characters might be from higher classes
    if fate > 0.7 and sc == "working":
        sc = "merchant"
    return sc


# ============================================================
# POPULATE CITIES WITH BACKGROUND NPCs
# ============================================================

def populate_city(world, city_location):
    """
    Spawn background NPCs into a city based on its economy/features.
    Named NPCs are created separately — this fills in the everyday people.

    Args:
        world: the World object
        city_location: Location object (type="city")

    Returns:
        List of created NPC objects.
    """
    # Decide how many NPCs based on city features. Default: 15.
    # Trade hubs get more people, small farming towns get fewer.
    economy = (city_location.economy or "").lower()
    if "hub" in economy or "trade" in economy or "port" in economy:
        npc_count = random.randint(18, 25)
    elif "agricultural" in economy or "farming" in economy:
        npc_count = random.randint(8, 14)
    elif "military" in economy or "fortress" in economy:
        npc_count = random.randint(12, 18)
    else:
        npc_count = random.randint(12, 18)

    # Pick occupation weights based on city economy
    occ_weights = _occupation_weights_for_city(city_location)
    return populate_location(world, city_location.id, npc_count, occ_weights)


def _occupation_weights_for_city(city_location):
    """
    Pick NPC occupation distribution based on the city's economy and features.
    Trade cities get more merchants, military cities get more soldiers, etc.
    """
    economy = (city_location.economy or "").lower()
    features_text = " ".join(city_location.features).lower() if city_location.features else ""

    if "trade" in economy or "port" in economy:
        return {
            "merchant": 0.30, "farmer": 0.10, "soldier": 0.10, "thief": 0.08,
            "scholar": 0.05, "priest": 0.04, "blacksmith": 0.08, "healer": 0.04,
            "artist": 0.05, "beggar": 0.06, "noble": 0.05, "spy": 0.05,
        }
    elif "military" in economy or "fortress" in economy:
        return {
            "soldier": 0.35, "blacksmith": 0.12, "merchant": 0.10, "farmer": 0.08,
            "healer": 0.08, "priest": 0.05, "thief": 0.05, "spy": 0.05,
            "beggar": 0.04, "noble": 0.03, "artist": 0.03, "scholar": 0.02,
        }
    elif "university" in features_text or "learning" in economy:
        return {
            "scholar": 0.25, "priest": 0.10, "merchant": 0.12, "artist": 0.10,
            "farmer": 0.08, "healer": 0.08, "soldier": 0.05, "beggar": 0.06,
            "noble": 0.06, "thief": 0.04, "blacksmith": 0.04, "spy": 0.02,
        }
    elif "agricultural" in economy or "farming" in economy:
        return {
            "farmer": 0.40, "merchant": 0.12, "blacksmith": 0.10, "priest": 0.06,
            "soldier": 0.06, "healer": 0.06, "beggar": 0.05, "thief": 0.04,
            "artist": 0.03, "noble": 0.03, "scholar": 0.03, "spy": 0.02,
        }

    # Default balanced distribution — populate_location uses its own default
    return None


# ============================================================
# ROAD CONNECTIONS BETWEEN CITIES
# ============================================================

def connect_cities(world, cities):
    """
    Create Road objects between cities. Cities in the same region are always
    connected. Cities in neighboring regions (same continent) have a chance
    of a cross-region road.

    Args:
        world: the World object
        cities: list of city Location objects
    """
    if len(cities) < 2:
        return

    # Group cities by their parent region
    by_region = {}
    for city in cities:
        region_id = city.parent_id
        if region_id not in by_region:
            by_region[region_id] = []
        by_region[region_id].append(city)

    # Connect all cities within the same region (short roads)
    for region_id, region_cities in by_region.items():
        for i in range(len(region_cities)):
            for j in range(i + 1, len(region_cities)):
                distance = _estimate_distance(region_cities[i], region_cities[j], same_region=True)
                road = _make_road(region_cities[i], region_cities[j], distance)
                world.roads.append(road)

    # Connect one city per region to a city in neighboring regions (same continent)
    region_ids = list(by_region.keys())
    for i in range(len(region_ids)):
        for j in range(i + 1, len(region_ids)):
            reg_a = world.locations.get(region_ids[i])
            reg_b = world.locations.get(region_ids[j])
            if not reg_a or not reg_b:
                continue

            # Only auto-connect regions on the same continent
            same_continent = (reg_a.parent_id == reg_b.parent_id)
            if same_continent or random.random() < 0.15:
                city_a = by_region[region_ids[i]][0]
                city_b = by_region[region_ids[j]][0]
                distance = _estimate_distance(city_a, city_b, same_region=False)
                road = _make_road(city_a, city_b, distance)
                world.roads.append(road)


def _estimate_distance(city_a, city_b, same_region=True):
    """
    Estimate km distance between two cities.
    Uses coordinates if available, otherwise a plausible random distance.
    """
    # Try coordinate-based distance if both cities have real coords
    if city_a.coordinates != (0, 0) and city_b.coordinates != (0, 0):
        dx = city_a.coordinates[0] - city_b.coordinates[0]
        dy = city_a.coordinates[1] - city_b.coordinates[1]
        straight_line = math.sqrt(dx * dx + dy * dy)
        return straight_line * 1.3  # roads are ~30% longer than straight line

    # Fallback: random plausible distance
    if same_region:
        return random.uniform(30, 120)   # 1-4 days on foot
    else:
        return random.uniform(150, 500)  # 5-17 days on foot


def _make_road(city_a, city_b, distance_km):
    """Create a Road between two cities with travel time and danger."""
    travel_days = distance_km / 30.0  # 30 km/day on foot

    # Danger scales with distance and the danger of both endpoints
    base_danger = max(city_a.danger_rating, city_b.danger_rating)
    distance_danger = min(50, int(distance_km / 10))
    danger = min(100, base_danger + distance_danger)

    return Road(
        from_id=city_a.id,
        to_id=city_b.id,
        distance_km=round(distance_km, 1),
        terrain="road",
        travel_days_foot=round(travel_days, 1),
        danger_rating=danger,
    )


# ============================================================
# LOCATION LOOKUP HELPER
# ============================================================

def _resolve_location(world, location_name):
    """
    Find a location ID by name (case-insensitive partial match).
    Tries exact match first, then partial match.
    Returns empty string if nothing found.
    """
    if not location_name:
        return ""

    name_lower = location_name.lower()

    # Exact match
    for loc_id, loc in world.locations.items():
        if loc.name.lower() == name_lower:
            return loc_id

    # Partial match (either direction)
    for loc_id, loc in world.locations.items():
        if name_lower in loc.name.lower() or loc.name.lower() in name_lower:
            return loc_id

    return ""


# ============================================================
# ON-DEMAND CITY DETAIL GENERATION
# ============================================================

def generate_city_details(city_location, world):
    """
    Add buildings, rooms, and other interior locations to a city.
    Called after the world is built to flesh out cities the player enters.

    Args:
        city_location: Location object (type="city")
        world: World object

    Returns:
        List of new Location objects that were added.
    """
    city_id = city_location.id
    new_locations = []

    # Standard buildings every city has
    standard_buildings = [
        {"name": "The Common House", "type": "building", "subtype": "tavern",
         "description": "Ale-stained tables, a crackling fire, the smell of stew.",
         "mood": "rowdy"},
        {"name": "Market Square", "type": "building", "subtype": "market",
         "description": "Stalls and carts, the hum of commerce and argument.",
         "mood": "busy"},
        {"name": "Temple", "type": "building", "subtype": "temple",
         "description": "Quiet stone, the smell of incense, flickering candles.",
         "mood": "solemn"},
        {"name": "Barracks", "type": "building", "subtype": "barracks",
         "description": "Military discipline. Racks of weapons, training dummies.",
         "mood": "tense"},
    ]

    # Bigger cities get more buildings
    if city_location.economy in ("trade_hub", "wealthy"):
        standard_buildings.extend([
            {"name": "Library", "type": "building", "subtype": "library",
             "description": "Dusty shelves, the rustle of pages, whispered conversations.",
             "mood": "quiet"},
            {"name": "Docks", "type": "building", "subtype": "docks",
             "description": "Salt air, creaking wood, sailors calling to each other.",
             "mood": "chaotic"},
        ])

    for bldg in standard_buildings:
        bldg_id = f"{city_id}_{bldg['subtype']}"
        loc = Location(
            id=bldg_id,
            name=bldg["name"],
            type=bldg["type"],
            description=bldg["description"],
            parent_id=city_id,
            mood=bldg.get("mood", ""),
        )
        world.locations[bldg_id] = loc
        city_location.children_ids.append(bldg_id)
        new_locations.append(loc)

    return new_locations


def generate_starter_world():
    """
    Create a small hand-crafted World for testing — NO API calls.
    Two cities connected by a road, ~20 NPCs, a tavern, a market, some variety.
    This is the "boot up and play immediately" world.

    Returns:
        A fully populated World object ready for gameplay.
    """
    world = World(
        name="The Shattered Coast",
        era="The Iron Quiet — 40 years after the last great war",
        tone="grim but not hopeless",
        themes=["the weight of memory", "what peace costs", "who deserves power"],
        current_day=1,
        time_slot="morning",
        season="autumn",
    )

    # --- Continent ---
    continent = Location(
        id="cont_ashenmere",
        name="Ashenmere",
        type="continent",
        description="A rain-swept land of grey coasts and old forests.",
        terrain="temperate",
    )
    world.locations[continent.id] = continent

    # --- Region ---
    region = Location(
        id="reg_duskwater",
        name="The Duskwater Reach",
        type="region",
        description="River valleys and fishing villages, overshadowed by the ruins of Fort Saelen.",
        parent_id="cont_ashenmere",
        danger_rating=25,
        economy="trade",
        terrain="river_valley",
    )
    continent.children_ids.append(region.id)
    world.locations[region.id] = region

    # --- City 1: Thornwall ---
    thornwall = Location(
        id="city_thornwall",
        name="Thornwall",
        type="city",
        description="A walled market town at the river crossing. Prosperous but nervous.",
        parent_id="reg_duskwater",
        economy="trade_hub",
        features=["stone walls", "river bridge", "weekly market", "old watchtower"],
        mood="cautious prosperity",
        coordinates=(100, 100),
    )
    region.children_ids.append(thornwall.id)
    world.locations[thornwall.id] = thornwall

    # Thornwall buildings
    tw_tavern = Location(id="city_thornwall_tavern", name="The Bent Nail",
        type="building", description="Warm light, cheap ale, loud arguments. The heart of Thornwall after dark.",
        parent_id="city_thornwall", mood="rowdy")
    tw_market = Location(id="city_thornwall_market", name="Bridge Market",
        type="building", description="Stalls crowd both sides of the bridge approach. Fish, grain, tools, gossip.",
        parent_id="city_thornwall", mood="busy")
    tw_temple = Location(id="city_thornwall_temple", name="Chapel of the Quiet",
        type="building", description="A small stone chapel. The priest keeps it clean but rarely full.",
        parent_id="city_thornwall", mood="solemn")
    tw_barracks = Location(id="city_thornwall_barracks", name="Town Guard Barracks",
        type="building", description="A squat building near the gate. Six guards, not enough.",
        parent_id="city_thornwall", mood="tense")
    tw_forge = Location(id="city_thornwall_forge", name="Harren's Forge",
        type="building", description="The ring of hammer on iron. Harren works dawn to dusk.",
        parent_id="city_thornwall", mood="industrious")
    tw_library = Location(id="city_thornwall_library", name="The Archive",
        type="building", description="Three rooms of books, mostly trade records. But some older things, deeper in.",
        parent_id="city_thornwall", mood="quiet")

    for bldg in [tw_tavern, tw_market, tw_temple, tw_barracks, tw_forge, tw_library]:
        world.locations[bldg.id] = bldg
        thornwall.children_ids.append(bldg.id)

    # --- City 2: Millhaven ---
    millhaven = Location(
        id="city_millhaven",
        name="Millhaven",
        type="city",
        description="A smaller town upstream. Grain mills, apple orchards, fewer strangers.",
        parent_id="reg_duskwater",
        economy="agricultural",
        features=["water mills", "apple orchards", "old stone bridge"],
        mood="quiet and wary",
        coordinates=(160, 130),
    )
    region.children_ids.append(millhaven.id)
    world.locations[millhaven.id] = millhaven

    # Millhaven buildings
    mh_tavern = Location(id="city_millhaven_tavern", name="The Orchard Rest",
        type="building", description="Cider instead of ale. Quieter than Thornwall's place. The locals stare.",
        parent_id="city_millhaven", mood="suspicious")
    mh_market = Location(id="city_millhaven_market", name="Mill Square",
        type="building", description="A modest square. Flour, apples, preserved fish. Not much else.",
        parent_id="city_millhaven", mood="sparse")
    mh_temple = Location(id="city_millhaven_temple", name="The Stone Circle",
        type="building", description="Older than the town. Moss-covered stones in a clearing. People still come.",
        parent_id="city_millhaven", mood="ancient")

    for bldg in [mh_tavern, mh_market, mh_temple]:
        world.locations[bldg.id] = bldg
        millhaven.children_ids.append(bldg.id)

    # --- Road connecting the two cities ---
    road = Road(
        from_id="city_thornwall",
        to_id="city_millhaven",
        distance_km=70,
        terrain="road",
        travel_days_foot=2.5,
        danger_rating=30,
    )
    world.roads.append(road)

    # --- Factions ---
    world.factions = {
        "Thornwall Merchants' Guild": {
            "name": "Thornwall Merchants' Guild",
            "type": "economic",
            "strength": 60,
            "goals": ["control river trade", "keep taxes low"],
            "territory": "Thornwall and the river road",
        },
        "The Ashen Guard": {
            "name": "The Ashen Guard",
            "type": "military",
            "strength": 40,
            "goals": ["protect the Reach", "rebuild Fort Saelen"],
            "territory": "The Duskwater Reach",
        },
        "The Quiet Hand": {
            "name": "The Quiet Hand",
            "type": "secret",
            "strength": 25,
            "goals": ["unknown — something about the old war"],
            "territory": "rumored in both towns",
        },
    }

    # --- History ---
    world.history = {
        "creation_myth": "The world was spoken into being, and each word became a river.",
        "recent_history": [
            "40 years ago: The Iron War ended. Fort Saelen was destroyed.",
            "30 years ago: Thornwall rebuilt its walls. Refugees settled.",
            "10 years ago: The Merchants' Guild rose to power. Trade boomed.",
            "2 years ago: Strange disappearances along the river road.",
            "Now: Tensions between the Guild and the Ashen Guard over jurisdiction.",
        ],
    }

    # --- Named NPCs ---
    # These are hand-crafted with specific fates and roles

    # HIGH FATE — the important ones
    # Maren Fell — former war hero, now town guard captain
    maren = create_npc(world, "city_thornwall_barracks", fate=0.7,
                       occupation="soldier", social_class="working",
                       name="Maren Fell", age=58)
    maren.faction = "The Ashen Guard"
    maren.faction_loyalty = 85
    maren.backstory = "Fought at Fort Saelen. Survived when most didn't. Drinks to forget but never misses a shift."
    maren.secret = "She knows what really destroyed the Fort — and it wasn't the enemy."
    maren.temperament = "melancholy"

    # Edrin Voss — merchant guild leader, charming and ruthless
    edrin = create_npc(world, "city_thornwall_market", fate=0.65,
                       occupation="merchant", social_class="merchant",
                       name="Edrin Voss", age=44)
    edrin.faction = "Thornwall Merchants' Guild"
    edrin.faction_loyalty = 90
    edrin.backstory = "Built the Guild from nothing. Everyone owes him a favor. Smiles too much."
    edrin.secret = "He's been paying bandits to attack Millhaven caravans — to control the trade routes."
    edrin.temperament = "cheerful"

    # Dalla Cairn — the drunk philosopher
    dalla = create_npc(world, "city_thornwall_tavern", fate=0.6,
                       occupation="scholar", social_class="working",
                       name="Dalla Cairn", age=67)
    dalla.backstory = "Once a renowned philosopher at the capital's academy. Now she drinks at The Bent Nail and argues with farmers. Brilliant, ruined, hiding in plain sight."
    dalla.secret = "She was exiled for publishing a proof that the gods are a mathematical impossibility."
    dalla.temperament = "volatile"

    # Kael Strand — young, ambitious, potential companion
    kael = create_npc(world, "city_thornwall_forge", fate=0.5,
                      occupation="blacksmith", social_class="working",
                      name="Kael Strand", age=22)
    kael.backstory = "Apprentice blacksmith with restless hands and a bigger world in his head. Wants to leave Thornwall but can't abandon his ailing master."
    kael.secret = "He's been forging weapons for someone outside of town. He doesn't know who they're for."
    kael.temperament = "calm"

    # Nessa Birch — Millhaven healer, quietly powerful
    nessa = create_npc(world, "city_millhaven_temple", fate=0.55,
                       occupation="healer", social_class="working",
                       name="Nessa Birch", age=35)
    nessa.backstory = "The only healer for miles. People come to the Stone Circle for her, not the old gods. She knows everyone's pain."
    nessa.secret = "She can do things with herbs that shouldn't be possible. The old stones speak to her."
    nessa.temperament = "calm"

    # MEDIUM FATE — interesting but not world-shaping
    sienna = create_npc(world, "city_thornwall_tavern", fate=0.3,
                        occupation="thief", social_class="working",
                        name="Sienna Wren", age=26)
    sienna.backstory = "Quick fingers, quicker mouth. Steals from merchants, gives some to the desperate."
    sienna.secret = "She works for the Quiet Hand but doesn't know their real purpose."

    father_orin = create_npc(world, "city_thornwall_temple", fate=0.25,
                             occupation="priest", social_class="merchant",
                             name="Father Orin Marsh", age=52)
    father_orin.backstory = "Patient, kind, but his chapel empties a little more each year."
    father_orin.secret = "He's lost his faith. Performs the rituals from habit."

    # LOW FATE — background characters with just enough to exist
    # Tavern regulars, market vendors, guards
    create_npc(world, "city_thornwall_tavern", fate=0.05, occupation="farmer",
               social_class="working", name="Brell Stone", age=40)
    create_npc(world, "city_thornwall_market", fate=0.05, occupation="merchant",
               social_class="merchant", name="Hild Frost", age=55)
    create_npc(world, "city_thornwall_barracks", fate=0.05, occupation="soldier",
               social_class="working", name="Gareth Pike", age=28)
    create_npc(world, "city_thornwall_barracks", fate=0.0, occupation="soldier",
               social_class="working", name="Ronan Hart", age=33)

    # Millhaven NPCs
    create_npc(world, "city_millhaven_tavern", fate=0.1, occupation="farmer",
               social_class="working", name="Aldric Glen", age=45)
    create_npc(world, "city_millhaven_market", fate=0.05, occupation="farmer",
               social_class="working", name="Petra Reed", age=38)
    create_npc(world, "city_millhaven_market", fate=0.0, occupation="merchant",
               social_class="merchant", name="Finn Cairn", age=50)

    # Fill in some more background NPCs to reach ~20 total
    create_npc(world, "city_thornwall_market", fate=0.0, occupation="beggar",
               social_class="destitute", name="Old Wren", age=72)
    create_npc(world, "city_thornwall_forge", fate=0.0, occupation="blacksmith",
               social_class="working", name="Harren Forge", age=61)
    create_npc(world, "city_thornwall_library", fate=0.15, occupation="scholar",
               social_class="merchant", name="Leif Rune", age=34)
    create_npc(world, "city_millhaven_temple", fate=0.0, occupation="farmer",
               social_class="working", name="Vara Dell", age=29)

    # --- Lore ---
    world.lore_index = {
        "iron_war": "A devastating conflict 40 years ago that reshaped the continent.",
        "fort_saelen": "A fortress that fell during the Iron War. Its ruins are avoided.",
        "the_quiet_hand": "A secret organization. No one knows what they want.",
        "the_stone_circle": "Ancient stones in Millhaven. Predates human settlement.",
        "the_merchants_guild": "Controls trade in Thornwall. Led by Edrin Voss.",
    }

    return world
