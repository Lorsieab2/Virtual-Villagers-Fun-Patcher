"""Counted results must read correctly when the count is one.

Every game reports how many villagers an upgrade affected. VV3 and VV5 chose the
word by count; VV1, VV2 and VV4 hardcoded the plural, so a single cured villager
produced "Cured sickness from 1 villagers."

The rule guarded here is narrow and mechanical: a format string may not follow a
count conversion with a hardcoded "villagers". Pick the word with a helper, the
way three of the five already did.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native"

# "%d villagers" / "%u Villagers" -- a count immediately followed by the noun.
# CASE-INSENSITIVE: a case-sensitive version missed the Equal Division
# results, which capitalise the word ("Set %u Villagers' Job Preferences."),
# so those still read "1 Villagers" while this guard passed.
HARDCODED = re.compile(r"%[0-9]*[du]\s+villagers?\b", re.IGNORECASE)
# A counted villager result of any shape, used only for anti-vacuity.
COUNTED = re.compile(r"%[0-9]*[du]\s+(?:%s|villagers?)\b", re.IGNORECASE)


# The companions the patcher actually deploys. The optional Full Mastery and
# Full Heal candidates are NOT on any default path -- they are separate
# catalog-visible candidates a player has to select -- and they still hardcode
# the plural in 19 places. That is a known, deliberate follow-up rather than an
# oversight: fixing them means rewriting nineteen argument lists and rebuilding
# five more companions, which is not worth doing in the same change as a
# release. This guard covers what ships by default and names what it does not,
# instead of passing quietly over both.
SHIPPING = (
    "vv1_origins_icons/vv1_origins_icons.c",
    "vv2_origins_icons/vv2_origins_icons.c",
    "vv3_full_mastery_candidate/vv3_full_mastery_candidate.c",
    "vv4_origins_icons/vv4_origins_icons.c",
    "vv5_task9_origins/vv5_task9_origins.c",
)


def _sources() -> list[Path]:
    return [NATIVE / rel for rel in SHIPPING]


class CountedResultPluralTests(unittest.TestCase):
    def test_no_counted_result_hardcodes_the_plural(self) -> None:
        offenders = []
        for source in _sources():
            text = source.read_text(encoding="utf-8", errors="replace")
            for line_number, line in enumerate(text.splitlines(), 1):
                if line.lstrip().startswith(("*", "/*", "//")):
                    continue  # prose, including the comments explaining this rule
                for match in HARDCODED.finditer(line):
                    offenders.append(
                        f"{source.relative_to(ROOT)}:{line_number}: {match.group(0)}"
                    )
        self.assertEqual(
            offenders,
            [],
            "a counted result hardcodes the plural, so it reads '1 villagers'; "
            "choose the word by count:\n" + "\n".join(offenders),
        )

    def test_the_scan_actually_sees_counted_results(self) -> None:
        """Without this, deleting every counted message would 'pass'."""
        seen = 0
        for source in _sources():
            text = source.read_text(encoding="utf-8", errors="replace")
            seen += len(COUNTED.findall(text))
        self.assertGreaterEqual(
            seen, 5, f"only {seen} counted villager results found; scan is broken"
        )

    def test_the_shipping_list_is_complete_and_real(self) -> None:
        """The exemption above is only honest while this list is right."""
        for rel in SHIPPING:
            with self.subTest(source=rel):
                self.assertTrue((NATIVE / rel).is_file(), f"{rel} is missing")
        self.assertEqual(len(SHIPPING), 5, "one deployed companion per game")

    def test_every_game_has_a_word_chooser(self) -> None:
        """All five companions must be able to pick the singular."""
        choosers = {
            "vv1_origins_icons": "vv_villagers_word",
            "vv2_origins_icons": "vv_villagers_word",
            "vv3_full_mastery_candidate": "villagers_word",
            "vv4_origins_icons": "vv_villagers_word",
            "vv5_task9_origins": "vpl_lc",
        }
        possessive = {
            "vv2_origins_icons": "vv_villagers_possessive",
            "vv5_task9_origins": "vpl_pos",
        }
        for directory, helper in choosers.items():
            source = NATIVE / directory / f"{directory}.c"
            with self.subTest(game=directory):
                self.assertTrue(source.is_file(), f"{source} is missing")
                text = source.read_text(encoding="utf-8", errors="replace")
                self.assertIn(
                    helper, text,
                    f"{directory} has no way to choose the singular form",
                )
                if directory in possessive:
                    # "Villager's" against "Villagers'" moves the apostrophe,
                    # so the possessive cannot reuse the plain noun chooser.
                    self.assertIn(possessive[directory], text)

    def test_the_pattern_matches_the_shape_that_shipped(self) -> None:
        """Positive control, so a clean run means the regex still works."""
        self.assertTrue(HARDCODED.search('"Cured sickness from %d villagers."'))
        self.assertTrue(HARDCODED.search('"Fully mastered %u villagers."'))
        # The capitalised shapes the case-sensitive version let through.
        self.assertTrue(HARDCODED.search("Set %u Villagers' Job Preferences."))
        self.assertTrue(HARDCODED.search('"%s: %u Villagers (%u Male, %u Female)."'))
        self.assertIsNone(HARDCODED.search('"Cured sickness from %d %s."'))


if __name__ == "__main__":
    unittest.main()
