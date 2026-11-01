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
