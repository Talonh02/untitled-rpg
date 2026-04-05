"""
Perception engine — observation, lie detection, eavesdropping.
Determines what the player notices based on their perception stat.
Higher perception reveals more details, catches more lies, hears more clearly.
"""
import random

from app.data import Player, NPC


def observe_scene(player_perception, scene_details):
    """
    Filter a scene's details based on the player's perception stat.
    Each detail has a min_perception requirement — the player only
    notices things they're perceptive enough to catch.

    Args:
        player_perception: int 0-100
        scene_details: list of dicts, each with:
            - "description": string (what the player sees)
            - "min_perception": int 0-100 (how perceptive you need to be)

    Returns:
        List of description strings the player can see, sorted from
        easiest to hardest to notice.
    """
    if not scene_details:
        return []

    visible = []
    for detail in scene_details:
        min_req = detail.get("min_perception", 0)
        description = detail.get("description", "")

        # Add a little randomness — sometimes you notice something
        # you normally wouldn't, or miss something obvious
        effective_perception = player_perception + random.uniform(-5, 5)

        if effective_perception >= min_req:
            visible.append(description)

    return visible


def detect_lie(player, npc, lie_severity=50):
    """
    Can the player tell that an NPC is lying?
    Uses a combination of perception, wisdom, and empathy vs
    the NPC's charisma, dishonesty, and willpower.

    Bigger lies are harder for the NPC to sell convincingly.
    High trust makes the player less suspicious (they want to believe).

    Args:
        player: Player object
        npc: NPC object
        lie_severity: 0-100, how big is the lie? 0 = white lie, 100 = outrageous

    Returns:
        "caught" — player sees through it
        "suspicious" — player senses something off but isn't sure
        "believed" — player doesn't notice the lie
    """
    # Player's ability to read people
    stats = player.get_effective_stats() if hasattr(player, "get_effective_stats") else player.stats
    player_read = (
        stats.perception * 0.5 +
        stats.wisdom * 0.3 +
        stats.empathy * 0.2
    )

    # NPC's ability to deceive
    npc_stats = npc.get_effective_stats() if hasattr(npc, "get_effective_stats") else npc.stats
    npc_deception = (
        npc_stats.charisma * 0.4 +
        (100 - npc_stats.honesty) * 0.3 +   # dishonest people lie better
        npc_stats.willpower * 0.3
    )

    # Bigger lies are harder to sell
    npc_deception -= lie_severity * 0.2

    # Trust makes you less suspicious — you want to believe them
    if npc.relationship and npc.relationship.trust > 50:
        player_read *= 0.7

    # Add randomness — some lies just slip through, some get caught
    margin = player_read - npc_deception + random.uniform(-15, 15)

    if margin > 20:
        return "caught"       # "Something about that doesn't add up."
    elif margin > 5:
        return "suspicious"   # "She hesitated before answering."
    else:
        return "believed"     # Player doesn't know they were lied to


def eavesdrop(player_perception, npcs_talking):
    """
    The player is trying to listen in on a conversation.
    How much they hear depends on their perception stat.

    Args:
        player_perception: int 0-100
        npcs_talking: list of NPC objects who are talking
                     (used for names and topic generation)

    Returns:
        Dict with:
        - "completeness": string ("tone_only", "fragments", "most_words",
                                  "full_sentences", "everything")
        - "heard": string (what the player actually heard)
        - "speaker_names": list of names they can identify (empty if perception is low)
    """
    # Determine how much the player hears based on perception
    # From MECHANICS.md:
    #   0-20:  tone only ("angry voices", "laughter")
    #   20-40: fragments ("...the bridge... can't... soldiers...")
    #   40-60: most words, miss key details
    #   60-80: full sentences, understand context
    #   80+:   everything, identify speakers and emotional subtext

    # Add a small random variance
    effective = player_perception + random.uniform(-5, 5)

    speaker_names = [npc.name for npc in npcs_talking] if npcs_talking else ["unknown"]

    if effective < 20:
        return {
            "completeness": "tone_only",
            "heard": "You hear voices — the tone is tense, but you can't make out words.",
            "speaker_names": [],
        }
    elif effective < 40:
        # Fragments — pick a few words from potential topics
        fragments = random.choice([
            "...the bridge... can't... soldiers...",
            "...payment... refused... three days...",
            "...saw them at... couldn't believe...",
            "...the old road... dangerous... wouldn't go...",
            "...told her... won't listen... too late...",
        ])
        return {
            "completeness": "fragments",
            "heard": f"You catch fragments: \"{fragments}\"",
            "speaker_names": [],
        }
    elif effective < 60:
        return {
            "completeness": "most_words",
            "heard": "You hear most of the conversation but miss key details.",
            "speaker_names": speaker_names[:1],  # can identify one speaker
        }
    elif effective < 80:
        return {
            "completeness": "full_sentences",
            "heard": "You hear the full conversation clearly.",
            "speaker_names": speaker_names,
        }
    else:
        return {
            "completeness": "everything",
            "heard": "You hear every word, and you can read the tension between them.",
            "speaker_names": speaker_names,
        }
