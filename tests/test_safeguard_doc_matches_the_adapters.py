"""The prose table in the safeguard doc must agree with the adapter data.

`data/mask_identity_adapters.json` is the record of what is proven, and
`docs/mask-identity-safeguard.md` renders the same facts as a table for people
to read. Nothing kept the two in step, and they drifted: VV1's health offset was
established at `+0x344` in the research and the exporter, while the adapter said
"no VV1 health offset is defined or documented" and the doc showed a dash. Three
places asserted a thing that a fourth disproved.

Prose that restates data is a cache, and an unchecked cache goes stale silently.
The failure is quiet in the worst way -- a reader consults the table, sees a
dash, and concludes the offset is unknown rather than that the table is old.

This test is deliberately narrow. It does not check the adapter against the
executable; `AdapterEvidenceTableTests` already requires a citation for every
offset, and the binary is the authority for whether that citation is true. It
checks only that the doc says what the data says, which is the one relationship
nothing else covers.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = ROOT / "data" / "mask_identity_adapters.json"
DOC = ROOT / "docs" / "mask-identity-safeguard.md"

# The doc writes an unproven field as a dash, which is not the same as zero and
# not the same as "look at the game next to it" -- the doc says so itself.
ABSENT = "--"

# Column order in the offsets table, after the leading game name.
COLUMNS = (
    "active",
    "health",
    "age",
    "gender",
    "head",
    "body",
    "skills",
    "preferred_skill",
    "likes",
    "dislikes",
    "nursing",
    "name",
)


def _doc_rows() -> dict[str, list[str]]:
    """The offsets table, keyed by game, as raw cell text."""
    rows: dict[str, list[str]] = {}
    for line in DOC.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^\|\s*(VV[1-5])\s*\|(.*)\|\s*$", line.strip())
        if not match:
            continue
        cells = [cell.strip() for cell in match.group(2).split("|")]
        # The doc has more than one table keyed by game name -- the adapter
        # status table is two columns wide. Only the offsets table has a cell
        # per field, so width is what tells them apart; matching on the game
        # name alone silently mixes the two.
        if len(cells) <= len(COLUMNS):
            continue
        # The final column is prose about the protected villager, not an offset.
        rows[match.group(1)] = cells[: len(COLUMNS)]
    return rows


class SafeguardDocMatchesTheAdaptersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.games = json.loads(ADAPTERS.read_text(encoding="utf-8"))["games"]
        cls.rows = _doc_rows()

    def test_the_table_lists_every_game(self) -> None:
        self.assertEqual(sorted(self.rows), ["VV1", "VV2", "VV3", "VV4", "VV5"])

    def test_every_cell_matches_the_adapter(self) -> None:
        for label, cells in sorted(self.rows.items()):
            entry = self.games[label.lower()]
            fields = entry.get("fields", {})
            self.assertEqual(
                len(cells),
                len(COLUMNS),
                f"{label} row has {len(cells)} offset cells, expected {len(COLUMNS)}",
            )
            for name, cell in zip(COLUMNS, cells):
                with self.subTest(game=label, field=name):
                    field = fields.get(name)
                    if field is None:
                        self.assertTrue(
                            cell.startswith(ABSENT),
                            f"{label}.{name} is not in the adapter, so the doc "
                            f"must show a dash, not {cell!r}",
                        )
                        continue
                    # A proven field must appear as its offset. Some cells carry
                    # a trailing note -- "0x1C5C (x5, f32)" -- so this checks the
                    # offset is present rather than that the cell is only that.
                    self.assertIn(
                        field["offset"].lower(),
                        cell.lower(),
                        f"{label}.{name} is proven at {field['offset']} but the "
                        f"doc cell reads {cell!r}",
                    )
                    self.assertFalse(
                        cell.startswith(ABSENT),
                        f"{label}.{name} is proven at {field['offset']} but the "
                        f"doc shows it as absent",
                    )

    def test_no_absent_field_is_described_as_proven(self) -> None:
        """The inverse direction: a dash must not hide a recorded offset."""
        for label, cells in sorted(self.rows.items()):
            absent = self.games[label.lower()].get("absent_fields", {})
            for name, cell in zip(COLUMNS, cells):
                if name in absent:
                    with self.subTest(game=label, field=name):
                        self.assertTrue(
                            cell.startswith(ABSENT),
                            f"{label}.{name} is listed in absent_fields but the "
                            f"doc gives it an offset: {cell!r}",
                        )


if __name__ == "__main__":
    unittest.main()
