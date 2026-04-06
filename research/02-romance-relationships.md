# Romance & Relationship Mechanics Research
## Compiled April 5, 2026

---

## 1. BioWare: Dragon Age Approval

### Origins
- **Scale:** -100 to +100
- **Romance states:** Neutral → Interested → Care → Adore → Love
- **Hard cap at 74** unless Friendly status or active romance (last 26 points gated behind personal quest)
- **Departure at -100** (one chance to talk them out)
- **Companion stat bonuses** tied to approval tiers (each companion boosts one stat)
- **Gifts:** Preferred categories give more points. Diminishing returns on repeats.
- **Romance = approval threshold + specific dialogue flags.** Not purely numeric.

### Dragon Age II
- **200-point meter** (-100 Rivalry to +100 Friendship)
- **Both extremes are good.** Max Friendship = trusted friend. Max Rivalry = respectful opposition. Middle is worst.
- Different bonuses for Friendship vs Rivalry path.

### Inquisition: Hidden meter. Veilguard: Visible meter returns.

---

## 2. Mass Effect: Binary Loyalty + Romance Flags

- Romance tracked as **boolean flags** in save file, not numeric scores
- Loyalty in ME2: **binary** (loyal/not loyal), unlocked via personal mission
- Loyalty affects suicide mission survival, unlocks power + outfit
- **Conflict resolution** requires sufficient Paragon/Renegade score — failing loses one companion's loyalty permanently
- Romance sequence: conversation post-loyalty → flirt option → lock-in or back-out
- Save file fields: `RomanceAvailable_[Character]` (bool), `RomanceState_[Character]` (progression), `PC Relationship` (0-100)

---

## 3. Baldur's Gate 3

- **Scale:** -50 to +100
- **Thresholds:** Very Low (-49 to -40), Low (-39 to -20), Neutral (-19 to 20), Medium (21-40), High (41-60), Very High (61-80), Exceptional (81-100)
- **Deltas:** ±1 (small), ±5 (medium), ±10 (large), up to ±20 for major quests
- **Departure at -50**, warnings at -20 and -40
- **Romance requires** approval threshold AND specific narrative dialogue nodes
- Design note: Approval popups exist because Larian "can't just let players break party members" — the number compresses infinite branching

---

## 4. Dwarf Fortress: Full Relationship Graph

The most mechanically detailed system.

### Core: Non-Reciprocal
Every entity has independent relationships with every interacted entity. A→B feelings are separate from B→A.

### Rank System (via idle chats)
Two dwarves on adjacent tiles who are idle will chat, incrementing rank.
- Rank 15: Friendship or grudge forms (depends on compatibility)
- Rank ~40: If friends + romantically compatible → lovers
- Rank 50: If lovers + willing → marriage

### Compatibility Calculation (3 axes)
1. **Shared preferences** (materials, creatures) → positive
2. **Shared skills** → positive  
3. **Personality facet alignment** (24 of 51 facets are relationship-active):
   - Both >60 or both <40 → positive compatibility
   - One >60, other <40 → negative (grudge pressure)
   - Only personality divergence causes grudges, never preferences/skills

### The 24 Relationship-Active Facets
VIOLENT, WASTEFULNESS, DISCORD, FRIENDLINESS, POLITENESS, VANITY, AMBITION, GRATITUDE, IMMODESTY, HUMOR, VENGEFUL, CRUELTY, HOPEFUL, CURIOUS, PERFECTIONIST, TOLERANT, ALTRUISM, DUTIFULNESS, THOUGHTLESSNESS, ORDERLINESS, EXCITEMENT_SEEKING, IMAGINATION, ABSTRACT_INCLINED, ART_INCLINED

### Additional Facets (affect formation speed)
- LOVE_PROPENSITY — how readily falls in love
- EMOTIONALLY_OBSESSIVE — depth of attachment
- GREGARIOUSNESS — frequency of socializing (chat opportunities)

### Affection Scale
100 = Kindred spirit, 75+ = Close friend, 50-74 = Friend, -50 to -74 = Disliked, -75 to -99 = Hated, -100 = Pure hate

### Decay
Dwarves who don't chat lose acquaintance status. Skill changes can alter compatibility.

**Key insight:** Social skills don't affect relationship formation. Only personality alignment and shared context matter.

---

## 5. Crusader Kings 3: Opinion System

### Opinion = Sum of Modifiers (positive and negative)
- Same trait: +10 to +20
- Opposite trait: -10 to -15

### Attraction (separate axis)
Beautiful/Handsome: +30, Ugly: -20, Hideous: -30

### AI Behavioral Hidden Values
Each trait gives hidden modifiers: Zealous = +200 Zeal -20 Rationality, Brave = +200 Boldness -35 Rationality, Ambitious = +200 Greed +200 Honor

### CK3 separates three axes:
1. **Opinion** (do I like you?)
2. **Attraction** (am I drawn to you?)
3. **AI behavioral tendencies** (what kind of person am I?)

---

## 6. Persona: Social Links / Confidants

- **10 ranks per link.** Hidden affinity points accumulate from dialogue choices.
- Good answer: ~15 points. Great answer: ~30 points.
- **Multipliers:** Matching Arcana Persona (x1.51), top exam score (x1.51), max Charm (x1.51)
- **Reversals** (P3 only, removed in P5): wrong answers or neglect. Most players found them punitive, not dramatic.
- **Essentially a hidden progress bar with dialogue as input.** Multipliers reward engagement breadth.

---

## 7. Disco Elysium: Dialogue IS the Mechanic

### Skill Check: `skill_value + 2d6 vs. difficulty`
- Passive checks: `skill + modifiers + 6 ≥ threshold` (no dice, auto-fire)
- White (active): dice rolled, retryable after skill point investment
- Red (active): ONE attempt, permanent

### Modifier Accumulation (the key mechanic)
Modifiers on any check come from: previous dialogue choices (up to 10 per check), clothes worn, thoughts internalized, drugs/alcohol, items, environmental observations.

### Kim Kitsuragi Reputation
Hidden numeric score built entirely through conversation:
- Rep > 0: "+1 modifier: The lieutenant trusts you"
- Rep > 7: "+2 modifier: The lieutenant *truly* trusts you"
- Rep < -5: "-1 modifier: The lieutenant *really* doesn't trust you"

**Key insight:** No separate "relationship score" needed if dialogue system is rich enough. Every choice becomes a potential ±1 on future checks.

---

## 8. Firewatch: Micro-Choice Tracking

- **10,000 tracked events** including speech and environmental interactions
- System picks "the truest and most specific thing that can happen next" based on accumulated state
- Whether you picked up a bottle before/after looking out a window is tracked
- **Interruptibility:** Cutting Delilah off means you know less about her AND may close future paths
- No approval popups, no visible meters — just accumulated micro-state

---

## 9. Stardew Valley (Clean Reference)

- **Scale:** 0 to 2500 (10 hearts, 250/heart). Spouses: 3500 (14 hearts).
- **Gift formula:** `Event_Multiplier × Preference × Quality_Multiplier`
- Loved (80) × Birthday (8x) × Iridium (1.5x) = 960 points max single gift
- Talking = +20/day. Decay daily if no interaction (unless maxed).
- Heart events at 2, 4, 6, 8, 10 thresholds.

---

## 10. CiF-CK / Comme il Faut (Academic)

Most rigorous framework. Deployed as Skyrim mod ("Social NPCs").

### Four Components:
1. **Social Networks** — Non-reciprocal scalar values. Two networks: Attraction and Friendship. Characters maintain Theory of Mind (beliefs about others' values, which can be wrong).
2. **Social Exchanges** — All possible actions (flirt, insult, ask out). Each has preconditions and consequences. Stages: dormant → initiated → performed → succeeded/failed.
3. **Volition Calculation:** `for each microtheory: if precondition true: volition += value. Execute exchange with highest positive volition.`
4. **Trigger Rules** — Fire after exchanges, updating social state.

**Prom Week** used same engine: 5,000 social considerations, 900 story instantiations, 18 characters. Pure social physics as gameplay.

---

## Synthesis for Loom

1. **Multi-axis relationships are validated.** CK3 (Opinion/Attraction/Behavioral), DF (24 facets), CiF-CK (Attraction + Friendship networks). Our trust/suspicion/attraction/fear/debt is in good company.
2. **Non-reciprocal is essential.** Both DF and CiF-CK do this. A's feelings toward B ≠ B's toward A.
3. **Thresholds trigger state changes.** DF at 15/40/50, BG3 at -50/-20/20/40/60/80, Persona at rank breakpoints. Below/above a threshold, the number barely matters. AT the threshold, everything changes.
4. **Flags alongside numbers.** ME's romance = boolean flags + approval. BG3 = threshold + narrative triggers. Use both continuous scores AND discrete flags.
5. **Conversation as input aligns with DE and Firewatch.** LLM interpreter assessing player words → relationship deltas is richer than either approach.
