# Per-save folders: inventory and proposal (NOT BUILT YET)

The owner, 2026-10-17: "FOR ANYTHING IN THE SAVES FOLDER, PLEASE MAKE SEPARATE FOLDERS TO PUT ALL THE
LOGS AND DATA FOR EACH SAVE IN ALL 5 GAMES" and "ADD A BUTTON TO MOVE EXISTING FILES TO ITS SAVE FOLDER".
Nothing below has been built; this page waits for the owner's approval of the layout.

`<save>` is the game's LDW save folder; `N` the save slot; `G` the game (1-5).

## Where the patcher writes today

| What | Path under `<save>` | Written by | Scope |
|---|---|---|---|
| 8 log kinds (Births and Conceptions, Deaths and Disappearances, Unaccounted Villagers, Island Events, Tribe Population, Tribe History, Village Statistics, Repairs Made) | `Virtual Villagers Fun Patcher Logs\Save N\<kind>\` | native companions (native/shared/log_slot.h); src/vv_save_layout.py:173 | per save |
| Older shared logs (before per-slot logs) | `...Logs\<kind>\`, `...Logs\Deaths`, `...Logs\Repairs`, `VVFP Logs\` | older builds; read by vv_save_layout.log_folders (:185) | mixed saves |
| Custom Titles | `...Data\Custom Titles\Custom Titles - Save N.dat` | native/shared/custom_titles.h:86 | per save |
| Graves, Village Roster / Villagers at Last Save | `...Data\Graves\`, `...Data\Unaccounted Villagers\` (+ loose older names) | native/shared/save_reset.c:40-43, data_subfolder.h | per save |
| Arrivals, Births recorded | `...Data\Arrivals\`, `...Data\Births\` | native/shared/arrival_backfill.h:141-142 | per save |
| Graves Logged | `...Data\Deaths\` | native/vvfp_cause_of_death/cod_backfill.inc | per save |
| Log Checks: Repair Approved, Cross-Check, Log Decisions | `...Data\Log Checks\` (older `Cross-Check\`) | src/vv_log_tools.py:257,288; src/vv_log_decisions.py:54 | per save |
| Former Heathens (VV5) | `...Data\Former Heathens\` | native/shared/former_heathens.h:44 | per save |
| Paid / Story Purchases | `...Data\Paid Purchases\` | native/shared/save_reset.c:80-83 | per save |
| Custom Island Event Deaths (VV3-5) | `...Data\Custom Island Event Deaths\` | native/vvfp_cause_of_death/cod_cie.inc | per save |
| Village Masks, Origins Doublers, Parents (A New Home) | `...Data\Village Masks\`, `...Data\Parents (A New Home)\` (+ loose older names) | native/shared/save_reset.c:91-131 | per save |
| Last Names, Missing Last Names | `...Data\Last Names\` | src/vv_last_names.py:462,2074 | per save |
| Family Tree Edits | `...Data\Family Tree Edits\` | src/vv_family_tree.py:494 | per save |
| Village Statistics, Stew Discoveries, Village Elders .dat | `...Data\<kind>\<kind> - Save N.dat` | native/statistics_export/statistics_store.c:1037-1046, village_elders.c:129 | per save |
| Loose pre-folder files (`vv1_masks_N.dat`, `vvfp_masks_N.dat`, ...) | `<save>\` | older builds; save_reset.c:97-127 | per save |
| Copies Made Before Repairs | `...Data\Copies Made Before Repairs\<file's place>` | native/shared/save_layout.h:244 | per file |
| Like and Dislike Words | `...Data\Like and Dislike Words\Virtual Villagers G Log Words.dat` | src/vv_log_tools.py:599; native/shared/log_words.h | one file per game |
| Family Trees (.vvtree, pictures, Reports) | `Virtual Villagers Fun Patcher Family Trees\` | src/vv_family_tree.py:1306 | player-named |
| Backups | `Backups\Backup <date>\` | src/vv_save_backup.py:63 | whole folder |
| The game's .ldw saves | `<save>\` | the game | never touched |

## Proposed layout

| Old | New | Kind |
|---|---|---|
| `...Logs\Save N\<kind>\` | `Virtual Villagers Fun Patcher\Save N\Logs\<kind>\` | per save |
| `...Data\<kind>\... - Save N.*` and loose `..._N.dat` | `Virtual Villagers Fun Patcher\Save N\Data\<kind>\` | per save |
| `Copies Made Before Repairs` of a save's files | `Virtual Villagers Fun Patcher\Save N\Data\Copies Made Before Repairs\` | per save (new copies) |
| Like and Dislike Words (one per game) | new boundaries: `Save N\Data\Like and Dislike Words\`; old file read, never split | shared, cannot move |
| Older shared logs (`...Logs\<kind>\`) | stay; still read | cannot move: records of several saves in one file; splitting rewrites history |
| Family Trees saved by the player | new saves for a slot: `Save N\Family Trees\`; old ones stay | player-named, no slot in the name |
| Backups | stay | cannot move: whole-folder copies of all saves |
| .ldw saves | stay | game's own, read-only |

Every reader keeps reading every old place (as vv_save_layout.find/places/log_folders do now).
