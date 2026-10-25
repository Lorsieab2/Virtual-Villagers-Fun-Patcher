"""New Believers (VV5): every island event the game fires, its odds and outcomes (src/vv_game_mechanics_events.py).

Read from the stock executable (inputs/vv5-stock-copy, SHA-256 92946781...C65D).  Button and title words are the game's
own strings (16-byte entries: id, name, text; e.g. 0x39D eEventTheBedBugsChoiceA).  rand(n) is 0x403660, the C
runtime's rand() % n.  Villager record (manager 0x554148 + 0x48, 0x2F44 bytes): age +0x1B8C, sex +0x1B90 (0 male),
health +0x1C40, sick +0x1C48, Faith +0x1CF0 (set 0x467F90, add 0x468020), Heathen +0x1CEC, skills +0x1C5C (Farming,
Parenting, Healing, Research, Building, Devotion; added by 0x475730, kept to 0..100), likes +0x1F5C and dislikes
+0x1F68 (3 each, the words of eSayLikesList 0x1A2).  Food 0x51D34C (gains through 0x41EB40, which raises a gain by
half at Food Mastery 2 and doubles it at 3; losses are not raised), tech points 0x51D5F8 (0x4237B0), Divine Energy
manager +0x17D64, noni +0x17D58, crops +0x17D5C.

THE EVENTS: the slot table 0x4DC850[1..55]; each slot's object (RTTI CEvent...) has its condition at vtable [1],
a single result at [12] (amounts set at [14] when the popup opens), or a two-choice event's result text at [10] and
its effect at [11] (argument 0 is the first button).  THE SCHEDULER and the chooser 0x418870, the room check 0x472BD0
and the picker 0x471870 are as docs/reports/island-event-conditions.txt (New Believers) has them.
"""
from __future__ import annotations

from vv_game_mechanics_events import Event, Line

STORY = "vv5_story_cheat_upgrades"
SLOTS = 55
FM = "before Food Mastery, which raises a food gain by half at level 2 and doubles it at level 3"
WEATHER = ("1.5 to 3, 3 to 6 or 5 to 10 real-life minutes on Fast, Normal or Slow speed (paused time does not "
           "count)")
BELIEVER = "a living believer"
CHILD = "a living believer child under 14 villager years"
HEATHEN_CHILD = "a Heathen child under 14 who is not sick"
KIDS = ("up to 3 children of 10 villager years (200 age units), one at a time while the room check passes, each a "
        "boy or a girl 50% each (rand(2)), with one of the six skills (each 1 in 6) at 5 to 9 (each 1 in 5)")

RULES = (
    Line("Timing: the first event comes 15 real-life minutes after a village is made; while the village has seen no "
         "event yet the next comes 30 real-life minutes later; after that 8 to 15 whole real-life hours after the last "
         "(each of the 8 hour counts 1 in 8), at any speed (0x424854, 0x418870). Paused time does not count (it is "
         "added on load, 0x425E36); with the game closed the clock runs on, and after time away the due event "
         "happens once."),
    Line("An event happens only when there is at least one believer, and a believer drawn at random has a shown age "
         "equal to their processed age (otherwise the game tries again at its next update, 0x442715)."),
    Line(f"Which event: every one of the {SLOTS} slots whose condition holds is listed and one is drawn, each "
         "equally likely (1 in the number listed); with none, nothing happens. No event is limited to once per "
         "village. Every event's villager is drawn from those it allows, each equally likely; villagers in the six "
         "special roles (role 12 to 17) are never drawn."),
    Line("Rescue: when the sexes are out of balance (2 or fewer women and more men, or 2 or fewer men and no more men "
         "than women; Heathens counted) or there are fewer than 3 believers, 6% of events (a 15% roll, then a 40% "
         "one) become Chutes Without Ladders, even without room (0x418913)."),
    Line("Room for new villagers (the room check 0x472BD0): believers plus the babies they carry below 90, plus 5 for "
         "each of the two collections completed; and a population of 10 to 16 needs 1 rebuilt hut, 17 to 34 needs 2, "
         "35 or more all 3. Heathens are not counted."),
    Line(f"Weather an event brings lasts like any other weather: {WEATHER}."),
    Line("A loss of food or tech points takes no more than there is. Skills stop at 0 and 100; Faith at -100 and "
         "100. A believer whose Faith falls to 0 or less becomes a Heathen; a Heathen above 0 joins the tribe (see "
         "Faith and Heathens)."),
    Line("With the patcher's \"Story / Cheat Upgrades\" (in this game): Pick Island Event chooses the next event "
         "and, where the game rolls, the outcome.", only_with=STORY),
)

EVENTS = (
    # -- Single-result events -------------------------------------------------------------------------
    Event("The Creeping Mold", "always possible", ("The stored food loses 100 (0x414A30).",)),
    Event("The Allergy Season", "always possible", (
        "Every villager plays a hay-fever action; nothing else changes (0x414A70).",)),
    Event("Isola Day Celebration", "always possible", (
        "The village celebrates; nothing else changes (0x414AC0).",)),
    Event("Blessings Day Celebration", "always possible", (
        "Divine Energy is filled to its cap, and the village celebrates (0x414B30).",)),
    Event("Day of Honor", "needs 2 or more graves", (
        "The villagers pay their respects to the dead; nothing else changes (0x414DD0).",)),
    Event("The Vision", f"needs {BELIEVER} (the one who sees it)", (
        "That believer's Faith +20 to +39, each equally likely (0x414BD0).",)),
    Event("The Mysterious Footprints (food gained)", "always possible", (
        f"The stored food gains 300 ({FM}), and fog comes (0x414C20).",)),
    Event("The Mysterious Footprints (food lost)", "always possible", (
        "The stored food loses 300, and fog comes (0x414C90).",)),
    Event("The Mysterious Footprints (tech gained)", "always possible", (
        "+2,000 tech points, and fog comes 15, 30 or 50 real-life seconds later on Fast, Normal or Slow (0x414CF0).",)),
    Event("The Mysterious Footprints (tech lost)", "always possible", (
        "-2,000 tech points, and fog comes 15, 30 or 50 real-life seconds later on Fast, Normal or Slow (0x414D60).",)),
    Event("The Cold Snap", "needs the fire burning", ("Fog comes and the fire goes out (0x414E20).",)),
    Event("Army Ants!", "needs the Hydroponic Farm", ("The crops are all eaten: 0 of 800 (0x414E80).",)),
    Event("Aphid Infestation!", "needs the Hydroponic Farm", ("The crops are halved, rounded down (0x414EB0).",)),
    Event("The River Breaks Its Banks", "needs the Hydroponic Farm", (
        "Noni +200 and crops +200 (0x414FB0); both can pass their caps (1,000 and 800) until the next growth or "
        "refill puts them back.",)),
    Event("The Strange Crystals", "always possible", ("+2,000 to +2,999 tech points, each equally likely (0x414EF0).",)),
    Event("The Especially Offensive Cloud", "always possible", ("Everyone hides; nothing else changes (0x414F30).",)),
    Event("The Bottle of Spicy Juice", "always possible", (
        "The villagers react to the hot sauce; nothing else changes (0x414F70).",)),
    Event("The Clumsy Heathen", "always possible", (
        "Noni +200 (0x415010); it can pass 1,000 until the next growth puts it back.",)),
    Event("The Pesky Critter", "needs The Knowing Totem solved", (
        "-500 to -2,999 tech points, each equally likely (0x415070).",)),
    Event("Mushroom Day!", f"needs {CHILD}", (
        f"The stored food gains 50 to 99, each equally likely ({FM}), and -500 to -1,499 tech points, each equally "
        "likely (0x4150F0).",)),
    Event("The Salty Air", "always possible", ("Everyone hides until it settles; nothing else changes (0x4153B0).",)),
    Event("Barrel O' Babies! (believers)", "needs room for new villagers", (
        f"{KIDS}; they join the tribe with Faith 30 to 59 (0x4151D0).",)),
    Event("Barrel O' Babies! (heathens)", "needs room for new villagers (believers counted)", (
        f"{KIDS}; they are Heathens with Faith -55 (0x4152B0).",)),
    Event("Chutes Without Ladders", "needs room for new villagers, or the rescue rule", (
        f"{KIDS}; they join the tribe with Faith 30 to 59 (0x415410).",)),
    Event("News From Another Tribe (a newcomer)", "needs room for new villagers", (
        "A villager of 18 villager years joins, a man or a woman 50% each (rand(2)): 50.05% of the time a master of "
        "Research, otherwise a master of one of the six skills (each 1 in 6, Research among them), at 80 to 84 "
        "(each 1 in 5) (0x415510).",)),
    Event("News From Another Tribe (a message)", "always possible", ("+2,000 tech points (0x4155B0).",)),
    # -- Two-choice events (argument 0 is the first button) --------------------------------------------
    Event("The Bed Bugs", f"needs {BELIEVER} who is not pregnant or nursing", (
        "\"Search for the bugs all night\": -5 health (only above 6 health), and a dislike numbered 82 is added, "
        "past the end of the game's 79-word list, so it shows no word (0x4156E7).",
        "\"Let it go\": -15 health, and the villagers scratch (0x4156BB).")),
    Event("The Mask", f"needs {BELIEVER}", (
        "\"Put it on\": Faith set to -10, so the believer becomes a Heathen (0x4157AB).",
        "\"Bury it\": Faith +10 and Divine Energy +10 (0x4157B8).")),
    Event("The Heathen Toy", f"needs {CHILD} and {HEATHEN_CHILD}", (
        "\"Keep it\": Research +20 to +29, each equally likely (0x4158F6).",
        "\"Return it to its owner\": Devotion +20 to +29, and the Heathen child's Faith +15 (0x415901).")),
    Event("The Daredevil Jump", f"needs {BELIEVER} (and a second one, who may be the same)", (
        "\"Jump\": now likes running and jumping and dislikes work (0x415A0C).",
        "\"Don't jump\": now dislikes jumping and dancing (0x415A65).")),
    Event("The Spa", f"needs {BELIEVER} and {HEATHEN_CHILD}", (
        "\"Bathe quickly before anyone notices\": +10 health (0x415CEB).",
        "\"Enjoy the pools\": caught -- Faith set to -10, a Heathen (0x415CFE).")),
    Event("Doubt", f"needs {BELIEVER}", (
        "\"Give a sign\": Faith -5 and Divine Energy -20 (0x415D9B).",
        "\"Don't give a sign\": Faith +5 and Devotion +15 (0x415DB4).")),
    Event("Spying on the Heathens", f"needs {CHILD} and {HEATHEN_CHILD}", (
        "\"Run away\": Devotion +15 (0x415ED2).",
        "\"Talk to the heathen\": Devotion +25, the Heathen child's Faith +5, and the stored food loses 40 "
        "(0x415EE6).")),
    Event("You're Doing It Wrong!", f"needs {BELIEVER} of 14 or more, {HEATHEN_CHILD}, and Science below level 2", (
        "\"Teach them to reduce explosions.\": 50.05% an explosion -- -10 to -29 health and a dislike numbered 81, "
        "past the end of the word list; 49.95% Science goes up a level (0x416038, the coin rolled with the "
        "condition at 0x415FDD).",
        "\"There are a lot of them; better not!\": +500 tech points (0x4160A4).")),
    Event("The Missing Kids", f"needs {CHILD} and {HEATHEN_CHILD}", (
        "\"Yell for help\": the child and the Heathen child each -5 health and both fall sick (0x4161D1).",
        "\"Try to help the heathen\": Devotion +10 for the child, the Heathen child's Faith +10 (0x41620E).")),
    Event("Outreach?", f"needs {BELIEVER} of 14 or more and a Heathen of 14 or more who is not sick (the envoy)", (
        "\"Offer a tour\": the envoy's Faith +20, the believer's Devotion +20, the stored food loses 25 and -800 "
        "tech points (0x41632C).",
        "\"Refuse the tour\": nothing changes.")),
    Event("The Advanced Artifacts", f"needs Science exactly at level 2 and {BELIEVER}", (
        "\"Collaborate with the other researchers\": +2,000 tech points, and the believer now likes learning "
        "(0x41655A).",
        "\"Prepare an independent report.\": 49.95% well received -- Research +40 and Science up a level; 50.05% not "
        "believed -- now dislikes learning, and -100 tech points (0x4164F8, the coin rolled with the condition at "
        "0x416448).")),
    Event("Trick Or Trade", f"needs 100 food or more and {BELIEVER}", (
        "\"Employ a clever ruse\": +1,500 tech points, and the believer's Devotion drops to 0 (0x416648).",
        "\"Trade some food for the scrolls\": the stored food loses 100, Devotion +35 and +3,000 tech points "
        "(0x41666B).")),
    Event("The Migrating Fruit Bats", f"needs {CHILD} and Food Mastery below level 2", (
        "\"Observe them\": Food Mastery goes up a level, and the noni bushes are emptied (0 noni) (0x416778).",
        "\"Scare them\": Farming +25, and the tribe drives the bats off (0x416799).")),
    Event("The Aphids in the Noni Bush", f"needs {BELIEVER}", (
        "\"Research bugs that eat aphids\": noni -90, Farming +40 and +1,500 tech points (0x41684D).",
        "\"Research potions that kill aphids\": noni cut to 50 if above (0x4168A3).")),
    Event("The Defector", "needs a living Heathen who is not sick", (
        "\"Accept the heathen\": 50.05% a genuine defector -- Faith set to 20, and they join the tribe; 49.95% a spy "
        "-- -2,000 tech points (0x416988, the coin rolled with the condition at 0x416902).",
        "\"Better not\": nothing changes.")),
    Event("The Straw Hat", f"needs {BELIEVER}", (
        "\"Wear it\": Devotion +35 (0x416A38).",
        f"\"Use it as a cooking strainer\": the stored food gains 200 ({FM}) (0x416A56).")),
    Event("The Strange Nectar", f"needs {BELIEVER} of 18 or more", (
        "\"Drink it\": the believer's age is set to 330 age units (16.5 villager years), older or younger "
        "(0x416B28).",
        "\"Bring it to the lab\": +2,000 tech points (0x416B39).")),
    Event("The Cracked Mask", f"needs {BELIEVER} and {HEATHEN_CHILD}", (
        "\"Attempt to fix the mask\": -20 to -30 health, Devotion +25, and the Heathen child's Faith +35 "
        "(0x416C00).",
        "\"Try to trick the heathen\": Faith set to -10, so the believer becomes a Heathen (0x416C4A).")),
    Event("Innovation in Farming (the mysterious storyteller)", f"needs The Heathen Scientist solved and {CHILD}", (
        "The storyteller appears and the children gather; nothing else changes (0x417010).",)),
)
