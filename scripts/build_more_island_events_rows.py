"""The five rows of "More Island Events" (vvN_more_island_events): The Aspiring Adventurer (all five games), The Cave
Explorers (A New Home), The Climb (The Lost Children), The Troubling Signs and Diving for Treasure (The Secret City) and The Playful Dolphins (The Tree of Life), written by scripts/build_more_island_events.py.  The sites are the companion's own
(native/vvfp_more_island_events: adv_vv1.inc, adv_vv2.inc, adv_vv345.inc; tests/test_aspiring_adventurer.py pins the
two together)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import vv_aspiring_adventurer as adv  # noqa: E402


def reward_words(game: int) -> str:
    return f"{adv.award_words(game, 'food')} for the meat, {adv.award_words(game, 'tech')} for the chest"


# Every event's way in (collection_design.md C2): never a share of the stock draw.
RARE = ("it never takes a share of the game's own draw: it comes through Story / Cheat Upgrades' separate rare "
        "roll or Pick Island Event")

CAVE_DESCRIPTION = (
    " And The Cave Explorers (A New Home only): once The Cave puzzle is done, two friends of 18 or more, at most 5 "
    "years apart, wonder what the cave hides. \"Don't explore\" changes nothing; \"Explore the Cave\" leads on: "
    "\"Proceed Further\" brings a scream in the dark (they run, then argue, make up, or both fall down a chasm and are "
    "gone for good, 1 in 10) or a find (a map that takes both away for good, 1 in 10; gold coins: tech points; a "
    "treasure map: three times as many; preserved food: twice the food); \"Stay Here\" lets them return what they "
    "found (food or tech points) or keep it (the researchers' tech points half the time; otherwise one or both die, "
    "with graves). Each award is a random amount from the smallest to the largest food or tech-point gain of the "
    "game's own island events (A New Home: " + adv.award_words(1, "food") + ", " + adv.award_words(1, "tech")
    + "), scaled as the Aspiring Adventurer's is.")
CAVE_BEHAVIOUR = (
    "The Cave Explorers (A New Home): one more encounter like The Aspiring Adventurer (never a share of the stock "
    "draw: taken only while due, through Story / Cheat Upgrades' rare roll or Pick Island Event), only while The "
    "Cave puzzle is done (world byte +0x9FA8) and two villagers who may go on The Aspiring Adventurer are 18 or more (360 age units) and at most 5 years (100 age units) apart; the pair is drawn among those "
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
    "may go is enough; it comes as one of the two-choice events, never taking a share of their draw.")
CLIMB_BEHAVIOUR = (
    "The Climb (The Lost Children): its own number in family A's draw, 22 (The Aspiring Adventurer 21), taken only "
    "while it is due (Story / Cheat Upgrades' rare roll or Pick Island Event: the draw's first answer then; the stock "
    "rand(22) otherwise, untouched) and only while a villager who may go on The "
    "Aspiring Adventurer is 18 or more (360 age units) with Research +0x7F4 of 20 or more (the game's own \"Trainee\" "
    "level, 0x429C3D); the villager is drawn among them. \"Go with the plan\": 50% the fall (health 0: a body and a "
    "grave), 50% the summit (Research set to the game's cap 100, 0x4212F4; a large tech award, twice a normal one, "
    "through the family-A tech writer 0x426290 after the two-choice factor 0x41F720; the game's own village "
    "celebration 0x45D7D0 with Old Friends' place 0x18). \"Follow the scientists' advice\": +10 to 20 Research, at "
    "most 100. The effects wait for their own page: they are made when the page that ends the ending's text is "
    "shown, and the event writes its own one Island Events log entry (VvfpIslandEventsGraphBegin / End / Write).")

TROUBLING_DESCRIPTION = (
    " And The Troubling Signs (The Secret City only): the Tribal Chief, wearing the chief's robe, asks one of four "
    "groups for advice in a popup with four buttons (the game's own look; the mouse, or the keys 1 to 4): the "
    "spiritual leaders (the village loses food), the magicians (gains tech points), the naturalists (gains food) or the "
    "scientists and healers (loses tech points) -- a random amount as the Aspiring Adventurer's, " + adv.award_words(3, "food")
    + " or " + adv.award_words(3, "tech") + ", times the game's own multiplier; a loss never takes more than is "
    "stored. Each group's advisor speaks, the chief calls the tribe by its own name, and the decree sends five "
    "villagers of 18 or more away for good (no graves). It needs the robed chief, nine other villagers of 18 or more "
    "who are not nursing a baby (four advisors, who stay, and the five) and a population of 61 or more (The Lost "
    "Children's \"A Dangerous Mission\" rule: the living villagers plus the babies being carried); " + RARE + ".")
TROUBLING_BEHAVIOUR = (
    "The Troubling Signs (The Secret City): needs the Tribal Chief in the robe (+0xE80 and the robe's body +0xDF4 = 29, "
    "as the robing 0x45FBC0 writes them), nine other different villagers of 18 or more (360 age units) who are not "
    "protected (adv_is_protected: nursing +0xE8C, the chief +0xE80) -- four advisors (one per group, the same four for "
    "the event; they stay) and five travellers, any nine equally likely -- a population of 61 or more (The Lost "
    "Children's 0x425860 rule: the living villagers plus the babies carried, litter +0xE90) and the tribe's name (the "
    "game object [0x4B309C] +0x12ED4). It shares table slot 0 with The Aspiring Adventurer and Diving for Treasure "
    "and never takes a share of the draw: the loop-end stub adds no entry to the selector's list and puts the object "
    "of the event that is due (Story / Cheat Upgrades' rare roll or Pick Island Event) in slot 0, which Story / Cheat "
    "Upgrades' pick then presents in place of the stock event drawn. "
    "The popup is the game's own dialog 0x4192F0 with two more answer buttons made as its constructor makes its two "
    "(0x46EC93, picture 4 via 0x42E9D0 / 0x42E8A0, 0x4019F0 ids 4 and 5, labels 0x4185A0 / 0x401620, add-child "
    "0x40C1F0), stacked and centred 1.5 button heights apart, room for them measured by the game's own paragraph "
    "0x40A0C0; that dialog's virtual table is a copy of 0x47F28C with its own click (ids 4 and 5) and key handlers "
    "(Enter / Esc OK, 1-4 the answers); Scrolling Popups' reserve adds VvfpMoreIslandEventsButtonRoom. Each answer's "
    "award is a normal one (the game's range, then its multiplier); the effects -- the five removed as a living "
    "villager is (no body), told to Cause of Death, and the award through the game's own writer (a loss at most what "
    "is stored) -- are made when the decree's last page is shown, with the event's one Island Events log entry. No "
    "site of its own.")
DIVE_DESCRIPTION = (
    " And Diving for Treasure (The Secret City only): a villager of 18 or more dives for something shimmering on the "
    "reef. \"Swim deeper\": 1 in 4 each, golden doubloons (tech points), a useless buoy, a container of exotic "
    "ingredients (food) -- a random amount as the Aspiring Adventurer's, " + adv.award_words(3, "tech") + " or "
    + adv.award_words(3, "food") + ", times the game's own multiplier -- or an air tank pops: 75% the diver gets "
    "ashore and now dislikes swimming; 25% the diver sinks: dies (17%, a grave), is never found (17%, no grave) or "
    "is rescued (66%, +10 to 20 Healing, at most 100). \"Better not\": +10 to 20 Parenting, at most 100. It needs two "
    "villagers of 18 or more who are not nursing a baby and not the Tribal Chief (the diver, and another named as the "
    "head Doctor on the rescue page); " + RARE + ".")
DIVE_BEHAVIOUR = (
    "Diving for Treasure (The Secret City): the diver and the rescue page's head Doctor are two different villagers "
    "of 18 or more (360 age units) who may be picked (vv3_eligible: alive +0xE78, present +0xF10, not a look-alike "
    "+0xE94, adv_is_protected: nursing +0xE8C, the chief +0xE80), each drawn among them. One more two-choice object "
    "with the Adventurer's virtual table and methods (adv_flow), put in slot 0 only while it is due (t_list adds no "
    "entry to the selector's list). \"Swim "
    "deeper\": rand(4) A / B / C / D; D: rand(100) < 75 survives -- swimming (preference 37 of the game's list at file "
    "0x97488) taken from the likes +0xFB4 and added to the dislikes +0xFC0 -- else sinks: rand(100) < 17 the game's "
    "own death (0x462670, health 0, cause -1: a grave), < 34 removed as a living villager is (no body; told to Cause "
    "of Death), else +10 to 20 Healing (+0xEB4); A a normal tech award, C a normal food award (the game's range, then "
    "its multiplier, through 0x427130 / 0x4263F0). \"Better not\": +10 to 20 Parenting (+0xEB0). Skills at most 100 "
    "(the game's own adder 0x455740 caps at 0x64). The effects are made when the ending's last page is shown, with "
    "the event's one Island Events log entry. No site of its own.")
DOLPHIN_DESCRIPTION = (
    " And The Playful Dolphins (The Tree of Life only): a villager of 14 or more, swimming underwater, spots a pod of "
    "dolphins. \"Swim towards the dolphins\": half the time the swimmer watches them hunt -- Farming becomes 100 (the "
    "game's maximum) and the village gains a large food award (twice a normal one: "
    + f"{2 * adv.award_range(4, 'food')[0]:,}" + " food before the scaling); half the time a tail slaps the swimmer, "
    "who loses 30 to 50 health but never dies of it (at least 1 is left). \"Hang back\": a small food award (half a "
    "normal one: " + f"{adv.award_range(4, 'food')[0] // 2:,}" + " food before the scaling). It needs two villagers of 14 or more who are not "
    "nursing a baby and not a body or a ghost; it needs no puzzle (not the Fishing Nets); " + RARE + ".")
DOLPHIN_BEHAVIOUR = (
    "The Playful Dolphins (The Tree of Life): the swimmer is a villager who may be picked (vv4_eligible: present "
    "+0x1CC4, alive +0x1C40, 14 or more +0x1B8C, adv_is_protected: nursing +0x1C4C, a body or ghost +0x1CC7), drawn "
    "among them; it can happen while two such villagers live, with no puzzle (not the Fishing Nets). One more "
    "two-choice object with the Adventurer's virtual table and methods (adv_flow), put in slot 0 only while it is due "
    "(t_list adds no entry). "
    "\"Swim towards the dolphins\": rand(100) < 50 the hunt -- Farming (float +0x1C5C) +200 capped at 100.0, as the "
    "game's own skill adder 0x46AD80 caps (the double 100.0 at 0x48A7C0) -- and a large food award (the game's range "
    "x 2, then Island Events Scale, through 0x41D920), else the tail slap: health (+0x1C40, 0..100, in the block "
    "+0x1C34) minus 30 to 50, never below 1, through the game's own setter 0x46AF00 (value, cause -1: never its death "
    "path). \"Hang back\": a small food award (the range x 1 / 2, then Island Events Scale). The effects are made "
    "when the ending's last page is shown, with the event's one Island Events log entry. No site of its own.")
MASK_DESCRIPTION = (
    " And The Mysterious Mask (The Tree of Life only): a group of 2 to 4 children under 14 finds a strange carved mask "
    "at the edge of the forest, and the player picks one of four answers: \"Wait for their parents to come\" or \"Cry "
    "for help\" (the children are safe), \"Walk towards the clearing\" or \"Walk towards the forest\" (the same odds: "
    "home safe 50%, else lost -- then rescued 75% or captured 25%, when every child of the group is gone for good, no "
    "graves). The elders' speech tells what happened, and in every ending five volunteers of 18 or more leave on an "
    "expedition for good (no graves). It needs a population of 61 or more (the living plus the babies carried), two "
    "children under 14 and five villagers of 18 or more who are not nursing a baby and not a body or a ghost; "
    + RARE + ".")
MASK_BEHAVIOUR = (
    "The Mysterious Mask (The Tree of Life): the group is 4 children under 14 (+0x1B8C < 280), or all of them when "
    "fewer (at least 2), the expedition 5 villagers of 18 or more (vv4_eligible and +0x1B8C >= 360), each drawn among "
    "those left; everyone passes adv_is_protected (nursing +0x1C4C, a body or ghost +0x1CC7); the population 61 or "
    "more counted as the game's own 0x467610 counts (present +0x1CC4, not a body +0x1CC7, health +0x1C40 > 0, plus "
    "the babies +0x1C50 while carrying +0x1C4C). One more object with the Adventurer's virtual table and methods "
    "(adv_flow, answers 4: the shared multi-answer popup native/shared/vvfp_multi_answer.h, ids 4 and 5 and the keys "
    "1 to 4), put in slot 0 only while it is due (t_list adds no entry). A walk: rand(100) < 50 home safe, else lost: rand(100) < 25 "
    "captured, else rescued. Its pages are laid out 6 lines shorter (3 for each answer past two) so the popup is no "
    "taller than a two-answer one. The five volunteers, and when captured every child of the group, are removed as a "
    "living villager is (adv_vv345.inc t_vanish: no body, no grave; told to Cause of Death) when the elders' last page "
    "is shown, with the event's one Island Events log entry. No site of its own.")

CEREMONY_PLACES = {
    1: "at the cemetery, \"Honoring the Dead\"",
    2: "at the memorial, \"Honoring the Dead\" or \"Reflecting\" (half the time each)",
    3: "at the graveyard, \"Honoring the Dead\" or \"Reflecting\" (half the time each)",
    4: "at the graveyard, \"Honoring the Dead\"",
    5: "at the mausoleum, \"Honoring the Dead\" -- or, with \"Memorial Actions Can Also Occur at the Heathen Hovel\" "
       "installed, half of them at the old Heathen hovel instead, \"Honoring the Dead\" or \"Reflecting\" (half the "
       "time each)",
}
RUMBLING_STRUCTURES = {
    1: "the second and third population huts (the first, \"The Hut\", is a puzzle and is never damaged)",
    2: "the three population huts (the Lovely Hut, the Hospital and the Sewing Hut are puzzles and are never damaged)",
    3: "the three population huts and the clothing hut",
    4: "the three population huts, the clothing hut, the love shack, the nursery school and the hospital",
    5: "the three population huts, the clothing hut and the love shack (the nursery school is left out)",
}
CEREMONY_WHEN = {
    1: "at least one grave", 2: "at least one grave", 3: "at least one grave", 4: "at least one grave",
    5: "at least one grave and The Last Heathen done (every Heathen converted and the hovel fixed up)",
}
CEREMONY_SITES = {
    1: "its own case past the island events' 15, the chooser's first answer only while it is due (the stock "
       "rand(15) otherwise, untouched), through two sites of its own",
    2: "its own case past the single-result events' 28, the chooser's first answer only while it is due (the stock "
       "rand(28) otherwise, untouched), through two sites of its own",
    3: "in slot 0 only while it is due (t_list adds no entry), no site of its own",
    4: "in slot 0 only while it is due (t_list adds no entry), no site of its own",
    5: "in slot 0 only while it is due (t_list adds no entry), no site of its own",
}


def ceremony_description(game: int) -> str:
    return (
        " And The Remembrance Ceremony and The Rumblings (all five games; one popup each, OK only). The Remembrance "
        "Ceremony needs " + CEREMONY_WHEN[game] + ": everyone joins in -- children, nursing mothers and fathers, "
        "everyone" + (" who believes" if game == 5 else "") + " -- each " + CEREMONY_PLACES[game] + ", and the feast "
        "quietly uses 10 food for every villager (never below 0). The Rumblings needs every puzzle solved and a finished "
        + ("hut" if game in (1, 2) else "structure") + ": an earthquake damages each of " + RUMBLING_STRUCTURES[game]
        + " one time in four (at least one always), each losing 10 to 100% of its building work; the builders must "
        "build it again (at 100% it is unbuilt again, as in a new village" + ("; an unbuilt one can be moved" if game in
        (4, 5) else "") + "). Nobody is hurt; a village over its limit keeps everyone and has no new births until it is "
        "rebuilt. Each can come again.")


def ceremony_behaviour(game: int) -> str:
    return (
        "The Remembrance Ceremony and The Rumblings (ceremony_core.inc, ceremony_games.inc): each " + CEREMONY_SITES[game]
        + "; the game's own single-result popup shows the owner's words, the effects are made as it is built, with the "
        "event's one Island Events log entry. The Remembrance Ceremony: needs " + CEREMONY_WHEN[game] + " (the game's "
        "own grave count); every living, present villager" + (" who is a believer" if game == 5 else "") + " is "
        "started on its own through the game's own stop and action starter, as its Day of Honor starts each one (so no "
        "group filter leaves anyone out), " + CEREMONY_PLACES[game] + "; the feast uses 10 food for every villager the "
        "game counts, never below 0 (Blessings Day's own rule). The Rumblings: needs every puzzle of the game's Puzzles "
        "screen solved and one of " + RUMBLING_STRUCTURES[game] + " finished; each finished one rand(100) < 25 (none: "
        "one of them at random), each losing 10 + rand(91) percent of its building work, written as the states the "
        "game's own construction passes through (at 100% the new village's state)"
        + ("; the building's effect handle freed and set to -1" if game >= 3 else "")
        + ("; the nursery school's teacher let go" if game == 4 else "")
        + ("; a damaged population hut's count of the still-locked \"3 huts\" trophy taken back (saved with the "
           "village at the state's +0x328), so it still needs three different huts" if game in (4, 5) else "") + ".")


DLL_NAME = "VVFP More Island Events.dll"
INSTALLED_BY = f"{DLL_NAME}, VvfpStartup (started by VVFP Startup.dll, second word)"
NAME = "More Island Events"
CLASSIC = (4, 5)

# (va, stock bytes, written, what) per game.
SITES = {
    1: (
        (0x4189F2, "E829FFFFFF", "E8XXXXXXXX",
         "the encounter setup 0x4189E0's call of its roller 0x418920: while one of the events is due (Story / Cheat "
         "Upgrades' rare roll or Pick Island Event) and can happen, it is taken instead; otherwise the companion calls "
         "the roller as before (the stock draws, untouched)"),
        (0x41939D, "0F87D70F0000", "E9XXXXXXXX90",
         "the answer's resolve 0x419380, past its stock kinds (ja 0x41A37A): the event's own kind is answered by the "
         "companion (the effects and the first result page, or The Cave Explorers' next question); every other kind "
         "goes on as before"),
        (0x41A3EE, "E8BD25FFFF", "E8XXXXXXXX",
         "OK's close in the encounter click handler 0x41A3D0: while the event has a page left it is shown instead"),
        (0x41A87C, "E8FF02FFFF", "E8XXXXXXXX",
         "the encounter constructor's attaching of its second answer: a question of more than one page starts on its "
         "first page, with OK"),
        (0x423A06, "E8A54C0000", "E8XXXXXXXX",
         "the trigger's call of the island event's constructor 0x4286B0 for the island family (type 2): for that one "
         "call, only while The Remembrance Ceremony or The Rumblings is due, the chooser's draw 0x4284DB (the game's "
         "rand, or Story / Cheat Upgrades' own roll) is pointed into the companion and put back after: its first "
         "answer is the due event's case, every other the stock rand(15); with nothing due the call is the stock one"),
        (0x4284E7, "83FF0E77EA", "E9XXXXXXXX",
         "the chooser 0x428470's `cmp edi, 0xE; ja` past its 15 cases: a draw of 15 or more is one of the two events "
         "(its text written into the event's own buffer +0x277F, its effects made, the chooser's own ending 0x428630); "
         "every other draw goes on as before"),
    ),
    2: (
        (0x41F792, "E8D9FDFFFF", "E8XXXXXXXX",
         "family A's setup 0x41F780's call of its chooser 0x41F570: only while one of the events is due (Story / "
         "Cheat Upgrades' rare roll or Pick Island Event), for that one run the draw's call 0x41F59D (the game's rand, "
         "or Story / Cheat Upgrades' own roll) is pointed into the companion and put back after: its first answer is "
         "the due event's number, every other the stock rand(22); with nothing due the draw's bytes stay stock"),
        (0x41F5AC, "0F87E4000000", "0F87XXXXXXXX",
         "family A's draw 0x41F570: 21 (The Aspiring Adventurer) or 22 (The Climb) is kept only when it is the due "
         "event just drawn; a stock draw of 21 is drawn again, as in the stock game"),
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
        (0x42F0F7, "E8E4570000", "E8XXXXXXXX",
         "the trigger's call of the single-result constructor 0x4348E0 (type 2): only while The Remembrance Ceremony "
         "or The Rumblings is due, for that one call the chooser's draw 0x434607 (the game's rand, or Story / Cheat "
         "Upgrades' own roll) is pointed into the companion and put back after: its first answer is the due event's "
         "case, every other the stock rand(28); with nothing due the call is the stock one"),
        (0x43462C, "0F87F2010000", "E9XXXXXXXX90",
         "the single-result chooser 0x434570's `ja` past its 28 cases: a draw of 28 or more is one of the two events "
         "(its text written into the event's own buffer +0x277F, its effects made, the chooser's own ending "
         "0x434842); every other draw goes on as before"),
    ),
    3: (
        (0x419B6E, "83FE3A7CE1", "E9XXXXXXXX",
         "the selector 0x419B30's loop end over the event table 0x4B3C78 (slots 1-57): no entry is added to the "
         "selector's list (the stock draw, untouched); the due event's object is put in slot 0 for Story / Cheat "
         "Upgrades' pick to present"),
        (0x419A18, "8B4E508B01", "E9XXXXXXXX",
         "the event dialog's click handler 0x419A00, OK: while the event has a page left it is shown instead"),
        (0x419BEA, "E801F7FFFF", "E8XXXXXXXX",
         "the selector's call of the dialog constructor 0x4192F0: after it, a question of more than one page starts on "
         "its first page, with OK"),
    ),
    4: (
        (0x418070, "83FE327CDB", "E9XXXXXXXX",
         "the selector 0x418000's loop end over the event table 0x4CCA28 (slots 1-49): no entry is added to the "
         "selector's list (the stock draw, untouched); the due event's object is put in slot 0 for Story / Cheat "
         "Upgrades' pick to present"),
        (0x417EB8, "8B4E508B01", "E9XXXXXXXX",
         "the event dialog's click handler 0x417EA0, OK: while the event has a page left it is shown instead"),
        (0x418106, "E885F6FFFF", "E8XXXXXXXX",
         "the selector's call of the dialog constructor 0x417790: after it, a question of more than one page starts on "
         "its first page, with OK"),
    ),
    5: (
        (0x4188E0, "83FE387CDB", "E9XXXXXXXX",
         "the selector 0x418870's loop end over the event table 0x4DC850 (slots 1-55): no entry is added to the "
         "selector's list (the stock draw, untouched); the due event's object is put in slot 0 for Story / Cheat "
         "Upgrades' pick to present"),
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
    1: "rare and separate: it never takes a share of the game's own draw (the stock island events' chances never "
       "change); after a natural island event, Story / Cheat Upgrades' separate rare roll may bring one of these "
       "events (or an Isola Grand Event Collection event) between two natural ones, never in trouble and never in "
       "place of a rescue, and Pick Island Event can pick it; it comes as one of the villager encounters, never the "
       "village's first island event",
    2: "rare and separate: it never takes a share of the game's own draw (the stock island events' chances never "
       "change); after a natural island event, Story / Cheat Upgrades' separate rare roll may bring one of these "
       "events (or an Isola Grand Event Collection event) between two natural ones, never in trouble and never in "
       "place of a rescue, and Pick Island Event can pick it; it comes as one of the two-choice island events, never "
       "the village's first island event",
    3: "rare and separate: it never takes a share of the game's own draw (the stock island events' chances never "
       "change); after a natural island event, Story / Cheat Upgrades' separate rare roll may bring one of these "
       "events (or an Isola Grand Event Collection event) between two natural ones, never in trouble and never in "
       "place of a rescue, and Pick Island Event can pick it",
    4: "rare and separate: it never takes a share of the game's own draw (the stock island events' chances never "
       "change); after a natural island event, Story / Cheat Upgrades' separate rare roll may bring one of these "
       "events (or an Isola Grand Event Collection event) between two natural ones, never in trouble and never in "
       "place of a rescue, and Pick Island Event can pick it",
    5: "rare and separate: it never takes a share of the game's own draw (the stock island events' chances never "
       "change); after a natural island event, Story / Cheat Upgrades' separate rare roll may bring one of these "
       "events (or an Isola Grand Event Collection event) between two natural ones, never in trouble and never in "
       "place of a rescue, and Pick Island Event can pick it",
}


def description(game: int) -> str:
    classic = ("Off by default; part of Classic VV Difficulty; Owner's Defaults ticks it."
               if game in CLASSIC else "Off by default; Owner's Defaults ticks it.")
    return (
        "Adds new island events, written by the owner, beside the game's own (more come in later versions). "
        + ("Four here: " if game in (1, 2) else "Five here: " if game in (3, 4) else "Three here: ")
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
        "Deaths log. The popups show the owner's text in pages that fit the screen (OK shows the next) -- with Scrolling "
        "Popups installed, one scrolling popup for the question and one for each answer's result; the effects wait "
        "for the page that tells them, and the Island Events log keeps one entry for each event."
        + (CAVE_DESCRIPTION if game == 1 else CLIMB_DESCRIPTION if game == 2 else TROUBLING_DESCRIPTION + DIVE_DESCRIPTION
           if game == 3 else DOLPHIN_DESCRIPTION + MASK_DESCRIPTION if game == 4 else "")
        + ceremony_description(game) + " Pick Island Event lists each of these events and picks one whenever its own "
        "requirements hold (otherwise it says what the event needs). " + classic
        + " **Needs Story / Cheat Upgrades (on by default), which runs the rare roll and Pick Island Event; ticking "
        "this ticks it.** "
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
        "dependencies": [f"vv{game}_story_cheat_upgrades"],
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
        ] + ([CAVE_BEHAVIOUR] if game == 1 else [CLIMB_BEHAVIOUR] if game == 2 else [TROUBLING_BEHAVIOUR, DIVE_BEHAVIOUR]
             if game == 3 else [DOLPHIN_BEHAVIOUR, MASK_BEHAVIOUR] if game == 4 else [])
        + [ceremony_behaviour(game)],
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
                               "tests/test_the_climb.py)" if game == 2 else
                               " (The Troubling Signs: who, the draw, all four answers by mouse and key, the effects on "
                               "the last page, the log entry, the words and the four buttons, in "
                               "tests/test_troubling_signs.py; Diving for Treasure: who, every branch at its odds, "
                               "every effect on the last page, the log entry, the words and the draw with 1, 2 and 3 "
                               "events, in tests/test_diving_for_treasure.py)" if game == 3 else
                               " (The Playful Dolphins: who, both branches at their odds, Farming 100, the awards, the "
                               "health loss that never kills, the effects on the last page, the log entry, the words "
                               "and the draw, in tests/test_playful_dolphins.py; The Mysterious Mask: who, the 61 / 60 "
                               "population, 1 / 2 children, 4 / 5 adults, all four answers by mouse and key, each "
                               "elders' speech, both disappearances, the effects on the last page, the log entry, the "
                               "words and the four buttons, in tests/test_mysterious_mask.py)" if game == 4 else "")
                            + "; The Remembrance Ceremony and The Rumblings: the conditions, the draw, everyone sent "
                            "and where, the feast, the damage and its states, the log entry and the words, in "
                            "tests/test_ceremony_and_rumblings.py"
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
