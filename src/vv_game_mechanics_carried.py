"""Game Mechanics: "Babies being carried" -- what a pregnant villager's babies count toward, all five games.

The owner, 2026-11-18: "How does food consumption work when there are nursing infants? The population counter increases
by the number of nursing babies. Does that affect anything? (Put it in Game Mechanics for all 5 games.)"  ("Nursing"
in these games means carrying an unborn baby.)

THE POPULATION COUNTER (read from the stock exes, research/stock-executables; decompiled with IDA):
  VV1 0x41CF90, VV2 0x425860, VV3 0x45E8F0, VV4 0x467610, VV5 0x4713F0.  Each walks the villager table and, for every
  record that is present with health above 0, adds 1, and while that record carries (conceived != 0) adds its babies
  -- 1, 2 or 3 (VV1/VV2 test the litter field for 2 and 3, a 0 there is one baby; VV3-VV5 add the litter field).
  VV2 leaves out the record itself when its +0x558 byte is set (the statues are made with health 0 anyway); VV4
  leaves out the ghost byte +0x1CC7; VV5 counts only believers (0x466170 refuses a Heathen), so a Heathen mother's
  babies are not counted either.  Nothing else is cached: every caller below runs the count afresh.

EVERY CALLER OF THE COUNTER (IDA code references, all five games) and of each game's room check (VV1 0x43A1A0, VV2
0x44B310, VV3 0x45FE30, VV4 0x468350, VV5 0x472BD0, each of which asks the counter first):
  VV1  0x414590 (hut sites: 0x414AE2 >= 15, 0x414BC7 >= 28)  0x41F9B0 / 0x42A340 (the population number on screen)
       0x423390 (island events: 0x42373C game over line at 0, 0x4237CB attempt only above 0, 0x4239B0 strength n =
       count / 3, 1-10)  0x427CA0 (Isola Day: food -10 x count, 0x4280BF)  0x42E900 (world tick: 0x42EF9F newborn's
       sex rule at 6 or fewer -> 0x42E660; 0x42F16C/0x42F17B Highest Population; 0x42F199-0x42F265 the 15/25/50 and
       "maximum sustainable" tips 312-315, the "all died" tip 317)  0x43A1A0 (room)  0x43DAD0 (the player's pair:
       0x43DC12 the trial limit, 0x43DDD8 the refusal reason below 90)  0x446C70 (catch-up: 0x446D52/0x446E41 the
       trial limit)  0x4472C0 (builders: 0x44754A hut 2 above 22, 0x44757C hut 3 above 45).
       Room callers: 0x419380 (The Mysterious Face's newcomer, 0x419700), 0x428470 case 12 (The Barrel O' Babies),
       0x42B740 (the Mysterious Crate's babies, 0x42C358), 0x43BBC0 (every conception), 0x43DAD0 (the refusal
       reason), 0x43E740 / 0x43EA50 (the housing mood, strings 577/578/579), 0x446C70 (catch-up embraces, 0x447139).
  VV2  0x418660 (hut sites: 0x4196E8 >= 21, 0x419763 >= 46)  0x41F570 case 14 (The Silver Mirror >= 2)  0x41F720
       (two-choice amounts x2 above 25, x3 above 50)  0x4299B0 / 0x4369D0 (the number on screen)  0x42E990 (island
       events: 0x42EE4C game over line, 0x42EEDB attempt, 0x42F0A1 strength n)  0x4335A0 (single-result amounts, x3
       above 50)  0x433600 (Isola Day case 7 0x433A04, Blessings Day first version case 10 0x433C54, second version
       case 12 0x433CBC: food -10 x count)  0x434570 case 16 (A Dangerous Mission > 60)  0x43B690 (world tick:
       0x43BE2D sex rule, 0x43C0C5/0x43C0D4 Highest Population, 0x43C0E3-0x43C1C1 tips 451-454)  0x44B310 (room)
       0x44F610 (the player's pair: 0x44F748 trial limit, 0x44F974 reason)  0x44FE10 / 0x450020 (the housing mood,
       with the room check)  0x45FBF0 (builders: 0x4600DE above 22, 0x460108 above 45)  0x464680 (catch-up trial
       limit).  Room callers: 0x41F570 case 4 (The Savage Child), 0x4204B0 (a two-choice result's newcomer),
       0x4308D0 (two adults dropped together, 0x430EE2: with no room the message 0x4257A0(53), and the pair's
       actions are queued anyway), 0x434570 cases 21 (The Barrel O' Babies) and 25 (Old
       Friends), 0x43B690 (the maximum tip), 0x44B980 (every conception: the player's pair, catch-up, the Gong's
       0x44E8A0, a two-choice result 0x4204B0), 0x44F610, 0x44FE10, 0x450020, 0x464680.
  VV3  0x419B30 (the rescue rule: fewer than 3, 0x419BA5)  0x428C60 (load/tick: 0x428CB0/0x428CBE Highest
       Population, 0x428CCD-0x428D62 tips 694-697)  0x444FC0 / 0x452CB0 (the housing mood)  0x4584B0 (the player's
       pair: the trial limit, 0x4585D7, DEAD: its flag +0x12F2C is set to 1 at 0x427EB1, the only writer)  0x45FE30
       (room)  0x45FFE0 (sex rule, 0x46036A)  0x4684D0 (island events: 0x4686B4 game over line, 0x468743 attempt)
       0x468C10 / 0x46C070 (the number on screen).  Room callers: 0x414D80 (The Canoe from the Other Side), 0x415750
       -> 0x415770 (The Crystal of Reflections), 0x415310 / 0x415320 (Another One of Those Barrels), 0x428C60,
       0x444FC0, 0x452CB0, 0x455AB0 (every conception), 0x466760 (two adults dropped together, 0x466964).
       NOT the counter: the island events' multiplier m and Isola Day / Blessings Day (0x414C80, 0x414D10) count with
       the picker 0x45D460(7, -1, ...): children under 280, adults 360-999 not pregnant (+0xE8C), elders 1,000+.
  VV4  0x418000 (rescue, 0x4180CF)  0x420330 (world tick: achievements 25 A Good Start and 26 Crowd Control get the
       count, 0x42056A; Highest Population 0x420603; the maximum tip 745 via the room check 0x420646)  0x42EDE0
       (achievement 69 A Grandiose Feast at 50 or more, 0x42EF00)  0x43F750 (island events: 0x43F9BC game over line,
       0x43FA4E attempt)  0x440150 / 0x444860 (the number on screen)  0x460C10 (the player's pair: trial limit
       0x460D60; its flag +0x1711C is set to 1 at 0x41F4F3, the only writer)  0x468350 (room)  0x468430 (sex rule,
       0x468804).  Room callers: 0x414D50 / 0x414D90 (Daredevil Barrel...of Babies!), 0x414F60 (The Abandoned
       Infants; each of its pregnancies goes through the writer 0x45E7B0 with the check on, 0x467B00 -> 0x467C15),
       0x420330, 0x440C60 (two adults dropped together: "There isn't enough housing..." eSayConcernedHousing, say
       142), 0x45E7B0 (every conception unless its last argument is 1: only 0x43B830 passes 1, through 0x460990, a
       newcomer woman made pregnant on arrival -- which event or puzzle runs 0x43B830 was not traced).
       NOT the counter: achievement 71 Prolific Procreation counts mothers (0x467740: carrying, 18 or more).
  VV5  0x418870 (rescue, 0x418933)  0x425020 (the Divine Energy cap 5 x (count + 2), 0x425029)  0x425E30 (world
       tick: achievements 30 A Good Start and 31 Crowd Control, 0x42611F; Highest Population 0x4261B8; tips 738-741)
       0x442350 (island events: 0x44267B game over line, 0x4426FB attempt)  0x442CE0 / 0x4479B0 (the number on
       screen)  0x468040 (Faith: fewer than 12, 0x468163)  0x472BD0 (room)  0x472C90 (sex rule, 0x4730D3).  Room
       callers: 0x4151C0 (Barrel O' Babies! both kinds, Chutes Without Ladders, News From Another Tribe), 0x4151D0 /
       0x4152B0 / 0x415410 / 0x415510 (their bodies), 0x425E30, 0x443BF0 (two adults dropped together, say 128 =
       eSayConcernedHousing), 0x465E00 (every conception unless its last argument is 1: only 0x43E220 passes 1,
       through 0x467D20, as in VV4), 0x46E8E0 (catch-up embraces, 0x46E94C).  NOT the counter: achievement 60
       Prolific Procreation (0x471590: believers carrying, 18 or more).
  The achievement numbers are the order of the eString_Achievement*Title entries in Assets\\sm.xml (A Good Start 25,
  Crowd Control 26, A Grandiose Feast 69, Prolific Procreation 71 in VV4; 30, 31, 60 in VV5), the same numbering
  vv_game_mechanics_vv4 already uses for Know Which Way the Wind Blows (19).  The say strings are the eSay entries:
  VV4's game over line is say 147 = eSayGameOver (index 142), VV5's 132 (index 131), so VV4's 142 and VV5's 128 are
  eSayConcernedHousing.  VV1 has no achievements; neither does VV2 or VV3 (no caller of an achievement counter).
  The trial limit ("population under 7" unless a flag is set) is in VV1-VV4 only: docs/hidden-gates-all-five-games.md
  gates 49 (VV1), 13 (VV2), the VV3 dead demo gate and VV4 gate 46.

Nothing here writes anything.
"""
from __future__ import annotations

import vv_game_mechanics as gm

GROUP = "Babies being carried"

# Every call (or tail jump) to each game's population counter and room check in the stock exe, as listed above;
# tests/test_game_mechanics_carried.py checks the exes hold exactly these.  VV3 0x468851, VV4 0x43FB6E and VV5
# 0x4427DE are calls in the island trigger whose answer nothing reads.
COUNTER = {1: 0x41CF90, 2: 0x425860, 3: 0x45E8F0, 4: 0x467610, 5: 0x4713F0}
ROOM_CHECK = {1: 0x43A1A0, 2: 0x44B310, 3: 0x45FE30, 4: 0x468350, 5: 0x472BD0}
COUNTER_SITES = {
    1: (0x414AE2, 0x414BC7, 0x41F9F6, 0x42373C, 0x4237CB, 0x4239B0, 0x4280BF, 0x42A4AF, 0x42EF9F, 0x42F16C, 0x42F17B,
        0x42F199, 0x42F1E9, 0x42F215, 0x42F23D, 0x42F265, 0x43A1A9, 0x43DC12, 0x43DDD8, 0x446D52, 0x446E41, 0x44754A,
        0x44757C),
    2: (0x4196E8, 0x419763, 0x41F641, 0x41F729, 0x41F744, 0x4299F5, 0x42EE4C, 0x42EEDB, 0x42F0A1, 0x4335A9, 0x4335C4,
        0x433A04, 0x433C54, 0x433CBC, 0x4347D8, 0x436B3F, 0x43BE2D, 0x43C0C5, 0x43C0D4, 0x43C0E3, 0x43C139, 0x43C171,
        0x43C199, 0x43C1C1, 0x44B320, 0x44F748, 0x44F974, 0x44FE7D, 0x45009D, 0x4600DE, 0x460108, 0x464748, 0x464817),
    3: (0x419BA5, 0x428CB0, 0x428CBE, 0x428CCD, 0x428D06, 0x428D2E, 0x428D48, 0x428D62, 0x44503C, 0x452D18, 0x4585D7,
        0x45FE37, 0x46036A, 0x4686B4, 0x468743, 0x468851, 0x468C5A, 0x46C1D7),
    4: (0x4180CF, 0x42056A, 0x420603, 0x42EF00, 0x43F9BC, 0x43FA4E, 0x43FB6E, 0x4401AA, 0x444A15, 0x460D60, 0x468357,
        0x468804),
    5: (0x418933, 0x425029, 0x42611F, 0x4261B8, 0x44267B, 0x4426FB, 0x4427DE, 0x442D4B, 0x447B65, 0x468163, 0x472BD7,
        0x4730D3),
}
ROOM_SITES = {
    1: (0x419700, 0x428664, 0x42C358, 0x43BBC3, 0x43DE4E, 0x43E7A7, 0x43EABB, 0x447139),
    2: (0x41F604, 0x4217DF, 0x430EE2, 0x4347FD, 0x43480F, 0x43C146, 0x44B983, 0x44FB02, 0x44FE6E, 0x45008E, 0x464B35),
    3: (0x414D85, 0x415315, 0x41535A, 0x41539D, 0x415775, 0x428D15, 0x44502E, 0x452D0A, 0x455AB8, 0x466964),
    4: (0x414D55, 0x414DCA, 0x414E0D, 0x414F9D, 0x420646, 0x440E77, 0x45E7C1),
    5: (0x4151C5, 0x41520A, 0x41524D, 0x4152F2, 0x41533D, 0x41544A, 0x41548D, 0x415515, 0x4261FF, 0x443FB0, 0x465E11,
        0x46E94C),
}
DEAD = "DEAD (never runs): "
C, U = gm.CODE, False

# --- What the babies being carried count toward (the population counter), per game: (text, verified) -----------

SEX = ("A newborn's sex: while the count is 6 or fewer, the baby's sex is not rolled when one sex has more and the "
       "other has 2 or fewer: it is of the sex that has more (that balance itself counts living villagers only).")

ROOM = {
    1: ("Room for more people: no new pregnancy starts once the count reaches 90 (the normal game), and at 15, 25 "
        "and 50 the first, second and third hut must be built first. A village of 13 villagers with twins on "
        "the way is already at 15, so nobody else can conceive until the first hut is built."),
    2: ("Room for more people: no new pregnancy starts once the count reaches 90 plus 5 for each complete children's "
        "collection (115 with all four), and at 15, 25 and 50 the first, second and third hut must be built first."),
    3: ("Room for more people: no new pregnancy starts once the count reaches 90 plus 5 for each complete collection "
        "(115 with all four) plus 10 at Magic level 3, and at 10, 17 and 35 the first, second and third hut must be "
        "rebuilt first."),
    4: ("Room for more people: no new pregnancy starts once the count reaches 90 plus 5 for each complete collection "
        "(115 with all four), and at 10, 17 and 35 the first, second and third hut must be built first."),
    5: ("Room for more people: no new pregnancy starts once the count of believers and the babies they carry "
        "reaches 90 plus 5 for each complete collectible set (105 with both), and at 10, 17 and 35 the first, second "
        "and third hut must be built first."),
}
ROOM_USERS = {
    1: "every new pregnancy (the player's pairs, the villagers' own and while catching up); The Barrel O' Babies "
       "(it needs room, and each baby comes only while there is room); the Mysterious Crate's babies; The Mysterious "
       "Face's newcomer; and the villagers' mood about housing",
    2: "every new pregnancy (the player's pairs, the villagers' own, while catching up, the Gong of Wonder's and an "
       "island event's); The Barrel O' Babies, Old Friends and The Savage Child (each needs room); two adults "
       "dropped together (no room: the game shows a message, and the pregnancy is refused by the same check); and "
       "the villagers' mood about housing",
    3: "every new pregnancy; The Canoe from the Other Side, The Crystal of Reflections and Another One of Those "
       "Barrels (each needs room; the barrel's later babies come only while there is room); two adults dropped "
       "together (no room: they do not embrace and the game says so); and the villagers' mood about housing",
    4: "every new pregnancy, The Abandoned Infants' too (each of its up to 6 pregnancies only while there is room); "
       "Daredevil Barrel...of Babies! (it needs room, and its later babies come only while there is room); and two "
       "adults dropped together (no room: \"There isn't enough housing to support more population!\")",
    5: "every new pregnancy, The Abandoned Infants' too (each only while there is room); Barrel O' Babies! (both "
       "kinds), Chutes Without Ladders and News From Another Tribe (each needs room); two adults dropped together "
       "(no room: \"There isn't enough housing to support more population!\"); and the catch-up embraces",
}

COUNTS: dict[int, list[tuple[str, bool | str]]] = {
    1: [
        ("The building sites: the second hut's site appears once the count reaches 15 and the third's at 28.", C),
        ("Builders start the second hut on their own only above 22 and the third above 45 (a builder the player "
         "drops on a hut site builds it at any count).", C),
        ("Island events: an event comes only while the count is above 0, and the island events' strength n is the "
         "count divided by 3 (1 to 10), so carried babies can make an event stronger.", C),
        ("Isola Day Celebration: the stored food loses 10 for every person counted, carried babies included.", C),
        (SEX, C),
        ("Highest Population (the game's statistic) is the most the count has reached, carried babies included.", C),
        ("The population tips (\"...first population milestone of 15 people!\", 25, 50 and \"...maximum sustainable "
         "population!\") follow the count, so they can come before that many villagers are living.", C),
    ],
    2: [
        ("The building sites: the second hut's site appears once the count reaches 21 and the third's at 46.", C),
        ("Builders start the second hut on their own only above 22 and the third above 45.", C),
        ("Island events: an event comes only while the count is above 0; strength n is the count divided by 3 (1 to "
         "10); the amounts \"x k\" use the count too (two-choice events x2 above 25 and x3 above 50, single-result "
         "events x3 above 50).", C),
        ("The Silver Mirror needs a count of 2 or more, and A Dangerous Mission more than 60.", C),
        ("Isola Day and both Blessings Day Celebrations: the stored food loses 10 for every person counted, carried "
         "babies included.", C),
        (SEX, C),
        ("Highest Population is the most the count has reached, carried babies included.", C),
        ("The population tips (15, 25, 50 and \"...maximum sustainable population!\") follow the count.", C),
    ],
    3: [
        ("Rescue: when the count is below 3 (or the sexes are out of balance), 15% of island events are replaced by a "
         "rescue event (The Crystal of Reflections, The Canoe from the Other Side or Another One of Those Barrels).",
         C),
        ("Island events: an event comes only while the count is above 0.", C),
        (SEX, C),
        ("Highest Population is the most the count has reached, carried babies included.", C),
        ("The population tips (15, 25, 50 and \"...maximum sustainable population!\") follow the count.", C),
    ],
    4: [
        ("Rescue: when the count is below 3 (or the sexes are out of balance), a rescue may replace the island event "
         "(Daredevil Barrel...of Babies!).", C),
        ("Island events: an event comes only while the count is above 0.", C),
        ("Achievements: \"A Good Start\" (a population of 10) and \"Crowd Control\" (100) are given by the count, and "
         "\"A Grandiose Feast\" (\"50 villagers enjoyed a grand feast together\") needs a count of 50 or more when "
         "the grand feast is made, so carried babies can complete all three early.", C),
        (SEX, C),
        ("Highest Population is the most the count has reached, carried babies included.", C),
        ("Highest Population 6 with 5 villagers listed, one of them pregnant: seen in the owner's new village.",
         gm.OWNER),
        ("The \"...maximum sustainable population!\" tip comes at 90 or more when the room check says no.", C),
    ],
    5: [
        ("Rescue: when the count is below 3 (or the sexes are out of balance), a rescue may replace the island event "
         "(Chutes Without Ladders).", C),
        ("Island events: an event comes only while the count is above 0.", C),
        ("Divine Energy: the cap is 5 x (the count + 2), +50 with the Tribute Statue, so each carried baby raises "
         "the cap by 5.", C),
        ("Faith: with fewer than 12 counted, believers can lose Faith by chance (12 minus the count in 100); carried "
         "babies count toward the 12.", C),
        ("Achievements: \"A Good Start\" (a population of 10) and \"Crowd Control\" (100) are given by the count.", C),
        (SEX, C),
        ("Highest Population is the most the count has reached, carried babies included.", C),
        ("The population tips (15, 25, 50 and \"...maximum sustainable population!\") follow the count.", C),
    ],
}

# --- What counts only villagers (or fewer) ---------------------------------------------------------------------

ONLY = {
    1: [],
    2: [],
    3: [
        ("The island events' amounts (m) and the food Isola Day and Blessings Day take count no carried babies, and "
         "they also leave out pregnant women of 18 to 49 and everyone of 14 to 17: they count children under 14, "
         "adults of 18 to 49 who are not pregnant, and elders of 50 or more (m also leaves out the Tribal Chief).",
         C),
    ],
    4: [
        ("\"Prolific Procreation\" (\"10 villagers nursing simultaneously\") counts the mothers (18 or more), not "
         "their babies: twins count once.", C),
    ],
    5: [
        ("\"Prolific Procreation\" counts the mothers (believers, 18 or more), not their babies.", C),
        ("Heathens are never in the count, and neither are the babies a Heathen mother carries.", C),
    ],
}
COMMON_ONLY = [
    ("Eating: only villagers are fed. A mother eats as one villager and her carried babies eat nothing until they "
     "are born (the Food estimates count it this way).", C),
    ("Work: a pregnant villager does no work while the game catches up after time away, and the babies do none.", C),
    ("Island events: only villagers are picked; a carried baby is never picked, and many events leave out pregnant "
     "villagers.", C),
]
BALANCE = {1: "a newborn's sex", 2: "a newborn's sex", 3: "the rescue and a newborn's sex",
           4: "the rescue and a newborn's sex", 5: "the rescue and a newborn's sex"}

TRIAL = {
    # docs/hidden-gates-all-five-games.md: VV1 gate 49 (flag +0xABEC set at 0x41C892), VV2 gate 13 (+0x30380 set by
    # 0x425670), VV3 the dead demo gate (+0x12F2C, 0x427EB1), VV4 gate 46 (+0x1711C, 0x41F4F3).
    1: ("A leftover trial-version limit would refuse a pairing (and a catch-up cure) at a count of 7 or more, but "
        "its switch is turned on and nothing found turns it off; whether a save can turn it off was not traced.", U),
    2: ("A leftover trial-version limit would refuse a pairing (and a catch-up cure) at a count of 7 or more, but "
        "its switch is always turned on; the chain that turns it on was not traced to the start of the game.", U),
    3: (DEAD + "a leftover trial-version limit would refuse a pairing at a count of 7 or more; its switch is turned "
        "on and nothing ever turns it off.", C),
    4: ("A leftover trial-version limit would refuse a pairing at a count of 7 or more, but its switch is turned on "
        "when a village is made and nothing else writes it; whether a save can turn it off was not traced.", U),
}
ARRIVAL = ("A newcomer woman who arrives already pregnant skips the room check: the game's arrival code gives her a "
           "pregnancy with the check turned off. Which event or puzzle brings such a newcomer was not traced.")


def _patch(village: gm.Village, feature: str, effect: str) -> tuple[str, bool | str] | None:
    """A patcher line, or None when the patch is known not to be in the game."""
    has = village.has(feature)
    if has is False:
        return None
    where = "" if has else " (whether the game has it could not be told)"
    return f"With the patcher's \"{gm.feature_name(feature)}\"{where}: {effect}", C


def patch_lines(village: gm.Village) -> list[tuple[str, bool | str]]:
    game = village.game
    out = [
        # data/builds.json patch_modes; native: the modes' predicates (docs/max-population-research.md).
        ("The patcher's population modes (Collection Progression and Immediate Fixed Max Pop) change only the limit: "
         "the count is the same" + (", except that in New Believers those modes count every villager record in use "
         "(Heathens and bodies not yet buried too) plus every carried baby" if game == 5 else "") + ".", C),
        # docs/max-population-research.md "Twins and triplets at maximum minus one": min(rolled, slots - demand).
        ("The patcher's birth guard (in every game it patches): twins or triplets become fewer babies only when the "
         "villager table has too few free places; babies already being carried count as taken places.", C),
    ]
    out.append(_patch(village, f"vv{game}_isola_grand_event_collection",
                      "its rare events wait while the village is in trouble, which counts the carried babies (fewer "
                      "than 3 people with them counted is trouble)."))
    out.append(_patch(village, f"vv{game}_story_cheat_upgrades",
                      "a Custom Island Event can still come to a village whose count is 0 (everyone dead)."))
    feast = ("counts no carried babies (as the game's own Blessings Day)" if game == 3 else
             "counts the carried babies (the game's own count)")
    out.append(_patch(village, f"vv{game}_more_island_events",
                      f"the Remembrance Ceremony's feast (10 food a person) {feast}, and in the ceremony itself the "
                      "carried babies stay with their mothers (only villagers take part)"
                      + ({3: "; The Troubling Signs needs a count of 61 or more, carried babies included",
                          4: "; The Mysterious Mask needs a population counted with the carried babies"}.get(game, ""))
                      + "."))
    if game in (1, 4, 5):
        # native/vvfp_island_events_scale: the game's own counter.
        out.append(_patch(village, f"vv{game}_island_events_scale_with_population",
                          "the island events' amounts are x1 up to 25, x2 up to 50 and x3 above, by the count with "
                          "the carried babies."))
    if game == 1:
        # native/vvfp_fix_huts: the same above-22 / above-45 tests through 0x41CF90.
        out.append(_patch(village, "vv1_builders_fix_huts",
                          "idle builders start the second and third huts at the same counts (above 22 and above 45)."))
    return [line for line in out if line is not None]


def live_lines(village: gm.Village) -> list[gm.Fact]:
    """This save's count: villagers + carried babies = the counter, and who carries how many."""
    import vv_game_mechanics_life as life
    everyone = life.people(village)
    if everyone is None:
        return [gm.Fact(GROUP, "This village now: the villager table could not be read.", gm.SAVE)]
    members = life.tribe(everyone)
    mothers = [p for p in members if p.carrying]
    babies = sum(p.babies for p in mothers)
    who = "believers" if village.game == 5 else "villagers"
    out = [gm.Fact(GROUP, f"This village now: {len(members)} {who} + {babies} bab{'y' if babies == 1 else 'ies'} "
                          f"being carried = {len(members) + babies} on the population counter.", gm.SAVE)]
    for p in mothers:
        out.append(gm.Fact(GROUP, f"{p.name}: {life._babies_words(p.babies)}.", gm.SAVE, True))
    outside = [p for p in everyone if p.heathen and p.carrying]
    if outside:
        out.append(gm.Fact(GROUP, f"Heathen mothers outside the count: {len(outside)}, carrying "
                                  f"{sum(p.babies for p in outside)}.", gm.SAVE, True))
    return out


def facts(village: gm.Village) -> list[gm.Fact]:
    game = village.game
    out: list[gm.Fact] = []
    add = lambda text, ok=C, sub=False: out.append(gm.Fact(GROUP, text, ok, sub))  # noqa: E731
    who = "believers" if game == 5 else "villagers"
    add(f"In short: each baby being carried counts as 1 on the game's population counter from the moment it is "
        f"conceived (twins 2, triplets 3), but it eats nothing, does no work and is never picked for anything until it "
        f"is born. So the count can be above the number of {who}, and it matters wherever the game checks the count: "
        "room for new babies and newcomers above all.")
    add("The population number on the game's screen (beside the food and tech points) is this count.")
    if not village.general:
        out.extend(live_lines(village))
    add("What the carried babies count toward (the game itself):")
    add(ROOM[game], C, True)
    add(f"The room check is used by {ROOM_USERS[game]}. A pregnancy refused for lack of room fails without a word.",
        C, True)
    if game in (4, 5):
        add(ARRIVAL, U, True)
    for text, ok in COUNTS[game]:
        add(text, ok, True)
    if game in TRIAL:
        add(TRIAL[game][0], TRIAL[game][1], True)
    add("What counts only villagers (the carried babies are not counted):")
    for text, ok in COMMON_ONLY + ONLY[game]:
        add(text, ok, True)
    add(f"The balance of men and women in {BALANCE[game]}: living villagers only"
        + (", Heathens included in a newborn's sex" if game == 5 else "") + ".", C, True)
    add("The patcher's features:")
    for text, ok in patch_lines(village):
        add(text, ok, True)
    return out
