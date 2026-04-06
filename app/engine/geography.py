"""
Geography engine — assigns real coordinates and generates roads.
Runs after world generation to give every location a real position
and connect them with roads that have actual distances.

Coordinate system: 1 unit = 1 km. World is ~5000km across.
- Continent scale: thousands of km apart
- Region scale: hundreds of km
- City scale: tens of km
- District/building scale: < 1 km
"""
import math
import random

from app.data import World, Location, Road


def build_geography(world: World):
    """
    Post-process a generated world: assign coordinates and build roads.
    Call this after the world builder creates the spatial tree.
    """
    assign_coordinates(world)
    generate_roads(world)
    assign_populations(world)


# ============================================================
# COORDINATE ASSIGNMENT
# ============================================================

# Spread radius per parent type — how far children are from parent (km)
# Continent contains regions hundreds of km apart.
# A city's districts are a few km apart.
# A building's rooms are meters apart.
TYPE_SPREAD = {
    "continent": 800,
    "region": 200,
    "city": 3,
    "district": 0.5,
    "building": 0.02,
    "floor": 0.005,
    "room": 0.002,
}


def assign_coordinates(world: World):
    """Assign real (x, y) coordinates to every location in the spatial tree.
    Uses parent_id to traverse — each location processed exactly once."""
    # Find root locations (no parent)
    roots = [loc for loc in world.locations.values() if not loc.parent_id]
    if not roots:
        return

    # Place roots across the world
    world_center = 2500  # center of 5000km world
    root_radius = 1200 if len(roots) > 1 else 0

    for i, root in enumerate(roots):
        if len(roots) == 1:
            root.coordinates = (world_center, world_center)
        else:
            angle = (i / len(roots)) * 2 * math.pi + random.uniform(-0.2, 0.2)
            root.coordinates = (
                int(world_center + root_radius * math.cos(angle)),
                int(world_center + root_radius * math.sin(angle)),
            )
        # Recursively place children using parent_id (not children_ids)
        _place_children_of(root.id, world)


def _place_children_of(parent_id: str, world: World):
    """Find all locations whose parent_id matches and place them around the parent."""
    parent = world.locations.get(parent_id)
    if not parent:
        return

    # Find children by parent_id (avoids double-processing from children_ids)
    children = [loc for loc in world.locations.values() if loc.parent_id == parent_id]
    if not children:
        return

    spread = TYPE_SPREAD.get(parent.type, 50)
    px, py = parent.coordinates

    for i, child in enumerate(children):
        angle = (i / max(1, len(children))) * 2 * math.pi
        angle += random.uniform(-0.4, 0.4)
        r = spread * random.uniform(0.3, 1.0)

        child.coordinates = (
            px + r * math.cos(angle),
            py + r * math.sin(angle),
        )
        # Recurse
        _place_children_of(child.id, world)


def distance_between(loc_a: Location, loc_b: Location) -> float:
    """Euclidean distance in km between two locations."""
    ax, ay = loc_a.coordinates
    bx, by = loc_b.coordinates
    return math.sqrt((ax - bx) ** 2 + (ay - by) ** 2)


# ============================================================
# ROAD GENERATION
# ============================================================

def generate_roads(world: World):
    """Generate roads between sibling locations with real distances."""
    world.roads = []  # rebuild from scratch
    seen = set()

    for loc in world.locations.values():
        if not loc.children_ids:
            continue

        children = [world.locations[cid] for cid in loc.children_ids
                    if cid in world.locations]

        # Connect siblings — every child can reach every other child
        for i, a in enumerate(children):
            for b in children[i + 1:]:
                road_key = tuple(sorted([a.id, b.id]))
                if road_key in seen:
                    continue
                seen.add(road_key)

                dist = distance_between(a, b)

                # Terrain based on location types
                if a.type in ("building", "district") or b.type in ("building", "district"):
                    terrain = "street"
                elif a.type == "city" or b.type == "city":
                    terrain = "road"
                else:
                    terrain = "trail"

                # Travel speed (km/day on foot)
                speed = {"street": 40, "road": 30, "trail": 20}.get(terrain, 25)
                travel_days = max(0.1, dist / speed)

                # Danger increases with distance
                danger = min(80, int(dist / 8))

                world.roads.append(Road(
                    from_id=a.id, to_id=b.id,
                    distance_km=round(dist, 1),
                    terrain=terrain,
                    travel_days_foot=round(travel_days, 1),
                    danger_rating=danger,
                ))

    # Also connect each child to its parent (you can always go "up" the tree)
    for loc in world.locations.values():
        if loc.parent_id and loc.parent_id in world.locations:
            parent = world.locations[loc.parent_id]
            road_key = tuple(sorted([loc.id, parent.id]))
            if road_key not in seen:
                seen.add(road_key)
                dist = distance_between(loc, parent)
                world.roads.append(Road(
                    from_id=loc.id, to_id=parent.id,
                    distance_km=round(dist, 1),
                    terrain="road",
                    travel_days_foot=round(max(0.1, dist / 30), 1),
                    danger_rating=min(60, int(dist / 10)),
                ))


# ============================================================
# POPULATION ASSIGNMENT
# ============================================================

# Default populations by location type (if not already set)
DEFAULT_POPULATIONS = {
    "continent": 5_000_000,
    "region": 500_000,
    "city": 20_000,
    "district": 3_000,
    "building": 20,
    "floor": 5,
    "room": 2,
}


def assign_populations(world: World):
    """Assign default populations to locations that don't have one yet."""
    for loc in world.locations.values():
        if loc.population == 0:
            base = DEFAULT_POPULATIONS.get(loc.type, 100)
            # Add some variance (±50%)
            loc.population = int(base * random.uniform(0.5, 1.5))


# ============================================================
# MAP DATA FOR FRONTEND
# ============================================================

def get_map_data(world: World, player_location: str = "") -> dict:
    """
    Build map data for the frontend to render.
    Returns locations with coordinates, populations, connections, and types.
    """
    locations = []
    for lid, loc in world.locations.items():
        locations.append({
            "id": lid,
            "name": loc.name,
            "type": loc.type,
            "x": loc.coordinates[0],
            "y": loc.coordinates[1],
            "population": loc.population,
            "parent_id": loc.parent_id,
            "children": loc.children_ids,
            "is_current": (lid == player_location),
            "danger": loc.danger_rating,
        })

    roads = []
    for road in world.roads:
        roads.append({
            "from": road.from_id,
            "to": road.to_id,
            "distance_km": road.distance_km,
            "travel_days": road.travel_days_foot,
            "terrain": road.terrain,
            "danger": road.danger_rating,
        })

    return {
        "locations": locations,
        "roads": roads,
        "player_location": player_location,
    }
