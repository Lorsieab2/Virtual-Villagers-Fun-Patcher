# Village Statistics .dat files: unique stews and the patch's own counters

The owner's rule: "in general if the game doesn't keep track of it, make a
.dat file." Everything the Village Statistics feature counts that the game does
not keep itself lives in two per-slot files beside the save, never in the save:

```
<save folder>\Virtual Villagers Fun Patcher Data\Village Statistics\Village Statistics - Save N.dat
<save folder>\Virtual Villagers Fun Patcher Data\Stew Discoveries\Stew Discoveries - Save N.dat
```

`<save folder>` is `Documents\LDW\<exe basename>`, the folder that holds the
game's `.ldw` saves (native/shared/save_folder.h). The stew file exists only for
The Lost Children, The Secret City and The Tree of Life. Code:
`native/statistics_export/statistics_store.c`; hooks:
`scripts/build_statistics_features.py`.

## How a count travels

1. An executable hook increments a **pending** field, or sets a bit in a
   pending stew bitset. The pending fields are scratch space inside the block
   the game saves and loads wholesale, verified free (no stock reference, no
   reference in any rendered patch of any public feature in any mode, none in
   `native/` or a shipped DLL, none in the repository history).
2. The full-save wrapper hands each primary-slot save (slots 1-5) to the
   companion export `SaveVillageStatistics`. Before calling the stock writer it
   adds every pending value into the slot's statistics `.dat`, merges every
   pending stew bit into the slot's stew `.dat`, replaces both files
   atomically, and only then zeroes the pending fields - in the live block and
   in the save buffer the writer is about to write. A saved file therefore
   only ever holds zeros there. It then calls the stock writer with the game's
   own arguments and returns its result; after a successful save it writes the
   statistics log from the `.dat`. Every other save (meta slot 0, the +0x14
   backups) and any save for which the companion does not resolve goes
   straight to the stock writer.
3. Because the pending fields are inside the saved/loaded block, loading
   another village overwrites them with that save's zeros, and each game's
   new-village reset zeroes them, so an event that was never saved is
   discarded with its village, exactly as the game discards its own unsaved
   progress, and is never credited to another village.

| game | pending block | pending fields |
|---|---|---|
| VV1 | manager (saved +8..; new-village clear 0x41C40E +0x9E4C..+0x9ED7) | buried +0x9E9C |
| VV2 | manager (saved +8..+0x30378; new-village clear 0x425210 +0x2E528..+0x2E607) | buried +0x2E5E0, twins +0x2E5E4, stew bits +0x2E5E8..+0x2E603 |
| VV3 | live block 0x5824A0 (0x98 bytes, copied to/from manager+0x4EC; cleared by 0x426450) | buried +0x4C, died +0x50, chiefs +0x54, stew bits +0x58..+0x83 |
| VV4 | live block 0x4D6DE0 (manager+0x850; cleared by 0x41D9D0) | buried +0x50, died +0x54, debris +0x58, food +0x5C, stew bits +0x60..+0x6F |
| VV5 | live block 0x51D358 (manager+0x7B4; cleared by 0x41EBF0) | buried +0x44, died +0x48, heathens +0x4C, food +0x50 |

## Unique stews

A stew's identity is the herb combination the game used; for The Tree of Life
it is also the water. Order does not matter to any of these games: each
matches a recipe on how many of each herb the pot holds (VV2 `0x425B60` counts
occurrences; VV3 `0x430270` and VV4 `0x42DB70` pack per-herb counts), so
`A+B+C` and `C+B+A` are one stew.

| game | hook (stolen bytes) | herbs | identities |
|---|---|---|---|
| VV2 Total Stews Found | cook routine `0x425B90` (`55 56 57 8B F1 33 FF`), ECX = manager, herbs at +0x3043C/+0x30440/+0x30444 | 0x30..0x35 | 56 |
| VV3 Stews Found | recipe routine `0x430510` (`53 8B 5C 24 0C`), herbs as its three stack arguments; its only caller `0x430AAC` is on the successful-brew branch (a failed brew blows up and never gets there) | 0x1F..0x25 | 84 |
| VV4 Stews Found | success path `0x42EE5F` (`6A 18 B9 48 51 70 00`), ESI = pot, herbs at +0xC/+0x10/+0x14, before the water flags are cleared at `0x42EE6B`/`0x42EE77` | 0x1F..0x22 | 20 x fresh/salt = 40 |

VV2 counts every stew the cook routine completes, including those the game's
Special Stews logic skips. For VV4 the water is salt exactly when flag 0xA
(byte `0x704F00`) is set - the game's own rule in `0x42ECA0` - and fresh
otherwise.

The hook records the **ordered** triple in the pending bitset,
`((h1*n)+h2)*n+h3` (VV4: `*2 + salt`), after range-checking each herb, so a
value the game never produces records nothing. The companion normalises each
ordered triple when it flushes: with the herbs mapped to `0..n-1` and sorted
`a <= b <= c`,

```
identity = C(c+2, 3) + C(b+1, 2) + a          (VV4: + 20 for salt water)
```

which numbers every multiset exactly once (VV2 30,30,30 -> 0; 30,30,31 -> 1;
35,35,35 -> 55).

File format (ASCII, `\n` line ends, ascending identity, one line per
discovered identity; the herbs are the game's own ids, sorted, two-digit
upper-case hex):

```
VVFP STEW DISCOVERIES v1 game=4
stew=0 herbs=1F,1F,1F water=fresh
stew=23 herbs=1F,1F,21 water=salt
```

The row is the number of identities in the file united with any still pending.

## The patch's own counters

Keys: `villagers_buried` (all five games), `twins_birthed` (VV2),
`chiefs_robed` (VV3), `debris_cleared` (VV4), `food_gathered` (VV4, VV5 - the
game never writes its +0x0C statistic), `heathens_converted` (VV5) and
`villagers_died` (VV3-VV5; counted, not printed).

```
VVFP VILLAGE STATISTICS v1 game=3
chiefs_robed=4
migrated.chiefs_robed=1
villagers_buried=12
migrated.villagers_buried=9
villagers_died=15
migrated.villagers_died=11
```

Sorted by key; a key this build does not know is kept as it is.

**Migration.** Earlier builds counted into fields inside the save. Those
fields are now frozen - no hook writes them. When a slot's file has no entry
for a counter, the counter starts from the frozen field (VV1 +0x9E84, VV2
+0x2E5D4 and +0x2E5D8, VV3 +0x38/+0x40/+0x44, VV4 +0x0C/+0x3C/+0x44/+0x48, VV5
+0x0C/+0x34/+0x38/+0x40), Villagers Buried from the larger of that and the
memorial the game still holds, and Chiefs Robed from the larger of that and 1
when a chief lives and the earlier seed never ran. `migrated.<key>` records the
start, and because the entry then exists the migration never runs again, so
reloading an older backup of the save cannot add it twice.

## Safe handling

* A missing file is an empty history.
* A file that cannot be opened for any other reason (locked, I/O error) is
  left alone and nothing is flushed: the pending values and bits stay in
  memory and in the save and are recorded by a later save.
* A file that opens but is not a valid v1 file for this game - corrupt,
  another game's, another version's - is never overwritten and nothing is read
  from it. It is renamed aside to `<name>.unreadable` (then `-2`, `-3`, ...)
  and the history restarts from what the save itself proves.
* Every write goes to `<name>.tmp` and replaces the file with
  `MoveFileExW(REPLACE_EXISTING | WRITE_THROUGH)`, and every new stew file is
  the union of the old set and the new discoveries.
* Start Over on the main menu, and deleting the tribe on the save-slot menu,
  clear the slot's statistics and stew files, their `.tmp`, and the
  "Village Statistics v2" log through the Start Over reset
  (native/shared/save_reset.c; docs/start-over-reset-hook.md).

## Limitations

* Stew discoveries made before this build are not invented: an existing
  village's stew count starts at zero. The Secret City and The Tree of Life do
  set a "found" flag on a recipe-table entry when it is brewed (VV3 entry
  +0x2C at `0x43055E`, VV4 entry +0x34 at `0x42ECE1`), which could credit
  those past combinations exactly; combinations with no table entry (the
  generic results) leave no trace at all. That partial retroactive credit is
  not implemented.
* The files outlive the save: restoring an older backup of a save does not roll
  them back.
* The flush happens before the stock writer. If the writer then fails, the
  flushed events stay counted; they happened.
* The Start Over reset ships whenever Origins, the Births and Conceptions log
  or this log is selected. It finds the Births and Conceptions log by the
  village header this log publishes when the village is saved, so a Start Over
  in a session in which that village was never saved leaves that log alone;
  the slot-addressed statistics files go either way.

## Verification

`tests/test_unique_stews.py` runs each stew hook on the rendered bytes for every
ordered triple (and both waters), a failed and a successful Secret City brew,
and the save wrapper; renders every game's whole public catalog in all three
modes; and runs `native/statistics_export/statistics_store_harness.c` (tests
A-G, migration, reload, corrupt/foreign/unreadable files, union, atomic
replace). The reset is covered by `native/shared/save_reset_harness.c`.
