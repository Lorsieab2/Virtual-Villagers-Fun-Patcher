# The first-load cross-check (v1.35.58)

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
  itself (`<name>.before-v1.35.58-repair`, never replacing an existing backup), written atomically,
  every change is listed in a log, and the check is marked done.

## What is checked, per file

| File | Game | Source of truth | "Confirmed wrong" means | Repaired in game? |
|---|---|---|---|---|
| Parentage Records (`Virtual Villagers 1 Parentage Records - Save N.dat`) | VV1 | Births and Conceptions log (written at each birth, never rewritten) | A living villager matched to Birth records by name, head **and** body, all naming the same parents, whose recorded parents differ; or recorded parents for a villager with no Birth record of that name (founder, grown arrival); or Birth records that disagree; or an expecting mother whose last logged conception names another father | **Yes** (prompt; `vv1_crosscheck.inc`); listed in the Repairs log |
| Graves missing from the Deaths log | all | the game's own graves / Roster of the Dead | a grave with no Death record | **Yes** (prompt; the grave backfill in `VVFP Cause of Death.dll`, written at the next save) |
| Births and Conceptions log | all | -- (it is the source) | -- | never rewritten; VV2-VV5 Birth records compared with the parents the save keeps (reported) |
| Deaths, Unaccounted Villagers logs | all | graves; the save | a death also listed as unaccounted is reported | never rewritten |
| Village Population log | all | the save | lists other villagers than the save | regenerated at every save; reported only |
| Village History log | all | the save | -- | **never rewritten** (owner rule); its last snapshot is compared and reported |
| Village Statistics log and .dat | all | the save, the logs | a row below what the save or a log proves (Highest Population, Oldest Villager, Babies Made, Twins, Villagers Buried, Village Elders) | reported only: the logs are lower bounds and the counters are cumulative |
| Village Elders .dat | VV1, VV3-VV5 | the save's skills; the History snapshots | an open line for a non-elder; an elder with no line; a closed duplicate of an open line | reported only: a closed duplicate may stand for a dead elder whose line was renamed, and VV1 has no grave flags, so no complete source exists |
| Village Masks .dat | all | **none** -- no save field or log records a mask | -- | not checkable; the load follows each mask by the identity stored with it |
| Custom Titles .dat | all | the save's name, likes and dislikes (the title's fingerprint) | a title whose fingerprint fits no villager | reported only: the load already moves a title to its villager, and a title missing from the file may have been removed by the player |
| Graves .dat | VV1, VV2 | the game's own graves | -- | self-validating: an entry is used only while its name-and-age fingerprint matches |
| Village Roster .dat (Cause of Death; Statistics) | all | the save | -- | rewritten from the game at every save |
| `*.previous-village-*` statistics/stews/elders files | all | -- | set aside by the old roster match | reported only |
| Stew Discoveries .dat | VV2-VV4 | -- | malformed | reported only |

## Once per village

`Virtual Villagers Fun Patcher Data\Cross-Check\Virtual Villagers 1 Cross-Check - Save N.dat` records
that the parentage check ran for the slot (clean, repaired, or no Births log to check against). It is
written last, so an interruption simply runs the check again; the rebuilt table then matches the log
and nothing changes. The grave backfill keeps its own coverage file and finds nothing once done.

## The Repairs log

`Virtual Villagers Fun Patcher Logs\Repairs\Virtual Villagers 1 Repairs Log <n>.txt`: the village's
own header line, then one numbered `Repair <n>` record per repair, one line per villager changed
(`Corrected`, `Filled in`, `Set to unknown`, `Expecting`) and the backup's name. None of the existing
logs fits: the Unaccounted Villagers log is about villagers who came and went unexplained, and the
Births log is never annotated.

## The read-only checker

```
python scripts/vvfp_consistency_check.py "<Documents>\LDW\<game folder>" <slot>
```

prints one section per file with OK / WRONG / NOTE / UNCHECKED and exits 1 when anything is WRONG.
It opens nothing for writing. `tests/test_consistency_checker.py` runs it on fixture saves built in
the test.
