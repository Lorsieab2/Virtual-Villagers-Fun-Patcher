"""Game Mechanics, The Secret City (VV3): every random roll that changes play, with its exact odds
(src/vv_game_mechanics_chances.py explains the table; tests/test_game_mechanics_chances.py checks it against the exe).

Addresses are the stock exe's (research\\stock-executables, 831,488 bytes).  rand(n) is 0x4032D0 (rand() % n).  The call
paths from the game-screen update 0x4684D0 were traced in the coordinator's research (mech_vv3 spec, addendum 3) and in
docs/hidden-gates-all-five-games.md (VV3, "Reachability chains"):
  the aging loop 0x45FFE0 (each villager's age unit: eating, starving, sickness, health, old age, births; called from
  0x428C60), its sickness roll 0x455C00, the pregnancy writer 0x455AB0 and room check 0x45FE30, the record set-up
  0x456120 / 0x45C540 (sex), the live embrace 0x4584B0 (step 13) and the catch-up runner 0x45B790, the skill test
  0x45A2C0 (step 7), the scheduler 0x45BFE0 and job chooser 0x459730 (the 40-second re-decision 0x45C990 -> 0x45C360,
  up to 10 tries), the special steps 0x458DB0 (24 fish, 25 big catch, 26 research, 38 snack, 43 chief's food), the
  collectible update 0x42DC90 (called every frame) and its spawner 0x42D940, the brew result 0x430A50.
Tech ids (0x426FC0 on 0x582618): 0 Science, 1 Medicine, 2 Alchemy, 3 Restoration, 4 Leadership, 5 Nature, 6 Magic.
Skills (record +0xEAC): Farming, Breeding (Parenting), Healing, Research, Building.  Sex (record +0xDC8): 0 male, 1 female.
Difficulty [game+0x12F08]: 0 Easy, 1 Medium, 2 Hard.  Food: the global 0x582490.  The fire: object 0x5946D8 (timer +0xC).
"""
from __future__ import annotations

import vv_game_mechanics as gm
from vv_game_mechanics_chances import (AGE_UNIT, BIRTHS, DRAWS, Check, Roll, at_most, below, chance, times)

_FRAME = ("checked once every frame while the game is not paused (the game draws at most about 30 frames a real-life "
          "second: its frame limiter waits for 33 real-life milliseconds a frame)")


def _ch(count: int) -> str:
    return chance(count)


def _not(count: int) -> int:
    return DRAWS - count


# Sickness (0x455C00): rand(n) <= k * m, where m is 1 with the fire burning or Aromatherapy (puzzle 11) solved, else 2;
# on Hard m is 1 more unless both are in place.
_SICK = {1: (1440, 3), 2: (2460, 3), 3: (5400, 2)}


def _sick(level: int, m: int) -> str:
    n, k = _SICK[level]
    return _ch(at_most(n, k * m))


_MULTI = below(100, 7)                    # a multiple birth at Medicine 3 (0x455B92)
_TRIPLE = below(100, 25)                  # of those, triplets (0x455BB2)
_TWINS = times(_MULTI, _not(_TRIPLE))
_TRIPLETS = times(_MULTI, _TRIPLE)
_LIKE = below(100, 25)                    # each of the two likes (or dislikes) rolls (0x4548D4, 0x455414)
_LIKES = (times(_not(_LIKE), _not(_LIKE)), 2 * times(_LIKE, _not(_LIKE)), times(_LIKE, _LIKE))


def _conceive(breeding: int, medicine: int, bonus: int = 0) -> str:
    """rand(300) + 50 - 50 x Medicine - bonus <= Breeding (0x4586E1)."""
    return _ch(sum(1 for v in range(DRAWS) if v % 300 + 50 - 50 * medicine - bonus <= breeding))


ROLLS = (
    # -- Each villager's age unit (the aging loop 0x45FFE0) -------------------------------------------------------
    Roll("Eating: " + AGE_UNIT + ", each living villager eats 2 food; with 500 food or less they skip the meal "
         "{0} of the time, and a villager who skips loses 1 health {1} of the time.",
         (Check(0x460053, 100, 0x32, "jl", take=False), Check(0x460062, 100, 0x1E, "jge", take=False),
          Check(0x4600B7, 100, 0x4B, "jg", take=False)),
         ("Eating 2 more: on Medium with 8,000 food or more, and on Hard at any amount, each villager eats 2 more food "
          "{2} of the time; never on Easy.",)),
    Roll("Starving: " + AGE_UNIT + ", with no food left each villager loses 1 health {0} of the time (a roll of 0 to 99 "
         "at or under 75).",
         (Check(0x4600DF, 100, 0x4B, "jle"), Check(0x460146, 100, 0x1E, "jg", take=False)),
         ("On Hard, and for a villager whose hidden number (a value the game rolls at creation and keeps in the save) is "
          "a multiple of 6, the loss comes every age unit.",
          "After that loss, a villager at 20 health or less whose hidden number is odd regains 1 health {1} of the "
          "time.")),
    Roll("A sick villager's health: " + AGE_UNIT + ", a sick villager loses 1 health {0} of the time while above 20 "
         "health, and only " + _ch(times(at_most(100, 60), at_most(100, 30))) + " of age units at 20 or less ({0} "
         "times {1}). Sickness never ends by itself.",
         (Check(0x46017D, 100, 0x3C, "jg", take=False), Check(0x460195, 100, 0x1E, "jg", take=False))),
    Roll("Regaining health: " + AGE_UNIT + ", a villager who is not sick, while there is food, passes the health check "
         "{0} of the time; failing that, it passes on Easy, at Medicine level 3, and with the fire burning on a second "
         "roll of {1}.",
         (Check(0x4601E6, 100, 0x32, "jl"), Check(0x460204, 100, 0x32, "jge", take=False),
          Check(0x46023D, 100, 0x14, "jge", take=False)),
         ("So the check passes " + _ch(below(100, 50)) + " of age units on Medium or Hard, "
          + _ch(below(100, 50) + times(_not(below(100, 50)), below(100, 50))) + " with the fire burning, and every one "
          "on Easy or at Medicine 3.",
          "A pass gives +1 health (up to 100); an elderly villager (42 years plus 8 for each Medicine level: 50, 58 or "
          "66 at Medicine 1, 2 or 3) gets it only {2} of the passes.")),
    Roll("Falling sick: " + AGE_UNIT + ", each villager who is not yet sick rolls; the chance depends on Medicine, the "
         "fire, the Aromatherapy puzzle and the difficulty.",
         (Check(0x455CD7, 1440, None, "jg"), Check(0x455CBB, 2460, None, "jg"), Check(0x455C9F, 5400, None, "jg"),
          Check(0x455D02, 1000, 0x0E, "jle"), Check(0x460282, 100, 0x32, "jl"), Check(0x455C14, 100, 0x32, "jge")),
         (f"Medicine 1: {_sick(1, 1)} with the fire burning or Aromatherapy solved, {_sick(1, 2)} with neither.",
          f"Medicine 2: {_sick(2, 1)} or {_sick(2, 2)}. Medicine 3: {_sick(3, 1)} or {_sick(3, 2)}. Medicine 0: no "
          "villager rolls this.",
          f"On Hard: with both the fire burning and Aromatherapy solved, the first figure; with one of the two, the "
          f"second; with neither, {_sick(1, 3)}, {_sick(2, 3)} or {_sick(3, 3)} at Medicine 1, 2 or 3.",
          "An elderly villager (42 years plus 8 for each Medicine level; 42 at Medicine 0) who escapes that roll has "
          "a second one: {3} more.",
          "On Easy the roll is made only " + _ch(times(_not(below(100, 50)), _not(below(100, 50)))) + " of age units "
          "(two rolls of 0 to 99 at 50 or more must both come up), so about a quarter of these chances.")),
    Roll("The old-age death roll: on each birthday (every 20 age units: 1 real-life hour on Fast, 2 real-life hours on Normal, 3 "
         "real-life hours 20 minutes on Slow) past 47, 55, 63 or 71 years (Medicine 0, 1, 2 or 3) a villager dies with a chance of 10% for each year past it (a roll of 0 to 99 under 10 x the years over): "
         + _ch(below(100, 10)) + " one year over, " + _ch(below(100, 50)) + " five years over, 100% from ten years "
         "over.",
         (Check(0x4602F9, 100),),
         ("The birthday roll follows the hidden processed age, which the game steps up one age unit at a time to "
          "the age shown -- every step in the same update after time away, so each birthday passed while away gets its "
          "roll.",),
         feature="vv3_nature_level_three_alters_mortality",
         patched="at Nature level 3 every one of these thresholds is 7 years later (54, 62, 70 or 78 years)."),
    # -- Work: the skill test (0x45A2C0, step 7) and the job chooser ---------------------------------------------
    Roll("The skill test, made whenever a villager finishes a task (a harvest, a building action, a cure, a research "
         "session, an embrace): a roll of 0 to 99 at or under the skill + 33 succeeds, so the chance is the skill + "
         "34% (" + _ch(below(100, 34)) + " at skill 0, " + _ch(below(100, 84)) + " at 50, 100% from 66).",
         (Check(0x45A342, 100, None, "jle"), Check(0x45A495, 100, 0x32, "jg", take=False),
          Check(0x45A4A6, 100, None, "jl")),
         ("A villager who likes learning, or who is under the potion effect that makes them feel smarter, adds 66 "
          "instead of 33 (" + _ch(below(100, 67)) + " at skill 0); one who dislikes learning adds 16 ("
          + _ch(below(100, 17)) + " at skill 0).",
          "On a failure nothing of the task is paid and the skill does not rise, except that a villager at exactly 0 "
          "gains 4. Before the village's first success in Farming, Breeding or Research, the try after one failure "
          "always succeeds.",
          "On a success the skill rises by (70 - skill) / 18 for Farming, Research and Building, / 10 for Breeding and "
          "/ 12 for Healing (whole numbers, at least 7 from 0), doubled when the villager likes learning and halved "
          "when they dislike it; once that comes to 0, the skill rises by 1 only when a roll of 0 to 99 is at or "
          "under 50 ({1}) and a second is at or above the skill."),
         feature="vv3_learning_never_fails",
         patched="every Farming, Building, Research, Healing and Breeding skill test succeeds; the skill gains are "
                 "the game's own."),
    Roll("Deciding what to do: every 40 real-life seconds at any speed, each idle villager decides again, up to 10 "
         "tries; each try goes on to look for something to do only {0} of the time (a roll of 0 to 99 above 65), "
         "except for the Tribal Chief, who always does.",
         (Check(0x45C0BC, 100, 0x41, "jg"),)),
    Roll("Choosing a job, at each try to look for something to do: a villager who does not like work takes no job {0} of the time; one who dislikes "
         "work takes none a further {1} of the time.",
         (Check(0x45973A, 100, 0x0F, "jge", take=False), Check(0x45977B, 100, 0x46, "jl"),
          Check(0x45978E, 100, 0x0F, "jle", take=False), Check(0x459853, 100, 0x55, "jg", take=False),
          Check(0x459874, 100, None, "jge"), Check(0x459892, 100)),
         ("Each of the five skills is looked at only {2} of the time (a roll of 0 to 99 above 15), and the highest skill "
          "looked at wins; Breeding counts 15 lower than it is; a villager who dislikes medicine passes over Healing "
          + _ch(below(100, 50)) + " of the time.",
          "A job ticked as the villager's preference on the Details screen replaces that pick {3} of the time.",
          "Then, with the job's score 6 or more, the villager takes the job only when a roll of 0 to 99 is under the "
          "score + 40, so from a score of 60 always; with 5 or less never.",
          "Children (Breeding) without the Children preference ticked still goes ahead only "
          + _ch(_not(below(100, 75))) + " of the time."),
         feature="vv3_birth_control",
         patched="a villager starts embracing on their own only with both Breeding skill and the Children preference "
                 "ticked: the " + _ch(_not(below(100, 75))) + " route without the preference is gone."),
    Roll("Low food: while food is 250 or less, a villager with Farming 20 or more tries farming first; otherwise one "
         "whose job is not Farming or Healing stands \"Worried about food\" instead of working {0} of the time.",
         (Check(0x45C246, 100, 0x32, "jl", take=False),)),
    # The weather (0x4B86C4; start 0x41FB40, every-frame update 0x41FD30 from 0x468BF3, reset 0x41FCC0): kind +0, the
    # waiting kind +4, its end +8 (game clock 0x5825D4), its start +0xC, the strength then +0x10, the strength +0x14
    # (0x4B86D8).  Kinds: 0 clear, 1 only from the roll below, 2 rain (Rainy Season 0x4150D0), 3 storm (the Omen
    # 0x4166B2), 4 fog (the Fog events 0x414E50 / 0x414E90, Thick as Pea Soup 0x4151E0, the Cold Snap 0x415110).
    Roll("The weather: when a spell of weather ends (0x41FEE4), a clear sky is followed by one of the other four kinds "
         "-- kind 1, rain, a storm or fog, 1 in 4 each (a roll of 0 to 4, made again while it comes up clear) -- and "
         "any other weather by a clear sky; a kind an island event or puzzle has set comes instead (30 real-life "
         "seconds after it is set on Normal speed, 0x41F990).",
         (Check(0x41FF52, 5), Check(0x41FC4E, None), Check(0x41FCE9, 100, push=0x41FCC6),
          Check(0x45BA42, 100, 0x4B, "jge", take=False)),
         ("A clear sky lasts 15 to 30 real-life minutes on Normal speed (7.5 to 15 on Fast, 25 to 50 on Slow), any "
          "other weather 3 to 6 (1.5 to 3 on Fast, 5 to 10 on Slow), each whole second of the range equally likely "
          "(0x41FC4E); while the first fruit tree is grown (planted 8 real-life hours ago on Normal) and no second one is "
          "planted, each lasts its shortest and a clear sky is always followed by rain (0x41FC0F, 0x41FF62).",
          "A new village starts clear; " + _ch(below(100, 20)) + " of the time instead the kind the real-life "
          "clock's minute gives (its remainder by 5, 1 to 4) comes 30 real-life seconds later on Normal speed (0x41FCC0, 0x41FA30).",
          "The weather's strength (0 to 100), on Normal speed: in rain or a storm it grows 5 every 6 real-life seconds "
          "from what it was when the rain began, up to 100 -- from 0, above 20 after 26 real-life seconds, 50 after "
          "60, above 50 after 62, 100 after 120 (0x41FE31) -- and in any other weather it falls 5 every 12 real-life "
          "seconds, down to 0 (100 to 0 in 240; 0x41FE0E). On Fast every one of these times is half as long, on "
          "Slow 1 2/3 times as long (the game's clock, paused time not counted). The Tsunami and a storm from The Omen in the Clouds set it to 100 at once "
          "(0x414B3E, 0x4166FF -> 0x41F9B0); a new village starts at 0.",
          "What the strength changes: above 20 every mushroom-or-collectible is a mushroom, and above 50 a second "
          "spawn roll is made (the mushroom line below); in rain or a storm at 50 or more the heavy-rain stop below, "
          "and a villager's pastime pick (0x45B9B0) is \"Playing in puddles\" {3} of the time; in rain or a storm "
          "above 30 every villager standing idle, \"Unsure what to do\" or \"Not feeling well\" goes \"Getting out "
          "of the rain\" (0x41FE4E); after it, while the strength is above 5 and no rain or storm falls, two of the "
          "six water-side pastimes (0x4598D0) are \"Cleaning up after the rain\" instead of \"Washing the laundry\" "
          "and \"Washing face\"; with The Lift solved the lift's height follows it, (strength - 20) x 8 "
          "/ 100 from 0 to 7, carrying a villager \"Standing on the lift\" (0x435C26), and \"Playing seesaw\" is "
          "picked only at strength 0 with nobody on the lift (0x45BBF9). When rain or a storm ends, villagers "
          "\"Drinking rain\", \"Getting out of the rain\" or \"Playing in puddles\" stop (0x41FF0E).",
          "Above 50 the scene also draws one more picture and sets one scene object's look (0x429269, 0x4210DA); "
          "what they show was not seen."),
         sub_verified=(gm.RUNNING, gm.RUNNING, gm.RUNNING, gm.RUNNING, False)),
    Roll("Heavy rain: in rain or a storm of strength 50 or more (the weather line above), a worker who neither likes "
         "nor dislikes rain stops working {0} of the time (rain-lovers go to drink the rain, rain-haters get out of "
         "it).",
         (Check(0x459537, 100, 0x14, "jge", take=False),)),
    Roll("Dislikes at work: a farmer who dislikes bees or honey (the honey), fruit (the fruit trees), or fish, the ocean "
         "or swimming (fishing) runs away instead {0} of the time; a fish-hater who does start fishing walks off "
         "every time. A builder who dislikes wood walks off a hut {1} of the time.",
         (Check(0x45B145, 100, 0x3C, "jge", take=False), Check(0x453A9D, 100, 0x28, "jge", take=False))),
    Roll("The big catch: each successful catch by a fisher with Farming 88 or more is a 55-food catch {0} of the time "
         "instead of the usual one.",
         (Check(0x4535A2, 100, 0x0A, "jge", take=False),)),
    Roll("The Tribal Chief's supervision: when the chief directs work where a villager is fishing, picking fruit, "
         "gathering honey, building or researching, the work pays more when a roll of 0 to 99 is under 25 x the "
         "Leadership level: " + _ch(below(100, 25)) + ", " + _ch(below(100, 50)) + " or " + _ch(below(100, 75))
         + " at Leadership 1, 2 or 3 (never at 0).",
         (Check(0x45FC9D, 100),),
         ("It adds a third to fish and fruit, a half to honey, 1 more to a building action, and a third (Science 0) or a "
          "quarter (Science 1 or more) to research.",)),
    Roll("The chief's Grant Food (Leadership 1 or more, every 23 real-life hours): 3 x Leadership x (10 to 29, each "
         "equally) food, so 30 to 87 at Leadership 1, 60 to 174 at 2, 90 to 261 at 3.",
         (Check(0x459042, 20),)),
    Roll("Hut repairs: once all four huts are finished, a builder who examines a hut goes on to fix it {0} of the time; "
         "fixing trains Building and changes nothing on the hut.",
         (Check(0x453CDE, 100, 0x46, "jge", take=False),)),
    Roll("Curing: a healer's cure passes the Healing skill test (the skill + 34%); a healer who dislikes medicine then "
         "fails {0} of the passes anyway (while playing; not while the game catches up).",
         (Check(0x4573B5, 100, 0x32, "jl"),),
         feature="vv3_chief_hospital_supervision",
         patched="with the Tribal Chief directing work at the Hospital, a cure whose skill test fails goes ahead when "
                 "the chief's supervision roll passes (" + _ch(below(100, 25)) + ", " + _ch(below(100, 50)) + " or "
                 + _ch(below(100, 75)) + " at Leadership 1, 2 or 3)."),
    Roll("Burying the dead: when a body is found, any adult takes it on {0} of the time; otherwise a villager with "
         "Healing 50 or more takes it {1} of the time.",
         (Check(0x45C189, 100, 0x19, "jl"), Check(0x45C1A1, 100, 0x46, "jge", take=False))),
    Roll("Research: after each successful research session, a lab accident costs the researcher 0 to 9 health "
         "(each equally) {0} of the time; while the fire burns, the session pays 1 more tech point {1} of the time.",
         (Check(0x45916F, 100, 2, "jge", take=False), Check(0x459421, 100, 0x0A, "jge", take=False),
          Check(0x459180, 10))),
    Roll("A snack at the food bin (a villager below 100 health who goes to eat while there is food): it costs 1 food "
         "and gives +1 health {0} of the time.",
         (Check(0x458E47, 100, 0x32, "jge", take=False),)),
    Roll("Brewing a potion (the Alchemy Lab): the brew blows up when a roll of 0 to 99 is at or under 15 x (3 - the "
         "Alchemy level): " + _ch(at_most(100, 45)) + ", " + _ch(at_most(100, 30)) + ", " + _ch(at_most(100, 15))
         + " or " + _ch(at_most(100, 0)) + " at Alchemy 0, 1, 2 or 3.",
         (Check(0x430A92, 100, None, "jle"), Check(0x430C2C, 40)),
         ("A blow-up costs the villager tending the pot 30 to 69 health (each equally); at 0 they die.",)),
    # -- Mushrooms and collectibles (0x42DC90, every frame) ------------------------------------------------------
    Roll("A mushroom or collectible appears: " + _FRAME + ", {0} each time (a roll of 0 to 5,999 under 3), so about "
         "once a real-life minute at any speed; at most 2 are out at once, and each is gone after 90 real-life "
         "seconds.",
         (Check(0x42DD72, 6000, 3, "jl"), Check(0x42DD8D, 6000, 3, "jge", take=False),
          Check(0x42D98D, 100), Check(0x42DA7A, 100, 8, "jge", take=False), Check(0x42DAB9, 100, 4, "jge", take=False)),
         ("With the weather's strength above 50 (the weather line above says when) a second roll of {1} follows in "
          "the same frame.",
          "It is a mushroom " + _ch(below(100, 30)) + " of the time (a roll of 0 to 99 under 30), and always in rain or "
          "a storm or with the weather's strength above 20; otherwise a collectible.",
          "A mushroom is red (35 food) {3} of the time, otherwise brown (6 food).",
          "A collectible is rare {4} of the time, uncommon " + _ch(below(100, 17) - below(100, 4)) + " and common "
          + _ch(_not(below(100, 17))) + ", from one of the four collections chosen at random (the Tablet only once "
          "The Ruins is at least 2% done); an owned Tablet piece is not placed again."),
         feature="vv3_super_secret_golden_mushroom",
         patched="1 in 1,000,000 of the random brown or red mushrooms is a gold Golden Mushroom instead, worth 100 "
                 "food."),
    Roll("The Tribal Chief's rare collectible (Leadership 3, every 23 real-life hours): the piece is always rare, from a "
         "collection chosen at random; it is lost when the game picks an owned Tablet piece or one already out.",
         (Check(0x42DC2B, 100),),
         feature="vv3_rare_collectible_retry",
         patched="a refused pick is made again, up to 20 times, so a piece almost always appears."),
    Roll("A new villager's likes and dislikes: two rolls each come up {0} of the time (a roll of 0 to 99 under 25), "
         "so a villager has no likes " + _ch(_LIKES[0]) + ", one " + _ch(_LIKES[1]) + " and two " + _ch(_LIKES[2])
         + "; dislikes the same; each is one of the game's 79 words, never one it already holds.",
         (Check(0x4548D4, 100, 0x19, "jge", take=False), Check(0x455414, 100, 0x19, "jge", take=False))),
    # -- Births and gender ---------------------------------------------------------------------------------------
    Roll("Conception (dropping one villager on another, or a villager embracing on their own): the pair must be a man "
         "and a woman, both 18 or older, alive, not sick, neither already pregnant or nursing; with 250 food or less "
         "they refuse {0} of the time; then the villager you dropped (or who started it) must pass the Breeding skill "
         "test.",
         (Check(0x45857D, 100, 0x41, "jle", take=False), Check(0x4586E1, 300)),
         ("Then a roll of 0 to 299, plus 50, less 50 x the Medicine level, less a potion's help, must be at or under "
          "that villager's Breeding: at Breeding 100, " + _conceive(100, 0) + ", " + _conceive(100, 1) + ", "
          + _conceive(100, 2) + " or " + _conceive(100, 3) + " at Medicine 0 to 3; at Breeding 50, "
          + _conceive(50, 1) + " at Medicine 1.",
          "The fertility potion takes 50 more off the roll (" + _conceive(50, 1, 50) + " at Breeding 50 and "
          "Medicine 1), the strong one 100 (" + _conceive(50, 1, 100) + ").",
          "A woman of 50 or older never conceives. The village's very first conception skips the food refusal and "
          "this roll. A conception raises that villager's Breeding by a tenth of what it lacks of 100, at least 5.",
          "No pregnancy starts once the population, babies on the way included, reaches 90 + 5 for each complete "
          "collection (25 for all four) + 10 at Magic 3, or without room in the huts: 10 people or more need one "
          "finished hut, 17 two, 35 three."),
         group=BIRTHS,
         feature="vv3_manual_drop_breeding_overrides_birth_control",
         patched="a woman of 50 or older dropped on a man (or a man on her) is no longer refused; the chances are the "
                 "game's own."),
    Roll("Conception while the game catches up time away (and in a Time Warp): a villager whose job is Children embraces "
         "on {0} of tries, with no skill test, food refusal or potion help; the roll of 0 to 299 is the same.",
         (Check(0x45BF59, 100, 5, "jg", take=False), Check(0x45B822, 300), Check(0x45B865, 50)),
         ("The baby's starting skill is then the partner's best skill (the embracing villager's "
          + _ch(below(50, 1)) + " of the time) at 5 to 7.",),
         group=BIRTHS),
    Roll("Twins and triplets, rolled once per pregnancy when it starts: only at Medicine level 3, a pregnancy is "
         "multiple {0} of the time, and a multiple is triplets {1} of the time.",
         (Check(0x455B92, 100, 7, "jge", take=False), Check(0x455BB2, 100, 0x19, "jge", take=False)),
         ("So at Medicine 3: one baby " + _ch(_not(_MULTI)) + ", twins " + _ch(_TWINS) + ", triplets "
          + _ch(_TRIPLETS) + ". Below Medicine 3 every pregnancy is one baby.",
          "Nothing else changes these odds: not the parents' skills, ages, food or potions, nor the difficulty."),
         group=BIRTHS),
    Roll("Birth: the babies come on the 41st age unit after conception. Each baby's sex is a roll of 0 to 99: a boy at "
         "49 or under ({0}), otherwise a girl.",
         (Check(0x45C54A, 100, 0x31, "jg", take=False),),
         ("Balancing: when the village has 6 or fewer people (babies on the way included) and one sex has 2 or fewer "
          "living members, the baby is of the other, more numerous sex (a boy when they are equal); otherwise the "
          "roll decides.",
          "Twins and triplets are copies of the first baby: the same sex, skills and likes.",
          "The baby's one starting skill is the mother's best skill (the father's " + _ch(below(50, 1)) + " of the "
          "time) at 5 to 7, or 4 to 6 when both parents' best skill is the same one."),
         group=BIRTHS),
    Roll("Other new villagers: Another One of Those Barrels brings 3 children of 10 years (the second and third only "
         "while there is room), each a boy or a girl exactly half the time, with one skill at 5 to 9.",
         (Check(0x415327, 2),),
         ("The Canoe from the Other Side always brings a man of 30 with Building 40 to 69.",
          "A Crystal of Reflections copy is the same sex as the villager it copies.",
          "A new village's founders: a man and a woman of 19 to 28, one of them with Building 20 to 29 (the man "
          + _ch(below(100, 50)) + " of the time), a woman of 19, then a child of 3, a child of 6 to 7 and two adults "
          "of 19 to 28, each of these four a boy or a girl exactly half the time."),
         group=BIRTHS,
         feature="vv3_story_cheat_upgrades",
         patched="a Custom Island Event's new villagers are the sex the player sets for each."),
)

# Cosmetic rolls left out (reported, not shown): looks at creation (head and body, 0x456365 / 0x4563C7 / 0x4564A9 ..
# 0x456577), the pose at creation (0x4565C4), walk targets, step lengths, animations and speech inside the 181 villager
# actions, the research lab's visual effect (0x4590AF, 10% of live sessions, particles only), the chief's lessons and
# the step-42 skill reward (0x458F13, queued by actions not traced to a player-visible name).
