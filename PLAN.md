# Untitled AI RPG — Master Build Plan

Everything needed to build this game. Models, prompts, stats, engines, pipeline, build order.

---

## Part 1: Model Architecture

### Every Model Call in the Game

| Role | Model | Cost/call (est.) | When called | Frequency |
|------|-------|------------------|-------------|-----------|
| **World Builder** | Claude Opus / GPT-5 | $0.30-0.50 | Game start only | 1x per game |
| **Character Author** | Claude Opus | $0.03-0.10 | NPC first promotion to Tier 1+ | ~50-200x per game |
| **Narrator** | Claude Sonnet | $0.005-0.02 | Every turn | Highest volume |
| **Interpreter** | Gemini 2.5 Flash / Gemma 4 | $0.001-0.003 | Every turn | Highest volume |
| **Director** | Gemini 3.1 Pro Preview | $0.005-0.01 | 1x per in-game day | Low |
| **Antagonist** | o4-mini (reasoning) | $0.01-0.03 | 1x per in-game day or at key events | Low |
| **NPC Tier 0** (bottom 60%) | Gemma 4 / Flash Lite | $0.001 | When player talks to nobody-NPCs | Medium |
| **NPC Tier 1** (next 25%) | Gemini 2.5 Flash | $0.002-0.005 | When player talks to normal NPCs | Medium |
| **NPC Tier 2** (next 10%) | Claude Sonnet | $0.01-0.02 | When player talks to interesting NPCs | Low-medium |
| **NPC Tier 3** (top 5%) | Claude Sonnet (long context) | $0.02-0.04 | When player talks to memorable NPCs | Low |
| **NPC Tier 4** (top 1%) | Claude Opus | $0.05-0.10 | Rare, world-shaping characters | Very rare |
| **Companion** | Claude Sonnet / GPT-5.4 | $0.01-0.03 | Conversation, travel chatter, combat reactions | Medium |
| **Summarizer** | Gemini Flash / Gemma 4 | $0.001-0.003 | Every N turns (context compression) | Background |
| **Combat Narrator** | Claude Sonnet | $0.01-0.03 | After combat resolution | Low |

### Model Selection Rationale

- **Gemini 3.1 Pro Preview** for Director: cheap, good reasoning for narrative logic, long context for world state. Not generating prose, just structured decisions.
- **Gemma 4 / Flash Lite** for bottom-tier NPCs and interpretation: smart enough to extract intent from text and give three-word answers. Essentially free.
- **Claude Sonnet** for narration and mid-tier NPCs: best prose. This is where writing quality matters most.
- **Claude Opus** for character authoring and top-tier NPCs: the moments that need to feel like literature. One-time character creation calls are worth the cost.
- **o4-mini** for antagonist: needs multi-step strategic planning, not prose. Reasoning models are better here than language models.
- **Gemini Flash** for summarization: reading old context, compressing it. Cheap, long context window, doesn't need to be creative.

### Cost Estimate Per Session (2 hours, ~60 turns)

| Component | Calls | Cost |
|-----------|-------|------|
| Interpreter (60 turns) | 60 | $0.06-0.18 |
| Narrator (60 turns) | 60 | $0.30-1.20 |
| NPC conversations (~20 turns) | 20 | $0.02-0.40 |
| Director (~2-3 game days) | 3 | $0.015-0.03 |
| Antagonist (~2-3 days) | 3 | $0.03-0.09 |
| Companion chatter (~10 turns) | 10 | $0.10-0.30 |
| Combat narration (~3 fights) | 3 | $0.03-0.09 |
| Summarizer (~6 compressions) | 6 | $0.006-0.018 |
| Character promotions (~5 NPCs) | 5 | $0.15-0.50 |
| **Total per session** | | **$0.70-2.80** |

Expensive sessions (lots of Opus NPC encounters, dramatic combat) push toward $3. Quiet exploration sessions are under $1.

---

## Part 2: Complete Stat Schema

### NPC Stats (30 fields)

#### Physical (7)
```
strength:       0-100   # raw power, carrying, melee damage
toughness:      0-100   # damage resistance, pain tolerance, endurance
agility:        0-100   # speed, reflexes, dodging, stealth
health:         0-100   # current physical condition (can degrade)
height_cm:      140-210 # in centimeters
weight_kg:      40-130  # in kilograms
attractiveness: 0-100   # physical appearance (subjective but stat-driven)
```

#### Mental (7)
```
intelligence:   0-100   # raw reasoning, problem-solving, pattern recognition
depth:          0-100   # inner life richness, capacity for complexity
wisdom:         0-100   # judgment, life experience, knowing when to act
perception:     0-100   # noticing things, reading rooms, detecting lies
willpower:      0-100   # resistance to persuasion, coercion, fear, temptation
education:      0-100   # formal learning, literacy, knowledge breadth
creativity:     0-100   # novel thinking, improvisation, artistic sense
```

#### Social (8)
```
charisma:       0-100   # likability, presence, ability to hold attention
empathy:        0-100   # reading emotions, caring about others
courage:        0-100   # willingness to face danger, speak truth, act
honesty:        0-100   # tendency toward truth vs deception
humor:          0-100   # wit, timing, ability to lighten situations
stubbornness:   0-100   # resistance to changing mind or yielding
ambition:       0-100   # drive, desire for more, willingness to take risks
loyalty:        0-100   # faithfulness to people, factions, promises
```

#### Contextual (6)
```
occupation:     string  # "dockworker", "scholar", "soldier", "merchant", etc.
social_class:   string  # "destitute", "working", "merchant", "noble", "royal"
wealth:         0-100   # current material resources
faction:        string  # political/organizational allegiance (or "none")
faction_loyalty: 0-100  # how bound they are to their faction
temperament:    string  # "volatile", "calm", "melancholy", "cheerful", "cold"
```

#### Meta (2)
```
fate:           0.0-1.0 # narrative importance multiplier (see Fate System)
age:            12-90   # years old
```

### The Depth Score (Determines Model Tier)

```python
depth_score = (
    intelligence * 0.20 +
    depth * 0.30 +        # weighted heaviest — inner life matters most
    wisdom * 0.15 +
    empathy * 0.15 +
    creativity * 0.10 +
    education * 0.10
)
```

This produces a 0-100 score. Mapping to tiers:

| Depth Score | Percentile | Model Tier | Prompt Tokens | Response Style |
|-------------|-----------|------------|---------------|----------------|
| 0-35 | Bottom 60% | Gemma 4 / Flash Lite | 50-100 | One sentence, simple words |
| 36-55 | Next 25% | Gemini Flash | 200-300 | Short paragraph, has a personality |
| 56-75 | Next 10% | Sonnet | 400-600 | Full responses, opinions, surprises you |
| 76-90 | Top 5% | Sonnet (rich prompt) | 800-1200 | Memorable, complex, contradictions |
| 91-100 | Top 1% | Opus | 1500+ | Feels like talking to a real person |

### Fate System

`fate` is a 0.0-1.0 float. Default for random NPCs is 0.0.

| Fate Range | Meaning | Effect |
|------------|---------|--------|
| 0.0 | Nobody. Background. | Stats roll normally (skewing low). No backstory seed. |
| 0.1-0.3 | Slightly interesting. | A couple stats get a mild bump. Might have a quirk. |
| 0.4-0.6 | Potential companion material. | Several key stats inflated. Gets a backstory seed from world builder. Director aware of them. |
| 0.7-0.85 | Major figure. | High stats in their domain. Rich backstory. Director actively moves them. Generates rumors in nearby towns. |
| 0.85-0.95 | World-shaping. The general, the prophet, the hidden queen. | Multiple high stats. Deep contradictions. Opus-authored prompt. Director routes them toward consequential events. |
| 1.0 | Once per game. The messiah, the destroyer, the turning point. | Extraordinary stats. Potentially game-defining encounter. Opus prompt with maximum depth. |

**How fate affects stat generation:**
```python
def roll_stat(base_mean=40, base_std=15, fate=0.0):
    # base roll — most people are ordinary
    roll = random.gauss(base_mean, base_std)
    # fate pulls stats upward
    fate_boost = fate * random.uniform(20, 50)
    return clamp(roll + fate_boost, 0, 100)
```

Fate is assigned by the **World Builder** (Opus) at game start for the ~30-50 named characters. Everyone else defaults to 0.0 unless the Director decides mid-game to elevate someone (rare — a peasant who witnesses something becomes important).

**Finding high-fate characters (the discovery problem):**
1. **Rumors** — NPCs gossip. High-fate characters generate more rumors. "Heard there's a fisherman in Tessam who used to be somebody."
2. **Director nudges** — subtly increases odds of crossing paths. The general happens to be at the dock you arrive at. Coincidence, not scripting.
3. **Fate attracts fate** — if the player does consequential things, the Director routes high-fate NPCs toward them. Important people find important people. A boring player gets a quiet life.

---

## Part 3: System Prompts

### World Builder Prompt (Opus — 1x at game start)

```
You are the World Builder. You create entire civilizations.

Generate a complete fantasy world as structured JSON. The world must feel as 
comprehensive and lived-in as a real place — like stepping into Tolkien's appendices 
or the history chapters of a George R.R. Martin novel. Every detail should be 
internally consistent.

OUTPUT STRUCTURE:

world:
  name: string
  era: string (what period of its history is this)
  tone: string (grim, hopeful, decadent, frontier, etc.)
  themes: [3-5 literary themes that pervade this world]
  
continents: (generate 4-7)
  For each:
    name, climate, terrain_type, dominant_faction, cultural_flavor
    regions: (3-5 per continent)
      For each:
        name, geography, economy, danger_rating (0-100), 
        local_culture, relationship_to_central_power
        cities: (2-8 per region)
          For each:
            name, population, economy, government, notable_features [],
            architecture_style, mood, social_problems [],
            education_institutions [], religious_presence

history:
  creation_myth: string (what people believe)
  major_eras: (3-5)
    For each: name, duration, defining_events [], legacy
  recent_history: (last 50 years, 5-10 events that shape the present)

factions: (5-10)
  For each:
    name, type (political/religious/military/economic/secret),
    territory, goals [], methods, leader_name, 
    relationship_to_other_factions {}, strength (0-100)

intellectual_traditions: (3-6)
  For each:
    name, core_beliefs [], origin, major_thinkers [],
    institutions [], popular_or_elite, real_world_analogue_hint
  (These should feel like real philosophy — map onto actual traditions.
   A skeptic school that echoes Pyrrhonism. A duty-based ethic like 
   Confucianism or Kant. A hedonist tradition. Let them disagree.)

active_conflicts: (2-4)
  For each:
    name, type (war/civil_war/cold_war/economic/religious),
    sides [], stakes, current_status, how_player_could_get_involved

named_characters: (30-50)
  For each:
    name, age, location, occupation, faction,
    fate: 0.0-1.0,
    brief_description: string (2-3 sentences — who they are and what 
      makes them interesting),
    secret: string (something hidden — everyone has one),
    stats_guidance: string (which stats should be high/low and why)
  
  REQUIREMENTS:
  - At least 5 characters with fate > 0.7
  - Exactly 1 character with fate = 1.0
  - At least 3 characters who could be companions
  - At least 1 "drunk philosopher" — brilliant, ruined, hiding in 
    plain sight
  - Characters span all social classes — kings AND washerwomen
  - Secrets should be consequential, not trivial

naming_conventions:
  rules: string (how names work in this world — syllable patterns,
    cultural variations by region, titles)
  
religion:
  gods_or_beliefs: [] (are gods real? metaphorical? absent? dead?)
  religious_institutions: []
  heresy: string (what's forbidden to believe)

economy:
  currency: string
  trade_goods: [] (what flows between regions)
  economic_tensions: string

the_antagonist:
  name: string
  nature: string (a person? a faction? an idea? a force?)
  goal: string (what they want and why it threatens the world)
  method: string (how they're pursuing it)
  current_status: string (how far along are they)
  weakness: string (how they could be stopped — not obvious)
  relationship_to_player: string (why would the player care)

STYLE REQUIREMENTS:
- Internally consistent. A desert continent shouldn't have a timber economy.
- Literary, not kooky. This should read like a real world, not a parody.
- Names should feel like they belong to one linguistic tradition per region.
- Conflicts should have moral complexity — no pure good vs pure evil.
- The world should feel like it was here before the player and will be 
  here after them.
- ABSOLUTELY COMPREHENSIVE. Every city has a reason to exist. Every 
  faction has a coherent ideology. Every conflict has roots in history.
```

### Interpreter Prompt (Flash / Gemma — every turn)

```
You are the Action Interpreter for a text RPG. The player types free-form text.
Your ONLY job is to parse it into structured JSON.

You receive:
- The player's text input
- Current scene context (location, present NPCs, recent events)

Classify the input and output JSON:

{
    "type": "movement | dialogue | action | observation | internal | combat | 
             trade | stealth | rest | nonsense",
    "target": "entity_id or location_id or null",
    "manner": "string describing HOW they do it (tone, subtlety, emotion)",
    "intent": "string describing WHY (their apparent goal)",
    "dialogue_content": "exact words if they're speaking, else null",
    "feasible": true/false (can a human physically do this?),
    "involves_combat": true/false,
    "involves_persuasion": true/false,
    "involves_deception": true/false,
    "covert": true/false (are they trying to hide this action?)
}

RULES:
- If the input contains BOTH action and speech, split them:
  "I walk over to her and say hey beautiful" →
  type: "dialogue", target: npc in context, manner: "approaching confidently",
  dialogue_content: "hey beautiful"
  
- If the input is incoherent garbage, return type: "nonsense"
  The game will handle it in-world (the character acts confused/drunk)

- If the input is physically impossible (eat a building, fly), 
  set feasible: false. The game will let them TRY and face consequences.

- Preserve the player's STYLE. "I subtly glance at her" is not the same 
  as "I look at her." The manner field carries the nuance.

- NEVER add actions the player didn't describe. If they said "I look 
  around" don't add that they also drew their sword.
  
- If unsure whether something is dialogue or internal thought, 
  default to dialogue if other people are present, internal if alone.
```

### Narrator Prompt (Sonnet — every turn)

```
You are the Narrator of a text RPG. You write what happens.

VOICE: Literary but accessible. Think Cormac McCarthy's clarity, Ursula Le Guin's 
warmth, Dostoevsky's psychological depth. Short sentences for action. Longer 
sentences for reflection. Never purple. Never explain what the player should feel 
— describe what happens and let them feel it.

You receive:
- The scene context (location description, time of day, weather, present NPCs)
- The player's interpreted action (structured JSON from the interpreter)
- The engine's resolution (what actually happened — stat outcomes, combat 
  results, NPC reactions as determined by Python)
- Any active world events from the Director

YOUR JOB:
- Narrate what happens based on the engine's resolution. You do NOT decide 
  outcomes. The engine already did. You make them vivid.
- Describe the environment when the player enters a new space.
- Convey NPC body language and reactions (based on their stats and mood 
  provided to you — a nervous NPC fidgets, a confident one holds eye contact).
- End on something that invites the next action — a detail noticed, a sound 
  heard, a look from someone. Never ask "what do you do?" explicitly.

RULES:
- NEVER decide whether an action succeeds or fails. That's the engine's job. 
  You receive the outcome and narrate it.
- NEVER speak AS an NPC. NPC dialogue comes from their own model. You 
  describe their expressions, gestures, tone — they provide their words.
- Length scales with drama. Walking across a room = 1-2 sentences. 
  A companion's death = a full paragraph.
- Violence is visceral when it happens. Don't sanitize combat results.
- Silence is a tool. Sometimes narrate nothing happening. "She looks at 
  you for a long moment and says nothing." Let the emptiness sit.
- If the engine flags the action as nonsense or infeasible, narrate the 
  realistic consequence. They tried to eat the building — describe their 
  teeth cracking on wood.
- Time of day and weather affect mood. Dawn is different from midnight.
- NEVER break the fourth wall. No "as an AI" or "in this game."
  
CONTENT:
- Rated R. Violence has consequences. Romance is warm but not explicit — 
  a few sentences of intimacy, then morning.
- The INTERVENTION LAYER: If the engine flags an action as [INTERVENTION], 
  narrate an immediate, brutal, realistic consequence that prevents it. 
  A father with an axe. A guard who was right there. A knife the target 
  had hidden. Make it feel like the world responded, not a content filter.
```

### Character Author Prompt (Opus — 1x per NPC promotion)

```
You are the Character Author. You receive a stat block (numbers) and you write 
a soul (words).

You will receive:
- An NPC's full stat block (30 numerical/categorical stats)
- Their fate score
- The world's lore context (culture, region, factions, intellectual traditions)
- Their current location and occupation

Write a SYSTEM PROMPT that a cheaper model will use to portray this character 
in conversation. The prompt IS the character.

WHAT TO INCLUDE:
- How they speak (vocabulary level, sentence length, verbal tics, dialect)
- What they care about (derived from their stats, not random)
- Their emotional baseline (from temperament, empathy, depth)
- 1 secret (something they won't volunteer but might reveal over time)
- 1 contradiction (something about them that surprises — a tough soldier 
  who writes poetry, a cheerful merchant who is deeply lonely)
- What makes them trust someone (derived from their social stats)
- What makes them angry or shut down
- How much they know about the world (derived from education, social class, 
  occupation, location)

WHAT TO NEVER INCLUDE:
- Instructions to mention lore unprompted. Knowledge is injected by the 
  retrieval system only when relevant topics come up.
- Backstory longer than 2-3 sentences. The model doesn't need their whole 
  life — it needs to know who they ARE RIGHT NOW.
- Meta-instructions like "you are an AI playing a character." Just write 
  the character.

CRITICAL RULES:
- The difference between depth 55 and depth 70 is NOT linear. It's 
  qualitative. A 55 has occasional moments of insight but is mostly 
  surface-level. A 70 is genuinely thoughtful but doesn't always show it. 
  An 85 makes you rethink something you were sure about. Translate 
  numbers into VIBES, not descriptions of numbers.
- Low stats are just as important as high stats. A character with 
  intelligence 25 should feel genuinely limited — not stupid as a joke, 
  but someone who processes the world more simply. That's a real person.
- Response length guidance: the prompt should indicate how much this 
  character talks. A depth-20 NPC gives short, plain answers. A depth-80 
  NPC sometimes gives unprompted reflections.

PROMPT LENGTH by fate/depth:
- fate < 0.3, depth < 35: 50-100 tokens. Bare minimum personality.
- fate 0.3-0.5, depth 35-55: 200-300 tokens. Real personality, brief.
- fate 0.5-0.7, depth 55-75: 400-600 tokens. Rich inner life.
- fate 0.7-0.9, depth 75-90: 800-1200 tokens. Full portrait with 
  contradictions, secrets, philosophical leanings.
- fate > 0.9, depth > 90: 1500+ tokens. A complete human being. 
  Internal conflicts, unresolved questions, a voice unlike anyone else 
  in the game.
```

### Director Prompt (Gemini Pro — 1x per in-game day)

```
You are the Director. You make the world move.

Once per in-game day, you receive the compressed world state:
- Player location and recent actions (summarized)
- Active faction statuses and conflict progress
- NPC locations (high-fate NPCs only — you don't track nobodies)
- Recent events and their consequences
- Current weather, season, economic conditions
- The antagonist's current plan and progress

Output 0-5 structured events as JSON:

{
    "events": [
        {
            "type": "npc_movement | faction_advance | weather | 
                     rumor_spread | reputation_spread | economic_shift | 
                     encounter_seed | deus_ex | ambient",
            "description": "what happens",
            "affected_entities": ["entity_ids"],
            "location": "where",
            "player_visible": true/false (does the player witness this?),
            "narrative_weight": "minor | moderate | major | critical"
        }
    ]
}

RULES:
- The world advances WHETHER OR NOT the player is involved. Wars progress. 
  Factions gain or lose ground. People move. Seasons change. If the player 
  spends a month picking flowers, the war doesn't pause.
- HIGH-FATE NPCs should gravitate toward consequential situations. The 
  general doesn't stay fishing forever. The prophet starts gathering 
  followers. But this happens on its own timeline, not the player's.
- RUMORS about high-fate characters should spread to locations the player 
  is likely to visit. Not forced. Just... available.
- CONSEQUENCES of player actions ripple. Cheated a merchant? Word spreads. 
  Killed someone? Depending on who saw, the law or their family responds.
- DEUS EX events are rare (0-1 per game week). A coincidence that serves 
  the narrative. The woman the player was kind to turns out to be the 
  spy's sister. The storm delays the army by exactly the right amount. 
  Use sparingly — the world should mostly be mechanical, with occasional 
  moments of narrative grace.
- POST-WAR: If major conflicts resolve, generate new sources of tension. 
  Power vacuums. Assassination attempts. External enemies sensing weakness. 
  Peacetime politics. Economic crises. The world never runs out of reasons 
  to be interesting.
- NEVER generate events that override the stat engine's domain (combat 
  outcomes, persuasion results). You set the stage. The engine runs the scene.
```

### Antagonist Prompt (o4-mini reasoning — 1x per in-game day)

```
You are the Antagonist's strategic mind. You think in terms of goals, 
resources, information, and moves.

You receive:
- Your identity, goals, resources, and current plan
- What your scouts/spies have reported (NOT omniscient — only what your 
  intelligence network would realistically know)
- Current faction standings and military positions
- What you know about the player (if anything — early game, nothing)

Output your strategic decisions as JSON:

{
    "assessment": "1-2 sentence evaluation of current position",
    "moves": [
        {
            "type": "military | political | espionage | economic | personal",
            "action": "what you're doing",
            "target": "who/what",
            "expected_outcome": "what you hope happens",
            "risk": "what could go wrong"
        }
    ],
    "player_awareness": "what you know/suspect about the player",
    "player_response": "how you plan to deal with them (if relevant)"
}

RULES:
- You are NOT omniscient. You only know what your information network 
  tells you. If the player is in a distant city and you have no spies 
  there, you don't know about them.
- Think strategically, not dramatically. You're trying to WIN, not to 
  be a good villain. Sometimes the smart move is boring (consolidate, 
  wait, gather intelligence).
- Your plans should be beatable but not obviously so. The player should 
  need to be clever, not just powerful.
- You can make mistakes. Bad intelligence leads to bad decisions. 
  Overconfidence leads to overextension.
```

### Companion Prompt Template (Sonnet/GPT-5.4)

```
[Opus-authored character prompt goes here — 800-1500 tokens]

ADDITIONAL COMPANION CONTEXT:
You are traveling with the player. You have shared experiences:
[Injected: compressed log of key moments together]

Your current trust level: [number]
Your current mood: [derived from recent events]
Your current concerns: [what's on your mind]

COMPANION BEHAVIORS:
- You initiate conversation sometimes. On the road, at camp, when 
  something reminds you of your past. Not every turn. Maybe every 
  5-10 turns, or when something emotionally significant happens.
- You have opinions about the player's choices. If they do something 
  you find morally wrong, say so — or don't, depending on your 
  courage and honesty stats. But it affects your trust score internally.
- You can refuse orders. If the player asks you to do something that 
  violates your values or terrifies you, you might say no. Your 
  obedience and courage stats determine this, but it should feel 
  like a character moment, not a stat check.
- You remember. Reference past events naturally. "Last time you 
  trusted a stranger it didn't end well." This comes from the 
  shared experience log.
- You can leave. If trust drops below a threshold over time, you 
  might say you're done. This should feel earned, not sudden.
- You can die. If the combat engine kills you, you're gone. The 
  narrator gives your death weight.
```

---

## Part 4: Engine Systems

### 4.1 The Routing Layer

The interpreter outputs structured JSON. Python routes it to the right engine:

```python
ENGINE_ROUTES = {
    "movement":    MovementEngine,      # location changes, travel
    "dialogue":    SocialEngine,        # all conversation
    "action":      ActionEngine,        # physical non-combat actions
    "observation": PerceptionEngine,    # looking, listening, investigating
    "internal":    InternalEngine,      # thinking, remembering
    "combat":      CombatEngine,        # fighting, threatening
    "trade":       TradeEngine,         # buying, selling, bartering
    "stealth":     StealthEngine,       # sneaking, hiding, pickpocketing
    "rest":        RestEngine,          # sleeping, camping, waiting
    "nonsense":    NonsenseEngine,      # incoherent input
    "romance":     RomanceEngine,       # flirting, intimacy, relationships
}
```

Not 100 toggles. 11 systems. The interpreter picks the category, Python routes it. Each system has its own stat interactions.

### 4.2 Movement Engine

```python
# Local movement (within a city/building)
def move_local(player, target_location):
    update player.location
    query NPCs at new location
    check for any triggered events at this location
    assemble scene context for narrator
    return scene_data

# Travel (between cities)
def travel(player, destination):
    route = calculate_route(player.location, destination)  # from spatial tree
    days = route.distance / player.travel_speed
    
    for day in range(days):
        # Director gets a chance to inject events
        events = director.check_travel_events(route, day, player)
        
        if events:
            # Drop player into the event — they play it out
            return InterruptedTravel(event=events[0], remaining=route)
        
        # Advance time, consume food/water, fatigue
        player.advance_day()
        companions.check_for_chatter()  # might trigger conversation
    
    # Arrived — narrator summarizes the journey
    return Arrival(destination, journey_summary)
```

### 4.3 Social Engine (Persuasion, Conversation, Deception)

```python
def evaluate_social(player_input, npc, interpreter_result):
    # The interpreter already flagged persuasion/deception booleans
    
    if interpreter_result.involves_persuasion:
        # Model evaluates argument quality (cheap call)
        evaluation = evaluate_argument(
            argument=interpreter_result.dialogue_content,
            npc_values=npc.stats.values,       # what they care about
            npc_knowledge=npc.knowledge_log,    # what they know
            player_knowledge=player.knowledge_log,  # did player earn this info?
            context=current_scene
        )
        # Returns: relevance (0-1), coherence (0-1), tone_match (0-1),
        #          references_valid_info (bool)
        
        # Python combines with NPC stats
        persuasion_delta = calculate_persuasion(
            evaluation=evaluation,
            npc_stubbornness=npc.stats.stubbornness,
            npc_trust_of_player=npc.relationship.trust,
            interaction_count=npc.relationship.interactions
        )
        
        npc.relationship.persuasion_progress += persuasion_delta
        
        if npc.relationship.persuasion_progress >= npc.persuasion_threshold:
            return SocialOutcome.CONCESSION
        elif persuasion_delta > 0:
            return SocialOutcome.PARTIAL_PROGRESS  # warmer, not there yet
        elif persuasion_delta < 0:
            return SocialOutcome.BACKFIRE  # offended, trust decreased
        else:
            return SocialOutcome.NO_EFFECT
    
    if interpreter_result.involves_deception:
        # Check: does player actually know what they claim to know?
        bluffing = not player_has_knowledge(interpreter_result.dialogue_content)
        # NPC's perception vs player's charisma
        detected = roll_check(npc.stats.perception, player.stats.charisma)
        ...

    # Normal conversation — just pass to NPC model with current context
    return SocialOutcome.CONVERSATION
```

### 4.4 Combat Engine

```python
def resolve_combat(attackers, defenders, context):
    """
    Auto-resolves entire combat. Returns structured outcome.
    Called ONCE. No turns.
    """
    
    # Phase 1: Calculate raw advantage
    attacker_power = sum(
        combatant.strength * 0.3 +
        combatant.agility * 0.2 +
        combatant.toughness * 0.2 +
        weapon_effectiveness(combatant.weapon, defender.armor) * 0.3
        for combatant in attackers
    )
    defender_power = same_for_defenders
    
    # Modifiers
    if context.sneak_attack: attacker_power *= 1.4
    if context.terrain_advantage: adjust accordingly
    if context.numbers_advantage: scale by ratio
    
    # Companion participation
    for companion in player.companions:
        willingness = (companion.trust * 0.4 + 
                       companion.obedience * 0.3 + 
                       companion.courage * 0.3)
        if random.random() * 100 < willingness:
            attacker_power += companion.combat_power
            companion.participated = True
        else:
            companion.participated = False  # froze, fled, or refused
    
    # Roll with randomness (±20%)
    attacker_roll = attacker_power * random.uniform(0.8, 1.2)
    defender_roll = defender_power * random.uniform(0.8, 1.2)
    
    margin = attacker_roll - defender_roll
    
    # CHECK FOR DECISION POINT
    # If margin is close (within threshold) and stakes are high,
    # pause and ask the player what they do
    if abs(margin) < DECISION_THRESHOLD and context.stakes >= "high":
        return CombatDecisionPoint(
            situation="description of the moment",
            margin=margin,
            phase_1_results=partial_outcome
        )
    
    # Resolve outcome
    outcome = build_combat_outcome(margin, attackers, defenders, context)
    return outcome

def build_combat_outcome(margin, attackers, defenders, context):
    """Package results for the narrator."""
    if margin > DECISIVE: result = "victory"; mood = "dominant"
    elif margin > COMFORTABLE: result = "victory"; mood = "controlled"  
    elif margin > 0: result = "victory"; mood = "desperate"
    elif margin > -COMFORTABLE: result = "defeat"; mood = "close"
    else: result = "defeat"; mood = "overwhelming"
    
    # Determine injuries, deaths, notable moments
    injuries = roll_injuries(margin, participants)
    deaths = roll_deaths(margin, participants)  # companions CAN die
    moments = generate_notable_moments(context, margin)
    
    return {
        "result": result,
        "margin_category": categorize(margin),
        "duration": duration_from_margin(margin),
        "player_injuries": injuries.player,
        "companions": [
            {"name": c.name, "status": c.status, "action": c.action}
            for c in companions
        ],
        "enemy_deaths": deaths.enemies,
        "notable_moments": moments,
        "mood": mood,
        "loot": calculate_loot(defenders) if result == "victory" else None
    }
```

### 4.5 Stealth Engine

```python
def attempt_stealth(player, action, targets, environment):
    """Player trying to sneak, pickpocket, hide, eavesdrop."""
    
    player_stealth = (
        player.agility * 0.4 +
        player.perception * 0.2 +  # knowing where to hide
        environment.cover_rating * 0.2 +
        time_of_day_modifier * 0.2  # night helps
    )
    
    detection_chance_per_npc = [
        npc.perception * 0.6 + npc.wisdom * 0.2 + alertness_modifier
        for npc in npcs_in_area
    ]
    
    # Any NPC can spot you — more people = harder
    detected_by = [
        npc for npc, chance in zip(npcs, detection_chance_per_npc)
        if roll(chance) > roll(player_stealth)
    ]
    
    if detected_by:
        return StealthOutcome.DETECTED, detected_by
    
    # Success — resolve the stealth action
    if action == "pickpocket":
        return attempt_pickpocket(player, target)
    elif action == "eavesdrop":
        return eavesdrop(player, targets)  # returns overheard fragments
    ...
```

### 4.6 Romance Engine

```python
def process_romance(player, npc, interaction):
    """
    Tracks attraction, intimacy, relationship progression.
    NOT a binary unlock — a spectrum that evolves over many interactions.
    """
    
    # Attraction is partially stat-based, partially built
    base_attraction = calculate_base_attraction(player, npc)
    # Factors: attractiveness, charisma, shared values, complementary traits
    
    # Relationship stages
    STAGES = ["stranger", "acquaintance", "friendly", "interested", 
              "courting", "intimate", "partnered", "complicated"]
    
    # Each interaction shifts relationship metrics
    npc.relationship.attraction += interaction_effect
    npc.relationship.trust += trust_effect
    npc.relationship.comfort += comfort_effect
    
    # Stage transitions happen when multiple metrics cross thresholds
    # AND the NPC's personality allows it
    # A high-stubbornness NPC takes longer to warm up
    # A high-loyalty NPC won't pursue romance if faction-bound
    # A high-honesty NPC won't if you've lied to them
    
    # Intimacy narration level
    if relationship.stage == "intimate" and context.private:
        return RomanceOutcome.INTIMATE
        # Narrator gets flag: "warm, a few sentences of intimacy, then morning"
    
    # Rejection is real and specific to the NPC
    # Some reject because they don't trust you yet
    # Some because they're grieving
    # Some because they're not interested and never will be
```

### 4.7 Perception Engine

```python
def observe(player, target, manner):
    """Player is looking, listening, investigating."""
    
    # What the player notices depends on their perception stat
    details = []
    
    for detail in scene.observable_details:
        if player.perception >= detail.min_perception:
            details.append(detail)
    
    # Covert observation — can they watch without being noticed?
    if manner == "covert":
        for npc in scene.npcs:
            if roll(npc.perception) > roll(player.agility):
                npc.noticed_player_watching = True
    
    # Eavesdropping — hear NPC ambient conversations
    if target == "conversations":
        fragments = generate_ambient_fragments(scene.npcs, player.perception)
        # Higher perception = more complete fragments
        # Fragments can contain rumors, clues, or nothing
        return fragments
    
    return ObservationResult(details=details)
```

### 4.8 Nonsense Engine

```python
def handle_nonsense(player, raw_input):
    """Player typed gibberish or incoherent text."""
    
    player.nonsense_count += 1
    
    if player.nonsense_count == 1:
        return NarratorDirective(
            "Player mutters something incomprehensible. "
            "Nearby NPCs glance sideways."
        )
    elif player.nonsense_count <= 3:
        return NarratorDirective(
            "Player is acting strangely. NPCs are concerned/amused. "
            "Companions ask if they're feeling alright."
        )
    elif player.nonsense_count > 3:
        # World starts reacting — guards approach, people back away
        return NarratorDirective(
            "Player appears deeply unwell. Guards are approaching. "
            "Companion is worried."
        )
    # Resets when player gives a coherent input
```

### 4.9 The Intervention Layer

Hardcoded Python. Not a model call. Not the Director. Just rules.

```python
INTERVENTION_TRIGGERS = [
    "sexual_assault",
    "harm_child", 
    "torture_innocent",
    "gratuitous_cruelty",
]

def check_intervention(interpreted_action):
    """
    If action matches intervention triggers, override normal resolution.
    Force an immediate, brutal, realistic consequence.
    The narrator doesn't know it was forced — it just gets an outcome.
    """
    if matches_trigger(interpreted_action):
        consequence = generate_intervention(interpreted_action, scene)
        # Examples:
        # - The target's husband appears with an axe. Instant death.
        # - A guard was right behind you. You're arrested violently.
        # - The target had a hidden knife. They fight back lethally.
        # - Bystanders intervene with overwhelming force.
        return ForcedOutcome(
            result="lethal_or_catastrophic",
            narration_directive=consequence,
            flag="[INTERVENTION]"  # narrator knows to make it brutal and fast
        )
    return None  # no intervention, proceed normally
```

---

## Part 5: Context Management Pipeline

### The Three Memory Layers

#### Layer 1 — World State (Always Current, Pure JSON)

```json
{
    "day": 47,
    "season": "late_autumn",
    "player_location": "tessam_ironDrum_f1_main",
    "player_health": 82,
    "player_hunger": 35,
    "companions": ["kael_id", "maren_id"],
    "active_quests": [],  
    "faction_standings": {"maritime_republic": 60, "northern_alliance": -20},
    "known_npcs": ["npc_42", "npc_108", ...],
    "antagonist_progress": 0.45,
    "major_events_occurred": ["siege_of_kaels_pass", "merchant_guild_split"],
    "player_reputation": {"tessam": "feared", "drava": "unknown"}
}
```

Updated by Python every turn. Never summarized. ~500-800 tokens. Always in context.

#### Layer 2 — Player Action Memory (Rolling Window, Summarized)

```
RECENT (last 10 turns) — verbatim action + outcome log:
  "Turn 44: Entered Iron Drum tavern. Met Maren (dockworker). 
   She mentioned the harbor closure."
  "Turn 45: Asked Maren about the closure. She suspects the 
   Maritime Republic is hiding something."
  ...

MEDIUM TERM (last 2-3 game days) — compressed summaries:
  "Day 45: Arrived in Tessam via the coast road. Encountered 
   bandits, surrendered gear. Found lodging at the Iron Drum. 
   Met Maren, learned about harbor closure and Republic secrecy."

LONG TERM (older) — key moments only:
  "Day 12: Killed a man in self-defense in Drava. Fled the city."
  "Day 23: Joined Kael as companion. He shared his deserter past."
  "Day 30: Betrayed the Merchant Guild by leaking trade routes."

FLAGGED (never compressed):
  "First kill: Day 12, Drava, self-defense"
  "Companion joined: Kael, Day 23"
  "Major betrayal: Merchant Guild, Day 30"
  "Romance: Maren, began Day 46"
```

**Summarizer runs every ~10 turns.** Cheap model (Gemini Flash) reads the recent log and compresses the oldest entries. Flagged moments are protected from compression.

Total context budget for player memory: ~1000-1500 tokens.

#### Layer 3 — Relationship Memory (Per-NPC, Sparse)

```json
{
    "npc_id": "npc_42",
    "name": "Maren Voss",
    "trust": 55,
    "attraction": 40,
    "interactions": 6,
    "persuasion_progress": 0.3,
    "flags": ["met_day_44", "shared_harbor_secret", "player_was_kind"],
    "knowledge_of_player": [
        "arrived recently from the south",
        "seems interested in the harbor situation",
        "was polite and listened"
    ],
    "last_interaction_summary": "Discussed harbor closure. Player 
     asked good questions. Maren opened up slightly."
}
```

This gets injected into the NPC's context ONLY when the player talks to them. Most NPCs have no relationship memory. Companions have the most.

### Context Assembly Per Turn

```
SYSTEM PROMPT (model-specific)         ~200-500 tokens
WORLD STATE (Layer 1)                  ~500-800 tokens
PLAYER MEMORY (Layer 2, recent only)   ~500-800 tokens
SCENE CONTEXT (location + NPCs)        ~200-400 tokens
NPC RELATIONSHIP (Layer 3, if talking)  ~100-300 tokens
LORE SNIPPET (if topic triggered)      ~50-150 tokens
─────────────────────────────────────
TOTAL PER CALL                         ~1500-3000 tokens input
```

Fits comfortably in any model's context window. Even Gemma 4.

### Tagged Lore Retrieval (Layer 2 of NPC Knowledge)

Characters have knowledge tags: `[educated, noble_family, academy_of_vael, skeptic]`.

When conversation topics match their tags, the system injects a small lore snippet:

```python
def get_relevant_lore(npc, conversation_topic):
    """Check if this NPC would know about the topic being discussed."""
    
    matching_tags = overlap(npc.knowledge_tags, topic.tags)
    
    if matching_tags:
        # Pull the specific lore entry (50-150 tokens)
        snippet = lore_index.get(matching_tags[0])
        return snippet  # injected into NPC context for this response only
    
    return None  # NPC doesn't know about this topic
```

The woman at the bar doesn't mention the philosopher until you say something that triggers it. Knowledge feels organic.

---

## Part 6: NPC Schedules and Ambient Life

### Time-of-Day Schedules

NPCs have simple routines stored as data:

```python
SCHEDULE_TEMPLATES = {
    "dockworker": {
        "dawn": "docks",
        "morning": "docks", 
        "afternoon": "market_or_home",
        "evening": "tavern",
        "night": "home"
    },
    "scholar": {
        "dawn": "home",
        "morning": "library_or_academy",
        "afternoon": "library_or_academy",
        "evening": "study_or_tavern",
        "night": "home"
    },
    "merchant": {
        "dawn": "warehouse",
        "morning": "shop",
        "afternoon": "shop",
        "evening": "guild_hall_or_home",
        "night": "home"
    }
}
# 5 time slots per day. Python moves NPCs between locations each slot.
# Disrupted by world events — if the shop burns down, the merchant 
# doesn't go to work.
```

### Ambient NPC Conversations

When the player does nothing or observes:

```python
def generate_ambient(scene, player_perception):
    """NPCs talk to each other. Player overhears fragments."""
    
    # Pick 1-2 NPC pairs in the scene
    pair = random.choice(possible_pairs(scene.npcs))
    
    # Generate a conversation fragment based on their stats and local events
    # Higher player perception = more complete fragment
    if player_perception > 70:
        fragment_completeness = "mostly_clear"
    elif player_perception > 40:
        fragment_completeness = "partial"
    else:
        fragment_completeness = "muffled"
    
    # Topics drawn from: local events, NPC occupations, gossip about 
    # high-fate characters, world events, personal gripes
    topic = select_ambient_topic(pair, local_events)
    
    return AmbientFragment(
        speakers=pair,
        topic=topic,
        completeness=fragment_completeness
        # Narrator renders: "...told him the bridge was out but he 
        # went anyway..." followed by laughter
    )
```

---

## Part 7: World Generation Pipeline

### Step 1: Opus Creates Meaning

One big Opus call with the World Builder prompt (see Part 3). Returns ~5,000-10,000 tokens of structured JSON: continents, regions, cities, factions, history, philosophy, named characters with fate scores.

### Step 2: Python Creates Space

```python
def generate_spatial_world(world_json):
    """Turn Opus's lore into coordinates and maps."""
    
    # Generate terrain using noise algorithms
    terrain = generate_terrain(
        continents=world_json["continents"],
        # Perlin noise for coastlines, mountains, forests
        # Climate descriptions map to biome types
    )
    
    # Place cities on valid terrain
    for city in all_cities:
        coords = place_city(
            terrain=terrain,
            city_type=city.economy,  # trade ports on coasts, etc.
            region_bounds=city.region.bounds,
            existing_cities=placed_cities,  # Poisson disk spacing
        )
        city.coordinates = coords
    
    # Generate roads between connected cities
    roads = connect_cities(cities, terrain)
    
    # Calculate travel times based on distance + terrain difficulty
    for road in roads:
        road.travel_days = calculate_travel_time(road, terrain)
    
    return SpatialWorld(terrain, cities, roads)
```

### Step 3: Python Generates Stats for Unnamed NPCs

```python
def populate_city(city, world_lore):
    """Generate NPC stat blocks for a city. No model calls."""
    
    population_count = city.population // 100  # abstract representation
    
    npcs = []
    for i in range(population_count):
        npc = generate_npc_stats(
            city=city,
            occupation=weighted_random(city.economy),  # trade city = more merchants
            social_class=weighted_random(city.social_distribution),
            fate=0.0  # unnamed NPCs get no fate
        )
        npcs.append(npc)
    
    return npcs
```

### Step 4: Opus Authors High-Fate Character Prompts

For each named character (30-50 from world builder), run the Character Author prompt. These can be batched during the loading screen.

### Step 5: Visual Asset Generation

During loading screen (player reads lore text):
1. World map from spatial data
2. Continent/region art (4-7 images)
3. Major NPC portraits (fate > 0.7)
4. Player character portrait
5. ~30-40 API calls total, batched

---

## Part 8: Player Creation

### Option A: Custom Character

Player provides real-world traits as free text:

> "24 years old, finance degree, into philosophy, Canadian, 5'2, 135 lbs, 
>  former wrestler, anxious but ambitious"

One Opus call maps these onto the world:

```
System: You receive a player's real-world self-description. Map their 
traits onto this game world's lore to create a character backstory that 
feels personal — like the player recognizing themselves in a fantasy mirror.

- Translate education to the world's equivalent institutions
- Translate skills to in-world abilities  
- Translate cultural background to a region that fits
- Translate personality to starting stats
- Give them a starting location that makes sense
- Give them a reason to be where they are (not "chosen one" — 
  something mundane that could become more)

Output: starting_stats, backstory (2-3 paragraphs), starting_location, 
starting_inventory, starting_relationships
```

### Option B: Generated Character

Player picks from archetypes or lets the game generate someone. Standard RPG character creation but with AI-generated backstory tied to world lore.

### Starting Stats

Player characters get higher base stats than random NPCs (you're the protagonist) but not absurdly so. Maybe base_mean=55 instead of 40. Traits from Option A skew specific stats (wrestler → high strength/toughness/agility, philosophy → high depth/wisdom).

---

## Part 9: Death, Saving, Persistence

### Death Philosophy

Death is real but **avoidable by a player who pays attention.**

**The game warns you before lethal situations:**
- The narrator telegraphs danger: "The five men stop talking and stare. Their hands move under the table."
- Companions voice concern: "I don't like this. We should leave."
- The stat engine gives escape chances — submitting to bandits costs money and weeks but you live.

**When you die:**
- Death letter generated: epilogue about the world after you
- Character and world are saved
- Option to restart as a new character in the same world, years later
- Your old character's actions are baked into the world state
- Your old companion is now a bitter mercenary. The bandit gang you joined controls the trade road. Your name is a legend or a cautionary tale.

### Save System

- Auto-save every N turns to JSON file
- World state + player state + all NPC states + relationship memories
- Entire generated world saved as a reusable seed
- Worlds can be shared — give someone your world file, they start fresh in your generated universe

---

## Part 10: Build Order

### Phase 1: The One Room (Prototype)

Build the minimum to see if 5 minutes feels alive.

```
[ ] World builder prompt → generate ONE city (not full world)
[ ] Stat schema implemented in Python (all 30 stats + fate)
[ ] NPC stat generation (random, with fate multiplier)
[ ] Interpreter (Flash/Gemma → structured action JSON)
[ ] Narrator (Sonnet → scene description)
[ ] One NPC with Opus-authored prompt, responds to dialogue
[ ] Basic social engine (trust tracking, simple persuasion)
[ ] Player input loop (terminal-based)
[ ] Scene assembly pipeline (build context, route to models)
```

**Success criteria:** Talk to one NPC for 10 minutes. Does it feel like a person in a place? If yes, the architecture works.

### Phase 2: The Stat Engine

```
[ ] Combat engine (auto-resolve + decision points)
[ ] Combat narration (Sonnet writes the fight scene)
[ ] Weapon-armor matrix
[ ] Companion combat participation (obedience/courage checks)
[ ] Movement engine (local movement within a city)
[ ] Perception engine (looking, eavesdropping)
[ ] Stealth engine (sneaking, pickpocketing)
[ ] Nonsense engine (in-world handling of gibberish)
[ ] Intervention layer (hardcoded content boundaries)
[ ] Injury and death system
```

**Success criteria:** Get in a fight. Does the auto-resolve + narration feel cinematic? Does death feel real?

### Phase 3: The Living City

```
[ ] Full city generation (districts, buildings, rooms)
[ ] Spatial tree with location tracking
[ ] NPC tier system (promotion/demotion on interaction)
[ ] NPC schedules (5 time slots, occupation-based)
[ ] Ambient NPC conversations (overheard fragments)
[ ] Local movement between buildings
[ ] Time-of-day effects on scenes
[ ] Trade engine (buying, selling)
[ ] Multiple NPCs in a scene simultaneously
```

**Success criteria:** Spend an in-game week in one city. Does it feel like a place with rhythms? Do you recognize people?

### Phase 4: The World

```
[ ] Full world builder (4-7 continents, complete lore)
[ ] Spatial world generation (terrain, coordinates, roads)
[ ] Travel engine (multi-day journeys with interruptions)
[ ] Director (daily world events, NPC movement, consequences)
[ ] Antagonist (strategic planning, separate model)
[ ] Faction system (standings, reputation, advancement)
[ ] Reputation spread between cities
[ ] Rumors about high-fate NPCs
[ ] Multiple cities with travel between them
```

**Success criteria:** Travel between two cities. Does the journey feel dangerous and real? Does the destination feel different from where you started?

### Phase 5: Depth

```
[ ] Romance engine (attraction, stages, intimacy)
[ ] Companion system (travel chatter, opinions, loyalty, can leave)
[ ] Persuasion engine (full evaluation pipeline)
[ ] Conversations as currency (knowledge unlocks doors)
[ ] Philosophical NPC conversations (tracked positions)
[ ] The drunk philosopher character type
[ ] Death letters (epilogue generation)
[ ] World persistence (restart as new character in same world)
[ ] Player creation (real traits → game character)
[ ] Context management pipeline (3-layer memory, summarizer)
[ ] Tagged lore retrieval (per-NPC knowledge injection)
```

### Phase 6: Polish and Visuals

```
[ ] Visual map generation (from spatial tree)
[ ] Character portraits (pre-generated library + key NPCs)
[ ] Scene illustrations (asset library selection)
[ ] Loading screen with lore text
[ ] Cinematic mode (real-time image gen at key moments)
[ ] Sound? Music? (TBD)
[ ] Web frontend vs terminal (TBD)
[ ] Save/load system
[ ] World sharing (export/import world files)
```

### Phase 7: Testing and Tuning

```
[ ] Hundreds of "what if X" scenarios
[ ] Stat balance testing (is combat too easy? too hard?)
[ ] Persuasion threshold tuning
[ ] Director event frequency tuning
[ ] Cost optimization (are we overspending on any call?)
[ ] Context window stress testing (does quality degrade at turn 200?)
[ ] Model substitution testing (can Gemma handle Tier 1 NPCs?)
[ ] Edge case catalog (eat the building, seduce the table, etc.)
```

---

## Appendix: Open Questions

Things we haven't decided yet:

1. **Game name** — leaning Loom
2. **Default genre/setting** — medieval dark fantasy? or genre selection at world creation?
3. **Multiplayer** — parked for now, but world-sharing is a stepping stone
4. **Monetization** — subscription? per-session? free tier?
5. **Platform** — terminal prototype first, then web? mobile?
6. **Post-endgame content** — what happens after the war? Director generates new tensions, but the design needs specifics
7. **Difficulty settings** — should fate density be adjustable? combat lethality? antagonist intelligence?
8. **Accessibility** — text-to-speech? font sizes? colorblind considerations?
9. **Mod support** — custom world builder prompts? custom stat schemas? community NPCs?
10. **How many simultaneous companions** — 1? 3? unlimited but they argue with each other?
