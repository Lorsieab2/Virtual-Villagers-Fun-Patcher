# Picture Studio: Everything

Picture Studio's **Everything** tab (Tools tab -> **Picture Studio...** -> Everything) shows every picture each of
the five Virtual Villagers games ships, drawn the way the game draws it, sorted by category. It saves them as
transparent PNGs at the game's size, 2x, 4x or a custom size. The villagers themselves stay on the **From my save**
and **Make your own** tabs ([picture-studio.md](picture-studio.md)).

No game art ships with the patcher. The first time the tab opens for a game, every picture in that game's `Images`
folder is copied (read only) into `Picture Studio Pictures\Everything\<game>` beside the patcher. That copy is
checked against its manifest each time it is used.

## What is listed

Each game lists two kinds of entry:

- **Composed entries** come from each game's table, `src/vv_assets_vv<n>.py`. They show what the game assembles
  on screen, for example:
  - a creature's animation frames;
  - a hut at each build stage, a puzzle object in each state, a fruit tree from empty to full;
  - the island assembled from its tiles;
  - the Tech screen's bars: empty (uncoloured), each level filled, and the whole screen;
  - meters at several fill levels;
  - dialog panels at the game's sizes and buttons in each state;
  - the title, loading and help screens.

  Each picture is a *plan*: the blits the game makes, in its order. A blit is a sheet, a cell, a place, a scale and
  an alpha. The plans are proven against the game's own draw code (below).
- **Source sheets** list every picture file of the game, cell by cell (`vv_pictures_assets.source_sheet_assets`).
  - A sheet the game builds is cut as the game's own sprite constructor cuts it. Each game's `sheet_table()` holds
    those constructor calls, read from the stock executable.
  - A picture the game never loads is marked **(unused)**. It is cut at the sheet's own clear gaps and noted
    "position not from the game".
  - A file a patch put in a patched game's `Images` folder is the patcher's, never unused.
  - Nothing is missed: a file no table knows is still listed.

Labels:

- Art the game ships but never draws is marked **(unused)**, and it is also listed under **Unused**.
- The patcher's own art is marked **(patcher)**. That covers the Origins masks and icons (read from inside the
  shipped Origins DLLs), A New Home's grey hair, the Golden Mushroom, the Visual Mods and Guardians of Isola
  replacement art (cut as the game cuts the picture it replaces), the Sort By art and the masks. It comes from what
  the release ships: `assets\`, or the companion DLLs.

The categories, in the order the tab shows them:

| Order | Categories |
|---|---|
| World | Creatures, Buildings and objects, Puzzles, Collectibles, Plants and food, Villagers (shadow, selection circle, skeleton, ripple), Scene |
| Interface | UI: Tech screen, UI: Meters, UI: Panels and buttons, Icons, Cursors, Fonts and digits, Effects, Screens |
| Other | Patcher art, Unused, Source sheets |

## Saving

- **Save PNG...** saves the picture shown.
- **Save all of this...** saves every picture of the entry picked.
- **Save all...** saves every picture of the category chosen beside it, or of every category.
- Every save goes into a new folder, with one folder per category (and group). An entry with several pictures gets a
  folder of its own.
- The window's size choice applies: game size, 2x and 4x are crisp; a custom size is smooth. So does the "Small
  clear margin" choice.

## How it is proven

Each game's page gives the addresses, rules and case counts:
[A New Home](picture-studio-assets-vv1.md), [The Lost Children](picture-studio-assets-vv2.md),
[The Secret City](picture-studio-assets-vv3.md), [The Tree of Life](picture-studio-assets-vv4.md),
[New Believers](picture-studio-assets-vv5.md).

- **The sprite table** (each game's `sheet_table()`):
  - The whole stock executable is scanned for every call to the engine's sprite constructors and picture loaders.
    The scan checks that every call is accounted for and every picture name the exe holds is built.
  - Where a name or a number is computed (the island's `MapX%dY%d.jpg` tiles, sprite tables), the game's own code is
    run in Unicorn to get the values.
  - The game's own cell-cut function is run on every cell of every sprite, and each result must equal
    `vv_picture_image.Atlas.cell`.
- **Composed entries** (`tests/test_assets_vv<n>.py`):
  - The game's own draw function for the object is run in Unicorn on the stock executable. The sprites are built by
    the game's constructors; only the picture loader is replaced, by one that gives each sheet its real size.
  - Every blit it makes must equal the plan, in order: sheet, cell, place, scale and alpha.
  - Entries that are only cut as built, not placed by an emulated draw, say so in their note.
- **JPEG pictures** (`src/vv_jpeg.py`, `tests/test_vv_jpeg.py`):
  - The games load JPEGs with SDL2_image, which hands them to libjpeg 9 (13-Jan-2013, `libjpeg-9.dll`) at its
    defaults.
  - `vv_jpeg` decodes them the same way: the integer IDCT; chroma scaled up by libjpeg 9's 16 x 16 IDCT rather than
    upsampled; libjpeg's YCbCr tables; the Adobe transform flag; progressive scans and restart intervals.
  - The test runs the game's own `libjpeg-9.dll` in Unicorn, driven exactly as SDL2_image drives it
    (`SDL2_image.dll` 0x10003510). On all **238 distinct JPEGs of the five games**, every pixel is the same.
- **Interlaced PNGs**: a few unused sheets are Adam7-interlaced. They are de-interlaced exactly; checked against
  Pillow on every interlaced file the games ship, and by a synthetic test.
- **The blitter**: scaling, surface alpha and layering are the existing Picture Studio rules
  ([picture-studio.md](picture-studio.md)), proven there.
- `tests/test_picture_studio_assets.py` checks the following:
  - The framework, the cache and the window tab, on synthetic pictures.
  - The release ships the code but no game picture, and every piece of the patcher's art it reads from what ships.
  - With `research/game-images`: every picture file of every game is listed, and every composed entry draws inside
    its sheet.

Without Unicorn, pefile, capstone, the stock executables, the games' DLLs or their pictures (as on CI), the tests
that need them skip.

## What is not drawn, or not proven

The per-game pages say this entry by entry. In short:

- **Filled rectangles and tints are not drawn.** These are things the game paints, not pictures it blits: the
  loading bar's and bamboo meter's colour fills, the loading screen's wash, and the disabled buttons' pixel tint.
- **Text and captions are not composed.** The fonts are listed glyph by glyph or whole, but text drawn with them is
  not.
- **Moving scenes are shown as cells.** The sea, particles, birds' and creatures' paths, and fades over time are
  not composed. Their sheets are listed frame by frame; which frame plays when is not traced for most creatures.
- **Some placements are not emulated.** The Golden Mushroom's offset and the patcher masks' places are read from
  the companions' source, not emulated. A few screens' fixed art is placed by call arguments read from the exe, not
  by running the screen's draw.
- **Some names are numbers.** Where the game's own name for a row or state was not traced, the label says "Skill
  bar 1", "frame 2" and so on rather than guessing.
- **Some masked story pages are listed separately.** The Secret City and The Tree of Life combine `*mask.jpg`
  story pages with their pages in code that was not found, so the pages and masks are listed whole and separately.
- **On screen, the game blends onto its opaque scene.** On a transparent picture, the overlap is the PNG's own
  straight-alpha blend (as for the villagers).
