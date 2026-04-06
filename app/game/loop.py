"""
The main game loop — the heart of the game.
Every turn: get input → interpret → route to engine → narrate → display.
"""
import random

from app.crash_log import log_crash, clear_log

from app.data import (
    GameState, Action, CombatOutcome, NPC, Relationship,
    WEAPONS, ARMOR, WEAPON_ARMOR_MATRIX, ENTITY_TIER_MULTIPLIERS
)
from app.config import GAME_CONSTANTS
from app.game.state import (
    assemble_scene_context, assemble_npc_context,
    log_action, flag_moment, run_summarizer, save_game
)


# ============================================================
# INTERVENTION LAYER — hardcoded content boundaries
# The world reacts with brutal consequences, never a popup.
# ============================================================

INTERVENTION_TRIGGERS = [
    "sexual_assault", "harm_child", "torture_innocent",
    "child_abuse", "rape", "molest",
]

INTERVENTION_RESPONSES = [
    "A man steps out of the shadows — he was standing right there the whole time. "
    "The blade enters before you even see his hand move.",
    "A door crashes open. Three armed guards pour in. They don't ask questions.",
    "The target was never helpless. The knife was in their hand before you finished the thought.",
    "A crossbow bolt strikes you from behind. Someone was watching.",
    "The crowd turns. All of them. At once. There is no escape from this many people.",
]


class GameLoop:
    """
    Runs the main turn-by-turn game loop.
    Gets player input, interprets it, routes to the right engine,
    narrates the result, and updates state.
    """

    def __init__(self, game_state: GameState, ui):
        self.state = game_state
        self.ui = ui  # TerminalUI instance from main.py
        # Track how many action turns since last time advancement
        self.action_count_since_time = 0
        # Track turns since last Director run
        self.last_director_day = 0

    def run(self):
        """
        Main game loop. Runs until the game is over.
        """
        # Clear crash log at game start so we only see this session's errors
        clear_log()
        # Show the opening scene
        self._show_initial_scene()

        while not self.state.game_over:
            try:
                self.play_turn()
            except KeyboardInterrupt:
                self.ui.show_system("\nGame paused. Type 'quit' to exit or press Enter to continue.")
                continue
            except Exception as e:
                # Never crash — log the error and keep going
                log_crash("play_turn", f"turn={self.state.turn_number}", e, "skipped turn")
                self.ui.show_system(f"[Something went wrong: {e}. The world continues.]")
                continue

    def play_turn(self):
        """
        One full turn of the game:
        1. Get input  2. Interpret  3. Route  4. Narrate  5. Update state
        """
        # Show status bar
        self._show_status()

        # 1. Get player input
        raw_input = self.ui.get_input()
        if not raw_input:
            return

        # Check for special commands first (inventory, save, etc.)
        if self._handle_special_command(raw_input):
            return

        # 2. Interpret the input — turn free text into a structured Action
        scene_context = assemble_scene_context(self.state)
        action = self._interpret_input(raw_input, scene_context)

        # 3. Check intervention layer BEFORE routing
        if self._check_intervention(action):
            return

        # 4. Route action to the appropriate engine
        engine_result = self._route_action(action)

        # 5. Narrate the result
        narration = self._narrate_result(action, engine_result, scene_context)

        # 6. Display to player
        self._display_result(action, narration, engine_result)

        # 7. Update game state
        self.state.turn_number += 1
        log_action(self.state, self.state.turn_number,
                   action.raw_input, str(engine_result), narration)

        # 8. Time advancement (every 5-10 action turns = 1 time slot)
        self.action_count_since_time += 1
        if self.action_count_since_time >= random.randint(5, 10):
            self._advance_time()
            self.action_count_since_time = 0

        # 9. Director events (once per new game day)
        if self.state.world.current_day > self.last_director_day:
            self._run_director()
            self.last_director_day = self.state.world.current_day

        # 10. Summarize old logs periodically
        summarize_every = GAME_CONSTANTS.get("summarize_every_n_turns", 10)
        if self.state.turn_number % summarize_every == 0:
            run_summarizer(self.state)

        # 11. Check if player is dead
        if self.state.player and self.state.player.health <= 0:
            self._handle_death("injuries")

    # ============================================================
    # INPUT INTERPRETATION
    # ============================================================

    def _interpret_input(self, raw_input: str, scene_context: str) -> Action:
        """
        Call the interpreter model to parse free text into a structured Action.
        Falls back to a simple keyword parser if the model fails.
        """
        try:
            from app.ai.interpreter import interpret
            action = interpret(raw_input, scene_context)
            if action:
                action.raw_input = raw_input
                return action
        except Exception as e:
            log_crash("interpret", "turn={}".format(getattr(getattr(self, "state", None), "turn_number", "?")), e, "used fallback")
            pass

        # Fallback: simple keyword-based parsing
        return self._fallback_interpret(raw_input)

    def _fallback_interpret(self, raw_input: str) -> Action:
        """
        Basic keyword parser when the AI interpreter isn't available.
        Not smart, but keeps the game playable.
        """
        text = raw_input.lower().strip()

        # Movement keywords
        if any(word in text for word in ["go ", "walk ", "move ", "enter ", "leave ", "head "]):
            return Action(type="movement", intent=text, raw_input=raw_input)

        # Combat keywords
        combat_words = ["attack", "fight", "punch", "strike", "kill", "hit", "stab",
                        "slash", "headbutt", "kick", "grab", "choke", "swing at", "tackle",
                        "shove", "throw", "wrestle", "bite", "elbow", "knee"]
        if any(word in text for word in combat_words):
            return Action(type="combat", intent=text, involves_combat=True, raw_input=raw_input)

        # Dialogue keywords — check for quotes or "say"/"tell"/"ask"
        if any(word in text for word in ["say ", "tell ", "ask ", "talk "]) or '"' in text:
            # Try to extract dialogue content
            dialogue = ""
            if '"' in raw_input:
                parts = raw_input.split('"')
                if len(parts) >= 2:
                    dialogue = parts[1]
            return Action(type="dialogue", dialogue_content=dialogue or text,
                          intent=text, raw_input=raw_input)

        # Observation
        if any(word in text for word in ["look", "examine", "inspect", "observe", "search"]):
            return Action(type="observation", intent=text, raw_input=raw_input)

        # Trade
        if any(word in text for word in ["buy ", "sell ", "trade ", "barter"]):
            return Action(type="trade", intent=text, raw_input=raw_input)

        # Stealth
        if any(word in text for word in ["sneak", "hide", "steal", "pickpocket"]):
            return Action(type="stealth", intent=text, covert=True, raw_input=raw_input)

        # Rest
        if any(word in text for word in ["rest", "sleep", "camp", "wait"]):
            return Action(type="rest", intent=text, raw_input=raw_input)

        # Internal thought
        if any(word in text for word in ["think", "remember", "consider", "reflect"]):
            return Action(type="internal", intent=text, raw_input=raw_input)

        # Default: treat it as a general action
        return Action(type="action", intent=text, raw_input=raw_input)

    # ============================================================
    # INTERVENTION CHECK
    # ============================================================

    def _check_intervention(self, action: Action) -> bool:
        """
        Check if the action triggers the intervention layer.
        If it does, narrate a brutal in-world consequence and return True.
        """
        # Check the action intent and raw input for trigger words
        check_text = (action.intent + " " + action.raw_input + " " +
                      action.manner + " " + action.type).lower()

        for trigger in INTERVENTION_TRIGGERS:
            if trigger in check_text:
                # Deliver the consequence
                response = random.choice(INTERVENTION_RESPONSES)
                self.ui.show_combat(response)

                # Severe damage or instant death
                if self.state.player:
                    self.state.player.health = 0
                    self._handle_death("the world's swift justice")
                return True
        return False

    # ============================================================
    # ACTION ROUTING — send the action to the right engine
    # ============================================================

    def _route_action(self, action: Action) -> dict:
        """
        Route a parsed Action to the appropriate engine module.
        Returns a dict describing what happened (for the narrator).
        """
        action_type = action.type

        if action_type == "movement":
            return self._handle_movement(action)
        elif action_type == "dialogue":
            return self._handle_dialogue(action)
        elif action_type == "combat":
            return self._handle_combat(action)
        elif action_type == "observation":
            return self._handle_observation(action)
        elif action_type == "trade":
            return self._handle_trade(action)
        elif action_type == "stealth":
            return self._handle_stealth(action)
        elif action_type == "rest":
            return self._handle_rest(action)
        elif action_type == "internal":
            return self._handle_internal(action)
        elif action_type == "romance":
            return self._handle_romance(action)
        elif action_type == "nonsense":
            return self._handle_nonsense(action)
        else:
            # Before falling through to generic, check if this looks like combat
            # that the interpreter missed (common when JSON parsing fails)
            raw = (action.raw_input or action.intent or "").lower()
            combat_words = ["attack", "fight", "punch", "strike", "kill", "hit", "stab",
                            "slash", "headbutt", "kick", "grab", "choke", "swing", "tackle",
                            "shove", "throw", "wrestle", "bite", "elbow", "knee"]
            if any(w in raw for w in combat_words):
                action.type = "combat"
                action.involves_combat = True
                return self._handle_combat(action)

            # Generic action — just narrate it
            return {"type": "generic", "description": action.intent}

    # --- Movement ---
    def _handle_movement(self, action: Action) -> dict:
        """Move the player locally or start travel."""
        try:
            from app.engine.movement import move_local
            # Fix #1: move_local expects (player, target_id, world)
            result = move_local(self.state.player, action.target or action.intent, self.state.world)
            return {"type": "movement", "result": result}
        except Exception as e:
            log_crash("move_local", "turn={}".format(getattr(getattr(self, "state", None), "turn_number", "?")), e, "used fallback")
            # Fallback: try to find a matching location and move there
            return self._fallback_movement(action)

    def _fallback_movement(self, action: Action) -> dict:
        """Simple movement fallback when the engine isn't available."""
        world = self.state.world
        player = self.state.player
        text = (action.target or action.intent).lower()

        # Try to find a location matching the text
        current_loc = world.locations.get(player.location)
        if current_loc and current_loc.children_ids:
            # Check children of current location
            for child_id in current_loc.children_ids:
                child = world.locations.get(child_id)
                if child and text in child.name.lower():
                    player.location = child_id
                    return {"type": "movement", "moved_to": child.name,
                            "description": child.description}

        # Check parent location
        if current_loc and current_loc.parent_id:
            parent = world.locations.get(current_loc.parent_id)
            if parent and text in parent.name.lower():
                player.location = parent.id
                return {"type": "movement", "moved_to": parent.name,
                        "description": parent.description}

        # Check all locations (broader search)
        for lid, loc in world.locations.items():
            if text in loc.name.lower():
                player.location = lid
                return {"type": "movement", "moved_to": loc.name,
                        "description": loc.description}

        return {"type": "movement", "moved_to": None,
                "description": "You look around but aren't sure where to go."}

    # --- Dialogue ---
    def _handle_dialogue(self, action: Action) -> dict:
        """Talk to an NPC. Promote them if this is the first meeting.
        Common nobodies (fate < 0.15) give terse responses — no model call."""
        world = self.state.world
        player = self.state.player

        # Find the target NPC
        npc = self._find_target_npc(action)
        if not npc:
            return {"type": "dialogue", "npc_name": None,
                    "response": "There's no one here by that name to talk to."}

        # Mark as met
        first_meeting = not npc.met_player
        npc.met_player = True

        # Initialize relationship if needed
        if not npc.relationship:
            npc.relationship = Relationship()
        npc.relationship.interactions += 1

        # First meeting: promote higher-tier NPCs with Character Author
        if first_meeting:
            if npc.fate >= 0.15 and not npc.system_prompt:
                # Uncommon+ NPCs get the full Character Author treatment
                self._promote_npc(npc)
            elif not npc.system_prompt:
                # Fallback: generate basic prompt if somehow missing
                npc.system_prompt = self._generate_basic_prompt(npc)

        # Build NPC context and call their model
        # Use dialogue_content (extracted speech) first, then raw_input (what they typed),
        # then intent as last resort. We want actual words, not "to ask about the war".
        player_words = action.dialogue_content or action.raw_input or action.intent
        npc_context = assemble_npc_context(npc, self.state)
        npc_response = self._call_npc_model(npc, player_words, npc_context)

        # Check if persuasion is involved
        if action.involves_persuasion:
            self._handle_persuasion(npc, action)

        # Check if deception is involved
        if action.involves_deception:
            self._handle_deception_check(npc, action)

        # Update trust slightly based on interaction
        try:
            from app.engine.social import update_trust
            # Fix #2: update_trust expects (npc, interaction_type_string, details_dict)
            update_trust(npc, "kind_words")
        except Exception as e:
            log_crash("unknown", "turn={}".format(getattr(getattr(self, "state", None), "turn_number", "?")), e, "used fallback")
            # Small default trust bump for friendly interaction
            if npc.relationship:
                npc.relationship.trust = min(100, npc.relationship.trust + 1)
                npc.relationship.comfort = min(100, npc.relationship.comfort + 0.5)

        # Store conversation memory so they remember next time
        player_said = player_words
        self._store_conversation_memory(npc, player_said, npc_response)

        return {"type": "dialogue", "npc_name": npc.name,
                "npc_id": npc.id, "response": npc_response}

    def _store_conversation_memory(self, npc: NPC, player_said: str, npc_said: str):
        """Write conversation back to the NPC's relationship so they remember next time."""
        if not npc.relationship:
            return

        rel = npc.relationship

        # Store what happened with timestamp (injected into next context)
        # FIX 9: append to conversation_log (full history) in addition to last_summary
        day = self.state.world.current_day
        rel.last_summary = f"[Day {day}] Player said: \"{player_said[:120]}\" You replied: \"{npc_said[:120]}\""
        rel.conversation_log.append(rel.last_summary)
        rel.conversation_log = rel.conversation_log[-15:]  # cap at 15 entries
        # Store the day for time-ago calculation
        if not hasattr(rel, '_last_interaction_day'):
            rel.flags = [f for f in rel.flags if not f.startswith("last_day:")]
        rel.flags = [f for f in rel.flags if not f.startswith("last_day:")]
        rel.flags.append(f"last_day:{day}")

        # Extract knowledge about the player from what they said
        # (simple keyword extraction — model-based extraction could come later)
        player_text = player_said.lower()
        knowledge_keywords = {
            "name": ["my name is", "i'm called", "call me", "i am"],
            "looking for": ["looking for", "searching for", "trying to find"],
            "from": ["i'm from", "i come from", "i traveled from"],
            "need": ["i need", "i want", "i'm looking to buy"],
        }
        for topic, triggers in knowledge_keywords.items():
            for trigger in triggers:
                if trigger in player_text:
                    # Extract the relevant bit after the trigger
                    idx = player_text.index(trigger) + len(trigger)
                    snippet = player_said[idx:idx+50].strip().rstrip(".,!?")
                    if snippet and snippet not in " ".join(rel.knowledge_of_player):
                        rel.knowledge_of_player.append(f"{topic}: {snippet}")
                    break

        # Keep knowledge list from growing forever
        rel.knowledge_of_player = rel.knowledge_of_player[-10:]

    # --- Combat ---
    def _handle_combat(self, action: Action) -> dict:
        """Resolve combat using the engine."""
        npc = self._find_target_npc(action)
        if not npc:
            return {"type": "combat", "result": "no_target",
                    "description": "You swing at the air. Nobody's there."}

        try:
            from app.engine.combat import resolve_combat
            # Fix #3: resolve_combat expects (player, [enemies], companions, context)
            # Look up companion NPC objects from player.companions IDs
            companions = [self.state.world.npcs[cid] for cid in self.state.player.companions
                          if cid in self.state.world.npcs]
            # Pass player's hired units into combat context
            player_units = [self.state.world.units[uid] for uid in self.state.player.hired_units
                            if uid in self.state.world.units]
            outcome = resolve_combat(self.state.player, [npc], companions,
                                     {"player_units": player_units})
            # Apply results to game state
            self._apply_combat_outcome(outcome, npc)
            return {"type": "combat", "outcome": outcome, "enemy_name": npc.name}
        except Exception as e:
            log_crash("resolve_combat", "turn={}".format(getattr(getattr(self, "state", None), "turn_number", "?")), e, "used fallback")
            # Fallback: simple combat resolution
            return self._fallback_combat(npc)

    def _fallback_combat(self, npc: NPC) -> dict:
        """Simple combat when the engine isn't ready."""
        player = self.state.player
        player_power = player.stats.combat_power(
            WEAPONS.get(player.weapon, {}).get("multiplier", 1.0),
            1.0  # no armor multiplier for now
        )
        enemy_power = npc.stats.combat_power()

        # Add randomness
        player_roll = player_power * random.uniform(0.8, 1.2)
        enemy_roll = enemy_power * random.uniform(0.8, 1.2)

        total = player_roll + enemy_roll
        if total == 0:
            total = 1
        margin = (player_roll - enemy_roll) / total

        # Apply HP damage using smooth margin curve
        from app.engine.combat import calculate_hp_damage
        hp_loss = calculate_hp_damage(margin, player.armor)
        player.health -= hp_loss

        if margin > 0.15:
            result = "victory"
            npc.is_alive = False
            player.kills += 1
            flag_moment(self.state, f"Killed {npc.name} in combat", "first_kill"
                        if player.kills == 1 else "combat")
        elif margin > 0:
            result = "narrow_victory"
            npc.is_alive = False
            player.kills += 1
        elif margin > -0.15:
            result = "narrow_defeat"
        else:
            result = "defeat"

        return {"type": "combat", "result": result, "margin": margin,
                "enemy_name": npc.name, "player_health": player.health}

    def _apply_combat_outcome(self, outcome, npc: NPC):
        """Apply combat results to game state."""
        player = self.state.player
        if isinstance(outcome, CombatOutcome):
            # Apply player injuries
            for inj in outcome.player_injuries:
                player.injuries.append(inj)
            # Apply HP damage using smooth margin-based formula
            from app.engine.combat import calculate_hp_damage
            hp_loss = calculate_hp_damage(outcome.margin, player.armor)
            player.health -= hp_loss
            # Track kills
            if outcome.result == "victory":
                player.kills += outcome.enemy_deaths
                npc.is_alive = False
                if player.kills == outcome.enemy_deaths:
                    flag_moment(self.state, f"First kill: {npc.name}", "first_kill")
            # Flag dramatic moments
            if outcome.margin_category in ("decisive", "crushing_defeat"):
                flag_moment(self.state,
                            f"Combat with {npc.name}: {outcome.result} ({outcome.margin_category})",
                            "combat")

    # --- Observation ---
    def _handle_observation(self, action: Action) -> dict:
        """Look around or examine something."""
        try:
            from app.engine.perception import observe_scene
            # Fix #7: observe_scene expects (player_perception_int, scene_details_list)
            perception = self.state.player.get_effective_stats().perception
            loc = self.state.world.locations.get(self.state.player.location)
            scene_details = []
            if loc:
                scene_details.append({"description": loc.description or loc.name, "min_perception": 0})
                for feat in loc.features:
                    scene_details.append({"description": feat, "min_perception": 30})
            npcs_here = self.state.world.npcs_at_location(self.state.player.location)
            for n in npcs_here:
                scene_details.append({"description": n.brief_description(), "min_perception": 10})
            result = observe_scene(perception, scene_details)
            return {"type": "observation", "result": result}
        except Exception as e:
            log_crash("observe_scene", "turn={}".format(getattr(getattr(self, "state", None), "turn_number", "?")), e, "used fallback")
            # Fallback: describe the current location and NPCs
            loc = self.state.world.locations.get(self.state.player.location)
            npcs_here = self.state.world.npcs_at_location(self.state.player.location)

            desc = ""
            if loc:
                desc = loc.description or f"You are in {loc.name}."
            npc_desc = ""
            if npcs_here:
                names = [n.brief_description() for n in npcs_here[:5]]
                npc_desc = "You see: " + "; ".join(names)

            return {"type": "observation",
                    "description": desc,
                    "npcs_visible": npc_desc}

    # --- Trade ---
    def _handle_trade(self, action: Action) -> dict:
        """Buy or sell items."""
        try:
            from app.engine.economy import calculate_price
            # Basic trade handling — the engine figures out prices
            return {"type": "trade", "description": action.intent}
        except Exception as e:
            log_crash("unknown", "turn={}".format(getattr(getattr(self, "state", None), "turn_number", "?")), e, "used fallback")
            return {"type": "trade",
                    "description": "Trading isn't fully set up yet, but you browse the wares."}

    # --- Stealth ---
    def _handle_stealth(self, action: Action) -> dict:
        """Sneaky stuff — stealing, hiding, eavesdropping."""
        try:
            from app.engine.perception import eavesdrop
            # Fix #8: eavesdrop expects (player_perception_int, npcs_talking_list)
            perception = self.state.player.get_effective_stats().perception
            npcs_here = self.state.world.npcs_at_location(self.state.player.location)
            result = eavesdrop(perception, npcs_here)
            return {"type": "stealth", "result": result}
        except Exception as e:
            log_crash("eavesdrop", "turn={}".format(getattr(getattr(self, "state", None), "turn_number", "?")), e, "used fallback")
            # Simple stealth check based on agility
            agility = self.state.player.stats.agility
            roll = random.randint(1, 100)
            success = roll < agility
            return {"type": "stealth", "success": success,
                    "description": "You move carefully..." if success
                    else "You stumble. Someone might have noticed."}

    # --- Rest ---
    def _handle_rest(self, action: Action) -> dict:
        """Rest to recover fatigue and advance time."""
        player = self.state.player

        # Restore fatigue
        old_fatigue = player.fatigue
        player.fatigue = max(0, player.fatigue - 40)

        # Slight health recovery if not badly hurt
        if player.health > 30:
            player.health = min(100, player.health + 5)

        # Increase hunger/thirst (time passes while resting)
        player.hunger = min(100, player.hunger + 10)
        player.thirst = min(100, player.thirst + 8)

        # Advance time by one slot
        self.state.world.advance_time_slot()

        return {"type": "rest",
                "fatigue_recovered": old_fatigue - player.fatigue,
                "new_time": self.state.world.time_slot,
                "description": "You rest for a while and feel somewhat better."}

    # --- Internal thought ---
    def _handle_internal(self, action: Action) -> dict:
        """The player is thinking, remembering, reflecting."""
        return {"type": "internal", "thought": action.intent,
                "description": "A moment of quiet reflection."}

    # --- Romance ---
    def _handle_romance(self, action: Action) -> dict:
        """Route romance through social engine with relationship tracking."""
        npc = self._find_target_npc(action)
        if not npc:
            return {"type": "romance", "description": "There's no one here for that."}

        if not npc.relationship:
            npc.relationship = Relationship()

        stage = npc.relationship.stage
        return {"type": "romance", "npc_name": npc.name,
                "stage": stage, "description": action.intent}

    # --- Nonsense ---
    def _handle_nonsense(self, action: Action) -> dict:
        """
        The player typed gibberish or something incoherent.
        Escalating world reaction based on how often they do this.
        """
        player = self.state.player
        player.nonsense_count += 1
        count = player.nonsense_count

        if count <= 2:
            desc = "You mutter something incoherent. People nearby glance at you."
        elif count <= 5:
            desc = ("You're acting strangely. A few people step away from you. "
                    "A guard watches from the corner.")
        elif count <= 8:
            desc = ("The guard approaches. 'Had too much to drink, friend?' "
                    "His hand rests on his weapon.")
        else:
            desc = ("Two guards grab your arms. 'That's enough. You're coming with us.' "
                    "They drag you toward the garrison.")
            # Actually apply consequences at high nonsense
            player.reputation.setdefault("local", {})
            player.reputation["local"]["sentiment"] = "suspicious"

        return {"type": "nonsense", "severity": count, "description": desc}

    # ============================================================
    # NARRATION
    # ============================================================

    def _narrate_result(self, action: Action, engine_result: dict,
                        scene_context: str) -> str:
        """
        Call the narrator model to turn engine results into prose.
        Falls back to the engine_result description if the model fails.
        """
        result_type = engine_result.get("type", "generic")

        # Combat gets special narration
        if result_type == "combat":
            return self._narrate_combat(engine_result, scene_context)

        # Try the narrator model
        try:
            from app.ai.narrator import narrate
            # Fix #10: narrate expects (scene_context, action, engine_result)
            narration = narrate(scene_context, action, engine_result)
            if narration:
                return narration
        except Exception as e:
            log_crash("narrate", "turn={}".format(getattr(getattr(self, "state", None), "turn_number", "?")), e, "used fallback")
            pass

        # Fallback: use the description from the engine result
        return engine_result.get("description", "Something happens.")

    def _narrate_combat(self, engine_result: dict, scene_context: str) -> str:
        """Narrate combat specifically — it gets special treatment."""
        try:
            from app.ai.narrator import narrate_combat
            # Fix #11: narrate_combat expects (CombatOutcome, participants_info_string)
            outcome = engine_result.get("outcome")
            enemy_name = engine_result.get("enemy_name", "unknown")
            participants_info = f"Player vs {enemy_name}. Scene: {scene_context}"
            if outcome:
                return narrate_combat(outcome, participants_info)
        except Exception as e:
            log_crash("get", "turn={}".format(getattr(getattr(self, "state", None), "turn_number", "?")), e, "used fallback")
            pass

        # Fallback: basic combat narration
        result = engine_result.get("result", "unknown")
        enemy = engine_result.get("enemy_name", "your opponent")
        if result in ("victory", "narrow_victory"):
            return f"You defeat {enemy}. The fight is over."
        elif result == "defeat":
            return f"{enemy} overpowers you. You fall."
        elif result == "no_target":
            return engine_result.get("description", "Nobody to fight.")
        else:
            return f"The fight with {enemy} ends inconclusively."

    # ============================================================
    # NPC INTERACTION HELPERS
    # ============================================================

    # ============================================================
    # COMMON NPC RESPONSES — no model call needed for nobodies
    # ============================================================

    COMMON_NPC_RESPONSES = [
        "Piss off.",
        "*ignores you*",
        "Do I know you?",
        "I'm drinking. Go away.",
        "Not interested.",
        "*grunts and turns away*",
        "Talk to someone else.",
        "What do you want?",
        "Buy your own drink.",
        "*stares blankly*",
        "Mind your business.",
        "I've got nothing for you.",
        "Leave me alone.",
        "*barely glances up*",
        "You lost?",
        "Not today, friend.",
    ]

    # Names for generating ambient NPCs on the fly
    AMBIENT_NAMES = [
        "Harn", "Bessa", "Colt", "Mira", "Dort", "Lena", "Peck", "Sorra",
        "Tam", "Vella", "Keth", "Nira", "Gost", "Willa", "Fen", "Dara",
        "Oric", "Tessa", "Brin", "Yara", "Mosk", "Ilsa", "Rutt", "Devva",
    ]

    # Occupations by location type
    AMBIENT_OCCUPATIONS = {
        "tavern": ["laborer", "farmer", "sailor", "carpenter", "drunk", "traveler", "off-duty guard"],
        "market": ["merchant", "porter", "fishmonger", "weaver", "beggar", "craftsman"],
        "building": ["commoner", "laborer", "visitor", "clerk"],
        "district": ["commoner", "laborer", "farmer", "traveler", "beggar"],
    }

    def _generate_ambient_npc(self) -> NPC:
        """Generate an NPC on the fly using the full causal chain:
        Role → Fate (attractor) → Stats (fate-shifted) → Power Tier → Everything."""
        loc = self.state.world.locations.get(self.state.player.location)
        loc_type = loc.type if loc else "building"

        # Pick occupation based on where we are
        occupations = self.AMBIENT_OCCUPATIONS.get(loc_type,
                      self.AMBIENT_OCCUPATIONS["building"])
        occupation = random.choice(occupations)

        # Use the causal chain generator
        from app.engine.npc_life import generate_npc
        npc = generate_npc(occupation, location=self.state.player.location)

        # Add to world so they persist while we're here
        self.state.world.npcs[npc.id] = npc
        return npc

    def _find_target_npc(self, action: Action) -> NPC:
        """
        Find the NPC the player is trying to interact with.
        Matches against: NPC id, name, occupation, and common descriptors.
        If nobody matches, generates an ambient NPC on the fly.
        """
        world = self.state.world

        # Direct ID match
        if action.target and action.target in world.npcs:
            return world.npcs[action.target]

        # Get NPCs at the player's location
        npcs_here = world.npcs_at_location(self.state.player.location)
        if not npcs_here:
            return None

        search_text = (action.target or action.intent or action.raw_input).lower()

        # Check for "random" / "stranger" / "someone" / "anyone" — pick a random NPC
        random_words = ["random", "stranger", "someone", "anyone", "nearby", "closest"]
        if any(w in search_text for w in random_words):
            return random.choice(npcs_here)

        # Try matching against NPC name
        for npc in npcs_here:
            if npc.name.lower() in search_text or search_text in npc.name.lower():
                return npc

        # Try matching against occupation (handles "the guard", "bartender", "merchant")
        for npc in npcs_here:
            occ = npc.occupation.lower()
            # Also check common synonyms
            occ_synonyms = {
                "barkeeper": ["bartender", "barkeep", "barman"],
                "soldier": ["guard", "knight", "warrior"],
                "merchant": ["trader", "shopkeeper", "vendor", "seller"],
                "healer": ["doctor", "medic", "herbalist"],
                "scholar": ["professor", "teacher", "academic"],
                "farmer": ["peasant"],
                "blacksmith": ["smith", "forge"],
            }
            all_names = [occ] + occ_synonyms.get(occ, [])
            if any(name in search_text for name in all_names):
                return npc

        # Try matching gendered descriptors ("the woman", "the man", "girl", "old man")
        gender_hints = {"woman": "f", "girl": "f", "lady": "f", "her": "f",
                        "man": "m", "guy": "m", "boy": "m", "him": "m"}
        for hint, gender in gender_hints.items():
            if hint in search_text:
                # Pick first NPC that vaguely matches (rough heuristic using name)
                # In future: NPCs should have a gender field
                return random.choice(npcs_here)

        # If there's only one NPC here, they're probably the target
        if len(npcs_here) == 1:
            return npcs_here[0]

        # Last resort: if the player is clearly trying to interact with someone
        # ("talk to the man", "approach someone"), generate an ambient NPC
        interaction_words = ["talk", "speak", "approach", "ask", "say", "tell",
                             "man", "woman", "person", "guy", "girl", "someone"]
        if any(w in search_text for w in interaction_words):
            return self._generate_ambient_npc()

        # If we have named NPCs and nothing matched, pick the first one
        if npcs_here:
            return npcs_here[0]

        return None

    def _promote_npc(self, npc: NPC):
        """
        Promote an NPC from a stat block to an active character.
        Calls the Character Author to write their system prompt.
        """
        try:
            from app.ai.character_author import author_character
            # Fix #4: author_character returns (system_prompt, backstory) tuple
            # and expects a world context string, not the World object
            world = self.state.world
            world_context = (f"World: {world.name}, Era: {world.era}, Tone: {world.tone}. "
                             f"Themes: {', '.join(world.themes)}. "
                             f"Traditions: {', '.join(world.intellectual_traditions[:3])}.")
            system_prompt, backstory = author_character(npc, world_context)
            if system_prompt:
                npc.system_prompt = system_prompt
                npc.backstory = backstory
                return
        except Exception as e:
            log_crash("author_character", "turn={}".format(getattr(getattr(self, "state", None), "turn_number", "?")), e, "used fallback")
            pass

        # Fallback: generate a basic system prompt from stats
        npc.system_prompt = self._generate_basic_prompt(npc)

    def _generate_basic_prompt(self, npc: NPC) -> str:
        """Generate a system prompt for a common NPC without a model call.
        These are normal people — they answer questions, give directions,
        complain about weather, share local gossip. Just not deeply."""
        traits = []
        if npc.stats.intelligence > 60:
            traits.append("articulate")
        elif npc.stats.intelligence < 30:
            traits.append("simple-spoken")
        if npc.stats.empathy > 60:
            traits.append("friendly")
        elif npc.stats.empathy < 30:
            traits.append("brusque")
        if npc.stats.humor > 60:
            traits.append("quick to joke")
        if npc.stats.courage > 70:
            traits.append("confident")
        elif npc.stats.courage < 25:
            traits.append("nervous")
        if npc.stats.honesty < 30:
            traits.append("evasive")
        if npc.temperament == "cheerful":
            traits.append("cheerful")
        elif npc.temperament == "melancholy":
            traits.append("tired")
        elif npc.temperament == "cold":
            traits.append("guarded")

        trait_str = ", ".join(traits) if traits else "ordinary"
        return (f"You are {npc.name}, a {npc.age}-year-old {npc.occupation}. "
                f"You are {trait_str}. You're a normal person going about your day. "
                f"You can answer simple questions, give directions, share local gossip, "
                f"or complain about the weather. You don't have secrets or deep wisdom. "
                f"Keep responses to 1-2 sentences. Talk like a real person, not a quest-giver.")

    def _call_npc_model(self, npc: NPC, player_message: str,
                        npc_context: str) -> str:
        """
        Call the appropriate model for this NPC's dialogue.
        Model tier is based on their depth score.
        """
        try:
            from app.ai.models import call_npc_model
            # Fix #19: call_npc_model expects (npc, system_prompt, conversation_context)
            response = call_npc_model(npc, npc.system_prompt, npc_context + "\n\nPlayer says: " + player_message)
            if response:
                return response
        except Exception as e:
            log_crash("call_npc_model", "turn={}".format(getattr(getattr(self, "state", None), "turn_number", "?")), e, "used fallback")
            pass

        # Fallback: generate a simple response based on NPC personality
        return self._fallback_npc_response(npc, player_message)

    def _fallback_npc_response(self, npc: NPC, player_message: str) -> str:
        """Generate a basic NPC response without a model."""
        depth = npc.stats.depth_score()
        temperament = npc.temperament

        if depth < 25:
            responses = [
                f"'{npc.name} shrugs.'",
                "Hm.",
                "Don't know much about that.",
                "You'd have to ask someone else.",
            ]
        elif depth < 50:
            responses = [
                "I suppose so.",
                "Interesting. Can't say I've thought about it much.",
                "Ask around the " + ("market" if npc.occupation == "merchant" else "tavern") + ".",
                "What's it to you?",
            ]
        else:
            responses = [
                "That's... a complicated question.",
                "I've wondered about that myself.",
                f"Sit down. This might take a while to explain.",
                "You're not the first to ask. Probably won't be the last.",
            ]

        # Adjust for temperament
        if temperament == "cold":
            responses = [r.replace("I suppose", "Hmph. Perhaps") for r in responses]
        elif temperament == "cheerful":
            responses = [r.replace("What's it to you?", "Ha! Good question!") for r in responses]

        return random.choice(responses)

    # --- Persuasion ---
    def _handle_persuasion(self, npc: NPC, action: Action):
        """Run the persuasion engine when the player is trying to convince an NPC."""
        try:
            from app.engine.social import calculate_persuasion_delta
            # Fix #5: calculate_persuasion_delta expects (evaluation_scores_dict, npc, relationship)
            evaluation_scores = {"relevance": 0.5, "coherence": 0.7, "tone_match": 0.5, "info_valid": 1.0}
            delta = calculate_persuasion_delta(evaluation_scores, npc, npc.relationship)
            if npc.relationship:
                npc.relationship.persuasion_progress += delta
        except Exception as e:
            log_crash("calculate_persuasion_delta", "turn={}".format(getattr(getattr(self, "state", None), "turn_number", "?")), e, "used fallback")
            pass

    # --- Deception check ---
    def _handle_deception_check(self, npc: NPC, action: Action):
        """Check if the NPC detects the player's lie."""
        try:
            from app.engine.perception import detect_lie
            # Fix #6: detect_lie expects (player, npc, lie_severity_int)
            detected = detect_lie(self.state.player, npc, 50)
            if detected and npc.relationship:
                npc.relationship.trust -= 15
                npc.relationship.flags.append("caught_lying")
        except Exception as e:
            log_crash("detect_lie", "turn={}".format(getattr(getattr(self, "state", None), "turn_number", "?")), e, "used fallback")
            # Simple fallback: compare player honesty vs NPC perception
            if npc.stats.perception > self.state.player.stats.charisma:
                if npc.relationship:
                    npc.relationship.trust -= 10

    # ============================================================
    # TRAVEL (multi-day movement between cities)
    # ============================================================

    def handle_travel(self, destination_id: str):
        """
        Handle multi-day travel between distant locations.
        Fast-forwards through travel days with interruption checks.
        """
        world = self.state.world
        player = self.state.player

        # Find the road
        road = None
        for r in world.roads:
            if ((r.from_id == player.location and r.to_id == destination_id) or
                    (r.to_id == player.location and r.from_id == destination_id)):
                road = r
                break

        if not road:
            self.ui.show_system("There's no known route to that destination.")
            return

        days = int(road.travel_days_foot)
        self.ui.show_system(f"Traveling to {destination_id}... ({days} days)")

        for day in range(days):
            # Show travel narration
            try:
                from app.ai.narrator import narrate_travel_summary
                # Fix #12: narrate_travel_summary expects a single dict
                summary = narrate_travel_summary({
                    "day": day + 1, "total_days": days,
                    "terrain": road.terrain, "weather": "clear"
                })
                self.ui.show_narration(summary)
            except Exception as e:
                log_crash("narrate_travel_summary", "turn={}".format(getattr(getattr(self, "state", None), "turn_number", "?")), e, "used fallback")
                self.ui.show_narration(f"Day {day + 1} of travel. The {road.terrain} stretches on.")

            # Advance time (one full day)
            for _ in range(5):  # 5 time slots = 1 day
                world.advance_time_slot()

            # Hunger and fatigue increase
            player.hunger = min(100, player.hunger + 15)
            player.fatigue = min(100, player.fatigue + 10)

            # Check for travel event
            try:
                from app.engine.movement import roll_travel_event
                # Fix #23: roll_travel_event expects (road, player, day_number)
                event = roll_travel_event(road, player, day + 1)
                if event:
                    self.ui.show_narration(f"Something happens on the road...")
                    # Drop into normal play for the event
                    return  # let the main loop handle it
            except Exception as e:
                log_crash("roll_travel_event", "turn={}".format(getattr(getattr(self, "state", None), "turn_number", "?")), e, "used fallback")
                # Random event chance
                if random.random() < road.danger_rating / 200:
                    self.ui.show_narration(
                        "You hear movement in the trees ahead. Something is out there.")
                    return

        # Arrived safely
        player.location = destination_id
        loc = world.locations.get(destination_id)
        if loc:
            self.ui.show_narration(f"You arrive at {loc.name}.")
        player.days_alive += days

    # ============================================================
    # TIME AND DIRECTOR
    # ============================================================

    def _advance_time(self):
        """Advance one time slot and apply time-based effects."""
        self.state.world.advance_time_slot()
        player = self.state.player

        # Hunger and thirst tick up
        player.hunger = min(100, player.hunger + 3)
        player.thirst = min(100, player.thirst + 4)

        # Fatigue ticks up slightly
        player.fatigue = min(100, player.fatigue + 2)

        # Fix #26: only decrement injury days_remaining at dawn (once per day)
        healed = []
        remaining = []
        for inj in player.injuries:
            if hasattr(inj, 'days_remaining') and inj.days_remaining > 0:
                if self.state.world.time_slot == "dawn":
                    inj.days_remaining -= 1
                if inj.days_remaining <= 0:
                    healed.append(inj)
                    continue
            remaining.append(inj)
        player.injuries = remaining

        if healed and self.ui:
            names = [i.name for i in healed]
            self.ui.show_system(f"Healed: {', '.join(names)}")

        # --- Wired systems (P2 fixes) ---
        # Trust/attraction decay for NPCs with relationships
        for npc in self.state.world.npcs.values():
            if npc.relationship and npc.relationship.trust < GAME_CONSTANTS.get("trust_no_decay_threshold", 60):
                decay = (GAME_CONSTANTS.get("trust_decay_companion", 0.5) if npc.is_companion
                         else GAME_CONSTANTS.get("trust_decay_npc", 0.1))
                npc.relationship.trust = max(-100, npc.relationship.trust - decay)

        # Economy tick at dawn (production, trade, prosperity)
        if self.state.world.time_slot == "dawn":
            try:
                from app.engine.economy_sim import tick_economy
                tick_economy(self.state.world)
            except Exception as e:
                log_crash("tick_economy", f"day={self.state.world.current_day}", e, "skipped")

        # NPC life simulation at dawn (NPCs move, hear news, talk to each other)
        if self.state.world.time_slot == "dawn":
            try:
                from app.engine.npc_life import update_npc_lives
                update_npc_lives(self.state.world)
            except Exception as e:
                log_crash("update_npc_lives", f"day={self.state.world.current_day}", e, "skipped")

        # Food consumption at dawn
        if self.state.world.time_slot == "dawn":
            food_words = ["food", "ration", "meat", "bread", "cheese", "fruit", "dried"]
            food_items = [item for item in player.inventory
                          if any(w in item.lower() for w in food_words)]
            if food_items and player.hunger > 20:
                player.inventory.remove(food_items[0])
                player.hunger = max(0, player.hunger - 30)

    def _run_director(self):
        """Run the Director to generate daily world events."""
        try:
            from app.engine.director import prepare_director_context, apply_director_events
            from app.ai.models import call_model

            # Fix #9: prepare_director_context returns a string for the Director AI
            # Then we call the director model with that context and apply events
            director_context = prepare_director_context(self.state.world, self.state.player)
            director_system_prompt = (
                "You are the Director of a text RPG world. Generate 1-3 daily events as JSON. "
                "Each event is a dict with 'type', 'target', 'description'. "
                "Types: npc_move, conflict_update, rumor, weather, npc_fate_change. "
                "Keep events plausible and interesting. Return a JSON list."
            )
            events = call_model("director", director_system_prompt, director_context, json_mode=True)
            if events and isinstance(events, list):
                apply_director_events(events, self.state.world)
        except Exception as e:
            log_crash("call_model", "turn={}".format(getattr(getattr(self, "state", None), "turn_number", "?")), e, "used fallback")
            pass  # Director is optional — world just stays quieter

    # ============================================================
    # DEATH
    # ============================================================

    def _handle_death(self, cause: str):
        """Handle player death — narrate it, show epilogue, end the game."""
        self.state.game_over = True
        self.state.death_reason = cause

        # Try to narrate the death
        try:
            from app.ai.narrator import narrate_death
            # Fix #13: narrate_death expects (death_context_dict, world_state_dict)
            player = self.state.player
            world = self.state.world
            death_context = {
                "cause": cause,
                "location": player.location,
                "days_alive": player.days_alive,
                "kills": player.kills,
            }
            world_state = {
                "world_name": world.name,
                "day": world.current_day,
                "season": world.season,
                "active_conflicts": len(world.active_conflicts),
            }
            death_text = narrate_death(death_context, world_state)
            self.ui.show_combat(death_text)
        except Exception as e:
            log_crash("narrate_death", "turn={}".format(getattr(getattr(self, "state", None), "turn_number", "?")), e, "used fallback")
            self.ui.show_combat(f"\nYou have died. Cause: {cause}.")

        # Show a brief epilogue
        self.ui.show_system(f"\n--- GAME OVER ---")
        self.ui.show_system(f"Days survived: {self.state.player.days_alive}")
        self.ui.show_system(f"Turns played: {self.state.turn_number}")

        if self.state.flagged_moments:
            self.ui.show_system("\nMoments that mattered:")
            for moment in self.state.flagged_moments[-5:]:
                self.ui.show_system(f"  - {moment.get('description', '...')}")

        flag_moment(self.state, f"Died: {cause}", "death")

    # ============================================================
    # DISPLAY
    # ============================================================

    def _display_result(self, action: Action, narration: str, engine_result: dict):
        """Show the turn's result to the player."""
        result_type = engine_result.get("type", "generic")

        # Show narration (the prose description of what happened)
        if narration:
            if result_type == "combat":
                self.ui.show_combat(narration)
            else:
                self.ui.show_narration(narration)

        # Show NPC dialogue separately (it has its own style)
        if result_type == "dialogue":
            npc_name = engine_result.get("npc_name")
            npc_response = engine_result.get("response", "")
            if npc_name and npc_response:
                self.ui.show_npc_dialogue(npc_name, npc_response)

    def _show_initial_scene(self):
        """Show the opening scene when the game starts."""
        scene = assemble_scene_context(self.state)

        # Try to get a narrated introduction
        try:
            from app.ai.narrator import narrate
            intro_action = Action(type="observation", intent="look around at your surroundings")
            # Fix #14: narrate expects (scene_context, action, engine_result)
            intro = narrate(scene,
                            intro_action,
                            {"type": "observation", "description": "The player looks around."})
            if intro:
                self.ui.show_narration(intro)
                return
        except Exception as e:
            log_crash("narrate", "turn={}".format(getattr(getattr(self, "state", None), "turn_number", "?")), e, "used fallback")
            pass

        # Fallback: show the raw scene context
        self.ui.show_narration(scene)

    def _show_status(self):
        """Show the status bar if we have a player."""
        if self.state.player:
            self.ui.show_status_bar(self.state.player, self.state.world)

    # ============================================================
    # SPECIAL COMMANDS
    # ============================================================

    def _handle_special_command(self, raw_input: str) -> bool:
        """
        Handle meta-commands like inventory, save, quit.
        Returns True if the input was a command (so we skip the normal turn).
        """
        cmd = raw_input.strip().lower()

        if cmd == "inventory" or cmd == "i":
            self.ui.show_inventory(self.state.player)
            return True

        elif cmd == "status" or cmd == "stats":
            self._show_player_status()
            return True

        elif cmd == "companions" or cmd == "party":
            self._show_companions()
            return True

        elif cmd == "save":
            self._save_game()
            return True

        elif cmd == "quit" or cmd == "exit":
            self._quit_game()
            return True

        elif cmd == "help" or cmd == "?":
            self._show_help()
            return True

        elif cmd == "map":
            self._show_map()
            return True

        return False

    def _show_player_status(self):
        """Show detailed player stats."""
        p = self.state.player
        self.ui.show_system(f"\n  {p.name}")
        self.ui.show_system(f"  Health: {p.health}/100  Hunger: {p.hunger}  "
                            f"Fatigue: {p.fatigue}")
        self.ui.show_system(f"  Weapon: {WEAPONS.get(p.weapon, {}).get('display', p.weapon)}  "
                            f"Armor: {ARMOR.get(p.armor, {}).get('display', p.armor)}")
        self.ui.show_system(f"  Coins: {p.coins}")
        self.ui.show_system(f"  Days alive: {p.days_alive}  Kills: {p.kills}")
        if p.injuries:
            names = [i.name if hasattr(i, 'name') else str(i) for i in p.injuries]
            self.ui.show_system(f"  Injuries: {', '.join(names)}")

    def _show_companions(self):
        """Show companion status."""
        player = self.state.player
        world = self.state.world

        if not player.companions:
            self.ui.show_system("You travel alone.")
            return

        companions = []
        for comp_id in player.companions:
            npc = world.npcs.get(comp_id)
            if npc:
                companions.append(npc)

        self.ui.show_companion_status(companions)

    def _save_game(self):
        """Save the current game."""
        try:
            filepath = "saves/save.json"
            save_game(self.state, filepath)
            self.ui.show_system(f"Game saved to {filepath}")
        except Exception as e:
            self.ui.show_system(f"Failed to save: {e}")

    def _quit_game(self):
        """Quit the game (with save prompt)."""
        self.ui.show_system("Save before quitting? (y/n)")
        response = self.ui.get_input()
        if response and response.strip().lower() in ("y", "yes"):
            self._save_game()
        self.state.game_over = True
        self.ui.show_system("Farewell.")

    def _show_help(self):
        """Show available commands."""
        self.ui.show_system("\n  Commands:")
        self.ui.show_system("  inventory / i   — View your inventory and equipment")
        self.ui.show_system("  status / stats  — View your character stats")
        self.ui.show_system("  companions      — View companion status")
        self.ui.show_system("  map             — View known locations")
        self.ui.show_system("  save            — Save the game")
        self.ui.show_system("  quit / exit     — Quit the game")
        self.ui.show_system("  help / ?        — Show this message")
        self.ui.show_system("\n  Otherwise, just type what you want to do.")

    def _show_map(self):
        """Show known locations."""
        world = self.state.world
        player = self.state.player
        current = world.locations.get(player.location)

        self.ui.show_system(f"\n  You are in: {current.name if current else 'unknown'}")

        # Show parent and sibling locations
        if current:
            parent = world.get_parent_location(current.id)
            if parent:
                self.ui.show_system(f"  Within: {parent.name}")
                # Show siblings (other locations at the same level)
                siblings = [world.locations[cid] for cid in parent.children_ids
                            if cid in world.locations and cid != current.id]
                if siblings:
                    self.ui.show_system("  Nearby:")
                    for sib in siblings[:10]:
                        self.ui.show_system(f"    - {sib.name} ({sib.type})")

            # Show children (places you can go deeper into)
            if current.children_ids:
                children = [world.locations[cid] for cid in current.children_ids
                            if cid in world.locations]
                if children:
                    self.ui.show_system("  Inside here:")
                    for child in children[:10]:
                        self.ui.show_system(f"    - {child.name} ({child.type})")

    # ============================================================
    # WEB API METHODS — used by server.py for the HTML frontend
    # These process turns without a terminal UI.
    # ============================================================

    def get_initial_scene(self) -> str:
        """Get the opening narration for a new game. No UI calls."""
        from app.crash_log import clear_log
        clear_log()
        scene = assemble_scene_context(self.state)
        try:
            from app.ai.narrator import narrate
            action = Action(type="observation", intent="look around at your surroundings")
            intro = narrate(scene, action,
                            {"type": "observation", "description": "The player arrives and looks around."})
            if intro:
                return intro
        except Exception:
            pass
        return scene

    def process_action(self, raw_input: str) -> dict:
        """Process freeform text from the web frontend. Returns result dict."""
        response = {"narration": "", "dialogue": None, "combat_text": None,
                    "system": [], "death": None}

        # Save command
        if raw_input.strip().lower() == "save":
            try:
                save_game(self.state, "saves/save.json")
                response["system"].append("Game saved.")
            except Exception as e:
                response["system"].append(f"Save failed: {e}")
            response["state"] = self.get_state_for_ui()
            return response

        # Interpret the freeform text into a structured action
        scene_context = assemble_scene_context(self.state)
        action = self._interpret_input(raw_input, scene_context)
        return self._finish_turn(action, scene_context, response)

    def process_button(self, action_type: str, target_id: str = "") -> dict:
        """Process a button click — skips interpreter (saves API calls)."""
        response = {"narration": "", "dialogue": None, "combat_text": None,
                    "system": [], "death": None}

        type_map = {
            "move": "movement", "talk": "dialogue", "attack": "combat",
            "observe": "observation", "rest": "rest", "trade": "trade",
            "stealth": "stealth",
        }
        action = Action(
            type=type_map.get(action_type, "action"),
            target=target_id,
            involves_combat=(action_type == "attack"),
            raw_input=f"{action_type} {target_id}".strip(),
            intent=f"{action_type} {target_id}".strip(),
        )

        scene_context = assemble_scene_context(self.state)
        return self._finish_turn(action, scene_context, response)

    def _finish_turn(self, action: Action, scene_context: str, response: dict) -> dict:
        """Shared turn processing for both text and button inputs."""
        # Intervention check
        check_text = f"{action.intent} {action.raw_input} {action.manner} {action.type}".lower()
        for trigger in INTERVENTION_TRIGGERS:
            if trigger in check_text:
                response["combat_text"] = random.choice(INTERVENTION_RESPONSES)
                if self.state.player:
                    self.state.player.health = 0
                response["death"] = {"cause": "the world's swift justice"}
                self.state.game_over = True
                response["state"] = self.get_state_for_ui()
                return response

        # Route action to engine
        engine_result = self._route_action(action)

        # Narrate
        narration = self._narrate_result(action, engine_result, scene_context)
        response["narration"] = narration

        # Pull out NPC dialogue if present
        if engine_result.get("type") == "dialogue":
            speaker = engine_result.get("npc_name")
            text = engine_result.get("response", "")
            if speaker and text:
                response["dialogue"] = {"speaker": speaker, "text": text}

        # Pull out combat info
        if engine_result.get("type") == "combat":
            response["combat_result"] = {
                "result": engine_result.get("result", ""),
                "enemy": engine_result.get("enemy_name", ""),
            }

        # Update game state
        self.state.turn_number += 1
        log_action(self.state, self.state.turn_number,
                   action.raw_input, str(engine_result), narration)

        # Time advancement (every 5-10 actions)
        self.action_count_since_time += 1
        if self.action_count_since_time >= random.randint(5, 10):
            self._advance_time()
            self.action_count_since_time = 0

        # Director events (once per day)
        if self.state.world.current_day > self.last_director_day:
            self._run_director()
            self.last_director_day = self.state.world.current_day

        # Summarize old logs periodically
        summarize_every = GAME_CONSTANTS.get("summarize_every_n_turns", 10)
        if self.state.turn_number % summarize_every == 0:
            run_summarizer(self.state)

        # Death check
        if self.state.player and self.state.player.health <= 0:
            response["death"] = {"cause": "injuries"}
            self.state.game_over = True

        response["state"] = self.get_state_for_ui()
        return response

    def get_state_for_ui(self) -> dict:
        """Build current game state as a dict for the frontend side panels."""
        player = self.state.player
        world = self.state.world
        if not player:
            return {"error": "no_player"}

        loc = world.locations.get(player.location)
        parent = world.get_parent_location(player.location) if loc else None

        # Nearby locations (children, parent, siblings)
        nearby = []
        if loc:
            for cid in loc.children_ids:
                child = world.locations.get(cid)
                if child:
                    nearby.append({"id": cid, "name": child.name,
                                   "type": child.type, "dir": "inside"})
            if loc.parent_id:
                p = world.locations.get(loc.parent_id)
                if p:
                    nearby.append({"id": p.id, "name": p.name,
                                   "type": p.type, "dir": "outside"})
                    for sid in p.children_ids:
                        if sid != loc.id:
                            sib = world.locations.get(sid)
                            if sib:
                                nearby.append({"id": sid, "name": sib.name,
                                               "type": sib.type, "dir": "nearby"})

        # NPCs at this location (observable traits, not raw numbers)
        npcs_here = world.npcs_at_location(player.location)

        # Auto-populate with ambient NPCs if location has population but few NPCs
        # Tavern (pop 25) → ~7 people. Market (pop 150) → ~10. Town square → ~12.
        import math as _math
        if loc and loc.population > 0 and len(npcs_here) < 8:
            target = min(12, max(4, int(_math.log2(max(1, loc.population)) * 1.5)))
            ambient_count = target - len(npcs_here)
            for _ in range(max(0, ambient_count)):
                ambient = self._generate_ambient_npc()
                npcs_here.append(ambient)

        npc_list = [self._npc_display(n) for n in npcs_here]

        # Companions
        comp_list = []
        for cid in player.companions:
            cnpc = world.npcs.get(cid)
            if cnpc:
                comp_list.append({
                    "name": cnpc.name, "health": cnpc.stats.health,
                    "trust": cnpc.relationship.trust if cnpc.relationship else 0,
                    "mood": cnpc.temperament,
                })

        # Hired units
        unit_list = []
        for uid in player.hired_units:
            unit = world.units.get(uid)
            if unit and unit.count > 0:
                unit_list.append({
                    "id": unit.id, "name": unit.name, "type": unit.unit_type,
                    "count": unit.count, "morale": unit.morale,
                    "weapon": WEAPONS.get(unit.weapon, {}).get("display", unit.weapon),
                    "armor": ARMOR.get(unit.armor, {}).get("display", unit.armor),
                    "cost_per_day": unit.daily_upkeep(),
                })

        return {
            "player": {
                "name": player.name,
                "health": player.health,
                "hunger": player.hunger,
                "thirst": player.thirst,
                "fatigue": player.fatigue,
                "weapon": WEAPONS.get(player.weapon, {}).get("display", player.weapon),
                "armor": ARMOR.get(player.armor, {}).get("display", player.armor),
                "coins": player.coins,
                "inventory": player.inventory,
                "days_alive": player.days_alive,
                "kills": player.kills,
                "injuries": [{"name": i.name, "severity": i.severity}
                             for i in player.injuries if hasattr(i, "name")],
                "stats": player.stats.to_dict(),
                "companions": comp_list,
                "hired_units": unit_list,
                "knowledge": player.knowledge_log[-20:],
            },
            "location": {
                "id": loc.id if loc else "",
                "name": loc.name if loc else "???",
                "type": loc.type if loc else "",
                "description": loc.description if loc else "",
                "parent": parent.name if parent else None,
                "population": loc.population if loc else 0,
            },
            "nearby": nearby,
            "npcs": npc_list,
            "time": {
                "slot": world.time_slot,
                "day": world.current_day,
                "season": world.season,
            },
            "turn": self.state.turn_number,
            "game_over": self.state.game_over,
        }

    def _npc_display(self, npc) -> dict:
        """Build display info for an NPC — observable traits, no raw numbers."""
        # Name: real name if met, appearance/occupation if not
        if npc.met_player:
            display_name = npc.name
        else:
            age = "young" if npc.age < 25 else "middle-aged" if npc.age < 50 else "older"
            display_name = f"A {age} {npc.occupation}"

        # Physical build (what you can see looking at them)
        combined = (npc.stats.strength + npc.stats.toughness) / 2
        if combined < 30:
            build = "slight"
        elif combined > 80:
            build = "imposing"
        elif combined > 65:
            build = "sturdy"
        else:
            build = ""  # average, nothing notable

        # Threat level (you can size someone up by looking at them)
        cpr = npc.stats.combat_power()
        tier_mult = ENTITY_TIER_MULTIPLIERS.get(npc.power_tier, 1.0)
        effective = cpr * tier_mult
        if effective < 25:
            threat = "harmless"
        elif effective < 45:
            threat = "capable"
        elif effective < 65:
            threat = "dangerous"
        else:
            threat = "deadly"

        # Fate tier — exponentially distributed rarity
        # common=grey, uncommon=green, rare=blue, epic=purple, legendary=gold, mythic=crimson
        fate = npc.fate
        if fate >= 0.85:   fate_tier = "mythic"
        elif fate >= 0.70: fate_tier = "legendary"
        elif fate >= 0.50: fate_tier = "epic"
        elif fate >= 0.30: fate_tier = "rare"
        elif fate >= 0.15: fate_tier = "uncommon"
        else:              fate_tier = "common"

        return {
            "id": npc.id, "name": display_name, "occupation": npc.occupation,
            "build": build, "threat": threat, "temperament": npc.temperament,
            "met": npc.met_player, "alive": npc.is_alive,
            "relationship": npc.relationship.stage if npc.relationship else "stranger",
            "fate_tier": fate_tier,
        }
