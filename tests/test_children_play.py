"""Children Play Tag and Build Sandcastles (all five games; "VVFP Children Play.dll").

The owner (2026-11-14): "children should be able to play tag and build sandcastles in VV1-VV4"; "the children should
build sandcastles near the ocean in each game if they don't already do that"; tag is a normal play choice like
sandcastles; "all children should participate in tag. Same rules as VV2 or whatever games have them natively. Same for
making sandcastles."

EMULATED, on the executable the patcher renders for each game's row, with the companion started as VVFP Startup.dll
starts it (VvfpStartup(game, ...)).  Each pick is made through the game's own call site of the child pastime pick
(the `call` the companion takes over), with the game's rand answered by a seeded generator; the stock pick and the
game routines the new choices call (stop, do-action, queue, walk ...) are stood in for and record what they are given,
so the test sees exactly what the companion asks of the game:

* the new choices come up one pick in 15 each, statistically, over many picks; every other pick is the stock pick,
  called with the same arguments, and the stock pick's bytes are the stock game's (its own odds untouched);
* a child who dislikes Playing (and A New Home's Golden Child) always gets the stock pick;
* tag needs two players or more and takes every child The Lost Children's rule takes, the starter "It";
* sandcastles walk only to the beach places at the water and bend over there;
* without the row nothing is installed and the call sites are stock; with a call site not stock, nothing at all.
The all-or-none install and the whole catalog are tests/test_companion_installs_all_or_none.py ("Children Play").
"""
from __future__ import annotations

import json
import math
import random
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

try:
    from test_companion_installs_all_or_none import HAVE_EMULATOR, Machine, render, stock_path, with_requirements
    from story_emulator import STACK_TOP
    from story_custom_fixtures import Village
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

DLL = ROOT / "assets" / "children_play" / "VVFP Children Play.dll"
MODES = ("stock", "collection_progression", "immediate_fixed")

PICK = {1: 0x4479B0, 2: 0x45EE00, 3: 0x45B9B0, 4: 0x465260, 5: 0x46E3F0}
SITES = {1: (0x448299,), 2: (0x4618C9,), 3: (0x45C16A, 0x45BDC9, 0x4269C9), 4: (0x4658D7,), 5: (0x46F125,)}
RAND = {1: 0x402F10, 2: 0x4031A0, 3: 0x4032D0, 4: 0x4036D0, 5: 0x403660}
DISLIKES = {2: (0x6E8, 62), 3: (0xFC0, 3), 4: (0x1E6C, 3), 5: (0x1F68, 3)}
PLAYING = 0x12
SLOTS = 15

# The beach places at the water (x lo, x hi, y lo, y hi).
VV1_BEACH = [(480, 591, 1503, 1557), (600, 711, 1530, 1614), (369, 480, 1452, 1539)]
VV2_BEACH = [(217, 256, 878, 917), (142, 181, 878, 917), (145, 184, 752, 791)]
RUNNING = [(0x3B4, 0x20, 0x3B8, 0x20), (0x2F5, 0x1E, 0x3C5, 0x20), (0x2CB, 0x1E, 0x428, 0x20),
           (0x3A4, 0x22, 0x4AD, 0x24), (0x41C, 0x24, 0x428, 0x24), (0x3DA, 0x24, 0x3EB, 0x26)]


class Game:
    """One game's rendered executable with the companion, a village and the stand-ins."""

    def __init__(self, test: unittest.TestCase, game: int, mode: str = "stock", seed: int = 1):
        self.game = game
        exe = render(game, with_requirements(game, [f"vv{game}_children_play"]), mode)
        self.exe = exe
        self.m = Machine(exe, DLL)
        self.v = Village(self.m, f"vv{game}")
        self.rng = random.Random(seed)
        self.scripted: list[int] = []
        self.calls: list[tuple] = []
        m = self.m

        def rand(p):
            n = p.arg(0)
            value = self.scripted.pop(0) if self.scripted else self.rng.randrange(n)
            self.calls.append(("rand", n, value))
            assert 0 <= value < n
            return value, 0
        m.stub(RAND[game], rand)

        def record(name, pop, nargs, ret=0, *, this=True):
            def fn(p):
                self.calls.append((name, p.reg("ecx") if this else None) + tuple(p.arg(i) for i in range(nargs)))
                return ret, pop
            return fn
        if game in (1, 2, 3):
            m.stub(PICK[game], record("stock", 4, 1, 0x55))
        else:
            m.stub(PICK[game], record("stock", 0, 0, 0x55))
        if game == 1:
            m.stub(0x439470, record("stop", 4, 1))
            m.stub(0x4399F0, record("queue", 0x1C, 7))
        if game == 2:
            m.stub(0x455CF0, record("stock_tag", 4, 1))
            m.stub(0x4492A0, record("stop", 4, 1))
            m.stub(0x449B70, record("queue", 0x1C, 7))
        if game in (3, 4):
            strings = m.alloc(0x40)
            self.words = {}
            text = m.alloc(0x200)
            for k, (sid, words) in enumerate(((0x190 if game == 3 else 0x1EB, "Playing tag"),
                                              (0x191 if game == 3 else 0x1EC, 'Playing tag - "It" '))):
                m.write(text + 0x40 * k, words.encode() + b"\0")
                self.words[sid] = text + 0x40 * k
            getter, lookup = (0x42F740, 0x42F190) if game == 3 else (0x44DA20, 0x44D3D0)
            m.stub(getter, lambda p: (strings, 0))

            def lookup_fn(p):
                assert p.reg("ecx") == strings
                return self.words.get(p.arg(0), 0), 4
            m.stub(lookup, lookup_fn)
            if game == 3:
                m.stub(0x460F70, record("stop", 4, 1))
                m.stub(0x455570, record("act", 8, 2))
                m.stub(0x4611B0, record("walk", 0x10, 4))
                m.stub(0x461B50, record("last", 0x10, 4))
                m.stub(0x461BF0, record("start", 4, 1))
            else:
                m.stub(0x468C60, record("stop", 0, 0))
                m.stub(0x45DEC0, record("act", 8, 2))
                m.stub(0x469050, record("walk", 0x10, 4))
                m.stub(0x469EC0, record("last", 0x10, 4))
                m.stub(0x46A030, record("start", 0, 0))
        if game == 5:
            self.children = 4
            self.joined = 3
            m.stub(0x471450, lambda p: (self.calls.append(("children", p.reg("ecx"))) or (self.children, 0)))

            def recruit(p):
                args = tuple(p.arg(i) for i in range(8))
                self.calls.append(("recruit", p.reg("ecx")) + args)
                p.put32(args[5], self.joined)
                return 0, 0x20
            m.stub(0x4710B0, recruit)
            m.stub(0x465580, record("do", 8, 2))
        m.export("VvfpStartup", game, 0)
        test.assertEqual(m.export("VvfpChildrenPlayInstalled"), 1)
        self.ai = m.alloc(0x2000)

    # ---- villagers ------------------------------------------------------------------------------------------------
    def kid(self, i: int, years: float = 6, **kw) -> int:
        r = self.v.put(i, sex="m" if i % 2 else "f", years=years, name=f"Kid{i}")
        L = {1: dict(carried=(0x3C, 0x13)), 2: dict(carried=(0x44, 0x1A)), 3: dict(carried=(0xF20, -1)),
             4: dict(carried=(0x1CDC, -1)), 5: dict(carried=None)}[self.game]
        off, nothing = L["carried"] or (None, None)
        if off is not None:
            self.m.write(r + off, struct.pack("<i", nothing))
        if kw.get("dislikes"):
            self.dislike(r)
        if kw.get("sick"):
            if self.game in (1, 2):
                self.m.put32(r + {1: 0x354, 2: 0x53C}[self.game], 1)
            else:
                self.m.write(r + {3: 0xE89, 4: 0x1C48}[self.game], b"\1")
        if kw.get("carrying"):
            self.m.write(r + off, struct.pack("<i", 3))
        if kw.get("golden"):
            self.m.put32(r + 0x36C, 0xC7)
        if kw.get("chief"):
            self.m.write(r + 0xE80, b"\1")
        return r

    def dislike(self, r: int) -> None:
        off, slots = DISLIKES[self.game]
        self.m.put32(r + off, PLAYING)

    # ---- one pick through the game's own call site ----------------------------------------------------------------
    def pick(self, i: int, site: int | None = None) -> int:
        m, g = self.m, self.game
        site = SITES[g][0] if site is None else site
        r = self.v.record(i)
        esp = STACK_TOP - 0x3000
        if g in (1, 2):
            esp -= 4
            m.put32(esp, i)
            m.set_reg("ecx", self.v.array)
        elif g == 3:
            esp -= 4
            m.put32(esp, r)
            m.set_reg("ecx", r)
        else:
            m.put32(self.ai + 0x1B88, r)
            m.set_reg("ecx", self.ai)
        m.set_reg("esp", esp)
        m.run(site, site + 5)
        assert m.reg("esp") == esp + (4 if g in (1, 2, 3) else 0), "the call pops what the stock pick pops"
        return m.reg("eax")

    def take(self) -> list[tuple]:
        out, self.calls = self.calls, []
        return out


def outcome(game: int, calls: list[tuple]) -> str:
    names = [c[0] for c in calls]
    if "stock" in names:
        return "stock"
    if game == 2 and "stock_tag" in names:
        return "tag"
    if game == 5 and "recruit" in names:
        return "tag"
    if game in (3, 4) and "act" in names:
        return "tag"
    if game == 1 and "stop" in names:
        return "tag"
    if "queue" in names:
        return "sand"
    return "none"


@unittest.skipUnless(HAVE_EMULATOR, "pefile/unicorn not installed")
class ChildrenPlay(unittest.TestCase):
    def setUp(self) -> None:
        if not DLL.is_file():
            self.skipTest("companion not built")
        for game in range(1, 6):
            if not stock_path(game).is_file():
                self.skipTest("stock executables not present")

    def test_new_choices_come_up_one_pick_in_fifteen(self) -> None:
        picks = 3000
        new = {1: ("tag", "sand"), 2: ("tag", "sand"), 3: ("tag",), 4: ("tag",), 5: ("tag",)}
        for game in range(1, 6):
            with self.subTest(game=game):
                g = Game(self, game, seed=game)
                for i in (3, 4, 5):
                    g.kid(i)
                counts = {"stock": 0, "tag": 0, "sand": 0, "none": 0}
                for n in range(picks):
                    g.pick(3)
                    counts[outcome(game, g.take())] += 1
                self.assertEqual(counts["none"], 0)
                p = 1 / SLOTS
                sigma = math.sqrt(picks * p * (1 - p))
                for choice in new[game]:
                    self.assertLess(abs(counts[choice] - picks * p), 5 * sigma, (game, counts))
                expected_stock = picks * (SLOTS - len(new[game])) / SLOTS
                self.assertLess(abs(counts["stock"] - expected_stock), 5 * math.sqrt(picks * 0.12), (game, counts))
                for choice in ("tag", "sand"):
                    if choice not in new[game]:
                        self.assertEqual(counts[choice], 0, (game, counts))

    def test_the_stock_pick_is_the_stock_games_own_and_keeps_its_arguments(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                stock = stock_path(game).read_bytes()
                g = Game(self, game)
                off = PICK[game] - 0x400000
                self.assertEqual(g.exe[off:off + 0x400], stock[off:off + 0x400], "the pick's own code is stock")
                g.kid(3)
                for _ in range(40):
                    g.scripted = [SLOTS - 1]          # past every new slot
                    g.pick(3)
                    calls = g.take()
                    self.assertEqual(outcome(game, calls), "stock")
                    stock_call = [c for c in calls if c[0] == "stock"][0]
                    if game in (1, 2):
                        self.assertEqual(stock_call[1:], (g.v.array, 3))
                    elif game == 3:
                        self.assertEqual(stock_call[1:], (g.v.record(3), g.v.record(3)))
                    else:
                        self.assertEqual(stock_call[1:], (g.ai,))

    def test_disliking_playing_blocks_both_and_the_golden_child_keeps_his_own_branch(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                g = Game(self, game)
                g.kid(4)
                g.kid(5)
                if game == 1:
                    g.kid(3, golden=True)
                else:
                    g.kid(3, dislikes=True)
                for _ in range(200):
                    g.pick(3)
                    calls = g.take()
                    self.assertEqual(outcome(game, calls), "stock")
                    self.assertFalse([c for c in calls if c[0] == "rand"], "no roll is made for them")

    def test_tag_takes_every_child_the_lost_childrens_rule_takes(self) -> None:
        for game in (1, 3, 4):
            with self.subTest(game=game):
                g = Game(self, game)
                players = [g.kid(3), g.kid(4), g.kid(5)]
                g.kid(6, sick=True)
                g.kid(7, carrying=True)
                g.v.put(8, sex="f", years=30, name="Adult")
                g.kid(9, years=6)
                g.m.put32(g.v.record(9) + {1: 0x344, 3: 0xE78, 4: 0x1C40}[game], 0)   # a body
                if game in (3, 4):
                    g.kid(10, dislikes=True)
                if game == 3:
                    g.kid(11, chief=True)
                if game == 1:
                    players.append(g.kid(12, golden=True))
                g.scripted = [0]
                self.assertEqual(g.pick(4), 1)
                calls = g.take()
                stopped = [c for c in calls if c[0] == "stop"]
                if game == 1:
                    self.assertEqual(sorted(c[2] for c in stopped), [3, 4, 5, 12])
                    texts = {i: g.m.cstring(g.v.record(i) + 0x314) for i in (3, 4, 5, 12)}
                    self.assertEqual(texts[4], 'Playing tag - "It" ')
                    self.assertEqual({texts[i] for i in (3, 5, 12)}, {"Playing tag"})
                    for i in (6, 7, 8, 9):
                        self.assertEqual(g.m.cstring(g.v.record(i) + 0x314), "")
                    walks = [c for c in calls if c[0] == "queue" and c[3] == 3]
                    self.assertEqual(len(walks), 4 * 4)
                    for c in walks:
                        self.assertEqual(c[1], g.v.array)
                        _, _, _i, _s, x, y, p3, mode, speed = c
                        self.assertTrue(845 <= x < 965 and 659 <= y < 779, c)
                        self.assertEqual((p3, mode, speed), (0, 0, 150))
                    pauses = [c for c in calls if c[0] == "queue" and c[3] == 5]
                    self.assertEqual(len(pauses), 16)
                    self.assertTrue(all(10 <= c[6] <= 13 for c in pauses))
                else:
                    acts = [c for c in calls if c[0] == "act"]
                    who = [c[1] for c in acts]
                    self.assertEqual(sorted(who), sorted(players))
                    self.assertEqual(who[0], g.v.record(4), "the starter first")
                    self.assertTrue(all(c[2] == (0x94 if game == 3 else 0x46) for c in acts), "Running around")
                    self.assertEqual(len(stopped), 2 * len(players), "stopped before and after Running around")
                    text = 0xF28 if game == 3 else 0x1CE4
                    self.assertEqual(g.m.cstring(g.v.record(4) + text), 'Playing tag - "It" ')
                    for r in players:
                        if r != g.v.record(4):
                            self.assertEqual(g.m.cstring(r + text), "Playing tag")
                    walks = [c for c in calls if c[0] == "walk"]
                    self.assertEqual(len(walks), 6 * len(players))
                    order = None
                    for k, r in enumerate(players):
                        mine = [c for c in walks if c[1] == r]
                        places = []
                        for c in mine:
                            _, _, x, y, speed, flag = c
                            self.assertEqual((speed, flag), (150, 0))
                            place = [n for n, (xb, xs, yb, ys) in enumerate(RUNNING)
                                     if xb <= x < xb + xs and yb <= y < yb + ys]
                            self.assertEqual(len(place), 1, c)
                            places.append(place[0])
                        self.assertEqual(sorted(places), list(range(6)))
                        order = places if order is None else order
                        self.assertEqual(places, order, "one order shared by every player")
                    lasts = [c for c in calls if c[0] == "last"]
                    self.assertEqual({c[2:] for c in lasts}, {(1, 0, 1, 0) if game == 3 else (1, 4, 1, 0)})
                    self.assertEqual(sorted(c[1] for c in calls if c[0] == "start"), sorted(players))

    def test_tag_needs_two_players(self) -> None:
        for game in (1, 3, 4):
            with self.subTest(game=game):
                g = Game(self, game)
                g.kid(3)
                g.kid(4, sick=True)
                g.v.put(5, sex="f", years=30, name="Adult")
                g.scripted = [0]
                g.pick(3)
                self.assertEqual(outcome(game, g.take()), "stock")

    def test_the_lost_children_and_new_believers_start_their_own_tag(self) -> None:
        g = Game(self, 2)
        g.kid(3)
        g.scripted = [0]
        self.assertEqual(g.pick(3), 1)
        calls = g.take()
        self.assertEqual([c for c in calls if c[0] == "stock_tag"], [("stock_tag", g.v.array, 3)])
        g = Game(self, 5)
        r = g.kid(3)
        for children, joined, started in ((4, 3, True), (4, 1, False), (10, 2, True)):
            g.children, g.joined = children, joined
            g.scripted = [0]
            self.assertEqual(g.pick(3), 1)
            calls = g.take()
            recruit = [c for c in calls if c[0] == "recruit"][0]
            self.assertEqual(recruit[0:2], ("recruit", 0x554148))
            self.assertEqual(recruit[2:7] + recruit[8:], (0xEE, 0x50, 0, 0x117, 0xFFFFFFFF, 2, children * 75 // 100))
            do = [c for c in calls if c[0] == "do"]
            self.assertEqual(len(do), 1 if started else 0)
            if started:
                self.assertEqual(do[0][1:3], (r, 0xEE))

    def test_sandcastles_go_to_the_beach_at_the_water(self) -> None:
        for game, beach, text in ((1, VV1_BEACH, 0x314), (2, VV2_BEACH, 0x4FC)):
            with self.subTest(game=game):
                g = Game(self, game, seed=7)
                g.kid(3)
                used = set()
                for _ in range(60):
                    g.scripted = [1]
                    self.assertEqual(g.pick(3), 1)
                    calls = g.take()
                    queue = [c for c in calls if c[0] == "queue"]
                    self.assertTrue(all(c[1] == g.v.array and c[2] == 3 for c in queue))
                    walks = [c for c in queue if c[3] == 3]
                    self.assertEqual(len(walks), 6)
                    place = None
                    for c in walks:
                        x, y, speed = c[4], c[5], c[8]
                        found = [n for n, (x0, x1, y0, y1) in enumerate(beach) if x0 <= x <= x1 and y0 <= y <= y1]
                        self.assertTrue(found, c)
                        place = found[0] if place is None else place
                        self.assertIn(place, found, "one place for the whole play")
                        self.assertEqual(speed, 100)
                    used.add(place)
                    bends = [c for c in queue if c[3] == 2 and c[8] == 1]
                    self.assertEqual(len(bends), 12, "twice bent over each round")
                    self.assertTrue(all(10 <= c[6] <= 29 for c in bends))
                    self.assertEqual(g.m.cstring(g.v.record(3) + text), "Making sandcastles")
                    self.assertFalse([c for c in calls if c[0] in ("stop", "stock", "stock_tag")])
                self.assertEqual(used, {0, 1, 2})

    def test_every_call_site_and_the_potion(self) -> None:
        g = Game(self, 3)
        g.kid(3)
        g.kid(4)
        for site in SITES[3]:
            g.scripted = [0]
            g.pick(3, site)
            self.assertEqual(outcome(3, g.take()), "tag", hex(site))

    def test_without_the_row_nothing_changes(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                stock = stock_path(game).read_bytes()
                for mode in MODES:
                    exe = render(game, (), mode)
                    for site in SITES[game]:
                        off = site - 0x400000
                        self.assertEqual(exe[off:off + 5], stock[off:off + 5])
                # A call site that is not the stock call: nothing is installed.
                exe = bytearray(render(game, with_requirements(game, [f"vv{game}_children_play"]), "stock"))
                off = SITES[game][-1] - 0x400000
                exe[off + 1] ^= 1
                m = Machine(bytes(exe), DLL)
                before = m.image()
                m.export("VvfpStartup", game, 0)
                self.assertEqual(m.export("VvfpChildrenPlayInstalled"), 0)
                self.assertEqual(m.image(), before)

    def test_the_rows(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                row = json.loads((ROOT / "data" / f"vv{game}_children_play_feature.json").read_text("utf-8"))
                self.assertEqual(row["patches"], [])
                self.assertEqual(row["dependencies"], [])
                self.assertEqual([d["va"] for d in row["runtime_detours"]], [f"0x{s:X}" for s in SITES[game]])
                stock = stock_path(game).read_bytes()
                text = stock[0x1000:0x90000]
                callers = [0x401000 + i for i in range(len(text) - 5) if text[i] == 0xE8
                           and (0x401000 + i + 5 + struct.unpack_from("<i", text, i + 1)[0]) & 0xFFFFFFFF == PICK[game]]
                self.assertEqual(callers, sorted(SITES[game]), "every call of the pick")
                for d in row["runtime_detours"]:
                    off = int(d["va"], 16) - 0x400000
                    self.assertEqual(stock[off:off + 5].hex().upper(), d["stock_bytes"])
                self.assertIn("**On by default.**", row["description"])


@unittest.skipUnless(HAVE_EMULATOR, "pefile/unicorn not installed")
class Defaults(unittest.TestCase):
    def test_on_by_default_and_in_owners_defaults(self) -> None:
        from vv_fun_patcher_gui import (default_fun_patch_selection, owners_default_fun_patch_selection,
                                        select_all_fun_patch_selection)
        for game in range(1, 6):
            row = f"vv{game}_children_play"
            self.assertTrue(default_fun_patch_selection(row))
            self.assertTrue(owners_default_fun_patch_selection(row))
            self.assertTrue(select_all_fun_patch_selection(row))


if __name__ == "__main__":
    unittest.main()
