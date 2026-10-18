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
import re
import struct
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import vv_save_backup
import vv_save_layout as layout
from transparency import PATCHER_VERSION

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
    reconciliation: object | None = None        # src/vv_reconcile.py Reconciliation (the window exports it)

    @property
    def wrong(self) -> int:
        return self.counts.get("WRONG", 0)

    @property
    def asked(self) -> int:
        """Contradictions only the player can settle (the read-only reconciliation, src/vv_reconcile.py)."""
        return self.counts.get("ASK", 0)

    @property
    def summary(self) -> str:
        parts = ", ".join(f"{self.counts.get(v, 0)} {v}" for v in ("OK", "WRONG", "ASK", "NOTE", "UNCHECKED"))
        verdict = (
            "nothing is confirmed wrong"
            if not self.wrong
            else f"{self.wrong} confirmed wrong"
        )
        if self.asked:
            verdict += f"; {self.asked} contradiction(s) only you can settle"
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
        rule, wrong = vv_last_names.wrong_last_names_explained(Path(folder), game, slot)
    except (vv_last_names.LastNamesError, vv_genealogy.GenealogyError, OSError, ValueError) as exc:
        report.add(f"{LOGS} (last names)", "UNCHECKED", f"could not be read ({exc})")
    else:
        if wrong:
            names = ", ".join(vv_last_names.wrong_last_name_text(v, should, used, rule, either)
                              for v, _now, should, used, either in wrong[:12])
            more = f" and {len(wrong) - 12} more" if len(wrong) > 12 else ""
            report.add(f"{LOGS} (last names)", "NOTE",
                       f"{len(wrong)} last name(s) are not what \"{vv_last_names.INHERIT[rule]}\" gives: "
                       f"{names}{more}. Repair Saves & Logs, Give villagers last names, puts them right.")
    # Villagers with no last name in a village that uses last names (the owner, v1.35.66).
    try:
        missing = vv_last_names.missing_last_names(Path(folder), game, slot)
    except (vv_last_names.LastNamesError, vv_genealogy.GenealogyError, OSError, ValueError, struct.error) as exc:
        report.add(f"{LOGS} (missing last names)", "UNCHECKED", f"could not be read ({exc})")
    else:
        if missing:
            report.add(f"{LOGS} (missing last names)", "NOTE", vv_last_names.missing_note(game, missing))
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
    # Skill values no game can hold (the owner, v1.35.70: "reset obviously-corrupted skill values";
    # src/vv_corrupt_skills.py): NaN, infinite, below 0 or above 100.
    import vv_corrupt_skills
    try:
        corrupt = vv_corrupt_skills.survey(Path(folder), game, slot)
    except (vv_last_names.LastNamesError, OSError, ValueError, struct.error) as exc:
        report.add("Save (skills)", "UNCHECKED", f"could not be read ({exc})")
    else:
        if corrupt:
            report.add("Save (skills)", "NOTE", vv_corrupt_skills.note(game, corrupt))
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
    # The always-on read-only reconciliation of records, logs and files (src/vv_reconcile.py; the owner,
    # 2026-10-11: "MAKE SURE ABSOLUTELY NOTHING IS LOST. IF THERE ARE CONTRADICTIONS ASK THE PLAYER"):
    # every villager followed through every source; each contradiction an ASK line, numbered.
    import vv_reconcile
    label = f"{LOGS}\\Save {slot} (read-only reconciliation of records, logs and files)"
    reconciled = None
    try:
        reconciled = vv_reconcile.reconcile(Path(folder), game, slot)
    except (vv_reconcile.ReconcileError, OSError, ValueError, struct.error) as exc:
        report.add(label, "UNCHECKED", f"the reconciliation could not run ({exc})")
    else:
        for verdict, text in reconciled.lines():
            report.add(label, verdict, text)
    for kind in kinds:
        # "sex" and "born_arrived" the checker itself reports (the latter as WRONG); the reconciliation's
        # questions are listed above.
        if kind.id in ("sex", "born_arrived", "contradictions", "reconcile") or not (kind.decided or kind.asked):
            continue
        asked = f", and {kind.asked} question(s) it asks you" if kind.asked else ""
        report.add(f"{LOGS} ({kind.label})", "NOTE",
                   f"{kind.decided} line(s) the save, the patcher's files or the logs settle{asked}; "
                   "Repair Saves & Logs can add them")
    return CheckResult(Path(folder), slot, game, report.render(), report.counts(), reconciled)


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
    # The save's own folder, or the older layout ("Cross-Check" in older builds): src/vv_save_layout.py
    return layout.route(folder, APPROVAL.format(game=game, slot=slot))


def approval_bytes(game: int, slot: int) -> bytes:
    return struct.pack("<4I", APPROVAL_MAGIC, APPROVAL_VERSION, game, slot)


def marker_paths(folder: Path, game: int, slot: int) -> list[tuple[Marker, Path]]:
    """Each marker of ``game`` for ``slot`` and where it would be (present or not)."""
    if game not in (1, 2, 3, 4, 5) or slot not in (1, 2, 3, 4, 5):
        raise LogToolError(f"There is no game {game} save slot {slot}.")
    return [
        (marker, layout.route(folder, marker.path.format(game=game, slot=slot)))
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
    newer build both left one, or in both the older layout and the save's own folder
    (src/vv_save_layout.py) -- the game reads whichever was written last, so clearing only one of
    them would leave the other to stop the check -- else where it would be."""
    out = []
    for marker, path in marker_paths(folder, game, slot):
        places = layout.both_places(folder, marker.path.format(game=game, slot=slot))
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
    answered: list = field(default_factory=list)  # the reconciliation's questions the player answered
    renamed: dict = field(default_factory=dict)  # (name, head, body) -> the name an answer gave back


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
        for other in layout.both_places(folder, APPROVAL.format(game=game, slot=slot)):
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
        note_word_repair(folder, game, village, words, now, slot=slot)
    if kinds is None:
        kinds = additions.plan(folder, game, slot)
    added = additions.apply(folder, kinds, chosen, answers or {})
    # "Retroactively edit records?" No: the log stays as it is and the verdict is remembered for the
    # readers (src/vv_log_decisions.py).
    kept = additions.resolve_decisions(kinds, chosen, answers or {})
    if kept:
        import vv_log_decisions
        vv_log_decisions.record(folder, game, slot, kept, now)
    # A contradiction the player chose to leave in the past records (or said is none) is remembered,
    # so it is not asked about again (src/vv_log_contradictions.py remember).
    if "contradictions" in chosen:
        import vv_log_contradictions
        vv_log_contradictions.remember(folder, game, slot, kinds, answers or {})
    # The read-only reconciliation's questions (src/vv_reconcile.py): every answer is remembered and
    # listed in the Repairs log; "Don't know" changes nothing and is asked again.  Only two kinds of
    # answer change anything: "<the record's name> is right (give the name back)" -- that villager gets
    # the name back everywhere (src/vv_last_names.py renames: the save, the logs, the patcher's files, a
    # backup first) -- and a pending custom title's "Give it to <villager>" / "Remove the title"
    # (vv_reconcile.settle_titles).  Nothing else is ever changed on a contradiction without the
    # player's word.
    answered: list[str] = []
    renamed: dict = {}
    if any(getattr(k, "id", None) == "reconcile" for k in kinds):     # asked whatever is ticked
        import vv_reconcile
        # The names are given back BEFORE any answer is kept (vv_reconcile.remember): a failed rename
        # keeps no answer, so every question is asked again and can be retried.
        # A pending custom title the player gave to a villager or removed (v1.35.71) is carried out in the
        # Custom Titles file first, checked again against the file and the save as they are now.
        answered, renamed = vv_reconcile.remember(
            folder, game, slot, kinds, answers or {}, now,
            give_back=lambda wanted: vv_reconcile.give_names_back(folder, game, slot, wanted, controller, now),
            settle=lambda actions: vv_reconcile.settle_titles(folder, game, slot, actions, controller,
                                                              backup.backup_folder, now))
        if answered:
            note_word_repair(folder, game, village,
                             [WordFix(line, -1, backup.backup_folder.name) for line in answered], now,
                             checked=additions.CHECKED["reconcile"], corrected="Answered", slot=slot)
    for kind in kinds:
        if added.get(kind.id):
            note_word_repair(folder, game, village, added[kind.id], now,
                             checked=additions.CHECKED[kind.id], corrected=additions.ADDED[kind.id],
                             unit="record(s)" if kind.id == "contradictions" else "villager(s)", slot=slot)
    # Nothing is moved or renamed: an older build's folders and files keep their names, and every
    # repair above wrote where its file already was (the owner, 2026-10-09; src/vv_save_layout.py).
    approval = approval_path(folder, game, slot)
    return ApprovalResult(folder, slot, game, cleared, approval if rearm else None, backup, words,
                          added.get("sex", []), added, answered, renamed)


# ---------------------------------------------------------------------------
# A "Likes:" / "Dislikes:" line's value, old and new (v1.35.68)
# ---------------------------------------------------------------------------
# Since v1.35.68 every log lists EVERY filled slot, in slot order, ", " between them ("herbs, crowds"),
# as the game's own Details panel does (the Island Events log's "old -> new" lines already did).
# Records written before that print one word: the first filled slot.  So a one-word value is what a
# full list's FIRST word would have printed, and the two agree.  No word of any game's list holds a comma.

def preference_words(value: str | None) -> tuple[str, ...]:
    """The words of a Likes / Dislikes value, in order; () for none ("(none)", "", missing)."""
    if value is None:
        return ()
    value = value.strip()
    if value in ("", "(none)", "(unknown)"):
        return ()
    return tuple(w.strip() for w in value.split(",") if w.strip())


def preferences_agree(a: str | None, b: str | None) -> bool:
    """Two Likes (or two Dislikes) values are of the same villager: the same words, or one of them a
    single word (an older one-word line, the first filled slot) that is the other's first."""
    wa, wb = preference_words(a), preference_words(b)
    if wa == wb:
        return True
    if len(wa) == 1 and wb and wb[0] == wa[0]:
        return True
    return len(wb) == 1 and bool(wa) and wa[0] == wb[0]


# ---------------------------------------------------------------------------
# Repair Saves & Logs: the old like / dislike words (v1.35.61)
# ---------------------------------------------------------------------------

# Named for the patcher that made the copy (live, v1.35.66: the copies were still labelled
# with v1.35.61, the build that introduced this repair, on every later build).
WORD_BACKUP_SUFFIX = f".before-{PATCHER_VERSION}-repair"


@dataclass
class WordFix:
    name: str            # the log file, inside the save folder
    count: int           # words put right
    backup: str          # the backup's file name


def copy_before_repair(folder: Path, path: Path, suffix: str) -> Path:
    """Where the copy of `path` (in the save folder) kept before a repair goes: "Data\\Copies Made
    Before Repairs", at the file's own place, "<name><suffix>" (the owner, 2026-10-09: no longer
    beside the file; native/shared/save_layout.h vv_layout_copy_path).  A file in a save's own folder
    ("Virtual Villagers Fun Patcher\\Save <S>\\...") has its copy in that save's own "Data\\Copies Made
    Before Repairs", at its place inside "Save <S>", so deleting the save's folder takes it too
    (native/shared/per_save.h)."""
    relative = Path(path).resolve().relative_to(Path(folder).resolve())
    if layout.older_layout(folder, path) is not None:
        root = Path(folder) / relative.parts[0] / relative.parts[1]
        target = root / layout.SAVE_DATA / layout.COPIES / Path(*relative.parts[2:])
    else:
        target = Path(folder) / layout.DATA / layout.COPIES / relative
    return target.with_name(target.name + suffix)


def copy_places(folder: Path, path: Path, suffix: str) -> list[Path]:
    """Every place a copy of `path` kept before a repair may be, for READING (a new copy is always
    made at copy_before_repair's place): that place, and for a file in a save's own folder also the
    older layout's "Data\\Copies Made Before Repairs\\<its older-layout place>", where its copies made
    before Repair Saves & Logs' "Move Files to Save Folders..." stay (src/vv_move_to_save_folders.py)."""
    out = [copy_before_repair(folder, path, suffix)]
    older = layout.older_layout(folder, path)
    if older is not None:
        target = Path(folder) / layout.DATA / layout.COPIES / Path(*older.split("\\"))
        out.append(target.with_name(target.name + suffix))
    return out


def _word_backup(folder: Path, path: Path) -> Path:
    for k in range(1, 1000):
        candidate = copy_before_repair(folder, path, WORD_BACKUP_SUFFIX + ("" if k == 1 else f"-{k}"))
        if not candidate.exists():
            candidate.parent.mkdir(parents=True, exist_ok=True)
            return candidate
    raise LogToolError(f"{path.name} has too many backups already; nothing was changed in it.")


def move_word_boundary(folder: Path, path: Path, game: int, moved) -> None:
    """After a log file was rewritten in place with bytes added or taken (src/vv_log_additions.py),
    its Like and Dislike Words boundary moved with them: `moved(offset)` is where the byte at
    `offset` of the file as it was is now.  In every boundary file that records one (both are read
    and the smaller taken: native/shared/log_words.h), a new last line.  None recorded, or 0, needs
    nothing (the whole file old, or all of it the game's own words).  The log's own boundary file
    (its save's own when the log is in a save's own folder: vv_save_layout.words_file_for) gets the
    new line too, so the smallest boundary read from every file is the moved one."""
    checker = load_checker()
    key = checker.word_key(str(Path(path).relative_to(folder))).lower()
    own = layout.words_file_for(folder, game, key)
    moved_to: int | None = None
    recorded_name: str | None = None
    for dat in layout.words_files(folder, game):
        recorded = None
        for line in dat.read_bytes().decode("utf-8", "replace").splitlines():
            offset, tab, name = line.partition("\t")
            if tab and name.lower() == key:
                try:
                    recorded = (int(offset), name)
                except ValueError:
                    continue
        if recorded is not None and dat == own:
            own = None                           # it keeps its own boundary, moved below if need be
        if recorded is None or recorded[0] <= 0:
            continue
        now = moved(recorded[0])
        if now != recorded[0]:
            with open(dat, "ab") as boundaries:
                boundaries.write(f"{now}\t{recorded[1]}\r\n".encode("utf-8"))
            if moved_to is None or now < moved_to:
                moved_to, recorded_name = now, recorded[1]
    if own is not None and moved_to is not None and own.is_file():
        # Only into a file already there: a caller copies every existing boundary file first to put
        # it back on a failure (src/vv_history_revision.py), and the files that recorded the boundary
        # were moved above, so the smallest boundary is right without a new file.
        with open(own, "ab") as boundaries:
            boundaries.write(f"{moved_to}\t{recorded_name}\r\n".encode("utf-8"))


def new_log_words(folder: Path, path: Path) -> None:
    """A log file this build has just made (a record appended to a save slot's own log that was not
    there yet): every word in it is the game's own, so its boundary is 0 -- recorded, as the game
    records one when it first writes a file (native/shared/log_words.h vv_log_words_appending), for
    the games whose words were ever wrong.  Nothing when a boundary is already recorded."""
    named = re.match(r"^Virtual Villagers (\d) ", Path(path).name)
    checker = load_checker()
    if not named or int(named.group(1)) not in checker.WORD_FIXES:
        return
    game = int(named.group(1))
    key = checker.word_key(str(Path(path).relative_to(folder)))
    if key.lower() in checker.word_boundaries(Path(folder), game):
        return
    dat = layout.words_file_for(folder, game, key)       # the save's own for a log in its own folder
    dat.parent.mkdir(parents=True, exist_ok=True)
    with open(dat, "ab") as boundaries:
        boundaries.write(f"0\t{key}\r\n".encode("utf-8"))


def fix_log_words(folder: Path, game: int) -> list[WordFix]:
    """Put the game's own like and dislike words into every log an older patcher wrote with the
    wrong list (scripts/vvfp_consistency_check.py old_words), with the game closed.

    Each file is copied first (WORD_BACKUP_SUFFIX: ".before-<this patcher's version>-repair", never replacing one, in Data\\Copies Made
    Before Repairs), rewritten through a temporary file, and its boundary recorded as 0 in the
    game's Like and Dislike Words file, so the same words are never translated twice."""
    checker = load_checker()
    folder = Path(folder)
    done: list[WordFix] = []
    # Appended to the new file, or an older build's "Log Words" while only it exists; the boundaries
    # are read from both (scripts/vvfp_consistency_check.py word_boundaries).  A log in a save's own
    # folder has its boundary in that save's own file (vv_save_layout.words_file_for).
    for f in checker.old_words(folder, game):
        dat = layout.words_file_for(folder, game, f.name)
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


def repair_record_start(folder: Path, game: int, header: str, slot: int | None,
                        now: datetime | None = None) -> tuple[Path, str]:
    """Where the next "Repair <n>" record goes and its first lines (the village header when the file's
    last one is another, "Repair <n>", "  Date: ..."), as native/shared/repairs_log.h writes them.

    The file: the slot's own "...Logs\\Save <slot>\\Repairs Made" (made here), or with no slot, the
    shared "Repairs Made" (an older build's "Repairs" while only it exists); its highest-numbered
    file, the next one once that holds 256 records or 4 MiB.  The number: per GAME, after the highest
    printed in ANY of the game's Repairs files (an older build's "Repairs", the shared "Repairs Made",
    every slot's), and after the records already in the file -- in the shared "Repairs Made" with the
    older folder's file of the same number (save_layout.h vv_layout_older_repairs) -- so no number is
    ever used twice."""
    stem = f"Virtual Villagers {game} Repairs Log"
    if slot:
        logs = layout.slot_log_folder(folder, layout.REPAIRS_LOGS, slot)
    else:
        logs = layout.find(folder, f"{layout.LOGS}\\{layout.REPAIRS_LOGS}")    # "Repairs" in older builds
    highest = layout.repairs_highest(folder, game)
    logs.mkdir(parents=True, exist_ok=True)
    number = 1
    while (logs / f"{stem} {number + 1}.txt").exists():
        number += 1
    path = logs / f"{stem} {number}.txt"
    existing = path.read_bytes().decode("latin-1") if path.exists() else ""
    repairs = sum(line.startswith("Repair ") for line in existing.splitlines())
    if repairs >= 256 or len(existing) >= 4 * 1024 * 1024:
        path = logs / f"{stem} {number + 1}.txt"
        existing, repairs = "", 0
    older = 0
    if logs.name == layout.REPAIRS_LOGS and not layout.is_slot_folder(logs):
        old = Path(folder) / layout.LOGS / "Repairs" / path.name
        if old.is_file():
            older = sum(1 for line in old.read_bytes().decode("latin-1").splitlines()
                        if line.startswith("Repair ") and line[7:8].isdigit())
    last = [line for line in existing.splitlines() if line.startswith("Village:")]
    when = (now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    text = "" if last and last[-1].rstrip() == header else header + "\r\n"
    text += f"Repair {max(repairs + older, highest) + 1}\r\n  Date: {when}\r\n"
    return path, text


def note_word_repair(folder: Path, game: int, village: str | None, fixes: list[WordFix],
                     now: datetime | None = None,
                     checked: str = "the like and dislike words in the logs, against the game's own list",
                     corrected: str = "Corrected", unit: str = "villager(s)", slot: int | None = None) -> None:
    """One "Repair <n>" record in the Repairs log (native/shared/repairs_log.h's shape).  Written in
    the village's own save slot's folder, "...Logs\\Save <S>\\Repairs Made" (the slot its header
    names, else `slot`); with no slot known, in the shared "Repairs Made" (an older build's "Repairs"
    while only it exists), as the game writes it.  "Repair <n>" is numbered per GAME: after the
    highest number printed in any of the game's Repairs files -- an older build's "Repairs", the
    shared "Repairs Made" and every slot's -- and, in the shared "Repairs Made", after the older
    folder's file of the same number too (save_layout.h vv_layout_older_repairs: "Repair 1" never
    comes twice)."""
    if not fixes:
        return
    header = village or "Village: (all villages in this save folder)"
    path, text = repair_record_start(folder, game, header, layout.header_slot(village) or slot, now)
    text += f"  Checked: {checked}\r\n"
    for fix in fixes:
        if fix.count < 0:                   # a line that says it all, no count
            text += f"  {corrected}: {fix.name}\r\n"
        else:
            text += f"  {corrected}: {fix.name} -- {fix.count} " + ("word(s)" if corrected == "Corrected" else unit) + "\r\n"
    text += "  Backup: " + ", ".join(dict.fromkeys(fix.backup for fix in fixes)) + "\r\n\r\n"
    with open(path, "ab") as log:
        log.write(text.encode("latin-1", "replace"))
