# Picture Studio, Everything tab: A New Home (Virtual Villagers 1)

`src/vv_assets_vv1.py` lists every picture A New Home builds and how the game draws it. The framework is
`src/vv_pictures_assets.py`. `tests/test_assets_vv1.py` proves the rules by running the game's own code. Every
address below is in the stock `Virtual Villagers - A New Home.exe` (`research/stock-executables`).

## How the game loads pictures

A scan of the whole executable finds six ways a picture is loaded, and nothing else:

| entry | what it builds | calls |
|---|---|---|
| `0x40A070(name, cols, rows)` | one sheet cut into cells | 73 |
| `0x409ED0(name)` | one whole picture | 40 (one is inside 0x40A070, one is the island's tile loop) |
| `0x40A0F0(prefix, ".png", across, down, cols, rows)` | a grid of sheets (the villager bodies and actions) | 4 |
| `0x4019B0(id, name, x, y, parent, flag)` | a button; its sheet is `0x40A070(name, 3, 1)` at 0x401712 | 55 |
| `0x402080(name, glyphs, flag)` | a font: ".png" is added and the picture is loaded whole at 0x402319 | 2 |
| `0x4115C0` | the island: 16 JPEG tiles, `"%sX%01dY%01d.jpg"` with `"Map"` | 1 loop |

The sheet loader `0x40A530` loads exactly the name it is given. It picks PNG, JPG or BMP by the ending. Its only
callers are the two constructors and the font loader. Some pictures come as a pair (bxshtBG, overview_bg,
tech_bg, VD_BG, as .jpg and .png). Of each pair, only the file the code names is ever read.

Cells are cut by `0x409F90` (`pi.Atlas.cell`). A frame `n` of a sheet with `c` columns is the cell
(`n % c`, `n / c`), as `0x4087B0` divides it.

Sprites are drawn through the graphics object's methods:

- 0x4093A0 whole;
- 0x4093B0 whole, faded;
- 0x4093C0 cell;
- 0x4093D0 frame;
- 0x4093E0 frame, faded;
- 0x4093F0 whole, scaled;
- 0x409410 cell, scaled;
- 0x409420 frame, scaled.

They end in the software blitter `0x403D70` (scaled or faded) or in SDL's `0x403D00` (plain). A scaled draw is
first centred by `0x407ED0`.

## How it was proven

Each composed asset below is one of the game's draw functions, run in Unicorn on objects built with the game's
own constructors. The sheet loader is replaced by one that gives every file its real size. Every blit is
recorded and must equal the module's plan, in order. A blit's key is its sheet, source rectangle, place, scale
and surface alpha. A full run of `tests/test_assets_vv1.py` compares **2,251 draws**:

- 460 on the island;
- 170 of creatures and effects;
- 1,564 of the interface;
- 57 of screens.

It also checks:

- 3,000+ cells cut by `0x409F90`;
- every constructor call of the executable.

## Categories

### Scene

- **The island** (`0x4115C0` builds the tiles, `0x411550` draws them). The tiles are MapX0Y0.jpg to MapX3Y3.jpg,
  each 512 x 512 at (x * 512, y * 512) minus the camera, x inside y. Emulated at four camera places.
- **The island with its objects.** These are the tiles, then the scene list, the order the village frame
  `0x4224A0` draws them in (0x411550, then 0x415E60, then the effects and the villagers). There are two frames:
  - a new game (food 100 and a full berry bush, which are chosen values);
  - everything built and solved.
- **The map** (`0x42A5A0`). overview_bg.jpg at (0, 0), then the scene list through `0x415ED0`. Each object goes
  at `(x - cell width) / 4 + dx`, `(y - cell height) / 4 + dy` (C division), at 25% scale. The offset `dx, dy`
  depends on the object:
  - the farm (0x80, 0x22);
  - the lagoon (0x96, -3);
  - the crops (0xAA, 0x37);
  - the blockage (0xAF, 0x38);
  - the garden (0x96, 0x12);
  - the temple (0x96, 0x1B);
  - the berries (0xB4, 0x34);
  - anything else (0xAF, 0x29).

  Tools, food and carried items 13 and 14 are left off the map. The game clips the map to its area, which is
  not done here. The villagers on the map (`0x4388E0`) are left out.

### Buildings, puzzles, plants

These are the island's objects. `0x416380` rebuilds the scene list from the game state at every change. It reads
the fields of the game object, listed as `S_*` in the module. `0x415E60` then draws each listed object: whole,
or its frame, at its place minus the camera. `island_objects()` is that function line for line. **227 game
states** were emulated (both 0x416380 and 0x415E60, and the map 0x415ED0 on each). They include every threshold
just under, at and over, every flag, every grave slot and 60 random mixes.

- **Huts 1-3.** A scaffold is drawn while the hut is being built, and a second one past half. Hut 1 shows its
  first scaffold before any work. A finished hut is smallHut.png.
- **Food pile.** stoolfood.png is drawn above 10 food. One of food1/2/3.png is drawn above 50, 400 or 2,000
  food.
- **Berry bush.** The bush itself is painted on the tiles. Nine berry clusters are laid on it, one more above
  each of 0, 150, 300, 450, 600, 750, 900, 1,050 and 1,300 berries.
- **Farm.** farm_after.png is drawn from farming level 2. The first 12 crop plots are drawn when the crops are
  above 400, and 12 more when the crops are not 0.
- **Tools.** tools2.png is drawn from science level 2, and tools3.png from level 3.
- **Beach debris.** Eleven pieces lie on the beach, each until the clearing passes its step. There is also one
  piece of fallen debris at (0x407, 0x1F1).
- **Boulder, Creek blockage** (blocked, being cleared, the lagoon), **Idol** (uncarved, one or two scaffolds;
  nothing once carved), **Temple** (eight scaffolds, then temple_rebuilt.jpg), **Garden**, **Drum**,
  **Treasure chest** (one or two scaffolds, then the chest).
- **Graveyard.** A 10 x 5 grid. Each grave's look is (value + column + row) % 4. Twelve slots bring their own
  grave flowers. Two more flags put down four flowers, and one flower.

### Creatures

- **Butterflies** (`0x412AB0`): butterflygreen.png, 4 x 5. The frame is `wing + colour * 4`, plus 2 when the
  butterfly heads right. A butterfly in state 2 instead gets the +2 when it is one of the even-numbered ones. Each
  is drawn scaled to its own percentage and centred. Emulated for 40 random sets of nine butterflies, each set
  on screen and minus the camera. The assets are drawn at 100%.

### Effects

- **Particles** (`0x41AB20`, layers 0, 1 and 2): waves, the sparkles, dust, blink, bubbles and the rainbow. Each
  frame of the sheet is a frame of the asset. Layer 2 is drawn at its own place, and the others minus the
  camera. A particle with a fixed frame is drawn as that frame, at alpha `1.0 - age * 0.1f`. That value is
  computed at x87 double precision and stored as a 32-bit float. The alpha constant is at 0x4595DC. Emulated
  for 30 random sets of particles over all three layers. Which items the game fades out this way was not
  traced.

### Tech screen

- **Tech screen** (`0x433B20`). tech_bg.png is drawn first. Then each technology's first cell, then its second
  cell from level 2, then its third from level 3. Each cell is 96 pixels to the right of the one before. While
  the screen fades in (stage 3 or less), the cells are drawn at the screen's alpha.

  | technology | picture | level field | place |
  |---|---|---|---|
  | Farming | farming.jpg | 0xA2E4 | (0x62, 0x36) |
  | Medicine | medicine.jpg | 0xA2D4 | (0x62, 0xBF) |
  | Fertility | breeding.jpg | 0xA2DC | (0x62, 0x148) |
  | Construction | building.jpg | 0xA2CC | (0x1A0, 0x36) |
  | Science | science.jpg | 0xA2C4 | (0x1A0, 0xBF) |
  | Spirituality | spirituality.jpg | 0xA2BC | (0x1A0, 0x148) |

  The names are the game's own strings. 45 level sets x 5 fade stages were emulated.
- **Technology bars.** Each bar is shown:
  - empty (uncoloured);
  - at level 1, 2 and 3, its cells joined as the screen draws them.

  Under the cells is the screen's own picture, cut to the bar's area. That cut is a crop, not a picture of its
  own, and the asset says so.
- The research and info buttons are placed where the 0x4019B0 calls in 0x4347E0 put them. The test checks
  those places against the scan. Each button's draw is emulated.

### Meters

- **Skill bars, rows 1-5, and the health bar** (`0x42F500(row, value)`). The value is clamped to 0-100. The bar
  has `(value * 256 / 100) / 16` slices, 16 pixels apart from x 0x1CE:
  - rows 3-7 are blue slices (StatusBarSliceB) at y 0xDF, 0x109, 0x134, 0x15F, 0x188;
  - row 8 is the health bar: the bulb at (0x1A1, 0x58) whenever any health shows, then red slices at y 0x5E.

  Emulated for rows 2-9 at every value from -5 to 105 (888 cases). The skill names were not traced, so the rows
  are numbered.
- **Loading bar** (`0x436FB0`, mode 3). The percentage is clamped to 1-100. The bar has
  `(percent * 320 / 100) / 8` segments of LoadColor.png, and the bamboo frame is drawn again after every
  segment. Under 3%, nothing is drawn at all. Emulated at every percentage from -3 to 105, at two places. In
  modes 0-2 the game fills a coloured rectangle (`0x408150`) and then draws the frame. The fill is not drawn
  here; the test checks that the frame is the only blit and that one fill was made.

### Panels and buttons

- **Dialog frames** (`0x40C670` builds, `0x40C4D0` draws). Each frame is a 9 x 1 tile grid, Green or Orange.
  A tile's size comes from the first cell. A grid is `(tile + size - 1) / tile` tiles across and down, at least
  2 each way.

  It is drawn row by row. The cells are:

  | place | cell |
  |---|---|
  | top-left | 8 |
  | top | 1 |
  | top-right | 0 |
  | left | 3 |
  | middle | 7 |
  | right | 2 |
  | bottom-left | 5 |
  | bottom | 4 |
  | bottom-right | 6 |

  The assets use the five sizes the game asks for: 455 x 400, 360 x 200, 640 x 448, 490 x 350 and 320 x 320.
  Emulated at 29 sizes x 2 colours x 2 places and alphas.
- **Buttons** (`0x4019B0` builds, `0x401340` draws). A shown, enabled button draws frame 0, 1 or 2 of its
  3 x 1 sheet at its place, one frame for each of the widget's three draw entries (0x401620, 0x401630,
  0x401610). They are labelled normal, mouse over and pressed, the usual order. Which input picks each was not
  traced. A disabled button is drawn by a per-pixel colour blend (`0x408C60`) that a plan cannot express, so it
  is left out. empty1.png is fully clear (the title screen's invisible buttons). All 12 button sheets were
  emulated at three places.
- **Options pieces:** the radio buttons and the slider and its handle are listed whole. They are drawn by the
  options dialog `0x428910`, which was not emulated.

### Icons, cursors

- **Job checkmark.** Its five places on the Details screen are read from `0x449140`, not emulated.
- **Tutorial arrows** (`0x435EB0`): listed whole.
- **Hands** (`0x408240` sets the cursor and its hot spot at half its size, `0x409060` draws it). The hand is
  drawn whole with its middle on the mouse. Emulated at three mouse places.

### Villagers

The shadow (opaque, and at 0.5 when held), the selection circle, the skeleton's four frames and the swimming
ripple at alpha 0.4 are listed as separate pieces. Their rules are the village compositor's, proven in
`tests/test_pictures_vv1.py`. Composed villagers are the other tabs.

### Screens

| screen | function | what is emulated |
|---|---|---|
| Splash | `0x431620` | SPLASH_BG.jpg |
| Title | `0x425DF0` | bxshtBG, three cloud layers twice (front opaque, middle 0.7, back 0.4), Boxshtfeat, the lava glow at (2, 0x97) at its alpha, logo1 at (10, 10) |
| Loading | `0x41F570` | bxshtBG, the loading bar at (0xF0, 0x1F4), logo1 at (0xFF, 0x32), ldwLogo at (0x2F, 0x190) |
| Help | `0x41DD00` | puzzles_bg, then page 1-4 or the credits at (0x50, 0x2E), for pages -1 to 6 |
| Puzzles | `0x42D5C0` | solved pictures, then puzzles_bg over them, then the covers of the unsolved ones, for 38 sets |
| You won, story 1 and 2, main panel, villager details, map | `0x41D5E0`, `0x41EBE0`, `0x41F9B0`, `0x449140`, `0x42A5A0` | the first blit (each background at (0, 0)) |

Notes:

- **Title:** the clouds' places and the lava's alpha are one moment of their drift, inside the game's ranges.
  The butterflies are left out.
- **Loading:** the white half-clear rectangle (a fill) is not drawn.
- **Puzzles:** the screen's 16 places are (0x50 + 0xA0 * col, 0x32 + 0x76 * row). Each puzzle is solved or
  covered by its own game-state flag (`PUZZLE_FLAGS`). The pictures are numbered in screen order, because the
  puzzles' names were not traced.
- **The first-blit screens:** only their first blit is proven. Text, villagers and widgets drawn over them are
  not drawn here.
- **Main panel with its buttons:** the buttons are at the places 0x4224A0 gives them, checked against the scan.
- **Villager details with its bars:** each bar is emulated. Their order and the checkmark's place are read
  from 0x449140, not emulated.

### Fonts

ldwBurweed27.png and ldwarialbold.png are listed whole. Their glyph rectangles are tables in the executable
(0x4862A0, 0x486888). Text is not composed.

### Patcher art (labelled "(patcher)")

- **Origins masks** (`assets/origins/mask_atlas.png`, 7 x 5). These are cut as the game's 0x40A070 cuts them.
  Their placement on a head is proven in `tests/test_pictures_vv1.py`.
- **Grey heads** (`assets/vv1_grey_hair`, 7 x 20, the stock head layout). Proven in the same place.
- **Super-Secret Golden Mushroom** (`assets/golden_mushroom/golden_mushroom.png`, under Collectibles).
  `VVFP Golden Mushroom.dll` draws it in place of carrying.png frame 15, moved by (6, 2). That offset is read
  from `native/vvfp_golden_mushroom/vvfp_golden_mushroom.c`, not emulated.
- **Sort By band and radio button** (`assets/sort_by`). They are built 1 x 1 and 3 x 1 by `VVFP VV1 Sort
  By.dll`. Their places on screen are not shown.
- **Origins window icons** (101-110, read from inside the shipped `VVFP VV1 Origins Icons.dll`, each icon's largest
  image). These are shown in the patcher's Origins window, a Windows dialog. The game does not draw them.
- **Visual Mods** (`data/vv1_visual_mods/new/Images`: the restored garden and lagoon, two map tiles). The game draws
  each in place of the picture of the same name, so each is cut as the game cuts that picture
  (`vv_pictures_assets.mod_art_assets`).

## Unused art

Files the executable never names (labelled "(unused)", cut at their own gaps):

- bfg_logo.png, gh_logo.png and mgs_logo.png (the splash screen's other slots are never filled);
- buy_button.png;
- Checkbox.png and CheckboxChecked.png;
- dust.png (dust2.png is used);
- main_wide_button.png (main_wide_button2.png is used);
- StatusBar.png;
- ProcessedHorizBambStrip3.png and ProcessedVertBambStrip1.png;
- canvas_bg.jpg;
- bxshtBG.jpg, overview_bg.png, tech_bg.jpg and VD_BG.jpg (the unread half of each pair).

Every sprite the game builds is drawn somewhere, so the table marks none of them "built, never drawn".

## Left out, and why

| left out | why |
|---|---|
| Text and fonts composed into words | glyph tables not decoded |
| The loading bar's fill modes, the loading screen's veil | SDL fills, not pictures |
| A disabled button's look | a per-pixel blend at 0x408C60 |
| The map's clipping, the villagers on the map | not done here; the villagers belong to other tabs |
| Butterflies on the title screen | they are listed as creatures |
| The options dialog's slider and radio placements | not traced |
| Carried items on villagers | another tab |

Contact sheets: `python scripts/render_asset_contact_sheets.py --game 1` writes `outputs/vv1/<category>.png`.
