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

NOTHING IS EVER MOVED OR RENAMED, here or in the game.  A v1.35.64 preview's Repair Saves & Logs moved
the files to their new names while A New Home was still patched by v1.35.63, whose companion then
found "Parentage Records" empty and offered to "fill in" 69 villagers' parents.  So every file stays
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


def writable(folder: Path, relative: str) -> Path:
    """Where to append to `relative` (its new name), a file or a folder read from both places when
    both exist: an older build's while only it exists, else the new one."""
    folder = Path(folder)
    old_rel = old_name(relative)
    if old_rel and (folder / old_rel).exists() and not (folder / relative).exists():
        return folder / old_rel
    return folder / relative
