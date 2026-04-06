# NPC AI & Dialogue Systems Research
## Compiled April 5, 2026

---

## 1. Dwarf Fortress Personality System

Three-layered: facets, values/beliefs, goals.

### Facets (0-100, 50 total)
7 severity levels with bell curve (78% land in neutral 40-60, only 0.4% at extremes).
- High ANGER_PROPENSITY → more tantrums
- High STRESS_VULNERABILITY → 50% chance of catatonia
- DISCORD at 91-100 → arguments generate *positive* thoughts
- Facets gate social skill learning: high ASSERTIVENESS always learns Persuader, high CRUELTY blocks Consoler

### Values/Beliefs (-50 to +50, 34 values)
LAW, LOYALTY, FAMILY, FRIENDSHIP, POWER, TRUTH, CUNNING, FAIRNESS, TRADITION, MARTIAL_PROWESS, KNOWLEDGE...
When two dwarves differ by >60 on any value → grudge pressure. Values can change through memories and arguments.

### Stress/Mental Break Cascade
Thoughts accumulate stress. Personality facets filter which events cause stress. Excessive stress → tantrums (high anger), depression (high depression), obliviousness (high anxiety). Tantrum can kill another dwarf → grief → cascade = "tantrum spiral."

**Key insight:** Facets map directly to our "depth score." The 60-point-value-difference = grudge rule is simple but generates complex emergent social dynamics.

---

## 2. RimWorld Pawn AI

### Needs: 0-100% bars (food, rest, recreation, beauty, comfort, outdoors, chemical)
Needs generate thoughts (mood modifiers) when crossing thresholds.

### Mood = base_mood + sum(all_thought_offsets)
Thoughts are temporary: `{description, mood_offset, duration, stack_limit}`

### Mental Break Thresholds
- Minor risk: mood < 35%
- Major risk: mood < 20%
- Extreme risk: mood < 5%

Traits shift thresholds. Below threshold → roll for break from severity pool.

**Key insight:** Thought stacking is very implementable. Each event → thought object → mood is just the sum. Simple but emergent.

---

## 3. The Sims: Advertisement System

**Intelligence lives in objects, not Sims.** Each object advertises what it offers (bed: +10 energy, toilet: +20 bladder). Other Sims advertise social increases.

### Action Selection Scoring
1. List reachable objects + their motive rewards
2. Apply **attenuation curves** per motive — physiological needs use exponential curves (spike when depleted, diminish when satisfied, based on Maslow)
3. Apply personality trait multipliers (neat Sim weights hygiene higher)
4. Apply distance penalty
5. Pick randomly from **top-scoring** interactions (not absolute best — prevents robotic behavior)

**The original AI was TOO good.** Will Wright deliberately degraded it so players were needed.

**Key insight:** Advertisement pattern directly applicable. World objects + NPCs broadcast what they offer, NPC decision-making is a scoring loop with personality-weighted attenuation. Cheap to compute, no AI needed.

---

## 4. Facade (2005)

### Architecture: Four Systems
1. **ABL (A Behavior Language):** Reactive planning for NPC behaviors. Multi-agent coordination.
2. **Beat System:** Story decomposed into ~20 dramatic beats, each containing 10-100 joint dialog behaviors (jdbs). A jdb is a 1-5 line coordinated exchange lasting seconds.
3. **Drama Manager:** Selects next beat based on dramatic arc. Monitors player actions + emotional state.
4. **NLU:** Forward-chaining template rules → discourse acts (intent + sentiment + topic). "Permissive template matching" — doesn't parse English fully. Deflection when can't understand.

**Total authored content:** ~2,500 dialogue lines across all beats.

**Key insight:** Permissive template matching for intent extraction is sufficient. You don't need perfect language understanding.

---

## 5. Versu / Emily Short

Created by Richard Evans (lead AI, Sims 3) and Emily Short.

### Social Practices
Social situations (dinner party, confession) provide affordances (available actions). Practices never control agents — only suggest.

### Utility-Based Action Selection
Each agent evaluates all actions, selects highest utility based on personality + goals + relationships. Characters express desires as world states, not specific actions.

### Emergent Behavior
Testing revealed a character fell silent when a third party entered a private conversation — behavior never authored, emerged from engine. "Just about everything you can do affects your character's opinion of other characters."

**Key insight:** Social practice model applicable to NPC-to-NPC ambient conversations. Define situations (tavern chat, market haggling) as affordance sets, let personality + utility scoring generate dialogue.

---

## 6. Commercial NPC AI Middleware

### Inworld AI
Character Brain (personality ML + emotions + memory) → Contextual Mesh (world grounding, anti-hallucination) → Real-Time AI (performance). "Goals and Actions" for trigger-based behavior with open-ended conversation.

### Convai
RAG knowledge bank: lore/scripts/context → retrieve relevant chunks → feed to LLM with personality. Supports NPC-to-NPC dialogue.

### Spirit AI (Character Engine)
Built by team including Emily Short. Recognizes entities, emotional tone, question type. Assembles responses from personality + emotions + game state + knowledge.

**All three use same pattern:** Character definition as system prompt + RAG for knowledge + triggers for game state. This is what we're already building.

---

## 7. Dialogue Scripting Engines

### Ink (Inkle)
- Text-first markup. Automatic state tracking (every line the player sees is remembered).
- Lists as state machines. Knots/stitches/diverts for flow.
- Parallel story flows (v1.0+) that share state.

### Yarn Spinner (Unity)
- Dialogue Runner bridges scripts ↔ game. Variable Storage persists state.

### Twine (Harlowe/SugarCube)
- Story variables (persist) vs temporary variables (current passage only).

**Key insight:** These are good fallback systems for dormant NPCs. Tier-0/1 NPCs could use Ink-style conditional dialogue instead of LLM tokens, promoting to AI voicing only when depth triggers.

---

## 8. Disco Elysium: Thought Cabinet / Skills

### 24 Skills as Internal Voices (4 attributes × 6 each)
- INT: Logic, Encyclopedia, Rhetoric, Drama, Conceptualization, Visual Calculus
- PSY: Volition, Inland Empire, Empathy, Authority, Esprit de Corps, Suggestion
- FYS: Endurance, Pain Threshold, Physical Instrument, Electrochemistry, Shivers, Half Light
- MOT: Hand/Eye, Perception, Reaction Speed, Savoir Faire, Interfacing, Composure

### Passive Checks (the innovation)
`skill_level + modifiers + 6 vs hidden_difficulty` — no dice. Fire automatically during conversations. When successful, skill "speaks" with distinct personality voice. **10,287 passive checks in the game.**

### Interjection Frequency Scales with Level
~Level 4 is where skills start giving input. Higher = louder voice. High-Empathy character constantly reads people. High-Electrochemistry constantly suggests substance use.

**Key insight:** Passive check formula (`stat + 6 vs difficulty`) is trivially implementable for NPC internal deliberation. When Director evaluates whether NPC notices/suspects something, run passive checks against personality axes. Scaling frequency creates natural differentiation without different prompts.

---

## 9. Shadows of Doubt / Watch Dogs: Legion

### Shadows of Doubt
- NPCs get persistent profiles at city gen: demographics, occupation, residence, relationships, fingerprints
- **Pre-computed daily schedules:** Before each game day, 10-15 seconds calculates all citizen schedules (4-10 journeys each). Avoids real-time pathfinding. Deviations calculated in real-time.
- **Memory system:** Global check loops through citizens, checks line of sight. Memories degrade based on familiarity + visual distinctiveness. Witnesses may lie.

### Watch Dogs: Legion (Census System)
- NPCs spawned as lightweight entities. When profiled, Census generates full identity in real-time.
- **"Uprezzing":** Background NPCs → fully-simulated characters through promotion. This IS our tier system.
- Memory spreads to connected NPCs (friends, enemies).

**Key insight:** Both solve scale the same way we plan to. Pre-computed daily schedules with real-time deviation = clean architecture for Director's daily pass.

---

## 10. Key Open-Source NPC Repos

- **Generative Agents** (github.com/joonspk-research/generative_agents) — Stanford paper implementation. Python + Django.
- **OrganicWorldsim** (github.com/Malacophonous/OrganicWorldsim) — Python, Maslow hierarchy, ART relationships, NetworkX. Closest to what we need.
- **SkyAGI** (github.com/litanlitudan/skyagi) — Generative agents as RPG.
- **AgentVerse** (github.com/OpenBMB/AgentVerse) — Multi-agent LLM framework (ICLR 2024).

---

## Synthesis for Loom

1. **NPC State:** DF/OrganicWorldsim pattern. Personality facets (0-100, ~10-15 axes), relationship graph (directed, multi-dimensional edges), memory stream (timestamped events), needs vector (Sims-style for autonomous behavior).
2. **Tiered Simulation:** Dormant = stat blocks + Ink-style conditional dialogue. Active = Sims advertisement system for autonomy (no LLM). Dramatic = Stanford generative agents memory/retrieval/reflection.
3. **Director:** Pre-compute daily schedules (Shadows of Doubt), allow real-time deviations. Facade drama manager for beat sequencing.
4. **Persuasion NLU:** Facade's permissive template matching: extract intent + sentiment + topic, evaluate against NPC personality.
5. **Knowledge Filtering:** RAG pattern. Tagged facts per NPC. Stanford retrieval scoring (recency × importance × relevance).
6. **Internal Deliberation:** DE passive checks (`stat + 6 vs difficulty`) for NPC noticing/suspecting. Frequency scales with stat level.
