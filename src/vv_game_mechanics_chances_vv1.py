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

ROLLS = (
    Roll("A mushroom appears: checked every 2 real-life seconds at any speed while no mushroom is out, {0} each time "
         "(a roll of 0 to 119 above 117).",
         (Check(0x423516, 120, 0x75, "jle", take=False), Check(0x4236C9, 100, 5, "jge", take=False)),
         ("It is a red mushroom {1} of the time (a roll of 0 to 99 below 5), otherwise brown.",)),
    Roll("Falling sick: checked " + AGE_UNIT + " for each villager of 14 or older who is not sick.",
         (Check(0x42E5E8, 10000, 2, "jg", take=False), Check(0x42E604, 4800, 3, "jg", take=False),
          Check(0x42E604, 2400, 3, "jg", take=False, push=0x42E61B), Check(0x42E648, 1000, 14, "jle")),
         ("Medicine level 3: {0}.", "Medicine level 2: {1}.", "Medicine level 1: {2}.",
          "Elderly villagers roll again when that fails: {3} more.")),
    Roll("How many babies: a pregnancy brings one baby unless Fertility is at level 3 or the strange-fish puzzle (The "
         "Magic Fish of Fertility) is solved; with either, a multiple birth comes {0} of the time, and with both, "
         "{1} of those are triplets (0x43BC28).",
         (Check(0x43BC41, 100, 7, "jge", take=False), Check(0x43BC7F, 100, 0x19, "jge", take=False)),
         ("So with one of the two: " + chance(_MULTI) + " twins; with both: "
          + chance(times(_MULTI, DRAWS - _TRIPLE)) + " twins and " + chance(times(_MULTI, _TRIPLE)) + " triplets.",
          "The babies are born 40 age units (2 villager years) after conception: 2, 4 or 6 real-life hours 40 minutes "
          "of play on Fast, Normal or Slow (0x42EF27)."),
         group=BIRTHS),
    Roll("Boy or girl: each baby is a boy {0} of the time and a girl " + chance(DRAWS - _MALE) + " (0x43C5F3).",
         (Check(0x43C5F3, 100, 0x31, "jg", take=False),),
         ("With 6 or fewer villagers a baby's sex is not rolled when the village is lopsided: when one sex has more and "
          "the other has 2 or fewer, the baby is of the sex that has more (0x42EF9F -> 0x42E660); otherwise it is "
          "rolled as above.",),
         group=BIRTHS),
)
