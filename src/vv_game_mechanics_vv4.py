"""Game Mechanics for The Tree of Life (VV4): read-only lines from one save (src/vv_game_mechanics.py).

THE SAVE.  A 24-byte header -- "ldwg", ..., the clock's base as an int64 Unix time at 0x08 -- then the
game state: state field X is file offset X + 0x10.  The clock counts real seconds from the base, so a
stamp v is the real moment base + v.  FILE offsets: speed 0x17120 (3 Fast, 6 Normal, 10 Slow; + 999
paused), difficulty 0x17104 (0 Easy, 1 Medium, 2 Hard), the last world tick 0x17100, the next world tick
0x170F4, food 0x85C, tech points 0xBCD0, tech levels 0xBCB8 (0 Science, 1 Medicine, 2 Learning, 4 Food
Mastery), Mushrooms Found 0x874, island events seen 0x884, blackberries 0x17108, the next island event
0x170F0.

THE RULES: the coordinator's verified spec mech_vv4\\spec.md v2 (2026-10-23).  A line built only from what
it marks EMULATED, or from the save, is verified; anything READ carries UNCONFIRMED, and nothing the spec
only guessed (a collection's name, what a flyer is) is shown at all (the owner: do not infer).  Handlers the stock game never fires and events that never happen are not listed.
"""
from __future__ import annotations

import struct

import vv_game_mechanics as gm
import vv_save_backup

GAME = 4
SPEED, LAST_TICK, NEXT_TICK, DIFFICULTY = 0x17120, 0x17100, 0x170F4, 0x17104
FOOD, TECH, LEVELS = 0x85C, 0xBCD0, 0xBCB8
MUSHROOMS_FOUND, EVENTS_SEEN = 0x874, 0x884
BERRIES, EVENT_NEXT = 0x17108, 0x170F0
SCIENCE, MEDICINE, LEARNING_TECH, FOOD_MASTERY = 0, 1, 2, 4
BERRY_CAP = 1000
GOLDEN = "vv4_super_secret_golden_mushroom"
LEARNING = "vv4_learning_never_fails"
SCALES = "vv4_complete_scales_golden_fish"
STORY = "vv4_story_cheat_upgrades"

# (line, verified)
EVENT_LINES = (
    ("Which event: every event whose conditions hold is equally likely (1 in the number of them; Aspiring Doctor "
     "counts 6 times). Rescue: with one sex down to 2 or fewer, or fewer than 3 villagers, 6% more become "
     "Daredevil Barrel, even when it could not otherwise happen.", gm.RUNNING),
    ("Rolled results: Arc of Colors (run right) 50% a fall (-25 to 44 health), 50% +300 food; Sealed Box (swim "
     "it back) 50% +5000 tech points, 50% the villager is lost; Innovation in Construction or Farming (try it) "
     "60% a skill gain, 40% -75 to 149 health.", gm.RUNNING),
    ("Creeping Mold -100 food (or all of it); Mysterious Footprints +300 food, -300 food, +2000 or -2000 tech "
     "points; A Closer Look +350 berries; Robber Crab (cut the tail) healing for several, (let go) Food Mastery "
     "+1 level; Phosphorescent Fungi (throw away) Research +40 to 49, sick, -15 to 19 health, (admire) some fall "
     "sick; Stinging Wasps some lose 10 to 19 health.", False),
    ("Village & Tree Malaise (fewer than 3 tree stages) some lose 5 to 14 health or fall sick; Euphoria (3 or "
     "more) everyone cured and fully healed; Pure Sea Air everyone cured; Cold Snap (the fire lit) puts the fire "
     "out; Daredevil Barrel (room, the stream restored, some debris) up to 3 babies; Abandoned Infants (6 women, "
     "room) babies for 6 women.", False),
    ("Day of Honor needs 2 graves, Banyan Festival 500 mushrooms found and 3 tree stages; Allergy Season, Isola "
     "Day, Blessings Day, Rainy Season and Monsoon change nothing stored. Pink Shell, Calabash, Faces in the "
     "Night, Screaming Baby, Wet Book, The Lie, Aspiring Doctor, Aspiring Scientist, Pretty Shell, Legendary "
     "Stranger, Climber, Mosquito Larvae and Tough Lessons have a fixed result for each choice.", False),
)
STEW_LINES = (
    ("Stews need 3 herbs and fresh water in a cooked pot; a ready stew is gone 5 minutes later. Spicy x3: runs to "
     "the stream; spicy, spicy, sweet: every adult comes; spicy, spicy, soapy: has got to go; spicy, sweet, "
     "sweet: the whole village comes; spicy, sweet, soapy: the Grand Feast (a well-cooked pot and the 4 feast "
     "items); spicy, soapy, soapy: the soapy-stew reaction.", gm.RUNNING),
    ("Sweet x3: honours the tree; sweet, sweet, soapy: the children get hiccups; sweet, soapy, soapy: heals 25 to "
     "59 health (5 to 14 with under 100 food), then no stew for 10 minutes; soapy x3: sick, then no stew for 10 "
     "minutes. In salt water, pulpy vines x3 make soap; any other mix tastes nasty or too salty.", gm.RUNNING),
)
LIFE_LINES = (
    ("A baby is born on the 41st age unit after conception. Conception after an embrace: (Parenting + 50 x "
     "(Medicine level - 1) + 1) in 300 (17% at Parenting 50 and Medicine 1). At Medicine 3: twins 5.25%, "
     "triplets 1.75%.", gm.RUNNING),
    ("A villager with food and not sick regains 1 health half the age units (75% while the Fire Pit burns, every "
     "one at Medicine 3 or on Easy); the elderly (50, 58 or 66 years) a fifth of that. Sickness each age unit: "
     "0.27%, 0.17% or 0.065% at Medicine 1, 2 or 3, 1.5% more for the elderly, a quarter on Easy. A sick "
     "villager loses 1 health 61% of age units and is never cured by time, except on Easy (25%).", gm.RUNNING),
    ("A job succeeds at skill + 34 out of 100 (+ 67 if they like learning, + 17 if they dislike it), + 15 or + 30 "
     "at Learning level 2 or 3; a success gains (70 - skill) ÷ 9 (at least 7 at skill 0), twice that if they "
     "like learning, half if they dislike it.", gm.RUNNING),
    ("Building: a hut needs 2000 -- the first hut gains 12 a visit, the second 4, the third 1; the clothing hut "
     "12, the Love Shack 200, the nursery and the hospital 50. Babies need the Love Shack; women of 50 or more "
     "cannot conceive; a baby is of the rarer sex when it is down to 2 or fewer. The Fire Pit stays lit 10, 20 "
     "or 33 hours 20 minutes on Fast, Normal or Slow. A research try injures (0 to 9 health) 2% of the time.",
     False),
)


# Hidden villager stats (the coordinator's specs hidden_vv4\spec.md and likes_all, 2026-10-23):
# (line, what stands behind it -- gm.RUNNING, gm.OWNER, or False for UNCONFIRMED).
HIDDEN_LINES = (
    ("Each villager's hidden number (1 to 183, rolled at every creation, not inherited) sets how it starves, "
     "its voice and its grave or ghost spot; the villagers' numbers are below.", gm.RUNNING),
    ('Liking learning makes a skill try succeed at skill + 67% instead of + 34%; disliking it, + 17%; a '
     'success gains twice as much when it is liked, half when disliked.', gm.RUNNING),
    ('Disliking work makes 78.5% of job picks end in doing nothing (29% otherwise, at Farming 50). A skill '
     'chosen on the Details screen wins 86% of the time; Parenting is picked on its own only when it is the '
     'chosen one.', gm.RUNNING),
    ('Disliking medicine: a healer considers Healing only half the time, and a patient refuses the cure half '
     'the time. Disliking wood, fish, the ocean, swimming, fruit, berries, plants, lifting or rocks makes a '
     'villager refuse that job. Running, rain, dancing, jumping, stories, frogs, fire, children and the others '
     'change reactions; any effect on outcomes is not yet worked out.', False),
    ("A baby starts with one skill at 5 to 7 (4 to 6 when both parents' best is the same) from the mother's "
     "best 49 times in 50, never Parenting; its family number is the mother's.", False),
    ('Sick: -1 health on 61% of age units, 19% at 20 health or less. Health comes back on half the age units '
     '(75% with the Fire Pit burning, every one at Medicine 3 or on Easy), a fifth of that for the elderly.', gm.RUNNING),
    ('The Fire Pit burns 10, 20 or 33 hours 20 minutes on Fast, Normal or Slow; a drop on the lit pit fills it '
     'again; while it burns each research job gives 1 more tech point 10% of the time.', False),
)

# Chance and timers (the coordinator's spec mech_vv4\\spec.md, "Chance and timers (v2.2)"):
# (line, verified on the running game's path); the full index of every roll is in the claims export.
CHANCE_V4 = (
    ("Every roll that changes play is in the groups above, with its odds: the spawn roll each frame (4 in "
     "6,000, a second one when the rain is heavy), mushroom or collectible, the Golden Fish, the island event "
     "and its outcomes, eating, health, sickness, old age, the skill roll, the snack, conception and twins, "
     "the Nursery School and the stews.", gm.RUNNING),
    ("Island events: Phosphorescent Fungi (admire) makes each villager sick at 30%; Mosquito Larvae (soap) at "
     "25%; Village & Tree Malaise at 20%, and each at 10% loses 5 to 14 health; Stinging Wasps: each at 50% "
     "loses 10 to 19 health; Robber Crab (cut the tail): each at 80% gains 5 to 9 Healing.", False),
    ("A new village: one of the first five villagers has a 30% chance of liking running. Every 40 seconds each "
     "villager's queue of actions is refreshed. About 2,000 more rolls (walk targets, animation lengths, job "
     "and idle choices, particles, speech): not individually worked out.", False),
    ("Timers: the second island event 30 minutes after the first, then 8 to 15 hours, at any speed; the world "
     "tick (berries, debris, Nursery School) and the age unit 3, 6 or 10 minutes; a birth on the 41st age "
     "unit; a ghost visit every 50 to 58 minutes; the hummingbird every 3 to 5 minutes (23 to 25 after Decorate "
     "Tree).", gm.RUNNING),
    ("A new village's first island event 15 minutes after it is made; an item lies 1 minute 30 seconds; a stew "
     "keeps 5 minutes and a healing or sick stew locks the villager out for 10; the Fire Pit 10, 20 or 33 hours "
     "20 minutes; clear weather 4 to 15, 8 to 30 or 13 to 50 minutes and other weather 1.5 to 3, 3 to 6 or 5 to "
     "10 minutes on Fast, Normal or Slow; the wind flutes play in fog every 30 to 45, 60 to 89 or 100 to 148 "
     "seconds.", False),
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
    add = lambda group, text, ok=False: out.append(gm.Fact(group, text, ok))  # noqa: E731
    mastery_words = {2: " (Food Mastery level 2: half as much again)", 3: " (Food Mastery level 3: doubled)"}.get(
        mastery, "")

    # -- Food sources --------------------------------------------------------------------
    add("Food sources", f"Food in storage: {_i32(data, FOOD):,}.", gm.SAVE)
    berries = _i32(data, BERRIES)
    add("Food sources", f"Blackberries: {berries:,} of {BERRY_CAP:,}; picking brings {food(max(2, berries // 100))} food "
                        f"now (the berries ÷ 100, at least 2; picking stops below 3), a harvest {food(min(30, berries))} "
                        f"(up to 30){mastery_words}.", gm.RUNNING)
    add("Food sources", f"Stomping or shaking down fruit brings {food(3)}; the fishing net {food(4)} a fish, or {food(8)} for "
                        "a Golden Fish: a (2 x fish scales + 1)% chance (3% with 1 scale, 25% with 12, none with 0)."
                        + mastery_words, gm.RUNNING)
    add("Food sources", f"Catching a crab brings {food(35)}." + mastery_words)
    if village.has(SCALES) is not False:
        add("Food sources", gm.patch_words(village, SCALES, "a Golden Fish needs all 12 scales"))

    # -- Refills -------------------------------------------------------------------------
    if paused:
        add("Refills", gm.PAUSED_NOTE, gm.RUNNING)
    add("Refills", f"Blackberries: +2 {gm.every(360, speed_value)}, up to {BERRY_CAP:,}; the stream gathers 2% more "
                   "debris at the same time, up to 100%.", gm.RUNNING)
    add("Refills", f"Next growth: {due(NEXT_TICK)}.", gm.SAVE)

    # -- Mushrooms / Collectibles --------------------------------------------------------
    add("Mushrooms", "While playing (not paused), something appears about every 45 seconds at any speed, twice as "
                     "often on wet ground; at most 2 at a time, each gone after 1 minute 30 seconds. 30% are "
                     f"mushrooms (all of them in rain or on wet ground): small 92% for {food(6)} food, large 8% for "
                     f"{food(35)}.", False)
    if village.has(GOLDEN):
        add("Mushrooms", f"The patcher's \"{gm.feature_name(GOLDEN)}\" is in the game: there is a secret to find.")
    add("Mushrooms", f"Mushrooms found in this village: {_i32(data, MUSHROOMS_FOUND):,}.", gm.SAVE)
    add("Collectibles", "The other 70% are collectibles: 82% common, 13% uncommon, 5% rare. A piece already found "
                        "gives 100, 250 or 1,500 tech points by rarity. Fish-scale spots count only in odd clock "
                        "hours.", gm.RUNNING)
    add("Collectibles", "Once the Mausoleum Mural set is complete, a buried villager's ghost brings a collectible every "
                        "50 to 58 minutes (nothing if more than an hour overdue).", gm.RUNNING)
    add("Collectibles", "The four collections are the Fish Scale, Lab Equipment, Mausoleum Mural and Wind Flute sets; "
                        "ghost visits need the Mausoleum Mural set complete.", gm.RUNNING)
    add("Collectibles", "Fog increases collectible spawning if you have Wind Flute pieces collected.", gm.OWNER)
    add("Collectibles", "With 3 or more tree stages a hummingbird flies by every 3 to 5 minutes (every 23 to 25 once "
                        "Decorate Tree is done); it changes nothing.", gm.RUNNING)
    add("Collectibles", "How much each Wind Flute piece adds in fog, and what a cold snap does, is not yet worked out. "
                        "Each complete collection raises the population limit by 5, all four by 25.")

    # -- Tech points ---------------------------------------------------------------------
    add("Tech points and effects", f"Tech points: {_i32(data, TECH):,}.", gm.SAVE)
    lvl = level[SCIENCE]
    divisor = {1: 11, 2: 9, 3: 7}.get(lvl)
    if divisor:
        add("Tech points and effects", (
            f"Research gives the researcher's skill ÷ {divisor} at Science level {lvl}, "
            + {gm.FAST: "twice that on Fast speed", gm.NORMAL: "as it is on Normal speed",
               gm.SLOW: "0.6 of it on Slow speed"}[speed]
            + f", rounded down; 10% of the time 1 more while the Fire Pit burns; while catching up "
              f"÷ {5 if lvl >= 3 else 7}."), gm.RUNNING)
        add("Tech points and effects", "Some effect on a villager triples their research for 4 minutes.")
    if village.has(LEARNING) is not False:
        add("Tech points and effects", gm.patch_words(village, LEARNING, "no skill roll fails"))
    add("Tech points and effects", "Nursery School: each child gains the teacher's five skills added up ÷ 240 an hour "
                                   "at any speed, in skills under 50.", gm.RUNNING)

    # -- Food earned ---------------------------------------------------------------------
    add("Food earned", f"Each villager eats 2 food every {gm.duration(60 * speed)} on {on} speed "
                       f"({2 * 3600 / (60 * speed):g} an hour); at 500 food or less half the time, and otherwise loses "
                       "1 health 30% of the time; on Medium at 8,000 food or more, or on Hard, 2 more 76% of the "
                       "time, never on Easy. A snack (below full health) costs 1 food and heals 1 half the time.",
        True)

    # -- Time away and Time Warp ---------------------------------------------------------
    out.extend(gm.time_away(village, real(LAST_TICK), speed_value,
                            "Saved paused: no age is counted for the time away, and the timers move on with the "
                            "pause.", unit_seconds=20 * 60 * speed))
    add("Time away and Time Warp", "While catching up: aging, eating, sickness, births and 4 jobs per age unit for "
                                   "adults.")
    add("Time away and Time Warp", "Every blackberry growth missed while the game was closed is added when it is next "
                                   "played, with no limit on how many, up to 1,000.", gm.RUNNING)
    out.append(gm.time_warp_line(speed_value))

    # -- Island events -------------------------------------------------------------------
    first = " (30 minutes while none has been seen yet)" if _i32(data, EVENTS_SEEN) == 0 else ""
    add("Island events", f"Next island event: {due(EVENT_NEXT)}.", gm.SAVE)
    add("Island events", f" Island events come every 8 to 15 whole hours, each "
                         f"equally likely, at any speed{first}; paused time does not count; after time away at most "
                         "one happens.", gm.RUNNING)
    for line, ok in EVENT_LINES:
        add("Island events", line, ok)
    if village.has(STORY) is not False:
        add("Island events", gm.patch_words(village, STORY, "Pick Island Event chooses the event and its rolls"))

    # -- Other ---------------------------------------------------------------------------
    for line, ok in HIDDEN_LINES:
        add(gm.HIDDEN, line, ok)
    out.extend(gm.starvation_lines(village, 0x8, gm.RUNNING))
    for line, ok in CHANCE_V4:
        add("Chance and timers", line, ok)
    for line, ok in STEW_LINES + LIFE_LINES:
        add("Other", line, ok)
    out.append(gm.old_age_line("55, 63 or 71 years (Medicine 1, 2, 3)"))
    add("Other", f"An age unit is {gm.duration(60 * speed)} and a year {gm.duration(20 * 60 * speed)} on {on} speed.", gm.RUNNING)
    return out
