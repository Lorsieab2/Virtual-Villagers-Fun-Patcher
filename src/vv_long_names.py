"""Long names: the whole text of a name longer than the game's field (v1.35.89, "Render Unicode with In-Game
Fonts" and "Use Unicode Font", all five games).

Every text box in the games takes VV_SHARED_NAME_BYTES (1200) bytes.  A text that leaves a box for a shorter
field (a villager's name: 27 bytes in A New Home, 23 in the others; the tribe name 31 / 19; an epitaph) is
saved there as its SHORT FORM -- the longest start of whole characters that fits, then the ellipsis "…" (and
a number when another long name already has that short form) -- and the companion appends one line,
"<short form><TAB><whole text>\\n" in the game's own bytes, to

    <save folder>\\Virtual Villagers Fun Patcher\\Save <S>\\Data\\Long Names\\
        Virtual Villagers <N> Long Names - Save <S>.dat

(first line "VVFP Long Names v1"; lines are only ever added, and the first line for a short form wins).
native/vvfp_unicode_text/long_names.inc writes it; this module reads it, so the patcher's windows, logs and
family trees can show the whole name: whole_name(raw) gives it for one name read from a save.
"""
from __future__ import annotations

from pathlib import Path

from vv_game_text import GAME_TEXT

SHARED_NAME_BYTES = 1200
HEADER = b"VVFP Long Names v1"
FOLDER = Path("Virtual Villagers Fun Patcher")


def file_name(game: int, slot: int) -> str:
    return f"Virtual Villagers {game} Long Names - Save {slot}.dat"


def path(save_folder: Path, game: int, slot: int) -> Path:
    return Path(save_folder) / FOLDER / f"Save {slot}" / "Data" / "Long Names" / file_name(game, slot)


def parse(data: bytes) -> dict[bytes, bytes]:
    """Short form -> whole text, in the game's bytes; whole lines only (a line still being written is
    ignored), the first pair of a short form wins."""
    pairs: dict[bytes, bytes] = {}
    if not data.startswith(HEADER):
        return pairs
    lines = data.split(b"\n")
    for line in lines[1:-1]:                  # the last piece has no newline yet: not a whole line
        short, tab, whole = line.partition(b"\t")
        if tab and short and whole and short not in pairs:
            pairs[short] = whole
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


def whole_name(raw: bytes, pairs: dict[bytes, bytes]) -> str:
    """The text of a name read from a save: its whole text when it is a known short form."""
    return pairs.get(bytes(raw), bytes(raw)).decode(GAME_TEXT)


def expand(text: str, pairs: dict[bytes, bytes]) -> str:
    """`text` with each short form in it replaced by its whole text, the longest first (as the game draws)."""
    if not pairs or "…" not in text:
        return text
    by_text = sorted(((s.decode(GAME_TEXT), w.decode(GAME_TEXT)) for s, w in pairs.items()),
                     key=lambda item: -len(item[0]))
    for short, whole in by_text:
        if short in text:
            text = text.replace(short, whole)
    return text
