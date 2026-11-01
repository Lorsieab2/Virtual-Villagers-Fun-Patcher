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

## Carried items

Every item a villager can be drawn carrying, as offered under **Carrying** on both tabs (`src/vv_pictures_carried.py`). "Unused in the game" items are drawn with the game's own carry code, which draws any number, but nothing the game runs carries them.

| Number | Name | Status | When the game carries it (or why it never does) |
|---|---|---|---|
| 0 (0x0) | Berries | in the game | Lecturing (a random item 0-25); Researching |
| 1 (0x1) | Rock | in the game | Doing exercise; Repairing the bath; Clearing rubble |
| 2 (0x2) | Feathers | in the game | Researching; Lecturing (a random item 0-25) |
| 3 (0x3) | Baby | in the game | expecting or nursing |
| 4 (0x4) | Wood | in the game | Fixing hut; Gathering firewood; Building small hut |
| 5 (0x5) | Laundry | in the game | Washing the laundry |
| 6 (0x6) | Crops | in the game | Bringing back a prize |
| 7 (0x7) | Flowers | in the game | Honoring the Dead; Researching |
| 8 (0x8) | Fish | in the game | Fishing |
| 9 (0x9) | Crab | in the game | Fishing (1 in 10, skilled) |
| 10 (0xA) | Water | in the game | Emptying the pot; Putting water on the firepit; Cleaning up after the rain |
| 11 (0xB) | Body | in the game | Burying the dead |
| 12 (0xC) | Magic fish | in the game | Lecturing (a random item 0-25) |
| 13 (0xD) | Brown mushroom (carrying.png) | in the game | Lecturing (a random item 0-25) |
| 14 (0xE) | Red mushroom (carrying.png) | in the game | Lecturing (a random item 0-25) |
| 15 (0xF) | Kindling | in the game | Gathering dry grass; Lecturing (a random item 0-25) |
| 16 (0x10) | Coconut | in the game | Lecturing (a random item 0-25) |
| 17 (0x11) | Empty bowl | in the game | Researching; Lecturing (a random item 0-25) |
| 18 (0x12) | Tool | in the game | Lecturing (a random item 0-25) |
| 19 (0x13) | Pot | in the game | Lecturing (a random item 0-25) |
| 20 (0x14) | Full pot | in the game | Lecturing (a random item 0-25) |
| 21 (0x15) | Herbs | in the game | Lecturing (a random item 0-25) |
| 22 (0x16) | Spear tips | in the game | Lecturing (a random item 0-25) |
| 23 (0x17) | Bounty | in the game | Bringing back a prize |
| 24 (0x18) | Lab equipment 1 | in the game | Researching |
| 25 (0x19) | Lab equipment 2 | in the game | Lecturing (a random item 0-25) |
| 26 (0x1A) | Alchemy Lab piece 1 | in the game | picking up a piece of the Alchemy Lab |
| 27 (0x1B) | Alchemy Lab piece 2 | in the game | picking up a piece of the Alchemy Lab |
| 28 (0x1C) | Alchemy Lab piece 3 | in the game | picking up a piece of the Alchemy Lab |
| 29 (0x1D) | Alchemy Lab piece 4 | in the game | picking up a piece of the Alchemy Lab |
| 30 (0x1E) | Alchemy Lab piece 5 | in the game | picking up a piece of the Alchemy Lab |
| 31 (0x1F) | Tiger Lily | in the game | Gathering herbs; Doing alchemy; Studying medicine |
| 32 (0x20) | Cactus | in the game | Gathering herbs; Doing alchemy; Studying medicine |
| 33 (0x21) | Lotus | in the game | Gathering herbs; Doing alchemy; Studying medicine |
| 34 (0x22) | Black Orchid | in the game | Gathering herbs; Doing alchemy; Studying medicine |
| 35 (0x23) | Rose | in the game | Gathering herbs; Doing alchemy; Studying medicine |
| 36 (0x24) | Pitcher Plant | in the game | Gathering herbs; Doing alchemy; Studying medicine |
| 37 (0x25) | Berry Plant | in the game | Gathering herbs; Doing alchemy; Studying medicine |
| 38 (0x26) | Banana | in the game | Harvesting fruit |
| 39 (0x27) | Mango | in the game | Harvesting fruit |
| 40 (0x28) | Papaya | in the game | Harvesting fruit |
| 41 (0x29) | Honey | in the game | Harvesting honey |
| 42 (0x2A) | Lit torch | in the game | Lighting burners; Trying an idea |
| 43 (0x2B) | Bowl of junk | in the game | Cleaning up after the rain |
| 44 (0x2C) | Key 1 (diamond) | in the game | picking up a key |
| 45 (0x2D) | Key 2 (red gem) | in the game | picking up a key; Trying to reach the key |
| 46 (0x2E) | Key 3 (dark sphere) | in the game | Swapping the pearl |
| 47 (0x2F) | Shark charmer vial | in the game | Carrying vial to ocean |
| 48 (0x30) | Leaves | in the game | Clearing leaves |
| 49 (0x31) | Giant pearl | in the game | picking up the giant pearl |
| 50 (0x32) | Unlit torch | in the game | Trying an idea |
| 51 (0x33) | Irregular pearl | in the game | picking up the irregular pearl |
| 52 (0x34) | Turtle shell, common 1 | in the game | Collecting a new item! (children) |
| 53 (0x35) | Turtle shell, common 2 | in the game | Collecting a new item! (children) |
| 54 (0x36) | Turtle shell, common 3 | in the game | Collecting a new item! (children) |
| 55 (0x37) | Turtle shell, common 4 | in the game | Collecting a new item! (children) |
| 56 (0x38) | Turtle shell, uncommon 1 | in the game | Collecting a new item! (children) |
| 57 (0x39) | Turtle shell, uncommon 2 | in the game | Collecting a new item! (children) |
| 58 (0x3A) | Turtle shell, uncommon 3 | in the game | Collecting a new item! (children) |
| 59 (0x3B) | Turtle shell, uncommon 4 | in the game | Collecting a new item! (children) |
| 60 (0x3C) | Turtle shell, rare 1 | in the game | Collecting a new item! (children) |
| 61 (0x3D) | Turtle shell, rare 2 | in the game | Collecting a new item! (children) |
| 62 (0x3E) | Turtle shell, rare 3 | in the game | Collecting a new item! (children) |
| 63 (0x3F) | Turtle shell, rare 4 | in the game | Collecting a new item! (children) |
| 64 (0x40) | Coral, common 1 | in the game | Collecting a new item! (children) |
| 65 (0x41) | Coral, common 2 | in the game | Collecting a new item! (children) |
| 66 (0x42) | Coral, common 3 | in the game | Collecting a new item! (children) |
| 67 (0x43) | Coral, common 4 | in the game | Collecting a new item! (children) |
| 68 (0x44) | Coral, uncommon 1 | in the game | Collecting a new item! (children) |
| 69 (0x45) | Coral, uncommon 2 | in the game | Collecting a new item! (children) |
| 70 (0x46) | Coral, uncommon 3 | in the game | Collecting a new item! (children) |
| 71 (0x47) | Coral, uncommon 4 | in the game | Collecting a new item! (children) |
| 72 (0x48) | Coral, rare 1 | in the game | Collecting a new item! (children) |
| 73 (0x49) | Coral, rare 2 | in the game | Collecting a new item! (children) |
| 74 (0x4A) | Coral, rare 3 | in the game | Collecting a new item! (children) |
| 75 (0x4B) | Coral, rare 4 | in the game | Collecting a new item! (children) |
| 76 (0x4C) | Tablet piece, common 1 | in the game | Collecting a new item! (children) |
| 77 (0x4D) | Tablet piece, common 2 | in the game | Collecting a new item! (children) |
| 78 (0x4E) | Tablet piece, common 3 | in the game | Collecting a new item! (children) |
| 79 (0x4F) | Tablet piece, common 4 | in the game | Collecting a new item! (children) |
| 80 (0x50) | Tablet piece, uncommon 1 | in the game | Collecting a new item! (children) |
| 81 (0x51) | Tablet piece, uncommon 2 | in the game | Collecting a new item! (children) |
| 82 (0x52) | Tablet piece, uncommon 3 | in the game | Collecting a new item! (children) |
| 83 (0x53) | Tablet piece, uncommon 4 | in the game | Collecting a new item! (children) |
| 84 (0x54) | Tablet piece, rare 1 | in the game | Collecting a new item! (children) |
| 85 (0x55) | Tablet piece, rare 2 | in the game | Collecting a new item! (children) |
| 86 (0x56) | Tablet piece, rare 3 | in the game | Collecting a new item! (children) |
| 87 (0x57) | Tablet piece, rare 4 | in the game | Collecting a new item! (children) |
| 88 (0x58) | Feather, common 1 | in the game | Collecting a new item! (children) |
| 89 (0x59) | Feather, common 2 | in the game | Collecting a new item! (children) |
| 90 (0x5A) | Feather, common 3 | in the game | Collecting a new item! (children) |
| 91 (0x5B) | Feather, common 4 | in the game | Collecting a new item! (children) |
| 92 (0x5C) | Feather, uncommon 1 | in the game | Collecting a new item! (children) |
| 93 (0x5D) | Feather, uncommon 2 | in the game | Collecting a new item! (children) |
| 94 (0x5E) | Feather, uncommon 3 | in the game | Collecting a new item! (children) |
| 95 (0x5F) | Feather, uncommon 4 | in the game | Collecting a new item! (children) |
| 96 (0x60) | Feather, rare 1 | in the game | Collecting a new item! (children) |
| 97 (0x61) | Feather, rare 2 | in the game | Collecting a new item! (children) |
| 98 (0x62) | Feather, rare 3 | in the game | Collecting a new item! (children) |
| 99 (0x63) | Feather, rare 4 | in the game | Collecting a new item! (children) |
| 100 (0x64) | Brown mushroom | in the game | Picking a mushroom (children) |
| 101 (0x65) | Red mushroom | in the game | Picking a mushroom (children; 8%) |
| 102 (0x66) | Golden Mushroom | patcher | Picking a mushroom (Super-Secret Golden Mushroom) |
| 103 (0x67) | Collectables picture 52 | blank picture, unused | no code stores it |
| 104 (0x68) | Collectables picture 53 | blank picture, unused | no code stores it |
| 105 (0x69) | Collectables picture 54 | blank picture, unused | no code stores it |

The carry field is record +0xF20 (-1 = nothing); the game's own names for 0-49 are its eCarrying_* list
(the name table 0x4A89F0, used by the debug dump 0x42A607); 50 and 51 have none. Every store, read from the
stock exe:

- **Setters**: 0x455F30 (asks the item's listener 0x42CDF0 first) with 13 callers, and 0x455F70 (0x434CC3,
  the fruit picked); -1 is stored directly at 0x45610F (the record reset, also on loading), 0x4565E9,
  0x456808 and 0x45681D.
- **The action queue**: the one enqueue routine 0x460E30; action type 0xF ("PlanToCarry", helper 0x461730,
  43 callers) carries its number (0x462075 -> 0x455F30), type 0x10 carries nothing (0x4620CF). Every caller
  was resolved, with the scripts started by 0x455570 and the drop and pick-up handlers.
- **Lecturing** (0x441404) picks a random item 0-25 five times, so every carrying.png picture from 0 to 25 is
  carried; the rest of the list comes from the jobs named above (0x32, the unlit torch: "Trying an idea"
  0x44BFB1; 0x33, the irregular pearl: 0x433460).
- **Collectables**: a child dropped on a collectable or mushroom carries its number (0x449A4D, 0x449893):
  0x34-0x63 the 48 collectables (Turtle Shells, Coral, Tablet pieces, Feathers: 4 common, 4 uncommon, 4 rare
  each), 0x64 / 0x65 the brown and red mushrooms; 0x66 only with the Super-Secret Golden Mushroom patch
  (the stock spawns never write it). 0x67-0x69 are blank cells nothing stores.
- **DEAD**: the scripts 0xAB "Hiding something" and 0xAC "Spring cleaning" would carry one of 0, 1, 2, 4, 5,
  6, 15, 18, 19 or 23, but no start site uses 0xAB or 0xAC; those numbers are carried by other, live jobs.
- **The Golden Mushroom**: the item draw 0x45F7E0 draws through the world draw 0x42E510, where "VVFP Golden
  Mushroom.dll" draws golden_mushroom.png, 7 to the right, for frame 50 of the collectables sheet (the
  village's sheet and the companion's are both the resource cache 0x42E750's sprite for id 0x75). The twins'
  copies are carrying.png cells, never swapped.
- **The save** (0x45EF80 -> 0x455460) keeps +0xDC4..+0xEC4, not +0xF20: 0x456000 clears it on loading, and a
  villager expecting or nursing (+0xE8C, name + 0xB8) gets the baby back at the next AI tick (0x45C0FD) or
  queue clear (0x460FD0). The litter +0xE90 (name + 0xBC) is saved.

**Proven** by tests/test_pictures_vv3.py `test_every_carried_item`: the game's own draw, run in
Unicorn on the stock executable, blits every item above in each of the four directions and in every pose
that draws the item (walking with twins and triplets, the work poses, a child) exactly as the plan says;
for the Golden Mushroom, the plan with the patcher's picture is the stock blits with the companion's swap
(tests/carried_golden.py, the offsets read from its source). The list itself is pinned by
tests/test_pictures_carried.py.
