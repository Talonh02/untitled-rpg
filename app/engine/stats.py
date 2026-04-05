"""
Stat generation for NPCs and players.
Uses gaussian distributions shaped by fate, occupation, social class, and age.
All formulas from MECHANICS.md.
"""
import random
import math

from app.data import Stats
from app.config import GAME_CONSTANTS


# ============================================================
# OCCUPATION STAT MODIFIERS
# Each occupation boosts some stats and suppresses others.
# Boosts are +10 to +15, suppressions are -5 to -10.
# ============================================================

OCCUPATION_MODIFIERS = {
    "soldier":    {"boosts": {"strength": 12, "toughness": 12, "courage": 10},
                   "suppresses": {"education": -8, "creativity": -5}},
    "scholar":    {"boosts": {"intelligence": 15, "education": 12, "depth": 10},
                   "suppresses": {"strength": -8, "toughness": -5}},
    "merchant":   {"boosts": {"charisma": 12, "perception": 10, "ambition": 12},
                   "suppresses": {"courage": -5, "creativity": -5}},
    "farmer":     {"boosts": {"toughness": 12, "wisdom": 10, "loyalty": 10},
                   "suppresses": {"education": -8, "ambition": -5}},
    "thief":      {"boosts": {"agility": 15, "perception": 12, "creativity": 10},
                   "suppresses": {"honesty": -10, "loyalty": -5}},
    "priest":     {"boosts": {"willpower": 12, "empathy": 12, "education": 10},
                   "suppresses": {"agility": -5, "ambition": -5}},
    "noble":      {"boosts": {"education": 12, "charisma": 12, "ambition": 10},
                   "suppresses": {"toughness": -5, "empathy": -5}},
    "artist":     {"boosts": {"creativity": 15, "depth": 12, "empathy": 10},
                   "suppresses": {"strength": -5, "stubbornness": -5}},
    "blacksmith": {"boosts": {"strength": 15, "toughness": 12, "willpower": 10},
                   "suppresses": {"charisma": -5, "education": -5}},
    "healer":     {"boosts": {"empathy": 15, "wisdom": 12, "perception": 10},
                   "suppresses": {"strength": -5, "ambition": -5}},
    "spy":        {"boosts": {"perception": 15, "agility": 12, "charisma": 10},
                   "suppresses": {"honesty": -10, "loyalty": -8}},
    "beggar":     {"boosts": {"perception": 10, "courage": 10, "creativity": 10},
                   "suppresses": {"education": -8}},
    # Fallback for occupations not in the table — no modifiers
}


# ============================================================
# SOCIAL CLASS FLOORS/CEILINGS for wealth and education
# A noble can't have education 10 (they had tutors).
# A beggar can't have wealth 80.
# ============================================================

SOCIAL_CLASS_RANGES = {
    "destitute": {"wealth": (0, 15),   "education": (0, 20)},
    "working":   {"wealth": (10, 40),  "education": (5, 40)},
    "merchant":  {"wealth": (35, 75),  "education": (25, 65)},
    "noble":     {"wealth": (60, 95),  "education": (50, 85)},
    "royal":     {"wealth": (85, 100), "education": (70, 95)},
}


def _clamp(value, low=0, high=100):
    """Keep a value within bounds."""
    return int(max(low, min(high, value)))


def _roll_stat(mean, std):
    """Roll a single stat from a gaussian, clamped 0-100."""
    return _clamp(random.gauss(mean, std))


def _apply_occupation_modifiers(stats_dict, occupation):
    """
    Nudge stats based on occupation.
    Boosts add +10 to +15, suppressions subtract -5 to -10.
    """
    mods = OCCUPATION_MODIFIERS.get(occupation, {})
    for stat_name, bonus in mods.get("boosts", {}).items():
        if stat_name in stats_dict:
            stats_dict[stat_name] = _clamp(stats_dict[stat_name] + bonus)
    for stat_name, penalty in mods.get("suppresses", {}).items():
        if stat_name in stats_dict:
            stats_dict[stat_name] = _clamp(stats_dict[stat_name] + penalty)
    return stats_dict


def _apply_social_class(stats_dict, social_class):
    """
    Enforce wealth and education floors/ceilings based on social class.
    A noble's education can't be below 50. A beggar's wealth can't be above 15.
    """
    ranges = SOCIAL_CLASS_RANGES.get(social_class, {})
    for stat_name, (floor, ceiling) in ranges.items():
        if stat_name in stats_dict:
            stats_dict[stat_name] = _clamp(stats_dict[stat_name], floor, ceiling)
    return stats_dict


def _apply_age_modifiers(stats_dict, age):
    """
    Age affects physical and mental stats.
    Young people are weaker physically but haven't gained wisdom yet.
    Old people lose physical ability but gain wisdom and depth.
    """
    # Physical modifiers — multipliers on strength, toughness, agility
    if age < 18:
        stats_dict["strength"] = _clamp(int(stats_dict["strength"] * 0.7))
        stats_dict["toughness"] = _clamp(int(stats_dict["toughness"] * 0.8))
        stats_dict["agility"] = _clamp(int(stats_dict["agility"] * 0.9))
    elif age <= 35:
        pass  # peak physical years, no change
    elif age <= 50:
        stats_dict["strength"] = _clamp(int(stats_dict["strength"] * 0.9))
        stats_dict["agility"] = _clamp(int(stats_dict["agility"] * 0.95))
    elif age <= 65:
        stats_dict["strength"] = _clamp(int(stats_dict["strength"] * 0.75))
        stats_dict["agility"] = _clamp(int(stats_dict["agility"] * 0.8))
        stats_dict["toughness"] = _clamp(int(stats_dict["toughness"] * 0.85))
    else:  # over 65
        stats_dict["strength"] = _clamp(int(stats_dict["strength"] * 0.6))
        stats_dict["agility"] = _clamp(int(stats_dict["agility"] * 0.65))
        stats_dict["toughness"] = _clamp(int(stats_dict["toughness"] * 0.7))

    # Mental modifiers — wisdom and depth grow with age
    if age < 25:
        stats_dict["wisdom"] = _clamp(int(stats_dict["wisdom"] * 0.7))
        stats_dict["depth"] = _clamp(int(stats_dict["depth"] * 0.8))
    elif age <= 40:
        stats_dict["wisdom"] = _clamp(int(stats_dict["wisdom"] * 0.9))
    elif age <= 60:
        stats_dict["wisdom"] = _clamp(stats_dict["wisdom"] + 10)
        stats_dict["depth"] = _clamp(stats_dict["depth"] + 5)
        stats_dict["perception"] = _clamp(stats_dict["perception"] + 5)
    else:  # over 60
        stats_dict["wisdom"] = _clamp(stats_dict["wisdom"] + 15)
        stats_dict["depth"] = _clamp(stats_dict["depth"] + 10)
        stats_dict["perception"] = _clamp(stats_dict["perception"] - 5)  # senses fade

    return stats_dict


def _apply_stat_correlations(stats_dict):
    """
    Soft corrections for truly incoherent stat combos.
    Most contradictions are kept — they make characters interesting.
    Only correct ~70% of the time for the ones we do touch.
    """
    # Smart but uneducated — interesting but rare. Nudge education up 70% of the time.
    if stats_dict["intelligence"] > 70 and stats_dict["education"] < 30:
        if random.random() > 0.3:
            stats_dict["education"] = _clamp(stats_dict["education"] + random.randint(5, 15))

    # Empathetic but dishonest — manipulator archetype. Keep 40% of the time.
    if stats_dict["empathy"] > 70 and stats_dict["honesty"] < 30:
        if random.random() > 0.4:
            stats_dict["honesty"] = _clamp(stats_dict["honesty"] + random.randint(5, 10))

    # Brave but slow — the tank. Always valid, no correction needed.
    # Deep but humorless — valid archetype, no correction.
    # Charming but cold — sociopath archetype, ALWAYS keep.

    return stats_dict


def _roll_physical_attributes(fate):
    """
    Roll height and weight. Fate doesn't really affect these much —
    physical size is mostly random.
    """
    # Height: normal distribution around 170cm, std 10
    height = _clamp(int(random.gauss(170, 10)), 140, 210)
    # Weight correlates loosely with height
    base_weight = 45 + (height - 140) * 0.5
    weight = _clamp(int(random.gauss(base_weight, 12)), 40, 130)
    return height, weight


def generate_npc_stats(fate=0.0, occupation="", social_class="working", age=30):
    """
    Generate a full Stats object for an NPC.

    Args:
        fate: 0.0 to 1.0 — narrative importance. Reshapes the stat distribution.
              Higher fate = higher mean AND wider variance (more extreme stats).
        occupation: string like "soldier", "scholar", etc. Nudges relevant stats.
        social_class: "destitute", "working", "merchant", "noble", "royal".
                      Enforces wealth/education floors and ceilings.
        age: character's age. Affects physical decline and wisdom gain.

    Returns:
        A Stats object with all 22 stats filled in.
    """
    # Base distribution parameters, shaped by fate
    base_mean = GAME_CONSTANTS["base_stat_mean"]  # 42
    base_std = GAME_CONSTANTS["base_stat_std"]     # 16
    stat_mean = base_mean + (fate * 30)
    stat_std = base_std + (fate * 8)

    # Roll all the core stats from the fate-shaped gaussian
    stat_names = [
        "strength", "toughness", "agility", "attractiveness",
        "intelligence", "depth", "wisdom", "perception",
        "willpower", "education", "creativity",
        "charisma", "empathy", "courage", "honesty",
        "humor", "stubbornness", "ambition", "loyalty",
    ]
    stats_dict = {}
    for name in stat_names:
        stats_dict[name] = _roll_stat(stat_mean, stat_std)

    # Roll wealth separately (will be clamped by social class later)
    stats_dict["wealth"] = _roll_stat(stat_mean, stat_std)

    # Apply modifiers in order: occupation → correlations → social class → age
    stats_dict = _apply_occupation_modifiers(stats_dict, occupation)
    stats_dict = _apply_stat_correlations(stats_dict)
    stats_dict = _apply_social_class(stats_dict, social_class)
    stats_dict = _apply_age_modifiers(stats_dict, age)

    # Physical attributes (height, weight) don't use the fate distribution
    height, weight = _roll_physical_attributes(fate)

    return Stats(
        strength=stats_dict["strength"],
        toughness=stats_dict["toughness"],
        agility=stats_dict["agility"],
        health=100,  # everyone starts healthy
        height_cm=height,
        weight_kg=weight,
        attractiveness=stats_dict["attractiveness"],
        intelligence=stats_dict["intelligence"],
        depth=stats_dict["depth"],
        wisdom=stats_dict["wisdom"],
        perception=stats_dict["perception"],
        willpower=stats_dict["willpower"],
        education=stats_dict["education"],
        creativity=stats_dict["creativity"],
        charisma=stats_dict["charisma"],
        empathy=stats_dict["empathy"],
        courage=stats_dict["courage"],
        honesty=stats_dict["honesty"],
        humor=stats_dict["humor"],
        stubbornness=stats_dict["stubbornness"],
        ambition=stats_dict["ambition"],
        loyalty=stats_dict["loyalty"],
    )


def generate_player_stats(traits_dict=None):
    """
    Generate stats for the player character.
    Players use a higher base mean (55 instead of 42) — they're above average.

    Args:
        traits_dict: optional dict of stat overrides, e.g. {"strength": 70, "intelligence": 80}.
                     Any stat not specified is rolled normally.

    Returns:
        A Stats object for the player.
    """
    player_mean = GAME_CONSTANTS["player_stat_mean"]  # 55
    player_std = GAME_CONSTANTS["base_stat_std"]       # 16

    stat_names = [
        "strength", "toughness", "agility", "attractiveness",
        "intelligence", "depth", "wisdom", "perception",
        "willpower", "education", "creativity",
        "charisma", "empathy", "courage", "honesty",
        "humor", "stubbornness", "ambition", "loyalty",
    ]

    stats_dict = {}
    for name in stat_names:
        # If the player specified this trait, use it; otherwise roll
        if traits_dict and name in traits_dict:
            stats_dict[name] = _clamp(traits_dict[name])
        else:
            stats_dict[name] = _roll_stat(player_mean, player_std)

    # Player wealth is set by game start, not rolled here
    height, weight = _roll_physical_attributes(0.5)

    return Stats(
        strength=stats_dict["strength"],
        toughness=stats_dict["toughness"],
        agility=stats_dict["agility"],
        health=100,
        height_cm=height,
        weight_kg=weight,
        attractiveness=stats_dict["attractiveness"],
        intelligence=stats_dict["intelligence"],
        depth=stats_dict["depth"],
        wisdom=stats_dict["wisdom"],
        perception=stats_dict["perception"],
        willpower=stats_dict["willpower"],
        education=stats_dict["education"],
        creativity=stats_dict["creativity"],
        charisma=stats_dict["charisma"],
        empathy=stats_dict["empathy"],
        courage=stats_dict["courage"],
        honesty=stats_dict["honesty"],
        humor=stats_dict["humor"],
        stubbornness=stats_dict["stubbornness"],
        ambition=stats_dict["ambition"],
        loyalty=stats_dict["loyalty"],
    )
