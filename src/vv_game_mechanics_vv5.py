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
     "if none qualifies, nothing happens.", True),
    ("Rescue: with the sexes out of balance or fewer than 3 believers, 6% of events become Chutes Without Ladders "
     "instead.", True),
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
     "(accept) are 50/50. Vision faith +20 to +39; Strange Crystals +2,000 to 2,999 tech points; Pesky Critter "
     "-500 to -2,999 tech points; Mushroom Day +50 to 99 food and -500 to -1,499 tech points.", True),
    ("Heathen Toy +20 to 29 Research or Devotion; Cracked Mask (fix it) -20 to 30 health; Barrels and Chutes up to "
     "3 ten-year-olds, each 50% a boy, with one random skill at 5 to 9 (a heathen barrel's babies start at faith "
     "-55); a newcomer is 18, 50% a man, with a random skill at 80 to 84.", False),
)
LIFE_LINES = (
    ("Sickness each age unit: 0.28%, 0.16% or 0.06% at Medicine 1, 2 or 3, 1.5% more from 50, 58 or 66 years; on "
     "Easy a quarter of that.", True),
    ("Old age: from 55, 63 or 71 years (Medicine 1, 2, 3), each birthday past it carries a death roll, the chance rising 10% for each year over.", False),
    ("A believer who is not sick regains 1 health half the age units, 75% while the fire burns, every one at "
     "Medicine 3 or on Easy; old villagers a fifth of that. At 500 food or less a believer loses 1 health 15% of "
     "age units.", True),
    ("Belief each age unit: down 37% with food under 10, 10% at 250 or less, 15% when sick, (12 - believers)% "
     "under 12 believers; up 20% at 8,000 food or more, 30% with the Idol, 10% or 20% at statue stage 1 or 2, "
     "10/20/30% at Spirituality 1/2/3, (believers ÷ 5)% at 12 or more. A drop is skipped half the time below "
     "belief 5, a rise 70% of the time above 75.", True),
    ("A believer turns heathen at belief 0 or less; a new villager's starting faith is 30 to 59.", False),
    ("Conception after an embrace: (Breeding - 50 + 50 x Medicine level + 1) in 300 (17%, 33% or 50% at Breeding "
     "50); the village's first is certain; a mother of 50 or more never conceives. At Medicine 3: 93% single, "
     "5.3% twins, 1.8% triplets.", True),
    ("A job succeeds at skill + 33 out of 100 (+ 66 if they like learning, + 16 if they dislike it), + 15 or + 30 "
     "at Learning level 2 or 3.", True),
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
    add("Food sources", f"Food in storage: {_i32(data, FOOD):,}.", True)
    noni = _i32(data, NONI)
    add("Food sources", f"Noni bushes: {noni:,} of {NONI_CAP:,}; a pick gives {max(2, noni // 100)} food now (the noni "
                        f"÷ 100, at least 2), a gathering {min(noni, 30)} (up to 30), and takes as many noni.", True)
    add("Food sources", "Noni can be picked once the granary is built.")
    crops = _i32(data, CROPS)
    harvest = {gm.FAST: 10, gm.NORMAL: 7, gm.SLOW: 4}[speed]
    add("Food sources", f"Hydroponic Farm crops: {crops:,} of {CROPS_FULL}; a harvest gives {harvest} food on {on} speed "
                        "(7 while catching up) and takes as many crops. Fishing at the lake: 4 food a fish.", True)
    add("Food sources", "Food Mastery raises every food gain by half (level 2) or doubles it (level 3).", True)

    # -- Refills -------------------------------------------------------------------------
    if paused:
        add("Refills", gm.PAUSED_NOTE, True)
    add("Refills", f"Noni: +2 {gm.every(UNIT, speed_value)}, up to {NONI_CAP:,} (empty to full in "
                   f"{gm.duration(NONI_CAP // 2 * 60 * speed)}); next {due(NONI_NEXT)}.", True)
    crop_next = "" if not paused and real(CROPS_NEXT) <= village.now else f"; next {due(CROPS_NEXT)}"
    add("Refills", f"Crops: refilled to {CROPS_FULL} {gm.every(CROP_UNITS * UNIT, speed_value)} once the Hydroponic "
                   f"Farm is built{crop_next}.", True)
    add("Refills", "The Hydroponic Farm is " + ("built." if farm else "not built yet."))

    # -- Mushrooms / Collectibles --------------------------------------------------------
    add("Mushrooms", "About one thing appears a minute at any speed, twice as often in some weather; none while "
                     "paused or closed. 30% are mushrooms (all of them in the rain): brown 92% for 6 food, red 8% "
                     "for 35, counted when they reach the food bin. Unpicked, a thing is gone after 1 minute 30 "
                     "seconds.", True)
    if village.has(GOLDEN):
        add("Mushrooms", f"The patcher's \"{gm.feature_name(GOLDEN)}\" is in the game: there is a secret to find.")
    add("Mushrooms", f"Mushrooms found in this village: {_i32(data, MUSHROOMS_FOUND):,}.", True)
    add("Collectibles", "The others are collectibles: 82% common, 13% uncommon, 5% rare. One set of 24 can always "
                        "appear; a second set of 24 only once the Knowing Totem is built (then half from each). A "
                        "piece already found gives +10, 50 or 150 Divine Energy from the first set, +100, 250 or "
                        "1,500 tech points from the second.", True)
    add("Collectibles", "The Earthquake God Power drops one collectible 10 seconds after it is cast: 72% uncommon, "
                        "28% rare.", True)
    add("Collectibles", "The Earthquake also raises every villager's belief by 2 to 8.")

    # -- Tech points and Divine Energy ---------------------------------------------------
    add("Tech points and effects", f"Tech points: {_i32(data, TECH):,}.", True)
    add("Tech points and effects", (
        f"Research gives the researcher's skill ÷ 11, ÷ 9 or ÷ 7 at Science 1, 2 or 3, "
        f"{'twice that' if speed == gm.FAST else ('0.6 of that' if speed == gm.SLOW else 'as it is')} on {on} "
        "speed, plus up to half the lab's items and, while the fire burns, 1 more 10% of the time; while catching "
        "up ÷ 7, ÷ 7 or ÷ 5. In play 2% of tries injure (0 to 9 health)."), True)
    add("Tech points and effects", "While catching up, nobody researches before the Knowing Totem is built, and "
                                   "nobody picks noni before the Hungry Totem.")
    if village.has(LEARNING) is not False:
        add("Tech points and effects", gm.patch_words(village, LEARNING, "learning never fails"))
    add("Tech points and effects", (
        f"Divine Energy: {_i32(data, ENERGY):,} of {_i32(data, ENERGY_CAP):,}. Each believer adds 1 "
        f"{gm.every(UNIT, speed_value)}, 4 at Devotion 50 or more, 9 at 88 or more (1 more at 8,000 food on Medium, "
        "or on Hard); Honoring adds 3, 7 or 12. The cap is 5 x (believers + 2), more with the statue, the Idol, "
        "Spirituality and the first set's pieces, at most 1,000."), True)
    add("Tech points and effects", "God Powers cost 10, 25, 50, 100, 150, 300, 400, 500, 600, 700 and 800.")

    # -- Food earned ---------------------------------------------------------------------
    add("Food earned", f"Each believer eats 2 food every {unit} on {on} speed ({2 * 3600 / (60 * speed):g} an hour); at "
                       "500 food or less only half the time; on Medium at 8,000 food or more, or on Hard, 2 more 76% "
                       "of the time; never on Easy. Heathens skip it.", True)

    # -- Time away and Time Warp ---------------------------------------------------------
    out.extend(gm.time_away(village, last, speed_value,
                            "Saved paused: the time away is not counted when it is next played; nothing ages, grows "
                            "or comes due.", unit_seconds=20 * 60 * speed))
    for n, fact in enumerate(out):
        if fact.text.startswith("Saved paused:"):
            out[n] = gm.Fact(fact.group, fact.text, True)
    add("Time away and Time Warp", "While catching up, each counted age unit runs the believers' life (eating, belief, "
                                   "Divine Energy, sickness, births) and 4 jobs: crops 7 food, research ÷ 7, ÷ 7 or "
                                   "÷ 5, no lab mishaps.", True)
    add("Time away and Time Warp", "Every noni growth and crop refill missed while the game was closed is added when "
                                   "it is next played, with no limit on how many: noni stop at 1,000, crops at 800.",
        True)
    add("Time away and Time Warp", "Heathens never age, while catching up or otherwise (the stock game's design).", True)
    out.append(gm.time_warp_line(speed_value))

    # -- Island events -------------------------------------------------------------------
    first = (" The first comes 15 minutes after the village is made and the next 30 minutes after it;"
             if _i32(data, EVENTS_SEEN) == 0 else "")
    add("Island events", f"Next island event: {due(EVENT_NEXT)}.{first} Island events come every 8 to 15 whole hours, "
                         "each equally likely, at any speed; paused time does not count.", True)
    for line, ok in EVENT_LINES:
        add("Island events", line, ok)
    weather = {gm.FAST: "1.5 to 3", gm.NORMAL: "3 to 6", gm.SLOW: "5 to 10"}[speed]
    add("Island events", f"Weather events last {weather} minutes on {on} speed.", True)
    if village.has(STORY) is not False:
        add("Island events", gm.patch_words(village, STORY, "Pick Island Event chooses the event"))

    # -- Other ---------------------------------------------------------------------------
    for line, ok in LIFE_LINES:
        add("Other", line, ok)
    add("Other", f"An age unit is {unit} and a year {gm.duration(20 * 60 * speed)} on {on} speed: ages, pregnancies, "
                 "noni, crops, weather and the fire follow the speed; mushrooms, collectibles and island events do "
                 "not.", True)
    return out
