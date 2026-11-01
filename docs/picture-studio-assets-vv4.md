# Picture Studio "Everything": The Tree of Life (VV4)

`src/vv_assets_vv4.py` gives the Everything tab every picture The Tree of Life ships and the things the game
assembles from them. `tests/test_assets_vv4.py` proves each rule against the stock executable
(`research/stock-executables/Virtual Villagers - The Tree of Life.exe`), running the game's own code in Unicorn
(`tests/story_emulator.Process`) down to its blits. A blit is recorded at the two blitters every sprite draw ends
in, 0x404CB0 (scaled / faded) and 0x404C40 (plain); reaching any other blitter (0x404770, 0x404830, 0x4046F0,
0x404280) fails the test. Every recorded blit must equal the module's plan, in order (`Draw.key()`: file, cell,
place, scale, surface alpha).

The emulation runs the game's own sprite registry and constructors. Only these are answered by the test: the file
reader 0x40B050 (a sheet's surface: the real picture's width and height, from `research/game-images`), operator new
0x470C5C, free 0x470B7B, sprintf 0x4716DB, the file check 0x40AF70, and the registry object 0x44CCF0.

## How the game builds its pictures

The sprite table at 0x4C07C8 (305 entries of 0x30 bytes: id, name, columns, rows, suffix, sheets across, sheets
down, then the registry's cached objects) is the source of almost every picture. The registry (0x44CB80 by id,
0x44C8A0 to find an entry, bounded by 0x4C40F8) builds an entry on first use:

| Columns, rows | Built by | Cut |
|---|---|---|
| 0, 0 | 0x40A840 (ldwImage) | the whole picture |
| n, 0 | 0x44C8F0 -> 0x401010 = 0x40AB10(name, n, 1) (ldwImageStrip) | n frames side by side: the buttons |
| c, r (no sheets) | 0x40AB10(name, c, r) (ldwImageGrid) | width / c by height / r |
| c, r, sheets a x d | 0x40ABA0(name, suffix, a, d, c, r) | a grid of sheets name + x + y + suffix |

Outside the table the exe builds: the 16 island map tiles `MapX<x>Y<y>.jpg` (0x46FCE0, sprintf of
`%sX%01dY%01d.jpg` with "Map", whole), SPLASH_BG.JPG and SPLASH1-3_BG.JPG (0x4466A4 - 0x446779, whole),
menu_logo.png and loading_logo.png (0x42079B, 0x4207E0), the puzzle screen's puzzles_bg.jpg, puzzle_covers.png 4 x 4
and btn_done.png 3 x 1 (0x445520, the same cuts as their table entries), and the two fonts (0x4023B0 ->
0x4027A0): ldwarialbold.png (glyph table 0x4BA140) and ldwBurweed27.png (0x4BB068).

`sheet_table()` lists all of them, one entry per distinct cut (graves.png is built whole as sprite 37 and 4 x 1 as
sprite 274; firestrip.png twice the same, sprites 250 and 275; AlchemyLab1.png whole as 291 and 1 x 1 as 80).
`used` is True for all of them: no table entry is shown to be never drawn (many ids are computed at run time, so
"never asked for by a constant" is not "never drawn").

Proven (`TheExesSprites`, needs the exe and pefile):

* `TABLE` is the exe's table, all 305 entries, and the lookup bound is 0x4C40F8.
* Every `call` of 0x40A840, 0x40AB10, 0x40ABA0, 0x401010 and 0x4023B0 in .text is one of the 19 known sites,
  and the named ones load the names listed above.
* Every picture name string in the exe is in `sheet_table()`.
* The fonts' glyph tables are the exe's.

Proven (`TheGamesCutIsTheAtlas`, emulated): every frame of every table sprite whose files the game ships, built by
the game's own constructors and drawn by the game's 0x44CEC0(id, frame, x, y, 1.0, 100), is the cell
`vv_picture_image.Atlas.cell` cuts (frame = row x columns + column). More than 5,000 frames, every one.

Pictures the table names but the shipped game does not have (nothing to show): small_logo.png,
story3_page1mask.png, SPLASH1_BG.JPG, SPLASH2_BG.JPG, SPLASH3_BG.JPG, menu_logo.png, loading_logo.png.

**Unused** (in the game's Images folder, never built by the exe; Source sheets lists them "(unused)", cut at their
own gaps): break1.png, btn_check.png, buy_button.png, graveflowers.png, main_no-comm.png, mausoleum_urn.png,
mossy_decal_small.png, verticalslidertrack.png (`UNUSED_FILES`, checked against the game's folder).

## Composed assets

### UI: Tech screen (0x43E640)

The screen draws, in order: tech_bg.jpg (sprite 227) at (0, 0); the colour carving's slices top down, slice 6 at
(395, 135) when 0x41F570 is 5 or more, slice 5 at (395, 201) when 4 or more, slice 4 (395, 271) when 3, slice 3
(395, 340) when 2, slice 2 (395, 408) when 1, then slice 1 at (395, 474) always; then the six technology bars from
the table at 0x4BEE60 (sprite, x, y, across): Science (tech_science.jpg) at (3, 73), Medicine (3, 179), Learning
(3, 281), Construction (tech_restoration.jpg, the game's label for it) (3, 386), Food Mastery (3, 489) and
Dendrology (398, 74). A bar with n levels learned (0x41E1C0) draws its jpg's frames 0 .. n-1 at (x + 132 k, y),
each at its fade-in alpha (1.0 once shown). 0x41F570 counts five done tasks (flags 1, 12, 13, 14 and 15 of
0x4D8BF8).

Assets: the Tech screen (4 frames: every bar at level 0-3), the colour carving (6 frames: 0-5 tasks), and each bar
uncoloured and at levels 1-3 (6 x 4 frames). The coloured pieces are the game's blits; the uncoloured bar is
tech_bg.jpg's own picture under the bar (the game draws the whole background, not a separate uncoloured bar).

Proven: 0x43E640 emulated for 7 carving values x 4 uniform levels, 3 mixed cases and 43 level combinations
(every blit equal, and the carving's and each bar's blits are the screen's own, in order). After its art the
screen sets the camera, draws the villager queue and its dialog (0x44C3E0, 0x41D5F0, 0x44C420, 0x46ABC0,
0x40D3E0): stubbed, not part of the picture.

### UI: Meters

* Villager Details bars (0x44D070(kind, value, y), sprites from 0x44D020): the value clamped to 0-100, value x 256
  / 100 / 4 slices (C division), each the whole slice at (468 + 4 i, y + the kind's offset): kinds 3-7
  StatusBarSliceB.png at +224, +266, +308, +352, +393, kind 8 StatusBarSliceR.png at +95. Assets: the blue and
  the red bar at 10, 25, 50, 75 and 100 %. Proven: 6 kinds x 13 values x 2 y's emulated.
* Loading bar (0x44DB10(3, x, y, value), sprites from 0x44DAD0): the value clamped to 1-100, value x 320 / 100
  / 8 segments; for each, LoadColor.png at (x + 8 i, y) and then BambooMeterFrame1.png at (x, y) again. Below 3 %
  the game draws nothing at all. Assets: 10, 25, 50, 75, 100 %. Proven: every value -3 to 102 and 300.
* The bamboo frame: kinds 0-2 of 0x44DB10 fill a rectangle (0x408210, a colour) and draw the frame over it. Only
  the frame is shown (proven: the frame is the only blit, after one fill); the fill is not a picture.
  healthBarbulb.png (sprite 170) is built with the bars (0x44D020) but its draw was not traced: Icons, cells only.

### UI: Panels and buttons

* Buttons: the engine's button draw 0x401200(state), reached from 0x401540, which picks state 0, 1 or 2 from the
  button's [+0x30] (vtable 0x48A5E0 entries 8-10): an enabled button draws its strip's frame `state` at its
  place, plain. State 2 also moves the caption 2 pixels (the pressed look); state 1 is labelled "mouse over" by
  the engine's convention, the mouse code that sets it was not traced. Assets: all 35 three-frame strips of the
  table, 3 frames each. `STRIP_REQUESTS` lists where the exe asks for each by a constant id (proven to be every
  such call of 0x44CB60; two calls use a computed id); the strips never asked for by a constant say so in their
  note. Left out: the caption (text) and the disabled look (0x408F60 tints the screen's pixels one by one).
  Proven: 0x401200 for every strip and state, and 0x401540 dispatching each state.
* Dialogs (the tiled background, 0x40DC70 + 0x40DAB0(x, y, 1.0)): tiles of the 9 x 1 grid,
  (margin + size + tile - 1) / tile across and down (at least 2; the margins [0x4CBB78], [0x4CBB74] are 0 and never
  written): top row tile 8, tile 1 across, tile 0; each middle row tile 3, tile 7, tile 2; bottom row tile 5,
  tile 4, tile 6. Assets: the green dialog at 800 x 60 (0x412AEF, its fixed size), the green one 300 wide
  (0x41983F, height varies: 200 shown), the orange one 512 wide (0x417CDD, height varies: 300 shown), and each
  grid's tiles named by where they go. Proven: the three sizes and 56 other sizes, at two places.

### Screens

Each screen's fixed art, from the exe's own call arguments: each 0x44CDB0(sprite, x, y, 1.0, 100) call's pushes
are read from the exe bytes (`test_tech_rows_and_screen_arguments`), and the generic cut test proves what such a
call blits. Loading screen (0x43F400: loading.jpg (0, 0), logo1.png (212, 10), ldwLogo.png (47, 400); between them
a 60 % wash fill and the loading bar, the fill not drawn), Trophies (0x43A950: background, top, bottom at
(0, 545)), Mausoleum (0x43D280, the same), Select villagers (0x43B6A0), Collections (0x43C6D0), Villager Details
(0x447D30, VD_BG_2.jpg), Island overview (0x4453C0), Boxshot (0x443560; the butterflies and the light beams,
whose opacity wavers with time, not drawn), the Puzzles page, Help pages 1-4 and Credits (0x43EF40). Only the art
before and between the screen's moving parts is shown; their notes say what comes between. Splash: SPLASH_BG.JPG
whole (built at 0x4466A4; where the splash draws it was not traced).

### Scene: the island (0x46FCE0, 0x46FE10)

The 16 map tiles, built x outer, y inner, tile (x, y) at (512 x, 512 y); 0x46FE10(scroll x, scroll y, left, top,
right, bottom) draws each tile in view at its place minus the scroll. One asset, the whole 2048 x 2048 ground.
Proven: emulated with the whole map in view and scrolled to (300, 100) in an 800 x 600 view. Everything standing
on the ground (trees, water, huts, the Tree of Life) is drawn over it by other code and is not part of it.

### Buildings and objects: huts (0x42FF80)

The draw of the hut classes (vtables 0x48E3CC, 0x48E44C, 0x48E4CC, 0x48E5CC, 0x48E64C, 0x48E6CC: the three huts,
love shack, nursery, hospital): draw part 0 and 1 are scaffolding.png (sprite 273) whole at the hut's place +
(0, 110) and + (88, 75) (table 0x4BDC80); part 2 and up is the hut sheet's frame part - 2 at the hut's place.
Assets: each part of hut_states.png (2 x 2), loveshack_states.png, nurseryhut_states.png, hospital_states.png
(2 x 3 each). Proven: every part of every hut emulated. Not shown together: which parts the game queues at each
build stage (0x4300E0 picks a stage 0-3 from the build progress; the queueing was not traced). The clothing hut
has its own draw (0x430C80), not traced: cells only. The highlighted hut (a tinted copy at 60 % first, 0x44C6B0)
is left out.

### Fonts and digits (0x4027A0)

Both fonts' glyphs, cut as the loader leaves its glyph table: the line height is the first glyph's height, and a
glyph whose right edge passes the picture's width starts a new line (the stock pictures are one line, 1940 and
2364 pixels wide). A negative character is its byte. 190 glyphs each. Proven: the loader emulated on both fonts;
the table it leaves equals `font_glyphs`. How text is laid out on screen is not part of this.

### Collectibles: the Super-Secret Golden Mushroom (patcher)

The Golden Mushroom companion (native/vvfp_golden_mushroom, `LATER_STUB(vv4, 0x4CC9E8, 0x44C645u, 7, 0)`) replaces
frame 50 of the collectables sheet at the world draw 0x44C640 with golden_mushroom.png, a 1 x 1 sprite built with
the game's 0x40AB10, 7 pixels to the right. Proven: 0x44C640 emulated with the sprite built by the game's own
0x40AB10, at three places; the offset and frame are read from the companion's source.

### Patcher art

* Origins masks: vvfp_mask_atlas00.png (assets/vv4_masks/vvfp_mask_atlas.png) 8 facings x 5 masks and
  vvfp_bighead_mask_atlas00.png 3 x 5, cut as the companion's 0x40ABA0(name, ".png", 1, 1, cols, 5) cuts them
  (their placement on a villager is vv_pictures_vv4's, proven in tests/test_pictures_vv4.py).
* vvfp_mask_preview.png: whole, position not from the game.
* The Origins icons in "VVFP VV4 Origins Icons.dll" (RT_ICON PNGs 1-49: icons 101-110 at 16-64 pixels), read from
  inside the shipped DLL (`origins_icon_resources()`, `vv_pictures_assets.read_patcher_art`).
* Not shipped, so not listed: assets/candidates/vv4_full_mastery (btn_upgrades_297x35.png), assets/origins/*.png.

## Everything else: cells only

Every other table sprite is listed in its category (`GROUPS`) cut as the game's constructor cuts it, in the sheet's
order, with the note that how the game plays or places those cells is not proven here: creatures (fish, crabs,
frogs, reef fish, bees, birds and the bird shadow, dragonflies, hummingbirds, butterflies), the labs, graves, the
Tree of Life's six states and branches, the food bin, island puzzle pieces, collectables, plants, water and
weather effects, the hand cursor, icons, controls, screen parts, story pages and logos. The villager sheets
(heads, bodies, actions, big heads and bodies) and carrying.png are only under Source sheets (the Villagers tab
draws them; carried items are another change's).

Traced but not composed, and why:

* The bird (0x42B220): the draw is clear (the shadow, then the bird at its frame field + 2 or + 4 by its state,
  scaled by its own percentage), but which frame-field values occur was not traced.
* The story pages and image1_page5mask.jpg (sprite 188, a whole JPEG): the code that draws the story pages asks
  for them by computed ids and was not found, so how the game uses the mask with image1_page5.jpg and
  image1_page5_hands.png is not known; the engine's picture loader (0x40B050) does not combine pictures itself.
  Listed as cells only.
* The Tree of Life, waterfalls, lake, effects: drawn by the island manager (sprites fetched at 0x439440) through
  the draw queue; not traced.

## Not drawn

* **Filled rectangles.** The game fills rectangles (the loading screen's 60 % wash, the bamboo meter's fill,
  0x408210). Plans hold only picture blits, so those fills are not drawn.

## Tests

`python -m pytest tests/test_assets_vv4.py -q` (with xdist `-n 8`). Gating: the exe-byte tests need the exe and
pefile; the emulated ones the exe, `research/game-images` and Unicorn; the pixel tests the pictures; `Rules` needs
nothing but the repository. Contact sheets: `python scripts/render_asset_contact_sheets.py --game 4` writes one
PNG per category into outputs/vv4/.
