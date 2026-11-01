"""Picture Studio's Everything tab, The Secret City: src/vv_assets_vv3.py proven against the stock executable.

The emulated checks run the game's own code in Unicorn (scripts/emu_vv3_assets.py: the resource table and its
getters, the sprite constructors, the camera, the cell cut and draw wrappers, the static constructors of the
village's objects) with only the picture loader (a surface of the stock size), operator new and the blitter
(recorded) replaced, and require every blit to equal the module's plan (vv_picture_image.Draw.key(), in order).

They need the stock executable in research/stock-executables (and Unicorn); the scan also needs capstone; the
picture checks the game's art in research/game-images.  Without them they skip, as on CI.
"""
from __future__ import annotations

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
import vv_assets_vv3 as v3  # noqa: E402

STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
ART = ROOT / "research" / "game-images" / "Virtual Villagers - The Secret City" / "Images"

try:
    import pefile  # noqa: F401
    import unicorn  # noqa: F401
    HAVE_UNICORN = True
except ImportError:
    HAVE_UNICORN = False
try:
    import capstone  # noqa: F401
    HAVE_CAPSTONE = True
except ImportError:
    HAVE_CAPSTONE = False

EMULATED = HAVE_UNICORN and STOCK.is_file()
WHY = "needs the stock The Secret City executable in research/stock-executables and Unicorn"


class _Sizes:
    """The stock sheets' sizes (planning without the art)."""

    def __init__(self, extra=None) -> None:
        self.sizes = {k.casefold(): v for k, v in {**v3.SIZES, **(extra or {})}.items()}

    def size(self, name: str):
        try:
            return self.sizes[name.casefold()]
        except KeyError:
            raise pi.PictureError(name) from None

    def has(self, name: str) -> bool:
        return name.casefold() in self.sizes


SHEETS = _Sizes()


def keys(plan) -> list:
    return [d.key() for d in plan]


# ------------------------------------------------------------------------------------------- pure logic

class PureLogic(unittest.TestCase):
    def test_sheet_table_covers_every_stock_file(self) -> None:
        covered = {n.casefold() for spec in v3.sheet_table() for n in spec.files()}
        for name in v3.SIZES:
            if name in v3.UNUSED_FILES:
                self.assertNotIn(name.casefold(), covered, name)
            else:
                self.assertIn(name.casefold(), covered, name)

    def test_table_shapes(self) -> None:
        self.assertEqual(len(v3.TABLE), 0xB4)
        self.assertEqual([e[0] for e in v3.TABLE], list(range(1, 0xB5)))
        self.assertEqual(v3.atlas_of(0x86), pi.Atlas("female_bodies", 32, 30, (2, 3)))
        self.assertEqual(v3.atlas_of(0x17), pi.Atlas("CheckboxStrip.png", 2, 1))
        self.assertEqual(v3.atlas_of(0x25), pi.Atlas("overview_bg.jpg", 1, 1))
        names = [s.name for s in v3.sheet_table()]
        self.assertEqual(names.count("firestrip.png"), 1)            # 0x6C and 0x82: the same sprite

    def test_meter_slices(self) -> None:
        self.assertEqual([v3.meter_slices(p) for p in (0, 6, 7, 50, 99, 100, 150, -3)], [0, 0, 1, 8, 15, 16, 16, 0])

    def test_assets_plan_from_sizes(self) -> None:
        extra = {"heathen_masks.png": (520, 725), "vvfp_hospitalFixed.png": (1071, 280),
                 "golden_mushroom.png": (29, 22)}
        got = v3.assets(_Sizes(extra))
        keys_ = [a.key for a in got]
        self.assertEqual(len(keys_), len(set(keys_)))
        cats = {a.category for a in got}
        for cat in (pa.TECH, pa.METERS, pa.SCREENS, pa.PANELS, pa.BUILDINGS, pa.PUZZLES, pa.CREATURES, pa.SCENE,
                    pa.EFFECTS, pa.VILLAGERS, pa.COLLECTIBLES, pa.PLANTS, pa.CURSORS, pa.FONTS, pa.PATCHER, pa.ICONS):
            self.assertIn(cat, cats, cat)
        for a in got:
            self.assertIn(a.category, pa.CATEGORIES)
            self.assertTrue(a.frames, a.key)
            if a.category == pa.PATCHER:
                self.assertTrue(a.patcher, a.key)

    def test_missing_files_are_skipped(self) -> None:
        empty = _Sizes()
        empty.sizes = {}
        self.assertEqual(v3.assets(empty), [])

    def test_patcher_art(self) -> None:
        art = v3.patcher_art()
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        for name, where in art.items():
            self.assertIsNotNone(pa.read_patcher_art(where), name)
            path = where[0] if isinstance(where, tuple) else where
            self.assertIn(f'"{path.relative_to(ROOT).as_posix()}"', release, name)


# ------------------------------------------------------------------------------------------- the emulator

def _emulator():
    import emu_vv3_assets as E
    e = E.Emulator(v3.SIZES)
    return e


@unittest.skipUnless(EMULATED, WHY)
class TableIsTheExes(unittest.TestCase):
    def test_resource_table(self) -> None:
        import pefile as pf
        pe = pf.PE(str(STOCK))
        image, base = pe.get_memory_mapped_image(), pe.OPTIONAL_HEADER.ImageBase

        def text(va):
            return image[va - base:va - base + 80].split(b"\0", 1)[0].decode("latin-1") if va else None
        got = []
        for i in range(0xB5):
            f = struct.unpack_from("<7I", image, 0x4A95A0 + i * 0x30 - base)
            self.assertEqual(f[0], i)
            if i == 0:
                self.assertEqual(text(f[1]), "No Graphic")
                continue
            got.append((f[0], text(f[1]), f[2], f[3], (f[5], f[6])))
            self.assertEqual(text(f[4]), ".png" if f[5] else None, hex(i))
        self.assertEqual(tuple(got), v3.TABLE)
        self.assertEqual(struct.unpack_from("<I", image, 0x42E6F8 + 2 - base)[0], 0xB5)   # cmp edx, 0xB5

    @unittest.skipUnless(HAVE_CAPSTONE, "needs capstone")
    def test_every_constructor_call_is_known(self) -> None:
        """A linear sweep of .text: every call of the whole / atlas / grid / strip constructors and the picture
        loader is the resource getter's, the engine's own, or one DIRECT names (with its own arguments)."""
        import disasm_vv3 as d
        engine = {0x401161, 0x4025E9, 0x40ADC0, 0x40AF32, 0x40B082, 0x42E7DA, 0x42E820, 0x42E97F, 0x42EB1B,
                  0x422F8F}
        direct = {}
        insns = d.all_insns()
        for i, ins in enumerate(insns):
            if ins.mnemonic in ("call", "jmp") and ins.op_str in ("0x40ad80", "0x40af10", "0x40af90", "0x401150",
                                                                  "0x40b3d0"):
                if ins.address in engine:
                    continue
                pushes = d.pushed_before(insns, i, 16)
                name = d.IMAGE[pushes[0] - d.BASE:pushes[0] - d.BASE + 40].split(b"\0", 1)[0].decode()
                if ins.op_str == "0x40af10":
                    direct[name] = (pushes[1], pushes[2])
                else:
                    direct[name] = (1, 1)
                direct[name] += (ins.address,)
        want = {n: (c, r) for n, c, r, _w in v3.DIRECT if not n.startswith("ldw")}
        self.assertEqual({n: v[:2] for n, v in direct.items()}, want)
        for n, c, r, where in v3.DIRECT:
            if not n.startswith("ldw"):
                self.assertEqual(int(where, 16), direct[n][2], n)
        # the fonts: their names (".png" added by 0x40256E) pushed for the font loader
        self.assertIn(b"ldwBurweed27\0", d.IMAGE[0x4807DC - d.BASE:0x4807DC - d.BASE + 13])
        self.assertIn(b"ldwarialbold\0", d.IMAGE[0x4807F4 - d.BASE:0x4807F4 - d.BASE + 13])
        self.assertEqual(d.IMAGE[0x47C4F0 - d.BASE:0x47C4F5 - d.BASE], b".png\0")
        self.assertEqual(d.IMAGE[0x47F538 - d.BASE:0x47F549 - d.BASE], b"%sX%01dY%01d.jpg\0")
        self.assertEqual(d.IMAGE[0x47E2C8 - d.BASE:0x47E2CC - d.BASE], b"Map\0")

    @unittest.skipUnless(HAVE_CAPSTONE, "needs capstone")
    def test_every_picture_name_in_the_exe_is_built(self) -> None:
        import disasm_vv3 as d
        built = {n.casefold() for s in v3.sheet_table() for n in s.files()}
        names = {m.group()[:-1].decode().lstrip("#=/@") for m in
                 re.finditer(rb"[A-Za-z0-9_ .\-#=/@]{3,}\.(?:png|jpg|PNG|JPG)\0", d.IMAGE)}
        names.discard("01d.jpg")                         # the tail of "%sX%01dY%01d.jpg"
        self.assertEqual({n for n in names if n.casefold() not in built}, set())
        for name in v3.UNUSED_FILES:
            self.assertNotIn(name.encode(), d.IMAGE)
            self.assertNotIn(name.casefold().encode(), d.IMAGE.lower())

    def test_map_tiles_are_the_loaders(self) -> None:
        e = _emulator()
        e.p.put32(0x4A4FDC, 0x47E2C8)                    # "Map" (the static pointer as the exe holds it)
        obj = e.p.alloc(0x400)
        e.loaded = []
        e.call(0x422F20, ecx=obj)
        got = []
        for x in range(4):
            for y in range(4):
                at = obj + 8 + 0x30 * x + 0xC * y
                got.append((e.loaded[4 * x + y], e.p.u32(at - 4), e.p.u32(at)))
                self.assertNotEqual(e.p.u32(at - 8), 0)
        self.assertEqual(got, list(v3.MAP_TILES))


@unittest.skipUnless(EMULATED, WHY)
class CellCutIsTheGames(unittest.TestCase):
    """0x42ECA0(id, frame, x, y, alpha, 100): every frame of every table sprite cut as pi.Atlas.cell cuts it."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.e = _emulator()
        cls.ui = cls.e.p.alloc(16)
        cls.e.p.put32(cls.ui, cls.e.resources)
        cls.e.p.put32(cls.ui + 4, cls.e.wrapper)

    def frame(self, rid, k, x=7, y=9):
        import emu_vv3_assets as E
        self.e.call(0x42ECA0, [rid, k, x, y, E.f32bits(1.0), 100], ecx=self.ui)
        return self.e.take()

    def test_every_frame(self) -> None:
        n = 0
        stock = {k.casefold() for k in v3.SIZES}
        for rid, name, cols, _rows, _s in v3.TABLE:
            a = v3.atlas_of(rid)
            if cols == 0 or not all(f.casefold() in stock for f in a.files()):
                continue                                  # whole pictures: the screens' test; no file: nothing
            for k in range(a.cols * a.rows):
                self.assertEqual(self.frame(rid, k), keys([v3._frame(SHEETS, a, k, 7, 9)]), f"{name} {k}")
                n += 1
        self.assertGreater(n, 4000)

    def test_buttons(self) -> None:
        for rid in v3.BUTTONS:
            a = v3.atlas_of(rid)
            for k in range(3):
                self.assertEqual(self.frame(rid, k, 0, 0), keys([v3._frame(SHEETS, a, k, 0, 0)]), hex(rid))

    def test_screens_and_their_calls(self) -> None:
        """Each screen picture: the call site pushes (id, x, y, 1.0, 100) and 0x42EB90 draws the plan."""
        if HAVE_CAPSTONE:
            import disasm_vv3 as d
            insns = d.all_insns()
            at = {ins.address: i for i, ins in enumerate(insns)}
        for site, rid, x, y, label in v3.SCREEN_DRAWS:
            if HAVE_CAPSTONE:
                i = at[site]
                self.assertEqual((insns[i].mnemonic, insns[i].op_str), ("call", "0x42eb90"), label)
                args = []
                for ins in reversed(insns[i - 12:i]):          # the five pushes nearest the call, last first
                    if ins.mnemonic == "push":
                        args.append(ins.op_str)
                    if len(args) == 5:
                        break
                zeroed = {ins.op_str.split(",")[0] for ins in insns[i - 40:i]
                          if ins.mnemonic == "xor" and ins.op_str.split(", ")[0] == ins.op_str.split(", ")[-1]}

                def value(op):
                    return 0 if op in zeroed else int(op, 0)
                self.assertEqual([value(a) for a in args], [rid, x, y, 0x3F800000, 100], label)
            self.assertEqual(self.e.draw_resource(rid, x, y), keys([v3.screen_draw(SHEETS, rid, x, y)]), label)


@unittest.skipUnless(EMULATED, WHY)
class TechScreenIsTheGames(unittest.TestCase):
    def test_tech_screen(self) -> None:
        import emu_vv3_assets as E
        e = _emulator()
        levels = [0] * 7
        e.p.stub(0x426FC0, lambda q: (levels[q.arg(0)] if q.arg(0) < 7 else 0, 4))   # the skill's level
        for a in (0x429A00, 0x42E2A0, 0x42E230):                                     # the screen's tail
            e.p.stub(a, lambda q: (0, 0))
        e.p.stub(0x40D1A0, lambda q: (0, 4))
        obj = e.p.alloc(0x200)
        for off in range(0x78, 0xD4, 4):
            e.p.put32(obj + off, E.f32bits(1.0))                                     # every piece faded in
        e.p.put32(obj + 0xD4, 0xFFFFFFFF)                                            # no skill selected
        import itertools
        n = 0
        for combo in itertools.product(range(4), repeat=2):
            for skill in range(7):
                levels[:] = [combo[0]] * 7
                levels[skill] = combo[1]
                e.call(0x4649C0, ecx=obj)
                self.assertEqual(e.take(), keys(v3.tech_screen(SHEETS, levels)), str(levels))
                n += 1
        self.assertEqual(n, 112)
        for skill in range(7):
            for level in range(4):
                plan = v3.tech_pieces(SHEETS, skill, level)
                box = v3.tech_bar_box(SHEETS, skill)
                for d in plan:                                     # every piece inside the bar's box
                    w, h = d.rect[2] - d.rect[0], d.rect[3] - d.rect[1]
                    self.assertTrue(box[0] <= d.x and d.x + w <= box[2] and box[1] <= d.y and d.y + h <= box[3])


@unittest.skipUnless(EMULATED, WHY)
class MetersAreTheGames(unittest.TestCase):
    def test_details_meters(self) -> None:
        e = _emulator()
        e.p.stub(0x428B60, lambda q: (0x1000, 0))
        e.call(0x42EEF0)
        meter = e.p.u32(0x592724)
        for m, _name, _y in v3.METERS:
            for p in list(range(-5, 106)):
                e.call(0x42EF60, [m, p & 0xFFFFFFFF], ecx=meter)
                self.assertEqual(e.take(), keys(v3.meter_plan(SHEETS, m, p)), f"{m} {p}")


class _Scene:
    """The village's objects, built by the C runtime's static constructors and their own sprite loaders."""

    _shared = None

    @classmethod
    def get(cls):
        if cls._shared is None:
            e = _emulator()
            e.p.api_handlers["GetSystemTimeAsFileTime"] = lambda q: (q.write(q.arg(0), bytes(8)), (0, 4))[1]
            e.p.api_handlers["GetPrivateProfileIntA"] = lambda q: (q.arg(2), 16)     # ldw.ini: its default
            for obj, ctor in e.STATIC_CTORS:
                try:
                    e.call(ctor, ecx=obj)
                except AssertionError:
                    pass                                     # three that need the OS (not drawn here)
            reg = struct.unpack("<26I", e.p.read(0x4B0D88, 104))
            for o in dict.fromkeys(reg):
                e.call(e.p.u32(e.p.u32(o) + 4), ecx=o)      # vtable +4: load its sprites
            e.take()
            cls._shared = (e, reg)
        return cls._shared


@unittest.skipUnless(EMULATED, WHY)
class SceneObjectsAreTheGames(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.e, cls.reg = _Scene.get()

    def draw(self, index: int, param: int) -> list:
        o = self.reg[index]
        self.e.call(self.e.p.u32(self.e.p.u32(o) + 0x18), [param | index], ecx=o)
        return self.e.take()

    def project(self, project: int, percent: int) -> None:
        """Set a project's progress (0x4358F0: count x 100 / needed, needed at 0x49D230)."""
        needed = struct.unpack("<i", self.e.p.read(0x49D230 + 4 * project, 4))[0]
        self.e.p.put32(0x594990 + 8 * project, percent * needed // 100)

    def test_huts(self) -> None:
        for hut in range(4):
            for stage in range(4):
                self.assertEqual(self.draw(HUT, ((stage + 2) << 24) | ((hut + 1) << 16)),
                                 keys(v3.hut_plan(SHEETS, hut, stage)), f"hut {hut} stage {stage}")
            for which in range(2):
                self.assertEqual(self.draw(HUT, (which << 24) | ((hut + 1) << 16)),
                                 keys(v3.hut_scaffold_plan(SHEETS, hut, which)), f"hut {hut} scaffold {which}")

    def test_hut_tables(self) -> None:
        p = self.e.p
        self.assertEqual(tuple(struct.unpack("<8i", p.read(0x4B09EC, 32))),
                         tuple(v for xy in v3.HUTS for v in xy))
        self.assertEqual(tuple(struct.unpack("<4i", p.read(0x4B09A4, 16))),
                         tuple(v for xy in v3.HUT_SCAFFOLD for v in xy))

    def test_statue(self) -> None:
        o = self.reg[8]
        for state, want in ((0, "statueFallen.png"), (1, "statueFallen.png"), (2, "statueErect.png"),
                            (3, "statueErect.png")):
            self.e.p.put32(o + 4, state)
            self.assertEqual(self.draw(8, 0x10000), keys([v3._whole(SHEETS, want, *v3.STATUE_AT)]))
        self.assertEqual(self.draw(8, 0x20000), keys([v3._whole(SHEETS, v3.SCAFFOLD, *v3.STATUE_SCAFFOLD)]))

    def test_rain_lift(self) -> None:
        o = self.reg[5]
        a = v3.atlas_of(0xAA)
        for k in range(8):
            self.e.p.put32(o + 0xC, k)
            self.assertEqual(self.draw(5, 0x10000), keys([v3._frame(SHEETS, a, k, *v3.RAINLIFT_AT)]))
        self.assertEqual(self.draw(5, 0x20000), keys([v3._whole(SHEETS, "RainLiftBroke.png", *v3.RAINLIFT_BROKE_AT)]))

    def test_rubble(self) -> None:
        for p in range(0, 101):
            self.project(6, p)
            self.assertEqual(self.draw(6, 0x10000), keys(v3.rubble_plan(SHEETS, p)), p)
        for k in range(2):
            self.assertEqual(self.draw(6, (k + 2) << 16), keys([v3._whole(SHEETS, v3.SCAFFOLD, *v3.RUBBLE_SCAFFOLD[k])]))

    def test_bushes(self) -> None:
        for p in range(0, 101):
            self.project(3, p)
            self.assertEqual(self.draw(3, 0x10000), keys(v3.roster_plan(SHEETS, p)), p)

    def test_alchemy_spots(self) -> None:
        o = self.reg[2]
        for hidden in range(6):
            for k in range(5):
                self.e.p.put32(o + 0xC + 0x10 * k, 1 if k == hidden else 0)
            want = [v3._whole(SHEETS, f"AlchemyLab{k}.png", *v3.ALCHEMY_SPOTS[k]) for k in range(5) if k != hidden]
            self.assertEqual(self.draw(2, 0), keys(want), hidden)

    def test_plans(self) -> None:
        import emu_vv3_assets as E
        o = self.reg[18]
        self.e.p.put32(o + 8, E.f32bits(1.0))
        self.assertEqual(self.draw(18, 0x10000), keys([v3._whole(SHEETS, "bath_plans.png", *v3.PLANS_AT)]))
        self.assertEqual(self.draw(18, 0x20000), keys([v3._whole(SHEETS, "statue_plans.png", *v3.PLANS_AT)]))

    def test_keys_and_clam(self) -> None:
        o = self.reg[19]
        keys_, clam = pi.Atlas("doorKeys.png", 3, 1), pi.Atlas("clamStates.png", 2, 1)
        p = self.e.p
        p.write(o + 0x1C, b"\0")
        p.write(o + 0x28, b"\0")
        p.write(o + 0x34, b"\0")
        self.assertEqual(self.draw(19, 0x10000), keys([v3._frame(SHEETS, keys_, 0, *v3.KEYS[0])]))
        self.assertEqual(self.draw(19, 0x20000), keys([v3._frame(SHEETS, keys_, 1, *v3.KEYS[1])]))
        p.put32(o + 0xC, 0)
        self.assertEqual(self.draw(19, 0x30000), keys([v3._frame(SHEETS, clam, 0, *v3.CLAM_AT),
                                                       v3._frame(SHEETS, keys_, 2, *v3.KEYS[2])]))
        p.put32(o + 0xC, 1)
        self.assertEqual(self.draw(19, 0x30000), keys([v3._frame(SHEETS, clam, 1, *v3.CLAM_AT)]))
        p.write(o + 0x1C, b"\1")
        self.assertEqual(self.draw(19, 0x10000), [])                   # picked up

    def test_sun_disk(self) -> None:
        import emu_vv3_assets as E
        o = self.reg[15]
        self.e.p.stub(0x401EB0, lambda q: (0, 0))                     # the clock (only the ghost uses it)
        a = v3.atlas_of(0x91)
        for k in range(3):
            self.e.p.put32(o + 4, k)
            self.assertEqual(self.draw(15, 0x30000), keys([v3._frame(SHEETS, a, k, *v3.SUNDISK_AT)]))
        self.e.p.put32(o + 0x14, E.f32bits(1.0))
        beam = v3._whole(SHEETS, "sunbeam.png", *v3.SUNBEAM_AT)
        self.assertEqual(self.draw(15, 0x20000), keys([beam, beam, beam]))

    def test_woodpile(self) -> None:
        o = self.reg[20]
        self.e.p.write(o + 8, b"\0\1")
        self.assertEqual(self.draw(20, 0), keys([v3._whole(SHEETS, "woodpile.png", *v3.WOODPILE_AT)]))


    def test_huts_being_built_in_the_queues_order(self) -> None:
        """0x432410 queues a hut's scaffolds and picture on the camera (0x42E440); the camera's flush 0x42E2A0
        sorts the queue and draws each through 0x435860 -> 0x432110: the order is the plan's."""
        import emu_vv3_assets as E
        e, o = self.e, self.reg[HUT]
        p = e.p
        progress = {"value": 0}
        p.stub(0x4321F0, lambda q: (0, 4))                              # not finished
        p.stub(0x432210, lambda q: (progress["value"], 4))              # its work done
        n = 0
        for hut in range(4):
            for stage in range(3):
                for work in (0, 1, 49, 50, 99):
                    for k in range(4):
                        p.put32(o + 0x14 + 0x14 * k, stage if k == hut else 0xFFFFFFFF)
                        p.write(o + 4 + 0x14 * k, b"\1")
                    progress["value"] = work
                    e.call(0x42E250, [0, 0, E.f32bits(1.0)], ecx=E.CAMERA)
                    e.call(0x432410, ecx=o)
                    e.call(0x42E2A0, ecx=E.CAMERA)
                    self.assertEqual(e.take(), keys(v3.hut_building_plan(SHEETS, hut, stage, work)),
                                     f"hut {hut} stage {stage} work {work}")
                    n += 1
        self.assertEqual(n, 60)
        del p.stubs[0x4321F0], p.stubs[0x432210]

    def test_orchard_trees(self) -> None:
        e, o = self.e, self.reg[9]
        p = e.p
        clock = {"t": 0}
        p.stub(0x426590, lambda q: (clock["t"], 0))                     # the game clock
        x, y = v3.ORCHARD_SPOT
        n = 0
        for tree in range(3):
            slot = o + 4 + 0x18 * 1
            p.write(slot, struct.pack("<iii", x, y, 0))
            p.put32(slot + 0x10, tree)
            for age in list(range(0, 400, 7)) + list(range(400, 0x7080 + 50, 997)) + [0x707F, 0x7080, 0x7081]:
                for amount in (0, 4, 5, 47, 48, 100, 222, 333, 334, 999):
                    if age < 0x7080 and amount:
                        continue
                    p.put32(slot + 0x14, amount)
                    clock["t"] = age
                    self.assertEqual(self.draw(9, 1 << 16), keys(v3.orchard_plan(SHEETS, tree, age, amount)),
                                     f"tree {tree} age {age} fruit {amount}")
                    n += 1
            for amount in range(0, 400):
                p.put32(slot + 0x14, amount)
                clock["t"] = 0x8000
                got = self.draw(9, 1 << 16)
                self.assertEqual(len(got) - 1, v3.fruit_count(tree, amount), f"tree {tree} fruit {amount}")
        self.assertGreater(n, 300)

    def test_overview_places(self) -> None:
        import emu_vv3_assets as E
        e = self.e
        p = e.p
        obj = 0x582660
        e.call(0x428DC0, ecx=obj)                                       # its sprites (0x428DCB ...)
        p.put32(obj + 0x14A4, e.wrapper)                                # the overview's renderer
        field = {"scaffolding.png": 0x1400, "map_bathDamage.png": 0x1484, "map_bath_filled.png": 0x1488,
                 "map_hospitalStates.png": 0x1490, "amppuddle.png": 0x1494, "map_foodbin.png": 0x1498,
                 "cape.png": 0x149C}
        scale = struct.unpack("<f", p.read(0x4B245C, 4))[0]
        self.assertEqual(scale, v3.OVERVIEW_SCALE)
        for label, sheet, frame, (px, py) in v3.OVERVIEW_PLACES:
            e.call(0x428F90, ecx=obj)                                   # the list emptied
            sprite = p.u32(obj + field[sheet])
            if frame is None:
                e.call(0x428E60, [sprite, px, py], ecx=obj)
            else:
                e.call(0x428EA0, [sprite, px, py, frame], ecx=obj)
            e.call(0x428EF0, [v3.OVERVIEW_AT[0], v3.OVERVIEW_AT[1], E.f32bits(scale)], ecx=obj)
            self.assertEqual(e.take(), keys([v3.overview_place(SHEETS, sheet, frame, px, py)]), label)

    def test_overview_list_is_the_games(self) -> None:
        """0x4290B0 builds the overview's list from the village's state: its entries (sheet, frame, place) for
        every combination of the states it reads are overview_list's."""
        import itertools
        e = self.e
        p = e.p
        obj = 0x582660
        e.call(0x428DC0, ecx=obj)
        field = {p.u32(obj + off): name for off, name in (
            (0x1400, "scaffolding.png"), (0x1484, "map_bathDamage.png"), (0x1488, "map_bath_filled.png"),
            (0x1490, "map_hospitalStates.png"), (0x1494, "amppuddle.png"), (0x1498, "map_foodbin.png"),
            (0x149C, "cape.png"))}
        st = {}
        p.stub(0x42DE40, lambda q: (0, 4))                                  # no collectable found
        p.stub(0x4358D0, lambda q: (int(st["done"]), 4))                    # the bath (project 7) built?
        p.stub(0x4358F0, lambda q: (st["work"], 4))                         # ... its work
        p.stub(0x426FC0, lambda q: (st["hospital"], 4))                     # the hospital's level
        p.stub(0x45FC00, lambda q: (int(st["cape"]), 0))                    # someone wears the cape?
        n = 0
        try:
            for done, work, hospital, puddle, cape, food in itertools.product(
                    (False, True), (0, 1, 50, 51, 84, 85, 94, 95), (0, 1, 2, 3, 4), (0, 50, 51), (False, True),
                    (0, 149, 150, 999, 1000, 2499, 2500, 3999, 4000, 9000)):
                st.update(done=done, work=work, hospital=hospital, cape=cape)
                p.put32(0x4B86D8, puddle)
                p.put32(0x582490, food)
                e.call(0x4290B0, ecx=obj)
                got = []
                at = obj
                while p.read(at, 1) != b"\0":
                    x, y, sprite, frame = struct.unpack("<iiIi", p.read(at + 4, 16))
                    got.append((field[sprite], None if frame == -1 else frame, (x, y)))
                    at += 0x14
                want = [(s, f, xy) for _l, s, f, xy in v3.overview_list(done, work, hospital, puddle, cape, food)]
                self.assertEqual(got, want, (done, work, hospital, puddle, cape, food))
                n += 1
        finally:
            for a in (0x42DE40, 0x4358D0, 0x4358F0, 0x426FC0, 0x45FC00):
                del p.stubs[a]
        self.assertEqual(n, 4800)

    def test_birds(self) -> None:
        e = self.e
        p = e.p
        obj = 0x582158
        p.put32(obj + 0x21C, e.resource(0xAC))
        p.put32(obj + 0x220, e.resource(0xAD))
        for frame in range(v3.BIRD_FRAMES):
            for height in (0, 7, 40):
                p.write(obj, struct.pack("<ii", 500, 600))
                p.write(obj + 0x24, struct.pack("<iiii", frame, 100, 0, 1))
                p.put32(obj + 0x38, height)
                e.call(0x4249E0, [0], ecx=obj)
                self.assertEqual(e.take(), keys(v3.bird_plan(SHEETS, frame, 500, 600, height)), (frame, height))

    def test_effect_frames(self) -> None:
        """0x429610 (the animation manager 0x583B28, queue kind 4): frame f of a sheet at its place."""
        e = self.e
        p = e.p
        mgr = 0x583B28
        slot = mgr + 4
        for rid in v3.EFFECT_STRIPS:
            a = v3.atlas_of(rid)
            sprite = e.resource(rid)
            for f in range(a.cols * a.rows):
                p.write(slot, bytes(0x44))
                p.put32(slot + 8, 300)
                p.put32(slot + 0xC, 200)
                p.put32(slot + 0x14, f)
                p.put32(slot + 0x34, 0xFFFFFFFF)
                p.put32(slot + 0x40, sprite)
                e.call(0x429610, [0], ecx=mgr)
                self.assertEqual(e.take(), keys([v3._frame(SHEETS, a, f, 300, 200)]), (a.name, f))


HUT = 0x15


@unittest.skipUnless(ART.is_dir(), "needs the game's art in research/game-images")
class RealArt(unittest.TestCase):
    def test_sizes_are_the_stock(self) -> None:
        for p in ART.iterdir():
            if p.suffix.casefold() in pa.PICTURE_EXTENSIONS:
                self.assertEqual(pa.picture_size(p.read_bytes()), v3.SIZES[p.name], p.name)

    def test_everything_lists(self) -> None:
        sheets = pa.AssetSheets(pa.PatcherOverlay(pa.GameFolderSource(ART.parent), v3.patcher_art()))
        got = pa.all_assets(3, sheets, v3)
        unused = [a for a in got if a.category == pa.SHEETS and a.unused]
        self.assertEqual(sorted(a.label for a in unused if a.group == "Never loaded by the game"),
                         sorted(v3.UNUSED_FILES))
        png = [a for a in got if a.category != pa.SHEETS and all(
            d.file.casefold().endswith(".png") for f in a.frames for d in f.plan)]
        for a in png[:40]:
            for f in a.frames[:2]:
                pa.render_frame(sheets, f)


if __name__ == "__main__":
    unittest.main()
