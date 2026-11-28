"""The casualty limit below 61 villagers and the flat 50% (the owner, 2026-11-27).

  "additional events should replace vanilla ones 50% of the time."
  "all events at any size; below 61 population a max of 1-2 villagers can die or disappear to prevent mass
   casualties"

native/vvfp_story_upgrades/story_collection.inc: every new event may come at any population; while the village has
fewer than 61 villagers the natural draw leaves out an event one of whose endings can take more than 2 villagers
(killed, made to disappear, dead with the body never found, dead after giving birth; a lost pregnancy is no one).
THE COUNT: one ending is one path through the event from its first page to an end; it takes the distinct villager
roles on that path, each villager the event made, and a group's size; the event's count is its worst ending.

Shown here:
  * the constants (C and Python): 50%, 61, 2;
  * the Python count (vv_cie_graph.gone) on small graphs: per ending, never the sum of all endings; a lost
    pregnancy is no one; a group of no fixed size is more than any limit;
  * every shipped More Island Events count, collection event and procedural piece under the rule;
  * the procedural twin (vv_procedural.usable): an outcome taking 2 is usable below 61, one taking 3 is not, both are
    at 61 or more (gate off);
  * EMULATED (the Story TEST build): the engine's count equals the Python one on every shipped collection event that
    takes anyone and on the Living Event Engine variants that do; an event taking 2 (and 1) is drawable at 60
    villagers, one taking 3 or more is left out at 60, and both are drawable at 61.
"""
from __future__ import annotations

import glob
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_cie_graph as cie  # noqa: E402
import vv_game_mechanics_adventurer as gm  # noqa: E402
import vv_procedural as vp  # noqa: E402

COLLECTION = ROOT / "native" / "vvfp_story_upgrades" / "story_collection.inc"
ASSETS = ROOT / "assets" / "event_collection"


def node(effects=(), children=(), choices=(), els=None) -> dict:
    return {"type": "question" if choices else "popup", "effects": list(effects),
            "children": [{"next": c, "weight": 1, "if": None, "else": None} for c in children],
            "choices": [{"label": c, "next": c, "if": None} for c in choices], "else": els}


def kill(role: str) -> dict:
    return {"do": "kill", "role": role, "cause": "Unknown causes"}


def graph(nodes: dict, start: str = "start") -> dict:
    return {"start": start, "nodes": nodes}


class TheConstants(unittest.TestCase):
    def test_c_and_python_agree(self) -> None:
        source = COLLECTION.read_text(encoding="utf-8")
        value = lambda name: int(re.search(rf"#define {name} (\d+)", source).group(1))   # noqa: E731
        self.assertEqual(value("SC_REPLACE_PERCENT"), 50)
        self.assertEqual(value("SC_MIN_POPULATION"), 61)
        self.assertEqual(value("SC_MAX_GONE"), 2)
        self.assertEqual((gm.REPLACE_PERCENT, gm.REPLACE_MIN_POPULATION, gm.REPLACE_MAX_GONE), (50, 61, 2))
        self.assertEqual((cie.GONE_LIMIT, vp.GONE_LIMIT), (2, 2))


class TheCount(unittest.TestCase):
    def test_two_on_one_ending(self) -> None:
        g = graph({"start": node(children=["end"]), "end": node([kill("a"), kill("b")])})
        self.assertEqual(cie.gone(g), 2)
        self.assertFalse(cie.too_deadly_below_61(g))

    def test_three_on_one_ending(self) -> None:
        g = graph({"start": node([kill("a")], children=["end"]),
                   "end": node([kill("b"), {"do": "vanish", "role": "c"}])})
        self.assertEqual(cie.gone(g), 3)
        self.assertTrue(cie.too_deadly_below_61(g))

    def test_per_ending_never_the_sum_of_the_endings(self) -> None:
        # Three answers, each ending takes a different villager (and one two): 2, never 4.
        g = graph({"start": node(choices=["x", "y", "z"]), "x": node([kill("a")]), "y": node([kill("b")]),
                   "z": node([kill("c"), {"do": "die_unrecovered", "role": "d", "cause": "Unknown causes"}])})
        self.assertEqual(cie.gone(g), 2)

    def test_the_same_villager_counts_once(self) -> None:
        g = graph({"start": node([{"do": "vanish", "role": "a"}], children=["end"]), "end": node([kill("a")])})
        self.assertEqual(cie.gone(g), 1)

    def test_a_lost_pregnancy_is_no_one_and_birth_then_death_is_one(self) -> None:
        g = graph({"start": node([{"do": "baby_lost", "role": "a"}, {"do": "baby_lost", "role": "b"},
                                  {"do": "baby_lost", "role": "c"}])})
        self.assertEqual(cie.gone(g), 0)
        g = graph({"start": node([{"do": "birth_then_die", "role": "a", "cause": "x"}, kill("b"), kill("c")])})
        self.assertEqual(cie.gone(g), 3)

    def test_made_villagers_and_groups(self) -> None:
        g = graph({"start": node([kill("$newest"), kill("$newest")])})
        self.assertEqual(cie.gone(g), 2)                 # a villager the event made: each time
        g = graph({"start": node([{"do": "kill", "target": {"random": 2}}, kill("a")])})
        self.assertEqual(cie.gone(g), 3)
        g = graph({"start": node([{"do": "vanish", "target": {"all": True}}])})
        self.assertEqual(cie.gone(g), cie.GONE_MANY)    # no fixed size: more than any limit

    def test_a_shared_end_page_adds_to_each_ending(self) -> None:
        g = graph({"start": node(choices=["x", "y"]), "x": node([kill("a")], els="end"),
                   "y": node([kill("b")], els="end"), "end": node([kill("c"), kill("d")])})
        self.assertEqual(cie.gone(g), 3)


class TheShippedEvents(unittest.TestCase):
    def test_collection_events_taking_more_than_two_are_only_the_signs_and_the_mask(self) -> None:
        files = sorted(ASSETS.glob("*.cieg"))
        if not files:
            self.skipTest("no compiled collection events")
        over = {f.stem for f in files if cie.too_deadly_below_61(cie.decompile_graph(f.read_bytes()))}
        self.assertEqual(over, {"mie_troubling_signs", "mie_mysterious_mask"})

    def test_no_procedural_piece_is_left_out_except_by_its_count(self) -> None:
        files = sorted((ASSETS / "pieces").glob("*.pcb"))
        if not files:
            self.skipTest("no piece files")
        taking = 0
        for f in files:
            for p in vp.read_pcb(f.read_bytes()).pieces:
                n = vp.gone(p)
                taking += n > 0
                if p.kind == vp.KIND_OUTCOME:
                    self.assertEqual(vp.too_deadly(p), n > 2, p.id)
                else:
                    self.assertEqual(n, 0, f"{p.id}: only outcomes take villagers")
        self.assertGreater(taking, 100)


def piece_file(gone_slots: int) -> vp.PieceFile:
    sl = [vp.Slot(f"s{k}", min_age=18) for k in range(gone_slots)]
    out = vp.Piece("o", vp.KIND_OUTCOME, text="It ends.", slots=sl,
                   effects=[vp.Effect(4, k, string="Unknown causes") for k in range(gone_slots)],
                   flags=vp.PF_DEADLY)
    return vp.PieceFile("t", 0x1F, [out])


class TheProceduralTwin(unittest.TestCase):
    def test_two_usable_below_61_three_not_both_at_61(self) -> None:
        two, three = piece_file(2).pieces[0], piece_file(3).pieces[0]
        below, above = vp.Settings(game=4, gate=True), vp.Settings(game=4, gate=False)
        self.assertTrue(vp.usable(two, below))
        self.assertFalse(vp.usable(three, below))
        self.assertTrue(vp.usable(two, above))
        self.assertTrue(vp.usable(three, above))

    def test_a_setup_that_takes_anyone_stays_out_below_61(self) -> None:
        setup = vp.Piece("s", vp.KIND_SETUP, slots=[vp.Slot("a")], effects=[vp.Effect(5, 0)])
        self.assertFalse(vp.usable(setup, vp.Settings(game=1, gate=True)))
        self.assertTrue(vp.usable(setup, vp.Settings(game=1, gate=False)))


try:
    import test_story_custom_island_event as sci  # noqa: E402
    import test_aspiring_adventurer as aa  # noqa: E402
    HAVE = sci.HAVE_EMULATOR and sci.TEST_DLL.is_file() and aa.HAVE_STOCK
except Exception:                                       # pragma: no cover - the emulator's own imports
    HAVE = False

NEEDS = unittest.skipUnless(HAVE, "needs unicorn, pefile, the stock executables and the Story TEST build")


@NEEDS
class TheEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.st = sci.Story("vv4")
        cls.p = cls.st.proc
        cls.blob = cls.p.alloc(0x100000)

    def put(self, data: bytes) -> int:
        self.assertLessEqual(len(data), 0x100000)
        self.p.write(self.blob, data)
        return len(data)

    def engine_gone(self, data: bytes) -> int:
        return self.p.export("VvfpStoryProbeCollectionGone", self.blob, self.put(data))

    def kept_out(self, data: bytes, population: int) -> bool:
        size = self.put(data)
        self.p.export("VvfpStoryProbeCollectionPopulation", 4, population)
        try:
            return bool(self.p.export("VvfpStoryProbeCollectionKeptOut", 4, self.blob, size))
        finally:
            self.p.export("VvfpStoryProbeCollectionPopulation", 4, -1)

    def test_the_engine_counts_as_python_on_every_shipped_event_that_takes_anyone(self) -> None:
        checked = 0
        for f in sorted(ASSETS.glob("*.cieg")):
            data = f.read_bytes()
            want = cie.gone(cie.decompile_graph(data))
            if want == 0 and checked % 40:
                checked += 1
                continue                                # every one that takes anyone, a sample of the rest
            with self.subTest(event=f.stem):
                self.assertEqual(self.engine_gone(data), want)
            checked += 1
        self.assertGreater(checked, 100)

    def test_the_engine_counts_as_python_on_the_living_variants_that_take_anyone(self) -> None:
        import vv_living_mixer as lm
        seen = 0
        for pak in sorted(glob.glob(str(ASSETS / "vv4" / "*.pak"))):
            for v in lm.read_pack(Path(pak).read_bytes())["variants"]:
                want = cie.gone(cie.decompile_graph(v["blob"]))
                if want == 0:
                    continue
                with self.subTest(pak=Path(pak).name, seed=v["seed"]):
                    self.assertEqual(self.engine_gone(v["blob"]), want)
                seen += 1
                if seen >= 120:
                    return
        self.assertGreater(seen, 0)

    def test_two_or_fewer_drawable_below_61_three_or_more_not_all_at_61(self) -> None:
        by_count: dict[int, bytes] = {}
        for f in sorted(ASSETS.glob("*.cieg")):
            data = f.read_bytes()
            by_count.setdefault(min(cie.gone(cie.decompile_graph(data)), 3), data)
        self.assertEqual(set(by_count), {0, 1, 2, 3})
        for n, data in sorted(by_count.items()):
            with self.subTest(gone=n):
                self.assertEqual(self.kept_out(data, 60), n > 2)       # below 61: only more than 2 stays out
                self.assertEqual(self.kept_out(data, 3), n > 2)        # at any small size too
                self.assertFalse(self.kept_out(data, 61))              # 61 or more: every one


if __name__ == "__main__":
    unittest.main()
