"""The five rows of "More Island Events" (vvN_more_island_events): for now one event, The Aspiring Adventurer, written by
scripts/build_more_island_events.py.  The sites are the companion's own (native/vvfp_more_island_events: adv_vv1.inc,
adv_vv2.inc, adv_vv345.inc; tests/test_aspiring_adventurer.py pins the two together)."""
from __future__ import annotations

DLL_NAME = "VVFP More Island Events.dll"
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"
NAME = "More Island Events"
CLASSIC = (4, 5)

# (va, stock bytes, written, what) per game.
SITES = {
    1: (
        (0x4189F2, "E829FFFFFF", "E8XXXXXXXX",
         "the encounter setup 0x4189E0's call of its roller 0x418920: the companion draws this event 1 in m + 1 (m the "
         "encounters the roller would accept now), else calls the roller as before"),
        (0x41939D, "0F87D70F0000", "E9XXXXXXXX90",
         "the answer's resolve 0x419380, past its stock kinds (ja 0x41A37A): the event's own kind is answered by the "
         "companion (the effects and the first result page); every other kind goes on as before"),
        (0x41A3EE, "E8BD25FFFF", "E8XXXXXXXX",
         "OK's close in the encounter click handler 0x41A3D0: while the event has a page left it is shown instead"),
        (0x41A87C, "E8FF02FFFF", "E8XXXXXXXX",
         "the encounter constructor's attaching of its second answer: a question of more than one page starts on its "
         "first page, with OK"),
    ),
    2: (
        (0x41F5AC, "0F87E4000000", "0F87XXXXXXXX",
         "family A's draw 0x41F570: its draw 21 (never kept in the stock game) is kept for this event when it can "
         "happen -- 1 in 22 a draw, like each stock event"),
        (0x41F7A0, "0F87620C0000", "0F87XXXXXXXX",
         "family A's setup 0x41F780, past its jump table: the event's 21 is set up by the companion"),
        (0x4204CE, "0F87831D0000", "0F87XXXXXXXX",
         "family A's resolve 0x4204B0, past its jump table: the event's 21 is answered by the companion (the effects "
         "and the first result page)"),
        (0x42230E, "E87DB0FEFF", "E8XXXXXXXX",
         "OK's close in family A's click handler 0x4222F0: while the event has a page left it is shown instead"),
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
       "are drawn (m the encounters possible then), never the village's first island event",
    2: "one more of the game's two-choice island events (family A), drawn 1 in 22 a draw like each of them, never the "
       "village's first island event",
    3: "one more island event, listed and drawn like the game's own (1 in the number listed)",
    4: "one more island event, listed and drawn like the game's own (1 in the number listed)",
    5: "one more island event, listed and drawn like the game's own (1 in the number listed)",
}


def description(game: int) -> str:
    classic = ("Off by default; part of Classic VV Difficulty; Owner's Defaults ticks it."
               if game in CLASSIC else "Off by default; Owner's Defaults ticks it.")
    return (
        "Adds new island events, written by the owner, to the ones the game draws from (more come in later versions). "
        "For now one: The Aspiring Adventurer -- a villager who loves to explore sees something glinting off the "
        "safe path. \"Go investigate!\" finds a pile of dirt, a stack of meat (+500 food) or a golden chest of "
        "artifacts (+2,000 tech points); half the time the adventurer gets home (with the find, or with a friend's "
        "help), half the time a trap leads to death (a grave) or a disappearance (no grave). \"Stay on the safe "
        "path\" brings them home 9 times in 10; otherwise they are lost: hurt, healed or disabled, a skilled "
        "survivalist, killed, gone, or they " + ("become a Heathen" if game == 5 else "join another tribe")
        + ". The event is " + HOW[game] + "; it needs two villagers of 14 or more who are not nursing a baby and not "
        + WHO_NOT[game] + ", and the adventurer and the friend who may come to help are drawn from them. The "
        "reward is 500 food or 2,000 tech points" + ("; " if game in (1, 4, 5) else " ") + SCALE[game] + ". Deaths are the game's own (\"Unknown "
        "causes\", with a grave); a disappearance is logged as one in the Deaths log. The popups show the owner's "
        "text in pages that fit the screen (OK shows the next). " + classic + " **Needs no other patch.** "
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
            "Choice A, \"Go investigate!\": the find 50% a pile of dirt, 25% meat (+500 food), 25% a golden chest "
            "(+2,000 tech points); then 50% a surviving ending (after the dirt A7 or A9; after a find A1, A5 or A8, "
            "which give the reward) and 50% a deadly one (A2 and A4 die, the game's own death with cause -1 and a "
            "grave; A3 and A6 disappear, no body), each equally likely within its half.",
            "Choice B, \"Stay on the safe path\": 90% home safe; 10% lost, then 1 in 6 each: the healers (1 in 3 "
            "each: dies; a full recovery; health set to 10-50 and running disliked), " + JOINS[game]
            + ", a survivalist (+20 to 30 in Farming, Building, Research or Healing, at most 100), dies under a "
            "fallen tree, dies at the bottom of a cliff, disappears.",
            "The reward goes through the game's own food or tech writer" + ("; " if game in (1, 4, 5) else ", ") + SCALE[game] + ". The effects are made "
            "when the answer is clicked, as the game's own two-choice events make theirs; a disappearance is told to "
            "the Cause of Death companion (VvfpCauseVanishedBy), so its Deaths log records it as one.",
            "The owner's words, by translation key (the event's popup shows the player's language when a translation "
            "has them), are laid out in pages that fit the game's popup -- whole paragraphs, else whole sentences -- "
            "each shown in turn with OK.",
        ],
        "explicit_non_changes": [
            "No executable byte is patched: the companion writes each site at run time, only after verifying every "
            "site's stock bytes (all of them, or none); without it the event does not exist.",
            "Every stock event, its odds, the island-event timer and counting, the rescue rules and Custom Island "
            "Events are unchanged; nothing is saved by the companion.",
        ],
        "evidence_status": ("implemented from exact-build disassembly; the draw, the popup pages, both choices' "
                            "effects and the install with every other patch emulated on the stock executable in "
                            "tests/test_aspiring_adventurer.py; runtime/player confirmation pending"),
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
