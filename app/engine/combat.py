"""
Combat resolution engine — auto-resolves fights with decision points.
No AI calls here. Pure math from MECHANICS.md, then the Narrator writes the prose.

The flow:
1. Calculate each side's total combat power (CPR * weapon * armor effectiveness)
2. Apply context modifiers (sneak attack, fatigue, terrain, darkness, numbers)
3. Add ±20% randomness per side
4. Compute margin = (player_roll - enemy_roll) / (player_roll + enemy_roll)
5. If margin is close (±0.08) and stakes aren't trivial → decision point
6. Otherwise → resolve outcome, roll injuries, roll deaths
"""
import random
import math

from app.data import (
    Stats, NPC, Player, CombatOutcome, Injury, Unit,
    WEAPONS, ARMOR, WEAPON_ARMOR_MATRIX, ENTITY_TIER_MULTIPLIERS
)
from app.config import GAME_CONSTANTS


# ============================================================
# INJURY TABLES — from MECHANICS.md
# Each entry becomes an Injury object with stat penalties and duration.
# ============================================================

MINOR_INJURIES = [
    {"name": "bruised ribs",   "severity": "minor",
     "stat_effects": {"strength": -5}, "days": 3,
     "description": "A sharp ache with every breath."},
    {"name": "black eye",      "severity": "minor",
     "stat_effects": {"perception": -3}, "days": 2,
     "description": "Swollen shut, throbbing."},
    {"name": "split lip",      "severity": "minor",
     "stat_effects": {"charisma": -3}, "days": 1,
     "description": "Blood on your teeth when you smile."},
    {"name": "twisted ankle",  "severity": "minor",
     "stat_effects": {"agility": -5}, "days": 3,
     "description": "Every step sends a jolt up your leg."},
    {"name": "scratches",      "severity": "minor",
     "stat_effects": {}, "days": 1,
     "description": "Superficial cuts. They sting more than anything."},
]

MODERATE_INJURIES = [
    {"name": "deep cut on arm",  "severity": "moderate",
     "stat_effects": {"strength": -10}, "days": 7,
     "description": "A long gash that won't stop seeping."},
    {"name": "cracked ribs",     "severity": "moderate",
     "stat_effects": {"strength": -8, "agility": -5}, "days": 10,
     "description": "Breathing is an exercise in pain management."},
    {"name": "concussion",       "severity": "moderate",
     "stat_effects": {"intelligence": -10, "perception": -8}, "days": 5,
     "description": "The world tilts when you turn your head."},
    {"name": "sprained wrist",   "severity": "moderate",
     "stat_effects": {"strength": -8}, "days": 7,
     "description": "Your grip is weak and unreliable."},
    {"name": "gash on leg",      "severity": "moderate",
     "stat_effects": {"agility": -12}, "days": 7,
     "description": "Your trousers are dark with blood below the knee."},
]

SERIOUS_INJURIES = [
    {"name": "broken arm",       "severity": "serious",
     "stat_effects": {"strength": -15}, "days": 20,
     "description": "The bone is wrong under the skin. No two-handed weapons."},
    {"name": "broken ribs",      "severity": "serious",
     "stat_effects": {"strength": -15, "agility": -10}, "days": 15,
     "description": "Something grinds inside when you move."},
    {"name": "deep stab wound",  "severity": "serious",
     "stat_effects": {"strength": -10, "agility": -10}, "days": 14,
     "description": "Needs treatment or it will worsen. Dark blood."},
    {"name": "shattered knee",   "severity": "serious",
     "stat_effects": {"agility": -20}, "days": 25,
     "description": "Your knee bends the wrong way under weight."},
    {"name": "fractured skull",  "severity": "serious",
     "stat_effects": {"intelligence": -15}, "days": 20,
     "description": "Blinding headaches. Risk of death if untreated."},
]

CRITICAL_INJURIES = [
    {"name": "severed hand",       "severity": "critical",
     "stat_effects": {"strength": -15, "agility": -10}, "days": 0,
     "description": "Permanent. Weapon effectiveness halved. No shield."},
    {"name": "blinded in one eye", "severity": "critical",
     "stat_effects": {"perception": -20}, "days": 0,
     "description": "Permanent. Ranged accuracy halved. Depth perception gone."},
    {"name": "crushed leg",        "severity": "critical",
     "stat_effects": {"agility": -25}, "days": 0,
     "description": "Permanent. Travel speed halved. You'll never run again."},
    {"name": "gutted",             "severity": "critical",
     "stat_effects": {"strength": -20, "agility": -15}, "days": 1,
     "description": "Death in one day without immediate treatment."},
    {"name": "spine damage",       "severity": "critical",
     "stat_effects": {"strength": -20, "agility": -20}, "days": 0,
     "description": "Permanent. Everything is harder now."},
]


# ============================================================
# LOSS ENGINE — smooth margin-based damage for individuals and units
# ============================================================

def calculate_hp_damage(margin, armor_name="none"):
    """
    Calculate HP damage from combat based on margin of victory.
    Smooth curve — winners get scratched, losers get hurt badly.

    margin  0.5 → ~5 HP  (crushing victory, barely touched)
    margin  0.15 → ~25 HP (narrow win, took some hits)
    margin  0.0 → ~40 HP  (dead even, both sides bloodied)
    margin -0.15 → ~55 HP (narrow loss, serious damage)
    margin -0.5 → ~80 HP  (crushing defeat, nearly killed)
    """
    # Base damage: scales inversely with margin
    base = max(0, 45 - margin * 80)

    # Armor reduces damage (plate=30 → 30% reduction)
    # FIX 7: armor_factor multiplier 1.0 (was 0.5) — plate now gives true 30% reduction
    armor_defense = ARMOR.get(armor_name, ARMOR["none"])["defense"]
    armor_factor = 1.0 - (armor_defense / 100.0) * 1.0

    damage = base * armor_factor * random.uniform(0.8, 1.2)
    return max(0, int(damage))


def calculate_unit_losses(unit, margin, is_winner):
    """
    Calculate casualties for a unit after combat. Three phases:

    1. CLASH — initial engagement losses (margin-based)
    2. ARMOR MITIGATION — better-armored units lose fewer
    3. ROUT — if morale breaks, fleeing troops get cut down (15-35% extra)

    Returns dict: {battle_losses, rout_losses, total, morale_after, routed}
    """
    # --- Phase 1: Clash casualties from margin ---
    if is_winner:
        # Winners lose 2-15% (less with bigger margin)
        base_rate = max(0.02, 0.15 - abs(margin) * 0.3)
    else:
        # Losers lose 15-70% (more with bigger margin)
        base_rate = min(0.70, 0.15 + abs(margin) * 0.7)

    # --- Phase 2: Armor mitigation ---
    # Plate (defense=30) reduces casualty rate by ~12%
    armor_defense = ARMOR.get(unit.armor, ARMOR["none"])["defense"]
    armor_factor = 1.0 - (armor_defense / 100.0) * 0.4
    base_rate *= armor_factor

    # Randomness ±25%
    base_rate *= random.uniform(0.75, 1.25)
    base_rate = max(0.01, min(0.85, base_rate))

    battle_losses = max(1, int(unit.count * base_rate))

    # --- Phase 3: Rout ---
    # If morale will drop below 20, the unit breaks.
    # Fleeing troops get cut down — 15-35% of survivors die in the rout.
    morale_hit = int(base_rate * 30)
    projected_morale = unit.morale - morale_hit
    routed = projected_morale < 20

    rout_losses = 0
    if routed:
        remaining_after_clash = unit.count - battle_losses
        rout_rate = random.uniform(0.15, 0.35)
        rout_losses = max(0, int(remaining_after_clash * rout_rate))

    total = min(battle_losses + rout_losses, unit.count - 1)  # at least 1 survivor

    # Apply casualties and morale
    unit.count = max(1, unit.count - total)
    unit.morale = max(0, unit.morale - morale_hit - (15 if routed else 0))

    return {
        "battle_losses": battle_losses,
        "rout_losses": rout_losses,
        "total": total,
        "morale_after": unit.morale,
        "routed": routed,
    }


def _get_weapon_data(weapon_name):
    """Look up weapon multiplier and other data. Falls back to unarmed."""
    return WEAPONS.get(weapon_name, WEAPONS["unarmed"])


def _get_armor_type(armor_name):
    """Get the armor type string for matrix lookup. Falls back to 'none'."""
    if armor_name in ARMOR:
        return armor_name
    return "none"


def _get_armor_defense(armor_name):
    """Get the flat defense value of armor (0-30)."""
    return ARMOR.get(armor_name, ARMOR["none"])["defense"]


def _calculate_cpr(combatant):
    """
    Calculate a combatant's raw Combat Power Rating.
    For individuals: base_stats * power_tier
    For Units: base_stats * power_tier * numbers_advantage(count)

    Power tier: human=1x, exceptional=2.5x, superhuman=6x, dragon=25x, divine=100x
    Numbers advantage: 1 + log2(count) * 0.7
    """
    # Units include numbers advantage in their CPR
    if isinstance(combatant, Unit):
        base_cpr = combatant.stats.combat_power()
        tier_mult = ENTITY_TIER_MULTIPLIERS.get(combatant.power_tier, 1.0)
        numbers_mult = 1.0 + math.log2(max(1, combatant.count)) * 0.7
        return base_cpr * tier_mult * numbers_mult

    # Individual NPC or Player
    if hasattr(combatant, "get_effective_stats"):
        stats = combatant.get_effective_stats()
    elif hasattr(combatant, "stats"):
        stats = combatant.stats
    else:
        return 42.0  # fallback for broken data

    base_cpr = stats.combat_power()
    power_tier = getattr(combatant, "power_tier", 1)
    tier_mult = ENTITY_TIER_MULTIPLIERS.get(power_tier, 1.0)

    return base_cpr * tier_mult


def _get_combatant_weapon(combatant):
    """Get the weapon name from a combatant (Player or NPC)."""
    if hasattr(combatant, "weapon"):
        return combatant.weapon
    return "unarmed"


def _get_combatant_armor(combatant):
    """Get the armor name from a combatant (Player or NPC)."""
    if hasattr(combatant, "armor"):
        return combatant.armor
    return "none"


def check_companion_participation(companion, context=None):
    """
    Determine if a companion actually fights alongside the player.
    Based on trust, loyalty, courage, and ambition — plus situational modifiers.

    Args:
        companion: NPC object (must have relationship and stats)
        context: optional dict with keys like "player_started_fight",
                 "defending_from_attack", "enemy_count", "enemy_has_grudge"

    Returns:
        One of: "fights_bravely", "fights_reluctantly", "fled", "refused", "froze"
    """
    if context is None:
        context = {}

    # Get trust — default to 30 if no relationship exists
    trust = 30.0
    if companion.relationship:
        trust = companion.relationship.trust

    # Willingness score (0-100 scale)
    willingness = (
        trust * 0.35 +
        companion.stats.loyalty * 0.25 +
        companion.stats.courage * 0.25 +
        companion.stats.ambition * 0.15
    )

    # Situational modifiers
    if context.get("player_started_fight", False):
        willingness -= 15     # they didn't ask for this
    if context.get("defending_from_attack", False):
        willingness += 20     # self-preservation kicks in
    if context.get("enemy_count", 1) > 4:
        willingness -= 10     # overwhelming odds are scary
    if context.get("enemy_has_grudge", False):
        willingness += 25     # personal motivation

    # Roll against willingness
    participation_roll = random.uniform(0, 100)

    if participation_roll < willingness:
        # They fight — how enthusiastically?
        if willingness - participation_roll > 30:
            return "fights_bravely"       # +5% CPR bonus
        else:
            return "fights_reluctantly"   # no bonus, might freeze mid-combat
    else:
        # They don't fight — why not?
        if companion.stats.courage < 30:
            return "fled"                 # ran away
        elif companion.stats.honesty > 60:
            return "refused"              # told you no straight up
        else:
            return "froze"                # wanted to help, couldn't move


def roll_injuries(margin, combatant_armor="none"):
    """
    Roll for injuries after combat based on the margin of victory/defeat.
    Even winners can get hurt — just less likely.

    Args:
        margin: float from -1 to +1. Positive = this side won.
        combatant_armor: armor type string for severity reduction.

    Returns:
        List of Injury objects (could be empty if lucky).
    """
    # Base injury chance depends on margin (from MECHANICS.md)
    if margin > 0.30:
        injury_chance = 0.1      # 10% in a decisive win
    elif margin > 0.15:
        injury_chance = 0.3
    elif margin > 0.03:
        injury_chance = 0.6
    elif margin > -0.03:
        injury_chance = 0.75
    elif margin > -0.15:
        injury_chance = 0.9
    else:
        injury_chance = 0.98     # almost certain in a bad defeat

    # Roll to see if we get injured at all
    if random.random() > injury_chance:
        return []  # no injuries — got lucky

    # How bad? Roll severity, with armor reducing it.
    severity_roll = random.random()
    armor_defense = _get_armor_defense(combatant_armor)
    armor_reduction = armor_defense / 100.0  # 0.0 to 0.30
    severity_roll -= armor_reduction          # armor pushes severity down

    # Pick from the appropriate table
    if severity_roll < 0.3:
        table = MINOR_INJURIES
    elif severity_roll < 0.65:
        table = MODERATE_INJURIES
    elif severity_roll < 0.85:
        table = SERIOUS_INJURIES
    else:
        table = CRITICAL_INJURIES

    entry = random.choice(table)
    injury = Injury(
        name=entry["name"],
        severity=entry["severity"],
        stat_effects=dict(entry["stat_effects"]),  # copy so we don't mutate the table
        days_remaining=entry["days"],               # 0 = permanent
        description=entry["description"],
    )
    return [injury]


def roll_death(margin, combatant, is_player=False):
    """
    Should this combatant die from this fight?

    Args:
        margin: float, negative means this combatant lost
        combatant: Player or NPC object
        is_player: if True, death chance is halved and returns
                   "near_death_choice" instead of True

    Returns:
        False (survived), True (dead), or "near_death_choice" (player gets a choice)
    """
    # Death base chance from margin (from MECHANICS.md)
    if margin > 0.15:
        death_chance = 0.0     # winners almost never die
    elif margin > 0.03:
        death_chance = 0.02    # narrow winners: 2%
    elif margin > -0.03:
        death_chance = 0.05    # standoff: 5%
    elif margin > -0.15:
        death_chance = 0.12    # narrow losers: 12%
    elif margin > -0.30:
        death_chance = 0.25    # clear losers: 25%
    else:
        death_chance = 0.45    # crushed: 45%

    # Toughness and willpower reduce death chance
    stats = combatant.get_effective_stats() if hasattr(combatant, "get_effective_stats") else combatant.stats
    survival_factor = (stats.toughness + stats.willpower) / 200.0
    death_chance *= (1 - survival_factor * 0.4)
    # A tough+willful character (both 80) reduces death chance by ~32%

    # Armor reduces death chance
    armor_name = _get_combatant_armor(combatant)
    armor_defense = _get_armor_defense(armor_name)
    death_chance *= (1 - armor_defense / 100.0)
    # Full plate (30) reduces death chance by 30%

    # Player gets protagonist advantage — death chance halved
    if is_player:
        death_chance *= GAME_CONSTANTS.get("protagonist_death_reduction", 0.5)
        if random.random() < death_chance:
            return "near_death_choice"  # decision point, not instant death
        return False

    return random.random() < death_chance


def resolve_combat(player, enemies, companions=None, context=None):
    """
    Auto-resolve a full combat encounter.

    Args:
        player: Player object
        enemies: list of NPC objects (the opposition)
        companions: optional list of NPC objects (player's allies)
        context: optional dict with situational modifiers:
            - "sneak_attack": bool
            - "player_fatigued": bool
            - "terrain": str ("narrow", "open", etc.)
            - "darkness": bool
            - "stakes": str ("trivial", "normal", "high")
            - "player_started_fight": bool
            - "defending_from_attack": bool

    Returns:
        CombatOutcome with result, margin, injuries, companion outcomes, etc.
    """
    if context is None:
        context = {}
    if companions is None:
        companions = []
    if not enemies:
        # No enemies — instant victory (shouldn't normally happen)
        return CombatOutcome(
            result="victory", margin=1.0, margin_category="decisive",
            duration="instant", mood="calm"
        )

    # --- Step 1: Determine companion participation ---
    companion_outcomes = []
    fighting_companions = []
    for comp in companions:
        status = check_companion_participation(comp, context)
        companion_outcomes.append({
            "name": comp.name, "id": comp.id, "status": status
        })
        if status in ("fights_bravely", "fights_reluctantly"):
            fighting_companions.append((comp, status))

    # --- Step 1b: Player-side units (hired mercs, etc.) ---
    # Units bypass companion participation check — they're paid to fight.
    player_units = context.get("player_units", [])
    for unit in player_units:
        if unit.should_flee():
            companion_outcomes.append({
                "name": unit.name, "id": unit.id, "status": "fled",
                "count": unit.count,
            })
        else:
            companion_outcomes.append({
                "name": unit.name, "id": unit.id, "status": "fights_bravely",
                "count": unit.count,
            })
            # Units add their full effective_cpr (includes numbers advantage)
            fighting_companions.append((unit, "fights_bravely"))

    # --- Step 2: Calculate player side's total combat power ---
    # Figure out the most common enemy armor for weapon effectiveness lookup
    enemy_armors = [_get_combatant_armor(e) for e in enemies]
    # Use the most common armor type among enemies
    enemy_armor_avg = max(set(enemy_armors), key=enemy_armors.count) if enemy_armors else "none"

    player_weapon = _get_combatant_weapon(player)
    player_armor = _get_combatant_armor(player)
    weapon_data = _get_weapon_data(player_weapon)

    # Player's CPR with weapon × armor effectiveness
    player_cpr = _calculate_cpr(player)
    weapon_armor_eff = WEAPON_ARMOR_MATRIX.get(player_weapon, WEAPON_ARMOR_MATRIX["unarmed"]).get(enemy_armor_avg, 1.0)
    player_total = player_cpr * weapon_data["multiplier"] * weapon_armor_eff

    # Add companions who are fighting
    for comp, status in fighting_companions:
        comp_cpr = _calculate_cpr(comp)
        comp_weapon = _get_combatant_weapon(comp)
        comp_weapon_data = _get_weapon_data(comp_weapon)
        comp_eff = WEAPON_ARMOR_MATRIX.get(comp_weapon, WEAPON_ARMOR_MATRIX["unarmed"]).get(enemy_armor_avg, 1.0)
        comp_power = comp_cpr * comp_weapon_data["multiplier"] * comp_eff
        if status == "fights_bravely":
            comp_power *= 1.05  # 5% bonus for bravery
        player_total += comp_power

    # --- Step 3: Calculate enemy side's total combat power ---
    # Most common player-side armor for enemy weapon effectiveness
    player_side_armors = [player_armor] + [_get_combatant_armor(c) for c, _ in fighting_companions]
    player_armor_avg = max(set(player_side_armors), key=player_side_armors.count)

    enemy_total = 0
    for enemy in enemies:
        e_cpr = _calculate_cpr(enemy)
        e_weapon = _get_combatant_weapon(enemy)
        e_weapon_data = _get_weapon_data(e_weapon)
        e_eff = WEAPON_ARMOR_MATRIX.get(e_weapon, WEAPON_ARMOR_MATRIX["unarmed"]).get(player_armor_avg, 1.0)
        enemy_total += e_cpr * e_weapon_data["multiplier"] * e_eff

    # --- Step 4: Apply context modifiers ---
    if context.get("sneak_attack", False):
        player_total *= GAME_CONSTANTS.get("sneak_attack_multiplier", 1.4)

    if context.get("player_fatigued", False):
        player_total *= 0.85  # 15% fatigue penalty

    player_count = 1 + len(fighting_companions)
    enemy_count = len(enemies)

    # Narrow terrain negates numbers advantage for the larger side
    if context.get("terrain") == "narrow" and enemy_count > player_count:
        enemy_total *= (player_count / enemy_count) ** 0.3

    # Darkness hurts both sides, but perception helps
    if context.get("darkness", False):
        player_perception = player.get_effective_stats().perception if hasattr(player, "get_effective_stats") else player.stats.perception
        player_total *= 0.8 + (player_perception / 500.0)
        avg_enemy_perception = sum(e.stats.perception for e in enemies) / len(enemies)
        enemy_total *= 0.8 + (avg_enemy_perception / 500.0)

    # Numbers advantage (diminishing returns via log2)
    # FIX 6: numbers advantage coefficient 0.25 (was 0.4) — reduces zerg bonus
    if player_count > enemy_count and enemy_count > 0:
        ratio = player_count / enemy_count
        player_total *= 1 + (math.log2(ratio) * 0.25)
    elif enemy_count > player_count and player_count > 0:
        ratio = enemy_count / player_count
        enemy_total *= 1 + (math.log2(ratio) * 0.25)

    # --- Step 5: Add randomness (±20% per side) ---
    player_roll = player_total * random.uniform(0.8, 1.2)
    enemy_roll = enemy_total * random.uniform(0.8, 1.2)

    # --- Step 6: Calculate margin ---
    total = player_roll + enemy_roll
    if total == 0:
        total = 1  # prevent division by zero
    margin = (player_roll - enemy_roll) / total
    # margin ranges roughly -1.0 to +1.0, usually -0.5 to +0.5

    # --- Step 7: Check for decision point ---
    stakes = context.get("stakes", "normal")
    decision_threshold = GAME_CONSTANTS.get("decision_point_margin", 0.08)
    is_decision_point = (abs(margin) < decision_threshold and stakes != "trivial")

    if is_decision_point:
        return CombatOutcome(
            result="standoff",
            margin=margin,
            margin_category="standoff",
            duration="prolonged",
            mood="desperate",
            companion_outcomes=companion_outcomes,
            is_decision_point=True,
            decision_prompt=(
                "The fight could go either way. What do you do?"
            ),
        )

    # --- Step 8: Determine outcome from margin ---
    if margin > 0.30:
        result, margin_cat, duration, mood = "victory", "decisive", "brief", "dominant"
    elif margin > 0.15:
        result, margin_cat, duration, mood = "victory", "comfortable", "brief", "controlled"
    elif margin > 0.03:
        result, margin_cat, duration, mood = "victory", "narrow", "prolonged", "desperate"
    elif margin > -0.03:
        result, margin_cat, duration, mood = "standoff", "standoff", "grueling", "exhausted"
    elif margin > -0.15:
        result, margin_cat, duration, mood = "defeat", "narrow_defeat", "prolonged", "desperate"
    elif margin > -0.30:
        result, margin_cat, duration, mood = "defeat", "clear_defeat", "prolonged", "overwhelmed"
    else:
        result, margin_cat, duration, mood = "defeat", "crushing_defeat", "brief", "broken"

    # --- Step 9: Roll injuries for the player ---
    player_injuries = roll_injuries(margin, player_armor)

    # --- Step 10: Apply casualties using the loss engine ---
    enemy_deaths = 0
    unit_casualties = []

    for enemy in enemies:
        if isinstance(enemy, Unit):
            is_winner = (margin < 0)  # enemy wins if margin is negative
            before = enemy.count
            report = calculate_unit_losses(enemy, margin, is_winner)
            enemy_deaths += report["total"]
            unit_casualties.append({
                "name": enemy.name, "side": "enemy",
                "before": before,
                "battle_losses": report["battle_losses"],
                "rout_losses": report["rout_losses"],
                "losses": report["total"],
                "after": enemy.count,
                "routed": report["routed"],
                "morale": report["morale_after"],
            })
        else:
            if roll_death(-margin, enemy, is_player=False):
                enemy.is_alive = False
                enemy_deaths += 1

    # Player-side unit casualties
    for unit in player_units:
        if isinstance(unit, Unit) and unit.count > 0:
            is_winner = (margin > 0)
            before = unit.count
            report = calculate_unit_losses(unit, margin, is_winner)
            unit_casualties.append({
                "name": unit.name, "side": "player",
                "before": before,
                "battle_losses": report["battle_losses"],
                "rout_losses": report["rout_losses"],
                "losses": report["total"],
                "after": unit.count,
                "routed": report["routed"],
                "morale": report["morale_after"],
            })

    # --- Step 11: Check player death ---
    player_death_result = roll_death(margin, player, is_player=True)
    if player_death_result == "near_death_choice":
        return CombatOutcome(
            result="defeat",
            margin=margin,
            margin_category=margin_cat,
            duration=duration,
            mood="broken",
            player_injuries=player_injuries,
            companion_outcomes=companion_outcomes,
            enemy_deaths=enemy_deaths,
            is_decision_point=True,
            decision_prompt=(
                "You're losing badly. Blood in your eyes. "
                "You can try to flee, surrender, or fight to the death."
            ),
        )

    # --- Step 12: Build notable moments for the narrator ---
    notable = []
    for co in companion_outcomes:
        if co["status"] == "fled":
            notable.append(f"{co['name']} fled the battle.")
        elif co["status"] == "refused":
            notable.append(f"{co['name']} refused to fight.")
        elif co["status"] == "froze":
            notable.append(f"{co['name']} froze, unable to move.")
        elif co["status"] == "fights_bravely":
            notable.append(f"{co['name']} fought bravely at your side.")
    if player_injuries:
        for inj in player_injuries:
            notable.append(f"You suffered: {inj.name}.")
    if enemy_deaths > 0:
        notable.append(f"{enemy_deaths} enem{'y' if enemy_deaths == 1 else 'ies'} killed.")

    # Add unit casualty reports to notable moments (narrator uses these for prose)
    for uc in unit_casualties:
        side_label = "Your" if uc["side"] == "player" else "Enemy"
        line = f"{side_label} {uc['name']}: {uc['battle_losses']} fell in the clash"
        if uc.get("rout_losses", 0) > 0:
            line += f", {uc['rout_losses']} more cut down in the rout"
        line += f". {uc['after']} of {uc['before']} remain."
        if uc.get("routed"):
            line += " They broke and scattered."
        notable.append(line)

    return CombatOutcome(
        result=result,
        margin=margin,
        margin_category=margin_cat,
        duration=duration,
        mood=mood,
        player_injuries=player_injuries,
        companion_outcomes=companion_outcomes,
        enemy_deaths=enemy_deaths,
        notable_moments=notable,
        unit_casualties=unit_casualties,
    )
