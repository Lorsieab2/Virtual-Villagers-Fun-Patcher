# VV5 Heathen Mommy Puzzle Restoration

## Exact inputs

- Supported modern executable: SHA-256 `92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D`, 991,232 bytes.
- Naturally enabled reference executable: SHA-256 `54D40C84E6FA82F157F70815FA6E5D72C40307F4CCCB38232FCEC30D7D13260F`, 1,253,376 bytes.

The reference is behavioral and code evidence. It is not accepted as patcher input, and none of its assets are copied into output files.

## New-game initializer comparison

The supported modern initializer is `sub_424AC0`. It makes exactly 28 calls to Heathen creator `sub_46FD20`.

The matching reference initializer begins at file offset `0x5A5F0`. Its first 21 creation sequences match the modern initializer's arguments, after address relocation. It then contains one extra, 29th creation call before resuming the remaining matching sequences.

The extra reference call is:

```text
creator(0, 1, 70, -1, 400, 0, 0, 17, -25)
```

The returned record is passed through the ordinary Heathen initialization helper. It is then used as `this` for the reference homolog of modern `sub_465E00`, with:

```text
nursing_baby(mother, 1, 1, 50, "Unknown", 2, 2, 1)
```

The final argument forces the nursing-baby setup without the ordinary population predicate. At the initial technology state it reserves one baby.

The modern initializer omits both the tag-17 mother creation and the baby call. It therefore starts a fresh village with 28 Heathens, while the naturally enabled reference starts with 29 active Heathen records plus one reserved nursing baby.

Physical demand added by the restored content is exactly two slots:

- one active mother record;
- one future child record reserved by the nursing-baby count.

## Retained modern puzzle behavior

The modern executable retains:

- RTTI and vtable for `CHeathenMommyPuzzle`;
- the constructor assigning puzzle ID `0x11`;
- behavior handlers `0xC0` and `0xC1`;
- the completion check that completes puzzle 17 when stat key `0xC1` reaches 3;
- `eTipPuzzleHeathenMommyComplete`;
- the associated mother action strings and routines;
- `puzzle_bonus_notsolved.png`, image `0x157`;
- `puzzle_bonus_solved.PNG`, image `0x158`.

The modern Puzzles screen omits the enabled reference's post-grid puzzle-17 render branch.

The modern executable does retain the complete puzzle-17 rollover branch at
`0x004493F0`. It hit-tests the seventeenth rectangle at screen-object offset
`+0x138`, checks puzzle ID `0x11`, routes an incomplete puzzle to retained
message ID `0xA7` (**This milestone has not been completed!**), and routes a
completed puzzle to retained completion-tip ID `0x2F4` (**The Heathen
Parent**). This is the direct modern homolog of the enabled reference branch
at `0x00441BCE`, which uses its build's corresponding IDs `0xA8` and `0x2F3`.
No rollover-code transplant is required; the renderer patch makes the retained
seventeenth hit target visible again. Player testing subsequently showed that
the original retained rectangle covered only the inset center of the restored
graphic, so rolling over its visible upper or left portions produced no text.
The patch now expands the rectangle's top-left corner from `(922, 501)` to the
graphic's exact draw origin `(881, 453)` while retaining its original
bottom-right corner `(1005, 615)`. The whole visible tile therefore reaches
the stock locked message or **The Heathen Parent** completion label.

## Patch

New-game restoration:

- file `0x24F69`: redirect the end of the 28-Heathen initializer to cave `0x94620`;
- file `0x94620`: create the exact tag-17 mother, run the stock initialization helper, assign the exact forced nursing baby using modern string `"Unknown"` at VA `0x004B6AA0`, then tail-jump to the stock final manager initialization.

Puzzles-screen restoration:

- file `0x48F16`: jump to cave `0x94380`;
- file `0x94380`: inspect puzzle 17's actual state, select retained image `0x157` or `0x158`, draw it at the reference coordinates, and resume the stock screen.

The naturally enabled reference uses its ordinary three-argument image drawer
at `0x00405E30` for both the background and the bonus image. The matching
function in the supported modern executable is `0x00409B90`; its normal
16-puzzle tile drawer similarly moved from reference `0x00405E80` to modern
`0x00409C20`.

Release v1.29.0 incorrectly called modern address `0x00405E30`, which is in
the middle of a different rendering function in that build. Opening the
Puzzles screen consequently produced exception `0xC0000005`. The corrected
cave calls the verified modern homolog at `0x00409B90`.

The patch affects newly created villages. It does not inject a mother into an existing save because the natural implementation is part of new-game initialization. Existing saves still receive the Puzzles-screen renderer.
