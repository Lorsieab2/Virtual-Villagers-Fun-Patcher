# Picture Studio

Picture Studio (Tools tab -> **Picture Studio...**) draws the villagers of a save, and villagers you
make yourself, exactly as each of the five Virtual Villagers games draws them, and saves them as
transparent PNG pictures. It is the Virtual Villagers counterpart of the Fish & Plant Tycoon Fix
Patcher's Picture Studio and is built the same way: pure Python (no Pillow, no Unicorn at run time),
no game art shipped, every drawing rule ported from the game's own draw code and proven against it by
emulating that code on the vanilla executable.

## The window (`src/vv_picture_studio.py`)

- **From my save**: the game, a save folder under `Documents\LDW` and a save (read only). The list
  shows everyone the save holds, grouped: Villagers, Bodies awaiting burial, The Lost Children's
  Esteemed Elder statues (the save's own and the Elder Totems patch's), New Believers' Heathens.
  Each is drawn with what the save and the patcher's own files say: head, body, sex, age (and so the
  life stage and the child scale), dead or alive, the Origins cosmetic mask (`Village Masks - Save
  <S>.dat`, followed to its villager as the companion's next load does), Change Appearance's head
  look (`Head Looks - Save <S>.dat`), New Believers' heathen faction and mask colours, The Secret
  City's Tribal Chief, A New Home's Golden Child and Grey Hair at 55 (on when the game folder holds
  its two pictures). The save does not keep a villager's pose, direction, frame, carried item or
  head turn, so those are picked under the picture (each renderer's `saved_fields()`).
- **Make your own**: one tab per subject the renderer offers (a villager; The Lost Children also an
  Esteemed Elder statue), one picker per field: sex, life stage and age (children year by year),
  every head row and body row of the game's sheets, mask, head look, pose, direction, frame, head
  turn, carried item, litter, shadow... Choices marked **(patcher)** are the patcher's own art.
- **Saving**: the picture shown, cut to its drawn pixels with a small clear margin (or none), at the
  game's size, 2x or 4x (crisp, nearest pixel) or any width and height (smooth). **Save all in this
  group...** writes every member of the group picked; **Save the whole village...** writes everyone,
  each group in its own folder, inside a new folder.
- **The pictures**: the first time a game folder is found (the patcher window's game folders, or
  **Find game...**), the sheets and drawing tables the renderer needs are copied (read only) into
  `Picture Studio Pictures\<game>` beside the patcher, checked against a manifest, and used from
  then on. The patcher's own art (mask atlases, A New Home's grey heads) is read from `assets\` or
  from the companion DLL the release ships it in.

Nothing is written but the PNGs the player saves and the picture cache.

## The renderer interface

One module per game, `src/vv_pictures_vv<n>.py`, found by name:

```python
GAME: int
def required_files() -> list[str]          # every Images\ file it reads from the player's game
def required_data_files() -> list[str]     # optional: Assets\ files (The Tree of Life, New Believers: animpts.dat)
def patcher_art() -> dict[str, Path]       # the patcher's own art it reads from assets\
def load(source) -> Renderer               # source.read(name) -> bytes | None

class Renderer:
    game: int
    problem: str                           # "" when the art is there
    def saved_items(folder, slot) -> list[SavedItem]
    def saved_fields() -> tuple[Field, ...]                 # the pose pickers for From my save
    def render_saved(folder, slot, item_id, **pose) -> Image
    def plan_saved(folder, slot, item_id, **pose) -> list[Draw]
    def custom_choices() -> list[Subject]
    def render_custom(spec) -> Image
    def plan_custom(spec) -> list[Draw]
```

A plan is the list of blits the game makes, in its order: `Draw(file, rect, x, y, scale, alpha)`.
The tests compare plans with the blits recorded from the game's own code (`Draw.key()`).

## Shared pieces (`src/vv_picture_image.py`, `src/vv_pictures_common.py`)

- **Atlas**: the engine's sprite atlas -- one sheet, or a grid of sheets named prefix + across +
  down (`male_bodies00.png`, `male_bodies10.png`, ...) -- and its cell cut (A New Home `0x409F90`:
  cell size from the summed sheet sizes, the sheet chosen by column/row division, wrapping past the
  last sheet, the place clamped). The other four games use the same code at their own addresses; each
  game's tests check it.
- **Centring and scale**: a child is drawn at an integer percent turned into a 32-bit float (`fild`
  x 0.01f); the place-scaled routine (`0x407ED0`) centres it on the unscaled cell with the rounded size.
- **The blitter** (A New Home `0x403D70`, the same in every game): unscaled, the cell's own pixels;
  scaled down, each destination pixel is the plain average of a box of source pixels (every channel,
  alpha included, truncated), the boxes laid out by a double-precision position starting half a step
  before the cell; a surface alpha A becomes the byte `ftol(A x 255 + 0.5)` and each pixel's alpha
  `(a x A + 127) >> 8`. Proven pixel for pixel by running the game's blitter in Unicorn **with the
  x87 at Windows' 53-bit precision** (`FPCW 0x027F`): the emulator's default 64-bit precision moves
  some box edges.
- **On a transparent canvas** the blits are combined with straight-alpha "over". The game blends onto
  its opaque scene: unscaled opaque draws go through SDL's own blitter (not emulated), and a faded
  draw darkens the scene by at most one level under fully clear pixels, which a transparent picture
  cannot show. The places, cells, scales and alphas are proven; the overlap arithmetic is the PNG's.
- **The save** (`vv_pictures_common.read_village`): the records the game loads (the log checker's own
  reading, `scripts/vvfp_consistency_check.py`), with the Origins masks (the checker's
  `read_mask_file` + `mask_follow`, The Secret City by identity) and the head looks
  (`native/vvfp_head_look/head_look_store.inc`: each look goes to the one villager with its stored
  identity, never guessed when two share it).

## What each game covers, and how it is proven

Each game's own page has the drawing rules with their addresses, the proofs and the gaps:
[A New Home](picture-studio-vv1.md), [The Lost Children](picture-studio-vv2.md),
[The Secret City](picture-studio-vv3.md), [The Tree of Life](picture-studio-vv4.md),
[New Believers](picture-studio-vv5.md).

| Game | Draw code ported | Parts | Life stages | Poses | Patcher art | Emulated proof |
|---|---|---|---|---|---|---|
| A New Home | village compositor `0x437790` | heads 0-19, bodies 0-19, both sexes; action sheets; every carried item (15, and the Golden Mushroom) | child (body age/7+50 %, head age/14+80 %), adult, elder (Grey Hair), dead (skeleton), the Golden Child | walk (4 directions x 8 frames x 7 head facings), bent over, standing at work, sitting, swimming, the Golden Child's action | Origins masks (`assets/origins/mask_atlas.png`), Grey Hair at 55, head look | 1,067 compositor states; 276 on the patched exe with the real mask hooks; 264 with the real Grey Hair DLL; atlas cut, centring and blitter |
| The Lost Children | village compositor `0x445B50` | heads 0-29 (young and old), bodies 0-29, actions; every carried item (26 + 54 collectables) | child, adult, elder (old head from 55), dead (skeleton), Esteemed Elder statues (8) | walk, bending, sitting, arms out, two in-the-air poses, resting, swimming | Origins masks (from the shipped Origins DLL), head look, Elder Totems statues | about 13,300 records on the stock exe; about 4,800 on the patched exe with the real mask code |
| The Secret City | villager handler `0x4605F0` (+ action overlay) | heads 0-29 (young and old), bodies 0-29 (29 = the Tribal Chief's robe); every carried item (52 + 54 collectables) | child (body age/700+0.5, head (age/14+80)/100), adult, elder, dead (skeleton) | 25 animation frames (walk 17-24 in 4 directions, 17 action poses), 8 head facings, height, swimming | Origins masks (ported from the companion's `VV3WorldMaskDrawAt`), head look | about 6,000 cases on the stock exe through the game's own resource table, atlases, camera and wrappers |
| The Tree of Life | village figure `0x467DA0`, Villager Details figure `0x45F550` | heads 0-29 (`00` young, `10` old), bodies 0-29 (29 = chief outfit); every carried item (70 + 54 collectables) | child (every year), adult, elder, dead (skeleton), ghost (60 %) | 8 walking steps x 4 directions, 17 action poses, held, standing in water; the Details portrait (3 facings, an expecting mother's babies) | Origins masks in the village and the Details portrait, head look | 2,304 combined states plus every pose x direction, skeletons, ghosts, water, items; masks on the patcher's own bytes; Details figure |
| New Believers | village draw `0x4720E0` | heads 0-29 (young and old halves), bodies 0-29, actions; every carried item (80 + 54 collectables) | child (per age unit), adult, elder, dead (skeleton, the save's frame) | walk (8 x 4), action poses 32-48, 8 head turns, swimming | the native heathen masks (Blue, Orange, Red, Purple, Chief), the Origins cosmetic mask (as the patcher's mask flip makes the game draw it), head look | the real loader on the real `animpts.dat` (all 50 x 4 records); over 1,300 records through `0x4720E0` |

## Carried items (`src/vv_pictures_carried.py`)

**Carrying** lists every item a villager can be drawn carrying, in all five games, named the way the game
or the patcher's Game Mechanics pages name it (The Secret City's names are its own eCarrying_* list), with
the babies carried (one, twins, triplets: the game draws the item again for each). Each game's page has
the full list with the jobs that carry each item and the addresses:

| Game | Items the game carries | Unused pictures (offered, marked) | Blank | Patcher |
|---|---|---|---|---|
| A New Home | 14 | 1 | 0 | Golden Mushroom |
| The Lost Children | 68 (18 + 48 collectables and 2 mushrooms) | 8 | 3 | Golden Mushroom (the game's own picture) |
| The Secret City | 102 (52 + 48 collectables and 2 mushrooms) | 0 | 3 | Golden Mushroom |
| The Tree of Life | 94 (44 + 50) | 26 | 3 | Golden Mushroom |
| New Believers | 82 (32 + 50) | 48 | 3 | Golden Mushroom |

- **In the game**: the game's own code carries it (every store of the carry field was found and each
  number traced to its job; the status texts are the game's).
- **"(unused in the game)"**: the picture is on the item sheet and the game's carry draw draws it -- the
  Studio draws it with that same code -- but nothing the game runs carries it: no store gives the number,
  or only code that never runs (DEAD: The Tree of Life's and New Believers' "Hiding something" / "Spring
  cleaning", which nothing starts). Each game's page gives the reason per item.
- **"(blank picture, unused in the game)"**: the collectables sheets' last three cells are empty.
- **"(patcher)"**: the Super-Secret Golden Mushroom. In A New Home, The Secret City, The Tree of Life and
  New Believers "VVFP Golden Mushroom.dll" draws the patcher's golden_mushroom.png where the game would
  draw the golden frame (A New Home 6 right and 2 down, the others 7 right, New Believers also 1 down); The
  Lost Children's own sheet has the picture.
- **From my save**: no game keeps the carried item in its save. On loading each game gives a villager who
  is expecting (or nursing) the baby and everyone else nothing, so the first choice, "As the game shows it
  after loading", draws exactly that; the babies carried come from the save's litter.
- **Proof**: each game's `test_every_carried_item` runs the game's own draw on the stock executable for
  every item in the list, in the four directions and the carrying poses, and requires every blit to be the
  plan's; the Golden Mushroom's plan is the stock blits with the companion's swap (`tests/carried_golden.py`,
  its offsets read from the companion's source). `tests/test_pictures_carried.py` pins the list and the
  facts read from the executables.
- **Not offered**: numbers that are no picture of their own (A New Home's 16-18 draw cells 1-3 again; The
  Lost Children's 0x1B-0x1D, which nothing stores), and the empty cells of carrying.png no number reaches
  (The Tree of Life's 70-77, New Believers' 80-90).

## Not covered, or not proven

Said plainly, game by game in each page; in short:

- **Screens other than the village**: the Villager Details portrait is drawn for The Tree of Life only.
  A New Home, The Lost Children, The Secret City and New Believers draw their village figure; their
  Details portraits (enlarged draws, which The Lost Children's enlarging blit does not match the
  nearest-pixel model for at 150 %, 172 % and 186 %), the map overview and dialog figures are not drawn.
- **Transient effects** are left out: the selection ring and splash/sparkle particles (A New Home draws
  its selection circle as an option), New Believers' colour flash and heathen sparkle, a ghost's fading.
- **What the save does not keep** (pose, direction, frame, head turn, height) is picked, never guessed;
  some pose names describe the art rather than the game's own activity names.  The carried item is not
  saved either; From my save offers what the game gives back on loading (the baby while expecting).
- **Masks**: The Secret City's mask placement is checked against the companion's C source, not by
  running the companion; New Believers' cosmetic mask is proven by giving the emulated stock exe the
  flipped fields, not by running the patched exe.

## Patcher bugs found along the way (fixed in v1.35.86)

Picture Studio's emulation of the games' draw code found three bugs in shipped patches; each is fixed
at its root and the Studio draws what the FIXED game draws:

- **The Lost Children, Origins masks**: the mask stubs' list of head sheets held `female_actions`
  (0xE574A0), so a woman whose body value equals her head value got a second mask over her body in
  action poses, and a girl bending or sitting got one whatever her body. The list is now the four head
  atlases (`scripts/build_vv2_mask_stage2.py`); `tests/test_vv2_mask_head_only.py`.
- **The Lost Children, head look**: `VVFP Head Look.dll` spliced only the swimming head's age compare,
  so every other village head still switched to the old head at 55. The other poses compare
  `cmp ecx, ebx` (too short to splice), so the DLL now splices the thirteen age loads before them;
  `tests/test_vv2_head_look_village.py`. The Secret City, The Tree of Life and New Believers were
  checked: each village draw picks the head sheet with compares the DLL already splices (none of their
  callees compares the age with 1,100). A New Home's old heads are Grey Hair at 55's, drawn at the head
  thunks for every pose.
- **The Tree of Life, Change Appearance preview**: `appearance_draw_cell`
  (`native/vv4_origins_icons/vv4_origins_icons.c`) built the body sheet's name from the old-head digit
  (for the head look Old, or Auto at 55 and over), but a body sheet's first digit is its place in the
  body sheets' grid, so the body preview showed another direction's frame. The body is now always read
  from the sheet the game draws it from; `tests/test_vv4_appearance_preview_sheets.py`. The other games'
  previews take only the head picture from the look (their bodies are one sheet per sex).
