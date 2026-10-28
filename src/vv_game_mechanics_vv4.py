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
import vv_game_mechanics_events as events
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

# The recipes 0x42ECF0 (herbs 0x1F spicy, 0x20 sweet, 0x21 soapy, 0x22 pulpy vines) and what each stew does, the
# stew's effect switch 0x41DEE0 (CPotion, vtable 0x48D5C4): 5 sends the villager "Burping up soap bubbles"
# (action 0xA1, 0x42E4AC) and counts the Soapy Stew achievement (0x41E02D); 9 says "I feel sick!" and sends them
# "Throwing up soapy stew!" (action 0x9F, 0x42E2A9) -- nothing in either sets the sickness flag +0x1C48.  The
# healing stew (8) and the soapy one (9) are kept 600 real-life seconds (0x41DF71, 0x41E0D6).
STEW_LINES = (
    ("A stew is 3 herbs in fresh water in the pot, heated by hot rocks (the heat rules are below). Spicy x3: runs "
     "to the stream; spicy, spicy, sweet: every adult comes; spicy, spicy, soapy: has got to go; spicy, sweet, "
     "sweet: the whole village comes; spicy, sweet, soapy: the Grand Feast (a well-cooked pot and the 4 feast "
     "items); spicy, soapy, soapy: \"Burping up soap bubbles\".", gm.RUNNING),
    ("Sweet x3: honours the tree; sweet, sweet, soapy: the children get hiccups; sweet, soapy, soapy: heals 25 to "
     "59 health (5 to 14 with under 100 food), and that villager cannot eat that stew again for 10 real-life "
     "minutes; soapy x3: \"I feel sick!\" and \"Throwing up soapy stew!\" (it does not make the villager sick), and "
     "the same 10 real-life minutes (real time, the same at every speed). In salt water, pulpy vines x3 make soap; any other mix tastes nasty or too "
     "salty.", gm.RUNNING),
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
            "empties itself when it reaches 0:00, 5 real-life minutes after the stew was made at every speed. The "
            "save does not keep the pot.")


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
    "out of this (the 5 minutes are real time, the same at every speed).")
# "That villager can't eat more stew so soon." (string 0x203) is said when the villager dropped on the pot
# (0x42E920) is refused by the add-effect 0x460A90: the same stew's effect is already on them (0x45EB40) or they
# have 12 (+0x1E5C).  An effect ends at a real-clock deadline (0x403750 + its length, 0x460B60); saving ends every
# villager's effects first (0x4660C4 -> 0x45EAA0), so no save holds one.
CANT_EAT_LINE = (
    "\"That villager can't eat more stew so soon.\" is the game's answer when that villager already has the same "
    "stew's effect, or already has 12 effects: it lasts until that effect ends (10 real-life minutes at every speed "
    "for the healing and sick stews), for that villager and that stew only. Saving the game ends every villager's stew effects, so a save "
    "holds none to count down.")
# Conception, births, health, sickness and the skill check's odds are under Chances and Births and gender; these
# are what those groups do not give.
# The skill check 0x462A80, one case per skill (jump table 0x4634B8): a success raises the skill by (70 - skill)
# divided by 18 for Farming (0x462CB7), Research (0x4633F0) and Building (0x4631C7), by 10 for Parenting
# (0x462EC2) and by 12 for Healing (0x46304F) -- the magic numbers 0x38E38E39 >> 34, 0x66666667 >> 34 and
# 0x2AAAAAAB >> 33 -- rounded toward 0, raised to 7 at skill 0; doubled for a villager who likes learning, halved
# for one who dislikes it; at 0 or less a roll of rand(100) <= 50 and then rand(100) >= skill gives 1 (0x462CFA).
# The buildings (0x431020..0x431372): every one needs 2,000 (the 0x7D0 each registers with 0x4386A0), and each
# build step Advances it [+0x24] times (0x43028D): Hut 1 12, Hut 2 4, Hut 3 1, the Clothing Hut 12, the Love Shack
# 200, the Nursery School and the Hospital 50.  The Fire Pit: lit for 72,000 game-clock seconds (0x4327F7, again on
# the pit fed while lit, 0x432882 -> 0x4328AA), the clock running at the speed (0x41DE70); research's extra point 0x464E87.
LIFE_LINES = (
    ("A success raises the skill by (70 - skill) ÷ 18 for Farming, Research and Building, ÷ 10 for Parenting and "
     "÷ 12 for Healing, rounded down (7 at skill 0); twice that for a villager who likes learning, half for one who "
     "dislikes it. When that comes to 0 (Farming, Research and Building from skill 53, Parenting from 61, Healing "
     "from 59, before the doubling or halving), a success gives 1 point 51.05% of the time when a second roll of 0 "
     "to 99 is at or above the skill, and nothing otherwise. The odds of the check itself are under Chances.",
     gm.RUNNING),
    ("Building: every building needs 2,000 build points; each build step adds 12 to Hut 1, 4 to Hut 2, 1 to Hut 3, "
     "12 to the Clothing Hut, 200 to the Love Shack and 50 to the Nursery School and the Hospital.", gm.RUNNING),
    ("The Fire Pit stays lit 10, 20 or 33 hours 20 minutes of real-life play on Fast, Normal or Slow speed; feeding "
     "the pit again while it burns starts that time over. While it burns each research job gives 1 more "
     "tech point 10.01% of the time, and health comes back more often (see Chances).", gm.RUNNING),
)


# Hidden villager stats (the coordinator's specs hidden_vv4\spec.md and likes_all, 2026-10-23):
# (line, what stands behind it -- gm.RUNNING, gm.OWNER, or False for UNCONFIRMED).
HIDDEN_LINES = (
    ("Each villager's hidden number (1 to 183, rolled at every creation, not inherited) sets how it starves, "
     "its voice and its grave or ghost spot; the villagers' numbers are below.", gm.RUNNING),
    # The skill check 0x462A80: liked learning (word 0x27) adds 66 (0x462AB9), disliked 16 (0x462AC6), else 33.
    ("Learning: liking it makes every skill check succeed at skill + 67 in 100 instead of skill + 34 (so from "
     "skill 33 always) and doubles the skill gained; disliking it, skill + 17 in 100 and half the gain (the checks "
     "and the gains are under Chances and Other).", gm.RUNNING),
    ("Work: liking it takes a villager's idle self-picks from 18.7% to 5%, and a job you give them is always "
     "done; disliking it, 75.9% idle, and a job you give them is done 47.9% of the time while food is under "
     "8,000. A skill chosen on the Details screen wins 86% of the time.", gm.RUNNING),
    ("Medicine, disliked: a healer considers Healing half as often and cures about half as often. Wood, disliked: "
     "builders take huts 29% of the time instead of 70%, 41% stop half-way (\"Running away\"), and half of "
     "drops on the wood pile end in running away.", gm.RUNNING),
    ("Running: a liking adult walks at speed 300 (150 otherwise) and one who dislikes it at 40 -- 3.4, 6.7 or "
     "24.9 seconds for the same walk (whether real time or on the game's clock was not traced: see the next line); children run unless they dislike it; the elderly always walk at 40. "
     "Jumping: liked, Dancing becomes 30 hops; disliked, every hop is skipped.", gm.RUNNING),
    ("Running: whether a walk's 3.4, 6.7 or 24.9 seconds are real time or on the game's clock was not traced.",
     False),
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
    # The conception 0x460990: the best skill (0x46AC20, the first highest above 0) of the mother 49 times in 50
    # (rand(50) != 0, 0x4609CD), else the father's; 5 to 7 (rand(3) + 5), or 4 to 6 when both parents' best is the
    # same skill (0x4609EE); a Parenting pick becomes no skill (index and level 0, 0x45E817).
    ("A baby starts with one skill at 5 to 7 (4 to 6 when both parents' best skill is the same one): the mother's "
     "best skill 49 times in 50, the father's 1 time in 50; when that skill is Parenting the baby starts with no "
     "skill.", gm.RUNNING),
)

# Chance and timers (the coordinator's spec mech_vv4\\spec.md, "Chance and timers (v2.2)"):
# (line, verified on the running game's path); the full index of every roll is in the claims export.
CHANCE_V4 = (
    ("Every roll that changes play is in its own group above, with its odds: the appearance roll each update of "
     "the village (Collectibles), mushroom or collectible (Mushrooms), the Golden Fish (Food sources), the island "
     "event and its outcomes (Island events), eating, health, sickness, old age, the skill check, conception, "
     "twins and the baby's sex (Chances, Births and gender), the snack (Food earned), the Nursery School (Tech "
     "points and effects) and the stews (Other).", gm.RUNNING),
    ("Every timer is in its own group too: island events (Island events), the world tick and the age unit "
     "(Refills, Villager timers), births (Births and gender), ghost visits and the hummingbird (Collectibles), how "
     "long an item lies (Mushrooms), the stews and the Fire Pit (Other), weather an event brings (Island "
     "events).", gm.RUNNING),
    ("A new village: one of the first five villagers has a 30% chance of liking running, and every 40 seconds "
     "each villager's queue of actions is refreshed (read from the coordinator's spec, not traced in the game's "
     "code here, so neither the 30% nor the 40 seconds' clock -- real time or the game's clock -- is proven: "
     "UNCONFIRMED).",
     False),
    ("Clear weather lasts 4 to 15, 8 to 30 or 13 to 50 real-life minutes on Fast, Normal or Slow speed, and the "
     "wind flutes play in fog every 30 to 45, 60 to 89 or 100 to 148 real-life seconds (read from the coordinator's "
     "spec, not traced in the game's weather code here).", False),
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

    # -- Food sources (the food in storage is under Vital statistics) ---------------------------
    berries = _i32(data, BERRIES)
    # Picking 0x464464 (the berries ÷ 100, at least 2), a harvest 0x4644EE (the berries, at most 30); either ends the
    # task below 3 berries (0x4644A9, 0x464522).  Every food gain goes through 0x41D920 (Food Mastery 2: + half,
    # 3: doubled).
    add("Food sources", f"Blackberries: {berries:,} of {BERRY_CAP:,}; picking brings {food(max(2, berries // 100))} food "
                        f"now (the berries ÷ 100, at least 2; picking stops below 3), a harvest {food(min(30, berries))} "
                        f"(the berries, at most 30, before Food Mastery){mastery_words}.", gm.RUNNING)
    add("Food sources", f"Stomping or shaking down fruit brings {food(3)}; the fishing net {food(4)} a fish, or {food(8)} for "
                        "a Golden Fish: a (2 x fish scales + 1)% chance (3% with 1 scale, 25% with 12, none with 0)."
                        + mastery_words, gm.RUNNING)
    # The Mossy Rocks (CMossyRocks, vtable 0x48E944; its villager is "Catching a crab", 0x436F30) pay 35 on their
    # result 1 (0x436F0E); a villager's find of a crab pays 55 and says "This villager found a crab!" (the job
    # event 18, 0x464A3F..0x464A93).  The owner: the 55-food catch is a crab.
    add("Food sources", f"A crab caught at the Mossy Rocks (\"Catching a crab\") brings {food(35)}." + mastery_words,
        gm.RUNNING)
    add("Food sources", f"A crab a villager finds (\"This villager found a crab!\") brings {food(55)}." + mastery_words,
        gm.OWNER)
    if village.has(SCALES) is not False:
        add("Food sources", gm.patch_words(village, SCALES, "a Golden Fish needs all 12 scales"))

    # -- Refills -------------------------------------------------------------------------
    if paused:
        add("Refills", gm.PAUSED_NOTE, gm.RUNNING)
    add("Refills", f"Blackberries: +2 {gm.every(360, speed_value)}, up to {BERRY_CAP:,}; the stream gathers 2% more "
                   "debris at the same time, up to 100%.", gm.RUNNING)
    add("Refills", f"Next growth: {due(NEXT_TICK)}.", gm.SAVE)

    # -- Mushrooms / Collectibles --------------------------------------------------------
    # The appearance: 0x413EE0 (at most 2 at a time, 0x413EFA); a mushroom when rand(100) < 30, or always in rain
    # (weather 2 or 3) or with the weather level above 20 (0x413F33..0x413F5C); red (0x77) when rand(100) < 8, else
    # brown (0x76) (0x413F8F); the item lies 90 real-life seconds (0x4140EC, the wall clock 0x403750).  Picked: brown
    # 6, red 35 (0x4145DE..0x414660), and Mushrooms Found +1 (0x414665).  How many updates the village gets each
    # real-life second is the game loop's and is not read here, so "about every 45 seconds" stays an estimate.
    add("Mushrooms", "While playing (not paused) a mushroom or a collectible appears by the roll under Collectibles: "
                     "about every 45 real-life seconds (an estimate: the roll is made once per update of the village, "
                     "and how many updates come each real-life second is not read here); at most 2 lie at a time, "
                     "each gone after 90 real-life seconds (real time, the same at every speed: the computer's clock 0x403750).",
                     False)
    add("Mushrooms", "30.03% of them are mushrooms, and every one while it rains or while the weather level is above "
                     f"20 (wet ground): brown 91.99% of the time, worth {food(6)} food, red (rare) 8.01%, worth "
                     f"{food(35)}.", gm.RUNNING)
    if village.has(GOLDEN):
        out.extend(gm.golden_lines(GOLDEN, 3600 / 45 * 0.30, speed_value, "something about every 45 real-life seconds "
                                   "at every speed, 30% of them mushrooms on dry ground in fair weather"))
    # The rarity 0x41404D: rand(100) < 5 rare (+8), < 18 uncommon (+4), else common; a piece already found pays
    # 100, 250 or 1,500 tech points (0x41446C..0x4144A4).  Fish-scale spots (0x46) need 0x41F5E0: (the save's clock
    # ÷ 3,600) odd.
    add("Collectibles", "The others are collectibles: 81.98% common, 13.01% uncommon, 5.01% rare. A piece already found "
                        "gives 100, 250 or 1,500 tech points by rarity. Fish-scale spots count only in every other "
                        "real-life hour (the odd whole hours counted from the save's clock base).", gm.RUNNING)
    # A ghost is not a buried villager (the owner, 2026-10-24): it takes a random grave's looks (0x414110).
    add("Collectibles", "The four collections are the Fish Scale, Lab Equipment, Mausoleum Mural and Wind Flute sets. "
                        "Once the Mausoleum Mural set is complete, a ghost brings a collectible every 50 to 58 real-life "
                        "minutes (real time, the same at every speed; nothing if more than a real-life hour overdue); what a ghost is: under Death and graves.",
        gm.RUNNING)
    add("Collectibles", "Fog increases collectible spawning if you have Wind Flute pieces collected.", gm.OWNER)
    add("Collectibles", (
        "Exactly (0x41437E): each update of the village (while not paused) something appears when a roll of 0 to 5,999 "
        "comes under 4 -- 24 in 32,768 -- and, when the weather level is above 50 (rain or wet ground), a second such "
        "roll gives another chance. In fog the first roll's 4 becomes 4 for every 2 Wind Flute pieces found (0x413B90 "
        "on the set 0x6A..0x75): no spawns at all from it with 0 or 1, the normal chance with 2 or 3, twice it with 4 "
        "or 5, up to 6 times it (144 in 32,768) with all 12."), gm.RUNNING)
    flutes = life.collectible_counts(village)
    if flutes is not None and len(flutes) >= 48 and not village.general:
        found = sum(1 for c in flutes[36:48] if c > 0)
        out.append(gm.Fact("Collectibles", (
            f"This village: {found} of the 12 Wind Flute pieces found, so in fog the first roll's chance is "
            f"{6 * 4 * (found // 2)} in 32,768 each update."), gm.SAVE, True))
    add("Collectibles", "With 3 or more tree stages a hummingbird flies by every 3 to 5 real-life minutes (every 23 to 25 "
                        "once Decorate Tree is done; whether real time or on the game's clock: the next line); it changes nothing.", gm.RUNNING)
    add("Collectibles", "The hummingbird's 3 to 5 (23 to 25) real-life minutes: whether they are real time or on "
                        "the game's clock was not traced.", False)
    # The room check 0x468350: +5 for each complete set (0x4143F0), 20 made 25 (0x4683AA).
    add("Collectibles", "Fog comes with the weather and with island events (see Island events). Each complete "
                        "collection raises the population limit by 5, and all four by 25 (the room check 0x468350).",
        gm.RUNNING)

    # -- Tech points (how many there are is under Vital statistics) -----------------------------
    lvl = level[SCIENCE]
    divisor = {1: 11, 2: 9, 3: 7}.get(lvl)
    if divisor:
        add("Tech points and effects", (
            f"Research gives the researcher's skill ÷ {divisor} at Science level {lvl}, "
            + {gm.FAST: "twice that on Fast speed", gm.NORMAL: "as it is on Normal speed",
               gm.SLOW: "0.6 of it on Slow speed"}[speed]
            + f", rounded down; then 3 times that for a villager with the Purify Tree's glow (below); then 0 to "
              f"(Lab Equipment pieces found - 1) more, each equally likely; then 1 more 10.01% of the time while "
              f"the Fire Pit burns. While catching up the skill ÷ {5 if lvl >= 3 else 7}, at every speed."),
            gm.RUNNING)
        # 0x45EB90 looks for the villager's effect kind 1 on 0x4CE1C0, which only the Purify Tree's result 0
        # (CPurifyTree vtable 0x48E9F8 +0x30 = 0x437EC0 -> 0x438089) gives, for 240 real-life seconds (0x4380CF ->
        # 0x460A90); 0x464E4F triples the research.  The Lab Equipment bonus: rand(pieces) (0x464E5D..0x464E82).
        add("Tech points and effects", "The Purify Tree's glow: one of the Purify Tree's two results gives the "
                                       "villager a glow for 4 real-life minutes (240 seconds; real time, the same "
                                       "at every speed: its end is set on the computer's clock, 0x460A90 -> "
                                       "0x403750, so paused time counts too), and while it lasts their research "
                                       "brings 3 times the tech points.", gm.RUNNING)
    if village.has(LEARNING) is not False:
        add("Tech points and effects", gm.patch_words(village, LEARNING, "no skill roll fails"))
    add("Tech points and effects", "Nursery School: each child gains the teacher's five skills added up ÷ 240 per "
                                   "real-life hour at any speed, in skills under 50 (the exact rule is under Time "
                                   "away).", gm.RUNNING)

    # -- Food earned: the eating odds are under Chances ------------------------------------
    # The snack, job event 68 (0x46438D): below 100 health with food in storage, rand(100) < 50 gives +1 health;
    # 1 food is taken either way (0x4643DF).
    add("Food earned", f"Each villager eats 2 food every age unit ({gm.duration(60 * speed)} of real-life play on {on} "
                       f"speed, {2 * 3600 / (60 * speed):g} food per real-life hour); when it is skipped and how much "
                       "more is eaten are under Chances (Eating). A snack (below full health, with food in storage) "
                       "costs 1 food and heals 1 health 50.05% of the time.", gm.RUNNING)

    # -- Time away (catch-up): src/vv_game_mechanics_catchup.py, added by vv_game_mechanics.read -----

    # -- Island events -------------------------------------------------------------------
    add("Island events", "When the next natural island event comes: under Village timers.", gm.SAVE)
    out.extend(events.facts(village))          # the catalog (src/vv_game_mechanics_events_vv4.py)

    # -- Other ---------------------------------------------------------------------------
    for line, ok in HIDDEN_LINES:
        add(gm.HIDDEN, line, ok)
    out.extend(gm.starvation_lines(village, 0x8, gm.RUNNING))
    add("Chance and timers", gm.autosave_line(4), gm.OWNER)
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
    # The owner (2026-10-24); the Cold Snap's apply 0x414BD0 ends the fire (tail jmp 0x432620 on 0x4D867C).
    add("Other", gm.FIRE_OUT + " The Cold Snap island event (it needs the Fire Pit burning) puts it out.", gm.OWNER)
    add("Other", gm.FIRE_CLOSED, gm.OWNER)
    out.append(gm.old_age_line("55, 63 or 71 years (Medicine 1, 2, 3)", "65, 73 or 81 years"))
    add("Other", f"An age unit is {gm.duration(60 * speed)} and a villager year (20 age units) "
                 f"{gm.duration(20 * 60 * speed)} of real-life play on {on} speed.", gm.RUNNING)
    clock = gm.later_clock(data, CLOCK, base, speed_value, _i32(data, STATS))
    out.append(gm.started_line(clock.created))
    out.extend(f for f in [gm.warp_dates_note(village, "Other", "the village's start date is")] if f)
    out.extend(gm.later_puzzle_lines(PUZZLE_NAMES, lambda pid: struct.unpack_from("<ii", data, PUZZLE_ENTRIES + 8 * pid),
                                     PUZZLE_THRESHOLDS, clock))
    out.extend(f for f in [gm.warp_dates_note(village, gm.PUZZLES, "the puzzle dates are")] if f)

    # -- The countdowns, and the people and clocks (src/vv_game_mechanics_life.py) ------------
    growth_at = None if paused else real(NEXT_TICK)
    event_at = None if paused else real(EVENT_NEXT)
    gm.with_due(out, "Next growth:", growth_at, "refill")
    multiplier = 2.0 if mastery >= 3 else (1.5 if mastery == 2 else 1.0)
    collectibles, complete = life.collectible_lines(village, life.COLLECTIBLE_PAY[4])
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
        mushroom_words="Something appears about every 45 real-life seconds while playing (not paused; real time, the "
                       "same at every speed; twice as often on wet "
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
