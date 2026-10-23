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
"""
from __future__ import annotations

import importlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

TITLE = "Game Mechanics"
GROUPS = ("Food sources", "Refills", "Mushrooms", "Collectibles", "Tech points and effects",
          "Food earned", "Time away and Time Warp", "Island events", "Other")
# A rule read from the game's code but not yet seen happen in a game: said so on the page.
UNCONFIRMED = "(not yet confirmed in game)"

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
    group: str
    text: str


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

    def has(self, feature: str) -> bool | None:
        return None if self.installed is None else feature in self.installed


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
    days, rest = divmod(minutes, 24 * 60)
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
AWAY_LIMITS: dict[int, dict] = {}
TIME_AWAY = "Time away and Time Warp"


def counted_away(game: int, seconds: float, speed: int) -> float | None:
    """How much of `seconds` away `game` counts at `speed`, or None while its limits are not confirmed."""
    limits = AWAY_LIMITS.get(game)
    if limits is None:
        return None
    seconds = max(0.0, seconds)
    if seconds <= limits["full"][speed]:
        return seconds
    return limits["band"] if seconds <= limits["band_end"] else limits["over"]


def time_away(village: "Village", last: float, speed_value: int, paused_words: str,
              unit_seconds: float | None = None) -> list[Fact]:
    """The time-away lines every game shares: when the save was last played, its speed or pause, how much
    of the time since then would count if it were opened now, and the rule -- the rule only from
    AWAY_LIMITS.  `unit_seconds`: a year's real length at this speed, to say the counted time in years."""
    speed = speed_base(speed_value)
    paused = speed_value >= PAUSED
    out = [Fact(TIME_AWAY, f"Last saved: {when(last)}, " + ("paused." if paused else f"on {speed_name(speed)} speed."))]
    if paused:
        out.append(Fact(TIME_AWAY, paused_words))
        return out
    away = max(0.0, village.now - last)
    counted = counted_away(village.game, away, speed)
    if counted is None:
        out.append(Fact(TIME_AWAY, f"Time since then: {duration(away)}. How much of it the game counts when the "
                                   "village is next played is not yet confirmed."))
        return out
    years = f" ({counted / unit_seconds:.1f} years of the villagers' lives)" if unit_seconds and counted else ""
    out.append(Fact(TIME_AWAY, f"If it were played now: {duration(away)} away, of which {duration(counted)} "
                               f"counts{years}."))
    limits = AWAY_LIMITS[village.game]
    out.append(Fact(TIME_AWAY, (
        f"On {speed_name(speed)} speed time away counts in full up to {duration(limits['full'][speed], exact=True)}; "
        f"from then to {duration(limits['band_end'], exact=True)} it counts as {duration(limits['band'], exact=True)}; "
        f"past that as {duration(limits['over'], exact=True)}, however long the game was closed.")))
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


def patch_words(village: "Village", feature: str, effect: str) -> str:
    """One sentence on a patch that changes a rule: whether it is in the game and what it does."""
    name = f"\"{feature_name(feature)}\""
    has = village.has(feature)
    if has is None:
        return f"With the patcher's {name}: {effect} (whether the game has it could not be told)."
    return f"The patcher's {name} is {'in' if has else 'not in'} the game" + (f": {effect}." if has else ".")


def installed_features(save_folder: Path, game_folders: list[Path]) -> frozenset[str] | None:
    """The patcher's feature ids in the game that saves into `save_folder`: the first of
    `game_folders` named like the save folder and holding "<name>.exe" (the repair window's
    _game_folders_for, as Move Old Files to New Names finds it), read from its transparency report.
    None when no such game folder, or no readable report, was found."""
    name = Path(save_folder).name
    for folder in game_folders:
        folder = Path(folder)
        if folder.name.casefold() != name.casefold() or not (folder / f"{name}.exe").is_file():
            continue
        for report in TRANSPARENCY:
            try:
                text = (folder / report).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            return frozenset(_FEATURE.findall(text))
        return None
    return None


# ---------------------------------------------------------------------------
# The section
# ---------------------------------------------------------------------------


def save_path(folder: Path, game: int, slot: int) -> Path:
    """The slot's own save, named as every other repair tool names it (src/vv_tribe_rename.py)."""
    import vv_tribe_rename
    saves = next(item for item in vv_tribe_rename.GAMES if item.number == game)
    return saves.save_path(Path(folder), slot)


def read(folder: Path, game: int, slot: int, game_folders: list[Path] | None = None,
         now: float | None = None) -> list[Fact]:
    """Every line of the section for one save slot, in GROUPS order.  Reads only."""
    import time
    path = save_path(folder, game, slot)
    try:
        data = path.read_bytes()
    except OSError as exc:
        return [Fact("Other", f"The save {path.name} could not be read ({exc.strerror or exc}).")]
    village = Village(Path(folder), game, slot, path, data,
                      installed_features(Path(folder), game_folders or []),
                      time.time() if now is None else now)
    try:
        module = importlib.import_module(f"vv_game_mechanics_vv{game}")
    except ImportError:
        return [Fact("Other", "Nothing is shown for this game yet.")]
    facts = list(module.facts(village))
    if not facts:
        facts = [Fact("Other", "Nothing is shown for this game yet.")]
    order = {name: n for n, name in enumerate(GROUPS)}
    return sorted(facts, key=lambda fact: order.get(fact.group, len(GROUPS)))


def render(facts: list[Fact]) -> str:
    """The section as text: each group's heading, then its lines."""
    out: list[str] = []
    group = None
    for fact in facts:
        if fact.group != group:
            if out:
                out.append("")
            out.append(fact.group)
            group = fact.group
        out.append(f"  {fact.text}")
    return "\n".join(out)
