# Issues & Resolution Log

Tracks every bug found during playtesting, what caused it, and whether it's fixed.

---

## Open Issues

### CRITICAL

**ISS-001: Combat engine never fires during gameplay**
- Found: 2026-04-05 playtest #1
- Symptom: Player punched merchant, headbutted guard, grabbed sword blade — HP stayed at 100. No injuries. No combat resolution.
- Cause: Either interpreter isn't returning `type: "combat"` (JSON truncation) or loop.py routing doesn't match combat actions to `resolve_combat()`. Crash log shows zero combat-related crashes, meaning the function was never called.
- Status: OPEN
- Priority: P0 — without this, there's no game

**ISS-002: Interpreter JSON truncation (~50% of turns)**
- Found: 2026-04-05 playtest #1
- Symptom: Interpreter returns valid-looking JSON but it's cut off mid-string, causing parse failure. Falls back to nonsense handler.
- Cause: Gemini Flash response truncated despite 1024 max_tokens. The JSON schema might be too complex for the model to complete reliably.
- Possible fixes: (a) Simplify the JSON schema (fewer fields), (b) Switch interpreter to Anthropic, (c) Add retry with "complete the JSON" prompt, (d) Use Gemini's structured output mode
- Status: OPEN
- Priority: P0 — this breaks every other system downstream

**ISS-003: Narrator invents NPCs that don't exist in the engine**
- Found: 2026-04-05 playtest #1
- Symptom: Narrator described "a young woman with dark hair carrying apples." Player tried to talk to her. Engine couldn't find her — she's not an NPC object. She disappeared next turn.
- Cause: Narrator improvises scene details beyond what the engine placed. No mechanism to auto-create Tier 0 NPCs from narrator descriptions.
- Possible fixes: (a) Constrain narrator to only describe NPCs the engine provides, (b) Auto-generate Tier 0 NPCs when narrator mentions someone, (c) Narrator pre-populates location with "extras" before describing the scene
- Status: OPEN
- Priority: P1

### HIGH

**ISS-004: Player starts surrounded by named NPCs they've never met**
- Found: 2026-04-05 playtest #1
- Symptom: Opening scene used NPC names like "Nessa" and "Vara" as if player knew them.
- Cause: Scene context was passing NPC names regardless of `met_player` flag.
- Status: FIXED (2026-04-05) — unmet NPCs now described by appearance/occupation only

**ISS-005: Narration text too dim to read**
- Found: 2026-04-05 playtest #1
- Symptom: Italic dim white text nearly invisible on terminal.
- Status: FIXED (2026-04-05) — removed `dim=True` from narration style

**ISS-006: Gemini model IDs wrong**
- Found: 2026-04-05 playtest #1
- Symptom: 404 errors for `gemini-2.5-flash-preview-05-20`
- Status: FIXED (2026-04-05) — updated to `gemini-2.5-flash` and `gemini-3.1-flash-lite-preview`

**ISS-007: Gemini API key not found**
- Found: 2026-04-05 playtest #1
- Symptom: Key name in keys.json is `gemini_api_key`, config only checked `GEMINI_API_KEY` and `gemini`.
- Status: FIXED (2026-04-05) — added `gemini_api_key` to lookup chain

**ISS-008: Debug messages printing to player screen**
- Found: 2026-04-05 playtest #1
- Symptom: `[models] JSON parse failed...` visible during gameplay.
- Status: FIXED (2026-04-05) — all model debug output routed to crash_log.txt via logging module

**ISS-009: Custom character creation too literal**
- Found: 2026-04-05 playtest #1
- Symptom: "Finance major" → "financial analysis for Merchants' Guild." Wrestling → "pit fighter." No transformation or surprise.
- Cause: Character Author prompt treats player description as a checklist instead of loose inspiration.
- Possible fix: Rewrite prompt to say "use traits as seeds, not a translation table. The character should feel like someone the player recognizes themselves in, refracted through the world."
- Status: OPEN
- Priority: P2

**ISS-010: No lore/world visibility for player**
- Found: 2026-04-05 playtest #1
- Symptom: Player has no way to read about the world's history, factions, geography, conflicts. Dropped into a world with no orientation.
- Possible fix: Add `lore` command that shows world name, continents, active conflicts, factions. Maybe an in-game book or notice board.
- Status: OPEN
- Priority: P2

**ISS-011: No stats/enemy visibility during combat**
- Found: 2026-04-05 playtest #1
- Symptom: No way to see enemy health, your own detailed stats, or combat log.
- Possible fix: Add `stats` command showing full stat block, combat shows enemy description with visual threat indicator (easy/dangerous/deadly).
- Status: OPEN
- Priority: P2

**ISS-012: No map**
- Found: 2026-04-05 playtest #1
- Symptom: Player has no sense of spatial layout — where are the buildings? Where's the market relative to the river?
- Possible fix: HTML frontend with map, or at minimum a `map` command showing ASCII layout.
- Status: OPEN
- Priority: P2

**ISS-013: Narrator prompt was too verbose and rule-heavy**
- Found: 2026-04-05 playtest #1
- Symptom: Prompt was 40 lines of rules. Models respond better to concise voice direction.
- Status: FIXED (2026-04-05) — trimmed to 15 lines focused on voice and key rules

### MEDIUM

**ISS-014: HP never changes**
- Found: 2026-04-05 playtest #1
- Symptom: HP stuck at 100 through entire playtest including combat.
- Cause: Downstream of ISS-001 — combat engine never fires so damage is never applied.
- Status: OPEN (blocked by ISS-001)

**ISS-015: Gemini "thought_signature" warning printed to screen**
- Found: 2026-04-05 playtest #1
- Symptom: `Warning: there are non-text parts in the response: ['thought_signature']`
- Cause: Gemini returns thinking traces that the SDK warns about.
- Possible fix: Suppress this specific warning or filter non-text parts.
- Status: OPEN
- Priority: P3

**ISS-016: Time advances too fast**
- Found: 2026-04-05 playtest #1
- Symptom: Went from Morning to Afternoon to Evening in ~6 actions. Each turn shouldn't be hours.
- Cause: Time advancement counter probably too aggressive.
- Status: OPEN
- Priority: P3

### LOW

**ISS-017: Python 3.9 deprecation warnings**
- Status: FIXED (2026-04-05) — suppressed via `warnings.filterwarnings("ignore")` in run.py

---

## Design Notes Banked from Playtesting

- Combat should auto-resolve in 1 pass, not let the player take 5 actions in one fight
- Player should start ALONE — just arrived in town, nobody knows them
- Should be able to read world lore (continents, factions, politics)
- Consider HTML frontend for map, stats panel, NPC portraits
- Track API cost per session for the player
- Party display when companions join
- Narrator should never name unmet NPCs
- Character creation should be looser — traits as seeds not checklist

---

## Resolution Stats

- Total issues found: 17
- Fixed: 6
- Open: 11
- Blocked: 1
