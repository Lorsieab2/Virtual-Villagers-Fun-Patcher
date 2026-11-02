"""Old "?" names in the logs, rewritten to the real names (v1.35.89; the owner: "Yes you can rewrite old ?
Names").

Up to v1.35.88 the parentage exporter ("VVFP Parentage Export.dll") wrote each byte 0x80-0xFF of a name
as '?': a villager the player named "Zoe Nunez" with her accents (Render Unicode with In-Game Fonts,
v1.35.87) is "Zo? ???ez" in that build's Births, Deaths, Arrived and History records.  The save holds her
real name.  Repair Saves & Logs offers to rewrite each such record's name to the real one:

  * a log name is one save villager's real name with each byte 0x80-0xFF as '?' (vv_long_names.
    legacy_mask), and NO other villager of the save has the same masked name -- a mask two villagers
    share is left alone and reported (`shared`);
  * the record's own Head and Body (and Sex, when it gives one) are that villager's -- the rest of the
    identity -- so a record of somebody else is never touched;
  * the rewrite is the patcher's renaming of a villager across the logs (vv_last_names.plan_renames),
    with the same mechanics as every repair: the game must be closed, the save folder is backed up
    first, each record keeps its place and number, no record is added, removed or moved, and any
    failure puts every changed file back.  A second repair finds nothing.
The save is never changed (it already holds the real names).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import vv_last_names as ln
import vv_long_names
import vv_save_backup

BACKUP_LABEL = "(before rewriting old question-mark names)"  # no "?": a folder name cannot hold one
_VALUE = re.compile(r"^(?P<indent>[ \t]*)(?P<label>[A-Za-z][A-Za-z ]*): (?P<value>.*?)\s*$")
_HEADING = re.compile(r"^\S.*$")


@dataclass(frozen=True)
class Found:
    """One record line whose name an older exporter wrote with '?'."""
    path: Path
    record: str                    # the record's heading: "Birth 5", "Death 3", "Villager 7", ...
    masked: str                    # as the log holds it: "Zo? ???ez"
    real: str                      # the save's: "Zoe Nunez" with her accents
    head: int
    body: int

    def describe(self) -> str:
        return f"\"{self.masked}\" → \"{self.real}\" ({self.path.name}, {self.record})"


@dataclass
class Survey:
    found: list[Found] = field(default_factory=list)
    shared: dict[str, list[str]] = field(default_factory=dict)     # masked name -> the save names sharing it

    def renames(self) -> dict[tuple, str]:
        return {(f.masked, f.head, f.body): f.real for f in self.found}


def _villagers(folder: Path, game: int, slot: int):
    return ln.living(Path(folder), game, slot, bodies=True)


def survey(folder: Path, game: int, slot: int) -> Survey:
    """Every log record of this slot's village whose name is an old '?' name of a save villager.  Reads
    only."""
    folder = Path(folder)
    people = _villagers(folder, game, slot)
    actual = {v.name for v in people}
    by_mask: dict[str, list] = {}
    for v in people:
        masked = vv_long_names.legacy_mask(v.name)
        # Never "?" alone (the bump-on-the-head name), never a name a save villager really has.
        if masked != v.name and not vv_long_names.only_question_marks(masked) and masked not in actual:
            by_mask.setdefault(masked, []).append(v)
    result = Survey()
    if not by_mask:
        return result
    import vv_log_tools as tools
    checker = tools.load_checker()
    # A name a "Name changed" record gave or took (a rename the logs record) was chosen as it is.
    renamed: set[str] = set()
    for path in checker.log_files(folder):
        try:
            text = path.read_bytes().decode("vv-game-text").replace("\r\n", "\n")
        except OSError:
            continue
        for block in text.split("\n\n"):
            lines = block.strip("\n").split("\n")
            if lines and lines[0].strip() == "Name changed":
                for line in lines[1:]:
                    m = _VALUE.match(line)
                    if m is not None and m.group("label") in ("Name", "Old name", "New name"):
                        renamed.add(m.group("value"))
    for masked in list(by_mask):
        if masked in renamed:
            del by_mask[masked]
    if not by_mask:
        return result
    for path in checker.log_files(folder):
        try:
            lines = path.read_bytes().decode("vv-game-text").replace("\r\n", "\n").split("\n")
        except OSError:
            continue
        heading = ""
        for k, line in enumerate(lines):
            if line and _HEADING.match(line) and ":" not in line.split(" ")[0]:
                heading = line.strip()
            m = _VALUE.match(line)
            if m is None or m.group("value") not in by_mask:
                continue
            masked = m.group("value")
            holders = by_mask[masked]
            if len({v.name for v in holders}) > 1:
                result.shared.setdefault(masked, sorted({v.name for v in holders}))
                continue
            # The record's own looks: the Head / Body (and Sex) lines that follow the name, before
            # the next name or record.
            head = body = sex = None
            indent = len(m.group("indent"))
            for nxt in lines[k + 1:k + 16]:
                n = _VALUE.match(nxt)
                if not nxt.strip() or not nxt[:1].isspace():
                    break                       # the record ends (a blank line, the next heading)
                if n is None:
                    continue
                if len(n.group("indent")) <= indent and n.group("label") in ("Name", "Child", "Mother", "Father",
                                                                              "Parents"):
                    break                       # somebody else's name: these looks are not hers
                label, value = n.group("label"), n.group("value")
                if label == "Head" and head is None:
                    head = value
                elif label == "Body" and body is None:
                    body = value
                elif label == "Sex" and sex is None:
                    sex = value
            for v in holders:
                if (head is not None and body is not None and head.isdigit() and body.isdigit()
                        and int(head) == v.head and int(body) == v.body and (sex is None or sex == v.sex)):
                    result.found.append(Found(path, heading, masked, v.name, v.head, v.body))
                    break
    return result


def plan(folder: Path, game: int, slot: int, found: Survey | None = None) -> ln.Plan:
    """What rewriting the old '?' names changes, file by file (the logs only).  Reads only."""
    found = found if found is not None else survey(folder, game, slot)
    return ln.plan_renames(Path(folder), game, slot, found.renames(), dead=True, ask=False)


def repair(folder: Path, game: int, slot: int, processes: vv_save_backup.ProcessController | None = None,
           now: datetime | None = None) -> ln.Result:
    """Rewrite every old '?' name to the save's real name.  Refused (nothing changed) while the game runs
    or when there is nothing to rewrite; the save folder is backed up first; any failure puts every
    changed file back."""
    folder = Path(folder)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    ln.tools._refuse_if_running(folder, controller)
    found = survey(folder, game, slot)
    if not found.found:
        raise ln.LastNamesError("No old \"?\" name to rewrite was found.")
    work = plan(folder, game, slot, found)
    return ln.apply(folder, work, controller, now, BACKUP_LABEL, "rewriting the old question-mark names")


def describe(found: list[Found], limit: int = 12) -> str:
    text = "; ".join(f.describe() for f in found[:limit])
    return text + (f"; and {len(found) - limit} more" if len(found) > limit else "")
