"""New Believers with Guardians of Isola Rewrite: every event text that says Heathen, convert or believer(s) switches
to its Guardians form at run time (docs/event-collection/guardians-wording.md; the owner, 2026-11-14 / 11-16 / 11-22:
"fix the Guardians of Isola event wordings too").

Pinned here:
  * every New Believers collection event (check j over every file): each such text has a Guardians form that differs;
  * every procedural piece New Believers can draw (assets/event_collection/pieces): each such text and label carries
    its Guardians form (PF_GUARDIANS), free of the words, made only by its own event's approved pairs, and the
    composer shows it with the patch on and the plain text with it off -- except the one piece awaiting the owner;
  * the engine's own words (story_graph.inc): the automatic "becomes a Heathen" lines, the log's "became a Heathen",
    what a role and an event need ("a believer", "believers") switch with cg_guardians_on;
  * the composer (story_procedural.inc) reads every shown text and label through pc_words.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

import collection_check as cc  # noqa: E402
import procedural_pieces as pp  # noqa: E402
import vv_cie_graph as cg  # noqa: E402
import vv_procedural as vp  # noqa: E402

PIECES = ROOT / "assets" / "event_collection" / "pieces"
NATIVE = ROOT / "native" / "vvfp_story_upgrades"


def shipped_pieces():
    for p in sorted(PIECES.glob("pieces-*.pcb")):
        for piece in vp.read_pcb(p.read_bytes(), p.stem[7:]).pieces:
            yield p.stem, piece


class CollectionTexts(unittest.TestCase):
    def test_every_new_believers_text_has_a_guardians_form(self):
        files = [p for p in (ROOT / "data" / "event_collection").rglob("*.json")
                 if p.name not in ("manifest.json", "shared_pools.json") and "content_tags" not in p.parts]
        bad, seen = [], 0
        for p in files:
            doc = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(doc, dict) or "nodes" not in doc or 5 not in (doc.get("games") or []):
                continue
            seen += 1
            rep = cc.Report(str(p))
            cc.check_guardians(doc, rep)
            bad += [f"{p.relative_to(ROOT).as_posix()}: {x}" for x in rep.problems]
        self.assertGreater(seen, 4000)
        self.assertEqual(bad, [])


class ProceduralPieces(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pieces = list(shipped_pieces())
        cls.keys = sorted(cc.lib.guardians_pairs(), key=len, reverse=True)

    def awaiting(self, pid: str) -> bool:
        return any(a in pid for a in pp.GUARDIANS_AWAITING)

    def test_every_piece_that_says_the_words_switches(self):
        bad, flagged = [], 0
        for group, p in self.pieces:
            if not p.games & (1 << 4) or not (pp.says_guardians_word(p.text) or pp.says_guardians_word(p.label)):
                continue
            if self.awaiting(p.id):
                continue
            if not p.flags & vp.PF_GUARDIANS:
                bad.append(f"{group} {p.id}: no Guardians form")
                continue
            flagged += 1
            if pp.says_guardians_word(p.gtext) or pp.says_guardians_word(p.glabel):
                bad.append(f"{group} {p.id}: its Guardians form still says Heathen / convert / believer")
            if (p.gtext, p.glabel) == (p.text, p.label):
                bad.append(f"{group} {p.id}: its Guardians form is the same text")
            # made only by the approved pairs (guardians-wording.md / the Living bank's)
            want = (pp.guardians_form(p.id, p.text, False, self.keys), pp.guardians_form(p.id, p.label, True, self.keys))
            if (p.gtext, p.glabel) != want:
                bad.append(f"{group} {p.id}: {(p.gtext, p.glabel)!r} is not {want!r}")
        self.assertGreater(flagged, 30)
        self.assertEqual(bad, [])

    def test_only_new_believers_pieces_with_the_words_are_flagged(self):
        bad = [p.id for _g, p in self.pieces if p.flags & vp.PF_GUARDIANS
               and (not p.games & (1 << 4)
                    or not (pp.says_guardians_word(p.text) or pp.says_guardians_word(p.label)))]
        self.assertEqual(bad, [])

    def test_no_guardians_name_in_any_form(self):
        name = re.compile(r"\bGuardians?\b")
        bad = [p.id for _g, p in self.pieces if p.flags & vp.PF_GUARDIANS
               and any(name.search(x or "") and not name.search(y or "")
                       for x, y in ((p.gtext, p.text), (p.glabel, p.label)))]
        self.assertEqual(bad, [])

    def test_the_owners_piece_pair(self):
        # the owner, 2026-11-22: s027's procedural setup, "the believers' circle" -> "the faithful's circle"
        self.assertEqual(pp.GUARDIANS_AWAITING, frozenset())
        s027 = [p for _g, p in self.pieces if p.id.endswith("s027_isolan_fire_s")]
        self.assertTrue(s027)
        for p in s027:
            self.assertTrue(p.flags & vp.PF_GUARDIANS)
            self.assertIn("the believers' circle", p.text)
            self.assertEqual(p.gtext, p.text.replace("the believers' circle", "the faithful's circle"))

    def test_the_composer_shows_the_form_only_with_the_patch(self):
        setup = vp.Piece("s1", vp.KIND_SETUP, flags=vp.PF_GUARDIANS | vp.PF_BELIEVERS, games=0x10,
                         text="A Heathen waits.", label="The Heathen", gtext="An Isolan waits.", glabel="The Isolan",
                         slots=[vp.Slot("subject", min_age=14, flags=vp.SF_BELIEVERS)])
        app = [vp.Piece(f"a{i}", vp.KIND_APPROACH, games=0x10, label=f"Ask {i}") for i in range(2)]
        out = vp.Piece("o1", vp.KIND_OUTCOME, flags=vp.PF_GUARDIANS, games=0x10, text="Two believers smile.",
                       gtext="Two villagers of faith smile.", links=[vp.Link("a0"), vp.Link("a1")])
        back = vp.read_pcb(vp.write_pcb([setup, *app, out]), "t")
        by = {p.id: p for p in back.pieces}
        self.assertEqual((by["s1"].gtext, by["s1"].glabel), ("An Isolan waits.", "The Isolan"))
        self.assertEqual(by["o1"].gtext, "Two villagers of faith smile.")
        self.assertIsNone(by["a0"].gtext)
        comp = vp.Composition("t", by["s1"], [by["a0"], by["a1"]], [[by["o1"]], [by["o1"]]], None, None, {}, {})
        on = vp.graph_of(comp, 5, guardians=True)
        off = vp.graph_of(comp, 5)
        other = vp.graph_of(comp, 4, guardians=True)
        self.assertEqual((on["title"], on["nodes"]["q"]["text"], on["nodes"]["o1_1"]["text"]),
                         ("The Isolan", "An Isolan waits.", "Two villagers of faith smile."))
        self.assertEqual((off["title"], off["nodes"]["q"]["text"], off["nodes"]["o1_1"]["text"]),
                         ("The Heathen", "A Heathen waits.", "Two believers smile."))
        self.assertEqual(other["title"], "The Heathen")

    def test_the_form_is_always_the_next_string(self):
        # a lone string equal to a flagged text must not be shared with the pair
        a = vp.Piece("a", vp.KIND_OUTCOME, games=0x10, text="Believers rest.", links=[vp.Link("x")])
        b = vp.Piece("b", vp.KIND_OUTCOME, flags=vp.PF_GUARDIANS, games=0x10, text="Believers rest.",
                     gtext="The faithful rest.", links=[vp.Link("x")])
        x = vp.Piece("x", vp.KIND_APPROACH, games=0x10, label="Go")
        by = {p.id: p for p in vp.read_pcb(vp.write_pcb([x, a, b])).pieces}
        self.assertEqual((by["a"].text, by["a"].gtext), ("Believers rest.", None))
        self.assertEqual((by["b"].text, by["b"].gtext), ("Believers rest.", "The faithful rest."))


class EngineWords(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = (NATIVE / "story_graph.inc").read_text(encoding="utf-8")
        cls.proc = (NATIVE / "story_procedural.inc").read_text(encoding="utf-8")

    def test_automatic_lines(self):
        m = re.search(r'#define CG_GUARDIANS_BECOMES "([^"]+)"', self.graph)
        self.assertIsNotNone(m)
        self.assertEqual({k: m.group(1) for k in ("status", "apostasy")}, cg.GUARDIANS_AUTO_LINES)
        self.assertEqual({k: cg.AUTO_LINES[k] for k in cg.GUARDIANS_AUTO_LINES},
                         {k: v.replace("an Isolan", "a Heathen") for k, v in cg.GUARDIANS_AUTO_LINES.items()})
        self.assertIn('lstrcmpA(key, "status") == 0 || lstrcmpA(key, "apostasy") == 0) && cg_guardians_on()',
                      self.graph)
        # both readers of the table go through it
        self.assertEqual(self.graph.count("cg_auto_guardians(key, "), 2)

    def test_log_line_and_needs(self):
        self.assertIn('cg_guardians_on() ? " became an Isolan." : " became a Heathen."', self.graph)
        self.assertIn('cg_guardians_on() ? ", a tribe member" : ", a believer"', self.graph)
        self.assertIn('return cg_guardians_on() ? "tribe members" : "believers";', self.graph)
        self.assertNotIn('game == 5 ? "believers"', self.graph)

    def test_custom_island_event_refusal(self):
        c5 = (NATIVE / "story_c5.inc").read_text(encoding="utf-8")
        body = c5[c5.index("static const char *c5_arm_refusal(void)"):]
        body = body[:body.index("\n}\n")]
        self.assertIn('cg_guardians_on()\n        ? "A question needs a living adult tribe member in the village to ask '
                      'it.', body)
        self.assertIn(': "A question needs a living adult believer in the village to ask it.', body)

    def test_composer_reads_shown_words_through_pc_words(self):
        self.assertIn("#define PC_F_GUARDIANS 0x20u", self.proc)
        self.assertEqual(vp.PF_GUARDIANS, 0x20)
        self.assertEqual(self.proc.count("pc_words("), 11)    # the definition and its ten readers
        # every remaining direct read of a text (32) or label (36) is a check, never a shown text
        direct = [ln.strip() for ln in self.proc.splitlines() if re.search(r"pc_str\(pc_u32\([^)]*\+ 3[26]\)\)", ln)]
        self.assertTrue(all(("== NULL" in d or "!= NULL" in d) for d in direct), direct)


class LeftTheTribeRecord(unittest.TestCase):
    """The owner (2026-11-22): the Deaths log's "Left the tribe: became a Heathen" is "...became an Isolan" with the
    patch (the companion: tests/test_cause_of_death.py); every reader takes both, and a record the patcher adds
    afterwards follows the logs' own words."""

    def test_the_companion_writes_it(self):
        cod = (ROOT / "native" / "vvfp_cause_of_death" / "cod_arrivals.inc").read_text(encoding="utf-8")
        self.assertIn('What happened: Left the tribe: became %s\\n', cod)
        self.assertIn('g_game == 5 && arrival_guardians_on() ? "an Isolan" : "a Heathen"', cod)

    def test_readers_take_both(self):
        import vv_genealogy as gen
        import vv_log_additions as la
        both = ("Left the tribe: became a Heathen", "Left the tribe: became an Isolan")
        self.assertEqual(la.LEFT_RECORDS, both)
        self.assertEqual(gen.LEFT_RECORDS, both)
        for mod in ("vv_log_additions", "vv_genealogy"):
            src = (ROOT / "src" / f"{mod}.py").read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"(\)|strip\(\)) == LEFT_FOR_THE_HEATHENS", src), mod)

    def test_an_added_record_says_what_the_logs_say(self):
        import vv_log_additions as la

        class Person:
            def value(self, label):
                return {"Name": "Ana", "Sex": "Female", "Head": "3", "Body": "4"}.get(label)
        isolan = la._left_record(Person(), la.LEFT_FOR_THE_ISOLANS)
        heathen = la._left_record(Person())
        self.assertIn("  What happened: Left the tribe: became an Isolan\n", isolan)
        self.assertIn("(became an Isolan with no record written", isolan)
        self.assertNotIn("Heathen", isolan)
        self.assertIn("  What happened: Left the tribe: became a Heathen\n", heathen)


if __name__ == "__main__":
    unittest.main()
