"""
Player creation — custom (from real-world description), quick (pick an archetype),
or from a saved dict. The custom path uses an AI model to translate real traits
into fantasy-world equivalents.
"""
import random

from app.data import Player, Stats, WEAPONS, PRICES
from app.config import GAME_CONSTANTS


# ============================================================
# QUICK CREATION — pick an archetype, get going fast
# ============================================================

# Each archetype has stat biases (added to a base of 55) and starter gear
ARCHETYPES = {
    "wanderer": {
        "description": "A traveler with no home and many stories.",
        "stat_boosts": {
            "agility": 10, "perception": 10, "wisdom": 5,
            "courage": 8, "creativity": 5,
        },
        "stat_penalties": {"education": -5, "ambition": -5},
        "weapon": "short_sword",
        "armor": "leather",
        "coins": 40,
        "inventory": ["bedroll", "waterskin", "dried meat (3 days)", "flint"],
        "backstory_template": "{name} has been walking for as long as anyone remembers. "
                              "No roots, no debts, no home — just the road and whatever it brings.",
    },
    "scholar": {
        "description": "A student of the world, more comfortable with books than blades.",
        "stat_boosts": {
            "intelligence": 12, "education": 15, "depth": 10,
            "wisdom": 5, "creativity": 5,
        },
        "stat_penalties": {"strength": -8, "toughness": -5, "courage": -5},
        "weapon": "dagger",
        "armor": "none",
        "coins": 60,
        "inventory": ["journal", "ink and quill", "bread and cheese (2 days)", "a worn book"],
        "backstory_template": "{name} left the academy with more questions than answers. "
                              "The world outside the library is louder and messier than any text prepared them for.",
    },
    "soldier": {
        "description": "Trained for war. Good with a blade, less so with words.",
        "stat_boosts": {
            "strength": 12, "toughness": 10, "courage": 10,
            "agility": 5, "willpower": 5,
        },
        "stat_penalties": {"empathy": -5, "creativity": -5, "depth": -5},
        "weapon": "long_sword",
        "armor": "chain",
        "coins": 30,
        "inventory": ["shield", "rations (4 days)", "whetstone", "soldier's cloak"],
        "backstory_template": "{name} served three years before walking away. "
                              "The fighting was never the hard part. It was everything that came after.",
    },
    "merchant": {
        "description": "A trader who knows the price of everything and the value of most things.",
        "stat_boosts": {
            "charisma": 10, "perception": 8, "intelligence": 5,
            "ambition": 10, "humor": 5,
        },
        "stat_penalties": {"strength": -5, "courage": -5, "toughness": -3},
        "weapon": "dagger",
        "armor": "leather",
        "coins": 120,
        "inventory": ["trade ledger", "scales", "fine clothes", "bread and wine (2 days)"],
        "backstory_template": "{name} started with nothing and built a name worth something. "
                              "Every person is a deal waiting to happen — the trick is finding what they want.",
    },
    "thief": {
        "description": "Quick hands, quick feet, slow to trust.",
        "stat_boosts": {
            "agility": 15, "perception": 10, "creativity": 8,
            "courage": 5,
        },
        "stat_penalties": {"honesty": -10, "loyalty": -5, "education": -5},
        "weapon": "dagger",
        "armor": "leather",
        "coins": 70,
        "inventory": ["lockpicks", "dark cloak", "rope (30ft)", "dried fruit (2 days)"],
        "backstory_template": "{name} learned young that the world doesn't hand you anything. "
                              "You take what you need and keep moving before anyone notices.",
    },
}


def create_player_quick(name: str, archetype: str, world=None) -> Player:
    """
    Create a player from one of the preset archetypes.
    Fast, no model call needed. Good for jumping right in.
    """
    archetype = archetype.lower()
    if archetype not in ARCHETYPES:
        archetype = "wanderer"  # default fallback

    template = ARCHETYPES[archetype]
    base_mean = GAME_CONSTANTS.get("player_stat_mean", 55)

    # Generate stats: start at player base, apply archetype boosts/penalties
    stat_values = {}
    stat_names = [
        "strength", "toughness", "agility", "intelligence", "depth",
        "wisdom", "perception", "willpower", "education", "creativity",
        "charisma", "empathy", "courage", "honesty", "humor",
        "stubbornness", "ambition", "loyalty",
    ]
    for stat in stat_names:
        # Base roll around player mean with some variance
        base = int(random.gauss(base_mean, 8))
        # Apply archetype boosts
        boost = template.get("stat_boosts", {}).get(stat, 0)
        penalty = template.get("stat_penalties", {}).get(stat, 0)
        value = max(1, min(100, base + boost + penalty))
        stat_values[stat] = value

    # Physical stats
    stat_values["health"] = 100
    stat_values["height_cm"] = random.randint(155, 195)
    stat_values["weight_kg"] = random.randint(55, 100)
    stat_values["attractiveness"] = int(random.gauss(50, 15))
    stat_values["attractiveness"] = max(1, min(100, stat_values["attractiveness"]))

    stats = Stats(**stat_values)
    backstory = template["backstory_template"].format(name=name)

    # Figure out starting location from the world (first city we can find)
    start_location = ""
    if world:
        start_location = _find_starting_location(world)

    return Player(
        name=name,
        backstory=backstory,
        stats=stats,
        location=start_location,
        weapon=template["weapon"],
        armor=template["armor"],
        coins=template["coins"],
        inventory=list(template["inventory"]),
    )


# ============================================================
# CUSTOM CREATION — describe yourself, AI maps it to the world
# ============================================================

def create_player_custom(name: str, description: str, world) -> Player:
    """
    Create a player from a real-world description.
    Uses an AI model to translate traits into the game world.

    Example input: "finance degree, philosopher, Canadian, 5'10, former wrestler"
    The model maps this onto the world's lore, factions, and geography.

    Falls back to a wanderer archetype if the model call fails.
    """
    # Build the prompt for the model
    world_context = _build_world_context_for_creation(world)

    prompt = f"""You are creating a player character for a fantasy RPG.

The player described themselves as: "{description}"

The game world:
{world_context}

Map the player's real-world traits onto this fantasy world. Be creative but logical:
- Education/career → guild membership, training, social position
- Physical traits → actual height/weight/build in the game
- Interests/hobbies → skills, knowledge, connections
- Nationality/background → region of origin within this world

Return ONLY valid JSON (no markdown, no explanation):
{{
    "backstory": "2-3 sentence backstory connecting their traits to this world",
    "starting_region": "name of a city/region from the world",
    "occupation_equivalent": "what they'd be in this world",
    "stat_boosts": {{"stat_name": boost_amount}},
    "stat_penalties": {{"stat_name": penalty_amount}},
    "suggested_weapon": "weapon_key from: unarmed, dagger, short_sword, long_sword, spear, mace, bow",
    "suggested_armor": "none, leather, or chain",
    "starting_coins": 30-80,
    "extra_inventory": ["1-3 thematic items"],
    "height_cm": estimated_height,
    "weight_kg": estimated_weight
}}"""

    # Try the model call
    char_data = None
    try:
        from app.ai.models import call_model
        import json
        result = call_model("character_author", prompt)
        if result:
            # Clean up the response — strip markdown fences if present
            cleaned = result.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]  # remove first line
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
            char_data = json.loads(cleaned)
    except Exception:
        pass  # fall back to quick creation

    # If model failed, fall back to wanderer with the name
    if not char_data:
        return create_player_quick(name, "wanderer", world)

    # Build the player from the model's response
    base_mean = GAME_CONSTANTS.get("player_stat_mean", 55)
    stat_values = {}
    stat_names = [
        "strength", "toughness", "agility", "intelligence", "depth",
        "wisdom", "perception", "willpower", "education", "creativity",
        "charisma", "empathy", "courage", "honesty", "humor",
        "stubbornness", "ambition", "loyalty",
    ]
    boosts = char_data.get("stat_boosts", {})
    penalties = char_data.get("stat_penalties", {})

    for stat in stat_names:
        base = int(random.gauss(base_mean, 8))
        boost = boosts.get(stat, 0)
        pen = penalties.get(stat, 0)
        stat_values[stat] = max(1, min(100, base + int(boost) - abs(int(pen))))

    stat_values["health"] = 100
    stat_values["height_cm"] = char_data.get("height_cm", random.randint(160, 185))
    stat_values["weight_kg"] = char_data.get("weight_kg", random.randint(60, 90))
    stat_values["attractiveness"] = max(1, min(100, int(random.gauss(50, 15))))

    stats = Stats(**stat_values)

    # Map weapon/armor to valid keys
    weapon = char_data.get("suggested_weapon", "short_sword")
    if weapon not in WEAPONS:
        weapon = "short_sword"
    armor_key = char_data.get("suggested_armor", "none")
    if armor_key not in ("none", "leather", "chain", "plate"):
        armor_key = "none"

    # Starting location: try to match the model's suggestion to a real location
    start_location = ""
    suggested_region = char_data.get("starting_region", "")
    if world and suggested_region:
        start_location = _match_location(world, suggested_region)
    if not start_location and world:
        start_location = _find_starting_location(world)

    coins = char_data.get("starting_coins", 50)
    coins = max(10, min(200, int(coins)))

    inventory = char_data.get("extra_inventory", [])
    if not isinstance(inventory, list):
        inventory = []

    return Player(
        name=name,
        backstory=char_data.get("backstory", f"{name} arrived with little more than their wits."),
        stats=stats,
        location=start_location,
        weapon=weapon,
        armor=armor_key,
        coins=coins,
        inventory=inventory,
    )


# ============================================================
# LOAD FROM DICT — for save game restoration
# ============================================================

def create_player_from_dict(d: dict) -> Player:
    """
    Rebuild a Player from a saved dictionary.
    This is called by load_game() in state.py.
    """
    from app.game.state import _deserialize_player
    return _deserialize_player(d)


# ============================================================
# HELPERS
# ============================================================

def _find_starting_location(world) -> str:
    """
    Pick a reasonable starting location from the world.
    Prefers cities, then districts, then anything.
    """
    if not world or not world.locations:
        return ""

    # Look for cities first (good starting points)
    cities = [loc for loc in world.locations.values() if loc.type == "city"]
    if cities:
        # Pick one with low danger
        safe_cities = [c for c in cities if c.danger_rating < 40]
        if safe_cities:
            chosen = random.choice(safe_cities)
        else:
            chosen = random.choice(cities)
        # If the city has children (districts/buildings), pick one
        if chosen.children_ids:
            child_id = random.choice(chosen.children_ids)
            if child_id in world.locations:
                return child_id
        return chosen.id

    # No cities? Pick any location
    all_locs = list(world.locations.values())
    if all_locs:
        return random.choice(all_locs).id
    return ""


def _match_location(world, name_hint: str) -> str:
    """
    Try to match a location name from the model's suggestion.
    Does fuzzy matching — if "Tessam" is suggested and "tessam_market" exists, match it.
    """
    hint_lower = name_hint.lower()
    for lid, loc in world.locations.items():
        if hint_lower in loc.name.lower() or hint_lower in lid.lower():
            return lid
    return ""


def _build_world_context_for_creation(world) -> str:
    """
    Build a brief world summary for the character creation prompt.
    Keeps it short so the model focuses on the player, not the lore.
    """
    if not world:
        return "A medieval fantasy world with multiple regions and factions."

    parts = []
    if world.name:
        parts.append(f"World: {world.name}")
    if world.era:
        parts.append(f"Era: {world.era}")
    if world.tone:
        parts.append(f"Tone: {world.tone}")

    # List some cities
    cities = [loc for loc in world.locations.values() if loc.type == "city"]
    if cities:
        city_names = [c.name for c in cities[:8]]
        parts.append(f"Major cities: {', '.join(city_names)}")

    # List factions
    if world.factions:
        faction_names = list(world.factions.keys())[:6]
        parts.append(f"Factions: {', '.join(faction_names)}")

    # Intellectual traditions
    if world.intellectual_traditions:
        traditions = []
        for t in world.intellectual_traditions[:4]:
            if isinstance(t, dict):
                traditions.append(t.get("name", "unknown"))
            else:
                traditions.append(str(t))
        parts.append(f"Intellectual traditions: {', '.join(traditions)}")

    return "\n".join(parts) if parts else "A medieval fantasy world."


def get_archetype_list() -> list:
    """
    Return a list of available archetypes with descriptions.
    Used by the UI to show player creation options.
    """
    result = []
    for key, data in ARCHETYPES.items():
        result.append({
            "key": key,
            "name": key.capitalize(),
            "description": data["description"],
        })
    return result
