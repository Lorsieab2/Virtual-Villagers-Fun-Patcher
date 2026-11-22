"""Cloth Sacks for Yellow Fruit (The Tree of Life): "VVFP VV4 Cloth Sacks.dll".

Everything here runs the shipped DLL beside The Tree of Life's own code in unicorn (tests/farmers_emulation_vv4.py,
with the companion mapped through tests/story_emulator.py's Process).  The drop dispatcher, the fruit trip, the job
events, the food writer (Food Mastery inside it), the Farming dispatcher (untouched) and the carried item's draw are the game's
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

ID, DLL = builder.ID, builder.DLL
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
EV_STEW, EV_STEW_DONE = 0x78, 0x79
POT, ITEM_REGISTRY, LOCKS = 0x4D76D8, 0x4CC0A0, 0x704E38
FEAST_FLAGS = 0xB20              # pot + 0xB20..0xB23: mushroom, berries, fish, fruit (0x42DD60 .. 0x42DDA0)
HARVEST_CREDIT_RETURN = 0x464510  # the return of job event 14's food-writer call: #805's whitelisted cutting-tool berries


def grand_feast(v) -> None:
    """The pot brewing the Grand Feast with none of its four items in: the item registry built by its own
    constructor 0x413360 (the pot's listener 0x42EA30 offered items 0, 6, 0x1F..0x25, 0x37, 0x38, 0x76..0x78), the
    pot's vtables as 0x42EF20 sets them, the product 4 (the feast) and the pot's lock 0x18 taken (boiling)."""
    v.call(0x413360, ITEM_REGISTRY)
    v.uc.mem_write(POT, struct.pack("<3I", 0x48E268, 0x48E258, 0x48E250))
    v.w32(POT + 0xB10, 4)
    v.w8(LOCKS + 0x14 * 0x18, 1)


def feast_flags(v) -> tuple[int, int, int, int]:
    """(mushroom, berries, fish, fruit): what the pot has for the feast."""
    return tuple(v.uc.mem_read(POT + FEAST_FLAGS, 4))


def food_writer_returns(v) -> list[int]:
    """Each food-writer 0x41D920 call's return address, as #805's doubler wrapper reads it."""
    seen: list[int] = []
    v.uc.hook_add(UC_HOOK_CODE, lambda u, *_: seen.append(struct.unpack("<I", u.mem_read(
        u.reg_read(UC_X86_REG_ESP), 4))[0]), begin=0x41D920, end=0x41D920)
    return seen


@functools.lru_cache(maxsize=None)
def builds():
    return {b.id: b for b in patcher.load_builds()}


@functools.lru_cache(maxsize=None)
def render(mode: str) -> bytes:
    """The Tree of Life's public catalog (this row in it) as the patcher renders it."""
    rows = [p for p in patcher.load_public_fun_patches()
            if p.game_id == "vv4" and p.id not in patcher.ALTERNATIVE_FUN_PATCH_IDS
            and p.id not in patcher.EXPERIMENTAL_FUN_PATCH_IDS]
    ids = patcher.resolve_fun_patch_ids([p.id for p in rows], game_id="vv4")
    assert ID in ids
    data, _ = patcher.render_patched_bytes(fe.STOCK, builds()["vv4"], mode, ids)
    return bytes(data)


class Hut:
    """A Tree of Life village with the Clothing Hut finished and the Cooking Pit restored."""

    def __init__(self, patched: bool = True, *, dll: Path = DLL, cloth: int = 3, tree: int | None = None,
                 levels=(1, 1, 1, 1, 1, 1, 1, 1), solved=SOLVED, berries: int = 0, exe: bytes | None = None,
                 seed: int = 5):
        self.v = fe.Village(seed=seed, berries=berries, solved=solved, levels=levels, exe=exe,
                            dll=dll if patched else None)
        self.taken: list[int] = []
        self.tree = tree
        if patched:
            p = self.v.process
            if tree is not None:
                self._fake_fruit_supply()
            p.export("VvfpStartup", 4, 0)
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
        # As the cutting tool: nothing is checked about the fruit at the drop (the owner, 2026-11-17); the sack
        # takes what is left at the food bin, at most 30, even none, and the cloth bolt is used either way.
        for tree, paid in ((1000, 30), (10, 10), (2, 2), (0, 0)):
            with self.subTest(tree=tree):
                h = Hut(tree=tree)
                r = h.villager(task=2)
                self.assertEqual(h.drop(r), 1)
                self.assertEqual(h.v.r32(CLOTH), 2)
                self.assertNotEqual(h.v.r32(r + REC_ACTION), 0x3F)  # never the empty tree's refusal
                h.run()
                self.assertEqual(h.taken, [paid] if paid else [])   # taken at the food bin, at most 30
                self.assertEqual(h.credits(), [paid])
                self.assertEqual(h.tree, tree - paid)
                self.assertEqual(h.v.r32(r + REC_TASK), 2 if tree - paid >= 3 else 0)   # event 14's rule

    def test_farmers_the_game_sends_never_make_a_sack(self) -> None:
        # The owner (2026-11-17): "farmers should never use cutting tools or sacks on their own".
        h = Hut()
        self.assertEqual(bytes(h.v.uc.mem_read(0x463A5A, 8)).hex().upper(), "3BFB0F8499060000")
        self.assertNotIn(0x463A5A, [va for va, _, _ in builder.SITES])
        for roll in (0, 1):                                     # the berries or the fruit
            with self.subTest(roll=roll):
                h = Hut(berries=1000)
                r = h.villager(preference=0)
                h.v.by_caller[0x463A68] = roll                  # the dispatcher's own rand(n), either pick
                h.v.call(DISPATCHER, r, 0)
                self.assertEqual(h.v.r32(CLOTH), 3)
                self.assertNotIn((0x13, EV_CREDIT), h.queue(r))
                self.assertNotIn((0x13, EV_MADE), h.queue(r))
                h.run(max_frames=30_000)
                self.assertNotIn(EV_CREDIT, h.events())
                self.assertEqual(h.v.r32(CLOTH), 3)

    def test_the_sack_pictures_are_drawn_for_the_sack_only(self) -> None:
        """Owner, live (v2): the sack was drawn faded and huge.  The world draw's fifth argument is the picture's
        ALPHA (it reaches 0x408DC0 as the opacity; the size is the map's zoom): every carried item passes 1.0, and
        so must the sack.  The pictures are carried-item size and sit on carrying.png's 40-pixel cell."""
        h = Hut()
        p = h.v.process
        names = [shipped for shipped, _ in builder.PICTURES]
        sizes = {name: builder.picture_size(name) for name in names}
        for w, hh in sizes.values():
            self.assertLessEqual(max(w, hh), 40)                  # no bigger than a carrying.png cell
        handles: dict[int, bytes] = {}

        def create(pp):
            leaf = pp.wstring(pp.arg(0)).rsplit("\\", 1)[-1]
            if leaf not in sizes:
                return 0xFFFFFFFF, 28
            handle = 0x900 + len(handles)
            handles[handle] = (ROOT / "assets" / "cloth_sacks" / leaf).read_bytes()[:26]
            return handle, 28

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

        def grid(*_):                                             # the game's image loader, stood in for
            sp = h.v.uc.reg_read(UC_X86_REG_ESP)
            this = h.v.uc.reg_read(fe.UC_X86_REG_ECX)
            name = p.cstring(h.v.r32(sp + 4))
            w, hh = sizes[name]
            h.v.w32(this + 0x10, w)
            h.v.w32(this + 0x14, hh)
            h.v.w32(this + 0x30, 0x51AC0000 + names.index(name))   # a mark to tell them apart
            h.v._ret(this, 0xC)
        drawn: list[tuple] = []

        def draw(*_):
            sp = h.v.uc.reg_read(UC_X86_REG_ESP)
            sprite, x, y, frame = struct.unpack("<4I", h.v.uc.mem_read(sp + 4, 16))
            alpha = struct.unpack("<f", h.v.uc.mem_read(sp + 20, 4))[0]
            drawn.append((sprite, x, y, frame, round(alpha, 2)))
            h.v._ret(0, 0x14)
        for at, fn in ((0x470C5C, alloc), (0x40AB10, grid), (WORLD_DRAW, draw)):
            h.v.uc.hook_add(UC_HOOK_CODE, lambda *_a, fn=fn: fn(), begin=at, end=at)
        mgr = fe.HEAP + 0x6000
        h.v.w32(mgr + 0x24, 0xCAFE0024)                           # carrying.png
        h.v.w32(mgr + 0x28, 0xCAFE0028)
        r = h.villager()
        label = {0: "empty", 1: "raw", 2: "cooked"}

        def picture() -> tuple:
            drawn.clear()
            h.v.call(CARRY_DRAW, mgr, r, 100, 200)
            sprite, x, y, frame, alpha = drawn[0]
            mark = h.v.r32(sprite + 0x30) - 0x51AC0000 if fe.HEAP <= sprite < fe.HEAP + 0x100000 else -1
            return label.get(mark, hex(sprite)), x, y, frame, alpha

        def placed(name: str) -> tuple:
            w, hh = sizes[f"vvfp_sack_{name}.png".replace("raw", "yellow_fruit_raw").replace("cooked", "yellow_fruit")]
            return 100 + (40 - w) // 2, 200 + 31 - hh
        h.v.w32(r + REC_ITEM, 0x35)
        self.assertEqual(picture(), ("0xcafe0024", 100, 200, 0x35, 1.0))   # cloth, not on a trip: the game's own
        h.drop(r)
        states = set()

        def watch(_f):
            if h.v.r32(r + REC_ITEM) in (0x35, 0x36):
                states.add((h.v.r32(r + REC_ITEM), picture()))
        h.run(watch=watch)
        self.assertIn((0x35, ("0xcafe0024", 100, 200, 0x35, 1.0)), states)   # making: the cloth bolt
        self.assertIn((0x35, ("empty", *placed("empty"), 0, 1.0)), states)    # the empty sack
        self.assertIn((0x36, ("raw", *placed("raw"), 0, 1.0)), states)        # trees to pit: the raw fruit
        self.assertIn((0x36, ("cooked", *placed("cooked"), 0, 1.0)), states)  # pit to bin: the cooked fruit
        self.assertNotIn((0x36, ("0xcafe0024", 100, 200, 0x36, 1.0)), states)  # never the loose yellow fruit
        self.assertTrue(all(state[1][4] == 1.0 for state in states))         # never faded
        h.v.w32(r + REC_ITEM, 0x36)
        self.assertEqual(picture()[0], "0xcafe0024")                          # the trip over: the game's own

    def test_the_sack_spot_always_wins_over_the_new_clothes_question(self) -> None:
        """Owner, live (v3): "sometimes I drop them on the right spot for sackmaking and it still gives the buying
        clothes prompt".  The game's own drop area of the finished hut (map cells whose drop-area field, the one
        0x46C410 reads for the drop dispatcher, is 0x12) reaches below the sack's box (y 40..134) to y 168, so a drop
        there went to the hut's handler 0x46F600 and its question.  Now, in the sack's columns (x -26..70), every
        drop the game would hand to the hut makes a sack.

        The hut's cells are marked by the game's own routine 0x430A20 on the Clothing Hut object 0x4D82D8 (built by
        its constructor 0x431190: drop area +0x1C = 0x12, area frame +0x7C = 4): it stamps the frame's mask twice
        with 0x46CDA0, at the hut's place + (0, 24) and + (-16, 16).  The mask is built as 0x46CC50 builds it (a
        cell where at least 20 of its 64 pixels are not transparent) from frame 4 of clothinghut_states.png.  (The
        point setter 0x46C450 writes a different field, the walk-target area 0x46C3F0 reads; the drop dispatcher
        never sees it.)  The hut's handler is registered as the game registers it (0x46E5E0 at 0x46FA94), and drops
        are made across the whole box and every hut cell in those columns."""
        from PIL import Image
        art = ROOT / "research" / "game-images" / "Virtual Villagers - The Tree of Life" / "Images" / "clothinghut_states.png"
        if not art.is_file():
            self.skipTest("the game's pictures (research/game-images) are needed")
        alpha = Image.open(art).crop((0, 400, 200, 600)).getchannel("A")        # frame 4: the hut's area shape
        mask = bytes(int(sum(1 for y in range(cy * 8, cy * 8 + 8) for x in range(cx * 8, cx * 8 + 8)
                             if alpha.getpixel((x, y))) >= 20) for cy in range(25) for cx in range(25))
        hut_obj = 0x4D82D8

        def village(patched: bool) -> Hut:
            h = Hut(patched=patched, cloth=99)
            h.v.call(0x431190, hut_obj)                                     # the Clothing Hut's constructor
            h.v.w32(fe.PUZZLES + 8 * 0x16, 2000)                            # finished: its threshold (0x4386A0)
            h.v.w32(HUT_X, 400)
            h.v.w32(HUT_Y, 1600)
            h.v.uc.mem_write(fe.HEAP + 0x9000, mask)
            h.v.w32(hut_obj + 0x6C, fe.HEAP + 0x9000)                       # the mask 0x42FD20 keeps there
            h.v.w32(hut_obj + 0x74, 25)
            h.v.w32(hut_obj + 0x78, 25)
            h.v.w32(hut_obj + 0x34, 3)                                      # built (0x430A20 skips state 4)
            h.v.call(0x430A20, hut_obj)                                     # the game marks the hut's areas
            h.v.call(0x46E5E0, 0, 0x12, 0x46F600, 5, 0)                      # cdecl registrar
            h.v.w32(0x4D6F88, 10_000)                                       # tech points for new clothes
            h.v.w32(fe.GAME + 0x1719C, -1)
            return h

        def prompt(h: Hut, at) -> tuple[bool, bool]:
            h.v.w32(fe.GAME + 0x171A0, -1)
            r = h.villager(at=at, index=1)
            h.v.w32(r + 0x1C90, 77)
            for i in range(80):                                             # an empty queue for each drop
                h.v.w32(r + i * 0x58, 0)
            for lock in range(5, 9):                                        # the pit's spots free again
                h.v.w8(0x704E38 + 0x14 * lock, 0)
            h.v.w32(CLOTH, 99)                                              # cloth for every drop (one each)
            h.drop(r)
            return h.v.r32(fe.GAME + 0x171A0) == 77, (0x13, EV_CREDIT) in h.queue(r)

        h = village(True)
        hut_cells = [(x, y) for x in range(400 - 26, 400 + 71) for y in range(1600, 1800)
                     if x % 8 == 4 and y % 8 == 4 and h.v.call(0x46C410, fe.MAP, x, y) == 0x12]
        # The setup is real: the hut's drop area is there, and in these columns reaches below the box.
        self.assertGreater(len(hut_cells), 100)
        self.assertTrue(any(y - 1600 >= 135 for _, y in hut_cells))
        self.assertEqual(h.v.call(0x46C410, fe.MAP, 400 + 150, 1600 + 90), 0x12)
        points = [(400 + x, 1600 + y) for x in range(-26, 71, 6) for y in range(40, 135, 6)] + hut_cells
        for at in points:
            asked, sack = prompt(h, at)
            self.assertFalse(asked, at)
            self.assertTrue(sack, at)
        self.assertEqual(prompt(h, (400 + 150, 1600 + 90)), (True, False))   # the rest of the hut: the question
        stock = village(False)
        for at in [(400 + 20, 1600 + 90)] + [p for p in hut_cells if not 40 <= p[1] - 1600 < 135][:3]:
            self.assertEqual(prompt(stock, at), (True, False), at)          # the stock game asks there

    def test_making_the_sack_is_silent(self) -> None:
        # Owner, live (v2): no researching sounds.  0x469CD0 queues step type 0x19, a sound at the villager (the
        # Researching action's 1 and 0x67); the making queues none, only the working-pose waits (type 0x0A).
        h = Hut()
        r = h.villager()
        h.drop(r)
        q = h.queue(r)
        made = q.index((0x13, EV_MADE))
        self.assertNotIn(0x19, [t for t, _ in q[:made]])
        self.assertEqual([t for t, _ in q[:made]].count(0x0A), 2)

    def test_the_pit_spot_is_the_villagers_from_the_drop(self) -> None:
        def taken(h):
            return [k for k in range(5, 9) if h.v.call(0x46D880, 0x705148, k) & 0xFF]
        h = Hut()
        r = h.villager()
        self.assertEqual(taken(h), [])
        h.drop(r)
        self.assertEqual(len(taken(h)), 1)                         # claimed at once, before the making
        self.assertEqual(h.queue(r)[0][0], 0x2E)
        for _ in range(200):                                       # while the sack is made
            h.v.step_frame()
        self.assertEqual(len(taken(h)), 1)
        h.run()
        self.assertEqual(h.credits(), [30])

    def test_a_full_cooking_pit_refuses_and_uses_no_cloth(self) -> None:
        for patched in (True, False):
            with self.subTest(patched=patched):
                h = Hut(patched=patched)
                for lock in range(5, 9):                           # all four spots taken
                    h.v.call(0x46D530, 0x705148, lock)
                r = h.villager()
                h.drop(r)
                self.assertEqual(h.v.r32(CLOTH), 3)
                self.assertNotIn((0x13, EV_CREDIT), h.queue(r))
                if patched:
                    self.assertEqual(h.v.r32(r + REC_ACTION), 0x1A)   # the tree's own refusal, text 0x13C


@unittest.skipUnless(HAVE_EMULATOR, "the stock executable, its map and unicorn are needed")
class GrandFeastAndDoublerTests(unittest.TestCase):
    """The owner (2026-11-19): "for the grand stew berries and fruit harvested by cutting tools or sacks should
    count"; and an owned Food Point Doubler doubles a sack exactly once, as it does cutting-tool berries."""

    def test_the_sack_goes_into_the_feast_as_the_stock_fruit_trip_does(self) -> None:
        h = Hut()
        grand_feast(h.v)
        r = h.villager()
        self.assertEqual(h.drop(r), 1)
        self.assertEqual(h.v.r32(CLOTH), 2)
        carried: list[int] = []

        def watch(_f):
            item = h.v.r32(r + REC_ITEM)
            if not carried or carried[-1] != item:
                carried.append(item)
        h.run(watch=watch)
        self.assertEqual(feast_flags(h.v), (0, 0, 0, 1))          # the feast's fruit, at 0x42EAE7
        self.assertEqual(h.credits(), [])                         # no food: the fruit is the stew's
        self.assertNotIn(EV_CREDIT, h.events())
        self.assertNotIn(15, h.events())
        self.assertEqual([e for e in h.events() if e >= EV_MADE], [EV_MADE, EV_FULL, EV_STEW, EV_STEW_DONE])
        self.assertIn(0x37, carried)                              # the stew's fruit, as the stock trip carries it
        self.assertFalse(h.v.at_bin())
        # The model: the stock game's own fruit trip in the same village goes to the stew the same way.
        stock = Hut(patched=False)
        grand_feast(stock.v)
        stock.villager()
        stock.v.start(0x64)
        stock.run()
        self.assertEqual(feast_flags(stock.v), (0, 0, 0, 1))
        self.assertEqual(stock.credits(), [])

    def test_the_sack_in_the_stew_uses_up_the_trees_fruit_as_the_stock_stew_trip(self) -> None:
        # The owner (2026-11-19): "it should use up the berries and the fruit".  The sack's fruit goes into the pot
        # through the stew listener's fruit put-down 0x42EAE7 once -- where "Yellow Fruit Trees are No Longer
        # Unlimited" takes its 3 for any stewed fruit (tests/test_vv4_yellow_fruit_trees_limited.py,
        # test_a_stomped_fruit_put_in_the_stew_takes_three) -- and the sack takes nothing more itself, so the fruit
        # is used up once and no food is paid.  Without that row the tree is the stock unlimited one: the same one
        # put-down, as the stock fruit trip into the stew.
        def stewed(h) -> list[int]:
            seen: list[int] = []
            h.v.uc.hook_add(UC_HOOK_CODE, lambda *_: seen.append(1), begin=0x42EAE7, end=0x42EAE7)
            return seen
        for tree in (1000, None):
            with self.subTest(limited=tree is not None):
                h = Hut(tree=tree)
                grand_feast(h.v)
                seen = stewed(h)
                r = h.villager()
                self.assertEqual(h.drop(r), 1)
                h.run()
                self.assertEqual(len(seen), 1)                    # the fruit put in the stew once
                self.assertEqual(h.taken, [])                     # the sack itself takes no fruit
                self.assertEqual(h.credits(), [])                 # and pays no food
                if tree is not None:
                    self.assertEqual(h.tree, 1000)                # (the stand-in has no 0x42EAE7 hook)
        stock = Hut(patched=False)
        grand_feast(stock.v)
        seen = stewed(stock)
        stock.villager()
        stock.v.start(0x64)
        stock.run()
        self.assertEqual(len(seen), 1)

    def test_with_the_fruit_in_the_sack_goes_to_the_food_bin(self) -> None:
        h = Hut()
        grand_feast(h.v)
        h.v.w8(POT + FEAST_FLAGS + 3, 1)                          # the feast has its fruit already
        r = h.villager()
        h.drop(r)
        h.run()
        self.assertEqual(h.credits(), [30])
        self.assertTrue(h.v.at_bin())

    def test_the_stock_fruit_trip_is_kept_whole_before_the_sack_tail(self) -> None:
        # The pit spot's copy goes in before the trip is read: both of the trip's 0x2F steps stay (the tail used
        # to be cut one step early, taking one of them).
        stock = Hut(patched=False)
        sr = stock.villager()
        stock.v.start(0x64)
        q = [t for t, _ in stock.queue(sr)]
        h = Hut()
        r = h.villager()
        h.drop(r)
        sq = [t for t, _ in h.queue(r)]
        made = sq.index(0x13)                                     # SACK_EV_MADE, then its text
        stock_head = q[:len(q) - 1 - q[::-1].index(5)]            # the stock trip up to its last text
        self.assertEqual(sq[made + 2:made + 2 + len(stock_head)], stock_head)
        self.assertEqual(sq.count(0x2F), q.count(0x2F))           # none of the trip's 0x2F steps cut

    def test_the_sack_is_paid_from_the_cutting_tool_harvests_own_writer_call(self) -> None:
        # #805 doubles only whitelisted stock returns; the sack's 30 come from job event 14's own call (return
        # 0x464510, the cutting-tool berries), once, so an owned Food Point Doubler doubles it once.
        h = Hut()
        seen = food_writer_returns(h.v)
        r = h.villager()
        h.drop(r)
        h.run()
        self.assertEqual(seen, [HARVEST_CREDIT_RETURN])
        harvest = Hut(patched=False, berries=1000)
        stock_seen = food_writer_returns(harvest.v)
        harvest.v.w32(TOOLS, 3)
        t = harvest.villager(at=(1568, 1124))
        harvest.v.call(HARVEST_DROP, 0, 0, t)
        harvest.run()
        self.assertEqual(stock_seen, [HARVEST_CREDIT_RETURN])


class RowTests(unittest.TestCase):
    def test_the_rows_are_the_builders_and_pin_the_shipped_files(self) -> None:
        path = ROOT / "data" / f"{ID}_feature.json"
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), builder.row(builder.sha(DLL)))
        row = json.loads((ROOT / "data" / f"{ID}_feature.json").read_text(encoding="utf-8"))
        self.assertIn("**Needs no other patch.**", row["description"])
        self.assertIn("**On by default (and in Owner's Defaults).**", row["description"])
        self.assertEqual([f["destination"] for f in row["companion_files"]],
                         ["VVFP VV4 Cloth Sacks.dll", "Images/vvfp_sack_empty.png", "Images/vvfp_sack_yellow_fruit_raw.png",
                          "Images/vvfp_sack_yellow_fruit.png"])

    def test_vvfp_startup_starts_it(self) -> None:
        # The v1.35.97 merge: the second word is full, so the sack companions are third-word entries.
        self.assertIn("VVFP VV4 Cloth Sacks.dll", patcher.STARTUP_LOADER_COMPANIONS_3)
        header = (ROOT / "native" / "shared" / "startup_companions_3.h").read_text(encoding="utf-8")
        self.assertIn('"VVFP VV4 Cloth Sacks.dll"', header)

    def test_on_by_default_and_in_owners_defaults(self) -> None:
        # The owner (2026-11-18): "Cloth Sacks for Yellow Fruit must be ON BY DEFAULT".
        import vv_fun_patcher_gui as gui
        self.assertNotIn(ID, gui.DEFAULT_OFF_FUN_PATCH_IDS)
        self.assertNotIn(ID, gui.OWNERS_DEFAULT_OFF_FUN_PATCH_IDS)
        self.assertNotIn(ID, gui.SELECT_ALL_OFF_FUN_PATCH_IDS)

    def test_the_captions_fit_the_villagers_caption_field(self) -> None:
        source = (ROOT / "native" / "vvfp_vv4_cloth_sacks" / "vvfp_vv4_cloth_sacks.c").read_text(encoding="utf-8")
        for text in ("Making a sack out of cloth", "Gathering food in cloth sack"):
            self.assertIn(f'"{text}"', source)
            self.assertLessEqual(len(text), 38)
        strings = json.loads((ROOT / "data" / "translations" / "patcher_strings.json").read_text(encoding="utf-8"))
        english = json.dumps(strings)
        for text in ("Making a sack out of cloth", "Gathering food in cloth sack"):
            self.assertIn(text, english)


@unittest.skipUnless(HAVE_EMULATOR, "the stock executable, its map and unicorn are needed")
class RenderedTests(unittest.TestCase):
    def test_the_rendered_executable_keeps_every_site_stock_and_it_installs_in_every_mode(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                exe = render(mode)
                for va, stock, _ in builder.SITES:
                    self.assertEqual(exe[va - 0x400000:va - 0x400000 + len(stock) // 2].hex().upper(), stock)
                h = Hut(exe=exe)
                self.assertEqual(h.installed(), 1)
                r = h.villager()
                self.assertEqual(h.drop(r), 1)
                self.assertIn((0x13, EV_CREDIT), h.queue(r))


if __name__ == "__main__":
    unittest.main()
