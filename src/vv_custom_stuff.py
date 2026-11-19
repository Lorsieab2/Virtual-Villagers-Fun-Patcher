"""Custom Stuff (all five games; the owner, 2026-11-19): the player's own first names, last names, and likes and
dislikes, added to each game's own.

The owner's rule: "normal vanilla stuff = fallback. custom stuff = additions that should be treated like normal game
additions, no special treatment. use outside files/dlls/sidecars etc to hold them, just like all new additions to the
game."  So nothing here ever replaces one of the game's own names or words, and nothing is written into an
executable or a save:

  * THE LIBRARY is the player's, beside the patcher: "Custom Stuff\\vv<N>\\First Names - Male.txt",
    "First Names - Female.txt", "Last Names.txt" and "Likes and Dislikes.txt" (UTF-8, one entry per line; a line
    starting with '#' is a comment).  The Custom Stuff window (src/vv_custom_stuff_window.py) edits it.
  * THE GAME'S COPY: after every build (src/vv_fun_patcher.py _apply_custom_stuff) and whenever the window saves,
    the entries that pass check_entries are written to "<patched game>\\Virtual Villagers Fun Patcher Files\\Custom
    Stuff\\" under the same names (apply_library).  "VVFP Custom Names.dll" (native/vvfp_custom_names) reads the
    name files as the game opens; the "Custom Stuff" row ships it.
  * LIKES AND DISLIKES are kept and copied like the names, but no game shows them yet (see the window's note):
    giving them to villagers the way the game gives its own needs a per-villager file of its own.

A name is checked the same way here and in the companion (vvfp_custom_names.c name_of): one word, no '%', comma, tab
or control letter, not only Roman-numeral letters (Number Duplicate Names' numerals), at most FIRST_MAX / LAST_MAX
bytes as the game keeps it (Windows-1252, or UTF-8 for a letter outside it).  Here it is also refused when the game
already has it (every name is then exactly as likely as every other) or the list holds it twice.
"""
from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIBRARY_DIR = ROOT / "Custom Stuff"
PATCHER_FILES = "Virtual Villagers Fun Patcher Files"
GAME_SUBFOLDER = "Custom Stuff"
GAMES = (1, 2, 3, 4, 5)
TITLES = {
    1: "A New Home",
    2: "The Lost Children",
    3: "The Secret City",
    4: "The Tree of Life",
    5: "New Believers",
}

KINDS = ("male", "female", "last", "likes")
FILE_NAMES = {
    "male": "First Names - Male.txt",
    "female": "First Names - Female.txt",
    "last": "Last Names.txt",
    "likes": "Likes and Dislikes.txt",
}
KIND_LABELS = {
    "male": "male first names",
    "female": "female first names",
    "last": "last names",
    "likes": "likes and dislikes",
}
FIRST_MAX = 10          # bytes, as the game keeps a first name (vvfp_custom_names.c FIRST_MAX)
LAST_MAX = 12           # bytes, a last name (LAST_MAX)
LIKE_MAX = 16           # letters of a like or dislike (the stock words are at most 11)
LIST_MAX = 1000         # entries a list may hold (LIST_MAX)
NUMERAL = re.compile(r"^[IVXLCDM]+$")
UNICODE_NOTE = ("uses letters outside Windows-1252: the game shows it only with \"Render Unicode with In-Game Fonts\" "
                "or \"Use Unicode Font\", and skips it otherwise")


# ---- the game's own lists ----------------------------------------------------------------------------------

def stock_entries(game: int, kind: str) -> tuple[str, ...]:
    """The game's own names or words of `kind`: the style reference, and what a custom entry may not repeat."""
    import vv_cie_graph
    if kind == "male":
        return vv_cie_graph.villager_names(game)[0]
    if kind == "female":
        return vv_cie_graph.villager_names(game)[1]
    if kind == "last":
        return vv_cie_graph.last_names(game)
    if kind == "likes":
        return vv_cie_graph.GAMES[game].preferences
    raise ValueError(kind)


# ---- checking ----------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Checked:
    line: int               # 1-based line in the text
    text: str               # the entry, trimmed
    problem: str = ""       # why it is refused ("" when kept)
    note: str = ""          # a warning for a kept entry

    @property
    def ok(self) -> bool:
        return not self.problem


def _kept_bytes(text: str) -> bytes:
    """The bytes the game keeps: Windows-1252 (Latin-1 range) when every letter fits, else UTF-8."""
    if all(ord(ch) <= 0xFF for ch in text):
        return text.encode("latin-1")
    return text.encode("utf-8")


def _letter_problem(text: str, kind: str) -> str:
    for ch in text:
        code = ord(ch)
        if code < 0x20 or code == 0x7F or 0x80 <= code <= 0xA0:
            return "has a control letter or a non-breaking space"
        if 0xD800 <= code <= 0xDFFF:
            return "has a broken letter"
        if ch == "%":
            return "has %, which an unpatched game reads as a formatting instruction"
        if ch == ",":
            return "has a comma (the game separates its lists with commas)"
        if ch == "\t":
            return "has a tab"
        if kind != "likes" and ch == " ":
            return "is more than one word (a name is one word)"
    return ""


def entry_problem(game: int, kind: str, text: str) -> tuple[str, str]:
    """(problem, note) for one entry, without looking at the rest of the list."""
    if not text:
        return "is empty", ""
    problem = _letter_problem(text, kind)
    if problem:
        return problem, ""
    if kind == "likes":
        if len(text) > LIKE_MAX:
            return f"is longer than {LIKE_MAX} letters (it must fit the Details screen)", ""
        if text != text.strip() or "  " in text:
            return "has extra spaces", ""
        note = UNICODE_NOTE if any(ord(ch) > 0xFF for ch in text) else ""
        return "", note
    if NUMERAL.match(text):
        return "is only Roman-numeral letters (Number Duplicate Names uses them for numbers)", ""
    limit = FIRST_MAX if kind in ("male", "female") else LAST_MAX
    latin = all(ord(ch) <= 0xFF for ch in text)
    if kind == "last" and not latin:
        return "uses letters outside Windows-1252 (last names are kept in the Last Names records that way)", ""
    if len(_kept_bytes(text)) > limit:
        unit = "letters" if latin else "bytes"
        return f"is longer than {limit} {unit} (with a last name it must fit the game's name)", ""
    return "", "" if latin else UNICODE_NOTE


def check_entries(game: int, kind: str, text: str) -> list[Checked]:
    """Every entry of `text` (one per line; '#' lines and blank lines skipped), with why each refused one is
    refused: a problem of its own, one the game already has, one written twice, or past LIST_MAX."""
    stock = {s.casefold() for s in stock_entries(game, kind)}
    seen: set[str] = set()
    out: list[Checked] = []
    kept = 0
    for number, raw in enumerate(text.splitlines(), 1):
        entry = raw.strip()
        if not entry or entry.startswith("#"):
            continue
        problem, note = entry_problem(game, kind, entry)
        key = entry.casefold()
        if not problem and key in stock:
            problem = "is already one of the game's own"
        if not problem and key in seen:
            problem = "is in the list twice"
        if not problem and kept >= LIST_MAX:
            problem = f"is past the {LIST_MAX} a list may hold"
        if not problem:
            seen.add(key)
            kept += 1
        out.append(Checked(number, entry, problem, note if not problem else ""))
    return out


def kept_entries(game: int, kind: str, text: str) -> list[str]:
    return [c.text for c in check_entries(game, kind, text) if c.ok]


# ---- the library -------------------------------------------------------------------------------------------

def library_path(game: int, kind: str, root: Path | None = None) -> Path:
    return Path(root or LIBRARY_DIR) / f"vv{game}" / FILE_NAMES[kind]


def read_library(game: int, kind: str, root: Path | None = None) -> str:
    """The player's list as they wrote it ("" when there is none)."""
    try:
        return library_path(game, kind, root).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return ""


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".tmp-", suffix=".txt", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(temp, path)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise


def write_library(game: int, kind: str, text: str, root: Path | None = None) -> Path:
    """Keep the player's list as they wrote it (refused lines too: the window shows why, and they can fix them)."""
    path = library_path(game, kind, root)
    _atomic_write(path, text if text.endswith("\n") or not text else text + "\n")
    return path


def game_file_text(game: int, kind: str, entries: list[str]) -> str:
    header = (f"# Custom Stuff: your {KIND_LABELS[kind]} for Virtual Villagers - {TITLES[game]}.\n"
              "# Written by the Virtual Villagers Fun Patcher's Custom Stuff window: change them there.\n")
    return header + "".join(e + "\n" for e in entries)


def apply_library(game: int, game_folder: Path, root: Path | None = None) -> Path | None:
    """Copy the checked entries of every list into the patched game in `game_folder`
    ("<folder>\\Virtual Villagers Fun Patcher Files\\Custom Stuff\\"); used from the game's next start.  A folder
    that is not a patched game is left alone (None).  An empty list writes an empty file, so a name removed from the
    library is gone from the game too."""
    patcher = Path(game_folder) / PATCHER_FILES
    if not patcher.is_dir():
        return None
    target = patcher / GAME_SUBFOLDER
    for kind in KINDS:
        entries = kept_entries(game, kind, read_library(game, kind, root))
        path = target / FILE_NAMES[kind]
        if not entries and not path.exists():
            continue
        _atomic_write(path, game_file_text(game, kind, entries))
    return target


def has_entries(game: int, root: Path | None = None) -> bool:
    return any(kept_entries(game, kind, read_library(game, kind, root)) for kind in KINDS)


# ---- the AI prompt and templates ---------------------------------------------------------------------------

def ai_prompt(game: int, kind: str, how_many: int = 40) -> str:
    """A prompt to paste into any AI chat: it asks for `how_many` new entries in the style of the game's own list,
    one per line, within the rules the window checks."""
    stock = ", ".join(stock_entries(game, kind))
    title = f"Virtual Villagers - {TITLES[game]}"
    if kind in ("male", "female"):
        sex = "male" if kind == "male" else "female"
        rules = (f"- One word each, at most {FIRST_MAX} letters, letters only (accented letters are fine).\n"
                 "- Easy to read and say, in the same island style as the list below.\n"
                 "- Not one of the names in the list below, and no name twice.\n")
        what = f"{how_many} new {sex} first names for villagers in the game {title}"
        listed = f"The game's own {sex} first names (match their style):"
    elif kind == "last":
        rules = (f"- One word each, at most {LAST_MAX} letters, letters only (accented letters are fine).\n"
                 "- They are family names that parents pass on to their children.\n"
                 "- Not one of the names in the list below, and no name twice.\n")
        what = f"{how_many} new last names (family names) for villagers in the game {title}"
        listed = "The game's own last names (match their style):"
    else:
        rules = (f"- One word or a very short phrase each, at most {LIKE_MAX} letters, no commas.\n"
                 "- Each must make sense both as \"likes ...\" and as \"dislikes ...\" (a thing or an activity on a "
                 "tropical island in a simple, timeless village: no modern technology).\n"
                 "- Lowercase, like the list below. Not one of the words in the list below, and no word twice.\n")
        what = f"{how_many} new likes and dislikes for villagers in the game {title}"
        listed = "The game's own likes and dislikes (match their style):"
    return (f"Please write {what}.\n\n"
            "Rules:\n" + rules +
            "- Kind and family-friendly.\n"
            "- Answer with the list only: one per line, no numbers, no bullets, no extra text.\n\n"
            f"{listed}\n{stock}\n")


def template_text(game: int, kind: str) -> str:
    """A ready-to-fill file for `kind`: what goes in it, then a few example lines the player replaces."""
    examples = {
        "male": ("Kaimana", "Tavita"),
        "female": ("Leilani", "Moana"),
        "last": ("Kealoha", "Makoa"),
        "likes": ("sea glass", "kites"),
    }[kind]
    limit = {"male": FIRST_MAX, "female": FIRST_MAX, "last": LAST_MAX, "likes": LIKE_MAX}[kind]
    one = "one word or short phrase" if kind == "likes" else "one word"
    return (f"# Custom Stuff template: {KIND_LABELS[kind]} for Virtual Villagers - {TITLES[game]}.\n"
            f"# One per line: {one}, at most {limit} letters, no % and no commas.\n"
            "# Lines starting with # are notes and are skipped. Replace the examples below with your own,\n"
            "# then use Import... in the Custom Stuff window.\n"
            + "".join(e + "\n" for e in examples))
