# Known behaviours and non-bugs

This register records durable findings about the five Virtual Villagers games
and the Fun Patcher: behaviour that looks like a bug and is not, behaviour the
owner has approved on purpose, and a few known open defects that are easy to
mistake for one of those. Check it before opening an issue or starting an
investigation. If the thing you are looking at is listed here, the entry says
whether it is settled and what would make it a real defect.

## How to add an entry

1. Put it under the group it belongs to (Logs, Parentage and identity,
   Statistics, Family Tree, Gameplay, Island Events).
2. Fill in every field:
   - **Behaviour** - what is seen, in plain words.
   - **Game(s) / subsystem** - which of the five games, and which part of the
     game or patcher.
   - **Conditions** - when it happens.
   - **Decision source** - an owner decision with its date, or the GitHub
     issue (`#N`) where it was settled.
   - **Evidence** - what supports it, and what kind of evidence it is (live
     game memory, the owner's logs or saves, or static analysis only). Say
     "static analysis only" when nothing was observed in play.
   - **Exceptions** - when the same symptom *is* a defect.
   - **Status** - one of: **non-bug**, **approved behaviour**, or **open
     defect**.
3. Only write what the source says. If the source is a static reading of the
   game code, say so. Never add paths outside this repository.
4. If a later decision changes an entry, update the entry and keep the old
   decision date in the Decision source line.

Issue links point to
`https://github.com/Lorsieab2/Virtual-Villagers-Fun-Patcher/issues/`. "Owner
decision" means a ruling the project owner gave directly; the date is when it
was given.

---

## Logs

### L1. The same name, head, body, like or dislike on unrelated villagers

- **Behaviour:** Two or more unrelated villagers in a log share a name, a head,
  a body, a like or a dislike. Groups can be large.
- **Game(s) / subsystem:** All five games. Every exported log.
- **Conditions:** Normal play. Names, likes, dislikes, heads and bodies are each
  drawn from a fixed, limited pool, and a name can be reused after its first
  holder dies.
- **Decision source:** Owner decision, 2026-09-25, recorded in
  [#434](https://github.com/Lorsieab2/Virtual-Villagers-Fun-Patcher/issues/434)
  (item 1) and [#436](https://github.com/Lorsieab2/Virtual-Villagers-Fun-Patcher/issues/436).
- **Evidence:** In the owner's VV3 log, grouping 61 Birth records by identical
  head, body, likes and dislikes gave groups of 9 and 12 children, too large to
  be litters (#434). The same log held 51 distinct names for 61 children.
  Measured live on 2026-09-25: 21 duplicated names among 107 living VV3
  villagers, 23 among 145 in VV5 (#436).
- **Exceptions:** A collision in the *data* is valid, but *code* that fails
  because of one is a defect. Example: VV2 and VV3 conceptions logging the
  father's age, likes and dislikes as "(not captured for this birth)" because
  a by-name lookup hit two villagers with the same name was ruled a real defect
  by the owner (retraction comments on
  [#428](https://github.com/Lorsieab2/Virtual-Villagers-Fun-Patcher/issues/428)
  and #434). Identity must come from a record pointer or slot, or from the full
  eight-field key in #436, never from a single field.
- **Status:** non-bug.

### L2. Twins and triplets have identical Birth records except for the name

- **Behaviour:** Two or three Birth records written at the same moment agree on
  head, body, likes, dislikes, parents and age.
- **Game(s) / subsystem:** All five games. Births and Conceptions log.
- **Conditions:** Any twin or triplet birth.
- **Decision source:** Owner decision, 2026-09-25, in #434 (item 2 and the
  "litters share everything but the name" comment).
- **Evidence:** The owner's rule. The litter sizes seen in the VV3 log (88
  singletons and 8 twin pregnancies in 96 conceptions) fit the 1 to 3 babies a
  litter can have (#434).
- **Exceptions:** None for the shared fields. Code that de-duplicates
  "identical records written together" would delete real children, and is a
  defect.
- **Status:** non-bug.

### L3. One father on many or all conceptions

- **Behaviour:** The same father's name repeats down the whole Births and
  Conceptions log.
- **Game(s) / subsystem:** All five games. Births and Conceptions log, Village
  Population log.
- **Conditions:** A village with one dominant breeding male.
- **Decision source:** Owner decision, recorded 2026-09-25 in #434 (item 4).
- **Evidence:** In the owner's running VV3 village all fourteen pregnant women
  carried father "Machu" (head 26, body 23). Machu was a real living villager
  in slot 53 with those values, and other records in the same village carried
  different fathers (live memory read).
- **Exceptions:** None by itself. A repeated value is only suspicious if the
  named villager does not exist or his own fields do not match the copy.
- **Status:** non-bug.

### L4. Villages edited by the player can be uniform to any degree

- **Behaviour:** Many or all villagers share an appearance, a name or any other
  field; values fall outside the games' normal pools or inheritance patterns.
- **Game(s) / subsystem:** All five games. All logs and tools that read
  villagers.
- **Conditions:** The player changed the village with Cheat Engine, a mod, or
  the patcher's own features.
- **Decision source:** Owner decision, 2026-09-25, in #434 (item 7).
- **Evidence:** The owner's rule. The logs record what memory holds and must
  not validate, clamp, warn about or de-duplicate values.
- **Exceptions:** None. Before treating uniformity as a bug, ask the owner
  whether the village was modified.
- **Status:** non-bug.

### L5. Head 0, body 0 and age 0 are real values

- **Behaviour:** A record shows `Head: 0`, `Body: 0` or age 0.
- **Game(s) / subsystem:** All five games. All logs, repairs and tools.
- **Conditions:** Any villager. The first entry of every game list is index 0
  ([#442](https://github.com/Lorsieab2/Virtual-Villagers-Fun-Patcher/issues/442)),
  so head 0 and body 0 are the first head and body. Age 0 is a newborn.
- **Decision source:** Owner decision, 2026-09-26, in
  [#443](https://github.com/Lorsieab2/Virtual-Villagers-Fun-Patcher/issues/443);
  age 0 added by the owner on 2026-10-09 for all five games.
- **Evidence:** 322 records in the owner's VV5 saves have a head or body of 0
  ([#345](https://github.com/Lorsieab2/Virtual-Villagers-Fun-Patcher/issues/345)).
  The owner's VV1 log from v1.35.5 printed real mothers with `Body: 0` and
  `Head: 0` (#345).
- **Exceptions:** A record that is *internally inconsistent* (some fields
  correct, others blank, for the same villager at the same moment) is still
  strong evidence of a defect (#443). Code that treats 0 as "unknown" is a
  defect; "unknown" needs its own flag, a negative value or no record.
- **Status:** non-bug.

### L6. "(none)" for a like or dislike

- **Behaviour:** A villager's likes or dislikes print as `(none)`.
- **Game(s) / subsystem:** All five games. All logs that print likes and
  dislikes.
- **Conditions:** The slot in the villager's likes or dislikes array is empty.
- **Decision source:** #434 (item 1).
- **Evidence:** Likes and dislikes are arrays in all five games; `(none)` is an
  empty slot, not a failed read (#434).
- **Exceptions:** None recorded.
- **Status:** non-bug.

### L7. A Birth record no longer matches the villager's current look

- **Behaviour:** A villager's head or body today differs from its Birth record.
- **Game(s) / subsystem:** All five games. Births and Conceptions log.
- **Conditions:** The look changed after birth, for example through Origins
  Change Appearance or an island event (see I4). Birth details are written once
  and never re-derived.
- **Decision source:** #434 (item 5).
- **Evidence:** VV3, Birth records against live memory: every unique-named
  child aged 60 or less matched (7 of 7), every child aged 156 or more differed
  (8 of 8) (#434). Live check of 74 children across all five games found no
  unexplained mismatches
  ([#435](https://github.com/Lorsieab2/Virtual-Villagers-Fun-Patcher/issues/435)).
- **Exceptions:** A mismatch on a child too young to have been changed would
  need investigating.
- **Status:** non-bug.

### L8. Old villages have short or empty parentage logs

- **Behaviour:** A village's Births and Conceptions log is empty, short, or
  missing fields that are only captured at the moment of conception.
- **Game(s) / subsystem:** All five games. Births and Conceptions log.
- **Conditions:** The village's pregnancies and births happened before the
  logging patches were installed. A hook records only what it sees.
- **Decision source:** Owner's account of their VV3, VV4 and VV5 test villages
  (project memory note "preexisting-tribes-predate-the-patches"; undated).
- **Evidence:** VV4 had no log file although more than twenty villagers were
  pregnant in live memory; the pregnancies were already under way before the
  hook existed.
- **Exceptions:** Missing data for a conception that happened *after* the patch
  was installed is not explained by this entry. The note's own VV3 example
  (63 "(not captured for this birth)" father fields) is attributed to a real
  defect in #428 and #436; see "Conflicts" at the end.
- **Status:** non-bug.

### L9. A new log file that holds only the village header

- **Behaviour:** A log rolls to a new numbered file that, when first read,
  contains only the `Village:` header line. The older file has records and no
  header.
- **Game(s) / subsystem:** All five games. Births and Conceptions log rotation.
- **Conditions:** The older file was written before headers existed, so it is
  treated as belonging to any village; the new file opens with the header for
  the village now being played. Reading at the wrong moment catches the new
  file between its header write and its first record.
- **Decision source:** Comment on #434 (2026-09-26) and #435, closed as not a
  defect.
- **Evidence:** VV4 `Log 2.txt` was 36 bytes when first read and 579 bytes with
  2 conceptions minutes later, while the game ran (#434). The related "DLL
  discrepancy" in #435 was a local checkout 115 commits behind `main`; the
  committed and deployed DLLs were byte-identical.
- **Exceptions:** A header file that never receives records after a conception
  would need a second look. Read a live log twice before concluding.
- **Status:** non-bug.

### L10. Start Over deletes the village's log files

- **Behaviour:** Pressing Start Over deletes the whole log files that belong to
  the village being erased.
- **Game(s) / subsystem:** All five games. Start Over reset.
- **Conditions:** Start Over. The game keeps the same tribe name and save slot,
  so the new village cannot be told apart from the old one by its log header.
- **Decision source:** Owner decision ("START OVER DELETING STUFF IS
  INTENTIONAL"), project memory note "history-logs-are-never-deleted"; reset
  hook documented in `docs/start-over-reset-hook.md`.
- **Evidence:** The logs only ever append; nothing rewrites or removes a record
  outside Start Over. Rolling to a new numbered file leaves earlier files whole.
- **Exceptions:** The Village History log is never touched by a reset. Any
  other removal or rewriting of a log entry is a defect.
- **Status:** approved behaviour.

### L11. A birth filed in a different log file from its conception

- **Behaviour:** A birth record lands in log file 2 while its conception is in
  log file 1.
- **Game(s) / subsystem:** VV1 (where it was analysed). Births and Conceptions
  log rotation.
- **Conditions:** Two pregnancies overlap across a rollover, which needs 256
  conceptions in one log first.
- **Decision source:** [#424](https://github.com/Lorsieab2/Virtual-Villagers-Fun-Patcher/issues/424),
  closed on the owner's judgement that it does not happen in actual games.
- **Evidence:** Codex review of #423; static analysis of the call graph. The
  two related defects (the 256th birth rolling over, and post-rollover births
  going back to log 1) were fixed in #423 and shipped in v1.35.21.
- **Exceptions:** Reopen #424 if a real village reaches the 256-conception
  boundary.
- **Status:** approved behaviour (accepted limitation).

### L12. Village History has no pregnancy lines

- **Behaviour:** The Village History log lists a villager's parents but never
  "Pregnant", the father of a child she is carrying, or the number of babies.
- **Game(s) / subsystem:** All five games. Village History and Village
  Population logs.
- **Conditions:** Always. Pregnancy is current state and belongs in Village
  Population only.
- **Decision source:** Owner decision, project memory note
  "village-history-has-no-pregnancy-lines" (undated).
- **Evidence:** The owner's instruction.
- **Exceptions:** None.
- **Status:** approved behaviour.

### L13. A record for a villager who is not in the tribe

- **Behaviour:** A conception record names villagers who appear in none of the
  tribe's saves, at the top of the first saved village's log.
- **Game(s) / subsystem:** Seen in VV3 and VV5. Births and Conceptions log.
- **Conditions:** The window before a new village's first save, when the game
  is already running villager records.
- **Decision source:** `docs/game-data-conventions.md` ("The games simulate
  villagers before the player's tribe exists"); the owner confirmed no earlier
  tribe had been started in that VV3 session.
- **Evidence:** The owner's first v1.35.27 VV3 tribe logged seven conceptions
  between fourteen such villagers; VV5's own `ldwLog.txt` named two more. Where
  the simulation comes from is UNVERIFIED.
- **Exceptions:** None recorded.
- **Status:** non-bug.

### L14. A renamed-in-place villager counts as the same villager

- **Behaviour:** The Unaccounted Villagers check treats a living villager
  overwritten in place (for example with Cheat Engine) by someone of the same
  sex as the same villager.
- **Game(s) / subsystem:** All five games. Unaccounted Villagers
  reconciliation.
- **Conditions:** Same record, same sex, different name.
- **Decision source:** Owner decision, 2026-10-03 ("leave as is"), project
  memory note "select-all-leaves-experimental-off".
- **Evidence:** The owner's decision.
- **Exceptions:** None. Do not reopen without a new request.
- **Status:** approved behaviour.

---

## Parentage and identity

### P1. A villager's parents can be missing from the living roster

- **Behaviour:** A parent lookup in the living villagers finds nothing.
- **Game(s) / subsystem:** All five games. Parentage, Family Tree, logs.
- **Conditions:** The parent has died, or an island event removed them from the
  village.
- **Decision source:** Owner decision, 2026-09-26, in #443.
- **Evidence:** In the owner's VV5 saves, 60 historical records were skipped in
  one check only because the parent was no longer living (#345).
- **Exceptions:** In VV2 to VV5 both parents are stored on the child's own
  record, so code that loses a parent there because it searched by name is a
  defect (#436, rule 2).
- **Status:** non-bug.

### P2. VV2 to VV5 children's heads cluster, and some land far from their parents

- **Behaviour:** Heads repeat heavily across a village, and some children have
  a head far from either parent's.
- **Game(s) / subsystem:** VV2, VV3, VV4, VV5 (not VV1). Appearance
  inheritance.
- **Conditions:** A child's head is roughly the average of the parents' head
  numbers, with a spread of up to about three either side. Black and blonde sit
  at the ends of the head images, so villages drift toward brown and red.
- **Decision source:** Owner decision, recorded in #434 (item 6, corrected to
  "average, not range"). Primary source: LDW Official Forums thread #132603
  (2008).
- **Evidence:** The owner's VV3 log: 61 children on only 14 head values, mostly
  heads 11 to 22, plus one at head 1 (#434). The forum thread documents
  children far from the parents' average with no known pattern.
- **Exceptions:** None. Nothing may check a child's head against its parents'.
- **Status:** non-bug.

### P3. Every head and body fits every age; children can be Tribal Chiefs

- **Behaviour:** A child wears an adult-looking head, body or chief's robe.
- **Game(s) / subsystem:** All five games (Tribal Chief: VV3). Change
  Appearance, Custom Island Event.
- **Conditions:** Any.
- **Decision source:** Owner decision, 2026-10-06 (project memory note
  "heads-bodies-fit-every-age").
- **Evidence:** The owner's knowledge of the games: children can be Tribal
  Chiefs naturally in play.
- **Exceptions:** None. Do not gate an appearance or role change on age.
- **Status:** non-bug.

### P4. Saves hold stale villager records after the living ones

- **Behaviour:** A save file contains plausible-looking villager records that
  the game does not load.
- **Game(s) / subsystem:** All five games. Save files and every patcher save
  reader.
- **Conditions:** Left over from deaths, departures or a village restarted in
  the same slot. The game loads villagers in order and stops at the first
  record whose present flag is not 1. VV2 zeroes everything after its last
  villager instead.
- **Decision source:** Live measurement, 2026-10-06 (project memory note
  "saves-hold-stale-villager-records").
- **Evidence:** Loading copies of the owner's saves in v1.35.61 and counting the
  game's own table: for example VV4 slot 43 held 115 plausible records and the
  game loaded 5; VV5 slot 25 held 106 and the game loaded 90.
- **Exceptions:** The Lost Children's Esteemed Elder statues are active records
  but are not villagers. A patcher reader that counts stale records as living
  villagers is a defect.
- **Status:** non-bug (game behaviour).

### P5. Children with no parents, and births with no father

- **Behaviour:** A child has no parents at all, or a birth has no father.
- **Game(s) / subsystem:** All five games. Parentage.
- **Conditions:** Children spawned by an island event or a Barrel of Babies did
  not come from a mother's delivery and have no parents. Some events start a
  pregnancy with no father: VV2's Gong of Wonder writes the game's own `"?"`
  placeholder with head 0 and body 0.
- **Decision source:** Owner decision (project memory note
  "fallback-father-for-fatherless-births"); #436 rule 8 (2026-09-26);
  `docs/game-data-conventions.md` ("A villager can be born without a father on
  purpose").
- **Evidence:** VV2's Gong passes the `"?"` string at `0x476290`, which is not
  inside any villager record (static analysis, `docs/game-data-conventions.md`).
- **Exceptions:** VV1 has no event that forces nursing, so a fatherless VV1
  birth would be unexpected. How a fatherless birth is labelled is not settled
  in one place; see "Conflicts" at the end.
- **Status:** non-bug.

### P6. A New Home does not store parents

- **Behaviour:** Stock VV1 keeps no parents on the villager record; the patcher
  has to track them itself.
- **Game(s) / subsystem:** VV1. Parentage.
- **Conditions:** Always.
- **Decision source:** Owner requirement, #436 (rule 5).
- **Evidence:** Static analysis recorded in #345: VV1's conception routine
  receives a partner value and never stores it.
- **Exceptions:** None. This is a structural difference, not a defect.
- **Status:** approved behaviour.

### P7. A New Home's Golden Child is born at 5 years and stays 5

- **Behaviour:** The Golden Child is 100 age units (5 years) at birth and never
  ages.
- **Game(s) / subsystem:** VV1. Ageing, Births log, Golden Child puzzle.
- **Conditions:** Any Golden Child.
- **Decision source:** Owner decision, 2026-10-08 (project memory note
  "golden-child-is-always-five").
- **Evidence:** The owner's log ("Age when recorded: 100"); the game's own
  Golden Child test `cmp [rec+0x36C], 0xC7` in the ageing tick at `0x42E5A4`
  ([#448](https://github.com/Lorsieab2/Virtual-Villagers-Fun-Patcher/issues/448)).
- **Exceptions:** Any *other* villager not ageing is a defect (#448: record 0
  was wrongly skipped by Time Warp).
- **Status:** non-bug (game behaviour).

### P8. A newborn only becomes its own villager at age 2

- **Behaviour:** A newborn's record carries its parents from birth, but its
  name and villager identity arrive at age 2.
- **Game(s) / subsystem:** All five games. Births, naming.
- **Conditions:** Every ordinary child.
- **Decision source:** Owner's description of the games (project memory note
  "children-become-villagers-at-age-two"; undated).
- **Evidence:** Static analysis found no name write on the birth path.
- **Exceptions:** The VV1 Golden Child (P7).
- **Status:** non-bug (game behaviour).

### P9. A nursing baby vanishes with its mother and gets no grave

- **Behaviour:** When a nursing mother dies, only she gets a grave; her nursing
  baby disappears with no grave or skeleton.
- **Game(s) / subsystem:** All five games. Deaths, graves, Births log.
- **Conditions:** A pregnant or nursing mother dies before the baby becomes a
  full villager.
- **Decision source:** Owner decision, 2026-10-09 (project memory note
  "nursing-babies-vanish-only-villagers-get-graves").
- **Evidence:** The owner's knowledge of the games: only full villagers make
  graves and skeletons.
- **Exceptions:** The lost baby must still be accounted for in the logs, not
  left as "Unaccounted".
- **Status:** non-bug (game behaviour).

---

## Statistics

### S1. Zeros in the Village Statistics log written at village creation

- **Behaviour:** The log written when a village is created shows 0 for counters
  such as Highest Population and Oldest Villager.
- **Game(s) / subsystem:** Seen in VV2. Village Statistics log.
- **Conditions:** The game sets these counters a moment after creation; the
  next clean save refreshes the log.
- **Decision source:** Owner decision, 2026-09-30 ("the statistics log updates
  so it won't matter").
- **Evidence:** New VV2 village in v1.35.41: log read 0 and 0; live memory read
  7 and 26; after loading and quitting cleanly the log read 7 and 26.
- **Exceptions:** A counter still wrong after a clean save and quit is a
  defect.
- **Status:** non-bug.

### S2. Highest Population higher than the roster

- **Behaviour:** Highest Population is larger than the number of villagers
  listed.
- **Game(s) / subsystem:** All five games. Village Statistics log.
- **Conditions:** A pregnant or nursing mother's babies add 1 to 3 to the
  game's population counter.
- **Decision source:** Owner decision, 2026-09-30 (project memory note
  "pending-babies-count-toward-population").
- **Evidence:** New VV4 village (v1.35.41): five villagers, one pregnant,
  Highest Population 6. VV3 showed Population 101 for 86 loaded villagers on
  2026-10-06.
- **Exceptions:** A difference the pending babies do not explain.
- **Status:** non-bug.

### S3. New Believers' Heathens never count in the statistics

- **Behaviour:** Heathens are left out of every Village Statistics row except
  Heathens Converted.
- **Game(s) / subsystem:** VV5. Village Statistics log.
- **Conditions:** Always. A converted Heathen is a believer and counts from the
  moment of conversion.
- **Decision source:** Owner decision, 2026-09-30, made row by row.
- **Evidence:** A new VV5 village (v1.35.41) read Oldest Villager 50 from a
  Heathen while Highest Population counted only believers; the owner then ruled
  every row believers-only.
- **Exceptions:** Heathens Converted is the only Heathen row.
- **Status:** approved behaviour.

### S4. New Believers never makes Heathen graves

- **Behaviour:** No Heathen grave exists, so no burial or baseline code handles
  one.
- **Game(s) / subsystem:** VV5. Villagers Buried, Mausoleum baseline.
- **Conditions:** Always.
- **Decision source:** Owner decision, 2026-09-30 ("No heathen graves are made
  ever").
- **Evidence:** A read-only scan of the owner's 65 VV5 saves found no Heathen
  corpse or grave. Static analysis suggested one was theoretically reachable
  through a bad outcome of The Missing Kids; the owner's ruling outranks it.
- **Exceptions:** None. A Heathen-grave guard would be dead code.
- **Status:** non-bug.

### S5. Babies Made, Twins Birthed and Triplets Birthed count at conception

- **Behaviour:** These rows rise when a pregnancy starts, not when the baby is
  delivered.
- **Game(s) / subsystem:** All five games. Village Statistics log.
- **Conditions:** Always. This is the games' own behaviour.
- **Decision source:** Owner decision, 2026-09-29 (project memory note
  "statistics-rows-count-what-they-say").
- **Evidence:** The code that writes the counters.
- **Exceptions:** None recorded.
- **Status:** approved behaviour.

### S6. Triplet counts and catch-up food

- **Behaviour:** The triplet counts and the food counted during catch-up in
  Village Statistics were reviewed and are not bugs.
- **Game(s) / subsystem:** Village Statistics log.
- **Conditions:** As reviewed in the 2026-10-10 statistics work.
- **Decision source:** Owner decision, 2026-10-10.
- **Evidence:** The owner's decision; no further evidence is recorded here.
- **Exceptions:** None recorded.
- **Status:** non-bug.

### S7. VV2 "Special Stews Found" and "Real Hours Played"

- **Behaviour:** VV2's Special Stews Found counts distinct stew recipes
  discovered. Real Hours Played is real time since the village was founded,
  not time spent playing.
- **Game(s) / subsystem:** VV2 (Special Stews Found); all five games (Real Hours
  Played). Village Statistics log.
- **Conditions:** Always. Both are the games' own formulas.
- **Decision source:** Owner decision, 2026-09-29.
- **Evidence:** The code that writes the counters.
- **Exceptions:** None recorded.
- **Status:** approved behaviour.

### S8. The games' own "Special Stews Found" text on the twins counter

- **Behaviour:** In VV3 to VV5 the games' own label for the twins counter
  (`eTwinsBirthed`) reads "Special Stews Found". The patcher leaves the game
  text alone.
- **Game(s) / subsystem:** VV3, VV4, VV5. Game statistics text.
- **Conditions:** No screen in normal play shows it: VV3 builds the page but
  never adds its tab, and VV4 and VV5 removed the page.
- **Decision source:** Owner decision, 2026-09-29 (skip the change).
- **Evidence:** Static analysis of the statistics pages. The patcher's log
  already labels the row "Twins Birthed".
- **Exceptions:** None.
- **Status:** approved behaviour.

### S9. Villagers Buried higher than the old Villagers Died row

- **Behaviour:** An older export showed Villagers Buried 61 and Villagers Died
  21.
- **Game(s) / subsystem:** All five games. Village Statistics log.
- **Conditions:** Buried was seeded from the graves already in the save; Died
  counted only deaths after the patch was installed.
- **Decision source:** [#342](https://github.com/Lorsieab2/Virtual-Villagers-Fun-Patcher/issues/342);
  the owner then had Villagers Died removed (shipped in #349).
- **Evidence:** The two rows measured different windows; both were correct.
- **Exceptions:** None. The Died row is no longer exported.
- **Status:** non-bug.

### S10. Everything from the cauldron is a stew

- **Behaviour:** The stews statistics count every successful cauldron product,
  including The Tree of Life's cloth pulp and soap brews.
- **Game(s) / subsystem:** All games with a cauldron. Stews statistics.
- **Conditions:** A successful brew. A failed brew (cold pot) makes nothing and
  is not a stew.
- **Decision source:** Owner decision, 2026-09-30.
- **Evidence:** In VV4 both special brews leave through the same success exit
  the statistics hook records (static analysis).
- **Exceptions:** Failed brews.
- **Status:** approved behaviour.

### S11. The Tree of Life's cloth vines count as herbs

- **Behaviour:** Stews made with the vine herbs used for cloth count like stews
  made with any other herb.
- **Game(s) / subsystem:** VV4. Stews statistics.
- **Conditions:** The player puts vine herbs in a stew.
- **Decision source:** Owner decision, 2026-09-30.
- **Evidence:** The owner: players can carry them into other stews.
- **Exceptions:** None.
- **Status:** approved behaviour.

### S12. The Super-Secret Golden Mushroom counts as a mushroom

- **Behaviour:** The Golden Mushroom counts in Mushrooms Found, the patcher's
  statistics, and every goal or achievement that counts mushrooms.
- **Game(s) / subsystem:** All five games. Super-Secret Golden Mushroom patch,
  statistics.
- **Conditions:** Always. By the owner's rule nothing else about the secret is
  documented publicly.
- **Decision source:** Owner decision, 2026-09-29.
- **Evidence:** The owner's rule.
- **Exceptions:** Stock code that checks mushroom types without a golden case is
  a defect to fix.
- **Status:** approved behaviour.

---

## Family Tree

### F1. Reorganize portraits moves portraits nobody dragged

- **Behaviour:** In "Families under their parents", Reorganize portraits can
  move or swap portraits the player did not drag, such as two married-in
  partners.
- **Game(s) / subsystem:** All five games. Family Tree Maker.
- **Conditions:** Pressing Reorganize portraits.
- **Decision source:** Owner decision, 2026-10-09 ("The button is called
  'reorganize' for a reason").
- **Evidence:** Reported during the v1.35.65 review.
- **Exceptions:** Someone changing generation, lines joined to the wrong
  people, a crash or lost edits are still defects.
- **Status:** approved behaviour.

---

## Gameplay

### G1. A village saves only on a clean quit

- **Behaviour:** A session's progress, and any patcher file written at save
  time, is lost if the game is killed or crashes.
- **Game(s) / subsystem:** All five games. Saving.
- **Conditions:** The player must load a village and then close the game
  normally.
- **Decision source:** Owner's account of the games, 2026-09-30.
- **Evidence:** The owner's description.
- **Exceptions:** None.
- **Status:** non-bug (game behaviour).

### G2. Builders only start a population hut the player has started

- **Behaviour:** Builders do not begin a new population hut until the player
  has dropped a villager on it at least once (progress 2 or more). After that
  they finish it at any population, including during catch-up.
- **Game(s) / subsystem:** All five games. Builder behaviour, population huts.
- **Conditions:** In VV1, the stock auto-start above 22 villagers (hut 10) and
  45 (hut 11) is kept. Every other construction project keeps stock rules.
- **Decision source:** Owner decision, final wording 2026-10-01, after two
  earlier versions (one shipped in v1.35.43).
- **Evidence:** The original games show a hut's scaffold at one population but
  only let builders work above a higher one, and abandon it if the population
  falls (VV1 15/28 shown, more than 22/45 to build).
- **Exceptions:** None.
- **Status:** approved behaviour.

### G3. Builders build before they fix huts

- **Behaviour:** Builders do new construction first; a hut fix only happens
  when there is nothing to build.
- **Game(s) / subsystem:** All five games. Builder patches.
- **Conditions:** Always.
- **Decision source:** Owner decision, 2026-09-30.
- **Evidence:** The owner's report that builders fixed huts ahead of building
  new ones; fixed in VV1 on branch fix/vv1-builders-build-before-fixing.
- **Exceptions:** A builder fixing a hut while construction is available is a
  defect.
- **Status:** approved behaviour.

### G4. Catch-up does not run the live scheduler; per-patch catch-up rules

- **Behaviour:** Load-time catch-up and Time Warp pick jobs directly instead of
  running the per-frame idle scheduler. Patches inside the job dispatcher act
  during catch-up; scheduler hooks do not unless the owner decided otherwise.
- **Game(s) / subsystem:** All five games. Catch-up, behaviour patches.
- **Conditions:** Catch-up. Most births happen here too.
- **Decision source:** Owner decisions, 2026-10-01 (project memory notes
  "catch-up-design-decisions" and "catch-up-is-the-main-birth-path"): Builders
  and Healers Work First acts in catch-up at about 3 in 4 for Building, Healing
  and Devotion only; the "regardless of food" bypass stays stock in catch-up;
  Easier Devotee Training is live only; VV2 Healers Study continues in
  catch-up.
- **Evidence:** Each game's catch-up worker calls the stock picker and
  dispatcher directly (static analysis). A real Time Warp birth in VV1 was
  missed by a hook placed only on the live birth site.
- **Exceptions:** None. Do not reopen these choices.
- **Status:** approved behaviour.

### G5. Birth Control's "25% non-preference fallback" is dead code

- **Behaviour:** Code in the breeding chooser describes a 25% fallback; it
  never decides anything in play.
- **Game(s) / subsystem:** VV1, VV2, VV3 Birth Control (compared against VV4
  and VV5).
- **Conditions:** Always.
- **Decision source:** Owner decision, 2026-09-30.
- **Evidence:** The owner's ruling. More generally, code found in a stock game
  is not proof that it runs (owner decision, 2026-09-30).
- **Exceptions:** None. Do not raise it again.
- **Status:** non-bug.

### G6. "Watering the field" is A New Home's garden-puzzle job

- **Behaviour:** VV1 has three different watering actions: "Watering crops"
  (Farming), "Trying to water strange patch" (well water, no progress), and
  "Watering the field" (lagoon water, advances the garden puzzle).
- **Game(s) / subsystem:** VV1. Jobs, Watering Trains Building patch.
- **Conditions:** "Watering the field" only makes progress once the lagoon
  puzzle is complete.
- **Decision source:** Owner corrections, 2026-09-29.
- **Evidence:** String 201 / job `0x445020`, string 202 / job `0x4452A0`, string
  588 / job `0x43FC20`.
- **Exceptions:** None.
- **Status:** non-bug (game behaviour).

### G7. VV1 healers with nobody sick only study the cactus if a player set them to

- **Behaviour:** In A New Home, a healer with no sick villager studies the
  Medical Cactus only if a player drop had already set them to study;
  otherwise the Healing job does nothing.
- **Game(s) / subsystem:** VV1. Healing job.
- **Conditions:** Nobody in the village is sick.
- **Decision source:** Found 2026-10-10. A fix is pending the owner's decision.
- **Evidence:** Static analysis only, 2026-10-10. See
  `docs/hidden-gates-all-five-games.md`, VV1 section 4, item 52 (`0x447894`
  to `0x4478E5`; `cmp [rec+3B8h],9`).
- **Exceptions:** Not applicable.
- **Status:** open defect.

### G8. VV3 to VV5 healers with nobody sick study only after a stock gate

- **Behaviour:** With nobody sick, healers study medicine on their own only
  after a stock gate is passed: Medicine level 2 (The Secret City), a built
  hospital (The Tree of Life), or the Pain Totem dismantled (New Believers).
  Before that they do nothing.
- **Game(s) / subsystem:** VV3, VV4, VV5. Healing job.
- **Conditions:** Nobody is sick and the game's gate is not yet met.
- **Decision source:** Session findings, 2026-10-10.
- **Evidence:** Static analysis only. `docs/hidden-gates-all-five-games.md`:
  VV3 section 4 (`0x45B69E`), VV4 section 4 item 56 (`0x46420C`), VV5 section 4
  item 44 (`0x46CD24`).
- **Exceptions:** Not observed in play.
- **Status:** non-bug (stock behaviour).

---

## Island Events

### I1. Unused events copied word for word from an earlier game stay off

- **Behaviour:** An island event that exists in a game's files but never runs,
  and whose text matches an earlier game's event word for word, is not
  restored.
- **Game(s) / subsystem:** All five games, notably VV3, VV4 and VV5. Restore
  Missing Island Events and similar work.
- **Conditions:** The games were built from each other, so such events are
  leftovers.
- **Decision source:** Owner decision, 2026-10-09. Earlier, on 2026-10-04, the
  owner left The Tree of Life's and New Believers' never-run events alone (The
  Canoe from the Other Side; The Stinging Wasps, The Abandoned Infants).
- **Evidence:** The owner's rule.
- **Exceptions:** Events whose text is original to that game can be candidates.
  Near-copies go to the owner with the exact differences.
- **Status:** approved behaviour.

### I2. The Arc of Brilliant Colors is not weather

- **Behaviour:** The Arc of Brilliant Colors is an island event (a villager sees
  a rainbow), not a weather state. There is no rainbow weather.
- **Game(s) / subsystem:** VV4 (event text in The Tree of Life). Island events,
  weather.
- **Conditions:** Always.
- **Decision source:** Owner correction, 2026-10-10.
- **Evidence:** The owner's correction. The event's settings are listed in
  `docs/story-island-outcomes.md` (The Tree of Life).
- **Exceptions:** None.
- **Status:** non-bug.

### I3. The Furry Food's "a few villagers" text

- **Behaviour:** In A New Home's restored event The Furry Food, "Remove the
  moldy pieces" keeps the original 50% sickness chance per villager and the
  original "a few villagers" text, which do not quite match.
- **Game(s) / subsystem:** VV1. Restore Missing Island Events.
- **Conditions:** That choice in that event.
- **Decision source:** Owner decision, 2026-10-04 (leave as is).
- **Evidence:** The original event code and text.
- **Exceptions:** None.
- **Status:** approved behaviour.

### I4. An island event can change a villager's head without a record

- **Behaviour:** A villager's head changes with no "Appearance changed" record
  in the logs.
- **Game(s) / subsystem:** Seen in VV1. Island events, logs, Family Tree.
- **Conditions:** An island event changes the look. The patcher only logs
  Change Appearance.
- **Decision source:** Owner report, 2026-10-08 (project memory note
  "island-events-can-change-a-villagers-head").
- **Evidence:** Papu Tamikai was born a twin with head 16 and has head 5 in the
  save. The Family Tree reader handles it (`_unrecorded_looks` in
  `src/vv_genealogy.py`).
- **Exceptions:** None.
- **Status:** open defect (logging these changes was offered; pending the
  owner's answer on which event and go-ahead).

---

## Conflicts between sources

These were found while writing the register. They are listed, not resolved.

1. **Old-tribe explanation versus #428 and #436.** The memory note
   "preexisting-tribes-predate-the-patches" explains VV3's 63 "(not captured for
   this birth)" father fields as an old tribe that predates the hook (L8).
   #428 (closed) and #436 attribute "(not captured for this birth)" in VV2 and
   VV3 to a real defect: their conception hooks passed no father pointer and
   fell back to a by-name scan.
2. **Father's age at conception.** #345 (closed, 2026-09) says the father's age
   is deliberately not recorded, by the owner's instruction to record only the
   mother's age, and that no game copies it. The memory note
   "only-the-mothers-age-matters-at-conception" says the owner later reversed
   that and wants the father's age captured from his own record at conception.
3. **How a fatherless birth is labelled.** The memory note
   "fallback-father-for-fatherless-births" gives a fatherless birth a fallback
   father named "Unknown" with head 0 and body 0. #436 rule 8 (open) says
   "never invent a father", and `docs/game-data-conventions.md` says VV2's Gong
   uses the game's own `"?"` and the log must not invent one.
