"""The baby is born, then the parent dies (docs/event-collection/cie-v6-binary.md section 23), in all five games.

The test build of "VVFP Story Upgrades.dll" runs beside each game's rendered executable in the emulator, as
tests/test_story_cie_graph_runtime_v6.py does -- and here the effect runs the GAME'S OWN catch-up for real (A New
Home 0x42E900 and The Lost Children 0x43B690 on a tick object from their own constructors, The Secret City 0x45FFE0,
The Tree of Life 0x468430, New Believers 0x472C90), with its real delivery and real villager creators.  Only what an
emulator cannot run is stood in for: the game's random routine (always its top value, so no random harm), the C
runtime's per-thread block, the heap, and two lazy singletons the catch-up never reads.

* an early birth: the baby is its own villager record after the parent's death, aged the nursing units already gone
  by, with the health deficit (round(50 x the share still to come), 5..50); the parent is dead (health 0), no longer
  nursing; the Cause of Death companion is told the babies were born BEFORE the death; one log line;
* twins and triplets (the game's own chain: every baby the same age and deficit);
* a full-term birth (no deficit, the game's 40 units) and the earliest one (age 1, deficit 50);
* the newborn takes a record freed by a death (the slots are the game's: a reused one);
* The Lost Children to New Believers: the child carries its own parents, as the delivery writes them;
* a parent no longer nursing just dies; a delivery the game does not make is a refusal and nobody dies.
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

from test_story_custom_island_event import HAVE_EMULATOR, emulated, have_stock  # noqa: E402

if HAVE_EMULATOR:
    from unicorn import UC_HOOK_CODE

    import test_story_cie_graph_runtime_v6 as v6

GAME_IDS = ("vv1", "vv2", "vv3", "vv4", "vv5")
# Each game's random routine (cdecl rand(n)), as its catch-up calls it ("push 0x64; call").
RAND = {"vv1": 0x402F10, "vv2": 0x4031A0, "vv3": 0x4032D0, "vv4": 0x4036D0, "vv5": 0x403660}
# Lazy singletons the catch-up reaches that the emulator's village has none of: (va, bytes popped, size of the
# zeroed object handed back, 0 = NULL).  A New Home / The Lost Children: the tick object's +0xC (never read by the
# tick); The Secret City: the world the catch-up reads its speed from; New Believers: a food tally (0x424F80,
# thiscall(amount)) whose manager would build the sound system.
SINGLETONS = {"vv1": [(0x430BC0, 0, 0)], "vv2": [(0x43E460, 0, 0)], "vv3": [(0x428B60, 0, 0x13000)], "vv4": [],
              "vv5": [(0x424F80, 4, 0)]}
SPEED = {"vv1": 0xA318, "vv2": 0x2EB08}        # the world's speed (3, 6 or 10): the tick's clock steps by it
CATCH_UP = {"vv1": 0x42E900, "vv2": 0x43B690, "vv3": 0x45FFE0, "vv4": 0x468430, "vv5": 0x472C90}
NURSING = 40
TOLD_DELIVERED, TOLD_KILLED = 6, 1


def deficit(elapsed: int) -> int:
    return max(5, min(50, (50 * (NURSING - elapsed) + NURSING // 2) // NURSING))


def real_catch_up(r) -> None:
    """Let the game's own catch-up run in the emulator (module docstring)."""
    p = r.p
    p.stub(RAND[r.game], lambda q: ((q.arg(0) - 1) & 0xFFFFFFFF if q.arg(0) else 0, 0))
    p.mu.hook_add(UC_HOOK_CODE, p._on_code, begin=RAND[r.game], end=RAND[r.game])
    for va, pop, size in SINGLETONS[r.game]:
        value = p.alloc(size) if size else 0
        p.stub(va, (lambda value, pop: lambda q: (value, pop))(value, pop))
        p.mu.hook_add(UC_HOOK_CODE, p._on_code, begin=va, end=va)
    tls = p.alloc(0x1000)
    image = b"".join(bytes(p.read(a, 0x1000)) for a in range(0x401000, 0x4C0000, 0x1000) if p.mapped(a, 0x1000))
    m = re.search(rb"\x8B\x48\x6C\x89\x0E\x8B\x48\x68\x89\x4E\x04\x8B\x0E\x3B\x0D(....)", image, re.S)
    if m:          # the C runtime's _LocaleUpdate: the per-thread block points at the global locale
        locale = struct.unpack("<I", m.group(1))[0]
        m2 = re.search(rb"\x8B\x46\x04\x3B\x05(....)", image[m.end():m.end() + 64], re.S)
        p.put32(tls + 0x6C, p.u32(locale))
        p.put32(tls + 0x68, p.u32(struct.unpack("<I", m2.group(1))[0]))
    p.put32(tls + 0x70, 2)
    tls_stub = next((k for k, v in p.api_names.items() if v == "TlsGetValue"), 0)

    def tls_get(q):
        # _getptd_noexit: TlsGetValue(__getvalueindex), through its wrapper, hands back FlsGetValue (call eax).
        outer = q.u32(q.reg("esp") + 12)
        return (tls_stub if q.mapped(outer, 2) and q.read(outer, 2) == b"\xFF\xD0" else tls), 4
    p.api_handlers["TlsGetValue"] = tls_get
    p.api_handlers["GetLastError"] = lambda q: (0, 0)
    p.api_handlers["SetLastError"] = lambda q: (0, 4)
    p.api_handlers["HeapAlloc"] = lambda q: (q.alloc(max(q.arg(2), 16)), 12)
    p.api_handlers["HeapFree"] = lambda q: (1, 12)
    if r.game in SPEED:
        p.put32(r.v.world + SPEED[r.game], 6)
    call = p.call
    p.call = lambda address, args=(), **kw: call(address, args, **{**kw, "limit": max(kw.get("limit", 0),
                                                                                       20_000_000)})


def graph(game: str, after: bool = False, effect: dict | None = None) -> dict:
    nodes = {"p0": {"text": "(Mum) gives birth and dies.",
                    "effects": [effect or {"do": "birth_then_die", "role": "mum"}]}}
    if after:
        nodes["p0"]["children"] = [{"next": "p1"}]
        nodes["p1"] = {"text": "(Friend) carries the child home."}
    return {"format": "vvfp-cie-graph", "version": 6, "title": "Two Lives", "games": [int(game[2])],
            "roles": {"mum": {"kind": "villager", "min_age": 18, "special": "nursing_parent", "protected": "allow"},
                      "friend": {"kind": "villager", "min_age": 14}},
            "start": "p0", "nodes": nodes}


def litter_value(game: str, babies: int) -> int:
    """The litter field for 1-3 babies (A New Home and The Lost Children leave it 0 for one)."""
    return 0 if babies == 1 and game in ("vv1", "vv2") else babies


@emulated
class BirthThenDie(unittest.TestCase):
    def village(self, game: str, elapsed: int = 20, babies: int = 1, nursing: bool = True, gap: bool = False,
                effect: dict | None = None):
        """Ann (record 0, nursing `elapsed` units with `babies`), Bob (the friend); with `gap`, record 1 is a record
        freed by a death and Bob is record 2."""
        people = [(0, "f", 30, "Ann", 0, nursing), (2 if gap else 1, "m", 31, "Bob", 0, False)]
        r = v6.V6(game, people)
        real_catch_up(r)
        L = r.v.L
        rec = r.v.record(0)
        processed = r.p.u32(rec + L["processed"])
        if nursing:
            r.p.put32(rec + L["pregnant"], processed - elapsed)
            r.p.put32(rec + L["litter"], litter_value(game, babies))
        if game != "vv1":
            v6.set_expected_father(r, game, 0, "Bob", 7, 8)
        r.rolls([0] * 40)
        r.log(1)
        self.assertIsNone(r.queue6(v6.compiled(graph(game, effect=effect))))
        return r

    def newborns(self, r, before: set[int]) -> list[int]:
        L = r.v.L
        return [i for i in range(16) if i not in before and r.v.byte(i, L["active"]) != 0
                and r.v.i32(i, L["health"]) > 0]

    def run_birth(self, game: str, **kw):
        r = self.village(game, **kw)
        before = {i for i in range(16) if r.v.byte(i, r.v.L["active"]) != 0}
        shown = r.walk_through()
        self.assertEqual(len(shown), 1)
        return r, self.newborns(r, before)

    def full_term_health(self, game: str) -> int:
        r, kids = self.run_birth(game, elapsed=NURSING)
        self.assertEqual(len(kids), 1)
        return r.v.i32(kids[0], r.v.L["health"])

    def test_an_early_birth_then_the_death_in_every_game(self):
        for game in GAME_IDS:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                healthy = self.full_term_health(game)
                r, kids = self.run_birth(game, elapsed=20)
                L = r.v.L
                self.assertEqual(len(kids), 1, "the baby is its own villager record")
                kid = kids[0]
                self.assertEqual((r.v.i32(kid, L["age"]), r.v.i32(kid, L["processed"])), (20, 20),
                                 "aged the nursing units already gone by")
                self.assertEqual(r.v.i32(kid, L["health"]), healthy - deficit(20), "the early-birth deficit")
                self.assertEqual(r.v.i32(0, L["health"]), 0, "Ann is dead")
                self.assertNotEqual(r.v.byte(0, L["active"]), 0, "her body stays: a grave follows")
                self.assertEqual(r.v.i32(0, L["pregnant"]), 0, "no longer nursing")
                told = r.told()
                self.assertEqual([k for k, i, _w in told if i == 0], [TOLD_DELIVERED, TOLD_KILLED],
                                 "the births told before the death")
                self.assertIn((TOLD_KILLED, 0, "unknown"), told, "Unknown causes")
                n, _now, filed = r.log()
                self.assertEqual(n, 1, "ONE Island Events log entry")
                self.assertIn("Ann's baby was born early; Ann died.", filed)

    def test_twins_and_triplets(self):
        for game in GAME_IDS:
            if not have_stock(game):
                continue
            healthy = self.full_term_health(game)
            for babies in (2, 3):
                with self.subTest(game=game, babies=babies):
                    r, kids = self.run_birth(game, elapsed=30, babies=babies)
                    L = r.v.L
                    self.assertEqual(len(kids), babies)
                    for kid in kids:
                        self.assertEqual(r.v.i32(kid, L["age"]), 30)
                        self.assertEqual(r.v.i32(kid, L["health"]), healthy - deficit(30))
                    self.assertEqual(r.v.i32(0, L["health"]), 0)
                    self.assertIn("Ann's babies were born early; Ann died.", r.log()[2])

    def test_full_term_and_the_earliest_birth(self):
        for game in GAME_IDS:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                healthy = self.full_term_health(game)
                r, kids = self.run_birth(game, elapsed=NURSING)
                L = r.v.L
                self.assertEqual(r.v.i32(kids[0], L["age"]), NURSING, "the game's own age")
                self.assertEqual(r.v.i32(kids[0], L["health"]), healthy, "no deficit at full term")
                self.assertIn("Ann's baby was born; Ann died.", r.log()[2])
                r, kids = self.run_birth(game, elapsed=0)
                self.assertEqual(r.v.i32(kids[0], L["age"]), 1, "never 0 (the creators' random age)")
                self.assertEqual(r.v.i32(kids[0], L["health"]), healthy - 50)
                self.assertGreater(r.v.i32(kids[0], L["health"]), 0)

    def test_a_freed_record_takes_the_baby(self):
        for game in GAME_IDS:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                r, kids = self.run_birth(game, gap=True)
                L = r.v.L
                self.assertEqual(kids, [1], "the record a death freed")
                self.assertEqual(r.p.cstring(r.v.record(2) + L["name"]), "Bob")
                self.assertGreater(r.v.i32(2, L["health"]), 0, "Bob is untouched")

    def test_the_child_carries_its_parents(self):
        for game in GAME_IDS[1:]:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                r, kids = self.run_birth(game)
                fn, mn, fh, fb, _mh, _mb = v6.PARENT_FIELDS[game]
                rec = r.v.record(kids[0])
                self.assertEqual(r.p.cstring(rec + mn), "Ann", "its mother")
                self.assertEqual(r.p.cstring(rec + fn), "Bob", "its father, as at the conception")
                self.assertEqual((r.p.u32(rec + fh), r.p.u32(rec + fb)), (7, 8))

    def test_not_nursing_just_dies_and_a_refused_birth_harms_nobody(self):
        for game in GAME_IDS:
            if not have_stock(game):
                continue
            with self.subTest(game=game, case="not nursing"):
                r = self.village(game)
                L = r.v.L
                r.p.put32(r.v.record(0) + L["pregnant"], 0)     # born since the casting
                before = {i for i in range(16) if r.v.byte(i, L["active"]) != 0}
                self.assertEqual(len(r.walk_through()), 1)
                self.assertEqual(self.newborns(r, before), [], "no birth")
                self.assertEqual(r.v.i32(0, L["health"]), 0, "she dies")
                self.assertEqual([k for k, i, _w in r.told() if i == 0], [TOLD_KILLED])
                self.assertIn("  Ann died.", r.log()[2])
            with self.subTest(game=game, case="refused"):
                r = self.village(game)
                L = r.v.L
                r.p.stub(CATCH_UP[game], lambda q: (0, 0))      # a catch-up that makes no birth
                r.p.mu.hook_add(UC_HOOK_CODE, r.p._on_code, begin=CATCH_UP[game], end=CATCH_UP[game])
                processed = r.p.u32(r.v.record(0) + L["processed"])
                age = r.p.u32(r.v.record(0) + L["age"])
                r.walk_through()
                self.assertGreater(r.v.i32(0, L["health"]), 0, "nobody dies")
                self.assertEqual(r.v.i32(0, L["pregnant"]), processed - 20, "still nursing, as she was")
                self.assertEqual(r.p.u32(r.v.record(0) + L["age"]), age, "her age as it was")
                self.assertEqual([k for k, _i, _w in r.told()], [])


EARLY = {"do": "deliver_early", "role": "mum"}
FRAIL = {"do": "deliver_early", "role": "mum", "min": -30, "max": -10}   # the walk's roll 0: -30


@emulated
class DeliverEarly(BirthThenDie):
    """cie-v6-binary.md 30: the same birth, and the parent lives; a frail newborn loses the roll more."""

    def run_early(self, game: str, effect: dict, **kw):
        return self.run_birth(game, effect=effect, **kw)

    def test_an_early_birth_and_the_parent_lives_in_every_game(self):
        for game in GAME_IDS:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                healthy = self.full_term_health(game)
                r, kids = self.run_early(game, EARLY, elapsed=20)
                L = r.v.L
                self.assertEqual(len(kids), 1, "the baby is its own villager record")
                kid = kids[0]
                self.assertEqual((r.v.i32(kid, L["age"]), r.v.i32(kid, L["processed"])), (20, 20))
                self.assertEqual(r.v.i32(kid, L["health"]), healthy - deficit(20), "the early-birth deficit")
                self.assertGreater(r.v.i32(0, L["health"]), 0, "Ann lives")
                self.assertEqual(r.v.i32(0, L["pregnant"]), 0, "no longer nursing")
                self.assertEqual([k for k, i, _w in r.told() if i == 0], [TOLD_DELIVERED], "the birth told, no death")
                n, _now, filed = r.log()
                self.assertEqual(n, 1)
                self.assertIn("Ann's baby was born early.", filed)
                self.assertNotIn("died", filed)

    def test_a_frail_newborn_loses_the_roll_more(self):
        for game in GAME_IDS:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                healthy = self.full_term_health(game)
                r, kids = self.run_early(game, FRAIL, elapsed=30, babies=2)
                L = r.v.L
                self.assertEqual(len(kids), 2)
                for kid in kids:
                    self.assertEqual(r.v.i32(kid, L["health"]), healthy - deficit(30) - 30, "twins: each the same")
                self.assertGreater(r.v.i32(0, L["health"]), 0)
                self.assertIn("Ann's babies were born early.", r.log()[2])
                r, kids = self.run_early(game, FRAIL, elapsed=NURSING)
                self.assertEqual(r.v.i32(kids[0], L["age"]), NURSING, "full term: the game's own age")
                self.assertEqual(r.v.i32(kids[0], L["health"]), healthy - 30, "no deficit, only the frail loss")
                self.assertIn("Ann's baby was born.", r.log()[2])

    def test_not_nursing_or_a_refused_birth_changes_nothing(self):
        for game in GAME_IDS:
            if not have_stock(game):
                continue
            with self.subTest(game=game, case="not nursing"):
                r = self.village(game, effect=EARLY)
                L = r.v.L
                r.p.put32(r.v.record(0) + L["pregnant"], 0)
                before = {i for i in range(16) if r.v.byte(i, L["active"]) != 0}
                r.walk_through()
                self.assertEqual(self.newborns(r, before), [])
                self.assertGreater(r.v.i32(0, L["health"]), 0)
                self.assertEqual([k for k, _i, _w in r.told()], [])
            with self.subTest(game=game, case="refused"):
                r = self.village(game, effect=FRAIL)
                L = r.v.L
                r.p.stub(CATCH_UP[game], lambda q: (0, 0))
                r.p.mu.hook_add(UC_HOOK_CODE, r.p._on_code, begin=CATCH_UP[game], end=CATCH_UP[game])
                processed = r.p.u32(r.v.record(0) + L["processed"])
                r.walk_through()
                self.assertGreater(r.v.i32(0, L["health"]), 0)
                self.assertEqual(r.v.i32(0, L["pregnant"]), processed - 20, "still nursing, as she was")
                self.assertEqual([k for k, _i, _w in r.told()], [])

    # the inherited birth_then_die tests run in BirthThenDie
    test_an_early_birth_then_the_death_in_every_game = None
    test_twins_and_triplets = None
    test_full_term_and_the_earliest_birth = None
    test_a_freed_record_takes_the_baby = None
    test_the_child_carries_its_parents = None
    test_not_nursing_just_dies_and_a_refused_birth_harms_nobody = None


if __name__ == "__main__":
    unittest.main()
