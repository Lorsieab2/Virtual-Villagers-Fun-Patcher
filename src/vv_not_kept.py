"""Records the saved village never held (v1.35.97): one rule for every patcher tool that reads the logs.

Before a village's first save the game can play the same time twice: it plays the village once (the
start-up catch-up), loads it again from its save and plays the same time over.  The Parentage Export
companion writes the first run's Conception and Birth records all the same, each closing with

    "  Note: Not in the village as it was saved: the game played this time, then"

(native/parentage_export/parentage_export.c NOT_KEPT_NOTE -- conception_not_kept -- and BIRTH_NOT_KEPT_NOTE
-- birth_not_kept; docs/game-data-conventions.md "The same village played twice before its first save").
Such a record is no pregnancy and no child of the saved village: a tool that builds family trees, parents,
last names, counts or repairs from the logs skips it (logs must match the save), and a tool that shows or
copies the log's own text keeps it as it is.
"""
from __future__ import annotations

# The first line of both notes, exactly as the companion writes it (two spaces in, before the line end).
NOT_KEPT_LINE = "  Note: Not in the village as it was saved: the game played this time, then"


def is_not_kept_line(line: str) -> bool:
    """Is `line` the companion's not-kept Note?  Its indent and line end ("\\r\\n" or "\\n") are not
    looked at, so a reader that strips its lines matches it the same; the words must be the very ones."""
    return line.strip() == NOT_KEPT_LINE.strip()


def is_not_kept(record) -> bool:
    """Does a record -- its text, or its lines -- carry the not-kept Note?  Only the companion's own
    line counts: the same words anywhere else (a name, a Custom Island Event's text) never do."""
    lines = record.splitlines() if isinstance(record, str) else record
    return any(is_not_kept_line(line) for line in lines)
