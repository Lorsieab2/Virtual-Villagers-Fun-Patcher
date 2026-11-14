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
    ]


def run_case(case: dict) -> dict:
    g = cg.load(case["graph"], True)
    facts = None if case["facts"] is None else frozenset(case["facts"])
    r = cg.simulate(g, case["game"], case["rolls"], binding(case["bindings"]), case["answers"],
                    facts=facts, unicode=case["unicode"])
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
        self.assertTrue(any("names no pool" in p for p in t.problems_of(v6(nodes={"k": {"text": "{Y}"}}))))
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

    def test_room_and_labels(self):
        self.assertEqual([cg.answer_room(n) for n in range(2, 8)], [0, 3, 6, 7, 9, 12])
        self.assertEqual(cg.answer_room(7, 11), 8)
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


if __name__ == "__main__":
    if "--write-vectors" in sys.argv:
        write_vectors()
        print(VECTORS)
    else:
        unittest.main()
