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
import vv_game_mechanics_death as death
from vv_game_mechanics_chances import at_most, chance
import vv_game_mechanics_events as events
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
    # The skill test 0x45A2C0: rand(100) <= skill + 33, + 66 when learning is liked or the "feels smarter" effect
    # (3) is on, + 16 when it is disliked (0x45A309..0x45A31B); a success gains (70 - skill) / 18 (0x45A455, Farming),
    # doubled or halved by liking or disliking LEARNING, not the skill (0x45A476..0x45A48D).  An earlier line here
    # said "+ 66% instead of + 33%" and "(70 - skill) / 9, doubled for a liked skill": both wrong.  The doubling
    # reads only the likes flag ([esp+0x13], set from 0x4547B0 on the likes list +0xFB4 at 0x45A2F1): the potion's
    # effect 3 (0x455E10 at 0x45A300) raises only the test's bonus, never the gain.
    ('Liking learning makes every skill test easier and every skill gain twice as big; the potion effect "feels '
     'smarter" makes the test just as easy but does not change the gain; disliking learning makes the test harder '
     'and the gain half as big. The exact chances and gains are under Chances (The skill test).', gm.CODE),
    # 0x45A554: a failed Parenting test gives +4 when Parenting is above 0; the other skills only at exactly 0.
    ("Parenting is the exception: any failed try while Parenting is above 0 gives 4 (the stock game's own "
     'rule).', gm.RUNNING),
    # The job chooser 0x459730: rand(100) < 15 and work not liked -> no job (0x459746); work disliked -> rand(100) <
    # 70 -> no job (0x459783).  The earlier "76% ... (21% otherwise, at Farming 60)" and "35%" (the try is 34 values
    # in 100, 33.94%: Chances) did not follow from it; the 86% preference is in Chances.
    ('Work: a villager who does not like work takes no job on 15% of job picks, and one who dislikes it on 70% of '
     'the others too; one who likes work skips that 15% (Chances, Choosing a job). A villager who dislikes work '
     'leaves an assigned spot more often (a fishing spot is kept 47.5% of the time, 80% otherwise, always when work '
     'is liked).', gm.RUNNING),
    ("Running: a liking adult walks at speed 300 (100 otherwise); a disliking villager of any age at 40, even "
     "running away (the same walk takes 146, 439 or 1,109 frames). Rain: liked, \"Drinking rain\"; disliked, "
     "\"Getting out of the rain\". Laundry: liked 37% of the time (10% otherwise), disliked never. Playing: a "
     "liking child picks from the plays; a disliking one makes no sandcastles or dirt play. Jumping: liked, a "
     "30-hop dance; disliked, no hops.", gm.RUNNING),
    # Healing passed over: rand(100) < 50 (0x459808); a cure that passes fails rand(100) < 50 (0x4573B5): at Healing
    # 50, 84.03% x 49.95% = 41.97% (an earlier "84% to 43%" was off by one point).
    ("Medicine, disliked: Healing is passed over half the time when a job is chosen, and half of the cures that pass "
     "the Healing test fail anyway (at Healing 50 a cure works 42% of the time instead of 84%). Fish, the ocean or "
     "swimming, disliked: refused (\"Running away\"); fruit, bees, honey, rocks, lifting, plants, bushes or "
     "wood: 60% of those jobs become running away (a drop on the hive 60%, on the driftwood 50%); fire, "
     "alchemy, potions, caves or the dark: a drop on that spot is refused.", gm.RUNNING),
    ("Disliked dancing, talking, sand, resting, heights, herbs or flowers: that choice is never made; resting or "
     "sitting: a sick villager paces; children: storytelling is called off 69 times in 70; stories: an adult "
     "dropped on a child tells no story; crowds: left out of celebrations.", gm.RUNNING),
    ('The other 44 likes and dislikes: no effect has been found in the running game.', False),
    # The traced chain: 0x4582A0 picks the mother's best skill 0x462460 (Parenting can be it), the father's on
    # rand(50) == 0, and passes it to the pregnancy writer 0x455AB0 as its 2nd argument; there a skill of 1
    # (Parenting) is stored as skill 0 with 0 points (0x455B1C..0x455B39, record +0xE3C / +0xE40), which the birth
    # 0x4603B6 -> 0x45FF90 -> 0x45F0B0 -> 0x456120 writes as Farming 0 (0x456470): so never Parenting, and no skill.
    ("A baby starts with one skill at 5 to 7 (4 to 6 when both parents' best is the same), from the mother's "
     "best 98% of the time; never Parenting: when the skill chosen is Parenting the baby starts with no skill at "
     "all. Twins and triplets are the first baby's copies but for the name. "
     "The mother's Parenting rises at each conception.", gm.RUNNING),
    # The aging loop 0x45FFE0: sick -1 at rand(100) <= 60, at 20 or less also rand(100) <= 30 (0x46017D, 0x460195):
    # 61.06% and 18.95%; health back rand(100) < 50, else Easy / fire + rand(100) < 50 / Medicine 3 (0x4601E6..
    # 0x46022E), the elderly rand(100) < 20 of those (0x46023D): 10.0%, 15.0%, 20.0%.  An earlier line said 19.5%,
    # 51% and "10% (14%, 21%)": wrong, and the same rules are in Chances.
    ('Health lost while sick and health coming back, for the young and the elderly: Chances (A sick villager\'s '
     'health, Regaining health).', gm.CODE),
    # The fire 0x5946D8: lit or refuelled with a 72,000-game-second timer (0x433A33, 0x433AF5) on the game clock.
    ('The campfire burns 20 hours of the game\'s clock: 10, 20 or 33 hours 20 minutes of real-life play on Fast, '
     'Normal or Slow (0x433A33); it stops while paused, and wood on a burning fire fills it again (0x433AF5). What a '
     'burning fire changes is under Chances (Regaining health, Falling sick, Research).', gm.CODE),
    # The owner (2026-10-24): the fire runs out when its timer expires; rain and the weather do not affect it (an
    # earlier line here said rain and the Omen stopped it being lit: false).  Its timer is a real-time deadline the
    # game clock 0x5825D4 shifts by the time paused and rescales at a speed change (0x426630, src/vv_save_clock.py),
    # so it also runs out while the game is closed, as the save's deadline shows.
    ('The campfire goes out when its timer runs out; rain and the weather do not affect it. Four trips of water '
     'for the Ash Key put a lit fire out.', gm.OWNER),
    # The Cold Snap (cond 0x415100) needs the fire burning and only sets the weather; no event ends the fire.
    ('No island event in this game puts the fire out: The Cold Snap needs it burning and leaves it lit.',
     gm.RUNNING),
    (gm.FIRE_CLOSED, gm.OWNER),
    # Breeding age (the owner, 2026-10-25): nobody under 18 breeds, but the owner has seen The Lovers choose a
    # teenager.  The code: every embrace checks both ages >= 360 (0x45854C..0x458565), the partner search too
    # (0x45CE3F, 0x45CE51); The Lovers' conditions 0x416ED0 / 0x417050 pick both lovers with 0x45D460 mode 2,
    # age [+0xDC4] 360..999 and the woman not carrying (0x45D4CC..0x45D4EF), never the chief (arg 3); the knife
    # (0x416F8B) or flowers (0x41710A) gives both +25 Breeding and calls 0x4582A0, which conceives at once
    # (0x455AB0: room check 0x45FE30, no conception roll, no age check).
    ("Breeding age: no villager under 18 has children, but the owner has seen The Lovers island event choose a "
     "teenager.", gm.OWNER),
    ("The Lovers in the game's code: both lovers are picked only from villagers of 18 to 49.95 villager years "
     "(360 to 999 age units), the woman not pregnant or nursing, neither one the Tribal Chief; if she carves the "
     "knife or he gives the flowers, both gain 25 Parenting and she conceives at once when there is room for a "
     "baby, with no conception roll and no age check of its own. Every other embrace needs both villagers 18 "
     "or older.", gm.RUNNING),
    ('The Ash Key: no timer and no chance. The fire must have burned 61 hours of real-life play on Normal speed in '
     "all (30.5 on Fast, 101.7 on Slow; on the game's clock): a burnout counts its whole burn, "
     'wood added counts the time burned so far, water counts nothing, paused time nothing. Then 12 trips of water '
     '(the 4th puts a lit fire out; while it burns, 10 minutes between trips starts the count again -- 10 minutes '
     "on the game's clock, 5, 10 or 16 minutes 40 seconds of real-life play on Fast, Normal or Slow: each trip "
     "sets a timer 600 seconds ahead on the game's clock, 0x433BCA -> 0x426790); then, with the fire "
     "out, a villager dropped on the key's spot finds it.", gm.RUNNING),
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


def _tree_steps(clock: Clock, now: int, due: int, interval: int, amount: int, credited: int, gain) -> dict:
    """A tree's or the honey's refill steps for the time to fill up (vv_game_mechanics_life.Source): the next refill
    comes at its due time (or as soon as the village is played, when it is overdue) and gains `gain(elapsed)` for all
    the time since `credited` -- the stock formula (0x434760, 0x4319B0) -- then `amount` every `interval` game
    seconds, in real time at the clock's speed."""
    out = {"step": amount, "interval": gm.real_seconds(interval, clock.runs_at)}
    if clock.frozen:
        out["first_in"] = gm.real_seconds(max(0, due - now), clock.runs_at)
        out["first_step"] = gain(max(0, due - credited))
    else:
        first = max(due, now)
        out["first_step"] = gain(max(0, first - credited))
        if clock.dated(first):
            out["next_at"] = clock.real(first)
    return out


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
        out.append(gm.Fact("Food sources", "Fruit trees: none is planted yet.", gm.SAVE))
    # The tree lines: the save's own times and fruit, worked through the game's own rules (the refill 0x434760, the
    # "ready" test 0x434030; the patches' schedule from their file) -- read from reachable code, so no label.
    for tree in trees:
        scheduled = timers is not None and tree.number <= len(timers.due)
        refilled = timers.credit[tree.number - 1] if scheduled else tree.refilled
        # The tree, then one sub-bullet for each fact about it (the owner, 2026-10-23).
        out.append(gm.Fact("Food sources", f"Tree {tree.number}: {tree.name}", gm.SAVE))
        sub(f"Planted {at(tree.planted, at=True)}; refills {gm.every(interval, clock.speed)}.", gm.CODE)
        sub(f"{max(tree.fruit, 0)} of {FRUIT_CAP} fruit.", gm.SAVE)
        ready = tree.planted + READY
        if clock.frozen:
            sub("Ready to pick." if now >= ready else
                f"Ready to pick after {gm.duration(gm.real_seconds(ready - now, clock.runs_at))} more of play on "
                f"{gm.speed_name(clock.runs_at)} speed.", gm.CODE)
        else:
            sub(f"Ready to pick since {at(ready)}." if now >= ready else f"Ready to pick from {at(ready)}.", gm.CODE,
                due=clock.real(ready) if now < ready and clock.dated(ready) else None, kind="ready")
        due = timers.due[tree.number - 1] if scheduled else refilled + interval
        due_real = clock.real(due) if not clock.frozen and now < due and clock.dated(due) else None
        sources.append(life.Source(f"Tree {tree.number} ({tree.name})", max(tree.fruit, 0), FRUIT_CAP,
                                   per_refill * 360 / interval if interval else 0.0, due_real,
                                   f"+{per_refill} {life.every_real(interval, clock.speed)}", verified=gm.SAVE,
                                   **_tree_steps(clock, now, due, timers.interval if scheduled else interval,
                                                 _gain(timers.interval, factor) if scheduled else per_refill,
                                                 refilled, lambda t: _gain(t, factor))))
        if scheduled:
            sub(f"On the patcher's \"{timers.name}\" schedule, read from its file for this save.", gm.SAVE)
        if tree.fruit >= FRUIT_CAP:
            sub("Full; a refill adds nothing until fruit is picked.", gm.CODE)
        elif clock.frozen:
            left = max(0, due - now)
            sub(f"Next refill ({per_refill} fruit) after {gm.duration(gm.real_seconds(left, clock.runs_at))} more "
                f"of play{' once unpaused' if clock.paused else ''}." if left else
                f"A refill is due as soon as the game {'is unpaused' if clock.paused else 'is played'}.", gm.CODE)
        elif now >= due:
            gained = min(_gain(now - refilled, factor), FRUIT_CAP - tree.fruit)
            sub(f"The next time the village is played it gets {gained} fruit: a refill was due {at(due, at=True)}.",
                gm.CODE)
        else:
            sub(f"Next refill due {at(due)} ({min(per_refill, FRUIT_CAP - tree.fruit)} fruit).", gm.CODE,
                due=due_real, kind="refill")

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
    # Saved paused, the game clock 0x5825D4 is stopped (rate 0: 0x426590 adds nothing), and the trees and honey
    # follow it (0x434760, 0x4319B0).
    if clock.paused:
        out.append(gm.Fact("Refills", gm.PAUSED_NOTE, gm.CODE))
    out.append(gm.Fact("Refills", (
        f"Fruit trees: each gains {per_refill} fruit {gm.every(interval, speed)}, up to {FRUIT_CAP}; {nature_words}. "
        f"{patch_words}"), gm.CODE))
    if not faster:
        alt = []
        if nature < 1:
            alt.append(f"at Nature level 1 or more: {_gain(REFILL, 42)} fruit {gm.every(REFILL, speed)}")
        if patch is not False:
            alt.append(f"with the patch and Nature level 1 or more: {_gain(REFILL_PATCHED, 56)} fruit "
                       f"{gm.every(REFILL_PATCHED, speed)}")
        if alt:
            out.append(gm.Fact("Refills", "Fruit trees otherwise: " + "; ".join(alt) + ".", gm.CODE))
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
                               f"+{honey_gain} {life.every_real(honey_every, speed)}", verified=gm.SAVE,
                               **(_tree_steps(clock, now, honey_due, honey_every, honey_gain, honey_at,
                                              (lambda t: ((t * 84) & 0xFFFFFFFF) // 99900) if faster
                                              else (lambda t: ((t * 2) & 0xFFFFFFFF) // 3600)) if hive else {})))

    # -- the clock (0x5825D4: "now" 0x426590, reset at every speed change or pause 0x426630) --------------
    if clock.paused:
        out.append(gm.Fact("Other", (
            f"The game's clock is stopped while paused; once unpaused it runs on {gm.speed_name(clock.runs_at)} "
            "speed. Times are real times from when its speed was last set; earlier ones are given as the village's age "
            "then, counted on Normal speed."), gm.CODE))
    elif clock.frozen:
        out.append(gm.Fact("Other", (
            f"The save's clock was written stopped; it runs again on {gm.speed_name(clock.runs_at)} speed once the "
            "village is played, so the time the game is closed does not count. Times are real times from when its speed was "
            "last set; earlier ones "
            "are given as the village's age then, counted on Normal speed."), gm.CODE))
    else:
        out.append(gm.Fact("Other", (
            f"The game's clock runs on {gm.speed_name(clock.runs_at)} speed, also while the game is closed "
            "(the next time it is played it catches up). Times are real times from "
            f"{gm.when(clock.restarted)} on, when its speed was last set; the save does not keep how it ran before "
            "then, so earlier times are given as the village's age then, counted on Normal speed."), gm.CODE))
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
            "refill times are shown, as the game uses them."), gm.SAVE))
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

# The brew's blow-up (0x430A92: rand(100) <= 15 x (3 - Alchemy)), at this save's level; every level's exact chance is
# in Chances (Brewing a potion).
BLOW_LINE = ("Brewing a potion blows up {blow} of the time at this village's Alchemy level {alchemy} (every level: "
             "Chances, Brewing a potion).")
# The rules the Other group once repeated -- conception, sickness, curing, health and building -- are each given
# once, exactly, under Chances and Births and gender (the Game Mechanics audit, 2026-10-25: an earlier copy here had
# "a roll of 300", "17%, 33%, 51%", "the hospital project", "Easy halves these" and "on Normal difficulty", all wrong
# against the code: rand(300) at 0x4586E1; 17.12%, 33.8%, 50.44%, 67.07%; the fire or Aromatherapy, 0x455C00; Easy
# rolls only 24.95% of age units, 0x460282 and 0x455C14; the game's word is "Medium").
POTION_EFFECTS_LINE = (
    "Potion effects are kept 10 real-life minutes (real time, the same at every speed: the end is a moment on the "
    "computer's clock, 0x403330, so paused time counts too, and saving ends every effect) (feels smarter, scientific clarity, hiccups, much healthier, feels "
    "better with 10 to 14 health, stinky breath, tasted soapy, crazy talk), 5 real-life minutes (light and springy, "
    "fertile +50, everyone else slowing down, very fertile +100), with no time limit (the two vials carried to the "
    "ocean) or not at all (the rest, such as curing sickness, which happen at once).")
HERBS_LINE = (
    "Herbs never run out: a bush can be gathered without limit once the Alchemy Lab is restored. A villager cannot "
    "drink a potion whose effect they already have, or any potion while they already have 4 effects.")


# The lines of EVENT_LINES verified by emulation (the spec's addendum, section C and D).
VERIFIED_EVENT_LINES = {1, 8, 9, 10, 11, 12}   # rescue, rolled results, Fog, results, the Ghostly Dream


# Chance and timers (the coordinator's spec mech_vv3\spec.md, "Chance and timers (complete index)"):
# (line, verified on a traced path).  The full index of every roll is in the claims export.
CHANCE_LINES = (
    ("Every roll that decides an outcome is in the lines above; none is worked out from its range alone.", True),
    ("About 2,000 more random rolls inside villager actions (walking, timing, animation, speech), and about 650 "
     "more in the game update, the drop handlers, the island events' animations, the screens and the world "
     "objects: not individually worked out.", False),
    ("Timers: the game's clock runs 2 times, 1 time or 0.6 times real time on Fast, Normal or Slow, and stops while "
     "paused; an age unit is 3, 6 or 10 real-life minutes, a villager year 1 hour, 2 hours or 3 hours 20 minutes "
     "of real life; a birth 41 age units; a planted fruit tree can be picked after 4, 8 or 13 hours 20 minutes of "
     "real life; an item lies 90 real-life seconds (still counting while paused, when no new ones appear); a clear "
     "sky lasts 15 to 30 real-life minutes on Normal speed and any other weather 3 to 6 (0x41FB40).", True),
    # (The brewed potion's countdown is under Tech points and effects; the 40-second re-decision under Chances; the
    # fire's 20 game hours, 0x433A33, under Hidden villager stats.)  0x427DD0 calls 0x427D90, which saves the
    # settings, the slot and slot + 20, once 600 seconds of the system clock 0x401ED0 have passed.  It is called at
    # 0x427B40, the last step of the game object's per-frame update 0x427720 (vtable slot 0x1C), skipped only while
    # the start-up loading step [+0x2C] is 6 or less (0x427B37); gm.autosave_line has the five games' trace.
    ("Not traced: how long a fixed-spot coral from puzzle code stays out, and the sharks' timer (so their clocks, "
     "real time or on the game's clock, are not known).", False),
    # A live run of The Secret City, written down in the Game Mechanics audit of 2026-10-25 (commit 72b88737): a
    # village played for 30 minutes left no new save.  The code says otherwise (Autosave above); the owner,
    # 2026-10-27: "for cases where the code contradicts live observation write both cases down".
    ("Seen in a live run of the game made for the Game Mechanics audit: a village played for 30 minutes of real "
     "time left no new save, while the game's code saves every 10 real-life minutes at every speed (Autosave above: the per-frame update "
     "0x427720 runs the save check 0x427DD0 at 0x427B40). What that run did differently was not recorded, so the "
     "difference is not explained.", False),
)


# A brewed potion waits in the pot (0x59454C) until a deadline 300 seconds ahead on the wall clock 0x403330
# (0x430E60; the pot's update 0x430F10 spoils it there through 0x430D00 / 0x430350), and the pot's countdown
# (0x469B53) shows what is left times the clock's rate / 6 (0x426580) as m:ss: 5:00 on Normal, 2:30 on Fast,
# 8:20 on Slow.  The owner sees its time change with the speed (2026-10-24).  The pot is not saved (its save and
# load slots are the no-ops 0x436170 / 0x436180), so no save holds a potion to count down.
# The owner (2026-10-24), and the code: a villager dropped on the herb table (0x59454C's drop slot 0x430D90)
# runs 0x430D00, which throws the brewed potion away (0x430350 on the pot 0x593BA0) and puts the table's
# herbs back as they were -- the same routine the spoil timer 0x430F10 runs.
POT_EMPTIED_LINE = ("The pot can be emptied by dropping a villager on the table with 3 herbs: the brewed potion is "
                    "thrown away and the herbs stay on the table.")
POTION_COUNTDOWN = {gm.FAST: "2:30", gm.NORMAL: "5:00", gm.SLOW: "8:20"}


def potion_line(speed: int) -> str:
    return (f"A brewed potion: the pot's on-screen countdown starts at {POTION_COUNTDOWN[speed]} on "
            f"{gm.speed_name(speed)} speed (5:00 on Normal, 2:30 on Fast, 8:20 on Slow: what it shows changes with "
            "the speed), and the potion is gone when it reaches 0:00 -- 5 real-life minutes after it was brewed at "
            "every speed, by the computer's clock (0x430E60, 0x430F10).")


# "That villager can't drink another potion so soon." (string 0x1A7, eSayCantDrinkAgain; the text at 0x49B9CC)
# is said only by the brewed potion's drop handler 0x4303E0 (the alchemy pot's vtable 0x49CF54, slot 9) when
# the villager's add-effect 0x4583A0 refuses the potion's effect: 0x455E10 finds the same effect already on
# that villager, or the villager already has 4 (+0xFB0, the count of the 24-byte effects at +0xF50).  So it is
# the "already have / 4 effects" rule, with no timer of its own.  An effect ends at a wall-clock deadline (+0x10
# of its entry, 0x403330 + 600 or 300 set by the effect's apply 0x4268F0; checked by the villager update
# 0x457051) -- 10 or 5 real-life minutes, the effect line's "in real time".  Saving ends every villager's
# effects first (0x45EF9C calls 0x455DD0 for each villager), so no save holds one to count down.
CANT_DRINK_LINE = (
    "\"That villager can't drink another potion so soon.\" is the game's answer when the rule above refuses a "
    "potion: that villager already has the same potion's effect, or already has 4 effects. It has no timer of "
    "its own; it lasts until that villager's effect ends (10 or 5 real-life minutes after drinking, real time, as the effect "
    "line says), for that villager and that effect only, so other villagers, and other potions while under 4 "
    "effects, can still be drunk. Saving the game ends every villager's potion effects, so time away never "
    "carries one over and a save holds none to count down.")


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

    # A fruit or honey pick: 4 / (rate x 1/6 as a float a hair over 1/6) rounded down (0x434ACF, 0x431C0D), so 7, 3 or 2
    # on Fast, Normal or Slow; 4 while catching up (0x434ABB, 0x431BE8).  The hive's honey is taken from 10 up
    # (0x4317F0: honey >= 10, from its drop handler 0x431D85; an earlier "only above 10" was one off).
    pick = {gm.FAST: 7, gm.NORMAL: 3, gm.SLOW: 2}[speed]
    add("Food sources", f"Food in storage: {_i32(buf, FOOD):,}.", gm.SAVE)
    add("Food sources", f"Picking fruit or honey brings {pick} on {on} speed (7, 3 or 2 on Fast, Normal or Slow, by "
                        "the game's own rounding; 4 while catching up); the hive gives honey only while it holds 10 "
                        "or more.", gm.CODE)
    # Fishing 0x458E81: 11 on Fast, 5 on Slow, 8 otherwise and while catching up (0x458E90..0x458EBA).
    add("Food sources", f"Fishing brings { {gm.FAST: 11, gm.NORMAL: 8, gm.SLOW: 5}[speed] } on {on} speed (11, 8 or "
                        "5 on Fast, Normal or Slow; 8 while catching up).", gm.CODE)
    # The big catch is a crab (the owner, 2026-10-23; the code's carried item 9, "Crab" in the carry-name
    # table 0x4A8A14, against 8 "Fish" for the plain catch, 0x4535AF / 0x4535F3); its chance is in Chances.
    add("Food sources", "The sea never runs out; a fisher with Farming 88 or more sometimes lands a crab worth 55 "
                        "food instead (its chance: Chances, The crab).", gm.CODE)

    # The spawner 0x42DC90 / 0x42D940: two slots (0x42D950), a second roll above strength 50 (0x42DD8D), each item
    # out 90 seconds of the wall clock (0x42DB10).  An earlier line said "in storms" and kept "At most 2" apart.
    add("Mushrooms", "While playing (not paused), about one mushroom or collectible appears a real-life minute at any "
                     "speed, about one every 30 real-life seconds while the weather's strength is above 50; at most 2 "
                     "are out at a time, and each is gone after 90 real-life seconds unpicked (the exact rolls: "
                     "Chances).", gm.CODE)
    # Brown and red are the owner's words (2026-10-23); the code calls the 35-food one the rare mushroom
    # (eCarrying_RareShroom 0x481224, item 0x65; the brown one eCarrying_Shroom, item 0x64).
    add("Mushrooms", "In fair weather 30% of them are mushrooms, in rain all: 92% are brown mushrooms worth 6 food, 8% "
                     "red (rare) mushrooms worth 35, counted when they reach the food bin.", gm.RUNNING)
    if village.has(GOLDEN):
        out.extend(gm.golden_lines(GOLDEN, 18.0, speed_value, "about one thing a real-life minute at every speed, "
                                   "30% of them mushrooms in fair weather (all of them in rain, which makes it sooner)"))
    add("Mushrooms", f"Mushrooms found in this village: {_i32(buf, MUSHROOMS_FOUND):,}.", gm.SAVE)
    add("Collectibles", "The others are collectibles: common 83%, uncommon 13%, rare 4%. A piece already found "
                        "gives 100, 250 or 1,500 tech points by rarity.", gm.RUNNING)
    add("Collectibles", "Tablet pieces already owned never appear again; coral, feather and turtle shell pieces "
                        "keep appearing, and each one already owned pays its tech points.", gm.RUNNING)
    # The Tablet is drawn only once The Ruins (puzzle 6) is at least 2% restored (0x42D9E0..0x42D9FF, 0x4358F0); the
    # population limit 0x45FE30: 90, +5 for each complete collection, 25 in all for the four (0x45FE8C), +10 at Magic 3.
    add("Collectibles", "The Tablet collection appears once The Ruins is at least 2% restored; each complete "
                        "collection raises the population limit by 5, and all four by 25 in all.", gm.CODE)
    # The chief's call 0x42DB30: always rare (0x42DC33), refused when the piece is out (0x42D7F0), carried (0x45EBF0)
    # or an owned Tablet piece (0x42D830); an earlier line named only the last.  The rule is in Chances.
    add("Collectibles", "A Tribal Chief with Leadership 3 can call a rare collectible every 23 real-life hours (real "
                        "time, at any speed, paused or closed; when "
                        "the call fails: Chances, The Tribal Chief's rare collectible).", gm.CODE)
    if village.has(RARE_RETRY) is not False:
        add("Collectibles", gm.patch_words(village, RARE_RETRY, "a failed call is tried again, up to 20 times"),
            gm.RUNNING)

    add("Tech points and effects", f"Tech points: {_i32(buf, POINTS):,}.", gm.SAVE)
    # A research session's tech points (0x459196..0x45943B): Science 0, skill / 5, x 2 on Fast, halved on Slow above
    # 1 (0x4591C6..0x45922A); Science 1, 2, 3, skill / 11, / 9, / 7 (0x45934D, 0x4592E2, 0x459274) divided by the
    # clock's rate x 1/6 (0x426580: the float 0.16666667 is a hair over 1/6), then rounded down (0x46EF58): 2n - 1 on
    # Fast, n - 1 on Normal, 0.6n rounded down (one less when it is whole) on Slow, n >= 1.  Then a supervising chief
    # adds a third / a quarter; at Science 1 or more Magic level 1 adds 1 (0x4593D5) and the "scientific clarity"
    # effect (4, 0x4593F2) 1; the fire 1 on rand(100) < 10 (0x459421).  An earlier line gave the -1 for Normal only.
    sci = level[SCIENCE]
    divisor = {0: 5, 1: 11, 2: 9, 3: 7}.get(sci, 7)
    catch = {0: 4, 1: 7, 2: 7, 3: 5}.get(sci, 5)
    if sci <= 0:
        speed_words = {gm.FAST: "then doubled on Fast speed", gm.NORMAL: "as it is on Normal speed",
                       gm.SLOW: "then halved, rounded down, on Slow speed when it is more than 1"}[speed]
        bonus = "; Magic and the potions add nothing at Science level 0"
    else:
        speed_words = {gm.FAST: "then doubled less 1 on Fast speed",
                       gm.NORMAL: "then less 1 on Normal speed",
                       gm.SLOW: "then times 0.6 rounded down on Slow speed, 1 less when that is a whole number"}[speed]
        speed_words += " (0 stays 0), by the game's own rounding"
        bonus = ("; then 1 more at Magic level 1 or higher, and 1 more for a researcher with the potion effect "
                 "\"scientific clarity\"")
    add("Tech points and effects", (
        f"Research: a successful session at Science level {sci} gives the Research skill ÷ {divisor}, rounded down, "
        f"{speed_words}" + bonus + "; a supervising Tribal Chief adds a share (Chances, The Tribal Chief's "
        f"supervision); a burning fire adds 1 on 10% of sessions; while catching up ÷ {catch} at every speed, with "
        "no speed rounding (Time away)."), gm.CODE)
    blow = at_most(100, 15 * (3 - level[ALCHEMY])) if level[ALCHEMY] <= 3 else 0
    add("Tech points and effects", BLOW_LINE.format(blow=chance(blow), alchemy=level[ALCHEMY]), gm.RUNNING)
    add("Tech points and effects", potion_line(speed), gm.RUNNING)
    add("Tech points and effects", POT_EMPTIED_LINE, gm.OWNER)

    # The aging loop 0x45FFE0: 2 food each age unit above 500 (0x460080); 2 more on rand(100) <= 75 on Medium at
    # 8,000 or more and on Hard at any amount, never on Easy (0x46008C..0x4600CB).  An earlier line said "at Normal
    # difficulty" (the game's word is Medium, 0x49BD74), "on Hard always" (it is 76.05% there too) and "1 or 2 health
    # about two times in three" without food (it is the 15% skip loss plus 76.05%, every unit on Hard or for a hidden
    # number that is a multiple of 6: 0x4600DD..0x460114).
    add("Food earned", f"Each villager eats 2 food every {gm.duration(60 * speed)} on {on} speed "
                       f"({2 * 3600 / (60 * speed):g} an hour) while there is more than 500, and on Medium at 8,000 "
                       "food or more or on Hard at any amount 2 more on 76% of age units (never on Easy). Skipped "
                       "meals at 500 or less and the health lost without food: Chances (Eating, Starving).",
        gm.CODE)

    # -- Time away (catch-up): src/vv_game_mechanics_catchup.py, added by vv_game_mechanics.read -----

    add("Island events", "When the next natural island event comes: under Village timers.", gm.SAVE)
    out.extend(events.facts(village))

    fire = wall(FIRE_END)
    # Saved with the clock stopped, the deadline waits from the moment the clock stopped (its wall base): unpausing
    # moves it on by the time paused (0x426630), so what is left is counted from there, not from the save.
    stopped_at = clock.restarted
    # The fire's state is the save's own deadline; what a burning fire changes is given once, under Chances.
    add("Other", ("The fire " + (f"burns until {gm.when(fire)}" if fire > village.now and not clock.frozen else
                                 "is out" if not clock.frozen or fire <= stopped_at
                                 else f"was burning when saved, with {gm.duration(fire - stopped_at)} left once "
                                      "the clock runs again")
                  + "; what a burning fire changes: Chances (Regaining health, Falling sick, Research)."), gm.SAVE)
    add("Other", POTION_EFFECTS_LINE, gm.RUNNING)
    add("Other", HERBS_LINE, gm.OWNER)
    add("Other", CANT_DRINK_LINE, gm.RUNNING)
    extra = ""
    if level[5] >= 3 or nature >= 3 or village.has(MORTALITY) is True:
        extra = gm.patch_words(village, MORTALITY, "at Nature level 3 the rolls start 7 years later (62, 70 "
                                                   "or 78 years; Medicine starts at 1, 0x426F40)")
    out.append(gm.old_age_line("55, 63 or 71 years (Medicine 1 to 3; a village starts at Medicine 1, 0x426F40)", "65, 73 or 81 years", extra))
    for line, ok in HIDDEN_LINES:
        add(gm.HIDDEN, line, ok)
    burned, water = _i32(buf, FIRE_BURNED), _i32(buf, FIRE_WATER)
    add(gm.HIDDEN, (f"This village's Ash Key count: the campfire has burned {gm.duration(burned)} in all, counted on "
                    f"Normal speed, of the {gm.duration(ASH_GATE)} needed"
                    + (", so the gate is open" if burned >= ASH_GATE else "") + f"; water trips counted: {water}."),
        gm.RUNNING)
    out.extend(gm.starvation_lines(village, 0x8, gm.RUNNING))
    add("Chance and timers", gm.autosave_line(3), gm.OWNER)
    for line, ok in CHANCE_LINES:
        add("Chance and timers", line, gm.RUNNING if ok else False)
    leadership = level[LEADERSHIP]
    ready = []
    for words, at in CHIEF_READY.items():
        stamp = _i32(buf, at)
        ready.append(f"{words}: " + ("ready" if stamp == 0 or wall(at) <= village.now else gm.when(wall(at))))
    # Each power sets its ready time 82,800 seconds (23 hours) ahead on the wall clock 0x403330 (0x421A9D, 0x421C62,
    # 0x466895), so the wait runs at any speed, paused or closed.  What each gives is in Chances.
    add("Other", "The Tribal Chief's powers each wait 23 real-life hours after use, at any speed, paused or closed: "
                 + "; ".join(ready) + f". Leadership is {leadership} (what Grant Food gives: Chances).", gm.CODE)
    out.append(gm.started_line(clock.created))
    out.extend(f for f in [gm.warp_dates_note(village, "Other", "the village's start date is")] if f)
    out.extend(gm.later_puzzle_lines(
        PUZZLE_NAMES, lambda pid: struct.unpack_from("<ii", buf, PUZZLES + 4 + 8 * pid), PUZZLE_THRESHOLDS, clock))
    out.extend(f for f in [gm.warp_dates_note(village, gm.PUZZLES, "the puzzle dates are")] if f)

    # -- The countdowns, and the people and clocks (src/vv_game_mechanics_life.py) ------------
    event_at = None if paused else wall(EVENT_NEXT)
    if not clock.frozen and fire > village.now:
        gm.with_due(out, "The fire burns until", fire, "ends")
    village_extra = []
    for words, at in CHIEF_READY.items():
        if _i32(buf, at) != 0 and wall(at) > village.now:
            village_extra.append(gm.Fact(life.VILLAGE_TIMERS, f"The Tribal Chief's power to {words.split(' (')[0]}: "
                                         f"ready again {gm.when(wall(at))}.", gm.SAVE, due=wall(at),
                                         due_kind="ready"))
    if not clock.frozen and fire > village.now:
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
        mushroom_words="About one thing appears each real-life minute while playing (not paused; real time, the "
                       "same at every speed), 30% of them "
                       "mushrooms in fair weather and all of them in rain, so about 18 mushrooms per real-life hour in "
                       "fair weather.",
        event_next=event_at,
        event_paused_left=max(0, _i32(buf, EVENT_NEXT) - _i32(buf, LAST_SAVED)) if paused else None,
        # The scheduler 0x468727: a new village's first event 15 minutes after its start (0x4280B2), the next after
        # the village's first event ever 30 minutes later (0x468899), then (rand(8) + 8) hours (0x4687EE); nothing
        # resets it when the game is started (an earlier "the first each time the game is started comes 30
        # real-life minutes after it" was wrong: the 30 minutes follow the village's first event only).  Its whole
        # rule is in Island events, so this line points there.
        event_rule="How it is timed (paused and closed time included) and which event comes: Island events (Timing, "
                   "Which event).",
        medicine=level[MEDICINE], elderly_from={0: 42, 1: 50, 2: 58, 3: 66}, old_age_from={0: 47, 1: 55, 2: 63, 3: 71},
        # 61.06% above 20 health, 61.06% x 31.03% = 18.95% at 20 or less (0x46017D, 0x460195; Chances).
        parents_from=18, sick_loss=(0.6106, 0.1895),
        sick_end="A healer cures a sick villager at Healing + 34%.",
        collectibles=life.collectible_lines(village, life.COLLECTIBLE_PAY[3])[0],
        limit=life.limit_words(village, None, "5 for each complete collection, 25 with all four, and 10 at Magic "
                                              "level 3"),
        puzzles=puzzles, village_extra=village_extra,
        food_words="2 food a villager every age unit while there is more than 500; on Medium at 8,000 or more, and "
                   "on Hard at any amount, 2 more 76% of the time; never more on Easy.",
        trips=[("fruit or honey picks", pick_food), ("fishing trips", {gm.FAST: 11, gm.NORMAL: 8, gm.SLOW: 5}[speed])])
    out.extend(life.sections(ctx))
    out.extend(death.facts(village, medicine=level[MEDICINE], speed_value=speed_value, base=epoch,
                           nature=max(level[5], nature)))
    return out


# The 16 puzzles by id (the game's own names, as the patcher's Story Cheat Upgrades lists them,
# native/vvfp_story_upgrades/story_c3.inc), each solved at the threshold the game's table 0x49D230 holds.
PUZZLE_NAMES = {0: "The First Chief", 1: "The Bee Hive", 2: "The Alchemy Lab", 3: "The Roster of the Dead",
                4: "Weather Dancing", 5: "The Lift", 6: "The Ruins", 7: "The Ancient Bath", 8: "The Statue",
                9: "The Orchard", 10: "The Sharks", 11: "Aromatherapy", 12: "The Ash Key", 13: "The Cliff Key",
                14: "The Clam Key", 15: "The Chief and the Princess"}
PUZZLE_THRESHOLDS = dict(enumerate((1, 1, 5, 700, 1, 1, 1800, 1400, 2, 1, 1, 6, 1, 1, 1, 1)))
