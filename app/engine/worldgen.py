"""
Procedural World Generator — builds a full spatial tree with real coordinates.
Creates continents, regions, cities, districts, and buildings with realistic
distances and populations. No model call — pure Python, instant.

The AI world builder (Opus) provides names, lore, and flavor.
This module provides the STRUCTURE — coordinates, populations, roads, scale.

Scale reference:
  - Continent: ~2000-4000km across
  - Region: ~200-600km across
  - Between cities: 30-150km (1-5 days travel on foot)
  - City: 2-8km across
  - District: 0.3-1km across
  - Building: 10-50m across
  - Room: 3-8m across
"""
import math
import random
from app.data import Location, Road, World, NPC, Stats


# ============================================================
# TEMPLATES — what goes inside each location type
# ============================================================

REGION_TYPES = ["coastal", "plains", "forest", "mountain", "river valley", "steppe", "swamp"]

CITY_TEMPLATES = {
    "capital": {
        "population_range": (80_000, 300_000),
        "districts": ["market", "noble", "temple", "docks", "barracks", "university"],
        "danger": 15,
    },
    "major_city": {
        "population_range": (20_000, 80_000),
        "districts": ["market", "residential", "temple", "docks"],
        "danger": 20,
    },
    "town": {
        "population_range": (2_000, 15_000),
        "districts": ["market", "residential", "temple"],
        "danger": 15,
    },
    "village": {
        "population_range": (200, 2_000),
        "districts": ["square"],
        "danger": 10,
    },
    "outpost": {
        "population_range": (50, 300),
        "districts": ["yard"],
        "danger": 35,
    },
}

# Buildings that appear in each district type
DISTRICT_BUILDINGS = {
    "market": ["tavern", "general store", "blacksmith"],
    "noble": ["manor house", "gardens", "guard house"],
    "temple": ["temple", "graveyard", "hospice"],
    "docks": ["harbor master", "tavern", "warehouse"],
    "slums": ["flophouse", "pawnshop", "alley"],
    "barracks": ["barracks", "training yard", "armory"],
    "craftsmen": ["workshop", "tanner", "pottery"],
    "university": ["library", "lecture hall", "observatory"],
    "residential": ["inn", "chapel", "well"],
    "square": ["tavern", "market stalls", "notice board"],
    "yard": ["watchtower", "stable"],
}

# Name parts for procedural generation
NAME_PREFIXES = [
    "Thorn", "Iron", "Silver", "Stone", "Black", "White", "Red", "Grey",
    "Oak", "Ash", "Moss", "Storm", "Frost", "Dawn", "Dusk", "Shadow",
    "Raven", "Wolf", "Hawk", "Bear", "Bone", "Rust", "Salt", "Wind",
    "Hollow", "Amber", "Cinder", "Flint", "Marble", "Copper",
]

NAME_SUFFIXES = [
    "wall", "gate", "keep", "hold", "ford", "haven", "port", "bridge",
    "march", "moor", "wick", "dale", "fell", "crest", "vale", "brook",
    "ton", "burg", "shire", "field", "wood", "water", "stone", "reach",
]

TAVERN_NAMES = [
    "The Quiet Drum", "The Bent Nail", "The Rusty Anchor", "The Black Boar",
    "The Sleeping Fox", "The Last Lantern", "The Three Crows", "The Iron Mug",
    "The Broken Wheel", "The Singing Stone", "The Dead Man's Rest", "The Lucky Coin",
    "The Old Oak", "The Wanderer's End", "The Blind Horse", "The Red Door",
]

REGION_NAMES = [
    "The Northern Reaches", "The Eastern Marches", "The Sunken Coast",
    "The Iron Hills", "The Greenwood", "The Ashlands", "The Golden Plains",
    "The Thornwild", "The Mistfen", "The Stormbreak", "The Quiet Valleys",
    "The Shattered Peaks", "The Saltwaste", "The Ember Fields",
]


def generate_world_structure(world: World, num_regions=4, cities_per_region=3):
    """
    Generate a full spatial tree with coordinates, populations, and roads.
    Uses existing world.name/era/tone if set (from AI world builder).
    Fills in the geographic structure that the AI doesn't handle.
    """
    # Use a continent as the root
    continent_id = "continent_main"
    world.locations[continent_id] = Location(
        id=continent_id,
        name=world.name or _gen_name(),
        type="continent",
        description=f"A vast continent in the era of {world.era or 'uncertainty'}.",
        population=sum(random.randint(100_000, 500_000) for _ in range(num_regions)),
        coordinates=(2500, 2500),
    )

    used_names = set()
    region_ids = []

    # --- Generate regions ---
    for i in range(num_regions):
        region_name = random.choice([n for n in REGION_NAMES if n not in used_names])
        used_names.add(region_name)
        region_id = f"region_{i}"
        region_type = random.choice(REGION_TYPES)

        # Spread regions across the continent
        angle = (i / num_regions) * 2 * math.pi + random.uniform(-0.3, 0.3)
        r = random.uniform(400, 900)
        rx = 2500 + r * math.cos(angle)
        ry = 2500 + r * math.sin(angle)

        world.locations[region_id] = Location(
            id=region_id, name=region_name, type="region",
            description=f"A {region_type} region.",
            parent_id=continent_id,
            terrain=region_type,
            population=random.randint(100_000, 500_000),
            coordinates=(rx, ry),
            danger_rating=random.randint(10, 40),
        )
        world.locations[continent_id].children_ids.append(region_id)
        region_ids.append(region_id)

        # --- Generate cities in this region ---
        # First city is always a capital or major city
        city_types = ["capital"] + ["major_city"] * (cities_per_region > 2) + \
                     ["town"] * max(0, cities_per_region - 2) + \
                     ["village"] * random.randint(1, 2)

        city_ids = []
        for j, ctype in enumerate(city_types[:cities_per_region + random.randint(0, 2)]):
            template = CITY_TEMPLATES.get(ctype, CITY_TEMPLATES["town"])
            city_name = _gen_name()
            while city_name in used_names:
                city_name = _gen_name()
            used_names.add(city_name)

            city_id = f"city_{i}_{j}"
            pop = random.randint(*template["population_range"])

            # Place city within region
            c_angle = (j / max(1, cities_per_region)) * 2 * math.pi + random.uniform(-0.5, 0.5)
            c_r = random.uniform(40, 150)
            cx = rx + c_r * math.cos(c_angle)
            cy = ry + c_r * math.sin(c_angle)

            world.locations[city_id] = Location(
                id=city_id, name=city_name, type="city",
                description=f"A {ctype.replace('_', ' ')} in {region_name}.",
                parent_id=region_id,
                population=pop,
                coordinates=(cx, cy),
                danger_rating=template["danger"],
                economy=random.choice(["trade", "agriculture", "mining", "fishing", "crafts"]),
            )
            world.locations[region_id].children_ids.append(city_id)
            city_ids.append(city_id)

            # --- Generate districts ---
            district_types = template["districts"]
            for k, dtype in enumerate(district_types):
                district_id = f"dist_{i}_{j}_{k}"
                d_angle = (k / len(district_types)) * 2 * math.pi + random.uniform(-0.3, 0.3)
                d_r = random.uniform(0.5, 2.0)  # districts 0.5-2km from center

                world.locations[district_id] = Location(
                    id=district_id,
                    name=f"{city_name} {dtype.title()}",
                    type="district",
                    description=f"The {dtype} district of {city_name}.",
                    parent_id=city_id,
                    population=pop // len(district_types),
                    coordinates=(cx + d_r * math.cos(d_angle), cy + d_r * math.sin(d_angle)),
                )
                world.locations[city_id].children_ids.append(district_id)

                # --- Generate buildings ---
                buildings = DISTRICT_BUILDINGS.get(dtype, ["building"])
                for m, btype in enumerate(buildings):
                    building_id = f"bld_{i}_{j}_{k}_{m}"
                    b_name = btype.title()

                    # Taverns get unique names
                    if btype == "tavern":
                        available = [n for n in TAVERN_NAMES if n not in used_names]
                        if available:
                            b_name = random.choice(available)
                            used_names.add(b_name)

                    b_angle = (m / len(buildings)) * 2 * math.pi + random.uniform(-0.5, 0.5)
                    b_r = random.uniform(0.05, 0.3)  # buildings 50-300m from district center
                    bx = world.locations[district_id].coordinates[0] + b_r * math.cos(b_angle)
                    by = world.locations[district_id].coordinates[1] + b_r * math.sin(b_angle)

                    world.locations[building_id] = Location(
                        id=building_id, name=b_name, type="building",
                        description=f"A {btype} in {city_name}'s {dtype} district.",
                        parent_id=district_id,
                        population=random.randint(3, 30),
                        coordinates=(bx, by),
                    )
                    world.locations[district_id].children_ids.append(building_id)

    # --- Generate roads between cities ---
    _generate_inter_city_roads(world, region_ids)

    # --- Generate political structure ---
    _generate_politics(world, region_ids)

    # --- Initialize economy ---
    from app.engine.economy_sim import initialize_economy
    initialize_economy(world)

    return world


# ============================================================
# POLITICAL STRUCTURE — factions, alliances, rulers
# ============================================================

HOUSE_NAMES = [
    "Ashford", "Blackwood", "Crestfall", "Dawnmere", "Ember",
    "Frostborn", "Greymane", "Hawkridge", "Ironvale", "Kestrel",
    "Lionsgate", "Morrow", "Nightingale", "Oakheart", "Pryor",
    "Ravenscar", "Stonebridge", "Thorn", "Umber", "Voss",
    "Warden", "Yarrow",
]

FIRST_NAMES_M = [
    "Aldric", "Brennan", "Calder", "Dorian", "Edmund", "Falk",
    "Gareth", "Hadrian", "Ivar", "Jorin", "Kael", "Leoric",
    "Maren", "Nolan", "Orin", "Percival", "Renn", "Silas",
    "Theron", "Varn", "Willem",
]

FIRST_NAMES_F = [
    "Adara", "Brenna", "Celia", "Daria", "Elena", "Freya",
    "Gwendolyn", "Helena", "Irena", "Jessa", "Katria", "Lyra",
    "Miriel", "Nessa", "Orla", "Petra", "Ravenna", "Sera",
    "Thea", "Vara", "Wren",
]

GOVERNMENT_TYPES = ["monarchy", "oligarchy", "theocracy", "republic", "military junta"]

RELATION_TYPES = ["allied", "neutral", "hostile", "vassal", "rival", "trade partners"]


def _generate_politics(world: World, region_ids: list):
    """Generate ruling houses, alliances, and enemies for each region."""
    used_houses = set()
    region_factions = {}

    for rid in region_ids:
        region = world.locations[rid]
        # Pick a ruling house
        house = random.choice([h for h in HOUSE_NAMES if h not in used_houses])
        used_houses.add(house)

        # Generate ruler
        is_female = random.random() < 0.4
        first = random.choice(FIRST_NAMES_F if is_female else FIRST_NAMES_M)
        ruler_name = f"{first} {house}"
        ruler_age = random.randint(28, 70)
        title = random.choice(["King", "Queen", "Duke", "Duchess", "Lord", "Lady",
                                "Governor", "Warden", "High Marshal"])

        gov_type = random.choice(GOVERNMENT_TYPES)

        # Capital city (first/largest city in the region)
        cities = [world.locations[cid] for cid in region.children_ids
                  if cid in world.locations and world.locations[cid].type == "city"]
        capital = max(cities, key=lambda c: c.population) if cities else None

        faction_id = f"house_{house.lower()}"
        region_factions[rid] = faction_id

        # Generate the ruler as an NPC
        from app.engine.npc_life import generate_npc
        ruler_role = "king" if title in ("King", "Queen") else "noble"
        ruler = generate_npc(ruler_role, name=ruler_name, age=ruler_age,
                             location=capital.id if capital else "")
        ruler.faction = faction_id
        ruler.faction_loyalty = 100
        world.npcs[ruler.id] = ruler

        # Build faction data
        world.factions[faction_id] = {
            "name": f"House {house}",
            "ruler": ruler_name,
            "ruler_id": ruler.id,
            "ruler_age": ruler_age,
            "title": title,
            "house": house,
            "government": gov_type,
            "region": rid,
            "region_name": region.name,
            "capital": capital.id if capital else "",
            "capital_name": capital.name if capital else "",
            "strength": random.choice(["weak", "moderate", "strong", "dominant"]),
            "goals": [],
            "allies": [],
            "enemies": [],
            "lineage": _generate_lineage(house),
            "population": region.population,
        }

    # Generate inter-faction relationships
    faction_ids = list(region_factions.values())
    for i, fid_a in enumerate(faction_ids):
        for fid_b in faction_ids[i + 1:]:
            # Roll relationship
            roll = random.random()
            if roll < 0.15:
                rel = "allied"
            elif roll < 0.35:
                rel = "hostile"
            elif roll < 0.50:
                rel = "rival"
            elif roll < 0.65:
                rel = "trade partners"
            else:
                rel = "neutral"

            world.factions[fid_a]["allies" if rel == "allied" else
                                   "enemies" if rel in ("hostile", "rival") else
                                   "goals"].append(
                f"{rel} with {world.factions[fid_b]['name']}"
            )
            world.factions[fid_b]["allies" if rel == "allied" else
                                   "enemies" if rel in ("hostile", "rival") else
                                   "goals"].append(
                f"{rel} with {world.factions[fid_a]['name']}"
            )

            # If hostile, add to active conflicts
            if rel == "hostile":
                world.active_conflicts.append({
                    "name": f"War between {world.factions[fid_a]['name']} and {world.factions[fid_b]['name']}",
                    "current_status": random.choice([
                        "open warfare", "border skirmishes",
                        "cold war — armies massing", "recently declared"
                    ]),
                    "factions": [fid_a, fid_b],
                })


def _generate_lineage(house_name: str) -> list:
    """Generate 2-3 generations of lineage for a ruling house."""
    lineage = []
    # Grandparent
    gp_name = f"{random.choice(FIRST_NAMES_M)} {house_name}"
    lineage.append(f"{gp_name} (founder, deceased)")
    # Parent
    p_name = f"{random.choice(FIRST_NAMES_M + FIRST_NAMES_F)} {house_name}"
    lineage.append(f"{p_name} (previous ruler, {'deceased' if random.random() < 0.6 else 'abdicated'})")
    return lineage


def _generate_inter_city_roads(world: World, region_ids: list):
    """Generate roads between cities. Siblings are always connected.
    Some cross-region roads for major trade routes."""
    from app.engine.geography import distance_between

    seen = set()

    for region_id in region_ids:
        region = world.locations[region_id]
        cities = [world.locations[cid] for cid in region.children_ids
                  if cid in world.locations and world.locations[cid].type == "city"]

        # Connect all cities within a region
        for i, a in enumerate(cities):
            for b in cities[i + 1:]:
                key = tuple(sorted([a.id, b.id]))
                if key in seen:
                    continue
                seen.add(key)

                dist = distance_between(a, b)
                speed = 30  # km/day on foot
                world.roads.append(Road(
                    from_id=a.id, to_id=b.id,
                    distance_km=round(dist, 1),
                    terrain=region.terrain or "road",
                    travel_days_foot=round(max(0.5, dist / speed), 1),
                    danger_rating=min(70, int(dist / 5) + region.danger_rating // 2),
                ))

    # Cross-region roads: connect closest cities between adjacent regions
    for i, rid_a in enumerate(region_ids):
        for rid_b in region_ids[i + 1:]:
            reg_a = world.locations[rid_a]
            reg_b = world.locations[rid_b]

            cities_a = [world.locations[c] for c in reg_a.children_ids
                        if c in world.locations and world.locations[c].type == "city"]
            cities_b = [world.locations[c] for c in reg_b.children_ids
                        if c in world.locations and world.locations[c].type == "city"]

            if not cities_a or not cities_b:
                continue

            # Find closest pair
            best_dist = float("inf")
            best_pair = None
            for ca in cities_a:
                for cb in cities_b:
                    d = distance_between(ca, cb)
                    if d < best_dist:
                        best_dist = d
                        best_pair = (ca, cb)

            if best_pair:
                a, b = best_pair
                key = tuple(sorted([a.id, b.id]))
                if key not in seen:
                    seen.add(key)
                    world.roads.append(Road(
                        from_id=a.id, to_id=b.id,
                        distance_km=round(best_dist, 1),
                        terrain="road",
                        travel_days_foot=round(max(1, best_dist / 30), 1),
                        danger_rating=min(80, int(best_dist / 4)),
                    ))


def _gen_name() -> str:
    """Generate a random fantasy place name."""
    return random.choice(NAME_PREFIXES) + random.choice(NAME_SUFFIXES)
