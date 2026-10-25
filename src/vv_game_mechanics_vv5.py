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
LEARNING = "vv5_learning_never_fails"

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
     'out of the rain 98.7% of the time. Running: liked, a walk at speed 300 (150 otherwise); disliked, 40, '
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
    # Job step 13 (0x46D057) takes min(noni, 30) at once; no job or event that queues it was found.
    add("Food sources", f"The job code also has a noni gathering that would bring {min(noni, 30)} at once (the noni, "
                        "up to 30; step 13 at 0x46D057), but no job or event that uses it was found, so whether it can "
                        "ever happen is not proven.")
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
    add("Food sources", "Food Mastery raises every food gain by half (level 2) or doubles it (level 3).", gm.RUNNING)

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
                     "counted when they reach the food bin. Unpicked, a thing is gone after 1 minute 30 seconds of "
                     "real-life time.", gm.RUNNING)
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
    out.extend(powers.lines(village))

    # -- Food earned ---------------------------------------------------------------------
    add("Food earned", f"Each believer eats 2 food every age unit ({unit} of real-life time on {on} speed, "
                       f"{2 * 3600 / (60 * speed):g} a real-life hour); how often they eat less at 500 food or less, or 2 more on "
                       "Medium at 8,000 food or more and on Hard, is under Chances. Heathens never eat; a nursing "
                       "mother eats as one believer and her babies nothing.", gm.RUNNING)

    # -- Time away (catch-up): src/vv_game_mechanics_catchup.py, added by vv_game_mechanics.read -----

    # -- Island events -------------------------------------------------------------------
    add("Island events", f"Next island event: {due(EVENT_NEXT)}.", gm.SAVE)
    out.extend(events.facts(village))          # the catalog (src/vv_game_mechanics_events_vv5.py)

    # -- Other ---------------------------------------------------------------------------
    for line, ok in HIDDEN_LINES:
        add(gm.HIDDEN, line, ok)
    out.extend(gm.starvation_lines(village, 0x8, gm.RUNNING))
    for line, ok in CHANCE_EXTRA:
        add("Chance and timers", line, ok)
    for line, ok in LIFE_LINES:
        add("Other", line, ok)
    out.append(gm.old_age_line("55, 63 or 71 years (Medicine 1, 2, 3)", "Heathens do not age."))
    if village.general:      # a save's page says it under Vital statistics ("Time and units")
        add("Other", f"Time and units: an age unit is {unit} of real-life time and a villager year (20 age units) "
                     f"{gm.duration(20 * 60 * speed)} on {on} speed (an age unit is 3, 6 or 10 real-life minutes on "
                     "Fast, Normal or Slow).", gm.RUNNING)
    add("Other", "Ages, pregnancies, noni, crops, weather and the fire follow the speed; mushrooms and collectibles "
                 "appearing, island events, God Power spells and a Heathen's 2-hour wait after preaching run on "
                 "real-life time at any speed.", gm.RUNNING)
    for line, ok in FIRE_LINES:
        add("Other", line, ok)
    clock = gm.later_clock(data, CLOCK, base, speed_value, _i32(data, STATS))
    out.append(gm.started_line(clock.created))
    names = dict(PUZZLE_NAMES)
    if village.has(HEATHEN_PARENT):
        names[17] = "The Heathen Parent"
    out.extend(gm.later_puzzle_lines(names, lambda pid: struct.unpack_from("<ii", data, PROJECTS + 8 * pid),
                                     PUZZLE_THRESHOLDS, clock))

    # -- The countdowns, and the people and clocks (src/vv_game_mechanics_life.py) ------------
    noni_at = None if paused else real(NONI_NEXT)
    crops_at = None if paused or not farm or real(CROPS_NEXT) <= village.now else real(CROPS_NEXT)
    event_at = None if paused else real(EVENT_NEXT)
    gm.with_due(out, "Noni: +2", noni_at if noni_at and noni_at > village.now else None, "refill")
    gm.with_due(out, "Crops: refilled", crops_at, "refill")
    gm.with_due(out, "Next island event:", event_at, "next")
    level = [_i32(data, LEVELS + 4 * k) for k in range(6)]
    mastery = level[FOOD_MASTERY]
    puzzles = []
    for pid, name in names.items():
        progress = _i32(data, PROJECTS + 8 * pid)
        if 0 < progress < PUZZLE_THRESHOLDS[pid]:
            puzzles.append((name, progress, PUZZLE_THRESHOLDS[pid]))
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
                 # The fish step 0x46D790 adds 4 food (0x41EB40) and reads or takes nothing: no store to run out.
                 life.Source("Fishing at the lake", None, unlimited=True,
                             refill_words="it has no store: every fish brings 4 food (before Food Mastery) and "
                                          "nothing runs out",
                             verified=gm.CODE)],
        tech=_i32(data, TECH), tech_words="Research brings them (the skill ÷ 11, ÷ 9 or ÷ 7 at Science 1 to 3).",
        brown=6, red=35, red_share=0.08, mushrooms_an_hour=18.0,
        mastery=2.0 if mastery >= 3 else (1.5 if mastery == 2 else 1.0), golden=village.has(GOLDEN) is True,
        mushroom_words="About one thing appears each real-life minute while playing, 30% of them mushrooms (all in "
                       "rain), so about 18 mushrooms per real-life hour.",
        event_next=event_at,
        event_paused_left=max(0, _i32(data, EVENT_NEXT) - _i32(data, LAST_TICK)) if paused else None,
        event_rule="It comes 8 to 15 whole real-life hours after the last (15 real-life minutes, then 30, in a new "
                   "village), each equally likely, at any speed; paused time and time away: see Island events.",
        event_running="",                      # said, verified, by the Island events group's Timing line
        medicine=level[MEDICINE_LEVEL], elderly_from={1: 50, 2: 58, 3: 66}, old_age_from={1: 55, 2: 63, 3: 71},
        parents_from=18, sick_loss=(0.61, 0.19),
        collectibles=life.collectible_lines(village, "10, 50 or 150 Divine Energy (the first set) or 100, 250 or "
                                                     "1,500 tech points (the second)")[0],
        limit=life.limit_words(village, None, "up to 15 for collections"),
        puzzles=puzzles,
        food_words="2 food a believer every age unit (Heathens skip it), less at 500 or less and 2 more 76% of the "
                   "time on Medium at 8,000 or more and on Hard (the exact odds: Chances).",
        trips=[("noni picks", max(2, noni // 100)), ("crop harvests", harvest if farm else 0), ("fish", 4)])
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
