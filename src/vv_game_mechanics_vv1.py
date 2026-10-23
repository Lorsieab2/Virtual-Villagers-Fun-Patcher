"""Game Mechanics for A New Home (VV1): read-only lines from one save (src/vv_game_mechanics.py).

THE SAVE.  "<base><slot>.ldw" (0xABE8 bytes): "ldwg", the clock's epoch G (Unix seconds), the buffer's
length 0xABDC, then the game state from state+8 on -- so a state offset S is file offset S + 4.  Every
offset below is a FILE offset (little-endian int32).  A clock value v is the real moment G + v: A New
Home's clock counts real seconds, and the speed only sets how long an age unit takes.

  food 0xA2F0, tech points 0xA300, berry bush 0xA2F8, crop field 0xA2FC, speed 0xA31C (3 Fast, 6 Normal,
  10 Slow; + 999 while paused), tech levels Spirituality / Science / Construction / Medicine / Fertility /
  Farming at 0xA2C0 + 8k; the save moment 0xA308, the next regrowth 0xA2F4, the next island event
  0xA304, the village's creation 0x9E20; Mushrooms Found 0x9E34.

THE RULES (static reading of the stock executable; the research notes are in the coordinator's
scratchpad spec, mech_vv1\\spec.md, 2026-10-23):
  * An age unit is 60 x speed real seconds (3 / 6 / 10 minutes); 20 units are a year (the world tick
    0x42E900).
  * Eating: 2 food per villager per unit (0x42ECCC).
  * Regrowth every 40 units (0x42EC0D): the berry bush +30; at Farming level 2 or more the crop field
    +800 up to 800 (0x42F2C5).  Changing speed rescales the time left (0x42E830); pausing freezes the
    timer (0x42E90A).  On load every missed regrowth is applied, without a cap (the 0x42EBF0 loop).
  * A pick from the bush gives bush / 130, at least 2 (0x43AD62); a crop harvest 7 (0x43AEC5); a catch
    9, or at Farming skill 90+ a 21% chance of 55 (0x43F4A7) -- fishing needs Farming level 3 and the
    beach cleaned.
  * Research gives Research / 7, / 5 or / 3 at Science level 1, 2 or 3, after a (Research + 31)% roll
    (0x43B2AB).
  * Mushrooms: while none is out, a 2-in-120 roll every 2 real seconds (0x42351E), so about 2 real
    minutes' wait at any speed; one stays 60 real seconds (0x42352F) at one of 9 spots; 8 food, or 45
    for the 5% big kind (0x43AFEF / 0x43B04C).  Mushrooms are not saved.  A New Home has no collectibles.
  * Island events: after the first two, every 12 to 23 real hours at any speed (0x423886); the timer
    freezes while paused; after an absence at most one fires.
  * Time away (0x42EA62): how much counts is shown only from vv_game_mechanics.AWAY_LIMITS, the verified
    table.  A save left paused gets no catch-up (credit zeroed, 0x42EACE) -- a static reading, not yet
    confirmed in game.
"""
from __future__ import annotations

import struct

import vv_game_mechanics as gm

GAME = 1
LENGTH = 0xABDC
FOOD, TECH, BUSH, FIELD, SPEED = 0xA2F0, 0xA300, 0xA2F8, 0xA2FC, 0xA31C
LEVELS = 0xA2C0
SCIENCE, FARMING = 1, 5                       # the level's index: Spirituality, Science, ... Farming
SAVED, REGROW, EVENT, CREATED = 0xA308, 0xA2F4, 0xA304, 0x9E20
MUSHROOMS_FOUND = 0x9E34
EVENTS_SEEN = 0x9E44                          # the Island Events statistic
UNIT = 360                                    # an age unit, in Normal-speed seconds (60 x 6)
REGROW_UNITS = 40
FIELD_CAP = 800
GOLDEN = "vv1_super_secret_golden_mushroom"
LEARNING = "vv1_learning_never_fails"
MAGIC_FRUIT = "vv1_magic_fruit_alters_mortality"

# The island events, each outcome and its odds, and life -- all verified by emulation (the coordinator's spec
# mech_vv1\spec.md v2, sections 5 and 7).
EVENT_LINES = (
    "Each event is a story event 20% of the time, a village event 40% and a crate or vial 40%; within each kind "
    "every event whose conditions hold is equally likely. The story events and their choices follow (what each "
    "choice does is not yet confirmed).",
    "Story events: Trapped Whale (Spirituality below 3): free it, Spirituality +1 level; harvest it, +1,000 food. "
    "Strange Berries (taste): 51% the villager becomes 12 and a half, 49% death. Old Drum: cut it, Healing 100; "
    "play it, bush +500. Mysterious Face (look): 51% the villager vanishes, 49% a stranger of 14 joins (or the "
    "villager vanishes if there is no room).",
    "Visitor (Medicine below 3): allow, Medicine +1 level; refuse, the villager falls sick and everyone else at "
    "75%. Mysterious Vial, red (drink): 50% everyone else sick, 50% Healing 100. Troubled Child (a child): "
    "farming, Farming +50 and sick; research, Research 100 and +3,000 tech points. Mysterious Vial, blue (drink): "
    "50% the villager becomes 4 years old, 50% nothing.",
    "Suspicious Monkey (a child): scare it, -50 health; wait, Healing +60. Wild Mushroom (taste): 50% Farming +65 "
    "and 300 to 499 food, 50% sick and -25 to -49 health. Black Pearl: share it, everyone +5 to 9 health; keep "
    "it, dislikes crowds and work. The Dream: the right cave, dislikes fish and the ocean; the left, nothing.",
    "The Moth: help it, nothing; leave it, Healing 100. The Book: read it, the villager vanishes; give it to the "
    "researchers, nothing. Brass Compass: mash it, everyone Farming +10 to 19; give it to the researchers, +2,000 "
    "to 4,999 tech points. Skills stop at 100.",
    "Village events (n is a third of the population, 1 to 10): Bad Little Monkey -900n tech points; Plague of "
    "Parrots bush -200n; Plague of Locusts (Farming 2 or more) the field emptied; Measles Epidemic (a child) every "
    "child sick; South Wind -80n from food, bush and field; Heat Wave sets each villager to one of two idle "
    "actions, nothing else; Isola Day and Blessings Day -10 food a villager and a gathering of the village.",
    "Big Wave (the beach cleaned) dirties the beach again; Good Little Monkey +900n tech points; Greedy Little "
    "Monkey +200n food; Barrel O' Babies (room) 1, 2 or 3 children of 3.5 to 4.45 years for n under 5, 5 to 7, 8 or more; North Wind "
    "bush and field +100n; Helpful Honeybees bush +300n.",
    "Crates and vials, 1 in 9 each; small 33%, medium 34%, large 33%: wooden +500/1,000/1,500 food; sealed "
    "+1,000/2,000/3,000 tech; weathered +500/1,000/1,500 tech and each villager sick at 15/20/25%; rotting the "
    "opener sick and -15 health, each villager sick at 20/30/45% with -10/-15/-20 health; watertight 1/2/3 "
    "children of 3.5 to 4.45 years if there is room.",
    "Fruit crate: the opener -40/70/110 health (a large one is fatal); red vial a new head; blue vial one skill "
    "+50/75/100; fizzy vial every skill -30/50/70. Leaving a crate or pouring a vial out does nothing.",
)
# Chance and timers (the coordinator's spec mech_vv1\spec.md, "Chance and timers (complete index)"):
# (line, verified on a traced path).  The full index of every roll is in the claims export.
CHANCE_LINES = (
    ("Every roll that changes play: a mushroom 2 in 120 each 2 seconds with none out, big 5 in 100; the island "
     "event kind and its next time; the event choices; crates and vials; rationing 50%, waste 76%, starving 76%; "
     "health regained 50% (20% for the elderly); falling sick; old age; the scheduler's 66% of nothing; the job "
     "chooser; the food source; skill success and gain; the embrace below 400 food (26%) and conception; twins "
     "7%, triplets 25% of twins; injuries 2%; rest +1 health 50%; an examined hut repaired 70%.", True),
    ("Sick damage (71%, about 22% at 20 health or less), the catch-up embrace (6%) and healing, the big catch "
     "(21%), dislike refusals and the story events' outcomes.", False),
    ("Every frame some map effects are rolled (1 in 20 of 1,000, 3 in 20, 3 in 25,000) depending on the puzzles; "
     "what they draw is not yet worked out, and their rate follows the frame rate.", False),
    ("64 more functions roll the dice (walking, animation, speech, villager creation and others): not individually "
     "worked out.", False),
    ("Timers: an age unit 3, 6 or 10 minutes (aging, eating, sickness, health, pregnancy, birthdays); regrowth 2 "
     "hours, 4 hours or 6 hours 40 minutes, every missed one added on load; island events 30 minutes after the "
     "first, then 12 to 23 hours, at any speed; the 2-second village step; the 40-second idle sweep; a mushroom "
     "lasts 1 minute.", True),
    ("A new village's first island event 15 minutes after it is made; the Golden Child's special action after 36 "
     "hours; the tutorial mushroom 1 minute 40 seconds; step and screen timers.", False),
    ("The game may also save every 10 minutes while playing; this has not been seen in a game.", False),
)
LIFE_LINES = (
    "A baby is born 41 age units after conception. Conception: a roll of 300 at or under Parenting - 50 + 50 x "
    "Fertility level (1, 51 or 101 in 300 at Parenting 0, 50, 100 and Fertility 1); below 400 food only 26% of "
    "embraces get that far. Twins 7% with Fertility 3 or the strange fish; a quarter of twins are triplets, "
    "needing both.",
    "Babies need room: under 15 people always; 15 or more need the first hut, 25 the second, 50 the third; none "
    "at 90. Villagers work from 14 and have children from 18.",
    "Sickness each age unit (14 and older): 1 in 600, 1 in 1,200 or 3 in 10,000 at Medicine 1, 2, 3; past 50, 58 "
    "or 66 years 1.5% more. Children never fall sick. With food and not sick, a villager regains 1 health half the "
    "age units (every one on Easy); past 50, 58 or 66 years 10% (20% on Easy).",
    "Building trips: huts 250, 400 and 600; the beach 75 (each counts 2); the blockage 350; the field 200; digging "
    "800; the ruins 1,000; chiseling 1,350 (the last two half as many at Building 90 or more). Each trip injures 2% "
    "of the time; an examined hut is repaired 70% of the time.",
)

def _i32(data: bytes, at: int) -> int:
    return struct.unpack_from("<i", data, at)[0]


def facts(village: gm.Village) -> list[gm.Fact]:
    data = village.data
    if len(data) != 12 + LENGTH or data[:4] != b"ldwg" or struct.unpack_from("<I", data, 8)[0] != LENGTH:
        return [gm.Fact("Other", f"{village.save.name} could not be read: it is not an A New Home save.")]
    epoch = struct.unpack_from("<I", data, 4)[0]
    speed_value = _i32(data, SPEED)
    if gm.speed_base(speed_value) not in gm.SPEED_NAMES:
        return [gm.Fact("Other", f"{village.save.name} could not be read: its game speed is not one the game "
                                 "writes.")]
    speed = gm.speed_base(speed_value)
    paused = speed_value >= gm.PAUSED
    on = gm.speed_name(speed)
    level = [_i32(data, LEVELS + 8 * k) for k in range(6)]
    saved = epoch + _i32(data, SAVED)

    def real(at: int) -> float:
        return epoch + _i32(data, at)

    def due(at: int) -> str:
        """A timer as a real date -- or, saved paused, how long after unpausing."""
        if paused:
            return f"{gm.duration(max(0, _i32(data, at) - _i32(data, SAVED)))} after it is unpaused"
        return gm.when(real(at)) if real(at) > village.now else f"{gm.when(real(at))} (when the village is next played)"

    out: list[gm.Fact] = []
    add = lambda group, text, ok=False: out.append(gm.Fact(group, text, ok))  # noqa: E731
    farming = level[FARMING]

    # -- Food sources --------------------------------------------------------------------
    add("Food sources", f"Food in storage: {_i32(data, FOOD):,}.", gm.SAVE)
    bush = _i32(data, BUSH)
    add("Food sources", f"Berry bush: {bush:,}; a pick takes {max(2, bush // 130):,} from it now (the bush ÷ 130, at "
                        "least 2).", gm.RUNNING)
    add("Food sources", f"Crop field: {_i32(data, FIELD):,} of {FIELD_CAP}; a harvest gives 7.", gm.RUNNING)
    add("Food sources", "Fishing: 9 a catch, or 55 for a big catch; it needs Farming level 3 and the beach cleaned "
                        f"(Farming is level {farming}).", gm.RUNNING)
    add("Food sources", "A villager with Farming skill 90 or more has a 21% chance of the big catch.")
    add("Food sources", ("Where a farmer goes: at Farming level 1 the bush; at level 2 half the time the bush and "
                         "half the crops (the crops when the bush is under 100); at level 3 with the beach clean fish "
                         "50%, berries 16.5%, crops 16.75%, nothing 16.75% (with a dirty beach berries 33%, crops "
                         f"33.5%, nothing 33.5%). Farming is level {farming}."), gm.RUNNING)

    # -- Refills -------------------------------------------------------------------------
    if paused:
        add("Refills", gm.PAUSED_NOTE, gm.RUNNING)
    add("Refills", f"The berry bush grows 30 {gm.every(REGROW_UNITS * UNIT, speed_value)}"
                   + (f"; the crop field grows 800, up to {FIELD_CAP}, at the same time." if farming >= 2
                      else "; the crop field does not refill below Farming level 2."), gm.RUNNING)
    add("Refills", f"Next regrowth: {due(REGROW)}.", gm.SAVE)
    add("Refills", "Changing the speed rescales the time left.")

    # -- Mushrooms / Collectibles --------------------------------------------------------
    add("Mushrooms", "While none is out, a mushroom appears after about 2 minutes on average, at any speed (even "
                     "while paused), at one of 9 places, and stays 1 minute; it is picked only when you drop a villager on it. It gives 8 food, or 45 for "
                     "the big kind (1 in 20).", gm.RUNNING)
    add("Mushrooms", "Mushrooms are not kept in the save.")
    if village.has(GOLDEN):
        add("Mushrooms", f"The patcher's \"{gm.feature_name(GOLDEN)}\" is in the game: there is a secret to find.")
    add("Mushrooms", f"Mushrooms found in this village: {_i32(data, MUSHROOMS_FOUND):,}.", gm.SAVE)
    add("Collectibles", "A New Home has no collectibles: mushrooms are its only random pickup.", gm.RUNNING)

    # -- Tech points ---------------------------------------------------------------------
    science = level[SCIENCE]
    divisor = {1: 7, 2: 5, 3: 3}.get(science)
    add("Tech points and effects", f"Tech points: {_i32(data, TECH):,}.", gm.SAVE)
    if divisor:
        add("Tech points and effects", (
            f"Research gives the researcher's Research skill ÷ {divisor} (Science is level {science}), after a "
            "(skill + 31)% roll; 2% of tries injure (0 to 9 health)."), gm.RUNNING)
    else:
        add("Tech points and effects", "Research gives no tech points before Science level 1.")
    add("Tech points and effects", "Every job succeeds at (skill + 31)%. A success raises the skill by 10 at 0, by 8 "
                                   "at 10, by 1 at 45; from 46 up by 1 at 26% x (100 - skill)% (14% at 46, 2.6% at "
                                   "90).", gm.RUNNING)
    if village.has(LEARNING) is not False:
        add("Tech points and effects", gm.patch_words(village, LEARNING, "the roll always passes"))

    # -- Food earned ---------------------------------------------------------------------
    add("Food earned", (f"Each villager eats 2 food every {gm.duration(60 * speed)} on {on} speed "
                        f"({2 * 3600 / (60 * speed):g} an hour); on Medium above 2,000 food, or on Hard, 2 more 76% of "
                        "the time; never on Easy. At 200 food or less a villager skips the meal half the time and "
                        "loses 1 health."), gm.RUNNING)
    add("Food earned", "With no food, a villager loses 1 health 76% of age units (every one on Hard).")

    # -- Time away and Time Warp ---------------------------------------------------------
    out.extend(gm.time_away(village, saved, speed_value,
                            "Saved paused: the time away is not counted when it is next played, and the regrowth and "
                            "island event timers move on with the paused time.", unit_seconds=20 * 60 * speed))
    for n, fact in enumerate(out):
        if fact.text.startswith("Saved paused:"):
            out[n] = gm.Fact(fact.group, fact.text, gm.RUNNING)             # verified (spec v2, section 1 and 8)
    add("Time away and Time Warp", "While catching up, an adult more than 2 age units behind tries 5 jobs for every "
                                   "counted age unit.", gm.RUNNING)
    add("Time away and Time Warp", "Every regrowth missed while the game was closed is added when it is next played, "
                                   "with no limit on how many: the bush has no cap, the crop field stops at 800.", gm.RUNNING)
    out.append(gm.time_warp_line(speed_value))

    # -- Island events -------------------------------------------------------------------
    first = (" The first is always a story event, the second 30 minutes later;"
             if _i32(data, EVENTS_SEEN) < 2 else "")
    add("Island events", f"Next island event: {due(EVENT)}.", gm.SAVE)
    add("Island events", f"{first} Island events come every 12 to 23 whole hours, "
                         "each equally likely, at any speed. Paused, the timer waits; after time away at most one "
                         "happens.", gm.RUNNING)
    for n, line in enumerate(EVENT_LINES):
        # Which event is picked is V; the story events' choice outcomes (lines 1 to 4) are not (spec v3, section 7).
        add("Island events", line, False if 1 <= n <= 4 else gm.RUNNING)

    # -- Other ---------------------------------------------------------------------------
    for line, ok in CHANCE_LINES:
        add("Chance and timers", line, gm.RUNNING if ok else False)
    for line in LIFE_LINES:
        add("Other", line, gm.RUNNING)
    out.append(gm.old_age_line("55, 63 or 71 years (Medicine 1, 2, 3)",
                               "The Golden Child does not age. " + gm.patch_words(
                                   village, MAGIC_FRUIT, "with its puzzle done, the rolls start 7 years later")))
    add("Other", (f"An age unit is {gm.duration(60 * speed)} and a year {gm.duration(20 * 60 * speed)} on {on} speed: "
                  "ages, pregnancies and regrowth follow the speed; work, mushrooms and island events do not."), gm.RUNNING)
    add("Other", f"The village was started at {gm.when(real(CREATED))}.", gm.SAVE)
    return out
