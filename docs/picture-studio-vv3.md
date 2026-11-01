# Picture Studio: The Secret City (Virtual Villagers 3)

`src/vv_pictures_vv3.py` draws a villager of The Secret City exactly as the game's village draw does;
`tests/test_pictures_vv3.py` proves it by running the game's own code. All addresses are the stock
executable's (`Virtual Villagers - The Secret City.exe`, SHA-256 `8BC5DB38...6503`).

## The atlases

The Secret City loads its sprites from a static resource table at `0x4A95A0` (entries of `0x30` bytes:
id, file name, columns, rows, suffix, sheets across, sheets down; looked up by `0x42E6F0`, built by
`0x42E750` with the engine's single-sheet `0x40AF10` or grid `0x40AF90` constructor). `0x45C730` puts the
villager's atlases in the village object `0x59E110`:

| field | id | atlas |
|---|---|---|
| `+0x127C34` / `+0x127C30` | `0x88` / `0x84` | `male_heads.png` / `female_heads.png`, 8 x 30 |
| `+0x127C3C` / `+0x127C38` | `0x89` / `0x85` | `male_heads_old.png` / `female_heads_old.png`, 8 x 30 |
| `+0x127C24` / `+0x127C20` | `0x8A` / `0x86` | `male_bodies` / `female_bodies`, 2 x 3 sheets, 32 x 30 |
| `+0x127C2C` / `+0x127C28` | `0x8B` / `0x87` | `male_actions` / `female_actions`, 1 x 3 sheets, 17 x 30 |
| `+0x127C1C` | `0x8D` | `peep_shadow1.png`, whole |
| `+0x127C44` / `+0x127C48` | `0x71` / `0x75` | `carrying.png` 13 x 4 / `collectables_small.png` 6 x 9 |
| `+0x127C4C` / `+0x127C50` | `0x8E` / `0x8F` | `skelly.png` 4 x 1 / `ripple.png` 4 x 1 |

Sex is `+0xDC8`: 0 male, anything else female. The cell cut (`0x40AE30`) and place-scaled (`0x408780`)
are the same code as A New Home's `0x409F90` / `0x407ED0`; the camera draws (`0x42E5E0` cell, `0x42E570`
whole image, `0x42E510` linear frame) multiply x and y by the zoom `[0x58F6F8+0x300C]` (1.0 in the village)
and pass the scale as `trunc(100 x scale)` percent, which the wrappers turn back into `percent x 0.01f`.

## The villager draw `0x4605F0`

* **Frame** `+0xEFC`: 17..24 are the walking frames, drawn from the bodies atlas at column
  `(frame - 17) + 8 x direction` (`+0xF14`, 0..3, set from the walk by `0x455500`: up-right, down-right,
  down-left, up-left); 0..16 are the actions atlas' own columns. Frames 8 (sitting) and 9 (lying) sit
  20 pixels lower (`0x4607A5`).
* **Size**: under 280 age units the body is drawn at `age x 1/700 + 0.5` (`0x455E50`) and the head at
  `(age / 14 + 80) / 100` (`0x46091E`); from 280 both are 1.0.
* **Head**: the old sheet from 1,100 units (`0x46086D`, `0x4608AE`; Change Appearance's head look moves only
  this compare), row = head `+0xDF0`, column = head facing `+0xF18` (the walk sets it to the direction; a
  random head turn may pick any of the 8), at
  `x + trunc(dx x body scale) - trunc(head scale x 20)`, `y + trunc(dy x body scale) - trunc(head scale x 27)`,
  `(dx, dy)` from the walking table `0x59E018` (by direction) or the action table `0x59E038` (by frame);
  `0x4605F0` fills both on its first call.
* **Order**: shadow (`0x42E570`, at the feet `0x455EF0` less `(34, 32) x scale`; none when `+0xF1C` is 6 or
  the height `+0xF04` is below 0; half size and 20 pixels lower while held, `+0xF12`), the carried item
  (`0x45F7E0`, `+0xF20`) when the direction is 0, 3 or 4, the body, the head, the carried item when the
  direction is 1, 2, 5, 6 or 7. The carried item is drawn again at (-5, +5) for twins and (0, +9) for
  triplets (`+0xE90`), always from `carrying.png`.
* **Swimming** (the cmap's kind 5 under the feet, not held, frame not 9): no body, the ripple (alpha 0.4,
  random frame) at the feet less 32, the head moved to the feet (`0x460B74`).
* **Dead** (health `+0xE78` at or below 0): only `skelly.png`, column `+0xDCC mod 4`, at the body scale.
* **Tribal Chief**: the robe is body 29 (`0x45FBDE`); the chief flag is `+0xE80`.

## The blitter `0x404620`

The same software blitter as A New Home's: unscaled, the cell; scaled down, box averages; surface alpha
`(a x A + 127) >> 8` with `A = trunc(alpha x 255 + 0.5)` (`vv_picture_image.blit_piece`).

## The patcher's art

* **Origins cosmetic masks**: the companion's `VV3WorldMaskDrawAt`
  (`native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c`), called by the cave at `0x460C7F`
  right after the head, draws `heathen_masks.png` (8 x 5, `assets/vv3_heathen_masks/heathen_masks.png`,
  RCDATA 5000) through the same `0x42E5E0` with the head's x, y and scale: row `mask - 1`, column
  `facing & 7`, x `+ round((-10 + (-4 for facings 0 and 1)) x head scale)`, y `+ round(-33 x head scale)`
  (32-bit floats, half away from zero). The mask comes from the companion's file, matched by identity
  (`vv_pictures_common.masks_by_rank`).
* **Head look** (Young / Old): only which head sheet is used, as `VVFP Head Look.dll` does.
* The Both Factions patch does not change how villagers are drawn (it changes technology levels, the
  herbs and the Tech screen only).

## How it is proven

`tests/test_pictures_vv3.py` runs `0x4605F0` in Unicorn on the stock executable, with the game's own
resource table, constructors (`0x45C730`), camera setter (`0x42E250(0, 0, 1.0)`), camera draws, cell cut,
place-scaled and wrappers; only the PNG loading (`0x40B3D0`, replaced by a sheet of the stock size) and the
blit (`0x404620`, recorded) are not run. The x87 runs with Windows' control word `0x027F`. Every blit
(sheet, cell rectangle, place, scale, alpha) must equal the plan:

* 1,600 adult cases (both sexes, all 25 frames, 4 directions, 8 head facings), every head and body row,
  every child age 0-279 in four frames, 1,098-1,101 and 1,600 for the old head, the dead at six ages and
  four frames, shadow on / held / off at five heights, carried items of both sheets with twins and
  triplets in every direction, 1,152 swimming cases, and 1,500 random states;
* the resource table entries and the two head-offset tables read from the game;
* the blitter run on real pixels for children's scales and the ripple's alpha.

The mask's registration is checked against the companion's C source (constants, rows, column, rounding,
the shipped atlas); it is **not** emulated through the companion DLL.

## Text (the Text tab)

The Secret City builds two bitmap fonts:

- **Arial Bold**: `ldwarialbold.png`, 1940 x 20, table 0x4A6A80, 20 pixels a line.
- **Burweed**: `ldwBurweed27.png`, 2364 x 27, table 0x4A5B78, 27 pixels a line.

They hold 0x20-0x7E and the Windows-1252 letters and signs from 0xA1 (The Secret City: 0xA2) to 0xFF, accented letters included. Bytes 0x80-0xA0 draw "!". The Text tab makes everything else in the font's style.

The game's text draw is 0x409CD0 and its centred draw is 0x40A070. They are run in Unicorn on the stock executable, and every blit is compared with the Text tab's plan (`tests/test_pictures_text.py`). See [picture-studio-text.md](picture-studio-text.md).

## Not covered

* The selection ring (`focus_circle.png`, `0x42E4B0`) and the splash particles (`0x429400`) are not drawn.
* `ghosts5.png` is drawn by a scene object (`0x4366xx`), not by the villager draw: no ghost pictures.
* The Villager Details portrait and the map are separate draws, not covered.
* Unscaled, fully opaque blits go through SDL's own blitter (`SDL_UpperBlit`), which cannot be emulated;
  the Studio composites them with standard alpha. Where several sprites overlap on the transparent canvas
  they are combined with straight-alpha "over", which is not defined by the game (it draws on the village).
* The save does not keep a villager's frame, direction, head turn, carried item or height: From my save
  draws the save's appearance (sex, age, head, body, dead, chief robe, mask, head look) in the pose picked.
