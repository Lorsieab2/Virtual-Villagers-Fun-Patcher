"""The Secret City (VV3): the Tribal Chief's "Directing work", everything it affects, read from the stock exe and the
patcher's own patches, with this save's live state (the owner, 2026-11-19: "explain what the chief's Directing Work
does to EVERYTHING it affects ... Nothing withheld").

THE STOCK EXE (research/stock-executables, The Secret City).
  * The chief's work site is the villager record's +0xEA0 (saved: the name + 0xCC in a save's villager entry; the
    chief byte is +0xE80, the name + 0xAC).  Dropping the chief on a work site writes it (the drop handlers
    0x4215F6 the Hospital 9 at Medicine 2, 0x42185D The Ancient Bath 0x16, 0x4222F5 the Statue's scaffolding 0x1A
    at Leadership 3 (below it the chief says string 0x132), 0x422453 the bee hive 0x15, 0x4224AC research 4,
    0x422574 any fruit tree 0x17, 0x422690 / 0x42271A / 0x4227AA / 0x422835 huts 0xB / 0xC / 0xD / 0xF, 0x4229AE
    The Ruins 0x1B, 0x422A0F The Roster of the Dead 0x1D, 0x4698E6 the sea 0x1C once The Sharks is solved).
  * The chief never takes a job (0x45C110 -> 0x45BDA0).  Each time it chooses what to do: a chief under 14 (age
    shown < 280) plays on rand(100) <= 6 (0x45BDB7); then 0x45FF30(0x2D) -> 0x45ECB0 looks for the first present
    villager whose current behaviour (+0xF24) is 0x2D, "Not feeling well" (string 0x11C, handler 0x449FC0; the
    sickness roll starts it at 0x4602B8), and if there is one the chief runs behaviour 0x8A, "Concerned about the
    sick" (string 0x1E4, handler 0x452540: three walks, each followed by a wait of rand(20) + 1, and nothing
    else), with no roll; then, with a site, 0x458C70; else it wanders.  0x458C70 (its table at 0x458D94) clears
    the site when its work is over -- the Hospital (9) and site 10 at once, a hut once built (0x4321F0), the hive
    while The Bee Hive is not solved, The Ancient Bath (puzzle 7), the scaffolding (puzzle 8), The Ruins (puzzle
    6), The Roster of the Dead (puzzle 3) once solved, the trees once none is planted with fruit -- and otherwise
    runs behaviour 0x81, "Directing work" (0x44B5F0: a walk to a point by the site and gestures; no skill test, no
    food, no tech points, no skill for the chief).  Research (4) and the sea (0x1C) never end.
  * The bonus roll 0x45FC60(site): the chief (0x45EF30) alive (+0xE78 > 0), not sick (+0xE89), its site equal
    to the work's site, then rand(100) < 25 x Leadership (tech 4, 0x426FC0(4)).  It does not look at where the
    chief stands or what it is doing, nor at the catch-up flag: it is asked by the work's own payoff, live and
    while catching up.  Its callers: fish 0x458EC6 (+fish / 3 into the same gain; the crab 0x458FDA has none),
    fruit 0x434AF8 (site 0x17 for every tree: + pick / 3, a second gain; the tree loses only the pick), honey
    0x431C36 (+ take / 2, a second gain), research 0x45923E (Science 0: + points / 3) and 0x4593B6 (Science 1+:
    + points / 4), a hut's building step 0x4327D8 (chief at any hut site 0xB-0xF / 0x11: +1 progress; 0xE and
    0x11 are never written), The Ancient Bath 0x431583 (+1), The Roster of the Dead 0x43602A (+1), The Ruins
    0x4363CA (+1), the scaffolding 0x4352E2 (the load counts twice).  The scaffolding's builders work there only
    while the chief directs it (0x422344..0x42235B, Building 20 or more).
  * Catch-up: the chief gets no job turns (0x460555); the others' catch-up payoffs ask the same roll.

THE PATCHER'S PATCHES (scripts/ and data/ of this repository).
  * Origins doublers (scripts/build_vv3_origins_feature.py, v1.35.97's whitelist from PR #805,
    docs/doubler-composition-audit.md): an owned Food Point Doubler doubles fruit, honey, fish and crabs, with the
    chief's fruit and honey bonus and the chief's grant (job event 43); an owned Tech Point Doubler doubles the
    research points, the chief's quarter and third, Magic, the potion point, the fire's point and duplicates.
  * vv3_chief_hospital_supervision (native/vvfp_chief_hospital): the Hospital site directs (the stock clears it).
  * vv3_fruit_harvested_at_food_bin (data/builds.json): the fruit and its chief bonus are paid at the food bin.
  * vv3_learning_never_fails: every work skill test passes, so more payoffs ask the roll; the roll is unchanged.
  * vv3_builders_and_healers_work_first: builders pick building work about 3 times in 4; the chief is untouched.
  * vv3_population_256: the chief search (0x45EF30, 0x45FC10) covers 256 records.
  * vv3_sickness_multiplier: sickness comes more often; a sick chief gives no bonus.
  None of the others touches the chief's site, the roll or the bonus.  The Secret City has no Food Mastery and no
  Food Gains are Flat patch (its fruit, honey and fish pay fixed amounts by speed).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

import vv_game_mechanics as gm

GROUP = "Tribal Chief: Directing work"
CHIEF, HEALTH, SICK, SITE = 0xAC, 0xA4, 0xB5, 0xCC          # a save's villager entry, from the name
SEA, TREE, HIVE = 0x1C, 0x17, 0x15
ORIGINS = "vv3_enable_origins_exclusive_features"

# site -> (the place, what the chief's roll adds there, the puzzle whose solving ends it or None)
SITES = {
    0x1C: ("the sea", "each fish caught gets a third more, rounded down (11, 8 or 5 become 14, 10 or 6 on Fast, "
                      "Normal or Slow; 8 becomes 10 while catching up); a crab gets nothing more", None),
    0x17: ("the fruit trees", "each fruit pick, from any tree, adds a third more food, rounded down (7, 3 or 2 add "
                              "2, 1 or 0 on Fast, Normal or Slow; 4 adds 1 while catching up); the tree loses only "
                              "the pick", None),
    HIVE: ("the bee hive", "each honey take adds half as much again, rounded down (7, 3 or 2 add 3, 1 or 1 on Fast, "
                           "Normal or Slow; 4 adds 2 while catching up); the hive loses only the take", None),
    4: ("research", "each research session that pays adds a third more tech points at Science level 0, a quarter "
                    "more at Science 1 to 3, rounded down", None),
    0xB: ("hut 1", "each building step on any hut adds 1 more to that hut's progress", None),
    0x16: ("The Ancient Bath", "each work step adds 1 more to its progress", 7),
    0x1D: ("The Roster of the Dead", "each work step adds 1 more to its progress", 3),
    0x1B: ("The Ruins", "each work step adds 1 more to its progress", 6),
    0x1A: ("the Statue's scaffolding", "each load the builders bring counts twice; the builders work there only "
                                       "while the chief directs it", 8),
    9: ("the Hospital", "", None),
}
SITES.update({k: (SITES[0xB][0].replace("1", str(n)), SITES[0xB][1], None)
              for k, n in ((0xC, 2), (0xD, 3), (0xF, 4))})
SITES.update({k: ("the fruit trees", SITES[TREE][1], None) for k in (0x18, 0x19)})


@dataclass(frozen=True)
class Chief:
    name: str
    site: int
    sick: bool
    health: int

    def directing(self, site: int) -> bool:
        return self.site == site and self.health > 0 and not self.sick


def chief(village: gm.Village) -> Chief | None:
    """The save's Tribal Chief, or None (no chief, or the villager table could not be read)."""
    import vv_last_names as ln
    data = village.data
    try:
        entries = ln._entries(3, data)
    except Exception:  # noqa: BLE001 -- an unreadable table has no chief to show
        return None
    for at in entries:
        try:
            if data[at + CHIEF]:
                return Chief(ln._cstr(data, at, 0x18), struct.unpack_from("<i", data, at + SITE)[0],
                             data[at + SICK] != 0, struct.unpack_from("<i", data, at + HEALTH)[0])
        except (struct.error, IndexError):
            return None
    return None


def _patch(village: gm.Village, feature: str, effect: str) -> str:
    """A patch and what it does to directing work, said whether or not it is in this game (nothing withheld)."""
    state = {True: "in this game", False: "not in this game"}.get(village.has(feature),
                                                                    "whether the game has it could not be told")
    return f"\"{gm.feature_name(feature)}\" ({state}): {effect}."


def chance(leadership: int) -> float:
    """The roll 0x45FC60: rand(100) < 25 x Leadership."""
    return max(0, min(100, 25 * leadership)) / 100


def fish_food(village: gm.Village, leadership: int, live: int, caught: int = 8) -> tuple[float, float] | None:
    """The average food of a fish catch (live, while catching up) with the chief directing the sea, or None when it
    is not: fish + the roll's share of fish ÷ 3 (0x458EC6)."""
    c = chief(village)
    if c is None or not c.directing(SEA) or leadership <= 0:
        return None
    p = chance(leadership)
    return live + p * (live // 3), caught + p * (caught // 3)


def facts(village: gm.Village, leadership: int, science: int, solved) -> list[gm.Fact]:
    """The group: the live state first, then the rule, each site, catch-up and the patches.  `solved(pid)`: whether
    puzzle `pid` is solved in this save."""
    out: list[gm.Fact] = []
    add = lambda text, ok=gm.CODE, sub=False: out.append(gm.Fact(GROUP, text, ok, sub))  # noqa: E731
    c = chief(village)
    pct = f"{chance(leadership):.0%}"
    if c is None:
        add("This village has no Tribal Chief now, so no work is directed and nothing below applies until it has one.",
            gm.SAVE)
    else:
        place = SITES.get(c.site, (None, "", None))
        if c.site == 0:
            add(f"{c.name}, the Tribal Chief, is not directing any work: drop the chief on a work site to start "
                f"(Leadership {leadership}, so the chief's roll would pass {pct} of the time).", gm.SAVE)
        elif place[0] is None:
            add(f"{c.name}, the Tribal Chief, has work site {c.site}, which no payoff in the game asks about: it adds "
                "nothing.", gm.SAVE)
        else:
            what = place[1] or ("nothing in the stock game (the chief stops at once); with the patcher's \"Tribal "
                                "Chief Supervises the Hospital\" it helps cures and study" if c.site == 9 else "")
            state = ("" if not (c.sick or c.health <= 0) else
                     " The chief is sick now, so the roll never passes until the chief is cured.")
            ends = place[2]
            if ends is not None and solved(ends):
                state += (" That work is finished, so the chief stops directing it the next time it chooses what to "
                          "do.")
            add(f"{c.name}, the Tribal Chief, is directing work at {place[0]}: {what}"
                + (f", each time the chief's roll passes ({pct} of the time at Leadership {leadership})" if place[1]
                   else "") + "." + state, gm.SAVE)
        if leadership <= 0:
            add("Leadership is 0 in this village, so directing work never adds anything; Leadership 1, 2 or 3 makes "
                "the roll pass 25%, 50% or 75% of the time.", gm.SAVE)
    add("How it starts and how long it lasts: drop the chief on a work site; the chief never does the work itself. "
        "The site is kept in the save, and each time the chief chooses what to do it goes back to direct that work, "
        "for as long as the work lasts: research and the sea never end; a hut, The Ancient Bath, The Roster of the "
        "Dead, The Ruins and the Statue's scaffolding end when finished; the bee hive ends at once while The Bee Hive "
        "is not solved; the fruit trees end when no tree is planted and ready. Dropping the chief somewhere else "
        "changes the site.")
    add("Before directing, each time the chief chooses what to do: a chief under 14 plays 7 times in 100; then, if "
        "any villager is \"Not feeling well\" at that moment (the action a villager starts when it falls sick, among "
        "others), the chief always goes \"Concerned about the sick\" instead: three short walks with a short wait "
        "after each, which cure no one and change nothing; then it chooses again. There are no odds on it: as long "
        "as someone is \"Not feeling well\" the chief keeps doing that, and directs work only once no one is. The "
        "bonus still comes meanwhile, as it needs only the chief's site. Directing itself is a short walk to the "
        "site and gestures: it costs and earns the chief nothing, and gives no skill.")
    add(f"The roll: each time someone's work at the chief's site pays off, the game rolls 0 to 99 and adds the "
        f"bonus when the roll is under 25 x Leadership: 25%, 50% or 75% at Leadership 1, 2 or 3, never at 0 "
        f"(this village: {pct}). The chief must be alive and not sick; where the chief stands or what it is doing "
        "does not matter, so the bonus also comes while the chief is concerned about the sick, plays or wanders.")
    add("What it adds, by site:")
    for label, site in (("The sea (once The Sharks is solved)", SEA), ("Any fruit tree", TREE),
                        ("The bee hive (once The Bee Hive is solved)", HIVE), ("Research", 4), ("Any hut", 0xB),
                        ("The Ancient Bath", 0x16), ("The Roster of the Dead", 0x1D), ("The Ruins", 0x1B),
                        ("The Statue's scaffolding (the chief can be dropped there only at Leadership 3)", 0x1A)):
        add(f"{label}: {SITES[site][1]}.", gm.CODE, True)
    add("The Hospital: in the stock game the chief dropped there stops at once and adds nothing.", gm.CODE, True)
    add("It never changes Grant Food, Educate or Point Out a Rare collectible (the chief's powers, under Chances), "
        "the Farming, Building or Research skill tests, skill gains, or how much a fruit tree or the hive loses.")
    add(f"While catching up (time away): the chief gets no job turns of its own, but the others' work at its site "
        "still asks the roll and gets the same bonus as live (fish 8 becomes 10, fruit 4 adds 1, honey 4 adds 2, "
        f"research and building as above). The site is not ended while the game is closed. Science is level "
        f"{science} here, so research gets "
        + ("a third" if science <= 0 else "a quarter") + " more.")
    # The patcher's patches (see the module notes).
    add("With the patcher's patches:")
    add(_patch(village, ORIGINS, "an owned Food Point Doubler doubles fruit and honey picks, fish and crabs, the "
                       "chief's bonus and the chief's grant included; an owned Tech Point Doubler doubles the "
                       "research points, the chief's research bonus included"), gm.CODE, True)
    add(_patch(village, "vv3_chief_hospital_supervision", "the chief dropped on the Hospital directs work there: "
                       "a healer's failed cure goes ahead when the chief's roll passes, and study there gives twice "
                       "the Medicine skill"), gm.CODE, True)
    add(_patch(village, "vv3_fruit_harvested_at_food_bin", "the fruit, and the chief's third more, are added "
                       "when the fruit reaches the food bin instead of at the tree"), False, True)
    add(_patch(village, "vv3_learning_never_fails", "every work skill test passes, so more work pays off and "
                       "asks the chief's roll; the roll itself is unchanged"), gm.CODE, True)
    add(_patch(village, "vv3_builders_and_healers_work_first", "builders choose building work about 3 times "
                       "in 4, so a chief directing a hut or a puzzle site has more steps to add to; the chief "
                       "itself is not changed"), gm.CODE, True)
    add(_patch(village, "vv3_population_256", "the game finds the chief among all 256 villagers"), gm.CODE,
        True)
    add(_patch(village, "vv3_sickness_multiplier", "sickness comes more often, and a sick chief adds "
                       "nothing until cured"), gm.CODE, True)
    add("No other patch changes the chief's site, the roll or the bonus. The Secret City has no Food Mastery and no "
        "\"Food Gains are Flat\" patch: its fruit, honey and fish pay fixed amounts by speed, and the chief's bonus "
        "is worked out from those. Hungrier Villagers changes only the eating, and 2-10x Tech Cost only the prices.",
        gm.CODE, True)
    return out
