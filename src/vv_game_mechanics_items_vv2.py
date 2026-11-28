"""Game Mechanics, The Lost Children (VV2): every technology, puzzle, building, item and patcher upgrade, each with what
it costs or how it is earned and exactly what it does (the owner, 2026-10-27: "Elaborate on what every store item and
upgrade and research and everything does!!!").

The same shape as src/vv_game_mechanics_items_vv1.py (Entry, ENTRIES, item_facts, ITEMS_GROUP, the labels).

THE STOCK EXE: research\\stock-executables\\Virtual Villagers - The Lost Children.exe (724,992 bytes).  State offsets
below are the game's (a save's file offset is 4 more).  Tech levels: Culture +0x2EA74, Science +0x2EA7C, Engineering
+0x2EA84, Medicine +0x2EA8C, Exploration +0x2EA94, Farming +0x2EA9C (each reset to 1 at 0x425229; at most 3); tech
points +0x2EADC.  The tech screen's buy handler is 0x4437F0..0x443A2C (the price of level 2, then of level 3, for each
technology); the drop handler 0x42FB20; the builders' dispatcher 0x45FE85..0x46028A; the completion callbacks 0x461B10
(table 0x4642F4); the stew 0x461040 (table 0x461510).
"""
from __future__ import annotations

import vv_game_mechanics as gm
from vv_game_mechanics_items_vv1 import KINDS, Entry, TECH, PUZZLE, BUILDING, ITEM, PATCHER

GAME = 2
ITEMS_GROUP = "Technologies, items and buildings"

C, E, O, U = gm.CODE, gm.RUNNING, gm.OWNER, False

# 0x44380A..0x443A13: (level 2, level 3) for each technology.
TECH_COSTS = {"Farming": (1_500, 90_000), "Exploration": (10_000, 160_000), "Science": (16_000, 150_000),
              "Medicine": (20_000, 65_000), "Engineering": (5_000, 75_000), "Culture": (20_000, 85_000)}
# The game's own titles (its tech tooltips' English strings, 0x82EA8..0x83498).
TECH_TITLES = {"Farming": "Farming Technology", "Exploration": "Exploration Technology",
               "Science": "Science Technology", "Medicine": "Medicine Technology",
               "Engineering": "Engineering Technology", "Culture": "Culture"}


def _buy(tech: str, level: int) -> str:
    cost = TECH_COSTS[tech][level - 2]
    return (f"{tech} level {level}: {cost:,} tech points on the Tech screen (from level {level - 1}); the points are taken "
            "at once and the level is never lost.")


# Level 1 of each technology, its own entry like The Secret City's to New Believers' (the owner, 2026-10-27: "Same
# between the virtual villagers games"): what a new village has before anything is bought.  Every line restates, for
# level 1, a reading cited under that technology's level 2 and 3 below.  "a new village's level": every technology
# is set to 1 for a new village (0x425229), as The Secret City's line words it.
LEVEL_ONE = "a new village's level, no price."

TECHNOLOGIES = (
    Entry(TECH, "Every technology", (
        ("The Lost Children has six: Farming, Exploration, Science, Medicine, Engineering and Culture. A new village "
         "starts each at level 1; 3 is the top level. The levels change nothing else than the effects listed under "
         "each one.", C),
        # docs/hidden-gates-all-five-games.md, VV2 5.1: the research dispatcher case 0x45FE6A has no tech-level gate.
        ("Research goes on at every level: no technology level stops it.", C),
    )),
    Entry(TECH, "Farming level 1", (
        (LEVEL_ONE, C),
        # 0x45FD1B..0x45FDC6 (coconuts from level 2), 0x430174 (the coconut trees' drop needs Farming >= 2).
        ("Farmers do not harvest coconuts, and a villager dropped on the coconut trees does not harvest them; the "
         "farmers' picks at every level are under Chances (Which food a farmer gathers).", C),
        # 0x42FC42..0x42FC72: Sustainable Fishing needs Farming 3.
        ("Sustainable Fishing cannot be started (it needs Farming level 3).", C),
    )),
    Entry(TECH, "Farming level 2", (
        (_buy("Farming", 2), C),
        # 0x45FD1B..0x45FDC6 (level 2), 0x45FD48 (more than 10 coconuts).
        ("Farmers can harvest coconuts (while the trees hold more than 10) and fish 81% of the time while the water "
         "is not fished out; the exact picks are under Chances (Which food a farmer gathers).", C),
        # 0x430174 (the coconut trees' drop): Farming >= 2 -> "Harvesting coconuts" 0x456F70.
        ("A villager dropped on the coconut trees harvests them (4 food a trip on Normal speed); below level 2 the "
         "drop does not start it.", C),
        ("Once Sustainable Fishing is solved, farmers fish with no limit from level 2 (Food sources).", E),
    )),
    Entry(TECH, "Farming level 3", (
        (_buy("Farming", 3), C),
        ("Farmers weigh fishing, coconuts and crops by whether the crops are ripe (Chances).", C),
        # 0x42FC42..0x42FC72: Sustainable Fishing not solved, Farming 3, Farming skill >= 88 or Research >= 88 ->
        # "Catching algae-eating fish!" 0x45D030.
        ("It is needed for Sustainable Fishing: a villager with Farming or Research skill 88 or more dropped in "
         "the water catches algae-eating fish.", C),
    )),
    Entry(TECH, "Exploration level 1", (
        (LEVEL_ONE, C),
        # 0x415FF5 (rand(100) < Exploration + 4 each 2 s), 0x4154B8 (mushroom below 65 - 15 x Exploration), 0x415D99
        # (rare below 2 x Exploration + 2, uncommon below 2 x Exploration + 14).
        ("Something appears on the ground 5% of each 2-second check (about 40 real-life seconds' wait; real time, "
         "the same at every speed, paused too); 50% of them are mushrooms; a collectible is rare 4% of the time, "
         "uncommon 12%, otherwise common. Exact odds under Chances.", C),
    )),
    Entry(TECH, "Exploration level 2", (
        (_buy("Exploration", 2), C),
        # 0x415FF5 (spawn: rand(100) < Exploration + 4 each 2 s), 0x4154B8 (mushroom below 65 - 15 x Exploration),
        # 0x415D99 (rare below 2 x Exploration + 2, uncommon below 2 x Exploration + 14).
        ("Something appears on the ground 6% of each 2-second check instead of 5% (about 33 real-life seconds' "
         "wait instead of 40; real time, at every speed, paused too); 35% of them are mushrooms instead of 50%; a "
         "collectible is rare 6% of the time instead of 4% (uncommon 12%). Exact odds under Chances.", C),
        # The cauldron: 0x419C20 registers map place 71 at Exploration >= 2 while +0x2E8A8 (found) and +0x2E8A4 (on
        # its way) are 0, and place 72 (The Cutting Tool's first spot) while +0x2E7A0 is 0; the hover 0x42AFED says
        # string 155 " sees something.".  The drop 0x42FDE3 -> 0x458810 ("Retrieving a cauldron", string 254;
        # callbacks 43 +0x2E8A4 + 1, then 42 +0x2E8A8 = 1).  The pot's drop 0x42FE78 does nothing until +0x2E8A8 is
        # set.  0x42F6F2..0x42F793: rand(100) < 30 sparkles (particle type 4, sparklestrip2.png) at both spots.
        ("Level 2 also lets your villagers find the cauldron for stews: while it is not found, a spot appears where "
         "a villager \"sees something.\", sparkling now and then; any villager dropped there goes \"Retrieving a "
         "cauldron\" and brings it back, and only then can stews be cooked (The Stew). The first spot for The "
         "Cutting Tool also appears only from level 2.", C),
    )),
    Entry(TECH, "Exploration level 3", (
        (_buy("Exploration", 3), C),
        ("Something appears 7% of each check (about 29 real-life seconds' wait; real time, the same at every "
         "speed, paused too); 20% of them are mushrooms; a collectible is rare 8% of the time (uncommon 12%).", C),
    )),
    Entry(TECH, "Science level 1", (
        (LEVEL_ONE, C),
        # Callback 31 0x46361B..0x463809: Research / 11 at Science 1 (/ 7 while catching up).
        ("Each successful research session gives Research ÷ 11 tech points (÷ 7 while catching up), rounded down -- "
         "nothing below Research 11; twice that on Fast speed, half on Slow when above 1, and a lit fire adds 1 more "
         "10% of the time.", C),
    )),
    Entry(TECH, "Science level 2", (
        (_buy("Science", 2), C),
        # Callback 31 0x46361B..0x463809.
        ("Each successful research session gives Research ÷ 9 tech points instead of ÷ 11 (÷ 6 instead of ÷ 7 while "
         "catching up), rounded down; twice that on Fast speed, half on Slow when above 1, and a lit fire adds 1 "
         "more 10% of the time.", C),
        # 0x457D48..0x457D70: the extra-trip path at rand(100) < 110 - 15 x Science; cosmetic.
        ("Researchers take the longer walking path less often (a roll of 0 to 99 below 110 - 15 x Science); both "
         "paths end in the same roll and pay.", C),
    )),
    Entry(TECH, "Science level 3", (
        (_buy("Science", 3), C),
        ("Research ÷ 5 (÷ 4 while catching up): a researcher of 50 gets 10 a session on Normal speed (4 at level 1, "
         "5 at level 2).", C),
        # 0x41C4E2: a picture drawn at Science >= 3.
        ("The village picture gains one more drawn piece at level 3; it changes nothing in play.", C),
    )),
    Entry(TECH, "Medicine level 1", (
        (LEVEL_ONE, C),
        # 0x43B2ED (sickness), 0x44F7A5 (conception rand(300) <= Parenting + 50 x Medicine - 50), 0x43BD73 (old age),
        # 0x43BCC9 / 0x43B361 (elderly from 840 + 160 x Medicine), 0x44BA6A (twins only at Medicine 3).
        ("Falling sick each age unit: 4 in 1,440 with the fire lit, 7 in 1,440 with it out (Chances: Falling sick); "
         "conception Parenting + 1 in 300 for the villager who started the embrace (Births and gender); elderly from "
         "50 years; old-age rolls from 55, death certain from 65 (Death and graves); no twins.", C),
    )),
    Entry(TECH, "Medicine level 2", (
        (_buy("Medicine", 2), C),
        # 0x43B2ED (sickness), 0x44F7A5 (conception rand(300) <= Parenting + 50 x Medicine - 50), 0x43BD73 (old age),
        # 0x43BCC9 / 0x43B361 (elderly from 840 + 160 x Medicine).
        ("Falling sick each age unit drops from 4 in 1,440 to 4 in 2,460 with the fire lit (7 in 1,440 to 7 in 2,460 "
         "with it out; Chances: Falling sick); conception gets 50 more in 300 (Parenting + 51 in 300 for the "
         "villager who started the embrace, Births and gender); elderly from 58 years instead of 50; old-age rolls "
         "from 63 instead of 55, death certain from 73 (Death and graves).", C),
    )),
    Entry(TECH, "Medicine level 3", (
        (_buy("Medicine", 3), C),
        ("Falling sick drops to 3 in 5,400 with the fire lit (5 in 5,400 with it out); conception Parenting + 101 in "
         "300; elderly from 66; old-age rolls from 71, death "
         "certain from 81.", C),
        # 0x44BA6A: twins 7%, a quarter of them triplets, only at Medicine 3.
        ("Twins and triplets become possible: 7% of conceptions are twins, and a quarter of those triplets (Births "
         "and gender).", C),
        # 0x4601DF (builders: the hospital needs Medicine 3), 0x4197DF (its site appears at Medicine 3 and
        # Engineering 3).
        ("It is needed for The Hospital: its site appears at Medicine 3 with Engineering 3.", C),
    )),
    Entry(TECH, "Engineering level 1", (
        (LEVEL_ONE, C),
        # 0x46012C..0x46028A: the thorns, the dam and the hospital need >= 2; the ruins, the vine wall and hut
        # examining need 3.  0x4307B0: the dam drop needs >= 2.
        ("Builders never work on their own on the briar thorns, the dam, the hospital, the ancient ruins or the vine "
         "wall, and never examine huts; a villager dropped on the dam site does not start it.", C),
    )),
    Entry(TECH, "Engineering level 2", (
        (_buy("Engineering", 2), C),
        # 0x46012C..0x4601E6.
        ("Builders work on their own on the thorns of the Overgrown Gong Piece (once the Cutting Tool is made and the "
         "work started), the dam (once started) and the hospital (Medicine 3 and the site worked once); below level "
         "2 they never do.", C),
        # 0x4307B0: the dam drop needs Engineering >= 2 -> "Building a dam" 0x45BA20.
        ("A villager dropped on the dam site builds the dam; below level 2 the drop does not start it.", C),
    )),
    Entry(TECH, "Engineering level 3", (
        (_buy("Engineering", 3), C),
        # 0x4601EC..0x46028A: ruins and vine wall (each needs Culture 3); hut examining only from here.
        ("Builders work on their own on the ancient ruins and the vine wall (each with Culture 3), and examine and "
         "fix huts (Hut repair).", C),
        # 0x43041C: the ruins drop needs Engineering 3 and Culture 3 -> "Uncovering ancient ruins" 0x45A000.
        ("A villager dropped on the ruins uncovers them (with Culture 3).", C),
        ("With Medicine 3 the hospital's site appears.", C),
    )),
    Entry(TECH, "Culture level 1", (
        (LEVEL_ONE, C),
        # 0x44F86F: rand(2) + 4 at Culture 1.
        ("A baby whose parents share the same best skill starts with 4 or 5 points in it (each 1 in 2); otherwise "
         "the baby's 5 to 7 is not changed (Hidden villager stats).", C),
        # 0x461A88..0x461ABE: rand(100) <= 3 x Culture.
        ("Culture activities: 4% of an adult's leisure picks that start nothing, at 4,000 food or more.", C),
    )),
    Entry(TECH, "Culture level 2", (
        (_buy("Culture", 2), C),
        # 0x44F86F: when both parents' best skill is the same, rand(2)+4 / rand(4)+5 / rand(5)+7 at Culture 1/2/3.
        ("A baby whose parents share the same best skill starts with 5 to 8 points in it (each 1 in 4) instead of "
         "4 to 5; otherwise the baby's 5 to 7 is not changed (Hidden villager stats).", C),
        # 0x461A88..0x461ABE: at 4,000 food or more, when the leisure pick 0x460C80 starts nothing, rand(100) <=
        # 3 x Culture (0x425850) sends the adult to 0x45F1B0.
        ("Culture activities: at 4,000 food or more, when an adult's leisure pick starts nothing, a roll of 0 to 99 "
         "at most 3 x Culture sends it to a culture activity: 7% at level 2 (4% at level 1, 10% at level 3).", C),
        # The culture pick 0x45F1B0: rand(100) <= 50 returns 0 (the caller 0x461AC7 then goes on as if the culture
        # roll had failed); else rand(6), table 0x45F2F4: 0 Reflecting 0x4523A0, or with a grave (0x426160, the 50
        # graves +0x2EB80) 0x454890 Honoring the Dead / Reflecting at rand(100) < 50; 1 0x457AA0 only with +0x2E7B8;
        # 2 0x459710 only with +0x2E7E0; 3 0x45CB40(1) Enjoying the pond; 4 0x455A20 Rain dancing and 5 0x4530E0
        # the circle dance, each skipped by a dislike of word 0x28 (dancing, 0x4454E0).  A skipped pick starts
        # nothing that time.
        ("A culture activity is then rolled again: 51 times in 100 nothing comes of it and the adult's leisure goes "
         "on as if there had been no culture roll; otherwise one of six, each 1 in 6: Reflecting (while the village "
         "has a grave, Honoring the Dead or Reflecting, 1 in 2 each); Admiring the ancient mosaic (only once The "
         "Ancient Mosaic is solved); Admiring the ancient gong encasement (only once The Overgrown Gong Piece is "
         "solved); Enjoying the pond; Rain dancing; a long dance in a circle (the two dances not for a villager who "
         "dislikes dancing). A pick that cannot happen starts nothing that time.", C),
        # 0x426180 kind 7 (Culture >= 2 and Science >= 2): 0x419B16 registers map place 59, the Sewing Hut's
        # building site, while that holds or once its progress +0x2E78C is above 0; the drop on place 59 (0x430305)
        # starts "Building a sewing hut" 0x457130 (7).
        ("With Science level 2 as well, the sewing hut's building site appears: a villager dropped on it starts "
         "\"Building a sewing hut\" (The Sewing Hut).", C),
    )),
    Entry(TECH, "Culture level 3", (
        (_buy("Culture", 3), C),
        ("A baby whose parents share the same best skill starts with 7 to 11 points in it (each 1 in 5).", C),
        ("Culture activities 10% of those picks.", C),
        ("It is needed, with Engineering 3, for the ancient ruins (The Ancient Mosaic) and the vine wall (The Vine "
         "Wall).", C),
    )),
)

PUZZLE_ENTRIES = (
    Entry(PUZZLE, "Fire", (
        # Gathering dry grass 0x457FB0 (callback 64: +0x30458 = 1) and firewood 0x4581D0 (callback 65: +0x30459 =
        # 1); the pit's drop 0x42FCBA: no wood -> string 40, no grass -> string 42, burning -> nothing, a dislike of
        # fire (word 0x32) -> runs away, else "Starting a fire" 0x458390; callback 2 (0x462558) clears both, lights
        # the fire, sets its end (Fast / Normal / Slow) and the Fire flag +0x2E768.
        ("Solved the first time the fire is lit: drop a villager on the dry grass (\"Gathering dry grass\") and one "
         "on the dry wood (\"Gathering firewood\") to put both in the pit, then one on the pit (\"Starting a "
         "fire\"); lighting uses both up. Without wood the pit says \"There is no firewood here.\", without grass "
         "\"Some dry grass would help the fire ignite.\"; a villager who dislikes fire runs away instead.", C),
        ("Reward: a fire that burns 10, 20 or 40 real-life hours when lit on Fast, Normal or Slow (a later speed "
         "change rescales what is left; a pause pushes it on; it burns down while the game is closed); fuel on a "
         "burning fire "
         "fills it to that again (Other).", E),
        ("While it burns: a villager falls sick half as often; on Medium and Hard a failed health roll gets a second "
         "roll; each successful research session gives 1 more tech point 10% of the time (Chances).", E),
    )),
    Entry(PUZZLE, "The Scarecrow", (
        # Callback 3 (0x4623F6): +1 to +0x2E76C a completion; solved at 2.
        ("Solved by building the scarecrow (\"Building a scarecrow\") twice to completion.", C),
        ("Reward: the birds never eat the young crops again (Food sources: The birds).", E),
    )),
    Entry(PUZZLE, "The Elder Totem", (
        # 0x44D19B..0x44D1AF: the first Esteemed Elder sets +0x2E778.
        ("Solved when the first villager becomes an Esteemed Elder: 3 of its 5 skills at 88 or more (checked about "
         "every 2 real-life seconds, real time).", E),
        ("Reward: every Esteemed Elder gets a totem statue (Village counts).", E),
        ("With the patcher (Esteemed Elders' Totems Use No Villager Records, on by default): the totems are kept in "
         "a file beside the save and take none of the 256 villager records, and there is no limit of 50.", C),
    )),
    Entry(PUZZLE, "The Hospital", (
        # Callback 5 (0x462F4B): 1,200 (0x4B0) sets +0x2E780.
        ("Solved by building the hospital: 1,200 progress (2 a successful trip, 1 while catching up). Needs "
         "Medicine 3 and Engineering 3 for its site, Engineering 2 for builders.", C),
        # 0x43BCBD: with the hospital every age unit gives +1 health (food, not sick).
        ("Reward: the health roll always passes: every age unit a villager who is not sick, while there is food, "
         "regains 1 health on every difficulty (an elderly villager's own further roll is under Chances: Regaining "
         "health). It does not change the odds of falling sick.", E),
        ("A sick villager dropped on it goes \"Recovering at the hospital\", which in the original game neither "
         "cures nor heals.", C),
        ("With the patcher (Hospital Recovery Heals, on by default): finishing \"Recovering at the hospital\" gives "
         "exactly 1 health, up to 100.", C),
    )),
    Entry(PUZZLE, "Herb Mastery", (
        # Callbacks 33-38 (0x4627AA..0x462941) set the six plants +0x2E860..+0x2E888; 34 sets +0x2E788 when all six
        # are set.  The first understanding of each plant gives the healer +5 Healing.
        ("Solved by understanding all six strange plants, each by a villager dropped on it (one who dislikes herbs "
         "refuses). The first understanding of each plant gives that villager 5 Healing.", C),
        ("Reward: every cure also gives 10 to 29 health (each amount 1 in 20), up to 100.", E),
        ("With the patcher (Easier Healing Mastery, on by default): healers with no patient study plants on their "
         "own, catch-up included (75% of those times for a villager checked on Healing, 14% for one not checked "
         "on Healing). With Healers Study Plants Regardless "
         "of Food (on by default): a studying villager carries on at 300 food or more, 50% of the time.", C),
        # The continuation 0x460590 picks rand(4) among herbs 1, 2, 5 and 6 (0x4606A1; VVFP Herb Study.dll: rand(6)).
        ("In the original game a villager carrying on with plant study never studies the third or fourth herb "
         "again. With the patcher (Fix Vanilla Bugs): all six can be studied again, each a Healing practice roll.",
         C),
        ("With the patcher (Villagers Work Their Own Job First): once Herb Mastery is solved, a healer with nothing "
         "else to do studies one of the six plants on their own, about three times in four (never one who "
         "dislikes herbs).", C),
    )),
    Entry(PUZZLE, "The Sewing Hut", (
        # Callback 7 (0x46305D): 400 (0x190) sets +0x2E790, +1 a trip.
        ("Solved by building the sewing hut: 400 progress (1 a successful trip, also while catching up).", C),
        # The drop on the finished hut (place 14, 0x43034C): 5,000 tech points or more -> the question string 821
        # (0x42EAD7), yes -> "Getting new clothes!" 0x45CEB0, whose callback 69 (0x461C1B) takes the 5,000 at the hut
        # (below 5,000 then: string 146) and opens the clothes window 0x4229D0 (left and right arrows); below 5,000
        # at the drop: string 146.  Nothing else reads +0x2E790 in play.
        ("Reward: a villager dropped on the sewing hut can get new clothes for 5,000 tech points: the game asks "
         "\"Do you want to spend 5000 tech points to change this villager's clothes?\", the villager walks to the "
         "hut (\"Getting new clothes!\"), the points are taken when it gets there, and a window with arrows opens "
         "to pick its new clothes. Below 5,000: \"Not enough tech points to make new clothes!\"", C),
    )),
    Entry(PUZZLE, "The Dam", (
        # Callback 8 (0x464168): 425 (0x1A9) sets +0x2E798, the crops to 0 and the next regrowth to now + speed x
        # 2,400 / 4 (paused counts as Normal).
        ("Solved by building the dam: 425 progress (2 a successful trip, 3 at Building 88 or more; 1 or 2 while "
         "catching up). Drop a villager on the site at Engineering 2 to start it.", C),
        ("Reward: the crop field: farmers plant and harvest (7 food a trip on Normal speed) and each regrowth fills "
         "it to 800 while the birds stay away; the pebbles collection opens. On completion the crops start at 0 and "
         "the next regrowth comes 30 minutes, 1 hour or 1 hour 40 minutes of real-life time later (Fast, Normal, "
         "Slow).", C),
    )),
    Entry(PUZZLE, "The Cutting Tool", (
        # Callback 9 (0x461F69) sets +0x2E7A0; "Creating cutting tools" 0x458440 / 0x4585B0.
        # Place 72 (registered at Exploration >= 2 while unsolved, 0x419C6A): the drop 0x42FD90 -> Research +0x7F4
        # >= 88 -> 0x458440 (callback 9 sets the progress +0x2E79C to 1, then string 168), below -> string 44; with
        # the progress set -> string 168.  Place 32 (the flexible wood, hover string 167): the drop 0x43004C with
        # the progress set and the held villager's Research >= 88 -> 0x4585B0, whose callback 9 sets +0x2E7A0.
        ("Solved in two drops, from Exploration level 2: a spot appears where a villager \"sees something.\"; a "
         "villager with Research 88 or more dropped there goes \"Creating cutting tools\" and the game says "
         "\"Special wood is needed to finish the tool.\" (below 88: \"Maybe a skilled scientist would understand "
         "these.\"). Then a villager with Research 88 or more dropped on the flexible pieces of wood goes "
         "\"Creating cutting tools\" again and finishes it.", C),
        ("Reward: builders can cut away the briar thorns (The Overgrown Gong Piece) at Engineering 2.", C),
    )),
    Entry(PUZZLE, "The Stew", (
        # 0x426017..0x426056 (the cook routine 0x425B90): the first stew cooked sets +0x2E7A8.
        ("Solved by the first stew cooked in the pot.", C),
        ("Reward: stews (see Stews).", C),
    )),
    Entry(PUZZLE, "The Vine Wall", (
        # Callback 11 (0x463FFF): 1,000 sets +0x2E7B0.
        ("Solved by removing the vines: 1,000 progress (2 a successful trip, 3 at Building 88 or more; 1 or 2 while "
         "catching up). Needs Engineering 3 and Culture 3.", C),
        # The wall's drop 0x42FF31 once +0x2E7B0 is set: 0x459A50 ("Reading the writings on the wall", string 270)
        # and the pop-up 0x1BF (447, "The Ancient Writings").  Play reads +0x2E7B0 nowhere else (0x42C03F is the
        # hover, 0x426222 the all-puzzles check).
        ("Reward: the writing behind the vines can be read: a villager dropped on the wall goes \"Reading the "
         "writings on the wall\" and the game shows \"The Ancient Writings\", the story of the Gong of Wonder.", C),
    )),
    Entry(PUZZLE, "The Ancient Mosaic", (
        # Callback 12 (0x462960): 5,000 (0x1388) sets +0x2E7B8; +1 a trip, +1 more at Building 88, the same while
        # catching up.
        ("Solved by uncovering the ancient ruins: 5,000 progress (1 a successful trip, 2 at Building 88 or more). "
         "Needs Engineering 3 and Culture 3.", C),
        ("Reward: villagers admire the mosaic (and it is one of the culture activities).", C),
    )),
    Entry(PUZZLE, "The Boxed Gong Piece", (
        # Place 22 (the crate, until +0x2E7D0 is set, 0x419A8B): the drop 0x42FD3B -> Building +0x7E8 >= 88 ->
        # 0x454730 "Trying to open the crate" (string 848; a fourth gets string 849), else string 851; its callback
        # 15 (0x461C74) opens the crate (+0x2E7D0) when 3 or more living villagers over 280 age units are at it,
        # else string 850.  Place 74 (the open crate): the drop 0x42FD64 -> 0x451040 (callbacks 70, then 13 sets
        # +0x2E7C0).
        ("Solved by opening the washed-up crate: three villagers over 14 with Building 88 or more, each dropped on "
         "it (\"Trying to open the crate\"), must be at it at the same time -- fewer: \"It is too hard to do "
         "alone\"; a fourth: \"There is no more room to help out\"; below Building 88: \"Maybe a trained builder "
         "would be strong enough...\". Then a villager dropped on the open crate goes \"Retrieving a piece of the "
         "gong\" and brings it back.", C),
        ("Reward: one of the four pieces of the Gong of Wonder (Gong of Wonder).", C),
    )),
    Entry(PUZZLE, "The Sunken Gong Piece", (
        # The pond's drop 0x430012: +0x2E7C8 not set and the villager kept by stew 5 (+0x3045C) -> 0x450D50
        # "Retrieving something from the pond" (a dislike of swimming, word 0x25, -> runs away; callbacks 67, then
        # 14 sets +0x2E7C8).  It also needs +0x2E970 clear, a saved byte no code of the game writes.
        ("Solved with the breathing stew (stew 5, Stews): the last villager to eat it, dropped on the pond while "
         "the piece is still down there, goes \"Retrieving something from the pond\" and brings it up; one who "
         "dislikes swimming runs away instead.", C),
        ("Reward: one of the four pieces of the Gong of Wonder.", C),
    )),
    Entry(PUZZLE, "The Inlaid Gong Piece", (
        # Place 66 (0x41A175: The Ancient Mosaic solved, the piece not, +0x2E7D4 not 2) takes only a totem (+0x558,
        # 0x42FB45): 0x430382 sets +0x2E7D4 = 1 with sparkles; then a villager's drop there -> 0x451210 (callbacks
        # 68 +0x2E7D4 = 2, then 16 sets +0x2E7D8).  The patcher's totems DLL (native/vvfp_vv2_totems) does the same
        # for its own totems (drop(), terrain 0x42).
        ("Solved once The Ancient Mosaic is restored: drag an Esteemed Elder's totem onto the mosaic, which "
         "uncovers the piece; then a villager dropped there goes \"Retrieving a piece of the gong\" and brings it "
         "back.", C),
        ("Reward: one of the four pieces of the Gong of Wonder.", C),
    )),
    Entry(PUZZLE, "The Overgrown Gong Piece", (
        # Callback 17 (0x46389B): 3,000 (0xBB8) sets +0x2E7E0.
        ("Solved by cutting away the briar thorns: 3,000 progress (2 a successful trip, 3 at Building 88 or more; 1 "
         "or 2 while catching up). Needs The Cutting Tool and Engineering 2.", C),
        ("Reward: one of the four pieces of the Gong of Wonder, and the beetles collection opens.", C),
    )),
    Entry(PUZZLE, "Sustainable Fishing", (
        # Callback 18 (0x4626F0): +1 to +0x2E7E4, solved at 10.
        ("Solved by catching algae-eating fish 10 times: a villager with Farming or Research 88 or more dropped in "
         "the water at Farming level 3.", C),
        ("Reward: fishing goes on after the fish run out, with no limit from Farming level 2 (Food sources).", E),
    )),
)

BUILDINGS = (
    Entry(BUILDING, "The broken starting hut", (
        # Callback 1 (0x462A9D): 400 (0x190) sets +0x2E760; 1 a trip.
        # 0x460066..0x4600A7: rand(100) roll of 80% for it, before the huts.
        ("Builders turn to it first, on an 80% roll each time a builder's work is chosen and no project the player "
         "set comes first: 400 progress, 1 a successful trip.", C),
    )),
    Entry(BUILDING, "Population huts", (
        # Callbacks 24/25/26: 450 / 700 / 900 (0x1C2, 0x2BC, 0x384); the conception gate 0x44B310 (15 / 25 / 50, below
        # 90 + 5 a finished collection, 25 for all four); builders 0x4600B8..0x460102; sites 0x4196E8, 0x419763.
        ("Three huts: 450, 700 and 900 progress, 2 a successful building trip (1 while catching up); 2% of trips "
         "injure the builder (Chances).", C),
        ("15 people or more need the first hut, 25 the second, 50 the third before a baby is conceived (babies on "
         "the way counted); the population stays below 90, plus 5 for each finished collection (25 for all four).",
         C),
        ("Builders start the first hut at any population; the second's site appears at 21 people and the third's "
         "at 46, and builders work on the second only above 22 people and on the third only above 45, and only "
         "once someone has worked on it once (a villager you drop there).", C),
        ("With the patcher (Builders Fix Huts When Idle, on by default): once you have dropped a villager on the "
         "second or third hut, builders finish it at any population.", C),
    )),
    Entry(BUILDING, "Hut repair (Examining hut, Fixing hut)", (
        # 0x45FB4D..0x45FB73; 0x4575B0 queues only a Building roll.
        ("At Engineering 3 a builder examines a hut and finds work 70% of the time: a Building skill roll only, as "
         "huts never decay; otherwise \"This hut is still in good repair.\"", C),
        ("With the patcher (Builders Fix Huts When Idle, on by default): idle builders fix standing huts at any "
         "Engineering level while no building project is open; building always comes first.", C),
    )),
    Entry(BUILDING, "The hospital", (("1,200 progress (The Hospital).", C),)),
    Entry(BUILDING, "The dam", (("425 progress (The Dam).", C),)),
    Entry(BUILDING, "The sewing hut", (("400 progress (The Sewing Hut).", C),)),
    Entry(BUILDING, "The vine wall", (("1,000 progress (The Vine Wall).", C),)),
    Entry(BUILDING, "The ancient ruins", (("5,000 progress (The Ancient Mosaic).", C),)),
    Entry(BUILDING, "The briar thorns", (("3,000 progress (The Overgrown Gong Piece).", C),)),
    Entry(BUILDING, "The scarecrow", (("Two completed builds (The Scarecrow).", C),)),
    Entry(BUILDING, "The fire pit", (
        ("Dry grass and firewood, then the fire (Fire). Fuel on a burning fire fills it again; fuel does not light a "
         "cold pit (Other).", E),
        ("With the patcher (Firepit: Dry Grass Drawn Above the Wood, on by default): only the drawing order of the "
         "grass and the wood changes.", C),
    )),
)


# The stew 0x461040: the pot's stew number (1-18, +0x3044C) decides the effect on the villager who eats it.
STEW_EFFECTS = (
    "1: +1 health, up to 100.",
    "2: the eater falls sick.",
    "3: the eater's sickness is cured.",
    "4: -1 health (never below 3), and the eater stops what it was doing.",
    # 5: the eater is kept at +0x3045C, read by the water drops 0x42FC92 and 0x430029 (-> 0x450D50).
    "5: the breathing stew: the game remembers the last villager to eat it, who can then dive for The Sunken Gong "
    "Piece (dropped on the pond while the piece is still down there).",
    "6: the eater goes \"Exercising\" (Building practice).",
    "7: the eater goes \"Relaxing\".",
    "8: \"Nature is calling!\"",
    "9: the eater dances.",
    "10: +2 to +6 health (each 1 in 5), up to 100.",
    "11: \"Jumpy!\"",
    "12: the eater goes \"Getting a drink\".",
    "13: a short step, then \"Getting a drink\".",
    "14: a child under 14 dances, runs away or goes \"Jumpy!\" (each 1 in 3); an adult nothing.",
    "15: an adult of 18 or more, not sick and not nursing, goes to embrace (Parenting work).",
    "16: with skills adding up to 5 or more: half the time one random skill +2 to +5, otherwise the best skill -2 "
    "to -5 (never below 0).",
    "17: +50 to +99 health, up to 100, and sickness cured.",
    "18: -15 to -39 health, never below 3.",
)

def _stew_mixes(number: int) -> str:
    """The herb mixes that make stew `number` (src/vv_stew_recipes.py), "A + B + C; ..."."""
    import vv_stew_recipes as stews
    return "; ".join(" + ".join(stews.VV2_HERBS[herb][0] for herb in mix) for mix in stews.VV2_RECIPES[number])


ITEMS = (
    Entry(ITEM, "Mushrooms", (
        ("Brown mushroom 6 food; red (rare) mushroom 35 food, 1 in 10 of them. Every 2 real-life seconds "
         "something appears 5%, 6% or 7% of the time at Exploration 1, 2, 3, and 50%, 35% or 20% of what appears "
         "are mushrooms; it lies 75 real-life seconds (both real time, at every speed, paused too). Only a child "
         "under 14 dropped on it picks it up (Mushrooms).", E),
        ("With the patcher (Super-Secret Golden Mushroom, off by default): 1 in 1,000,000 of them is a Golden "
         "Mushroom worth 100 food.", E),
        ("With the patcher (VV1 Mushroom/Collectible Duplication Cheat, off by default): several children can be "
         "dropped on one mushroom or collectible, and it is multiplied: each of them gets it.", C),
        # The pick callbacks 0x3E / 0x3F remove the one item object whatever it is by then; Fix Vanilla Bugs reaches
        # them only when the map's area under the child is the item's own (tests/test_duplicate_pickups.py).
        ("With the patcher (Fix Vanilla Bugs, on by default): with several children on one item, each takes it only "
         "when it is standing on it; in the normal game a child picking after the first takes whatever mushroom or "
         "collectible is out by then, so a new one that has just appeared elsewhere vanishes with nothing for it.",
         C),
        # The mushroom job 0x45BCA0 queues its award (step 17, callback 39/40) right after the carry step 15
        # (data/builds.json vv2_collectibles_stay_collected: "VVFP Collectibles Stay Collected.dll"); stock: at the
        # end of the trip.
        ("With the patcher (Picked Up Collectibles Stay Collected When Dropped, off by default): a mushroom counts "
         "the moment the child picks it up -- its food and Mushrooms Found, once -- even if the child is moved or "
         "stops before the food bin (in the normal game it counts only at the end of the trip).", C),
        # The adult dispatcher's case 0x42FCAB (call 0x42FCAE, data/builds.json vv2_adult_confused).
        ("With the patcher (Adults Dropped on Mushrooms or Collectibles Are Confused, on by default): a villager of "
         "14 or more dropped on a mushroom is Confused and the message bar says \"Only children can see and pick up "
         "mushrooms.\" (in the normal game: \"Only children can see collectibles.\").", C),
    )),
    Entry(ITEM, "Collectibles", (
        ("Four collections of 12 pieces (4 common, 4 uncommon, 4 rare): butterflies and shells always, pebbles once "
         "The Dam is built, beetles once The Overgrown Gong Piece is solved; only a child under 14 dropped on one "
         "picks it up (Collectibles).", E),
        ("A piece already found pays 100, 250 or 1,500 tech points by rarity; each complete collection raises the "
         "population limit by 5, all four by 25.", E),
        # The collectible job 0x45BF10 queues its award (callback 41) right after the carry step.
        ("With the patcher (Picked Up Collectibles Stay Collected When Dropped, off by default): a piece counts the "
         "moment the child picks it up, with its messages, once, even if the child is moved or stops on the way.",
         C),
        # The adult dispatcher's case 0x42FCAB (call 0x42FCAE, data/builds.json vv2_adult_confused).
        ("With the patcher (Adults Dropped on Mushrooms or Collectibles Are Confused, on by default): a villager of "
         "14 or more dropped on a collectible is Confused and the message bar says \"Only children can see and pick "
         "up collectibles.\" (the normal game's own message is \"Only children can see collectibles.\").", C),
    )),
    # Each collection, its own entry as on The Tree of Life's and New Believers' tabs (the owner, 2026-10-27).  The pieces:
    # one found byte each at state 0x2E720 + piece, 12 a collection in the order 0, 12, 24, 36 (0x426120); the
    # pickup's completion messages 0x4634B3..0x46360E (each shown once, flags +0x20F..+0x213: Butterfly 0x4634DB,
    # Shell 0x463515, Beetle 0x46354F, Pebble 0x463589); the room check 0x44B310 (+5 for each complete collection,
    # 0x44B32E..0x44B375; 20 made 25 at 0x44B378).
    *(Entry(ITEM, f"{name} Collection", (
        (f"pieces {first + 1} to {first + 12} of the 48: 12 pieces (4 common, 4 uncommon, 4 rare); {opens}; only a "
         "child under 14 dropped on one picks it up, and the collection is drawn at random among the open ones "
         "(Chances).", E),
        (f"Completing it raises the population limit by 5; the game says \"{name} Collection ... Your village "
         "population maximum is increased by 5.\"", C),
    )) for name, first, opens in (
        ("Butterfly", 0, "it can appear from a new village on"),
        ("Shell", 12, "it can appear from a new village on"),
        ("Beetle", 24, "it appears only once The Overgrown Gong Piece is solved"),
        ("Pebble", 36, "it appears only once The Dam is built"))),
    Entry(ITEM, "All four collections", (
        # 0x44B378..0x44B37D: four complete collections count 25, not 20; 0x4635A7..0x46360E: the message, once.
        ("with all four complete the population limit is 25 higher (90 + 25 = 115); the fourth collection adds 10 "
         "(from 15 to 25), not 5.", C),
        ("Completing the fourth shows that collection's own message (\"increased by 5\") and then \"All Collections "
         "Complete! ... In addition to keeping the collections, your village population maximum is increased by "
         "10!\": the two messages say 15 for a rise of 10 (the code's figure is the one above).", C),
    )),
    Entry(ITEM, "Stews", (
        ("Cooked in the pot from water, food and herbs; ready the moment it is made and kept 15 real-life minutes "
         "(real time, the same at every speed; in the base game paused time counts too, Fix Vanilla Bugs "
         "pauses it; Other). Every villager who eats from it in that time "
         "gets its effect, once, at the moment it eats.", E),
        ("Adding food to the stew uses food; there are 18 stews, each told apart only by what it does.", C),
        # 0x461040, table 0x461510.
        ("What each stew does, by the game's stew number (one line each below):", C),
        *((f"Stew {effect}", C) for effect in STEW_EFFECTS),
        # Every one of the 56 three-herb mixes run through the cook routine 0x425B90 in the emulator
        # (src/vv_stew_recipes.py VV2_RECIPES, tests/test_game_mechanics_stews.py); stew 1 is its fall-through.
        ("Which 3 herbs make each stew, in any order (the herbs named by their flowers' colour, as in the "
         "patcher's Stew Recipes window; every mix not listed makes stew 1):", E),
        *((f"Stew {number}: {_stew_mixes(number)}.", E) for number in range(2, 19)),
        # data/builds.json vv2_empty_stew_pot ("VVFP VV2 Empty Stew.dll"): the drop 0x430AF9, the pot's own empty
        # 0x425B20 at the end of the walk; the stew's 10 food left at callback 46 (0x46236C).
        ("With the patcher (Empty the Stew Pot from the Science Hut Door, on by default): a villager of 14 or more "
         "dropped on the science hut's doorway while a ready stew is in the pot walks to the pot and empties it "
         "(\"Emptying the pot\"); a villager who dislikes cooking runs away instead, and a stew still being made "
         "is left alone. No food is lost or given back: the stew's 10 food was used when the food went in.", C),
    )),
    Entry(ITEM, "A snack (the food store)", (
        ("A villager below 100 health with food in store snacks: 1 food, +1 health 50% of the time (Chances: A "
         "snack).", E),
    )),
    Entry(ITEM, "Teaching children", (
        # docs/hidden-gates VV2 5.6: 0x44F9D0 (Parenting >= 50 -> 0x44A4E0, a Parenting roll); attendees under 14
        # gain nothing; below 50 "Telling a story" 0x449F40.
        ("An adult with Parenting 50 or more dropped on a child teaches the children: a Parenting skill roll for "
         "the teacher; in the original game the children gain nothing. Below 50 it tells a story instead.", C),
        ("With the patcher (Teaching Children Grants Skill, on by default): each child who finishes a lesson gains 7 "
         "to 9 points in one random skill; with Teaching Children Stops at 50 (on by default) only a skill below 50, "
         "and never past 50.", C),
    )),
    Entry(ITEM, "The Gong of Wonder", (
        ("Whole once its four pieces are found; rung by a villager dropped on it, then rests 24 real-life hours "
         "(real time, the same at every speed, paused or closed); its results are under Island events.", E),
        ("With the patcher (Gong of Wonder Coconuts Fix, on by default): a coconut result adds 30 to the coconut "
         "trees instead of setting them to 30.", C),
    )),
    Entry(ITEM, "Research", (
        ("Tech points for every technology: Research ÷ 11, ÷ 9 or ÷ 5 at Science 1, 2, 3 per successful session "
         "(Tech points and effects).", E),
    )),
)


def _origins(row: str, price: int, where: str, effect: str, sub: bool = False) -> str:
    """One Origins row; a sub-line (`sub`) leaves out the patch's name, which its entry's first line gives."""
    words = (f"\"{row}\" on the {where}, {price:,} tech points (0 with Story / Cheat Upgrades and its cost row "
             f"unticked): {effect}")
    return words if sub else ("With the patcher (Enable Origins Tech, Details, and Village-Wide Upgrades, on by "
                              "default): " + words)


# Prices: native/vv2_origins_icons/vv2_origins_icons.c (vv2_tech_action_costs, vv2_detail_action_costs) and
# data/vv2_origins_feature.json.
ORIGINS = (
    Entry(PATCHER, "Origins: Time Warp", (
        (_origins("Time Warp", 50_000, "Tech screen's Upgrades", "moves the village on 12 villager years on Fast, 6 "
                  "on Normal and 3 on Slow (12, 12 and 10 hours of real-life time), replayed by the game's "
                  "catch-up; refused while paused."), gm.CLAMP),
    )),
    Entry(PATCHER, "Origins: Island Event", (
        (_origins("Island Event", 30_000, "Tech screen's Upgrades", "queues one of the game's island events, which "
                  "comes a few real-life seconds after the Tech screen closes; while one is pending the row reads "
                  "\"Why not?\" and cannot be bought again. The game's island event timer is not changed."), C),
    )),
    Entry(PATCHER, "Origins: Barrel of Babies", (
        (_origins("Barrel of Babies", 75_000, "Tech screen's Upgrades", "the game's Barrel O' Babies with 3 "
                  "toddlers, queued like the Island Event; refused, free, without room for them (an unburied body "
                  "still takes a place)."), C),
    )),
    Entry(PATCHER, "Origins: Tech Point Doubler and Food Point Doubler", (
        (_origins("Tech Point Doubler / Food Point Doubler", 500_000, "Tech screen's Upgrades", "the Tech Point "
                  "Doubler doubles the tech points research earns (with the fire's extra point) and pieces of a "
                  "collection found again; the Food Point Doubler doubles the food gathered from food sources "
                  "(coconuts, crops, fish, the big catch and mushrooms). Island events, the Gong of Wonder, the Sack "
                  "and Vial, purchases and cheats are not doubled."), C),
    )),
    Entry(PATCHER, "Origins: Full Heal / Cure All", (
        # data/vv2_origins_feature.json, the Cure apply at 0x9A5CC: every record in use, alive and not a totem:
        # health below 100 -> 100; sick (+0x53C) -> cured and People Cured (+0x2E508) + 1.
        (_origins("Full Heal / Cure All", 30_000, "Tech screen's Upgrades", "cures every sick villager and sets every "
                  "living villager to full health (100); each villager cured counts in People Cured."), C),
    )),
    # native/vv2_origins_icons/vv2_origins_icons.c: ApplyVV2RunningToAll (likes capped at 3, VV2_LIKE_CAP),
    # ApplyVV2MasteryToAll, ApplyVV2AgeToAll (+0x530 = 360), ApplyVV2Collections; each living, non-totem record.
    Entry(PATCHER, "Origins: village-wide rows", (
        (_origins("Grant Running to All Villagers / Grant Full Mastery to All Villagers / All Villagers are Exactly "
                  "18", 1_000_000, "Tech screen's Upgrades", "each once: running added as a like to every living "
                  "villager with fewer than 3 likes (a running dislike removed from every one); every villager's five "
                  "skills set to 100; every villager's age set to 18 years."), C),
        (_origins("Complete All Collections / Reset All Collections", 1_000_000, "Tech screen's Upgrades", "marks "
                  "all 48 pieces found, or none.", sub=True), C),
        (_origins("Equal Division of Labor (Includes Parenting) / (No Parenting)", 1_000_000, "Tech screen's "
                  "Upgrades", "splits the village evenly across the jobs, men and women balanced in each, each "
                  "villager to the job of its most-progressed skill while that job has room.", sub=True), C),
        (_origins("Clear All Skill Preferences", 500_000, "Tech screen's Upgrades", "unticks every villager's job "
                  "checkmark; no skill changes.", sub=True), C),
        (_origins("Check Highest Skill (Includes Parenting) / (No Parenting)", 1_000_000, "Tech screen's Upgrades",
                  "ticks each villager's most-progressed skill (ties to the first of Farming, Building, Research, "
                  "Healing, Parenting); a villager with no progress keeps its checkmark.", sub=True), C),
        (_origins("Change Appearance for All", 450_000, "Tech screen's Upgrades", "sets the head, body or Heathen "
                  "mask (Blue, Orange, Red, Purple or Chief) of every villager at once.", sub=True), C),
    )),
    # data/vv2_origins_feature.json, the Details apply at 0x94A00: Youth +0x530 - 700, at least 100; Mastery
    # +0x7E4..+0x7F4 = 100; Running word 38 into the first free like slot, then every running dislike cleared;
    # Age 18 +0x530 = 360.
    Entry(PATCHER, "Origins: Villager Details rows", (
        (_origins("Grant Youth", 50_000, "Villager Details screen", "makes the villager shown 35 years younger (700 "
                  "age units), never under 5 years."), C),
        (_origins("Grant Full Mastery", 100_000, "Villager Details screen", "sets the villager's five skills to "
                  "100.", sub=True), C),
        (_origins("Grant Running", 40_000, "Villager Details screen", "adds running to the villager's likes and "
                  "removes a running dislike.", sub=True), C),
        (_origins("Set Age to 18", 50_000, "Villager Details screen", "sets the villager's age to 18 years.",
                  sub=True), C),
        (_origins("Change Appearance", 5_000, "Villager Details screen", "picks the villager's head, body or Heathen "
                  "mask.", sub=True), C),
    )),
    Entry(PATCHER, "Story / Cheat Upgrades", (
        ("With the patcher (Story / Cheat Upgrades, on by default; needs the Origins upgrades): every Origins "
         "upgrade costs 0 tech points only while Story / Cheat Upgrades cost Tech Points (ticked with it, and on by "
         "default) is unticked.", C),
        ("Pick Island Event (0, or 30,000 tech points): choose which island event comes next (59 with Restore "
         "Missing Island Events, 56 without) and, where the event rolls for it, how it turns out; the game's event "
         "code runs it.", C),
        ("Custom Island Event (0, or 30,000 tech points): an event you write, with the changes the game's code "
         "supports, the fish and the field's protection from birds included.", C),
        ("Pick Gong of Wonder Outcome (0, or 30,000 tech points): choose the Gong's result; refused, free, while the "
         "Gong is not whole.", C),
        ("Choose Time Skip Amount (0, or 50,000 tech points): 1 to 72 years, in steps of at most one Time Warp, each "
         "replayed by the game's catch-up.", C),
    )),
)

ENTRIES: tuple[Entry, ...] = TECHNOLOGIES + PUZZLE_ENTRIES + BUILDINGS + ITEMS + ORIGINS


def item_facts(village: gm.Village | None = None) -> list[gm.Fact]:
    """Every entry as Facts of ITEMS_GROUP (see src/vv_game_mechanics_items_vv1.item_facts)."""
    out: list[gm.Fact] = []
    for entry in ENTRIES:
        (head, ok), *rest = entry.lines
        out.append(gm.Fact(ITEMS_GROUP, f"{entry.name}: {head}", ok))
        out.extend(gm.Fact(ITEMS_GROUP, text, label, sub=True) for text, label in rest)
    return out


def counts() -> dict[str, int]:
    return {kind: sum(1 for entry in ENTRIES if entry.kind == kind) for kind in KINDS}
