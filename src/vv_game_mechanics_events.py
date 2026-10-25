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
year-like number); every time says real-life or game time, every age says age units and villager years.

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
    return event_facts(village, getattr(module, "RULES", ()), getattr(module, "EVENTS", ()),
                       getattr(module, "EXTRA", ()))


def share(percent: float, count: int) -> str:
    """`percent` shared equally by `count` events, to two decimals: "2.86%"."""
    return f"{percent / count:.2f}%"
