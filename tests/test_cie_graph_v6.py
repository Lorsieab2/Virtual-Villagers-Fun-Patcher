"""Branching Custom Island Events format version 6 (the Isola Grand Event Collection, v1.35.97).

Pinned here:
  * versions 1 to 5 compile, normalize and table their chances byte for byte as before version 6 existed
    (tests/data/cie_v1_v5_pins.json, taken at 98cd1b39 before any version 6 code);
  * the shared walk vectors (tests/data/cie_v6_expand_vectors.json, also run by the engine's emulator tests): a
    graph, a fixed random stream, the villagers and answers -> the path, every effect's roll, every pool pick and
    the text the player reads.  Regenerate with  python tests/test_cie_graph_v6.py --write-vectors  (only when
    the contract in docs/event-collection/cie-v6-binary.md changes);
  * the version 6 format: tokens, pools (distinct, weighted, conditional), game words, inline picks, aliases, the
    harm-capable derivation and the protected rules, size words, choice "if", the new effects and conditions, the
    character set and the glyph fallback, the fit with pools, 5 to 7 answers, the binary layout and round trips.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_cie_graph as cg  # noqa: E402
import test_cie_graph as t  # noqa: E402

DATA = ROOT / "tests" / "data"
PINS = json.loads((DATA / "cie_v1_v5_pins.json").read_text(encoding="utf-8"))
VECTORS = DATA / "cie_v6_expand_vectors.json"
GARDEN = DATA / "cie_v6_gardening.json"
KITCHEN = DATA / "cie_v6_kitchen.json"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pinned_cases() -> dict:
    return {
        "the_aspiring_adventurer.json": read(ROOT / "data/cie_graphs/the_aspiring_adventurer.json"),
        "the_cave_explorers.json": read(ROOT / "data/cie_graphs/the_cave_explorers.json"),
        "tiny_v1": t.tiny(),
        "multi_v2": t.multi(),
        "v3": t.v3(),
        "four_doors_v4": t.four_doors(4),
        "four_doors_v5": t.four_doors(5),
        "per_game_v5": t.PerGameAmounts().graph(),
    }


def v6(**kw) -> dict:
    """A small valid version 6 graph (every game); `kw` replaces top-level keys, nodes= adds or replaces nodes."""
    g = {
        "format": "vvfp-cie-graph", "version": 6, "title": "Six", "games": [1, 2, 3, 4, 5],
        "roles": {"hero": {"kind": "villager"}, "pal": {"kind": "villager"}},
        "start": "p",
        "nodes": {
            "p": {"text": "(Hero) and (pal) find {X.1} and {X.2}.", "children": [{"next": "q"}]},
            "q": {"type": "question", "text": "Keep them?", "choices": [
                {"label": "Keep", "next": "k"}, {"label": "Leave", "next": "l"}]},
            "k": {"text": "(Hero) keeps them."},
            "l": {"text": "(Pal) leaves them."},
        },
        "pools": {"X": {"distinct": True, "items": ["a shell", "a stone", "a feather"]}},
    }
    nodes = kw.pop("nodes", None)
    g.update(kw)
    if nodes:
        g["nodes"].update(nodes)
    return g


GUARD = {
    "format": "vvfp-cie-graph", "version": 6, "title": "The Ledge", "games": [3],
    "roles": {"climber": {"kind": "villager"}},
    "start": "p",
    "nodes": {
        "p": {"text": "(Climber) reaches the ledge.", "children": [{"next": "fall", "weight": 3}, {"next": "safe"}]},
        "fall": {"popup": "append", "text": "(climber.He/She) slips and is gone.", "effects": [{"do": "vanish",
                                                                                                 "role": "climber"}]},
        "safe": {"popup": "append", "text": "(climber.He/She) climbs down safely."},
    },
}


GAPS = {
    # G1-G9 (collection_gaps_spec.md): the other member of an alias, distinct_from, a one-option brace, a game word
    # inside a pick, {@tribe}, a stranger first, a quoted title, damage and skill sizes, five buttons.
    "format": "vvfp-cie-graph", "version": 6, "title": "The \"Twin\" Cooks", "games": [1, 3],
    "words": {"chief": {"3": "the Chief", "*": "the elders"}},
    "roles": {
        "judge": {"kind": "stranger", "sex": "female"},
        "cook1": {"kind": "villager"}, "cook2": {"kind": "villager"},
        "winner": {"kind": "alias", "of": ["cook1", "cook2"]},
        "loser": {"kind": "other", "of": "winner"},
    },
    "pools": {
        "LIKE": {"items": ["soup", "stew", "cake"]},
        "HATE": {"items": ["soup", "stew", "cake"], "distinct_from": ["LIKE"]},
    },
    "start": "p",
    "nodes": {
        "p": {"text": "{@Tribe} gathers. The judge likes {LIKE} and hates {HATE}. {a quiet} morning for "
                      "{the {@chief}|2:{@tribe}}.", "children": [{"next": "q"}]},
        "q": {"type": "question", "text": "Who wins?", "choices": [
            {"label": "One", "next": "a"}, {"label": "Two", "next": "a"}, {"label": "Three", "next": "a"},
            {"label": "Four", "next": "a"}, {"label": "Five", "next": "b"}]},
        "a": {"text": "(Winner) wins; (loser) sulks and (loser.his/her) hut shakes.",
              "effects": [{"do": "skill", "role": "winner", "skills": ["Farming"], "size": "large"},
                          {"do": "mood", "role": "loser", "mood": "bad"},
                          {"do": "damage", "size": "small"}]},
        "b": {"text": "A tie: (cook1) and (cook2) share it."},
    },
}


CAPS = {
    # The owner's ALL-CAPS labels: all-caps placeholders give the words in capitals; a long VV3 title by pixels.
    "format": "vvfp-cie-graph", "version": 6, "title": "The Village Idiot and the Impossible Invention",
    "games": [3, 4, 5],
    "roles": {"subject": {"kind": "villager"}, "friend": {"kind": "villager"}},
    "start": "q",
    "nodes": {
        "q": {"type": "question", "text": "(Name) builds a machine; (friend.he/she) watches.", "choices": [
            {"label": "TELL (HIM/HER) TO STOP BEFORE ANYONE IS HURT.", "next": "a"},
            {"label": "LET (HIM/HER) FINISH, WITH (FRIEND.HIM/HER) WATCHING.", "next": "b"}]},
        "a": {"text": "(NAME) STOPS. (FRIEND.HE/SHE) CHEERS FOR (HIM/HER)."},
        "b": {"text": "(Name) finishes; (friend.Name) claps."},
    },
}

NO_ROLES = {
    # No roles at all: the only patient is story text (as V20 crisis D1).
    "format": "vvfp-cie-graph", "version": 6, "title": "A Stranger on the Sand", "games": [1, 2, 3, 4, 5],
    "roles": {},
    "start": "p",
    "nodes": {
        "p": {"text": "A stranger lies ill on the sand; the healers gather.", "children": [{"next": "q"}]},
        "q": {"type": "question", "text": "What do the healers do?", "choices": [
            {"label": "Tend the stranger", "next": "a"}, {"label": "Send for help", "next": "b"}]},
        "a": {"text": "The stranger recovers and leaves {a gift|2:a song} behind.",
              "effects": [{"do": "food", "size": "small", "scaled": True}]},
        "b": {"text": "{@Tribe} comes; the stranger is gone by morning.",
              "children": [{"next": "b1"}, {"next": "b2", "weight": 3}]},
        "b1": {"popup": "append", "text": "No one knows where."},
        "b2": {"popup": "append", "text": "Footprints lead to the sea."},
    },
}

TITLES = {
    # Per-node popup titles (cie-v6-binary.md 14): the opening picks the title (V24); the answer's first page,
    # shown in the question's own popup, keeps the question's title; the next popup takes the answer's.
    "format": "vvfp-cie-graph", "version": 6, "title": "The Revolution", "games": [1, 2, 3, 4, 5],
    "roles": {"subject": {"kind": "villager"}},
    "start": "b",
    "nodes": {
        "b": {"type": "branch", "children": [{"next": "inv"}, {"next": "dis"}]},
        "inv": {"title": "The Revolutionary Invention", "text": "(Name) builds a wondrous machine.",
                "children": [{"next": "q"}]},
        "dis": {"title": "The Revolutionary Discovery", "text": "(Name) finds a wondrous cave.",
                "children": [{"next": "q"}]},
        "q": {"type": "question", "text": "Show the elders?", "choices": [
            {"label": "Show them", "next": "y"}, {"label": "Keep it quiet", "next": "n"}]},
        "y": {"title": "The Elders Decide", "text": "The elders gather around (him/her).",
              "children": [{"next": "y2"}]},
        "y2": {"text": "They decide to let (him/her) carry on."},
        "n": {"text": "(Name) keeps the secret."},
    },
}


def binding(spec: dict) -> dict:
    return {r: cg.Binding(v["name"], v["sex"]) for r, v in spec.items()}


def vector_cases() -> list[dict]:
    """The inputs of the shared vectors (the expected parts are made by simulate and pinned in the file)."""
    garden, kitchen = read(GARDEN), read(KITCHEN)
    stream = [7, 3, 2, 9, 4, 1, 5, 8, 6, 2, 11, 13, 17, 19, 23, 29]
    two = {"cook1": {"name": "Ana", "sex": "f"}, "cook2": {"name": "Bo", "sex": "m"}, "trader": {"name": "", "sex": "f"}}
    three = dict(two, helper={"name": "Cy", "sex": "m"})
    return [
        {"name": "gardening_vv3", "graph": garden, "game": 3, "unicode": False,
         "rolls": [4, 1, 2, 3, 0, 5, 7, 2, 9, 3, 6, 8], "bindings": {"gardener1": {"name": "Ana", "sex": "f"},
                                                                     "gardener2": {"name": "Bo", "sex": "m"}},
         "answers": [0], "facts": None},
        {"name": "gardening_vv3_plots", "graph": garden, "game": 3, "unicode": False,
         "rolls": [5, 5, 3, 1, 2, 4, 6, 0, 1, 2, 3, 4], "bindings": {"gardener1": {"name": "Kai", "sex": "m"},
                                                                     "gardener2": {"name": "Lea", "sex": "f"}},
         "answers": [1], "facts": None},
        {"name": "kitchen_vv1_trade", "graph": kitchen, "game": 1, "unicode": False, "rolls": stream,
         "bindings": two, "answers": [0], "facts": None},
        {"name": "kitchen_vv1_trade_unicode", "graph": kitchen, "game": 1, "unicode": True, "rolls": stream,
         "bindings": two, "answers": [0], "facts": None},
        {"name": "kitchen_vv1_keep", "graph": kitchen, "game": 1, "unicode": False, "rolls": stream[1:],
         "bindings": two, "answers": [1], "facts": None},
        {"name": "kitchen_vv1_sell_helper", "graph": kitchen, "game": 1, "unicode": False, "rolls": stream,
         "bindings": three, "answers": [3], "facts": None},
        {"name": "kitchen_vv3_ask_chief", "graph": kitchen, "game": 3, "unicode": False, "rolls": stream,
         "bindings": two, "answers": [4], "facts": None},
        {"name": "guard_harmable", "graph": GUARD, "game": 3, "unicode": False, "rolls": [0, 0],
         "bindings": {"climber": {"name": "Dee", "sex": "f"}}, "answers": [], "facts": ["harmable:climber"]},
        {"name": "guard_protected_now", "graph": GUARD, "game": 3, "unicode": False, "rolls": [0, 0],
         "bindings": {"climber": {"name": "Dee", "sex": "f"}}, "answers": [], "facts": []},
        {"name": "gaps_vv1_tribe", "graph": GAPS, "game": 1, "unicode": False, "rolls": [1, 0, 0, 2, 5, 3, 1, 7, 4, 9, 2, 8, 6, 3, 5, 1, 0, 7, 2, 4],
         "bindings": {"judge": {"name": "", "sex": "f"}, "cook1": {"name": "Ana", "sex": "f"},
                      "cook2": {"name": "Bo", "sex": "m"}}, "answers": [0], "facts": None, "tribe": "Kalahuna"},
        {"name": "gaps_vv3_no_tribe", "graph": GAPS, "game": 3, "unicode": False, "rolls": [0, 1, 1, 0, 9, 4, 2, 6, 8, 3, 7, 1, 5, 2, 0, 6, 4, 9, 3, 8],
         "bindings": {"judge": {"name": "", "sex": "f"}, "cook1": {"name": "Ana", "sex": "f"},
                      "cook2": {"name": "Bo", "sex": "m"}}, "answers": [0], "facts": None, "tribe": None},
        {"name": "caps_vv3", "graph": CAPS, "game": 3, "unicode": False, "rolls": [0, 0, 0, 0],
         "bindings": {"subject": {"name": "Ana", "sex": "f"}, "friend": {"name": "Bo", "sex": "m"}},
         "answers": [0], "facts": None},
        {"name": "no_roles_vv5", "graph": NO_ROLES, "game": 5, "unicode": False, "rolls": [3, 1, 4, 1, 5],
         "bindings": {}, "answers": [1], "facts": None},
        {"name": "node_titles_vv2", "graph": TITLES, "game": 2, "unicode": False, "rolls": [0],
         "bindings": {"subject": {"name": "Ana", "sex": "f"}}, "answers": [0], "facts": None},
        {"name": "node_titles_vv4", "graph": TITLES, "game": 4, "unicode": False, "rolls": [1],
         "bindings": {"subject": {"name": "Bo", "sex": "m"}}, "answers": [0], "facts": None},
    ]


def run_case(case: dict) -> dict:
    g = cg.load(case["graph"], True)
    facts = None if case["facts"] is None else frozenset(case["facts"])
    r = cg.simulate(g, case["game"], case["rolls"], binding(case["bindings"]), case["answers"],
                    facts=facts, unicode=case["unicode"], tribe=case.get("tribe"))
    r["cieg_sha256"] = sha(cg.compile_graph(g))
    return r


def write_vectors() -> None:
    out = {"_about": "Shared walk vectors for CIE graph format version 6 (docs/event-collection/cie-v6-binary.md "
                     "section 6).  Each case: a graph, the game, the random stream (each roll taken % n; none for "
                     "n <= 1), the villagers bound, the answer clicked at each question (its choice index), the "
                     "run-time facts (null = every bound villager harmable, every threshold met) and whether the "
                     "Unicode Text companion is on.  expect: the path, each effect's roll [a, b], each pool pick "
                     "[pool, instance, item index] in draw order, the aliases drawn, each popup's text as the player "
                     "reads it (before paging), the rolls used and the compiled .cieg's SHA-256.  Run by "
                     "tests/test_cie_graph_v6.py and the engine's emulator tests.",
           "cases": []}
    for case in vector_cases():
        c = dict(case)
        c["expect"] = run_case(case)
        out["cases"].append(c)
    VECTORS.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")


class OlderVersionsUnchanged(unittest.TestCase):
    def test_every_pinned_graph_is_byte_identical(self):
        cases = pinned_cases()
        self.assertEqual(set(cases), set(PINS))
        for name, data in cases.items():
            with self.subTest(name):
                g = cg.load(data)
                pin = PINS[name]
                self.assertEqual(g["version"], pin["version"])
                blob = cg.compile_graph(g)
                self.assertEqual(sha(blob), pin["cieg_sha256"])
                self.assertEqual(sha(json.dumps(g, sort_keys=True).encode()), pin["normalized_sha256"])
                tables = "\n\n".join(cg.chances_table(g, n) for n in g["games"])
                self.assertEqual(sha(tables.encode()), pin["chances_sha256"])
                self.assertEqual(cg.compile_graph(cg.decompile_graph(blob)), blob)

    def test_v6_words_are_refused_before_version_6(self):
        d = t.tiny()
        d["pools"] = {"A": {"items": ["x"]}}
        self.assertTrue(any("version 6" in p for p in t.problems_of(d)))
        d = t.four_doors(5)
        d["nodes"]["a"]["effects"] = [{"do": "celebrate"}]
        self.assertTrue(any("celebrate needs format version 6" in p for p in t.problems_of(d)))
        d = t.four_doors(5)
        d["nodes"]["q"]["choices"].append({"label": "The fifth door", "next": "a"})
        self.assertTrue(any("five to seven need format version 6" in p for p in t.problems_of(d)))


class SharedVectors(unittest.TestCase):
    def test_every_vector(self):
        data = read(VECTORS)
        self.assertEqual([c["name"] for c in data["cases"]], [c["name"] for c in vector_cases()])
        for case in data["cases"]:
            with self.subTest(case["name"]):
                self.assertEqual(run_case(case), case["expect"])

    def test_the_vectors_say_what_the_contract_says(self):
        by = {c["name"]: c["expect"] for c in read(VECTORS)["cases"]}
        g = by["gardening_vv3"]
        a = [p for p in g["picks"] if p[0] == "A"]
        self.assertEqual([p[1] for p in a], [1, 2])
        self.assertNotEqual(a[0][2], a[1][2])                     # distinct
        self.assertIn("Ana favors", g["popups"][0])
        # VV1 without the Unicode Text companion: ; & % ( ) fall back; with it, the real characters.
        plain, uni = by["kitchen_vv1_trade"]["popups"][0], by["kitchen_vv1_trade_unicode"]["popups"][0]
        self.assertIn("100 percent", plain)
        self.assertIn("100%", uni)
        self.assertNotIn(";", plain)
        self.assertEqual(by["kitchen_vv1_trade"]["aliases"], {"either": "cook2"})
        self.assertIn("the elders", plain)                         # {@chief} in A New Home
        self.assertIn("The Chief approves.", by["kitchen_vv3_ask_chief"]["popups"][-1])
        self.assertIn("Cy helps himself.", by["kitchen_vv1_sell_helper"]["popups"][-1])
        # The harm guard: harmable, the 3-in-4 fall happens on roll 0; protected now, it is taken out.
        self.assertEqual(by["guard_harmable"]["nodes"], ["p", "fall"])
        self.assertEqual(by["guard_protected_now"]["nodes"], ["p", "safe"])
        self.assertEqual(by["guard_protected_now"]["rolls_used"], 0)   # one child left, weight 1: no roll


class ActionsTable(unittest.TestCase):
    def test_the_shipped_actions_are_the_catalog(self):
        catalog = read(ROOT / "tests" / "cie_behaviour_catalog.json")
        for n in range(1, 6):
            self.assertEqual({k: (v["group"], v["unsafe"]) for k, v in cg.actions(n).items()},
                             {a["label"]: (a["group"], bool(a["unsafe"])) for a in catalog[str(n)]}, n)


class Tokens(unittest.TestCase):
    def test_tokens_and_braces(self):
        self.assertEqual(cg.text_tokens(r"a \(b\) (name) {X.2} {@w} {1:x|y}"),
                         [("lit", "a "), ("esc", "\\("), ("lit", "b"), ("esc", "\\)"), ("lit", " "),
                          ("ph", "(name)"), ("lit", " "), ("brace", "{X.2}"), ("lit", " "), ("brace", "{@w}"),
                          ("lit", " "), ("brace", "{1:x|y}")])
        self.assertEqual(cg.parse_brace("X.2"), ("pool", "X", 2))
        self.assertEqual(cg.parse_brace("X"), ("pool", "X", 1))
        self.assertEqual(cg.parse_brace("@chief"), ("word", "chief"))
        self.assertEqual(cg.parse_brace("3:a|b"), ("inline", [(3, "a"), (1, "b")]))
        self.assertEqual(cg.parse_brace("X.9")[0], "bad")
        self.assertEqual(cg._canon_text("{1:a|1:b} {3:a|b}"), "{a|b} {3:a|1:b}")

    def test_v6_placeholders(self):
        roles = {"gardener1": {"kind": "villager"}, "friend": {"kind": "villager"}}
        p = cg.parse_placeholder_v6("Gardener1", roles)
        self.assertEqual((p.role, p.what, p.capital), ("gardener1", "name", True))
        self.assertEqual(cg.parse_placeholder_v6("friend.himself/herself", roles).what, "himself/herself")
        self.assertEqual(cg.parse_placeholder_v6("Woman/Man", roles).role, "gardener1")   # first role: no subject
        self.assertIsNone(cg.parse_placeholder_v6("nobody", roles))
        self.assertIsNone(cg.parse_placeholder_v6("name1", roles))                        # no subject role
        g = cg.lower(cg.load(v6(roles={"hero": {"kind": "villager"}, "pal": {"kind": "villager", "sex": "female"}})))
        b = {"hero": cg.Binding("Al", "m"), "pal": cg.Binding("Bea", "f")}
        self.assertEqual(cg.expand_v6("(pal.Woman/Man), (hero.boy/girl), (pal.son/daughter), (hero.Himself/Herself)",
                                      g, b), "Woman, boy, daughter, Himself")

    def test_role_ids_and_keywords(self):
        self.assertTrue(any("cannot be name" in p for p in t.problems_of(v6(roles={"Name": {"kind": "villager"}}))))
        d = v6(roles={"hero": {"kind": "villager"}, "pal": {"kind": "villager"}, "Pal": {"kind": "villager"}})
        self.assertTrue(any("differ only in capitals" in p for p in t.problems_of(d)))

    def test_characters(self):
        self.assertEqual(t.problems_of(v6(nodes={"k": {"text": "Salt; pepper & 50% \\(maybe\\) / so."}})), [])
        for bad in ("a { b", "a | b", "a @ b", "a \\n b", "(nonsense)", "x}", "é"):
            self.assertTrue(t.problems_of(v6(nodes={"k": {"text": bad}})), bad)
        self.assertEqual(cg.glyph_fallback("a;b(c)&d%", 2), "a,b-c-anddpercent".replace("dpercent", "d percent"))
        self.assertEqual(cg.glyph_fallback("a;b", 3), "a;b")
        self.assertEqual(cg.glyph_fallback("a;b", 1, unicode=True), "a;b")


class Pools(unittest.TestCase):
    def test_pool_rules(self):
        self.assertEqual(t.problems_of(v6()), [])
        # G4: a one-option brace that cannot be a name is its text; an identifier-shaped one must name a list.
        self.assertEqual(cg.load(v6(nodes={"k": {"text": "{X} or {two words} or {quiet!}"}}))["nodes"]["k"]["text"],
                         "{X} or two words or quiet!")
        for typo in ("{Y}", "{Y.2}", "{Dish_2}"):
            self.assertTrue(any(f"unknown list {typo[1:-1].split('.')[0]}" in p
                                for p in t.problems_of(v6(nodes={"k": {"text": f"(Hero) keeps {typo}."}}))), typo)
        self.assertTrue(any("names no game word" in p for p in t.problems_of(v6(nodes={"k": {"text": "{@nope}"}}))))
        d = v6(pools={"X": {"distinct": True, "items": ["a"]}})
        self.assertTrue(any("2 different items are used; it has 1" in p for p in t.problems_of(d)))
        d = v6(pools={"X": {"items": ["{X}"]}})
        self.assertTrue(any("name themselves" in p for p in t.problems_of(d)))
        d = v6(pools={"X": {"items": ["{A}"]}, "A": {"items": ["{B}"]}, "B": {"items": ["{C}"]},
                      "C": {"items": ["c"]}})
        self.assertTrue(any("more than 3 deep" in p for p in t.problems_of(d)))
        d = v6(pools={"X": {"items": ["{A}"]}, "A": {"items": ["{B}"]}, "B": {"items": ["b"]}})
        self.assertEqual(t.problems_of(d), [])
        d = v6(pools={"_X": {"items": ["a"]}})
        self.assertTrue(any("starting with a letter" in p for p in t.problems_of(d)))
        d = v6(pools={"X": {"items": [{"text": "a", "if": {"game": [3]}}]}})
        self.assertTrue(any("no item that can be drawn" in p for p in t.problems_of(d)))

    def test_conditional_and_weighted_items_in_the_draw(self):
        d = v6(games=[1, 3], pools={"X": {"items": [{"text": "a", "weight": 5}, {"text": "b", "if": {"game": [3]}},
                                                    "c"]}})
        d["nodes"]["p"]["text"] = "(Hero) and (pal) find {X}."
        g = cg.load(d)
        b = {"hero": cg.Binding("Al", "m"), "pal": cg.Binding("Bea", "f")}
        # VV1: items a (5) and c (1): total 6, roll 5 -> c; VV3: a, b, c: total 7, roll 5 -> b.
        self.assertEqual(cg.simulate(g, 1, [5], b, [0])["picks"], [["X", 1, 2]])
        self.assertEqual(cg.simulate(g, 3, [5], b, [0])["picks"], [["X", 1, 1]])
        self.assertEqual(cg.simulate(g, 3, [4], b, [0])["picks"], [["X", 1, 0]])

    def test_worst_case_takes_the_longest_item(self):
        d = v6(pools={"X": {"items": ["a", "a much longer item", "b"]}})
        d["nodes"]["p"]["text"] = "{X} {X.2}"
        lg = cg.lower(cg.load(d))
        self.assertEqual(cg.worst_v6("{X} {X.2}", lg, cg.GAMES[3], None), "a much longer item a much longer item")

    def test_include_pools(self):
        shared = {"pools": {"mats": {"items": ["wood", "stone"]}}}
        d = v6(include_pools=["mats"])
        d["nodes"]["k"]["text"] = "(Hero) keeps {mats}."
        g, problems = cg.validate(d, shared_pools=shared)
        self.assertEqual(problems, [])
        self.assertEqual(g["pools"]["mats"]["items"][1]["text"], "stone")
        self.assertNotIn("include_pools", g)
        self.assertTrue(any("not a shared pool" in p for p in cg.validate(v6(include_pools=["nope"]),
                                                                           shared_pools=shared)[1]))
        self.assertTrue(any("also one of the event's own" in p for p in cg.validate(v6(include_pools=["X"]),
                                                                                     shared_pools={"X": {}})[1]))

    def test_game_words(self):
        d = v6(games=[1, 3], words={"chief": {"3": "the Chief", "*": "the elders"}})
        d["nodes"]["k"]["text"] = "(Hero) asks {@chief}."
        g = cg.load(d)
        self.assertEqual(g["words"], {"chief": {"1": "the elders", "3": "the Chief"}})
        self.assertTrue(any("no word for" in p for p in t.problems_of(v6(games=[1, 3],
                                                                          words={"chief": {"3": "the Chief"}}))))
        self.assertTrue(any("names no game word" in p for p in t.problems_of(v6(nodes={"k": {"text": "{@x}"}}))))
        self.assertTrue(any("not one of the event's games" in p
                            for p in t.problems_of(v6(games=[3], words={"w": {"3": "a", "4": "b"}}))))


class RolesAndSafety(unittest.TestCase):
    def test_requirements_normalize_and_round_trip(self):
        d = v6(roles={"hero": {"kind": "villager", "max_age": 13, "min_age": 3, "sex": "female",
                               "skill": {"names": ["Farming", "Devotion"], "min": 5, "pick": "highest"}},
                      "pal": {"kind": "villager", "special": "nursing_parent"},
                      "who": {"kind": "alias", "of": ["pal", "hero"]}})
        d["nodes"]["l"]["text"] = "(Who) leaves them."
        g = cg.load(d, True)
        self.assertEqual(g["roles"]["who"]["of"], ["hero", "pal"])              # role order
        self.assertEqual(g["roles"]["hero"]["skill"], {"names": ["Farming", "Devotion"], "min": 5, "pick": "highest"})
        blob = cg.compile_graph(g)
        self.assertEqual(cg.decompile_graph(blob), cg.without_names(g))
        role = struct.unpack_from("<BBBBHBBBBHBBH", blob, struct.unpack_from("<I", blob, 44)[0])
        self.assertEqual(role[0], 0)
        self.assertEqual(role[7], 13)                                            # max_age
        self.assertEqual((role[10], role[11]), (5, 1))                          # skill min, highest
        alias = struct.unpack_from("<BBBBHBBBBHBBH", blob, struct.unpack_from("<I", blob, 44)[0] + 32)
        self.assertEqual((alias[0], alias[12]), (2, 0b11))
        pal = struct.unpack_from("<BBBBHBBBBHBBH", blob, struct.unpack_from("<I", blob, 44)[0] + 16)
        self.assertEqual(pal[8], 3)                                               # special nursing_parent

    def test_special_roles_only_in_their_games(self):
        d = v6(roles={"hero": {"kind": "villager", "special": "golden_child"}, "pal": {"kind": "villager"}})
        self.assertTrue(any("golden_child is only in A New Home" in p for p in t.problems_of(d)))
        d["games"] = [1]
        self.assertEqual(t.problems_of(d), [])

    def test_exclude_flags_normalise_into_protected(self):
        g = cg.load(v6(roles={"hero": {"kind": "villager", "exclude_nursing": False}, "pal": {"kind": "villager"}}))
        self.assertEqual((g["roles"]["hero"]["protected"], g["roles"]["pal"]["protected"]), ("allow", "auto"))
        self.assertNotIn("exclude_nursing", g["roles"]["hero"])

    def test_harm_capable_and_the_protected_filter(self):
        d = v6(nodes={"k": {"text": "(Hero) keeps them.", "effects": [{"do": "kill", "role": "hero"}]},
                      "l": {"text": "(Pal) leaves them.", "effects": [{"do": "skill", "role": "pal",
                                                                         "skills": ["Farming"], "min": 1, "max": 2}]}})
        g = cg.load(d)
        self.assertEqual(cg.harm_capable(g), {"hero"})
        blob = cg.compile_graph(g)
        roles = struct.unpack_from("<I", blob, 44)[0]
        hero_flags, pal_flags = blob[roles + 1], blob[roles + 17]
        self.assertEqual(hero_flags & (16 | 32 | 6), 16 | 32 | 6)
        self.assertEqual(pal_flags & (16 | 32 | 6), 0)                       # harmless: protected may take part
        # An owner's collection event never allows protected villagers into a harm-capable role ...
        d["roles"]["hero"]["protected"] = "allow"
        self.assertEqual(t.problems_of(d), [])                                # (a player's own graph: they decide)
        d["collection"] = {"id": "x", "lines": [1, 2]}
        self.assertTrue(any("cannot be allow in a collection event" in p for p in t.problems_of(d)))
        # ... and an explicit "exclude" keeps them out of a harmless role too.
        d["roles"]["hero"]["protected"] = "auto"
        d["roles"]["pal"]["protected"] = "exclude"
        g = cg.load(d)
        blob = cg.compile_graph(g)
        self.assertTrue(blob[roles + 17] & 32)
        self.assertEqual(cg.decompile_graph(blob), cg.without_names(g))

    def test_every_harm_counts(self):
        harmful = [{"do": "kill"}, {"do": "vanish"}, {"do": "sick"}, {"do": "health", "min": 1, "max": 50},
                   {"do": "health_change", "min": -5, "max": 5}, {"do": "preference", "list": "dislikes",
                                                                  "preference": "ants"},
                   {"do": "skill", "skills": ["Farming"], "min": -10, "max": -5}, {"do": "mood", "mood": "bad"},
                   {"do": "action", "action": "Shaking head"}]
        harmless = [{"do": "health", "min": 100, "max": 100}, {"do": "health_change", "min": 5, "max": 10},
                    {"do": "preference", "list": "likes", "preference": "ants"}, {"do": "mood", "mood": "good"},
                    {"do": "skill", "skills": ["Farming"], "set": 100}, {"do": "action", "action": "Dancing"},
                    {"do": "celebrate", "who": "hero"}]
        for e in harmful + harmless:
            e = dict(e)
            if e["do"] != "celebrate":
                e["role"] = "hero"
            g = cg.load(v6(games=[1], nodes={"k": {"text": "(Hero) keeps them.", "effects": [e]}}))
            self.assertEqual(cg.harm_capable(g) == {"hero"}, e in [dict(h, role="hero") for h in harmful], e)

    def test_an_alias_harmed_harms_its_members_and_is_guarded(self):
        d = v6(roles={"hero": {"kind": "villager"}, "pal": {"kind": "villager"},
                      "one": {"kind": "alias", "of": ["hero", "pal"]}},
               nodes={"p": {"text": "(Hero) and (pal) find {X.1} and {X.2}.",
                            "children": [{"next": "q", "weight": 3}, {"next": "hurt"}]},
                      "hurt": {"popup": "append", "text": "(One) falls.", "effects": [{"do": "vanish", "role": "one"}]}})
        g = cg.load(d)
        self.assertEqual(cg.harm_capable(g), {"one", "hero", "pal"})
        lg = cg.lower(g)
        self.assertEqual(lg["nodes"]["p"]["children"][1]["guard"], {"harmable": "one"})
        self.assertIsNone(lg["nodes"]["p"]["children"][0]["guard"])
        blob = cg.compile_graph(g)
        child = struct.unpack_from("<HHHHHH", blob, struct.unpack_from("<I", blob, 52)[0] + 12)
        self.assertNotEqual(child[5], cg.NONE)
        # The walk splits on the alias: one in two the hero, one in two the pal.
        rows = cg.chances(g, 3)
        self.assertTrue(rows)


class EffectsAndConditions(unittest.TestCase):
    def test_new_effects_round_trip(self):
        d = v6(games=[3], nodes={"k": {"text": "(Hero) keeps them.", "effects": [
            {"do": "celebrate"}, {"do": "celebrate", "who": "pal"}, {"do": "action", "role": "hero",
                                                                    "action": "Rain dancing"},
            {"do": "mood", "role": "pal", "mood": "good"}, {"do": "health_change", "role": "hero", "min": -9, "max": 9},
            {"do": "skill", "role": "pal", "skills": ["Farming", "Healing"], "set": 100},
            {"do": "damage", "structures": ["hut"], "min": 10, "max": 50}, {"do": "damage", "min": 1, "max": 100},
            {"do": "food", "size": "huge", "scaled": True}, {"do": "tech", "size": "small", "loss": True}]}})
        g = cg.load(d)
        blob = cg.compile_graph(g)
        self.assertEqual(cg.decompile_graph(blob), cg.without_names(g))
        self.assertEqual(cg.compile_graph(cg.decompile_graph(blob)), blob)
        codes = [blob[struct.unpack_from("<I", blob, 56)[0] + 16 * i] for i in range(10)]
        self.assertEqual(codes, [11, 11, 12, 13, 14, 15, 16, 16, 1, 2])
        e = g["nodes"]["k"]["effects"]
        self.assertEqual(e[8]["per_game"], {"3": [600, 1800]})
        self.assertEqual(e[9]["per_game"], {"3": [-1000, -500]})
        self.assertEqual((e[9]["amount"], e[9]["max"]), (-1000, -500))
        e0 = struct.unpack_from("<BBBBiiHH", blob, struct.unpack_from("<I", blob, 56)[0])
        self.assertEqual(e0[1], 0xFF)                                          # celebrate: everyone

    def test_sizes_are_the_design_table(self):
        self.assertEqual([cg.size_range("tech", s, 1) for s in ("small", "normal", "large", "huge")],
                         [(250, 2499), (500, 4999), (1000, 9998), (1500, 14997)])
        self.assertEqual([cg.size_range("food", s, 4) for s in ("small", "normal", "large", "huge")],
                         [(150, 150), (300, 300), (600, 600), (900, 900)])
        self.assertEqual(cg.size_range("food", "small", 5), (25, 150))
        g = cg.load(v6(nodes={"k": {"text": "(Hero) keeps them.", "effects": [{"do": "food", "size": "large"}]}}))
        self.assertEqual(g["nodes"]["k"]["effects"][0]["per_game"],
                         {"1": [400, 3000], "2": [200, 3000], "3": [400, 1200], "4": [600, 600], "5": [100, 600]})

    def test_effect_checks(self):
        for bad in ({"do": "mood", "role": "hero", "mood": "meh"}, {"do": "health_change", "role": "hero",
                                                                   "min": 0, "max": 0},
                    {"do": "damage", "min": 0, "max": 5}, {"do": "action", "role": "hero", "action": "Flying"},
                    {"do": "celebrate", "who": "nobody"}, {"do": "food", "size": "tiny"},
                    {"do": "food", "size": "small", "amount": 5}, {"do": "skill", "role": "hero",
                                                                  "skills": ["Farming"], "set": 101},
                    {"do": "skill", "role": "hero", "skills": ["Juggling"], "min": 1, "max": 2}):
            self.assertTrue(t.problems_of(v6(nodes={"k": {"text": "(Hero) keeps them.", "effects": [bad]}})), bad)

    def test_new_conditions(self):
        d = v6(nodes={"p": {"text": "(Hero) and (pal) find {X.1} and {X.2}.", "children": [
            {"next": "q", "if": {"all": [{"min_population": 6}, {"special_present": "golden_child"}]}, "else": "l"},
            {"next": "k", "if": {"any": [{"min_children": 2}, {"harmable": "pal"}]}, "else": "l"}]}})
        g = cg.load(d)
        blob = cg.compile_graph(g)
        self.assertEqual(cg.decompile_graph(blob), cg.without_names(g))
        ops = {blob[struct.unpack_from("<I", blob, 60)[0] + 8 * i] for i in range(struct.unpack_from("<H", blob, 34)[0])}
        self.assertTrue({9, 10, 11, 12} <= ops)
        # Every combination of the run-time facts is walked: the "else" covers the ones that fail.
        self.assertGreater(len(cg.contexts(g)), 5)
        for bad in ({"special_present": "queen"}, {"min_population": 0}, {"harmable": "nobody"}):
            self.assertTrue(t.problems_of(v6(nodes={"p": {"text": "x", "children": [{"next": "q", "if": bad,
                                                                                          "else": "l"}]}})), bad)

    def test_requirement_if(self):
        g = cg.load(v6(requirement={"min_eligible": 2, "if": {"min_population": 8}}))
        blob = cg.compile_graph(g)
        self.assertNotEqual(struct.unpack_from("<H", blob, 42)[0], cg.NONE)
        self.assertEqual(cg.decompile_graph(blob)["requirement"], {"min_eligible": 2, "if": {"min_population": 8}})
        self.assertTrue(t.problems_of(v6(requirement={"if": {"visited": "p"}})))


class Answers(unittest.TestCase):
    def seven(self, **choice_if) -> dict:
        labels = ["One", "Two", "Three", "Four", "Five", "Six", "Seven"]
        d = v6(nodes={"q": {"type": "question", "text": "Pick one.", "choices": [
            dict({"label": lab, "next": "k" if i % 2 else "l"}, **({"if": choice_if[lab]} if lab in choice_if else {}))
            for i, lab in enumerate(labels)]}})
        return d

    def test_seven_answers_and_choice_if(self):
        self.assertEqual(t.problems_of(self.seven(), True), [])
        d = self.seven()
        d["nodes"]["q"]["choices"].append({"label": "Eight", "next": "k"})
        self.assertTrue(any("2 to 7 answers" in p for p in t.problems_of(d, True)))
        d = self.seven(Six={"game": [3, 4, 5]}, Seven={"game": [3, 4, 5]})
        g = cg.load(d, True)
        rows = cg.chances(g, 1)
        self.assertEqual(sorted(b for key in rows for _q, b in key), [0, 1, 2, 3, 4])
        rows = cg.chances(g, 3)
        self.assertEqual(sorted(b for key in rows for _q, b in key), [0, 1, 2, 3, 4, 5, 6])
        self.assertIn("G: SEVEN", cg.chances_table(g, 3))
        blob = cg.compile_graph(g)
        self.assertEqual(cg.decompile_graph(blob), cg.without_names(g))
        # At least two answers shown in every game; only static conditions.
        d = v6(nodes={"q": {"type": "question", "text": "Pick.", "choices": [
            {"label": "A", "next": "k"}, {"label": "B", "next": "l", "if": {"game": [3]}}]}})
        self.assertTrue(any("only 1 of its answers" in p for p in t.problems_of(d, True)))
        d = v6(nodes={"q": {"type": "question", "text": "Pick.", "choices": [
            {"label": "A", "next": "k"}, {"label": "B", "next": "l", "if": {"visited": "p"}}]}})
        self.assertTrue(any("uses only game, patch, role" in p for p in t.problems_of(d, True)))

    def test_room_matches_the_engine(self):
        """answer_room == story_graph.inc cg_answer_room for 2..7 answers, in every game's question popup and
        result popup (an answer's first page), read from the engine's own source:
          * CG_ANSWER_LINES, story_graph.inc:152 (from the merge of feat/97-coll-engine 2ba3bf5e);
          * the cap in cg_answer_room, story_graph.inc:1103-1112: from five answers never more than the layout's
            lines less the title it leads with (5) less 3;
          * the table itself from vvfp_multi_answer.h ma_room_for / ma_step (lines 128-145): the first answer stands
            (n - 1) x 1.25 h - 1.5 h above the game's own first (n >= 5), h = a button, 2 lines of 20 px."""
        native = (ROOT / "native" / "vvfp_story_upgrades" / "story_graph.inc").read_text(encoding="utf-8")
        m = re.search(r"static const int CG_ANSWER_LINES\[CG_MAX_ANSWERS \+ 1\] = \{([^}]*)\};", native)
        self.assertIsNotNone(m, "CG_ANSWER_LINES moved: re-read story_graph.inc")
        table = [int(x) for x in m.group(1).split(",")]
        self.assertEqual(table, [0, 0] + [cg.answer_room(n) for n in range(2, 8)])
        for line in ("int room = CG_ANSWER_LINES[n < 2 ? 2 : n];",
                     "int most = l->lines - (l->with_title ? 5 : 0) - 3;",
                     "if (n > CG_V4_ANSWERS && room > most) {",
                     "room = most > 0 ? most : 0;"):
            self.assertIn(line, native, "cg_answer_room changed: mirror it in vv_cie_graph.answer_room")
        self.assertIn("#define CG_V4_ANSWERS 4", native)
        helper = (ROOT / "native" / "shared" / "vvfp_multi_answer.h").read_text(encoding="utf-8")
        self.assertIn("return count > 4 ? h + h / 4 : h + h / 2;", helper)
        self.assertIn("return (count - 1) * ma_step(h, count) - (h + h / 2);", helper)
        h, line = 40, 20
        for n in range(5, 8):
            px = (n - 1) * (h + h // 4) - (h + h // 2)
            self.assertEqual(-(-px // line), table[n], n)

        def engine(n: int, layout) -> int:
            room = table[2 if n < 2 else n]
            most = layout.lines - (5 if layout.with_title else 0) - 3
            if n > 4 and room > most:
                room = most if most > 0 else 0
            return room

        for game in cg.GAMES.values():
            for layout in (game.question, game.result):
                for n in range(2, 8):
                    self.assertEqual(cg.answer_room(n, layout), engine(n, layout), (game.name, layout, n))
        # A New Home's question popup: 13 lines, the title's 5, three kept: room 5 from five answers.
        self.assertEqual([cg.answer_room(n, cg.GAMES[1].question) for n in range(2, 8)], [0, 3, 6, 5, 5, 5])

    def test_seven_answers_fit_without_scrolling_where_the_engine_does(self):
        # Every game: the question keeps 3 lines below its title, and its answers' pages fit.
        self.assertEqual(t.problems_of(self.seven(), False), [])
        # A New Home, four buttons (no cap: the version 4 rule) and an answer page with changes: the title (5),
        # the buttons (6) and the refusal lines (2) leave no line in its 13, so the engine cannot show it either.
        d = read(KITCHEN)
        problems = t.problems_of(d, False)
        self.assertEqual(len(problems), 1, problems)
        self.assertTrue(problems[0].startswith("A New Home: the popup of b runs off the screen"), problems)
        self.assertEqual(t.problems_of(d, True), [])

    def test_room_and_labels(self):
        self.assertEqual([cg.answer_room(n) for n in range(2, 8)], [0, 3, 6, 7, 10, 12])
        self.assertEqual(cg.answer_room(7, cg.GAMES[3].question), 8)
        self.assertEqual([cg.answer_letter(b) for b in range(8)], list("ABCDEFG") + ["8"])
        long_label = "Ask the Isolan team to agree on a few shared safety rules first."   # 64 bytes: v6 allows 95
        d = v6(nodes={"q": {"type": "question", "text": "Pick.", "choices": [
            {"label": long_label, "next": "k"}, {"label": "Leave", "next": "l"}]}})
        self.assertEqual(t.problems_of(d, True), [])
        d["nodes"]["q"]["choices"][0]["label"] = "{X}"
        self.assertTrue(any("game words only" in p for p in t.problems_of(d, True)))


class Binary(unittest.TestCase):
    def test_header_and_sections(self):
        g = cg.load(read(GARDEN), True)
        blob = cg.compile_graph(g)
        h = struct.unpack_from("<4sHHIII", blob, 0)
        self.assertEqual(h[:3], (b"CIEG", 6, 96))
        o_pool, o_item, n_pool, n_item, flags, col, zero = struct.unpack_from("<IIHHHHI", blob, 76)
        self.assertEqual((n_pool, n_item, flags, zero), (2, 11, 1, 0))
        self.assertEqual(struct.unpack_from("<HHHBB", blob, o_pool), (struct.unpack_from("<HHHBB", blob, o_pool)[0],
                                                                       0, 6, 1, 0))
        self.assertNotEqual(col, cg.NONE)
        d = cg.decompile_graph(blob)
        self.assertEqual(d["collection"]["id"], "vv3_gardening_contest")
        self.assertEqual(d, cg.without_names(g))
        # A version 6 number on an 80-byte header is refused.
        bad = bytearray(cg.compile_graph(cg.load(t.tiny())))
        struct.pack_into("<H", bad, 4, 6)
        struct.pack_into("<I", bad, 12, 0)
        struct.pack_into("<I", bad, 12, __import__("zlib").crc32(bytes(bad)))
        with self.assertRaises(cg.GraphError):
            cg.decompile_graph(bytes(bad))

    def test_inline_picks_and_words_become_pools(self):
        d = v6(games=[1, 3], words={"chief": {"3": "the Chief", "*": "the elders"}})
        d["nodes"]["k"]["text"] = "(Hero) {keeps|3:hides} them for {@chief}."
        g = cg.load(d)
        lg = cg.lower(g)
        self.assertEqual(lg["nodes"]["k"]["text"], "(Hero) {_i1} them for {@chief}.")
        self.assertEqual([it["weight"] for it in lg["pools"]["_i1"]["items"]], [1, 3])
        self.assertEqual(lg["pools"]["@chief"]["items"], [{"text": "the elders", "weight": 1, "if": {"game": [1]}},
                                                          {"text": "the Chief", "weight": 1, "if": {"game": [3]}}])
        blob = cg.compile_graph(g)
        self.assertIn(b"{_i1}", blob)
        self.assertEqual(cg.decompile_graph(blob), cg.without_names(g))
        self.assertEqual(g["nodes"]["k"]["text"], "(Hero) {1:keeps|3:hides} them for {@chief}.")

    def test_authoring_keys_are_kept_but_never_compiled(self):
        d = read(GARDEN)
        d["nodes"]["s1"]["src"] = "L3070-3071"
        d["nodes"]["s1"]["text_only_reason"] = "none"
        d["pools"]["A"]["items"][0] = {"text": "neat rows with carefully labeled plants", "src": "L3053"}
        d["grammar_fixes"] = [{"line": 1, "from": "a", "to": "b"}]
        g = cg.load(d, True)
        self.assertEqual(g["nodes"]["s1"]["src"], "L3070-3071")
        self.assertEqual(cg.compile_graph(g), cg.compile_graph(cg.load(read(GARDEN), True)))
        self.assertEqual(cg.decompile_graph(cg.compile_graph(g)), cg.without_names(g))

    def test_deterministic(self):
        a = cg.compile_graph(cg.load(read(KITCHEN), True))
        b = cg.compile_graph(cg.load(copy.deepcopy(read(KITCHEN)), True))
        self.assertEqual(a, b)


class FormatGaps(unittest.TestCase):
    """G1-G9 (the lead's collection_gaps_spec.md), as docs/event-collection/cie-v6-binary.md writes them."""

    def test_gaps_graph_passes_and_round_trips(self):
        for scrolling in (False, True):
            self.assertEqual(cg.validate(GAPS, scrolling)[1], [], scrolling)
        g = cg.load(GAPS)
        blob = cg.compile_graph(g)
        self.assertEqual(cg.decompile_graph(blob), cg.without_names(g))
        self.assertEqual(cg.compile_graph(cg.decompile_graph(blob)), blob)

    def test_g1_a_fresh_popup_after_five_buttons(self):
        d = copy.deepcopy(GAPS)
        g = cg.load(d)
        page = [p for h in cg.walk(g, cg.contexts(g, [1])[0]) for p in h.popups if p.nodes == ["a"]][0]
        self.assertEqual(page.room, 0, "after five buttons: a fresh popup, no room")
        d["nodes"]["q"]["choices"] = d["nodes"]["q"]["choices"][:3] + d["nodes"]["q"]["choices"][4:]
        # (In A New Home the shared popup leaves no line for this page without Scrolling Popups: as the engine.)
        self.assertTrue(any("A New Home: the popup of a runs off" in p for p in t.problems_of(d)))
        g = cg.load(d, True)
        page = [p for h in cg.walk(g, cg.contexts(g, [3])[0]) for p in h.popups if p.nodes == ["a"]][0]
        self.assertEqual(page.room, 6, "two to four buttons: the answer shares the question's popup")

    def test_g2_the_other_member(self):
        g = cg.load(GAPS)
        self.assertEqual(sorted(cg.harm_capable(g)), ["cook1", "cook2", "loser"])
        blob = cg.compile_graph(g)
        roles = struct.unpack_from("<I", blob, 44)[0]
        loser = struct.unpack_from("<BBBBHBBBBHBBH", blob, roles + 4 * 16)
        self.assertEqual((loser[0], loser[12]), (3, 1 << 3))          # kind 3, the alias at index 3
        bad = copy.deepcopy(GAPS)
        bad["roles"]["winner"]["of"] = ["cook1"]
        self.assertTrue(any("exactly two" in p for p in t.problems_of(bad)))

    def test_g3_distinct_from(self):
        d = copy.deepcopy(GAPS)
        d["pools"]["HATE"]["distinct_from"] = ["NOPE"]
        self.assertTrue(any("distinct_from names no pool" in p for p in t.problems_of(d)))
        g = cg.load(GAPS)
        b = binding({"judge": {"name": "", "sex": "f"}, "cook1": {"name": "Ana", "sex": "f"},
                     "cook2": {"name": "Bo", "sex": "m"}})
        for first in range(3):
            r = cg.simulate(g, 3, [0, first, 0] + [0] * 20, b, [4])
            picks = {p[0]: p[2] for p in r["picks"]}
            self.assertNotEqual(picks["LIKE"], picks["HATE"])        # the same texts: never the same one

    def test_g4_inline_picks(self):
        g = cg.load(GAPS)
        self.assertIn("a quiet morning", g["nodes"]["p"]["text"])
        lg = cg.lower(g)
        self.assertEqual([it["text"] for it in lg["pools"]["_i1"]["items"]], ["the {@chief}", "{@tribe}"])
        d = v6(nodes={"k": {"text": "{a|{b|c}}"}})
        self.assertTrue(t.problems_of(d))                               # nested picks: refused
        d = v6(nodes={"k": {"text": "{a|{X}}"}})
        self.assertTrue(t.problems_of(d))                               # a list inside a pick: refused

    def test_g5_tribe(self):
        lg = cg.lower(cg.load(GAPS))
        self.assertNotIn("@tribe", lg["pools"])
        self.assertEqual(cg.expand_v6("{@Tribe} and {@tribe}", lg, {}, tribe="kalahuna"), "Kalahuna and kalahuna")
        self.assertEqual(cg.expand_v6("{@Tribe} and {@tribe}", lg, {}), "The village and the village")
        self.assertEqual(cg.worst_v6("{@tribe}", lg, cg.GAMES[1], None), "W" * 31)
        self.assertEqual(cg.worst_v6("{@tribe}", lg, cg.GAMES[4], None), "W" * 19)
        self.assertTrue(any("built in" in p for p in t.problems_of(v6(words={"tribe": {"*": "x"}}))))

    def test_g6_g7_title_and_first_role(self):
        self.assertEqual(t.problems_of(v6(title='The "Big" Day')), [])
        self.assertTrue(t.problems_of(dict(t.tiny(), title='The "Big" Day')))    # still refused before version 6
        self.assertEqual(next(iter(cg.load(GAPS)["roles"])), "judge")

    def test_g9_and_skill_sizes(self):
        sizes = {}
        for size in ("small", "normal", "large", "huge"):
            g = cg.load(v6(nodes={"k": {"text": "(Hero) keeps them.", "effects": [
                {"do": "damage", "size": size}, {"do": "skill", "role": "hero", "skills": ["Farming"], "size": size},
                {"do": "skill", "role": "pal", "skills": ["Farming"], "size": size, "loss": True}]}}))
            e = g["nodes"]["k"]["effects"]
            sizes[size] = ((e[0]["min"], e[0]["max"]), (e[1]["min"], e[1]["max"]), (e[2]["min"], e[2]["max"]))
        self.assertEqual(sizes, {"small": ((10, 30), (5, 10), (-10, -5)), "normal": ((25, 50), (10, 20), (-20, -10)),
                                 "large": ((50, 75), (20, 40), (-40, -20)), "huge": ((75, 100), (30, 60), (-60, -30))})

    def test_the_pilots_pass_both_ways(self):
        """Track D's pilot files (data/event_collection), through their own loader, with and without Scrolling
        Popups -- Between Life and Death and The Parent's Lesson included (G1)."""
        sys.path.insert(0, str(ROOT / "scripts"))
        import collection_check as cc
        shared = {"pools": cc.shared_pools()}
        files = sorted(p for p in (ROOT / "data" / "event_collection").rglob("*.json")
                       if p.name not in ("manifest.json", "shared_pools.json"))
        self.assertGreaterEqual(len(files), 10)
        for p in files:
            g = cc.graph_for_engine(read(p))
            for scrolling in (False, True):
                with self.subTest(p.name, scrolling=scrolling):
                    self.assertEqual(cg.validate(g, scrolling, shared)[1], [])


class TitlesCapsAndNoRoles(unittest.TestCase):
    """The content round's three: VV3-5 titles by pixels, ALL-CAPS placeholders, an event with no roles."""

    OWNER_TITLES = ("The Little Things They Remember", "The Duel of the Terrible Inventors",
                    "The Trial of the Shattered Pearls", "The Magician and the Naturalist",
                    "The Village Idiot and the Impossible Invention")

    def test_titles_by_pixels(self):
        # The measure, pinned against the emulated stock dialog (tests/scrolling_popups_emulation.py: the body draw
        # VV3 0x418510 calls the centred draw 0x40A070 with the title [dialog+0x54] in the dialog's font): one line,
        # centred; these glyph extents were read from its blits in VV3, VV4 and VV5 alike.
        for game in (3, 4, 5):
            self.assertEqual([cg.title_px(game, t) for t in ("The Mysterious Footprints", self.OWNER_TITLES[0],
                                                             self.OWNER_TITLES[4], "W" * 47)],
                             [229, 298, 399, 799], game)
        self.assertEqual(cg.TITLE_BOX_PX, {3: 432, 4: 432, 5: 624})
        for title in self.OWNER_TITLES:
            d = v6(games=[3, 4, 5], title=title)
            self.assertEqual(t.problems_of(d), [], title)
        self.assertTrue(all("pixels wide" in p for p in t.problems_of(v6(games=[3, 4, 5], title="W" * 47))))
        # Versions 1-5 keep their 30 characters.
        d = t.four_doors(5)
        d["title"] = self.OWNER_TITLES[0]
        self.assertTrue(any("longer than its 30 characters" in p for p in t.problems_of(d)))

    def test_all_caps_placeholders(self):
        roles = {"subject": {"kind": "villager"}, "friend": {"kind": "villager"}}
        for token, what, role in (("NAME1", "name", "subject"), ("HIM/HER", "him/her", "subject"),
                                  ("FRIEND.HE/SHE", "he/she", "friend"), ("FRIEND", "name", "friend"),
                                  ("HIMSELF/HERSELF", "himself/herself", "subject")):
            p = cg.parse_placeholder_v6(token, roles)
            self.assertEqual((p.what, p.role, p.upper), (what, role, True), token)
        self.assertFalse(cg.parse_placeholder_v6("Name1", roles).upper)
        g = cg.lower(cg.load(CAPS, True))
        b = {"subject": cg.Binding("Ana", "f"), "friend": cg.Binding("Bo", "m")}
        self.assertEqual(cg.expand_v6("TELL (NAME1) TO STOP; (FRIEND.HE/SHE) AND (HIM/HER).", g, b),
                         "TELL ANA TO STOP; HE AND HER.")
        # The fit measures them as written (names W x the room; pronouns in capitals).
        self.assertEqual(cg.worst_v6("(HIS/HER) (NAME)", g, cg.GAMES[3], None), "HIS " + "W" * 23)
        for scrolling in (False, True):
            self.assertEqual(cg.validate(CAPS, scrolling)[1], [])
        # The fit is kept: an all-caps NAME in that label runs off the screen with the longest name, so the content
        # uses the all-caps pronoun there.
        d = copy.deepcopy(CAPS)
        d["nodes"]["q"]["choices"][0]["label"] = "TELL (NAME1) TO STOP BEFORE ANYONE IS HURT."
        self.assertTrue(any("runs off the screen" in p for p in t.problems_of(d, True)))

    def test_no_roles(self):
        for scrolling in (False, True):
            self.assertEqual(cg.validate(NO_ROLES, scrolling)[1], [])
        g = cg.load(NO_ROLES)
        blob = cg.compile_graph(g)
        self.assertEqual(struct.unpack_from("<H", blob, 26)[0], 0)              # role count 0
        self.assertEqual(cg.decompile_graph(blob), cg.without_names(g))
        for bad in ({"text": "(Name) waits."}, {"text": "Waits.", "effects": [{"do": "kill"}]},
                    {"text": "Waits.", "effects": [{"do": "mood", "role": "x", "mood": "bad"}]}):
            d = copy.deepcopy(NO_ROLES)
            d["nodes"]["b1"] = dict(bad, popup="append")
            self.assertTrue(t.problems_of(d), bad)
        d = copy.deepcopy(NO_ROLES)
        d["version"] = 5
        self.assertTrue(any("roles is missing" in p for p in t.problems_of(d)))
        # Track D's checker takes it too.
        sys.path.insert(0, str(ROOT / "scripts"))
        import collection_check as cc
        doc = dict(copy.deepcopy(NO_ROLES), collection={"id": "test_no_roles", "lines": [1, 2]})
        doc["nodes"]["b"]["children"][1]["weight"] = 1          # (the checker wants equal odds without a source)
        for check in (cc.check_safety, cc.check_engine, cc.check_chances):
            rep = cc.Report("no roles")
            check(doc, rep)
            self.assertEqual(rep.problems, [], check.__name__)
        rep = cc.Report("no roles")
        cc.check_tokens(doc, None, rep)
        self.assertEqual(rep.problems, [])


class Fit(unittest.TestCase):
    def test_fallback_is_measured_in_vv1(self):
        d = v6(games=[1, 3])
        d["nodes"]["k"]["text"] = "&" * 700
        problems = t.problems_of(d, True)
        self.assertTrue(any(p.startswith("A New Home") and "longer than 1990" in p for p in problems), problems)
        self.assertFalse(any(p.startswith("The Secret City") for p in problems))

    def test_longest_pool_item_is_measured(self):
        d = v6(pools={"X": {"distinct": True, "items": ["a", "b", "x" * 1500]}})
        d["nodes"]["p"]["text"] = "{X.1} {X.2}"
        self.assertTrue(any("longer than 1990" in p for p in t.problems_of(d, True)))


class NodeTitles(unittest.TestCase):
    """Per-node popup titles (cie-v6-binary.md 14)."""

    def test_valid_round_trip_and_record(self):
        g = cg.load(copy.deepcopy(TITLES))
        blob = cg.compile_graph(g)
        self.assertEqual(cg.decompile_graph(blob), cg.without_names(g))
        names = list(cg.lower(g)["nodes"])
        o_node = struct.unpack_from("<I", blob, 48)[0]
        for i, nid in enumerate(names):
            title = struct.unpack_from("<H", blob, o_node + 28 * i + 26)[0]
            self.assertEqual(title == cg.NONE, "title" not in g["nodes"][nid], nid)

    def test_refusals(self):
        d = copy.deepcopy(TITLES)
        d["nodes"]["b"]["title"] = "A Branch"
        self.assertTrue(any("a branch shows no text" in p for p in t.problems_of(d)))
        d = copy.deepcopy(TITLES)
        d["nodes"]["inv"]["title"] = "W" * 40
        self.assertTrue(any("node inv: its popup title is" in p and "pixels wide" in p for p in t.problems_of(d)))
        d["nodes"]["inv"]["title"] = "x" * 48
        self.assertTrue(any("longer than 47" in p for p in t.problems_of(d)))
        d["nodes"]["inv"]["title"] = "Bad (Name)"
        self.assertTrue(any("node inv: its popup title has no placeholders" in p for p in t.problems_of(d)))
        d["nodes"]["inv"]["title"] = "Semi;colon"
        self.assertTrue(any("cannot show" in p for p in t.problems_of(d)))
        old = t.four_doors(5)
        next(iter(old["nodes"].values()))["title"] = "Older"
        self.assertTrue(any("unknown fields title" in p for p in t.problems_of(old)))

    def test_simulate_titles(self):
        g = cg.load(copy.deepcopy(TITLES))
        r = cg.simulate(g, 3, [0], {"subject": cg.Binding("Ana", "f")}, [0])
        self.assertEqual(r["titles"], ["The Revolutionary Invention"] * 3 + ["The Elders Decide"])
        r = cg.simulate(g, 3, [1], {"subject": cg.Binding("Ana", "f")}, [1])
        self.assertEqual(r["titles"], ["The Revolutionary Discovery"] * 3)

    def test_the_fit_pages_with_the_widest_title(self):
        # A New Home leads each page with its title: a node's two-line title takes one more line than the event's.
        d = copy.deepcopy(TITLES)
        d["games"] = [1]
        g = cg.load(d)
        ctx = cg.contexts(g, [1])[0]
        pops = [p for h in cg.walk(g, ctx) for p in h.popups if "y" in p.nodes]
        self.assertEqual(pops[0].titles, ["The Revolutionary Invention", "The Elders Decide"])
        layout = cg.Layout(10, 14, True)
        self.assertEqual(cg.widest_title(g, ["", "Short", "Threeline Titleline Hereline"], layout, cg.GAMES[1]),
                         "Threeline Titleline Hereline")
        self.assertEqual(cg.widest_title(g, ["", "Short"], layout, cg.GAMES[1]), "The Revolution")


if __name__ == "__main__":
    if "--write-vectors" in sys.argv:
        write_vectors()
        print(VECTORS)
    else:
        unittest.main()
