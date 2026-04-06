"""
Web server — serves the HTML frontend and handles game API requests.
Run with: python3 run.py --web
"""
import os
import sys
import json
from flask import Flask, jsonify, request, send_from_directory

# Make sure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.data import GameState

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
app = Flask(__name__, static_folder=os.path.join(PROJECT_ROOT, 'static'))

# Single-player game state — persists between requests
_game = {"loop": None}


# ============================================================
# STATIC FILE SERVING
# ============================================================

@app.route('/')
def index():
    return send_from_directory(app.static_folder, 'index.html')


@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)


# ============================================================
# GAME API
# ============================================================

@app.route('/api/archetypes')
def archetypes():
    """Return available character archetypes for the creation screen."""
    from app.game.player import get_archetype_list
    return jsonify(get_archetype_list())


@app.route('/api/new-game', methods=['POST'])
def new_game():
    """Create a new game — world, player, initial scene."""
    global _game
    data = request.json or {}
    name = data.get('name', 'Stranger')
    creation_type = data.get('type', 'quick')
    archetype = data.get('archetype', 'wanderer')
    description = data.get('description', '')

    game_state = GameState()

    # Generate world
    # Try AI world builder first (Opus — rich lore, names, factions)
    # Then fill in geography structure (coordinates, roads, populations)
    try:
        from app.engine.world import generate_starter_world
        game_state.world = generate_starter_world()
    except Exception:
        from app.data import World
        game_state.world = World(name="", era="", tone="")

    # If AI world builder didn't create enough locations, generate structure
    if len(game_state.world.locations) < 10:
        from app.engine.worldgen import generate_world_structure
        generate_world_structure(game_state.world, num_regions=4, cities_per_region=3)

    # Post-process: assign coordinates and roads to any locations missing them
    try:
        from app.engine.geography import build_geography
        build_geography(game_state.world)
    except Exception:
        pass

    # Create the player
    if creation_type == 'custom' and description:
        try:
            from app.game.player import create_player_custom
            player = create_player_custom(name, description, game_state.world)
        except Exception:
            from app.game.player import create_player_quick
            player = create_player_quick(name, 'wanderer', game_state.world)
    else:
        from app.game.player import create_player_quick
        player = create_player_quick(name, archetype, game_state.world)

    game_state.player = player

    # Initialize game loop (ui=None for web mode)
    from app.game.loop import GameLoop
    _game["loop"] = GameLoop(game_state, ui=None)

    # Auto-save the world so we never have to regenerate
    try:
        from app.game.state import save_game as _save
        os.makedirs("saves", exist_ok=True)
        _save(game_state, "saves/save.json")
    except Exception:
        pass

    # Save player profile for quick reuse
    _save_profile(name, creation_type, archetype, description)

    # Get opening narration and state
    initial = _game["loop"].get_initial_scene()
    state = _game["loop"].get_state_for_ui()

    return jsonify({
        "narration": initial,
        "state": state,
        "player": {
            "name": player.name,
            "backstory": player.backstory,
            "weapon": player.weapon,
            "armor": player.armor,
            "coins": player.coins,
        }
    })


@app.route('/api/action', methods=['POST'])
def action():
    """Process a player action (freeform text or button click)."""
    if not _game["loop"]:
        return jsonify({"error": "No active game. Start a new game first."}), 400

    data = request.json or {}

    # Button actions skip the interpreter (cheaper, more reliable)
    if data.get('button'):
        result = _game["loop"].process_button(data['button'], data.get('target', ''))
    else:
        text = data.get('text', '')
        if not text:
            return jsonify({"error": "No input provided."}), 400
        result = _game["loop"].process_action(text)

    return jsonify(result)


@app.route('/api/state')
def state():
    """Get the current game state for the side panels."""
    if not _game["loop"]:
        return jsonify({"error": "No active game."}), 400
    return jsonify(_game["loop"].get_state_for_ui())


@app.route('/api/save', methods=['POST'])
def save():
    """Save the current game to disk."""
    if not _game["loop"]:
        return jsonify({"error": "No active game."}), 400
    try:
        from app.game.state import save_game
        save_game(_game["loop"].state, "saves/save.json")
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/load', methods=['POST'])
def load():
    """Load a saved game."""
    global _game
    if not os.path.exists("saves/save.json"):
        return jsonify({"error": "No save file found."}), 404
    try:
        from app.game.state import load_game
        from app.game.loop import GameLoop
        game_state = load_game("saves/save.json")
        _game["loop"] = GameLoop(game_state, ui=None)
        initial = _game["loop"].get_initial_scene()
        state = _game["loop"].get_state_for_ui()
        return jsonify({"narration": initial, "state": state})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/battle', methods=['POST'])
def battle():
    """Run a round-by-round battle simulation. Returns all rounds for playback."""
    if not _game["loop"]:
        return jsonify({"error": "No active game."}), 400

    data = request.json or {}
    enemy_id = data.get('enemy_id', '')
    player_fights = data.get('player_fights', True)
    hold_companions = data.get('hold_companions', [])

    world = _game["loop"].state.world
    player = _game["loop"].state.player

    # Find enemy
    enemy = world.npcs.get(enemy_id)
    enemies = [enemy] if enemy else []
    # Also include enemy units at this location
    enemy_units = [u for u in world.units.values()
                   if u.location == player.location and not u.is_player_unit]
    enemies.extend(enemy_units)

    if not enemies:
        return jsonify({"error": "No enemies to fight."}), 400

    # Gather player's companions and units
    companions = [world.npcs[cid] for cid in player.companions if cid in world.npcs]
    player_units = [world.units[uid] for uid in player.hired_units if uid in world.units]

    from app.engine.battle_sim import simulate_battle
    result = simulate_battle(
        player, enemies, companions, player_units,
        options={"player_fights": player_fights, "hold_companions": hold_companions}
    )

    # Update game state after battle
    if result["outcome"] == "victory":
        player.kills += sum(1 for e in enemies if hasattr(e, 'is_alive') and not e.is_alive)
    _game["loop"].state.turn_number += 1

    result["state"] = _game["loop"].get_state_for_ui()
    return jsonify(result)


@app.route('/api/visualize', methods=['POST'])
def visualize():
    """Generate an image of the current scene or an NPC portrait."""
    if not _game["loop"]:
        return jsonify({"error": "No active game."}), 400

    data = request.json or {}
    target_npc_id = data.get('npc_id', '')

    try:
        from app.ai.image import generate_scene_image, generate_npc_portrait

        if target_npc_id:
            # Generate portrait of a specific NPC
            npc = _game["loop"].state.world.npcs.get(target_npc_id)
            if not npc:
                return jsonify({"error": "NPC not found."}), 404
            url = generate_npc_portrait(npc, _game["loop"].state)
        else:
            # Generate scene image
            url = generate_scene_image(_game["loop"].state)

        if url:
            return jsonify({"image_url": url})
        else:
            return jsonify({"error": "Image generation failed."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/lore')
def lore():
    """Return world lore for the Lore tab."""
    if not _game["loop"]:
        return jsonify({"error": "No active game."}), 400
    world = _game["loop"].state.world
    return jsonify({
        "name": world.name,
        "era": world.era,
        "tone": world.tone,
        "themes": world.themes,
        "factions": world.factions,
        "history": world.history,
        "religion": world.religion,
        "traditions": world.intellectual_traditions,
        "conflicts": world.active_conflicts,
        "economy": world.economy_info,
    })


# ============================================================
# SERVER STARTUP
# ============================================================

@app.route('/api/map')
def map_data():
    """Return full map data — locations with coordinates, roads, populations."""
    if not _game["loop"]:
        return jsonify({"error": "No active game."}), 400
    from app.engine.geography import get_map_data
    player_loc = _game["loop"].state.player.location if _game["loop"].state.player else ""
    return jsonify(get_map_data(_game["loop"].state.world, player_loc))


@app.route('/api/profile')
def get_profile():
    """Return saved player profile for auto-fill on character creation."""
    profile = _load_profile()
    return jsonify(profile)


def _save_profile(name, creation_type, archetype, description):
    """Save player profile so they don't re-enter it every time."""
    profile = {
        "name": name,
        "type": creation_type,
        "archetype": archetype,
        "description": description,
    }
    try:
        os.makedirs("saves", exist_ok=True)
        with open("saves/profile.json", "w") as f:
            json.dump(profile, f, indent=2)
    except Exception:
        pass


def _load_profile():
    """Load saved player profile."""
    try:
        with open("saves/profile.json") as f:
            return json.load(f)
    except Exception:
        return {}


def start_server(port=5000):
    """Start the Flask dev server."""
    print(f"\n  ╔═══════════════════════════════════╗")
    print(f"  ║     UNTITLED RPG — Web Mode       ║")
    print(f"  ║   http://localhost:{port}            ║")
    print(f"  ╚═══════════════════════════════════╝\n")
    app.run(host='0.0.0.0', port=port, debug=False)
