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
import vv_game_mechanics_death as death
import vv_game_mechanics_life as life
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
    ("Stews need 3 herbs and fresh water in a cooked pot; a ready stew is gone 5 real-life minutes later at every "
     "speed. Spicy x3: runs to "
     "the stream; spicy, spicy, sweet: every adult comes; spicy, spicy, soapy: has got to go; spicy, sweet, "
     "sweet: the whole village comes; spicy, sweet, soapy: the Grand Feast (a well-cooked pot and the 4 feast "
     "items); spicy, soapy, soapy: the soapy-stew reaction.", gm.RUNNING),
    ("Sweet x3: honours the tree; sweet, sweet, soapy: the children get hiccups; sweet, soapy, soapy: heals 25 to "
     "59 health (5 to 14 with under 100 food), then no stew for 10 real-life minutes; soapy x3: sick, then no stew "
     "for 10 real-life minutes. In salt water, pulpy vines x3 make soap; any other mix tastes nasty or too salty.", gm.RUNNING),
)
# The stew pot (0x4D76D8) and its herb table (0x4D8220), the same design as The Secret City's potion: a stew
# made (0x42EDE0) sets the table's deadline +8 to the real clock 0x403750 + 300 (0x42F240, from 0x42EEB2); the
# table's update 0x42F1D0 empties the pot there (0x42F060 -> 0x42DA30, the herbs put back).  The pot's countdown
# (0x42E5D2) shows the time left (0x42F410) x the clock's rate / 6 (0x41DB00) as m:ss.  The table is not saved
# (its save and load slots are no-ops, 0x432380), so no save holds a stew to count down.
STEW_COUNTDOWN = {gm.FAST: "2:30", gm.NORMAL: "5:00", gm.SLOW: "8:20"}


def stew_pot_line(speed: int) -> str:
    return (f"A ready stew: the pot's on-screen countdown starts at {STEW_COUNTDOWN[speed]} on {gm.speed_name(speed)} "
            "speed (5:00 on Normal, 2:30 on Fast, 8:20 on Slow: what it shows changes with the speed), and the pot "
            "empties itself when it reaches 0:00. The save does not keep the pot.")


# The owner (2026-10-24).  In the code a villager dropped on the herb table (its drop slot 0x42F0F0) empties the
# pot through 0x42F060 -> 0x42DA30 and puts the herbs back, as in The Secret City.
GRATE_LINE = "The pot can be emptied by dropping a villager on the grate."
# The owner (2026-10-24): some stews can be reheated by putting another hot rock in the pot.
REHEAT_LINE = "Some stews can be reheated by putting another hot rock in the pot."
# The code.  The recipe 0x42ECA0 (via 0x42DBF0): stews 0-9 in fresh water (state 9), 10 = soapy x3 and 11 =
# pulpy vines x3 in salt water (state 0xA), 12 / 13 any other mix in salt / fresh water.  Each hot rock (item 6)
# adds 10 heat (+0xB1C, 0x42EAA7; only emptying the pot lowers it, 0x42DA76); 0x42DC80 has a stew ready at 10
# heat, the Grand Feast (4) at 20 with its 4 feast items, 10 and 11 at once.  The pot takes an item only while
# its hot state 0x18 is on (0x42EA61, read by 0x42DD50); state 0x18 lasts 600 game-clock seconds (0x46D530,
# table 0x46D5C0 -> 0x46D555, clock 0x41DB20).  Making a stew (0x42EDE0) ends states 0x18, 9 and 0xA
# (0x42EE5F..0x42EE7E); an unfinished Grand Feast instead turns 0x18 on again (0x42EE1D).  A rock that goes in
# while the pot is hot and its stew is ready makes the same stew again (0x42EAF1 -> vtable +0x2C = 0x42EDE0,
# the recipe read again from the 3 herbs kept), which sets the 300-second deadline again (0x42EEB2 -> 0x42F240);
# nothing counts the times.  What turns the hot state on for an already-made stew is not traced here (the only
# other writer is 0x42F4A0, a drop handler on the pot's boiling-water object, vtable 0x48E2F0 +0x28).
REHEAT_CODE_LINE = (
    "In the game's code: each hot rock adds 10 heat to the pot, which only emptying it takes away; a stew is ready "
    "at 10 heat, the Grand Feast at 20 with its 4 feast items, and the two salt-water mixes (soapy x3, pulpy "
    "vines x3) need no heat. The pot takes things only while it is hot: making a stew ends that, and an unfinished "
    "Grand Feast stays hot for 10 real-life minutes on Normal speed (5 on Fast, 16 minutes 40 seconds on Slow) "
    "after each thing added. A hot rock that goes into the hot pot while its stew is ready makes "
    "the same stew again and starts its 5 real-life minutes over; nothing limits how often, and no stew is left "
    "out of this.")
# "That villager can't eat more stew so soon." (string 0x203) is said when the villager dropped on the pot
# (0x42E920) is refused by the add-effect 0x460A90: the same stew's effect is already on them (0x45EB40) or they
# have 12 (+0x1E5C).  An effect ends at a real-clock deadline (0x403750 + its length, 0x460B60); saving ends every
# villager's effects first (0x4660C4 -> 0x45EAA0), so no save holds one.
CANT_EAT_LINE = (
    "\"That villager can't eat more stew so soon.\" is the game's answer when that villager already has the same "
    "stew's effect, or already has 12 effects: it lasts until that effect ends (10 real-life minutes at every speed "
    "for the healing and sick stews), for that villager and that stew only. Saving the game ends every villager's stew effects, so a save "
    "holds none to count down.")
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
     "cannot conceive; with 6 or fewer villagers a baby is of the more common sex when the other is down to 2 "
     "or fewer (see Births and gender). The Fire Pit stays lit 10, 20 "
     "or 33 hours 20 minutes on Fast, Normal or Slow. A research try injures (0 to 9 health) 2% of the time.",
     False),
)


# Hidden villager stats (the coordinator's specs hidden_vv4\spec.md and likes_all, 2026-10-23):
# (line, what stands behind it -- gm.RUNNING, gm.OWNER, or False for UNCONFIRMED).
HIDDEN_LINES = (
    ("Each villager's hidden number (1 to 183, rolled at every creation, not inherited) sets how it starves, "
     "its voice and its grave or ghost spot; the villagers' numbers are below.", gm.RUNNING),
    ("Learning: liking it takes a skill roll's success from 74% to 100% (at the same skill) and doubles the gain; "
     "disliking it, 57.6% and half the gain.", gm.RUNNING),
    ("Work: liking it takes a villager's idle self-picks from 18.7% to 5%, and a job you give them is always "
     "done; disliking it, 75.9% idle, and a job you give them is done 47.9% of the time while food is under "
     "8,000. A skill chosen on the Details screen wins 86% of the time.", gm.RUNNING),
    ("Medicine, disliked: a healer considers Healing half as often and cures about half as often. Wood, disliked: "
     "builders take huts 29% of the time instead of 70%, 41% stop half-way (\"Running away\"), and half of "
     "drops on the wood pile end in running away.", gm.RUNNING),
    ("Running: a liking adult walks at speed 300 (150 otherwise) and one who dislikes it at 40 -- 3.4, 6.7 or "
     "24.9 seconds for the same walk; children run unless they dislike it; the elderly always walk at 40. "
     "Jumping: liked, Dancing becomes 30 hops; disliked, every hop is skipped.", gm.RUNNING),
    ("Rain: liked, always \"Drinking rain\" in the rain; disliked, always \"Getting out of the rain\". Laundry: "
     "liked 38% of the time (11% otherwise), disliked never. Playing: liked, a child only plays; disliked, no "
     "dirt or sandcastle play. Dancing, disliked: never dances, and dance steps are cut from 5 other actions.",
     gm.RUNNING),
    ("Disliked fish, the ocean, swimming, berries or fruit: 60% run away from that farming job, and no water "
     "leisure; rocks, plants or lifting: 60% run away from clearing rubble and debris. Crowds: skips the "
     "Celebrating rally. Resting or sitting: a villager not feeling well paces (resting also blocks Relaxing).",
     gm.RUNNING),
    ("Disliked herbs or flowers: never \"Curious about the herbs\"; sand: no beach lounging; talking: no "
     "Chatting; fire: dropped on the fire pit, runs away (always when lit, 81% unlit); frogs: dropped on the "
     "cooking table, runs away (100% or 76%); children: \"Telling a story\" ends 99% of the time; stories: no "
     "story when either villager dislikes them.", gm.RUNNING),
    ("The other 46 likes and dislikes: no effect has been found in the running game.", False),
    ("A baby starts with one skill at 5 to 7 (4 to 6 when both parents' best is the same) from the mother's "
     "best 49 times in 50, never Parenting; its family number is the mother's.", False),
    ('Sick: -1 health on 61% of age units, 19% at 20 health or less. Health comes back on half the age units '
     '(75% with the Fire Pit burning, every one at Medicine 3 or on Easy), a fifth of that for the elderly.', gm.RUNNING),
    ('The Fire Pit burns 10, 20 or 33 hours 20 minutes on Fast, Normal or Slow; a drop on the lit pit fills it '
     'again; while it burns each research job gives 1 more tech point 10% of the time.', False),
    # The owner (2026-10-24); the Cold Snap's apply 0x414BD0 ends the fire (tail jmp 0x432620 on 0x4D867C).
    (gm.FIRE_OUT + " The Cold Snap island event (it needs the Fire Pit burning) puts it out.", gm.OWNER),
    (gm.FIRE_CLOSED, gm.OWNER),
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
    ("A new village's first island event 15 real-life minutes after it is made; an item lies 1 minute 30 real-life "
     "seconds; a stew keeps 5 real-life minutes (another hot rock starts them over) and a healing or sick stew "
     "locks the villager out for 10 real-life minutes; on Fast, Normal or Slow, the Fire Pit burns 10, 20 or 33 "
     "hours 20 minutes of real life, clear weather lasts 4 to 15, 8 to 30 or 13 to 50 real-life minutes and other "
     "weather 1.5 to 3, 3 to 6 or 5 to 10, and the wind flutes play in fog every 30 to 45, 60 to 89 or 100 to 148 "
     "real-life seconds.", False),
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
                     f"mushrooms (all of them in rain or on wet ground): brown 92% worth {food(6)} food, red (rare) 8% "
                     f"worth {food(35)}.", False)        # the 35 one is the game's rare mushroom ("You picked N rare mushrooms")
    if village.has(GOLDEN):
        add("Mushrooms", gm.golden_line(GOLDEN, "about 5 years of play"), gm.RUNNING)
    add("Mushrooms", f"Mushrooms found in this village: {_i32(data, MUSHROOMS_FOUND):,}.", gm.SAVE)
    add("Collectibles", "The other 70% are collectibles: 82% common, 13% uncommon, 5% rare. A piece already found "
                        "gives 100, 250 or 1,500 tech points by rarity. Fish-scale spots count only in odd clock "
                        "hours.", gm.RUNNING)
    # A ghost is not a buried villager (the owner, 2026-10-24): it takes a random grave's looks (0x414110).
    add("Collectibles", "Once the Mausoleum Mural set is complete, a ghost brings a collectible every 50 to 58 minutes "
                        "(nothing if more than an hour overdue); what a ghost is: under Death and graves.", gm.RUNNING)
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

    # -- Time away (catch-up): src/vv_game_mechanics_catchup.py, added by vv_game_mechanics.read -----

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
    for line, ok in STEW_LINES:
        add("Other", line, ok)
    add("Other", stew_pot_line(speed), gm.RUNNING)
    add("Other", GRATE_LINE, gm.OWNER)
    add("Other", REHEAT_LINE, gm.OWNER)
    add("Other", REHEAT_CODE_LINE, gm.RUNNING)
    add("Other", CANT_EAT_LINE, gm.RUNNING)
    for line, ok in LIFE_LINES:
        add("Other", line, ok)
    out.append(gm.old_age_line("55, 63 or 71 years (Medicine 1, 2, 3)"))
    add("Other", f"An age unit is {gm.duration(60 * speed)} and a year {gm.duration(20 * 60 * speed)} on {on} speed.", gm.RUNNING)
    clock = gm.later_clock(data, CLOCK, base, speed_value, _i32(data, STATS))
    out.append(gm.started_line(clock.created))
    out.extend(gm.later_puzzle_lines(PUZZLE_NAMES, lambda pid: struct.unpack_from("<ii", data, PUZZLE_ENTRIES + 8 * pid),
                                     PUZZLE_THRESHOLDS, clock))

    # -- The countdowns, and the people and clocks (src/vv_game_mechanics_life.py) ------------
    growth_at = None if paused else real(NEXT_TICK)
    event_at = None if paused else real(EVENT_NEXT)
    gm.with_due(out, "Next growth:", growth_at, "refill")
    gm.with_due(out, "Next island event:", event_at, "next")
    multiplier = 2.0 if mastery >= 3 else (1.5 if mastery == 2 else 1.0)
    collectibles, complete = life.collectible_lines(village, "100, 250 or 1,500 tech points")
    bonus = None if complete is None else 5 * complete + (5 if complete == 4 else 0)
    puzzles = []
    for pid, name in PUZZLE_NAMES.items():
        progress = _i32(data, PUZZLE_ENTRIES + 8 * pid)
        if 0 < progress < PUZZLE_THRESHOLDS[pid]:
            puzzles.append((name, progress, PUZZLE_THRESHOLDS[pid]))
    ctx = life.Context(
        village, speed_value, real(LAST_TICK), _i32(data, FOOD), low_food=500, extra_from=8000,
        sources=[life.Source("Blackberries", berries, BERRY_CAP, 2.0, growth_at, f"+2 {life.every_real(360, speed_value)}",
                             verified=gm.SAVE, step=2, interval=gm.real_seconds(360, speed_value),
                             next_at=real(NEXT_TICK), first_in=max(0, _i32(data, NEXT_TICK) - _i32(data, LAST_TICK)), rule=gm.RUNNING),
                 life.Source("The fishing net and the fruit", None, unlimited=True,
                             refill_words="no store of theirs is read here: they bring what the gatherers fetch",
                             verified=False)],
        tech=_i32(data, TECH), tech_words="Research brings them; a piece already found pays 100, 250 or 1,500 by rarity.",
        brown=6, red=35, red_share=0.08, mushrooms_an_hour=3600 / 45 * 0.30, mastery=multiplier,
        golden=village.has(GOLDEN) is True,
        mushroom_words="Something appears about every 45 real-life seconds while playing (twice as often on wet "
                       "ground), 30% of them mushrooms (all in rain), so about 24 mushrooms per real-life hour.",
        event_next=event_at,
        event_paused_left=max(0, _i32(data, EVENT_NEXT) - _i32(data, LAST_TICK)) if paused else None,
        event_rule="It comes 8 to 15 whole real-life hours after the last, each equally likely, at any speed; then every event "
                   "whose conditions hold is equally likely.",
        event_running="Paused time does not count; with the game closed it runs on, and after time away at most one "
                      "happens.",
        medicine=level[MEDICINE], elderly_from={1: 50, 2: 58, 3: 66}, old_age_from={1: 55, 2: 63, 3: 71},
        parents_from=18, sick_loss=(0.61, 0.19),
        sick_end="Time never cures a sickness except on Easy (25%); a healer or a healing stew does.",
        collectibles=collectibles,
        limit=life.limit_words(village, bonus, "5 for each complete collection, 25 with all four"),
        puzzles=puzzles,
        food_words="2 food a villager every age unit while there is more than 500; on Medium at 8,000 or more, or "
                   "on Hard, 2 more 76% of the time; never more on Easy; a snack below full health costs 1 more.",
        trips=[("blackberry picks", max(2, berries // 100)), ("fish in the net", 4), ("fruit stomps", 3)])
    out.extend(life.sections(ctx))
    out.extend(death.facts(village, medicine=level[MEDICINE], speed_value=speed_value, base=base))
    return out


# The game clock 0x4D6F18, saved by 0x41DAC0 at manager+0x8E8 (0x41F0BF) and loaded by 0x41DAA0 (0x41FCAB); the
# statistics block 0x4D6DE0 (manager+0x850), whose first field is the village's start, written from the wall
# clock 0x403750 by the new-village routine 0x41FEF0 (0x41FF35).  The puzzles 0x4D8BF8 (manager+0x160C0, by
# 0x438810: a dword, then each puzzle's progress and solve time); solved at the threshold each puzzle registers
# with (0x4386A0; The Grand Feast's 1 by 0x4386C0), the time stamped by Advance 0x438A30 from the game clock.
CLOCK, STATS, PUZZLE_ENTRIES = 0x8F8, 0x860, 0x160D4
PUZZLE_NAMES = {0: "The Cutting Tool", 1: "The Stream", 2: "Boiling Water", 3: "Soap Invented", 4: "The Butterflies",
                5: "The Frog Rescue", 6: "The Cooking Pit", 7: "Cloth Invented", 8: "The Nursery School",
                9: "The Mossy Rocks", 10: "The Grand Feast", 11: "Fishing Nets", 12: "Pruning the Tree",
                13: "Honoring the Tree", 14: "Purify Tree", 15: "Decorating the Tree"}
PUZZLE_THRESHOLDS = {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 5, 6: 1, 7: 1, 8: 1, 9: 5, 10: 1, 11: 1, 12: 1, 13: 1, 14: 1, 15: 3}
