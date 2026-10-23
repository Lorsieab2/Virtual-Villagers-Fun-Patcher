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
STATUS = {gm.OWNER: "CONFIRMED BY OWNER", gm.CLAMP: "VERIFIED FROM RUNNING CODE", gm.SAVE: "READ FROM THE SAVE"}
EVIDENCE = {gm.OWNER: "owner", gm.CLAMP: "the catch-up clamp and Time Warp, verified on the games' own aging path",
            gm.SAVE: "the save"}
NOW = 1_800_000_000.0                         # a fixed "now", so the export does not change from run to run
_DATE = re.compile(r"\b\d{1,2} (January|February|March|April|May|June|July|August|September|October|November|"
                   r"December) \d{4}, \d{1,2}:\d{2} (AM|PM)")
_NUMBER = re.compile(r"(?<![A-Za-z])[-+]?\d[\d,]*(\.\d+)?")
_PATCH = re.compile(r"\"([^\"]+)\"")


_UNIT = r"\d[\d,]* (?:days?|hours?|minutes?|seconds?)"
_TOKEN = re.compile(rf"(?P<date>{_DATE.pattern})|(?P<time>{_UNIT}(?: {_UNIT})*)|(?P<num>{_NUMBER.pattern})")
_PLACE = {"date": "<date>", "time": "<time>", "num": "#"}


def _tokens(text: str) -> list[tuple[str, str]]:
    return [(m.lastgroup, m.group(0)) for m in _TOKEN.finditer(gm.tidy(text))]


def template(text: str) -> str:
    """A line's shape: every date, length of time and number replaced -- the key its renderings share."""
    return _TOKEN.sub(lambda m: _PLACE[m.lastgroup], gm.tidy(text))


def merged(texts: list[str]) -> str:
    """One line from all its renderings: a value the same in every one is kept (a rule's own figure); one that
    differs is "#" (a number), "<time>" (a length of time) or "<date>" (a date and time) from the save."""
    rows = [_tokens(t) for t in texts]
    keep = [len({row[k][1] for row in rows}) == 1 for k in range(len(rows[0]))]
    pieces = iter(keep)
    return _TOKEN.sub(lambda m: m.group(0) if next(pieces) else _PLACE[m.lastgroup], gm.tidy(texts[0]))

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
        for trees in ([(1, base - 50_000, base - 20_000, 300)], [(0, base - 100, base - 100, 1000)],
                      [(2, base - 1000, base - 500, 10), (1, base - 90_000, base - 90_000, 999),
                       (0, base - 200_000, base - 5_000, 0)]):
            buf = data
            for n, (kind, planted, refilled, fruit) in enumerate(trees):
                buf = _put(buf, h + m.TREES + 0x14 + 0x18 * n + 8, planted, refilled, kind, fruit)
            out.append(_put(buf, h + m.TREES + 0x5C, len(trees)))
    elif game == 4:
        for level in range(1, 4):
            out += [_put(data, m.LEVELS + 4 * m.SCIENCE, level), _put(data, m.LEVELS + 4 * m.FOOD_MASTERY, level)]
        out += [_put(data, m.EVENTS_SEEN, 0), _put(data, m.EVENTS_SEEN, 3)]
    elif game == 5:
        out += [_put(data, m.PROJECTS + 8 * m.HYDRO_FARM, 0), _put(data, m.PROJECTS + 8 * m.HYDRO_FARM, 30)]
        out += [_put(data, m.EVENTS_SEEN, 0), _put(data, m.EVENTS_SEEN, 3)]
    return out


NOWS = (1_790_000_000.0, NOW)                 # before and long after the fixtures were saved


def variants(game: int) -> list[tuple[bytes, list[str] | None]]:
    """(save bytes, the patches in the game or None for not known): each real save, with each branch value,
    at each speed and paused, with every patch, none, or not known."""
    out = []
    features = gm.feature_ids(f"vv{game}_")
    for path in fixture_saves(game):
        for data in pokes(game, gzip.decompress(path.read_bytes())):
            found = vv_save_backup.save_speed(game, data)
            speeds = [data]
            if found is not None:
                offset = found[0]
                for value in (3, 6, 10, 1002, 1005, 1009):
                    speeds.append(data[:offset] + value.to_bytes(4, "little") + data[offset + 4:])
            for each in speeds:
                for patches in (None, [], features):
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
                report.write_text("\n".join(f"- Optional feature: {gm.feature_name(fid)} [{fid}]" for fid in patches)
                                  + "\n", encoding="utf-8")
            for now in NOWS:
                result.append(gm.read(folder, game, 1, [game_folder] if patches is not None else [], now=now))
    return result


def claims(game: int) -> dict[str, dict[str, tuple[str, str, str, str]]]:
    """{group: {template: (line, status, evidence, patches)}} in the window's group order."""
    seen: dict[tuple[str, str], list[gm.Fact]] = {}
    for page in pages(game):
        for fact in page:
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
