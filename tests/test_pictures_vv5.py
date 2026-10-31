"""Picture Studio, New Believers: the drawing rules in src/vv_pictures_vv5.py, proven against the game's own code.

* The table: the game's loader 0x451180 is run in Unicorn on the stock executable, reading the game's own
  Assets\\animpts.dat, and the table it leaves at 0x5258B8 must be the one vv_pictures_vv5.AnimTable reads
  (every animation record, head record and heathen mask offset the draw uses).
* The village draw: the game's 0x4720E0 draws one villager record (the manager 0x554148 set up by the
  game's own sprite set-up 0x46F870 and camera 0x44F0F0, zoom 1.0 as the village scene sets it at 0x442C37),
  for well over a thousand states -- every pose 0-48 in every direction, head turns, sexes, child ages and
  adults, the old head, heathens of every colour and rank, the dead, carried items and a mother's
  litter, swimming -- down to the engine's software blitter 0x404C40; every blit (sheet, cell, place, surface
  alpha, scale) must be the renderer's plan.
* The blitter: the game's 0x404C40 run on real pixels (scaled down, and with a surface alpha) must give what
  vv_picture_image.blit_piece and the alpha rule give.
* The patcher's cosmetic mask: a Believer with one must be drawn as the builder's mask_flip makes the game
  draw it (scripts/build_vv5_task9_native_actions.py), checked against that source and the emulated game.

The emulated checks need the stock executable (research/stock-executables), Unicorn and pefile, and the
game's pictures and Assets\\animpts.dat copied into research/game-images (never committed); they skip
without them, as on CI.  Nothing reads the owner's saves.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_picture_image as pi  # noqa: E402
import vv_pictures_common as common  # noqa: E402
import vv_pictures_vv5 as v5  # noqa: E402

EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
GAME = ROOT / "research" / "game-images" / "Virtual Villagers - New Believers"
ANIMPTS = GAME / "Assets" / "animpts.dat"

try:
    import pefile  # noqa: F401
    from unicorn import UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_FPCW

    from story_emulator import API_STUBS, Process
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - CI has no Unicorn
    HAVE_EMULATOR = False

HAVE_GAME = EXE.is_file() and ANIMPTS.is_file() and (GAME / "Images" / "male_heads00.png").is_file()
EMULATED = HAVE_EMULATOR and HAVE_GAME
WHY = "the stock New Believers executable, its pictures and Assets (research/), Unicorn and pefile are needed"

MGR, TABLE, RENDERER = 0x554148, 0x5258B8, 0x521078
NEW, FREE, SPRINTF = 0x47BBDC, 0x47BAFB, 0x47C046
FOPEN, FREAD, FCLOSE, RESOURCES = 0x47D1AC, 0x47D567, 0x47D06C, 0x402F60
BLITTER = 0x404C40


def _f(v: float) -> int:
    return struct.unpack("<I", struct.pack("<f", v))[0]


def _u2f(u: int) -> float:
    return struct.unpack("<f", struct.pack("<I", u & 0xFFFFFFFF))[0]


def _s32(u: int) -> int:
    u &= 0xFFFFFFFF
    return u - (1 << 32) if u & 0x80000000 else u


class Game:
    """New Believers in Unicorn: the stock executable, its imports bound to stubs, the C runtime's new,
    sprintf and stdio answered from Python (files from research/game-images), IMG_Load answered with an
    SDL_Surface of the picture's real size, the x87 at Windows' 53-bit precision (control word 0x027F)."""

    def __init__(self) -> None:
        self.p = Process(EXE.read_bytes())
        p = self.p
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
        p.stub(NEW, lambda q: (q.alloc(max(16, q.arg(0))), 0))
        p.stub(FREE, lambda q: (0, 0))
        p.stub(SPRINTF, self._sprintf)
        self.handles: dict[int, list] = {}
        p.stub(FOPEN, self._fopen)
        p.stub(FREAD, self._fread)
        p.stub(FCLOSE, lambda q: (0, 0))
        # The resource manager 0x402F60: its vtable +0 and +8 turn a name into a path (one argument each).
        obj, table, fn = p.alloc(0x40), p.alloc(0x40), API_STUBS + 0x8000
        p.put32(obj, table)
        for k, slot_at in enumerate((0, 8)):
            p.mu.mem_write(fn + 16 * k, b"\xC3")
            p.put32(table + slot_at, fn + 16 * k)
            p.stub(fn + 16 * k, lambda q: (q.arg(0), 4))
        p.stub(RESOURCES, lambda q: (obj, 0))
        self.surfaces: dict[int, str] = {}
        h = p.api_handlers
        h["IMG_Load"] = self._img_load
        h["SDL_AllocFormat"] = lambda q: (q.alloc(0x40), 0)
        h["SDL_ConvertSurface"] = lambda q: (q.arg(0), 0)
        for name in ("SDL_FreeFormat", "SDL_FreeSurface", "SDL_LockSurface", "SDL_UnlockSurface"):
            h[name] = lambda q: (0, 0)
        p.mu.reg_write(UC_X86_REG_FPCW, 0x027F)

    def _sprintf(self, q):
        fmt, out, k, i = q.cstring(q.arg(1)), [], 2, 0
        while i < len(fmt):
            if fmt[i] == "%":
                v = q.arg(k)
                k += 1
                out.append(q.cstring(v) if fmt[i + 1] == "s" else str(_s32(v)))
                i += 2
            else:
                out.append(fmt[i])
                i += 1
        text = "".join(out).encode("latin-1") + b"\0"
        q.write(q.arg(0), text)
        return len(text) - 1, 0

    def _fopen(self, q):
        path = GAME / "Assets" / Path(q.cstring(q.arg(0))).name
        if not path.is_file():
            return 0, 0
        handle = 0x7000 + 4 * len(self.handles)
        self.handles[handle] = [path.read_bytes(), 0]
        return handle, 0

    def _fread(self, q):
        buf, size, count, handle = q.arg(0), q.arg(1), q.arg(2), q.arg(3)
        data, at = self.handles[handle]
        chunk = data[at:at + size * count]
        q.write(buf, chunk)
        self.handles[handle][1] += len(chunk)
        return len(chunk) // max(1, size), 0

    def surface(self, w: int, h: int, pixels: int = 0, alpha: bool = True) -> int:
        p = self.p
        fmt = p.alloc(0x40)
        p.put32(fmt, 0x16362004 if alpha else 0x16161804)
        p.write(fmt + 8, bytes((32, 4)))
        p.put32(fmt + 12, 0x00FF0000)
        p.put32(fmt + 16, 0x0000FF00)
        p.put32(fmt + 20, 0x000000FF)
        p.put32(fmt + 24, 0xFF000000 if alpha else 0)
        p.write(fmt + 28, bytes((0, 0, 0, 0 if alpha else 8, 16, 8, 0, 24 if alpha else 0)))
        s = p.alloc(0x40)
        p.put32(s + 4, fmt)
        p.put32(s + 8, w)
        p.put32(s + 12, h)
        p.put32(s + 16, w * 4)
        p.put32(s + 20, pixels)
        p.write(s + 36, struct.pack("<iiii", 0, 0, w, h))
        return s

    def _img_load(self, q):
        path = GAME / "Images" / Path(q.cstring(q.arg(0)).replace("\\", "/")).name
        w, h = struct.unpack(">II", path.read_bytes()[16:24])
        s = self.surface(w, h)
        self.surfaces[s] = path.name
        return s, 0


class Village(Game):
    """The village draw 0x4720E0 on one record, every blit recorded at the blitter 0x404C40."""

    def __init__(self) -> None:
        super().__init__()
        p = self.p
        p.call(0x46F870, ecx=MGR)                    # the manager's sprites
        p.call(0x451180, ecx=TABLE)                  # the animation table, from Assets\animpts.dat
        p.call(0x44F0F0, [0, 0, _f(1.0)], ecx=RENDERER)   # the village camera (0x442C37): zoom 1.0
        renderer, wrapper = p.alloc(0x100), p.alloc(0x10)
        p.put32(wrapper, renderer)
        p.put32(0x4DB0E8, wrapper)                   # 0x4080C0's renderer
        p.write(renderer + 0x60, struct.pack("<iiii", 0, 0, 4000, 4000))   # its clip
        p.put32(MGR + 0x3C, wrapper)                 # the manager's constructor 0x46F80A
        p.write(MGR + 0x1BB518, struct.pack("<f", 1.0))                    # 0x46F84A
        p.put32(MGR + 0x1BB220, 0xFFFFFFFF)          # 0x46F85A: nobody hovered
        self.water = False
        self.rand = 0
        p.stub(0x4653D0, lambda q: (0, 0))           # not the selected villager
        p.stub(0x47AD80, lambda q: (1 if self.water else 0, 8))
        p.stub(0x477820, lambda q: (5 if self.water else 0, 8))
        p.stub(0x403660, lambda q: (self.rand, 0))   # rand(n)
        p.stub(0x4036E0, lambda q: (self.rand, 0))   # the ripple's random frame
        p.stub(0x425950, lambda q: (MGR, 0))
        p.stub(0x41EDE0, lambda q: (1, 0))           # no bubbles (a particle effect, not the villager)
        p.stub(BLITTER, self._blit)
        self.blits: list[tuple] = []

    def _blit(self, q):
        rect = tuple(_s32(q.arg(k)) for k in range(3, 7))
        self.blits.append((self.surfaces[q.arg(0)].casefold(), rect, _s32(q.arg(1)), _s32(q.arg(2)),
                           round(_u2f(q.arg(8)), 6), pi.surface_alpha(_u2f(q.arg(7)))))
        return 0, 0x28

    def draw(self, look: v5.Look, pose: v5.Pose) -> list[tuple]:
        p = self.p
        look = v5.effective(look)
        r = MGR + 0x48
        p.write(r, bytes(0x2F44))
        for off, value in ((0x1C40, look.health), (0x1B8C, look.age), (0x1B90, 0 if look.male else 1),
                           (0x1BB8, look.head), (0x1BBC, look.body), (0x1C98, 1000), (0x1C9C, 1000),
                           (0x1CB4, pose.pose), (0x1D00, pose.direction), (0x1D04, pose.turn), (0x1CC8, 1),
                           (0x1CFC, look.rank), (0x1B94, look.skeleton), (0x1D0C, pose.item),
                           (0x1C50, pose.litter)):
            p.put32(r + off, value)
        p.write(r + 0x1CCC, struct.pack("<ff", 1.0, 1.0))     # +0x1CCC scale, +0x1CD0 alpha (0x4651B0)
        p.write(r + 0x1CEC, bytes((look.faction, look.orange, look.red)))
        self.water = pose.swimming
        self.rand = pose.ripple
        self.blits = []
        p.call(0x4720E0, [0, _f(1.0)], ecx=MGR)
        return self.blits


def plan_keys(renderer, look: v5.Look, pose: v5.Pose) -> list[tuple]:
    pose.x, pose.y = 1000, 1000
    return [d.key() for d in renderer.planner.plan(look, pose)]


def _cases():
    out = []
    for age in (0, 1, 20, 99, 100, 140, 200, 260, 279, 280, 281, 600, 1099, 1100, 1500):
        for male in (True, False):
            out.append((v5.Look(male=male, age=age, head=(age // 20) % 30, body=(age // 7) % 30), v5.Pose()))
    for pose in range(49):
        for direction in range(4):
            for turn in (0, 3, 5, 7):
                out.append((v5.Look(head=pose % 30, body=(pose * 3 + direction) % 30, age=150 + pose,
                                    male=direction % 2 == 0), v5.Pose(pose=pose, direction=direction, turn=turn)))
    for head in range(30):
        out.append((v5.Look(head=head, body=29 - head, age=700, male=head % 2 == 0), v5.Pose(turn=head % 8)))
    for body in range(30):
        for pose in (0, 13, 32, 40, 41, 48):
            out.append((v5.Look(head=body, body=body, age=320, male=body % 2 == 1), v5.Pose(pose=pose)))
    for rank, orange, red in ((0, 0, 0), (0, 1, 0), (0, 0, 1), (12, 0, 0), (13, 0, 0), (14, 0, 0), (15, 0, 0),
                              (16, 0, 0), (13, 1, 0)):
        for turn in range(8):
            for age in (100, 600, 1200):
                out.append((v5.Look(faction=1, rank=rank, orange=orange, red=red, age=age, head=7, body=9,
                                    male=turn % 2 == 0), v5.Pose(turn=turn, direction=turn % 4)))
    for skeleton in (0, 1, 2, 3, 7, 1234, -1, -6):
        out.append((v5.Look(health=0, skeleton=skeleton, age=100 * abs(skeleton % 13)), v5.Pose()))
        out.append((v5.Look(health=-5, skeleton=skeleton, age=900), v5.Pose()))
    for item in (0, 5, 46, 79, 0x50, 0x55, 0x85):
        for litter in (1, 2, 3):
            for direction in range(4):
                out.append((v5.Look(age=200 + item), v5.Pose(item=item, litter=litter, direction=direction)))
    for turn in range(8):
        for ripple in range(4):
            out.append((v5.Look(age=300 + 40 * turn, faction=turn % 2), v5.Pose(swimming=True, turn=turn,
                                                                            ripple=ripple)))
    for pose in (0x28, 0x29):
        for swim in (False, True):
            out.append((v5.Look(age=900), v5.Pose(pose=pose, swimming=swim)))
    return out


@unittest.skipUnless(EMULATED, WHY)
class VillageDrawMatchesTheGame(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.game = Village()
        cls.renderer = v5.load(pi.FolderSource(GAME))

    def test_the_renderer_has_the_art(self) -> None:
        self.assertEqual(self.renderer.problem, "")

    def test_table_is_the_loaders(self) -> None:
        mem = self.game.p
        t = self.renderer.table

        def entry(at: int) -> v5.Entry:
            return v5._entry(mem.read(at, v5.RECORD), 0)
        for n in range(v5.ANIMS):
            for k in range(4):
                self.assertEqual(t.anims[n][k], entry(TABLE + 0x7258 + n * v5.ANIM + k * v5.RECORD), (n, k))
        for sex in range(2):
            for turn in range(v5.TURNS):
                self.assertEqual(t.heads[sex][turn], entry(TABLE + 0x1F05C + (sex * 11 + turn) * v5.RECORD),
                                 (sex, turn))
        for turn in range(8):
            self.assertEqual(struct.unpack("<ii", mem.read(TABLE + 0x21A4C + turn * 0x58, 8)), (0x101, turn))
            for colour in range(5):
                at = TABLE + 0x21A7C + (turn * 11 + colour) * 8
                self.assertEqual(t.masks[turn][colour], struct.unpack("<ii", mem.read(at, 8)), (turn, colour))

    def test_every_state_is_drawn_as_the_game_draws_it(self) -> None:
        cases = _cases()
        self.assertGreater(len(cases), 1000)
        for look, pose in cases:
            with self.subTest(look=look, pose=pose):
                self.assertEqual(plan_keys(self.renderer, look, pose), self.game.draw(look, pose))

    def test_head_look_only_moves_the_age_compare(self) -> None:
        """VVFP Head Look.dll changes only the compare at 0x4722A2: Old at 30 is the game at 1,100, Young at
        60 is the game at 1,099 (the scale is a grown-up's either way)."""
        for male in (True, False):
            for turn in range(8):
                old = plan_keys(self.renderer, v5.Look(male=male, age=600, head=9, old=True), v5.Pose(turn=turn))
                self.assertEqual(old, self.game.draw(v5.Look(male=male, age=1100, head=9), v5.Pose(turn=turn)))
                young = plan_keys(self.renderer, v5.Look(male=male, age=1200, head=9, old=False), v5.Pose(turn=turn))
                self.assertEqual(young, self.game.draw(v5.Look(male=male, age=1099, head=9), v5.Pose(turn=turn)))

    def test_cosmetic_masks_are_the_flip(self) -> None:
        """A Believer's Origins mask is the game's heathen draw with mask_flip's fields."""
        for cosmetic in range(1, 6):
            for turn in range(8):
                look = v5.Look(cosmetic=cosmetic, age=500, head=3, body=4, male=turn % 2 == 0)
                pose = v5.Pose(turn=turn)
                plan = plan_keys(self.renderer, look, pose)
                self.assertEqual(plan, self.game.draw(look, pose))
                self.assertIn("vv5_heathenheads.png", [k[0] for k in plan])


@unittest.skipUnless(EMULATED, WHY)
class BlitterMatchesTheGame(unittest.TestCase):
    """0x404C40 on real pixels: a test picture blitted scaled and faded onto an opaque screen."""

    @staticmethod
    def pattern(w: int, h: int) -> bytes:
        return b"".join(bytes(((x * 37 + y * 11) % 256, (x * 5 + y * 13) % 256, (x * y) % 256,
                               (0 if (x + y) % 7 == 0 else 255 if (x * y) % 3 else (x * 29 + y * 3) % 256)))
                        for y in range(h) for x in range(w))

    def test_scaled_and_faded_pixels(self) -> None:
        game = Game()
        p = game.p
        sw, sh = 160, 120
        screen = game.surface(sw, sh, p.alloc(sw * sh * 4), alpha=False)
        gfx = p.alloc(0x100)
        p.put32(gfx + 0x30, screen)
        p.put32(gfx + 8, sw)
        p.put32(gfx + 0xC, sh)
        w, h = 88, 70
        rgba = self.pattern(w, h)
        argb = bytearray(len(rgba))
        argb[0::4], argb[1::4], argb[2::4], argb[3::4] = rgba[2::4], rgba[1::4], rgba[0::4], rgba[3::4]
        source = game.surface(w, h, p.alloc(w * h * 4))
        p.write(p.u32(source + 20), bytes(argb))
        sheet = pi.Image(w, h, rgba)
        background = (10, 200, 30)
        for percent in (50, 57, 64, 70, 78, 87, 93, 99, 100):
            scale = pi.f32(percent / 100.0)
            for rect in ((0, 0, 40, 65), (40, 0, 80, 65), (3, 2, 43, 67)):
                for alpha in ((1.0, 0.4, 0.5) if percent < 100 else (0.4, 0.5)):
                    with self.subTest(percent=percent, rect=rect, alpha=alpha):
                        p.write(p.u32(screen + 20), bytes((background[2], background[1], background[0], 0)) * (sw * sh))
                        p.call(BLITTER, [source, 20, 9, *rect, _f(alpha), _f(scale), 0], ecx=gfx)
                        raw = p.read(p.u32(screen + 20), sw * sh * 4)
                        got = [(raw[i + 2], raw[i + 1], raw[i]) for i in range(0, len(raw), 4)]
                        self.assertEqual(got, self.screen(pi.blit_piece(sheet, rect, scale), 20, 9, background,
                                                          pi.surface_alpha(alpha), sw, sh, percent == 100))

    @staticmethod
    def screen(image: pi.Image, x: int, y: int, background, alpha: int, sw: int, sh: int,
               clear_too: bool = False) -> list:
        """The screen the rules give.  Unscaled and faded, the blitter also blends a clear pixel (its alpha
        weighted to 0), which darkens the screen under it by at most one step -- nothing a transparent PNG
        can show; scaled, it skips a box whose average alpha is 0."""
        out = [background] * (sw * sh)
        for j in range(image.height):
            for i in range(image.width):
                px, py = x + i, y + j
                r, g, b, a = image.pixel(i, j)
                if not (0 <= px < sw and 0 <= py < sh) or (a == 0 and not clear_too):
                    continue
                if alpha < 255:
                    a = (a * alpha + 127) >> 8
                d = out[py * sw + px]
                out[py * sw + px] = tuple((s * a + dv * (255 - a) + 0x7F) >> 8 for s, dv in zip((r, g, b), d))
        return out


@unittest.skipUnless(EXE.is_file(), "the stock New Believers executable is needed")
class ExecutableFacts(unittest.TestCase):
    """What the renderer copies from the executable, read straight from it."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.exe = EXE.read_bytes()
        try:
            import pefile as pe_module
        except ImportError:  # pragma: no cover
            raise unittest.SkipTest("pefile is needed")
        pe = pe_module.PE(data=cls.exe)
        cls.image = pe.get_memory_mapped_image()
        cls.base = pe.OPTIONAL_HEADER.ImageBase

    def dword(self, va: int) -> int:
        return struct.unpack_from("<I", self.image, va - self.base)[0]

    def text(self, va: int) -> str:
        at = va - self.base
        return self.image[at:self.image.index(b"\0", at)].decode("latin-1")

    def test_sprite_descriptors(self) -> None:
        """The descriptor table 0x4D1A1C..: the id is the dword before each name, then columns, rows, the
        suffix and the sheets across and down."""
        found = {}
        at = 0x4CEFBC
        while True:
            name_va = self.dword(at)
            if not 0x400000 < name_va < 0x500000:
                break
            ident = self.dword(at - 4)
            cols, rows, suffix, across, down = struct.unpack_from("<iiIii", self.image, at + 4 - self.base)
            found[ident] = (self.text(name_va), cols, rows, (across or 1, down or 1) if suffix else (1, 1))
            at += 0x30
        for ident, atlas in v5.SPRITES.items():
            self.assertEqual(found[ident], (atlas.name, atlas.cols, atlas.rows, tuple(atlas.sheets)), hex(ident))
        self.assertEqual(found[0x102][0], v5.SHADOW)

    def test_saved_heathen_fields(self) -> None:
        """The save writer 0x465270 puts +0x1CEC/D/E at entry +1/+2/+3 and +0x1CFC at entry +0xC, the record
        window from +0x1B8C at entry +0x10 (so the name, +0x1B9C, is at entry +0x20)."""
        code = self.image[0x46530E - self.base:0x465346 - self.base]
        for pattern in (b"\x0f\xb6\x87\xec\x1c\x00\x00\x88\x46\x01", b"\x8a\x8f\xed\x1c\x00\x00\x88\x4e\x02",
                        b"\x8a\x97\xee\x1c\x00\x00\x88\x56\x03", b"\x8b\x8f\xfc\x1c\x00\x00\x89\x4e\x0c"):
            self.assertIn(pattern, code)
        self.assertIn(b"\x8d\x87\x8c\x1b\x00\x00", self.image[0x465278 - self.base:0x465287 - self.base])
        self.assertIn(b"\x8d\x4e\x10", self.image[0x465287 - self.base:0x46528A - self.base])


class Rules(unittest.TestCase):
    """What needs no game: the renderer's own rules (CI)."""

    def test_mask_rows(self) -> None:
        self.assertEqual(v5.mask_row(v5.Look()), 0)
        self.assertEqual(v5.mask_row(v5.Look(orange=1)), 1)
        self.assertEqual(v5.mask_row(v5.Look(red=1)), 2)
        self.assertEqual([v5.mask_row(v5.Look(rank=r, orange=1)) for r in range(12, 17)], [3, 4, 3, 3, 3])

    def test_mask_flip_follows_the_builder(self) -> None:
        """scripts/build_vv5_task9_native_actions.py mask_flip: 2 orange, 3 red, 4 purple (12), 5 chief (13)."""
        source = (ROOT / "scripts" / "build_vv5_task9_native_actions.py").read_text(encoding="utf-8")
        for line in ("mov byte ptr [esi+0x1CED], 1", "mov byte ptr [esi+0x1CEE], 1", "mov byte ptr [esi+0x1CFC], 12",
                     "mov byte ptr [esi+0x1CFC], 13", "mov byte ptr [esi+0x1CEC], 1", "cmp byte ptr [esi+0x1CEC], 0"):
            self.assertIn(line, source)
        flips = {k: v5.effective(v5.Look(cosmetic=k)) for k in range(1, 6)}
        self.assertEqual([(f.faction, f.orange, f.red, f.rank) for f in flips.values()],
                         [(1, 0, 0, 0), (1, 1, 0, 0), (1, 0, 1, 0), (1, 0, 0, 12), (1, 0, 0, 13)])
        heathen = v5.Look(faction=1, red=1, cosmetic=5)
        self.assertIs(v5.effective(heathen), heathen)          # a real Heathen is never flipped

    def test_scales(self) -> None:
        self.assertEqual(v5.child_scale(280), 1.0)
        self.assertEqual(v5.child_scale(0), 0.5)
        self.assertAlmostEqual(v5.child_scale(140), pi.f32(0.7), places=6)
        self.assertEqual(v5.head_scale(0), pi.f32(0.8))
        self.assertEqual(v5.head_scale(280), 1.0)
        self.assertEqual(v5._percent(pi.f32(0.6428571)), pi.f32(0.64))

    def test_table_overwrites_on_a_synthetic_file(self) -> None:
        data = struct.pack("<I", v5.BLOCK_A) + bytes(range(256)) * (v5.BLOCK_A // 256) + bytes(v5.BLOCK_A % 256)
        data += struct.pack("<I", v5.BLOCK_B) + bytes(v5.BLOCK_B) + struct.pack("<I", v5.BLOCK_C) + bytes(v5.BLOCK_C)
        t = v5.AnimTable(data)
        self.assertEqual((t.anims[3][0].sprite, t.anims[3][0].frame, t.anims[3][2].sprite), (0xFD, 3, 0xFA))
        self.assertEqual((t.anims[40][0].sprite, t.anims[40][0].frame, t.anims[40][2].sprite), (0xFE, 8, 0xFB))
        self.assertEqual((t.heads[1][4].sprite, t.heads[1][4].frame, t.heads[0][9].frame, t.heads[1][9].frame),
                         (0xF9, 4, 1, 4))
        with self.assertRaises(pi.PictureError):
            v5.AnimTable(data[:100])

    def test_saved_look_offsets(self) -> None:
        name = 0x40
        raw = bytearray(0x200)
        raw[name - 0x1F:name - 0x1C] = b"\x01\x00\x01"
        struct.pack_into("<i", raw, name - 0x14, 13)
        struct.pack_into("<i", raw, name - 8, 6)
        v = common.SaveVillager(rank=0, name="A", male=False, age=900, head=3, body=4, health=50, at=name,
                                data=bytes(raw), mask=2, look=common.LOOK_OLD)
        look = v5.save_look(v)
        self.assertEqual((look.faction, look.orange, look.red, look.rank, look.skeleton, look.old, look.cosmetic),
                         (1, 0, 1, 13, 6, True, 2))
        self.assertEqual(v5.title_of(look), "Heathen Chief")
        self.assertEqual(v5.title_of(v5.Look(rank=13)), "Retired Heathen Chief")
        self.assertEqual(v5.title_of(v5.Look(red=1)), "Former Heathen (red mask)")

    def test_custom_choices(self) -> None:
        r = v5.Renderer(None)
        self.assertTrue(r.problem)
        subjects = r.custom_choices()
        fields = {f.key: f for f in subjects[0].fields}
        self.assertEqual(len(fields["head"].options), 30)
        self.assertEqual(len(fields["body"].options), 30)
        self.assertEqual(sum(o.patcher for o in fields["mask"].options), 5)
        with self.assertRaises(pi.PictureError):
            r.plan_custom({"subject": "villager"})


@unittest.skipUnless(HAVE_GAME, WHY)
class Pictures(unittest.TestCase):
    def test_a_villager_is_drawn(self) -> None:
        r = v5.load(pi.FolderSource(GAME))
        image = r.render_custom({"subject": "villager", "sex": False, "stage": ("child", 100), "head": 4,
                                 "body": 6, "mask": ("heathen", 4), "pose": ("walk", 3), "turn": 5})
        box = image.bbox()
        self.assertIsNotNone(box)
        self.assertGreater(image.height, 60)
        self.assertEqual(len(pi.decode_png(pi.export(image, scale=2).to_png()).data) % 4, 0)


if __name__ == "__main__":
    unittest.main()
