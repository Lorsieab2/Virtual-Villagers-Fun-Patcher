# Improved Pathfinding (A New Home, The Lost Children)

The owner's request: "Updates the pathfinding to resemble VV3-VV5. Hopefully
villagers don't get stuck behind things anymore!" -- and, on what goes wrong:
"BOTH VV1 AND VV2 HAVE VILLAGERS GET STUCK BEHIND THINGS AND DROP IMPORTANT
STUFF."

Everything below was read from the stock executables (Hex-Rays over all five
games, `research/stock-executables`); nothing was assumed from the later
games' behaviour.

## How the games walk

All five games move a villager toward the current action's target in a
straight line, testing the walkability grid at the feet (sprite x + 20,
y + 65) one step ahead on each axis. What differs is what happens when that
step is blocked.

| game | grid | blocked | when blocked |
|---|---|---|---|
| VV1 | 168x168 DWORDs at `village+253972`, `[x/10*168 + y/10]` (`0x414200`) | 1..14 (42 = off grid) | `0x43DFC0`: nudge sideways one cell; after 15, `0x439470` clears the action queue |
| VV2 | 168x168 DWORDs at `village+15037656`, `[x/10*170 + y/10]` (`0x4181D0`) | 1..23; 24 unless the goal is on 24 | `0x41A700` floods a field from the goal, `0x44DE80` follows it with `0x41A9B0`; either failing calls `0x4492A0`, which clears the queue |
| VV3 | 256x256 DWORDs, `cmap.dat`, 8-px cells (`0x420340`) | bit 0; type 5 for children | `0x4232A0` floods from the goal, `0x423590` descends, up to 500 waypoints |
| VV4, VV5 | as VV3 | as VV3 | as VV3 |

"Drop important stuff" is the queue clear: a villager's carried item or
task lives in the action queue (VV1: thirty 24-byte entries from record
+68; entry 0 is the current action, so `[18] [19]` are its target and
`[22]` its speed), and clearing it abandons whatever they were doing.

## What the companion does

`native/vvfp_pathfinding/vvfp_pathfinding.c`, shipped as
`assets/pathfinding/VVFP Improved Pathfinding.dll`, one DLL for both games
(the parentage companion is shaped the same way).

**A New Home.** The blocked handler `0x43DFC0` is detoured. The companion
floods the game's grid from the goal (breadth-first, four neighbours, the
game's own 1..14 rule), walks the field from the villager's cell collecting
the end of every straight run -- diagonals only where both cells they pass
between are open -- and pushes those corners to the front of the action
queue as walk-tos, last corner first (`0x4399F0` with mode 2, type 3, the
villager's speed: the exact call the stock nudge makes; at most the queue's
free entries, up to twelve), starts the first (`0x43DEF0`) and forces a
re-aim (`[21] = 99`, as the stock does). Reaching each corner pops to the
next and, after the last, back to the task, so the obstacle is never met
again -- The Secret City hands its walker the whole list too. There is no
retry guard, and none is needed: the task walk's only collision test is
this same grid (`0x414200`, both axes, in `0x445CB0`), and the handler is
called from nowhere else, so nothing can block a villager that the route
does not see. While a route exists the stock handler never runs:
bumping into a hut or the side of anything is routed round (the owner:
those never count as unreachable). With no route at all -- the task's own
cell on an obstacle, or walled off -- the action ends at once through the
game's own queue clear (`0x439470`), which is what The Secret City does
(`0x460F70`), never through fifteen nudges first. The stock handler runs,
through the trampoline, only when there is no village or grid to read.

**The Lost Children.** Two routines are replaced wholesale, keeping the
game's follower and its field layout (two ints then 168x168 WORDs in the
villager's record, 1 at the goal, `0x7FFE` blocked, `0x7FFF` unreached, the
outer ring blocked):

* `0x41A700` (flood): the same rule as the stock and as The Secret City --
  a goal on a blocked cell is refused and the action ends -- but the field
  is written by the shared flood so the descent below has it.
* `0x41A9B0` (descent): the stock takes the first neighbour in a fixed
  order whose distance is smaller, cuts corners between obstacles, and
  returns -1 from a cell the flood never reached. The companion takes the
  neighbour nearest the goal, refuses the corner cut, steps into the goal
  cell last (returning the goal's exact point), and from an unreached or
  blocked cell heads for the nearest reached one within three cells.

## Install shape

No feature row patches a byte. Each game's Origins companion loads the DLL
by full path from its per-frame tick (`Vv1MaskTick`, `Vv2MaskSweep`) and
calls `VvfpPathfindingInstall(game)` once. The DLL compares every site's
stock bytes (VV1 `0x43DFC0`: `51 53 55 8B 6C 24 10`; VV2 `0x41A700`:
`B8 10 B9 01 00`, `0x41A9B0`: `B8 67 66 66 66`) before writing a jmp, all
sites or none; the displaced bytes run from a read-execute trampoline
page; the site is writable only for the write; nothing runs from DllMain.
A different build of the game installs nothing and plays as stock.

## Evidence

* `native/vvfp_pathfinding/pathfinding_harness.c` (built and run by
  `scripts/build_pathfinding_harness.ps1`, 32-bit): synthetic grids in each
  game's layout -- a wall walked round, an enclosed goal refused, a goal on
  an obstacle's edge approached then handed to the stock walk, a corner
  between two obstacles never cut, a stranded villager brought back, a
  three-wall maze threaded; for VV2 the field laid out as the follower
  reads it, a blocked goal accepted, the goal-on-24 rule kept. **TESTED.**
* `tests/test_improved_pathfinding.py`: the rows pin the DLL and change no
  bytes; each site's stock bytes are what the stock executables hold; the
  exports, the bridges in both Origins companions (and in their shipped
  DLLs), registration, bundling and documentation. **TESTED.**
* Live play in the owner's villages: **UNVERIFIED** until played.
