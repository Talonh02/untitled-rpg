# AI RPG Codebases & Engines Research
## Compiled April 5, 2026

---

## Tier 1 — Highest Relevance

### RPGGO / XTalk + Zagii Engine
- **Repo:** https://github.com/RPGGO-AI/XTalk (15 stars, TypeScript, active)
- **Paper:** https://arxiv.org/html/2407.08195v2
- **What:** Closest existing project to Loom's architecture. Multi-NPC, multi-model text RPG engine with DM coordinator agent. Zagii engine uses PMTA framework (Perception, Memory, Thinking, Action) for NPC decision-making. Different LLMs serve different roles: lightweight for real-time dialogue, SOTA for validation, multimodal for visuals.
- **Key mechanics:** Game Status Manager breaks objectives into hierarchical sub-goals with numerical anchors. Emergent Narrative System uses RAG. Centralized Message Bus coordinates modules. Cold-start optimization: SOTA models pre-generate validation heuristics for lightweight models.
- **Relevance:** Only production system with explicit multi-model architecture for different game roles. Zajii layer (NPC orchestration) and DM agent parallel our Director and Interpreter.

### Stanford Generative Agents / AI Town
- **Generative Agents:** https://github.com/joonspk-research/generative_agents (21k stars, Apache-2.0)
- **AI Town (a16z):** https://github.com/a16z-infra/ai-town (9.7k stars, MIT, TypeScript)
- **What:** 25 AI characters in simulated town. Each has memory stream (vector DB), reflection (higher-order observations), planning (daily → moment-to-moment). After conversations, GPT summarizes, embeds, stores for semantic retrieval.
- **Memory retrieval formula:** `score = α_recency × recency + α_importance × importance + α_relevance × relevance`. Recency: exponential decay 0.995/game-hour. Importance: LLM-assigned 1-10. Relevance: cosine similarity of embeddings.
- **Reflection trigger:** When sum of recent importance scores > 150, generate reflections (~2-3/game day). 100 most recent memories → "3 most salient questions" → retrieve relevant memories → extract "5 high-level insights."
- **Relevance:** Memory/reflection/planning architecture directly applicable to NPC promotion system. Seed promoted NPCs with memory stream from stat-block history.

### Evennia (Python MUD Engine)
- **Repo:** https://github.com/evennia/evennia (2k stars, BSD-3, Python, very active)
- **What:** Most mature open-source Python MUD framework. Room/Exit/Object typeclass pattern. Persistent objects, command sets, tickers/timers, in-game menus. Django ORM backend.
- **Key pattern:** Rooms are graph nodes with no inherent coordinates. Exits are first-class objects (not just direction integers). Every object has exactly one `location` field. This is literally our `npc.location = "tessam_ironDrum_f2_backroom"` pattern.
- **Relevance:** Battle-tested Python implementation of our spatial tree. Object hierarchy (MudObject → Location, Item, Living → Player, NPC) is a reference design.

### Neighborly (NPC Simulation)
- **Repo:** https://github.com/ShiJbey/neighborly (74 stars, MIT, Python, active)
- **Paper:** IEEE Conference on Games 2022
- **What:** ECS-based settlement simulation. Characters have traits, statuses, relationships (romance + reputation), occupations, life events. NPCs form opinions based on trait compatibility. Simulates hundreds of years of history in minutes.
- **Relevance:** Best open-source reference for NPC relationship/opinion simulation in Python. Trait-based opinion system maps to our design.

### OrganicWorldsim
- **Repo:** https://github.com/Malacophonous/OrganicWorldsim (Python 3)
- **What:** Open-world RPG NPC simulation. Maslow's hierarchy for motivations. Relationships as directed graph with ART (Attitude, Respect, Trust) edges. NPC memory as event records. Uses NetworkX.
- **Relevance:** Closest existing codebase to what we need for NPC relationships.

---

## Tier 2 — Significant Architectural Value

### Gigax (LLM NPC Engine)
- **Repo:** https://github.com/GigaxGames/gigax (339 stars, MIT, Python)
- **What:** Runtime NPC actions using fine-tuned local models. Uses Outlines for structured generation — NPCs emit valid action tags, not free-form text. Sub-second GPU inference.
- **Relevance:** Structured generation via Outlines directly solves interpreter JSON truncation problem (~50% failure rate in our playtest).

### TaleWeave AI
- **Repo:** https://github.com/ssube/taleweave-ai (14 stars, MIT, Python)
- **What:** MUD engine where AI NPCs have mood, hunger, thirst, weather tracking. Plugin-based action systems. Generates worlds from text prompts.
- **Relevance:** Closest existing project combining MUD-style world sim with LLM NPCs. Plugin architecture for game systems is a good pattern.

### Tale (Python MUD/IF)
- **Repo:** https://github.com/irmen/Tale (150 stars, LGPL-3.0, Python)
- **What:** Dual-mode framework (single-player IF / multiplayer MUD). Clean object hierarchy. Parser uses LPC-MUD soul system.
- **Relevance:** Smaller and more readable than Evennia. Good starting point for studying room/item/NPC modeling.

### dungeon-master-ai-project
- **Repo:** https://github.com/fedefreak92/dungeon-master-ai-project (28 stars, Python)
- **What:** D&D 5e RPG backend with stacked finite state machine for game phases. ASCII maps. Entity factory. Zero external dependencies.
- **Relevance:** Stacked FSM is a good pattern for game states. Separation of Python logic from AI narration matches "models speak, Python thinks."

---

## Tier 3 — Reference Value

### SillyTavern
- **Repo:** https://github.com/SillyTavern/SillyTavern (25k stars, AGPL-3.0, JS)
- **Relevance:** WorldInfo/lorebook system for injecting context into LLM prompts. Character card format is de facto standard.

### KoboldCpp
- **Repo:** https://github.com/LostRuins/koboldcpp (10k stars, AGPL-3.0, C++)
- **Relevance:** If we ever run local models for cheap NPC dialogue, this is the inference backend.

### Original AI Dungeon
- **Repo:** https://github.com/latitudegames/AIDungeon (3.2k stars, MIT, Python)
- **Relevance:** Historical reference. Demonstrates what NOT to do — no separation between game logic and generation.

### Inform 7
- **Repo:** https://github.com/ganelson/inform (1.6k stars, C)
- **Relevance:** Gold standard for text game world modeling concepts. Decades of design thinking about containment, light propagation, doors.

---

## Academic Papers

- **"A Text-to-Game Engine for UGC-Based RPGs"** (RPGGO, 2024) — https://arxiv.org/html/2407.08195v2
- **"Generative Agents: Interactive Simulacra of Human Behavior"** (Stanford, 2023) — foundational memory/reflection/planning paper
- **"Large Language Models and Games: A Survey"** (2024) — https://arxiv.org/html/2402.18659v4
- **"Fixed-Persona SLMs with Modular Memory"** (2025) — https://arxiv.org/html/2511.10277 — SLMs fine-tuned per NPC persona with swappable memory

---

## Meta-Resources

- https://github.com/tajmone/awesome-interactive-fiction (206 stars)
- https://github.com/mudcoders/awesome-mud (136 stars)
- https://github.com/Yuan-ManX/ai-game-devtools
