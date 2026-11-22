"""The Remembrance Ceremony: the owner's island event for all five games (2026-11-13) -- its words and its rules.

The one source of the event's English: scripts/build_more_island_events.py writes it into the companion
(native/vvfp_more_island_events/ceremony_text.inc) and into the translation template
(data/translations/patcher_strings.json), and the Game Mechanics page reads the rules below.

THE OWNER'S TEXT, as pasted in chat (2026-11-13), unaltered: one popup, no choice, just OK.  It has no quote marks,
apostrophes or ellipses, so every game's font draws it as written.

THE OWNER'S RULES (2026-11-13, with the owner's answers of the same day):
  * when: at least ONE grave in every game (the game's own grave count, even where the stock Day of Honor asks for
    two); New Believers also needs The Last Heathen (project 25) done -- every Heathen converted and the hovel fixed
    up, saved and for good;
  * who: everyone, "everyone joins in, even children, nursing mothers. no one is left out" -- protected villagers
    included; New Believers' believers only;
  * each villager is sent on its own through the game's own action starter (the stop, then the action, as the
    game's own Day of Honor starts each one), so the stock group filters leave no one out;
  * the place and the action: the game's own honoring (and reflecting, 50% each where the game has both at that
    place) at that game's graveyard or memorial (PLACES below); New Believers: "Honoring the Dead" (behaviour 17,
    the game's own "Honoring the dead"; never bare "Honoring", the owner 2026-11-13, which is the devotees' separate
    job) at the mausoleum, or -- with the "Memorial Actions Can Also Occur at the Heathen Hovel" patch installed --
    50% the mausoleum, 50% the old Heathen hovel, where Honoring the Dead or Reflecting (50% each) go there the way
    that patch sends them;
  * the feast quietly uses 10 food for every villager the game counts, never below 0 (Blessings Day's own rule in A
    New Home, The Lost Children and The Secret City, and the same in the other two); the popup does not say it;
  * the effects come as the popup shows, with one Island Events log entry; it can happen again, as likely as one
    stock event each time.
"""
from __future__ import annotations

STEM = "vvfp.more_island_events/remembrance_text"
CONTEXT = ("VVFP More Island Events.dll (the island event The Remembrance Ceremony, all five games: its popup, in the "
           "game's own island-event popup)")

TITLE = "The Remembrance Ceremony"
GAMES = (1, 2, 3, 4, 5)

TEXTS: tuple[tuple[str, str], ...] = (
    ("TITLE", TITLE),
    ("TEXT", "Today is the Day of Remembrance. The villagers are gathering to honor those that came before them, and "
             "to thank them for all the sacrifices they have made. Throughout the day they share stories about their "
             "ancestors and loved ones, partake in a grand feast, and acknowledge that all experiences, good and bad, "
             "form parts of their future."),
)

GRAVES_AT_LEAST = 1                     # the owner: "at least ONE grave in ALL five games"
FOOD_PER_VILLAGER = 10                  # Blessings Day's own rule (A New Home 0x4280B7, The Lost Children 0x433C4C,
                                        # The Secret City 0x414D10), never below 0
HONOR_PERCENT = 50                      # where a place has both honoring and reflecting
HOVEL_PERCENT = 50                      # New Believers with the hovel patch: the hovel or the mausoleum

# Each game: (place words, the actions there).  The actions are the game's own (the starter the game's Day of Honor
# or its everyday chooser uses); the companion starts each villager on its own.
PLACES = {
    1: ("the cemetery", ("\"Honoring the Dead\"",)),
    2: ("the memorial", ("\"Honoring the Dead\"", "\"Reflecting\"")),
    3: ("the graveyard", ("\"Honoring the Dead\"", "\"Reflecting\"")),
    4: ("the graveyard", ("\"Honoring the Dead\"",)),
    5: ("the mausoleum", ("\"Honoring the Dead\"",)),
}


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
