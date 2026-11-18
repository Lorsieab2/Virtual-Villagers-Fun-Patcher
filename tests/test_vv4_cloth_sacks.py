"""Cloth Sacks for Yellow Fruit and Cutting Tool Harvest Caption (The Tree of Life): "VVFP VV4 Cloth Sacks.dll" and
"VVFP VV4 Harvest Caption.dll".

Everything here runs the shipped DLLs beside The Tree of Life's own code in unicorn (tests/farmers_emulation_vv4.py,
with the companion mapped through tests/story_emulator.py's Process).  The drop dispatcher, the fruit trip, the job
events, the food writer (Food Mastery inside it), the Farming dispatcher and the carried item's draw are the game's
own routines; only rand, the clock and the two singleton getters are stand-ins (farmers_emulation_vv4.py says why
each is safe), and for the pictures the image loader and operator new (the sprite's own loading is not the point).
"Stock" is the same village without the companion: every behaviour test also shows the stock game does not do it.
The cutting tool on the blackberries -- the model the owner set -- is run as the stock game runs it, beside a sack.

The live effect in a running game is NOT verified here.
"""
from __future__ import annotations

import functools
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_fun_patcher as patcher  # noqa: E402
import build_vv4_cloth_sacks_features as builder  # noqa: E402

try:
    import pefile  # noqa: F401
    from unicorn import UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_ESP

    import farmers_emulation_vv4 as fe
    from story_emulator import API_STUBS

    HAVE_EMULATOR = fe.STOCK.is_file() and fe.CMAP.is_file()
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

ID, CAPTION_ID = builder.ID, builder.CAPTION_ID
DLL, CAPTION_DLL = builder.DLL, builder.CAPTION_DLL
MODES = ("stock", "collection_progression", "immediate_fixed")

DROP = 0x46E460                  # the drop dispatcher: (villager), ret 4
HARVEST_DROP = 0x46E7E0          # map area 0x31's handler, the cutting tool (message, villager)
DISPATCHER = 0x4639B0
CARRY_DRAW = 0x466770            # thiscall(villager, x, y), ret 0xC
WORLD_DRAW = 0x44C640
HUT_X, HUT_Y = 0x4D8300, 0x4D8304
CLOTH, TOOLS = 0x4D8ACC, 0x4D8618
REC_AGE, REC_PREGNANT, REC_TASK, REC_ACTION, REC_ITEM, REC_CAPTION = 0x1B8C, 0x1C4C, 0x1C54, 0x1CE0, 0x1CDC, 0x1CE4
SKILL_ROLL = 0x462B1A            # rand(100) of the skill check (return address)
AWNING = (425, 1712)             # under the awning: the hut's place (400, 1600) + (25, 112)
EV_MADE, EV_FULL, EV_CREDIT = 0x75, 0x76, 0x77
FOOD_MASTERY = 4                 # the technology index (0x41E1C0)
SOLVED = (6, 0x16)               # the Cooking Pit restored, the Clothing Hut finished (no nets, no berries)
FAKE_OFFSET = 0xF000             # the stand-in fruit supply's exports, at the end of the API stub page


@functools.lru_cache(maxsize=None)
def builds():
    return {b.id: b for b in patcher.load_builds()}


@functools.lru_cache(maxsize=None)
def render(mode: str) -> bytes:
    """The Tree of Life's public catalog (both rows in it) as the patcher renders it."""
    rows = [p for p in patcher.load_public_fun_patches()
            if p.game_id == "vv4" and p.id not in patcher.ALTERNATIVE_FUN_PATCH_IDS
            and p.id not in patcher.EXPERIMENTAL_FUN_PATCH_IDS]
    ids = patcher.resolve_fun_patch_ids([p.id for p in rows], game_id="vv4")
    assert ID in ids and CAPTION_ID in ids
    data, _ = patcher.render_patched_bytes(fe.STOCK, builds()["vv4"], mode, ids)
    return bytes(data)


class _Rolls(dict):
    """farmers_emulation_vv4's forced rand(n) answers by return address, plus every rand the companion (mapped at
    0x10000000) draws answered by the hut's dll_rand when it is set."""

    def __init__(self, hut: "Hut"):
        super().__init__()
        self.hut = hut

    def _ours(self, caller: int) -> bool:
        return self.hut.dll_rand is not None and 0x10000000 <= caller < 0x11000000

    def __contains__(self, caller) -> bool:
        return self._ours(caller) or dict.__contains__(self, caller)

    def __getitem__(self, caller):
        return self.hut.dll_rand if self._ours(caller) else dict.__getitem__(self, caller)


class Hut:
    """A Tree of Life village with the Clothing Hut finished and the Cooking Pit restored."""

    def __init__(self, patched: bool = True, *, dll: Path = DLL, cloth: int = 3, tree: int | None = None,
                 levels=(1, 1, 1, 1, 1, 1, 1, 1), solved=SOLVED, berries: int = 0, exe: bytes | None = None,
                 seed: int = 5):
        self.v = fe.Village(seed=seed, berries=berries, solved=solved, levels=levels, exe=exe,
                            dll=dll if patched else None)
        self.dll_rand: int | None = None
        self.taken: list[int] = []
        self.tree = tree
        if patched:
            p = self.v.process
            if tree is not None:
                self._fake_fruit_supply()
            p.export("VvfpStartup", 4, 0)
            self.v.by_caller = _Rolls(self)      # a rand(n) the companion draws can be forced (dll_rand)
        self.v.w32(HUT_X, 400)
        self.v.w32(HUT_Y, 1600)
        self.v.w32(CLOTH, cloth)
        self.v.by_caller[SKILL_ROLL] = 0          # every Farming check passes unless a test says otherwise

    def installed(self) -> int:
        return self.v.process.export("VvfpClothSacksInstalled")

    def _fake_fruit_supply(self) -> None:
        """"VVFP VV4 Fruit Supply.dll" stood in for: its VvfpYellowFruitLeft / VvfpYellowFruitTake on `tree`."""
        p = self.v.process
        fake = API_STUBS + FAKE_OFFSET
        p.mu.mem_write(fake, b"\xC3" * 0x20)

        def left(_p):
            return self.tree, 0

        def take(pp):
            want = pp.arg(0)
            n = min(want, self.tree)
            self.tree -= n
            self.taken.append(n)
            return n, 4
        p.stubs[fake] = left
        p.stubs[fake + 0x10] = take

        def module(pp):
            if pp.arg(0) == 0:
                return 0x400000, 4
            return (0x7000000 if pp.wstring(pp.arg(0)) == "VVFP VV4 Fruit Supply.dll" else 0), 4

        def proc(pp):
            name = pp.cstring(pp.arg(1))
            return {"VvfpYellowFruitLeft": fake, "VvfpYellowFruitTake": fake + 0x10}.get(name, 0), 8
        p.api_handlers["GetModuleHandleW"] = module
        p.api_handlers["GetProcAddress"] = proc

    def villager(self, at=AWNING, **kw) -> int:
        return self.v.villager(at=at, skills=kw.pop("skills", {"farming": 100}), **kw)

    def drop(self, r: int) -> int:
        return self.v.call(DROP, 0, r) & 0xFF

    def caption(self, r: int) -> str:
        return bytes(self.v.uc.mem_read(r + REC_CAPTION, 40)).split(b"\0")[0].decode("latin-1")

    def queue(self, r: int) -> list[tuple[int, int]]:
        out = []
        for i in range(80):
            t = self.v.r32(r + i * 0x58)
            if t == 0:
                break
            out.append((t, self.v.r32(r + i * 0x58 + 4)))
        return out

    def run(self, max_frames: int = 20_000, watch=None) -> int:
        """Frames until the queue is empty; `watch(frame)` each frame."""
        for f in range(max_frames):
            self.v.step_frame()
            if watch is not None:
                watch(f)
            if self.v.queue_type() == 0:
                return f
        raise AssertionError("the trip never ended")

    def credits(self) -> list[int]:
        return [amount for _, amount in self.v.food_log]

    def events(self) -> list[int]:
        return [e for _, e in self.v.events]


@unittest.skipUnless(HAVE_EMULATOR, "the stock executable, its map and unicorn are needed")
class SackTripTests(unittest.TestCase):
    def test_installs_for_the_tree_of_life_only(self) -> None:
        h = Hut()
        self.assertEqual(h.installed(), 1)
        self.assertEqual(h.v.uc.mem_read(0x46E460, 1)[0], 0xE9)
        self.assertEqual(h.v.uc.mem_read(0x4667B4, 1)[0], 0xE8)
        other = fe.Village(dll=DLL)
        other.process.export("VvfpStartup", 3, 0)
        self.assertEqual(other.process.export("VvfpClothSacksInstalled"), 0)
        self.assertEqual(bytes(other.uc.mem_read(0x46E460, 8)).hex().upper(), "83EC08568B742410")

    def test_a_drop_under_the_awning_makes_a_sack_and_brings_30_food(self) -> None:
        h = Hut()
        r = h.villager()
        food = h.v.food()
        self.assertEqual(h.drop(r), 1)
        self.assertEqual(h.v.r32(CLOTH), 2)                   # one cloth bolt used at once, as the cutting tool
        seen: list[tuple[str, int]] = []

        def watch(_f):
            key = (h.caption(r), h.v.r32(r + REC_ITEM))
            if not seen or seen[-1] != key:
                seen.append(key)
        h.run(watch=watch)
        self.assertEqual(h.credits(), [30])                   # the sack's 30, nothing else (no event 15's 3)
        self.assertEqual(h.v.food(), food + 30)
        self.assertNotIn(15, h.events())
        self.assertEqual([e for e in h.events() if e >= EV_MADE], [EV_MADE, EV_FULL, EV_CREDIT])
        self.assertTrue(h.v.at_bin())
        captions = [c for c, _ in seen]
        self.assertEqual(captions[0], "Making a sack out of cloth")
        self.assertIn("Gathering food in cloth sack", captions)
        self.assertIn((captions[0], 0x35), seen)              # the cloth in hand while making
        self.assertEqual(seen[-1][1] & 0xFFFFFFFF, 0xFFFFFFFF)  # put down at the bin
        self.assertIn(0x36, [i for _, i in seen])             # the full sack (yellow fruit) carried
        self.assertNotIn(0x37, [i for _, i in seen])          # never the stew's stomped fruit (a Grand Feast item)

    def test_the_stock_game_does_nothing_of_the_kind(self) -> None:
        h = Hut(patched=False)
        r = h.villager()
        h.drop(r)
        self.assertEqual(h.v.r32(CLOTH), 3)
        self.assertNotEqual(h.v.r32(r + REC_ACTION), 0x64)
        self.assertEqual(h.v.food_log, [])

    def test_no_cloth_refuses_as_no_cutting_tool_does(self) -> None:
        h = Hut(cloth=0)
        r = h.villager()
        self.assertEqual(h.drop(r), 1)
        self.assertEqual(h.v.r32(r + REC_ACTION), 0x1A)        # the cutting tool's refusal action
        self.assertEqual(h.v.r32(CLOTH), 0)
        self.assertNotIn((0x13, EV_CREDIT), h.queue(r))

    def test_only_an_adult_under_the_awning_with_the_hut_and_pit_ready(self) -> None:
        cases = {
            "elsewhere on the hut": dict(at=(520, 1712)),
            "a child": dict(age=100),
            "expecting": dict(),
        }
        for name, kw in cases.items():
            with self.subTest(name):
                h = Hut()
                r = h.villager(**kw)
                if name == "expecting":
                    h.v.w32(r + REC_PREGNANT, 1)
                h.drop(r)
                self.assertEqual(h.v.r32(CLOTH), 3)
                self.assertNotIn((0x13, EV_CREDIT), h.queue(r))
        for solved in ((6,), (0x16,)):
            with self.subTest(solved=solved):
                h = Hut(solved=solved)
                r = h.villager()
                h.drop(r)
                self.assertEqual(h.v.r32(CLOTH), 3)

    def test_a_failed_farming_check_loses_the_cloth_like_a_cutting_tool(self) -> None:
        h = Hut()
        r = h.villager(skills={"farming": 0})
        h.v.by_caller[SKILL_ROLL] = 99
        h.drop(r)
        h.run()
        self.assertEqual(h.v.r32(CLOTH), 2)
        self.assertEqual(h.v.food_log, [])

    def test_food_mastery_multiplies_a_sack_as_it_multiplies_a_cutting_tool_harvest(self) -> None:
        for level, expected in ((1, 30), (2, 45), (3, 60)):
            levels = [1] * 8
            levels[FOOD_MASTERY] = level
            with self.subTest(level=level):
                sack = Hut(levels=tuple(levels))
                r = sack.villager()
                before = sack.v.food()
                sack.drop(r)
                sack.run()
                # The stock game's cutting tool on the blackberries, the model: one tool, 30 berries.
                harvest = Hut(patched=False, levels=tuple(levels), berries=1000)
                harvest.v.w32(TOOLS, 3)
                h = harvest.villager(at=(1568, 1124))
                stock_before = harvest.v.food()
                harvest.v.call(HARVEST_DROP, 0, 0, h)
                self.assertEqual(harvest.v.r32(TOOLS), 2)
                harvest.run()
                # Both ask the food writer for 30; Food Mastery multiplies inside it, the same for both.
                self.assertEqual(harvest.credits(), [30])
                self.assertEqual(sack.credits(), [30])
                self.assertEqual(harvest.v.food() - stock_before, expected)
                self.assertEqual(sack.v.food() - before, expected)

    def test_with_the_limited_tree_a_sack_takes_its_fruit_from_it(self) -> None:
        for tree, paid in ((1000, 30), (10, 10)):
            with self.subTest(tree=tree):
                h = Hut(tree=tree)
                r = h.villager(task=2)
                h.drop(r)
                h.run()
                self.assertEqual(h.taken, [paid])            # taken at the food bin, at most 30
                self.assertEqual(h.credits(), [paid])
                self.assertEqual(h.tree, tree - paid)
                self.assertEqual(h.v.r32(r + REC_TASK), 2 if tree - paid >= 3 else 0)   # event 14's rule
        h = Hut(tree=2)
        r = h.villager()
        h.drop(r)
        self.assertEqual(h.v.r32(r + REC_ACTION), 0x3F)         # the tree's own refusal
        self.assertEqual(h.v.r32(CLOTH), 3)

    def test_farmers_the_game_sends_make_sacks_as_one_more_choice(self) -> None:
        h = Hut()
        r = h.villager(preference=0)
        h.dll_rand = 1                                         # rand(2) == 1: the sack (one other option: fruit)
        h.v.call(DISPATCHER, r, 0)
        self.assertEqual(h.v.r32(CLOTH), 2)
        q = h.queue(r)
        self.assertEqual(q[1], (3, 100))                       # first the walk to the awning
        self.assertIn((0x13, EV_CREDIT), q)
        h.run(max_frames=30_000)
        self.assertEqual(h.credits(), [30])
        not_picked = Hut()
        r = not_picked.villager(preference=0)
        not_picked.dll_rand = 0
        not_picked.v.call(DISPATCHER, r, 0)
        self.assertEqual(not_picked.v.r32(CLOTH), 3)
        self.assertIn(not_picked.v.r32(r + REC_ACTION), range(100, 105))   # the dispatcher's own fruit
        none = Hut(cloth=0)
        r = none.villager(preference=0)
        none.dll_rand = 1
        none.v.call(DISPATCHER, r, 0)
        self.assertNotIn((0x13, EV_CREDIT), none.queue(r))

    def test_the_sack_pictures_are_drawn_for_the_sack_only(self) -> None:
        h = Hut()
        p = h.v.process
        heads = {name: struct.pack(">II", w, hh) + bytes([8, 6]) for name, w, hh in builder.PICTURES}
        handles: dict[int, bytes] = {}

        def create(pp):
            path = pp.wstring(pp.arg(0))
            leaf = path.rsplit("\\", 1)[-1]
            if leaf not in heads:
                return 0xFFFFFFFF, 28
            handles[0x900 + len(handles)] = b"\x89PNG\r\n\x1a\n\0\0\0\x0dIHDR" + heads[leaf]
            return 0x900 + len(handles) - 1, 28

        def read(pp):
            data = handles[pp.arg(0)]
            n = min(pp.arg(2), len(data))
            pp.write(pp.arg(1), data[:n])
            pp.put32(pp.arg(3), n)
            return 1, 20
        p.api_handlers["CreateFileW"] = create
        p.api_handlers["ReadFile"] = read
        p.api_handlers["CloseHandle"] = lambda pp: (1, 4)
        heap = [fe.HEAP + 0x8000]

        def alloc(*_):
            at = heap[0]
            heap[0] += 0x40
            h.v._ret(at, 0)

        def grid(*_):
            sp = h.v.uc.reg_read(UC_X86_REG_ESP)
            this = h.v.uc.reg_read(fe.UC_X86_REG_ECX)
            name = p.cstring(h.v.r32(sp + 4))
            size = {n: hh for n, _, hh in builder.PICTURES}[name]
            h.v.w32(this + 0x10, 60)
            h.v.w32(this + 0x14, size)
            h.v.w32(this + 0x30, 0x51AC0000 + size)               # a mark to tell the two apart
            h.v._ret(this, 0xC)
        drawn: list[tuple] = []

        def draw(*_):
            sp = h.v.uc.reg_read(UC_X86_REG_ESP)
            sprite, x, y, frame = struct.unpack("<4I", h.v.uc.mem_read(sp + 4, 16))
            scale = struct.unpack("<f", h.v.uc.mem_read(sp + 20, 4))[0]
            drawn.append((sprite, x, y, frame, round(scale, 2)))
            h.v._ret(0, 0x14)
        for at, fn in ((0x470C5C, alloc), (0x40AB10, grid), (WORLD_DRAW, draw)):
            h.v.uc.hook_add(UC_HOOK_CODE, lambda *_a, fn=fn: fn(), begin=at, end=at)
        mgr = fe.HEAP + 0x6000
        h.v.w32(mgr + 0x24, 0xCAFE0024)                           # carrying.png
        h.v.w32(mgr + 0x28, 0xCAFE0028)
        r = h.villager()

        def picture() -> tuple:
            drawn.clear()
            h.v.call(CARRY_DRAW, mgr, r, 100, 200)
            sprite, x, y, frame, scale = drawn[0]
            mark = h.v.r32(sprite + 0x30) if fe.HEAP <= sprite < fe.HEAP + 0x100000 else 0
            return {0x51AC0000 + 65: "empty", 0x51AC0000 + 87: "full"}.get(mark, hex(sprite)), x, y, frame, scale
        h.v.w32(r + REC_ITEM, 0x35)
        self.assertEqual(picture(), ("0xcafe0024", 100, 200, 0x35, 1.0))   # cloth, not on a trip: the game's own
        h.drop(r)
        states = set()

        def watch(_f):
            if h.v.r32(r + REC_ITEM) in (0x35, 0x36):
                states.add((h.v.r32(r + REC_ITEM), picture()))
        h.run(watch=watch)
        self.assertIn((0x35, ("0xcafe0024", 100, 200, 0x35, 1.0)), states)   # making: the cloth bolt
        self.assertIn((0x35, ("empty", 106, 201, 0, 0.45)), states)           # the empty sack
        self.assertIn((0x36, ("0xcafe0024", 100, 200, 0x36, 1.0)), states)   # shaking: the game's yellow fruit
        self.assertIn((0x36, ("full", 106, 191, 0, 0.45)), states)            # the full sack to the bin
        h.v.w32(r + REC_ITEM, 0x36)
        self.assertEqual(picture()[0], "0xcafe0024")                          # the trip over: the game's own


@unittest.skipUnless(HAVE_EMULATOR, "the stock executable, its map and unicorn are needed")
class HarvestCaptionTests(unittest.TestCase):
    def caption(self, patched: bool, action: int) -> str:
        v = fe.Village(berries=1000, dll=CAPTION_DLL if patched else None)
        if patched:
            v.process.export("VvfpStartup", 4, 0)
            self.assertEqual(v.process.export("VvfpHarvestCaptionInstalled"), 1)
        r = v.villager()
        v.start(action)
        return bytes(v.uc.mem_read(r + REC_CAPTION, 40)).split(b"\0")[0].decode("latin-1")

    def test_the_cutting_tool_harvest_says_so_and_picking_does_not(self) -> None:
        self.assertEqual(self.caption(True, 0xBE), builder.CAPTION)
        self.assertNotEqual(self.caption(True, 99), builder.CAPTION)
        self.assertNotEqual(self.caption(False, 0xBE), builder.CAPTION)
        self.assertLessEqual(len(builder.CAPTION), 38)


class RowTests(unittest.TestCase):
    def test_the_rows_are_the_builders_and_pin_the_shipped_files(self) -> None:
        for path, made in ((ROOT / "data" / f"{ID}_feature.json", builder.row(builder.sha(DLL))),
                           (ROOT / "data" / f"{CAPTION_ID}_feature.json",
                            builder.caption_row(builder.sha(CAPTION_DLL)))):
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), made)
        row = json.loads((ROOT / "data" / f"{ID}_feature.json").read_text(encoding="utf-8"))
        self.assertIn("**Needs no other patch.**", row["description"])
        self.assertIn("**Off by default; Owner's Defaults ticks it.**", row["description"])
        self.assertEqual([f["destination"] for f in row["companion_files"]],
                         ["VVFP VV4 Cloth Sacks.dll", "Images/vvfp_sack_empty.png", "Images/vvfp_sack_yellow_fruit.png"])

    def test_vvfp_startup_starts_both(self) -> None:
        self.assertIn("VVFP VV4 Cloth Sacks.dll", patcher.STARTUP_LOADER_COMPANIONS_2)
        self.assertIn("VVFP VV4 Harvest Caption.dll", patcher.STARTUP_LOADER_COMPANIONS_2)
        header = (ROOT / "native" / "shared" / "startup_companions_2.h").read_text(encoding="utf-8")
        self.assertIn('"VVFP VV4 Cloth Sacks.dll"', header)

    def test_off_by_default_and_on_in_owners_defaults(self) -> None:
        import vv_fun_patcher_gui as gui
        for pid in (ID, CAPTION_ID):
            self.assertIn(pid, gui.DEFAULT_OFF_FUN_PATCH_IDS)
            self.assertNotIn(pid, gui.OWNERS_DEFAULT_OFF_FUN_PATCH_IDS)

    def test_the_captions_fit_the_villagers_caption_field(self) -> None:
        source = (ROOT / "native" / "vvfp_vv4_cloth_sacks" / "vvfp_vv4_cloth_sacks.c").read_text(encoding="utf-8")
        for text in ("Making a sack out of cloth", "Gathering food in cloth sack"):
            self.assertIn(f'"{text}"', source)
            self.assertLessEqual(len(text), 38)
        strings = json.loads((ROOT / "data" / "translations" / "patcher_strings.json").read_text(encoding="utf-8"))
        english = json.dumps(strings)
        for text in ("Making a sack out of cloth", "Gathering food in cloth sack", builder.CAPTION):
            self.assertIn(text, english)


@unittest.skipUnless(HAVE_EMULATOR, "the stock executable, its map and unicorn are needed")
class RenderedTests(unittest.TestCase):
    def test_the_rendered_executable_keeps_every_site_stock_and_both_install_in_every_mode(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                exe = render(mode)
                for va, stock, _ in builder.SITES + (builder.CAPTION_SITE,):
                    self.assertEqual(exe[va - 0x400000:va - 0x400000 + len(stock) // 2].hex().upper(), stock)
                h = Hut(exe=exe)
                self.assertEqual(h.installed(), 1)
                r = h.villager()
                self.assertEqual(h.drop(r), 1)
                self.assertIn((0x13, EV_CREDIT), h.queue(r))
                v = fe.Village(exe=exe, dll=CAPTION_DLL)
                v.process.export("VvfpStartup", 4, 0)
                self.assertEqual(v.process.export("VvfpHarvestCaptionInstalled"), 1)


if __name__ == "__main__":
    unittest.main()
