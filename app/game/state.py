"""
State management — saving, loading, context assembly, and log summarization.
This is the persistence and context layer that ties everything together.
"""
import json
import os
from typing import Optional

from app.data import (
    GameState, World, Player, NPC, Location, Road, Stats,
    Relationship, Injury, Unit, WEAPONS, ARMOR
)
from app.config import GAME_CONSTANTS


# ============================================================
# SAVE / LOAD
# ============================================================

def save_game(game_state: GameState, filepath: str):
    """
    Save the entire game state to a JSON file.
    Converts all dataclasses to dicts so JSON can handle them.
    """
    data = {
        "turn_number": game_state.turn_number,
        "action_log": game_state.action_log,
        "summary_log": game_state.summary_log,
        "flagged_moments": game_state.flagged_moments,
        "game_over": game_state.game_over,
        "death_reason": game_state.death_reason,
        "player": game_state.player.to_dict() if game_state.player else None,
        "world": _serialize_world(game_state.world),
    }
    # Make sure the save directory exists
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def load_game(filepath: str) -> GameState:
    """
    Load a saved game from a JSON file.
    Reconstructs all the dataclass objects from dicts.
    """
    with open(filepath, "r") as f:
        data = json.load(f)

    gs = GameState()
    gs.turn_number = data.get("turn_number", 0)
    gs.action_log = data.get("action_log", [])
    gs.summary_log = data.get("summary_log", [])
    gs.flagged_moments = data.get("flagged_moments", [])
    gs.game_over = data.get("game_over", False)
    gs.death_reason = data.get("death_reason", "")

    # Rebuild player
    player_data = data.get("player")
    if player_data:
        gs.player = _deserialize_player(player_data)

    # Rebuild world
    world_data = data.get("world")
    if world_data:
        gs.world = _deserialize_world(world_data)

    return gs


# ============================================================
# SERIALIZATION HELPERS
# ============================================================

def _serialize_world(world: World) -> dict:
    """Turn the World object into a plain dict for JSON."""
    return {
        "name": world.name,
        "era": world.era,
        "tone": world.tone,
        "themes": world.themes,
        # Convert Location objects to dicts
        "locations": {lid: loc.to_dict() for lid, loc in world.locations.items()},
        "roads": [r.to_dict() for r in world.roads],
        # Convert NPC objects to dicts
        "npcs": {nid: npc.to_dict() for nid, npc in world.npcs.items()},
        "factions": world.factions,
        "history": world.history,
        "intellectual_traditions": world.intellectual_traditions,
        "lore_index": world.lore_index,
        "antagonist": world.antagonist,
        "naming_conventions": world.naming_conventions,
        "religion": world.religion,
        "economy_info": world.economy_info,
        "current_day": world.current_day,
        "time_slot": world.time_slot,
        "season": world.season,
        "events_log": world.events_log,
        "reputation_queue": world.reputation_queue,
        "active_conflicts": world.active_conflicts,
        # Fix #17: serialize world.items
        "items": {iid: item.to_dict() for iid, item in world.items.items()},
        # Units (armies, merc bands, patrols)
        "units": {uid: unit.to_dict() for uid, unit in world.units.items()},
    }


def _deserialize_world(d: dict) -> World:
    """Rebuild a World from a saved dict."""
    w = World()
    w.name = d.get("name", "")
    w.era = d.get("era", "")
    w.tone = d.get("tone", "")
    w.themes = d.get("themes", [])

    # Rebuild locations
    for lid, loc_data in d.get("locations", {}).items():
        coords = loc_data.get("coordinates", [0, 0])
        w.locations[lid] = Location(
            id=loc_data["id"],
            name=loc_data["name"],
            type=loc_data["type"],
            description=loc_data.get("description", ""),
            parent_id=loc_data.get("parent_id", ""),
            children_ids=loc_data.get("children_ids", []),
            danger_rating=loc_data.get("danger_rating", 0),
            economy=loc_data.get("economy", ""),
            features=loc_data.get("features", []),
            coordinates=tuple(coords),
            terrain=loc_data.get("terrain", ""),
            mood=loc_data.get("mood", ""),
            population=loc_data.get("population", 0),
            # Fix #17: restore dungeon fields
            is_dungeon=loc_data.get("is_dungeon", False),
            locked=loc_data.get("locked", False),
            lock_difficulty=loc_data.get("lock_difficulty", 0),
            trap=loc_data.get("trap", {}),
            notable_items=loc_data.get("notable_items", []),
        )

    # Rebuild roads
    for rd in d.get("roads", []):
        w.roads.append(Road(
            from_id=rd["from"],
            to_id=rd["to"],
            distance_km=rd["distance_km"],
            terrain=rd.get("terrain", "road"),
            travel_days_foot=rd.get("travel_days_foot", 1.0),
            danger_rating=rd.get("danger_rating", 20),
        ))

    # Rebuild NPCs
    for nid, npc_data in d.get("npcs", {}).items():
        w.npcs[nid] = _deserialize_npc(npc_data)

    w.factions = d.get("factions", {})
    w.history = d.get("history", {})
    w.intellectual_traditions = d.get("intellectual_traditions", [])
    w.lore_index = d.get("lore_index", {})
    w.antagonist = d.get("antagonist", {})
    w.naming_conventions = d.get("naming_conventions", "")
    w.religion = d.get("religion", {})
    w.economy_info = d.get("economy_info", {})
    w.current_day = d.get("current_day", 1)
    w.time_slot = d.get("time_slot", "morning")
    w.season = d.get("season", "spring")
    w.events_log = d.get("events_log", [])
    w.reputation_queue = d.get("reputation_queue", [])
    w.active_conflicts = d.get("active_conflicts", [])
    # Fix #17: restore world.items
    from app.data import Item
    for iid, item_data in d.get("items", {}).items():
        w.items[iid] = Item(**{k: v for k, v in item_data.items() if k in Item.__dataclass_fields__})
    # Restore units
    for uid, unit_data in d.get("units", {}).items():
        w.units[uid] = Unit.from_dict(unit_data)
    return w


def _deserialize_npc(d: dict) -> NPC:
    """Rebuild an NPC from a saved dict."""
    # Rebuild relationship if present
    rel_data = d.get("relationship")
    rel = None
    if rel_data:
        rel = Relationship(
            trust=rel_data.get("trust", 0),
            attraction=rel_data.get("attraction", 0),
            comfort=rel_data.get("comfort", 0),
            intimacy=rel_data.get("intimacy", 0),
            persuasion_progress=rel_data.get("persuasion_progress", 0),
            interactions=rel_data.get("interactions", 0),
            flags=rel_data.get("flags", []),
            knowledge_of_player=rel_data.get("knowledge_of_player", []),
            last_summary=rel_data.get("last_summary", ""),
            # FIX 9: restore conversation history on load
            conversation_log=rel_data.get("conversation_log", []),
        )

    # Rebuild injuries
    injuries = []
    for inj in d.get("injuries", []):
        if isinstance(inj, dict):
            injuries.append(Injury(
                name=inj["name"],
                severity=inj["severity"],
                stat_effects=inj.get("stat_effects", {}),
                days_remaining=inj.get("days_remaining", 0),
                description=inj.get("description", ""),
            ))

    return NPC(
        id=d["id"],
        name=d["name"],
        age=d["age"],
        fate=d["fate"],
        stats=Stats.from_dict(d.get("stats", {})),
        occupation=d.get("occupation", ""),
        social_class=d.get("social_class", "working"),
        wealth=d.get("wealth", 30),
        faction=d.get("faction", "none"),
        faction_loyalty=d.get("faction_loyalty", 50),
        temperament=d.get("temperament", "calm"),
        weapon=d.get("weapon", "unarmed"),    # Fix #27: restore weapon
        armor=d.get("armor", "none"),          # Fix #27: restore armor
        location=d.get("location", ""),
        system_prompt=d.get("system_prompt", ""),
        backstory=d.get("backstory", ""),
        secret=d.get("secret", ""),
        relationship=rel,
        knowledge_tags=d.get("knowledge_tags", []),
        injuries=injuries,
        personal_log=d.get("personal_log", []),
        schedule_template=d.get("schedule_template", ""),  # Fix #17: restore schedule_template
        power_tier=d.get("power_tier", 1),  # Fix #17: restore power_tier
        is_companion=d.get("is_companion", False),
        is_alive=d.get("is_alive", True),
        met_player=d.get("met_player", False),
        model_tier=d.get("model_tier", ""),
    )


def _deserialize_player(d: dict) -> Player:
    """Rebuild a Player from a saved dict."""
    injuries = []
    for inj in d.get("injuries", []):
        if isinstance(inj, dict):
            injuries.append(Injury(
                name=inj["name"],
                severity=inj["severity"],
                stat_effects=inj.get("stat_effects", {}),
                days_remaining=inj.get("days_remaining", 0),
                description=inj.get("description", ""),
            ))

    return Player(
        name=d["name"],
        backstory=d.get("backstory", ""),
        stats=Stats.from_dict(d.get("stats", {})),
        location=d.get("location", ""),
        hunger=d.get("hunger", 0),
        thirst=d.get("thirst", 0),
        fatigue=d.get("fatigue", 0),
        weapon=d.get("weapon", "unarmed"),
        armor=d.get("armor", "none"),
        coins=d.get("coins", 50),
        inventory=d.get("inventory", []),
        knowledge_log=d.get("knowledge_log", []),
        companions=d.get("companions", []),
        hired_units=d.get("hired_units", []),
        injuries=injuries,
        reputation=d.get("reputation", {}),
        days_alive=d.get("days_alive", 0),
        kills=d.get("kills", 0),
    )


# ============================================================
# CONTEXT ASSEMBLY — build the text that gets sent to models
# ============================================================

def assemble_scene_context(game_state: GameState) -> str:
    """
    Build a ~300-500 token string describing the current scene.
    This gets sent to the narrator and interpreter so they know
    what's happening around the player.
    """
    world = game_state.world
    player = game_state.player
    if not player:
        return "No player in the game yet."

    parts = []

    # 1. Location info
    loc = world.locations.get(player.location)
    if loc:
        parts.append(f"Location: {loc.name} ({loc.type})")
        if loc.description:
            parts.append(loc.description)
        if loc.mood:
            parts.append(f"Mood: {loc.mood}")
        # Add parent location for context (e.g. which city this room is in)
        parent = world.get_parent_location(player.location)
        if parent:
            parts.append(f"Within: {parent.name} ({parent.type})")

    # 2. Time and weather
    parts.append(f"Time: {world.time_slot}, Day {world.current_day}, {world.season}")

    # 3. NPCs present at this location
    npcs_here = world.npcs_at_location(player.location)
    if npcs_here:
        npc_descriptions = []
        for npc in npcs_here[:10]:  # cap at 10 to keep context short
            if npc.met_player:
                # Player knows this person — use their name
                npc_descriptions.append(npc.brief_description())
            else:
                # Player hasn't met them — describe by appearance/occupation only
                age_desc = "young" if npc.age < 25 else "middle-aged" if npc.age < 50 else "older"
                build = "slight" if npc.stats.strength < 30 else "sturdy" if npc.stats.strength > 65 else ""
                npc_descriptions.append(f"a {age_desc} {build} {npc.occupation}".strip())
        parts.append(f"Present: {'; '.join(npc_descriptions)}")
    else:
        parts.append("You are alone here.")

    # 4. Player condition (brief)
    conditions = []
    if player.hunger > 60:
        conditions.append("hungry")
    if player.thirst > 60:
        conditions.append("thirsty")
    if player.fatigue > 60:
        conditions.append("exhausted")
    if player.health < 50:
        conditions.append(f"wounded (health {player.health})")
    if conditions:
        parts.append(f"Player condition: {', '.join(conditions)}")

    # 5. Recent events (last 2 from action log for continuity)
    recent = game_state.action_log[-2:] if game_state.action_log else []
    if recent:
        parts.append("Recent:")
        for entry in recent:
            # Each entry is a dict with keys like "action", "result", "narration"
            if isinstance(entry, dict):
                summary = entry.get("summary", entry.get("action", ""))
                if summary:
                    parts.append(f"  - {summary}")

    return "\n".join(parts)


def generate_world_briefing(game_state: GameState, fate_tier: str = "common") -> str:
    """
    Build a world briefing from game state. Programmatic, no model call, free.
    Everyone gets the base briefing (world state + major events + local news).
    Higher fate tiers get additional sections (politics, secrets, analysis).

    This is what makes even a common farmer able to say
    "Heard the king died. Bad business."
    """
    world = game_state.world
    player = game_state.player
    sections = []

    # === BASE BRIEFING (everyone gets this — ~150 tokens) ===

    # World + time
    world_line = f"World: {world.name or 'unnamed'}."
    if world.era:
        world_line += f" Era: {world.era}."
    world_line += f" {world.season.capitalize()}, day {world.current_day}. {world.time_slot.capitalize()}."
    sections.append(world_line)

    # Major events (from events_log — the Director generates these)
    if world.events_log:
        event_lines = []
        for evt in world.events_log[-6:]:
            if isinstance(evt, dict):
                desc = evt.get("description", str(evt))
                day = evt.get("day", "?")
                event_lines.append(f"- Day {day}: {desc}")
            else:
                event_lines.append(f"- {evt}")
        if event_lines:
            sections.append("Recent events everyone has heard about:\n" + "\n".join(event_lines))

    # Active conflicts
    if world.active_conflicts:
        conflict_lines = []
        for c in world.active_conflicts[:3]:
            if isinstance(c, dict):
                conflict_lines.append(f"- {c.get('name', 'Unknown conflict')}: {c.get('current_status', 'ongoing')}")
            else:
                conflict_lines.append(f"- {c}")
        if conflict_lines:
            sections.append("Wars and conflicts:\n" + "\n".join(conflict_lines))

    # Local news (based on player's current location)
    loc = world.locations.get(player.location) if player else None
    city = world.get_city_for_location(player.location) if player else None
    local_lines = []
    if city:
        local_lines.append(f"You are in {city.name} (population ~{city.population:,})." if city.population else f"You are in {city.name}.")
        if city.economy:
            local_lines.append(f"Local economy: {city.economy}.")
    if loc and loc != city:
        local_lines.append(f"Specifically: {loc.name} ({loc.type}).")
    if local_lines:
        sections.append("Local:\n" + "\n".join(f"- {l}" for l in local_lines))

    # World tone/themes (flavor)
    if world.themes:
        sections.append(f"The mood of the times: {', '.join(world.themes[:3])}.")

    base_briefing = "\n\n".join(sections)

    # === HIGHER TIER ADDITIONS ===
    # Tiers: common, uncommon, rare, epic, legendary, mythic
    tier_order = ["common", "uncommon", "rare", "epic", "legendary", "mythic"]
    tier_idx = tier_order.index(fate_tier) if fate_tier in tier_order else 0

    extras = []

    # Uncommon+ : faction standings
    if tier_idx >= 1 and world.factions:
        faction_lines = []
        for fname, fdata in list(world.factions.items())[:5]:
            if isinstance(fdata, dict):
                goals = fdata.get("goals", [])
                strength = fdata.get("strength", "?")
                faction_lines.append(f"- {fname}: strength {strength}. {goals[0] if goals else ''}")
            else:
                faction_lines.append(f"- {fname}: {fdata}")
        if faction_lines:
            extras.append("Factions you've heard of:\n" + "\n".join(faction_lines))

    # Rare+: economy, religion, intellectual climate
    if tier_idx >= 2:
        if world.economy_info:
            extras.append(f"Economy: {str(world.economy_info)[:200]}")
        if world.religion:
            rel_summary = world.religion.get("name", str(world.religion)[:100])
            extras.append(f"Religion: {rel_summary}")
        if world.intellectual_traditions:
            names = []
            for t in world.intellectual_traditions[:3]:
                names.append(t.get("name", str(t)) if isinstance(t, dict) else str(t))
            extras.append(f"Intellectual traditions: {', '.join(names)}")

    # Epic+: player reputation
    if tier_idx >= 3 and player and player.reputation:
        rep_lines = []
        for region, rep_data in list(player.reputation.items())[:3]:
            if isinstance(rep_data, dict):
                rep_lines.append(f"- In {region}: {rep_data.get('sentiment', 'unknown')}")
            else:
                rep_lines.append(f"- {region}: {rep_data}")
        if rep_lines:
            extras.append("What people say about the player:\n" + "\n".join(rep_lines))
        if player.kills > 0:
            extras.append(f"The player has killed {player.kills} {'person' if player.kills == 1 else 'people'}.")

    # Legendary+: key NPCs and their movements
    if tier_idx >= 4:
        important = [n for n in world.npcs.values() if n.fate > 0.5 and n.is_alive]
        if important:
            npc_lines = []
            for n in sorted(important, key=lambda x: -x.fate)[:5]:
                nloc = world.locations.get(n.location)
                loc_name = nloc.name if nloc else "unknown"
                npc_lines.append(f"- {n.name} ({n.occupation}, fate {n.fate:.1f}) at {loc_name}")
            extras.append("Key figures:\n" + "\n".join(npc_lines))

    # Mythic: antagonist, secrets, hidden truths
    if tier_idx >= 5:
        if world.antagonist:
            ant = world.antagonist
            extras.append(f"The great threat: {ant.get('name', 'Unknown')} — {ant.get('current_status', 'active')}.")
        if world.lore_index:
            secret_keys = list(world.lore_index.keys())[:3]
            secrets = [world.lore_index[k] for k in secret_keys]
            if secrets:
                extras.append("Things few know:\n" + "\n".join(f"- {s}" for s in secrets))

    if extras:
        return base_briefing + "\n\n" + "\n\n".join(extras)
    return base_briefing


def assemble_npc_context(npc: NPC, game_state: GameState) -> str:
    """
    Build the full context for an NPC model call.
    Includes: system prompt + world briefing (scaled by fate tier) +
    relationship data + lore + injuries.
    """
    parts = []

    # 1. The NPC's system prompt (personality) + universal speech rules
    if npc.system_prompt:
        parts.append(npc.system_prompt)
    parts.append(
        "[RULES: Speak directly as yourself in first person. Just talk — no narrating "
        "your own actions, gestures, or expressions in italics or asterisks. "
        "No *I lean back* or *she pauses*. Only your words.]"
    )

    # 2. World briefing — everyone gets the base, higher tiers get more
    fate = npc.fate
    if fate >= 0.85:
        tier = "mythic"
    elif fate >= 0.70:
        tier = "legendary"
    elif fate >= 0.50:
        tier = "epic"
    elif fate >= 0.30:
        tier = "rare"
    elif fate >= 0.15:
        tier = "uncommon"
    else:
        tier = "common"
    briefing = generate_world_briefing(game_state, tier)
    parts.append(f"\n[WORLD STATE — what you know about the world:]\n{briefing}")

    # Build tier index for conditional sections below (0=common, 5=mythic)
    tier_order = ["common", "uncommon", "rare", "epic", "legendary", "mythic"]
    tier_idx = tier_order.index(tier) if tier in tier_order else 0

    # 3. Relationship with player (if any)
    if npc.relationship:
        rel = npc.relationship
        parts.append(f"\n[Relationship with player: {rel.stage}, "
                     f"trust={rel.trust:.0f}, comfort={rel.comfort:.0f}, "
                     f"interactions={rel.interactions}]")
        if rel.knowledge_of_player:
            parts.append(f"[You know about the player: {', '.join(rel.knowledge_of_player[-5:])}]")
        if rel.last_summary:
            # Calculate how long ago the last interaction was
            time_ago = ""
            last_day_flags = [f for f in rel.flags if f.startswith("last_day:")]
            if last_day_flags:
                try:
                    last_day = int(last_day_flags[-1].split(":")[1])
                    days_since = game_state.world.current_day - last_day
                    if days_since == 0:
                        time_ago = "earlier today"
                    elif days_since == 1:
                        time_ago = "yesterday"
                    elif days_since < 7:
                        time_ago = f"{days_since} days ago"
                    elif days_since < 30:
                        weeks = days_since // 7
                        time_ago = f"about {weeks} week{'s' if weeks > 1 else ''} ago"
                    elif days_since < 90:
                        months = days_since // 30
                        time_ago = f"about {months} month{'s' if months > 1 else ''} ago"
                    else:
                        months = days_since // 30
                        time_ago = f"{months} months ago — a long time"
                except (ValueError, IndexError):
                    pass
            time_str = f" ({time_ago})" if time_ago else ""
            parts.append(f"[Last interaction{time_str}: {rel.last_summary}]")

        # FIX 9: inject full conversation history for rare+ NPCs (tier_idx >= 2)
        if hasattr(rel, 'conversation_log') and rel.conversation_log and tier_idx >= 2:
            parts.append("[Previous conversations:\n" +
                         "\n".join(f"  {entry}" for entry in rel.conversation_log[-10:]) + "]")

    # 4. Current situation
    world = game_state.world
    loc = world.locations.get(npc.location)
    if loc:
        parts.append(f"\n[You are in {loc.name}. It is {world.time_slot}, {world.season}.]")

    # 5. Lore snippets matching this NPC's knowledge tags (on top of world briefing)
    if npc.knowledge_tags and world.lore_index:
        relevant_lore = []
        for tag in npc.knowledge_tags:
            if tag in world.lore_index:
                relevant_lore.append(world.lore_index[tag])
        if relevant_lore:
            parts.append(f"\n[Specialist knowledge: {' '.join(relevant_lore[:3])}]")

    # 6. Personal log — what's happened in their life recently
    if hasattr(npc, 'personal_log') and npc.personal_log:
        # Scale how much personal history they share by tier
        if tier_idx >= 4:  # legendary+: full log
            log_entries = npc.personal_log[-10:]
        elif tier_idx >= 2:  # rare+: recent entries
            log_entries = npc.personal_log[-5:]
        else:  # uncommon: just the highlights
            log_entries = npc.personal_log[-3:]
        if log_entries:
            parts.append("\n[What's been happening in your life recently:]\n" +
                         "\n".join(f"  {entry}" for entry in log_entries))

    # 7. Mood/injuries affecting behavior
    if npc.injuries:
        injury_names = [i.name if isinstance(i, Injury) else str(i) for i in npc.injuries]
        parts.append(f"[You are currently injured: {', '.join(injury_names)}]")

    return "\n".join(parts)


def assemble_world_summary(game_state: GameState) -> str:
    """
    Build a compressed world state summary for the Director.
    Covers player location, faction standings, high-fate NPCs, recent events.
    """
    world = game_state.world
    player = game_state.player
    parts = []

    # 1. Player state
    if player:
        loc = world.locations.get(player.location)
        loc_name = loc.name if loc else player.location
        parts.append(f"Player: {player.name} at {loc_name}, "
                     f"health={player.health}, day {world.current_day}")
        if player.companions:
            parts.append(f"Companions: {', '.join(player.companions)}")

    # 2. Faction standings
    if world.factions:
        faction_lines = []
        for fname, fdata in world.factions.items():
            if isinstance(fdata, dict):
                strength = fdata.get("strength", "?")
                goals = fdata.get("goals", [])
                goal_str = goals[0] if goals else "unknown"
                faction_lines.append(f"  {fname}: strength={strength}, goal={goal_str}")
            else:
                faction_lines.append(f"  {fname}: {fdata}")
        if faction_lines:
            parts.append("Factions:\n" + "\n".join(faction_lines))

    # 3. High-fate NPC locations (only fate > 0.4 — the Director doesn't track nobodies)
    important_npcs = [npc for npc in world.npcs.values()
                      if npc.fate > 0.4 and npc.is_alive]
    if important_npcs:
        npc_lines = []
        for npc in sorted(important_npcs, key=lambda n: -n.fate)[:15]:
            loc = world.locations.get(npc.location)
            loc_name = loc.name if loc else npc.location
            npc_lines.append(f"  {npc.name} (fate={npc.fate:.1f}) at {loc_name}")
        parts.append("Key NPCs:\n" + "\n".join(npc_lines))

    # 4. Active conflicts
    if world.active_conflicts:
        parts.append("Active conflicts:")
        for conflict in world.active_conflicts[:5]:
            if isinstance(conflict, dict):
                parts.append(f"  - {conflict.get('name', 'Unknown')}: "
                             f"{conflict.get('current_status', 'ongoing')}")
            else:
                parts.append(f"  - {conflict}")

    # 5. Recent events
    recent_events = world.events_log[-5:] if world.events_log else []
    if recent_events:
        parts.append("Recent events:")
        for evt in recent_events:
            if isinstance(evt, dict):
                parts.append(f"  - Day {evt.get('day', '?')}: {evt.get('description', str(evt))}")
            else:
                parts.append(f"  - {evt}")

    # 6. Antagonist status
    if world.antagonist:
        ant = world.antagonist
        parts.append(f"Antagonist: {ant.get('name', 'Unknown')} — "
                     f"{ant.get('current_status', 'active')}")

    # 7. Time/season
    parts.append(f"World: day {world.current_day}, {world.time_slot}, {world.season}")

    return "\n".join(parts)


# ============================================================
# ACTION LOG + SUMMARIZER
# ============================================================

def log_action(game_state: GameState, turn_number: int, action: str,
               result: str, narration: str):
    """
    Add an entry to the action log. Each entry records what happened on a turn.
    """
    entry = {
        "turn": turn_number,
        "action": action,
        "result": result,
        "narration": narration,
        # Build a short summary for context injection
        "summary": f"Turn {turn_number}: {action[:80]}",
    }
    game_state.action_log.append(entry)


def flag_moment(game_state: GameState, description: str, moment_type: str):
    """
    Flag an important moment that should NEVER be compressed away.
    These are the beats that make the story memorable.

    moment_type: "first_kill", "companion_joined", "betrayal", "romance",
                 "discovery", "death_nearby", "major_choice", etc.
    """
    moment = {
        "turn": game_state.turn_number,
        "day": game_state.world.current_day,
        "description": description,
        "type": moment_type,
    }
    game_state.flagged_moments.append(moment)


def run_summarizer(game_state: GameState):
    """
    Compress old action log entries to keep context manageable.
    Runs every N turns (set in GAME_CONSTANTS).

    Strategy:
    1. Try to call a cheap model to summarize old entries.
    2. If that fails, fall back to mechanical compression (just extract key facts).
    3. Flagged moments are NEVER compressed — they stay verbatim forever.
    """
    summarize_every = GAME_CONSTANTS.get("summarize_every_n_turns", 10)

    # Only summarize if we have enough entries
    if len(game_state.action_log) < summarize_every:
        return

    # Grab the oldest entries (keep the most recent ones for immediate context)
    keep_recent = 5  # always keep the last 5 entries verbatim
    old_entries = game_state.action_log[:-keep_recent]
    recent_entries = game_state.action_log[-keep_recent:]

    if not old_entries:
        return

    # Try model-based summarization first
    summary_text = _try_model_summary(old_entries)

    # If model call failed, do mechanical compression
    if not summary_text:
        summary_text = _mechanical_summary(old_entries)

    # Save the summary and trim the action log
    game_state.summary_log.append({
        "turns": f"{old_entries[0].get('turn', '?')}-{old_entries[-1].get('turn', '?')}",
        "summary": summary_text,
    })
    game_state.action_log = recent_entries


def _try_model_summary(entries: list) -> str:
    """
    Try to use a cheap model (summarizer tier) to compress action log entries.
    Returns empty string if the model call fails.
    """
    try:
        # Import here to avoid circular imports — AI module may not be ready yet
        from app.ai.models import call_model

        # Build the text to summarize
        text_parts = []
        for entry in entries:
            if isinstance(entry, dict):
                text_parts.append(f"Turn {entry.get('turn', '?')}: "
                                  f"{entry.get('action', '')} → {entry.get('result', '')}")
            else:
                text_parts.append(str(entry))

        prompt = (
            "Summarize these RPG game turns into 2-3 concise sentences. "
            "Focus on key events, decisions, and consequences. "
            "Preserve names, locations, and important details.\n\n"
            + "\n".join(text_parts)
        )

        # Fix #18: call_model needs 3 args (role, system_prompt, user_message)
        result = call_model("summarizer", "You summarize game events concisely.", prompt)
        if result and isinstance(result, str):
            return result.strip()
    except Exception:
        # Model not available or call failed — that's fine, we have a fallback
        pass
    return ""


def _mechanical_summary(entries: list) -> str:
    """
    Fallback summarizer that doesn't need a model.
    Just extracts key facts from entries mechanically.
    """
    facts = []
    for entry in entries:
        if isinstance(entry, dict):
            action = entry.get("action", "")
            result = entry.get("result", "")
            turn = entry.get("turn", "?")
            # Keep it short — just the action and outcome
            if action:
                line = f"T{turn}: {action[:60]}"
                if result:
                    line += f" → {result[:40]}"
                facts.append(line)

    if facts:
        return "Summary of earlier turns: " + " | ".join(facts)
    return "Earlier turns occurred but details were lost."
