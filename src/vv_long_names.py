"""Long names: the whole text of a name longer than the game's field (v1.35.89, "Render Unicode with In-Game
Fonts" and "Use Unicode Font", all five games).

Every text box in the games takes VV_SHARED_NAME_BYTES (1200) bytes.  A text that leaves a box for a shorter
field (a villager's name: 27 bytes in A New Home, 23 in the others; the tribe name 31 / 19; an epitaph) is
saved there as its SHORT FORM -- the longest start of whole characters that fits, then the ellipsis (and a
number when another long name already has that short form) -- and the companion appends one record,
"<short form><TAB><whole text><TAB><CRC-32 of the two and the tab, 8 upper-case hex><LF>" in the game's own
bytes, in one write, to

    <save folder>\\Virtual Villagers Fun Patcher\\Save <S>\\Data\\Long Names\\
        Virtual Villagers <N> Long Names - Save <S>.dat

(first line "VVFP Long Names v2"; records are only ever added, and the first record for a short form wins;
a record cut short by a failed write fails its checksum and is skipped).  native/vvfp_unicode_text/
long_names.inc writes it; this module reads it, so the patcher's windows, logs and family trees show the
whole name: whole_name(raw) for one name read from a save, expand(text) for a log line.
"""
from __future__ import annotations

import zlib
from pathlib import Path

from vv_game_text import GAME_TEXT

SHARED_NAME_BYTES = 1200
HEADER = b"VVFP Long Names v2" + b"\n"
FOLDER = Path("Virtual Villagers Fun Patcher")
ELLIPSIS = chr(0x2026)
_TAB, _LF = b"\t", b"\n"


def file_name(game: int, slot: int) -> str:
    return f"Virtual Villagers {game} Long Names - Save {slot}.dat"


def path(save_folder: Path, game: int, slot: int) -> Path:
    return Path(save_folder) / FOLDER / f"Save {slot}" / "Data" / "Long Names" / file_name(game, slot)


def record(short: bytes, whole: bytes) -> bytes:
    """One record as the companion writes it."""
    body = short + _TAB + whole
    return body + _TAB + b"%08X" % zlib.crc32(body) + _LF


def parse(data: bytes) -> dict[bytes, bytes]:
    """Short form -> whole text, in the game's bytes: every whole record whose checksum holds (a record cut
    short, or merged with the next, is skipped); the first record of a short form wins."""
    pairs: dict[bytes, bytes] = {}
    if not data.startswith(HEADER):
        return pairs
    for line in data[len(HEADER):].split(_LF)[:-1]:       # the last piece has no LF: not a whole record
        parts = line.split(_TAB)
        if len(parts) != 3 or not parts[0] or not parts[1] or len(parts[2]) != 8:
            continue
        if b"%08X" % zlib.crc32(parts[0] + _TAB + parts[1]) != parts[2]:
            continue
        pairs.setdefault(parts[0], parts[1])
    return pairs


def load(save_folder: Path, game: int) -> dict[bytes, bytes]:
    """Every slot's pairs of a game's save folder (the companion reads all five: a short form may come from
    any slot, as Change Tribe shows every slot's tribe)."""
    pairs: dict[bytes, bytes] = {}
    for slot in range(1, 6):
        try:
            data = path(save_folder, game, slot).read_bytes()
        except OSError:
            continue
        for short, whole in parse(data).items():
            pairs.setdefault(short, whole)
    return pairs


# The pairs of the village being read (activate()), for readers that decode one name or line at a time
# (vv_genealogy._cstr, vv_log_additions.read_lines).  Empty: names are read as written.
ACTIVE: dict[bytes, bytes] = {}


class activate:
    """`with activate(folder, game):` -- names read meanwhile are whole (the Family Tree Maker and the other
    full-name readers); outside it, every reader keeps the names as the save and logs write them (Last
    Names and Number Duplicate Names rename what is written, so they need the short forms)."""

    def __init__(self, save_folder: Path | None, game: int | None) -> None:
        self.on = save_folder is not None and bool(game)
        self.pairs = load(save_folder, game) if self.on else {}

    def __enter__(self):
        global ACTIVE
        import vv_game_text
        self.before = ACTIVE
        self.before_hook = vv_game_text.LONG_NAMES
        self.before_legacy = dict(LEGACY)
        ACTIVE = self.pairs
        vv_game_text.LONG_NAMES = expand_line if self.on else None
        return self.pairs

    def __exit__(self, *exc):
        global ACTIVE
        import vv_game_text
        ACTIVE = self.before
        vv_game_text.LONG_NAMES = self.before_hook
        LEGACY.clear()
        LEGACY.update(self.before_legacy)
        return False


# Logs written before v1.35.89 hold each name byte 0x80-0xFF as '?' (the parentage exporter's old rule):
# "Zo? ??ez" is the save's "Zoe Nunez" with her accents.  While a full-name reader runs, a log line whose
# value is exactly such a name of the save reads as that name (legacy_names(): only names no other
# villager of the save shares once masked, so two villagers are never made one).
LEGACY: dict[str, str] = {}


def legacy_mask(name: str) -> str:
    """A name as the exporter wrote it before v1.35.89: each byte 0x80-0xFF as '?'."""
    import vv_game_text
    raw = vv_game_text.encode_game_text(name)
    return "".join(chr(c) if c < 0x80 else "?" for c in raw)


def only_question_marks(name: str) -> bool:
    """A name of '?' alone (and any trailing spaces): a real, deliberate name.  The island events that make a
    villager forget their name write exactly "?" -- The Lost Children 0x41FD61 / 0x4211EE ("A Bump On The
    Head"), The Secret City 0x418433, The Tree of Life 0x4156D9, New Believers 0x415BDA; the string is "?"
    and a NUL in every game, no space -- so it is never read as an older exporter's mask."""
    stripped = name.rstrip(" \t")
    return bool(stripped) and set(stripped) == {"?"}


def legacy_names(save_names) -> dict[str, str]:
    """Masked -> real name, for the save's names that have a byte 0x80-0xFF and whose mask is theirs alone.
    Never a mask that is '?' alone (only_question_marks), and never a mask that is itself the name of a save
    villager (that is her own name, not anybody's mask)."""
    names = [n for n in save_names if n]
    actual = set(names)
    seen: dict[str, set[str]] = {}
    for name in names:
        masked = legacy_mask(name)
        if masked != name and not only_question_marks(masked) and masked not in actual:
            seen.setdefault(masked, set()).add(name)
    return {masked: next(iter(group)) for masked, group in seen.items() if len(group) == 1}


def _legacy_lines(text: str) -> str:
    if not LEGACY or "?" not in text:
        return text
    import re
    return re.sub(r"(?m)^([ \t]*[A-Za-z][A-Za-z ]*: )(.*?)(\r?)$",
                  lambda m: m.group(1) + LEGACY.get(m.group(2), m.group(2)) + m.group(3), text)


def whole_bytes(raw: bytes) -> bytes:
    """A name's bytes, whole when it is a short form of the active village."""
    return ACTIVE.get(bytes(raw), bytes(raw)) if ACTIVE else bytes(raw)


def expand_line(line: str) -> str:
    """A log line (or a whole log) with each short form of the active village whole, and each name an older
    exporter wrote with '?' for its letters 0x80-0xFF as the save's (LEGACY)."""
    return _legacy_lines(expand(line, ACTIVE) if ACTIVE else line)


def whole_name(raw: bytes, pairs: dict[bytes, bytes]) -> str:
    """The text of a name read from a save: its whole text when it is a known short form."""
    import vv_game_text
    return vv_game_text._decode(pairs.get(bytes(raw), bytes(raw)))


def expand(text: str, pairs: dict[bytes, bytes]) -> str:
    """`text` with each short form in it replaced by its whole text, the longest first (as the game draws)."""
    if not pairs or ELLIPSIS not in text:
        return text
    import vv_game_text
    by_text = sorted(((vv_game_text._decode(s), vv_game_text._decode(w)) for s, w in pairs.items()),
                     key=lambda item: -len(item[0]))
    for short, whole in by_text:
        if short in text:
            text = text.replace(short, whole)
    return text
