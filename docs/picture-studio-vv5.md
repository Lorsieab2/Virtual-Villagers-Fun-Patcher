# Picture Studio: New Believers (Virtual Villagers 5)

Renderer: `src/vv_pictures_vv5.py`. Proof: `tests/test_pictures_vv5.py`. Addresses are those of the stock
executable (`Virtual Villagers - New Believers.exe`, SHA-256 `92946781...C65D`).

## Where the pictures and numbers come from

* **Sprites.** The game's sprite descriptors (from `0x4CEFBC`; the id is the dword before each name, then
  columns, rows, suffix, sheets across, sheets down). The villager uses
  `0xFC/0xF9` male/female heads (16 x 30 over `*_heads00.png` + `*_heads10.png`: columns 0-7 young, 8-15
  old), `0xFD/0xFA` bodies (32 x 30 over 2 x 3 sheets), `0xFE/0xFB` actions (17 x 30 over 1 x 3 sheets),
  `0x101` `vv5_heathenheads.png` (8 x 5), `0x102` `peep_shadow1.png` (whole), `0x103` `skelly.png` (4 x 1),
  `0x104` `ripple.png` (4 x 1), `0xE8` `carrying.png` (13 x 7), `0xEC` `collectables_small.png` (6 x 9).
  The village manager's copies are set by `0x46F870`. Cells are cut by `0x40AE90`, the same code as A New
  Home's `0x409F90` (`vv_picture_image.Atlas`).
* **Anchors.** Every place comes from the animation table `0x5258B8`, filled by the loader `0x451180`
  from the game's own `Assets\animpts.dat` (three blocks: `0x17E08` bytes at table `+0x7254`, `0x29F0` at
  `+0x1F05C`, `0x2C0` at `+0x21A4C`) and then partly overwritten (`0x4519BD..0x451AEE`: sprite ids and frame
  bases). The renderer reads the same file from the player's game (read only) and applies the same
  overwrites (`AnimTable`). An anim record (`0x1E8` bytes) holds the sprite id, the frame base, 30 neck
  points (`+8`) and 30 body anchors (`+0xF8`), one per body row; a head record the same with one anchor
  per head row; the mask block one (x, y) per head turn and colour.

## The village draw `0x4720E0`

| Step | Rule | Address |
|---|---|---|
| scale | `s = (age/700 + 0.5) x [+0x1CCC]` under 280 age units, else `[+0x1CCC]` (1.0: set at `0x4651B0`, never saved) | `0x466240` |
| head scale | `hs = (age/14 + 80)/100` under 280, else 1.0 | `0x4722F3` |
| place | `P = (X + trunc(20 s), Y + trunc(55 s))` | `0x466350` |
| feet | `Yl = Y` (+20 for poses 40/41, sitting and lying) | `0x472263` |
| pose | `a = pose + 8 x direction` for poses 0-7, else the pose | `0x4722B9` |
| old head | `+8` columns when the age is 1,100 or more (`setl/sub/and`) | `0x4722A2` |
| head anchor | `HA = heads[sex][turn].anchor[head]`, each `trunc(v x hs + 0.5)` | `0x451DA0` |
| shadow | `peep_shadow1.png` at `(P.x - trunc(34 s), P.y - trunc(32 s))`, scale `s`; not in water | `0x4723A5..0x472437` |
| carried item | at `(X, Yl + trunc(18 s))`, unscaled; before the body for directions 0/3/4, after the head otherwise; a litter of 2/3 adds `carrying.png` copies at `(-5, +5)` and `(0, +9)`; not in water | `0x4724C3`, `0x4701C0` |
| body | `B = (P.x, Yl + trunc(55 s)) - anchor x s` of anim `a`, sex, body row; cell (body, frame base) at scale `s` | `0x451D00`, `0x47279C` |
| head | `B + neck x s - HA`; cell (head, turn (+8)) at scale `hs` | `0x451CA0`, `0x4729C3` |
| heathen | body and head through the tinted draw `0x44F4E0` (colour alpha byte 0: no tint, `0x408F40` -> `0x408AC0`); mask row Blue 0 / Orange 1 / Red 2 / Purple 3 (rank 12, 14-16) / Chief 4 (rank 13), column = head turn, at `B + neck - maskanchor`, scale `hs` | `0x472732`, `0x4728C6` |
| swimming | `ripple.png` frame `rand & 3` at `(P.x - 32, Yl + trunc(55 s) - 32)`, alpha 0.4, then the head only at `P' - HA` (pose 41 keeps its body) | `0x472592..0x47264B`, `0x4727CD` |
| dead | `skelly.png` frame `[+0x1B94] mod 4` (C remainder) at `(X, Y)`, scale `s` | `0x472B18` |

Every blit goes through a cell draw (`0x408DA0`/`0x408B70`/`0x408AC0`), the placement `0x407F10` (scale =
integer percentage `trunc(100 x f)` / 100.0, never centred: the flag is 0) and the software blitter
`0x404C40`, which is A New Home's blitter rule: a box-average downscale and the surface alpha
`(a x A + 127) >> 8` (`vv_picture_image.blit_piece`).

## The save

The writer `0x465270` keeps faction `+0x1CEC`, Orange `+0x1CED`, Red `+0x1CEE` at entry `+1..+3`, the rank
`+0x1CFC` at `+0xC`, and the record window from `+0x1B8C` at `+0x10` (so, from the name: `-0x1F`, `-0x1E`,
`-0x1D`, `-0x14`; the skeleton seed `+0x1B94` at `-8`). The pose, head turn, direction, carried item
(`+0x1D0C`, `-1` after a load: `0x46525E`) and per-villager scale are not saved: From my save offers them as
pickers. Titles in the details line follow the owner's list: Heathen Chief, Heathen (colour mask), Retired
Heathen Chief (rank 13, Believer), Former Heathen (orange/red mask) from the colour bytes the conversion
`0x4668B0` leaves; a converted blue Heathen cannot be told from a born Believer.

## The patcher's art

* **Origins cosmetic mask** (a Believer): `scripts/build_vv5_task9_native_actions.py` `mask_flip`, entered
  at `0x472481` (after the shadow), sets faction 1 and Orange (`+0x1CED = 1`), Red (`+0x1CEE = 1`), Purple
  (rank 12), Chief (rank 13) or nothing (Blue) for the villager's own draw; the renderer does the same.
  The masks are the game's own `vv5_heathenheads.png`, read from the player's game.
* **Head look** (`VVFP Head Look.dll`): only the age compare at `0x4722A2` changes; Young / Old set the
  old-head columns directly.

## How it is proven (`tests/test_pictures_vv5.py`)

* `test_table_is_the_loaders`: `0x451180` run in Unicorn on the real `Assets\animpts.dat`; all 50 x 4 anim
  records, 2 x 11 head records and 8 x 5 mask offsets equal `AnimTable`'s.
* `test_every_state_is_drawn_as_the_game_draws_it`: 1,300+ records drawn by `0x4720E0` (every pose 0-48 in
  every direction, head turns, every head and body row, both sexes, child ages 0-279 and adults, 1,099 /
  1,100, heathens of every colour and rank 12-16, the dead with eight skeleton seeds, 7 carried items x 3
  litters x 4 directions, swimming with every ripple frame, poses 40/41 in and out of water); every blit
  (file, cell, x, y, scale, alpha) equals the plan.
* `test_head_look_only_moves_the_age_compare`, `test_cosmetic_masks_are_the_flip` (and the builder source
  check `test_mask_flip_follows_the_builder`).
* `test_scaled_and_faded_pixels`: `0x404C40` on a test picture at 9 scales x 3 cells x alphas.
* `test_sprite_descriptors`, `test_saved_heathen_fields`: read from the executable.

## Text (the Text tab)

New Believers builds two bitmap fonts:

- **Arial Bold**: `ldwarialbold.png`, 1940 x 20, table 0x4C7FE0, 20 pixels a line.
- **Burweed**: `ldwBurweed27.png`, 2384 x 27 (a wider "q"), table 0x4C8F08, 27 pixels a line.

They hold 0x20-0x7E and the Windows-1252 letters and signs from 0xA1 (The Secret City: 0xA2) to 0xFF, accented letters included. Bytes 0x80-0xA0 draw "!". The Text tab makes everything else in the font's style.

The game's text draw is 0x409930 and its centred draw is 0x409EB0. They are run in Unicorn on the stock executable, and every blit is compared with the Text tab's plan (`tests/test_pictures_text.py`). See [picture-studio-text.md](picture-studio-text.md).

## Not covered / not proven

* **The Villager Details portrait** (`0x466C40`, big heads/bodies `bigheads*`, `bigbodies.png`, the
  `0x155` patcher bighead masks): not drawn; only the village figure is offered.
* **Transient effects**: the colour flash `+0x1CDC/+0x1CDD` (the tinted path with a non-zero colour alpha,
  `0x403B50`), the heathen sparkle `+0x1CF4` (random), swimming bubbles (`0x41D460`, random), the selection
  ring and hover highlight (`0x4653D0`, `+0x1BB220`), the fade passes `+0x1F58`/`+0x1CC8 > 1` and the alpha
  override `+0x1CE1`: game states of a moment, not of the villager; never drawn.
* **States the pickers do not offer**: `+0x1CD5` (half shadow, +20), `+0x1D08` 2/6/9 (shadow moved or
  hidden), `+0x1CBC` (lift), directions 4-7 (a walking pose with direction 4+ would read past the 32 body
  columns; the game never sets one that the renderer knows of). The code paths are ported only for the
  values tested.
* **Compositing on a transparent canvas**: the game blends onto the village; overlapping parts are
  combined with ordinary alpha compositing. Unscaled faded draws also darken the screen under fully clear
  pixels by one step in the game -- invisible in a PNG.
* **The cosmetic mask** is proven by giving the emulated stock game the flipped fields, not by running the
  patched executable.
* `Assets\animpts.dat` is read from the game folder the pictures came from (the Studio's picture cache
  copies `Images` only).

## Carried items

Every item a villager can be drawn carrying, as offered under **Carrying** on both tabs (`src/vv_pictures_carried.py`). "Unused in the game" items are drawn with the game's own carry code, which draws any number, but nothing the game runs carries them.

| Number | Name | Status | When the game carries it (or why it never does) |
|---|---|---|---|
| 0 (0x0) | Noni | in the game | Harvesting noni; Harvesting crops; Researching |
| 1 (0x1) | Rock | in the game | Doing exercise |
| 2 (0x2) | Feathers | in the game | Researching (a random pick) |
| 3 (0x3) | Baby | in the game | expecting (heathens too) |
| 4 (0x4) | Wood | in the game | Building; Gathering firewood; Fixing huts; the totems, the mausoleum, the aqueduct, the granary |
| 5 (0x5) | Laundry | in the game | Washing the laundry |
| 6 (0x6) | Bowl of nuts | unused in the game | only the never-started actions Hiding something / Spring cleaning store it (DEAD) |
| 7 (0x7) | Flowers | in the game | Honoring the dead; Researching (a random pick) |
| 8 (0x8) | Fish (carrying.png) | unused in the game | no code stores it |
| 9 (0x9) | Crab | unused in the game | no code stores it |
| 10 (0xA) | Pan | in the game | Panning for gold; Retrieving a pan |
| 11 (0xB) | Body | in the game | Burying the dead |
| 12 (0xC) | Magic fish | unused in the game | no code stores it |
| 13 (0xD) | Brown mushroom (carrying.png) | unused in the game | no code stores it (a carried mushroom is collectables picture 49) |
| 14 (0xE) | Red mushroom (carrying.png) | unused in the game | no code stores it |
| 15 (0xF) | Dry grass | in the game | Gathering dry grass; Researching (a random pick) |
| 16 (0x10) | Coconut | unused in the game | no code stores it |
| 17 (0x11) | Bowl of soup | in the game | Researching (a random pick) |
| 18 (0x12) | Tool | in the game | Building a statue |
| 19 (0x13) | Pot | unused in the game | only the never-started actions Hiding something / Spring cleaning store it (DEAD) |
| 20 (0x14) | Stew pot | unused in the game | no code stores it |
| 21 (0x15) | Big leaf | unused in the game | no code stores it |
| 22 (0x16) | Spear tips | in the game | Building a statue |
| 23 (0x17) | Bounty | unused in the game | only the never-started actions Hiding something / Spring cleaning store it (DEAD) |
| 24 (0x18) | Lab bowl | in the game | Researching (a random pick) |
| 25 (0x19) | Nothing to see (an empty picture) | in the game | Researching (a random pick): the hands look empty |
| 26 (0x1A) | Lab bowl (second picture) | unused in the game | no code stores it |
| 27 (0x1B) | Striped jar | unused in the game | no code stores it |
| 28 (0x1C) | Striped vase | unused in the game | no code stores it |
| 29 (0x1D) | Tool (second picture) | unused in the game | no code stores it |
| 30 (0x1E) | Red amphora | unused in the game | no code stores it |
| 31 (0x1F) | Medicinal plant 1 (orange flowers) | in the game | Studying medicine |
| 32 (0x20) | Medicinal plant 2 (yellow flowers) | in the game | Studying medicine; Scratching for roots (heathens) |
| 33 (0x21) | Medicinal plant 3 (white flowers) | in the game | Studying medicine |
| 34 (0x22) | Medicinal plant 4 (dark leaves) | in the game | Studying medicine |
| 35 (0x23) | Medicinal plant 5 (red berries) | in the game | Studying medicine |
| 36 (0x24) | Red-topped stalk | unused in the game | no code stores it |
| 37 (0x25) | Yellow berry cluster | unused in the game | no code stores it |
| 38 (0x26) | Banana | unused in the game | no code stores it |
| 39 (0x27) | Mango | unused in the game | no code stores it |
| 40 (0x28) | Papaya | unused in the game | no code stores it |
| 41 (0x29) | Gold dust | in the game | Panning for gold |
| 42 (0x2A) | Lit torch | unused in the game | no code stores it |
| 43 (0x2B) | Debris | unused in the game | no code stores it |
| 44 (0x2C) | Flat stone | unused in the game | no code stores it |
| 45 (0x2D) | Red gem | unused in the game | no code stores it |
| 46 (0x2E) | Dark sphere | unused in the game | no code stores it |
| 47 (0x2F) | Red striped pot | unused in the game | no code stores it |
| 48 (0x30) | Leaves | unused in the game | no code stores it |
| 49 (0x31) | Pearl | unused in the game | no code stores it |
| 50 (0x32) | Unlit torch | unused in the game | no code stores it |
| 51 (0x33) | Irregular pearl | unused in the game | no code stores it |
| 52 (0x34) | Hot rock | unused in the game | no code stores it |
| 53 (0x35) | Cloth | unused in the game | no code stores it |
| 54 (0x36) | Yellow fruit | unused in the game | no code stores it |
| 55 (0x37) | Orange fruit | unused in the game | no code stores it |
| 56 (0x38) | Flying fish | in the game | Retrieving a fish |
| 57 (0x39) | Golden fish | unused in the game | no code stores it |
| 58 (0x3A) | Soap | unused in the game | no code stores it |
| 59 (0x3B) | Fish bone | unused in the game | no code stores it |
| 60 (0x3C) | Heat-treated bone | unused in the game | no code stores it |
| 61 (0x3D) | Beetle | unused in the game | no code stores it |
| 62 (0x3E) | Big bowl of noni | unused in the game | only the never-started action Harvesting noni (the other way) stores it (DEAD) |
| 63 (0x3F) | Lei braid | unused in the game | no code stores it |
| 64 (0x40) | Lei | unused in the game | no code stores it |
| 65 (0x41) | Lei flower (orange) | unused in the game | no code stores it |
| 66 (0x42) | Lei flower (purple) | unused in the game | no code stores it |
| 67 (0x43) | Lei flower (white) | unused in the game | no code stores it |
| 68 (0x44) | Frog | unused in the game | no code stores it |
| 69 (0x45) | Twig nest | unused in the game | no code stores it |
| 70 (0x46) | Scientist's necklace piece | in the game | bringing a necklace piece (The Heathen Chief's necklace) |
| 71 (0x47) | Farmer's necklace piece | in the game | bringing a necklace piece |
| 72 (0x48) | Doctor's necklace piece | in the game | bringing a necklace piece |
| 73 (0x49) | Builder's necklace piece | in the game | bringing a necklace piece |
| 74 (0x4A) | Necklace | in the game | Bringing necklace to chief |
| 75 (0x4B) | Red dye | in the game | Putting dye in the pools |
| 76 (0x4C) | Yellow dye | in the game | Putting dye in the pools |
| 77 (0x4D) | Blue dye | in the game | Putting dye in the pools |
| 78 (0x4E) | Smelted gold | in the game | Smelting the gold dust |
| 79 (0x4F) | Golden eye | in the game | Installing the golden eye (The Blind Totem) |
| 80 (0x50) | Lab gear, common 1 | in the game | Collecting science item (children) |
| 81 (0x51) | Lab gear, common 2 | in the game | Collecting science item (children) |
| 82 (0x52) | Lab gear, common 3 | in the game | Collecting science item (children) |
| 83 (0x53) | Lab gear, common 4 | in the game | Collecting science item (children) |
| 84 (0x54) | Lab gear, common 5 | in the game | Collecting science item (children) |
| 85 (0x55) | Lab gear, common 6 | in the game | Collecting science item (children) |
| 86 (0x56) | Lab gear, common 7 | in the game | Collecting science item (children) |
| 87 (0x57) | Lab gear, common 8 | in the game | Collecting science item (children) |
| 88 (0x58) | Lab gear, uncommon 1 | in the game | Collecting science item (children) |
| 89 (0x59) | Lab gear, uncommon 2 | in the game | Collecting science item (children) |
| 90 (0x5A) | Lab gear, uncommon 3 | in the game | Collecting science item (children) |
| 91 (0x5B) | Lab gear, uncommon 4 | in the game | Collecting science item (children) |
| 92 (0x5C) | Lab gear, uncommon 5 | in the game | Collecting science item (children) |
| 93 (0x5D) | Lab gear, uncommon 6 | in the game | Collecting science item (children) |
| 94 (0x5E) | Lab gear, uncommon 7 | in the game | Collecting science item (children) |
| 95 (0x5F) | Lab gear, uncommon 8 | in the game | Collecting science item (children) |
| 96 (0x60) | Lab gear, rare 1 | in the game | Collecting science item (children) |
| 97 (0x61) | Lab gear, rare 2 | in the game | Collecting science item (children) |
| 98 (0x62) | Lab gear, rare 3 | in the game | Collecting science item (children) |
| 99 (0x63) | Lab gear, rare 4 | in the game | Collecting science item (children) |
| 100 (0x64) | Lab gear, rare 5 | in the game | Collecting science item (children) |
| 101 (0x65) | Lab gear, rare 6 | in the game | Collecting science item (children) |
| 102 (0x66) | Lab gear, rare 7 | in the game | Collecting science item (children) |
| 103 (0x67) | Lab gear, rare 8 | in the game | Collecting science item (children) |
| 104 (0x68) | Relic, common 1 | in the game | Collecting a relic (children) |
| 105 (0x69) | Relic, common 2 | in the game | Collecting a relic (children) |
| 106 (0x6A) | Relic, common 3 | in the game | Collecting a relic (children) |
| 107 (0x6B) | Relic, common 4 | in the game | Collecting a relic (children) |
| 108 (0x6C) | Relic, common 5 | in the game | Collecting a relic (children) |
| 109 (0x6D) | Relic, common 6 | in the game | Collecting a relic (children) |
| 110 (0x6E) | Relic, common 7 | in the game | Collecting a relic (children) |
| 111 (0x6F) | Relic, common 8 | in the game | Collecting a relic (children) |
| 112 (0x70) | Relic, uncommon 1 | in the game | Collecting a relic (children) |
| 113 (0x71) | Relic, uncommon 2 | in the game | Collecting a relic (children) |
| 114 (0x72) | Relic, uncommon 3 | in the game | Collecting a relic (children) |
| 115 (0x73) | Relic, uncommon 4 | in the game | Collecting a relic (children) |
| 116 (0x74) | Relic, uncommon 5 | in the game | Collecting a relic (children) |
| 117 (0x75) | Relic, uncommon 6 | in the game | Collecting a relic (children) |
| 118 (0x76) | Relic, uncommon 7 | in the game | Collecting a relic (children) |
| 119 (0x77) | Relic, uncommon 8 | in the game | Collecting a relic (children) |
| 120 (0x78) | Relic, rare 1 | in the game | Collecting a relic (children) |
| 121 (0x79) | Relic, rare 2 | in the game | Collecting a relic (children) |
| 122 (0x7A) | Relic, rare 3 | in the game | Collecting a relic (children) |
| 123 (0x7B) | Relic, rare 4 | in the game | Collecting a relic (children) |
| 124 (0x7C) | Relic, rare 5 | in the game | Collecting a relic (children) |
| 125 (0x7D) | Relic, rare 6 | in the game | Collecting a relic (children) |
| 126 (0x7E) | Relic, rare 7 | in the game | Collecting a relic (children) |
| 127 (0x7F) | Relic, rare 8 | in the game | Collecting a relic (children) |
| 128 (0x80) | Brown mushroom | in the game | Picking a mushroom (children) |
| 129 (0x81) | Red mushroom | in the game | Picking a mushroom (children) |
| 130 (0x82) | Golden Mushroom | patcher | Picking a mushroom (Super-Secret Golden Mushroom) |
| 131 (0x83) | Collectables picture 52 | blank picture, unused | the game refuses it (0x41375B: nothing above 0x82) |
| 132 (0x84) | Collectables picture 53 | blank picture, unused | the game refuses it |
| 133 (0x85) | Collectables picture 54 | blank picture, unused | the game refuses it |

The carry field is record +0x1D0C (-1 = nothing). Every store, read from the stock exe:

- **The setter** SetCarrying 0x466420 (it asks the listener registry 0x413750, which refuses anything above
  0x82, 0x41375B) with 11 callers, and -1 at 0x46525E (the record reset), 0x46645A, 0x468675 and 0x468967.
  Step opcode 0x12 carries its number (0x473C90, and the fast-forward 0x4754D2); only 0x474D80 builds it
  (76 call sites, each resolved to its action).
- **Reached**: each step belongs to an action registered at 0x452C20 / 0x452C40 and started by 0x465580
  (directly, through the redirector 0x4716D0, or through a shared tail). The golden eye (79, action 0xB7
  "Installing the golden eye") is started by dropping a villager at The Blind Totem: 0x479C19 `push 0xB7`
  jumps to the shared start 0x479CFF -> 0x465580 when the puzzle is at its last step (0x479BE9..0x479C06).
- **Collectables**: a child dropped on one (0x413660 -> actions 35 and 36, children only) carries its
  number: 0x50-0x67 Lab gear and 0x68-0x7F Relics (8 common, 8 uncommon, 8 rare each), 0x80 / 0x81 the brown
  and red mushrooms; 0x82 only with the Super-Secret Golden Mushroom patch. 0x83-0x85 are blank cells the
  setter refuses.
- **DEAD**: actions 0x5B "Hiding something" and 0x5C "Spring cleaning" (one of 0, 1, 2, 4, 5, 6, 15, 18, 19,
  23) and action 0x82 "Harvesting noni" the other way (62) are registered but never started (no start site
  or shared tail pushes them), so the bowl of nuts (6), the Pot (19), the Bounty (23) and the big bowl of
  noni (62) appear only there. The patcher's Story Upgrades can start any action, and so can make them
  appear.
- **Unused**: the other pictures marked unused are on carrying.png (much of it The Tree of Life's sheet) but
  nothing stores their number; cells 80-90 are empty art no number reaches.
- **The Golden Mushroom**: the item draw 0x4701C0 draws through 0x44F380, where "VVFP Golden Mushroom.dll"
  draws golden_mushroom.png, 7 right and 1 down, for collectables frame 50 (the village's sheet and the
  collectables manager's are both 0x44FA30's sprite for id 0xEC).
- **The save** (0x465270) keeps the record windows only, not +0x1D0C: an expecting villager (+0x1C4C, name
  + 0xB0) gets the baby back from the AI tick or Stop (0x466470, 0x47356D; a Heathen too). The litter +0x1C50
  (name + 0xB4) is saved, and nothing clears it at the birth: a mother of twins carries two of whatever she
  holds until she conceives again (derived from the complete list of stores; not seen in a running game).

**Proven** by tests/test_pictures_vv5.py `test_every_carried_item`: the game's own draw, run in
Unicorn on the stock executable, blits every item above in each of the four directions and in every pose
that draws the item (walking with twins and triplets, the work poses, a child) exactly as the plan says;
for the Golden Mushroom, the plan with the patcher's picture is the stock blits with the companion's swap
(tests/carried_golden.py, the offsets read from its source). The list itself is pinned by
tests/test_pictures_carried.py.
