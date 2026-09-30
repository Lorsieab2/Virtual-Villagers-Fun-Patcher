# Builders Fix Huts When Idle (all five games)

The owner's request: "Builders 'Fix huts' when no building projects are
present: When no building projects are present/available to be worked on
AND not all population huts are complete, then builders will fix huts to
increase their skill. (just makes it able to be autonomously chosen. applies
during catch-up time and live playing)". First asked for as default-off, then:
"make them selectable by default."

Everything below was read from the stock executables (Hex-Rays over all
five games, `research/stock-executables`).

## What the stock games do

Each game has one Building dispatcher the idle scheduler calls, live and in
catch-up, with the villager's preferred job. Examining a hut leads to fixing
it 30% of the time, and the fix ends with a practice-Building roll.

| game | dispatcher | how "fix a hut" is reached stock |
|---|---|---|
| VV1 | `0x4472C0` | after every project check fails: `rand(100) <= 20` does nothing; else `rand(3)` picks hut 9/10/11 and examines it (`0x446600`) only if that hut is complete, else nothing |
| VV2 | `0x45FBF0` | the same shape: `rand(4)` picks hut 24/25/26 (or building 5), examined (`0x45F7C0`) only if complete |
| VV3 | `0x45AF00` | an option list is built; "fix a hut" (job 86, random hut 0..2) is an option only when all four huts are complete; an empty list does nothing |
| VV4 | `0x4639B0` | as VV3: job 46, huts = projects 19..22 |
| VV5 | `0x46C540` | as VV3: job 53, huts = projects 19..22 |

So a builder whose village has no project available -- the next hut not yet
unlocked by population, everything else built -- idles in VV3-VV5 and mostly
idles in VV1-VV2.

Hut completion is read where each game keeps it: VV1 village state
`+0x9FE8/+0x9FF0/+0x9FF8`; VV2 `+0x2E818/+0x2E820/+0x2E828`; VV3 the
predicate `0x4321F0(i)`; VV4 `0x438960(19+i)` on `0x4D8BF8`; VV5
`0x43AE80(19+i)` on `0x51E008`.

## What the companion does

`native/vvfp_fix_huts/vvfp_fix_huts.c`, shipped as
`assets/fix_huts/VVFP Fix Huts.dll`, one DLL for all five games. At each
game's "nothing available" point it asks two questions: is any population
hut still incomplete, and is at least one complete? If both, it picks a
random COMPLETE hut (among the ones the stock code fixes: huts 0..2 /
9..11 / 24..26) and starts the game's own examine/fix job for it, exactly as
the stock code does when it chooses a hut, returning through the stock "job
started" epilogue. Otherwise the stock code runs unchanged.

| game | site | what is displaced |
|---|---|---|
| VV1 | `0x447724` | `push 100; call rand; add esp, 4` (the skip roll) |
| VV2 | `0x46029D` | the same |
| VV3 | `0x45B39E` | `cmp edi, ebx; je nothing` (the empty-list test) |
| VV4 | `0x463F8A` | the same |
| VV5 | `0x46CADA` | the same |

## How it is loaded

* **VV1, VV2, VV4, VV5:** a companion that already runs every frame
  (`Vv1MaskTick`, `Vv2MaskSweep`, `Vv4MaskCacheSurface`, `Vv5MaskSync`)
  loads the DLL by full path and calls `VvfpFixHutsInstall(game)`, which
  verifies the stock bytes at the site and writes the detour at run time.
  Those rows patch no executable byte.
* **VV3:** its shared Origins DLL is not rebuilt from source, so nothing of
  ours runs every frame there. The row therefore carries a small
  executable-side stub, placed by a composition overlay in the reserved zero
  range of the page Origins appends (`0x6DF800`, after the parentage overlay
  at `0x6DF400`): the site jumps to it; it replays the stock test, resolves
  `VvfpFixHutsDecide` once through the stock import table (GetModuleHandleA /
  LoadLibraryA / GetProcAddress, the VV3 parentage trampoline's shape,
  cached in `.vv3md` at `0x6E0FF8`), calls it with the dispatcher's object,
  and takes the stock "started" or "nothing" path. A failed resolution is
  remembered and the stock path runs from then on.

## Regardless of the food supply (v1.35.35)

The owner: "Builders fix huts regardless of the food supply when not all
population huts are built." Every game's idle scheduler reads the food total
before the Building dispatcher -- one scheduler, reached from both the live
per-frame caller and the catch-up loop:

| Game | Stock gate | Builder bypass (while any population hut is unbuilt) |
| --- | --- | --- |
| VV1 | `0x448336` `cmp [state+0xA2EC], 400; jge` skips the preferred-job attempt | selected job 4 (Building) -> the preferred-job attempt; installs only while Builder Action Fixes (same bytes) is off |
| VV2 | `0x4619E9` `cmp [state+0x2EAA4], 300; jge`, the same | selected job `[record+0x7F8]` 5 (Building) -> the preferred-job attempt |
| VV3 | `0x45C229`, at 250 food or less the pick (`ebx`) waits behind a farming attempt, then half the time is swapped for food action 0x76 | picked job 4 -> the stock dispatch-with-pick `0x45C271`; a second executable-side stub at page offset 0x100 of the fix-huts overlay, cache slot `0x6E0FFC` |
| VV4 | `0x4659B0`, the same after the pick (`eax`), food action 0x41 | picked job 4 -> `0x465A0F` |
| VV5 | `0x46F271`, the same, food action 0x47 | picked job 4 -> `0x46F2CE` |

Job numbers are each dispatcher's own: the case that holds the fix-huts site
is Building. In VV1 the picker's switch at `0x439CAC` confirms it (1 Farming,
2 Parenting, 3 Research, 4 Building, 5 Healing, by the skill each rates, named
from the owner's live game) -- which also showed that Builder Action Fixes
compared the selected job with 1, Farming, until v1.35.35.

Evidence: `tests/test_builders_regardless_of_food.py` runs every food stub
in an emulator over the games' own layouts (builder, non-builder, all huts
built, the exact threshold, low food, and for VV3 the companion missing),
checks every exit's registers and stack, and checks each site against the
stock executable; each assertion was mutation-checked. **TESTED.** Live play:
**UNVERIFIED** until played.

## Below Building level 3, and A New Home's false "started" (v1.35.37)

The owner, v1.35.36 installed: "how come vv1 builders stay idle doing nothing
still?" -- "In VV1 right now I only have 1 hut built. The builders should be
fixing huts."  Read live from the owner's running village: Building level
(`[state+0xA2CC]`) 2, hut 9 built, huts 10/11 not, every project flag
complete, both builders on "Nothing" for a full minute, and this companion's
check counter 0 -- the hut site `0x447724` was never reached.

* **The level gate.** Below Building level 3 the stock Building branch gives
  up at `cmp [state+0xA2CC], 3; jl` (VV1 `0x44765E`), before the hut.  The
  Lost Children has the same gate (`cmp [state+0x2EA84], 3; jl` at
  `0x4601F2`).  The owner (v1.35.38): "below level 3, at all food levels,
  villagers will fix huts if at least one is built and there are no other
  building projects available" -- every hut built included.  Below level 3
  each level stub calls its own chooser (`vv1_choose_any` /
  `vv2_choose_any`: any built population hut) and examines it directly (VV1
  `0x446600`, VV2 `0x45F7C0`) with `ebx = 1` for the stock "started"
  epilogue; with no hut built it keeps the gate's "nothing" (VV2 the gate's
  own `0x46004C`; VV1 `al = 0` after the dispatcher's pops).  The stock
  random pick (VV2's fourth option is building 5, not a hut) is never reached
  from below level 3 (Codex on #463).  The Secret City, The Tree of Life and
  New Believers have no exit before their site: a built hut is offered while
  another is unbuilt (this companion) and, once every hut is built, by the
  stock "fix a hut" option.
* **A New Home's false "started".** Every way VV1's Building branch gives up
  (`0x4474A1`, `0x4477A6`) returns `mov al, bl` with `bl = 1`: "started" with
  nothing started, so the builder stood idle and the scheduler (and Builders
  and Healers Work First's fallback) never looked further.  The hut stub now
  reports "nothing" (`xor al, al` after the dispatcher's own pops) when no hut
  stands and when the stock 20% skip roll fires.  The Lost Children and the
  later games already report "nothing" (`xor al, al`).

Evidence: `tests/test_builders_level_gate.py` runs the level stubs and A New
Home's hut stub in an emulator (level 3 continues stock; level 2 with hut 9
built fixes hut 9; no hut standing and the skip roll say "nothing" with the
dispatcher's saves popped in order), mutation-checked. **TESTED.** Live play:
**UNVERIFIED** until the owner runs v1.35.37.

## Addendum: Builders and Healers Work First (v1.35.36)

The owner: "in both low and high food situations, builders and healers still
should prioritize fixing huts over other stuff for all 5 games", as "an
addendum to the preexisting ones". Its own companion, `VVFP Work First.dll`
(`native/vvfp_work_first`), loaded by full path by this one's per-frame install
(`work_first_bridge`); five rows, each depending on this row.

Every adult idle scheduler asks one work dispatcher "start job N for this
villager". When the adult scheduler asks it for a villager whose selected job
is Healing (always -- the owner, v1.35.38: "For healers, they should study
medicine at all food levels, when they can study medicine"), or Building while
a population hut is unbuilt, the dispatcher is first asked for that own job; if it starts something the scheduler sees
"started", and if there is nothing of theirs to do the scheduler's own request
runs unchanged (Codex on #462: a first version forced the pick instead, which
left a builder or healer with nothing to do idle). At low food in VV3-VV5 the
scheduler's farming attempt is one of these calls. Only the adult scheduler's
call sites (by return address) are affected.

| Game | Dispatcher | Scheduler call returns | Selected job | Building | Healing |
| --- | --- | --- | --- | --- | --- |
| VV1 | `0x4472C0` | `0x448355`, `0x448382` | `village+i*0x3D8+0x3D0` | 4 | 5 |
| VV2 | `0x45FBF0` | `0x461A08`, `0x461A35` | `village+i*0xE48C+0x7F8` | 5 | 3 |
| VV3 | `0x45AF00` (stub in this row's page, resolves `VvfpWorkFirstFirst`) | `0x45C23C`, `0x45C27A`, `0x45C28F` | `record+0xEC0` | 4 | 2 |
| VV4 | `0x4639B0` | `0x4659D2`, `0x465A17`, `0x465A2A` | `[obj+0x1B88]+0x1C70` | 4 | 2 |
| VV5 | `0x46C540` | `0x46F291`, `0x46F2D6`, `0x46F2EA` | `[obj+0x1B88]+0x1C74` | 4 | 2 |

In VV3-VV5 the low-food bypass above also covers a healer's pick (job 2) while
the addendum is shipped.

Evidence: `tests/test_work_first.py` runs every dispatcher stub in an emulator
with the dispatcher body scripted (own job starts / starts nothing, the stock
request starts or not, other jobs, another caller, all huts built, and for VV3
the DLL missing); mutation-checked (the Building/Healing match, and the
fallback). **TESTED.** Live play: **UNVERIFIED** until played.

## Build first, fix last: The Lost Children to New Believers

The owner: "The builders will prioritize fixing huts OVER building the new
huts or other projects, when in fact they should build new stuff first, then
fix huts." A builder builds any new hut or project the stock game would let
it build or continue first; only when there is none does it fix a hut.

How builders reached a hut fix while construction stood:

| Game | Stock construction order | The way to a fix |
|---|---|---|
| VV2 | 80% (`rand(100) > 20`): own task `[record+0x7E0]` 11..20 while its project is incomplete; project 1; then 80%: hut 24 while incomplete, hut 25 (population > 22, progress >= 2), hut 26 (population > 45, progress >= 2); level >= 2, each 80%: project 17, 8, 5; level gate `0x4601F2`; level >= 3, each 80%: project 12, 11; hut site `0x46029D` | any failed roll fell through to the level gate (below level 3) or the hut site, where this companion -- or the stock `rand(4)` -- fixed a hut |
| VV3 | option list: huts 0..2 and 3 (state > 1, incomplete), projects 8, 6, 7, 3; no rolls | option 9 (fix) sits beside construction once all four huts are built, picked 1 time in n |
| VV4 | option list: huts 19..22 and projects 23, 25, 24 (state >= 1, incomplete), options 5-7; a villager with dislike item 30 (`0x45D1F0` on `record+0x1E6C`) keeps each hut/project option only on `rand(100) <= 15` | the mix above, and a list the dislike roll emptied went to this companion's fix |
| VV5 | the same with state > 1, projects 23, 24 (and option 6 behind dislike item 53), `0x464F90` on `record+0x1F68` | the same |

Project records in VV2 are (signed progress dword, complete byte) at state
`+0x2E754 + id*8`; the owner's saves (state + 4 in the `.ldw`) read hut 24 at
383/0 while it was being built and 24/1 once built, level at `+0x2EA84`.

The fix, in the companion (with the owner's option A: where a stock roll
says "not this time" but construction is available, the builder goes
STRAIGHT INTO that construction, as A New Home does):

* VV2: `vv2_construction` is the branch's own construction test without the
  rolls, in the branch's order, answering with the stock code that builds the
  first one it finds -- the instruction just after that construction's own
  test (own task: the jump-table handler with eax = `&record+0x7E0`; project
  1 `0x4600A7`; huts 24/25/26 `0x45FF0B`/`0x45FF38`/`0x45FF65`; projects 17,
  8, 5 `0x460171`/`0x4601A9`/`0x45FF92`; 12, 11 `0x46023D`/`0x46028C`). The
  hut site and the level gate jump there, so the jump always starts it.
* VV3-VV5: at the list test every list goes to `later_filter` (VV3 through the
  page stub and the export `VvfpFixHutsFilter`): option 9 is removed from a
  list holding construction; a list the dislike roll left without
  construction (empty, or only option 9) while construction stands gets back
  every option the rolls took (the dispatcher's own state tests re-asked, in
  its order: VV4 options 1-4, 6, 8, 10, 11; VV5 1-4, 6, 8, 11), and the stock
  pick starts one -- each of those handlers starts its job unconditionally;
  only with no construction at all is a hut fixed. The Secret City has no
  such rolls.

Evidence: `tests/test_builders_build_before_fixing.py` runs each game's real
dispatcher from its entry (VV3: the rendered executable with the row's page
stub) with the companion's test build and its detours in place, only the leaf
routines scripted, over 62 roll sequences per case; against v1.35.41 it
fails in every violating case, and 15 source mutations are each killed.
**TESTED.** Live play: **UNVERIFIED** until played.

## About three times in four, once per decision

The owner: the behaviour patches "should increase the LIKELIHOOD of villagers
doing that action, not 100% replace them" -- 75%, one roll per decision:
if it passes the patches act together (own work first, construction before a
fix, the hut fix when idle, the food bypasses); if it fails the stock game
decides that turn unchanged. Scope: Builders Fix Huts When Idle (all five),
Builders and Healers Work First (all five), Healers Study Plants Regardless
of Food (VV1, VV2) and Builder Action Fixes (VV1).

* The decision is one run of the game's idle scheduler, which the fix-huts
  companion wraps (VV1 `0x448220`, VV2 `0x461850`, VV4 `0x465840`, VV5
  `0x46F070` at run time; VV3 `0x45BFE0` through a fourth stub in the row's
  page, which resolves `VvfpFixHutsScheduler3` into `.vv3md` slot
  `0x6E0FEC`). The Secret City, The Tree of Life and New Believers run the
  scheduler from a retry loop (up to ten times while the villager has no job;
  counters zeroed before the loop): the loop is one decision. A New Home's and
  The Lost Children's only retry loop is a once-per-load placement pass whose
  counter is not zeroed per villager, so there each run is its own decision.
* The roll is drawn lazily, the first time a patched site would act, from
  the companion's own xorshift generator (seeded from the time-stamp counter);
  the game's RNG is never touched. Work First gets it through
  `VvfpWorkFirstSetRoll` (VV3: by module name); Healers Study looks up
  `VvfpFixHutsRoll` and, with Builders Fix Huts not selected, draws its own
  75% at its one site per run. Builder Action Fixes' exe cave rolls
  `rdtsc * 0x9E3779B9 >= 2^30`; with Builders Fix Huts loaded the companion
  verifies the row's exact jmp and cave and points the jmp at its own
  equivalent stub, which asks the shared roll.
* When the roll fails every patched site runs the stock code: the displaced
  instructions and the stock continuation, registers and stack as the stock
  code has them.

Evidence: `tests/test_builders_decision_roll.py` runs each game from its own
caller (VV1 `0x4487C8`, VV2 `0x464E9C`, VV3/VV4/VV5 their retry loops) in the
executable the patcher renders, with the three companions' test builds
installed by their own install routines: every patched site is reached and
acts on a forced pass (option A included), a forced fail matches the stock
executable call for call, one decision draws one roll, the retry loop is one
decision, and with the real generator 800 decisions per game fall within four
standard deviations of 75%. **Executes (emulated from the real callers).**
Live play: **UNVERIFIED** until played.

## Evidence

* `tests/test_builders_fix_huts.py`: the runtime sites' stock bytes equal
  the stock executables' and the written jmp lands on the DLL's stub
  (decoded in an emulator from the DLL's probe); the VV1/VV2 choosers, run
  in the emulator over a village laid out as the game keeps its flags, pick
  only complete huts and defer when none or all are complete; VV3's site
  patch replaces the exact stock test, the stub assembles to the addresses
  named, the import-table slots exist, the cache slot is unclaimed, and the
  composed image renders in every mode with the stub in place; the rows are
  on by default, registered, bundled; the four companions carry the bridge.
  **TESTED.**
* Live play: **UNVERIFIED** until played. The VV3-VV5 decision path calls
  the games' own predicates and job starters and cannot run outside the game.
