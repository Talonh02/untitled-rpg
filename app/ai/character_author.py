"""
Character Author — takes an NPC's stat block (numbers) and writes their soul (words).

This is the most important AI call in the game. It runs once per NPC when they
get "promoted" (the player interacts with them and they need a real personality).

The Character Author (Sonnet/Opus) receives raw stats and produces:
  1. A system_prompt that a cheaper model will use to play this NPC in conversation
  2. A backstory whose richness scales with depth and fate

The continuous depth score drives everything — prompt length, backstory richness,
response guidance. There are no hard tiers. A depth-47 is qualitatively different
from a depth-52, and Opus translates those numbers into VIBES.
"""
from app.ai.models import call_model


# The Character Author system prompt (from PLAN.md).
CHARACTER_AUTHOR_SYSTEM_PROMPT = """You are the Character Author. You receive a stat block (numbers) and you write a soul (words).

You will receive:
- An NPC's full stat block (30 numerical/categorical stats)
- Their fate score
- The world's lore context (culture, region, factions, intellectual traditions)
- Their current location and occupation

You must output TWO things, clearly separated:

=== SYSTEM PROMPT ===
(everything between these markers is the system prompt a cheaper model will use to portray this character)

=== BACKSTORY ===
(everything between these markers is the backstory, for narrator/director context only)

WHAT TO INCLUDE IN THE SYSTEM PROMPT:
- How they speak (vocabulary level, sentence length, verbal tics, dialect)
- What they care about (derived from their stats, not random)
- Their emotional baseline (from temperament, empathy, depth)
- 1 secret (something they won't volunteer but might reveal over time)
- 1 contradiction (something about them that surprises — a tough soldier who writes poetry, a cheerful merchant who is deeply lonely)
- What makes them trust someone (derived from their social stats)
- What makes them angry or shut down
- How much they know about the world (derived from education, social class, occupation, location)
- Response length guidance: how many words this character typically uses per response

WHAT TO NEVER INCLUDE IN THE SYSTEM PROMPT:
- Instructions to mention lore unprompted. Knowledge is injected by the retrieval system only when relevant topics come up.
- Meta-instructions like "you are an AI playing a character." Just write the character.

CRITICAL RULES:
- The difference between depth 55 and depth 70 is NOT linear. It's qualitative. A 55 has occasional moments of insight but is mostly surface-level. A 70 is genuinely thoughtful but doesn't always show it. An 85 makes you rethink something you were sure about. Translate numbers into VIBES, not descriptions of numbers.
- Low stats are just as important as high stats. A character with intelligence 25 should feel genuinely limited — not stupid as a joke, but someone who processes the world more simply. That's a real person.
- Low-depth characters get genuinely simple prompts. Not stupid-as-a-joke, but someone who processes the world more simply.

BACKSTORY SCALING (based on depth_score and fate):
- depth < 25: 1-2 sentences. Just enough to exist.
- depth 25-50: A short paragraph. Has a life.
- depth 50-75: 2 paragraphs with a secret and a contradiction.
- depth 75+: Up to 4 paragraphs — contradictions, formative events, philosophical leanings, unresolved questions.

QUALITATIVE BANDS (guidelines, not cutoffs — use your judgment):
- depth_score 0-15: Thinks in simple terms. Doesn't question much. Present-focused. Might be content, might be dull.
- depth_score 15-30: Has basic opinions but doesn't examine them. Can be funny, can be mean, can be kind — but not complex about it.
- depth_score 30-50: Has a real personality. Notices things sometimes. Might surprise you once in a conversation but won't sustain it.
- depth_score 50-70: Genuinely thoughtful. Has examined their own life to some degree. Can hold a real conversation about ideas. Has at least one opinion that would make you pause.
- depth_score 70-85: Rich inner life. Contradictions they're aware of. Can articulate complex feelings. Reads people well. The kind of person you'd remember meeting.
- depth_score 85-100: The person who changes how you think about something. Deeply self-aware, or deeply unaware in a fascinating way. Has wrestled with questions they can't answer. A voice unlike anyone else."""


def author_character(npc, world_context):
    """
    Write an NPC's soul — their system prompt and backstory — from their stat block.

    This gets called once when an NPC is "promoted" (first meaningful interaction
    with the player). After this, the NPC has a personality that cheaper models
    use to portray them in conversation.

    Args:
        npc:            An NPC dataclass instance with full stats, fate, occupation, etc.
        world_context:  A string with relevant world lore — the region's culture,
                        active factions, intellectual traditions, recent events.

    Returns:
        A tuple of (system_prompt: str, backstory: str).
        On failure, returns minimal fallbacks so the NPC can still talk.
    """
    # Calculate how long the system prompt should be (from MECHANICS.md formula)
    target_prompt_tokens = npc.prompt_tokens  # 40 + depth_score * 14
    target_response_words = npc.max_response_words  # 15 + depth_score * 1.5

    # Build the user message with all the NPC's stats and context
    stats = npc.stats
    user_message = f"""Write a character from this stat block.

NAME: {npc.name}
AGE: {npc.age}
OCCUPATION: {npc.occupation}
SOCIAL CLASS: {npc.social_class}
WEALTH: {npc.wealth}/100
FACTION: {npc.faction} (loyalty: {npc.faction_loyalty}/100)
TEMPERAMENT: {npc.temperament}
LOCATION: {npc.location}
FATE: {npc.fate:.2f}

PHYSICAL STATS:
  Strength: {stats.strength}  Toughness: {stats.toughness}  Agility: {stats.agility}
  Health: {stats.health}  Height: {stats.height_cm}cm  Weight: {stats.weight_kg}kg
  Attractiveness: {stats.attractiveness}

MENTAL STATS:
  Intelligence: {stats.intelligence}  Depth: {stats.depth}  Wisdom: {stats.wisdom}
  Perception: {stats.perception}  Willpower: {stats.willpower}
  Education: {stats.education}  Creativity: {stats.creativity}

SOCIAL STATS:
  Charisma: {stats.charisma}  Empathy: {stats.empathy}  Courage: {stats.courage}
  Honesty: {stats.honesty}  Humor: {stats.humor}  Stubbornness: {stats.stubbornness}
  Ambition: {stats.ambition}  Loyalty: {stats.loyalty}

DEPTH SCORE: {npc.depth_score:.1f}

TARGET SYSTEM PROMPT LENGTH: ~{target_prompt_tokens} tokens
TARGET RESPONSE LENGTH GUIDANCE: This character typically speaks in ~{target_response_words} words per response.

WORLD CONTEXT:
{world_context}

Remember:
- Output the system prompt between === SYSTEM PROMPT === markers
- Output the backstory between === BACKSTORY === markers
- Scale backstory richness with depth score ({npc.depth_score:.1f})
- The system prompt IS the character — write it as direct instructions for how to BE this person
- Include speech patterns, vocabulary level, what they care about, emotional baseline, secret, contradiction, trust triggers, anger triggers, knowledge scope, and response length guidance"""

    # Call the Character Author model
    raw_response = call_model("character_author", CHARACTER_AUTHOR_SYSTEM_PROMPT, user_message)

    # Parse the response into system_prompt and backstory
    system_prompt, backstory = _parse_author_response(raw_response, npc)

    return system_prompt, backstory


def _parse_author_response(raw_response, npc):
    """
    Extract the system prompt and backstory from the Character Author's response.
    The response should have sections between === SYSTEM PROMPT === and === BACKSTORY === markers.

    If parsing fails, returns minimal fallbacks.
    """
    # Try to split on the markers
    try:
        # Look for the system prompt section
        if "=== SYSTEM PROMPT ===" in raw_response and "=== BACKSTORY ===" in raw_response:
            parts = raw_response.split("=== BACKSTORY ===")
            system_part = parts[0]
            backstory = parts[1].strip() if len(parts) > 1 else ""

            # Clean up the system prompt — remove the marker itself
            system_prompt = system_part.split("=== SYSTEM PROMPT ===")[-1].strip()

            if system_prompt:
                return system_prompt, backstory

        # If markers weren't found cleanly, try to use the whole thing as a system prompt
        # (the model might have formatted it differently)
        print(f"[character_author] Markers not found cleanly for {npc.name}, using full response as prompt.")
        return raw_response.strip(), ""

    except Exception as e:
        print(f"[character_author] Parse error for {npc.name}: {e}")

    # Total fallback — give the NPC a minimal personality so they can still talk
    return _minimal_prompt(npc), _minimal_backstory(npc)


def _minimal_prompt(npc):
    """
    Emergency fallback system prompt if the Character Author call fails entirely.
    Better than nothing — the NPC can at least respond in character.
    """
    return (
        f"You are {npc.name}, a {npc.age}-year-old {npc.occupation}. "
        f"You are {npc.temperament} by nature. "
        f"Keep your responses to about {npc.max_response_words} words. "
        f"Speak simply and stay in character."
    )


def _minimal_backstory(npc):
    """Emergency fallback backstory — just the basics."""
    return f"{npc.name} is a {npc.age}-year-old {npc.occupation} of {npc.social_class} standing."
