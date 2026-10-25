"""Game Mechanics, New Believers (VV5): every random roll that changes play, with its exact odds
(src/vv_game_mechanics_chances.py explains the table; tests/test_game_mechanics_chances.py checks it against the exe).

Addresses are the stock exe's (SHA-256 92946781...C65D, 991,232 bytes).  rand(n) is 0x403660 (rand() % n).  The call
paths from the main scene's update 0x442350 (proven to run by the owner's saves: its timers move and its counters are
the only writers of the save's statistics, the coordinator's mech_vv5 spec):
  the life tick 0x472C90 (each believer's age unit: Faith 0x468040, Divine Energy, eating, starving, sickness, health,
  old age, births; Heathens skipped at 0x472CB7), its sickness roll 0x465F50, the pregnancy writer 0x465E00, the
  villager set-up 0x4681F0 (sex 0x46F5E0, starting Faith 0x468508), the embrace 0x4689A0 and its conception 0x468B7B,
  the skill check 0x46B270.
Tech ids (0x423600 on 0x51D5CC): 0 Science, 1 Medicine, 2 Learning, 3 Construction, 4 Food Mastery, 5 Spirituality.
Skills (record +0x1C5C): Farming, Parenting, Healing, Research, Building, Devotion.  Sex (record +0x1B90): 0 male, 1
female.  Difficulty [manager +0x17D54]: 0 Easy, 1 Medium, 2 Hard.  Food: the global 0x51D34C.
"""
from __future__ import annotations

from vv_game_mechanics_chances import AGE_UNIT, BIRTHS, DRAWS, Check, Roll, at_most, below, chance, times


def _not(count: int) -> int:
    return DRAWS - count


def _sick(n: int, k: int) -> str:
    return chance(at_most(n, k))


def _conceive(parenting: int, medicine: int) -> str:
    """rand(300) + 50 - 50 x Medicine <= Parenting (0x468BB6)."""
    return chance(sum(1 for v in range(DRAWS) if v % 300 + 50 - 50 * medicine <= parenting))


_MULTI = below(100, 7)                     # a multiple birth at Medicine 3 (0x465EE3)
_TRIPLE = below(100, 25)                   # of those, triplets (0x465F03)
_TWINS = times(_MULTI, _not(_TRIPLE))
_TRIPLETS = times(_MULTI, _TRIPLE)
_MALE = at_most(100, 49)                   # the sex roll (0x46F5EA): 49 or less is a boy
_EASY = _not(below(100, 50))

ROLLS = (
    # -- Each believer's age unit (the life tick 0x472C90; Heathens get none of these) -------------------------
    Roll("Eating: " + AGE_UNIT + ", each believer eats 2 food; with 500 food or less they eat only {0} of the time, "
         "and one who does not eat loses 1 health {1} of the time.",
         (Check(0x472D74, 100, 0x32, "jl"), Check(0x472D83, 100, 0x1E, "jge", take=False),
          Check(0x472DE2, 100, 0x4B, "jg", take=False)),
         ("Eating 2 more: on Medium with 8,000 food or more, and on Hard at any amount, each believer eats 2 more "
          "{2} of the time (and gains 1 more Divine Energy); never on Easy.",)),
    Roll("Starving: " + AGE_UNIT + ", with no food left each believer loses 1 health {0} of the time.",
         (Check(0x472E0A, 100, 0x4B, "jle"), Check(0x472E88, 100, 0x1E, "jg", take=False)),
         ("On Hard, and for a believer whose hidden name number is a multiple of 6, the loss comes every age unit.",
          "After that loss, a believer at 20 health or less whose hidden number is odd (and not a multiple of 6) "
          "regains 1 health {1} of the time.")),
    Roll("A sick believer's health: " + AGE_UNIT + ", a sick believer loses 1 health {0} of the time while above 20 "
         "health, and only " + chance(times(at_most(100, 60), at_most(100, 30))) + " of age units at 20 or less. "
         "Sickness never ends by itself.",
         (Check(0x472EA8, 100, 0x3C, "jg", take=False), Check(0x472EBD, 100, 0x1E, "jg", take=False))),
    Roll("Regaining health: " + AGE_UNIT + ", a believer who is not sick, while there is food, passes the health check "
         "{0} of the time; failing that, it passes on Easy, at Medicine level 3, and with the fire burning on a second "
         "roll of {1}.",
         (Check(0x472EFB, 100, 0x32, "jl"), Check(0x472F18, 100, 0x32, "jge", take=False),
          Check(0x472F51, 100, 0x14, "jge", take=False)),
         ("So the check passes " + chance(below(100, 50)) + " of age units on Medium or Hard, "
          + chance(below(100, 50) + times(_not(below(100, 50)), below(100, 50))) + " with the fire burning, and every "
          "one on Easy or at Medicine 3.",
          "A pass gives +1 health (up to 100); an old believer (50, 58 or 66 years at Medicine 1, 2 or 3) gets it only "
          "{2} of the passes.")),
    Roll("Falling sick: " + AGE_UNIT + ", each believer who is not yet sick rolls; the chance depends on Medicine.",
         (Check(0x465FCF, 1440, 3, "jle"), Check(0x465FB6, 2460, 3, "jg", take=False),
          Check(0x465F9D, 5400, 2, "jg", take=False), Check(0x465FF0, 1000, 0x0E, "jle"),
          Check(0x472F8C, 100, 0x32, "jl"), Check(0x465F63, 100, 0x32, "jl")),
         ("Medicine 1: {0}; Medicine 2: {1}; Medicine 3: {2}.",
          "An old believer (50, 58 or 66 years at Medicine 1, 2 or 3) who escapes that roll has a second one: {3} more.",
          "On Easy the roll is made only " + chance(times(_EASY, _EASY)) + " of age units (two rolls of 0 to 99 at 50 "
          "or more must both come up), so about a quarter of these chances.")),
    Roll("Old age: on each birthday (every 20 age units: 1 real-life hour on Fast, 2 on Normal, 3 real-life hours 20 "
         "minutes on Slow) past 55, 63 or 71 years (Medicine 1, 2 or 3) a believer dies with a chance of 10% for each year past "
         "it (a roll of 0 to 99 under 10 x the years over): " + chance(below(100, 10)) + " one year over, "
         + chance(below(100, 50)) + " five years over, 100% from ten years over (65, 73 or 81).",
         (Check(0x47300A, 100),),
         ("The roll follows the hidden processed age, which catches up with the age shown a step at a time after time "
          "away. Heathens never age.",)),
    # -- Work ------------------------------------------------------------------------------------------------
    Roll("The skill check, made whenever a villager finishes a task (a harvest, a building action, a cure, a research "
         "session, an embrace, Honoring): a roll of 0 to 99 at or under the skill + 33 succeeds, so the chance is the "
         "skill + 34% (" + chance(below(100, 34)) + " at skill 0, " + chance(below(100, 84)) + " at 50, 100% from 66).",
         (Check(0x46B305, 100, None, "jle"),),
         ("A villager who likes learning adds 66 instead of 33 (" + chance(below(100, 67)) + " at skill 0); one who "
          "dislikes it adds 16 (" + chance(below(100, 17)) + " at skill 0). Learning level 2 adds 15 more, level 3 "
          "adds 30.",),
         feature="vv5_learning_never_fails",
         patched="every Learning skill check succeeds."),
    # -- Births and gender -----------------------------------------------------------------------------------
    Roll("Conception (dropping one villager on another, or two embracing on their own): the pair must be a man and a "
         "woman, both 18 or older, alive, not sick, neither pregnant or nursing, and the love shack built; with 250 "
         "food or less they refuse (\"They're too hungry to think about this!\") {0} of the time; then the villager "
         "you dropped must pass the Parenting skill check.",
         (Check(0x468A82, 100, 0x41, "jle", take=False), Check(0x468BB6, 300, None, "jg", take=False)),
         ("Then a roll of 0 to 299, plus 50, less 50 x the Medicine level, must be at or under that villager's "
          "Parenting: at Parenting 50, " + _conceive(50, 1) + ", " + _conceive(50, 2) + " or " + _conceive(50, 3)
          + " at Medicine 1, 2 or 3; at Parenting 100, " + _conceive(100, 1) + ", " + _conceive(100, 2) + " or "
          + _conceive(100, 3) + ".",
          "The village's very first conception is certain (the game's tip 40 not yet shown skips the food refusal "
          "and the roll). A woman of 50 or older never conceives (0x468BC9)."),
         group=BIRTHS),
    Roll("How many babies: a pregnancy brings one baby, except at Medicine level 3: then a multiple birth comes {0} "
         "of the time, and of those {1} are triplets, so " + chance(_TWINS) + " twins and " + chance(_TRIPLETS)
         + " triplets (0x465ED7).",
         (Check(0x465EE3, 100, 7, "jge", take=False), Check(0x465F03, 100, 0x19, "jge", take=False)),
         ("The babies are born 40 age units (2 villager years) after conception: 2, 4 or 6 hours 40 minutes of "
          "real-life play on Fast, Normal or Slow (0x4730BA).",
          "In a game written by the patcher, twins or triplets are kept only while 2 or 3 villager records are free "
          "(Heathens, bodies and babies still owed counted), and a birth waits, the pregnancy kept, until the whole "
          "litter fits (the patcher's safety fixes at 0x65F10, 0x65F23, 0x730AF); the stock game makes the litter "
          "anyway, and a baby that finds no free record of the 150 is lost."),
         group=BIRTHS),
    Roll("Boy or girl: each first baby of a pregnancy, and any villager the game makes without a sex given, is a boy "
         "{0} of the time and a girl " + chance(_not(_MALE)) + " (0x46F5E0).",
         (Check(0x46F5EA, 100, 0x31, "jg", take=False),),
         ("With 6 or fewer believers a baby's sex is not rolled when the living villagers (Heathens included) are "
          "lopsided: when one sex has more and the other has 2 or fewer, the baby is of the sex that has more "
          "(0x4730D8, 0x472B80); otherwise it is rolled as above.",
          "A twin or triplet is a copy of the first baby (0x4687F0, 0x4688DC): the same sex, head, body and Faith; "
          "only its name is picked again when it came out the same."),
         group=BIRTHS),
)
