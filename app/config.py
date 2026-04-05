"""
Configuration — API keys and model settings.
Loads keys from environment variables or a keys.json file.
"""
import os
import json

# --- API Key Loading ---
# Try keys.json first (check a few common locations), fall back to env vars
KEYS = {}
KEY_PATHS = [
    os.path.expanduser("~/Desktop/Claude/erudite/.sensitive/keys.json"),
    os.path.join(os.path.dirname(__file__), "..", ".sensitive", "keys.json"),
]
for path in KEY_PATHS:
    if os.path.exists(path):
        with open(path) as f:
            KEYS = json.load(f)
        break

def get_key(name):
    """Get an API key from keys.json or environment variable."""
    # Try keys.json first (various key name formats)
    for key_name in [name, name.lower(), name.upper()]:
        if key_name in KEYS:
            return KEYS[key_name]
    # Fall back to env var
    return os.environ.get(name, "")

ANTHROPIC_API_KEY = get_key("ANTHROPIC_API_KEY") or get_key("anthropic")
OPENAI_API_KEY = get_key("OPENAI_API_KEY") or get_key("openai")
GEMINI_API_KEY = get_key("GEMINI_API_KEY") or get_key("gemini") or get_key("gemini_api_key")

# --- Model Configuration ---
# Maps our role names to actual model IDs and providers
MODELS = {
    # Narrator — best prose (Sonnet)
    "narrator": {"provider": "anthropic", "model": "claude-sonnet-4-20250514", "max_tokens": 1024},
    # Interpreter — cheap, fast, just extracts intent
    "interpreter": {"provider": "gemini", "model": "gemini-2.5-flash", "max_tokens": 1024},
    # Character Author — writes NPC souls from stat blocks (Opus)
    "character_author": {"provider": "anthropic", "model": "claude-sonnet-4-20250514", "max_tokens": 2048},
    # Director — daily world events
    "director": {"provider": "gemini", "model": "gemini-2.5-flash", "max_tokens": 2048},
    # World Builder — one-time world generation (big call)
    "world_builder": {"provider": "anthropic", "model": "claude-sonnet-4-20250514", "max_tokens": 8192},
    # NPC models by tier (selected based on depth score)
    "npc_flash_lite": {"provider": "gemini", "model": "gemini-3.1-flash-lite-preview", "max_tokens": 256},
    "npc_flash": {"provider": "gemini", "model": "gemini-2.5-flash", "max_tokens": 512},
    "npc_sonnet": {"provider": "anthropic", "model": "claude-sonnet-4-20250514", "max_tokens": 768},
    "npc_opus": {"provider": "anthropic", "model": "claude-sonnet-4-20250514", "max_tokens": 1024},
    # Summarizer — compresses action logs
    "summarizer": {"provider": "gemini", "model": "gemini-3.1-flash-lite-preview", "max_tokens": 512},
    # Argument evaluator — rates persuasion quality
    "evaluator": {"provider": "gemini", "model": "gemini-2.5-flash", "max_tokens": 256},
}

# NPC model tier thresholds (with fuzz — see select_npc_model in models.py)
NPC_MODEL_THRESHOLDS = {
    "npc_flash_lite": (0, 30),    # depth score 0-30 (fuzzed)
    "npc_flash": (30, 52),        # 30-52
    "npc_sonnet": (52, 72),       # 52-72
    "npc_opus": (72, 100),        # 72+
}

# Game constants
GAME_CONSTANTS = {
    "base_stat_mean": 42,
    "base_stat_std": 16,
    "player_stat_mean": 55,       # players are slightly above average
    "decision_point_margin": 0.08,
    "protagonist_death_reduction": 0.5,
    "sneak_attack_multiplier": 1.4,
    "trust_decay_companion": 0.5,  # per day if ignored
    "trust_decay_npc": 0.1,        # per day naturally
    "trust_no_decay_threshold": 60, # trust above this doesn't decay
    "food_per_day": 1,
    "travel_speed_foot": 30,       # km/day
    "travel_speed_horse": 60,
    "reputation_spread_speed": 40,  # km/day word of mouth
    "summarize_every_n_turns": 10,
}
