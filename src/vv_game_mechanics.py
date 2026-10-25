"""Game Mechanics (the Tools tab's window, src/vv_game_mechanics_window.py): one save's hidden rules.

For the curious, and read-only: for the tribe chosen in the window, each game's own module
(src/vv_game_mechanics_vv<N>.py) reads the slot's save -- and the patcher's per-save files that
change a rule -- and returns plain-words lines, each a fact of this village (an amount now, the next
time something happens) together with its rule (a rate or an interval at the save's game speed and
techs, and the patcher's patches in the game that change it).  The lines are grouped as GROUPS.

Nothing here writes anything: no save, log, data file or backup is created or changed, so the page
may be read with the game running (it then shows the save as it was last written).

TIME.  Every time is real time.  The games count their own clock in game seconds; at Normal speed a
game second is a real second, at Fast two pass each real second and at Slow 0.6 (the games' speed
value -- 3 Fast, 6 Normal, 10 Slow -- is real seconds per 6 game seconds).  A game rule of N game
seconds therefore takes N * speed / 6 real seconds.  Paused (the speed plus 999) stops the clock.

A GAME'S MODULE is found by name (vv_game_mechanics_vv<N>) and has
    facts(village: Village) -> list[Fact]
It raises nothing for a save it cannot read: it returns a Fact saying what could not be read.

LIVE COUNTDOWNS (the owner, 2026-10-24; docs/game-mechanics-window.md).  A Fact whose moment is a
real time still to come -- a refill, a crop ready, an event that ends -- may carry
    due:      that moment, absolute real time in Unix seconds (work it out from village.now and the
              save's clock), or None;
    due_kind: what happens then, in one word: "refill", "ready", "ends", "due", ... (DUE_KINDS).
The page then shows the moment's date and time and, right after it on the same bullet, a live
countdown -- "24 October 2026, 3:14 PM (in 12 min 03 s)" -- that the window ticks every second from
ONE shared timer, without reading any file again.  At zero it reads "..., due now (refresh to see
the new state)": the game's own state is only known again from the save.  Where the date goes:
  * the text holds DUE ("{due}"): the date and countdown go there, e.g.
        Fact("Refills", f"Honey: 40 of 100; the next refill is {gm.DUE}.", SAVE, due=t, due_kind="refill");
  * otherwise, when the text already holds when(due), the countdown goes right after it;
  * otherwise "<Kind>: <date> (countdown)." is added at the end ("Next refill: ...", "Ready: ...").
A fact whose clock is stopped (the save was written paused, a frozen clock) passes due=None and
keeps its own words ("once unpaused"); it gets no countdown.  render(facts) gives the text as it
reads at `now`; render_live(facts, now) also gives each countdown's place (Countdown) for the window.
A fact with a due is left out of a game's general rules (general()), which have no village.
"""
from __future__ import annotations

import importlib
import math
import re
import struct
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

TITLE = "Game Mechanics"
# Vital statistics first (the owner, 2026-10-24), then where the page's facts come from, then the village's people
# and clocks (src/vv_game_mechanics_life.py), then the rules.
GROUPS = ("Vital statistics", "Sources", "Nursing and pregnancy", "Villager timers", "Village timers", "Food sources", "Refills", "Mushrooms", "Collectibles", "Tech points and effects",
          "God powers", "Food earned", "Time away and Time Warp", "Island events", "Puzzles", "Golden Child",
          "Hidden villager stats", "Chance and timers", "Other")
PUZZLES = "Puzzles"
GOLDEN_CHILD = "Golden Child"                 # A New Home only: vv_game_mechanics_vv1.golden_child_facts
# Every fact is a bullet under its heading; a sub-fact (a tree's planting, its fruit, ...) an indented dash under
# the fact before it (the owner, 2026-10-23: "bullet point everything ... for easier legibility").
BULLET, SUB_BULLET = "• ", "    – "
# The label every unverified line carries, in capitals, right beside it (the owner, 2026-10-23), and the
# line at the top of the window that explains it.
UNCONFIRMED = "UNCONFIRMED"
LABEL_NOTE = ("UNCONFIRMED marks anything not yet confirmed by the owner in a game, or verified from the "
              "game's own code as the game itself runs it. Lines without it are values read straight from the "
              "save, or confirmed that way.")
# What lets a line go without the label (the owner, 2026-10-23, binding): a value read straight from the save,
# a rule the owner confirmed in a game, or the time-away clamp and Time Warp verified on the games' own aging
# path.  A rule only emulated in isolation by the research (a spec's VERIFIED) is NOT enough: it is shown
# UNCONFIRMED until its reach from the game's own call paths is shown.
# RUNNING: emulated AND traced from the game's own call paths with inputs the game supplies (a research
# spec's reachability re-check, e.g. The Secret City's addendum 3).
SAVE, OWNER, CLAMP, RUNNING = "save", "owner", "clamp", "running"
TRUSTED = frozenset({SAVE, OWNER, CLAMP, RUNNING})

# The games' speed values (src/vv_save_backup.py, "GAME SPEED"): real seconds per 6 game seconds.
FAST, NORMAL, SLOW = 3, 6, 10
PAUSED = 999
SPEED_NAMES = {FAST: "Fast", NORMAL: "Normal", SLOW: "Slow"}

# The game folder's transparency report lists each patch in the game:
# "- Optional feature: <name> [<id>]" (src/transparency.py); src/vv_move_old_names.py reads the same file.
TRANSPARENCY = ("Virtual Villagers Fun Patcher Files\\VVFP Transparency Log.txt", "VVFP Transparency Log.txt")
_FEATURE = re.compile(r"^- Optional feature: .* \[([a-z0-9_]+)\]\s*$", re.M)

_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
           "October", "November", "December")


@dataclass(frozen=True)
class Fact:
    """One line of the page.  `verified` says what stands behind it: SAVE, OWNER or CLAMP (see TRUSTED) let it
    go without the label; True (a research spec's isolated emulation) or False does not -- it is shown with
    UNCONFIRMED.  A line is unconfirmed unless it says otherwise.  `sub`: shown as a sub-bullet of the fact
    before it.  `due` / `due_kind`: a real moment still to come and what happens then, for the live countdown
    (see LIVE COUNTDOWNS in the module docstring); None when the clock is stopped or there is none."""
    group: str
    text: str
    verified: bool | str = False
    sub: bool = False
    due: float | None = None
    due_kind: str | None = None

    @property
    def confirmed(self) -> bool:
        return self.verified in TRUSTED


@dataclass
class Village:
    """One save slot, read once.  `installed` is the set of the patcher's feature ids in the game
    that writes this save folder, or None when that game's folder (and its report) was not found."""
    folder: Path
    game: int
    slot: int
    save: Path
    data: bytes
    installed: frozenset[str] | None
    now: float                      # the real time the section is shown at (Unix seconds)
    notes: list[str] = field(default_factory=list)
    certain: bool = True            # a patch missing from installed is known to be out (False: only not seen)
    exe: Path | None = None         # the game's executable as found (patch_source), when one was
    general: bool = False           # a game's general rules page (no save): nothing read from a save is shown

    def has(self, feature: str) -> bool | None:
        if self.installed is None:
            return None
        return True if feature in self.installed else (False if self.certain else None)


# ---------------------------------------------------------------------------
# Words
# ---------------------------------------------------------------------------


def when(seconds: float) -> str:
    """A real moment as the owner reads it: "22 October 2026, 3:14 PM" (local time)."""
    moment = datetime.fromtimestamp(seconds)
    hour = moment.hour % 12 or 12
    return f"{moment.day} {_MONTHS[moment.month - 1]} {moment.year}, {hour}:{moment.minute:02d} " \
           f"{'AM' if moment.hour < 12 else 'PM'}"


def duration(seconds: float, exact: bool = False) -> str:
    """A real length of time in words: "3 hours", "1 hour 30 minutes", "45 minutes", "20 seconds" --
    to the minute, or `exact` to the second (a rule like "8 hours 36 minutes 40 seconds")."""
    seconds = int(round(seconds))
    if seconds < 60:
        return _plural(seconds, "second")
    if exact and seconds % 60:
        return f"{duration(seconds - seconds % 60)} {_plural(seconds % 60, 'second')}"
    minutes = (seconds + 30) // 60
    days, rest = divmod(minutes, 24 * 60) if minutes > 24 * 60 else (0, minutes)
    hours, minutes = divmod(rest, 60)
    parts = [_plural(n, unit) for n, unit in ((days, "day"), (hours, "hour"), (minutes, "minute")) if n]
    return " ".join(parts)


def _plural(n: int, unit: str) -> str:
    return f"{n} {unit}" if n == 1 else f"{n} {unit}s"


def speed_base(value: int) -> int:
    """The speed a save runs at once unpaused (the value less 999 while paused)."""
    return value - PAUSED if value >= PAUSED else value


def speed_name(value: int) -> str:
    return SPEED_NAMES.get(speed_base(value), f"speed {speed_base(value)}")


def real_seconds(game_seconds: float, speed: int) -> float:
    """How long `game_seconds` of the game's clock take in real time at `speed` (3, 6 or 10)."""
    return game_seconds * speed_base(speed) / NORMAL


def every(game_seconds: float, speed_value: int) -> str:
    """"every 3 hours on Normal speed" -- or, for a save written paused, "... once unpaused" (the owner,
    2026-10-22: real time only; a game's module also says once that a paused save waits, PAUSED_NOTE)."""
    base = speed_base(speed_value)
    text = f"every {duration(real_seconds(game_seconds, base))} on {speed_name(base)} speed"
    return f"{text} once unpaused" if speed_value >= PAUSED else text


PAUSED_NOTE = "The game was saved paused: nothing refills or grows until it is unpaused."


# ---------------------------------------------------------------------------
# Time away (catch-up)
# ---------------------------------------------------------------------------

# How much time away each game counts, per game -- ONLY figures verified by emulating the game's own
# clamp (the coordinator's clamp verification; the research specs disagreed): {"full": {speed: real
# seconds counted in full}, "band_end": real seconds, "band": counted in the band, "over": counted past
# it}.  A game not listed here shows that its limits are not yet confirmed, never a guessed figure.
#
# VERIFIED (2026-10-23, the coordinator's emulation of each game's own clamp, identical in all five):
# pending += away; over 86,400 s it becomes 86,400 and the speed band is skipped; otherwise Fast keeps
# up to 38,200 s else 31,000, Normal at most 31,000, Slow up to 23,800 s else 31,000; paused gives 0.
_VERIFIED_AWAY = {"full": {FAST: 38_200, NORMAL: 31_000, SLOW: 23_800}, "band_end": 86_400, "band": 31_000,
                  "over": 86_400}
AWAY_LIMITS: dict[int, dict] = {game: _VERIFIED_AWAY for game in range(1, 6)}
TIME_AWAY = "Time away and Time Warp"
# The Origins Time Warp (every game, verified the same way): years credited per warp, by speed.  The
# patcher's Expanded warps differ and are not shown until the owner settles them.
TIME_WARP_YEARS = {FAST: 12, NORMAL: 6, SLOW: 3}


def time_warp_line(speed_value: int) -> Fact:
    speed = speed_base(speed_value)
    return Fact(TIME_AWAY, (
        f"Time Warp (the Origins upgrade): each one gives the villagers {TIME_WARP_YEARS[speed]} years on "
        f"{speed_name(speed)} speed (12 on Fast, 6 on Normal, 3 on Slow), past the time-away limits; not while "
        "paused."), CLAMP)


def old_age_line(thresholds: str, extra: str = "") -> Fact:
    """The verified old-age rule (2026-10-23, all five games, emulated and checked against the owner's logs):
    a death roll at each whole year past the threshold in the hidden processed age."""
    return Fact("Other", (
        f"Old age: at each whole year past {thresholds}, a death roll whose chance is 10% for each year over (100% "
        "at 10 years over). The roll follows a hidden processed age: time away adds to the age shown in the game, "
        "logs and graves at once, while the processed age catches up a step at a time, so the shown age can be "
        "higher, by up to about 12 years after a long time away." + (f" {extra}" if extra else "")), RUNNING)


HIDDEN = "Hidden villager stats"
# How a villager gets its head and body (src/vv_game_mechanics_genetics.py, the owner 2026-10-24), shown right
# after the hidden villager stats.
GENETICS = "Genetics"
GROUPS = GROUPS[:GROUPS.index(HIDDEN) + 1] + (GENETICS,) + GROUPS[GROUPS.index(HIDDEN) + 1:]


def genetics_facts(village: "Village") -> list[Fact]:
    """The Genetics group for `village` (found by name, as each game's module is)."""
    return list(importlib.import_module("vv_game_mechanics_genetics").facts(village))


def starvation_lines(village: "Village", delta: int, basis: str, totem_colour: bool = False) -> list[Fact]:
    """Each living villager's hidden starvation number (a value the game rolls at creation and keeps in the
    save, `delta` bytes before the villager's name in its record) and what it means for them: a multiple of
    6 loses health on every age unit without food, any other escapes 24% of them (never on Hard); an odd one
    at 20 health or less regains 1 after the loss 31% of the time.  Read only."""
    try:
        import vv_last_names
        roster = vv_last_names.living(village.folder, village.game, village.slot)
    except Exception:  # noqa: BLE001 -- a villager table that cannot be read gives no per-villager lines
        return []
    out = []
    for villager in roster:
        if not 0 <= villager.at - delta <= len(village.data) - 4:
            continue
        number = struct.unpack_from("<i", village.data, villager.at - delta)[0]
        words = ("every age unit without food costs 1 health" if number % 6 == 0 else
                 "escapes the health loss on 24% of age units without food (never on Hard)")
        if number % 2:
            words += "; at 20 health or less, regains 1 after a loss 31% of the time"
        colour = f" (totem colour {number % 8})" if totem_colour else ""
        out.append(Fact(HIDDEN, f"{villager.name}: hidden number {number}{colour} -- {words}.", basis))
    return out


def counted_away(game: int, seconds: float, speed: int) -> float | None:
    """How much of `seconds` away `game` counts at `speed`, or None while its limits are not confirmed."""
    limits = AWAY_LIMITS.get(game)
    if limits is None:
        return None
    seconds = max(0.0, seconds)
    if seconds <= limits["full"].get(speed, limits["full"][NORMAL]):
        return seconds
    return limits["band"] if seconds <= limits["band_end"] else limits["over"]


def time_away(village: "Village", last: float, speed_value: int, paused_words: str,
              unit_seconds: float | None = None) -> list[Fact]:
    """The time-away lines every game shares: when the save was last played, its speed or pause, how much
    of the time since then would count if it were opened now, and the rule -- the rule only from
    AWAY_LIMITS.  `unit_seconds`: a year's real length at this speed, to say the counted time in years."""
    speed = speed_base(speed_value)
    paused = speed_value >= PAUSED
    out = [Fact(TIME_AWAY, f"Last saved: {when(last)}, " + ("paused." if paused else f"on {speed_name(speed)} speed."),
                SAVE)]
    limits = AWAY_LIMITS.get(village.game)
    if paused:
        out.append(Fact(TIME_AWAY, paused_words))
    else:
        away = max(0.0, village.now - last)
        counted = counted_away(village.game, away, speed)
        if counted is None:
            out.append(Fact(TIME_AWAY, f"Time since then: {duration(away)}. How much of it the game counts when the "
                                       "village is next played is not yet confirmed."))
        else:
            years = f" ({counted / unit_seconds:.1f} years of the villagers' lives)" if unit_seconds and counted else ""
            out.append(Fact(TIME_AWAY, f"If it were played now: {duration(away)} away, of which {duration(counted)} "
                                       f"counts{years}.", CLAMP))
    if limits is None:
        return out
    full = limits["full"].get(speed, limits["full"][NORMAL])
    band, band_end, over = limits["band"], limits["band_end"], limits["over"]
    if full == band:
        rule = f"counts in full up to {duration(full, exact=True)}, and as that up to {duration(band_end)}"
    else:
        rule = (f"counts in full up to {duration(full, exact=True)}; from then to {duration(band_end)} it counts as "
                f"{duration(band, exact=True)}" + (" -- more than the time away, while that is under it" if band > full else ""))
    out.append(Fact(TIME_AWAY, (
        f"On {speed_name(speed)} speed time away {rule}; past that as {duration(over)}, however long the game was "
        "closed" + (f" ({over / unit_seconds:g} years on {speed_name(speed)} speed)." if unit_seconds else ".")
        + " A save left paused gets none."), CLAMP))
    return out


# ---------------------------------------------------------------------------
# The later games' game clock, and dating its past times
# ---------------------------------------------------------------------------


@dataclass
class GameClock:
    """The game clock of The Secret City, The Tree of Life and New Believers (VV3 0x5825D4, VV4 0x4D6F18, VV5
    0x51D490; each saved with the village): the rate (the speed; 0 while paused), the speed before a pause, the
    wall base and the game base.  Its "now" is game base + (wall now - wall base) * 6 / rate, so a game second
    G from the game base on is the real moment
        epoch + wall base + (G - game base) * speed / 6.
    The base is reset at every speed change or pause (VV3 0x426630); the save keeps only the last one, so a
    game second BEFORE it cannot be dated: the speeds, pauses and closed spells between are not kept.  What
    the save does establish is how far into the village it was -- a new village starts the clock at game
    second 0 (VV3 0x4264F0 from 0x427FE2, VV4 0x41DA70 from 0x41F252, VV5 0x41EC90 from 0x424747) -- and that
    it was before the base.  `created`: the village's start (Unix seconds), or None when the save has none."""
    rate: int
    before: int
    wall: int
    base: int
    epoch: int                      # the clock's wall origin (Unix seconds)
    speed: int                      # the save's speed value (3/6/10, +999 paused)
    created: float | None = None

    @property
    def paused(self) -> bool:
        return self.speed >= PAUSED

    @property
    def frozen(self) -> bool:
        """Saved stopped (paused, or a rate of 0): no time passes while the game is closed."""
        return self.rate == 0 or self.paused

    @property
    def runs_at(self) -> int:
        for value in (speed_base(self.speed), self.rate, self.before):
            if value in SPEED_NAMES:
                return value
        return NORMAL

    def real(self, game_seconds: int) -> float:
        """The real moment of a game second at or after the base (later ones at the save's speed)."""
        return self.epoch + self.wall + (game_seconds - self.base) * self.runs_at / NORMAL

    def game_now(self, now: float) -> int:
        if self.frozen:
            return self.base
        return self.base + int(max(0.0, now - self.epoch - self.wall) * NORMAL / self.runs_at)

    @property
    def restarted(self) -> float:
        """The real moment of the base: the earliest one the save can date."""
        return self.epoch + self.wall

    def dated(self, game_seconds: int) -> bool:
        return game_seconds >= self.base

    def moment(self, game_seconds: int, at: bool = False) -> str:
        """A game second in words: its real date ("at ..." with `at`) when the save can date it, otherwise how
        far into the village it was and that it was before the base -- never a date worked back."""
        if self.dated(game_seconds):
            return ("at " if at else "") + when(self.real(game_seconds))
        # Real time only (the owner, 2026-10-22): the clock's count, as the Ash Key line gives it, on Normal speed.
        started = f"started {when(self.created)}; " if self.created is not None else ""
        return (f"{'when ' if at else ''}the village was {duration(max(0, game_seconds), exact=True)} old, counted on "
                f"Normal speed ({started}the save keeps no real date before {when(self.restarted)})")


def later_clock(data: bytes, at: int, epoch: int, speed: int, created_wall: int | None) -> GameClock:
    """The saved clock at `at` (four int32: rate, before, wall base, game base), with the village's start
    `created_wall` (wall seconds from `epoch`, the statistics block's first field) when it is one."""
    rate, before, wall, base = struct.unpack_from("<4i", data, at)
    # (A new village's start is written just after its clock starts, so it may be a little after the wall base.)
    created = epoch + created_wall if created_wall is not None and created_wall > 0 else None
    return GameClock(rate, before, wall, base, epoch, speed, created)


def started_line(created: float | None) -> Fact:
    """The village's start, read from the save (the statistics block's first field, which the game sets when the
    village is made and its Real Hours Played counts from)."""
    if created is None:
        return Fact("Other", "When the village was started is not in this save.", SAVE)
    return Fact("Other", f"The village was started at {when(created)}.", SAVE)


def later_puzzle_lines(names: dict[int, str], entry, threshold: dict[int, int], clock: GameClock,
                       total: str = "") -> list[Fact]:
    """One line for each named puzzle of a later game: solved, and when (the time the game's own Advance stamps,
    on the game clock), or not yet solved.  `entry(id)` -> (progress, solve time); solved is the game's own test,
    progress >= the threshold the puzzle registers with."""
    out = []
    solved = 0
    for pid, name in names.items():
        progress, stamp = entry(pid)
        if progress >= threshold[pid]:
            solved += 1
            if stamp <= 0:
                when_words = "solved (the game kept no time for it)"
            elif stamp > clock.base + MAX_AHEAD:     # far past the clock's base: not a time it wrote
                when_words = f"solved (the time the save holds for it, {stamp:,}, is not one the game's clock reached)"
            else:
                when_words = f"solved {clock.moment(stamp, at=True)}"
            out.append(Fact(PUZZLES, f"{name}: {when_words}.", SAVE))
        else:
            out.append(Fact(PUZZLES, f"{name}: not yet solved.", SAVE))
    out.insert(0, Fact(PUZZLES, f"Puzzles solved: {solved} of {len(names)}{total}.", SAVE))
    return out


MAX_HOURS = 24 * 365 * 100                 # a century of play: any recorded time past it is not a real one
MAX_AHEAD = 2 * 366 * 86_400               # a year on Fast past the clock's base: a stamp later is not a real one


def hours_puzzle_lines(names: list[str], solved, hours, created: float | None) -> list[Fact]:
    """A New Home's and The Lost Children's puzzles: a solved flag and the whole hours since the village was
    started that its completion writes (the Puzzles screen's "Completed in N hours"; at least 1 in The Lost
    Children), so the moment is known to within the hour."""
    out = []
    count = 0
    for n, name in enumerate(names):
        if not solved(n):
            out.append(Fact(PUZZLES, f"{name}: not yet solved.", SAVE))
            continue
        count += 1
        h = hours(n)
        if h <= 0:
            words = "solved (the game kept no time for it)"
        elif h > MAX_HOURS:                  # a value no completion writes: shown, never turned into a date
            words = f"solved (the hours the save holds for it, {h:,}, are not a possible time)"
        elif h == 1:                     # 0 and 1 whole hours are both written as 1
            words = "solved within 2 hours of the village's start" + (
                f", by {when(created + 7200)}" if created is not None else "")
        elif created is None:
            words = f"solved {h} hours after the village was started"
        else:
            words = (f"solved {h} hours after the village was started: between {when(created + h * 3600)} "
                     f"and {when(created + (h + 1) * 3600)}")
        out.append(Fact(PUZZLES, f"{name}: {words}.", False))
    out.insert(0, Fact(PUZZLES, f"Puzzles solved: {count} of {len(names)}.", SAVE))
    return out


# ---------------------------------------------------------------------------
# The patches in the game
# ---------------------------------------------------------------------------


def feature_name(feature: str) -> str:
    """A patch's name as the patcher shows it (data/builds.json, then the feature manifests
    data/*_feature.json), or its id when it is in neither."""
    global _NAMES
    if _NAMES is None:
        import json
        data_folder = Path(__file__).resolve().parents[1] / "data"
        names: dict[str, str] = {}
        for path in sorted(data_folder.glob("*_feature.json")) + [data_folder / "builds.json"]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            entries = data.get("fun_patches", []) if path.name == "builds.json" else [data]
            names.update({entry["id"]: entry["name"] for entry in entries
                          if isinstance(entry, dict) and "id" in entry and "name" in entry})
        _NAMES = names
    return _NAMES.get(feature, feature)


_NAMES: dict[str, str] | None = None


def feature_ids(prefix: str) -> list[str]:
    """Every patch id the patcher knows that starts with `prefix` (for example "vv3_")."""
    feature_name("")
    return sorted(fid for fid in (_NAMES or {}) if fid.startswith(prefix))


def golden_line(feature: str, wait: str) -> str:
    """The Super-Secret Golden Mushroom's facts, for the Game Mechanics page only and only when the patch is in
    the game (the owner, 2026-10-23; everywhere else it stays a secret).  From the patch itself: the kind roll
    (native/vvfp_golden_mushroom kind_roll; The Lost Children's own row) is two draws of the game's raw C rand,
    each a multiple of 1000 out of 0..31999 -- 1 in 1,000,000 -- made only on the random mushroom spawn, and the
    pickup gives 100 food through the game's own mushroom award (tests/test_super_secret_golden_mushroom.py)."""
    return (f"The patcher's \"{feature_name(feature)}\" is in the game: 1 in 1,000,000 of the random brown or red "
            "mushrooms is a gold Golden Mushroom instead, worth 100 food. It never comes from anything else, and it "
            f"counts as a mushroom. At this game's mushroom rate one appears on average once in {wait}.")


def patch_words(village: "Village", feature: str, effect: str) -> str:
    """One sentence on a patch that changes a rule: whether it is in the game and what it does."""
    name = f"\"{feature_name(feature)}\""
    has = village.has(feature)
    if has is None:
        return f"With the patcher's {name}: {effect} (whether the game has it could not be told)."
    return f"The patcher's {name} is {'in' if has else 'not in'} the game" + (f": {effect}." if has else ".")


@dataclass
class PatchSource:
    """Which of the patcher's patches are in the game, and where that was read (the owner, 2026-10-23: from the
    game's executable as it is now, or the patcher's log of the run that made it -- never from the save).
    `installed`: the ids known to be in it, or None when nothing can be told; `certain`: whether an id missing
    from `installed` is known to be out (a log matching the exe) or only not seen (read from the exe's bytes)."""
    installed: frozenset[str] | None
    certain: bool
    exe: Path | None
    words: str                                  # the source, for the top of the page
    problems: list[str] = field(default_factory=list)


_MODIFIED = re.compile(r"^Modified EXE: .*\| SHA-256 ([0-9a-fA-F]{64})\s*$", re.M)
_TIMESTAMP = re.compile(r"^Timestamp \(UTC\): (.+?)\s*$", re.M)
PATCH_LOG_SUFFIX = ".patch-log.json"
PATCHER_SIGNATURE = "Virtual Villagers Fun Patcher"


def _sha256(path: Path) -> str:
    import hashlib
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _game_exes(save_folder: Path, game_folders: list[Path]) -> list[Path]:
    """The executables of the game that saves into `save_folder`: each of `game_folders` named like the save
    folder (Documents\\LDW\\<exe stem>) and holding "<name>.exe" (the repair window's _game_folders_for)."""
    name = Path(save_folder).name
    found: list[Path] = []
    for folder in game_folders:
        folder = Path(folder)
        exe = folder / f"{name}.exe"
        if folder.name.casefold() == name.casefold() and exe.is_file():
            if all(exe.resolve() != other.resolve() for other in found):
                found.append(exe)
    return found


def _from_logs(exe: Path, digest: str) -> tuple[frozenset[str] | None, str, list[str]]:
    """The patch list from the patcher's own logs of the run that wrote `exe` -- its patch log
    "<exe stem>.patch-log.json" or its transparency report -- only when the log's output hash is this exe's."""
    import json
    files = exe.parent / "Virtual Villagers Fun Patcher Files"
    problems: list[str] = []
    try:
        data = json.loads((files / (exe.stem + PATCH_LOG_SUFFIX)).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    if isinstance(data, dict) and data.get("patcher") == PATCHER_SIGNATURE:
        if str(data.get("output_sha256", "")).lower() == digest:
            ids = frozenset(str(x) for x in data.get("fun_patches", []) if isinstance(x, str))
            return ids, f"the patcher's log of the run that made it ({data.get('created_utc', 'no date')} UTC)", []
        problems.append(f"The patcher's log {exe.stem + PATCH_LOG_SUFFIX} is for a different {exe.name} (made "
                        f"{data.get('created_utc', 'on an unknown date')} UTC): the game was patched again or replaced "
                        "since, so the log is not used.")
    for report in TRANSPARENCY:
        try:
            text = (exe.parent / report).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        stamp = _TIMESTAMP.search(text)
        when_words = f" ({stamp.group(1)} UTC)" if stamp else ""
        recorded = _MODIFIED.search(text)
        if recorded and recorded.group(1).lower() == digest:
            return frozenset(_FEATURE.findall(text)), f"the patcher's transparency log{when_words}", problems
        problems.append(f"The patcher's transparency log{when_words} "
                        + ("records a different " + exe.name if recorded else "records no hash for the game")
                        + ", so it is not used.")
        break
    return None, "", problems


def _from_exe(exe: Path, game: int) -> frozenset[str] | None:
    """The patches whose every byte edit is in `exe` at its recorded place (the patcher's own check,
    vv_fun_patcher._patches_present), read only.  A patch whose code the patcher places elsewhere is not seen,
    so a missing id means only "not seen"."""
    try:
        import vv_fun_patcher as fp
        data = exe.read_bytes()
        found = set()
        for feature in fp.load_fun_patches():
            if feature.raw.get("game_id") not in (game, f"vv{game}") and not feature.id.startswith(f"vv{game}_"):
                continue
            edits = feature.raw.get("patches") or []
            if edits and fp._patches_present(data, edits):
                found.add(feature.id)
        return frozenset(found)
    except Exception:  # noqa: BLE001 -- a catalog or exe that cannot be read tells nothing
        return None


def patch_source(save_folder: Path, game_folders: list[Path], game: int = 0,
                 exe: Path | None = None) -> PatchSource:
    """Which patches the game that saves into `save_folder` has now (see PatchSource): its exe found among
    `game_folders` -- or `exe`, the one the player chose with the window's Browse... -- the patcher's log of the
    run that made it when that log's hash is the exe's; otherwise the exe's own bytes.  Never the save."""
    chosen: list[str] = []
    if exe is not None and Path(exe).is_file():
        exes = [Path(exe)]
    else:
        exes = _game_exes(save_folder, game_folders)
        if exe is not None:
            chosen = [f"The game chosen for this save folder, {exe}, was not found; the game was looked for as "
                      "usual."]
    if chosen:
        found = patch_source(save_folder, game_folders, game)
        found.problems[:0] = chosen
        return found
    name = Path(save_folder).name
    if not exes:
        return PatchSource(None, False, None, "", [f"Could not tell which patches this game has: no game folder "
                                                   f"holding {name}.exe was found."])
    digests = {}
    for exe in exes:
        try:
            digests[exe] = _sha256(exe)
        except OSError:
            continue
    if not digests:
        return PatchSource(None, False, exes[0], "", [f"Could not tell which patches this game has: {exes[0]} could "
                                                      "not be read."])
    if len(set(digests.values())) > 1:
        return PatchSource(None, False, None, "", ["Could not tell which patches this game has: several different "
                                                   f"{name}.exe were found (" + "; ".join(str(e) for e in digests)
                                                   + ")."])
    exe = next(iter(digests))
    ids, words, problems = _from_logs(exe, digests[exe])
    if ids is not None:
        return PatchSource(ids, True, exe, f"{exe}, as listed by {words}", problems)
    ids = _from_exe(exe, game) if game else None
    if ids is None:
        return PatchSource(None, False, exe, "", problems + [f"Could not tell which patches this game has: no "
                                                             f"patcher log matches {exe}, and its bytes could not be "
                                                             "read."])
    return PatchSource(ids, False, exe, f"{exe}, read from its own bytes (no patcher log matches it); a patch the "
                                        "exe does not show is given as not known", problems)


SOURCES = "Sources"


def sources_lines(save: Path, patches: PatchSource, notes: list[str]) -> list[Fact]:
    """Where the page's facts come from (the owner, 2026-10-23): the save and when it was last written (a game saves
    only on a clean quit, so while it runs the save can be behind it), the game's exe and where its patch list was
    read, the patcher's per-save files the page read, and every disagreement between them."""
    out = []
    try:
        written = when(save.stat().st_mtime)
        out.append(Fact(SOURCES, f"The save: {save}, last written {written}. The game writes it only when it is "
                                 "closed normally, so while it is being played the values here can be behind it.", SAVE))
    except OSError:
        out.append(Fact(SOURCES, f"The save: {save}.", SAVE))
    if patches.words:
        out.append(Fact(SOURCES, f"The patches in the game: {patches.words}.", SAVE))
    out += [Fact(SOURCES, problem, SAVE) for problem in patches.problems]
    out += [Fact(SOURCES, note, SAVE) for note in notes]
    return out


def installed_features(save_folder: Path, game_folders: list[Path]) -> frozenset[str] | None:
    """The patch ids known to be in the game (patch_source), or None."""
    return patch_source(save_folder, game_folders).installed


# ---------------------------------------------------------------------------
# The section
# ---------------------------------------------------------------------------


def save_path(folder: Path, game: int, slot: int) -> Path:
    """The slot's own save, named as every other repair tool names it (src/vv_tribe_rename.py)."""
    import vv_tribe_rename
    saves = next(item for item in vv_tribe_rename.GAMES if item.number == game)
    return saves.save_path(Path(folder), slot)


def read(folder: Path, game: int, slot: int, game_folders: list[Path] | None = None,
         now: float | None = None, exe: Path | None = None) -> list[Fact]:
    """Every line of the section for one save slot, in GROUPS order.  Reads only, and reads every source again
    at each call (the window's Refresh).  `exe`: the game the player chose for this save folder, if any."""
    import time
    path = save_path(folder, game, slot)
    try:
        data = path.read_bytes()
    except OSError as exc:
        return [Fact("Other", f"The save {path.name} could not be read ({exc.strerror or exc}).")]
    patches = patch_source(Path(folder), game_folders or [], game, exe)
    village = Village(Path(folder), game, slot, path, data, patches.installed,
                      time.time() if now is None else now, certain=patches.certain, exe=patches.exe)
    try:
        module = importlib.import_module(f"vv_game_mechanics_vv{game}")
    except ImportError:
        return [Fact("Other", "Nothing is shown for this game yet.")]
    facts = list(module.facts(village))
    if any(fact.group != "Other" for fact in facts):     # not for a save the game's module could not read
        facts += genetics_facts(village)
    if not facts:
        facts = [Fact("Other", "Nothing is shown for this game yet.")]
    facts = sources_lines(path, patches, village.notes) + facts
    order = {name: n for n, name in enumerate(GROUPS)}
    return sorted(facts, key=lambda fact: order.get(fact.group, len(GROUPS)))


# A new, empty village's save for each game, to show the general rules when no save is found: (header size,
# where the buffer's length is, the buffer's length, where the speed is, where the clock's epoch is and its
# width) -- the layouts vv_save_backup reads (its "GAME SPEED" notes).
_BLANK = {1: (12, 8, 0x0ABDC, 12 + 0xA310), 2: (12, 8, 0x30370, 12 + 0x2EB00), 3: (12, 8, 0x12F1C, 12 + 0x12F18),
          4: (24, 16, 0x1710C, 24 + 0x17108), 5: (24, 16, 0x17D78, 24 + 0x17D74)}
GENERAL_NOTE = ("No save was found for this game, so these are its general rules at Normal speed; everything "
                "read from a save is left out.")


def blank_save(game: int, now: float) -> bytes:
    header, length_at, length, speed_at = _BLANK[game]
    data = bytearray(header + length)
    data[:4] = b"ldwg"
    struct.pack_into("<I", data, length_at, length)
    if header == 24:
        struct.pack_into("<q", data, 8, int(now))
    else:
        struct.pack_into("<I", data, 4, int(now))
    struct.pack_into("<i", data, speed_at, NORMAL)
    if game == 3:                              # the clock running at Normal, and the puzzles' mark
        struct.pack_into("<4i", data, 12 + 0x57C, NORMAL, 0, 0, 0)
        struct.pack_into("<I", data, 12 + 0x11ECC, 0x2AD)
    return bytes(data)


def general(game: int, now: float | None = None) -> list[Fact]:
    """A game's general rules, for when no save is found: its page for a new, empty village at Normal speed,
    without anything read from a save (the values, the dates and the time-away figures of that save)."""
    import time
    now = time.time() if now is None else now
    village = Village(Path("."), game, 1, Path(f"{game}.ldw"), blank_save(game, now), None, now, general=True)
    module = importlib.import_module(f"vv_game_mechanics_vv{game}")
    keep = []
    for fact in list(module.facts(village)) + genetics_facts(village):
        if fact.due is not None:
            continue                           # a moment of the empty save's village
        if fact.verified == SAVE or fact.text.startswith(("If it were played now", "Time since then", "Next ",
                                                          "Saved paused", "Fruit trees: none")):
            continue
        if re.search(r"\b(19[67]\d|20\d\d)\b", fact.text) or "could not be read" in fact.text:
            continue                           # a date from the empty save
        if re.match(r"^[A-Z][A-Za-z' ]{0,30}: -?[\d,]+\b", fact.text) or "would bring 0" in fact.text \
                or fact.text.startswith("The birds:"):
            continue                           # an amount from the empty save ("Crop field: 0 of 800")
        keep.append(fact)
    order = {name: n for n, name in enumerate(GROUPS)}
    return sorted(keep, key=lambda fact: order.get(fact.group, len(GROUPS)))


def with_due(facts: list[Fact], start: str, moment: float | None, kind: str) -> None:
    """Give the facts whose text starts with `start` an upcoming moment for the window's countdown (in place).  A
    moment of None (saved paused, not read) leaves them as they are."""
    if moment is None:
        return
    import dataclasses
    for n, fact in enumerate(facts):
        if fact.text.startswith(start) and fact.due is None:
            facts[n] = dataclasses.replace(fact, due=float(moment), due_kind=kind)


DUE = "{due}"
# A due fact's kind, as the words before its date when its text does not place the date itself.
DUE_KINDS = {"refill": "Next refill", "ready": "Ready", "ends": "Ends", "due": "Due", "starts": "Starts",
             "next": "Next"}
DUE_NOW = "due now (refresh to see the new state)"


def countdown(due: float, now: float) -> str:
    """The time left until `due` at `now`: "in 12 min 03 s", "in 2 h 05 min 00 s", "in 3 d 4 h 05 min 06 s",
    "in 9 s" -- whole seconds rounded up, so it reads "in 1 s" until the very moment -- or DUE_NOW from then on."""
    left = math.ceil(due - now - 1e-9)
    if left <= 0:
        return DUE_NOW
    days, rest = divmod(left, 86_400)
    hours, rest = divmod(rest, 3600)
    minutes, seconds = divmod(rest, 60)
    if days:
        return f"in {days} d {hours} h {minutes:02d} min {seconds:02d} s"
    if hours:
        return f"in {hours} h {minutes:02d} min {seconds:02d} s"
    if minutes:
        return f"in {minutes} min {seconds:02d} s"
    return f"in {seconds} s"


def countdown_span(due: float, now: float) -> str:
    """The live words right after a due fact's date: " (in 12 min 03 s)", or ", due now (refresh ...)"."""
    words = countdown(due, now)
    return f", {words}" if words == DUE_NOW else f" ({words})"


@dataclass(frozen=True)
class Countdown:
    """Where a live countdown is on the rendered page: its line (1-based, as Tk counts), its first column and
    its length, as rendered, and the moment it counts down to."""
    line: int
    column: int
    length: int
    due: float


def _due_line(text: str, due: float, kind: str | None, now: float) -> tuple[str, int, int]:
    """`text` with the due's date and countdown placed (see LIVE COUNTDOWNS); the countdown's start and length."""
    date = when(due)
    span = countdown_span(due, now)
    if DUE in text:
        head, tail = text.split(DUE, 1)
        return head + date + span + tail.replace(DUE, date), len(head) + len(date), len(span)
    at = text.find(date)
    if at >= 0:
        at += len(date)
        return text[:at] + span + text[at:], at, len(span)
    label = DUE_KINDS.get(kind or "due", (kind or "due").capitalize())
    head = text.rstrip()
    if head and head[-1] not in ".!?":
        head += "."
    head = f"{head} {label}: {date}" if head else f"{label}: {date}"
    return head + span + ".", len(head), len(span)


def render_live(facts: list[Fact], now: float | None = None) -> tuple[str, list[Countdown]]:
    """The section as text as it reads at `now` (each group's heading, then its lines), and every live
    countdown's place on it for the window to tick."""
    import time
    now = time.time() if now is None else now
    out: list[str] = []
    spans: list[Countdown] = []
    group = None
    for fact in facts:
        if fact.group != group:
            if out:
                out.append("")
            out.append(fact.group)
            group = fact.group
        mark = SUB_BULLET if fact.sub else BULLET
        lead = mark if fact.confirmed else f"{mark}{UNCONFIRMED}  "
        body = tidy(fact.text)
        if fact.due is not None:
            body, column, length = _due_line(body, fact.due, fact.due_kind, now)
            spans.append(Countdown(len(out) + 1, len(lead) + column, length, fact.due))
        out.append(lead + body)
    return "\n".join(out), spans


def render(facts: list[Fact], now: float | None = None) -> str:
    """The section as text: each group's heading, then its lines (a countdown as it reads at `now`)."""
    return render_live(facts, now)[0]


def tidy(text: str) -> str:
    """A line with an empty marker left in it read cleanly: no space before a stop, no double space."""
    text = re.sub(r"\(\s*\)", "", text)
    text = re.sub(r"\s+([.;,)])", r"\1", text)
    return re.sub(r"  +", " ", text).strip()
