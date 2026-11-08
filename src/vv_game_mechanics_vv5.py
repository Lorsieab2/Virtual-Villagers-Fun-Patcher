"""Game Mechanics for New Believers (VV5): read-only lines from one save (src/vv_game_mechanics.py).

THE SAVE.  A 24-byte header -- "ldwg", ..., the clock's base as an int64 Unix time at 0x08 -- then the
game manager from +0x10: manager field X is file offset X + 0x10.  The clock 0x4036E0 counts real
seconds from the base (not scaled by the speed), so a stamp v is the real moment base + v.  FILE offsets:
  speed 0x17D8C (3 Fast, 6 Normal, 10 Slow; + 999 paused), the last tick 0x17D60, food 0x7C0, Mushrooms
  Found 0x7D8, island events seen 0x7E8, tech points 0xBC34, noni 0x17D68 (next tick 0x17D50), crops
  0x17D6C (next refill 0x17D54), Divine Energy 0x17D74 (cap 0x17D70), next island event 0x17D4C,
  project n's progress 0x16D30 + 8n (the Hydroponic Farm is project 5, done at 30; the Knowing Totem 4).

THE RULES: the coordinator's verified spec mech_vv5\\spec.md (2026-10-23).  A line built only from what it
marks VERIFIED (the stock routine emulated) or from the save is verified; anything it marks READ carries UNCONFIRMED.  Events that can never happen in the
stock game are not listed.
"""
from __future__ import annotations

import struct

import vv_game_mechanics as gm
import vv_game_mechanics_death as death
import vv_game_mechanics_events as events
import vv_game_mechanics_faith_vv5 as faith
import vv_game_mechanics_life as life
import vv_game_mechanics_nursery as nursery
import vv_game_mechanics_powers_vv5 as powers
import vv_save_backup

GAME = 5
SPEED, LAST_TICK = 0x17D8C, 0x17D60
FOOD, MUSHROOMS_FOUND, EVENTS_SEEN, TECH = 0x7C0, 0x7D8, 0x7E8, 0xBC34
NONI, NONI_NEXT, CROPS, CROPS_NEXT = 0x17D68, 0x17D50, 0x17D6C, 0x17D54
ENERGY, ENERGY_CAP, EVENT_NEXT = 0x17D74, 0x17D70, 0x17D4C
PROJECTS = 0x16D30
HYDRO_FARM, HYDRO_DONE = 5, 30
UNIT = 360                                    # an age unit, in Normal-speed seconds
NONI_CAP, CROPS_FULL, CROP_UNITS = 1000, 800, 40
STORY = "vv5_story_cheat_upgrades"
GOLDEN = "vv5_super_secret_golden_mushroom"
HUNGRIER = "vv5_hungrier_villagers"
CLASSIC = "vv5_classic_vv_difficulty"
LEARNING = "vv5_learning_never_fails"
SCIENCE_SET = "vv5_science_collectibles_complete"
# Food Gains are Flat, like VV1-3 (Harder Games): a noni pick pays The Secret City's fruit and honey pick
# (0x434ABB..0x434AE4: 7, 3 or 2 on Fast, Normal or Slow, 4 while catching up) instead of the noni / 100; the
# patched step 0x46CFD4 reads the catch-up flag game+0x17E10 and the speed game+0x17D7C (any other value: 3).
FLAT = "vv5_food_pays_like_earlier_games"
FLAT_PICK, FLAT_CATCH_UP = {gm.FAST: 7, gm.NORMAL: 3, gm.SLOW: 2}, 4

# The audit of 2026-10-25 removed the Other group's sickness, health, conception and skill-check lines: each repeated
# the exact one under Chances or Births and gender (and the sickness line had Medicine 2 as 0.16%, the code's
# 2460-roll gives 0.171%, 0x465FB6).  The Faith pointer went too: the group is on the page under its own heading.
LIFE_LINES: tuple[tuple[str, object], ...] = ()


# Hidden villager stats (the coordinator's specs hidden_vv5\spec.md and likes_all, 2026-10-23):
# (line, what stands behind it -- gm.RUNNING, gm.OWNER, or False for UNCONFIRMED).
HIDDEN_LINES = (
    ("Each villager's hidden name number (1 to 183, not inherited; a name always has the same one) sets how it "
     "starves; the villagers' numbers are below.", gm.RUNNING),
    # Preaching is under Faith and Heathens; the skill check's odds (with the like and dislike of learning) under
    # Chances.  The gain: (70 - skill) ÷ 18 at 0x46B3EE, 7 at skill 0 (0x46B40E), halved or doubled 0x46B41C.
    ('Learning: a skill check that succeeds gains (70 - skill) ÷ 18 skill points (Parenting ÷ 10, Healing ÷ 12), '
     '7 at skill 0, then doubled for a villager who likes learning and halved for one who dislikes it; how often '
     'the check succeeds, liked or disliked, is under Chances.', gm.RUNNING),
    ('Parenting: a failed check gives 4 at any Parenting except 0, where the other skills give 4 only at 0 (at '
     "Parenting 10: 55% fail for +4, 45% succeed for +6). This is the stock game's own behaviour.", gm.RUNNING),
    ('Liking work skips the 15% chance of doing nothing and keeps a player-given task 99% of the time (86% '
     'otherwise); disliking it, 70% of job picks end in doing nothing, a player-given task is kept 63% of the '
     'time, and while catching up 78% find no job (29% otherwise).', gm.RUNNING),
    ('Rain: a villager who likes it drinks the rain 98.7% of the time (12% otherwise); one who dislikes it gets '
     'out of the rain 98.7% of the time. Running: liked, a walk at speed 300 (100 otherwise, 0x4659BF); disliked, 40 (0x465A06), '
     'except when fleeing. Jumping: liked, Dancing becomes a 30-jump dance; disliked, jump steps are skipped.',
     gm.RUNNING),
    ('Dancing, disliked: no dancing or rain dancing, and no dance moves at celebrations. Laundry: liked 53% of the '
     'time (12.3% otherwise), disliked never. Swimming, disliked: no swimming, pools, lake or waterfall; the '
     'ocean, disliked: no swimming or pools, and 60% of fishing becomes running away.', gm.RUNNING),
    ('Disliked heights: no waterfall; talking: no praising; resting: no relaxing, and like sitting, a villager '
     'who is not feeling well paces instead of lying or sitting down. Fish or berries, disliked: 60% of fishing '
     'or noni picking becomes running away.', gm.RUNNING),
    ('Wood, disliked: wooden projects are offered 16% of the time, 37% of hut building becomes running away, a '
     'drop on the wood pile is refused half the time. Owls, disliked: the granary 16%. Rocks, disliked: never the '
     'statue, and running away. Medicine, disliked: the Healing job 42.6% instead of 78.5%, a cure accepted 36.7% '
     'instead of 73.5%.', gm.RUNNING),
    ('Fire, disliked: dropped on the fire pit, the villager runs away (80% unlit, always when burning). Stories, '
     'disliked: no story when either villager dislikes them. Children, disliked: "Telling a story" stops 69 '
     'times in 70. Playing: liked, a child picks from 5 plays; disliked, never plays in the dirt. Crowds, '
     'disliked: never joins village celebrations.', gm.RUNNING),
    ('Heathen adults choose what to do without their likes; heathen children follow the children\'s ways.',
     gm.RUNNING),
    # Unproven, not wrong: the 24 likes above are every read of the like and dislike lists traced for this page.
    ('The other 55 of the game\'s 79 likes and dislikes (Plants and Lifting among them): no code that reads them '
     'was found, so they are thought to change nothing; not proven, as not every read of a villager\'s likes and '
     'dislikes in the game was traced.', False),
    # The sickness and health line that stood here repeated Chances and Death and graves word for word.
)
# The fire (the Other group): its length and lighting are the Lightning Strike's (God powers, 0x439090); the
# research bonus 0x46DE7C-0x46DEA0 (rand(100) < 10 while 0x438EC0 says it burns); the Cold Snap's apply 0x414E20 sets
# weather 4, then 0x438E30 ends the fire; the owner (2026-10-24) for the rest.
FIRE_LINES = (
    ('The fire: lit on the built fire pit by the Lightning Strike God Power, it burns 10, 20 or 33 hours 20 '
     'minutes of real-life play on Fast, Normal or Slow (see God powers). While it burns, health comes back more '
     'often (see Chances) and a research success gives 1 more tech point 10.01% of the time.', gm.RUNNING),
    (gm.FIRE_OUT + " The Cold Snap island event (it needs the fire burning) puts it out. How it burns down while "
     "the game is closed is under Time away (catch-up).", gm.OWNER),
)
# Puddle play (scripts/build_apprentice_faith_puddles_features.py has the trace): "Playing in puddles" is behaviour
# 0x5E (0x45FFF0, string 0x229), started only by 0x46E4F7: rain level [0x718EB8] 50 or more, rand(100) < 75, raining
# (0x477040), the lake's water 0x43C5D0 (project 10's progress above 0) absent; five walks to lake-bed area 0x6A
# (0x4744C0 at 0x46003B) and its picker 0x477B90.  "Excited about the puddles" (0xEB, 0x454200) is another action:
# its choosers 0x469E4B (the child-activity pick 0x469DC0, case 4) and 0x46EFB2, three walks to area 0x69.
PUDDLES = "vv5_puddles_by_the_lake"
PUDDLE_LINES = (
    ("Children go \"Playing in puddles\" in the dry lake bed when it rains; once the lake bed is full of water they "
     "no longer do, because they cannot swim.", gm.OWNER),
    ("In the code: \"Playing in puddles\" (0x45FFF0) starts (0x46E4F7) 75 times in 100 when the rain level is 50 "
     "or more, it is raining and The Lake holds no water (0x43C5D0); the child walks five times to a random point "
     "of the lake bed's puddles (area 0x6A, 1,479 spots, 0x4744C0) and plays there. The game's own point picker "
     "0x477B90 only ever takes the first 1,024 spots of an area.", gm.CODE),
    ("\"Excited about the puddles\" is a different action with the same rain and water rule: a child's pastime "
     "(0x469DC0, one pick in 6) or the scheduler (0x46EFB2) starts it (0x454200), three walks to the lake bed "
     "(area 0x69); with water in the lake, or without rain, those choosers pick \"Chasing fish\" instead "
     "(\"Looking for bits of fish\" before The Lake is solved, 0x454130).", gm.CODE),
)
# The audit of 2026-10-25: "104 rolls are verified" was a count nobody could check, Spreading the Word's line
# contradicted the exact one under Faith and Heathens (0x46D2A8: +30 to one listener, not "a random heathen"), and
# the God Power spell timers repeated God powers (the game calls Revive "Revive", not "Reanimate").
CHANCE_EXTRA = (
    # 2,368 calls and jumps to rand 0x403660 in the stock exe's code section, counted 2026-10-25.
    ('The game asks its random-number routine (0x403660) from 2,368 places in its code. The rolls on this page '
     'are the ones that decide food, health, sickness, Faith, births, deaths, skills, island events, collectibles '
     'and God Powers; the others (where villagers walk, how long they wait or animate, which sound or voice plays, '
     'which child or leisure action is picked) were not traced one by one, so it is not proven that none of them '
     'changes a figure on this page.', False),
    ('Timers, in real-life time on Fast, Normal or Slow speed: an age unit 3, 6 or 10 minutes (noni +2 at each); '
     'a crop refill every 2 hours, 4 hours or 6 hours 40 minutes; weather 1.5 to 3, 3 to 6 or 5 to 10 minutes. '
     'At any speed: the first island event 15 minutes after a village is made, the next 30 minutes later while '
     'none has been seen, then 8 to 15 whole hours after the last; God Power spells as under God powers.',
     gm.RUNNING),
)


def _i32(data: bytes, at: int) -> int:
    return struct.unpack_from("<i", data, at)[0]


def facts(village: gm.Village) -> list[gm.Fact]:
    data = village.data
    found = vv_save_backup.save_speed(GAME, data)
    if found is None or len(data) < SPEED + 4 or found[0] != SPEED:
        return [gm.Fact("Other", f"{village.save.name} could not be read: it is not a New Believers save.")]
    base = struct.unpack_from("<q", data, 8)[0]
    speed_value = found[1]
    speed = gm.speed_base(speed_value)
    paused = speed_value >= gm.PAUSED
    on = gm.speed_name(speed)
    last = base + _i32(data, LAST_TICK)

    def real(at: int) -> float:
        return base + _i32(data, at)

    def due(at: int) -> str:
        if paused:
            return f"{gm.duration(max(0, _i32(data, at) - _i32(data, LAST_TICK)))} after it is unpaused"
        if real(at) <= village.now:
            return f"{gm.when(real(at))} (when the village is next played)"
        return gm.when(real(at))

    out: list[gm.Fact] = []
    add = lambda group, text, ok=False: out.append(gm.Fact(group, text, ok))  # noqa: E731
    unit = gm.duration(60 * speed)
    farm = _i32(data, PROJECTS + 8 * HYDRO_FARM) >= HYDRO_DONE

    # -- Food sources --------------------------------------------------------------------
    add("Food sources", f"Food in storage: {_i32(data, FOOD):,}.", gm.SAVE)
    noni = _i32(data, NONI)
    # The pick is job step 12 (0x46CFCD): max(2, noni ÷ 100) into storage through 0x41EB40, as many noni taken.
    add("Food sources", f"Noni bushes: {noni:,} of {NONI_CAP:,}; a pick gives {max(2, noni // 100)} food now (the noni "
                        f"÷ 100, at least 2, before Food Mastery), and takes as many noni. Noni can be picked once the "
                        "granary is built (while catching up, also only once The Hungry Totem is solved: see Time away "
                        "(catch-up)).", gm.RUNNING)
    flat = village.has(FLAT)
    if flat is not False:
        add("Food sources", gm.patch_words(
            village, FLAT, f"a noni pick gives {FLAT_PICK.get(speed, 3)} food on {on} speed instead (7, 3 or 2 on "
                           f"Fast, Normal or Slow and {FLAT_CATCH_UP} while catching up, as The Secret City's fruit "
                           "and honey, before Food Mastery) and takes as many noni; the Hydroponic Farm crops (10, 7 "
                           "or 4 by speed) and the lake fish (4) already pay a fixed amount and are unchanged"),
            gm.RUNNING)
    # Job step 13 (0x46D057, min(noni, 30) at once) is inherited code nothing in New Believers queues: never listed
    # (the owner: inherited unused things stay off the page).
    crops = _i32(data, CROPS)
    harvest = {gm.FAST: 10, gm.NORMAL: 7, gm.SLOW: 4}[speed]
    add("Food sources", f"Hydroponic Farm crops: {crops:,} of {CROPS_FULL}; a harvest gives {harvest} food on {on} speed "
                        "(10, 7 or 4 on Fast, Normal or Slow; 7 while catching up), before Food Mastery, and takes as "
                        "many crops. Fishing at the lake: 4 food a fish, before Food Mastery.", gm.RUNNING)
    if village.general:      # the lines above carry a save's amounts, which the general page leaves out
        add("Food sources", "A noni pick gives the noni ÷ 100 food (at least 2) and takes as many noni; noni can be "
                            "picked once the granary is built (while catching up, also only once The Hungry Totem is "
                            "solved). A Hydroponic Farm harvest gives 10, 7 or 4 food on Fast, Normal or Slow (7 while "
                            "catching up) and takes as many crops; fishing at the lake gives 4 food a fish; all before "
                            "Food Mastery.", gm.RUNNING)
        add("Refills", f"Noni: +2 every age unit ({life.every_real(UNIT, speed_value)}), up to {NONI_CAP:,} (empty to "
                       f"full in {gm.duration(NONI_CAP // 2 * 60 * speed)} of real-life time).", gm.RUNNING)
    # The food-gain multiplier 0x41EB40: level 2 adds half (rounded down, 0x41EB66), level 3 doubles (0x41EB62).
    def levels(amount: int) -> str:
        return f"{amount} -> {amount + amount // 2} -> {amount * 2}"
    mastery = max(1, [_i32(data, LEVELS + 4 * k) for k in range(5)][FOOD_MASTERY])
    add("Food sources", "Food Mastery (a technology) boosts the food every source brings into storage, at the moment "
                        "it is credited (0x41EB40): level 2 adds half (rounded down), level 3 doubles it. The "
                        "sources' own regrowth (the noni on the bushes, the crops) is not boosted. Each gain at Food "
                        f"Mastery level 1 -> 2 -> 3" + ("" if village.general else f" (this village is at level {mastery})")
                        + ": a noni pick " + ("" if village.general else f"now {levels(max(2, noni // 100))}, ")
                        + f"{levels(2)} at the least; a Hydroponic Farm harvest {levels(10)} on Fast, {levels(7)} on "
                        f"Normal and while catching up, {levels(4)} on Slow; a fish {levels(4)}; a brown mushroom "
                        f"{levels(6)}, a red one {levels(35)}."
                        + gm.flat_pick_mastery(village, FLAT, flat, levels), gm.RUNNING)

    # -- Refills -------------------------------------------------------------------------
    if paused:
        add("Refills", gm.PAUSED_NOTE, gm.RUNNING)
    add("Refills", f"Noni: +2 {life.every_real(UNIT, speed_value)}, up to {NONI_CAP:,} (empty to full in "
                   f"{gm.duration(NONI_CAP // 2 * 60 * speed)} of real-life time); next {due(NONI_NEXT)}.", gm.RUNNING)
    crop_next = "" if not paused and real(CROPS_NEXT) <= village.now else f"; next {due(CROPS_NEXT)}"
    add("Refills", f"Crops: refilled to {CROPS_FULL} {life.every_real(CROP_UNITS * UNIT, speed_value)} (only with the "
                   f"Hydroponic Farm built){crop_next}.", gm.RUNNING)
    add("Refills", "The Hydroponic Farm is " + ("built." if farm else "not built yet."), gm.SAVE)

    # -- Mushrooms / Collectibles --------------------------------------------------------
    # The spawn 0x414622-0x414684: none while paused; rand(6000) < 3 (18 in 32,768), < 6 in fog (weather 4,
    # 0x414633), and a second rand(6000) < 3 while the weather level 0x718EB8 is above 50.  What appears
    # 0x41422C-0x4142CE: a mushroom 30.03% (rand(100) < 30), always while it rains (0x477040) or the weather level
    # is above 20; red 8% (rand(100) < 8), else brown.
    add("Mushrooms", "Each update of the village (none while paused or closed) something appears with a chance of 18 "
                     "in 32,768; in fog 36 in 32,768, and while the weather level is above 50 a second roll of 18 in "
                     "32,768 comes on top. 30% of what appears are mushrooms, and all of it while it rains or the "
                     "weather level is above 20: brown 92% worth 6 food, red (rare) 8% worth 35 (before Food Mastery), "
                     "counted when they reach the food bin. Unpicked, a thing is gone after 1 minute 30 seconds (real time, the "
                     "same at every speed: 90 seconds on the computer's clock, 0x41441B) of "
                     "real-life time.", gm.RUNNING)
    # The Secret City's roll is the same (0x42DD6D..0x42DD98): the owner asked for VV4's to match it (2026-11-08).
    add("Mushrooms", "Apart from fog's doubling, this is exactly The Secret City's timing (3 in 6,000 each update, a "
                     "second 3 in 6,000 above weather strength 50, at most 2 out at once), so New Believers needs no "
                     "\"Collectible Spawn Timing works like VV1-3\" patch.", gm.CODE)
    add("Mushrooms", "That is about one thing a real-life minute at any speed if the village updates about 30 times a "
                     "real-life second; the update rate was not read from the code, so this is an estimate.")
    if village.has(GOLDEN):
        out.extend(gm.golden_lines(GOLDEN, 18.0, speed_value, "about one thing a real-life minute at every speed, 30% "
                                   "of them mushrooms in fair weather"))
    add("Mushrooms", f"Mushrooms found in this village: {_i32(data, MUSHROOMS_FOUND):,}.", gm.SAVE)
    add("Collectibles", "The others are collectibles: 82% common, 13% uncommon, 5% rare. One set of 24 can always "
                        "appear; a second set of 24 only once the Knowing Totem is built (then half from each). A "
                        "piece already found gives +10, 50 or 150 Divine Energy from the first set, +100, 250 or "
                        "1,500 tech points from the second.", gm.RUNNING)
    add("Collectibles", "The Earthquake God Power also drops one (see God powers).", gm.RUNNING)

    # -- Tech points and Divine Energy ---------------------------------------------------
    add("Tech points and effects", f"Tech points: {_i32(data, TECH):,}.", gm.SAVE)
    # Research, job step 19 (0x46DB7B): the divisors 0x46DCDF-0x46DE09, the speed factor 0x41ED20; then
    # rand(owned ÷ 2) more, where owned counts the second set's pieces (ids 0x50-0x67, 0x413F50 at 0x46DE5A), and
    # the fire's +1 (0x46DE7C).  The injury 0x46DC67 is in the same step, after the skill check succeeded.
    add("Tech points and effects", (
        f"Research gives the researcher's Research skill ÷ 11, ÷ 9 or ÷ 7 at Science 1, 2 or 3, "
        f"{'twice that' if speed == gm.FAST else ('0.6 of that' if speed == gm.SLOW else 'as it is')} on {on} "
        "speed (twice on Fast, 0.6 of it on Slow), plus 0 to (half the pieces of the second collectible set owned, "
        "less 1) more, each equally likely (0 to 11 with all 24), and, while the fire burns, 1 more 10.01% of the "
        "time; while catching up ÷ 7, ÷ 7 or ÷ 5 at any speed (see Time away (catch-up)). 2% of successful "
        "research sessions also cost the researcher 0 to 9 health (see Death and graves)."), gm.RUNNING)
    # The bonus 0x46DE5F: 12 with all 24 pieces, else 0 (scripts/build_science_collectibles_complete_features.py).
    if village.has(SCIENCE_SET) is not False:
        add("Tech points and effects", gm.patch_words(village, SCIENCE_SET, "the second collectible set's pieces add "
                                                      "nothing to research until all 24 are found; then 0 to 11 more"))
    # The cap 0x425020-0x4250D0: 5 x (0x4713F0: living believers + the babies they carry + 2); +50 at the statue's
    # stage 1 or more and +50 more at 2 (0x51D950); +100 once The Tribute Statue (puzzle 14) is solved; +50 at
    # Spirituality 2 and +50 more at 3; the first set's pieces owned (ids 0x68-0x7F, 0x413F50 at 0x42509F): below 24
    # it adds 3 x the count (0x4250AE: lea ecx,[eax+esi]; lea esi,[ecx+eax*2]), at 24 a flat 90 instead (0x4250A9:
    # add esi, 0x5A) -- 23 pieces give 69, the 24th jumps it to 90; at most 1,000.
    # Honoring, job step (0x46D88F-0x46D8D7): +3, +4 more at Devotion 50 or more, +5 more at 88 or more.
    add("Tech points and effects", (
        f"Divine Energy: {_i32(data, ENERGY):,} of {_i32(data, ENERGY_CAP):,}."), gm.SAVE)
    add("Tech points and effects", (      # its own line: the general page drops the amounts line above
        f"Divine Energy: each believer adds 1 every age unit ({life.every_real(UNIT, speed_value)}), 4 at Devotion 50 or more, 9 at 88 or more (1 more at 8,000 food on Medium, "
        "or on Hard). Honoring adds 3, 7 at Devotion 50 or more, or 12 at 88 or more, on three Honorings in four, "
        "and on the fourth only if the Devotion check succeeds. The cap is 5 x (believers + the babies they carry + "
        "2), +50 once the Tribute Statue reaches its first stage and +50 more at its second, +100 once The Tribute "
        "Statue is solved, +50 at Spirituality 2 and +50 more at 3, and +3 for each piece of the first collectible "
        "set owned while it is incomplete (69 with 23 pieces), then a flat +90 once all 24 are owned (the 24th "
        "piece adds 21), at most 1,000."), gm.RUNNING)
    out.extend(nursery.lines(village, 5))       # the Nursery School and why children or Heathens gain skills
    out.extend(powers.lines(village))

    # -- Food earned ---------------------------------------------------------------------
    add("Food earned", f"Each believer eats 2 food every age unit ({unit} of real-life time on {on} speed, "
                       f"{2 * 3600 / (60 * speed):g} a real-life hour); how often they eat less at 500 food or less, or 2 more on "
                       "Medium at 8,000 food or more and on Hard, is under Chances. Heathens never eat; a nursing "
                       "mother eats as one believer and her babies nothing.", gm.RUNNING)
    # Hungrier Villagers: both meal immediates x N (scripts/build_hungrier_villagers_features.py).
    if village.has(HUNGRIER) is not False:
        add("Food earned", gm.patch_words(village, HUNGRIER, "each believer's meal, and the difficulty's extra, "
                                        "take 2 to 10 times the food (the slider); food never goes below 0"))
    if village.has(CLASSIC) is not False:
        add("Food earned", gm.patch_words(village, CLASSIC, "it ticks Food Gains are Flat, Hungrier Villagers, 2-10x "
                                         "Tech Cost, Science Collectibles Only Count When Complete and Faith Loss is Doubled/Gains Halved "
                                         "together; each one's own line on this page says what it changes"))

    # -- Time away (catch-up): src/vv_game_mechanics_catchup.py, added by vv_game_mechanics.read -----

    # -- Island events -------------------------------------------------------------------
    add("Island events", "When the next natural island event comes: under Village timers.", gm.SAVE)
    out.extend(events.facts(village))          # the catalog (src/vv_game_mechanics_events_vv5.py)

    # -- Other ---------------------------------------------------------------------------
    for line, ok in HIDDEN_LINES:
        add(gm.HIDDEN, line, ok)
    out.extend(gm.starvation_lines(village, 0x8, gm.RUNNING))
    add("Chance and timers", gm.autosave_line(5), gm.OWNER)
    for line, ok in CHANCE_EXTRA:
        add("Chance and timers", line, ok)
    for line, ok in LIFE_LINES:
        add("Other", line, ok)
    out.append(gm.old_age_line("55, 63 or 71 years (Medicine 1, 2, 3)", "65, 73 or 81 years", "Heathens do not age.",
                               who="believer"))
    # (The age unit at each speed: Vital statistics' Time and units, on the save's page and the general one alike.)
    add("Other", "Ages, pregnancies, noni, crops, weather and the fire follow the speed; mushrooms and collectibles "
                 "appearing, island events, God Power spells and a Heathen's 2-hour wait after preaching run on "
                 "real-life time at any speed.", gm.RUNNING)
    for line, ok in FIRE_LINES:
        add("Other", line, ok)
    for line, ok in PUDDLE_LINES:
        add("Other", line, ok)
    if village.has("vv5_fix_vanilla_bugs") is True:
        add("Other", "With Fix Vanilla Game Bugs: \"Playing in puddles\" spots come from all 1,479 of its "
                     "spots, each equally likely (the picker keeps a uniform sample of every cell, 0x494E80); every "
                     "other walk to an area, fishing and \"Excited about the puddles\" included, picks as stock.",
            gm.CODE)
    if village.has(PUDDLES) is not False:           # patch_words says when that could not be told
        add("Other", "Normally \"Playing in puddles\" stops once The Lake holds water. " + gm.patch_words(
            village, PUDDLES, "with water in the lake the rain still brings it, and each of the five walks goes to a "
                              "random point of the lake's north-west sandy shore, never in the water, between the "
                              "lake's west tip and the rocks with the red flower (0x494E00); before The Lake has "
                              "water, nothing changes"), gm.CODE)
    clock = gm.later_clock(data, CLOCK, base, speed_value, _i32(data, STATS))
    out.append(gm.started_line(clock.created))
    out.extend(f for f in [gm.warp_dates_note(village, "Other", "the village's start date is")] if f)
    names = dict(PUZZLE_NAMES)
    if village.has(HEATHEN_PARENT):
        names[17] = "The Heathen Parent"
    out.extend(gm.later_puzzle_lines(names, lambda pid: struct.unpack_from("<ii", data, PROJECTS + 8 * pid),
                                     PUZZLE_THRESHOLDS, clock))
    out.extend(f for f in [gm.warp_dates_note(village, gm.PUZZLES, "the puzzle dates are")] if f)
    # The Last Heathen's hovel cover: 0x4370E0 draws image 0x1B once project 25 is done, top-left (0x6A9, 0x5B3);
    # Fix Vanilla Bugs moves it to (0x6A6, 0x5B9) and names the owner's picture (tests/test_vv5_hovel_cover.py).
    add(gm.PUZZLES, "The Last Heathen: once it is solved, the game covers the old Heathen camp on the island map with "
                    "the picture hovel_cover.png, its top-left corner at (1705, 1459) (0x4370E0).", gm.CODE)
    out.append(gm.Fact(gm.PUZZLES, gm.patch_words(
        village, "vv5_fix_vanilla_bugs", "the cover is drawn at (1702, 1465), 3 pixels left and 6 lower, where it "
        "meets the map's own tiles, in the owner's redrawn picture vvfp_hovel.png (art by Lorsieab2); the game's own "
        "hovel_cover.png is not changed"), gm.CODE, True))

    # -- The countdowns, and the people and clocks (src/vv_game_mechanics_life.py) ------------
    noni_at = None if paused else real(NONI_NEXT)
    crops_at = None if paused or not farm or real(CROPS_NEXT) <= village.now else real(CROPS_NEXT)
    event_at = None if paused else real(EVENT_NEXT)
    gm.with_due(out, "Noni: +2", noni_at if noni_at and noni_at > village.now else None, "refill")
    gm.with_due(out, "Crops: refilled", crops_at, "refill")
    level = [_i32(data, LEVELS + 4 * k) for k in range(6)]
    mastery = level[FOOD_MASTERY]
    puzzles = []
    for pid, name in names.items():
        progress = _i32(data, PROJECTS + 8 * pid)
        if 0 < progress < PUZZLE_THRESHOLDS[pid]:
            puzzles.append((name, progress, PUZZLE_THRESHOLDS[pid]))
    # Hand of Bloom for food (the owner, 2026-11-08: "The player may cast Hand of Bloom on the noni bush to add
    # fruit, the crop field once the puzzle is solved to instantly refill it, and on the ground to spawn a variety of
    # mushrooms ... take into account god power refill time and divine energy"): 150 Divine Energy a cast
    # (0x498840), no cooldown (0x422E50); the effects src/vv_game_mechanics_powers_vv5.py EFFECTS[4] cites
    # (0x42315F, 0x439EA0, 0x420E5B, 0x420C18); Divine Energy each age unit per believer 1, 4 at Devotion 50 or more,
    # 9 at 88 or more (the life tick, see Tech points and effects).
    energy_now, energy_cap = _i32(data, ENERGY), _i32(data, ENERGY_CAP)
    boost = 2.0 if mastery >= 3 else (1.5 if mastery == 2 else 1.0)

    def bloom_lines(c, members):
        believers = [p for p in members if not p.heathen]
        devotion = [p.skill("Devotion", 5) for p in believers]
        if not believers or any(d is None for d in devotion):
            return []
        # 1 more each on Hard, or on Medium at 8,000 food or more (the life tick; Tech points and effects).
        level = c.difficulty
        extra = 1 if level == 2 or (level == 1 and c.food >= 8000) else 0
        income = sum(9 if d >= 88 else 4 if d >= 50 else 1 for d in devotion) + extra * len(believers)
        out = []
        head = (f"Hand of Bloom for food (cast by the player in live play; 150 Divine Energy a cast, no cooldown): this "
                f"tribe's {len(believers)} believers make about {income:,} Divine Energy each age unit (1 each, 4 at "
                f"Devotion 50 or more, 9 at 88 or more, 1 more on Hard or on Medium at 8,000 food or more"
                + (", as now" if extra else "") + f"; Honoring adds more), now {energy_now:,} of a {energy_cap:,} cap. ")
        if energy_cap < 150:
            return [head + "The cap is below 150, so Hand of Bloom cannot be cast yet."]
        units = 150 / income
        wait = units * c.unit
        per_hour = 3600.0 / wait
        head += (f"One cast's worth comes every {units:,.1f} age units ({gm.duration(wait)} of real-life play on "
                 f"{gm.speed_name(c.speed)} speed), so at most about {per_hour:,.2f} casts per real-life hour, "
                 f"{energy_now // 150:,} castable now. The Divine Energy also builds up while catching up, so casts can "
                 "wait for when the game is played. Each use below takes a whole cast; other powers take from the same "
                 "Divine Energy.")
        out.append(head)
        noni_food = 149.5 * boost
        kept = max(0.0, min(149.5, 1000 - noni))
        out.append(f"On the noni bushes: +100 to +199 noni (about 150) over the next 100 to 199 updates, about "
                   f"{noni_food:,.0f} food once picked (a pick takes as many noni as the food it brings, before Food "
                   f"Mastery); the next +2 growth cuts anything above 1,000 back to 1,000, so unless farmers pick "
                   f"during it a cast keeps at most 1,000 minus the noni there: now {noni:,}, so about {kept:,.0f} noni "
                   f"({kept * boost:,.0f} food) kept" + (" (the whole cast)." if kept >= 149.5 else "."))
        if farm:
            room = max(0, CROPS_FULL - crops)
            out.append(f"On the field (the Hydroponic Farm built): the crops are filled to {CROPS_FULL} at once and their "
                       f"timer starts again, so it adds what is missing, {room:,} crops now, about {room * boost:,.0f} "
                       "food once harvested (a harvest takes as many crops as the food it brings, before Food Mastery); "
                       "best cast when the field is nearly empty.")
        else:
            out.append("On the field: only once the Hydroponic Farm is built (until then the game refuses it and "
                       "nothing is spent).")
        brown, red = 6 * boost, 35 * boost
        out.append(f"On open ground: 17 to 22 plants, each a mushroom half the time while 10 to 12 mushroom places are "
                   f"left, so up to about 10 mushrooms, brown ({brown:g} food) or red ({red:g}) equally likely: about "
                   f"{10 * (brown + red) / 2:,.0f} food a cast if all are picked (children pick them, in live play when "
                   "dropped on them).")
        return out

    # Fishing at the lake needs The Lake restored (project 10, the dispatcher 0x46C600; before it, "Looking for bits
    # of fish", 0x454130): the owner, 2026-11-08: fish never run out once their puzzle is done.
    lake = _i32(data, PROJECTS + 8 * 10) >= PUZZLE_THRESHOLDS[10]
    ctx = life.Context(
        village, speed_value, last, _i32(data, FOOD), low_food=500, extra_from=8000,
        sources=[life.Source("Noni bushes", noni, NONI_CAP, 2.0, noni_at if noni_at and noni_at > village.now else None,
                             f"+2 {life.every_real(UNIT, speed_value)}", verified=gm.SAVE,
                             step=2, interval=gm.real_seconds(UNIT, speed_value), next_at=real(NONI_NEXT),
                             first_in=max(0, _i32(data, NONI_NEXT) - _i32(data, LAST_TICK)), rule=gm.RUNNING),
                 life.Source("Hydroponic Farm crops", crops, CROPS_FULL, CROPS_FULL / CROP_UNITS if farm else 0.0, crops_at,
                             f"refilled to {CROPS_FULL} {life.every_real(CROP_UNITS * UNIT, speed_value)}" if farm
                             else "the Hydroponic Farm is not built yet", verified=gm.SAVE,
                             step=CROPS_FULL if farm else 0, interval=gm.real_seconds(CROP_UNITS * UNIT, speed_value),
                             next_at=real(CROPS_NEXT), first_in=life.resumed(max(0, _i32(data, CROPS_NEXT) - _i32(data, LAST_TICK)), speed_value), rule=gm.RUNNING),
                 ] + ([
                 # The fish step 0x46D790 adds 4 food (0x41EB40) and reads or takes nothing: no store to run out.
                 life.Source("Fishing at the lake", None, unlimited=True,
                             refill_words="it has no store: every fish brings 4 food (before Food Mastery) and "
                                          "nothing runs out",
                             verified=gm.CODE)] if lake else []),
        tech=_i32(data, TECH), tech_words="Research brings them (the skill ÷ 11, ÷ 9 or ÷ 7 at Science 1 to 3).",
        brown=6, red=35, red_share=0.08, mushrooms_an_hour=18.0,
        mastery=2.0 if mastery >= 3 else (1.5 if mastery == 2 else 1.0), golden=village.has(GOLDEN) is True,
        mushroom_words="About one thing appears each real-life minute while playing (not paused; real time, the same "
                       "at every speed), 30% of them mushrooms (all in "
                       "rain), so about 18 mushrooms per real-life hour.",
        event_next=event_at,
        event_paused_left=max(0, _i32(data, EVENT_NEXT) - _i32(data, LAST_TICK)) if paused else None,
        event_rule="It comes 8 to 15 whole real-life hours after the last (15 real-life minutes, then 30, in a new "
                   "village), each equally likely, at any speed; paused time and time away: see Island events.",
        event_running="",                      # said, verified, by the Island events group's Timing line
        medicine=level[MEDICINE_LEVEL], elderly_from={1: 50, 2: 58, 3: 66}, old_age_from={1: 55, 2: 63, 3: 71},
        parents_from=18, sick_loss=(0.61, 0.19),
        collectibles=life.collectible_lines(village, life.COLLECTIBLE_PAY[5])[0],
        limit=life.limit_words(village, None, "up to 15 for collections"),
        puzzles=puzzles,
        food_words="2 food a believer every age unit (Heathens skip it), less at 500 or less and 2 more 76% of the "
                   "time on Medium at 8,000 or more and on Hard (the exact odds: Chances).",
        # With Food Gains are Flat the pick pays FLAT_PICK live and FLAT_CATCH_UP while catching up.
        trips=[("noni picks", (FLAT_PICK.get(speed, 3), FLAT_CATCH_UP) if village.has(FLAT) is True
                else max(2, noni // 100), "Noni bushes"),
               ("crop harvests", harvest if farm else 0, "Hydroponic Farm crops"), ("fish", 4 if lake else 0, "Fishing at the lake")],
        food_extra=bloom_lines)
    out.extend(life.sections(ctx))
    out.extend(death.facts(village, medicine=level[MEDICINE_LEVEL], speed_value=speed_value, base=base))
    out.extend(faith.lines(village))
    return out


# The tech levels: six dwords at manager +0xBC0C (saved by 0x4235B0 from 0x51D5CC); Medicine is the second (the
# twins roll at 0x465EC6), Food Mastery the fifth (the food-gain multiplier 0x41EB4C: x1.5 at level 2, x2 at 3).
LEVELS, MEDICINE_LEVEL, FOOD_MASTERY = 0xBC0C + 0x10, 1, 4


# The game clock 0x51D490, saved by 0x41ECE0 at manager+0x84C (0x42457F) and loaded by 0x41ECC0 (0x42579B); the
# statistics block 0x51D358 (manager+0x7B4), whose first field is the village's start, written from the wall
# clock 0x4036E0 (0x425A19).  The puzzles are the items at PROJECTS (0x51E008, each progress and solve time),
# solved at the threshold each registers with (0x43ABB0), the time stamped by Advance 0x43AF80 from the game
# clock.  The 16 puzzles are ids 1 to 16 (the Village Statistics' count), 17 with the patcher's Heathen Parent
# puzzle; their names are the game's own puzzle tips.
CLOCK, STATS = 0x85C, 0x7C4
HEATHEN_PARENT = "vv5_heathen_mommy_puzzle"
PUZZLE_NAMES = {1: "The Sick Heathen", 2: "The Prison Break", 3: "The Hungry Totem", 4: "The Knowing Totem",
                5: "The Hydroponic Farm", 6: "The Buried Mausoleum", 7: "The Blocking Totem", 8: "The Hollow Totem",
                9: "The Heathen Builder", 10: "The Lake", 11: "The Pain Totem", 12: "The Rainbow Totem",
                13: "The Heathen Scientist", 14: "The Tribute Statue", 15: "The Blind Totem", 16: "The Heathen Chief"}
PUZZLE_THRESHOLDS = {pid: 1 for pid in range(1, 18)} | {5: HYDRO_DONE, 10: 2}
