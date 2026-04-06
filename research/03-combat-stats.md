# Combat Systems & Stat Engines Research
## Compiled April 5, 2026

---

## 1. Mount & Blade Auto-Resolve

### Troop Power Rating
```
TroopPower = (2 + TroopTier) × (10 + TroopTier) × 0.02
Mounted: × 1.2 | Hero: × 1.5
```
Tier 0 (recruit) ≈ 0.4, Tier 6 (elite) ≈ 1.92. Quadratic curve.

### Damage Calculation
```
Damage = (0.5 + 0.5 × rand(0,1)) × (40 × (AttackerPower / VictimPower)^0.7) × PerkBonus
Death: if rand(0, VictimMaxHP) < Damage → dead/wounded
```

**Key insight:** The `^0.7` exponent prevents one elite from trivially mowing down 20 peasants. Diminishing returns on power advantage.

### Morale
Base 50, range 0-99. Food variety, victories, wages as modifiers. Below threshold → troops desert. In combat → troops flee.

---

## 2. Dwarf Fortress Combat

No hit points. Every body part modeled with layered tissues (skin, fat, muscle, bone, organs, arteries, nerves).

### Attack Momentum
```
M = Size × Str × Vel / (10^6 × (1 + individual_Size / (weapon_density × weapon_size)))
```

### Edged Attack Penetration
```
M ≥ (rSY + (A+1) × rSF) × (10 + 2×Qa) / (S × Qw)
Where: rSY = shear yield ratio, S = sharpness (adamantine=10×, steel=1×, obsidian=2×)
```

### Blunt Attack
```
M ≥ (2×IF - IY) × (2 + 0.4×Qa) × A
```

**Key insight:** Maces vs plate should be > 1.0 because they're purpose-built anti-armor. Our matrix has mace/club vs plate at 0.85 — should be higher.

---

## 3. Battle Brothers

### Hit Chance
```
Hit% = Attacker_Melee_Skill - Defender_Melee_Defense + modifiers
```

### Damage Pipeline
```
1. Roll weapon damage: rand(Min, Max)
2. Armor damage: floor(min(current_armor, floor(roll × ArmorMod × modifiers) × ForgeMod))
   ForgeMod = 1 - ((helmet + body_armor) × 0.0005)
3. HP damage (two parts):
   Armor_Ignore = hp_roll × Ignore% × modifiers
   Non_Ignore = floor(hp_roll × (1 - Ignore%) × modifiers)
4. Remaining armor: 10% passive damage reduction
```

### Injury Thresholds
```
Body injury if: floor(hp_roll) ≥ HP × 0.25 × InjuryMod
Head injury if: floor(hp_roll) ≥ HP × 0.3125 × InjuryMod
```

### Morale
Six states: Confident → Steady → Wavering → Breaking → Fleeing. Triggers: first casualty, ally fleeing, wounded, surrounded. Snowball effect.

---

## 4. Kenshi

### Damage Formula
```
Base: 20 (floor)
+ Dexterity: up to 30 cut at level 100
+ Strength: up to 45 blunt at level 100
+ Weapon Skill: up to 30 cut + 15 blunt at level 100
Total = (20 + skill_damage) × weapon_multiplier
```

### Armor Penetration
```
Effective_Resistance = Base_Resistance × (1 - AP%)
```

**Key insight:** Separates cut and blunt as fundamentally different damage types with different stat scaling (dex vs str), different wound effects (cut=bleeding, blunt=stun/KO), different armor interactions.

---

## 5. Classic TTRPG Formulas

### D&D 5e
```
Hit: d20 + ability_mod + proficiency ≥ AC
Hit probability: (21 + attack_bonus - AC) / 20, clamped [0.05, 0.95]
Advantage: P(hit) = 1 - (1 - P_base)² ≈ +4-5 effective
```
"Bounded accuracy" — full range stays compressed so weak creatures can always hit strong ones.

### GURPS
```
Attack: 3d6 ≤ skill (bell curve, not flat!)
Damage after armor: Cutting × 1.5, Impaling × 2.0, Crushing × 1.0
```
Bell curve means middle is common, extremes are very rare. Skill 10 = 50%, Skill 14 = 90%.

### Savage Worlds
```
Attack: trait die (d4-d12) + d6 wild die, take best, ALL DICE EXPLODE
Damage vs Toughness: meet = Shaken, every +4 over = 1 Wound
```
Exploding dice create long tail — weak character can occasionally devastate.

---

## 6. Open-Source Combat Repos (Python)

- **CombatWiz** (github.com/kenfar/CombatWiz) — Monte Carlo combat sim, 1000+ battles
- **Battle Brothers Damage Calculator** (github.com/turtle225/Battle-Brothers-Damage-Calculator) — 80+ switches, heavily commented Python
- **OpenPythonRPG** (github.com/rodmarkun/OpenPythonRPG) — Modular RPG engine with AI
- **DndFight** (github.com/AndHilton/DndFight) — D&D combat Monte Carlo simulator

---

## 7. Roguelike Combat

### Caves of Qud Penetration System
```
1. Compare PV vs AV
2. Roll three singlets: each 1d10-2 (range -1 to 8, exploding on 8)
3. Each singlet + PV > AV = success
4. All 3 succeed → +1 penetration, reduce PV by 2, repeat
5. Any fail → stop
Damage = weapon_dice × number_of_penetrations
```
+6 PV over AV guarantees ≥1 penetration. Every +2 PV above that guarantees 1 more.

### DCSS
```
Damage = 1d(base × str_mod) × skill_mod × fighting_mod + slaying + enchant
AC reduction: rand(0, AC) subtracted
GDR: minimum reduction = GDR% of incoming (capped at AC/2)
```
**GDR means heavy armor always blocks something.** No feel-bad zero-reduction rolls.

---

## 8. Auto-Resolve & Lanchester's Laws

### Linear Law (melee, 1v1): `outcome ∝ α×A vs β×B`
Doubling troops = 2× advantage.

### Square Law (ranged/modern): `outcome ∝ α×A² vs β×B²`
Doubling troops = 4× advantage. 

**For medieval melee:** Reality is between linear and square. Our `1 + log2(ratio) × 0.4` is reasonable. But should be terrain-parameterized:
```python
if terrain == "open_field": exponent = 0.6    # closer to square
elif terrain == "narrow": exponent = 0.15      # almost negated
else: exponent = 0.4                            # default
```

---

## 9. Morale & Fleeing

### Moldvay D&D (clean design)
```
Morale score: 2-12. Check on first casualty or 50% casualties.
Roll 2d6. Result > morale → flee/surrender.
```
Bell curve against flat threshold. Morale-6: breaks 72%. Morale-9: breaks 28%.

### Design Principles
1. **Cascade/snowball:** One unit fleeing triggers checks in nearby units
2. **Thresholds, not gradients:** Holds steady until triggered, then drops sharply
3. **Personality-driven:** Brave checks less often, stubborn harder to break
4. **Enemy-specific:** Terrifying opponents impose harder checks

---

## Concrete Recommendations for Loom

1. **Power compression exponent** (M&B): `(CPR_attacker / CPR_defender)^0.7` — prevents invincibility against groups
2. **Bump mace/club vs armor:** Chain → 1.1+, Plate → 0.95-1.05. Maces were purpose-built anti-armor.
3. **Mid-combat enemy morale:** After first enemy falls, check if rest flee. Morale = courage×0.4 + loyalty×0.3 + willpower×0.3 vs 2d6. Leader dead = -3 penalty.
4. **Separate cut/blunt injuries** (Kenshi): Slashing = bleeding (worsens without treatment). Blunt = stun/fracture (heals but impairs immediately).
5. **Replace uniform randomness with tailed distribution:** `random.triangular(0.7, 1.3, 1.0)` instead of `uniform(0.8, 1.2)`. Creates occasional dramatic upsets.
6. **Guaranteed armor damage reduction** (DCSS): Armor always blocks `armor_rating × 0.3` before random rolls.
7. **Terrain-scaled numbers advantage** (Lanchester): Parameterize exponent by terrain type.
