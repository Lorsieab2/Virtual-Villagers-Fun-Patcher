"""Game Mechanics for New Believers (VV5): every technology level, God power, puzzle, building, repair, upgrade and item
the player can buy, earn, build or use, and what each one does (the owner, 2026-10-27: "Elaborate on what every store
item and upgrade and research and everything does!!!").

ITEMS_GROUP is the heading the coordinator wires into vv_game_mechanics.GROUPS; item_facts() gives the lines in the
page's own Fact form.  Each entry is one bullet, "<name> (<cost, or how it is earned>): <exact effect>", with its
sub-bullets; a patch that changes it comes after the stock value as "With the patcher (<patch>, on/off by default):".

THE LABELS (the owner's standing rule; label() gives them):
  VERIFIED-E  gm.RUNNING -- emulated, or read with exact odds, from a caller the game reaches (re-used from the God
              powers, Faith and Heathens, Chances, Island events and New Believers modules, with their evidence);
  VERIFIED-C  gm.CODE    -- traced on a live path of the stock exe, at the addresses cited (this module's own reads, and
              docs/hidden-gates-all-five-games.md's New Believers rules it marks Reached), or the patcher's own code
              that runs it (native/vv5_task9_origins, scripts/build_vv5_task9_native_actions.py, the feature manifests);
  UNCONFIRMED False      -- anything not yet proven that way; the page shows it with the label.

The stock exe: research/stock-executables/Virtual Villagers - New Believers.exe (SHA-256 92946781...C65D).  Read here:
  * the tech cost table 0x4CA3B4 (three dwords a tech; 0x4236D0 reads table[3 x id + level + 1], 0 past level 3), the
    levels 0x51D5CC (all six set to 1 by 0x423590; a loaded level outside 1..3 is refused, 0x423720), the purchase in the
    Tech screen's handler 0x441655-0x4416B4 (refused with too few tech points, else 0x4237B0 takes the cost and
    0x423610 raises the level), the tech labels eTech*Label 0x4A7C2C-0x4A7CD8;
  * the projects 0x51E008, each registered by 0x43ABB0(id, points needed) from its class's constructor (RTTI names):
    0 CNurserySchool, 1 CConvertMasterDoctorPuzzle, 2 CFencePuzzle, 3 CFoodTotemPuzzle, 4 CResearchTotemPuzzle,
    5 CHydroFarm (30), 6 CRestoreMausoleumPuzzle, 7 CBuildingTotemPuzzle, 8 CChildrensTotemPuzzle,
    9 CConvertMasterBuilderPuzzle, 10 CRestoreLake (2), 11 CMedicineTotemPuzzle, 12 CRainbowTotemPuzzle,
    13 CConvertMasterScientistPuzzle, 14 CBelieverIdolPuzzle, 15 CClosedEyeTotemPuzzle, 16 CConvertHeathenChiefPuzzle,
    17 CHeathenMommyPuzzle, 18 CFirePit (3), 19-21 CHouse1-3 (2,000), 22 CClothingHut (2,000), 23 CLoveShack (2,000),
    24 CNurseryHut (2,000), 25 CConvertLastHeathenPuzzle; the rest need 1;
  * the build step 0x434D20 (reached from 0x473E3A): a successful build action adds the building's +0x24 points one at a
    time (CHouse1 12, CHouse2 4, CHouse3 1, CClothingHut 12, CLoveShack 400, CNurseryHut 50: 0x4359E2-0x435C82);
  * the clothes: work event 90 of the dispatcher 0x46CE60 (table 0x46DEB0, queued at 0x45CF5F) needs 5,000 tech points
    (0x46CE93), takes them (0x46CEC7) and opens the outfit chooser 0x419DF0, which steps the body (record +0x1BBC)
    through 0 to 28 (0x419CE0) and on its fourth button puts the old body back and returns the 5,000 (0x419E77-0x419E9E);
  * Divine Energy: the adder 0x424F80 (kept 0 to the cap); work event 40 adds 1 (0x46DA1B).
Read only: nothing here writes anything.
"""
from __future__ import annotations

from dataclasses import dataclass

import vv_game_mechanics as gm
import vv_game_mechanics_faith_vv5 as faith
import vv_game_mechanics_powers_vv5 as powers
from vv_game_mechanics_chances import at_most, below, chance, times

ITEMS_GROUP = "Technologies, items and buildings"
GROUPS = (ITEMS_GROUP,)

VERIFIED_E, VERIFIED_C, UNCONFIRMED = gm.RUNNING, gm.CODE, False
LABELS = {gm.RUNNING: "VERIFIED-E", gm.CLAMP: "VERIFIED-E", gm.CODE: "VERIFIED-C"}

TECH, POWER, PUZZLE, BUILDING, ITEM, PATCHER = "technology", "power", "puzzle", "building", "item", "patcher"
KINDS = (TECH, POWER, PUZZLE, BUILDING, ITEM, PATCHER)


def label(fact: gm.Fact) -> str:
    """The owner's label for a line: VERIFIED-E, VERIFIED-C or UNCONFIRMED."""
    return LABELS.get(fact.verified, gm.UNCONFIRMED)


@dataclass(frozen=True)
class Entry:
    """One bullet: what kind of thing it is, its name (the game's own), its cost or how it is earned, its exact
    effect, and what stands behind it; `subs` are (text, verified) sub-bullets."""
    kind: str
    name: str
    cost: str
    text: str
    verified: bool | str
    subs: tuple[tuple[str, bool | str], ...] = ()


AGE_UNIT = "age unit (3, 6 or 10 real-life minutes on Fast, Normal or Slow speed; 20 make a villager year)"


# ---------------------------------------------------------------------------
# The game's own tables (the tests read each one from the stock exe)
# ---------------------------------------------------------------------------

# (id, the game's label, level 2 cost, level 3 cost): table 0x4CA3B4, labels eTech*Label.
TECHS = ((0, "Science", 8_000, 70_000), (1, "Medicine", 5_000, 50_000), (2, "Learning", 4_000, 35_000),
         (3, "Construction", 5_000, 65_000), (4, "Food Mastery", 3_000, 40_000), (5, "Spirituality", 8_000, 80_000))
TECH_TABLE, TECH_LEVELS = 0x4CA3B4, 0x51D5CC

# The 16 puzzles of the Puzzles screen (project ids 1 to 16; the names are the game's own completion tips) and the
# class each registers as.
PUZZLE_CLASSES = {1: ("The Sick Heathen", "CConvertMasterDoctorPuzzle"), 2: ("The Prison Break", "CFencePuzzle"),
                  3: ("The Hungry Totem", "CFoodTotemPuzzle"), 4: ("The Knowing Totem", "CResearchTotemPuzzle"),
                  5: ("The Hydroponic Farm", "CHydroFarm"), 6: ("The Buried Mausoleum", "CRestoreMausoleumPuzzle"),
                  7: ("The Blocking Totem", "CBuildingTotemPuzzle"), 8: ("The Hollow Totem", "CChildrensTotemPuzzle"),
                  9: ("The Heathen Builder", "CConvertMasterBuilderPuzzle"), 10: ("The Lake", "CRestoreLake"),
                  11: ("The Pain Totem", "CMedicineTotemPuzzle"), 12: ("The Rainbow Totem", "CRainbowTotemPuzzle"),
                  13: ("The Heathen Scientist", "CConvertMasterScientistPuzzle"),
                  14: ("The Tribute Statue", "CBelieverIdolPuzzle"), 15: ("The Blind Totem", "CClosedEyeTotemPuzzle"),
                  16: ("The Heathen Chief", "CConvertHeathenChiefPuzzle")}
# The buildings (the game's own milestone tips name them), their project ids, classes and points needed.
BUILDING_CLASSES = {19: ("Hut 1", "CHouse1", 2_000, 12), 20: ("Hut 2", "CHouse2", 2_000, 4),
                    21: ("Hut 3", "CHouse3", 2_000, 1), 22: ("The Clothing Hut", "CClothingHut", 2_000, 12),
                    23: ("The Love Shack", "CLoveShack", 2_000, 400), 24: ("The Nursery School", "CNurseryHut", 2_000, 50),
                    18: ("The fire pit", "CFirePit", 3, None)}


def _actions(points: int, per: int) -> int:
    return -(-points // per)


def _conceive(parenting: int, medicine: int) -> str:
    """rand(300) + 50 - 50 x Medicine <= Parenting (0x468BB6), as the Births and gender group gives it."""
    return chance(sum(1 for v in range(32768) if v % 300 + 50 - 50 * medicine <= parenting))


_MULTI, _TRIPLE = below(100, 7), below(100, 25)
_TWINS = times(_MULTI, 32768 - _TRIPLE)
_TRIPLETS = times(_MULTI, _TRIPLE)


def _feature(feature: str) -> str:
    """"With the patcher (<name>, on/off by default)": the patch's name and whether the patcher ticks it by default."""
    return f"With the patcher (\"{gm.feature_name(feature)}\", {'off' if feature in DEFAULT_OFF else 'on'} by default)"


# The VV5 patches named below that the patcher's default selection leaves off (vv_fun_patcher_gui.DEFAULT_OFF_FUN_PATCH_IDS;
# the test keeps the two the same).
DEFAULT_OFF = frozenset({"vv5_learning_never_fails", "vv5_everyone_collects_like_vv1", "vv5_super_secret_golden_mushroom",
                         "vv5_story_cheat_upgrades", "vv5_story_cheat_upgrades_cost_tech_points"})
ORIGINS = "vv5_enable_origins_exclusive_features"
STORY = "vv5_story_cheat_upgrades"
STORY_COST = "vv5_story_cheat_upgrades_cost_tech_points"
PATCHES = (ORIGINS, STORY, STORY_COST, "vv5_learning_never_fails", "vv5_heathen_mommy_puzzle",
           "vv5_statue_polishing_or_honoring", "vv5_easier_devotee_training", "vv5_vv4_nursery_divisor_parity",
           "vv5_builders_fix_huts", "vv5_builders_and_healers_work_first", "vv5_super_secret_golden_mushroom",
           "vv5_everyone_collects_like_vv1")


# ---------------------------------------------------------------------------
# Technologies
# ---------------------------------------------------------------------------

def _tech_entries() -> list[Entry]:
    p = faith._p
    sick = (chance(at_most(1440, 3)), chance(at_most(2460, 3)), chance(at_most(5400, 2)))
    out = [Entry(TECH, "The Tech screen", "tech points", (
        "every one of the six technologies starts at level 1 in a new village (0x423590) and goes up to level 3. Each "
        "level is bought with tech points, the price in the game's own table (0x4CA3B4); with fewer tech points the "
        "purchase is refused and nothing is spent, otherwise the price is taken at once and the level goes up by 1 "
        "(0x44167F-0x4416B4). At level 3 the game shows \"Fully Researched\" and nothing more can be bought. Three island "
        "events can also raise a level for free, each on one of its two choices: You're Doing It Wrong! and The "
        "Advanced Artifacts (Science, 49.95% of the time) and The Migrating Fruit Bats (Food Mastery, every time) "
        "(see Island events)."), VERIFIED_C)]
    research = {1: ("÷ 11", "÷ 7"), 2: ("÷ 9", "÷ 7"), 3: ("÷ 7", "÷ 5")}
    effects = {
        "Science": {
            1: ("each successful research session gives the researcher's Research skill {0} tech points (rounded down), "
                "twice that on Fast and 0.6 of it on Slow; while catching up {1} at any speed (see Tech points and "
                "effects).", ()),
            2: ("research gives the Research skill {0} (catching up {1}).",
                (("The Clothing Hut's site appears once Science is above 1 (its reveal 0x4357FC, run by the buildings' "
                  "update 0x434BF0).", VERIFIED_C),
                 ("The Advanced Artifacts island event needs Science exactly at level 2; You're Doing It Wrong! needs it "
                  "below 2 (see Island events).", VERIFIED_E))),
            3: ("research gives the Research skill {0} (catching up {1}).", ()),
        },
        "Medicine": {
            1: (f"each believer who is not sick falls sick with a chance of {sick[0]} each {AGE_UNIT}; an old believer "
                f"(50 years or more) who escapes that roll has a second one of {chance(at_most(1000, 14))}; old-age "
                f"death rolls start past 55 years; a pregnancy is "
                f"always one baby; at Parenting 50 an embrace conceives {_conceive(50, 1)} of the time.", ()),
            2: (f"falling sick {sick[1]} an age unit; old from 58 years; old-age rolls past 63; at Parenting 50 an "
                f"embrace conceives {_conceive(50, 2)} of the time.",
                (("Dropping a villager on the medicine spot to study needs Medicine 2, and a studying villager keeps the "
                  "task only with Healing 6 or more (0x47998F, 0x46BDED); the drop handler is registered (0x47A9AB) but "
                  "its call from the drop was not traced.", UNCONFIRMED),)),
            3: (f"falling sick {sick[2]} an age unit; old from 66 years; old-age rolls past 71; at Parenting 50 an "
                f"embrace conceives {_conceive(50, 3)} of the time; a believer who is not sick passes the regain-health "
                f"check (+1 health) every age unit while there is food (see Chances); and a pregnancy brings twins "
                f"{chance(_TWINS)} and triplets "
                f"{chance(_TRIPLETS)} of the time (only at this level).", ()),
        },
        "Learning": {
            1: (f"every task's skill check (a harvest, a build action, a cure, research, an embrace, Honoring) succeeds "
                f"on a roll of 0 to 99 at or under the skill + 33: {chance(below(100, 34))} at skill 0.", ()),
            2: (f"the skill check gets 15 more: skill + 48 or under, {chance(below(100, 49))} at skill 0.", ()),
            3: (f"the skill check gets 30 more: skill + 63 or under, {chance(below(100, 64))} at skill 0.",
                (("The Nursery School's site appears once Learning is above 2 (its reveal 0x4358BC).", VERIFIED_C),)),
        },
        "Construction": {
            1: ("only Hut 1's site is open; Hut 2 and Hut 3 do not appear yet, so the tribe cannot grow past 16 "
                "believers (the babies they carry counted) until Construction 2 and Hut 2.", ()),
            2: ("Hut 2's site appears (0x4356FC); the Tribute Statue's second stage can be worked on once Spirituality "
                "is at level 2 too (0x432350).", ()),
            3: ("Hut 3's site appears (0x43576C); the Tribute Statue's third stage can be worked on once Spirituality "
                "is at level 3 too.", ()),
        },
        "Food Mastery": {
            1: ("every food gain is stored as it is.", ()),
            2: ("every food gain is raised by half, rounded down (0x41EB5B): a brown mushroom 6 becomes 9, a red one 35 "
                "becomes 52; losses are not changed.", ()),
            3: ("every food gain is doubled (0x41EB62): a brown mushroom 12, a red one 70; losses are not changed.", ()),
        },
        "Spirituality": {
            1: (f"each {AGE_UNIT} every believer gains 1 Faith {p(10)} of the time from this roll (see Faith and "
                "Heathens); every successful Devotion skill check gains 1 more Devotion (0x46BC89).", ()),
            2: (f"Faith +1 {p(20)} of the time each age unit; the Divine Energy cap +50 (0x425071); the Tribute "
                "Statue's second stage can be worked on with Construction 2 (0x432350); every successful Devotion "
                "skill check gains 2 more Devotion (0x46BC89).", ()),
            3: (f"Faith +1 {p(30)} of the time each age unit; the Divine Energy cap +50 more (0x425085); the statue's "
                "third stage with Construction 3; every successful Devotion check gains 3 more Devotion.", ()),
        },
    }
    for tid, name, two, three in TECHS:
        for level, cost in ((1, "every village starts at it"), (2, f"{two:,} tech points"),
                            (3, f"{three:,} tech points")):
            text, subs = effects[name][level]
            if name == "Science":
                text = text.format(*research[level])
            subs = tuple(subs)
            if name == "Learning":
                subs += ((f"{_feature('vv5_learning_never_fails')}: every believer's work skill check succeeds "
                          "(Farming, Building, Research, Healing, Parenting and Devotion), at every Learning level.",
                          VERIFIED_C),) if level == 1 else ()
            verified = VERIFIED_C if name == "Construction" else VERIFIED_E
            out.append(Entry(TECH, f"{name} level {level}", cost, text, verified, subs))
    return out


# ---------------------------------------------------------------------------
# God powers (the full lines are under God powers; each one's own entry here)
# ---------------------------------------------------------------------------

POWER_WORDS = {
    "Spawn Butterflies": "for 2 minutes 6 seconds of real-life time (real time, at every speed, paused or not) every living child under 14 not being carried "
                         "goes \"Playing with butterflies!\"; adults are not drawn.",
    "Swarm of Bees": "every living villager within 150 pixels hides or runs, nobody loses health; cast on the noni "
                     "bushes it gives +20 noni at once.",
    "Sunshine": "makes it sunny at once (a weather spell of 1.5 to 3, 3 to 6 or 5 to 10 real-life minutes on Fast, "
                "Normal or Slow), ending a Tempest or any rain.",
    "Lightning Strike": "everyone within 300 pixels hides, nobody loses health; on the built fire pit it lights the "
                        "fire for 10, 20 or 33 hours 20 minutes of real-life play on Fast, Normal or Slow; on the Pain "
                        "Totem it opens 75 real-life seconds in which villagers work on taking it down.",
    "Hand of Bloom": "on the field with the Hydroponic Farm built, fills the crops to 800; on the noni bushes +100 to "
                     "+199 noni over 100 to 199 updates; elsewhere 17 to 22 plants within 104 pixels, each a mushroom "
                     "half the time while 10 to 12 mushroom places are left.",
    "Tempest": "a full-strength storm (weather 5) for one weather spell; while it rains every random spawn is a "
               "mushroom; with The Lake not started and the weather level above 50, The Lake gets 1 of its 2 points "
               "120 real-life seconds later (real time).",
    "Fog of Doom": "fog for 2 real-life minutes (real time, at every speed, paused or not); mushrooms and collectibles appear twice as often (36 in 32,768 each "
                   "update instead of 18).",
    "Time Warp": "the target villager ages 20 times as fast for 5 real-life minutes (real time, paused or not; about 30, 15 or 10 age units on "
                 "Fast, Normal or Slow) and walks and works 10 times as fast; not saved, ended by quitting.",
    "Revive": "a dead villager still lying on the island comes back with 100 health after 4 real-life seconds (real time); cast "
              "on the dry lake bed with The Lake not started, The Lake gets 1 of its 2 points.",
    "Grant Youth": "a living believer of 14 or more is brought back to 5 years old (100 age units), 3 age units each "
                   "update; skills, likes and Faith are kept. A pregnant villager stays pregnant, but the time she had "
                   "already carried is counted backwards, so the birth comes that much later (0x41FEB0).",
    "Earthquake": "every living villager but the six special roles gains 2 to 8 Faith (a Heathen above 0 joins the "
                  "tribe); 10 real-life seconds (real time) later one collectible drops (72% uncommon, 28% rare) and each "
                  "unfinished project with progress loses some (each started hut 100 of its 2,000).",
}


def _power_entries() -> list[Entry]:
    out = [Entry(POWER, "Divine Energy", "how it is earned", (
        "the God powers' currency. Each believer adds 1 every age unit, 4 at Devotion 50 or more, 9 at 88 or more; "
        "Honoring adds 3, 7 or 12 at those Devotion levels; a relic found again adds 10, 50 or 150 by rarity; the "
        "Blessings Day Celebration island event fills it to the cap. The cap is 5 x (believers + the babies they carry "
        "+ 2), raised by the Tribute Statue, Spirituality and the relics (their own entries), at most 1,000; a power "
        "can be cast whenever the Divine Energy is at least its cost (see God powers)."), VERIFIED_E,
        (("A set-up routine sets the cap to 50 and adds 50 Divine Energy (0x425DA6); that it is the new village's "
          "start was not traced.", UNCONFIRMED),))]
    for name, cost, _ in powers.TABLE:
        out.append(Entry(POWER, name, f"{cost:,} Divine Energy",
                         POWER_WORDS[name] + " Every number and its source: God powers.", VERIFIED_E))
    return out


# ---------------------------------------------------------------------------
# Puzzles
# ---------------------------------------------------------------------------

def _puzzle_entries() -> list[Entry]:
    p = faith._p
    return [
        Entry(PUZZLE, "The Sick Heathen", "cure the sick Heathen Doctor", (
            "a healer's successful cure sets the Heathen Doctor's Faith to 25 to 59, each equally likely (0x468CFB), "
            "so the Doctor joins the tribe as a believer."), VERIFIED_E),
        Entry(PUZZLE, "The Prison Break", "30 successful \"Making a granary out of the fence\" building actions", (
            "the bamboo fence becomes the food bin (0x438BB3: +1 a successful action, done at 30). Until then no "
            "villager gathers food on their own: noni picking, crop harvests and fishing all need it (0x46C583)."),
         VERIFIED_C),
        Entry(PUZZLE, "The Hungry Totem", "villagers dismantle it (\"Dismantling the Hungry Totem\")", (
            "while the game catches up time away, noni is picked only once this totem is down (0x46C5B5); in play "
            "noni is picked once the food bin is built."), VERIFIED_C,
              (("How many dismantling actions it takes was not traced.", UNCONFIRMED),)),
        Entry(PUZZLE, "The Knowing Totem", "villagers dismantle it (\"Dismantling the Knowing Totem\")", (
            "opens the lab: while catching up, research is done only once it is down (0x46C75E); the second "
            "collectible set (the lab gear) can appear only from then on; The Pesky Critter island event becomes "
            "possible."), VERIFIED_C,
              (("How many dismantling actions it takes was not traced.", UNCONFIRMED),)),
        Entry(PUZZLE, "The Hydroponic Farm", "30 points, from the aqueduct repair", (
            "the farm's crops are refilled to 800 every 40 age units (2 hours, 4 hours or 6 hours 40 minutes of "
            "real-life play on Fast, Normal or Slow) and a harvest gives 10, 7 or 4 food (7 while catching up), before "
            "Food Mastery; Hand of Bloom on the field fills the crops at once; solving it adds 80 Faith to the Heathen "
            "Master Farmer (0x439E35); the Army Ants!, Aphid Infestation! and The River Breaks Its Banks events "
            "become possible. The Earthquake takes 1 of the 30 points from an unfinished farm."), VERIFIED_E,
              (("The repair is \"Directing aqueduct repair\", which only a master of Research (88 or more) is kept on "
                "(0x46BE38), and \"Repairing aqueduct\"; how many points each action gives was not traced.",
                UNCONFIRMED),)),
        Entry(PUZZLE, "The Buried Mausoleum", "villagers restore it (\"Restoring the mausoleum\")", (
            "the dead are buried from then on: with a body waiting, an idle villager buries it 25% of the time, and "
            "one with Healing 50 or more 70% of the rest (0x46F130). The Earthquake adds 50 of the 1,000 restoring "
            "points it needs (0x43C9C0)."), VERIFIED_C),
        Entry(PUZZLE, "The Blocking Totem", "villagers dismantle it (\"Dismantling the Blocking Totem\")", (
            "the game's tip says the mausoleum can then be dug out; the code that ties the two was not traced."),
         UNCONFIRMED),
        Entry(PUZZLE, "The Hollow Totem", "village children break it (\"Squeezing into the Hollow Totem\")", (
            "the game's tip says the lake becomes the believers'; what changes in play was not traced."), UNCONFIRMED),
        Entry(PUZZLE, "The Heathen Builder", "a build-off with the Heathen Master Builder", (
            "the Master Builder joins the tribe (the game's tip); how the build-off is won and the Faith it sets were "
            "not traced."), UNCONFIRMED),
        Entry(PUZZLE, "The Lake", "2 points", (
            "1 point from a Tempest cast while The Lake has none and the weather level is above 50 (it comes 120 "
            "real-life seconds later, real time), 1 from Revive cast on the dry lake bed (0x43C7E0, 0x4233DD). Solved, the lake "
            "has fish: a fishing trip gives 4 food a fish, before Food Mastery (0x46D790), and nothing runs out."),
         VERIFIED_E),
        Entry(PUZZLE, "The Pain Totem", "a Lightning Strike on it, then villagers take it down", (
            "villagers work on taking it down only during the 75 real-life seconds (real time) after each strike on it (0x43A0C0). "
            "Solved, healers with nobody to cure study medicine on their own (0x46CD24)."), VERIFIED_E),
        Entry(PUZZLE, "The Rainbow Totem", "villagers put three dyes in the pools and dismantle it", (
            "the game's tip says the warm springs become the villagers'; what changes in play was not traced."),
         UNCONFIRMED),
        Entry(PUZZLE, "The Heathen Scientist", "a proof the Heathen Master Scientist examines", (
            "the Master Scientist joins the tribe (the game's tip); the steps and the Faith set were not traced."),
         UNCONFIRMED),
        Entry(PUZZLE, "The Tribute Statue", "three building stages", (
            f"each stage raises the Divine Energy cap: +50 at the first, +50 more at the second, +100 once solved; "
            f"each age unit every believer gains 1 Faith {p(10)} of the time at the first stage, {p(20)} at the second "
            f"and {p(30)} once solved. The second stage needs Construction and Spirituality both at 2 or more, the "
            "third both at 3 (0x432350). From the first stage villagers choose Honoring as a job (0x46CDB6)."),
         VERIFIED_E,
              (("Polishing the finished statue: work event 40 adds 1 Divine Energy (0x46DA1B); which action queues "
                "that event was not traced.", UNCONFIRMED),
               (f"{_feature('vv5_statue_polishing_or_honoring')}: a villager dropped on the finished statue polishes it "
                "or Honors, 50% each, whatever their skills; one who carries the job on alone keeps the 50/50 only when "
                "checked on that skill, and anyone else 14% of the time.", VERIFIED_C))),
        Entry(PUZZLE, "The Blind Totem", "villagers make and install a golden eye (panning, smelting, installing)", (
            "until it is solved no God power can be cast on the island's north-east corner (world x past 1,815 and y "
            "above 445): the game says \"Your vision and power are blocked here!\" (0x4234C8)."), VERIFIED_E),
        Entry(PUZZLE, "The Heathen Chief", "four necklace pieces brought to the Chief", (
            "the Heathen Chief's Faith is set to 100 (0x4360EE), so the Chief joins the tribe."), VERIFIED_E,
              (("The pieces are the scientist's, the doctor's, the farmer's and the builder's (the game's own action "
                "names); where each is found was not traced.", UNCONFIRMED),)),
        Entry(PUZZLE, "The Heathen Parent", "convert the Heathen Mommy", (
            f"{_feature('vv5_heathen_mommy_puzzle')} only: a new village's Heathen Mommy carries one baby, and solving "
            "her puzzle sets her Faith to 50 to 59, each equally likely, which brings her into the tribe (0x43979C); it "
            "is the 17th puzzle on the Puzzles screen. Without the patch the Puzzles screen stops after puzzle 16 "
            "(0x44974C)."), VERIFIED_E),
    ]


# ---------------------------------------------------------------------------
# Buildings, repairs and upgrades
# ---------------------------------------------------------------------------

def _building_entries() -> list[Entry]:
    build = ("Builders only work on a site that already has some progress (more than 1%), so the player drops the "
             "first builder on it (0x46C791-0x46CA80); every successful Building skill check adds the points one at a "
             "time (0x434D9B).")
    h1, h2, h3 = (BUILDING_CLASSES[n] for n in (19, 20, 21))
    clothing, shack, nursery = (BUILDING_CLASSES[n] for n in (22, 23, 24))
    return [
        Entry(BUILDING, "Hut 1", f"{h1[2]:,} points, {h1[3]} a successful build action ({_actions(h1[2], h1[3])} "
                                 "actions)", (
            "the tribe can grow to 10 believers or more (the babies they carry counted) only with it built: the room "
            "check refuses a pregnancy at 10 to 16 believers without it (0x472C74). " + build), VERIFIED_C),
        Entry(BUILDING, "Hut 2", f"{h2[2]:,} points, {h2[3]} a successful build action ({_actions(h2[2], h2[3])} "
                                 "actions)", (
            "needed for 17 believers or more (0x472C65); its site appears only at Construction 2 (0x4356FC)."),
         VERIFIED_C),
        Entry(BUILDING, "Hut 3", f"{h3[2]:,} points, {h3[3]} a successful build action ({_actions(h3[2], h3[3]):,} "
                                 "actions)", (
            "needed for 35 believers or more (0x472C56); its site appears only at Construction 3 (0x43576C). The "
            "overall limit is 90 believers, 95 with one collection completed, 105 with both (0x472BDC)."), VERIFIED_C),
        Entry(BUILDING, "The Clothing Hut", f"{clothing[2]:,} points, {clothing[3]} a successful build action "
                                            f"({_actions(clothing[2], clothing[3])} actions)", (
            "its site appears at Science 2 (0x4357FC). Built, a villager dropped on it changes clothes (its own "
            "entry)."), VERIFIED_C),
        Entry(BUILDING, "The Love Shack", f"{shack[2]:,} points, {shack[3]} a successful build action "
                                          f"({_actions(shack[2], shack[3])} actions)", (
            "no baby is conceived in play until it is built: the embrace refuses without it (0x468A69). Time away "
            "does not need it (see Time away (catch-up))."), VERIFIED_C),
        Entry(BUILDING, "The Nursery School", f"{nursery[2]:,} points, {nursery[3]} a successful build action "
                                              f"({_actions(nursery[2], nursery[3])} actions)", (
            "its site appears at Learning 3 (0x4358BC). Built, a teacher's lessons raise the children's skills: a "
            "lesson spread over all six skills gives each a fifth of the lesson, six fifths in all (0x425FDF)."),
         VERIFIED_C,
              ((f"{_feature('vv5_vv4_nursery_divisor_parity')}: a spread lesson gives each of the six skills a sixth, "
                "exactly one lesson in all; lessons on the strongest skill are unchanged.", VERIFIED_C),)),
        Entry(BUILDING, "The fire pit", "3 points, from \"Gathering dry grass\", \"Gathering firewood\" and \"Starting "
                                        "a fire\"", (
            "the Lightning Strike lights the built pit for 10, 20 or 33 hours 20 minutes of real-life play on Fast, "
            "Normal or Slow. While it burns a believer who fails the health check gets a second roll (see Chances) and "
            "a research success gives 1 more tech point 10.01% of the time; the Cold Snap island event puts it out."),
         VERIFIED_E,
              (("Which of the three actions gives each of the 3 points was not traced.", UNCONFIRMED),)),
        Entry(BUILDING, "Fixing a hut (the repair)", "free; a builder's own job", (
            "offered only once Huts 1 to 3 and the Clothing Hut are all built (0x46C9E6): the builder examines one of "
            "the three huts, picked at random, and fixes it 70% of the time (0x463F47); the fix ends with a Building "
            "skill check that trains Building."), VERIFIED_C,
              ((f"{_feature('vv5_builders_fix_huts')}: about three times in four a builder builds first, and with no "
                "project to work on examines and fixes a built hut even before every hut stands.", VERIFIED_C),
               (f"{_feature('vv5_builders_and_healers_work_first')}: builders and healers try their own work first about "
                "three times in four, and in catch-up devotees try Honoring first.", VERIFIED_C))),
    ]


# ---------------------------------------------------------------------------
# Items: mushrooms, collectibles, clothes
# ---------------------------------------------------------------------------

def _item_entries() -> list[Entry]:
    return [
        Entry(ITEM, "Brown mushroom", "appears on the island at random, see Mushrooms", (
            "6 food (9 at Food Mastery 2, 12 at 3) when it reaches the food bin, counted in Mushrooms Found. 92% of "
            "the mushrooms that appear are brown; an unpicked one is gone after 1 minute 30 seconds (real time, the same at every speed) of real-life "
            "time."), VERIFIED_E),
        Entry(ITEM, "Red (rare) mushroom", "appears on the island at random, see Mushrooms", (
            "35 food (52 at Food Mastery 2, 70 at 3), 8% of the mushrooms that appear."), VERIFIED_E,
              ((f"{_feature('vv5_super_secret_golden_mushroom')}: 1 in 1,000,000 random brown or red mushrooms is a "
                "Golden Mushroom worth 100 food, counted as a mushroom.", VERIFIED_E),
               (f"{_feature('vv5_everyone_collects_like_vv1')}: several children dropped on one mushroom or collectible "
                "each pick it up, so it is counted and paid once for each.", UNCONFIRMED))),
        Entry(ITEM, "Relics (the first collectible set, 24 pieces)", "appear on the island at random, 82% common, 13% "
                                                                     "uncommon, 5% rare; see Collectibles", (
            "each piece owned raises the Divine Energy cap by 3 while the set is incomplete (69 with 23 pieces); all "
            "24 give a flat +90. A piece found again gives 10, 50 or 150 Divine Energy by rarity. Completing the set "
            "raises the believers' limit by 5 (90 to 95; 105 with both sets)."), VERIFIED_E),
        Entry(ITEM, "Lab gear (the second collectible set, 24 pieces)", "appear at random only once the Knowing Totem "
                                                                        "is down", (
            "every successful research session gives 0 to (half the pieces owned, less 1) more tech points, each "
            "equally likely (0 to 11 with all 24). A piece found again gives 100, 250 or 1,500 tech points by rarity. "
            "Completing the set raises the believers' limit by 5. Once the Knowing Totem is down, half of the "
            "collectibles that appear are from each set."), VERIFIED_E),
        Entry(ITEM, "A change of clothes", "5,000 tech points, at the built Clothing Hut", (
            "the villager's clothes-changing task (work event 90, queued at 0x45CF5F) takes 5,000 tech points "
            "(0x46CEC7) and opens the outfit chooser: its arrows step the villager's body through the game's 29 outfits "
            "(0 to 28, 0x419CE0); one of its buttons puts the old outfit back and returns the 5,000 (0x419E77). With "
            "fewer than 5,000 tech points the villager is \"Confused\" and nothing is spent (0x46CE93)."), VERIFIED_C),
        Entry(ITEM, "Tech points", "how they are earned", (
            "research (Science level 1 to 3 above), the lab gear, the fire, duplicate lab gear and island events; "
            "they are spent on the technologies and a change of clothes."), VERIFIED_E),
    ]


# ---------------------------------------------------------------------------
# The patcher's upgrades and cheats (Origins, Story / Cheat Upgrades)
# ---------------------------------------------------------------------------

# (row as the menu shows it, stock price) -- native/vv5_task9_origins/vv5_task9_origins.c action_cost, and
# scripts/build_vv5_task9_native_actions.py for the three village events.
ORIGINS_TECH = (
    ("Time Warp", 50_000, "the village moves on 12, 6 or 3 villager years on Fast, Normal or Slow speed (one 12-hour "
                          "real-life clock jump on Fast or Normal, 10 hours on Slow), each villager's age credited as "
                          "the game's own aging does; refused, nothing spent, while paused or with nobody alive."),
    ("Island Event", 30_000, "makes the next island event due now; the game picks it as usual. One at a time: refused, "
                             "nothing spent, while an Island Event or Barrel of Babies is waiting."),
    ("Barrel of Babies", 75_000, "after the Tech screen closes, the game's own Barrel O' Babies! event comes (up to 3 "
                                 "children). Refused, nothing spent, without room for 3 more villagers."),
    ("Tech Point Doubler", 500_000, "doubles every tech point research earns (the base, the lab gear bonus and the "
                                    "fire's +1); island events and duplicate lab gear are not doubled. Removable for "
                                    "free (no refund) and buyable again; not sold with 256 Villagers "
                                    "(Experimental)."),
    ("Food Point Doubler", 500_000, "doubles the food of every mushroom picked up, after Food Mastery (the one food "
                                    "gain it lets through returns to 0x414970, the mushroom pickup that also counts "
                                    "Mushrooms Found); noni picks, crop harvests, fishing and island events are not "
                                    "doubled. Removable for free (no refund) and buyable again; not sold with 256 "
                                    "Villagers (Experimental)."),
    ("Full Heal / Cure All", 30_000, "every living believer is cured of sickness and set to 100 health; each cure "
                                     "counts in People Cured. Heathens are skipped."),
    ("Complete All Collections", 1_000_000, "marks all 48 collectibles found and earns the collection goals still "
                                            "open (the relics, the science items, Master Collector)."),
    ("Reset All Collections", 1_000_000, "clears all 48 collectibles."),
    ("Grant Running to All Villagers", 1_000_000, "every living believer likes running (a free like slot is needed; a "
                                                  "dislike of running is removed)."),
    ("Grant Full Mastery to All Villagers", 1_000_000, "every living believer's six skills are set to 100."),
    ("All Villagers are Exactly 18", 1_000_000, "every living believer is set to 18 years (360 age units)."),
    ("Equal Division of Labor (Includes Parenting)", 1_000_000, "every living believer's job checkmark is shared out "
                                                                 "evenly over the six jobs, men and women each."),
    ("Equal Division of Labor (No Parenting)", 1_000_000, "the same over five jobs, Parenting left out."),
    ("Change Appearance for All", 450_000, "the heads, bodies and masks chosen (by sex, for the whole village, or a "
                                           "mask spread) are written to every active villager at once; charged only "
                                           "when at least one villager changes."),
    ("Clear All Skill Preferences", 500_000, "every living believer's job checkmark is cleared."),
    ("Check Highest Skill (Includes Parenting)", 1_000_000, "every living believer's job checkmark is set to their "
                                                            "highest skill."),
    ("Check Highest Skill (No Parenting)", 1_000_000, "the same, Parenting left out."),
)
ORIGINS_DETAILS = (
    ("Grant Youth", 50_000, "the chosen believer is 35 villager years younger (700 age units), but no younger than 5 "
                            "(100 age units)."),
    ("Grant Full Mastery", 100_000, "the chosen believer's six skills are set to 100."),
    ("Grant Running", 40_000, "the chosen believer likes running; refused, nothing spent, when all three like slots "
                              "are full."),
    ("Set Age to 18", 50_000, "the chosen believer is set to 18 years (360 age units)."),
    ("Change Appearance", 5_000, "the chosen villager's head, body and Heathen mask."),
)


NO_CHANGE_CHECK = frozenset({"Time Warp", "Island Event", "Barrel of Babies", "Tech Point Doubler",
                             "Food Point Doubler"})


def _patcher_entries() -> list[Entry]:
    lead = _feature(ORIGINS)
    out = []
    for screen, rows in (("the Tech screen's Upgrades", ORIGINS_TECH), ("the Villager Details screen's Upgrades",
                                                                       ORIGINS_DETAILS)):
        for name, price, effect in rows:
            subs = ()
            if name == "Barrel of Babies":
                subs = (("Which of the game's two Barrel O' Babies! versions the purchase brings (the believers', slot "
                         "26, or the Heathens') is not settled: the patch's notes name different event numbers.",
                         UNCONFIRMED),)
            unchanged = "" if name in NO_CHANGE_CHECK else " Nothing is spent when nothing would change."
            out.append(Entry(PATCHER, name, f"{price:,} tech points", (
                f"{lead}: on {screen}: {effect}{unchanged}"), VERIFIED_C, subs))
    out.append(Entry(PATCHER, "Story / Cheat Upgrades", "0 tech points", (
        f"{_feature(STORY)}: every Origins upgrade above costs 0 tech points, and the Tech screen's Upgrades add Choose "
        "Time Skip Amount (1 to 72 villager years, run as Time Warps one after another), Pick Island Event (the chosen "
        "event happens if its own condition holds, with the game's own odds) and Custom Island Event."), VERIFIED_C,
        ((f"{_feature(STORY_COST)}: the Origins upgrades keep their prices, Pick Island Event and Custom Island Event "
          "cost 30,000 tech points each, and Choose Time Skip Amount 50,000, taken once when the skip starts; ticking "
          "Story / Cheat Upgrades ticks this too.", VERIFIED_C),)))
    return out


ENTRIES: tuple[Entry, ...] = ()


def entries() -> tuple[Entry, ...]:
    """Every entry, in the page's order: technologies, God powers, puzzles, buildings, items, the patcher's upgrades."""
    global ENTRIES
    if not ENTRIES:
        ENTRIES = tuple(_tech_entries() + _power_entries() + _puzzle_entries() + _building_entries()
                        + _item_entries() + _patcher_entries())
    return ENTRIES


def item_facts(village: gm.Village | None = None) -> list[gm.Fact]:
    """The group's lines: each entry a bullet ("<name> (<cost>): <effect>"), its sub-lines indented under it.  The
    general rules only: nothing here is read from a save (`village` is accepted for the page's wiring)."""
    out: list[gm.Fact] = []
    for entry in entries():
        out.append(gm.Fact(ITEMS_GROUP, f"{entry.name} ({entry.cost}): {entry.text}", entry.verified))
        for text, verified in entry.subs:
            out.append(gm.Fact(ITEMS_GROUP, text, verified, sub=True))
    return out
