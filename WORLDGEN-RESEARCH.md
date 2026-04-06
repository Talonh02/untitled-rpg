# Procedural World Generation Research
## For the Untitled AI RPG Spatial Tree

Research compiled April 5, 2026. Focused on what's directly useful for a text RPG with the hierarchy:
```
World > Continent (4) > Region (3-5) > City (2-8) > District (2-5) > Building (10-50) > Floor (1-5) > Room (1-10)
```

Generated top-down, on demand. Cities at game start, interiors when you enter.

---

## 1. Roguelike Map Generation

### How the Big Roguelikes Do It

**Caves of Qud** — The closest match to what you're building.
- Fixed overworld layout (240x75 zones, each 25x80 tiles), but procedural ruins, lairs, villages
- Uses **Wave Function Collapse (WFC)** for building interiors — multi-pass: coarse architecture first, WFC fills middle detail, final pass adds connectivity and population
- Zone tier system controls difficulty/loot per area
- Procedural sultans with generated histories, lore fragments, recurring themes
- Key insight: *hybrid fixed + procedural*. The world map skeleton is authored, the details are generated
- Wiki: https://wiki.cavesofqud.com/wiki/World_generation
- GDC talk on their WFC approach: https://gdcvault.com/play/1026263/

**NetHack** — The classic room-and-corridor generator.
- `makelevel()` in `mklev.c` coordinates everything
- Stage 1: Determine level type (procedural vs pre-designed Lua template)
- Stage 2: `makerooms()` — iteratively place random-sized rooms, assign types (shop, throne room, vault, morgue, beehive, temple)
- Stage 3: `makecorridors()` → `join()` connects rooms with corridors, places doors at endpoints
- Stage 4: `wallification()` processes wall types (horizontal, vertical, corner, T-junction)
- Stage 5: Populate with monsters, items, traps based on difficulty
- Maze levels use recursive backtracking: fill grid with stone, carve paths from random start
- Data structure: `levl[x][y]` grid of `struct rm` (terrain type, visibility, lighting)
- Source: https://github.com/NetHack/NetHack — `src/mklev.c`
- Deep analysis: https://deepwiki.com/NetHack/NetHack/3.2-level-generation

**Angband** — Template-driven generation.
- Fill dungeon with granite, divide into 11x11 logical blocks
- Pick room type, find rectangle of blocks that fits (usually 33x11)
- Room types: simple rectangles, overlapping rectangles, pit rooms (themed monster groups), vault templates
- Vaults are handmade ASCII templates in `vault.txt` — dangerous, lucrative prefab rooms
- Corridor algorithm tunnels between rooms but can only handle width-1 walls
- Source: https://github.com/angband/angband — `src/generate.c`
- Detailed breakdown: http://roguelikedeveloper.blogspot.com/2007/11/unangband-dungeon-generation-part-two.html

**Brogue** — Room accretion with cellular automata.
- Start with one room, continuously generate and attach rooms where they fit
- Room shapes created by 5 generations of cellular automata, then flood-fill to select largest blob
- 15% chance any room gets a hallway (forces entry through a corridor)
- Adds "loopiness" by cutting doorways between adjacent rooms (prevents pure tree structure)
- Lakes are additional cellular automata overlaid on the dungeon
- Analysis: http://anderoonies.github.io/2020/03/17/brogue-generation.html

### Core Dungeon Algorithms

| Algorithm | What It Makes | Best For |
|-----------|--------------|----------|
| **BSP Trees** | Rectangular rooms + corridors | Classic dungeon layouts |
| **Cellular Automata** | Organic caves, natural shapes | Caves, ruins, wilderness |
| **Tunneling/Drunkard's Walk** | Winding corridors carved from stone | Mine-like environments |
| **Room Accretion** (Brogue) | Rooms attached to existing structure | Guaranteed connectivity |
| **Wave Function Collapse** | Pattern-based, locally coherent | Building interiors, city blocks |
| **Rooms and Mazes** | Rooms first, maze fills gaps, connect | Bob Nystrom's approach — clean |

**Bob Nystrom's "Rooms and Mazes"** — Probably the cleanest algorithm description:
1. Place random non-overlapping rooms (odd dimensions for grid alignment)
2. Fill remaining solid areas with maze (depth-first search)
3. Find "connectors" (solid tiles between two regions), build spanning tree
4. Open connectors to link regions, add some extra for loops
5. Remove dead ends from mazes

This creates naturally connected dungeons with loops. Article: http://journal.stuffwithstuff.com/2014/12/21/rooms-and-mazes/

### Useful Repos

| Repo | Stars | Language | What |
|------|-------|----------|------|
| [AsPJT/DungeonTemplateLibrary](https://github.com/AsPJT/DungeonTemplateLibrary) | 1400+ | C++ | Multiple dungeon/terrain algorithms |
| [AtTheMatinee/dungeon-generation](https://github.com/AtTheMatinee/dungeon-generation) | 220+ | Python | Side-by-side comparison of common algorithms |
| [vurmux/urizen](https://github.com/vurmux/urizen) | 136+ | Python3 | Roguelike dungeon generation library |
| [glouw/dungen](https://github.com/glouw/dungen) | — | C | Delaunay triangulation dungeon generator |
| [mxgmn/WaveFunctionCollapse](https://github.com/mxgmn/WaveFunctionCollapse) | Massive | C# | The canonical WFC implementation |

### What's Useful for Your Tree

For a text RPG, you don't need pixel-level tile maps. What matters is the *graph* — which rooms connect to which rooms, what's in each room. The algorithms above generate 2D grids, but the output you actually need is:
- A list of rooms with types/contents
- A connectivity graph (room A connects to room B via door/corridor/stairs)
- Categorical terrain (not pixel coordinates)

You can use BSP or room accretion to generate the *structure*, then flatten it to a graph for your spatial tree.

---

## 2. MUD World Builders (40 Years of Room Graphs)

### CircleMUD / DikuMUD Data Model

The gold standard for room-based spatial graphs. CircleMUD's world file format:

```
#<vnum>
<room name>~
<room description>~
<zone_number> <room_bitvector> <sector_type>
D<direction>          (0=N, 1=E, 2=S, 3=W, 4=Up, 5=Down)
<exit description>~
<keyword>~
<door_flag> <key_vnum> <destination_room_vnum>
S                     (end of room)
```

Key design decisions:
- **VNUM (Virtual Number)**: Every room gets a unique integer ID. Rooms, mobs, objects have independent VNUM spaces
- **6 directional exits**: N/E/S/W/Up/Down. Each exit has a destination VNUM, optional door, optional key
- **Zone system**: World divided into zones (VNUM ranges), each zone in a separate file
- **Sector types**: 0-9 (Inside, City, Field, Forest, Hills, Mountains, Water, Underwater, Flying)
- **Room flags**: Dark, no-mob, indoors, peaceful, no-magic, tunnel (limits occupants), private

The CircleMUD builder's manual is still one of the best documents on room-based world design:
- https://www.circlemud.org/cdp/building/building-3.html (room files)
- https://www.circlemud.org/cdp/building/building-2.html (mechanics)

A Python parser for CircleMUD world files to JSON exists: https://github.com/isms/circlemud-world-parser

### LPMud — Object-Oriented Rooms

LPMud separated the engine (driver) from the game logic (mudlib). Rooms are LPC objects inheriting from `/lib/room`:
- Exits are unlimited (not just 6 compass directions) — any string can be an exit name
- Rooms are objects with properties, not flat file entries
- Inheritance: a `tavern` inherits from `room`, adds drink/food mechanics
- Wizards code rooms as Python-like classes, not data files
- The virtual machine (driver) handles networking; the mudlib handles all game logic

This is closer to your Python architecture — rooms as objects with methods, not data records.

### Evennia — Modern Python MUD Engine

**The most directly relevant codebase for your project.**

- https://github.com/evennia/evennia (4k+ stars, actively maintained)
- Pure Python 3, Django backend, PostgreSQL/SQLite
- Everything is a typeclass inheriting from `TypedObject`

Three core spatial types:
- **Rooms**: Root containers. Have no location themselves. Just hold other objects.
- **Exits**: Objects connecting rooms. Each exit has a `destination` property. Exit names can be anything ("north", "jump out window", "portal").
- **Objects**: Characters, items — anything with a `location` field pointing to a room

Key architectural insight:
> "Evennia does not require rooms to be positioned in a logical way. You could make an exit 'west' that leads to a room described as being in the far north."

Rooms have NO inherent spatial coordinates. They're pure graph nodes connected by exit edges. Distance and position are emergent from the graph topology, not stored properties.

Database model uses Django ORM with SharedMemoryModel (caching layer so the same object instance is always returned after first lookup — performance critical for MUDs).

**What to steal from Evennia:**
- The typeclass pattern (Room, Exit, Object all inherit from one base)
- Exits as first-class objects (not just direction integers)
- The `location` field pattern (every object has exactly one location)
- You already have this pattern! Your `npc.location = "tessam_ironDrum_f2_backroom"` is exactly Evennia's model

### What MUDs Teach You

1. **Rooms are graph nodes, exits are directed edges.** Period. Don't think in grids.
2. **VNUM-style IDs work.** Simple integer or string IDs for every room. Your tree already does this.
3. **Exits can be arbitrary.** Not just N/S/E/W. "climb rope", "enter portal", "jump".
4. **Zone-based generation is natural.** CircleMUD zones = your tree levels. Generate a zone when needed.
5. **The flat-file-to-JSON pipeline is well-understood.** CircleMUD proved you can serialize entire worlds to simple text files.

---

## 3. Dwarf Fortress World Generation

The legendary worldgen. Here's the actual pipeline:

### Generation Phases (in order)

1. **Preparing elevation** — Midpoint displacement (fractal) generates heightmap. Mid-elevations smoothed to create plains.
2. **Setting temperature** — Based on latitude + elevation. Reset after vegetation affects it.
3. **Running rivers** — Trace from mountain edges downward. Many "test rivers" run, carving channels. Extreme elevation differences smoothed so everything isn't canyons.
4. **Forming lakes and minerals** — Small oceans dried out. Mineral distribution placed.
5. **Growing vegetation** — Based on rainfall + temperature + drainage. Rain shadows considered (mountains block weather systems, creating dry areas on the lee side).
6. **Verifying terrain** — Biome assignment from field interactions: high rainfall + low drainage = swamp.
7. **Importing wildlife** — Creature placement based on biome.
8. **Placing civilizations** — 5 races (dwarf, elf, human, goblin, kobold) placed in equal numbers.
9. **Making cave civilizations** — Underground peoples.
10. **Placing megabeasts** — Dragons, titans, etc.
11. **Recounting legends** — **This is the magic.** A zero-player strategy game runs for N years. Civilizations expand, wage wars, build sites, track populations. History is the record of that simulation. Thousands of agents with loose turn rules.

### Key Technical Insights

- **Fractal terrain + field interactions**: Elevation, rainfall, temperature, drainage, volcanism, wildness are independent layers. Biomes emerge from their intersection, not from a biome-placement algorithm. This produces internally consistent geography.
- **Rain shadow simulation**: Mountains block precipitation, creating realistic desert placement.
- **History as simulation**: DF doesn't write history — it simulates a civilization game and records what happens. Wars break out because civilizations expand into each other's territory, not because a script says "war happens at year 200."
- **PRNG-seeded**: Same seed = same world. Always.

### What to steal for your RPG

You're already using Opus for world generation. The DF approach suggests:
- Generate terrain layers (elevation, moisture, temperature) independently, then derive biomes from their intersection
- Don't author history — simulate it. Even a simple simulation (factions expand, border conflicts trigger wars) produces more interesting history than authored events
- The zero-player strategy game concept could run during your Director's daily tick

Python DF-style worldgen: https://github.com/Dozed12/df-style-worldgen (archived but complete — Python + libtcod, generates terrain layers + civilization expansion)

---

## 4. Procedural City Generation

### Approaches

**L-Systems (Parish & Muller, 2001)** — The foundational paper.
- Start with an axiom, apply growth rules to generate road networks
- Different rule sets produce radial, grid, or organic street patterns
- System generates highways first, then secondary streets, then divides land into lots, then places buildings
- Paper: https://cgl.ethz.ch/Downloads/Publications/Papers/2001/p_Par01.pdf

**Block-Centric (Watabou)** — Used in the Medieval Fantasy City Generator.
- Instead of growing roads outward (road-centric), define blocks of buildings first
- Voronoi diagrams create initial block shapes
- Walls, rivers, districts added as features
- Open source: https://github.com/watabou/TownGeneratorOS
- Live: https://watabou.github.io/city.html

**Wave Function Collapse for Cities**
- Infinite procedurally generated city using WFC with backtracking
- 3D voxel grid: each "slot" can contain one "module" (building block)
- Constraints ensure adjacent modules are compatible (road meets road, wall meets wall)
- Demo: https://marian42.itch.io/wfc
- Source: https://github.com/marian42/wavefunctioncollapse

**Shadows of Doubt** — **Almost exactly your hierarchy.**
- Location hierarchy: City > District > Block > Building > Floor > Address > Room > Tile
- Each tile = 1.8m x 1.8m, building floors = 15x15 tiles
- Floorplan templates define address boundaries, procedural logic generates interior walls
- Room placement priority system: cycle through room types by importance (living room first, then bathroom)
- Connectivity rules: bathrooms have 1 door, kitchens can connect to living rooms, everything connects to hallways
- "Space stealing": rooms that need more space can take from previously placed rooms
- Devblog: https://colepowered.com/shadows-of-doubt-devblog-13-creating-procedural-interiors/

### Useful City Gen Repos

| Repo | What | Language |
|------|------|----------|
| [josauder/procedural_city_generation](https://github.com/josauder/procedural_city_generation) | Full Python city gen with road networks | Python |
| [Yatoom/city-generator](https://github.com/Yatoom/city-generator) | Parish & Muller L-system implementation | Python |
| [magnificus/Procedural-Cities](https://github.com/magnificus/Procedural-Cities) | Complete cities with building interiors | C++ |
| [manusuena/Procedural-City-Layout-Generation](https://github.com/manusuena/Procedural-City-Layout-Generation) | Districts + MCEdit integration | Python |
| [phiresky/procedural-cities](https://github.com/phiresky/procedural-cities) | 15-page survey of all approaches | Paper |

### What's Useful for Your Tree

For a text RPG, you don't need geometric street layouts. You need:
- **District assignment**: Divide a city into 2-5 districts with character (market, docks, noble quarter, slums, temple district)
- **Building type distribution**: Each district has a probability table for building types (taverns cluster in market district, warehouses at docks)
- **Connectivity**: Which districts are adjacent? Which buildings face the main road?

This is a weighted random table problem, not a geometric one. Shadows of Doubt's priority-based room placement is the closest analog to what you need.

---

## 5. Graph-Based World Representation

### Amit Patel (Red Blob Games) — Map Representations

The definitive resource on how to think about game maps: http://theory.stanford.edu/~amitp/GameProgramming/MapRepresentations.html

Key representations:
- **Grids** — Simple, uniform tiles. Wasteful for large uniform areas.
- **Navigation meshes** — Polygons for walkable areas. Better for large spaces.
- **Graphs** — Nodes and edges. Most flexible. Your spatial tree is a graph.
- **Hierarchical maps** — Multiple abstraction levels. Pathfind zone-to-zone, then within zones.

### Hierarchical Pathfinding (HPA*)

For your spatial tree, pathfinding happens at multiple levels:
- **Room to room** within a building: Simple graph traversal
- **Building to building** within a district: Check adjacency
- **District to district**: Check connectivity graph
- **City to city**: Road network between cities
- **Region to region**: Travel time between regions

Real-world analogy from Amit Patel: "To get from your home to a location in another city, you find a path from your chair to your car, from the car to the street, from street to highway, highway to highway, then reverse down."

This is exactly your tree. Pathfinding = walk up the tree to the lowest common ancestor, then walk back down.

### Text Adventure Knowledge Graphs

Academic research (ACL 2019) on building knowledge graphs from text adventure game states:
- Games contain hundreds of locations, characters, objects
- The agent builds a graph of locations + connections as it explores
- Graph structure enables reasoning about unseen areas
- Paper: https://aclanthology.org/N19-1358.pdf

### What This Means for Your Tree

Your spatial tree IS a graph. Every node ID is a vertex. Parent-child relationships are edges. Exits between rooms are cross-edges. You already have the right data structure. What you need:

1. **Cross-links between siblings**: Not just parent-child. Room A on Floor 2 might have a window to the courtyard (a room in a different building). District A is adjacent to District B.
2. **Edge weights for travel time**: Moving between rooms = instant. Between buildings = minutes. Between cities = hours/days.
3. **Pathfinding = tree traversal**: To go from Room X in City A to Room Y in City B, walk up to the common ancestor (Region), traverse the road network, walk back down.

---

## 6. Perlin/Simplex Noise Terrain Generation

### Core Technique (Red Blob Games Tutorial)

The canonical tutorial: https://www.redblobgames.com/maps/terrain-from-noise/

**Elevation from noise octaves:**
```python
# Combine multiple frequencies for natural-looking terrain
e = (1.0 * noise(1*x, 1*y) +      # large features
     0.5 * noise(2*x, 2*y) +      # medium features
     0.25 * noise(4*x, 4*y))      # small features
e = e / (1.0 + 0.5 + 0.25)        # normalize
e = pow(e, exponent)                # redistribute (flatter valleys, steeper peaks)
```

**Biomes from two noise fields:**
- Elevation noise = height
- Moisture noise = wetness (independent seed)
- Biome = f(elevation, moisture): low+dry = desert, mid+wet = forest, high+any = mountain/snow

**Islands:**
- Distance function: 0 at center, 1 at edges
- Blend with noise: `elevation = lerp(noise, distance, 0.5)`
- Forces edges underwater while keeping internal variation

### Repos

| Repo | What | Language |
|------|------|----------|
| [wadefletch/terrain](https://github.com/wadefletch/terrain) | Island generation from Perlin noise | Python |
| [architectdrone/perlin-world-gen](https://github.com/architectdrone/perlin-world-gen) | Terrain + biomes from Perlin | Python |
| [jpw1991/perlin-noise-2d-terrain-generation](https://github.com/jpw1991/perlin-noise-2d-terrain-generation) | Roguelike terrain with biomes | Python |

### What's Useful for Your Tree

Noise-based terrain gives you the substrate your cities sit on. Use it to:
- Generate the continent shapes at game start
- Place regions based on terrain (coastal regions, mountain passes, river valleys)
- Determine city types from terrain (port city on coast, mining town in mountains, farming town in plains)
- The terrain doesn't need pixel resolution — you need categorical data per region/city: "coastal", "mountainous", "forested", "desert"

A single Perlin noise pass at low resolution (one value per city-sized area) gives you enough to drive meaningful terrain variety without rendering a pixel map.

---

## 7. Fantasy Map Generators

### Azgaar's Fantasy Map Generator

The most sophisticated open-source fantasy map generator. 19-stage pipeline:

1. Voronoi tessellation (10k-100k cells from jittered grid)
2. Heightmap (0-100 per cell, <20 = water)
3. Feature classification (ocean/sea/continent/island/lake)
4. Name generation (linguistic datasets)
5. Ocean depth contours
6. Lake detection (closed depressions)
7. River simulation (precipitation flux, MIN_FLUX=30 threshold)
8. Settlement placement (scored by coastal access, elevation, river presence)
9. Biome assignment (temperature + humidity)
10. Culture distribution (BFS expansion from seeds, weighted by suitability)
11. Trade routes
12. Political boundaries (group settlements into states)
13. Military zones
14. Religion distribution
15. Provincial subdivision
16. Heraldry generation
17. Ice placement
18. Map markers
19. Typography

**Central data structure**: `PackedGraph` — parallel arrays indexed by cell ID. Each cell stores: neighbors, vertices, elevation, distance from coast, area, feature membership, river ID, settlement, culture, state, province, religion, population.

Rivers use the most interesting algorithm: iterate cells high-to-low, accumulate precipitation flux, assign river IDs where flux exceeds threshold. At confluences, dominant tributary determined by flux comparison.

- Live: https://azgaar.github.io/Fantasy-Map-Generator/
- Source: https://github.com/Azgaar/Fantasy-Map-Generator
- Data model: https://github.com/Azgaar/Fantasy-Map-Generator/wiki/Data-model

### Martin O'Leary's Terrain Generator (mewo2)

Elegant approach to fantasy maps:
1. Voronoi diagram from Delaunay triangulation (each vertex has exactly 3 neighbors)
2. Heightmap from primitives (addHill, addCone)
3. Erosion via flow map + terrain slope
4. Fill depressions (Planchon-Darboux algorithm — ensure path to sea from all points)
5. Rivers where flux exceeds threshold, following flow map to coastline
6. City placement scored by terrain suitability
7. Markov-chain name generation

- Source: https://github.com/mewo2/terrain
- C++ port with more features: https://github.com/rlguy/FantasyMapGenerator

### Other Generators

| Tool | What | URL |
|------|------|-----|
| **Watabou City Gen** | Medieval city layouts with walls, districts, rivers | https://watabou.github.io/city.html |
| **Donjon** | World maps (fault-line terrain), dungeon maps (grid + cellular automata) | https://donjon.bin.sh/ |
| **WorldEngine** | Python, plate tectonics + erosion + Holdridge biomes (40 types) | https://github.com/Mindwerks/worldengine |

### What's Useful for Your Tree

Azgaar's pipeline is overkill for a text RPG, but the ordering is instructive:
1. Generate terrain first (elevation, water)
2. Place rivers and coastlines
3. Score locations for settlements
4. Place cities where scores are highest
5. Assign cultures and politics after geography

For your Opus world-generation call, you could provide terrain data (from a quick noise pass) as context, then ask Opus to place civilizations and history that make sense given the geography. Geography constrains narrative.

---

## 8. On-Demand / Lazy Generation

### The Core Pattern

Generate the skeleton at start, fill in detail when the player looks.

**Seed-based determinism**: Every chunk/zone/building gets its own seed derived from the global seed + its coordinates/ID. This means:
- You can throw away generated content when the player leaves
- It regenerates identically when they return (same seed = same output)
- You never store the full world — just the seed and any player-modified state

```python
# Derive a building's seed from the world seed + its ID
import hashlib
building_seed = int(hashlib.sha256(f"{world_seed}:{building_id}".encode()).hexdigest()[:8], 16)
```

### How Games Do It

**No Man's Sky**: 18 quintillion planets don't exist until visited. Each planet's seed = its coordinates fed through a deterministic algorithm. Only player modifications are saved separately.

**Minecraft**: World divided into 16x16 chunks. Each chunk seeded with global seed + chunk coordinates. Generated on approach, discardable, regenerable.

**Key distinction**: Static procedural generation (generate once, save) vs dynamic (regenerate from seed on demand). For a text RPG, dynamic is better — your world is mostly text, which is tiny to regenerate.

### The Modification Problem

The hard part: what happens when the player changes something in a generated area?

Solutions:
1. **Delta storage**: Store only the differences from the generated baseline. When regenerating, apply deltas on top.
2. **Event log**: Record player actions that changed the world. Replay on regeneration.
3. **Promotion to persistent**: When a player modifies a generated area, it gets saved permanently. Unmodified areas remain regenerable.

For your RPG, option 3 is simplest. Most buildings are visited once and forgotten. Only save the ones where something happened.

### What's Useful for Your Tree

Your architecture already has this right:
- World + Cities at game start (persistent)
- Building interiors when you enter (on-demand)
- Room contents when you enter a room (on-demand)

Add seed-based determinism so buildings regenerate consistently. Store a delta layer for player-modified locations. Everything else regenerates from seed.

---

## Summary: What to Build

Based on all this research, here's what's specifically useful for your spatial tree:

### 1. World Level (Opus call at game start)
- Generate terrain with Perlin noise (low-res, one value per region)
- Feed terrain to Opus: "Here's the geography. Place civilizations, write history."
- Store: continent boundaries, region terrain types, city locations + types, faction territories, history events

### 2. City Level (on first visit)
- Weighted random tables per city type: port cities get docks + warehouses + fish markets; mountain towns get mines + smithies + temples
- District assignment: 2-5 districts with character, derived from city type
- Building list per district: type + size + importance, from probability tables
- Cross-links: which districts are adjacent, main roads, gates
- **Don't need geometry.** Just the graph.

### 3. Building Level (on entry)
- Seed from world_seed + building_id
- Room count from building size/type
- Room types from building purpose (tavern: common room, kitchen, cellar, rooms for rent, owner's quarters)
- Connectivity: simple graph. Most rooms connect to a central hallway/common area.
- Brogue's room accretion or Shadows of Doubt's priority placement both work here
- **WFC is overkill for text.** Simple templates + random variation is enough.

### 4. Pathfinding
- Within a building: direct room graph traversal
- Within a city: district adjacency graph
- Between cities: road network with travel times
- Pathfinding = walk up tree to lowest common ancestor, traverse at that level, walk back down

### 5. Persistence
- Seed-based regeneration for unmodified areas
- Delta storage for player-changed locations
- Promote to persistent only when necessary

### Key Repos to Study

1. **Evennia** (https://github.com/evennia/evennia) — Python MUD engine. Room/Exit/Object typeclass pattern. Most directly applicable to your codebase.
2. **AtTheMatinee/dungeon-generation** (https://github.com/AtTheMatinee/dungeon-generation) — Python implementations of common algorithms side by side.
3. **mxgmn/WaveFunctionCollapse** (https://github.com/mxgmn/WaveFunctionCollapse) — For if you ever want sophisticated interior generation.
4. **Azgaar/Fantasy-Map-Generator** (https://github.com/Azgaar/Fantasy-Map-Generator) — Most complete open-source worldgen pipeline. Study the stage ordering.
5. **Mindwerks/worldengine** (https://github.com/Mindwerks/worldengine) — Python world generator with plate tectonics, erosion, 40 biome types.
6. **CircleMUD world parser** (https://github.com/isms/circlemud-world-parser) — See how 40 years of MUD rooms serialize to JSON.
7. **Dozed12/df-style-worldgen** (https://github.com/Dozed12/df-style-worldgen) — DF-style terrain layers + civilization simulation in Python.

### Key Articles to Read

1. Bob Nystrom's "Rooms and Mazes": http://journal.stuffwithstuff.com/2014/12/21/rooms-and-mazes/
2. Red Blob Games terrain from noise: https://www.redblobgames.com/maps/terrain-from-noise/
3. Red Blob Games map representations: http://theory.stanford.edu/~amitp/GameProgramming/MapRepresentations.html
4. Cogmind's procedural map generation series: https://www.gridsagegames.com/blog/2014/06/procedural-map-generation/
5. Brogue dungeon creation analysis: http://anderoonies.github.io/2020/03/17/brogue-generation.html
6. Shadows of Doubt procedural interiors: https://colepowered.com/shadows-of-doubt-devblog-13-creating-procedural-interiors/
7. Curated roguelike dev resources: https://github.com/marukrap/RoguelikeDevResources
8. Phiresky's procedural cities survey: https://github.com/phiresky/procedural-cities
