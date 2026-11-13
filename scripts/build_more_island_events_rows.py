"""The five rows of "More Island Events" (vvN_more_island_events): The Aspiring Adventurer (all five games), The Cave
Explorers (A New Home) and The Climb (The Lost Children), written by scripts/build_more_island_events.py.  The sites are the companion's own
(native/vvfp_more_island_events: adv_vv1.inc, adv_vv2.inc, adv_vv345.inc; tests/test_aspiring_adventurer.py pins the
two together)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import vv_aspiring_adventurer as adv  # noqa: E402


def reward_words(game: int) -> str:
    return f"{adv.award_words(game, 'food')} for the meat, {adv.award_words(game, 'tech')} for the chest"


CAVE_DESCRIPTION = (
    " And The Cave Explorers (A New Home only): once The Cave puzzle is done, two friends of 18 or more, at most 5 "
    "years apart, wonder what the cave hides. \"Don't explore\" changes nothing; \"Explore the Cave\" leads on: "
    "\"Proceed Further\" brings a scream in the dark (they run, then argue, make up, or both fall down a chasm and are "
    "gone for good, 1 in 10) or a find (a map that takes both away for good, 1 in 10; gold coins: tech points; a "
    "treasure map: three times as many; preserved food: twice the food); \"Stay Here\" lets them return what they "
    "found (food or tech points) or keep it (the researchers' tech points 8 times in 10; otherwise one or both die, "
    "with graves). Each award is a random amount from the smallest to the largest food or tech-point gain of the "
    "game's own island events (A New Home: " + adv.award_words(1, "food") + ", " + adv.award_words(1, "tech")
    + "), scaled as the Aspiring Adventurer's is.")
CAVE_BEHAVIOUR = (
    "The Cave Explorers (A New Home): one more encounter like The Aspiring Adventurer (with both possible, each is 1 in "
    "m + 2), only while The Cave puzzle is done (world byte +0x9FA8) and two villagers who may go on The Aspiring "
    "Adventurer are 18 or more (360 age units) and at most 5 years (100 age units) apart; the pair is drawn among those "
    "ordered pairs. Three questions in the encounter dialog: the answers are given new words (the constructor's own "
    "text setter 0x4015A0) and centred again (the buttons' own size and move). Explore -> Proceed Further: 50% A (10% "
    "argue, 80% make up, 10% the chasm: both removed with no body), 50% B (10% a map: both removed with no body; 30% "
    "gold coins a normal tech award, 30% a treasure map 3x, 30% preserved food 2x food); Stay Here -> return (food or "
    "tech, 50/50, a normal award) or keep (50% the researchers' normal tech award, 25% name2 and name1 die, 25% name2 "
    "dies: health 0, a body and a grave). The effects wait for their own page: they are made when the page that ends "
    "the ending's text is shown, and the event writes its own one Island Events log entry with a Choice line for each "
    "answer clicked; each removal is told to the Cause of Death companion (VvfpCauseVanishedBy).")

CLIMB_DESCRIPTION = (
    " And The Climb (The Lost Children only): a villager of 18 or more who is at least a Trainee in Research (20 or "
    "more) wants to climb the Great Falls. \"Go with the plan\": half the time they fall and die (a grave); half "
    "the time they reach the top -- their Research becomes the game's maximum (100), the village gains a large tech "
    "award (twice a normal one: " + adv.award_words(2, "tech", "large") + ", then the game's own factor) and "
    "everyone celebrates. \"Follow the scientists' advice\": +10 to 20 Research (at most 100). One villager who "
    "may go is enough; it has its own slot among the two-choice events.")
CLIMB_BEHAVIOUR = (
    "The Climb (The Lost Children): its own slot in family A's draw, 22 of rand(23) (The Aspiring Adventurer 21; each "
    "1 in 23 a draw, like each stock event), kept only while a villager who may go on The "
    "Aspiring Adventurer is 18 or more (360 age units) with Research +0x7F4 of 20 or more (the game's own \"Trainee\" "
    "level, 0x429C3D); the villager is drawn among them. \"Go with the plan\": 50% the fall (health 0: a body and a "
    "grave), 50% the summit (Research set to the game's cap 100, 0x4212F4; a large tech award, twice a normal one, "
    "through the family-A tech writer 0x426290 after the two-choice factor 0x41F720; the game's own village "
    "celebration 0x45D7D0 with Old Friends' place 0x18). \"Follow the scientists' advice\": +10 to 20 Research, at "
    "most 100. The effects wait for their own page: they are made when the page that ends the ending's text is "
    "shown, and the event writes its own one Island Events log entry (VvfpIslandEventsGraphBegin / End / Write).")

DLL_NAME = "VVFP More Island Events.dll"
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"
NAME = "More Island Events"
CLASSIC = (4, 5)

# (va, stock bytes, written, what) per game.
SITES = {
    1: (
        (0x4189F2, "E829FFFFFF", "E8XXXXXXXX",
         "the encounter setup 0x4189E0's call of its roller 0x418920: the companion draws rand(m + k), m the "
         "encounters the roller would accept now and k the events that can happen (The Aspiring Adventurer, The "
         "Cave Explorers): a draw of m or more is one of them, each 1 in m + k; else it calls the roller as before"),
        (0x41939D, "0F87D70F0000", "E9XXXXXXXX90",
         "the answer's resolve 0x419380, past its stock kinds (ja 0x41A37A): the event's own kind is answered by the "
         "companion (the effects and the first result page, or The Cave Explorers' next question); every other kind "
         "goes on as before"),
        (0x41A3EE, "E8BD25FFFF", "E8XXXXXXXX",
         "OK's close in the encounter click handler 0x41A3D0: while the event has a page left it is shown instead"),
        (0x41A87C, "E8FF02FFFF", "E8XXXXXXXX",
         "the encounter constructor's attaching of its second answer: a question of more than one page starts on its "
         "first page, with OK"),
    ),
    2: (
        (0x41F792, "E8D9FDFFFF", "E8XXXXXXXX",
         "family A's setup 0x41F780's call of its chooser 0x41F570: for that one run the draw's call 0x41F59D (the "
         "game's rand, or Story / Cheat Upgrades' own roll) is pointed into the companion and put back after, so the "
         "draw is one wider for each event past the first: rand(23) -- the only way to widen it without writing "
         "Story / Cheat Upgrades' own site for good (it installs later and checks the stock bytes there)"),
        (0x41F5AC, "0F87E4000000", "0F87XXXXXXXX",
         "family A's draw 0x41F570: its draw 21 (never kept in the stock game) is kept for The Aspiring Adventurer and "
         "22 for The Climb, each when it can happen -- each 1 in 23 a draw, like each stock event"),
        (0x41F7A0, "0F87620C0000", "0F87XXXXXXXX",
         "family A's setup 0x41F780, past its jump table: the events' 21 and 22 are set up by the companion"),
        (0x4204CE, "0F87831D0000", "0F87XXXXXXXX",
         "family A's resolve 0x4204B0, past its jump table: the events' 21 and 22 are answered by the companion (the "
         "first result page; the effects wait for their own page)"),
        (0x42230E, "E87DB0FEFF", "E8XXXXXXXX",
         "OK's close in family A's click handler 0x4222F0: while the event has a page left it is shown instead (the "
         "ending's last page makes its effects)"),
        (0x42F1A3, "E8D831FFFF", "E8XXXXXXXX",
         "the trigger's call of family A's constructor 0x422380: after it, a question of more than one page starts on "
         "its first page, with OK"),
    ),
    3: (
        (0x419B6E, "83FE3A7CE1", "E9XXXXXXXX",
         "the selector 0x419B30's loop end over the event table 0x4B3C78 (slots 1-57): the event, in slot 0, is "
         "listed after them when it can happen, so it is drawn like any listed event"),
        (0x419A18, "8B4E508B01", "E9XXXXXXXX",
         "the event dialog's click handler 0x419A00, OK: while the event has a page left it is shown instead"),
        (0x419BEA, "E801F7FFFF", "E8XXXXXXXX",
         "the selector's call of the dialog constructor 0x4192F0: after it, a question of more than one page starts on "
         "its first page, with OK"),
    ),
    4: (
        (0x418070, "83FE327CDB", "E9XXXXXXXX",
         "the selector 0x418000's loop end over the event table 0x4CCA28 (slots 1-49): the event, in slot 0, is "
         "listed after them when it can happen, so it is drawn like any listed event"),
        (0x417EB8, "8B4E508B01", "E9XXXXXXXX",
         "the event dialog's click handler 0x417EA0, OK: while the event has a page left it is shown instead"),
        (0x418106, "E885F6FFFF", "E8XXXXXXXX",
         "the selector's call of the dialog constructor 0x417790: after it, a question of more than one page starts on "
         "its first page, with OK"),
    ),
    5: (
        (0x4188E0, "83FE387CDB", "E9XXXXXXXX",
         "the selector 0x418870's loop end over the event table 0x4DC850 (slots 1-55): the event, in slot 0, is "
         "listed after them when it can happen, so it is drawn like any listed event"),
        (0x418738, "8B4E508B01", "E9XXXXXXXX",
         "the event dialog's click handler 0x418720, OK: while the event has a page left it is shown instead"),
        (0x41896A, "E8B1F6FFFF", "E8XXXXXXXX",
         "the selector's call of the dialog constructor 0x418020: after it, a question of more than one page starts on "
         "its first page, with OK"),
    ),
}

WHO_NOT = {
    1: "the Golden Child",
    2: "an Esteemed Elder's totem statue",
    3: "the Tribal Chief",
    4: "a body or a ghost",
    5: "a Heathen, the chief, the Retired Chief or another of the special roles the game's own picker skips, or a "
       "Reanimated spirit",
}
JOINS = {
    1: "joins another tribe (gone for good, no grave)",
    2: "joins another tribe (gone for good, no grave)",
    3: "joins another tribe (gone for good, no grave)",
    4: "joins another tribe (gone for good, no grave)",
    5: "becomes a Heathen, the game's own conversion (\"the Isolans' tribe\" with Guardians of Isola, else \"the "
       "heathens' tribe\")",
}
SCALE = {
    1: "with Island Events Scale With Population or With Stored Food and Tech Points ticked, the amount scales as "
       "that patch scales the game's own events",
    2: "times the game's own factor for its two-choice events (1 up to 25 villagers, 2 up to 50, 3 above)",
    3: "times the game's own multiplier for its events (the villagers it counts, divided by 20, plus 1)",
    4: "with Island Events Scale With Population or With Stored Food and Tech Points ticked, the amount scales as "
       "that patch scales the game's own events",
    5: "with Island Events Scale With Population or With Stored Food and Tech Points ticked, the amount scales as "
       "that patch scales the game's own events",
}
HOW = {
    1: "one more of the game's villager encounters (its two-choice island events), drawn 1 in m + 1 when the encounters "
       "are drawn (m the encounters possible then; 1 in m + 2 while The Cave Explorers can happen too), never the "
       "village's first island event",
    2: "one more of the game's two-choice island events (family A) with its own slot in the draw, 1 in 23 a draw like "
       "each of them (the draw is one wider for The Climb), never the village's first island event",
    3: "one more island event, listed and drawn like the game's own (1 in the number listed)",
    4: "one more island event, listed and drawn like the game's own (1 in the number listed)",
    5: "one more island event, listed and drawn like the game's own (1 in the number listed)",
}


def description(game: int) -> str:
    classic = ("Off by default; part of Classic VV Difficulty; Owner's Defaults ticks it."
               if game in CLASSIC else "Off by default; Owner's Defaults ticks it.")
    return (
        "Adds new island events, written by the owner, to the ones the game draws from (more come in later versions). "
        + ("Two here: " if game in (1, 2) else "For now one: ")
        + "The Aspiring Adventurer -- a villager who loves to explore sees something glinting off the "
        "safe path. \"Go investigate!\" finds a pile of dirt, a stack of meat (food) or a golden chest of "
        "artifacts (tech points); half the time the adventurer gets home (with the find, or with a friend's "
        "help), half the time a trap leads to death (a grave) or a disappearance (no grave). \"Stay on the safe "
        "path\" brings them home 9 times in 10; otherwise they are lost: hurt, healed or disabled, a skilled "
        "survivalist, killed, gone, or they " + ("become a Heathen" if game == 5 else "join another tribe")
        + ". The event is " + HOW[game] + "; it needs two villagers of 14 or more who are not nursing a baby and not "
        + WHO_NOT[game] + ", and the adventurer and the friend who may come to help are drawn from them. The "
        "reward is a random amount from the smallest to the largest food or tech-point gain of the game's own island "
        "events (" + reward_words(game) + ")" + ("; " if game in (1, 4, 5) else " ") + SCALE[game]
        + ". Deaths are the game's own (\"Unknown causes\", with a grave); a disappearance is logged as one in the "
        "Deaths log. The popups show the owner's text in pages that fit the screen (OK shows the next); the effects wait "
        "for the page that tells them, and the Island Events log keeps one entry for each event."
        + (CAVE_DESCRIPTION if game == 1 else CLIMB_DESCRIPTION if game == 2 else "") + " " + classic + " **Needs no other patch.** "
        "**Unverified in play: the event has not been seen in a running game** (emulated on the stock executable). "
        "The companion is \"" + DLL_NAME + "\", started by VVFP Startup.dll; nothing is saved by it."
    )


def row(game: int, sha: str) -> dict:
    return {
        "id": f"vv{game}_more_island_events",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": f"vv{game}",
        "name": NAME,
        "description": description(game),
        "output_tag": "Aspiring Adventurer",
        "dependencies": [],
        "behavior_changes": [
            f"The event is {HOW[game]}. It can happen only while at least two villagers may go: 14 or more (280 age "
            f"units), alive and present, not carrying a baby, and not {WHO_NOT[game]}; the adventurer and the friend "
            "of ending A8 are drawn from them, the friend never the adventurer.",
            "Choice A, \"Go investigate!\": the find 50% a pile of dirt, 25% meat (a food award: "
            + adv.award_words(game, "food") + "), 25% a golden chest (a tech award: " + adv.award_words(game, "tech")
            + "); then 50% a surviving ending (after the dirt A7 or A9; after a find A1, A5 or A8, "
            "which give the reward) and 50% a deadly one (A2 and A4 die, the game's own death with cause -1 and a "
            "grave; A3 and A6 disappear, no body), each equally likely within its half.",
            "Choice B, \"Stay on the safe path\": 90% home safe; 10% lost, then 1 in 6 each: the healers (1 in 3 "
            "each: dies; a full recovery; health set to 10-50 and running disliked), " + JOINS[game]
            + ", a survivalist (+20 to 30 in Farming, Building, Research or Healing, at most 100), dies under a "
            "fallen tree, dies at the bottom of a cliff, disappears.",
            "The reward is drawn, each amount equally likely, from the game's smallest to its largest stock "
            "island-event gain of that kind (src/vv_aspiring_adventurer.py AWARD_RANGES), and goes through the game's "
            "own food or tech writer" + ("; " if game in (1, 4, 5) else ", ") + SCALE[game] + ". The effects wait for their own page (the "
            "page that ends the ending's text), and the event writes its own one Island Events log entry; a "
            "disappearance is told to "
            "the Cause of Death companion (VvfpCauseVanishedBy), so its Deaths log records it as one.",
            "The owner's words, by translation key (the event's popup shows the player's language when a translation "
            "has them), are laid out in pages that fit the game's popup -- whole paragraphs, else whole sentences -- "
            "each shown in turn with OK.",
        ] + ([CAVE_BEHAVIOUR] if game == 1 else [CLIMB_BEHAVIOUR] if game == 2 else []),
        "explicit_non_changes": [
            "No executable byte is patched: the companion writes each site at run time, only after verifying every "
            "site's stock bytes (all of them, or none); without it the event does not exist.",
            "Every stock event, its odds, the island-event timer and counting, the rescue rules and Custom Island "
            "Events are unchanged; nothing is saved by the companion.",
        ],
        "evidence_status": ("implemented from exact-build disassembly; the draw, the popup pages, both choices' "
                            "effects and the install with every other patch emulated on the stock executable in "
                            "tests/test_aspiring_adventurer.py"
                            + (" (The Cave Explorers: every path, its effects and its pages, in "
                               "tests/test_cave_explorers.py)" if game == 1 else
                               " (The Climb: who may climb, both answers, both climbs, every effect and its pages, in "
                               "tests/test_the_climb.py)" if game == 2 else "")
                            + "; runtime/player confirmation pending"),
        "companion_files": [
            {"source": f"assets/more_island_events/{DLL_NAME}", "destination": DLL_NAME, "sha256": sha},
        ],
        "patches": [],
        "runtime_detours": [
            {"va": f"0x{va:X}", "stock_bytes": stock, "written_bytes": written, "routine": what,
             "installed_by": INSTALLED_BY}
            for va, stock, written, what in SITES[game]
        ],
    }
