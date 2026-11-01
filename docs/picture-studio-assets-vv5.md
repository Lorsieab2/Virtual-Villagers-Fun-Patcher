# Picture Studio, Everything tab: New Believers (VV5)

Source: `src/vv_assets_vv5.py`. Proof: `tests/test_assets_vv5.py`. That test runs the stock executable's own code in Unicorn and records every blit. The emulated parts skip on CI, because CI has no stock executable and no game pictures.

## The sprites (`sheet_table()`)

Almost every picture is built from the game's sprite table at **0x4CEFB8**. It holds 341 records of 0x30 bytes each: id, name, columns, rows, suffix, sheets across and sheets down. The getter 0x44F760 searches 345 slots, and the last 4 are empty. On first use, the getter **0x44FA40** builds a record in one of four ways:

| record | constructor | cut |
|---|---|---|
| rows > 0, suffix | grid 0x40B0A0 | `Atlas(name, cols, rows, (across, down))` (the seven villager and bighead sheets) |
| rows > 0 | cells 0x40B010 | width // cols x height // rows |
| rows 0, cols > 0 | strip 0x401000 (= 0x40B010 with 1 row) | width // cols x height |
| otherwise | whole 0x40AD50 | the whole picture |

These sprites are built outside the table:
- `puzzles_bg.jpg` (whole, 0x448ABF) and `puzzle_covers.png` (4 x 4, 0x448AF4).
- `SPLASH_BG.JPG` (whole, 0x449964).
- The 25 island map tiles, built from `"%s%01dX%01dY.jpg"` with the prefix `LargeMap` (0x47ABE0).
- Two fonts: `ldwarialbold` and `ldwBurweed27`. The font constructor 0x402360 adds `.png` (0x4956B4). Each font has a glyph table at 0x4C7FE0 / 0x4C8F08 of `(code, left, 0, right, height)` records, 190 glyphs in each.

The exe also names some pictures that the game's Images folder does not have, so the game never draws them: `menu_logo.png`, `loading_logo.png`, `SPLASH1-3_BG.JPG`, `small_logo.png`, `Tech_colorcarving_slice1-6.png` and the four `collecting_*_collectionscreen.png`.

Two records share a picture and a cut (`firestrip.png` 0xE4/0xF8 and `hospital_states.png` 0xD4/0x10B), so each pair is listed once. `graves.png` is listed twice because it is built both whole (0x40) and as 4 x 1 (0xF7).

**What "used" means.** Every sprite in the table is marked used, because the game builds it by id when asked. The test's census found about 170 ids passed as constants to the getters and the draw (`push id; call 0x44FA30 / 0x44FC50 / 0x44FEF0 / 0x44FC70`). It also resolved the getter calls that compute an id or read it from a table (0x4C7BB0, 0x4CCC78, 0x4CD220 and the animation table). The remaining ids reach the getters through object fields and data tables that were not traced. So this listing does not prove that every table sprite is drawn. It only proves that each one is built and drawn the way shown when the game asks for it.

**Proven:**
- `DESCRIPTORS` is the exe's table, record for record (`test_descriptors_are_the_table`).
- The test checks every E8 call in the exe to the four sprite constructors and the font constructor. Each call is either:
  - one of the engine's own calls: the getters 0x44F817, 0x44F8DF, 0x44F959, 0x44F99E and 0x44FAE5, the constructors' own calls 0x40B03D and 0x401011, and the button class 0x401738, which cuts a strip it is given;
  - the map loader;
  - a call that pushes one of the names listed above (`test_every_constructor_call_is_accounted_for`).
- The fonts' glyph tables are the exe's (`test_font_glyph_tables`).

**Not proven:** the surface loader 0x47B8E0 (IMG_Load / SDL_LoadBMP) has two direct callers, 0x4350B0 and 0x447CC0. Both are virtual methods, and the test does not trace them.

## Unused

`UNUSED_FILES` lists 35 pictures. No NUL-terminated string in the exe names any of them, with or without its extension, and no sprite record names them either:
- FaithGradientArc and FaithGradientBar
- MS_Button_01-04
- break, break1, btn_check, buy_button, click, cloud_puff
- crabstrip1-2, cutting_tool, graveflowers, growth
- help_label_1-4
- hole-closed, light-beams, main_UI_BG
- map_hospitalStates, mausoleum_urn
- reefFish1-3
- ruinsRubble, selectvillager, undertoe, verticalslidertrack
- vv5_heathenheads06, willowisp1

`test_every_picture_is_built_or_unused` checks that every picture in the Images folder is either built by `sheet_table()` or unused, never both. (`DRM` is a folder, not a picture.)

Each unused picture is listed whole under Unused, and Source sheets also cuts it at its own gaps. **Faith meter (kind 9)** is listed under Unused too. 0x4500E0 can draw it: `FaithMeterBG.png` at (441, y+38) with half-length slices, blue to the right or red to the left. But none of the function's 13 callers passes kind 9; they pass kinds 3-8 and 11, which the test reads from the exe.

## Composed assets, each proven by running the game's own draw

| category | asset | draw | rule | cases checked |
|---|---|---|---|---|
| every category | each table sprite with a picture, every frame | sprite draw **0x44FC70** (id, frame, 0, 0, 1.0, 100) | frame k is cell (k mod cols, k div cols); a whole sprite is the whole picture; strips go through SDL_UpperBlit | every frame of every sprite, over 5,000 (the villager grids included) |
| UI: Tech screen | Tech screen in 5 states; each of the 6 tech bars (uncoloured, then 1, 2 and 3 levels); 11 god power icons, lit and grey | **0x440F80** | see below | 84 states (6 level sets x 14 Divine Energy caps), plus the icon fade at 5 starting alphas |
| UI: Meters | 7 Villager Details bars (Farming, Building, Research, Healing, Parenting, Devotion, Health) at 7 values | **0x4500E0** | see below | 378 (9 kinds x 21 values x 2 y) |
| UI: Meters | Divine Energy bar (HUD) at 7 states | **0x450380**; backing from 0x4431E8 | see below | 576 (12 caps x 12 energies x 4 costs); the backing draw is emulated and its call bytes are checked |
| UI: Panels | Orange and Green dialog boxes, 4 game sizes each | **0x40E160 + 0x40DFA0** | 9-slice, see below | 60 (2 colours x 10 sizes x 3 places and alphas) |
| Scene | the island assembled from its 25 tiles, and the tiles | **0x47ABE0** | tile (X, Y) is `LargeMap<X>X<Y>Y.jpg` at (512X, 512Y), X outer | the names loaded, in order, and the stored places |

**How each composed draw works:**

- **Tech screen (0x440F80):**
  - It clears the screen with a colour fill first; the test asserts that fill is (0, 0, 1024, 768).
  - Then it draws `Tech_UI_BG.jpg` at (0, 0).
  - For each line in the table 0x4CD220 (science, medicine, learning, restoration, food mastery and evangelism bars, at x 5 and y 78/192/307/420/534/647), it draws cell k at (5 + 167k, y) for each level k bought (0x423600).
  - Then the 11 god power icons at the table 0x4CD300. An icon is lit once the Divine Energy cap (village +0x17D60) reaches its cost (0x49A19C: 10 to 800):
    - Lit: the backing, then the coloured icon, both at the fade alpha (+0.02 a frame, up to 1.0).
    - Not yet: the grey icon, then the backing at alpha 0.6 (0x498938).
    - Either way, the top ring follows.
  - The "uncoloured bar" is not a separate blit. It is the screen background's own pixels under the bar, and its asset note says so.
- **Details bars (0x4500E0):** the call takes (kind, value, y). It draws n = trunc(trunc(clamp(value, ±100) x 256 / 100) / 4) slices, 4 px apart, starting at x 571:
  - `StatusBarSliceB.png` at y + 299, 341, 383, 427 or 468 for kinds 3-7, and y + 508 for kind 11;
  - `StatusBarSliceR.png` at y + 170 for kind 8 (health).
  - The skill names come from the record fields each caller reads (+0x1C5C..+0x1C70, +0x1C40).
- **Divine Energy bar (0x450380):** the call takes (x, y, cap, energy, cost).
  - The cap is clamped to 10..1,000, and the length is L = trunc(cap x 372 / 1,000).
  - It draws trunc(L/4) green slices, then trunc(trunc(L x energy / cap) / 4) blue slices, then trunc(trunc(L x cost / cap) / 4) glow slices.
  - On the HUD, `ManaBGBar.png` is drawn at (614, 10) and the bar at (617, 12).
  - The pulsing glow after a cast uses a sine alpha, and it is not listed.
- **Dialog boxes (0x40E160 + 0x40DFA0):**
  - Tiles are 64 x 64, cell 0 of the 9 x 1 grid sheet.
  - The box is (w + 63) // 64 columns by (h + 63) // 64 rows, at least 2 each. The padding globals 0x4DB334/0x4DB338 are 0 in the file.
  - Cell layout: top row 8, then 1s, then 0; middle rows 3, then 7s, then 2; bottom row 5, then 4s, then 6.
  - The sizes come from the game's callers: 455x400, 360x200, 640x508 and 480x320.

## Shown frame by frame only

The frames are the game's cells, proven by the 0x44FC70 test, in the sheet's order. What decides which frame the game shows, and when, was not traced. This applies to:
- **Creatures:** butterflies, bird and shadow, dragonflies, hummingbird, frogs, fish, bees.
- **Buildings and objects:** huts and their stages, granary, food bin, totems, idol, lab, ducts, paint pools, graves.
- **Puzzles:** covers, necklace pieces, proofs, eye and pupil, blink masks.
- **Collectibles:** the 48 collection pictures and the small ones.
- **Plants and food.**
- **Effects:** sparkles, smoke, fire, rain, lightning and other animated strips.
- **Scene:** waterfalls, waves, clouds, fog, rockslides, lake.
- **Panels and buttons:** buttons are shown as frames 1-3. Which state each frame belongs to (normal, hover, pressed) was not traced, so they are labelled by number.
- **Icons, cursors and screens:** whole pictures.

These are **not composed:** a hut with its scaffolding or woodpile, an animal's frame order over time, buttons with their text, the loading bar 0x450E30 (mostly SDL colour fills, which are not pictures), and the scene with its camera offset. Only the map loader's tile places are proven; the camera draw is not.

Left to Source sheets only: the villager grid sheets (heads, bodies, actions, bigheads). Picture Studio's villager renderer draws those, and carried items belong to the other branch.

## Fonts and digits

Each glyph of the Arial bold and Burweed fonts is cut as the glyph table cuts it. Negative codes are the Latin-1 characters 161-255. The cuts come from the exe's table, which is read directly. No text draw was emulated.

## Patcher art (what the release ships)

- `golden_mushroom.png`: the Super-Secret Golden Mushroom. VVFP Golden Mushroom.dll draws it in place of collectables frame 51, 7 px right and 1 px down (`LATER_STUB(vv5, 0x4DC808, 0x44F385u, 7, 1)`). This comes from the native source; it was not emulated.
- `bigheads_masks.png`: the Details portrait masks. It is shown whole and cut 3 x 5 (facings right, front and left by Blue, Orange, Red, Purple and Chief), the layout of `scripts/build_vv5_bighead_mask_atlas.py`. Where the patcher draws them is not taken from the game.
- The 10 Origins icons, read from inside the shipped VV5 Origins DLL (`vv5_task9_origins.rc` compiles them in; `vv_pictures_assets.origins_icon` takes each icon's largest image).
- Guardians of Isola's replacement art (data/guardians_of_isola/new/Images), cut as the game cuts the picture each one replaces (`vv_pictures_assets.mod_art_assets`).

## Tests

`python -m pytest tests/test_assets_vv5.py -q`. CI runs the Rules tests only.

Contact sheets: `python scripts/render_asset_contact_sheets.py --game 5` writes `outputs/vv5/<category>.png`.
