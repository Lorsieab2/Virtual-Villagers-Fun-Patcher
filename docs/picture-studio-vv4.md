# Picture Studio: The Tree of Life (Virtual Villagers 4)

`src/vv_pictures_vv4.py` draws The Tree of Life's villagers exactly as the game does, from the player's
own game files: the sprite sheets under `Images\` and the game's animation-point file
`Assets\animpts.dat` (where each head and body sits). No game file ships with the patcher. Every rule
below was ported from the vanilla executable (SHA-256 `6D27A429...F1B220`) and is proven by
`tests/test_pictures_vv4.py`, which runs the game's own code in Unicorn and compares every blit.

## The pieces

| What | Where in the game | Rule |
|---|---|---|
| Sprite table | `0x4C07CC` (0x30 bytes per entry) | heads 16 x 30 over `<sex>_heads00/10.png` (columns 0-7 young, 8-15 old); bodies 32 x 30 over a 2 x 3 grid `<sex>_bodies00..12.png`; actions 17 x 30 over `<sex>_actions00..02.png`; `bigheads` 12 x 30 over `BigHeads00/10.png`; `bigbodies.png` 2 x 30; `skelly.png` 4 x 1; `ripple.png` 4 x 1; `carrying.png` 13 x 6; `collectables_small.png` 6 x 9; `peep_shadow1.png` whole |
| Atlas cut | `0x40A990` | the same as A New Home's `0x409F90` (`vv_picture_image.Atlas`) |
| Manager sprites | `0x465F70` | `+4` shadow, `+0x24` carrying, `+0x28` collectables, `+0x2C` skeleton, `+0x30` ripple |
| Animation tables | `0x4E00E0`, built by `0x44DE60` | `Assets\animpts.dat`: a length, 50 poses x 4 parts x 0x1E8 bytes copied to `+0x7254`, a length, 22 head entries x 0x1E8 copied to `+0x1F05C`; then fixed sprites and frames written over them (`0x44E636-0x44E750`): poses 0-31 the bodies sheet at frame = pose, 32-48 the actions sheet at pose - 32, 49 `bigbodies.png` (male frame 0, female 1); head columns 0-7 the heads sheet, 8-10 `bigheads` (male 0-2, female 3-5). Each pose part holds a head anchor per body (`+8`) and a body anchor per body (`+0xF8`); each head entry a head offset per head (`+0xF8`) |
| Anchors | `0x44E960`, `0x44E900`, `0x44EA00` | `trunc(offset x scale + 0.5)` (toward zero) |
| Scales | `0x45EC30`, `0x467EEC` | body `age / 700 + 0.5`, head `(age / 14 + 80) / 100`, both 32-bit floats, full size (1.0) from 280 age units |
| World draw | `0x44C790`, `0x44C720`, `0x44C640` | `percent = trunc(100 x scale)` (`[0x4DB9F8+0x3010]` is 100 at zoom 1); `0x409A80` makes the cell a frame and `0x408DC0` cuts it back (C division); the blitter draws at `percent / 100` from the given top-left, never centred |
| Camera | `0x44C3E0` | the village sets zoom 1.0 (`0x4400DD`: no scale; only the scroll moves) |
| Blitter | `0x404CB0` | the same model as A New Home's (`vv_picture_image.blit_piece`): box-averaged down-scaling, surface alpha `(a x A + 127) >> 8` |

## The village figure (`0x467DA0`)

The draw queue (`0x44C420`, case 6) calls it with surface alpha 1.0 for every villager every frame.

1. **A body awaiting burial** (health <= 0): `skelly.png` cell `(record +0x1B94) C-mod 4` at the villager's
   place, at the body scale, alpha 1.0. Nothing else.
2. Otherwise `X = x + trunc(20 x bodyScale)`, `Y = y + trunc(55 x bodyScale)` (`0x45ED00`).
3. **Pose**: record `+0x1CB0`; 0-7 is a step and the direction (`+0x1CD0`, 0-7, else 2) adds 8 per
   direction; 8-49 is the table's pose as it is.
4. **Shadow** (`peep_shadow1.png`, not in water): at `X - trunc(34s)`, `Y - trunc(32s)`, at scale `s`, the
   body scale (halved, and 20 pixels lower, while the hand holds the villager: `+0x1CC5`).
5. **Carried item** behind (direction 0, 3, 4; not in water): `+0x1CDC` (-1 none; below 70 a
   `carrying.png` cell, else `collectables_small.png` cell n - 70) at `(x, y + trunc(18 x bodyScale))`
   (`0x466770`); a litter of 2 or 3 (`+0x1C50`) adds copies at `(-5, +5)` and `(0, +9)` - always
   `carrying.png` cells at the record's own number, so a collectable's copies are other carrying cells,
   as the game draws them.
6. **Body**: the pose's sprite and frame for the sex, row = body, at `(X, Y)` minus the body anchor, at
   the body scale. Standing in water (terrain 5 at the feet, `0x46C3D0`, not held, pose not 0x29) there is
   no body: `ripple.png` (a random cell) at `(X - 32, Y - 32)` at alpha 0.4.
7. **Head**: the place plus the head anchor of that body, minus the head offset of (head column, sex,
   head); column `+0x1CD4`, plus 8 for the old head from 1,100 age units (Change Appearance's head look:
   `common.old_head`), at the head scale.
8. **Carried item** in front (direction 1, 2, 5, 6, 7; not in water).

**Ghosts** (`0x466370`) are villager records with `+0x1CC7` set, drawn at their own surface alpha
`+0x1CCC`: 0.6 when they appear (`0x48E330`); the game fades it while a ghost leaves (`0x45FAE3`). The
Studio draws 0.6.

## The Villager Details figure (`0x45F550`)

Pose 49 (`bigbodies.png`) and the big head (`bigheads`, head column `8 + (+0x2E38 C-mod 3)`, plus 6
columns for the old head) through `0x409A70` (no world transform) at `trunc(scale x 100)` percent; an
expecting mother (`+0x1C4C` non-zero) holds her babies: `carrying.png` cell 3 at 200% at
`(x - 2 trunc(20s) - 10, y - 2 trunc(55s) + 36)`, and for twins / triplets 8 and 13 pixels higher.

## The patcher's Origins masks (proven on the patcher's own bytes)

The tests apply the Origins row's mask patches from `data/vv4_origins_feature.json` (the resolve cave,
the world cave at `0x728EB0` with its lift table, the Details cave at `0x7287A1` with its tables, and the
two call sites) to the vanilla executable, answer the companion DLL's two exports, and compare blits.

* **Village** (`mask_world_cave`, on the head draw `0x468263`): the head's own world draw again with
  `vvfp_mask_atlas00.png` (8 x 5 cells of 65 x 145), column `head column AND 7`, row `mask - 1`, `y`
  lifted by `rint(34 x headScale)` (`fistp`).
* **Details** (`mask_head_cave`, on `0x45F702`): `vvfp_bighead_mask_atlas00.png` (3 x 5), column the
  portrait facing (`0, 1, 2`), `x + (19, 3, -16)[column]`, `y + (0, 2, 0, 2, 0)[row] - 50`, a young
  villager's Orange, Purple or Chief mask 2 left and 3 down, at `(headPercent x 3) >> 1` percent.

The masks come from the save's "Village Masks" file (`common.masks_by_rank`), the head look from
"Head Looks" (`common.head_looks_by_rank`).

## Proof (tests/test_pictures_vv4.py)

* `TablesMatchTheGame`: every pose part and head entry the renderers read, against the game's loader run
  on the game's own files; the sprite table.
* `VillageMatchesTheGame`: 2,304 states (2 sexes x 12 ages around every threshold x 4 head/body pairs x 8
  poses x 3 head columns), all 50 poses x 4 directions, every head and body, skeletons (8 frames x 4 ages),
  ghosts, held, in water (every ripple cell), 7 items x 3 litters x 4 directions.
* `MaskMatchesThePatcher`: masks 0-5 x 6 ages x 8 head columns x 2 sexes in the village, and 6 masks x 6
  ages x 5 portrait facings x 2 sexes in the Details portrait; the patcher's lift and seating tables.
* `DetailsMatchesTheGame`: 2 sexes x 7 ages x 5 portrait facings x 3 head/body pairs, every head and
  body, expecting mothers with 1, 2 and 3 babies.
* `BlitterMatchesTheGame`: the game's `0x404CB0` on test pixels at 8 child scales, alpha 1 and 0.6, three
  cells, under Windows' 53-bit x87 precision.
* Without the emulator (CI): tables from a made-up file, plans on blank sheets of the real sizes, the
  save reader on a made-up save.

## Not covered or not proven

* **The emulated renderer is fed by stubs** for the terrain test (water or not), the selection test, the
  random numbers (the ripple's cell, the splash particles) and the sprite registry; the geometry is the
  game's.
* **Selection ring** (`focus_circle`, drawn when the villager is selected) and the **splash particles**
  in water are not drawn: they are not part of the villager.
* **Elevation** (`+0x1CB8`, used while jumping/climbing) is taken as 0, and `+0x1CD8 = 6` (no shadow) is
  not offered.
* **Directions 4-7**: the body sheets have 4 directions; with a step pose, directions 4-7 would read past
  the 50 poses. They are not offered (no game state using them was found).
* **Map/overview** (zoom other than 1, `0x44544B`) is not drawn.
* **Ghost alpha** is the starting 0.6, not the fading values.
* The carried "baby" item (cell 3) is identified from the Details portrait, which draws it for an
  expecting mother; which village task sets item 3 was not traced.
* The pixels where two sprites overlap are combined with straight alpha over a clear background; the
  game blends onto its scene (the blitter's own formula is proven for each sprite on an opaque
  background).

## Change Appearance's preview (fixed in v1.35.86)

`native/vv4_origins_icons/vv4_origins_icons.c` `appearance_draw_cell` used to name the body sheet
`<sex>_bodies<age><page>.png` with the old-head digit (head look Old, or Auto at 55 and over); the first
digit of a body sheet is the sheet's place across the 2 x 3 grid (directions 2-3), not an age, so an
"old" body preview read another direction's frame. It now always reads `<sex>_bodies0<page>.png`, the
sheet the game draws the body from (the head still comes from `_heads00` / `_heads10` by the look).
`tests/test_vv4_appearance_preview_sheets.py` runs the shipped DLL's window procedure in Unicorn.
