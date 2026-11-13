"""The Secret City (VV3): every island event the game fires, its odds and outcomes (src/vv_game_mechanics_events.py).

Read from the stock executable (research/stock-executables, inputs/vv3-stock-copy).  Button words are the game's own
strings (16-byte entries: id, name, text; e.g. 0x325 eEventDaredevilChoiceA).  rand(n) is 0x4032D0, the C runtime's
rand() % n.  The villager table is manager 0x59E110 + 0x14, 0x1F8C bytes a record: age +0xDC4, sex +0xDC8 (0 male),
health +0xE78, sick +0xE89, chief +0xE80, pregnant or nursing +0xE8C, present +0xF10, skills Farming +0xEAC,
Parenting +0xEB0, Healing +0xEB4, Research +0xEB8, Building +0xEBC, likes list +0xFB4, dislikes list +0xFC0.

THE SCHEDULER (0x468750; docs/reports/island-event-conditions.txt, The Secret City):
  * The next event time is manager+0x12EF4 on the wall clock 0x403330 (real seconds).  A new village sets it 15
    minutes after its start (0x4280B2); the village's first event ever (lifetime counter 0x5824C4 = 0) sets the next
    30 minutes later (0x468899), every later one (rand(8) + 8) x 3600 s later (0x4687EE).  Saved paused, the closed
    time is added on load (0x428C60).
  * Tried only with a living villager of 14 or more (0x45C9D0(1)) whose age +0xDC4 equals its processed age +0xE74.
  * The selector 0x419B30: every slot 1 to 57 of the table 0x4B3C78 (filled at 0x418630) whose canHappen (vtable
    [1]) is true is listed, and one is drawn with rand(count) (0x419B7C); none, nothing happens.  Then a rand(100)
    (0x419B87) is drawn; when the sexes are out of balance (0x45FDE0 != -1) or fewer than 3 people (0x45E8F0),
    a second rand(100) < 15 replaces the pick: first draw < 30 The Crystal of Reflections, < 60 The Canoe from the
    Other Side, else Another One of Those Barrels -- without their condition (0x419BAF-0x419BD9).
  * Single-result effects are vtable [12]; a two-choice event's results [10] (text) and [11] (effect; argument 0
    the first button), amounts precomputed by [13].  Counted villagers c: the picker 0x45D460(7, -1, 1) -- living,
    present, not the Tribal Chief, and a child under 280 age units, an adult of 360-999 not pregnant or nursing, or
    an elder of 1,000 or more (14-17-year-olds and pregnant or nursing women of 18-49 are not counted); m is
    c / 20 rounded down, plus 1 (the 0x66666667 multiply in every [13]).
  * Weather (0x41FB40 on 0x4B86C4): lasts rand(180) + 180 game seconds (game clock 0x5825D4), or exactly 180 when
    the first fruit tree is grown (planted 28,800 game seconds ago) and the second not planted (0x41FC0F-0x41FC3D).
"""
from __future__ import annotations

from vv_game_mechanics_events import Event, Line

FIX = "vv3_fix_vanilla_bugs"
BOTH = "vv3_both_factions"
STORY = "vv3_story_cheat_upgrades"

SLOTS = 57
RESCUE = 15

M = "m x"            # the amounts' multiplier (the module docstring)
ADULT = "a living villager of 18 villager years or more who is not pregnant or nursing (or 50 or more)"
WEATHER = ("weather for 1.5 to 3, 3 to 6 or 5 to 10 real-life minutes on Fast, Normal or Slow speed (paused "
           "time does not count)")

RULES = (
    # The scheduler 0x468750: (rand(8) + 8) x 3600 s on the wall clock (0x4687EE); a new village's first 15 minutes
    # (0x4280B2), the first event ever brings the next 30 minutes later (0x468899); paused time added on load (0x428C60).
    Line("Timing: an event comes 8 to 15 whole real-life hours after the last one, at any speed (each of the 8 "
         "lengths equally likely). In a new village the first comes 15 real-life minutes after it is started, and the "
         "village's first event ever brings the next 30 real-life minutes later. Time saved paused does not count; "
         "after time away at most one event happens."),
    # 0x45C9D0(1): a living villager of 14 or more whose age +0xDC4 equals its processed age +0xE74.
    Line("An event happens only when there is a living villager of 14 villager years or more whose age is up to "
         "date (the age shown equals the hidden age the game counts by); otherwise the game waits and tries again."),
    Line(f"Which event: every one of the {SLOTS} events whose condition holds is listed and one is drawn, each "
         "equally likely (1 in the number listed); with none, nothing happens. No event is limited to once per "
         "village."),
    # The selector 0x419B30 (0x419BAF-0x419BD9): the balance test 0x45FDE0, fewer than 3 people 0x45E8F0.
    Line(f"Rescue: when the sexes are out of balance (2 or fewer women and more men, or 2 or fewer men and no more "
         f"men than women) or there are fewer than 3 people, {RESCUE}% of events are replaced, even when their own "
         "condition does not hold: 4.5% The Crystal of Reflections, 4.5% The Canoe from the Other Side, 6% Another "
         "One of Those Barrels."),
    # m: the picker 0x45D460(7, -1, 1) count / 20 + 1 (the 0x66666667 multiply in every [13]).
    Line("m (the amounts' multiplier): the villagers the game counts, divided by 20, rounded down, plus 1 (1 for 0 to "
         "19 villagers, 2 for 20 to 39, ...). Counted: the living, except the Tribal Chief -- children under 14, "
         "adults of 18 to 49 who are not pregnant or nursing, elders of 50 or more; 14-to-17-year-olds are not "
         "counted. A loss takes no more than there is."),
    # Every "N%" is rand(100) < N, rand() % 100 of the C runtime's 0..32,767 (0x4032D0).
    Line("Who: an event's villager is drawn from those its condition allows, each equally likely. Every \"N%\" is "
         "the game's roll (a random number from 0 to 32,767, divided by 100, the remainder below N), which "
         "makes it N% to within 0.07 percentage points."),
    # Of the likes and dislikes the outcomes add, Hidden villager stats lists those the game's code acts on; ants and
    # clouds, and liking medicine or crowds, are not among them (the 44 words with no effect found).
    Line("A like or dislike an outcome adds shows on the villager's Details screen; of those the events give, liking "
         "or disliking ants, liking clouds, and liking medicine or crowds change nothing that has been found in the "
         "game's code (Hidden villager stats lists the ones that do).", False),
    Line("With the patcher's \"Story / Cheat Upgrades\" (in this game): Pick Island Event chooses the next event "
         "instead of the draw above.", only_with=STORY),
)

EVENTS = (
    # -- Single-result events -------------------------------------------------------------------------
    # Each result's effect routine is named in the comment above it (the module docstring: vtable [12], or [10] / [11]
    # for a two-choice event).
    Event("The Tsunami", "needs 15 of the 16 puzzles solved, 2 living women and 2 living men who are not the chief", (
        # 0x414B30 -> 0x45D990
        "Every living villager is swept away at 15% each -- gone for good, no body, no grave.",)),
    Event("The Plague Of Ants", "always possible", (
        # 0x414B70; amount 0x418F30
        f"The stored food loses {M} 100.",)),
    Event("The Science Fair", "needs 3 living children under 14 villager years", (
        # 0x414BF0 -> 0x45DC40
        "Each living child, 50% each: +10 to 19 Research (each 1 in 10), up to 100.",)),
    Event("The Allergy Season", "always possible", (
        # 0x414C40: 0x45DDE0, action 0x65
        "Every villager plays an allergy animation; nothing else changes.",)),
    Event("Isola Day Celebration", "always possible", (
        # 0x414C80
        "The stored food loses 10 for every counted villager, and the children and adults celebrate.",)),
    Event("Blessings Day Celebration", "always possible", (
        # 0x414D10
        "The stored food loses 10 for every counted villager, and everyone celebrates.",)),
    Event("Day of Honor", "needs 2 graves or more", (
        # 0x414FE0, action 0xA
        "Every villager goes to honour the dead; nothing else changes.",)),
    Event("The Canoe from the Other Side", "needs room for a new villager (or the rescue rule)", (
        # 0x414D90 -> 0x45FF50
        "A man of 600 age units (30 villager years) joins with Building 40 to 69 (each 1 in 30), a head 0 to 29 "
        "and a body 0 to 28.",)),
    Event("The Mysterious Fog (food gained)", "always possible", (
        # 0x414E50
        f"Honeycombs: the stored food gains {M} 300, and fog {WEATHER}.",)),
    Event("The Mysterious Fog (food lost)", "always possible", (
        # 0x414E90
        f"The stored food loses {M} 300, and fog {WEATHER}.",)),
    Event("The Mysterious Fog (tech gained)", "always possible", (
        # 0x414F30
        f"The tribe gains {M} 2,000 tech points.",)),
    Event("The Mysterious Fog (tech lost)", "always possible", (
        # 0x414F70
        f"The tribe loses {M} 2,000 tech points.",)),
    Event("The Miraculous Bloom", "needs The Bee Hive solved", (
        # 0x415050 -> 0x431810
        "The bee hive's honey is set to 500, whatever it held.",)),
    Event("The Reflection in the Water", "always possible", (
        # vtable [12] is the empty 0x436180
        "A message only: nothing changes.",)),
    Event("The Chief's Address", "needs a living Tribal Chief, who gives it", (
        # 0x419050
        "The villagers gather to listen; no amount changes.",)),
    Event("The Rainy Season", "always possible", (
        # 0x4150D0
        f"Rain {WEATHER}.",)),
    Event("The Cold Snap", "needs the fire burning", (
        # 0x415110
        f"A cold spell {WEATHER}, and the villagers huddle by the fire.",)),
    Event("The Salty Air", "always possible", (
        # 0x415160, action 0x45
        "Every villager goes into hiding until it settles; nothing else changes.",)),
    Event("The Oppressive Humidity", "always possible", (
        # 0x4151A0 -> 0x45D8D0, action 0x7B
        "Every villager slows down, and every living villager's ongoing work is cleared.",)),
    Event("\"Thick as Pea Soup\"", "always possible", (
        # 0x4151E0
        f"Thick fog {WEATHER}, and every living villager's ongoing work is cleared.",)),
    Event("The Stinging Jellyfish", "always possible", (
        # 0x415220 -> 0x45D920
        "Every living villager is stung at 50% each and loses 10 to 19 health (each 1 in 10); at 0 health a "
        "villager dies.",)),
    # The counter is 0x5824B4 (items brought home that are not collection pieces).
    Event("The Mushroom Celebration", "needs 500 non-collection items brought home", (
        # 0x4152A0, action 0x42
        "Everyone celebrates; nothing else changes.",)),
    Event("The Yellow Geckos", "always possible", (
        # 0x4152E0 -> 0x45D7D0
        "Every living villager is cured of sickness.",)),
    Event("Another One of Those Barrels", "needs room for a new villager (or the rescue rule)", (
        # 0x415320
        "1 to 3 children of 200 age units (10 villager years) join: the first always, the second and the third each "
        "only if there is room then. Each: a boy or a girl 50% each, one skill (Farming, Parenting, Healing, Research "
        "or Building, 20% each) at 5 to 9, a head 0 to 29 and a body 0 to 28, a name from the game's list.",)),
    # -- Two-choice events (the first button is the first named) --------------------------------------
    Event("The Daredevil", "needs a living man of 18 villager years or more (the chief can be him) and 2 living "
                           "women of 18 or more", (
        # rand(100) at 0x41547D
        "\"He swims with sharks\": 75% the women swoon -- he gains 30 Parenting, up to 100; 25% a crab bites -- he "
        "loses 5 to 10 health and 5 to 14 Parenting, and now dislikes swimming.",
        "\"He rethinks his \"plan\"\": nothing changes.")),
    Event("The Ghostly Dream (nature or healing)", f"needs Nature technology level 1 or more and {ADULT}, not "
                                                   "the chief", (
        # 0x415550
        "\"Study the ways of nature\": +20 to 39 Farming (each 1 in 20), up to 100.",
        "\"Study the healing arts\": +20 to 39 Healing, up to 100.")),
    Event("The Ghostly Dream (research or architecture)", f"needs Magic technology level 1 or more and {ADULT}, not "
                                                          "the chief", (
        # 0x415690
        "\"Become preoccupied with research\": +20 Research, up to 100.",
        "\"Become inspired by architecture\": +20 Building, up to 100."),
        patched=((BOTH, "a tribe can have both factions, so both Ghostly Dreams can be listed at once; in the normal "
                        "game only the faction's own one can"),)),
    Event("The Crystal of Reflections", f"needs room for a new villager and {ADULT} (or the rescue rule)", (
        # 0x4191E0 -> 0x45F2D0
        "\"Keep the crystal\": a copy of the villager joins in the first free record -- the same skills, age, sex "
        "and looks, a new name.",
        "\"Dispose of the crystal\": nothing changes.")),
    Event("The Bitter Brown Beans (taste or dye)", "needs Science technology below level 2 and a living villager of "
                                                   "18 to 49 villager years not pregnant or nursing", (
        # 0x415840
        f"\"Taste some beans\": every living villager falls sick at 30% each, and the tribe gains {M} 200 food and "
        f"{M} 1,000 tech points.",
        "\"Use beans for dye\": the villager's body becomes, 50% each, outfit 5 or 18 for a man, 14 or 16 for a "
        "woman.")),
    Event("The Bitter Brown Beans (brew or fertilizer)", "needs Science technology level 2 or more and a living "
                                                         "villager of 18 to 49 not pregnant or nursing", (
        # 0x415A10
        f"\"Try to brew the beans\": the tribe gains {M} 600 food and {M} 2,000 tech points.",
        # 0x4340A0
        "\"Use the beans as fertilizer\": every fruit tree that is grown is set to 1,000 fruit (grown: ready to "
        "pick, 8 real-life hours of play after planting on Normal speed, 4 on Fast, 13 real-life hours 20 minutes "
        "on Slow).")),
    Event("The Ancient Tablet (laundry or decoration)", "needs Science technology below level 2 and a living "
                                                        "villager of 18 to 49 not pregnant or nursing", (
        # 0x415B70
        "\"Use it for doing laundry\": the villager now likes laundry.",
        "\"Use it for decoration\": the villager now likes learning.")),
    Event("The Ancient Tablet (research or display)", f"needs Science level 2 or more, Alchemy below level 3 and "
                                                      f"{ADULT}", (
        # 0x415D10
        f"\"Focus research on tablet\": Alchemy technology goes up 1 level, and the tribe loses {M} 1,000 tech "
        "points.",
        "\"Put it on display\": every living villager, 20% each: +10 to 34 Research (each 1 in 25), up to 100.")),
    Event("The Low Tide", "needs 8 living villagers who are not the chief; the event's 50% coin is rolled when it "
                          "is picked", (
        # 0x415E80
        f"\"Grab the fish\": 50% they get away with the fish -- {M} 500 food; 50% a wave -- every living villager "
        "is swept away at 20% each (gone, no body), then every one left comes to dislike the ocean at 20% each.",
        "\"Move to high ground\": nothing changes.")),
    Event("The Ants and the Granary", "needs a living child under 14 who is not the chief", (
        # 0x416010
        "\"Sweep the ants away\": the stored food loses a third (food x 0.33, rounded), and the child now dislikes "
        "ants.",
        f"\"Let them be\": the stored food loses {M} 50 (at least 1), the child now likes ants and gains 5 to 9 "
        "Farming, up to 100.")),
    Event("The Green Pearl", f"needs {ADULT}, not the chief", (
        # 0x416150
        "\"Grind it into powder\": the villager's health becomes 100, and the villager now likes running.",
        "\"Mount it on a bracelet\": +15 to 29 Parenting (each 1 in 15), up to 100.")),
    Event("The Blue Pearl", f"needs The Alchemy Lab solved and {ADULT}", (
        # 0x4162D0
        "\"Grind it into powder\": +20 to 34 Research (each 1 in 15), up to 100.",
        "\"Examine it more closely\": nothing changes.")),
    Event("The Lazy Apprentice", "needs a living child under 14 who is not the chief and a living villager of 18 or "
                                 "more with Research 30 or more (the teacher)", (
        # 0x416420
        "\"Stay with the current teacher\": the child now likes learning.",
        "\"Find a new teacher\": the child gains 20 to 39 Farming and 10 to 19 Building, up to 100, and now "
        "dislikes learning.")),
    Event("The Omen in the Clouds", f"needs {ADULT}, not the chief; the omen (1 to 4, 25% each) is rolled when it is "
                                    "picked", (
        # 0x416680, the omen table 0x4167F8
        f"\"Warn the villagers\": by the omen, 25% each: a storm the village is ready for ({WEATHER}, no harm) and "
        f"the villager now likes crowds; a storm nobody believed -- the same weather, {M} 500 food lost, and the "
        f"villager now likes crowds; a false alarm -- {M} 800 tech points lost and the villager now dislikes "
        "crowds; a false alarm the villager studies -- +15 to 24 Research, up to 100, and the villager now likes "
        "clouds.",
        f"\"Perform the dance\": rain {WEATHER}, the villager falls sick and now likes crowds.")),
    Event("The Playful Otters", "needs a living child under 14 who is not the chief", (
        # 0x4168E0
        f"\"Throw them some food\": the stored food loses {M} 500.",
        "\"Just keep watching them\": the child gains 15 to 29 Farming, up to 100.")),
    Event("The Ant Hill", "needs a living child under 14 who is not the chief", (
        # 0x416AC0
        "\"Poke the ant hill with a stick\": the child loses 5 to 14 health and now dislikes ants.",
        f"\"Drop some bits of food\": the stored food loses {M} 200, and the child now likes learning and ants.")),
    Event("The Red Starfish", f"needs {ADULT}, not the chief", (
        # 0x416C10 -> 0x45DA60
        "\"Pick it up\": one skill -- Parenting, Farming, Healing, Building or Research, 20% each -- loses 5 to 19 "
        "(each 1 in 15), down to 0.",
        "\"Leave it alone\": nothing changes.")),
    Event("The Blue Starfish", f"needs {ADULT}, not the chief", (
        # 0x416D10 -> 0x45DB50
        "\"Pick it up\": one skill, 20% each as above, gains 10 to 24, up to 100.",
        "\"Leave it alone\": nothing changes.")),
    Event("Bed Bugs", f"needs {ADULT}, not the chief", (
        # 0x416E20
        "\"Swat it\": the villager falls sick and loses 5 to 9 health.",
        "\"Have a closer look\": the villager now likes ants.")),
    Event("The Lovers (her gift)", "needs a living woman of 18 to 49 villager years who is not pregnant or nursing "
                                   "and not the chief, and a living man of 18 to 49 who is not the chief", (
        # 0x416ED0 -> 0x45D460 with its adult class: age 360 to 999 age units, a woman not pregnant or nursing
        # (0x45D4CC), not the chief.
        Line("How the pair is picked: the woman, then the man, each drawn equally likely from the adults the game "
             "allows (360 to 999 age units, a woman not pregnant or nursing, not the chief)."),
        # The code and the owner's sighting disagree (the owner, 2026-10-27: "for cases where the code contradicts
        # live observation write both cases down"): the code's line, then the owner's, never one without the other.
        # The code: 0x416ED0 -> 0x45D460, 0x45D4CC.
        Line("In the game's code both picks come only from adults of 360 to 999 age units (18 to 49 villager "
             "years), the woman not pregnant or nursing, so the game's draw never chooses a teenager; Pick Island "
             "Event offers only villagers the game could draw, and only the patcher's Custom Island Event, which may "
             "pick any villager by design, can choose one."),
        Line("The owner has seen The Lovers choose a teenager (14 to 17 villager years) while playing.",
             "owner"),
        # The conception 0x4582A0; the twin and triplet rolls 0x416F30.
        "\"Carve a knife for him\": both gain 25 Parenting, up to 100, and she conceives his child, if there is "
        "room; at Medicine level 3 the conception's twin and triplet rolls are made.",
        "\"Give him a shark-tooth necklace\": nothing changes.")),
    Event("The Lovers (his gift)", "needs a living man of 18 to 49 who is not the chief and a living woman of 18 to "
                                   "49 who is not pregnant or nursing and not the chief", (
        # 0x417050 -> 0x45D460
        Line("How the pair is picked: the man, then the woman, as for her gift."),
        # The teenager note is given once, under her gift (it stood here word for word too).  0x417050 -> 0x45D460.
        Line("A teenager, in the game's code: as for her gift, the game's own draw never chooses one; only the "
             "patcher's Custom Island Event can."),
        Line("A teenager, seen by the owner: as for her gift.", "owner"),
        # 0x4170B0
        "\"Give her a shell necklace\": nothing changes.",
        "\"Give her flowers\": both gain 25 Parenting, up to 100, and she conceives his child, if there is room.")),
    Event("The Medical Emergency", "needs Medicine technology level 2 or more, a living villager who is not the "
                                   f"chief (the patient) and {ADULT} (the healer); the outcome is rolled first", (
        # rand(100) at 0x41722D; 0x417260
        "\"Attempt the procedure\": 50% full recovery -- the patient gains 40 Healing, up to 100, and now likes "
        "medicine; 50% the patient dies (health 0).",
        "\"Let the illness take its course\": the patient now dislikes running and work.")),
    Event("The Mysterious Vial (quartz)", "needs any living villager (the chief can be the one)", (
        # 0x417400: the age +0xDC4 and the processed age +0xE74 both set (0x417440)
        "\"Taste it\": a villager of 280 age units or less (14 villager years or younger) becomes an elder -- age "
        "1,000 (50 villager years; the hidden age the game counts by too), health 100, +30 to 59 Healing and +30 to "
        "59 Research, up to 100 -- and anyone older becomes a child of 200 age units (10 villager years).",
        "\"Bring it back to the village\": nothing changes.")),
    Event("The Mysterious Vial (obsidian)", f"needs {ADULT} (the chief can be the one)", (
        # rand(100) at 0x4175BD; 0x417610
        "\"Taste it\": 33% a new head (0 to 29); 33% clumsy -- two skill losses, each a skill drawn 20% each and "
        "15 to 44 lost, down to 0; 34% insight -- two skill gains of 15 to 44, up to 100.",
        "\"Bring it back to the village\": nothing changes.")),
    Event("The Mysterious Vial (amber)", f"needs {ADULT} (the chief can be the one)", (
        # "Feels years younger" lowers only the shown age +0xDC4 (0x41780C), not the processed age +0xE74 that the
        # aging loop 0x45FFE0 steps (it runs a villager's age unit only while processed < shown, 0x46001E): so the
        # villager's life rules stop until the shown age catches up again.  The quartz vial sets both (0x417440).
        # rand(100) at 0x41771D; 0x417770.
        "\"Taste it\": 33% scientific insight -- +15 to 44 Research, up to 100; 33% feels years younger -- health "
        "100 and cured at once, and the age shown drops 100 age units (5 villager years), not below 100, but the "
        "hidden age the game counts by stays, so for the next 100 age units (10 real-life hours of play on Normal "
        "speed, 5 real-life hours on Fast, 16 real-life hours 40 minutes on Slow) the villager's age units do "
        "nothing: no eating, no health gained or lost, no sickness roll, no old-age roll and no progress of a "
        "pregnancy; then they run on as before, the old-age rolls by the hidden age, which was never made younger; "
        "34% two copies of the villager join, each if there is a free record.",
        "\"Bring it back to the village\": nothing changes."),
        patched=((FIX, "scientific insight also gives the tribe 100 tech points, as its text says; in the normal "
                       "game it gives only the Research"),)),
    Event("The Mango and the Papaya", "needs a living villager of 18 to 49 not pregnant or nursing; the swim's 50% "
                                      "coin is rolled when it is picked", (
        # 0x4179A0
        f"\"Swim out after the papaya\": 50% both fruits home -- {M} 400 food; 50% the papaya is full of bugs and the "
        "mango is lost -- nothing.",
        f"\"Be satisfied with the mango\": {M} 200 food.")),
    Event("The Mysterious Crate", "needs 3 living villagers of 18 to 49 not pregnant or nursing (the chief can be "
                                  "the one); the outcome is rolled first", (
        # rand(100) at 0x417ACD; 0x417B00
        f"\"Open the crate\": 50% a crate of fruit -- {M} 500 food; 50% a tarantula -- the opener falls sick and "
        f"loses 10 to 29 health, and {M} 400 food.",
        "\"Shove it back out to sea\": nothing changes.")),
    Event("Vanity and the Bee", "needs a living woman of 18 to 49 who is not pregnant or nursing and not the chief", (
        # 0x417D50
        "\"Run to the water\": she now likes running.",
        "\"Swat at the bee\": she falls sick, loses 15 to 24 health and now dislikes bees.")),
    Event("The Noisy Bird", "needs a living woman of 18 to 49 who is not pregnant or nursing and not the chief", (
        # 0x417E80
        "\"Scare the bird away\": she walks off; nothing changes.",
        "\"Leave the bird alone\": the same.")),
    Event("The Hole in the Hut", "needs The Bee Hive solved and a living villager of 18 to 49 not pregnant or "
                                 "nursing, not the chief", (
        # 0x417F90
        "\"Use beeswax\": the bee hive loses a third of its honey (honey x 2 / 3).",
        "\"Use tree sap\": the first fruit tree loses half its fruit.")),
    Event("The Royal Jelly", f"needs {ADULT}, not the chief", (
        # 0x4180A0
        "\"Use a clear vial\": the villager is cured and gains 15 to 29 Healing, up to 100.",
        "\"Use a dark vial\": nothing changes."),
        patched=((FIX, "the dark vial cures and gives the Healing, and the clear vial changes nothing, as their "
                       "texts say; in the normal game it is the other way round"),)),
    Event("The Shooting Star", "needs a living child under 14 who is not the chief", (
        # 0x4181C0
        f"\"Tell the others\": {M} 200 food.",
        "\"Stay and watch\": the child gains 25 to 49 Research, up to 100.")),
    Event("The Return of Biggles", "needs a living villager who is not the chief", (
        # 0x418390
        "\"Confront him\": +20 to 44 Research, up to 100, and the villager's name becomes \"?\".",
        f"\"Watch him work\": {M} 1,000 tech points.")),
)

# The Aspiring Adventurer (the owner, 2026-11-12): "VVFP More Island Events.dll" adds it (src/vv_game_mechanics_adventurer.py).
from vv_game_mechanics_adventurer import (adventurer_event, diving_for_treasure_event,  # noqa: E402
                                          troubling_signs_event)

EVENTS = EVENTS + (adventurer_event(3), troubling_signs_event(), diving_for_treasure_event())
