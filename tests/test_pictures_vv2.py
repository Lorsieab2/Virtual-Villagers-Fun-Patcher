"""Picture Studio, The Lost Children: src/vv_pictures_vv2.py proven against the game's own code.

* THE COMPOSITOR.  The game's asset loader (0x44C232 .. 0x44C59F) builds every villager atlas with its own
  constructors in Unicorn on the stock executable (each picture a fake surface the size of the real
  sheet); then the village compositor 0x445B50 draws one record, and every blit it makes (the plain
  0x403F90 and the scaled 0x404000: sheet, cell rectangle, place, scale, surface alpha) is recorded.
  For thousands of records -- every state the compositor knows, each direction, frame and head column,
  both sexes, every child age, adults young and old, the head and body rows, bodies awaiting burial,
  statues, swimming, carried items and litters, selection, a villager held by the hand -- the renderer's
  plan must be those blits, in that order.
* THE MASKS.  The same on the executable the patcher builds with "Enable Origins-Exclusive Features and
  Heathen Masks": its .vvmk head stubs run, with the patch's mask atlas built by the game's own
  constructor and a mask in the patch's own table, and draw the masks the plan has.
* THE PRIMITIVES.  The atlas constructors, cell cut, place-scaled centring and blitter are A New Home's
  instruction for instruction (only addresses differ); the blitter is also run on real pixels.
* THE SAVE.  saved_items and plan_saved on a synthetic save (never the owner's).

The emulated checks need the stock executable (research/stock-executables), the game's pictures
(research/game-images, for their sizes) and Unicorn/pefile/capstone; without them they skip.
"""
from __future__ import annotations

import functools
import re
import struct
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_picture_image as pi  # noqa: E402
import vv_pictures_common as common  # noqa: E402
import vv_pictures_vv2 as v2  # noqa: E402

STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"
VV1_STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
IMAGES = ROOT / "research" / "game-images" / "Virtual Villagers - The Lost Children"

try:
    import pefile  # noqa: F401
    from unicorn.x86_const import UC_X86_REG_FPCW
    from story_emulator import API_STUBS, Process
    HAVE_UNICORN = True
except ImportError:
    HAVE_UNICORN = False

try:
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    HAVE_CAPSTONE = True
except ImportError:
    HAVE_CAPSTONE = False

HAVE_GAME = STOCK.is_file() and (IMAGES / "Images").is_dir()
EMULATE = HAVE_UNICORN and HAVE_GAME

GAME_SIZE = 0xE57600
X0, Y0 = 300, 280
INIT_START, INIT_END = 0x44C232, 0x44C59F
COMPOSITOR = 0x445B50
PLAIN_BLIT, SCALED_BLIT = 0x403F90, 0x404000


def _png_size(data: bytes) -> tuple[int, int]:
    return struct.unpack(">II", data[16:24])


class VillageEmulator:
    """The Lost Children's village compositor on one record, in Unicorn."""

    def __init__(self, exe: bytes) -> None:
        self.p = p = Process(exe)
        p.mu.mem_map(API_STUBS, 0x10000)
        p.api_names = {}
        slot = 0
        for entry in p._exe_pe.DIRECTORY_ENTRY_IMPORT:
            for imp in entry.imports:
                if not imp.name:
                    continue
                stub = API_STUBS + slot * 16
                slot += 1
                p.mu.mem_write(stub, b"\xC3")
                p.api_names[stub] = imp.name.decode()
                p.mu.mem_write(imp.address, struct.pack("<I", stub))
                p.api_handlers[imp.name.decode()] = lambda q: (0, 0)
        self.names: dict[int, str] = {}
        self.blits: list[tuple] = []
        self.terrain = 0
        self.timer = 0
        p.stub(0x467F83, lambda q: (q.alloc(max(4, q.arg(0))), 0))          # operator new
        p.stub(0x40A730, self._image)                                       # a picture by name
        p.stub(0x4031A0, lambda q: (max(0, q.arg(0) - 1) & 0xFFFFFFFF, 0))  # rand(n): never the rare branch
        p.stub(0x403200, lambda q: (self.timer, 0))                          # the clock
        p.stub(0x4181D0, lambda q: (self.terrain, 8))                        # the terrain at a point
        p.stub(0x4239D0, lambda q: (0, 0x1C))                                # particles
        p.stub(PLAIN_BLIT, self._plain)
        p.stub(SCALED_BLIT, self._scaled)
        self.game = p.alloc(GAME_SIZE)
        self._build_atlases()
        renderer = p.alloc(0x100)
        p.write(renderer + 0x60, struct.pack("<iiii", -100000, -100000, 100000, 100000))
        holder = p.alloc(4)
        p.put32(holder, renderer)
        p.put32(self.game + 0xE574D0, holder)
        self.camera = p.alloc(0x30500)
        p.put32(self.game + 0xE574D4, self.camera)
        p.put32(self.game + 0xE574D8, p.alloc(0x10))
        p.put32(self.game + 0xE574DC, p.alloc(0x10))
        for i in range(256):
            p.put32(self.game + 0xE57090 + 4 * i, i)

    # ---- the pictures: a fake surface the size of the real sheet
    def _image(self, q):
        name = q.cstring(q.arg(0))
        data = (IMAGES / "Images" / name).read_bytes() if name != v2.MASK_FILE else v2.mask_atlas_bytes()
        w, h = _png_size(data)
        surface = q.alloc(0x40)
        q.put32(surface + 8, w)
        q.put32(surface + 12, h)
        self.names[surface] = name
        this = q.reg("ecx")
        q.put32(this, surface)
        q.write(this + 4, b"\x01")
        return this, 4

    def _plain(self, q):
        surface, x, y, l, t, r, b = (q.arg(i) for i in range(7))
        self.blits.append((self.names[surface].casefold(), tuple(_s(v) for v in (l, t, r, b)), _s(x), _s(y), 1.0, 255))
        return 0, 0x1C

    def _scaled(self, q):
        surface, x, y, l, t, r, b, alpha, scale, _flag = (q.arg(i) for i in range(10))
        f = lambda v: struct.unpack("<f", struct.pack("<I", v))[0]   # noqa: E731
        self.blits.append((self.names[surface].casefold(), tuple(_s(v) for v in (l, t, r, b)), _s(x), _s(y), round(f(scale), 6),
                           pi.surface_alpha(f(alpha))))
        return 0, 0x28

    def _build_atlases(self) -> None:
        p = self.p
        p.set_reg("esi", self.game)
        p.set_reg("edi", 0)
        p.set_reg("esp", 0x0FF00000 - 0x8000)
        p.run(INIT_START, INIT_END, limit=5_000_000)

    def build_atlas(self, name: str, cols: int, rows: int) -> int:
        """An atlas built by the game's own single-sheet constructor 0x40A270."""
        obj = self.p.alloc(0x34)
        text = self.p.alloc(64)
        self.p.write(text, name.encode() + b"\0")
        self.p.call(0x40A270, [text, cols, rows], ecx=obj, limit=5_000_000)
        return obj

    # ---- one record
    def record(self, st: v2.State, index: int = 0) -> int:
        p = self.p
        rec = self.game + index * 0xE48C
        p.write(rec, bytes(0x5C0))
        p.put32(rec + 4, X0)
        p.put32(rec + 8, Y0)
        p.put32(rec + 0x20, st.frame)
        p.put32(rec + 0x24, st.height)
        p.write(rec + 0x30, bytes((1, 1 if st.selected else 0, 1 if st.held else 0)))
        p.put32(rec + 0x38, st.direction)
        p.put32(rec + 0x3C, st.facing)
        p.put32(rec + 0x40, 4 if st.hidden else st.state)
        p.put32(rec + 0x44, st.item)
        p.put32(rec + 0x52C, st.health)
        p.put32(rec + 0x530, st.age)
        p.put32(rec + 0x538, 1 if st.male else 2)
        p.put32(rec + 0x544, st.litter)
        p.put32(rec + 0x548, st.head)
        p.put32(rec + 0x54C, st.body)
        p.put32(rec + 0x550, st.variant)
        p.write(rec + 0x558, b"\x01" if st.statue else b"\x00")
        return rec

    def draw(self, st: v2.State) -> list[tuple]:
        self.record(st)
        self.terrain, self.timer = st.terrain, st.timer
        self.blits = []
        self.p.mu.reg_write(UC_X86_REG_FPCW, 0x027F)
        self.p.call(COMPOSITOR, [], ecx=self.game, limit=5_000_000)
        return self.blits


def _s(value: int) -> int:
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value & 0x80000000 else value


@functools.lru_cache(maxsize=None)
def _renderer() -> v2.Renderer:
    return v2.load(pi.FolderSource(IMAGES))


def _plan_keys(st: v2.State) -> list[tuple]:
    r = _renderer()
    return [d.key() for d in v2.plan(r.sheets, st, X0, Y0)]


def _states():
    """The records every check draws: each state's own pickers, both sexes, the life stages."""
    ages = (0, 40, 100, 199, 279, 280, 600, 1099, 1100, 2400)
    for male in (True, False):
        for age in ages:
            for state in (0, 1, 2, 3, 5, 6, 8, 9, 10):
                frames = range(8) if state in (0, 5, 9) else range(4)
                for frame in frames:
                    for direction in range(4):
                        if state not in (0, 5, 9, 2) and direction:
                            continue
                        yield v2.State(male=male, age=age, head=(age + frame) % 30, body=(age * 7 + frame) % 30,
                                       state=state, frame=frame, direction=direction,
                                       facing=(frame + direction) % 7, height=frame * 3, variant=frame)


@unittest.skipUnless(EMULATE, "the stock The Lost Children, its pictures and Unicorn are needed")
class CompositorMatchesTheGame(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.emu = VillageEmulator(STOCK.read_bytes())

    def check(self, st: v2.State, label: str = "") -> None:
        self.assertEqual(_plan_keys(st), self.emu.draw(st), label or repr(st))

    def test_every_state_direction_frame_and_age(self) -> None:
        n = 0
        for st in _states():
            self.check(st)
            n += 1
        self.assertGreater(n, 2000)

    def test_every_head_and_body_row(self) -> None:
        for male in (True, False):
            for age in (100, 600, 1500):
                for k in range(30):
                    self.check(v2.State(male=male, age=age, head=k, body=29 - k, facing=k % 7, frame=k % 8,
                                        direction=k % 4))

    def test_items_litters_shadows_and_held(self) -> None:
        for age in (60, 600, 1200):
            for state in (0, 1, 2, 3, 8, 9, 10):
                for item in (0, 5, 12, 13, 25, v2.NO_ITEM, 27, 30, 40, 80):
                    for litter in (0, 1, 3):
                        for direction in (0, 1, 2, 3):
                            for selected, held in ((False, False), (True, False), (False, True), (True, True)):
                                self.check(v2.State(male=age % 2 == 0, age=age, head=4, body=9, state=state,
                                                    frame=2, direction=direction, item=item, litter=litter,
                                                    selected=selected, held=held, variant=3))

    def test_swimming_and_water(self) -> None:
        for age in (100, 280, 900, 1100):
            for terrain in (0, 0x18, 0x19):
                for state in (0, 1, 9):
                    for timer in range(5):
                        for held in (False, True):
                            self.check(v2.State(age=age, head=7, body=3, state=state, terrain=terrain,
                                                timer=timer, held=held, facing=timer, variant=1))

    def test_bodies_statues_and_hidden(self) -> None:
        for variant in range(-9, 12):
            self.check(v2.State(health=0, variant=variant, age=500))
            self.check(v2.State(health=-5, variant=variant, age=100, selected=True))
            self.check(v2.State(statue=True, variant=variant))
            self.check(v2.State(statue=True, variant=variant, selected=True, health=0))
        self.check(v2.State(hidden=True))


def _patched_exe() -> bytes | None:
    import vv_fun_patcher as patcher
    build = {b.id: b for b in patcher.load_builds()}["vv2"]
    data, _applied = patcher.render_patched_bytes(STOCK, build, "immediate_fixed",
                                                  ["vv2_enable_origins_exclusive_features"])
    return bytes(data)


def _section_va(exe: bytes, name: bytes) -> int | None:
    import pefile
    pe = pefile.PE(data=exe)
    for s in pe.sections:
        if s.Name.rstrip(b"\0") == name:
            return pe.OPTIONAL_HEADER.ImageBase + s.VirtualAddress
    return None


@unittest.skipUnless(EMULATE and v2.ORIGINS_DLL.is_file(), "the stock game, its pictures, Unicorn and the patcher")
class MasksMatchThePatchedGame(unittest.TestCase):
    """The Origins patch's own head stubs, in the executable the patcher builds."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            exe = _patched_exe()
        except Exception as exc:  # noqa: BLE001 -- the patcher could not build it here
            raise unittest.SkipTest(f"the patched executable could not be built ({exc})")
        cls.table = _section_va(exe, b".mtab")
        if cls.table is None:
            raise unittest.SkipTest("the patched executable has no .mtab section")
        cls.emu = VillageEmulator(exe)
        atlas = cls.emu.build_atlas(v2.MASK_FILE, 8, 5)
        cls.emu.p.put32(cls.table + 0xF08, atlas)

    def check(self, st: v2.State) -> None:
        self.emu.p.write(self.table, bytes((st.mask,)))
        self.assertEqual(_plan_keys(st), self.emu.draw(st), repr(st))

    def test_the_hooks_are_the_patchs(self) -> None:
        data = self.emu.p.read(0x4095B0, 5)
        self.assertEqual(data[0], 0xE9, "the adult head thunk is not detoured")
        self.assertEqual(self.emu.p.read(0x409600, 1)[0], 0xE9, "the child head thunk is not detoured")

    def test_every_mask_on_every_stage_and_pose(self) -> None:
        n = 0
        for mask in range(6):
            for male in (True, False):
                for age in (40, 150, 279, 280, 700, 1100, 2000):
                    for state in (0, 1, 2, 3, 8, 9, 10):
                        for facing in (0, 3, 5, 6):
                            for same in (False, True):
                                head = 11
                                body = head if same else 4
                                self.check(v2.State(male=male, age=age, head=head, body=body, state=state,
                                                    frame=facing % 4, direction=facing % 4, facing=facing,
                                                    height=6, variant=1, mask=mask))
                                n += 1
                    self.check(v2.State(male=male, age=age, head=2, body=8, terrain=0x18, mask=mask, facing=4))
        self.assertGreater(n, 1000)

    def test_bodies_and_statues_wear_no_mask(self) -> None:
        for mask in (1, 5):
            self.check(v2.State(health=0, variant=2, mask=mask))
            self.check(v2.State(statue=True, variant=5, mask=mask))

    def test_a_record_outside_the_table_range_is_unmasked(self) -> None:
        # a table byte the stubs refuse (6 or more) draws no mask; the plan then has none either
        st = v2.State(age=600, head=3, body=3, mask=7)
        self.emu.p.write(self.table, bytes((7,)))
        game = self.emu.draw(st)
        self.assertEqual(game, _plan_keys(replace(st, mask=0)))


def _normalised(game: int, start: int, end: int) -> list[str]:
    import pefile
    exe = (STOCK if game == 2 else VV1_STOCK)
    pe = pefile.PE(str(exe))
    base, image = pe.OPTIONAL_HEADER.ImageBase, pe.get_memory_mapped_image()
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    out = []
    for ins in md.disasm(image[start - base:end - base], start):
        out.append(re.sub(r"0x4[0-9a-f]{5}", "ADDR", f"{ins.mnemonic} {ins.op_str}"))
    return out


@unittest.skipUnless(HAVE_CAPSTONE and HAVE_UNICORN and STOCK.is_file() and VV1_STOCK.is_file(),
                     "both stock executables and capstone are needed")
class PrimitivesAreANewHomes(unittest.TestCase):
    def test_same_instructions(self) -> None:
        for (a, a_end), (b, b_end), what in (
                ((0x407ED0, 0x4080A0), (0x408160, 0x408330), "place-scaled"),
                ((0x403D70, 0x405AD0), (0x404000, 0x405D60), "the blitter"),
                ((0x4086C0, 0x408740), (0x4088C0, 0x408940), "the cell draw"),
                ((0x409F90, 0x40A020), (0x40A190, 0x40A220), "the cell cut"),
                ((0x40A070, 0x40A0E6), (0x40A270, 0x40A2E6), "the one-sheet atlas"),
                ((0x40A0F0, 0x40A29C), (0x40A2F0, 0x40A49C), "the atlas of sheets")):
            self.assertEqual(_normalised(1, a, a_end), _normalised(2, b, b_end), what)


@unittest.skipUnless(HAVE_UNICORN and STOCK.is_file(), "the stock executable and Unicorn are needed")
class BlitterMatchesTheGame(unittest.TestCase):
    """The Lost Children's own blitter 0x404000 on real pixels against vv_picture_image's rules."""

    def test_scaled_down_and_faded(self) -> None:
        exe = STOCK.read_bytes()
        p = Process(exe)
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
                    p.api_handlers[imp.name.decode()] = lambda q: (0, 0)
        sw, sh = 160, 120

        def fmt(amask):
            f = p.alloc(0x40)
            p.put32(f, 0x16362004 if amask else 0x16161804)
            p.write(f + 8, bytes((32, 4)))
            for k, v in enumerate((0x00FF0000, 0x0000FF00, 0x000000FF, amask)):
                p.put32(f + 12 + 4 * k, v)
            p.write(f + 28, bytes((0, 0, 0, 0 if amask else 8, 16, 8, 0, 24 if amask else 0)))
            return f

        def surface(w, h, amask):
            s = p.alloc(0x40)
            px = p.alloc(w * h * 4 + 16)
            p.put32(s + 4, fmt(amask))
            p.put32(s + 8, w)
            p.put32(s + 12, h)
            p.put32(s + 16, w * 4)
            p.put32(s + 20, px)
            p.write(s + 36, struct.pack("<iiii", 0, 0, w, h))
            return s
        screen = surface(sw, sh, 0)
        gfx = p.alloc(0x100)
        p.put32(gfx + 0x30, screen)
        p.put32(gfx + 8, sw)
        p.put32(gfx + 0xC, sh)
        w, h = 88, 70
        rgba = b"".join(bytes(((x * 37 + y * 11) % 256, (x * 5 + y * 13) % 256, (x * y) % 256,
                               (0 if (x + y) % 7 == 0 else 255 if (x * y) % 3 else (x * 29 + y * 3) % 256)))
                        for y in range(h) for x in range(w))
        src = surface(w, h, 0xFF000000)
        argb = bytearray(len(rgba))
        argb[0::4], argb[1::4], argb[2::4], argb[3::4] = rgba[2::4], rgba[1::4], rgba[0::4], rgba[3::4]
        p.write(p.u32(src + 20), bytes(argb))
        sheet = pi.Image(w, h, rgba)
        bg = (10, 200, 30)
        f32bits = lambda v: struct.unpack("<I", struct.pack("<f", v))[0]   # noqa: E731
        for percent in (50, 57, 63, 70, 77, 80, 85, 90, 93, 97, 99):
            scale = pi.percent_scale(percent)
            for rect in ((0, 0, 40, 65), (40, 0, 80, 65), (3, 2, 43, 67)):
                p.write(p.u32(screen + 20), bytes((bg[2], bg[1], bg[0], 0)) * (sw * sh))
                p.mu.reg_write(UC_X86_REG_FPCW, 0x027F)
                p.call(SCALED_BLIT, [src, 20, 9, *rect, f32bits(1.0), f32bits(scale), 0], ecx=gfx)
                raw = p.read(p.u32(screen + 20), sw * sh * 4)
                got = [(raw[i + 2], raw[i + 1], raw[i]) for i in range(0, len(raw), 4)]
                piece = pi.blit_piece(sheet, rect, scale)
                want = [bg] * (sw * sh)
                for j in range(piece.height):
                    for i in range(piece.width):
                        r, g, b, a = piece.pixel(i, j)
                        if a:
                            d = want[(9 + j) * sw + 20 + i]
                            want[(9 + j) * sw + 20 + i] = tuple((s * a + dv * (255 - a) + 0x7F) >> 8
                                                                for s, dv in zip((r, g, b), d))
                self.assertEqual(got, want, f"scale {percent} rect {rect}")


class HeadLookInTheVillage(unittest.TestCase):
    """VVFP Head Look.dll's compares in The Lost Children's village compositor: only the swimming head's
    (0x4469BA); tests/test_head_look.py runs the DLL on it."""

    def test_only_the_swimming_compare_is_spliced(self) -> None:
        source = (ROOT / "native" / "vvfp_head_look" / "vvfp_head_look.c").read_text(encoding="utf-8")
        body = source[source.index("static const hl_site VV2_SITES[]"):]
        body = body[:body.index("};")]
        sites = [int(v, 16) for v in re.findall(r"0x([0-9A-F]{6})u", body)]
        village = [s for s in sites if v2.COMPOSITOR_START <= s <= v2.COMPOSITOR_END]
        self.assertEqual(village, [0x4469BA])

    def test_the_plan_follows_it(self) -> None:
        r = v2.load(_NullSource())
        st = v2.State(age=600, head=3, body=3, terrain=v2.DEEP_WATER)
        files = lambda s: [d.file for d in v2.plan(r.sheets, s) if d.what == "head"]   # noqa: E731
        self.assertEqual(files(replace(st, look=common.LOOK_OLD)), ["male_heads_old.png"])
        self.assertEqual(files(replace(st, look=common.LOOK_YOUNG, age=2000)), ["male_heads.png"])
        walking = replace(st, terrain=0, look=common.LOOK_OLD)
        self.assertEqual(files(walking), ["male_heads.png"])


class _NullSource:
    """Sizes only: every sheet a blank PNG of the real sheet's size (no game art)."""
    SIZES = {"male_heads.png": (280, 1950), "female_heads.png": (280, 1950), "male_heads_old.png": (280, 1950),
             "female_heads_old.png": (280, 1950), "totems.png": (320, 100), "peep_shadow1.png": (68, 64),
             "focus_circle.png": (68, 64), "carrying.png": (520, 50), "collectables_images.png": (240, 360),
             "skelly.png": (240, 65), "ripple.png": (260, 65), v2.MASK_FILE: (520, 725)}
    problem = ""

    def read(self, name: str) -> bytes | None:
        size = self.SIZES.get(name)
        if size is None:
            if "bodies" in name:
                size = (640, 650)
            elif "actions" in name:
                size = (360, 650)
            else:
                return None
        return pi.Image(*size).to_png()


class PlansWithoutTheGame(unittest.TestCase):
    """What can be checked with no game art (as on CI)."""

    def setUp(self) -> None:
        self.r = v2.load(_NullSource())

    def test_required_files_are_the_atlases(self) -> None:
        files = v2.required_files()
        for name in ("male_heads.png", "female_heads_old.png", "male_bodies00.png", "male_bodies12.png",
                     "female_actions02.png", "totems.png", "skelly.png", "carrying.png"):
            self.assertIn(name, files)
        self.assertEqual(len(files), len(set(files)))

    def test_the_mask_atlas_is_the_patchs(self) -> None:
        data = v2.mask_atlas_bytes()
        if data is None:
            self.skipTest("the Origins DLL is not in assets")
        self.assertEqual(_png_size(data), (520, 725))
        native = ROOT / "native" / "vv2_origins_icons" / "heathen_masks.png"
        if native.is_file():
            self.assertEqual(data, native.read_bytes())

    def test_child_scales(self) -> None:
        self.assertEqual([v2.child_body_scale(a) for a in (0, 40, 279)], [50, 55, 89])
        self.assertEqual([v2.child_head_scale(a) for a in (0, 40, 279)], [80, 82, 99])

    def test_stages_and_custom(self) -> None:
        subjects = self.r.custom_choices()
        self.assertEqual([s.key for s in subjects], ["villager", "statue"])
        fields = {f.key: f for f in subjects[0].fields}
        self.assertEqual(len(fields["head"].options), 30)
        self.assertEqual(len(fields["body"].options), 30)
        self.assertEqual([o.key for o in fields["mask"].options], [0, 1, 2, 3, 4, 5])
        for stage in fields["stage"].options:
            for pose in fields["pose"].options:
                spec = {"subject": "villager", "sex": False, "stage": stage.key, "head": 29, "body": 29,
                        "mask": 5, "pose": pose.key, "frame": 7, "direction": 3, "facing": 6}
                self.assertTrue(self.r.plan_custom(spec), (stage.key, pose.key))
        statue = self.r.plan_custom({"subject": "statue", "kind": 7, "shadow": "none"})
        self.assertEqual([d.what for d in statue], ["statue"])

    def test_no_shadow_option(self) -> None:
        spec = {"subject": "villager", "stage": ("adult", 600), "shadow": "none"}
        self.assertNotIn("shadow", [d.what for d in self.r.plan_custom(spec)])
        spec["shadow"] = "selected"
        self.assertEqual([d.what for d in self.r.plan_custom(spec)][:2], ["shadow", "selection circle"])

    def test_unknown_pose_is_a_plain_error(self) -> None:
        with self.assertRaises(pi.PictureError):
            self.r.plan_custom({"subject": "villager", "pose": "fly"})


def _entry(name: str, *, male: bool, age: int, head: int, body: int, health: int = 100,
           statue: bool = False, variant: int = 0, litter: int = 0) -> bytes:
    """One saved villager entry of The Lost Children (record +0x524 .. +0x804; the name at +0x40)."""
    e = bytearray(0x2E0)
    at = 0x40
    e[at:at + len(name)] = name.encode()
    for off, value in ((-0x38, health), (-0x34, age), (-0x2C, 1 if male else 2), (-0x20, litter),
                       (-0x1C, head), (-0x18, body), (-0x14, variant)):
        struct.pack_into("<i", e, at + off, value)
    e[at - 0x0C] = 1 if statue else 0
    e[at + 0x29C] = 1
    return bytes(e)


class SyntheticSave(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        body = b"".join([
            _entry("Kaimana", male=True, age=900, head=12, body=4),
            _entry("Leilani", male=False, age=120, head=3, body=22),
            _entry("Makoa", male=True, age=1500, head=20, body=9),
            _entry("Noelani", male=False, age=700, head=1, body=1, health=0, variant=6),
            _entry("Palila", male=True, age=1800, head=5, body=5, statue=True, variant=3, health=0),
        ])
        data = b"ldwg" + bytes(0x200) + body + bytes(0x2E0)
        (self.folder / "Virtual Villagers - The Lost Children1.ldw").write_bytes(data)
        self.r = v2.load(_NullSource())

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_items(self) -> None:
        items = self.r.saved_items(self.folder, 1)
        self.assertEqual([(i.label, i.location, i.kind) for i in items], [
            ("Kaimana (adult, 45 years)", "Villagers", "villager"),
            ("Leilani (child, 6 years)", "Villagers", "villager"),
            ("Makoa (elder, 75 years)", "Villagers", "villager"),
            ("Noelani (body, 35 years)", "Bodies awaiting burial", "body"),
            ("Palila (statue)", "Esteemed Elder statues", "statue"),
        ])
        self.assertIn("head 12, body 4", items[0].detail)

    def test_plans_follow_the_save(self) -> None:
        ids = {i.label.split(" ")[0]: i.id for i in self.r.saved_items(self.folder, 1)}
        child = self.r.plan_saved(self.folder, 1, ids["Leilani"], pose="walk")
        self.assertEqual([d.what for d in child], ["shadow", "body", "head"])
        self.assertTrue(child[1].file.startswith("female_bodies"))
        self.assertAlmostEqual(child[1].scale, pi.percent_scale(v2.child_body_scale(120)))
        elder = self.r.plan_saved(self.folder, 1, ids["Makoa"], pose="walk")
        self.assertEqual(elder[-1].file, "male_heads_old.png")
        body = self.r.plan_saved(self.folder, 1, ids["Noelani"])
        self.assertEqual([(d.what, d.file, d.rect) for d in body], [("skeleton", "skelly.png", (120, 0, 180, 65))])
        statue = self.r.plan_saved(self.folder, 1, ids["Palila"])
        self.assertEqual([d.what for d in statue], ["statue shadow", "statue"])
        self.assertEqual(statue[-1].rect, (120, 0, 160, 100))
        self.assertEqual([(d.x, d.y) for d in statue], [(-0x11, 0x3B), (0, 0)])
        image = self.r.render_saved(self.folder, 1, ids["Kaimana"], pose="sit")
        self.assertGreater(image.width, 30)

    def test_the_elder_totems_patchs_statues(self) -> None:
        """native/vvfp_vv2_totems: the store's file (version 2: header, roster rows, entries, FNV-1a)."""
        body, h, path = self._store([("Kaimana", 12, 4, 1), ("Leilani", 3, 22, 2), ("Makoa", 20, 9, 1)])
        r = v2.load(_NullSource())
        items = [i for i in r.saved_items(self.folder, 1) if i.id.startswith("t")]
        self.assertEqual([i.label for i in items], ["Hoku's totem (statue)", "Lani's totem (statue)"])
        plan = r.plan_saved(self.folder, 1, items[0].id)
        self.assertEqual([(d.what, d.rect) for d in plan], [("statue shadow", (0, 0, 68, 64)),
                                                            ("statue", (200, 0, 240, 100))])
        path.write_bytes(body + struct.pack("<I", h ^ 1))           # a damaged file is not read
        self.assertFalse([i for i in v2.load(_NullSource()).saved_items(self.folder, 1) if i.id.startswith("t")])

    def _store(self, roster) -> tuple[bytes, int, Path]:
        """An ElderTotems.dat (version 2: header, the village's name, roster rows, entries, FNV-1a) holding
        two statues, for the village whose living villagers are `roster` (name, head, body, sex)."""
        entries = [_entry("Hoku", male=True, age=1900, head=2, body=6, statue=True, variant=13, health=0)[:0x2E0],
                   _entry("Lani", male=False, age=1500, head=9, body=1, statue=True, variant=4, health=0)[:0x2E0]]
        header = bytearray(72)
        header[:16] = v2.TOTEMS_MAGIC
        struct.pack_into("<iiiiii", header, 16, 2, 2, 1, 0x2E0, len(roster), len(entries))
        rows = b"".join(name.encode().ljust(24, b"\0") + struct.pack("<iii", head, body, sex)
                        for name, head, body, sex in roster)
        body = bytes(header) + rows + b"".join(entries)
        h = common.FNV_BASIS
        for b in body:
            h = ((h ^ b) * common.FNV_PRIME) & 0xFFFFFFFF
        path = v2.totems_file(self.folder, 1)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body + struct.pack("<I", h))
        return body, h, path

    def test_another_villages_totems_are_not_listed(self) -> None:
        """Codex (PR #660): a slot whose village was replaced can still hold the old village's
        ElderTotems.dat, whole and checked.  The game's companion loads a store only when it is bound to
        the save (bound_to: more than half of its roster stands in the save); Picture Studio uses the same
        test (vv_vv2_totem_store.bound), so the old village's statues are not listed."""
        self._store([("Ahiga", 1, 2, 1), ("Bena", 3, 4, 2), ("Kaimana", 12, 4, 1)])   # one of three here
        items = v2.load(_NullSource()).saved_items(self.folder, 1)
        self.assertFalse([i for i in items if i.id.startswith("t")])
        self.assertEqual(len(items), 5)                                       # the save's own records stay
        self._store([("Ahiga", 1, 2, 1), ("Leilani", 3, 22, 2), ("Kaimana", 12, 4, 1)])   # two of three
        self.assertEqual(len([i for i in v2.load(_NullSource()).saved_items(self.folder, 1)
                              if i.id.startswith("t")]), 2)

    def test_the_store_is_read_by_the_repair_tools_reader(self) -> None:
        source = (ROOT / "src" / "vv_pictures_vv2.py").read_text(encoding="utf-8")
        self.assertIn("store_file.bound(store, data)", source)
        self.assertIn("store_file.read(Path(folder), int(slot))", source)

    def test_nothing_is_written(self) -> None:
        before = sorted(p.name for p in self.folder.rglob("*"))
        self.r.saved_items(self.folder, 1)
        self.assertEqual(before, sorted(p.name for p in self.folder.rglob("*")))


@unittest.skipUnless((IMAGES / "Images").is_dir(), "the game's pictures (research/game-images) are needed")
class WithTheGamesPictures(unittest.TestCase):
    def test_every_required_file_is_in_the_game(self) -> None:
        for name in v2.required_files():
            self.assertTrue((IMAGES / "Images" / name).is_file(), name)

    def test_pixels(self) -> None:
        r = _renderer()
        image = r.render_custom({"subject": "villager", "sex": True, "stage": ("adult", 600), "head": 6,
                                 "body": 12, "mask": 3, "pose": "walk", "frame": 2, "facing": 5})
        box = image.bbox()
        self.assertIsNotNone(box)
        self.assertGreater(box[3] - box[1], 60)
        small = r.render_custom({"subject": "villager", "stage": ("child", 40), "shadow": "none"})
        big = r.render_custom({"subject": "villager", "stage": ("adult", 600), "shadow": "none"})
        self.assertLess(small.cropped(0).height, big.cropped(0).height)


if __name__ == "__main__":
    unittest.main()
