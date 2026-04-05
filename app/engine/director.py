"""
Director engine — daily world events, reputation spread, NPC scheduling.
The Director is an AI model (Gemini) that decides what happens in the world
each in-game day. This module handles the non-AI parts: preparing context,
applying the Director's decisions, spreading reputation, and moving NPCs.
"""
import random
import math

from app.data import World, NPC, Location
from app.config import GAME_CONSTANTS
from app.engine.npc import get_npc_schedule_location


def prepare_director_context(world, player):
    """
    Build a compressed summary of the world state for the Director AI.
    The Director needs to know what's happening to make good daily decisions,
    but we can't send the entire world — it'd be too many tokens.

    Args:
        world: World object
        player: Player object

    Returns:
        String — a compressed state summary ready to inject into a Director prompt.
    """
    lines = []

    # Basic world state
    lines.append(f"Day {world.current_day}, {world.time_slot}, {world.season}")
    lines.append(f"World: {world.name}, Era: {world.era}, Tone: {world.tone}")

    # Player location and status
    player_city = world.get_city_for_location(player.location)
    city_name = player_city.name if player_city else "unknown"
    lines.append(f"Player '{player.name}' in {city_name} (location: {player.location})")
    lines.append(f"  Health: {player.health}, Hunger: {player.hunger}, Coins: {player.coins}")
    lines.append(f"  Weapon: {player.weapon}, Armor: {player.armor}")
    lines.append(f"  Days alive: {player.days_alive}, Kills: {player.kills}")

    # Player companions
    if player.companions:
        comp_names = []
        for comp_id in player.companions:
            comp = world.npcs.get(comp_id)
            if comp:
                comp_names.append(f"{comp.name} ({comp.occupation})")
        if comp_names:
            lines.append(f"  Companions: {', '.join(comp_names)}")

    # Player reputation summary
    if player.reputation:
        rep_lines = []
        for city_id, rep_data in player.reputation.items():
            loc = world.locations.get(city_id)
            loc_name = loc.name if loc else city_id
            strength = rep_data.get("strength", 0)
            sentiment = rep_data.get("sentiment", "unknown")
            if strength > 20:  # only report meaningful reputation
                rep_lines.append(f"{loc_name}: {sentiment} ({strength})")
        if rep_lines:
            lines.append(f"  Reputation: {'; '.join(rep_lines)}")

    # Active conflicts
    if world.active_conflicts:
        lines.append("Active conflicts:")
        for conflict in world.active_conflicts[:5]:  # cap at 5
            if isinstance(conflict, dict):
                lines.append(f"  - {conflict.get('name', 'unknown')}: {conflict.get('status', '')}")
            else:
                lines.append(f"  - {conflict}")

    # Recent events (last 5)
    if world.events_log:
        lines.append("Recent events:")
        for event in world.events_log[-5:]:
            if isinstance(event, dict):
                lines.append(f"  - Day {event.get('day', '?')}: {event.get('description', '')}")
            else:
                lines.append(f"  - {event}")

    # High-fate NPCs and their locations (the Director cares about important people)
    important_npcs = [npc for npc in world.npcs.values()
                      if npc.fate > 0.4 and npc.is_alive]
    if important_npcs:
        lines.append("Key NPCs:")
        for npc in sorted(important_npcs, key=lambda n: -n.fate)[:10]:
            loc = world.locations.get(npc.location)
            loc_name = loc.name if loc else "unknown"
            met_tag = " [MET]" if npc.met_player else ""
            lines.append(f"  - {npc.name} ({npc.occupation}, fate={npc.fate:.1f}) at {loc_name}{met_tag}")

    # Faction summary
    if world.factions:
        lines.append("Factions:")
        for fac_name, fac_data in list(world.factions.items())[:8]:
            if isinstance(fac_data, dict):
                strength = fac_data.get("strength", "?")
                lines.append(f"  - {fac_name}: strength {strength}")
            else:
                lines.append(f"  - {fac_name}")

    return "\n".join(lines)


def apply_director_events(events_json, world):
    """
    Apply the Director AI's decisions to the world state.
    The Director returns a JSON list of events; we execute them here.

    Args:
        events_json: list of event dicts from the Director model. Each has:
            - "type": string (e.g., "npc_move", "conflict_update", "rumor", "weather")
            - "target": entity ID or location ID
            - "description": what happened (for the events log)
            - other type-specific keys
        world: World object to modify

    Returns:
        List of event descriptions that were applied (for logging/narration).
    """
    if not events_json:
        return []

    applied = []

    for event in events_json:
        if not isinstance(event, dict):
            continue

        event_type = event.get("type", "")
        description = event.get("description", "Something happened.")

        if event_type == "npc_move":
            # Move an NPC to a new location
            npc_id = event.get("npc_id", "")
            new_location = event.get("location", "")
            if npc_id in world.npcs and new_location:
                world.npcs[npc_id].location = new_location
                applied.append(description)

        elif event_type == "conflict_update":
            # Update an active conflict's status
            conflict_name = event.get("name", "")
            new_status = event.get("status", "")
            for conflict in world.active_conflicts:
                if isinstance(conflict, dict) and conflict.get("name") == conflict_name:
                    conflict["status"] = new_status
                    applied.append(description)
                    break

        elif event_type == "rumor":
            # Add a rumor to the events log (NPCs will reference it)
            world.events_log.append({
                "day": world.current_day,
                "type": "rumor",
                "description": description,
                "source_location": event.get("location", ""),
            })
            applied.append(description)

        elif event_type == "weather":
            # Weather doesn't change world state much, just gets logged
            world.events_log.append({
                "day": world.current_day,
                "type": "weather",
                "description": description,
            })
            applied.append(description)

        elif event_type == "npc_fate_change":
            # Director elevates or demotes an NPC's fate
            npc_id = event.get("npc_id", "")
            new_fate = event.get("fate", 0.0)
            if npc_id in world.npcs:
                world.npcs[npc_id].fate = max(0.0, min(1.0, new_fate))
                applied.append(description)

        elif event_type == "building_destroyed":
            # Mark a location as destroyed
            loc_id = event.get("location", "")
            if loc_id in world.locations:
                world.locations[loc_id].features.append("destroyed")
                applied.append(description)

        else:
            # Generic event — just log it
            world.events_log.append({
                "day": world.current_day,
                "type": event_type,
                "description": description,
            })
            applied.append(description)

    return applied


def spread_reputation(event, origin_city_id, world):
    """
    After a notable event, reputation spreads outward from the origin city.
    Farther cities hear about it later and with less strength.

    Args:
        event: dict with "type", "description", "sentiment" (feared/respected/wanted),
               and "notability" (0-100, how big a deal this is)
        origin_city_id: where the event happened
        world: World object

    Returns:
        Number of reputation events queued.
    """
    # Notability values for different event types
    NOTABILITY = {
        "killed_someone_public": 60,
        "killed_someone_private": 15,
        "won_major_fight": 50,
        "helped_someone": 20,
        "stole_something": 35,
        "joined_faction": 40,
        "betrayed_faction": 80,    # betrayal travels fast
        "public_speech": 30,
        "saved_city": 90,
    }

    event_type = event.get("type", "")
    base_notability = event.get("notability", NOTABILITY.get(event_type, 30))
    sentiment = event.get("sentiment", "respected")
    description = event.get("description", "")

    origin = world.locations.get(origin_city_id)
    if not origin:
        return 0

    origin_coords = origin.coordinates
    reputation_speed = GAME_CONSTANTS.get("reputation_spread_speed", 40)  # km/day
    queued = 0

    # Find all cities and spread reputation to them
    for loc_id, loc in world.locations.items():
        if loc.type != "city" or loc_id == origin_city_id:
            continue

        # Calculate distance between cities
        dx = origin_coords[0] - loc.coordinates[0]
        dy = origin_coords[1] - loc.coordinates[1]
        distance = math.sqrt(dx * dx + dy * dy)

        # Reputation reach depends on how notable the event was
        reach = base_notability * 10  # in km equivalent
        if distance > reach:
            continue  # too far away, they won't hear about it

        # Strength decays with distance
        strength = base_notability * (1 - distance / reach)

        # How many days until the news arrives
        days_to_arrive = distance / reputation_speed if reputation_speed > 0 else 1

        # Queue the reputation event
        world.reputation_queue.append({
            "city_id": loc_id,
            "description": description,
            "strength": round(strength, 1),
            "sentiment": sentiment,
            "arrives_day": world.current_day + round(days_to_arrive),
        })
        queued += 1

    return queued


def process_reputation_queue(world, player):
    """
    Check if any queued reputation events have arrived at their cities.
    If so, update the player's reputation there.

    Call this once per in-game day.

    Args:
        world: World object
        player: Player object
    """
    still_pending = []
    for rep_event in world.reputation_queue:
        if rep_event["arrives_day"] <= world.current_day:
            # This reputation has arrived — apply it
            city_id = rep_event["city_id"]
            if city_id not in player.reputation:
                player.reputation[city_id] = {"strength": 0, "sentiment": "unknown"}

            existing = player.reputation[city_id]
            existing["strength"] = min(100, existing.get("strength", 0) + rep_event["strength"])
            # Sentiment takes the most recent notable event
            if rep_event["strength"] > existing.get("strength", 0) * 0.5:
                existing["sentiment"] = rep_event["sentiment"]
        else:
            still_pending.append(rep_event)

    world.reputation_queue = still_pending


def decay_reputation(player):
    """
    Reputation decays 1 point per week (approximately 0.14/day) in each city.
    Major events decay slower (0.2/week).

    Call once per in-game day.
    """
    for city_id, rep_data in player.reputation.items():
        strength = rep_data.get("strength", 0)
        if strength <= 0:
            continue
        # Normal decay: 1 point per 7 days ≈ 0.143/day
        rep_data["strength"] = max(0, strength - 0.143)


def advance_npc_schedules(world):
    """
    Move all NPCs to their schedule-appropriate locations for the current time slot.
    Also processes world events that might disrupt schedules.

    Call this when the time slot changes.

    Args:
        world: World object
    """
    # Gather active world events that might affect schedules
    recent_events = []
    for event in world.events_log[-10:]:
        if isinstance(event, dict):
            recent_events.append(event)

    for npc_id, npc in world.npcs.items():
        if not npc.is_alive:
            continue
        if npc.is_companion:
            continue  # companions follow the player, not their schedule

        # Get where they should be
        target_type = get_npc_schedule_location(npc, world.time_slot, recent_events)

        # Resolve the location type to an actual location ID
        # Look for a matching location in the NPC's current city
        npc_city = world.get_city_for_location(npc.location)
        if npc_city:
            # Find a child location matching the type
            for child_id in npc_city.children_ids:
                child_loc = world.locations.get(child_id)
                if child_loc and (child_loc.type == target_type or target_type in child_loc.name.lower()):
                    npc.location = child_id
                    break
            # If no matching child found, check deeper (building rooms etc.)
            # For now, the NPC just stays where they are if we can't resolve it
