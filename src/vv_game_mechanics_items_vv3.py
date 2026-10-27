"""Game Mechanics: every technology, puzzle, building, item, potion and patcher upgrade of The Secret City (VV3).

The owner's rule for every Game Mechanics page (2026-10-27): "Elaborate on what every store item and upgrade and
research and everything does!!!"  item_facts() gives each player-facing thing its own entry, in the page's Fact
format (src/vv_game_mechanics.py): its cost or how it is earned, its exact effect with numbers, odds and timings, who
or what it acts on, and the stock value first, then the patched value.  A rule another group already gives in full
(the odds under Chances, the refills under Refills, the Ash Key under Hidden villager stats) is named here and pointed
to, not repeated.

LABELS (the owner's standing rule).  Each entry carries what stands behind it:
  VERIFIED_E (gm.RUNNING) -- emulated from a live caller, with exact odds;
  VERIFIED_C (gm.CODE)    -- traced on a live path in the stock executable (the addresses are beside each entry);
  gm.OWNER                -- the owner's own word from the game;
  UNCONFIRMED (False)     -- not yet proven: shown with the UNCONFIRMED label.

What was read for this module (2026-10-27, research/stock-executables, 831,488 bytes):
  * TECH PRICES: the Tech screen's price 0x427020(id) = dword [0x4A818C + 4 * (level + 1 + 3 * id)], read by the
    purchase 0x465640 (0x465700); a new village starts at Science, Medicine, Alchemy, Restoration and Leadership 1,
    Nature and Magic 0 (0x426F40), and a level stops at 3 (0x426FD0).  So the five ordinary technologies are never
    at level 0: nothing that only happens at level 0 is listed.
  * Tech levels go up only by the purchase (0x4657DB), the save loader (0x4270B5) and one island event
    (0x415D30, An Ancient Tablet); tech points are added only by research (0x459232..0x459435), duplicate
    collectibles (0x42DF79), the chief's call 0x458E09, island events (0x414F48..0x415AAB) and the purchase
    (0x4657D0): no puzzle pays tech points or a tech level.
  * RESTORATION (tech 3): every reader of 0x426FC0(3) is a drop handler registered through 0x4212A0
    (0x422A5E..0x422C64): region 6 0x421B00 (the Lift, < 2 Confused), region 22 0x4226D0 (the second hut, < 2),
    region 26 0x4228F0 (clearing rubble, < 2), region 23 0x422760 (the third hut, < 3), region 18 0x422220 (the
    statue's scaffolding, < 3), region 35 0x4214B0 (drawing plans, < 3 once puzzle 7 is solved), and the builders'
    offer 0x466B1C (< 3).  "Confused" is action 0x2C with the game's hint 0x14 (eTTipStandAloneConfused).
  * HUTS: hut i is project 21 + i (0x4321E0, table 0x49D0D0); its total is 2,000 (0x49D230); a new hut set starts
    hut 1 at 250 short, hut 2 at 1,600 short, huts 3 and 4 at 2,000 (0x4322F0 -> 0x4322C0, remainders 0x49D0E0).
  * NEW CLOTHES: the drop handler at 0x422892 opens the clothes only with project 24 (the fourth hut) finished and at
    least 5,000 tech points (0x4228A2: cmp [0x582644], 0x1388).
  * THE SHARKS: 0x436580 (a vial carrier reaching map region 42) advances puzzle 10 (0x4365B9), then effect 0x1B
    sends the sharks away (0x4365D5) and any other vial sparkles over them.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import vv_game_mechanics as gm
from vv_game_mechanics_chances import at_most, below, chance

GAME = 3
# The groups this module's facts go under (the coordinator wires them into gm.GROUPS).
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

# The seven technologies (0x426FC0 on 0x582618; the Tech screen's info strings eTech*Info), their next-level prices
# (0x4A818C: level 1, 2, 3; 0 = the level a new village already has) and the level a new village starts at.
TECHS = ("Science", "Medicine", "Alchemy", "Restoration", "Leadership", "Nature", "Magic")
TECH_PRICES = {"Science": (0, 11_000, 150_000), "Medicine": (0, 8_000, 75_000), "Alchemy": (0, 5_000, 55_000),
               "Restoration": (0, 7_000, 85_000), "Leadership": (0, 7_000, 125_000),
               "Nature": (4_500, 50_000, 150_000), "Magic": (4_500, 50_000, 150_000)}
START_LEVEL = {"Science": 1, "Medicine": 1, "Alchemy": 1, "Restoration": 1, "Leadership": 1, "Nature": 0,
               "Magic": 0}
# The puzzles' thresholds (0x49D230[0..15], as vv_game_mechanics_vv3.PUZZLE_THRESHOLDS) and the huts' (21..24).
HUT_PROJECTS = (21, 22, 23, 24)
HUT_TOTAL = 2_000
HUT_START_SHORT = (250, 1_600, 2_000, 2_000)
CLOTHES_PRICE = 5_000

# The patcher's defaults (src/vv_fun_patcher_gui.py DEFAULT_OFF_FUN_PATCH_IDS / ALTERNATIVE_OFF_FUN_PATCH_IDS, for
# this game): every other patch is ticked by default.  tests/test_game_mechanics_items_vv3.py checks this mirror.
DEFAULT_OFF = frozenset({"vv3_learning_never_fails", "vv3_everyone_collects_like_vv1",
                         "vv3_super_secret_golden_mushroom", "vv3_manual_drop_breeding_overrides_birth_control",
                         "vv3_story_cheat_upgrades", "vv3_story_cheat_upgrades_cost_tech_points",
                         "vv3_population_256", "vv3_fruit_trees_take_turns"})

ORIGINS = "vv3_enable_origins_exclusive_features"
VILLAGE_WIDE = "vv3_origins_village_wide_upgrades"
STORY = "vv3_story_cheat_upgrades"
STORY_COST = "vv3_story_cheat_upgrades_cost_tech_points"


@dataclass(frozen=True)
class Entry:
    """One player-facing thing: its kind, its name as the game (or the patcher) shows it, what it costs and does,
    what stands behind that, and any further facts (each with its own label), shown as sub-bullets."""
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

def _level(name: str, level: int, text: str, verified: bool | str = VERIFIED_C,
           subs: tuple[tuple[str, bool | str], ...] = ()) -> Entry:
    """One technology level's entry: its price (or that a new village has it), then what it gives."""
    price = TECH_PRICES[name][level - 1]
    head = "a new village's level, no price" if level <= START_LEVEL[name] else _tp(price)
    return Entry(TECH, f"{name} level {level}", f"{head}. {text}", verified, subs)


def _techs() -> list[Entry]:
    blow = {lvl: chance(at_most(100, 15 * (3 - lvl))) for lvl in (1, 2, 3)}
    sup = {lvl: _ch(25 * lvl) for lvl in (1, 2, 3)}
    research = ("Each successful research session pays the researcher's Research skill ÷ {d}, rounded down, then "
                "scaled by the game speed (the exact rounding: Tech points and effects) -- nothing from the skill "
                "below Research {d}; while the game catches up time away ÷ {c} at every speed. The shorter research "
                "walk (a 7 to 11 wait, not 10 to 19) is taken {p}% of the time; both end in the same skill test and "
                "payout.")
    sick = ("Falling sick, rolled each age unit (3, 6 or 10 real-life minutes on Fast, Normal or Slow) for each "
            "healthy villager: {odds}, where m is 1 while the campfire burns or Aromatherapy is solved and 2 otherwise "
            "(Chances, Falling sick). A villager is elderly from {old} years (a further 1.5% chance of falling sick each "
            "age unit, and health coming back only 20% as often); the old-age death rolls start at {death} years. "
            "Conception at Parenting P: (P + {p}) in 300 (Births and gender).")
    confused = ("the villager is \"Confused\" and the game shows its tip that villagers sometimes need more "
                "advanced technology")
    supervise = ("The Tribal Chief's supervision pays when a roll of 0 to 99 is under 25 x Leadership: {s} of the "
                 "time -- a third more fish and fruit, half as much honey again, 1 more build unit, a quarter more "
                 "research (Chances, The Tribal Chief's supervision). Grant Food gives {food} food.")
    return [
        Entry(TECH, "The Tech screen", (
            "each technology is bought one level at a time with tech points on the Tech screen; the price of the next "
            "level is taken at once and the level goes up at once. Science, Medicine, Alchemy, Restoration and "
            "Leadership start at level 1 in every new village and go to 3; Nature and Magic (the two factions) start "
            "at 0. Without enough tech points the game says \"You don't have enough tech points!\" and nothing is "
            "taken. Each level below is what that level gives."), VERIFIED_C),
        # Science (0): the research payout 0x459196 (vv_game_mechanics_vv3, Tech points and effects); the walk 0x44867A.
        _level("Science", 1, research.format(d=11, c=7, p=85)),
        _level("Science", 2, research.format(d=9, c=7, p=70)),
        _level("Science", 3, research.format(d=7, c=5, p=55)),
        # Medicine (1): sickness 0x455C00, old age 0x4602C1, conception 0x4586E1, twins 0x455B77, study 0x45B69E.
        _level("Medicine", 1, sick.format(odds="(3m + 1) in 1,440", old=50, death=55, p=1) + " A healer with "
               "nobody sick to cure does nothing."),
        _level("Medicine", 2, sick.format(odds="(3m + 1) in 2,460", old=58, death=63, p=51) + " A healer with "
               "nobody sick to cure studies medicine (\"Studying medicine\", Healing practice), and a healer dropped "
               "on the medical area keeps going back to it with Healing 6 or more."),
        _level("Medicine", 3, sick.format(odds="(2m + 1) in 5,400", old=66, death=71, p=101) + " Twins and "
               "triplets become possible: a pregnancy is multiple " + _ch(7) + " of the time, a quarter of those "
               "triplets (Births and gender); and a fed, healthy villager's health always passes the check for "
               "coming back."),
        # Alchemy (2): the brew's blow-up 0x430A81..0x430A92.
        _level("Alchemy", 1, f"A brew in the Alchemy Lab blows up {blow[1]} of the time (a roll of 0 to 99 at or "
                             "under 15 x (3 - Alchemy) = 30), costing the villager tending the pot 30 to 69 health, "
                             "each equally likely (Chances, Brewing a potion).", VERIFIED_E),
        _level("Alchemy", 2, f"A brew blows up {blow[2]} of the time (at or under 15); nothing else about a potion "
                             "changes.", VERIFIED_E),
        _level("Alchemy", 3, f"A brew blows up {blow[3]} of the time (only a roll of 0).", VERIFIED_E),
        _level("Restoration", 1, "A villager dropped on the Lift, the second hut, the rubble, the third hut or the "
                                 f"statue's scaffolding does not work there: {confused}."),
        _level("Restoration", 2, "Villagers dropped there repair the Lift (The Lift), build the second hut and clear "
                                 "the rubble."),
        _level("Restoration", 3, "Villagers dropped there build the third hut and the statue's scaffolding (The "
                                 "Statue), and draw plans once The Ancient Bath is solved; builders also take on the "
                                 "scaffolding by themselves."),
        # Leadership (4): supervision 0x45FC60, grant food 0x459042, powers' 23 hours 0x421A9D / 0x421C62 / 0x466895.
        _level("Leadership", 1, supervise.format(s=sup[1], food="30 to 87") + " Leadership works only through the "
               "Tribal Chief (The First Chief); each power then waits 23 real-life hours at any speed, paused or "
               "closed."),
        _level("Leadership", 2, supervise.format(s=sup[2], food="60 to 174") + " The chief can Educate the "
               "Children (Technologies, items and buildings)."),
        _level("Leadership", 3, supervise.format(s=sup[3], food="90 to 261") + " The chief can Point Out a Rare "
               "Collectible (Technologies, items and buildings)."),
        # Nature (5): 0x4347C3 (fruit factor), 0x420BB9 (the Pitcher Plant art), 0x4601C4 (read, not used).
        _level("Nature", 1, (
            "The Faction of Nature (Choosing a faction). A fruit tree's refill counts 42 fruit instead of 37 per "
            "real-life hour on Normal speed (per 30 minutes on Fast, per 1 hour 40 minutes on Slow) -- 126 fruit every "
            "3 real-life hours on Normal speed (1 hour 30 minutes on Fast, 5 hours on Slow) instead of 111; the honey "
            "is not changed."), VERIFIED_C,
            ((patch("vv3_nature_honey_refill") + ": the fruit trees refill every 2 hours 15 minutes of real-life play "
              "on Normal speed with 56 fruit per real-life hour on Normal speed (the same 126 fruit a refill), and the "
              "honey every 45 minutes instead of every hour (on Normal speed), gaining 84 for every 27 hours 45 "
              "minutes of real-life play on Normal speed (3.03 per real-life hour on Normal speed) instead of 2 per "
              "real-life hour (Refills).", VERIFIED_E),)),
        _level("Nature", 2, "The Pitcher Plant grows by the Alchemy Lab, a herb for potions (Technologies, items and "
                            "buildings)."),
        _level("Nature", 3, (
            "Nothing: the game says it increases longevity, but the aging code reads the Nature level and throws it "
            "away."), VERIFIED_C,
            ((patch("vv3_nature_level_three_alters_mortality") + ": every old-age death roll starts 7 years later "
              "(62, 70 or 78 years at Medicine 1, 2 or 3).", UNCONFIRMED),)),
        # Magic (6): 0x4593DC (+1 research), 0x420BDD (the Berry Plant art), 0x45FE9D (+10 population).
        _level("Magic", 1, "The Faction of Magic (Choosing a faction). Each successful research session pays 1 more "
                           "tech point."),
        _level("Magic", 2, "The Berry Plant grows by the Alchemy Lab, a herb for potions (Technologies, items and "
                           "buildings)."),
        _level("Magic", 3, "The population limit is 10 higher: 90 + 5 for each complete collection (25 for all "
                           "four) + 10, so 125 at most in the stock game."),
        Entry(TECH, "Choosing a faction", (
            "Nature and Magic are the two factions: buying level 1 of either asks \"Are you sure? Once you choose a "
            "faction for your tribe, you cannot change it.\", and once one is above 0 clicking the other only says "
            "\"You have already chosen your faction!\" -- a stock village has one faction for good."), VERIFIED_C,
            ((patch("vv3_both_factions") + ": the second faction can be bought too, at its normal price; buying "
              "level 1 of either asks \"With the power of the Fun Patcher, you can now embrace both Nature and Magic "
              "Factions. Use this gift wisely.\", and every level of both works at once. The save keeps the first "
              "faction; the second is kept in the patcher's per-save file (Virtual Villagers 3 Second Faction - Save "
              "<slot>.dat).", VERIFIED_E),)),
    ]


# ---------------------------------------------------------------------------
# Puzzles
# ---------------------------------------------------------------------------

def _puzzles() -> list[Entry]:
    no_pay = ("Solving any puzzle pays no tech points, no food and no tech level by itself: the game stamps the "
              "solve time on the Puzzles screen and runs that puzzle's own completion -- its tip and what it "
              "unlocks, below.")
    return [
        Entry(PUZZLE, "Puzzles in general", no_pay, VERIFIED_C),
        Entry(PUZZLE, "The First Chief", (
            "solved in 1 step, when a villager trying on the robe becomes the Tribal Chief. The chief never takes a job; "
            "dropped on work the chief directs it, with the Leadership supervision bonus (Technologies, "
            "Leadership), and has the once-a-day powers."), VERIFIED_C,
            (("Only one villager, chosen when the village is made and not shown to the player, fits the robe.", UNCONFIRMED),
             (patch("vv3_everyone_tries_on_robe") + ": dropping a villager on the robe sends every active, living "
              "villager who is not nursing to try it on too, so the one it fits is found at once; the game alone "
              "still decides who becomes chief.", UNCONFIRMED))),
        Entry(PUZZLE, "The Bee Hive", (
            "solved in 1 step. Solved, farmers can gather honey while the hive holds more than 10: a pick brings 7, "
            "3 or 2 food on Fast, Normal or Slow (4 while catching up), and the hive refills 2 honey per real-life "
            "hour on Normal speed (per 30 minutes on Fast, per 1 hour 40 minutes on Slow) up to 3,000 (Refills). Unsolved, honey is never offered."), VERIFIED_C),
        Entry(PUZZLE, "The Alchemy Lab", (
            "solved after 5 steps (the lab's scattered pieces). Solved, villagers can gather the herbs and brew "
            "potions (Technologies, items and buildings); before it no herb can be gathered."), VERIFIED_C),
        Entry(PUZZLE, "The Roster of the Dead", (
            "solved after 700 steps; what counts a step was not traced here."), UNCONFIRMED),
        Entry(PUZZLE, "Weather Dancing", (
            "solved in 1 step; the step is the Tribal Chief's \"Doing a weather dance\"."), UNCONFIRMED),
        Entry(PUZZLE, "The Lift", (
            "solved in 1 step: a villager \"Repairing the lift\", which needs Restoration level 2 (below it the "
            "villager is Confused)."), VERIFIED_C,
            (("The game's tip: the lift lets the villagers reach the tree high above on the cliff.", UNCONFIRMED),)),
        Entry(PUZZLE, "The Ruins", (
            "solved after 1,800 steps. Once it is at least 2% done the Tablet collection starts to appear among "
            "the collectibles (Collectibles)."), VERIFIED_C),
        Entry(PUZZLE, "The Ancient Bath", (
            "solved after 1,400 steps (\"Repairing the bath\"); a builder who dislikes rocks or lifting runs away "
            "from it 60% of the time. Solved, drawing plans at the statue needs Restoration level 3."), VERIFIED_C),
        Entry(PUZZLE, "The Statue", (
            "solved after 2 steps (\"Building scaffolding\", \"Pushing statue\"). The scaffolding needs Restoration "
            "level 3, a builder with Building 20 or more, and the Tribal Chief standing at the scaffolding spot for a "
            "builder to take it on alone; drawing plans needs Building 88 or more."), VERIFIED_C),
        Entry(PUZZLE, "The Orchard", (
            "solved in 1 step, while all three fruit trees are grown (unsolved again, the game solves it again at "
            "once). A tree can be picked 8 real-life hours after it is planted on Normal speed (4 on Fast, 13 "
            "hours 20 minutes on Slow); each tree's fruit and refill are under Food sources and Refills."),
            VERIFIED_C),
        Entry(PUZZLE, "The Sharks", (
            "solved in 1 step: a villager carrying either shark vial (Technologies, items and buildings) to the Diving Rock. "
            "Solved, fishing is offered: a catch brings 11, 8 or 5 food on Fast, Normal or Slow (8 while catching "
            "up), a crab worth 55 for a fisher with Farming 88 or more (Chances, The crab). The vial of Black "
            "Orchid x2 and Pitcher Plant sends the sharks away; the other vial only sparkles over them."),
            VERIFIED_C),
        Entry(PUZZLE, "Aromatherapy", (
            "solved after 6 steps (\"Lighting burners\", \"Doing aromatherapy\"). Solved, it lowers the chance of "
            "falling sick as a burning campfire does (Technologies, Medicine: m is 1)."), VERIFIED_C),
        Entry(PUZZLE, "The Ash Key", (
            "solved in 1 step: with the campfire's 61 hours of burning (on Normal speed) and 12 trips of water done, "
            "a villager dropped on the key's spot finds it (the whole rule and this village's count: Hidden villager "
            "stats)."), VERIFIED_E),
        Entry(PUZZLE, "The Cliff Key", "solved in 1 step (\"Trying to reach the key\").", UNCONFIRMED),
        Entry(PUZZLE, "The Clam Key", "solved in 1 step.", UNCONFIRMED),
        Entry(PUZZLE, "The Chief and the Princess", "solved in 1 step.", UNCONFIRMED),
    ]


# ---------------------------------------------------------------------------
# Buildings and repairs
# ---------------------------------------------------------------------------

def _buildings() -> list[Entry]:
    return [
        Entry(BUILDING, "Building in general", (
            "each hut needs 2,000 build units; each successful \"Building small hut\" step adds 1 (a failed Building "
            "skill test adds nothing), and a supervising Tribal Chief adds 1 more 25 x Leadership % of the time. "
            "Builders take on a hut or project by themselves only once it is at least 2% done, so the first push on "
            "a new one is a villager you drop there."), VERIFIED_C,
            (("While the game catches up time away a hut gets work only from a builder already standing in it.",
              VERIFIED_C),)),
        Entry(BUILDING, "The first hut", (
            "starts 250 build units short of its 2,000 in a new village. Room for babies: with 10 or more villagers "
            "(babies on the way included) no pregnancy starts without 1 finished hut, from 17 without 2, from 35 "
            "without 3."), VERIFIED_C),
        Entry(BUILDING, "The second hut", (
            "starts 1,600 build units short; a villager dropped on it builds only at Restoration level 2 or more. It "
            "counts toward the room for babies (The first hut)."), VERIFIED_C),
        Entry(BUILDING, "The third hut", (
            "starts at 0 of 2,000 build units; a villager dropped on it builds only at Restoration level 3. It counts "
            "toward the room for babies."), VERIFIED_C),
        Entry(BUILDING, "The fourth hut", (
            "starts at 0 of 2,000 build units. It never counts toward the room for babies; finished, it is where "
            "villagers get new clothes (Technologies, items and buildings)."), VERIFIED_C),
        Entry(BUILDING, "Fixing huts", (
            "only once all four huts are finished: a builder examining a hut goes on to \"Fixing hut\" "
            + _ch(70) + " of the time. Fixing trains Building and changes nothing on the hut: huts never wear "
            "out."), VERIFIED_C,
            ((patch("vv3_builders_fix_huts") + ": builders build first and fix huts when no building project can be "
              "worked on; it steps in on about three builder choices in four (14% for a villager whose job "
              "checkmark is not Building).", UNCONFIRMED),)),
        # The fire 0x5946D8: 72,000 game seconds (0x433A33), refuelled 0x433AF5.
        Entry(BUILDING, "The campfire", (
            "lit, it burns 20 hours of the game's clock -- 10, 20 or 33 hours 20 minutes of real-life play on Fast, "
            "Normal or Slow -- and stops counting while paused; wood on a burning fire starts the 20 hours over. "
            "While it burns: research pays 1 more tech point " + _ch(10) + " of sessions, villagers fall sick less "
            "often (Technologies, Medicine) and health comes back more often (Chances, Regaining health)."),
            VERIFIED_C,
            (("It goes out when its timer runs out; rain and the weather do not affect it. Four trips of water for "
              "the Ash Key put a lit fire out.", gm.OWNER),)),
        Entry(BUILDING, "The medical area", (
            "a healer dropped there keeps going back only with Healing 6 or more and Medicine level 2 or more; with "
            "nobody sick, healers study medicine there from Medicine level 2."), VERIFIED_C,
            ((patch("vv3_chief_hospital_supervision") + ": the Tribal Chief dropped there directs the work: a healer "
              "studying medicine gains twice the skill, and a cure whose skill test fails goes ahead when the "
              "chief's supervision roll passes (25 x Leadership % of the time).", UNCONFIRMED),)),
    ]


# ---------------------------------------------------------------------------
# Items, herbs and potions
# ---------------------------------------------------------------------------

def _potion_name(product: int) -> str:
    import vv_game_mechanics_counts as counts
    """"Potion <the game's effect number> ("<what the drinker says>")": the game names a potion by nothing else, and
    three sayings are shared by two potions each."""
    say = counts.VV3_POTIONS[product][0].replace("{He/She}", "He or she")
    return f"Potion {product} (\"{say}\")" if not say.startswith("(") else f"Potion {product} (nothing is said)"


# The effect switch 0x4268F0 (vv_game_mechanics_counts.VV3_POTIONS), with what a closer trace changed: product 40 calls
# the village 0x45E0C0 -> 0x45DDE0 with flag 1, which picks only free children under 14 (age < 0x118, [+0xF20] == -1),
# not every villager (docs/vv3-both-factions.md); 26 and 27 are the shark vials (0x436580).
POTION_FIXES = {
    26: "\"Carrying vial to ocean\"; kept with no time limit. At the Diving Rock it solves The Sharks, and the sharks "
        "are charmed: they sparkle and stay",
    27: "\"Carrying vial to ocean\"; kept with no time limit. At the Diving Rock it solves The Sharks and the sharks "
        "leave",
    40: "every living child under 14 who is not already holding or heading for something goes \"Something smells "
        "YUMMY!\" and walks to the pot; adults never go",
}


def _potions() -> list[Entry]:
    import vv_game_mechanics_counts as counts
    recipes: dict[int, list[str]] = defaultdict(list)
    for a, b, c, product in counts.VV3_COMBOS:
        recipes[product].append(" + ".join(counts.VV3_HERBS[h] for h in (a, b, c)))
    out = []
    for product in sorted(recipes):
        does = POTION_FIXES.get(product, counts.VV3_POTIONS[product][1])
        found = "; ".join(recipes[product])
        out.append(Entry(ITEM, _potion_name(product), (
            f"brewed from {found} ({len(recipes[product])} recipe{'s' if len(recipes[product]) > 1 else ''}). "
            f"The villager dropped on the pot drinks it: {does}."), VERIFIED_C))
    return out


def _items() -> list[Entry]:
    herbs = ("Tiger Lily", "Cactus", "Lotus", "Black Orchid", "Rose")
    out = [
        Entry(ITEM, "The herbs", (
            f"{', '.join(herbs)} grow by the Alchemy Lab from the start; the Pitcher Plant only at Nature level 2 or "
            "more, the Berry Plant only at Magic level 2 or more. A villager dropped on a herb gathers it "
            "(\"Gathering herbs\") once The Alchemy Lab is solved, while the pot holds fewer than 3 herbs. Gathering "
            "reads no technology."), VERIFIED_C,
            (("Herbs never run out: a bush can be gathered without limit once the Alchemy Lab is restored.",
              gm.OWNER),
             ("A villager who dislikes herbs refuses to gather them.", VERIFIED_C))),
        Entry(ITEM, "Brewing a potion", (
            "any 3 herbs in the pot, in any order, make one potion: the 77 herb combinations each give one of the "
            "potions below. The brew blows up " + chance(at_most(100, 30)) + ", " + chance(at_most(100, 15))
            + " or " + chance(at_most(100, 0)) + " of the time at Alchemy 1, 2 or 3 (Technologies, Alchemy), costing "
            "the villager tending it 30 to 69 health."), VERIFIED_E,
            (("The game spoils a brewed potion 5 real-life minutes after it is brewed, the same at every speed: its "
              "deadline is the computer's clock + 300 seconds (0x430E60, checked by the pot's update 0x430F10). The pot's "
              "on-screen countdown shows that time on the game's clock -- it starts at 5:00, 2:30 or 8:20 on Normal, Fast "
              "or Slow (Tech points and effects) -- and reaches 0:00 when the potion spoils. The save does not keep the "
              "pot.", VERIFIED_C),
             ("The owner sees a brewed potion's time follow the game speed (the countdown shown changes with it).",
              gm.OWNER),
             ("The pot can be emptied by dropping a villager on the table with 3 herbs: the brewed potion is thrown "
              "away and the herbs stay on the table.", gm.OWNER))),
        Entry(ITEM, "Drinking a potion", (
            "drop a villager on the pot with a potion ready. A villager cannot drink a potion whose effect they "
            "already have, or any potion while they already have 4 effects; the game then says \"That villager "
            "can't drink another potion so soon.\" Effects last 10 or 5 real-life minutes at every speed (as each "
            "potion says), and saving the game ends every villager's effects."), VERIFIED_E,
            (("A villager cannot drink a potion whose effect they already have, nor any potion with 4 effects.",
              gm.OWNER),)),
        Entry(ITEM, "The recipe book", (
            "the first time a combination is brewed without blowing up, the game marks it in the Alchemy Lab's "
            "book (\"Your villagers found an interesting new recipe!\"), kept in the save: the count is under "
            "Village counts. With 50 combinations found the game gives the achievement \"Alchemy R Us\"."),
            VERIFIED_C),
    ]
    out += _potions()
    sup = _ch(25)
    out += [
        Entry(ITEM, "Fruit", (
            "picking brings 7, 3 or 2 food on Fast, Normal or Slow (4 while catching up), a third more when the "
            f"supervising chief's roll passes ({sup} at Leadership 1); a tree holds up to 1,000 fruit and is picked "
            "only with 10 or more (Food sources, Refills)."), VERIFIED_C,
            ((patch("vv3_fruit_harvested_at_food_bin") + ": the fruit leaves the tree, and the food is added, only "
              "when the villager puts it in the food bin.", UNCONFIRMED),
             (patch("vv3_fruit_trees_refill_together") + ": every tree refills when the first one is due; over time "
              "each gives the same fruit as in the stock game.", UNCONFIRMED),
             (patch("vv3_fruit_trees_take_turns") + ": the trees refill one after another, evenly spread over the "
              "refill time (one every hour of real-life play on Normal speed with three trees at the stock 3-hour refill; "
              "on the game's clock: 30 minutes on Fast, 1 hour 40 minutes on Slow).", UNCONFIRMED))),
        Entry(ITEM, "Honey", (
            "after The Bee Hive: a pick brings 7, 3 or 2 food on Fast, Normal or Slow (4 while catching up), half "
            "as much again when the supervising chief's roll passes; the hive gives honey only while it holds 10 "
            "or more."), VERIFIED_C),
        Entry(ITEM, "Fish and the crab", (
            "after The Sharks: a catch brings 11, 8 or 5 food on Fast, Normal or Slow (8 while catching up); a "
            "fisher with Farming 88 or more lands a crab worth 55 food instead " + _ch(10) + " of the time."),
            VERIFIED_C),
        Entry(ITEM, "Mushrooms", (
            "a brown mushroom is worth 6 food, a red (rare) one 35, counted when it reaches "
            "the food bin; how often they appear is under Mushrooms."), VERIFIED_E,
            ((patch("vv3_super_secret_golden_mushroom") + ": 1 in 1,000,000 of the random mushrooms is a Golden "
              "Mushroom worth 100 food (Mushrooms).", VERIFIED_E),
             (patch("vv3_everyone_collects_like_vv1") + ": several children dropped on one mushroom or collectible "
              "each collect it, so it is multiplied.", UNCONFIRMED))),
        Entry(ITEM, "Collectibles", (
            "four collections, the Tablet only once The Ruins is at least 2% done. A piece "
            "already owned pays 100, 250 or 1,500 tech points (common, uncommon, rare) instead; Tablet pieces "
            "already owned never appear again. Each complete collection raises the population limit by 5, all four "
            "by 25."), VERIFIED_C),
        Entry(ITEM, "Grant Food (the chief's power)", (
            "from Leadership level 1, once every 23 real-life hours (real time, at any speed): 3 x Leadership x (10 to 29, each equally "
            "likely) food -- 30 to 87 at level 1, 60 to 174 at level 2, 90 to 261 at level 3."), VERIFIED_C),
        Entry(ITEM, "Educate the Children (the chief's power)", (
            "once every 23 real-life hours (real time, at any speed): each child who finishes the lesson gains 7 to 9 points in one random "
            "skill, up to 100."), VERIFIED_C,
            (("It needs Leadership level 2 (the game's Leadership text says so).", UNCONFIRMED),
             (patch("vv3_chief_lessons_cap_50") + ": only a skill below 50 can be chosen and the gain stops at 50; "
              "with every skill at 50 the lesson gives nothing.", UNCONFIRMED))),
        Entry(ITEM, "Point Out a Rare Collectible (the chief's power)", (
            "from Leadership level 3, with the chief placed at the top of the path, once every 23 real-life hours "
            "(real time, at any speed): "
            "a rare piece from a collection chosen at random appears; the call is spent for nothing when the game "
            "picks an owned Tablet piece or a piece already out (Chances, The Tribal Chief's rare collectible)."),
            VERIFIED_C,
            ((patch("vv3_rare_collectible_retry") + ": a refused pick is made again, up to 20 times, so a piece "
              "almost always appears.", VERIFIED_E),)),
        Entry(ITEM, "New clothes", (
            "a villager dropped on the fourth hut once it is finished, with at least 5,000 tech points in store, "
            "opens the clothes; with fewer the game says \"Not enough tech points to make new clothes!\"."),
            VERIFIED_C,
            (("The game's question: \"Do you want to spend 5000 tech points to change this villager's clothes?\" -- "
              "the deduction itself was not traced.", UNCONFIRMED),)),
        Entry(ITEM, "Wood for the campfire", (
            "a villager dropped on the burning campfire with wood starts its 20 hours of the game's clock over: 10, 20 or 33 hours 20 minutes of "
            "real-life play on Fast, Normal or Slow (The campfire)."),
            VERIFIED_C),
        Entry(ITEM, "Water for the Ash Key", (
            "after the campfire's 61 hours of burning (on the game's clock: 30 hours 30 minutes on Fast, 61 hours on "
            "Normal or 101 hours 40 minutes on Slow of real-life play), 12 trips of water; the 4th puts a lit fire out, "
            "and while it burns 10 minutes between trips starts the count again (also on the game's clock: 5, 10 or 16 "
            "minutes 40 seconds of real-life play on Fast, Normal or Slow, 0x433BCA -> 0x426790) (Hidden villager "
            "stats)."), VERIFIED_E),
        Entry(ITEM, "A snack at the food bin", (
            "a villager below 100 health eats 1 food and regains 1 health " + _ch(50) + " of the time (Chances)."),
            VERIFIED_C),
    ]
    return out


# ---------------------------------------------------------------------------
# The patcher's upgrades
# ---------------------------------------------------------------------------

# The Origins payload's price tables (scripts/build_vv3_origins_feature.py "tech_costs" / "detail_costs") and the
# companion's 1,000,000 checks (Collections, Equal Division, Check Highest Skill, the village-wide rows).
ORIGINS_PRICES = {"Time Warp": 50_000, "Island Event": 30_000, "Barrel of Babies": 75_000,
                  "Tech Point Doubler": 500_000, "Food Point Doubler": 500_000,
                  "Grant Youth": 50_000, "Grant Full Mastery": 100_000, "Grant Running": 40_000,
                  "Set Age to 18": 50_000, "Change Appearance": 5_000}


def _patcher() -> list[Entry]:
    o, vw, st = patch(ORIGINS), patch(VILLAGE_WIDE), patch(STORY)
    free = (patch(STORY) + ": every Origins upgrade costs 0 tech points while \"" + gm.feature_name(STORY_COST)
            + "\" is unticked; with it ticked (it is ticked with Story / Cheat Upgrades) the prices here stand.")
    rows = [
        ("Time Warp", f"{o}: {_tp(50_000)} on the Tech screen's Origins upgrades. The village's clock moves on by 12 "
                      "real-life hours on Fast or Normal and 10 on Slow, so the villagers live 12, 6 or 3 years on "
                      "Fast, Normal or Slow at once (Time away); refused while paused.", gm.CLAMP),
        ("Island Event", f"{o}: {_tp(30_000)}: the game's own island event chooser picks and runs an event a few "
                         "real-life seconds after the Tech screen closes; one at a time. Its awards are never "
                         "doubled, and it does not move when the game's own next island event comes.", UNCONFIRMED),
        ("Barrel of Babies", f"{o}: {_tp(75_000)}: the game's own barrel island event, \"Another One of Those "
                             "Barrels\": 3 children of 10 years, each a boy or a girl half the time, with one skill "
                             "at 5 to 9; refused, with nothing taken, without room for all three.", UNCONFIRMED),
        ("Tech Point Doubler", f"{o}: {_tp(500_000)}, owned by this save and removable: every positive tech-point gain "
                               "the villagers earn is doubled; island events and duplicate collectibles are not.",
         UNCONFIRMED),
        ("Food Point Doubler", f"{o}: {_tp(500_000)}, owned by this save and removable: every positive food gain is "
                               "doubled; island events and duplicate collectibles are not.", UNCONFIRMED),
        ("Complete All Collections", f"{vw}: {_tp(1_000_000)}: every collection piece is marked found (each complete "
                                     "collection raises the population limit by 5, all four by 25); nothing is "
                                     "taken when every piece is already found.", UNCONFIRMED),
        ("Reset All Collections", f"{vw}: {_tp(1_000_000)}: every collection piece is marked not found; nothing is "
                                  "taken when none is found.", UNCONFIRMED),
        ("Equal Division of Labor (Includes Parenting / No Parenting)",
         f"{vw}: {_tp(1_000_000)} each: the villagers' job checkmarks are spread evenly over the jobs, men and women "
         "balanced in each, each villager given the job they are best at among those left; the No Parenting one "
         "leaves Parenting out. The Tribal Chief is skipped.", UNCONFIRMED),
        ("Clear All Skill Preferences", f"{o}: {_tp(500_000)}: every villager's job checkmark is cleared, so each "
                                        "chooses their own work as in the stock game; skills are not changed; the "
                                        "Tribal Chief is skipped.", UNCONFIRMED),
        ("Check Highest Skill (Includes Parenting / No Parenting)",
         f"{o}: {_tp(1_000_000)} each: each villager's job checkmark is set to the skill they have most progress in "
         "(ties: Farming, Building, Research, Healing, Parenting, in that order); the No Parenting one ignores "
         "Parenting; a villager with no progress yet keeps theirs; the Tribal Chief is skipped.", UNCONFIRMED),
        ("All Villagers Like Running", f"{vw}: {_tp(1_000_000)}: every villager likes running (an adult who likes "
                                       "running walks at speed 300 instead of 100).", UNCONFIRMED),
        ("Grant Full Mastery to All Villagers", f"{vw}: {_tp(1_000_000)}: every villager's five skills become 100.",
         UNCONFIRMED),
        ("Make Villagers Young Adults", f"{vw}: {_tp(1_000_000)}: every villager is made 18.", UNCONFIRMED),
        ("Grant Youth", f"{o}: {_tp(50_000)} on the Villager Details screen: that villager is made 35 years "
                        "younger, never below 5 years.", UNCONFIRMED),
        ("Grant Full Mastery", f"{o}: {_tp(100_000)} on the Villager Details screen: that villager's five skills "
                               "become 100.", UNCONFIRMED),
        ("Grant Running", f"{o}: {_tp(40_000)} on the Villager Details screen: running goes into a free Like slot "
                          "and out of the Dislikes; refused, with nothing taken, without a free Like slot.",
         UNCONFIRMED),
        ("Set Age to 18", f"{o}: {_tp(50_000)} on the Villager Details screen: that villager is made 18.",
         UNCONFIRMED),
        ("Change Appearance", f"{o}: {_tp(5_000)} on the Villager Details screen: that villager's head and body "
                              "are chosen from the game's own art.", UNCONFIRMED),
        ("Pick Island Event", f"{st}: 0 tech points ({_tp(30_000)} with \"{gm.feature_name(STORY_COST)}\" ticked, "
                              "as it is by default with it): the player picks which stock island event comes, and "
                              "how it turns out, from the game's own list; it runs through the game's own island "
                              "event code.", UNCONFIRMED),
        ("Custom Island Event", f"{st}: 0 tech points ({_tp(30_000)} with \"{gm.feature_name(STORY_COST)}\" "
                                "ticked): an island event the player writes -- food, tech points, new villagers and "
                                "what this game's own code can change.", UNCONFIRMED),
        ("Choose Time Skip Amount", f"{st}: 0 tech points ({_tp(50_000)} with \"{gm.feature_name(STORY_COST)}\" "
                                    "ticked): 1 to 72 villager years, as a run of Time Warps (12, 6 or 3 years each "
                                    "on Fast, Normal or Slow), each caught up by the game before the next.",
         UNCONFIRMED),
        ("Recharge Chief Powers", f"{st}: 0 tech points ({_tp(30_000)} with \"{gm.feature_name(STORY_COST)}\" "
                                  "ticked): the Tribal Chief's once-a-day powers are ready at once; refused with "
                                  "nothing spent when there is no chief or every power is ready already.",
         UNCONFIRMED),
    ]
    out = [Entry(PATCHER, "Free Origins upgrades", free, UNCONFIRMED)]
    out += [Entry(PATCHER, name, text, ok) for name, text, ok in rows]
    out.append(Entry(PATCHER, "Learning Skills Never Fails", (
        patch("vv3_learning_never_fails") + ": every Farming, Building, Research, Healing and Parenting skill test "
        "succeeds; the skill gains and everything else are the game's own (stock: the test passes at the skill + 34% "
        "for a villager neutral about learning)."), UNCONFIRMED))
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
