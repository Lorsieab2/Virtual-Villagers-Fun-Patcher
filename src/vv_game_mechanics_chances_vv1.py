"""Game Mechanics, A New Home (VV1): every random roll that changes play, with its exact odds
(src/vv_game_mechanics_chances.py explains the table; tests/test_game_mechanics_chances.py checks it against the exe).

Addresses are the stock exe's (inputs\\vv1-stock-copy).  The call paths into each routine from the game's frame loop
were traced in the coordinator's research (mech_vv1 spec, "Reachability"): the village update 0x423390 (mushrooms),
the world tick 0x42E900 (each villager's age unit) and its sickness roll 0x42E590.
"""
from __future__ import annotations

from vv_game_mechanics_chances import AGE_UNIT, BIRTHS, DRAWS, Check, Roll, at_most, below, chance, times

_MULTI = below(100, 7)                     # a multiple birth (0x43BC41)
_TRIPLE = below(100, 25)                   # of those, triplets (0x43BC7F)
_MALE = at_most(100, 49)                   # the sex roll (0x43C5F3): 49 or less is a boy (+0x350 = 1)


def _conceive(parenting: int, fertility: int) -> str:
    """rand(300) + 50 - 50 x Fertility <= Parenting (0x43DC66)."""
    return chance(sum(1 for v in range(DRAWS) if v % 300 + 50 - 50 * fertility <= parenting))

ROLLS = (
    Roll("A mushroom appears: checked every 2 real-life seconds at any speed while no mushroom is out, {0} each time "
         "(a roll of 0 to 119 above 117).",
         (Check(0x423516, 120, 0x75, "jle", take=False), Check(0x4236C9, 100, 5, "jge", take=False)),
         ("It is a red mushroom {1} of the time (a roll of 0 to 99 below 5), otherwise brown.",)),
    Roll("Falling sick: checked " + AGE_UNIT + " for each villager of 14 or older who is not sick.",
         (Check(0x42E5E8, 10000, 2, "jg", take=False), Check(0x42E604, 4800, 3, "jg", take=False),
          Check(0x42E604, 2400, 3, "jg", take=False, push=0x42E61B), Check(0x42E648, 1000, 14, "jle"),
          Check(0x42EE5F, 100, 0x32, "jl", take=False)),
         ("Medicine level 3: {0}.", "Medicine level 2: {1}.", "Medicine level 1: {2}.",
          "Elderly villagers roll again when that fails: {3} more.",
          "On Easy the roll is made only {4} of age units (0x42EE5F).")),
    Roll("Eating: " + AGE_UNIT + ", each villager eats 2 food; with 200 food or less they eat only {0} of the time, "
         "and one who does not eat loses 1 health instead (0x42EC94). The Golden Child is passed over: he never eats.",
         (Check(0x42ECA7, 100, 0x32, "jl"), Check(0x42ECF4, 100, 0x4B, "jg", take=False)),
         ("Eating 2 more: with more than 2,000 food on Medium, and at any amount on Hard, each villager eats 2 more "
          "{1} of the time; never on Easy.",)),
    Roll("Starving: " + AGE_UNIT + ", with no food left each villager loses 1 health {0} of the time, and every age "
         "unit on Hard (0x42ED0C).",
         (Check(0x42ED1C, 100, 0x4B, "jle"),)),
    Roll("A sick villager's health: " + AGE_UNIT + ", a sick villager loses 1 health {0} of the time while above 20 "
         "health, and only " + chance(times(at_most(100, 70), at_most(100, 30))) + " of age units at 20 or less. "
         "Sickness never ends by itself.",
         (Check(0x42ED77, 100, 0x46, "jg", take=False), Check(0x42ED93, 100, 0x1E, "jg", take=False))),
    Roll("Regaining health: " + AGE_UNIT + ", a villager who is not sick, while there is food, regains 1 health {0} "
         "of the time, and every age unit on Easy; an elderly villager (42 years plus 8 for each Medicine level) only "
         "{1} of those (0x42EDCB).",
         (Check(0x42EDE3, 100, 0x32, "jl"), Check(0x42EE1E, 100, 0x14, "jge", take=False))),
    Roll("The old-age death roll: on each birthday (every 20 age units: 1 real-life hour on Fast, 2 on Normal, 3 real-life hours 20 "
         "minutes on Slow) past 47, 55, 63 or 71 years (Medicine 0, 1, 2 or 3) a villager dies with a chance of 10% "
         "for each year past it (a roll of 0 to 99 under 10 x the years over): " + chance(below(100, 10))
         + " one year over, " + chance(below(100, 50)) + " five years over, 100% from ten years over (0x42EE7E).",
         (Check(0x42EEBC, 100),),
         ("The birthday roll follows the hidden processed age, which the game steps up one age unit at a time to "
          "the age shown -- every step in the same update after time away, so each birthday passed while away gets "
          "its roll. The Golden Child stays 5 and never reaches it.",)),
    Roll("Conception (dropping one villager on another, or two embracing on their own): with less than 400 food the "
         "pair refuses {0} of the time; then the villager who started it must pass the Parenting skill test, and a "
         "roll of 0 to 299, plus 50, less 50 x the Fertility level, must be at or under that villager's Parenting "
         "(0x43DC61): at Parenting 100, " + _conceive(100, 1) + ", " + _conceive(100, 2) + " or " + _conceive(100, 3)
         + " at Fertility 1, 2 or 3; the partner's skills do not matter.",
         (Check(0x43DBCC, 100, 0x19, "jle", take=False), Check(0x43DC66, 300)),
         ("The tutorial's first embrace skips the food refusal and the roll.",
          "No pregnancy starts at 90 people or more (babies on the way counted), or without room in the huts: 15 people "
          "or more need hut 1, 25 hut 2, 50 hut 3 (0x43A1A0)."),
         group=BIRTHS),
    Roll("How many babies: a pregnancy brings one baby unless Fertility is at level 3 or the strange-fish puzzle (The "
         "Magic Fish of Fertility) is solved; with either, a multiple birth comes {0} of the time, and with both, "
         "{1} of those are triplets (0x43BC28).",
         (Check(0x43BC41, 100, 7, "jge", take=False), Check(0x43BC7F, 100, 0x19, "jge", take=False)),
         ("So with one of the two: " + chance(_MULTI) + " twins; with both: "
          + chance(times(_MULTI, DRAWS - _TRIPLE)) + " twins and " + chance(times(_MULTI, _TRIPLE)) + " triplets.",
          "The babies are born on the 41st age unit after conception (2 villager years and 1 age unit): 2 real-life "
          "hours 3 minutes, 4 real-life hours 6 minutes or 6 real-life hours 50 minutes of play on Fast, Normal or Slow (0x42EF27)."),
         group=BIRTHS),
    Roll("Boy or girl: each baby is a boy {0} of the time and a girl " + chance(DRAWS - _MALE) + " (0x43C5F3).",
         (Check(0x43C5F3, 100, 0x31, "jg", take=False),),
         ("With 6 or fewer villagers a baby's sex is not rolled when the village is lopsided: when one sex has more and "
          "the other has 2 or fewer, the baby is of the sex that has more (0x42EF9F -> 0x42E660); otherwise it is "
          "rolled as above.",),
         group=BIRTHS),
)
