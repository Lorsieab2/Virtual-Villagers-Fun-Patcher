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
import vv_game_mechanics_death as death
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
STORY = "vv2_story_cheat_upgrades"
GONG_WHOLE = 0x2E7F0                           # the Gong of Wonder rebuilt (set with its rest 0 at 0x4639E9..)
# The collectibles: one found byte per piece at state 0x2E720 + piece (the pickup 0x463426..0x46347B, kind - 0x1E),
# 12 pieces a collection in the order of its completion message (0x426120 with 0, 12, 24, 36 -> messages 0x1DE..
# 0x1E1: Butterfly, Shell, Beetle, Pebble, the string table 0x497DE4), within each 4 common, 4 uncommon, 4 rare
# (the duplicate's pay table 0x464418: 100, 250, 1,500).  The game keeps no count of duplicates.
COLLECTION_FLAGS = 0x2E720
COLLECTIONS = ("Butterflies", "Shells", "Beetles", "Pebbles")


def collections(data: bytes) -> list[int] | None:
    """Pieces found in each of the four collections (Butterflies, Shells, Beetles, Pebbles), or None."""
    at = COLLECTION_FLAGS + S
    if at + 48 > len(data):
        return None
    return [sum(1 for b in data[at + 12 * k:at + 12 * k + 12] if b) for k in range(4)]


def collections_line(data: bytes) -> str | None:
    found = collections(data)
    if found is None:
        return None
    complete = sum(1 for n in found if n == 12)
    return (f"Collectibles found: {sum(found)} of the 48 pieces ("
            + ", ".join(f"{name} {n} of 12" for name, n in zip(COLLECTIONS, found))
            + f"); {complete} of the 4 collections complete. The game keeps no count of pieces found again.")
EVENTS_SEEN = 0x2E51C                          # the Island Events Seen counter (state offset)

# The conception and sickness odds are under Births and gender and Chances (exact, from the exe); the measured
# figures that stood here (33.9%, 0.52% ...) disagreed with them and are gone (the audit, 2026-10-25).
# Building points per successful try (the completion callbacks): the three huts +0x2E814/+0x2E81C/+0x2E824 and
# the Hospital +0x2E77C get +1, and +1 more unless catching up (flag +0x3046C: 0x462BD8, 0x462D0F, 0x462E4B,
# 0x462F5D); the Dam +0x2E794, the Vine Wall +0x2E7AC and the thorns +0x2E7DC the same plus 1 at Building 88
# (0x46417A, 0x464011, 0x4638AD; cmp 0x58); the Ancient Mosaic +0x2E7B4 +1, +1 more at Building 88, with no
# catch-up test (0x462960..0x4629D6); the broken starting hut +0x2E75C and the Sewing Hut +0x2E78C +1 only
# (0x462A9D, 0x46305D).
ODDS_LINES = (
    ("Building points per successful try: the three huts and the Hospital +2 (+1 while catching up); the Dam, the "
     "Vine Wall and the thorns of the Overgrown Gong Piece +2, or +3 at Building 88 or more (+1 or +2 while "
     "catching up); the Ancient Mosaic +1, or +2 at Building 88; the broken starting hut and the Sewing Hut +1. "
     "The last three are the same while catching up. Work injuries are under Chances.", gm.RUNNING),
)


# Hidden villager stats (the coordinator's specs hidden_vv2\spec.md and likes_all, 2026-10-23):
# (line, what stands behind it -- gm.RUNNING, gm.OWNER, or False for UNCONFIRMED).
# The hidden number +0x550: the creator rolls rand(123) + 1 (0x44CCF1..0x44CD1B); a twin or triplet takes its
# sibling's + 1, rolled again past 123 (0x44D02D..0x44D04A); a totem copies its elder's (0x44D37D).  Readers: the
# starvation rule (0x43BB65, 0x43BB98), the totem's frame (its remainder by 8), and one animation picked by sex
# and whether the number is odd (0x44B224..0x44B24F).  So the game itself never gives 0.
# Learning (the skill roll 0x44E170): it passes when rand(100) <= skill + 33, + 66 liking learning (word 0x27,
# 0x445510), + 16 disliking it (0x4454E0) -- (skill + 34)% -- the gain (100 - 2 x skill) / 10, Building / 7
# (0x44E2C1, 0x44E428, 0x44E52B, 0x44E7F7 x 0x66666667; 0x44E62E x 0x92492493), halved disliking, doubled liking.
# Work (0x461582..0x4615D4): a villager who does not like work drops a job the player gave 20% of the time, or
# 40% of the rest while food is 4,000 or more or it dislikes work.
# A baby's starting skill (the embrace 0x44F610): each parent's best skill (0x44B4D0: Parenting, Building,
# Healing, Farming, Research, the first of a tie), rand(3) + 5 points (0x44F846); when both parents' best is the
# same skill, by Culture (+0x2EA74) rand(2) + 4, rand(4) + 5 or rand(5) + 7 (0x44F869..0x44F8AC); the mother's or
# the father's, rand(100) < 50 (0x44F8BA); a best of Parenting becomes Farming + 0 (0x44B9EE..0x44B9F8).
HIDDEN_LINES = (
    ("Each villager's hidden number (1 to 123, rolled when the game makes the villager, not inherited; a twin's or "
     "triplet's is its sibling's + 1, rolled again past 123) sets how it starves, its totem's colour (the "
     "number's remainder by 8) and, by whether it is odd, which of two animations it plays in one of its "
     "routines; the game itself never gives 0. The villagers' numbers are below.", gm.RUNNING),
    ("Likes and dislikes: a new villager gets them from the first 47 words; jumping, cooking, fire, eating, "
     "children, talking and vegetables appear only when edited in.", gm.RUNNING),
    ("Learning: liking learning makes a skill try pass 33 points more often and doubles the gain; disliking it "
     "makes it pass 17 points less often and halves the gain (the exact roll and gains are under Chances, "
     "Every work step's skill roll).", gm.RUNNING),
    ("Work: liked, the villager never gives up for the 15% skip and always keeps a job the player gave; disliked, "
     "it also gives up 70% of the time and drops a job the player gave 52% of the time (Chances: Choosing a job, "
     "Keeping a player-assigned job). Medicine, disliked: Healing is passed over half the time.", gm.RUNNING),
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
    ("The other 37 likes and dislikes: none of the game's checks of a like or dislike that were traced reads "
     "them, so no effect of theirs is known; not every one of the about 90 places that check likes was traced. "
     "The preferred job and Parenting's own odds are under Chances (Choosing a job).", False),
    ("A baby is born with points in one parent's best skill (the mother's or the father's, 50% each; on a tie "
     "the first of Parenting, Building, Healing, Farming, Research): 5 to 7, each 1 in 3; when both parents' best "
     "is the same skill, 4 to 5, 5 to 8 or 7 to 11 at Culture level 1, 2 or 3 (each equally likely). A best "
     "skill of Parenting gives no points (while catching up: Time away). The mother's Parenting at a conception "
     "and the birth's timing are under Births and gender.", gm.RUNNING),
    ("An Esteemed Elder's totem keeps the elder's hidden number, so its colour was set when the elder was "
     'born; a totem never ages, loses health or dies.', gm.RUNNING),
    ("Totem babies: in the stock game a twin or triplet born into a record a totem left behind (a totem's "
     "burial, or Start Over) kept the totem mark and never aged or died. The patcher's Fix Vanilla Bugs has "
     'cleared that since v1.35.77.', gm.RUNNING),
    # Sickness and health and the fire's research bonus stood here too; they are under Chances (and the fire
    # under Other), word for word the same rules (the audit, 2026-10-25).
)
# The stew pot (state +0x3043C..+0x30455, past the saved range +8..+0x30378, so never saved).  The cook routine
# 0x425B90 (called when the last ingredient goes in, 0x4620A1..0x4623BA) sets the stew +0x3044C at once and
# the pot's end +0x30450 to the real clock 0x403200 + 900 (0x425BA2); the world update empties the pot with
# 0x425B20 once 0x403200 passes it (0x42EBCC..0x42EBE7) -- nothing else empties it, and eating (0x461040,
# from 0x4623E9) leaves it.  Nothing reads +0x30450 for the screen, so no countdown is shown.  The stews'
# effects (0x461040 and the routines it calls: 0x455330, 0x45CD00, 0x450580, 0x454AB0, 0x455AC0, 0x453430,
# 0x44B010, 0x45FBF0, 0x44B1B0, 0x449B70) never read the clock: each acts once, when eaten.  Checked again
# (2026-10-25): the 75 routines reachable by calls from 0x461040 (its jump table 0x461510 followed) call neither
# the clock 0x403200 nor the engine timer 0x401EA0.
STEW_POT_LINE = (
    "A stew is ready the moment it is made, and the pot keeps it 15 real-life minutes at every speed, then empties "
    "itself; the pot's timer runs on the real clock, so paused time counts too. Eating does not empty it: every "
    "villager who eats from it in those 15 minutes gets the stew. The game shows no countdown for it, and the save "
    "does not keep the pot.")
STEW_EFFECT_LINE = (
    "Each stew acts once, at the moment a villager eats it: none of the stews' effects sets a timer, so no "
    "villager has one running and a save holds none to count down.")
CHANCE_EXTRA = (
    ("Every roll that changes play has its exact odds under Chances, except those with a group of their own: the "
     "island events and the Gong of Wonder (Island events), the twins and the baby's sex (Births and gender), a "
     "baby's looks (Genetics) and a baby's starting skill (Hidden villager stats).", gm.RUNNING),
    ("Every timer is in its own group: the age unit (Vital statistics, Villager timers), the regrowth (Refills), "
     "the island events and the Gong's rest (Island events), births (Nursing and pregnancy), how long an item "
     "lies (Mushrooms), the fire and the stew pot (Other) and an unburied body (Death and graves).", gm.RUNNING),
    ("The game's other rolls, about 1,050 places in its code, pick where a villager walks, which spot an item "
     "lies on, how long a step or an animation lasts, speech, facing and the dance and play routines; that none "
     "of them changes a value the save keeps comes from reading the code, not from running each one.", False),
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

    # -- Food sources (the food in storage is under Vital statistics) ----------------------
    add("Food sources", f"Coconuts: {_i32(data, COCONUTS):,}; a trip brings {(8, 4, 2)[pick]} on {on} speed "
                        "(4 while catching up).", gm.RUNNING)
    add("Food sources", f"Crops: {_i32(data, CROPS):,} of {CROPS_FULL}; a trip brings {(10, 7, 4)[pick]} on {on} speed "
                        "(7 while catching up).", gm.RUNNING)
    # The birds (the owner, 2026-10-23: clarify them): the regrowth step 0x43B960 grows the crops 800 only while
    # 0x425AC0 says the birds have not found the field (the dam built, the Scarecrow's byte 0, the allowance
    # 0x2EAD4 at 0 or less), and otherwise sets them to 0 (0x43BA0D); the allowance starts at 1000 (0x425261) and
    # every crop harvest takes its food from it (0x463264: sub [+0x2EAD4], the trip's yield); message 0x1CA
    # (0x487138).  Read again 2026-10-25 on the reached world tick (0x43B9B0..0x43BA67): the regrowth adds 800
    # (0x43B9FF), and the same tick caps the crops at 800 (0x43C225..0x43C234), so the field is refilled to 800.
    # 0x425AC0 says the birds have found the field only with the dam's byte at 1 (cmp byte [ecx+0x2E798], 1);
    # without the dam the regrowth sets the crops to 0 for that reason alone (0x43B9F2 -> 0x43BA0D).  Nothing
    # else in the game writes the allowance (0x425261, 0x463264 only); the patcher's Story / Cheat Upgrades does,
    # in its Custom Island Event values and refill (native/vvfp_story_upgrades/story_c2.inc, c2_refill).
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
    add("Food sources", "The birds: " + birds, gm.RUNNING)
    out.append(gm.Fact("Food sources", "A new village allows 1,000 food of crop harvest; every harvest (10, 7 or 4 "
                                       "food on Fast, Normal or Slow, 7 while catching up) counts against it, and the "
                                       "game never gives it back.", gm.RUNNING, sub=True))
    out.append(gm.Fact("Food sources", ("Once it is used up, at every regrowth (every "
                                        f"{gm.duration(2400 * 3)}, {gm.duration(2400 * 6)} or {gm.duration(2400 * 10)} "
                                        "of real-life time on Fast, Normal or Slow; none while paused; every missed one "
                                        "after time away) the birds eat all the field's crops instead of it being "
                                        "refilled to 800. No chance is rolled; the time of day and the weather do not "
                                        "matter, and stored food is never touched."), gm.RUNNING, sub=True))
    out.append(gm.Fact("Food sources", "Only The Scarecrow stops it, for good."
                       + (" " + gm.patch_words(village, STORY, "a Custom Island Event can set the allowance (\"Field "
                                                               "protection from birds\") or refill it to 1,000")
                          if village.has(STORY) is True else ""),
                       gm.RUNNING, sub=True))
    out.append(gm.Fact("Food sources", "The game says: \"Oh my! Birds found your field and are relentlessly eating "
                                       "the young crops before your villagers can harvest them!\"", gm.RUNNING, sub=True))
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
    # Sustainable Fishing: the algae-eating fish counter +0x2E7E4 +1 a time, solved at 10 (0x462704..0x46271D).
    add("Food sources", "At 0 fish, fishing stops until Sustainable Fishing is solved (the algae-eating fish done 10 "
                        "times); after that, from Farming level 2, villagers fish with no limit and the count goes "
                        "below 0, as in the stock game.", gm.RUNNING)
    add("Food sources", "Every trip needs a Farming skill roll (Chances, Every work step's skill roll); a failed trip "
                        "brings nothing."
                        + (" " + gm.patch_words(village, LEARNING, "no trip fails")
                           if village.has(LEARNING) is True else ""), gm.RUNNING)

    # -- Refills -------------------------------------------------------------------------
    # The regrowth (the world tick, 0x43B9B0..0x43BA45): while the speed is below 999 and the minute of the next
    # regrowth +0x2EAC0 has come, it moves 2,400 x the speed on (0x43B9C1), coconuts +30 capped at 1,500
    # (0x43B9D1..0x43B9E2), crops +800 with the dam built and the birds away (0x43B9FF), else 0 (0x43BA0D); the
    # same tick caps the crops at 800 (0x43C225..0x43C234), and it repeats until no regrowth is due.
    if paused:
        add("Refills", gm.PAUSED_NOTE, gm.RUNNING)        # the regrowth loop stops at a speed of 999 or more (0x43B9B6)
    add("Refills", (f"Every regrowth, {gm.every(2400 * 6, speed_value)}: coconuts +30, up to {COCONUT_CAP:,}; crops "
                    f"refilled to {CROPS_FULL} if the dam is built and the birds have not found the field (or are "
                    "kept away), otherwise the crops are lost to the birds. "
                    f"({'Dam built' if dam else 'No dam yet'}; {'birds kept away' if scared else 'no bird scarer'}.)"),
        gm.RUNNING)
    add("Refills", f"Next regrowth: {due(REGROW)}.", gm.SAVE)
    add("Refills", "Changing the speed rescales the time left to the next regrowth and on the fire (pausing counts as "
                   "Normal); the island event and Gong timers are not rescaled.", gm.RUNNING)

    # -- Mushrooms and collectibles ------------------------------------------------------
    # The spawn check runs in the 2-second block also while paused (it skips only a speed of exactly 999,
    # 0x42EC87; a pause stores the speed + 999); a wait of 2 / p seconds at p = 5%, 6.01%, 7.01%.  The pick-up:
    # only a villager under 280 age units (0x430C9E).
    add("Mushrooms", "One thing at a time, at any speed, while the game is open (paused too): every 2 real-life "
                     "seconds with nothing out, an (Exploration level + 4)% chance (about 40, 33 or 29 real-life "
                     "seconds' wait at Exploration 1, 2, 3). It lies 75 real-life seconds. Only a villager under 14 "
                     "picks one up, when you drop them on it. Exact odds under Chances.", gm.RUNNING)
    add("Mushrooms", "It is a mushroom 50%, 35% or 20% of the time at Exploration 1, 2, 3: a brown "
                     "mushroom worth 6 food, or 1 in 10 a red (rare) mushroom worth 35.", gm.RUNNING)
    if village.has(GOLDEN):
        explore = _i32(data, LEVELS + 8 * EXPLORATION_LEVEL)
        wait_s, share_m = GOLDEN_WAITS.get(explore, GOLDEN_WAITS[1])
        out.extend(gm.golden_lines(GOLDEN, 3600 / wait_s * share_m, speed_value, (
            f"at Exploration level {explore if explore in GOLDEN_WAITS else 1}, something appears about every {wait_s} "
            f"real-life seconds while nothing is out, at every speed, {share_m:.0%} of them mushrooms")))
    add("Collectibles", "When it is not a mushroom it is a collectible: rare 4%, 6% or 8% at Exploration 1, 2, 3, "
                        "uncommon 12%, the rest common. Butterflies and shells can always appear, pebbles once the "
                        "dam is built, beetles once The Overgrown Gong Piece is solved"
                        + (" (it is)." if data[BEETLES + S] else " (it is not yet)."), gm.RUNNING)
    # The duplicate pay 0x463426..0x46347B (table 0x464418), the room 0x44B310..0x44B37D.
    add("Collectibles", "Each collection has 12 pieces: 4 common, 4 uncommon and 4 rare. A piece already found pays "
                        "100, 250 or 1,500 tech points by rarity. Each complete collection raises the population "
                        "limit by 5, all four by 25. What this village has found is under Village counts.", gm.RUNNING)

    # -- Tech points (the count is under Vital statistics) ---------------------------------
    add("Tech points and effects", (
        "Research gives Research skill ÷ 11, ÷ 9 or ÷ 5 at Science 1, 2 or 3, "
        + {gm.FAST: "twice that on Fast speed", gm.NORMAL: "as it is on Normal speed",
           gm.SLOW: "halved on Slow speed when above 1"}[speed]
        + "; a lit fire adds a 10% chance of 1 more. While catching up ÷ 7, ÷ 6 or ÷ 4."), gm.RUNNING)
    if village.general:
        # The general page has no Village counts group (gm.general leaves counts.facts out), so the elder rules
        # stand here; a save's page keeps its one copy under Village counts (counts.vv2_lines).
        add("Tech points and effects", "Esteemed Elders: about every 2 real-life seconds while the game runs, any "
                                       "living villager who is not yet an elder and has 3 of the 5 skills at 88 or "
                                       "more becomes one and gets a totem (0x44D4C0, 0x44D190); no dice roll, no age "
                                       "condition, the same at every speed.", gm.RUNNING)
        add("Tech points and effects", "Normal game: at most 50 totems (0x44D4D1, 0x44D54C): with 50 standing no new "
                                       "elder is made, and each totem takes one of the 256 villager records.",
            gm.RUNNING)
    else:
        add("Tech points and effects", "Esteemed Elders and their totems: see Village counts.", gm.RUNNING)

    # -- Food earned: the eating odds are under Chances ------------------------------------
    add("Food earned", f"Each villager eats 2 food every age unit ({gm.duration(60 * speed)} of real-life play on {on} "
                       f"speed, {2 * 3600 / (60 * speed):g} food per real-life hour); when it is skipped and how much "
                       "more is eaten, and the snack, are under Chances (Eating, A snack).", gm.RUNNING)

    # -- Time away (catch-up): src/vv_game_mechanics_catchup.py, added by vv_game_mechanics.read -----

    # -- Island events -------------------------------------------------------------------
    add("Island events", f"Next island event: {due(EVENT_NEXT)}.", gm.SAVE)
    add("Island events", f"Island events seen in this village: {_i32(data, EVENTS_SEEN):,}.", gm.SAVE)
    out.extend(events.event_facts(village, catalog.RULES, catalog.EVENTS))
    # The Gong of Wonder: its rest from the save (the clock counts real seconds at any speed), then its results.
    # The first-C flag is a byte (cmp byte [+0x2E910], 0x44E8C1; set at 0x44EFDB); the drop handler queues the
    # ringing only with the Gong rebuilt (byte +0x2E7F0, 0x42FE12) and its rest passed (0x42FE23).
    gong_first = data[GONG_FIRST_DONE + S] == 0
    if not data[GONG_WHOLE + S]:
        gong_when = "is not rebuilt yet (its four pieces), so it cannot be rung"
    elif real(GONG_NEXT) > village.now:
        gong_when = f"can ring again {gm.when(real(GONG_NEXT))}"
    else:
        gong_when = "can ring now"
    add("Island events", f"The Gong of Wonder {gong_when} (its rest is 24 real-life hours at any speed)."
                         + (" This village has had no tier C result yet, so its next ring is tier C." if gong_first
                            else ""), gm.SAVE)
    out.extend(events.event_facts(village, extra=catalog.EXTRA))

    # -- Other ---------------------------------------------------------------------------
    # The fuel (0x4624CF..0x46253F): only on a fire still burning, its end becomes the clock + 0x8CA0, 0x11940 or
    # 0x23280 seconds (Fast, any other speed, Slow); a cold pit is left alone.
    fire = real(FIRE_END)
    add("Other", ("The fire " + (f"burns until {gm.when(fire)}" if fire > village.now and not paused else
                                 ("was burning when it was saved" if paused and _i32(data, FIRE_END) > _i32(data, LAST_TICK)
                                  else "is out"))
                  + f"; a lit fire burns {gm.duration(FIRE_HOURS[speed] * 3600)} of real-life time on {on} speed "
                    "(10, 20 or 40 hours on Fast, Normal or Slow), fuel on a burning fire fills it to that again, and "
                    "fuel does not light a cold pit."), gm.RUNNING)
    add("Other", gm.FIRE_OUT, gm.OWNER)
    # The Lost Children's island events (the island-event conditions report, VV2 part): none reads or ends the fire.
    # Checked 2026-10-25: the fire's end +0x2EAC4 is written only by the new village (0x4251F8), its own expiry
    # (0x42ECDB), the pause and speed shifts (0x43B60C, 0x43B712) and lighting or fuelling it (0x462516..0x4625E5).
    add("Other", "No island event in this game puts the fire out.", gm.RUNNING)
    add("Other", gm.FIRE_CLOSED, gm.OWNER)
    add("Other", STEW_POT_LINE, gm.RUNNING)
    add("Other", STEW_EFFECT_LINE, gm.RUNNING)
    # An unburied body's removal is under Death and graves (it stood here too).
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
    # Every puzzle's hours: (the clock - the start +0x2E4F8) / 3600, then at least 1, written with its solved byte
    # (checked 2026-10-25 for all 16: 0x46264A Fire .. 0x462743 Sustainable Fishing; the gong pieces 0x463E89,
    # 0x463B5C, 0x463CDA, 0x463967).
    out.extend(gm.hours_puzzle_lines([name for name, _flag, _hours in PUZZLES],
                                     lambda n: data[PUZZLES[n][1] + S] != 0,
                                     lambda n: _i32(data, PUZZLES[n][2]), created, verified=gm.RUNNING))

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
    out.extend(death.facts(village, medicine=_i32(data, LEVELS + 8 * MEDICINE_LEVEL), speed_value=speed_value,
                           base=struct.unpack_from("<I", data, 4)[0]))
    return out


# The tech levels: six dwords 8 apart from state 0x2EA74 (all six reset at 0x425229); Medicine is the fourth
# (0x2EA8C: the twins roll at 0x44BA6A, sickness at 0x43B2ED), Exploration the fifth (0x2EA94: the mushroom spawn
# roll, its level + 4, at 0x415FF5).
LEVELS, MEDICINE_LEVEL, EXPLORATION_LEVEL = 0x2EA74, 3, 4
# The wait for something to appear (real-life seconds, 2 / p rounded, p = 5%, 6.01%, 7.01%: the spawn roll
# 0x415FED) and the share of mushrooms, by Exploration level (50%, 35% or 20% mushrooms).
GOLDEN_WAITS = {1: (40, 0.50), 2: (33, 0.35), 3: (29, 0.20)}


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
    wait, share = GOLDEN_WAITS.get(exploration, GOLDEN_WAITS[1])
    found = collections(data)
    collectible_words = ("Collectibles: " + (f"{sum(found)} of the 48 pieces found (by collection under Village "
                                             "counts)" if found is not None else "not read from this save")
                         + "; what a piece found again pays is under Collectibles.")
    ctx = life.Context(
        village, speed_value, real_last(data), _i32(data, FOOD), low_food=150, extra_from=4001, sources=sources,
        tech=_i32(data, TECH), tech_words="Research brings them (the skill ÷ 11, ÷ 9 or ÷ 5 at Science 1 to 3).",
        brown=6, red=35, red_share=0.10, mushrooms_an_hour=3600 / wait * share, golden=village.has(GOLDEN) is True,
        mushroom_words=f"At Exploration level {exploration} something appears about every {wait} real-life seconds while "
                       f"nothing is out, {share:.0%} of them mushrooms, picked only when you drop a child on them.",
        event_next=event_at,
        event_paused_left=max(0, _i32(data, EVENT_NEXT) - _i32(data, LAST_TICK)) if paused else None,
        # How the next event is timed and chosen, paused, closed and after a Time Warp: Island events and Time away
        # (the lines that stood here repeated them, one of them UNCONFIRMED).
        event_rule="How it is timed and which event comes: see Island events; paused, closed and after a Time Warp: "
                   "see Time away.",
        medicine=level[MEDICINE_LEVEL], elderly_from={1: 50, 2: 58, 3: 66}, old_age_from={1: 55, 2: 63, 3: 71},
        parents_from=18, sick_loss=(0.61, 0.19),
        collectibles=[(collectible_words, gm.SAVE)],
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
