# Untitled AI RPG — Concept Doc

**Created:** April 5, 2026
**Status:** Ideation → prototyping tomorrow

---

## What It Is

An AI-powered text RPG where the world is generated fresh each playthrough, every character is a persistent AI with its own goals and knowledge, and an adversarial AI actively strategizes against you. Not a chatbot. Not a choose-your-own-adventure. A living world that runs whether you're watching or not.

## What Makes It New

Nothing like this exists. AI Dungeon and competitors are single-model text generators — one AI plays narrator, villain, shopkeeper, and love interest simultaneously. Everything sounds the same. There's no real opposition, no consequences, no world that moves without you.

This game uses multiple AI models architecturally:

| Role | What it does | Model tier |
|------|-------------|-----------|
| **Narrator** | Describes scenes, conveys outcomes, literary voice | Sonnet (best prose) |
| **Active NPCs** | Dialogue, reactions, decisions when in-scene | Flash Lite (cheap, fast, 363 tok/s) |
| **Director** | Background world events, NPC movement, faction advancement, coincidences | Flash (1x per in-game day) |
| **Antagonist** | Strategic opposition — troop movements, schemes, resource allocation | Reasoning model (o4-mini/Grok) |
| **Companions** | Deep personality, secrets, loyalty arcs, emotional weight | Sonnet/GPT-5.4 |
| **Stat Engine** | HP, hunger, travel, combat math, relationships, inventory, time | Python (free) |

Characters seamlessly scale between model tiers based on dramatic importance. A dormant NPC costs nothing. A bartender giving directions uses Flash Lite. A companion confessing a betrayal uses Opus. The player never knows — conversations just feel more alive when they matter.

## Core Architecture

### World as JSON Graph
The world is a graph of 50-200 nodes (cities, camps, ruins, wilderness) with connections, travel times, factions, and resources. Not a visual map — a queryable data structure any model can reason about.

### Stat Engine (Python)
All math lives in code, not in models:
- Hunger, thirst, fatigue (timers)
- Combat resolution (stats + dice + model tactical reasoning)
- Relationship scores (trust, suspicion, attraction, fear, debt) between ALL NPCs
- Faction reputation
- World clock (time passes, NPCs act offscreen)
- Inventory, currency, encumbrance

### The Director
One cheap model call per in-game day. Reads the world state summary. Outputs 0-3 events:
- The bard from town 1 arrives at your current location (convergent paths)
- A storm closes the harbor (weather)
- The merchant you cheated is one town closer (consequences approaching)
- A faction advances its plans (the war doesn't wait for you)

This is the magic. It makes the world feel alive.

### NPC Context Filtering
No NPC gets the full world state. Each gets only what they'd plausibly know:
- A peasant knows local gossip
- A spymaster knows troop movements
- Your companion knows your habits but not your secrets
- The antagonist knows what their scouts have reported

### Genre Agnosticism
The system doesn't know what genre it is. It has NPCs with wants, a world with problems, and a player making choices. Talk to the scarred woman → adventure. Flirt with the musician → romance. Eavesdrop on merchants → intrigue. Pick a fight → combat. The same stat engine handles all of it. Relationship scores drive romance. Faction scores drive politics. Combat stats drive fights. The story emerges from play.

## Economics

**Per-turn cost:** ~$0.01-0.03 (2-4 API calls)
**Per-session (60 turns, ~2 hours):** ~$1-1.50
**Subscription:** $10-15/month
**World generation:** ~$0.50-1.00 (one-time per playthrough)

## What We Already Have (from Erudite)
- Multi-model API orchestration (Claude, GPT, Gemini all wired up)
- Character system with persistent prompts and personality
- Pixel art sprite generation (Retro Diffusion API)
- Scene/environment image generation (GPT Image pipeline)
- API keys for all providers in place
- Frontend design skills (dark aesthetic, typography, atmosphere)

## Competitive Landscape
- **AI Dungeon:** Declining, $4M raised, single-model, no real antagonist, subreddit quarantined
- **Character.AI:** 20M MAU but chat platform, not a game
- **Hidden Door:** $9M raised, social AI storytelling, licensed IP — closest competitor but no adversarial AI
- **NovelAI:** Writing tool, not a game
- **RPGGO:** AI game master but single-model NPCs
- **Nobody** has multi-model adversarial architecture

AI roleplay market: ~$500M-1.2B (2025), projected $8.9B by 2033.

## Key Design Principles
1. Models do reasoning, Python does simulation
2. The world moves without you — consequences compound
3. Characters scale model tier with dramatic importance
4. NPCs only know what they'd plausibly know
5. The system is genre-agnostic — the player decides the story
6. Real stakes — you can die, fail, lose, be betrayed
7. Every playthrough is a new generated world

---

## Name Candidates

1. **Loom** — where threads of story weave together
2. **Hearthless** — no safe home, the world is the game
3. **Candlewax** — stories told by candlelight, they melt and reshape
4. **Thornfield** — evokes Brontë, gothic, a place with secrets
5. **The Pale** — the boundary between known and unknown, an old word for frontier
6. **Inkblood** — text-based, alive, costs something
7. **Fathom** — to understand, to measure depth, the ocean floor
8. **Ironwrit** — iron (hard, real, consequential) + writ (written, decreed, storied)
9. **Wayward** — going your own direction, no rails, no predetermined path
10. **Duskborn** — born at twilight, between worlds, between light and dark

---

## Tomorrow
- Prototype the world generator (JSON graph)
- Prototype the stat engine (Python)
- One test scene: narrator + one NPC + player input loop
- See if it feels alive
