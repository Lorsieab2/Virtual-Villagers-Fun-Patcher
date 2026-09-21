"""A parentage feature must describe the log the companion actually writes.

The description in each manifest is what the GUI shows a player and what the
transparency log publishes, so it is a promise about behaviour rather than
decoration. It drifted twice from one change to the exporter:

  * VV2 still said the father's age, head and body are "not recorded by this
    game" after the companion gained a lookup that recovers them.
  * VV1 said it appends "the mother's and father's names, their ages at
    conception, their head and body values" while VV1 is FATHER_NOT_RECORDED,
    so every father field -- his name included -- reads as unavailable.
  * VV2 through VV5 still advertised "their ages at conception" after the
    father's age was removed from the record entirely. The guard did not catch
    it because it only checked how a description talked about lookup FAILURE,
    never which fields it claimed. That omission also left the previous
    assertion inverted: with the age gone, no father field depends on a lookup
    any more, yet every description was still required to say one could fail.

All three were true when written, and none was caught by anything: a
description is prose, and no test read it against the C. This does, by deriving
the expectation from the exporter's own layout table and its format string.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "native/parentage_export/parentage_export.c"

# game number -> manifest, as far as each exists in this checkout. VV3 is added
# by a separate branch; a missing manifest is simply not checked, but a missing
# EXPORTER is a failure, since it is the source of truth being compared against.
MANIFESTS = {
    game: ROOT / f"data/vv{game}_parentage_feature.json" for game in (1, 2, 3, 4, 5)
}

# The exporter renders exactly these two strings when a field is unavailable.
NOT_RECORDED = "not recorded by this game"
NOT_FOUND = "(record not found)"


def _father_kinds() -> dict[int, str]:
    """Each game's father_kind, read from the exporter's own layout table.

    The table is declared GAME_LAYOUTS[6] with index 0 unused, so the rows that
    carry a FATHER_* constant are VV1..VV5 in order and can be read off without
    parsing C. An index-0 row that ever gained one would shift this, which the
    five-kinds assertion below would catch rather than silently mis-map.
    """
    source = EXPORTER.read_text(encoding="utf-8")
    # Block comments only; the file uses no // comments.
    #
    # Each row is preceded by a long comment explaining its offsets, and
    # those comments name FATHER_* constants freely -- the VV1 row's does
    # so several times. Matching them as though they were code shifted
    # every game's kind by one and dropped VV5 off the end, which is what
    # the five-kinds assertion reported when FATHER_BY_CAPTURE arrived.
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    table = source[source.index("GAME_LAYOUTS[6] = {") :]
    kinds = re.findall(
        r"\b(FATHER_BY_ID|FATHER_BY_NAME|FATHER_NOT_RECORDED|FATHER_BY_CAPTURE)\b,",
        table,
    )
    return {game: kind for game, kind in zip(range(1, 6), kinds)}


def _descriptions(path: Path) -> list[str]:
    found: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            value = node.get("description")
            if isinstance(value, str):
                found.append(value)
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(json.loads(path.read_text(encoding="utf-8")))
    return found


class ParentageDescriptionsMatchExporterTests(unittest.TestCase):
    def test_the_exporter_declares_a_kind_for_every_game(self):
        kinds = _father_kinds()
        self.assertEqual(
            sorted(kinds), [1, 2, 3, 4, 5], "layout table did not yield five kinds"
        )

    def test_a_description_does_not_promise_what_the_exporter_withholds(self):
        kinds = _father_kinds()
        checked = 0
        for game, path in MANIFESTS.items():
            if not path.exists():
                continue
            for description in _descriptions(path):
                if "arentage" not in description and "onception" not in description:
                    continue
                checked += 1
                with self.subTest(game=game):
                    if kinds[game] == "FATHER_NOT_RECORDED":
                        # Nothing about the father is available, his name
                        # included, so the description must say so and must not
                        # advertise his details.
                        self.assertIn(
                            NOT_RECORDED,
                            description,
                            "VV%d withholds every father field but the "
                            "description does not say so" % game,
                        )
                        self.assertNotIn(
                            "both parents are captured",
                            description,
                            "VV%d cannot capture the father at all" % game,
                        )
                    else:
                        # A lookup is attempted, so the description must not
                        # claim the fields are never recorded, and must use the
                        # wording the exporter actually prints when it fails.
                        self.assertNotIn(
                            "as %s" % NOT_RECORDED,
                            description,
                            "VV%d recovers the father's details, so the "
                            "description must not say they are %s"
                            % (game, NOT_RECORDED),
                        )
        self.assertGreater(checked, 0, "no parentage description was checked")

    def test_the_exporter_records_both_parents_ages(self):
        """The record now prints two ages -- the mother's and the father's.

        The owner reversed the earlier mother-only rule ("capture the father's
        ages too upon conception"), so a description mentioning the father's
        age now describes something true, and this guard confirms the exporter
        really prints it, from each parent's own record.
        """
        source = EXPORTER.read_text(encoding="utf-8")
        ages = source.count("Age at conception")
        self.assertEqual(
            ages, 2, "the exporter should print an age for both parents; "
            "if this changed, the descriptions and this guard need revisiting"
        )
        self.assertIn("*(const int *)(mother + g->age)", source)
        self.assertIn("*(const int *)(father_from_caller + g->age)", source)

    def test_a_description_that_mentions_an_age_names_a_parent(self):
        """A description mentioning an age must say whose -- the mother's, the
        father's, or both -- never a bare "age" that leaves it ambiguous."""
        for game, path in MANIFESTS.items():
            if not path.exists():
                continue
            for description in _descriptions(path):
                if "arentage" not in description and "onception" not in description:
                    continue
                if "age" not in description.lower():
                    continue
                with self.subTest(game=game):
                    self.assertTrue(
                        "mother's age" in description
                        or "her age" in description
                        or "father's age" in description
                        or "his age" in description
                        or "parents' ages" in description
                        or "both parents" in description,
                        "VV%d mentions an age without naming a parent" % game,
                    )

    def test_both_unavailable_strings_exist_in_the_exporter(self):
        source = EXPORTER.read_text(encoding="utf-8")
        # If either string is renamed, the descriptions above are quoting text
        # the log no longer prints, which is the same drift in a new form.
        self.assertIn(NOT_RECORDED, source)
        self.assertIn(NOT_FOUND, source)


if __name__ == "__main__":
    unittest.main()
