"""Game Mechanics for The Tree of Life (VV4): read-only lines from one save (src/vv_game_mechanics.py).

THE SAVE.  A 24-byte header -- "ldwg", ..., the clock's base as an int64 Unix time at 0x08 -- then the
game state: state field X is file offset X + 0x10.  The clock counts real seconds from the base, so a
stamp v is the real moment base + v.  FILE offsets: speed 0x17120 (3 Fast, 6 Normal, 10 Slow; + 999
paused), the last world tick 0x17100, the next world tick 0x170F4, food 0x85C, tech points 0xBCD0, tech
levels 0xBCB8 (index 0 drives research, index 4 is Food Mastery), Mushrooms Found 0x874, island events
seen 0x884, blackberries 0x17108, the next island event 0x170F0.

THE RULES (static reading of the stock executable; the coordinator's scratchpad spec mech_vv4\\spec.md,
2026-10-23 -- what it could not trace is said to be not yet worked out, what it inferred is marked
uncertain):
  * The world tick runs every 60 x speed real seconds; overdue ticks all run on return; paused time is
    not counted (0x420330).  Each tick: blackberries +2 up to 1000; stream debris +2% up to 100%.
  * Food Mastery: level 2 adds half, level 3 doubles every food gain (0x41D920).  Gathering 11 / 8 / 5
    on Fast / Normal / Slow (8 while catching up); a blackberry pick max(2, berries / 100); fishing 4,
    a Golden Fish 8 at (2 x scales + 1)% ; mushrooms 6 or 35.
  * Research: skill / 11, / 9, / 7 at level 1, 2, 3, x 2 on Fast, x 0.6 on Slow (uncertain); while
    catching up / 7, / 7, / 5.  A duplicate collectible 100 / 250 / 1500 tech points (0x414410).
  * Island events: 8 to 15 whole hours after the last (30 minutes after the first), at any speed; one
    picked uniformly among the eligible (0x418000); at most one after time away.
"""
from __future__ import annotations

import struct

import vv_game_mechanics as gm
import vv_save_backup

GAME = 4
SPEED, LAST_TICK, NEXT_TICK = 0x17120, 0x17100, 0x170F4
FOOD, TECH, LEVELS = 0x85C, 0xBCD0, 0xBCB8
MUSHROOMS_FOUND, EVENTS_SEEN = 0x874, 0x884
BERRIES, EVENT_NEXT = 0x17108, 0x170F0
RESEARCH, FOOD_MASTERY = 0, 4
BERRY_CAP = 1000
UNSURE = "(uncertain)"
NOT_YET = "not yet worked out"
GOLDEN = "vv4_super_secret_golden_mushroom"
LEARNING = "vv4_learning_never_fails"
SCALES = "vv4_complete_scales_golden_fish"
STORY = "vv4_story_cheat_upgrades"

EVENT_LINES = (
    "Which event: every event whose conditions hold is equally likely (1 in the number of them); at most one "
    "happens after time away.",
    "Always possible: Creeping Mold, Allergy Season, Isola Day, the four Mysterious Fog events (food gained, "
    "food lost, tech gained, tech lost), Blessings Day, Rainy Season, Monsoon, Stinging Wasps and Pure Sea Air.",
    "With a suitable villager (most need one of 14 or more): A Closer Look, Arc of Colors, Robber Crab, "
    "Phosphorescent Fungi, Abandoned Infants, Pink Shell, Calabash, Climber, Mosquito Larvae, Faces in the "
    "Night, Screaming Baby, Sealed Box, Wet Book, The Lie, Aspiring Doctor (6 kinds), Aspiring Scientist, "
    "Innovation in Construction, Innovation in Farming, Child in the Tree, Pretty Shell, Biggles Pays a Visit.",
    "Day of Honor needs 2 graves; Banyan Festival 500 mushrooms found and 3 tree stages; Village & Tree Malaise "
    "fewer than 3 stages, Euphoria 3 or more; Daredevil Barrel room for more villagers, the stream restored and "
    f"some debris; Cold Snap a condition {NOT_YET}.",
    f"Rescue {UNSURE}: with too few of one sex or fewer than 3 villagers, a 6% chance of Daredevil Barrel instead.",
    f"Several events then roll 50% or 60% for their result; the odds of each outcome are {NOT_YET}.",
)


def _i32(data: bytes, at: int) -> int:
    return struct.unpack_from("<i", data, at)[0]


def facts(village: gm.Village) -> list[gm.Fact]:
    data = village.data
    found = vv_save_backup.save_speed(GAME, data)
    if found is not None and found[0] != SPEED:
        return [gm.Fact("Other", f"{village.save.name} could not be read: it is in the older Tree of Life save "
                                 "layout, which this page does not read.")]
    if found is None:
        return [gm.Fact("Other", f"{village.save.name} could not be read: it is not a Tree of Life save.")]
    base = struct.unpack_from("<q", data, 8)[0]
    speed_value = found[1]
    speed = gm.speed_base(speed_value)
    paused = speed_value >= gm.PAUSED
    on = gm.speed_name(speed)
    level = [_i32(data, LEVELS + 4 * k) for k in range(6)]
    mastery = level[FOOD_MASTERY]

    def real(at: int) -> float:
        return base + _i32(data, at)

    def due(at: int) -> str:
        if paused:
            return f"{gm.duration(max(0, _i32(data, at) - _i32(data, LAST_TICK)))} after it is unpaused"
        return gm.when(real(at)) + (" (when the village is next played)" if real(at) <= village.now else "")

    def food(amount: int) -> int:
        return amount * 2 if mastery >= 3 else (amount + amount // 2 if mastery == 2 else amount)

    out: list[gm.Fact] = []
    add = lambda group, text: out.append(gm.Fact(group, text))  # noqa: E731
    gather = {gm.FAST: 11, gm.NORMAL: 8, gm.SLOW: 5}[speed]
    mastery_words = {2: " (Food Mastery level 2: half as much again)", 3: " (Food Mastery level 3: doubled)"}.get(
        mastery, "")

    add("Food sources", f"Food in storage: {_i32(data, FOOD):,}.")
    berries = _i32(data, BERRIES)
    add("Food sources", f"Blackberries: {berries:,} of {BERRY_CAP:,}; a pick brings {food(max(2, berries // 100))} food "
                        f"now{mastery_words} (the berries ÷ 100, at least 2); picking stops below 3.")
    add("Food sources", f"Gathering brings {food(gather)} food on {on} speed ({food(8)} while catching up){mastery_words}.")
    add("Food sources", f"Fishing (once fishing is restored) brings {food(4)} a fish, or {food(8)} for a Golden Fish: a "
                        "(2 x fish scales collected + 1)% chance with at least 1 scale (3% with 1, 25% with 12). "
                        + gm.patch_words(village, SCALES, "a Golden Fish needs all 12 scales"))

    if paused:
        add("Refills", gm.PAUSED_NOTE)
    add("Refills", f"Blackberries: +2 {gm.every(360, speed_value)}, up to {BERRY_CAP:,}; the stream gathers 2% more "
                   "debris at the same time, up to 100%.")
    add("Refills", f"Next growth: {due(NEXT_TICK)}. Every growth missed while the game is closed happens when it is "
                   "next played.")

    add("Mushrooms", f"Mushrooms give {food(6)} food, or {food(35)} for the large kinds{mastery_words}. When they appear "
                     f"is {NOT_YET}.")
    if village.has(GOLDEN):
        add("Mushrooms", f"The patcher's \"{gm.feature_name(GOLDEN)}\" is in the game: there is a secret to find.")
    add("Mushrooms", f"Mushrooms found in this village: {_i32(data, MUSHROOMS_FOUND):,}.")
    add("Collectibles", "Four collections of 12. Once the collectible timer is running, one appears every 50 to 58 "
                        f"minutes at any speed {UNSURE}. A piece already found gives 100, 250 or 1,500 tech points by "
                        "rarity.")

    add("Tech points and effects", f"Tech points: {_i32(data, TECH):,}.")
    lvl = level[RESEARCH]
    divisor = {1: 11, 2: 9, 3: 7}.get(lvl)
    if divisor:
        add("Tech points and effects", (
            f"Research gives the researcher's skill ÷ {divisor} at research level {lvl}, "
            + {gm.FAST: "twice that on Fast speed", gm.NORMAL: "as it is on Normal speed",
               gm.SLOW: "0.6 of it on Slow speed"}[speed]
            + f" {UNSURE}; while catching up ÷ {5 if lvl >= 3 else 7}."))
    add("Tech points and effects", gm.patch_words(village, LEARNING, "no skill roll fails"))

    add("Food earned", f"A villager eats only when below full health: 1 food a meal {UNSURE}.")

    out.extend(gm.time_away(village, real(LAST_TICK), speed_value,
                            "Saved paused: no age is counted for the time away, and the timers move on with the "
                            "pause.", unit_seconds=20 * 60 * speed))
    add("Time away and Time Warp", "While catching up, each counted age unit gives every villager of 14 or more 4 "
                                   "jobs; gathering brings 8 food at every speed; with the Fruitwells built a "
                                   "successful farmer brings 5 more.")
    add("Time away and Time Warp", (f"Time Warp (the patcher's Origins upgrades) {UNSURE}: moves the clock on 3 "
                                    "years' worth at the current speed (3 hours on Fast, 6 on Normal, 10 on Slow); "
                                    "the island event and growth then come due at once."))

    first = " (30 minutes after the first)" if _i32(data, EVENTS_SEEN) == 0 else ""
    add("Island events", f"Next island event: {due(EVENT_NEXT)}. Island events come every 8 to 15 whole hours at any "
                         f"speed{first}; paused time does not count.")
    for line in EVENT_LINES:
        add("Island events", line)
    if village.has(STORY) is not False:
        add("Island events", gm.patch_words(village, STORY, "Pick Island Event chooses the event and its rolls"))

    add("Other", f"An age unit is {gm.duration(60 * speed)} and a year {gm.duration(20 * 60 * speed)} on {on} speed. "
                 f"Sickness, healing, building, pregnancy and stews are {NOT_YET}.")
    return out
