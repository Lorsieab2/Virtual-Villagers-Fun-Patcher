"""Game Mechanics for The Lost Children (VV2): read-only lines from one save (src/vv_game_mechanics.py).

THE SAVE.  A 12-byte header -- "ldwg", the clock's base (the village's creation, Unix seconds), the
buffer's length -- then the game state from state+8 on: state offset S is file offset S + 4.  The clock
0x403200 counts real seconds from the base, so a stamp v is the real moment base + v.  State offsets:
  speed 0x2EB08 (3 Fast, 6 Normal, 10 Slow; + 999 paused), the last tick 0x2EAE4, food 0x2EAA4, tech
  points 0x2EADC, coconuts 0x2EACC, fish 0x2EAD0, the field's bird allowance 0x2EAD4 (the harvest allowed
  before the birds come), crops 0x2EAD8, the next regrowth 0x2EAC0, the fire's end 0x2EAC4, the Gong's
  next ring 0x2EAC8, the next island event 0x2EAE0, the dam 0x2E798, the bird scarer 0x2E770, the Gong's
  first ring done 0x2E910, the Beetle collection's flag 0x2E7E0.

THE RULES: the coordinator's verified spec mech_vv2\\spec.md (2026-10-23).  A line built only from what
it marks EMU (the stock routine run in an emulator over many seeds) or SAVE is verified; a line with
anything it marks READ carries UNCONFIRMED (vv_game_mechanics.Fact.verified).
"""
from __future__ import annotations

import struct

import vv_game_mechanics as gm
import vv_game_mechanics_events as events
import vv_game_mechanics_events_vv2 as catalog
import vv_game_mechanics_life as life
import vv_save_backup

GAME = 2
S = 4                                          # file offset = state offset + 4
SPEED, LAST_TICK, FOOD, TECH = 0x2EB08, 0x2EAE4, 0x2EAA4, 0x2EADC
COCONUTS, FISH, ALLOWANCE, CROPS = 0x2EACC, 0x2EAD0, 0x2EAD4, 0x2EAD8
REGROW, FIRE_END, GONG_NEXT, EVENT_NEXT = 0x2EAC0, 0x2EAC4, 0x2EAC8, 0x2EAE0
DAM, SCARER, GONG_FIRST_DONE, BEETLES = 0x2E798, 0x2E770, 0x2E910, 0x2E7E0
COCONUT_CAP, CROPS_FULL = 1500, 800
FIRE_HOURS = {gm.FAST: 10, gm.NORMAL: 20, gm.SLOW: 40}
GOLDEN = "vv2_super_secret_golden_mushroom"
LEARNING = "vv2_learning_never_fails"
TOTEMS = "vv2_totems_out_of_entries"
EVENTS_SEEN = 0x2E51C                          # the Island Events Seen counter (state offset)

ODDS_LINES = (
    ("Conception per embrace at Parenting 100: 33.9%, 50.5% or 67.1% at Medicine 1, 2, 3 (7.6% at Parenting 30 "
     "and Medicine 1); with food under 300 two thirds of that; never for a woman of 50. At Medicine 3, 7.18% of "
     "conceptions are twins or more, 1.84% triplets.", gm.RUNNING),
    ("Sickness each age unit with the fire out / lit: 0.52% / 0.28% at Medicine 1, 0.28% / 0.14% at Medicine 2, "
     "0.11% / 0.09% at Medicine 3, about 1.5% more from 50, 58 or 66 years; Easy halves these.", gm.RUNNING),
    ("Building: huts and the hospital +2 a try (+1 while catching up); the dam, vines and thorns +2, or +3 at "
     "Building 88 (+1 or +2 while catching up); the ruins +1, or +2 at 88. A work try injures about 2% of the "
     "time (1% at the ruins).", gm.RUNNING),
)


# Hidden villager stats (the coordinator's specs hidden_vv2\spec.md and likes_all, 2026-10-23):
# (line, what stands behind it -- gm.RUNNING, gm.OWNER, or False for UNCONFIRMED).
HIDDEN_LINES = (
    ("Each villager's hidden number (1 to 123, rolled at creation, not inherited; a twin's is its sibling's + "
     "1) sets how it starves, its totem's colour (the number's remainder by 8) and its body and some "
     "animations; the villagers' numbers are below.", gm.RUNNING),
    ("Likes and dislikes: a new villager gets them from the first 47 words; jumping, cooking, fire, eating, "
     "children, talking and vegetables appear only when edited in.", gm.RUNNING),
    ("Learning: a skill try passes at skill + 66% when liked, + 16% when disliked, + 33% otherwise; the gain is "
     "doubled when liked and halved when disliked (Building gains Ã· 7, the others Ã· 10 of (100 - 2 x skill)).",
     gm.RUNNING),
    ("Work: liked, never idles for the 15% skip and always goes back to a remembered task; disliked, idles 70% of "
     "the time and drops remembered tasks (time on jobs 25.5% liked, 21.6% otherwise, 6.6% disliked). Medicine, "
     "disliked: Healing about half as often.", gm.RUNNING),
    ("Running: liked, walks at speed 300 (100 otherwise); disliked, 40 on every walk, children too; elders always "
     "walk at 40. Crowds, disliked: never joins Heat Wave, Isola Day, Day of Honor, the Blessings Days, completion "
     "celebrations or Gong watching.", gm.RUNNING),
    ("Disliked swimming, heights, coconuts, herbs, fire or cooking: \"Running away\" at that spot (the coconut "
     "harvest refused 75% of the time); fish: always refuses fishing; turnips or vegetables: refuses the crops "
     "trip 75%; wood: refuses building 40% at the check and half of firewood drops. Wood, liked: always the "
     "shorter route.", gm.RUNNING),
    ("Eating, liked: snacks instead of going to the pond and always eats a ready stew. Laundry, the ocean, "
     "talking, sand or resting, disliked: never chosen. Dancing or jumping, disliked: no dance or jump. Children, "
     "disliked: a storyteller tells a story only 2% of the time. Playing, liked: a child picks one of 4 lively "
     "plays.", gm.RUNNING),
    ("The other 37 likes and dislikes: no effect has been found in the running game. A preferred job wins 86% of "
     "the time; Parenting is picked on its own only 25% of the time.", False),
    ("A baby starts with one skill at 5 to 7 from a parent's best (Parenting is never inherited); the mother's "
     'Parenting rises at each conception; the litter is born after 40 age units of the mother.', False),
    ("An Esteemed Elder's totem keeps the elder's hidden number, so its colour was set when the elder was "
     'born; a totem never ages, loses health or dies.', gm.RUNNING),
    ("Totem babies: in the stock game a twin or triplet born into a record a totem left behind (a totem's "
     "burial, or Start Over) kept the totem mark and never aged or died. The patcher's Fix Vanilla Bugs has "
     'cleared that since v1.35.77.', gm.RUNNING),
    ('Sick: -1 health on 61% of age units, 19% at 20 health or less. Health comes back on every age unit on '
     'Easy, half of them otherwise (75% with the fire lit), a fifth of that past 42 + 8 x Medicine years.', gm.RUNNING),
    ('The fire: while lit, a research try gives 1 more tech point 10% of the time; fuel on a lit fire fills it '
     'to 10, 20 or 40 hours (Fast, Normal, Slow); fuel does not light a cold pit.', False),
)
# The stew pot (state +0x3043C..+0x30455, past the saved range +8..+0x30378, so never saved).  The cook routine
# 0x425B90 (called when the last ingredient goes in, 0x4620A1..0x4623BA) sets the stew +0x3044C at once and
# the pot's end +0x30450 to the real clock 0x403200 + 900 (0x425BA2); the world update empties the pot with
# 0x425B20 once 0x403200 passes it (0x42EBCC..0x42EBE7) -- nothing else empties it, and eating (0x461040,
# from 0x4623E9) leaves it.  Nothing reads +0x30450 for the screen, so no countdown is shown.  The stews'
# effects (0x461040 and the routines it calls: 0x455330, 0x45CD00, 0x450580, 0x454AB0, 0x455AC0, 0x453430,
# 0x44B010, 0x45FBF0, 0x44B1B0, 0x449B70) never read the clock: each acts once, when eaten.
STEW_POT_LINE = (
    "A stew is ready the moment it is made, and the pot keeps it 15 real-life minutes at every speed, then empties "
    "itself; the pot's timer runs on the real clock, so paused time counts too. Eating does not empty it: every "
    "villager who eats from it in those 15 minutes gets the stew. The game shows no countdown for it, and the save "
    "does not keep the pot.")
STEW_EFFECT_LINE = (
    "Each stew acts once, at the moment a villager eats it: none of the stews' effects sets a timer, so no "
    "villager has one running and a save holds none to count down.")
CHANCE_EXTRA = (
    ('Every roll that changes play is in the groups above, with its odds as measured.', gm.RUNNING),
    ('Timers: an age unit 3, 6 or 10 real-life minutes on Fast, Normal or Slow; regrowth every 2 hours, 4 hours '
     "or 6 hours 40 minutes of real life; island events 10 to 19 whole real-life hours apart; the Gong's 24 "
     'real-life hours of rest; a stew stays in the pot 15 real-life minutes; an item lies 1 minute 15 real-life '
     'seconds; an unburied body 240 age units.', gm.RUNNING),
    ('Many more rolls inside villager actions (walking, timing, animation, speech): not individually worked '
     'out.', False),
)


def _i32(data: bytes, state: int) -> int:
    return struct.unpack_from("<i", data, state + S)[0]


# The fish: one signed dword (0x2EAD0) a new village sets to 1100 (0x425257), or 2200 or 550 by difficulty
# (0x4255B7 / 0x42559D), that nothing ever adds to.  Each catch subtracts 11, 8 or 5 (8 while catching up) at
# 0x463305 with no floor.  The polluted-water test 0x425B00 is "fish <= 0 and Sustainable Fishing (the solved byte
# 0x2E7E8) not solved", so once it is solved Farming level 2 (0x45FD1B) and 3 (0x45FC36) farmers and the fishing
# task itself (0x45E562) fish on with no limit and the count keeps falling below 0, as in the stock game; level 1
# (0x45FDF4) only ever fishes while the count is above 0.  The other readers (0x45536B, 0x460970) also only test
# "> 0" (signed); nothing else writes it.  Wrapping past -2^31 would take about 195 million more trips.
SUSTAINABLE_FISHING, FARMING_LEVEL = 0x2E7E8, 5


def _fishing(data: bytes) -> tuple[int, bool, bool]:
    """(the fish count, Sustainable Fishing solved, fishing now has no limit)."""
    solved = data[SUSTAINABLE_FISHING + S] != 0
    farming = _i32(data, LEVELS + 8 * FARMING_LEVEL)
    return _i32(data, FISH), solved, solved and farming >= 2


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
    add = lambda group, text, ok=False: out.append(gm.Fact(group, text, ok))  # noqa: E731
    pick = {gm.FAST: 0, gm.NORMAL: 1, gm.SLOW: 2}[speed]
    # Both are the puzzles' solved bytes (0x425AC9 reads the Scarecrow's as a byte), not dwords.
    dam, scared = data[DAM + S] != 0, data[SCARER + S] != 0

    # -- Food sources --------------------------------------------------------------------
    add("Food sources", f"Food in storage: {_i32(data, FOOD):,}.", gm.SAVE)
    add("Food sources", f"Coconuts: {_i32(data, COCONUTS):,}; a trip brings {(8, 4, 2)[pick]} on {on} speed "
                        "(4 while catching up).", gm.RUNNING)
    add("Food sources", f"Crops: {_i32(data, CROPS):,} of {CROPS_FULL}; a trip brings {(10, 7, 4)[pick]} on {on} speed "
                        "(7 while catching up).", gm.RUNNING)
    # The birds (the owner, 2026-10-23: clarify them): the regrowth step 0x43B960 grows the crops 800 only while
    # 0x425AC0 says the birds have not found the field (the dam built, the Scarecrow's byte 0, the allowance
    # 0x2EAD4 at 0 or less), and otherwise sets them to 0 (0x43BA0D); the allowance starts at 1000 (0x425261) and
    # every crop harvest takes its food from it (0x463264); message 0x1CA (0x487138).  Static reading.
    # 0x425AC0 says the birds have found the field only with the dam's byte at 1 (cmp byte [ecx+0x2E798], 1);
    # without the dam the regrowth sets the crops to 0 for that reason alone (0x43B9F2 -> 0x43BA0D).
    allowance = _i32(data, ALLOWANCE)
    if scared:
        birds = "kept away by The Scarecrow."
    elif allowance > 0:
        birds = f"{allowance:,} more food of crop harvest before they find the field and eat the young crops."
    elif dam:
        birds = "they have found the field: each regrowth's new crops are eaten."
    else:
        birds = ("they come only once the dam is built; until then each regrowth leaves the field empty because "
                 "there is no dam, not because of birds.")
    add("Food sources", "The birds: " + birds, False)                      # static reading
    out.append(gm.Fact("Food sources", "A new village allows 1,000 food of crop harvest; every harvest (10, 7 or 4 "
                                       "food on Fast, Normal or Slow) counts against it, and it never comes back.",
                       False, sub=True))
    out.append(gm.Fact("Food sources", ("Once it is used up, at every regrowth (every "
                                        f"{gm.duration(2400 * 3)}, {gm.duration(2400 * 6)} or {gm.duration(2400 * 10)} "
                                        "on Fast, Normal or Slow; none while paused; every missed one after time away) "
                                        "the birds eat all the field's crops instead of it growing 800. No chance is "
                                        "rolled; the time of day and the weather do not matter, and stored food is never "
                                        "touched."), False, sub=True))
    out.append(gm.Fact("Food sources", "Only The Scarecrow stops it, for good; no patch changes it.", False, sub=True))
    out.append(gm.Fact("Food sources", "The game says: \"Oh my! Birds found your field and are relentlessly eating "
                                       "the young crops before your villagers can harvest them!\"", False, sub=True))
    fish, fishing_solved, fishing_unlimited = _fishing(data)
    trip = f"a trip brings {(11, 8, 5)[pick]} on {on} speed (8 while catching up)."
    if fishing_unlimited:
        add("Food sources", f"Fish: no limit, as Sustainable Fishing is solved; {trip}", gm.RUNNING)
        out.append(gm.Fact("Food sources", f"The game's own fish count is {fish:,}: it started at 2,200, 1,100 or "
                                           "550 by difficulty, never grows back, and every catch still takes from "
                                           "it. Below 0 it only means the first fish were used up long ago; every "
                                           "check in the game only asks whether it is above 0, so it does no harm.", gm.SAVE, sub=True))
    elif fishing_solved and fish <= 0:
        add("Food sources", f"Fish: {fish:,}; Sustainable Fishing is solved, but at Farming level 1 villagers fish "
                            "only while the count is above 0. From Farming level 2 they fish with no limit.", gm.SAVE)
    else:
        add("Food sources", f"Fish: {fish:,} (they never grow back); {trip}", gm.RUNNING)
    add("Food sources", "At 0 fish, fishing stops until Sustainable Fishing is solved (the algae-eating fish done 10 "
                        "times); after that, from Farming level 2, villagers fish with no limit and the count goes "
                        "below 0, as in the stock game.")
    add("Food sources", "Every trip needs a Farming roll; a failed trip brings nothing. "
                        + gm.patch_words(village, LEARNING, "no trip fails"))

    # -- Refills -------------------------------------------------------------------------
    if paused:
        add("Refills", gm.PAUSED_NOTE)
    add("Refills", (f"Every regrowth, {gm.every(2400 * 6, speed_value)}: coconuts +30, up to {COCONUT_CAP:,}; crops "
                    f"refilled to {CROPS_FULL} if the dam is built and the birds have not found the field (or are "
                    "kept away), otherwise the crops are lost to the birds. "
                    f"({'Dam built' if dam else 'No dam yet'}; {'birds kept away' if scared else 'no bird scarer'}.)"),
        True)
    add("Refills", f"Next regrowth: {due(REGROW)}.", gm.SAVE)
    add("Refills", "Changing the speed rescales the time left to the next regrowth and on the fire (pausing counts as "
                   "Normal); the island event and Gong timers are not rescaled.", gm.RUNNING)

    # -- Mushrooms and collectibles ------------------------------------------------------
    add("Mushrooms", "One thing at a time, at any speed and only while playing: every 2 seconds with nothing out, a "
                     "(Exploration level + 4)% chance (about 40, 34 or 28 seconds' wait at Exploration 1, 2, 3). It "
                     "stays 1 minute 15 seconds. Only a villager under 14 picks one up, when you drop them on it.", gm.RUNNING)
    add("Mushrooms", "It is a mushroom 50%, 35% or 20% of the time at Exploration 1, 2, 3: a brown "
                     "mushroom worth 6 food, or 1 in 10 a red (rare) mushroom worth 35.", gm.RUNNING)
    if village.has(GOLDEN):
        add("Mushrooms", gm.golden_line(GOLDEN, "about 2.5, 3 or 4.5 years of play at Exploration 1, 2, 3"), gm.RUNNING)
    add("Collectibles", "When it is not a mushroom it is a collectible: rare 4%, 6% or 8% at Exploration 1, 2, 3, "
                        "uncommon 12%, the rest common. Butterflies and shells can always appear, pebbles once the "
                        "dam is built, beetles once their place is opened"
                        + (" (it is)." if _i32(data, BEETLES) > 0 else " (it is not yet)."), gm.RUNNING)
    add("Collectibles", "A piece already found gives 100, 250 or 1500 tech points by rarity. Each complete collection "
                        "raises the population limit by 5, all four by 25.")

    # -- Tech points ---------------------------------------------------------------------
    add("Tech points and effects", f"Tech points: {_i32(data, TECH):,}.", gm.SAVE)
    add("Tech points and effects", (
        "Research gives Research skill Ã· 11, Ã· 9 or Ã· 5 at Science 1, 2 or 3, "
        + {gm.FAST: "twice that on Fast speed", gm.NORMAL: "as it is on Normal speed",
           gm.SLOW: "halved on Slow speed when above 1"}[speed]
        + "; a lit fire adds a 10% chance of 1 more. While catching up Ã· 7, Ã· 6 or Ã· 4."), gm.RUNNING)
    if village.has(TOTEMS):
        add("Tech points and effects", "Esteemed Elders: a villager with 3 skills at 88 or more becomes a totem; the "
                                       f"patcher's \"{gm.feature_name(TOTEMS)}\" keeps the totems apart from the "
                                       "villagers, with no limit on how many.")
    else:
        add("Tech points and effects", "Esteemed Elders: a villager with 3 skills at 88 or more becomes a totem while "
                                       "there are fewer than 50 totems.", gm.RUNNING)

    # -- Food earned ---------------------------------------------------------------------
    add("Food earned", f"Each villager eats 2 food every {gm.duration(60 * speed)} on {on} speed "
                       f"({2 * 3600 / (60 * speed):g} an hour); on Medium above 4000 food, or on Hard, 2 more 76% of "
                       "the time; at 150 food or less half the time, and a skipped meal costs 1 health 30% of the "
                       "time.", gm.RUNNING)

    # -- Time away and Time Warp ---------------------------------------------------------
    out.extend(gm.time_away(village, real(LAST_TICK), speed_value,
                            "Saved paused: nobody ages while it is closed; the regrowth, the fire and the next "
                            "island event are pushed back by the paused time, the Gong's rest is not.",
                            unit_seconds=20 * 60 * speed))
    add("Time away and Time Warp", "While catching up a trip brings 4 coconuts, 7 crops or 8 fish at every speed, "
                                   "research Ã· 7, Ã· 6 or Ã· 4, building 1 a try.", gm.RUNNING)
    add("Time away and Time Warp", "Counted years are worked off at one age unit every 2 seconds of play; mushrooms "
                                   "and collectibles do not pile up; a due island event happens once.")
    add("Time away and Time Warp", "A stew cooking when the game is closed is lost: the save does not keep it.",
        gm.SAVE)
    add("Time away and Time Warp", "Every regrowth missed while the game was closed is added when it is next played, "
                                   "with no limit on how many: coconuts stop at 1,500, crops at 800.", gm.RUNNING)
    out.append(gm.time_warp_line(speed_value))
    add("Time away and Time Warp", "A Time Warp also brings the regrowth, the fire, the next island event and the "
                                   "Gong 10 hours (Slow) or 12 hours (Normal, Fast) sooner.")

    # -- Island events -------------------------------------------------------------------
    add("Island events", f"Next island event: {due(EVENT_NEXT)}.", gm.SAVE)
    add("Island events", f"Island events seen in this village: {_i32(data, EVENTS_SEEN):,}.", gm.SAVE)
    out.extend(events.event_facts(village, catalog.RULES, catalog.EVENTS))
    # The Gong of Wonder: its rest from the save (the clock counts real seconds at any speed), then its results.
    gong_first = _i32(data, GONG_FIRST_DONE) == 0
    gong_when = (f"can ring again {gm.when(real(GONG_NEXT))}" if real(GONG_NEXT) > village.now
                 else "can ring now")
    add("Island events", f"The Gong of Wonder {gong_when} (its rest is 24 real-life hours at any speed)."
                         + (" This village has had no tier C result yet, so its next ring is tier C." if gong_first
                            else ""), gm.SAVE)
    out.extend(events.event_facts(village, extra=catalog.EXTRA))

    # -- Other ---------------------------------------------------------------------------
    fire = real(FIRE_END)
    add("Other", ("The fire " + (f"burns until {gm.when(fire)}" if fire > village.now and not paused else
                                 ("was burning when it was saved" if paused and _i32(data, FIRE_END) > _i32(data, LAST_TICK)
                                  else "is out"))
                  + f"; a lit fire burns {gm.duration(FIRE_HOURS[speed] * 3600)} on {on} speed, and fuel on a burning "
                    "fire fills it again."), gm.RUNNING)
    add("Other", gm.FIRE_OUT, gm.OWNER)
    # The Lost Children's island events (the island-event conditions report, VV2 part): none reads or ends the fire.
    add("Other", "No island event in this game puts the fire out.", gm.RUNNING)
    add("Other", gm.FIRE_CLOSED, gm.OWNER)
    add("Other", STEW_POT_LINE, gm.RUNNING)
    add("Other", STEW_EFFECT_LINE)
    add("Other", f"An unburied body is gone after {gm.duration(240 * 60 * speed)} of real life on {on} speed "
                 "(240 age units).", gm.RUNNING)
    for line, ok in HIDDEN_LINES:
        add(gm.HIDDEN, line, ok)
    out.extend(gm.starvation_lines(village, 0x14, gm.RUNNING, totem_colour=True))
    for line, ok in CHANCE_EXTRA:
        add("Chance and timers", line, ok)
    for line, ok in ODDS_LINES:
        add("Other", line, ok)
    out.append(gm.old_age_line("55, 63 or 71 years (Medicine 1, 2, 3)", "Totems do not age."))
    created = real(CREATED)
    out.append(gm.started_line(created))
    out.extend(gm.hours_puzzle_lines([name for name, _flag, _hours in PUZZLES],
                                     lambda n: data[PUZZLES[n][1] + S] != 0,
                                     lambda n: _i32(data, PUZZLES[n][2]), created))

    # -- The countdowns, and the people and clocks (src/vv_game_mechanics_life.py) ------------
    regrow_at = None if paused else real(REGROW)
    event_at = None if paused else real(EVENT_NEXT)
    gm.with_due(out, "Next regrowth:", regrow_at, "refill")
    gm.with_due(out, "Next island event:", event_at, "next")
    if real(GONG_NEXT) > village.now:
        gm.with_due(out, "The Gong of Wonder can ring again", real(GONG_NEXT), "ready")
    if not paused and fire > village.now:
        gm.with_due(out, "The fire burns until", fire, "ends")
    out.extend(life.sections(_context(village, data, speed_value, regrow_at, event_at, dam, scared, allowance)))
    return out


# The tech levels: six dwords 8 apart from state 0x2EA74 (all six reset at 0x425229); Medicine is the fourth
# (0x2EA8C: the twins roll at 0x44BA6A, sickness at 0x43B2ED), Exploration the fifth (0x2EA94: the mushroom spawn
# roll, its level + 4, at 0x415FF5).
LEVELS, MEDICINE_LEVEL, EXPLORATION_LEVEL = 0x2EA74, 3, 4


def _context(village: gm.Village, data: bytes, speed_value: int, regrow_at: float | None, event_at: float | None,
             dam: bool, scared: bool, allowance: int) -> life.Context:
    speed = gm.speed_base(speed_value)
    pick = {gm.FAST: 0, gm.NORMAL: 1, gm.SLOW: 2}[speed]
    paused = speed_value >= gm.PAUSED
    level = [_i32(data, LEVELS + 8 * k) for k in range(6)]
    crops_grow = dam and (scared or allowance > 0)
    fish, _, fishing_unlimited = _fishing(data)
    every = life.every_real(2400 * 6, speed_value).removeprefix("every ")
    # The regrowth's own steps (0x43B960): coconuts +30 up to 1,500; crops refilled to 800.
    steps = dict(interval=gm.real_seconds(2400 * 6, speed_value),
                 next_at=struct.unpack_from("<I", data, 4)[0] + _i32(data, REGROW),
                 first_in=life.resumed(max(0, _i32(data, REGROW) - _i32(data, LAST_TICK)), speed_value))
    sources = [
        life.Source("Coconuts", _i32(data, COCONUTS), COCONUT_CAP, 30 / 40, regrow_at, f"+30 every {every}", verified=gm.SAVE,
                    step=30, **steps),
        life.Source("Crops", _i32(data, CROPS), CROPS_FULL, CROPS_FULL / 40 if crops_grow else 0.0,
                    regrow_at if crops_grow else None,
                    f"refilled to {CROPS_FULL} every {every}" if crops_grow else
                    ("no refill until the dam is built" if not dam else "eaten by the birds at every regrowth"),
                    verified=gm.SAVE, step=CROPS_FULL if crops_grow else 0, **steps),
        (life.Source("Fish: no limit, as Sustainable Fishing is solved", None, unlimited=True, verified=gm.SAVE)
         if fishing_unlimited else
         life.Source("Fish", fish, None, 0.0, None, "they never grow back", verified=gm.SAVE))]
    exploration = level[EXPLORATION_LEVEL]
    waits = {1: (40, 0.50), 2: (34, 0.35), 3: (28, 0.20)}
    wait, share = waits.get(exploration, (40, 0.50))
    ctx = life.Context(
        village, speed_value, real_last(data), _i32(data, FOOD), low_food=150, extra_from=4001, sources=sources,
        tech=_i32(data, TECH), tech_words="Research brings them (the skill Ã· 11, Ã· 9 or Ã· 5 at Science 1 to 3).",
        brown=6, red=35, red_share=0.10, mushrooms_an_hour=3600 / wait * share, golden=village.has(GOLDEN) is True,
        mushroom_words=f"At Exploration level {exploration} something appears about every {wait} real-life seconds while "
                       f"nothing is out, {share:.0%} of them mushrooms, picked only when you drop a child on them.",
        event_next=event_at,
        event_paused_left=max(0, _i32(data, EVENT_NEXT) - _i32(data, LAST_TICK)) if paused else None,
        event_rule="It comes 10 to 19 whole real-life hours after the last, at any speed; then every event whose conditions hold "
                   "is equally likely within its kind (two-choice 20%, single-result 40%, sacks and vials 40%).",
        event_running="Paused, its timer is pushed back by the paused time; with the game closed it runs on, and a due "
                      "event happens once; a Time Warp brings it 10 real-life hours (Slow) or 12 (Normal, Fast) sooner.",
        medicine=level[MEDICINE_LEVEL], elderly_from={1: 50, 2: 58, 3: 66}, old_age_from={1: 55, 2: 63, 3: 71},
        parents_from=18, sick_loss=(0.61, 0.19),
        collectibles=[("Collectibles owned: not shown, because where The Lost Children's save keeps its collection "
                       "counts has not been traced. A piece already found pays 100, 250 or 1,500 "
                       "tech points by rarity.", gm.SAVE)],
        limit=life.limit_words(village, None, "5 for each complete collection, 25 with all four"),
        food_words="2 food a villager every age unit; on Medium above 4,000 food, or on Hard, 2 more 76% of the "
                   "time; never more on Easy.",
        gatherer_words=("The birds: the field's crops count for nothing here, as the birds eat each regrowth's crops."
                        if dam and not crops_grow else ""),
        trips=[("coconut trips", (8, 4, 2)[pick]), ("crop trips", (10, 7, 4)[pick] if crops_grow or _i32(data, CROPS) else 0),
               ("fishing trips", (11, 8, 5)[pick] if fish > 0 or fishing_unlimited else 0)])
    return ctx


def real_last(data: bytes) -> float:
    return struct.unpack_from("<I", data, 4)[0] + _i32(data, LAST_TICK)


# The village's start: [state+0x2E4F8], on the clock 0x403200, that the puzzles' hours count from.  The 16
# puzzles (the Village Statistics' count): a solved byte and the whole hours since the start that the completion
# writes, (the clock - the start) / 3600, at least 1 (0x462B44..0x462B73); state offsets, as the patcher's Story
# Cheat Upgrades reads them.
CREATED = 0x2E4F8
PUZZLES = (("Fire", 0x2E768, 0x2E530), ("The Scarecrow", 0x2E770, 0x2E534), ("The Elder Totem", 0x2E778, 0x2E538),
           ("The Hospital", 0x2E780, 0x2E53C), ("Herb Mastery", 0x2E788, 0x2E540), ("The Sewing Hut", 0x2E790, 0x2E544),
           ("The Dam", 0x2E798, 0x2E548), ("The Cutting Tool", 0x2E7A0, 0x2E54C), ("The Stew", 0x2E7A8, 0x2E550),
           ("The Vine Wall", 0x2E7B0, 0x2E554), ("The Ancient Mosaic", 0x2E7B8, 0x2E558),
           ("The Boxed Gong Piece", 0x2E7C0, 0x2E55C), ("The Sunken Gong Piece", 0x2E7C8, 0x2E560),
           ("The Inlaid Gong Piece", 0x2E7D8, 0x2E568), ("The Overgrown Gong Piece", 0x2E7E0, 0x2E56C),
           ("Sustainable Fishing", 0x2E7E8, 0x2E570))
