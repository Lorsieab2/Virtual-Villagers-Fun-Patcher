"""The Tree of Life (VV4) and New Believers (VV5): the Nursery School's lessons, and why children or Heathens gain
skills -- lines of the Game Mechanics "Tech points and effects" group (vv_game_mechanics_vv4.py / _vv5.py call
`lines`; the Time away group and the building entries point here).

Read from the stock exes (research/stock-executables; tests/nursery_emulation.py runs the lesson itself and
tests/test_game_mechanics_nursery.py pins every number and address below).  New Believers first, The Tree of Life in
brackets where it differs:
  * the teacher: the Nursery School's drop handler 0x43AA30 [0x4376E0]: on the unfinished building (project 24
    CNurseryHut [24]) the villager builds (job 16, 0x43AB00 [0x4377BC]); on the finished one 0x43A990 [0x437620]
    wants at least 3 of the skills at a whole 50 or more, or the villager says "Not enough skills to teach!" (string
    0x208 at 0x43AB3A [0x253 at 0x4377F6]); the first good drop solves project 0 CNurserySchool [puzzle 8] (vtable +0x28
    -> 0x43A7A0 -> 0x43AF80(0) [0x437440 -> 0x438A30(8)]), the one teaching now (action 0x6F [0x7E], 0x43A830
    [0x4374C0]) has its queue cleared (0x473440 [0x468C60]) and the new one gets job 8 (0x43AA06 [0x4376B4]) and action
    0x6F "Teaching at the nursery school" [0x7E]; the job dispatcher 0x46BCF0 re-queues 0x6F for job 8 (0x46BE6B).
    Pick-up refuses Heathens only (0x445F32, tip "You cannot touch heathens because they do not believe in you.").
  * solving it 0x43A7D0 [0x437470]: 0x470810(7) [0x466BF0(0x30)] gives every living, not sick believer the
    "Celebrating" action 0x31 -> 0x45B690 [0x2A -> 0x453F50] (walk, sparkle, dance steps: no skill), the tip
    eTipPuzzleNurserySchoolComplete (0x43A7F0 [0x43748A]) and a trophy counter (0x413450(0x32) [0x412F90(0x2E)]).
  * the lesson, in the noni tick 0x425E30 [world tick 0x420330], once per age unit (the village update 0x442350 calls
    it at 0x4425C0; while catching up, once for every missed age unit): the teacher 0x471BB0(8) [0x467C50(8)] -- the
    villagers with job 8 who are active, +0x1CE1 clear and health above 0, one at random (rand(count)); none, no
    lesson.  Total = the teacher's skills, each cut to a whole number (0x47C9B0 [0x471630]), added (0x475670
    [0x46ACD0]); lesson = total ÷ (1440.0 ÷ speed) ÷ 10.0 (0x498B38 / 0x498B30 [0x48D688 / 0x48D680]) = total x speed
    ÷ 14,400.  One rand(100) < 50 (0x425FC5 [0x420439]) for the whole tick: whole lesson to the top skill, else
    lesson ÷ 5.0 (0x498810 [0x48D678]) to each skill.  The children: every active record with +0x1CE1 clear (0x466170
    [+0x1CC4 set, the ghost byte +0x1CC7 clear]) and age under 280 units (0x42600E [0x420487]); no Heathen test
    (+0x1CEC is never read).  Top skill 0x4755C0 [0x46AC20]: walking the list, a skill is taken when it is above the
    whole number of the one taken so far; -1 when none is above 0, then rand(6) [rand(5)] (0x42603B [0x4204B4]).
    Each award only to a skill whose whole number is below 50 (0x426053 / 0x426077 [0x4204CC / 0x4204EE]), through
    the adder 0x475730 [0x46AD80], which keeps 0 to 100 (100.0 at 0x4957D8 / 0x4980D4).
  * joining the tribe: the Faith setter 0x467F90 calls 0x4668B0 when Faith rises above 0 (0x467FBD): sound, sparkle,
    0x470810(9) (everyone celebrates), the joiner's action 0xDC (0x463230: walk and sparkle steps), "There is a new
    believer!", the role cleared unless it is 13 (0x466966), the Heathen flag cleared (0x466880 writes +0x1CEC,
    +0x2F14, +0x2F40 only), The Last Heathen check, the queue cleared: no skill is read or written.
  * the Heathen Chief: the new village's set-up 0x4259D0 calls 0x424AC0 (0x425DBB), which makes him (role 13,
    0x424D5F) and sets his six skills to 100.0 (0x424D87-0x424DAF).
  * the Earthquake 0x41F746-0x41F7CC: Faith +2 to +8 (rand(7) + 2) through 0x468020 for everyone but roles 12-17; no
    skill.
Read only.
"""
from __future__ import annotations

import vv_game_mechanics as gm

GROUP = "Tech points and effects"
VV5_NURSERY = "vv5_vv4_nursery_divisor_parity"

# Per game: skills in the game's order, the teacher's best total, and the addresses quoted in the lines.
SKILLS = {4: ("Farming", "Parenting", "Healing", "Research", "Building"),
          5: ("Farming", "Parenting", "Healing", "Research", "Building", "Devotion")}
SPEEDS = (gm.FAST, gm.NORMAL, gm.SLOW)
CHILDHOOD = 280                         # age units: a child is under 14 villager years
DIVISOR = 14_400                        # the lesson: total x speed ÷ 14,400


def lesson(total: int, speed: int) -> float:
    """One age unit's whole lesson."""
    return total * speed / DIVISOR


def per_hour(total: int) -> float:
    """A whole lesson's worth per real-life hour (60 ÷ speed age units an hour): the same at every speed."""
    return total / 240


def average_top_per_hour(total: int) -> float:
    """On average a real-life hour: half the age units the whole lesson, half a fifth of it (the top skill)."""
    return per_hour(total) / 2 + per_hour(total) / 2 / 5


def average_other_per_hour(total: int) -> float:
    return per_hour(total) / 2 / 5


def _n(x: float) -> str:
    """A rate to 4 decimals, trailing zeros dropped (0.125, 0.25, 0.4167, 1.5)."""
    return f"{x:.4f}".rstrip("0").rstrip(".")


def _three(values, digits: int = 4) -> str:
    a, b, c = (f"{v:.{digits}f}".rstrip("0").rstrip(".") for v in values)
    return f"{a}, {b} or {c}"


def lines(village: gm.Village, game: int) -> list[gm.Fact]:
    out: list[gm.Fact] = []
    add = lambda text, ok=gm.CODE, sub=False: out.append(gm.Fact(GROUP, text, ok, sub))  # noqa: E731
    vv5 = game == 5
    names = SKILLS[game]
    n = len(names)
    best = 100 * n
    half = 50 * n
    listed = ", ".join(names)
    a = {
        "drop": "0x43AA30" if vv5 else "0x4376E0",
        "check": "0x43A990" if vv5 else "0x437620",
        "build": "0x43AB00" if vv5 else "0x4377BC",
        "solve": "0x43A9E9" if vv5 else "0x437679",
        "job": "0x43AA06" if vv5 else "0x4376B4",
        "old": "0x43A830 -> 0x473440" if vv5 else "0x4374C0 -> 0x468C60",
        "done": ("0x43A7D0, the celebration 0x470810 -> 0x45B690" if vv5
                 else "0x437470, the celebration 0x466BF0 -> 0x453F50"),
        "tip": "0x43A7F0" if vv5 else "0x43748A",
        "tick": ("the noni tick 0x425E30, which the village's update calls at 0x4425C0" if vv5
                 else "the world tick 0x420330"),
        "teacher": "0x471BB0" if vv5 else "0x467C50",
        "total": "0x475670" if vv5 else "0x46ACD0",
        "math": "0x425FA7-0x425FC1" if vv5 else "0x420418-0x420435",
        "roll": "0x425FC5" if vv5 else "0x420439",
        "child": "0x426001-0x42600E" if vv5 else "0x42046D-0x420487",
        "nothing": "0x426056" if vv5 else "0x4204CF",
        "spread": "0x425FDF, 0x42606A-0x426095" if vv5 else "0x420453, 0x4204E3-0x42050C",
        "top": "0x4755C0" if vv5 else "0x46AC20",
        "draw": "0x42603B" if vv5 else "0x4204B4",
        "add": "0x475730" if vv5 else "0x46AD80",
    }
    puzzle = "milestone (not on the Puzzles screen; " if vv5 else "puzzle ("
    count = "six" if vv5 else "five"
    crowd = "the believers" if vv5 else "the villagers"
    add(f"Nursery School, the teacher: the player drops a villager on the finished Nursery School; with at least 3 "
        f"of the {count} skills at 50 or more (whole numbers) that villager becomes the teacher (job 8, {a['job']}), "
        f"otherwise they say \"Not enough skills to teach!\" ({a['drop']} -> {a['check']}). On the unfinished "
        f"building they build it instead ({a['build']}). The first teacher also solves The Nursery School {puzzle}"
        f"{a['solve']}). A new teacher interrupts the one teaching now ({a['old']}: only the action queue is "
        "cleared, the old teacher's job is left as it is).")
    if vv5:
        add("Heathens cannot be picked up (\"You cannot touch heathens because they do not believe in you.\", "
            "0x445F32), so the player can never make a Heathen the teacher. The teacher pick 0x471BB0 has no Heathen "
            "test, so a teacher who becomes a Heathen would go on teaching if the job stays the Nursery School; "
            "whether it stays was not traced.", False, True)
    add(f"Solving The Nursery School gives no skill: {crowd} stop to celebrate (\"Celebrating\") and the tip "
        f"\"The Nursery School ... This will help them raise smarter children.\" shows ({a['done']}, the tip "
        f"{a['tip']}). The lessons below start with the first teacher and go on with no end, as long as someone has "
        "the Nursery School as their job.")
    add(f"Nursery School, the lesson: once every age unit (3, 6 or 10 real-life minutes on Fast, Normal or Slow; "
        f"{a['tick']}; paused, none), the game picks a villager whose job is the Nursery School, one at random when "
        f"there are several ({a['teacher']}); with none there is no lesson. The lesson is the teacher's {count} "
        f"skills, each cut to its whole number, added up (0 to {best:,}, {a['total']}) x the speed value (3, 6 or 10) "
        f"÷ 14,400 ({a['math']}).")
    if vv5:
        who = ("every child under 14 villager years (under 280 age units; Heathen children included, as the child "
               f"test has no Heathen test, {a['child']})")
    else:
        who = f"every child under 14 villager years (under 280 age units) who is not a ghost ({a['child']})"
    whole = ", Devotion included: six fifths in all" if vv5 else ": exactly one lesson in all"
    add(f"One roll for the whole age unit, 50 in 100 ({a['roll']}): {who} gets either the whole "
        f"lesson in its top skill, only if that skill's whole number is below 50 (at 50 or more that child gets "
        f"nothing that age unit, {a['nothing']}), or a fifth of the lesson in every skill whose whole number is "
        f"below 50 ({a['spread']}){whole}.")
    if vv5 and village.has(VV5_NURSERY) is True:
        add(f"With \"{gm.feature_name(VV5_NURSERY)}\" (in this game): a sixth instead of a fifth, exactly one lesson "
            "in all (0x425FDF reads a private 6.0).", gm.CODE, True)
    add(f"The top skill ({a['top']}): the game walks {listed} and takes a skill whenever it is above the whole number "
        f"of the one taken so far, so among skills with the same whole number the last one that has any fraction "
        f"wins ({names[-1]} over all the others); while every skill is 0 a skill is drawn for that child, each 1 in "
        f"{n} ({a['draw']}).")
    add(f"Skills keep their fractions (32-bit floats, nothing is rounded away) and stay 0 to 100 ({a['add']}); the 50 "
        f"test is on the whole number before the lesson is added, so a skill can end a little above 50 (49.9 + "
        f"{_n(lesson(100 * n, gm.SLOW))} = {_n(49.9 + lesson(100 * n, gm.SLOW))} on Slow with a {100 * n:,} teacher).")
    top6 = average_top_per_hour(best)
    oth6 = average_other_per_hour(best)
    weakest = 150
    add(f"How much: the same per real-life hour at every speed, and per hour the game is closed (catch-up): a whole "
        f"lesson's worth is the teacher's total ÷ 240 a real-life hour. With a teacher at 100 in every skill "
        f"({best:,}): per age unit {_three(lesson(best, s) for s in SPEEDS)} (Fast, Normal, Slow) in the top skill, or "
        f"{_three(lesson(best, s) / 5 for s in SPEEDS)} in each skill below 50; on average a child's top skill gains "
        f"{_n(top6)} a real-life hour and every other skill below 50 gains {_n(oth6)}. At 50 in every skill "
        f"({half:,}): half that, {_n(average_top_per_hour(half))} and {_n(average_other_per_hour(half))}. The "
        f"weakest teacher (3 skills at 50, the rest 0: {weakest}): {_n(average_top_per_hour(weakest))} and "
        f"{_n(average_other_per_hour(weakest))}.")
    tops = [CHILDHOOD * lesson(best, s) * 0.6 for s in SPEEDS]
    others = [CHILDHOOD * lesson(best, s) * 0.1 for s in SPEEDS]
    add(f"Game speed: it does not change the gain per real-life hour, but a child's 280 age units last 14, 28 or 46 "
        f"hours 40 minutes of real-life play on Fast, Normal or Slow, so a slower speed gives each child more by its "
        f"14th birthday: with a {best:,} teacher on average {_three(tops, 1)} in its top skill (a skill passing 50 "
        f"stops there) and {_three(others, 1)} in every other skill.")

    # -- Why children or Heathens gain skills ---------------------------------------------------------------
    last = names[-1]
    if vv5:
        add("Why children or Heathens gain skills (the code's answer):")
        add("A Heathen child gains Devotion: the lesson's child test has no Heathen test, and Heathens never age (the "
            "life tick skips them, 0x472CB7), so a Heathen child stays under 14 and keeps getting lessons with no end "
            "until its skills reach 50. While every skill of a child is below a whole 1 they all count as tied and "
            "the tie goes to the last, Devotion, so once Devotion is above 0 (a spread age unit gives it a fifth) "
            "Devotion gets the whole lessons, unless the skill drawn at the child's first lesson reaches a whole 1 "
            "first. Emulated with the game's own code (400 children from 0, a 600 teacher): Devotion became the "
            "trained skill for 394, 371 and 341 of them on Fast, Normal and Slow. The same happens to a believer "
            "child whose skills are all below 1.", gm.CODE, True)
        add("Village children gain in all six skills at once: on the spread age units (half of them, one roll for "
            "every child together) each child gets a fifth of the lesson in every skill whose whole number is below "
            "50 (0x42606A-0x426095).", gm.CODE, True)
        add("The Nursery School's completion is not a skill gain: it only makes the believers celebrate; it is the "
            "first teacher who starts the lessons, at the same drop.", gm.CODE, True)
        add("A Retired Heathen Chief's joining gives no skill: joining the tribe (0x4668B0, from the Faith setter "
            "0x467F90 when Faith rises above 0) makes everyone celebrate, keeps the Chief's role (0x466966; every "
            "other role is cleared) and clears the Heathen flag (0x466880), and reads or writes no skill. The Heathen "
            "Chief is made with all six skills at 100 (0x424D87-0x424DAF, from the new village's set-up 0x4259D0 at "
            "0x425DBB) and keeps them; as a believer he can be picked up (the pick-up refuses only Heathens, "
            "0x445F32), so dropped on the finished Nursery School he is a teacher with the highest total, 600, "
            "and every child's lessons are the largest the game gives (2.5 a real-life hour, at every speed).", gm.CODE, True)
        add("The Earthquake gives no skill: it adds 2 to 8 Faith (rand(7) + 2, 0x41F78F) to every villager but the "
            "six special roles; a Heathen whose Faith rises above 0 joins the tribe through the same join, which "
            "changes no skill, however many times it is cast. A Heathen child who joins keeps the skills the Nursery "
            "School gave it, starts ageing like every believer and has its last lesson before its 14th birthday.",
            gm.CODE, True)
        add("An adult Heathen (14 or more) gets no lessons (the age test 0x42600E).", gm.CODE, True)
        add("The owner (in play): Heathens, child Heathens most of all, sometimes gain Devotion at random, and "
            "village children sometimes gain in all six skills, seen around the Nursery School's completion, a "
            "Retired Heathen Chief's conversion or repeated Earthquakes.", gm.OWNER, True)
    else:
        add("Why children gain skills (the code's answer):")
        add(f"While every skill of a child is below a whole 1 they all count as tied and the tie goes to the last, "
            f"{last}, so once {last} is above 0 (a spread age unit gives it a fifth) {last} gets the whole lessons, "
            "unless the skill drawn at the child's first lesson reaches a whole 1 first. Emulated with the game's "
            f"own code (400 children from 0, a 500 teacher): {last} became the trained skill for 398, 385 and 357 of "
            "them on Fast, Normal and Slow.", gm.CODE, True)
        add("Children gain in all five skills at once: on the spread age units (half of them, one roll for every "
            "child together) each child gets a fifth of the lesson in every skill whose whole number is below 50 "
            "(0x4204E3-0x42050C).", gm.CODE, True)
        add("The Nursery School's completion is not a skill gain: it only makes the villagers celebrate; it is "
            "the first teacher who starts the lessons, at the same drop.", gm.CODE, True)
    return out
