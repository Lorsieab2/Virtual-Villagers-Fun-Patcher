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

# (line, verified)
EVENT_LINES = (
    ("Which event: every event whose conditions hold at that moment is equally likely (1 in the number of them); "
     "if none qualifies, nothing happens.", gm.RUNNING),
    ("Rescue: with the sexes out of balance or fewer than 3 believers, 6% of events become Chutes Without Ladders "
     "instead.", gm.RUNNING),
    ("Always possible: Creeping Mold, Allergy Season, Isola Day, the four Footprints events (food gained, food lost, "
     "tech gained, tech lost), Blessings Day, Strange Crystals, Especially Offensive Cloud, Spicy Juice, Clumsy "
     "Heathen, Salty Air and News From Another Tribe (a message).", False),
    ("Day of Honor needs 2 or more graves. Vision, Mask, Doubt, Aphids in the Noni Bush, Straw Hat and Daredevil "
     "Jump need a believer; Bed Bugs a believer who is not pregnant; Strange Nectar a believer of 18 or more. Cold "
     "Snap needs the fire burning. Army Ants, Aphid Infestation and River Breaks Its Banks need the Hydroponic "
     "Farm; Pesky Critter the Knowing Totem. Advanced Artifacts needs Science exactly level 2; Trick Or Trade 100 "
     "food or more.", False),
    ("Mushroom Day needs a believer child; Migrating Fruit Bats also Food Mastery below 2; Innovation in Farming "
     "also the Heathen Scientist. Heathen Toy, Spying on the Heathens and Missing Kids need a believer child and a "
     "healthy heathen child. Spa and Cracked Mask need a believer and a healthy heathen child; You're Doing It "
     "Wrong! an adult believer, a heathen child and Science below 2; Outreach? an adult believer and a healthy "
     "adult heathen; Defector a healthy heathen. The Barrel O' Babies events, Chutes Without Ladders and News "
     "From Another Tribe (a newcomer) need room for more villagers.", False),
    ("Rolled results: You're Doing It Wrong! (teach them), Advanced Artifacts (independent report) and Defector "
     "(accept) are 50/50.", gm.RUNNING),
    ("Vision faith +20 to +39; Strange Crystals +2,000 to 2,999 tech points; Pesky Critter -500 to -2,999 tech "
     "points; Mushroom Day +50 to 99 food and -500 to -1,499 tech points.", False),
    ("Heathen Toy +20 to 29 Research or Devotion; Cracked Mask (fix it) -20 to 30 health; Barrels and Chutes up to "
     "3 ten-year-olds, each 50% a boy, with one random skill at 5 to 9 (a heathen barrel's babies start at faith "
     "-55); a newcomer is 18, 50% a man, with a random skill at 80 to 84.", False),
)
LIFE_LINES = (
    ("Sickness each age unit: 0.28%, 0.16% or 0.06% at Medicine 1, 2 or 3, 1.5% more from 50, 58 or 66 years; on "
     "Easy a quarter of that.", gm.RUNNING),
    ("A believer who is not sick regains 1 health half the age units, 75% while the fire burns, every one at "
     "Medicine 3 or on Easy; old villagers a fifth of that. At 500 food or less a believer loses 1 health 15% of "
     "age units.", gm.RUNNING),
    ("Belief each age unit: down 37% with food under 10, 10% at 250 or less, 15% when sick, (12 - believers)% "
     "under 12 believers; up 20% at 8,000 food or more, 30% with the Idol, 10% or 20% at statue stage 1 or 2, "
     "10/20/30% at Spirituality 1/2/3, (believers ÷ 5)% at 12 or more. A drop is skipped half the time below "
     "belief 5, a rise 70% of the time above 75.", gm.RUNNING),
    ("A believer turns heathen at belief 0 or less; a new villager's starting faith is 30 to 59.", False),
    ("Conception after an embrace: (Breeding - 50 + 50 x Medicine level + 1) in 300 (17%, 33% or 50% at Breeding "
     "50); the village's first is certain; a mother of 50 or more never conceives. At Medicine 3: 93% single, "
     "5.3% twins, 1.8% triplets.", gm.RUNNING),
    ("A job succeeds at skill + 33 out of 100 (+ 66 if they like learning, + 16 if they dislike it), + 15 or + 30 "
     "at Learning level 2 or 3.", gm.RUNNING),
)


# Hidden villager stats (the coordinator's specs hidden_vv5\spec.md and likes_all, 2026-10-23):
# (line, what stands behind it -- gm.RUNNING, gm.OWNER, or False for UNCONFIRMED).
HIDDEN_LINES = (
    ("Each villager's hidden name number (1 to 183, not inherited; a name always has the same one) sets how it "
     "starves; the villagers' numbers are below.", gm.RUNNING),
    ("Preaching to a heathen: the preacher's Devotion check (35% at Devotion 0, 83% at 50, sure at 88) gives "
     'the heathen 3 belief, 4 at Devotion 50, 5 at 88; then that heathen cannot be preached to for 2 hours '
     '(the 800-energy God Power sets the same wait).', gm.RUNNING),
    ('Liking learning makes a skill check succeed at skill + 66% instead of + 33% (+ 15 or + 30 at Learning 2 '
     'or 3); disliking it, + 16%. A success gains (70 - skill) ÷ 18 (Parenting ÷ 10, Healing ÷ 12), at least 7 '
     'at skill 0, doubled when liked and halved when disliked.', gm.RUNNING),
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
    ('Plants and lifting, and the other 53 likes and dislikes: no effect has been found in the running game.',
     False),
    ('Sick: -1 health on 61% of age units, 19% at 20 health or less. Health comes back on half the age units, '
     '75% while the fire burns, every one at Medicine 3 or on Easy; old villagers a fifth of that. With food '
     'at 500 or less, -1 health 15% of age units.', gm.RUNNING),
    ('The fire (the 100-energy God Power on a built fire pit) burns 10, 20 or 33 hours 20 minutes on Fast, '
     'Normal or Slow, stops while paused and is rescaled when the speed changes; while it burns a research '
     'success gives 1 more tech point 10% of the time.', gm.RUNNING),
)
CHANCE_EXTRA = (
    ('104 rolls are verified: every one in the groups above.', gm.RUNNING),
    ('About 2,250 more rolls (where villagers walk, how long they wait or animate, sounds and voices, pickers, '
     'God Power side effects, child and leisure choices): not individually worked out.', False),
    ('Spreading the Word gives a random heathen 30 belief and marks them for 2 hours; the Earthquake marks '
     'every heathen the same way.', False),
    ('Timers: an age unit 3, 6 or 10 minutes; noni +2 at the same pace; crops every 2 hours, 4 hours or 6 '
     'hours 40 minutes; the next island event 15 minutes, then 30 minutes, then 8 to 15 hours; weather 1.5 to '
     "3, 3 to 6 or 5 to 10 minutes; each villager's catch-up stamp.", gm.RUNNING),
    ('God Power spells run on their own clock that ignores pausing: Fog of Doom 2 minutes, Time Warp 5 '
     "minutes, Reanimate 4 seconds, the Earthquake's drop after 10 seconds; an item lies 1 minute 30 seconds; "
     'puzzle and on-screen timers of 5 seconds to 2 minutes.', False),
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
    add("Food sources", f"Noni bushes: {noni:,} of {NONI_CAP:,}; a pick gives {max(2, noni // 100)} food now (the noni "
                        f"÷ 100, at least 2), and takes as many noni.", gm.RUNNING)
    add("Food sources", f"A noni gathering would bring {min(noni, 30)} (up to 30); nothing in the game was found to start "
                        "one.")
    add("Food sources", "Noni can be picked once the granary is built.")
    crops = _i32(data, CROPS)
    harvest = {gm.FAST: 10, gm.NORMAL: 7, gm.SLOW: 4}[speed]
    add("Food sources", f"Hydroponic Farm crops: {crops:,} of {CROPS_FULL}; a harvest gives {harvest} food on {on} speed "
                        "(7 while catching up) and takes as many crops. Fishing at the lake: 4 food a fish.", gm.RUNNING)
    add("Food sources", "Food Mastery raises every food gain by half (level 2) or doubles it (level 3).", gm.RUNNING)

    # -- Refills -------------------------------------------------------------------------
    if paused:
        add("Refills", gm.PAUSED_NOTE, gm.RUNNING)
    add("Refills", f"Noni: +2 {gm.every(UNIT, speed_value)}, up to {NONI_CAP:,} (empty to full in "
                   f"{gm.duration(NONI_CAP // 2 * 60 * speed)}); next {due(NONI_NEXT)}.", gm.RUNNING)
    crop_next = "" if not paused and real(CROPS_NEXT) <= village.now else f"; next {due(CROPS_NEXT)}"
    add("Refills", f"Crops: refilled to {CROPS_FULL} {gm.every(CROP_UNITS * UNIT, speed_value)} once the Hydroponic "
                   f"Farm is built{crop_next}.", gm.RUNNING)
    add("Refills", "The Hydroponic Farm is " + ("built." if farm else "not built yet."))

    # -- Mushrooms / Collectibles --------------------------------------------------------
    add("Mushrooms", "Each update of the village, something appears with a chance of 18 in 32,768, twice in some "
                     "weather; none while paused or closed. 30% are mushrooms (all of them in the rain): brown 92% "
                     "worth 6 food, red (rare) 8% worth 35, counted when they reach the food bin. Unpicked, a thing is gone "
                     "after 1 minute 30 seconds.", gm.RUNNING)
    add("Mushrooms", "That is about one thing a minute, at any speed.")
    if village.has(GOLDEN):
        add("Mushrooms", gm.golden_line(GOLDEN, "about 6 years of play"), gm.RUNNING)
    add("Mushrooms", f"Mushrooms found in this village: {_i32(data, MUSHROOMS_FOUND):,}.", gm.SAVE)
    add("Collectibles", "The others are collectibles: 82% common, 13% uncommon, 5% rare. One set of 24 can always "
                        "appear; a second set of 24 only once the Knowing Totem is built (then half from each). A "
                        "piece already found gives +10, 50 or 150 Divine Energy from the first set, +100, 250 or "
                        "1,500 tech points from the second.", gm.RUNNING)
    add("Collectibles", "The Earthquake God Power drops one collectible 10 real-life seconds after it is cast: 72% "
                        "uncommon, 28% rare (see God powers).", gm.RUNNING)

    # -- Tech points and Divine Energy ---------------------------------------------------
    add("Tech points and effects", f"Tech points: {_i32(data, TECH):,}.", gm.SAVE)
    add("Tech points and effects", (
        f"Research gives the researcher's skill ÷ 11, ÷ 9 or ÷ 7 at Science 1, 2 or 3, "
        f"{'twice that' if speed == gm.FAST else ('0.6 of that' if speed == gm.SLOW else 'as it is')} on {on} "
        "speed, plus up to half the lab's items and, while the fire burns, 1 more 10% of the time; while catching "
        "up ÷ 7, ÷ 7 or ÷ 5. In play 2% of tries injure (0 to 9 health)."), gm.RUNNING)
    add("Tech points and effects", "While catching up, nobody researches before the Knowing Totem is built, and "
                                   "nobody picks noni before the Hungry Totem.")
    if village.has(LEARNING) is not False:
        add("Tech points and effects", gm.patch_words(village, LEARNING, "learning never fails"))
    add("Tech points and effects", (
        f"Divine Energy: {_i32(data, ENERGY):,} of {_i32(data, ENERGY_CAP):,}. Each believer adds 1 "
        f"{gm.every(UNIT, speed_value)}, 4 at Devotion 50 or more, 9 at 88 or more (1 more at 8,000 food on Medium, "
        "or on Hard). Honoring adds 3, 7 or 12 on three Honorings in four, and on the fourth only if the Devotion "
        "check succeeds. The cap is 5 x (believers + 2), more with the statue, the Idol, "
        "Spirituality and the first set's pieces, at most 1,000."), gm.RUNNING)
    out.extend(powers.lines(village))

    # -- Food earned ---------------------------------------------------------------------
    add("Food earned", f"Each believer eats 2 food every {unit} on {on} speed ({2 * 3600 / (60 * speed):g} an hour); at "
                       "500 food or less only half the time; on Medium at 8,000 food or more, or on Hard, 2 more 76% "
                       "of the time; never on Easy. Heathens skip it.", gm.RUNNING)

    # -- Time away and Time Warp ---------------------------------------------------------
    out.extend(gm.time_away(village, last, speed_value,
                            "Saved paused: the time away is not counted when it is next played; nothing ages, grows "
                            "or comes due.", unit_seconds=20 * 60 * speed))
    for n, fact in enumerate(out):
        if fact.text.startswith("Saved paused:"):
            out[n] = gm.Fact(fact.group, fact.text, gm.RUNNING)
    add("Time away and Time Warp", "While catching up, each counted age unit runs the believers' life (eating, belief, "
                                   "Divine Energy, sickness, births) and 4 jobs: crops 7 food, research ÷ 7, ÷ 7 or "
                                   "÷ 5, no lab mishaps.", gm.RUNNING)
    add("Time away and Time Warp", "Every noni growth and crop refill missed while the game was closed is added when "
                                   "it is next played, with no limit on how many: noni stop at 1,000, crops at 800.",
        True)
    add("Time away and Time Warp", "Heathens never age, while catching up or otherwise (the stock game's design).", gm.OWNER)
    out.append(gm.time_warp_line(speed_value))

    # -- Island events -------------------------------------------------------------------
    first = (" The first comes 15 minutes after the village is made and the next 30 minutes after it;"
             if _i32(data, EVENTS_SEEN) == 0 else "")
    add("Island events", f"Next island event: {due(EVENT_NEXT)}.", gm.SAVE)
    add("Island events", f"{first} Island events come every 8 to 15 whole hours, "
                         "each equally likely, at any speed; paused time does not count.", gm.RUNNING)
    for line, ok in EVENT_LINES:
        add("Island events", line, ok)
    weather = {gm.FAST: "1.5 to 3", gm.NORMAL: "3 to 6", gm.SLOW: "5 to 10"}[speed]
    add("Island events", f"Weather events last {weather} minutes on {on} speed.", gm.RUNNING)
    if village.has(STORY) is not False:
        add("Island events", gm.patch_words(village, STORY, "Pick Island Event chooses the event"))

    # -- Other ---------------------------------------------------------------------------
    for line, ok in HIDDEN_LINES:
        add(gm.HIDDEN, line, ok)
    out.extend(gm.starvation_lines(village, 0x8, gm.RUNNING))
    for line, ok in CHANCE_EXTRA:
        add("Chance and timers", line, ok)
    for line, ok in LIFE_LINES:
        add("Other", line, ok)
    out.append(gm.old_age_line("55, 63 or 71 years (Medicine 1, 2, 3)", "Heathens do not age."))
    add("Other", f"An age unit is {unit} and a year {gm.duration(20 * 60 * speed)} on {on} speed: ages, pregnancies, "
                 "noni, crops, weather and the fire follow the speed; mushrooms, collectibles and island events do "
                 "not.", gm.RUNNING)
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
                 life.Source("Fishing at the lake", None, unlimited=True,
                             refill_words="no store of its own is read here: it brings what the gatherers fetch",
                             verified=False)],
        tech=_i32(data, TECH), tech_words="Research brings them (the skill ÷ 11, ÷ 9 or ÷ 7 at Science 1 to 3).",
        brown=6, red=35, red_share=0.08, mushrooms_an_hour=18.0,
        mastery=2.0 if mastery >= 3 else (1.5 if mastery == 2 else 1.0), golden=village.has(GOLDEN) is True,
        mushroom_words="About one thing appears each real-life minute while playing, 30% of them mushrooms (all in "
                       "rain), so about 18 mushrooms per real-life hour.",
        event_next=event_at,
        event_paused_left=max(0, _i32(data, EVENT_NEXT) - _i32(data, LAST_TICK)) if paused else None,
        event_rule="It comes 8 to 15 whole real-life hours after the last (15 real-life minutes, then 30, in a new "
                   "village), each equally "
                   "likely, at any speed; then every event whose conditions hold is equally likely.",
        event_running="Paused time does not count; with the game closed it runs on, and after time away the due "
                      "event happens once.",
        medicine=level[MEDICINE_LEVEL], elderly_from={1: 50, 2: 58, 3: 66}, old_age_from={1: 55, 2: 63, 3: 71},
        parents_from=18, sick_loss=(0.61, 0.19),
        collectibles=life.collectible_lines(village, "10, 50 or 150 Divine Energy (the first set) or 100, 250 or "
                                                     "1,500 tech points (the second)")[0],
        limit=life.limit_words(village, None, "up to 15 for collections"),
        puzzles=puzzles,
        food_words="2 food a believer every age unit (Heathens skip it); at 500 or less only half the time; on "
                   "Medium at 8,000 or more, or on Hard, 2 more 76% of the time; never more on Easy.",
        trips=[("noni picks", max(2, noni // 100)), ("crop harvests", harvest if farm else 0), ("fish", 4)])
    out.extend(life.sections(ctx))
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
