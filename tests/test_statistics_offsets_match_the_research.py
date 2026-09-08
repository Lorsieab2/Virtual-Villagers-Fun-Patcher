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

# The exporter prints this row from `+0x28`; the research table records that
# offset as Twins Birthed. The divergence is real, documented, and awaiting an
# owner decision -- not drift for this module to fail on.
KNOWN_LABEL_DIVERGENCE = {"0x28": ("Special Stews Found", "Twins Birthed")}


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

    def test_the_known_label_divergence_is_still_recorded(self) -> None:
        """+0x28 prints one name and is documented as another, on purpose.

        If the row is ever relabelled, this fails and the divergence note in
        the research document has to be revisited in the same change.
        """
        body = _function_body("write_later_game")
        documented = _documented_layout()
        for offset, (shipped, researched) in KNOWN_LABEL_DIVERGENCE.items():
            with self.subTest(offset=offset):
                self.assertIn(
                    r'"%s: %%d\n"' % shipped,
                    body,
                    "the exporter no longer prints %r; the recorded divergence is stale"
                    % shipped,
                )
                self.assertIn(
                    researched,
                    documented.get(offset, ""),
                    "the research table no longer records +%s as %r"
                    % (offset, researched),
                )


if __name__ == "__main__":
    unittest.main()
