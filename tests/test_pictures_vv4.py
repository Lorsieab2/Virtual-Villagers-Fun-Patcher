"""Picture Studio, The Tree of Life: the drawing rules in src/vv_pictures_vv4.py, proven against the game's own code.

* The animation tables: the game's loader 0x44DE60 runs in Unicorn on the vanilla executable, reading the game's
  own Assets\\animpts.dat and anims.dat; every sprite, frame and anchor the renderers read from its table at
  0x4E00E0 must be vv_pictures_vv4.Tables'.
* The village figure: the game's live renderer 0x467DA0 runs on a villager record for many states -- sexes,
  child ages and adults, the old head, every pose (steps x directions, the 17 actions, the big body), head
  columns, heads and bodies (the chief's outfit 29 too), bodies awaiting burial, ghosts, villagers picked up,
  standing in water, carried items and litters -- down to its blits (0x404CB0); every blit (sheet, cell, place,
  scale, surface alpha) must be the plan's, in order.
* The patcher's Origins mask: the same, on the executable with the Origins mask bytes the patcher writes
  (data/vv4_origins_feature.json: the world cave at 0x728EB0, its lift table, the resolve cave, the call at
  0x468263), with the companion DLL's two exports answered here.
* The Villager Details figure: the game's 0x45F550, the same way.
* The blitter: the game's 0x404CB0 on real pixels against vv_picture_image.blit_piece (scaled down, faded).
* Without the emulator: the tables from a made-up file, the plans on blank sheets of the real sizes, and the
  save reader on a made-up save (never the owner's).

The emulated checks need the vanilla executable (research/stock-executables), the game's pictures and Assets
(research/game-images/Virtual Villagers - The Tree of Life) and Unicorn; they skip without (CI).
"""
from __future__ import annotations

import json
import struct
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_picture_image as pi  # noqa: E402
import vv_pictures_common as common  # noqa: E402
import vv_pictures_vv4 as p4  # noqa: E402

STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"
ART = ROOT / "research" / "game-images" / "Virtual Villagers - The Tree of Life"
MANIFEST = ROOT / "data" / "vv4_origins_feature.json"

try:
    import pefile  # noqa: F401
    from unicorn.x86_const import UC_X86_REG_FPCW
    from story_emulator import API_STUBS, Process
    HAVE_EMULATOR = True
except ImportError:                     # CI: no Unicorn
    HAVE_EMULATOR = False

EMULATED = HAVE_EMULATOR and STOCK.is_file() and (ART / "Images").is_dir() and (ART / "Assets" / "animpts.dat").is_file()
HAVE_ART = (ART / "Images").is_dir() and (ART / "Assets" / "animpts.dat").is_file()

DRAW = 0x4DB9F8          # the world draw manager (camera)
ANIM = 0x4E00E0          # the animation tables
MGR = 0x50E568           # the villager manager: records at +0x44, 0x2E3C each
STRIDE = 0x2E3C
SPRITES = 0x4C07CC       # the sprite table
MASK_PATCHES = (32, 34, 35, 37, 38, 39, 40)   # resolve cave, Details cave + tables + call, world cave + lifts + call
BIGHEAD_SLOT = 0x728A3C
MASK_SLOT_ATLAS = 0x728D70


def f32bits(v: float) -> int:
    return struct.unpack("<I", struct.pack("<f", v))[0]


def _s32(v: int) -> int:
    return v - (1 << 32) if v & 0x80000000 else v


def art_size(name: str) -> tuple[int, int]:
    patcher = p4.patcher_art().get(name)
    if patcher is not None:
        data = patcher.read_bytes()[:24]
    else:
        data = pi.FolderSource(ART).read(name)[:24]
    return struct.unpack(">II", data[16:24])


class TreeOfLife:
    """The vanilla executable in Unicorn with the game's own sprite setup (0x465F70), camera (0x44C3E0) and
    animation tables (0x44DE60, reading the game's Assets), every blit recorded."""

    def __init__(self, masks: bool = False) -> None:
        exe = bytearray(STOCK.read_bytes())
        if masks:
            patches = json.loads(MANIFEST.read_text(encoding="utf-8"))["patches"]
            for k in MASK_PATCHES:
                entry = patches[k]
                at = int(entry["offset"], 16)
                before, after = bytes.fromhex(entry["before"]), bytes.fromhex(entry["after"])
                assert bytes(exe[at:at + len(before)]) == before, entry["purpose"]
                exe[at:at + len(after)] = after
        self.p = p = Process(bytes(exe))
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
        self.surfaces: dict[int, str] = {}
        self.objects: dict = {}
        self.blits: list = []
        self.registry = p.alloc(0x40)
        p.stub(0x44CCF0, lambda q: (self.registry, 0))                 # the sprite registry
        p.stub(0x44CB70, lambda q: (self.sprite(q.arg(0)), 4))         # registry: sprite by id
        p.stub(0x44CD90, lambda q: (self.sprite(q.arg(0)), 4))
        p.stub(0x404CB0, self._blit)                                   # the blitter: recorded
        p.stub(0x4036D0, lambda q: (99, 0))                            # rand(n): no splash, no portrait turn
        self.ripple = 0
        p.stub(0x41FE70, lambda q: (self.registry, 0))
        p.stub(0x403750, lambda q: (self.ripple, 0))                   # the ripple's random cell
        self.gfx = p.alloc(0x100)
        self.wrap = p.alloc(0x10)
        p.put32(self.wrap, self.gfx)
        p.put32(0x4CB928, self.wrap)
        p.write(self.gfx + 0x60, struct.pack("<iiii", -100000, -100000, 100000, 100000))
        self.call(0x44C3E0, [0, 0, f32bits(1.0)], ecx=DRAW)            # camera: no scroll, zoom 1
        self.call(0x465F70, [], ecx=MGR)                               # the manager's sprites
        p.put32(MGR + 0x38, self.wrap)                                 # the ripple's draw target
        self.files: dict = {}
        resolver, vtable, code = p.alloc(0x40), p.alloc(0x40), p.alloc(0x10)
        p.write(code, b"\xC3")
        p.put32(resolver, vtable)
        p.put32(vtable + 8, code)
        p.put32(0x4CB51C, resolver)
        p.stub(code, lambda q: (self._string(q.cstring(q.arg(0))), 4))
        p.stub(0x471ECC, self._fopen)
        p.stub(0x472287, self._fread)
        p.stub(0x471D8C, lambda q: (0, 0))
        self.call(0x44DE60, [], ecx=ANIM)
        self.mask = 0
        if masks:
            getter, cache = p.alloc(0x10), p.alloc(0x10)
            p.write(getter, b"\xC3")
            p.write(cache, b"\xC3")
            p.stub(getter, lambda q: (self.mask, 4))                   # Vv4MaskGetForRecord(record)
            p.stub(cache, lambda q: (0, 4))
            p.api_handlers["LoadLibraryA"] = lambda q: (0x5000, 4)
            p.api_handlers["GetProcAddress"] = lambda q: ({110: cache, 114: getter}[q.arg(1)], 8)
            p.put32(MASK_SLOT_ATLAS, self.atlas([p4.MASK_FILE], 8, 5, 1, 1))
            p.put32(BIGHEAD_SLOT, self.atlas([p4.BIG_MASK_FILE], 3, 5, 1, 1))

    def call(self, addr: int, args, ecx=None):
        self.p.mu.reg_write(UC_X86_REG_FPCW, 0x027F)          # Windows runs the x87 at 53 bits
        return self.p.call(addr, list(args), ecx=ecx, limit=5_000_000)

    def _string(self, text: str) -> int:
        at = self.p.alloc(0x100)
        self.p.write(at, text.encode() + b"\0")
        return at

    def _fopen(self, q):
        path = ART / "Assets" / q.cstring(q.arg(0))
        if not path.is_file():
            return 0, 0
        handle = 0x7000 + 4 * len(self.files)
        self.files[handle] = [path.read_bytes(), 0]
        return handle, 0

    def _fread(self, q):
        buf, size, count, handle = (q.arg(i) for i in range(4))
        data, at = self.files[handle]
        chunk = data[at:at + size * count]
        self.files[handle][1] += len(chunk)
        q.write(buf, chunk)
        return (len(chunk) // size if size else 0), 0

    def atlas(self, files, cols, rows, across, down) -> int:
        """A sprite object as the engine's grid constructor lays it out (the same fields as A New Home's
        0x40A0F0; read by 0x40A990, 0x421570, 0x40A940 / 0x40A950)."""
        p = self.p
        sheets = []
        for name in files:
            w, h = art_size(name)
            surface = p.alloc(0x40)
            p.put32(surface + 8, w)
            p.put32(surface + 12, h)
            sheet = p.alloc(8)
            p.put32(sheet, surface)
            self.surfaces[surface] = name
            sheets.append((sheet, w, h))
        obj = p.alloc(0x70)
        if (across, down) != (0, 0):
            sum_w = sum(sheets[(down - 1) * across + x][1] for x in range(across))
            sum_h = sum(sheets[y * across + across - 1][2] for y in range(down))
            cw, ch = sum_w // cols, sum_h // rows
            table = p.alloc(4 * len(sheets))
            for k, s in enumerate(sheets):
                p.put32(table + 4 * k, s[0])
            p.write(obj + 4, struct.pack("<12I", sheets[0][0], cols, rows, cw, ch, sheets[0][1], sheets[0][2],
                                         across, down, sheets[0][1] // cw, sheets[0][2] // ch, table))
        else:
            c, r = max(cols, 1), max(rows, 1)
            w, h = sheets[0][1], sheets[0][2]
            p.write(obj + 4, struct.pack("<12I", sheets[0][0], c, r, w // c, h // r, w, h, 0, 0, 0, 0, 0))
        return obj

    def table_entry(self, sid: int):
        w = struct.unpack("<12I", self.p.read(SPRITES + sid * 0x30, 0x30))
        return self.p.cstring(w[0]), w[1], w[2], (self.p.cstring(w[3]) if w[3] else ""), w[4], w[5]

    def sprite(self, sid: int) -> int:
        if sid not in self.objects:
            name, cols, rows, suffix, across, down = self.table_entry(sid)
            if across or down:
                files = [f"{name}{x}{y}{suffix}" for y in range(down) for x in range(across)]
            else:
                files = [name]
            try:
                self.objects[sid] = self.atlas(files, cols, rows, across, down)
            except (OSError, TypeError):
                self.objects[sid] = self.p.alloc(0x70)      # a sprite the villagers never draw
        return self.objects[sid]

    def _blit(self, q):
        a = [q.arg(i) for i in range(10)]
        f = lambda v: struct.unpack("<f", struct.pack("<I", v))[0]  # noqa: E731
        self.blits.append((self.surfaces.get(a[0], hex(a[0])).casefold(),
                           (_s32(a[3]), _s32(a[4]), _s32(a[5]), _s32(a[6])), _s32(a[1]), _s32(a[2]),
                           round(f(a[8]), 6), pi.surface_alpha(f(a[7])), a[9]))
        return 0, 0x28

    def record(self, i: int = 0) -> int:
        return MGR + 0x44 + i * STRIDE

    def set_villager(self, look: p4.Look, pose: p4.Pose, x: int = 400, y: int = 300) -> int:
        p = self.p
        r = self.record()
        p.write(r, bytes(STRIDE))
        for off, val in ((0x1B8C, look.age), (0x1B90, 1 if look.female else 0), (0x1B94, look.dead_frame),
                         (0x1BB8, look.head), (0x1BBC, look.body), (0x1C40, look.health), (0x1C94, x),
                         (0x1C98, y), (0x1CB0, pose.pose), (0x1CD0, pose.direction), (0x1CD4, pose.head_column),
                         (0x1CDC, look.item), (0x1C50, look.litter), (0x1C4C, 1 if look.expecting else 0),
                         (0x2E38, pose.portrait_facing)):
            p.put32(r + off, val)
        p.write(r + 0x1CC5, bytes([1 if pose.held else 0]))
        if look.ghost:
            p.write(r + 0x1CC7, b"\x01")
            p.write(r + 0x1CCC, struct.pack("<f", p4.GHOST_ALPHA))
        p.put32(r + 0x2E2C, self.wrap)            # the Details figure's draw target
        self.mask = look.mask
        self.ripple = pose.ripple
        return r

    def village(self, look: p4.Look, pose: p4.Pose) -> list:
        self.set_villager(look, pose)
        self.blits = []
        water = pose.water
        self.p.stub(0x46FE80, lambda q: (1 if water else 0, 8))       # a terrain at the feet ...
        self.p.stub(0x46C3D0, lambda q: (5 if water else 0, 8))       # ... 5: water
        self.p.stub(0x45DD10, lambda q: (0, 0))                        # not selected
        self.call(0x467DA0, [0, f32bits(1.0)], ecx=MGR)                # the draw queue passes 1.0 (0x44C4B3)
        return [b[:6] for b in self.blits]

    def details(self, look: p4.Look, pose: p4.Pose, px: int = 400, py: int = 300) -> list:
        self.set_villager(look, pose)
        self.blits = []
        self.call(0x45F550, [px, py], ecx=self.record())
        return [b[:6] for b in self.blits]


def keys(plan) -> list:
    return [d.key() for d in plan]


_GAMES: dict = {}


def emulated_game(masks: bool = False) -> TreeOfLife:
    """One emulated game per kind for the whole file (each holds a Unicorn engine)."""
    if masks not in _GAMES:
        _GAMES[masks] = TreeOfLife(masks=masks)
    return _GAMES[masks]


class _Emulated(unittest.TestCase):
    game: TreeOfLife = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.game = emulated_game()
        cls.renderer = p4.load(pi.FolderSource(ART))
        cls.tables = cls.renderer.tables()

    def plan(self, look, pose):
        return keys(p4.plan_village(self.renderer.sheets, self.tables, look, pose))

    def check(self, look, pose):
        self.assertEqual(self.plan(look, pose), self.game.village(look, pose), (look, pose))


@unittest.skipUnless(EMULATED, "the vanilla The Tree of Life, its pictures and Assets, and Unicorn are needed")
class TablesMatchTheGame(_Emulated):
    def test_every_entry_the_renderers_read(self) -> None:
        mem = self.game.p
        for (k, female), entry in self.tables.body.items():
            at = ANIM + 0x7258 + k * 0x7A4 + (2 * int(female)) * 0x1E8
            sprite, frame = struct.unpack("<2i", mem.read(at, 8))
            first = tuple(struct.unpack_from("<2i", mem.read(at + 8, 240), 8 * j) for j in range(30))
            second = tuple(struct.unpack_from("<2i", mem.read(at + 0xF8, 240), 8 * j) for j in range(30))
            self.assertEqual((sprite, frame, first, second), (entry.sprite, entry.frame, entry.first, entry.second),
                             (k, female))
        for (col, female), entry in self.tables.head.items():
            at = ANIM + 0x1F05C + (int(female) * 11 + col) * 0x1E8
            sprite, frame = struct.unpack("<2i", mem.read(at, 8))
            second = tuple(struct.unpack_from("<2i", mem.read(at + 0xF8, 240), 8 * j) for j in range(30))
            self.assertEqual((sprite, frame, second), (entry.sprite, entry.frame, entry.second), (col, female))

    def test_sprite_table_is_the_games(self) -> None:
        for sid, atlas in p4.SPRITES.items():
            name, cols, rows, suffix, across, down = self.game.table_entry(sid)
            if across or down:
                self.assertEqual((atlas.name, atlas.cols, atlas.rows, tuple(atlas.sheets), atlas.suffix),
                                 (name, cols, rows, (across, down), suffix), sid)
            else:
                self.assertEqual((atlas.name, atlas.cols, atlas.rows), (name, max(cols, 1), max(rows, 1)), sid)


@unittest.skipUnless(EMULATED, "the vanilla The Tree of Life, its pictures and Assets, and Unicorn are needed")
class VillageMatchesTheGame(_Emulated):
    def test_ages_sexes_poses_heads_and_bodies(self) -> None:
        n = 0
        for female in (False, True):
            for age in (0, 1, 20, 100, 139, 200, 279, 280, 600, 1099, 1100, 1700):
                for body, head in ((0, 0), (7, 13), (29, 29), (14, 3)):
                    for pose_no, direction in ((0, 0), (3, 1), (7, 2), (5, 3), (12, 0), (33, 1), (48, 2), (49, 3)):
                        for column in (0, 5, 7):
                            self.check(p4.Look(female=female, age=age, head=head, body=body, old=age >= 1100),
                                       p4.Pose(pose=pose_no, direction=direction, head_column=column))
                            n += 1
        self.assertEqual(n, 2 * 12 * 4 * 8 * 3)

    def test_every_pose_direction_and_head_column(self) -> None:
        for pose_no in range(50):
            for direction in range(4):
                self.check(p4.Look(age=600, head=9, body=11), p4.Pose(pose=pose_no, direction=direction,
                                                                       head_column=pose_no % 8))
        for column in range(8):
            for female in (False, True):
                self.check(p4.Look(female=female, age=1400, head=4, body=2, old=True), p4.Pose(head_column=column))

    def test_every_head_and_body(self) -> None:
        for female in (False, True):
            for value in range(30):
                self.check(p4.Look(female=female, age=600, head=value, body=value), p4.Pose(pose=2, direction=1))
                self.check(p4.Look(female=female, age=150, head=29 - value, body=value), p4.Pose(pose=35))

    def test_bodies_awaiting_burial(self) -> None:
        for frame in (0, 1, 2, 3, 6, 1101, -1, -6):
            for age in (0, 150, 280, 1500):
                self.check(p4.Look(age=age, health=0, dead_frame=frame), p4.Pose())
                self.check(p4.Look(age=age, health=-40, dead_frame=frame, female=True), p4.Pose(pose=33))

    def test_ghosts(self) -> None:
        for age in (100, 600, 1300):
            for pose_no in (0, 6, 40):
                self.check(p4.Look(age=age, head=5, body=6, ghost=True, old=age >= 1100), p4.Pose(pose=pose_no))

    def test_picked_up_and_in_water(self) -> None:
        for age in (40, 600):
            for direction in range(4):
                self.check(p4.Look(age=age, head=1, body=2), p4.Pose(pose=4, direction=direction, held=True))
                for ripple in range(4):
                    self.check(p4.Look(age=age, head=1, body=2),
                               p4.Pose(pose=4, direction=direction, water=True, ripple=ripple))
                self.check(p4.Look(age=age, head=1, body=2), p4.Pose(pose=0x29 - direction * 8, direction=direction,
                                                                     water=True))

    def test_carried_items_and_litters(self) -> None:
        for item in (0, 3, 17, 69, 0x46, 0x46 + 30, 0x46 + 53):
            for litter in (1, 2, 3):
                for direction in range(4):
                    self.check(p4.Look(age=500, head=2, body=3, item=item, litter=litter),
                               p4.Pose(pose=1, direction=direction))
                self.check(p4.Look(age=120, head=2, body=3, item=item, litter=litter), p4.Pose(water=True))

    def test_every_carried_item(self) -> None:
        """Every item of vv_pictures_carried.VV4 (the patcher's Golden Mushroom included), in every direction,
        walking (with twins and triplets), in action poses, as a child and held up by the hand, is blitted by
        the game's own draw 0x467DA0 as the plan says.  The Golden Mushroom's stock blit (collectables frame
        50) is what the patched game's world draw 0x44C640 swaps (carried_golden)."""
        import carried_golden
        import vv_pictures_carried as carried
        golden = carried.GOLDEN_ITEM[p4.GAME]
        frame50 = p4._draw_frame(self.renderer.sheets, p4.COLLECTABLES, 0, 0, 50, 1.0, 1.0, "")
        n = 0
        for it in carried.items(p4.GAME):
            for direction in range(4):
                cases = [(p4.Look(age=500, head=2, body=3, item=it.value, litter=litter), p4.Pose(pose=1,
                                                                                               direction=direction))
                         for litter in (1, 2, 3)]
                cases += [(p4.Look(age=500, head=2, body=3, item=it.value), p4.Pose(pose=pose_no, direction=direction))
                          for pose_no in (33, 40, 48)]
                cases += [(p4.Look(age=120, female=True, head=5, body=6, item=it.value), p4.Pose(pose=6,
                                                                                              direction=direction)),
                          (p4.Look(age=600, head=5, body=6, item=it.value), p4.Pose(pose=4, direction=direction,
                                                                                    held=True))]
                for look, pose in cases:
                    stock = p4.plan_village(self.renderer.sheets, self.tables, look, pose, golden_art=False)
                    self.assertEqual(keys(stock), self.game.village(look, pose), (it.name, look, pose))
                    if it.value == golden:
                        self.assertEqual(keys(p4.plan_village(self.renderer.sheets, self.tables, look, pose)),
                                         carried_golden.swapped(stock, p4.GAME,
                                                                lambda d: (d.file, d.rect) == (frame50.file,
                                                                                               frame50.rect)))
                    n += 1
        self.assertEqual(n, len(carried.items(p4.GAME)) * 4 * 8)

    def test_shadow_left_out_is_the_shadow_draw_only(self) -> None:
        look, pose = p4.Look(age=300, head=6, body=8), p4.Pose(pose=3, direction=2)
        full = self.plan(look, pose)
        bare = self.plan(look, replace(pose, shadow=False))
        self.assertEqual(full[1:], bare)
        self.assertEqual(full[0][0], "peep_shadow1.png")


@unittest.skipUnless(EMULATED and MANIFEST.is_file(), "the vanilla The Tree of Life, its pictures and Assets, "
                                                      "and Unicorn are needed")
class MaskMatchesThePatcher(_Emulated):
    @classmethod
    def setUpClass(cls) -> None:
        cls.game = emulated_game(masks=True)
        cls.renderer = p4.load(pi.FolderSource(ART))
        cls.tables = cls.renderer.tables()

    def test_the_lift_table_is_the_patchers(self) -> None:
        self.assertEqual(self.game.p.read(0x728FC4, 5), bytes([p4.MASK_LIFT] * 5))

    def test_every_mask_at_every_size_and_facing(self) -> None:
        for mask in range(0, 6):
            for age in (0, 70, 200, 279, 600, 1300):
                for column in range(8):
                    for female in (False, True):
                        self.check(p4.Look(female=female, age=age, head=column * 3, body=5, mask=mask,
                                           old=age >= 1100), p4.Pose(pose=column % 8, direction=column % 4,
                                                                     head_column=column))
            self.check(p4.Look(age=600, head=4, body=4, mask=mask, item=3, litter=2), p4.Pose(direction=1))
            self.check(p4.Look(age=600, head=4, body=4, mask=mask), p4.Pose(water=True))
            self.check(p4.Look(age=600, head=4, body=4, mask=mask, ghost=True), p4.Pose(held=True))

    def test_details_masks(self) -> None:
        for mask in range(0, 6):
            for age in (0, 150, 279, 280, 900, 1500):
                for facing in (0, 1, 2, 3, 7):
                    for female in (False, True):
                        look = p4.Look(female=female, age=age, head=8, body=12, mask=mask, old=age >= 1100,
                                       expecting=female and age > 300, litter=2)
                        pose = p4.Pose(view="details", portrait_facing=facing)
                        plan = keys(p4.plan_details(self.renderer.sheets, self.tables, look, pose))
                        self.assertEqual(plan, self.game.details(look, pose), (look, pose))

    def test_the_details_tables_are_the_patchers(self) -> None:
        raw = self.game.p.read(0x728A40, 16)
        self.assertEqual(tuple(raw[0:3]), p4.BIG_MASK_FACE)
        self.assertEqual(tuple(struct.unpack("3b", raw[8:11])), p4.BIG_MASK_DX)
        self.assertEqual(tuple(raw[11:16]), p4.BIG_MASK_DY)


@unittest.skipUnless(EMULATED, "the vanilla The Tree of Life, its pictures and Assets, and Unicorn are needed")
class DetailsMatchesTheGame(_Emulated):
    def check_details(self, look, pose):
        plan = keys(p4.plan_details(self.renderer.sheets, self.tables, look, pose))
        self.assertEqual(plan, self.game.details(look, pose), (look, pose))

    def test_portraits(self) -> None:
        for female in (False, True):
            for age in (0, 60, 279, 280, 900, 1100, 1900):
                for facing in (0, 1, 2, 4, 5):
                    for head, body in ((0, 0), (12, 29), (29, 17)):
                        self.check_details(p4.Look(female=female, age=age, head=head, body=body, old=age >= 1100),
                                           p4.Pose(view="details", portrait_facing=facing))

    def test_expecting_mothers_hold_their_babies(self) -> None:
        for litter in (1, 2, 3):
            for age in (300, 800):
                self.check_details(p4.Look(female=True, age=age, head=5, body=9, expecting=True, litter=litter),
                                   p4.Pose(view="details", portrait_facing=1))

    def test_every_head_and_body(self) -> None:
        for value in range(30):
            self.check_details(p4.Look(age=700, head=value, body=29 - value), p4.Pose(view="details"))


@unittest.skipUnless(EMULATED, "the vanilla The Tree of Life and Unicorn are needed")
class BlitterMatchesTheGame(unittest.TestCase):
    """The game's own blitter 0x404CB0 on a test picture: scaled down (children) and faded (ghosts at 0.6,
    the ripple at 0.4) must give what vv_picture_image.blit_piece and the surface alpha give."""

    @staticmethod
    def pattern(w: int, h: int) -> bytes:
        return b"".join(bytes(((x * 37 + y * 11) % 256, (x * 5 + y * 13) % 256, (x * y) % 256,
                               (0 if (x + y) % 7 == 0 else 255 if (x * y) % 3 else (x * 29 + y * 3) % 256)))
                        for y in range(h) for x in range(w))

    @classmethod
    def setUpClass(cls) -> None:
        self = cls
        self.p = p = Process(STOCK.read_bytes())
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

    @classmethod
    def surface(self, w: int, h: int, amask: int) -> int:
        p = self.p
        fmt = p.alloc(0x40)
        p.put32(fmt, 0x16362004 if amask else 0x16161804)
        p.write(fmt + 8, bytes((32, 4)))
        p.write(fmt + 12, struct.pack("<4I", 0x00FF0000, 0x0000FF00, 0x000000FF, amask))
        p.write(fmt + 28, bytes((0, 0, 0, 0 if amask else 8, 16, 8, 0, 24 if amask else 0)))
        s = p.alloc(0x40)
        pixels = p.alloc(w * h * 4 + 16)
        p.write(s + 4, struct.pack("<5I", fmt, w, h, w * 4, pixels))
        p.write(s + 36, struct.pack("<iiii", 0, 0, w, h))
        return s

    def screen_rgb(self):
        raw = self.p.read(self.p.u32(self.screen + 20), self.sw * self.sh * 4)
        return [(raw[i + 2], raw[i + 1], raw[i]) for i in range(0, len(raw), 4)]

    def expected(self, piece: pi.Image, x: int, y: int, bg, alpha: int):
        out = [bg] * (self.sw * self.sh)
        for j in range(piece.height):
            for i in range(piece.width):
                r, g, b, a = piece.pixel(i, j)
                if alpha < 255:
                    a = (a * alpha + 127) >> 8
                if a == 0:
                    continue
                d = out[(y + j) * self.sw + x + i]
                out[(y + j) * self.sw + x + i] = tuple((s * a + v * (255 - a) + 0x7F) >> 8 for s, v in zip((r, g, b), d))
        return out

    def test_scaled_and_faded(self) -> None:
        w, h = 88, 70
        rgba = self.pattern(w, h)
        sheet = pi.Image(w, h, rgba)
        src = self.surface(w, h, 0xFF000000)
        argb = bytearray(len(rgba))
        argb[0::4], argb[1::4], argb[2::4], argb[3::4] = rgba[2::4], rgba[1::4], rgba[0::4], rgba[3::4]
        self.p.write(self.p.u32(src + 20), bytes(argb))
        for pct in (50, 57, 64, 71, 80, 87, 93, 99):
            for alpha in (1.0, p4.GHOST_ALPHA):
                for rect in ((0, 0, 40, 65), (40, 0, 80, 65), (3, 2, 43, 67)):
                    self.p.write(self.p.u32(self.screen + 20), bytes((30, 200, 10, 0)) * (self.sw * self.sh))
                    scale = p4.blit_scale(pct)
                    self.p.mu.reg_write(UC_X86_REG_FPCW, 0x027F)
                    self.p.call(0x404CB0, [src, 20, 9, *rect, f32bits(alpha), f32bits(scale), 0], ecx=self.gfx)
                    piece = pi.blit_piece(sheet, rect, scale)
                    want = self.expected(piece, 20, 9, (10, 200, 30), pi.surface_alpha(alpha))
                    self.assertEqual(self.screen_rgb(), want, (pct, alpha, rect))


# ------------------------------------------------------------------------------------------- no emulator

SIZES = {"carrying.png": (520, 240), "collectables_small.png": (240, 360), "peep_shadow1.png": (68, 64),
         "skelly.png": (240, 65), "ripple.png": (260, 65), "bigbodies.png": (160, 3900),
         "bigheads00.png": (480, 3000), "bigheads10.png": (480, 3000), p4.MASK_FILE: (520, 725)}
for _sex in ("male", "female"):
    SIZES.update({f"{_sex}_heads00.png": (320, 1950), f"{_sex}_heads10.png": (320, 1950)})
    for _x in range(2):
        for _y in range(3):
            SIZES[f"{_sex}_bodies{_x}{_y}.png"] = (640, 650)
    for _y in range(3):
        SIZES[f"{_sex}_actions0{_y}.png"] = (680, 650)


def made_up_animpts() -> bytes:
    """A file of the game's shape: pose k's body anchor for body b is (k + b, 50 + b), head anchor (1, -10 - b);
    the head offset for head h is (h - 3, 40 + h % 5)."""
    body = bytearray(50 * 0x7A4)            # the blob lands at +0x7254: pose k, part s at blob + 4 + ...
    for k in range(50):
        for part in range(4):
            at = 4 + k * 0x7A4 + part * 0x1E8
            for b in range(30):
                if at + 8 + 8 * b + 8 <= len(body):
                    struct.pack_into("<2i", body, at + 8 + 8 * b, 1, -10 - b)
                if at + 0xF8 + 8 * b + 8 <= len(body):
                    struct.pack_into("<2i", body, at + 0xF8 + 8 * b, k + b, 50 + b)
    body = bytes(body)
    head = bytearray(22 * 0x1E8)
    for e in range(22):
        for h in range(30):
            struct.pack_into("<2i", head, e * 0x1E8 + 0xF8 + 8 * h, h - 3, 40 + h % 5)
    return struct.pack("<I", len(body)) + body + struct.pack("<I", len(head)) + bytes(head)


class BlankGame:
    """Blank sheets of the real sizes, and a made-up animpts.dat."""
    problem = ""
    copy = None

    def read(self, name: str):
        if name.replace("\\", "/").casefold() == "assets/animpts.dat":
            return made_up_animpts()
        size = SIZES.get(name.casefold())
        if size is None:
            return None
        return pi.Image(*size).to_png() if size[0] * size[1] < 400000 else _header_only(size)


def _header_only(size) -> bytes:
    """A PNG whose header gives the size (the plans read sizes only)."""
    return pi.Image(1, 1).to_png()[:16] + struct.pack(">II", *size) + pi.Image(1, 1).to_png()[24:]


class PlansWithoutTheGame(unittest.TestCase):
    def setUp(self) -> None:
        self.r = p4.load(BlankGame())

    def test_required_files_and_patcher_art(self) -> None:
        files = p4.required_files()
        for name in ("male_heads00.png", "female_heads10.png", "male_bodies12.png", "female_actions02.png",
                     "bigheads10.png", "bigbodies.png", "peep_shadow1.png", "skelly.png", "ripple.png",
                     "carrying.png", "collectables_small.png"):
            self.assertIn(name, files)
        self.assertNotIn(p4.MASK_FILE, files)
        self.assertTrue(p4.patcher_art()[p4.MASK_FILE].is_file())

    def test_tables_from_the_file(self) -> None:
        t = self.r.tables()
        self.assertEqual((t.body[(3, False)].sprite, t.body[(3, False)].frame), (280, 3))
        self.assertEqual((t.body[(40, True)].sprite, t.body[(40, True)].frame), (278, 8))
        self.assertEqual((t.body[(49, True)].sprite, t.body[(49, True)].frame), (283, 1))
        self.assertEqual((t.head[(9, True)].sprite, t.head[(9, True)].frame), (282, 4))
        self.assertEqual(t.body[(7, False)].second[2], (9, 52))
        self.assertEqual(t.head[(5, False)].second[7], (4, 42))

    def test_an_adult_walking(self) -> None:
        plan = self.r.plan(p4.Look(head=7, body=2), p4.Pose(pose=3, direction=1, head_column=5))
        self.assertEqual([d.what for d in plan], ["shadow", "body", "head"])
        shadow, body, head = plan
        X, Y = 400 + 20, 300 + 55
        self.assertEqual((shadow.x, shadow.y), (X - 34, Y - 32))
        self.assertEqual((body.file, body.rect, body.x, body.y), ("male_bodies00.png", (440, 130, 480, 195),
                                                                  X - (11 + 2), Y - 52))
        self.assertEqual((head.file, head.rect, head.x, head.y), ("male_heads00.png", (200, 455, 240, 520),
                                                                  X - 13 + 1 - 4, Y - 52 - 11 - 42))
        # the head anchor (1, -12) rounds as the game's does: trunc(-12 + 0.5) = -11

    def test_a_child_is_smaller_and_old_heads_are_the_second_sheet(self) -> None:
        child = self.r.plan(p4.Look(age=70, head=1, body=1), p4.Pose())
        self.assertEqual(child[1].scale, p4.blit_scale(60))
        self.assertEqual(child[2].scale, p4.blit_scale(85))
        old = self.r.plan(p4.Look(age=1200, head=1, body=1, old=True), p4.Pose(head_column=2))
        self.assertEqual((old[2].file, old[2].rect[0]), ("male_heads10.png", 80))

    def test_dead_ghost_mask_and_details(self) -> None:
        dead = self.r.plan(p4.Look(health=0, dead_frame=5), p4.Pose())
        self.assertEqual([(d.file, d.rect) for d in dead], [("skelly.png", (60, 0, 120, 65))])
        ghost = self.r.plan(p4.Look(ghost=True), p4.Pose())
        self.assertTrue(all(d.alpha == p4.GHOST_ALPHA for d in ghost))
        masked = self.r.plan(p4.Look(mask=5, age=0), p4.Pose(head_column=6))
        self.assertEqual((masked[-1].file, masked[-1].rect), (p4.MASK_FILE, (390, 580, 455, 725)))
        self.assertEqual(masked[-1].y, masked[-2].y - round(34 * p4.head_scale(0)))
        details = self.r.plan(p4.Look(female=True, expecting=True, litter=3), p4.Pose(view="details"))
        self.assertEqual([d.what for d in details], ["body", "head", "baby", "baby", "baby"])
        with self.assertRaises(pi.PictureError):
            self.r.plan(p4.Look(health=0), p4.Pose(view="details"))

    def test_custom_choices_cover_every_head_body_and_stage(self) -> None:
        subject = self.r.custom_choices()[0]
        fields = {f.key: f for f in subject.fields}
        self.assertEqual([o.key for o in fields["head"].options], list(range(30)))
        self.assertEqual([o.key for o in fields["body"].options], list(range(30)))
        self.assertTrue(all(o.patcher for o in fields["mask"].options[1:]))
        stages = [o.key[0] for o in fields["life"].options]
        for stage in ("child", "adult", "elder", "ghost", "dead"):
            self.assertIn(stage, stages)
        for option in fields["pose"].options:
            spec = {f.key: f.default for f in subject.fields}
            spec["pose"] = option.key
            self.assertTrue(self.r.plan_custom(spec))
        spec = {f.key: f.default for f in subject.fields}
        spec.update(view="details", life=("elder", 1200), look=common.LOOK_YOUNG)
        head = [d for d in self.r.plan_custom(spec) if d.what == "head"][0]
        self.assertEqual(head.file, "bigheads00.png")

    def test_no_animpts_is_said_in_words(self) -> None:
        class NoAssets(BlankGame):
            def read(self, name):
                return None if "animpts" in name else super().read(name)
        with self.assertRaises(pi.PictureError):
            p4.load(NoAssets()).plan(p4.Look(), p4.Pose())


def made_up_save(people) -> bytes:
    """A save holding `people` (name, female, age, head, body, health, pregnant, litter, dead_frame) in The
    Tree of Life's entry layout (0x104 bytes, the name at +0x14), then an end-of-list entry."""
    lay = 0x104
    start = 24 + 0x400
    data = bytearray(b"ldwg" + bytes(start - 4) + bytes(lay * (len(people) + 2)))
    for k, (name, female, age, head, body, health, pregnant, litter, frame) in enumerate(people):
        p = start + k * lay + 0x14
        struct.pack_into("<I", data, p - 0x14, 1)
        data[p:p + len(name)] = name.encode()
        for off, val in ((-0x10, age), (-0x0C, 1 if female else 0), (-8, frame), (0x1C, head), (0x20, body),
                         (0xA4, health), (0xB0, pregnant), (0xB4, litter)):
            struct.pack_into("<i", data, p + off, val)
    return bytes(data)


class SaveReading(unittest.TestCase):
    def test_saved_villagers_and_bodies(self) -> None:
        import tempfile
        people = [("Tautai", True, 700, 4, 29, 90, 650, 2, 5), ("Palanke", False, 1200, 12, 16, 80, 0, 0, 1),
                  ("Kiri", False, 90, 0, 0, 30, 0, 0, 2), ("Moana", True, 900, 7, 3, 0, 0, 0, 7)]
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "Virtual Villagers - The Tree of Life1.ldw").write_bytes(made_up_save(people))
            r = p4.load(BlankGame())
            items = r.saved_items(folder, 1)
            self.assertEqual([i.label for i in items], ["Tautai (adult, 35 years)", "Palanke (elder, 60 years)",
                                                        "Kiri (child, 4 years)", "Moana (dead, 45 years)"])
            self.assertEqual([i.location for i in items], ["Villagers"] * 3 + ["Bodies awaiting burial"])
            self.assertIn("Tribal Chief", items[0].detail)
            v = r._person(folder, 1, items[0].id)
            look = r.look_of(v)
            self.assertEqual((look.female, look.head, look.body, look.expecting, look.litter, look.dead_frame),
                             (True, 4, 29, True, 2, 5))
            self.assertTrue(r.look_of(r._person(folder, 1, items[1].id)).old)
            dead = r.plan_saved(folder, 1, items[3].id)
            self.assertEqual([(d.file, d.rect) for d in dead], [("skelly.png", (180, 0, 240, 65))])
            details = r.plan_saved(folder, 1, items[0].id, view="details")
            self.assertEqual([d.what for d in details], ["body", "head", "baby", "baby"])


@unittest.skipUnless(HAVE_ART, "the game's pictures (research/game-images) are needed")
class PixelsFromTheGame(unittest.TestCase):
    def test_pictures_are_drawn(self) -> None:
        r = p4.load(pi.FolderSource(ART))
        for spec in ({}, {"life": ("child", 40), "head": 20, "body": 29, "mask": 3},
                     {"view": "details", "sex": True, "expecting": True, "litter": 2},
                     {"life": ("dead", 600)}, {"pose": ("water", 2)}, {"life": ("ghost", 600)}):
            full = {f.key: f.default for f in r.custom_choices()[0].fields}
            full.update(spec)
            image = r.render_custom(full)
            self.assertIsNotNone(image.bbox(), spec)


if __name__ == "__main__":
    unittest.main()
