"""New Believers' log words for the Heathens, in both wordings: the game's own and Guardians of Isola Rewrite's.

The owner (2026-11-23): "with the Guardians of Isola patch Heathens = Isolans", everywhere, the logs too.  With the
rewrite on, the companions write (native/shared/isolan_log_words.h, former_heathens.h, special_title.h):

    Arrived "How: Converted from the Isolans"            for "Converted from the Heathens"
    Death "no grave (died among the Isolans: ...)"       for "... the Heathens ..."
    "Special villager: Former Isolan (blue mask)" ...    for "Former Heathen (blue mask)" ... "Retired Isolan Chief"
    "Special villager: Esteemed Isolan Doctor" ...       the rewrite's OWN in-game names of the puzzle Heathens
                                                         (vv_guardians_role_titles, generated from its sm.xml)
    Arrived "How: Replaced an Isolan who died ..."       for "Replaced a Heathen ..."
    Island Events "  <name>: Isolan no -> yes"           for "Heathen no -> yes"
    Village Statistics "Isolans Converted: N"            for "Heathens Converted: N"

Every reader takes both, old logs included -- as LEFT_RECORDS does for "Left the tribe: became a Heathen" / "...an
Isolan" (vv_log_additions).  heathen_form() gives any of these words in the game's own (Heathen) wording, so a
reader keyed on the Heathen words reads either.
"""
from __future__ import annotations

from vv_guardians_role_titles import ROLE_TITLES

CONVERTED_HEATHENS = "Converted from the Heathens"
CONVERTED_ISOLANS = "Converted from the Isolans"
CONVERTED_HOWS = (CONVERTED_HEATHENS, CONVERTED_ISOLANS)

NO_GRAVE_HEATHENS = "no grave (died among the Heathens: nothing was left)"
NO_GRAVE_ISOLANS = "no grave (died among the Isolans: nothing was left)"

REPLACED = {
    "Replaced a Heathen who died of old age": "Replaced an Isolan who died of old age",
    "Replaced a Heathen lost in an island event": "Replaced an Isolan lost in an island event",
}

FORMER_TITLES = {
    "Former Heathen (blue mask)": "Former Isolan (blue mask)",
    "Former Heathen (orange mask)": "Former Isolan (orange mask)",
    "Former Heathen (red mask)": "Former Isolan (red mask)",
    "Former Heathen Master (purple mask)": "Former Isolan Master (purple mask)",
    "Retired Heathen Chief": "Retired Isolan Chief",
}

# The puzzle Heathens' titles, the game's own -> the rewrite's (roles 12..17).
PUZZLE_TITLES = {heathen: isolan for heathen, isolan in ROLE_TITLES.values()}

# An Island Events change line's key: "  <name>: Heathen no -> yes", or "Isolan".
CHANGE_KEYS = ("Heathen", "Isolan")

CONVERTED_ROWS = ("Heathens Converted", "Isolans Converted")

# Every Isolan word -> its Heathen word.
_TO_HEATHEN = {
    CONVERTED_ISOLANS: CONVERTED_HEATHENS,
    NO_GRAVE_ISOLANS: NO_GRAVE_HEATHENS,
    CONVERTED_ROWS[1]: CONVERTED_ROWS[0],
    **{isolan: heathen for heathen, isolan in REPLACED.items()},
    **{isolan: heathen for heathen, isolan in FORMER_TITLES.items()},
    **{isolan: heathen for heathen, isolan in PUZZLE_TITLES.items()},
}


_TO_ISOLAN = {heathen: isolan for isolan, heathen in _TO_HEATHEN.items()}


def heathen_form(text: str | None) -> str | None:
    """`text` (a log value: a title, a "How:", a grave line, a statistics row) in the game's own Heathen wording;
    anything that is not one of the Guardians of Isola words as it is."""
    if text is None:
        return None
    return _TO_HEATHEN.get(text.strip(), text)


def isolan_form(text: str) -> str:
    """The Guardians of Isola word for one of the Heathen words above (what the writers put with the rewrite on);
    anything else as it is."""
    return _TO_ISOLAN.get(text, text)