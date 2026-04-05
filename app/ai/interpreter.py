"""
Interpreter — turns the player's free-form text into a structured Action.

The player types whatever they want ("I walk over and say hey beautiful").
This module sends it to a fast/cheap model (Gemini Flash) which parses it
into JSON fields: type, target, manner, intent, etc.

The game engine then uses that structured Action to decide what happens.
"""
from app.data import Action
from app.ai.models import call_model


# The full system prompt for the interpreter model (from PLAN.md).
# This tells the model exactly how to parse player input into JSON.
INTERPRETER_SYSTEM_PROMPT = """You are the Action Interpreter for a text RPG. The player types free-form text.
Your ONLY job is to parse it into structured JSON.

You receive:
- The player's text input
- Current scene context (location, present NPCs, recent events)

Classify the input and output JSON:

{
    "type": "movement | dialogue | action | observation | internal | combat | trade | stealth | rest | nonsense | romance",
    "target": "entity_id or location_id or null",
    "manner": "string describing HOW they do it (tone, subtlety, emotion)",
    "intent": "string describing WHY (their apparent goal)",
    "dialogue_content": "exact words if they're speaking, else null",
    "feasible": true/false,
    "involves_combat": true/false,
    "involves_persuasion": true/false,
    "involves_deception": true/false,
    "covert": true/false
}

RULES:
- If the input contains BOTH action and speech, split them:
  "I walk over to her and say hey beautiful" →
  type: "dialogue", target: npc in context, manner: "approaching confidently",
  dialogue_content: "hey beautiful"

- If the input is incoherent garbage, return type: "nonsense"
  The game will handle it in-world (the character acts confused/drunk)

- If the input is physically impossible (eat a building, fly),
  set feasible: false. The game will let them TRY and face consequences.

- Preserve the player's STYLE. "I subtly glance at her" is not the same
  as "I look at her." The manner field carries the nuance.

- NEVER add actions the player didn't describe. If they said "I look
  around" don't add that they also drew their sword.

- If unsure whether something is dialogue or internal thought,
  default to dialogue if other people are present, internal if alone.

Output ONLY valid JSON. No explanation, no markdown, no extra text."""


def interpret(raw_input, scene_context):
    """
    Parse the player's raw text into a structured Action.

    Args:
        raw_input:      Whatever the player typed (e.g. "I sneak up and steal his purse")
        scene_context:  A string describing the current scene — location, NPCs present,
                        recent events. Helps the model figure out who "him" refers to, etc.

    Returns:
        An Action dataclass with all the parsed fields filled in.
        On failure, returns Action(type="nonsense") so the game can handle it gracefully.
    """
    # Build the user message with both the player's input and the scene context
    user_message = f"""SCENE CONTEXT:
{scene_context}

PLAYER INPUT:
{raw_input}"""

    # Call the interpreter model (Gemini Flash — fast and cheap)
    # json_mode=True means call_model will try to parse the response as JSON
    result = call_model("interpreter", INTERPRETER_SYSTEM_PROMPT, user_message, json_mode=True)

    # If the model call totally failed, result will be a fallback dict
    # Either way, try to build an Action from whatever we got
    if isinstance(result, dict):
        return Action.from_dict(result, raw=raw_input)

    # If somehow we got a non-dict back (shouldn't happen with json_mode), treat as nonsense
    return Action(type="nonsense", raw_input=raw_input)
