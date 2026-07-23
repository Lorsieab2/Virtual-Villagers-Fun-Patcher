# VV5 Heathen Mommy Puzzle Restoration

## Exact inputs

- Supported modern executable: SHA-256 `92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D`, 991,232 bytes.
- Naturally visible reference executable: SHA-256 `54D40C84E6FA82F157F70815FA6E5D72C40307F4CCCB38232FCEC30D7D13260F`, 1,253,376 bytes.

The reference build is evidence for the original feature. It is not accepted as a patcher input and none of its bytes or assets are copied into output files.

## What the modern build retains

The modern build still contains:

- RTTI for `CHeathenMommyPuzzle`.
- The puzzle object's vtable at VA `0x499E0C`.
- Its constructor at file offset `0x39C80`, which assigns puzzle ID `0x11` and registers behavior handlers `0xC0` and `0xC1`.
- The completion check at VA `0x439740`. When puzzle 17 is incomplete and stat key `0xC1` reaches 3, it marks puzzle 17 complete and invokes the stock completion display.
- `eTipPuzzleHeathenMommyComplete`, modern localization ID `0x2F4`.
- The "Listening to the other mothers", "Hiding her child from invaders", and "Talking mommy to mommy with heathen" action strings and their action routines.
- `puzzle_bonus_notsolved.png`, modern image ID `0x157`.
- `puzzle_bonus_solved.PNG`, modern image ID `0x158`.

The modern constructor, action handlers, completion predicate, completion write, text, and image assets all have corresponding structures in the naturally visible reference.

## Removed code

The naturally visible reference draws the standard puzzle grid, checks puzzle ID `0x11`, and then draws one retained bonus image at screen coordinates `(0x371, 0x1C5)`. The solved image is selected when puzzle 17 is complete; otherwise the not-solved image is selected.

The matching modern Puzzles-screen function has the same 1-through-16 loop but proceeds directly to the following label after the loop. Across all puzzle-manager references, the enabled build has 381 and the modern build has 380; the omitted post-loop reference is this puzzle-17 render branch.

## Patch

- File offset `0x48F16`: replace the following-screen-label load with a guarded jump to padding at `0x94380`.
- File offset `0x94380`: check stock puzzle ID `0x11`, obtain modern retained image `0x157` or `0x158`, draw it at the original coordinates, restore the displaced instruction, and return to VA `0x448F1B`.

The patch changes only visibility on the Puzzles screen. It deliberately reuses the modern executable's existing puzzle state, trigger, completion logic, strings, and image resources.
