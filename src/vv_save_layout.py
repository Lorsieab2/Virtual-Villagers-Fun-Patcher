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
    """Where this build WRITES the slot's `sub` logs: "...Logs\\Save <slot>\\<sub>" (never made here)."""
    return Path(folder) / slot_folder(slot) / sub


def header_slot(header: str | None) -> int | None:
    """The slot a "Village: <name> (Save <S>)" header names -- the LAST such marker, as every reader
    takes it -- or None."""
    found = _SLOT_HEADER.findall(header or "")
    return int(found[-1]) if found else None


def log_folders(folder: Path, sub: str, slot: int | None = None) -> list[Path]:
    """Every folder that may hold `sub`'s logs, in reading order (oldest first): the shared folder under
    an older build's name, the shared folder, then the slot folders -- only `slot`'s, or all five when
    `slot` is None (a game-wide count).  Nothing need exist and nothing is made."""
    folder = Path(folder)
    shared = f"{LOGS}\\{sub}"
    out: list[Path] = []
    old = old_name(shared)
    if old:
        out.append(folder / old)
    out.append(folder / shared)
    out.extend(slot_log_folder(folder, sub, s) for s in SLOTS if slot is None or s == int(slot))
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
    """The slot when `path` lies inside a "...Logs\\Save <S>" folder, else None."""
    parts = [p.lower() for p in Path(path).parts]
    for i, part in enumerate(parts[:-1]):
        if part == LOGS.lower():
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


def writable(folder: Path, relative: str) -> Path:
    """Where to append to `relative` (its new name), a file or a folder read from both places when
    both exist: an older build's while only it exists, else the new one."""
    folder = Path(folder)
    old_rel = old_name(relative)
    if old_rel and (folder / old_rel).exists() and not (folder / relative).exists():
        return folder / old_rel
    return folder / relative
