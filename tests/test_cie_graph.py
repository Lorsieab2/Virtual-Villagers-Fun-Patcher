"""Branching Custom Island Events (src/vv_cie_graph.py): the graph format, its checks, the .cieg and the odds.

The owner (v1.35.97): "allow the player to create multiple branching complicated outcome events like I just made for
Aspiring Adventurer in Custom Island Events".  Pinned here:
  * the Aspiring Adventurer as a graph (data/cie_graphs/the_aspiring_adventurer.json) passes, with and without
    scrolling, and its chances are the owner's table exactly (A7/A9 12.5%, A1/A5/A8 8.33%, deadly 12.5% each;
    Choice B 90%, lost endings 1.67%, healers 0.56%; the "In all" lines);
  * every check refuses what it should (missing node, cycle, unreachable, dead end on some history, weights,
    question shape, characters, effects a game lacks, unbound roles, awards, fit, popups per run);
  * compile -> decompile gives the graph back, the header is sound and a damaged file is refused;
  * placeholders fill as the player reads them; the fit mirrors the companion's ce_wrap;
  * the per-game tables mirror native/vvfp_story_upgrades (CAP bits, popups, labels, skills, preferences) and the
    name room is the Last Names room (the owner: (name) is the full name).
"""
from __future__ import annotations

import copy
import json
import re
import struct
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_cie_graph as cg  # noqa: E402

AA = ROOT / "data" / "cie_graphs" / "the_aspiring_adventurer.json"
NATIVE = ROOT / "native" / "vvfp_story_upgrades"


def aa_data() -> dict:
    return json.loads(AA.read_text(encoding="utf-8"))


def tiny(**nodes) -> dict:
    """A small valid graph; `nodes` replace or add nodes."""
    g = {
        "format": "vvfp-cie-graph", "version": 1, "title": "Test", "games": [1, 2, 3, 4, 5],
        "roles": {"subject": {"kind": "villager"}},
        "start": "q",
        "nodes": {
            "q": {"type": "question", "text": "(Name) wonders.", "choices": [
                {"label": "Yes", "next": "a"}, {"label": "No", "next": "b"}]},
            "a": {"text": "(Name) goes.", "children": [{"next": "c", "weight": 3}, {"next": "d"}]},
            "b": {"text": "(Name) stays."},
            "c": {"text": "Good.", "popup": "append"},
            "d": {"text": "Bad.", "effects": [{"do": "kill"}]},
        },
    }
    g["nodes"].update(nodes)
    return g


def problems_of(data: dict, scrolling: bool = False) -> list[str]:
    return cg.validate(data, scrolling)[1]


class AspiringAdventurer(unittest.TestCase):
    def setUp(self):
        self.g = cg.load(AA)

    def test_passes_with_and_without_scrolling(self):
        self.assertEqual(problems_of(aa_data(), False), [])
        self.assertEqual(problems_of(aa_data(), True), [])

    def ends(self, game=1, patches=(), roles=None):
        rows = cg.chances(self.g, game, patches, roles)
        return ({r.key: r.chance for r in rows[0]["ends"]}, {r.key: r.chance for r in rows[1]["ends"]},
                {r.key: r for r in rows[0]["outcomes"]}, {r.key: r for r in rows[1]["outcomes"]})

    def test_choice_a_is_the_owners_table(self):
        for game in range(1, 6):
            a, _, outs, _ = self.ends(game)
            self.assertEqual(sum(a.values()), 1)
            for e in ("A7", "A9", "A2", "A3", "A4", "A6"):
                self.assertEqual(a[e], Fraction(1, 8), (game, e))
            for e in ("A1", "A5", "A8"):
                self.assertEqual(a[e], Fraction(1, 12), (game, e))
                self.assertEqual(cg.percent(a[e]), "8.33%")
            self.assertEqual(outs["comes home safe"].chance, Fraction(1, 2))
            self.assertEqual(outs["comes home safe"].by_award,
                             {"nothing": Fraction(1, 4), "+500 food": Fraction(1, 8),
                              "+2,000 tech points": Fraction(1, 8)})
            self.assertEqual(outs["dies and gets a grave"].chance, Fraction(1, 4))
            self.assertEqual(outs["disappears, no grave"].chance, Fraction(1, 4))

    def test_choice_b_is_the_owners_table(self):
        for game in range(1, 6):
            _, b, _, outs = self.ends(game)
            self.assertEqual(sum(b.values()), 1)
            self.assertEqual(b["b_home"], Fraction(9, 10))
            for h in ("H1", "H2", "H3"):
                self.assertEqual(cg.percent(b[h]), "0.56%")
                self.assertEqual(b[h], Fraction(1, 180))
            two = "L2_heathen" if game == 5 else "L2"
            self.assertNotIn("L2" if game == 5 else "L2_heathen", b)
            for e in (two, "L3", "L4", "L5", "L6"):
                self.assertEqual(b[e], Fraction(1, 60))
                self.assertEqual(cg.percent(b[e]), "1.67%")
            self.assertEqual(cg.percent(outs["comes home alive"].chance), "92.78%")
            self.assertEqual(cg.percent(outs["dies and gets a grave"].chance), "3.89%")
            self.assertEqual(cg.percent(outs["disappears, no grave"].chance), "1.67%")
            self.assertEqual(cg.percent(outs["joins the other tribe"].chance), "1.67%")

    def test_no_friend_makes_a8_a5(self):
        a, _, _, _ = self.ends(3, roles={"subject", "stranger"})
        self.assertNotIn("A8", a)
        self.assertEqual(a["A5"], Fraction(1, 6))
        self.assertEqual(cg.percent(a["A5"]), "16.67%")

    def test_awards_are_paid_only_in_a1_a5_a8(self):
        for p in cg.walk(self.g, cg.Context(2, frozenset(), frozenset(self.g["roles"]))):
            paid = [e for _, e in p.effects if e["do"] == "pay_award"]
            self.assertEqual(bool(paid), p.end in ("A1", "A5", "A8"), p.nodes)

    def test_guardians_of_isola_wording(self):
        ctx = cg.Context(5, frozenset({"guardians_of_isola"}), frozenset(self.g["roles"]))
        node = self.g["nodes"]["L2_heathen"]
        self.assertIn("Isolans'", cg.node_text(node, ctx, ()))
        self.assertIn("heathens'", cg.node_text(node, cg.Context(5, frozenset(), ctx.roles), ()))

    def test_the_table_text(self):
        table = cg.chances_table(self.g, 1)
        self.assertIn("CHOICE A: GO INVESTIGATE!", table)
        self.assertIn("CHOICE B: STAY ON THE SAFE PATH", table)
        self.assertRegex(table, r"A1 \(gets away safely, reward\) \.+ 8\.33%  \(4\.17% \+500 food, 4\.17% \+2,000")
        self.assertRegex(table, r"comes home alive \.+ 92\.78%")


class Checks(unittest.TestCase):
    def assertProblem(self, data, pattern, scrolling=False):
        found = problems_of(data, scrolling)
        self.assertTrue(any(re.search(pattern, p) for p in found), f"{pattern!r} not in {found}")

    def test_tiny_passes(self):
        self.assertEqual(problems_of(tiny()), [])

    def test_format_and_version(self):
        d = tiny()
        d["version"] = 5
        self.assertProblem(d, "version 5")
        d = tiny()
        d["format"] = "x"
        self.assertProblem(d, "format")

    def test_missing_nodes(self):
        self.assertProblem(tiny(b={"text": "x", "children": [{"next": "nowhere"}]}), "'nowhere' names no node")
        d = tiny()
        d["start"] = "zz"
        self.assertProblem(d, "start 'zz'")
        self.assertProblem(tiny(a={"text": "x", "children": [{"next": "c", "if": {"visited": "zz"}, "else": "d"}]}),
                           "visited 'zz'")

    def test_cycle(self):
        self.assertProblem(tiny(c={"text": "x", "children": [{"next": "a"}]}), "a cycle")

    def test_unreachable(self):
        self.assertProblem(tiny(e={"text": "lonely"}), "node e is never reached")

    def test_dead_end_on_some_history(self):
        keep_d = {"text": "x", "children": [{"next": "d"}]}
        d = tiny(a={"text": "x", "children": [{"next": "c", "if": {"game": 5}}]}, b=keep_d)
        self.assertProblem(d, r"node a \(A New Home\): no child applies")
        d = tiny(a={"text": "x", "children": [{"next": "c", "if": {"game": 5}}], "else": "d"}, b=keep_d)
        self.assertEqual(problems_of(d), [])

    def test_weights(self):
        self.assertProblem(tiny(a={"text": "x", "children": [{"next": "c", "weight": 0}]}), "weight")
        self.assertProblem(tiny(a={"text": "x", "children": [{"next": "c", "weight": 1.5}]}), "weight")

    def test_question_shape(self):
        self.assertProblem(tiny(q={"type": "question", "text": "x", "choices": [{"label": "A", "next": "a"}]}),
                           "exactly two choices")
        self.assertProblem(tiny(b={"type": "question", "text": "x", "choices": [
            {"label": "A", "next": "c"}, {"label": "B", "next": "d"}]}), "only be the start")

    def test_characters(self):
        self.assertProblem(tiny(b={"text": "50% (sad) & \"quoted\""}), "not a placeholder")
        self.assertProblem(tiny(b={"text": "50% & quoted"}), "characters the game cannot show")
        self.assertProblem(tiny(b={"text": "caf\u00e9"}), "characters the game cannot show")

    def test_effect_a_game_lacks(self):
        self.assertProblem(tiny(b={"text": "x", "effects": [{"do": "status", "status": "heathen"}]}),
                           "status heathen is not in A New Home")
        self.assertProblem(tiny(b={"text": "x", "effects": [{"do": "preference", "list": "likes",
                                                             "preference": "frogs"}]}),
                           "'frogs' is not one of A New Home")
        self.assertProblem(tiny(b={"text": "x", "effects": [{"do": "skill", "skills": ["Devotion"], "min": 1,
                                                             "max": 2}]}), "'Devotion' is not one of")
        d = tiny(b={"text": "x", "effects": [{"do": "status", "status": "heathen"}]})
        d["games"] = [5]
        self.assertEqual(problems_of(d), [])

    def test_effect_fields(self):
        self.assertProblem(tiny(b={"text": "x", "effects": [{"do": "health", "min": 0, "max": 50}]}), "health")
        self.assertProblem(tiny(b={"text": "x", "effects": [{"do": "food", "amount": 0}]}), "amount")
        self.assertProblem(tiny(b={"text": "x", "effects": [{"do": "fly"}]}), "an effect is")
        self.assertProblem(tiny(b={"text": "x", "effects": [{"do": "kill", "cause": "(bad)"}]}), "cause")

    def test_unbound_role(self):
        d = tiny(b={"text": "(name2) waves."})
        d["roles"]["friend"] = {"kind": "villager", "optional": True}
        self.assertProblem(d, "may not be bound")
        d["nodes"]["b"]["text"] = "(name1) waves."
        self.assertEqual(problems_of(d), [])
        self.assertProblem(tiny(b={"text": "(friend.name) waves."}), "names no role")

    def test_stranger_has_no_name(self):
        d = tiny(b={"text": "(stranger.name) waves."})
        d["roles"]["stranger"] = {"kind": "stranger"}
        self.assertProblem(d, "a stranger has no name")

    def test_award_rules(self):
        self.assertProblem(tiny(b={"text": "x", "effects": [{"do": "pay_award"}]}), "pay_award with no award")
        self.assertProblem(tiny(b={"text": "You get (award)."}), "no award")

    def test_effect_on_the_gone(self):
        self.assertProblem(tiny(d={"text": "x", "effects": [{"do": "kill"}, {"do": "sick"}]}), "already gone")

    def test_append_needs_an_open_popup(self):
        self.assertProblem(tiny(b={"text": "x", "popup": "append"}), "append with no popup")

    def test_label_fit(self):
        """The owner (2026-11-13): a label may be wider than its button; only the bytes kept and the screen limit it."""
        ok = tiny(q={"type": "question", "text": "x", "choices": [
            {"label": "Curses schmurses. I'm keeping them.", "next": "a"}, {"label": "W" * 30, "next": "b"}]})
        self.assertEqual(problems_of(ok), [])
        self.assertProblem(tiny(q={"type": "question", "text": "x", "choices": [
            {"label": "W" * 31, "next": "a"}, {"label": "B", "next": "b"}]}),
            r"The Lost Children: the label 'W+' runs off the screen")
        d = tiny(q={"type": "question", "text": "x", "choices": [
            {"label": "W" * 31, "next": "a"}, {"label": "B", "next": "b"}]})
        d["games"] = [5]
        self.assertEqual(problems_of(d), [], "New Believers' wider screen shows it whole")
        self.assertProblem(tiny(q={"type": "question", "text": "x", "choices": [
            {"label": "Help (name) now, before the night", "next": "a"}, {"label": "B", "next": "b"}]}),
            "A New Home: the label .* characters with the longest names; at most 39")
        self.assertEqual(cg.label_px(1, "Curses schmurses. I'm keeping them."), 384)

    def test_title_fit(self):
        d = tiny()
        d["title"] = "A title of thirty-one letters!!"
        self.assertProblem(d, "The Secret City: the title")
        d["games"] = [1, 2]
        self.assertEqual(problems_of(d), [])

    def test_text_fit_knows_scrolling(self):
        word = "W" * 60                                   # wider than any popup's line, but cut, so it fits
        self.assertEqual(problems_of(tiny(b={"text": word})), [])
        sentence = " ".join(["word"] * 150) + "."           # one sentence taller than a page
        self.assertProblem(tiny(b={"text": sentence}), "runs off the screen without scrolling")
        self.assertEqual(problems_of(tiny(b={"text": sentence}), scrolling=True), [])
        long = "\n".join(["Short words here."] * 120)       # more bytes than the popup holds
        self.assertProblem(tiny(b={"text": long}), "longer than", scrolling=True)

    def test_too_many_popups(self):
        nodes = {"b": {"text": "1", "children": [{"next": "p2"}]}}
        for i in range(2, 8):
            nodes[f"p{i}"] = {"text": str(i), "children": [{"next": f"p{i + 1}"}]} if i < 7 else {"text": "7"}
        self.assertProblem(tiny(**nodes), "popups; at most")

    def test_every_problem_is_reported(self):
        with self.assertRaises(cg.GraphError) as e:
            cg.load(tiny(b={"text": "x", "children": [{"next": "nowhere", "weight": 0}]}))
        self.assertGreaterEqual(len(e.exception.problems), 2)


class Binary(unittest.TestCase):
    def test_round_trip(self):
        for data in (aa_data(), tiny()):
            g = cg.load(data)
            blob = cg.compile_graph(g)
            self.assertEqual(cg.decompile_graph(blob), g)
            self.assertEqual(cg.compile_graph(cg.decompile_graph(blob)), blob)
            # The normalized graph is itself a valid graph.
            self.assertEqual(cg.load(copy.deepcopy(g)), g)

    def test_header(self):
        blob = cg.compile_graph(cg.load(AA))
        self.assertEqual(blob[:4], b"CIEG")
        version, hsize, fsize = struct.unpack_from("<HHI", blob, 4)
        self.assertEqual((version, hsize, fsize), (1, 80, len(blob)))
        self.assertEqual(struct.unpack_from("<I", blob, 16)[0], 0b11111)
        self.assertEqual(struct.unpack_from("<H", blob, 24)[0], 2)          # requirement kept for shipped events

    def test_damage_is_refused(self):
        blob = bytearray(cg.compile_graph(cg.load(AA)))
        blob[200] ^= 1
        with self.assertRaises(cg.GraphError):
            cg.decompile_graph(bytes(blob))
        with self.assertRaises(cg.GraphError):
            cg.decompile_graph(b"CIEG")

    def test_conditions_round_trip(self):
        d = tiny(a={"text": "x", "children": [
            {"next": "c", "if": {"all": [{"game": [1, 3]}, {"not": {"visited": "q"}}, {"any": [{"role": "subject"},
                                                                                            {"game": 2}]}]},
             "else": "d"}, {"next": "d"}]})
        g = cg.load(d)
        self.assertEqual(cg.decompile_graph(cg.compile_graph(g)), g)


class Placeholders(unittest.TestCase):
    def test_expand(self):
        b = {"subject": cg.Binding("Anh", "f"), "friend": cg.Binding("Bao", "m"),
             "stranger": cg.Binding("", "m")}
        self.assertEqual(cg.expand("(Name) and (his/her) friend (name2); (He/She) saw (him/her).", b),
                         "Anh and her friend Bao; She saw her.")
        self.assertEqual(cg.expand("(name1) met a (stranger.man/woman) with (stranger.his/her) knife.", b),
                         "Anh met a man with his knife.")
        self.assertEqual(cg.expand("(friend.He/She) gains (award) (award_unit).", b, ("tech", 2000)),
                         "He gains 2000 tech points.")
        with self.assertRaises(KeyError):
            cg.expand("(nonsense)", b)

    def test_worst_case(self):
        game = cg.GAMES[1]
        self.assertEqual(cg.worst_case("(name) (he/she) (man/woman)", game, None), "W" * 27 + " she woman")
        self.assertEqual(cg.worst_case("(award)", game, ("food", 500, False)), "999")
        self.assertEqual(cg.worst_case("(award)", game, ("food", 500, True)), "9" * 10)


class Fit(unittest.TestCase):
    def test_wrap_mirrors_ce_wrap(self):
        self.assertEqual(cg.wrap("aaa bbb ccc", 7), ["aaa bbb", "ccc"])
        self.assertEqual(cg.wrap("aaaaaaaaa", 4), ["aaaa", "aaaa", "a"])
        self.assertEqual(cg.wrap("a\nb", 10), ["a", "b"])
        self.assertEqual(cg.popup_lines(cg.Layout(10, 5, True), "T", "x"), 5)  # title + three blank + text

    def test_paginate(self):
        layout = cg.Layout(20, 3, False)
        pages, why = cg.paginate(layout, "", "One two three.\nFour five six seven eight nine ten eleven twelve.")
        self.assertIsNone(why)
        self.assertGreaterEqual(len(pages), 2)
        pages, why = cg.paginate(layout, "", " ".join(["word"] * 40) + ".")
        self.assertIsNotNone(why)

    def test_aa_pages_without_scrolling(self):
        g = cg.load(AA)
        for game in range(1, 6):
            paths = cg.walk(g, cg.Context(game, frozenset(), frozenset(g["roles"])))
            for p in paths:
                for pop in p.popups:
                    layout = getattr(cg.GAMES[game], pop.layout)
                    pages, why = cg.paginate(layout, g["title"], pop.worst, cg.REFUSAL_LINES if pop.effects else 0)
                    self.assertIsNone(why)
                    self.assertLessEqual(len(pages), cg.MAX_PAGES)


class MirrorsTheNativeTables(unittest.TestCase):
    def test_cap_bits(self):
        header = (NATIVE / "story_custom.h").read_text(encoding="utf-8")
        bits = dict(re.findall(r"#define (CAP_\w+)\s+(0x[0-9A-Fa-f]+)u", header))
        for name, value in bits.items():
            self.assertEqual(getattr(cg, name), int(value, 16), name)
        for game in range(1, 6):
            src = (NATIVE / f"story_c{game}.inc").read_text(encoding="utf-8")
            body = src[src.index(f"static const ce_adapter C{game}_ADAPTER = {{"):]
            caps_text = body[body.index("{") + 1:body.index(",\n    \"") if game == 1 else body.index(",\n    0x118")]
            caps = 0
            for name in re.findall(r"CAP_\w+", caps_text):
                caps |= getattr(cg, name)
            self.assertEqual(cg.GAMES[game].caps, caps, game)

    def test_skills(self):
        for game in range(1, 6):
            src = (NATIVE / f"story_c{game}.inc").read_text(encoding="utf-8")
            m = re.search(rf"C{game}_SKILLS\[\] = \{{([^}}]*)\}}", src)
            self.assertEqual(cg.GAMES[game].skills, tuple(re.findall(r'"([^"]+)"', m.group(1))), game)

    def test_preferences(self):
        common = (NATIVE / "story_common.inc").read_text(encoding="utf-8")

        def macro(name):
            m = re.search(rf"#define {name} \\\n((?:\s+\".*\"\s*\\?\n)+)", common)
            return "".join(re.findall(r'"([^"]*)"', m.group(1))).split(",")
        self.assertEqual(list(cg.GAMES[3].preferences), macro("STORY_PREFERENCES_79_VV3"))
        self.assertEqual(list(cg.GAMES[4].preferences), macro("STORY_PREFERENCES_79"))
        self.assertEqual(list(cg.GAMES[5].preferences), macro("STORY_PREFERENCES_79"))
        for game, slots in ((1, "4, 47,"), (2, "62, 62,")):
            src = (NATIVE / f"story_c{game}.inc").read_text(encoding="utf-8")
            body = src[src.index(f"C{game}_ADAPTER = {{"):]
            m = re.search(re.escape(slots) + r"\n((?:\s+\"[^\"]*\",?\n)+)", body)
            listed = "".join(re.findall(r'"([^"]*)"', m.group(1))).split(",")
            self.assertEqual(list(cg.GAMES[game].preferences), listed, game)

    def test_popups_and_labels(self):
        expect = {1: (49, 13, 49, 13, 1, 39), 2: (46, 16, 46, 16, 1, 39), 3: (48, 11, 48, 11, 0, 39),
                  4: (48, 11, 48, 11, 0, 39), 5: (48, 11, 48, 17, 0, 39)}
        for game, numbers in expect.items():
            src = (NATIVE / f"story_c{game}.inc").read_text(encoding="utf-8")
            self.assertIn(", ".join(map(str, numbers)) + ",", src, game)
            g = cg.GAMES[game]
            self.assertEqual((g.question.width, g.question.lines, g.result.width, g.result.lines,
                              int(g.result.with_title), g.label_width), numbers)

    def test_name_room_is_the_last_names_room(self):
        import vv_last_names
        self.assertEqual({n: g.name_room for n, g in cg.GAMES.items()}, vv_last_names.ROOM)


class Library(unittest.TestCase):
    def test_save_and_read(self):
        g = cg.load(AA)
        with tempfile.TemporaryDirectory() as tmp:
            j, b = cg.save_to_library(g, tmp)
            self.assertEqual(j.parent, Path(tmp) / "Virtual Villagers Fun Patcher" / "Custom Island Events")
            self.assertEqual(j.name, "The Aspiring Adventurer.json")
            self.assertEqual(cg.decompile_graph(b.read_bytes()), g)
            (j.parent / "Broken.json").write_text("{", encoding="utf-8")
            lib = cg.read_library(tmp)
            self.assertEqual(lib["The Aspiring Adventurer"], (g, []))
            self.assertIsNone(lib["Broken"][0])

    def test_stem(self):
        self.assertEqual(cg.library_stem("A: <bad>/name?"), "A badname")
        self.assertEqual(cg.library_stem("???"), "Custom Island Event")


CAVE = ROOT / "data" / "cie_graphs" / "the_cave_explorers.json"


def multi(**nodes) -> dict:
    """A version 2 graph: a page, a question, a chance split, another question after a page, endings."""
    g = {
        "format": "vvfp-cie-graph", "version": 2, "title": "Two Questions", "games": [1, 2, 3, 4, 5],
        "roles": {"subject": {"kind": "villager"}},
        "start": "p",
        "nodes": {
            "p": {"text": "(Name) finds a \"door\".", "effects": [{"do": "food", "amount": 100}],
                  "children": [{"next": "q1"}]},
            "q1": {"type": "question", "text": "Open it?", "choices": [
                {"label": "Open", "next": "o"}, {"label": "Leave", "next": "l"}]},
            "o": {"text": "It opens.", "children": [{"next": "o1", "weight": 3}, {"next": "o2"}]},
            "o1": {"popup": "append", "text": "A stair.", "children": [{"next": "q2"}]},
            "o2": {"popup": "append", "text": "A pit.", "effects": [{"do": "kill"}]},
            "q2": {"type": "question", "text": "Go down?", "choices": [
                {"label": "Down", "next": "d"}, {"label": "Up", "next": "u"}]},
            "d": {"text": "Gold.", "effects": [{"do": "tech", "amount": 50}]},
            "u": {"text": "Home."},
            "l": {"text": "(He/She) walks away."},
        },
    }
    g["nodes"].update(nodes)
    return g


class QuestionsAnywhere(unittest.TestCase):
    """Version 2 (v1.35.97): a question may be any node, as often as the author likes."""

    def assertProblem(self, data, pattern, scrolling=False):
        found = problems_of(data, scrolling)
        self.assertTrue(any(re.search(pattern, p) for p in found), f"{pattern!r} not in {found}")

    def test_a_multi_question_graph_passes_and_walks_every_answer(self):
        self.assertEqual(problems_of(multi()), [])
        g = cg.load(multi())
        paths = cg.walk(g, cg.Context(1, frozenset(), frozenset(g["roles"])))
        self.assertEqual(sorted(p.answers for p in paths), sorted([
            (("q1", 0),), (("q1", 0), ("q2", 0)), (("q1", 0), ("q2", 1)), (("q1", 1),)]))
        rows = cg.chances(g, 1)
        self.assertEqual({r.key: r.chance for r in rows[(("q1", 0),)]["ends"]}, {"o2": 1})
        self.assertEqual({r.key: r.chance for r in rows[(("q1", 0), ("q2", 0))]["ends"]}, {"d": 1})
        table = cg.chances_table(g, 1)
        self.assertIn("CHOICES q1 A: OPEN > q2 B: UP", table)
        # The popups: the question's own, the answer's page, the second question.
        p = next(p for p in paths if p.end == "d")
        self.assertEqual([x.layout for x in p.popups], ["plain", "question", "result", "question", "result"])

    def test_version_1_keeps_its_rules(self):
        d = multi()
        d["version"] = 1
        self.assertProblem(d, "characters the game cannot show")         # the double quote is version 2's
        d["nodes"]["p"]["text"] = "(Name) finds a door."
        self.assertProblem(d, "only be the start node in a version 1 event")
        d["version"] = 5
        self.assertProblem(d, "version 5 is not one this patcher reads")

    def test_an_answer_shows_its_own_page_first(self):
        self.assertProblem(multi(l={"type": "branch", "children": [{"next": "q2"}]}),
                           "an answer must show a page of its own before the next question")
        self.assertProblem(multi(u={"type": "branch"}), "an answer must show a page of its own before the event")
        self.assertProblem(multi(p={"type": "branch", "effects": [{"do": "food", "amount": 1}],
                                    "children": [{"next": "q1"}]}),
                           "the changes before this question need a page")

    def test_a_question_makes_no_changes(self):
        self.assertProblem(multi(q2={"type": "question", "text": "Go down?", "effects": [{"do": "sick"}],
                                     "choices": [{"label": "Down", "next": "d"}, {"label": "Up", "next": "u"}]}),
                           "a question makes no changes")

    def test_no_loops_and_no_dangling_answers(self):
        self.assertProblem(multi(u={"text": "Home.", "children": [{"next": "o"}]}), "a cycle")
        self.assertProblem(multi(q2={"type": "question", "text": "x", "choices": [
            {"label": "Down", "next": "d"}, {"label": "Up", "next": "nowhere"}]}), "'nowhere' names no node")

    def test_round_trip_and_versions(self):
        g = cg.load(multi())
        blob = cg.compile_graph(g)
        self.assertEqual(struct.unpack_from("<H", blob, 4)[0], 2)
        self.assertEqual(cg.decompile_graph(blob), g)
        self.assertEqual(cg.compile_graph(cg.decompile_graph(blob)), blob)
        # A version 1 graph is still written as version 1, and read back as it was.
        v1 = cg.load(tiny())
        b1 = cg.compile_graph(v1)
        self.assertEqual(struct.unpack_from("<H", b1, 4)[0], 1)
        self.assertEqual(cg.decompile_graph(b1), v1)
        bad = bytearray(blob)
        struct.pack_into("<H", bad, 4, 5)
        struct.pack_into("<I", bad, 12, 0)
        struct.pack_into("<I", bad, 12, __import__("zlib").crc32(bytes(bad)))
        with self.assertRaises(cg.GraphError):
            cg.decompile_graph(bytes(bad))


class CaveExplorers(unittest.TestCase):
    """The owner's event as the library's second example (scripts/build_cave_explorers_graph.py)."""

    def setUp(self):
        self.data = json.loads(CAVE.read_text(encoding="utf-8"))
        self.g = cg.load(self.data)

    def test_passes_with_and_without_scrolling_and_is_built_from_the_source(self):
        self.assertEqual(problems_of(self.data, False), [])
        self.assertEqual(problems_of(self.data, True), [])
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_cave_explorers_graph as build
        self.assertEqual(build.build(), self.data, "regenerate with scripts/build_cave_explorers_graph.py")

    def test_the_owners_odds(self):
        import vv_cave_explorers as cave
        rows = cg.chances(self.g, 1)

        def ends(*answers):
            return {r.key: r.chance for r in rows[tuple(answers)]["ends"]}
        proceed = ("intro", 0), ("explore_q", 0)
        for side in (0, 1):
            run = ends(*proceed, ("run_q", side))
            self.assertEqual(run["argue_2"] * 100, cave.A_ENDINGS["ARGUE"])
            self.assertEqual(run["makeup"] * 100, cave.A_ENDINGS["MAKEUP"])
            self.assertEqual((run["chasm_1"] + run["chasm_2"]) * 100, cave.A_ENDINGS["CHASM"])
        find = ends(*proceed)
        for key, pct in cave.B_FINDS.items():
            self.assertEqual(find[key.lower()] * 100, pct, key)
        keep = ends(("intro", 0), ("explore_q", 1), ("stay_q", 1))
        self.assertEqual({k: v * 100 for k, v in keep.items()},
                         {k.lower(): v for k, v in cave.KEEP_ENDINGS.items()})
        self.assertEqual(ends(("intro", 0), ("explore_q", 1), ("stay_q", 0)),
                         {"return_food": Fraction(1, 2), "return_tech": Fraction(1, 2)})
        self.assertEqual(ends(("intro", 1)), {"dont": 1})

    def test_the_words_are_the_events(self):
        import vv_cave_explorers as cave
        b = {"subject": cg.Binding("Anh", "f"), "friend": cg.Binding("Bao", "m")}
        names, sexes = {"a": "Anh", "b": "Bao"}, {"a": "f", "b": "m"}
        n = self.g["nodes"]
        self.assertEqual(cg.expand(n["intro"]["text"], b), cave.fill("INTRO", names, sexes))
        self.assertIn("special friend", n["intro"]["text"])
        self.assertEqual(cg.expand(n["dont"]["text"], b), cave.fill("DONT", names, sexes))
        self.assertEqual(cg.expand(n["a_s2"]["text"], b),
                         cave.fill("A_SCREAM", {"s": "Bao", "o": "Anh"}, {"s": "m"}))
        ctx = cg.Context(1, frozenset(), frozenset(self.g["roles"]))
        self.assertEqual(cg.expand(cg.node_text(n["run_q"], ctx, ("a_s2",)), b),
                         cave.fill("RUN", {"s": "Bao"}, {"s": "m"}))
        self.assertEqual(cg.expand(n["keep"]["text"] + " " + n["keep_one"]["text"], b),
                         cave.fill("KEEP", names) + cave.KEEP_JOIN + cave.fill("KEEP_ONE", names, sexes))
        self.assertEqual(cg.expand(n["find_coins"]["text"], b, ("tech", 2000)),
                         cave.fill("FIND_COINS", names, sexes, 2000))
        self.assertEqual(n["stay"]["text"] + " " + n["stay_q"]["text"],
                         cave.TEXTS[[k for k, _ in cave.TEXTS].index("STAY")][1]
                         .replace("{b}", "(name2)").replace("{a}", "(name1)").replace("{He.b}", "(friend.He/She)"))


def v3(**kw) -> dict:
    """A version 3 graph: a ranged award, a puzzle requirement, two villagers at most 5 years apart."""
    g = {
        "format": "vvfp-cie-graph", "version": 3, "title": "Three Rules", "games": [1, 3],
        "requirement": {"min_eligible": 2, "puzzles": {"1": ["The Cave"], "3": ["The Bee Hive"]}},
        "roles": {"subject": {"kind": "villager", "min_age": 18},
                  "friend": {"kind": "villager", "min_age": 18, "max_age_gap": {"role": "subject", "years": 5}}},
        "start": "s",
        "nodes": {"s": {"text": "(name1) and (name2) find (award) (award_unit).",
                        "effects": [{"do": "tech", "amount": 500, "max": 4999, "scaled": True, "defer": True},
                                    {"do": "pay_award"}]}},
    }
    for k, v in kw.items():
        g[k] = v
    return g


class Version3(unittest.TestCase):
    """The owner (2026-11-13): award ranges, "only after a puzzle is solved", "at most N years apart"."""

    def assertProblem(self, data, pattern):
        found = problems_of(data)
        self.assertTrue(any(re.search(pattern, p) for p in found), f"{pattern!r} not in {found}")

    def test_passes_and_round_trips(self):
        self.assertEqual(problems_of(v3()), [])
        g = cg.load(v3())
        self.assertEqual(g["requirement"]["puzzles"], {"1": ["The Cave"], "3": ["The Bee Hive"]})
        self.assertEqual(g["roles"]["friend"]["max_age_gap"], {"role": "subject", "years": 5})
        self.assertEqual(g["nodes"]["s"]["effects"][0]["max"], 4999)
        blob = cg.compile_graph(g)
        self.assertEqual(struct.unpack_from("<H", blob, 4)[0], 3)
        self.assertEqual(cg.decompile_graph(blob), g)
        self.assertEqual(cg.compile_graph(cg.decompile_graph(blob)), blob)

    def test_the_range_in_the_walk_the_fit_and_the_table(self):
        g = cg.load(v3())
        (p,) = cg.walk(g, cg.Context(1, frozenset(), frozenset(g["roles"])))
        self.assertEqual(p.award, ("tech", (500, 4999), True))
        self.assertEqual(cg.award_words(p), "+500 to 4,999 tech points")
        self.assertEqual(cg.worst_case("(award)", cg.GAMES[1], ("tech", (500, 4999), False)), "9999")
        self.assertIn("+500 to 4,999 tech points", cg.chances(g, 1)[None]["outcomes"][0].by_award)

    def test_range_rules(self):
        bad = v3()
        bad["nodes"]["s"]["effects"][0]["max"] = 400
        self.assertProblem(bad, "its top is above its amount")
        bad["nodes"]["s"]["effects"][0]["max"] = -10
        self.assertProblem(bad, "its top is above its amount")
        old = v3()
        old["version"] = 2
        self.assertProblem(old, "an amount range needs format version 3")

    def test_puzzle_rules(self):
        self.assertProblem(v3(requirement={"puzzles": {"1": ["The Moon"]}}), "A New Home's puzzles are")
        self.assertProblem(v3(requirement={"puzzles": {"2": ["Fire"]}}), "'2' is not one of the event's games")
        old = v3()
        old["version"] = 2
        self.assertProblem(old, "needing a puzzle solved needs format version 3")
        self.assertEqual(set(cg.PUZZLES), set(cg.GAMES))

    def test_age_gap_rules(self):
        d = v3()
        d["roles"]["friend"]["max_age_gap"] = {"role": "friend", "years": 5}
        self.assertProblem(d, "the age gap names another villager role")
        d = v3()
        d["roles"]["subject"]["max_age_gap"] = {"role": "friend", "years": 5}
        self.assertProblem(d, "on one of the two roles only")
        d = v3()
        d["roles"]["friend"]["max_age_gap"] = {"role": "subject", "years": 81}
        self.assertProblem(d, "an age gap is 0..80 years")
        d = v3()
        d["roles"]["stranger"] = {"kind": "stranger"}
        d["roles"]["friend"]["max_age_gap"] = {"role": "stranger", "years": 5}
        self.assertProblem(d, "the age gap names another villager role")

    def test_the_cave_explorers_uses_all_three(self):
        import vv_aspiring_adventurer as adv
        g = cg.load(CAVE)
        self.assertEqual(g["version"], 3)
        self.assertEqual(g["requirement"]["puzzles"], {"1": ["The Cave"]})
        self.assertEqual(g["roles"]["friend"]["max_age_gap"], {"role": "subject", "years": 5})
        food, tech = adv.AWARD_RANGES[1]["food"], adv.AWARD_RANGES[1]["tech"]
        ranges = {nid: (n["effects"][0]["do"], n["effects"][0]["amount"], n["effects"][0]["max"])
                  for nid, n in g["nodes"].items() if n["effects"] and n["effects"][0]["do"] in ("food", "tech")}
        self.assertEqual(ranges, {
            "find_coins": ("tech", *tech), "find_treasure": ("tech", 3 * tech[0], 3 * tech[1]),
            "find_food": ("food", 2 * food[0], 2 * food[1]), "return_food": ("food", *food),
            "return_tech": ("tech", *tech), "keep_research": ("tech", *tech)})
        self.assertEqual(g["nodes"]["stay_q"]["choices"][1]["label"], "Curses schmurses. I'm keeping them.")

    def test_the_puzzles_mirror_the_companion(self):
        for game in range(1, 6):
            src = (NATIVE / f"story_c{game}.inc").read_text(encoding="utf-8")
            i = src.index(f"C{game}_PUZZLE_DEFS[] = {{")
            names = tuple(re.findall(r'\{\s*"([^"]+)"', src[i:src.index("};", i)]))
            self.assertEqual(cg.PUZZLES[game], names, game)


def four_doors(version: int = 4) -> dict:
    """A version 4 graph: a four-answer question, one answer leading (after its own page) to a three-answer one."""
    return {
        "format": "vvfp-cie-graph", "version": version, "title": "Four Doors", "games": [3, 4, 5],
        "roles": {"subject": {"kind": "villager"}},
        "start": "q",
        "nodes": {
            "q": {"type": "question", "text": "(Name) finds four doors.", "choices": [
                {"label": "The red door", "next": "a"}, {"label": "The blue door", "next": "b"},
                {"label": "The green door", "next": "c"}, {"label": "The gold door", "next": "d"}]},
            "a": {"text": "Food behind the red door.", "effects": [{"do": "food", "amount": 100}]},
            "b": {"text": "A second room.", "children": [{"next": "q2"}]},
            "q2": {"type": "question", "text": "Three more doors.", "choices": [
                {"label": "Left", "next": "e"}, {"label": "Middle", "next": "f"}, {"label": "Right", "next": "h"}]},
            "e": {"text": "Left."}, "f": {"text": "Middle.", "effects": [{"do": "tech", "amount": 50}]},
            "h": {"text": "Right."},
            "c": {"text": "Tech behind the green door.", "effects": [{"do": "tech", "amount": 100}]},
            "d": {"text": "(Name) is never seen again.", "effects": [{"do": "vanish"}]},
        },
    }


class Version4(unittest.TestCase):
    """The owner (2026-11-13): "Make the 2-4 option thing general" -- a question with 2, 3 or 4 answers."""

    def test_three_and_four_answers_pass(self):
        self.assertEqual(problems_of(four_doors(), False), [])
        self.assertEqual(problems_of(four_doors(), True), [])

    def test_two_to_four_answers_only(self):
        d = four_doors()
        d["nodes"]["q"]["choices"].append({"label": "A fifth", "next": "d"})
        self.assertProblem(d, "a question has 2 to 4 answers")
        d = four_doors()
        d["nodes"]["q"]["choices"] = d["nodes"]["q"]["choices"][:1]
        self.assertProblem(d, "a question has 2 to 4 answers")
        d = four_doors()
        d["nodes"]["q"]["choices"][2]["next"] = "nowhere"
        self.assertProblem(d, "'nowhere' names no node")

    def test_a_new_home_and_the_lost_children_keep_two_for_now(self):
        d = four_doors()
        d["games"] = [1, 2, 3]
        found = problems_of(d)
        self.assertIn("A New Home: a question with more than two buttons is not shown in this game yet (untick the "
                      "game, or keep two buttons)", found)
        self.assertTrue(any(p.startswith("The Lost Children: a question with more than two") for p in found))
        self.assertFalse(any(p.startswith("The Secret City") for p in found))
        self.assertEqual(cg.MORE_ANSWER_GAMES, (3, 4, 5))

    def test_versions_1_to_3_keep_two(self):
        for version in (2, 3):
            self.assertProblem(four_doors(version), "three or four answers need format version 4")
        d = copy.deepcopy(tiny())
        d["nodes"]["q"]["choices"].append({"label": "Maybe", "next": "b"})
        self.assertProblem(d, "three or four answers need format version 4")

    def test_every_answer_its_own_page_and_no_loops(self):
        d = four_doors()
        d["nodes"]["q"]["choices"][3]["next"] = "q2"
        d["nodes"]["q2"]["choices"].append({"label": "Down", "next": "d"})
        self.assertProblem(d, "an answer must show a page of its own before the next question")
        d = four_doors()
        d["nodes"]["e"]["children"] = [{"next": "b"}]
        self.assertProblem(d, "a cycle")

    def test_round_trip_and_version_number(self):
        g = cg.load(four_doors())
        blob = cg.compile_graph(g)
        self.assertEqual(struct.unpack_from("<H", blob, 4)[0], 4)
        self.assertEqual(cg.decompile_graph(blob), g)
        self.assertEqual(cg.compile_graph(cg.decompile_graph(blob)), blob)
        self.assertEqual([c["label"] for c in cg.decompile_graph(blob)["nodes"]["q"]["choices"]],
                         ["The red door", "The blue door", "The green door", "The gold door"])

    def test_the_shipped_examples_compile_to_the_same_bytes(self):
        # Compiled before format version 4 (the module at 538ddc27): versions 1 to 3 are unchanged.
        pins = {"the_aspiring_adventurer.json": "a8eefacb036a67e1534fbb0685ecc3e41963ed837ba971379733a9b0892e4c2c",
                "the_cave_explorers.json": "b922a6878a819698084c7c0f3671012e8a7d0e0f0b22ca11f6af23ae340269be"}
        for name, digest in pins.items():
            blob = cg.compile_graph(cg.load(ROOT / "data" / "cie_graphs" / name))
            self.assertEqual(__import__("hashlib").sha256(blob).hexdigest(), digest, name)

    def test_the_chances_are_keyed_by_answer(self):
        rows = cg.chances(cg.load(four_doors()), 3)
        keys = set(rows)
        self.assertEqual(keys, {(("q", 0),), (("q", 1), ("q2", 0)), (("q", 1), ("q2", 1)), (("q", 1), ("q2", 2)),
                                (("q", 2),), (("q", 3),)})
        table = cg.chances_table(cg.load(four_doors()), 3)
        self.assertIn("CHOICES q D: THE GOLD DOOR", table)
        self.assertIn("q2 C: RIGHT", table)

    def test_the_question_keeps_room_for_its_buttons(self):
        self.assertEqual([cg.answer_room(n) for n in (2, 3, 4)], [0, 3, 6])
        # A question whose text fills the two-answer popup no longer fits one page with four answers: it is paged.
        layout = cg.GAMES[3].question
        words = " ".join(["Word."] * 400)
        two = cg.paginate(layout, "Four Doors", words, cg.answer_room(2))[0]
        four = cg.paginate(layout, "Four Doors", words, cg.answer_room(4))[0]
        self.assertGreater(len(four), len(two))
        paths = cg.walk(cg.load(four_doors()), cg.Context(3, frozenset(), frozenset({"subject"})))
        rooms = {(p.layout, p.room) for h in paths for p in h.popups}
        self.assertIn(("question", 6), rooms)
        self.assertIn(("question", 3), rooms)
        self.assertIn(("result", 6), rooms)            # an answer's first page is shown in the question's popup
        self.assertIn(("result", 3), rooms)

    def assertProblem(self, data, words):
        found = problems_of(data)
        self.assertTrue(any(words in p for p in found), f"{words!r} not in {found}")


if __name__ == "__main__":
    unittest.main()
