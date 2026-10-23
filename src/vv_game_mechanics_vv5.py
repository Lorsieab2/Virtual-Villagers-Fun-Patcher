"""Game Mechanics for New Believers (VV5): read-only lines from one save (src/vv_game_mechanics.py).

THE SAVE.  A 24-byte header -- "ldwg", ..., the clock's base as an int64 Unix time at 0x08 -- then the
game manager from +0x10: manager field X is file offset X + 0x10.  The clock 0x4036E0 counts real
seconds from the base (not scaled by the speed), so a stamp v is the real moment base + v.  FILE offsets:
  speed 0x17D8C (3 Fast, 6 Normal, 10 Slow; + 999 paused), the last tick 0x17D60, food 0x7C0, Mushrooms
  Found 0x7D8, island events seen 0x7E8, tech points 0xBC34, noni 0x17D68 (next tick 0x17D50), crops
  0x17D6C (next refill 0x17D54), Divine Energy 0x17D74 (cap 0x17D70), next island event 0x17D4C.

THE RULES (static reading of the stock executable; the research notes are in the coordinator's
scratchpad spec, mech_vv5\\spec.md, 2026-10-23):
  * An age unit is 60 x speed real seconds; 20 units are a year (0x473163).  Paused, every timer is
    pushed on by the paused time (0x425E4E): a paused save's "next" is that long after unpausing.
  * Noni: +2 a unit up to 1000 (0x425F64); a pick gives max(2, noni / 100) food (0x46CFCD).  Crops:
    refilled to 800 every 40 units once the Hydroponic Farm (project 5) is built (0x425ECD); a harvest
    gives 10 / 7 / 4 food on Fast / Normal / Slow, 7 during catch-up (0x46D0D0).  Fish 4 food (0x46D790).
  * Each believer eats 2 food a unit; heathens skip the life tick and eat nothing (0x472CB7).
  * Mushrooms and collectibles: about one spawn a minute at any speed, none while paused or closed
    (0x414633); 30% a mushroom (always in rain), of which 8% red (35 food) and 92% brown (6 food); the
    other 70% a collectible, 82% common, 13% uncommon, 5% rare (0x414395), the lab set only after the
    Knowing Totem (project 4).  Unpicked, both vanish after 90 seconds (0x414420).
  * Tech points: Research skill / 11, / 9, / 7 at Science 1, 2, 3 in play (x 6 / speed), / 7, / 7, / 5
    during catch-up, and only once the Knowing Totem is built (0x46C75E, 0x46DC96).
  * Divine Energy: each believer, each unit, +1, +3 more at Devotion 50+, +5 more at 88+ (0x472D1C),
    up to the cap (0x425020).
  * Island events: 15 minutes after the village is made, the second 30 minutes later, then every 8 to
    15 whole hours at any speed (0x4427A6); paused time does not count, closed time does; an overdue
    one happens once after loading.
  * Time away (0x46FF97..0x470013): counted in full up to 10 h 36 m 40 s / 8 h 36 m 40 s / 6 h 36 m 40 s
    (Fast / Normal / Slow), then as 8 h 36 m 40 s up to 24 hours, then 24 hours; a paused save gets
    nothing (0x47002E).  Heathens get no age on this path.
  * Time Warp (the patcher's vv5_expanded_256_time_warp): 3 / 6 / 12 years on Slow / Normal / Fast,
    past the caps; refused while paused.
"""
from __future__ import annotations

import struct

import vv_game_mechanics as gm
import vv_save_backup

GAME = 5
SPEED, LAST_TICK = 0x17D8C, 0x17D60
FOOD, MUSHROOMS_FOUND, EVENTS_SEEN, TECH = 0x7C0, 0x7D8, 0x7E8, 0xBC34
NONI, NONI_NEXT, CROPS, CROPS_NEXT = 0x17D68, 0x17D50, 0x17D6C, 0x17D54
ENERGY, ENERGY_CAP, EVENT_NEXT = 0x17D74, 0x17D70, 0x17D4C
UNIT = 360                                    # an age unit, in Normal-speed seconds
NONI_CAP, CROPS_FULL, CROP_UNITS = 1000, 800, 40
FULL_AWAY = {gm.FAST: 38_200, gm.NORMAL: 31_000, gm.SLOW: 23_800}
BAND_AWAY, DAY = 31_000, 86_400
TIME_WARP = "vv5_expanded_256_time_warp"
TIME_WARP_YEARS = {gm.SLOW: 3, gm.NORMAL: 6, gm.FAST: 12}
STORY = "vv5_story_cheat_upgrades"
UNSURE = "(uncertain)"
# The selector 0x418870: one of the events whose conditions hold, each equally likely; the eleven the
# stock game can never pick (dead code) are not listed (the coordinator's spec, section 5).
EVENT_LINES = (
    "Which event: every event whose conditions hold at that moment is equally likely (1 in the number of "
    "them); if none qualifies, nothing happens. An event can happen any number of times.",
    "Rescue: with 2 or fewer of the outnumbered sex, or fewer than 3 believers, there is a 6% chance the event "
    "is Chutes Without Ladders instead.",
    "Always possible: Creeping Mold, Allergy Season, Isola Day, the four Footprints events (food gained, food "
    "lost, tech gained, tech lost), Blessings Day, Strange Crystals, Especially Offensive Cloud, Spicy Juice, "
    "Clumsy Heathen, Salty Air and News From Another Tribe (a message).",
    "Day of Honor needs 2 or more graves. Vision, Mask, Doubt, Aphids in the Noni Bush, Straw Hat and Daredevil "
    "Jump need a believer; Bed Bugs a believer who is not pregnant; Strange Nectar a believer of 18 or more.",
    "Cold Snap needs the fire burning. Army Ants, Aphid Infestation and River Breaks Its Banks need the "
    "Hydroponic Farm; Pesky Critter the Knowing Totem. Advanced Artifacts needs Science exactly level 2; Trick Or "
    "Trade 100 food or more.",
    "Mushroom Day needs a believer child; Migrating Fruit Bats also Food Mastery below 2; Innovation in Farming "
    "also the Heathen Scientist. Heathen Toy, Spying on the Heathens and Missing Kids need a believer child and "
    "a healthy heathen child.",
    "Spa and Cracked Mask need a believer and a healthy heathen child; You're Doing It Wrong! an adult believer, "
    "a heathen child and Science below 2; Outreach? an adult believer and a healthy adult heathen; Defector a "
    "healthy heathen.",
    "The two Barrel O' Babies events, Chutes Without Ladders and News From Another Tribe (a newcomer) need room "
    "for more villagers.",
    "Rolled outcomes: You're Doing It Wrong! (teach them) 50% an explosion (10 to 29 health lost), 50% Science "
    "+1. Advanced Artifacts (independent report) 50% Research +40 and Science +1, 50% 100 tech points lost. "
    "Defector (accept) 50% a believer, 50% a spy (2,000 tech points lost).",
    "Amounts, each equally likely: Vision faith +20 to +39; Heathen Toy +20 to +29 Research or Devotion; Strange "
    "Crystals +2,000 to +2,999 tech points; Pesky Critter -500 to -2,999 tech points; Mushroom Day +50 to +99 "
    "food and -500 to -1,499 tech points; Cracked Mask (fix it) 20 to 30 health lost.",
    "Barrels and Chutes bring up to 3 ten-year-olds, each 50% a boy, with one random skill at 5 to 9 (a heathen "
    "barrel's babies start at faith -55); a newcomer is 18, 50% a man, with a random skill at 80 to 84. "
    f"Weather events last about 3 to 6 minutes {UNSURE}. Every other choice's result is fixed.",
)
ODDS_LINES = (
    "A new villager's starting faith: 30 to 59, each equally likely.",
    "A job succeeds with skill + 33 out of 100 (+ 66 if they like learning, + 16 if they dislike it), + 15 or "
    "+ 30 at Learning level 2 or 3.",
    "Conception: (Breeding - 50 + 50 x Medicine level + 1) out of 300 (17% at Breeding 50 and Medicine 1); the "
    "first is certain. At Medicine 3 only: twins 5.25%, triplets 1.75%.",
    f"Belief, each age unit {UNSURE}: down 30% with food under 10, 10% at 250 or less, 15% when sick, "
    "(12 - believers)% under 12 believers; up 20% at 8,000 food or more, 30% with the Idol, 10% or 20% at statue "
    "stage 1 or 2, 10/20/30% at Spirituality 1/2/3, (believers ÷ 5)% at 12 or more. A drop is skipped half the "
    "time below belief 5, a rise 70% of the time above 75. At belief 0 or less a believer turns heathen.",
    f"Sickness, each age unit {UNSURE}: 0.28%, 0.16% or 0.06% at Medicine 1, 2 or 3; old age adds 1.5%.",
    f"Burial {UNSURE}: 25%, then 70% of the rest for a healer with Healing 50 or more. Research in play {UNSURE}: "
    "a 10% lab accident and a 2% injury.",
)
GOLDEN = "vv5_super_secret_golden_mushroom"
LEARNING = "vv5_learning_never_fails"


def _i32(data: bytes, at: int) -> int:
    return struct.unpack_from("<i", data, at)[0]


def counted_away(seconds: float, speed: int) -> float:
    if seconds <= FULL_AWAY.get(speed, FULL_AWAY[gm.NORMAL]):
        return max(0.0, seconds)
    return BAND_AWAY if seconds <= DAY else DAY


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
    add = lambda group, text: out.append(gm.Fact(group, text))  # noqa: E731
    unit = gm.duration(60 * speed)

    # -- Food sources --------------------------------------------------------------------
    add("Food sources", f"Food in storage: {_i32(data, FOOD):,}.")
    noni = _i32(data, NONI)
    add("Food sources", f"Noni bushes: {noni:,} of {NONI_CAP:,}; a pick gives {max(2, noni // 100)} food now "
                        "(the noni ÷ 100, at least 2), once the granary is built.")
    crops = _i32(data, CROPS)
    harvest = {gm.FAST: 10, gm.NORMAL: 7, gm.SLOW: 4}[speed]
    add("Food sources", f"Hydroponic Farm crops: {crops:,} of {CROPS_FULL}; a harvest needs 15 and gives {harvest} "
                        f"food on {on} speed (7 while catching up).")
    add("Food sources", "Fishing at the lake: 4 food a fish; it never runs out.")

    # -- Refills -------------------------------------------------------------------------
    if paused:
        add("Refills", gm.PAUSED_NOTE)
    add("Refills", f"Noni: +2 {gm.every(UNIT, speed_value)}, up to {NONI_CAP:,} (empty to full in "
                   f"{gm.duration(NONI_CAP // 2 * 60 * speed)}); next {due(NONI_NEXT)}.")
    crop_next = "" if not paused and real(CROPS_NEXT) <= village.now else f"; next {due(CROPS_NEXT)}"
    add("Refills", f"Crops: refilled to {CROPS_FULL} {gm.every(CROP_UNITS * UNIT, speed_value)} once the "
                   f"Hydroponic Farm is built{crop_next}.")
    add("Refills", "Every noni growth and crop refill missed while the game is closed is added, without a cap, "
                   "when it is next played.")

    # -- Collectibles / Mushrooms --------------------------------------------------------
    add("Mushrooms", "About one thing appears a minute at any speed (none while paused or closed); 30% of them are "
                     "mushrooms (all of them in the rain). A mushroom is red 8% of the time (35 food) and brown "
                     "92% (6 food); one of each at a time; children pick them. Unpicked, it is gone after "
                     "1 minute 30 seconds.")
    if village.has(GOLDEN):
        add("Mushrooms", f"The patcher's \"{gm.feature_name(GOLDEN)}\" is in the game: there is a secret to find.")
    add("Mushrooms", f"Mushrooms found in this village: {_i32(data, MUSHROOMS_FOUND):,}.")
    add("Collectibles", "The other 70% are collectibles: 82% common, 13% uncommon, 5% rare. The lab set appears "
                        "only once the Knowing Totem is built. Unpicked, one is gone after 1 minute 30 seconds.")

    # -- Tech points ---------------------------------------------------------------------
    add("Tech points and effects", f"Tech points: {_i32(data, TECH):,}.")
    add("Tech points and effects", (
        f"Research gives the researcher's Research skill ÷ 11, ÷ 9 or ÷ 7 at Science level 1, 2 or 3, "
        f"{'twice that' if speed == gm.FAST else ('0.6 of that' if speed == gm.SLOW else 'as it is')} on {on} "
        "speed, plus a bonus from the lab's items; while catching up ÷ 7, ÷ 7 or ÷ 5, and only once the "
        "Knowing Totem is built."))
    add("Tech points and effects", gm.patch_words(village, LEARNING, "learning never fails"))
    add("Tech points and effects", (
        f"Divine Energy: {_i32(data, ENERGY):,} of {_i32(data, ENERGY_CAP):,}. Each believer adds 1 {gm.every(UNIT, speed_value)}, "
        "3 more at Devotion 50 or more and 5 more at 88 or more."))

    # -- Food earned ---------------------------------------------------------------------
    add("Food earned", f"Each believer eats 2 food every {unit} on {on} speed ({2 * 3600 / (60 * speed):g} an hour); "
                       "at 500 food or less only half the time. Heathens eat nothing.")

    # -- Time away and Time Warp ---------------------------------------------------------
    add("Time away and Time Warp", f"Last played: {gm.when(last)}, " + ("paused." if paused else f"on {on} speed."))
    if paused:
        add("Time away and Time Warp", "Saved paused: the time away is not counted when it is next played; "
                                       "nothing ages, grows or comes due.")
    else:
        away = max(0.0, village.now - last)
        counted = counted_away(away, speed)
        add("Time away and Time Warp", (
            f"If it were played now: {gm.duration(away)} away, of which {gm.duration(counted)} counts"
            + (f" ({counted / (60 * speed) / 20:.1f} years of the villagers' lives)." if counted else ".")))
    add("Time away and Time Warp", (
        f"On {on} speed time away counts in full up to {gm.duration(FULL_AWAY[speed], exact=True)}; from then to "
        f"24 hours it counts as only {gm.duration(BAND_AWAY, exact=True)}; the most it ever counts is 24 hours, "
        f"{DAY / (60 * speed) / 20:g} years on {on} speed, however long the game was closed. Heathens do not age "
        "while catching up."))
    add("Time away and Time Warp", (
        "While catching up, each counted age unit runs eating, belief, Divine Energy, sickness and births, and "
        "4 jobs for every healthy villager of 14 or more; island events, mushrooms, collectibles and weather "
        "do not run."))
    add("Time away and Time Warp", (
        f"Time Warp (the patcher's Origins upgrades): each one adds {TIME_WARP_YEARS[speed]} years on {on} speed "
        "(3 on Slow, 6 on Normal, 12 on Fast), past the time-away limits, and is refused while paused; the "
        "added time runs the same catch-up as time away " + UNSURE + "."))

    # -- Island events -------------------------------------------------------------------
    first = (" The first comes 15 minutes after the village is made and the second 30 minutes after it;"
             if _i32(data, EVENTS_SEEN) < 2 else "")
    add("Island events", f"Next island event: {due(EVENT_NEXT)}.{first} Island events come every 8 to 15 whole "
                         "hours at any speed. Paused time does not count; time the game is closed does, and an "
                         "overdue event happens once when it is next played.")

    for line in EVENT_LINES:
        add("Island events", line)
    add("Island events", gm.patch_words(
        village, STORY, "Pick Island Event chooses the event and its outcome, among events whose conditions hold"))

    # -- Other ---------------------------------------------------------------------------
    for line in ODDS_LINES:
        add("Other", line)
    add("Other", f"An age unit is {unit} and a year {gm.duration(20 * 60 * speed)} on {on} speed: ages, pregnancies "
                 "(40 units), noni and crops follow the speed; mushrooms, collectibles and island events do not.")
    return out
