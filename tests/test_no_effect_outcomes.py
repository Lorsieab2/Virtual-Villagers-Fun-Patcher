"""The owner, 2026-11-23, in capitals: "ANYTHING FLAVOR OR NO EFFECT outcome in an island event MUST HAVE (no effect)
at the end." (docs/event-collection/cie-v6-binary.md 46).

* src/vv_cie_graph.py: an outcome (after the last answer, or the whole run with no question) whose nodes have no
  effect ends with "(no effect)" in simulate and in walk (the fit counts it); the pages before a question never do;
  an outcome with any effect, or a Village Solidarity raise / lower tag while that companion is started, never does;
  words that already end with it are not given a second one.
* The branching engine (native/vvfp_story_upgrades/story_graph.inc, the test build in the emulator) shows the same
  words as simulate in all five games, "(no effect)" last.
* The old-format Custom Island Event (story_custom.inc ce_compose_in_once): a plain event that changes nothing ends
  with it; one with food never does.
* More Island Events' mirrors: the endings that change nothing end with the piece NO_EFFECT.
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_cie_graph as cg  # noqa: E402

LANTERN = {
    "format": "vvfp-cie-graph", "version": 6, "title": "The Lantern", "games": [1, 2, 3, 4, 5],
    "roles": {"subject": {"kind": "villager", "min_age": 14}},
    "start": "p",
    "nodes": {
        "p": {"text": "(Name) finds a lantern in the sand.", "children": [{"next": "q"}]},
        "q": {"type": "question", "text": "What should (Name) do with it?", "choices": [
            {"label": "Keep it", "next": "keep"}, {"label": "Trade it", "next": "trade"},
            {"label": "Ask the elders", "next": "ask"}]},
        "keep": {"text": "(Name) hangs it by the door. It glows softly at night."},
        "trade": {"text": "(Name) trades it for a basket of fruit.", "auto_text": True,
                  "effects": [{"do": "food", "amount": 40}]},
        "ask": {"text": "The elders smile.", "children": [{"next": "ask2"}]},
        "ask2": {"popup": "append", "text": "They say it is very old. \\(no effect\\)"},
    },
}
ANA = {"subject": cg.Binding("Ana", "f")}


def lantern() -> dict:
    return cg.load(copy.deepcopy(LANTERN))


class Rule(unittest.TestCase):
    def test_changes_nothing(self):
        self.assertTrue(cg.outcome_changes_nothing([{"effects": []}, {"effects": []}]))
        self.assertFalse(cg.outcome_changes_nothing([{"effects": []}, {"effects": [{"do": "action"}]}]))
        tagged = [{"effects": [], "solidarity": "raise"}]
        self.assertTrue(cg.outcome_changes_nothing(tagged))
        self.assertFalse(cg.outcome_changes_nothing(tagged, solidarity=True))
        self.assertTrue(cg.outcome_changes_nothing([{"effects": [], "solidarity": "neutral"}], solidarity=True))

    def test_never_twice(self):
        for text in ("Done. (no effect)", "Done.\n(No Effect).", "Done. \\(no effect\\)\n"):
            self.assertEqual(cg.with_no_effect(text), text)
        self.assertEqual(cg.with_no_effect("Done."), "Done.\n(no effect)")
        self.assertEqual(cg.with_no_effect("Done.", escaped=True), "Done.\n\\(no effect\\)")
        self.assertEqual(cg.with_no_effect(""), "(no effect)")

    def test_the_line_is_an_automatic_line(self):
        self.assertEqual(cg.AUTO_LINES["no_effect"], "(no effect)")
        self.assertEqual(cg.NO_EFFECT_LINE, "(no effect)")

    def test_the_heathens_own_cast(self):
        """45: with the Heathens' own cast the tribe's effects and the solidarity tag change nothing; a villager's
        own effect still does; a mixed cast is as always."""
        food = [{"effects": [{"do": "food", "amount": 50, "defer": False, "scaled": False}], "solidarity": "raise"}]
        self.assertTrue(cg.outcome_changes_nothing(food, solidarity=True, heathen_cast=True))
        self.assertFalse(cg.outcome_changes_nothing(food, solidarity=True))
        self.assertFalse(cg.outcome_changes_nothing(food))
        own = [{"effects": [{"do": "health_change", "role": "isolan", "min": -40, "max": -40}]}]
        self.assertFalse(cg.outcome_changes_nothing(own, heathen_cast=True))
        for e, flavor in (({"do": "tech", "amount": 5}, True), ({"do": "damage", "min": 1, "max": 5}, True),
                          ({"do": "village", "what": "tech_level", "step": 1}, True),
                          ({"do": "village", "what": "weather"}, False),
                          ({"do": "celebrate"}, True), ({"do": "celebrate", "role": "isolan"}, False),
                          ({"do": "mood", "role": "isolan", "good": True}, False)):
            with self.subTest(e=e):
                self.assertEqual(cg.flavor_only(e), flavor)


class Simulate(unittest.TestCase):
    def popups(self, answer: int, **kw) -> list[str]:
        return cg.simulate(lantern(), 3, [0] * 20, ANA, [answer], **kw)["popups"]

    def test_a_flavor_outcome_ends_with_it(self):
        shown = self.popups(0)
        self.assertTrue(shown[-1].endswith("It glows softly at night.\n(no effect)"), shown[-1])
        self.assertNotIn("(no effect)", "".join(shown[:-1]), "never before the choice")

    def test_an_outcome_with_an_effect_never(self):
        shown = self.popups(1)
        self.assertNotIn("(no effect)", "\n".join(shown))
        self.assertIn("The village gains 40 food.", shown[-1])

    def test_words_that_say_it_are_not_given_a_second(self):
        shown = self.popups(2)
        self.assertEqual(shown[-1].count("(no effect)"), 1, shown[-1])
        self.assertTrue(shown[-1].endswith("very old. (no effect)"), shown[-1])

    def test_a_solidarity_tag_with_its_companion(self):
        g = copy.deepcopy(LANTERN)
        g["nodes"]["keep"]["solidarity"] = "raise"
        g = cg.load(g)
        on = cg.simulate(g, 3, [0] * 20, ANA, [0], solidarity=True)["popups"]
        off = cg.simulate(g, 3, [0] * 20, ANA, [0])["popups"]
        self.assertNotIn("(no effect)", on[-1])
        self.assertTrue(off[-1].endswith("(no effect)"))

    def test_a_plain_event_with_no_question(self):
        g = cg.load({"format": "vvfp-cie-graph", "version": 6, "title": "A Breeze", "games": [1, 2, 3, 4, 5],
                     "roles": {"subject": {"kind": "villager", "min_age": 14}}, "start": "p",
                     "nodes": {"p": {"text": "(Name) feels a breeze."}}})
        for game in range(1, 6):
            # A New Home and The Lost Children draw no parenthesis: their glyph fallback, as every text there
            self.assertEqual(cg.simulate(g, game, [0] * 8, ANA)["popups"],
                             ["Ana feels a breeze.\n" + cg.glyph_fallback("(no effect)", game)])

    def test_walk_counts_it(self):
        ctx = cg.Context(3, frozenset(), frozenset({"subject"}), cg.default_facts(lantern(), {"subject"}))
        histories = cg.walk(lantern(), ctx)
        ends = {h.nodes[-1]: h.popups[-1].text for h in histories}
        self.assertTrue(ends["keep"].endswith("\\(no effect\\)"), ends["keep"])
        self.assertNotIn("no effect", ends["trade"])
        self.assertEqual(ends["ask2"].count("no effect"), 1)


class MoreIslandEventsMirrors(unittest.TestCase):
    def test_the_pieces(self):
        import vv_aspiring_adventurer as adv
        import vv_cave_explorers as cave
        import vv_diving_for_treasure as dive
        for m in (adv, cave, dive):
            self.assertEqual(dict(m.TEXTS)["NO_EFFECT"], "(no effect)", m.__name__)
        self.assertEqual(dive.pages_of("B"), (("DEEPER", "FIND_B", "NO_EFFECT"),))
        for e in ("A", "C", "D1", "D2A", "D2B", "D2C", "NOT"):
            self.assertNotIn("NO_EFFECT", sum(dive.pages_of(e), ()), e)
        self.assertEqual({k for k, v in adv.EFFECTS.items() if v == "none"}, {"A7", "A9", "HOME", "H2"})


try:
    from test_story_cie_graph_runtime_v6 import (  # noqa: E402
        GAME_IDS, TWO, V6, compiled, emulated, have_stock, norm)
except Exception:  # noqa: BLE001 -- no emulator here: the engine's half is skipped
    emulated = None

if emulated is not None:
    @emulated
    class Engine(unittest.TestCase):
        """The test build of "VVFP Story Upgrades.dll" shows simulate's words, "(no effect)" last, in all five
        games."""

        def test_each_answer_in_every_game(self):
            g = lantern()
            ran = 0
            for game in GAME_IDS:
                if not have_stock(game):
                    continue
                for answer in (0, 1, 2):
                    with self.subTest(game=game, answer=answer):
                        r = V6(game, TWO)
                        r.rolls([0] * 40)
                        self.assertIsNone(r.queue6(compiled(LANTERN)))
                        r.walk_through([answer])
                        shown = norm(" ".join(r.displays()))
                        want = cg.simulate(g, int(game[2]), [0] * 20, ANA, [answer])["popups"]
                        self.assertEqual(shown, norm(" ".join(want)))
                        line = cg.glyph_fallback("(no effect)", int(game[2]))   # VV1 / VV2: "-no effect-"
                        self.assertEqual(shown.endswith(line), answer != 1, shown)
                        self.assertEqual(shown.count(line), 0 if answer == 1 else 1)
                        ran += 1
            if ran == 0:
                self.skipTest("no stock executable")


try:
    import test_story_custom_island_event as old  # noqa: E402
    from story_custom_fixtures import Event  # noqa: E402
except Exception:  # noqa: BLE001 -- no emulator here
    old = None

if old is not None:
    @old.emulated
    class OldFormatCustomEvent(unittest.TestCase):
        """A plain Custom Island Event (the old format, story_custom.inc ce_compose_in_once) delivered through each
        game's own island-event path: one that changes nothing ends with "(no effect)" (A New Home and The Lost
        Children: "-no effect-", their glyph fallback); one with food never does."""

        def chooser_text(self, game: str, event) -> str:
            site, resume, _chooser = old.CHOOSER[game]
            story = old.Story(game)
            p = story.proc
            story.village.put(1, sex="m", years=30, name="Adult")
            story.record_call(old.CHOOSER[game][2], 8)
            obj = p.alloc(0x5100)
            old._set_custom(story, event)
            esp = old.HEAP + 0x3000000
            p.put32(esp, 2)
            p.put32(esp + 4, 6)
            p.set_reg("esp", esp)
            p.set_reg("ecx", obj)
            p.set_reg("esi", obj)
            p.set_reg("ebp", obj + 0x277F)
            p.run(site, resume)
            return p.cstring(obj + 0x277F)

        def object_text(self, game: str, event) -> str:
            table, site, resume, register, lookup, *_ = old.SELECT[game]
            story = old.Story(game)
            p = story.proc
            story.village.put(1, sex="m", years=30, name="Adult")
            for slot in range(1, 58):
                p.put32(table + 4 * slot, p.alloc(0x20))
            old._set_custom(story, event)
            p.set_reg("esi", 5)
            p.set_reg("esp", old.HEAP + 0x3000000)
            p.run(site, resume)
            obj = p.reg(register)
            body = p.call(p.u32(p.u32(obj) + 0xC), [], ecx=obj)
            return p.cstring(p.call(lookup, [body]))

        def test_every_game(self):
            ran = 0
            for game in ("vv1", "vv2", "vv3", "vv4", "vv5"):
                if not old.have_stock(game):
                    continue
                line = "-no effect-" if game in ("vv1", "vv2") else "(no effect)"
                text_of = self.chooser_text if game in old.CHOOSER else self.object_text
                with self.subTest(game=game, effects=False):
                    text = text_of(game, Event(title="A Quiet Night", text="The stars shine."))
                    self.assertTrue(text.rstrip().endswith("The stars shine.\n\n" + line), repr(text))
                with self.subTest(game=game, effects=True):
                    text = text_of(game, Event(title="A Quiet Night", text="The stars shine.", food_op=old.ADD,
                                               food_amount=250))
                    self.assertIn("250 food", text)
                    self.assertNotIn("no effect", text)
                ran += 1
            if ran == 0:
                self.skipTest("no stock executable")

        def test_the_line_is_checked_when_queued(self):
            """Codex (#853): the text checked when the event is queued holds its "(no effect)" (a blank line and
            the line), so a description that fills the panel without it is refused -- never shown with it dropped;
            the longest one queued shows it whole."""
            ran = 0
            for game, (_width, lines, _tw, _sep) in old.PANEL.items():
                if not old.have_stock(game):
                    continue

                def longest(**fx) -> int:
                    story = old.Story(game)
                    story.village.put(1, sex="m", years=30, name="Adult")
                    best = 0
                    for k in range(1, lines + 2):
                        if story.refusal(Event(title="Night", text="\n".join(["Quiet."] * k), **fx)) is None:
                            best = k
                    return best

                with self.subTest(game=game):
                    plain, changing = longest(), longest(tech_op=old.ADD, tech_amount=1)
                    self.assertGreater(plain, 0)
                    self.assertEqual(plain, changing - 2, "its blank line and its line are kept free")
                    line = "-no effect-" if game in ("vv1", "vv2") else "(no effect)"
                    text_of = self.chooser_text if game in old.CHOOSER else self.object_text
                    text = text_of(game, Event(title="Night", text="\n".join(["Quiet."] * plain)))
                    self.assertTrue(text.rstrip().endswith("Quiet.\n\n" + line), repr(text))
                ran += 1
            if ran == 0:
                self.skipTest("no stock executable")


try:
    import test_heathens_in_island_events as hv  # noqa: E402
except Exception:  # noqa: BLE001 -- no emulator here
    hv = None

if hv is not None and old is not None:
    @old.emulated
    class HeathenCast(unittest.TestCase):
        """New Believers' Heathens in island events (45): with the Heathens' own cast an outcome whose only effects
        are the tribe's (flavor, the Heathens' village's) ends with "(no effect)" -- once, the hv_ lines' own
        included; a mixed cast's food is the tribe's and gets none."""

        def setUp(self):
            if not old.have_stock("vv5"):
                self.skipTest("no New Believers")
            self.e = hv.Engine()

        def words(self, g, people, heathens, solidarity=False) -> str:
            r = self.e.run_with(people, heathens=heathens)
            if solidarity:
                from test_village_solidarity import fake_solidarity
                fake_solidarity(r.p, 1000, 1000, [])
            self.assertIsNone(r.queue6(hv.compiled(g)))
            return " ".join(" ".join(s[1] for s in r.walk_through()).split())

        def test_a_heathen_only_flavor_outcome(self):
            for auto in (True, False):
                for solidarity in (False, True):
                    with self.subTest(auto_lines=auto, solidarity=solidarity):
                        g = hv.graph("only", auto=auto)
                        g["nodes"]["p"]["solidarity"] = "raise"
                        words = self.words(g, hv.Engine.ONE, (0,), solidarity)
                        self.assertTrue(words.endswith("(no effect)"), words)
                        self.assertEqual(words.count("(no effect)"), 1, words)
            with self.subTest(case="a villager's own effect"):
                fx = [{"do": "health_change", "role": "isolan", "min": -40, "max": -40}]
                self.assertNotIn("(no effect)", self.words(hv.graph("only", fx), hv.Engine.ONE, (0,)))

        def test_a_mixed_cast_outcome(self):
            roles = {"isolan": {"kind": "villager", "min_age": 14, "heathens": "only"},
                     "host": {"kind": "villager", "min_age": 14}}
            for auto in (True, False):
                with self.subTest(auto_lines=auto):
                    words = self.words(hv.graph("only", roles=roles, auto=auto), hv.Engine.TWO, (1,))
                    self.assertNotIn("(no effect)", words)


if __name__ == "__main__":
    unittest.main()
