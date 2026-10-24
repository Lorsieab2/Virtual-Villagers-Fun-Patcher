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
    -- exact from the wall base on (the last speed change or pause).  Before it the save cannot date a game
    second (the speeds, pauses and closed spells between are not kept): such a time is shown as the village's age
    then, counted on Normal speed (a new village starts the clock at 0, 0x4264F0 from 0x427FE2), never as a
    date worked back (gm.GameClock.moment).  The village's start is the statistics block's first field
    (0x5824A0, buffer 0x4E4: wall seconds, written from 0x403330 at 0x4646EB).  The clock runs on while the game is closed (the next
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
import vv_game_mechanics_life as life

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
# Honey gained 45 minutes, 1 hour, 3 hours and 10 hours (Normal speed) after the last gain: stock, and with the
# Nature refill patch at Nature 1 or more (both emulated).
HONEY_GAINS = (0, 2, 6, 20)
HONEY_PATCHED_GAINS = (2, 3, 9, 30)
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
TOGETHER, TAKE_TURNS, BOTH_FACTIONS = "vv3_fruit_trees_refill_together", "vv3_fruit_trees_take_turns", "vv3_both_factions"


class SaveUnreadable(ValueError):
    pass


# The game clock (vv_game_mechanics.GameClock): a past game second is dated only from the clock's base on.
Clock = gm.GameClock


def _u32(buf: bytes, at: int) -> int:
    return struct.unpack_from("<I", buf, at)[0]


# Hidden villager stats (the coordinator's specs hidden_vv3\spec.md and likes_all, 2026-10-23):
# (line, what stands behind it -- gm.RUNNING, gm.OWNER, or False for UNCONFIRMED).
HIDDEN_LINES = (
    ("Each villager's hidden name number (1 to 123) sets how it starves, its voice and its grave spot; "
     "renaming changes the name, not the number. The villagers' numbers are below.", gm.RUNNING),
    ('No hidden fertility, learning rate, lifespan or toughness value is rolled: a new villager rolls only '
     'sex, name number, family number, head, body, likes and dislikes.', gm.RUNNING),
    ('Liking learning (or the clever potion) makes a skill try succeed at skill + 66% instead of + 33%; '
     'disliking it, + 16%. A success gains (70 - skill) ÷ 9, doubled for a liked skill and halved for a '
     'disliked one; a failure at 0 gives 4.', gm.RUNNING),
    ("Parenting is the exception: any failed try while Parenting is above 0 gives 4 (the stock game's own "
     'rule).', gm.RUNNING),
    ('Disliking work makes 76% of job picks end in doing nothing (21% otherwise, at Farming 60), and liking it, '
     'never; a villager who dislikes work leaves an assigned spot more often (a fishing spot is kept 47.5% of the '
     'time, 80% otherwise, always when work is liked). A preferred job wins 86% of the time. A villager other '
     'than the chief decides something only 35% of the time.', gm.RUNNING),
    ("Running: a liking adult walks at speed 300 (100 otherwise); a disliking villager of any age at 40, even "
     "running away (the same walk takes 146, 439 or 1,109 frames). Rain: liked, \"Drinking rain\"; disliked, "
     "\"Getting out of the rain\". Laundry: liked 37% of the time (10% otherwise), disliked never. Playing: a "
     "liking child picks from the plays; a disliking one makes no sandcastles or dirt play. Jumping: liked, a "
     "30-hop dance; disliked, no hops.", gm.RUNNING),
    ("Medicine, disliked: Healing is skipped half the time, and cures fall from 84% to 43%. Fish, the ocean or "
     "swimming, disliked: refused (\"Running away\"); fruit, bees, honey, rocks, lifting, plants, bushes or "
     "wood: 60% of those jobs become running away (a drop on the hive 60%, on the driftwood 50%); fire, "
     "alchemy, potions, caves or the dark: a drop on that spot is refused.", gm.RUNNING),
    ("Disliked dancing, talking, sand, resting, heights, herbs or flowers: that choice is never made; resting or "
     "sitting: a sick villager paces; children: storytelling is called off 69 times in 70; stories: an adult "
     "dropped on a child tells no story; crowds: left out of celebrations.", gm.RUNNING),
    ('The other 44 likes and dislikes: no effect has been found in the running game.', False),
    ("A baby starts with one skill at 5 to 7 (4 to 6 when both parents' best is the same), from the mother's "
     "best 98% of the time; never Parenting. Twins and triplets are the first baby's copies but for the name. "
     "The mother's Parenting rises at each conception.", gm.RUNNING),
    ('Sick: -1 health on 61% of age units above 20 health, 19.5% at 20 or below. Health comes back on 51% of '
     'age units (75% with the fire lit, every one at Medicine 3); the elderly 10% (14%, 21%).', gm.RUNNING),
    ('The campfire burns 10, 20 or 33 hours 20 minutes on Fast, Normal or Slow, stops while paused, and wood '
     'on a burning fire fills it again; while it burns a research payout gives 1 more tech point 10% of the '
     'time.', gm.RUNNING),
    ('The campfire burns out while the game is closed (a saved unpaused game); rain and the Omen stop it being '
     'lit.', False),
    ('The Ash Key: no timer and no chance. The fire must have burned 61 hours on Normal in all (30.5 on Fast, '
     '101.7 on Slow): a burnout counts its whole burn, wood added counts the time burned so far, water counts '
     'nothing, paused time nothing. Then 12 trips of water (the 4th puts a lit fire out; while it burns, 10 '
     "minutes between trips starts the count again); then, with the fire out, a villager dropped on the key's "
     'spot finds it.', gm.RUNNING),
)


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
    """The saved clock, with the village's start: the statistics block's first field (0x5824A0, written from
    the wall clock 0x403330 at 0x4646EB), wall seconds from the epoch."""
    return gm.later_clock(buf, CLOCK, epoch, _i32(buf, SPEED), _i32(buf, STATS))


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


TIMER_MAGIC = 0x54335656                 # 'V' 'V' '3' 'T'
TIMER_ENTRY = 40                         # fp (8), mode, count, 2 unused, interval, credit[3], due[3]
TIMER_ENTRIES = 16
TIMER_MODES = {1: "All Fruit Trees Refill at the Same Time", 2: "Fruit Trees Take Turns Refilling"}


@dataclass
class TreeSchedule:
    mode: int
    interval: int
    credit: list[int]                    # each tree's fruit is paid up to here (game seconds)
    due: list[int]                       # each tree's next refill (game seconds)

    @property
    def name(self) -> str:
        return TIMER_MODES.get(self.mode, "")


def _trees_fingerprint(buf: bytes) -> int | None:
    """FNV-1a 64 of the trees as the saver writes them -- their 0x14-byte header, `count` records and the
    count (native/shared/vv3_fruit_timers.h, fingerprint)."""
    count = _i32(buf, TREES + 0x5C)
    if not 0 <= count <= MAX_TREES:
        return None
    value = _fnv(buf[TREES:TREES + 0x14])
    value = _fnv(buf[TREES + 0x14:TREES + 0x14 + TREE_SIZE * count], value)
    return _fnv(struct.pack("<i", count), value)


def patch_tree_timers(village: gm.Village, buf: bytes) -> TreeSchedule | None:
    """The schedule "All Fruit Trees Refill at the Same Time" / "Fruit Trees Take Turns Refilling" keep
    for exactly this save, from their per-save file (the format of native/shared/vv3_fruit_timers.h,
    branch feat/vv3-trees-refill-together): the newest entry whose fingerprint is this save's trees.
    None when there is no file, it is not a valid one, or no entry matches -- the game then pays the
    fruit on the save's own (stock) timers.  Only read."""
    try:
        data = tree_timers_file(village).read_bytes()
    except OSError:
        return None
    if len(data) != 20 + TIMER_ENTRIES * TIMER_ENTRY:
        return None
    magic, version, game, slot, count = struct.unpack_from("<5I", data, 0)
    if magic != TIMER_MAGIC or version != 1 or game != GAME or slot != village.slot or count > TIMER_ENTRIES:
        return None
    fingerprint = _trees_fingerprint(buf)
    if fingerprint is None:
        return None
    for n in range(count - 1, -1, -1):
        at = 20 + n * TIMER_ENTRY
        lo, hi, mode, trees, _a, _b, interval = struct.unpack_from("<IIBBBBI", data, at)
        credit = list(struct.unpack_from("<3I", data, at + 16))
        due = list(struct.unpack_from("<3I", data, at + 28))
        if mode not in TIMER_MODES or trees > MAX_TREES or interval == 0:
            return None                  # the companion sets such a file aside: so does the page
        if (hi << 32 | lo) == fingerprint:
            return TreeSchedule(mode, interval, credit[:trees], due[:trees])
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
    if gm.speed_base(clock.speed) not in gm.SPEED_NAMES:
        return [gm.Fact("Other", f"{village.save.name} could not be read: its game speed is not one the game writes.")]
    out: list[gm.Fact] = []
    nature, second = nature_level(village.folder, village.slot, buf)
    patch = village.has(NATURE_PATCH)
    faster = nature >= 1 and patch is True
    interval = REFILL_PATCHED if faster else REFILL
    factor = 56 if faster else (42 if nature >= 1 else 37)
    per_refill = _gain(interval, factor)
    now = clock.game_now(village.now)
    # A past game second is dated only from the clock's base on; before it the line says how far into the
    # village it was (clock.moment) -- never a date worked back at today's speed, which the speed changes,
    # pauses and closed spells before the base would make wrong.
    at = clock.moment

    def sub(text: str, ok=False, due: float | None = None, kind: str | None = None) -> None:
        out.append(gm.Fact("Food sources", text, ok, sub=True, due=due, due_kind=kind if due is not None else None))

    sources: list[life.Source] = []

    # -- the fruit trees ------------------------------------------------------------------
    timers = patch_tree_timers(village, buf)
    trees = trees_of(buf)
    if not trees:
        out.append(gm.Fact("Food sources", "Fruit trees: none is planted yet."))
    for tree in trees:
        scheduled = timers is not None and tree.number <= len(timers.due)
        refilled = timers.credit[tree.number - 1] if scheduled else tree.refilled
        # The tree, then one sub-bullet for each fact about it (the owner, 2026-10-23).
        out.append(gm.Fact("Food sources", f"Tree {tree.number}: {tree.name}", gm.SAVE))
        sub(f"Planted {at(tree.planted, at=True)}; refills {gm.every(interval, clock.speed)}.")
        sub(f"{max(tree.fruit, 0)} of {FRUIT_CAP} fruit.", gm.SAVE)
        ready = tree.planted + READY
        if clock.frozen:
            sub("Ready to pick." if now >= ready else
                f"Ready to pick after {gm.duration(gm.real_seconds(ready - now, clock.runs_at))} more of play on "
                f"{gm.speed_name(clock.runs_at)} speed.")
        else:
            sub(f"Ready to pick since {at(ready)}." if now >= ready else f"Ready to pick from {at(ready)}.",
                due=clock.real(ready) if now < ready and clock.dated(ready) else None, kind="ready")
        due = timers.due[tree.number - 1] if scheduled else refilled + interval
        due_real = clock.real(due) if not clock.frozen and now < due and clock.dated(due) else None
        sources.append(life.Source(f"Tree {tree.number} ({tree.name})", max(tree.fruit, 0), FRUIT_CAP,
                                   per_refill * 360 / interval if interval else 0.0, due_real,
                                   f"+{per_refill} {gm.every(interval, clock.speed)}", verified=gm.SAVE))
        if scheduled:
            sub(f"On the patcher's \"{timers.name}\" schedule, read from its file for this save.")
        if tree.fruit >= FRUIT_CAP:
            sub("Full; a refill adds nothing until fruit is picked.")
        elif clock.frozen:
            left = max(0, due - now)
            sub(f"Next refill ({per_refill} fruit) after {gm.duration(gm.real_seconds(left, clock.runs_at))} more "
                f"of play{' once unpaused' if clock.paused else ''}." if left else
                f"A refill is due as soon as the game {'is unpaused' if clock.paused else 'is played'}.")
        elif now >= due:
            gained = min(_gain(now - refilled, factor), FRUIT_CAP - tree.fruit)
            sub(f"The next time the village is played it gets {gained} fruit: a refill was due {at(due, at=True)}.")
        else:
            sub(f"Next refill due {at(due)} ({min(per_refill, FRUIT_CAP - tree.fruit)} fruit).", due=due_real,
                kind="refill")

    # -- the honey ------------------------------------------------------------------------
    honey_at = _i32(buf, HONEY + 4)
    honey = _i32(buf, HONEY + 8)
    hive = _i32(buf, PUZZLES + 4 + 8 * BEE_HIVE) >= 1
    out.append(gm.Fact("Food sources", f"Honey: {honey} of {HONEY_CAP}"
                       + (" (The Bee Hive is solved)." if hive else " (The Bee Hive is not solved yet)."), gm.SAVE))

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
        f"{gm.speed_name(clock.runs_at)} speed."), gm.RUNNING))
    honey_every = HONEY_PATCHED if faster else HONEY_EVERY
    honey_gain = ((honey_every * 84) // 99900) if faster else ((honey_every * 2) // 3600)
    honey_due = honey_at + honey_every
    honey_real = (clock.real(honey_due) if not clock.frozen and honey < HONEY_CAP and now < honey_due
                  and clock.dated(honey_due) else None)
    if clock.frozen or honey >= HONEY_CAP:
        honey_next = "."
    elif now < honey_due:
        honey_next = f"; next due {at(honey_due)}."
    else:
        honey_factor_gain = (((now - honey_at) * 84) & 0xFFFFFFFF) // 99900 if faster else \
            (((now - honey_at) * 2) & 0xFFFFFFFF) // 3600
        honey_next = (f"; the next time the village is played it gets {min(honey_factor_gain, HONEY_CAP - honey)} "
                      f"(a gain was due {at(honey_due, at=True)}).")
    out.append(gm.Fact("Refills", (
        f"Honey: gains {honey_gain} {gm.every(honey_every, speed)}, up to {HONEY_CAP}{honey_next} By the time since "
        f"the last gain -- " + ", ".join(f"{gm.duration(gm.real_seconds(t, speed))} +{g}" for t, g in
                                       zip((2700, 3600, 10800, 36000), HONEY_PATCHED_GAINS if faster else HONEY_GAINS))
        + "."), gm.RUNNING,              # stock and patched (v1.35.81), reach traced (spec addendum 3)
        due=honey_real, due_kind="refill" if honey_real is not None else None))
    sources.append(life.Source("Honey" + ("" if hive else " (The Bee Hive not solved yet)"), honey, HONEY_CAP,
                               honey_gain * 360 / honey_every if hive else 0.0, honey_real,
                               f"+{honey_gain} {gm.every(honey_every, speed)}", verified=gm.SAVE))

    # -- the clock ------------------------------------------------------------------------
    if clock.paused:
        out.append(gm.Fact("Other", (
            f"The game's clock is stopped while paused; once unpaused it runs on {gm.speed_name(clock.runs_at)} "
            "speed. Times are real times from when its speed was last set; earlier ones are given as the village's age "
            "then, counted on Normal speed.")))
    elif clock.frozen:
        out.append(gm.Fact("Other", (
            f"The save's clock was written stopped; it runs again on {gm.speed_name(clock.runs_at)} speed once the "
            "village is played, so the time the game is closed does not count. Times are real times from when its speed was "
            "last set; earlier ones "
            "are given as the village's age then, counted on Normal speed.")))
    else:
        out.append(gm.Fact("Other", (
            f"The game's clock runs on {gm.speed_name(clock.runs_at)} speed, also while the game is closed "
            "(the next time it is played it catches up). Times are real times from "
            f"{gm.when(clock.restarted)} on, when its speed was last set; the save does not keep how it ran before "
            "then, so earlier times are given as the village's age then, counted on Normal speed.")))
    # The patcher's per-save files the page read, and where they disagree with the game as it is now.
    timer_file = tree_timers_file(village)
    if timer_file.is_file():
        village.notes.append(f"Read: {timer_file}.")
        if timers is not None:
            mode_id = {1: TOGETHER, 2: TAKE_TURNS}[timers.mode]
            if village.has(mode_id) is False:
                village.notes.append(
                    f"They disagree: this save's fruit-tree timers file holds a \"{timers.name}\" schedule, so that "
                    "patch was in the game when the village was last played, but the game's exe does not have it now. "
                    "The schedule is shown as the file has it; the game as it is now would not use it.")
    faction_file = Path(village.folder) / SAVES / f"Save {village.slot}" / FACTION_FILE.format(slot=village.slot)
    if faction_file.is_file():
        village.notes.append(f"Read: {faction_file}.")
        if second and village.has(BOTH_FACTIONS) is False:
            village.notes.append(
                "They disagree: this save's Both Factions file gives it a second faction, but the game's exe does not "
                "have the patcher's \"Both Factions\" now.")
    if timers is None and trees and tree_timers_file(village).is_file():
        out.append(gm.Fact("Other", (
            "The patcher's fruit-tree timers file is there but has no schedule for this save: the save's own "
            "refill times are shown, as the game uses them.")))
    out.extend(_village(village, buf, epoch, clock, nature, sources))
    return out


# ---------------------------------------------------------------------------
# The rest of the village (the coordinator's spec mech_vv3\spec.md, 2026-10-23; island events from
# docs/reports/island-event-conditions.txt, The Secret City)
# ---------------------------------------------------------------------------

FOOD = 0x4EC - HEADER                   # buffer offsets: the spec's file offsets less the 12-byte header
STATS = 0x4F0 - HEADER
MUSHROOMS_FOUND = STATS + 0x14
LAST_SAVED = 0x12F08 - HEADER               # wall seconds from the epoch
EVENT_NEXT = 0x12EF8 - HEADER               # wall seconds from the epoch
FIRE_END = 0x12125 + 4 - HEADER             # the fire record's burn deadline, wall seconds
FIRE_BURNED = 0x12125 + 0xC - HEADER         # its burning time in all, game seconds (the Ash Key's count)
FIRE_WATER = 0x12125 + 0x10 - HEADER         # its water trips counted
ASH_GATE = 219_600                           # game seconds of burning before the water trips count
# The chief's powers, ready again at (wall seconds; 0 = ready): rare collectible, educate, grant food.
CHIEF_READY = {"call a rare collectible (Leadership 3)": 0x12EFC - HEADER,
               "educate the children (Leadership 2)": 0x12F00 - HEADER,
               "grant food (Leadership 1)": 0x12F04 - HEADER}
SCIENCE, MEDICINE, ALCHEMY, LEADERSHIP = 0, 1, 2, 4
UNSURE = ""                              # every unverified line carries UNCONFIRMED
GOLDEN = "vv3_super_secret_golden_mushroom"
RARE_RETRY = "vv3_rare_collectible_retry"
MORTALITY = "vv3_nature_level_three_alters_mortality"
STORY = "vv3_story_cheat_upgrades"
SOURCE = "(from the patcher's island event report)"

EVENT_LINES = (
    "Which event: every one of the 57 events whose conditions hold is equally likely; if none qualifies, "
    "nothing happens. None is limited to once per village.",
    "Rescue: with 2 or fewer of the outnumbered sex, or fewer than 3 villagers, the event is instead The Crystal "
    "of Reflections 4.5% of the time, The Canoe from the Other Side 4.5% and Another One of Those Barrels 6%.",
    "Always possible: The Plague Of Ants, The Allergy Season, Isola Day Celebration, The Mysterious Fog (food "
    "gained, food lost, tech gained, tech lost), Blessings Day Celebration, The Reflection in the Water, The "
    "Rainy Season, The Salty Air, The Oppressive Humidity, \"Thick as Pea Soup\", The Stinging Jellyfish and The "
    f"Yellow Geckos {SOURCE}.",
    "Room for more villagers: The Canoe from the Other Side, Another One of Those Barrels, and with an adult, The "
    "Crystal of Reflections (a copy of the villager if it is kept). Day of Honor needs 2 graves; The Science Fair "
    "3 children; The Low Tide 8 villagers besides the chief (grabbing the fish sweeps each away at 20%, on a 50% "
    "coin); The Tsunami 15 of the 16 puzzles and 2 women and 2 men (each villager swept away at 15%).",
    "The Bee Hive solved: The Miraculous Bloom, and with an adult The Hole in the Hut. The Alchemy Lab solved: The "
    "Blue Pearl. Nature level 1: The Ghostly Dream (nature or healing); Magic level 1: The Ghostly Dream (research "
    "or architecture). Medicine level 2: The Medical Emergency. A burning fire: The Cold Snap. 500 mushrooms "
    "brought home: The Mushroom Celebration. A Tribal Chief: The Chief's Address.",
    "Science below level 2: The Bitter Brown Beans (taste or dye) and The Ancient Tablet (laundry or decoration); "
    "Science 2 or more: The Bitter Brown Beans (brew or fertilizer), and with Alchemy below 3 The Ancient Tablet "
    "(research or display).",
    "A child: The Ants and the Granary, The Playful Otters, The Ant Hill, The Shooting Star; with an adult of "
    "Research 30 or more, The Lazy Apprentice. A man of 18 or more and 2 women: The Daredevil. A woman and a "
    "man of 18 to 49: The Lovers (her gift, his gift). A woman of 18 to 49: Vanity and the Bee, The Noisy Bird.",
    "Any adult (or, for some, any villager): The Green Pearl, The Red Starfish, The Blue Starfish, Bed Bugs, The "
    "Royal Jelly, The Omen in the Clouds, The Mysterious Vial (quartz, obsidian, amber), The Mango and the "
    "Papaya (the swim decided by a 50% coin), The Return of Biggles; 3 adults of 18 to 49: The Mysterious Crate. "
    f"The weather events last about 3 to 6 minutes {UNSURE}.",
    "Rolled results: The Tsunami sweeps each villager away at 15%; The Daredevil (swims) the ladies swoon 75%, a "
    "crab bites 25%; The Medical Emergency (tried) recovery 50%, death 50%; The Mysterious Vial, obsidian or amber "
    "(tasted) three results at 33/33/34% (the quartz vial goes by age); The Mysterious Crate (opened) coconuts 50%, "
    "tarantulas 50% (sick and 10 to 29 health lost); The Omen in the Clouds one of 4 omens, 25% each; The Bitter "
    "Brown Beans (dye) one of two looks, 50% each; The Low Tide and The Mango and the Papaya a hidden 50% coin.",
    "The Mysterious Fog: food gained or lost (population ÷ 20 + 1) x 300, tech points gained or lost (population "
    "÷ 20 + 1) x 2,000; a loss takes no more than there is.",
    "Results on the villager picked: The Daredevil swoon Breeding +30, crab Breeding -5 to -14 and health -5 to -10; "
    "The Ghostly Dream Farming or Healing +21 to +39, or Research or Building +20; The Bitter Brown Beans taste food "
    "+200 and tech +1,000, brew food +600 and tech +2,000; The Green Pearl health +50 or Breeding +15 to +29; The "
    "Blue Pearl Research +20 to +34; The Lazy Apprentice (new teacher) Farming +21 to +39 and Building +10 to +19.",
    "The Omen in the Clouds (warn) omen 4 Research +15 to +24, (dance) sick; The Playful Otters Farming +15 to +29; "
    "The Ant Hill health -5 to -14; The Ants and the Granary Farming +5 to +9; Bed Bugs sick and health -5 to -9; "
    "Vanity and the Bee (swat) sick and health -15 to -24; The Lovers Breeding +25; The Medical Emergency success "
    "Healing +40, failure death; The Mysterious Vial quartz 20 years younger, amber Research +15 to +44 or 5 years "
    "younger and health +50; The Mysterious Crate coconuts food +500, tarantulas food +400, sick and health -10 to "
    "-29; The Royal Jelly Healing +15 to +29; The Shooting Star food +200 or Research +25 to +49; The Return of "
    "Biggles Research +20 to +44 or tech points.",
    "The Ghostly Dream needs Nature level 1 or more (nature or healing: Farming or Healing +20 to +39) or Magic "
    "level 1 or more (research or architecture: Research or Building +20), and a villager of 18 or more who is not "
    "pregnant or nursing and not the chief; skills stop at 100. With both factions both can happen, as separate "
    "events.",
)
ODDS_LINES = (
    "Brewing a potion blows up {blow}% of the time at Alchemy level {alchemy} (46%, 31%, 16% or 1% at Alchemy "
    "0 to 3).",
    "Conception: a roll of 300 + 50 - 50 x Medicine level (less a potion's help: 50 or 100) at or under Breeding; "
    "at Breeding 100 that is 17%, 33%, 51% or 67% at Medicine 0 to 3. Twins 5.3% and triplets 1.75%, at "
    "Medicine 3 only.",
    "Sickness, each age unit, with the fire lit or the hospital project done / without: 0.28% / 0.49% at "
    "Medicine 1, 0.17% / 0.30% at Medicine 2, 0.064% / 0.107% at Medicine 3; the elderly (from 42 years plus 8 "
    "for each Medicine level) 1.51% more. Easy halves these; Hard raises them.",
    "A sick villager is cured at Healing + 34%.",
    "A baby is born on the 41st age unit after conception. A healthy villager with food regains 1 health about "
    "half of the age units on Normal difficulty (every one on Easy); a sick one loses 1 health 61% of them. A "
    "successful building action adds 1 to the building, 2 when a supervising chief wins the Leadership roll.",
    "Potion effects last 10 minutes (feels smarter, scientific clarity, hiccups, garlic breath, bubble breath, crazy "
    "talk and two more), 5 minutes (light and springy, fertility +50, everyone slowing down, strong fertility +100) "
    "or happen at once (the rest, such as curing sickness), in real time.",
    "Herbs never run out: a bush can be gathered without limit once the Alchemy Lab is restored. A villager cannot "
    "drink a potion whose effect they already have, or any potion while they already have 4 effects.",
)


# The lines of EVENT_LINES and ODDS_LINES verified by emulation (the spec's addendum, section C and D).
VERIFIED_EVENT_LINES = {1, 8, 9, 10, 11, 12}   # rescue, rolled results, Fog, results, the Ghostly Dream
VERIFIED_ODDS_LINES = {0, 1, 2, 4, 5}       # blow-up, conception, sickness, life, potions


# Chance and timers (the coordinator's spec mech_vv3\spec.md, "Chance and timers (complete index)"):
# (line, verified on a traced path).  The full index of every roll is in the claims export.
CHANCE_LINES = (
    ("Every roll that decides an outcome is in the lines above; none is worked out from its range alone.", True),
    ("About 2,000 more random rolls inside villager actions (walking, timing, animation, speech), and about 650 "
     "more in the game update, the drop handlers, the island events' animations, the screens and the world "
     "objects: not individually worked out.", False),
    ("Timers: the game's clock runs 2 times, 1 time or 0.6 times real time on Fast, Normal or Slow, and stops while "
     "paused; an age unit is 3, 6 or 10 minutes, a year 1 hour, 2 hours or 3 hours 20 minutes; a birth 41 age "
     "units; a planted fruit tree can be picked after 4 hours, 8 hours or 13 hours 20 minutes; an item lies 90 "
     "seconds (still counting while paused, when no new ones appear).", True),
    ("A brewed potion keeps 5 minutes on Normal speed, 2 minutes 30 seconds on Fast and 8 minutes 20 seconds on "
     "Slow, as the pot's countdown shows.", False),
    ("Villagers re-decide what to do every 40 seconds at any speed; a fixed-spot coral appears for 90 seconds from "
     "puzzle code; the weather, fire and shark timers' lengths; the game may also save every 10 minutes while "
     "playing (not seen in a game: a 30-minute run left no new save).", False),
)


# A brewed potion waits in the pot (0x59454C) until a deadline 300 seconds ahead on 0x403330 (0x430E60, checked
# by 0x430F10), and the pot's countdown (0x469B53) shows what is left times the clock's rate / 6 (0x426580): 5
# minutes on Normal, 2 minutes 30 seconds on Fast, 8 minutes 20 seconds on Slow.  The owner sees its time change
# with the speed (2026-10-24); not timed in a game.  The pot is not saved, so no save holds a potion to count down.
POTION_KEEPS = {gm.FAST: "2 minutes 30 seconds", gm.NORMAL: "5 minutes", gm.SLOW: "8 minutes 20 seconds"}


def potion_line(speed: int) -> str:
    return (f"A brewed potion keeps {POTION_KEEPS[speed]} on {gm.speed_name(speed)} speed (5 minutes on Normal, "
            "2 minutes 30 seconds on Fast, 8 minutes 20 seconds on Slow), as the pot's countdown shows.")


def _village(village: gm.Village, buf: bytes, epoch: int, clock: Clock, nature: int,
             sources: list[life.Source] | None = None) -> list[gm.Fact]:
    out: list[gm.Fact] = []
    add = lambda group, text, ok=False: out.append(gm.Fact(group, text, ok))  # noqa: E731
    speed_value = clock.speed
    speed = clock.runs_at
    paused = clock.paused
    on = gm.speed_name(speed)
    level = [_i32(buf, TECHS + 4 * k) for k in range(7)]
    wall = lambda at: epoch + _i32(buf, at)  # noqa: E731

    def due(at: int) -> str:
        if paused:
            return f"{gm.duration(max(0, _i32(buf, at) - _i32(buf, LAST_SAVED)))} after it is unpaused"
        return gm.when(wall(at)) + (" (when the village is next played)" if wall(at) <= village.now else "")

    pick = {gm.FAST: 7, gm.NORMAL: 3, gm.SLOW: 2}[speed]          # the game's own rounding (the spec's addendum)
    add("Food sources", f"Food in storage: {_i32(buf, FOOD):,}.", gm.SAVE)
    add("Food sources", f"Picking fruit or honey brings {pick} on {on} speed (7, 3 or 2 on Fast, Normal or Slow, by "
                        "the game's own rounding; 4 while catching up); honey is gathered only above 10.")
    add("Food sources", f"Fishing brings { {gm.FAST: 11, gm.NORMAL: 8, gm.SLOW: 5}[speed] } on {on} speed (8 while "
                        "catching up).", True)
    # The big catch is a crab (the owner, 2026-10-23; the code's carried item 9, "Crab" in the carry-name
    # table 0x4A8A14, against 8 "Fish" for the plain catch, 0x4535AF / 0x4535F3).
    add("Food sources", "A fisher with Farming 88 or more has a 10% chance of catching a crab, worth 55 food; the sea "
                        "never runs out.")

    add("Mushrooms", "While playing (not paused), about one thing appears a minute at any speed, about every 30 "
                     "seconds in storms; each is gone after 1 minute 30 seconds unpicked.", True)
    add("Mushrooms", "At most 2 are out at a time.")
    # Brown and red are the owner's words (2026-10-23); the code calls the 35-food one the rare mushroom
    # (eCarrying_RareShroom 0x481224, item 0x65; the brown one eCarrying_Shroom, item 0x64).
    add("Mushrooms", "In fair weather 30% of them are mushrooms, in rain all: 92% are brown mushrooms worth 6 food, 8% "
                     "red (rare) mushrooms worth 35, counted when they reach the food bin.", gm.RUNNING)
    if village.has(GOLDEN):
        add("Mushrooms", gm.golden_line(GOLDEN, "about 6 years of play in fair weather"), gm.RUNNING)
    add("Mushrooms", f"Mushrooms found in this village: {_i32(buf, MUSHROOMS_FOUND):,}.", gm.SAVE)
    add("Collectibles", "The others are collectibles: common 83%, uncommon 13%, rare 4%. A piece already found "
                        "gives 100, 250 or 1,500 tech points by rarity.", gm.RUNNING)
    add("Collectibles", "Tablet pieces already owned never appear again; coral, feather and turtle shell pieces "
                        "keep appearing, and each one already owned pays its tech points.", gm.RUNNING)
    add("Collectibles", "The tablet collection appears once its project is started; a full collection raises the "
                        "population limit by 5, all four by 25.")
    add("Collectibles", "A Tribal Chief with Leadership 3 can call a rare collectible every 23 hours; it fails "
                        "only when it picks a rare tablet piece already owned.", gm.RUNNING)
    if village.has(RARE_RETRY) is not False:
        add("Collectibles", gm.patch_words(village, RARE_RETRY, "a failed call is tried again"))

    add("Tech points and effects", f"Tech points: {_i32(buf, POINTS):,}.", gm.SAVE)
    divisor = {0: 5, 1: 11, 2: 9, 3: 7}.get(level[SCIENCE], 7)
    catch = {0: 4, 1: 7, 2: 7, 3: 5}.get(level[SCIENCE], 5)
    speed_words = {gm.FAST: "twice that on Fast speed", gm.NORMAL: "as it is on Normal speed",
                   gm.SLOW: "0.6 of it on Slow speed" if level[SCIENCE] else "half of it on Slow speed"}[speed]
    add("Tech points and effects", (
        f"Research gives Research skill ÷ {divisor} at Science level {level[SCIENCE]}, {speed_words}"
        + (" -- 1 point less on Normal speed, by the game's own rounding" if level[SCIENCE] >= 1 else "")
        + f"; a lit fire adds a 10% chance of 1 more; while catching up ÷ {catch}."))
    blow = max(0, 15 * (3 - level[ALCHEMY]) + 1)
    add("Tech points and effects", ODDS_LINES[0].format(blow=min(blow, 100), alchemy=level[ALCHEMY]), gm.RUNNING)
    add("Tech points and effects", potion_line(speed))

    add("Food earned", f"Each villager eats 2 food every {gm.duration(60 * speed)} on {on} speed "
                       f"({2 * 3600 / (60 * speed):g} an hour) while there is more than 500; at Normal difficulty 2 "
                       "more 76% of the time at 8,000 food or more, on Hard always, on Easy never. At 500 or less "
                       "a villager eats half the time, and otherwise loses 1 health 30% of the time; with no food "
                       "at all a villager loses 1 or 2 health about two times in three.", gm.RUNNING)

    out.extend(gm.time_away(village, wall(LAST_SAVED), speed_value,
                            "Saved paused: nobody ages, the clock is stopped and the next island event is pushed "
                            "back by the time away; nothing advances.", unit_seconds=20 * 60 * speed))
    add("Time away and Time Warp", "The fruit trees and the honey get the whole time away when it is next played "
                                   "(the game's clock ran on), with no limit on how many refills: the honey stops at "
                                   "3,000, a tree at 1,000.", True)
    add("Time away and Time Warp", "While catching up every healthy adult does 4 jobs each age unit, without walking; "
                                   "mushrooms and collectibles do not pile up and only one overdue island event "
                                   "happens.")
    out.append(gm.time_warp_line(speed_value))

    add("Island events", f"Next island event: {due(EVENT_NEXT)}.", gm.SAVE)
    add("Island events", f" Island events come every 8 to 15 whole hours at any "
                         "speed, each hour about equally likely; the first of each time the game is started comes "
                         "30 minutes after it.", gm.RUNNING)
    add("Island events", "A new village's first event comes 15 minutes after it is made; paused time does not count.")
    for n, line in enumerate(EVENT_LINES):
        add("Island events", line, gm.RUNNING if n in VERIFIED_EVENT_LINES else False)
    if village.has(STORY) is not False:
        add("Island events", gm.patch_words(village, STORY, "Pick Island Event chooses the event"))

    fire = wall(FIRE_END)
    add("Other", ("The fire " + (f"burns until {gm.when(fire)}" if fire > village.now and not paused else
                                 "is out" if not paused or fire <= wall(LAST_SAVED)
                                 else f"was burning when saved, with {gm.duration(fire - wall(LAST_SAVED))} left")
                  + "; while it burns sickness is lower and research gets its 10% chance of 1 more."))
    for n, line in enumerate(ODDS_LINES[1:], 1):
        add("Other", line, gm.RUNNING if n in VERIFIED_ODDS_LINES else False)
    extra = ""
    if level[5] >= 3 or nature >= 3:
        extra = gm.patch_words(village, MORTALITY, "at Nature level 3 the rolls start 7 years later")
    out.append(gm.old_age_line("47, 55, 63 or 71 years (Medicine 0 to 3)", extra))
    for line, ok in HIDDEN_LINES:
        add(gm.HIDDEN, line, ok)
    burned, water = _i32(buf, FIRE_BURNED), _i32(buf, FIRE_WATER)
    add(gm.HIDDEN, (f"This village's Ash Key count: the campfire has burned {gm.duration(burned)} in all, counted on "
                    f"Normal speed, of the {gm.duration(ASH_GATE)} needed"
                    + (", so the gate is open" if burned >= ASH_GATE else "") + f"; water trips counted: {water}."),
        gm.RUNNING)
    out.extend(gm.starvation_lines(village, 0x8, gm.RUNNING))
    for line, ok in CHANCE_LINES:
        add("Chance and timers", line, gm.RUNNING if ok else False)
    leadership = level[LEADERSHIP]
    ready = []
    for words, at in CHIEF_READY.items():
        stamp = _i32(buf, at)
        ready.append(f"{words}: " + ("ready" if stamp == 0 or wall(at) <= village.now else gm.when(wall(at))))
    add("Other", "The Tribal Chief's powers each wait 23 hours after use, at any speed, paused or closed: "
                 + "; ".join(ready) + f". Granting food gives 3 x Leadership x 10 to 29 (Leadership is {leadership}).")
    out.append(gm.started_line(clock.created))
    out.extend(gm.later_puzzle_lines(
        PUZZLE_NAMES, lambda pid: struct.unpack_from("<ii", buf, PUZZLES + 4 + 8 * pid), PUZZLE_THRESHOLDS, clock))

    # -- The countdowns, and the people and clocks (src/vv_game_mechanics_life.py) ------------
    event_at = None if paused else wall(EVENT_NEXT)
    gm.with_due(out, "Next island event:", event_at, "next")
    if not paused and fire > village.now:
        gm.with_due(out, "The fire burns until", fire, "ends")
    village_extra = []
    for words, at in CHIEF_READY.items():
        if _i32(buf, at) != 0 and wall(at) > village.now:
            village_extra.append(gm.Fact(life.VILLAGE_TIMERS, f"The Tribal Chief's power to {words.split(' (')[0]}: "
                                         f"ready again {gm.when(wall(at))}.", gm.SAVE, due=wall(at),
                                         due_kind="ready"))
    if not paused and fire > village.now:
        village_extra.append(gm.Fact(life.VILLAGE_TIMERS, f"The campfire burns until {gm.when(fire)}.", gm.SAVE,
                                     due=fire, due_kind="ends"))
    puzzles = []
    for pid, name in PUZZLE_NAMES.items():
        progress = struct.unpack_from("<i", buf, PUZZLES + 4 + 8 * pid)[0]
        if 0 < progress < PUZZLE_THRESHOLDS[pid]:
            puzzles.append((name, progress, PUZZLE_THRESHOLDS[pid]))
    pick_food = {gm.FAST: 7, gm.NORMAL: 3, gm.SLOW: 2}[speed]
    srcs = list(sources or [])
    srcs.append(life.Source("Fishing", None, unlimited=True, refill_words="the sea never runs out", verified=gm.RUNNING))
    ctx = life.Context(
        village, speed_value, wall(LAST_SAVED), _i32(buf, FOOD), low_food=500, extra_from=8000, sources=srcs,
        tech=_i32(buf, POINTS), tech_words=f"Research brings them (the skill ÷ {divisor} at Science level "
                                           f"{level[SCIENCE]}); a piece already found pays 100, 250 or 1,500 by rarity.",
        brown=6, red=35, red_share=0.08, mushrooms_an_hour=18.0, golden=village.has(GOLDEN) is True,
        mushroom_words="About one thing appears a minute while playing (not paused), 30% of them mushrooms in fair "
                       "weather and all of them in rain, so about 18 mushrooms an hour in fair weather.",
        event_next=event_at,
        event_paused_left=max(0, _i32(buf, EVENT_NEXT) - _i32(buf, LAST_SAVED)) if paused else None,
        event_rule="It comes 8 to 15 whole hours after the last, at any speed, each hour about equally likely; the "
                   "first each time the game is started comes 30 minutes after it; then each of the 57 events whose "
                   "conditions hold is equally likely.",
        event_running="Paused time does not count; with the game closed it runs on, and after time away only one "
                      "overdue event happens; the catch-up adds none.",
        medicine=level[MEDICINE], elderly_from={0: 42, 1: 50, 2: 58, 3: 66}, old_age_from={0: 47, 1: 55, 2: 63, 3: 71},
        parents_from=14, sick_loss=(0.61, 0.195),
        sick_end="A healer cures a sick villager at Healing + 34%.",
        collectibles=life.collectible_lines(village, "100, 250 or 1,500 tech points")[0],
        limit=life.limit_words(village, None, "5 for each complete collection, 25 with all four, and 10 at Magic "
                                              "level 3"),
        puzzles=puzzles, village_extra=village_extra,
        food_words="2 food a villager every age unit while there is more than 500; on Medium at 8,000 or more, or "
                   "on Hard, 2 more 76% of the time (always on Hard); never more on Easy.",
        trips=[("fruit or honey picks", pick_food), ("fishing trips", {gm.FAST: 11, gm.NORMAL: 8, gm.SLOW: 5}[speed])])
    out.extend(life.sections(ctx))
    return out


# The 16 puzzles by id (the game's own names, as the patcher's Story Cheat Upgrades lists them,
# native/vvfp_story_upgrades/story_c3.inc), each solved at the threshold the game's table 0x49D230 holds.
PUZZLE_NAMES = {0: "The First Chief", 1: "The Bee Hive", 2: "The Alchemy Lab", 3: "The Roster of the Dead",
                4: "Weather Dancing", 5: "The Lift", 6: "The Ruins", 7: "The Ancient Bath", 8: "The Statue",
                9: "The Orchard", 10: "The Sharks", 11: "Aromatherapy", 12: "The Ash Key", 13: "The Cliff Key",
                14: "The Clam Key", 15: "The Chief and the Princess"}
PUZZLE_THRESHOLDS = dict(enumerate((1, 1, 5, 700, 1, 1, 1800, 1400, 2, 1, 1, 6, 1, 1, 1, 1)))
