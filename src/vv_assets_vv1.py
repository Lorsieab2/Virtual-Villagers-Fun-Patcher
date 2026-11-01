"""Picture Studio's Everything tab for A New Home (Virtual Villagers 1): every picture the game builds and how it
draws them (src/vv_pictures_assets.py is the framework; docs/picture-studio-assets-vv1.md says how each rule was
read from the stock executable and proven; tests/test_assets_vv1.py runs the game's own draw code on them).

Every address is in the stock "Virtual Villagers - A New Home.exe" (research/stock-executables).

THE SPRITES (sheet_table).  The engine builds a sprite in one of these ways, and a scan of the whole executable for
every call to each finds the sprites below and nothing else:
  * 0x40A070(name, cols, rows): one sheet cut into cells (73 calls);
  * 0x409ED0(name): one whole picture (40 calls; one is 0x40A070's own, one is the island's tile loop);
  * 0x40A0F0(prefix, suffix, across, down, cols, rows): a grid of sheets (the villager bodies and actions);
  * 0x4019B0(id, name, x, y, parent, flag): a button, whose sheet is built at 0x401712 as name, 3 x 1 (55 calls);
  * 0x402080(name, glyphs, flag): a font: ".png" is added to the name and the picture is loaded whole at 0x402319;
  * 0x4115C0: the island, 4 x 4 JPEG tiles named "%sX%01dY%01d.jpg" with "Map" (MapX0Y0.jpg ... MapX3Y3.jpg).
The sheet loader 0x40A530 loads exactly the name it is given (PNG, JPG or BMP by the name's ending): of the
pictures that come as a pair (bxshtBG, overview_bg, tech_bg, VD_BG .jpg and .png) only the one named is ever read.

THE DRAWS.  Every sprite is drawn through the graphics object's methods (0x4093A0 whole, 0x4093B0 whole faded,
0x4093C0 cell, 0x4093D0 frame, 0x4093E0 frame faded, 0x4093F0 whole scaled, 0x409410 cell scaled, 0x409420 frame
scaled), which end in the software blitter 0x403D70 (scaled or faded) or SDL's 0x403D00 (plain).  A "frame" n of a
sheet of c columns is the cell (n % c, n / c).  The composed assets below are each one draw function of the game
run on chosen state; the module's plans are that function's blits in its order (tests/test_assets_vv1.py).
"""
from __future__ import annotations

from pathlib import Path

import vv_picture_image as pi
import vv_pictures_assets as va
from vv_pictures_assets import Asset, Frame, SheetSpec

GAME = 1
ROOT = Path(__file__).resolve().parents[1]
EXE_NAME = "Virtual Villagers - A New Home.exe"

# ------------------------------------------------------------------ the engine's sprite constructors

CTOR_ONE, CTOR_WHOLE, CTOR_GRID = 0x40A070, 0x409ED0, 0x40A0F0
CTOR_BUTTON, BUTTON_SHEET_SITE = 0x4019B0, 0x401712
CTOR_FONT, FONT_LOAD_SITE = 0x402080, 0x402319
TILE_BUILDER, TILE_SITE = 0x4115C0, 0x4116E8
SHEET_LOADER = 0x40A530

# Every 0x40A070 call: (name, cols, rows, call sites).  Where the game picks one of two names at one call (the
# dialog frames' colour), both are listed with that call.
ONE_SHEETS = (
    ("butterflygreen.png", 4, 5, (0x412E17,)),
    ("GreenDlgTileGrid.png", 9, 1, (0x413681, 0x41557B, 0x41594B, 0x427170, 0x429872, 0x431BAE, 0x435FF1,
                                    0x436D04)),
    ("OrangeDlgTileGrid.png", 9, 1, (0x413681, 0x41557B, 0x41A555, 0x427170, 0x42879E, 0x429872, 0x42D1D5,
                                     0x431BAE, 0x436D04)),
    ("scaffolding.png", 1, 1, (0x4172FE,)),
    ("smallHut.png", 1, 1, (0x41733A,)),
    ("food1.png", 1, 1, (0x417372,)),
    ("food2.png", 1, 1, (0x4173AA,)),
    ("food3.png", 1, 1, (0x4173E2,)),
    ("carrying.png", 15, 1, (0x41741A, 0x41ADB0, 0x43C26E)),
    ("berry1.png", 1, 1, (0x417452,)),
    ("berry2.png", 1, 1, (0x41748A,)),
    ("berry3.png", 1, 1, (0x4174C2,)),
    ("berry4.png", 1, 1, (0x4174FA,)),
    ("berry5.png", 1, 1, (0x417532,)),
    ("berry6.png", 1, 1, (0x41756A,)),
    ("berry7.png", 1, 1, (0x4175A2,)),
    ("berry8.png", 1, 1, (0x4175DA,)),
    ("berry9.png", 1, 1, (0x417612,)),
    ("stoolfood.png", 1, 1, (0x41764A,)),
    ("debris.png", 4, 1, (0x417682,)),
    ("crops_planted.png", 2, 1, (0x4176BA,)),
    ("tools2.png", 1, 1, (0x4176F2,)),
    ("tools3.png", 1, 1, (0x41772A,)),
    ("blockage.png", 1, 1, (0x417762,)),
    ("farm_after.png", 1, 1, (0x41779A,)),
    ("boulder.png", 1, 1, (0x4177D2,)),
    ("idol_uncarved.png", 1, 1, (0x41780A,)),
    ("graves.png", 4, 1, (0x417842,)),
    ("graveflowers.png", 3, 1, (0x41787A,)),
    ("drum.png", 1, 1, (0x4178B2,)),
    ("tchest.png", 1, 1, (0x4178EA,)),
    ("lagoon_restored.jpg", 1, 1, (0x417922,)),
    ("temple_rebuilt.jpg", 1, 1, (0x41795A,)),
    ("garden_restored.png", 1, 1, (0x417993,)),
    ("waves_proto.png", 10, 1, (0x41AD05,)),
    ("yellow_sparkle.png", 10, 1, (0x41AD40,)),
    ("dust2.png", 9, 1, (0x41AD78,)),
    ("blink.png", 10, 1, (0x41ADE8,)),
    ("sparklestrip2.png", 10, 1, (0x41AE21,)),
    ("sparklestrip.png", 10, 1, (0x41AE59,)),
    ("bubble.png", 10, 1, (0x41AE91,)),
    ("rainbow.png", 10, 1, (0x41AEC9,)),
    ("gamewin_bg.jpg", 1, 1, (0x41D6F3,)),
    ("intro1_bg.png", 1, 1, (0x41E6AB,)),
    ("intro2_bg.png", 1, 1, (0x41EDFE,)),
    ("bxshtBG.png", 1, 1, (0x41F6FD,)),
    ("logo1.png", 1, 1, (0x41F72F, 0x4266C5)),
    ("ldwLogo.png", 1, 1, (0x41F761,)),
    ("puzzle_covers.jpg", 4, 4, (0x42E143,)),
    ("puzzle_solved.jpg", 4, 4, (0x42E178,)),
    ("spirituality.jpg", 3, 1, (0x434A5A,)),
    ("medicine.jpg", 3, 1, (0x434A8C,)),
    ("science.jpg", 3, 1, (0x434ABE,)),
    ("farming.jpg", 3, 1, (0x434AF0,)),
    ("building.jpg", 3, 1, (0x434B22,)),
    ("breeding.jpg", 3, 1, (0x434B54,)),
    ("female_heads.png", 7, 20, (0x43C099,)),
    ("male_heads.png", 7, 20, (0x43C0D4,)),
    ("skelly.png", 4, 1, (0x43C2A6,)),
    ("ripple.png", 4, 1, (0x43C2DE,)),
)
# The two 0x40A070 calls whose name is not a pushed string: the button sheet (its caller's name, 3 x 1) and the
# whole-picture constructor's own (0x40A092, inside 0x40A070).
ONE_SHEET_INDIRECT = {BUTTON_SHEET_SITE: "the button's sheet: 0x4019B0's name, 3 x 1"}

# Every 0x409ED0 call with a pushed name: (name, sites).
WHOLE_PICTURES = (
    ("puzzles_bg.png", (0x41E039, 0x42E10E)),
    ("help1.jpg", (0x41E06A,)), ("help2.jpg", (0x41E09B,)), ("help3.jpg", (0x41E0CC,)), ("help4.jpg", (0x41E0FD,)),
    ("credits.jpg", (0x41E12E,)),
    ("main_BG.png", (0x4226C9,)), ("peep_shadow1.png", (0x4226FB, 0x43C202)), ("hand.png", (0x42272D,)),
    ("hand_open.png", (0x42275F,)),
    ("bxshtBG.png", (0x426577,)), ("Boxshtfeat.png", (0x4265AE,)), ("CloudBack.png", (0x4265E5,)),
    ("CloudMiddle.png", (0x42661C,)), ("Cloudfront.png", (0x426653,)), ("Lavaglow.png", (0x42668A,)),
    ("radioblank.png", (0x42977C,)), ("radioselected.png", (0x4297AD,)), ("WideSlider2.png", (0x4297DE,)),
    ("sliderhandle.png", (0x42980F,)), ("overview_bg.jpg", (0x429E18,)),
    ("BambooMeterFrame1.png", (0x42F389, 0x436EC9)), ("StatusBarSliceB.png", (0x42F3BE,)),
    ("StatusBarSliceR.png", (0x42F3F3,)), ("healthBarbulb.png", (0x42F428,)), ("SPLASH_BG.jpg", (0x431576,)),
    ("tech_bg.png", (0x434A28,)), ("arrowglow.png", (0x4360F3,)), ("arrowglowdown.png", (0x436150,)),
    ("arrowleftglow.png", (0x4361BA,)), ("arrowrightglow.png", (0x4361F6,)), ("LoadColor.png", (0x436EFE,)),
    ("focus_circle.png", (0x43C236,)), ("VD_BG.png", (0x449914,)), ("checkmark.png", (0x449942,)),
)
WHOLE_INDIRECT = {0x40A092: "0x40A070's own whole picture (its name argument)",
                  TILE_SITE: "the island tiles, \"%sX%01dY%01d.jpg\" with \"Map\", x and y 0-3 (0x4115C0)"}

# The 0x40A0F0 grids (the villager atlases of src/vv_pictures_vv1.py): (prefix, (across, down), cols, rows, site).
GRIDS = (
    ("female_bodies", (2, 2), 32, 20, 0x43C10F),
    ("female_actions", (1, 2), 9, 20, 0x43C14F),
    ("male_bodies", (2, 2), 32, 20, 0x43C18E),
    ("male_actions", (1, 2), 9, 20, 0x43C1CE),
)

# Every 0x4019B0 call (a button): (sheet, sites).  0x401640 builds the sheet with 0x40A070(name, 3, 1) at 0x401712.
BUTTONS = (
    ("main_wide_button2.png", (0x4136E1, 0x413919, 0x4155C5, 0x4155FD, 0x41A7A9, 0x41E207, 0x41E2BA, 0x41EE9A,
                               0x41EF40, 0x427247, 0x427453, 0x4287DB, 0x4299B6, 0x429EDE, 0x429F85, 0x42D429,
                               0x42E242, 0x42E2F5, 0x431C35, 0x431D3B, 0x434B9D, 0x435F88, 0x436D9C, 0x449A81)),
    ("ultra_wide_button.png", (0x41A593, 0x41A6C5, 0x427247, 0x42D213, 0x42D345)),
    ("leftarrow.png", (0x41E36D, 0x449BC1)),
    ("rightarrow.png", (0x41E3B3, 0x449B24)),
    ("MS_Button_01.png", (0x4227F3,)), ("MS_Button_02.png", (0x4228A7,)), ("MS_Button_03.png", (0x42295B,)),
    ("MS_Button_04.png", (0x422A0F,)), ("main_detail_button.png", (0x422AC3,)),
    ("empty1.png", (0x426774, 0x42682C, 0x4268E4, 0x42699C, 0x426A51, 0x426B0C)),
    ("research_button.png", (0x434C50, 0x434D06, 0x434DBC, 0x434E72, 0x434F28, 0x434FDE)),
    ("info_button.png", (0x435094, 0x43513D, 0x4351E6, 0x43528F, 0x435338, 0x4353E1)),
)

# The two fonts (0x402080 from 0x4126F0 and 0x412790): the picture is loaded whole by 0x40A530 at 0x402319, its
# glyph rectangles come from tables in the executable (0x4862A0, 0x486888).
FONTS = (("ldwBurweed27.png", 0x412719, 0x4126F0), ("ldwarialbold.png", 0x4127B9, 0x412790))

TILE_FORMAT, TILE_PREFIX, TILE_SIZE, TILES_ACROSS = "%sX%01dY%01d.jpg", "Map", 512, 4


def tile_name(x: int, y: int) -> str:
    return TILE_FORMAT.replace("%s", TILE_PREFIX).replace("%01d", str(x), 1).replace("%01d", str(y), 1)


def tile_files() -> list[str]:
    """The island's tiles in the order 0x4115C0 builds them (x inside y)."""
    return [tile_name(x, y) for y in range(TILES_ACROSS) for x in range(TILES_ACROSS)]


def _hx(sites) -> str:
    return ", ".join(f"0x{s:X}" for s in sites)


def sheet_table() -> list[SheetSpec]:
    """Every sprite the stock executable builds, once per (file, cut): its constructor calls in `where`."""
    merged: dict[tuple, dict] = {}

    def add(name, cols, rows, sheets=(1, 1), whole=False, where=""):
        key = (name.casefold(), cols, rows, tuple(sheets))
        entry = merged.setdefault(key, {"name": name, "cols": cols, "rows": rows, "sheets": tuple(sheets),
                                        "whole": whole, "where": []})
        entry["whole"] = entry["whole"] or whole
        entry["where"].append(where)
    for name, cols, rows, sites in ONE_SHEETS:
        add(name, cols, rows, where=f"0x40A070 at {_hx(sites)}")
    for name, sites in WHOLE_PICTURES:
        add(name, 1, 1, whole=True, where=f"0x409ED0 at {_hx(sites)}")
    for name in tile_files():
        add(name, 1, 1, whole=True, where="0x409ED0 at 0x4116E8 (the island tiles, 0x4115C0)")
    for prefix, sheets, cols, rows, site in GRIDS:
        add(prefix, cols, rows, sheets, where=f"0x40A0F0 at 0x{site:X}")
    for name, sites in BUTTONS:
        add(name, 3, 1, where=f"a button: 0x4019B0 at {_hx(sites)}, its sheet 0x40A070 at 0x401712")
    for name, site, _fn in FONTS:
        add(name, 1, 1, whole=True, where=f"a font: 0x402080 named at 0x{site:X}, loaded whole at 0x402319")
    out = []
    for e in merged.values():
        out.append(SheetSpec(e["name"], e["cols"], e["rows"], e["sheets"], whole=e["whole"], used=True,
                             where="; ".join(e["where"])))
    return out


def patcher_art() -> dict[str, Path]:
    """The patcher's own pictures for A New Home (each shipped by the release, scripts/build_release.py)."""
    art = {
        "mask_atlas.png": ROOT / "assets" / "origins" / "mask_atlas.png",
        "vvfp_grey_male_heads.png": ROOT / "assets" / "vv1_grey_hair" / "vvfp_grey_male_heads.png",
        "vvfp_grey_female_heads.png": ROOT / "assets" / "vv1_grey_hair" / "vvfp_grey_female_heads.png",
        "golden_mushroom.png": ROOT / "assets" / "golden_mushroom" / "golden_mushroom.png",
        "vvfp_sort_band.png": ROOT / "assets" / "sort_by" / "vvfp_sort_band.png",
        "vvfp_sort_radio.png": ROOT / "assets" / "sort_by" / "vvfp_sort_radio.png",
    }
    for stem, _label in ORIGINS_ICONS:          # inside the shipped Origins companion (its largest image)
        where = va.origins_icon(GAME, int(stem[:3]))
        if where is not None:
            art[stem + ".png"] = where
    return art


ORIGINS_ICONS = (("101-time-warp", "Time Warp"), ("102-island-event", "Island Event"),
                 ("103-barrel-of-babies", "Barrel of Babies"), ("104-tech-point-doubler", "Tech Point Doubler"),
                 ("105-food-point-doubler", "Food Point Doubler"), ("106-grant-youth", "Grant Youth"),
                 ("107-grant-full-mastery", "Grant Full Mastery"), ("108-grant-running", "Grant Running"),
                 ("109-upgrade-checkmark", "Upgrade checkmark"), ("110-cure-all", "Cure All"))

# ------------------------------------------------------------------ plan helpers (sizes only)


def _cdiv(a: int, b: int) -> int:
    return pi._cdivmod(a, b)[0]


def _cmod(a: int, b: int) -> int:
    return pi._cdivmod(a, b)[1]


def atlas(name: str, cols: int = 1, rows: int = 1) -> pi.Atlas:
    return pi.Atlas(name, cols, rows)


def frame_draw(sheets, at: pi.Atlas, index: int, x: int, y: int, alpha: float = 1.0, what: str = "") -> pi.Draw:
    """0x4087B0 / 0x408840: frame `index` is cell (index % cols, index / cols), drawn at (x, y)."""
    return va.cell_plan(sheets, at, _cmod(index, at.cols), _cdiv(index, at.cols), x, y, alpha=alpha, what=what)


def whole_draw(sheets, name: str, x: int, y: int, alpha: float = 1.0, what: str = "") -> pi.Draw:
    """0x408590 (plain) / 0x408630 (faded, scale 1): the whole picture at (x, y)."""
    return va.whole_plan(sheets, name, x, y, alpha=alpha, what=what)


def scaled_cell(sheets, at: pi.Atlas, col: int, row: int, x: int, y: int, percent: int, what: str = "") -> pi.Draw:
    """0x408AF0 / 0x408BA0 / 0x4088F0: the cell drawn at `percent`, its top-left moved by 0x407ED0's centring."""
    name, rect = at.cell(sheets.size, col, row)
    dx, dy = pi.centre_offset(rect[2] - rect[0], rect[3] - rect[1], percent)
    return pi.Draw(name, rect, x + dx, y + dy, pi.percent_scale(percent), 1.0, what)


def scaled_whole(sheets, name: str, x: int, y: int, percent: int, what: str = "") -> pi.Draw:
    w, h = sheets.size(name)
    dx, dy = pi.centre_offset(w, h, percent)
    return pi.Draw(name, (0, 0, w, h), x + dx, y + dy, pi.percent_scale(percent), 1.0, what)


def _has(sheets, *names) -> bool:
    return all(sheets.has(n) for n in names)


# ------------------------------------------------------------------ the island: tiles (0x4115C0 / 0x411550)


def island_tiles_plan(sheets, camx: int = 0, camy: int = 0) -> list[pi.Draw]:
    """0x411550: the 16 tiles in the order 0x4115C0 keeps them, each whole at its place minus the camera."""
    out = []
    for y in range(TILES_ACROSS):
        for x in range(TILES_ACROSS):
            out.append(whole_draw(sheets, tile_name(x, y), x * TILE_SIZE - camx, y * TILE_SIZE - camy,
                                  what=f"tile {x},{y}"))
    return out


# ------------------------------------------------------------------ the island's objects (0x416380 / 0x415E60)

# The game-state fields 0x416380 reads (offsets in the game object at scene+0x1480).
S_HUT1_DONE, S_HUT1 = 0x9FE8, 0x9FE4
S_HUT2_DONE, S_HUT2 = 0x9FF0, 0x9FEC
S_HUT3_DONE, S_HUT3 = 0x9FF8, 0x9FF4
S_FOOD, S_BERRIES = 0xA2EC, 0xA2F4
S_ITEM_COUNT, S_ITEM_X, S_ITEM_Y, S_ITEM_KIND = 0xACAC, 0xACA4, 0xACA8, 0xACB0
S_SCIENCE, S_FARMING, S_CROPS = 0xA2C4, 0xA2E4, 0xA2F8
S_DEBRIS_DONE, S_DEBRIS = 0x9FB8, 0x9FB4
S_BOULDER_DONE = 0x9FA8
S_CREEK_DONE, S_CREEK = 0x9FB0, 0x9FAC
S_IDOL_DONE, S_IDOL = 0x9FD8, 0x9FD4
S_TEMPLE_DONE, S_TEMPLE = 0x9FE0, 0x9FDC
S_GARDEN_DONE = 0x9FC0
S_LOG_A, S_LOG_B = 0xA054, 0xA058
S_DRUM_A, S_DRUM_B = 0xA04C, 0xA050
S_FLOWERS_A, S_FLOWERS_B = 0xA000, 0xA098
S_GRAVES, GRAVE_STRIDE, GRAVE_SLOTS = 0xA340, 0x2C, 50
S_CHEST_DONE, S_CHEST = 0x9FC8, 0x9FC4
BYTE_FIELDS = {S_HUT1_DONE, S_HUT2_DONE, S_HUT3_DONE, S_DEBRIS_DONE, S_BOULDER_DONE, S_CREEK_DONE, S_IDOL_DONE,
               S_TEMPLE_DONE, S_GARDEN_DONE, S_LOG_B, S_DRUM_B, S_FLOWERS_A, S_FLOWERS_B, S_CHEST_DONE}

# The scene object's sprite slots (0x417280): offset -> (file, cols, rows).
SCENE_SPRITES = {
    0x1400: ("smallHut.png", 1, 1), 0x1404: ("scaffolding.png", 1, 1), 0x1408: ("food1.png", 1, 1),
    0x140C: ("food2.png", 1, 1), 0x1410: ("food3.png", 1, 1), 0x1414: ("stoolfood.png", 1, 1),
    0x1418: ("berry1.png", 1, 1), 0x141C: ("berry2.png", 1, 1), 0x1420: ("berry3.png", 1, 1),
    0x1424: ("berry4.png", 1, 1), 0x1428: ("berry5.png", 1, 1), 0x142C: ("berry6.png", 1, 1),
    0x1430: ("berry7.png", 1, 1), 0x1434: ("berry8.png", 1, 1), 0x1438: ("berry9.png", 1, 1),
    0x143C: ("carrying.png", 15, 1), 0x1440: ("drum.png", 1, 1), 0x1444: ("debris.png", 4, 1),
    0x1448: ("crops_planted.png", 2, 1), 0x144C: ("tools2.png", 1, 1), 0x1450: ("tools3.png", 1, 1),
    0x1454: ("blockage.png", 1, 1), 0x1458: ("farm_after.png", 1, 1), 0x145C: ("boulder.png", 1, 1),
    0x1460: ("idol_uncarved.png", 1, 1), 0x1464: ("graves.png", 4, 1), 0x1468: ("graveflowers.png", 3, 1),
    0x146C: ("tchest.png", 1, 1), 0x1470: ("lagoon_restored.jpg", 1, 1), 0x1474: ("temple_rebuilt.jpg", 1, 1),
    0x1478: ("garden_restored.png", 1, 1),
}
SPRITE_OF = {v[0]: (k, v[1], v[2]) for k, v in SCENE_SPRITES.items()}

# (x, y, frame) of the beach debris pieces and the progress (0x9FB4) under which each still lies.
DEBRIS = ((150, 0x169, 0x5BD, 1), (0x78, 0x11D, 0x5A7, 2), (0x2D, 0x1AD, 0x5BD, 3), (0x5A, 0xE1, 0x571, 0),
          (0x1E, 0x117, 0x571, 1), (0x5A, 0x154, 0x593, 2), (0x0F, 0x22A, 0x5FB, 3), (0x4B, 0x182, 0x5DC, 0),
          (0x05, 0x157, 0x5B7, 2), (0x69, 0x220, 0x5F0, 1), (0x3C, 0x1F6, 0x5D7, 3))
CROPS_A = ((0x171, 0x4BE, 0), (0x18A, 0x4C0, 0), (0x19F, 0x4BF, 0), (0x1B3, 0x4BF, 0), (0x1CE, 0x4C0, 0),
           (0x1F4, 0x4BE, 0), (0x172, 0x4E7, 1), (0x188, 0x4E4, 1), (0x19E, 0x4E5, 1), (0x1B3, 0x4E4, 1),
           (0x1CF, 0x4E6, 1), (0x1F5, 0x4E8, 1))
CROPS_B = ((0x215, 0x4BE, 0), (0x230, 0x4C0, 0), (0x247, 0x4BF, 0), (0x25C, 0x4BF, 0), (0x272, 0x4C0, 0),
           (0x296, 0x4BE, 0), (0x214, 0x4E7, 1), (0x231, 0x4E4, 1), (0x249, 0x4E5, 1), (0x25D, 0x4E4, 1),
           (0x272, 0x4E6, 1), (0x295, 0x4E8, 1))
BERRIES = ((0, "berry9.png", 0x294, 0x196), (150, "berry8.png", 0x2C0, 0x18F), (300, "berry7.png", 0x33C, 0x164),
           (450, "berry6.png", 0x28D, 0x13A), (600, "berry5.png", 0x2C9, 0x12B), (750, "berry4.png", 0x311, 0x167),
           (900, "berry3.png", 0x301, 0x131), (1050, "berry2.png", 0x28E, 0x16F), (1300, "berry1.png", 0x2E4, 0x16B))
TEMPLE = ((0x177, 0x54B, 0x4EC), (0x1F4, 0x519, 0x53C), (0x271, 0x52D, 0x50A), (1, 0x57D, 0x4C4),
          (0xFA, 0x591, 0x546), (0x36B, 0x555, 0x550), (0x7D, 0x577, 0x519), (0x2EE, 0x56D, 0x501))
# The graveyard: slot -> the grave flowers 0x416380 puts down when that slot holds a grave (x, y, frame).
GRAVE_FLOWERS = {2: (0x4D1, 0xC8, 0), 7: (0x563, 0xD2, 1), 14: (0x513, 0xF0, 1), 18: (0x591, 0xE6, 0),
                 24: (0x53C, 0x10E, 0), 22: (0x4EC, 0x118, 0), 32: (0x535, 0x14A, 0), 37: (0x5C7, 0x14A, 1),
                 43: ((0x4D1, 0x17C, 0), (0x522, 0x188, 1)), 46: ((0x563, 0x188, 1), (0x5B8, 0x17C, 0)),
                 10: (0x4A3, 0xE4, 0), 29: (0x5F2, 0x107, 0)}
GRAVE_FLOWER_ORDER = (2, 7, 14, 18, 24, 22, 32, 37, 43, 46, 10, 29)


def island_objects(state: dict) -> list[tuple[str, int, int, int]]:
    """The scene list 0x416380 builds from the game state, in its order: (file, x, y, frame) with frame -1 for a
    whole picture (0x415DD0) and the cell index otherwise (0x415E10).  `state` maps a field offset to its value."""
    g = lambda off: state.get(off, 0)  # noqa: E731
    out: list[tuple[str, int, int, int]] = []

    def whole(name, x, y):
        out.append((name, x, y, -1))

    def frame(name, x, y, f):
        out.append((name, x, y, f))
    if not g(S_HUT1_DONE):
        whole("scaffolding.png", 0x35A, 0x400)
        if g(S_HUT1) > 0x7D:
            whole("scaffolding.png", 0x373, 0x3E2)
    else:
        whole("smallHut.png", 0x332, 0x3B0)
    if not g(S_HUT2_DONE):
        if g(S_HUT2) >= 1:
            whole("scaffolding.png", 0xFA, 0x395)
        if g(S_HUT2) > 0xC8:
            whole("scaffolding.png", 0x12B, 0x377)
    else:
        whole("smallHut.png", 0xE1, 0x340)
    if not g(S_HUT3_DONE):
        if g(S_HUT3) >= 1:
            whole("scaffolding.png", 0x104, 0x472)
        if g(S_HUT3) > 0x12C:
            whole("scaffolding.png", 0xEB, 0x454)
    else:
        whole("smallHut.png", 0xDC, 0x418)
    food = g(S_FOOD)
    if food > 2000:
        whole("food3.png", 0x442, 0x434)
    elif food > 400:
        whole("food2.png", 0x444, 0x441)
    elif food > 50:
        whole("food1.png", 0x453, 0x455)
    if food > 10:
        whole("stoolfood.png", 0x462, 0x47A)
    for above, name, x, y in BERRIES:
        if g(S_BERRIES) > above:
            whole(name, x, y)
    if g(S_ITEM_COUNT) > 1:
        frame("carrying.png", g(S_ITEM_X), g(S_ITEM_Y), g(S_ITEM_KIND) + 0xD)
    if g(S_SCIENCE) >= 2:
        whole("tools2.png", 0x1F4, 0x3E8)
    if g(S_SCIENCE) >= 3:
        whole("tools3.png", 0x228, 0x3E8)
    if g(S_FARMING) >= 2:
        whole("farm_after.png", 0x137, 0x47F)
        if g(S_CROPS) > 400:
            for x, y, f in CROPS_A:
                frame("crops_planted.png", x, y, f)
        if g(S_CROPS) != 0:
            for x, y, f in CROPS_B:
                frame("crops_planted.png", x, y, f)
    if g(S_DEBRIS_DONE) != 1:
        for below, x, y, f in DEBRIS:
            if g(S_DEBRIS) < below:
                frame("debris.png", x, y, f)
    if not g(S_BOULDER_DONE):
        whole("boulder.png", 0x3DD, 0x53)
    if not g(S_CREEK_DONE):
        whole("blockage.png", 0xC4, 0x70)
        if g(S_CREEK) > 0xAF:
            whole("scaffolding.png", 0xC8, 0x91)
        else:
            whole("blockage.png", 0xDC, 0x8C)
    else:
        whole("lagoon_restored.jpg", 0x72, 1)
    if not g(S_IDOL_DONE):
        whole("idol_uncarved.png", 0x179, 0x21F)
        if g(S_IDOL) > 0:
            whole("scaffolding.png", 0x183, 0x25B)
        if g(S_IDOL) > 0x2A3:
            whole("scaffolding.png", 0x183, 0x283)
    if not g(S_TEMPLE_DONE):
        for at_least, x, y in TEMPLE:
            if g(S_TEMPLE) >= at_least:
                whole("scaffolding.png", x, y)
    else:
        whole("temple_rebuilt.jpg", 0x4FD, 0x4BF)
    if g(S_GARDEN_DONE):
        whole("garden_restored.png", 0x52E, 0x2CA)
    if g(S_LOG_A) == 0 and not g(S_LOG_B):
        frame("debris.png", 0x407, 0x1F1, 2)
    if g(S_DRUM_A) != 0 or g(S_DRUM_B):
        frame("drum.png", 0x2DE, 0x382, 0)
    if g(S_FLOWERS_A):
        for x, y, f in ((0x4E2, 0xB4, 1), (0x52D, 0xAA, 0), (0x578, 0xB4, 1), (0x5C3, 0xAA, 0)):
            frame("graveflowers.png", x, y, f)
    if g(S_FLOWERS_B):
        frame("graveflowers.png", 0x23E, 0x9F, 2)
    slot = 0
    for row, y in enumerate(range(0xC8, 0x15E, 0x1E)):
        for col, x in enumerate(range(0x4D1, 0x5FD, 0x1E)):
            value = g(S_GRAVES + slot * GRAVE_STRIDE)
            if value > 0:
                flowers = GRAVE_FLOWERS.get(slot)
                if flowers is not None:
                    for fx, fy, ff in (flowers if isinstance(flowers[0], tuple) else (flowers,)):
                        frame("graveflowers.png", fx, fy, ff)
                frame("graves.png", x, y, _cmod(value + col + row, 4))
            slot += 1
    if g(S_CHEST_DONE):
        whole("tchest.png", 0x443, 0x53E)
    else:
        if g(S_CHEST) != 0:
            whole("scaffolding.png", 0x438, 0x546)
        if g(S_CHEST) > 0x190:
            whole("scaffolding.png", 0x474, 0x56E)
    return out


def objects_plan(sheets, objects, camx: int = 0, camy: int = 0) -> list[pi.Draw]:
    """0x415E60: each listed object at its place minus the camera, whole (0x4093A0) or its frame (0x4093D0)."""
    out = []
    for name, x, y, f in objects:
        _off, cols, rows = SPRITE_OF[name]
        if f == -1:
            out.append(whole_draw(sheets, name, x - camx, y - camy, what=name))
        else:
            out.append(frame_draw(sheets, atlas(name, cols, rows), f, x - camx, y - camy, what=name))
    return out


# The map (0x415ED0): each object at a quarter of its place plus an offset per sprite, drawn at 25%.
MAP_PERCENT = 25
MAP_OFFSETS = {"farm_after.png": (0x80, 0x22), "lagoon_restored.jpg": (0x96, -3), "crops_planted.png": (0xAA, 0x37),
               "blockage.png": (0xAF, 0x38), "garden_restored.png": (0x96, 0x12), "temple_rebuilt.jpg": (0x96, 0x1B)}
MAP_SKIPPED = {"tools2.png", "tools3.png", "food1.png", "food2.png", "food3.png", "stoolfood.png"}
MAP_BERRY = (0xB4, 0x34)
MAP_OTHER = (0xAF, 0x29)


def map_objects_plan(sheets, objects) -> list[pi.Draw]:
    """0x415ED0, the island's objects on the map: x' = (x - cell width) / 4 + dx, y' = (y - cell height) / 4 + dy
    (C division), drawn at 25%; tools, food and carried items 13 and 14 are left off; the berry layers, the farm,
    the crops, the blockage, the lagoon, the garden and the temple have offsets of their own and are drawn whole
    (the crops too: their whole two-cell sheet); anything else is drawn whole or as its frame."""
    out = []
    for name, x, y, f in objects:
        _off, cols, rows = SPRITE_OF[name]
        if name in MAP_SKIPPED or (name == "carrying.png" and f in (13, 14)):
            continue
        w, h = sheets.size(name)
        cw, ch = w // cols, h // rows
        if name.startswith("berry"):
            dx, dy = MAP_BERRY
        else:
            dx, dy = MAP_OFFSETS.get(name, MAP_OTHER)
        mx, my = _cdiv(x - cw, 4) + dx, _cdiv(y - ch, 4) + dy
        if name in MAP_OFFSETS or name.startswith("berry") or f == -1:
            out.append(scaled_whole(sheets, name, mx, my, MAP_PERCENT, what=name))
        else:
            at = atlas(name, cols, rows)
            out.append(scaled_cell(sheets, at, _cmod(f, cols), _cdiv(f, cols), mx, my, MAP_PERCENT, what=name))
    return out


# ------------------------------------------------------------------ creatures: butterflies (0x412AB0)

BUTTERFLY = atlas("butterflygreen.png", 4, 5)
BUTTERFLY_COLOURS = 5


def butterfly_index(colour: int, wing: int, heading: int, state: int = 0, number: int = 0) -> int:
    """0x412AB0's frame: wing + colour x 4, plus 2 when heading right (heading >= 0) -- and, for a butterfly in
    state 2, plus 2 for the even-numbered ones of the nine whatever the heading."""
    right = (number % 2 == 0) if state == 2 else heading >= 0
    return wing + colour * 4 + (2 if right else 0)


def butterfly_plan(sheets, x: int, y: int, colour: int, wing: int, heading: int, percent: int = 100,
                   state: int = 0, number: int = 0, camx: int = 0, camy: int = 0) -> pi.Draw:
    """One butterfly: frame-scaled (0x409420) at its percentage, centred by 0x407ED0."""
    i = butterfly_index(colour, wing, heading, state, number)
    return scaled_cell(sheets, BUTTERFLY, i % 4, i // 4, x - camx, y - camy, percent, what="butterfly")


# ------------------------------------------------------------------ effects: particles (0x41AB20)

PARTICLE_SPRITES = {0x3438: "waves_proto.png", 0x343C: "yellow_sparkle.png", 0x3440: "dust2.png",
                    0x3444: "carrying.png", 0x3448: "blink.png", 0x344C: "sparklestrip2.png",
                    0x3450: "sparklestrip.png", 0x3454: "rainbow.png", 0x3458: "bubble.png"}
PARTICLE_FADE = pi.f32(0.1)            # 0x4595DC
EFFECTS = (("waves_proto.png", 10, "Waves"), ("yellow_sparkle.png", 10, "Yellow sparkle"),
           ("dust2.png", 9, "Dust"), ("blink.png", 10, "Blink"), ("sparklestrip2.png", 10, "Small sparkle"),
           ("sparklestrip.png", 10, "Sparkle"), ("bubble.png", 10, "Bubble"), ("rainbow.png", 10, "Rainbow"))


def particle_alpha(age: int) -> float:
    """A fading particle's alpha: 1.0 - age x 0.1f in the x87's double precision, stored as a 32-bit float
    (fild, fmul, fsubr, fstp)."""
    return pi.f32(1.0 - age * PARTICLE_FADE)


def particle_plan(sheets, name: str, cols: int, frame: int, x: int, y: int, lift: int = 0, fixed: int = -1,
                  layer: int = 1, camx: int = 0, camy: int = 0) -> pi.Draw:
    """One particle of 0x41AB20: layer 2 is drawn at its own place, layers 0 and 1 minus the camera; a particle
    with a fixed frame (`fixed` != -1) is drawn as that frame, faded by its age (`frame`)."""
    at = atlas(name, cols, 1)
    if layer == 2:
        return frame_draw(sheets, at, frame, x, y + lift, what=name)
    if fixed != -1:
        return frame_draw(sheets, at, fixed, x - camx, y - camy + lift, alpha=particle_alpha(frame), what=name)
    return frame_draw(sheets, at, frame, x - camx, y - camy + lift, what=name)


# ------------------------------------------------------------------ the Tech screen (0x433B20)

# (name the game gives the technology, picture, game-state level field, x, y); the drawing order of 0x433B20.
TECHS = (("Farming", "farming.jpg", 0xA2E4, 0x62, 0x36), ("Medicine", "medicine.jpg", 0xA2D4, 0x62, 0xBF),
         ("Fertility", "breeding.jpg", 0xA2DC, 0x62, 0x148), ("Construction", "building.jpg", 0xA2CC, 0x1A0, 0x36),
         ("Science", "science.jpg", 0xA2C4, 0x1A0, 0xBF), ("Spirituality", "spirituality.jpg", 0xA2BC, 0x1A0, 0x148))
TECH_SEGMENT = 0x60
TECH_SPRITES = {"spirituality.jpg": 0x44, "farming.jpg": 0x48, "science.jpg": 0x4C, "medicine.jpg": 0x50,
                "building.jpg": 0x54, "breeding.jpg": 0x58}


def tech_screen_plan(sheets, levels: dict, stage: int = 4, alpha: float = 1.0, background: bool = True,
                     only=None) -> list[pi.Draw]:
    """0x433B20: tech_bg.png at (0, 0), then each technology's first cell, then its second cell for level 2 and up,
    then its third for level 3, every one at alpha `alpha` while the screen fades in (stage <= 3), else 1.0.
    `levels` maps the picture to its level; `only` keeps one technology's cells."""
    a = alpha if stage <= 3 else 1.0
    out = [whole_draw(sheets, "tech_bg.png", 0, 0, what="Tech screen")] if background else []
    for segment, need in ((0, -10 ** 9), (1, 2), (2, 3)):
        for label, name, _field, x, y in TECHS:
            if only is not None and name != only:
                continue
            if segment == 0 or levels.get(name, 0) >= need:
                out.append(frame_draw(sheets, atlas(name, 3, 1), segment, x + segment * TECH_SEGMENT, y, alpha=a,
                                      what=f"{label} {segment + 1}"))
    return out


# ------------------------------------------------------------------ meters

SKILL_ROWS = {3: 0xDF, 4: 0x109, 5: 0x134, 6: 0x15F, 7: 0x188}
SKILL_X, SLICE = 0x1CE, 0x10
HEALTH_ROW, BULB_PLACE, HEALTH_Y = 8, (0x1A1, 0x58), 0x5E


def skill_bar_plan(sheets, row: int, value: int) -> list[pi.Draw]:
    """0x42F500(row, value): value clamped to 0-100, (value x 256 / 100) / 16 slices 16 pixels apart from x 0x1CE.
    Rows 3-7 are the Details screen's skill bars (blue slices); row 8 the health bar: the bulb at (0x1A1, 0x58) when
    any slice or any health shows, then red slices at y 0x5E."""
    v = min(100, max(0, value))
    scaled = _cdiv(v << 8, 100)
    n = _cdiv(scaled, 16)
    out = []
    if row in SKILL_ROWS:
        for i in range(n):
            out.append(whole_draw(sheets, "StatusBarSliceB.png", SKILL_X + SLICE * i, SKILL_ROWS[row], what="slice"))
    elif row == HEALTH_ROW:
        if n >= 1 or scaled != 0:
            out.append(whole_draw(sheets, "healthBarbulb.png", *BULB_PLACE, what="bulb"))
        for i in range(n):
            out.append(whole_draw(sheets, "StatusBarSliceR.png", SKILL_X + SLICE * i, HEALTH_Y, what="slice"))
    return out


LOAD_PLACE = (0xF0, 0x1F4)


def loading_bar_plan(sheets, percent: int, x: int = LOAD_PLACE[0], y: int = LOAD_PLACE[1]) -> list[pi.Draw]:
    """0x436FB0 in its LoadColor mode (3): percent clamped to 1-100, (percent x 320 / 100) / 8 segments; each
    segment LoadColor.png at x + 8i, and after each the bamboo frame at (x, y) again (so no segment, no frame)."""
    p = min(100, percent) if percent > 0 else 1
    n = _cdiv(_cdiv(p * 320, 100), 8)
    out = []
    for i in range(n):
        out.append(whole_draw(sheets, "LoadColor.png", x + 8 * i, y, what="segment"))
        out.append(whole_draw(sheets, "BambooMeterFrame1.png", x, y, what="frame"))
    return out


# ------------------------------------------------------------------ dialogs (tile grid, 0x40C670 / 0x40C4D0)

# The nine cells' places in the frame (0x40C4D0's frames): top-left 8, top 1, top-right 0, left 3, middle 7,
# right 2, bottom-left 5, bottom 4, bottom-right 6.
DIALOG_SIZES = ((455, 400, "0x4135E0"), (360, 200, "0x415554"), (640, 448, "0x429700"), (490, 350, "0x431B30"),
                (320, 320, "0x436CB1"))


def dialog_plan(sheets, name: str, w: int, h: int, x: int = 0, y: int = 0, alpha: float = 1.0) -> list[pi.Draw]:
    """0x40C670(sprite, w, h) takes a tile's size from the first cell and 0x40C450 makes the grid
    (tile + w - 1) / tile tiles across and down (at least 2); 0x40C4D0(x, y, alpha) draws it row by row."""
    at = atlas(name, 9, 1)
    _n, rect = at.cell(sheets.size, 0, 0)
    tw, th = rect[2] - rect[0], rect[3] - rect[1]
    cols, rows = _cdiv(tw + w - 1, tw), _cdiv(th + h - 1, th)
    cols, rows = (cols if cols > 1 else 2), (rows if rows > 1 else 2)
    out = []

    def put(f, px, py):
        out.append(frame_draw(sheets, at, f, px, py, alpha=alpha, what=f"tile {f}"))
    put(8, x, y)
    for i in range(cols - 2):
        put(1, x + tw * (i + 1), y)
    put(0, x + (cols - 1) * tw, y)
    cy = y + th
    for _r in range(rows - 2):
        put(3, x, cy)
        for i in range(cols - 2):
            put(7, x + tw * (i + 1), cy)
        put(2, x + (cols - 1) * tw, cy)
        cy += th
    put(5, x, cy)
    for i in range(cols - 2):
        put(4, x + tw * (i + 1), cy)
    put(6, x + (cols - 1) * tw, cy)
    return out


def button_plan(sheets, name: str, state: int, x: int = 0, y: int = 0) -> list[pi.Draw]:
    """0x401340(state) on an enabled, visible button with no parent offset: frame `state` of its 3 x 1 sheet at
    the button's top-left."""
    return [frame_draw(sheets, atlas(name, 3, 1), state, x, y, what=f"button {state}")]


# ------------------------------------------------------------------ screens

def help_plan(sheets, page: int) -> list[pi.Draw]:
    """0x41DD00: puzzles_bg.png at (0, 0), then the help page (help1-4, then the credits) at (0x50, 0x2E)."""
    pages = ("help1.jpg", "help2.jpg", "help3.jpg", "help4.jpg", "credits.jpg")
    out = [whole_draw(sheets, "puzzles_bg.png", 0, 0)]
    if 0 <= page <= 4:
        out.append(whole_draw(sheets, pages[page], 0x50, 0x2E))
    return out


# The 16 puzzles (0x42D5C0): the game-state flag of each picture, in screen order.
PUZZLE_FLAGS = (0xA058, 0x9FE8, 0x9FB8, 0xA050, 0x9FB0, 0xA090, 0xA000, 0xA080, 0x9FC0, 0xA098, 0x9FE0, 0x9FD8,
                0xA008, 0xA088, 0x9FC8, 0x9FA8)


def puzzle_place(i: int) -> tuple[int, int]:
    return 0x50 + 0xA0 * (i % 4), 0x32 + 0x76 * (i // 4)


def puzzle_screen_plan(sheets, solved) -> list[pi.Draw]:
    """0x42D5C0: each solved puzzle's picture (puzzle_solved.jpg frame i) at its place, then puzzles_bg.png over
    them at (0, 0), then each unsolved one's cover (puzzle_covers.jpg frame i).  `solved` is a set of indexes."""
    solved_at, cover_at = atlas("puzzle_solved.jpg", 4, 4), atlas("puzzle_covers.jpg", 4, 4)
    out = [frame_draw(sheets, solved_at, i, *puzzle_place(i), what=f"puzzle {i + 1}") for i in range(16)
           if i in solved]
    out.append(whole_draw(sheets, "puzzles_bg.png", 0, 0))
    out += [frame_draw(sheets, cover_at, i, *puzzle_place(i), what=f"cover {i + 1}") for i in range(16)
            if i not in solved]
    return out


CLOUDS = (("Cloudfront.png", 1.0), ("CloudMiddle.png", pi.f32(0.7)), ("CloudBack.png", pi.f32(0.4)))
# One moment of the drift: the clouds move right from -250 and wrap at 800 at random heights (0x425C50); these
# places are inside those ranges (front y 10-59, middle 100-159, back 150-209).
TITLE_CLOUDS = ((120.0, 25, 60.0, 120, 300.0, 170), (520.0, 40, 460.0, 140, -100.0, 190))
TITLE_LAVA = pi.f32(0.6)


def title_plan(sheets, clouds=TITLE_CLOUDS, lava: float = TITLE_LAVA) -> list[pi.Draw]:
    """0x425DF0: bxshtBG.png, the three cloud layers (front opaque, middle at 0.7, back at 0.4) twice each,
    Boxshtfeat.png, Lavaglow.png at (2, 0x97) at its pulsing alpha, logo1.png at (10, 10) (then the butterflies)."""
    out = [whole_draw(sheets, "bxshtBG.png", 0, 0)]
    for fx, fy, mx, my, bx, by in clouds:
        for (name, alpha), (cx, cy) in zip(CLOUDS, ((fx, fy), (mx, my), (bx, by))):
            out.append(whole_draw(sheets, name, int(cx), cy, alpha=alpha, what="cloud"))
    out.append(whole_draw(sheets, "Boxshtfeat.png", 0, 0))
    out.append(whole_draw(sheets, "Lavaglow.png", 2, 0x97, alpha=lava, what="lava glow"))
    out.append(whole_draw(sheets, "logo1.png", 10, 10))
    return out


def loading_screen_plan(sheets, percent: int) -> list[pi.Draw]:
    """0x41F570: bxshtBG.png, (a white rectangle at alpha 0.5 over the whole screen, a fill: not drawn here), the
    loading bar at (0xF0, 0x1F4), logo1.png at (0xFF, 0x32), ldwLogo.png at (0x2F, 0x190)."""
    return ([whole_draw(sheets, "bxshtBG.png", 0, 0)] + loading_bar_plan(sheets, percent)
            + [whole_draw(sheets, "logo1.png", 0xFF, 0x32), whole_draw(sheets, "ldwLogo.png", 0x2F, 0x190)])


# The Details screen's job checkmark (0x449146): one place for each job.
CHECK_PLACES = ((0x2F4, 0xD5), (0x2F4, 0xFF), (0x2F4, 0x12A), (0x2F4, 0x155), (0x2F4, 0x17E))

# The cursor (0x408240 / 0x409060): the hand is drawn whole with its middle on the mouse.


def cursor_plan(sheets, name: str, mx: int = 0, my: int = 0) -> list[pi.Draw]:
    w, h = sheets.size(name)
    return [whole_draw(sheets, name, mx - _cdiv(w, 2), my - _cdiv(h, 2), what="cursor")]


# The main screen's buttons (0x4224A0's 0x4019B0 calls): sheet and place.
MAIN_BUTTONS = (("MS_Button_01.png", 80, 403), ("MS_Button_02.png", 21, 450), ("MS_Button_03.png", 56, 490),
                ("MS_Button_04.png", 57, 554), ("main_detail_button.png", 681, 485))
TECH_BUTTONS = (("research_button.png", 325, 142), ("research_button.png", 325, 416),
                ("research_button.png", 643, 279), ("research_button.png", 325, 279),
                ("research_button.png", 643, 142), ("research_button.png", 643, 416),
                ("info_button.png", 282, 142), ("info_button.png", 282, 416), ("info_button.png", 600, 279),
                ("info_button.png", 282, 279), ("info_button.png", 600, 142), ("info_button.png", 600, 416))


# ------------------------------------------------------------------ the assets

def _frames(*pairs) -> tuple:
    return tuple(Frame(label, tuple(plan)) for label, plan in pairs)


EVERYTHING_BUILT = {
    S_HUT1_DONE: 1, S_HUT2_DONE: 1, S_HUT3_DONE: 1, S_FOOD: 3000, S_BERRIES: 1500, S_SCIENCE: 3, S_FARMING: 3,
    S_CROPS: 500, S_DEBRIS_DONE: 1, S_BOULDER_DONE: 1, S_CREEK_DONE: 1, S_IDOL_DONE: 1, S_TEMPLE_DONE: 1,
    S_GARDEN_DONE: 1, S_LOG_B: 1, S_DRUM_B: 1, S_FLOWERS_A: 1, S_FLOWERS_B: 1, S_CHEST_DONE: 1,
    **{S_GRAVES + i * GRAVE_STRIDE: 1 for i in range(GRAVE_SLOTS)}}
NEW_GAME = {S_FOOD: 100, S_BERRIES: 1500}


def _objs_asset(sheets, key, category, label, states, group="", note="", proof="emulated 0x416380 + 0x415E60"):
    frames = []
    for frame_label, state, keep in states:
        objs = [o for o in island_objects(state) if keep(o)]
        if not objs or not all(sheets.has(o[0]) for o in objs):
            continue
        frames.append(Frame(frame_label, tuple(objects_plan(sheets, objs))))
    if not frames:
        return None
    return Asset(key, category, label, tuple(frames), group=group, note=note, proof=proof)


def _near(x0, y0, x1, y1, names=None):
    def keep(o):
        return x0 <= o[1] < x1 and y0 <= o[2] < y1 and (names is None or o[0] in names)
    return keep


def _island_assets(sheets) -> list[Asset]:
    out: list[Asset | None] = []
    scaf = {"scaffolding.png", "smallHut.png"}
    for n, (done, prog, box, levels) in enumerate(((S_HUT1_DONE, S_HUT1, (0x300, 0x380, 0x400, 0x460), (0, 0x7E)),
                                                   (S_HUT2_DONE, S_HUT2, (0xD0, 0x320, 0x150, 0x3A0), (1, 0xC9)),
                                                   (S_HUT3_DONE, S_HUT3, (0xD0, 0x410, 0x150, 0x480), (1, 0x12D))), 1):
        keep = _near(*box, names=scaf)
        out.append(_objs_asset(sheets, f"hut{n}", va.BUILDINGS, f"Hut {n}", (
            ("building, started", {prog: levels[0]}, keep), ("building, more than half", {prog: levels[1]}, keep),
            ("finished", {done: 1}, keep)), group="Huts",
            note="each stage as the island draws it (0x416380); the hut is built where it stands on the island"))
    food = {"food1.png", "food2.png", "food3.png", "stoolfood.png"}
    keep = lambda o: o[0] in food  # noqa: E731
    out.append(_objs_asset(sheets, "food", va.BUILDINGS, "Food pile", tuple(
        (f"food above {a}", {S_FOOD: a + 1}, keep) for a in (10, 50, 400, 2000)), group="Food",
        note="the stool and the pile drawn for the village's food (0x416380: above 10, 50, 400 and 2,000)"))
    keep = lambda o: o[0].startswith("berry")  # noqa: E731
    out.append(_objs_asset(sheets, "berries", va.PLANTS, "Berry bush berries", tuple(
        (f"berries above {a}", {S_BERRIES: a + 1}, keep) for a, _n, _x, _y in BERRIES), group="Berry bush",
        note="the berry clusters 0x416380 lays on the bush (painted on the island tiles) as its berries grow: one "
             "more cluster above each of 0, 150, 300, 450, 600, 750, 900, 1,050 and 1,300"))
    keep = lambda o: o[0] in ("farm_after.png", "crops_planted.png")  # noqa: E731
    out.append(_objs_asset(sheets, "farm", va.PLANTS, "Farm", (
        ("farming level 2, nothing planted", {S_FARMING: 2}, keep),
        ("crops planted (1 to 400)", {S_FARMING: 2, S_CROPS: 1}, keep),
        ("crops planted (above 400)", {S_FARMING: 2, S_CROPS: 401}, keep)), group="Farm"))
    keep = lambda o: o[0] in ("tools2.png", "tools3.png")  # noqa: E731
    out.append(_objs_asset(sheets, "tools", va.BUILDINGS, "Tools", (
        ("science level 2", {S_SCIENCE: 2}, keep), ("science level 3", {S_SCIENCE: 3}, keep)), group="Tools",
        note="drawn by the science level (game-state field 0xA2C4)"))
    keep = lambda o: o[0] == "debris.png" and o[2] >= 0x500  # noqa: E731
    stages = sorted({below for below, *_r in DEBRIS})
    out.append(_objs_asset(sheets, "debris", va.PUZZLES, "Beach debris", tuple(
        (f"cleared {s}", {S_DEBRIS: s}, keep) for s in [0] + stages[:-1]), group="Beach debris",
        note="the smashed-boat debris on the beach, one piece fewer as the clearing (0x9FB4) passes each step"))
    keep = lambda o: o[0] == "debris.png" and o[1] == 0x407  # noqa: E731
    out.append(_objs_asset(sheets, "log", va.PUZZLES, "Fallen debris", (("lying", {}, keep),), group="Beach debris",
                           note="debris cell 3 at (0x407, 0x1F1) until the game-state fields 0xA054 and 0xA058 are set"))
    keep = lambda o: o[0] == "boulder.png"  # noqa: E731
    out.append(_objs_asset(sheets, "boulder", va.PUZZLES, "Boulder", (("blocking the cave", {}, keep),),
                           group="Boulder"))
    keep = lambda o: o[0] in ("blockage.png", "scaffolding.png", "lagoon_restored.jpg") and o[2] < 0xB0  # noqa: E731
    out.append(_objs_asset(sheets, "creek", va.PUZZLES, "Creek blockage", (
        ("blocked", {}, keep), ("being cleared (above 175)", {S_CREEK: 0xB0}, keep),
        ("cleared: the lagoon", {S_CREEK_DONE: 1}, keep)), group="Creek"))
    keep = lambda o: o[0] in ("idol_uncarved.png", "scaffolding.png") and 0x170 <= o[1] < 0x190  # noqa: E731
    out.append(_objs_asset(sheets, "idol", va.PUZZLES, "Idol", (
        ("uncarved", {}, keep), ("being carved", {S_IDOL: 1}, keep), ("being carved (above 675)", {S_IDOL: 0x2A4},
                                                                      keep)), group="Idol",
        note="once carved (0x9FD8) the island draws nothing here"))
    keep = lambda o: o[0] in ("scaffolding.png", "temple_rebuilt.jpg") and o[1] >= 0x4C0 and o[2] >= 0x4B0  # noqa: E731
    out.append(_objs_asset(sheets, "temple", va.PUZZLES, "Temple", tuple(
        (f"rebuilding, {a}", {S_TEMPLE: a}, keep) for a in sorted(t[0] for t in TEMPLE)) + (
        ("rebuilt", {S_TEMPLE_DONE: 1}, keep),), group="Temple"))
    keep = lambda o: o[0] == "garden_restored.png"  # noqa: E731
    out.append(_objs_asset(sheets, "garden", va.PUZZLES, "Garden", (("restored", {S_GARDEN_DONE: 1}, keep),),
                           group="Garden"))
    keep = lambda o: o[0] == "drum.png"  # noqa: E731
    out.append(_objs_asset(sheets, "drum", va.PUZZLES, "Drum", (("found", {S_DRUM_B: 1}, keep),), group="Drum"))
    keep = lambda o: o[0] in ("scaffolding.png", "tchest.png") and o[1] >= 0x430 and o[2] >= 0x530  # noqa: E731
    out.append(_objs_asset(sheets, "chest", va.PUZZLES, "Treasure chest", (
        ("digging", {S_CHEST: 1}, keep), ("digging (above 400)", {S_CHEST: 0x191}, keep),
        ("found", {S_CHEST_DONE: 1}, keep)), group="Treasure chest"))
    keep = lambda o: o[0] in ("graves.png", "graveflowers.png") and o[2] >= 0xC8  # noqa: E731
    out.append(_objs_asset(sheets, "graveyard", va.BUILDINGS, "Graveyard", (
        ("one grave", {S_GRAVES: 1}, keep), ("ten graves", {S_GRAVES + i * GRAVE_STRIDE: 1 for i in range(10)}, keep),
        ("full (50 graves)", {S_GRAVES + i * GRAVE_STRIDE: 1 for i in range(GRAVE_SLOTS)}, keep)),
        group="Graves", note="each grave's look is (its value + column + row) % 4; the flowers belong to slots"))
    keep = lambda o: o[0] == "graveflowers.png" and o[2] < 0xC0  # noqa: E731
    out.append(_objs_asset(sheets, "flowers", va.BUILDINGS, "Grave flowers", (
        ("four flowers (0xA000)", {S_FLOWERS_A: 1}, keep), ("one flower (0xA098)", {S_FLOWERS_B: 1}, keep)),
        group="Graves"))
    for i in range(4):
        if sheets.has("graves.png"):
            out.append(Asset(f"grave{i}", va.BUILDINGS, f"Grave, look {i + 1}",
                             (Frame("", (frame_draw(sheets, atlas("graves.png", 4, 1), i, 0, 0),)),), group="Graves",
                             proof="frame of 0x416380's graves.png"))
    # The whole island: tiles, then its objects.
    tiles_ok = all(sheets.has(n) for n in tile_files())
    if tiles_ok:
        out.append(Asset("island", va.SCENE, "The island", (Frame("", tuple(island_tiles_plan(sheets))),),
                         group="The island", note="the 16 tiles of 512 x 512 at their places (0x4115C0 / 0x411550)",
                         proof="emulated 0x4115C0 + 0x411550"))
        frames = []
        for label, state in (("a new game", NEW_GAME), ("everything built and solved", EVERYTHING_BUILT)):
            objs = island_objects(state)
            if all(sheets.has(o[0]) for o in objs):
                frames.append(Frame(label, tuple(island_tiles_plan(sheets) + objects_plan(sheets, objs))))
        if frames:
            out.append(Asset("island_objects", va.SCENE, "The island with its objects", tuple(frames),
                             group="The island", note="tiles then the scene list, as the village draws them before "
                                                      "the villagers (0x4224A0: 0x411550 then 0x415E60)",
                             proof="emulated 0x4115C0 + 0x411550, 0x416380 + 0x415E60"))
    if sheets.has("overview_bg.jpg"):
        frames = []
        for label, state in (("a new game", NEW_GAME), ("everything built and solved", EVERYTHING_BUILT)):
            objs = island_objects(state)
            if all(sheets.has(o[0]) for o in objs if o[0] not in MAP_SKIPPED):
                frames.append(Frame(label, tuple([whole_draw(sheets, "overview_bg.jpg", 0, 0)]
                                                 + map_objects_plan(sheets, objs))))
        out.append(Asset("map", va.SCENE, "The map", tuple(frames), group="The map",
                         note="overview_bg.jpg and the island's objects at 25% (0x42A5A0 / 0x415ED0); the game clips "
                              "them to the map's area, which is not done here; the villagers on the map are left out",
                         proof="emulated 0x42A5A0 (0x415ED0 inside)"))
    return [a for a in out if a is not None]


def _creature_assets(sheets) -> list[Asset]:
    if not sheets.has(BUTTERFLY.name):
        return []
    out = []
    names = ("first", "second", "third", "fourth", "fifth")
    for c in range(BUTTERFLY_COLOURS):
        frames = []
        for heading, side in ((-1, "flying left"), (1, "flying right")):
            for wing in (0, 1):
                frames.append(Frame(f"{side}, wings {wing + 1}",
                                    (butterfly_plan(sheets, 0, 0, c, wing, heading),)))
        out.append(Asset(f"butterfly{c}", va.CREATURES, f"Butterfly, {names[c]} colour", tuple(frames),
                         group="Butterflies", note="drawn at its own size (100%) here; the game gives each "
                                                   "butterfly a size of its own",
                         proof="emulated 0x412AB0"))
    return out


def _effect_assets(sheets) -> list[Asset]:
    out = []
    for name, cols, label in EFFECTS:
        if not sheets.has(name):
            continue
        out.append(Asset(f"effect:{name}", va.EFFECTS, label, tuple(
            Frame(f"frame {f + 1}", (particle_plan(sheets, name, cols, f, 0, 0),)) for f in range(cols)),
            group="Particles", note="each frame of the particle's sheet as 0x41AB20 draws it",
            proof="emulated 0x41AB20"))
    if sheets.has("carrying.png"):
        out.append(Asset("effect:fade", va.EFFECTS, "Fading item", tuple(
            Frame(f"age {age}", (particle_plan(sheets, "carrying.png", 15, age, 0, 0, fixed=0),))
            for age in range(0, 10, 2)), group="Particles",
            note="a particle with a fixed frame (here carrying.png cell 1) loses 0.1 of its alpha per step of its "
                 "age; which items the game drops this way was not traced",
            proof="emulated 0x41AB20"))
    return out


def _tech_assets(sheets) -> list[Asset]:
    names = [t[1] for t in TECHS]
    if not _has(sheets, "tech_bg.png", *names):
        return []
    out = []
    for label, name, _field, x, y in TECHS:
        crop = pi.Draw("tech_bg.png", (x, y, x + 3 * TECH_SEGMENT, y + sheets.size(name)[1]), x, y,
                       what="the screen under the bar")
        frames = [Frame("empty (the Tech screen's bar, uncoloured)", (crop,))]
        for level in (1, 2, 3):
            frames.append(Frame(f"level {level}", (crop,) + tuple(tech_screen_plan(
                sheets, {name: level}, background=False, only=name))))
        out.append(Asset(f"tech:{name}", va.TECH, f"{label} bar", tuple(frames), group="Technology bars",
                         note="the bar's three cells joined as the Tech screen draws them; under them the screen's "
                              "own picture cut to the bar (a crop, not a separate picture)",
                         proof="emulated 0x433B20"))
    frames = []
    for level in (1, 2, 3):
        frames.append(Frame(f"every technology at level {level}",
                            tuple(tech_screen_plan(sheets, {n: level for n in names}))))
    frames.append(Frame("fading in (alpha 0.5), level 2", tuple(tech_screen_plan(
        sheets, {n: 2 for n in names}, stage=1, alpha=0.5))))
    if all(sheets.has(b) for b, _x, _y in TECH_BUTTONS):
        frames.append(Frame("level 2, with its buttons", tuple(
            tech_screen_plan(sheets, {n: 2 for n in names})
            + [d for b, bx, by in TECH_BUTTONS for d in button_plan(sheets, b, 0, bx, by)])))
    out.append(Asset("tech:screen", va.TECH, "Tech screen", tuple(frames), group="The screen",
                     note="the buttons' places are read from 0x4347E0's 0x4019B0 calls (their text is not drawn)",
                     proof="emulated 0x433B20 (and 0x401340 for the buttons)"))
    return out


def _meter_assets(sheets) -> list[Asset]:
    out = []
    values = (0, 10, 25, 50, 75, 100)
    if sheets.has("StatusBarSliceB.png"):
        for k, row in enumerate(sorted(SKILL_ROWS), 1):
            out.append(Asset(f"skill{row}", va.METERS, f"Skill bar, row {k}", tuple(
                Frame(f"{v}%", tuple(skill_bar_plan(sheets, row, v))) for v in values if v),
                group="Details screen", note="value 0 draws nothing", proof="emulated 0x42F500"))
    if _has(sheets, "StatusBarSliceR.png", "healthBarbulb.png"):
        out.append(Asset("health", va.METERS, "Health bar", tuple(
            Frame(f"{v}%", tuple(skill_bar_plan(sheets, HEALTH_ROW, v))) for v in (1,) + values[1:]),
            group="Details screen", note="at 1% only the bulb shows", proof="emulated 0x42F500"))
    if _has(sheets, "LoadColor.png", "BambooMeterFrame1.png"):
        out.append(Asset("loading", va.METERS, "Loading bar", tuple(
            Frame(f"{p}%", tuple(loading_bar_plan(sheets, p, 0, 0))) for p in (3, 25, 50, 75, 100)),
            group="Loading", note="the bamboo frame is drawn again after every segment; under 3% nothing is drawn",
            proof="emulated 0x436FB0"))
    return out


def _panel_assets(sheets) -> list[Asset]:
    out = []
    for colour, name in (("Green", "GreenDlgTileGrid.png"), ("Orange", "OrangeDlgTileGrid.png")):
        if not sheets.has(name):
            continue
        out.append(Asset(f"dialog:{name}", va.PANELS, f"{colour} dialog frame", tuple(
            Frame(f"{w} x {h} ({where})", tuple(dialog_plan(sheets, name, w, h))) for w, h, where in DIALOG_SIZES),
            group="Dialogs", note="at the sizes the game asks for (the dialogs built at the functions named)",
            proof="emulated 0x40C670 + 0x40C4D0"))
    labels = ("normal", "mouse over", "pressed")
    for name, _sites in BUTTONS:
        if not sheets.has(name):
            continue
        out.append(Asset(f"button:{name}", va.PANELS, name.rsplit(".", 1)[0], tuple(
            Frame(labels[s], tuple(button_plan(sheets, name, s))) for s in range(3)), group="Buttons",
            note="its three pictures as a button draws them (frames 0, 1, 2 for the widget's three draw states, "
                 "in the usual order normal, mouse over, pressed: which input picks each was not traced); the "
                 "greyed look of a disabled button is a per-pixel blend (0x408C60) and is not drawn here",
            proof="emulated 0x4019B0 + 0x401340"))
    for name, label in (("radioblank.png", "Radio button"), ("radioselected.png", "Radio button, selected"),
                        ("WideSlider2.png", "Slider"), ("sliderhandle.png", "Slider handle")):
        if sheets.has(name):
            out.append(va.one(sheets, f"panel:{name}", va.PANELS, label, name, group="Options",
                              note="drawn whole by the options dialog (0x428910)", proof="constructor 0x409ED0"))
    return out


def _icon_assets(sheets) -> list[Asset]:
    out = []
    if sheets.has("checkmark.png"):
        out.append(Asset("checkmark", va.ICONS, "Job checkmark", tuple(
            Frame(f"job {i + 1}", (whole_draw(sheets, "checkmark.png", x, y),)) for i, (x, y) in
            enumerate(CHECK_PLACES)), group="Details screen",
            note="marks the villager's job on the Details screen (0x449146); places read from that function, "
                 "not emulated", proof="read from 0x449146"))
    for name, label in (("arrowglow.png", "Glowing arrow, up"), ("arrowglowdown.png", "Glowing arrow, down"),
                        ("arrowleftglow.png", "Glowing arrow, left"),
                        ("arrowrightglow.png", "Glowing arrow, right")):
        if sheets.has(name):
            out.append(va.one(sheets, f"icon:{name}", va.ICONS, label, name, group="Tutorial arrows",
                              note="the tutorial's pointing arrows (0x435EB0)", proof="constructor 0x409ED0"))
    return out


def _cursor_assets(sheets) -> list[Asset]:
    out = []
    for name, label in (("hand_open.png", "Hand, open"), ("hand.png", "Hand, holding")):
        if sheets.has(name):
            out.append(Asset(f"cursor:{name}", va.CURSORS, label, (Frame("", tuple(cursor_plan(sheets, name))),),
                             group="Hand", note="its middle is the mouse's point (0x408240 sets the hot spot to "
                                                "half its size)", proof="emulated 0x408240 + 0x409060"))
    return out


def _villager_parts(sheets) -> list[Asset]:
    out = []
    if sheets.has("peep_shadow1.png"):
        out.append(Asset("shadow", va.VILLAGERS, "Shadow", (
            Frame("on the ground", (whole_draw(sheets, "peep_shadow1.png", 0, 0),)),
            Frame("held by the hand (alpha 0.5)", (whole_draw(sheets, "peep_shadow1.png", 0, 0, alpha=0.5),))),
            group="Under a villager", proof="emulated 0x437790 (tests/test_pictures_vv1.py)"))
    if sheets.has("focus_circle.png"):
        out.append(va.one(sheets, "focus", va.VILLAGERS, "Selection circle", "focus_circle.png",
                          group="Under a villager", proof="emulated 0x437790 (tests/test_pictures_vv1.py)"))
    if sheets.has("skelly.png"):
        out.append(Asset("skelly", va.VILLAGERS, "Skeleton", tuple(
            Frame(f"bones {i + 1}", (frame_draw(sheets, atlas("skelly.png", 4, 1), i, 0, 0),)) for i in range(4)),
            group="The dead", proof="emulated 0x437790 (tests/test_pictures_vv1.py)"))
    if sheets.has("ripple.png"):
        out.append(Asset("ripple", va.VILLAGERS, "Swimming ripple", tuple(
            Frame(f"frame {i + 1}", (va.cell_plan(sheets, atlas("ripple.png", 4, 1), i, 0, alpha=pi.f32(0.4)),))
            for i in range(4)), group="Swimming", note="drawn at alpha 0.4",
            proof="emulated 0x437790 (tests/test_pictures_vv1.py)"))
    return out


def _screen_assets(sheets) -> list[Asset]:
    out = []
    if sheets.has("SPLASH_BG.jpg"):
        out.append(va.one(sheets, "splash", va.SCREENS, "Splash screen", "SPLASH_BG.jpg",
                          proof="emulated 0x431620"))
    if _has(sheets, "bxshtBG.png", "Boxshtfeat.png", "logo1.png", "Lavaglow.png", *(c for c, _a in CLOUDS)):
        out.append(Asset("title", va.SCREENS, "Title screen", (Frame("", tuple(title_plan(sheets))),),
                         note="one moment of the drifting clouds and the pulsing lava glow (their places and alpha "
                              "are the game's ranges, picked here); the butterflies are left out",
                         proof="emulated 0x425DF0"))
    if _has(sheets, "bxshtBG.png", "logo1.png", "ldwLogo.png", "LoadColor.png", "BambooMeterFrame1.png"):
        out.append(Asset("loading_screen", va.SCREENS, "Loading screen", tuple(
            Frame(f"{p}% loaded", tuple(loading_screen_plan(sheets, p))) for p in (25, 100)),
            note="the white half-transparent rectangle the game fills over the background is not drawn",
            proof="emulated 0x41F570"))
    if sheets.has("puzzles_bg.png"):
        pages = ("help1.jpg", "help2.jpg", "help3.jpg", "help4.jpg", "credits.jpg")
        frames = [Frame(f"page {i + 1}" if i < 4 else "credits", tuple(help_plan(sheets, i)))
                  for i, p in enumerate(pages) if sheets.has(p)]
        out.append(Asset("help", va.SCREENS, "Help", tuple(frames), proof="emulated 0x41DD00"))
    if _has(sheets, "puzzles_bg.png", "puzzle_solved.jpg", "puzzle_covers.jpg"):
        out.append(Asset("puzzles", va.SCREENS, "Puzzles screen", (
            Frame("none solved", tuple(puzzle_screen_plan(sheets, set()))),
            Frame("half solved", tuple(puzzle_screen_plan(sheets, set(range(0, 16, 2))))),
            Frame("all solved", tuple(puzzle_screen_plan(sheets, set(range(16)))))),
            proof="emulated 0x42D5C0"))
        out.append(Asset("puzzle_pictures", va.PUZZLES, "Puzzle pictures", tuple(
            Frame(f"puzzle {i + 1}, solved", (frame_draw(sheets, atlas("puzzle_solved.jpg", 4, 4), i, 0, 0),))
            for i in range(16)) + tuple(
            Frame(f"puzzle {i + 1}, cover", (frame_draw(sheets, atlas("puzzle_covers.jpg", 4, 4), i, 0, 0),))
            for i in range(16)), group="Puzzles screen",
            note="numbered in the screen's order (left to right, top to bottom)", proof="emulated 0x42D5C0"))
    for name, label, fn in (("gamewin_bg.jpg", "You won", "0x41D5E0"), ("intro1_bg.png", "Story, page 1", "0x41D5E0"),
                            ("intro2_bg.png", "Story, page 2", "0x41EBE0"), ("main_BG.png", "Main panel", "0x41F9B0"),
                            ("VD_BG.png", "Villager details", "0x449146"), ("overview_bg.jpg", "Map", "0x42A5A0")):
        if sheets.has(name):
            out.append(va.one(sheets, f"screen:{name}", va.SCREENS, label, name,
                              note=f"its background, drawn whole at (0, 0) first by {fn}; what is drawn over it "
                                   "(text, buttons, villagers) is not", proof=f"emulated {fn} (its first blit)"))
    if _has(sheets, "main_BG.png", *(b for b, _x, _y in MAIN_BUTTONS)):
        out.append(Asset("main_panel", va.SCREENS, "Main panel with its buttons", (Frame("", tuple(
            [whole_draw(sheets, "main_BG.png", 0, 0)]
            + [d for b, x, y in MAIN_BUTTONS for d in button_plan(sheets, b, 0, x, y)])),),
            note="the buttons at the places 0x4224A0 gives them; their text and the panel's numbers are not drawn",
            proof="main_BG emulated (0x41F9B0), each button emulated (0x401340); the places read from 0x4224A0"))
    if _has(sheets, "VD_BG.png", "StatusBarSliceB.png", "StatusBarSliceR.png", "healthBarbulb.png",
            "checkmark.png"):
        plan = [whole_draw(sheets, "VD_BG.png", 0, 0)]
        for row in (3, 5, 7, 6, 4, 8):
            plan += skill_bar_plan(sheets, row, 60)
        plan.append(whole_draw(sheets, "checkmark.png", *CHECK_PLACES[0]))
        out.append(Asset("details", va.SCREENS, "Villager details with its bars", (Frame("every bar at 60%",
                                                                                         tuple(plan)),),
                         note="the background, the six bars (in 0x449146's order) and the job checkmark; the "
                              "villager and the text are not drawn",
                         proof="the bars emulated (0x42F500); the order and the checkmark read from 0x449146"))
    return out


def _patcher_assets(sheets) -> list[Asset]:
    out = []
    if sheets.has("mask_atlas.png"):
        at = atlas("mask_atlas.png", 7, 5)
        colours = ("blue", "orange", "purple", "red", "chief")
        out.append(Asset("p:masks", va.PATCHER, "Origins masks", tuple(
            Frame(f"{colours[r]}, facing {c + 1}", (va.cell_plan(sheets, at, c, r),)) for r in range(5)
            for c in range(7)), group="Origins", patcher=True,
            note="7 facings x 5 masks, cut as the game's 0x40A070 cuts the patcher's mask atlas (worn on the head: "
                 "the Villagers tab draws them on villagers)", proof="constructor 0x40A070"))
    for sex, name in (("man", "vvfp_grey_male_heads.png"), ("woman", "vvfp_grey_female_heads.png")):
        if sheets.has(name):
            at = atlas(name, 7, 20)
            out.append(Asset(f"p:{name}", va.PATCHER, f"Grey heads ({sex})", tuple(
                Frame(f"head {r}, facing {c + 1}", (va.cell_plan(sheets, at, c, r),)) for r in range(20)
                for c in range(7)), group="Grey Hair at 55", patcher=True,
                note="the stock 7 x 20 head layout (the Villagers tab draws them on villagers)",
                proof="constructor 0x40A070"))
    if sheets.has("golden_mushroom.png"):
        out.append(Asset("p:golden", va.COLLECTIBLES, "Super-Secret Golden Mushroom", (
            Frame("", (whole_draw(sheets, "golden_mushroom.png", 6, 2, what="golden mushroom"),)),),
            group="Golden Mushroom", patcher=True,
            note="drawn by VVFP Golden Mushroom.dll in place of carrying.png frame 15, moved by (6, 2) from that "
                 "cell's top-left (native/vvfp_golden_mushroom); placed from its source, not emulated",
            proof="read from vvfp_golden_mushroom.c"))
    if sheets.has("vvfp_sort_band.png"):
        out.append(va.one(sheets, "p:band", va.PATCHER, "Sort By band", "vvfp_sort_band.png", group="Sort By",
                          patcher=True, note="built 1 x 1 by VVFP VV1 Sort By.dll; its place is not shown",
                          proof="read from vv1_sort_by.c"))
    if sheets.has("vvfp_sort_radio.png"):
        at = atlas("vvfp_sort_radio.png", 3, 1)
        out.append(Asset("p:radio", va.PATCHER, "Sort By radio button", tuple(
            Frame(f"picture {c + 1}", (va.cell_plan(sheets, at, c, 0),)) for c in range(3)), group="Sort By",
            patcher=True, note="built 3 x 1 by VVFP VV1 Sort By.dll; its place is not shown",
            proof="read from vv1_sort_by.c"))
    for stem, label in ORIGINS_ICONS:
        if sheets.has(stem + ".png"):
            out.append(va.one(sheets, f"p:{stem}", va.PATCHER, label, stem + ".png", group="Origins window icons",
                              patcher=True, note="shown in the patcher's Origins window (a Windows dialog), not "
                                                 "drawn by the game", proof="sheet"))
    return out


def assets(sheets) -> list[Asset]:
    """Every composed asset of A New Home (the Source sheets are added by vv_pictures_assets)."""
    out: list[Asset] = []
    for part in (_island_assets, _creature_assets, _effect_assets, _tech_assets, _meter_assets, _panel_assets,
                 _icon_assets, _cursor_assets, _villager_parts, _screen_assets, _patcher_assets):
        out += part(sheets)
    if all(sheets.has(f) for f, *_r in FONTS):
        for name, _site, _fn in FONTS:
            out.append(va.one(sheets, f"font:{name}", va.FONTS, name.rsplit(".", 1)[0], name, group="Fonts",
                              note="the font's picture; its glyph rectangles are tables in the executable and text is "
                                   "not composed here", proof="loaded whole at 0x402319"))
    return out
