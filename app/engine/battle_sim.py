"""
Battle Simulator — round-by-round combat instead of auto-resolve.
Produces a sequence of rounds the frontend plays back with delays (~500ms each).

Each round: every combatant attacks, HP ticks down, casualties happen.
Dragon HP: 100 * 25 (tier mult) = 2500. Takes hundreds of arrows to drop.
Soldiers: each ~80 effective HP. Die individually as damage accumulates.

Player can choose before battle:
- fight (engage personally) or watch (safe, no contribution)
- hold companions back (safe for next battle)
"""
import random
import math

from app.data import (
    Stats, NPC, Player, Unit,
    WEAPONS, ARMOR, ENTITY_TIER_MULTIPLIERS
)

# Convert weapon speed strings to attack-rate multipliers
SPEED_MULT = {"fast": 1.3, "medium": 1.0, "slow": 0.7, "ranged": 1.0}

# Effective HP per soldier in a unit (for converting damage → casualties)
SOLDIER_HP = 80


def simulate_battle(player, enemies, companions=None, player_units=None, options=None):
    """
    Run the full battle simulation.

    options:
        player_fights: bool — True = player engages, False = watches
        hold_companions: list of NPC ids to keep out of combat

    Returns dict with rounds list, outcome, and summary.
    """
    sim = BattleSim(player, enemies, companions or [], player_units or [], options or {})
    return sim.run()


class BattleSim:
    def __init__(self, player, enemies, companions, player_units, options):
        self.options = options
        self.rounds = []
        self.round_num = 0

        # --- Build combatant tracking lists ---
        self.player_side = []
        self.enemy_side = []

        # Player
        p_tier = getattr(player, "power_tier", 1)
        p_hp = player.health * ENTITY_TIER_MULTIPLIERS.get(p_tier, 1.0)
        self.player_side.append(self._make_individual(
            player, "player", p_hp,
            active=options.get("player_fights", True)
        ))

        # Companions
        held = options.get("hold_companions", [])
        for comp in companions:
            c_tier = getattr(comp, "power_tier", 1)
            c_hp = comp.stats.health * ENTITY_TIER_MULTIPLIERS.get(c_tier, 1.0)
            self.player_side.append(self._make_individual(
                comp, "companion", c_hp,
                active=(comp.id not in held)
            ))

        # Player units
        for unit in player_units:
            self.player_side.append(self._make_unit(unit))

        # Enemies
        for e in enemies:
            if isinstance(e, Unit):
                self.enemy_side.append(self._make_unit(e))
            else:
                e_tier = getattr(e, "power_tier", 1)
                e_hp = e.stats.health * ENTITY_TIER_MULTIPLIERS.get(e_tier, 1.0)
                self.enemy_side.append(self._make_individual(e, "npc", e_hp))

    def _make_individual(self, entity, ctype, hp, active=True):
        stats = entity.get_effective_stats() if hasattr(entity, "get_effective_stats") else entity.stats
        return {
            "name": entity.name, "type": ctype, "entity": entity,
            "hp": hp, "max_hp": hp,
            "weapon": getattr(entity, "weapon", "unarmed"),
            "armor": getattr(entity, "armor", "none"),
            "str": stats.strength, "agi": stats.agility,
            "tgh": stats.toughness, "per": stats.perception,
            "power_tier": getattr(entity, "power_tier", 1),
            "active": active, "alive": True,
        }

    def _make_unit(self, unit):
        return {
            "name": unit.name, "type": "unit", "entity": unit,
            "count": unit.count, "start_count": unit.count,
            "weapon": unit.weapon, "armor": unit.armor,
            "str": unit.stats.strength, "agi": unit.stats.agility,
            "tgh": unit.stats.toughness, "per": unit.stats.perception,
            "morale": unit.morale, "power_tier": unit.power_tier,
            "active": True, "alive": True,
        }

    # ================================================================
    # MAIN LOOP
    # ================================================================

    def run(self, max_rounds=20):
        for _ in range(max_rounds):
            if self._battle_over():
                break
            self.round_num += 1
            rnd = self._simulate_round()
            self.rounds.append(rnd)

        outcome = self._determine_outcome()
        summary = self._build_summary(outcome)
        self._apply_results()

        return {
            "rounds": self.rounds,
            "outcome": outcome,
            "summary": summary,
            "total_rounds": self.round_num,
        }

    # ================================================================
    # ONE ROUND
    # ================================================================

    def _simulate_round(self):
        events = []

        # Player side attacks enemy side
        for c in self.player_side:
            if not c["alive"] or not c["active"]:
                continue
            # FIX 3: high power-tier entities (dragons, giants) hit ALL enemies
            if c.get("power_tier", 1) >= 3:
                for target in [t for t in self.enemy_side if t["alive"]]:
                    evt = self._resolve_attack(c, target)
                    if evt:
                        events.append(evt)
            else:
                target = self._pick_target(self.enemy_side)
                if target:
                    evt = self._resolve_attack(c, target)
                    if evt:
                        events.append(evt)

        # Enemy side attacks player side
        for c in self.enemy_side:
            if not c["alive"]:
                continue
            # FIX 3: high power-tier entities hit ALL player-side combatants
            if c.get("power_tier", 1) >= 3:
                for target in [t for t in self.player_side if t["alive"]]:
                    evt = self._resolve_attack(c, target)
                    if evt:
                        events.append(evt)
            else:
                # Normal enemies prefer to target active combatants
                target = self._pick_target(self.player_side, prefer_active=True)
                if target:
                    evt = self._resolve_attack(c, target)
                    if evt:
                        events.append(evt)

        # Morale breaks
        for c in self.player_side + self.enemy_side:
            if c["type"] == "unit" and c["alive"] and c.get("morale", 50) < 15:
                c["alive"] = False
                events.append({"text": f"{c['name']} broke and fled!", "type": "rout"})

        return {
            "round": self.round_num,
            "events": events,
            "player_side": [self._snapshot(c) for c in self.player_side],
            "enemy_side": [self._snapshot(c) for c in self.enemy_side],
        }

    # ================================================================
    # ATTACK RESOLUTION
    # ================================================================

    def _resolve_attack(self, attacker, defender):
        if attacker["type"] == "unit":
            return self._unit_attacks(attacker, defender)
        return self._individual_attacks(attacker, defender)

    def _individual_attacks(self, atk, dfn):
        """One individual attacks — player, NPC, dragon, etc."""
        weapon = WEAPONS.get(atk["weapon"], WEAPONS["unarmed"])
        speed = SPEED_MULT.get(weapon["speed"], 1.0)

        # Number of swings this round (fast weapons get more)
        num_attacks = max(1, int(speed + random.uniform(-0.2, 0.2)))
        # FIX 3: high-tier entities (dragons, giants) get bonus attacks
        if atk.get("power_tier", 1) >= 3:
            num_attacks += atk["power_tier"]  # dragon (tier 4) gets 5+ attacks per round

        total_damage = 0
        hits = 0

        for _ in range(num_attacks):
            # Hit chance: 50% base, ±agility difference, armor reduces it
            # FIX 4: armor penalty in individual attacks (0.008 per defense point)
            dfn_agi = dfn.get("agi", 42)
            armor_def = ARMOR.get(dfn.get("armor", "none"), ARMOR["none"])["defense"]
            hit_chance = 0.50 + (atk["agi"] - dfn_agi) * 0.005 - armor_def * 0.008
            hit_chance = max(0.15, min(0.90, hit_chance))

            if random.random() < hit_chance:
                hits += 1
                # Damage = strength + weapon power, scaled by power tier
                raw = (atk["str"] * 0.3 + weapon["multiplier"] * 8)
                raw *= ENTITY_TIER_MULTIPLIERS.get(atk["power_tier"], 1.0)
                raw *= random.uniform(0.6, 1.4)

                # Armor absorbs some
                armor_def = ARMOR.get(dfn.get("armor", "none"), ARMOR["none"])["defense"]
                absorbed = armor_def * random.uniform(0.3, 0.8)
                actual = max(1, raw - absorbed)
                total_damage += actual

        if hits == 0:
            return {"text": f"{atk['name']} swings and misses", "type": "miss"}

        # Apply damage to target
        return self._apply_damage(atk, dfn, hits, total_damage)

    def _unit_attacks(self, unit, target):
        """A unit attacks — many soldiers, many small hits."""
        count = unit.get("count", 0)
        if count <= 0:
            return None

        weapon = WEAPONS.get(unit["weapon"], WEAPONS["unarmed"])

        # How many soldiers attack this round (~30% of unit, with variance)
        attack_count = max(1, int(count * 0.3 * random.uniform(0.6, 1.4)))

        # Hit chance: perception helps, enemy armor hurts
        # FIX 4: stronger armor penalty (0.012 instead of 0.005) — plate drops hit% by 36%
        armor_def = ARMOR.get(target.get("armor", "none"), ARMOR["none"])["defense"]
        hit_chance = 0.35 + unit["per"] * 0.003 - armor_def * 0.012
        hit_chance = max(0.10, min(0.70, hit_chance))

        hits = sum(1 for _ in range(attack_count) if random.random() < hit_chance)

        if hits == 0:
            return {"text": f"{unit['name']} attack but miss", "type": "miss"}

        # Damage per hit
        dmg_per = (unit["str"] * 0.2 + weapon["multiplier"] * 5) * random.uniform(0.7, 1.3)
        total_damage = hits * dmg_per

        return self._apply_damage(unit, target, hits, total_damage)

    def _apply_damage(self, atk, dfn, hits, total_damage):
        """Apply damage to a target and return the event description."""
        total_damage = max(1, total_damage)

        if dfn["type"] == "unit":
            # Convert damage to casualties
            casualties = max(1, int(total_damage / SOLDIER_HP))
            dfn["count"] = max(0, dfn.get("count", 0) - casualties)
            dfn["morale"] = max(0, dfn.get("morale", 50) - int(casualties * 0.5))
            if dfn["count"] <= 0:
                dfn["alive"] = False

            return {
                "text": f"{atk['name']} — {hits} hits, {casualties} of {dfn['name']} fall",
                "type": "attack", "damage": int(total_damage), "casualties": casualties,
            }
        else:
            dfn["hp"] = max(0, dfn.get("hp", 100) - total_damage)
            if dfn["hp"] <= 0:
                dfn["alive"] = False

            # Pick a good verb
            weapon = WEAPONS.get(atk.get("weapon", "unarmed"), WEAPONS["unarmed"])
            if weapon["speed"] == "ranged":
                verb = "arrows strike"
            elif atk["type"] == "unit":
                verb = "blows land on"
            else:
                verb = "hits"

            dead_text = " — a killing blow!" if not dfn["alive"] else ""
            return {
                "text": f"{atk['name']} {verb} {dfn['name']} for {int(total_damage)}{dead_text}",
                "type": "attack", "damage": int(total_damage),
            }

    # ================================================================
    # HELPERS
    # ================================================================

    def _pick_target(self, side, prefer_active=False):
        alive = [c for c in side if c["alive"]]
        if prefer_active:
            active = [c for c in alive if c.get("active", True)]
            if active:
                alive = active
        if not alive:
            return None
        # Weighted: units are bigger targets (more likely to be hit)
        weights = []
        for c in alive:
            if c["type"] == "unit":
                weights.append(max(1, c.get("count", 1)))
            else:
                weights.append(10)  # individuals are smaller targets
        total = sum(weights)
        r = random.uniform(0, total)
        cumulative = 0
        for c, w in zip(alive, weights):
            cumulative += w
            if r <= cumulative:
                return c
        return alive[-1]

    def _battle_over(self):
        p_alive = any(c["alive"] for c in self.player_side if c["active"])
        e_alive = any(c["alive"] for c in self.enemy_side)
        return not p_alive or not e_alive

    def _determine_outcome(self):
        e_alive = any(c["alive"] for c in self.enemy_side)
        p_alive = any(c["alive"] for c in self.player_side if c["active"])
        if not e_alive:
            return "victory"
        if not p_alive:
            return "defeat"
        return "stalemate"

    def _snapshot(self, c):
        if c["type"] == "unit":
            return {
                "name": c["name"], "type": "unit",
                "count": c.get("count", 0), "start_count": c.get("start_count", 0),
                "morale": c.get("morale", 50), "alive": c["alive"],
            }
        return {
            "name": c["name"], "type": c["type"],
            "hp": max(0, int(c.get("hp", 0))), "max_hp": int(c.get("max_hp", 100)),
            "alive": c["alive"], "active": c.get("active", True),
        }

    def _build_summary(self, outcome):
        parts = []
        for c in self.player_side:
            if c["type"] == "unit":
                lost = c["start_count"] - c.get("count", 0)
                if lost > 0:
                    parts.append(f"{c['name']}: {lost} of {c['start_count']} fell")
            elif c["type"] == "player":
                hp_lost = int(c["max_hp"] - max(0, c.get("hp", 0)))
                if hp_lost > 0:
                    parts.append(f"You took {hp_lost} damage")
        for c in self.enemy_side:
            if c["type"] == "unit":
                lost = c["start_count"] - c.get("count", 0)
                parts.append(f"Enemy {c['name']}: {lost} of {c['start_count']} killed")
            elif not c["alive"]:
                parts.append(f"{c['name']} was slain")
            else:
                hp_lost = int(c["max_hp"] - max(0, c.get("hp", 0)))
                if hp_lost > 0:
                    parts.append(f"{c['name']} took {hp_lost} damage")
        return f"{outcome.capitalize()} after {self.round_num} rounds. " + ". ".join(parts) + "."

    def _apply_results(self):
        """Write battle results back to the actual game entities."""
        for c in self.player_side:
            ent = c["entity"]
            if c["type"] in ("player", "companion"):
                tier = ENTITY_TIER_MULTIPLIERS.get(c["power_tier"], 1.0)
                ent.stats.health = max(0, int(c.get("hp", 0) / tier))
            elif c["type"] == "unit":
                ent.count = c.get("count", 0)
                ent.morale = c.get("morale", 0)

        for c in self.enemy_side:
            ent = c["entity"]
            if c["type"] == "unit":
                ent.count = c.get("count", 0)
                ent.morale = c.get("morale", 0)
            else:
                tier = ENTITY_TIER_MULTIPLIERS.get(c["power_tier"], 1.0)
                ent.stats.health = max(0, int(c.get("hp", 0) / tier))
                if not c["alive"]:
                    ent.is_alive = False
