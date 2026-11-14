"""Adults Dropped on Mushrooms or Collectibles Are Confused (all five games): vvN_adult_confused.

The owner (2026-11-14): "dropping a 14+ year old villager on a mushroom or collectible should give the 'confused'
behavior: 'only children can see and pick up mushrooms/collectibles'".  The adult does the game's own Confused
action and the status line says "Only children can see and pick up mushrooms." or "Only children can see and pick
up collectibles."; a child picks it up as before.

Everything below loads the SHIPPED "VVFP Adult Confused.dll" beside the stock executable (or the executable as the
patcher renders it with every other row) in unicorn (tests/story_emulator.py's Process), starts it as VVFP
Startup.dll does, and then runs the game's OWN drop code from the point where it has found what lies under the
villager:

* A New Home: from 0x4250FA (the drop's area tests), the map lookup 0x414200 answering the area; an adult on a
  mushroom (area 0x21) reaches the companion through 0x425168, a child goes on to the mushroom job 0x444500.
* The Lost Children: the adult dispatcher 0x42FB20 itself (its case 0x42FCAB for areas 0x2F / 0x30 reaches the
  companion); a child from 0x430C80 (the drop's child branch) to the mushroom job 0x45BCA0 / collectible job 0x45BF10.
* The Secret City, The Tree of Life, New Believers: the drop 0x42D2E0 / 0x4131A0 / 0x413660 from the point its object
  lists have answered (0x42D354 / 0x413219 / 0x4136DB, the item id in esi): the mushroom or collectible action is
  started through the do-action, which the companion takes for an adult.

Only the game routines the drop calls are stand-ins that record what they are asked (the do-action, the Confused
action, the status line, the clock, the map lookup, the jobs).  Not run here: the player's drag itself, the
Confused handler's animation steps and the live game (not yet verified in play).
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

import vv_fun_patcher as vfp  # noqa: E402

try:
    import pefile  # noqa: F401
    from story_emulator import RETURN, STACK_TOP, Process
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

STOCK = ROOT / "research" / "stock-executables"
NAMES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
MODES = ("stock", "collection_progression", "immediate_fixed")
DLL = ROOT / "assets" / "adult_confused" / "VVFP Adult Confused.dll"
DLL_NAME = "VVFP Adult Confused.dll"
ROW = "vv{}_adult_confused"
NAME = "Adults Dropped on Mushrooms or Collectibles Are Confused"
HAVE_STOCK = all((STOCK / f"Virtual Villagers - {n}.exe").is_file() for n in NAMES.values())
NEEDS = unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(),
                            "unicorn/pefile, the stock executables or the companion are missing")

MUSHROOMS = "Only children can see and pick up mushrooms."
COLLECTIBLES = "Only children can see and pick up collectibles."
ADULT, CHILD = 14 * 20, 14 * 20 - 1          # age units: 20 a year; a child is under 0x118
CLOCK = 100

# Every site the companion writes: (VA, stock bytes).
SITES = {
    1: [(0x425168, "E8E3EFFFFF")],
    2: [(0x42FCAE, "E8DD480200")],
    3: [(0x42D377, "E8F4810200"), (0x42D391, "E8DA810200")],
    4: [(0x41324C, "E86FAC0400"), (0x413266, "E855AC0400"), (0x413284, "E837AC0400")],
    5: [(0x413700, "E87B1E0500"), (0x41371A, "E8611E0500")],
}


def _exe(game: int) -> Path:
    return STOCK / f"Virtual Villagers - {NAMES[game]}.exe"


@functools.lru_cache(maxsize=None)
def _rendered(game: int, ids: tuple[str, ...], mode: str) -> bytes:
    build = next(b for b in vfp.load_builds() if b.id == f"vv{game}")
    data, _ = vfp.render_patched_bytes(_exe(game), build, mode, list(ids))
    return bytes(data)


def _others(game: int) -> list[str]:
    alts = set(vfp.ALTERNATIVE_FUN_PATCH_IDS)
    return [p.id for p in vfp.load_public_fun_patches()
            if p.game_id == f"vv{game}" and p.id not in alts and p.id != ROW.format(game)]


class Game:
    """The executable with the companion loaded (started unless `with_dll` is False: the stock game)."""

    def __init__(self, game: int, exe: bytes | None = None, *, with_dll: bool = True):
        self.game = game
        self.p = Process(exe if exe is not None else _exe(game).read_bytes(), DLL)
        self.calls: list[tuple[int, int, tuple[int, ...]]] = []
        self.installed = 0
        if with_dll:
            self.p.export("VvfpStartup", game, 0)
            self.installed = self.p.export("VvfpAdultConfusedInstalled")

    def stub(self, va: int, pop: int, result=0) -> None:
        def fn(p):
            args = tuple(p.arg(i) for i in range(4))
            ecx = p.reg("ecx")
            self.calls.append((va, ecx, args[:max(pop // 4, 0)] if pop else args))
            value = result(self, args, ecx) if callable(result) else result
            return value & 0xFFFFFFFF, pop
        self.p.stub(va, fn)

    def of(self, va: int) -> list[tuple[int, tuple[int, ...]]]:
        return [(ecx, args) for v, ecx, args in self.calls if v == va]

    def frame(self, values: dict[int, int]) -> int:
        """A stack at the drop's frame: `values` by offset from esp."""
        esp = STACK_TOP - 0x2000
        self.p.write(esp, bytes(0x100))
        for offset, value in values.items():
            self.p.put32(esp + offset, value)
        self.p.set_reg("esp", esp)
        return esp


# ---------------------------------------------------------------------------------------------------------------
# The Secret City, The Tree of Life, New Believers
# ---------------------------------------------------------------------------------------------------------------
LATER = {
    # resume point (esi = the item, [esp+0x20] the record), the queue clear the drop calls first (va, pop), the
    # do-action, the age field, the Confused action, the stock text, the selected test (VV3: a byte), the status
    # line and its show routine, the items: (id, the stock action, mushroom?)
    3: dict(resume=0x42D354, clear=(0x460F70, 4), do=0x455570, age=0xDC4, confused=0x2C, text=0x1A,
            selected=("byte", 0xF11), line=0x58F5E8, show=0x42E200, extra={},
            items=[(0x34, 0x30, False), (0x58, 0x30, False), (0x64, 0x2F, True), (0x65, 0x2F, True),
                   (0x66, 0x2F, True)]),
    4: dict(resume=0x413219, clear=(0x468C60, 0), do=0x45DEC0, age=0x1B8C, confused=0x1A, text=0x80,
            selected=("call", 0x45DD10), line=0x4DB8E8, show=0x44C3A0, extra={0x42DD60: 0},
            items=[(0x46, 0x1F, False), (0x6A, 0x1F, False), (0x76, 0x1E, True), (0x77, 0x1E, True),
                   (0x78, 0x1E, True)]),
    5: dict(resume=0x4136DB, clear=(0x473440, 0), do=0x465580, age=0x1B8C, confused=0x1F, text=0x76,
            selected=("call", 0x4653D0), line=0x520F68, show=0x44F0B0, extra={},
            items=[(0x50, 0x24, False), (0x68, 0x24, False), (0x80, 0x23, True), (0x81, 0x23, True),
                   (0x82, 0x23, True)]),
}


def later_drop(g: Game, item: int, age: int, *, selected: bool = True, stew: bool = False):
    """Run the drop from where it found `item` under a villager of `age`; what was started and shown."""
    r = LATER[g.game]
    record = g.p.alloc(0x2000)
    g.p.put32(record + r["age"], age)
    g.stub(r["clear"][0], r["clear"][1])
    g.stub(r["do"], 8, lambda gg, args, ecx: (gg.p.u32(args[1]), gg.p.u32(args[1] + 4))[0])
    g.stub(r["show"], 4)
    for va, value in r["extra"].items():
        g.stub(va, 0, 1 if stew else value)
    if r["selected"][0] == "byte":
        g.p.write(record + r["selected"][1], bytes([1 if selected else 0]))
    else:
        g.stub(r["selected"][1], 0, 1 if selected else 0)
    g.frame({0x1C: RETURN, 0x20: record})
    g.p.set_reg("esi", item)
    g.p.set_reg("edi", 0)
    g.p.run(r["resume"], RETURN)
    started = [(args[0], g.p.u32(args[1]), g.p.u32(args[1] + 4), ecx) for ecx, args in g.of(r["do"])]
    shown = [(ecx, g.p.cstring(args[0])) for ecx, args in g.of(r["show"])]
    return record, started, shown


@NEEDS
class LaterGamesTests(unittest.TestCase):
    def test_installs_on_the_stock_games(self):
        for game in (3, 4, 5):
            with self.subTest(game=game):
                g = Game(game)
                self.assertEqual(g.installed, 1)
                for va, stock in SITES[game]:
                    got = g.p.read(va, 5)
                    self.assertEqual(got[0], 0xE8)
                    self.assertNotEqual(got.hex().upper(), stock)
                    target = (va + 5 + struct.unpack("<i", got[1:])[0]) & 0xFFFFFFFF
                    self.assertTrue(g.p.dll_base <= target < g.p.dll_base + g.p.dll_size, hex(target))

    def test_an_adult_is_confused_and_told_why(self):
        for game in (3, 4, 5):
            r = LATER[game]
            for item, _action, mushroom in r["items"]:
                with self.subTest(game=game, item=hex(item)):
                    g = Game(game)
                    record, started, shown = later_drop(g, item, ADULT)
                    self.assertEqual(started, [(r["confused"], r["text"], 0xFFFFFFFF, record)])
                    self.assertEqual(shown, [(r["line"], MUSHROOMS if mushroom else COLLECTIBLES)])

    def test_the_line_is_left_alone_when_the_villager_is_not_the_selected_one(self):
        for game in (3, 4, 5):
            r = LATER[game]
            with self.subTest(game=game):
                g = Game(game)
                record, started, shown = later_drop(g, r["items"][2][0], ADULT, selected=False)
                self.assertEqual([s[0] for s in started], [r["confused"]])
                self.assertEqual(shown, [])

    def test_a_child_picks_up_as_before(self):
        for game in (3, 4, 5):
            r = LATER[game]
            for item, action, _mushroom in r["items"]:
                for with_dll in (True, False):
                    with self.subTest(game=game, item=hex(item), with_dll=with_dll):
                        g = Game(game, with_dll=with_dll)
                        record, started, shown = later_drop(g, item, CHILD)
                        self.assertEqual([(s[0], s[1], s[3]) for s in started], [(action, item, record)])
                        self.assertEqual(shown, [])

    def test_the_stock_game_starts_the_pick_for_an_adult_too(self):
        """Without the companion an adult gets the pick action, whose handler sends an adult straight out."""
        for game in (3, 4, 5):
            r = LATER[game]
            for item, action, _mushroom in r["items"]:
                with self.subTest(game=game, item=hex(item)):
                    g = Game(game, with_dll=False)
                    _record, started, shown = later_drop(g, item, ADULT)
                    self.assertEqual([s[0] for s in started], [action])
                    self.assertEqual(shown, [])

    def test_tree_of_life_stew_pot_take(self):
        """While a stew is being made a mushroom goes to the pot's take (0x90): a child as before, an adult confused."""
        g = Game(4)
        _record, started, _shown = later_drop(g, 0x76, CHILD, stew=True)
        self.assertEqual([s[:2] for s in started], [(0x90, 0x76)])
        g = Game(4)
        _record, started, shown = later_drop(g, 0x77, ADULT, stew=True)
        self.assertEqual([s[:2] for s in started], [(0x1A, 0x80)])
        self.assertEqual([s[1] for s in shown], [MUSHROOMS])


# ---------------------------------------------------------------------------------------------------------------
# A New Home
# ---------------------------------------------------------------------------------------------------------------
VV1_RECORD = 0x3D8


def vv1_drop(g: Game, age: int, area: int, slot: int = 3):
    screen = g.p.alloc(0x1000)
    villagers = g.p.alloc(0x40000)
    state = g.p.alloc(0x10000)
    label = g.p.alloc(0x100)
    g.p.put32(screen + 0x10, state)
    g.p.put32(screen + 0x14, g.p.alloc(0x100))
    g.p.put32(screen + 0x20, villagers)
    g.p.put32(screen + 0x294, slot)
    g.p.put32(screen + 0x350, label)
    record = villagers + slot * VV1_RECORD
    g.p.put32(record + 0x348, age)
    g.stub(0x414200, 8, area)                        # the map's area under the villager
    for va, pop in ((0x424150, 8), (0x444500, 4), (0x440040, 4), (0x40BB30, 4), (0x41C960, 8)):
        g.stub(va, pop)
    g.stub(0x402F70, 0, CLOCK)
    g.frame({})
    g.p.set_reg("esi", screen)
    g.p.set_reg("ebp", 0x118)
    g.p.set_reg("ebx", 0xC7)
    g.p.run(0x4250FA, 0x4252BE)
    return screen, villagers, label


@NEEDS
class NewHomeTests(unittest.TestCase):
    def test_installs_on_the_stock_game(self):
        g = Game(1)
        self.assertEqual(g.installed, 1)
        self.assertNotEqual(g.p.read(0x425168, 5).hex().upper(), SITES[1][0][1])

    def test_an_adult_on_a_mushroom_is_confused_and_told_why(self):
        g = Game(1)
        screen, villagers, label = vv1_drop(g, ADULT, 0x21)
        self.assertEqual(g.of(0x440040), [(villagers, (3,))])
        self.assertEqual([(ecx, g.p.cstring(a[0])) for ecx, a in g.of(0x40BB30)], [(label, MUSHROOMS)])
        self.assertEqual(g.p.u32(screen + 0x284), CLOCK + 5)
        self.assertEqual(g.of(0x424150), [])
        self.assertEqual(g.of(0x444500), [])

    def test_an_adult_anywhere_else_goes_on_as_before(self):
        for area in (0x2, 0xF, 0x20, 0x22):
            with self.subTest(area=hex(area)):
                g = Game(1)
                screen, _villagers, _label = vv1_drop(g, ADULT, area)
                self.assertEqual(g.of(0x424150), [(screen, (3, area))])
                self.assertEqual(g.of(0x440040), [])

    def test_a_child_picks_the_mushroom_as_before(self):
        for with_dll in (True, False):
            with self.subTest(with_dll=with_dll):
                g = Game(1, with_dll=with_dll)
                _screen, villagers, _label = vv1_drop(g, CHILD, 0x21)
                self.assertEqual(g.of(0x444500), [(villagers, (3,))])
                self.assertEqual(g.of(0x440040), [])
                self.assertEqual(g.of(0x40BB30), [])

    def test_the_stock_game_leaves_the_adult_standing(self):
        g = Game(1, with_dll=False)
        screen, _villagers, _label = vv1_drop(g, ADULT, 0x21)
        self.assertEqual(g.of(0x424150), [(screen, (3, 0x21))])   # whose case 0x21 is the empty default
        self.assertEqual(g.of(0x440040), [])


# ---------------------------------------------------------------------------------------------------------------
# The Lost Children
# ---------------------------------------------------------------------------------------------------------------
VV2_RECORD = 0xE48C


def vv2_world(g: Game, age: int, slot: int = 3):
    screen = g.p.alloc(0x1000)
    villagers = g.p.alloc(0xE58000)
    state = g.p.alloc(0x40000)
    label = g.p.alloc(0x100)
    g.p.put32(screen + 0x10, state)
    g.p.put32(screen + 0x14, g.p.alloc(0x100))
    g.p.put32(screen + 0x20, villagers)
    g.p.put32(screen + 0x1E4, slot)
    g.p.put32(screen + 0x2BC, label)
    g.p.put32(villagers + slot * VV2_RECORD + 0x530, age)
    for va, pop in ((0x454590, 8), (0x40C510, 4), (0x45BCA0, 4), (0x45BF10, 4)):
        g.stub(va, pop)
    g.stub(0x403200, 0, CLOCK)
    return screen, villagers, label


@NEEDS
class LostChildrenTests(unittest.TestCase):
    def test_installs_on_the_stock_game(self):
        g = Game(2)
        self.assertEqual(g.installed, 1)
        self.assertNotEqual(g.p.read(0x42FCAE, 5).hex().upper(), SITES[2][0][1])

    def test_an_adult_is_confused_and_told_why(self):
        for area, words in ((0x2F, MUSHROOMS), (0x30, COLLECTIBLES)):
            with self.subTest(area=hex(area)):
                g = Game(2)
                screen, villagers, label = vv2_world(g, ADULT)
                g.p.call(0x42FB20, [3, area], ecx=screen)
                # the game's own Confused action, with no text queued (0: the queue stores nothing)
                self.assertEqual(g.of(0x454590), [(villagers, (3, 0))])
                self.assertEqual([(ecx, g.p.cstring(a[0])) for ecx, a in g.of(0x40C510)], [(label, words)])
                self.assertEqual(g.p.u32(screen + 0x1D4), CLOCK + 5)

    def test_the_stock_game_says_collectibles_for_both(self):
        for area in (0x2F, 0x30):
            with self.subTest(area=hex(area)):
                g = Game(2, with_dll=False)
                screen, villagers, _label = vv2_world(g, ADULT)
                g.p.call(0x42FB20, [3, area], ecx=screen)
                self.assertEqual(g.of(0x454590), [(villagers, (3, 0x2B))])
                self.assertEqual(g.of(0x40C510), [])

    def test_the_other_confused_cases_are_unchanged(self):
        """Case 0x3D of the same dispatcher starts Confused with its own text (0x28): passed through as it was."""
        g = Game(2)
        screen, villagers, _label = vv2_world(g, ADULT)
        g.p.write(g.p.u32(screen + 0x10) + 0x30459, b"\0")
        g.p.call(0x42FB20, [3, 0x3D], ecx=screen)
        self.assertEqual(g.of(0x454590), [(villagers, (3, 0x28))])
        self.assertEqual(g.of(0x40C510), [])

    def test_a_child_picks_up_as_before(self):
        for area, job in ((0x2F, 0x45BCA0), (0x30, 0x45BF10)):
            for with_dll in (True, False):
                with self.subTest(area=hex(area), with_dll=with_dll):
                    g = Game(2, with_dll=with_dll)
                    screen, villagers, _label = vv2_world(g, CHILD)
                    g.stub(0x4181D0, 8, area)
                    g.frame({})
                    g.p.set_reg("esi", screen)
                    g.p.run(0x430C80, 0x430F63)
                    self.assertEqual(g.of(job), [(villagers, (3,))])
                    self.assertEqual(g.of(0x454590), [])


# ---------------------------------------------------------------------------------------------------------------
# All five: every stock byte checked, every other patch, the row
# ---------------------------------------------------------------------------------------------------------------
@NEEDS
class InstallTests(unittest.TestCase):
    def test_a_changed_site_or_checked_byte_installs_nothing(self):
        for game in range(1, 6):
            for va, _bytes in SITES[game]:
                for at in (va, va - 2):
                    with self.subTest(game=game, va=hex(at)):
                        g = Game(game, with_dll=False)
                        g.p.write(at, bytes([g.p.read(at, 1)[0] ^ 0xFF]))
                        g.p.export("VvfpStartup", game, 0)
                        self.assertEqual(g.p.export("VvfpAdultConfusedInstalled"), 0)
                        for other, stock_bytes in SITES[game]:
                            if other != va:
                                self.assertEqual(g.p.read(other, 5).hex().upper(), stock_bytes)

    def test_with_every_other_patch_in_every_mode(self):
        for game in range(1, 6):
            others = _others(game)
            self.assertGreater(len(others), 10)
            for mode in MODES:
                exe = _rendered(game, tuple(others + [ROW.format(game)]), mode)
                with self.subTest(game=game, mode=mode):
                    g = Game(game, exe)
                    self.assertEqual(g.installed, 1)
                    if game >= 3:
                        r = LATER[game]
                        record, started, shown = later_drop(g, r["items"][2][0], ADULT)
                        self.assertEqual([s[0] for s in started], [r["confused"]])
                        self.assertEqual([s[1] for s in shown], [MUSHROOMS])
                        g = Game(game, exe)
                        record, started, shown = later_drop(g, r["items"][0][0], CHILD)
                        self.assertEqual([s[0] for s in started], [r["items"][0][1]])
                    elif game == 1:
                        _screen, villagers, _label = vv1_drop(g, ADULT, 0x21)
                        self.assertEqual(g.of(0x440040), [(villagers, (3,))])
                    else:
                        screen, villagers, _label = vv2_world(g, ADULT)
                        g.p.call(0x42FB20, [3, 0x30], ecx=screen)
                        self.assertEqual(g.of(0x454590), [(villagers, (3, 0))])

    def test_no_other_row_writes_a_site_or_the_code_it_checks(self):
        """No row's executable patch or runtime detour touches the five bytes of a site (Collectibles Stay
        Collected's included: its sites are elsewhere in each game)."""
        rows = [p for p in vfp.load_public_fun_patches() if not p.id.endswith("_adult_confused")]
        data = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
        by_id = {r["id"]: r for r in data["fun_patches"]}
        for game in range(1, 6):
            ranges = [(va, va + 5) for va, _ in SITES[game]]
            image_base = 0x400000
            pe = pefile.PE(str(_exe(game)), fast_load=True)
            for row in rows:
                if row.game_id != f"vv{game}":
                    continue
                spec = by_id.get(row.id, {})
                for d in spec.get("runtime_detours", []):
                    va = int(d["va"], 16)
                    n = len(d["stock_bytes"]) // 2
                    for lo, hi in ranges:
                        self.assertFalse(va < hi and lo < va + n, (row.id, d["va"]))
                for p in spec.get("patches", []):
                    va = pe.get_rva_from_offset(int(p["offset"], 16)) + image_base
                    n = len(p["before"]) // 2
                    for lo, hi in ranges:
                        self.assertFalse(va < hi and lo < va + n, (row.id, p["offset"]))

    def test_the_rows(self):
        for game in range(1, 6):
            row = next(p for p in vfp.load_public_fun_patches() if p.id == ROW.format(game))
            with self.subTest(game=game):
                self.assertEqual(row.name, NAME)
                self.assertIn(DLL_NAME, row.description)
                self.assertIn("**", row.description)
                self.assertIn(DLL_NAME, vfp.STARTUP_LOADER_COMPANIONS_2)


if __name__ == "__main__":
    unittest.main()
