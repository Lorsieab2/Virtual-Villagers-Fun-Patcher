"""The player-facing .txt exports must open readably in a Windows text viewer.

Both companions write their logs with bare `\\n` in their format strings, which
is correct C. Whether that reaches the disk as LF or CRLF is decided entirely
by the mode the file was opened in, and both were opened BINARY -- `"ab"` for
the parentage log, `"wb"` for the statistics file. So every line break was a
bare LF.

These games are Windows-only and the exports are files a player opens by
double-clicking. Notepad renders a bare-LF file as one unbroken line: a
256-record parentage log measured 2816 LF and zero CRLF, all of it on one line.

The fix is the open mode, not the format strings -- the C runtime translates
`\\n` to CRLF in text mode, so the code stays portable and the artifact becomes
readable.

The parentage READ side stays binary on purpose. `count_records` has to see the
bytes as they are on disk: it matches "Conception " at the START of a line, so
it is ending-agnostic and works on a file that mixes both, which is exactly
what an upgrading player has. Reading in text mode would also silently swallow
a lone CR, which is the corruption the count is meant to survive.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PARENTAGE = ROOT / "native/parentage_export/parentage_export.c"
STATISTICS = ROOT / "native/statistics_export/statistics_export.c"


def _open_modes(source: Path) -> list[str]:
    """Every mode string passed to _wfopen in one translation unit."""
    return re.findall(r'_wfopen\([^,]+,\s*L"([^"]+)"\)', source.read_text(encoding="utf-8"))


class ExportedLogsUseWindowsLineEndingsTests(unittest.TestCase):
    def test_the_parentage_log_is_written_in_text_mode(self):
        modes = _open_modes(PARENTAGE)
        self.assertIn(
            "a",
            modes,
            "the parentage log must be appended in TEXT mode so its \\n "
            "reaches the disk as CRLF; a bare-LF .txt shows as one unbroken "
            "line in Notepad",
        )
        self.assertNotIn(
            "ab",
            modes,
            "binary append writes bare LF, which is what made the log "
            "unreadable in every Windows text viewer",
        )

    def test_the_parentage_log_is_read_in_binary_mode(self):
        """The read side must NOT follow the write side into text mode.

        count_records needs the bytes as they are on disk. A player upgrading
        mid-save has a file whose old records end in LF and whose new ones end
        in CRLF, and the count has to be right for both -- numbering and the
        256-record rollover both depend on it.
        """
        modes = _open_modes(PARENTAGE)
        self.assertIn(
            "rb",
            modes,
            "count_records must read in binary; text mode would swallow a "
            "lone CR, which is the corruption it exists to survive",
        )

    def test_the_statistics_file_is_written_in_text_mode(self):
        modes = _open_modes(STATISTICS)
        self.assertIn("w", modes, "the statistics export must be written in TEXT mode")
        self.assertNotIn("wb", modes, "binary write produces a bare-LF .txt")

    def test_neither_companion_hardcodes_carriage_returns(self):
        """The format strings must stay `\\n`, with the mode doing the work.

        Writing "\\r\\n" in text mode would produce CRCRLF, so a later
        well-meaning edit that "adds the missing \\r" reintroduces the problem
        in a form that looks like a fix.
        """
        for source in (PARENTAGE, STATISTICS):
            with self.subTest(source=source.name):
                text = source.read_text(encoding="utf-8")
                self.assertNotIn(
                    "\\r\\n",
                    text,
                    "%s must not hardcode CRLF; in text mode that becomes "
                    "CRCRLF" % source.name,
                )


if __name__ == "__main__":
    unittest.main()
