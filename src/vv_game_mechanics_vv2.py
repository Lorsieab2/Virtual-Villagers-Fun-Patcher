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
RESTORE_EVENTS = "vv2_restore_missing_island_events"
GONG_FIX = "vv2_gong_of_wonder_coconuts_fix"
STORY = "vv2_story_cheat_upgrades"

# (line, verified)
EVENT_LINES = (
    ("The first event is always a two-choice event. After that 20% are two-choice events, 40% single-result "
     "events and 40% sacks or vials; within each kind every event whose conditions hold is equally likely: "
     "with every condition met each single-result event is 1.67%, each two-choice event 0.95%, each sack or "
     "vial 5%.", True),
    ("Single-result events: Obnoxious Parrot, Flash Flood, Dense Fog (4 kinds), East Wind, Heat Wave, Isola Day, "
     "Day of Elders, Blessings Day (2 kinds), Spring Allergies, Friendly Parrot, West Wind and Mother Parrot "
     "always; Epidemic, Rats! and Foul Passing once all 16 puzzles are solved; Where Are The Infants? also needs "
     "a nursing adult; Day of Honor a memorial grave; A Dangerous Mission more than 60 villagers; Barrel O' "
     "Babies and Old Friends room for more villagers.", False),
    ("Single-result results (k is 1 up to 50 villagers, 3 above): Obnoxious Parrot -25% of the tech points; Flash "
     "Flood food cut to 750; Dense Fog food -200k, tech -1000k, tech +800k or food +150k; Friendly Parrot food "
     "+400k; East Wind -80 per strength from food, coconuts and crops; West Wind +100 per strength to coconuts "
     "and crops; Isola Day and Blessings Day cost 10 food a villager + 10.", True),
    ("Epidemic makes each villager sick at 79.7%; Rats! takes half the food and bites each villager at 40.2% "
     "(sick, -60 health); Foul Passing takes all the food; Mother Parrot gives each child a 35% chance of +7 to "
     "17 Parenting; A Dangerous Mission sends up to 8 of the youngest adults away. Heat Wave, Spring Allergies "
     "and Day of Honor change no amounts.", True),
    ("Two-choice events: Ancient Gold Coin needs Culture below 2; Spyglass Exploration below 2; Cursed Idol 250 "
     "food or more; Prettiest Girl a woman of 14 or more; Savage Child room for more villagers; For The Birds "
     "and Child Prodigy a child; Silver Mirror 2 or more villagers; Love Note an adult man and an adult woman.",
     False),
    ("Two-choice results (k is 1 up to 25 villagers, 2 up to 50, 3 above): Voices In The Brush (investigate) 50% "
     "+700k food, 50% the villager is never seen again; Hole In The Sand (investigate) 1 in 6 each: +1000 tech, "
     "+1000 tech, +300 food, -150 food, the finder sick, or the finder sick and every other villager at 40%; "
     "Bump On The Head (bonk) 50% every skill +30, 50% every skill -30, either way -10 health.", True),
    ("Falling Star: a wish for yourself raises one skill by 10 to 20; for the village 50% +100 to 299k food, 50% "
     "+1000 to 2999k tech. Gold Coin (give) +2000 tech; Cursed Idol (offer) -250 food; Prettiest Girl (looks "
     "aren't everything) +20 to 39 Parenting; Strange Request (allow) -3000 tech; Savage Child (chase) -1000 "
     "tech; For The Birds +100 food or +30 Farming; Nightmare (let sleep) -20 health.", True),
    ("Child Prodigy (play) Building +50, (apprentice) +1000 tech and +10 Research; Dragonflies (chase) each "
     "villager sick at 20%; Crystal Ball (keep) swaps with another villager; Huge Coconut (hurl) +250 food and "
     "the finder fully healed; Spyglass (give) +3000 tech; Love Note +30 Parenting; White Pearl (keep) +10 to 29 "
     "every skill, (show) -200 tech.", True),
    ("Sacks by size small / medium / large (33%, 34%, 33%): plastic +500/1000/1500 food; sealed +1000/2000/3000 "
     "tech; compromised +500/1000/1500 tech and each villager sick at 15/20/25%; canvas the finder -15 health and "
     "each villager bitten at 20/30/45% for -10/-15/-20; burlap the finder -40/70/110 health; green vial a new "
     "head; orange vial one skill +50/75/100; fragrant vial every skill -30/50/70.", True),
    ("Barrel O' Babies, Old Friends and Savage Child (lure) bring villagers; how many and who is not yet "
     "worked out.", False),
)
GONG_LINES = (
    ("Gong of Wonder: the first ring is always tier C, each of its 9 results 11.1%. Later rings: tier A 5% (each "
     "of 6 about 0.84%: sparkles and a glow only; +1000 food with the crops and coconuts refilled; +20,000 to "
     "59,999 tech points; all food, crops and coconuts taken; every woman of 18 to 49 healed and pregnant; the "
     "ringer dies).", True),
    ("Tier B 23.75% (each of 9 about 2.64%: each villager sick at 30%; an island event in a minute; +10,000 to "
     "29,999 tech points; +1000 to 2998 food; the ringer -90 health; the crops emptied; the coconuts emptied; "
     "youth taken; youth given). Tier C 71.25% (each about 7.9%, Wisdom 15.8% as it is on two of the 9: everyone healed; +200 to "
     "999 food; the crops refilled; the coconuts refilled; +3005 to 12,999 tech points; -3000 to 12,999 tech "
     "points; each villager sick at 15%; one of the ringer's skills set to 100).", True),
)
ODDS_LINES = (
    ("Conception per embrace at Parenting 100: 33.9%, 50.5% or 67.1% at Medicine 1, 2, 3 (7.6% at Parenting 30 "
     "and Medicine 1); with food under 300 two thirds of that; never for a woman of 50. At Medicine 3, 7.18% of "
     "conceptions are twins or more, 1.84% triplets.", True),
    ("Sickness each age unit with the fire out / lit: 0.52% / 0.28% at Medicine 1, 0.28% / 0.14% at Medicine 2, "
     "0.11% / 0.09% at Medicine 3, about 1.5% more from 50, 58 or 66 years; Easy halves these.", True),
    ("Old age: from 55, 63 or 71 years (Medicine 1, 2, 3), each birthday past it carries a death roll, the chance rising 10% for each year over.", False),
    ("Building: huts and the hospital +2 a try (+1 while catching up); the dam, vines and thorns +2, or +3 at "
     "Building 88 (+1 or +2 while catching up); the ruins +1, or +2 at 88. A work try injures about 2% of the "
     "time (1% at the ruins).", True),
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
    add = lambda group, text, ok=False: out.append(gm.Fact(group, text, ok))  # noqa: E731
    pick = {gm.FAST: 0, gm.NORMAL: 1, gm.SLOW: 2}[speed]
    dam, scared = _i32(data, DAM) > 0, _i32(data, SCARER) > 0

    # -- Food sources --------------------------------------------------------------------
    add("Food sources", f"Food in storage: {_i32(data, FOOD):,}.", gm.SAVE)
    add("Food sources", f"Coconuts: {_i32(data, COCONUTS):,}; a trip brings {(8, 4, 2)[pick]} on {on} speed "
                        "(4 while catching up).", True)
    add("Food sources", f"Crops: {_i32(data, CROPS):,} of {CROPS_FULL}; a trip brings {(10, 7, 4)[pick]} on {on} speed "
                        "(7 while catching up).", True)
    add("Food sources", ("The birds: " + ("kept away." if scared else
                                          f"{_i32(data, ALLOWANCE):,} more food of harvest before they find the "
                                          "field and eat the young crops.")), True)
    add("Food sources", f"Fish: {_i32(data, FISH):,} (they never grow back); a trip brings {(11, 8, 5)[pick]} on {on} "
                        "speed (8 while catching up).", True)
    add("Food sources", "At 0 fish, fishing stops until the algae-eating fish have been done 10 times; after that "
                        "the count can go below 0, as in the stock game.")
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

    # -- Mushrooms and collectibles ------------------------------------------------------
    add("Mushrooms", "One thing at a time, at any speed and only while playing: every 2 seconds with nothing out, a "
                     "(Exploration level + 4)% chance (about 40, 34 or 28 seconds' wait at Exploration 1, 2, 3). It "
                     "stays 1 minute 15 seconds.", True)
    add("Mushrooms", "It is a mushroom 50%, 35% or 20% of the time at Exploration 1, 2, 3: +6 food, or 1 in 10 a "
                     "special one for +35.", True)
    if village.has(GOLDEN):
        add("Mushrooms", f"The patcher's \"{gm.feature_name(GOLDEN)}\" is in the game: there is a secret to find.")
    add("Collectibles", "When it is not a mushroom it is a collectible: rare 4%, 6% or 8% at Exploration 1, 2, 3, "
                        "uncommon 12%, the rest common. Butterflies and shells can always appear, pebbles once the "
                        "dam is built, beetles once their place is opened"
                        + (" (it is)." if _i32(data, BEETLES) > 0 else " (it is not yet)."), True)
    add("Collectibles", "A piece already found gives 100, 250 or 1500 tech points by rarity. Each complete collection "
                        "raises the population limit by 5, all four by 25.")

    # -- Tech points ---------------------------------------------------------------------
    add("Tech points and effects", f"Tech points: {_i32(data, TECH):,}.", gm.SAVE)
    add("Tech points and effects", (
        "Research gives Research skill ÷ 11, ÷ 9 or ÷ 5 at Science 1, 2 or 3, "
        + {gm.FAST: "twice that on Fast speed", gm.NORMAL: "as it is on Normal speed",
           gm.SLOW: "halved on Slow speed when above 1"}[speed]
        + "; a lit fire adds a 10% chance of 1 more. While catching up ÷ 7, ÷ 6 or ÷ 4."), True)
    if village.has(TOTEMS):
        add("Tech points and effects", "Esteemed Elders: a villager with 3 skills at 88 or more becomes a totem; the "
                                       f"patcher's \"{gm.feature_name(TOTEMS)}\" keeps the totems apart from the "
                                       "villagers, with no limit on how many.")
    else:
        add("Tech points and effects", "Esteemed Elders: a villager with 3 skills at 88 or more becomes a totem while "
                                       "there are fewer than 50 totems.", True)

    # -- Food earned ---------------------------------------------------------------------
    add("Food earned", f"Each villager eats 2 food every {gm.duration(60 * speed)} on {on} speed "
                       f"({2 * 3600 / (60 * speed):g} an hour); on Medium above 4000 food, or on Hard, 2 more 76% of "
                       "the time; at 150 food or less half the time, and a skipped meal costs 1 health 30% of the "
                       "time.", True)

    # -- Time away and Time Warp ---------------------------------------------------------
    out.extend(gm.time_away(village, real(LAST_TICK), speed_value,
                            "Saved paused: nobody ages while it is closed; the regrowth, the fire and the next "
                            "island event are pushed back by the paused time, the Gong's rest is not.",
                            unit_seconds=20 * 60 * speed))
    add("Time away and Time Warp", "While catching up a trip brings 4 coconuts, 7 crops or 8 fish at every speed, "
                                   "research ÷ 7, ÷ 6 or ÷ 4, building 1 a try.", True)
    add("Time away and Time Warp", "Counted years are worked off at one age unit every 2 seconds of play; mushrooms "
                                   "and collectibles do not pile up; a due island event happens once. A stew "
                                   "cooking when the game is closed is lost.")
    add("Time away and Time Warp", "Every regrowth missed while the game was closed is added when it is next played, "
                                   "with no limit on how many: coconuts stop at 1,500, crops at 800.", True)
    out.append(gm.time_warp_line(speed_value))
    add("Time away and Time Warp", "A Time Warp also brings the regrowth, the fire, the next island event and the "
                                   "Gong 10 hours (Slow) or 12 hours (Normal, Fast) sooner.")

    # -- Island events -------------------------------------------------------------------
    add("Island events", f"Next island event: {due(EVENT_NEXT)}.", gm.SAVE)
    add("Island events", f" Island events come every 10 to 19 whole hours at any "
                         "speed, each equally likely; a new village's first comes 15 minutes after it is made, the "
                         "second 30 minutes later.", True)
    for line, ok in EVENT_LINES:
        add("Island events", line, ok)
    if village.has(RESTORE_EVENTS) is not False:
        add("Island events", gm.patch_words(village, RESTORE_EVENTS,
                                            "Mosquito Swarm (each villager sick at 20%), Dragonfly Migration (+20 "
                                            "health for all) and Science Awareness Day (each child +3 to 7 Research) "
                                            "can happen too"))
    if village.has(STORY) is not False:
        add("Island events", gm.patch_words(village, STORY, "Pick Island Event and Pick Gong Outcome choose them"))

    # -- Other ---------------------------------------------------------------------------
    gong_first = _i32(data, GONG_FIRST_DONE) == 0
    gong_when = (f"can ring again {gm.when(real(GONG_NEXT))}" if real(GONG_NEXT) > village.now
                 else "can ring now")
    add("Other", f"The Gong of Wonder {gong_when}; it rings at most once every 24 hours, at any speed."
                 + (" Its first ring is always tier C." if gong_first else ""), True)
    for line, ok in GONG_LINES:
        add("Other", line, ok)
    if village.has(GONG_FIX) is not False:
        add("Other", gm.patch_words(village, GONG_FIX, "its coconut results work as their words say"))
    fire = real(FIRE_END)
    add("Other", ("The fire " + (f"burns until {gm.when(fire)}" if fire > village.now and not paused else
                                 ("was burning when it was saved" if paused and _i32(data, FIRE_END) > _i32(data, LAST_TICK)
                                  else "is out"))
                  + f"; a lit fire burns {gm.duration(FIRE_HOURS[speed] * 3600)} on {on} speed, and fuel on a burning "
                    "fire fills it again."), True)
    add("Other", f"A stew is ready 15 minutes after it starts. An unburied body is gone after "
                 f"{gm.duration(240 * 60 * speed)} on {on} speed.", True)
    for line, ok in ODDS_LINES:
        add("Other", line, ok)
    return out
