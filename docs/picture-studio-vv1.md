# Picture Studio: A New Home (Virtual Villagers 1)

`src/vv_pictures_vv1.py` draws an A New Home villager the way the village draws it, and
`tests/test_pictures_vv1.py` proves it by running the game's own code. Every address below is in the
stock executable (`Virtual Villagers - A New Home.exe`, SHA-256 `1EC790B9...F03D`). It is the one in
`research/stock-executables`.

## The atlases

The game builds every villager atlas at 0x43C08E-0x43C2EB. Each one is a sprite of the shared engine. A
single sheet comes from `0x40A070(name, cols, rows)` and a grid of sheets from
`0x40A0F0(prefix, ".png", across, down, cols, rows)`, whose files are named `%s%d%d%s`, across then down.
The renderer's table is `vv1.ATLASES` / `vv1.IMAGES`.

| gameobj slot | atlas | cells |
|---|---|---|
| +0x3DFF4 / +0x3DFF8 | female_heads.png / male_heads.png | 7 x 20 (a column is a facing; a row is the head value) |
| +0x3DFE4 / +0x3DFE8 | female_bodies / male_bodies 00, 10, 01, 11 | 2 x 2 sheets, 32 x 20 (column = frame + 8 x direction; row = body value) |
| +0x3DFEC / +0x3DFF0 | female_actions / male_actions 00, 01 | 1 x 2 sheets, 9 x 20 (columns 0-3 bent over, 4-7 standing at work, 8 sitting; row = body value) |
| +0x3E000 | carrying.png | 15 x 1 (carried items; item 4 is a baby) |
| +0x3E004 | skelly.png | 4 x 1 (the dead) |
| +0x3E008 | ripple.png | 4 x 1 (swimming) |
| +0x3DFE0 / +0x3DFFC | peep_shadow1.png / focus_circle.png | whole pictures (0x409ED0) |

A cell is cut by 0x409F90 (`pi.Atlas.cell`). On a single sheet the cell is `w / cols` by `h / rows`, with
the column and row clamped to the last one. In a grid the cell size comes from the summed sheet sizes, the
sheet is picked by `col / per-sheet-cols` and `row / per-sheet-rows`, and wraps past the last sheet.

## The draw (the village compositor 0x437790)

The compositor draws each record of the draw order at gameobj+0x3DBDC in the order below. Positions are
relative to the record's x (+4) and y (+8) minus the camera. Nothing at all is drawn for state +0x38 = 4.

1. **Shadow and selection.** The ground test 0x414200 runs at (x + 0x14, y + 0x41).
   - In water (0xF), unless held (+0x2A) or the Golden Child: no shadow. The selection circle is drawn at
     (-13, +0x16) when the villager is selected (+0x29 = 1).
   - On land: peep_shadow1 at (-13, +0x13), plus the circle there when selected.
   - Held by the hand (+0x2A, set by the pick-up at 0x41DCCE / 0x41E14A and cleared by the drop 0x439450):
     the shadow at (-13, +0x27) at surface alpha 0.5 (0x409400 -> 0x408A40).
   - The dead get no shadow.
2. **Dead** (health +0x344 <= 0): skelly.png frame (+0x368 % 4, C remainder) at (0, 0), and nothing else.
3. **A child** (age +0x348 < 0x118) is drawn through 0x409410 -> 0x408AF0 at a scale. The body scale is
   `age/7 + 50` percent and the head scale is `age/14 + 80` percent, as C division. Each cell is centred
   on its unscaled cell by 0x407ED0, which moves it by `-((round(w*s) - w) / 2)`.
   - The Golden Child (+0x36C = 0xC7) is always drawn with the boys' sheets, at (+5, +13):
     - +0x58 = 6 or 7: male_actions column +0x20;
     - state 2: male_actions column 8;
     - otherwise: male_bodies column +0x20 + 8 x +0x30.

     His head is column +0x34.
   - State 1 (bent over): the carried item (+0x3C, unless 0x13) at (-5, +0x21), then actions column
     +0x20 at (0, +13), then head column 3 at (-2f - 2, 2f + 0x11), where f = +0x20.
   - Any other state draws in this order:
     - the item behind at (+5, +0x24) when +0x30 is 0 or 3;
     - bodies column +0x20 + 8 x +0x30 at (+5, +13);
     - head column +0x34 at (+5, +13);
     - the item in front when +0x30 is 1 or 2.
4. **An adult** is drawn unscaled through 0x4093C0 -> 0x408740.
   - **In water** (not held): ripple.png at (-12, +0x1C). Its frame is random & 3 (0x402F70), and it is
     drawn at surface alpha 0.4 through 0x4093E0 -> 0x408840. That alpha is the 0.4f that was pushed for
     0x402F70 and is still on the stack, read as the wrapper's 5th argument. Then the head column +0x34 at
     (0, +0x27), and nothing else.
   - **States 0 and 5 (walking):**
     - the item behind at (0, +0x10) for +0x30 = 0 or 3; with a litter (+0x35C != 0) also at (-5, +10),
       and with three also at (0, +5);
     - bodies column +0x20 + 8 x +0x30 at (0, +3);
     - head column +0x34 at (0, -1);
     - the item in front at (0, +0x19), (-5, +0x12) and (0, +13) for +0x30 = 1 or 2.
   - **State 1 (bent over):** the item at (-5, +0x21), actions column +0x20 at (0, +3), and head
     column 3 at (-2f - 2, 2f + 7).
   - **State 2 (sitting):** actions column 8 at (0, +3) and head column +0x34 at (0, +7). For +0x30 = 1 or
     2 the item is drawn at (0, +0x14), (-5, +0x19) and (0, +0x1D).
   - **State 3 (standing at work):** the item at (0, +0x15), actions column +0x20 + 4 at (0, +3), and
     head column 3 at (0, -2).
   - **Any other state:** nothing.

The particle sparkles (0x41AFD0) are effects, not part of the villager. They appear only on a 1-in-10
roll for the Golden Child in water and a 1-in-20 roll for a swimmer. They are left out of pictures.

## The blitter (shared by the five games)

The software blitter is 0x403D70 (place, cell, surface alpha, scale). It is reproduced by
`pi.blit_piece` and `Image.draw`:

- **Scaled down:** each of the trunc(w*s) x trunc(h*s) pixels is the truncated plain average of a box of
  source pixels in all four channels. The boxes are laid out by a position that starts half a step before
  the cell and grows by w / width, in double precision. Windows runs the x87 at 53-bit precision; the
  emulator's default of 64 bits gives a few different boxes.
- **Surface alpha:** A = ftol(alpha x 255 + 0.5), and each pixel's alpha becomes (a x A + 127) >> 8.
  Pixels whose (averaged) alpha is 0 are skipped.
- **Plain blits** (scale 1, alpha 1) go through SDL's own blitter (0x403D00, SDL_UpperBlit). They are
  composited with ordinary alpha.

## The patcher's own art

- **Origins masks** (`assets/origins/mask_atlas.png`: 7 facings x 5 colours of 40 x 160 cells). The
  companion builds this atlas with the game's constructor (Vv1GetMaskSprite,
  `native/vv1_origins_icons`). The village hooks in `scripts/build_vv1_origins_feature.py` replace the
  thunks 0x409410 and 0x4093C0. After a head drawn from the young head sheets, each hook draws the mask
  with the head's own arguments and these changes:
  - the atlas is swapped for the mask atlas;
  - the row becomes mask - 1;
  - a child's y is lifted by `(scale x 15) >> 5`, with the same scale and centring;
  - an adult's y is lifted by 48.

  The mask therefore follows every pose, swimming included. The renderer reads the masks from the save's
  "Virtual Villagers 1 Village Masks - Save S.dat" (`vv_pictures_common.masks_by_rank`).
- **Grey Hair at 55** (`assets/vv1_grey_hair/vvfp_grey_<sex>_heads.png`, the stock 7 x 20 layout). Every
  village head draw takes the grey sheet of the villager's sex when `vvfp_head_look_old(look, age)` is
  true: Auto from age 1,100, Old always, Young never. The Golden Child's head draws use the man's grey
  sheet. The masks still see the young sheet, so a grey head keeps its mask. From my save has a
  "Grey Hair at 55" on/off choice, because the save alone does not say whether its game has the patch
  (the patch is on by default).
- **Change Appearance's head look** comes from "Head Looks - Save S.dat" (`vv_pictures_common`).

## How each rule was proven (tests/test_pictures_vv1.py)

- `test_atlases_are_the_ones_the_game_builds`: each constructor call and its arguments are read from the
  bytes of 0x43C060-0x43C300 and compared with `vv1.ATLASES` / `vv1.IMAGES`.
- `test_every_cell_is_cut_as_the_game_cuts_it`: 0x409F90 is run on the atlases the game's own
  constructors built (the sheet loader 0x40A530 is replaced by one that gives each sheet its real size).
  It is checked for every cell, plus two past the end in each direction, against `pi.Atlas.cell`.
- `VillageDrawIsTheGames`: the whole compositor 0x437790 is run, and every blit it reaches is compared
  with the plan, in order. The comparison covers sheet, rectangle, x, y, scale and alpha, so the wrappers,
  the cell cut and the centring are all included. **1,067 records** are covered:
  - every direction x frame x four facings x both sexes walking, and state 5;
  - every work pose and frame, with and without an item;
  - sitting in every direction;
  - states 4, 6, 7 and 9;
  - every item x litter x direction for walking and sitting adults and for children;
  - every child age 0-280;
  - the Golden Child in every state and action at four ages and in water;
  - swimming at every ripple frame and facing;
  - the dead, including negative +0x368;
  - every selected, held and water combination for adults and children.
- `test_ripple_is_faded_by_the_stale_04`: the ripple's alpha is the 0.4f left on the stack.
- `OriginsMasksAreThePatchersOwn`: the compositor is run on the executable the patcher renders with the
  Origins row, with the mask table nibble set. It covers **276 records**: every mask 0-5 on every adult
  state, swimming, children at five ages (walking and bent over), the Golden Child and the dead.
- `GreyHairIsThePatchersOwn`: "VVFP VV1 Grey Hair.dll" is started in the emulator with its own installer.
  Its grey sheets are built by the game's constructor, and the head look is answered through a stand-in
  "VVFP Head Look.dll". It covers **264 records**: no look, Auto, Young and Old x ages
  0/279/280/1,099/1,100/2,400 x both sexes x four states, plus water and the Golden Child.
  `test_a_grey_head_keeps_its_mask` covers Grey Hair together with the Origins masks.
- `PlaceScaledIsTheGames`: 0x407ED0's centring for four cell sizes at every scale from 50 to 100.
- `BlitterIsTheGames`: 0x403D70 is run on a 32-bit test picture with SDL2 surfaces at FPCW 0x027F. It
  covers 12 scales x 3 rectangles x 4 surface alphas, plus the unscaled faded path, pixel for pixel
  against `pi.blit_piece` and the alpha rule.
- `Planning`, `SavedVillage` and `TheArt` test the renderer, the save reader (on a synthetic save) and the
  real art, which is drawn when `research/game-images` is present.

Without Unicorn, pefile or the stock executable (CI), the emulated classes skip.

## Not covered or not proven

- **Plain blits:** the blend arithmetic of SDL's own blitter is not emulated (SDL2.dll is not loaded).
  Their place and cell are proven; their pixels are the art's own.
- **Clear pixels under a faded blit:** the faded unscaled path also blends pixels whose alpha is 0, which
  darkens the screen by at most one step under them. A transparent picture cannot show this.
- **Other screens:** the Details portrait (0x437340), the dialog figure (0x4375F0) and the map (0x4388E0)
  are not drawn. Only the village view is.
- **Sparkles:** the particle sparkles are not drawn.
- **Labels:** the labels for direction (+0x30) and head facing (+0x34) are numbers. The game's names for
  them were not traced.
- **Grey Hair in From my save:** whether a save's game was patched with Grey Hair at 55 is not detected
  from the save. It is a choice, on by default as the patch is.
- **Origins masks in the owner's save:** the save copy used for the samples has no Village Masks file,
  so no saved masks were seen. Masks were proven on synthetic tables only.
