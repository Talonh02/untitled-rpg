"""
Movement and travel engine — local movement within a city and overland travel.
Handles terrain speed multipliers, food consumption, travel events,
and the day-by-day progression of journeys.
"""
import random
import math

from app.data import Player, World, Location, Road
from app.config import GAME_CONSTANTS


# ============================================================
# TERRAIN SPEED MULTIPLIERS
# 1.0 = road speed (base). Everything else is slower.
# ============================================================

TERRAIN_SPEEDS = {
    "road":     1.0,
    "plains":   0.8,
    "forest":   0.6,
    "hills":    0.5,
    "mountains": 0.3,
    "swamp":    0.4,
    "desert":   0.5,    # plus double water consumption
    "snow":     0.4,
}


# ============================================================
# TRAVEL EVENT TYPES and their probabilities
# When something happens during travel, what kind of thing is it?
# ============================================================

TRAVEL_EVENT_TABLE = [
    ("bandit_encounter",   0.35),   # 35% of events
    ("traveler_encounter", 0.15),   # merchant, pilgrim, refugee
    ("weather_event",      0.15),   # storm, fog, heat wave
    ("wildlife",           0.10),   # wolves, bear, etc.
    ("discovery",          0.10),   # ruins, cave, abandoned camp
    ("companion_event",    0.10),   # companion wants to talk
    ("director_event",     0.05),   # Director plants something special
]


def move_local(player, target_location_id, world):
    """
    Move the player to a different location within the same city/area.
    This is instant movement (walking across town), not travel.

    Args:
        player: Player object
        target_location_id: where to go (must be in the same city)
        world: World object

    Returns:
        Dict with scene data for the narrator:
        - "success": bool
        - "location": the Location object arrived at
        - "npcs_present": list of NPC brief descriptions
        - "error": string if movement failed
    """
    target = world.locations.get(target_location_id)
    if not target:
        return {"success": False, "error": f"Unknown location: {target_location_id}"}

    # Update player position
    player.location = target_location_id

    # Gather who's there
    npcs_here = world.npcs_at_location(target_location_id)
    npc_descriptions = [npc.brief_description() for npc in npcs_here]

    return {
        "success": True,
        "location": target,
        "location_name": target.name,
        "location_type": target.type,
        "description": target.description,
        "mood": target.mood,
        "npcs_present": npc_descriptions,
        "npc_objects": npcs_here,
        "features": target.features,
    }


def calculate_travel(origin_id, destination_id, world):
    """
    Plan a journey between two locations.
    Finds the route, calculates days needed, and lists terrain types.

    Args:
        origin_id: starting location ID
        destination_id: target location ID
        world: World object (has roads and locations)

    Returns:
        Dict with route info:
        - "route": list of Road objects making up the path
        - "total_days": float, estimated travel time
        - "terrain_types": list of terrain strings encountered
        - "total_danger": average danger rating along the route
        - "error": string if no route found
    """
    origin = world.locations.get(origin_id)
    destination = world.locations.get(destination_id)
    if not origin or not destination:
        return {"error": "Unknown location", "route": [], "total_days": 0, "terrain_types": []}

    # Find roads that connect origin to destination (simple direct lookup)
    # In a full game this would be pathfinding; for now, find direct roads
    route = []
    for road in world.roads:
        if (road.from_id == origin_id and road.to_id == destination_id) or \
           (road.to_id == origin_id and road.from_id == destination_id):
            route.append(road)
            break

    if not route:
        # No direct road — estimate based on coordinates
        ox, oy = origin.coordinates
        dx, dy = destination.coordinates
        distance_km = math.sqrt((ox - dx) ** 2 + (oy - dy) ** 2)
        if distance_km == 0:
            distance_km = 50  # default if coordinates aren't set

        base_speed = GAME_CONSTANTS.get("travel_speed_foot", 30)
        terrain = destination.terrain or "plains"
        speed_mult = TERRAIN_SPEEDS.get(terrain, 0.8)
        days = distance_km / (base_speed * speed_mult)

        return {
            "route": [],
            "total_days": round(max(0.5, days), 1),
            "terrain_types": [terrain],
            "total_danger": (origin.danger_rating + destination.danger_rating) / 2,
            "distance_km": distance_km,
            "error": None,
        }

    # Calculate travel time from the road data
    total_days = 0
    terrain_types = []
    total_danger = 0
    for road in route:
        terrain = road.terrain or "road"
        terrain_types.append(terrain)
        total_days += road.travel_days_foot
        total_danger += road.danger_rating

    avg_danger = total_danger / len(route) if route else 0

    return {
        "route": route,
        "total_days": round(total_days, 1),
        "terrain_types": terrain_types,
        "total_danger": avg_danger,
        "distance_km": sum(r.distance_km for r in route),
        "error": None,
    }


def roll_travel_event(route_segment, player, day_number=1):
    """
    Check if something happens during a day of travel.
    Higher danger rating = more likely something happens.

    Args:
        route_segment: a Road object or dict with "danger_rating" and "terrain"
        player: Player object
        day_number: which day of the journey (not used much yet)

    Returns:
        Dict with event info, or None for a quiet day.
        Event dict has "type" and "description" keys.
    """
    # Get danger rating from the segment
    if isinstance(route_segment, dict):
        danger = route_segment.get("danger_rating", 20)
        terrain = route_segment.get("terrain", "road")
    else:
        danger = route_segment.danger_rating
        terrain = route_segment.terrain

    base_chance = danger / 100.0

    # Modifiers from MECHANICS.md
    # Reputation effects would go here (feared = 0.5x, party > 3 = 0.7x)
    if terrain == "road":
        base_chance *= 0.6   # roads are safer

    # Player party size — companions make travel safer
    party_size = 1 + len(player.companions)
    if party_size > 3:
        base_chance *= 0.7

    # Roll to see if anything happens
    if random.random() >= base_chance:
        return None  # quiet day

    # Something happens — pick what type from the weighted table
    roll = random.random()
    cumulative = 0.0
    event_type = "traveler_encounter"  # fallback
    for etype, prob in TRAVEL_EVENT_TABLE:
        cumulative += prob
        if roll < cumulative:
            event_type = etype
            break

    # Build event descriptions based on type
    descriptions = {
        "bandit_encounter": [
            "Figures step out from behind the rocks ahead.",
            "A rough voice calls out from the treeline: 'Your purse or your life.'",
            "You spot a crude barricade across the road. Armed men wait behind it.",
        ],
        "traveler_encounter": [
            "A merchant caravan approaches from the opposite direction.",
            "A lone pilgrim walks the road, muttering prayers.",
            "A family of refugees trudges past, eyes downcast.",
        ],
        "weather_event": [
            "Dark clouds roll in fast. A storm is coming.",
            "A thick fog settles, reducing visibility to a few paces.",
            "The heat becomes oppressive. Your water won't last at this rate.",
        ],
        "wildlife": [
            "Wolves shadow you through the trees, keeping their distance. For now.",
            "A bear blocks the path ahead, sniffing the air.",
            "Something large moves through the underbrush nearby.",
        ],
        "discovery": [
            "You notice the overgrown entrance to some ruins off the road.",
            "An abandoned camp — the fire's still warm.",
            "A cave mouth yawns in the hillside. Scratches mark the entrance.",
        ],
        "companion_event": [
            "Your companion wants to talk about something.",
            "Your companion notices something you missed and calls you over.",
        ],
        "director_event": [
            "Something unusual happens.",  # The Director fills in the details
        ],
    }

    desc_options = descriptions.get(event_type, ["Something happens on the road."])
    description = random.choice(desc_options)

    return {
        "type": event_type,
        "description": description,
        "danger_rating": danger,
        "terrain": terrain,
        "day": day_number,
    }


def consume_food(player):
    """
    Consume 1 food unit per day. If no food, hunger increases.
    Hunger above 60 causes stat penalties (handled by Player.get_effective_stats).

    Args:
        player: Player object

    Returns:
        Dict with status info about hunger.
    """
    food_per_day = GAME_CONSTANTS.get("food_per_day", 1)

    # Check if player has food in inventory
    food_count = player.inventory.count("food")

    if food_count >= food_per_day:
        # Remove food from inventory
        for _ in range(food_per_day):
            player.inventory.remove("food")
        # Hunger decreases when fed
        player.hunger = max(0, player.hunger - 10)
        return {"fed": True, "hunger": player.hunger, "food_remaining": player.inventory.count("food")}
    else:
        # No food — hunger increases by 20 per day
        player.hunger = min(100, player.hunger + 20)

        # Check for starvation death at extreme hunger
        if player.hunger >= 80:
            # 5% base death chance per day at hunger 80+
            death_roll = random.random() < 0.05
            return {
                "fed": False, "hunger": player.hunger,
                "food_remaining": 0, "starving": True,
                "death_risk": death_roll,
            }

        status = "fine"
        if player.hunger > 60:
            status = "starving"
        elif player.hunger > 30:
            status = "hungry"

        return {"fed": False, "hunger": player.hunger, "food_remaining": 0, "status": status}
