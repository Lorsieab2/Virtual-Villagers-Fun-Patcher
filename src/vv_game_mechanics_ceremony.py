"""The Remembrance Ceremony and The Rumblings in the Game Mechanics pages' island events (all five games; the owner,
2026-11-13).

One Event each per game, shown only when the exe has the patch (vvN_more_island_events).  Every rule comes from
src/vv_remembrance_ceremony.py and src/vv_the_rumblings.py, the same sources the companion's words and the tests use;
the companion (native/vvfp_more_island_events/ceremony_core.inc, ceremony_games.inc) rolls exactly these odds with
the game's own random routine.
"""
from __future__ import annotations

import vv_remembrance_ceremony as rc
import vv_the_rumblings as rb
from vv_game_mechanics_events import Event

PATCH = "vv{}_more_island_events"
SCHEDULE = ("when the game draws an island event on its own schedule (the wall clock, real-life hours; paused time "
            "does not count)")
DRAW = {
    1: "one more island event (the no-choice kind), with its own case in that draw: each case whose condition holds "
       "is equally likely, this one included",
    2: "one more single-result island event, with its own case in that draw (each of its up to ten draws is 1 in 28 "
       "plus one for each of the patcher's events that can happen, for every event, this one included)",
    3: "one more island event, listed with the others whose condition holds and drawn like them (1 in the number "
       "listed: it has its own place in the draw)",
    4: "one more island event, listed with the others whose condition holds and drawn like them (1 in the number "
       "listed: it has its own place in the draw)",
    5: "one more island event, listed with the others whose condition holds and drawn like them (1 in the number "
       "listed: it has its own place in the draw)",
}
GRAVES = {
    1: "at least one grave (the game's own count of its graves)",
    2: "at least one grave (the game's own Day of Honor test)",
    3: "at least one grave (the game's own count; its Day of Honor asks for two, this event for one)",
    4: "at least one grave (the game's own count; its Day of Honor asks for two, this event for one)",
    5: "at least one grave (the game's own count; its Day of Honor asks for two, this event for one) and The Last "
       "Heathen done -- every Heathen converted and the old hovel fixed up, which the game saves and keeps for good",
}
WHAT = {
    1: "goes to the cemetery and goes \"Honoring the Dead\"",
    2: "goes to the memorial and goes \"Honoring the Dead\" or \"Reflecting\" (50% each)",
    3: "goes to the graveyard and goes \"Honoring the Dead\" or \"Reflecting\" (50% each)",
    4: "goes to the graveyard and goes \"Honoring the Dead\"",
    5: "goes \"Honoring\" at the mausoleum",
}


def _which(game: int) -> str:
    return "the believers" if game == 5 else "everyone"


def remembrance_event(game: int) -> Event:
    subs = [
        f"Who takes part: {_which(game)} -- every living villager who is in the village, children and babies that "
        "are villagers too, nursing mothers and fathers, and the villagers other events never pick (the owner: "
        "\"everyone joins in\")" + ("; Heathens never" if game == 5 else "") + ". Babies still being carried are not "
        "villagers yet, so they stay with their mothers.",
        f"Each one stops what it is doing and {WHAT[game]}, started one by one exactly as the game's own Day of Honor "
        "starts each villager, so nobody is left out by the game's usual group rules.",
    ]
    if game == 5:
        subs.append("With the patcher's \"Memorial Actions Can Also Occur at the Heathen Hovel\": each believer "
                    f"goes to the old Heathen hovel instead {rc.HOVEL_PERCENT}% of the time, and there goes "
                    f"\"Honoring\" or \"Reflecting\" ({rc.HONOR_PERCENT}% each), the way that patch sends them; the "
                    "rest go \"Honoring\" at the mausoleum. Without it, \"Reflecting\" is never used.")
    subs += [
        f"The feast quietly uses {rc.FOOD_PER_VILLAGER} food for every villager the game counts, never below 0 (the "
        "same as Blessings Day" + (" in this game" if game in (1, 2, 3) else " in A New Home, The Lost Children and "
                                   "The Secret City") + "); the popup does not mention it.",
        "One popup with the owner's words and OK. The effects come as the popup shows; the Island Events log keeps one "
        "entry for the event. It can happen again, as likely as one stock event each time.",
    ]
    return Event(
        rc.TITLE,
        f"needs {GRAVES[game]}; {DRAW[game]}, {SCHEDULE}; added by \"More Island Events\" (without it the event does "
        "not exist)",
        tuple(subs),
        only_with=PATCH.format(game),
    )


def _names(game: int) -> str:
    names = [s[0] for s in rb.STRUCTURES[game]]
    return ", ".join(names[:-1]) + " and " + names[-1] if len(names) > 1 else names[0]


def rumblings_event(game: int) -> Event:
    lo, hi = rb.LOSS
    left = rb.LEFT_OUT[game]
    subs = [
        f"The structures it can damage: {_names(game)}."
        + (f" Never {', '.join(left)}" + (" (puzzles stay solved)." if game in (1, 2) else ".") if left else ""),
        f"Each finished one is damaged {rb.DAMAGE_PERCENT}% of the time; at least one always is (when none is, one of "
        "them, each equally likely), and every one can be.",
        f"A damaged one loses {lo} to {hi}% of its building work (each whole percent equally likely)"
        + (", counted on the work above where a new village starts it (the first two huts start part built)"
           if game == 3 else ", counted on the work above where a new village starts it (the first hut starts part "
           "built)" if game == 2 else "") + ", and the builders must build it again. At 100% it is unbuilt, exactly "
        "as in a new village" + ("; an unbuilt one can be moved" if game in (4, 5) else "") + ". A heavily damaged "
        "one may need a villager dropped on it before the builders start, as in the stock game.",
        "When it is finished again the game shows its own celebration, tip and completion message again.",
        "Solved puzzles stay solved. No one is hurt and nobody leaves: a village left over its population limit keeps "
        "everyone, babies already on the way are still born, and no new babies come until the hut is rebuilt -- the "
        "same as when the stock game runs out of room.",
    ]
    if game == 4:
        subs.append("A damaged nursery school's teacher stops teaching until it is rebuilt.")
    subs.append("One popup with the owner's words and OK. The effects come as the popup shows; the Island Events log "
                "keeps one entry for the event, naming each damaged structure. It can happen again, as likely as one "
                "stock event each time.")
    return Event(
        rb.TITLE,
        f"needs every puzzle solved ({rb.PUZZLES[game]}, the Puzzles screen's) and at least one finished structure "
        f"it can damage; {DRAW[game]}, {SCHEDULE}; added by \"More Island Events\" (without it the event does not "
        "exist)",
        tuple(subs),
        only_with=PATCH.format(game),
    )
