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

## Text (the Text tab)

The Tree of Life builds two bitmap fonts:

- **Arial Bold**: `ldwarialbold.png`, 1940 x 20, table 0x4BA140, 20 pixels a line.
- **Burweed**: `ldwBurweed27.png`, 2364 x 27, table 0x4BB068, 27 pixels a line.

They hold 0x20-0x7E and the Windows-1252 letters and signs from 0xA1 (The Secret City: 0xA2) to 0xFF, accented letters included. Bytes 0x80-0xA0 draw "!". The Text tab makes everything else in the font's style.

The game's text draw is 0x409700 and its centred draw is 0x409BE0. They are run in Unicorn on the stock executable, and every blit is compared with the Text tab's plan (`tests/test_pictures_text.py`). See [picture-studio-text.md](picture-studio-text.md).

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

## Carried items

Every item a villager can be drawn carrying, as offered under **Carrying** on both tabs (`src/vv_pictures_carried.py`). "Unused in the game" items are drawn with the game's own carry code, which draws any number, but nothing the game runs carries them.

| Number | Name | Status | When the game carries it (or why it never does) |
|---|---|---|---|
| 0 (0x0) | Berries | in the game | Harvesting blackberries; Researching; Adding to the stew |
| 1 (0x1) | Rock | in the game | Heating a rock in the fire; Clearing rubble; Doing exercise |
| 2 (0x2) | Feathers | in the game | Researching |
| 3 (0x3) | Baby | in the game | expecting |
| 4 (0x4) | Wood | in the game | Attempting to fix the piers; Keeping the stream clear; Fixing the hut; Gathering firewood; Building a hut |
| 5 (0x5) | Laundry | in the game | Washing the laundry |
| 6 (0x6) | Crops | in the game | Adding to the stew |
| 7 (0x7) | Flowers | in the game | Honoring the Dead; Researching |
| 8 (0x8) | Fish (carrying.png) | unused in the game | no code stores it |
| 9 (0x9) | Crab | in the game | Catching a crab |
| 10 (0xA) | Water | in the game | Filling a pot; Emptying the pot; Cleaning up the nasty mold; Cleaning up after the rain |
| 11 (0xB) | Body | in the game | Burying the dead |
| 12 (0xC) | Magic fish | unused in the game | no code stores it |
| 13 (0xD) | Brown mushroom (carrying.png) | unused in the game | no code stores it (a carried mushroom is collectables picture 49) |
| 14 (0xE) | Red mushroom (carrying.png) | unused in the game | no code stores it |
| 15 (0xF) | Dry grass | in the game | Gathering dry grass; Researching |
| 16 (0x10) | Coconut | unused in the game | no code stores it |
| 17 (0x11) | Empty bowl | in the game | Filling a pot with fresh water / salt water; Researching |
| 18 (0x12) | Tool | in the game | Sharpening into a cutting tool; Cutting some pulpy vines; Looking for a tool to cut some stalks |
| 19 (0x13) | Pot | unused in the game | only the never-started jobs Hiding something / Spring cleaning store it (DEAD) |
| 20 (0x14) | Stew pot | in the game | Something smells YUMMY! |
| 21 (0x15) | Big leaf | in the game | Covering the hot rocks |
| 22 (0x16) | Stone tips | in the game | Attempting to cut the branch |
| 23 (0x17) | Bounty | unused in the game | only the never-started jobs Hiding something / Spring cleaning store it (DEAD) |
| 24 (0x18) | Lab bowl | in the game | Researching |
| 25 (0x19) | Nothing to see (an empty picture) | in the game | Researching (1 in 7: the hands look empty) |
| 26 (0x1A) | Lab bowl (second picture) | unused in the game | no code stores it |
| 27 (0x1B) | Striped jar | unused in the game | no code stores it |
| 28 (0x1C) | Striped vase | unused in the game | no code stores it |
| 29 (0x1D) | Tool (second picture) | unused in the game | no code stores it |
| 30 (0x1E) | Clay amphora | unused in the game | no code stores it |
| 31 (0x1F) | Spicy herb | in the game | Gathering herbs; Retrieving medicinal plant for study; Cooking |
| 32 (0x20) | Sweet herb | in the game | Gathering herbs; Retrieving medicinal plant for study; Cooking |
| 33 (0x21) | Soapy herb | in the game | Gathering herbs; Retrieving medicinal plant for study; Cooking |
| 34 (0x22) | Pulpy vines | in the game | Gathering herbs; Cutting some pulpy vines; Cooking |
| 35 (0x23) | Medicinal plant | in the game | Retrieving medicinal plant for study; Cooking |
| 36 (0x24) | Red-topped stalk | unused in the game | no code stores it |
| 37 (0x25) | Yellow berry cluster | unused in the game | no code stores it |
| 38 (0x26) | Banana | unused in the game | no code stores it |
| 39 (0x27) | Mango | unused in the game | no code stores it |
| 40 (0x28) | Papaya | unused in the game | no code stores it |
| 41 (0x29) | Cloth pulp | in the game | Spreading cloth pulp; Honoring the tree |
| 42 (0x2A) | Lit torch | unused in the game | no code stores it |
| 43 (0x2B) | Debris | in the game | Cleaning up after the rain |
| 44 (0x2C) | Keystone | in the game | Attempting to install the keystone |
| 45 (0x2D) | Red gem | unused in the game | no code stores it |
| 46 (0x2E) | Dark sphere | unused in the game | no code stores it |
| 47 (0x2F) | Red striped pot | unused in the game | no code stores it |
| 48 (0x30) | Leaves | unused in the game | no code stores it |
| 49 (0x31) | Pearl | unused in the game | no code stores it |
| 50 (0x32) | Unlit torch | unused in the game | no code stores it |
| 51 (0x33) | Irregular pearl | unused in the game | no code stores it |
| 52 (0x34) | Hot rock | in the game | Taking a hot rock to the pot; Carrying a hot rock |
| 53 (0x35) | Cloth | in the game | Repairing braid for a lei; Attempting to fix fishing nets; Storing finished cloth; Attempting to bind the branch |
| 54 (0x36) | Yellow fruit | in the game | Shaking down some fruit! |
| 55 (0x37) | Orange fruit | in the game | Carrying fruit to the food bin; Adding to the stew |
| 56 (0x38) | Fish | in the game | Retrieving a fish |
| 57 (0x39) | Golden fish | in the game | Retrieving a fish (once the fish scales are found) |
| 58 (0x3A) | Soap | in the game | Stacking soap; Attempting to clean the stump; Adding soap to the pond |
| 59 (0x3B) | Fish bone | in the game | Retrieving a fish bone |
| 60 (0x3C) | Heat-treated bone | in the game | Heat treating a fish bone |
| 61 (0x3D) | Beetle | in the game | Purifying the tree |
| 62 (0x3E) | Blackberries | in the game | Harvesting blackberries |
| 63 (0x3F) | Lei braid | in the game | Taking braid to start a lei |
| 64 (0x40) | Lei | in the game | Hanging a lei on the tree |
| 65 (0x41) | Lei flower (orange) | in the game | Picking a flower for the lei; Taking flower to lab |
| 66 (0x42) | Lei flower (purple) | in the game | Picking a flower for the lei; Taking flower to lab |
| 67 (0x43) | Lei flower (white) | in the game | Picking a flower for the lei; Taking flower to lab |
| 68 (0x44) | Frog | in the game | Rescuing frogs |
| 69 (0x45) | Twig nest | unused in the game | no code stores it |
| 70 (0x46) | Fish scale, common 1 | in the game | Collecting a fish scale (children) |
| 71 (0x47) | Fish scale, common 2 | in the game | Collecting a fish scale (children) |
| 72 (0x48) | Fish scale, common 3 | in the game | Collecting a fish scale (children) |
| 73 (0x49) | Fish scale, common 4 | in the game | Collecting a fish scale (children) |
| 74 (0x4A) | Fish scale, uncommon 1 | in the game | Collecting a fish scale (children) |
| 75 (0x4B) | Fish scale, uncommon 2 | in the game | Collecting a fish scale (children) |
| 76 (0x4C) | Fish scale, uncommon 3 | in the game | Collecting a fish scale (children) |
| 77 (0x4D) | Fish scale, uncommon 4 | in the game | Collecting a fish scale (children) |
| 78 (0x4E) | Fish scale, rare 1 | in the game | Collecting a fish scale (children) |
| 79 (0x4F) | Fish scale, rare 2 | in the game | Collecting a fish scale (children) |
| 80 (0x50) | Fish scale, rare 3 | in the game | Collecting a fish scale (children) |
| 81 (0x51) | Fish scale, rare 4 | in the game | Collecting a fish scale (children) |
| 82 (0x52) | Lab equipment, common 1 | in the game | Collecting lab gear (children) |
| 83 (0x53) | Lab equipment, common 2 | in the game | Collecting lab gear (children) |
| 84 (0x54) | Lab equipment, common 3 | in the game | Collecting lab gear (children) |
| 85 (0x55) | Lab equipment, common 4 | in the game | Collecting lab gear (children) |
| 86 (0x56) | Lab equipment, uncommon 1 | in the game | Collecting lab gear (children) |
| 87 (0x57) | Lab equipment, uncommon 2 | in the game | Collecting lab gear (children) |
| 88 (0x58) | Lab equipment, uncommon 3 | in the game | Collecting lab gear (children) |
| 89 (0x59) | Lab equipment, uncommon 4 | in the game | Collecting lab gear (children) |
| 90 (0x5A) | Lab equipment, rare 1 | in the game | Collecting lab gear (children) |
| 91 (0x5B) | Lab equipment, rare 2 | in the game | Collecting lab gear (children) |
| 92 (0x5C) | Lab equipment, rare 3 | in the game | Collecting lab gear (children) |
| 93 (0x5D) | Lab equipment, rare 4 | in the game | Collecting lab gear (children) |
| 94 (0x5E) | Mausoleum mural piece, common 1 | in the game | Collecting mausoleum piece (children) |
| 95 (0x5F) | Mausoleum mural piece, common 2 | in the game | Collecting mausoleum piece (children) |
| 96 (0x60) | Mausoleum mural piece, common 3 | in the game | Collecting mausoleum piece (children) |
| 97 (0x61) | Mausoleum mural piece, common 4 | in the game | Collecting mausoleum piece (children) |
| 98 (0x62) | Mausoleum mural piece, uncommon 1 | in the game | Collecting mausoleum piece (children) |
| 99 (0x63) | Mausoleum mural piece, uncommon 2 | in the game | Collecting mausoleum piece (children) |
| 100 (0x64) | Mausoleum mural piece, uncommon 3 | in the game | Collecting mausoleum piece (children) |
| 101 (0x65) | Mausoleum mural piece, uncommon 4 | in the game | Collecting mausoleum piece (children) |
| 102 (0x66) | Mausoleum mural piece, rare 1 | in the game | Collecting mausoleum piece (children) |
| 103 (0x67) | Mausoleum mural piece, rare 2 | in the game | Collecting mausoleum piece (children) |
| 104 (0x68) | Mausoleum mural piece, rare 3 | in the game | Collecting mausoleum piece (children) |
| 105 (0x69) | Mausoleum mural piece, rare 4 | in the game | Collecting mausoleum piece (children) |
| 106 (0x6A) | Wind flute head, common 1 | in the game | Collecting a wind flute head (children) |
| 107 (0x6B) | Wind flute head, common 2 | in the game | Collecting a wind flute head (children) |
| 108 (0x6C) | Wind flute head, common 3 | in the game | Collecting a wind flute head (children) |
| 109 (0x6D) | Wind flute head, common 4 | in the game | Collecting a wind flute head (children) |
| 110 (0x6E) | Wind flute head, uncommon 1 | in the game | Collecting a wind flute head (children) |
| 111 (0x6F) | Wind flute head, uncommon 2 | in the game | Collecting a wind flute head (children) |
| 112 (0x70) | Wind flute head, uncommon 3 | in the game | Collecting a wind flute head (children) |
| 113 (0x71) | Wind flute head, uncommon 4 | in the game | Collecting a wind flute head (children) |
| 114 (0x72) | Wind flute head, rare 1 | in the game | Collecting a wind flute head (children) |
| 115 (0x73) | Wind flute head, rare 2 | in the game | Collecting a wind flute head (children) |
| 116 (0x74) | Wind flute head, rare 3 | in the game | Collecting a wind flute head (children) |
| 117 (0x75) | Wind flute head, rare 4 | in the game | Collecting a wind flute head (children) |
| 118 (0x76) | Brown mushroom | in the game | Picking a mushroom (children) |
| 119 (0x77) | Red mushroom | in the game | Picking a mushroom (children; 8%) |
| 120 (0x78) | Golden Mushroom | patcher | Picking a mushroom (Super-Secret Golden Mushroom) |
| 121 (0x79) | Collectables picture 52 | blank picture, unused | the game refuses it (0x4132B5: nothing above 0x78) |
| 122 (0x7A) | Collectables picture 53 | blank picture, unused | the game refuses it |
| 123 (0x7B) | Collectables picture 54 | blank picture, unused | the game refuses it |

The carry field is record +0x1CDC (-1 = nothing). Every store, read from the stock exe:

- **The setter** 0x45ED50 (10 callers; it asks the listener registry 0x4132B0, which refuses anything
  above 0x78, 0x4132B5) and the plain -1 stores 0x45D99F (the record reset, also on loading), 0x45DB19 and
  0x45F370. Action type 0x11 carries its number (0x46A657, 0x468BCF); only 0x4697C0 builds it (94 call
  sites, each resolved). The baby (3) is given at every action stop while +0x1C4C is set (0x468CDE,
  0x43B99D, 0x4658B8).
- **Collectables**: a child sent to one (the drop handler 0x44101F -> 0x4131A0) carries its number:
  0x46-0x75 the 48 collectables (Fish Scales, Lab Equipment, Mausoleum Mural pieces, Wind Flute heads: 4
  common, 4 uncommon, 4 rare each), 0x76 / 0x77 the brown and red mushrooms (0x4543D3, and the stew 0x42E1CC);
  0x78 only with the Super-Secret Golden Mushroom patch. 0x79-0x7B are blank cells the setter refuses.
- **DEAD**: jobs 0x55 "Hiding something" and 0x56 "Spring cleaning" (0x4589E0, 0x458E90: one of 0, 1, 2, 4,
  5, 6, 15, 18, 19, 23) and job 0x6D (0x434040: 1 and 0x34) are never assigned, so the Pot (19) and the
  Bounty (23) appear only there. The patcher's Story Upgrades can start any job, and so can make them appear.
- **Unused**: the other pictures marked unused are on carrying.png but nothing stores their number;
  carrying.png's cells 70-77 are empty art no number reaches (a litter's copy of a collectable would, and
  only children carry collectables).
- **The Golden Mushroom**: the item draw 0x466770 draws through 0x44C640, where "VVFP Golden Mushroom.dll"
  draws golden_mushroom.png, 7 to the right, for collectables frame 50 (the village's sheet and the
  collectables manager's are both 0x44CB70's sprite for id 260).
- **The save** keeps the record windows only, not +0x1CDC: the reset clears it on loading and an expecting
  mother (+0x1C4C, name + 0xB0) gets the baby back at her next action stop. The litter +0x1C50 (name + 0xB4)
  is saved and cleared at the birth (0x468A17).

**Proven** by tests/test_pictures_vv4.py `test_every_carried_item`: the game's own draw, run in
Unicorn on the stock executable, blits every item above in each of the four directions and in every pose
that draws the item (walking with twins and triplets, the work poses, a child) exactly as the plan says;
for the Golden Mushroom, the plan with the patcher's picture is the stock blits with the companion's swap
(tests/carried_golden.py, the offsets read from its source). The list itself is pinned by
tests/test_pictures_carried.py.
