# One folder per save

The owner, 2026-10-17: "FOR ANYTHING IN THE SAVES FOLDER, PLEASE MAKE SEPARATE FOLDERS TO PUT ALL THE
LOGS AND DATA FOR EACH SAVE IN ALL 5 GAMES" and "ADD A BUTTON TO MOVE EXISTING FILES TO ITS SAVE FOLDER".
Approved the same day.

`<save>` is the game's LDW save folder, `N` the save slot (1-5), `G` the game (1-5).

## The layout

    <save>\Virtual Villagers Fun Patcher\Save N\Logs\<log folder>\<log file>
    <save>\Virtual Villagers Fun Patcher\Save N\Data\<kind folder>\<name> - Save N.<ext>
    <save>\Virtual Villagers Fun Patcher\Save N\Data\Like and Dislike Words\Virtual Villagers G Log Words.dat
    <save>\Virtual Villagers Fun Patcher\Save N\Data\Copies Made Before Repairs\<place inside Save N>

Deleting `Virtual Villagers Fun Patcher\Save N` deletes everything the patcher keeps for that save once its
older files have been moved (below).

## Where each file goes (routing)

Every reader and writer still names the older layout's path and routes it (native/shared/per_save.h
`vv_ps_route_*`, src/vv_save_layout.py `route`); the answer depends only on what is on disk, so the games
and the patcher always agree:

| Kind | Unit | Rule |
|---|---|---|
| A log (`...Logs\Save N\<log folder>\...`) | the slot's log folder | the save's own folder once it exists; else the older one while it holds anything; else the save's own. Readers read both, older first. |
| A data file (`...Data\<kind>\... - Save N.<ext>`) | the file (with its `.tmp` and set-aside copies) | wherever it is; both: the one written last; neither: the save's own. |

Nothing is ever moved automatically. A save that already has a log or data file in the older folders keeps
adding to it there until the player moves it.

## Inventory

| What | Older place | Per save? | Code |
|---|---|---|---|
| Births and Conceptions, Deaths and Disappearances, Unaccounted Villagers, Island Events logs | `...Logs\Save N\<log>` | per save | native/parentage_export/parentage_export.c (build_log_path, build_family_log_path) |
| Tribe Population, Tribe History logs | `...Logs\Save N\<log>` | per save | native/population_export/population_export.c |
| Village Statistics log | `...Logs\Save N\Village Statistics` | per save | native/statistics_export/statistics_export.c |
| Repairs Made log | `...Logs\Save N\Repairs Made` | per save | native/shared/repairs_log.h, native/vv1_parentage/vv1_crosscheck.inc, src/vv_log_tools.py repair_record_start |
| Village Masks, Graves, Parents (A New Home), Villagers at Last Save | `...Data\<kind>` | per save | native/shared/data_subfolder.h vv_data_file_path |
| Arrivals / Births Recorded | `...Data\Arrivals`, `...Data\Births` | per save | native/shared/arrival_backfill.h |
| Graves Logged, Custom Island Event Deaths, Former Heathens | `...Data\Deaths`, `...\Custom Island Event Deaths`, `...\Former Heathens` | per save | native/vvfp_cause_of_death/cod_backfill.inc cod_data_path |
| Custom Titles | `...Data\Custom Titles` | per save | native/vvfp_story_upgrades/story_titles.inc; readers in parentage/population exporters |
| Paid / Story Purchases | `...Data\Paid Purchases` | per save | native/shared/paid_purchases.h |
| Log Checks (Repair Approved, Cross-Check marker, Log Decisions) | `...Data\Log Checks` | per save | native/shared/crosscheck_bridge.h, native/vv1_parentage/vv1_crosscheck.inc, src/vv_log_tools.py, src/vv_log_decisions.py |
| Last Names, Missing Last Names | `...Data\Last Names` | per save | native/vvfp_last_names/vvfp_last_names.c, native/shared/crosscheck_bridge.h, src/vv_last_names.py |
| Village Statistics, Villagers Counted, Stew Discoveries, Village Elders | `...Data\<kind>` | per save | native/statistics_export/statistics_store.c, statistics_export.c, village_elders.c |
| Family Tree Edits | `...Data\Family Tree Edits` | per save | src/vv_family_tree.py |
| Elder Totems (`ElderTotems.dat`, `Elder Totem Settings.dat`) | `...Data\Elder Totems` | per save; new in this layout only (never in the older layout) | native/vvfp_vv2_totems/vvfp_vv2_totems.c, src/vv_vv2_totem_store.py |
| Like and Dislike Words | `...Data\Like and Dislike Words` (one per game) | shared file; a moved or new log's boundaries go in its save's own file | native/shared/log_words.h, src/vv_save_layout.py words_file_for |
| Copies Made Before Repairs | `...Data\Copies Made Before Repairs` | a save's own file keeps its copies in its save's folder; older copies stay | native/shared/save_layout.h vv_layout_copy_path, src/vv_log_tools.py copy_before_repair |

## Not per save (never moved)

| What | Why |
|---|---|
| Older shared logs `...Logs\<log>\` (no slot), `VVFP Logs\` | one file holds records of several saves; splitting would rewrite history |
| Files under an older build's name (Cross-Check, Parentage Records, Log Words, Genealogy, "Village Roster") | an older patch reads only those; use Move Old Files to New Names first |
| Loose files in the Data folder or beside the saves | an older build's; the games move them into their folder themselves |
| Copies Made Before Repairs of older-layout files, Backups | backups are never moved |
| Virtual Villagers Fun Patcher Family Trees | named by the player, not by save |
| The game's .ldw saves | the game's own, read only |

## Move Files to Save Folders (Repair Saves & Logs)

src/vv_move_to_save_folders.py. Only when the player presses it; refused while the game runs, when the
game's install is not found, or when any patch DLL of the game names the older folders but not
`Virtual Villagers Fun Patcher\Save `. The confirmation lists every file, from where to where, per save,
and everything not moved with its reason; Cancel is the default. Each file is copied to Copies Made Before
Repairs and read back, copied to its new place (never replacing anything) and read back, its Like and
Dislike Words boundary copied to its save's own file, and only then is the original removed. Any failure
puts everything back. One Repairs Made record per save lists every file moved and not moved.

Start Over (native/shared/save_reset.c) clears the erased village's files in both places.
