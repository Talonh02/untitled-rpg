"""
Multi-model router — sends API calls to Anthropic, Gemini, or OpenAI
depending on which role is making the call.

Every function here catches errors so the game NEVER crashes from an API failure.
"""
import json
import random
import time
import traceback

import app.config as config


# ============================================================
# MAIN ROUTER — call any model by role name
# ============================================================

def call_model(role, system_prompt, user_message, json_mode=False):
    """
    Send a message to whatever model is assigned to this role.

    Args:
        role:          Key from config.MODELS (e.g. "narrator", "interpreter")
        system_prompt: The system-level instructions for the model
        user_message:  The user-level content to send
        json_mode:     If True, parse the response as JSON and return a dict

    Returns:
        A string (or dict if json_mode=True).
        On total failure, returns a safe fallback so the game keeps running.
    """
    model_info = config.MODELS.get(role)
    if not model_info:
        print(f"[models] WARNING: Unknown role '{role}', returning fallback.")
        return _fallback(role, json_mode)

    provider = model_info["provider"]
    model_id = model_info["model"]
    max_tokens = model_info["max_tokens"]

    # Try up to 2 times (1 retry) with a short pause between
    last_error = None
    for attempt in range(2):
        try:
            if provider == "anthropic":
                text = _call_anthropic(model_id, system_prompt, user_message, max_tokens)
            elif provider == "gemini":
                text = _call_gemini(model_id, system_prompt, user_message, max_tokens)
            elif provider == "openai":
                text = _call_openai(model_id, system_prompt, user_message, max_tokens)
            else:
                print(f"[models] Unknown provider '{provider}' for role '{role}'.")
                return _fallback(role, json_mode)

            # If we want JSON, try to parse it
            if json_mode:
                return _parse_json(text, role)
            return text

        except Exception as e:
            last_error = e
            print(f"[models] Attempt {attempt + 1} failed for {role} ({provider}/{model_id}): {e}")
            if attempt == 0:
                time.sleep(1)  # brief pause before retry

    # Both attempts failed
    print(f"[models] All attempts failed for {role}. Last error: {last_error}")
    return _fallback(role, json_mode)


# ============================================================
# NPC-SPECIFIC CALLS
# ============================================================

def call_npc_model(npc, system_prompt, conversation_context):
    """
    Call the model assigned to a specific NPC based on their model_tier.

    Args:
        npc:                   An NPC dataclass instance (has .model_tier)
        system_prompt:         The NPC's character prompt (written by Character Author)
        conversation_context:  String of the recent conversation for the user message

    Returns:
        A string with the NPC's response, or a fallback if the call fails.
    """
    # Figure out which role key to use from the NPC's tier
    tier = npc.model_tier
    if not tier:
        # If no tier assigned yet, pick one now
        tier = select_npc_model(npc.depth_score, npc.fate)

    # The tier string should match a key in config.MODELS like "npc_flash_lite"
    role_key = tier if tier.startswith("npc_") else f"npc_{tier}"

    # Make sure this role exists in config
    if role_key not in config.MODELS:
        print(f"[models] NPC tier '{role_key}' not in config, defaulting to npc_flash.")
        role_key = "npc_flash"

    return call_model(role_key, system_prompt, conversation_context)


def select_npc_model(depth_score, fate):
    """
    Pick which model tier an NPC should use, with fuzzy boundaries.

    The randomness is intentional — occasionally an ordinary person surprises you
    with an unexpectedly thoughtful response, and sometimes a seemingly smart
    person is duller than expected. People aren't predictable.

    Args:
        depth_score:  Float 0-100 from Stats.depth_score()
        fate:         Float 0.0-1.0 — narrative importance

    Returns:
        A string like "npc_flash_lite", "npc_flash", "npc_sonnet", or "npc_opus"
    """
    # Fate gives a small boost, plus random fuzz for fuzzy boundaries
    effective_score = depth_score + (fate * 10) + random.uniform(-8, 8)

    if effective_score < 30:
        return "npc_flash_lite"
    elif effective_score < 52:
        return "npc_flash"
    elif effective_score < 72:
        return "npc_sonnet"
    else:
        return "npc_opus"


# ============================================================
# PROVIDER-SPECIFIC API CALLS
# ============================================================

def _call_anthropic(model_id, system_prompt, user_message, max_tokens):
    """Call the Anthropic (Claude) API and return the text response."""
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=model_id,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_message}
        ]
    )
    # The response has a list of content blocks; grab the text from the first one
    return response.content[0].text


def _call_gemini(model_id, system_prompt, user_message, max_tokens):
    """Call the Google Gemini API and return the text response."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    response = client.models.generate_content(
        model=model_id,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
        )
    )
    return response.text


def _call_openai(model_id, system_prompt, user_message, max_tokens):
    """Call the OpenAI API and return the text response."""
    import openai

    client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=model_id,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
    )
    return response.choices[0].message.content


# ============================================================
# HELPERS
# ============================================================

def _parse_json(text, role):
    """
    Try to extract valid JSON from the model's response.
    Models sometimes wrap JSON in markdown code blocks, so we handle that.
    """
    # Strip markdown code fences if present (```json ... ```)
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Remove first line (```json or ```) and last line (```)
        lines = cleaned.split("\n")
        # Drop the opening fence line
        lines = lines[1:]
        # Drop the closing fence line if it's just ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"[models] JSON parse failed for {role}: {e}")
        print(f"[models] Raw text was: {text[:200]}...")
        return _fallback(role, json_mode=True)


def _fallback(role, json_mode=False):
    """
    Return a safe fallback value when everything fails.
    The game keeps running no matter what.
    """
    if json_mode:
        # Return a minimal Action-like dict for the interpreter,
        # or a generic dict for other JSON roles
        if role == "interpreter":
            return {
                "type": "nonsense",
                "target": "",
                "manner": "",
                "intent": "failed to interpret",
                "dialogue_content": "",
                "feasible": True,
                "involves_combat": False,
                "involves_persuasion": False,
                "involves_deception": False,
                "covert": False
            }
        # Generic JSON fallback for director, antagonist, etc.
        return {"error": "model_call_failed"}

    # Narrative fallback — the world flickers but doesn't break
    return "(The world shimmers briefly, as if uncertain.)"
