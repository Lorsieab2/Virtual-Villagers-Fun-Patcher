# VV2: villagers stuck walking to the herb (root cause, by emulation of the stock exe)

Owner report: villagers get stuck studying the herb in the south-east sand area (village with all technologies 3,
dam built). Emulated: stock The Lost Children exe in Unicorn, map and state from the owner's slot 5 save COPY.
Scripts: tests/vv2_stuck_villager_emulation.py (harness and scratch fix), tests/test_vv2_stuck_villager_emulation.py.

## Findings
* The herb job that walks to the south-east herb is herb 6 (callback 0x26), queued by 0x459130 (reached from the
  drop handler 0x4306A2). Its first step is the walk (3, 1611, 1391). In stock VV2 only a villager the player drops on
  a plant studies it (the Easier Healing Mastery patch adds autonomous study), so the walk starts from wherever the
  villager is.
* Walking, 0x45E880 reads the map cell the villager is about to enter. A cell of 76 to 80 calls 0x44FCB0 (return
  0x45EB1F or 0x45ECFA) and the step is undone (the villager does not enter the cell). For cells 76..79 the handler
  queues fixed waypoints at the FRONT of the step queue (0x449B70 mode 2, shifting the queue) and restarts the front
  step (0x44FBB0). Cell 79 (rows y 1210..1219 and y 1280..1289, x 1400..1579) queues the walk (3, 1325, 1242, 0, 2, 100).
* Why it never completes: from (1325,1242) the straight walk to the herb (1611,1391) reaches (1398..1399, 1280), and
  its next step is the first band cell (x 1400, y 1280). Handler: waypoint queued again, the villager walks back
  to (1325..1327, 1242..1243), then again toward the herb, to the same pixel. Period 225 frames (7.5 s). The queue
  front is the herb walk at every hit (call chain 0x44FDF2 <- 0x45EB1F <- 0x461A7E <- 0x464EEE: the walk, the
  per-frame update); the step queue never empties, so the scheduler 0x461850 is never reached again.
  Emulation, start feet (1500,1000): 56 band hits in 5,000 frames, no scheduler call, still looping at frame 30,000
  (hits at 29353, 29578, 29803, all at (1399,1280)).
* It is a near miss of 1 to 2 pixels: whether the line from the waypoint passes x < 1400 at y 1280 depends on the
  few pixels of arrival tolerance (arrival is within +-2 of the waypoint) and the integer step phase. Starting the
  herb study at points around the waypoint: starts below and left of it stall, starts above and right pass (grid
  in the emulation notes). Other starts never touch the line: 29 of 29 non-band starts in the sample finish.
  Starts from the north of the island that cross y 1209 get 8 to 60 band hits (each frame a copy of the waypoint is
  queued while the villager slides along the line) and then either clear the y 1280 line (finish) or loop.
* Not tied to herbs: any walk whose line from the waypoint grazes the west end of the y 1280 band loops. The earlier
  emulation found it for the coconut job and crops (3 of 36 runs; the last jobs before the stall 0x460B20, 0x45F420,
  0x456F70, 0x460E70, 0x457AA0, leisure targets x 1230..1599, y 1380..1559).

## Scratch fix (emulation only, nothing installed)
Detect the loop: a new band episode (no hit for 60 frames) within 8 px of two earlier episodes. Then, instead of
the stock waypoint, queue the nearest candidate standing point (rings of 12..80 px, 16 directions) that is free by
the game's own cell read (0x4181D0: cell 0 or above 23, not 76..80) with a free straight line to it and from it to the
walk target; each candidate is tried once. When none is left: clear the step queue (the scratch version kept
the villager's +0x40/+0x44; the shipped fix calls the stock clear 0x4492A0 instead, see below).
Proof (10 tests): stalled starts (1500,1000), (1350,1050), (1540,1280), (1420,1280), (1480,1280) reach the herb
(feet within 30 px) in 1,759 to 2,123 frames; the alternate chosen is (1391,1288). Five to fifteen ordinary starts
are identical to stock step for step (frame, feet, queue front); with every alternate blocked the villager gives up
at the third loop, the queue is empty and the scheduler runs in the next frames.

## The native fix: VVFP Stuck Walks.dll (Fix Vanilla Bugs, The Lost Children)
Built as a companion DLL detour, so the exe needs no room (native/vvfp_stuck_walks/vvfp_stuck_walks.c, build
scripts/build_vvfp_stuck_walks.ps1, started by VVFP Startup.dll from its second word, shipped and pinned by the
vv2_fix_vanilla_bugs row in data/builds.json).
* Site: the band handler's entry 0x44FCB0 (8B 44 24 08 56: mov eax,[esp+8]; push esi), a jmp to the companion; the
  stub re-runs the two displaced instructions and jumps back to 0x44FCB5 for the stock path (no trampoline page).
* Detection: an approach is a band hit (cell 76..79) while the queue front is a walk (type 3) to a point that is
  NOT one of the handler's twelve waypoints. Per villager index (up to 256, kept in the DLL only), the target and
  the last four approach feet positions are remembered; a third approach to the same target within 8 px of two
  earlier ones is the loop. Hits while walking to a stock waypoint (the slides) are never counted.
* Alternate route: the nearest untried point on rings of 12, 24, 36, 48, 60, 80 px round the feet (16 directions)
  that the game's own map read 0x4181D0 calls walkable (cell 0 or above 23; 24 only for an adult, the walk's rule
  at 0x45E9E5; never 75..80) with walkable straight lines (every 3 px) feet -> point and point -> target. Queued
  with the stock push 0x449B70 (3, x, y, 0, mode 2 front, 100) and started with 0x44FBB0, exactly as the stock
  handler queues its waypoint; if the walk to the point meets the band, the next point replaces it in the front
  entry. At most 16 points.
* Give up: none left -> the game's own queue clear 0x4492A0 is called (thiscall, ecx = the village, [esp+4] = the
  villager index, ret 4: the stock give-up's convention), so the give-up is the normal stock one: the queue is emptied,
  +0x40 / +0x44 are written as stock writes them (what is carried is dropped), the handler returns without starting a
  step and the scheduler gives the villager a new job. (Owner, 2026-11-03: "drop it normal stock.")
* Composition: Improved Pathfinding detours 0x41A700 / 0x41A9B0 (the router), a different routine; the alternate
  point is walked by the stock walk, which uses the (detoured) router on a blocked cell as always.

Emulation proof (tests/test_vv2_stuck_walks_native.py, 23 tests; the companion's TEST build mapped into the stock exe
in unicorn, its site written where VvfpStartup writes it; everything is machine code):
* without the companion, start (1500,1000) never ends the study (40+ band hits, the queue front stays the walk);
* with it, the five stalled starts (1500,1000) (1350,1050) (1540,1280) (1420,1280) (1480,1280) reach the herb and
  the scheduler runs again (1,668 to 2,123 frames), with and without Improved Pathfinding installed;
* five ordinary starts are identical to stock frame for frame (frame, feet, queue front), with and without
  Improved Pathfinding; the companion counts no loop for them;
* every alternate refused (the map read answers blocked to the companion's own calls): one give-up, the scheduler
  runs, and the write to +0x44 (0x1A) comes from 0x4492A0 itself, none from the companion;
* tests/test_companion_installs_all_or_none.py: the site goes in all or none, beside the whole VV2 catalog.

## Not determined
* Live: the fix is NOT seen in a running game. To test live: The Lost Children, row vv2_fix_vanilla_bugs (Fix
  Vanilla Bugs), a village with the south-east sand open; drop a villager on the herb in the south-east sand
  (from the north of the island, or from near (1350,1050) / (1500,1000)): stock, the villager walks back and forth
  near the shore for ever; fixed, after two turn-backs it walks round and studies the herb.
* Which record field holds the carried item in VV2 is still not proven live (+0x44 by analogy with VV1's +0x3C:
  0x1A nothing, 0x0B the baby). The give-up is the stock clear, so whatever it is, it is dropped as stock drops it.
* The other four games: docs/reports/vv2-stuck-villager/other-games.md.

## Earlier notes on an in-exe fix (superseded by the companion DLL above)
* Patch mechanism: vv2_fix_vanilla_bugs is plain file-offset byte patches (offset = VA - 0x400000), rendered by
  render_patched_bytes; no compiler is installed (keystone 0.9.2 is, for assembling bytes). The rain fix used 11 bytes
  of padding. There is no padding run of 24 bytes or more in the VV2 .text; the zero slack at the end of .text
  (0x73C40..0x73FFF, VA 0x473C40) is nearly full: rendering every VV2 feature in the three modes leaves only holes
  of 14, 14, 9, 15, 24 and 14 bytes (0x73C62, 0x73C92, 0x73D77, 0x73E41, 0x73EB8, 0x73FDF); the expanded-256 modes
  also use 0x73C40..0x73F9C (modes not rendered here: their names did not resolve in my script).
* Free space can be made by re-encoding the band handler itself, 0x44FCB0..0x44FE0F (336 bytes of code plus the
  16-byte jump table at 0x44FE00, entered only from 0x45EB1A and 0x45ECF5). It queues 12 fixed waypoints in four
  cases, each as 7 pushes and a call (26 bytes); a table plus one loop is much smaller. Stock waypoints, in
  insertion order (each inserted at the front, so the last is walked first):
  case 76: (1157,647) (1190,466) (1384,323) (1510,354); case 77: (908,700) (1061,653) (1068,567);
  case 78: (887,1183) (998,1228) (1010,1434) (781,1463); case 79: (1325,1242). Each entry: 3, x, y, 0, 2, 100.
* Open problem, per-villager memory of "this approach has already been redirected": entry fields are all used
  (+0x58 of the front entry is the step timer; +0x5C is the stuck counter; +0x60 the speed); in a 60,000-frame
  emulation every record byte below 0x800 that is not persistent data (names 0x4FD..0x7EF) is written during play,
  so no free transient record byte is proven. The .data section has 0x1638 bytes of zero-initialised tail
  (VA 0x49A000..0x49B638); whether the game or another VVFP feature uses it is NOT checked. A counter keyed on the
  target walk (stored target x, y plus count) in a global table would also work and needs only that area.
