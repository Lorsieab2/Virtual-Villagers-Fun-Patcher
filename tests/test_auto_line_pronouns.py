"""The automatic outcome lines use each pronoun in its own form (live v1.35.97: A New Home's The Teaching Day showed
"gains 15 skill in what his does best").

Every line of src/vv_cie_graph.py AUTO_LINES (pinned equal to story_graph.inc CG_AUTO_LINES by
tests/test_cie_graph_v6.py) is rendered for a man (he), a woman (she) and, for the group lines, many villagers
(they):
  * <P> is the possessive his/her and only ever stands before a noun ("shakes his head", "forgets her name");
  * <H> is the subject he/she and takes a singular verb ("what he does best");
  * a group's line says "what they do best" (a plural verb);
  * no line puts a possessive or object pronoun where a subject belongs.
The engine's own rendering of the best-skill lines, in all five games, is the shared vectors' auto_lines_best_vv<N>
(tests/data/cie_v6_expand_vectors.json, run by tests/test_story_cie_graph_runtime_v6.py).
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_cie_graph as cg  # noqa: E402

PEOPLE = {"he": {"subject": cg.Binding("Bo", "m"), "friend": cg.Binding("Ana", "f")},
          "she": {"subject": cg.Binding("Ana", "f"), "friend": cg.Binding("Bo", "m")}}
# The nouns a possessive <P> may stand before.
POSSESSED = {"head", "name"}
WRONG = re.compile(r"\b(his|her|him|hers)\s+(does|do|is|are|was|has|have|gains|loses|gets|can|will)\b"
                   r"|\bwhat\s+(his|her|him)\b|\b(he|she|they)\s+(head|name|body|baby|skill)\b"
                   r"|\b(he|she)\s+do\b|\bthey\s+does\b", re.I)


def render(key: str, who: str) -> str:
    line = cg._auto_fill(key, "subject", skill="Farming", word="ants", number=5, other="friend")
    return cg.expand(line, PEOPLE[who])


def render_group(key: str) -> str:
    return cg._group_line(key, count=3, low=2, number=5, skill="Farming", word="Ana")


class AutoLinePronouns(unittest.TestCase):
    def test_each_template_uses_its_pronoun_forms(self):
        for key, template in cg.AUTO_LINES.items():
            with self.subTest(key=key):
                for m in re.finditer(r"<P>\s+(\w+)", template):
                    self.assertIn(m.group(1), POSSESSED, f"<P> (his/her) before a noun only: {template!r}")
                for m in re.finditer(r"<H>\s+(\w+)", template):
                    self.assertTrue(m.group(1).endswith("s"), f"<H> (he/she) takes a singular verb: {template!r}")
                self.assertNotRegex(template, r"what <P>", "a subject is <H>, never <P>")

    def test_every_line_reads_right_for_he_she_and_they(self):
        for key, template in cg.AUTO_LINES.items():
            with self.subTest(key=key):
                if "<C>" in template or key.startswith("group1_"):
                    text = render_group(key)
                    self.assertNotRegex(text, WRONG)
                    self.assertNotIn("<", text)
                    continue
                for who in ("he", "she"):
                    text = render(key, who)
                    self.assertNotRegex(text, WRONG, f"{who}: {text!r}")
                    self.assertNotIn("<", text)
                    if key == "no_effect":
                        # the owner's literal line (2026-11-23, cie-v6-binary.md 46): its parentheses are the
                        # words themselves, never a placeholder left unfilled
                        self.assertEqual(text, "(no effect)")
                        continue
                    if key.startswith("hv_") or key == "pz_flavor":
                        # cie-v6-binary.md 45: the owner's literal "(no effect)" ends every Heathens' village line
                        # and a puzzle's Heathen's (nothing is made to them)
                        self.assertTrue(text.endswith(" (no effect)"), text)
                        text = text[:-len(" (no effect)")]
                    self.assertNotIn("(", text, "no placeholder left unfilled")

    def test_the_best_skill_lines(self):
        self.assertEqual(render("skill_best", "he"), "Bo gains 5 skill in what he does best.")
        self.assertEqual(render("skill_best", "she"), "Ana gains 5 skill in what she does best.")
        self.assertEqual(render("skill_best-", "he"), "Bo loses 5 skill in what he does best.")
        self.assertEqual(render("skill_best-", "she"), "Ana loses 5 skill in what she does best.")
        self.assertEqual(render_group("group_best+"), "3 villagers each gain 5 skill in what they do best.")
        self.assertEqual(render_group("group_best-"), "3 villagers each lose 5 skill in what they do best.")
        self.assertEqual(render_group("group_best+r"), "3 villagers gain 2 to 5 skill in what they do best.")
        self.assertEqual(render_group("group_best-r"), "3 villagers lose 2 to 5 skill in what they do best.")

    def test_the_possessive_lines_stay_possessive(self):
        self.assertEqual(render("mood-", "he"), "Bo shakes his head.")
        self.assertEqual(render("mood-", "she"), "Ana shakes her head.")
        self.assertEqual(render("lose_name", "he"), "Bo forgets his name.")
        self.assertEqual(render("lose_name", "she"), "Ana forgets her name.")

    def test_the_engine_fills_he_she_for_h(self):
        """story_graph.inc cg_auto_add: <H> becomes the role's (id.he/she), as <P> its (id.his/her)."""
        native = (ROOT / "native" / "vvfp_story_upgrades" / "story_graph.inc").read_text(encoding="utf-8")
        body = native[native.index("static void cg_auto_add("):]
        body = body[:body.index("\n}\n")]
        self.assertIn("t[1] == 'H' ? \".he/she)\"", body)
        self.assertIn("t[1] == 'P' ? \".his/her)\"", body)


if __name__ == "__main__":
    unittest.main()
