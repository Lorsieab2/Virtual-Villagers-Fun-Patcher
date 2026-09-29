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
