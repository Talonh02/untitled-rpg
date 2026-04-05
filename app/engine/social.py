"""
Social engine — persuasion, trust, deception, bluffing, romance.
Handles all the math for NPC relationships and how conversations move the needle.

Key idea: persuasion isn't a single roll. It's cumulative across exchanges.
Each argument the player makes adds or subtracts from a progress bar.
When progress crosses the threshold for a favor size, the NPC concedes.
"""
import random

from app.data import NPC, Player, Relationship
from app.config import GAME_CONSTANTS


def _clamp(value, low, high):
    """Keep a value within bounds."""
    return max(low, min(high, value))


def calculate_persuasion_delta(evaluation_scores, npc, relationship):
    """
    How much does one exchange of dialogue move the persuasion needle?

    The evaluator model scores the player's argument on 4 dimensions (each 0-1),
    then we weigh that against the NPC's resistance and the existing trust level.

    Args:
        evaluation_scores: dict with keys "relevance", "coherence",
                          "tone_match", "info_valid" — each 0.0 to 1.0.
                          These come from the evaluator model.
        npc: NPC object (we need their stubbornness, willpower, empathy, faction_loyalty)
        relationship: Relationship object (we need trust)

    Returns:
        Float from -12 to +18 — how much persuasion progress changes.
        Positive = moving toward concession. Negative = backfiring.
    """
    # Pull scores with safe defaults
    relevance = evaluation_scores.get("relevance", 0.5)
    coherence = evaluation_scores.get("coherence", 0.5)
    tone_match = evaluation_scores.get("tone_match", 0.5)
    info_valid = evaluation_scores.get("info_valid", 0.5)

    # Base argument strength: weighted average of the 4 dimensions
    argument_strength = (
        relevance * 0.35 +
        coherence * 0.25 +
        tone_match * 0.25 +
        info_valid * 0.15
    )

    # NPC resistance (0.0 to 1.0, higher = harder to persuade)
    resistance = (
        npc.stats.stubbornness * 0.40 +
        npc.stats.willpower * 0.30 +
        (100 - npc.stats.empathy) * 0.15 +   # low empathy = harder to reach
        npc.faction_loyalty * 0.15             # loyal to their faction = harder to sway
    ) / 100.0

    # Trust bonus: up to +0.3 at max trust, scales linearly
    trust = relationship.trust if relationship else 0.0
    trust_bonus = (trust / 100.0) * 0.3

    # Calculate the raw delta
    delta = (argument_strength - resistance + trust_bonus) * 20.0
    # Typical range: about -10 to +15 per exchange

    # Clamp so one exchange can't do everything
    delta = _clamp(delta, -12.0, 18.0)

    return delta


def get_persuasion_threshold(favor_size, npc_stubbornness=50):
    """
    How much total persuasion progress is needed to get a given favor?

    Stubbornness modifies the threshold: pushovers need less, stubborn
    NPCs need a lot more convincing.

    Args:
        favor_size: string — "small", "medium", "large", "extreme", "impossible"
        npc_stubbornness: int 0-100

    Returns:
        Float — the total persuasion_progress needed.
    """
    # Base thresholds from MECHANICS.md
    base_thresholds = {
        "small":      random.uniform(15, 30),    # directions, gossip
        "medium":     random.uniform(40, 60),    # discount, access, info
        "large":      random.uniform(70, 90),    # risk their safety, betray someone
        "extreme":    random.uniform(90, 120),   # betray faction, sacrifice
        "impossible": 150.0,                      # violates core values
    }
    base = base_thresholds.get(favor_size, 50.0)

    # Stubbornness modifier: 0.7x (pushover) to 1.3x (extremely stubborn)
    stubbornness_mult = 0.7 + (npc_stubbornness / 100.0) * 0.6
    return base * stubbornness_mult


def update_trust(npc, interaction_type, details=None):
    """
    Update an NPC's trust toward the player based on what happened.
    Trust has inertia — it's harder to change at extremes.

    Args:
        npc: NPC object (must have npc.relationship)
        interaction_type: string key like "kind_words", "kept_promise", "betrayed", etc.
        details: optional dict with extra context (not used in base calc)

    Returns:
        Float — the new trust value after the update.
    """
    if npc.relationship is None:
        npc.relationship = Relationship()

    # Trust effect ranges from MECHANICS.md
    # Each is a (min, max) tuple — we roll within the range
    TRUST_EFFECTS = {
        "kind_words":       (2, 5),
        "helpful_action":   (5, 10),
        "shared_secret":    (8, 15),
        "kept_promise":     (10, 20),
        "saved_their_life": (25, 40),
        "lied_to_them":     (-25, -10),   # if detected
        "broke_promise":    (-30, -15),
        "harmed_friend":    (-40, -20),
        "betrayed":         (-80, -40),
        "ignored_them":     (-3, -1),      # per day of neglect (companions)
    }

    if interaction_type not in TRUST_EFFECTS:
        return npc.relationship.trust  # unknown interaction, no change

    low, high = TRUST_EFFECTS[interaction_type]
    # Roll a random change within the range
    if low < 0:
        change = -random.uniform(abs(high), abs(low))  # negative changes
    else:
        change = random.uniform(low, high)

    # Trust has inertia at extremes — diminishing returns
    trust = npc.relationship.trust
    if trust > 70:
        change *= 0.6    # hard to go from 80 to 90
    if trust < 20:
        change *= 0.7    # hard to rebuild once broken

    npc.relationship.trust = _clamp(trust + change, -100.0, 100.0)
    npc.relationship.interactions += 1
    return npc.relationship.trust


def detect_bluff(player_charisma, npc_perception, claim_valid=False):
    """
    Can the NPC tell the player is bluffing?

    If the claim is actually valid, the NPC can't detect a lie
    (because there isn't one). For actual bluffs, it's the player's
    charisma vs the NPC's perception, plus randomness.

    Args:
        player_charisma: int 0-100
        npc_perception: int 0-100
        claim_valid: bool — if True, there's nothing to detect

    Returns:
        "caught", "suspicious", or "believed"
    """
    if claim_valid:
        return "believed"  # you can't detect a truth as a lie

    # Player's deception ability vs NPC's detection ability
    player_deception = player_charisma + random.uniform(-15, 15)
    npc_detection = npc_perception + random.uniform(-15, 15)

    margin = npc_detection - player_deception

    if margin > 20:
        return "caught"        # "I know you're lying."
    elif margin > 5:
        return "suspicious"    # "Something about that doesn't add up..."
    else:
        return "believed"      # NPC buys it


def update_romance(player, npc, interaction_type, model_evaluation=None):
    """
    Update romance metrics (attraction, comfort, intimacy) based on an interaction.
    Trust is handled by update_trust separately.

    Args:
        player: Player object
        npc: NPC object (must have npc.relationship)
        interaction_type: what happened — "clever_remark", "brave_action",
                         "shared_meal", "private_conversation",
                         "vulnerable_moment", "survived_danger",
                         "cruelty", "dismissive", "shared_their_secret"
        model_evaluation: optional dict from the AI evaluator with
                         quality scores for dialogue-based interactions

    Returns:
        Dict with "stage_before", "stage_after", "changes" summarizing what moved.
    """
    if npc.relationship is None:
        npc.relationship = Relationship()

    rel = npc.relationship
    stage_before = rel.stage

    # Track what changed for the return value
    changes = {}

    # --- Attraction changes ---
    attraction_delta = 0
    if interaction_type == "clever_remark":
        attraction_delta = random.uniform(2, 5)
    elif interaction_type == "brave_action":
        attraction_delta = random.uniform(3, 8)
    elif interaction_type == "time_together":
        attraction_delta = random.uniform(1, 3)
    elif interaction_type == "cruelty":
        attraction_delta = -random.uniform(5, 15)
    elif interaction_type == "cowardice":
        attraction_delta = -random.uniform(5, 10)

    if attraction_delta != 0:
        rel.attraction = _clamp(rel.attraction + attraction_delta, 0, 100)
        changes["attraction"] = round(attraction_delta, 1)

    # --- Comfort changes ---
    comfort_delta = 0
    if interaction_type in ("kind_interaction", "shared_meal", "time_together"):
        comfort_delta = random.uniform(1, 3)
    elif interaction_type == "shared_meal":
        comfort_delta = random.uniform(3, 8)
    elif interaction_type == "remembered_detail":
        comfort_delta = random.uniform(5, 10)
    elif interaction_type == "aggressive_action":
        comfort_delta = -random.uniform(5, 10)
    elif interaction_type == "caught_lying":
        comfort_delta = -random.uniform(3, 5)

    if comfort_delta != 0:
        rel.comfort = _clamp(rel.comfort + comfort_delta, 0, 100)
        changes["comfort"] = round(comfort_delta, 1)

    # --- Intimacy changes ---
    intimacy_delta = 0
    if interaction_type == "vulnerable_moment":
        # NPC shared something personal and player responded well
        intimacy_delta = random.uniform(3, 8)
    elif interaction_type == "player_vulnerable":
        # Player shared something personal
        intimacy_delta = random.uniform(5, 12)
    elif interaction_type == "private_conversation":
        intimacy_delta = random.uniform(2, 5)
    elif interaction_type == "survived_danger":
        intimacy_delta = random.uniform(8, 15)
    elif interaction_type == "dismissive":
        intimacy_delta = -random.uniform(5, 10)
    elif interaction_type == "shared_their_secret":
        # Player told someone else the NPC's secret
        intimacy_delta = -random.uniform(10, 20)

    if intimacy_delta != 0:
        rel.intimacy = _clamp(rel.intimacy + intimacy_delta, 0, 100)
        changes["intimacy"] = round(intimacy_delta, 1)

    stage_after = rel.stage

    return {
        "stage_before": stage_before,
        "stage_after": stage_after,
        "stage_changed": stage_before != stage_after,
        "changes": changes,
    }


def apply_trust_decay(npc, is_companion=False):
    """
    Trust decays slowly when the player isn't around.
    Companions decay faster if ignored. High trust (>60) doesn't decay.

    Call this once per in-game day for relevant NPCs.

    Args:
        npc: NPC object with relationship
        is_companion: if True, uses the faster companion decay rate
    """
    if npc.relationship is None:
        return

    trust = npc.relationship.trust
    threshold = GAME_CONSTANTS.get("trust_no_decay_threshold", 60)

    # High trust doesn't decay — real relationships persist
    if trust > threshold:
        return

    if is_companion:
        decay = GAME_CONSTANTS.get("trust_decay_companion", 0.5)
    else:
        decay = GAME_CONSTANTS.get("trust_decay_npc", 0.1)

    npc.relationship.trust = max(-100, trust - decay)


def apply_attraction_decay(npc):
    """
    Attraction decays at -1/day if not interacting.
    Call once per in-game day for NPCs with attraction > 0.
    """
    if npc.relationship is None:
        return
    if npc.relationship.attraction > 0:
        npc.relationship.attraction = max(0, npc.relationship.attraction - 1.0)
