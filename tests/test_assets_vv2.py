"""Picture Studio's Everything tab, The Lost Children (src/vv_assets_vv2.py), proven against the stock executable.

* THE DRAWS.  Every composed picture the module calls GENERATED is the game's own draw routine run in Unicorn
  (scripts/emulate_vv2_assets.py): the village's scene list (0x41C1D0 fills it from the world's state, 0x41B630
  draws it) for every hut, building, puzzle, crop and grave state, the island's tiles (0x411FF0 / 0x411F80), the
  collections screen (0x416180), the Tech screen (0x441830), the Villager Details bars (0x43C470), the bamboo
  meter (0x4451B0), the dialog panels (0x40D050 / 0x40CEB0), every button in every state (0x4010B0 / 0x401360)
  and the birds (0x4135C0).  Here each routine runs again and every blit it makes (file, cell rectangle, place,
  scale, alpha) must be the module's plan, in order, the plan's rectangles cut from the sheets' sizes alone.  A
  swept state (build points, food, coconuts ...) is checked at both ends of its range and just outside it.
* THE TABLE.  sheet_table() is every call the executable makes to its sprite constructors (0x40A270, 0x40A0D0,
  0x40A2F0, the picture loader 0x40A730), its button maker 0x4019D0 and its font loader 0x402110, each with the
  names and numbers it passes: the whole .text section is scanned for them.
* THE CUT.  The game's cell cut 0x40A190 on every sprite the table builds agrees with vv_picture_image.Atlas.cell.
* THE FONTS.  The glyph rectangles are the font loader's own.

The emulated checks need the stock executable, the game's pictures (their sizes) and Unicorn / pefile (the scan:
capstone); without them they skip.  The checks at the end need nothing (a fake source of PNG headers).
"""
from __future__ import annotations

import functools
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_picture_image as pi  # noqa: E402
import vv_pictures_assets as pa  # noqa: E402
import vv_assets_vv2 as m  # noqa: E402

EXE = ROOT / "research" / "stock-executables" / m.EXE_NAME
IMAGES = ROOT / "research" / "game-images" / "Virtual Villagers - The Lost Children" / "Images"

try:
    import pefile  # noqa: F401
    import unicorn  # noqa: F401
    HAVE_UNICORN = True
except ImportError:
    HAVE_UNICORN = False
try:
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    HAVE_CAPSTONE = True
except ImportError:
    HAVE_CAPSTONE = False

EMULATE = HAVE_UNICORN and EXE.is_file() and IMAGES.is_dir()


@functools.lru_cache(maxsize=None)
def _emu():
    import emulate_vv2_assets as ev
    return ev, ev.Emu()


def _sheets():
    return pa.AssetSheets(pi.FolderSource(IMAGES.parent))


def _plan_keys(sheets, entries) -> list[tuple]:
    return [d.key() for d in m.plan_of(sheets, entries)]


def _generated() -> dict:
    return {a[0]: a for a in m.GENERATED}


# ------------------------------------------------------------------ the draws

@unittest.skipUnless(EMULATE, "the stock The Lost Children, its pictures and Unicorn are needed")
class DrawsMatchTheGame(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ev, cls.e = _emu()
        cls.sheets = _sheets()
        cls.gen = _generated()

    def _compare(self, key: str, frames) -> int:
        """frames: the recipe's [(label, blits, alphas, ...)], compared with the module's plans."""
        rows = self.gen[key][6]
        mine = {r[0]: r[1] for r in rows}
        drawn = [f for f in frames if f[1]]
        self.assertEqual([f[0] for f in drawn], [r[0] for r in rows], key)
        n = 0
        for f in drawn:
            self.assertEqual(_plan_keys(self.sheets, mine[f[0]]), self.ev.keys(f[1]), f"{key}: {f[0]}")
            n += 1
        return n

    def test_every_recipe_but_the_scene(self) -> None:
        n = 0
        for recipe in self.ev.RECIPES:
            if recipe is self.ev.scene_assets:
                continue
            for key, *_rest, frames in recipe(self.e):
                n += self._compare(key, frames)
        self.assertGreater(n, 150)

    def test_the_scene_objects_in_every_state(self) -> None:
        sc = self.ev.Scene(self.e)
        defs = {d[0]: d for d in self.ev.SCENE_DEFS}
        n = 0
        for key, d in defs.items():
            sites = d[4]
            rows = self.gen[key][6]
            self.assertTrue(rows, key)
            for label, entries, state, span in rows:
                want = _plan_keys(self.sheets, entries)
                blits, _alphas = sc.draw(state, sites)
                self.assertEqual(want, self.ev.keys(blits), f"{key}: {label}")
                n += 1
                if span is None:
                    continue
                field, a, b, first, last = span
                st = dict(state)
                st[field] = b
                self.assertEqual(want, self.ev.keys(sc.draw(st, sites)[0]), f"{key}: {label} at {b}")
                for outside in (a - 1, b + 1):
                    if first <= outside <= last:
                        st[field] = outside
                        self.assertNotEqual(want, self.ev.keys(sc.draw(st, sites)[0]),
                                            f"{key}: {label} also at {outside}")
        self.assertGreater(n, 100)

    def test_a_swept_state_drawing_nothing_is_left_out(self) -> None:
        # the first new hut at 0 points draws its frame 0; the second draws nothing until it has a point
        self.assertTrue(self.gen["hut1"][6][0][0].startswith("0 build"))
        self.assertTrue(self.gen["hut2"][6][0][0].startswith("1 to"))

    def test_the_fonts(self) -> None:
        self.assertEqual(self.ev.font_glyphs(self.e), {k: [tuple(r) for r in v] for k, v in m.GLYPHS.items()})


@unittest.skipUnless(EMULATE, "the stock The Lost Children, its pictures and Unicorn are needed")
class CellCutMatchesTheGame(unittest.TestCase):
    def test_every_one_sheet_sprite(self) -> None:
        _ev, e = _emu()
        sheets = _sheets()
        n = 0
        for spec in m.sheet_table():
            # a whole picture (0x40A0D0) has no cells: the game draws it whole (0x408820, the rect (0, 0, w, h))
            if spec.whole or tuple(spec.sheets) != (1, 1) or not all(sheets.has(f) for f in spec.files()):
                continue
            sprite = e.sprite(spec.name, spec.cols, spec.rows)
            for row in range(spec.rows + 1):            # one past the last: the cut clamps
                for col in range(spec.cols + 1):
                    want = spec.atlas.cell(sheets.size, col, row)[1]
                    self.assertEqual(e.cell(sprite, col, row), want, f"{spec.name} {col},{row}")
                    n += 1
        self.assertGreater(n, 1500)


# ------------------------------------------------------------------ the table is the executable's every call

def _image():
    import pefile as pe_module
    pe = pe_module.PE(str(EXE))
    base = pe.OPTIONAL_HEADER.ImageBase
    text = next(s for s in pe.sections if s.Name.startswith(b".text"))
    return base, pe.get_memory_mapped_image(), base + text.VirtualAddress, text.Misc_VirtualSize


def _cstr(img, base, va):
    off = va - base
    if not 0 <= off < len(img):
        return None
    end = img.find(b"\0", off)
    s = img[off:end]
    return s.decode() if 1 <= len(s) < 120 and all(32 <= c < 127 for c in s) else None


def _calls(img, base, t0, size, target):
    data = img[t0 - base:t0 - base + size]
    out, i = [], 0
    while True:
        i = data.find(b"\xE8", i)
        if i < 0 or i > len(data) - 5:
            return out
        if t0 + i + 5 + struct.unpack_from("<i", data, i + 1)[0] == target:
            out.append(t0 + i)
        i += 1


def _window(md, img, base, site):
    """The instructions from just after the previous call to the call at `site` (the call's own arguments)."""
    for k in range(0x90, 0, -1):
        seq = list(md.disasm(img[site - k - base:site - base + 5], site - k))
        ends = [s.address for s in seq]
        if site in ends:
            seq = seq[:ends.index(site)]
            calls = [j for j, s in enumerate(seq) if s.mnemonic == "call"]
            return seq[calls[-1] + 1:] if calls else seq[-24:]
    return []


def _args(md, img, base, site):
    """(picture names the call's arguments name, the numbers it pushes last-pushed first)."""
    seq = _window(md, img, base, site)
    names, numbers = [], []
    for ins in seq:
        for v in re.findall(r"0x4[0-9a-f]{5}", ins.op_str):
            s = _cstr(img, base, int(v, 16))
            if s and s not in names:
                names.append(s)
    for ins in reversed(seq):
        if ins.mnemonic == "push":
            numbers.append(ins.op_str)
    return names, numbers


def _num(text: str, seq) -> int | None:
    try:
        return int(text, 0)
    except ValueError:
        return None


@unittest.skipUnless(HAVE_CAPSTONE and HAVE_UNICORN and EXE.is_file(), "the stock executable and capstone")
class TableIsTheExecutables(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base, cls.img, cls.t0, cls.size = _image()
        cls.md = Cs(CS_ARCH_X86, CS_MODE_32)
        cls.where: dict[int, set] = {}
        for spec in m.sheet_table():
            for part in spec.where.split("; "):
                for site in re.findall(r"0x([0-9A-F]{6})\*?", part.split(" at ", 1)[-1].split(" (")[0]):
                    cls.where.setdefault(int(site, 16), set()).add((spec.name, spec.cols, spec.rows))

    def calls(self, target: int) -> list[int]:
        return _calls(self.img, self.base, self.t0, self.size, target)

    def test_every_one_sheet_call(self) -> None:
        sites = self.calls(m.ONE_SHEET)
        self.assertEqual(len(sites), 107)
        for site in sites:
            if site == m.BUTTON_SHEET_SITE:
                continue                                   # the button's own name: the button calls below
            names, nums = _args(self.md, self.img, self.base, site)
            names = [n for n in names if n.casefold().endswith((".png", ".jpg"))]
            cols, rows = (_num(x, None) for x in nums[1:3])
            got = {(n, cols if cols is not None else "reg", rows if rows is not None else "reg") for n in names}
            want = self.where.get(site, set())
            # a count in a register (ebp = 2 at the two loaders that set it) is the table's own number
            got = {(n, c if c != "reg" else next(w[1] for w in want if w[0] == n),
                    r if r != "reg" else next(w[2] for w in want if w[0] == n)) for n, c, r in got}
            self.assertEqual(got, want, f"0x{site:X}")

    def test_every_whole_picture_call(self) -> None:
        sites = self.calls(m.WHOLE)
        internal = {0x40A292}                             # 0x40A270's own call, with its name argument
        self.assertEqual(len(sites), 41)
        for site in sites:
            if site in internal:
                continue
            if site == m.TILE_SITE:
                self.assertEqual({w[0] for w in self.where[site]}, set(m.tile_files()))
                continue
            names, _nums = _args(self.md, self.img, self.base, site)
            names = {n for n in names if n.casefold().endswith((".png", ".jpg"))}
            self.assertEqual({(n, 1, 1) for n in names}, self.where.get(site, set()), f"0x{site:X}")

    def test_the_grids_buttons_fonts_and_loader(self) -> None:
        grids = self.calls(m.GRID)
        self.assertEqual(sorted(grids), sorted(g[4] for g in m.GRIDS))
        for prefix, sheets, cols, rows, site in m.GRIDS:
            names, nums = _args(self.md, self.img, self.base, site)
            self.assertIn(prefix, names)
            self.assertEqual([_num(x, None) for x in nums[4:6]], [cols, rows], prefix)
        buttons: dict[int, set] = {}
        for name, sites in m.BUTTONS:
            for s in sites:
                buttons.setdefault(int(str(s).rstrip("*"), 16) if isinstance(s, str) else s, set()).add(name)
        made = self.calls(m.BUTTON_MAKER)
        self.assertEqual(sorted(made), sorted(buttons))
        for site in made:
            names, _nums = _args(self.md, self.img, self.base, site)
            self.assertEqual({n for n in names if n.endswith(".png")}, buttons[site], f"0x{site:X}")
        fonts = self.calls(m.FONT_LOADER)
        self.assertEqual(sorted(fonts), sorted(f[1] for f in m.FONTS_BUILT))
        for name, site, table in m.FONTS_BUILT:
            names, nums = _args(self.md, self.img, self.base, site)
            self.assertIn(name[:-4], names)
            self.assertIn(f"0x{table:x}", nums)
        loader = self.calls(m.PICTURE)
        self.assertEqual(sorted(loader), [0x4025A9, 0x40A110, 0x40A3E2])   # the font, 0x40A0D0's, 0x40A2F0's

    def test_every_picture_name_is_built(self) -> None:
        """Every picture name in the executable is one the table builds (or a part of one: the tiles, grids)."""
        names = set()
        for mt in re.finditer(rb"[A-Za-z0-9_\-]{2,60}\.(?:png|jpg|PNG|JPG)\0", self.img):
            names.add(mt.group()[:-1].decode().casefold())
        built = {f.casefold() for spec in m.sheet_table() for f in spec.files()}
        self.assertEqual(names - built - {"boxshot.jpg"}, set())        # "boxshot.jpg": the tail of vv2_boxshot.jpg

    def test_the_never_drawn_sprites(self) -> None:
        """scene+0x1648 (smallwaves01) and scene+0x15E4 (stoolfood) are read only by the scene's destructor."""
        for off, store in ((0x1648, 0x41DDED), (0x15E4, 0x41DBF5)):
            hits = []
            for ins in self.md.disasm(self.img[self.t0 - self.base:self.t0 - self.base + self.size], self.t0):
                if f"+ 0x{off:x}]" in ins.op_str:
                    hits.append(ins.address)
            self.assertEqual(len(hits), 2, f"+0x{off:X}: {[hex(h) for h in hits]}")
            self.assertIn(store, hits)
            other = next(h for h in hits if h != store)
            self.assertTrue(0x41B330 <= other < 0x41B580, hex(other))


# ------------------------------------------------------------------ with nothing (as on CI)

SIZES = {
    'BambooMeterFrame1.png': (320, 30), 'Checkbox.png': (48, 32), 'CheckboxChecked.png': (48, 32),
    'CheckboxStrip.png': (96, 32), 'CloudBack.png': (264, 20), 'CloudMiddle.png': (264, 24),
    'Cloudfront.png': (228, 48), 'GreenDlgTileGrid.png': (576, 64), 'LoadColor.png': (8, 30),
    'MS_Button_01.png': (364, 52), 'MS_Button_02.png': (256, 50), 'MS_Button_03.png': (300, 60),
    'MS_Button_04.png': (288, 40), 'OrangeDlgTileGrid.png': (576, 64), 'ProcessedHorizBambStrip3.png': (80, 12),
    'ProcessedVertBambStrip1.png': (120, 8), 'SPLASH_BG.jpg': (800, 600), 'Shore02.png': (328, 456),
    'StatusBar.png': (16, 16), 'StatusBarSliceB.png': (16, 16), 'StatusBarSliceR.png': (16, 16),
    'VD_BG_2.png': (800, 600), 'WideSlider2.png': (260, 32), 'algae.png': (240, 240), 'arrowglow.png': (100, 100),
    'arrowglowdown.png': (100, 100), 'arrowleftglow.png': (100, 100), 'arrowrightglow.png': (100, 100),
    'beetles_big.png': (244, 169), 'bfg_logo.png': (168, 168), 'bigwave01.png': (333, 536), 'bird.png': (600, 25),
    'bird_shadow.png': (51, 25), 'blink.png': (100, 10), 'blurry_sparkle.png': (200, 20), 'boxes.png': (372, 388),
    'briars.png': (300, 77), 'bubble.png': (200, 20), 'building.jpg': (288, 80), 'butterflies_big.png': (244, 169),
    'buy_button.png': (304, 28), 'candlestrip.png': (180, 20), 'carrying.png': (520, 50), 'checkmark.png': (32, 32),
    'clothinghut.png': (180, 166), 'collectables_images.png': (240, 360), 'collections_bg.jpg': (800, 600),
    'coveredpot.png': (34, 35), 'crate.png': (164, 58), 'credits.jpg': (639, 472), 'culture.jpg': (288, 80),
    'dam.jpg': (252, 224), 'detailradiobtn.png': (96, 32), 'dragonflies.png': (210, 140), 'dust.png': (270, 30),
    'dust2.png': (270, 30), 'empty1.png': (388, 32), 'exploration.jpg': (288, 80), 'farming.jpg': (288, 80),
    'female_heads.png': (280, 1950), 'female_heads_old.png': (280, 1950), 'firestrip.png': (512, 256),
    'flood.jpg': (512, 408), 'foam.png': (192, 96), 'focus_circle.png': (68, 64), 'foodStates.png': (348, 109),
    'gamewin_bg.jpg': (800, 600), 'gongsmall.png': (100, 100), 'graveflowers.png': (201, 46), 'graves.png': (220, 44),
    'hand.png': (54, 54), 'hand_open.png': (54, 54), 'healthBarbulb.png': (28, 28), 'help1.jpg': (639, 472),
    'help2.jpg': (639, 472), 'help3.jpg': (639, 472), 'help4.jpg': (639, 472), 'hospital.png': (287, 152),
    'info_button.png': (112, 28), 'intro1_bg.jpg': (800, 600), 'intro2_bg.jpg': (800, 600),
    'intro3_bg.jpg': (800, 600), 'ldwBurweed27.png': (793, 54), 'ldwLogo.png': (168, 178),
    'ldwarialbold.png': (728, 40), 'leafCover.png': (59, 63), 'leaningspears.png': (27, 52),
    'leftarrow.png': (120, 36), 'loading.jpg': (800, 600), 'logo1.png': (300, 172), 'main_BG.png': (800, 600),
    'main_detail_button.png': (345, 52), 'main_wide_button.png': (384, 32), 'main_wide_button2.png': (388, 32),
    'male_heads.png': (280, 1950), 'male_heads_old.png': (280, 1950), 'medicine.jpg': (288, 80),
    'medwaves01.png': (258, 441), 'mosaicCovers1.png': (510, 510), 'mosaicCovers2.png': (510, 510),
    'overview_bg.jpg': (800, 600), 'pebbles_big.png': (244, 169), 'peep_shadow1.png': (68, 64),
    'petalstrip.png': (600, 300), 'popup_button1.png': (420, 32), 'puzzle_covers.jpg': (640, 472),
    'puzzle_solved.jpg': (640, 472), 'puzzles_bg.png': (800, 600), 'radioblank.png': (32, 32),
    'radioselected.png': (32, 32), 'rainbow.png': (500, 25), 'research_button.png': (172, 28),
    'researchstates.png': (412, 71), 'rightarrow.png': (120, 36), 'ripple.png': (260, 65),
    'scaffolding.png': (97, 45), 'scarecrow.png': (100, 59), 'science.jpg': (288, 80),
    'sharp_sparkle.png': (200, 20), 'shells_big.png': (244, 169), 'shore01.png': (328, 456), 'skelly.png': (240, 65),
    'sliderhandle.png': (16, 32), 'small_huts.png': (400, 272), 'smallwaves01.png': (149, 317),
    'sparklestrip.png': (250, 25), 'sparklestrip2.png': (120, 12), 'speartips.png': (17, 22), 'spray.png': (1200, 100),
    'stoolfood.png': (35, 8), 'sunkenGong.jpg': (39, 54), 'tech_bg.jpg': (800, 600), 'tinyflowers.png': (22, 22),
    'totems.png': (320, 100), 'ultra_wide_button.png': (1203, 42), 'veggies.png': (300, 200),
    'vines1.png': (178, 143), 'vines2.png': (183, 196), 'vines3.png': (187, 242), 'vines4.png': (204, 253),
    'vv2_boxshot.jpg': (800, 600), 'waterfallanimA.png': (512, 512), 'waterfallanimb.png': (240, 60),
    'waves_proto.png': (500, 50), 'wetFarm.jpg': (335, 296), 'wheel_pieces.png': (300, 300),
    'woodpile.png': (67, 44), 'yellow_sparkle.png': (300, 30),
}
for _x in range(4):
    for _y in range(4):
        SIZES[f"MapX{_x}Y{_y}.jpg"] = (512, 512)
for _p in ("female", "male"):
    for _k in range(3):
        SIZES[f"{_p}_actions0{_k}.png"] = (360, 650)
        for _a in range(2):
            SIZES[f"{_p}_bodies{_a}{_k}.png"] = (640, 650)
NEVER_LOADED = {"Checkbox.png", "CheckboxChecked.png", "CloudBack.png", "CloudMiddle.png", "Cloudfront.png",
                "ProcessedHorizBambStrip3.png", "ProcessedVertBambStrip1.png", "StatusBar.png", "bfg_logo.png",
                "buy_button.png", "detailradiobtn.png", "dust.png", "main_wide_button.png"}


def _header(w: int, h: int) -> bytes:
    """Just enough of a PNG for its size (no pixels)."""
    return pi.PNG_MAGIC + b"\0\0\0\rIHDR" + struct.pack(">II", w, h) + b"\x08\x06\0\0\0"


class _Fake:
    """Every picture of the stock Images folder as a bare PNG header of its real size."""
    problem = ""

    def __init__(self, names=None, extra=None) -> None:
        self.sizes = dict(SIZES if names is None else {n: SIZES[n] for n in names})
        self.sizes.update(extra or {})
        self.folded = {k.casefold(): k for k in self.sizes}

    def read(self, name: str) -> bytes | None:
        key = self.folded.get(name.casefold())
        return _header(*self.sizes[key]) if key else None

    def names(self) -> list[str]:
        return list(self.sizes)


class WithNothing(unittest.TestCase):
    def test_the_table(self) -> None:
        table = m.sheet_table()
        keys = [(s.name.casefold(), s.cols, s.rows, tuple(s.sheets)) for s in table]
        self.assertEqual(len(keys), len(set(keys)))
        by = {s.name: s for s in table}
        self.assertEqual((by["small_huts.png"].cols, by["small_huts.png"].rows), (2, 2))
        self.assertEqual((by["popup_button1.png"].cols, by["popup_button1.png"].rows), (3, 1))
        self.assertTrue(by["MapX3Y3.jpg"].whole and by["ldwarialbold.png"].whole)
        self.assertEqual(by["female_bodies"].sheets, (2, 3))
        self.assertEqual({s.name for s in table if not s.used}, set(m.NEVER_DRAWN))
        files = {f.casefold() for s in table for f in s.files()}
        self.assertEqual({n for n in SIZES if n.casefold() not in files}, NEVER_LOADED)

    def test_every_generated_file_is_built(self) -> None:
        files = {f.casefold() for s in m.sheet_table() for f in s.files()}
        grids = m.grids()
        for key, *_r, rows in m.GENERATED:
            for _label, entries, _state, _span in rows:
                for name, col, row, *_rest in entries:
                    self.assertIn(name.casefold(), files, key)
                    cols, rws = grids[name.casefold()]
                    self.assertTrue(0 <= col < cols and 0 <= row < rws, (key, name, col, row))

    def test_everything_builds_from_sizes_alone(self) -> None:
        sheets = pa.AssetSheets(pa.PatcherOverlay(_Fake(), {}))
        assets = pa.all_assets(2, sheets, m)
        self.assertEqual(len({a.key for a in assets}), len(assets))
        cats = {a.category for a in assets}
        for c in (pa.CREATURES, pa.BUILDINGS, pa.PUZZLES, pa.COLLECTIBLES, pa.PLANTS, pa.VILLAGERS, pa.SCENE, pa.TECH,
                  pa.METERS, pa.PANELS, pa.ICONS, pa.CURSORS, pa.FONTS, pa.EFFECTS, pa.SCREENS, pa.UNUSED, pa.SHEETS):
            self.assertIn(c, cats)
        frames = sum(len(a.frames) for a in assets)
        self.assertGreater(frames, 1500)
        for a in assets:
            self.assertIn(a.category, pa.CATEGORIES)
            for f in a.frames:
                for d in f.plan:
                    self.assertIsInstance(d, pi.Draw)
                    l, t, r, b = d.rect
                    w, h = sheets.size(d.file)
                    self.assertTrue(0 <= l < r <= w and 0 <= t < b <= h, (a.key, f.label, d))
        unused = {a.label for a in assets if a.category == pa.UNUSED and a.group == "Never loaded by the game"}
        self.assertEqual(unused, NEVER_LOADED)

    def test_a_missing_picture_drops_only_what_needs_it(self) -> None:
        names = [n for n in SIZES if n not in ("small_huts.png", "bird.png", "tech_bg.jpg")]
        sheets = pa.AssetSheets(pa.PatcherOverlay(_Fake(names), {}))
        keys = {a.key for a in m.assets(sheets)}
        self.assertNotIn("hut1", keys)
        self.assertNotIn("bird", keys)
        self.assertIn("tech:Farming", keys)
        self.assertIn("hospital", keys)
        self.assertNotIn("screen:tech", keys)              # every frame of it needs tech_bg.jpg

    def test_the_patcher_art(self) -> None:
        art = m.patcher_art()
        for stem, _label in m.ORIGINS_ICONS:
            self.assertIsNotNone(pa.read_patcher_art(art[stem + ".png"]), stem)
        extra = {name: pa.picture_size(pa.read_patcher_art(path)) for name, path in art.items()}
        sheets = pa.AssetSheets(pa.PatcherOverlay(_Fake(extra=extra), {}))
        patcher = [a for a in m.assets(sheets) if a.patcher]
        self.assertTrue(patcher)
        self.assertTrue(all(a.category == pa.PATCHER for a in patcher))
        if m.MASK_FILE in art:
            masks = next(a for a in patcher if a.key == "patcher:masks")
            self.assertEqual(len(masks.frames), 40)
            self.assertEqual(masks.frames[0].plan[0].rect, (0, 0, 65, 145))

    def test_the_mask_atlas_is_the_dlls(self) -> None:
        if not m.ORIGINS_DLL.is_file():
            self.skipTest("the Origins DLL is not in assets")
        data = pi.pe_resource(m.ORIGINS_DLL.read_bytes(), *m.MASK_RESOURCE)
        self.assertEqual(pa.picture_size(data), (520, 725))
        self.assertEqual(pa.read_patcher_art(m.patcher_art()[m.MASK_FILE]), data)
        self.assertIn(m.MASK_FILE, m.patcher_images())

    def test_the_glyphs(self) -> None:
        self.assertEqual(set(m.GLYPHS), {"ldwBurweed27.png", "ldwarialbold.png"})
        for name, rows in m.GLYPHS.items():
            w, h = SIZES[name]
            self.assertGreater(len(rows), 60)
            self.assertEqual(rows[0][0], ord("A"))
            for code, (l, t, r, b) in rows:
                self.assertTrue(0 <= l <= r <= w and 0 <= t < b <= h, (name, code))

    def test_sweep_labels_and_states(self) -> None:
        gen = _generated()
        self.assertEqual([r[0] for r in gen["hut1"][6]],
                         ["0 build points", "1 to 225 build points", "226 or more build points", "finished"])
        for key, *_r, rows in m.GENERATED:
            labels = [r[0] for r in rows]
            self.assertEqual(len(labels), len(set(labels)), key)


@unittest.skipUnless(IMAGES.is_dir(), "the game's pictures (research/game-images) are needed")
class WithTheGamesPictures(unittest.TestCase):
    def test_pixels(self) -> None:
        sheets = _sheets()
        by = {a.key: a for a in m.assets(sheets)}
        for key, label in (("bird", None), ("panel:Green", "400 x 300"), ("button:popup_button1.png", "pressed"),
                           ("hut1", "finished"), ("bar:8", "50 of 100")):
            asset = by[key]
            frame = next(f for f in asset.frames if label is None or f.label == label)
            image = pa.render_frame(sheets, frame)
            self.assertIsNotNone(image.bbox(), key)
        panel = pa.render_frame(sheets, by["panel:Green"].frames[1])
        self.assertEqual((panel.width, panel.height), (448, 320))   # 0x40CE30: ceil(400 / 64) x ceil(300 / 64) tiles


if __name__ == "__main__":
    unittest.main()
