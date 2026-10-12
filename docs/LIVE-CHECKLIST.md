# Live checklist: what no running game has shown yet

This is the list for a live pass. Every item here is something the test suite, the
emulators and the harnesses cover, but that nobody has watched happen in a running
copy of the game. It is built from two places: the "Not yet seen in a running game"
paragraph of the README (it has been carried since v1.35.66 and still stands in the
v1.35.68 README), and the live notes of the v1.35.66 pass (what was seen, and what that
pass marked as not run, not exercised or unconfirmed), plus the changes made after
v1.35.68 in this branch (section B).

How each line reads: **Seen** says where it has been seen live; **Not seen** says what is
still open, by game (1 = A New Home, 2 = The Lost Children, 3 = The Secret City,
4 = The Tree of Life, 5 = New Believers). "Seen" is taken from the live notes only; an
item is moved out of this file by a live pass, not by a test.

## Rules for a live pass

- Use a **copy** of the game folder and of its save folder (the patched game saves to
  `Documents\LDW\<the executable's name>`, so a copy with its own executable name has its
  own saves). Never the saves you play.
- Build the copy with every patch ticked (Select All; Select All leaves the
  experimental patches off) so every companion is installed.
- Run one game at a time. Quit with the game's own Menu, Quit: a village is saved only
  on a clean quit and every 600 seconds by the autosave; killing the game loses the
  session (known behaviour G1).
- The logs are in the save folder: `Virtual Villagers Fun Patcher Logs\Save <n>\...`
  (per save slot), the data in `Virtual Villagers Fun Patcher Data\...`.
- Tech points: the Tech screen's upgrades need them; a copy's village can be given tech
  points with Cheat Engine (a value the owner can set is a value the patch must
  support).

## A. The README's "Not yet seen" list

1. **Numbered Birth records** ("Birth 1", "Birth 2"; a Birth number is never used twice).
   Seen: 1 (twins), 3, 4. Not seen: 2, 5.
   Steps (2 and 5): build the copy **without** Birth Control (Select All includes it, so
   untick it), start a village, let a woman conceive (watch the Population log's
   "Nursing: yes"), Time Skip 12 years (Upgrades, Choose Time Skip Amount) or wait, quit.
   Expect: `Births and Conceptions` has "Conception n" then "Birth n" with the mother,
   the father and "Born as: Single birth / Twin / Triplet".
2. **Lost before birth records and Nursing lines.** Seen: 1 (Custom Island Event
   "Disappears" of a nursing mother), 5 (the Heathen case, by the owner's rule no Lost
   record). Not seen: 2, 3, 4, and 5 for a believer.
   Steps: make a woman nurse (a Custom Island Event "Pregnant" change, or wait), then
   make her disappear (Custom Island Event "Disappears") or let her die; quit.
   Expect: her Deaths / Disappeared record has "Nursing: yes, N baby(ies) (never born: lost
   with their mother)" and the Births log has "Lost before birth" (not for a Heathen).
3. **The "Nursing" wording** ("Nursing: yes", "Babies nursing: 2" instead of Pregnant).
   Seen: 1, 3. Not seen: 2, 4, 5 in the Population log of a nursing mother.
4. **The Island Events log's new lines.** Seen: the record shape in all five games; the
   "Choice:" line in 2, 3, 4, 5; the expected father and babies in 1. Not seen: the
   expected father and babies lines in 2, 3, 4, 5.
   Steps: Custom Island Event, Villager changes, Pregnant with a father, deliver it; quit.
   Expect: the Island Events record lists Nursing, Babies nursing, Expected father (name,
   head, body).
5. **A New Home's expected father** in the Family Tree Maker, the Village Matchmaker and
   the Custom Island Event change. Seen: the log line (1). Not seen: the Family Tree
   Maker and Matchmaker windows on a live village (only headless), and the Custom Island
   Event's father change in the dialog.
6. **The first-load cross-check:** Birth records written afterwards, and the removal of
   backfilled Arrived records of villagers born here. Not seen in a window: the live pass
   ran the repair through the Python API only; the **prompts themselves were not
   exercised** (see item 12).
7. **New Believers: the Faction line and "Left the tribe: became a Heathen".** Seen: 5.
   Nothing open except the catch-up case (item 17).
8. **The Tree of Life: the "Disappears" record and the founders' Arrived records.**
   Seen: 4. Open: none.
9. **The Village Statistics changes.** Not seen: every row on a played village across
   quits, a Start Over and a second tribe in the slot; New Believers counting only the
   tribe's Village Elders (newest change, never played). Steps (every game): play a
   village a few minutes, quit, open `Village Statistics\Village Statistics v2 - Save <n>.txt`,
   compare each row with the game's own Village Statistics screen; Start Over and check
   the file is a fresh village's; start a second tribe in another slot and check the
   two files do not mix. In 5: convert a believer to a Heathen and check the Heathens do
   not count.
10. **Each villager's own last-name rule.** Seen: 2 (the patcher's window gave the
    suggested names), 1, 3 (the quit box). Not seen: 4, 5 for a villager that really
    lacks one (a Barrel of Babies child).
11. **Choose Time Skip Amount in all five games.** Seen: all five (12 years charged
    once in each; 1 year in 1; 24 and 72 years in 2). Open: none. (Kept as a regression check.)
12. **The contradiction questions** (Repair Saves & Logs asks, then "Retroactively edit
    records?"). Not seen: the prompts in the window, in any game. Steps: use a copy of a
    save folder whose Births log has a Birth and a backfilled "Arrived ... How: unknown"
    for the same villager (or two "Death 15"); Repair Saves & Logs, tick "Records that
    contradict each other"; answer the resolution, then Yes once and No once (a No is
    remembered and not asked again; Check Logs shows it as left as you chose).
13. **The missing last names question at the quit.** Seen: 1, 2, 3 (Remind me and Not
    now written to the request file). Not seen: 4, 5.
14. **Dropping an Adult on a Child Tells a Story** in 1 and 2. Not seen: the one
    attempt in 1 never landed the drop (automation, not a finding). Steps: drag an adult
    onto a child (about 15 years old); the child's label reads "Telling a story" while
    they listen.
15. **A New Home's Easier Healing Mastery and its Healers Study catch-up.** Not seen.
    Steps (1): tick both; give a villager the Doctor skill with sick villagers around
    and Time Skip 6 years; expect the sick cured and the doctor's study progress made in
    the catch-up.
16. **The default fathers and A New Home's "Unknown" father.** Not seen. Steps (1): a
    villager conceived with no father known (a Custom Island Event pregnancy with no
    father); expect "Unknown" in the logs.
17. **The catch-up "Left the tribe" record and its Repair backfill** (5). Not seen. Steps:
    let a believer's faith fall to 0 during a Time Skip catch-up; expect a Disappeared
    record "Left the tribe: became a Heathen"; on a save missing it, Repair Saves & Logs
    adds it.
18. **The Time Skip popup** ("12 years have passed on the island."). Seen: 2 (delivered from the saved queue), 3. Not seen
    in 1, 4, 5.
19. **Fix grave information.** Not seen: the repair on a village whose graves lack a
    cause or epitaph (2 has been seen writing the Graves file live, 1 to 5 not the
    repair). Steps: a copy with a grave in the Graves file that the Deaths log lacks;
    Repair Saves & Logs, Fix grave information; expect a Death record from the grave.
20. **The Custom Island Event's Health, parents and Edit.** Seen: 1, 4, and in 3 the
    parents ("Kinship") and the title and mask. Not seen: Health and parents in 2 and
    5; the **Choices editor** (the two-choice event's edit window) in any game.
21. **The Family Tree Maker's "continued on page N" lines.** Checked headless on the
    owner's village; not seen in the window by the owner (steps: Family Tree Maker,
    Positions, a tree that needs two pages, read the page footers).

## B. Changes made after v1.35.68 (this branch): nothing here has run live

1. **A New Home: the village started with the hidden F1 key.** There is no Skip button:
   pressing F1 on the Start / "?" screen of a new village (a hidden key, apparently a
   leftover developer shortcut; 0x41F480) jumps into the village without setting its
   start time. Before: its logs appeared only at the first quit (the village's start
   time is never set on that path, so the game's autosave skips it). Now the Cause of
   Death companion makes the same slot save the quit makes, once, the first frame the
   village is on screen with its founders waiting.
   Steps (1 only; 2-5 have no such path): a **fresh save folder**, launch, go through
   the intro to the screen with the **Start** and **"?"** buttons, and there press
   **F1** instead of clicking a button; then **do not quit**. Expect within a second or
   two: the Births and Conceptions log with "Arrived 1..6, How: Founder", the
   Population, History and Statistics files, all under `Logs\Save 1\`, written before
   any quit. Then Start Over in that slot and press F1 on that screen again: the new
   founders are written again. Then quit and relaunch: no duplicate Arrived records,
   no "Cross-Check - Save 5.dat" for another slot.
   Also check the Start path still works (click Start, not F1): same logs, written
   once.
   Look for: the game freezing or crashing in the first seconds (a direct call to the
   game's save), a second set of founders, logs under the wrong "Save <n>".
2. **A two-choice Custom Island Event question on screen at the quit** (all five games).
   Before: the points stayed spent and the question was gone. Now it comes back.
   Steps (each game): Upgrades, Custom Island Event, build an event **with the two
   choices**, buy it, close the Tech screen, wait for the question popup. **Do not
   click.** Menu, Quit. Relaunch, Play: within a few seconds (the island event is made
   due again) the same question appears; answer it; expect one result popup, the tech
   points charged once (not again), the Island Events log with one record, and no
   Story Purchases file left in `Virtual Villagers Fun Patcher Data\Paid Purchases`.
   Also: quit with the question up, relaunch, **quit again without answering**, relaunch:
   still asked once.
3. **A crash between a purchase and the next save.** Kill the process (by its PID)
   after buying a Pick Island Event / Custom Island Event / Barrel of Babies and **before**
   any save. Relaunch: the village is as of the last save, with the tech points not
   spent, and **no** purchase delivered (the save never paid for it); the Paid
   Purchases file is gone or ignored. Then the same with a save made after the
   purchase (let the 10-minute autosave run, or quit): the purchase is delivered once.
   (Design: a purchase is believed only when the slot's save is newer than it; see
   docs/known-behaviours-and-non-bugs.md.)
4. **Move Old Files to New Names** writes a note in each slot it touched (all five
   games). Steps: a copy of a save folder still holding an older build's names (Cross-
   Check, Parentage Records, Log Words, Deaths, Repairs), game closed, Repair Saves &
   Logs, Move Old Files to New Names; expect one record in the shared
   `Repairs Made` and one in `Logs\Save <n>\Repairs Made` for every slot whose
   "- Save <n>" files moved.
5. **The "Retroactively edit records? No" answers are one store.** Answer No to a
   contradiction in Repair Saves & Logs; expect `Log Checks\Virtual Villagers <g> Log
   Decisions - Save <n>.json` to hold it (a "contradiction_left" entry) and no new
   "Contradictions Left" file; a copy that has the older "Contradictions Left" file
   keeps honouring its answers.
6. **Every companion DLL is rebuilt** (/Brepro, so the same source always gives the same
   file). Smoke test, each game: launch the patched copy, load a village, open the
   Origins menu, play two minutes, quit. Nothing should differ from v1.35.68.

7. **Custom Island Event: several entries for one villager.** In any game, add 'Add a like' whale meat as one Villager changes entry and butterflies as another for the same villager (the count line should warn they are combined), queue, deliver: both likes are added and the Island Events log shows the whole "Likes: old -> old, whale meat, butterflies" line. Also: Dies in one entry and a like in another, only the death happens; Edit the combined entry and check the other like stays. Also: queue a two-choice event, let the question come up and quit at once (before a quarter second passes): the question must come back next launch; answer a question and quit at once: it must not come back.

## C. Questions the live pass left open (from the v1.35.66 notes)

- **The Tree of Life, weather.** "Pick The Rainy Season" logged "Weather: clear -> rain"
  but no rain showed in the captures; the type-4 (fog or drizzle) event never fired.
  Steps (4): Pick Island Event, The Rainy Season; watch the village screen for rain
  and, when you can trigger it, a type-4 weather event.
- **A New Home: a quit that did not exit once.** After Menu, Quit the save was written
  but the process stayed alive without a window for over 40 seconds, once, in one
  session. Not reproduced since. Steps (1): quit ten times in a row from a village with
  an unanswered missing-last-names box and from one without; each should exit at once.
- **New Believers: a Custom Island Event dialog quirk.** When the risk warning pops up
  on adding change A, a second Villager change added right after was dropped. Possibly
  automation timing. Steps (5): add a Heathen change to a purple or Chief villager, then
  immediately add another change.
- **The Custom Island Event Choices editor** was skipped in every game (see A20).
- **A New Home: Easier Healing Mastery, the Doctor.** See A15.
