"""The Aspiring Adventurer in the Game Mechanics pages' island events (all five games; the owner, 2026-11-12).

One Event per game, shown only when the exe has the patch (vvN_more_island_events).  Every number comes from
src/vv_aspiring_adventurer.py, the same source the companion's words and the tests use; the companion
(native/vvfp_more_island_events/adv_core.inc) rolls exactly these odds with the game's own random routine.
"""
from __future__ import annotations

import vv_aspiring_adventurer as adv
import vv_cave_explorers as cave
import vv_the_climb as climb
from vv_game_mechanics_events import Event, Line

TITLE = adv.TITLE

NOT_SPECIAL = {
    1: "not the Golden Child",
    2: "not an Esteemed Elder's totem statue",
    3: "not the Tribal Chief",
    4: "not a body or a ghost",
    5: "a believer (never a Heathen), not the chief, the Retired Chief or another of the special roles the game's own "
       "picker skips, and not a Reanimated spirit",
}
# The owner's protected villagers (2026-11-13; native/vvfp_more_island_events/adv_core.inc adv_is_protected): never
# picked by any of these events, whatever the role.
PROTECTED = {
    1: "the Golden Child",
    2: "an Esteemed Elder's totem statue",
    3: "the Tribal Chief",
    4: "a body or a ghost",
    5: "a Reanimated spirit, and the chief, the Retired Chief and the other roles the game's own island events never "
       "pick",
}


def never_picked(game: int) -> str:
    """The owner's protected villagers in plain words (the same for every role of every event of the game)."""
    return (f"Never picked, in any role (the owner's protected villagers): a nursing mother or father, "
            f"{PROTECTED[game]}, and anyone the game's own island events never pick. Everyone else may be picked "
            "(titles, Esteemed Elders who are not statues, founders and the like included).")
HOW = {
    1: "one more of the villager encounters (the two-choice island events): when an encounter is drawn, this event is "
       "1 in m + 1 (1 in m + 2 while The Cave Explorers can happen too), m the encounters possible at that moment, "
       "like each of them; never the village's first island event (always a visitor)",
    2: "one more two-choice island event (family A) with its own slot in the draw: each of family A's draws is 1 in "
       "23 for each event, this one included (the draw is one wider for The Climb, which has its own slot too); never "
       "the village's first island event",
    3: "one more island event: listed with the others whose condition holds and drawn like them (1 in the number "
       "listed), at the game's usual times",
    4: "one more island event: listed with the others whose condition holds and drawn like them (1 in the number "
       "listed), at the game's usual times",
    5: "one more island event: listed with the others whose condition holds and drawn like them (1 in the number "
       "listed), at the game's usual times",
}
REWARD = {
    1: "as drawn (scaled only with Island Events Scale ticked: below)",
    2: "times the game's own two-choice factor: x1 up to 25 villagers, x2 up to 50, x3 above",
    3: "times m, the game's own multiplier for its events (the villagers it counts, divided by 20, plus 1)",
    4: "as drawn (scaled only with Island Events Scale ticked: below)",
    5: "as drawn (scaled only with Island Events Scale ticked: below)",
}
FOOD_WRITER = {4: " (the game's own food writer then raises food by half at Food Mastery level 2 and doubles it at "
                  "level 3, as for its own events)",
               5: " (the game's own food writer then raises food by half at Food Mastery level 2 and doubles it at "
                  "level 3, as for its own events)"}


def reward_line(game: int) -> str:
    """The Aspiring Adventurer's reward in plain words (the owner, 2026-11-12: a random award, scaling)."""
    return (f"The reward is a random amount, each equally likely: {adv.award_words(game, 'food')} for the meat, "
            f"{adv.award_words(game, 'tech')} for the chest -- from the smallest to the largest food or tech-point "
            "gain of the game's own island events -- given only in A1, A5 and A8 through the game's own food or tech "
            f"writer{FOOD_WRITER.get(game, '')}, {REWARD[game]}.")
JOINS = {
    5: "becomes a Heathen through the game's own conversion (\"...joined the Isolans' tribe\" with Guardians of Isola, "
       "\"...the heathens' tribe\" without)",
}


def _pct(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text + "%"


def adventurer_event(game: int) -> Event:
    feature = f"vv{game}_more_island_events"
    who = "alive and present, 14 villager years or more, not nursing a baby (mother or father)"
    if NOT_SPECIAL[game]:
        who += ", " + NOT_SPECIAL[game]
    chances = adv.outcome_chances()
    a, b = chances["A"], chances["B"]
    joins = JOINS.get(game, "joins another tribe: gone for good, no grave")
    subs = [
        f"Who: the adventurer is drawn from the villagers who are {who}, each equally likely; the friend of ending A8 "
        "is drawn the same way from the others (never the adventurer). The event needs two such villagers, so in "
        "play the friend always exists and A8 is always possible.",
        never_picked(game),
        "\"Go investigate!\" (one popup with the opening and the find, then one with the ending): the find is a pile "
        "of dirt 50%, meat 25% (a food award) or a golden chest of artifacts 25% (a tech-point award); then 50% a "
        "surviving ending and 50% a deadly one, each equally likely within its half.",
        "After the dirt: A7 (home safe) 25%, A9 (laughs it off) 25%; A2, A3, A4, A6 12.5% each. After the meat or "
        "the chest: A1 (gets away), A5 (escapes the trap), A8 (a friend comes to help) 16.67% each (1 in 6), each "
        "with the reward; A2, A3, A4, A6 12.5% each, no reward.",
        f"Out of every investigation: A1 {_pct(a['A1'])}, A5 {_pct(a['A5'])}, A8 {_pct(a['A8'])} (each half with "
        f"food, half with tech points); A7 {_pct(a['A7'])}; A9 {_pct(a['A9'])}; A2 (the beast, dies, a grave) "
        f"{_pct(a['A2'])}; A3 (the beast, disappears, no grave) {_pct(a['A3'])}; A4 (the knife, dies, a grave) "
        f"{_pct(a['A4'])}; A6 (the knife, disappears, no grave) {_pct(a['A6'])}. In all: home safe 50% (12.5% with "
        "the food, 12.5% with the tech points, 25% with nothing), dies 25%, disappears 25%. The stranger of A4 and A6 "
        "is a man or a woman, 50% each.",
        "\"Stay on the safe path\" (one popup with the walk home; when lost, a second with the ending; after the "
        f"healers, a third): home safe {_pct(b['HOME'])}; lost {adv.LOST_PERCENT}%, then each of the six lost "
        "endings 1 in 6.",
        f"Lost ending 1, brought to the healers, then 1 in 3 each: dies, a grave ({_pct(b['H1'])}); a full recovery "
        f"({_pct(b['H2'])}); disabled -- health set to 10 to 50 (each equally likely) and now dislikes running "
        f"({_pct(b['H3'])}).",
        f"Lost ending 2 ({_pct(b['L2'])}): {joins}. Lost ending 3 ({_pct(b['L3'])}): the survivalist gains 20 to 30 "
        "points (each equally likely) in Farming, Building, Research or Healing (1 in 4 each), up to 100. Lost "
        f"endings 4 (a fallen tree) and 5 (a stony cliff), {_pct(b['L4'])} each: dies, a grave. Lost ending 6 "
        f"({_pct(b['L6'])}): disappears, no grave.",
        f"In all, staying on the path: home alive {_pct(b['HOME'] + b['L3'] + b['H2'] + b['H3'])}, dies "
        f"{_pct(b['H1'] + b['L4'] + b['L5'])}, disappears {_pct(b['L6'])}, "
        + ("becomes a Heathen " if game == 5 else "joins another tribe ") + f"{_pct(b['L2'])}.",
        reward_line(game),
        "A death is the game's own (\"Unknown causes\", as the game's own island events give; the body is buried and "
        "gets a grave); a disappearance takes the villager with no body and no grave, and the Deaths log records it "
        "as a disappearance. The effects wait for their own page: they come when the page that ends the ending's "
        "text is shown, and the Island Events log keeps one entry for the event, with the answer and every change.",
    ]
    if game in (1, 4, 5):
        subs.append(Line("With the patcher's \"Island Events Scale With Population (like The Lost Children)\" (in this "
                         "game): the reward is multiplied by k (1 up to 25 people, 2 up to 50, 3 above; see the rules "
                         "above).", only_with=f"vv{game}_island_events_scale_with_population"))
        subs.append(Line("With the patcher's \"Island Events Scale With Stored Food and Tech Points\" (in this "
                         "game): the reward gains a tenth of what is stored (see the rules above).",
                         only_with=f"vv{game}_island_events_scale_with_stored_amounts"))
    return Event(
        TITLE,
        f"needs at least two villagers who are {who}; {HOW[game]}; added by \"More Island Events\" (without it the "
        "event does not exist)",
        tuple(subs),
        only_with=feature,
    )


def cave_explorers_event() -> Event:
    """The Cave Explorers (A New Home only; the owner, 2026-11-12): every number from src/vv_cave_explorers.py, the
    rewards from src/vv_aspiring_adventurer.py's ranges; the companion (native/vvfp_more_island_events/cave_core.inc)
    rolls exactly these odds with the game's own random routine."""
    c = cave.outcome_chances()
    p, run, ret, keep = c["PROCEED"], c["RUN"], c["RETURN"], c["KEEP"]
    who = ("alive and present, 18 villager years or more, not nursing a baby (mother or father), not the Golden "
           "Child")
    subs = [
        f"Who: two villagers who are {who}, at most {cave.MAX_AGE_GAP_YEARS} villager years apart (name1 and name2: "
        "every such pair equally likely, either way round).",
        never_picked(1),
        "Three questions in a row in the encounter's own popup, each after its pages: \"Explore the Cave\" or "
        "\"Don't explore\"; then \"Proceed Further\" or \"Stay Here\"; then, depending on the way, \"Run towards the "
        "left path\" or \"Run towards the right path\" (the same odds either way), or \"You're right, I'll return "
        "them.\" or \"Curses schmurses. I'm keeping them.\"",
        "After \"Don't explore\" nothing happens.",
        f"After \"Proceed Further\", {_pct(p['A'])} a scream in the dark (A), {_pct(100 - p['A'])} a find (B). In A the "
        "one who screams is name1 or name2 (1 in 2) and what they felt one of four (1 in 4 each); then they run: "
        f"they argue {_pct(run['ARGUE'])} (nothing happens), they make up {_pct(run['MAKEUP'])} (nothing happens), "
        f"or the chasm {_pct(run['CHASM'])}: both disappear, gone for good, no grave and no food from the berries.",
        f"In B the finder is name1 or name2 (1 in 2) and the find is a map {cave.B_FINDS['FIND_MAP']}% (both leave "
        "for a strange place: they disappear, no grave), gold coins "
        f"{cave.B_FINDS['FIND_COINS']}% ({adv.award_words(1, 'tech')}), a treasure map "
        f"{cave.B_FINDS['FIND_TREASURE']}% (a huge award, three times: {adv.award_words(1, 'tech', 'huge')}) or "
        f"preserved food {cave.B_FINDS['FIND_FOOD']}% (a large award, twice: {adv.award_words(1, 'food', 'large')}). "
        f"Out of every \"Proceed Further\": the map {_pct(p['FIND_MAP'])}, the coins {_pct(p['FIND_COINS'])}, the "
        f"treasure map {_pct(p['FIND_TREASURE'])}, the food {_pct(p['FIND_FOOD'])}, and in A the chasm "
        f"{_pct(p['A'] * run['CHASM'] / 100)}.",
        f"\"Stay Here\", then \"You're right, I'll return them.\": food {_pct(ret['RETURN_FOOD'])} "
        f"({adv.award_words(1, 'food')}) or tech points {_pct(ret['RETURN_TECH'])} ({adv.award_words(1, 'tech')}).",
        f"After \"Curses schmurses. I'm keeping them.\", the researchers {_pct(keep['KEEP_RESEARCH'])} "
        f"({adv.award_words(1, 'tech')}); both die {_pct(keep['KEEP_BOTH'])} (name2, then name1: two graves); only "
        f"name2 dies {_pct(keep['KEEP_ONE'])} (one grave).",
        "Each amount is drawn, each equally likely, from the smallest to the largest food or tech-point gain of the "
        "game's own island events (a large award twice that, a huge one three times), given through the game's own "
        "food or tech writer; with Island Events Scale ticked it is then scaled as that patch scales the game's own "
        "encounters (below).",
        "A death is the game's own (\"Unknown causes\", as the game's own island events give; the body is buried and "
        "gets a grave); a disappearance takes the villager with no body and no grave, and the Deaths log records it "
        "as a disappearance. The effects wait for their own page: they come when the page that ends the ending's "
        "text is shown; the Island Events log keeps one entry for the event, with each answer clicked and every "
        "change.",
        Line("With the patcher's \"Island Events Scale With Population (like The Lost Children)\" (in this game): "
             "each award is multiplied by k (1 up to 25 people, 2 up to 50, 3 above; see the rules above).",
             only_with="vv1_island_events_scale_with_population"),
        Line("With the patcher's \"Island Events Scale With Stored Food and Tech Points\" (in this game): each award "
             "gains a tenth of what is stored (see the rules above).",
             only_with="vv1_island_events_scale_with_stored_amounts"),
    ]
    return Event(
        cave.TITLE,
        "needs The Cave puzzle done (the Golden Child has opened the cave) and two villagers who are " + who
        + f", at most {cave.MAX_AGE_GAP_YEARS} villager years apart; one more of the villager encounters: when an "
        "encounter is drawn, this event is 1 in m + 1 (1 in m + 2 while The Aspiring Adventurer can happen too), m "
        "the encounters possible at that moment, like each of them; never the village's first island event; added by "
        "\"More Island Events\" (without it the event does not exist)",
        tuple(subs),
        only_with="vv1_more_island_events",
    )


def the_climb_event() -> Event:
    """The Climb (The Lost Children only; the owner, 2026-11-12): every number from src/vv_the_climb.py, the award from
    src/vv_aspiring_adventurer.py's ranges; the companion (native/vvfp_more_island_events/climb_core.inc) rolls exactly
    these odds with the game's own random routine."""
    c = climb.outcome_chances()
    lo, hi = climb.ADVICE_GAIN
    who = (f"alive and present, {climb.ADULT_YEARS} villager years or more, with a Research of "
           f"{climb.RESEARCH_TRAINEE} or more (the game's own \"Trainee\" level: below {climb.RESEARCH_TRAINEE} the "
           "Details screen says \"Untrained\"), not nursing a baby (mother or father), not an Esteemed Elder's totem "
           "statue")
    subs = [
        f"Who: a villager who is {who}; one such villager is enough, and the villager is drawn among them, each "
        "equally likely; anyone younger or below Trainee in Research never climbs.",
        never_picked(2),
        "One question in the game's own two-choice popup: \"Go with the plan\" or \"Follow the scientists' "
        "advice\".",
        f"\"Go with the plan\" (its page, then the climb): the fall {c['PLAN']['FALL']:g}% or the summit "
        f"{c['PLAN']['SUMMIT']:g}%.",
        "The fall: the villager dies, the game's own death (\"Unknown causes\", as the game's own island events "
        "give; the body is buried and gets a grave).",
        f"The summit: the villager's Research becomes {climb.RESEARCH_MAX} (the game's maximum); the village gains a "
        "large tech award -- twice a normal one (a normal one is drawn, each amount equally likely, from "
        f"{adv.award_words(2, 'tech')}): {adv.award_words(2, 'tech', 'large')} -- times the game's own two-choice factor (x1 up to 25 villagers, x2 "
        "up to 50, x3 above), through the game's own tech writer; and the village celebrates as in the game's own Old "
        "Friends event (every living villager of 14 or more who is not sick and does not dislike crowds goes "
        "\"Celebrating\"). \"Distinguished Scientist\" is the story's words only: no title is given.",
        f"\"Follow the scientists' advice\" gives +{lo} to {hi} Research (each equally likely), at most "
        f"{climb.RESEARCH_MAX}; nothing else happens.",
        "The effects wait for their own page: the fall's, the summit's and the advice's come when the page that ends "
        "that text is shown (never on the plan's page); the Island Events log keeps one entry for the event, with the "
        "answer and every change.",
    ]
    return Event(
        climb.TITLE,
        "needs one villager who is " + who + "; " + "one more two-choice island event (family A) with its own slot in "
        "the draw: each of family A's draws is 1 in 23 for each event, this one included; never the village's first "
        "island event; added by \"More Island Events\" (without it the event does not exist)",
        tuple(subs),
        only_with="vv2_more_island_events",
    )
