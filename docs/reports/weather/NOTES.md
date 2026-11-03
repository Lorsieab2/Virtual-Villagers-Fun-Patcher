# Weather crash audit (all five Virtual Villagers games)

After the divide-by-zero audit (docs/reports/div-by-zero/NOTES.md) found the rain's one
division-by-zero, the owner asked whether there is "any weather crash".  This audit reads every
weather routine in the five stock executables -- rain, storms, lightning, fog, their timers, the
weather-choice and weather-change routines, their sounds and screen effects, and the weather carried
through a save and through catch-up -- and looks at every kind of crash, not only division.

**Result: one reachable weather crash, the rain's zero-length line (The Secret City, The Tree of
Life, New Believers).  It is already fixed in Fix Vanilla Game Bugs by PR #679 (this branch builds on
it).  Every other weather routine, in all five games, is bounded and guarded; no new crash is
reachable.**  Nothing here is a new fix: the audit confirms the one known crash is covered and proves
the rest safe, with the stock routines run in unicorn where it adds to the static evidence
(tests/test_weather_no_crash.py).

## What each game has

| Game | Weather | Routines (addresses) |
|---|---|---|
| A New Home | **none** | No weather object, no rain / storm / lightning / fog draw, no alpha line drawer.  The only "rain", "fog", "thunder", "lightning" tokens are puzzle and action names in the game's data (the same list the population and parentage exports read).  Weather effects begin in The Secret City. |
| The Lost Children | **none** | Same as A New Home: no weather object and no weather rendering. |
| The Secret City | rain, storm, fog | weather object 0x4B86C4 (type +0, timer +0x14, intensity +0x2C); rain draw 0x41F5F0, rain init 0x41F269, rain object ctor/reset 0x41F720, rain tick 0x41F7D0; fog draw 0x41F8E0 (64 sprites); weather setter 0x41FB40 / 0x41F990, weather change+tick 0x41FD30, ctor 0x41FCC0; shared line drawer 0x403D20; weather clock getter 0x426590 |
| The Tree of Life | rain (Rainy Season, Monsoon), type-4 | weather object 0x6C461C; rain draw 0x46B6D0, rain init 0x46B469, rain ctor 0x46B800, rain tick 0x46B9F0, rain reset 0x46B2E0; fog/overlay 0x46B050 / 0x46B1D0 / 0x46B8C0; weather setter 0x46BC30, change+tick 0x46BE10, ctor 0x46BDA0; shared line drawer 0x404280; clock getter 0x41DB20 |
| New Believers | rain, snow/drift, lightning, storm (Tempest) | weather object 0x718EA0 (type +0, timer +0x18, intensity +0x2C); rain draw 0x476730, rain init 0x4764C0, rain ctor 0x476860, rain tick 0x476B40, rain update 0x476310; drift/particle init 0x476560, splash/effect spawner 0x41D460; lightning draw 0x41DBF0, lightning builder 0x41DDC0, lightning segment setters 0x41DD70 / 0x41DDA0; weather setter 0x477020 / 0x477030, weather change 0x477060, weather tick 0x4772B0, draw dispatch 0x476EB0, ctor 0x477240; shared line drawer 0x404210; clock getter 0x41ED40 |

The weather type is a small integer: The Secret City 0 clear, 2 rain, 3 storm, 4 fog; The Tree of
Life 0 clear, 2 rain, 4 the cold-snap/footprints type; New Believers 0 clear, 2-4, 5 storm.

## The one reachable crash (already fixed)

| Game | Site | Routine | Crash kind | Trigger | Reachable | Fixed |
|---|---|---|---|---|---|---|
| The Secret City | 0x403EC4 | line drawer 0x403D20, called by the rain 0x41F5F0 | divide by zero (#DE) | a raindrop whose point equals its previous point, so the line's two ends are the same, divides by the line's length | **yes** -- div-by-zero audit, unicorn on the stock exe | **PR #679** (this branch): a zero-length line is drawn as its one point; every other line exactly as before |
| The Tree of Life | 0x404432 | line drawer 0x404280, called by the rain 0x46B6D0 | same | same | **yes** | **PR #679** |
| New Believers | 0x4043C2 | line drawer 0x404210, called by the rain 0x476730 (and the lightning 0x41DBF0, which already skips a zero-length segment) | same | same | **yes** | **PR #679** |

The rain draws each drop as a short line from its point to where it was last frame; a drop that has
not yet moved (the first frame rain starts, before the first rain update) is a zero-length line.
Full state, reachability and the exact patch bytes are in docs/reports/div-by-zero/NOTES.md and
tests/test_no_divide_by_zero_crashes.py.  This weather audit confirms the rain is the only caller
that can reach the drawer with a zero-length line: the lightning guards it itself (below), and no
other weather routine draws a line.

## Every other weather crash kind, by game (checked, found safe)

Each row is a crash kind looked for and why the game never reaches it.  "Guard" quotes the stock
instruction that prevents it.

### New Believers (the most weather code; the others are a subset)

| Site | Routine | Crash kind looked for | Why it is safe |
|---|---|---|---|
| 0x476730 | rain draw | drop index runs past the 512-drop array (float intensity used as a loop bound) | the loop draws while `intensity*512 > index`; intensity is the weather object's +0x2C, which the weather tick 0x4772B0 clamps to [0,1] (`fld1; fcom; ...` then `fldz; fcom; ...`), so the index reaches at most 512 -- exactly the array the rain ctor 0x476860 fills (`mov edx,0x1FF` loop).  index == 512 ends the loop (`fcompp`; strictly greater continues). No overrun. |
| 0x476730 → 0x404210 | rain → line drawer | zero-length line divide | the reachable crash above; fixed by #679 |
| 0x4764C0 / 0x476860 | rain init / ctor | use before init, negative counts | the ctor zeroes all 512 drops and both camera anchors before any draw; init sets each point to `rand(800)/rand(600)` and speed `rand(2)+10 / rand(40)+20`, all positive; `rand(n)` with n>0 (the game's rand 0x403660) |
| 0x41DDC0 | lightning builder | segment-array out of bounds; rand(0)/negative; divide | the array holds 32 segments; the builder returns -1 before writing when it is full (`cmp dword[ebx+0x6A4],0x20; jl build`).  Its two `idiv`: the first by `rand(4)+2` (>=2); the second by a count clamped `cmp ecx,2; jge; mov ecx,2` (>=2).  No zero divide, no overrun. |
| 0x41DBF0 | lightning draw | zero-length segment reaches the line drawer; divide | each segment whose two ends coincide is skipped (`cmp eax,ecx; jne draw; cmp ebx,[esp+0x2C]; je skip`), so the lightning never calls the drawer with a zero-length line; segment count read from +0x6A4, bounded by the builder's 32 |
| 0x41D460 | splash/effect spawner (rain splashes) | effect-slot array out of bounds | scans 512 slots for a free one and returns -1 if none (`cmp ebp,0x200; jl`); some kinds cap at 100 (`cmp ebp,0x64; jg`); no write past the array |
| 0x476560 | drift/particle init | array overrun | a fixed `0x80` (128) loop over the object's own drift table |
| 0x477060 | weather change | type used as a jump-table index (`jmp [eax*4 + 0x47721C]`) with a bad type | guarded first (`cmp eax,5; ja 0x47714B`): a type > 5 takes no branch and changes nothing |
| 0x476EB0 / 0x4772B0 | draw dispatch / tick | same, for `type-2` into a 4-entry table | guarded (`mov eax,[esi]; add eax,-2; cmp eax,3; ja default`): any other type falls through, no wild jump |
| 0x4772B0 | weather tick | `fidiv` by the object's +0x38 (a span) | +0x38 is the weather's duration in clock units, set by the setter to a positive constant (the game's own schedule, or an island-event / story duration of 180, etc.); the tick runs only while the weather is active |
| 0x476730 / 0x4772B0 | rain, tick sounds | missing sound handle | the volume helper (0x44C360 family → 0x40C660) checks the channel: `cmp dword[eax],0; je skip` and `cmp esi,-1; je skip`, so a missing or -1 handle is a no-op |
| 0x404210 blit path | alpha blit used by fog/overlay | divide by a zero on-screen span; unclipped writes | the span divides are each guarded (`cmp ...,0; je skip`, `test eax,eax; je skip`) and the source/dest rectangles are intersected with the surface clip (0x407EE0) before any pixel is touched |

### The Tree of Life

Same routines and the same guards as New Believers, minus the lightning (The Tree of Life has no
lightning): rain draw 0x46B6D0 bound by the clamped intensity (+0x2C, clamped in 0x46BE10 / the tick)
over the 512-drop array (ctor 0x46B800, `mov ebx,0x200`); weather change 0x46BE10 type guarded
(`cmp eax,4; ja`, `jmp [eax*4+0x46C134]`); the setter 0x46BC30 guarded (`cmp eax,4; ja; jmp
[eax*4+0x46BD8C]`); `fidiv` by +0x38 duration; the shared blit and clip; sounds through the same
checked volume helper.  Rain splashes reuse the spawner at 0x467860.

### The Secret City

Rain draw 0x41F5F0 bound by the clamped intensity (+0x28/+0x2C, clamped in the tick 0x41FD30) over
the 512-drop array (ctor 0x41F720, `mov edx,0x200`); fog draw 0x41F8E0 is a fixed 64-sprite loop (no
line drawer, no divide); weather change 0x41FD30 and setter 0x41FB40 both guard the type before the
jump table (`cmp eax,5/4; ja`); `fidiv` by +0x34 duration (positive); the shared blit, clip and
sound checks.  No lightning.

## Weather from a save, and during catch-up

- **Saved/loaded weather.**  The games do not persist a live rain/lightning object; the weather
  *type* (and its timer) live in the village record that the island-event companion calls "Weather"
  (New Believers 0x718EA0, The Tree of Life 0x6C461C, The Secret City 0x4B86C4).  When that type is
  read back -- a normal save, a damaged or old save, or a save a Story / Cheat Upgrade or Custom
  Island Event has written -- it only ever reaches the game through the weather change / draw / tick
  dispatchers above, every one of which bounds the type (`cmp N; ja default`) before using it as a
  jump-table index.  A type outside 0..5 changes nothing and draws nothing; it cannot wild-jump or
  index out of range.  No weather field is a pointer, a count or a size read without a check.
- **Catch-up (time away, Time Warp, Choose Time Skip).**  Catch-up replays the villager tick, not the
  weather: no rain/lightning object is built or drawn while catching up, so none of the weather draw
  routines runs during catch-up.  The weather resumes from its (bounded) type when the game draws
  again.  The Story / Cheat Upgrades weather controls (story_c4.inc case 0/1 -> setter 0x46BC30;
  the fog/storm durations in story_tables.h) call the game's own setter with a type (0..5) and a
  positive duration, i.e. exactly what the schedule does; they add no new state and no new divide.

## The patcher's own companions

grep of native/ for weather, rain, lightning, thunder, storm, cloud, fog: the only companions that
touch weather are the Island Events / Custom Island Event and Story / Cheat Upgrades DLLs, and they
change only the weather **type** (and duration), through the game's own setter, never the rain drop
arrays, the lightning segments, the intensity or any draw.  island_event_more.inc's `weather_word`
reads the type to name it in the log; it writes nothing.  No companion can push the type out of the
range the game's dispatchers already bound, and none draws weather itself.  So no companion adds a
weather crash.

## Not checked, and why

- The weather type never seen live in a running game (The Tree of Life / New Believers type 4) was
  not named, only confirmed in range: no game was launched (the owner may be playing).  Reachability
  of a crash does not depend on its name.
- A deliberately corrupted game install (damaged picture, font or animation files) was not
  considered -- the same exclusion as the divide-by-zero audit; the patcher never changes those
  files.
- Float exceptions stay masked in every game (established in the divide-by-zero audit), so float
  division and float-to-int conversions do not trap; where a float-to-int result feeds an index
  (the rain loop bound), the index is bounded as shown above.
