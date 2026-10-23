"""Game Mechanics for The Lost Children (VV2): read-only lines from one save (src/vv_game_mechanics.py).

THE SAVE.  A 12-byte header -- "ldwg", the clock's base (the village's creation, Unix seconds), the
buffer's length -- then the game state from state+8 on: state offset S is file offset S + 4.  The clock
0x403200 counts real seconds from the base, so a stamp v is the real moment base + v.  State offsets:
  speed 0x2EB08 (3 Fast, 6 Normal, 10 Slow; + 999 paused), the last tick 0x2EAE4, food 0x2EAA4, tech
  points 0x2EADC, coconuts 0x2EACC, fish 0x2EAD0, field water 0x2EAD4, crops 0x2EAD8, the next regrowth
  0x2EAC0, the fire's end 0x2EAC4, the Gong's next ring 0x2EAC8, the next island event 0x2EAE0, the dam
  0x2E798, irrigation 0x2E770, the Gong's first ring done 0x2E910.

THE RULES (static reading of the stock executable; the coordinator's scratchpad spec mech_vv2\\spec.md,
2026-10-23; items it marks uncertain are said so on the page):
  * Yields per trip on Fast / Normal / Slow (catch-up): coconuts 8/4/2 (4), crops 10/7/4 (7), fish
    11/8/5 (8) (0x463160, 0x46321E, 0x4632CB).
  * Regrowth every speed x 2400 seconds: coconuts +30 up to 1500; crops to 800 with the dam and water or
    irrigation, else wiped.  Missed regrowths all happen on load (0x43B9B0).
  * Mushrooms and collectibles (real time, any speed): one at a time; a (Exploration + 4)% roll every
    2 seconds (0x415FEB); shown 75 seconds; a mushroom (65 - 15 x Exploration)% of the time, +6 food or,
    1 in 10, +35; collectibles rare (2 x Exploration + 2)%, uncommon 12%; duplicates 100 / 250 / 1500
    tech points (0x46345A).
  * Research: Research / 11, / 9, / 5 at Science 1, 2, 3, x 2 on Fast, / 2 on Slow above 1; a lit fire a
    10% chance of +1 (0x46361B).  Catch-up / 7, / 6, / 4.
  * The fire burns 10 / 20 / 40 hours (0x4624E8); the Gong rings at most once a day (0x461B3F): tier A
    5%, B 23.75%, C the rest, the first ring always C.
  * Island events: 15 minutes after creation, 30 minutes after the first, then every 10 to 19 hours;
    two-choice 20%, single-result 40%, sack 40%.
  * Elder totems: 3 skills at 88 or more, while there are fewer than 50 totems (0x44D4C0); the patcher's
    vv2_totems_out_of_entries keeps them outside the villager records, with no such limit.
"""
from __future__ import annotations

import struct

import vv_game_mechanics as gm
import vv_save_backup

GAME = 2
S = 4                                          # file offset = state offset + 4
SPEED, LAST_TICK, FOOD, TECH = 0x2EB08, 0x2EAE4, 0x2EAA4, 0x2EADC
COCONUTS, FISH, WATER, CROPS = 0x2EACC, 0x2EAD0, 0x2EAD4, 0x2EAD8
REGROW, FIRE_END, GONG_NEXT, EVENT_NEXT = 0x2EAC0, 0x2EAC4, 0x2EAC8, 0x2EAE0
DAM, IRRIGATION, GONG_FIRST_DONE = 0x2E798, 0x2E770, 0x2E910
COCONUT_CAP, CROPS_FULL = 1500, 800
FIRE_HOURS = {gm.FAST: 10, gm.NORMAL: 20, gm.SLOW: 40}
UNSURE = "(uncertain)"
GOLDEN = "vv2_super_secret_golden_mushroom"
LEARNING = "vv2_learning_never_fails"
TOTEMS = "vv2_totems_out_of_entries"
RESTORE_EVENTS = "vv2_restore_missing_island_events"
GONG_FIX = "vv2_gong_of_wonder_coconuts_fix"
STORY = "vv2_story_cheat_upgrades"

EVENT_LINES = (
    "The first event is always a two-choice event. After that each is a two-choice event 20% of the time, a "
    "single-result event 40% and a sack or vial 40%; within each kind every event whose conditions hold is "
    "equally likely.",
    "Single-result events (each about 1.67% when every condition holds): Obnoxious Parrot, Flash Flood, Dense "
    "Fog (4 kinds), East Wind, Heat Wave, Isola Day, Day of Elders, Blessings Day (2 kinds), Spring Allergies, "
    "Friendly Parrot, West Wind and Mother Parrot always; Epidemic, Rats! and Foul Passing once all 16 puzzles "
    "are solved; Where Are The Infants? also needs a nursing adult; Day of Honor a memorial grave; A Dangerous "
    "Mission more than 60 villagers; Barrel O' Babies and Old Friends room for more villagers.",
    "Single-result strength is a third of the population, 1 to 10; Barrel O' Babies brings one toddler at "
    "strength 1 to 4, two at 5 to 7, three at 8 to 10.",
    "Two-choice events (each about 0.95% when it can happen): Ancient Gold Coin needs Culture below 2; Spyglass "
    "Exploration below 2; Cursed Idol 250 food or more; Prettiest Girl a woman of 14 or more; Savage Child room "
    "for more villagers; For The Birds and Child Prodigy a child; Silver Mirror 2 or more villagers; Love Note "
    "an adult man and an adult woman.",
    "Sacks and vials: plastic, sealed, compromised, canvas, burlap, green, orange or fragrant, 5% each; small "
    "33%, medium 34%, large 33%. A compromised sack makes each villager sick at 15/20/25% by size; a canvas "
    "sack bites each villager at 20/30/45%.",
    f"The split between outcomes inside a choice (Voices, Hole In The Sand, Bump) is not yet worked out {UNSURE}.",
)
GONG_LINES = (
    "Gong of Wonder: tier A 5% (each of its 6 results about 0.83%: a vision, +1000 food with the plants and "
    "coconuts refilled, +20,000 to 59,999 tech points, all food taken, every woman pregnant, the ringer's life "
    "taken); tier B 23.75% (each of 9 about 2.64%: 30% fall sick, an island event in a minute, +10,000 to "
    "29,999 tech points, +1000 to 2999 food, the ringer loses 90 health, the plants or coconuts emptied, youth "
    "taken or given).",
    "Tier C the rest, 71.25% (each of 9 about 7.92%, Wisdom 15.8%): everyone healed, +200 to 999 food, the "
    "plants refilled, the coconuts refilled, +3000 to 12,999 tech points, -3000 to 12,999 tech points, 15% "
    f"fall sick. The first ring is always tier C. Which result is \"a vision\" is {UNSURE.strip('()')}.",
)
ODDS_LINES = (
    "Conception: a roll of 300 at or under Parenting + 50 x Medicine level - 50. Twins 7% at Medicine 3, and "
    "a quarter of twins become triplets.",
    "An embrace fails 34% of the time with food under 300; a work trip injures 2% of the time.",
    "A sick villager loses 1 health 61% of age units; the lit fire halves the chance of falling sick. Old age: "
    "at each birthday past 55, 63 or 71 (Medicine 1, 2, 3) a 10% chance of death for each year over.",
)


def _i32(data: bytes, state: int) -> int:
    return struct.unpack_from("<i", data, state + S)[0]


def facts(village: gm.Village) -> list[gm.Fact]:
    data = village.data
    found = vv_save_backup.save_speed(GAME, data)
    if found is None or found[0] != SPEED + S:
        return [gm.Fact("Other", f"{village.save.name} could not be read: it is not a Lost Children save.")]
    base = struct.unpack_from("<I", data, 4)[0]
    speed_value = found[1]
    speed = gm.speed_base(speed_value)
    paused = speed_value >= gm.PAUSED
    on = gm.speed_name(speed)

    def real(at: int) -> float:
        return base + _i32(data, at)

    def due(at: int) -> str:
        if paused:
            return f"{gm.duration(max(0, _i32(data, at) - _i32(data, LAST_TICK)))} after it is unpaused"
        return gm.when(real(at)) + (" (when the village is next played)" if real(at) <= village.now else "")

    out: list[gm.Fact] = []
    add = lambda group, text: out.append(gm.Fact(group, text))  # noqa: E731
    pick = {gm.FAST: 0, gm.NORMAL: 1, gm.SLOW: 2}[speed]

    # -- Food sources --------------------------------------------------------------------
    add("Food sources", f"Food in storage: {_i32(data, FOOD):,}.")
    add("Food sources", f"Coconuts: {_i32(data, COCONUTS):,}; a trip brings {(8, 4, 2)[pick]} on {on} speed "
                        "(4 while catching up).")
    dam, irrigated = _i32(data, DAM) > 0, _i32(data, IRRIGATION) > 0
    add("Food sources", f"Crops: {_i32(data, CROPS):,} of {CROPS_FULL}, field water {_i32(data, WATER):,}; a trip "
                        f"brings {(10, 7, 4)[pick]} on {on} speed (7 while catching up)"
                        + ("." if dam else "; the crops grow only once the dam is built."))
    add("Food sources", f"Fish: {_i32(data, FISH):,} (they never grow back); a trip brings {(11, 8, 5)[pick]} on {on} "
                        "speed (8 while catching up). At 0, fishing stops until the algae-eating fish have been "
                        "done 10 times; after that the count can go below 0, as in the stock game.")
    add("Food sources", "Every trip needs a Farming roll; a failed trip brings nothing. "
                        + gm.patch_words(village, LEARNING, "no trip fails"))

    # -- Refills -------------------------------------------------------------------------
    if paused:
        add("Refills", gm.PAUSED_NOTE)
    add("Refills", (f"Every regrowth, {gm.every(2400 * 6, speed_value)}: coconuts +30, up to {COCONUT_CAP:,}; crops "
                    f"refilled to {CROPS_FULL} while the dam is built and the field has water or irrigation "
                    f"({'built' if dam else 'no dam yet'}, {'irrigated' if irrigated else 'not irrigated'}), "
                    "otherwise the crops are lost."))
    add("Refills", f"Next regrowth: {due(REGROW)}. Every regrowth missed while the game is closed happens when it "
                   "is next played.")

    # -- Mushrooms and collectibles ------------------------------------------------------
    add("Mushrooms", "One thing at a time, at any speed and only while playing: every 2 seconds with nothing out, a "
                     "(Exploration level + 4)% chance (about 40, 33 or 29 seconds' wait at Exploration 1, 2, 3). "
                     "It stays 1 minute 15 seconds.")
    add("Mushrooms", f"It is a mushroom 50%, 35% or 20% of the time at Exploration 1, 2, 3: +6 food, or 1 in 10 a "
                     f"special one for +35 {UNSURE}.")
    if village.has(GOLDEN):
        add("Mushrooms", f"The patcher's \"{gm.feature_name(GOLDEN)}\" is in the game: there is a secret to find.")
    add("Collectibles", "When it is not a mushroom it is a collectible: rare 4%, 6% or 8% at Exploration 1, 2, 3, uncommon 12%, the rest "
                        "common. A piece already found gives 100, 250 or 1500 tech points by rarity. Each complete "
                        "collection raises the population limit by 5, all four by 25.")

    # -- Tech points ---------------------------------------------------------------------
    add("Tech points and effects", f"Tech points: {_i32(data, TECH):,}.")
    add("Tech points and effects", (
        "Research gives Research skill ÷ 11, ÷ 9 or ÷ 5 at Science 1, 2 or 3, "
        + {gm.FAST: "twice that on Fast speed", gm.NORMAL: "as it is on Normal speed",
           gm.SLOW: "halved on Slow speed when above 1"}[speed]
        + "; a lit fire adds a 10% chance of 1 more. While catching up ÷ 7, ÷ 6 or ÷ 4."))
    if village.has(TOTEMS):
        add("Tech points and effects", "Esteemed Elders: a villager with 3 skills at 88 or more becomes a totem; the "
                                       f"patcher's \"{gm.feature_name(TOTEMS)}\" keeps the totems apart from the "
                                       "villagers, with no limit on how many.")
    else:
        add("Tech points and effects", "Esteemed Elders: a villager with 3 skills at 88 or more becomes a totem while "
                                       "there are fewer than 50 totems.")

    # -- Food earned ---------------------------------------------------------------------
    add("Food earned", f"Each villager eats 2 food every {gm.duration(60 * speed)} on {on} speed "
                       f"({2 * 3600 / (60 * speed):g} an hour); at 150 food or less only half eat.")

    # -- Time away and Time Warp ---------------------------------------------------------
    out.extend(gm.time_away(village, real(LAST_TICK), speed_value,
                            "Saved paused: nobody ages while it is closed; the regrowth, the fire and the next "
                            "island event are pushed back by the paused time, the Gong's rest is not.",
                            unit_seconds=20 * 60 * speed))
    add("Time away and Time Warp", "Counted years are worked off at one age unit every 2 seconds of play (12 years "
                                   "take about 8 minutes); each unit eats, rolls sickness and old age, and gives "
                                   "every healthy villager of 14 or more 4 jobs. Building adds 1 a try instead of 2. "
                                   "Mushrooms and collectibles do not pile up; a due island event happens once.")
    add("Time away and Time Warp", ("Time Warp (the patcher's Origins upgrades): exactly 3, 6 or 12 years on Slow, "
                                    "Normal or Fast, past the time-away limits, and the regrowth, fire, island "
                                    "event and Gong come due 10 hours (Slow) or 12 hours sooner; refused while "
                                    "paused."))

    # -- Island events -------------------------------------------------------------------
    add("Island events", f"Next island event: {due(EVENT_NEXT)}. Island events come every 10 to 19 hours at any "
                         "speed (the first 15 minutes after the village is made, the second 30 minutes later).")
    for line in EVENT_LINES:
        add("Island events", line)
    if village.has(RESTORE_EVENTS) is not False:
        add("Island events", gm.patch_words(village, RESTORE_EVENTS,
                                            "3 more single-result events, each then about 1.48%"))
    if village.has(STORY) is not False:
        add("Island events", gm.patch_words(village, STORY, "Pick Island Event and Pick Gong Outcome choose them"))

    # -- Other ---------------------------------------------------------------------------
    gong_first = _i32(data, GONG_FIRST_DONE) == 0
    gong_when = (f"can ring again {gm.when(real(GONG_NEXT))}" if real(GONG_NEXT) > village.now
                 else "can ring now")
    add("Other", f"The Gong of Wonder {gong_when}; it rings at most once a day, at any speed."
                 + (" Its first ring is always tier C." if gong_first else ""))
    for line in GONG_LINES:
        add("Other", line)
    add("Other", gm.patch_words(village, GONG_FIX, "its coconut results work as their words say"))
    fire = real(FIRE_END)
    add("Other", ("The fire " + (f"burns until {gm.when(fire)}" if fire > village.now and not paused else
                                 ("was burning when it was saved" if paused and _i32(data, FIRE_END) > _i32(data, LAST_TICK)
                                  else "is out"))
                  + f"; a lit fire burns {gm.duration(FIRE_HOURS[speed] * 3600)} on {on} speed."))
    add("Other", f"A stew cooks for 15 minutes. An unburied body is gone after {gm.duration(240 * 60 * speed)} on {on} "
                 "speed.")
    for line in ODDS_LINES:
        add("Other", line)
    return out
