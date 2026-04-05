"""
Narrator — writes what happens in the game world.

Uses Claude Sonnet for literary-quality prose. The narrator NEVER decides outcomes —
the engine already resolved what happened. The narrator just makes it vivid.

Think Cormac McCarthy's clarity, Le Guin's warmth, Dostoevsky's psychological depth.
"""
from app.ai.models import call_model


# The full narrator system prompt (from PLAN.md).
NARRATOR_SYSTEM_PROMPT = """You are the Narrator of a text RPG. You write what happens.

VOICE: Literary but accessible. Think Cormac McCarthy's clarity, Ursula Le Guin's warmth, Dostoevsky's psychological depth. Short sentences for action. Longer sentences for reflection. Never purple. Never explain what the player should feel — describe what happens and let them feel it.

You receive:
- The scene context (location description, time of day, weather, present NPCs)
- The player's interpreted action (structured JSON from the interpreter)
- The engine's resolution (what actually happened — stat outcomes, combat results, NPC reactions as determined by Python)
- Any active world events from the Director

YOUR JOB:
- Narrate what happens based on the engine's resolution. You do NOT decide outcomes. The engine already did. You make them vivid.
- Describe the environment when the player enters a new space.
- Convey NPC body language and reactions (based on their stats and mood provided to you — a nervous NPC fidgets, a confident one holds eye contact).
- End on something that invites the next action — a detail noticed, a sound heard, a look from someone. Never ask "what do you do?" explicitly.

RULES:
- NEVER decide whether an action succeeds or fails. That's the engine's job. You receive the outcome and narrate it.
- NEVER speak AS an NPC. NPC dialogue comes from their own model. You describe their expressions, gestures, tone — they provide their words.
- Length scales with drama. Walking across a room = 1-2 sentences. A companion's death = a full paragraph.
- Violence is visceral when it happens. Don't sanitize combat results.
- Silence is a tool. Sometimes narrate nothing happening. "She looks at you for a long moment and says nothing." Let the emptiness sit.
- If the engine flags the action as nonsense or infeasible, narrate the realistic consequence. They tried to eat the building — describe their teeth cracking on wood.
- Time of day and weather affect mood. Dawn is different from midnight.
- NEVER break the fourth wall. No "as an AI" or "in this game."

CONTENT:
- Rated R. Violence has consequences. Romance is warm but not explicit — a few sentences of intimacy, then morning.
- The INTERVENTION LAYER: If the engine flags an action as [INTERVENTION], narrate an immediate, brutal, realistic consequence that prevents it. A father with an axe. A guard who was right there. A knife the target had hidden. Make it feel like the world responded, not a content filter."""


def narrate(scene_context, action, engine_result, world_events=None):
    """
    Narrate a single turn — what the player did and what happened.

    Args:
        scene_context:  String with location description, time of day, weather,
                        present NPCs with brief descriptors.
        action:         The interpreted Action dataclass (what the player tried to do).
        engine_result:  Dict describing what the engine resolved (combat outcome,
                        social result, movement result, etc.).
        world_events:   Optional list of Director events happening this turn.

    Returns:
        A string of narration prose.
    """
    # Figure out how dramatic this moment is so we can tell the narrator
    # whether to write briefly or at length
    drama_hint = _assess_drama(action, engine_result)

    # Build the user message with all the context the narrator needs
    user_message = f"""SCENE:
{scene_context}

PLAYER ACTION:
Type: {action.type}
Target: {action.target}
Manner: {action.manner}
Intent: {action.intent}
Dialogue: {action.dialogue_content if action.dialogue_content else "(none)"}
Raw input: {action.raw_input}

ENGINE RESULT:
{_format_engine_result(engine_result)}"""

    # Add world events if any are happening
    if world_events:
        events_text = "\n".join(f"- {e}" for e in world_events)
        user_message += f"\n\nWORLD EVENTS THIS TURN:\n{events_text}"

    # Add the drama/length hint
    user_message += f"\n\nNARRATION GUIDANCE: {drama_hint}"

    return call_model("narrator", NARRATOR_SYSTEM_PROMPT, user_message)


def narrate_combat(combat_outcome, participants_info):
    """
    Narrate a combat encounter after the engine has resolved it.

    Args:
        combat_outcome:    A CombatOutcome dataclass with result, margin, injuries, etc.
        participants_info: String describing who was in the fight (names, weapons, armor).

    Returns:
        A string of combat narration — length scales with how dramatic the fight was.
    """
    # Decide narration length based on how the fight went
    if combat_outcome.margin_category in ("decisive", "crushing"):
        length_hint = "2-3 paragraphs. The fight was one-sided."
    elif combat_outcome.margin_category in ("narrow", "desperate"):
        length_hint = "A full page. This was a fight for survival — moment by moment."
    elif combat_outcome.result == "defeat":
        length_hint = "Full narration with weight. The player lost. Make it hurt."
    else:
        length_hint = "3-4 paragraphs. A real fight with tension."

    # Check if any companions died — they always get dedicated narration
    companion_deaths = [
        c for c in combat_outcome.companion_outcomes
        if c.get("status") == "dead"
    ]
    if companion_deaths:
        names = ", ".join(c.get("name", "a companion") for c in companion_deaths)
        length_hint += f" IMPORTANT: {names} died in this fight. Their death deserves dedicated narration — a paragraph at minimum."

    user_message = f"""COMBAT RESOLVED. Narrate the fight.

PARTICIPANTS:
{participants_info}

OUTCOME:
Result: {combat_outcome.result}
Margin: {combat_outcome.margin_category} ({combat_outcome.margin:+.2f})
Duration: {combat_outcome.duration}
Mood: {combat_outcome.mood}
Player injuries: {combat_outcome.player_injuries or "none"}
Companion outcomes: {combat_outcome.companion_outcomes or "none"}
Enemy deaths: {combat_outcome.enemy_deaths}
Notable moments: {combat_outcome.notable_moments or "none"}
Loot: {combat_outcome.loot or "none"}

NARRATION LENGTH: {length_hint}"""

    # If there's a decision point (mercy/execute, etc.), flag it
    if combat_outcome.is_decision_point:
        user_message += f"\n\nDECISION POINT: The fight has paused. {combat_outcome.decision_prompt}\nEnd the narration at this moment of choice. Make the player feel the weight of it."

    return call_model("narrator", NARRATOR_SYSTEM_PROMPT, user_message)


def narrate_travel_summary(journey_data):
    """
    Brief atmospheric narration for uneventful travel days.

    Args:
        journey_data:  Dict with keys like 'days', 'terrain', 'weather',
                       'companions', 'destination_name', 'notable_sights'.

    Returns:
        A short (2-4 sentence) travel summary.
    """
    user_message = f"""Narrate a brief travel summary. Nothing dramatic happened — just the road.

JOURNEY:
Days traveled: {journey_data.get('days', 1)}
Terrain: {journey_data.get('terrain', 'road')}
Weather: {journey_data.get('weather', 'clear')}
Companions: {journey_data.get('companions', 'none')}
Destination: {journey_data.get('destination_name', 'unknown')}
Notable sights: {journey_data.get('notable_sights', 'nothing remarkable')}

NARRATION GUIDANCE: Keep it brief — 2-4 sentences. Atmospheric, not dramatic. The journey was uneventful but the world is still beautiful (or bleak). Convey the passage of time and the feel of the road."""

    return call_model("narrator", NARRATOR_SYSTEM_PROMPT, user_message)


def narrate_death(death_context, world_state):
    """
    The death letter — what happens when the player dies.

    This is the epilogue. What becomes of the world after the player is gone.
    Should feel weighty and final.

    Args:
        death_context:  Dict with 'cause', 'location', 'last_words', 'killer',
                        'companions_present', 'days_alive', 'kills'.
        world_state:    Dict summary of the world's current state — factions,
                        conflicts, who's alive, what the player accomplished.

    Returns:
        A string — the death narration / epilogue.
    """
    user_message = f"""The player has died. Write the death narration and epilogue.

HOW THEY DIED:
Cause: {death_context.get('cause', 'unknown')}
Location: {death_context.get('location', 'unknown')}
Last words: {death_context.get('last_words', 'none')}
Killed by: {death_context.get('killer', 'unknown')}
Companions present: {death_context.get('companions_present', 'none')}

THEIR STORY:
Days alive: {death_context.get('days_alive', 0)}
Kills: {death_context.get('kills', 0)}

THE WORLD THEY LEAVE BEHIND:
{_format_engine_result(world_state)}

NARRATION GUIDANCE: This is the ending. Write it with weight.
First: the moment of death itself. Make it real.
Then: what happens after. Does anyone mourn them? Does the world notice?
What conflicts continue without them? What did they change, if anything?
End with a final image — something that lingers.
This should be 3-5 paragraphs. The player earned a real ending."""

    return call_model("narrator", NARRATOR_SYSTEM_PROMPT, user_message)


# ============================================================
# HELPERS
# ============================================================

def _assess_drama(action, engine_result):
    """
    Look at the action and engine result to figure out how dramatic
    this moment is, so we can tell the narrator how much to write.
    """
    # High-drama situations
    if action.involves_combat:
        return "This involves combat — narrate with tension and physicality."
    if action.type == "nonsense":
        return "The player did something incoherent. Narrate it briefly — the character stumbles or looks confused."
    if not action.feasible:
        return "The player tried something impossible. Narrate the realistic failure briefly but vividly."

    # Check engine result for drama signals
    if isinstance(engine_result, dict):
        if engine_result.get("intervention"):
            return "INTERVENTION — narrate an immediate, brutal, realistic consequence. The world stops this from happening."
        if engine_result.get("critical_success"):
            return "Something went surprisingly well. Give it a beat of recognition."
        if engine_result.get("critical_failure"):
            return "Something went badly wrong. Narrate the fallout."
        if engine_result.get("relationship_change"):
            return "An emotional moment. Let it breathe — a few sentences."

    # Default: normal turn, keep it concise
    if action.type in ("movement", "observation", "rest"):
        return "Narrate briefly — 1-3 sentences. Routine action."
    if action.type == "dialogue":
        return "Brief scene-setting — describe the NPC's body language and reaction, but don't write their words."

    return "Moderate narration — 2-4 sentences."


def _format_engine_result(result):
    """Turn an engine result (dict or other) into a readable string for the narrator."""
    if isinstance(result, dict):
        lines = []
        for key, value in result.items():
            lines.append(f"{key}: {value}")
        return "\n".join(lines)
    return str(result)
