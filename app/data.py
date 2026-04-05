"""
Shared data models — every part of the game imports from here.
These are the core data structures for NPCs, players, locations, and world state.
"""
from dataclasses import dataclass, field
from typing import Optional
import random
import math


# ============================================================
# STATS
# ============================================================

@dataclass
class Stats:
    """All 22 numerical stats for any character (NPC or player)."""
    # Physical (7)
    strength: int = 42
    toughness: int = 42
    agility: int = 42
    health: int = 100       # current health, degrades with injury
    height_cm: int = 170
    weight_kg: int = 70
    attractiveness: int = 42
    # Mental (7)
    intelligence: int = 42
    depth: int = 42
    wisdom: int = 42
    perception: int = 42
    willpower: int = 42
    education: int = 42
    creativity: int = 42
    # Social (8)
    charisma: int = 42
    empathy: int = 42
    courage: int = 42
    honesty: int = 42
    humor: int = 42
    stubbornness: int = 42
    ambition: int = 42
    loyalty: int = 42

    def depth_score(self) -> float:
        """
        The single number that determines how 'interesting' a character is.
        Drives model tier, prompt length, response richness.
        Continuous 0-100.
        """
        return (
            self.depth * 0.30 +
            self.intelligence * 0.20 +
            self.wisdom * 0.15 +
            self.empathy * 0.15 +
            self.creativity * 0.10 +
            self.education * 0.10
        )

    def combat_power(self, weapon_mult=1.0, armor_mult=1.0) -> float:
        """Raw combat power rating (CPR)."""
        base = (
            self.strength * 0.25 +
            self.agility * 0.25 +
            self.toughness * 0.20 +
            self.courage * 0.10 +
            self.perception * 0.10 +
            self.willpower * 0.10
        )
        return base * weapon_mult * armor_mult

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage and context injection."""
        return {
            "strength": self.strength, "toughness": self.toughness,
            "agility": self.agility, "health": self.health,
            "height_cm": self.height_cm, "weight_kg": self.weight_kg,
            "attractiveness": self.attractiveness,
            "intelligence": self.intelligence, "depth": self.depth,
            "wisdom": self.wisdom, "perception": self.perception,
            "willpower": self.willpower, "education": self.education,
            "creativity": self.creativity,
            "charisma": self.charisma, "empathy": self.empathy,
            "courage": self.courage, "honesty": self.honesty,
            "humor": self.humor, "stubbornness": self.stubbornness,
            "ambition": self.ambition, "loyalty": self.loyalty,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Stats":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ============================================================
# RELATIONSHIP (per NPC ↔ player)
# ============================================================

@dataclass
class Relationship:
    """Tracks how an NPC feels about the player. Sparse — most NPCs have none."""
    trust: float = 0.0           # -100 to 100
    attraction: float = 0.0      # 0 to 100
    comfort: float = 0.0         # 0 to 100
    intimacy: float = 0.0        # 0 to 100
    persuasion_progress: float = 0.0
    interactions: int = 0
    flags: list = field(default_factory=list)
    knowledge_of_player: list = field(default_factory=list)
    last_summary: str = ""

    @property
    def stage(self) -> str:
        """Current relationship stage based on metrics."""
        if self.intimacy > 50 and self.trust > 65 and self.comfort > 60:
            if self.trust < 50:
                return "complicated"
            return "intimate"
        if self.attraction > 55 and self.trust > 50 and self.comfort > 45 and self.intimacy > 25:
            return "courting"
        if self.attraction > 40 and self.trust > 35 and self.comfort > 30:
            return "interested"
        if self.trust > 25 and self.comfort > 20:
            return "friendly"
        if self.interactions > 0:
            return "acquaintance"
        return "stranger"

    def to_dict(self) -> dict:
        return {
            "trust": self.trust, "attraction": self.attraction,
            "comfort": self.comfort, "intimacy": self.intimacy,
            "persuasion_progress": self.persuasion_progress,
            "interactions": self.interactions, "flags": self.flags,
            "knowledge_of_player": self.knowledge_of_player,
            "last_summary": self.last_summary, "stage": self.stage,
        }


# ============================================================
# ITEM (weapons, armor, artifacts — from junk to mythic)
# ============================================================

@dataclass
class Item:
    """
    Any item in the game world. Tier determines power level.
    Tier 0 = improvised junk. Tier 4 = mythic god-forged artifact.
    Notable items have names, history, and rumors — they're discoverable
    through tavern gossip, scholar knowledge, and dungeon exploration.
    """
    id: str
    name: str
    type: str                   # weapon, armor, consumable, key, misc
    subtype: str = ""           # long_sword, plate, healing_potion, etc.
    tier: int = 1               # 0=improvised, 1=common, 2=quality, 3=legendary, 4=mythic
    description: str = ""       # what it looks like
    # --- Combat stats ---
    base_multiplier: float = 1.0    # weapon damage multiplier (from WEAPONS table for tier 1)
    tier_multiplier: float = 1.0    # stacks with base: effective = base * tier_mult
    defense: int = 0                # armor defense value
    armor_overrides: dict = field(default_factory=dict)  # override weapon-armor matrix entries
    special_effect: str = ""        # "bleeds target — toughness -5", "ignores chain armor", etc.
    stat_bonuses: dict = field(default_factory=dict)     # {"strength": +10, "courage": +5}
    # --- Lore (empty for common items, rich for notable ones) ---
    history: str = ""           # how it was made, who owned it, what happened to them
    location: str = ""          # where it currently is (location node ID, or "" if carried)
    known_by: list = field(default_factory=list)     # NPC ids who know about this item
    rumor_text: str = ""        # what people whisper in taverns
    guarded_by: str = ""        # what stands between you and the item
    # --- State ---
    carried_by: str = ""        # player or NPC id, or "" if placed in world
    discovered: bool = False    # has the player found/seen this item?
    value: int = 0              # price in coins (0 = priceless / not for sale)

    @property
    def effective_multiplier(self) -> float:
        """Total weapon power: base weapon type × tier scaling."""
        return self.base_multiplier * self.tier_multiplier

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "type": self.type,
            "subtype": self.subtype, "tier": self.tier,
            "description": self.description,
            "base_multiplier": self.base_multiplier,
            "tier_multiplier": self.tier_multiplier,
            "defense": self.defense,
            "armor_overrides": self.armor_overrides,
            "special_effect": self.special_effect,
            "stat_bonuses": self.stat_bonuses,
            "history": self.history, "location": self.location,
            "known_by": self.known_by, "rumor_text": self.rumor_text,
            "guarded_by": self.guarded_by,
            "carried_by": self.carried_by, "discovered": self.discovered,
            "value": self.value,
        }

# Tier multipliers — how much stronger than common (tier 1) gear
ITEM_TIER_MULTIPLIERS = {
    0: 0.3,     # improvised — chair leg, rock, broken bottle
    1: 1.0,     # common — iron sword, leather armor, standard gear
    2: 1.8,     # quality — steel, masterwork, minor enchantment
    3: 4.0,     # legendary — named weapons, ancient craft, powerful magic
    4: 15.0,    # mythic — god-forged, world artifacts, one-of-a-kind
}

# Power tier for entities (NPCs, creatures, beings)
# Used as a multiplier on combat power rating
ENTITY_TIER_MULTIPLIERS = {
    0: 0.5,     # animals — rats, dogs, wolves
    1: 1.0,     # humans — the default, all our math assumes this
    2: 2.5,     # exceptional — legendary warrior, minor magic user, large beast
    3: 6.0,     # superhuman — master mage, giant, troll, wyvern
    4: 25.0,    # mythic — dragon, demigod, ancient being
    5: 100.0,   # divine — god, world-ending force, unkillable without special means
}


# ============================================================
# INJURY
# ============================================================

@dataclass
class Injury:
    """A specific injury a character is carrying."""
    name: str
    severity: str           # minor, moderate, serious, critical
    stat_effects: dict = field(default_factory=dict)  # {"strength": -10}
    days_remaining: int = 0  # 0 = permanent
    description: str = ""

    def to_dict(self):
        return {"name": self.name, "severity": self.severity,
                "stat_effects": self.stat_effects,
                "days_remaining": self.days_remaining,
                "description": self.description}


# ============================================================
# NPC
# ============================================================

@dataclass
class NPC:
    """A non-player character — from background scenery to world-shaping figure."""
    id: str
    name: str
    age: int
    fate: float                   # 0.0 to 1.0 — narrative importance
    stats: Stats
    occupation: str
    social_class: str             # destitute, working, merchant, noble, royal
    wealth: int                   # 0-100
    faction: str = "none"
    faction_loyalty: int = 50
    temperament: str = "calm"     # volatile, calm, melancholy, cheerful, cold
    power_tier: int = 1           # 0=animal, 1=human, 2=exceptional, 3=superhuman, 4=mythic, 5=divine
    location: str = ""            # node ID in spatial tree
    system_prompt: str = ""       # written by Character Author (empty = not yet authored)
    backstory: str = ""           # richness scales with depth/fate
    secret: str = ""
    relationship: Optional[Relationship] = None
    knowledge_tags: list = field(default_factory=list)
    injuries: list = field(default_factory=list)
    schedule_template: str = ""   # key into SCHEDULE_TEMPLATES
    is_companion: bool = False
    is_alive: bool = True
    met_player: bool = False
    model_tier: str = ""          # set by select_npc_model()

    @property
    def depth_score(self) -> float:
        return self.stats.depth_score()

    @property
    def prompt_tokens(self) -> int:
        """How many tokens the Character Author should write for this NPC."""
        return int(40 + self.depth_score * 14)

    @property
    def max_response_words(self) -> int:
        """Soft guideline for how much this NPC talks."""
        return int(15 + self.depth_score * 1.5)

    def get_effective_stats(self) -> Stats:
        """Stats with active injury penalties applied."""
        d = self.stats.to_dict()
        for inj in self.injuries:
            if isinstance(inj, Injury):
                for stat_name, penalty in inj.stat_effects.items():
                    if stat_name in d:
                        d[stat_name] = max(0, d[stat_name] + penalty)
        return Stats.from_dict(d)

    def brief_description(self) -> str:
        """Short description for scene context (what the narrator sees)."""
        age_desc = "young" if self.age < 25 else "middle-aged" if self.age < 50 else "older"
        build = "slight" if self.stats.strength < 30 else "sturdy" if self.stats.strength > 65 else ""
        return f"{self.name}, {age_desc} {build} {self.occupation}".strip()

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "age": self.age,
            "fate": self.fate, "stats": self.stats.to_dict(),
            "occupation": self.occupation, "social_class": self.social_class,
            "wealth": self.wealth, "faction": self.faction,
            "faction_loyalty": self.faction_loyalty,
            "temperament": self.temperament, "location": self.location,
            "system_prompt": self.system_prompt, "backstory": self.backstory,
            "secret": self.secret,
            "relationship": self.relationship.to_dict() if self.relationship else None,
            "knowledge_tags": self.knowledge_tags,
            "injuries": [i.to_dict() if isinstance(i, Injury) else i for i in self.injuries],
            "is_companion": self.is_companion, "is_alive": self.is_alive,
            "met_player": self.met_player, "model_tier": self.model_tier,
            "depth_score": self.depth_score,
        }


# ============================================================
# PLAYER
# ============================================================

@dataclass
class Player:
    """The player character — a special NPC with extra state."""
    name: str
    backstory: str
    stats: Stats
    location: str = ""
    hunger: int = 0               # 0-100, bad above 60
    thirst: int = 0
    fatigue: int = 0
    weapon: str = "unarmed"
    armor: str = "none"
    coins: int = 50
    inventory: list = field(default_factory=list)
    knowledge_log: list = field(default_factory=list)   # things the player has learned
    companions: list = field(default_factory=list)       # list of NPC ids
    injuries: list = field(default_factory=list)
    reputation: dict = field(default_factory=dict)       # city_id → {strength, sentiment}
    nonsense_count: int = 0
    days_alive: int = 0
    kills: int = 0

    @property
    def health(self) -> int:
        return self.stats.health

    @health.setter
    def health(self, val):
        self.stats.health = max(0, min(100, val))

    def get_effective_stats(self) -> Stats:
        d = self.stats.to_dict()
        for inj in self.injuries:
            if isinstance(inj, Injury):
                for stat_name, penalty in inj.stat_effects.items():
                    if stat_name in d:
                        d[stat_name] = max(0, d[stat_name] + penalty)
        # Hunger/fatigue penalties
        if self.hunger > 60:
            d["strength"] = max(0, d["strength"] - 10)
            d["agility"] = max(0, d["agility"] - 10)
        if self.fatigue > 60:
            d["strength"] = max(0, d["strength"] - 5)
            d["perception"] = max(0, d["perception"] - 10)
        return Stats.from_dict(d)

    def has_knowledge(self, topic: str) -> bool:
        """Check if the player has learned about a topic."""
        topic_lower = topic.lower()
        return any(topic_lower in k.lower() for k in self.knowledge_log)

    def to_dict(self) -> dict:
        return {
            "name": self.name, "backstory": self.backstory,
            "stats": self.stats.to_dict(), "location": self.location,
            "hunger": self.hunger, "thirst": self.thirst,
            "fatigue": self.fatigue, "weapon": self.weapon,
            "armor": self.armor, "coins": self.coins,
            "inventory": self.inventory,
            "knowledge_log": self.knowledge_log,
            "companions": self.companions,
            "injuries": [i.to_dict() if isinstance(i, Injury) else i for i in self.injuries],
            "reputation": self.reputation,
            "days_alive": self.days_alive, "kills": self.kills,
        }


# ============================================================
# LOCATION (node in spatial tree)
# ============================================================

@dataclass
class Location:
    """A node in the world's spatial tree. Can be a continent, city, building, or room."""
    id: str
    name: str
    type: str               # continent, region, city, district, building, floor, room
    description: str = ""
    parent_id: str = ""
    children_ids: list = field(default_factory=list)
    danger_rating: int = 0  # 0-100
    economy: str = ""
    features: list = field(default_factory=list)
    coordinates: tuple = (0, 0)
    terrain: str = ""
    mood: str = ""
    # --- Dungeon/exploration fields (empty for normal locations) ---
    is_dungeon: bool = False
    locked: bool = False          # needs a key, high agility, or a puzzle to enter
    lock_difficulty: int = 0      # 0-100, agility check to pick / strength to force
    trap: dict = field(default_factory=dict)   # {"type": "pit", "perception_to_spot": 60, "damage": 30}
    notable_items: list = field(default_factory=list)  # item IDs placed here by world builder

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name, "type": self.type,
            "description": self.description, "parent_id": self.parent_id,
            "children_ids": self.children_ids, "danger_rating": self.danger_rating,
            "economy": self.economy, "features": self.features,
            "coordinates": list(self.coordinates), "terrain": self.terrain,
            "mood": self.mood, "is_dungeon": self.is_dungeon,
            "locked": self.locked, "lock_difficulty": self.lock_difficulty,
            "trap": self.trap, "notable_items": self.notable_items,
        }


# ============================================================
# ROAD (connection between locations)
# ============================================================

@dataclass
class Road:
    """A connection between two locations with travel data."""
    from_id: str
    to_id: str
    distance_km: float
    terrain: str = "road"
    travel_days_foot: float = 1.0
    danger_rating: int = 20

    def to_dict(self):
        return {"from": self.from_id, "to": self.to_id,
                "distance_km": self.distance_km, "terrain": self.terrain,
                "travel_days_foot": self.travel_days_foot,
                "danger_rating": self.danger_rating}


# ============================================================
# WORLD STATE
# ============================================================

@dataclass
class World:
    """The entire game world — locations, NPCs, factions, lore, everything."""
    name: str = ""
    era: str = ""
    tone: str = ""
    themes: list = field(default_factory=list)
    # Spatial data
    locations: dict = field(default_factory=dict)   # id → Location
    roads: list = field(default_factory=list)        # list of Road
    # Characters
    npcs: dict = field(default_factory=dict)         # id → NPC
    # Items and artifacts
    items: dict = field(default_factory=dict)         # id → Item
    # Factions, history, lore
    factions: dict = field(default_factory=dict)
    history: dict = field(default_factory=dict)
    intellectual_traditions: list = field(default_factory=list)
    lore_index: dict = field(default_factory=dict)   # tag → lore snippet text
    antagonist: dict = field(default_factory=dict)
    naming_conventions: str = ""
    religion: dict = field(default_factory=dict)
    economy_info: dict = field(default_factory=dict)
    # Time
    current_day: int = 1
    time_slot: str = "morning"   # dawn, morning, afternoon, evening, night
    season: str = "spring"
    # Events
    events_log: list = field(default_factory=list)
    reputation_queue: list = field(default_factory=list)
    active_conflicts: list = field(default_factory=list)

    def npcs_at_location(self, location_id: str) -> list:
        """Query: which NPCs are at this location?"""
        return [npc for npc in self.npcs.values()
                if npc.location == location_id and npc.is_alive]

    def get_parent_location(self, location_id: str) -> Optional[Location]:
        loc = self.locations.get(location_id)
        if loc and loc.parent_id:
            return self.locations.get(loc.parent_id)
        return None

    def get_city_for_location(self, location_id: str) -> Optional[Location]:
        """Walk up the tree to find the city this location belongs to."""
        loc = self.locations.get(location_id)
        while loc:
            if loc.type == "city":
                return loc
            loc = self.locations.get(loc.parent_id) if loc.parent_id else None
        return None

    def advance_time_slot(self):
        """Move to next time slot, advancing day if needed."""
        slots = ["dawn", "morning", "afternoon", "evening", "night"]
        idx = slots.index(self.time_slot)
        if idx < len(slots) - 1:
            self.time_slot = slots[idx + 1]
        else:
            self.time_slot = "dawn"
            self.current_day += 1
            # Season changes every 90 days
            seasons = ["spring", "summer", "autumn", "winter"]
            self.season = seasons[(self.current_day // 90) % 4]


# ============================================================
# ACTION (output of the interpreter)
# ============================================================

@dataclass
class Action:
    """Structured representation of what the player is trying to do."""
    type: str               # movement, dialogue, action, observation, internal,
                            # combat, trade, stealth, rest, nonsense, romance
    target: str = ""        # entity_id or location_id
    manner: str = ""        # HOW they do it (tone, subtlety, emotion)
    intent: str = ""        # WHY (their apparent goal)
    dialogue_content: str = ""  # exact words if speaking
    feasible: bool = True
    involves_combat: bool = False
    involves_persuasion: bool = False
    involves_deception: bool = False
    covert: bool = False
    raw_input: str = ""     # the original player text

    @classmethod
    def from_dict(cls, d: dict, raw: str = "") -> "Action":
        return cls(
            type=d.get("type", "nonsense"),
            target=d.get("target", ""),
            manner=d.get("manner", ""),
            intent=d.get("intent", ""),
            dialogue_content=d.get("dialogue_content", ""),
            feasible=d.get("feasible", True),
            involves_combat=d.get("involves_combat", False),
            involves_persuasion=d.get("involves_persuasion", False),
            involves_deception=d.get("involves_deception", False),
            covert=d.get("covert", False),
            raw_input=raw,
        )


# ============================================================
# COMBAT OUTCOME
# ============================================================

@dataclass
class CombatOutcome:
    """Result of a resolved combat encounter."""
    result: str              # victory, defeat, fled, standoff
    margin: float            # how decisive (-1 to +1)
    margin_category: str     # decisive, comfortable, narrow, crushing_defeat, etc.
    duration: str            # instant, brief, prolonged, grueling
    mood: str                # dominant, controlled, desperate, etc.
    player_injuries: list = field(default_factory=list)
    companion_outcomes: list = field(default_factory=list)  # [{name, status, action}]
    enemy_deaths: int = 0
    notable_moments: list = field(default_factory=list)
    loot: dict = field(default_factory=dict)
    is_decision_point: bool = False
    decision_prompt: str = ""


# ============================================================
# GAME STATE (top-level container)
# ============================================================

@dataclass
class GameState:
    """Everything needed to save/load a game."""
    world: World = field(default_factory=World)
    player: Optional[Player] = None
    turn_number: int = 0
    action_log: list = field(default_factory=list)      # recent turns (verbatim)
    summary_log: list = field(default_factory=list)      # compressed older turns
    flagged_moments: list = field(default_factory=list)  # never compressed
    game_over: bool = False
    death_reason: str = ""


# ============================================================
# WEAPON AND ARMOR DATA
# ============================================================

WEAPONS = {
    "unarmed":      {"multiplier": 0.6, "speed": "fast", "display": "bare fists"},
    "dagger":       {"multiplier": 0.8, "speed": "fast", "display": "dagger"},
    "short_sword":  {"multiplier": 1.0, "speed": "medium", "display": "short sword"},
    "long_sword":   {"multiplier": 1.15, "speed": "medium", "display": "long sword"},
    "two_hand_sword": {"multiplier": 1.3, "speed": "slow", "display": "two-handed sword"},
    "spear":        {"multiplier": 1.1, "speed": "medium", "display": "spear"},
    "mace":         {"multiplier": 1.05, "speed": "medium", "display": "mace"},
    "war_axe":      {"multiplier": 1.2, "speed": "slow", "display": "war axe"},
    "bow":          {"multiplier": 1.1, "speed": "ranged", "display": "bow"},
    "crossbow":     {"multiplier": 1.25, "speed": "slow", "display": "crossbow"},
}

ARMOR = {
    "none":    {"defense": 0, "display": "no armor"},
    "leather": {"defense": 8, "display": "leather armor"},
    "chain":   {"defense": 18, "display": "chain mail"},
    "plate":   {"defense": 30, "display": "plate armor"},
}

# Weapon effectiveness vs armor type (multiplier on weapon's base)
# Values < 1.0 = weapon is bad against that armor
WEAPON_ARMOR_MATRIX = {
    "unarmed":       {"none": 1.0, "leather": 0.6, "chain": 0.3, "plate": 0.15},
    "dagger":        {"none": 1.0, "leather": 0.8, "chain": 0.4, "plate": 0.2},
    "short_sword":   {"none": 1.0, "leather": 0.9, "chain": 0.65, "plate": 0.4},
    "long_sword":    {"none": 1.0, "leather": 0.95, "chain": 0.7, "plate": 0.5},
    "two_hand_sword":{"none": 1.0, "leather": 1.0, "chain": 0.8, "plate": 0.6},
    "spear":         {"none": 1.0, "leather": 0.9, "chain": 0.6, "plate": 0.45},
    "mace":          {"none": 0.9, "leather": 0.95, "chain": 1.0, "plate": 0.85},
    "war_axe":       {"none": 1.0, "leather": 1.0, "chain": 0.85, "plate": 0.7},
    "bow":           {"none": 1.0, "leather": 0.85, "chain": 0.5, "plate": 0.3},
    "crossbow":      {"none": 1.0, "leather": 0.95, "chain": 0.75, "plate": 0.55},
}

# Prices in coins
PRICES = {
    "dagger": 15, "short_sword": 40, "long_sword": 80, "two_hand_sword": 150,
    "spear": 35, "mace": 45, "war_axe": 90, "bow": 60, "crossbow": 100,
    "leather": 60, "chain": 200, "plate": 750,
    "food_day": 3, "lodging_poor": 2, "lodging_decent": 8, "lodging_fine": 25,
    "horse": 300, "healing_potion": 20,
}
