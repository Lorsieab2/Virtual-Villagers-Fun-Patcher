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
  * nursing mothers (pregnant and nursing are one state, the conception field +0x1C4C; the carried babies are a count
    on the mother, not records): the villager's next-action chooser sends a mother to the mother activities 0x46A1D0
    from 0x46F0FD [0x461A30 from 0x4658AD]; the job gate skips work while she carries (0x46E918 [0x465788]), so job 8's
    re-queue of the teaching action never runs for her.  The drop: the hotspot dispatcher 0x4794A0 [0x46E460] refuses
    a carrying villager unless the hotspot's flag is 1 (0x479521 [0x46E4CB]) with tip 0x2D0 [0x2DF]
    eTTipStandAloneMommiesNoWork (0x47953D [0x46E4E7]); the Nursery School registers flag 0 (0x479810(0x11, 0x43AA30,
    -1, 0) at 0x43AB8B [0x46E5E0(0x22, 0x4376E0, -1, 0) at 0x43784B]), so its handler never sees her, built or not.
    The tip routine [0x44B890] skips a tip already shown unless forced; the dispatcher does not force it.  The teacher
    pick 0x471BB0 [0x467C50] and the lesson's child test have no carrying test.  Conceiving 0x465E00 [0x45E7B0] adds
    max(5, (100 - Parenting) / 10) Parenting (0x465E1E-0x465E62 [0x45E7CE-0x45E812]) and changes no job; the game's own
    conception step [0x464FF8-0x46511B] clears no queue.  A new teacher clears only the villager doing the teaching
    action (0x43A830 [0x4374C0 -> 0x4678F0(0x7E)]).  The hover caption: [0x437749-0x437775 picks "under construction"
    or "foundation"]; New Believers always passes 0x206 "under construction" (0x43AAB5), the 0x43AEA0 count unused.
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


MOTHER_TIP = "Nursing mothers don't work while they are caring for an infant."
# The mother activities each game's picker offers (captions from Assets\sm.xml; the picker's action list).
MOTHER_ACTIVITIES = {
    4: ("Washing baby", "Changing baby", "Showing baby the cooking area", "Showing baby the blackberries",
        "Showing baby the tree", "Showing baby the fish statue", "Showing baby the tide pool",
        "Showing baby the beach", "Showing baby the wind flutes"),
    5: ("Washing baby", "Changing baby", "Showing baby the noni", "Showing baby the statue",
        "Showing baby the aqueduct", "Showing baby the stream", "Showing baby the hidden grove"),
}


def mother_lines(add, village: gm.Village, game: int) -> None:
    """Nursing mothers and the Nursery School: the game's behaviour, read from the stock exes (addresses in the
    module docstring).  Nothing here is changed by the patcher."""
    vv5 = game == 5
    # The chooser 0x46F0FD [0x4658AD] -> the mother picker; the job gate 0x46E918 [0x465788]; the dispatcher's
    # carrying test 0x479521 [0x46E4CB]; the teacher pick 0x471BB0 [0x467C50].
    add("Nursing mothers and the Nursery School: a nursing mother (pregnant and nursing are one state: she carries "
        "her baby or babies until they are born) never goes to the Nursery School on her own and is refused when "
        "dropped on it; her carried babies get no lessons. A teacher who becomes a mother keeps the job, and the "
        "lessons go on while she looks after her baby elsewhere.")
    add("On her own: a nursing mother only does the mother activities (" + ", ".join(MOTHER_ACTIVITIES[game]) +
        ") and does no work, so she never walks to the Nursery School and never does \"Teaching at the nursery "
        "school\", even when the Nursery School is her job.", gm.CODE, True)
    # Emulated: the dispatcher with the Nursery's registration, a carrying adult -> the tip, the handler not called.
    add(f"Dropped on it: the game refuses her before the Nursery School is asked, on the finished school and on the "
        f"building site alike, with the tip \"{MOTHER_TIP}\" (emulated with the game's code). So a mother cannot "
        "build it or become the teacher. Being picked up stops what she was doing; she then picks a new mother "
        "activity.", gm.CODE, True)
    add("That tip shows only once: the game skips a tip it has already shown, so later drops of a nursing mother "
        "on the Nursery School are refused with no message (the skip is in the code; where the game marks the tip "
        "as shown was not traced).", False, True)
    add("Her babies: carried babies are not villagers yet, and the lesson goes only to villagers under 14, so the "
        "unborn and carried babies get nothing. Once born they are children and get the lessons like every child, "
        "wherever they are.", gm.CODE, True)
    add("Her skills: the Nursery School gives a mother nothing. Conceiving itself raises her Parenting by a tenth of "
        "what she lacks of 100, at least 5 (Parenting 20 gains 8, Parenting 80 gains 5).", gm.CODE, True)
    add("A teacher who becomes a mother keeps the Nursery School as her job: the game's pick of the teacher looks "
        "only at the job and at being alive and present, not at a baby or at where the teacher is. So every child "
        "keeps getting her full lessons for the whole time she carries, while she does mother activities "
        "elsewhere.", gm.CODE, True)
    add("Whether she first finishes a teaching round she had already started when she conceived was not traced.",
        False, True)
    add("Two teachers: a new teacher dropped on the school stops only the villager teaching right now. A teacher "
        "who is a mother is not teaching, so she keeps the job too; both are then teachers and each age unit the "
        "lesson uses one of them, picked at random.", gm.CODE, True)
    if vv5:
        # Grant Youth keeps the pregnancy (vv_game_mechanics_items_vv5 "Grant Youth"); child test 0x426001-0x42600E.
        add("A pregnant child: Grant Youth keeps a pregnancy, and the lesson's child test has no pregnancy test, so "
            "a pregnant villager made 5 years old again gets the Nursery School's lessons like any child while she "
            "carries (not seen in play).", gm.CODE, True)
        # 0x43AAB5: always 0x206; the 0x43AEA0 count is fetched and not used.  Fix Vanilla Bugs rewrites
        # 0x43AA99-0x43AAC0 (tests/test_vv5_nursery_foundation_caption.py).
        add("Walking past the unfinished school a villager always says \"{name} sees a nursery school under "
            "construction.\"; the game's other line, \"{name} sees a nursery school foundation.\", is never used "
            "(the game works out whether only the foundation is there, then ignores it).", gm.CODE, True)
        add(gm.patch_words(village, "vv5_fix_vanilla_bugs",
                           "it says \"{name} sees a nursery school foundation.\" while nothing is built yet and "
                           "\"... under construction.\" once building has started, as in The Tree of Life"),
            gm.CODE, True)


def lines(village: gm.Village, game: int) -> list[gm.Fact]:
    out: list[gm.Fact] = []
    add = lambda text, ok=gm.CODE, sub=False: out.append(gm.Fact(GROUP, text, ok, sub))  # noqa: E731
    vv5 = game == 5
    names = SKILLS[game]
    n = len(names)
    best = 100 * n
    half = 50 * n
    listed = ", ".join(names)
    # The code behind each line below, New Believers first, The Tree of Life in brackets:
    #   the teacher: the drop 0x43AA30 [0x4376E0] -> the check 0x43A990 [0x437620]; job 8 set at 0x43AA06 [0x4376B4];
    #     building 0x43AB00 [0x4377BC]; the solve 0x43A9E9 [0x437679]; a new teacher clears the old one's action
    #     queue 0x43A830 -> 0x473440 [0x4374C0 -> 0x468C60]; Heathens cannot be picked up 0x445F32; the teacher pick
    #     0x471BB0 has no Heathen test;
    #   solving: 0x43A7D0, the celebration 0x470810 -> 0x45B690, the tip 0x43A7F0 [0x437470, 0x466BF0 -> 0x453F50,
    #     0x43748A];
    #   the lesson: the noni tick 0x425E30, called by the village's update at 0x4425C0 [the world tick 0x420330]; the
    #     teacher 0x471BB0 [0x467C50]; the total 0x475670 [0x46ACD0]; the sum 0x425FA7-0x425FC1 [0x420418-0x420435];
    #   the roll 0x425FC5 [0x420439]; the child test 0x426001-0x42600E [0x42046D-0x420487]; nothing at 50 or more
    #     0x426056 [0x4204CF]; the spread 0x425FDF, 0x42606A-0x426095 [0x420453, 0x4204E3-0x42050C]; with the
    #     divisor patch 0x425FDF reads a private 6.0;
    #   the top skill 0x4755C0 [0x46AC20]; the draw while all are 0 0x42603B [0x4204B4]; Fix Vanilla Bugs' tie-break
    #     0x42602F -> 0x4264C3, chained through the padding to 0x4295F2 [0x4204A8 -> 0x420313 -> 0x423972], the
    #     routine's other callers unchanged;
    #   skills are 32-bit floats kept 0 to 100 by the adder 0x475730 [0x46AD80].
    puzzle = "milestone (it is not on the Puzzles screen)" if vv5 else "puzzle"
    count = "six" if vv5 else "five"
    crowd = "the believers" if vv5 else "the villagers"
    add(f"Nursery School, the teacher: the player drops a villager on the finished Nursery School; with at least 3 "
        f"of the {count} skills at 50 or more (whole numbers) that villager becomes the teacher, otherwise they say "
        "\"Not enough skills to teach!\". Dropped on the unfinished building, they build it instead. The first "
        f"teacher also solves The Nursery School {puzzle}. A new teacher interrupts the one teaching now, but only "
        "stops what they are doing: the old teacher's job is left as it is.")
    if vv5:
        add("Heathens cannot be picked up (\"You cannot touch heathens because they do not believe in you.\"), so "
            "the player can never make a Heathen the teacher. The game's pick of the teacher has no Heathen test, so "
            "a teacher who becomes a Heathen would go on teaching if the job stays the Nursery School; whether it "
            "stays was not traced.", False, True)
    mother_lines(add, village, game)
    add(f"Solving The Nursery School gives no skill: {crowd} stop to celebrate (\"Celebrating\") and the tip "
        "\"The Nursery School ... This will help them raise smarter children.\" shows. The lessons below start with "
        "the first teacher and go on with no end, as long as someone has the Nursery School as their job.")
    add("Nursery School, the lesson: once every age unit (3, 6 or 10 real-life minutes on Fast, Normal or Slow; none "
        "while paused), the game picks a villager whose job is the Nursery School, one at random when there are "
        f"several; with none there is no lesson. The lesson is the teacher's {count} skills, each cut to its whole "
        f"number and added up (0 to {best:,}), x the speed value (3, 6 or 10) ÷ 14,400.")
    if vv5:
        who = ("every child under 14 villager years (under 280 age units; Heathen children included, as the game's "
               "child test has no Heathen test)")
    else:
        who = "every child under 14 villager years (under 280 age units) who is not a ghost"
    whole = ", Devotion included: six fifths in all" if vv5 else ": exactly one lesson in all"
    add(f"Who gets the lesson: one 50-in-100 roll each age unit, for all the children together. Either {who} gets "
        "the whole lesson in its top skill, only if that skill's whole number is below 50 (at 50 or more that child "
        "gets nothing that age unit), or (a spread age unit) each gets a fifth of the lesson in every skill whose whole number is below "
        f"50{whole}.")
    if vv5 and village.has(VV5_NURSERY) is True:
        add(f"With \"{gm.feature_name(VV5_NURSERY)}\" (in this game): a sixth instead of a fifth, exactly one lesson "
            "in all.", gm.CODE, True)
    add(f"The top skill: the game goes through {listed} in that order and takes a skill whenever it is above the "
        "whole number of the one taken so far, so among skills with the same whole number the last one that has any "
        f"fraction wins ({names[-1]} over all the others); while every skill is 0 a skill is drawn for that child, "
        f"each 1 in {n}.")
    fix = f"vv{game}_fix_vanilla_bugs"
    add(gm.patch_words(village, fix, "skills with the same whole number tie and the tie is broken at random, each "
                                     "tied skill equally likely (the game's other uses of the top skill are "
                                     "unchanged); the 50 test, the 50-in-100 roll, the spread and the amounts stay as "
                                     "above"),
        gm.CODE, True)
    add("Skills keep their fractions (nothing is rounded away) and stay 0 to 100; the 50 test is on the whole number "
        "before the lesson is added, so a skill can end a little above 50 (49.9 + "
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
        # Heathens never age: the life tick skips them (0x472CB7).
        add("A Heathen child gains Devotion: the lesson's child test has no Heathen test, and Heathens never age, so "
            "a Heathen child stays under 14 and keeps getting lessons with no end until its skills reach 50. While "
            "every skill of a child is below a whole 1 they all count as tied and the tie goes to the last, Devotion, "
            "so once Devotion is above 0 (a spread age unit gives it a fifth) Devotion gets the whole lessons, unless "
            "the skill drawn at the child's first lesson reaches a whole 1 first. Emulated with the game's code (400 "
            "children from 0, a 600 teacher): Devotion became the trained skill for 394, 371 and 341 of them on Fast, "
            "Normal and Slow. The same happens to a believer child whose skills are all below 1.", gm.CODE, True)
        add(gm.patch_words(village, fix, "a tie goes to any of the tied skills, each equally likely, so a child from 0 "
                                         "is trained in each skill about 1 in 6 times (emulated, 400 children: "
                                         "Devotion 85, 62 and 57 of them on Fast, Normal and Slow)"), gm.CODE, True)
        add("Village children gain in all six skills at once: on the spread age units (half of them, one roll for "
            "every child together) each child gets a fifth of the lesson in every skill whose whole number is below "
            "50.", gm.CODE, True)
        add("The Nursery School's completion is not a skill gain: it only makes the believers celebrate; it is the "
            "first teacher who starts the lessons, at the same drop.", gm.CODE, True)
        # Joining: 0x4668B0, from the Faith setter 0x467F90 when Faith rises above 0; the role kept 0x466966; the
        # Heathen flag cleared 0x466880.  The Chief's skills: 0x424D87-0x424DAF, from the new village's set-up
        # 0x4259D0 at 0x425DBB.  The pick-up refuses only Heathens: 0x445F32.
        add("A Retired Heathen Chief's joining gives no skill: joining the tribe makes everyone celebrate, keeps the "
            "Chief's role (every other role is cleared) and clears the Heathen flag, and reads or writes no skill. "
            "The Heathen Chief is made with all six skills at 100 when the village is set up, and keeps them; as a "
            "believer he can be picked up (only Heathens cannot be), so dropped on the finished Nursery School he is "
            "a teacher with the highest total, 600, and every child's lessons are the largest the game gives (2.5 a "
            "real-life hour, at every speed).", gm.CODE, True)
        # The Earthquake's Faith: rand(7) + 2 at 0x41F78F.
        add("The Earthquake gives no skill: it adds 2 to 8 Faith to every villager but the six special roles; a "
            "Heathen whose Faith rises above 0 joins the tribe through the same join, which changes no skill, however "
            "many times it is cast. A Heathen child who joins keeps the skills the Nursery School gave it, starts "
            "ageing like every believer and has its last lesson before its 14th birthday.", gm.CODE, True)
        # The lesson's age test: 0x42600E.
        add("An adult Heathen (14 or more) gets no lessons: the lesson's age test leaves out everyone 14 or older.",
            gm.CODE, True)
        add("The owner (in play): Heathens, child Heathens most of all, sometimes gain Devotion at random, and "
            "village children sometimes gain in all six skills, seen around the Nursery School's completion, a "
            "Retired Heathen Chief's conversion or repeated Earthquakes.", gm.OWNER, True)
    else:
        add("Why children gain skills (the code's answer):")
        add(f"While every skill of a child is below a whole 1 they all count as tied and the tie goes to the last, "
            f"{last}, so once {last} is above 0 (a spread age unit gives it a fifth) {last} gets the whole lessons, "
            "unless the skill drawn at the child's first lesson reaches a whole 1 first. Emulated with the game's "
            f"code (400 children from 0, a 500 teacher): {last} became the trained skill for 398, 385 and 357 of "
            "them on Fast, Normal and Slow.", gm.CODE, True)
        add(gm.patch_words(village, fix, "a tie goes to any of the tied skills, each equally likely, so a child from 0 "
                                         "is trained in each skill about 1 in 5 times (emulated, 400 children: "
                                         "Building 90, 80 and 87 of them on Fast, Normal and Slow)"), gm.CODE, True)
        add("Children gain in all five skills at once: on the spread age units (half of them, one roll for every "
            "child together) each child gets a fifth of the lesson in every skill whose whole number is below "
            "50.", gm.CODE, True)
        add("The Nursery School's completion is not a skill gain: it only makes the villagers celebrate; it is "
            "the first teacher who starts the lessons, at the same drop.", gm.CODE, True)
    return out
