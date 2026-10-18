"""The names of the folders and files the patcher keeps in a save folder, and the names older builds
used (the owner, 2026-10-09: "rename the patcher-created folders and files to accurately explain what
they contain. and sort things in separate folders, appropriately named too" -- the save folders only;
Tribe History and Tribe Population keep their names -- and then: "from now on use the new renaming,
but it also recognizes the old renaming").

    new name                                      older builds' name
    Logs\\Deaths and Disappearances               Logs\\Deaths
    Logs\\Repairs Made                            Logs\\Repairs
    Family Trees\\Reports                         Logs\\Genealogy
    Data\\Family Tree Edits\\... Family Tree Edits Data\\Genealogy\\... Genealogy Edits
    Data\\Unaccounted Villagers\\Virtual Villagers G Villagers at Last Save
                                                  ...\\Virtual Villagers G Village Roster
    Data\\Village Statistics\\Villagers Counted     ...\\Village Roster
    Data\\Like and Dislike Words                  Data\\Log Words
    Data\\Log Checks                              Data\\Cross-Check
    Data\\Parents (A New Home)                    Data\\Parentage Records
    Data\\Copies Made Before Repairs\\<the place>  (new copies only; older ones stay beside their
                                                  files, and nothing reads them)

NOTHING IS MOVED OR RENAMED AUTOMATICALLY, here or in the game.  A v1.35.64 preview's Repair Saves &
Logs moved the files to their new names while A New Home was still patched by v1.35.63, whose
companion then found "Parentage Records" empty and offered to "fill in" 69 villagers' parents.  Only
the player's own "Move Old Files to New Names..." in Repair Saves & Logs (src/vv_move_old_names.py)
moves them, once every game that plays the save reads the new names.  Otherwise every file stays
where it is, and every reader and writer (here and native/shared/save_layout.h) picks, at the point
of use:

  - only the new name exists: the new one;
  - only the old name exists: the old one, for reading AND writing;
  - neither: the new name;
  - both (an older and a newer build both played the village):
      a whole file (the parents, the rosters, the Family Tree Edits, a marker): the one written last
        (`find`), read and written from then on; the other is never touched;
      a folder (the Deaths, Repairs and Genealogy logs): written in the new one (`find`, `writable`);
        the Deaths logs are read from both, a record kept in both counted once
        (scripts/vvfp_consistency_check.py deaths_records);
      the Like and Dislike Words: read from both, the smaller boundary of each log file taken
        (`places`; scripts/vvfp_consistency_check.py word_boundaries), new boundaries written to the
        new one (`writable`);
      a Repair Saves & Logs approval: the game acts on neither (native/shared/crosscheck_bridge.h).

Nothing here creates a folder.  The Backups folder is never touched."""
from __future__ import annotations

import os
import re
from pathlib import Path

LOGS = "Virtual Villagers Fun Patcher Logs"
DATA = "Virtual Villagers Fun Patcher Data"
TREES = "Virtual Villagers Fun Patcher Family Trees"
COPIES = "Copies Made Before Repairs"

DEATHS_LOGS = "Deaths and Disappearances"
REPAIRS_LOGS = "Repairs Made"
TREE_REPORTS = "Reports"
TREE_EDITS = "Family Tree Edits"
LOG_WORDS = "Like and Dislike Words"
LOG_CHECKS = "Log Checks"
PARENTS_VV1 = "Parents (A New Home)"

# (old folder, new folder), relative to the save folder.
FOLDERS = (
    (f"{LOGS}\\Deaths", f"{LOGS}\\{DEATHS_LOGS}"),
    (f"{LOGS}\\Repairs", f"{LOGS}\\{REPAIRS_LOGS}"),
    (f"{LOGS}\\Genealogy", f"{TREES}\\{TREE_REPORTS}"),
    (f"{DATA}\\Log Words", f"{DATA}\\{LOG_WORDS}"),
    (f"{DATA}\\Cross-Check", f"{DATA}\\{LOG_CHECKS}"),
    (f"{DATA}\\Parentage Records", f"{DATA}\\{PARENTS_VV1}"),
)
# (old folder, new folder, the new name read back, the old name): files renamed.
FILES = (
    (f"{DATA}\\Genealogy", f"{DATA}\\{TREE_EDITS}",
     re.compile(r"^(Virtual Villagers \d) Family Tree Edits( - Save \d+\.json)$"), r"\1 Genealogy Edits\2"),
    (f"{DATA}\\Unaccounted Villagers", f"{DATA}\\Unaccounted Villagers",
     re.compile(r"^(Virtual Villagers \d) Villagers at Last Save( - Save \d+\.dat.*)$"), r"\1 Village Roster\2"),
    (f"{DATA}\\Village Statistics", f"{DATA}\\Village Statistics",
     re.compile(r"^Villagers Counted( - Save \d+\.dat.*)$"), r"Village Roster\1"),
)
# The same renames read forwards, one for each line of FILES: (an older build's name, its new name).
FILES_FORWARD = (
    (re.compile(r"^(Virtual Villagers \d) Genealogy Edits( - Save \d+\.json)$"), r"\1 Family Tree Edits\2"),
    (re.compile(r"^(Virtual Villagers \d) Village Roster( - Save \d+\.dat.*)$"), r"\1 Villagers at Last Save\2"),
    (re.compile(r"^Village Roster( - Save \d+\.dat.*)$"), r"Villagers Counted\1"),
)


def new_file_name(index: int, name: str) -> str | None:
    """The new name of a file named `name` in FILES[index]'s older folder, or None when it is not
    one of that line's files (old_name of the result gives `name` back)."""
    forward, template = FILES_FORWARD[index]
    if not forward.match(name):
        return None
    new = forward.sub(template, name)
    _old_folder, _new_folder, back, old_file = FILES[index]
    return new if back.match(new) and back.sub(old_file, new) == name else None


def old_name(relative: str) -> str | None:
    """Where an older build kept the file or folder `relative` (a path under its new name, relative to
    the save folder), or None when its name did not change."""
    rel = relative.replace("/", "\\")
    for old, new in FOLDERS:
        if rel.lower() == new.lower() or rel.lower().startswith(new.lower() + "\\"):
            rel = old + rel[len(new):]
            break
    for old_folder, new_folder, back, old_file in FILES:
        head, _, name = rel.rpartition("\\")
        if head.lower() == new_folder.lower() and back.match(name):
            return f"{old_folder}\\{back.sub(old_file, name)}"
    return rel if rel != relative.replace("/", "\\") else None


def places(folder: Path, relative: str) -> list[Path]:
    """Every place `relative` (its new name) is in the save folder: the older build's first, then
    the new one -- both when both exist, none when neither does."""
    folder = Path(folder)
    old = old_name(relative)
    found = [folder / old] if old and (folder / old).exists() else []
    return found + ([folder / relative] if (folder / relative).exists() else [])


def _written(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return -1


def find(folder: Path, relative: str) -> Path:
    """The one place to read and write `relative` (its new name): the new one, an older build's while
    only it exists, the new one when neither does; under both names a file is the one written last
    (a tie: the new one) and a folder the new one."""
    folder = Path(folder)
    new = folder / relative
    old_rel = old_name(relative)
    if not old_rel or not (folder / old_rel).exists():
        return new
    old = folder / old_rel
    if not new.exists():
        return old
    if old.is_file() and new.is_file() and _written(old) > _written(new):
        return old
    return new


# ---- One folder of logs per save slot (the owner, 2026-10-10: "separate log per slot", then "Just put
# the logs in separate folders per slot"; native/shared/log_slot.h is the games' side) -----------------
#
#     <save folder>\Virtual Villagers Fun Patcher Logs\Save <S>\<the log's own folder>\<its own name>
#
# Every log keeps its folder and file names; only the parent folder is the slot's.  The shared
# "...Logs\<the log's folder>\" older builds wrote (and an older build's name for it, FOLDERS above) is
# NEVER moved, split, renamed or deleted: every reader reads it first -- each record kept only under its
# own slot's "Village: <name> (Save <S>)" header -- and then the slot's folder, as one history.  Numbered
# records ("Conception <n>", "Birth <n>", "Death <n>", "Arrived <n>", "Island event <n>",
# "Unaccounted <n>", "Repair <n>") are numbered per GAME, so a new number follows the highest printed in
# every folder of the game (log_folders with slot None).
#
# The Logs folder's own sub-folders (`sub` below): "Births and Conceptions", "Deaths and Disappearances",
# "Unaccounted Villagers", "Island Events", "Tribe Population", "Tribe History", "Village Statistics",
# "Repairs Made".

SLOTS = (1, 2, 3, 4, 5)
_SLOT_HEADER = re.compile(r" \(Save ([1-5])\)")


def slot_folder(slot: int) -> str:
    """"Virtual Villagers Fun Patcher Logs\\Save <slot>", relative to the save folder."""
    return f"{LOGS}\\Save {int(slot)}"


def slot_log_folder(folder: Path, sub: str, slot: int) -> Path:
    """Where this build WRITES the slot's `sub` logs: the save's own "Virtual Villagers Fun
    Patcher\\Save <slot>\\Logs\\<sub>", or the older "...Logs\\Save <slot>\\<sub>" while it holds the
    slot's logs and the new one is not there (`route`).  Never made here."""
    return route(folder, f"{slot_folder(slot)}\\{sub}")


def older_slot_log_folder(folder: Path, sub: str, slot: int) -> Path:
    """The slot's `sub` logs in the older layout, "...Logs\\Save <slot>\\<sub>" (only read)."""
    return Path(folder) / slot_folder(slot) / sub


def own_slot_log_folder(folder: Path, sub: str, slot: int) -> Path:
    """The slot's `sub` logs in the save's own folder, "Virtual Villagers Fun Patcher\\Save <slot>\\Logs\\
    <sub>" (whether it is there or not)."""
    return Path(folder) / save_root(slot) / SAVE_LOGS / sub


def header_slot(header: str | None) -> int | None:
    """The slot a "Village: <name> (Save <S>)" header names -- the LAST such marker, as every reader
    takes it -- or None."""
    found = _SLOT_HEADER.findall(header or "")
    return int(found[-1]) if found else None


def log_folders(folder: Path, sub: str, slot: int | None = None) -> list[Path]:
    """Every folder that may hold `sub`'s logs, in reading order (oldest first): the shared folder under
    an older build's name, the shared folder, then for each slot -- only `slot`'s, or all five when
    `slot` is None (a game-wide count) -- its older "...Logs\\Save <S>\\<sub>" and then the save's own
    "Virtual Villagers Fun Patcher\\Save <S>\\Logs\\<sub>".  Nothing need exist and nothing is made."""
    folder = Path(folder)
    shared = f"{LOGS}\\{sub}"
    out: list[Path] = []
    old = old_name(shared)
    if old:
        out.append(folder / old)
    out.append(folder / shared)
    for s in SLOTS:
        if slot is None or s == int(slot):
            out += [older_slot_log_folder(folder, sub, s), own_slot_log_folder(folder, sub, s)]
    return out


def numbered_logs(folder: Path, sub: str, stem: str, slot: int | None = None) -> list[Path]:
    """Every existing "<stem> <n>.txt" of `sub`'s logs, folder by folder in log_folders' order and by
    number within each: the one history a slot's (or, slot None, the game's) records are read from."""
    files: list[Path] = []
    pattern = re.compile(re.escape(stem) + r" (\d+)\.txt", re.I)
    for place in log_folders(folder, sub, slot):
        if not place.is_dir():
            continue
        found = []
        for p in place.iterdir():
            m = pattern.fullmatch(p.name)
            if m and p.is_file():
                found.append((int(m.group(1)), p))
        files.extend(p for _, p in sorted(found))
    return files


def is_slot_folder(path: Path) -> int | None:
    """The slot when `path` lies inside a "...Logs\\Save <S>" folder or a save's own "Virtual Villagers
    Fun Patcher\\Save <S>\\Logs" folder, else None."""
    parts = [p.lower() for p in Path(path).parts]
    for i, part in enumerate(parts[:-1]):
        if part == LOGS.lower():
            m = re.fullmatch(r"save ([1-5])", parts[i + 1])
            return int(m.group(1)) if m else None
        if part == SAVES.lower() and i + 2 < len(parts) and parts[i + 2] == SAVE_LOGS.lower():
            m = re.fullmatch(r"save ([1-5])", parts[i + 1])
            return int(m.group(1)) if m else None
    return None


def slot_first_logs(folder: Path, sub: str, stem: str, slot: int) -> list[Path]:
    """For a log the game REWRITES at each save (Tribe Population's "Village Population <n>.txt"): the
    slot folder's numbered files when it has any, else the shared ones (an older build's, read only
    while the slot has none of its own)."""
    own = [p for p in numbered_logs(folder, sub, stem, slot) if is_slot_folder(p)]
    return own or [p for p in numbered_logs(folder, sub, stem, slot) if not is_slot_folder(p)]


def marker_numbers(path: Path, marker: str) -> tuple[int, int]:
    """(how many lines of `path` begin with `marker` -- "Repair ", "Death " --, the highest number
    printed straight after it; 0 when none): log_slot.h vv_log_marker_numbers_a.  (0, 0) when the
    file is not there; OSError when it is there and cannot be read."""
    try:
        text = Path(path).read_bytes().decode("latin-1")
    except FileNotFoundError:
        return 0, 0
    count = highest = 0
    for line in text.split("\n"):
        if line.startswith(marker):
            count += 1
            m = re.match(r"\d+", line[len(marker):])
            if m:
                highest = max(highest, int(m.group(0)))
    return count, highest


def repairs_highest(folder: Path, game: int) -> int:
    """The highest "Repair <n>" printed in ANY of the game's Repairs files: an older build's
    "Repairs", the shared "Repairs Made" and every slot's (repairs_log.h vv_repairs_highest)."""
    highest = 0
    for path in numbered_logs(folder, REPAIRS_LOGS, f"Virtual Villagers {int(game)} Repairs Log", None):
        highest = max(highest, marker_numbers(path, "Repair ")[1])
    return highest


def append_target(folder: Path, sub: str, stem: str, slot: int, marker: str | None = None,
                  per_file: int = 256, max_bytes: int = 4 * 1024 * 1024) -> Path:
    """The file of the slot's own folder a new record of `sub` is appended to: its highest-numbered
    "<stem> <n>.txt" while it holds fewer than `per_file` `marker` records and `max_bytes` bytes,
    else the next number ("<stem> 1.txt" when the slot has none).  Never made here."""
    place = slot_log_folder(folder, sub, slot)
    files = [p for p in numbered_logs(folder, sub, stem, slot) if p.parent == place]
    if not files:
        return place / f"{stem} 1.txt"
    last = files[-1]
    number = int(re.search(r" (\d+)\.txt$", last.name).group(1))
    try:
        size = last.stat().st_size
    except OSError:
        size = 0
    records = marker_numbers(last, marker)[0] if marker else 0
    if size >= max_bytes or (marker and records >= per_file):
        return place / f"{stem} {number + 1}.txt"
    return last


# ---- One folder per save slot for everything the patcher keeps about it (the owner, 2026-10-17: "FOR
# ANYTHING IN THE SAVES FOLDER, PLEASE MAKE SEPARATE FOLDERS TO PUT ALL THE LOGS AND DATA FOR EACH SAVE
# IN ALL 5 GAMES ... I JUST WANNA DELETE EVERYTHING IN ONE FILE"; native/shared/per_save.h is the games'
# side and keeps the same rules) ------------------------------------------------------------------------
#
#     <save folder>\Virtual Villagers Fun Patcher\Save <S>\Logs\<the log's own folder>\<its own name>
#     <save folder>\Virtual Villagers Fun Patcher\Save <S>\Data\<the kind's folder>\<... - Save <S>.dat>
#
# A path of the older layout ("...Logs\Save <S>\<sub>\..." or "...Data\<kind>\<name> - Save <S>.<ext>")
# is ROUTED (`route`) to one place, decided by what is already there -- never by a clock, never by a
# guess -- so a writer and every reader always agree and no history is ever split:
#
#   a log: its unit is the slot's folder of that log ("Logs\Save <S>\Deaths and Disappearances").  The
#     new folder once it exists; else the older one while it holds anything (it is written where it is
#     until the player moves it with Repair Saves & Logs' "Move Files to Save Folders..."); else the new.
#     Readers read both (`log_folders`), older first.
#   a data file: its unit is the file.  Only one place has it: that one; both (an older patch wrote
#     after a newer one): the one written last (a tie: the new); neither: the new.
#
# Nothing is ever moved, renamed or deleted here.  NOT per save, and never routed: the older shared
# logs ("...Logs\<sub>\", no slot), the Like and Dislike Words of the older layout, a loose file in the
# Data folder itself (an older build's; the games move it into its folder when they read it), the
# Copies Made Before Repairs of an older-layout file, Backups, the Family Trees folder and the game's
# own saves.

SAVES = "Virtual Villagers Fun Patcher"
SAVE_LOGS = "Logs"
SAVE_DATA = "Data"
MAX_PATH = 260                     # the games' path limit: a new place that would not fit is never used
_DATA_SLOT = re.compile(r" - Save ([1-5])(?=\.|$)(\.[^.\\]*)?", re.I)   # per_save.h vv_ps_classify
_OLDER_DATA_FOLDERS = ("cross-check", "parentage records", "log words", "genealogy")
_OLDER_DATA_FILE = re.compile(r"(^| )Village Roster - Save | Genealogy Edits - Save ", re.I)


def save_root(slot: int) -> str:
    """"Virtual Villagers Fun Patcher\\Save <slot>", relative to the save folder: everything of that
    save, in one folder."""
    return f"{SAVES}\\Save {int(slot)}"


def per_save_place(relative: str) -> tuple[int, str, str] | None:
    """(slot, the place in the save's own folder, "folder" or "file") for an older-layout path of a
    save's log or data file (relative to the save folder), or None when it is not one save's (see
    above).  Names only; nothing is looked at."""
    rel = str(relative).replace("/", "\\").strip("\\")
    low = rel.lower()
    logs = f"{LOGS}\\save ".lower()
    if low.startswith(logs) and len(rel) > len(logs) and rel[len(logs)] in "12345" \
            and (len(rel) == len(logs) + 1 or rel[len(logs) + 1] == "\\"):
        slot = int(rel[len(logs)])
        rest = rel[len(logs) + 2:]
        return slot, f"{save_root(slot)}\\{SAVE_LOGS}" + (f"\\{rest}" if rest else ""), "folder"
    data = f"{DATA}\\".lower()
    if not low.startswith(data):
        return None
    rest = rel[len(data):]
    head, _, name = rest.rpartition("\\")
    if not head or head.lower().split("\\")[0] == COPIES.lower():
        return None
    # A file under an OLDER BUILD'S NAME stays where it is: the save's own folder holds only the newest
    # names, and an older patch reads only the older place (per_save.h vv_ps_classify).
    if head.lower().split("\\")[0] in _OLDER_DATA_FOLDERS or _OLDER_DATA_FILE.search(name):
        return None
    found = list(_DATA_SLOT.finditer(name))
    if not found:
        return None
    return int(found[-1].group(1)), f"{save_root(int(found[-1].group(1)))}\\{SAVE_DATA}\\{rest}", "file"


def _there(path: Path) -> bool | None:
    """True a file or folder, False certainly absent, None there but not examinable (counted as there,
    as native/shared/save_layout.h vv_layout_probe_w does)."""
    try:
        os.stat(path)
        return True
    except (FileNotFoundError, NotADirectoryError):
        return False
    except OSError:
        return None


def _holds_anything(path: Path) -> bool:
    try:
        with os.scandir(path) as entries:
            return any(True for _ in entries)
    except (FileNotFoundError, NotADirectoryError):
        return False
    except OSError:
        return True


def _file_unit(path: Path) -> Path:
    """The data file a helper file belongs to ("x - Save 1.dat.tmp" -> "x - Save 1.dat")."""
    found = list(_DATA_SLOT.finditer(path.name))
    return path.with_name(path.name[:found[-1].end()]) if found else path


def _fits(path: Path) -> bool:
    return len(str(path)) + 32 < MAX_PATH


def route(folder: Path, relative: str) -> Path:
    """The one place to read AND write `relative` (an older-layout path under its newest name, relative
    to the save folder): the save's own folder or the older layout, by the rules above.  Not one save's:
    `find`'s answer, as before."""
    folder = Path(folder)
    rel = str(relative).replace("/", "\\")
    old = find(folder, rel)
    place = per_save_place(rel)
    if place is None:
        return old
    slot, new_rel, unit = place
    new = folder / new_rel
    if not _fits(new):
        return old
    if unit == "folder":
        tail = new_rel.split("\\")[3:4]               # the log's own folder under "Save <S>\Logs"
        old_unit = folder / slot_folder(slot) / tail[0] if tail else folder / slot_folder(slot)
        new_unit = folder / save_root(slot) / SAVE_LOGS / tail[0] if tail else folder / save_root(slot) / SAVE_LOGS
        if new_unit.is_dir() or not _holds_anything(old_unit):
            return new
        return old
    old_unit, new_unit = _file_unit(old), _file_unit(new)
    old_there, new_there = _there(old_unit), _there(new_unit)
    if old_there is False:
        return new
    if new_there is False:
        return old
    if old_unit.is_file() and new_unit.is_file() and _written(old_unit) > _written(new_unit):
        return old
    return new


def both_places(folder: Path, relative: str) -> list[Path]:
    """Every place an older-layout path (its newest name) is: the older layout's first, then the save's
    own folder -- both when both exist, none when neither does."""
    folder = Path(folder)
    out = places(folder, relative)
    place = per_save_place(relative)
    if place is not None and (folder / place[1]).exists():
        out.append(folder / place[1])
    return out


def older_layout(folder: Path, path: Path) -> str | None:
    """Where in the older layout a file of the save's own folder was kept (relative to the save
    folder), or None when `path` is not in a save's own folder."""
    try:
        parts = Path(path).resolve().relative_to(Path(folder).resolve()).parts
    except ValueError:
        return None
    if len(parts) < 3 or parts[0].lower() != SAVES.lower() or not re.fullmatch(r"(?i)save [1-5]", parts[1]):
        return None
    slot = int(parts[1][-1])
    rest = "\\".join(parts[3:])
    if parts[2].lower() == SAVE_LOGS.lower():
        return f"{slot_folder(slot)}" + (f"\\{rest}" if rest else "")
    if parts[2].lower() == SAVE_DATA.lower():
        return f"{DATA}" + (f"\\{rest}" if rest else "")
    return None


# The Like and Dislike Words boundaries (native/shared/log_words.h) are keyed by each log file's path
# inside the save folder.  A log in a save's own folder has its boundaries in that save's own
# "Virtual Villagers Fun Patcher\Save <S>\Data\Like and Dislike Words\Virtual Villagers <G> Log Words.dat",
# so deleting the save's folder takes them with it (a boundary left behind would apply to a new log of
# the same name and turn its correct words into wrong ones).  Every other log's stay in the shared file.

def words_key_slot(key: str) -> int | None:
    """The save whose own folder the log `key` (its path inside the save folder) is in, or None."""
    m = re.match(re.escape(SAVES) + r"\\Save ([1-5])\\", str(key).replace("/", "\\"), re.I)
    return int(m.group(1)) if m else None


def save_words_file(folder: Path, game: int, slot: int) -> Path:
    """The save's own Like and Dislike Words file (whether it is there or not)."""
    return Path(folder) / save_root(slot) / SAVE_DATA / LOG_WORDS / f"Virtual Villagers {int(game)} Log Words.dat"


def words_files(folder: Path, game: int) -> list[Path]:
    """Every Like and Dislike Words file of the game that exists: the shared one(s) (an older build's
    "Log Words" first), then each save's own.  Read them all; a log's boundary is the smallest."""
    out = places(folder, f"{DATA}\\{LOG_WORDS}\\Virtual Villagers {int(game)} Log Words.dat")
    return out + [p for p in (save_words_file(folder, game, s) for s in SLOTS) if p.exists()]


def words_file_for(folder: Path, game: int, key: str) -> Path:
    """The Like and Dislike Words file a boundary for the log `key` is appended to: its save's own when
    the log is in a save's own folder, else the shared one (an older build's while only it exists)."""
    slot = words_key_slot(key)
    if slot is not None:
        return save_words_file(folder, game, slot)
    return writable(folder, f"{DATA}\\{LOG_WORDS}\\Virtual Villagers {int(game)} Log Words.dat")


def writable(folder: Path, relative: str) -> Path:
    """Where to append to `relative` (its new name), a file or a folder read from both places when
    both exist: an older build's while only it exists, else the new one."""
    folder = Path(folder)
    old_rel = old_name(relative)
    if old_rel and (folder / old_rel).exists() and not (folder / relative).exists():
        return folder / old_rel
    return folder / relative
