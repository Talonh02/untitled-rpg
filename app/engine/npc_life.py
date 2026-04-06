"""
NPC Life Simulation — NPCs live their lives between player interactions.
Runs daily at dawn. Gives NPCs memory of their own actions, movements,
reactions to world events, and interactions with each other.

When you meet someone 3 weeks later, they know where they've been,
what they've heard, and who they've talked to.
"""
import random
import math

from app.data import NPC, Stats, World, ENTITY_TIER_MULTIPLIERS


# ============================================================
# CAUSAL CHAIN: Role → Fate → Stats → Everything Else
# ============================================================

# Step 1: Role sets the fate attractor (gaussian mean for fate roll)
ROLE_FATE_ATTRACTORS = {
    # Commoners — fate near 0. Most people.
    "laborer": 0.03, "farmer": 0.04, "fisherman": 0.03, "servant": 0.02,
    "beggar": 0.02, "drunk": 0.01, "commoner": 0.03, "porter": 0.03,
    "craftsman": 0.05, "clerk": 0.05,
    # Skilled trades
    "carpenter": 0.06, "blacksmith": 0.08, "weaver": 0.05,
    "baker": 0.05, "tailor": 0.06, "herbalist": 0.08,
    # Service/commerce
    "barkeeper": 0.08, "innkeeper": 0.08, "merchant": 0.12,
    "trader": 0.10, "shopkeeper": 0.07,
    # Military
    "guard": 0.10, "soldier": 0.12, "knight": 0.30, "captain": 0.25,
    "general": 0.55, "commander": 0.40, "mercenary": 0.15,
    # Religious/scholarly
    "priest": 0.15, "monk": 0.10, "scholar": 0.18, "healer": 0.12,
    "high priestess": 0.45,
    # Criminal
    "thief": 0.10, "assassin": 0.25, "smuggler": 0.12, "bandit": 0.08,
    "spy": 0.30, "master assassin": 0.40,
    # Nobility
    "noble": 0.45, "lord": 0.55, "lady": 0.50,
    "prince": 0.60, "princess": 0.60, "king": 0.75, "queen": 0.75,
    # Wanderers
    "traveler": 0.10, "pilgrim": 0.08, "bard": 0.15, "adventurer": 0.20,
    # Exceptional
    "champion": 0.45, "archmage": 0.50, "seer": 0.40,
    "guild master": 0.40, "legendary warrior": 0.55,
    # Creatures
    "dragon": 0.60, "ancient dragon": 0.80, "troll": 0.15, "giant": 0.20,
}

# Step 3b: Role sets stat FLOORS (minimum values for certain stats)
ROLE_STAT_FLOORS = {
    "king":       {"education": 50, "charisma": 45, "ambition": 50},
    "queen":      {"education": 50, "charisma": 50, "willpower": 45},
    "prince":     {"education": 40, "charisma": 35},
    "princess":   {"education": 40, "charisma": 40},
    "general":    {"courage": 60, "willpower": 55, "intelligence": 50},
    "commander":  {"courage": 50, "willpower": 45, "intelligence": 45},
    "knight":     {"courage": 50, "strength": 45, "loyalty": 50},
    "captain":    {"courage": 45, "strength": 40},
    "guard":      {"courage": 35, "strength": 38},
    "soldier":    {"courage": 35, "strength": 40},
    "scholar":    {"education": 55, "intelligence": 50},
    "priest":     {"wisdom": 45, "empathy": 40},
    "high priestess": {"wisdom": 55, "empathy": 50, "willpower": 50},
    "assassin":   {"agility": 55, "perception": 50, "courage": 40},
    "master assassin": {"agility": 65, "perception": 60, "courage": 50},
    "spy":        {"perception": 55, "intelligence": 50, "charisma": 45},
    "champion":   {"strength": 60, "courage": 60, "agility": 50},
    "archmage":   {"intelligence": 70, "willpower": 60, "education": 65},
    "seer":       {"wisdom": 60, "perception": 60, "intelligence": 55},
    "dragon":     {"strength": 80, "toughness": 85, "willpower": 70, "perception": 65},
    "ancient dragon": {"strength": 90, "toughness": 95, "willpower": 85, "perception": 80, "intelligence": 75},
    "merchant":   {"intelligence": 40, "charisma": 40},
    "guild master": {"intelligence": 55, "charisma": 50, "ambition": 55},
    "thief":      {"agility": 45, "perception": 42},
    "mercenary":  {"strength": 42, "courage": 40},
    "noble":      {"education": 40, "charisma": 38},
}

# Step 4b: Role → social class
ROLE_SOCIAL_CLASS = {
    "beggar": "destitute", "drunk": "destitute",
    "laborer": "working", "farmer": "working", "servant": "working",
    "fisherman": "working", "porter": "working", "commoner": "working",
    "guard": "working", "soldier": "working",
    "carpenter": "working", "blacksmith": "working", "weaver": "working",
    "baker": "working", "tailor": "working", "barkeeper": "working",
    "merchant": "merchant", "trader": "merchant", "shopkeeper": "merchant",
    "innkeeper": "merchant", "guild master": "merchant",
    "knight": "noble", "captain": "noble", "noble": "noble",
    "lord": "noble", "lady": "noble", "general": "noble",
    "prince": "royal", "princess": "royal", "king": "royal", "queen": "royal",
}

# Step 4c: Role → default weapon/armor
ROLE_EQUIPMENT = {
    "guard":    ("short_sword", "chain"),
    "soldier":  ("long_sword", "chain"),
    "knight":   ("long_sword", "plate"),
    "captain":  ("long_sword", "chain"),
    "general":  ("long_sword", "plate"),
    "champion": ("two_hand_sword", "plate"),
    "mercenary": ("short_sword", "leather"),
    "thief":    ("dagger", "leather"),
    "assassin": ("dagger", "leather"),
    "bandit":   ("short_sword", "leather"),
    "merchant": ("dagger", "none"),
    "noble":    ("short_sword", "none"),
}


def generate_npc(occupation, name=None, age=None, location="") -> NPC:
    """
    Generate an NPC following the full causal chain:

    1. Role → fate attractor
    2. Fate rolled from gaussian(attractor, 0.12)
    3. Fate → stat mean = 42 + fate*20
    4. Stats rolled from gaussian(mean, 16), role floors applied
    5. Role → power tier, social class, equipment
    6. Everything else derived from above

    A king clusters around fate 0.75 with stats mean ~57.
    A farmer clusters around fate 0.04 with stats mean ~43.
    But outliers happen — a farmer CAN roll fate 0.40 and become rare.
    """
    occ_lower = occupation.lower()

    # 1. Fate attractor from role
    attractor = ROLE_FATE_ATTRACTORS.get(occ_lower, 0.05)

    # 2. Roll fate (gaussian around attractor, clamped 0-1)
    fate = max(0.0, min(1.0, random.gauss(attractor, 0.12)))

    # 3. Fate shifts stat generation mean
    stat_mean = 42 + fate * 20  # fate 0.0 → 42, fate 1.0 → 62

    # 4. Roll all stats
    stat_names = [
        "strength", "toughness", "agility", "intelligence", "depth",
        "wisdom", "perception", "willpower", "education", "creativity",
        "charisma", "empathy", "courage", "honesty", "humor",
        "stubbornness", "ambition", "loyalty",
    ]
    stat_values = {}
    for s in stat_names:
        stat_values[s] = max(1, min(100, int(random.gauss(stat_mean, 16))))

    # Apply role stat floors (king gets education 50+ etc.)
    floors = ROLE_STAT_FLOORS.get(occ_lower, {})
    for stat, floor in floors.items():
        if stat in stat_values and stat_values[stat] < floor:
            stat_values[stat] = floor

    # Physical stats
    stat_values["health"] = 100
    stat_values["height_cm"] = random.randint(155, 195)
    stat_values["weight_kg"] = random.randint(55, 100)
    stat_values["attractiveness"] = max(1, min(100, int(random.gauss(50, 15))))

    stats = Stats(**stat_values)

    # 5. Power tier from species/role
    power_tier = get_default_power_tier(occ_lower)

    # Social class
    social_class = ROLE_SOCIAL_CLASS.get(occ_lower, "working")

    # Equipment
    weapon, armor = ROLE_EQUIPMENT.get(occ_lower, ("unarmed", "none"))

    # Wealth correlates with social class
    wealth_ranges = {
        "destitute": (0, 10), "working": (5, 30),
        "merchant": (30, 70), "noble": (50, 90), "royal": (80, 100),
    }
    w_min, w_max = wealth_ranges.get(social_class, (10, 40))
    wealth = random.randint(w_min, w_max)

    # Name and age defaults
    if not name:
        from app.game.loop import GameLoop
        name = random.choice(GameLoop.AMBIENT_NAMES)
    if not age:
        age = random.randint(18, 65)

    # Temperament from stats
    if stats.empathy > 60 and stats.humor > 50:
        temperament = "cheerful"
    elif stats.empathy < 30 or stats.willpower > 70:
        temperament = "cold"
    elif stats.depth > 60 and stats.wisdom > 55:
        temperament = "melancholy"
    else:
        temperament = "calm"

    npc_id = f"npc_{name.lower()}_{random.randint(100, 999)}"

    return NPC(
        id=npc_id, name=name, age=age, fate=fate,
        stats=stats, occupation=occupation,
        social_class=social_class, wealth=wealth,
        temperament=temperament, power_tier=power_tier,
        weapon=weapon, armor=armor, location=location,
    )


# ============================================================
# ROLE → POWER TIER DEFAULTS
# Power tier is about WHAT you are, not WHO you are.
# A mythic-fate princess is still tier 1 (human).
# A common-fate wolf is tier 0.
# ============================================================

# Species/nature overrides (non-human entities)
SPECIES_POWER_TIER = {
    "rat": 0, "dog": 0, "cat": 0, "wolf": 0, "hawk": 0,
    "bear": 2, "dire wolf": 2, "wyvern": 3,
    "troll": 3, "giant": 3, "ogre": 3,
    "dragon": 4, "ancient dragon": 4, "demon": 4,
    "god": 5, "avatar": 5, "titan": 5,
}

# Roles that elevate a human above tier 1
ROLE_POWER_UPGRADES = {
    # Tier 2 — exceptional humans (trained beyond normal or minor magic)
    "champion": 2, "master assassin": 2, "archmage": 2,
    "legendary warrior": 2, "knight commander": 2, "seer": 2,
    "battle mage": 2, "high priestess": 2, "berserker": 2,
}


def get_default_power_tier(occupation: str) -> int:
    """Get the default power tier for an NPC based on what they are.
    Most humans are tier 1. Specific creatures/roles can be higher."""
    occ_lower = occupation.lower()
    # Check species first (non-human)
    for species, tier in SPECIES_POWER_TIER.items():
        if species in occ_lower:
            return tier
    # Check role upgrades (exceptional humans)
    for role, tier in ROLE_POWER_UPGRADES.items():
        if role in occ_lower:
            return tier
    # Default: human
    return 1


# ============================================================
# DAILY LIFE SIMULATION
# ============================================================

def update_npc_lives(world: World):
    """
    Daily tick: NPCs live their lives.
    Called at dawn. Updates personal_log, moves NPCs, resolves NPC interactions.
    """
    for npc in list(world.npcs.values()):
        if not npc.is_alive or npc.is_companion:
            continue
        # Only simulate noteworthy NPCs (uncommon+)
        if npc.fate < 0.15:
            continue

        # 1. React to world events (everyone hears major news)
        _absorb_world_events(npc, world)

        # 2. Maybe move (travelers, merchants, soldiers roam)
        _maybe_move(npc, world)

        # 3. Daily life flavor (occupation-based)
        _daily_routine(npc, world)

        # 4. Keep log trimmed
        npc.personal_log = npc.personal_log[-15:]

    # 5. NPC-to-NPC interactions (high-fate NPCs talk to each other)
    _resolve_npc_interactions(world)


def _absorb_world_events(npc: NPC, world: World):
    """NPC hears about recent world events. Major events reach everyone."""
    recent_events = [e for e in world.events_log[-5:] if isinstance(e, dict)]
    for event in recent_events:
        day = event.get("day", 0)
        # Only process events from last 3 days
        if world.current_day - day > 3:
            continue
        desc = event.get("description", "")
        # Don't double-log
        if any(f"Day {day}" in entry and desc[:30] in entry for entry in npc.personal_log[-5:]):
            continue
        if _event_relevant_to_npc(desc, npc, world):
            npc.personal_log.append(f"Day {day}: Heard that {desc}")


def _maybe_move(npc: NPC, world: World):
    """Some NPCs travel. Merchants trade, soldiers patrol, travelers wander."""
    mobile_roles = {"traveler", "merchant", "soldier", "messenger", "spy",
                    "pilgrim", "bard", "mercenary", "scout", "trader"}
    if npc.occupation.lower() not in mobile_roles:
        return
    # 10-20% chance of moving per day
    move_chance = 0.10 + npc.fate * 0.1  # higher fate = more active
    if random.random() > move_chance:
        return

    current = world.locations.get(npc.location)
    if not current:
        return

    # Find candidate destinations (siblings and parent)
    candidates = []
    if current.parent_id:
        parent = world.locations.get(current.parent_id)
        if parent:
            for cid in parent.children_ids:
                if cid != npc.location and cid in world.locations:
                    candidates.append(cid)
            # Can also go up to the parent
            candidates.append(current.parent_id)

    if not candidates:
        return

    new_id = random.choice(candidates)
    new_loc = world.locations.get(new_id)
    if new_loc:
        old_name = current.name
        npc.location = new_id
        npc.personal_log.append(
            f"Day {world.current_day}: Traveled from {old_name} to {new_loc.name}."
        )


def _daily_routine(npc: NPC, world: World):
    """Add occasional flavor entries based on occupation. Not every day."""
    if random.random() > 0.15:  # 15% chance of a notable day
        return

    routines = {
        "merchant": [
            "Good day for trade. Sold well.",
            "Quiet market today. Worried about supply routes.",
            "New shipment arrived, but the quality was poor.",
        ],
        "guard": [
            "Uneventful patrol. The walls hold.",
            "Caught a pickpocket near the market.",
            "New faces at the gate today. Travelers from the east.",
        ],
        "scholar": [
            "Found an interesting passage in an old text.",
            "Argued with a colleague about the old histories.",
            "The archive was quiet today. Good for thinking.",
        ],
        "barkeeper": [
            "Busy night. Good tips.",
            "Had to break up a fight between two drunks.",
            "A stranger asked too many questions about the town.",
        ],
        "farmer": [
            "The harvest looks thin this year.",
            "Fixed the fence. Again.",
            "Weather's turning. Winter will be hard.",
        ],
        "soldier": [
            "Drills all morning. The captain is worried.",
            "Heard rumors from the scouts. Something's moving in the east.",
            "Supplies are running low. Morale is steady but strained.",
        ],
    }

    entries = routines.get(npc.occupation.lower(), [
        "Another day. Nothing remarkable.",
        "Something felt different today. Hard to say what.",
    ])
    npc.personal_log.append(f"Day {world.current_day}: {random.choice(entries)}")


def _event_relevant_to_npc(desc: str, npc: NPC, world: World) -> bool:
    """Check if a world event is relevant to an NPC."""
    desc_lower = desc.lower()

    # Major events everyone hears about
    major = ["war", "king", "queen", "dragon", "army", "invasion",
             "famine", "plague", "died", "death", "burning", "siege"]
    if any(kw in desc_lower for kw in major):
        return True

    # Faction-related
    if npc.faction != "none" and npc.faction.lower() in desc_lower:
        return True

    # Location-related
    loc = world.locations.get(npc.location)
    if loc and loc.name.lower() in desc_lower:
        return True

    # Well-connected people hear more
    if npc.fate > 0.30:
        return random.random() < 0.3
    return random.random() < 0.08


# ============================================================
# NPC-TO-NPC INTERACTIONS
# High-fate NPCs talk to each other. Persuasion matters.
# ============================================================

def _resolve_npc_interactions(world: World):
    """Once per day, notable NPCs may interact with each other."""
    # Only NPCs with fate >= 0.30 (rare+) interact
    notable = [n for n in world.npcs.values()
               if n.is_alive and n.fate >= 0.30 and not n.is_companion]

    if len(notable) < 2:
        return

    # 30% chance of an interaction happening today
    if random.random() > 0.30:
        return

    # Pick two NPCs at the same location (or nearby)
    for _ in range(5):  # try a few times to find co-located pair
        a, b = random.sample(notable, 2)
        if a.location == b.location:
            _npc_interact(a, b, world)
            return

    # No co-located pair found — occasionally two important NPCs
    # in different locations exchange messages
    if random.random() < 0.1:
        a, b = random.sample(notable, 2)
        _npc_exchange(a, b, world)


def _npc_interact(npc_a: NPC, npc_b: NPC, world: World):
    """Two NPCs at the same location have an interaction."""
    # Resolve persuasion if one has higher ambition
    if npc_a.stats.ambition > npc_b.stats.ambition + 10:
        success = resolve_npc_persuasion(npc_a, npc_b)
        if success:
            entry_a = f"Day {world.current_day}: Convinced {npc_b.name} to support my cause."
            entry_b = f"Day {world.current_day}: {npc_a.name} made a compelling argument. I'm considering their proposal."
        else:
            entry_a = f"Day {world.current_day}: Spoke with {npc_b.name}. They weren't persuaded."
            entry_b = f"Day {world.current_day}: {npc_a.name} tried to win me over. I declined."
    else:
        # Just a conversation
        entry_a = f"Day {world.current_day}: Had a conversation with {npc_b.name}."
        entry_b = f"Day {world.current_day}: Spoke with {npc_a.name}."

    npc_a.personal_log.append(entry_a)
    npc_b.personal_log.append(entry_b)


def _npc_exchange(npc_a: NPC, npc_b: NPC, world: World):
    """Two distant NPCs exchange messages (letters, envoys)."""
    loc_a = world.locations.get(npc_a.location)
    loc_b = world.locations.get(npc_b.location)
    name_a = loc_a.name if loc_a else "somewhere"
    name_b = loc_b.name if loc_b else "somewhere"

    npc_a.personal_log.append(
        f"Day {world.current_day}: Sent a message to {npc_b.name} in {name_b}."
    )
    npc_b.personal_log.append(
        f"Day {world.current_day}: Received word from {npc_a.name} in {name_a}."
    )


def resolve_npc_persuasion(persuader: NPC, target: NPC) -> bool:
    """
    Resolve one NPC trying to convince another.
    Pure math — charisma and intelligence vs willpower and stubbornness.
    Returns True if persuasion succeeds.
    """
    # Persuader's effectiveness
    persuade = (
        persuader.stats.charisma * 0.30 +
        persuader.stats.intelligence * 0.25 +
        persuader.stats.empathy * 0.20 +
        persuader.stats.education * 0.15 +
        persuader.stats.honesty * 0.10
    )

    # Target's resistance
    resist = (
        target.stats.willpower * 0.30 +
        target.stats.stubbornness * 0.25 +
        target.stats.intelligence * 0.20 +
        target.stats.wisdom * 0.15 +
        target.stats.perception * 0.10
    )

    # Relationship modifier (if they have one)
    if target.relationship:
        persuade += target.relationship.trust * 0.2  # trust helps

    # Roll with randomness
    margin = (persuade - resist) / 100.0 + random.uniform(-0.15, 0.15)
    return margin > 0
