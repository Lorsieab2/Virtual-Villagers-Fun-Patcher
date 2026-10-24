# VV3 fruit-tree timing: Refill at the Same Time / Take Turns Refilling

Two owner-requested patches for The Secret City that the patcher never builds together:

* **All Fruit Trees Refill at the Same Time** (`vv3_fruit_trees_refill_together`, on by default)
* **Fruit Trees Take Turns Refilling** (`vv3_fruit_trees_take_turns`, off by default; Owner's
  Defaults ticks it instead of the other)

Everything here was read from the stock executable with capstone and checked by running the
shipped bytes in an emulator (`tests/test_vv3_fruit_tree_timing.py`,
`tests/test_vv3_fruit_tree_timing_exclusive.py`). **Not run in the game.**

## 1. The stock trees

| what | where |
|---|---|
| the trees object (game object 9) | `0x5947E0`, vtables `0x49D1D0` / `0x49D1C4`; up to 3 trees, count `+0x64` |
| one tree (0x18 bytes from `+0x1C`) | x, y, planted time, refill timer, kind, fruit |
| planting | `0x434A0D..0x434A6D`: kind, planted = clock, timer = planted, fruit 1,000, count + 1 |
| ready to pick | 28,800 s after planting (`0x434030`); the fruit job wants 10 or more (`0x45ADEA`), a pick 5 or more |
| the update | `0x434760` (vtable slot 8), run by the world objects' update `0x435880` every frame, live and after catch-up / Time Warp |
| the refill loop | `0x43478A..0x43481A`: a tree whose timer is at least 10,800 s old gains `floor(elapsed * f / 3600)`, f = 37 (Nature 0) or 42 (Nature 1+); its timer = now; every tree held to 1,000 |
| the Nature patch | `vv3_nature_honey_refill`: the test at `0x4347AA` jumps to `0x47B380` (8,100 s at Nature 1+), the factor at `0x4347CE` becomes 56 |
| a dead tree | the tail `0x43487F` ends the list at the first tree with no position, kind -1 or no planted time |
| the island event | `0x415AD0` fills grown trees to 1,000, timers untouched |
| save / load | `0x433EC0` (slot 4) writes header, records, count (0x60 bytes); `0x433E40` (slot 3) reads them; called by the world objects' save `0x435790` / load `0x435710` |
| the clock | `0x426590` on `0x5825D4`, game seconds |

Each tree has its own timer, started when it was planted, so trees refill at moments set by
when they were planted. A refill pays for the whole time since the last one, so a tree earns
37 fruit per game hour (42 / 56 with Nature) whenever it is below 1,000; the cap is the only
loss, and only while a tree is full.

## 2. Design (built)

One engine, `native/shared/vv3_fruit_timers.h`, two companions (one feature each):
`VVFP VV3 Trees Refill Together.dll` (mode 1) and `VVFP VV3 Trees Take Turns.dll` (mode 2),
started by VVFP Startup.dll (bits 26 and 27).

* **The stock timers stay stock.** The companion's pass replaces the refill loop (jump at
  `0x43478A`, on at `0x43481B`) and moves every tree's own timer exactly as the stock loop
  would. The save therefore always holds the timers the unpatched game would hold.
* **The fruit follows the patch's schedule**: per tree, `credit` (paid up to) and `due` (next
  refill). At `due` a tree gains the stock formula for `now - credit` -- same factor, same
  Nature rules, same cap -- then `credit = now`, `due = now + interval`. Every tree therefore
  earns at exactly the stock rate for exactly the time that passed; no fruit is created.
* **Laying out**: after any change the earliest due keeps its moment and the others follow it in
  the order they were due by 0 (together) or `interval / trees` (in turns). A tree not known
  yet (new, or every tree of a save without an entry) starts from its own stock timer.
* **The file**: `Save <S>\Data\Fruit Trees\Virtual Villagers 3 Fruit Tree Timers - Save <S>.dat`
  (sidecar_io.h: atomic, unreadable never replaced, invalid set aside), one entry per save
  bound by an FNV-1a fingerprint of the trees' saved bytes, last 16 kept, tagged with the
  companion's mode: switching patches starts from the stock timers. Start Over deletes it
  (`native/shared/save_reset.c`); both rows are Start Over file owners, so a build with only
  one of them still ships the reset.
* **Install**: the three sites (`0x43478A`, `0x433E40`, `0x433EC0`) must be stock and the
  interval test / factors must be the stock bytes or the Nature patch's exactly; all or none.

Why the together rule pays each tree for its own time (instead of one shared timestamp): using
the oldest tree's timestamp would pay the younger trees for time before their last refill
(extra fruit); using the newest would drop time (lost fruit). Paying each tree from its own
`credit` keeps every tree's total equal to the stock game's; only the first shared refill comes
early, with less fruit, for the trees that were not due yet. A newly planted tree's first refill
therefore comes at the others' next refill (sooner than the stock 3 hours) with the matching
smaller amount; it is full and not ready to pick for 8 hours anyway, so it changes nothing a
player sees.

## 3. Which rule gives the most fruit (simulation)

A simulation of the engine's own rules (one pass every 5 game seconds), villagers picking as fast as allowed
(a load of 4, a pick only from a tree with 10 or more, a trip of 120-300 s), three trees,
10 game days:

| Nature 0, 12 pickers | later days | longest wait with nothing to pick |
|---|---|---|
| stock, trees planted together | 2,664 / day | 166 min |
| stock, planted 20 min apart | 2,664 / day | 135 min |
| stock, planted 1 h apart | 2,664 / day | 55 min |
| Refill at the Same Time | 2,664 / day | 167 min |
| Take Turns Refilling | 2,664 / day | 55 min |

Nature 1 with the Nature patch (6 pickers): 4,032 / day for all; longest wait stock-together
88 min, together 88 min, take turns 29 min. With 1-2 pickers the trees never run dry and every
rule is the same.

* A hungry village eats exactly what the trees grow (3 x 37 x 24 = 2,664 a day at Nature 0), so
  **no rule can give more fruit per day without exceeding the stock rate**; timing only changes
  how long the village waits with nothing to pick. Taking turns gives the shortest waits.
* The suggested "timer paused while a tree is full" was simulated too (crediting only time
  below full, or holding the timer while full): it never gave more fruit -- a full tree is a
  village that is not short of fruit -- and holding the timer lost the even spacing (waits back
  to 140-167 min). So it is not used. Carrying a full tree's time over the cap would exceed the
  stock 1,000 limit and is not used either.

## 4. Composition

* `vv3_nature_honey_refill`: read, never written; its 8,100 s interval and factor 56 apply.
* `vv3_fruit_harvested_at_food_bin` (and the rain-lift fix on `fix/vv3-lift-fruit-at-bin`): the
  pick and delivery listeners `0x434A80` / `0x434C30` and `0x434C80` are not touched; they take
  fruit off the trees, which this schedule refills.
* No byte of either row is in the executable; the three run-time sites are touched by no other
  row in any mode or the 256 Villagers build.

## 5. Not verified

* Not run in the game: a real frame loop, a real save/load/quit cycle, a real file on disk.
* The emulator stubs only the clock and the planting puzzle's check.
