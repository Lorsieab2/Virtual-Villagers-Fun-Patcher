"""Game Mechanics: every technology, puzzle, building, item, stew and patcher upgrade of The Tree of Life (VV4).

The owner's rule for every Game Mechanics page (2026-10-27): "Elaborate on what every store item and upgrade and
research and everything does!!!"  item_facts() gives each player-facing thing its own entry, in the page's Fact
format (src/vv_game_mechanics.py), the same shape as src/vv_game_mechanics_items_vv3.py: its cost or how it is earned,
its exact effect with numbers, odds and timings, who or what it acts on, the stock value first, then the patched one.
A rule another group gives in full (the odds under Chances, the refills under Refills, the stew pot's code under
Other) is named and pointed to, not repeated.

LABELS: VERIFIED_E (gm.RUNNING) emulated from a live caller; VERIFIED_C (gm.CODE) traced on a live path in the stock
executable; gm.OWNER the owner's word; UNCONFIRMED (False) not yet proven.

What was read for this module (2026-10-27, research/stock-executables, 929,792 bytes):
  * TECH PRICES: 0x41E220(id) = dword [0x4BC18C + 4 * (level + 1 + 3 * id)] (Science 8,000 / 70,000, Medicine
    5,000 / 50,000, Learning 4,000 / 35,000, Construction 5,000 / 65,000, Food Mastery 3,000 / 40,000, Dendrology
    3,000 / 60,000); every technology starts at level 1 (0x41E150) and stops at 3 (0x41E1D0); the save loader refuses a
    level outside 1..3.  Levels go up only by the purchase (0x43EAFE), the loader (0x41E29B) and island events
    (0x415314 Food Mastery, 0x41591D / 0x416DBF Dendrology, 0x416DB2 Medicine).
  * Tech readers (0x41E1C0 on 0x4D6F5C): Food Mastery 0x41D933 (every food gain, 0x41D920); Learning 0x462AD5 (the
    skill check); Medicine 0x45E8A7 (twins), 0x45E964 (sickness), 0x465EBA / 0x465EEA (old age), 0x468669 (health);
    Science 0x464BE8 (research); Construction 0x46F38A (< 2: the second hut's drop says Confused), 0x46F477 (< 3: the
    third hut's), 0x433FB4 (< 2: clearing rubble); Dendrology 0x437B12 (< 2: binding the branch, puzzle 12 unsolved),
    0x43847E (< 3: purifying the tree, puzzle 14 unsolved); the buildings' unlock predicates 0x430B90 / 0x430C00
    (Construction), 0x430CF0 (Science), 0x430DB0 (Learning), 0x430E30 (Medicine).
  * NEW CLOTHES: 0x46F75B..0x46F775: project 22 (the Clothing Hut) finished and at least 5,000 tech points
    (cmp [0x4D6F88], 0x1388).
"""
from __future__ import annotations

from dataclasses import dataclass

import vv_game_mechanics as gm
from vv_game_mechanics_chances import below, chance

GAME = 4
TECH_GROUP = "Technologies"
PUZZLE_GROUP = "Puzzle rewards"
BUILDING_GROUP = "Buildings and repairs"
ITEMS_GROUP = "Items, potions and stews"
PATCHER_GROUP = "Patcher upgrades"
ITEM_GROUPS = (TECH_GROUP, PUZZLE_GROUP, BUILDING_GROUP, ITEMS_GROUP, PATCHER_GROUP)

TECH, PUZZLE, BUILDING, ITEM, PATCHER = "technology", "puzzle", "building", "item", "patcher"
GROUP_OF = {TECH: TECH_GROUP, PUZZLE: PUZZLE_GROUP, BUILDING: BUILDING_GROUP, ITEM: ITEMS_GROUP,
            PATCHER: PATCHER_GROUP}

VERIFIED_E = gm.RUNNING
VERIFIED_C = gm.CODE
UNCONFIRMED = False

# The six technologies (the label strings 0x3ED..0x3F2, eTech*Label in the game's sm.xml) and their level 2 and 3
# prices (0x4BC18C); every one starts at level 1.
TECHS = ("Science", "Medicine", "Learning", "Construction", "Food Mastery", "Dendrology")
TECH_PRICES = {"Science": (8_000, 70_000), "Medicine": (5_000, 50_000), "Learning": (4_000, 35_000),
               "Construction": (5_000, 65_000), "Food Mastery": (3_000, 40_000), "Dendrology": (3_000, 60_000)}
# The seven buildings (projects 19..25, the build rates [+0x24] each registers: 0x431052 .. 0x431372).
BUILDINGS = {"Hut 1": 12, "Hut 2": 4, "Hut 3": 1, "The Clothing Hut": 12, "The Love Shack": 200,
             "The Nursery School": 50, "The Hospital": 50}
BUILD_TOTAL = 2_000
CLOTHES_PRICE = 5_000

DEFAULT_OFF = frozenset({"vv4_learning_never_fails", "vv4_everyone_collects_like_vv1",
                         "vv4_super_secret_golden_mushroom", "vv4_manual_drop_breeding_overrides_birth_control",
                         "vv4_story_cheat_upgrades", "vv4_story_cheat_upgrades_cost_tech_points",
                         "vv4_population_256"})

ORIGINS = "vv4_enable_origins_exclusive_features"
VILLAGE_WIDE = "vv4_origins_village_wide_upgrades"
STORY = "vv4_story_cheat_upgrades"
STORY_COST = "vv4_story_cheat_upgrades_cost_tech_points"


@dataclass(frozen=True)
class Entry:
    kind: str
    name: str
    text: str
    verified: bool | str = False
    subs: tuple[tuple[str, bool | str], ...] = ()


# The village-wide row's manifest is not a *_feature.json, so gm.feature_name does not find its name.
NAMES = {VILLAGE_WIDE: "Enable Origins Tech, Details, and Village-Wide Upgrades"}


def setting(fid: str) -> str:
    """A patch's name as the patcher shows it."""
    return NAMES.get(fid) or gm.feature_name(fid)


def patch(fid: str) -> str:
    """'With the patcher ("<setting>", on by default)' -- the setting's name as the patcher shows it."""
    return f"With the patcher (\"{setting(fid)}\", {'off' if fid in DEFAULT_OFF else 'on'} by default)"


def _ch(n: int, d: int = 100) -> str:
    return chance(below(d, n))


def _tp(n: int) -> str:
    return f"{n:,} tech points"


# ---------------------------------------------------------------------------
# Technologies
# ---------------------------------------------------------------------------

def _level(name: str, level: int, text: str, verified: bool | str,
           subs: tuple[tuple[str, bool | str], ...] = ()) -> Entry:
    """One technology level's entry: its price (or that a new village has it), then what it gives."""
    head = "a new village's level, no price" if level == 1 else _tp(TECH_PRICES[name][level - 2])
    return Entry(TECH, f"{name} level {level}", f"{head}. {text}", verified, subs)


def _techs() -> list[Entry]:
    research = ("Each successful research session pays the researcher's Research skill ÷ {d}, rounded down -- "
                "nothing from the skill below Research {d} -- twice that on Fast speed and 0.6 of it on Slow; then 3 "
                "times that with the Purify Tree's glow, up to (Lab Equipment pieces found - 1) more, and 1 more "
                "10.01% of the time while the Fire Pit burns (Tech points and effects). While the game catches up "
                "time away: ÷ {c} at every speed.")
    sick = ("Falling sick, rolled each age unit (3, 6 or 10 real-life minutes on Fast, Normal or Slow) for each "
            "healthy villager: {odds}, and an old villager who escapes it 15 in 1,000 more (Chances, Falling sick). "
            "A villager is old from {old} years; the old-age death rolls start at {death} years. Conception at "
            "Parenting P: (P + {p}) in 300 (Births and gender).")
    learn = ("Every skill check (a harvest, a building step, a cure, a research session, an embrace) succeeds at the "
             "skill + {n}% for a villager neutral about learning, + {like}% for one who likes it, + {dis}% for one "
             "who dislikes it; the skill gained on a success is not changed.")
    food = ("Every food the villagers gather -- blackberries, fruit, fish, the Golden Fish, crabs and mushrooms -- "
            "{how}.")
    return [
        Entry(TECH, "The Tech screen", (
            "each technology is bought one level at a time with tech points on the Tech screen; the price of the "
            "next level is taken at once and the level goes up at once. All six start at level 1 in every new "
            "village and go to 3. Without enough tech points the game says \"You don't have enough tech points!\" "
            "and nothing is taken. Some island events also give a level (Island events). Each level below is what "
            "that level gives."), VERIFIED_C),
        _level("Science", 1, research.format(d=11, c=7), VERIFIED_E),
        _level("Science", 2, research.format(d=9, c=7), VERIFIED_E,
               (("Level 2 makes the Clothing Hut appear as a building site.", UNCONFIRMED),)),
        _level("Science", 3, research.format(d=7, c=5), VERIFIED_E),
        _level("Medicine", 1, sick.format(odds="4 in 1,440", old=50, death=55, p=1), VERIFIED_C),
        _level("Medicine", 2, sick.format(odds="4 in 2,460", old=58, death=63, p=51), VERIFIED_C),
        _level("Medicine", 3, sick.format(odds="3 in 5,400", old=66, death=71, p=101) + " Twins and triplets "
               "become possible: a pregnancy is multiple " + _ch(7) + " of the time, a quarter of those triplets; and "
               "a fed villager who is not sick always passes the check for health coming back.", VERIFIED_C,
               (("Level 3 makes the Hospital appear as a building site.", UNCONFIRMED),)),
        _level("Learning", 1, learn.format(n=34, like=67, dis=17), VERIFIED_C),
        _level("Learning", 2, learn.format(n=49, like=82, dis=32), VERIFIED_C),
        _level("Learning", 3, learn.format(n=64, like=97, dis=47), VERIFIED_C,
               (("Level 3 makes the Nursery School appear as a building site.", UNCONFIRMED),)),
        _level("Construction", 1, "Hut 1 is the only hut a villager dropped there builds; dropped on the second or "
                                  "third hut, or the rubble, the villager is \"Confused\".", UNCONFIRMED),
        _level("Construction", 2, "Villagers dropped there build Hut 2 and clear the rubble.", UNCONFIRMED,
               (("Level 2 makes Hut 2 appear as a building site.", UNCONFIRMED),)),
        _level("Construction", 3, "Villagers dropped there build Hut 3.", UNCONFIRMED,
               (("Level 3 makes Hut 3 appear as a building site.", UNCONFIRMED),)),
        _level("Food Mastery", 1, food.format(how="counts as it is"), VERIFIED_E),
        _level("Food Mastery", 2, food.format(how="counts half as much again (+ the amount ÷ 2, rounded down)"),
               VERIFIED_E),
        _level("Food Mastery", 3, food.format(how="counts double"), VERIFIED_E),
        _level("Dendrology", 1, "Neither the branch can be bound (Pruning the Tree) nor the tree purified (Purify "
                                "Tree).", UNCONFIRMED),
        _level("Dendrology", 2, "The branch can be bound (Pruning the Tree).", UNCONFIRMED),
        _level("Dendrology", 3, "The tree can be purified (Purify Tree); below it the game says \"Your tribe must "
                                "master dendrology to cure the tree.\"", UNCONFIRMED),
    ]


# ---------------------------------------------------------------------------
# Puzzles
# ---------------------------------------------------------------------------

def _puzzles() -> list[Entry]:
    tree = ("one of the five stages of the Tree of Life (The Stream, Pruning, Honoring, Purify and Decorating each "
            "give one; the tree's art follows them)")
    return [
        Entry(PUZZLE, "The Cutting Tool", "solved in 1 step; the cutting tools made count on hand (Village counts).",
              UNCONFIRMED),
        Entry(PUZZLE, "The Stream", (
            f"solved in 1 step; {tree}. The stream gathers 2% more debris with each growth of the blackberries "
            "(every 6 game minutes), up to 100%."), VERIFIED_E),
        Entry(PUZZLE, "Boiling Water", "solved in 1 step.", UNCONFIRMED),
        Entry(PUZZLE, "Soap Invented", (
            "solved in 1 step: soap made in the pot (pulpy vines x3 in salt water); the soap bars made count on "
            "hand."), UNCONFIRMED),
        Entry(PUZZLE, "The Butterflies", "solved in 1 step; solving it needs The Stream solved.", UNCONFIRMED),
        Entry(PUZZLE, "The Frog Rescue", "solved after 5 steps.", UNCONFIRMED),
        Entry(PUZZLE, "The Cooking Pit", (
            "solved in 1 step. Solved, farmers are offered the fruit (\"Attempting to retrieve fruit\": stomping or "
            "shaking down fruit, 3 food before Food Mastery), and while the game catches up time away each adult "
            "assigned to the fruit, or (Farming - 25)% of the others, adds 5 food per age unit."), VERIFIED_C),
        Entry(PUZZLE, "Cloth Invented", "solved in 1 step; the cloth bolts made count on hand.", UNCONFIRMED),
        Entry(PUZZLE, "The Nursery School", "solved in 1 step.", UNCONFIRMED),
        Entry(PUZZLE, "The Mossy Rocks", (
            "solved after 5 steps; a crab caught there (\"Catching a crab\") brings 35 food before Food Mastery."),
            VERIFIED_E),
        Entry(PUZZLE, "The Grand Feast", (
            "solved in 1 step: the spicy, sweet and soapy stew in a well-cooked pot (20 heat) with its 4 feast "
            "items (Items, potions and stews)."), VERIFIED_E),
        Entry(PUZZLE, "Fishing Nets", (
            "solved in 1 step. Solved, fishing is offered: 4 food a fish before Food Mastery, or 8 for a Golden "
            "Fish, which comes (2 x fish scales found + 1)% of the time -- 3% with 1 scale, 25% with all 12, never "
            "with none."), VERIFIED_E,
            ((patch("vv4_complete_scales_golden_fish") + ": a Golden Fish comes only with all 12 scales (25% of the "
              "time).", UNCONFIRMED),)),
        Entry(PUZZLE, "Pruning the Tree", f"solved in 1 step (binding the branch); {tree}.", VERIFIED_E,
              (("Binding the branch needs Dendrology level 2.", UNCONFIRMED),)),
        Entry(PUZZLE, "Honoring the Tree", f"solved in 1 step (the sweet x3 stew honours the tree); {tree}.",
              VERIFIED_E),
        Entry(PUZZLE, "Purify Tree", (
            f"solved in 1 step; {tree}. One of the Purify Tree's two results gives the villager a glow for 4 "
            "real-life minutes (240 seconds), and while it lasts their research brings 3 times the tech points."),
            VERIFIED_E,
            (("Purifying the tree needs Dendrology level 3.", UNCONFIRMED),)),
        Entry(PUZZLE, "Decorating the Tree", (
            f"solved after 3 steps; {tree}. With 3 or more tree stages a hummingbird flies by every 3 to 5 real-life "
            "minutes, every 23 to 25 once the tree is decorated; it changes nothing."), VERIFIED_E),
    ]


# ---------------------------------------------------------------------------
# Buildings and repairs
# ---------------------------------------------------------------------------

def _buildings() -> list[Entry]:
    def steps(rate: int) -> str:
        return (f"each successful step adds {rate} build point{'s' if rate > 1 else ''} "
                f"({-(-BUILD_TOTAL // rate):,} steps)")
    return [
        Entry(BUILDING, "Building in general", (
            "every building needs 2,000 build points, and each successful build step (the Building skill check "
            "passed, the builder standing in the building's area) adds that building's own amount."), VERIFIED_E,
            (("A builder takes on a building by itself only once it is at least 1% built, so the first push on a new "
              "site is a villager you drop there.", UNCONFIRMED),
             ("A builder who dislikes wood considers each wooden building only 16% of the time and walks off 40% of "
              "the time once started.", VERIFIED_C))),
        Entry(BUILDING, "Hut 1", (
            f"{steps(12)}. Room for babies: from 10 villagers no pregnancy starts "
            "without Hut 1, from 17 without Huts 1 and 2, from 35 without all three."), VERIFIED_C),
        Entry(BUILDING, "Hut 2", f"{steps(4)}. It counts toward the room for babies (Hut 1).", VERIFIED_E,
              (("It is built only at Construction level 2.", UNCONFIRMED),)),
        Entry(BUILDING, "Hut 3", f"{steps(1)}. It counts toward the room for babies (Hut 1).", VERIFIED_E,
              (("It is built only at Construction level 3.", UNCONFIRMED),)),
        Entry(BUILDING, "The Clothing Hut", (
            f"{steps(12)}. It never counts toward the room for babies; finished, it is where villagers get new "
            "clothes (Items, potions and stews)."), VERIFIED_E,
            (("It appears as a site at Science level 2.", UNCONFIRMED),)),
        Entry(BUILDING, "The Love Shack", (
            f"{steps(200)}. Until it is finished no villager can conceive while "
            "the game is played (\"The love shack has not been completed!\"); time away does not check it."),
            VERIFIED_C),
        Entry(BUILDING, "The Nursery School (the building)", (
            f"{steps(50)}. Finished, each child gains the teacher's five skills added up ÷ 240 per real-life hour at "
            "any speed, in skills under 50 (Time away)."), VERIFIED_E,
            (("It appears as a site at Learning level 3.", UNCONFIRMED),)),
        Entry(BUILDING, "The Hospital", (
            f"{steps(50)}. Finished, a healer with nobody sick studies medicine there (Healing practice), and a "
            "healer dropped there keeps going back with Healing 6 or more; it cures nobody and heals no "
            "health."), VERIFIED_C,
            (("It appears as a site at Medicine level 3.", UNCONFIRMED),)),
        Entry(BUILDING, "Fixing huts", (
            "only once Huts 1 to 3 and the Clothing Hut are all finished: a builder examining a hut goes on to fix "
            "it " + _ch(70) + " of the time, otherwise says \"This hut is still in good repair.\" Fixing trains "
            "Building and adds nothing to the hut."), VERIFIED_C,
            ((patch("vv4_builders_fix_huts") + ": builders build first and fix huts when no building can be worked "
              "on.", UNCONFIRMED),)),
        Entry(BUILDING, "The Fire Pit", (
            "lit, it burns 10, 20 or 33 hours 20 minutes of real-life play on Fast, Normal or Slow speed; feeding "
            "the pit again while it burns starts that time over. While it burns each research session gives 1 more "
            "tech point 10.01% of the time, and health comes back more often (Chances, Regaining health)."),
            VERIFIED_E,
            (("It goes out when its timer runs out; rain and the weather do not affect it. The Cold Snap island event "
              "(it needs the Fire Pit burning) puts it out.", gm.OWNER),)),
    ]


# ---------------------------------------------------------------------------
# Items, herbs and stews
# ---------------------------------------------------------------------------

# Each stew (the recipe 0x42ECA0 via 0x42DBF0; what it does: the effect switch 0x41DEE0, vv_game_mechanics_vv4
# STEW_LINES): (name, recipe, what it does, label).
STEWS = (
    ("Spicy stew", "spicy x3", "the villager who eats it runs to the stream", VERIFIED_E),
    ("Spicy, spicy, sweet stew", "spicy, spicy, sweet", "every adult comes to the pot", VERIFIED_E),
    ("Spicy, spicy, soapy stew", "spicy, spicy, soapy", "the villager \"has got to go\"", VERIFIED_E),
    ("Spicy, sweet, sweet stew", "spicy, sweet, sweet", "the whole village comes to the pot", VERIFIED_E),
    ("The Grand Feast stew", "spicy, sweet, soapy, in a well-cooked pot (20 heat) with the 4 feast items",
     "solves The Grand Feast", VERIFIED_E),
    ("Spicy, soapy, soapy stew", "spicy, soapy, soapy",
     "the villager goes \"Burping up soap bubbles\", and it counts the Soapy Stew achievement", VERIFIED_E),
    ("Sweet stew", "sweet x3", "honours the tree (Honoring the Tree)", VERIFIED_E),
    ("Sweet, sweet, soapy stew", "sweet, sweet, soapy", "the children get hiccups", VERIFIED_E),
    ("Healing stew", "sweet, soapy, soapy",
     "the villager who eats it regains 25 to 59 health (5 to 14 while the village has under 100 food), and cannot eat "
     "this stew again for 10 real-life minutes", VERIFIED_E),
    ("Soapy stew", "soapy x3",
     "the villager says \"I feel sick!\" and goes \"Throwing up soapy stew!\" -- it does not make them sick -- and "
     "cannot eat this stew again for 10 real-life minutes", VERIFIED_E),
    ("Soap", "pulpy vines x3, in salt water, with no heat", "makes soap", VERIFIED_E),
    ("Soapy herbs in salt water", "soapy x3, in salt water, with no heat",
     "a stew of its own (stew 10 of the recipe table); what it gives was not traced here", UNCONFIRMED),
    ("A failed stew", "any other mix", "tastes nasty (fresh water) or too salty (salt water)", VERIFIED_E),
)


def _items() -> list[Entry]:
    out = [
        Entry(ITEM, "The herbs", (
            "spicy, sweet and soapy herbs, and pulpy vines, go into the pot 3 at a time, with fresh or salt water; "
            "the mix decides the stew (below)."), VERIFIED_E),
        Entry(ITEM, "Hot rocks", (
            "each hot rock dropped in the pot adds 10 heat, which only emptying the pot takes away; a stew is ready "
            "at 10 heat, the Grand Feast at 20 with its 4 feast items, and the two salt-water mixes need no heat. "
            "The pot takes things only while it is hot: making a stew ends that, and an unfinished Grand Feast stays "
            "hot for 10 real-life minutes on Normal speed (5 on Fast, 16 minutes 40 seconds on Slow) after each "
            "thing added."), VERIFIED_E,
            (("Some stews can be reheated by putting another hot rock in the pot.", gm.OWNER),
             ("In the game's code a hot rock that goes into the hot pot while its stew is ready makes the same stew "
              "again and starts its 5 real-life minutes over; nothing limits how often.", VERIFIED_E))),
        Entry(ITEM, "A ready stew", (
            "the pot's on-screen countdown starts at 5:00 on Normal speed, 2:30 on Fast and 8:20 on Slow, and the "
            "pot empties itself at 0:00, 5 real-life minutes after the stew was made at every speed. A villager "
            "dropped on the pot eats it. The save does not keep the pot."), VERIFIED_E),
        Entry(ITEM, "The grate", "the pot can be emptied by dropping a villager on the grate.", gm.OWNER),
        Entry(ITEM, "Eating a stew", (
            "a villager who already has that stew's effect, or already has 12 effects, is refused: \"That villager "
            "can't eat more stew so soon.\" It lasts until that effect ends (10 real-life minutes for the healing "
            "and soapy stews), for that villager and that stew only; saving the game ends every villager's stew "
            "effects."), VERIFIED_E),
    ]
    out += [Entry(ITEM, name, f"{recipe}: {does}.", ok) for name, recipe, does, ok in STEWS]
    out += [
        Entry(ITEM, "Blackberries", (
            "the bushes hold up to 1,000 and grow 2 every 6 game minutes (6 real-life minutes on Normal speed). "
            "Picking brings the berries ÷ 100 (at least 2) food, a harvest the berries up to 30, before Food "
            "Mastery; picking is offered only above 3 berries."), VERIFIED_E),
        Entry(ITEM, "Fruit", "stomping or shaking down fruit brings 3 food before Food Mastery (after The Cooking "
                             "Pit).", VERIFIED_E),
        Entry(ITEM, "Fish and the Golden Fish", (
            "after Fishing Nets: a fish brings 4 food before Food Mastery, a Golden Fish 8; a Golden Fish comes "
            "(2 x fish scales + 1)% of the time (Fishing Nets)."), VERIFIED_E),
        Entry(ITEM, "Crabs", "a crab caught at the Mossy Rocks brings 35 food before Food Mastery.", VERIFIED_E,
              (("A crab a villager finds (\"This villager found a crab!\") brings 55 food before Food Mastery.",
                gm.OWNER),)),
        Entry(ITEM, "Mushrooms", (
            "brown 91.99% of the time, worth 6 food, red (rare) 8.01%, worth 35, before Food "
            "Mastery (how often: Mushrooms)."), VERIFIED_E,
            ((patch("vv4_super_secret_golden_mushroom") + ": 1 in 1,000,000 of the random mushrooms is a Golden "
              "Mushroom worth 100 food (Mushrooms).", VERIFIED_E),
             (patch("vv4_everyone_collects_like_vv1") + ": several children dropped on one mushroom or collectible "
              "each collect it, so it is multiplied.", UNCONFIRMED))),
        Entry(ITEM, "The Fish Scale collection", (
            "a set of 12 pieces; each raises the Golden Fish chance by 2 points (Fishing Nets). Fish-scale spots count only in "
            "every other real-life hour."), VERIFIED_E),
        Entry(ITEM, "The Lab Equipment collection", (
            "a set of 12 pieces; each research session pays 0 to (pieces found - 1) more tech points, each equally likely."),
            VERIFIED_E),
        Entry(ITEM, "The Mausoleum Mural collection", (
            "a set of 12 pieces; once complete, a ghost brings a collectible every 50 to 58 real-life minutes (nothing if "
            "more than an hour overdue)."), VERIFIED_E),
        Entry(ITEM, "The Wind Flute collection", (
            "a set of 12 pieces; in fog the appearance roll's chance is 4 in 6,000 for every 2 pieces found: none with 0 or 1, "
            "the normal chance with 2 or 3, up to 6 times it with all 12."), VERIFIED_E,
            (("Fog increases collectible spawning if you have Wind Flute pieces collected.", gm.OWNER),)),
        Entry(ITEM, "Collectibles", (
            "common 81.98%, uncommon 13.01%, rare 5.01%. A piece already owned pays 100, "
            "250 or 1,500 tech points by rarity. Each complete collection raises the population limit by 5, all four "
            "by 25."), VERIFIED_E),
        Entry(ITEM, "New clothes", (
            "a villager dropped on the finished Clothing Hut, with at least 5,000 tech points in store, gets new "
            "clothes; with fewer the game says \"Not enough tech points to make new clothes!\"."), VERIFIED_C,
            (("The game's question: \"Do you want to spend 5000 tech points to change this villager's clothes?\" -- "
              "the deduction itself was not traced.", UNCONFIRMED),)),
        Entry(ITEM, "A snack at the food bin", (
            "a villager below full health, with food in storage, eats 1 food and regains 1 health 50.05% of the "
            "time."), VERIFIED_E),
    ]
    return out


# ---------------------------------------------------------------------------
# The patcher's upgrades
# ---------------------------------------------------------------------------

def _patcher() -> list[Entry]:
    o, vw, st = patch(ORIGINS), patch(VILLAGE_WIDE), patch(STORY)
    cost = gm.feature_name(STORY_COST)
    rows = [
        ("Time Warp", f"{o}: {_tp(50_000)}: the village's clock moves on by 12 real-life hours on Fast or Normal and "
                      "10 on Slow, so the villagers live 12, 6 or 3 years on Fast, Normal or Slow at once (Time "
                      "away); refused while paused.", gm.CLAMP),
        ("Island Event", f"{o}: {_tp(30_000)}: the game's own island event chooser picks and runs an event a few "
                         "real-life seconds after the Tech screen closes; one at a time. Its awards are never "
                         "doubled, and it does not move when the game's own next island event comes.", UNCONFIRMED),
        ("Barrel of Babies", f"{o}: {_tp(75_000)}: the game's barrel island event brings up to 3 children, a few "
                             "real-life seconds after the Tech screen closes; refused, with nothing taken, while the "
                             "village has no room for them (an unburied villager still takes a place).",
         UNCONFIRMED),
        ("Tech Point Doubler", f"{o}: {_tp(500_000)}, owned by this save and removable: every positive tech-point gain "
                               "the villagers earn is doubled; island events and duplicate collectibles are not.",
         UNCONFIRMED),
        ("Food Point Doubler", f"{o}: {_tp(500_000)}, owned by this save and removable: every positive food gain is "
                               "doubled after Food Mastery; island events and duplicate collectibles are not.",
         UNCONFIRMED),
        ("Full Heal / Cure All", f"{o}: {_tp(30_000)}: every sick villager is cured and every villager is restored "
                                 "to full health; nothing is taken when everyone is already healthy.", UNCONFIRMED),
        ("Complete All Collections", f"{vw}: {_tp(1_000_000)}: every collection piece is marked found; nothing is "
                                     "taken when every piece is already found.", UNCONFIRMED),
        ("Reset All Collections", f"{vw}: {_tp(1_000_000)}: every collection piece is marked not found; nothing is "
                                  "taken when none is found.", UNCONFIRMED),
        ("Equal Division of Labor (Includes Parenting / No Parenting)",
         f"{vw}: {_tp(1_000_000)} each: the villagers' job checkmarks are spread evenly over the jobs, men and women "
         "balanced in each; the No Parenting one leaves Parenting out.", UNCONFIRMED),
        ("Clear All Skill Preferences", f"{o}: {_tp(500_000)}: every villager's job checkmark is cleared, so each "
                                        "chooses their own work as in the stock game; skills are not changed.",
         UNCONFIRMED),
        ("Check Highest Skill (Includes Parenting / No Parenting)",
         f"{o}: {_tp(1_000_000)} each: each villager's job checkmark is set to the skill they have most progress in "
         "(ties: Farming, Building, Research, Healing, Parenting, in that order); the No Parenting one ignores "
         "Parenting; a villager with no progress yet keeps theirs.", UNCONFIRMED),
        ("All Villagers Like Running", f"{vw}: {_tp(1_000_000)}: every villager likes running (an adult who likes "
                                       "running walks at speed 300 instead of 150).", UNCONFIRMED),
        ("Grant Full Mastery to All Villagers", f"{vw}: {_tp(1_000_000)}: every villager's five skills become 100.",
         UNCONFIRMED),
        ("All Villagers are Exactly 18", f"{vw}: {_tp(1_000_000)}: every villager's age becomes exactly 18 (360 age "
                                         "units); nothing is taken when everyone already is.", UNCONFIRMED),
        ("Change Appearance for All", f"{o}: {_tp(450_000)}: one head, body and mask choice per sex, or a "
                                      "whole-village mask mode, applied to every villager.", UNCONFIRMED),
        ("Grant Youth", f"{o}: {_tp(50_000)} on the Villager Details screen: that villager is made 35 years "
                        "younger, never below 5 years.", UNCONFIRMED),
        ("Grant Full Mastery", f"{o}: {_tp(100_000)} on the Villager Details screen: that villager's five skills "
                               "become 100.", UNCONFIRMED),
        ("Grant Running", f"{o}: {_tp(40_000)} on the Villager Details screen: running goes into a free Like slot "
                          "and out of the Dislikes; refused, with nothing taken, without a free Like slot.",
         UNCONFIRMED),
        ("Set Age to 18", f"{o}: {_tp(50_000)} on the Villager Details screen: that villager is made 18.",
         UNCONFIRMED),
        ("Change Appearance", f"{o}: {_tp(5_000)} on the Villager Details screen: that villager's head, body and "
                              "Heathen mask are chosen from the game's own art.", UNCONFIRMED),
        ("Pick Island Event", f"{st}: 0 tech points ({_tp(30_000)} with \"{cost}\" ticked, as it is by default "
                              "with it): the player picks which stock island event comes, and how it turns out, from "
                              "the game's own list; it runs through the game's own island event code.", UNCONFIRMED),
        ("Custom Island Event", f"{st}: 0 tech points ({_tp(30_000)} with \"{cost}\" ticked): an island event the "
                                "player writes -- food, tech points, new villagers and what this game's own code can "
                                "change.", UNCONFIRMED),
        ("Choose Time Skip Amount", f"{st}: 0 tech points ({_tp(50_000)} with \"{cost}\" ticked): 1 to 72 villager "
                                    "years, as a run of Time Warps (12, 6 or 3 years each on Fast, Normal or Slow), "
                                    "each caught up by the game before the next.", UNCONFIRMED),
    ]
    free = (patch(STORY) + f": every Origins upgrade costs 0 tech points while \"{cost}\" is unticked; with it ticked "
            "(it is ticked with Story / Cheat Upgrades) the prices here stand.")
    out = [Entry(PATCHER, "Free Origins upgrades", free, UNCONFIRMED)]
    out += [Entry(PATCHER, name, text, ok) for name, text, ok in rows]
    out.append(Entry(PATCHER, "Difficulty Settings", (
        patch("vv4_difficulty_settings") + ": the Options dialog shows the Difficulty choice (Easy, Normal or Hard) "
        "that The Tree of Life already plays by; a village starts on Normal, and the choice is saved with the "
        "village."), UNCONFIRMED))
    return out


ENTRIES_BUILDERS = (_techs, _puzzles, _buildings, _items, _patcher)


def entries() -> list[Entry]:
    out: list[Entry] = []
    for build in ENTRIES_BUILDERS:
        out.extend(build())
    return out


def item_facts() -> list[gm.Fact]:
    """Every entry as the page's Facts: "<name>: <text>" under its kind's group, each further fact a sub-bullet."""
    facts: list[gm.Fact] = []
    for entry in entries():
        group = GROUP_OF[entry.kind]
        facts.append(gm.Fact(group, f"{entry.name}: {entry.text}", entry.verified))
        facts.extend(gm.Fact(group, text, ok, sub=True) for text, ok in entry.subs)
    return facts
