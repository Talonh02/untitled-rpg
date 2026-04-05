# Game Mechanics — The Actual Math

Every formula, every number, every curve. No pseudocode. Real math you can implement.

---

## 1. Stat Generation

### Base Distribution

Every NPC stat (0-100) is drawn from a normal distribution. Most people are average. Extraordinary people are rare.

```
Base distribution: mean = 42, std = 16
```

This gives roughly:
- 68% of people score 26-58 (ordinary)
- 95% of people score 10-74 (almost everyone)
- 2.5% score above 74 (notably talented)
- 0.1% score above 90 (exceptional)

### Fate Influence on Stats

Fate doesn't add a flat bonus. It **reshapes the distribution** — pulling the mean upward and widening the variance. A fate-touched person has *higher ceiling AND more variance*. They're not uniformly great; they have spikes and valleys, which makes them interesting.

```
For a given NPC with fate f (0.0 to 1.0):

    stat_mean = 42 + (f * 30)
    stat_std  = 16 + (f * 8)
    
    raw_roll = clamp(gaussian(stat_mean, stat_std), 0, 100)
```

| Fate | Effective Mean | Effective Std | Typical Range | Feel |
|------|---------------|--------------|---------------|------|
| 0.0 | 42 | 16 | 26-58 | Ordinary person |
| 0.2 | 48 | 19.6 | 28-68 | Slightly above average, some quirks |
| 0.4 | 54 | 22.4 | 32-76 | Noticeable. Good at something. |
| 0.6 | 60 | 24.8 | 35-85 | Clearly talented. Stands out. |
| 0.8 | 66 | 28.8 | 37-95 | Remarkable. Multiple high stats. |
| 0.95 | 70.5 | 23.6 | 47-94 | World-class. Deep contradictions. |
| 1.0 | 72 | 24 | 48-96 | Once-per-game. Stats rarely below 50. |

### Occupation Stat Modifiers

After rolling base stats, occupation pulls specific stats in its direction. A soldier doesn't re-roll — their strength and toughness get a nudge.

```
modifier = occupation_bonus[stat_name]  # typically +5 to +15
stat = clamp(raw_roll + modifier, 0, 100)
```

| Occupation | Boosted Stats (+10-15) | Suppressed Stats (-5-10) |
|------------|----------------------|------------------------|
| Soldier | strength, toughness, courage | education, creativity |
| Scholar | intelligence, education, depth | strength, toughness |
| Merchant | charisma, perception, ambition | courage, creativity |
| Farmer | toughness, wisdom, loyalty | education, ambition |
| Thief | agility, perception, creativity | honesty, loyalty |
| Priest | willpower, empathy, education | agility, ambition |
| Noble | education, charisma, ambition | toughness, empathy |
| Artist | creativity, depth, empathy | strength, stubbornness |
| Blacksmith | strength, toughness, willpower | charisma, education |
| Healer | empathy, wisdom, perception | strength, ambition |
| Spy | perception, agility, charisma | honesty, loyalty |
| Beggar | perception, courage, creativity | education, wealth |

### Social Class → Wealth and Education Floors

```
destitute:  wealth 0-15,   education 0-20
working:    wealth 10-40,  education 5-40
merchant:   wealth 35-75,  education 25-65
noble:      wealth 60-95,  education 50-85
royal:      wealth 85-100, education 70-95
```

These are hard floors/ceilings overlaid after rolling. A noble can't have education 10 (they had tutors). A beggar can't have wealth 80.

### Stat Correlations

Some stats should loosely correlate. Not perfectly — contradictions are what make characters interesting — but a trend.

```
After rolling all stats independently, apply soft correlations:

If intelligence > 70 AND education < 30:
    # Naturally smart but uneducated — interesting, keep it (30% chance)
    # Otherwise nudge education up slightly (70% chance)
    if random() > 0.3: education += random(5, 15)

If empathy > 70 AND honesty < 30:
    # Empathetic but dishonest — manipulator archetype, keep it (40% chance)
    if random() > 0.4: honesty += random(5, 10)

If courage > 80 AND agility < 25:
    # Brave but slow — the tank, always valid, no correction

If depth > 75 AND humor < 20:
    # Deep but humorless — valid archetype, no correction

If charisma > 80 AND empathy < 20:
    # Charming but cold — sociopath archetype, ALWAYS keep this
```

The point: let most contradictions survive. They're features, not bugs. Only correct the ones that feel genuinely incoherent (smart person with zero education should be rare, not impossible).

### Age Modifiers

Age affects stats. A 70-year-old isn't as strong as a 25-year-old, but may be wiser.

```
age_physical_modifier:
    age < 18:  strength *= 0.7, toughness *= 0.8, agility *= 0.9
    age 18-35: no change (peak physical)
    age 36-50: strength *= 0.9, agility *= 0.95
    age 51-65: strength *= 0.75, agility *= 0.8, toughness *= 0.85
    age > 65:  strength *= 0.6, agility *= 0.65, toughness *= 0.7

age_mental_modifier:
    age < 25:  wisdom *= 0.7, depth *= 0.8
    age 25-40: wisdom *= 0.9
    age 41-60: wisdom += 10, depth += 5, perception += 5
    age > 60:  wisdom += 15, depth += 10, perception -= 5 (senses fade)
```

---

## 2. Character Scaling (Continuous, Not Tiered)

### The Depth Score

This is the single number that determines how much computational soul a character gets.

```python
depth_score = (
    depth * 0.30 +          # inner life richness — heaviest weight
    intelligence * 0.20 +    # reasoning ability
    wisdom * 0.15 +          # life experience, judgment
    empathy * 0.15 +         # emotional awareness
    creativity * 0.10 +      # novel thinking
    education * 0.10          # knowledge breadth
)
# Result: 0.0 to 100.0
```

### Continuous Prompt Length

Prompt length scales **linearly** with depth score. No buckets.

```
prompt_tokens = 40 + (depth_score * 14)
```

| Depth Score | Prompt Tokens | What That Buys You |
|-------------|---------------|--------------------|
| 5 | 110 | Name, occupation, one personality trait, speech style hint |
| 20 | 320 | Personality, mood, basic speech pattern, one want |
| 40 | 600 | Full personality, backstory seed, a secret, speech patterns, what they care about |
| 60 | 880 | Rich inner life, contradictions, opinions, emotional triggers, knowledge scope |
| 80 | 1160 | Deep portrait with philosophical leanings, unresolved questions, layered secrets |
| 95 | 1370 | Complete human being. The Opus-authored masterpiece. |
| 100 | 1440 | Maximum richness. |

### Continuous Response Length Guidance

Built into the character prompt by the Character Author:

```
max_response_words ≈ 15 + (depth_score * 1.5)
```

| Depth Score | Approximate Max Words | Feel |
|-------------|----------------------|------|
| 10 | 30 | "Yeah." / "The road's that way." |
| 25 | 52 | A sentence or two. Gets to the point. |
| 40 | 75 | Short paragraph. Expresses a thought. |
| 60 | 105 | Full response. Has opinions. Might surprise you. |
| 80 | 135 | Gives you something to think about. |
| 95 | 157 | Sometimes gives unprompted reflections. Multi-paragraph when moved. |

These are guidelines the Character Author bakes into the prompt, not hard limits. A depth-20 NPC might say more when scared or angry. A depth-90 NPC might be terse when they don't trust you.

### Model Selection (Fuzzy Boundaries)

The model tier is discrete — you have to pick one. But the **boundaries are fuzzy** with a random roll, so there's no clean line between "worth talking to" and "not worth talking to."

```python
def select_model(depth_score, fate):
    # Fate gives a small boost to model selection (not just stats)
    effective_score = depth_score + (fate * 10)
    
    # Add randomness so boundaries aren't crisp
    roll = effective_score + random.uniform(-8, 8)
    
    if roll < 30:
        return "flash_lite"      # ~55% of NPCs
    elif roll < 52:
        return "flash"           # ~25% of NPCs
    elif roll < 72:
        return "sonnet"          # ~13% of NPCs
    elif roll < 88:
        return "sonnet_rich"     # ~5% of NPCs (same model, more context)
    else:
        return "opus"            # ~2% of NPCs
```

**Why fuzzy matters:** A depth-28 NPC (normally Flash Lite) has a ~15% chance of rolling into Flash territory. That means occasionally a seemingly ordinary person surprises you with an unexpectedly interesting response. And a depth-32 NPC has a ~15% chance of landing on Flash Lite and being duller than expected. **People aren't predictable. The randomness IS the realism.**

### The Character Author as Continuous Translator

The Character Author (Opus) receives the raw depth score and all stats. It doesn't see tiers. It sees: "depth 47, intelligence 62, empathy 31, education 55, creativity 28."

Its job is to **translate those specific numbers into a specific person.** A depth-47 is not a depth-52 — Opus writes a qualitatively different prompt for each. The continuous range of possible stat combinations produces a continuous range of possible personalities.

Opus should think in terms of these qualitative bands (but these are guidelines for Opus, not hard cutoffs):

```
depth_score 0-15:   "Thinks in simple terms. Doesn't question much. 
                     Present-focused. Might be content, might be dull."

depth_score 15-30:  "Has basic opinions but doesn't examine them. 
                     Can be funny, can be mean, can be kind — but 
                     not complex about it."

depth_score 30-50:  "Has a real personality. Notices things sometimes.
                     Might surprise you once in a conversation but 
                     won't sustain it."

depth_score 50-70:  "Genuinely thoughtful. Has examined their own 
                     life to some degree. Can hold a real conversation
                     about ideas. Has at least one opinion that would
                     make you pause."

depth_score 70-85:  "Rich inner life. Contradictions they're aware of.
                     Can articulate complex feelings. Reads people well.
                     The kind of person you'd remember meeting."

depth_score 85-100: "The person who changes how you think about 
                     something. Deeply self-aware, or deeply unaware
                     in a fascinating way. Has wrestled with questions
                     they can't answer. A voice unlike anyone else."
```

---

## 3. Combat Math

### Combatant Power Rating (CPR)

Every participant in a fight gets a single power number.

```
CPR = (strength * 0.25) + (agility * 0.25) + (toughness * 0.20) +
      (courage * 0.10) + (perception * 0.10) + (willpower * 0.10)

# Then multiply by weapon and armor factors
CPR = CPR * weapon_multiplier * armor_multiplier
```

An average adult (stats ~42 across the board): CPR ≈ 42
A trained soldier (boosted physical stats ~65): CPR ≈ 65
An elite warrior (stats 75-90): CPR ≈ 80-90

### Weapon Multipliers

Base weapon multiplier when unarmored. The weapon-armor matrix modifies this.

| Weapon | Base Multiplier | Speed | Notes |
|--------|----------------|-------|-------|
| Unarmed | 0.6 | Fast | Floor — anyone can punch |
| Dagger | 0.8 | Fast | Good for stealth, bad for open combat |
| Short sword | 1.0 | Medium | Baseline weapon |
| Long sword | 1.15 | Medium | Standard military weapon |
| Two-handed sword | 1.3 | Slow | High damage, leaves you exposed |
| Spear | 1.1 | Medium | Reach advantage, good in formation |
| Mace/Club | 1.05 | Medium | Armor-penetrating |
| War axe | 1.2 | Slow | High damage |
| Bow | 1.1 | N/A | Ranged — separate calculation |
| Crossbow | 1.25 | Slow | Powerful but slow to reload |

### Weapon vs Armor Effectiveness Matrix

This multiplier modifies the weapon's base. Values < 1.0 mean the weapon is bad against that armor. Values > 1.0 mean it's particularly effective.

|  | None | Leather | Chain | Plate |
|--|------|---------|-------|-------|
| **Unarmed** | 1.0 | 0.6 | 0.3 | 0.15 |
| **Dagger** | 1.0 | 0.8 | 0.4 | 0.2 |
| **Short sword** | 1.0 | 0.9 | 0.65 | 0.4 |
| **Long sword** | 1.0 | 0.95 | 0.7 | 0.5 |
| **2H sword** | 1.0 | 1.0 | 0.8 | 0.6 |
| **Spear** | 1.0 | 0.9 | 0.6 | 0.45 |
| **Mace/Club** | 0.9 | 0.95 | 1.0 | 0.85 |
| **War axe** | 1.0 | 1.0 | 0.85 | 0.7 |
| **Bow** | 1.0 | 0.85 | 0.5 | 0.3 |
| **Crossbow** | 1.0 | 0.95 | 0.75 | 0.55 |

**Key takeaways the player would learn:**
- Maces are the only thing good against everything
- Don't bring a dagger to a plate-armored fight
- Bows are devastating against unarmored but useless against plate
- Two-handed swords are the best all-around but leave you exposed (no shield)

### Armor Defense Rating

Armor adds a flat defense that reduces incoming effective CPR:

```
none:    0
leather: 8
chain:   18
plate:   30
```

### Full Combat Resolution

```python
def resolve_combat(player_side, enemy_side, context):
    """
    Returns outcome for the entire encounter.
    player_side: list of combatants (player + companions who participate)
    enemy_side: list of enemy combatants
    context: terrain, sneak_attack, etc.
    """
    
    # 1. Calculate each side's total effective power
    player_total = 0
    for c in player_side:
        cpr = calculate_cpr(c)
        weapon_armor_mod = WEAPON_ARMOR_MATRIX[c.weapon][enemy_armor_avg]
        cpr *= weapon_armor_mod
        player_total += cpr
    
    enemy_total = 0
    for e in enemy_side:
        cpr = calculate_cpr(e)
        weapon_armor_mod = WEAPON_ARMOR_MATRIX[e.weapon][player_armor_avg]
        cpr *= weapon_armor_mod
        enemy_total += cpr
    
    # 2. Apply context modifiers
    if context.sneak_attack:
        player_total *= 1.4    # 40% bonus for surprise
    if context.player_fatigued:
        player_total *= 0.85   # 15% penalty when tired
    if context.terrain == "narrow" and len(enemy_side) > len(player_side):
        # Narrow terrain negates numbers advantage
        enemy_total *= (len(player_side) / len(enemy_side)) ** 0.3
    if context.darkness:
        # Both sides penalized but perception helps
        player_total *= 0.8 + (player.perception / 500)
        enemy_total *= 0.8 + (avg_enemy_perception / 500)
    
    # 3. Numbers advantage (diminishing returns)
    # 2v1 isn't 2x power, it's ~1.5x (they get in each other's way)
    player_numbers = len(player_side)
    enemy_numbers = len(enemy_side)
    if player_numbers > enemy_numbers:
        ratio = player_numbers / enemy_numbers
        player_total *= 1 + (math.log2(ratio) * 0.4)  
        # 2v1 = 1.4x, 3v1 = 1.63x, 5v1 = 1.93x
    elif enemy_numbers > player_numbers:
        ratio = enemy_numbers / player_numbers
        enemy_total *= 1 + (math.log2(ratio) * 0.4)
    
    # 4. Add randomness (±20%)
    player_roll = player_total * random.uniform(0.8, 1.2)
    enemy_roll = enemy_total * random.uniform(0.8, 1.2)
    
    # 5. Calculate margin
    total = player_roll + enemy_roll
    if total == 0: total = 1  # prevent div by zero
    
    margin = (player_roll - enemy_roll) / total
    # margin ranges from roughly -1.0 (total defeat) to +1.0 (total victory)
    # In practice, usually -0.5 to +0.5
    
    # 6. Check for decision point
    if abs(margin) < 0.08 and context.stakes != "trivial":
        return CombatDecisionPoint(margin=margin, ...)
    
    # 7. Determine outcome
    return resolve_outcome(margin, player_side, enemy_side, context)
```

### Outcome Determination from Margin

```
margin > +0.30:  DECISIVE VICTORY — you dominated
margin +0.15 to +0.30:  COMFORTABLE VICTORY — clear win, minor costs
margin +0.03 to +0.15:  NARROW VICTORY — won but it cost you
margin -0.03 to +0.03:  STANDOFF / DECISION POINT — could go either way
margin -0.15 to -0.03:  NARROW DEFEAT — you lost but survived
margin -0.30 to -0.15:  CLEAR DEFEAT — beaten badly
margin < -0.30:  CRUSHING DEFEAT — lucky to be alive
```

### Injury System

Injuries are rolled based on margin. Worse margin = more and worse injuries.

```python
def roll_injuries(margin, combatant, enemy_weapons):
    """Determine injuries for one combatant."""
    
    # Base injury chance depends on margin
    # Even winners can get hurt
    if margin > 0.30:
        injury_chance = 0.1       # 10% chance of any injury in decisive win
    elif margin > 0.15:
        injury_chance = 0.3
    elif margin > 0.03:
        injury_chance = 0.6
    elif margin > -0.03:
        injury_chance = 0.75
    elif margin > -0.15:
        injury_chance = 0.9
    else:
        injury_chance = 0.98      # almost certain injury in bad defeat
    
    if random.random() > injury_chance:
        return []  # no injuries
    
    # How bad? Roll severity.
    severity_roll = random.random()
    armor_reduction = combatant.armor_rating / 100  # 0.0 to 0.30
    severity_roll -= armor_reduction  # armor reduces severity
    
    if severity_roll < 0.3:
        return [random.choice(MINOR_INJURIES)]
    elif severity_roll < 0.65:
        return [random.choice(MODERATE_INJURIES)]
    elif severity_roll < 0.85:
        return [random.choice(SERIOUS_INJURIES)]
    else:
        return [random.choice(CRITICAL_INJURIES)]

MINOR_INJURIES = [
    {"name": "bruised ribs", "effect": "strength -5 for 3 days"},
    {"name": "black eye", "effect": "perception -3 for 2 days"},
    {"name": "split lip", "effect": "charisma -3 for 1 day"},
    {"name": "twisted ankle", "effect": "agility -5 for 3 days"},
    {"name": "scratches", "effect": "none, cosmetic"},
]

MODERATE_INJURIES = [
    {"name": "deep cut on arm", "effect": "strength -10 for 7 days"},
    {"name": "cracked ribs", "effect": "strength -8, agility -5 for 10 days"},
    {"name": "concussion", "effect": "intelligence -10, perception -8 for 5 days"},
    {"name": "sprained wrist", "effect": "weapon_multiplier * 0.7 for 7 days"},
    {"name": "gash on leg", "effect": "agility -12 for 7 days"},
]

SERIOUS_INJURIES = [
    {"name": "broken arm", "effect": "cannot use two-handed weapons for 20 days, strength -15"},
    {"name": "broken ribs", "effect": "strength -15, agility -10 for 15 days"},
    {"name": "deep stab wound", "effect": "health -20, needs treatment or worsens"},
    {"name": "shattered knee", "effect": "agility -20 for 25 days, permanent -3"},
    {"name": "fractured skull", "effect": "intelligence -15 for 20 days, risk of death if untreated"},
]

CRITICAL_INJURIES = [
    {"name": "severed hand", "effect": "permanent. weapon_multiplier * 0.5. no shield."},
    {"name": "blinded in one eye", "effect": "permanent. perception -20. ranged accuracy halved."},
    {"name": "crushed leg", "effect": "permanent agility -25. travel speed halved."},
    {"name": "gutted", "effect": "death in 1 day without immediate treatment"},
    {"name": "spine damage", "effect": "permanent strength -20, agility -20"},
]
```

### Death Rolls

```python
def roll_death(margin, combatant, context):
    """Should this combatant die?"""
    
    # Death base chance from margin
    if margin > 0.15:
        death_chance = 0.0    # winners almost never die
    elif margin > 0.03:
        death_chance = 0.02   # narrow winners: 2%
    elif margin > -0.03:
        death_chance = 0.05   # standoff: 5%
    elif margin > -0.15:
        death_chance = 0.12   # narrow losers: 12%
    elif margin > -0.30:
        death_chance = 0.25   # clear losers: 25%
    else:
        death_chance = 0.45   # crushed: 45%
    
    # Toughness and willpower reduce death chance
    survival_factor = (combatant.toughness + combatant.willpower) / 200
    death_chance *= (1 - survival_factor * 0.4)
    # A tough+willful (both 80) character reduces death chance by ~32%
    
    # Armor reduces death chance
    death_chance *= (1 - combatant.armor_rating / 100)
    # Full plate (30) reduces death chance by 30%
    
    # THE PLAYER GETS A SURVIVAL BONUS (protagonist advantage)
    if combatant.is_player:
        death_chance *= 0.5  # halved for player
        # Plus: always offer an escape or surrender before death
        if random.random() < death_chance:
            return "near_death_choice"  # decision point, not instant death
    
    return random.random() < death_chance
```

### Decision Points (Mid-Combat Choices)

When the margin is close (-0.08 to +0.08) or the player is about to die, the combat engine pauses and asks for player input.

```python
DECISION_POINT_SCENARIOS = [
    {
        "trigger": "margin_close",
        "prompt": "The fight could go either way. {enemy} has you pinned "
                  "but is tiring. What do you do?",
        "options_interpreted_by_model": True,
        # Player types freely. Interpreter parses.
        # Smart choices (gouge eyes, use environment) give +0.05 to +0.15 margin bonus
        # Bad choices (hesitate, plead) give -0.05 to -0.10
        # The interpreter model rates the choice:
        #   clever/tactical: +0.10 to +0.15
        #   aggressive: +0.05 (straightforward but effective)
        #   defensive: +0.02 (plays it safe, slight advantage)
        #   passive/pleading: -0.05 (shows weakness)
        #   reckless: random(-0.10, +0.15) (high variance)
    },
    {
        "trigger": "companion_endangered",
        "prompt": "{companion} is about to take a killing blow. "
                  "You can intervene but it leaves you exposed.",
        # Choosing to save companion: companion lives, player takes
        # an automatic injury roll (moderate+)
        # Choosing self-preservation: companion makes their own death roll
    },
    {
        "trigger": "player_near_death",
        "prompt": "You're losing badly. Blood in your eyes. "
                  "You can try to flee, surrender, or fight to the death.",
        # Flee: agility check. Success = escape with injuries. 
        #   Fail = death roll at -0.05 penalty.
        # Surrender: combat ends. Consequences depend on who you're fighting.
        #   Bandits: robbed, possibly captured for days/weeks.
        #   Soldiers: imprisoned.
        #   Assassin: they might kill you anyway (depends on their goal).
        # Fight to death: final death roll at current margin. 
        #   Small chance of miraculous reversal (+0.05 willpower bonus).
    }
]
```

### Companion Combat Participation

```python
def check_companion_participation(companion, context):
    """Does this companion actually fight?"""
    
    # Willingness score (0-100)
    willingness = (
        companion.relationship.trust * 0.35 +   # do they trust you?
        companion.stats.loyalty * 0.25 +          # are they loyal in general?
        companion.stats.courage * 0.25 +          # are they brave?
        companion.stats.ambition * 0.15            # do they want glory?
    )
    
    # Modifiers
    if context.player_started_fight:
        willingness -= 15    # they didn't ask for this
    if context.defending_from_attack:
        willingness += 20    # self-preservation kicks in
    if context.enemy_count > 4:
        willingness -= 10    # overwhelming odds are scary
    if companion.has_grudge_against(context.enemy):
        willingness += 25    # personal motivation
    
    # Roll
    participation_roll = random.uniform(0, 100)
    
    if participation_roll < willingness:
        # They fight
        if willingness - participation_roll > 30:
            return "fights_bravely"   # bonus: +5% to their CPR
        else:
            return "fights_reluctantly"  # no bonus, might freeze mid-combat
    else:
        # They don't fight
        if companion.stats.courage < 30:
            return "fled"             # ran away
        elif companion.stats.honesty > 60:
            return "refused"          # told you no (honest about it)
        else:
            return "froze"            # wanted to help, couldn't move
    
    # Each of these becomes a narrative moment for Sonnet
```

---

## 4. Persuasion Math

### Argument Evaluation (Model Call)

The interpreter (or a dedicated evaluator) scores the player's argument on 4 dimensions, each 0.0-1.0:

```
relevance:    Does this argument address what the NPC actually cares about?
coherence:    Is the argument logically sound? Does it make sense?
tone_match:   Is the tone appropriate for this NPC? (humor for a jovial NPC, 
              gravity for a serious one, respect for a proud one)
info_valid:   Does the player reference information they actually have?
              (checked against player.knowledge_log)
```

### Persuasion Delta (Per Exchange)

```python
def calculate_persuasion_delta(evaluation, npc, relationship):
    """How much does this exchange move the needle?"""
    
    # Base argument strength (0.0 to 1.0)
    argument_strength = (
        evaluation.relevance * 0.35 +
        evaluation.coherence * 0.25 +
        evaluation.tone_match * 0.25 +
        evaluation.info_valid * 0.15
    )
    
    # NPC resistance (0.0 to 1.0, higher = harder to persuade)
    resistance = (
        npc.stats.stubbornness * 0.40 +
        npc.stats.willpower * 0.30 +
        (100 - npc.stats.empathy) * 0.15 +  # low empathy = harder to reach
        npc.stats.faction_loyalty * 0.15      # faction-loyal people resist harder
    ) / 100
    
    # Trust bonus (0.0 to 0.3) — built over multiple interactions
    trust_bonus = (relationship.trust / 100) * 0.3
    
    # Calculate delta
    delta = (argument_strength - resistance + trust_bonus) * 20
    # Typical range: -10 to +15 per exchange
    
    # Clamp — one exchange can't do everything
    delta = clamp(delta, -12, 18)
    
    # Bluffing penalty
    if not evaluation.info_valid and evaluation.references_specific_info:
        # They claimed to know something they don't
        delta -= 8
        # NPC's perception check for detecting the lie:
        if roll(npc.stats.perception) > roll(player.stats.charisma):
            delta -= 15  # caught lying — massive trust damage
            relationship.trust -= 20
    
    return delta
```

### Persuasion Thresholds

Each NPC has a persuasion threshold for each potential concession:

```
Small favor (directions, gossip): 15-30
Medium favor (discount, access, information): 40-60
Large favor (risk their safety, betray someone): 70-90
Extreme (betray faction, sacrifice something): 90-120
Impossible (violates core values): 150+ (effectively impossible
  without massive trust built over many interactions)
```

Threshold is modified by stubbornness:
```
actual_threshold = base_threshold * (0.7 + npc.stubbornness / 100 * 0.6)
# Stubbornness 0: threshold * 0.7 (pushover)
# Stubbornness 50: threshold * 1.0 (normal)
# Stubbornness 100: threshold * 1.3 (extremely hard to move)
```

### Trust Accumulation

Trust isn't just persuasion — it's the relationship over time.

```python
def update_trust(npc, interaction_type, details):
    """Trust changes from each interaction."""
    
    TRUST_EFFECTS = {
        "kind_words":        +2 to +5,
        "helpful_action":    +5 to +10,
        "shared_secret":     +8 to +15,
        "kept_promise":      +10 to +20,
        "saved_their_life":  +25 to +40,
        "lied_to_them":      -10 to -25,  (if detected)
        "broke_promise":     -15 to -30,
        "harmed_friend":     -20 to -40,
        "betrayed":          -40 to -80,
        "ignored_them":      -1 to -3,    (per day of neglect for companions)
    }
    
    # Trust has inertia — it's harder to change at extremes
    # Easy to go from 30→40, hard to go from 80→90
    trust = npc.relationship.trust
    change = TRUST_EFFECTS[interaction_type]
    
    if trust > 70:
        change *= 0.6   # diminishing returns at high trust
    if trust < 20:
        change *= 0.7   # hard to rebuild once broken
    
    npc.relationship.trust = clamp(trust + change, -100, 100)
    # -100 to 0: hostile/distrustful
    # 0 to 30: neutral/cautious
    # 30 to 60: friendly/warming
    # 60 to 80: close/loyal
    # 80 to 100: deep bond (very hard to reach, very meaningful)
```

### Trust Decay

Trust decays slowly if the player isn't around.

```
For companions: trust decays 0.5/day if player ignores them (doesn't talk)
For NPCs: trust decays 0.1/day naturally (people forget)
For high-trust (>60): no decay (real relationships persist)
```

---

## 5. Travel Math

### World Scale

```
Average continent diameter: ~2000 km equivalent
Average distance between neighboring cities: 50-150 km
Cross-continent journey: 500-1500 km

Player base travel speed: 30 km/day on foot
                         60 km/day on horseback
                         80-120 km/day by ship (weather dependent)
```

### Terrain Speed Multipliers

```
Road:        1.0x  (base speed)
Plains:      0.8x
Forest:      0.6x
Hills:       0.5x
Mountains:   0.3x
Swamp:       0.4x
Desert:      0.5x (plus water consumption doubled)
Snow:        0.4x
River crossing: costs 0.5 days (ford) or 0 with bridge
```

### Travel Event Probability (Per Day)

```python
def roll_travel_event(route_segment, player, day_number):
    """Check if something happens during a day of travel."""
    
    base_chance = route_segment.danger_rating / 100
    # danger_rating 0 = safe road, 100 = death march
    
    # Modifiers
    if player.reputation_in_region == "feared":
        base_chance *= 0.5   # people avoid you
    if player.party_size > 3:
        base_chance *= 0.7   # groups are less likely to be targeted
    if route_segment.terrain == "road":
        base_chance *= 0.6   # roads are safer
    if time_of_day == "night" and player.is_camping:
        base_chance *= 1.3   # night camps are vulnerable
    
    if random.random() < base_chance:
        # Something happens — what?
        event_roll = random.random()
        
        if event_roll < 0.35:
            return "bandit_encounter"    # 35% of events
        elif event_roll < 0.50:
            return "traveler_encounter"  # 15% — merchant, pilgrim, refugee
        elif event_roll < 0.65:
            return "weather_event"       # 15% — storm, fog, heat wave
        elif event_roll < 0.75:
            return "wildlife"            # 10% — wolves, bear, etc.
        elif event_roll < 0.85:
            return "discovery"           # 10% — ruins, cave, abandoned camp
        elif event_roll < 0.95:
            return "companion_event"     # 10% — companion wants to talk
        else:
            return "director_event"      # 5% — Director plants something
    
    return None  # quiet day, narrate summary
```

### Food and Supplies

```
Base food consumption: 1 unit/day per person
Water consumption: 1 unit/day (2 in desert/heat)
Carrying capacity: 10 + (strength / 10) units of food
Horse adds: +20 carrying capacity

Day without food: hunger stat increases by 20
  hunger 0-30: fine
  hunger 30-60: strength -5, agility -5, "you're weakening"
  hunger 60-80: strength -15, agility -10, willpower -10, "you're starving"
  hunger 80-100: all physical stats halved, death roll each day (5% base)

Day without water: same but 2x speed (dehydration kills faster)
```

---

## 6. Reputation Math

### How Reputation Spreads

```python
def spread_reputation(event, origin_city, world):
    """After a notable event, reputation spreads outward."""
    
    # How notable was it?
    notability = {
        "killed_someone_public": 60,
        "killed_someone_private": 15,  # only if witnesses
        "won_major_fight": 50,
        "helped_someone": 20,
        "stole_something": 35,
        "joined_faction": 40,
        "betrayed_faction": 80,        # betrayal travels fast
        "public_speech": 30,
        "saved_city": 90,
    }
    
    base_notability = notability[event.type]
    
    # Spread to connected cities with distance decay
    for city in world.cities:
        distance = world.distance(origin_city, city)
        
        # Reputation reaches further with higher notability
        reach = base_notability * 10  # in km equivalent
        
        if distance > reach:
            continue  # too far, didn't hear about it
        
        # Strength of reputation at this distance
        strength = base_notability * (1 - distance / reach)
        
        # Travel time delay (reputation doesn't spread instantly)
        days_to_arrive = distance / 40  # ~40 km/day by word of mouth
        
        # Queue the reputation event
        world.queue_reputation(
            city=city,
            content=event.description,
            strength=strength,   # 0-100, how well-known
            sentiment=event.sentiment,  # "feared", "respected", "wanted"
            arrives_day=world.current_day + days_to_arrive
        )
```

### Reputation Effects on NPC Behavior

```
reputation_strength > 80 in a city:
    - NPCs reference you by name or description
    - Merchants adjust prices (±15% based on sentiment)
    - Guards react (helpful if respected, hostile if feared)
    - Some NPCs approach you, others avoid you
    
reputation_strength 40-80:
    - Some NPCs have heard of you ("aren't you the one who...")
    - Subtle behavioral shifts (nervousness, curiosity)
    
reputation_strength < 40:
    - You're a stranger. Nobody knows you.
    
reputation_sentiment "feared":
    - NPCs are deferential but dishonest (they tell you what you want to hear)
    - Harder to build genuine trust
    - Guards watch you, might preemptively report your location
    
reputation_sentiment "respected":
    - NPCs are open and helpful
    - Easier to persuade (trust_bonus +10)
    - Faction members of your allies are friendly by default
    
reputation_sentiment "wanted":
    - Guards actively look for you
    - Bounty hunters may appear (Director event)
    - Some NPCs might hide you (depending on their alignment)
```

### Reputation Decay

```
Reputation decays 1 point per week in each city.
Major events (saved the city, murdered the mayor) decay at 0.2/week instead.
Legendary events (won the war, killed the king) don't decay at all.
```

---

## 7. Romance Math

### Base Attraction

```python
def calculate_base_attraction(player, npc):
    """
    One-time calculation when first meeting.
    This is the NPC's initial read on the player.
    """
    
    # Physical attraction (0-40 points)
    physical = (
        player.attractiveness * 0.4 +
        # NPC preferences based on their own stats:
        # High-intelligence NPCs care less about looks
        player.attractiveness * (1 - npc.stats.intelligence / 200) * 0.3 +
        # Height/build compatibility (some NPCs prefer tall, some don't)
        random.uniform(0, 10)  # personal taste variance
    ) * 0.4
    
    # Personality attraction (0-40 points)
    personality = (
        # Shared high stats create resonance
        stat_overlap(player, npc, ["depth", "intelligence", "humor"]) * 0.3 +
        # Complementary stats create intrigue
        stat_complement(player, npc, ["courage", "empathy"]) * 0.2 +
        # Charisma is universally attractive
        player.charisma * 0.2 +
        # Social class proximity (not hard barrier but affects comfort)
        class_compatibility(player, npc) * 0.1
    ) * 0.4
    
    # Situational (0-20 points)
    situational = (
        context.shared_danger * 10 +       # bonding through adversity
        context.player_helped_npc * 8 +     # gratitude seeds attraction
        context.first_impression * 5        # how the meeting went
    ) * 0.2
    
    return clamp(physical + personality + situational, 0, 100)
```

### Romance Progression

Romance isn't a single stat — it's four metrics that all need to reach thresholds:

```
attraction:  0-100  (initial interest, can grow or fade)
trust:       0-100  (shared with general relationship trust)
comfort:     0-100  (how relaxed they are around you)
intimacy:    0-100  (emotional closeness, vulnerability shared)
```

Stage transitions require ALL relevant metrics to cross a threshold:

```
stranger → acquaintance:     any interaction (automatic)
acquaintance → friendly:     trust > 25, comfort > 20
friendly → interested:       attraction > 40, trust > 35, comfort > 30
interested → courting:       attraction > 55, trust > 50, comfort > 45, intimacy > 25
courting → intimate:         attraction > 60, trust > 65, comfort > 60, intimacy > 50
intimate → partnered:        trust > 80, comfort > 75, intimacy > 70
                             (attraction can be lower for deep bonds — 50+)
partnered → complicated:     trust drops below 50 while other metrics stay high
                             (they still love you but something's wrong)
```

### What Builds Each Metric

```
attraction:
    +2-5:  player says something clever or funny (model-evaluated)
    +3-8:  player does something brave (engine detects courage-based action)
    +1-3:  time spent together (slow natural build, ~1/day if traveling together)
    -5-15: player does something the NPC finds repulsive (cruelty, cowardice)
    -1/day: natural decay if not interacting (attraction needs maintenance)

trust:
    (see Trust Accumulation in section 4)

comfort:
    +1-3:  every positive interaction without conflict
    +3-8:  sharing a meal, traveling together, quiet moments
    +5-10: player remembers something personal the NPC mentioned
    -5-10: player is aggressive or confrontational nearby
    -3-5:  player lies (even if not to the NPC — they notice)

intimacy:
    +3-8:  NPC shares something vulnerable AND player responds well
    +5-12: player shares something vulnerable AND NPC responds well
    +2-5:  extended private conversation (no one else around)
    +8-15: surviving danger together
    -5-10: player dismisses something the NPC cares about
    -10-20: player shares the NPC's secret with someone else
```

### Rejection Mechanics

NPCs don't all reject for the same reason. The rejection reason comes from their stats:

```python
def check_rejection(player, npc, advance_type):
    """Why might this NPC say no?"""
    
    if npc.relationship.attraction < 30 and advance_type == "romantic":
        return "not_interested"  # they're just not into you. permanent ceiling.
    
    if npc.relationship.trust < required_trust[advance_type]:
        return "not_ready"  # could change with time
    
    if npc.stats.loyalty > 70 and npc.has_partner:
        return "committed"  # loyal to someone else
    
    if npc.stats.stubbornness > 80 and npc.values_conflict(player):
        return "values"  # fundamental incompatibility
    
    if npc.mood == "grieving":
        return "wrong_time"  # come back later
    
    return None  # no rejection, advance proceeds
```

**Some NPCs will never be interested in you.** That's realistic. `not_interested` is a permanent ceiling on the attraction stat for that NPC. You can be their friend (trust and comfort grow normally) but romance is off the table. The game doesn't tell you why explicitly — the NPC just doesn't reciprocate the romantic energy.

---

## 8. Economy Math

### Currency and Prices

Prices scale with city wealth and player reputation.

```
Base daily expenses (food + lodging):
    poor inn:    2-4 coins
    decent inn:  5-10 coins
    fine inn:    15-30 coins

Weapons:
    dagger:          10-20 coins
    short sword:     30-50 coins
    long sword:      60-100 coins
    quality weapon:  150-300 coins (stat bonus)

Armor:
    leather:    40-80 coins
    chain:      150-250 coins
    plate:      500-1000 coins

Horse:          200-400 coins
Ship passage:   50-150 coins (depends on distance)
Bribe (guard):  10-50 coins (depends on request)
Bribe (official): 50-200 coins

Starting player wealth: 30-80 coins (depending on background)
```

### Wealth Stat → Actual Coins

```
NPC wealth stat maps to approximate holdings:
    wealth 0-10:    0-5 coins (destitute)
    wealth 10-30:   5-30 coins
    wealth 30-50:   30-100 coins
    wealth 50-70:   100-500 coins
    wealth 70-90:   500-5000 coins
    wealth 90-100:  5000+ coins
```

### Merchant Pricing

```python
def calculate_price(base_price, merchant, player, city):
    """What does this merchant charge?"""
    
    price = base_price
    
    # City economy affects prices
    if city.economy == "trade_hub":
        price *= 0.85  # cheaper due to competition
    elif city.economy == "remote":
        price *= 1.3   # scarcity markup
    
    # Merchant's greed (charisma inverted = stinginess)
    merchant_markup = 1.0 + (100 - merchant.stats.honesty) / 500
    # Honest merchant: 1.0-1.08x. Dishonest: 1.12-1.20x
    price *= merchant_markup
    
    # Player reputation discount/markup
    if player.reputation_in_city.sentiment == "respected":
        price *= 0.9
    elif player.reputation_in_city.sentiment == "feared":
        price *= 0.85  # fear discount (they don't want trouble)
    elif player.reputation_in_city.sentiment == "wanted":
        price *= 1.5   # risk premium
    
    # Haggling (if player attempts)
    # See persuasion system — arguing about price is a persuasion check
    # Success: 10-25% discount
    # Failure: merchant offended, might refuse to sell
    
    return round(price)
```

---

## 9. Perception and Observation Math

### Observable Details by Perception

Every scene has a list of details with minimum perception requirements:

```python
SCENE_DETAILS_EXAMPLE = [
    {"description": "the room is crowded and noisy", "min_perception": 0},
    {"description": "a bard plays in the corner", "min_perception": 0},
    {"description": "two men argue loudly by the fire", "min_perception": 10},
    {"description": "a woman sits alone, watching the room", "min_perception": 25},
    {"description": "the woman has a knife concealed in her boot", "min_perception": 60},
    {"description": "one of the arguing men keeps glancing at the door", "min_perception": 45},
    {"description": "the bartender's hand moves under the counter when you enter", "min_perception": 55},
    {"description": "faint scratches on the back door — recently forced open", "min_perception": 70},
    {"description": "the bard's song contains a coded message (specific lyrics)", "min_perception": 85},
]
```

### Lie Detection

When an NPC lies to the player:

```python
def detect_lie(player, npc, lie_severity):
    """Can the player tell this NPC is lying?"""
    
    player_read = player.stats.perception * 0.5 + player.stats.wisdom * 0.3 + player.stats.empathy * 0.2
    npc_deception = npc.stats.charisma * 0.4 + (100 - npc.stats.honesty) * 0.3 + npc.stats.willpower * 0.3
    
    # Bigger lies are harder to sell
    npc_deception -= lie_severity * 0.2  # severity 0-100
    
    # Trust makes you less suspicious
    if npc.relationship.trust > 50:
        player_read *= 0.7  # you trust them, harder to spot
    
    margin = player_read - npc_deception + random.uniform(-15, 15)
    
    if margin > 20:
        return "caught"        # "something about that doesn't add up"
    elif margin > 5:
        return "suspicious"    # "she hesitated before answering"
    else:
        return "believed"      # player doesn't know they were lied to
```

### Eavesdropping Completeness

```
player_perception 0-20:   hear tone only ("angry voices", "laughter")
player_perception 20-40:  hear fragments ("...the bridge... can't... soldiers...")
player_perception 40-60:  hear most words, miss key details
player_perception 60-80:  hear full sentences, understand context
player_perception 80+:    hear everything, can identify speakers and emotional subtext
```

---

## 10. NPC Schedule and Ambient Life Math

### Time Slots

```
dawn:       5am-7am    (waking, preparation)
morning:    7am-12pm   (primary activity)
afternoon:  12pm-5pm   (secondary activity)
evening:    5pm-9pm    (social time)
night:      9pm-5am    (rest, clandestine activity)
```

### Schedule Disruption

```python
def get_npc_location(npc, time_slot, world_events):
    """Where is this NPC right now?"""
    
    base_location = SCHEDULE_TEMPLATES[npc.occupation][time_slot]
    
    # Check for disruptions
    for event in world_events:
        if event.affects(npc):
            if event.type == "building_destroyed" and event.target == base_location:
                return npc.home  # nowhere to go
            if event.type == "siege" and npc.stats.courage < 40:
                return "hiding"  # scared NPCs stay home
            if event.type == "festival":
                return "town_square"  # everyone's at the festival
            if event.type == "curfew":
                if time_slot in ["evening", "night"]:
                    return npc.home
    
    # Personal disruptions
    if npc.health < 30:
        return npc.home  # too sick/injured to go out
    if npc.mood == "grieving" and random.random() < 0.5:
        return npc.home  # might stay home
    
    return base_location
```

### Ambient Conversation Topic Selection

```python
def select_ambient_topic(npc_pair, local_events, world_events):
    """What are two NPCs talking about?"""
    
    topic_pool = []
    
    # Always available: weather, work complaints, gossip
    topic_pool += [
        ("weather", 15),
        ("work_complaint", 15),
        ("local_gossip", 10),
        ("personal_gripe", 10),
    ]
    
    # Recent local events spike as topics
    for event in local_events[-5:]:
        topic_pool.append((event.description, 25))  # high weight — people talk about news
    
    # High-fate characters generate rumors
    for npc in world.high_fate_npcs_in_region:
        if npc.fate > 0.6:
            topic_pool.append((f"rumor_about_{npc.name}", npc.fate * 20))
    
    # World events (war, famine) dominate conversation
    for event in world_events:
        if event.narrative_weight in ["major", "critical"]:
            topic_pool.append((event.description, 40))
    
    # NPC occupations influence topics
    if "merchant" in [npc_pair[0].occupation, npc_pair[1].occupation]:
        topic_pool.append(("trade_prices", 15))
    if "soldier" in [npc_pair[0].occupation, npc_pair[1].occupation]:
        topic_pool.append(("military_movement", 15))
    
    # Disagreements are more interesting (and likelier between high-depth NPCs)
    if both_npcs_depth_above(npc_pair, 50):
        topic_pool.append(("philosophical_disagreement", 15))
        topic_pool.append(("political_argument", 10))
    
    # Weighted random selection
    return weighted_choice(topic_pool)
```

---

## Summary of Key Numbers

Quick reference for the numbers that matter most during implementation:

```
STAT GENERATION
    Base mean: 42, std: 16
    Fate mean shift: +30 * fate
    Fate std shift: +8 * fate
    
CHARACTER SCALING
    Prompt tokens: 40 + (depth_score * 14)
    Response words: 15 + (depth_score * 1.5)
    Model boundary fuzz: ±8 points random
    
COMBAT
    Decision point threshold: margin within ±0.08
    Player death chance halved (protagonist bonus)
    Sneak attack: 1.4x multiplier
    Numbers advantage: 1 + (log2(ratio) * 0.4) multiplier
    Randomness: ±20% per side
    
PERSUASION
    Delta per exchange: typically -12 to +18
    Small favor threshold: 15-30
    Large favor threshold: 70-90
    Trust bonus: up to +0.3 modifier at max trust
    Caught lying penalty: -15 delta, -20 trust
    
TRUST
    Saved life: +25 to +40
    Betrayal: -40 to -80
    Decay: 0.5/day if ignored (companions), 0.1/day (NPCs)
    High trust (>60): no decay
    
TRAVEL  
    Foot: 30 km/day base
    Horse: 60 km/day
    Neighboring cities: 50-150 km (2-5 days on foot)
    Food: 1 unit/day/person
    Starvation starts: 3 days without food (hunger stat)
    
REPUTATION
    Spreads at ~40 km/day by word of mouth
    Decays 1/week (normal), 0.2/week (major), 0/week (legendary)
    Fear discount: 15% off merchant prices
    Respect discount: 10% off
    
ROMANCE
    Interested stage: attraction>40, trust>35, comfort>30
    Intimate stage: trust>65, comfort>60, intimacy>50
    Attraction decay: 1/day if not interacting
    Some NPCs have permanent attraction ceiling (not interested)

ECONOMY
    Daily expenses: 2-10 coins
    Starting wealth: 30-80 coins
    Long sword: 60-100 coins
    Plate armor: 500-1000 coins
```
