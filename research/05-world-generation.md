# Procedural World & Map Generation Research
## Compiled April 5, 2026

Note: Full detailed version also saved to WORLDGEN-RESEARCH.md in project root (written during research).

---

## 1. Roguelike Map Generation

### Caves of Qud — Closest analog
- Hybrid fixed overworld + procedural interiors
- WFC for building generation (multi-pass: coarse → WFC detail → connectivity)
- Zone tier system for difficulty/loot

### NetHack — Classic pipeline
`makelevel()` → `makerooms()` (random rooms + types) → `makecorridors()` → `wallification()` → populate

### Brogue — Room accretion
Start with one room, continuously attach rooms. 15% get hallways. Add "loopiness" by cutting doorways between adjacent rooms.

### Core Algorithms
| Algorithm | Best For |
|-----------|----------|
| BSP Trees | Classic dungeon layouts |
| Cellular Automata | Caves, ruins, wilderness |
| Room Accretion (Brogue) | Guaranteed connectivity |
| Wave Function Collapse | Building interiors, city blocks |
| Rooms and Mazes (Nystrom) | Cleanest general approach |

**Bob Nystrom's "Rooms and Mazes":** http://journal.stuffwithstuff.com/2014/12/21/rooms-and-mazes/

---

## 2. MUD World Builders (40 Years of Room Graphs)

### CircleMUD
- VNUM IDs for every room. 6-directional exits (N/E/S/W/Up/Down) with destination VNUMs.
- Zone system (VNUM ranges). Sector types (Inside, City, Forest, Mountains, Water...).
- Room flags: Dark, no-mob, peaceful, tunnel (limits occupants), private.
- Python parser: github.com/isms/circlemud-world-parser

### LPMud — OOP Rooms
Rooms as objects with inheritance. Exits unlimited (any string, not just compass). Closer to our Python architecture.

### Evennia — Modern Python
- github.com/evennia/evennia (4k+ stars, actively maintained)
- Rooms = graph nodes (NO inherent coordinates). Exits = first-class objects. Objects have one `location` field.
- Our `npc.location = "tessam_ironDrum_f2_backroom"` is literally Evennia's model.

### MUD Lessons
1. Rooms are graph nodes, exits are directed edges
2. VNUM-style IDs work (our tree already does this)
3. Exits can be arbitrary ("climb rope", "enter portal")
4. Zone-based generation is natural

---

## 3. Dwarf Fortress World Generation

### 10-Phase Pipeline
1. Fractal terrain (midpoint displacement)
2. Temperature (latitude + elevation)
3. Rivers (trace downward, carve channels)
4. Lakes and minerals
5. Vegetation (rainfall + temperature + drainage)
6. Biome assignment from field intersections
7. Wildlife placement
8. Civilization placement
9. Cave civilizations
10. **History simulation** — zero-player strategy game runs N years. Wars, expansion, population tracking.

### Key Insights
- Biomes emerge from intersecting independent layers (elevation × rainfall × drainage), not biome placement
- History comes from simulation, not authorship
- Rain shadow simulation (mountains block precipitation → realistic deserts)
- PRNG-seeded: same seed = same world

### Python implementation: github.com/Dozed12/df-style-worldgen

---

## 4. Procedural City Generation

### Shadows of Doubt — Almost exactly our hierarchy
City > District > Block > Building > Floor > Address > Room > Tile
- Room placement by priority (living room first, then bathroom)
- Connectivity rules (bathrooms: 1 door; kitchens connect to living rooms)
- "Space stealing" between rooms

### Other Approaches
- L-Systems (Parish & Muller, 2001) — highways → streets → lots → buildings
- Block-Centric (Watabou) — Voronoi diagrams for blocks. github.com/watabou/TownGeneratorOS
- WFC for 3D cities: github.com/marian42/wavefunctioncollapse

### For Text RPG
Don't need geometric layouts. Need weighted random tables for building types per district. This is a probability table problem, not a geometry problem.

---

## 5. Graph-Based Worlds

### Hierarchical Pathfinding (Amit Patel / Red Blob Games)
Pathfinding = walk up tree to lowest common ancestor, traverse at that level, walk back down.

"To get from your home to another city: chair → car → street → highway → highway → reverse down."

This is exactly our tree.

### Cross-Links Needed
- Room A might have window to courtyard (different building)
- District A adjacent to District B
- Edge weights for travel time (rooms: instant, buildings: minutes, cities: hours/days)

---

## 6. Terrain Generation

### Standard Approach (Red Blob Games)
```python
e = (1.0 × noise(1×x,1×y) + 0.5 × noise(2×x,2×y) + 0.25 × noise(4×x,4×y))
e = e / 1.75
e = pow(e, exponent)  # flatter valleys, steeper peaks
```
Biome = f(elevation_noise, moisture_noise): low+dry = desert, mid+wet = forest, high = mountain

For our tree: only need low-resolution categorical terrain (coastal/mountain/forest/plains per region), not pixel maps.

---

## 7. Fantasy Map Generators

### Azgaar's — 19-stage pipeline
Voronoi tessellation → heightmap → features → rivers → settlements (scored by suitability) → biomes → cultures → trade routes → politics → provinces → religions → heraldry
- github.com/Azgaar/Fantasy-Map-Generator
- Live: azgaar.github.io/Fantasy-Map-Generator/

### Key Ordering Insight
Terrain first → rivers → settlements scored by geography → politics after geography. Geography constrains narrative.

### Other Tools
- Martin O'Leary: github.com/mewo2/terrain (elegant Voronoi + erosion + city scoring)
- WorldEngine: github.com/Mindwerks/worldengine (Python, plate tectonics, 40 biome types)
- Watabou City Gen: watabou.github.io/city.html

---

## 8. Lazy / On-Demand Generation

### Seed-Based Determinism
```python
building_seed = int(hashlib.sha256(f"{world_seed}:{building_id}".encode()).hexdigest()[:8], 16)
```
Regenerate identically without storing. Only save player-modified state.

### Persistence Strategy
1. **Delta storage** — store only differences from generated baseline
2. **Event log** — record player actions, replay on regeneration
3. **Promotion to persistent** — modified areas saved permanently, rest regenerable

Option 3 is simplest. Most buildings visited once and forgotten.

---

## Key Repos to Study

1. **Evennia** (github.com/evennia/evennia) — Python MUD, Room/Exit/Object pattern
2. **AtTheMatinee/dungeon-generation** (Python, side-by-side algorithm comparison)
3. **mxgmn/WaveFunctionCollapse** (canonical WFC)
4. **Azgaar/Fantasy-Map-Generator** (complete worldgen pipeline)
5. **Mindwerks/worldengine** (Python, plate tectonics, biomes)
6. **isms/circlemud-world-parser** (40 years of MUD rooms → JSON)
7. **Dozed12/df-style-worldgen** (Python DF-style terrain + civilization sim)

## Key Articles

1. Bob Nystrom "Rooms and Mazes": journal.stuffwithstuff.com/2014/12/21/rooms-and-mazes/
2. Red Blob Games terrain: redblobgames.com/maps/terrain-from-noise/
3. Red Blob Games map representations: theory.stanford.edu/~amitp/GameProgramming/MapRepresentations.html
4. Shadows of Doubt interiors: colepowered.com/shadows-of-doubt-devblog-13-creating-procedural-interiors/
5. Brogue generation: anderoonies.github.io/2020/03/17/brogue-generation.html
