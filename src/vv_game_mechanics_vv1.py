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
  * Time away (0x42EA62): each villager's away time counts in full up to 10 h 36 m 40 s / 8 h 36 m
    40 s / 6 h 36 m 40 s (Fast / Normal / Slow); from there to 24 hours it counts as 8 h 36 m 40 s; over
    24 hours as 24 hours.  A save left paused gets no catch-up (credit zeroed, 0x42EACE) -- a static
    reading, not yet confirmed in game.
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
# Time away: counted in full up to this (real seconds), per speed; then 8 h 36 m 40 s up to a day;
# then a day.
FULL_AWAY = {gm.FAST: 38_200, gm.NORMAL: 31_000, gm.SLOW: 23_800}
BAND_AWAY = 31_000
DAY = 86_400
GOLDEN = "vv1_super_secret_golden_mushroom"
LEARNING = "vv1_learning_never_fails"


def _i32(data: bytes, at: int) -> int:
    return struct.unpack_from("<i", data, at)[0]


def counted_away(seconds: float, speed: int) -> float:
    """How much of `seconds` away the game counts, at `speed` (3, 6 or 10)."""
    if seconds <= FULL_AWAY.get(speed, FULL_AWAY[gm.NORMAL]):
        return max(0.0, seconds)
    return BAND_AWAY if seconds <= DAY else DAY


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
    add = lambda group, text: out.append(gm.Fact(group, text))  # noqa: E731

    # -- Food sources --------------------------------------------------------------------
    add("Food sources", f"Food in storage: {_i32(data, FOOD):,}.")
    bush = _i32(data, BUSH)
    add("Food sources", f"Berry bush: {bush:,}; a pick takes {max(2, bush // 130):,} from it now (the bush ÷ 130, "
                        "at least 2).")
    field = _i32(data, FIELD)
    add("Food sources", f"Crop field: {field:,} of {FIELD_CAP}; a harvest gives 7"
                        + ("." if level[FARMING] >= 2 else "; it refills only at Farming level 2 or more."))
    add("Food sources", "Fishing: 9 a catch, or for a villager with Farming skill 90 or more a 21% chance of 55; "
                        "it needs Farming level 3 and the beach cleaned"
                        + (" (Farming is level 3)." if level[FARMING] >= 3 else f" (Farming is level {level[FARMING]})."))

    # -- Refills -------------------------------------------------------------------------
    if paused:
        add("Refills", gm.PAUSED_NOTE)
    every = gm.every(REGROW_UNITS * UNIT, speed_value)
    add("Refills", f"The berry bush grows 30 {every}"
                   + (f"; the crop field grows 800, up to {FIELD_CAP}, at the same time." if level[FARMING] >= 2
                      else "; the crop field does not refill below Farming level 2."))
    add("Refills", f"Next regrowth: {due(REGROW)}. Changing the speed rescales the time left; every regrowth "
                   "missed while the game is closed is added when it is next played.")

    # -- Collectibles / Mushrooms --------------------------------------------------------
    add("Collectibles", "A New Home has no collectibles: mushrooms are its only random pickup.")
    add("Mushrooms", "While none is out, a mushroom appears after about 2 minutes on average, at any speed, at one "
                     "of 9 spots, and stays 1 minute unless picked. It gives 8 food, or 45 for the big kind "
                     "(1 in 20). Mushrooms are not kept in the save.")
    # The Super-Secret Golden Mushroom: only that a secret exists, never its odds or what it gives (the owner).
    if village.has(GOLDEN):
        add("Mushrooms", f"The patcher's \"{gm.feature_name(GOLDEN)}\" is in the game: there is a secret to find.")
    add("Mushrooms", f"Mushrooms found in this village: {_i32(data, MUSHROOMS_FOUND):,}.")

    # -- Tech points ---------------------------------------------------------------------
    science = level[SCIENCE]
    divisor = {1: 7, 2: 5, 3: 3}.get(science)
    add("Tech points and effects", f"Tech points: {_i32(data, TECH):,}.")
    if divisor:
        add("Tech points and effects", (
            f"Research gives the researcher's Research skill ÷ {divisor} (Science is level {science}), after a "
            "roll of (Research skill + 31)% that can fail."))
    else:
        add("Tech points and effects", "Research gives no tech points before Science level 1.")
    add("Tech points and effects", gm.patch_words(village, LEARNING, "the roll always passes"))

    # -- Food earned ---------------------------------------------------------------------
    per_hour = 2 * 3600 / (60 * speed)
    add("Food earned", f"Each villager eats 2 food every {gm.duration(60 * speed)} on {on} speed "
                       f"({per_hour:g} an hour).")

    # -- Time away and Time Warp ---------------------------------------------------------
    add("Time away and Time Warp", f"Last saved: {gm.when(saved)}, "
                                   + ("paused." if paused else f"on {on} speed."))
    if paused:
        add("Time away and Time Warp", (
            "Saved paused: the time away is not counted when it is next played, and the regrowth and island "
            f"event timers wait {gm.UNCONFIRMED}."))
    else:
        away = max(0.0, village.now - saved)
        counted = counted_away(away, speed)
        add("Time away and Time Warp", (
            f"If it were played now: {gm.duration(away)} away, of which {gm.duration(counted)} counts"
            + (f" ({counted / (60 * speed) / 20:.1f} years of the villagers' lives)." if counted else ".")))
    full = FULL_AWAY[speed]
    add("Time away and Time Warp", (
        f"On {on} speed time away counts in full up to {gm.duration(full, exact=True)}; from then to 24 hours it "
        f"counts as only {gm.duration(BAND_AWAY, exact=True)}; the most it ever counts is 24 hours, "
        f"{DAY / (60 * speed) / 20:g} years of the villagers' lives on {on} speed, however long the game was "
        "closed. Each counted age unit lets every adult try up to 5 jobs at once."))

    # -- Other ---------------------------------------------------------------------------
    # -- Island events -------------------------------------------------------------------
    first = (" The first is always the item event, the second 30 minutes later;"
             if _i32(data, EVENTS_SEEN) < 2 else "")
    add("Island events", f"Next island event: {due(EVENT)}.{first} Island events come every 12 to 23 hours, at any "
                         "speed. Paused, the timer waits; after time away at most one happens.")
    add("Island events", "Each event: 20% the item event; 40% an event scaled by the population (a third of it, 1 "
                         "to 10), whose outcomes include tech points (900 each), food (200 each), losses of 80 each "
                         "from the bush, the field or the food, or the beach dirtied again; 40% one of the other "
                         f"events. The odds of each outcome inside an event are {gm.UNCONFIRMED.strip('()')}.")
    add("Other", (f"An age unit is {gm.duration(60 * speed)} and a year {gm.duration(20 * 60 * speed)} on {on} "
                  "speed: ages, pregnancies (40 units) and regrowth follow the speed; work, mushrooms and island "
                  "events do not."))
    add("Other", f"The village was started at {gm.when(real(CREATED))}.")
    return out
