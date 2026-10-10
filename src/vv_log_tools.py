"""Check Saves & Logs and Repair Saves & Logs: the patcher window's two log tools (all five games).

The owner (2026-10-04): beside Back Up / Restore Saves and Rename Tribe, a
"Check Saves & Logs..." that shows, for one village, whether every log and data file
the patcher keeps agrees with its save, and a "Repair Saves & Logs..." that has the
game itself repair them.  The owner (2026-10-05): no repair prompt during
gameplay -- "Repair Saves & Logs" is the player's own go-ahead, and the game repairs
without asking.

CHECK SAVES & LOGS is the read-only checker scripts/vvfp_consistency_check.py, run
in-process: the same function the command line runs, so the window shows
whatever the checker reports (no list of files is kept here).  It only opens
files for reading, so it may run while the game is running, and it never
writes, moves or creates anything.  The Backups folder is never read.

REPAIR SAVES & LOGS does not repair anything in Python.  The repairs belong to the
game's own cross-check (native/shared/crosscheck_bridge.h,
docs/first-load-cross-check.md), which never shows anything while a village
is being played.  Repair Saves & Logs is the player's approval, given beforehand with
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
import vv_save_layout as layout

DATA = "Virtual Villagers Fun Patcher Data"
LOGS = "Virtual Villagers Fun Patcher Logs"
BACKUP_LABEL = vv_save_backup.BEFORE_REARM
CHECKER = Path(__file__).resolve().parents[1] / "scripts" / "vvfp_consistency_check.py"


class LogToolError(Exception):
    """Nothing was done; the message says why."""


class GameRunning(LogToolError):
    """The game that saves in this folder is running."""


# ---------------------------------------------------------------------------
# Check Saves & Logs
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
    # What older records lack that Repair Saves & Logs can add (src/vv_log_additions.py; the checker
    # itself reports the Sex lines).
    import vv_log_additions as additions
    try:
        kinds = additions.plan(Path(folder), game, slot)
    except OSError as exc:
        kinds = []
        report.add(f"{LOGS} (older records)", "UNCHECKED", f"a log could not be read ({exc.strerror or exc})")
    # Wrong last names (the owner, 2026-10-07): the ones the village's rule does not give.
    import vv_genealogy
    import vv_last_names
    try:
        rule, wrong = vv_last_names.wrong_last_names(Path(folder), game, slot)
    except (vv_last_names.LastNamesError, vv_genealogy.GenealogyError, OSError, ValueError) as exc:
        report.add(f"{LOGS} (last names)", "UNCHECKED", f"could not be read ({exc})")
    else:
        if wrong:
            names = ", ".join(f"{v.name} (should be {should or 'none'})" for v, _now, should in wrong[:12])
            more = f" and {len(wrong) - 12} more" if len(wrong) > 12 else ""
            report.add(f"{LOGS} (last names)", "NOTE",
                       f"{len(wrong)} last name(s) are not what \"{vv_last_names.INHERIT[rule]}\" gives: "
                       f"{names}{more}. Repair Saves & Logs, Give villagers last names, puts them right.")
    # Names the game's Villager Details screen cut short (the owner, 2026-10-07: "Full names will be
    # in the logs"): the full name the logs keep, src/vv_cut_names.py.
    import vv_cut_names
    try:
        cuts, cut_notes = vv_cut_names.find_cut(Path(folder), game, slot)
    except (vv_last_names.LastNamesError, vv_genealogy.GenealogyError, OSError, ValueError, struct.error) as exc:
        report.add(f"{LOGS} (cut names)", "UNCHECKED", f"could not be read ({exc})")
    else:
        if cuts:
            report.add(f"{LOGS} (cut names)", "NOTE",
                       f"{len(cuts)} name(s) the game's Villager Details screen cut short: "
                       f"{vv_cut_names.describe(cuts, '{cut} ({full})')}; "
                       "Repair Saves & Logs restores them.")
        for note in cut_notes:
            report.add(f"{LOGS} (cut names)", "NOTE", note)
    # Records that contradict each other (src/vv_log_contradictions.py): one villager born and
    # arrived or arrived twice, a Death or Repair number used twice -- confirmed wrong, and repaired
    # by Repair Saves & Logs; what no file can prove wrong is a note.
    import vv_log_contradictions
    try:
        contradictions = vv_log_contradictions.find(Path(folder), game, slot)
    except OSError as exc:
        contradictions = []
        report.add(f"{LOGS} (contradictions)", "UNCHECKED", f"a log could not be read ({exc.strerror or exc})")
    for found in contradictions:
        report.add(f"{LOGS} (contradictions)", "WRONG" if found.wrong else "NOTE", found.text)
    for kind in kinds:
        if kind.id in ("sex", "contradictions") or not (kind.decided or kind.asked):
            continue
        asked = f", and {kind.asked} question(s) it asks you" if kind.asked else ""
        report.add(f"{LOGS} ({kind.label})", "NOTE",
                   f"{kind.decided} line(s) the save, the patcher's files or the logs settle{asked}; "
                   "Repair Saves & Logs can add them")
    return CheckResult(Path(folder), slot, game, report.render(), report.counts())


# ---------------------------------------------------------------------------
# Repair Saves & Logs: approve the repair, and re-arm the check
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Marker:
    """One "already checked" marker of the first-load cross-check."""

    what: str                   # what it records, for the confirmation
    games: tuple[int, ...]      # the games that write it
    path: str                   # relative to the save folder; {game} and {slot}
    source: str                 # the native code that writes and reads it
    kind: str                   # its format, for marker_is_valid


# EVERY marker that stops a part of the cross-check from finding anything
# again.  Repair Saves & Logs clears these and nothing else; a new once-per-village
# part of the check adds its marker here.
REARM_MARKERS: tuple[Marker, ...] = (
    Marker(
        "A New Home's parents checked against the Births and Conceptions log",
        (1,),
        DATA + r"\Log Checks\Virtual Villagers {game} Cross-Check - Save {slot}.dat",
        "native/vv1_parentage/vv1_crosscheck.inc (vv1_xc_marker_state)",
        "vv1",
    ),
    Marker(
        "graves already confirmed in the Deaths log",
        (1, 2, 3, 4, 5),
        DATA + r"\Deaths\Virtual Villagers {game} Graves Logged - Save {slot}.dat",
        "native/vvfp_cause_of_death/cod_backfill.inc (logged_bind)",
        "graves",
    ),
    Marker(
        "villagers' Arrived records already backfilled",
        (1, 2, 3, 4, 5),
        DATA + r"\Arrivals\Virtual Villagers {game} Arrivals Recorded - Save {slot}.dat",
        "native/shared/arrival_backfill.h (vv_arrival_marker_present)",
        "arrivals",
    ),
    Marker(
        "villagers' Birth records already backfilled from the save",
        (2, 3, 4, 5),
        DATA + r"\Births\Virtual Villagers {game} Births Recorded - Save {slot}.dat",
        "native/shared/arrival_backfill.h (vv_backfill_marker_present)",
        "births",
    ),
)


# The player's approval for one slot (native/shared/crosscheck_bridge.h reads
# it, uses it once and deletes it; native/shared/save_reset.c deletes it at
# Start Over).
APPROVAL = DATA + r"\Log Checks\Virtual Villagers {game} Repair Approved - Save {slot}.dat"
APPROVAL_MAGIC = 0x31415256          # 'V' 'R' 'A' '1'
APPROVAL_VERSION = 1


def approval_path(folder: Path, game: int, slot: int) -> Path:
    """Where the approval for ``game``'s ``slot`` is (present or not)."""
    if game not in (1, 2, 3, 4, 5) or slot not in (1, 2, 3, 4, 5):
        raise LogToolError(f"There is no game {game} save slot {slot}.")
    return layout.find(folder, APPROVAL.format(game=game, slot=slot))   # "Cross-Check" in older builds


def approval_bytes(game: int, slot: int) -> bytes:
    return struct.pack("<4I", APPROVAL_MAGIC, APPROVAL_VERSION, game, slot)


def marker_paths(folder: Path, game: int, slot: int) -> list[tuple[Marker, Path]]:
    """Each marker of ``game`` for ``slot`` and where it would be (present or not)."""
    if game not in (1, 2, 3, 4, 5) or slot not in (1, 2, 3, 4, 5):
        raise LogToolError(f"There is no game {game} save slot {slot}.")
    return [
        (marker, layout.find(folder, marker.path.format(game=game, slot=slot)))
        for marker in REARM_MARKERS
        if game in marker.games
    ]


def marker_is_valid(marker: Marker, data: bytes, game: int, slot: int) -> bool:
    """True when the game would read ``data`` as this slot's marker (the same
    test as the native code named in ``marker.source``).  Anything else at a
    marker's path does not stop a rescan, and is kept: Repair Saves & Logs removes
    only real markers."""
    checker = load_checker()
    if marker.kind == "vv1":
        return checker.vv1_marker_ok(data, slot)
    if marker.kind == "graves":
        return checker.graves_logged_problem(data, game) is None
    magic = checker.ARRIVALS_MARKER_MAGIC if marker.kind == "arrivals" else checker.BIRTHS_MARKER_MAGIC
    return checker.backfill_marker_ok(data, magic, game, slot)


def marker_places(folder: Path, game: int, slot: int) -> list[tuple[Marker, Path]]:
    """Each marker of ``game`` for ``slot`` at EVERY place it is: under both names when an older and a
    newer build both left one (src/vv_save_layout.py) -- the game reads whichever was written last,
    so clearing only one of them would leave the other to stop the check -- else where it would be."""
    out = []
    for marker, path in marker_paths(folder, game, slot):
        places = layout.places(folder, marker.path.format(game=game, slot=slot))
        out += [(marker, place) for place in places] or [(marker, path)]
    return out


def present_markers(folder: Path, game: int, slot: int) -> list[tuple[Marker, Path]]:
    return [(marker, path) for marker, path in marker_places(folder, game, slot) if path.is_file()]


@dataclass
class ApprovalResult:
    folder: Path
    slot: int
    game: int
    cleared: list[Path]
    approval: Path | None
    backup: vv_save_backup.BackupResult
    words: list = field(default_factory=list)   # WordFix: old like / dislike words put right now
    sexes: list = field(default_factory=list)   # WordFix: Sex lines added to older records now
    added: dict = field(default_factory=dict)   # kind id -> WordFix: every line added to older records now


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
            "menu); Repair Saves & Logs never pauses or closes a game. Nothing was changed."
        )


def approve_repair(
    folder: Path,
    game: int,
    slot: int,
    processes: vv_save_backup.ProcessController | None = None,
    now: datetime | None = None,
    *,
    chosen: set[str] | None = None,
    answers: dict[str, str] | None = None,
    kinds: list | None = None,
    rearm: bool = True,
) -> ApprovalResult:
    """Repair Saves & Logs with the game closed: what the player ticked.

    Refused (nothing changed) while the game is running.  The save folder is
    backed up first.  With `rearm` (the checklist's "the game repairs what is
    confirmed wrong"), only the markers in REARM_MARKERS are removed and the
    approval file is written (atomically: a temporary file moved into place).
    `chosen` names what is added to older records now (src/vv_log_additions.py
    kinds, and "words": the like / dislike words an older patcher wrote with
    the wrong list), with the player's `answers` to its questions; `kinds` is
    the plan the player saw (planned again when not given).  By default: the
    words and the Sex lines the save, the logs or the name lists decide.
    """
    import vv_log_additions as additions

    folder = Path(folder)
    chosen = {"words", "sex"} if chosen is None else set(chosen)
    targets = marker_places(folder, game, slot)        # under both names, both cleared
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
    for marker, path in targets if rearm else ():
        if not path.is_file():
            continue
        try:
            if not marker_is_valid(marker, path.read_bytes(), game, slot):
                continue
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
    left = [path for path in cleared if path.exists()]
    if left:
        raise LogToolError(f"{left[0].name} is still there after clearing it. Nothing was approved.")
    if rearm:
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
        # The game acts on an approval kept under both names under neither (src/vv_save_layout.py,
        # native/shared/crosscheck_bridge.h): this same approval left under the other name by an
        # earlier Repair is cleared, as the game clears one it has used.
        for other in layout.places(folder, APPROVAL.format(game=game, slot=slot)):
            if other != approval:
                try:
                    if other.read_bytes() == approval_bytes(game, slot):
                        other.unlink()
                except OSError:
                    pass
    try:
        village = load_checker().births_log(folder, game, slot)[0].village
    except Exception:                           # the header is only the Repairs log's label
        village = None
    words: list[WordFix] = []
    if "words" in chosen and game in load_checker().WORD_FIXES:
        words = fix_log_words(folder, game)
        note_word_repair(folder, game, village, words, now)
    if kinds is None:
        kinds = additions.plan(folder, game, slot)
    added = additions.apply(folder, kinds, chosen, answers or {}, game)
    for kind in kinds:
        if added.get(kind.id):
            note_word_repair(folder, game, village, added[kind.id], now,
                             checked=additions.CHECKED[kind.id], corrected=additions.ADDED[kind.id],
                             unit="record(s)" if kind.id == "contradictions" else "villager(s)")
    # Nothing is moved or renamed: an older build's folders and files keep their names, and every
    # repair above wrote where its file already was (the owner, 2026-10-09; src/vv_save_layout.py).
    approval = approval_path(folder, game, slot)
    return ApprovalResult(folder, slot, game, cleared, approval if rearm else None, backup, words,
                          added.get("sex", []), added)


# ---------------------------------------------------------------------------
# Repair Saves & Logs: the old like / dislike words (v1.35.61)
# ---------------------------------------------------------------------------

WORD_BACKUP_SUFFIX = ".before-v1.35.61-repair"


@dataclass
class WordFix:
    name: str            # the log file, inside the save folder
    count: int           # words put right
    backup: str          # the backup's file name


def copy_before_repair(folder: Path, path: Path, suffix: str) -> Path:
    """Where the copy of `path` (in the save folder) kept before a repair goes: "Data\\Copies Made
    Before Repairs", at the file's own place, "<name><suffix>" (the owner, 2026-10-09: no longer
    beside the file; native/shared/save_layout.h vv_layout_copy_path)."""
    relative = Path(path).resolve().relative_to(Path(folder).resolve())
    target = Path(folder) / layout.DATA / layout.COPIES / relative
    return target.with_name(target.name + suffix)


def _word_backup(folder: Path, path: Path) -> Path:
    for k in range(1, 1000):
        candidate = copy_before_repair(folder, path, WORD_BACKUP_SUFFIX + ("" if k == 1 else f"-{k}"))
        if not candidate.exists():
            candidate.parent.mkdir(parents=True, exist_ok=True)
            return candidate
    raise LogToolError(f"{path.name} has too many backups already; nothing was changed in it.")


def fix_log_words(folder: Path, game: int) -> list[WordFix]:
    """Put the game's own like and dislike words into every log an older patcher wrote with the
    wrong list (scripts/vvfp_consistency_check.py old_words), with the game closed.

    Each file is copied first (".before-v1.35.61-repair", never replacing one, in Data\\Copies Made
    Before Repairs), rewritten through a temporary file, and its boundary recorded as 0 in the
    game's Like and Dislike Words file, so the same words are never translated twice."""
    checker = load_checker()
    folder = Path(folder)
    done: list[WordFix] = []
    # Appended to the new file, or an older build's "Log Words" while only it exists; the boundaries
    # are read from both (scripts/vvfp_consistency_check.py word_boundaries).
    dat = layout.writable(folder, checker.LOG_WORDS.format(game=game))
    for f in checker.old_words(folder, game):
        data = f.path.read_bytes()
        out, at = [], 0
        for start, end, _old, new in f.fixes:
            out.append(data[at:start])
            out.append(new.encode("latin-1"))
            at = end
        out.append(data[at:])
        backup = _word_backup(folder, f.path)
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
                     now: datetime | None = None,
                     checked: str = "the like and dislike words in the logs, against the game's own list",
                     corrected: str = "Corrected", unit: str = "villager(s)") -> None:
    """One "Repair <n>" record in the Repairs log (native/shared/repairs_log.h's shape).  Written in
    "Repairs Made" (an older build's "Repairs" while only it exists); with both folders there, its
    number continues after the older folder's file of the same number (save_layout.h
    vv_layout_older_repairs: "Repair 1" never comes twice)."""
    if not fixes:
        return
    logs = layout.find(folder, f"{layout.LOGS}\\{layout.REPAIRS_LOGS}")    # "Repairs" in older builds
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
    older = 0
    if logs.name == layout.REPAIRS_LOGS:
        old = Path(folder) / layout.LOGS / "Repairs" / path.name
        if old.is_file():
            older = sum(1 for line in old.read_bytes().decode("latin-1").splitlines()
                        if line.startswith("Repair ") and line[7:8].isdigit())
    header = village or "Village: (all villages in this save folder)"
    last = [line for line in existing.splitlines() if line.startswith("Village:")]
    when = (now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    text = "" if last and last[-1].rstrip() == header else header + "\r\n"
    text += f"Repair {repairs + 1 + older}\r\n  Date: {when}\r\n"
    text += f"  Checked: {checked}\r\n"
    for fix in fixes:
        text += f"  {corrected}: {fix.name} -- {fix.count} " + ("word(s)" if corrected == "Corrected" else unit) + "\r\n"
    text += "  Backup: " + ", ".join(fix.backup for fix in fixes) + "\r\n\r\n"
    with open(path, "ab") as log:
        log.write(text.encode("latin-1", "replace"))
