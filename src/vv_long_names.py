"""Long names: the whole text of a name longer than the game's field (v1.35.89, "Render Unicode with In-Game
Fonts" and "Use Unicode Font", all five games).

Every text box in the games takes VV_SHARED_NAME_BYTES (1200) bytes.  A text that leaves a box for a shorter
field (a villager's name: 27 bytes in A New Home, 23 in the others; the tribe name 31 / 19; an epitaph) is
saved there as its SHORT FORM -- the longest start of whole characters that fits, then the ellipsis (and a
number when another long name already has that short form) -- and the companion keeps one record,
"<short form><TAB><room><TAB><whole text><TAB><CRC-32 of everything before the last tab, 8 upper-case hex><LF>"
in the game's own bytes, in

    <save folder>\\Virtual Villagers Fun Patcher\\Save <S>\\Data\\Long Names\\
        Virtual Villagers <N> Long Names - Save <S>.dat

(first line "VVFP Long Names v3"; room is the field's bytes with its NUL, 0 when unknown).  Every write makes the
whole file in "<file>.tmp" and moves it over the old one (MoveFileEx REPLACE_EXISTING | WRITE_THROUGH): see
write().  v1 ("short<TAB>whole") and v2 ("short<TAB>whole<TAB>CRC") files are still read.  Records are only
ever added, and the first record for a short form wins; a record that is cut short, fails its checksum, has no
mark, is longer than its room, holds a control character or is over 1,200 bytes is skipped.
native/vvfp_unicode_text/long_names.inc writes it; this module reads it, so the patcher's windows, logs and
family trees show the whole name: whole_name(raw) for one name read from a save, expand(text) for a log line.
"""
from __future__ import annotations

import zlib
from pathlib import Path

from vv_game_text import GAME_TEXT

SHARED_NAME_BYTES = 1200
HEADER = b"VVFP Long Names v3" + b"\n"
HEADERS = {b"VVFP Long Names v1\n": 1, b"VVFP Long Names v2\n": 2, HEADER: 3}
FOLDER = Path("Virtual Villagers Fun Patcher")
ELLIPSIS = chr(0x2026)
_TAB, _LF = b"\t", b"\n"


def file_name(game: int, slot: int) -> str:
    return f"Virtual Villagers {game} Long Names - Save {slot}.dat"


def path(save_folder: Path, game: int, slot: int) -> Path:
    return Path(save_folder) / FOLDER / f"Save {slot}" / "Data" / "Long Names" / file_name(game, slot)


def record(short: bytes, whole: bytes, room: int = 0) -> bytes:
    """One v3 record as the companion writes it: short, room, whole, CRC-32 of those and the two tabs, LF."""
    body = short + _TAB + b"%d" % max(0, room) + _TAB + whole
    return body + _TAB + b"%08X" % zlib.crc32(body) + _LF


def record_v2(short: bytes, whole: bytes) -> bytes:
    """One v2 record (still read)."""
    body = short + _TAB + whole
    return body + _TAB + b"%08X" % zlib.crc32(body) + _LF


def has_mark(short: bytes) -> bool:
    """A short form carries the ellipsis (0x85 or its UTF-8) or three dots."""
    return b"\x85" in short or b"\xe2\x80\xa6" in short or b"..." in short


def valid(short: bytes, whole: bytes, room: int = 0) -> bool:
    """Whether a record is kept: a mark, a short form that fits its room (0: unknown), no control character
    (C0 or DEL), and a whole text within the shared limit."""
    if not short or not whole or len(whole) > SHARED_NAME_BYTES or not has_mark(short):
        return False
    if room > 0 and len(short) >= room:
        return False
    return not any(c < 0x20 or c == 0x7F for c in short + whole)


def records(data: bytes) -> list[tuple[bytes, int, bytes]]:
    """Every intact, valid record of a file of any version, in order: (short form, room, whole text)."""
    out: list[tuple[bytes, int, bytes]] = []
    version = HEADERS.get(data[:len(HEADER)])
    if version is None:
        return out
    for line in data[len(HEADER):].split(_LF)[:-1]:       # the last piece has no LF: not a whole record
        parts = line.split(_TAB)
        room = 0
        if version == 1:
            if len(parts) != 2:
                continue
            short, whole = parts
        elif version == 2:
            if len(parts) != 3 or len(parts[2]) != 8:
                continue
            short, whole = parts[0], parts[1]
            if b"%08X" % zlib.crc32(short + _TAB + whole) != parts[2]:
                continue
        else:
            if len(parts) != 4 or len(parts[3]) != 8 or not parts[1].isdigit() or len(parts[1]) > 5:
                continue
            short, whole, room = parts[0], parts[2], int(parts[1])
            if b"%08X" % zlib.crc32(_TAB.join(parts[:3])) != parts[3]:
                continue
        if valid(short, whole, room):
            out.append((short, room, whole))
    return out


def parse(data: bytes) -> dict[bytes, bytes]:
    """Short form -> whole text, in the game's bytes: every whole record whose checksum holds (a record cut
    short, or merged with the next, is skipped); the first record of a short form wins."""
    pairs: dict[bytes, bytes] = {}
    for short, _room, whole in records(data):
        pairs.setdefault(short, whole)
    return pairs


def write(file: Path, new: list[tuple[bytes, int, bytes]]) -> None:
    """Keep `new` records (short form, room, whole text) in a Long Names file, as the companion does: the file's
    own valid records first (v1/v2 turned into v3), then the new ones whose short form is not there yet; the
    whole file is made in "<file>.tmp" and moved over the old one, and written in place only when the move is
    refused.  Raises ValueError for a record that is not valid, OSError when nothing could be written."""
    import os
    file = Path(file)
    for short, room, whole in new:
        if not valid(short, whole, room):
            raise ValueError(f"not a valid long-name record: {short!r}")
    try:
        old = records(file.read_bytes())
    except OSError:
        old = []
    have = {short for short, _room, _whole in old}
    out = [HEADER]
    for short, room, whole in old:
        out.append(record(short, whole, room))
    for short, room, whole in new:
        if short not in have:
            have.add(short)
            out.append(record(short, whole, room))
    blob = b"".join(out)
    file.parent.mkdir(parents=True, exist_ok=True)
    temp = file.with_name(file.name + ".tmp")
    try:
        with open(temp, "wb") as handle:
            handle.write(blob)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        try:
            temp.unlink()
        except OSError:
            pass
        raise
    try:
        os.replace(temp, file)
    except OSError:
        try:
            temp.unlink()
        except OSError:
            pass
        with open(file, "r+b" if file.exists() else "wb") as handle:     # refused: in place, never emptied first
            handle.write(blob)
            handle.truncate()


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
