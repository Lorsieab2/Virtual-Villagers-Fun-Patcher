"""New Believers' log words for the Heathens, in both wordings: the game's own and Guardians of Isola Rewrite's.

The owner (2026-11-23): "with the Guardians of Isola patch Heathens = Isolans", everywhere, the logs too.  With the
rewrite on, the companions write (native/shared/isolan_log_words.h, former_heathens.h, special_title.h):

    Arrived "How: Converted from the Isolans"            for "Converted from the Heathens"
    Death "no grave (died among the Isolans: ...)"       for "... the Heathens ..."
    "Special villager: Former Isolan (blue mask)" ...    for "Former Heathen (blue mask)" ... "Retired Isolan Chief"
    "Special villager: Esteemed Isolan Doctor" ...       the rewrite's OWN in-game names of the puzzle Heathens
                                                         (vv_guardians_role_titles, generated from its sm.xml)
    Arrived "How: Replaced an Isolan who died ..."       for "Replaced a Heathen ..."
    Arrived "How: Arrived at the Isolan camp [with N other(s)]"   for "... the Heathen camp ..." (v1.35.101)
    Island Events "  <name>: Isolan no -> yes"           for "Heathen no -> yes"
    Village Statistics "Isolans Converted: N"            for "Heathens Converted: N"

Every reader takes both, old logs included -- as LEFT_RECORDS does for "Left the tribe: became a Heathen" / "...an
Isolan" (vv_log_additions).  heathen_form() gives any of these words in the game's own (Heathen) wording, so a
reader keyed on the Heathen words reads either.
"""
from __future__ import annotations

import re

from vv_guardians_role_titles import ROLE_TITLES

CONVERTED_HEATHENS = "Converted from the Heathens"
CONVERTED_ISOLANS = "Converted from the Isolans"
CONVERTED_HOWS = (CONVERTED_HEATHENS, CONVERTED_ISOLANS)

NO_GRAVE_HEATHENS = "no grave (died among the Heathens: nothing was left)"
NO_GRAVE_ISOLANS = "no grave (died among the Isolans: nothing was left)"

REPLACED = {
    "Replaced a Heathen who died of old age": "Replaced an Isolan who died of old age",
    "Replaced a Heathen lost in an island event": "Replaced an Isolan lost in an island event",
    # a camp child made in the place of one who grew up (Heathen Tribe Expansion and Evolution, v1.35.101)
    "Replaced a Heathen child who grew up": "Replaced an Isolan child who grew up",
}

# Heathen Tribe Expansion and Evolution (v1.35.101; native/shared/heathen_evo.h HE_ARRIVED_*): a new Heathen's
# Arrived record, "How: Arrived at the Heathen camp", or one of a group, "... with N other(s)" (N 1 to 3); the
# rewrite's "Isolan camp".  Every such record also carries the Heathen Faction line, so no reader counts it.
ARRIVED_ALONE = {"Arrived at the Heathen camp": "Arrived at the Isolan camp"}
ARRIVED_GROUP = re.compile(r"^Arrived at the (Heathen|Isolan) camp with ([1-9]\d*) others?$")


def is_heathen_arrival(how: str | None) -> bool:
    """Whether an Arrived record's "How:" says a Heathen joined the camp (a replacement or a new arrival), in either
    wording."""
    how = (how or "").strip()
    return (how in REPLACED or how in REPLACED.values() or how in ARRIVED_ALONE or how in ARRIVED_ALONE.values()
            or ARRIVED_GROUP.match(how) is not None)

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
    **{isolan: heathen for heathen, isolan in ARRIVED_ALONE.items()},
    **{isolan: heathen for heathen, isolan in FORMER_TITLES.items()},
    **{isolan: heathen for heathen, isolan in PUZZLE_TITLES.items()},
}


_TO_ISOLAN = {heathen: isolan for isolan, heathen in _TO_HEATHEN.items()}


def heathen_form(text: str | None) -> str | None:
    """`text` (a log value: a title, a "How:", a grave line, a statistics row) in the game's own Heathen wording;
    anything that is not one of the Guardians of Isola words as it is."""
    if text is None:
        return None
    group = ARRIVED_GROUP.match(text.strip())
    if group is not None and group.group(1) == "Isolan":
        return text.strip().replace("the Isolan camp", "the Heathen camp", 1)
    return _TO_HEATHEN.get(text.strip(), text)


def isolan_form(text: str) -> str:
    """The Guardians of Isola word for one of the Heathen words above (what the writers put with the rewrite on);
    anything else as it is."""
    return _TO_ISOLAN.get(text, text)