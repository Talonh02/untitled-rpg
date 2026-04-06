"""
Scene image generation — creates pixel art snapshots of the current scene.
Uses the Retro Diffusion API for consistent pixel art style.

The player clicks "Visualize" and gets a pixel art image of what's in front of them.
~$0.02-0.03 per image via rd_fast.
"""
import os
import json
import base64
import time
import logging
import urllib.request

import app.config as config

_log = logging.getLogger("image")

# Load Retro Diffusion API key from the shared keys file
_RD_KEY = ""
for path in [
    os.path.expanduser("~/Desktop/Claude/erudite/.sensitive/keys.json"),
    os.path.join(os.path.dirname(__file__), "..", "..", ".sensitive", "keys.json"),
]:
    if os.path.exists(path):
        with open(path) as f:
            keys = json.load(f)
            _RD_KEY = keys.get("retro_diffusion_key", "")
            if _RD_KEY:
                break

RD_API_URL = "https://api.retrodiffusion.ai/v1/inferences"


def _call_retro_diffusion(prompt, width=256, height=256, style="rd_fast__detailed"):
    """Call the Retro Diffusion API and return base64 image data."""
    payload = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "prompt_style": style,
        "num_images": 1,
        "remove_bg": False,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        RD_API_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-RD-Token": _RD_KEY,
        },
        method="POST",
    )
    response = urllib.request.urlopen(req, timeout=60)
    result = json.loads(response.read().decode("utf-8"))

    if result.get("base64_images"):
        return result["base64_images"][0]
    return None


def generate_scene_image(game_state, save_dir="static/images") -> str:
    """
    Generate a pixel art image of the current scene.

    Returns the URL path to the saved image (e.g. "/static/images/scene_123.png"),
    or empty string if generation fails.
    """
    os.makedirs(save_dir, exist_ok=True)
    prompt = _describe_scene(game_state)

    try:
        img_b64 = _call_retro_diffusion(prompt, width=256, height=256,
                                         style="rd_fast__detailed")
        if img_b64:
            filename = f"scene_{int(time.time())}.png"
            filepath = os.path.join(save_dir, filename)
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(img_b64))
            return f"/static/images/{filename}"
    except Exception as e:
        _log.warning(f"Scene image generation failed: {e}")

    return ""


def generate_npc_portrait(npc, game_state, save_dir="static/images") -> str:
    """
    Generate a pixel art portrait of a specific NPC.
    Uses rd_fast__portrait style for character focus.
    """
    os.makedirs(save_dir, exist_ok=True)

    # Build a character-focused prompt
    age = "young" if npc.age < 25 else "middle-aged" if npc.age < 50 else "older"
    build_val = (npc.stats.strength + npc.stats.toughness) / 2
    build = "large muscular" if build_val > 65 else "thin" if build_val < 30 else ""

    mood = npc.temperament
    depth = npc.stats.depth_score()
    gaze = "intelligent piercing eyes" if depth > 60 else "weary eyes" if depth > 40 else "simple expression"

    world = game_state.world
    time_light = {
        "dawn": "golden dawn light",
        "morning": "morning light",
        "afternoon": "warm afternoon sun",
        "evening": "warm candlelight orange glow",
        "night": "flickering candlelight deep shadows",
    }.get(world.time_slot, "ambient light")

    prompt = (
        f"Portrait of a {age} {build} {npc.occupation}, "
        f"{mood} expression, {gaze}, dark fantasy character, "
        f"lit by {time_light}, detailed face close-up"
    )

    try:
        img_b64 = _call_retro_diffusion(prompt, width=128, height=128,
                                         style="rd_fast__portrait")
        if img_b64:
            filename = f"npc_{npc.id}_{int(time.time())}.png"
            filepath = os.path.join(save_dir, filename)
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(img_b64))
            return f"/static/images/{filename}"
    except Exception as e:
        _log.warning(f"NPC portrait generation failed: {e}")

    return ""


def _describe_scene(game_state) -> str:
    """
    Build a visual description of the current scene from game state.
    No model call — pure Python, instant, free.
    """
    world = game_state.world
    player = game_state.player
    parts = []

    # Location
    loc = world.locations.get(player.location) if player else None
    if loc:
        parts.append(loc.description or f"A {loc.type} called {loc.name}")

    # Lighting from time of day
    time_mood = {
        "dawn": "soft golden dawn light",
        "morning": "bright morning light",
        "afternoon": "warm afternoon sunlight",
        "evening": "warm orange candlelight long shadows",
        "night": "moonlight and flickering candlelight deep shadows",
    }
    parts.append(time_mood.get(world.time_slot, "ambient light"))

    # Characters present (up to 3)
    if player:
        npcs = world.npcs_at_location(player.location)
        if npcs:
            npc_parts = []
            for npc in npcs[:3]:
                age = "young" if npc.age < 25 else "older" if npc.age > 50 else ""
                build_val = (npc.stats.strength + npc.stats.toughness) / 2
                build = "large" if build_val > 65 else "thin" if build_val < 30 else ""
                desc = f"{age} {build} {npc.occupation}".strip()
                npc_parts.append(desc)
            parts.append("characters: " + ", ".join(npc_parts))

    # Season
    season_mood = {
        "spring": "spring green outside",
        "summer": "warm golden summer",
        "autumn": "autumn orange brown leaves",
        "winter": "cold winter frost",
    }
    parts.append(season_mood.get(world.season, ""))

    scene = ", ".join(p for p in parts if p)
    return f"dark fantasy pixel art scene, {scene}"
