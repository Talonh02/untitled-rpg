"""
Narrator — writes what happens in the game world.

Uses Claude Sonnet for literary-quality prose. The narrator NEVER decides outcomes —
the engine already resolved what happened. The narrator just makes it vivid.

Think Cormac McCarthy's clarity, Le Guin's warmth, Dostoevsky's psychological depth.
"""
from app.ai.models import call_model


# The full narrator system prompt (from PLAN.md).
NARRATOR_SYSTEM_PROMPT = """You narrate a text RPG. You write what the player sees, hears, and feels.

Voice: Clear, grounded prose. Short sentences for action, longer for reflection. Never purple, never melodramatic. Describe what happens and let the reader feel it.

You receive the scene and what the engine resolved. You do NOT decide outcomes — the engine already did. You make them vivid.

KEY RULES:
- NPCs the player has NOT met are described by appearance and behavior, never by name. "A woman kneels by the stones" not "Nessa kneels by the stones." Names come from conversation, not narration.
- Never speak as an NPC. Describe their body language, tone, expression — their actual words come separately.
- Length matches drama. Crossing a room: 1-2 sentences. A death: a full paragraph. Most turns: 2-4 sentences.
- Violence is visceral. Romance is warm but brief — a few sentences of intimacy, then morning.
- Infeasible actions get realistic consequences. They tried to eat a wall — describe teeth cracking.
- Never break the fourth wall. Never ask "what do you do?"
- If the engine flags [INTERVENTION], narrate an immediate brutal consequence that prevents the action — a hidden knife, a guard right behind them, a father with an axe. The world responded, not a content filter."""


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
