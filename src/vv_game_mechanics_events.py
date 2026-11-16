"""Game Mechanics: every island event a game fires, with its exact odds and outcomes (the owner, 2026-10-24:
"for island events, exact odds for all outcomes and specifics on outcomes; also for VV2 Gong of Wonder").

Each game's catalog is in src/vv_game_mechanics_events_vv<N>.py, read from that game's stock executable
(inputs\\vvN-stock-copy; research\\stock-executables): the scheduler, the event table and its conditions, and
each popup's buttons and results, with the addresses in the catalog's comments.  An event the game never fires
(an inherited or developer-dead one) is never listed (the owner, 2026-10-09); one a patch adds is listed only when
that patch is in the game's exe.

THE CATALOG.  A game's module has
    RULES:  tuple of Line   -- how an event is chosen (timer, families, weights), shown first;
    EVENTS: tuple of Event  -- one parent bullet per event, its choices and results as sub-bullets;
    EXTRA:  tuple of (heading Event, ...) groups shown after the events (The Lost Children's Gong of Wonder).
A Line's or Event's `verified` is what stands behind it (vv_game_mechanics.Fact.verified): RUNNING for a rule
read from the game's own reachable code (the owner, 2026-10-24: static tracing of reachable code counts, as
does an emulation or the owner's word), False (shown UNCONFIRMED) for an estimate or anything not proven.

WORDS.  A choice is the popup's own button text, in quotes; an amount of food or tech points is written with
thousands separators (so the general rules page keeps it: vv_game_mechanics.general drops a line with a bare
year-like number); every time names its clock (real-life, or the game's clock), every age says age units and
villager years.

PATCHES (the owner, 2026-10-24): a patch is named only where it changes an odd or an outcome shown, and only
when it is in the game's exe (Village.has is True): the normal game's value is the line itself, then
"With the patcher's "<patch>" (in this game): ...".  A patch that is not in the exe, or not known to be, is not
mentioned.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field

import vv_game_mechanics as gm

GROUP = "Island events"
ROOM = "Room for new villagers"           # a rule line the exe's population mode adds to (life.room_words)


@dataclass(frozen=True)
class Line:
    """One bullet: `text`, and what stands behind it."""
    text: str
    verified: bool | str = gm.RUNNING
    sub: bool = False
    only_with: str | None = None            # shown only when this patch is in the exe


@dataclass(frozen=True)
class Event:
    """One event (or a heading such as the Gong of Wonder): its title as the game shows it, how it is chosen and
    what it needs, and its choices and results.  `patched`: (patch id, what it changes) for each patch that
    changes this event, shown only when that patch is in the exe.  `only_with`: an event a patch adds."""
    title: str
    text: str
    subs: tuple = ()                        # each a str (RUNNING) or a Line
    verified: bool | str = gm.RUNNING
    patched: tuple = ()
    only_with: str | None = None


def scale_population_id(game: int) -> str:
    """Island Events Scale With Population (like The Lost Children): A New Home, The Tree of Life, New Believers."""
    return f"vv{game}_island_events_scale_with_population"


def scale_stored_id(game: int) -> str:
    """Island Events Scale With Stored Food and Tech Points, its alternative."""
    return f"vv{game}_island_events_scale_with_stored_amounts"


def scaling_rules(game: int, people: str) -> tuple[Line, Line]:
    """The two rules lines that define the patches' factor k and the stored-amount rule (each shown only with its
    patch); `people` says who counts, as the game's own count for room does."""
    return (
        Line("With the patcher's \"Island Events Scale With Population (like The Lost Children)\" (in this game): "
             "each food and tech-point amount of the events marked so is multiplied by k, as in The Lost Children's "
             f"two-choice events: k is 1 up to 25 people, 2 up to 50, 3 above ({people}). A rolled amount is "
             "multiplied after the roll; a loss still takes no more than there is.",
             only_with=scale_population_id(game)),
        Line("With the patcher's \"Island Events Scale With Stored Food and Tech Points\" (in this game): each food "
             "and tech-point amount of the events marked so becomes the game's amount plus a tenth of the food (for "
             "food) or of the tech points (for tech points) stored at that moment, rounded down, and never less than "
             "the game's amount; a loss grows the same way and still takes no more than there is.",
             only_with=scale_stored_id(game)),
    )


def with_scaling(game: int, events: tuple, titles: frozenset) -> tuple:
    """`events` with both patches' marks on each event titled in `titles` (every title must be there)."""
    import dataclasses
    missing = titles - {event.title for event in events}
    if missing:
        raise ValueError(f"island events scale: no such event {sorted(missing)}")
    marks = ((scale_population_id(game), "its food and tech-point amounts are multiplied by k (1 up to 25 people, "
                                         "2 up to 50, 3 above; see the rules above)"),
             (scale_stored_id(game), "its food and tech-point amounts each gain a tenth of what is stored (see the "
                                     "rules above)"))
    return tuple(dataclasses.replace(event, patched=tuple(event.patched) + marks) if event.title in titles else event
                 for event in events)


# More Frequent Island Events (all five games): the game's own wait between events, rand(K) + K whole real-life
# hours (scripts/build_island_frequency_features.py), divided by the patcher window's N.
FREQUENCY_HOURS = {1: 12, 2: 10, 3: 8, 4: 8, 5: 8}
TIMING = "Timing:"


def frequency_id(game: int) -> str:
    """More Frequent Island Events, in all five games."""
    return f"vv{game}_more_frequent_island_events"


def frequency_multiplier(village) -> int | None:
    """The N the game's "VVFP Island Frequency.txt" holds (beside its companion, in the patcher's folder next to the
    game's exe), read as the companion reads it: 2 to 100 (above 100 is 100, below 2 is 2), 2 with no number;
    None when the exe is not known or the file cannot be read."""
    import patcher_files
    from pathlib import Path
    exe = getattr(village, "exe", None)
    if exe is None:
        return None
    try:
        raw = (Path(exe).parent / patcher_files.PATCHER_FILES_FOLDER / "VVFP Island Frequency.txt").read_bytes()[:15]
    except OSError:
        return None
    text = raw.decode("latin-1").lstrip(" \t")
    digits = ""
    for ch in text:
        if not ("0" <= ch <= "9"):
            break
        digits += ch
    if not digits:
        return 2
    return max(2, min(100, int(digits[:4])))


def _span(seconds: int) -> str:
    """A wait in plain words: whole hours and minutes (seconds only under a minute)."""
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    parts = []
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if secs and not hours:
        parts.append(f"{secs} second{'s' if secs != 1 else ''}")
    return " ".join(parts) or "0 seconds"


def frequency_words(village) -> str:
    """The timing line's patched sub-line: the shortened wait, at the game's own N when it can be read."""
    game = village.game
    k = FREQUENCY_HOURS[game]
    n = frequency_multiplier(village)
    if n is None:
        effect = (f"each wait after an event ({k} to {2 * k - 1} hours) is divided by the number set on its slider "
                  "(2 to 100), so the game's own events come that many times as often; the first events' minutes "
                  "are unchanged")
    else:
        effect = (f"the game's own events come {n} times as often: the wait after an event is "
                  f"{_span(k * 3600 // n)} to {_span((2 * k - 1) * 3600 // n)} of real-life time instead of {k} to "
                  f"{2 * k - 1} hours (each of the {k} waits as likely); the first events' minutes are unchanged")
    return patched_words(frequency_id(game), effect)


def _line(item) -> Line:
    return item if isinstance(item, Line) else Line(item)


def patched_words(feature: str, effect: str) -> str:
    """The owner's form for a patch that changes a value shown: the normal game's value is said first."""
    return f"With the patcher's \"{gm.feature_name(feature)}\" (in this game): {effect}"


def event_facts(village: gm.Village, rules=(), events=(), extra=()) -> list[gm.Fact]:
    """The Island events group: the rules, then one parent bullet per event with its sub-bullets."""
    out: list[gm.Fact] = []

    def shown(only_with: str | None) -> bool:
        return only_with is None or village.has(only_with) is True

    for item in rules:
        line = _line(item)
        if shown(line.only_with):
            out.append(gm.Fact(GROUP, line.text, line.verified, sub=line.sub))
            if line.text.startswith(TIMING) and village.game in FREQUENCY_HOURS \
                    and village.has(frequency_id(village.game)) is True:
                out.append(gm.Fact(GROUP, frequency_words(village), gm.CODE, sub=True))
            if line.text.startswith(ROOM):
                import vv_game_mechanics_life as life       # the limit this game's exe gives (its population mode)
                words = life.room_words(village)
                if words:
                    out.append(gm.Fact(GROUP, words, gm.CODE, sub=True))
    for event in tuple(events) + tuple(extra):
        if not shown(event.only_with):
            continue
        head = f"{event.title} -- {event.text}" if event.text else event.title
        out.append(gm.Fact(GROUP, head, event.verified))
        for item in event.subs:
            line = _line(item)
            if shown(line.only_with):
                out.append(gm.Fact(GROUP, line.text, line.verified, sub=True))
        for feature, effect in event.patched:
            if village.has(feature) is True:
                out.append(gm.Fact(GROUP, patched_words(feature, effect), gm.RUNNING, sub=True))
    return out


def facts(village: gm.Village) -> list[gm.Fact]:
    """The game's island-event catalog as Facts (none when the game has no catalog module)."""
    try:
        module = importlib.import_module(f"vv_game_mechanics_events_vv{village.game}")
    except ImportError:
        return []
    return (event_facts(village, getattr(module, "RULES", ()), getattr(module, "EVENTS", ()),
                        getattr(module, "EXTRA", ()))
            + collection_facts(village))


def collection_facts(village: gm.Village) -> list[gm.Fact]:
    """The Isola Grand Event Collection's lines (src/vv_game_mechanics_collection.py), with its patch only."""
    import vv_game_mechanics_collection as collection
    return collection.facts(village)


def share(percent: float, count: int) -> str:
    """`percent` shared equally by `count` events, to two decimals: "2.86%"."""
    return f"{percent / count:.2f}%"
