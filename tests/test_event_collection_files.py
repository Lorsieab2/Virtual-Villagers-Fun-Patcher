"""Isola Grand Event Collection: the frozen source, the manifest and every collection file (design E4 a-h).

Pinned here:
  * the source in the repo is the frozen v26 copy (SHA-256 in data/event_collection/SOURCE.sha256), line count fixed;
  * data/event_collection/manifest.json is current (scripts/collection_manifest.py --check), covers every
    non-blank line of the source with no overlap, and lists its disagreements with the inventories;
  * every data/event_collection/<section>/<id>.json passes scripts/collection_check.py (a SCHEMA and g ROUND are
    SKIPPED, never passed, until src/vv_cie_graph.py reads version 6);
  * each check refuses what it should: a changed word, a dropped bank item, an unconsumed source line, an unlisted
    grammar fix, an unprefixed pronoun, "Chief" outside VV3, a missing effect, unequal weights, a harmed special
    villager, an unreachable node;
  * grammar fixes used by any file are in docs/event-collection/grammar-fixes.md.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import collection_check as cc  # noqa: E402
import collection_lib as lib  # noqa: E402
import collection_manifest as cm  # noqa: E402

GARDENING = ROOT / "data" / "event_collection" / "v6" / "vv3_gardening_contest.json"


def check_doc(doc: dict, name: str = "vv3_gardening_contest", section: str = "v6") -> cc.Report:
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / section / f"{name}.json"
        p.parent.mkdir()
        p.write_text(cc.canonical(doc), encoding="utf-8", newline="\n")
        return cc.check_file(p)


def problems(rep: cc.Report, check: str) -> list[str]:
    return [p for p in rep.problems if p.startswith(check)]


class FrozenSource(unittest.TestCase):
    def test_sha256_matches_the_record(self):
        self.assertEqual(lib.recorded_sha256(),
                         "f5abb8bf95f7345eda4f7acf676e58c536841c7767322348aad8134cdc96e567")
        self.assertEqual(lib.source_sha256(), lib.recorded_sha256(),
                         "the frozen source changed (or was checked out with CRLF: see .gitattributes)")

    def test_record_names_the_source(self):
        rel = lib.SOURCE_HASH_FILE.read_text(encoding="ascii").split(None, 1)[1].strip()
        self.assertEqual(ROOT / rel, lib.SOURCE)

    def test_line_count_is_stable(self):
        raw = lib.SOURCE.read_bytes()
        self.assertNotIn(b"\r", raw)
        self.assertEqual(len(lib.source_lines()), lib.SOURCE_LINES)


class Manifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(lib.MANIFEST.read_text(encoding="utf-8"))

    def test_manifest_is_current(self):
        self.assertEqual(lib.MANIFEST.read_text(encoding="utf-8"), cm.dumps(cm.build()),
                         "run python scripts/collection_manifest.py")

    def test_every_line_belongs_to_one_row(self):
        self.assertEqual(self.data["uncovered_lines"], [])
        self.assertEqual(self.data["overlaps"], [])

    def test_counts(self):
        c = self.data["counts"]
        # 22 + 29 + 124 events, 4 add-ons (two Cooking Contest add-ons, V13-A, V13-B): the source has 34 V17
        # contests where inventory part 3 counted 33 (listed in inventory_disagreements).
        self.assertEqual(c["events"], 175)
        self.assertEqual(c["addons"], 4)
        self.assertEqual(c["series"], {"v14_golden_child": 25, "v17_contests": 34, "v18_trials": 12,
                                       "v20_crises": 12})
        self.assertTrue(any("V17-E has 7 contests" in d["what"] for d in self.data["inventory_disagreements"]))

    def test_rows_are_verified_against_the_source(self):
        for r in self.data["rows"]:
            self.assertEqual(r["source_check"]["boundary"], [], r["id"])
            self.assertNotEqual(r["source_check"]["title_found"], False, r["id"])
            if r["kind"] in ("event", "addon"):
                self.assertEqual(r["source_check"]["choices"], "verified", r["id"])
        self.assertEqual(self.data["disagreements"], [])

    def test_ids_unique_and_credit_verbatim(self):
        ids = [r["id"] for r in self.data["rows"]]
        self.assertEqual(len(ids), len(set(ids)))
        for r in self.data["rows"]:
            text = "\n".join(lib.line(n) for spec in r["credit"]["lines"] for n in lib.src_lines(spec))
            self.assertEqual(r["credit"]["text"], text, r["id"])

    def test_known_counts(self):
        rows = {r["id"]: r for r in self.data["rows"]}
        self.assertEqual(rows["vv3_gardening_contest"]["pools"], {"A": 6, "(1)": 4, "(2)": 4, "(3)": 5})
        self.assertEqual(rows["vv2_cooking_contest"]["pools"]["Q"], 27)
        self.assertEqual(rows["vv1_child_of_legend"]["pools"]["(4)"], 11)
        self.assertEqual(rows["vv5_meaning_of_faith"]["choices"], 6)
        self.assertEqual(rows["all_v20_between_life_and_death"]["choices"], 7)
        self.assertEqual(rows["all_v22_4_parents_lesson"]["choices"], 7)


# Format gaps Track A / B must close before Phase 2 (each pinned so the test flips when the gap closes): a file listed
# here may fail ONLY with problems matching its pattern.
#   GAP-FIT7: an answer's first page is shown in the question's popup, which keeps the room of 5-7 buttons; without
#   Scrolling Popups that leaves too few lines for an outcome sentence (design R2, B7.3).
#   GAP-LABEL-NAME: a button label that holds a villager's name in capitals ("TELL (NAME1) TO STOP ...") is wider than
#   the screen with the longest names, and the format has no all-caps name or pronoun form (lead/owner decision).
KNOWN_GAPS: dict[str, str] = {   # G1 (a fresh popup after five to seven buttons) closed both former gaps
    # The two GAP-LABEL-NAME pins are closed by the engine's label fallback (decision 14).
    # Decision 3 (review r1 M6): one sentence after a four-button question that does not fit the answer page in
    # VV1 without Scrolling Popups; a sentence is never split and a heading never stands alone.
    "all_v20_r1_should_not_exist.json": r"^a SCHEMA: A New Home: the popup of (a3|d2) runs off the screen without "
                                        r"scrolling: a sentence is taller than the popup",
}


class CollectionFiles(unittest.TestCase):
    def test_every_file_passes(self):
        import re
        files = cc.collection_files()
        self.assertGreaterEqual(len(files), 10)
        rows = cc.manifest_rows()
        for p in files:
            with self.subTest(file=p.name):
                rep = cc.check_file(p, rows)
                gap = KNOWN_GAPS.get(p.name)
                if gap:
                    self.assertTrue(rep.problems, f"{p.name}: the gap is closed; remove it from KNOWN_GAPS")
                    self.assertEqual([x for x in rep.problems if not re.match(gap, x)], [])
                else:
                    self.assertEqual(rep.problems, [])
                if cc.engine() is None:
                    self.assertTrue(rep.skipped, "a and g must say SKIPPED while the v6 format is missing")

    def test_cli_runs(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "collection_check.py")], capture_output=True,
                           text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 1 if KNOWN_GAPS else 0, r.stdout + r.stderr)
        self.assertIn("files pass", r.stdout)

    def test_shared_pools(self):
        self.assertEqual(cc.check_shared_pools(), [])

    def test_every_listed_grammar_fix_is_on_its_line(self):
        fixes = cc.grammar_doc_fixes()
        self.assertGreaterEqual(len(fixes), 30)
        for n, before, after in fixes:
            self.assertIn(before, lib.normalize_source_text(lib.line(n)), f"L{n}")
            self.assertNotEqual(before, after)

    def test_grammar_fixes_used_are_listed(self):
        listed = cc.grammar_doc_fixes()
        for p in cc.collection_files():
            doc = json.loads(p.read_text(encoding="utf-8"))
            for f in doc.get("grammar_fixes", []):
                (n,) = lib.src_lines(f["src"])
                self.assertIn((n, f["before"], f["after"]), listed, p.name)

    def test_authoring_keys_never_reach_the_engine(self):
        for p in cc.collection_files():
            g = cc.graph_for_engine(json.loads(p.read_text(encoding="utf-8")))
            blob = json.dumps(g)
            for key in ('"src"', '"text_only"', '"rarity"', '"ledger"', '"title_src"',
                        '"inline_sets"'):
                self.assertNotIn(key, blob, p.name)
            for part in list(g["nodes"].values()) + list(g.get("pools", {}).values()):
                self.assertNotIn("set", part, p.name)   # a bank label ("set" on an effect is skill_set)


class ChecksRefuse(unittest.TestCase):
    """Each check bites: mutate the passing Gardening Contest and expect that check's problem."""

    @classmethod
    def setUpClass(cls):
        cls.base = json.loads(GARDENING.read_text(encoding="utf-8"))

    def doc(self):
        return copy.deepcopy(self.base)

    def test_base_passes(self):
        self.assertEqual(check_doc(self.doc()).problems, [])

    def test_changed_word(self):
        d = self.doc()
        d["nodes"]["s2"]["text"] = d["nodes"]["s2"]["text"].replace("curved path", "winding path")
        self.assertTrue(problems(check_doc(d), "b FIDELITY"))

    def test_added_word(self):
        d = self.doc()
        d["pools"]["A"]["items"][0]["text"] += " and bees"
        self.assertTrue(problems(check_doc(d), "b FIDELITY"))

    def test_dropped_word_is_unconsumed(self):
        d = self.doc()
        d["nodes"]["s4"]["text"] = d["nodes"]["s4"]["text"].replace(" They simplify it rather than overpromise.", "")
        rep = check_doc(d)
        self.assertTrue(any("L3077" in p for p in problems(rep, "c COVERAGE")), rep.problems)

    def test_dropped_item_changes_the_bank_size(self):
        d = self.doc()
        del d["pools"]["A"]["items"][5]
        rep = check_doc(d)
        self.assertTrue(problems(rep, "d TOKENS"))
        self.assertTrue(problems(rep, "c COVERAGE"))

    def test_unconsumed_line(self):
        d = self.doc()
        d["collection"]["ledger"] = [e for e in d["collection"]["ledger"] if e["src"] != "L3046"]
        self.assertTrue(any("L3046" in p for p in problems(check_doc(d), "c COVERAGE")))

    def test_unlisted_grammar_fix(self):
        d = self.doc()
        d["grammar_fixes"] = [{"src": "L3072", "before": "path's", "after": "paths'"}]
        d["nodes"]["s2"]["text"] = d["nodes"]["s2"]["text"].replace("path's", "paths'")
        self.assertTrue(any("grammar-fixes.md" in p for p in problems(check_doc(d), "b FIDELITY")))

    def test_unprefixed_pronoun(self):
        d = self.doc()
        d["pools"]["END"]["items"][4]["text"] = "(he/she) agrees"
        self.assertTrue(any("role-prefixed" in p for p in problems(check_doc(d), "d TOKENS")))

    def test_chief_outside_vv3(self):
        d = self.doc()
        d["games"] = [3, 4]
        d["nodes"]["s2"]["text"] = "the Chief suggests"
        self.assertTrue(any("Chief" in p for p in problems(check_doc(d), "d TOKENS")))

    def test_gloriously_offensive(self):
        d = self.doc()
        d["nodes"]["s3"]["text"] = "GLORIOUSLY OFFENSIVE"
        self.assertTrue(any("GLORIOUSLY" in p for p in problems(check_doc(d), "d TOKENS")))

    def test_missing_effect(self):
        d = self.doc()
        d["nodes"]["s1"]["effects"] = []
        self.assertTrue(any("experience" in p for p in problems(check_doc(d), "e EFFECTS")))

    def test_food_needs_a_size(self):
        d = self.doc()
        d["nodes"]["p2"]["effects"] = [{"do": "food", "amount": 50, "scaled": True}]
        self.assertTrue(problems(check_doc(d), "e EFFECTS"))

    def test_skill_amount_off_table(self):
        d = self.doc()
        d["nodes"]["s1"]["effects"][0]["max"] = 25
        self.assertTrue(problems(check_doc(d), "e EFFECTS"))

    def test_unequal_weights_without_odds(self):
        d = self.doc()
        d["nodes"]["shared"]["children"][0]["weight"] = 3
        self.assertTrue(problems(check_doc(d), "h CHANCES"))

    def test_rarity_weights(self):
        d = self.doc()
        kids = d["nodes"]["shared"]["children"]
        for k in kids:
            k["weight"] = 20
        kids[3]["rarity"], kids[3]["weight"] = "rare", 5
        self.assertEqual(problems(check_doc(d), "h CHANCES"), [])
        kids[3]["weight"] = 4
        self.assertTrue(problems(check_doc(d), "h CHANCES"))

    def test_unreachable_node(self):
        d = self.doc()
        d["nodes"]["orphan"] = {"text": "{END}"}
        self.assertTrue(problems(check_doc(d), "h CHANCES"))

    def test_harmed_special_role(self):
        d = self.doc()
        d["roles"]["gardener1"]["special"] = "tribal_chief"
        d["nodes"]["s1"]["effects"][0] = {"do": "kill", "role": "gardener1", "cause": "unknown", "src": "L3071"}
        self.assertTrue(problems(check_doc(d), "f SAFETY"))

    def test_harmed_role_allowing_protected(self):
        d = self.doc()
        d["roles"]["gardener1"]["protected"] = "allow"
        d["nodes"]["s1"]["effects"][0] = {"do": "health_change", "role": "gardener1", "min": -20, "max": -10,
                                          "src": "L3071"}
        self.assertTrue(problems(check_doc(d), "f SAFETY"))

    def test_wrong_credit(self):
        d = self.doc()
        d["collection"]["credit"] = "someone else"
        self.assertTrue(problems(check_doc(d), "a SCHEMA"))

    def test_engine_seam_strips_authoring_keys(self):
        g = cc.graph_for_engine(self.doc())
        self.assertEqual(g["pools"]["A"]["items"][0], "neat rows with carefully labeled plants")
        self.assertNotIn("ledger", g["collection"])
        self.assertNotIn("text_only", g["nodes"]["p2"])


class TextRegex(unittest.TestCase):
    def test_tokens(self):
        import re
        src = 'Then (he/she) (L) the (K) into a (J, different from the first J) (into/onto) (the Chief/a child).'
        words = {"chief": {"3": "the Chief", "*": "the village leader"}}
        for data in ['Then (cook.he/she) {L} the {K} into a {J.2} {into|onto} {{@chief}|a child}.']:
            self.assertRegex(src, cc.text_regex(data, words))
        self.assertIsNone(re.search(cc.text_regex("Then (x.he/she) {L} a {K}", {}), src))


if __name__ == "__main__":
    unittest.main()
