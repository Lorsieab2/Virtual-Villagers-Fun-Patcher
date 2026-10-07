# The cross-check (v1.35.58; orphan masks v1.35.59)

Before v1.35.57 the patcher kept some per-villager data by villager **record index**. Every game
packs its villager array when a save is loaded, so after a death everyone behind it comes back one
record lower, and data kept by index drifted onto the wrong villagers. v1.35.57 makes that data
follow the villager from now on, but data that had *already* drifted is stored against the wrong
identity and cannot be seen from the file alone.

v1.35.58 therefore checks every log and data file it keeps against a source of truth, and repairs
what is **confirmed** wrong -- but only when the player says so, and never with a question while a
village is being played.

## Never during play: two ways a repair is allowed

The owner (2026-10-05): "For the 'repair' popups that appear during gameplay, can you make them appear
only if the player clicks the 'check logs' and 'repair' button? Or perhaps have a setting in the patcher
that toggles the automatic check during gameplay. When it is toggled ON, it brings up the repair prompt
when the game is closed, not while it is running, and only if there's a problem." Both are built.
Later the same day: "Can you make the check logs automatically default on? (With a message in the prompt
on how to turn the toggle off)" -- the setting is **on by default**, and the quit-time box ends by saying
how to turn it off. Nothing is ever shown while a village is being played
(`native/shared/crosscheck_bridge.h`).

### "Check logs automatically" (the patcher setting)

A tick box beside **Check Saves & Logs...** / **Repair Saves & Logs...** on both tabs of the patcher window, remembered
like the other settings (`patcher_local_settings.json`). It is a **per-install** choice, made when a game
is created: the patcher writes it into that game's executable as bit 31 of the word the startup loader
hands every companion at game start (`STARTUP_LOADER_CHECK_LOGS` in `src/vv_fun_patcher.py`,
`VVFP_STARTUP_CHECK_LOGS` in `native/shared/startup_companions.h`; the patch log's startup-loader line ends
"Check logs automatically: on" or "... off"). Changing the box changes the games created from then on; a
game already created keeps its own setting until it is created again. A fresh install, or a settings file
from v1.35.57 or earlier (which never had the key), starts with the box ticked; only a saved untick turns
it off. Default Patches, Owner's Defaults, Select All Patches and Deselect All Patches choose patches only and
leave this box as it is. On the command line it is on by default for `dry-run`, `apply`, `dry-run-all`
and `apply-all`; `--no-check-logs-automatically` turns it off (`--check-logs-automatically` is still
accepted).

* **Off**: nothing is scanned and nothing is asked, ever. Use **Check Saves & Logs...** and
  **Repair Saves & Logs...**.
* **On** (default): once a village has been on screen for a few seconds after it loads (never during the
  load-time catch-up), each game's Origins companion scans it silently, reading only. Nothing is shown.
  When the player **closes the game** after playing a village the scan found something in, the game's
  own quit save runs first; right after it, before the game frees anything, the village is scanned
  again from the state that save wrote, and only if something is still confirmed wrong ONE box asks:

  > Before the game closes: the Fun Patcher checked the records of the village you just played against
  > its save and its logs, and found some it can put right: ... The game has already been saved.
  > Repair them now? "Not now" changes nothing; you will be asked again the next time you close the
  > game after playing this village.
  >
  > To stop these checks, untick 'Check logs automatically' in the Virtual Villagers Fun Patcher and
  > patch the game again.

  The last sentence is the same in all five games (`VVFP_XC_HOW_TO_STOP`): the setting is written into the
  game when it is patched, so turning it off means unticking the box and patching the game again.

  The two buttons read **Repair** and **Not now**.

  * **Not now** changes nothing and records nothing; the next time the player closes the game after
    playing that village, it asks again.
  * **Repair** repairs every part found there and then, through the companion that owns it, from the
    state just saved: the file is backed up beside itself (`<name>.before-v1.35.58-repair`; the orphan
    masks, added in v1.35.59, `<name>.before-v1.35.59-repair`; never
    replacing an existing backup), written atomically, every change is listed in the Repairs log, and
    the part's marker is written. If a part cannot be repaired (a file locked), a second box says so and
    the rest is still done; what was left is found again next time.

  The question is about the village played last: playing another village afterwards in the same session
  replaces it, and the earlier village is asked about the next time it is the one played before closing.

### Repair Saves & Logs (the player's go-ahead, given beforehand)

**Repair Saves & Logs...** in the patcher window (`src/vv_log_tools.py`, `approve_repair`), with the game
closed, backs the save folder up (`Backup <date> (before repair re-arm)`), clears the slot's "already
checked" markers (below) and writes the slot's approval:

    <save folder>\Virtual Villagers Fun Patcher Data\Cross-Check\
        Virtual Villagers N Repair Approved - Save S.dat      (16 bytes: 'VRA1', 1, game, slot)

The next time that village is played -- whatever the setting -- it is repaired **without asking**:
A New Home's parents as soon as the village has settled, every other part at the village's next save (the
quit save at the latest) exactly as an answered Repair always was, and anything still found right after
the quit save is completed there. Then the game deletes the approval: it is used once. A part that could
not be done (a file locked) keeps the approval for the next time; a game that ends without its quit save
(a crash) keeps it too. Start Over deletes it with the village (`native/shared/save_reset.c`). **Check
Logs...** shows a pending approval as a NOTE. The check lives in each game's Origins companion, so it runs in every game created with any
of the patches that install it (Cause of Death, Show Parents, the Origins upgrades, ...); a game created
without them has nothing in it to check or repair.

### Why at the quit, and why there

Every game saves a village only when it is left (the save-slot screen's own save) and when the game
quits. Every clean quit goes through the application's shutdown (vtable `+0x14` of the application
object WinMain creates, runs and then shuts down): it saves the current slot -- the save manager's
current-slot field, `[application+4] + 0xABE4 / 0x30378 / 0x12F24 / 0x17114 / 0x17D80` -- then the
settings (slot 0), and only then deletes its screens and the village. The quit hook is the instruction
right after those two saves (A New Home `0x41B25B`, The Lost Children `0x423C5B`, The Secret City
`0x427331`, The Tree of Life `0x41E4F1`, New Believers `0x4239A1`; five position-independent bytes no
branch lands inside), installed by each game's Origins companion at game start, after verifying them, as
a `jmp` to a stub that saves every register and the flags, calls the check and runs the displaced
instructions. So when the check runs:

* the quit save is on disk and every companion's save-time work has run;
* the village, its graves and the save manager are still exactly what was saved (the settings save in
  between writes only the settings block, and every companion save hook takes slots 1-5 only);
* the village's header can be read back from the saved file ("VVFP Save Reset.dll").

`tests/test_repair_at_quit.py` proves all of this from the five stock executables;
`tests/test_startup_loader.py` that the hook is in place before WinMain in every game, population mode
and selection that ships the Origins companion (and in no other), and that its stub gives the game back
every register and flag.

**Each repair completes at the quit, from the just-saved state:**

| Part | At the quit | Why it is the saved state |
|---|---|---|
| A New Home's parents, and expected fathers left on villagers who are not expecting | `Vv1ParentageCrossCheckApply`, as before: the table rebuilt from the Births log against the living villagers, the parentage file written atomically (backup, Repairs log, Cross-Check marker) | the villagers are the ones just saved; the parentage file is the companion's own, never part of the game's save |
| Graves -> Death records | `VvfpCauseRepairGravesNow`: the grave backfill a save runs, with the header read back from the saved file; the Graves Logged file updated | the graves are the ones just saved; the logs were named by the quit save |
| Arrived records | `VvfpCauseRepairArrivalsNow`: the same backfill a save runs, then its marker | as above |
| Birth records from the save (VV2-VV5) | `VvfpCauseRepairBirthsNow`: the same, then its marker | each villager's own parents, on the record just saved |
| Village Elders and Statistics | `VvfpStatisticsRepairReconcileNow`: what the next save would have done, from the quit save's own state -- the same save manager (alive until after the hook), the store bound as that save bound it, its counters already flushed into the file (it runs only when that save's were, and only right after a successful save of the same slot), the roster that save read -- then the Village Statistics log written again so it shows the repaired counters | the quit save flushed every pending count; nothing counts between it and the hook |

One difference from a repair made before a save: the quit save has already reconciled the Unaccounted
Villagers log, so a villager whose departure or arrival only a backfilled record would have explained is
already listed there as Unaccounted (logs are never rewritten). Every companion is armed when the game
opens (`VVFP Startup.dll`), so in practice every death and arrival is seen live and this cannot arise.

### Never hangs the exit

The quit box runs on a thread of its own, owned by nothing; the game's window is minimised first, so
the box is not hidden behind a full-screen game. While it is open the game's thread takes only messages
sent to it (nothing waiting on it can deadlock) and runs no game code. If the box cannot be shown, or is
not answered within five minutes, nothing is done (as "Not now") and the game goes on closing. A fault
anywhere in the quit check is caught, and the game goes on closing. Nothing here runs from `DllMain`.

## What is checked, per file

v1.35.58 extends the check to every file that a source of truth can reconcile (owner, 2026-10-04: "I
want everything to reconcile with the game saves"). Everything else stays report-only, and the checker
prints why with each such file.

| File | Game | Source of truth | "Confirmed wrong" means | Repaired in game? |
|---|---|---|---|---|
| Parentage Records (`Virtual Villagers 1 Parentage Records - Save N.dat`) | VV1 | Births and Conceptions log (written at each birth, never rewritten) | A living villager matched to Birth records by name, head **and** body, all naming the same parents, whose recorded parents differ; or recorded parents for a villager with no Birth record of that name (founder, grown arrival); or Birth records that disagree; or an expecting mother whose last logged conception names another father | **Yes** (Repair; `vv1_crosscheck.inc`); listed in the Repairs log |
| Graves missing from the Deaths log | all | the game's own graves / Roster of the Dead | a grave with no Death record | **Yes** (Repair; the grave backfill in `VVFP Cause of Death.dll`, written at the next save, or right after the quit save) |
| Births log: villagers with no Birth or Arrived record | all | the save's living villagers | a villager with no parents on the record and no Birth or Arrived record | **Yes** (Repair; an Arrived record, "Recorded afterwards", at the next save, or right after the quit save) |
| Births log: Birth records backfilled from the save | VV2-VV5 | each villager's own parents, kept on their save record for life | a living villager whose record keeps parents (born here) with neither a Birth nor an Arrived record of the same name, head and body (counted: two alike need two; a name only one record and one villager carry settles it when looks changed) | **Yes** (Repair; `RecordBirthsMissingFromLog` writes a Birth record from the save -- child's looks, likes, dislikes, skills, both parents -- marked "Recorded afterwards (born before this log existed)", at the next save or right after the quit save). VV1 keeps no parents in the save: nothing to backfill |
| Births and Conceptions log, otherwise | all | -- (it is the source) | -- | never rewritten; VV2-VV5 Birth records compared with the parents the save keeps (reported) |
| Deaths, Unaccounted Villagers logs | all | graves; the save | a death also listed as unaccounted is reported | never rewritten |
| Village Elders .dat | VV1, VV3, VV4 | the Village History log's snapshots of this village (skills at every save) | a villager a snapshot shows with Master (the game's own threshold: 90 in VV1, 88 later) in 3+ skills, not alive now, whose name is on no line | **Yes** (Repair; a closed line `E -1 <name> <father> <mother> 0 0`, at the next save or right after the quit save; `statistics_reconcile.inc`). Living elders are added by every save already. Never removes a line |
| Village Elders .dat | VV2 | -- | -- | not applicable: The Lost Children counts its elders itself (the game's counter, in the save) |
| Village Elders .dat | VV5 | -- | -- | reported only: the History log lists the Heathens too, with nothing telling them apart (the Heathen Chief has every skill at 100), and Heathens never count (owner) |
| Village Statistics .dat: Villagers Buried | all | this village's Death records whose Grave line names a grave; the graves the memorial holds | the counter below that | **Yes** (Repair; raised to the bound at the next save or right after the quit save, never lowered) |
| Village Statistics .dat: Twins Birthed | VV2 | this village's Conception records with "Babies in pregnancy: 2" (the patcher's counter counts at conception) | the counter below that | **Yes** (same) |
| Village Statistics .dat: Chiefs Robed | VV3 | a living robed Tribal Chief | 0 while one lives | **Yes** (same) |
| Village Statistics .dat: Food Gathered, Debris Cleared, Heathens Converted | VV4, VV5 | **none** | -- | reported only: no save field or log bounds them (the Arrived records' "Converted from the Heathens" also follow the Maker's conversions, which do not count) |
| Village Statistics log: the game's own rows | all | the save | -- | reported only: Highest Population, Oldest Villager, Babies Made, Triplets, Tech Points, People Cured, Mushrooms Found, Island Events Seen, Puzzles Solved (and Twins outside VV2) are the GAME's counters, kept in the save and printed at every save, so the log cannot disagree with the save, and the patcher never changes the game's own counters |
| Village Population log | all | the save | lists other villagers than the save | reported only: it is rewritten from the game at every save; a copy written at load would record the load-time catch-up the save may never keep, and its writer also files the Births log's held records early |
| Village History log | all | the save | -- | **never rewritten** (owner rule); a snapshot is appended at every save, so the next save's is the save's; one appended at load would record unsaved state |
| Village Masks .dat (v1.35.59) | all | the villagers the save holds (each entry stores the identity of the villager it is for: each Origins companion's own hash of the name and the fields a life never changes -- A New Home name, gender and family scalar; The Secret City gender, Likes, Dislikes and name; the others name, gender and parents' names) | an **orphan**: an entry whose stored identity no villager carries -- living, or (The Secret City to New Believers) a body awaiting burial, which the save still holds -- on a record nobody holds (The Secret City finds masks by identity, so any entry). An entry with no identity on such a record is one too: a roster-keyed file stores none for a record nobody held, and the follow never puts such an entry on anyone. An identity some villager carries -- one, or several alike -- is never touched ("ambiguous: keep"); an older name-only file ('VM04', 'VM05' / 'VM25') is matched by name | **Yes** (scanned silently at load; the quit prompt says "N mask entries for villagers who are no longer in the village"; `native/shared/orphan_masks.h`, each Origins companion's `vvfp_xc_masks_scan` / `vvfp_xc_masks_repair`). Removed after the quit save when the player answers Repair, and -- with a Repair Saves & Logs approval -- as soon as the village has settled after loading (the mask file is the companion's own, written whenever the table changes, not at a save; one that could not be removed then is completed after the quit save). Only the entries the last scan found that are still orphans when they are removed; the file is backed up as `<file>.before-v1.35.59-repair`, each removal listed in the Repairs log (`Mask removed: <mask>, record <n> -- ...`). No village header (from the save, through `VVFP Save Reset.dll`), a failed write or a failed note changes nothing. So that an ambiguous entry stays one, A New Home, The Lost Children and New Believers write its identity on its empty record in the file's roster |
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
removed there is nothing left to find, so nothing is added to Repair Saves & Logs' list or to Start Over's.

## The "already checked" markers

**Repair Saves & Logs...** clears exactly the markers in `vv_log_tools.REARM_MARKERS` for the chosen slot,
before writing its approval -- the Cross-Check marker above (A New Home), in every game
`Deaths\Virtual Villagers N Graves Logged - Save S.dat` and
`Arrivals\Virtual Villagers N Arrivals Recorded - Save S.dat`, and in The Lost Children to New Believers
`Births\Virtual Villagers N Births Recorded - Save S.dat` -- so the approved check looks at everything
again. A new once-per-village part of the check adds its marker to that one list. Clearing a marker never
loses data and never writes anything twice: each part counts what the logs already hold before it
writes. **Check Saves & Logs...** runs the read-only checker below in the patcher itself.

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
