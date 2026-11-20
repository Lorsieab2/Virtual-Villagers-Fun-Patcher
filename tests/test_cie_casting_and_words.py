"""Casting and words that follow the villager (the owner, 2026-11-16; docs/event-collection/cie-v6-binary.md 37).

* A role may PREFER a special villager ("prefer": "tribal_chief" / "golden_child"): The Secret City's robed Tribal
  Chief (A New Home's Golden Child) is cast when they may take the role, else any villager the role takes.
* The chief's title words: one title a run -- the Chief, the leader, the elder, the headman / headwoman (the cast
  chief's presentation) or the council head -- the same on every page (linked pools); the real Tribal Chief cast in
  the chief role is always the author's VV3 word.
* A carrier's words (and a chief's) follow Gender Presentation, else the recorded sex; a sex change sets a role's
  words again for the pages after it; the Golden Child's words follow his (or her) recorded sex.
* The collection: the chief events run in every game, the Golden Child's words and the carriers' are placeholders.

The engine half runs the test build of "VVFP Story Upgrades.dll" beside each game's executable in the emulator.
"""
from __future__ import annotations

import copy
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import collection_check as cc  # noqa: E402
import collection_lib as lib  # noqa: E402
import vv_cie_graph as cg  # noqa: E402
from test_story_custom_island_event import HAVE_EMULATOR, emulated, have_stock  # noqa: E402

if HAVE_EMULATOR:
    from test_story_cie_graph_runtime_v6 import V6, compiled, norm

GAME_IDS = ("vv1", "vv2", "vv3", "vv4", "vv5")
DATA = ROOT / "data" / "event_collection"
TITLES = {"chief", "leader", "elder", "headman", "headwoman", "council head"}

CHIEF_GRAPH = {
    "format": "vvfp-cie-graph", "version": 6, "title": "The Long Council", "games": [1, 2, 3, 4, 5],
    "roles": {"chief": {"kind": "villager", "min_age": 14, "prefer": "tribal_chief"}},
    "start": "p",
    "nodes": {"p": {"text": "(Chief) calls the village together. {@Chief} speaks first.", "children": [{"next": "q"}]},
              "q": {"type": "popup", "text": "Everyone listens to {@chief} until sunset.", "new_page": True}},
    "words": {"Chief": {"3": "The Chief", "*": "The leader"}, "chief": {"3": "the Chief", "*": "the leader"}},
}
CARRIER_GRAPH = {
    "format": "vvfp-cie-graph", "version": 6, "title": "The Night Feed", "games": [1, 2, 3, 4, 5],
    "roles": {"parent": {"kind": "villager", "min_age": 18, "special": "nursing_parent"}},
    "start": "p",
    "nodes": {"p": {"text": "(Parent), a nursing (parent.mother/father), rocks (parent.his/her) baby. "
                            "(parent.He/She) hums."}},
}
SEX_GRAPH = {
    "format": "vvfp-cie-graph", "version": 6, "title": "The Person They Have Always Been", "games": [1, 2, 3, 4, 5],
    "roles": {"subject": {"kind": "villager", "min_age": 25}},
    "start": "p",
    "nodes": {"p": {"text": "(Name) shares a private truth; (subject.he/she) is glad.",
                    "effects": [{"do": "sex_change", "role": "subject"}], "children": [{"next": "q"}]},
              "q": {"type": "popup", "text": "Later, (subject.he/she) laughs with friends.", "new_page": True}},
}
GOLDEN_GRAPH = {
    "format": "vvfp-cie-graph", "version": 6, "title": "The Little Healer", "games": [1],
    "roles": {"child": {"kind": "villager", "min_age": 0, "special": "golden_child"}},
    "start": "p",
    "nodes": {"p": {"text": "The Golden Child hums. (child.He/She) smiles, and the (child.boy/girl) waves."}},
}


def title_of(text: str) -> str:
    """The chief's title in a page's words ("The council head speaks" -> "council head")."""
    m = re.search(r"\b[Tt]he (council head|chief|leader|elder|headman|headwoman)\b", text, re.I)
    return m.group(1).lower() if m else ""


class Compiler(unittest.TestCase):
    """The patcher's side: normalize, lower, compile, decompile, simulate."""

    def test_prefer_round_trips_and_is_checked(self):
        g = cg.load(copy.deepcopy(CHIEF_GRAPH))
        self.assertEqual(g["roles"]["chief"]["prefer"], "tribal_chief")
        back = cg.decompile_graph(cg.compile_graph(g))
        self.assertEqual(back["roles"], cg.without_names(g)["roles"])
        self.assertEqual(back["words"], g["words"])
        bad = copy.deepcopy(CHIEF_GRAPH)
        bad["roles"]["chief"]["prefer"] = "nursing_parent"
        self.assertTrue(any("prefer is" in p for p in cg.validate(bad)[1]))
        both = copy.deepcopy(CHIEF_GRAPH)
        both["games"] = [3]
        both["words"] = {k: {"3": v["3"]} for k, v in both["words"].items()}
        both["roles"]["chief"]["special"] = "tribal_chief"
        self.assertTrue(any("special or prefer" in p for p in cg.validate(both)[1]))

    def test_the_titles_are_linked_pools_with_the_authors_words_first(self):
        lg = cg.lower(cg.load(copy.deepcopy(CHIEF_GRAPH)))
        for word in ("@Chief", "@chief"):
            pool = lg["pools"][word]
            self.assertTrue(pool["linked"])
            texts = [it["text"] for it in pool["items"]]
            self.assertEqual([it["if"] for it in pool["items"][:2]], [{"game": [1, 2, 4, 5]}, {"game": [3]}])
            self.assertIn("(chief.headman/headwoman)", " ".join(texts).lower())
            for it in pool["items"][2:]:
                self.assertIn({"not": {"is_special": "chief"}}, it["if"]["all"])
        self.assertEqual(len(lg["pools"]["@Chief"]["items"]), len(lg["pools"]["@chief"]["items"]))
        # an article before a chief word leaves "elder" out (no "a elder")
        a = copy.deepcopy(CHIEF_GRAPH)
        a["nodes"]["q"]["text"] = "Everyone listens to a {@chief} until sunset."
        texts = " ".join(it["text"] for it in cg.lower(cg.load(a))["pools"]["@chief"]["items"])
        self.assertNotIn("elder", texts)
        self.assertIn("elder", " ".join(it["text"] for it in lg["pools"]["@chief"]["items"]))

    def test_one_title_a_run_in_every_game(self):
        g = cg.load(copy.deepcopy(CHIEF_GRAPH))
        for game in (1, 2, 3, 4, 5):
            seen = set()
            for roll in range(12):
                for real in (False, True):
                    facts = frozenset({"is_special:chief"}) if real else frozenset()
                    out = cg.simulate(g, game, [roll] * 8, {"chief": cg.Binding("Ana", "f")}, facts=facts)
                    a, b = (title_of(t) for t in out["popups"])
                    self.assertEqual(a, b, out["popups"])
                    self.assertIn(a, TITLES)
                    if real:
                        self.assertEqual(a, "chief" if game == 3 else a)
                        if game == 3:
                            self.assertIn("The Chief speaks", out["popups"][0])
                    seen.add(a)
            self.assertEqual(seen, TITLES - {"headman"}, game)     # Ana: "headwoman"

    def test_the_headman_word_follows_the_binding(self):
        self.assertEqual(cg.PRONOUNS_V6["headman/headwoman"], ("headman", "headwoman"))
        g = cg.load(copy.deepcopy(CHIEF_GRAPH))
        lg = cg.lower(g)
        k = next(i for i, it in enumerate(lg["pools"]["@Chief"]["items"]) if "headman" in it["text"].lower()
                 and it["if"]["all"][0] == {"game": [1, 2, 4, 5]})
        eligible = [i for i, it in enumerate(lg["pools"]["@Chief"]["items"])
                    if 1 in (it["if"].get("game") or it["if"]["all"][0]["game"])]
        roll = eligible.index(k)
        for sex, word in (("m", "headman"), ("f", "headwoman")):
            out = cg.simulate(g, 1, [roll] * 8, {"chief": cg.Binding("Kai", sex)})
            self.assertIn(f"The {word} speaks first", out["popups"][0])

    def test_is_special_compiles_as_op_18(self):
        self.assertEqual(cg.COND_CODES["is_special"], 18)
        g = copy.deepcopy(CHIEF_GRAPH)
        g["nodes"]["p"]["variants"] = [{"if": {"is_special": "chief"}, "text": "The robed one rises."}]
        back = cg.decompile_graph(cg.compile_graph(cg.load(g)))
        self.assertEqual(back["nodes"]["p"]["variants"][0]["if"], {"is_special": "chief"})


class CollectionCheck(unittest.TestCase):
    """The fidelity check reads a pronoun placeholder as either of its own words written bare in the source."""

    def test_bare_words_and_their_mutations(self):
        rx = cc.text_regex("(child.He/She) smiles at (child.him/her).", {})
        self.assertRegex("He smiles at him.", rx)
        self.assertRegex("(He/she) smiles at (him/her).", rx)
        self.assertNotRegex("He smiles at them.", rx)                 # mutation: a word not of the pair
        self.assertNotRegex("He smiles at hims.", rx)
        rx = cc.text_regex("a nursing (mother.mother/father).", {})
        self.assertRegex("a nursing mother.", rx)
        self.assertNotRegex("a nursing aunt.", rx)
        self.assertEqual(cc._ph_blind("Ask (mother.Him/Her) Now"), cc._ph_blind("Ask Her Now"))

    def test_carrier_text(self):
        self.assertEqual(lib.carrier_text("(mother), a nursing mother, feeds her baby; she gives her a cup and "
                                          "rests herself. Ask Her.", "mother"),
                         "(mother), a nursing (mother.mother/father), feeds (mother.his/her) baby; (mother.he/she) "
                         "gives (mother.him/her) a cup and rests (mother.himself/herself). Ask (mother.Him/Her).")
        doc = {"roles": {"m": {"kind": "villager", "special": "nursing_parent", "sex": "female"}},
               "nodes": {"a": {"text": "She sings."}}}
        lib.carrier_words(doc)
        self.assertNotIn("sex", doc["roles"]["m"])
        self.assertEqual(doc["nodes"]["a"]["text"], "(m.He/She) sings.")


def collection_docs():
    for p in sorted(DATA.rglob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if isinstance(d, dict) and isinstance(d.get("roles"), dict):
            yield p, d


def texts_of(d: dict):
    for n in d["nodes"].values():
        yield n.get("text") or ""
        for v in n.get("variants") or []:
            yield v.get("text") or ""
        for c in n.get("choices") or []:
            yield c.get("label") or ""
    for pool in (d.get("pools") or {}).values():
        for it in pool["items"]:
            yield it["text"] if isinstance(it, dict) else it


class Collection(unittest.TestCase):
    """The owner's rules on the collection's files."""

    def test_the_golden_childs_words_are_placeholders(self):
        bare = re.compile(r"(?<![A-Za-z(./])(?:he|him|his|himself|boy)(?![A-Za-z/)])", re.I)
        n = 0
        for p, d in collection_docs():
            if any(r.get("special") == "golden_child" for r in d["roles"].values()):
                n += 1
                self.assertEqual(d["games"], [1], p.name)
                for t in texts_of(d):
                    self.assertIsNone(bare.search(t), f"{p.name}: {t[:80]}")
        self.assertGreaterEqual(n, 27)

    def test_the_golden_childs_lines_need_him_there(self):
        for name in ("v20/all_v20_r1_should_not.json", "v20/all_v20_r4_relic.json"):
            d = json.loads((DATA / name).read_text(encoding="utf-8"))
            for n in d["nodes"].values():
                for v in n.get("variants") or []:
                    if "Golden Child" in v.get("text", ""):
                        self.assertEqual(v["if"], {"all": [{"game": [1]}, {"special_present": "golden_child"}]})

    def test_carriers_take_no_sex(self):
        for p, d in collection_docs():
            for rid, r in d["roles"].items():
                if r.get("special") == "nursing_parent" and r.get("sex") == "female":
                    self.fail(f"{p.name}: {rid} is written female (only villagers born female are cast anyway)")

    def test_the_chief_events_run_in_every_game_and_prefer_the_tribal_chief(self):
        for name in ("exclusive/vv3_chiefs_impossible", "exclusive/vv3_child_who_claimed",
                     "v6/vv3_chiefs_monumental", "v9/vv3_chief_and_pearl"):
            d = json.loads((DATA / f"{name}.json").read_text(encoding="utf-8"))
            self.assertEqual(d["games"], [1, 2, 3, 4, 5], name)
            self.assertEqual(d["roles"]["chief"].get("prefer"), "tribal_chief", name)
            self.assertNotIn("special", d["roles"]["chief"])
            for t in texts_of(d):
                self.assertNotRegex(re.sub(r"\{[^{}]*\}", "", t), r"\bChief\b|Secret City", name)
        d = json.loads((DATA / "v17/vv3_v17_sculpture.json").read_text(encoding="utf-8"))
        self.assertEqual(d["roles"]["chief"].get("prefer"), "tribal_chief")


@emulated
class Engine(unittest.TestCase):
    """The engine casts, draws and words as the patcher does, in all five games."""

    def run_graph(self, game, people, graph, rolls, mark=None):
        r = V6(game, people)
        if mark:
            mark(r)
        r.rolls(rolls)
        self.assertIsNone(r.queue6(compiled(graph)))
        shown = r.walk_through()
        return r, [norm(t) for _k, t, _l in shown]

    def test_the_tribal_chief_is_preferred_and_called_the_chief(self):
        people = [(0, "f", 30, "Ann", 0, False), (1, "m", 40, "Bob", 0, False), (2, "f", 35, "Cy", 0, False)]
        for game in GAME_IDS:
            if not have_stock(game):
                continue
            for chief in ((False, True) if game == "vv3" else (False,)):
                for roll in (0, 2, 5):
                    with self.subTest(game=game, chief=chief, roll=roll):
                        def mark(r):
                            if chief:
                                r.p.write(r.v.record(1) + 0xE80, b"\1")     # Bob: The Secret City's Tribal Chief
                        r, pages = self.run_graph(game, people, CHIEF_GRAPH, [roll] * 40, mark)
                        self.assertEqual(r.state()["records"][0], 1 if chief else roll % 3, pages)
                        a, b = title_of(pages[0]), title_of(pages[1])
                        self.assertEqual(a, b, pages)                   # one title on every page
                        self.assertIn(a, TITLES)
                        if chief:
                            self.assertIn("The Chief speaks first", pages[0])
                            self.assertIn("listens to the Chief", pages[1])

    def test_the_title_matches_the_patchers_draw(self):
        for game in GAME_IDS:
            if not have_stock(game):
                continue
            g = cg.load(copy.deepcopy(CHIEF_GRAPH))
            for roll in range(6):
                with self.subTest(game=game, roll=roll):
                    r, pages = self.run_graph(game, [(0, "m", 30, "Kai", 0, False)], CHIEF_GRAPH, [roll] * 40)
                    want = cg.simulate(g, int(game[2]), [roll] * 8, {"chief": cg.Binding("Kai", "m")})
                    for page, popup in zip(pages, want["popups"], strict=True):
                        self.assertTrue(page.endswith(norm(popup)), (page, popup))   # (A New Home, The Lost Children: the title first)

    def test_a_carriers_words_follow_gender_presentation(self):
        for game in GAME_IDS:
            if not have_stock(game):
                continue
            for presented, words in ((0, ("She hums", "nursing mother", "her baby")),
                                     (1, ("He hums", "nursing father", "his baby"))):
                with self.subTest(game=game, presented=presented):
                    r, pages = self.run_graph(game, [(0, "f", 30, "Ann", 0, True)], CARRIER_GRAPH, [0] * 40,
                                              lambda r: r.p.export("VvfpStoryProbeGraphPresented", presented))
                    for w in words:
                        self.assertIn(w, pages[0])

    def test_a_sex_change_sets_the_words_of_the_pages_after_it(self):
        for game in GAME_IDS:
            if not have_stock(game):
                continue
            for sex, before, after in (("f", "she is glad", "he laughs"), ("m", "he is glad", "she laughs")):
                with self.subTest(game=game, sex=sex):
                    r, pages = self.run_graph(game, [(0, sex, 30, "Ari", 0, False)], SEX_GRAPH, [0] * 40)
                    # the page that makes the change keeps the words it was written with; the pages after follow it
                    self.assertRegex(pages[0], rf"\b{before}\b")
                    self.assertRegex(pages[1], rf"(?<![A-Za-z]){after}\b")

    def test_two_word_changes_on_one_page_keep_its_first_words(self):
        # A sex_change then a presentation on the same page: the page making them still reads with the words it
        # began with, never the in-between ones (Codex, #787).
        graph = copy.deepcopy(SEX_GRAPH)
        graph["nodes"]["p"]["effects"].append({"do": "presentation", "role": "subject", "on": True})
        for game in GAME_IDS:
            if not have_stock(game):
                continue
            for sex, before in (("f", "she is glad"), ("m", "he is glad")):
                with self.subTest(game=game, sex=sex):
                    # Gender Presentation installed (the test build's stand-in), so the presentation effect applies
                    r, pages = self.run_graph(game, [(0, sex, 30, "Ari", 0, False)], graph, [0] * 40,
                                              lambda r: r.p.export("VvfpStoryProbeGraphPresentation", 1, 0, 0))
                    self.assertGreaterEqual(r.p.export("VvfpStoryProbeGraphPresentation", -2, 0, 0), 1,
                                            "the presentation effect ran")
                    self.assertRegex(pages[0], rf"(?<![A-Za-z]){before}\b")

    def test_a_loaded_run_never_takes_another_runs_words(self):
        """Codex on #787: a run that changed a role's words leaves no trace on the next run loaded in the same
        process (another save slot's, or the same village's after a reload)."""
        wave = {"format": "vvfp-cie-graph", "version": 6, "title": "A Wave", "games": [1, 2, 3, 4, 5],
                "roles": {"subject": {"kind": "villager", "min_age": 25}},
                "start": "p", "nodes": {"p": {"text": "(Name) looks up; (subject.he/she) waves."}}}
        for game in GAME_IDS:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                # 1) a run that changes Ari's sex on its first page, played to the end in this process
                r = V6(game, [(0, "f", 30, "Ari", 0, False)])
                r.rolls([0] * 40)
                r.p.export("VvfpStoryProbeQueueSession", 0, 0, 1, 0)
                self.assertIsNone(r.queue6(compiled(SEX_GRAPH)))
                r.walk_through()
                self.assertEqual(r.state()["female"][0], 0, "Ari is now male")
                self.assertGreater(r.p.export("VvfpStoryProbeGraphLateAt", 0), 0, "the change was noted")
                # 2) another run, queued for the same (now male) Ari in a fresh process, saved to its file
                q = V6(game, [(0, "m", 30, "Ari", 0, False)])
                q.rolls([0] * 40)
                q.p.export("VvfpStoryProbeQueueSession", 0, 0, 1, 0)
                self.assertIsNone(q.queue6(compiled(wave)))
                q.tick()
                file = q.graph_file()
                # 3) that run loaded into the first process: its page reads with his words, not the old run's
                r.p.export("VvfpStoryProbeQueueSession", 0, 0, r.p.tick + 10_000, 0)
                buf = r.p.alloc(len(file) + 16)
                r.p.write(buf, file)
                r.p.export("VvfpStoryProbeGraphSession", buf, len(file))
                r.tick()
                self.assertEqual(r.p.export("VvfpStoryProbeGraphLateAt", 0), 0,
                                 "a loaded run starts with no other run's word-change notes")
                pages = [norm(t) for _k, t, _l in r.walk_through()]
                self.assertTrue(pages, "the loaded run is shown")
                self.assertRegex(pages[0], r"(?<![A-Za-z])he waves\b")

    def test_a_quit_before_the_save_reads_the_page_again_with_its_first_words(self):
        """Codex on #787: the page that changes the sex is shown, the player quits without saving; the run comes
        back at that page against the older save and reads it with the words it first had."""
        from test_story_custom_island_event import TEXT_BUF
        for game in GAME_IDS:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                people = [(0, "f", 30, "Ari", 0, False)]
                r = V6(game, people)
                r.rolls([0] * 40)
                r.p.export("VvfpStoryProbeQueueSession", 0, 0, 1, 0)
                self.assertIsNone(r.queue6(compiled(SEX_GRAPH)))
                bought = r.p.tick
                r.p.tick += 1000                                 # the page is shown after the purchase
                r.p.export("VvfpStoryProbeSetTick", r.p.tick)
                if not r.state()["armed"]:
                    assert r.p.export("VvfpStoryProbeGraphArmNext", r.n) == 1
                r.p.write(TEXT_BUF, b"\0")
                assert r.p.export("VvfpStoryProbeDeliver", r.n, TEXT_BUF, 9000) == 1
                first = norm(r.p.cstring(TEXT_BUF, 9000))
                self.assertRegex(first, r"\bshe is glad\b")
                self.assertEqual(r.state()["female"][0], 0, "the change is made: his words now")
                r.tick()
                file = r.graph_file()
                again = V6(game, people)                     # the older save: Ari as she was
                again.rolls([0] * 40)
                again.p.export("VvfpStoryProbeQueueSession", 0, 0, bought + 500, 0)    # saved before the page
                buf = again.p.alloc(len(file) + 16)
                again.p.write(buf, file)
                again.p.export("VvfpStoryProbeGraphSession", buf, len(file))
                again.tick()
                self.assertEqual(again.state()["female"][0], 1, "the words as the page first read them")
                self.assertRegex(norm(again.displays()[0]), r"\bshe is glad\b")
                pages = [norm(t) for _k, t, _l in again.walk_through()]
                self.assertRegex(pages[0], r"\bshe is glad\b")
                self.assertRegex(pages[-1], r"(?<![A-Za-z])he laughs\b")
    def test_the_golden_childs_words_follow_the_recorded_sex(self):
        if not have_stock("vv1"):
            self.skipTest("A New Home's executable")
        for sex, words in (("m", ("He smiles", "the boy waves")), ("f", ("She smiles", "the girl waves"))):
            with self.subTest(sex=sex):
                def mark(r):
                    r.p.put32(r.v.record(1) + 0x36C, 0xC7)              # Lulu: the Golden Child's family
                r, pages = self.run_graph("vv1", [(0, "m", 30, "Kai", 0, False), (1, sex, 5, "Lulu", 0, False)],
                                          GOLDEN_GRAPH, [0] * 40, mark)
                self.assertEqual(r.state()["records"][0], 1)
                for w in words:
                    self.assertIn(w, pages[0])


if __name__ == "__main__":
    unittest.main()
