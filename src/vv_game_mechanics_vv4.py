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
from pathlib import Path

import vv_game_mechanics as gm
import vv_game_mechanics_death as death
import vv_game_mechanics_events as events
import vv_game_mechanics_life as life
import vv_game_mechanics_nursery as nursery
import vv_save_backup

GAME = 4
SPEED, LAST_TICK, NEXT_TICK, DIFFICULTY = 0x17120, 0x17100, 0x170F4, 0x17104
FOOD, TECH, LEVELS = 0x85C, 0xBCD0, 0xBCB8
MUSHROOMS_FOUND, EVENTS_SEEN = 0x874, 0x884
BERRIES, EVENT_NEXT = 0x17108, 0x170F0
SCIENCE, MEDICINE, LEARNING_TECH, FOOD_MASTERY = 0, 1, 2, 4
BERRY_CAP = 1000
GOLDEN = "vv4_super_secret_golden_mushroom"
# Picked Up Collectibles Stay Collected When Dropped (off by default; Owner's Defaults ticks it).
COLLECTED = "vv4_collectibles_stay_collected"
HUNGRIER = "vv4_hungrier_villagers"
CLASSIC = "vv4_classic_vv_difficulty"
SPAWN_LIKE_VV3 = "vv4_collectible_spawn_like_vv3"
LEARNING = "vv4_learning_never_fails"
SCALES = "vv4_complete_scales_golden_fish"
# Food Gains are Flat, like VV1-3 (Harder Games): a blackberry pick pays The Secret City's fruit and honey pick
# (0x434ABB..0x434AE4: 7, 3 or 2 on Fast, Normal or Slow, 4 while catching up) instead of the berries / 100; the
# patched step 0x46446B reads the catch-up flag game+0x171A4 and the speed game+0x17110 (any other value: 3).
FLAT = "vv4_food_pays_like_earlier_games"
FLAT_PICK, FLAT_CATCH_UP = {gm.FAST: 7, gm.NORMAL: 3, gm.SLOW: 2}, 4
HARDER_FISHING = "vv4_harder_fishing_unlock"
SCIENCE_SET = "vv4_science_collectibles_complete"
STORY = "vv4_story_cheat_upgrades"
# Yellow Fruit Trees are No Longer Unlimited ("VVFP VV4 Fruit Supply.dll", native/vvfp_vv4_fruit_supply): the tree holds
# at most 1,000 fruit, refilled to full every 40 age units of a reference villager; 3 fruit a food-bin credit (job
# event 15) or a stewed fruit (0x42EAE7), 5 a catch-up Cooking Pit bonus (0x468AAB), all before Food Mastery.  The
# count is kept beside the save, never in it (FRUIT_FILE, read by fruit_supply).
YELLOW_FRUIT = "vv4_yellow_fruit_trees_limited"
FRUIT_FULL, FRUIT_TRIP, FRUIT_BONUS, FRUIT_REFILL_UNITS = 1000, 3, 5, 40
FRUIT_SAVES = "Virtual Villagers Fun Patcher"
FRUIT_FILE = "Data\\Fruit Trees\\Virtual Villagers 4 Yellow Fruit Tree - Save {slot}.dat"
FRUIT_MAGIC = 0x46345656            # 'V' 'V' '4' 'F'
# Yellow Breadfruit Refills Partially Every Time (needs the patch above; the same companion, FS_PARTIAL_*): every 30
# age units the tree gains floor(units x 37 / 10) -- 111 -- up to 1,000, The Secret City's fruit-tree pace.
PARTIAL = "vv4_yellow_fruit_refills_partially"
FRUIT_PARTIAL_UNITS, FRUIT_PARTIAL_PER_10_UNITS = 30, 37
FRUIT_PARTIAL_GAIN = FRUIT_PARTIAL_UNITS * FRUIT_PARTIAL_PER_10_UNITS // 10     # 111

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
     "minutes (real time, the same at every speed); soapy x3: \"I feel sick!\" and \"Throwing up soapy stew!\" (it "
     "does not make the villager sick), with the same 10-minute wait. In salt water, pulpy vines x3 make soap; any "
     "other mix tastes nasty or too salty.", gm.RUNNING),
)
# The stew pot (0x4D76D8) and its herb table (0x4D8220), the same design as The Secret City's potion: a stew
# made (0x42EDE0) sets the table's deadline +8 to the real clock 0x403750 + 300 (0x42F240, from 0x42EEB2); the
# table's update 0x42F1D0 empties the pot there (0x42F060 -> 0x42DA30, the herbs put back).  The pot's countdown
# (0x42E5D2) shows the time left (0x42F410) x the clock's rate / 6 (0x41DB00) as m:ss.  The table is not saved
# (its save and load slots are no-ops, 0x432380), so no save holds a stew to count down.
STEW_COUNTDOWN = {gm.FAST: "2:30", gm.NORMAL: "5:00", gm.SLOW: "8:20"}


def stew_pot_line(speed: int) -> str:
    return (f"A ready stew: the pot's on-screen countdown starts at {STEW_COUNTDOWN[speed]} on {gm.speed_name(speed)} "
            "speed (2:30 on Fast, 5:00 on Normal, 8:20 on Slow), and the pot empties itself when it reaches 0:00, "
            "5 real-life minutes after the stew was made at every speed. The save does not keep the pot.")


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
# nothing counts the times.  The owner (2026-11-12), seen in play: some stews evaporate instead of reheating, so
# something not traced here stops it for them.  What turns the hot state on for an already-made stew is not traced here (the only
# other writer is 0x42F4A0, a drop handler on the pot's boiling-water object, vtable 0x48E2F0 +0x28).
REHEAT_CODE_LINE = (
    "In the game's code: each hot rock adds 10 heat to the pot, which only emptying it takes away; a stew is ready "
    "at 10 heat, the Grand Feast at 20 with its 4 feast items, and the two salt-water mixes (soapy x3, pulpy "
    "vines x3) need no heat. The pot takes things only while it is hot: making a stew ends that, and an unfinished "
    "Grand Feast stays hot for 10 real-life minutes on Normal speed (5 on Fast, 16 minutes 40 seconds on Slow) "
    "after each thing added. A hot rock that goes into the hot pot while its stew is ready makes "
    "the same stew again and starts its 5 real-life minutes over (the 5 minutes are real time, the same at every "
    "speed). In play, though, not every stew can be reheated this way: some just evaporate.")
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
     "from 59, before the doubling or halving), a success still gives 1 point when two more rolls both come up: "
     "one of 51.05%, then a roll of 0 to 99 at or above the skill; otherwise nothing. The odds of the check itself "
     "are under Chances.",
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
    # The walk speed 0x45E2C0: 300 for running (0x45E2FF), 40 for a dislike (0x45E325); the elderly 0x465EB0; the walk
    # 0x461120 moves speed / 100 pixels a 33 ms frame (tests/test_game_mechanics_farmers_vv4.py measures it).
    ("Running: an adult who likes it walks at speed 300 (100 otherwise) and one who dislikes it at 40; children run "
     "unless they dislike it; the elderly (840 + 160 x Medicine level age units or more) always walk at 40; sickness "
     "only takes the running away. A walk moves speed ÷ 100 pixels each 33 ms frame: 30.3 pixels a real-life second "
     "at 100, 3 times that at 300 and 0.4 times at 40, in real time, the same at every speed. Jumping: liked, "
     "Dancing becomes 30 hops; disliked, every hop is skipped.", gm.RUNNING),
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
    # Read from the coordinator's spec (mech_vv4\\spec.md), not traced in the game's code.
    ("A new village: one of the first five villagers has a 30% chance of liking running (not traced in the game's "
     "code).", False),
    # The refresh 0x466D20 runs at 0x43F801 when the game's clock reaches [game+0x171BC]; the 2-second step sets
    # that to the clock + 40 every time (0x43F962), as does the pause (0x43F7E3) and the refresh itself (0x43F814).
    ("Every villager's queue of actions is refreshed only when 40 seconds of the game's clock (whole real-life "
     "seconds) go by without the village's 2-second step, and each step pushes that moment 40 seconds ahead: so "
     "not every 40 seconds in normal play, only after the village has stopped updating for 40 real-life seconds "
     "or more.", gm.CODE),
    ("Clear weather lasts 4 to 15, 8 to 30 or 13 to 50 real-life minutes on Fast, Normal or Slow speed (not traced "
     "in the game's weather code).", False),     # read from the coordinator's spec (mech_vv4\\spec.md)
    # Traced in the stock exe (the coordinator, 2026-11-10): setting the weather 0x46BC30 clears the flute timer
    # (weather object +0xC) for every kind but fog (state 4, 0x46BCA0), which sets it to the game's clock (0x41DB20)
    # + 60 + rand(30); the weather update 0x46BE10 re-arms it the same way when it passes and, with at least 1 Wind
    # Flute piece found (0x413B90 on the set 0x6A), counts a "Know Which Way the Wind Blows" step (0x412F90, 0x13)
    # and plays Flute1 (1-4 pieces), Flute3 (5-9) or Flute5 (10-12) at 3.0 x the Sound slider (0x4AB3A8; FMOD
    # caps it at full).  How the game's clock relates to real seconds at each speed was not verified with it.
    ("Wind flutes: only in fog, they play every 60 to 89 seconds on the game's clock, and only once at least 1 Wind "
     "Flute piece is found (none with 0). The tune changes with the pieces found (one for 1 to 4, another for 5 to "
     "9, a third for 10 to 12), and each time counts toward the \"Know Which Way the Wind Blows\" achievement.",
     gm.CODE),
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
    # The harvest (action 0xBE, 0x451CE0, ending in job event 14) is started by the drop handler 0x46E7E0 (map area
    # 0x31, registered at 0x46FB00): with no cutting tool on hand (The Cutting Tool's object 0x4D8614, puzzle 0,
    # registered by 0x431690 -> 0x4386A0; its count +4 = 0x4D8618) the villager refuses (0x46E810); otherwise the
    # harvest starts and one cutting tool is used (0x4369F0(1) at 0x46E872).  The owner, 2026-11-07: the harvest
    # is done with cutting tools, not cloth; the code agrees.
    add("Food sources", "A blackberry harvest is done with a cutting tool (The Cutting Tool): it uses one of the "
                        "tribe's cutting tools and brings the berries, at most 30, before Food Mastery; with no "
                        "cutting tool on hand the villager refuses.", gm.OWNER)       # the drop handler 0x46E7E0
    flat = village.has(FLAT)
    if flat is not False:
        add("Food sources", gm.patch_words(
            village, FLAT, f"a blackberry pick brings {food(FLAT_PICK.get(speed, 3))} food on {on} speed instead "
                           f"(7, 3 or 2 on Fast, Normal or Slow and {FLAT_CATCH_UP} while catching up, as The Secret "
                           "City's fruit and honey, before Food Mastery) and takes as many berries off the bush; the "
                           "harvest with a cutting tool, Cooking Pit fruit (3), fish from the net (4) and the Golden Fish (8) already pay a "
                           "fixed amount and are unchanged"), gm.RUNNING)
    add("Food sources", f"Stomping or shaking down fruit brings {food(3)}; the fishing net {food(4)} a fish, or {food(8)} for "
                        "a Golden Fish: a (2 x fish scales + 1)% chance (3% with 1 scale, 25% with 12, none with 0)."
                        + mastery_words, gm.RUNNING)
    # The yellow fruit tree and the Cooking Pit (puzzle 6, CFruitwells vtable 0x48E890, constructor 0x436510): the drop
    # 0x435970 (action 0x6A before the restore, 0x64 after), the trip 0x4343A0 -> 0x65..0x68 (0x4346F0), the spot
    # locks 5..8 and holes 1..4 (table 0x704E38; timeouts 0x46D563 45 and 180 game seconds, freed by 0x46D7F0 from
    # 0x43F984), the stew 0x4349A3, the credit job event 15 0x464567; catch-up 0x463A30 and the bonus 0x468A7A.
    add("Food sources", "The yellow fruit tree (once The Cooking Pit is restored): a trip brings 3 food and takes "
                        "about 162 real-life seconds at every speed. Before the pit is restored a villager dropped on "
                        "the tree only finds the fruit needs cooking.", gm.CODE)
    # The trip's queue (0x4346F0, spot 1; the others alike): the shake (1 s poses: step 2 0x468EE0, step 10
    # 0x469280; then a 3 s animation, step 43 0x469EC0(3)), the Farming check (step 9 0x469220), a 3 s wait (step 14
    # 0x4693B0(3) at 0x4348C5), the fruit taken (step 17 item 0x36), a 1 s pose (0x4348E9), the walk to the pit
    # (area 0x22), "Cooking fruit in an earthen oven" (0x23F), a 5 s wait (0x434915), the hops, a 3 s wait
    # (0x43497F), then "Carrying fruit to the food bin" (0x240): the stomped fruit taken (step 17 item 0x37), the walk
    # to the food bin (area 8), a 1 s wait (0x434A0F) and the job event 15 (the food, step 19).  Steps 2, 10, 14 and
    # 43 are waits: their seconds (+0x54) get the clock 0x403750 added when they start (0x46A072, 0x46A17D, 0x46A201,
    # 0x46A3B4) and end through 0x46A000.
    out.append(gm.Fact("Food sources", (
        "How a trip goes (waits in real-life seconds, the same at every speed): it claims one of the pit's 4 fruit "
        "spots (all 4 taken: \"There is no more room in the cooking pit!\" and the villager gives up), shakes fruit "
        "down (1 s poses, then a 3 s animation), the Farming check ((Farming + 34) in 100; a failure ends it with "
        "nothing), a 3 s wait, takes the fruit, a 1 s wait, carries it to the pit, a 5 s wait, stomps it in its "
        "cooking hole, a 3 s wait, takes the stomped fruit, walks it to the food bin, a 1 s wait, then 3 food is "
        "added. If the stew pot is waiting for an ingredient the fruit goes into the stew instead."), gm.CODE, True))
    add("Food sources", "The fruit never runs out (nothing counts it). The 4 spots limit only the start of a trip, and "
                        "a spot frees itself 45 seconds on the game's clock after it is claimed (22.5, 45 or 75 real-life "
                        "seconds on Fast, Normal or Slow) even while its villager is still busy, so more than 4 can be "
                        "on fruit trips at once: about 14, 7 or 5 (an estimate). A villager dropped on the tree does "
                        "one trip (no task is set); a farmer the game sends picks the bush, the fruit or the nets at "
                        "random among those open, and one who dislikes fruit runs away 60 times in 100.", gm.CODE)
    add("Food sources", "While catching up nobody is sent to the fruit and no fruit trip runs. Instead, once The "
                        "Cooking Pit is restored, after each counted age unit's job turns (all but the last 2) every "
                        "villager who had job turns (aged 14 or more, not sick or pregnant) adds 5 food x Food "
                        "Mastery (5, 7 or 10) on a (Farming - 25) in 100 chance, whatever its job, with no walking and "
                        "no spot limit: 3.75 "
                        "food a unit at Farming 100, 1.75 at 60, nothing at 25 or less (Food Mastery 1); children add "
                        "nothing. Each villager eats 2, so it carries a tribe of high-Farming adults but not a large "
                        "one of children and low-Farming villagers.", gm.CODE)
    # The Mossy Rocks (CMossyRocks, vtable 0x48E944; its villager is "Catching a crab", 0x436F30) pay 35 on their
    # result 1 (0x436F0E); a villager's find of a crab pays 55 and says "This villager found a crab!" (the job
    # event 18, 0x464A3F..0x464A93).  The owner: the 55-food catch is a crab.
    add("Food sources", f"A crab caught at the Mossy Rocks (\"Catching a crab\") brings {food(35)}." + mastery_words,
        gm.RUNNING)
    add("Food sources", f"A crab a villager finds (\"This villager found a crab!\") brings {food(55)}." + mastery_words,
        gm.OWNER)
    # Every food gain goes through 0x41D920: level 2 adds half (rounded down), level 3 doubles.
    def levels(amount: int) -> str:
        return f"{amount} -> {amount + amount // 2} -> {amount * 2}"
    add("Food sources", "Food Mastery (a technology) boosts the food every source brings into storage, at the moment "
                        "it is added: level 2 adds half (rounded down), level 3 doubles it. The "
                        "sources' own regrowth (the berries on the bush) is not boosted. Each gain at Food Mastery "
                        "level 1 -> 2 -> 3" + ("" if village.general else f" (this village is at level {max(1, mastery)})")
                        + ": a blackberry pick " + ("" if village.general else f"now {levels(max(2, berries // 100))}, ")
                        + f"{levels(2)} at the least, a harvest at most "
                        f"{levels(30)}; a fish from the net {levels(4)}, a Golden Fish {levels(8)}; stomped or shaken-down "
                        f"fruit {levels(3)}; a crab at the Mossy Rocks {levels(35)}, a crab a villager finds "
                        f"{levels(55)}; a brown mushroom {levels(6)}, a red one {levels(35)}."
                        + gm.flat_pick_mastery(village, FLAT, flat, levels), gm.RUNNING)
    if village.has(SCALES) is not False:
        add("Food sources", gm.patch_words(village, SCALES, "a Golden Fish needs all 12 scales"))
    # The fishing nets need the piers fixed (stage [0x4D86AC] >= 2, 0x4334CC) and the Clothing Hut built (0x4334FC).
    # Cloth Invented's drop 0x436D40: the Clothing Hut finished -> cutting the pulpy vines (action 0x7A, the only start
    # of the cloth chain); with the patch also Science 3.  Fixing the piers (action 0x80: the drop 0x4334D5, the
    # Building dispatcher's option 6 0x463DD8, the task-30 continuation 0x46384D): with the patch also Construction 3
    # (scripts/build_vv4_harder_fishing_unlock_feature.py).
    if village.has(HARDER_FISHING) is not False:
        add("Food sources", gm.patch_words(village, HARDER_FISHING, "no cloth can be made until Science level 3 (a "
                                           "villager dropped on the vines says \"Don't know what to do with these "
                                           "tough vines!\") and the piers cannot be fixed until Construction level "
                                           "3 (a villager dropped on them says \"Additional research may be "
                                           "necessary.\", and builders leave them alone), so the fishing nets, "
                                           "which need both, wait for them; piers already fixed and cloth the "
                                           "village already has still count"))
    fruit_patch = village.has(YELLOW_FRUIT)
    supply = fruit_supply(village) if fruit_patch is not False else None
    fruit_at = fruit_next_at = None
    # With Yellow Breadfruit Refills Partially Every Time the tree gains 111 every 30 units instead of filling every 40.
    partial = fruit_patch is True and village.has(PARTIAL) is True
    refill_units = FRUIT_PARTIAL_UNITS if partial else FRUIT_REFILL_UNITS
    every_refill = life.every_real(refill_units * 360, speed_value).removeprefix("every ")
    refill_rule = (f"gaining {FRUIT_PARTIAL_GAIN} fruit every {FRUIT_PARTIAL_UNITS} age units (with \"Yellow "
                   "Breadfruit Refills Partially Every Time\")" if partial else
                   f"refilled to full every {FRUIT_REFILL_UNITS} age units")
    if fruit_patch is not False:
        add("Food sources", gm.patch_words(
            village, YELLOW_FRUIT,
            f"the yellow fruit tree holds at most {FRUIT_FULL:,} fruit, {refill_rule} "
            f"({every_refill}; time away as the game counts it and Time Warp count too); "
            f"a fruit trip takes {FRUIT_TRIP} fruit when its food goes in the food bin (Food Mastery multiplies "
            f"the food, not the fruit taken), a stomped fruit put in the stew takes {FRUIT_TRIP}, a catch-up "
            f"Cooking Pit bonus takes {FRUIT_BONUS} and pays nothing with fewer left; with fewer than {FRUIT_TRIP} "
            "left a villager dropped on the tree refuses, and farmers the game sends leave the last 3 (they are "
            "not sent there with fewer than 6 left; a villager the player drops on it still takes them). "
            "Dendrology and "
            "Construction gate other puzzles (and the pit's debris), not the fruit; the difficulty, the Purify "
            "Tree, the Tree of Life, the Nursery's \"Showing baby the cooking area\" and the island event that "
            "needs the restored pit take no fruit; a Custom Island Event that refills the food sources fills the "
            f"tree to {FRUIT_FULL:,}, and no island event of the game's own refills it"
            + (f"; the two trees show the fruit left (art by Lorsieab2), in the village and on the Overview Map "
               f"({stages})" if (stages := fruit_stages_text()) else "")))
        if fruit_patch is True:
            if supply is None:
                add("Food sources", "The yellow fruit tree's supply: no file of the patch's for this village, so "
                                    f"the tree is full ({FRUIT_FULL:,} fruit) when the village is next played.",
                    gm.SAVE)
            else:
                left = max(1, refill_units - supply[1])
                shown = fruit_shown(supply[0])
                next_refill = (f"gains {fruit_partial_gain(supply[1] + left)} fruit (up to {FRUIT_FULL:,})"
                               if partial else "refilled to full")
                add("Food sources", f"The yellow fruit tree's supply (the patch's file, as of the last save): "
                                    f"{supply[0]:,} of {FRUIT_FULL:,} fruit left"
                                    + (f" (the trees show: {shown})" if shown else "")
                                    + f"; {next_refill} after {left} more "
                                    f"age units ({gm.duration(gm.real_seconds(left * 360, speed_value))} of play on "
                                    f"{on} speed).", gm.SAVE)
                # The owner (2026-11-12): a limited food source shows its next refill in real time.  The age units
                # run from the save's last life tick; saved paused or already past, it comes when next played.
                at = real(LAST_TICK) + gm.real_seconds(left * 360, speed_value)
                fruit_at = None if paused or at <= village.now else at
                fruit_next_at = None if paused else at

    # -- Refills -------------------------------------------------------------------------
    if paused:
        add("Refills", gm.PAUSED_NOTE, gm.RUNNING)
    add("Refills", f"Blackberries: +2 {gm.every(360, speed_value)}, up to {BERRY_CAP:,}; the stream gathers 2% more "
                   "debris at the same time, up to 100%.", gm.RUNNING)
    add("Refills", f"Next growth: {due(NEXT_TICK)}.", gm.SAVE)
    if fruit_patch is not False:
        add("Refills", gm.patch_words(village, YELLOW_FRUIT, f"the yellow fruit tree is refilled to {FRUIT_FULL:,} "
                                      f"every {FRUIT_REFILL_UNITS} age units ({every_refill}), counted "
                                      "as the game counts its villagers' ages, live, while catching up and with "
                                      "Time Warp; a Custom Island Event that refills the food sources also fills "
                                      "it to full (the 40-unit count runs on)") if not partial else (
            f"The yellow fruit tree gains {FRUIT_PARTIAL_GAIN} fruit every {FRUIT_PARTIAL_UNITS} age units "
            f"({every_refill}), up to {FRUIT_FULL:,} (\"Yellow Fruit Trees are No Longer Unlimited\" with \"Yellow "
            "Breadfruit Refills Partially Every Time\": The Secret City's 37 fruit an hour), counted as the game "
            "counts its villagers' ages, live, while catching up and with Time Warp, so time away pays in "
            "proportion; no technology changes it. A Custom Island Event that refills the food sources fills it to "
            "full (the count runs on)."))
    if fruit_patch is True and village.has(PARTIAL) is None:
        add("Refills", gm.patch_words(village, PARTIAL, f"the yellow fruit tree gains {FRUIT_PARTIAL_GAIN} fruit "
                                      f"every {FRUIT_PARTIAL_UNITS} age units instead of being refilled to full"))

    # -- Mushrooms / Collectibles --------------------------------------------------------
    # The appearance: 0x413EE0 (at most 2 at a time, 0x413EFA); a mushroom when rand(100) < 30, or always in rain
    # (weather 2 or 3) or with the weather level above 20 (0x413F33..0x413F5C); red (0x77) when rand(100) < 8, else
    # brown (0x76) (0x413F8F); the item lies 90 real-life seconds (0x4140EC, the wall clock 0x403750).  Picked: brown
    # 6, red 35 (0x4145DE..0x414660), and Mushrooms Found +1 (0x414665).  How many updates the village gets each
    # real-life second is the game loop's and is not read here, so "about every 45 seconds" stays an estimate.
    add("Mushrooms", "While playing (not paused) a mushroom or a collectible appears by the roll under Collectibles: "
                     "about every 45 real-life seconds (an estimate: the roll is made once per update of the village, "
                     "and how many updates come each real-life second is not read here); at most 2 lie at a time, "
                     "each gone after 90 real-life seconds (real time, the same at every speed: it runs on the "
                     "computer's clock).",
                     False)
    # The roll 0x4143A8: rand(6000) < 4 (fog: (Wind Flute pieces / 2) x 4); above weather strength 50 a second < 4
    # (0x4143CF).  The Secret City's is < 3 and < 3 (0x42DD7A, 0x42DD95).
    add("Mushrooms", "The roll: 4 in 6,000 each update of the village (The Secret City: 3 in 6,000); in fog (Wind "
                     "Flute pieces ÷ 2, rounded down) x 4 in 6,000 instead, so none with 0 or 1 piece; while the "
                     "weather strength is above 50, a second roll of 4 in 6,000.", gm.CODE)
    if village.has(SPAWN_LIKE_VV3) is not False:
        add("Mushrooms", gm.patch_words(village, SPAWN_LIKE_VV3, "the roll and the heavy-weather second roll are "
                                        "3 in 6,000, as in The Secret City (about a quarter fewer); fog's Wind "
                                        "Flute roll and everything else are unchanged"))
    add("Mushrooms", "30.03% of them are mushrooms, and every one while it rains or while the weather level is above "
                     f"20 (wet ground): brown 91.99% of the time, worth {food(6)} food, red (rare) 8.01%, worth "
                     f"{food(35)}.", gm.RUNNING)
    if village.has(GOLDEN):
        out.extend(gm.golden_lines(GOLDEN, 3600 / 45 * 0.30, speed_value, "something about every 45 real-life seconds "
                                   "at every speed, 30% of them mushrooms on dry ground in fair weather"))
    # The rarity 0x41404D: rand(100) < 5 rare (+8), < 18 uncommon (+4), else common; a piece already found pays
    # 100, 250 or 1,500 tech points (0x41446C..0x4144A4).  Fish-scale spots (0x46) need 0x41F5E0: (the save's clock
    # ÷ 3,600) odd.
    # The release listener 0x414410: any area but the stew pot (5) instead of only the food bin (8) (data/builds.json
    # vv4_collectibles_stay_collected).
    if village.has(COLLECTED) is not False:
        add("Mushrooms", gm.patch_words(village, COLLECTED, (
            "a mushroom a child has picked up counts wherever the child puts it down, once, not only at the "
            "food bin; one dropped on the stew pot is left to the pot (collectibles already count "
            "anywhere)")), gm.CODE)
    add("Collectibles", "The others are collectibles: 81.98% common, 13.01% uncommon, 5.01% rare. A piece already found "
                        "gives 100, 250 or 1,500 tech points by rarity. Fish-scale spots count only in every other "
                        "real-life hour (the odd whole hours counted from the save's clock base).", gm.RUNNING)
    # A ghost is not a buried villager (the owner, 2026-10-24): it takes a random grave's looks (0x414110).
    add("Collectibles", "The four collections are the Fish Scale, Lab Equipment, Mausoleum Mural and Wind Flute sets. "
                        "Once the Mausoleum Mural set is complete, a ghost brings a collectible every 50 to 58 real-life "
                        "minutes (real time, the same at every speed; nothing if more than a real-life hour overdue); what a ghost is: under Death and graves.",
        gm.RUNNING)
    add("Collectibles", "Fog increases collectible spawning if you have Wind Flute pieces collected.", gm.OWNER)
    # The roll 0x41437E; the Wind Flute count 0x413B90 on the set 0x6A..0x75.
    add("Collectibles", (
        "Exactly: each update of the village (while not paused) something appears when a roll of 0 to 5,999 comes "
        "under 4 -- 24 in 32,768 -- and, when the weather level is above 50 (rain or wet ground), a second such roll "
        "gives another chance. In fog the first roll's 4 becomes 4 for every 2 Wind Flute pieces found: no spawns at "
        "all from it with 0 or 1, the normal chance with 2 or 3, twice it with 4 or 5, up to 6 times it (144 in "
        "32,768) with all 12."), gm.RUNNING)
    flutes = life.collectible_counts(village)
    if flutes is not None and len(flutes) >= 48 and not village.general:
        found = sum(1 for c in flutes[36:48] if c > 0)
        out.append(gm.Fact("Collectibles", (
            f"This village: {found} of the 12 Wind Flute pieces found, so in fog the first roll's chance is "
            f"{6 * 4 * (found // 2)} in 32,768 each update."), gm.SAVE, True))
    add("Collectibles", "With 3 or more tree stages a hummingbird flies by every 3 to 5 real-life minutes, the same at "
                        "every speed (every 23 to 25 once Decorate Tree is done); it changes nothing.", gm.RUNNING)
    # The scene update 0x43F750: skipped while paused (0x43FDDA, the game clock 0x4D6F18's rate 0); now = 0x403750
    # (0x43FDEA: whole real-life seconds from time(), not the game clock); with more than 2 tree stages (0x41F570,
    # 0x43FE87) and now past the timer game+0x170EC (0x43FE95) the bird flies (0x42C5F0, image 0x12F
    # hummingbirdstrip.png) and the timer becomes now + 180 + rand(120) (0x43FEA9, 0x43FEB0), + 1,200 once
    # Decorating the Tree (puzzle 15) is solved (0x43FECA, 0x43FED6).  The timer is not one the game clock rescales.
    add("Collectibles", "The hummingbird's minutes are real time: its timer runs on the computer's clock, so they are "
                        "the same at Fast, Normal and Slow. It does not fly while the game is paused; if its time "
                        "came during a pause, it flies as soon as the game runs again.", gm.CODE)
    # The room check 0x468350: +5 for each complete set (0x4143F0), 20 made 25 (0x4683AA).
    add("Collectibles", "Fog comes with the weather and with island events (see Island events). Each complete "
                        "collection raises the population limit by 5, and all four by 25.",
        gm.RUNNING)                             # the room check 0x468350

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
        # Its end is set on the computer's clock: 0x460A90 -> 0x403750.
        add("Tech points and effects", "The Purify Tree's glow: one of the Purify Tree's two results gives the "
                                       "villager a glow for 4 real-life minutes (240 seconds; real time, the same "
                                       "at every speed, and paused time counts too), and while it lasts their "
                                       "research brings 3 times the tech points.", gm.RUNNING)
    # The bonus 0x464E6F: cmp al,12 / jne instead of test / jle (scripts/build_science_collectibles_complete_features.py).
    if divisor and village.has(SCIENCE_SET) is not False:
        add("Tech points and effects", gm.patch_words(village, SCIENCE_SET, "the Lab Equipment pieces add nothing to "
                                                      "research until all 12 are found; then 0 to 11 more"))
    if village.has(LEARNING) is not False:
        add("Tech points and effects", gm.patch_words(village, LEARNING, "no skill roll fails"))
    out.extend(nursery.lines(village, 4))       # the Nursery School and why children gain skills

    # -- Food earned: the eating odds are under Chances ------------------------------------
    # The snack, job event 68 (0x46438D): below 100 health with food in storage, rand(100) < 50 gives +1 health;
    # 1 food is taken either way (0x4643DF).
    add("Food earned", f"Each villager eats 2 food every age unit ({gm.duration(60 * speed)} of real-life play on {on} "
                       f"speed, {2 * 3600 / (60 * speed):g} food per real-life hour); when it is skipped and how much "
                       "more is eaten are under Chances (Eating). A snack (below full health, with food in storage) "
                       "costs 1 food and heals 1 health 50.05% of the time.", gm.RUNNING)
    # Hungrier Villagers: both meal immediates x N (scripts/build_hungrier_villagers_features.py).
    if village.has(HUNGRIER) is not False:
        add("Food earned", gm.patch_words(village, HUNGRIER, "each villager's meal, and the difficulty's extra, "
                                        "take 2 to 10 times the food (the slider); food never goes below 0"))
    if village.has(CLASSIC) is not False:
        add("Food earned", gm.patch_words(village, CLASSIC, "it ticks Food Gains are Flat, Hungrier Villagers, 2-10x "
                                         "Tech Cost, Science Collectibles Only Count When Complete, Harder Fishing Unlock in "
                                         "VV4 and Collectible Spawn Timing works like VV1-3 together; each one's own line on this page says what it changes"))

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
    gm.with_due(out, "The yellow fruit tree's supply (the patch's file", fruit_at, "refill")
    multiplier = 2.0 if mastery >= 3 else (1.5 if mastery == 2 else 1.0)
    collectibles, _ = life.collectible_lines(village, life.COLLECTIBLE_PAY[4])
    puzzles = []
    for pid, name in PUZZLE_NAMES.items():
        progress = _i32(data, PUZZLE_ENTRIES + 8 * pid)
        if 0 < progress < PUZZLE_THRESHOLDS[pid]:
            puzzles.append((name, progress, PUZZLE_THRESHOLDS[pid]))
    # The net's catch on average: a fish (4) or, with s fish scales found, a Golden Fish (8) on rand(100) < 2s + 1
    # (0x433360: 0x413B90 counts the scale kinds found, ids 0x46..0x51, the save's counts 0 to 11); with the
    # patcher's "Complete Fish Scales = Golden Fish in Nets" only once all 12 are found (25%).
    counts = life.collectible_counts(village) or [0] * 48
    scales = sum(1 for c in counts[0:12] if c > 0)
    golden_share = 0.0 if scales == 0 or (village.has(SCALES) is True and scales < 12) else (2 * scales + 1) / 100
    # Each outcome is one gain, rounded by Food Mastery on its own before averaging (Codex, #719); the net's trip
    # food is then that average divided back by the multiplier, so supplies() (which multiplies a float) gives it.
    import vv_game_mechanics_farmers as farmers_mod
    multiplier_now = 2.0 if level[FOOD_MASTERY] >= 3 else (1.5 if level[FOOD_MASTERY] == 2 else 1.0)
    net_food = ((1 - golden_share) * farmers_mod.boosted(4, multiplier_now)
                + golden_share * farmers_mod.boosted(8, multiplier_now)) / multiplier_now
    net_food = int(net_food) if golden_share == 0 else float(net_food)
    # The Cooking Pit (puzzle 6; the owner, 2026-11-08: "a special food source where it never runs out, BUT it can't
    # support a large tribe like the fish due to the amount of cooking and walk time to the food bin it takes ...
    # there's also a limited amount of villagers that can work at the fruit cooking pit simultaneously"): live, the
    # fruit trip (src/vv_game_mechanics_farmers_vv4.py, "fruit stomps": 4 fruit spots, 0x4343A0); while catching up
    # no farmer is sent to it (0x463A30) and the Cooking Pit bonus adds food by itself (FRUITWELLS, 0x468A7A).
    pit = _i32(data, PUZZLE_ENTRIES + 8 * 6) >= PUZZLE_THRESHOLDS[6]
    pit_level = max(1, min(3, level[FOOD_MASTERY]))

    def pit_bonus(members):
        if not pit:
            return None
        workers = [p for p in members if p.works]
        known = [p.skill("Farming", 4) for p in workers]
        if any(f is None for f in known):
            return None
        food_each = farmers_mod.game_module(4).FRUITWELLS["food"][pit_level]
        total = sum(farmers_mod.game_module(4).fruitwells_food_unit(int(f), pit_level) for f in known)
        paying = sum(1 for f in known if f > 25)
        limited = ""
        if fruit_patch is True:
            # 1,000 fruit every 40 age units at 5 a bonus: at most 200 bonuses a refill, 5 a unit on average (with the
            # partial refill 111 every 30 units: 3.7 fruit a unit).
            gives, every = (FRUIT_PARTIAL_GAIN, FRUIT_PARTIAL_UNITS) if partial else (FRUIT_FULL, FRUIT_REFILL_UNITS)
            cap = gives / FRUIT_BONUS / every * food_each
            if total > cap:
                limited = (f" With Yellow Fruit Trees are No Longer Unlimited each bonus takes {FRUIT_BONUS} fruit "
                           f"and the tree gives {gives:,} every {every} age units, so at most "
                           f"{cap:,.1f} food a unit on average, not {total:,.1f}"
                           + (f" (now {supply[0]:,} fruit left)" if supply is not None else "") + ".")
                total = cap
            else:
                limited = (f" With Yellow Fruit Trees are No Longer Unlimited each bonus takes {FRUIT_BONUS} fruit; "
                           f"this village's bonuses fit in the tree's {gives:,} fruit every "
                           f"{every} age units.")
        return total, (
            f"The Cooking Pit while catching up (it is restored): after each counted age unit's job turns, every "
            f"villager who had them (aged 14 or more, not sick or pregnant; all but the last 2 units) adds {food_each} "
            f"food (Food Mastery level {pit_level}) on a (Farming - 25) in 100 chance, whatever its job and with no "
            f"walking; nobody is sent to the fruit itself. This village: {len(workers)} working "
            f"villagers, {paying} of them with Farming above 25, so about {total:,.1f} food each counted age unit, "
            f"against about {sum(1 for p in members if not p.golden) * life.eat_per_unit(ctx_ref[0]):,.1f} eaten. "
            "Farming 25 or less adds nothing and children add nothing, so a large tribe of low-Farming villagers "
            "gets little from it." + limited)

    def fruit_budget(ctx, members, counted, credited, added):
        """With the limited tree, one store for the fruit (Codex, PR #735): the closed-game estimate counted the
        tree's refills as fruit to pick (life.closed_refills) and, separately, the catch-up bonus that takes that
        same fruit.  Here the tree runs unit by unit as the companion runs it: the saved fruit, each unit's bonuses
        (all but the last 2 units) taking FRUIT_BONUS fruit each while it has them, then the refill to FRUIT_FULL at
        every FRUIT_REFILL_UNITS-th unit.  Nobody is sent to the fruit while catching up, so no trip takes any.
        What is left on the tree beyond the saved fruit is the food credited on it (1 food a fruit, before Food
        Mastery, as a trip's 3 for 3)."""
        if not (pit and fruit_patch is True) or not callable(ctx.catch_up_bonus):
            return credited, added
        fruit_source = next((s for s in ctx.sources if s.name == "The Cooking Pit fruit" and not s.unlimited), None)
        if fruit_source is None:
            return credited, added
        workers = [p for p in members if p.works]
        known = [p.skill("Farming", 4) for p in workers]
        units = int(counted // ctx.unit)
        start = supply[0] if supply is not None else FRUIT_FULL
        since = supply[1] if supply is not None else 0
        naive = min(fruit_source.per_unit * counted / ctx.unit, max(0, FRUIT_FULL - start)) * ctx.mastery
        if any(f is None for f in known):
            return credited, added
        food_each = farmers_mod.game_module(4).FRUITWELLS["food"][pit_level]
        wanted = sum(farmers_mod.game_module(4).fruitwells_food_unit(int(f), pit_level) for f in known) / food_each
        fruit, paid = float(start), 0.0
        for unit in range(1, units + 1):
            if unit <= units - 2:
                bonuses = min(wanted, fruit // FRUIT_BONUS)
                fruit -= bonuses * FRUIT_BONUS
                paid += bonuses
            since += 1
            if partial and since >= FRUIT_PARTIAL_UNITS:
                since, fruit = 0, min(float(FRUIT_FULL), fruit + fruit_partial_gain(since))
            elif not partial and since >= FRUIT_REFILL_UNITS:
                since, fruit = 0, float(FRUIT_FULL)
        return credited - naive + (fruit - start) * ctx.mastery, paid * food_each

    ctx_ref = []
    ctx = life.Context(
        village, speed_value, real(LAST_TICK), _i32(data, FOOD), low_food=500, extra_from=8000,
        sources=[life.Source("Blackberries", berries, BERRY_CAP, 2.0, growth_at, f"+2 {life.every_real(360, speed_value)}",
                             verified=gm.SAVE, step=2, interval=gm.real_seconds(360, speed_value),
                             next_at=real(NEXT_TICK), first_in=max(0, _i32(data, NEXT_TICK) - _i32(data, LAST_TICK)), rule=gm.RUNNING),
                 ] + ([life.Source("The fishing net", None, unlimited=True,
                             refill_words="no store of theirs is read here: they bring what the farmers fetch",
                             verified=False)]
                      if _i32(data, PUZZLE_ENTRIES + 8 * 11) >= PUZZLE_THRESHOLDS[11] else [])
                + ([life.Source("The Cooking Pit fruit", supply[0] if supply is not None else FRUIT_FULL, FRUIT_FULL,
                                (FRUIT_PARTIAL_GAIN if partial else FRUIT_FULL) / refill_units, fruit_at,
                                (f"+{FRUIT_PARTIAL_GAIN}" if partial else f"refilled to {FRUIT_FULL:,}")
                                + f" every {refill_units} age units "
                                f"({life.every_real(refill_units * 360, speed_value)}); a fruit trip takes "
                                f"{FRUIT_TRIP} for its {FRUIT_TRIP} food, and a trip can start only while one of the "
                                "pit's 4 fruit spots is free",
                                verified=gm.CODE, step=FRUIT_PARTIAL_GAIN if partial else FRUIT_FULL,
                                interval=gm.real_seconds(refill_units * 360, speed_value),
                                next_at=fruit_next_at,
                                first_in=gm.real_seconds(
                                    max(1, refill_units - (supply[1] if supply is not None else 0)) * 360,
                                    speed_value),
                                **({"first_step": fruit_partial_gain(
                                    max(refill_units, (supply[1] if supply is not None else 0) + 1))}
                                   if partial else {}),
                                rule=gm.CODE)] if pit and fruit_patch is True else [])
                + ([life.Source("The Cooking Pit fruit", None, unlimited=True,
                                # The fruit spots: 0x4343A0.
                                refill_words="it never runs out, but each trip takes about 2 3/4 real-life minutes of "
                                             "shaking, stomping, cooking and walking to the food bin for 3 food, and a "
                                             "trip can start only while one of its 4 fruit spots is free (each frees "
                                             "itself after 45 seconds on the game's clock, so about 14, 7 or 5 "
                                             "villagers work it at once on Fast, Normal or Slow, an estimate)",
                                verified=gm.CODE,
                                capped_words="the Cooking Pit fruit never runs out, but live only about 14, 7 or 5 "
                                             "villagers work it at once on Fast, Normal or Slow, and while catching up only the Cooking Pit's own food comes "
                                             "(below)")] if pit and fruit_patch is not True else []),
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
        limit=life.limit_words(village, life.later_sets(village)),
        puzzles=puzzles,
        # The meal: 0x46848B.
        food_words="2 food a villager every age unit while there is more than 500 (at 500 or less half the meals are "
                   "eaten); on Medium at 8,000 or more, or on Hard, 2 more 76% of the time; never more on Easy; a "
                   "snack below full health costs 1 more.",
        # Farmers needed lists only the sources a farmer is sent to: the bush, and the nets once Fishing Nets is
        # solved.  The fruit is left out: no job turn is sent to it while catching up and no task holds a farmer on it.
        # With Food Gains are Flat the pick pays FLAT_PICK live and FLAT_CATCH_UP while catching up.
        trips=[("blackberry picks", (FLAT_PICK.get(speed, 3), FLAT_CATCH_UP) if village.has(FLAT) is True
                else max(2, berries // 100), "Blackberries"),
               ("fish in the net", net_food if _i32(data, PUZZLE_ENTRIES + 8 * 11) >= PUZZLE_THRESHOLDS[11] else 0,
                "The fishing net"),
               ("fruit stomps", 3 if pit else 0, "The Cooking Pit fruit")],
        catch_up_bonus=pit_bonus, closed_budget=fruit_budget)
    ctx_ref.append(ctx)
    out.extend(life.sections(ctx))
    out.extend(death.facts(village, medicine=level[MEDICINE], speed_value=speed_value, base=base))
    return out


def fruit_partial_gain(units: int) -> int:
    """The fruit a partial refill adds after `units` age units (the companion's floor(units x 37 / 10)), before the
    1,000 cap."""
    return units * FRUIT_PARTIAL_PER_10_UNITS // 10


def fruit_supply_file(village: gm.Village) -> Path:
    return village.folder / FRUIT_SAVES / f"Save {village.slot}" / FRUIT_FILE.format(slot=village.slot)


def fruit_identity(sex: int, name: bytes, father: bytes, mother: bytes) -> int:
    """The companion's identity of a villager (native/vvfp_vv4_fruit_supply identity(): FNV-1a of the gender dword,
    the name and the parents' names, each up to 25 bytes and a terminator)."""
    h = 2166136261
    for b in struct.pack("<I", sex & 0xFFFFFFFF):
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    for text, end in ((name, 0xFF), (father, 0xFE), (mother, 0xFD)):
        for b in bytes(text).split(b"\0", 1)[0][:25]:
            h = ((h ^ b) * 16777619) & 0xFFFFFFFF
        h = ((h ^ end) * 16777619) & 0xFFFFFFFF
    return h or 1


def fruit_supply(village: gm.Village) -> tuple[int, int] | None:
    """The yellow fruit tree's (fruit left, age units since its last refill) from the companion's file for this
    save's slot, when the file is whole and at least one of the villagers it was written with is alive in this
    save (the companion's own rule); None otherwise -- no file, another village's, unreadable -- and the companion
    then starts the tree full."""
    try:
        raw = fruit_supply_file(village).read_bytes()
    except (OSError, TypeError, AttributeError):
        return None
    if len(raw) != 32 + 1024:
        return None
    magic, version, game, slot, fruit, units, count, _ = struct.unpack_from("<8I", raw)
    if (magic, version, game, slot) != (FRUIT_MAGIC, 1, GAME, village.slot) or fruit > FRUIT_FULL \
            or units >= FRUIT_REFILL_UNITS or count > 256:
        return None
    roster = {v for v in struct.unpack_from("<256I", raw, 32) if v}
    return (fruit, units) if roster & fruit_living(village) else None


def fruit_stages() -> list[dict]:
    """The trees' pictures by the fruit left: [{"from", "to", "picture", "shows"}], the most fruit first, from the
    patch's row (data/vv4_yellow_fruit_trees_limited_feature.json, written from the companion's one table FS_STAGES);
    [] when it cannot be read."""
    import json
    try:
        record = json.loads((Path(__file__).resolve().parents[1] / "data" / f"{YELLOW_FRUIT}_feature.json")
                            .read_text(encoding="utf-8"))
        return list(record["fruit_tree_stages"])
    except (OSError, ValueError, KeyError, TypeError):
        return []


def fruit_stages_text() -> str:
    """'801 to 1,000 fruit: 5 fruits on each tree; ...' -- the pictures' stages in words ('' when unknown)."""
    def span(row: dict) -> str:
        return f"{row['from']:,}" if row["from"] == row["to"] else f"{row['from']:,} to {row['to']:,}"
    return "; ".join(f"{span(row)} fruit: {row['shows']}" for row in fruit_stages())


def fruit_shown(fruit: int) -> str:
    """What the trees show with `fruit` left ('' when unknown)."""
    return next((row["shows"] for row in fruit_stages() if row["from"] <= fruit <= row["to"]), "")


def fruit_living(village: gm.Village) -> set[int]:
    """The companion's identities of the save's living villagers (empty when the table cannot be read)."""
    try:
        import vv_last_names as ln
        entries = ln._entries(GAME, village.data)
        f = ln.FIELDS[GAME]
        data = village.data
        return {fruit_identity(_i32(data, at + f.sex), data[at:at + f.name_cap],
                               data[at + f.father:at + f.father + f.parent_cap],
                               data[at + f.mother:at + f.mother + f.parent_cap]) for at in entries}
    except Exception:  # noqa: BLE001 -- an unreadable villager table: the file cannot be tied to this village
        return set()


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
