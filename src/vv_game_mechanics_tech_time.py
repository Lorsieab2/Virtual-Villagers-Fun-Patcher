"""Game Mechanics: the time needed while catching up to earn the tech points for each technology level.

The owner (2026-11-06): "add sections for: Time needed for next technology: (technology name) (level) from cheapest
to most expensive" and "time needed for each technology and level. (how much time needed during catch up until you
achieve enough tech points to buy them, taking into account things that increase tech point gain and speed)".
Vital statistics shows these lines right after "Tech points:" (src/vv_game_mechanics_life.py vitals_lines).

THE RATE, from each stock exe (research/stock-executables), read with capstone for this module (2026-11-06) and
matching docs/hidden-gates-all-five-games.md (Research sections) and src/vv_game_mechanics_catchup.py:
  * Job turns: each working adult gets TURNS_PER_UNIT job turns each counted age unit, none in the last 2 units of a
    catch-up (src/vv_game_mechanics_farmers_vvN.py, with their addresses).
  * The job chooser (VV1 0x439AE0, VV2 0x449C60, VV3 0x459730, VV4 0x461CC0, VV5 0x46A3C0) picks the villager's
    highest skill or its preference the same way whatever the skill is, so a researcher whose preference and
    highest skill is Research picks Research on farmers.farming_chosen(Research) of its turns (0.83096 x
    min(1, (skill + 40) / 100); never at Research 1 or less in VV1, 5 or less in the others).
  * Research is the dispatcher's job 3 (VV1 0x44747B, VV2 0x45FE6A, VV3 0x45B19E, VV4 0x463BFC, VV5 0x46C75E); New
    Believers sends nobody while catching up until The Knowing Totem (project 4) is solved (0x46C75E / 0x46C775).
  * The session passes the Research skill test: (skill + 31) in 100 in VV1 (0x43D440), (skill + 34) in 100 in VV2
    (0x44E170) and VV3 (0x45A2C0), (skill + 34 + 15 x (Learning - 1)) in 100 in VV4 (0x462A80, Learning read at
    0x462AD5) and VV5 (0x46B270, Learning read through 0x423600); every test passes with the patcher's Learning Skills
    Never Fails.
  * A success pays Research ÷ the catch-up divisor, rounded down (no speed factor while catching up):
    VV1 ÷ 7 / 5 / 3 at Science 1 / 2 / 3, as live (0x43B2DD..0x43B34B: VV1 has no catch-up flag);
    VV2 ÷ 7 / 6 / 4 (0x4637AD, 0x463760, 0x463697; flag +0x3046C);
    VV3 ÷ 7 / 7 / 5 (0x45935F, 0x4592F4, 0x459289; flag +0x12FB4), then 1 more at Magic level 1 or more
    (0x4593D5..0x4593ED);
    VV4 ÷ 7 / 7 / 5 (0x464DEB, 0x464D6B, 0x464CEB; flag +0x171A4), then rand(Lab Equipment pieces owned) more
    (0x464E5D..0x464E82; the set is the save's collectible counts 12..23, src/vv_game_mechanics_life.py VV4_SETS);
    VV5 ÷ 7 / 7 / 5 (0x46DDED, 0x46DD6D, 0x46DCED; flag +0x17E10), then rand(the second set's pieces owned ÷ 2)
    more (0x46DE4D..0x46DE77; 0x413F50(0x50) counts ids 0x50..0x67, which the save writer 0x413B80 copies first from
    +0x770, so the save's collectible counts 0..23).
  * The fire: 1 more on rand(100) < 10 while it burns, in VV2 (0x4637C5..0x463809: its end, a real moment, later
    than the clock 0x403200), VV3 (0x459410..0x459435), VV4 (0x464E87..0x464EAB) and VV5 (0x46DE7C..0x46DEA0); none
    of these tests the catch-up flag.  VV1 has no bonus.
  * Not counted (each lasts real-life minutes or needs a villager the save does not name): VV3's potion "scientific
    clarity" (+1, 0x4593F2) and the Tribal Chief's supervision (0x4593AF); VV4's Purify Tree glow (x 3, 0x464E46).
  * Difficulty: none of the code above reads it (VV1 state +0xA30C, VV2 +0x2EAEC, VV3 +0x12F08, VV4 +0x170F4, VV5
    +0x17D54 appear nowhere in the chooser, the skill test, the payout or the tech adders VV1 0x41D120, VV2
    0x426290, VV3 0x427130, VV4 0x41E300, VV5 0x4237B0), and the prices are fixed tables (VV1 0x435AF8, VV2
    0x44380A, VV3 0x427020, VV4 0x41E220, VV5 0x4236D0).
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass

import vv_game_mechanics as gm

RESEARCH_SHOWN = 50            # the Research skill the page's figures are for (as FARMING_SHOWN)
TOP = 3                        # every technology's top level
FIRE = 0.1                     # the fire's +1 on rand(100) < 10
WORK_AGE = 280                 # age units (14 years): who gets job turns


@dataclass(frozen=True)
class Game:
    science: str
    divisors: dict[int, int]   # Science level -> the catch-up divisor
    offset: int                # the Research skill test passes (skill + offset) in 100 at Learning 1
    learning: str | None       # the technology that adds 15 to the test for each level above 1
    fire: bool
    rule: str                  # the catch-up rule in the game's words, with its addresses


GAMES = {
    1: Game("Science", {1: 7, 2: 5, 3: 3}, 31, None, False,
            "A New Home: each working adult gets 5 job turns each counted age unit; a session passes the Research "
            "test (skill + 31) times in 100 (0x43D440) and pays Research ÷ 7, ÷ 5 or ÷ 3 at Science 1, 2 or 3, "
            "rounded down, as in live play (0x43B2DD..0x43B34B); nothing adds to it."),
    2: Game("Science", {1: 7, 2: 6, 3: 4}, 34, None, True,
            "The Lost Children: each working adult gets 4 job turns each counted age unit; a session passes the "
            "Research test (skill + 34) times in 100 (0x44E170) and pays Research ÷ 7, ÷ 6 or ÷ 4 at Science 1, 2 "
            "or 3 while catching up, rounded down (0x4637AD, 0x463760, 0x463697); while the fire burns, 1 more on "
            "10% of successes (0x4637C5..0x463809: the fire's end is a real moment, so it counts only while the "
            "fire still burns when the catch-up runs)."),
    3: Game("Science", {1: 7, 2: 7, 3: 5}, 34, None, True,
            "The Secret City: each working adult except the Tribal Chief gets 4 job turns each counted age unit; a "
            "session passes the Research test (skill + 34) times in 100 (0x45A2C0) and pays Research ÷ 7, ÷ 7 or "
            "÷ 5 at Science 1, 2 or 3 while catching up, rounded down (0x45935F, 0x4592F4, 0x459289), then 1 more at "
            "Magic level 1 or more (0x4593D5); while the fire burns, 1 more on 10% of successes (0x459410)."),
    4: Game("Science", {1: 7, 2: 7, 3: 5}, 34, "Learning", True,
            "The Tree of Life: each working adult gets 4 job turns each counted age unit; a session passes the "
            "Research test (skill + 34) times in 100 at Learning 1, 15 more for each Learning level above it "
            "(0x462A80, 0x462AD5), and pays Research ÷ 7, ÷ 7 or ÷ 5 at Science 1, 2 or 3 while catching up, "
            "rounded down (0x464DEB, 0x464D6B, 0x464CEB), then 0 to (Lab Equipment pieces owned - 1) more, each "
            "equally likely (0x464E5D..0x464E82); while the Fire Pit burns, 1 more on 10% of successes (0x464E87)."),
    5: Game("Science", {1: 7, 2: 7, 3: 5}, 34, "Learning", True,
            "New Believers: nobody researches while catching up until The Knowing Totem is solved (0x46C75E, "
            "0x46C775); then each working adult gets 4 job turns each counted age unit; a session passes the "
            "Research test (skill + 34) times in 100 at Learning 1, 15 more for each Learning level above it "
            "(0x46B270), and pays Research ÷ 7, ÷ 7 or ÷ 5 at Science 1, 2 or 3 while catching up, rounded down "
            "(0x46DDED, 0x46DD6D, 0x46DCED), then 0 to (half the second collectible set's pieces owned - 1) more, "
            "each equally likely (0x46DE4D..0x46DE77); while the fire burns, 1 more on 10% of successes "
            "(0x46DE7C)."),
}

# The code checked for a read of the difficulty (the job choice, the Research test, the payout, the tech-point adder)
# and the price table, by game.
DIFFICULTY_CHECKED = {1: ("0x439AE0, 0x43D440, 0x43B2AB, 0x41D120", "0x435AF8"),
                      2: ("0x449C60, 0x44E170, 0x46361B, 0x426290", "0x44380A"),
                      3: ("0x459730, 0x45A2C0, 0x45916D, 0x427130", "0x427020"),
                      4: ("0x461CC0, 0x462A80, 0x464BB0, 0x41E300", "0x41E220"),
                      5: ("0x46A3C0, 0x46B270, 0x46DB7B, 0x4237B0", "0x4236D0")}


def difficulty_line(game: int) -> str:
    code, prices = DIFFICULTY_CHECKED[game]
    return ("Difficulty (Easy, Medium or Hard) changes none of these times: the job choice, the Research test, the "
            f"payout and the tech-point adder never read it ({code}), and the prices are a fixed table ({prices}). "
            "It changes how much the villagers eat (Food estimates).")


LOW_FOOD = ("At 250 food or less a working adult with Farming 20 or more farms on its job turn before anything "
            "else (the job turn {at}), so a researcher with Farming 20 or more researches only above 250 food.")
LOW_FOOD_AT = {3: "0x45BF00", 4: "0x465750", 5: "0x46E985"}


def _i32(data: bytes, at: int) -> int:
    return struct.unpack_from("<i", data, at)[0]


def techs(game: int, data: bytes) -> dict[str, int] | None:
    """The save's level of each technology, by the game's own name, in the save's order; None if unreadable."""
    try:
        if game == 1:
            import vv_game_mechanics_vv1 as m
            names = ("Spirituality", "Science", "Construction", "Medicine", "Fertility", "Farming")
            return {n: _i32(data, m.LEVELS + 8 * k) for k, n in enumerate(names)}
        if game == 2:
            import vv_game_mechanics_vv2 as m
            names = ("Culture", "Science", "Engineering", "Medicine", "Exploration", "Farming")
            return {n: m._i32(data, m.LEVELS + 8 * k) for k, n in enumerate(names)}     # file = state + 4
        if game == 3:
            import vv_game_mechanics_items_vv3 as items
            import vv_game_mechanics_vv3 as m
            return {n: _i32(data, m.HEADER + m.TECHS + 4 * k) for k, n in enumerate(items.TECHS)}
        if game == 4:
            import vv_game_mechanics_items_vv4 as items
            import vv_game_mechanics_vv4 as m
            return {n: _i32(data, m.LEVELS + 4 * k) for k, n in enumerate(items.TECH_PRICES)}
        if game == 5:
            import vv_game_mechanics_items_vv5 as items
            import vv_game_mechanics_vv5 as m
            return {n: _i32(data, m.LEVELS + 4 * k) for k, n, *_ in items.TECHS}
    except (struct.error, IndexError):
        return None
    return None


def price(game: int, name: str, level: int) -> int:
    """The tech points level `level` of `name` costs (each game's items module holds the table)."""
    if game in (1, 2):
        items = __import__(f"vv_game_mechanics_items_vv{game}")
        return items.TECH_COSTS[name][level - 2]
    if game == 3:
        import vv_game_mechanics_items_vv3 as items
        return items.TECH_PRICES[name][level - 1]
    if game == 4:
        import vv_game_mechanics_items_vv4 as items
        return items.TECH_PRICES[name][level - 2]
    import vv_game_mechanics_items_vv5 as items
    return next(two if level == 2 else three for _, n, two, three in items.TECHS if n == name)


def buyable(game: int, levels: dict[str, int], both_factions: bool = False) -> list[str]:
    """The technologies whose next level can still be bought.  The Secret City's two factions shut each other out
    once one is chosen (unless the patcher lets both be bought)."""
    lowest = 0 if game == 3 else 1                 # only The Secret City's factions start at 0
    out = [n for n, lvl in levels.items() if lowest <= lvl < TOP]
    if game == 3 and not both_factions:
        if levels.get("Nature", 0) > 0:
            out = [n for n in out if n != "Magic"]
        elif levels.get("Magic", 0) > 0:
            out = [n for n in out if n != "Nature"]
    return out


def lab_bonus(game: int, data: bytes) -> float:
    """The average extra tech points a success gets from collectibles owned: rand(n) is 0 to n - 1."""
    if game not in (4, 5):
        return 0.0
    import vv_game_mechanics_life as life
    at = life.COLLECTIBLES_AT[game]
    try:
        counts = struct.unpack_from("<48i", data, at)
    except struct.error:
        return 0.0
    pieces = sum(1 for c in (counts[12:24] if game == 4 else counts[0:24]) if c > 0)
    n = pieces if game == 4 else pieces // 2
    return (n - 1) / 2 if n > 0 else 0.0


def per_success(game: int, levels: dict[str, int], skill: int, lab: float, fire: bool = False) -> float:
    """The average tech points a successful catch-up session pays."""
    rule = GAMES[game]
    points = skill // rule.divisors.get(levels.get(rule.science, 1), rule.divisors[1]) + lab
    if game == 3 and levels.get("Magic", 0) >= 1:
        points += 1
    return points + (FIRE if fire and rule.fire else 0.0)


def per_unit(game: int, levels: dict[str, int], skill: int = RESEARCH_SHOWN, lab: float = 0.0, fire: bool = False,
             never_fails: bool = False) -> float:
    """Tech points one researcher (preference and highest skill Research) earns each counted age unit."""
    import vv_game_mechanics_farmers as farmers
    rule = GAMES[game]
    module = farmers.game_module(game)
    chosen = module.farming_chosen(skill)          # the chooser is the same for every preferred skill
    offset = rule.offset + (15 * (levels.get(rule.learning, 1) - 1) if rule.learning else 0)
    passes = 1.0 if never_fails else min(100, max(0, skill + offset)) / 100.0
    return module.TURNS_PER_UNIT * chosen * passes * per_success(game, levels, skill, lab, fire)


@dataclass(frozen=True)
class Goal:
    name: str
    level: int
    cost: int                  # this level's own price
    needed: int                # tech points to earn from now: the unbought levels up to it, less the save's points
    units: float               # counted age units of job turns for one researcher (0: can be bought now)


def goals(game: int, levels: dict[str, int], tech: int, rate, every_level: bool,
          both_factions: bool = False) -> list[Goal]:
    """Each buyable technology's next level (or every remaining level), cheapest first.  `rate(levels)` gives the
    tech points an age unit at those levels: a level bought on the way (Science, Magic, Learning) changes it."""
    out = []
    for name in buyable(game, levels, both_factions):
        have, spent, units, owned = tech, 0, 0.0, dict(levels)
        for level in range(levels[name] + 1, TOP + 1 if every_level else levels[name] + 2):
            cost = price(game, name, level)
            if have < cost:
                speed = rate(owned)
                units = math.inf if speed <= 0 else units + (cost - have) / speed
                spent += cost - have
                have = cost
            have -= cost
            owned[name] = level
            out.append(Goal(name, level, cost, spent, units))
    return sorted(out, key=lambda g: (sum_cost(g, levels, game), g.name, g.level))


def sum_cost(goal: Goal, levels: dict[str, int], game: int) -> int:
    """The prices of the unbought levels up to `goal`, added up."""
    return sum(price(game, goal.name, lvl) for lvl in range(levels[goal.name] + 1, goal.level + 1))


def closed_words(ctx, units: float) -> str:
    """The counted catch-up time for `units` age units of job turns, and the real-life time closed it takes."""
    import vv_game_mechanics_life as life
    on = gm.speed_name(ctx.speed)
    limits = gm.AWAY_LIMITS[ctx.game]
    whole = math.ceil(units - 1e-9)
    per_close = int(limits["over"] // ctx.unit) - 2        # job-turn units in one catch-up of 24 counted hours
    closings = max(1, math.ceil(whole / per_close))
    counted = whole + 2 * closings
    seconds = counted * ctx.unit
    real = seconds if closings == 1 and seconds <= life.full_away(ctx) else closings * limits["band_end"]
    # One shape whatever the figures (the claims files key each line on its shape).
    return (f"{counted:,} counted age units ({gm.duration(seconds)} of time away on {on} speed), closed for at "
            f"least {gm.duration(real)} of real-life time in all (catch-ups needed: {closings:,})")


def workers(everyone) -> int:
    """Working adults: 14 or more, not sick, pregnant or nursing, 20 health or more (The Secret City's chief never
    works; New Believers' Heathens are not in the tribe)."""
    return sum(1 for p in everyone if not p.heathen and not p.chief and p.age >= WORK_AGE and not p.sick
               and not p.carrying and p.health >= 20)


def lines(ctx, everyone) -> list[gm.Fact]:
    """The two sections' lines for a save's Vital statistics (nothing on the general page or a paused save's
    unknown tech points)."""
    import vv_game_mechanics_farmers as farmers_mod
    import vv_game_mechanics_life as life
    village, game = ctx.village, ctx.game
    if village.general or ctx.tech is None or game not in GAMES:
        return []
    levels = techs(game, village.data)
    if levels is None:
        return []
    out: list[gm.Fact] = []
    add = lambda text, ok=True, sub=True: out.append(gm.Fact(life.VITALS, text, ok, sub))  # noqa: E731
    rule = GAMES[game]
    never = village.has(f"vv{game}_learning_never_fails") is True
    lab = lab_bonus(game, village.data)
    rate = lambda owned: per_unit(game, owned, RESEARCH_SHOWN, lab, False, never)  # noqa: E731
    adults = workers(everyone or [])
    both = game == 3 and village.has("vv3_both_factions") is True
    if game == 5:
        import vv_game_mechanics_vv5 as vv5
        if _i32(village.data, vv5.PROJECTS + 8 * 4) < vv5.PUZZLE_THRESHOLDS[4]:
            rate = lambda owned: 0.0  # noqa: E731

    def goal_lines(head: str, g: Goal) -> None:
        if g.needed <= 0:
            add(f"{head}: can be bought now.")
        elif math.isinf(g.units):
            add(f"{head}, {g.needed:,} still needed: not earned while catching up now (nobody researches: the rule "
                "below).")
        else:
            add(f"{head}, {g.needed:,} still needed; one researcher: {closed_words(ctx, g.units)}.")
            if adults > 1:
                add(f"{g.name} level {g.level} with all {adults} working adults researching: "
                    f"{closed_words(ctx, g.units / adults)}.")

    now = rate(levels)
    earns = (f"one earns {now:,.2f} tech points each counted age unit now" if now else
             "nobody researches while catching up until The Knowing Totem is solved, and it is not solved yet")
    add(f"Time needed for next technology (estimates, cheapest first), while catching up, for researchers with "
        f"Research {RESEARCH_SHOWN} set to Research: {earns} (an age unit is {gm.duration(ctx.unit)} of time away "
        f"on {gm.speed_name(ctx.speed)} speed).", True, False)
    nexts = goals(game, levels, ctx.tech, rate, False, both)
    for g in nexts:
        goal_lines(f"{g.name} level {g.level}: {g.cost:,} tech points", g)
    if not nexts:
        add("Every technology is at its top level.", gm.SAVE)
        return out
    add("Time needed for each technology and level (estimates, cheapest first): levels are bought in order, so a "
        "later level needs the points of the unbought levels below it as well as its own; a "
        + {3: "Science or Magic", 4: "Science or Learning", 5: "Science or Learning"}.get(game, "Science")
        + " level bought on the way raises the rate for the levels after it.", True, False)
    for g in goals(game, levels, ctx.tech, rate, True, both):
        goal_lines(f"{g.name} level {g.level}: {sum_cost(g, levels, game):,} tech points from level "
                   f"{levels[g.name]}", g)
    if game == 3 and not both and levels.get("Nature", 0) == 0 and levels.get("Magic", 0) == 0:
        add("Nature and Magic are the two factions: buying level 1 of one shuts the other out.", gm.CODE)

    # How it is worked out.
    add(rule.rule, gm.CODE)
    if rule.fire:
        fired = per_unit(game, levels, RESEARCH_SHOWN, lab, True, never) if now else 0.0
        if fired:
            add(f"With the fire burning through the whole catch-up, one researcher earns {fired:,.2f} tech points "
                f"each counted age unit instead of {now:,.2f}: every time above is {now / fired:.3f} times as long.")
    if lab:
        add(f"This save's collectibles add {lab:g} tech points to each success on average (in the rate above).",
            gm.SAVE)
    if never:
        add(gm.patch_words(village, f"vv{game}_learning_never_fails", "every Research test passes (in the rate "
                           "above)"), gm.CODE)
    if village.has(f"vv{game}_enable_origins_exclusive_features") is True:
        add(f"With the patcher's \"{gm.feature_name(f'vv{game}_enable_origins_exclusive_features')}\" (in this "
            "game): an owned Tech Point Doubler doubles the tech points research earns, so every time above halves; "
            "whether this save owns one is not read here.", False if game == 4 else gm.CODE)
    chosen = farmers_mod.game_module(game).FARMING_CHOSEN
    add(f"How it is worked out: points still needed ÷ (job turns x the share of turns that choose Research, "
        f"{chosen:.5f} x min(1, (Research + 40) ÷ 100), x the share that pass the Research test x the points a "
        "success pays), rounded up to whole counted age units, plus the last 2 counted age units of each catch-up, "
        "which give no job turns. A catch-up counts at most the time-away limits: up to "
        f"{gm.duration(life.full_away(ctx))} closed counts in full on {gm.speed_name(ctx.speed)} speed, longer "
        f"counts {gm.duration(gm.AWAY_LIMITS[game]['band'])} until it is more than "
        f"{gm.duration(gm.AWAY_LIMITS[game]['band_end'])}, then {gm.duration(gm.AWAY_LIMITS[game]['over'])}; so "
        "the real-life time closed is the counted time when one closing that long covers it, otherwise more than "
        f"{gm.duration(gm.AWAY_LIMITS[game]['band_end'])} for each catch-up needed. "
        f"The skill is taken to stay at {RESEARCH_SHOWN}, for every working adult.", True)
    add("Not counted: a villager who likes or dislikes learning (a different test), "
        + {3: "the potion \"scientific clarity\" (+1 for 10 real-life minutes, real time, 0x4593F2) and the "
              "Tribal Chief's supervision (0x4593AF), ",
           4: "the Purify Tree's glow (3 times the points for 4 real-life minutes, real time, 0x464E46), "
           }.get(game, "")
        + "the skill gained on each success and tech points that come any other way.", gm.CODE)
    if game >= 3:
        add(LOW_FOOD.format(at=LOW_FOOD_AT[game]), gm.CODE)
    add(difficulty_line(game), gm.CODE)
    if ctx.paused:
        add("Saved paused: no time away counts until it is unpaused.", gm.SAVE)
    add("Who researches now is not kept in the save.", gm.SAVE)
    return out
