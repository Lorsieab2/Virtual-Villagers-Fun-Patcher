"""Write every claim the Game Mechanics window can show, one UTF-8 text file per game, for the owner to check.

    python scripts/export_game_mechanics_claims.py <output folder>

Each file, "Virtual Villagers <N> - <Title> - Game Mechanics Claims.txt", lists the window's lines grouped as
the window groups them.  A line's numbers, dates and times depend on the save, so each is written as a
template ("#" for a number, "<date>" for a date and time); every template the window can render from the
repository's real saves (tests/fixtures/rename_tribe), at every speed and paused, with the patcher's patches
in the game, not in it, and not known, is listed once, with:
  * its status: CONFIRMED BY OWNER, VERIFIED FROM RUNNING CODE, READ FROM THE SAVE, or UNCONFIRMED;
  * the evidence: "owner", the catch-up clamp verification, the save, or the research spec (the addresses
    are in the game's module, src/vv_game_mechanics_vv<N>.py);
  * the patches it names.
Read-only: it reads the committed fixtures and writes only into the output folder.  Not shipped to players.
"""
from __future__ import annotations

import gzip
import re
import struct
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_save_backup  # noqa: E402
import vv_tribe_rename  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "rename_tribe"
TITLES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
STATUS = {gm.OWNER: "CONFIRMED BY OWNER", gm.CLAMP: "VERIFIED FROM RUNNING CODE", gm.RUNNING: "VERIFIED FROM RUNNING CODE",
          gm.CODE: "VERIFIED FROM RUNNING CODE", gm.SAVE: "READ FROM THE SAVE"}
EVIDENCE = {gm.OWNER: "owner", gm.CLAMP: "the catch-up clamp and Time Warp, verified on the games' own aging path",
            gm.RUNNING: "the research spec's emulation with its call path from the game traced (addresses in the module)",
            gm.CODE: "the game's own reachable code, read at the addresses in src/vv_game_mechanics_catchup.py",
            gm.SAVE: "the save"}
NOW = 1_800_000_000.0                         # a fixed "now", so the export does not change from run to run
_DATE = re.compile(r"\b\d{1,2} (January|February|March|April|May|June|July|August|September|October|November|"
                   r"December) \d{4}, \d{1,2}:\d{2} (AM|PM)")
_NUMBER = re.compile(r"(?<![A-Za-z])[-+]?\d[\d,]*(\.\d+)?")
_PATCH = re.compile(r"\"([^\"]+)\"")


_UNIT = r"\d[\d,]* (?:days?|hours?|minutes?|seconds?)"
_TOKEN = re.compile(rf"(?P<date>{_DATE.pattern})|(?P<time>{_UNIT}(?: {_UNIT})*)|(?P<num>{_NUMBER.pattern})")
_PLACE = {"date": "<date>", "time": "<time>", "num": "#"}


_VILLAGER = re.compile(r"^.*?(?=: hidden number )")


def _plain(text: str) -> str:
    """A line as rendered, with a villager's name (the per-villager lines) as <villager>."""
    import vv_game_mechanics_life as life
    return life.claim_template(_VILLAGER.sub("<villager>", gm.tidy(text), count=1))


def _tokens(text: str) -> list[tuple[str, str]]:
    return [(m.lastgroup, m.group(0)) for m in _TOKEN.finditer(_plain(text))]


def template(text: str) -> str:
    """A line's shape: every date, length of time and number replaced -- the key its renderings share."""
    return _TOKEN.sub(lambda m: _PLACE[m.lastgroup], _plain(text))


def merged(texts: list[str]) -> str:
    """One line from all its renderings: a value the same in every one is kept (a rule's own figure); one that
    differs is "#" (a number), "<time>" (a length of time) or "<date>" (a date and time) from the save."""
    rows = [_tokens(t) for t in texts]
    keep = [len({row[k][1] for row in rows}) == 1 for k in range(len(rows[0]))]
    pieces = iter(keep)
    return _TOKEN.sub(lambda m: m.group(0) if next(pieces) else _PLACE[m.lastgroup], _plain(texts[0]))

def fixture_saves(game: int) -> list[Path]:
    return sorted(FIXTURES.glob(f"vv{game}-*-[1-5].ldw.gz"))


def _put(data: bytes, at: int, *values: int) -> bytes:
    buf = bytearray(data)
    for k, value in enumerate(values):
        struct.pack_into("<i", buf, at + 4 * k, value)
    return bytes(buf)


def pokes(game: int, data: bytes) -> list[bytes]:
    """The save itself and copies with one branch-deciding value changed at a time (the levels, counters and
    flags each game's module reads), so every kind of line the window can write is rendered."""
    import importlib
    m = importlib.import_module(f"vv_game_mechanics_vv{game}")
    out = [data]
    if game == 1:
        for level in range(0, 4):
            out += [_put(data, m.LEVELS + 8 * m.FARMING, level), _put(data, m.LEVELS + 8 * m.SCIENCE, level)]
        out.append(_put(data, m.EVENTS_SEEN, 0))
    elif game == 2:
        for at in (m.DAM, m.SCARER, m.BEETLES, m.GONG_FIRST_DONE):
            out += [_put(data, at + m.S, 0), _put(data, at + m.S, 1)]
        for at in (m.FIRE_END, m.GONG_NEXT):
            out += [_put(data, at + m.S, 0), _put(data, at + m.S, 400_000_000)]
        for scarer in (0, 1):                   # the birds: kept away, still allowed some harvest, or found the field
            out += [_put(_put(data, m.SCARER + m.S, scarer), m.ALLOWANCE + m.S, amount) for amount in (0, 500)]
        for dam in (0, 1):                      # with the allowance used up: the birds only with the dam built
            out.append(_put(_put(_put(data, m.SCARER + m.S, 0), m.ALLOWANCE + m.S, 0), m.DAM + m.S, dam))
        # The fish: still some, used up, and below 0 once Sustainable Fishing is solved (no limit from Farming
        # level 2; at level 1 fishing stops at 0).
        solved_at = m.SUSTAINABLE_FISHING + m.S
        for fish, solved, farming in ((700, 0, 3), (0, 0, 3), (-40, 1, 1), (-1_162_256, 1, 3)):
            buf = _put(_put(data, m.FISH + m.S, fish), m.LEVELS + 8 * m.FARMING_LEVEL + m.S, farming)
            out.append(buf[:solved_at] + bytes([solved]) + buf[solved_at + 1:])
    elif game == 3:
        h = m.HEADER
        for level in range(0, 4):
            for tech in (m.SCIENCE, m.ALCHEMY, m.NATURE, m.LEADERSHIP):
                out.append(_put(data, h + m.TECHS + 4 * tech, level))
        out.append(_put(data, h + m.PUZZLES + 4 + 8 * m.BEE_HIVE, 0))
        out.append(_put(data, h + m.PUZZLES + 4 + 8 * m.BEE_HIVE, 1))
        out.append(_put(data, h + m.HONEY + 8, m.HONEY_CAP))
        out += [_put(data, h + m.FIRE_END, 0), _put(data, h + m.FIRE_END, 400_000_000)]
        for at in m.CHIEF_READY.values():
            out.append(_put(data, h + at, 400_000_000))
        clock = struct.unpack_from("<4i", data, h + m.CLOCK)
        base = clock[3]
        # Trees and refills before the clock's base (not dated) and after it (dated); the last two also without the
        # village's start in the save.
        sets = ([(1, base - 50_000, base - 20_000, 300)], [(0, base - 100, base - 100, 1000)],
                [(2, base - 1000, base - 500, 10), (1, base - 90_000, base - 90_000, 999),
                 (0, base - 200_000, base - 5_000, 0)], [(1, base + 10, base + 10, 5)])
        for start, chosen in ((data, sets), (_put(data, h + m.STATS, 0), sets[2:])):
            for trees in chosen:
                buf = start
                for n, (kind, planted, refilled, fruit) in enumerate(trees):
                    buf = _put(buf, h + m.TREES + 0x14 + 0x18 * n + 8, planted, refilled, kind, fruit)
                out.append(_put(buf, h + m.TREES + 0x5C, len(trees)))
        out += _puzzle_pokes(data, [h + m.PUZZLES + 4 + 8 * pid for pid in m.PUZZLE_NAMES], base)
    elif game == 4:
        for level in range(1, 4):
            out += [_put(data, m.LEVELS + 4 * m.SCIENCE, level), _put(data, m.LEVELS + 4 * m.FOOD_MASTERY, level)]
        out += [_put(data, m.EVENTS_SEEN, 0), _put(data, m.EVENTS_SEEN, 3)]
        base = struct.unpack_from("<4i", data, m.CLOCK)[3]
        out += _puzzle_pokes(data, [m.PUZZLE_ENTRIES + 8 * pid for pid in m.PUZZLE_NAMES], base)
        out.append(_put(data, m.STATS, 0))
    elif game == 5:
        out += [_put(data, m.PROJECTS + 8 * m.HYDRO_FARM, 0), _put(data, m.PROJECTS + 8 * m.HYDRO_FARM, 30)]
        out += [_put(data, m.EVENTS_SEEN, 0), _put(data, m.EVENTS_SEEN, 3)]
        base = struct.unpack_from("<4i", data, m.CLOCK)[3]
        out += _puzzle_pokes(data, [m.PROJECTS + 8 * pid for pid in list(m.PUZZLE_NAMES) + [17]], base)
        out.append(_put(data, m.STATS, 0))
    if game in (1, 2):
        s = 4                                   # file offset = state offset + 4
        buf = data
        for _name, flag, _hours in m.PUZZLES:
            buf = buf[:flag + s] + b"\0" + buf[flag + s + 1:]
        out.append(buf)
        for hours in (0, 1, 7):
            buf = data
            for _name, flag, at in m.PUZZLES:
                buf = _put(buf[:flag + s] + b"\1" + buf[flag + s + 1:], at + s, hours)
            out.append(buf)
    return out


def _life_pokes(game: int, data: bytes) -> list[bytes]:
    """The people and the difficulty (src/vv_game_mechanics_life.py): each difficulty; a mother of 1, 2 or 3 babies
    now due, due later and with time away still to work off; a sick villager; a child and a youth; A New Home's
    Golden Child; New Believers' faith and Heathens; and a save whose villager table cannot be read."""
    import vv_game_mechanics_life as life
    import vv_last_names as ln
    out = [_put(data, life.DIFFICULTY_AT[game], level) for level in (0, 1, 2)]
    out.append(_put(_put(data, life.DIFFICULTY_AT[game], 1), _FOOD[game], 9_000))
    out.append(gm.blank_save(game, NOW))        # a new, empty village's save: no villager table to be found
    if game == 3:
        # The honey with The Bee Hive solved and its next gain still ahead: its time to full as a date to come.
        import vv_game_mechanics_vv3 as vv3
        h = vv3.HEADER
        base = struct.unpack_from("<4i", data, h + vv3.CLOCK)[3]
        hive = _put(data, h + vv3.PUZZLES + 4 + 8 * vv3.BEE_HIVE, 1)
        out.append(_put(hive, h + vv3.HONEY + 4, base + 50_000_000, 100))
        # ... and with its gain just overdue at the export's first moment, on a running clock at Fast and Normal:
        # the time to full is then a date to come with no next-refill date of its own.
        epoch = struct.unpack_from("<I", data, 4)[0]
        wall = struct.unpack_from("<4i", data, h + vv3.CLOCK)[2]
        for speed in (3, 6):
            now_game = base + int((NOWS[0] - epoch - wall) * 6 / speed)
            running = _put(_put(hive, h + vv3.CLOCK, speed), h + vv3.SPEED, speed)
            out.append(_put(running, h + vv3.HONEY + 4, now_game - 3_700, 100))
    try:
        entries = ln._entries(game, data)
    except Exception:  # noqa: BLE001 -- a fixture without villagers gives no people pokes
        return out
    if not entries:
        return out
    lay = life.LAYOUTS[game]
    at = entries[0]
    age = struct.unpack_from("<i", data, at + lay.age)[0]
    for babies in (1, 2, 3):
        for left, lag in ((0, 0), (12, 0), (12, 30), (40, 0)):
            buf = _put(data, at + lay.processed, age - lag)
            buf = _put(buf, at + lay.conceived, age - lag - life.BIRTH_UNITS + left)
            out.append(_put(buf, at + lay.babies, (0 if babies == 1 else babies) if lay.singles_unwritten else babies))
    for health in (90, 15):
        buf = _put(data, at + lay.health, health)
        sick = bytearray(buf)
        if lay.sick_byte:
            sick[at + lay.sick] = 1
        else:
            struct.pack_into("<i", sick, at + lay.sick, 1)
        out.append(bytes(sick))
    for years_units in (277, 100, 300, 360 * 3):
        out.append(_put(_put(data, at + lay.age, years_units), at + lay.processed, years_units))
    if game == 1:
        out.append(_put(data, at + life.VV1_FAMILY, life.GOLDEN_FAMILY))
    if game == 5:
        out.append(_put(data, at + life.VV5_FAITH, 5))
        flipped = bytearray(data)
        flipped[at + life.VV5_FACTION] = 0 if data[at + life.VV5_FACTION] else 1
        out.append(bytes(flipped))
    return out


_FOOD = {1: 0xA2F0, 2: 0x2EAA4 + 4, 3: 0x4EC, 4: 0x85C, 5: 0x7C0}


def _puzzle_pokes(data: bytes, entries: list[int], base: int) -> list[bytes]:
    """The puzzles all unsolved, and all solved with no time, with a time before the clock's base and after it."""
    out = []
    for progress, stamp in ((0, 0), (5_000, 0), (5_000, max(1, base - 100)), (5_000, base + 100)):
        buf = data
        for at in entries:
            buf = _put(buf, at, progress, stamp)
        out.append(buf)
    return out


# The game folder's stand-in exe (b"MZ") and the transparency report line giving its hash, so the report counts as
# the patcher's log of this exe (vv_game_mechanics.patch_source).
HASH_LINE = ("Modified EXE: {name}.exe | size 2 | SHA-256 "
             "9b8db510ef42b8ed54a3712636fda55a4f8cfcd5493e20b74ab00cd4f3979f2d\n")
NOWS = (1_790_000_000.0, NOW)                 # before and long after the fixtures were saved


def variants(game: int) -> list[tuple[bytes, list[str] | None]]:
    """(save bytes, the patches in the game or None for not known): each real save, with each branch value,
    at each speed and paused, with every patch, none, or not known."""
    out = []
    features = gm.feature_ids(f"vv{game}_")
    for path in fixture_saves(game):
        raw = gzip.decompress(path.read_bytes())
        # The people pokes change no patch's line, so they are read with the patches not known only.
        for data, all_patches in [(d, True) for d in pokes(game, raw)] + [(d, False) for d in _life_pokes(game, raw)]:
            found = vv_save_backup.save_speed(game, data)
            speeds = [data]
            if found is not None:
                offset = found[0]
                for value in (3, 6, 10, 1002, 1005, 1009):
                    speeds.append(data[:offset] + value.to_bytes(4, "little") + data[offset + 4:])
            for each in speeds:
                for patches in ((None, [], features) if all_patches else (None,)):
                    out.append((each, patches))
    return out

def pages(game: int) -> list[list[gm.Fact]]:
    """Every page the export covers, as the window builds them (src/vv_game_mechanics.read)."""
    saves = next(item for item in vv_tribe_rename.GAMES if item.number == game)
    result = []
    with tempfile.TemporaryDirectory(prefix="gmx") as temp:
        root = Path(temp)
        folder = root / saves.base
        folder.mkdir()
        game_folder = root / "games" / saves.base
        (game_folder / "Virtual Villagers Fun Patcher Files").mkdir(parents=True)
        (game_folder / f"{saves.base}.exe").write_bytes(b"MZ")
        report = game_folder / "Virtual Villagers Fun Patcher Files" / "VVFP Transparency Log.txt"
        for data, patches in variants(game):
            (folder / f"{saves.base}1.ldw").write_bytes(data)
            if patches is not None:
                report.write_text(HASH_LINE.format(name=saves.base)
                                  + "\n".join(f"- Optional feature: {gm.feature_name(fid)} [{fid}]" for fid in patches)
                                  + "\n", encoding="utf-8")
            for now in NOWS:
                result.append(gm.read(folder, game, 1, [game_folder] if patches is not None else [], now=now))
            if game == 3 and patches is None:
                # The fruit-tree timing patches' own schedule for these trees, in each of their two modes.
                for mode in (1, 2):
                    timers = _tree_timer_file(data, mode)
                    if timers is None:
                        continue
                    place = folder / "Virtual Villagers Fun Patcher" / "Save 1" / "Data" / "Fruit Trees"
                    place.mkdir(parents=True, exist_ok=True)
                    (place / "Virtual Villagers 3 Fruit Tree Timers - Save 1.dat").write_bytes(timers)
                    for now in NOWS:
                        result.append(gm.read(folder, game, 1, [], now=now))
                    (place / "Virtual Villagers 3 Fruit Tree Timers - Save 1.dat").unlink()
    return result


def _tree_timer_file(data: bytes, mode: int) -> bytes | None:
    """A timers file (native/shared/vv3_fruit_timers.h) whose one entry is these trees' schedule."""
    import vv_game_mechanics_vv3 as vv3
    buf = data[12:]
    count = struct.unpack_from("<i", buf, vv3.TREES + 0x5C)[0]
    fingerprint = vv3._trees_fingerprint(buf)
    if fingerprint is None or count < 1:
        return None
    timers = [struct.unpack_from("<i", buf, vv3.TREES + 0x14 + 0x18 * n + 12)[0] & 0xFFFFFFFF for n in range(3)]
    entry = struct.pack("<IIBBBBI3I3I", fingerprint & 0xFFFFFFFF, fingerprint >> 32, mode, count, 0, 0, 10_800,
                        *timers, *[(t + 10_800) & 0xFFFFFFFF for t in timers])
    return (struct.pack("<5I", vv3.TIMER_MAGIC, 1, 3, 1, 1) + entry
            + bytes(vv3.TIMER_ENTRY * (vv3.TIMER_ENTRIES - 1)))


def claims(game: int) -> dict[str, dict[str, tuple[str, str, str, str]]]:
    """{group: {template: (line, status, evidence, patches)}} in the window's group order."""
    seen: dict[tuple[str, str], list[gm.Fact]] = {}
    for page in pages(game):
        for fact in page:
            if fact.group == gm.SOURCES:       # where this page was read from: no claim about the game
                continue
            seen.setdefault((fact.group, template(fact.text)), []).append(fact)
    out: dict[str, dict[str, tuple[str, str, str, str]]] = {group: {} for group in gm.GROUPS}
    for (group, key), facts in seen.items():
        fact = facts[0]
        status = STATUS[fact.verified] if fact.confirmed else "UNCONFIRMED"
        evidence = EVIDENCE[fact.verified] if fact.confirmed else (
            f"research spec; addresses in src/vv_game_mechanics_vv{game}.py")
        patches = ", ".join(_PATCH.findall(fact.text)) or "none named"
        out.setdefault(group, {})[key] = (merged([f.text for f in facts]), status, evidence, patches)
    return out

def file_name(game: int) -> str:
    return f"Virtual Villagers {game} - {TITLES[game]} - Game Mechanics Claims.txt"


def render(game: int) -> str:
    lines = [f"Virtual Villagers {game}: {TITLES[game]} -- every line the Game Mechanics window can show",
             "", "\"#\" stands for a number, \"<time>\" for a length of time and \"<date>\" for a date and time that differ",
             "from village to village (read from the save); every other figure is the rule's own.", ""]
    for group, entries in claims(game).items():
        if not entries:
            continue
        lines += [group.upper(), ""]
        for text, status, evidence, patches in entries.values():
            lines += [f"- {text}", f"    Status: {status}", f"    Evidence: {evidence}", f"    Patches: {patches}", ""]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    target = Path(argv[0])
    target.mkdir(parents=True, exist_ok=True)
    for game in range(1, 6):
        path = target / file_name(game)
        path.write_text(render(game), encoding="utf-8")
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
