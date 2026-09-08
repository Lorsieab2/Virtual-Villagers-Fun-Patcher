"""Pin the exporter's statistics offsets to the documented block layout.

`docs/village-statistics-export-research.md` carries a table mapping each
statistics-block offset to the statistic stored there, and
`native/statistics_export/statistics_export.c` reads those offsets to build
the exported rows. Nothing checked that the two agreed.

That gap is not hypothetical. Review of PR #288 caught two live
contradictions by hand: the research document listed VV1's `+0x9E38` as a
confirmed lifetime *Villagers Buried* while a later section of the same file
established it as a saturating recount, and a blocked-counters entry was
removed on evidence that satisfied a neighbouring requirement rather than the
one it was filed under. Both were right about the binaries and wrong about
the rest of the repository, which is exactly the class of defect a reader
catches and a disassembler does not.

The offsets themselves are verified against the stock executables elsewhere.
What this module adds is the consistency check: the C source and the research
table must describe the same layout, so that correcting one without the other
fails here rather than shipping a row that contradicts its own documentation.

The label at `+0x28` is deliberately allowed to disagree. The research
document records it as Twins Birthed on disassembly evidence, while the
exporter still prints "Special Stews Found"; renaming a shipped row changes
user-visible output and is the owner's decision. This module pins the
*offset* agreement and records the known label divergence explicitly, so the
divergence stays visible instead of being mistaken for drift.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "native" / "statistics_export" / "statistics_export.c"
RESEARCH = ROOT / "docs" / "village-statistics-export-research.md"

# Rows whose printed label must match what the research document records for
# that offset. `+0x28` is here because it did not: the later games printed
# "Special Stews Found" over a field the childbirth routine increments on the
# twins branch, and the requirements ask for Twins Birthed in all five games
# with Special Stews Found in The Lost Children alone. Pinning it keeps the
# stale enum-name mapping from being reintroduced.
LABELLED_OFFSETS = {"0x28": "Twins Birthed"}

# The Lost Children genuinely has a Special Stews Found statistic, from a
# different field. Its writer must keep that row.
VV2_KEEPS = "Special Stews Found"


def _function_body(name: str) -> str:
    text = SOURCE.read_text(encoding="utf-8")
    start = text.index("static int %s(" % name)
    nxt = text.find("\nstatic ", start + 1)
    return text[start:nxt if nxt != -1 else len(text)]


def _read_offsets(body: str) -> list[str]:
    """Offsets the body reads out of the statistics block, in row order."""
    return [
        m.group(1).lower()
        for m in re.finditer(r"read_int\(\s*statistics\s*,\s*(0x[0-9A-Fa-f]+)\)", body)
    ]


def _documented_layout() -> dict[str, str]:
    """The offset -> statistic table from the research document."""
    layout: dict[str, str] = {}
    for line in RESEARCH.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\|\s*`(\+0x[0-9A-Fa-f]+)`\s*\|\s*(.+?)\s*\|\s*$", line)
        if match is None:
            continue
        offset = match.group(1)[1:].lower()
        # Keep the first table that defines an offset: later tables in the
        # document describe per-game memorial arrays, not this block.
        layout.setdefault(offset, match.group(2))
    return layout


def _described_offsets() -> set[str]:
    """Offsets the document accounts for, whether in the table or in prose.

    Fields added by this project live in the block's reserve and are described
    in prose rather than in the stock-layout table -- VV5's Heathens Converted
    at `+0x34` is one. Requiring a table row for those would fail on documented
    behaviour, so an explicit mention anywhere in the document counts.
    """
    text = RESEARCH.read_text(encoding="utf-8")
    found = {
        match.group(1).lower()
        for match in re.finditer(r"`?\+(0x[0-9A-Fa-f]{2})`?", text)
    }
    return found | set(_documented_layout())


class StatisticsOffsetsMatchTheResearchTests(unittest.TestCase):
    def test_the_later_game_writer_reads_a_contiguous_block(self) -> None:
        """Rows step by 4 with no gap, so a dropped row cannot pass unnoticed."""
        offsets = [int(value, 16) for value in _read_offsets(_function_body("write_later_game"))]
        self.assertTrue(offsets, "no statistics reads found in write_later_game")
        self.assertEqual(offsets, sorted(offsets), "rows are not in ascending offset order")
        self.assertEqual(
            offsets,
            list(range(offsets[0], offsets[0] + 4 * len(offsets), 4)),
            "statistics rows are no longer contiguous 4-byte fields",
        )

    def test_every_read_offset_is_documented(self) -> None:
        described = _described_offsets()
        self.assertIn("0x04", described, "the research document was not parsed")
        for writer in ("write_later_game", "write_vv5"):
            for offset in _read_offsets(_function_body(writer)):
                with self.subTest(writer=writer, offset=offset):
                    self.assertIn(
                        offset,
                        described,
                        "%s reads +%s, which the research document does not describe"
                        % (writer, offset),
                    )

    def test_labelled_offsets_print_what_the_research_records(self) -> None:
        """A row's printed label must match the statistic at its offset.

        `+0x28` shipped as "Special Stews Found" over a field the childbirth
        routine increments on the twins branch. Both later-game writers now
        print Twins Birthed, and this fails if either regresses to the stale
        enum-name mapping.
        """
        documented = _documented_layout()
        for writer in ("write_later_game", "write_vv5"):
            body = _function_body(writer)
            for offset, label in LABELLED_OFFSETS.items():
                with self.subTest(writer=writer, offset=offset):
                    self.assertIn(
                        r'"%s: %%d\n"' % label,
                        body,
                        "%s does not print +%s as %r" % (writer, offset, label),
                    )
                    self.assertIn(
                        label,
                        documented.get(offset, ""),
                        "the research table no longer records +%s as %r"
                        % (offset, label),
                    )

    def test_the_lost_children_keeps_its_own_stew_row(self) -> None:
        """VV2's Special Stews Found is a real, separate statistic.

        The later-game relabel must not be applied to The Lost Children, whose
        requirements list Special Stews Found explicitly and whose value comes
        from a different field entirely.
        """
        body = _function_body("write_vv2")
        self.assertIn(
            r'"%s: %%d\n"' % VV2_KEEPS,
            body,
            "write_vv2 no longer prints its Special Stews Found row",
        )


if __name__ == "__main__":
    unittest.main()
