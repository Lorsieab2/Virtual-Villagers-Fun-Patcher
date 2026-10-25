"""Game Mechanics, The Tree of Life (VV4): every random roll that changes play, with its exact odds
(src/vv_game_mechanics_chances.py explains the table; tests/test_game_mechanics_chances.py checks it against the exe).

Addresses are the stock exe's (inputs/vv4-stock-copy).  rand(n) is 0x4036D0 (rand() % n).  The life tick 0x468430
(each villager's age unit: eating, starving, sickness, health, old age, births) has the same design as New Believers'
0x472C90, without Faith: its sickness roll 0x45E930, the pregnancy writer (litter roll 0x45E893), the villager set-up
(sex 0x465D00), the embrace 0x460C60 and its conception 0x460E52 (the second embrace path 0x465035 rolls the same),
the skill check 0x462A80.  Tech ids (0x41E1C0 on 0x4D6F5C): 1 Medicine, 2 Learning.  Sex (record +0x1B90): 0 male,
1 female.  Difficulty [manager +0x170F4]: 0 Easy, 1 Medium, 2 Hard.  Food: the global 0x4D6DD0.  The Fire Pit:
0x4D867C (0x432600).
"""
from __future__ import annotations

from vv_game_mechanics_chances import AGE_UNIT, BIRTHS, DRAWS, Check, Roll, at_most, below, chance, times


def _not(count: int) -> int:
    return DRAWS - count


def _conceive(parenting: int, medicine: int) -> str:
    """rand(300) + 50 - 50 x Medicine <= Parenting (0x460E59)."""
    return chance(sum(1 for v in range(DRAWS) if v % 300 + 50 - 50 * medicine <= parenting))


_MULTI = below(100, 7)                     # a multiple birth at Medicine 3 (0x45E893)
_TRIPLE = below(100, 25)                   # of those, triplets (0x45E8B3)
_TWINS = times(_MULTI, _not(_TRIPLE))
_TRIPLETS = times(_MULTI, _TRIPLE)
_MALE = at_most(100, 49)                   # the sex roll (0x465D0A): 49 or less is a boy
_EASY = _not(below(100, 50))

ROLLS = (
    Roll("Eating: " + AGE_UNIT + ", each villager eats 2 food; with 500 food or less they eat only {0} of the time, "
         "and one who does not eat loses 1 health {1} of the time.",
         (Check(0x46849E, 100, 0x32, "jl"), Check(0x4684AD, 100, 0x1E, "jge", take=False),
          Check(0x4684FE, 100, 0x4B, "jg", take=False)),
         ("Eating 2 more: on Medium with 8,000 food or more, and on Hard at any amount, each villager eats 2 more {2} "
          "of the time; never on Easy.",)),
    Roll("Starving: " + AGE_UNIT + ", with no food left each villager loses 1 health {0} of the time.",
         (Check(0x468526, 100, 0x4B, "jle"), Check(0x4685A4, 100, 0x1E, "jg", take=False)),
         ("On Hard, and for a villager whose hidden number is a multiple of 6, the loss comes every age unit.",
          "After that loss, a villager at 20 health or less whose hidden number is odd (and not a multiple of 6) "
          "regains 1 health {1} of the time.")),
    Roll("A sick villager's health: " + AGE_UNIT + ", a sick villager loses 1 health {0} of the time while above 20 "
         "health, and only " + chance(times(at_most(100, 60), at_most(100, 30))) + " of age units at 20 or less. "
         "Sickness never ends by itself.",
         (Check(0x4685D7, 100, 0x3C, "jg", take=False), Check(0x4685EC, 100, 0x1E, "jg", take=False))),
    Roll("Regaining health: " + AGE_UNIT + ", a villager who is not sick, while there is food, passes the health check "
         "{0} of the time; failing that, it passes on Easy, at Medicine level 3, and with the Fire Pit burning on a "
         "second roll of {1}.",
         (Check(0x46862A, 100, 0x32, "jl"), Check(0x468647, 100, 0x32, "jge", take=False),
          Check(0x468680, 100, 0x14, "jge", take=False)),
         ("So the check passes " + chance(below(100, 50)) + " of age units on Medium or Hard, "
          + chance(below(100, 50) + times(_not(below(100, 50)), below(100, 50))) + " with the Fire Pit burning, and "
          "every one on Easy or at Medicine 3.",
          "A pass gives +1 health (up to 100); an old villager (50, 58 or 66 years at Medicine 1, 2 or 3) gets it only "
          "{2} of the passes.")),
    Roll("Falling sick: " + AGE_UNIT + ", each villager who is not yet sick rolls; the chance depends on Medicine.",
         (Check(0x45E9AF, 1440, 3, "jle"), Check(0x45E996, 2460, 3, "jg", take=False),
          Check(0x45E97D, 5400, 2, "jg", take=False), Check(0x45E9D0, 1000, 0x0E, "jle"),
          Check(0x4686BB, 100, 0x32, "jl"), Check(0x45E943, 100, 0x32, "jl")),
         ("Medicine 1: {0}; Medicine 2: {1}; Medicine 3: {2}.",
          "An old villager (50, 58 or 66 years at Medicine 1, 2 or 3) who escapes that roll has a second one: {3} more.",
          "On Easy the roll is made only " + chance(times(_EASY, _EASY)) + " of age units (two rolls of 0 to 99 at 50 "
          "or more must both come up), so about a quarter of these chances.")),
    Roll("The old-age death roll: on each birthday (every 20 age units: 1 real-life hour on Fast, 2 on Normal, 3 real-life hours 20 "
         "minutes on Slow) past 55, 63 or 71 years (Medicine 1, 2 or 3) a villager dies with a chance of 10% for each "
         "year past it (a roll of 0 to 99 under 10 x the years over): " + chance(below(100, 10)) + " one year over, "
         + chance(below(100, 50)) + " five years over, 100% from ten years over (65, 73 or 81).",
         (Check(0x46873F, 100),),
         ("The birthday roll follows the hidden processed age, which the game steps up one age unit at a time to "
          "the age shown -- every step in the same update after time away, so each birthday passed while away gets its "
          "roll.",)),
    Roll("The skill check, made whenever a villager finishes a task (a harvest, a building action, a cure, a research "
         "session, an embrace): a roll of 0 to 99 at or under the skill + 33 succeeds, so the chance is the skill + "
         "34% (" + chance(below(100, 34)) + " at skill 0, " + chance(below(100, 84)) + " at 50, 100% from 66).",
         (Check(0x462B15, 100, None, "jle"),),
         ("A villager who likes learning adds 66 instead of 33 (" + chance(below(100, 67)) + " at skill 0); one who "
          "dislikes it adds 16 (" + chance(below(100, 17)) + " at skill 0). Learning level 2 adds 15 more, level 3 "
          "adds 30.",),
         feature="vv4_learning_never_fails",
         patched="every Learning skill check succeeds."),
    Roll("Conception (dropping one villager on another, or two embracing on their own): the pair must be a man and a "
         "woman, both 18 or older, alive, not sick, neither pregnant or nursing, and the Love Shack built; with 250 "
         "food or less they refuse {0} of the time; then the villager you dropped must pass the Parenting skill "
         "check.",
         (Check(0x460CFF, 100, 0x41, "jle", take=False), Check(0x460E59, 300, None, "jg", take=False)),
         ("Then a roll of 0 to 299, plus 50, less 50 x the Medicine level, must be at or under that villager's "
          "Parenting: at Parenting 50, " + _conceive(50, 1) + ", " + _conceive(50, 2) + " or " + _conceive(50, 3)
          + " at Medicine 1, 2 or 3; at Parenting 100, " + _conceive(100, 1) + ", " + _conceive(100, 2) + " or "
          + _conceive(100, 3) + ".",
          "The village's very first conception is certain (the game's tip not yet shown skips the roll). A woman of "
          "50 or older never conceives (0x460E67)."),
         group=BIRTHS),
    Roll("How many babies: a pregnancy brings one baby, except at Medicine level 3: then a multiple birth comes {0} "
         "of the time, and of those {1} are triplets, so " + chance(_TWINS) + " twins and " + chance(_TRIPLETS)
         + " triplets.",
         (Check(0x45E893, 100, 7, "jge", take=False), Check(0x45E8B3, 100, 0x19, "jge", take=False)),
         ("The babies are born on the 41st age unit after conception (2 villager years and 1 age unit): 2 real-life "
          "hours 3 minutes, 4 real-life hours 6 minutes or 6 real-life hours 50 minutes of play on Fast, Normal or Slow (0x4687F2).",),
         group=BIRTHS),
    Roll("Boy or girl: each first baby of a pregnancy, and any villager the game makes without a sex given, is a boy "
         "{0} of the time and a girl " + chance(_not(_MALE)) + " (0x465D00).",
         (Check(0x465D0A, 100, 0x31, "jg", take=False),),
         ("With 6 or fewer villagers a baby's sex is not rolled when the living villagers are lopsided: when one sex "
          "has more and the other has 2 or fewer, the baby is of the sex that has more (0x468809, 0x468300); otherwise "
          "it is rolled as above.",
          "A twin or triplet is a copy of the first baby: the same sex, head and body; only its name is picked again."),
         group=BIRTHS),
)
