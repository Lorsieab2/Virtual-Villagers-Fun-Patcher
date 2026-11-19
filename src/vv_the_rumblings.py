"""The Rumblings: the owner's island event for all five games (2026-11-13) -- its words and its rules.

The one source of the event's English: scripts/build_more_island_events.py writes it into the companion
(native/vvfp_more_island_events/ceremony_text.inc) and into the translation template
(data/translations/patcher_strings.json), and the Game Mechanics page reads the rules below.

THE OWNER'S TEXT, as pasted in chat (2026-11-13), unaltered: one popup, no choice, just OK.  It has no quote marks,
apostrophes or ellipses, so every game's font draws it as written.

THE OWNER'S RULES (2026-11-13, with the owner's answers of the same day):
  * when: every puzzle of that game solved (the game's own puzzle-done flags, its Puzzles screen's list) and at least
    one finished structure of STRUCTURES below;
  * a structure that is itself a puzzle is never damaged (A New Home's first hut "The Hut"; The Lost Children's
    Hospital, Sewing Hut and Lovely Hut): solved puzzles stay solved; New Believers' nursery school is left out too;
  * each finished structure is damaged with DAMAGE_PERCENT, at least one always (none drawn: one of them at random),
    every one can be; a damaged one loses LOSS (10 to 100%, each whole percent equally likely) of its building work --
    counted on the work above the game's own new-village value (The Secret City's first two huts start part built)
    -- and the builders must build it again; at 100% it is exactly as a new village has it (unbuilt; The Tree of Life
    and New Believers: it can then be moved);
  * no one is hurt, nobody leaves: a village over its limit keeps everyone and has no new births until it is rebuilt,
    as the game itself does when it runs out of room; babies already on the way are still born;
  * the rebuilt structure's own celebration, tip and completion message come again, as the game shows them;
  * the effects come as the popup shows, with one Island Events log entry; it can happen again, as likely as one
    stock event each time.
"""
from __future__ import annotations

STEM = "vvfp.more_island_events/rumblings_text"
CONTEXT = ("VVFP More Island Events.dll (the island event The Rumblings, all five games: its popup, in the game's own "
           "island-event popup)")

TITLE = "The Rumblings"
GAMES = (1, 2, 3, 4, 5)

TEXTS: tuple[tuple[str, str], ...] = (
    ("TITLE", TITLE),
    ("TEXT", "One morning, the village becomes wracked with a violent shaking. Things start flying off shelves, "
             "pottery smashes on the floor, and everyone starts taking cover under nearby structures. The villagers "
             "are frightened, but luckily, no one is hurt. A lot of loose rubble is strewn about and some structures "
             "have been visibly damaged. It looks like the builders have more work cut out for them."),
)

DAMAGE_PERCENT = 25                     # each finished structure
LOSS = (10, 100)                        # percent of its building work, inclusive, each whole percent equally likely

# Each game's structures the event may damage: (name, done at, new-village progress).  Left out: the ones that are
# puzzles (A New Home's first hut; The Lost Children's Lovely Hut, Hospital and Sewing Hut) and New Believers'
# nursery school (the owner).
STRUCTURES = {
    1: (("the second population hut", 400, 0), ("the third population hut", 600, 0)),
    2: (("the first population hut", 450, 205), ("the second population hut", 700, 0),
        ("the third population hut", 900, 0)),
    3: (("the first population hut", 2000, 1750), ("the second population hut", 2000, 400),
        ("the third population hut", 2000, 0), ("the clothing hut", 2000, 0)),
    4: (("the first population hut", 2000, 0), ("the second population hut", 2000, 0),
        ("the third population hut", 2000, 0), ("the clothing hut", 2000, 0), ("the love shack", 2000, 0),
        ("the nursery school", 2000, 0), ("the hospital", 2000, 0)),
    5: (("the first population hut", 2000, 0), ("the second population hut", 2000, 0),
        ("the third population hut", 2000, 0), ("the clothing hut", 2000, 0), ("the love shack", 2000, 0)),
}
LEFT_OUT = {
    1: ("the first population hut (\"The Hut\" puzzle)",),
    2: ("the Lovely Hut", "the Hospital", "the Sewing Hut (all three are puzzles)"),
    3: (),
    4: (),
    5: ("the nursery school",),
}
PUZZLES = {1: 16, 2: 16, 3: 16, 4: 16, 5: 11}   # the Puzzles screen's list in each game


def progress_after(done_at: int, start: int, loss: int) -> int:
    """The structure's building progress after losing `loss` percent of the work above `start`."""
    return start + (done_at - start) * (100 - loss) // 100


def forms(key: str) -> tuple[str, ...]:
    return ("",)


def english(key: str, form: str = "") -> str:
    return dict(TEXTS)[key]


def names_in(key: str) -> tuple[str, ...]:
    return ()


def stem(key: str, form: str = "") -> str:
    return f"{STEM}.{key}"


def rows() -> list[tuple[str, str, str, tuple[str, ...]]]:
    """Every (stem, key, English, names) the companion asks the translations for."""
    return [(stem(key), key, english(key), ()) for key, _ in TEXTS]
