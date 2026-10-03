VIRTUAL VILLAGERS -- HIDDEN GATES IN ALL FIVE GAMES
===================================================
What decides whether a villager works, builds, breeds, heals or researches,
and how much it produces: every population, food, age, skill, level and
random-roll condition in the original games' code, in plain language.

Date: 2026-10-01 (written for the owner; kept in the repository as research)
Games: A New Home (VV1), The Lost Children (VV2), The Secret City (VV3),
       The Tree of Life (VV4), New Believers (VV5) -- the stock executables.

HOW THIS WAS DONE, AND HOW FAR TO TRUST IT
------------------------------------------
- Each game's own executable was taken apart instruction by instruction. Every
  rule in this report cites the address in the game and the exact number it
  uses, so any line can be checked.
- No game was launched for this report. Nothing here has been watched
  happening in play yet. Where a rule could not be traced back to code the
  game actually runs, it is marked UNVERIFIED-REACHABILITY.
- The original games contain code the developers wrote and never switched on
  ("developer-dead"). Rules found only in dead code are listed separately and
  do NOT affect play.
- Ages: 20 internal age units = 1 year everywhere. One unit is about 6 real
  minutes at Normal speed, so a game year is about 2 real hours (worked out
  from the code, not timed).
- "Catch-up" means the time the game replays when you come back after it was
  closed (and Time Warp). Several rules are different there -- see below.

THE BIG PICTURE (rules shared by most or all games)
---------------------------------------------------
1. Most "thinking" does nothing. When an idle villager decides what to do,
   about two times in three nothing happens at all (VV1-VV5).

2. Picking a job is a dice roll on the skill. A villager only considers a job
   whose skill is above 5. Even then the job is taken with a chance of
   (skill + 40)%. A villager whose skills are all 5 or lower never picks a job
   on their own (VV2-VV5; VV1 uses the same skill + 40 roll).

3. Every task is another dice roll, and a failure wastes it. Each completed
   job step succeeds with a chance of (skill + 34)% -- the roll is 0-99 and
   passes at skill + 33 or below; VV1 uses skill + 31. A villager who LIKES
   "learning" gets +66 instead of +33; one who DISLIKES it gets only +16. In
   VV4/VV5 Learning tech adds +15 or +30. A failed roll gives no food, no
   build progress, no tech points, no cure and no baby.

4. Who never works. Children under 14, sick villagers, and pregnant or nursing
   mothers never pick a job (VV2-VV5). In VV3 the Tribal Chief never does.
   In VV4/VV5 villagers who don't like "work" refuse 15% of the time, and
   those who dislike it refuse another 70%.

5. Low food changes behaviour. At 250 food or less (VV3-VV5), villagers with
   Farming 20+ farm first and about half of everyone else just stands
   "Worried about food". In VV1, at 400 food or MORE a villager gets one job
   roll instead of two.

6. Builders rarely start a new building on their own. In VV3, VV4 and VV5
   they only continue one that already has progress, so a newly unlocked hut
   or project sits untouched until you drop a villager on it. In VV1 the
   first hut needs nothing and huts 2 and 3 are started on their own once the
   population reaches 23 and 46 (see VV1 gate 29); only VV1's other projects
   need existing progress. In VV2 a builder must be dragged to huts 2 and 3
   once.

7. Breeding needs adults and luck.
   - Both partners must be 18 or older in every game.
   - Women 50 or older cannot conceive in live play (VV2-VV5; in VV1 there is
     no upper age limit).
   - Conception roll: roughly "a random number up to 300 must be no more than
     Parenting skill + 50 per Medicine level - 50" (all five games, small
     differences per game). Low Medicine and low Parenting mean most attempts
     fail.
   - Low food makes embraces fail: below 400 food in VV1 (74% fail, even
     when YOU drag the couple together), below 300 food in VV2 (34% fail).
   - VV4/VV5 need the Love Shack built for any live conception. In VV4
     villagers only embrace on their own if you set their preference to
     Parenting.
   - Twins and triplets only happen at Medicine level 3 (VV2-VV5; about 7% of
     births, a quarter of those triplets). VV1 needs Fertility 3 or the
     strange-fish puzzle for twins, and both for triplets.
   - Heathens never conceive (VV5).

8. Huts cap the population. Each game stops births at certain head-counts
   until the next population hut is finished:
   - VV1: 15 / 25 / 50 people need huts 1 / 2 / 3 (hut 2 starts at 23-24
     people, hut 3 at 46-49 -- a narrow window; unborn babies count).
   - VV2: 15 / 25 / 50 villagers need 1 / 2 / 3 huts.
   - VV3: 10 / 17 / 35 need 1 / 2 / 3 finished huts.
   - VV4/VV5: 10 / 17 / 35 (VV5 counts believers: 17 and 35).
   The overall cap is 90 plus a bonus for finished collections: up to 115
   in VV4 (four collections of 5), up to 105 in VV5 (a +15 total); VV3 also
   adds Magic 3.

9. Healing is a skill roll too. A cure succeeds with about (Healing skill +
   31-34)% chance. A healer who DISLIKES medicine fails half their cures
   regardless (VV3-VV5). In VV5 healers never treat sick Heathens.

10. Research pays tech points = Research skill divided by a number that
    depends on Science level (VV1: 7/5/3; VV2: 11/9/5; VV4/VV5: 11/9/7). A
    researcher whose skill is below that number earns nothing from the base
    formula; in VV1 that is nothing at all, but in VV2-VV5 a success can still
    earn the game's bonuses (lit fire, chief, Magic, collections). The game
    speed setting also changes the amount per action: Fast gives MORE food
    and tech points per successful action, Slow gives less (in VV3-VV5 the
    payout is divided by speed/6, where the speed value is 3 on Fast, 6 on
    Normal and 10 on Slow).

11. Time away plays by different rules. Catch-up/Time Warp breeding skips
    almost all the live checks in VV4 and VV5 (no Love Shack, no Parenting
    roll, and an initiating mother aged 50 or over is not refused; the partner
    search still rejects a partner aged 50 or over) -- which explains older
    mothers after time away. In VV2 the man can be any age away, and children
    inherit more skill (10-19 instead of 4-11). Research pays MORE during
    catch-up in VV2 and VV4, and building is slower in VV2. In VV1 one healing
    action during catch-up can cure every sick adult at once.

THE TOP SURPRISES
-----------------
- VV1: a "fix huts" check, a 74% embrace failure below 400 food that even
  applies to your own drag-and-drop, and research that stops entirely once
  all six techs reach level 3 unless you assign someone to research.
- VV2: huts never decay -- "fixing" a hut is pure skill practice. The
  hospital neither cures nor reduces disease; only Medicine and a lit fire do.
- VV3: buying Science 1 appears to CUT research per success from skill / 5 to
  skill / 11 (worth checking in play). At Medicine 0, only villagers 42+ can
  get sick.
- VV4: a failed Parenting roll gives +4 Parenting to anyone above 0, while
  every other skill gives +4 only at exactly 0 -- a developer slip in the
  original game. Hut 3 gets 1 build point per trip against 2,000 needed
  (hut 1 gets 12). Easy difficulty runs only a quarter of the sickness checks.
- VV5: nobody farms on their own until the fence is made into a granary. In
  villages of 6 or fewer believers the baby's sex is forced to fix an
  imbalance. Healers only study medicine on their own (with nobody sick) once
  the Pain Totem is dismantled; catch-up does no research until the Knowing
  Totem is dismantled.

DEAD CODE FOUND (does not affect play)
--------------------------------------
- A demo-era "population under 7" limit in VV1, VV2 and VV4: its switch is
  always set off in the shipped games.
- A 25% "have children without the preference" fallback in the job chooser
  (VV4, VV5).
- VV5 building options 5 and 10; VV4's Science-level-0 research branch.

PROBLEMS THIS HUNT FOUND IN THE PATCHER'S OWN FILES (recorded, NOT changed)
--------------------------------------------------------------------------
These were found in passing. You did not ask for them to be fixed, so
nothing was changed. Say the word and they become pull requests.

1. LOGS SHOW THE WRONG LIKES/DISLIKES IN TWO GAMES -- confirmed by comparing
   the patcher's word lists with each game's own list (both the population
   and parentage exporters use them):
   - The Secret City: entries 62 and 63 print "frogs" and "soap"; the game's
     own words are "alchemy" and "potions". (VV4 and VV5 really are "frogs,
     soap", which is where the shared list came from.)
   - A New Home: 10 of 47 words are off. The game's list has "rough wood",
     "drift wood" and "birds" and no "learning" or "parrots", so from
     "dancing" onward every word is shifted. A villager who likes "work" is
     logged as liking "parrots", and so on.
   - The Lost Children, The Tree of Life and New Believers match exactly.
   Best confirmed against a villager's Details panel in the game.

2. docs/builders-fix-huts.md says examining a hut leads to a repair 30% of
   the time. VV4's code repairs 70% of the time (0x45CA3C). VV1 has the same
   70/30 roll (0x4468D8, confirmed), but which branch is the repair there is
   not yet confirmed.

3. docs/vv2-easier-healing-research.md mislabels three VV2 skill offsets
   (+0x7E4 is Parenting, +0x7EC Farming, +0x7F4 Research), and VV2 field
   +0x2EB08 is the game-speed setting, not an island event.

4. The breeding research doc treats one routine as the manual drag route
   only (VV2 0x44F610, VV4 0x460C10). It is also the final step of embraces
   villagers start on their own, so its "woman under 50" rule applies to
   both.

5. In catch-up, VV3 and VV4 count a cure in "People Cured" even when the
   cure roll fails. The patcher's Village Statistics may therefore count
   failed cures.

STILL UNKNOWN
-------------
- Which difficulty/speed number means Easy/Medium/Hard and Slow/Fast is
  inferred from the code, not read from a label (VV2, VV5).
- A few VV4/VV5 status effects and record fields are not yet named; see each
  game's section.
- Nothing here has been watched in play. A Time Warp test of the surprising
  ones (VV3's Science 1 research cut, VV4's hut 3 build rate, VV1's food
  embrace penalty) would be the quickest confirmation.

The full per-game reports follow, one section per activity. Each rule has a
plain sentence first, then its evidence line (address, constant, and whether
it is reached).


============================================================================
A NEW HOME (VV1) -- FULL REPORT
============================================================================

# Virtual Villagers: A New Home (VV1): hidden gates in the stock code

Executable: `research/stock-executables/Virtual Villagers - A New Home.exe` (stripped 32-bit, image base 0x400000).
Method: static disassembly (Python + capstone) of the stock exe only. **No game was launched**, so every claim below is
static evidence (tier 4 under the owner's evidence hierarchy) unless a prior live observation from the repo is cited.
Where this report contradicts an existing doc, it says so.

`rand(N)` = stock RNG `0x402F10`, which returns `rand() % N` (0..N-1). So "`rand(100) <= 25`" is a 26% chance.

## Units and conventions used below

- **Age**: 20 internal age units = 1 displayed year (owner-authoritative, `docs/villager-record-reference.md`).
  The game converts real time into age units in the world tick `0x42E900`: `age += (elapsed seconds / 60) / speed`
  (`0x42EAF2..0x42EB0C`). `speed` is state `+0xA318`: **6 = Normal** (default, `0x41C82B`), 3 = "2x speed",
  10 = "1/2 speed", +999 = Paused (`0x429480..0x42954D`; option strings at `0x480400`).
  So at Normal speed **1 age unit = 6 real minutes and 1 displayed year = 2 real hours** (1 hour at 2x speed).
  Static derivation; not timed live.
- Key ages: 280 units = **14 years** (adult), 360 = **18 years** (breeding), 40 = **2 years** (pregnancy length).
- Record fields (stride 0x3D8): health +0x344, age +0x348, "processed age" +0x34C (the per-unit tick cursor),
  gender +0x350 (2 = the mother), sick +0x354, pregnancy stamp +0x358, litter +0x35C, dislikes +0x3A8 (4 slots),
  skills Parenting +0x3BC, Building +0x3C0, Farming +0x3C4, Healing +0x3C8, Research +0x3CC,
  Details-panel job preference +0x3D0 (toggled by the UI at `0x449731..0x44973F`), player-assigned work spot +0x3B8
  (written only by the drop-on-work-area handler `0x4241E2..0x424CEB`).
- Village state (`[mgr+0x3E010]`): food +0xA2EC, tech points +0xA2FC, berry-bush pool +0xA2F4, crop-field pool +0xA2F8,
  difficulty +0xA30C (0 Easy / 1 Medium default / 2 Hard; `0x429578/0x4295A6/0x4295D8`, default `0x41C821`).
- Tech levels (all start at **1**, `0x41C43E..0x41C45C`; max 3): Spirituality +0xA2BC (by elimination), Science +0xA2C4,
  Construction +0xA2CC, Medicine +0xA2D4, Fertility +0xA2DC, Farming +0xA2E4. Mapping proven by use: Science scales
  tech points (`0x43B2E9`), Construction gates projects (`0x4475D7`), Medicine gates sickness/longevity (`0x42E5D4`,
  `0x42EDFC`), Fertility gates twins and the conception roll (`0x43BC28`, `0x43DC6B`), Farming switches food sources
  (`0x4472EB`). Purchase costs, `0x435AF8..0x435D2E` (level 1 to 2 / 2 to 3): Construction 2,500 / 80,000;
  Spirituality 5,000 / 80,000; Farming 6,000 / 50,000; Fertility 11,000 / 240,000; Science 12,000 / 150,000;
  Medicine 15,000 / 250,000. A new village starts with 99 tech points (`0x41C410`).
- Like/dislike indices are read with the **exe's own English list** at `0x47B3xx` ("ants, crowds, resting, laundry,
  medicine, turnips, ..., rocks, rough wood, ..., drift wood, ..., fish, ..., work, lifting, surprises, jokes, sleeping").
  Index 4 = medicine, 5 = turnips, 12 = berries, 15 = rocks, 25 = bushes, 30 = drift wood, 33 = fish, 42 = work.

### Reachability chains (cited by tag)

- **[LIVE-AI]** Village-scene update `0x423390` (a virtual method: its address is stored at vtable slot `0x4598D0`) calls
  the idle sweep `0x448450` at most once every 40 real seconds (`0x4233E7..0x423405`). The sweep runs the adult/child
  scheduler `0x448220` for each villager whose action queue is empty, retrying up to 10 times (`0x448480..0x448492`).
  The action runner `0x448600` (called at `0x42403F` while not paused) also calls `0x448220` one second after a
  villager's queue empties (`0x4487C8`). The runner's opcode 6 is the skill test `0x43D440` (`0x448846`) and opcode 14
  is the reward callback `0x43A230` (`0x4488BE`). The queue-step dispatcher `0x43DEF0` starts opcode 9 at `0x43DAD0`
  (embrace) and opcode 17 at `0x43CEB0` (heal). Prior live evidence that this chain runs: the owner's running village
  showed the Building branch stopping at the level gate (`docs/builders-fix-huts.md`, v1.35.37 section), and live queue
  tracing of the school drum (`docs/vv1-school-lessons-research.md`).
- **[TICK]** `0x423390` calls the world tick `0x42E900` (`0x42348C`). Its per-villager loop runs once per **age unit**
  (`0x42EC60..0x42F156`): eating, health, sickness, old age, birth delivery and catch-up.
- **[CATCH-UP]** Inside [TICK], an adult lagging more than 2 units (that is, away time being replayed) calls `0x42E790`
  five times per unit (`0x42F0E6..0x42F12A`). That routine runs the chooser `0x439AE0` and dispatcher `0x4472C0`, then
  executes the queue instantly in `0x446C70`.
- **[PLAYER]** The village input handler drops the held villager (+0xAD34) on another villager (`0x4251FF..0x4252B9`).
  A sick target leads to the heal queue `0x445580`; any other target leads to the embrace queue `0x445510`. Nothing
  happens while paused (`0x425202`).

A routine marked **REACHED** below sits on one of these chains. **UNVERIFIED-REACHABILITY** means no caller chain was
established.

---

## 0. The idle scheduler, which decides every adult's activity (shared by all five activities)

1. **Two of every three "what should I do?" moments are thrown away.** Each time the scheduler runs, a 66% roll ends it
   with nothing chosen. The 40-second sweep retries up to 10 times; the end-of-task call does not retry.
   Evidence: `0x44825C push 64h; call rand; 0x448266 cmp eax,41h; jle exit` (0..65 = 66%). REACHED [LIVE-AI].
2. **Sick villagers never work, breed or heal others.** A sick adult only wanders (one third drinks well water, one
   third does 0x441CC0, one third does nothing).
   Evidence: `0x44826F cmp [rec+354h],0; jne -> 0x446420(i,100)`; 0x446420 uses `rand(3)` (`0x44643B`). REACHED [LIVE-AI].
3. **Children under 14 never work.** Villagers under 280 age units go to the child routine (play, school, meditation),
   which never calls the job chooser or work dispatcher.
   Evidence: `0x44828A cmp [rec+348h],118h; jge adult; call 0x4479B0`. 0x4479B0 contains no call to 0x439AE0 or 0x4472C0.
   REACHED [LIVE-AI].
4. **Pregnant or nursing villagers do no work for the whole 2-year pregnancy.** Each scheduler call gives them a 20%
   chance of a filler action and otherwise nothing.
   Evidence: `0x4482A5 cmp [rec+358h],0` -> `0x4482DF rand(100); cmp eax,14h; jge exit; call 0x445AD0`. REACHED.
5. **Burial overrides everything.** Once burial is unlocked (state flag +0xA000), any dead body sends the next idle
   adult to bury it before considering any job.
   Evidence: `0x448307 cmp byte [st+0A000h],1` -> `0x43A200` (first corpse) -> `0x443890` "Burying the dead".
   REACHED; the flag's puzzle source was not traced.
6. **A hungry village works harder.** Below 400 food, an idle adult gets an extra job roll first. If that starts
   nothing, the adult resumes the player-assigned work spot, or with 61% probability does a random idle action. At
   400 food or more, that first attempt is skipped and only one job roll remains.
   Evidence: `0x448336 cmp [st+0A2ECh],190h; jge 0x44836F`; 1st roll `0x448347`, fallback `0x447CD0(i,60)` at
   `0x448362`; 2nd roll `0x448374`. REACHED [LIVE-AI]. Note: `docs/vv1-builder-action-fixes-research.md` describes the
   ≥400 path as going to "the general selection path"; that path itself contains a second chooser call, so high food
   halves the job rolls rather than removing them.
7. **The "preference" argument does nothing.** The scheduler passes 1 on the low-food call and 0 on the other, but the
   chooser never reads that argument, so both rolls are identical.
   Evidence: `0x439AE0 ... ret 8`. The only stack reads are `[esp+14h]` (the villager index); `[esp+18h]` is never read.
8. **Low-skill villagers with no work spot just idle.** If a villager's best skill is under 50 and the five skills total
   under 70, the scheduler stops at "resume my assigned work spot, else idle".
   Evidence: `0x44838F call 0x43B520` (highest skill) `cmp eax,32h; jge`; `0x43B5A0` (skill total) `cmp eax,46h; jge`;
   `0x4483AB call 0x447CD0(i,100)`. REACHED.
9. **A very rich village plays.** At 2,000 food or more, a leisure branch (`0x4480F0`) is offered before the
   Spirituality-weighted puzzle branch.
   Evidence: `0x4483D5 cmp [st+0A2ECh],7D0h; jl`. Spirituality roll at `0x4483F3..0x448406`:
   `rand(100) <= 3*Spirituality + 3 per puzzle flag (+9FE0,+A000,+9FD8,+A008)` (`0x41CED0`). REACHED.

### The job chooser `0x439AE0` (REACHED from [LIVE-AI] `0x448347`/`0x448374` and [CATCH-UP] `0x42E7DB`)

10. **15% of job rolls are blank before anything else is considered.**
    Evidence: `0x439AEB rand(100); cmp eax,0Fh; jge continue; else return 0`.
11. **Villagers who dislike work refuse 70% of jobs.**
    Evidence: `0x439B05 push 2Ah (42 = "work"); call 0x4372E0` (dislikes scan) -> `rand(100); cmp eax,46h; jl -> return 0`.
12. **Each of the five skills is skipped 16% of the time, so a villager sometimes picks a weaker skill.** The best
    remaining skill wins. Parenting must beat Farming, then competes at its value minus 15.
    Evidence: per-skill `rand(100); cmp eax,0Fh; jle skip` at `0x439B2B, 0x439B4E, 0x439B78, 0x439BA1, 0x439BF6`;
    `0x439B75 lea esi,[eax-0Fh]`.
13. **Villagers who dislike medicine skip Healing half the time,** even when it is their best skill.
    Evidence: `0x439BCE push 4 (medicine); call 0x4372E0; rand(100); cmp eax,32h; jl skip`.
14. **A job ticked on the Details panel wins 86% of the time,** at the full value of that skill.
    Evidence: `0x439C25 [rec+3D0h] nonzero and != pick` -> `rand(100); cmp eax,55h; jg keep` -> table `0x439CAC`.
15. **The chance to actually start the chosen job is (skill + 40)%.** A score of 1 or less never works through this path.
    So a skill of 10 gives 50%, and 60 or more always works.
    Evidence: `0x439C80 cmp esi,1; jle return0`; `0x439C89 rand(100); add esi,28h; cmp eax,esi; setge` (job if rand < skill+40).

### The work-spot fallback `0x447CD0`

16. **A villager the player dropped on a work area keeps returning to it.** On Medium and Hard this requires at least
    1 point in that job's skill; Easy has no requirement. This route skips several autonomous gates (see 34, 37 and 48).
    Evidence: `0x447CE5 [rec+3B8h]` switch `0x4480A8`; each case `cmp [skill],1; jge go; cmp [st+0A30Ch],0; jne skip`
    (`0x447D06..0x447FC6`). REACHED.

### The skill test, the success roll for every task (`0x43D440`)

17. **Every work attempt is a dice roll against skill: (skill + 31)% success.** A failure makes the villager shake their
    head and cancels the rest of the task, so no food, points or progress are produced.
    Evidence: per skill `rand(100); lea ecx,[skill+1Eh]; cmp eax,ecx; jle success` at `0x43D47B` (Farming), `0x43D5D8`
    (Parenting), `0x43D8A4` (Research), `0x43D7F0` (Building), `0x43D722` (Healing). Failure calls `0x439470` (clears the
    30-entry queue) and `0x43A040` ("Shaking head"). REACHED: runner opcode 6 `0x448846`, catch-up `0x446D9F`, embrace
    `0x43DBF6`. During the tutorial, flags +0x13E, +0x140 and +0x148 turn some Farming, Research and Parenting failures
    into successes.
18. **Skill only grows on a successful attempt, and growth slows sharply past 45.** The gain is (100 − 2×skill) / 10
    (Building / 9), rounded down: about +10 at skill 0, +6 at 20, +2 at 40 and +1 at 45. From 46 up, a success gives
    +1 only with probability 26% × (100 − skill)%. The cap is 100.
    Evidence: `0x43D53A..0x43D57E` (`imul 66666667h; sar 2` = /10); Building `0x43D80B mov eax,38E38E39h; sar 1` (= /9);
    slow path `rand(100) <= 25` and `rand(100) >= skill`; cap `cmp ...,64h` at `0x43D5A0` and similar.

---

## 1. Jobs: food (foraging, crops, fishing)

Route: the chooser returns 1, then dispatcher case 1 at `0x4472E5` (jump table `0x447990`). REACHED [LIVE-AI]/[CATCH-UP].

19. **Food sources unlock with Farming technology:**
    - Level 1: berry bush only.
    - Level 2: half the time crops instead of berries; crops are used whenever the bush is below 100.
    - Level 3: adds fishing, which is chosen half the time.
    Evidence: switch on `[st+0A2E4h]` at `0x4472EB`. L1 `0x44745C`; L2 `0x4473E3` (`cmp [st+0A2F4h],64h`, `rand(100)<50`);
    L3 `0x44730B` (`rand(100)<50` fish, `rand(100)<33` berries, `rand(100)<50` crops).
20. **Fishing needs the beach cleaned.** Even at Farming level 3, nobody fishes until the "Cleaning up the beach"
    project is finished.
    Evidence: `0x44730B cmp byte [st+9FB8h],1; jne skip-fishing` (+9FB8 is set by the beach callback `0x43AB3A`).
21. **At Farming level 1, a farmer facing an empty bush idles while the game counts the task as started.** The
    scheduler therefore looks no further for that farmer on this decision.
    Evidence: `0x44745C cmp [st+0A2F4h],0; jle 0x447472` -> `mov al,bl` with `bl=1` (set at `0x4472F2`).
22. **Foraging yields the bush's stock ÷ 130 (at least 2) and drains the bush by the same amount.** The bush starts at
    1,400 (1,900 on Easy) and regrows only 30 every 2 game years, so it runs down.
    Evidence: callback 14 `0x43AD62` (`imul 7E07E07Fh; sar 6` = /130; `cmp edi,2; jge`); `sub [st+0A2F4h],edi`;
    regrowth `0x42EC0D add [st+0A2F4h],1Eh` once per world step of `speed × 2400` seconds (= 40 age units);
    start values `0x41C462`/`0x41C491`.
23. **Crops give 7 food each and draw from a field that refills only when Farming is level 2 or higher.** The field
    gains 800 per 2 game years and is capped at 800. With the field empty, a farmer waters crops for skill only.
    Evidence: callback 15 `0x43AEC5` (`push 7; call 0x41D140`; `add [st+0A2F8h],-7`); refill `0x42EC16 cmp [st+0A2E4h],2;
    jl; add [st+0A2F8h],320h`; cap `0x42F2C5`; "Watering crops" `0x445020` queues only a Farming skill test (`0x44528C`)
    and no food callback.
24. **Fishing gives 9 food.** A master fisher (Farming 90 or more) has a 21% chance per trip of a 55-food catch, and
    that big catch skips the skill test, so it cannot fail.
    Evidence: `0x43F4A7 cmp [rec+3C4h],5Ah; jl normal; rand(100); cmp eax,14h; jg normal`. Big branch queues callback 17
    (`0x43F652`; `0x43AF86 push 37h`) with no opcode 6. Normal branches queue opcode 6 skill 1 (`0x43F716`/`0x43F864`)
    and then callback 16 (`0x43AF34 push 9`).
25. **Dislikes block food jobs:**
    - Dislikes fish: never fishes (no roll).
    - Dislikes berries or bushes: refuses foraging 75% of the time.
    - Dislikes turnips: refuses crops 75% of the time.
    Evidence: `0x43F456 push 21h` (fish) -> abort with no roll; `0x441E16 push 0Ch`/`0x441E24 push 19h` -> `rand(100);
    cmp eax,4Bh; jge go`; `0x4439F9 push 5` (turnips) -> same 75%.
26. **Below 200 food, rationing starts.** Each villager has a 50% chance per age unit to skip a meal and lose 1 health
    instead of eating. At 0 food, a villager loses 1 health per unit 76% of the time (always on Hard).
    Evidence: [TICK] `0x42EC94 cmp food,0C8h; jg eat; rand(100); cmp eax,32h; jl eat; dec health`; `0x42ED0C..0x42ED46`.
27. **Everyone eats 2 food every age unit (6 real minutes).** Above 2,000 food (or always on Hard; never on Easy) there
    is also a 76% chance of 2 more food wasted.
    Evidence: `0x42ECCC add food,-2`; `0x42ECD5 cmp food,7D0h` / `cmp [st+0A30Ch],2` -> `rand(100) <= 75` -> `add food,-2`. REACHED [TICK].

## 2. Building (huts, projects, repairs)

Route: the chooser returns 4, then dispatcher case 4 at `0x4474AA`. REACHED [LIVE-AI]/[CATCH-UP]. The live level gate
at `0x44765E` was observed in the owner's game (builders-fix-huts doc).

28. **Huts come first 79% of the time.** On the other 21% of decisions the builder skips straight to projects, unless
    the player assigned them to a hut site.
    Evidence: `0x4474AC rand(100); cmp eax,14h; jg hut-path`; hut-path forced for work spot 11/12/13 (`0x4474D3..0x4474E0`).
    Builders assigned to spots 1, 2, 7, 8 or 14 skip huts (`0x4474F5..0x447522`).
29. **Hut 2 can only be started autonomously at 23 or more people, and hut 3 at 46 or more.** The count includes
    unborn babies. Births stop at 25 without hut 2 and at 50 without hut 3 (gate 41), so builders get a two-person
    window (23–24 and 46–49) to start each hut on their own. The first hut has no population requirement.
    Evidence: `0x44754A call 0x41CF90; cmp eax,16h; jle skip-hut10`; `0x44757C cmp eax,2Dh; jle skip-hut11`; hut 9 at
    `0x44752E` is unconditional. Population counter `0x41CF90`: living active villagers plus 1/2/3 per pregnancy by litter.
30. **Hut sizes:** the small hut needs 250 successful build trips, the second hut 400 and the third hut 600. Each trip
    has a 2% chance of injuring the builder for 0 to 14 health.
    Evidence: callbacks 9/10/11 `0x43A757`/`0x43A87E`/`0x43A9A5`: `inc progress`, `cmp ...,0FAh/190h/258h`;
    `rand(100); cmp eax,2; jge` -> `sub health, rand(15)`.
31. **Autonomous builders never start a new project; they only continue one at least one step along.** Projects are
    started by the player dropping a villager on them. Huts are exempt.
    Evidence: `cmp [st+9FB4h],0; jle` (beach, `0x4475B6`), `+9FACh` (blockage, `0x447606`), `+9FBCh` (field, `0x447643`),
    `+9FDCh` (ruins, `0x447693`), `+9FD4h` (chisel, `0x4476D0`), `+9FC4h` (digging, `0x447701`).
32. **Construction level 2 is needed before builders clear the blockage or water the garden field.**
    Evidence: `0x4475D7 cmp [st+0A2CCh],2; jl 0x44765E`.
33. **Construction level 3 is needed for the ruins, chiseling, digging and any hut repair.** Below level 3, builders give
    up as soon as the projects open to them run out, and the game reports them as busy (a false "started").
    Evidence: `0x44765E cmp [st+0A2CCh],3; jl 0x4474A1` (`mov al,bl`, `bl=1`). The doc
    `docs/builders-fix-huts.md` records this gate live in the owner's game.
34. **Each project is tried with 79% probability per decision,** or always if the builder is assigned to it. The beach
    is the exception: it is tried whenever it is started and unfinished.
    Evidence: `rand(100); cmp eax,14h; jg try` at `0x4475E0, 0x447621, 0x447671, 0x4476AE, 0x4476EC`; beach `0x4475A8`
    (no roll).
35. **Project sizes:** the beach needs 75 trips (+2 each, done at 150), the blockage 350, the watered field 200, digging
    800, the ruins 1,000 and chiseling 1,350. Builders with skill 90 or more add double progress on the ruins and
    chiseling.
    Evidence: callbacks 3 `0x43AAAC add 2; 0x43AB11 96h`, 2 `0x43B136 15Eh`, 4 `0x43B1FE 0C8h`, 5 `0x43ACC5 320h`,
    8 `0x43B3C3 3E8h`, 7 `0x43A5F9 546h`; double progress `0x43A5D8 cmp [rec+3C0h],5Ah; jl; inc` (ruins `0x43B3A9`).
    The 2% injury roll appears in each.
36. **Watering the garden field never fails.** Unlike every other building task, it has no skill test.
    Evidence: `0x43FC20` queues no opcode 6 (only callback 4 at `0x43FD6B`). The other building routines queue opcode 6
    skill 4 (`0x44236B, 0x44483C, 0x43FE82, 0x440A2A, 0x442B5C, 0x444442`).
37. **Repairing huts only trains skill.** Builders with Construction 3 examine a random hut when nothing else is open,
    except that 21% of the time they do nothing and still report "busy". Only an already-built hut is examined.
    A repair adds no progress; it is only a Building skill test. A builder
    examining a hut goes on to repair it **70%** of the time. Expert builders (Building 50 or more) also repair huts
    during leisure (1 in 6 of those leisure picks).
    Evidence: `0x447724 rand(100); cmp eax,14h; jle false-started`; `rand(3)` hut, only if built
    (`0x447752 cmp byte [st+9FF8h],1; jne`). Examine `0x4468CE rand(100); cmp eax,46h; jge inspect-only; call 0x4423E0`.
    "Fixing hut" `0x4423E0` ends with opcode 6 skill 4 (`0x4427FB`) and no callback. Leisure `0x44606F
    cmp [rec+3C0h],32h; jl` -> `0x440AD0`. **Contradicts `docs/builders-fix-huts.md`**, which says 30%: the code fixes
    when `rand(100) < 70`.
38. **Dislikes block projects:** dislikes drift wood means refusing the beach 85% of the time; dislikes rocks means
    refusing the blockage 75% of the time.
    Evidence: `0x444696 push 1Eh` -> `cmp eax,55h; jge go`; `0x43FDA6 push 0Fh` -> `cmp eax,4Bh; jge go`.
39. **A builder assigned to a hut site ignores the population requirement and the "already started" rule.** They keep
    building the next unbuilt hut through the work-spot route.
    Evidence: `0x447F18..0x447FC6`: work-spot cases call `0x442090` with only `cmp byte [st+9FE8h/9FF0h/9FF8h]`, with no
    `0x41CF90` call and no progress check. REACHED via gate 16.

## 3. Breeding (embracing, pregnancy, births)

Routes: autonomous choice (chooser returns 2) leads to dispatcher case 2 at `0x4477AF`, which walks to the partner and
queues opcode 9. The player's drop (`0x4252B9`) also queues opcode 9 (`0x445510`). Opcode 9 resolves in **the same
routine** `0x43DAD0` for both (queue step `0x43DF4F`). Catch-up uses `0x446C70` opcode 9 (`0x446E70`, `0x447055`).
All conceptions go through `0x43BBC0`. All REACHED.

40. **Both partners must be 18 or older, of opposite sex, alive, healthy (not sick) and not already pregnant. There is
    no upper age limit for either sex.**
    Evidence: `0x43DB35 mov eax,168h` with `cmp age` for both (`0x43DB3A/0x43DB46`); `+350` differ (`0x43DB58`);
    `+344 > 0`; `+358 == 0`; `+354 == 0` (`0x43DB64..0x43DBB2`). Same checks in case 2 (`0x4477C0..0x447827`) and
    catch-up (`0x446E96..0x446F1A`, `0x447084..0x44710C`). No upper-age compare exists in any of them.
41. **Population cap, checked at conception and counting babies on the way:** under 15 people, anyone can conceive;
    15 or more needs hut 1; 25 or more needs hut 2; 50 or more needs hut 3; at 90 conception stops.
    Evidence: `0x43A1A0`: `cmp eax,5Ah; jl` / `cmp 32h` -> `[st+9FF8h]` / `cmp 19h` -> `[st+9FF0h]` / `cmp 0Fh` ->
    `[st+9FE8h]`; called first in `0x43BBC0` (`0x43BBC3`). Birth delivery (`0x42EF15..0x42F0CE`) does not re-check.
42. **Below 400 food, 74% of embraces fail outright.** This applies to the player's drag-and-drop too, except during the
    tutorial's first embrace.
    Evidence: `0x43DBBE cmp [st+0A2ECh],190h; jge ok; rand(100); cmp eax,19h; jle ok; [st+148h]==0 -> fail`. Same in
    catch-up `0x446F26`/`0x447118`.
43. **The initiating villager must pass a Parenting skill test, then a conception roll that Fertility technology
    drives.** Success requires `rand(300) <= Parenting − 50 + 50 × Fertility`, which gives:
    - Fertility 1: (Parenting+1)/300, at most about 34%.
    - Fertility 2: (Parenting+51)/300.
    - Fertility 3: (Parenting+101)/300, at most 67%.
    The partner's skill does not matter. The tutorial flag +0x148 skips the roll.
    Evidence: `0x43DBF6 call 0x43D440(i,2)`; `0x43DC61 push 12Ch; rand; imul [st+0A2DCh],32h; 32h-...; add; cmp eax,[ebp+3BCh];
    jg fail` (`ebp` = initiator). Catch-up repeats it at `0x446F5B` and `0x44715C`.
44. **Autonomous embracing picks the lowest-numbered eligible partner in the village,** not a nearby or random one.
    Evidence: `0x4477B5..0x447835` scans slots 0..255 and takes the first match. The only identity exclusion compares
    +0x36C and +0x368 (`0x4477DC`/`0x4477E7`). +0x36C is inherited from the father and +0x368 is `rand(100)+1`
    (`0x43C657..0x43C67B`), so this is in effect a self-exclusion.
45. **Pregnancy lasts 40 age units (2 years; 4 real hours at Normal).** The baby then appears as a 2-year-old with all
    skills 0.
    Evidence: [TICK] `0x42EF27 add eax,28h; cmp eax,[+34Ch]` -> `0x43C350(...,28h)`; child skills zeroed at `0x43C3D8..0x43C3F0`.
46. **Twins and triplets need late-game unlocks.** Twins (7%) need Fertility level 3 or the strange-fish puzzle (+0xA090).
    Triplets (25% of twin pregnancies) need both.
    Evidence: `0x43BC28 cmp [st+0A2DCh],3; je roll; cmp byte [st+0A090h],0; je single`; `rand(100); cmp eax,7; jge single`;
    triplets `0x43BC6A..0x43BC87` (`cmp ...,3; jne`, `[A090]`, `cmp eax,19h; jge`). +A090 is set by callback 30
    (`0x43A2EC`), queued by "Hunting a strange fish!" `0x444C80`.
47. **In a tiny village of 6 or fewer, the newborn's sex is not 50/50.** If women outnumber men and there are at most 2
    men, the baby is a girl. If men are at least as many as women and there are at most 2 women, the baby is a boy.
    Otherwise it is 50/50.
    Evidence: `0x42EF9F call 0x41CF90; cmp eax,6; jg` -> `0x42E660` (counts gender 1 in esi and 2 in edx; returns 2 if
    edx>esi and esi≤2, 1 if edx≤esi and edx≤2, else 0); `0x43C5E1` uses a nonzero hint as +0x350. Static reading; a
    counter-intuitive "join the majority" rule. Not checked in play.
48. **When the player is away (catch-up), an adult chooses Parenting and then embraces only 6% of the time.** That
    adult also needs 20 or more health. One catch-up embrace scans the whole village twice and **does not stop after a
    success**, so a single high-skill man can make several women pregnant in one replayed moment.
    Evidence: `0x42E7C5 cmp [+344h],14h; jl skip`; `0x42E7E0 cmp eax,2; rand(100); cmp eax,5; jg skip` -> opcode 9;
    `0x446E70` loop ends at `0x44704F` and `0x447055` loop ends at `0x447256`, both running past a call to `0x43BBC0`.
49. **Dead trial limit:** pairing (and catch-up healing) contains a "population must be under 7" check. It applies only
    when profile flag +0xABEC is 0, but the only code that writes the flag sets it to 1.
    Evidence: `0x43DC09 cmp byte [st+0ABECh],1; je ok; call 0x41CF90; cmp eax,7; jge fail`; writer `0x41C892 mov byte
    [st+0ABECh],1`. A 0 could only arrive from a settings file block copied at `0x41BE59`. UNVERIFIED-REACHABILITY; very
    likely developer-dead.

## 4. Healing (curing the sick, medicine)

Routes: the chooser returns 5, then dispatcher case 5 at `0x447894`. Player drop of any villager onto a sick one:
`0x425285` -> `0x445580`. Both resolve in `0x43CEB0`. Catch-up: `0x446CC1` and `0x446DD0`. REACHED.

50. **Getting sick (rolled once per age unit, half the units on Easy):**
    - Children under 14 and the Golden Child never get sick.
    - Adults: 1 in 600 at Medicine 1, 1 in 1,200 at Medicine 2, 3 in 10,000 at Medicine 3.
    - Older villagers (over 50/58/66 years at Medicine 1/2/3) add 1.5% per unit.
    Evidence: `0x42E590`: `cmp [+36Ch],0C7h`; `cmp [+348h],118h; jl none`; `rand(960h)<=3`, `rand(12C0h)<=3`, `rand(2710h)<=2`;
    elderly `0x42E622 Med*160+840`, `rand(3E8h) <= 0Eh`. Call `0x42EE6C`, 50% skip on Easy at `0x42EE55..0x42EE6A`.
51. **Sickness slowly kills.** A sick villager loses 1 health in 71% of units, and in only about 22% once at 20 health
    or lower. Sick villagers never regain health.
    Evidence: `0x42ED75 rand(100); cmp eax,46h; jg; cmp health,14h; jg dec; rand(100); cmp eax,1Eh; jg skip`;
    regen requires `+354 == 0` (`0x42EDD8`).
52. **Healers only heal when someone is sick, and they treat the lowest-numbered sick villager first.** With nobody
    sick, a healer studies the medical cactus only if the player assigned them there; otherwise the Healing job does
    nothing.
    Evidence: `0x447894..0x4478E5` scans for `+344>0 && +354!=0 && identity differs`, first match wins. No match:
    `cmp [rec+3B8h],9; jne` -> `0x443270`.
53. **A cure succeeds with probability (Healing + 31)%.** This holds whether the healer chose the job or the player
    dropped them on the patient. Any villager can be dropped, including a child with Healing 0, who has a 31% chance.
    Evidence: heal queue `0x445580` = opcode 6 skill 5 (`0x4455C4`) then opcode 17; `0x43CEB0` cures unconditionally
    (`0x43CF4B mov [+354h],0`). No age check in `0x4251FF..0x425285`, `0x445580` or `0x43CEB0`.
54. **When the village screen is not showing, a healer skips the walk and the skill test.** The cure then lands on
    whichever idle villager is at the healer's own position, which is probably nobody.
    Evidence: `0x447910 cmp [st+0ACB4h],1` (screen id; 1 = village) else `0x44792E` queues opcode 17 alone. `0x439350`
    picks the villager under a point. The effect is UNVERIFIED.
55. **Once all four medicinal plants are studied, every cure also restores 10–29 health.** The plants are the cactus
    (+A068), the lily (+A070), the rose (+A060) and the strange plant (+A078).
    Evidence: `0x43CF5B cmp byte [st+0A080h],0; je; rand(14h)+0Ah` added to health, cap 100. +A080 set at `0x43A3BD`
    when +A068, +A070, +A060 and +A078 are all set. The first cactus study always succeeds (callback 25 with no test,
    `0x44341E`); later studies are Healing skill tests only (`0x4433FE`).
56. **Healing is much stronger during catch-up.** One healing action cures every sick adult whose (Healing + 31)% roll
    passes, not just one patient. A separate catch-up branch cures one adult at a rate of `rand(1500) < Healing`.
    Evidence: opcode 17 `0x446DD0..0x446E65` loops all 256 slots with a skill test per villager; opcode 6 skill 5
    `0x446CCF push 5DCh; cmp eax,[+3C8h]; jge`. Both require patient age 280 or more (`0x446D39`, `0x446E28`).

## 5. Research (tech points)

Route: the chooser returns 3, then dispatcher case 3 at `0x44747B` -> `0x442C10` "Researching". REACHED [LIVE-AI]/[CATCH-UP].

57. **Research stops once all six technologies reach level 3 (sum 18).** A researcher assigned by the player to the
    research spot ignores this and keeps going.
    Evidence: `0x447481 call 0x41CEA0; cmp eax,12h; jge nothing`; work-spot route `0x447DA7..0x447DC7` calls `0x442C10`
    without the sum check (gate 16).
58. **Each successful research session gives Research ÷ 7 tech points at Science 1, ÷ 5 at Science 2 and ÷ 3 at
    Science 3, rounded down.** A researcher under 7 skill therefore earns **nothing** at Science 1, even on a success.
    Evidence: callback 18 `0x43B2AB`: switch `[st+0A2C4h]`; `imul 92492493h; sar 2` (÷7), `66666667h; sar 1` (÷5),
    `55555556h` (÷3) -> `0x41D120` (adds to +A2FC).
59. **A research session must first pass the Research skill test ((Research + 31)%), and carries a 2% chance of losing
    0–9 health.**
    Evidence: `0x442D28` opcode 6 skill 3 queued before callback 18 (`0x442D3C`); `0x43B2AB rand(100); cmp eax,2; jge;
    sub health, rand(0Ah)`.

## Lifespan gates that affect all five activities (World tick, REACHED [TICK])

60. **Health regenerates only when food is above 0 and the villager is not sick.** It is rolled every unit on Easy and
    half the units otherwise. Past 50/58/66 years (Medicine 1/2/3) regeneration drops to 20% of rolls.
    Evidence: `0x42EDCB..0x42EE4D`: threshold `Med*160+840`; `rand(100); cmp eax,14h; jge skip`.
61. **Old age:** on each birthday past 55/63/71 years (Medicine 1/2/3), the chance of dying that year is 10% for every
    year over that age. In stock there is no Magic-Fruit adjustment in this routine.
    Evidence: `0x42EE7E..0x42EF05` (`age % 20 == 0`; threshold `Med*160 + 940`; `rand(100) < (age/20 − thr/20)*10` ->
    health = 0). Medicine is the only state field read there.

---

## Surprises (the gates a player would least expect)

1. **Hut 2 and hut 3 have a two-person build window** (gates 29 and 41). Builders start hut 2 only at 23–24 people and
   hut 3 only at 46–49, counting unborn babies, while births stop at 25 and 50 without those huts. A death or two at the
   wrong moment stalls the village until the player assigns a builder to the hut site.
2. **Two thirds of "what now?" moments are wasted outright** (gate 1), and a well-fed village (400 food or more) gets
   one job roll instead of two (gate 6).
3. **Builders never start a new project themselves** (gate 31). Below Construction 3 they report "busy" while idling
   (gate 33), and farmers do the same at an empty bush at Farming 1 (gate 21).
4. **Below 400 food, 74% of embraces fail,** including the player's own drag-and-drop (gate 42).
5. **A child dropped on a sick villager cures them 31% of the time** (gate 53). The healer's age does not matter.
6. **The Science payout is skill ÷ 7, so researchers under 7 skill earn 0 points per session** at Science 1 (gate 58).
7. **Master fishers' big catches (55 food) cannot fail** (gate 24). Watering the garden field also never fails (gate 36).
8. **A villager who dislikes fish never fishes; one who dislikes work refuses 70% of all jobs** (gates 25 and 11).
9. **Catch-up is stronger than live play for healing** (every sick adult can be cured at once, gate 56). It is also
   stronger for multiple pregnancies (one man, many conceptions per moment, gate 48), though embracing itself is rarer
   offline (6%).
10. **Tiny villages copy the majority sex** (gate 47). In a village of 6 or fewer, the newborn tends to be the sex that
    already outnumbers the other.
11. **Below 200 food, villagers start skipping meals and losing health** (gate 26), well before the store reaches zero.
12. **Pregnancy benches a villager for 4 real hours at Normal speed** (gate 4), and twins need Fertility 3 or the
    strange-fish puzzle (gate 46).

### Incidental findings (not fixed; outside this task)

- `docs/builders-fix-huts.md` says examining a hut leads to a repair 30% of the time; the stock code repairs when
  `rand(100) < 70`, which is 70% (`0x4468D8`).
- The VV1 preference list the exporters print (`native/parentage_export/parentage_export.c` `PREFERENCES_47`:
  "...rocks,heights,...,rough wood,...,learning,...,parrots,work,...") differs from the exe's own English list at
  `0x47B3xx` ("...rocks, rough wood, ..., drift wood, ..., dancing, monkeys, birds, work, lifting, surprises, jokes,
  sleeping") from index 16 onward in places. For example, index 42 is "parrots" in the exporter but "work" in the exe,
  and the exe uses 42 as the "dislikes work" job gate. Worth checking against the game's Details panel; possible
  logging defect.


============================================================================
THE LOST CHILDREN (VV2) -- FULL REPORT
============================================================================

# Virtual Villagers 2: The Lost Children — hidden gates in jobs, building, breeding, healing and research

Executable: `research/stock-executables/Virtual Villagers - The Lost Children.exe`, 724,992 bytes,
SHA-256 `46C1503C…E677ED677` (checked before analysis). Every address below is a VA in that exact build.

**How much to trust this.** This is a static reading of the disassembly, done with capstone. I did not
launch the game, as instructed, so none of it is checked against a live game. Under the project's
evidence order, these readings rank below live memory and the owner's saves.

## Conventions

* **Random rolls.** `RNG(n)` at `0x4031A0` is `rand() % n`, which gives 0…n‑1. So "`RNG(100) < 15`"
  means a 15% chance.
* **Age units.** There are 20 internal units per displayed year. Each age unit takes `speed × 60`
  seconds of real time, from the aging code at `0x43B8E3–0x43B8FD`: elapsed seconds ÷ 60 ÷ `[state+0x2EB08]`.
  * The speed setting is 6 by default (written at `0x425664`). The Options screen writes 10, 6 or 3
    at `0x435924/0x43596A/0x4359AD`, and 999 means paused.
  * At the default speed, one unit is 6 minutes and one displayed year is 2 hours.
  * I worked these timings out from the code and did not time them live.
  * Key ages: 280 = 14 yrs, 360 = 18 yrs, 1000 = 50 yrs.
* **Skill offsets.** The record stride is `0xE48C`. The code fixes the skill offsets as:
  * `+0x7E4` Parenting, `+0x7E8` Building, `+0x7EC` Farming, `+0x7F0` Healing, `+0x7F4` Research,
    and `+0x7F8` is the skill preference.
  * The skill-roll dispatcher `0x44E170` maps type 1 → `+0x7EC`, 2 → `+0x7E4`, 3 → `+0x7F0`, 4 → `+0x7F4`
    and 5 → `+0x7E8` (jump table at `0x44E88C`). The work dispatcher `0x45FBF0` uses the same job
    numbers (table at `0x46053C`): 1 Farming, 2 Parenting, 3 Healing, 4 Research, 5 Building.
  * This agrees with the live Cheat Engine table in `villager-record-reference.md`, which has
    `+0x7E4` = Parenting.
  * It contradicts `docs/vv2-easier-healing-research.md`, which labels `+0x7E4` as Farming,
    `+0x7EC` as Research and `+0x7F4` as Parenting. That doc's skill labels are wrong; only its
    Healing offset is right.
* **Village-state fields** (each is `[villager array + 0xE574D4] + offset`):
  * Food is `+0x2EAA4`. Tech points are `+0x2EADC`.
  * Tech levels (1–3), mapped through the tech tooltip switch at `0x4422F0`:
    * Culture `+0x2EA74`, Science `+0x2EA7C`, Engineering `+0x2EA84`.
    * Medicine `+0x2EA8C`, Exploration `+0x2EA94`, Farming `+0x2EA9C`.
  * Difficulty is `+0x2EAEC`, set to 0, 1 or 2 at `0x4359D8/0x435A06/0x435A38`. I read 0/1/2 as
    Easy/Medium/Hard because the Options screen lists the strings 0x375–0x377 in that order; I have
    not verified that live.
  * Fish stock `+0x2EAD0`, crops `+0x2EAD8`, coconuts `+0x2EACC`.
  * The fire burns until the time in `+0x2EAC4`.
  * Population is counted by `0x425860`: living villagers that are not totems, plus 1–3 for each
    nursing litter.
* **Reachability labels.**
  * **REACHED** means the caller chain was traced statically from one of these entry points:
    * The village scene's per-frame method `0x42E990`, which is slot 8 of vtable `0x476BB8`.
      * It calls the villager updater `0x464CD0` every frame unless the game is paused (`0x42F9FF`).
      * It calls the world tick `0x43B690` about every 2 seconds (`0x42EBBC`).
    * The player drop-on-object handler `0x42FB20`.
  * **UNVERIFIED-REACHABILITY** means the code exists but I did not trace a caller chain to it.
* **Main chain.** `0x464CD0` → empty queue (op 0) → AI decision `0x461850` → job chooser `0x449C60` →
  dispatcher `0x45FBF0` → task builder → queue ops.
  * Op 6 runs the skill roll `0x44E170`.
  * Op 17 runs a completion callback through `0x461B10`.
  * Op 12 runs "pair/teach at my spot" (`0x44F610`), through the op starter `0x44FBB0`.
  * Op 20 runs "cure at my spot" (`0x44D9E0`).
* **Catch-up while you were away.** The world tick runs `0x43B4D0` four times per missed age unit
  for each villager who is more than 2 units behind (`0x43BF9E–0x43BFF5`). That routine simulates
  queues in `0x464680` and sets flag `[state+0x3046C]` = 1 while it runs.

---

## Gates every job shares (who gets picked for any work)

1. **Idle villagers often decide to do nothing.** About once a second an idle villager rolls, and 66%
   of the time the decision step just leaves them doing "Nothing".
   *Evidence:* `0x46188C–0x461899` `RNG(100) ≤ 65 → return`, with a 1-second wait at `0x464EC1`. REACHED.
2. **Children under 14 never work.** They are routed to child play instead.
   *Evidence:* `0x4618BA` `cmp age, 0x118 (280); jl → 0x45EE00`. REACHED. Catch-up uses the same 280
   floor at `0x43B4FC`.
3. **Sick villagers and nursing mothers do not work.**
   *Evidence:* `0x46189F` sick (`+0x53C`) → sick behaviours. `0x4618D5` nursing (`+0x540`) →
   mother activities only: 20% chance per tick, otherwise nothing (`0x461913–0x461920`). REACHED.
4. **During catch-up, a villager below 20 health does no work at all.**
   *Evidence:* `0x43B50D` `cmp health, 0x14; jl skip`. REACHED (catch-up only; live play has no
   health floor besides health > 0).
5. **"Likes work" check.** 15% of the time the chooser gives up unless the villager likes "work"
   (token 43). If the villager dislikes work, the chooser gives up 70% of the time.
   *Evidence:* `0x449C66–0x449CAC`. The likes test `0x445510` reads `+0x5F0`; the dislikes test
   `0x4454E0` reads `+0x6E8`. REACHED.
6. **Skill-based job pick.** Each of the five skills is considered only with an 84% chance
   (`RNG(100) > 15`), and the highest one wins.
   * Parenting counts 15 points lower than it really is (`lea esi,[eax-0xF]` at `0x449D02`).
   * Healing is skipped half the time for villagers who dislike medicine (token 4) (`0x449D55–0x449D70`).
   *Evidence:* `0x449CB2–0x449DA8`. REACHED.
7. **Skill preference.** A set preference overrides the pick 86% of the time (`RNG(100) ≤ 85`).
   *Evidence:* `0x449DAA–0x449E0F`, table `0x449E60`. REACHED.
8. **Minimum skill to work.** A villager whose winning skill score is 5 or less never picks a job on
   their own. Above that, they still only go with chance (score + 40)%.
   * So a Farming 20 villager starts farming 60% of the time the job is picked; a 60+ skill villager
     always does.
   *Evidence:* `0x449E0F` `cmp esi,5; jle → 0`, then `RNG(100) < esi+0x28` at `0x449E14–0x449E23`. REACHED.
9. **When nothing is picked.** A villager whose best skill is under 50 and whose five skills total
   under 70 falls back to their player-assigned job, or else idles.
   *Evidence:* `0x461A3D–0x461A5E` (`0x44B4D0` best skill < 0x32, `0x44B550` total < 0x46 →
   `0x460590`). REACHED.
10. **A player-assigned job only "sticks" while the villager's skill in it is at least 6.**
    * Below 6, the assignment is forgotten.
    * Villagers who don't like work skip their assignment 20% of the time. That rises to 52% when food
      is 4000 or more, or when they dislike work.
    *Evidence:* `0x461580–0x461620` (`cmp edx,6; jge`, `RNG(100)<0x14`, `RNG(100)<0x28`,
    `food ≥ 0xFA0`). REACHED from `0x4619D6`.
11. **Skill 0 on Medium/Hard.** A villager with 0 skill drops a player-assigned job, but only on
    Medium or Hard. On Easy they keep at it.
    *Evidence:* `0x460590` cases, e.g. `0x4605C8` `cmp Farming,1; jge`, else `cmp [state+0x2EAEC],0; jne skip`. REACHED.

### The universal skill roll (applies to every task with an op‑6 step)

12. **Every working step has a skill check, and failing it ends the task.**
    * Success means `RNG(100) ≤ skill + bonus`. The bonus is +33 normally, +66 if the villager likes
      "learning" and +16 if they dislike it.
    * `RNG(100)` is 0-99, so the chance is (skill + 34)%: a neutral villager at skill 0 succeeds
      34% of the time, and at 66 skill or more (33 if they like learning) nobody ever fails.
    * On failure the task is cancelled with no output. A failed villager with skill 0 is bumped to 4.
    *Evidence:* `0x44E170–0x44E1AC` (`ebp` = 0x42/0x21/0x10), per-skill compare e.g.
    `0x44E1D0–0x44E1E2`. On fail: `0x4492A0` and `0x44B1B0` clear the queue; `mov [skill],4` at
    `0x44E21A`. REACHED (op 6 at `0x464F15`).
13. **Learning slows as skill rises.**
    * A success adds `trunc((100 − 2×skill)/10)` points. Building divides by 7 instead of 10.
    * The gain is doubled if the villager likes learning and halved if they dislike it.
    * Once the formula reaches 0 (Building from 47, the other skills from 46), a success adds 1 point
      only with a 26% × (100 − skill)% chance.
    * Skill caps at 100.
    *Evidence:* `0x44E2B8–0x44E343` (`0x66666667`), Building `0x44E62E` (`0x92492493`). The fallback
    is `RNG(100) ≤ 25 && RNG(100) ≥ skill`. REACHED.
14. **Tutorial exception.** While a "teach a villager" tutorial step is active, a failed Farming,
    Parenting or Research roll is turned into a success.
    *Evidence:* `0x44E1E4–0x44E1FF` (state `+0x1BF`/`+0x1DB`), `0x44E381` (`+0x1CD`/`+0x1DE`),
    `0x44E6F0` (`+0x1C1`/`+0x1DD`). REACHED (tutorial only).

---

## 1. Jobs / gathering food (job 1, Farming)

1. **The Farming *technology level* decides which food sources farmers use** (`0x45FC15`, switch on
   `[state+0x2EA9C]`):
   * **Level 1:** fishing, plus crops once the dam exists.
     * While fish remain: 49% of the time they fish; otherwise they fish if there is no dam and
       farm if there is one.
     * With no fish left, they farm if the dam exists and do nothing if it doesn't.
     *Evidence:* `0x45FDF4–0x45FE1F` (`RNG(100) > 50`). REACHED.
   * **Level 2:** coconuts become available, but only while the trees hold more than 10. (Level 3
     uses 10 or more.)
     *Evidence:* `0x45FD48` `cmp coconuts, 0xA; jle`; level 3 at `0x45FC88` `jl`. REACHED.
   * **Level 3:** fishing, coconuts and crops are weighted by whether crops are ripe.
     * With no crops ripe: fish 80%, otherwise coconuts 75%.
     * With crops ripe: fish 40%, coconuts 25%, otherwise harvest.
     *Evidence:* `0x45FC36–0x45FCCE` (`RNG(100)<0x50/0x28`, `<0x4B/0x19`). REACHED.
2. **Polluted or empty water.** Once the fish stock (starting at 1100) is used up, farmers who try to
   fish just stand "Disgusted by the algae" and get no food. This lasts until the algae-eating-fish
   project has been done 10 times.
   * At Farming level 2, a farmer facing polluted water still tries this 81% of the time.
   * At Farming level 1, fishing stops entirely once the stock reaches 0, even after the fix.
   *Evidence:* `0x425B00` (fish ≤ 0 && `+0x2E7E8` == 0). Fixed by callback 18 at `0x4626F0` (10 catches).
   Level-2 roll `0x45FD24` `RNG(100) ≤ 80`. Fish stock initialised to 0x44C at `0x425257`. REACHED.
3. **Crops need the dam.** Without the dam (`+0x2E798`), farmers never plant, water or harvest.
   *Evidence:* `0x45FCD4`/`0x45FDC6`/`0x45FE25` `cmp byte [+0x2E798],1; jne → nothing`. REACHED.
4. **Crop regrowth.** Crops regrow by 800 every `speed × 2400` s (4 h at normal speed). That happens
   only if the dam is built and the field still has water (`+0x2EAD4` > 0) or permanent irrigation
   (`+0x2E770`). Otherwise the crop count is wiped to 0. Each regrowth tick also adds 30 coconuts,
   up to 1500.
   *Evidence:* `0x43B9C1–0x43BA17` (`imul 0x960`, `+0x320`, coconut `+0x1E`, cap `0x5DC`). Failure
   test `0x425AC0`. REACHED.
5. **Dislikes:**
   * Villagers who dislike fish never fish (`0x4507A6–0x4507D9`).
   * Villagers who dislike heights or coconuts refuse coconut picking 75% of the time (`0x456F76–0x456F9F`).
   * Villagers who dislike turnips or vegetables refuse field work 75% of the time (`0x4593D8–0x45940B`).
   REACHED.
6. **Food per trip.** A food trip only pays out if the Farming skill roll passes (type 1, every
   gathering task). At normal speed one successful trip yields:
   * Coconuts +4, crops +7, fish +8.
   * 2× speed raises these to 8/10/11; ½ speed lowers them to 2/4/5.
   * During catch-up they are always 4/7/8.
   *Evidence:* callbacks 27/28/29 at `0x463160`, `0x46321E` and `0x4632CB`, keyed on
   `[state+0x2EB08]` == 3/10 and the catch-up flag `+0x3046C`. Op‑6 type 1 in `0x450BDE`,
   `0x457088`, `0x45D493` and `0x4595F2`. REACHED.
7. **Mushrooms.** Mushrooms give +6 food, and the special one gives +35.
   *Evidence:* callbacks 39/40, `0x4633C5`/`0x463422`. Reached via a child task whose caller I did not
   trace: UNVERIFIED-REACHABILITY for the queue builder.
8. **Eating and starvation.** Each villager eats 2 food per age unit (6 real minutes at normal speed).
   * At 150 food or less, they eat only half the time. When they skip, they lose 1 health 30% of the time.
   * On Medium, when food is above 4000, they eat 2 more 76% of the time. On Hard they eat 2 more
     76% of the time at any food level. Easy never adds the extra 2.
   * At 0 food each villager loses 1 health per age unit: always on Hard, about ¾ of the time otherwise.
   *Evidence:* `0x43BAB0–0x43BB85` (`cmp food,0x96`, `RNG(100)<0x1E`, `cmp food,0xFA0`/difficulty 2,
   `RNG(100) ≤ 0x4B`). REACHED.

## 2. Building (job 5)

1. **Order of checks.** 80% of the time, a builder first continues a player-assigned project
   (states 11–20).
   *Evidence:* `0x45FE85` `RNG(100) > 20` then the switch at `0x460550`. REACHED.
2. **The broken starting hut is rebuilt first** (80% roll). Each repair cycle needs a Building roll.
   *Evidence:* `0x460066–0x4600A7` (`+0x2E760`, `+0x2E75C` > 0). Op‑6 type 5 at `0x44AE07`. Done at
   400 progress, `0x462AFD`. REACHED.
3. **Hut 1 has no population requirement.** Any builder starts it (80% roll each decision).
   *Evidence:* `0x4600B8–0x4600D8` (`+0x2E818`). REACHED.
4. **Hut 2 needs population above 22, and hut 3 above 45.** Each also needs progress of at least 2.
   * The hut's site appears, with progress set to 1, only once population reaches 21 and 46 respectively.
   * So a builder will not take a new hut on unprompted. Someone, normally the player dragging a
     builder onto the site, must do the first cycle.
   *Evidence:* `0x4600DE` `pop > 0x16`, `cmp [+0x2E81C],2; jge`. `0x460102` `pop > 0x2D`, `[+0x2E824] ≥ 2`.
   Site reveal `0x4196E8` (`pop < 0x15` hides it) and `0x419763` (`< 0x2E`), progress = 1 at
   `0x419702`/`0x41977D`. REACHED; "player must start it" is inferred from the absence of any other
   writer.
5. **Engineering 2 unlocks thorn-clearing, the dam and the hospital.**
   * Thorn-clearing also needs the cutting tools (`+0x2E7A0`) and must already have been started.
   * The dam must already have been started (progress > 0).
   * The hospital needs Medicine 3 and progress ≥ 2. Its site appears only at Medicine 3 *and*
     Engineering 3.
   *Evidence:* `0x46012C` `cmp Engineering,2; jl → skip`. Thorns `0x460153–0x46016F`, dam
   `0x460191–0x4601A7`, hospital `0x4601C9–0x4601E6` (`cmp Medicine,3`). Site reveal at
   `0x4197DF–0x4197F3`. REACHED.
6. **Engineering 3 unlocks the ancient ruins and the vine wall,** which also need Culture 3.
   * Below Engineering 3, builders also never examine or "fix" huts.
   *Evidence:* `0x4601EC` `cmp Engineering,3; jl → nothing`. Ruins `0x460226–0x46023B` (Culture ≥ 3),
   vines `0x46026E–0x46028A`. REACHED.
7. **"Fixing" huts does nothing to the hut.** Examining a hut finds work 70% of the time, and that
   work is just a Building skill roll (practice). The other 30% the builder says "This hut is still in
   good repair." Huts never decay.
   *Evidence:* `0x45FB4D–0x45FB5C` `RNG(100) < 0x46 → 0x4575B0`. `0x4575B0` queues only op‑6 type 5
   (`0x457A45`) with no callback. Message 0x5C at `0x45FB73`. REACHED (Engineering ≥ 3 only).
8. **Builders who dislike wood walk off a building job 40% of the time** when the job reaches its
   wood check.
   * That check runs when the earlier `RNG(100) ≤ 50` roll succeeds or the builder likes wood.
   *Evidence:* `0x457282–0x4572A1` route to `0x457372`, then `0x457372–0x45738D` (token 30,
   `RNG(100) < 0x28`). I did not fully trace whether every other path also reaches this check, so
   the overall abandon rate is not settled. REACHED.
9. **Every building cycle needs a Building roll** (see the universal skill roll).
   * A cycle adds 2 progress (1 during catch-up), with +1 more on some projects for Building 88+.
   * Totals needed: hut 1 450, hut 2 700, hut 3 900, hospital 1200, dam 425, vines 1000, ruins 5000.
   * Each cycle has a 2% injury chance: hut work costs 0–14 health, the dam 0–9.
   *Evidence:* op‑6 type 5 then callback (`0x4574EF`/`0x457506`). Callbacks 24/25/26/5/8/11/12/17
   (`0x462BC6`, `0x462CFD`, `0x462E39`, `0x462F4B`, `0x464168`, `0x463FFF`, `0x462960`, `0x46389B`):
   * The `+0x3046C` catch-up flag halves the increment.
   * The `cmp Building,0x58` bonus applies to the dam, vines, ruins and thorns.
   * Thresholds are `0x1C2/0x2BC/0x384/0x4B0/0x1A9/0x3E8/0x1388`.
   * Injury is `RNG(100) < 2`.
   REACHED.

## 3. Breeding (job 2, embracing, conception, nursing, birth)

VV2 has no visible pregnancy. Conception immediately makes the mother "nursing", and that litter
already counts toward population.

1. **When villagers choose to embrace.** The chooser counts Parenting at −15, so a villager needs
   Parenting above 20 to pick it on their own.
   * If Parenting is not their preferred skill, the pick then goes through only 25% of the time.
   *Evidence:* `0x449D02` (`−0xF`), `0x449E0F` (> 5). Fallback `0x449E25–0x449E52`: `RNG(100) < 0x4B → 0`,
   else job 2. REACHED.
2. **Who a villager will look for as a partner.**
   * The partner must be 18–49 years old (under internal age 1000), whatever their gender.
   * The partner must be the opposite gender, alive, not sick and not nursing.
   * The villager themselves must be 18+ and not nursing. They have no upper age limit.
   *Evidence:* scan `0x46035D–0x4603E9`. Candidate `cmp age,0x3E8; jge skip` and `cmp age,0x168`;
   self `cmp [+0x530],0x168`. REACHED.
3. **What happens when they meet.** Autonomous embraces (`0x45D510` queues op 12) and player drops
   both end in `0x44F610`, which re-checks the following:
   * Both are 18+ and opposite genders.
   * Both have health > 0, neither is nursing, neither is sick.
   * **When food is under 300, the embrace fails 34% of the time.**
   * The initiator must pass a Parenting skill roll.
   *Evidence:* `0x44F66B–0x44F6EE`. `0x44F6F4` `cmp food,0x12C; jge`, `RNG(100) > 0x41 → fail`.
   `0x44F72C` op‑6 type 2. REACHED (op 12 via `0x44FBB0`).
4. **Conception chance.** Conception succeeds when `RNG(300) ≤ Parenting + 50×Medicine − 50`.
   * Medicine 1, Parenting 100: about 34%. Medicine 3, Parenting 100: about 67%.
   * At Medicine 1 with Parenting 30, the chance is only about 10%.
   *Evidence:* `0x44F79B–0x44F7C2` (`RNG(0x12C)`, `imul Medicine,0x32`). REACHED.
5. **No conception if the woman is 50 or older** (internal 1000), whichever of the two she is.
   There is no age limit for men.
   *Evidence:* `0x44F7C8–0x44F7F9` (`cmp gender,2` / `cmp age,0x3E8`). REACHED.
6. **Housing cap.** No conception goes through unless there is room. This applies to every route,
   including the Love Note and Gong events.
   * Population must be below 90, plus 5 for each completed collection (25 if all four are complete).
   * Population 15+ needs hut 1, 25+ needs two huts, and 50+ needs all three.
   *Evidence:* `0x44B310`. Collections via `0x426120`; `cmp edi,0x14 → 0x19`; `add edi,0x5A`;
   `cmp pop,0x32/0x19/0xF` against hut count. Called first in `0x44B980` (`0x44B983`). REACHED.
7. **Twins and triplets need Medicine 3.** At Medicine 3 a conception has a 7% chance of twins, and a
   quarter of twins become triplets (1.75% overall). Below Medicine 3, only single babies.
   *Evidence:* `0x44BA64–0x44BAB6` (`cmp Medicine,3`, `RNG(100) < 7`, `RNG(100) < 0x19`). REACHED.
8. **Mother's skill boost.** Each conception raises the mother's Parenting by max(5, (100 − P)/10).
   *Evidence:* `0x44B99E–0x44B9E0`. REACHED.
9. **Nursing length.** The baby is nursed for 40 age units (2 displayed years, about 4 real hours at
   normal speed) before becoming a 2-year-old child. During that time the mother cannot work or conceive.
   *Evidence:* weaning `0x43BE18–0x43BE23` (`+0x540 + 0x28 < processed age`). Child created by
   `0x44F5C0` with age arg 0x28. REACHED.
10. **A child inherits points in one parent's best skill.** The parent is chosen 50/50.
    * Normal play: 5–7 points.
    * If both parents share the same best skill, the Culture level sets the amount instead: 4–5 at
      Culture 1, 5–8 at Culture 2, 7–11 at Culture 3.
    * **If the chosen parent's best skill is Parenting, the child inherits nothing.**
    *Evidence:* `0x44F846–0x44F8AC` (`RNG(3)+5`; Culture switch: `RNG(2)+4`, `RNG(4)+5`, `RNG(5)+7`).
    `0x44B9EA–0x44B9FA` (category 2 → type 1, amount 0). Applied at `0x44CB16–0x44CB6D`. REACHED.
11. **Catch-up breeding differs from live play.**
    * A villager picks embracing only 6% of the times the chooser lands on it (`RNG(100) ≤ 5`, `0x43B532`).
    * The partner search lets the man be any age 18+; only the woman must be under 50.
    * The child inherits 10–19 points, and Culture has no effect.
    *Evidence:* `0x43B52D–0x43B55A`. Scans `0x464847`/`0x464A54` (`RNG(10)+10` at
    `0x464998`/`0x4649BD`). REACHED (catch-up).
12. **Gender forcing in tiny villages.** In a village of 6 or fewer, a newborn's gender is forced if
    one gender has 2 or fewer adults. The forced gender is the majority gender, not the minority.
    *Evidence:* `0x43BE29–0x43BE3E` calls `0x43B3A0` when pop ≤ 6. `0x43B4A8–0x43B4C4` returns 2 if
    females > males and males ≤ 2, 1 if females ≤ males and females ≤ 2. Used as the gender override
    at `0x44CB7E`. REACHED. The meaning 1 = male, 2 = female comes from the live record table.
13. **Demo population cap (dead).** "Population under 7" gates in the conception and catch-up healing
    code are a demo limit, and they never apply in this build.
    *Evidence:* `0x44F73F`/`0x464738` check `[state+0x30380]`, which `0x425670` sets to 1
    unconditionally (`0x4256C2`). DEVELOPER-DEAD. The setter's own caller chain (`0x4262D0`,
    `0x4265B0`) was not traced to the program entry.

## 4. Healing (job 3, curing, plants, health)

1. **A healer only works if someone is sick.** The healer takes the first sick, living villager in
   record order who is not themselves. No age limit applies to the patient.
   *Evidence:* `0x46045A–0x4604AD` (`+0x52C` > 0, `+0x53C` ≠ 0, id pair ≠ self). REACHED.
2. **The cure needs the healer to pass a Healing roll first.** The roll is the first step of the
   "Healing someone" task, so failing it ends the task without curing.
   *Evidence:* `0x45D580` queues op‑6 type 3 (`0x45D5C8`) before op 20 (`0x45D5DC`). REACHED.
3. **Instant cure off the main screen.** If you are not on the main village screen, a healer's cure
   is applied instantly, with no walk and no skill roll.
   *Evidence:* `0x4604B6–0x4604DA`: `cmp [state+0x30470],1` (current screen id); otherwise op 20 is
   queued directly. Reachability depends on villagers updating while another screen is up, which I did
   not establish: UNVERIFIED-REACHABILITY.
4. **The cure itself.** A cure clears the sickness. Cured villagers gain 10–29 health only after all
   six strange plants have been understood.
   *Evidence:* `0x44D9E0`: clears `+0x53C`, People Cured++, and `if [state+0x2E788]` adds
   `RNG(20)+10` capped at 100 (`0x44DA8B–0x44DAB7`). The flag is set by callback 34 at `0x462839`
   when all of `+0x2E860…+0x2E888` are set. REACHED.
5. **Understanding a plant.** The first time someone understands each plant gives that healer +5
   Healing.
   * A villager who dislikes herbs refuses plant study.
   * Repeat studies only practise the skill roll.
   *Evidence:* callbacks 33–38 at `0x4627AA`/`0x462941`. Herb dislike (token 11) in the drop handler
   at `0x43046C`/`0x4304C5`. REACHED (player drag).
6. **Burying the dead.** Any adult has a 25% chance to go bury an unburied body. Villagers with
   Healing 50+ get a further 70% chance.
   *Evidence:* `0x44B400` finds a dead villager. `0x46198A–0x4619AF` (`RNG(100) < 0x19`,
   `cmp Healing,0x32`, `RNG(100) < 0x46`). Task `0x459290` ("Burying the dead"). REACHED.
7. **Getting sick** is rolled every age unit for each healthy villager:
   * Medicine 1: (3k+1)/1440. Medicine 2: (3k+1)/2460. Medicine 3: (2k+1)/5400.
   * k = 2 when the fire is out and 1 when it is lit.
   * On Easy, the roll is skipped half the time.
   * Villagers at or above age 50/58/66 (Medicine 1/2/3) add a further 1.5% per age unit.
   * The hospital does not lower this chance.
   *Evidence:* `0x43B2B0` (`RNG(0x5A0/0x99C/0x1518)`, fire `+0x2EAC4`, elderly `RNG(1000) ≤ 14`).
   Called at `0x43BD3D` with the Easy skip at `0x43BD21–0x43BD38`. REACHED.
8. **What sickness costs.** A sick villager loses 1 health with 61% chance per age unit (about 19%
   once at 20 health or less). Sickness never ends by itself; only a cure, a stew or an event clears it.
   *Evidence:* `0x43BBE1–0x43BC4B`. The only `+0x53C ← 0` writers I found are the cure paths, the
   stew handler `0x461040` and events. REACHED.
9. **Natural health regeneration** happens only when food > 0 and the villager is not sick.
   * On Easy, regeneration is always eligible.
   * On Medium/Hard it is eligible 50% of the time, plus more when the fire is lit or the hospital is built.
   * Villagers older than 840 + 160 × Medicine units (50/58/66 years) regenerate only 20% of the time.
   *Evidence:* `0x43BC64–0x43BD1B`. REACHED.
10. **Hospital recovery does nothing.** "Recovering at the hospital" (dropping a sick villager on the
    finished hospital) neither cures nor heals.
    *Evidence:* the only caller of `0x45C250` is `0x4302EA`. `opfind` shows no op 20 and no callback
    in its queue. Consistent with `docs/vv2-hospital-recovery-research.md`. REACHED (player drag).
11. **Catch-up healing.** On each healer skill step, the healer gets a Healing/1500 chance to run a
    cure scan.
    * The scan re-rolls the healer's Healing skill for every villager slot until it reaches the first
      sick one. Every successful roll also grants skill.
    *Evidence:* `0x4646CD–0x464769` (`RNG(0x5DC) < Healing`, `0x44E170` inside the 256-slot loop) and
    the op‑20 scan at `0x4647C2`. REACHED (catch-up).
12. **Old age.** On each birthday past age 55/63/71 (Medicine 1/2/3), a villager dies with a 10%
    chance per year past that age.
    *Evidence:* `0x43BD67–0x43BDEE` (threshold `940 + 160×Medicine` units, `RNG(100) < 10×years_over`
    → health 0). REACHED.

## 5. Research (job 4, tech points)

1. **No hidden extra gates.** Research has no gates beyond the shared chooser gates and the Research
   skill roll: no tech level, food level or building requirement.
   *Evidence:* dispatcher case `0x45FE6A` always calls `0x457CC0`, whose queue ends op‑6 type 4
   (`0x457EF9`) + callback 31 (`0x457F0D`). REACHED.
2. **Tech points per successful session:**
   * **Live play:** Research ÷ 11 at Science 1, ÷ 9 at Science 2, ÷ 5 at Science 3, rounded down.
     **A researcher with Research below 11 earns 0 points at Science 1.**
   * **During catch-up:** ÷ 7, ÷ 6 and ÷ 4.
   * 2× speed doubles the points; ½ speed halves them (if above 1).
   * A lit fire adds a 10% chance of +1 point.
   *Evidence:* callback 31 at `0x46361B–0x463809`:
   * Divisors via `0x2E8BA2E9`, `0x38E38E39` and `0x66666667`; catch-up divisors `0x92492493`,
     `0x2AAAAAAB` and `sar 2`.
   * Speed handling at `0x46376E–0x4637BB`; fire bonus `RNG(100) < 0xA` at `0x4637F8`.
   * The ÷5 branch at `0x463678` for levels above 3 can never run: DEVELOPER-DEAD.
   REACHED.
3. **Research injury.** Research has a 2% chance per session to injure, costing 0–9 health.
   *Evidence:* `0x463629` `RNG(100) < 2`, `RNG(10)`. REACHED.
4. **What higher Science changes.** Science also changes which walking path a researcher takes:
   `RNG(100) < 110 − 15 × Science` picks the extra-trip path. This is cosmetic only; both paths end
   in the same roll and payout.
   *Evidence:* `0x457D48–0x457D70`. REACHED.
5. **Tech costs.** Next-level tech costs:
   * Farming 1 500 / 90 000. Engineering 5 000 / 75 000.
   * Exploration 10 000 / 160 000. Science 16 000 / 150 000.
   * Medicine 20 000 / 65 000. Culture 20 000 / 85 000.
   *Evidence:* `0x442332–0x4423EF`. REACHED (tech screen).
6. **Teaching children (player only).** Dropping an adult on a child starts "Teaching children" only
   if the adult's Parenting is 50+. Below 50 they tell a story instead.
   * The lesson trains the teacher's Parenting.
   * Children under 14 attend but gain no skill.
   *Evidence:* `0x44F9D0` `cmp Parenting,0x32` → `0x44A4E0` (op‑6 type 2 at `0x44A63D`), else
   `0x449F40` "Telling a story". Attendee loop `0x44A7A4` `age < 0x118`. REACHED (player drop flag `+0x31`).

---

## Surprises (the gates a player would least expect)

1. **Catch-up rules differ from live play.**
   * **Breeding:** the man can be any age, children inherit 10–19 skill points instead of 4–11, and
     Culture has no effect.
   * **Food and research:** gathering always pays the normal-speed amounts, and research pays more
     tech points.
   * **Building:** construction moves at half speed.
2. **Research below 11 earns 0 tech points from the base formula at Science 1.** Below Science 2
   (Research 9+) or Science 3 (Research 5+), a low-skill researcher's only points are the lit fire's
   10% chance of +1 (rule 2).
3. **Twins and triplets are impossible below Medicine 3.**
4. **A child inherits nothing when the chosen parent is best at Parenting,** and the Culture 1
   "same skill" bonus (4–5) is lower than the normal 5–7.
5. **"Fixing hut" is fake.** Huts never decay, and below Engineering 3 builders never even examine them.
6. **Builders won't start huts 2 and 3 on their own.** The site's progress starts at 1 and they
   require 2, so someone has to drag a builder there once.
7. **The hospital doesn't reduce disease and doesn't heal.** Only the Medicine level and a lit fire
   change disease odds.
8. **Food under 300 makes a third of embraces fail.** The 300 mark also changes job order, and 150
   or less starts costing health.
9. **The 15/25/50 housing steps are hard limits,** because conception checks housing, not just the
   90 + collections cap.
10. **Villagers with every skill at 5 or below never pick a job by themselves.** Assigned work is
    forgotten once the skill in it drops below 6.
11. **In very small villages (6 or fewer), births are forced toward the majority gender.**
12. **Game speed changes food per trip and tech points per session,** not just the clock.


============================================================================
THE SECRET CITY (VV3) -- FULL REPORT
============================================================================

# Virtual Villagers 3 — The Secret City: hidden gates on work, building, breeding, healing and research

Source: stock `Virtual Villagers - The Secret City.exe` (831,488 bytes), disassembled with capstone. All addresses are image VAs.
**Evidence level: static only.** No game was launched. "Reached" below means a call chain was traced in the code from the game-screen update to the gate. Nothing here was observed in a running game. The same applies to every probability. A gate is marked UNVERIFIED-REACHABILITY when no such chain was traced, and its meaning is marked as inferred when only its effect could be read.

## 0. Common machinery (applies to all five activities)

**Units and identities used below**
- Age: 20 internal units = 1 displayed year (the birthday test `idiv 0x14` at 0x4602D9). Age is at record +0xDC4. One age unit = 60 × *game-speed value* real seconds: elapsed seconds are divided by 60 (`mul 0x88888889; shr 5`) and then by the speed value (`div [game+0x12F20]`) at 0x45F5A7–0x45F5B5. The speed value is 6 by default (0x427E46), and the options code sets 3, 6 or 10 (0x41DBB4, 0x41DB65, 0x41DB13). **At Normal speed one displayed year is 2 real hours.** Value 3 is read as "Fast" and 10 as "Slow" because a smaller value makes age advance faster. That labelling is inferred, not traced to the button art.
- Thresholds that recur below: 280 = 14 years, 360 = 18, 840 = 42, 1000 = 50.
- Food store: global 0x582490. The add routine is 0x4263F0.
- Skills sit at record +0xEAC in this order: Farming +0xEAC, Breeding +0xEB0, Healing +0xEB4, Research +0xEB8, Building +0xEBC. Each is clamped to 0..100 by 0x455740. Job numbers 0–4 follow the same order.
- Likes list: +0xFB4. Dislikes list: +0xFC0. Three slots each, tested by 0x4547B0. Item numbers index the exe's own 79-word list (eSayLikesList), e.g. 8 bees, 15 rocks, 30 wood, 33 fish, 34 fruit, 39 learning, 43 work, 66 rain, 70 honey.
- Technology levels are read by `0x426FC0(id)` on 0x582618: 0 Science, 1 Medicine, 2 Alchemy, 3 Restoration, 4 Leadership, 5 Nature, 6 Magic. IDs 1, 2, 4, 5 and 6 are identified from their effects matching the in-game tech texts. Science (0) and Restoration (3) are identified by elimination.
- Difficulty: [game+0x12F08], with 0, 1 (default, 0x427E3C) or 2. It is set from the options code at 0x41DBEE/0x41DC1C/0x41DC4E. Reading 0 as Easy and 2 as Hard is inferred.
- The Tribal Chief is the villager with byte +0xE80 set (search at 0x45EF30).
- "Catch-up" means the game is replaying time that passed while it was closed. During catch-up, flag [game+0x12FB4] is set (0x46054E).

**Reachability chains (static)**
- **LIVE:** game-screen Update 0x4684D0 (vtable entry at 0x49E8F0) → 0x45C990 at 0x46853D, which runs for each active villager with no queued action → 0x45C360, which makes up to 10 attempts (`cmp ebx,0xA` at 0x45C380) → scheduler 0x45BFE0 → job chooser 0x459730 → job dispatcher 0x45AF00 → action handler. Handlers are registered by id at 0x453D3B into the table at 0x596970. Each handler queues "steps". The step-start switch is 0x461FB0: type 7 is the skill test 0x45A2C0, type 27 adds build progress through 0x4358B0. The step-finish switch is 0x461BF0: type 13 is conception 0x4584B0, type 22 is cure 0x457350. Special steps go through 0x458DB0: case 24 food, 25 big catch, 26 research points, 43 chief's food.
- **CATCH-UP:** 0x4684D0 → 0x428C60 (at 0x46866D) → aging loop 0x45FFE0 (at 0x428CA0) → 0x45BF00, called 4 times per age unit (0x460568–0x460580). This only happens when the villager's processed clock is more than 2 units behind their age, and only for adults who are not sick, not pregnant and not the chief. 0x45BF00 → 0x459730 / 0x45AF00 → 0x45B790, which executes the queued steps on the spot: step 13 at 0x45B7EB, step 22 at 0x45B91E, everything else through 0x461FB0.

**The skill test behind every job: 0x45A2C0.** Every harvest, build, hut repair, cure, research session and conception goes through this test.
- Plain: each time a villager finishes a job they roll for success. The roll is 0-99 and passes at skill + 33 or below, so the chance is skill + 34 percent: a neutral villager at skill 0 succeeds 34% of the time, and anyone at 66 skill or more always succeeds. Villagers who like "learning" (or are under temporary effect 3) get +66 instead. Villagers who dislike "learning" get only +16. On a failure they shake their head, the rest of the job is cancelled (no food, no build progress, no tech points, no cure, no baby) and they gain nothing. The one exception: a villager at exactly 0 skill gains 4 points even when they fail.
  Evidence: the margin is set at 0x45A2F5–0x45A31B (0x21, 0x21−0x11, or 0x42). The test is `rand(100)` vs skill+margin, e.g. `cmp eax,ebp; jle success` at 0x45A34C. A failure clears the queue (0x460F70, e.g. 0x45A3BE) and starts action 0x31 "Shaking head". The zero-skill consolation is +4 at 0x45A3AE. REACHED through step type 7 in both chains.
- Plain: on a success the skill rises by (70 − skill) ÷ 18 for Farming, Research and Building; ÷ 10 for Breeding; ÷ 12 for Healing. The first success from 0 always gives 7. Learning-lovers get double and learning-haters get half. Once that formula reaches 0 (Farming, Building and Research from about 53; Breeding from 61; Healing from 59), each success has only a 51% × (100 − skill)% chance of +1. That is the slow grind to Master.
  Evidence: divisors are `0x38E38E39 sar2` (÷18) at 0x45A455, `0x66666667 sar2` (÷10) at 0x45A5CF, `0x2AAAAAAB sar1` (÷12) at 0x45A6EA, ÷18 at 0x45A7F3 and 0x45A9D3. The floor of 7 is at 0x45A46C. Doubling and halving are at 0x45A47A–0x45A48D. The chance of +1 is `rand(100)<=50 && rand(100)>=skill` at 0x45A493–0x45A4B2. REACHED.
- Plain (one-time mercy): before a village's first-ever Farming, Breeding or Research success, once one attempt in that skill has failed, the next attempt is guaranteed to succeed. Healing and Building get no such mercy.
  Evidence: flag pairs on 0x594C40 are 0x28B/0x29F (Farming, 0x45A354–0x45A38B), 0x28F/0x2A2 (Breeding, 0x45A503–0x45A53A) and 0x28D/0x2A1 (Research, 0x45A8A9–0x45A8E0). REACHED. Whether these flags are kept per village or per install was not traced.

## 1. Jobs and food gathering

**Who can work at all (scheduler 0x45BFE0)**
- **Children never work.** Anyone under 14 years is sent to child behaviour instead.
  Evidence: `cmp [esi+0xDC4],0x118; jge` at 0x45C15B → 0x45B9B0. REACHED, live. Catch-up uses the same 280 test at 0x45BF1C and 0x460538.
- **The Tribal Chief never picks a job.** The chief only buries the dead, frets over the sick, directs work where the player put them, or wanders.
  Evidence: `test [esi+0xE80]` at 0x45C110 → 0x45C11B / 0x45BDA0. The job chooser is never reached for the chief. REACHED.
- **Sick villagers and pregnant or nursing mothers never work.** Sick villagers mope or eat. Mothers only care for the baby.
  Evidence: sick +0xE89 → 0x45A250 (0x45C0D7). Pregnant +0xE8C → 0x459590 (0x45C0EF), which only starts baby actions 0x67/0x68/0x69 etc. REACHED.
- **Each decision is only a 34% chance to look for anything**, but the game retries the decision up to 10 times. In practice an idle adult almost always ends up doing something.
  Evidence: `rand(100) <= 0x41 → return` at 0x45C0BA–0x45C0D1, with the retry loop at 0x45C380. The chief is exempt. REACHED.
- **Heavy rain stops some workers.** In rain or storm weather of strength 50 or more, rain-lovers go drinking rain and rain-haters go indoors instead of working. Everyone else has a 20% chance of stopping.
  Evidence: `[0x4B86C4]==2||3 && [0x4B86D8]>=0x32` at 0x45C1D1 → 0x4594E0 (rain, item 66; 20% at 0x459535). Reading those two globals as weather type and intensity is inferred from the resulting actions. REACHED.
- **Catch-up only: villagers below 20 health do no work** while the game replays time away.
  Evidence: `cmp [esi+0xE78],0x14; jl` at 0x45BF2C. REACHED, catch-up.

**Which job they pick (chooser 0x459730)**
- A villager who does not like "work" takes a 15% chance of no job at all. A villager who dislikes "work" takes a further 70% chance of no job.
  Evidence: `rand<15 && !likes(43)` at 0x459733–0x45975A; `dislikes(43) && rand<70` at 0x45976C–0x459786. REACHED.
- The game compares the villager's five skills, but each skill is only looked at 84% of the time (`rand(100)>15`). The highest skill looked at wins. Breeding counts 15 lower than it really is. Medicine-haters skip Healing half the time.
  Evidence: 0x45978C–0x459840; Breeding `lea esi,[eax-0xF]` at 0x4597C1; Medicine (item 4) 50% at 0x4597FB–0x459815. REACHED.
- If the player ticked a job preference in the villager's Details (+0xEC0, set by the toggles at 0x46E00D–0x46E0BB), that job replaces the pick 86% of the time.
  Evidence: `rand(100) <= 0x55` at 0x45985B. REACHED.
- **Skill floor and a final roll.** A score of 5 or less means no job. Otherwise the job is taken only if `rand(100) < score + 40`, so a villager needs a score of 60 or more to always work.
  Evidence: `cmp esi,5; jle` at 0x45986D; `add esi,0x28; cmp eax,esi; jge none` at 0x459879. REACHED.

**Low food (≤ 250)**
- Plain: when food is 250 or less, anyone with Farming 20+ tries to farm first, whatever their usual job. Everyone whose job is not Farming or Healing has a 50% chance of standing around "Worried about food" instead of doing it.
  Evidence: `cmp [0x582490],0xFA; jg` at 0x45C213; `cmp [esi+0xEAC],0x14` at 0x45C229; `rand<50`, pick≠0/2 → action 0x76 at 0x45C244–0x45C265. REACHED, live.
- During catch-up the same 250 test only redirects Farming-20+ villagers to farm. There is no "worried" substitution. Evidence: 0x45BF91–0x45BFA6. REACHED.

**Where food can come from (dispatcher job 0, 0x45AF31)** — one available source is chosen at random.
- **Honey:** available only once project 1 (the honey site, object 0x5945D0) is complete **and** more than 10 honey is stored. Bee-haters and honey-haters run away 60% of the time.
  Evidence: `0x4358D0(1)` at 0x45AF46; `cmp [0x5945E0],0xA; jle` at 0x45AF4F; dislikes 8/70 then `rand<60` → "Running away" at 0x45B129–0x45B163. REACHED.
- **Fruit trees (up to 3):** a tree counts only if it is planted, has 10 or more fruit, and was planted at least 28,800 game-clock seconds ago. Fruit-haters run away 60% of the time.
  Evidence: 0x434090 (count), `0x434100(i) >= 0xA` at 0x45AF9A, 0x434030 (`0x7080` age test), dislike 34 at 0x45B0AC. REACHED.
- **Fishing:** available only once project 10 is complete. Haters of fish, the ocean or swimming run away 60% of the time. A fish-hater who does start fishing walks off every time when the action begins.
  Evidence: `0x4358D0(0xA)` at 0x45AFD3; dislikes 33/17/37 at 0x45B023–0x45B057; action 0x0B handler `dislikes(0x21)` → run away at 0x453453. REACHED.
- If none of these is available, the farmer finds nothing to do. Evidence: `test ebx,ebx; je fail` at 0x45AFEC.

**How much food a success brings**
- Fruit picking gives 4 food at Normal speed (8 at Fast, 2 at Slow, 4 during catch-up). Honey gives the same amounts.
  Evidence: `4.0 / (speed/6)` truncated, using the constant at 0x49D054: fruit at 0x434ACF–0x434AE4, honey at 0x431C0D–0x431C22. Catch-up fixed 4 at 0x434ABB / 0x431BE8. REACHED.
- A fishing success gives 8 food (11 at Fast, 5 at Slow, 8 in catch-up). **A fisher with Farming 88+ has a 10% chance of a 55-food catch instead.**
  Evidence: step 0x18 → 0x458E81 (8/11/5 at 0x458E90–0x458EBA); `cmp [esi+0xEAC],0x58; rand<10` → step 0x19 (+0x37) at 0x453597 / 0x458FDA. REACHED.
- **Chief bonus:** if the chief stands supervising that job, the yield gets +⅓ (fishing, fruit) or +½ (honey). The bonus fires only on a `rand(100) < 25 × Leadership level` roll, so it never happens at Leadership 0.
  Evidence: 0x45FC60 (`imul esi,0x19` at 0x45FC9A), called with 0x1C, 0x17 and 0x15 at 0x458EC1, 0x434AF1 and 0x431C2F. REACHED.
- **Player-assigned workers:** a villager the player dropped on a work spot keeps going back only while their skill for it is 6 or more (for the hospital spot, Healing 6+ *and* Medicine 2+). A villager who does not like work also skips the spot 20% of the time. Of the rest, 60% also skip it whenever food is 8,000 or more or they dislike work.
  Evidence: 0x45AA90 (`rand<20`, `rand<40`, `cmp food,0x1F40`, dislikes 43). The skill floor `cmp eax,6` is at 0x45AB4A. Medicine ≥2 is at 0x45AB2B. REACHED.
- Refill rates (re-checked constants from docs/vv3-nature-honey-research.md): trees refill after 10,800 s at factor 37, or 42 from Nature 1 up (0x4347AD–0x4347CD), capped at 1,000 per tree (0x434801). Honey refills after 3,600 s and is capped at 3,000 (0x4319E5, 0x431A24). REACHED (shared updater).
- Consumption: every villager eats 2 food per age unit. With food at 500 or less, they eat only half the time, and the other half there is a 30% chance they lose 1 health instead. With food at 8,000 or more on Normal, or always on Hard, there is a 76% chance they eat 2 more.
  Evidence: 0x460040–0x4600CB. REACHED.

## 2. Building

- **No population gate exists in the builders' list.** Builders choose at random among the sites that pass the checks below. With no site available, a builder does nothing.
  Evidence: option list at 0x45B1C0–0x45B39E; `cmp edi,ebx; je fail` at 0x45B39E. No population read occurs in the routine. REACHED.
- **A hut or project is offered to idle builders only after it is already 2% or more under way.** Builders do not start fresh sites on their own. In practice the player has to drop a villager on the site to begin it.
  Evidence: huts use `0x432210(i) > 1` (percent built since construction began; returns 0 until the first build action records a start at 0x432717) at 0x45B1DA, 0x45B207, 0x45B231 and 0x45B338. Projects 8, 6, 7 and 3 use `0x4358F0(id) > 1` (percent) at 0x45B25C, 0x45B2BD, 0x45B2E7 and 0x45B310. The player-drop route 0x45AC43–0x45AD95 has no such floor. REACHED. That the player normally starts the site is **inferred**.
- **The scaffolding project (project 8) needs the chief.** The chief must be standing on the scaffolding spot (chief +0xEA0 = 26), the site must report ready (0x594870 → 0x435080), and the builder needs Building 20+.
  Evidence: 0x45B278–0x45B2A6 (`cmp [ebx+0xEA0],0x1A`, `cmp [esi+0xEBC],0x14`). REACHED.
- **Dislikes interrupt building.** Rubble and the bath send haters of rocks or lifting away 60% of the time. Clearing leaves does the same for haters of plants or bushes. A villager who dislikes wood walks off a hut 40% of the time, partway through.
  Evidence: 0x45B44C–0x45B479 (items 15/44), 0x45B4C3 (15/44), 0x45B53A (65/25), and wood (30) `rand<40` at 0x453A8A–0x453AA8. REACHED.
- **Hut repairs only happen once all four huts are finished.** The builder examines a random hut (0–2), and 70% of examinations become a "Fixing hut". Fixing only trains Building; it changes nothing on the hut.
  Evidence: all of 0x4321F0(0..3) at 0x45B355–0x45B393 → option 9 → action 0x56 with `rand(3)` (0x45B5D5); `rand(100) < 0x46` → 0x448520 at 0x453CDC; the fix chain ends in a practise-Building step at 0x44862A. REACHED.
- **Build speed:** each successful "Building small hut" action adds **1 unit** of progress. The builder must pass the Building skill test first; on a failure no unit is added. A supervising chief adds a second unit on a 25% × Leadership roll. Hut 0 starts needing 250 units, hut 1 needs 1,600, and huts 2 and 3 need 2,000 each.
  Evidence: the chain is practise step 0x453B62 then step 27 at 0x453BE2 → 0x4358B0 → hut vtable+0x24 0x432680 → `0x435990` (+1) at 0x4327E9, with the extra +1 at 0x4327DE behind 0x45FC60. Starting remainders [0,250,1600,2000,2000] are at 0x49D0E0, applied by 0x4322F0. Totals are 2,000 for projects 21–24 at 0x49D230. REACHED.
- Low food applies here too: builders face the 50% "Worried about food" substitution when food is 250 or less (section 1).

## 3. Breeding (making babies)

- **Picking "Children" (chooser 0x459730):** Breeding counts as skill − 15. A villager needs Breeding 21 or more to ever pick it on their own, then must pass `rand(100) < (Breeding−15)+40`. **Without the Children preference ticked, a pick of Children still goes ahead only 25% of the time.**
  Evidence: 0x4597C1, 0x45986D, and `rand >= 0x4B` at 0x459890–0x45989F. REACHED.
- **Partner search (0x45CE00):** the partner must be of the opposite sex. Both must be **at least 18 and under 50 years old — for both sexes** — alive with health above 0, not sick, and not already pregnant or nursing. The partner must be active, must not be the villager themselves, and must not stand on the initiator's current target point. One eligible partner is chosen at random. **No family check exists**, so siblings, parents and children all qualify.
  Evidence: `0x168`, `0x3E8`, health, sick, pregnancy and gender tests at 0x45CE20–0x45CECC (repeated in the unrolled loop to 0x45D200); random pick at 0x45D21B. REACHED, live (0x45B60C) and catch-up (0x45B7F1).
- **At the moment of embracing (step 13 → 0x4584B0, live):** the pair needs health above 0, opposite sexes, neither sick, both 18 or older, and neither pregnant. **If food is 250 or less, the couple refuses 34% of the time ("worried about food").** This refusal only starts after the village's first conception. The initiator must then pass the Breeding skill test.
  Evidence: 0x458505–0x458579; `rand>0x41 && food<=0xFA && flag 0x291` at 0x45857B–0x4585A7; 0x45A2C0(…,1) at 0x4585BA. REACHED. Embracing (0x44A680) queues step 13 through 0x4616B0. That the player's drag-to-pair route ends in the same handler is UNVERIFIED-REACHABILITY.
- **Conception roll (live):** a baby is conceived if `rand(300) + 50 − 50×Medicine − bonus ≤ initiator's Breeding`. The bonus is 50 under temporary effect 0x11 and 100 under effect 0x1E; these are presumably the "fertile" and "very fertile" potions, a link that is inferred. So at Medicine 0 even a Breeding-100 villager succeeds only about 17% of the time; at Medicine 3 that rises to about 67%. **The village's very first conception skips this roll.**
  Evidence: 0x458679–0x4586F1 (`imul eax,eax,0x32`, `push 0x12C`); flag 0x291 test at 0x4586A7. REACHED.
- **Women 50 or older cannot conceive** in this live route. The check covers both partners, but only women.
  Evidence: `cmp [..+0xDC4],0x3E8; cmp [..+0xDC8],1` at 0x4586F3–0x45871A (gender 1 = the one who gets pregnant, per 0x45B89A). REACHED.
- **Dead demo gate:** a "population must be under 7" breeding block exists, but it is unreachable in this build because its switch is hard-wired on.
  Evidence: `[game+0x12F2C]` test at 0x4585C8 vs `mov byte [esi+0x12F2C],1` at 0x427EB1 (the only writer). **DEAD.**
- **Population and housing (0x45FE30, checked inside the pregnancy writer 0x455AB0):** no pregnancy can start once population (living villagers plus unborn babies) reaches **90 + 5 for each of 4 collections (all four give 25 instead of 20) + 10 at Magic 3.** Housing also gates it: **10+ villagers need at least 1 finished hut, 17+ need 2, and 35+ need 3.** Only huts 0–2 count; hut 3 does not. When a pregnancy is blocked it fails silently, after the skill test has already been spent.
  Evidence: 0x45FE37–0x45FEE6 (`add esi,0x5A`; `cmp ebx,0x23/0x11/0xA` with `edi>=3/2/1`); 0x455AB8 `je` exit. REACHED.
- **Twins and triplets need Medicine 3.** At Medicine 3 a pregnancy has a 7% chance of being multiple; a quarter of those are triplets (≈1.75% triplets, ≈5.25% twins). Below Medicine 3, every birth is a single baby.
  Evidence: 0x455B77–0x455BDD (`cmp eax,3`, `rand<7`, `rand<0x19`). REACHED.
- Conceiving also raises the initiator's Breeding by max(5, (100−skill)÷10). Evidence: 0x455AC5–0x455B12. REACHED.
- **Birth timing:** the baby arrives 40 age units after conception (2 displayed years, 4 real hours at Normal). Mothers do no work in the meantime.
  Evidence: `add eax,0x28; cmp eax,ecx` at 0x46034F. REACHED.
- **Small-village sex balancing:** with 6 or fewer villagers, if one sex has 2 or fewer members and is outnumbered, newborns are forced to that sex.
  Evidence: `cmp eax,6; jg` at 0x46036F → 0x45FDE0. REACHED.
- **Catch-up breeding is different.** While the game replays time, a villager whose pick is Children breeds on only 6% of tries. There is no Breeding skill test, no low-food refusal, no fertility-potion bonus, and no first-conception free pass. The partner search is the same, and the conception roll is `rand(300)+50−50×Medicine ≤ Breeding`.
  Evidence: 0x45BF52–0x45BF70 (`rand(100) <= 5`); 0x45B7EB–0x45B8C9. REACHED, catch-up.

## 4. Healing

- **A healer works only when someone is sick**, chosen at random (any age) among living, active, sick villagers.
  Evidence: 0x45D2C0 (sick byte +0xE89, health >0). REACHED (0x45B695 live, 0x45B924 catch-up).
- **With nobody sick, healers study medicine only at Medicine 2+.** Studying trains Healing. Below Medicine 2, a healer with no patient does nothing.
  Evidence: `0x426FC0(1) cmp eax,2; jl fail` at 0x45B69E → action 0xBD "Studying medicine" (0x451890, ends in a practise-Healing step at 0x4519FC). REACHED.
- **Cure chance:** the cure needs the Healing skill test ((skill + 34)%). **A healer who dislikes medicine then fails half of the successful attempts anyway** (live only).
  Evidence: 0x457395; dislikes(4) `rand<50` → fail at 0x4573A2–0x4573C0; the cure clears +0xE89 at 0x4573F0. REACHED, live.
- **Catch-up quirk:** in catch-up the medicine-hater penalty is missing. The cure counter 0x5824B0 goes up **even when the cure fails**. The live code bumps the same counter only on success, and pays its 30-cure award off it.
  Evidence: 0x45B961–0x45B971 (`inc [0x5824B0]` after `je`) vs 0x457405. REACHED.
- **Who gets sick (0x455C00, once per age unit per villager):**
  - At Medicine 0, only villagers aged 42 or older can catch disease, at about 1.5% per age unit.
  - At Medicine 1–3, anyone can. The per-unit chance is (3m+1)/1440, (3m+1)/2460 and (2m+1)/5400 for levels 1, 2 and 3, and the "elderly" 1.5% roll still applies from age 42 + 8 years per Medicine level.
  - m is 1 when the fire is lit or project 11 is complete, and 2 otherwise. On Hard, m goes up by one more unless both the fire and project 11 are in place.
  - On Easy, half of all rolls are skipped.
  Evidence: 0x455C03–0x455D0D (`0x5A0`, `0x99C`, `0x1518`, `0x3E8` cut at 0xE); elderly test 0x45C5E0 (`840 + 160×Medicine`); fire is project 20's object 0x5946D8 (table 0x4B0D88). REACHED via the aging loop 0x460297.
- **Sickness drains health:** 60% of age units, −1 health while health is above 20; at 20 or below, only 30% of those. Sick villagers never cure themselves. The only other clears found are potion and event code (0x42699A, 0x417802, 0x418102), which were not traced.
  Evidence: 0x46015E–0x4601AC. REACHED.
- **Natural recovery (healthy villagers):** +1 health per age unit when they pass a gate. The gate is a 50% roll; failing that, being on Easy, the fire burning (half the time), or Medicine 3. The +1 itself is certain below age 42 + 8 years per Medicine level, and 20% above it. Recovery needs food above 0.
  Evidence: 0x4601C9–0x460254; 0x45C610. REACHED.
- **Old-age death:** from 47 years at Medicine 0 (55, 63, 71 at Medicine 1, 2, 3), each birthday carries a 10% death chance per year past the threshold.
  Evidence: threshold `160×Medicine − 160 + 1100` at 0x4602C1–0x4602ED; roll at 0x4602F7–0x46033C. REACHED. The Medicine-0 threshold of 47 years is not listed in docs/vv3-nature-mortality-research.md.
- **Burying the dead:** when a body is found, any adult takes it on 25% of the time; otherwise a villager with Healing 50+ takes it 70% of the time.
  Evidence: 0x45C176–0x45C1A9. REACHED.

## 5. Research

- **Research needs no tech, food or population threshold.** A villager whose pick is Research always goes to the lab.
  Evidence: dispatcher case 3 → action 3 at 0x45B19E. REACHED.
- **Tech points are paid only after the Research skill test succeeds.** A failed test means no points.
  Evidence: Researching handler 0x448640: practise step `0x461290(3)` at 0x4487C0, then payout step 26 at 0x4487C9. REACHED.
- **Points per success** (handler 0x458DB0 case 26, from 0x459196). The payout depends on the Science level:

  | Science level | Live, Normal speed | Catch-up |
  |---|---|---|
  | 0 | Research ÷ 5 (×2 at Fast, ÷2 at Slow) | Research ÷ 4 |
  | 1 | Research ÷ 11 | Research ÷ 7 |
  | 2 | Research ÷ 9 | Research ÷ 7 |
  | 3 | Research ÷ 7 | Research ÷ 5 |

  At Science 1–3 the live result is also divided by speed ÷ 6. **Read literally, buying Science 1 cuts each researcher's payout per success by more than half (÷5 → ÷11).** Whether the action is also shorter at higher Science, so that the per-hour rate works out higher, was not established.
  Evidence: `dec eax` chain at 0x4591A2–0x4591B1; ÷5 at 0x4591C6; ÷11 at 0x45934D; ÷9 at 0x4592E2; ÷7 at 0x459274; Fast/Slow tweaks at 0x459200–0x45922A. REACHED. Live behaviour UNVERIFIED.
- **Bonuses:**
  - A supervising chief adds ⅓ (Science 0) or ¼ (Science 1+) on the 25% × Leadership roll.
  - **Only at Science 1+:** Magic 1+ adds +1 and temporary effect 4 adds +1.
  - A lit fire adds +1 10% of the time.
  Evidence: 0x459237–0x45925A; 0x4593AF–0x4593D0; Magic `0x426FC0(6)>=1` at 0x4593D5; effect 4 at 0x4593F2; fire at 0x459410–0x459435. The Science-0 path jumps past the Magic and effect lines. REACHED.
- **Lab accident:** each payout carries a 2% chance of losing 3–12 health. Evidence: 0x45916D–0x459191. REACHED.
- **Session length:** at Science level S, the session takes its first branch (the one with the 7–11 wait, 0x4486FC) with probability (100 − 15×S)%, and otherwise the branch with the 10–19 wait (0x4487AB). Evidence: 0x44867A–0x44869C. REACHED.

## Surprises (what a player would least expect)
1. **The 18–50 window applies to men too.** The autonomous partner search rejects anyone 50 or older, male or female (0x45CE6C/0x45CE74). Only the drag-and-pair route limits women alone.
2. **There is no incest check.** Siblings, parents and children are all valid partners (0x45CE00).
3. **Every birth is a single baby until Medicine 3**, and even then only 7% of pregnancies are multiple (0x455B86).
4. **Breeding is housing-gated:** 10, 17 and 35 villagers need 1, 2 and 3 finished huts. The fourth hut never counts (0x45FEEE–0x45FF14).
5. **Medicine 0 makes young villagers immune to disease.** Only those 42 and older can get sick; buying Medicine 1 lets anyone catch it, though rarely (0x455C85–0x455CEE).
6. **Builders never start a fresh hut or project on their own.** It must already be 2% under way (0x45B1DA etc.).
7. **The chief never does a job.** They only add a 25%-per-Leadership-level bonus to work they supervise (0x45C110, 0x45FC60).
8. **Science 1 appears to lower each researcher's points per success** (÷5 → ÷11, 0x4591B7 vs 0x459338). Magic's +1 is ignored at Science 0.
9. **Catch-up counts failed cures as "people cured"** (0x45B971). In catch-up, medicine-haters heal at full rate, and couples skip the skill and food checks.
10. **Expert fishers (Farming 88+) have a 10% chance of a 55-food catch** (0x453597).
11. **Dislikes decide work:** bee-haters avoid honey, wood-haters abandon huts, medicine-haters fail half their cures, and work-haters skip 70% of job decisions.
12. **One free success:** the first Farming, Breeding or Research success in a village is guaranteed after a single failure, and the first conception skips the fertility roll.
13. **A dead demo limit** (no babies at 7+ villagers) is still in the code, switched off by a hard-wired 1 (0x427EB1).


============================================================================
THE TREE OF LIFE (VV4) -- FULL REPORT
============================================================================

# Virtual Villagers 4 (The Tree of Life): hidden gates on work, building, breeding, healing and research

**Source.** Static disassembly (Python and capstone) of the stock
`research/stock-executables/Virtual Villagers - The Tree of Life.exe` (929,792 bytes; SHA-256 `6D27A429…1B220` per `docs/max-population-research.md`).
I did not run anything live, so **none of this has been checked in a running game**. The repo docs were used only as leads; every number below was re-read from the executable.
Two leads turned out to be wrong for VV4. They are called out where they come up: the examine-then-fix chance, and the claim that some breeding gates belong only to the manual route.

## Conventions used below

- **RNG(n)** is `0x4036D0`. It returns `rand() % n`, so a value from 0 to n−1. For example, "RNG(100) < 15" is a 15% chance and "RNG(100) <= 15" is 16%.
- **Age** is stored in age units. 20 units make one displayed year. The code itself divides age by 20 at `0x468784`/`0x4687B4` (`imul 0x66666667; sar 3`) and then compares the result with 60 and 70 years for the old-age achievements.
  - 280 = 14 y
  - 360 = 18 y
  - 1000 = 50 y
  - 40 = 2 y
- **Villager record fields used below:**
  - age `+0x1B8C`
  - gender `+0x1B90` (1 = female, which is the gender that becomes pregnant at `0x4650BE`/`0x460990`; 0 = male)
  - health `+0x1C40`
  - sick `+0x1C48`
  - pregnant/nursing `+0x1C4C`
  - litter `+0x1C50`
  - player-assigned work site `+0x1C54`
  - skills (float) `+0x1C5C`, in the order Farming 0, Parenting 1, Healing 2, Research 3, Building 4
  - job preference chosen by the player `+0x1C70`
  - likes `+0x1E60` (3 slots)
  - dislikes `+0x1E6C` (3 slots)
- **Preference IDs** (79-entry list):
  - 12 berries
  - 15 rocks
  - 17 the ocean
  - 30 wood
  - 33 fish
  - 34 fruit
  - 37 swimming
  - 39 learning
  - 43 work
  - 44 lifting
  - 65 plants
  - 66 rain
  - 4 medicine
- **Tech indices** (from the label string IDs `0x3ED..0x3F2`): 0 Science, 1 Medicine, 2 Learning, 3 Construction, 4 Food Mastery, 5 Dendrology.
  - The level getter is `0x41E1C0` on `0x4D6F5C`.
  - Every tech starts at **level 1** (`0x41E150` writes 1 to all six), and the save loader rejects levels outside 1..3 (`0x41E270`–`0x41E27B`).
- **Food stock** is `[0x4D6DD0]`. Every food gain goes through `0x41D920`, which multiplies it: ×1 at Food Mastery 1, ×1.5 at level 2 (`+amount/2`, `0x41D946`), ×2 at level 3 (`add esi,esi`, `0x41D942`).
- **Difficulty** is `[game+0x170F4]`: 0 Easy, 1 Normal (the default, `0x41F483`), 2 Hard. It is set by `theOptionsDialog` at `0x41B159`/`0x41B187`/`0x41B1B9`.
- **"Catch-up"** is the offline/time-skip simulation. While it runs, flag `[game+0x171A4]` is 1 (`0x468A59`/`0x468ACF`).

## Reachability chains

These were proved statically, by real call and vtable edges. **Nothing was run.**

- **R-LIVE (live AI):**
  1. `theMainScene` vtable `0x48ED58` slot 8 is `0x43F750` (the RTTI name was read).
  2. `0x43FF97` calls the villager manager `0x466420`. It does so only while game speed `[game+0x17110]` < 999, that is, not paused (`0x43FF8A`).
  3. `0x46643B` calls `0x45FAB0`.
  4. `0x45FC4E` calls `0x465BD0`. This per-villager tick runs `jmp 0x465840` ("think") when the action queue is empty, and otherwise `jmp 0x46A4D0` (run the current step).
  5. Step starts go through `0x46A030`, which is the tail of every action handler.
  6. "Think" `0x465840` calls the job chooser `0x461CC0` and the job dispatcher `0x4639B0`.
- **R-LIFE (once per age unit per villager):** `0x43F750` → `0x43F970` → `0x420330` → `0x420560` → `0x468430`. This tick handles eating, health, sickness, birth and catch-up.
- **R-CATCHUP:** `0x468430` (`0x468A60`–`0x468A75`) calls `0x465750` four times per lagging age unit, then `jmp 0x464FA0`. `0x464FA0` runs the queued steps immediately.
  - It only handles step types 3, 9, 15, 17–19, 24 and 29–32 (table `0x4651C4`/`0x4651B0`). Every other step is skipped.

---

## 1. Jobs and work (farming, berries, fruit, fishing, and general work)

### 1a. Who may think about work at all (live, `0x465840`)

1. **Only about a third of idle moments lead anywhere.** Each time an idle villager "thinks", nothing at all happens 66% of the time.
   - Evidence: `0x46587F` RNG(100); `cmp eax,0x41; jle` return. Continues only on 66..99 (34%). R-LIVE.
2. **Sick villagers never work.** They run the sick routine instead.
   - Evidence: `0x465898` `cmp [rec+0x1C48],0; je`, else `call 0x462A00`. R-LIVE.
3. **Pregnant or nursing villagers never work.**
   - Evidence: `0x4658AD` `cmp [rec+0x1C4C],0`, else `0x461A30`. R-LIVE.
4. **Children under 14 never get adult jobs.**
   - Evidence: `0x4658C9` `cmp [rec+0x1B8C],0x118` (280 units = 14 y); `jge` adult, else `0x465260` (child behaviour). R-LIVE.
5. **When a body is lying unburied, any adult may drop everything to bury it.** This happens 25% of the time. An adult with Healing ≥ 50 also takes 70% of the remaining cases, so a skilled healer buries about 77.5% of the time.
   - Evidence: `0x4658E7` `0x466CE0` finds the corpse; `0x4658FD` RNG(100) `cmp 0x19; jl` bury; `0x465910` `0x461910(skill2)` (Healing ≥ 50.0, constant at `0x4AA900`); `0x465923` `cmp 0x46` (70); then action 41, "Burying the dead". R-LIVE.
6. **In heavy rain, a villager who likes rain or dislikes rain stops work on every think. Everyone else loses 20% of their thinks to the rain.**
   - Evidence: `0x465952` weather `[0x6C461C]` ∈ {2,3} and `[0x6C4634]` ≥ 50.
   - `0x461960`:
     - likes 66 → action 36, "Drinking rain"
     - dislikes 66 → action 68, "Getting out of the rain"
     - otherwise RNG(100) < 20 (`0x4619D4`)
   - The weather meaning is inferred from preference 66 = "rain". R-LIVE.
7. **A villager the player dropped on a work site keeps at it, but each think can lapse.** A villager who does not *like* work skips the site 20% of the time. In a further 40% of cases the villager also skips if they dislike work or the village has ≥ 8,000 food.
   - Evidence: `0x4634D0`. `0x4634E4` likes 43; `0x4634F7` `cmp 0x14`; `0x463506` `cmp 0x28`; `0x46350B` `cmp [food],0x1F40`; `0x463525` dislikes 43. R-LIVE.
8. **A player-assigned job is dropped after one go if the villager's matching skill is below 6.**
   - Farming sites need Farming ≥ 6. The research site needs Research ≥ 6. Building sites need Building ≥ 6. The healing site needs Healing ≥ 6 *and* a finished hospital.
   - Evidence: `0x46355C`–`0x4635C6` `cmp eax,6`; the task-code→skill table is at `0x463920`. Codes 2/3/5/23–25/28 are Farming, 4 is Research, 6/7/11–17/30/31 are Building, 9 is Healing plus project 25. R-LIVE.
9. **At 250 food or less the village is in "hungry mode":**
   - Anyone with Farming ≥ 20 is sent farming first.
   - Healers keep their own job.
   - Everyone else has a 50% chance on each think of standing around "Worried about food" instead of doing their job.
   - Evidence: `0x46599D` `cmp [0x4D6DD0],0xFA; jg` normal mode. `0x4659C0` `0x4618F0(skill0)` (Farming ≥ 20.0, constant at `0x48CC34`) → dispatcher(0). `0x4659DA` RNG(100) `cmp 0x32`; job 0 or 2 is exempt; otherwise action 65, "Worried about food" (`0x4659FD`). R-LIVE.

### 1b. Which job a villager picks (chooser `0x461CC0`)

Reached by R-LIVE (`0x4659AB`, `0x465A1D`) and R-CATCHUP (`0x465798`).

10. **On each think there is a 15% "lazy" check. Any villager who does not like work takes no job when it fires.**
    - Evidence: `0x461CCC` RNG(100) `cmp 0xF; jge` skip; otherwise likes 43 is required (`0x461CE7`), or the chooser returns −1.
11. **A villager who dislikes work refuses a job 70% of the time** (on top of the 15% check).
    - Evidence: `0x461D02` dislikes 43; `0x461D15` RNG(100) `cmp 0x46; jl` no job.
12. **Each skill only "enters the running" 84% of the time.** The highest skill among those that enter wins.
    - Evidence: five `RNG(100) > 15` tests at `0x461D28`, `0x461D4D`, `0x461D82`, `0x461DAD`, `0x461E09`, each followed by an `int(skill) > best` compare.
13. **Healing is passed over half the time by a villager who dislikes medicine.**
    - Evidence: `0x461DC9` dislikes 4; `0x461DE2` RNG(100) `cmp 0x32; jl` skip.
14. **The player's job preference overrides the skill race 86% of the time.**
    - Evidence: `0x461E31` pref ≠ −1 and ≠ the pick; `0x461E4A` RNG(100) `cmp 0x55; jg` keep the pick; otherwise use pref and score = int(skill[pref]).
15. **No job is taken when the winning score is 5 or less.** Otherwise the villager acts only with chance (score + 40)%. So a brand-new villager (skill 0–5) never works through this chooser unless another path applies.
    - Evidence: `0x461E69` `cmp esi,5; jle` −1; `0x461E70` RNG(100) vs `esi+0x28`; `jge` −1.
16. **The "25% embrace fallback without the Children preference" is dead code.**
    - Job 1 is only ever selected when pref == 1 (`0x461D67`) or through the pref override. So the test "job 1 and pref ≠ 1" at `0x461E7F`–`0x461EA1` (`RNG(100) >= 75`) can never be true. Unreachable by construction.

### 1c. What a farmer actually does (dispatcher `0x4639B0`, job 0, `0x4639F0`)

Reached by R-LIVE and R-CATCHUP.

17. **The dispatcher refuses any job while the villager is flagged "busy at an assigned site"** (`+0x1C54 == 1`).
    - Evidence: `0x4639D2`. R-LIVE.
18. **Berry picking is offered only while the bushes hold more than 3 berries.**
    - The bush stock `[game+0x170F8]` regrows by +2 per world tick, up to 1,000 (`0x4203CA`–`0x4203E1`).
    - Evidence: `0x463A0A` `cmp [eax+0x170F8],3; jle`. R-LIVE.
19. **Fruit gathering ("Attempting to retrieve fruit") needs internal project 6 finished, and is never offered during catch-up.**
    - Evidence: `0x463A1B` `0x438960(6)` and `0x463A30` `cmp [game+0x171A4],0`. R-LIVE only.
20. **Fishing needs internal project 11 finished** (the piers and nets puzzle; its actions 127–129 are "fix nets", "fix piers" and "Retrieving a fish").
    - Evidence: `0x463A43` `0x438960(0xB)`. R-LIVE.
21. **A farmer who dislikes the food in question refuses 60% of the time and pulls a face instead.** That means berries (pref 12) for berry picking, fruit (34) for fruit, and fish (33), the ocean (17) or swimming (37) for fishing.
    - Evidence: `0x463BB2`, `0x463B47`, `0x463AD9`: `RNG(100) cmp 0x3C; jl` → action 6, and the assigned site is cleared. R-LIVE.

### 1d. Whether the work succeeds, and how skill grows (`0x462A80`)

Reached live via step 9 (`0x46A615`), in catch-up via step 9 (`0x464FDA`), and from the live heal and embrace steps.

22. **Every work attempt is a success roll.** The chance is **(skill + bonus + 1)%**:
    - bonus = **33** normally, **66** if the villager likes "learning", **16** if they dislike it
    - plus **15** at Learning tech level 2, or **30** at level 3
    - A fresh, neutral villager (skill 0, Learning level 1) succeeds 34% of the time.
    - Evidence: `0x462A8F`–`0x462AE9` (likes 39 → `mov edi,0x42`; dislikes 39 → 0x10; else 0x21; `0x462AD5` Learning: L2 +0xF, L3 +0x1E). Per skill: `RNG(100) > int(skill)+edi` = fail at `0x462B1F` (Farming), `0x462D9D` (Parenting), `0x462FA8` (Healing), `0x4632AD` (Research), `0x463134` (Building).
23. **A failed roll wipes out the task.** The queued steps are erased (`0x468C60`), so no food, building points or tech points are produced. The villager "shakes their head" instead (action 32).
    - Evidence: `0x462BAF`/`0x462BC6`, and the same at each skill. R-LIVE and R-CATCHUP.
24. **Skill gain on a success is (70 − skill) ÷ 9 for Farming, Research and Building, ÷ 6 for Healing, and ÷ 5 for Parenting.**
    - The result is rounded down, with a minimum of 7 at skill 0.
    - It is halved if the villager dislikes learning and doubled if they like it.
    - Once the formula reaches 0 (around skill 62–66), each success has only 50% × (100 − skill)% chance of +1.
    - At skill 100 nothing more is gained.
    - Evidence: magic constants `0x38E38E39 sar 2` (÷9) at `0x462CB7`/`0x4631C7`/`0x4633F0`; `0x2AAAAAAB sar 1` (÷6) at `0x46304F`; `0x66666667 sar 2` (÷5) at `0x462EC2`. `RNG(100) > 50` / `RNG(100) >= skill` at `0x462CFA`. The skill writer `0x46AD80` clamps to 0..100 (`0x48A7C0` = 100.0).
25. **A failed roll gives +4 skill, but only to a villager whose skill is exactly 0 (Farming, Healing, Research, Building).** For **Parenting the test is reversed**: *every* failed Parenting roll by a villager with Parenting above 0 gives +4. This looks like a developer slip.
    - Evidence: `0x461930` returns "skill == 0.0". Farming `0x462B98 je` skip; Healing `0x462FE0 je`; Building `0x46316C je`; Research `0x46335D je`; but Parenting `0x462E29 jne` skip. The +4.0 constant is at `0x4AA908`.
26. **Tutorial safety net:** in Farming, Parenting and Research, the second failed roll in a game is turned into a success, once. Healing and Building have no such net.
    - Evidence: tip flags via `0x44B9A0`/`0x44B890` on `0x4DACE0`. Farming pair `0x2B2`/`0x2D2` (`0x462B27`–`0x462B5E`), Parenting `0x2CC`/`0x2D5` (`0x462DA5`), Research `0x2BC`/`0x2D4` (`0x4632B5`).
27. **The skill rank names come from these cutoffs:** below 20 is Untrained; 20–49 is Trainee; 50–87 is Adept; 88 and up is Master. A villager under 14 with skill ≥ 20 shows as Apprentice. Reaching 88 also fires the "mastered" statistic.
    - Evidence: `0x41BE31`–`0x41BE7B` (`cmp 0x14`/`0x32`/`0x58`; age `cmp 0x118`; strings 0xD4–0xD9). Mastery: `0x46AD80` compares against 88.0 at `0x4AB378`. The display path reachability is **UNVERIFIED**. The 88 statistic is R-LIVE.

### 1e. How much food a successful job brings in

These are reward events through `0x4642F0`, step 19, before the Food Mastery multiplier.

28. **Berry picking (action 99) brings 1% of the bush stock, at least 2.** The berries are removed from the bush.
    - Evidence: `0x464464` (`/100` via `0x51EB851F sar 5`; `cmp edi,2`). R-LIVE.
29. **Each load of fruit is worth 3 food. Each fish is worth 4.**
    - Evidence: `0x464567` `push 3`; `0x4645A4` `push 4`. R-LIVE.
30. **During catch-up, once project 6 is finished, each adult also earns a flat +5 food per age unit.** This applies when they are assigned to the fruit site, or with chance (Farming − 25)%. They then take a Farming practice roll.
    - Evidence: `0x468A7A`–`0x468AC5`. R-CATCHUP.
31. **A villager eats 2 food per age unit.** At 500 food or less, each villager eats only half the time; the rest of the time there is a 30% chance of losing 1 health.
    - Evidence: `0x46848B` `cmp [food],0x1F4`; `0x4684A6`/`0x4684B5`; `0x46AF40(-1)`. R-LIFE.
32. **Normal and Hard: at 8,000+ food, or always on Hard, each villager wastes a further 2 food 76% of the time.** Easy never does.
    - Evidence: `0x4684D4`–`0x468512`. R-LIFE.
33. **With no food left, villagers lose health.**
    - Evidence: `0x468517`–`0x4685B7`. R-LIFE.

---

## 2. Building (huts, special buildings, fixing)

34. **A builder can only work on a building that has already been started.** The game unlocks a new building as an empty foundation with 0 progress, and the builder job only offers buildings that are at least 1% built. **The first push on a newly unlocked building has to come from the player dropping a villager on it.** After that, builders continue on their own.
    - Evidence: the unlock calls SetState(3) at `0x43097F`. SetState `0x430430` sets progress = 2000 − table[3] = 0 (table at `0x48E334` = 0, 250, 1600, 2000, 2000). `0x438980` returns 0 when progress == 0 (`0x438988`), and the dispatcher requires ≥ 1 (`0x463C7F` and similar).
    - Assigned-site continuation for project 19 (`0x4636CD`) and the others needs no ≥ 1%.
    - Static reasoning only. **The live behaviour is UNVERIFIED.**
35. **The buildings unlock by tech level, not by population.**

    | Project | Building | Unlocks when |
    |---|---|---|
    | 19 | Hut 1 | Always |
    | 20 | Hut 2 | Construction ≥ 2 |
    | 21 | Hut 3 | Construction = 3 |
    | 22 | Clothing hut | Science ≥ 2 (a second unlock path also exists when Science = 3) |
    | 23 | Love shack | Always |
    | 24 | Nursery school | Learning = 3 |
    | 25 | Hospital | Medicine = 3 |

    - Evidence: the vtable slot-25 predicates are `0x431070` (state==4), `0x430B90` (tech3 > 1), `0x430C00` (tech3 > 2), `0x430CF0` (tech0 > 1), `0x430DB0` (tech2 > 2), `0x430E30` (tech1 > 2); the Science=3 path is at `0x430156`–`0x430183`.
    - The names come from completion tips by region ID (`0x4302C3` table: regions 10–12 hut tip 0x2FC, region 20 clothing hut tip 0x2FD) and from the tech descriptions (Learning L3 = nursery, Medicine L3 = hospital).
    - Called from the per-project update (slot 9 `0x4300E0`), which is reached via the scene update. Reachability of the update caller is **UNVERIFIED-REACHABILITY** (it is a vtable call).
36. **Tech prices (tech points to reach level 2 / level 3):**

    | Tech | Level 2 | Level 3 |
    |---|---|---|
    | Science | 8,000 | 70,000 |
    | Medicine | 5,000 | 50,000 |
    | Learning | 4,000 | 35,000 |
    | Construction | 5,000 | 65,000 |
    | Food Mastery | 3,000 | 40,000 |
    | Dendrology | 3,000 | 60,000 |

    - The third population hut alone sits behind a 65,000-point purchase.
    - Evidence: `0x41E220` → table `0x4BC18C[level + 3·tech]`.
37. **Every building needs 2,000 build points. A successful build trip adds a fixed amount per building, so the buildings take wildly different numbers of trips:**

    | Building | Points per successful trip | Trips needed |
    |---|---|---|
    | Hut 1 | 12 | ~167 |
    | Hut 2 | 4 | 500 |
    | Hut 3 | 1 | 2,000 |
    | Clothing hut | 12 | ~167 |
    | Love shack | 200 | 10 |
    | Nursery | 50 | 40 |
    | Hospital | 50 | 40 |

    - The builder also has to be standing in the building's area, or the trip adds nothing.
    - Evidence: requirement `push 0x7D0` at `0x430FF8` and similar; rate `[obj+0x24]` = 0xC/4/1/0xC/0xC8/0x32/0x32 at `0x431052`/`0x4310F2`/`0x431172`/`0x4311F2`/`0x431272`/`0x4312F2`/`0x431372`. Applied by the loop at `0x43028D`–`0x4302A6` in `0x430210`; area check `0x43023B` (`[obj+0x14]` vs `0x46C3F0`). Reached via step 29 `0x46A7E2` → `0x438AC0` → slot 10. R-LIVE and R-CATCHUP.
38. **A builder who dislikes wood:**
    - only considers each wood building 16% of the time (`0x463CAA`… `RNG(100) <= 15`)
    - having started, walks off 40% of the time (`0x45C7FC` `cmp 0x28`)
    - R-LIVE.
39. **Puzzle chores:**
    - "Clearing debris" is offered only while that task sits between 1% and 97% done (`0x463DAF`–`0x463DCF`).
    - "Fixing the piers" is offered only while its stage is < 2 and its counter < 100 (`0x463DD8`–`0x463DF4`).
    - "Clearing rubble" is offered only while its object is untouched and its counter < 100 (`0x463E27`–`0x463E3C`).
    - Builders who dislike plants or lifting (debris), or rocks or lifting (rubble), refuse 60% of the time.
    - The rubble branch reports "nothing started" even when it does start rubble work (`0x464098`–`0x46412C` both `xor al,al`). The scheduler may therefore immediately pick something else. That consequence is **UNVERIFIED** live.
    - R-LIVE.
40. **Builders only "fix huts" once all four of huts 1–3 and the clothing hut are finished.**
    - Examining a hut leads to an actual fix **70%** of the time; otherwise the villager says "This hut is still in good repair."
    - `docs/builders-fix-huts.md` gives 30% as the series-wide figure. For VV4 the code says 70%.
    - The fix is only a Building practice roll and adds no points.
    - Evidence: `0x463E9B`–`0x463EDB` (all of 19..22) → option 9 → action 46 with RNG(3). `0x45CA32` RNG(100) `cmp 0x46; jge` the 0xAC message, else `0x4535D0`. Fix handler `0x4536E6` attempt(4). R-LIVE.

---

## 3. Breeding (embracing, pregnancy, births)

41. **Villagers only seek a partner on their own if the player set their job preference to Parenting/Children.**
    - When Parenting is also their best skill, they score Parenting − 15 and act with (P + 25)% chance; they need Parenting ≥ 21.
    - When another skill is higher, the 86% preference override scores the full P: act with (P + 40)% chance, needing P ≥ 6.
    - So a villager whose best skill is Parenting embraces *less* readily.
    - Evidence: `0x461D58`–`0x461D75` (`cmp [rec+0x1C70],1`; `lea esi,[eax-0xF]`); override `0x461E4F`–`0x461E67`. R-LIVE and R-CATCHUP.
42. **A partner must be:**
    - alive and at least 18
    - of the other sex
    - younger than 50
    - not sick
    - not pregnant
    - The initiator must also be 18+ and not pregnant, but has **no upper age limit** in this check. No family or relationship check exists.
    - Evidence: mate selector `0x466DA0`: `0x466DE0`/`0x466DE8` `cmp 0x168`; `0x466DFA` gender; `0x466E0D` `cmp edx,0x3E8` (candidate only); `0x466E15` sick; `0x466E39`/`0x466E3F` pregnant. Called from the dispatcher (job 1, `0x464181`) and catch-up (`0x464FFE`). R-LIVE and R-CATCHUP.
43. **In live play nobody can conceive until the love shack (project 23, "Rebuilding broken hut") is finished.** The game says "The love shack has not been completed!"
    - Evidence: `0x460CE3` `0x438960(0x17)`, message 0x9D. Live embrace step `0x460C10` is reached via step 15 → `0x46A220`. R-LIVE.
44. **Live embracing also fails if:**
    - either villager is sick, under 18, or already pregnant, or they are the same sex
    - "too hungry": at 250 food or less, 34% of embraces are refused, but only after the first breeding tip has been shown
    - Evidence: `0x460C94`–`0x460CDD`; food `0x460CFD`–`0x460D2B` (`RNG(100) > 65`, `food <= 0xFA`, tip flag 0x2CE). R-LIVE.
45. **The initiator must then pass a Parenting success roll** (rule 22). If it fails: "That didn't go too well."
    - Evidence: `0x460D40` `0x462A80(1)`. R-LIVE.
46. **Demo-era cap, dead code:** once the village reached 7 people, embracing would always fail, unless a game flag is set. The flag is unconditionally set to 1 when a game is created, and nothing else writes it, so the cap never applies in the full game.
    - Evidence: `0x460D4E` `cmp [game+0x1711C],0`; pop < 7 (`0x460D65`); the only writer is `0x41F4F3` `mov byte [esi+0x1711C],1`. Whether a save load can overwrite it is **UNVERIFIED**.
47. **The conception roll is a 300-sided die.** A baby is conceived when RNG(300) ≤ Parenting + 50 × Medicine level − 50.
    - So at Medicine 1 the chance is (P + 1)/300, at most 34%. Medicine 3 adds +100, giving at most 67%.
    - **The very first embrace of a game skips this roll.**
    - Evidence: live `0x460E31`–`0x460E65` (skipped when tip flag 0x2CE is unset, `0x460E2F`); catch-up `0x46500E`–`0x465048`. R-LIVE and R-CATCHUP.
48. **In live play, a mother aged 50 or over never conceives**, whichever of the pair started it. There is no upper age for fathers.
    - Evidence: `0x460E67`–`0x460E8C` (`cmp age,0x3E8` and `cmp gender,1` for both). R-LIVE.
49. **During catch-up, breeding skips almost all of these gates.** An adult who chose Parenting has a 6% chance per think of a partner search. A partner is then picked by rule 42, and only the 300-sided roll (rule 47) and the population cap (rule 50) apply.
    - Not checked during catch-up: the love shack, the hungry refusal, the Parenting success roll, and the mother-under-50 rule when she is the initiator.
    - This is why older mothers appear after being away.
    - Catch-up also requires health ≥ 20 and age ≥ 14 to think at all.
    - Evidence: `0x465750`: `0x46577B` `cmp [rec+0x1C40],0x14`, `0x46576B` age 0x118, `0x4657A4` RNG(100) `cmp 5; jg`. Step 15 → `0x464FF8` (no love-shack/food/attempt calls). R-CATCHUP.
50. **Population cap:** no new pregnancy can start once the village (living villagers plus babies being nursed) reaches **90 + 5 per completed 12-piece collection**. There are four collections; all four give 25, so the cap is 115.
    - Below the cap, the village also needs **hut 1 built to pass 10 people, huts 1 and 2 to pass 17, and huts 1–3 to pass 35.**
    - Only huts 19–21 count. The clothing hut does not.
    - Evidence: `0x468350`: collections 0x46/0x52/0x5E/0x6A (`0x4143F0` = 12 pieces), `cmp esi,0x14 → 0x19`, `add esi,0x5A`; `cmp ebx,0x23/0x11/0xA` against the hut count from `0x438960(0x13..0x15)`. The count is `0x467610`. Called first thing in the conception routine `0x45E7C1` (unless suppressed). R-LIVE and R-CATCHUP.
    - The collection names (fish scales, research lab, then probably mausoleum and wind flutes) are in label order; the last two are **UNVERIFIED**.
51. **Without Medicine level 3, every birth is a single baby.**
    - At Medicine 3: 7% of pregnancies are multiple, and a quarter of those are triplets. That works out to about 5.25% twins and 1.75% triplets.
    - Evidence: `0x45E87D` litter = 1; `0x45E88C` Medicine == 3 and `0x45E89B` RNG(100) < 7; `0x45E8BB` RNG(100) < 25 → 3, else 2. R-LIVE and R-CATCHUP.
52. **Conceiving raises the mother's Parenting by (100 − P)/10, at least 5.**
    - Evidence: `0x45E7CE`–`0x45E812`.
53. **Pregnancy and nursing last 40 age units (2 years).** The child then appears as a 2-year-old.
    - Evidence: `0x4687EF` `add eax,0x28; cmp eax,[clock]`; birth via `0x467D50` with `push 0x28`. R-LIFE.
54. **In a village of 6 or fewer, a baby's sex is forced to the rarer sex if that sex has 2 or fewer members.**
    - Evidence: `0x468809` `cmp eax,6; jg`; `0x468300` with `cmp ecx,2`. R-LIFE.
55. **Pregnant and nursing villagers do no work** (rule 3).

---

## 4. Healing (curing the sick, medicine)

56. **A healer's job offers two things.** If any villager is sick, the healer is sent to a random sick villager (no priority by health). If nobody is sick, the healer studies medicine, but only once the hospital is built. Otherwise the healer has nothing to do.
    - Evidence: dispatcher job 2 `0x4641FC`; patient finder `0x466EB0` (alive, active, `+0x1C48` set); `0x46420C` `0x438960(0x19)` → action 94, "Studying medicine". R-LIVE.
57. **A cure is a Healing success roll** (rule 22).
    - Even after a successful roll, **a healer who dislikes medicine fails half the time.**
    - A cure clears the sickness and adds 1 to People Cured.
    - Evidence: live heal `0x45FD90` (step 24 via `0x46A230`): `0x45FDD9` attempt(2); `0x45FDE8` dislikes 4; `0x45FE01` RNG(100) < 50 fail; `0x45FE36` clear; `0x45FE77` People Cured `[0x4D6DF0]`++. R-LIVE.
58. **During catch-up, cures skip the walk and the medicine-dislike check, and the People Cured counter rises even when the cure fails.** That is a statistics defect in stock VV4.
    - Evidence: `0x465122`–`0x465182` (`je 0x465182` skips only the clear; the `add [0x4D6DF0],1` is unconditional). R-CATCHUP.
59. **Sick villagers lose health.**
    - Each age unit, 61% of the time, they lose 1 health; at 20 health or less, only a 31% chance.
    - Evidence: `0x4685BC`–`0x468600`. R-LIFE.
60. **How often villagers fall ill, per age unit:**

    | Medicine level | Chance |
    |---|---|
    | 1 | 4 in 1,440 |
    | 2 | 4 in 2,460 |
    | 3 | 3 in 5,400 |

    - A villager past "old age" has an extra 15 in 1,000 chance. Old age is 840 + 160 × Medicine units: 50 y at Medicine 1, 58 at 2, 66 at 3.
    - On Easy, only a quarter of these checks happen (two separate 50% skips).
    - Evidence: `0x45E930`: `0x45E938` difficulty; `0x45E9AA` `0x5A0`, `0x45E991` `0x99C`, `0x45E978` `0x1518`; old age `0x465EB0` (`lea; shl 5; add 0x348`), `0x45E9CB` RNG(1000) ≤ 14. Called at `0x4686D0` (with another Easy 50% at `0x4686B0`). R-LIFE.
61. **Healthy villagers with food recover 1 health per age unit; old villagers only 20% of the time.**
    - On Normal and Hard this happens on 50% of age units. It also happens on 50% of the rest if a fire is burning, and always at Medicine 3.
    - On Easy it always happens.
    - Evidence: `0x468605`–`0x4686A6`. R-LIFE.
62. **Healing practice:** studying medicine at the hospital is a Healing success roll that only trains the skill.
    - Evidence: action 94 handler `0x44F8F1` attempt(2). R-LIVE.

---

## 5. Research (tech points)

63. **Researching needs no table or building.** Anyone whose chosen job is Research just researches.
    - Evidence: dispatcher job 3 `0x463BFC` → action 2 (`0x453700`). R-LIVE.
64. **Each research trip is a Research success roll** (rule 22). A failure produces no tech points.
    - Evidence: `0x453898` attempt(3), then reward event 19 (`0x4538A1`). R-LIVE and R-CATCHUP.
65. **Tech points per successful trip, live:**
    - Research skill ÷ 11 at Science 1, ÷ 9 at Science 2, ÷ 7 at Science 3, rounded down.
    - Then scaled by the game-speed setting: divided by (speed / 6). Speed 6 is the default.
    - **During catch-up the divisors are kinder** (÷ 7, ÷ 7, ÷ 5) and are not speed-scaled.
    - So a researcher below 11 skill earns nothing from the base formula at Science 1.
    - Evidence: `0x464ADF`–`0x464E39`. Science via `0x464BE8`. Magic constants: `0x2E8BA2E9` (÷11), `0x38E38E39 sar 1` (÷9), `0x92492493` (÷7), `0x66666667 sar 1` (÷5). Speed `0x41DB00` = `[0x4D6F18+0x20]/6.0` (`0x48D5B8`); the speed setter is `0x41DBE0`. R-LIVE and R-CATCHUP.
66. **Science level 0 would give zero base points. That branch is dead, because Science always starts at level 1.**
    - Evidence: `0x464C02` `jne 0x464E40` with edi = 0; `0x41E150`; loader `0x41E270`.
67. **Research bonuses:**
    - A villager under status effect #1 earns triple points.
    - Each completed research-lab piece adds RNG(pieces) points.
    - A burning fire gives a 10% chance of +1 ("Fire assists researchers").
    - Evidence: `0x464E46` `0x45EB90` (effect type 1 via `0x4CE1C0`) → `lea edi,[edi+edi*2]`; `0x464E5D` collection 0x52 count → `RNG(count)`; `0x464E87` fire `0x432600`, RNG(100) < 10 → +1. Which stew or puzzle grants effect #1 is **UNVERIFIED**. R-LIVE.
68. **Each research trip has a 2% chance of costing the researcher 0–9 health.**
    - Evidence: `0x464BB0` RNG(100) < 2 → `0x46AF40(-RNG(10), 3)`. R-LIVE.

---

## Surprises: the gates a player would least expect

1. **The love shack is required to breed live, but not during catch-up.** Catch-up conception ignores the love shack, hunger, the Parenting roll, and the under-50 limit for an initiating mother (rules 43, 49).
2. **Autonomous breeding happens only when the player sets the villager's preference to Parenting.** A villager whose *best* skill is Parenting embraces less often than one whose Parenting is lower than another skill (rule 41).
3. **No twins or triplets until Medicine level 3** (rule 51).
4. **Hut 3 gets 1 build point per successful trip against 2,000 needed**, versus 12 for hut 1. It is also locked behind the 65,000-point Construction level 3. Populations over 35 need it (rules 37, 36, 50).
5. **Builders will not start a newly unlocked building on their own.** The first work has to come from a player drop (rule 34, static, not checked live).
6. **"Fix huts" needs the clothing hut (Science 2) as well as the three population huts**, and examining leads to a fix 70% of the time, not the 30% the repo doc states (rule 40).
7. **Every failed Parenting roll by a villager with Parenting above 0 gives +4 Parenting.** In every other skill, failure only helps at skill 0 (rule 25).
8. **Liking "learning" doubles the base success bonus** (66 against 33) and doubles skill gains. Disliking it cuts the bonus to 16 and halves gains (rules 22, 24).
9. **In heavy rain, anyone who likes *or* dislikes rain stops working altogether** (rule 6).
10. **At 250 food or less, half the village's thinking turns to "Worried about food"** (rule 9).
11. **Live research is divided by the game-speed factor, and catch-up research uses kinder divisors**, so time away out-researches watching (rule 65).
12. **Catch-up counts failed cures as "People Cured"** (rule 58).
13. **Dead code:**
    - the chooser's 25% embrace fallback (rule 16)
    - the population-7 embrace block (rule 46)
    - the Science-level-0 research branch (rule 66)
14. **Tutorial gifts:** the first embrace of a game always conceives if eligible, and the second Farming, Parenting or Research failure is turned into a success, once (rules 26, 47).
15. **A villager whose skills are all 5 or lower never takes a job by themselves.** They need a player drop, the nursery school, or the low-food farming path, which itself needs Farming ≥ 20 (rules 15, 9).
16. **Difficulty silently changes the simulation.** On Easy, villagers fall ill a quarter as often. On Hard (and at 8,000+ food on Normal), villagers waste extra food (rules 32, 60).


============================================================================
NEW BELIEVERS (VV5) -- FULL REPORT
============================================================================

# Virtual Villagers 5: New Believers: hidden gates on jobs, building, breeding, healing and research

All of this comes from reading the stock executable statically:
`research/stock-executables/Virtual Villagers - New Believers.exe`, 991,232 bytes,
SHA-256 `92946781…C65D`. I disassembled it with capstone. **No game was launched**, so nothing here has been
checked in live play. Where an existing repo document said something, I checked it against the
exe again. My findings matched the docs everywhere I compared them.

## Conventions used below

- **Random rolls.** `RNG(n)` at `0x403660` returns `rand() % n`, a value from 0 to n−1. "RNG(100) < 15" therefore means a 15% chance.
- **Ages.** Age is stored in record field `+0x1B8C`, in units of 1/20 of a displayed year. The code divides by 20 itself at `0x473055` (`imul 0x66666667; sar 3`) to award the 60- and 70-year achievements.
  - 280 units = 14 years. 360 units = 18 years. 1000 units = 50 years.
- **Skills.** The six skills are floats from `+0x1C5C` upward. Their index order is fixed by the code that uses them:
  - 0 Farming
  - 1 Breeding/Parenting
  - 2 Healing
  - 3 Research
  - 4 Building
  - 5 Devotion
  - Evidence: farm events check skill 0, the pregnancy writer trains skill 1 on the mother, the cure step checks skill 2, the research event reads `+0x1C68`, building checks skill 4, and Honoring checks skill 5.
  - Other fields: preferred job `+0x1C74`, likes `+0x1F5C`, dislikes `+0x1F68`.
- **Preferences.** Each villager has 3 like slots and 3 dislike slots, matched by `0x464F90`. Preference numbers index the embedded list at file offset `0xAEF60`. Examples: 4 medicine, 12 berries, 15 rocks, 30 wood, 33 fish, 37 swimming, 39 learning, 43 work, 66 rain. Running (38) and work (43) agree with earlier repo evidence.
- **Job numbers.** The work dispatcher `0x46C540` uses: 0 Farming, 1 Children, 2 Healing, 3 Research, 4 Building, 5 Devotion.
- **Technologies.** Tech levels run 1–3 and are read with `0x423600(id)` on `0x51D5CC`. The upgrade costs come from table `0x4CA3B4`:

  | id | Tech | Level 2 cost | Level 3 cost |
  |---|---|---:|---:|
  | 0 | Science | 8,000 | 70,000 |
  | 1 | Medicine | 5,000 | 50,000 |
  | 2 | Learning | 4,000 | 35,000 |
  | 3 | Construction | 5,000 | 65,000 |
  | 4 | Food Mastery | 3,000 | 40,000 |
  | 5 | Spirituality | 8,000 | 80,000 |

- **Projects and puzzles.** "Project n complete" means `0x43AE80(n)` on `0x51E008`, which tests progress ≥ threshold. Indices come from the `0x43ABB0` registrations and the RTTI names:

  | n | Object (in-game action) |
  |---|---|
  | 2 | CFencePuzzle ("Making a granary out of the fence") |
  | 3 | CFoodTotemPuzzle (Hungry Totem) |
  | 4 | CResearchTotemPuzzle (Knowing Totem) |
  | 5 | CHydroFarm |
  | 6 | CRestoreMausoleumPuzzle |
  | 10 | CRestoreLake |
  | 11 | CMedicineTotemPuzzle (Pain Totem) |
  | 14 | CBelieverIdolPuzzle (statue) |
  | 19 / 20 / 21 | CHouse1 / CHouse2 / CHouse3, 2,000 points each |
  | 22 | CClothingHut |
  | 23 | CLoveShack |
  | 24 | CNurseryHut |

- **Global state.**
  - Food stock: `[0x51D34C]`.
  - Tech points: `[0x51D5F8]`.
  - Village manager: `0x425950()`.
  - Offline catch-up flag: manager `+0x17E10` (=1 only while the offline catch-up simulation runs; set and cleared at `0x47330A` and `0x473330`).
  - Game speed: manager `+0x17D7C`. Values are 3, 6 (default) and 10, plus 999 for paused, set at `0x41B93F`, `0x41B969`, `0x41B990` and `0x41B911`. The value divides the ageing rate (a villager year takes 20 x 60 x value real seconds), so 3 is Fast and 10 is Slow, as in the other four games and in docs/vv5-origins-exclusive-features-research.md. (An earlier draft of this section had the two reversed.)
  - Difficulty: manager `+0x17D54`, values 0, 1 or 2. Default 1 is set at `0x4249D3`. The setter at `0x41B9B9`/`0x41B9E7`/`0x41BA19` sits next to strings "Difficulty / Easy / Medium / Hard" (ids 1406–1409). I read it as 0 = Easy, 1 = Medium, 2 = Hard, but that mapping is inferred from button order.
- **Faction.** Record byte `+0x1CEC`: 0 is a Believer, non-zero is a Heathen. In VV5, sex value 1 is the female: the pregnancy wrapper `0x467D20` picks the mother as the partner with `+0x1B90 == 1`.

### How reachability was established

Each chain below was followed through direct calls or vtable slots. **All of it is static evidence, not live-play confirmation.**

- **Live AI.** `theMainScene` vtable `0x49A2F4` (slot `0x49A314`) → `0x442350` → `0x470980` (call at `0x44244F`) → per villager `0x46F3C0` (at `0x4709AC`). That function retries the scheduler `0x46F070` up to 10 times while the villager's action queue is empty (`0x46F3D3`).
  - The scheduler calls the chooser `0x46A3C0`, the dispatcher `0x46C540`, and the continue-assignment routine `0x46BCF0`.
  - A second per-villager path, `0x471EB0` → `0x4671E0` → `0x46F4A0`, also tail-jumps to `0x46F070` (`0x46F580`) and to the step-update executor `0x473B30`.
- **Live steps.** Every behaviour routine ends with `jmp 0x473590`, which starts the next action step.
  - Step type 16 starts `0x4689A0`, the embrace/conception step (`0x473859`).
  - Step type 25 starts `0x468C10`, the cure step (`0x47386A`).
  - Step type 10 is a skill check calling `0x46B270` (`0x473C69`).
  - Step type 20 fires a work event into `0x46CE60` (`0x473D13`).
- **Life tick.** It runs per villager for every 1/20-year age unit, both live and offline. The chain is `0x442350` → `0x425E30` (`0x4425C0`) → `0x472C90` (`0x4260EB`).
  - If a villager's clock is more than 2 units behind, this routine also runs 4 offline job ticks `0x46E8E0`, which resolve steps instantly through `0x46E020`.

---

## 1. Jobs and work (gathering food, and the general rules for every job)

### General gates (every adult job, live play)

1. **Heathens never use the work system.** A Heathen is sent to separate Heathen AI before any job choice is made.
   - Evidence: `0x46F0BA` `cmp byte [rec+0x1CEC],0; je` → else `call 0x46E9E0`. That routine contains no call to the chooser or the dispatcher. *Reached* (live AI chain).

2. **Most idle checks do nothing at all. Two in three attempts are skipped, but the game retries up to 10 times, so an idle villager almost always gets a decision within a frame.**
   - Evidence: `0x46F0CF` `RNG(100)`, `cmp eax,0x41; jle → exit`. This proceeds only on 66–99, a 34% chance per attempt.
   - Evidence for the retry: `0x46F3D3` `cmp edi,0xA`, up to 10 scheduler calls while the queue is empty. That makes the per-frame chance about 1 − 0.66¹⁰ ≈ 98%. *Reached.*

3. **Sick villagers, and mothers who are pregnant or nursing, never work.** They follow their own sick or nursing routines instead.
   - Evidence: `0x46F0E8` sick byte `+0x1C48` → `0x46B1F0`; `0x46F0FD` `+0x1C4C != 0` → `0x46A1D0`. Neither routine calls the chooser or the dispatcher. *Reached.*

4. **Children under 14 never work.**
   - Evidence: `0x46F117` `cmp [rec+0x1B8C],0x118; jl → 0x46E3F0` (280 units = 14 years). *Reached.*

5. **Rain can interrupt work.** When it rains, the villager may run for shelter, or play in the rain if they like rain, before any job is considered.
   - Evidence: `0x46F1B1`–`0x46F1D1`: weather `0x477040` state ∈ {2,3,5} and `[0x718EB8] ≥ 50` → `0x46A100`, which uses behaviours 0x2B/0x4A and checks like #66 "rain". The exact odds inside `0x46A100` were only partly decoded. *Reached.*

6. **Choosing a job (the chooser at `0x46A3C0`).** These are all hidden rolls.
   - **Villagers who don't like work sometimes refuse.** A villager who does not *like* "work" (#43) refuses to choose any job 15% of the time.
     - Evidence: `0x46A3CC` `RNG(100)<15` → `likes(43)` else return −1.
   - **Villagers who dislike work refuse 70% of the time on top of that.**
     - Evidence: `0x46A40B` `RNG(100) < 0x46`.
   - **A skill is only considered 84% of the time.** The villager tends to choose its highest skill, but each skill is skipped 16% of the time. Ties keep the earlier skill, in the order Farming, Breeding, Building, Healing, Research, Devotion.
     - Evidence: six `RNG(100) > 15` gates at `0x46A41E`, `0x46A443`, `0x46A478`, `0x46A4A3`, `0x46A4FF`, `0x46A52B`.
   - **The preferred job usually wins.** The villager's preferred job overrides the highest-skill pick 86% of the time.
     - Evidence: `0x46A56B` `RNG(100) ≤ 0x55`.
   - **Weak villagers rarely act.** A job is attempted only if its skill is above 5, and then only with chance (skill + 40)%. So at skill 5 or below nothing is done, at skill 30 there is a 70% chance, and at skill 60 or more it always happens.
     - Evidence: `0x46A594` `cmp esi,5; jle → −1`; `0x46A599` `RNG(100) < esi+0x28`.
   - **Healing and medicine.** A villager who dislikes "medicine" (#4) skips Healing as their best skill half the time.
     - Evidence: `0x46A4C7` `dislikes(4)` → `RNG(100) < 50` skips.
   - All of the above is *Reached* (called from `0x46F26C`, `0x46F2DD` and `0x46E928`).

7. **Every job action is a skill check. A failed check means no food, no tech points and no building progress for that action, and the villager just shakes their head.** These gates live in `0x46B270`, the step-type-10 skill check that every work behaviour queues before its payoff event.
   - **The success roll.** Success means `RNG(100) ≤ skill + B`, where:
     - B = 33 normally, 66 if the villager likes "learning" (#39), and 16 if they dislike it.
     - The Learning tech adds +15 at level 2 and +30 at level 3.
     - Unskilled villagers therefore succeed about 34% of the time at Learning level 1.
     - Evidence: `0x46B27F`–`0x46B2D9` (`mov edi,0x42`, else `0x21` or `0x10`; `+0x0F` / `+0x1E` from `0x423600(2)`), and the compare at `0x46B30F` (and the five sibling compares).
   - **On a failure** the action queue is cleared (`0x473440`) and the villager is given behaviour 0x25, "Shaking head".
   - **Beginner's consolation.** A villager failing with a skill of exactly 0 still gains +4.0 skill (`0x46B340`–`0x46B35B`).
     - **Breeding is inverted:** the +4 is given only when the Breeding skill is *not* 0 (`0x46B517` `jne` skips the add when skill==0).
   - **Skill gain on success** is (70 − skill) ÷ d, with d = 9 for Farming, Research, Building and Devotion, 5 for Breeding, and 6 for Healing.
     - A skill of exactly 0 gets at least 7.
     - The gain is halved for villagers who dislike learning and doubled for those who like it.
     - Devotion additionally gets + the Spirituality tech level (`0x46BC82`).
     - When the computed gain is 0 or less (from about skill 62 for d=9), the villager gains +1 only with chance 51% × (100 − skill)%.
     - Evidence: `0x46B3EE`–`0x46B46E` and siblings (divisors `0x38E38E39`, `0x66666667`, `0x2AAAAAAB`).
   - **Which behaviours queue a skill check.** The queue routine is `0x474780`. Callers: farm `0x457968`, `0x457C2D`, `0x457CD4`, `0x463B62` (skill 0); research `0x45A7A8` (skill 3); study medicine `0x455391` (skill 2); build `0x463DC4` and every totem, statue and granary routine (skill 4); Honoring `0x45CC9B` (skill 5). *Reached* (live executor and catch-up `0x46E05A`).

8. **A job the player assigned by drag only continues while the villager stays competent.** Without the needed skill, the assignment is silently dropped.
   - Evidence: in `0x46BCF0` the assignment is kept only if the matching skill is ≥ 6 (`0x46BD96`, `0x46BDD4`, `0x46BDF8` `cmp eax,6`). Otherwise `+0x1C54` is cleared.
   - **A villager who doesn't like work also sometimes stops** on an assigned job: 20% of checks they do nothing, and 40% of the rest they quit when food is 8,000 or more, or when they dislike work.
     - Evidence: `0x46BD15`–`0x46BD54`.
   - *Reached* (`0x46F251`).
     - The scheduler gate at `0x46F23A` only calls `0x46BCF0` when `+0x1C54` is 2 or more. **What a value of 1 means is unidentified.** It also makes the dispatcher refuse, at `0x46C565`.

### Food gates

9. **When food is at 250 or below, farming comes first, and half the village just worries.**
   - **Farmers stop what they are doing to farm.** Any villager with Farming of 20 or more tries a farming job first.
     - Evidence: `0x46F25E` `cmp [0x51D34C],0xFA; jg`; `0x46F280` `0x469D70(0)` is skill ≥ 20.0 (constant `[0x498044]=20.0`) → `0x46C540(0)`.
   - **Everyone else** has a 50% chance of doing their normal job. Otherwise, unless their job is Farming or Healing, they only do "Worried about food" (behaviour 0x47).
     - Evidence: `0x46F299` `RNG(100) < 0x32`; `0x46F2A8` `cmp edi,0` / `cmp edi,2`; `0x46F2BC` `push 0x47`.
   - Offline, the same farm-first rule applies without the "worried" outcome (`0x46E985`–`0x46E9A8`). *Reached.*

10. **Farming needs the granary first. Farmers gather nothing on their own until the fence has been made into a granary (project 2).** This holds for noni, crops and fish alike.
    - Evidence: `0x46C583` `push 2; 0x43AE80; je → nothing`.
    - The granary takes 30 "Making a granary out of the fence" actions.
      - Evidence: `0x438BB3` `add [obj+8],1; cmp edi,0x1E` → complete project 2.
    - Each action is itself a Building skill check (`0x4389A2`). *Reached.*

11. **Noni picking** is offered only when more than 3 noni are on the bushes. During *offline* catch-up it also needs the Hungry Totem dismantled.
    - Evidence: `0x46C5AC` `cmp [mgr+0x17D58],3; jle`; `0x46C5B5` project 3 complete, *or* `0x46C5CA` catch-up flag == 0.
    - Villagers who dislike "berries" (#12) refuse 60% of the time (`0x46C6F3`–`0x46C717`, `RNG(100) < 0x3C`).
    - **Yield per successful action** (event 12): food += max(2, noni ÷ 100), and that much is taken off the bushes (`0x46CFCD`). The second noni behaviour 0x82 (event 13) takes min(noni, 30) (`0x46D057`).
    - The noni stock grows by 2 per periodic update (`0x425F64`) and by +20 at `0x42146B`.
    - The worker drops the job when fewer than 3 noni remain (`0x46D012`). *Reached.*

12. **Crop harvesting** needs the Hydroponic Farm restored (project 5) and at least 15 crops grown.
    - Evidence: `0x46C5DD` `cmp [mgr+0x17D5C],0xF; jl`; `0x46C5E6` project 5.
    - **Yield** (event 14, `0x46D0D0`): 7 food during catch-up. In live play it depends on game speed: 10 on Fast (3), 7 on Normal (6), 4 on Slow (10).
    - Crops are replanted to 800 (`0x439EDA`, `0x425EDB`). *Reached.*

13. **Fishing** needs the lake restored (project 10).
    - Evidence: `0x46C600` `push 0xA; 0x43AE80`.
    - Villagers who dislike fish (#33), the ocean (#17) or swimming (#37) refuse 60% of the time (`0x46C647`–`0x46C699`).
    - **Yield**: 4 food per fish (event 16, `0x46D790`). *Reached.*

14. **The game speed setting quietly changes yields.** Other fixed food events are event 11 (+8 food during catch-up; live: 11 on Fast, 8 on Normal, 5 on Slow, `0x46CF5D`), event 15 (+3), event 17 (+8) and event 18 (+55, plus a tip). Faster game speed means more food per action.
    - The behaviours that fire events 11, 15, 17 and 18 were **not identified**; they are not reached through a constant `push` before `0x474EF0`. *UNVERIFIED-REACHABILITY.*

15. **Food Mastery multiplies every food gain:** ×1 at level 1, ×1.5 (rounded down) at level 2, ×2 at level 3. This happens before the gain is stored.
    - Evidence: `0x41EB4C` `0x423600(4)`; `0x41EB5B` level 2 → `+A/2`; `0x41EB62` level 3 → `add esi,esi`. *Reached* (every food event).

16. **Eating, every 1/20 of a year, for each believer.**
    - **Above 500 food** the villager eats 2.
    - **At 500 food or below** the villager eats 2 only half the time. Otherwise there is a 30% chance of losing 1 health instead (15% overall).
    - **Extra eating.** On Hard, or at 8,000 food or more on Medium, there is a 76% chance of eating 2 more. This never happens on Easy.
    - **At 0 food** most ticks cost health.
    - Evidence: `0x472D66` `cmp [0x51D34C],0x1F4`; `0x472D7C` `RNG<50`; `0x472D8B` `RNG<30` → `0x4758F0(−1,1)`; `0x472DAA` `cmp 0x1F40` / `difficulty==2`, `0x472DC9` `difficulty!=0`, `0x472DEA` `RNG ≤ 75`; `0x472DFB` starvation branch. *Reached* (life tick).

17. **Offline catch-up work.** While the player is away, each villager gets 4 instant job ticks per missed age unit, but only if:
    - they are not sick or pregnant,
    - they are 14 or older,
    - their health is 20 or more.
    - Evidence: `0x4732E7`–`0x473326`; `0x46E8EE`–`0x46E91F` (`cmp [rec+0x1C40],0x14`). *Reached.*

### Leisure fallbacks (food above 250, nothing dispatched)

18. **A villager whose best skill is under 20 goes to behaviour 0x48 instead of working.**
    - Evidence: `0x46F308` `cmp eax,0x14`.

19. **A mediocre villager mostly idles.** If their best skill is under 50 and all six skills total under 70, they idle 95% of the time.
    - Evidence: `0x46F31F`–`0x46F347` (`0x475670` sum, `cmp 0x46`, `RNG(100) < 0x5F` → return). *Reached.*

---

## 2. Building (huts, projects, fixing)

20. **Builders never start a brand-new site. They only join a project that already shows more than 1% progress, so the player must drag a builder there first.**
    - Evidence: dispatcher case 4, `0x46C791`–`0x46CA80`. Each candidate requires `0x43AEA0(n) > 1`, the percent-complete value, which returns 0 when progress == 0 (`0x43AEA8`), and also requires "not complete".
    - On a 2,000-point hut, more than 1% means about 21 or more points. *Reached.*

21. **Hut 2 needs Construction level 2, and Hut 3 needs Construction level 3.** Their sites don't appear until then, and dragging a villager onto them earlier only makes the villager "Confused".
    - **The site appears** through each building's reveal predicate (vtable `+0x68`, run from `0x434BF0`):
      - House1 and Love Shack: any time the building is in state 4 (`0x435C00`).
      - House2: Construction > 1 (`0x4356FC` `push 3 … cmp eax,1; jle`).
      - House3: Construction > 2 (`0x43576C`).
      - Clothing Hut: **Science** > 1 (`0x4357FC`, `push 0`).
      - Nursery Hut: **Learning** > 2 (`0x4358BC`).
      - When revealed, the site is set to state 3 with 0 progress (`0x4354AF` `vt+0x44(3)`; table `0x499820` = {0, 250, 1600, 2000, 2000}).
    - **The drag handlers**, registered at `0x47A944` and `0x47A954`: `0x479FCA` Construction < 2 → Confused (0x1F); `0x47A0B7` Construction < 3 → Confused.
    - Reachability: the reveal is *Reached* (`0x434BF0` is the per-object update). The drag handlers are registered handlers, but the call into them from the drop dispatcher was not traced.

22. **How much each successful build action adds.** This is fixed per building and not tied to skill. Skill only decides whether the action succeeds (gate 7).

    | Building | Points per action | Actions for 2,000 points |
    |---|---:|---:|
    | House 1 | +12 | ~167 |
    | House 2 | +4 | 500 |
    | House 3 | +1 | 2,000 |
    | Clothing Hut | +12 | |
    | Love Shack | +400 | |
    | Nursery Hut | +50 | |

    - Evidence: `0x434D9B` loop `[obj+0x24]` times `0x43AF80` (+1 each). The constants come from the constructors: `0x4359E2` = 0xC, `0x435A62` = 4, `0x435AE2` = 1, `0x435B62` = 0xC, `0x435BE2` = 0x190, `0x435C82` = 0x32.
    - Reachability: the build step reaches `0x43B080` → vt `+0x28` = `0x434D20` (`0x473E3A`). **The House 3 rate of 1 point per action is unusual enough to confirm in play.**

23. **Builders who dislike "wood" (#30) rarely build.** Each hut or clothing/nursery option is offered to them only 16% of the time (`0x46C80B`–`0x46C829`, `RNG(100) ≤ 15`), and once building they abandon it 40% of the time (`0x463CF9`–`0x463D17`, `RNG(100) < 0x28`). *Reached.*

24. **Fixing huts** ("Examining the hut", job 0x35) is offered only when Houses 1–3 **and** the Clothing Hut are all complete. The hut to examine is then picked at random from the 3.
    - Evidence: `0x46C9E6`–`0x46CA26` (projects 19–22), `0x46CC54` `RNG(3)`. *Reached.*

25. **The statue.** Building the statue needs the statue project started and the Believer Idol (project 14) not yet finished.
    - Evidence: `0x46C96E`–`0x46C994`.
    - Villagers who dislike "rocks" (#15) refuse 90% of the time (`0x46CBD5`–`0x46CBF9`).
    - Building the granary needs it already started and below 100% (`0x46C921`, `0x4388D0`). It uses dislike #53 (shown as "owls" in the embedded list; check this mapping).
    - Repairing the aqueduct needs the Hydro Farm started, the aqueduct not yet fixed (`0x439F50`), and someone already "Directing aqueduct repair" (behaviour 0xE7), or a live-only `0x471BB0(0x1F)` count (`0x46CA80`–`0x46CAD0`). *Reached.*

26. **Food does not gate building in stock VV5** beyond the generic food gate 9.

27. **Developer-dead code.** Building options 5 and 10 in the dispatcher's jump table (`0x46CB50`, which handles dislikes plants/lifting, and `0x46CDF7`) can never be selected. No code writes the value 5 or 10 into the option list (`0x46C791`–`0x46CAD8`).

---

## 3. Breeding (making babies, pregnancy, births, believers and heathens)

28. **Only believers can have babies. Heathens never conceive through normal play;** new heathens come only from events and the starting village.
    - Evidence:
      - Heathen AI `0x46E9E0` never queues an embrace.
      - The life tick skips Heathen records (`0x472CB7` `cmp byte [rec+0x1CEC],0; je`).
      - The partner search rejects Heathens (`0x470A4A` `cmp byte [cand+0x1CEC],0; jne skip`).
      - The only callers of the pregnancy writer `0x465E00` are `0x467DBE`, `0x46E16B`, `0x46E19B` and the seeding call `0x471B6D`. *Reached.*

29. **A villager only chooses to make babies on their own if "Children" is their preferred job.** The breeding score must also be above 5, and the (score + 40)% roll must pass.
    - Evidence: `0x46A467` `cmp [rec+0x1C74],1` (score = Breeding − 15), or the preference override `0x46A56B` (score = full Breeding).
    - **Developer-dead code.** The chooser's 25% "Children without the preference" fallback at `0x46A5AA`–`0x46A5D2` can never run: job 1 can only be selected when the preference already equals 1. *Reached* chooser; the fallback is dead.

30. **The partner search** (`0x470A10`) requires all of the following:
    - Both partners: alive (health > 0), aged 18 or over (`cmp 0x168`), and opposite sex.
    - The partner (not the initiator) must be an active Believer, not sick, and **under 50** (`cmp 0x3E8`).
    - Neither partner pregnant or nursing.
    - Not the same villager, and not standing on the initiator's exact position fields.
    - **There is no family or incest check.**
    - Evidence: `0x470A30`–`0x470AE8`. *Reached* (`0x46CC99` live, `0x46E07E` offline).

31. **No babies anywhere until the Love Shack is built (project 23).** This applies to both player-dragged and autonomous embracing in live play.
    - **The live embrace step** (`0x4689A0`, step type 16) checks the following, refusing with the message id shown:
      - partner alive (0x8C)
      - opposite sex (0x7D)
      - neither sick (0x7A)
      - both 18 or over (0x82)
      - neither pregnant or nursing (0x7C)
      - **the Love Shack complete** (`0x468A69` `push 0x17; 0x43AE80; jne`, else 0x8D)
    - *Reached* (`0x473859`).

32. **A hungry village refuses to embrace.** With food at 250 or below there is a 34% refusal ("hungry", 0x79). This only applies once tutorial tip 0x2BE has been seen.
    - Evidence: `0x468A80` `RNG(100) > 0x41`, `0x468A8F` `food ≤ 0xFA`, `0x468A9B` `0x44E840(0x2BE)`.
    - The meaning "tip already seen" is inferred from `0x44E730(0x2BE)` being called on the first success.

33. **Embracing is itself a skill check:** the initiator's Breeding skill goes through the roll in gate 7 (`0x468AC2` `0x46B270(1)`, fail → "Shaking head", message 0x7E). *Reached.*

34. **Even after a successful embrace, conception is a separate roll:** `RNG(300) + 50 − 50 × Medicine level ≤ the initiator's Breeding skill`.
    - At Medicine level 1 a skill of 50 conceives about 17% of the time. At Medicine level 3 the same skill conceives about 50% of the time.
    - Evidence: `0x468B8E`–`0x468BC2` (`push 0x12C`, `imul eax,eax,0x32`, `mov ebp,0x32`).
    - **The first time this happens (before tip 0x2BE is set) it always succeeds.**
      - Evidence: `0x468B7B` `0x44E840(0x2BE); je 0x468BC4` skips the roll. *Reached.*

35. **Women of 50 or over can't conceive through embracing in live play. Men have no upper age limit.**
    - Evidence: `0x468BC4`–`0x468BE9`. Either partner aged ≥ 1000 units with sex == 1 (female) → no pregnancy. *Reached.*

36. **Population cap and huts.** The writer refuses to start a pregnancy unless the cap predicate `0x472BD0` passes (`0x465E0C`).
    - **The cap.** Believers (plus unborn babies) must be under 90 + 5 for each of the two completed collections (groups 0x68 and 0x50). Both together give +15.
      - Evidence: `0x472BDC`–`0x472C09`, `0x472C49` `add esi,0x5A`.
    - **Hut rule:**
      - 10 or more believers need at least 1 hut built.
      - 17 or more need 2.
      - 35 or more need 3.
      - Evidence: `0x472C56` `cmp ebx,0x23` / `edi ≥ 3`; `0x472C65` `0x11` / `≥ 2`; `0x472C74` `0xA` / `≥ 1`.
    - **Heathens don't count** towards either limit (`0x4713F0` counts faction-0 records only).
    - **Combined with gate 21,** a new conception is refused once the village reaches 17 believers (counting unborn babies) without Hut 2, which needs Construction level 2, and once it reaches 35 without Hut 3, which needs Construction level 3. *Reached.*

37. **The mother's Breeding skill rises** by max(5, (100 − skill) ÷ 10) at every conception.
    - Evidence: `0x465E1E`–`0x465E62`. *Reached.*

38. **Twins and triplets only happen with Medicine at level 3.** At that level twins are 5.25% and triplets 1.75%. Below level 3 a pregnancy is always a single baby.
    - Evidence: `0x465ECD` litter = 1; `0x465ED7` Medicine == 3 and `RNG(100) < 7`; `0x465EF7` Medicine == 3 and `RNG(100) < 0x19` → 3, else 2. *Reached.*

39. **Pregnancy length.** The baby is delivered once more than 40 age units (2 displayed years) have passed since conception.
    - Evidence: `0x4730AF`–`0x4730BF` (`add eax,0x28; cmp eax,[clock]`). *Reached* (life tick).

40. **Small villages balance the sexes.** With 6 or fewer believers, a newborn is forced to be the sex that has 2 or fewer members and is outnumbered.
    - Evidence: `0x4730D3` `cmp eax,6; jg`; `0x472B80` (counts via `0x4714A0`, thresholds `cmp …,2`). *Reached.*

41. **Offline catch-up skips three live rules:**
    - **the Love Shack** is not required,
    - **the over-50 woman rule** does not apply,
    - **there is no embrace skill check.**
    - What it does do: when the pick is Children, it has a 6% chance per tick (`0x46E934` `RNG(100) ≤ 5`) plus the cap predicate (`0x46E94C`). The partner is found by `0x470A10`, which still rejects partners aged 50 or over. Conception uses the same RNG(300) formula (`0x46E094`–`0x46E0C8`), and the pregnancy writer still enforces the cap.
    - **This is how older women and pre-Love-Shack villages get pregnancies while the game is closed.** *Reached* (`0x46E8E0` → `0x46E020`).

42. **Believers can lose their faith and become Heathens, which takes them out of breeding.** Belief (`+0x1CF0`, from −100 to 100) drifts each age unit for believers only. The routine is `0x468040`, called only from the life tick at `0x472D17`.
    - **Pushes belief down:**
      - food under 10: 30% chance of −1
      - food at 250 or below: 10% chance of −1
      - sick: 15% chance of −1
      - believer population under 12: a (12 − population)% chance of −1
    - **Pushes belief up:**
      - food of 8,000 or more: 20% chance of +1
      - statue: Believer Idol complete gives 30%; statue stage 1 gives 10% and stage 2 gives 20%
      - Spirituality tech: 10%, 20% or 30% at levels 1–3
      - believer population of 12 or more: a (population ÷ 5)% chance of +1
    - **Dampening:** a drop is skipped 50% of the time while belief is below 5, and a rise is skipped 70% of the time while belief is above 75.
    - **Faith flips:** when belief crosses ≤ 0, `0x4669E0` makes the villager a Heathen (`0x466880(1)`). When a Heathen's belief crosses > 0 they convert (`0x4668B0`), once the main scene sets `mgr+0x17E39` (`0x442206`).
    - Evidence: `0x468044`–`0x4681DE`; `0x467F90`.
    - *Reached* statically. **The starting belief value of believers was not established, so how often this happens in play is unknown.**

---

## 4. Healing (curing the sick, studying medicine)

43. **Healers only treat believers. A sick heathen is never chosen as a patient.**
    - Evidence: patient search `0x470B40`: health > 0, active (`0x466170(0)`), sick byte `+0x1C48` set, `+0x1CEC == 0` (`0x470B7F`), and not at the healer's position. *Reached* (`0x46CD1A`, `0x46E1A8`).

44. **When nobody is sick, healers study medicine on their own only after the Pain Totem is dismantled (project 11). Before that they do nothing.**
    - Evidence: `0x46CD24` `push 0xB; 0x43AE80; je → nothing`; `0x46CD42` behaviour 0x65 "Studying medicine". *Reached.*

45. **Dragging a villager onto the medicine spot to study needs Medicine level 2.** Such an assignment is also dropped automatically unless Healing ≥ 6 and Medicine ≥ 2.
    - Evidence: `0x47998F` `0x423600(1) … cmp eax,2; jl`; `0x46BDED`–`0x46BE0C`. Reachability: the handler is registered (`0x47A9AB`) and the continuation is *Reached*.

46. **A cure works only if the healer passes the skill check with their Healing skill. Healers who dislike "medicine" fail half the cures they would otherwise pass.**
    - **The steps:**
      - The live cure step `0x468C10` (step type 25) does the Healing skill check `0x46B270(2)` (`0x468C6E`), using the roll from gate 7.
      - If the healer dislikes #4, there is an extra `RNG(100) < 50` failure (`0x468C7B`–`0x468C99`).
      - On success the patient's sick flag is cleared (`0x468CCB`).
      - On failure the healer gets "Shaking head" (`0x468D64`).
    - **The People Cured counter** `[0x51D368]` goes up only on success in live play (`0x468D4D`). During offline catch-up it goes up even on a failed cure (`0x46E202`).
    - *Reached.*

47. **A doctor bias in burying the dead.** Once the mausoleum is restored (project 6) and a body is waiting, anyone buries it 25% of the time. Villagers with Healing of 50 or more also bury it 70% of the remaining time.
    - Evidence: `0x46F130`–`0x46F185` (`RNG(100) < 0x19`; `0x4650E0(2)` is ≥ 50.0; `RNG(100) < 0x46`). *Reached.*

48. **How often villagers fall sick.** The roll is made each age unit, in the life tick. On Easy it is made only every other unit.
    - **Medicine level 1:** 4 in 1,440. **Level 2:** 4 in 2,460. **Level 3:** 3 in 5,400.
    - **Old age** adds a 15-in-1,000 chance per unit, starting at 50, 58 or 66 years for Medicine levels 1, 2 and 3.
    - Evidence: `0x465F50`. Difficulty gate at `0x465F58`/`0x465F6B`; `RNG(0x5A0) ≤ 3`, `RNG(0x99C) ≤ 3`, `RNG(0x1518) ≤ 2`; `0x46F790` age ≥ 160 × Medicine + 840, then `RNG(1000) ≤ 14`.
    - Called at `0x472F9B` (`difficulty != 0`, or `RNG(100) ≥ 50`). *Reached.*

---

## 5. Research (tech points)

49. **During offline catch-up nobody researches until the Knowing Totem is dismantled (project 4).** In live play research is always offered.
    - Evidence: dispatcher case 3 `0x46C75E`: project 4 complete, *or* `0x46C775` catch-up flag == 0 → behaviour 4. *Reached.*

50. **Every research action is a Research skill check** (gate 7; `0x45A7A8` `push 3`). **A failed check earns nothing** (event 19 fires afterwards, at `0x45A7B1`). *Reached.*

51. **Tech points per successful action rise with Research skill and the Science level:**

    | Science level | Live play | Offline catch-up |
    |---|---|---|
    | 1 | skill ÷ 11 | skill ÷ 7 |
    | 2 | skill ÷ 9 | skill ÷ 7 |
    | 3 | skill ÷ 7 | skill ÷ 5 |

    - **Game speed.** In live play the result is divided by speed ÷ 6, which is 2× on Fast, 1× on Normal and 0.6× on Slow.
    - **Bonuses on top:**
      - Lab gear: RNG(⌊n ÷ 2⌋) more points, where n is the number of owned collection items 0x50–0x67.
      - Fire Pit: when `0x438EC0` on the Fire Pit object is true, a 10% chance of +1.
    - Evidence:
      - `0x46DC96`–`0x46DE3B`: `0x423600(0)` level switch; divisors `0x2E8BA2E9` ÷11, `0x38E38E39` ÷9, `0x92492493` ÷7, `0x66666667` ÷5.
      - `0x41ED20` = `[0x51D490+0x20]` ÷ 6.0.
      - Awards at `0x46DE48`/`0x46DE77`/`0x46DEA0` (returns `0x46DE4D`, `0x46DE7C`, `0x46DEA5`, matching `data/vv5_task9_native_actions.json`).
      - `0x413F50(0x50,…)`.
    - *Reached.*

52. **The lab is dangerous in live play.** Each research action has a 10% chance of a lab accident effect (`0x46DB8D`–`0x46DC61`) and a 2% chance of losing 3 + RNG(10) health (`0x46DC67`–`0x46DC91`). Neither happens during catch-up. *Reached.*

53. **A drag-assigned researcher** keeps the assignment only while Research ≥ 6 (`0x46BDC9`–`0x46BDD7`).
    - Directing the aqueduct repair requires a **master** in Research (≥ 88.0; `0x46BE38` → `0x41FD90(3)`). The other master-only assignment, `0x46BE67` → `0x41FD90(4)`, is for Building. *Reached.*

---

## 6. Devotion (where it gates the other activities)

54. **Villagers only choose "Honoring" as a job once the statue is at stage 1 or 2, or the Believer Idol puzzle is complete.**
    - Evidence: dispatcher case 5 `0x46CDB6`–`0x46CDF2` (project 14, or `0x4271C0` on the statue object == 1 or 2) → behaviour 0xA0.
    - Honoring is a Devotion skill check (`0x45CC9B`). Devotion gains add the Spirituality level (gate 7). *Reached.*

55. **The Retired Chief spends half of their idle checks on devotion,** split 50/50 between Honoring and Spreading the Word.
    - Evidence: `0x46F1DD` `cmp [rec+0x1CFC],0xD`; `0x46F1E6` and `0x46F1F5` `RNG(100) < 50`. *Reached.* This is the same code documented in `docs/vv5-easier-devotee-research.md`.

56. **Devotion controls faith, and faith controls breeding** (see gate 42). Spirituality and the statue raise belief; hunger, sickness and a small village lower it.

---

## Surprises (gates a player would least expect)

- **Food.**
  - No food is gathered on its own until the **fence has been made into a granary**, and that takes 30 successful building actions (gate 10).
  - **Faster game speed gives more** food and tech points per action. Fast gives about 2× the research of Normal; Slow gives 0.6× (gates 14 and 51).
- **Construction.**
  - Builders **never start a new hut on their own**; the player must kick it off (gate 20).
  - **Hut 3 gains only 1 point per build action, versus 12 for Hut 1** (gate 22).
  - Hut 2 and Hut 3 are locked behind Construction levels 2 and 3. Because of the hut rule, **breeding stops at 17 and 35 believers** until that tech is bought and those huts are built (gates 21 and 36).
- **Babies.**
  - **The Love Shack is required for every live conception.** Offline catch-up ignores that rule, and the over-50 mother rule too (gates 31 and 41).
  - **Twins and triplets are impossible below Medicine level 3** (gate 38).
  - **The very first conception is guaranteed** (gate 34).
  - **Villages of 6 or fewer believers have the baby's sex forced** to fix an imbalance (gate 40).
  - **Believers can turn Heathen** through hunger, sickness or a tiny village, which removes them from breeding and from the population cap (gate 42).
- **Skills.** A Breeding failure at skill 0 gives no +4 consolation, but every Breeding failure at a skill above 0 does. Every other skill works the other way round (gate 7).
- **Healing.**
  - **Healers never treat sick Heathens** (gate 43).
  - Offline, a failed cure still adds to **People Cured** (gate 46).
- **Developer-dead code.** The chooser's 25% Children fallback (gate 29) and building options 5 and 10 (gate 27) can never run.

## Limits of this report

- Nothing here was observed in a running game. Every "Reached" is a static call chain.
- Not identified:
  - the behaviours that fire food events 11, 15, 17 and 18
  - what `+0x1C54 == 1` and `+0x1CD6` mean
  - the full odds inside the rain handler `0x46A100`
  - the semantics of the Fire Pit predicate `0x438EC0`
  - the starting belief of believers
  - which collection is group 0x68 and which is group 0x50 (0x50 is the one the research bonus counts)
- The Difficulty value mapping (0 = Easy, 1 = Medium, 2 = Hard) is inferred from button order, not from a label read directly in code. The speed mapping (3 = Fast, 10 = Slow) follows from the ageing arithmetic and matches the repo's Time Warp research.
