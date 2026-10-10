"""The questions the patcher asks when it opens (the automatic check's queue, all five games).

The owner (v1.35.66): with "Check logs automatically" on, what the records need from the player is asked
-- in the game only at the quit, and only to queue it, since a save and its logs are changed with the
game closed -- and the patcher asks it the next time it opens, each question with plain directions.  The
first is the missing last names (src/vv_last_names.py: the game's quit check writes the slot's request
file, native/shared/crosscheck_bridge.h).

HOW A FEATURE ADDS A QUESTION.  Register a Source once, at import, in the feature's own module:

    import vv_startup_questions as questions
    questions.register(questions.Source(
        "contradictions",                       # a unique name
        pending=lambda folder, game: [...],     # the slots of `folder` (game 1-5) with a question queued;
                                                # reads only, and fast: it runs for every save folder
        asker="_ask_contradictions_for",        # the patcher window's method (src/vv_fun_patcher_gui.py)
    ))

and give the patcher window (App in src/vv_fun_patcher_gui.py) that method:

    def _ask_contradictions_for(self, folder: Path, game: int, slot: int, tribe: str) -> None

which asks with the window's own dialogs (the game is closed when it is called), says in plain steps how
to do the same later from Repair Saves & Logs, and itself removes or keeps what it queued (its "Not now"
is the feature's to remember).  The patcher calls every source's pending() for each game's save folders,
in the order registered, only while "Check logs automatically" is on, and never for a folder whose game
is running.  A source whose pending() raises is skipped.  The module the source lives in must be
imported by vv_fun_patcher_gui (its "import" line is what registers it).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Source:
    name: str
    pending: Callable[[Path, int], list[int]]
    asker: str


SOURCES: list[Source] = []


def register(source: Source) -> None:
    """Add a source of questions (a second registration under the same name replaces the first)."""
    SOURCES[:] = [s for s in SOURCES if s.name != source.name] + [source]


@dataclass(frozen=True)
class Pending:
    source: Source
    folder: Path
    game: int
    slot: int


def pending(folder: Path, game: int) -> list[Pending]:
    """Every queued question of `folder`, source by source."""
    out = []
    for source in list(SOURCES):
        try:
            slots = source.pending(Path(folder), game)
        except (OSError, ValueError, UnicodeError):
            continue
        out += [Pending(source, Path(folder), game, slot) for slot in slots]
    return out
