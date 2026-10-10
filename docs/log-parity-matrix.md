# Five-game log parity matrix

The owner (2026-10-09): "VV1-5 will have at a minimum the same information in all of its logs
UNLESS A SPECIFIC GAME LACKS THAT FEATURE. (Example: Golden Child is VV1-exclusive)".

This page compares every log and per-villager data file the patcher writes, field by field, across
the five games. Cells:

- **yes**: written.
- **n/a (feature)**: not written because the game does not have the feature; the reason is given.
- **GAP**: the game has the data but the log did not carry it. Every GAP found is listed under
  "Fixed" with its test.

Sources: the writers themselves (native/population_export, native/parentage_export,
native/vvfp_cause_of_death, native/statistics_export, native/shared), their harnesses, and the
owner's own test-village logs. Births and Conceptions, Island Events and the Deaths and
Disappearances record paths were compared before this audit and are not repeated here.

Game key: VV1 A New Home, VV2 The Lost Children, VV3 The Secret City, VV4 The Tree of Life,
VV5 New Believers.

## Village Population and Village History

One writer (`write_villager`, population_export.c) prints both; the History leaves out the
pregnancy lines (owner rule: the History is descent only).

| Line | VV1 | VV2 | VV3 | VV4 | VV5 |
|---|---|---|---|---|---|
| Villager n, Name, Age, Sex, Head, Body | yes | yes | yes | yes | yes |
| Custom title | yes | yes | yes | yes | yes |
| Special villager | yes (Golden Child) | yes (Esteemed Elder) | yes (Tribal Chief, Esteemed Elder) | yes (Scholar) | yes (Heathen roles, Former Heathen, Retired Heathen Chief, Esteemed Elder) |
| Mask | yes | yes | yes | yes | yes |
| Faction | n/a (feature: Heathens are VV5 only) | n/a | n/a | n/a | yes |
| Nursing / Babies nursing (Population only) | yes | yes | yes | yes | yes |
| Father of the child she carries, head, body (Population only) | yes (Show Parents sidecar) | yes (record) | yes | yes | yes |
| Likes, Dislikes (first filled; the game's own list) | yes (47) | yes (62) | yes (79, alchemy/potions) | yes (79) | yes (79) |
| Parents: Father/Mother with head and body | yes (Show Parents sidecar) | yes (record) | yes | yes | yes |
| Skills (the game's own names and order) | yes (5) | yes (5) | yes (5) | yes (5) | yes (6, Devotion) |

Special titles differ because each game's title is its own: A New Home's executable has no elder or
scholar title (its only special villager is the Golden Child), and the others' titles are the ones
their own Details panels show (native/shared/special_title.h).

Files: "Tribe Population\Village Population n.txt" (rewritten each save, 256 villagers per file)
and "Tribe History\Village History n.txt" (appended each save, rolls at 4 MiB): the same in all five.

## Village Statistics

Rows are the owner's directive (docs/village-statistics-directive.md): the 14 common rows in every
game, and each game's own rows on top -- VV2 Special Stews Found and Total Stews Found, VV3 Chiefs
Robed and Stews Found, VV4 Debris Cleared and Stews Found, VV5 Heathens Converted. No GAP: every
common row is written in every game. A New Home has no cauldron (no stews) and New Believers' rows
are as the directive lists them. VV2's Village Elders row is the game's own lifetime counter, which
counts the owner's definition (once per villager at 3 or more masteries); the other games keep the
Village Elders .dat (docs/village-statistics-verification.md).

File: "Village Statistics\Village Statistics v2 - Save S.txt" in all five.

## Deaths and Disappearances (record fields)

All five use the one renderer (WriteVillageRecord, parentage_export.c) with the Cause of Death
companion's lines.

| Record / line | VV1 | VV2 | VV3 | VV4 | VV5 |
|---|---|---|---|---|---|
| Death n: Name, Custom title, Special villager, Mask | yes | yes | yes | yes | yes |
| Age at death, Sex, Cause of death, Grave, Epitaph | yes | yes | yes | yes | yes |
| Nursing (babies lost with her) | yes | yes | yes | yes | yes |
| Head, Body, Likes, Dislikes | yes | yes | yes | yes | yes |
| Recorded afterwards (grave backfill) | yes | yes | yes | yes | yes |
| Disappeared: Age, Sex, What happened, Nursing | yes | yes | yes | yes | yes (and "Left the tribe: became a Heathen") |
| Epitaph changed | yes | yes | yes | yes | yes |
| Numbering beside an older build's "Deaths" folder | was BUG (all five) -- fixed | was BUG -- fixed | was BUG -- fixed | was BUG -- fixed | was BUG -- fixed |

Where the cause is kept differs by design: VV1 and VV2 graves keep no cause, so the Graves .dat
holds it; VV3-VV5 keep it on the record and in the Roster of the Dead.

## Unaccounted Villagers and Arrived records

| Line | VV1 | VV2 | VV3 | VV4 | VV5 |
|---|---|---|---|---|---|
| What, Age, Sex, Health, Nursing, Mask | yes | yes | yes | yes | yes |
| Faction | n/a (feature) | n/a | n/a | n/a | yes |
| Head, Body, Likes, Dislikes, Skills | yes | yes | yes | yes | yes |
| Parents: Father, Mother (Unaccounted) | was GAP -- fixed | yes | yes | yes | yes |
| Parents: Father, Mother (Arrived, when known) | was GAP -- fixed | yes | yes | yes | yes |
| Record, Last seen, Found | yes | yes | yes | yes | yes |

## Repairs Made

| Item | VV1 | VV2 | VV3 | VV4 | VV5 |
|---|---|---|---|---|---|
| Repair n, Date, Checked, one line per change, Backup | yes | yes | yes | yes | yes |
| Parentage repair (A New Home's parents sidecar) | yes | n/a (feature: parents are on the record) | n/a | n/a | n/a |
| Numbering after an older build's "Repairs" folder | yes (parentage repair); was BUG for the statistics and mask repairs -- fixed | was BUG -- fixed | was BUG -- fixed | was BUG -- fixed | was BUG -- fixed |

## Per-villager and village data files

| File | VV1 | VV2 | VV3 | VV4 | VV5 |
|---|---|---|---|---|---|
| Custom Titles - Save S.dat | yes | yes | yes | yes | yes |
| Village Masks | yes | yes | yes | yes | yes |
| Parents (A New Home) Parentage Records | yes | n/a (parents on the record) | n/a | n/a | n/a |
| Graves (causes, A New Home's epitaphs) | yes | yes | n/a (cause on the record) | n/a | n/a |
| Former Heathens | n/a (feature) | n/a | n/a | n/a | yes |
| Last Names, Missing Last Names | yes | yes | yes | yes | yes |
| Unaccounted roster (Villagers at Last Save) | yes (version 3: with parents' names) | yes | yes | yes | yes |
| Village Elders .dat | yes | n/a (the game's own counter) | yes | yes | yes |
| Stew Discoveries | n/a (no cauldron) | yes | yes | yes | n/a (not a directive row) |
| Like and Dislike Words (log word boundaries) | yes | n/a (its list was always its own) | yes | n/a | n/a |
| Log Checks: Repair Approved | yes | yes | yes | yes | yes |
| Log Checks: Cross-Check marker (parentage check) | yes | n/a (parents on the record) | n/a | n/a | n/a |
| Paid Purchases | per game by design | | | | |

## Fixed in this audit

1. **A New Home's Unaccounted and Arrived records name the villager's parents.** The Cause of Death
   companion takes them from the Show Parents companion for a live record and keeps them in the
   Unaccounted roster file (version 3, A New Home only) for a villager who leaves unseen. Readers:
   the checker (`vcr1_problem`) and the last-names rename (`_plan_unaccounted`) read version 3.
   Test: native/vvfp_cause_of_death/arrival_harness.c `parents_cases` (3 checks fail against the
   build before, in A New Home only; all five games pass after); tests/test_log_parity.py.
   No backfill: a villager who already left is in a version 2 roster with no parents to recover.
2. **Deaths numbering beside an older build's "Deaths" folder.** Every record after the first got
   the same number (the owner's A New Home log: four records "Death 15"). The number now follows the
   highest printed in either folder. Test: native/parentage_export/death_log_harness.c case 9b. The
   records already written keep their numbers (the logs are append-only).
3. **Repairs numbering beside an older build's "Repairs" folder.** native/shared/repairs_log.h (the
   statistics reconcile and the orphan masks, all five games) restarted at "Repair 1"; A New Home's
   parentage repair and the patcher's own repairs already continued after the older folder. Test:
   native/statistics_export/reconcile_harness.c case 7b.

### Per game (the owner's rule: a bug found in one game is checked and fixed in all five)

| Fix | VV1 | VV2 | VV3 | VV4 | VV5 |
|---|---|---|---|---|---|
| 1. Parents on Unaccounted / Arrived records | affected, fixed (arrival_harness parents_cases) | not affected (record), test added | not affected, test added | not affected, test added | not affected, test added |
| 2. Deaths numbering beside "Deaths" | affected, fixed (death_log_harness 9b runs in VV3's geometry; the code is shared) | affected, fixed | affected, fixed | affected, fixed | affected, fixed |
| 3. Repairs numbering beside "Repairs" | affected (statistics and mask repairs), fixed (reconcile_harness 7b) | affected, fixed (7b) | affected, fixed (7b) | affected, fixed (7b) | affected, fixed (7b) |

## Left for the owner

- **Data file names differ between games**: "Virtual Villagers 1 Village Masks - Save S.dat" (VV1,
  VV2) and "Village Masks - Save S.dat" (VV3-VV5); "Custom Titles - Save S.dat" and "Village Elders -
  Save S.dat" carry no game number while the Deaths and Births files do. Renaming changes where
  older builds look, so it waits for the owner's word.
- **Population, History and Statistics file names carry no game number** ("Village Population 1.txt")
  while the Births, Deaths, Unaccounted, Island Events and Repairs logs do ("Virtual Villagers 1 ...
  Log 1.txt"). The same in all five games; renaming waits for the owner's word.
