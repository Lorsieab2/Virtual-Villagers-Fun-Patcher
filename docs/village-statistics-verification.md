# Village Statistics — verification matrix

Governed by [village-statistics-directive.md](village-statistics-directive.md)
(section XVI). One row per required statistic per game:
**source/hook → initialisation → update condition → persistence → test → result.**

Evidence levels used below: **code** = traced in the stock/rendered
executable; **emu** = the patcher's rendered bytes (or the shipped DLL) run
in an emulator; **harness** = the real C code run by a test harness;
**saves** = cross-checked against the owner's real save files; **log** = the
owner's exported log. No row is marked *live* unless it was observed in a
running game.

Owner decisions that shape the rows:
- Real Hours Played is the games' own formula: wall-clock hours since the
  village was founded.
- Babies/Twins/Triplets are counted at conception, as the games do.
- VV2 Special Stews Found is the game's own recipe counter, as intended.
- Villagers Buried counts burials (skeleton pickups) plus the memorial
  baseline; deaths with no skeleton picked up are not counted.
- Data the game does not keep is kept in per-save `.dat` files beside the
  saves; old patch values in the save are frozen, and the new log is
  `Village Statistics v2 - Save N.txt`.

## Common statistics (all five games)

| Statistic | Source / hook | Initialisation | Update condition | Persistence | Test | Result |
|---|---|---|---|---|---|---|
| Real Hours Played | game clock − the save's creation time ÷ 3600 (VV1 0x41D0E0, VV2 0x425A90; VV3–VV5 clock RVA vs statistics+0x00) | village creation | wall clock | save (creation time) | code; VV1 log 75 h vs 75.6 h since the save folder was created | OK (owner's chosen semantics) |
| Food Gathered | VV1 +0x9E28 (0x41D14A), VV2 +0x2E504 (0x4262BA), VV3 +0x0C (0x426401); VV4/VV5: patch hook (stock never writes) | new village | each positive food award | save (VV4/VV5: moving to .dat) | code; VV1 log matches save | OK — VV4/VV5 pending the .dat move |
| Tech Points Earned | VV1 0x41D12A, VV2 0x42629A, VV3 0x42714C, VV4 0x41E30D, VV5 0x4237BD | new village | each tech award | save | code; emu (VV2 double-add removed at 0x463742) | OK |
| People Cured | successful cure writers only; VV3/VV4/VV5 failed-roll branch retargeted past the +1 (0x45B968, 0x465179, 0x46E1F9) | new village | a cure that clears the illness | save | emu: cure +1, failed roll +0 (stock counted +1) | OK |
| Mushrooms Found | VV1 0x43B042, VV2 0x463416, VV3 0x42E087, VV4 0x414665, VV5 0x414970 (mushroom award path; collectibles never touch it) | new village | each mushroom picked, golden included | save | code; emu (golden reaches the same single increment) | OK |
| Highest Population | max-store (VV1 0x42F182, VV2 0x43C0DB, VV3 0x428CC3, VV4 0x420608, VV5 0x4261BD) | new village | population exceeds the stored maximum | save | code (load/max/store shape) | OK |
| Village Elders | VV2: game counter +0x2E514 (0x44D55F, once per villager at ≥3 masteries ≥88). VV1/VV3/VV4/VV5: per-save `Village Elders - Save N.dat` (village_elders.c), Master = VV1 ≥90, VV3 ≥0x58, VV4/VV5 ≥88.0 | new .dat: living elders + graves the game flagged | a villager seen with ≥3 masteries at a save; a new flagged grave not matched to a recorded elder | .dat (VV2: save) | harness A–F + file safety, mutation-checked | OK (limits in village_elders.c) |
| Oldest Villager | max-store (VV1 0x42EB3F, VV2 0x43B930, VV3 0x45F5ED, VV4 0x466663, VV5 0x4700B4) | new village | a villager older than the stored maximum | save | code | OK |
| Island Events Seen | event scheduler (VV3 0x46886A, VV4 0x43FBD6, VV5 0x442849; VV1/VV2 event code) | new village | each island event started | save | code | OK |
| Babies Made | conception routine, + litter size | new village | each conception | save | code | OK (counted at conception) |
| Twins Birthed | litter-2 branch (VV1 0x43BCC0, VV3 0x455BE7, VV4 0x45E8DD, VV5 0x465F2D); VV2 patch counter | new village | each twin conception, +1 | save (VV2: moving to .dat) | code | OK — VV2 pending the .dat move |
| Triplets Birthed | litter-3 branch (VV1 0x43BCB0, VV2 0x44BAD2, VV3 0x455BC9, VV4 0x45E8CA, VV5 0x465F1A) | new village | each triplet conception, +1 | save | code | OK |
| Villagers Buried | skeleton-pickup hook (VV1 0x448F65, VV2 0x46503B, VV3 0x462293, VV4 0x46A977, VV5 0x473F8F) + one-time memorial baseline (VV1 graves 0xA340+i·0x2C, VV2 +0x2EB0C/+0x74, VV3 Roster of the Dead only, VV4/VV5 mausoleum) | baseline = memorial occupied count when first tracked | each skeleton picked up, once | moving to .dat | emu (VV1 recount 0x41CF10 vs seed walk, 60 random memorials) | OK — pending the .dat move |
| Puzzles Solved: X out of Y | VV1/VV2 the Puzzles screen's 16 flags; VV3 progress ≥ threshold ids 0–15; VV4 the game's predicate ids 0–15; VV5 ids 1–16 (+17 with the Heathen Mommy patch, threshold 1, marker RVA 0x48F16) | game state | a puzzle solved | save | saves: VV1 72, VV2 35, VV3 32, VV4 37, VV5 62 saves agree with the game's rule; VV1 log 7/16 matches | OK |

## Game-specific statistics

| Game | Statistic | Source / hook | Update condition | Persistence | Test | Result |
|---|---|---|---|---|---|---|
| VV2 | Special Stews Found | game +0x2E520 (0x4260DC) | first cook of each of 18 recipes (ids 2, 4, 0x12 only after The Stew puzzle) | save | code | OK (intended) |
| VV2 | Total Stews Found | stew-completion hook, `Stew Discoveries - Save N.dat` | a new unique herb combination | .dat | stew tests A–F | in progress |
| VV3 | Chiefs Robed | robing routine entry 0x45FBC0 (branchless; reached only by a completed try-on with no living chief) | each new Tribal Chief | moving to .dat | code | OK — pending the .dat move |
| VV3 | Stews Found | successful-potion hook 0x430510, .dat | a new unique herb combination | .dat | stew tests A–F | in progress |
| VV4 | Debris Cleared | stream-debris decrement 0x43965A (the Civil Engineer trophy's unit) | each clearing unit | moving to .dat | code | OK — pending the .dat move |
| VV4 | Stews Found | success path 0x42EE5F, herbs + fresh/salt water, .dat | a new unique herb+water combination | .dat | stew tests A–G | in progress |
| VV5 | Heathens Converted | conversion entry 0x4668B0 (+2 Heathen Mommy tag 0x11, else +1) | each conversion | moving to .dat | code | OK — pending the .dat move |

## Not verified live

Nothing in this matrix has been observed in a running game. The deciding
live checks, where static analysis cannot settle a question, are listed in
the final report.
