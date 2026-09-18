"""The cross-game conventions doc must keep stating what the code does.

`docs/game-data-conventions.md` records facts that apply across all five
games -- zero-based indexing, the age-unit ratio, the shape of the
preference arrays. Each has already been got wrong once, and each produces
plausible-looking output when wrong, so the doc is only worth having if it
cannot quietly fall out of step with the code it describes.

These guards tie the doc's claims to the source of truth for each one
rather than asserting the numbers twice.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "game-data-conventions.md"
POPULATION = ROOT / "native" / "population_export" / "population_export.c"


class GameDataConventionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = DOC.read_text(encoding="utf-8")
        self.source = POPULATION.read_text(encoding="utf-8")

    def test_the_doc_ships_with_the_release(self) -> None:
        """A convention players cannot read is one they cannot check."""
        manifest = (ROOT / "scripts" / "build_release.py").read_text(
            encoding="utf-8")
        self.assertIn("docs/game-data-conventions.md", manifest)

    def test_the_preference_list_lengths_match_the_implementation(self) -> None:
        """The doc names 47/62/79; the C literals are what actually index."""
        for name, count in (("PREFERENCES_47", 47),
                            ("PREFERENCES_62", 62),
                            ("PREFERENCES_79", 79)):
            with self.subTest(list=name):
                start = self.source.index("static const char %s[] =" % name)
                end = self.source.index(";", start)
                literal = "".join(
                    part for part in self.source[start:end].split('"')[1::2])
                self.assertEqual(len(literal.split(",")), count)
                sentence = re.search(
                    r"The list itself grew across the series[^.]*\.",
                    self.doc, re.S)
                self.assertIsNotNone(
                    sentence, "doc must list the per-game list lengths")
                self.assertIn(
                    str(count), sentence.group(0),
                    "doc must state the %d-entry list" % count)

    def test_the_doc_states_the_age_ratio_the_owner_gave(self) -> None:
        """20, not a value re-derived from a single rounded sample."""
        self.assertRegex(self.doc, r"\b20 age units = 1 year\b")
        self.assertNotRegex(self.doc, r"\b21 age units\b")

    def test_the_doc_states_that_indexing_is_zero_based(self) -> None:
        """The first entry of a list is value 0, with no adjustment."""
        self.assertRegex(
            self.doc,
            r"(?is)first entry of that list is\s+value\s+\*\*0\*\*,\s+not value 1")

    def test_the_doc_states_both_empty_markers(self) -> None:
        """-1 AND past-the-end both mean empty; requiring only one rejects
        the correct offsets, which is exactly how they were once discarded."""
        sentence = re.search(
            r"A slot is empty when it holds[^.]*\.", self.doc, re.S)
        self.assertIsNotNone(
            sentence, "doc must define what an empty slot holds")
        empty = sentence.group(0)
        self.assertIn(
            "`-1`", empty, "doc must name -1 as an empty marker")
        self.assertIn(
            "past the end of the list", empty,
            "doc must name a past-the-end index as an empty marker")

    def test_the_doc_matches_the_first_filled_behaviour(self) -> None:
        """The panel shows the first FILLED slot; the code must agree."""
        self.assertRegex(self.doc, r"(?i)\*\*first filled\*\* entry")
        body = self.source[self.source.index("static int first_preference("):]
        body = body[:body.index("\n}")]
        self.assertIn("continue;", body)

    # No line-ending assertion here. The committed blob is LF, but nothing
    # pins this doc's bytes, and the repository leaves docs/*.md unspecified
    # in .gitattributes -- so the worktree encoding depends on the checkout's
    # core.autocrlf and legitimately differs between a developer machine and
    # a CI runner. Asserting LF tested the environment rather than the file,
    # and failed in CI for a doc that was correct in the repository. The eol
    # rules that do exist are for files carrying raw hash pins, not for docs.


if __name__ == "__main__":
    unittest.main()
