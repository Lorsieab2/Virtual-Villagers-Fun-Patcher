"""Picture Studio, The Secret City: src/vv_pictures_vv3.py's drawing rules, proven against the game's own code.

* The villager draw: the stock executable's own villager draw 0x4605F0 runs in Unicorn
  (tests/story_emulator.py) on records made for each case, with the game's own resource table (0x4A95A0),
  atlas constructors (0x45C730 -> 0x42E750 -> 0x40AF10 / 0x40AF90), camera setter (0x42E250), camera
  draws (0x42E5E0, 0x42E570, 0x42E510), cell cut (0x40AE30), place-scaled (0x408780) and draw wrappers --
  only the sheet loader (the PNG reading, 0x40B3D0) is replaced by a sheet of the stock size, and the
  blitter 0x404620 is recorded.  Every blit (sheet, cell, place, scale, alpha) must be the plan's.
* The blitter: the game's 0x404620 runs on real pixels for a child's scaled-down draw and the ripple's
  surface alpha (Windows' 53-bit x87 precision), and its screen must be what vv_picture_image gives.
* The Origins mask: its registration is read from the companion's own C source
  (native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c VV3WorldMaskDrawAt).
* The save reader, on a synthetic save (never the owner's).

The emulated checks need the stock executable in research/stock-executables (and Unicorn); the pixel checks
the game's art in research/game-images.  Without them they skip, as on CI.
"""
from __future__ import annotations

import random
import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_picture_image as pi  # noqa: E402
import vv_pictures_common as common  # noqa: E402
import vv_pictures_vv3 as v3  # noqa: E402

STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
ART = ROOT / "research" / "game-images" / "Virtual Villagers - The Secret City"
DLL_SOURCE = ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.c"

try:
    import pefile  # noqa: F401
    from unicorn.x86_const import UC_X86_REG_FPCW
    from story_emulator import API_STUBS, Process
    HAVE_EMULATOR = True
except ImportError:                                     # CI: no Unicorn, no pefile
    HAVE_EMULATOR = False

EMULATED = HAVE_EMULATOR and STOCK.is_file()
WHY = "needs the stock The Secret City executable in research/stock-executables and Unicorn"

GAME_OBJECT = 0x59E110          # the village (0x42E3F0: ecx for 0x4605F0)
RECORDS = GAME_OBJECT + 0x14
STRIDE = 0x1F8C
CAMERA = 0x58F6F8
DRAW = 0x4605F0
BLITTER = 0x404620
WINDOWS_FPCW = 0x027F           # the x87 as Windows runs a program: 53-bit precision, round to nearest


def _f32bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def _bitsf32(value: int) -> float:
    return struct.unpack("<f", struct.pack("<I", value & 0xFFFFFFFF))[0]


def _s32(value: int) -> int:
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value & 0x80000000 else value


class VillageEmulator:
    """The stock executable with its villager draw ready to run on one record."""

    def __init__(self) -> None:
        p = self.p = Process(STOCK.read_bytes())
        p.mu.mem_map(API_STUBS, 0x10000)
        p.api_names = {}
        slot = 0
        for entry in p._exe_pe.DIRECTORY_ENTRY_IMPORT:
            for imp in entry.imports:
                if imp.name:
                    stub = API_STUBS + slot * 16
                    slot += 1
                    p.mu.mem_write(stub, b"\xC3")
                    p.api_names[stub] = imp.name.decode()
                    p.mu.mem_write(imp.address, struct.pack("<I", stub))
        self.names: dict[int, str] = {}
        self.blits: list = []
        self.water = False
        self.ripple = 0
        p.stub(0x46EC93, lambda q: (q.alloc(max(q.arg(0), 4)), 0))       # operator new
        p.stub(0x40B3D0, self._sheet)                                     # a sheet: its PNG, here its size
        p.stub(BLITTER, self._blit)
        p.stub(0x423090, lambda q: (1 if self.water else 0, 8))           # inside the island's map?
        p.stub(0x420580, lambda q: (5 if self.water else 0, 8))           # the cmap's kind under the feet
        p.stub(0x4032D0, lambda q: (99, 0))                               # rand(n): no splash particle
        p.stub(0x428B60, lambda q: (0x1000, 0))                           # the random source (cdecl)
        p.stub(0x403330, lambda q: (self.ripple, 0))                      # ... its next number
        p.stub(0x426610, lambda q: (1, 0))
        p.stub(0x429400, lambda q: (0, 0x20))
        renderer = p.alloc(0x200)
        p.write(renderer + 0x60, struct.pack("<iiii", 0, 0, 20000, 20000))  # its clip rectangle
        wrapper = p.alloc(16)
        p.put32(wrapper, renderer)
        p.put32(0x4B34A8, wrapper)
        p.put32(GAME_OBJECT + 4, wrapper)
        self._fpu()
        p.call(0x42E250, [0, 0, _f32bits(1.0)], ecx=CAMERA)                # no scroll, zoom 1.0
        p.call(0x45C730, [], ecx=GAME_OBJECT)                             # the game's own atlases

    def _fpu(self) -> None:
        self.p.mu.reg_write(UC_X86_REG_FPCW, WINDOWS_FPCW)

    def _sheet(self, q):
        this, name = q.reg("ecx"), q.cstring(q.arg(0))
        w, h = {**v3.SIZES, "focus_circle.png": (68, 64)}[name]     # the selection ring: loaded, never pictured
        surface = q.alloc(0x40)
        q.put32(surface + 8, w)
        q.put32(surface + 12, h)
        q.put32(this, surface)
        self.names[surface] = name
        return this, 4

    def _blit(self, q):
        a = [q.arg(i) for i in range(10)]
        self.blits.append((self.names[a[0]], _s32(a[1]), _s32(a[2]), tuple(_s32(v) for v in a[3:7]),
                           _bitsf32(a[7]), _bitsf32(a[8]), a[9]))
        return 0, 0x28

    def draw(self, look: v3.Look, x: int = 1000, y: int = 1000) -> list[tuple]:
        """The game's blits for a villager in `look`, as (file, rect, x, y, scale, alpha byte)."""
        p = self.p
        r = RECORDS
        p.write(r, bytes(STRIDE))
        fields = {0xDC4: (4, look.age), 0xDC8: (4, 0 if look.male else 1), 0xDCC: (4, look.dead_frame),
                  0xDF0: (4, look.head), 0xDF4: (4, look.body), 0xE78: (4, 0 if look.dead else 100),
                  0xE90: (4, look.litter), 0xEE0: (4, x), 0xEE4: (4, y), 0xEFC: (4, look.frame),
                  0xF04: (4, look.height), 0xF10: (1, 1), 0xF12: (1, 1 if look.held else 0),
                  0xF14: (4, look.direction), 0xF18: (4, look.facing),
                  0xF1C: (4, v3.NO_SHADOW_JOB if look.shadow == "off" else 0), 0xF20: (4, look.item)}
        for off, (size, value) in fields.items():
            p.write(r + off, (value & ((1 << (8 * size)) - 1)).to_bytes(size, "little"))
        self.water, self.ripple, self.blits = look.swimming, look.ripple, []
        self._fpu()
        p.call(DRAW, [0], ecx=GAME_OBJECT)
        out = []
        for file, bx, by, rect, alpha, scale, centred in self.blits:
            assert not (centred and scale != 1.0), "a centred scaled blit: the plan does not model it"
            out.append((file.casefold(), rect, bx, by, round(scale, 6), pi.surface_alpha(alpha)))
        return out


@unittest.skipUnless(EMULATED, WHY)
class VillagerDrawIsTheGames(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.emu = VillageEmulator()

    def check(self, look: v3.Look, label: str) -> None:
        want = [d.key() for d in v3.plan(look, 1000, 1000, mask_art=False)]
        self.assertEqual(self.emu.draw(look), want, label)

    def test_atlases_are_the_resource_tables(self) -> None:
        """Each atlas the draw uses (0x45C730's resource ids) is the table entry 0x4A95A0 names."""
        import pefile as pf
        pe = pf.PE(str(STOCK))
        image, base = pe.get_memory_mapped_image(), pe.OPTIONAL_HEADER.ImageBase

        def text(va):
            return image[va - base:va - base + 64].split(b"\0", 1)[0].decode()
        table = {}
        for i in range(0xB5):
            f = struct.unpack_from("<7I", image, 0x4A95A0 + i * 0x30 - base)
            table[f[0]] = (text(f[1]), f[2], f[3], (f[5], f[6]) if f[5] else (1, 1))
        for rid, atlas in ((0x88, v3.ATLASES[("male", "heads")]), (0x89, v3.ATLASES[("male", "heads_old")]),
                           (0x8A, v3.ATLASES[("male", "bodies")]), (0x8B, v3.ATLASES[("male", "actions")]),
                           (0x84, v3.ATLASES[("female", "heads")]), (0x85, v3.ATLASES[("female", "heads_old")]),
                           (0x86, v3.ATLASES[("female", "bodies")]), (0x87, v3.ATLASES[("female", "actions")]),
                           (0x71, v3.CARRYING), (0x75, v3.COLLECTABLES), (0x8E, v3.SKELLY), (0x8F, v3.RIPPLE)):
            self.assertEqual(table[rid], (atlas.name, atlas.cols, atlas.rows, tuple(atlas.sheets)), hex(rid))
        self.assertEqual(table[0x8D][0], v3.SHADOW)

    def test_head_tables_are_the_games(self) -> None:
        self.emu.draw(v3.Look())
        p = self.emu.p
        by_direction = tuple(struct.unpack_from("<ii", p.read(0x59E018, 32), 8 * k) for k in range(4))
        by_frame = tuple(struct.unpack_from("<ii", p.read(0x59E038, 0x88), 8 * k) for k in range(17))
        self.assertEqual(by_direction, v3.HEAD_BY_DIRECTION)
        self.assertEqual(by_frame, v3.HEAD_BY_FRAME)

    def test_adults_every_frame_direction_and_head(self) -> None:
        n = 0
        for male in (True, False):
            for frame in range(25):
                for direction in range(4):
                    for facing in range(8):
                        look = v3.Look(male=male, age=600, head=(frame + facing) % 30,
                                       body=(frame * 7 + direction) % 30, frame=frame, direction=direction,
                                       facing=facing)
                        self.check(look, f"adult {male} frame {frame} direction {direction} facing {facing}")
                        n += 1
        self.assertEqual(n, 1600)

    def test_every_head_and_body_row(self) -> None:
        for male in (True, False):
            for k in range(30):
                self.check(v3.Look(male=male, head=k, body=k, frame=17 + k % 8), f"rows {k}")
                self.check(v3.Look(male=male, head=k, body=29 - k, frame=k % 17), f"action rows {k}")

    def test_children_at_every_age(self) -> None:
        for age in range(0, 280):
            for frame in (8, 9, 17 + age % 8, age % 17):
                self.check(v3.Look(male=age % 2 == 0, age=age, head=age % 30, body=(age * 3) % 30, frame=frame,
                                   direction=age % 4, facing=(age * 5) % 8), f"child {age} frame {frame}")

    def test_old_head_from_1100(self) -> None:
        for age in (1098, 1099, 1100, 1101, 1600):
            for male in (True, False):
                self.check(v3.Look(male=male, age=age, head=4), f"age {age}")
        self.assertIn("old", v3.plan(v3.Look(age=1100), mask_art=False)[-1].file)
        self.assertNotIn("old", v3.plan(v3.Look(age=1099), mask_art=False)[-1].file)

    def test_the_dead(self) -> None:
        for age in (0, 100, 279, 280, 900, 1500):
            for frame in range(4):
                self.check(v3.Look(age=age, dead=True, dead_frame=frame), f"dead {age} {frame}")

    def test_shadows_heights_and_held(self) -> None:
        for shadow in ("on", "held", "off"):
            for height in (0, 1, 13, -1, -9):
                for age in (40, 600):
                    self.check(v3.Look(age=age, shadow=shadow, height=height, frame=19),
                               f"{shadow} {height} {age}")

    def test_carried_items_and_babies(self) -> None:
        for item in list(range(0, 52, 5)) + [51, 0x2A, 0x34, 0x34 + 20, 0x34 + 53]:
            for direction in range(4):
                for litter in (1, 2, 3):
                    for age in (30, 600):
                        self.check(v3.Look(age=age, item=item, litter=litter, direction=direction, frame=20),
                                   f"item {item} dir {direction} litter {litter}")

    def test_swimming(self) -> None:
        for direction in range(4):
            for ripple in range(4):
                for age in (10, 200, 600):
                    for frame in (9, 17, 22, 4):
                        for item in (-1, 0x2A, 7):
                            for shadow in ("on", "held"):
                                self.check(v3.Look(age=age, direction=direction, ripple=ripple, frame=frame,
                                                   item=item, swimming=True, shadow=shadow),
                                           f"swim {direction} {ripple} {age} {frame} {item} {shadow}")

    def test_random_states(self) -> None:
        rng = random.Random(20261031)
        for _ in range(1500):
            look = v3.Look(male=rng.random() < .5, age=rng.choice([rng.randrange(280), rng.randrange(280, 2000)]),
                           head=rng.randrange(30), body=rng.randrange(30), frame=rng.randrange(25),
                           direction=rng.randrange(4), facing=rng.randrange(8),
                           shadow=rng.choice(["on", "held", "off"]), item=rng.choice([-1, rng.randrange(52),
                                                                                      0x34 + rng.randrange(54)]),
                           litter=rng.choice([1, 2, 3]), swimming=rng.random() < .25, ripple=rng.randrange(4),
                           height=rng.choice([0, 0, rng.randrange(-5, 30)]), dead=rng.random() < .05,
                           dead_frame=rng.randrange(4))
            self.check(look, str(vars(look)))


@unittest.skipUnless(EMULATED, WHY)
class BlitterIsTheGames(unittest.TestCase):
    """The pixels: The Secret City's blitter 0x404620 on a test picture against vv_picture_image."""

    @staticmethod
    def pattern(w: int, h: int) -> bytes:
        return b"".join(bytes(((x * 37 + y * 11) % 256, (x * 5 + y * 13) % 256, (x * y) % 256,
                               (0 if (x + y) % 7 == 0 else 255 if (x * y) % 3 else (x * 29 + y * 3) % 256)))
                        for y in range(h) for x in range(w))

    def setUp(self) -> None:
        p = self.p = Process(STOCK.read_bytes())
        p.mu.mem_map(API_STUBS, 0x10000)
        p.api_names = {}
        slot = 0
        for entry in p._exe_pe.DIRECTORY_ENTRY_IMPORT:
            for imp in entry.imports:
                if imp.name:
                    stub = API_STUBS + slot * 16
                    slot += 1
                    p.mu.mem_write(stub, b"\xC3")
                    p.api_names[stub] = imp.name.decode()
                    p.mu.mem_write(imp.address, struct.pack("<I", stub))
        p.api_handlers["SDL_LockSurface"] = lambda q: (0, 0)
        p.api_handlers["SDL_UnlockSurface"] = lambda q: (0, 0)
        self.sw, self.sh = 160, 120
        self.screen = self.surface(self.sw, self.sh, 0)
        self.gfx = p.alloc(0x100)
        p.put32(self.gfx + 0x30, self.screen)
        p.put32(self.gfx + 8, self.sw)
        p.put32(self.gfx + 12, self.sh)

    def surface(self, w: int, h: int, amask: int) -> int:
        p = self.p
        fmt = p.alloc(0x40)
        p.write(fmt + 8, bytes((32, 4)))
        p.write(fmt + 12, struct.pack("<IIII", 0x00FF0000, 0x0000FF00, 0x000000FF, amask))
        p.write(fmt + 28, bytes((0, 0, 0, 0 if amask else 8, 16, 8, 0, 24 if amask else 0)))
        s = p.alloc(0x40)
        pixels = p.alloc(w * h * 4 + 16)
        p.put32(s + 4, fmt)
        p.write(s + 8, struct.pack("<iii", w, h, w * 4))
        p.put32(s + 20, pixels)
        p.write(s + 36, struct.pack("<iiii", 0, 0, w, h))
        return s

    def blit(self, src: int, rect, x: int, y: int, alpha: float, scale: float) -> list:
        p = self.p
        p.write(p.u32(self.screen + 20), bytes((30, 200, 10, 0)) * (self.sw * self.sh))
        p.mu.reg_write(UC_X86_REG_FPCW, WINDOWS_FPCW)
        p.call(BLITTER, [src, x, y, *rect, _f32bits(alpha), _f32bits(scale), 0], ecx=self.gfx)
        raw = p.read(p.u32(self.screen + 20), self.sw * self.sh * 4)
        return [(raw[i + 2], raw[i + 1], raw[i]) for i in range(0, len(raw), 4)]

    def expected(self, piece: pi.Image, x: int, y: int, alpha: int) -> list:
        out = [(10, 200, 30)] * (self.sw * self.sh)
        for j in range(piece.height):
            for i in range(piece.width):
                r, g, b, a = piece.pixel(i, j)
                if alpha < 255:
                    a = (a * alpha + 127) >> 8
                if a == 0:
                    continue
                d = out[(y + j) * self.sw + x + i]
                out[(y + j) * self.sw + x + i] = tuple((s * a + dv * (255 - a) + 0x7F) >> 8 for s, dv in zip((r, g, b), d))
        return out

    def test_children_scaled_down(self) -> None:
        w, h = 88, 70
        rgba = self.pattern(w, h)
        sheet = pi.Image(w, h, rgba)
        argb = bytearray(len(rgba))
        argb[0::4], argb[1::4], argb[2::4], argb[3::4] = rgba[2::4], rgba[1::4], rgba[0::4], rgba[3::4]
        src = self.surface(w, h, 0xFF000000)
        self.p.write(self.p.u32(src + 20), bytes(argb))
        for age in (0, 35, 99, 140, 200, 255, 279):
            for scale in (v3.camera_scale(v3.body_scale(age)), v3.camera_scale(v3.head_scale(age))):
                for rect in ((0, 0, 40, 65), (40, 0, 80, 65), (3, 2, 43, 67)):
                    got = self.blit(src, rect, 20, 9, 1.0, scale)
                    want = self.expected(pi.blit_piece(sheet, rect, scale), 20, 9, 255)
                    self.assertEqual(got, want, f"age {age} scale {scale} rect {rect}")

    def test_ripple_alpha(self) -> None:
        w, h = 65, 65
        rgba = self.pattern(w, h)
        sheet = pi.Image(w, h, rgba)
        argb = bytearray(len(rgba))
        argb[0::4], argb[1::4], argb[2::4], argb[3::4] = rgba[2::4], rgba[1::4], rgba[0::4], rgba[3::4]
        src = self.surface(w, h, 0xFF000000)
        self.p.write(self.p.u32(src + 20), bytes(argb))
        got = self.blit(src, (0, 0, 65, 65), 30, 20, pi.f32(0.4), 1.0)
        want = self.expected(sheet, 30, 20, pi.surface_alpha(pi.f32(0.4)))
        # The game's alpha path also blends the fully clear pixels (a darkening by one step that no
        # transparent picture can hold): compare only where the sprite has any alpha.
        mask = [False] * (self.sw * self.sh)
        for j in range(h):
            for i in range(w):
                if sheet.pixel(i, j)[3] and (sheet.pixel(i, j)[3] * 102 + 127) >> 8:
                    mask[(20 + j) * self.sw + 30 + i] = True
        self.assertEqual([g for g, m in zip(got, mask) if m], [w_ for w_, m in zip(want, mask) if m])


class MaskIsTheCompanions(unittest.TestCase):
    """The Origins mask: VV3WorldMaskDrawAt's own numbers."""

    def test_registration_constants(self) -> None:
        if not DLL_SOURCE.is_file():
            self.skipTest("the companion's source is not in this checkout")
        src = DLL_SOURCE.read_text(encoding="utf-8", errors="replace")
        self.assertEqual(int(re.search(r"#define VV3_WORLD_MASK_X_NUDGE_PX \((-?\d+)\)", src).group(1)), v3.MASK_X)
        self.assertEqual(int(re.search(r"#define VV3_WORLD_MASK_Y_NUDGE_PX \((-?\d+)\)", src).group(1)), v3.MASK_Y)
        table = re.search(r"VV3_WORLD_MASK_X_NUDGE_BY_FACING\[8\] = \{([^}]*)\}", src).group(1)
        self.assertEqual(tuple(int(t) for t in table.replace("\n", " ").split(",")), v3.MASK_X_BY_FACING)
        self.assertIn('mask_atlas_name[] = "heathen_masks.png"', src)
        self.assertRegex(src, r"push 5\s+/\* rows")
        self.assertRegex(src, r"push 8\s+/\* cols")
        self.assertIn("mask_args[3] = mask - 1;", src)
        self.assertIn("facing = mask_args[4] & 7;", src)
        self.assertIn("return (int)(value >= 0.0f ? value + 0.5f : value - 0.5f);", src)
        rc = (DLL_SOURCE.parent / "vv3_full_mastery_candidate.rc").read_text(encoding="utf-8", errors="replace")
        self.assertIn("assets/vv3_heathen_masks/heathen_masks.png", rc)
        self.assertEqual(v3.patcher_art()["heathen_masks.png"], ROOT / "assets" / "vv3_heathen_masks" / "heathen_masks.png")

    def test_the_shipped_companion_carries_the_same_atlas(self) -> None:
        """The release zip carries the Origins companion, not the loose file: its RCDATA 5000 is the same
        bytes, and the renderer reads it when the loose file is missing."""
        loose = ROOT / "assets" / "vv3_heathen_masks" / "heathen_masks.png"
        if not (loose.is_file() and v3.SHIPPED_DLL.is_file()):
            self.skipTest("the atlas or the companion is not in this checkout")
        self.assertEqual(pi.pe_resource(v3.SHIPPED_DLL.read_bytes(), *v3.MASK_RESOURCE), loose.read_bytes())
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('"data/candidates/VVFP VV3 Safe Upgrades.dll"', release)
        saved = v3.MASK_ART
        try:
            v3.MASK_ART = ROOT / "no such file.png"
            self.assertEqual(v3.patcher_art(), {})
            self.assertEqual(v3.load(None).source.read("heathen_masks.png"), loose.read_bytes())
        finally:
            v3.MASK_ART = saved

    def test_mask_follows_the_head(self) -> None:
        for age in (0, 120, 279, 600):
            for facing in range(8):
                for mask in range(1, 6):
                    plan = v3.plan(v3.Look(age=age, facing=facing, mask=mask))
                    head, drawn = plan[-2], plan[-1]
                    self.assertEqual((head.what, drawn.what), ("head", "mask"))
                    hs = v3.head_scale(age)
                    self.assertEqual(drawn.file, "heathen_masks.png")
                    self.assertEqual(drawn.rect, (65 * facing, 145 * (mask - 1), 65 * facing + 65, 145 * mask))
                    self.assertEqual(drawn.x, head.x + v3.mask_nudge(-10 + (-4 if facing < 2 else 0), hs))
                    self.assertEqual(drawn.y, head.y + v3.mask_nudge(-33, hs))
                    self.assertEqual(drawn.scale, head.scale)
        self.assertEqual(v3.mask_nudge(-33, 1.0), -33)
        self.assertEqual(v3.mask_nudge(-14, 0.8), -11)       # -11.2 rounds to -11
        self.assertEqual(v3.mask_nudge(-10, 0.85), -9)       # -8.5 rounds away from zero


class Numbers(unittest.TestCase):
    def test_sizes(self) -> None:
        self.assertEqual(v3.body_scale(0), 0.5)
        self.assertEqual(v3.body_scale(280), 1.0)
        self.assertEqual(v3.head_scale(280), 1.0)
        self.assertAlmostEqual(v3.head_scale(0), 0.8, places=6)
        self.assertEqual(v3.camera_scale(v3.body_scale(100)), pi.percent_scale(64))
        self.assertEqual(v3.camera_scale(1.0), 1.0)

    def test_required_files_and_choices(self) -> None:
        files = v3.required_files()
        self.assertIn("male_bodies12.png", files)
        self.assertIn("female_actions02.png", files)
        self.assertNotIn("heathen_masks.png", files)            # the patcher's own art, from assets
        (subject,) = v3.load(pi.Pictures(3, None)).custom_choices()
        fields = {f.key: f for f in subject.fields}
        self.assertEqual([o.key for o in fields["head"].options], list(range(30)))
        self.assertEqual([o.key for o in fields["body"].options], list(range(30)))
        self.assertIn("robe", fields["body"].options[29].label)
        self.assertEqual(len(fields["mask"].options), 6)
        self.assertTrue(all(o.patcher for o in fields["mask"].options[1:]))
        stages = [o.key for o in fields["stage"].options]
        self.assertEqual(stages[:14], [y * 20 for y in range(14)])
        self.assertIn("dead", stages)
        self.assertEqual(len(fields["pose"].options), 19)

    def test_custom_specs(self) -> None:
        r = v3.load(pi.Pictures(3, None))
        r.sheets = v3._Sizes                                     # plan without the art
        look = r.custom_look({"sex": "female", "stage": 1200, "head": 3, "body": 29, "look": 1, "mask": 2,
                              "pose": 8, "direction": 2, "frame": 0, "facing": "auto", "shadow": "off"})
        self.assertEqual((look.male, look.age, look.frame, look.facing, look.shadow), (False, 1200, 8, 2, "off"))
        plan = v3.plan(look)
        self.assertEqual(plan[-2].file, "female_heads.png")    # Young look over an elder
        self.assertEqual(plan[-1].file, "heathen_masks.png")
        old = v3.plan(r.custom_look({"stage": 200, "look": 2}))
        self.assertEqual(old[-1].file, "male_heads_old.png")   # Old look on a child
        swim = v3.plan(r.custom_look({"pose": "swim", "frame": 2}))
        self.assertEqual([d.what for d in swim], ["shadow", "ripple", "head"])
        dead = v3.plan(r.custom_look({"stage": "dead", "frame": 3}))
        self.assertEqual([(d.what, d.rect) for d in dead], [("skeleton", (180, 0, 240, 65))])


def _entry(name: str, *, male=True, age=600, head=3, body=5, health=100, chief=False, skills=(10,) * 5,
           dead_frame=1, litter=1, father="Aru", mother="Bea") -> bytes:
    """A saved The Secret City villager entry (0x11C bytes: u32 flag, record +0xDC4.. at +4; name at +0x14)."""
    e = bytearray(0x11C)
    struct.pack_into("<I", e, 0, 1)
    n = 0x14

    def put(rec_off: int, value: int) -> None:
        struct.pack_into("<i", e, n + rec_off - 0xDD4, value)
    put(0xDC4, age)
    put(0xDC8, 0 if male else 1)
    put(0xDCC, dead_frame)
    e[n:n + len(name)] = name.encode()
    put(0xDF0, head)
    put(0xDF4, body)
    e[n + 0x24:n + 0x24 + len(father)] = father.encode()
    e[n + 0x3D:n + 0x3D + len(mother)] = mother.encode()
    put(0xE78, health)
    e[n + 0xE80 - 0xDD4] = 1 if chief else 0
    put(0xE90, litter)
    for k, s in enumerate(skills):
        put(0xEAC + 4 * k, s)
    return bytes(e)


class SyntheticSave(unittest.TestCase):
    def make(self, folder: Path) -> list[bytes]:
        entries = [_entry("Kaimana", chief=True, body=29, age=900), _entry("Lani", male=False, age=120, head=7),
                   _entry("Moku", age=1300, skills=(90, 95, 88, 1, 2)), _entry("Pua", health=0, dead_frame=2)]
        data = bytes(0x400) + b"".join(entries) + bytes(0x11C) + bytes(0x200)
        (folder / "Virtual Villagers - The Secret City1.ldw").write_bytes(data)
        return entries

    def test_items_and_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.make(folder)
            r = v3.load(pi.Pictures(3, None))
            items = r.saved_items(folder, 1)
            self.assertEqual([i.label for i in items],
                             ["Kaimana (adult, 45 years)", "Lani (child, 6 years)", "Moku (elder, 65 years)",
                              "Pua (dead, 30 years)"])
            self.assertEqual([i.location for i in items], ["Villagers"] * 3 + ["Bodies awaiting burial"])
            self.assertIn("Tribal Chief", items[0].detail)
            self.assertIn("Esteemed Elder", items[2].detail)
            self.assertIn("Female", items[1].detail)
            r.sheets = v3._Sizes
            dead = r.plan_saved(folder, 1, items[3].id, frame=2)
            self.assertEqual([d.what for d in dead], ["skeleton"])
            child = r.plan_saved(folder, 1, items[1].id)
            self.assertEqual(child[-1].file, "female_heads.png")
            elder = r.plan_saved(folder, 1, items[2].id)
            self.assertEqual(elder[-1].file, "male_heads_old.png")

    def test_a_saved_villager_can_carry(self) -> None:
        """Codex (PR #660): From my save offers the carried item and the litter Make your own has, and
        they reach the plan exactly as the custom tab's do."""
        r = v3.load(pi.Pictures(3, None))
        saved = {f.key: f for f in r.saved_fields()}
        custom = {f.key: f for f in r.custom_choices()[0].fields}
        for key in ("item", "litter"):
            self.assertIn(key, saved)
            self.assertEqual([o.key for o in saved[key].options], [o.key for o in custom[key].options])
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.make(folder)
            r.sheets = v3._Sizes
            items = r.saved_items(folder, 1)
            plain = r.plan_saved(folder, 1, items[0].id, pose="walk")
            self.assertNotIn("item", [d.what for d in plain])
            for item, litter in ((3, 1), (3, 2), (v3.COLLECTABLE_FIRST + 4, 3)):
                carried = r.plan_saved(folder, 1, items[0].id, pose="walk", item=item, litter=litter)
                spec = {"subject": "villager", "sex": "male", "stage": 900, "head": 0, "body": 29,
                        "pose": "walk", "item": item, "litter": litter}
                custom_plan = r.plan_custom(spec)
                self.assertEqual([d.key() for d in carried if d.what == "item"],
                                 [d.key() for d in custom_plan if d.what == "item"])
                self.assertEqual(len([d for d in carried if d.what == "item"]), litter)

    def test_masks_from_the_companions_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.make(folder)
            people = common.read_save(folder, 3, 1)[1]
            values = bytearray(256)
            ids = [0] * 256
            values[5], ids[5] = 4, people[1].ident             # Lani: Purple, by identity, at any entry
            place = folder / "Virtual Villagers Fun Patcher" / "Save 1" / "Data" / "Village Masks"
            place.mkdir(parents=True)
            (place / "Village Masks - Save 1.dat").write_bytes(b"MSK4" + bytes(values) + struct.pack("<256I", *ids))
            r = v3.load(pi.Pictures(3, None))
            r.sheets = v3._Sizes
            items = r.saved_items(folder, 1)
            self.assertIn("Purple Mask (patcher)", items[1].detail)
            plan = r.plan_saved(folder, 1, items[1].id)
            self.assertEqual(plan[-1].what, "mask")
            self.assertEqual(plan[-1].rect[1], 145 * 3)


@unittest.skipUnless((ART / "Images" / "male_heads.png").is_file(), "needs the game's art in research/game-images")
class Pictures(unittest.TestCase):
    def test_every_required_sheet_is_the_stock_size(self) -> None:
        source = pi.FolderSource(ART)
        for name in v3.required_files():
            data = source.read(name)
            self.assertIsNotNone(data, name)
            self.assertEqual(struct.unpack(">II", data[16:24]), v3.SIZES[name], name)

    def test_pictures_draw(self) -> None:
        r = v3.load(pi.Pictures(3, pi.FolderSource(ART), patcher=v3.patcher_art()))
        adult = r.render_custom({"sex": "male", "stage": 600, "head": 12, "body": 4, "mask": 5})
        child = r.render_custom({"sex": "female", "stage": 60, "head": 2, "body": 9, "pose": 8})
        self.assertIsNotNone(adult.bbox())
        self.assertIsNotNone(child.bbox())
        self.assertLess(child.bbox()[3] - child.bbox()[1], adult.bbox()[3] - adult.bbox()[1])


if __name__ == "__main__":
    unittest.main()
