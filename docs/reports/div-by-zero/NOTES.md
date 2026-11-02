# Divide-by-zero audit (all five Virtual Villagers games)

The owner, in the Virtual Families chat: "Make sure the bank crash bug isnt in any game!!!"  (Virtual
Families 1's bank dialog divides by a value that is 0 when money is under $0.43 and nobody earns pay.)
This audit looks at every integer division in the five stock executables whose divisor could be 0.

Result: **one reachable division by zero, in three games** -- the engine's alpha line drawer, used by
the rain.  It is fixed in Fix Vanilla Bugs (The Secret City, The Tree of Life, New Believers).  Every
other division is safe.

## Method

1. capstone linear sweep of each `.text`: every `div` / `idiv`, and every call to the MSVC 64-bit
   helpers (found by their byte patterns):
   A New Home `_aulldiv` 0x44D1F0; The Lost Children `_aulldiv` 0x46A270; The Secret City `_aulldiv`
   0x471540; The Tree of Life `_alldiv` 0x477060, `_aulldiv` 0x477A70, `_allrem` 0x4779B0, `_alldvrm`
   0x47F7C0; New Believers `_alldiv` 0x482F10, `_aulldiv` 0x483920, `_allrem` 0x483860, `_alldvrm` 0x48A860.
   Integer divisions (div + idiv): A New Home 202, The Lost Children 451, The Secret City 217, The Tree
   of Life 203, New Believers 227.
2. IDA 9.4 headless (`ida_list_divisions.py`, run on copies of the executables outside the repo):
   every function holding a division, IDA's FLIRT library flag, and Hex-Rays' division expressions
   with their divisor (`vv1_ida_divisions.txt` ... `vv5_ida_divisions.txt` list every variable divisor).
3. Each variable divisor traced back to every write of its source; a candidate that can be 0 run in
   unicorn on the stock executable with that value at 0.
4. FPU: no executable imports `_controlfp` / `_control87`.  The only `fldcw` in A New Home, The Lost
   Children and The Secret City is the CRT's own; The Tree of Life and New Believers add the compiler's
   `or 0xC00` (round toward zero) around `fistp` and the CRT's 0x27F / 0x133F / 0x7F words.  Every one
   keeps all exception mask bits set, so float division never traps; `ldmxcsr` appears only in the
   CRT's SSE set-up.  Float division is out of scope.

## Reachable: the line drawer (The Secret City, The Tree of Life, New Believers)

| Game | Site | Routine | Divisor | Zero when | Reachable | Fixed |
|---|---|---|---|---|---|---|
| The Secret City | 0x403EC4 (`idiv ebx`; 0x403EC0 `idiv edi`) | line drawer 0x403D20, called by the rain 0x41F5F0 | max(2\|dx\|, 2\|dy\|) | the line's two ends are the same point | yes: unicorn, stock -- a zero-length line and a rain drop on its previous point fault (#DE) at 0x403EC4 | yes: 0x403EB9 sends the 2\|dy\| branch to a check at 0x4045A4 (padding): `test ebx, ebx; jz` keeps the undivided step |
| The Tree of Life | 0x404432 (0x404428) | line drawer 0x404280, called by the rain 0x46B6D0 | same | same | yes: same, faults at 0x404432 | yes: 0x404421..0x404439 rewritten in place |
| New Believers | 0x4043C2 (0x4043B8) | line drawer 0x404210, called by the rain 0x476730 and the lightning 0x41DBF0 | same | same | yes: same, faults at 0x4043C2 | yes: 0x4043B1..0x4043C9 rewritten in place |

Game state: each rain drop is a line from its point (x, y) to its previous point.  The rain
initialiser (New Believers 0x4764C0, The Tree of Life 0x46B469, The Secret City 0x41F269) sets the
point to (rand(800), rand(600)) and the speed to (rand(2)+10, rand(40)+20) but never the previous
point, which the rain object's constructor (New Believers 0x476860) zeroes.  The rain update copies
the point into the previous point and moves it, and a drop that leaves the view is reset with a
length of its speed, so a drop is zero-length only between rain starting and its first rain update,
and only if its new point equals its previous point: (0, 0) the first time rain starts in a session
(about 1 in 480,000 per drop shown).  New Believers' lightning (0x41DBF0) already skips a zero-length
segment; the rain does not.  Whether a frame is drawn between the rain starting and its first
update depends on the order of the game's update and draw calls: a weather change from another
weather starts the new rain at intensity 0 (0x477060 sets +0x2C to 0 when the old weather timer is
set), so no drop is drawn that frame; the first weather of a session gets a random intensity.  This
order was not confirmed live (no game was launched).  The fix is defensive: a zero-length line is
drawn as its one point, and every line with any length is drawn exactly as before (unicorn: same
pixels, same stack, for 17 lines x 3 alpha pairs in each game).  A New Home and The Lost Children
have no line drawer and no rain lines.

## Every other division with a variable divisor (not reachable)

### A New Home
| Site | Routine | Divisor | Why it is never 0 |
|---|---|---|---|
| 0x402F2A | rand(n) 0x402F10 | n | `n <= 0 \|\| n > 0x7FFF` takes the other branch, so every rand(count) caller is safe |
| 0x4080BB | set frame rate 0x4080B0 | frame rate | the app's virtual +0x28 (0x402FC0) returns 30 |
| 0x41DAC7, 0x41EA80, 0x41F388 | fades 0x41DA70 / 0x41EA20 / 0x41F310 | flag + 1 | `setne cl; inc ecx`: 1 or 2 |
| 0x42E877 | speed change 0x42E830 | old speed | a speed of 999 or more becomes 6; the speed field is only 3, 6, 10 or +999 |
| 0x42E99C, 0x42EB04 | village tick 0x42E900 | speed field +0xA318 | every write is 3, 6, 10, +999 (paused) or "old - 999, 6 if 0" (0x41FE9B) |
| 0x411A0C..0x411B83 | high-score digest 0x411760 | strlen(name) | the only caller skips it when the name is empty (0x4336F3 `je`) |
| sprite, tile and file helpers 0x4087B0, 0x408840, 0x408BA0, 0x409F90, 0x40A070, 0x40A0F0, 0x40A340, 0x415ED0, 0x40C450, 0x40DF80 | engine | frame columns / rows, tile size, element size | set from the game's own picture definitions and constant arguments, never a game value |
| 0x403D70, 0x405AD0 (79 sites) | image scalers | pixel weight sums | sums over a non-empty picture's pixels |

### The Lost Children
| Site | Routine | Divisor | Why it is never 0 |
|---|---|---|---|
| 0x4031BA | rand(n) 0x4031A0 | n | as A New Home |
| 0x40834B | 0x408340 | frame rate | constant 30 |
| 0x42734B, 0x4282A0, 0x42897E, 0x429338 | fades | flag + 1 | 1 or 2 |
| 0x43B5EA, 0x43B608 | speed change 0x43B5A0 | old speed | 999+ becomes 6 (0x42A00D); field only 3, 6, 10, +999 |
| 0x43B766, 0x43B8FB | village tick 0x43B690 | speed field +0x2EB08 | writes 3, 6, 10, +999, "old - 999, 6 if 0" |
| 0x41240C..0x412583 | high-score digest 0x412160 | strlen(name) | the caller 0x441300 checks `strlen != 0` first |
| 0x443CA3 | dialog layout 0x443B90 | font 0's line height | a loaded font's height |
| 0x41BAD0 (28 sites) and the same engine helpers as A New Home | sprites | frame counts | picture definitions |

### The Secret City
| Site | Routine | Divisor | Why it is never 0 |
|---|---|---|---|
| 0x4032EA | rand(n) 0x4032D0 | n | as A New Home |
| 0x40896B | 0x408960 | frame rate | constant |
| 0x425A71, 0x425A8D | two-creature scene 0x425510 | the creatures' kind (+0x2C) | only ever 100 or 50 (0x424E21, 0x4253A5, 0x425424, initialiser 0x425290) |
| 0x429BB2, 0x429BC0 | 0x429B70 | *v | checked `!= 0` first |
| 0x43223F | puzzle percent 0x432210 | total | checked `== 0` first |
| 0x4350EA | 0x4350D0 | +0xF8 | checked `!= 0` first |
| 0x435905 | puzzle percent 0x4358F0 | table 0x49D230 | constants 1..2000 |
| 0x45F437, 0x45F5C3 | village tick 0x45F3E0 | speed field +0x12F20 | writes 3, 6, 10, +999, "old - 999, 6 if 0" (0x4664A0) |
| 0x41DF3D | dialog layout 0x41DE90 | font line height | loaded font |
| 0x439760 | 0x439600 | GetDeviceCaps(LOGPIXELSY) | a display's DPI |
| 0x441033, 0x44103C, 0x441055 | animation 0x440FF0 | frame count | frames added by the game's own animation tables |
| 0x449F09 | 0x449D70 | 15 or 18 | constants |
| 0x4295D5..0x429664 and the engine helpers | sprites | frame counts | picture definitions |

### The Tree of Life
| Site | Routine | Divisor | Why it is never 0 |
|---|---|---|---|
| 0x4036EB | rand(n) 0x4036D0 | n | as A New Home |
| 0x40815B | 0x408150 | frame rate | constant |
| 0x4389C0 | puzzle percent 0x438980 | total - progress getter | every registration (0x4386A0) gives a total of 1, 3, 5 or 2000; the getter returns 0, or for the 2000 ones total - x with x != 0 |
| 0x412A46 | achievement percent 0x412A20 | goal table 0x4B8524 | every entry a nonzero constant |
| 0x41D711, 0x41D71F | 0x41D6D0 | *v | checked `!= 0` first |
| 0x43ABC3, 0x43ABFF, 0x43AC9D | scrolling text 0x43AB20 / 0x43AC20 | scroll range | 0x43A889: a constant (0x14BA + layout constants) |
| 0x43D0A3, 0x43D24D, 0x43D2B9, 0x43D5B2 | mausoleum list | row height, scroll range | its arrow buttons exist only when the range is > 0 (0x43CC6C `jle` skips them) |
| 0x4664A7, 0x466638 | village tick 0x466450 | speed field +0x17110 | writes 3, 6, 10, +999, "old - 999, 6 if 0"; the setter 0x41ACB0 is only called with 3, 6, 10, 999 |
| 0x426247 | 0x426090 | GetDeviceCaps | DPI |
| 0x44F5C7.. | animation 0x44F580 | frame count | animation tables |

### New Believers
| Site | Routine | Divisor | Why it is never 0 |
|---|---|---|---|
| 0x40367B | rand(n) 0x403660 | n | as A New Home |
| 0x4080EB | 0x4080E0 | frame rate | constant |
| 0x43AEFB | puzzle percent 0x43AEA0 | total - progress getter | 26 registrations (0x43ABB0): totals 1, 2, 30, 2000; every getter returns 0 or (0x434EF0) total - x with x != 0 |
| 0x412F36 | achievement percent 0x412F10 | goal table 0x4C6544 | every entry a nonzero constant (1 .. 1,000,000) |
| 0x41E761, 0x41E76F | 0x41E730 | *v | checked `!= 0` first |
| 0x41DDF9, 0x41DE0F | lightning builder 0x41DDC0 | rand(4) + 2; the segment count (clamped to 2 or more) | never 0 |
| 0x41BC56 | dialog layout 0x41BBA0 | font line height | loaded font |
| 0x43D4B3, 0x43D4EF, 0x43D58D | scrolling text 0x43D410 / 0x43D510 | scroll range, track | 0x43D14C: 0x161E + constants; 0x43D510 also checks `> 0` |
| 0x43F972, 0x43FB1D, 0x43FBB8, 0x43FE8D | mausoleum 0x43F130 | row height, scroll range +0x68, track | the arrow buttons (ids 1 and 2, handler 0x43FF30) are created only when +0x68 > 0 (0x43F4C0) and removed on leaving; the drag needs +0x68 > 0 too |
| 0x45042C, 0x4504C3 | bar 0x450380 | the bar's maximum | clamped to 10..1000 first |
| 0x4735AB | 0x473590 | +0x1CC8 | only ever 1 or 10 |
| 0x46FEE3, 0x470071 | village tick 0x46FE90 | speed field +0x17D7C | writes 3, 6, 10, +999, "old - 999, 6 if 0"; the setter 0x41B500 is only called with 3, 6, 10, 999 |
| 0x4262AB | speed change 0x426260 | old speed | 999+ becomes 6 |
| 0x42BEB7 | 0x42BD00 | GetDeviceCaps | DPI |
| 0x452A77, 0x452A80, 0x452A9B | animation 0x452A30 | frame count (+0xE0) | 0 at creation, +1 per frame added (0x451FB5) by the game's tables |
| 0x45C264 | 0x45C140 | 15 or 18 | constants |
| the engine helpers (0x404C40, 0x4068B0, 0x4088D0.., 0x409F00, 0x40AE90.., 0x40DF20, 0x40FB00, 0x41D750, 0x41D7D0) | sprites, text wrap (checked), tiles, files | picture definitions, constants | |

## Safe in bulk

- Divisions by constants: A New Home 61, The Lost Children 336, The Secret City 72, The Tree of Life 30,
  New Believers 72 Hex-Rays expressions (rand() % constant, / 60, % 20 ...).
- CRT (IDA FLIRT library functions, plus the same routines in The Tree of Life where FLIRT names them
  differently): `_time`, `_gmtime(64)`, `_localtime(64)`, `_asctime`, `_cvtdate`, `_fread`, `_fwrite`,
  the float formatters (`__cftoe`, `__cftoa_l`, `__ShrMan` ...) and printf's radix divisions: constant
  divisors (31536000, 86400, 3600, 60, 10, 8, 16) or the element size the caller passes.  Every
  `_alldiv` / `_aulldiv` / `_allrem` / `_alldvrm` call in all five games is inside these CRT routines.

## Not checked, and why

- The CRT's internals were classified by FLIRT and constant divisors, not traced call by call.
- Picture, font and animation definitions: their frame counts and sizes come from the game's own
  files and tables, which the patcher never changes; a damaged game install was not considered.
- Whether the game draws a frame between rain starting and its first rain update (the last condition
  for the rain crash) was not confirmed in a running game: no game was launched.
- The patcher's own companion DLLs (not the stock executables) were not part of this audit.
- Float division (x87 exceptions stay masked in every game).
