"""
NPC lifecycle — creation, promotion/demotion, model tier selection, scheduling.
NPCs start as stat blocks and get "souls" (system prompts) written by the Character Author
only when the player actually meets them.
"""
import random
import uuid

from app.data import NPC, Stats, Relationship
from app.config import GAME_CONSTANTS, NPC_MODEL_THRESHOLDS
from app.engine.stats import generate_npc_stats


# ============================================================
# SCHEDULE TEMPLATES
# Where different occupations go throughout the day.
# Keys are time slots: dawn, morning, afternoon, evening, night.
# Values are location type strings that get resolved to actual
# location IDs based on what's available in the NPC's city.
# ============================================================

SCHEDULE_TEMPLATES = {
    "soldier":    {"dawn": "barracks", "morning": "guard_post", "afternoon": "training_ground",
                   "evening": "tavern", "night": "barracks"},
    "scholar":    {"dawn": "home", "morning": "library", "afternoon": "library",
                   "evening": "home", "night": "home"},
    "merchant":   {"dawn": "home", "morning": "market", "afternoon": "market",
                   "evening": "tavern", "night": "home"},
    "farmer":     {"dawn": "fields", "morning": "fields", "afternoon": "fields",
                   "evening": "tavern", "night": "home"},
    "thief":      {"dawn": "home", "morning": "market", "afternoon": "alley",
                   "evening": "tavern", "night": "alley"},
    "priest":     {"dawn": "temple", "morning": "temple", "afternoon": "market",
                   "evening": "temple", "night": "home"},
    "noble":      {"dawn": "home", "morning": "court", "afternoon": "garden",
                   "evening": "great_hall", "night": "home"},
    "artist":     {"dawn": "home", "morning": "workshop", "afternoon": "market",
                   "evening": "tavern", "night": "home"},
    "blacksmith": {"dawn": "forge", "morning": "forge", "afternoon": "forge",
                   "evening": "tavern", "night": "home"},
    "healer":     {"dawn": "home", "morning": "clinic", "afternoon": "clinic",
                   "evening": "home", "night": "home"},
    "spy":        {"dawn": "home", "morning": "market", "afternoon": "tavern",
                   "evening": "docks", "night": "alley"},
    "beggar":     {"dawn": "street", "morning": "market", "afternoon": "temple",
                   "evening": "tavern", "night": "street"},
    # Default for unknown occupations
    "default":    {"dawn": "home", "morning": "market", "afternoon": "market",
                   "evening": "tavern", "night": "home"},
}


# ============================================================
# COMMON NAMES — used when generating random NPCs
# ============================================================

FIRST_NAMES = [
    "Arin", "Brell", "Cael", "Dara", "Edrin", "Fael", "Gwen", "Hale",
    "Isen", "Jora", "Kael", "Lira", "Maren", "Nessa", "Orin", "Pell",
    "Quinn", "Reva", "Soren", "Talia", "Unn", "Vael", "Wren", "Yara",
    "Zeph", "Bryn", "Corwin", "Dalla", "Eamon", "Fiona", "Gareth", "Hild",
    "Idris", "Kira", "Leif", "Mira", "Niall", "Petra", "Ronan", "Sigrid",
    "Theron", "Vara", "Aldric", "Benna", "Cedric", "Elara", "Finn", "Greta",
]

LAST_NAMES = [
    "Stone", "Ash", "Thorn", "Vale", "Frost", "Hale", "Brook", "Wren",
    "Marsh", "Fell", "Pike", "Reed", "Hart", "Crane", "Forge", "Croft",
    "Strand", "Birch", "Glen", "Rune", "Dell", "Cairn", "Helm", "Brine",
]


def _generate_name():
    """Pick a random first + last name combo."""
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def _generate_age(occupation):
    """
    Roll a plausible age for an occupation.
    Soldiers skew younger, scholars skew older, etc.
    """
    age_ranges = {
        "soldier": (18, 45), "scholar": (25, 75), "merchant": (20, 65),
        "farmer": (16, 70), "thief": (14, 40), "priest": (30, 80),
        "noble": (16, 70), "artist": (18, 65), "blacksmith": (20, 60),
        "healer": (25, 70), "spy": (20, 45), "beggar": (12, 80),
    }
    low, high = age_ranges.get(occupation, (18, 65))
    return random.randint(low, high)


def select_npc_model(depth_score, fate=0.0):
    """
    Pick which AI model tier to use for this NPC's dialogue.

    Fate gives a small boost to model selection (not just stats).
    Boundaries are fuzzy — a random ±8 roll means a boring NPC might
    occasionally surprise you, and a smart NPC might be duller than expected.
    People aren't predictable; the randomness IS the realism.

    Args:
        depth_score: float 0-100, from Stats.depth_score()
        fate: float 0.0-1.0, narrative importance

    Returns:
        A model tier string like "npc_flash_lite", "npc_flash", "npc_sonnet", "npc_opus"
    """
    # Fate gives a small boost to model selection
    effective_score = depth_score + (fate * 10)

    # Fuzzy ±8 randomness so boundaries aren't crisp
    roll = effective_score + random.uniform(-8, 8)

    if roll < 30:
        return "npc_flash_lite"   # ~55% of NPCs — simple, one-sentence answers
    elif roll < 52:
        return "npc_flash"        # ~25% — short paragraph, has a personality
    elif roll < 72:
        return "npc_sonnet"       # ~13% — full responses, opinions, surprises
    else:
        return "npc_opus"         # ~7% — memorable, complex, feels real


def create_npc(world, location_id, fate=0.0, occupation="", social_class="working",
               name="", age=None):
    """
    Create a brand new NPC with a full stat block.
    The NPC starts WITHOUT a system_prompt — that gets written by the
    Character Author only when the player first meets them (promotion).

    Args:
        world: the World object (used for ID uniqueness check)
        location_id: where this NPC lives
        fate: 0.0-1.0 narrative importance
        occupation: their job (affects stat modifiers)
        social_class: affects wealth/education floors
        name: optional — auto-generated if blank
        age: optional — auto-generated based on occupation if None

    Returns:
        A fully initialized NPC object (added to world.npcs automatically).
    """
    # Generate unique ID
    npc_id = f"npc_{uuid.uuid4().hex[:8]}"

    # Fill in defaults
    if not name:
        name = _generate_name()
    if age is None:
        age = _generate_age(occupation)

    # Roll stats
    stats = generate_npc_stats(fate=fate, occupation=occupation,
                               social_class=social_class, age=age)

    # Pick model tier based on depth score
    model_tier = select_npc_model(stats.depth_score(), fate)

    # Pick a temperament based on stats (rough heuristic)
    if stats.courage > 70 and stats.empathy < 30:
        temperament = "cold"
    elif stats.empathy > 65 and stats.humor > 50:
        temperament = "cheerful"
    elif stats.depth > 60 and stats.humor < 30:
        temperament = "melancholy"
    elif stats.courage < 30 or stats.willpower < 30:
        temperament = "volatile"
    else:
        temperament = "calm"

    # Determine wealth in coins (not the stat — the stat is already set)
    # Wealth stat is 0-100, but actual coin holdings vary
    npc = NPC(
        id=npc_id,
        name=name,
        age=age,
        fate=fate,
        stats=stats,
        occupation=occupation,
        social_class=social_class,
        wealth=stats.to_dict().get("education", 42),  # placeholder — wealth is in stats
        faction="none",
        faction_loyalty=random.randint(20, 80),
        temperament=temperament,
        location=location_id,
        schedule_template=occupation if occupation in SCHEDULE_TEMPLATES else "default",
        model_tier=model_tier,
    )

    # Add to the world
    world.npcs[npc_id] = npc
    return npc


def promote_npc(npc):
    """
    Mark an NPC as met by the player. This triggers the Character Author
    to write them a system prompt (soul) if they don't have one yet.

    Returns True if the NPC needs a system prompt written (i.e., first meeting).
    """
    npc.met_player = True

    # Initialize a relationship tracker if they don't have one
    if npc.relationship is None:
        npc.relationship = Relationship()
    npc.relationship.interactions += 1

    # They need a prompt written if they don't have one yet
    needs_authoring = (npc.system_prompt == "")
    return needs_authoring


def demote_npc(npc):
    """
    Strip the system prompt from an NPC to save memory.
    Used for NPCs the player hasn't interacted with in a long time.
    Keeps flags and relationship data — just removes the expensive prompt text.
    """
    npc.system_prompt = ""
    # Keep: met_player, relationship, backstory, secret, knowledge_tags
    # These are small and might matter if the player comes back


def populate_location(world, location_id, count, occupation_weights=None):
    """
    Fill a location with NPCs. Used during world generation to
    put people in cities, taverns, markets, etc.

    Args:
        world: the World object
        location_id: where to place them
        count: how many NPCs to create
        occupation_weights: optional dict like {"merchant": 0.4, "soldier": 0.3, "farmer": 0.3}
                           If None, uses a generic mix.

    Returns:
        List of the created NPC objects.
    """
    if occupation_weights is None:
        occupation_weights = {
            "farmer": 0.25, "merchant": 0.15, "soldier": 0.12, "thief": 0.05,
            "scholar": 0.05, "priest": 0.05, "blacksmith": 0.08, "healer": 0.05,
            "artist": 0.05, "beggar": 0.05, "noble": 0.03, "spy": 0.02,
        }

    # Build a weighted list for random selection
    occupations = list(occupation_weights.keys())
    weights = list(occupation_weights.values())

    # Guess social class from occupation (rough mapping)
    class_by_occupation = {
        "noble": "noble", "beggar": "destitute", "merchant": "merchant",
        "scholar": "merchant", "priest": "merchant", "spy": "merchant",
        "soldier": "working", "farmer": "working", "thief": "working",
        "blacksmith": "working", "healer": "working", "artist": "working",
    }

    npcs = []
    for _ in range(count):
        # Pick occupation from weighted distribution
        occ = random.choices(occupations, weights=weights, k=1)[0]
        sc = class_by_occupation.get(occ, "working")

        # Most NPCs are nobodies (fate 0.0). Occasionally one is a bit interesting.
        fate = 0.0
        fate_roll = random.random()
        if fate_roll > 0.95:
            fate = random.uniform(0.1, 0.3)  # slightly interesting (5% chance)
        elif fate_roll > 0.99:
            fate = random.uniform(0.3, 0.5)  # potential companion material (1% chance)

        npc = create_npc(world, location_id, fate=fate, occupation=occ, social_class=sc)
        npcs.append(npc)

    return npcs


def get_npc_schedule_location(npc, time_slot, world_events=None):
    """
    Figure out where an NPC should be right now based on their schedule,
    health, mood, and any world events that might disrupt things.

    Args:
        npc: the NPC object
        time_slot: "dawn", "morning", "afternoon", "evening", "night"
        world_events: optional list of active world events

    Returns:
        A location type string (e.g., "tavern", "market", "home").
        The caller resolves this to an actual location_id in the NPC's city.
    """
    # Get their base schedule
    template_key = npc.schedule_template if npc.schedule_template in SCHEDULE_TEMPLATES else "default"
    base_location = SCHEDULE_TEMPLATES[template_key].get(time_slot, "home")

    # Check for disruptions from world events
    if world_events:
        for event in world_events:
            event_type = event.get("type", "") if isinstance(event, dict) else getattr(event, "type", "")
            event_target = event.get("target", "") if isinstance(event, dict) else getattr(event, "target", "")

            if event_type == "building_destroyed" and event_target == base_location:
                return "home"  # their usual spot is gone
            if event_type == "siege" and npc.stats.courage < 40:
                return "home"  # scared NPCs stay home during sieges
            if event_type == "festival":
                return "town_square"  # everyone goes to the festival
            if event_type == "curfew" and time_slot in ["evening", "night"]:
                return "home"  # curfew sends people home

    # Personal disruptions
    if npc.stats.health < 30:
        return "home"  # too sick or injured to go out
    if npc.temperament == "melancholy" and random.random() < 0.3:
        return "home"  # sometimes just stays home

    return base_location
