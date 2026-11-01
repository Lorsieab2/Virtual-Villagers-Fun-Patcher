"""Picture Studio, A New Home: the drawing rules in src/vv_pictures_vv1.py, proven against the game's own code.

* The village draw: the game's own compositor 0x437790 is run in Unicorn on the stock executable
  (research/stock-executables), with every atlas built by the game's own constructors (0x40A070, 0x40A0F0,
  0x409ED0; only the sheet loader 0x40A530 is replaced, by one that gives each sheet its real size) and a
  record in every state the compositor reads -- states, directions, frames, head facings, sexes, every
  child age and adults, the Golden Child, carried items and litters, water, dead, selected and held.  Every
  blit it reaches (0x403D70 scaled / faded, 0x403D00 plain: sheet, source rectangle, place, surface alpha,
  scale) must be the renderer's plan, in order.
* The masks: the same, on the executable the patcher builds with Origins (its village mask hooks on
  0x409410 / 0x4093C0), the mask atlas built through the game's constructor as Vv1GetMaskSprite does.
* The blitter: 0x403D70 is run on real pixels (Windows' 53-bit x87 precision) and its screen must be the
  one vv_picture_image's rules give (box-averaged scaling, surface alpha).
* The save reader and renderer on synthetic saves (never the owner's), and the art when
  research/game-images holds a copy of the game's Images folder.

Everything emulated needs the stock exe, Unicorn and pefile, and skips without them (CI).
"""
from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_picture_image as pi  # noqa: E402
import vv_pictures_vv1 as vv1  # noqa: E402

try:
    import pefile  # noqa: F401
    from unicorn.x86_const import UC_X86_REG_FPCW
    from story_emulator import API_STUBS, Process
    HAVE_UNICORN = True
except ImportError:                                    # CI: no Unicorn
    HAVE_UNICORN = False

EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
ART = ROOT / "research" / "game-images" / "Virtual Villagers - A New Home" / "Images"
EMULATOR = HAVE_UNICORN and EXE.is_file()
WHY = "the stock A New Home executable (and Unicorn) are needed"

# The real sizes of the sheets (A New Home's Images folder, and the patcher's own art).
SIZES = {
    "female_heads.png": (280, 1300), "male_heads.png": (280, 1300),
    "female_bodies00.png": (640, 650), "female_bodies10.png": (640, 650),
    "female_bodies01.png": (640, 650), "female_bodies11.png": (640, 650),
    "male_bodies00.png": (640, 650), "male_bodies10.png": (640, 650),
    "male_bodies01.png": (640, 650), "male_bodies11.png": (640, 650),
    "female_actions00.png": (360, 650), "female_actions01.png": (360, 650),
    "male_actions00.png": (360, 650), "male_actions01.png": (360, 650),
    "carrying.png": (600, 25), "skelly.png": (240, 65), "ripple.png": (260, 65),
    "peep_shadow1.png": (68, 64), "focus_circle.png": (68, 64),
    "mask_atlas.png": (280, 800), "golden_mushroom.png": (29, 22),
    "vvfp_grey_male_heads.png": (280, 1300), "vvfp_grey_female_heads.png": (280, 1300),
}

NEW, SHEET_CTOR = 0x44AF03, 0x40A530
CTOR_ONE, CTOR_GRID, CTOR_WHOLE = 0x40A070, 0x40A0F0, 0x409ED0
COMPOSITOR = 0x437790
BLIT_SCALED, BLIT_PLAIN = 0x403D70, 0x403D00
GROUND, RAND, RAND_F, PARTICLES = 0x414200, 0x402F10, 0x402F70, 0x41AFD0
FPCW = 0x027F                       # Windows runs the x87 at 53-bit precision


class SizeSource:
    """A source with only the sheets' sizes (a PNG header each): enough to plan, not to draw."""

    def read(self, name: str) -> bytes | None:
        size = SIZES.get(name) or next((v for k, v in SIZES.items() if k.casefold() == name.casefold()), None)
        if size is None:
            return None
        return pi.PNG_MAGIC + struct.pack(">I4sII", 13, b"IHDR", *size) + bytes(5)


def f32bits(value: float) -> int:
    return struct.unpack("<I", struct.pack("<f", value))[0]


def bits_f32(value: int) -> float:
    return struct.unpack("<f", struct.pack("<I", value & 0xFFFFFFFF))[0]


def signed(value: int) -> int:
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value & 0x80000000 else value


class Village:
    """A New Home's village draw in Unicorn: a game object whose atlases the game's own constructors built,
    one villager record, and every blit recorded."""

    def __init__(self, exe: bytes, dll: Path | None = None) -> None:
        p = self.p = Process(exe, dll)
        if dll is None:                 # with a DLL, Process binds the executable's imports too
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
        self.surfaces: dict[int, str] = {}
        p.stub(NEW, lambda q: (q.alloc(max(q.arg(0), 4)), 0))
        p.stub(SHEET_CTOR, self._sheet)
        self.blits: list[pi.Draw] = []
        p.stub(BLIT_SCALED, self._blit_scaled)
        p.stub(BLIT_PLAIN, self._blit_plain)
        self.ground = 0
        self.rand = 99
        self.ripple = 0
        self.particles = 0
        p.stub(GROUND, lambda q: (self.ground, 8))
        p.stub(RAND, lambda q: (self.rand % max(1, q.arg(0)), 0))
        p.stub(RAND_F, lambda q: (self.ripple, 0))
        p.stub(PARTICLES, self._particles)
        self.game = p.alloc(0x3E100)
        # the scaled-cell wrapper's object: [0] the renderer, whose clip rectangle is +0x60..+0x6C
        renderer = p.alloc(0x100)
        p.write(renderer + 0x60, struct.pack("<iiii", -100000, -100000, 100000, 100000))
        wrapper = p.alloc(0x10)
        p.put32(wrapper, renderer)
        p.put32(self.game + 0x3E00C, wrapper)
        p.put32(self.game + 0x3E010, p.alloc(0x40))           # the camera at 0, 0
        p.put32(self.game + 0x3E014, p.alloc(0x40))
        p.put32(self.game + 0x3E018, p.alloc(0x40))
        for i in range(256):
            p.put32(self.game + 0x3DBDC + 4 * i, i)
        self.atlases: dict[int, int] = {}
        for slot_, atlas in vv1.ATLASES.items():
            self.atlases[slot_] = self.build(atlas)
            p.put32(self.game + slot_, self.atlases[slot_])
        for slot_, name in vv1.IMAGES.items():
            obj = p.alloc(0x34)
            self.call(CTOR_WHOLE, [self.cstr(name)], ecx=obj)
            p.put32(self.game + slot_, obj)

    def cstr(self, text: str) -> int:
        at = self.p.alloc(len(text) + 1)
        self.p.write(at, text.encode() + b"\0")
        return at

    def call(self, fn: int, args, ecx=None) -> int:
        self.p.mu.reg_write(UC_X86_REG_FPCW, FPCW)
        return self.p.call(fn, list(args), ecx=ecx)

    def build(self, atlas: pi.Atlas) -> int:
        """The atlas built by the game's own constructor, as 0x43C08E-0x43C2EB builds it."""
        obj = self.p.alloc(0x34)
        if atlas.grid:
            across, down = atlas.sheets
            self.call(CTOR_GRID, [self.cstr(atlas.name), self.cstr(atlas.suffix), across, down, atlas.cols,
                                  atlas.rows], ecx=obj)
        else:
            self.call(CTOR_ONE, [self.cstr(atlas.name), atlas.cols, atlas.rows], ecx=obj)
        return obj

    def _sheet(self, q):
        """0x40A530 (thiscall, the file name): a sheet object [surface, is-PNG] with a surface of the real size."""
        name = q.cstring(q.arg(0))
        w, h = SIZES[name]
        surface = q.alloc(0x40)
        q.put32(surface + 8, w)
        q.put32(surface + 12, h)
        self.surfaces[surface] = name
        q.put32(q.reg("ecx"), surface)
        q.write(q.reg("ecx") + 4, b"\x01")
        return q.reg("ecx"), 4

    def _blit_scaled(self, q):
        a = [q.arg(i) for i in range(10)]
        self.blits.append(pi.Draw(self.surfaces[a[0]], tuple(signed(v) for v in a[3:7]), signed(a[1]), signed(a[2]),
                                  bits_f32(a[8]), bits_f32(a[7])))
        return 0, 0x28

    def _blit_plain(self, q):
        a = [q.arg(i) for i in range(7)]
        self.blits.append(pi.Draw(self.surfaces[a[0]], tuple(signed(v) for v in a[3:7]), signed(a[1]), signed(a[2])))
        return 0, 0x1C

    def _particles(self, q):
        self.particles += 1
        return 0, 0x1C

    def draw(self, v: "vv1.Villager", x: int = 1000, y: int = 1000) -> list[pi.Draw]:
        """The blits the compositor makes for record 0 holding `v` at (x, y)."""
        p, r = self.p, self.game
        p.write(r, bytes(0x3D8))
        p.write(r + 0x28, bytes((1, 1 if v.selected else 0, 1 if v.held else 0)))
        for off, value in ((4, x), (8, y), (0x20, v.frame), (0x30, v.direction), (0x34, v.head_col),
                           (0x38, v.state), (0x3C, v.item), (0x58, v.act), (0x344, v.health), (0x348, v.age),
                           (0x350, 1 if v.male else 2), (0x35C, v.litter), (0x360, v.head), (0x364, v.body),
                           (0x368, v.bones), (0x36C, vv1.GOLDEN if v.golden else 3)):
            p.put32(r + off, value)
        for i in range(1, 256):
            p.write(r + i * 0x3D8 + 0x28, b"\0")
        self.ground = vv1.WATER if v.water else 1
        self.ripple = v.ripple
        self.blits = []
        self.call(COMPOSITOR, [], ecx=r)
        return self.blits


def keys(plan) -> list[tuple]:
    return [d.key() for d in plan]


@unittest.skipUnless(EMULATOR, WHY)
class VillageDrawIsTheGames(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.village = Village(EXE.read_bytes())
        cls.sheets = pi.Sheets(SizeSource())
        cls.count = 0

    def check(self, v: "vv1.Villager", label: str) -> None:
        game = self.village.draw(v)
        plan = vv1.plan(v, self.sheets, 1000, 1000)
        self.assertEqual(keys(plan), keys(game), f"{label}: {v}")
        type(self).count += 1

    def test_atlases_are_the_ones_the_game_builds(self) -> None:
        """0x43C08E-0x43C2EB: each atlas's constructor and arguments, read from the code."""
        import pefile as pf
        pe = pf.PE(str(EXE))
        image = pe.get_memory_mapped_image()
        base = pe.OPTIONAL_HEADER.ImageBase

        def u32(va):
            return struct.unpack_from("<I", image, va - base)[0]

        def text(va):
            return image[va - base:va - base + 64].split(b"\0", 1)[0].decode()
        # Each constructor call in the block: (pushes before the call, the call, the slot after it).
        found = {}
        code = image[0x43C060 - base:0x43C300 - base]
        at = 0
        pushes: list[int] = []
        while at < len(code):
            op = code[at]
            if op == 0x6A:                                        # push imm8
                pushes.append(code[at + 1] if code[at + 1] < 0x80 else code[at + 1] - 256)
                at += 2
            elif op == 0x68:                                      # push imm32
                pushes.append(struct.unpack_from("<I", code, at + 1)[0])
                at += 5
            elif op == 0x55:                                      # push ebp (2 there)
                pushes.append(2)
                at += 1
            elif op == 0xE8:                                      # call rel32
                target = 0x43C060 + at + 5 + struct.unpack_from("<i", code, at + 1)[0]
                found_call = (target, list(reversed(pushes)))
                pushes = []
                at += 5
                # the next `mov [esi+disp32], eax` names the slot
                k = at
                while k < len(code) - 6 and not (code[k] == 0x89 and code[k + 1] == 0x86):
                    k += 1
                if found_call[0] in (CTOR_ONE, CTOR_GRID, CTOR_WHOLE):
                    found[struct.unpack_from("<I", code, k + 2)[0]] = found_call
            else:
                at += 1
        for slot_, atlas in vv1.ATLASES.items():
            target, args = found[slot_]
            if atlas.grid:
                self.assertEqual(target, CTOR_GRID, hex(slot_))
                prefix, suffix, across, down, cols, rows = args
                self.assertEqual((text(prefix), text(suffix), across, down, cols, rows),
                                 (atlas.name, atlas.suffix, *atlas.sheets, atlas.cols, atlas.rows), hex(slot_))
            else:
                self.assertEqual(target, CTOR_ONE, hex(slot_))
                self.assertEqual((text(args[0]), args[1], args[2]), (atlas.name, atlas.cols, atlas.rows), hex(slot_))
        for slot_, name in vv1.IMAGES.items():
            self.assertEqual(found[slot_][0], CTOR_WHOLE)
            self.assertEqual(text(found[slot_][1][0]), name)
        del u32

    def test_every_cell_is_cut_as_the_game_cuts_it(self) -> None:
        """0x409F90 on the atlases the game built, against pi.Atlas.cell, for every cell (and past the end)."""
        rect = self.village.p.alloc(16)
        for slot_, atlas in vv1.ATLASES.items():
            obj = self.village.atlases[slot_]
            for row in range(atlas.rows + 2):
                for col in range(atlas.cols + 2):
                    self.village.call(0x409F90, [col, row, rect], ecx=obj)
                    got = struct.unpack("<iiii", self.village.p.read(rect, 16))
                    sheet = self.village.surfaces[self.village.p.u32(self.village.p.u32(obj + 4))]
                    self.assertEqual(atlas.cell(SizeSource_size, col, row), (sheet, got), (atlas.name, col, row))

    def test_adults_walking_every_direction_frame_facing_and_sex(self) -> None:
        for male in (True, False):
            for direction in range(4):
                for frame in range(8):
                    for head_col in (0, 3, 5, 6):
                        self.check(vv1.Villager(male=male, age=700, head=(frame * 3 + direction) % 20,
                                                body=(frame + 7 * direction) % 20, direction=direction, frame=frame,
                                                head_col=head_col), "walking")
            self.check(vv1.Villager(male=male, age=700, head=19, body=19, state=5, direction=2, frame=3), "state 5")

    def test_adult_work_poses(self) -> None:
        for male in (True, False):
            for frame in range(4):
                for state in (1, 3):
                    self.check(vv1.Villager(male=male, age=900, head=4, body=11, state=state, frame=frame), "work")
                    self.check(vv1.Villager(male=male, age=900, head=4, body=11, state=state, frame=frame, item=5),
                               "work + item")
            for direction in range(4):
                self.check(vv1.Villager(male=male, age=400, head=2, body=6, state=2, direction=direction, head_col=1),
                           "sitting")
            for state in (4, 6, 7, 9):
                self.check(vv1.Villager(male=male, age=400, state=state), f"state {state}")

    def test_carrying_and_litters(self) -> None:
        for direction in range(4):
            for item in (0, 3, 8, 14, 0x13):
                for litter in (0, 1, 2, 3):
                    for state in (0, 2):
                        self.check(vv1.Villager(male=False, age=500, head=7, body=3, state=state, direction=direction,
                                                item=item, litter=litter, frame=2), "carrying")
                self.check(vv1.Villager(male=True, age=120, direction=direction, item=item, frame=1), "child carrying")
                self.check(vv1.Villager(male=True, age=120, state=1, direction=direction, item=item, frame=2),
                           "child bent carrying")

    def test_every_carried_item(self) -> None:
        """Every item of vv_pictures_carried.VV1 (the patcher's Golden Mushroom included), in every direction
        and every pose that draws the item -- walking (with twins and triplets), bent over, sitting, standing
        at work, a child walking and bent -- is blitted by the game's own draw as the plan says.  The Golden
        Mushroom's stock blits are what the patched game swaps for golden_mushroom.png (carried_golden)."""
        import carried_golden
        import vv_pictures_carried as carried
        golden = carried.GOLDEN_ITEM[vv1.GAME]
        n = 0
        for it in carried.items(vv1.GAME):
            for direction in range(4):
                cases = [vv1.Villager(male=direction % 2 == 0, age=500, head=7, body=3, state=state, direction=direction,
                                      item=it.value, litter=litter, frame=1)
                         for state, litter in ((0, 0), (0, 2), (0, 3), (1, 0), (2, 0), (2, 3), (3, 0))]
                cases += [vv1.Villager(male=True, age=120, direction=direction, item=it.value, frame=1),
                          vv1.Villager(male=False, age=60, state=1, direction=direction, item=it.value, frame=2)]
                for v in cases:
                    game = self.village.draw(v)
                    stock = vv1.plan(v, self.sheets, 1000, 1000, golden_art=False)
                    self.assertEqual(keys(stock), keys(game), f"{it.name}: {v}")
                    if it.value == golden:
                        self.assertEqual(keys(vv1.plan(v, self.sheets, 1000, 1000)),
                                         carried_golden.swapped(stock, vv1.GAME, lambda d: d.what == "carried"), v)
                    n += 1
        self.assertEqual(n, len(carried.items(vv1.GAME)) * 4 * 9)

    def test_children_at_every_age(self) -> None:
        for age in range(0, vv1.ADULT + 1):
            male = age % 2 == 0
            self.check(vv1.Villager(male=male, age=age, head=age % 20, body=(age * 7) % 20, direction=age % 4,
                                    frame=age % 8, head_col=age % 7), f"child {age}")
        for age in range(0, vv1.ADULT, 13):
            for frame in range(4):
                self.check(vv1.Villager(male=age % 3 == 0, age=age, head=5, body=9, state=1, frame=frame), "child bent")
            self.check(vv1.Villager(age=age, state=2, direction=1), "child state 2 walks")

    def test_the_golden_child(self) -> None:
        for age in (40, 100, 200, 279):
            for state in (0, 1, 2, 3):
                for act in (0, 6, 7):
                    self.check(vv1.Villager(male=False, age=age, golden=True, head=19, body=4, state=state, act=act,
                                            frame=state + act % 5, direction=act % 4, head_col=state), "golden")
            self.check(vv1.Villager(age=age, golden=True, water=True, head=19, body=4), "golden in water")
        self.assertEqual(self.village.particles, 0)   # the sparkle: rand(100) < 10 only

    def test_water_dead_selected_held(self) -> None:
        for male in (True, False):
            for ripple in range(4):
                for head_col in range(7):
                    self.check(vv1.Villager(male=male, age=800, head=12, water=True, ripple=ripple, head_col=head_col,
                                            selected=ripple == 2), "swimming")
            self.check(vv1.Villager(male=male, age=60, head=12, water=True, selected=True), "child in water")
            for bones in (0, 1, 2, 3, 7, -1, -6):
                self.check(vv1.Villager(male=male, age=800, health=0, bones=bones), "dead")
                self.check(vv1.Villager(male=male, age=50, health=-4, bones=bones, selected=True), "dead child")
            for selected in (False, True):
                for held in (False, True):
                    for water in (False, True):
                        self.check(vv1.Villager(male=male, age=700, selected=selected, held=held, water=water, head=1),
                                   "selected/held")
                        self.check(vv1.Villager(male=male, age=70, selected=selected, held=held, water=water, head=1),
                                   "child selected/held")

    def test_ripple_is_faded_by_the_stale_04(self) -> None:
        game = self.village.draw(vv1.Villager(age=800, water=True))
        self.assertEqual(round(game[0].alpha, 6), round(pi.f32(0.4), 6))

    @classmethod
    def tearDownClass(cls) -> None:
        print(f"\nA New Home: {cls.count} villager states drawn by the game and the renderer alike")


def SizeSource_size(name: str) -> tuple[int, int]:
    return SIZES[name]


ORIGINS = "vv1_enable_origins_exclusive_features"
MASK_TABLE, MASK_MANAGER, MASK_SPRITE = 0x491000, 0x491098, 0x4911B8   # scripts/build_vv1_origins_feature.py


def _origins_exe() -> bytes:
    import vv_fun_patcher as patcher
    builds = {build.id: build for build in patcher.load_builds()}
    rendered, _ = patcher.render_patched_bytes(EXE, builds["vv1"], "stock", [ORIGINS])
    return bytes(rendered)


@unittest.skipUnless(EMULATOR, WHY)
class OriginsMasksAreThePatchersOwn(unittest.TestCase):
    """The village with the Origins row: the patcher's own mask hooks on 0x409410 / 0x4093C0 draw each
    masked head's mask; the compositor is run whole, the mask atlas built by the game's constructor as
    Vv1GetMaskSprite builds it (mask_atlas.png, 7 x 5)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.village = Village(_origins_exe())
        p = cls.village.p
        cls.mask_atlas = cls.village.build(vv1.MASK_ATLAS)
        p.put32(MASK_MANAGER, cls.village.game)
        p.put32(MASK_SPRITE, cls.mask_atlas)
        cls.sheets = pi.Sheets(SizeSource())
        cls.count = 0

    def check(self, v: "vv1.Villager", label: str) -> None:
        table = bytearray(128)
        table[0] = v.mask                       # record 0's nibble
        self.village.p.write(MASK_TABLE, bytes(table))
        game = self.village.draw(v)
        plan = vv1.plan(v, self.sheets, 1000, 1000)
        self.assertEqual(keys(plan), keys(game), f"{label}: {v}")
        if v.mask and v.health > 0 and v.state != 4:
            self.assertIn("mask_atlas.png", [d.file for d in game], label)
        type(self).count += 1

    def test_every_mask_on_every_pose(self) -> None:
        for mask in range(6):
            for male in (True, False):
                for state in (0, 1, 2, 3, 5):
                    for frame in (0, 3):
                        self.check(vv1.Villager(male=male, age=700, head=8, body=2, state=state, frame=frame,
                                                direction=frame % 4, head_col=(frame + mask) % 7, mask=mask), "adult")
                self.check(vv1.Villager(male=male, age=700, water=True, mask=mask, head_col=mask), "swimming")
                for age in (0, 40, 99, 180, 279):
                    self.check(vv1.Villager(male=male, age=age, head=8, body=2, mask=mask, head_col=mask, frame=age % 8),
                               "child")
                    self.check(vv1.Villager(male=male, age=age, state=1, frame=2, mask=mask), "child bent")
                self.check(vv1.Villager(age=100, golden=True, head=19, mask=mask), "golden")
                self.check(vv1.Villager(age=700, health=0, mask=mask), "dead")

    @classmethod
    def tearDownClass(cls) -> None:
        print(f"\nA New Home with Origins: {cls.count} masked states drawn by the patched game and the renderer alike")


GREY_DLL = ROOT / "assets" / "vv1_grey_hair" / "VVFP VV1 Grey Hair.dll"
INVALID = 0xFFFFFFFF


def _png_header(name: str) -> bytes:
    w, h = SIZES[name]
    return pi.PNG_MAGIC + struct.pack(">I4sII", 13, b"IHDR", w, h) + b"\x08\x06\x00\x00\x00"


@unittest.skipUnless(EMULATOR and GREY_DLL.is_file(), WHY + ", and the Grey Hair companion")
class GreyHairIsThePatchersOwn(unittest.TestCase):
    """The village with Grey Hair at 55: "VVFP VV1 Grey Hair.dll" started in the emulator on the stock
    executable (its 31 splices installed by its own installer), its grey sheets built by the game's own
    constructor, and the head look answered through a "VVFP Head Look.dll" the test stands in for (Auto, Young or
    Old); the whole compositor is run and every blit compared with the renderer's plan."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.village = cls.start(EXE.read_bytes())
        cls.sheets = pi.Sheets(SizeSource())
        cls.count = 0

    @classmethod
    def start(cls, exe: bytes) -> "Village":
        v = Village(exe, GREY_DLL)
        p = v.p
        cls.look = None                                         # None and 0: Auto
        handles: dict[int, bytes] = {}

        def create(q):
            path = q.wstring(q.arg(0))
            for name in vv1.GREY.values():
                if path.lower().endswith("\\images\\" + name):
                    handle = 0x600 + len(handles)
                    handles[handle] = _png_header(name)
                    return handle, 28
            return INVALID, 28

        def read(q):
            data = handles[q.arg(0)][:q.arg(2)]
            q.write(q.arg(1), data)
            q.put32(q.arg(3), len(data))
            return 1, 20
        fns = {}
        for name, (value, pop) in {"VvfpHeadLookInstalled": (1, 4), "VvfpHeadLookGet": (None, 8),
                                   "VvfpHeadLookSet": (0, 12), "VvfpHeadLookSetMany": (0, 20)}.items():
            at = p.alloc(16)
            p.write(at, b"\xC3")
            fns[name] = at
            p.stub(at, (lambda val, n: (lambda q: (((cls.look or 0) if val is None else val), n)))(value, pop))

        def module(q):
            wanted = q.cstring(q.arg(0))
            if wanted == "VVFP Head Look.dll":
                return 0x7700, 4      # present from the start: the companion looks it up once
            return 0x400000, 4

        def proc(q):
            return fns.get(q.cstring(q.arg(1)), 0), 8
        p.api_handlers.update(CreateFileW=create, ReadFile=read, CloseHandle=lambda q: (1, 4),
                              GetModuleHandleA=module, GetProcAddress=proc)
        p.export("VvfpStartup", 1, 0)
        return v

    def check(self, villager: "vv1.Villager", look: int | None, label: str) -> None:
        type(self).look = look
        grey = vv1.common.old_head(villager.age, vv1.common.LOOK_AUTO if look is None else look)
        v = vv1.replace(villager, grey=grey)
        game = self.village.draw(v)
        plan = vv1.plan(v, self.sheets, 1000, 1000)
        self.assertEqual(keys(plan), keys(game), f"{label} (look {look}): {v}")
        type(self).count += 1

    def test_ages_and_looks_in_every_pose(self) -> None:
        for look in (None, 0, 1, 2):
            for age in (0, 279, 280, 1099, 1100, 2400):
                for male in (True, False):
                    for state in (0, 1, 2, 3):
                        self.check(vv1.Villager(male=male, age=age, head=(age + state) % 20, body=3, state=state,
                                                frame=1, direction=state, head_col=age % 7), look, "pose")
                    self.check(vv1.Villager(male=male, age=age, water=True, head=7), look, "water")
                self.check(vv1.Villager(age=age, golden=True, head=19, body=2), look, "golden")
        self.assertIn("vvfp_grey_female_heads.png", self.village.surfaces.values())

    def test_a_grey_head_keeps_its_mask(self) -> None:
        """Grey Hair on the executable the patcher builds with Origins: the head grey, the mask as before."""
        village = self.start(_origins_exe())
        village.p.put32(MASK_MANAGER, village.game)
        village.p.put32(MASK_SPRITE, village.build(vv1.MASK_ATLAS))
        type(self).look = None
        for mask in (1, 5):
            for age in (100, 700, 1100, 1500):
                for state in (0, 1, 2, 3):
                    table = bytearray(128)
                    table[0] = mask
                    village.p.write(MASK_TABLE, bytes(table))
                    v = vv1.Villager(male=age % 2 == 0, age=age, head=4, body=6, state=state, frame=2, mask=mask,
                                     grey=age >= 1100)
                    game = village.draw(v)
                    self.assertEqual(keys(vv1.plan(v, self.sheets, 1000, 1000)), keys(game), v)
                    if age >= 1100:
                        self.assertTrue(any("grey" in d.file for d in game) and any(d.file == "mask_atlas.png"
                                                                                     for d in game), v)

    @classmethod
    def tearDownClass(cls) -> None:
        print(f"\nA New Home with Grey Hair at 55: {cls.count} states drawn by the patched game and the renderer alike")


@unittest.skipUnless(EMULATOR, WHY)
class PlaceScaledIsTheGames(unittest.TestCase):
    """0x407ED0 (place-scaled: centring) on synthetic cells, against pi.centre_offset."""

    def test_centring(self) -> None:
        v = Village(EXE.read_bytes())
        p = v.p
        renderer = p.alloc(0x100)
        p.write(renderer + 0x60, struct.pack("<iiii", -100000, -100000, 100000, 100000))
        rect, px, py, flag = p.alloc(16), p.alloc(4), p.alloc(4), p.alloc(4)
        for w, h in ((40, 65), (40, 160), (68, 64), (13, 7)):
            for percent in range(50, 101):
                p.write(rect, struct.pack("<iiii", 40, 65, 40 + w, 65 + h))
                p.put32(px, 500)
                p.put32(py, 600)
                p.put32(flag, 1)
                v.call(0x407ED0, [rect, px, py, percent, flag], ecx=renderer)
                dx, dy = pi.centre_offset(w, h, percent)
                self.assertEqual((signed(p.u32(px)) - 500, signed(p.u32(py)) - 600), (dx, dy), (w, h, percent))


@unittest.skipUnless(EMULATOR, WHY)
class BlitterIsTheGames(unittest.TestCase):
    """The pixels: 0x403D70 on a test picture against vv_picture_image's rules (shared by all five games:
    the same engine)."""

    @staticmethod
    def pattern(w: int, h: int) -> bytes:
        return b"".join(bytes(((x * 37 + y * 11) % 256, (x * 5 + y * 13) % 256, (x * y) % 256,
                               (0 if (x + y) % 7 == 0 else 255 if (x * y) % 3 else (x * 29 + y * 3) % 256)))
                        for y in range(h) for x in range(w))

    def setUp(self) -> None:
        self.p = p = Process(EXE.read_bytes())
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
        p.put32(self.gfx + 0xC, self.sh)

    def surface(self, w: int, h: int, amask: int) -> int:
        p = self.p
        fmt = p.alloc(0x40)
        p.put32(fmt, 0x16362004 if amask else 0x16161804)
        p.write(fmt + 8, bytes((32, 4)))
        for off, mask in ((12, 0x00FF0000), (16, 0x0000FF00), (20, 0x000000FF), (24, amask)):
            p.put32(fmt + off, mask)
        p.write(fmt + 28, bytes((0, 0, 0, 0 if amask else 8, 16, 8, 0, 24 if amask else 0)))
        s, px = p.alloc(0x40), p.alloc(w * h * 4 + 16)
        p.put32(s + 4, fmt)
        p.put32(s + 8, w)
        p.put32(s + 12, h)
        p.put32(s + 16, w * 4)
        p.put32(s + 20, px)
        p.write(s + 36, struct.pack("<iiii", 0, 0, w, h))
        return s

    def blit(self, src: int, rect, x: int, y: int, alpha: float, scale: float) -> list[tuple]:
        p = self.p
        r, g, b = 10, 200, 30
        p.write(p.u32(self.screen + 20), bytes((b, g, r, 0)) * (self.sw * self.sh))
        p.mu.reg_write(UC_X86_REG_FPCW, FPCW)
        p.call(BLIT_SCALED, [src, x, y, *rect, f32bits(alpha), f32bits(scale), 0], ecx=self.gfx)
        raw = p.read(p.u32(self.screen + 20), self.sw * self.sh * 4)
        return [(raw[i + 2], raw[i + 1], raw[i]) for i in range(0, len(raw), 4)]

    def expected(self, piece: pi.Image, x: int, y: int, alpha: float) -> list[tuple]:
        """The piece put down as the blitter does it on an opaque screen: (s * a + d * (255 - a) + 127) >> 8,
        a the pixel's alpha times the surface alpha ((a * A + 127) >> 8), clear pixels left alone."""
        bg = (10, 200, 30)
        out = [bg] * (self.sw * self.sh)
        big_a = pi.surface_alpha(alpha)
        for j in range(piece.height):
            for i in range(piece.width):
                r, g, b, a = piece.pixel(i, j)
                if a == 0:
                    continue
                if big_a < 255:
                    a = (a * big_a + 127) >> 8
                at = (y + j) * self.sw + x + i
                out[at] = tuple((s * a + d * (255 - a) + 0x7F) >> 8 for s, d in zip((r, g, b), out[at]))
        return out

    def test_scaled_and_faded_pixels(self) -> None:
        w, h = 88, 70
        rgba = self.pattern(w, h)
        sheet = pi.Image(w, h, rgba)
        src = self.surface(w, h, 0xFF000000)
        argb = bytearray(len(rgba))
        argb[0::4], argb[1::4], argb[2::4], argb[3::4] = rgba[2::4], rgba[1::4], rgba[0::4], rgba[3::4]
        self.p.write(self.p.u32(src + 20), bytes(argb))
        cases = 0
        for percent in (50, 57, 63, 70, 77, 80, 85, 89, 90, 93, 97, 99):
            scale = pi.percent_scale(percent)
            for rect in ((0, 0, 40, 65), (40, 0, 80, 65), (3, 2, 43, 67)):
                for alpha in (1.0, 0.5, 0.25, 0.9):
                    got = self.blit(src, rect, 20, 9, alpha, scale)
                    want = self.expected(pi.blit_piece(sheet, rect, scale), 20, 9, alpha)
                    self.assertEqual(got, want, (percent, rect, alpha))
                    cases += 1
        for alpha in (0.4, 0.5, 0.8):
            got = self.blit(src, (0, 0, 40, 65), 20, 9, pi.f32(alpha), 1.0)
            want = self.expected(sheet.sub(0, 0, 40, 65), 20, 9, pi.f32(alpha))
            # The unscaled faded path also blends clear pixels (a = 0), which darkens the screen by at most
            # one step under them: no picture shows that; every other pixel must be the same.
            clear = {(20 + i) + (9 + j) * self.sw for j in range(65) for i in range(40) if sheet.pixel(i, j)[3] == 0}
            self.assertEqual([c for k, c in enumerate(got) if k not in clear],
                             [c for k, c in enumerate(want) if k not in clear], alpha)
            cases += 1
        self.assertGreater(cases, 100)


# ------------------------------------------------------------------------------- without the game

class Planning(unittest.TestCase):
    """The renderer itself, on sizes alone (no game, no art)."""

    def setUp(self) -> None:
        self.r = vv1.load(SizeSource())

    def test_required_files_are_the_atlases_sheets(self) -> None:
        files = vv1.required_files()
        self.assertIn("male_bodies11.png", files)
        self.assertIn("female_actions01.png", files)
        self.assertEqual(len(files), len(set(files)))
        self.assertTrue(all(name in SIZES for name in files))
        for path in vv1.patcher_art().values():
            self.assertTrue(path.is_file(), path)

    def test_custom_choices_cover_every_row_and_stage(self) -> None:
        (subject,) = self.r.custom_choices()
        fields = {f.key: f for f in subject.fields}
        self.assertEqual([o.key for o in fields["head"].options], list(range(20)))
        self.assertEqual([o.key for o in fields["body"].options], list(range(20)))
        self.assertEqual([o.key for o in fields["mask"].options], list(range(6)))
        self.assertTrue(all(o.patcher for o in fields["mask"].options[1:]))
        stages = [o.key[0] for o in fields["stage"].options]
        for stage in ("child", "adult", "elder", "dead", "golden"):
            self.assertIn(stage, stages)
        self.assertEqual(len([s for s in stages if s == "child"]), 12)

    def test_every_custom_combination_plans(self) -> None:
        (subject,) = self.r.custom_choices()
        fields = {f.key: f for f in subject.fields}
        for stage in fields["stage"].options:
            for pose in fields["pose"].options:
                spec = {"subject": "villager", "sex": False, "stage": stage.key, "head": 3, "body": 4,
                        "mask": 2, "look": 2, "pose": pose.key, "frame": 3, "direction": 1, "head_col": 4}
                if pose.key == "golden_act" and stage.key[0] != "golden":
                    with self.assertRaises(pi.PictureError):
                        self.r.plan_custom(spec)
                    continue
                plan = self.r.plan_custom(spec)
                self.assertTrue(plan, (stage, pose))
                if stage.key[0] == "dead":
                    self.assertEqual([d.what for d in plan], ["skeleton"])
                    self.assertEqual(plan[-1].file, "skelly.png")
                else:
                    self.assertIn("mask", [d.what for d in plan])

    def test_grey_hair_follows_the_age_and_the_look(self) -> None:
        def head_file(age, look):
            spec = {"stage": ("adult", age), "look": look, "head": 4}
            return next(d.file for d in self.r.plan_custom(spec) if d.what == "head")
        self.assertEqual(head_file(1099, 0), "male_heads.png")
        self.assertEqual(head_file(1100, 0), "vvfp_grey_male_heads.png")
        self.assertEqual(head_file(1100, 1), "male_heads.png")
        self.assertEqual(head_file(300, 2), "vvfp_grey_male_heads.png")
        self.assertEqual(head_file(2000, -1), "male_heads.png")       # no Grey Hair patch: never grey

    def test_masks_ride_the_head(self) -> None:
        adult = self.r.plan_custom({"stage": ("adult", 600), "mask": 3, "head_col": 2})
        head, mask = [d for d in adult if d.what == "head"][0], [d for d in adult if d.what == "mask"][0]
        self.assertEqual((mask.file, mask.rect, mask.x, mask.y), ("mask_atlas.png", (80, 320, 120, 480), head.x,
                                                                 head.y - 48))
        child = self.r.plan_custom({"stage": ("child", 100), "mask": 1, "head_col": 5})
        head, mask = [d for d in child if d.what == "head"][0], [d for d in child if d.what == "mask"][0]
        percent = 100 // 14 + 80
        self.assertEqual(mask.scale, head.scale)
        self.assertEqual(mask.rect, (200, 0, 240, 160))
        # both centred on their own cells, the mask lifted by (scale * 15) >> 5 before centring
        self.assertEqual(mask.y - pi.centre_offset(40, 160, percent)[1],
                         head.y - pi.centre_offset(40, 65, percent)[1] - ((percent * 15) >> 5))


class SavedVillage(unittest.TestCase):
    """saved_items / plan_saved on a synthetic A New Home save (never a real one)."""

    def make_save(self, folder: Path) -> None:
        import vv_log_tools
        checker = vv_log_tools.load_checker()
        data = bytearray(checker.VV1_BLOCK0 + 256 * checker.VV1_STRIDE + 0x100)
        data[:4] = b"ldwg"

        def put(rank, name, male, age, head, body, health=100, family=3, bones=0):
            base = checker.VV1_BLOCK0 + rank * checker.VV1_STRIDE - checker.VV1_BASE
            data[base + 0x3D4] = 1
            data[base + 0x370:base + 0x370 + len(name)] = name.encode()
            for off, value in ((0x350, 1 if male else 2), (0x348, age), (0x360, head), (0x364, body),
                               (0x344, health), (0x36C, family), (0x368, bones)):
                struct.pack_into("<i", data, base + off, value)
        put(0, "Akika", True, 700, 6, 8)
        put(1, "Bem", False, 1200, 13, 14)
        put(2, "Kanoa", True, 100, 19, 4, family=0xC7)
        put(3, "Lani", False, 140, 2, 3)
        put(4, "Moana", True, 900, 5, 5, health=0, bones=2)
        (folder / "Virtual Villagers1.ldw").write_bytes(bytes(data))

    def test_saved_items_and_plans(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.make_save(folder)
            r = vv1.load(SizeSource())
            items = r.saved_items(folder, 1)
            self.assertEqual([i.label for i in items],
                             ["Akika (adult, 35 years)", "Bem (elder, 60 years)", "Kanoa (the Golden Child, 5 years)",
                              "Lani (child, 7 years)", "Moana (dead, 45 years)"])
            self.assertEqual([i.location for i in items][-1], "Bodies awaiting burial")
            golden = r.plan_saved(folder, 1, "2")
            self.assertTrue(all(d.file.startswith(("male_", "peep")) for d in golden))
            dead = r.plan_saved(folder, 1, "4")
            self.assertEqual([(d.file, d.rect) for d in dead], [("skelly.png", (120, 0, 180, 65))])
            # no Head Looks file and no Grey Hair data: Bem is grey (the patch's own rule, Auto) from 55
            elder = r.plan_saved(folder, 1, "1", pose="walk")
            self.assertIn("vvfp_grey_female_heads.png", [d.file for d in elder])
            stock = r.plan_saved(folder, 1, "1", pose="walk", grey_hair=False)
            self.assertIn("female_heads.png", [d.file for d in stock])
            self.assertIn("grey_hair", [f.key for f in r.saved_fields()])


@unittest.skipUnless(ART.is_dir(), "a copy of A New Home's Images folder in research/game-images is needed")
class TheArt(unittest.TestCase):
    def test_every_required_file_is_the_games_and_its_size(self) -> None:
        for name in vv1.required_files():
            data = (ART / name).read_bytes()
            self.assertEqual(struct.unpack(">II", data[16:24]), SIZES[name], name)
        for name, path in vv1.patcher_art().items():
            data = path.read_bytes()
            self.assertEqual(struct.unpack(">II", data[16:24]), SIZES[name], name)

    def test_pictures_draw(self) -> None:
        r = vv1.load(ART.parent)
        for spec in ({"stage": ("adult", 600), "head": 3, "body": 7, "mask": 4, "look": 0},
                     {"stage": ("child", 60), "sex": False, "head": 9, "body": 2},
                     {"stage": ("golden", 100), "head": 19, "pose": "golden_act", "frame": 5},
                     {"stage": ("dead", 0), "bones": 3},
                     {"stage": ("elder", 1100), "look": 0, "pose": "swim", "head": 6}):
            image = r.render_custom(spec)
            self.assertIsNotNone(image.bbox(), spec)
            self.assertGreater(image.width, 30)


if __name__ == "__main__":
    unittest.main()
