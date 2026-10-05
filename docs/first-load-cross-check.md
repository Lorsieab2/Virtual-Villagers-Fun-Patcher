# The first-load cross-check (v1.35.58; orphan masks v1.35.59)

Before v1.35.57 the patcher kept some per-villager data by villager **record index**. Every game
packs its villager array when a save is loaded, so after a death everyone behind it comes back one
record lower, and data kept by index drifted onto the wrong villagers. v1.35.57 makes that data
follow the villager from now on, but data that had *already* drifted is stored against the wrong
identity and cannot be seen from the file alone.

v1.35.58 therefore checks every log and data file it keeps against a source of truth, and repairs
what is **confirmed** wrong -- but only after asking the player.

## The prompt

The first time a village has been on screen for a few seconds after it loads (never during the
load-time catch-up), each game's Origins companion asks **one** question covering everything found
(`native/shared/crosscheck_bridge.h`):

> The Fun Patcher checked this village's records against its save and its logs, and found some it
> can put right: ... Repair them now? "Not now" changes nothing; you will be asked again the next
> time this village is loaded.

The two buttons read **Repair** and **Not now**. The box is shown from a thread of its own, owned by
the game's window, so the game's render path is never blocked by a modal loop; the answer is acted on
on the game's own thread. When nothing is found, nothing is shown.

* **Not now** changes nothing and records nothing; the next load asks again.
* **Repair** repairs each part through the companion that owns it: the file is backed up beside
  itself (`<name>.before-v1.35.58-repair`; the orphan masks, added in v1.35.59,
  `<name>.before-v1.35.59-repair`; never replacing an existing backup), written atomically, every
  change is listed in a log, and the check is marked done.

## What is checked, per file

v1.35.58 extends the prompt to every file that a source of truth can reconcile (owner, 2026-10-04: "I
want everything to reconcile with the game saves"). Everything else stays report-only, and the checker
prints why with each such file.

| File | Game | Source of truth | "Confirmed wrong" means | Repaired in game? |
|---|---|---|---|---|
| Parentage Records (`Virtual Villagers 1 Parentage Records - Save N.dat`) | VV1 | Births and Conceptions log (written at each birth, never rewritten) | A living villager matched to Birth records by name, head **and** body, all naming the same parents, whose recorded parents differ; or recorded parents for a villager with no Birth record of that name (founder, grown arrival); or Birth records that disagree; or an expecting mother whose last logged conception names another father | **Yes** (prompt; `vv1_crosscheck.inc`); listed in the Repairs log |
| Graves missing from the Deaths log | all | the game's own graves / Roster of the Dead | a grave with no Death record | **Yes** (prompt; the grave backfill in `VVFP Cause of Death.dll`, written at the next save) |
| Births log: villagers with no Birth or Arrived record | all | the save's living villagers | a villager with no parents on the record and no Birth or Arrived record | **Yes** (prompt; an Arrived record, "Recorded afterwards", at the next save) |
| Births log: Birth records backfilled from the save | VV2-VV5 | each villager's own parents, kept on their save record for life | a living villager whose record keeps parents (born here) with neither a Birth nor an Arrived record of the same name, head and body (counted: two alike need two; a name only one record and one villager carry settles it when looks changed) | **Yes** (prompt; `RecordBirthsMissingFromLog` writes a Birth record from the save -- child's looks, likes, dislikes, skills, both parents -- marked "Recorded afterwards (born before this log existed)", at the next save). VV1 keeps no parents in the save: nothing to backfill |
| Births and Conceptions log, otherwise | all | -- (it is the source) | -- | never rewritten; VV2-VV5 Birth records compared with the parents the save keeps (reported) |
| Deaths, Unaccounted Villagers logs | all | graves; the save | a death also listed as unaccounted is reported | never rewritten |
| Village Elders .dat | VV1, VV3, VV4 | the Village History log's snapshots of this village (skills at every save) | a villager a snapshot shows with Master (the game's own threshold: 90 in VV1, 88 later) in 3+ skills, not alive now, whose name is on no line | **Yes** (prompt; a closed line `E -1 <name> <father> <mother> 0 0`, at the next save; `statistics_reconcile.inc`). Living elders are added by every save already. Never removes a line |
| Village Elders .dat | VV2 | -- | -- | not applicable: The Lost Children counts its elders itself (the game's counter, in the save) |
| Village Elders .dat | VV5 | -- | -- | reported only: the History log lists the Heathens too, with nothing telling them apart (the Heathen Chief has every skill at 100), and Heathens never count (owner) |
| Village Statistics .dat: Villagers Buried | all | this village's Death records whose Grave line names a grave; the graves the memorial holds | the counter below that | **Yes** (prompt; raised to the bound at the next save, never lowered) |
| Village Statistics .dat: Twins Birthed | VV2 | this village's Conception records with "Babies in pregnancy: 2" (the patcher's counter counts at conception) | the counter below that | **Yes** (same) |
| Village Statistics .dat: Chiefs Robed | VV3 | a living robed Tribal Chief | 0 while one lives | **Yes** (same) |
| Village Statistics .dat: Food Gathered, Debris Cleared, Heathens Converted | VV4, VV5 | **none** | -- | reported only: no save field or log bounds them (the Arrived records' "Converted from the Heathens" also follow the Maker's conversions, which do not count) |
| Village Statistics log: the game's own rows | all | the save | -- | reported only: Highest Population, Oldest Villager, Babies Made, Triplets, Tech Points, People Cured, Mushrooms Found, Island Events Seen, Puzzles Solved (and Twins outside VV2) are the GAME's counters, kept in the save and printed at every save, so the log cannot disagree with the save, and the patcher never changes the game's own counters |
| Village Population log | all | the save | lists other villagers than the save | reported only: it is rewritten from the game at every save; a copy written at load would record the load-time catch-up the save may never keep, and its writer also files the Births log's held records early |
| Village History log | all | the save | -- | **never rewritten** (owner rule); a snapshot is appended at every save, so the next save's is the save's; one appended at load would record unsaved state |
| Village Masks .dat (v1.35.59) | all | the villagers the save holds (each entry stores the identity of the villager it is for: each Origins companion's own hash of the name and the fields a life never changes -- A New Home name, gender and family scalar; The Secret City gender, Likes, Dislikes and name; the others name, gender and parents' names) | an **orphan**: an entry whose stored identity no villager carries -- living, or (The Secret City to New Believers) a body awaiting burial, which the save still holds -- on a record nobody holds (The Secret City finds masks by identity, so any entry). An entry with no identity on such a record is one too: a roster-keyed file stores none for a record nobody held, and the follow never puts such an entry on anyone. An identity some villager carries -- one, or several alike -- is never touched ("ambiguous: keep"); an older name-only file ('VM04', 'VM05' / 'VM25') is matched by name | **Yes** (prompt: "N mask entries for villagers who are no longer in the village"; `native/shared/orphan_masks.h`, each Origins companion's `vvfp_xc_masks_scan` / `vvfp_xc_masks_repair`). Removed **at once** (the mask file is the companion's own, written whenever the table changes, not at a save), and only the entries the prompt listed that are still orphans when the player answers; the file is backed up as `<file>.before-v1.35.59-repair`, each removal listed in the Repairs log (`Mask removed: <mask>, record <n> -- ...`). No village header (from the save, through `VVFP Save Reset.dll`), a failed write or a failed note changes nothing. So that an ambiguous entry stays one, A New Home, The Lost Children and New Believers write its identity on its empty record in the file's roster |
| Custom Titles .dat | all | the save's name, likes and dislikes (the title's fingerprint) | -- | reported only: a dead villager's title is not an orphan, and graves keep no likes or dislikes, so no file can prove a title belongs to nobody |
| Graves .dat | VV1, VV2 | the game's own graves | -- | self-validating: an entry is used only while its name-and-age fingerprint matches |
| Village Roster .dat (Cause of Death; Statistics) | all | the last save | -- | not rebuilt: each is the record of the LAST SAVE the next save compares with; a mismatch is the evidence it uses (another village in the slot; villagers who left unaccounted for) |
| `*.previous-village-*` statistics/stews/elders files | all | -- | set aside by the old roster match | reported only |
| Stew Discoveries .dat | VV2-VV4 | -- | malformed | reported only: VV3 and VV4 keep no record of stews made; VV2's found-recipe flags name recipes, not the herb combinations the file counts |

The Village Elders and Statistics parts run only when the slot's Village Roster says the files are this
village's (the next save sets another village's aside, as always), and only on a save whose counters
were flushed, so a pending count is never added on top of a bound that already holds it.

## Once per village

`Virtual Villagers Fun Patcher Data\Cross-Check\Virtual Villagers 1 Cross-Check - Save N.dat` records
that the parentage check ran for the slot (clean, repaired, or no Births log to check against). It is
written last, so an interruption simply runs the check again; the rebuilt table then matches the log
and nothing changes. The grave backfill keeps its own coverage file and finds nothing once done; the
Arrived and Birth backfills keep `Arrivals\Virtual Villagers N Arrivals Recorded - Save S.dat` and
`Births\Virtual Villagers N Births Recorded - Save S.dat` (VV2-VV5). The Elders and Statistics part
needs no marker: once repaired its scan finds nothing; nor do the orphan mask entries (v1.35.59): once
removed there is nothing left to find, so nothing is added to Repair Logs' list or to Start Over's.

## Asking again: Repair Logs

The patcher window's **Repair Logs...** (src/vv_log_tools.py) re-arms the check for one slot with the
game closed: after a "(before repair re-arm)" backup it clears exactly the markers in
`vv_log_tools.REARM_MARKERS` -- the Cross-Check marker above (A New Home), in every game
`Deaths\Virtual Villagers N Graves Logged - Save S.dat` and
`Arrivals\Virtual Villagers N Arrivals Recorded - Save S.dat`, and in The Lost Children to New Believers
`Births\Virtual Villagers N Births Recorded - Save S.dat` -- so the next load scans everything again
and asks before repairing. A new once-per-village part of the check adds its marker to that one list.
**Check Logs...** runs the read-only checker below in the patcher itself.

## The Repairs log

`Virtual Villagers Fun Patcher Logs\Repairs\Virtual Villagers N Repairs Log <n>.txt`: the village's
own header line, then one numbered `Repair <n>` record per repair (its date, what was checked against
what), one line per change -- A New Home's parents (`Corrected`, `Filled in`, `Set to unknown`,
`Expecting`); `Village Elder added: <name>`; `Villagers Buried raised: <was> -> <now>` and the like --
`Mask removed: Red Mask, record 6 -- kept for a villager who is no longer in the village (identity
<hex>)` -- and each backup's name (`native/shared/repairs_log.h`). None of the existing logs fits: the Unaccounted
Villagers log is about villagers who came and went unexplained, and the Births log is never annotated
(its backfilled records carry their own "Recorded afterwards" note).

## The read-only checker

```
python scripts/vvfp_consistency_check.py "<Documents>\LDW\<game folder>" <slot>
```

prints one section per file with OK / WRONG / NOTE / UNCHECKED and exits 1 when anything is WRONG.
It opens nothing for writing. `tests/test_consistency_checker.py` runs it on fixture saves built in
the test.
