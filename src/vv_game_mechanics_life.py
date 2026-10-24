"""Game Mechanics: the village's people and its clocks, for all five games (src/vv_game_mechanics.py).

Four groups every game's page gains, built here from what each game's module reads (a `Context`):

  Vital statistics       first on the page: food, sources, tech points, collectibles, mushrooms, the next island
                         event and birth, population against its limit, the game's speed, difficulty and time away,
                         and the food estimates (marked as estimates, their inputs as sub-bullets).
  Nursing and pregnancy  each mother carrying babies, how many, and when they are born.
  Villager timers        children growing up, the elderly and the old-age rolls, the sick, A New Home's Golden
                         Child, New Believers' faith.
  Village timers         puzzles under way, the next natural island event and what decides it, the patcher's own
                         timers kept beside the save.

THE VILLAGERS (each game's saved entry, offsets relative to the villager's name; vv_last_names and the checker
find the entries the game loads; Cheat Engine's tables in docs/villager-record-reference.md and the island-event
companion's field tables, native/vvfp_island_events/island_event_games.inc):

  game  age     processed  health  sick          conceived  babies   expected father  other
  1     -0x28   -0x24      -0x2C   -0x1C dword   -0x18      -0x14    (not kept)       family -0x04
  2     -0x34   -0x30      -0x38   -0x28 dword   -0x24      -0x20    +0x5C
  3     -0x10   +0xA0      +0xA4   +0xB5 byte    +0xB8      +0xBC    +0x74            Tribal Chief +0xAC byte
  4     -0x10   +0xA0      +0xA4   +0xAC byte    +0xB0      +0xB4    +0x74
  5     -0x10   +0xA0      +0xA4   +0xAC byte    +0xB0      +0xB4    +0x74            faction -0x1F byte, faith -0x18

  The "processed" age is the age the life tick has stepped up to (time away raises the age at once and the
  processed age catches up).  Conceiving stores the processed age (VV1 0x43BBFA, VV2 0x44BA00, VV4 0x45E830);
  the babies come when the processed age passes it by 40 (VV1 0x42EF27, VV2 0x43BE18), on the 41st age unit.
  The Details screen's "Nursing for: N min" is (conceived + 41 - processed) x the speed in The Secret City to New
  Believers (0x46DBC3, 0x447C0F, 0x44B123) and (conceived + 40 - processed) x the speed in A New Home
  (0x449352).  Babies: A New Home and The Lost Children write 2 or 3 for twins or triplets and nothing for one
  (0 = one); the later games write 1, 2 or 3.  "Pregnant" and "nursing" are one state in every game.
  New Believers: a villager whose faction byte (record +0x1CEC) is not 0 is a Heathen outside the tribe -- the
  test the patcher's Village Statistics uses (native/statistics_export village_elders.c).  Such Heathens are
  left out of every count and total here (the owner: Heathens never count unless they are in the tribe).

Nothing here writes anything.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

import vv_game_mechanics as gm

VITALS = "Vital statistics"
NURSING = "Nursing and pregnancy"
VILLAGER_TIMERS = "Villager timers"
VILLAGE_TIMERS = "Village timers"

YEAR = 20                                    # age units a year
BIRTH_UNITS = 41                             # the babies come on the 41st age unit after conceiving
DETAILS_UNITS = {1: 40, 3: 41, 4: 41, 5: 41}  # the Details screen's "Nursing for" (VV1 0x449375; VV3-5 add 0x29)
CATCH_UP_STEP = 2                            # real seconds a counted age unit takes to work off (UNCONFIRMED)
DIFFICULTY = {0: "Easy", 1: "Medium", 2: "Hard"}

# The difficulty: the dword each game's own menus set to 0, 1 or 2 (Easy, Medium, Hard; the exes' strings) and
# its eating, starving and sickness code reads -- VV1 manager +0xA30C (0x42ECE1), VV2 +0x2EAEC (0x43BB0E), VV3
# +0x12F08 (0x455C53), VV4 +0x170F4 (0x45E938), VV5 +0x17D54 (0x465F58).  File offsets: +4 for the first three
# games (their saves start the manager 4 bytes in), +0x10 for the last two.
DIFFICULTY_AT = {1: 0xA30C + 4, 2: 0x2EAEC + 4, 3: 0x12F08 + 4, 4: 0x170F4 + 0x10, 5: 0x17D54 + 0x10}


def difficulty(game: int, data: bytes) -> int | None:
    at = DIFFICULTY_AT[game]
    if at + 4 > len(data):
        return None
    value = struct.unpack_from("<i", data, at)[0]
    return value if value in DIFFICULTY else None


@dataclass(frozen=True)
class Layout:
    age: int
    processed: int
    health: int
    sick: int
    sick_byte: bool
    conceived: int
    babies: int
    father: int | None
    singles_unwritten: bool               # one baby is written as 0 (A New Home, The Lost Children)


LAYOUTS = {
    1: Layout(-0x28, -0x24, -0x2C, -0x1C, False, -0x18, -0x14, None, True),
    2: Layout(-0x34, -0x30, -0x38, -0x28, False, -0x24, -0x20, 0x5C, True),
    3: Layout(-0x10, 0xA0, 0xA4, 0xB5, True, 0xB8, 0xBC, 0x74, False),
    4: Layout(-0x10, 0xA0, 0xA4, 0xAC, True, 0xB0, 0xB4, 0x74, False),
    5: Layout(-0x10, 0xA0, 0xA4, 0xAC, True, 0xB0, 0xB4, 0x74, False),
}
GOLDEN_FAMILY = 199                          # A New Home's Golden Child (vv_game_mechanics_vv1 HIDDEN_LINES)
VV1_FAMILY = -0x04
VV3_CHIEF = 0xAC
VV5_FACTION, VV5_FAITH = -0x1F, -0x18


@dataclass
class Person:
    name: str
    sex: str
    age: int
    processed: int
    health: int
    sick: bool
    conceived: int                           # the processed age at conception; 0 = not carrying
    babies: int                              # 1 to 3 while carrying
    father: str = ""
    heathen: bool = False                    # New Believers: outside the tribe
    faith: int | None = None
    golden: bool = False                     # A New Home's Golden Child
    chief: bool = False                      # The Secret City's Tribal Chief

    @property
    def carrying(self) -> bool:
        return self.conceived != 0

    @property
    def years(self) -> int:
        return self.age // YEAR


def _i32(data: bytes, at: int) -> int:
    return struct.unpack_from("<i", data, at)[0]


def people(village: gm.Village) -> list[Person] | None:
    """Every living villager the game loads from this save (statues and bodies left out), or None when the
    villager table cannot be read.  New Believers' Heathens are returned marked; every count leaves them out."""
    try:
        import vv_last_names as ln
        entries = ln._entries(village.game, village.data)
    except Exception:  # noqa: BLE001 -- an unreadable table gives no people lines
        return None
    lay = LAYOUTS[village.game]
    f = ln.FIELDS[village.game]
    data = village.data
    out = []
    for at in entries:
        try:
            sick = data[at + lay.sick] != 0 if lay.sick_byte else _i32(data, at + lay.sick) != 0
            conceived = _i32(data, at + lay.conceived)
            raw = _i32(data, at + lay.babies)
            babies = (raw if raw in (2, 3) else 1) if lay.singles_unwritten else (raw if raw in (1, 2, 3) else 1)
            p = Person(ln._cstr(data, at, f.name_cap), "Male" if _i32(data, at + f.sex) == f.male else "Female",
                       _i32(data, at + lay.age), _i32(data, at + lay.processed), _i32(data, at + lay.health), sick,
                       conceived, babies)
            if lay.father is not None and conceived:
                p.father = ln._cstr(data, at + lay.father, 0x18)
            if village.game == 1:
                p.golden = _i32(data, at + VV1_FAMILY) == GOLDEN_FAMILY
            if village.game == 3:
                p.chief = data[at + VV3_CHIEF] != 0
            if village.game == 5:
                p.heathen = data[at + VV5_FACTION] != 0
                p.faith = _i32(data, at + VV5_FAITH)
        except (struct.error, IndexError):
            continue
        out.append(p)
    return out


def tribe(everyone: list[Person]) -> list[Person]:
    """The villagers who count: in New Believers only the tribe (faction 0); everyone in the other games."""
    return [p for p in everyone if not p.heathen]


# ---------------------------------------------------------------------------
# What each game's module hands over
# ---------------------------------------------------------------------------


@dataclass
class Source:
    """A food source: its amount now, what it adds back for each age unit on average (its refill shared out over
    the time between refills, in food), its cap, and its next refill (a real moment) when it has one."""
    name: str
    amount: int | None
    cap: int | None = None
    per_unit: float = 0.0
    next_refill: float | None = None
    refill_words: str = ""
    unlimited: bool = False                  # the sea: limited only by the gatherers
    verified: bool | str = False


@dataclass
class Context:
    village: gm.Village
    speed_value: int
    last: float                              # the save's last moment (real), where time away counts from
    food: int
    low_food: int                            # at or below this, meals are skipped and health is lost
    extra_from: int                          # on Medium, from this much food 2 more 76% of the time
    sources: list[Source] = field(default_factory=list)
    tech: int | None = None
    tech_words: str = ""
    brown: int = 6
    red: int = 35
    red_share: float = 0.08
    mushrooms_an_hour: float | None = None   # random mushrooms appearing an hour while playing, at most
    mushroom_words: str = ""
    mastery: float = 1.0                     # Food Mastery's multiplier on food gained
    golden: bool = False
    event_next: float | None = None          # the save's next island event (real), None while paused
    event_paused_left: float | None = None   # saved paused: real seconds of play to it
    event_rule: str = ""
    event_running: str = ""                  # paused, catch-up, time away, Time Warp
    medicine: int | None = None
    elderly_from: dict[int, int] = field(default_factory=dict)   # Medicine level -> years
    old_age_from: dict[int, int] = field(default_factory=dict)   # Medicine level -> years
    parents_from: int = 18                   # years
    sick_loss: tuple[float, float] = (0.61, 0.19)    # the chance of -1 health an age unit above / at 20 health
    sick_end: str = ""
    collectibles: list[tuple[str, bool | str]] = field(default_factory=list)
    limit: tuple[str, bool | str] | None = None
    puzzles: list[tuple[str, int, int]] = field(default_factory=list)   # (name, progress, needed): under way
    village_extra: list[gm.Fact] = field(default_factory=list)
    villager_extra: list[gm.Fact] = field(default_factory=list)
    vitals_extra: list[gm.Fact] = field(default_factory=list)
    food_words: str = ""                     # how the game feeds its villagers, for the estimates
    gatherer_words: str = ""
    trips: list[tuple[str, float]] = field(default_factory=list)   # (a gathering trip, the food it brings)

    @property
    def game(self) -> int:
        return self.village.game

    @property
    def speed(self) -> int:
        return gm.speed_base(self.speed_value)

    @property
    def paused(self) -> bool:
        return self.speed_value >= gm.PAUSED

    @property
    def unit(self) -> float:
        """An age unit in real seconds at the save's speed (60 x 3, 6 or 10)."""
        return 60.0 * self.speed

    @property
    def difficulty(self) -> int | None:
        return difficulty(self.game, self.village.data)


# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------


def full_away(ctx: Context) -> float:
    """The most time away the game counts in full at the save's speed (the verified clamp)."""
    limits = gm.AWAY_LIMITS[ctx.game]
    return min(limits["full"].get(ctx.speed, limits["full"][gm.NORMAL]), limits["band"])


def by_age(ctx: Context, units: float) -> tuple[float | None, str]:
    """When `units` more age units will have passed: time away adds to the age at once (counted in full up to the
    verified limit), so a moment within that limit is a real moment even with the game closed; past it, the rest
    needs play.  (moment or None, words)."""
    seconds = max(0.0, units) * ctx.unit
    if ctx.paused:
        return None, f"after {gm.duration(seconds)} of play once it is unpaused"
    if seconds <= full_away(ctx):
        moment = ctx.last + seconds
        if moment <= ctx.village.now:
            return moment, f"as soon as the village is next played (due {gm.when(moment)})"
        return moment, f"on {gm.when(moment)}"
    counted = gm.counted_away(ctx.game, ctx.village.now - ctx.last, ctx.speed) or 0.0
    if seconds <= counted:
        return None, "as soon as the village is next played (the time away counted covers it)"
    return None, (f"after about {gm.duration(seconds - counted)} more of play on {gm.speed_name(ctx.speed)} speed "
                  "once the time away counted is used")


def by_processed(ctx: Context, p: Person, units: float) -> tuple[float | None, str]:
    """When the processed age will have stepped `units` more: it first works off what time away has already added
    to the age (one age unit every 2 seconds of play, UNCONFIRMED), then runs at the speed."""
    lag = max(0, p.age - p.processed)
    if units <= lag:
        return None, (f"within about {gm.duration(units * CATCH_UP_STEP)} of play while the village catches up "
                      "(the time away is already counted)")
    return by_age(ctx, units - lag)


# ---------------------------------------------------------------------------
# Nursing and pregnancy
# ---------------------------------------------------------------------------


def _babies_words(n: int) -> str:
    return {1: "1 baby", 2: "twins", 3: "triplets"}.get(n, f"{n} babies")


def birth_wait(ctx: Context, p: Person) -> float:
    """Seconds of play from now until `p`'s babies are born, as by_processed times it: what time away has already
    added (her lag, and the time away counted if the village were played now) is worked off at CATCH_UP_STEP a unit,
    the rest at the speed's age unit."""
    left = max(0, p.conceived + BIRTH_UNITS - p.processed)
    if left == 0:
        return 0.0
    lag = max(0, p.age - p.processed)
    if left <= lag:
        return left * CATCH_UP_STEP
    rest = (left - lag) * ctx.unit
    counted = 0.0 if ctx.paused else (gm.counted_away(ctx.game, ctx.village.now - ctx.last, ctx.speed) or 0.0)
    if rest <= counted:
        return (lag + rest / ctx.unit) * CATCH_UP_STEP
    return (lag + counted / ctx.unit) * CATCH_UP_STEP + rest - counted


def nursing_lines(ctx: Context, everyone: list[Person]) -> tuple[list[gm.Fact], tuple[float | None, str] | None]:
    """Each mother carrying babies, and (the soonest birth's moment, its words)."""
    out: list[gm.Fact] = []
    mothers = [p for p in tribe(everyone) if p.carrying]
    outside = [p for p in everyone if p.heathen and p.carrying]
    add = lambda text, ok=False, sub=False, due=None, kind=None: out.append(  # noqa: E731
        gm.Fact(NURSING, text, ok, sub, due, kind))
    add("In every Virtual Villagers game being pregnant and nursing are one state: from the embrace that conceives, "
        "the mother carries her baby or babies (\"Nursing\" on the Details screen) until they are born on the 41st "
        "age unit of her processed age.", gm.OWNER)
    if ctx.game == 1:
        add("A New Home's Details screen counts one age unit fewer than the birth takes (\"Nursing for\" is 40 age "
            "units from conceiving, the birth comes on the 41st).", gm.RUNNING)
    if not mothers:
        add("Nobody is carrying a baby now.", gm.SAVE)
    soonest: tuple[float | None, str] | None = None
    best = None
    # In order of birth by the same catch-up-aware timing the lines give (not by units left alone: a mother further
    # from her birth but with time away still to work off can be born first).
    for p in sorted(mothers, key=lambda m: birth_wait(ctx, m)):
        left = max(0, p.conceived + BIRTH_UNITS - p.processed)
        if left == 0:
            moment, words = None, "at the next age unit the game steps (they are due)"
        else:
            moment, words = by_processed(ctx, p, left)
        father = f" by {p.father}" if p.father else ""
        # Built from the save and the verified 41-unit rule and time-away clamp; the catch-up pace is not verified.
        ok = gm.RUNNING if p.age <= p.processed else False
        add(f"{p.name}{father}: {_babies_words(p.babies)}; {left} age unit{'s' if left != 1 else ''} to go, born "
            f"{words}.", ok, due=moment, kind="due" if moment is not None else None)
        if ctx.game in DETAILS_UNITS:            # the Details screen's own sum (The Lost Children's is not traced)
            shown = max(0, p.conceived + DETAILS_UNITS[ctx.game] - p.processed) * ctx.speed
            out.append(gm.Fact(NURSING, f"The game's Details screen shows \"Nursing for: {shown} min\".", gm.RUNNING,
                               True))
        if best is None:
            best = (moment, f"{p.name}: {_babies_words(p.babies)}, born {words}")
    if best is not None:
        soonest = best
    if mothers:
        add("Then the babies are born as villagers of their own and the mother is free to conceive again. Her babies "
            "already count in the population while she carries them; if she dies or vanishes first, they are lost "
            "with her and leave no grave.", gm.OWNER)
        if ctx.game == 1:
            add("A New Home keeps no expected father on the mother's record.", gm.RUNNING)
    if outside:
        add(f"Outside the tribe (Heathens, not counted): {len(outside)} carrying.", gm.SAVE)
    return out, soonest


# ---------------------------------------------------------------------------
# Villager timers
# ---------------------------------------------------------------------------


def villager_lines(ctx: Context, everyone: list[Person]) -> list[gm.Fact]:
    out: list[gm.Fact] = []
    add = lambda text, ok=False, sub=False, due=None, kind=None: out.append(  # noqa: E731
        gm.Fact(VILLAGER_TIMERS, text, ok, sub, due, kind))
    people_ = [p for p in tribe(everyone) if not p.golden]
    on = gm.speed_name(ctx.speed)
    add(f"An age unit is {gm.duration(ctx.unit)} of play on {on} speed and a year {gm.duration(YEAR * ctx.unit)}; "
        "time away adds to the ages at once, as far as it counts.", gm.RUNNING)

    # Growing up.
    adult = 14 * YEAR
    children = sorted((p for p in people_ if p.age < adult), key=lambda p: -p.age)
    def growing(group: list[Person], at_years: int) -> None:
        """One sub-bullet for each age unit the villagers reach `at_years` in (namesakes of an age together)."""
        rows: dict[int, list[Person]] = {}
        for p in group:
            rows.setdefault(at_years * YEAR - p.age, []).append(p)
        for units in sorted(rows):
            moment, words = by_age(ctx, units)
            names = [p.name for p in rows[units]]
            who = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
            verb = "turns" if len(names) == 1 else "turn"
            out.append(gm.Fact(VILLAGER_TIMERS, f"{who}, {rows[units][0].years}: {verb} {at_years} {words}.", False,
                               True, moment, "due" if moment else None))

    if children:
        add(f"Children ({len(children)}): each works from 14 and can have children from {ctx.parents_from}.",
            gm.RUNNING if ctx.game == 1 else False)
        growing(children, 14)
    teens = sorted((p for p in people_ if adult <= p.age < ctx.parents_from * YEAR), key=lambda p: -p.age)
    if teens and ctx.parents_from > 14:
        add(f"Old enough to work, not yet to have children ({len(teens)}):", gm.RUNNING if ctx.game == 1 else False)
        growing(teens, ctx.parents_from)

    # Old age.
    if ctx.old_age_from:
        med = ctx.medicine
        if med in ctx.old_age_from:
            start = ctx.old_age_from[med]
            rolling = [p for p in people_ if p.processed >= start * YEAR]
            words = (f"Old-age rolls start at {start} years (Medicine level {med}): "
                     + (", ".join(f"{p.name} ({p.years})" for p in sorted(rolling, key=lambda q: -q.age))
                        + " roll each year" if rolling else "nobody is that old yet") + ".")
            add(words, gm.SAVE if not rolling else gm.RUNNING)
            nxt = sorted((p for p in people_ if p.processed < start * YEAR), key=lambda q: -q.processed)[:1]
            for p in nxt:
                moment, when_words = by_processed(ctx, p, start * YEAR - p.processed)
                out.append(gm.Fact(VILLAGER_TIMERS, f"Next to reach it: {p.name}, {when_words}.", False, True,
                                   moment, "starts" if moment else None))
        else:
            add("Old-age rolls start at " + ", ".join(f"{y} years at Medicine {m}" for m, y in ctx.old_age_from.items())
                + "; this save's Medicine level is not read here.", gm.RUNNING)
    if ctx.elderly_from and ctx.medicine in ctx.elderly_from:
        start = ctx.elderly_from[ctx.medicine]
        elders = [p for p in people_ if p.age >= start * YEAR]
        add(f"Elderly from {start} years (Medicine level {ctx.medicine}): {len(elders)} villager"
            f"{'s' if len(elders) != 1 else ''}; they regain health a fifth as often and fall sick more.", gm.RUNNING)

    # The sick.
    sick = [p for p in people_ if p.sick]
    if sick:
        high, low = ctx.sick_loss
        add(f"Sick ({len(sick)}): each loses 1 health on {high:.0%} of age units above 20 health and {low:.0%} at 20 or "
            "less, so if nobody cures them health lasts about the time below on average (an estimate)."
            + (f" {ctx.sick_end}" if ctx.sick_end else ""), gm.RUNNING)
        for p in sorted(sick, key=lambda q: q.health):
            units = max(0, p.health - 20) / high + min(p.health, 20) / low
            moment, words = by_processed(ctx, p, units)
            out.append(gm.Fact(VILLAGER_TIMERS, f"{p.name}: {p.health} health; at 0 {words} (an estimate).", False, True,
                               moment, "ends" if moment else None))
    else:
        add("Nobody is sick now.", gm.SAVE)

    # A New Home's Golden Child.
    for p in (q for q in everyone if q.golden):
        add(f"{p.name} is the Golden Child: always 5 years old (100 age units) and never older; never eats, starves, "
            "falls sick or dies of old age.", gm.RUNNING)

    # New Believers: faith.
    if ctx.game == 5:
        believers = tribe(everyone)
        heathens = [p for p in everyone if p.heathen]
        low = sorted((p for p in believers if p.faith is not None and p.faith <= 10), key=lambda q: q.faith)
        add("Faith: a believer becomes a Heathen at belief 0 or less; belief moves each age unit by food, sickness, "
            "the village's size, the Idol, the statue and Spirituality.", gm.RUNNING)
        if low:
            add("Believers at belief 10 or less: " + ", ".join(f"{p.name} ({p.faith})" for p in low) + ".", gm.SAVE)
        else:
            add("No believer is at belief 10 or less.", gm.SAVE)
        if heathens:
            top = sorted(heathens, key=lambda q: -(q.faith or -1000))[:5]
            add(f"Heathens outside the tribe: {len(heathens)}, never counted on this page. Highest belief (preaching "
                "adds 3 to 5, then that Heathen waits 2 hours): "
                + ", ".join(f"{p.name} ({p.faith})" for p in top) + ".", gm.SAVE)
    out.extend(ctx.villager_extra)
    return out


# ---------------------------------------------------------------------------
# Village timers
# ---------------------------------------------------------------------------


STORY_FILE = "Virtual Villagers {game} Story Purchases - Save {slot}.dat"
STORY_MAGIC = 0x31515356                     # 'V' 'S' 'Q' '1' (native/vvfp_story_upgrades/story_queue.inc)
STORY_ROSTER = 16 + 16                       # magic, version, game, slot, layout[4], then roster[256]
STORY_HAVE = STORY_ROSTER + 4 * 256          # then `have`
STORY_WHEN = STORY_HAVE + 8                  # then when[4], FILETIMEs (8-aligned after `have`)
SQ_PICK, SQ_CUSTOM, SQ_GONG, SQ_SKIP = 1, 2, 4, 8
SQ_BITS = (SQ_PICK, SQ_CUSTOM, SQ_GONG, SQ_SKIP)   # their when[] index, as sq_bit_index
FILETIME_UNIX = 11_644_473_600               # seconds from 1601 to 1970


def title_identity(game: int, data: bytes, at: int) -> int:
    """native/shared/custom_titles.h vv_title_identity of the saved villager whose name is at `at`: FNV-1a of the
    name to its NUL, 0xFF, then the likes' and the dislikes' bytes -- the roster key the queue file keeps."""
    import vv_last_names as ln
    f = ln.FIELDS[game]
    h = 2166136261
    for b in data[at:at + f.name_cap]:
        if b == 0:
            break
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    h = ((h ^ 0xFF) * 16777619) & 0xFFFFFFFF
    h = h or 1
    for b in data[at + f.likes:at + f.likes + 4 * f.slots] + data[at + f.dislikes:at + f.dislikes + 4 * f.slots]:
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h or 1


def story_queue(village: gm.Village) -> tuple[int, Path] | None:
    """The patcher's queued Story / Cheat purchases that the companion would deliver into this save (Pick Island
    Event, Custom Island Event, Pick Gong of Wonder Outcome, Choose Time Skip Amount): (the SQ_* bits still in
    force, the file), or None when there is no such file.  As story_queue.inc's restore decides it: the file is
    this game's and slot's; its roster shares a strict majority with the save's villagers (sq_same_village; another
    village's file -- an older save or another village restored into the slot -- counts for nothing); and an item
    bought after the save was last written was never paid for in it (sq_restore) and is dropped.  Read only."""
    try:
        import vv_last_names as ln
        import vv_save_layout as layout
        path = layout.route(Path(village.folder), f"{layout.DATA}\\Paid Purchases\\"
                            + STORY_FILE.format(game=village.game, slot=village.slot))
        data = path.read_bytes()
        saved = village.save.stat().st_mtime
    except (OSError, ValueError, AttributeError):
        return None
    if len(data) < STORY_WHEN + 8 * len(SQ_BITS):
        return None
    magic, _version, game, slot = struct.unpack_from("<4I", data, 0)
    if magic != STORY_MAGIC or game != village.game or slot != village.slot:
        return None
    try:
        now = {title_identity(game, village.data, at) for at in ln._entries(game, village.data, bodies=True)}
    except Exception:  # noqa: BLE001 -- no villagers to match: not this village's queue
        return 0, path
    was = [v for v in struct.unpack_from("<256I", data, STORY_ROSTER) if v]
    if not was or sum(1 for v in was if v in now) * 2 <= len(was):
        return 0, path
    have = struct.unpack_from("<I", data, STORY_HAVE)[0]
    saved_ft = int((saved + FILETIME_UNIX) * 10_000_000)
    for k, bit in enumerate(SQ_BITS):
        if have & bit and struct.unpack_from("<Q", data, STORY_WHEN + 8 * k)[0] > saved_ft:
            have &= ~bit                       # newer than the save: never paid for there
    return have, path


def village_lines(ctx: Context) -> tuple[list[gm.Fact], tuple[float | None, str]]:
    out: list[gm.Fact] = []
    add = lambda text, ok=False, sub=False, due=None, kind=None: out.append(  # noqa: E731
        gm.Fact(VILLAGE_TIMERS, text, ok, sub, due, kind))
    # The next natural island event.
    queue = story_queue(ctx.village)
    blocked = queue is not None and queue[0] & (SQ_PICK | SQ_CUSTOM)
    if queue is not None:
        ctx.village.notes.append(f"Read: {queue[1]}.")
    if ctx.paused and ctx.event_paused_left is not None:
        event = (None, f"after {gm.duration(ctx.event_paused_left)} of play once unpaused")
    elif ctx.event_next is not None:
        event = (ctx.event_next, gm.when(ctx.event_next) + (" (when the village is next played)"
                                                             if ctx.event_next <= ctx.village.now else ""))
    else:
        event = (None, "not read")
    if blocked:
        # The owner: a Custom or Picked island event is never listed here, only that one delays the natural one.
        add("A purchased island event is pending and delays the natural one, which is timed afresh after it.",
            gm.SAVE)
        event = (None, "after a pending purchased event, timed afresh then")
    else:
        add(f"Next natural island event: {event[1]}.", gm.SAVE, due=event[0], kind="next" if event[0] else None)
    if ctx.event_rule:
        out.append(gm.Fact(VILLAGE_TIMERS, ctx.event_rule, gm.RUNNING, True))
    if ctx.event_running:
        out.append(gm.Fact(VILLAGE_TIMERS, ctx.event_running, False, True))
    if queue is not None and queue[0] & SQ_SKIP:
        add("A Choose Time Skip Amount purchase is still under way (the patcher's queued purchases file).", gm.SAVE)

    # Puzzles under way.
    if ctx.puzzles:
        add("Puzzles under way: " + "; ".join(f"{name} {got} of {need}" for name, got, need in ctx.puzzles) + ".",
            gm.SAVE)
    out.extend(ctx.village_extra)
    return out, event


# ---------------------------------------------------------------------------
# Vital statistics
# ---------------------------------------------------------------------------


def eat_per_unit(ctx: Context, food: int | None = None) -> float:
    """Food one villager eats an age unit on average at the save's difficulty and food store."""
    food = ctx.food if food is None else food
    level = ctx.difficulty
    extra = 0.0
    if level == 2 or (level == 1 and food >= ctx.extra_from):
        extra = 0.76 * 2
    return 2.0 + extra


def vitals_lines(ctx: Context, everyone: list[Person] | None, soonest, event) -> list[gm.Fact]:
    out: list[gm.Fact] = []
    add = lambda text, ok=False, sub=False, due=None, kind=None: out.append(  # noqa: E731
        gm.Fact(VITALS, text, ok, sub, due, kind))
    sub = lambda text, ok=False, due=None, kind=None: add(text, ok, True, due, kind)  # noqa: E731
    on = gm.speed_name(ctx.speed)
    level = ctx.difficulty
    level_words = DIFFICULTY.get(level, "not read") if level is not None else "not read"

    # 1. The game's speed, difficulty and time away -- every figure below uses them.
    away = max(0.0, ctx.village.now - ctx.last)
    counted = 0.0 if ctx.paused else (gm.counted_away(ctx.game, away, ctx.speed) or 0.0)
    add(f"Speed {on}" + (" (saved paused)" if ctx.paused else "") + f"; difficulty {level_words}; last saved "
        f"{gm.when(ctx.last)}, {gm.duration(away)} ago, of which {gm.duration(counted)} would count if it were "
        "played now. Every figure below is at this speed and difficulty.", gm.SAVE)

    # 2. Food and its sources.
    add(f"Food in storage: {ctx.food:,}.", gm.SAVE)
    for s in ctx.sources:
        amount = "" if s.amount is None else f"{s.amount:,}" + (f" of {s.cap:,}" if s.cap else "")
        text = f"{s.name}: {amount}" if amount else s.name
        if s.next_refill is not None:
            text += f"; next refill {gm.when(s.next_refill)}"
        elif s.refill_words:
            text += f"; {s.refill_words}"
        sub(text + ".", s.verified, due=s.next_refill, kind="refill" if s.next_refill else None)

    # 3. Tech points and collectibles.
    if ctx.tech is not None:
        add(f"Tech points: {ctx.tech:,}." + (f" {ctx.tech_words}" if ctx.tech_words else ""), gm.SAVE)
    for text, ok in ctx.collectibles:
        add(text, ok)

    # 4. Mushrooms.
    avg = (1 - ctx.red_share) * ctx.brown + ctx.red_share * ctx.red
    golden = " and 1 in 1,000,000 a Golden Mushroom worth 100" if ctx.golden else ""
    add(f"Mushrooms: brown worth {ctx.brown * ctx.mastery:g} food, red (rare) {ctx.red * ctx.mastery:g}, "
        f"{ctx.red_share:.0%} of them red{golden}." + (f" {ctx.mushroom_words}" if ctx.mushroom_words else ""),
        gm.RUNNING)

    # 5. The next natural island event and the soonest birth.
    add(f"Next natural island event: {event[1]}.", gm.SAVE, due=event[0], kind="next" if event[0] else None)
    if soonest is not None:
        add(f"Soonest birth: {soonest[1]}.", False, due=soonest[0], kind="due" if soonest[0] else None)
    elif everyone is not None:
        add("Soonest birth: nobody is carrying a baby.", gm.SAVE)

    # 6. Population and its limit.
    if everyone is None:
        add("Population: the villager table could not be read.", gm.SAVE)
        return out + list(ctx.vitals_extra)
    members = tribe(everyone)
    babies = sum(p.babies for p in members if p.carrying)
    heathens = len(everyone) - len(members)
    words = f"Population: {len(members)} villager{'s' if len(members) != 1 else ''}"
    if babies:
        words += f" and {babies} bab{'ies' if babies != 1 else 'y'} on the way ({len(members) + babies} in all, as the game counts it)"
    add(words + ".", gm.SAVE)
    if ctx.limit is not None:
        sub(ctx.limit[0][0].upper() + ctx.limit[0][1:] + ".", ctx.limit[1])
    if heathens:
        sub(f"Heathens outside the tribe: {heathens}, left out of every count and total on this page.", gm.SAVE)
    out.extend(ctx.vitals_extra)

    # 7. Food sustainability (estimates).
    out.extend(food_estimates(ctx, members))
    return out


def food_estimates(ctx: Context, members: list[Person]) -> list[gm.Fact]:
    out: list[gm.Fact] = []
    add = lambda text, sub=False, ok=False: out.append(gm.Fact(VITALS, text, ok, sub))  # noqa: E731
    on = gm.speed_name(ctx.speed)
    mothers = [p for p in members if p.carrying]
    eaters_now = [p for p in members if not p.golden]
    eaters = len(eaters_now) + len(mothers)      # each nursing mother and her babies counted as 2 (the owner)
    per_unit = eat_per_unit(ctx)
    units_hour = 3600.0 / ctx.unit
    per_hour = eaters * per_unit * units_hour
    level = ctx.difficulty
    add(f"Food estimates (estimates, not the game's own figures), on {on} speed at difficulty "
        f"{DIFFICULTY.get(level, 'not read') if level is not None else 'not read'}:")
    add(f"Population for food: {eaters} -- {len(eaters_now)} who eat, each nursing mother and her baby or babies "
        f"counted as 2 ({len(mothers)} mother{'s' if len(mothers) != 1 else ''})"
        + ("; the Golden Child never eats" if any(p.golden for p in members) else "")
        + ("; Heathens outside the tribe never eat" if ctx.game == 5 else "") + ".", True, gm.SAVE)
    add(f"Eating: {ctx.food_words} That is {per_unit:g} food a villager each age unit now, "
        f"{per_unit * units_hour:g} an hour on {on} speed.", True, gm.RUNNING)
    add(f"Food eaten: about {per_hour:,.0f} an hour.", True)
    stay = ctx.low_food + 1
    for hours in (8, 24):
        add(f"Food needed for 100% health over {hours} hours of play: about {per_hour * hours + stay:,.0f} "
            f"(eating, plus staying above {ctx.low_food:,}).", True)
    add(f"100% health needs: more than {ctx.low_food:,} food at every age unit (at or below it meals are skipped and "
        "health is lost), no sickness, and time: a healthy villager regains 1 health on about half the age units.",
        True, gm.RUNNING)

    refill_unit = sum(s.per_unit for s in ctx.sources) * ctx.mastery
    refill_hour = refill_unit * units_hour
    on_sources = int(sum(max(0, s.amount or 0) for s in ctx.sources if not s.unlimited) * ctx.mastery)
    add(f"Refills: about {refill_hour:,.0f} food an hour back on the sources"
        + (f" (Food Mastery x{ctx.mastery:g})" if ctx.mastery != 1 else "") + "; "
        + ("; ".join(f"{s.name} {s.per_unit * units_hour * ctx.mastery:,.0f}" for s in ctx.sources if s.per_unit)
           or "none refill") + ".", True)
    if per_hour > 0:
        hours_store = ctx.food / per_hour
        add(f"Storage alone lasts about {gm.duration(hours_store * 3600)} of play"
            + (f", to about {gm.when(ctx.village.now + hours_store * 3600)} if played from now" if not ctx.paused else "")
            + ".", True)
        net = per_hour - refill_hour
        total = ctx.food + on_sources
        if net > 0:
            add(f"With the food still on the sources ({on_sources:,}) and their refills: about "
                f"{gm.duration(total / net * 3600)} of play.", True)
        else:
            add(f"With the food still on the sources ({on_sources:,}): the refills keep up with the eating, so it "
                "lasts while gatherers bring it in.", True)
    per_villager_unit = per_unit
    if per_villager_unit:
        add(f"Sustainable population on the refills alone: about {refill_unit / per_villager_unit:,.1f} villagers "
            f"(refills {refill_unit:,.2f} food an age unit, each villager eats {per_villager_unit:g})"
            + ("; fishing adds without limit, as far as the gatherers bring it" if any(s.unlimited for s in ctx.sources)
               else "") + ".", True)
    gap = per_hour - refill_hour
    if gap > 0:
        brown, red = ctx.brown * ctx.mastery, ctx.red * ctx.mastery
        line = (f"To fill the gap of about {gap:,.0f} food an hour: {gap / brown:,.0f} brown or {gap / red:,.0f} red "
                f"mushrooms an hour ({gap * 24 / brown:,.0f} or {gap * 24 / red:,.0f} a day)")
        if ctx.golden:
            line += f", or {gap / (100 * ctx.mastery):,.1f} Golden Mushrooms"
        if ctx.mushrooms_an_hour is not None:
            supply = ctx.mushrooms_an_hour * ((1 - ctx.red_share) * brown + ctx.red_share * red)
            line += (f"; random mushrooms bring at most about {supply:,.0f} an hour while playing, which "
                     + ("covers it." if supply >= gap else "does not cover it."))
        else:
            line += "."
        add(line, True)
    else:
        add("The refills cover the eating: no mushrooms are needed.", True)
    trips = [(name, food * ctx.mastery) for name, food in ctx.trips if food > 0]
    if trips and per_hour > 0:
        add("Gatherers: to bring in what is eaten takes about " + ", or ".join(
            f"{per_hour / food:,.0f} {name} an hour ({food:g} each)" for name, food in trips)
            + "; a trip's length depends on walking, so the number of gatherers this needs is not worked out.", True)
    if ctx.gatherer_words:
        add(ctx.gatherer_words, True)
    add("How many villagers gather now is not kept in the save.", True, gm.SAVE)

    # Time away: the closed-game estimates.
    if ctx.paused:
        add("Saved paused: no time away is counted, so nothing is eaten while the game is closed.", True, gm.RUNNING)
    else:
        for hours in (8, 24):
            counted = gm.counted_away(ctx.game, hours * 3600, ctx.speed) or 0.0
            eaten = eaters * per_unit * counted / ctx.unit
            add(f"Closed for {hours} hours: {gm.duration(counted)} counts, so about {eaten:,.0f} food is eaten while "
                f"catching up (gatherers bring some back meanwhile); refills missed while closed are all added.",
                True)
    return out


# ---------------------------------------------------------------------------
# The population limit and the collectibles
# ---------------------------------------------------------------------------

# Each game's base cap before collections (data/builds.json's patch modes and docs/max-population-research.md).
STOCK_BASE = {1: 90, 2: 90, 3: 90, 4: 90, 5: 90}
PROGRESSION_BASE = {1: 256, 2: 231, 3: 115, 4: 125, 5: 135}
POP_256 = {3: "vv3_population_256", 4: "vv4_population_256", 5: "vv5_population_256"}


def population_mode(village: gm.Village) -> str | None:
    """Which of the patcher's population modes the game's exe has ("stock", "collection_progression",
    "immediate_fixed"), from its own bytes at the places data/builds.json records; None when the exe is not
    known or none matches."""
    if village.exe is None:
        return None
    try:
        import json
        builds = json.loads((Path(__file__).resolve().parents[1] / "data" / "builds.json").read_text(encoding="utf-8"))
        game = next(g for g in builds["games"] if g["id"] == f"vv{village.game}")
        exe = Path(village.exe).read_bytes()
    except (OSError, ValueError, StopIteration, KeyError):
        return None
    for mode in ("immediate_fixed", "collection_progression"):
        patches = game["variants"].get(mode, {}).get("patches") or []
        if patches and all(exe[int(p["offset"], 16):int(p["offset"], 16) + len(bytes.fromhex(p["after"]))]
                           == bytes.fromhex(p["after"]) for p in patches):
            return mode
    patches = game["variants"].get("collection_progression", {}).get("patches") or []
    if patches and all(exe[int(p["offset"], 16):int(p["offset"], 16) + len(bytes.fromhex(p["before"]))]
                       == bytes.fromhex(p["before"]) for p in patches):
        return "stock"
    return None


def limit_words(village: gm.Village, bonus: int | None, bonus_words: str, stock_extra: str = "") -> tuple[str, bool | str]:
    """The population limit's words: the mode the exe has, the 256 Villagers patch, and the collection bonus when
    the save tells it (`bonus`, points), else the rule (`bonus_words`)."""
    game = village.game
    mode = population_mode(village)
    big = POP_256.get(game)
    if big and village.has(big):
        return "the limit is up to 256 with the patcher's \"256 Villagers (Experimental)\"", False
    if mode == "immediate_fixed":
        cap = 256 if game <= 2 else 150
        return f"the limit is {cap} (the patcher's Immediate Fixed Max Pop, read from the exe)", gm.SAVE
    base = PROGRESSION_BASE[game] if mode == "collection_progression" else STOCK_BASE[game]
    mode_words = ("the patcher's Collection Progression Max Pop, read from the exe" if mode == "collection_progression"
                  else "the stock limit, read from the exe" if mode == "stock"
                  else "the stock rule; which population mode the exe has is not known")
    top = 256 if game <= 2 else 150
    if bonus is not None:
        cap = min(top, base + bonus) if mode == "collection_progression" else base + bonus
        return f"the limit is {cap}: {base} plus {bonus} for collections ({mode_words}){stock_extra}", False
    return f"the limit is {base} plus {bonus_words} ({mode_words}){stock_extra}", False


# The later games' collectibles: the item manager's 51 dwords the save writer copies first (VV3 0x42D460, VV4
# 0x4137C0, VV5 0x413B80), 48 of them how many of each piece were found, duplicates included (the owner's saves:
# counts of 1 to 35).  The Tree of Life's four sets of 12 in this order (the owner's Cheat Engine work,
# native/vv4_origins_icons: "Fish Scales, Lab Pieces, Mausoleum, Wind Flutes"); the other games' order of the
# pieces is not worked out, so they are given as totals.  File offsets of the block.
COLLECTIBLES_AT = {3: 0x370 + 12, 4: 0x6DC + 0x10, 5: 0x640 + 0x10}
VV4_SETS = ("Fish Scale", "Lab Equipment", "Mausoleum Mural", "Wind Flute")


def collectible_counts(village: gm.Village) -> list[int] | None:
    at = COLLECTIBLES_AT.get(village.game)
    if at is None or at + 48 * 4 > len(village.data):
        return None
    counts = list(struct.unpack_from("<48i", village.data, at))
    return counts if all(0 <= c < 1_000_000 for c in counts) else None


def collectible_lines(village: gm.Village, duplicate_words: str) -> tuple[list[tuple[str, bool | str]], int | None]:
    """The lines for Vital statistics, and the complete sets (The Tree of Life only; None otherwise)."""
    counts = collectible_counts(village)
    if counts is None:
        return [("Collectibles owned: not read from this save.", gm.SAVE)], None
    owned = sum(1 for c in counts if c > 0)
    found = sum(counts)
    lines = [(f"Collectibles: {owned} of 48 pieces owned; {found:,} found in all, {found - owned:,} of them "
              f"duplicates, which pay {duplicate_words} by rarity.", gm.SAVE)]
    complete = None
    if village.game == 4:
        sets = [counts[12 * k:12 * k + 12] for k in range(4)]
        complete = sum(1 for s in sets if all(c > 0 for c in s))
        lines.append(("By set: " + "; ".join(f"{name} {sum(1 for c in s if c > 0)} of 12 ({sum(s) - sum(1 for c in s if c > 0)} "
                                             "duplicates)" for name, s in zip(VV4_SETS, sets)) + ".", gm.OWNER))
    return lines, complete


# ---------------------------------------------------------------------------
# The claims export's shape of a line (scripts/export_game_mechanics_claims.py): villagers' names left out
# ---------------------------------------------------------------------------

import re as _re

_NAME_LISTS = _re.compile(r"(?<=: )[^:;()]+? \(-?[\d,]+\)(?:, [^:;()]+? \(-?[\d,]+\))*")
_STARTS = (
    (_re.compile(r"^(Soonest birth: )[^:]+?(?=: (?:1 baby|twins|triplets))"), r"\1<villager>"),
    (_re.compile(r"^[^:]+? by [^:]+?(?=: (?:1 baby|twins|triplets);)"), "<villager> by <villager>"),
    (_re.compile(r"^[^:]+?(?=: (?:1 baby|twins|triplets);)"), "<villager>"),
    (_re.compile(r"^[^:]+?, (\d+): turns? "), r"<villagers>, \1: turn(s) "),
    (_re.compile(r"^[^:]+?(?=: -?\d+ health; )"), "<villager>"),
    (_re.compile(r"^.+?(?= is the Golden Child: )"), "<villager>"),
    (_re.compile(r"^(Next to reach it: )[^,]+?(?=, )"), r"\1<villager>"),
)


def claim_template(text: str) -> str:
    """`text` with the villagers' names this module writes replaced by <villager> / <villagers>."""
    for pattern, place in _STARTS:
        new = pattern.sub(place, text, count=1)
        if new != text:
            text = new
            break
    return _NAME_LISTS.sub("<villagers>", text)


# ---------------------------------------------------------------------------
# The groups
# ---------------------------------------------------------------------------


def sections(ctx: Context) -> list[gm.Fact]:
    """The four groups for one save; nothing for a game's general page (no save)."""
    if ctx.village.general:
        return []
    everyone = people(ctx.village)
    out: list[gm.Fact] = []
    soonest = None
    if everyone is not None:
        nursing, soonest = nursing_lines(ctx, everyone)
        out += nursing
        out += villager_lines(ctx, everyone)
    else:
        out.append(gm.Fact(NURSING, "The villager table could not be read.", gm.SAVE))
    village, event = village_lines(ctx)
    out += village
    out = vitals_lines(ctx, everyone, soonest, event) + out
    return out
