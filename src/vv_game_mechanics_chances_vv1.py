"""Game Mechanics, A New Home (VV1): every random roll that changes play, with its exact odds
(src/vv_game_mechanics_chances.py explains the table; tests/test_game_mechanics_chances.py checks it against the exe).

Addresses are the stock exe's (inputs\\vv1-stock-copy).  The call paths into each routine from the game's frame loop
were traced in the coordinator's research (mech_vv1 spec, "Reachability"): the village update 0x423390 (mushrooms),
the world tick 0x42E900 (each villager's age unit) and its sickness roll 0x42E590.
"""
from __future__ import annotations

from vv_game_mechanics_chances import AGE_UNIT, BIRTHS, Check, Roll

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
)
