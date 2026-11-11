"""Stew Recipes: every stew the cauldron makes in The Lost Children (VV2), The Secret City (VV3) and The Tree of Life
(VV4) -- the herbs by their in-game names, the water and what happens.

The owner, 2026-11-10: "for VV2, VV3 and VV4: I want separate pages for Stew Recipes. the ingame names of each herb,
fresh or salt water and their effects"; then, asked whether it belongs in Game Mechanics: "Separate window".  So it
is a tool of its own (src/vv_stew_recipes_window.py), one tab per game; Game Mechanics is not changed.  Anything from
the cauldron is a stew (the owner's rule), so soap, cloth pulp, the potions and the failed mixes are recipes here
too; in The Tree of Life the pulpy vines are a herb like the others.

Every line is read from the stock executables (research/stock-executables), the addresses in the comments beside
each table; the visible text has none.  tests/test_stew_recipes.py pins every table to the exe bytes (and runs The
Lost Children's cook routine for every herb mix).  Where the owner's play disagrees with the code (the health floors:
"I could swear I killed villagers with just the stews"), the line says so and carries UNCONFIRMED.  Read only.
"""
from __future__ import annotations

import re

import vv_game_mechanics as gm

GROUP = "Stew Recipes"
GAMES = (2, 3, 4)
C, E = gm.CODE, gm.RUNNING

HERBS_LINE, WATER_LINE, DOES_LINE, KILL_LINE = "Herbs: ", "Water: ", "What happens: ", "Can it kill? "
# Can it kill?  A stew that makes the eater sick: yes -- a sick villager loses 1 health on 61% of age units (19% at 20
# health or less) until cured and dies at 0 (VV2 aging step 0x43B690, 0x43BC0E; VV3 life tick 0x460030 the same rules;
# src/vv_game_mechanics_death.py).  A stew that takes health: the code stops it at a floor (VV2 3: 0x461174,
# 0x4614F4; VV3 2: 0x426CB6 -> 0x462670, 0x426C9F), but the owner has seen villagers die from the stews alone
# (2026-11-10), so that line is UNCONFIRMED.
SICK_KILLS = ("Yes: a sick villager keeps losing health until cured, so this {thing} can kill a villager who is "
              "not cured.", C)
FLOOR = ("The game's code seems to stop this {thing} at {floor} health, so it would not kill on its own, but "
         "players have seen villagers die from these {things} alone.", False)


def _kill(words: tuple, **names) -> tuple:
    return words[0].format(**names), words[1]


PUZZLE_LINE, REHEAT_LINE = "Puzzle: ", "Reheat: "


def _recipe(title: str, herbs: str, water: str, does: str, ok=C, kill=None, extra=()) -> list[gm.Fact]:
    """One recipe as a small table: its title (what it does, in short), then its herbs, its water and what happens,
    for a stew that harms whether it can kill (`kill`: its words and their label), then any `extra` lines (each its
    words and label: a puzzle's requirements, reheating)."""
    out = [gm.Fact(GROUP, title, ok),
           gm.Fact(GROUP, HERBS_LINE + herbs, ok, sub=True),
           gm.Fact(GROUP, WATER_LINE + water, ok, sub=True),
           gm.Fact(GROUP, DOES_LINE + does, ok, sub=True)]
    if kill is not None:
        out.append(gm.Fact(GROUP, KILL_LINE + kill[0], kill[1], sub=True))
    out += [gm.Fact(GROUP, words, label, sub=True) for words, label in extra]
    return out


def _mixes(triples, name) -> str:
    """Each herb mix as "A + A + B", the mixes apart by semicolons."""
    return "; ".join(" + ".join(name(h) for h in triple) for triple in triples)


# ---------------------------------------------------------------------------------------------------------------------
# The Lost Children (VV2)
# ---------------------------------------------------------------------------------------------------------------------
# The six herbs are carried items 0x30..0x35.  The game names none of them: every herb spot's hover (the village mouse
# slot's switch 0x42AD1D, table 0x42C1E8 -> 0x42C184: places 0x24..0x29 all go to 0x42BD6D) says string 176
# " sees the strange plant.", and studying one (0x4589A0, 0x458B70, 0x458CD0, 0x458E30, 0x458FD0, 0x459130) shows
# string 263 "Studying strange plant".  So the page names each by where it grows.  The drop handler 0x42FB52 (table
# 0x430888 -> 0x4307EC) sends place 0x25/0x26/0x24/0x27/0x28/0x29 to the herb trip 0x45A5C0 with 0x21/0x24/0x23/
# 0x22/0x25/0x26 (0x43053C, 0x4305AD, 0x4304E5, 0x43048E, 0x43061E, 0x43068F); its table 0x45AD58 picks the trip
# whose completion action (0x45A756 .. 0x45AD36, pushed for step 0x11) adds herb 0x30 + (action - 48) to the pot
# (the completion switch 0x461B10, table 0x4642F4: 0x462033, 0x46215B, 0x4620C7, 0x4621EF, 0x46226E, 0x4622ED).
# Where each grows: the spot the study walks to (the first walk of each study routine above), on the island map
# (Images/MapX0Y0..MapX3Y3.jpg, 512-pixel tiles), (x, y).
VV2_HERBS = {   # the patcher's names, by each plant's colour on the island map (the owner, 2026-11-10)
    0x30: ("Dark blue flower", "top middle, by the grey rocks beside the big stone face", 0x25, (969, 186)),
    0x31: ("Purple-black flower", "top right, the row of flowers above the waterfall", 0x26, (1538, 382)),
    0x32: ("Brown pitcher plant", "top left corner, by the rocks above the beach", 0x24, (139, 118)),
    0x33: ("Orange flower", "bottom middle, at the bottom edge", 0x27, (889, 1617)),
    0x34: ("Light blue flower", "along the top edge, right of the big stone face", 0x28, (1286, 70)),
    0x35: ("Red flower", "bottom right, beside the mosaic ruins", 0x29, (1611, 1391)),
}
# The cook routine 0x425B90 (called when the last ingredient goes in) counts each herb in the pot's three slots
# (0x425B60: the order does not matter) and sets the stew +0x3044C; every one of the 56 mixes, run in the emulator
# (tests/test_game_mechanics_stews.py), gives the stew below.  Stew 1 is its fall-through (0x425EF8): every mix not
# matched before it.
VV2_RECIPES = {
    1: ((0x30, 0x30, 0x32), (0x30, 0x30, 0x34), (0x30, 0x30, 0x35), (0x30, 0x32, 0x32), (0x30, 0x32, 0x33),
        (0x30, 0x33, 0x33), (0x30, 0x33, 0x34), (0x30, 0x33, 0x35), (0x30, 0x34, 0x34), (0x30, 0x34, 0x35),
        (0x32, 0x32, 0x32), (0x32, 0x32, 0x33), (0x32, 0x32, 0x34), (0x32, 0x33, 0x33), (0x32, 0x33, 0x34),
        (0x32, 0x34, 0x34), (0x33, 0x33, 0x34), (0x34, 0x35, 0x35)),
    2: ((0x30, 0x31, 0x31), (0x31, 0x31, 0x32), (0x31, 0x31, 0x33), (0x31, 0x31, 0x34), (0x31, 0x31, 0x35)),
    3: ((0x30, 0x31, 0x34), (0x30, 0x32, 0x34)),
    4: ((0x30, 0x31, 0x33), (0x30, 0x31, 0x35), (0x31, 0x32, 0x32), (0x31, 0x32, 0x33), (0x31, 0x32, 0x34),
        (0x31, 0x32, 0x35), (0x31, 0x33, 0x34), (0x31, 0x34, 0x34), (0x31, 0x34, 0x35), (0x31, 0x35, 0x35)),
    5: ((0x31, 0x33, 0x33),),
    6: ((0x33, 0x35, 0x35), (0x35, 0x35, 0x35)),
    7: ((0x30, 0x35, 0x35),),
    8: ((0x30, 0x32, 0x35),),
    9: ((0x32, 0x33, 0x35), (0x32, 0x35, 0x35)),
    10: ((0x34, 0x34, 0x34), (0x34, 0x34, 0x35)),
    11: ((0x30, 0x30, 0x30), (0x30, 0x30, 0x33)),
    12: ((0x30, 0x30, 0x31), (0x30, 0x31, 0x32)),
    13: ((0x32, 0x32, 0x35), (0x32, 0x34, 0x35)),
    14: ((0x33, 0x33, 0x33), (0x33, 0x34, 0x35)),
    15: ((0x33, 0x33, 0x35),),
    16: ((0x31, 0x33, 0x35),),
    17: ((0x33, 0x34, 0x34),),
    18: ((0x31, 0x31, 0x31),),
}
# The water: the pot's drop 0x42FE5E..0x42FF0A asks for the water (0x45AF30, "Adding water to the stew", string 293)
# before the food; that trip walks to (1006, 859) and (1405, 823), the edge of the pond at the foot of the waterfall
# on the island map, and its completion (action 47, 0x4623C7) sets the pot's water +0x30455.  No other water goes in.
VV2_WATER = "fresh water from the pond at the foot of the waterfall"
# What each stew does when eaten: the effect switch 0x461040 (table 0x461510), the message each case shows (0x44B2A0
# with the string id), and the routines it calls (their status words: 0x455330 "Exercising", 0x454AB0 "Relaxing",
# 0x45CD00 "Nature is calling!", 0x450580 "Dancing" (not for one who dislikes dancing, 0x450586), 0x455AC0 "Jumpy!",
# 0x44B010 "Running away", 0x453430 "Getting a drink", 0x44B1B0 "Shaking head").  Health: +0x52C, never above 100.
# Stew 5 keeps its eater (+0x3045C, 0x46114E); the pond's drop (0x430012) sends that villager, while the Sunken Gong
# Piece is not yet found (+0x2E7C8), to 0x450D50 "Retrieving something from the pond".  Stew 15 calls the job picker
# 0x45FBF0 with kind 2 (0x46035D): a partner of the other sex, both 18 or older (360 age units), "Embracing" (0x45D510),
# the partner "Waiting for someone" (0x45D4B0); a woman holding a baby (+0x540) does nothing (0x461304).  Stew 16:
# 0x44B550 adds the skills; 5 or more, half the time a random skill +2..+5 (table 0x461558), else the best (0x44B4D0)
# -2..-5, never below 0.  When it is cooked, stews 1 and 14 also call villagers to eat (0x425EF8, 0x425F92): the
# check reads the carried item +0x44 above 0x32 (its "below 0" branch can never be true), so only a child out
# fetching a find from the 22nd collectable on (the last three shells, the beetles, the pebbles) or a mushroom is
# called: 1 in 5 of them (rand(100) < 20) for stew 1, 9 in 10 (< 90) for stew 14.
CALLED = ("When it is cooked, a child who is out fetching a find (one of the last three shells, a beetle, a pebble "
          "or a mushroom) at that moment comes to eat it, {odds}; nobody else is called.")
VV2_STEWS = (   # (stew number, title, what happens)
    (17, "Heals 50 to 99 health and cures sickness",
     "\"This stew completely restored your villager!\" The eater gains 50 to 99 health (up to 100) and is cured of "
     "sickness."),
    (10, "Heals 2 to 6 health",
     "\"Your villager feels healthier after eating.\" The eater gains 2 to 6 health (up to 100)."),
    (1, "Heals 1 health (every mix not listed under another stew)",
     "\"Your villager feels healthier after eating.\" The eater gains 1 health (up to 100). "
     + CALLED.format(odds="1 time in 5")),
    (3, "Cures sickness",
     "\"The spicy stew clears your villager's nose and throat.\" The eater is cured of sickness."),
    (5, "Puzzle: The Sunken Gong Piece -- lets a villager dive for it",
     "\"Strange stew... your villager feels no need to breathe!\" The game remembers who ate it (only the last one "
     "to eat it): that villager, dropped on the pond while the Sunken Gong Piece is still down there, goes "
     "\"Retrieving something from the pond\"."),
    (16, "Changes a skill",
     "\"Your villager feels healthier after eating.\" For a villager whose skills add up to 5 or more: half the "
     "time one skill picked at random goes up by 2 to 5, otherwise their best skill goes down by 2 to 5 (never "
     "below 0). Nothing for anyone else."),
    (15, "Sends the eater to embrace a partner",
     "No message. A villager aged 18 or older who is not sick, and not a woman holding a baby, goes \"Embracing\" "
     "with a partner of the other sex aged 18 or older (who goes \"Waiting for someone\"), when the game finds "
     "one."),
    (6, "Sends the eater to exercise",
     "\"The stew gave your villager a burst of energy!\" The eater goes \"Exercising\"."),
    (7, "Sends the eater to relax",
     "\"The stew made your villager tired.\" The eater goes \"Relaxing\"."),
    (9, "Sends the eater dancing",
     "\"The stew gave your villager a burst of energy!\" The eater goes \"Dancing\" (not a villager who dislikes "
     "dancing)."),
    (11, "Makes the eater jumpy",
     "\"Wow! Is your villager allergic to this stew?\" The eater goes \"Jumpy!\"."),
    (12, "Makes the eater thirsty",
     "\"Thirsty! So thirsty!\" The eater goes \"Getting a drink\"."),
    (13, "Very spicy: makes the eater thirsty",
     "\"This stew is very, very spicy!\" The eater takes a short step, then goes \"Getting a drink\"."),
    (14, "Sweet smell: makes children play",
     "\"This stew gives off a very sweet smell.\" A child under 14 who eats it plays (dancing, jumping or running "
     "away, equally likely); an adult nothing more. " + CALLED.format(odds="9 times in 10")),
    (8, "Sends the eater to the bathroom",
     "\"The stew made your villager have to go to the bathroom.\" The eater goes \"Nature is calling!\"."),
    (4, "Nasty: loses 1 health",
     "\"This stew is nasty. It really isn't edible.\" The eater loses 1 health, stops what they were "
     "doing and goes \"Shaking head\"."),
    (2, "Makes the eater sick",
     "\"The stew made your villager very ill.\" The eater falls sick."),
    (18, "Burns: loses 15 to 39 health",
     "\"It burns! This foul stew is very harmful.\" The eater loses 15 to 39 health."),
)


# Stew 2 makes the eater sick; stews 4 and 18 take health, stopped at 3 in the code (0x461174, 0x4614F4).
VV2_KILLS = {2: _kill(SICK_KILLS, thing="stew"),
             4: _kill(FLOOR, thing="stew", floor=3, things="stews"),
             18: _kill(FLOOR, thing="stew", floor=3, things="stews")}


# The puzzles.  The Stew: the cook routine solves it (+0x2E7A8, 0x426056) with the first stew cooked that is not 4, 2
# or 18 (0x42602B..0x426040).  The Sunken Gong Piece: the pond's drop (0x430012..0x43002F) sends the villager kept by
# stew 5 (+0x3045C) to dive (0x450D50) while the piece is not found (+0x2E7C8) and a third flag +0x2E970 is clear --
# what sets +0x2E970 was not found in the code, hence UNCONFIRMED.
VV2_PUZZLES = {
    5: [(PUZZLE_LINE + "The Sunken Gong Piece. One villager is enough: the last villager to eat this stew, dropped "
         "on the pond, dives and brings it up. It works only while the piece is still down there (once it is found, "
         "the stew does nothing more for the pond).", C),
        (PUZZLE_LINE + "The game also checks one more condition there whose meaning was not found in the code.",
         False)],
}
VV2_SUMMARY = (
    "Stews for puzzles: The Stew -- the first stew you cook solves it, unless it is one of the three harmful ones "
    "(\"Makes the eater sick\", \"Nasty\" or \"Burns\"), which do not count. The Sunken Gong Piece -- the breathing "
    "stew (\"Lets a villager dive for it\" below): one villager who ate it, dropped on the pond.")


def _vv2_name(herb: int) -> str:
    return VV2_HERBS[herb][0]


def vv2_facts() -> list[gm.Fact]:
    out = [
        # The pot's drop 0x42FE5E..0x42FF2E: a ready stew is eaten (0x451550); the fire must burn (else string 296
        # "There is no fire burning!"); then the start (0x45A4A0), the water (0x45AF30), the food (0x45AD70: more than
        # 10 in store, else string 295; 0x46236C takes 10); the herbs go in only once the stew is started and the
        # plant understood (0x430474..0x43049A, flags +0x2E860..+0x2E888; else the study).  The cook routine runs
        # when the last of these goes in (0x4620A1..0x4623BA); the pot keeps the stew 15 real-life minutes
        # (vv_game_mechanics_vv2.STEW_POT_LINE).
        gm.Fact(GROUP, (
            "How a stew is made: drop a villager on the pot while the fire is burning to start it, then drop "
            "villagers on the pot to add the water and then 10 food (the store needs more than 10), and drop "
            "villagers on strange plants to add 3 herbs, in any order. The stew is ready the moment the last of "
            "these goes in, and every villager dropped on the pot in the next 15 real-life minutes eats it. The "
            "water is always fresh water, fetched from the pond at the foot of the waterfall: no stew here takes "
            "salt water."), C),
        # The effect switch 0x461040 touches no food (+0x2EAA4 is never read or written there).
        gm.Fact(GROUP, (
            "Food: every stew takes 10 food from the store when the food goes in, and the store must hold more than "
            "10. Eating a stew takes no food and gives only what its recipe says below."), C),
        gm.Fact(GROUP, VV2_SUMMARY, C),
        gm.Fact(GROUP, (
            "The herbs: the names below are the patcher's own, after each plant's colour; the game calls every "
            "one \"the strange plant\" (pointing at any of them says \"... sees the strange plant.\"). A plant goes "
            "into a stew only once your villagers understand it; until then a villager dropped on it studies it "
            "(\"Studying strange plant\")."), C),
    ]
    out += [gm.Fact(GROUP, f"{name}: {where}.", C, sub=True) for name, where, _place, _spot in VV2_HERBS.values()]
    for stew, title, does in VV2_STEWS:
        out += _recipe(title, _mixes(VV2_RECIPES[stew], _vv2_name), VV2_WATER, does, E, VV2_KILLS.get(stew),
                       VV2_PUZZLES.get(stew, ()))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# The Secret City (VV3)
# ---------------------------------------------------------------------------------------------------------------------
# The herbs are carried items 0x1F..0x25 (vv_game_mechanics_counts.VV3_HERBS): the hover switch 0x466A40 (table
# 0x46767C -> 0x467610) shows regions 8..12, 30 and 31 the strings eSaySeesHerb1..7 (0xB0..0xB6: "{name} sees a Tiger
# Lily." .. "a Berry plant."), and those regions' drops (0x421F50, 0x421FE0, 0x422070, 0x422100, 0x422190, 0x421340,
# 0x4213D0, registered at 0x422AC7..0x422B1B) gather items 0x1F..0x25 ("Gathering herbs", task 0x73).  The recipes
# are vv_game_mechanics_counts.VV3_COMBOS (the book's constructor 0x4305A0: 77 calls of 0x430480 with three herbs
# and a potion, no water); what each potion does is VV3_POTIONS (the effect switch 0x4268F0) with
# vv_game_mechanics_items_vv3.POTION_FIXES.  With Both Factions (native/vvfp_vv3_both_factions, RECIPES): a Pitcher
# Plant, a Berry Plant and a third herb make these potions (docs/vv3-both-factions.md).
VV3_BOTH = ((0x1F, 0x07), (0x20, 0x23), (0x21, 0x26), (0x22, 0x16), (0x23, 0x19), (0x24, 0x21), (0x25, 0x28))
VV3_WATER = "none (the alchemy pot takes only the 3 herbs)"
# Potion 21 makes the drinker sick; 2, 20 and 31 take health, stopped at 2 in the code (their words below drop the
# shared "never below 2", which the owner's play does not confirm).
VV3_KILLS = {21: _kill(SICK_KILLS, thing="potion"),
             **{p: _kill(FLOOR, thing="potion", floor=2, things="potions") for p in (2, 20, 31)}}
# The addresses the shared potion words carry in brackets, left out of this page's visible text (a bracket's other
# words are kept: "(0x45B9B0; 16.02% of the time none)" reads "(16.02% of the time none)").
_BRACKET = re.compile(r"\s*\(([^()]*)\)")
# Potion 1's shared words name the game's particle effect by its number; in a player's words it is a small puff.
VV3_PLAIN = {1: "A small puff appears at the villager; nothing else happens."}


def _plain(text: str) -> str:
    def keep(match: re.Match) -> str:
        if "0x" not in match.group(1):
            return match.group(0)
        parts = [part.strip() for part in re.split(r"[;,]", match.group(1)) if "0x" not in part]
        return f" ({'; '.join(parts)})" if parts else ""
    return gm.tidy(_BRACKET.sub(keep, text))


# The Sharks: either shark vial (26 or 27) kept by its drinker ("Carrying vial to ocean", no time limit), at the
# Diving Rock (0x436580; 0x4365C7 for 27), solves it; the puzzle's threshold is 1 (vv_game_mechanics_vv3
# PUZZLE_THRESHOLDS[10]).  Every potion needs The Alchemy Lab restored first (vv_game_mechanics_items_vv3).
SHARKS = (PUZZLE_LINE + "The Sharks. One villager is enough: the one who drinks it carries the vial, and taking it "
          "to the Diving Rock solves it.", C)
VV3_PUZZLES = {26: [SHARKS], 27: [SHARKS]}
VV3_SUMMARY = ("Stews for puzzles: The Sharks -- either shark vial (potion 26: Rose + Rose + Berry Plant; potion 27: "
               "Black Orchid + Black Orchid + Pitcher Plant): one villager drinks it and carries the vial to the "
               "Diving Rock. No potion can be made before The Alchemy Lab is restored.")


def _vv3_potion(product: int) -> tuple[str, str]:
    """A potion's title (what the drinker says: the game names a potion by nothing else) and what happens."""
    import vv_game_mechanics_counts as counts
    import vv_game_mechanics_items_vv3 as items
    say, does = counts.VV3_POTIONS[product]
    say = say.replace("{He/She}", "He or she")
    title = "A potion that says nothing" if say.startswith("(") else f"\"{say}\""
    if product in VV3_PUZZLES:
        title = f"Puzzle: The Sharks -- {title[0].lower()}{title[1:]}"
    if product in VV3_PLAIN:
        return title, VV3_PLAIN[product]
    does = items.POTION_FIXES.get(product, does).replace(", never below 2", "")
    return title, _plain(does[0].upper() + does[1:] + ".")


def vv3_facts() -> list[gm.Fact]:
    import vv_game_mechanics_counts as counts
    from vv_game_mechanics_chances import at_most, chance
    herbs = counts.VV3_HERBS
    out = [
        gm.Fact(GROUP, (
            "The herbs, by the names the game shows when you point at them: " + ", ".join(herbs.values()) + ". "
            "Tiger Lily, Cactus, Lotus, Black Orchid and Rose grow by the Alchemy Lab from the start; the Pitcher "
            "Plant only at Nature level 2 or more, the Berry Plant only at Magic level 2 or more."), C),
        # The brew's blow-up 0x430A81..0x430A92 (vv_game_mechanics_items_vv3 "Brewing a potion").
        gm.Fact(GROUP, (
            "How a potion is made: any 3 herbs in the alchemy pot, in any order -- no water, fresh or salt. A brew "
            "blows up " + chance(at_most(100, 30)) + ", " + chance(at_most(100, 15)) + " or "
            + chance(at_most(100, 0)) + " of the time at Alchemy level 1, 2 or 3. A villager dropped on the pot "
            "drinks the potion; the potion has no name in the game, only what the drinker says."), C),
        # Neither the alchemy pot's code (0x42F000..0x431400) nor the effect switch 0x4268F0 writes the food store
        # 0x582490 (the switch only compares it with 100, 0x4269EE / 0x426B04).
        gm.Fact(GROUP, (
            "Food: potions take no food, and drinking one takes none; two healing potions heal less while the "
            "village has under 100 food (below)."), C),
        gm.Fact(GROUP, VV3_SUMMARY, C),
    ]
    by_potion: dict[int, list[tuple[int, int, int]]] = {}
    for a, b, c, product in counts.VV3_COMBOS:
        by_potion.setdefault(product, []).append(tuple(sorted((a, b, c))))
    for product in sorted(by_potion):
        title, does = _vv3_potion(product)
        out += _recipe(f"{title} (potion {product})", _mixes(by_potion[product], herbs.get), VV3_WATER, does,
                       kill=VV3_KILLS.get(product), extra=VV3_PUZZLES.get(product, ()))
    out.append(gm.Fact(GROUP, (
        f"With the patcher's \"{gm.feature_name('vv3_both_factions')}\" (on by default) both the Pitcher Plant and "
        "the Berry Plant grow, and these 7 mixes of both make a potion too:"), C))
    for third, product in VV3_BOTH:
        title, does = _vv3_potion(product)
        out += _recipe(f"{title} (potion {product})",
                       " + ".join(herbs[h] for h in sorted((0x24, 0x25, third))), VV3_WATER, does,
                       kill=VV3_KILLS.get(product))
    return out


# ---------------------------------------------------------------------------------------------------------------------
# The Tree of Life (VV4)
# ---------------------------------------------------------------------------------------------------------------------
# The herbs are carried items 0x1F..0x22: each plant's handler (0x46EFA0, 0x46F030, 0x46F0C0, 0x46F150) says
# eSaySeesHerb1..4 (0x137..0x13A) when pointed at and, dropped on, sends the villager "Gathering herbs" (job 0x40)
# with item 0x1F, 0x20, 0x21 or 0x22 (0x46F012, 0x46F0A2, 0x46F132, 0x46F1C2).  The pulpy vines the cloth-maker cuts
# are that same item 0x22 (job 0x7A, 0x436B98; tests/test_unique_stews.py).
VV4_HERBS = {0x1F: "spicy-smelling plant", 0x20: "sweet-smelling plant", 0x21: "soapy-smelling plant",
             0x22: "pulpy vines"}
# The water: the fresh-water fill (0x42F630, "Filling a pot with fresh water") ends by clearing flag 0xA and setting
# flag 9 (0x42F753, 0x42F75C); the salt-water fill (0x42F770, "Filling a pot with salt water") clears 9 and sets 0xA
# (0x42F852, 0x42F85B).  The recipes (the register 0x42ECF0: herbs, product, water flag) match only in their own
# water (0x42DBF0 -> 0x46D880); a mix that matches none is 12 in salt water and 13 otherwise (0x42ECBE..0x42ECCF).
FRESH, SALT = 9, 0xA
VV4_RECIPES = (   # (herbs, product, water flag)
    ((0x1F, 0x1F, 0x1F), 0, FRESH), ((0x1F, 0x1F, 0x20), 1, FRESH), ((0x1F, 0x1F, 0x21), 2, FRESH),
    ((0x1F, 0x20, 0x20), 3, FRESH), ((0x1F, 0x20, 0x21), 4, FRESH), ((0x1F, 0x21, 0x21), 5, FRESH),
    ((0x20, 0x20, 0x20), 6, FRESH), ((0x20, 0x20, 0x21), 7, FRESH), ((0x20, 0x21, 0x21), 8, FRESH),
    ((0x21, 0x21, 0x21), 9, FRESH), ((0x21, 0x21, 0x21), 10, SALT), ((0x22, 0x22, 0x22), 11, SALT),
)
FAILED_SALT, FAILED_FRESH = 12, 13
# What each does.  Eaten (a villager dropped on the pot, job 0x92 "Eating some stew"): the effect switch 0x41DEE0
# (table 0x41E108) says a line (0x44C3A0 with esi) and gives the eater, or everyone the village walk 0x4671A0 picks
# (its 2nd and 3rd arguments an age from / below, 280 age units = 14), a job: 0 job 0x86 "Drinking from stream", say
# 0x5D; 1 job 0x87 for 14 or older, say 0x1FD; 2 job 0x33 "Nature is calling!", say 0x216; 3 job 0x88 for everyone,
# say 0x1FD; 4 job 0x93 for everyone, say 0x5B; 5 job 0xA1 ("Burping up soap bubbles", 0x42E4AC) and the Soapy
# Stew count 0x44 (0x41E02D), nothing said; 6 job 0x8F "Honoring the tree", say 0x5C; 7 job 0xA0 for those under 14,
# say 0x1FA; 8 heals 25..59 (0x4036D0(0x23) + 0x19), or 5..14 with under 100 food (0x4D6DD0), say 0x202 / 0x204,
# kept 600 real-life seconds; 9 job 0x9F ("Throwing up soapy stew!", 0x42E2A9), say 0x1FE, kept 600; 12 say 0x1F9;
# 13 say 0x1F8.  Jobs 0x87, 0x88, 0x93 and 0xA0 start with "Something smells YUMMY!" (0x457220, 0x457320, 0x4573B0,
# 0x42E330).  10 and 11 are not eaten: the pot's drop (0x42E748..0x42E770) gives job 0x77 "Stacking soap" for 10 and
# 0x7B "Spreading cloth pulp" for 11, and pointing at the pot says "Soap is ready to stack." / "Pulp for cloth is
# ready." (0x42E580..0x42E5B1).
# Boiling and food (re-traced 2026-11-10; the older pages call the +0xB1C count "heat", which it is not):
#   * A hot rock (job "Taking a hot rock to the pot", 0x42F920, carrying item 0x34) dropped on the pot's boiling-water
#     object (0x42F4A0) makes the pot boil: state 0x18 for 600 game-clock seconds (0x46D530) and one step of Boiling
#     Water (Advance 2).  The pot takes anything only while it boils (0x42EA61; else "The pot needs boiling water.",
#     string 0x234); the water fills (0x42F74A, 0x42F849) end the boiling, making a stew ends it (0x42EE5F), and an
#     unfinished Grand Feast boils again after each thing added (0x42EE1D).  When it ends with a stew unfinished the
#     pot says "The pot contains a cold unfinished stew."
#   * Food: a villager dropped on the food bin while the pot boils (0x46ED4A..0x46ED85: 10 food or more in store)
#     takes 10 food from the store (0x41D920(-10)) and carries item 6 to the pot ("Adding to the stew", job 0x85,
#     0x42E090), which adds 10 to the count +0xB1C (0x42EAA7).  0x42DC80: a stew is ready at 10 (one trip), the Grand
#     Feast at 20 (two trips) with its 4 items; soap and cloth pulp (10, 11) at once; failing, the pot says "This stew
#     needs something nutritious!" (0x42EE30, string 0x1E9).
#   * Remaking: a food trip while the pot boils with a stew ready makes the same stew again (0x42EAF1 -> 0x42EDE0)
#     and starts its 5 real-life minutes over; nothing excludes a recipe.  The owner: "VV4 stews can be reheated with
#     another hot rock if they go cold (applies to certain stews only)" -- which stews the owner means is not settled
#     by the code, so the per-recipe line is UNCONFIRMED.
#   * The Grand Feast's 4 items (0x42EABE, table 0x42EB4C -> 0x42EB38) and who brings them: blackberries (item 0,
#     +0xB21: a villager dropped on the bush while the pot wants them, 0x46F8AC), a fish (item 0x38, +0xB22: the
#     fishing trip, 0x43332C), fruit (item 0x37, +0xB23: "Carrying fruit to the cooking pot", 0x4349A8 and three more)
#     and a mushroom (items 0x76..0x78, +0xB20: the pick-up 0x413233; the three items above the 48 collectables).  The
#     feast is solved when it is made (0x42EEDC: Advance 0xA, threshold 1), before anyone eats it.
#   * Honoring the Tree: 0x4366D0 (vtable 0x48E8F4) counts the villagers on job 0x8F "Honoring the tree" (0x4678F0)
#     and advances puzzle 13 (threshold 1) at 20 or more (0x4366EC); job 0x8F comes from the sweet x3 stew (0x41E040).
#   * Soap Invented / Cloth Invented: 0x43A2D0 adds 3 bars of soap and advances puzzle 3; 0x4368B6 adds 3 cloth and
#     advances puzzle 7 -- their link to the soap stacking (job 0x77) and the pulp (job 0x7B) was not traced.
FOOD_TRIP, FEAST_FOOD = 10, 20
VV4_STEWS = {   # product: (title, what happens)
    8: ("Heals 25 to 59 health",
        "\"He or she feels much healthier!\" The eater gains 25 to 59 health; while the village has under 100 food, "
        "only 5 to 14, and the game says \"This stew works better when the tribe is eating well.\" That villager "
        "cannot eat this stew again for 10 real-life minutes."),
    4: ("Puzzle: The Grand Feast",
        "\"It's a grand feast!\" Whoever eats it, the whole village drops what they are doing and goes \"Something "
        "smells YUMMY!\"."),
    6: ("Puzzle: Honoring the Tree -- sends the eater to honor the tree",
        "\"This smells like flowers!\" The eater goes \"Honoring the tree\"."),
    1: ("Calls everyone 14 or older to the pot",
        "\"Yummy!\" Every villager aged 14 or older drops what they are doing and goes \"Something smells YUMMY!\"."),
    3: ("Calls the whole village to the pot",
        "\"Yummy!\" Every villager drops what they are doing and goes \"Something smells YUMMY!\"."),
    7: ("Hiccups; calls the children to the pot",
        "\"Oh no, hiccups!\" Every child under 14 drops what they are doing and goes \"Something smells YUMMY!\"."),
    0: ("Very spicy: sends the eater to drink",
        "\"This stew is really spicy!\" The eater goes \"Drinking from stream\"."),
    2: ("Sends the eater to the bathroom",
        "\"He or she has got to go!\" The eater goes \"Nature is calling!\"."),
    5: ("Soap bubbles",
        "Nothing is said; the eater goes \"Burping up soap bubbles\", and it counts toward the Soapy Stew "
        "achievement (25 villagers burping bubbles)."),
    9: ("Makes the eater throw up",
        "\"I feel sick!\" The eater goes \"Throwing up soapy stew!\" (it does not make them sick), and cannot eat "
        "this stew again for 10 real-life minutes."),
    10: ("Makes soap",
         "Not eaten: the pot says \"Soap is ready to stack.\", and a villager dropped on it goes \"Stacking "
         "soap\". Needs no food."),
    11: ("Makes cloth pulp",
         "Not eaten: the pot says \"Pulp for cloth is ready.\", and a villager dropped on it goes \"Spreading cloth "
         "pulp\". Needs no food."),
    FAILED_FRESH: ("Nasty (any other mix in fresh water)", "\"Nasty! It's bitter.\" Nothing else happens."),
    FAILED_SALT: ("Too salty (any other mix in salt water)", "\"Too salty! It's disgusting.\" Nothing else happens."),
}
VV4_ORDER = (8, 4, 6, 1, 3, 7, 0, 2, 5, 9, 10, 11, FAILED_FRESH, FAILED_SALT)
VV4_WATER = {FRESH: "fresh water", SALT: "salt water"}
FEAST_ITEMS = ("blackberries", "a fish", "fruit (\"Carrying fruit to the cooking pot\")", "a mushroom")
VV4_PUZZLES = {
    4: [(PUZZLE_LINE + "The Grand Feast. It needs, all while the pot boils: one hot rock to make it boil, 20 food "
         "from the food bin (two trips of 10), and one each of " + ", ".join(FEAST_ITEMS[:-1]) + " and "
         + FEAST_ITEMS[-1] + ", each brought to the pot by a villager dropped on that food while the pot wants it. "
         "When its 3 herbs are in but the rest is not, the pot boils for another 10 minutes of the game's clock. "
         "The puzzle is solved the moment the feast is made: nobody has to eat it.", C),
        (PUZZLE_LINE + "The game's recipe table gives the Grand Feast's herbs as spicy, sweet and soapy; the owner "
         "remembers spicy, sweet and sweet. Not yet settled.", False)],
    6: [(PUZZLE_LINE + "Honoring the Tree. It is solved when 20 villagers are \"Honoring the tree\" at the same "
         "time; each of them must have eaten this stew (a villager counts once, while honoring).", C)],
    10: [(PUZZLE_LINE + "Soap Invented: stacking a batch gives 3 bars of soap and counts for it (the link from "
          "stacking to the puzzle was not traced in the code).", False)],
    11: [(PUZZLE_LINE + "Cloth Invented: the cloth made from the pulp gives 3 bolts and counts for it (the link "
          "from the pulp to the puzzle was not traced in the code).", False)],
}
VV4_SUMMARY = (
    "Stews for puzzles: The Grand Feast (spicy, sweet and soapy, 20 food and the 4 feast foods; solved when it is "
    "made); Honoring the Tree (3 sweet-smelling plants; 20 villagers who ate it honoring at the same time); and, "
    "UNCONFIRMED, soap for Soap Invented and cloth pulp for Cloth Invented.")
REHEAT = (REHEAT_LINE + "in the game's code, every recipe can be made again: another hot rock makes the pot boil, "
          "and food added then makes the same stew again with a fresh 5 minutes. The owner remembers only certain "
          "stews reheating.", False)


def vv4_facts() -> list[gm.Fact]:
    recipes = {product: (herbs, water) for herbs, product, water in VV4_RECIPES}
    out = [
        gm.Fact(GROUP, (
            "The herbs, by the names the game shows when you point at them: the spicy-smelling plant, the "
            "sweet-smelling plant, the soapy-smelling plant and the pulpy vines. The pulpy vines the cloth-maker "
            "cuts are the same herb."), C),
        gm.Fact(GROUP, (
            "How a stew is made: the pot is filled with fresh water or salt water (\"Filling a pot with fresh "
            "water\" / \"... salt water\"), then one hot rock makes it boil (\"Taking a hot rock to the pot\"). The "
            "pot takes herbs and food only while it boils: 10 minutes of the game's clock (10 real-life minutes on "
            "Normal speed, 5 on Fast, 16 minutes 40 seconds on Slow). If that runs out first, the unfinished stew "
            "goes cold (\"The pot contains a cold unfinished stew.\") until another hot rock makes it boil again. "
            "3 herbs go in, in any order. The game's own tip: \"Only fresh water stews are edible.\""), C),
        gm.Fact(GROUP, (
            "Food: a villager dropped on the food bin while the pot boils takes 10 food from the store into the "
            "stew (\"Adding to the stew\"; the store needs at least 10). Every stew needs one such trip (10 food) "
            "before it is ready (\"This stew needs something nutritious!\" until then), the Grand Feast two (20 "
            "food); soap and cloth pulp need none. Eating a stew takes no food and gives only what its recipe says "
            "below."), C),
        gm.Fact(GROUP, VV4_SUMMARY, C),
        # The effect switch 0x41DEE0: its only health call is the healing stew's (0x41DF69, an addition), and no
        # case sets the sickness flag +0x1C48.
        gm.Fact(GROUP, "None of these stews takes away health or makes anyone sick.", C),
    ]
    for product in VV4_ORDER:
        title, does = VV4_STEWS[product]
        if product in recipes:
            herbs, water = recipes[product]
            mix = " + ".join(VV4_HERBS[h] for h in herbs)
            water_words = VV4_WATER[water]
        elif product == FAILED_FRESH:
            mix, water_words = "any other 3 (pulpy vines in fresh water always end here)", VV4_WATER[FRESH]
        else:
            mix, water_words = "any 3 but 3 soapy-smelling plants or 3 pulpy vines", VV4_WATER[SALT]
        out += _recipe(title, mix, water_words, does, extra=[*VV4_PUZZLES.get(product, ()), REHEAT])
    return out


def facts(game: int) -> list[gm.Fact]:
    """The Stew Recipes group of one game: The Lost Children, The Secret City and The Tree of Life only."""
    return {2: vv2_facts, 3: vv3_facts, 4: vv4_facts}.get(game, list)()
