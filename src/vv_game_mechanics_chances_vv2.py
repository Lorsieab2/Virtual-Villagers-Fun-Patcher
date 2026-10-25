"""Game Mechanics, The Lost Children (VV2): every random roll that changes play, with its exact odds
(src/vv_game_mechanics_chances.py explains the table; tests/test_game_mechanics_chances.py checks it against the exe).

Addresses are the stock exe's (research\\stock-executables, 724,992 bytes).  rand(n) is 0x4031A0.  The game's own call
paths into each routine were traced in the coordinator's research (mech_vv2 spec, "Reach", R0-R3) and in
docs/hidden-gates-all-five-games.md (VV2, REACHED):
  * the 2-second block of the village scene's frame (0x42EB7C): the world tick 0x43B690 (each villager's age unit, its
    sickness roll 0x43B2B0, sex balancing 0x43B3A0, births) and the item spawn 0x415FE0 -> 0x415490;
  * the villager updater 0x464CD0 -> AI decision 0x461850 -> job chooser 0x449C60 -> work dispatcher 0x45FBF0, the
    skill roll 0x44E170 (queue op 6), the completion callbacks 0x461B10 (op 17, table 0x4642F4) and the embrace
    0x44F610 (op 12);
  * catch-up: 0x43B4D0 four times for each counted age unit, simulating queues in 0x464680;
  * villager creation 0x44C600 (sex at 0x44CB7E-0x44CBA1), its wrappers 0x44F5C0 (births) and 0x44F580 (event
    arrivals), the litter copy 0x44CEC0 (sex copied at 0x44CFFD), the new village 0x424C80.
Skill offsets (record stride 0xE48C): +0x7E4 Parenting, +0x7E8 Building, +0x7EC Farming, +0x7F0 Healing, +0x7F4
Research.  Tech levels: Culture +0x2EA74, Science +0x2EA7C, Engineering +0x2EA84, Medicine +0x2EA8C, Exploration
+0x2EA94, Farming +0x2EA9C.  Sex +0x538: 1 male, 2 female.

Not listed, as they decide nothing the save or the player's village keeps (cosmetic): where a villager walks, which
spot an item lies on, how long a step or animation lasts, speech, facing, the dance and play routines (about 1,050 roll
sites, mech_vv2 rolls_index.tsv), and the random sexes 0x424EDA gives the empty villager records when a new village
is set up (no villager uses them: every founder's sex is set when it is created).  A new villager's looks (head and
body, 0x44CBAD) belong to the Genetics group.  Island events and the Gong of Wonder are in their own groups.
"""
from __future__ import annotations

import vv_game_mechanics_chances as ch
from vv_game_mechanics_chances import AGE_UNIT, BIRTHS, Check, Roll

_c = ch.chance
_b = ch.below
_m = ch.at_most
_x = ch.times
N = ch.DRAWS


def _not(count: int) -> int:
    return N - count


def _or(a: int, b: int) -> int:
    """A first roll's count, or failing it a second one's (independent)."""
    return round(a + (N - a) * b / N)


# The farming level 3 choice (0x45FC36-0x45FD18).
_F80, _F40, _C75, _C25 = _b(100, 80), _b(100, 40), _b(100, 75), _b(100, 25)
_FISH_EMPTY = _or(_F80, _F40)                       # no ripe crops: two fishing rolls
# The farming level 2 choice (0x45FD1B-0x45FDC6).
_L2_FISH = _m(100, 80)
_L2_COCONUT_RIPE = _not(_m(100, 50))                # crops ripe, dam built: only the first coconut roll
_L2_COCONUT_EMPTY = _or(_not(_m(100, 50)), _b(100, 50))
# Sickness (0x43B2B0): m = 1 while the fire burns, else 2.
_SICK = {(1, True): _m(1440, 3), (1, False): _m(1440, 6), (2, True): _m(2460, 3), (2, False): _m(2460, 6),
         (3, True): _m(5400, 2), (3, False): _m(5400, 4)}
_ELDER = _m(1000, 14)
# Twins and triplets (0x44BA6A-0x44BAB6), Medicine 3 only.
_T7, _T25 = _b(100, 7), _b(100, 25)


def _conceive(parenting: int, medicine: int) -> str:
    return _c(_m(300, parenting - 50 + 50 * medicine)) if parenting - 50 + 50 * medicine >= 0 else "0%"


ROLLS = (
    # ---------------------------------------------------------------- Mushrooms and collectibles
    Roll("An item (a mushroom or a collectible) appears: checked every 2 real-life seconds while none lies on the "
         "ground, at any speed and also while the game is paused (the check skips only a speed of exactly 999, and a "
         "pause stores the speed plus 999, 0x42EC87); it appears when a roll of 0 to 99 is below Exploration level "
         "+ 4. It lies 75 real-life seconds.",
         (Check(0x415FED, 100, None, "jge"),),
         (f"Exploration level 1: {_c(_b(100, 5))} each check; level 2: {_c(_b(100, 6))}; level 3: {_c(_b(100, 7))}.",)),
    Roll("Mushroom or collectible: a roll of 0 to 99 below 65 - 15 x Exploration level makes it a mushroom, otherwise "
         "a collectible.",
         (Check(0x4154B8, 100, None, "jge"), Check(0x415935, 100, 0xA, "jge", take=False)),
         (f"Exploration level 1: a mushroom {_c(_b(100, 50))}; level 2: {_c(_b(100, 35))}; level 3: "
          f"{_c(_b(100, 20))}.",
          "A mushroom is the special one (35 food instead of 6) {1} of the time (a roll of 0 to 99 below 10)."),
         feature="vv2_super_secret_golden_mushroom",
         patched="1 in 1,000,000 of the mushrooms that appear is a Golden Mushroom instead, worth 100 food (two "
                 "draws of the game's random-number routine, each a multiple of 1,000 out of 0 to 31,999)."),
    Roll("A collectible's collection and rarity: the collection is drawn from 4 with a roll of 0 to 3 until one is "
         "open, so each open collection is equally likely (Butterflies and Shells always; Beetles once the Overgrown "
         "Gong Piece is uncovered, flag 0x2E7E0; Pebbles once the Dam is built). Then a roll of 0 to 99 below 2 x "
         "Exploration + 2 makes it rare, below 2 x Exploration + 14 uncommon, otherwise common.",
         (Check(0x415D99, 100),),
         (f"Exploration level 1: rare {_c(_b(100, 4))}, uncommon {_c(_b(100, 16) - _b(100, 4))}, common "
          f"{_c(_not(_b(100, 16)))}.",
          f"Exploration level 2: rare {_c(_b(100, 6))}, uncommon {_c(_b(100, 18) - _b(100, 6))}, common "
          f"{_c(_not(_b(100, 18)))}.",
          f"Exploration level 3: rare {_c(_b(100, 8))}, uncommon {_c(_b(100, 20) - _b(100, 8))}, common "
          f"{_c(_not(_b(100, 20)))}.")),
    # ---------------------------------------------------------------- Food and health, each age unit
    Roll("Eating at 150 food or less: rolled " + AGE_UNIT + " for each villager who eats; the villager skips the "
         "meal {0} of the time (a roll of 0 to 99 of 50 or more), and a villager who skips loses 1 health {1} of "
         "those times. Above 150 food every meal is eaten (2 food).",
         (Check(0x43BAC5, 100, 0x32, "jl", take=False), Check(0x43BAD4, 100, 0x1E, "jge", take=False))),
    Roll("Eating 2 more food: rolled " + AGE_UNIT + " for each villager who eats, {0} of the time (a roll of 0 to "
         "99 of 75 or less), on Medium only while food is above 4,000, on Hard at any food level; never on Easy.",
         (Check(0x43BB21, 100, 0x4B, "jg", take=False),)),
    Roll("Starving at 0 food: rolled " + AGE_UNIT + " for each villager; the villager loses 1 health {0} of the "
         "time (a roll of 0 to 99 of 75 or less), every time on Hard, and every time for a villager whose hidden "
         "number is a multiple of 6.",
         (Check(0x43BB4D, 100, 0x4B, "jle"), Check(0x43BBC0, 100, 0x1E, "jg", take=False)),
         ("After such a loss, a villager left at 20 health or less whose hidden number is odd and not a multiple of 3 "
          "regains the 1 health {1} of the time (a roll of 0 to 99 of 30 or less). The hidden numbers are in Hidden "
          "villager stats.",)),
    Roll("Sickness costs health: rolled " + AGE_UNIT + " for each sick villager; above 20 health it loses 1 health "
         "{0} of the time (a roll of 0 to 99 of 60 or less).",
         (Check(0x43BC10, 100, 0x3C, "jg", take=False), Check(0x43BC2C, 100, 0x1E, "jg", take=False)),
         (f"At 20 health or less a second roll (0 to 99, 30 or less, {{1}}) must also pass: "
          f"{_c(_x(_m(100, 60), _m(100, 30)))} of age units. Sickness never ends by itself.",)),
    Roll("Regaining health: rolled " + AGE_UNIT + " for each villager who is not sick while there is food; a roll "
         "of 0 to 99 below 50 gives +1 health ({0}). On Easy every such age unit gives +1.",
         (Check(0x43BC84, 100, 0x32, "jl"), Check(0x43BC9D, 100, 0x32, "jge", take=False),
          Check(0x43BCEB, 100, 0x14, "jge", take=False)),
         (f"On Medium or Hard, when the first roll fails a second roll (0 to 99 below 50) gives it while the fire "
          f"burns: {_c(_or(_b(100, 50), _b(100, 50)))} of age units with the fire lit.",
          "Once the Hospital is built (flag 0x2E780) every such age unit gives +1, on every difficulty.",
          "An elderly villager (50, 58 or 66 years and older at Medicine level 1, 2 or 3) gets the +1 only when a "
          "further roll (0 to 99 below 20) passes: {2} of the chance above.")),
    Roll("Falling sick: rolled " + AGE_UNIT + " for each villager who is not sick, at any age; the fire changes the "
         "odds (m = 1 while it burns, 2 while it is out): a roll of 0 to 1,439 of 3m or less at Medicine level 1, of "
         "0 to 2,459 of 3m or less at level 2, of 0 to 5,399 of 2m or less at level 3.",
         (Check(0x43B343, 1440, None, "jg"), Check(0x43B322, 2460, None, "jg"), Check(0x43B301, 5400, None, "jg"),
          Check(0x43B385, 1000, 14, "jle"), Check(0x43BD2D, 100, 0x32, "jl", take=False)),
         (f"Medicine level 1: {_c(_SICK[1, True])} with the fire lit, {_c(_SICK[1, False])} with it out.",
          f"Medicine level 2: {_c(_SICK[2, True])} with the fire lit, {_c(_SICK[2, False])} with it out.",
          f"Medicine level 3: {_c(_SICK[3, True])} with the fire lit, {_c(_SICK[3, False])} with it out.",
          "An elderly villager (older than 50, 58 or 66 years at Medicine level 1, 2 or 3) who escapes that roll falls "
          "sick on a second roll (0 to 999, 14 or less) {3} of the time.",
          "On Easy the whole check is made only {4} of age units (a roll of 0 to 99 of 50 or more). The Hospital does "
          "not change these odds.")),
    Roll("Old age: rolled at each birthday (every 20 age units) of a villager past 55, 63 or 71 years (Medicine "
         "level 1, 2 or 3); the villager dies when a roll of 0 to 99 is below 10 x the years past that age.",
         (Check(0x43BDA5, 100),),
         (f"1 year past: {_c(_b(100, 10))}; 2: {_c(_b(100, 20))}; 5: {_c(_b(100, 50))}; 7: {_c(_b(100, 70))}; 10 "
          "or more: 100%.",)),
    # ---------------------------------------------------------------- Skills
    Roll("Every work step's skill roll (farming, building, healing, research, parenting): rolled once per step; it "
         "passes when a roll of 0 to 99 is at most the skill + 33 (+ 66 for a villager who likes learning, + 16 for "
         "one who dislikes it). A failed step ends the task with nothing gained; a failure at skill 0 sets the skill "
         "to 4.",
         (Check(0x44E1D0, 100, None, "jle"), Check(0x44E2F4, None, 0x19, "jg", take=False)),
         (f"Skill 0: {_c(_b(100, 34))} ({_c(_b(100, 67))} liking learning, {_c(_b(100, 17))} disliking it); skill "
          f"30: {_c(_b(100, 64))}; skill 66 or more: 100% ({_c(_b(100, 17 + 66))} at 66 disliking learning).",
          "A pass raises the skill by (100 - 2 x skill) / 10, rounded down (Building: / 7), doubled for a villager "
          "who likes learning and halved for one who dislikes it. Where that is 0 (from skill 46, Building 47), the "
          f"skill rises by 1 only when a roll of 0 to 99 is 25 or less ({_c(_m(100, 25))}) and a second roll of 0 to "
          f"99 is at least the skill: {_c(_x(_m(100, 25), N - _b(100, 46)))} at skill 46, "
          f"{_c(_x(_m(100, 25), N - _b(100, 90)))} at 90. Skills stop at 100."),
         feature="vv2_learning_never_fails",
         patched="every work step's skill roll passes; the skill gains are the game's own."),
    # ---------------------------------------------------------------- What villagers do
    Roll("An idle villager does nothing: each time an idle adult's next activity is chosen, it is \"Nothing\" {0} of "
         "the time (a roll of 0 to 99 of 65 or less).",
         (Check(0x46188E, 100, 0x41, "jle"), Check(0x461915, 100, 0x14, "jge", take=False)),
         ("A nursing mother takes one of her 6 mother activities (each equally likely) only {1} of the times her "
          "activity is chosen (a roll of 0 to 99 below 20), and otherwise does nothing; she never works.",)),
    Roll("Burying the dead: while an unburied body lies in the village, an adult goes to bury it {0} of the times "
         "its activity is chosen (a roll of 0 to 99 below 25).",
         (Check(0x46198C, 100, 0x19, "jl"), Check(0x4619A4, 100, 0x46, "jge", take=False)),
         (f"A villager with Healing 50 or more who misses that roll goes on a second roll (0 to 99 below 70, {{1}}): "
          f"{_c(_or(_b(100, 25), _b(100, 70)))} in all.",)),
    Roll("Choosing a job (each time an adult's work is chosen, 0x449C60): {0} of the time (a roll of 0 to 99 below 15) "
         "the chooser gives up unless the villager likes work; a villager who dislikes work also gives up {1} of the "
         "time (below 70).",
         (Check(0x449C6E, 100, 0xF, "jge", take=False), Check(0x449CA1, 100, 0x46, "jl"),
          Check(0x449CB4, 100, 0xF, "jle", take=False), Check(0x449D65, 100, 0x32, "jl"),
          Check(0x449DC5, 100, 0x55, "jg", take=False), Check(0x449E16, 100, None, "jge"), Check(0x449E38, 100)),
         ("Each of the five skills is weighed only on a roll of 0 to 99 above 15 ({2} each), and the highest weighed "
          "skill wins; Parenting is weighed 15 points lower than it is, and Healing is passed over {3} of the time by "
          "a villager who dislikes medicine.",
          "A checked skill preference (Villager Details) other than the winner replaces it {4} of the time (a roll of "
          "0 to 99 of 85 or less).",
          "The villager then takes the job only when the winning score is above 5 and a roll of 0 to 99 is below the "
          f"score + 40: a score of 20 takes it {_c(_b(100, 60))} of the time, 60 or more always.",
          f"When Parenting wins without being the checked preference the villager embraces only {_c(_not(_b(100, 75)))} "
          "of the time (a roll of 0 to 99 of 75 or more), otherwise nothing."),
         feature="vv2_birth_control",
         patched="a villager whose checked preference is not Parenting never chooses to embrace on their own (the "
                 "fallback roll is removed), and a villager pairing up on their own never takes a partner of 50 or "
                 "older."),
    Roll("Keeping a player-assigned job: each time the work of a villager who does not like work is chosen, it drops "
         "the assignment for that turn {0} of the time (a roll of 0 to 99 below 20).",
         (Check(0x461596, 100, 0x14, "jl"), Check(0x4615A9, 100, 0x28, "jge", take=False)),
         (f"When it keeps it, a second roll (0 to 99 below 40, {{1}}) drops it too while food is 4,000 or more or the "
          f"villager dislikes work: {_c(_or(_b(100, 20), _b(100, 40)))} in all then. A villager who likes work always "
          "keeps it. An assignment whose skill is below 6 is forgotten.",)),
    Roll("Which food a farmer gathers (each time a farmer's work is chosen), by the Farming technology level.",
         (Check(0x45FE00, 100, 0x32, "jg"), Check(0x45FD26, 100, 0x50, "jg", take=False),
          Check(0x45FD79, 100, 0x32, "jg"), Check(0x45FD98, 100, 0x32, "jl"), Check(0x45FC51, 100, 0x50, "jl"),
          Check(0x45FC60, 100, 0x28, "jge", take=False), Check(0x45FC9D, 100, 0x4B, "jl"),
          Check(0x45FCAC, 100, 0x19, "jge", take=False)),
         ("Level 1: while fish remain, fishing {0} of the time (a roll of 0 to 99 above 50), otherwise the crops if "
          "the Dam is built (fishing if it is not); with no fish left, the crops if the Dam is built, otherwise "
          "nothing.",
          f"Level 2: while the water is not fished out, fishing {{1}} (a roll of 0 to 99 of 80 or less); otherwise, "
          f"with more than 10 coconuts and no dislike of heights or coconuts, coconuts {_c(_L2_COCONUT_RIPE)} with "
          f"ripe crops and the Dam built, {_c(_L2_COCONUT_EMPTY)} with the field empty; otherwise the crops (Dam "
          "built).",
          f"Level 3: while the water is not fished out, fishing {_c(_FISH_EMPTY)} with the field empty (two rolls, "
          f"below 80 then below 40) and {{5}} with ripe crops; then, with 10 coconuts or more, coconuts "
          f"{_c(_or(_C75, _C25))} of the rest with the field empty (below 75 then below 25) and {_c(_C25)} with "
          "ripe crops; otherwise the crops (Dam built).")),
    Roll("Refusing a gathering trip: a villager who dislikes coconuts or heights refuses a coconut trip {0} of the "
         "time, and one who dislikes turnips or vegetables refuses a crops trip {1} of the time (a roll of 0 to 99 "
         "below 75). One who dislikes fish always refuses fishing.",
         (Check(0x456F94, 100, 0x4B, "jge", take=False), Check(0x459400, 100, 0x4B, "jge", take=False))),
    Roll("A builder's work (each time a builder's work is chosen): it first goes on with a project the player set "
         "{0} of the time (a roll of 0 to 99 above 20); otherwise the broken starting hut and the huts come first.",
         (Check(0x45FE87, 100, 0x14, "jle", take=False), Check(0x45FB4F, 100),
          Check(0x457284, 100, 0x32, "jle"), Check(0x457382, 100, 0x28, "jge", take=False)),
         (f"Examining a hut (Engineering level 3) finds work {_c(_b(100, 70))} of the time (a roll of 0 to 99 below "
          "70): a Building "
          "practice roll only, as huts never decay; otherwise \"This hut is still in good repair.\"",
          f"A builder who dislikes wood takes the short route to the wood {{2}} of the time (a roll of 0 to 99 of 50 "
          f"or less) and there walks off the job {{3}} of the time (below 40), dropping the assignment: "
          f"{_c(_x(_m(100, 50), _b(100, 40)))} of building trips in all. One who likes wood always takes the short "
          "route and never walks off."),
         feature="vv2_builders_fix_huts",
         patched="each time the game chooses a builder's work the patch steps in about three times in four (14% for a "
                 "villager whose checked job is not Building): construction first, then fixing a standing hut; the "
                 "rest of the time the normal game's rolls above decide."),
    Roll("Work injuries: rolled once for each building, repair or research step that passes its skill roll; a roll of "
         "0 to 99 below 2 injures the worker ({0}).",
         (Check(0x462BEA, 100, 2, "jge", take=False), Check(0x462D21, 100, 2, "jge", take=False),
          Check(0x462E5D, 100, 2, "jge", take=False), Check(0x462F6F, 100, 2, "jge", take=False),
          Check(0x462AB2, 100, 2, "jge", take=False), Check(0x463072, 100, 2, "jge", take=False),
          Check(0x462975, 100, 1, "jge", take=False), Check(0x46418C, 100, 2, "jge", take=False, push=0x46418A),
          Check(0x464023, 100, 2, "jge", take=False), Check(0x4638BF, 100, 2, "jge", take=False),
          Check(0x46361D, 100, 2, "jge", take=False)),
         ("The three huts, the Hospital, the broken starting hut and the Sewing Hut: {0}, losing 0 to 14 health (a "
          "roll of 0 to 14).",
          "The Ancient Mosaic (the ruins): {6} (a roll of 0 to 99 below 1), losing 0 to 14 health.",
          "The Dam, the Vine Wall and the Overgrown Gong Piece (the thorns): {7}, losing 0 to 9 health.",
          "Research: {10}, losing 0 to 9 health.")),
    Roll("Research with the fire lit: each research session that passes its skill roll gives 1 more tech point {0} of "
         "the time while the fire burns (a roll of 0 to 99 below 10).",
         (Check(0x4637F0, 100, 0xA, "jge", take=False),)),
    Roll("A snack: each snack a villager eats while below 100 health and with food in store costs 1 food and gives "
         "+1 health {0} of the time (a roll of 0 to 99 below 50).",
         (Check(0x4626BD, 100, 0x32, "jge", take=False),)),
    Roll("A cure's extra health: once all six strange plants are understood, each villager a healer cures also gains "
         "10 to 29 health (10 + a roll of 0 to 19, each amount equally likely), up to 100.",
         (Check(0x44DA97, 20),)),
    # ---------------------------------------------------------------- Catch-up
    Roll("While catching up (time away and Time Warp), for each villager more than 2 age units behind, 4 job tries "
         "each counted age unit: when the chooser lands on Parenting the villager embraces only {0} of the time (a "
         "roll of 0 to 99 of 5 or less), otherwise nothing.",
         (Check(0x43B534, 100, 5, "jg", take=False), Check(0x4646DC, 1500, None, "jge")),
         (f"A healer's catch-up step runs a cure scan when a roll of 0 to 1,499 is below Healing: "
          f"{_c(_b(1500, 50))} at Healing 50, {_c(_b(1500, 100))} at 100.",)),
    # ---------------------------------------------------------------- New villagers
    Roll("A new villager's likes and dislikes: at creation a roll of 0 to 99 below 30 gives a first like ({0}), and "
         "a second such roll a second like; the dislikes are rolled the same way, and a like is never also a dislike.",
         (Check(0x44C9C2, 100, 0x1E, "jge", take=False), Check(0x44C9D6, 100, 0x1E, "jge", take=False),
          Check(0x44CA5A, 100, 0x1E, "jge", take=False), Check(0x44CA6E, 100, 0x1E, "jge", take=False)),
         (f"No like {_c(_not(_b(100, 30)))}, one {_c(_x(_b(100, 30), _not(_b(100, 30))))}, two "
          f"{_c(_x(_b(100, 30), _b(100, 30)))}; the same for dislikes.",)),
    # ================================================================ Births and gender
    Roll("An embrace (a villager dropped on another, or pairing up on their own, 0x44F610): both 18 or older, of "
         "opposite sexes, alive, not sick and not nursing. Below 300 food the embrace goes on only {0} of the time "
         "(a roll of 0 to 99 of 65 or less); then the villager who started it must pass a Parenting skill roll.",
         (Check(0x44F702, 100, 0x41, "jle"), Check(0x44F7A0, 300)),
         ("A baby is conceived when a roll of 0 to 299, + 50 - 50 x Medicine level, is at most the Parenting of the "
          "villager who started it. Never when the woman is 50 or older (1,000 age units).",
          f"Medicine level 1: Parenting 30 {_conceive(30, 1)}, 50 {_conceive(50, 1)}, 100 {_conceive(100, 1)}.",
          f"Medicine level 2: Parenting 30 {_conceive(30, 2)}, 50 {_conceive(50, 2)}, 100 {_conceive(100, 2)}.",
          f"Medicine level 3: Parenting 30 {_conceive(30, 3)}, 50 {_conceive(50, 3)}, 100 {_conceive(100, 3)}.",
          "There must be room: population (babies on the way included) below 90 plus 5 for each finished collection "
          "(25 for all four), and 15 or more people need the first hut, 25 the second, 50 the third.",
          "Each conception raises the mother's Parenting by (100 - Parenting) / 10, at least 5, up to 100.",
          "During the tutorial, while its message \"Good! They get along and want to go indoors for some privacy...\" "
          "is still to come, the embrace skips the food roll and always conceives."),
         group=BIRTHS, feature="vv2_manual_drop_breeding_overrides_birth_control",
         patched="a woman of 50 or older dropped on a man (or a man dropped on her) is no longer refused; the rolls "
                 "above still decide."),
    Roll("Twins and triplets: rolled once for each conception (an embrace, catch-up, the Love Note event or the Gong "
         "of Wonder): only at Medicine level 3, twins when a roll of 0 to 99 is below 7 ({0}), and then triplets when "
         "a second roll of 0 to 99 is below 25 ({1}). Below Medicine level 3 every pregnancy is one baby.",
         (Check(0x44BA75, 100, 7, "jge", take=False), Check(0x44BAA9, 100, 0x19, "jge", take=False)),
         (f"Each pregnancy at Medicine level 3: one baby {_c(_not(_T7))}, twins {_c(_x(_T7, _not(_T25)))}, "
          f"triplets {_c(_x(_T7, _T25))}.",
          "The babies are born on the 41st age unit of the mother after conceiving, as children of 2 years.",
          "Nothing else changes these odds: food, difficulty, age, skills and the other technologies do not."),
         group=BIRTHS),
    Roll("A baby's sex: when the babies are born, each is a boy when a roll of 0 to 99 is 49 or less ({0}), "
         "otherwise a girl; neither parent's sex matters.",
         (Check(0x44CB88, 100, 0x31, "jg", take=False),),
         ("In a village of 6 or fewer people (babies on the way included), the first baby's sex is not rolled when "
          "one sex has 2 or fewer living members: it is the more numerous sex (a girl when women outnumber men and "
          "there are 2 men or fewer, otherwise a boy when there are 2 women or fewer).",
          "Twins and triplets are copies of the first baby's record, so they always share its sex."),
         group=BIRTHS),
    Roll("Villagers who arrive: every new villager not born in the village gets its sex as follows.",
         (Check(0x4252A8, 100), Check(0x44CB88, 100, 0x31, "jg", take=False)),
         (f"A new village's founders: a man and a woman of 19 to 28 years (the one given 20 to 29 points of Building "
          f"is the man {_c(_b(100, 50))} of the time, a roll of 0 to 99 below 50), three children of 15, 13 and 12 "
          "years each a boy or a girl exactly 50% of the time (a roll of 0 to 1), a boy of 9 and a girl of 4.",
          "The Barrel O' Babies (1 toddler at an event strength below 5, 2 at 5 to 7, 3 at 8 or more; each 3.5 to "
          "4.45 years old) rolls each toddler's sex like a baby's: a boy {1}, a girl otherwise.",
          "Old Friends: always one man and one woman of 20 to 29 years. The Savage Child, lured with food: always a "
          "boy of 13. The Strange Request: Biggles, always a man of 29. The Silver Mirror (\"Speak the word "
          "Sunimeg\"): a copy of the villager who looks in it, with the same sex.",
          "An Esteemed Elder's totem keeps the elder's sex; it is a statue, not a villager."),
         group=BIRTHS, feature="vv2_enable_origins_exclusive_features",
         patched="the Origins Barrel of Babies upgrade brings the game's own Barrel O' Babies with 3 toddlers, each "
                 "sex rolled as above."),
)
