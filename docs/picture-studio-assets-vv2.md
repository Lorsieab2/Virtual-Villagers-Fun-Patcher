# Picture Studio, Everything: The Lost Children (Virtual Villagers 2)

The module is `src/vv_assets_vv2.py`; its proofs are `tests/test_assets_vv2.py`; the game's draw routines are run
by `scripts/emulate_vv2_assets.py`, which also writes the module's `GENERATED` block. Everything was read from the
stock executable (`research/stock-executables/Virtual Villagers - The Lost Children.exe`); addresses are its own.
The framework is `src/vv_pictures_assets.py` (docs/picture-studio.md).

## How the pictures are proven

The Lost Children's sprite engine is A New Home's at other addresses (docs/picture-studio-vv2.md): the one-sheet
constructor 0x40A270 (name, cols, rows), the whole-picture constructor 0x40A0D0 (name), the grid-of-sheets
constructor 0x40A2F0 (prefix, suffix, across, down, cols, rows), the picture loader 0x40A730, the cell cut
0x40A190, the plain blit 0x403F90 and the scaled / faded blit 0x404000. Every draw call the game has goes through
thunks 0x4095A0 (whole), 0x4095C0 (a frame), 0x4095D0 (a frame with alpha), 0x409610 (a frame scaled) and the like,
which end in one of the two blitters.

A *composed* picture is the game's own draw routine run in Unicorn: each picture is a fake surface the size of the
real file (only the loader 0x40A730 is replaced), each sprite is built by the game's own constructor with the
arguments the game gives it, the routine runs on the state the picture shows, and every blit (file, cell rectangle,
place, scale, alpha byte) is recorded. The module keeps each blit as the cell of the sprite it came from, its place,
scale and alpha, and turns it back into a blit from the sheet's size alone; `DrawsMatchTheGame` runs every routine
again and requires every plan to be the game's blits, in order (`Draw.key()`).

What the emulation replaces: operator new (a heap), rand (0x4031A0, always n - 1), the clock (0x403200, 0), the
graphics object (0x408320: one whose clip holds everything, so nothing is clipped), the file-exists check 0x40A690
(yes). Nothing else of the game is stubbed in the routines below.

## Categories

### Buildings and objects, Puzzles, Plants and food, Villagers (graves): the village's scene list

The village draws its static objects from one list (0x14-byte entries at scene+0x1E0): 0x41C1D0 fills it from the
world's state each time something changes, 0x41B630 draws it in insertion order (no depth sort), a whole sprite
through 0x408820 or a frame through 0x4089B0, at (x - camera x, y - camera y). Each object below is the entries
added from its own stretch of 0x41C1D0 (the call sites to the two append helpers 0x41B580 / 0x41B5D0 inside it),
for each state it has. A state that is a number (build points, food, coconuts, crops, mosaic and thorn points) was
*swept*: 0x41C1D0 was run for every value in the range and each run of values drawing the same is one picture
(labelled with its range); the test checks each range at both ends and that the values just outside it draw
something else. A state that draws nothing is left out.

| Asset | Code (0x41C1D0 part) | World state | Pictures |
|---|---|---|---|
| The Hut (three new huts) | 0x41C1DE, 0x41C292, 0x41C347 | +0x2E814/+0x2E81C/+0x2E824 points, +0x2E818/+0x2E820/+0x2E828 done | 4 each |
| The Lovely Hut (the broken starting hut) | 0x41C6A1 | +0x2E75C points (+0x2E760 solved: nothing drawn) | 3 |
| The Hospital | 0x41C3FC | +0x2E77C points, +0x2E780 done | 4 |
| The Sewing Hut | 0x41C520 | +0x2E78C points, +0x2E790 done | 4 |
| The research table | 0x41C4DC | Science level +0x2EA7C (2 and 3) | 2 |
| The fire pit's dry grass and firewood | 0x41C5EA | bytes +0x30458, +0x30459 | 3 |
| The Exploration find (carrying.png 19 / 20) | 0x41C63A | +0x2E8A8, +0x30448, +0x3044C | 3 |
| The covered pot and the spear tips | 0x41C7CE | Exploration level +0x2EA94 >= 2 | 2 |
| The Cutting Tool (leaning spears) | 0x41C719 | +0x2E7A0 | 1 |
| The food store | 0x41C81D | food +0x2EAA4 | 3 |
| The crops | 0x41D1C1 | crops +0x2EAD8 (drawn only once the Dam is solved, +0x2E798) | 4 |
| The coconut trees | 0x41D4B3 | coconuts +0x2EACC | 7 |
| The Dam and the farm | 0x41CE20, 0x41D403 | +0x2E794 points, +0x2E798 solved | 4 |
| The Vine Wall | 0x41CD75 | +0x2E7AC points | 4 |
| The Ancient Mosaic | 0x41CE63 | +0x2E7B4 points, +0x2E7B8 solved (only once the Dam is solved) | 20 |
| The Inlaid / Sunken / Boxed Gong Pieces | 0x41C7A5, 0x41C5B8, 0x41C741 | +0x2E7D4, +0x2E7C8/+0x2E7C4, +0x2E7D0/+0x2E7BC | 1, 1, 3 |
| The Overgrown Gong Piece (the briars) | 0x41C92A | thorn points +0x2E7DC | 13 |
| The Gong of Wonder and the flowers | 0x41CB97 | +0x2E7E0 cleared, pieces +0x2E7C0/+0x2E7C8/+0x2E7D8 | 5 |
| The Scarecrow | 0x41D46B | +0x2E76C = 1, +0x2E770 solved | 2 |
| Complete collections shown in the village | 0x41C87F | the found bytes +0x2E720.. (0x426120) | 5 |
| The grave flowers | 0x41D7FD | +0x2E858 | 1 |
| The graveyard | 0x41D875 | the 50 grave records +0x2EB80 + 0x7C k (10 x 5 places, stone (value + col + row) & 3) | 3 |

The puzzle names are the game's own (its completion messages, and src/vv_game_mechanics_vv2.py /
native/vvfp_story_upgrades/story_c2.inc for the fields). The Esteemed Elder statues (totems.png) are drawn by the
villager compositor, not this list: they are listed cell by cell (8 kinds).

### Scene

* **The island** (16 tiles): 0x411FF0 builds `MapX<x>Y<y>.jpg` (x across, y down, 512 x 512, at (512x, 512y)),
  0x411F80 draws the 16 at (tile - camera). Emulated with the camera at (0, 0) and a clip that holds everything.
* The sea (shore01/02, bigwave01, medwaves01): whole pictures; 0x41B6E0 moves and fades them each frame (not
  traced).

### Collectibles

The collections screen 0x416180 draws collections_bg.jpg, then each found piece (the found byte +0x2E720 + piece)
from its collection's 4 x 3 sheet at its own place, then the Gong of Wonder's four pieces (wheel_pieces.png 2 x 2)
for +0x2E7C8, +0x2E7D8, +0x2E7C0, +0x2E7E0. Emulated for every piece alone, each collection complete, every gong
piece, and the screen empty and full (53 blits). Rarity labels are the game's pay table's (4 common, 4 uncommon,
4 rare a collection). collectables_images.png (the things on the ground, 6 x 9) is listed cell by cell.

### UI: Tech screen

0x441830 draws tech_bg.jpg, then each technology's picture (3 x 1 JPEGs: farming, medicine, exploration, building =
Engineering, science, culture): frame 0 always, frame 1 over it from level 2, frame 2 over both at level 3, at the
screen's fade alpha (+0x20; 1.0 here, +0x1C = 4, the screen settled). Emulated for each technology at levels 1-3 and
the whole screen at each level, up to 0x441D2B, where its buttons and text widgets are drawn.

### UI: Meters

* **The Villager Details bars** 0x43C470 (which 3..8, value 0..100): one 16 x 16 slice per 1/16 of the value
  (value x 256 / 100 >> 4) at x = 0x1CE + 16k; which 3..7 are the five skill bars (StatusBarSliceB.png, y 0xDF,
  0x109, 0x134, 0x15F, 0x188), 8 the health bar (healthBarbulb.png at (0x1A1, 0x58) once the value is above 0, then
  StatusBarSliceR.png at y 0x5E). Emulated at 0, 6, 7, 25, 50, 75, 99 and 100.
* **The bamboo meter** 0x4451B0 (mode, x, y, value): mode 3 draws LoadColor.png 8-pixel slices and the
  BambooMeterFrame1.png frame again after each one (the game's own order). Modes 0-2 fill the bar with a colour
  (0x4034D0, a rectangle fill, not a picture) and are left out. Emulated at 25, 50, 75, 100.

### UI: Panels and buttons

* **Dialog panels**: 0x40D050 (sprite, w, h) sizes a panel of GreenDlgTileGrid.png / OrangeDlgTileGrid.png (9 x 1
  tiles of 64), 0x40CEB0 (x, y, alpha) draws it: corner 8, the top edge 1, corner 0, then each middle row edge 3,
  middle 7, edge 2, then corner 5, bottom edge 4, corner 6. Emulated at 200 x 120, 400 x 300, 560 x 420.
* **Buttons** (13 sheets, each 3 x 1, built at 0x401732 for the 61 buttons 0x4019D0 makes): the dispatch 0x4010B0
  draws frame = the button's state +0x30, which the mouse handler 0x401780 sets: 0 the mouse away, 1 over it, 2 over
  it and pressed. Emulated through the dispatch for all three states of every sheet, at the button's own (0, 0). A
  disabled button (+0x29 = 0) is drawn by the game's own tint loop 0x408E60 (pixels blended toward a colour), not a
  blit: not drawn here.
* Check box (CheckboxStrip.png, 2 x 1), slider and handle, radio buttons: cut as built.

### Fonts and digits

ldwBurweed27.png and ldwarialbold.png: the font loader 0x402110 (name + ".png", glyph table 0x4952C0 / 0x4958A8)
wraps the table's glyph rectangles to the picture; each glyph is read back with 0x4026C0 (73 each). Emulated.
Text itself is drawn by 0x409360 through SDL; not composed here.

### Creatures

* **Birds** 0x4135C0: nine birds (+0x2C, 0x30 bytes each); a bird draws its shadow (bird_shadow.png) at (x, y + 3)
  flying or (x, y + 0x25) landed, then bird.png frame +0x24 + 2 (facing 3) or + 4 (landed, + 4 more facing 3),
  both scaled by +0x28 % through 0x409610. Emulated flying and landed, both facings, frames 0 and 1, unscaled. Which
  frames the birds' update plays is not traced.
* Dragonflies (6 x 4): cut as built.

### Effects

The 18 particle strips the effects manager's constructor builds (its calls 0x423470 .. 0x42389B) (sparkles, dust, bubbles, rainbow, fire, waterfall, foam,
spray, algae, petals, candle, waves_proto): every cell in frame order, cut as built. The particle system 0x423250
places, moves and fades them: not traced.

### Villagers

Shadow, selection circle, skelly.png (4) and ripple.png (4): cut as built; the compositor 0x445B50 that places them
is docs/picture-studio-vv2.md (the Villagers tabs).

### Screens

The splash, main menu, loading, logo, box shot, the story's three pages, help 1-4, credits, win screen, map
overview, Puzzles screen (with its 4 x 4 covers and solved pictures), collections, Tech and Villager Details
backgrounds: whole pictures, as built (only the build is proven; they are drawn at the screen's corner). The
collections screen and the Tech screen are also composed (above).

### Patcher art

* The Origins icons 101-110 (the upgrade dialogs' icons), read from inside the shipped `VVFP VV2 Origins Icons.dll`
  (each icon's largest image).
* The Origins heathen mask atlas heathen_masks.png (520 x 725, 8 x 5 cells of 65 x 145; rows Blue, Orange, Red,
  Purple, Chief; columns the head's column), read straight from inside the shipped `VVFP VV2 Origins Icons.dll`
  (RCDATA 5000; `patcher_art()` gives `(dll, 10, 5000)`, read by `vv_pictures_assets.read_patcher_art`). A patched
  game's Images also holds a copy the DLL extracts at startup: `patcher_images()` lists it, so Source sheets shows it
  as the patcher's, not as unused. Its placement on heads is proven by tests/test_pictures_vv2.py (the Villagers tabs).
* The Golden Mushroom: The Lost Children needs no new picture (its own sheet holds the art; the companion
  vvfp_golden_mushroom draws nothing for it), so none is listed.

## Unused

* Never loaded (the executable names none of them; the test scans every picture name in it): Checkbox.png,
  CheckboxChecked.png, CloudBack.png, CloudMiddle.png, Cloudfront.png, ProcessedHorizBambStrip3.png,
  ProcessedVertBambStrip1.png, StatusBar.png, bfg_logo.png, buy_button.png, detailradiobtn.png, dust.png,
  main_wide_button.png. Listed whole (Unused) and cut at their own gaps (Source sheets).
* Built, never drawn: smallwaves01.png (scene+0x1648) and stoolfood.png (scene+0x15E4) -- each field is written by
  the scene's constructor and read only where the scene is torn down (0x41B330 .. 0x41B57F) (`test_the_never_drawn_sprites`).
* SPLASH1_BG / SPLASH2_BG / SPLASH3_BG.JPG: built only if the file exists (0x40A690); the game ships none.

## The table

`sheet_table()` holds every call: 0x40A270 (107 calls; the button class's own at 0x401732), 0x40A0D0 (41; 0x40A292
is 0x40A270's own; 0x4120E2 the island's tiles), 0x40A2F0 (4: the bodies and actions grids), 0x40A730 (3: the font
loader 0x4025A9 and the two constructors'), 0x4019D0 (61 buttons) and 0x402110 (2 fonts). Six panel sites and
0x432DB7 pick one of two names by an argument; both are listed. `TableIsTheExecutables` scans the whole .text for
the calls and the names and numbers each passes; `CellCutMatchesTheGame` runs 0x40A190 on every one-sheet sprite
and every cell (and one past the last, which the cut clamps).

## Left out, and why

* The village's moving pieces: the sea (0x41B6E0), the particles (0x423250), the dragonflies' flight, the birds'
  update: their state changes every frame from rand and the clock; only their cells (and the birds' draw) are here.
* The map overview's miniature (0x41BAD0, everything at 25%), the HUD (0x4299B0), the Villager Details screen's text
  and portrait, the Puzzles screen's layout: not traced.
* Colour fills (the bamboo meter's modes 0-2) and the disabled buttons' tint: not pictures.
* Carried items (carrying.png) are another tab's; their cells are in Source sheets.
