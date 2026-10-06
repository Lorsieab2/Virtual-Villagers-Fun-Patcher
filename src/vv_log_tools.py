"""Check Logs and Repair Logs: the patcher window's two log tools (all five games).

The owner (2026-10-04): beside Back Up / Restore Saves and Rename Tribe, a
"Check Logs..." that shows, for one village, whether every log and data file
the patcher keeps agrees with its save, and a "Repair Logs..." that has the
game itself repair them.  The owner (2026-10-05): no repair prompt during
gameplay -- "Repair Logs" is the player's own go-ahead, and the game repairs
without asking.

CHECK LOGS is the read-only checker scripts/vvfp_consistency_check.py, run
in-process: the same function the command line runs, so the window shows
whatever the checker reports (no list of files is kept here).  It only opens
files for reading, so it may run while the game is running, and it never
writes, moves or creates anything.  The Backups folder is never read.

REPAIR LOGS does not repair anything in Python.  The repairs belong to the
game's own cross-check (native/shared/crosscheck_bridge.h,
docs/first-load-cross-check.md), which never shows anything while a village
is being played.  Repair Logs is the player's approval, given beforehand with
the game closed (it is never paused or closed for this):

  1. the save folder is backed up with Back Up Saves' own copier, labelled
     "(before repair re-arm)";
  2. the "already checked" markers of the slot are cleared (REARM_MARKERS,
     the one list): each part of the check runs once per village and records
     that it is done in a marker, and while a marker is there that part finds
     nothing.  Clearing one never loses data: it only says "already
     checked", and the check it re-arms counts what the logs already hold
     before writing anything, so nothing is ever written twice;
  3. the slot's approval file is written (APPROVAL: 16 bytes, 'VRA1',
     version 1, game, slot).

The next time that village is played -- whatever the "Check logs
automatically" setting -- the game repairs everything confirmed wrong
WITHOUT asking: A New Home's parents as soon as the village has settled, the
rest at its next save (the quit save at the latest), anything still left
right after the quit save; every change is backed up and listed in the
Repairs log.  Then the game deletes the approval: it is used once.  Start Over
deletes it with the village (native/shared/save_reset.c).
"""
from __future__ import annotations

import importlib.util
import os
import struct
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import vv_save_backup

DATA = "Virtual Villagers Fun Patcher Data"
BACKUP_LABEL = vv_save_backup.BEFORE_REARM
CHECKER = Path(__file__).resolve().parents[1] / "scripts" / "vvfp_consistency_check.py"


class LogToolError(Exception):
    """Nothing was done; the message says why."""


class GameRunning(LogToolError):
    """The game that saves in this folder is running."""


# ---------------------------------------------------------------------------
# Check Logs
# ---------------------------------------------------------------------------


def load_checker():
    """scripts/vvfp_consistency_check.py as a module (the command line's own code)."""
    name = "vvfp_consistency_check"
    module = sys.modules.get(name)
    if module is not None and Path(getattr(module, "__file__", "")).resolve() == CHECKER:
        return module
    spec = importlib.util.spec_from_file_location(name, CHECKER)
    if spec is None or spec.loader is None:
        raise LogToolError(f"The log checker {CHECKER.name} is missing from the patcher's folder.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


@dataclass
class CheckResult:
    folder: Path
    slot: int
    game: int
    text: str                                   # the checker's own report, as the CLI prints it
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def wrong(self) -> int:
        return self.counts.get("WRONG", 0)

    @property
    def summary(self) -> str:
        parts = ", ".join(f"{self.counts.get(v, 0)} {v}" for v in ("OK", "WRONG", "NOTE", "UNCHECKED"))
        verdict = (
            "nothing is confirmed wrong"
            if not self.wrong
            else f"{self.wrong} confirmed wrong"
        )
        return f"Save {self.slot}: {verdict} ({parts})."


def check_logs(folder: Path, slot: int, game: int) -> CheckResult:
    """Run the read-only checker on one slot.  Nothing is written."""
    checker = load_checker()
    if game not in checker.SAVE_STEMS or slot not in (1, 2, 3, 4, 5):
        raise LogToolError(f"There is no game {game} save slot {slot}.")
    save = Path(folder) / f"{checker.SAVE_STEMS[game]}{slot}.ldw"
    if not save.is_file():
        raise LogToolError(f"Save {slot} has no tribe in {Path(folder).name} ({save.name} is not there).")
    try:
        report = checker.check(Path(folder), slot, game)
    except checker.CheckError as exc:
        raise LogToolError(str(exc)) from exc
    except OSError as exc:
        raise LogToolError(
            f"A file could not be read ({exc}). If the game is saving right now, "
            "try again in a moment. Nothing was changed."
        ) from exc
    return CheckResult(Path(folder), slot, game, report.render(), report.counts())


# ---------------------------------------------------------------------------
# Repair Logs: approve the repair, and re-arm the check
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Marker:
    """One "already checked" marker of the first-load cross-check."""

    what: str                   # what it records, for the confirmation
    games: tuple[int, ...]      # the games that write it
    path: str                   # relative to the save folder; {game} and {slot}
    source: str                 # the native code that writes and reads it


# EVERY marker that stops a part of the cross-check from finding anything
# again.  Repair Logs clears these and nothing else; a new once-per-village
# part of the check adds its marker here.
REARM_MARKERS: tuple[Marker, ...] = (
    Marker(
        "A New Home's parents checked against the Births and Conceptions log",
        (1,),
        DATA + r"\Cross-Check\Virtual Villagers {game} Cross-Check - Save {slot}.dat",
        "native/vv1_parentage/vv1_crosscheck.inc (vv1_xc_marker_state)",
    ),
    Marker(
        "graves already confirmed in the Deaths log",
        (1, 2, 3, 4, 5),
        DATA + r"\Deaths\Virtual Villagers {game} Graves Logged - Save {slot}.dat",
        "native/vvfp_cause_of_death/cod_backfill.inc (logged_bind)",
    ),
    Marker(
        "villagers' Arrived records already backfilled",
        (1, 2, 3, 4, 5),
        DATA + r"\Arrivals\Virtual Villagers {game} Arrivals Recorded - Save {slot}.dat",
        "native/shared/arrival_backfill.h (vv_arrival_marker_present)",
    ),
    Marker(
        "villagers' Birth records already backfilled from the save",
        (2, 3, 4, 5),
        DATA + r"\Births\Virtual Villagers {game} Births Recorded - Save {slot}.dat",
        "native/shared/arrival_backfill.h (vv_backfill_marker_present)",
    ),
)


# The player's approval for one slot (native/shared/crosscheck_bridge.h reads
# it, uses it once and deletes it; native/shared/save_reset.c deletes it at
# Start Over).
APPROVAL = DATA + r"\Cross-Check\Virtual Villagers {game} Repair Approved - Save {slot}.dat"
APPROVAL_MAGIC = 0x31415256          # 'V' 'R' 'A' '1'
APPROVAL_VERSION = 1


def approval_path(folder: Path, game: int, slot: int) -> Path:
    """Where the approval for ``game``'s ``slot`` is (present or not)."""
    if game not in (1, 2, 3, 4, 5) or slot not in (1, 2, 3, 4, 5):
        raise LogToolError(f"There is no game {game} save slot {slot}.")
    return Path(folder) / APPROVAL.format(game=game, slot=slot)


def approval_bytes(game: int, slot: int) -> bytes:
    return struct.pack("<4I", APPROVAL_MAGIC, APPROVAL_VERSION, game, slot)


def marker_paths(folder: Path, game: int, slot: int) -> list[tuple[Marker, Path]]:
    """Each marker of ``game`` for ``slot`` and where it would be (present or not)."""
    if game not in (1, 2, 3, 4, 5) or slot not in (1, 2, 3, 4, 5):
        raise LogToolError(f"There is no game {game} save slot {slot}.")
    return [
        (marker, Path(folder) / marker.path.format(game=game, slot=slot))
        for marker in REARM_MARKERS
        if game in marker.games
    ]


def present_markers(folder: Path, game: int, slot: int) -> list[tuple[Marker, Path]]:
    return [(marker, path) for marker, path in marker_paths(folder, game, slot) if path.is_file()]


@dataclass
class ApprovalResult:
    folder: Path
    slot: int
    game: int
    cleared: list[Path]
    approval: Path
    backup: vv_save_backup.BackupResult
    words: list = field(default_factory=list)   # WordFix: old like / dislike words put right now


def _refuse_if_running(folder: Path, processes: vv_save_backup.ProcessController) -> None:
    exe = vv_save_backup.game_exe_name(folder)
    try:
        running = processes.find(exe)
    except (OSError, vv_save_backup.BackupError) as exc:
        raise LogToolError(
            f"Could not check whether {exe} is running, so nothing was changed ({exc})."
        ) from exc
    if running:
        raise GameRunning(
            f"{exe} is running. Close the game first (quit it normally from its "
            "menu); Repair Logs never pauses or closes a game. Nothing was changed."
        )


def approve_repair(
    folder: Path,
    game: int,
    slot: int,
    processes: vv_save_backup.ProcessController | None = None,
    now: datetime | None = None,
) -> ApprovalResult:
    """Approve the game repairing the slot's village the next time it is played.

    Refused (nothing changed) while the game is running.  The save folder is
    backed up first; then only the markers in REARM_MARKERS are removed, and
    the approval file is written (atomically: a temporary file moved into
    place).
    """
    folder = Path(folder)
    targets = marker_paths(folder, game, slot)
    approval = approval_path(folder, game, slot)
    controller = processes if processes is not None else vv_save_backup.WindowsProcesses()
    _refuse_if_running(folder, controller)
    try:
        backup = vv_save_backup.copy_save_folder(folder, now or datetime.now(), suffix=BACKUP_LABEL)
    except vv_save_backup.BackupError as exc:
        raise LogToolError(f"The backup failed, so nothing was changed. {exc}") from exc
    # The backup took a moment; the game may have been started meanwhile.
    _refuse_if_running(folder, controller)
    cleared: list[Path] = []
    for _marker, path in targets:
        if not path.is_file():
            continue
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise LogToolError(
                f"{path.name} could not be cleared ({exc}). "
                f"{len(cleared)} marker(s) were cleared before it and nothing was "
                f"approved; the backup is in {backup.backup_folder}."
            ) from exc
        cleared.append(path)
    left = [path for _marker, path in targets if path.exists()]
    if left:
        raise LogToolError(f"{left[0].name} is still there after clearing it. Nothing was approved.")
    temporary = approval.with_name(approval.name + ".tmp")
    try:
        approval.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_bytes(approval_bytes(game, slot))
        os.replace(temporary, approval)
    except OSError as exc:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise LogToolError(
            f"The approval could not be written ({exc}). The game will not repair "
            f"anything; the backup is in {backup.backup_folder}."
        ) from exc
    words: list[WordFix] = []
    if game in load_checker().WORD_FIXES:
        try:
            village = load_checker().births_log(folder, game, slot)[0].village
        except Exception:                       # the header is only the Repairs log's label
            village = None
        words = fix_log_words(folder, game)
        note_word_repair(folder, game, village, words, now)
    return ApprovalResult(folder, slot, game, cleared, approval, backup, words)


# ---------------------------------------------------------------------------
# Repair Logs: the old like / dislike words (v1.35.61)
# ---------------------------------------------------------------------------

WORD_BACKUP_SUFFIX = ".before-v1.35.61-repair"


@dataclass
class WordFix:
    name: str            # the log file, inside the save folder
    count: int           # words put right
    backup: str          # the backup's file name


def _word_backup(path: Path) -> Path:
    for k in range(1, 1000):
        candidate = path.with_name(path.name + WORD_BACKUP_SUFFIX + ("" if k == 1 else f"-{k}"))
        if not candidate.exists():
            return candidate
    raise LogToolError(f"{path.name} has too many backups already; nothing was changed in it.")


def fix_log_words(folder: Path, game: int) -> list[WordFix]:
    """Put the game's own like and dislike words into every log an older patcher wrote with the
    wrong list (scripts/vvfp_consistency_check.py old_words), with the game closed.

    Each file is copied beside itself first (".before-v1.35.61-repair", never replacing one),
    rewritten through a temporary file, and its boundary recorded as 0 in the game's Log Words
    file, so the same words are never translated twice."""
    checker = load_checker()
    folder = Path(folder)
    done: list[WordFix] = []
    dat = folder / checker.LOG_WORDS.format(game=game)
    for f in checker.old_words(folder, game):
        data = f.path.read_bytes()
        out, at = [], 0
        for start, end, _old, new in f.fixes:
            out.append(data[at:start])
            out.append(new.encode("latin-1"))
            at = end
        out.append(data[at:])
        backup = _word_backup(f.path)
        temporary = f.path.with_name(f.path.name + ".tmp")
        try:
            with open(f.path, "rb") as source, open(backup, "xb") as copy:
                copy.write(source.read())
            temporary.write_bytes(b"".join(out))
            os.replace(temporary, f.path)
            dat.parent.mkdir(parents=True, exist_ok=True)
            with open(dat, "ab") as boundaries:
                boundaries.write(f"0\t{f.name}\r\n".encode("utf-8"))
        except OSError as exc:
            try:
                temporary.unlink()
            except OSError:
                pass
            raise LogToolError(
                f"{f.path.name} could not be corrected ({exc}). "
                f"{len(done)} log file(s) were corrected before it."
            ) from exc
        done.append(WordFix(f.name, len(f.fixes), backup.name))
    return done


def note_word_repair(folder: Path, game: int, village: str | None, fixes: list[WordFix],
                     now: datetime | None = None) -> None:
    """One "Repair <n>" record in the Repairs log (native/shared/repairs_log.h's shape)."""
    if not fixes:
        return
    logs = Path(folder) / "Virtual Villagers Fun Patcher Logs" / "Repairs"
    logs.mkdir(parents=True, exist_ok=True)
    number = 1
    while (logs / f"Virtual Villagers {game} Repairs Log {number + 1}.txt").exists():
        number += 1
    path = logs / f"Virtual Villagers {game} Repairs Log {number}.txt"
    existing = path.read_bytes().decode("latin-1") if path.exists() else ""
    repairs = sum(line.startswith("Repair ") for line in existing.splitlines())
    if repairs >= 256 or len(existing) >= 4 * 1024 * 1024:
        path = logs / f"Virtual Villagers {game} Repairs Log {number + 1}.txt"
        existing, repairs = "", 0
    header = village or "Village: (all villages in this save folder)"
    last = [line for line in existing.splitlines() if line.startswith("Village:")]
    when = (now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    text = "" if last and last[-1].rstrip() == header else header + "\r\n"
    text += f"Repair {repairs + 1}\r\n  Date: {when}\r\n"
    text += "  Checked: the like and dislike words in the logs, against the game's own list\r\n"
    for fix in fixes:
        text += f"  Corrected: {fix.name} -- {fix.count} word(s)\r\n"
    text += "  Backup: " + ", ".join(fix.backup for fix in fixes) + "\r\n\r\n"
    with open(path, "ab") as log:
        log.write(text.encode("latin-1", "replace"))
