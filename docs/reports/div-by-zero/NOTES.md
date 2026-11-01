# Divide-by-zero audit: working notes (all five Virtual Villagers games)

Work in progress. Saved as it goes so nothing is lost on a restart.

## Method

1. capstone linear sweep of each stock exe's .text: every `div`/`idiv`, and every call to the CRT
   64-bit helpers (found by their MSVC byte patterns):
   - A New Home: `_aulldiv` 0x44D1F0
   - The Lost Children: `_aulldiv` 0x46A270
   - The Secret City: `_aulldiv` 0x471540
   - The Tree of Life: `_alldiv` 0x477060, `_aulldiv` 0x477A70, `_allrem` 0x4779B0, `_alldvrm` 0x47F7C0
   - New Believers: `_alldiv` 0x482F10, `_aulldiv` 0x483920, `_allrem` 0x483860, `_alldvrm` 0x48A860
   Integer division counts (div + idiv): A New Home 202, The Lost Children 451, The Secret City 217,
   The Tree of Life 203, New Believers 227.  No exe imports `_controlfp`/`_control87`; the FPU
   control word is checked separately for `fldcw` sites.
2. IDA 9.4 headless (`ida_list_divisions.py`, run on a copy of the exe outside the repo): every
   function holding a division, FLIRT library flag, and Hex-Rays' division expressions with the
   divisor text.  Library (CRT) functions are listed in bulk as safe (constant radixes, time
   conversion constants, fread/fwrite element size).
3. Each variable divisor is traced to its source; reachable ones are confirmed in unicorn.

## A New Home (VV1) -- first pass (IDA listing: vv1_ida_divisions.txt)

- CRT/library: 50 division sites (`_time`, `_localtime`, `_gmtime`, `_fwrite`, `_fread`, `_cvtdate`,
  `_asctime`, float-format helpers, `_aulldiv`, `_aulldvrm`) -- safe, constants or caller sizes.
- 61 divisions by constants -- safe.
- 0x402F10 the game's rand(n): `rand() % n` only when 1 <= n <= 0x7FFF; n <= 0 takes the other
  branch (returns 0) -- safe, so every rand(count) caller is safe too.
- FPU: the only `fldcw` in A New Home, The Lost Children and The Secret City is the CRT's own
  `_controlfp` body; The Tree of Life and New Believers also have the compiler's `or 0xC00`
  (round toward zero) around `fistp`, and CRT 0x27F / 0x133F / 0x7F words -- every one keeps all
  exception mask bits set, so float division never traps.  `ldmxcsr` only in the CRT's SSE setup.
- Game speed field (village +0xA318, 41752): every write is 3, 6, 10, +999 (paused) or
  "old - 999, and 6 if that is 0" (0x41FE9B-0x41FEA7).  The divisions by it (0x42E99C, 0x42EB04)
  and by the old speed in 0x42E830 (a2 >= 999 -> 6) never see 0 -- safe.
- 0x41DA70 / 0x41EA20 / 0x41F310: 50 / (flag + 1): `setne cl; inc ecx` (0x41DAC0), so 1 or 2 -- safe.
- Sprite helpers: the column/row counts come from the constructor 0x40A070's constant arguments
  (each picture's frame layout), never a game value -- safe.
- To trace: 0x4080B0 (1000 / frame rate), 0x41DA70 / 0x41EA20 / 0x41F310 (50 / (x + 1)),
  0x42E830 and 0x42E900 (divide by the game speed field +41752 / the old speed), 0x411760,
  0x415ED0, the sprite-sheet helpers 0x409F90 / 0x40A070 / 0x40A340 / 0x4087B0 / 0x408840 /
  0x408BA0 (frame columns and rows), 0x40C450 (tile size), 0x40DF80 (read element size),
  the image scalers 0x403D70 / 0x405AD0 (pixel weights).
