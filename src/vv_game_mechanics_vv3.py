"""Game Mechanics for The Secret City (VV3): read-only lines from one save (src/vv_game_mechanics.py).

THE SAVE.  "<base><slot>.ldw" is a 12-byte header -- "ldwg", the save's own clock epoch (Unix seconds),
the buffer's length -- then the game's save buffer, which the save writer 0x427C60 fills from the game
state at state+8 onward, so a state offset S is buffer offset S - 8 (0x12F1C bytes stock, 0x1A4B4 with
256 Villagers, whose builds keep the stock bytes first: every offset below is the same in both).

  THE CLOCK (0x5825D4, saved by 0x426540 at buffer 0x57C):  +0 the rate (the speed; 0 while paused),
    +4 the speed it had before a pause, +8 the wall base, +0xC the game base.  The clock's "now" 0x426590
    is game base + (wall now - wall base) * 6 / rate, wall seconds counted by 0x403330 from the epoch
    in the save's header (0x4A4210, loaded with the save).  So a game second G is the real moment
        epoch + wall base + (G - game base) * speed / 6
    -- exact from the wall base on (the last speed change or pause); before it, worked out at the same
    speed, as the game's own clock relates them.  The clock runs on while the game is closed (the next
    load catches up), except when it was saved stopped (a rate of 0: paused, among others).  The speed
    the player sees -- and Repair Saves & Logs' Game speed sets -- is the dword at buffer 0x12F18
    (3 Fast, 6 Normal, 10 Slow; +999 while paused); intervals are shown at that speed.
  TECHS (0x582618, saved by 0x426F60 at buffer 0x6CC0): seven levels; Nature is technology 5, Magic 6.
    With Both Factions the second faction's level is kept in "Virtual Villagers Fun Patcher\\Save <S>\\
    Data\\Factions\\Virtual Villagers 3 Second Faction - Save <S>.dat" (native/vvfp_vv3_both_factions),
    bound to this save by an FNV-1a 64 fingerprint of the buffer's first 0x6CDC bytes and the tech
    points after them.
  PUZZLES (0x594990, saved by 0x435790 at buffer 0x11ECC):  the dword 0x2AD, the manager's 0xD0 bytes
    (puzzle i's progress and solve time at +4 + 8i), then each puzzle object's own block in the order
    0x4355E0 registers them from the table 0x4B0D88: 0x594614 (1 byte), the honey 0x5945D0 (0x10),
    0x593B40 (0x3C), 0x594B3C (1), 0x594BF8 (1), 0x594AD8 (0xC), 0x594BA4 (1), 0x5945BC (1), 0x594870
    (0x10), then the fruit trees 0x5947E0 (0x60) -- so the honey block is at buffer 0x11FA1 and the
    trees' at 0x1200D.
  THE HONEY (0x5945D0, block by 0x4316A0):  +4 the time of its last growth, +8 the honey (0..3000).
  THE FRUIT TREES (0x5947E0, block by 0x433EC0, read back by 0x433E40):  +0x14 three trees of 0x18
    bytes -- x, y, the time it was planted, the time of its last refill, its kind (0 Banana, 1 Mango,
    2 Papaya: the strings at 0x480DCC/0x480DC4/0x480DBC, the art bananaTree/mangoTree/papayaTree), its
    fruit (0..1000) -- and +0x5C how many are planted (0..3).

THE RULES (the refill 0x434760, the honey 0x4319B0, the "ready" test 0x434030).  A tree is picked from
0x7080 game seconds (8 hours on Normal speed) after it is planted.  Once 0x2A30 game seconds (3 hours)
have passed since its last refill, a tree gains floor(elapsed * 37 / 3600) fruit -- 42 at Nature level
1 or more -- up to 1000, and the time is set to now.  With the patcher's "Nature Level 1 Actually
Replenishes Food Sources Faster" (vv3_nature_honey_refill) and Nature 1 or more, 8,100 game seconds
(2 hours 15 minutes) and 56 (the same 126 fruit a refill).  The honey gains floor(elapsed * 2 / 3600)
once 3,600 game seconds have passed (with that patch at Nature 1 or more: 2,700 and elapsed * 84 /
99900), up to 3000.  docs/vv3-nature-honey-research.md.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

import vv_game_mechanics as gm

GAME = 3
HEADER = 12
BUFFERS = (0x12F1C, 0x1A4B4)            # stock, 256 Villagers (src/vv_save_backup.py)
CLOCK = 0x57C
SPEED = 0x12F18
TECHS = 0x6CC0
POINTS = 0x6CDC
NATURE, MAGIC = 5, 6
PUZZLES = 0x11ECC
PUZZLES_MARK = 0x2AD
BEE_HIVE = 1                            # puzzle 1, The Bee Hive (story_c3.inc C3_PUZZLE_DEFS)
HONEY = 0x11FA1
TREES = 0x1200D
TREE_SIZE = 0x18
MAX_TREES = 3
FRUIT = ("Banana", "Mango", "Papaya")
FRUIT_CAP = 1000
HONEY_CAP = 3000
READY = 0x7080                          # 8 game hours after planting
REFILL = 0x2A30                         # 3 game hours
REFILL_PATCHED = 8100                   # 2 hours 15 minutes
HONEY_EVERY = 3600
HONEY_PATCHED = 2700
NATURE_PATCH = "vv3_nature_honey_refill"
NATURE_PATCH_NAME = "Nature Level 1 Actually Replenishes Food Sources Faster"

SAVES = "Virtual Villagers Fun Patcher"
FACTION_FILE = "Data\\Factions\\Virtual Villagers 3 Second Faction - Save {slot}.dat"
FACTION_MAGIC = 0x46325656
FACTION_ENTRIES = 16
# The two fruit-tree patches' own timers ("All Fruit Trees Refill at the Same Time" / "Fruit Trees Take
# Turns Refilling", branch feat/vv3-trees-refill-together): kept beside the save, which keeps the stock
# timers.  See patch_tree_timers.
TREE_TIMERS_FILE = "Data\\Fruit Trees\\Virtual Villagers 3 Fruit Tree Timers - Save {slot}.dat"


class SaveUnreadable(ValueError):
    pass


@dataclass
class Clock:
    rate: int           # the speed while running, 0 while paused
    before: int         # the speed before a pause
    wall: int           # wall seconds from the epoch at the base
    base: int           # the game seconds at the base
    epoch: int          # the save's own epoch (Unix seconds)
    speed: int          # the save's speed value (3/6/10, +999 paused)

    @property
    def paused(self) -> bool:
        """Saved paused, as the player set it (the speed value plus 999)."""
        return self.speed >= gm.PAUSED

    @property
    def frozen(self) -> bool:
        """The clock was saved stopped (paused, or a rate of 0): no time passes while the game is closed."""
        return self.rate == 0 or self.paused

    @property
    def runs_at(self) -> int:
        """The speed the clock runs at (once unpaused): the save's speed, as the player set it."""
        for value in (gm.speed_base(self.speed), self.rate, self.before):
            if value in gm.SPEED_NAMES:
                return value
        return gm.NORMAL

    def real(self, game_seconds: int) -> float:
        """The real moment (Unix seconds) of a game second, as the game's clock relates them."""
        return self.epoch + self.wall + (game_seconds - self.base) * self.runs_at / gm.NORMAL

    def game_now(self, now: float) -> int:
        """The game clock at the real moment `now`: it ran on after the save unless stopped."""
        if self.frozen:
            return self.base
        return self.base + int(max(0.0, now - self.epoch - self.wall) * gm.NORMAL / self.runs_at)


def _u32(buf: bytes, at: int) -> int:
    return struct.unpack_from("<I", buf, at)[0]


def _i32(buf: bytes, at: int) -> int:
    return struct.unpack_from("<i", buf, at)[0]


def buffer_of(data: bytes) -> tuple[bytes, int]:
    """(the save buffer, the save's epoch); SaveUnreadable when it is not a Secret City slot save."""
    if len(data) < HEADER or data[:4] != b"ldwg":
        raise SaveUnreadable("it is not a Secret City save")
    length = _u32(data, 8)
    if length not in BUFFERS or len(data) != HEADER + length:
        raise SaveUnreadable("its length is not a Secret City save's")
    buf = data[HEADER:]
    if _u32(buf, PUZZLES) != PUZZLES_MARK:
        raise SaveUnreadable("its puzzles are not where The Secret City keeps them")
    return buf, _u32(data, 4)


def clock_of(buf: bytes, epoch: int) -> Clock:
    rate, before, wall, base = (_i32(buf, CLOCK + 4 * k) for k in range(4))
    return Clock(rate, before, wall, base, epoch, _i32(buf, SPEED))


@dataclass
class Tree:
    number: int
    kind: int
    planted: int
    refilled: int
    fruit: int

    @property
    def name(self) -> str:
        return FRUIT[self.kind] if 0 <= self.kind < len(FRUIT) else f"an unknown fruit ({self.kind})"


def trees_of(buf: bytes) -> list[Tree]:
    count = _i32(buf, TREES + 0x5C)
    trees = []
    for n in range(max(0, min(count, MAX_TREES))):
        at = TREES + 0x14 + TREE_SIZE * n
        planted, refilled, kind, fruit = (_i32(buf, at + 8 + 4 * k) for k in range(4))
        trees.append(Tree(n + 1, kind, planted, refilled, fruit))
    return trees


# ---------------------------------------------------------------------------
# Nature, with Both Factions' second faction
# ---------------------------------------------------------------------------


def _fnv(data: bytes, value: int = 0xCBF29CE484222325) -> int:
    for byte in data:
        value = ((value ^ byte) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return value


def second_faction(folder: Path, slot: int, buf: bytes) -> tuple[int, int] | None:
    """(technology, level) of Both Factions' second faction for exactly this save, or None.  Read as
    the companion's loader reads it: same slot, the save's fingerprint, the faction the save holds at
    the level it holds.  Never written here."""
    path = Path(folder) / SAVES / f"Save {slot}" / FACTION_FILE.format(slot=slot)
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < 20:
        return None
    magic, version, game, file_slot, count = struct.unpack_from("<5I", data, 0)
    stride = {2: 24, 1: 20}.get(version)
    if (magic != FACTION_MAGIC or game != GAME or file_slot != slot or count > FACTION_ENTRIES
            or stride is None or len(data) != 20 + FACTION_ENTRIES * stride):
        return None
    fingerprint = _fnv(buf[:POINTS + 4])
    for n in range(count - 1, -1, -1):
        lo, hi, secondary, secondary_level, primary, primary_level = struct.unpack_from(
            "<IIBBBB", data, 20 + n * stride)
        if (hi << 32 | lo) != fingerprint or {secondary, primary} != {NATURE, MAGIC}:
            continue
        if not 1 <= secondary_level <= 3 or _i32(buf, TECHS + 4 * primary) != primary_level:
            continue
        return secondary, secondary_level
    return None


def nature_level(folder: Path, slot: int, buf: bytes) -> tuple[int, bool]:
    """(Nature's level, whether it is Both Factions' second faction)."""
    level = _i32(buf, TECHS + 4 * NATURE)
    second = second_faction(folder, slot, buf)
    if level <= 0 and second is not None and second[0] == NATURE:
        return second[1], True
    return level, False


# ---------------------------------------------------------------------------
# The fruit-tree patches' own timers (the hook)
# ---------------------------------------------------------------------------


def patch_tree_timers(village: gm.Village) -> list[int] | None:
    """THE HOOK for "All Fruit Trees Refill at the Same Time" / "Fruit Trees Take Turns Refilling":
    their own refill times, per tree, from their per-save file -- None while this build cannot read
    it (its format is not yet published), and then the save's own (stock) timers are shown."""
    return None


def tree_timers_file(village: gm.Village) -> Path:
    return village.folder / SAVES / f"Save {village.slot}" / TREE_TIMERS_FILE.format(slot=village.slot)


# ---------------------------------------------------------------------------
# The lines
# ---------------------------------------------------------------------------


def _gain(elapsed: int, factor: int) -> int:
    """The game's own arithmetic: (elapsed * factor) in 32 bits, divided by 3600."""
    return ((elapsed * factor) & 0xFFFFFFFF) // 3600


def facts(village: gm.Village) -> list[gm.Fact]:
    try:
        buf, epoch = buffer_of(village.data)
    except SaveUnreadable as exc:
        return [gm.Fact("Other", f"{village.save.name} could not be read: {exc}.")]
    clock = clock_of(buf, epoch)
    out: list[gm.Fact] = []
    nature, second = nature_level(village.folder, village.slot, buf)
    patch = village.has(NATURE_PATCH)
    faster = nature >= 1 and patch is True
    interval = REFILL_PATCHED if faster else REFILL
    factor = 56 if faster else (42 if nature >= 1 else 37)
    per_refill = _gain(interval, factor)
    now = clock.game_now(village.now)

    def at(game_seconds: int) -> str:
        return gm.when(clock.real(game_seconds))

    # -- the fruit trees ------------------------------------------------------------------
    timers = patch_tree_timers(village)
    trees = trees_of(buf)
    if not trees:
        out.append(gm.Fact("Food sources", "Fruit trees: none is planted yet."))
    for tree in trees:
        refilled = timers[tree.number - 1] if timers is not None else tree.refilled
        text = (f"Tree {tree.number}: {tree.name}, planted at {at(tree.planted)}, refills "
                f"{gm.every(interval, clock.speed)}. {max(tree.fruit, 0)} of {FRUIT_CAP} fruit.")
        ready = tree.planted + READY
        if clock.frozen:
            text += (" Ready to pick." if now >= ready else
                     f" Ready to pick after {gm.duration(gm.real_seconds(ready - now, clock.runs_at))} more "
                     f"of play on {gm.speed_name(clock.runs_at)} speed.")
        else:
            text += (f" Ready to pick since {at(ready)}." if now >= ready else
                     f" Ready to pick from {at(ready)}.")
        due = refilled + interval
        if tree.fruit >= FRUIT_CAP:
            text += " Full: a refill adds nothing until fruit is picked."
        elif clock.frozen:
            left = max(0, due - now)
            text += (f" Next refill ({per_refill} fruit) after {gm.duration(gm.real_seconds(left, clock.runs_at))} "
                     f"more of play{' once unpaused' if clock.paused else ''}." if left else
                     f" A refill is due as soon as the game {'is unpaused' if clock.paused else 'is played'}.")
        elif now >= due:
            gained = min(_gain(now - refilled, factor), FRUIT_CAP - tree.fruit)
            text += (f" A refill was due at {at(due)}: the next time the village is played it gets "
                     f"{gained} fruit.")
        else:
            text += f" Next refill due {at(due)} ({min(per_refill, FRUIT_CAP - tree.fruit)} fruit)."
        out.append(gm.Fact("Food sources", text))

    # -- the honey ------------------------------------------------------------------------
    honey_at = _i32(buf, HONEY + 4)
    honey = _i32(buf, HONEY + 8)
    hive = _i32(buf, PUZZLES + 4 + 8 * BEE_HIVE) >= 1
    out.append(gm.Fact("Food sources", f"Honey: {honey} of {HONEY_CAP}"
                       + (" (The Bee Hive is solved)." if hive else
                          " (gathering it needs The Bee Hive solved; it is not solved yet).")))

    # -- the rules ------------------------------------------------------------------------
    speed = clock.speed
    nature_words = (f"Nature is level {nature}" + (" (the second faction, from Both Factions' file)"
                                                   if second else "") if nature >= 1
                    else "Nature is level 0")
    if patch is None:
        patch_words = (f"Whether the game has the patcher's \"{NATURE_PATCH_NAME}\" could not be told (its game "
                       "folder was not found); the stock rule is shown.")
    else:
        patch_words = (f"The patcher's \"{NATURE_PATCH_NAME}\" is {'in' if patch else 'not in'} the game"
                       + (" but needs Nature level 1." if patch and nature < 1 else "."))
    if clock.paused:
        out.append(gm.Fact("Refills", gm.PAUSED_NOTE))
    out.append(gm.Fact("Refills", (
        f"Fruit trees: each gains {per_refill} fruit {gm.every(interval, speed)}, up to {FRUIT_CAP}; {nature_words}. "
        f"{patch_words}")))
    if not faster:
        alt = []
        if nature < 1:
            alt.append(f"at Nature level 1 or more: {_gain(REFILL, 42)} fruit {gm.every(REFILL, speed)}")
        if patch is not False:
            alt.append(f"with the patch and Nature level 1 or more: {_gain(REFILL_PATCHED, 56)} fruit "
                       f"{gm.every(REFILL_PATCHED, speed)}")
        if alt:
            out.append(gm.Fact("Refills", "Fruit trees otherwise: " + "; ".join(alt) + "."))
    out.append(gm.Fact("Refills", (
        f"A new tree can be picked {gm.duration(gm.real_seconds(READY, clock.runs_at))} after it is planted, on "
        f"{gm.speed_name(clock.runs_at)} speed.")))
    honey_every = HONEY_PATCHED if faster else HONEY_EVERY
    honey_gain = ((honey_every * 84) // 99900) if faster else ((honey_every * 2) // 3600)
    honey_due = honey_at + honey_every
    if clock.frozen or honey >= HONEY_CAP:
        honey_next = "."
    elif now < honey_due:
        honey_next = f"; next due {at(honey_due)}."
    else:
        honey_factor_gain = (((now - honey_at) * 84) & 0xFFFFFFFF) // 99900 if faster else \
            (((now - honey_at) * 2) & 0xFFFFFFFF) // 3600
        honey_next = (f"; a gain was due at {at(honey_due)}: the next time the village is played it gets "
                      f"{min(honey_factor_gain, HONEY_CAP - honey)}.")
    out.append(gm.Fact("Refills", (
        f"Honey: gains {honey_gain} {gm.every(honey_every, speed)}, up to {HONEY_CAP}{honey_next}")))

    # -- the clock ------------------------------------------------------------------------
    if clock.paused:
        out.append(gm.Fact("Other", (
            f"The game's clock is stopped while paused; once unpaused it runs on {gm.speed_name(clock.runs_at)} "
            "speed. Times are real times, worked out at that speed.")))
    elif clock.frozen:
        out.append(gm.Fact("Other", (
            f"The save's clock was written stopped; it runs again on {gm.speed_name(clock.runs_at)} speed once the "
            "village is played, so the time the game is closed does not count. Times are real times, worked "
            "out at that speed.")))
    else:
        out.append(gm.Fact("Other", (
            f"The game's clock runs on {gm.speed_name(clock.runs_at)} speed, also while the game is closed "
            "(the next time it is played it catches up). Times are real times; those before "
            f"{gm.when(clock.real(clock.base))} assume it was always on this speed.")))
    if timers is None and tree_timers_file(village).is_file():
        out.append(gm.Fact("Other", (
            "The patcher's fruit-tree timers file is there, but this version cannot read it yet: the "
            "save's own refill times are shown.")))
    return out
