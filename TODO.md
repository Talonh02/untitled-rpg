# TODO — Next Session Priorities

## Context for Future Claude
This is an AI-powered text RPG prototype. 23 Python files, ~8200 lines. Terminal-based right now, moving to HTML frontend. First playtest happened 2026-04-05 — game runs, narrator prose is good, but the engine barely connects to the game loop. Most "gameplay" is the narrator improvising because the interpreter JSON keeps truncating.

Read these files to understand the project:
- `CONCEPT.md` — what the game is
- `ARCHITECTURE.md` — how systems relate
- `MECHANICS.md` — all the math (formulas, numbers)
- `PLAN.md` — system prompts, model assignments, build order
- `ISSUES.md` — every bug found, status, resolution
- `app/data.py` — all shared data classes

The repo is at github.com/Talonh02/untitled-rpg

---

## P0 — Build HTML Frontend
The terminal is limiting. Build a web frontend served by the Python backend.

**Layout:**
- Left panel: location tree, nearby places (clickable to move), people present (clickable to interact)
- Center: narrative text + NPC dialogue
- Bottom: text input for freeform actions + contextual action buttons (Attack, Talk, Trade, Observe)
- Right panel or tabs: Journal, Map, Inventory, Stats, Lore

**Key principle:** The side panel shows REAL Python state (who's here, what's nearby, your stats). The text input handles anything creative the buttons can't. Buttons are shortcuts, not the whole game.

**Stack:** Python backend (Flask or just http.server), HTML/CSS/JS frontend. Same dark candlelit aesthetic as Erudite (dark bg, gold accents, Fraunces font).

**Features to include:**
- Clickable NPC list (talk/attack/observe)
- Clickable location list (move there, shows travel time)
- Journal tab (logs rumors heard, people met, places visited — grows organically)
- Lore tab (world name, continents, factions, conflicts, religion — generated at world creation)
- Newspaper system (buy at market, shows events from other regions)
- Map tab (even ASCII to start)
- Stats panel (full stat block, not just HP)
- Party display when companions join

## P1 — Fix Interpreter Reliability
ISS-002 is the root cause of most gameplay problems. Gemini Flash returns truncated JSON ~50% of the time.

Options:
1. Use Gemini's structured output / JSON mode (not just json_mode=True on our side)
2. Simplify the JSON schema (fewer fields)
3. Switch interpreter to Anthropic Haiku (more reliable JSON, slightly more expensive)
4. Hybrid: buttons for common actions (no interpreter needed), model only for freeform text

## P2 — Wire Up Missing Systems
From the second adversarial review, these systems exist but aren't connected:
- [ ] `_advance_time` should call `advance_npc_schedules()` — NPCs move on their own
- [ ] `_advance_time` should call trust/attraction decay
- [ ] `_advance_time` should call `consume_food()` — hunger system
- [ ] `_advance_time` should process `reputation_queue` — reputation arrives at cities
- [ ] `handle_travel` is never called — long-distance travel is unreachable
- [ ] `_handle_romance` doesn't call `update_romance()` from social engine
- [ ] Items/dungeons are data models only — nothing creates, places, or interacts with them
- [ ] Power tier is wired into combat CPR but not tested in real gameplay

## P3 — Design Decisions Banked

**Characters:**
- Fate and depth are INDEPENDENT axes (brave dull farm boy vs deep poor poet)
- Fate comes from TWO sources: stat-driven (emerged from rolls) AND role-driven (you're the king, minimum fate 0.7)
- Role tiers drive stat floors (king gets education 50+, general gets courage 70+)
- Education and intelligence should correlate more strongly
- Character dossiers for high-fate NPCs: lineage (parents, grandparents), beliefs (religion, philosophy), mannerisms, formative memories, opinions about other NPCs
- Every NPC gets programmatic background (parents, birthplace, years in town) even if they're nobodies — template-generated, no model call
- Physical descriptions for everyone (eye color, hair, build, distinguishing features) — enough for pixel portrait generation later
- No hardcoded character archetypes (drunk philosopher, corrupt prince) — they should emerge from stat rolls naturally
- NPCs should have opinions about each other (pre-generated relationship web)
- NPCs can be wrong about things (believe something false about the world)

**Combat:**
- Numbers advantage coefficient should be 0.7 not 0.4 (5v1 should be ~2.6x, not ~1.9x)
- Add epic and mythic armor tiers above plate (dragonscale defense 50, mythic defense 75)
- Item tiers: common, quality, rare, epic, legendary, mythic
- Items have names, history, locations, rumors — discoverable through tavern gossip and dungeon exploration
- Combat should auto-resolve in one pass, not let player take 5 separate combat actions
- Player should be able to level up through fiction (drink dragon blood, train with master) not XP

**World:**
- Whole world should run in Python every game-day (NPC schedules, faction scores, economics) — nearly free
- One cheap model call per day generates 3-5 newspaper headlines from world events
- Newspapers buyable at markets or readable on notice boards
- Newspaper sections: politics, war, economics, philosophy
- Oceans as spatial tree nodes, ships as travel mode, sea event table (storms, pirates, travelers)
- Genre logic tree for future: setting × scale × magic level × tone × conflict type × social structure — shelved for now, first build is continental mid-magic medieval

**Player experience:**
- Custom character creation should be loose — traits as seeds not a checklist
- Player should start alone at a tavern, knowing nobody
- No morality meter — world tracks what you DID, not what you ARE
- Small life (staying in one city, being a blacksmith) should be rich and valid
- The world doesn't chase you — epic destiny is there if you seek it
- Player can join any faction including the "bad guys"
- Death is real but telegraphed — game warns you before lethal situations
- Restart as new character in same world after death
- Director should stage events above your tier sometimes — watch two dragons fight from ground level
- Silence as a mechanic (NPC says nothing, let it sit)
- Conversations as currency (knowledge unlocks doors)

**Meta:**
- Build next phase sequentially, testing each path end-to-end. No more 3-agent speed runs.
- The LLM should do LESS than it currently does — Python handles state, movement, combat math, NPC placement. Model only does: interpret freeform text, narrate transitions, voice NPCs, evaluate persuasion, write newspaper
