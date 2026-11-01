# Picture Studio, Everything tab: The Secret City (Virtual Villagers 3)

`src/vv_assets_vv3.py` lists every picture The Secret City ships and what the game assembles from them;
`tests/test_assets_vv3.py` proves the composed pictures by running the stock executable's own draw code in
Unicorn (`scripts/emu_vv3_assets.py`). All addresses are the stock `Virtual Villagers - The Secret City.exe`'s.

## How the game builds its sprites

* **The resource table** `0x4A95A0`: 181 entries of `0x30` bytes (id, file, columns, rows, suffix, sheets across,
  sheets down); entry 0 is "No Graphic". `0x42EA80` builds an entry as an atlas when it has columns and rows
  (`0x42E750` -> `0x40AF10`, or the sheet grid `0x40AF90` for the villagers' bodies and actions), a strip when it
  has columns only (`0x42E920` -> `0x401150`, which is `0x40AF10(name, columns, 1)`; only `CheckboxStrip.png`), and
  a whole picture otherwise (`0x40AD80`). `firestrip.png` is in the table twice (`0x6C`, `0x82`) with the same cut.
* **By name**, outside the table: `clamStates.png` 2 x 1 (`0x43296E`), `doorKeys.png` 3 x 1 (`0x4329A7`),
  `ruinsRubble.png` 3 x 1 (`0x4360FE`), `SPLASH_BG.JPG` and `SPLASH1-3_BG.JPG` (`0x46C509` ...), `menu_logo.png` /
  `loading_logo.png` (`0x4261A0` / `0x4261E5`), the 16 village map tiles `MapX%01dY%01d.jpg` (`0x422F20`, x and y
  0-3, 512 pixels apart) and the two fonts `ldwBurweed27` / `ldwarialbold` + `.png` (`0x4244D9` / `0x424569`, read
  whole by the font loader `0x402560`).
* Named by the exe but **not shipped**: `small_logo.png`, `story3_page1mask.png`, `SPLASH1-3_BG.JPG`,
  `menu_logo.png`, `loading_logo.png` (nothing to show).
* **Never built** (no table entry, no constructor, no string in the exe names them): `buy_button.png`,
  `opendoor.png`. They are listed under Source sheets ("Never loaded by the game") and under Unused.

`sheet_table()` is the table plus the by-name sprites (206 sprites). `used` is left true for every table entry:
many entries are requested with computed ids (tables in `.data`), so "never drawn" is not proven for any of them.

## What the composed pictures are and how each is proven

Every emulated test runs the game's own code -- resource table and getters, sprite constructors, camera
(`0x42E250` at no scroll and zoom 1.0, `0x42E4B0` whole, `0x42E510` frame, `0x42E570` scaled), cell cut, draw
wrappers and the static constructors of the village's objects (`0x47ACD0`-`0x47B130`) with each object's own
sprite loader (vtable `+4`) -- replacing only the picture loader `0x40B3D0` (a surface of the stock size), operator
new and the blitter `0x404620` (recorded; `SDL_UpperBlit`, which the strip draw uses, is recorded too). Every blit
(sheet, cell, place, scale, alpha) must equal the plan, in order.

| Category | Composed assets (frames) | Draw | Proof |
|---|---|---|---|
| UI: Tech screen | 7 bars x (uncoloured + levels 1-3), 7 "pieces" sheets, the whole screen (5) | `0x4649C0` | emulated: 112 level combinations of the whole screen; table `0x4B1F68` |
| UI: Meters | 6 Villager Details meters x 5 fills | `0x42EF60` | emulated: every meter at -5..105% (666 cases) |
| Screens | loading screen, title screen, 13 whole screen pictures | `0x42EB90` | each call site's pushes read (capstone) and `0x42EB90` emulated with them |
| UI: Panels and buttons | 21 buttons x normal / mouse over / pressed | frame k of the button sheet | `0x42ECA0` emulated for each frame |
| Buildings | huts 1-3 and the clothing hut (4 stages + 3 with scaffolds), statue, rain lift (8 frames + broken), ruins rubble (10 + 2 scaffolds), AlchemyLab0-4, wood pile, 14 overview places | `0x432110`, `0x432410`+`0x42E2A0`, `0x435000`, `0x435B60`, `0x436190`, `0x42FBA0`, `0x433910`, `0x428EF0` | emulated (see below) |
| Puzzles | door keys, giant clam (open with key / closed), sun disk (3) | `0x432C10`, `0x436890` | emulated |
| Plants and food | banana, mango, papaya trees: planted, 5 growth stages, grown with 0..max fruit; bushes at 8 clearing levels | `0x4341A0`, `0x435E90` | emulated: 3 trees x ~90 ages x 10 food amounts, and the fruit count for food 0-399 |
| Creatures | bird (12 frames with its shadow) | `0x4249E0` | emulated: 12 frames x 3 heights |
| Effects | 21 animation strips (257 frames) | `0x429610` (animation manager `0x583B28`) | emulated: every frame |
| Scene | the village from its 16 tiles; overview map in 3 village states | `0x422F20`; `0x42EB90` + `0x4290B0` + `0x428EF0` | tile names and places read back from the loader; overview list emulated for 4,800 state combinations |

Details:

* **Huts** (`0x594620`, registry index `0x15`): `0x432110` with parameter `((stage + 2) << 24) | ((hut + 1) << 16)`
  draws frame `stage` of `hut_states.png` (`clothinghut_states.png` for the clothing hut, hut 4) at `0x4B09EC[hut]`;
  `(which << 24)` draws a scaffold at the hut plus `0x4B09A4[which]`. "With scaffolds" frames are the camera queue's
  order: `0x432410` queues scaffold 1 (from 1 point of work) and 2 (from 50) in layer 6 keyed y + their offset +
  45, the hut keyed y + 110 (+ 75 for huts 2-4) in layer 3 at stage 0 and layer 6 after; the flush `0x42E2A0`
  sorts and draws. Proven: 16 stage draws, 8 scaffold draws, 60 queue-and-flush cases.
* **Statue** (`0x435000`): fallen below state 2, raised from 2, at (700, 460); scaffold at (790, 235). The
  "being raised" frame's layering (statue under the scaffold) is **not** proven.
* **Rain lift** (`0x435B60`): frame `+0xC` of `RainLift.png` (4 x 2) at (1477, 845); broken at (1520, 824).
* **Ruins rubble** (`0x436190`): `max(1, (100 - progress) x 10 / 100)` pieces at the table `0x436277`, piece k
  frame k mod 3; progress 0-100 all checked. **Bushes** (`0x435E90`): `max(1, (100 - progress) x 8 / 100)`, bush k
  frame 7 - k at `0x435F14`.
* **Door keys and clam** (`0x432C10`, registry index `0x13`): keys 1 and 2 where they lie unless picked up; the clam
  `clamStates.png` frame `+0xC` at (1830, 235), with key 3 drawn over it while open.
* **Sun disk** (`0x436890`): `sundisk.png` frame `+4` at (124, 432); the sun beam is blitted three times over itself
  at (0, -200) (shown at alpha 1.0; the game fades it in).
* **Plans** (`0x431E80`): `bath_plans.png` / `statue_plans.png` at (265, 1266), shown at alpha 1.0 (they fade).
* **Orchard trees** (`0x4341A0`, registry index 9): under 300 clock units the dirt mound; to 28,800 the mound and
  the tree scaled `1 - (28800 - age) x 3.5087720e-5` through `0x42E570`; then the tree and
  `min(max, food x max / 333)` fruit (one from 5 food) at the spot tables `0x4343BF`/`0x4344F7`/`0x434653`. Mango
  fruit 6-10 use the sheet's last cell (it has 5).
* **Overview map**: `0x4290B0` fills the list from the village state (bath built / its work, hospital level 1-3,
  puddle over 50, cape worn, food: below 150 / 1000 / 2500 / 4000), `0x428EF0` draws it at `(0xBC, 0x3D)` plus
  the place x 0.20703125, at 20%. The list builder ran on 4,800 states and each place's draw was emulated.
* **Meters**: slices = `min(100, max(0, p)) x 256 / 100 / 16` of `StatusBarSliceB.png` from x 462 (16 apart) at y
  223, 265, 308, 351, 392 (meters 3-7, labelled "Skill bar 1-5": which skill each is was not traced); health
  (meter 8): `healthBarbulb.png` at (417, 88) when above 0 and `StatusBarSliceR.png` slices at y 94.
* **Tech screen**: `tech_bg.jpg`, then for each skill `0x426FC0(k)` pieces: horizontal bars (science, medicine,
  alchemy, restoration, farming) piece k at x + 95k; vertical bars (nature, magic) piece k at y + 236 - 118k
  (bottom up). The "uncoloured" frame is the region of `tech_bg.jpg` under the bar's pieces (the background holds the
  uncoloured bar); its crop is ours, the place is the game's. The selected-skill glow (`sunbeam.png`, `+0xD4`) is
  not shown.
* **Buttons**: the button handler `0x4016B0` keeps `+0x30` = 0 away, 1 mouse over, 2 over and pressed; the frames
  are cells 1-3 in that order. The cut of each cell is emulated; the paint that picks the cell from `+0x30` was not
  found, so the state names are by that order, **not proven**.
* **Cell cut**: every frame of every table atlas and strip with a shipped file (4,780 frames) drawn through
  `0x42ECA0` equals `vv_picture_image.Atlas.cell`'s cut.
* **Table and scan**: the resource table read from the exe equals `TABLE`; a linear sweep (capstone) finds every
  call of the four constructors and the picture loader and each is the getters', the engine's, or a `DIRECT` one
  with its own arguments; every picture name string in the exe is built.

## Cell-exported only (the game's cut, not a composed draw)

Creatures other than the bird (reef fish 1-3, bees, shark, dragonflies, hummingbird: every frame in order),
graves and grave flowers, hospital and food bin states (village-scale), bath, cape, puddle, the alchemy and
science lab sheets, door, door frame, canopy, tree overhang, fog, cloud, collectables (54), the collection screen
pieces, door gems, small door keys, herbs, magic plants, puzzle pictures, awards, carried items, dialog tiles,
check box, radio buttons, slider, scroll bar, tutorial arrows, cursors, logos, the villagers' shadow, selection
ring, skeleton and ripple (their draw is proven by `tests/test_pictures_vv3.py`), the ghost (it bobs with the
clock; shown still), splash, main menu, collections screen and the story pages.

## Left out, and why

* **Story pages with masks**: `image1_page5.jpg` + `image1_page5mask.jpg`, `page2_flicker_alphaMask.png` and the
  missing `story3_page1mask.png` are drawn by the story code with computed ids; how the mask is combined was not
  traced, so the pages and masks are listed whole and separately.
* **Village-scale hospital, food bin, bath, cape**: their village draw was not found (only the overview's is
  proven); their cells are listed.
* **Dialog panels**: the nine tiles are listed; the dialog's assembly (`0x419837` ...) was not emulated.
* **Fonts**: whole pictures; the glyph cut and the text draw are not modelled.
* **Main menu, Awards, Puzzles, Collections, Details screens' buttons and text**: only their pictures.
* The **villagers** themselves are the Villager tab's (`src/vv_pictures_vv3.py`); carried items are another
  branch's.
* Pictures drawn only by SDL's own blit composite with straight alpha; overlapping blits on a transparent canvas
  are "over" (the game draws on the village).

## Patcher art (labelled patcher)

* **Origins masks** `assets/vv3_heathen_masks/heathen_masks.png` (8 x 5: rows Blue, Orange, Red, Purple, Tribal
  Chief, as row = mask - 1; 8 facings) -- its placement over the head is `docs/picture-studio-vv3.md`'s, checked against the companion's C
  source, not emulated.
* **Hospital (Fix Vanilla Bugs)** `assets/vv3_hospital/vvfp_hospitalFixed.png`: the stock sheet with the table legs
  redrawn, cut 3 x 1 as the game cuts the stock one.
* **Super-Secret Golden Mushroom** `assets/golden_mushroom/golden_mushroom.png`: whole; `vvfp_golden_mushroom.c`
  draws it in place of collectable frame 51 (item `0x66`). Placement not emulated.
* **Origins icons** 101-110: the patcher's menu icons, read from inside the shipped VV3 companion
  ("VVFP VV3 Safe Upgrades.dll", each icon's largest image); never drawn by the game.
* The Both Factions, Chief Hospital, fruit tree and Fix Huts DLLs carry no pictures.

## Contact sheets

`python scripts/render_asset_contact_sheets.py --game 3` writes `outputs/vv3/<category>.png`.
