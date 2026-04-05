# Untitled AI RPG — Architecture

The technical blueprint. How every system works, why, and how they connect.

---

## 1. Core Principle: Models Speak, Python Thinks

Every decision in this architecture follows one rule: **the AI models generate language, Python runs the simulation.** No model ever decides if you live or die. No model tracks your location. No model does math. Python handles all state, all logic, all spatial reasoning, all combat resolution. Models do exactly three things: interpret player input, voice characters, and narrate outcomes.

This isn't a chatbot with game flavor. It's a simulation engine with an AI narration layer.

---

## 2. Multi-Model Architecture

Different roles get different models based on what the job demands.

| Role | Job | Model Tier | Why |
|------|-----|-----------|-----|
| **Interpreter** | Parse player free-text into structured action JSON | Flash Lite / Haiku | Cheapest. Just extracting intent, not generating prose. |
| **Narrator** | Describe scenes, narrate combat, convey outcomes | Sonnet | Best prose quality at reasonable cost. |
| **Active NPCs** | Dialogue when player talks to someone | Tiered (see NPC system) | Model tier = character's soul. |
| **Character Author** | Write NPC system prompts from stat blocks | Opus | One-time per NPC. Translates numbers into personality. |
| **Director** | Background world events, NPC movement, consequences | Flash | 1x per in-game day. Cheap but coherent. |
| **Antagonist** | Strategic opposition, troop planning, schemes | Reasoning model (o4-mini) | Needs multi-step planning, not prose. |
| **World Generator** | Create the world bible at game start | Opus / GPT-5 | One big call. Lore, factions, history, philosophy. |
| **Stat Engine** | Everything mathematical | Python | Free. Deterministic. Reliable. |

**Key insight:** The player never knows which model is running. Conversations just *feel* more alive when they matter. A barkeeper giving directions uses Flash Lite. A companion confessing betrayal uses Opus. The shift is invisible.

---

## 3. The Spatial Tree (World Structure)

The world is a **hierarchical tree**, not a flat list. Generated top-down, on demand.

```
World
  Continent (4)
    Region (3-5 per continent)
      City (2-8 per region)
        District (2-5 per city)
          Building (10-50 per district)
            Floor (1-5 per building)
              Room (1-10 per floor)
```

### What Gets Generated When

| Level | When | How | Cost |
|-------|------|-----|------|
| World + Continents + Regions + Cities | Game start | One Opus call → structured JSON. Python places on coordinate grid. | ~$0.30 |
| City details (buildings, districts) | First visit | Python + weighted random tables, or one Flash call | ~$0.01 |
| Building interiors | When you enter | Python spawns rooms from templates | Free |
| Room contents + NPCs | When you enter a room | Python selects NPCs appropriate to location/time | Free |

### Location Is a Single Field

Every entity in the game (player, NPCs, items) has **one location field**: a node ID in the tree. Not a boolean for every possible location. When you walk into a room, Python queries: "which NPCs have `location == this_room`?" Millisecond lookup, not a model call.

```python
# NOT this (2000 booleans per character):
npc.in_tavern_12 = False
npc.in_temple_3 = True

# THIS (one field):
npc.location = "tessam_ironDrum_f2_backroom"
```

### Proximity Is a Query, Not a Stat

- "Who's in my room?" → filter on exact location match
- "Who's in my building?" → filter one level up in the tree
- "Who's nearby in town?" → filter at district/city level
- "Who's approaching from another city?" → Director's job, once per game-day

### Map Rendering

The spatial tree IS the map data. Rendering options:
- **ASCII terminal** — fits the text RPG aesthetic perfectly
- **matplotlib/Pillow** — 2D rendered map, nodes for cities, lines for roads, color by faction
- **Browser-based** — Canvas/D3.js/Leaflet if frontend goes web
- **Terrain generation** — Perlin/Simplex noise for coastlines and mountains, cities placed on valid terrain

The model creates *meaning* (Opus: "Tessam is a trade port on an archipelago"). Python creates *space* (coordinates (347, 891), coastal tile, elevation 2, connected to roads 14 and 22).

---

## 4. NPC Tier System

The defining feature. NPCs exist on a spectrum from inert data to literary characters.

### Tier 0 — Stat Block (Dormant)

The 40 people in a bar. Pure data. No model call. ~20-30 stats each, randomly generated, skewing low (most people are ordinary). The narrator mentions "a crowded bar, dockworkers arguing over dice" — that's it. They're scenery.

```python
{
    "id": "npc_4821",
    "name": "Maren Voss",
    "age": 34,
    "location": "tessam_ironDrum_f1_main",
    "appearance": {"height": 168, "build": "stocky", "hair": "dark"},
    "stats": {
        "strength": 55, "toughness": 60, "agility": 35,
        "intelligence": 42, "depth": 28, "wisdom": 35,
        "charisma": 40, "courage": 50, "empathy": 45,
        "education": 20, "perception": 55, "willpower": 48,
        "temperament": "calm", "social_class": "working",
        "occupation": "dockworker"
    },
    "flags": []  # gets populated on interaction
}
```

### Tier 1 — Active NPC (Promoted on Interaction)

The moment you talk to someone, they get promoted. Python takes their stat block and makes one model call to generate a 200-500 token context prompt consistent with their stats and local lore. Now they're a person.

If you walk away, they **demote back to Tier 0**, but with flags: `["met_player", "got_punched", "holds_grudge"]`. Cheap to store. Meaningful later.

### Tier 2 — Dramatic Character

Key NPCs, companions, major antagonist figures. Full backstory, secrets, internal contradictions, philosophical leanings. 800-1500 token system prompts. Written by Opus at creation time.

### The Depth Score → Model Tier Mapping

Sum of intelligence + depth + wisdom + emotional complexity + education (5-6 relevant stats) = **depth score**.

| Depth Score Percentile | Model | Prompt Size | What It Feels Like |
|----------------------|-------|------------|-------------------|
| Bottom 60% | Flash Lite | 50-100 tokens | Three-word answers about the weather |
| Next 25% | Flash | 200-300 tokens | Normal conversation, basic personality |
| Next 10% | Sonnet | 400-600 tokens | Unexpectedly interesting, has opinions |
| Top 5% | Sonnet | 800+ tokens | Memorable, makes you think |
| Top 1% (1-2 per city) | Opus | 1500+ tokens | Feels like talking to a real person |

**Response length scales too.** A shallow character gives you a sentence. A deep character gives you a paragraph. An Opus character sometimes gives you three paragraphs unprompted because they have something to say.

### Opus as Character Author

The stat-to-prompt pipeline is NOT a lookup table. "Depth 70" means nothing to a template. It means something to Opus.

Opus reads the full stat block and writes the system prompt. It looks at `depth: 70, intelligence: 45, emotional_vulnerability: 88, education: 30` and synthesizes: *"She's perceptive about people but not intellectual about it. She never went to school but reads a room better than anyone. She speaks simply but notices things others miss."*

The difference between 55 and 70 isn't linear. It's qualitative. A model translates numbers into vibes. Cheaper models then *perform* the prompt Opus wrote.

### The Magic Moment

The quiet woman washing clothes by the river. You almost walk past. You say something offhand. She responds with something that stops you cold. Because she rolled 92 on depth but low on social visibility. She's not a queen or a wizard. She's just a person with a rich inner life who happened to end up doing laundry. **That's the moment that feels like literature.**

---

## 5. The Game Loop (Per Turn)

```
1. Player types free text
     ↓
2. INTERPRETER (Flash Lite) → structured action JSON
   {"action": "move", "target": "building_14", "intent": "enter"}
   {"action": "talk", "target": "npc_4821", "topic": "the war"}
   {"action": "attack", "target": "npc_892", "method": "punch"}
     ↓
3. STAT ENGINE (Python) resolves consequences
   - Update player location
   - Query NPCs at new location
   - Roll combat if needed
   - Check for Director events
   - Update relationship scores
     ↓
4. SCENE ASSEMBLY (Python) builds narrator context
   - Room description (from spatial tree)
   - Present NPCs (name + brief descriptors)
   - Combat outcome (if any)
   - Relevant world events
   - ~300-500 tokens of assembled context
     ↓
5. NARRATOR (Sonnet) writes the scene
   or NPC MODEL (tiered) voices the character
     ↓
6. Display to player. Loop.
```

**Minimum calls per turn:** 2 (interpreter + narrator). Dramatic scenes with NPCs might be 3-4 calls. Combat is 2 (Python resolves, Sonnet narrates).

---

## 6. Combat Engine (Auto-Resolve)

**Not turn-based.** The player doesn't click "attack" repeatedly. They decide to fight, Python resolves the entire encounter instantly, and Sonnet writes the scene.

### Input Stats

- Player: strength, agility, weapon type, weapon quality, armor type, health, fatigue
- Enemy: same stats
- Companions: combat skill, obedience, courage, trust (determines if they follow orders)
- Context: terrain, numbers advantage, sneak attack boolean, weather

### Weapon-Armor Matrix

|  | Unarmored | Leather | Chain | Plate |
|--|-----------|---------|-------|-------|
| **Sword** | Excellent | Good | Fair | Poor |
| **Club/Mace** | Good | Good | Good | Good |
| **Spear** | Good | Good | Fair | Fair |
| **Dagger** | Good | Fair | Poor | Terrible |
| **Bow** | Excellent | Good | Fair | Poor |

### Resolution Flow

```python
def resolve_combat(attacker, defender, companions, context):
    # Calculate base hit chance from stats
    # Apply weapon-armor multiplier
    # Apply terrain/sneak/numbers modifiers
    # Roll for each participant
    # Determine injuries, deaths, fleeing
    # Package into structured outcome

    return {
        "result": "victory",        # victory / defeat / fled / standoff
        "margin": "narrow",         # decisive / comfortable / narrow / pyrrhic
        "duration": "prolonged",    # instant / brief / prolonged / grueling
        "player_injuries": ["deep cut left arm"],
        "companions": [
            {"name": "Kael", "status": "alive", "action": "flanked"},
            {"name": "Dara", "status": "dead", "cause": "shield bash to skull"}
        ],
        "enemy_deaths": 3,
        "notable_moments": ["sneak_attack_success", "disarmed_then_recovered"],
        "mood": "desperate"
    }
```

### Narration Scales with Margin

- **Decisive victory** → 2 paragraphs. Clean, efficient.
- **Narrow victory** → Full page. Desperate, ugly, costly.
- **Defeat** → Also narrated. Sometimes the most beautiful writing in the game.
- **Companion death** → Always given weight. Named, mourned.

### Companion Obedience

You tell your companion to sneak attack. Python checks: `trust: 74, obedience: 60, courage: 45`. Maybe they do it. Maybe they freeze. Maybe they fumble. That gets narrated as a character moment — their cowardice or bravery becomes story, not a failed dice roll.

---

## 7. Persuasion & Social System

**The player has no persuasion stat.** The player's actual words are the mechanic. This is what separates the game from every RPG where you click "Persuade [DC 15]."

### NPC Persuadability Dimensions

- **Stubbornness** — base resistance to changing their mind
- **Emotional vulnerability** — susceptibility to emotional appeals
- **Faction loyalty** — how much their allegiance constrains them
- **Trust** (toward player) — built over time through interactions
- **Values** — what they care about (money, honor, family, truth)

### Evaluation Flow

```
Player types argument
     ↓
Interpreter model answers structured questions:
  - Does this address something the NPC actually cares about?
  - Is it logically coherent?
  - Does it reference info the player legitimately has?
  - Is the tone appropriate for this NPC's personality?
     ↓
Python combines with NPC stats:
  trust_score + interaction_history + stubbornness + evaluation
     ↓
Outcome (spectrum, not binary):
  - Full concession
  - Partial concession ("I can't do that, but...")
  - Refusal but trust shifted (next conversation starts warmer)
  - Firm refusal
  - Offense taken (trust decreases)
```

### Trust Over Time

One brilliant sentence doesn't open every door. But ten genuine conversations should open doors that no amount of cleverness in a single exchange could. **The game is harder or easier depending on how emotionally intelligent the player is.** Not their character. *Them.*

### Conversations as Currency

Some doors only open through knowledge. You learned in the tavern that the guard's brother died in the northern campaign. You say: "I heard about your brother. I'm sorry." The interpreter checks: does the player actually have this knowledge (tracked in their knowledge log)? If yes → trust shift. If bluffing → suspicion.

---

## 8. The Director

One cheap model call per in-game day. Reads a compressed world state summary. Outputs 0-3 structured events.

### What the Director Does

- Moves NPCs between locations (the bard from town 1 arrives at yours)
- Advances faction plans (the army marches, the treaty falls apart)
- Creates weather and environmental events
- Spreads consequences (the merchant you cheated is one town closer)
- Spreads reputation (you arrive somewhere new, the bartender already looks nervous)
- Generates ambient events (a festival, a plague, a shipwreck)

### What the Director Never Does

- Resolve combat
- Voice characters
- Override the stat engine
- Make decisions that should be deterministic

### Director Output Schema

```json
{
    "day": 14,
    "events": [
        {
            "type": "npc_movement",
            "npc_id": "npc_102",
            "from": "drava_market",
            "to": "tessam_docks",
            "reason": "seeking revenge on player"
        },
        {
            "type": "faction_advance",
            "faction": "northern_alliance",
            "action": "siege of Kael's Pass begins",
            "world_effect": "trade route closed"
        },
        {
            "type": "reputation_spread",
            "region": "shardcoast",
            "content": "a stranger killed three men in the Iron Drum",
            "sentiment": "fear"
        }
    ]
}
```

---

## 9. Context Management (The Hard Problem)

This is where most AI games fail. Characters namedrop lore constantly. NPCs know things they shouldn't. Context bloats and quality degrades.

### Per-NPC Context Filtering

No NPC gets the full world state. Each gets only what they'd plausibly know:

| NPC Type | Knows | Doesn't Know |
|----------|-------|-------------|
| Peasant | Local gossip, weather, nearby events | Troop movements, politics |
| Merchant | Trade routes, prices, who's buying what | Military strategy |
| Spymaster | Troop movements, political intrigue, secrets | Common gossip (beneath them) |
| Companion | Player's habits, shared experiences | Player's private thoughts, things that happened when they weren't there |
| Antagonist | What scouts report, faction intelligence | Player's exact location (unless tracked) |

### Two-Layer Knowledge System (Tagged Lore Retrieval)

**Layer 1 — Character Prompt (always loaded):** Personality, speech patterns, current mood, immediate knowledge. 300-500 tokens. This is what they "are."

**Layer 2 — Retrievable Lore Index (injected on demand):** The character has tags: `[educated, noble_family, studied_academy_of_vael, skeptic]`. When conversation topics match their tags, the system injects a small relevant lore snippet (50-100 tokens) for that specific response.

The woman at the bar doesn't mention the philosopher until you say something that triggers it. Then the system pulls lore about that philosopher into her context, and she references it naturally. **Knowledge feels organic, not performative.**

### Preventing Context Bloat

From the CCA architecture principles:
- **Trim tool outputs** — if a world query returns 40 fields, only pass the 5 relevant ones to the narrator
- **Structured fact extraction** — pull key facts (names, dates, amounts) into a persistent block, don't rely on summarization
- **Position-aware ordering** — place critical info at the start and end of context (models miss things in the middle)
- **Use `/compact` equivalent** — summarize and reset when context gets stale in long sessions

---

## 10. Ambient Life

The world doesn't wait for the player.

### NPC-to-NPC Conversations

If you sit in a tavern and do nothing, NPCs start talking **to each other**. Not to you. You overhear fragments.

*"...told him the bridge was out but he went anyway..."* and then laughter.

You can:
- **Ignore it** (scenery)
- **Listen closer** (might get noticed, might learn something)
- **Interject** (now you're part of it)

Sometimes fragments are meaningless. Sometimes they're clues. The player learns to pay attention.

### Philosophical Disagreement

Two scholars argue about whether the gods are real. A soldier and a priest debate whether the war is just. The game tracks which positions you endorse. NPCs with matching worldviews trust you faster.

### The Drunk Philosopher

Every world generates one: brilliant but ruined. Alcoholic ex-professor, disgraced court advisor, hermit in the woods. Sonnet-tier minimum. Rich context prompt drawn from real philosophical traditions mapped onto world lore. Hard to find. Hard to earn trust from. Deeply rewarding. **The character players tell their friends about.**

### Silence as a Mechanic

You say something wrong. The game responds: *"She looks at you for a long moment and says nothing."* Let the player sit in that. Most games fill every second. Silence is the most human thing a game can do.

---

## 11. Player Creation

The player can input real traits about themselves:

> *"2024 finance degree, interest in philosophy, Canadian, 5'2, 135 lbs, former wrestler"*

One Opus call maps these onto the world:
- Finance degree → merchant guild apprenticeship
- Philosophy → studied at the Academy of [world equivalent]
- Wrestling → combat training, known for grappling
- Canadian → from a northern coastal region

The player gets a backstory that feels personal because **it's them, refracted through a fantasy lens.** That's a unique selling point no one else offers.

---

## 12. Death & Consequences

### Real Stakes

You can die. You can fail. You can lose. You can be betrayed. If you punch a bard in a crowded bar, maybe 15 dockworkers pile on you and you're dead. Game over. The player thinks: *"Wow. That never happens in any game."*

Or maybe nothing happens because the room hated the bard. The stats decide, not the model.

### Death Letters

When you die, the game generates a short epilogue:
- The war you were fighting — did your side win?
- The companion you traveled with — where did they end up?
- The merchant you cheated — did they recover?

Makes death meaningful instead of "game over, restart."

---

## 13. Visual Pipeline

### Pre-Generation (World Creation, Player Waits 2-5 Min)

- World map image (from spatial tree coordinates)
- 10-20 major NPC portraits
- 4-5 landscape images per region type
- Player character portrait
- ~30-40 image API calls, batched during loading screen with lore text

### City Entry (10-15 Second Transition)

- One establishing shot (cached forever)
- 2-3 key NPC portraits for that location

### Runtime (Instant, No API Call)

Pre-generated asset library: 50-100 character portraits across archetypes, interior scenes, mood variations. Python selects closest match based on scene tags. 80% right instantly beats 100% right after an awkward pause.

### Cinematic Mode (Premium/Optional)

Key moments trigger real image generation with a brief atmospheric pause. Entering a new city. Meeting a major NPC. A dramatic combat outcome. The wait feels intentional, not laggy.

### Tools Available (from Erudite stack)

- Retro Diffusion API — pixel art sprites and portraits
- GPT Image — scene illustrations, maps
- All API keys already in `.sensitive/keys.json`

---

## 14. Economics

| Event | Calls | Cost |
|-------|-------|------|
| Normal turn (move/look) | 2 (interpreter + narrator) | ~$0.005 |
| Conversation turn | 3 (interpreter + NPC + narrator framing) | ~$0.01-0.03 |
| Dramatic scene (2 companions + NPC) | 4-5 calls | ~$0.05-0.08 |
| Combat (resolve + narrate) | 2 (Python + Sonnet) | ~$0.01 |
| Director (daily) | 1 Flash call | ~$0.002 |
| NPC promotion (first interaction) | 1 call (backstory gen) | ~$0.005-0.02 |
| Opus character creation | 1 Opus call | ~$0.05-0.10 |
| World generation | 1 Opus call + spatial math | ~$0.30-0.50 |

**Stress-test the expensive scenario:** A dramatic scene with 2 Sonnet companions, an Opus NPC, the narrator, and the interpreter = 5 calls = maybe $0.10-0.15 per turn. That's the ceiling, not the average.

**Per session (2 hours, ~60 turns):** $0.60-2.00 depending on how social the player is.

---

## 15. Relationship to CCA Architecture Principles

This game IS a multi-agent system. The CCA exam guide's building wisdom applies directly:

- **Agentic loop:** The game loop IS an agentic loop — check result type, route to next action, iterate
- **Hub-and-spoke orchestration:** The game engine is the coordinator; models are subagents with scoped roles
- **Programmatic vs prompt enforcement:** Stats/combat/location = programmatic (deterministic). Dialogue/narration = prompt-based (creative). Never mix them.
- **Structured output schemas:** Every model call returns JSON except narration. The interpreter, director, character author, and combat narrator all have defined schemas.
- **Context management:** The tiered NPC system IS context management. Only pass what's needed. Trim aggressively. Use tagged retrieval, not bloated prompts.
- **Tool distribution:** Each model gets only the context relevant to its role (4-5 "tools" worth of info, not 18)
- **Error propagation:** If a model call fails, the game doesn't crash — Python falls back (generic narration, default NPC response, skip Director event)
- **Independent review:** The Antagonist model is a separate instance from the Narrator — adversarial by design, not self-reviewing

---

## 16. File Structure

```
untitled-rpg/
  CONCEPT.md              — what the game is and why
  ARCHITECTURE.md         — this document
  app/
    main.py               — entry point, game loop
    engine/
      stats.py            — stat definitions, generation, depth scoring
      world.py            — spatial tree, world/city/room generation
      npc.py              — NPC management, tier promotion/demotion
      combat.py           — auto-resolve combat engine
      director.py         — daily world events
      persuasion.py       — social/persuasion evaluation
    ai/
      models.py           — multi-model router (tier → API call)
      interpreter.py      — player text → structured action
      narrator.py         — scene narration
      character_author.py — Opus writes NPC prompts from stats
    game/
      loop.py             — main game loop orchestration
      player.py           — player creation and state
      scene.py            — scene context assembly
  data/
    schemas/              — JSON schemas for world, NPCs, actions, combat
  docs/
    DESIGN.md             — design philosophy and decisions
```
