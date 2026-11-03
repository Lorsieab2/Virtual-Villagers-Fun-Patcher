# The stuck-walk class in A New Home, The Secret City, The Tree of Life and New Believers

The owner (2026-11-03): "They tend to get stuck pathfinding to things especially herbs. Would be nice to fix in
Vanilla Bugs. (All games!!!)" and "please don't drop mushrooms and collectibles and stuff if you run into things if
at all possible!!"  The Lost Children's loop and its fix: root-cause.md.  Each game's stock exe was traced by
disassembly and its walk run in unicorn with tests/farmers_emulation_vvN.py (scratch scripts, not committed).  The
key addresses below were re-read from the stock exes by disassembly (0x46FB90 VV4, 0x460F70 VV3, 0x439470 VV1,
0x473540 VV5).  The emulations ran on each harness's map (VV1 its new-village map; VV3 and VV4 their cmap.dat; VV5
its lcmap.dat), not on a real save, and nothing was seen live.

Two questions per game: (1) is there a repeat that keeps the step queue from ever emptying (The Lost Children's
band loop)?  (2) does a walk that gives up lose what the villager carries?

| Game | (1) never-ending loop | (2) give-up drops the carried item |
|---|---|---|
| A New Home | NOT FOUND | FOUND |
| The Lost Children | FOUND, fixed (VVFP Stuck Walks.dll) | the stock give-up 0x4492A0 resets +0x44; the new give-up keeps it |
| The Secret City | NOT FOUND (the band code is there but dead) | FOUND |
| The Tree of Life | NOT FOUND (the band code is there but dead) | FOUND |
| New Believers | NOT FOUND (the band code is there but dead) | FOUND |

## A New Home (VV1)
* No band handler: the walk 0x445CB0 (step runner 0x448600, type 3) reads cells with 0x414200 and compares only
  against 1, 0xE and 0x2A (all 66 calls of 0x414200 scanned); no fixed-coordinate front insert in the step chain.
* The blocked handler 0x43DFC0 (the one Improved Pathfinding detours) nudges sideways and counts in rec+0x40; past 15
  it calls the clear 0x439470 (0x43DFEE).  rec+0x40 is reset only by the scheduler (0x44823B) and at creation, so
  the cap is 15 nudges for the whole job.  A concave corner (cell-1 blocks round x 1430..1460, y 710) repeats a
  6-nudge cycle every 277 frames and ends at the 16th nudge (emulated: a villager carrying fish (8) from (1335,605)
  to (1365,1245), give-up at frame 817).  So it ends; it does not loop forever.
* The walk also clears at the map edges (0x445F3B, 0x445F71): the fishing job picks sea spots with feet x up to
  1635 but the walk clears at feet x >= 1560 (11 of 40 emulated fishing trips cleared before fishing).
* Carried item: rec+0x3C (0x13 nothing, 3 the baby; 0 berries, 6 crops, 8 fish, 0xD/0xE mushrooms; queue type 12
  sets it, 13 clears it, the draw at 0x437BC6 / 0x4383FB skips 0x13).  The clear 0x439470 zeroes the 30 queue
  entries and sets +0x3C to 0x13 (3 when nursing): the item and its reward are lost.

## The Secret City (VV3)
* The band handler exists but cannot fire: the walk 0x458760 calls 0x420610 (the cell's trigger id, bits 25..31) and
  0x422C70 on the table 0x560958, which registers only id 1 = 0x422CA0, a copy of The Lost Children's case 76
  (waypoints (1157,647) (1190,466) (1384,323) (1510,354)).  No cell of the stock cmap.dat has trigger bits (0 of
  65,536); the only writer is the map stamp 0x4203A0 (callers 0x42C710, 0x42C912, 0x42C951; whether reachable in
  play is UNCONFIRMED).  0x42D660 (the earlier scan's hit) classifies collectible ids, not map cells.
* Emulation: 130 random walks and 120 targets beside obstacles all finished; no repeat re-queue.
* Give-ups: the router failing (0x458A8C, after 0x4237C0), the follower's next point blocked (0x457992), the map
  edge (0x458975, 0x4589AF), all calling the clear 0x460F70, which calls 0x455F30(-1) (3 when nursing): the
  release listeners run and the carried item rec+0xF20 becomes -1.  A mushroom (0x64..0x66) is credited only in the
  food area (area 0xE) and a collectible (0x34..0x63) only in area 0x19; anywhere else it is gone (picked up from
  the world, never credited).  Emulated: a child carrying 0x64 or 0x40 walking to a blocked target.

## The Tree of Life (VV4)
* The band handler exists but cannot fire: both walks (0x461120 routed, 0x4614A0 direct) read the cell's area
  (0x46C430) and call 0x46FB60 on the table 0x7054CC, which registers only area 1 = 0x46FB90, a copy of The Lost
  Children's case 76 (re-read: push 0x485/0x287, 0x4A6/0x1D2, ... to 0x469050 mode 1).  Every cell of the stock
  cmap.dat has area 0 and no code writes the field.
* Emulation: 132 walks (adults, children, from the food bin, blocked targets): 0x46FB90 never ran, no stall.
  Walks at speed 300 were not tried (UNCONFIRMED).
* Give-ups (0x461303 router failed, 0x4613C6 / 0x4613FF / 0x46167E / 0x4616B7 map edge, 0x460F62 follower) call the
  clear 0x468C60, which calls 0x45ED50(-1): the carried item +0x1CDC becomes -1 through the release listeners; a
  mushroom (0x76..0x78) is credited only on the food bin (field 8).  Emulated: a mushroom carried away from the bin
  is lost; at the bin it is credited; a pregnant villager's item is replaced by 3 with no release (lost even there).

## New Believers (VV5)
* The band handler exists but cannot fire: the cell's field4 indexes the table 0x77DED4 (0x47AA60), which registers
  only index 1 (0x47AB00 -> 0x47AA90), the same four waypoints; field4 is 0 in all 102,400 cells of lcmap.dat and
  the cell writers keep or copy it.
* Emulation: 600 random adult walks finished at the exact target (one search, one path insert each).
* Give-ups (0x46950A search failed, 0x469090 next waypoint -1, 0x4695D2 / 0x46960B off the map, and the follow
  step's 0x4697BB / 0x46984C) call the clear 0x473440, which calls 0x466420(-1) (0x473556; the baby when nursing):
  the carried item +0x1D0C becomes -1.  Lab gear, relics and mushrooms are credited only in their delivery area;
  elsewhere they are gone.  Emulated with a brown mushroom (0x80): a blocked target, a child walking to water, and
  route cells blocked mid-walk all lose it.

## Not fixed here, and why
Question (1), the loop the owner saw, exists only in The Lost Children, and is fixed there.  Question (2) is a
different fix in each of the other four games and needs a decision the owner has not made: simply not resetting the
carried field does not keep the item -- the villager's next job's pick-up overwrites it with no release (VV3
0x455F30, VV4 0x45ED50, VV5 0x466420), so the item would still be lost, one job later.  Keeping it means one of:
  a. finish the delivery where the villager stands (run the job's remaining release and reward steps, as A New Home's
     emulated scratch fix did: the fish was paid at frame 821), so food is credited away from the bin; or
  b. queue a walk to the delivery area (the food bin, the collection spot) and the release step, so the item is
     delivered properly -- a new route that may fail the same way; or
  c. put the item back on the ground where the villager stands.
Which is wanted, per game, is the owner's call.  Whether the real games' mushroom and collectible spots ever fall in
blocked or child-closed cells (the trigger for these give-ups in VV3-VV5) is UNCONFIRMED.

## Keep Carried (owner decision 2026-11-03: do not drop the item; alternate routes first)

### A New Home (VV1): built, "VVFP Keep Carried.dll" (native/vvfp_keep_carried), row vv1_fix_vanilla_bugs
* The three calls of the clear 0x439470 that end a walk (0x43DFEE the nudge cap; 0x445F3B / 0x445F71 the map edge)
  go to the companion. The map-edge clears are the same mechanism: the stock nudge pushes waypoints such as
  (1685, 725), off the map, and the walk then clears at the edge (emulated: nine of the blocked starts below were
  lost that way, not by the cap).
* Held item (+0x3C not 0x13, not 3) with other steps behind the walks: the nudges' stale waypoints (the leading run
  of type-3 steps; the run's last is the real target) are dropped and a breadth-first route over the game's own map
  read 0x414200 (cells 1..14 and 0x2A block; 4 neighbours, cut to corners with free straight lines) is queued as
  walks in front, then 0x43DEF0 starts it (+0x40 = 0, +0x54 = 99). Up to four routes per walk (a state silent for
  40 s of the game clock is a new walk); no route: the stock clear.
* Emulation (tests/test_keep_carried_vv1.py, 22 tests): villager carrying fish (8) with the fish job's tail queued
  behind the walk: stock drops it (give-up frame 816, no reward); with the companion the fish is paid (food +55,
  reward 17); nine more blocked starts all lost in stock, all paid with the companion; ordinary walks identical frame
  for frame with and without Improved Pathfinding; Improved Pathfinding alone already routes the main scenario (the
  companion is then not called); nothing held, the baby, and no route are the stock behaviour.
* Not covered: the fishing trip cut at the east edge BEFORE the fish is caught (nothing is held then; the sea spots
  reach x 1635 and the walk clears at x >= 1540) -- a different bug (a trip cut short, nothing lost); the 0x2A
  give-ups inside 0x43DFC0 (0x43E08C ...) when the villager is next to that special cell. Unseen live.

### The Secret City, The Tree of Life, New Believers: built (same DLL), router call hooked

(The first version of this note said these three could not be built because the maps were missing; the maps were
found: the games' Assets\cmap.dat / lcmap.dat, copied into research/game-data/vvN, never committed.)

* Their walk asks a router (a flood from the goal over the game's own grid) when it starts; "no route" -- the goal
  cell blocked, or the villager walled in -- gives the walk up through the clear (VV3 0x460F70, VV4 0x468C60, VV5
  0x473440), which empties the queue and releases the carried item with -1. A route search of our own over the same
  grid cannot beat the router, so the alternate is a different STANDING POINT near the goal, chosen with the game's
  own router: the router CALL inside the walk step (VV3 0x458A80 -> 0x4237C0, VV4 0x4612F8 -> 0x4706B0, VV5
  0x46948F -> 0x47B640; five bytes `call`, one site per game) goes to the companion, which asks the router first.
  Only on "no route", with an item held (not -1, not 3), the front step the walk (type 3; VV5 type 4) and another
  step behind it, it asks the router about points on rings of 8 to 64 px round the goal (16 directions, nearest
  first) and writes the first routable point into the walk step's goal (step params +4/+8). The router's own state
  is then what a normal route leaves; the release step follows.
* Entry layout found: a step queue entry is [type, speed, x, y, ...] (VV3 0x2C bytes x 80, VV4 and VV5 0x58 x 80);
  the walk function receives the entry + 4. VV3 walk = type 3, release = type 0xF with the item (pusher 0x461730);
  VV4 walk = 3, item step = type 17 (0x46A646, item at entry +4); VV5 walk = 4, item steps 0x13 (-1) / 0x14.
* Emulation on the real maps (tests/test_keep_carried_routers.py, 17 tests): VV3 a mushroom (0x64) from (1300,1300)
  to the blocked point (1120,1248) next to the food area: stock gives up and releases it at (1172,1264), nothing
  credited; with the companion it is released at (1120,1264) in the food area (region 14) and 6 food is credited. VV4
  a mushroom (0x76) to the blocked point (1124,1248) of the food bin: stock releases at (1296,1299); with the
  companion at (1124,1256), inside the bin (field 8). VV5 a brown mushroom (0x80) to the blocked (1110,1170): stock
  releases at (1404,1174), the companion at (1096,1129) (43 px away: the nearest point the router reached). A goal the
  router reaches, nothing held, the baby and a walk with no step behind it are identical to stock frame for frame.
* Not emulated: VV4 and VV5 credit (the harnesses do not run the games' item-listener registrations, so the release
  runs the dispatcher with nothing registered); the VV5 delivery place of a mushroom or relic was not located, so its
  proof is "released at the alternate point, step queue intact". Not covered: the follower's own give-ups (next
  waypoint -1) and the map-edge give-ups, which are different routines. Improved Pathfinding exists only for VV1 and
  VV2 and does not touch these call sites. Unseen live.
