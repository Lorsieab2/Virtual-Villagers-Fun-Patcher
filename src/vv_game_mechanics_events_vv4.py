"""The Tree of Life (VV4): every island event the game fires, its odds and outcomes (src/vv_game_mechanics_events.py).

Read from the stock executable (inputs/vv4-stock-copy).  Button and title words are the game's own strings (16-byte
entries at 0x4C41F8..: id, name, text; e.g. 0x34E eEventArcOfColorsChoiceA).  rand(n) is 0x4036D0, the C runtime's
rand() % n.  Villager record (manager 0x50E568 + 0x44, 0x2E3C bytes): age +0x1B8C, sex +0x1B90 (0 male), health
+0x1C40 (added by 0x46AF40, set by 0x46AF00, kept to 0..100), sick +0x1C48, skills +0x1C5C (Farming, Parenting,
Healing, Research, Building; added by 0x46AD80, kept to 0..100), likes +0x1E60 and dislikes +0x1E6C (3 each; added by
0x45D2D0, the opposite list's same word removed by 0x45D1C0; the words of eSayLikesList).  Food 0x4D6DD0 (gains
through 0x41D920, raised by half at Food Mastery 2 and doubled at 3), tech points 0x4D6F88 (0x41E300), blackberries
manager +0x170F8.  Tech levels 0x4D6F5C (0x41E1C0; 0x41E1D0 raises one, to 3 at most): 0 Science, 1 Medicine,
2 Learning, 3 Construction, 4 Food Mastery, 5 Dendrology.  Group effects on every living villager: 0x467040
(rand(100) < p: health -(rand(n) + base)), 0x466F40 (rand(100) < p: falls sick), 0x467110 (rand(100) < p: a skill
+(rand(n) + base)), 0x467290 (everyone: a skill +amount), 0x466FB0 (every sick villager cured), 0x467490 (everyone
healed to 100).

THE EVENTS: the slot table 0x4CCA28[1..49]; each slot's object (RTTI CEvent...) has its condition at vtable [1], a
single result at [12] (amounts set at [14] when the popup opens), or a two-choice event's result text at [10] and its
effect at [11] (argument 0 is the first button).  THE SCHEDULER and the chooser 0x418000, the room check 0x468350 and
the picker 0x4679B0 are as docs/reports/island-event-conditions.txt (The Tree of Life) has them.
"""
from __future__ import annotations

from vv_game_mechanics_events import Event, Line

STORY = "vv4_story_cheat_upgrades"
SLOTS = 49
FM = "before Food Mastery, which raises a food gain by half at level 2 and doubles it at level 3"
WEATHER = ("1.5 to 3, 3 to 6 or 5 to 10 real-life minutes on Fast, Normal or Slow speed (paused time does not "
           "count)")
ANY = "a living villager of any age"
ADULT = "a living villager of 14 or more"
CHILD = "a living child under 14 villager years"
DOCTOR = "needs a living villager of any age (the text calls them a healer; skills are not checked)"

RULES = (
    Line("Timing: the first event comes 15 real-life minutes after a village is made; while the village has seen no "
         "event yet the next comes 30 real-life minutes later; after that 8 to 15 whole real-life hours after the last "
         "(each of the 8 hour counts 1 in 8), at any speed (0x41F31B). Paused time does not count (it is added on "
         "load, 0x420330); with the game closed the clock runs on, and after time away the due event happens once."),
    Line("An event happens only when the village has someone, and a villager drawn at random has a shown age equal to "
         "their processed age (otherwise the game tries again at its next update, 0x43FA5B)."),
    Line(f"Which event: every one of the {SLOTS} slots whose condition holds is listed and one is drawn, each "
         "equally likely (1 in the number listed); with none, nothing happens. No event is limited to once per "
         "village. Every event's villager is drawn from those it allows, each equally likely."),
    Line("Rescue: when the sexes are out of balance (2 or fewer women and more men, or 2 or fewer men and no more men "
         "than women) or there are fewer than 3 people, 6% of events (a 15% roll, then a 40% one) become Daredevil "
         "Barrel...of Babies!, even without its condition (0x4180A5)."),
    Line("Room for new villagers (the room check 0x468350): villagers plus the babies being carried below 90 plus "
         "the collections' bonus (5 for each complete collection, 25 with all four: see Collectibles); and a "
         "population of 10 to 16 needs 1 rebuilt hut, 17 to 34 needs 2, 35 or more all 3."),
    Line(f"Weather an event brings lasts like any other weather: {WEATHER}."),
    Line("A loss of food or tech points takes no more than there is. Health and skills stop at 0 and 100."),
    Line("With the patcher's \"Story / Cheat Upgrades\" (in this game): Pick Island Event chooses the next event "
         "and, where the game rolls, the outcome.", only_with=STORY),
)

EVENTS = (
    # -- Single-result events -------------------------------------------------------------------------
    Event("The Creeping Mold", "always possible", ("The stored food loses 100 (0x414760).",)),
    Event("The Allergy Season", "always possible", ("Everyone sneezes; nothing else changes (0x4147B0).",)),
    Event("Isola Day Celebration", "always possible", ("The village celebrates; nothing else changes (0x4147F0).",)),
    Event("Blessings Day Celebration", "always possible", ("The village celebrates; nothing else changes (0x414860).",)),
    Event("Day of Honor", "needs 2 or more graves", (
        "The villagers pay their respects to the dead; nothing else changes (0x414AF0).",)),
    Event("The Mysterious Footprints (food gained)", "always possible", (
        f"The stored food gains 300 ({FM}), and fog comes (0x414940).",)),
    Event("The Mysterious Footprints (food lost)", "always possible", (
        "The stored food loses 300, and fog comes (0x4149B0).",)),
    Event("The Mysterious Footprints (tech gained)", "always possible", (
        "+2,000 tech points, and fog comes 15, 30 or 50 real-life seconds later on Fast, Normal or Slow (0x414A10).",)),
    Event("The Mysterious Footprints (tech lost)", "always possible", (
        "-2,000 tech points, and fog comes 15, 30 or 50 real-life seconds later on Fast, Normal or Slow (0x414A80).",)),
    Event("A Closer Look", f"needs {ANY}", (
        "The blackberry bushes gain 350 berries (0x414B38).",)),
    Event("The Rainy Season", "always possible", ("Rain comes (0x414B90).",)),
    Event("The Cold Snap", "needs the Fire Pit burning", ("Fog comes and the fire goes out (0x414BD0).",)),
    Event("\"A Monsoon!\"", "always possible", (
        "Rain comes, and every villager drops what they were doing (0x414C10).",)),
    Event("The Stinging Wasps", "always possible", (
        "Every villager is stung 50% of the time, losing 10 to 19 health (each equally likely) (0x414C69).",)),
    Event("The Festival of the Banyan", "needs 500 mushrooms brought home and 3 of the 5 tree puzzles solved", (
        "The children are celebrated; nothing else changes (0x414CE0).",)),
    Event("The Pure Sea Air", "always possible", ("Every sick villager is cured (0x414D20).",)),
    Event("Daredevil Barrel...of Babies!", "needs room, The Stream solved and the stream flowing (or the rescue rule)", (
        "Up to 3 children of 10 villager years (200 age units), one at a time while the room check passes (the first "
        "always), each a boy or a girl 50% each (rand(2)), with one of the five skills (each 1 in 5) at 5 to 9 "
        "(0x414D90).",)),
    Event("The State of the Tree (glum)", "needs fewer than 3 of the 5 tree puzzles solved", (
        "Every villager loses 5 to 14 health 10% of the time, and falls sick 20% of the time (0x414EB0).",)),
    Event("The State of the Tree (rejuvenated)", "needs 3 or more of the 5 tree puzzles solved", (
        "Every sick villager is cured and everyone is healed to 100 health (0x414F20).",)),
    Event("The Abandoned Infants", "needs room and 6 living women of 14 or more who are not pregnant or sick", (
        "Up to 6 women of 18 or more who are not pregnant or nursing and not sick become pregnant (the father the "
        "game's default, head 2, body 2), each pregnancy with the usual chance of twins or triplets at Medicine 3 "
        "(0x467B00 -> 0x45E7B0).",)),
    # -- Two-choice events (argument 0 is the first button) --------------------------------------------
    Event("The Arc of Brilliant Colors", f"needs {ANY} who is not pregnant or nursing", (
        "\"Run to the left side\": the villager walks to the mausoleum; nothing else changes (0x415213).",
        "\"Run to the right side\": 50% (rand(2), rolled when the result shows) a fall -- -25 to -44 health and now "
        "dislikes heights; 50% rare mushrooms -- the stored food gains 300 (" + FM + ") and now likes heights "
        "(0x4150C6).")),
    Event("The Robber Crab", f"needs {ANY}", (
        "\"Cut off its tail\": every villager gains 5 to 9 Healing 80% of the time (0x4152E5).",
        "\"Let it go\": Food Mastery goes up a level (up to 3) (0x4152FC).")),
    Event("The Phosphorescent Fungi", f"needs {CHILD}", (
        "\"Throw it into the ocean\": the child gains 40 to 49 Research, falls sick and loses 15 to 19 health (left "
        "at 3 if that would kill them) (0x4153C8).",
        "\"Admire it from afar\": every villager falls sick 30% of the time, and the child gains 20 Building "
        "(0x415438).")),
    Event("The Pink Shell", f"needs {ANY}", (
        "\"Pick it up and listen inside\": -5 to -10 health, and now dislikes crab meat (0x415778).",
        "\"Admire it without touching it\": now likes learning (0x4157BB).")),
    Event("The Calabash Instrument", f"needs {ANY}", (
        "\"Fill it up to the first notch\": +3,000 tech points (0x41585A).",
        "\"Fill it to the top\": -2,000 tech points (0x415867).")),
    Event("The Climber", f"needs {CHILD}", (
        "\"Try to find a way down\": -50 health; a child who survives raises Dendrology a level (0x4158F8).",
        "\"Start yelling for help\": -500 tech points (0x415942).")),
    Event("The Mosquito Larvae", f"needs {ADULT}, Soap and The Stream solved, and the stream flowing", (
        "\"Put soap in the pond\": 1 of the village's soap is used up (the Soap puzzle's count, 0x43A410), and every villager falls sick 25% of the "
        "time (0x415A55).",
        "\"Pour oil in the pond\": +500 tech points (0x415A74).")),
    Event("Faces in the Night", f"needs {ADULT}", (
        "\"Inform the tribe\": +1,000 tech points (0x415B38).",
        "\"Ignore the faces\": now dislikes work and the dark (0x415B4B).")),
    Event("The Screaming Baby", "needs a living woman of 14 or more who is pregnant or nursing and not sick", (
        "\"Leave baby alone\": now dislikes work and likes sleeping (0x415C3C).",
        "\"Take baby to the beach\": now likes dancing, and +10 health (0x415C78).")),
    Event("The Sealed Box", f"needs {ADULT} who is not pregnant or nursing", (
        "\"Swim back with the box\": 50.05% +5,000 tech points; 49.95% swept away -- health 0, gone from the "
        "village (0x415D78, the coin rolled with the condition at 0x415CF5).",
        "\"Let it go\": nothing changes.")),
    Event("The Wet Book", f"needs {ANY}", (
        "\"Read each page\": each of the villager's five skills below 50 is raised to 50 (0x415E68).",
        "\"Bring it to the lab\": every villager gains 5 to 10 Parenting (0x415EE3).")),
    Event("The Lie", f"needs {CHILD}", (
        "\"Lie\": -25 to -50 health, and a dislike numbered 79 is added, past the end of the game's 79-word list, so "
        "it shows no word (0x415FB8).",
        "\"Tell the truth\": every villager gains 5 to 10 Parenting and the child 10 to 20 Farming (0x415FFB).")),
    Event("The Aspiring Doctor (algae)", DOCTOR, (
        "\"Eat algae\": cured, Healing +20, and a like numbered 80 is added (past the end of the word list) "
        "(0x4160DC).",
        "\"Better not\": falls sick (0x416125).")),
    Event("The Aspiring Doctor (sea water)", DOCTOR, (
        "\"Drink sea water\": falls sick and -15 health (0x416207).",
        "\"Better not\": falls sick, and Healing +20 (0x41628D).")),
    Event("The Aspiring Doctor (mushrooms)", DOCTOR, (
        "\"Eat a bit\": cured, -15 to -34 health, Healing +25 (0x416378).",
        "\"Better not\": falls sick (0x4163C2).")),
    Event("The Aspiring Doctor (bark)", DOCTOR, (
        "\"Eat a bit\": cured, +25 health, Healing +25 (0x416448).",
        "\"Better not\": falls sick (0x416482).")),
    Event("The Aspiring Doctor (fasting)", DOCTOR, (
        "\"Fast\": falls sick, -20 to -30 health, Healing +20 (0x416508).",
        "\"Eat\": falls sick (0x416552).")),
    Event("The Aspiring Doctor (cut leg)", DOCTOR, (
        "\"Use bark\": cured, -10 to -15 health, Healing +20 (0x4165DC).",
        "\"Use mushrooms\": falls sick, -10 to -15 health, Healing +10 (0x41660C).")),
    Event("The Aspiring Scientist", f"needs {ANY}", (
        "\"Try the salts\": -35 to -75 health, Research +20 and +2,000 tech points (0x4166D8).",
        "\"Use algae\": -1,000 tech points (0x416727).")),
    Event("Innovation in Construction", f"needs {ADULT} who is not pregnant, nursing or sick", (
        "\"Try the technique\": 60.06% Building +65; 39.94% a fall -- -75 to -149 health (0x416808, the coin rolled "
        "with the condition at 0x416785).",
        "\"It is too dangerous\": nothing changes.")),
    Event("Innovation in Farming", f"needs {ADULT} who is not pregnant, nursing or sick, and the Cooking Pit restored", (
        "\"Try standing on fruit\": 60.06% Farming +65; 39.94% onto the hot coals -- -75 to -149 health (0x416938, "
        "the coin rolled with the condition at 0x4168A5).",
        "\"That is too dangerous\": nothing changes.")),
    Event("Tough Lessons", f"needs {CHILD} and {ADULT}", (
        "\"Climb the Tree\": the adult -75 health and Parenting +60 (0x416A68).",
        "\"Leave the Child\": the adult's Parenting -10 (0x416A82).")),
    Event("The Pretty Shell", "needs 2 living villagers of 14 or more", (
        "\"Teach kids sharing\": Parenting +30 (0x416B82).",
        "\"Teach kids negotiation\": Farming, Research, Building and Healing +15 each (0x416B96).")),
    Event("The Legendary Stranger", f"needs {ANY}", (
        "\"How should we care for our people?\": Medicine goes up a level (0x416DA3).",
        "\"How should we care for the tree?\": Dendrology goes up a level (0x416DBD).")),
)
