"""Check Logs and Repair Logs (src/vv_log_tools.py and the patcher window).

Check Logs runs scripts/vvfp_consistency_check.py in-process and must leave
every file exactly as it found it (bytes, size and modification time), never
open anything for writing, and never read the Backups folder.  Repair Logs must
refuse while the game is running (never pausing it), back the folder up first,
clear exactly the cross-check's "already checked" markers for the chosen game
and slot, and write that slot's approval (the game then repairs the village
the next time it is played, without asking) -- nothing else.  Every save
folder is built here from the repository's own fixture saves; no file outside
the repository is read.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_log_tools as tools  # noqa: E402
import vv_save_backup as backup  # noqa: E402
import vv_tribe_rename as rename  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "rename_tribe"
NOW = datetime(2026, 10, 4, 15, 30, 0)
DATA = "Virtual Villagers Fun Patcher Data"
LOGS = "Virtual Villagers Fun Patcher Logs"

# (fixture tag, game number, folder suffix): every game and the 256 builds.
CASES = [
    ("huttest", 1, "Modded"),
    ("huttest", 2, "Modded"),
    ("huttest", 3, "Modded"),
    ("huttest", 4, "Modded"),
    ("huttest", 5, "Modded"),
    ("256", 3, "Modded 256"),
    ("256", 4, "Modded 256"),
    ("256", 5, "Modded 256"),
]


def fixture(name: str) -> bytes:
    return gzip.decompress((FIXTURES / f"{name}.ldw.gz").read_bytes())


def markers_of(game: int, slot: int) -> list[str]:
    names = [
        f"{DATA}/Deaths/Virtual Villagers {game} Graves Logged - Save {slot}.dat",
        f"{DATA}/Arrivals/Virtual Villagers {game} Arrivals Recorded - Save {slot}.dat",
    ]
    if game == 1:
        names.append(f"{DATA}/Cross-Check/Virtual Villagers 1 Cross-Check - Save {slot}.dat")
    else:
        names.append(f"{DATA}/Births/Virtual Villagers {game} Births Recorded - Save {slot}.dat")
    return names


class FakeProcesses:
    def __init__(self, pids=(), error=None, start_after=None):
        self.pids = list(pids)
        self.error = error
        self.calls = 0
        self.start_after = start_after

    def find(self, exe_name):
        self.calls += 1
        if self.error is not None:
            raise self.error
        if self.start_after is not None and self.calls > self.start_after:
            return [4242]
        return list(self.pids)

    def suspend(self, pid, exe_name):  # pragma: no cover - never used
        raise AssertionError("Repair Logs must never pause a game")

    def resume(self, handle):  # pragma: no cover - never used
        raise AssertionError("Repair Logs must never pause a game")


class FolderTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.documents = Path(self._tmp.name) / "Documents"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def make_folder(self, tag: str, number: int, suffix: str) -> Path:
        game = rename.GAMES[number - 1]
        folder = self.documents / "LDW" / f"{game.title} - {suffix}"
        folder.mkdir(parents=True)
        game.save_path(folder, 1).write_bytes(fixture(f"vv{number}-{tag}-1"))
        game.index_path(folder).write_bytes(fixture(f"vv{number}-{tag}-0"))
        # Every marker of both slots and of a neighbouring game (renamed
        # executables of two games may share a folder), logs, data files and
        # look-alikes, so "exactly the markers" is tested against neighbours.
        for slot in (1, 2):
            for other in {number, 2 if number == 1 else 1}:
                for name in markers_of(other, slot):
                    self.write(folder, name, f"marker {other} {slot}".encode())
        self.write(folder, f"{DATA}/Cross-Check/Virtual Villagers 1 Cross-Check - Save 1.dat.unreadable-1", b"x")
        self.write(folder, f"{DATA}/Deaths/Virtual Villagers {number} Graves Logged - Save 1.dat.tmp", b"t")
        self.write(folder, f"{DATA}/Graves/Virtual Villagers {number} Graves - Save 1.dat", b"VCD1")
        self.write(folder, f"{DATA}/Village Masks/Village Masks - Save 1.dat", b"masks")
        self.write(folder, f"{DATA}/Parentage/Virtual Villagers 1 Parentage Records - Save 1.dat", b"p")
        self.write(folder, f"{LOGS}/Deaths/Virtual Villagers {number} Deaths Log 1.txt",
                   b"Village: Hut (Save 1)\n\n")
        self.write(folder, f"{LOGS}/Births and Conceptions/Virtual Villagers {number} Births and Conceptions Log 1.txt",
                   b"Village: Hut (Save 1)\n\n")
        self.write(folder, f"{LOGS}/Repairs/Virtual Villagers 1 Repairs Log 1.txt", b"Village: Hut (Save 1)\n")
        self.write(folder, "Backups/Backup 2026-10-01 10-00-00/old.txt", b"old backup")
        return folder

    @staticmethod
    def write(folder: Path, relative: str, data: bytes) -> None:
        path = folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    @staticmethod
    def state(folder: Path) -> dict[str, tuple[int, int, str]]:
        """Every file and folder: size, modification time, SHA-256."""
        out = {}
        for path in sorted(folder.rglob("*")):
            stat = path.stat()
            digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "dir"
            out[path.relative_to(folder).as_posix()] = (stat.st_size if path.is_file() else 0,
                                                       stat.st_mtime_ns, digest)
        return out


# ---------------------------------------------------------------------------
# Check Logs
# ---------------------------------------------------------------------------


class CheckLogsTests(FolderTest):
    def test_every_game_and_variant_is_checked_and_nothing_changes(self) -> None:
        for tag, number, suffix in CASES:
            with self.subTest(game=number, variant=suffix):
                folder = self.make_folder(tag, number, suffix)
                before = self.state(folder)
                result = tools.check_logs(folder, 1, number)
                self.assertEqual(self.state(folder), before)
                self.assertTrue(result.summary.startswith("Save 1: "))
                self.assertIn("== ", result.text)
                self.assertEqual(sum(result.counts.values()),
                                 sum(1 for line in result.text.splitlines() if line.startswith("  ")))

    def test_nothing_is_opened_for_writing_and_the_backups_are_never_read(self) -> None:
        folder = self.make_folder("huttest", 1, "Modded")
        opened: list[tuple[str, str]] = []
        real_open = io.open

        def recording_open(file, mode="r", *args, **kwargs):
            opened.append((str(file), mode))
            return real_open(file, mode, *args, **kwargs)

        with mock.patch("io.open", recording_open):
            tools.check_logs(folder, 1, 1)
        self.assertTrue(opened)
        for name, mode in opened:
            self.assertFalse(set(mode) & set("wax+"), (name, mode))
            self.assertNotIn("\\Backups\\", name.replace("/", "\\"))

    def test_the_report_is_the_checkers_own(self) -> None:
        folder = self.make_folder("huttest", 3, "Modded")
        checker = tools.load_checker()
        report = checker.check(folder, 1, 3)
        result = tools.check_logs(folder, 1, 3)
        self.assertEqual(result.text, report.render())
        self.assertEqual(result.counts, report.counts())
        self.assertEqual(set(result.counts), {"OK", "WRONG", "NOTE", "UNCHECKED"})

    def test_a_wrong_line_is_counted_and_summarised(self) -> None:
        checker = tools.load_checker()
        rep = checker.Report()
        rep.add("a", "OK", "fine")
        rep.add("a", "WRONG", "bad (repairable)")
        rep.add("b", "NOTE", "hm")
        with mock.patch.object(checker, "check", return_value=rep):
            folder = self.make_folder("huttest", 2, "Modded")
            result = tools.check_logs(folder, 1, 2)
        self.assertEqual(result.wrong, 1)
        self.assertEqual(result.summary, "Save 1: 1 confirmed wrong (1 OK, 1 WRONG, 1 NOTE, 0 UNCHECKED).")

    def test_an_empty_slot_is_refused_with_a_message(self) -> None:
        folder = self.make_folder("huttest", 5, "Modded")
        with self.assertRaises(tools.LogToolError) as caught:
            tools.check_logs(folder, 2, 5)
        self.assertIn("Save 2 has no tribe", str(caught.exception))
        with self.assertRaises(tools.LogToolError):
            tools.check_logs(folder, 6, 5)

    def test_a_file_that_cannot_be_read_is_reported_not_raised(self) -> None:
        folder = self.make_folder("huttest", 4, "Modded")
        checker = tools.load_checker()
        with mock.patch.object(checker, "check", side_effect=PermissionError("in use")):
            with self.assertRaises(tools.LogToolError) as caught:
                tools.check_logs(folder, 1, 4)
        self.assertIn("Nothing was changed", str(caught.exception))

    def test_checking_works_while_the_game_runs(self) -> None:
        # Check Logs never asks whether the game is running: it only reads.
        folder = self.make_folder("huttest", 1, "Modded")
        with mock.patch.object(backup, "WindowsProcesses", side_effect=AssertionError("asked")):
            tools.check_logs(folder, 1, 1)


class CheckerRefactorTests(FolderTest):
    SCRIPT = ROOT / "scripts" / "vvfp_consistency_check.py"

    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(self.SCRIPT), *args],
                              capture_output=True, text=True, timeout=120)

    def test_the_cli_reports_a_missing_slot_and_exits_1(self) -> None:
        folder = self.make_folder("huttest", 3, "Modded")
        done = self.run_cli(str(folder), "4")
        self.assertEqual(done.returncode, 1)
        self.assertEqual(done.stdout, "")
        self.assertIn("no save for slot 4 in", done.stderr)
        self.assertNotIn("Traceback", done.stderr)

    def test_the_cli_prints_the_report_and_its_count(self) -> None:
        folder = self.make_folder("huttest", 3, "Modded")
        before = self.state(folder)
        done = self.run_cli(str(folder), "1")
        report = tools.load_checker().check(folder, 1)
        # The HutTest village has three villagers born before its Births log
        # (v1.35.58 backfills their Birth records): exit 1, "confirmed wrong".
        self.assertEqual(done.returncode, 1 if report.wrong else 0, done.stderr)
        self.assertEqual(done.stdout, report.render() + f"\n\n{report.wrong} confirmed wrong\n")
        self.assertEqual(self.state(folder), before)

    def test_check_raises_check_error_not_system_exit(self) -> None:
        checker = tools.load_checker()
        folder = self.make_folder("huttest", 1, "Modded")
        with self.assertRaises(checker.CheckError):
            checker.check(folder, 3)
        self.assertFalse(issubclass(checker.CheckError, SystemExit))


# ---------------------------------------------------------------------------
# Repair Logs
# ---------------------------------------------------------------------------


def approval_of(number: int, slot: int) -> str:
    return f"{DATA}/Cross-Check/Virtual Villagers {number} Repair Approved - Save {slot}.dat"


def approval_pending(folder: Path, number: int, slot: int) -> bool:
    """Whether the slot's approval is there, exactly as the game reads it."""
    path = folder / approval_of(number, slot)
    return path.is_file() and path.read_bytes() == tools.approval_bytes(number, slot)


class ApprovalTests(FolderTest):
    def test_exactly_the_slots_markers_are_cleared_and_its_approval_written_in_every_game(self) -> None:
        for tag, number, suffix in CASES:
            with self.subTest(game=number, variant=suffix):
                folder = self.make_folder(tag, number, suffix)
                before = self.state(folder)
                self.assertFalse(approval_pending(folder, number, 1))
                result = tools.approve_repair(folder, number, 1, FakeProcesses(), NOW)
                expected = set(markers_of(number, 1))
                self.assertEqual({p.relative_to(folder).as_posix() for p in result.cleared}, expected)
                after = self.state(folder)
                for name in expected:
                    self.assertNotIn(name, after)
                approval = approval_of(number, 1)
                self.assertEqual(result.approval.relative_to(folder).as_posix(), approval)
                self.assertEqual(
                    (folder / approval).read_bytes(),
                    b"VRA1" + (1).to_bytes(4, "little") + number.to_bytes(4, "little") + (1).to_bytes(4, "little"),
                )
                self.assertTrue(approval_pending(folder, number, 1))
                self.assertFalse(approval_pending(folder, number, 2))
                new_backup = result.backup.backup_folder.relative_to(folder).as_posix()
                outside_new_backup = {
                    k: v for k, v in after.items()
                    if v[2] != "dir" and not k.startswith(new_backup) and k != approval
                }
                # Files only: clearing a marker updates its folder's own time.
                self.assertEqual(
                    outside_new_backup,
                    {k: v for k, v in before.items() if k not in expected and v[2] != "dir"},
                )

    def test_the_marker_list_is_the_native_codes_own(self) -> None:
        reset = (ROOT / "native" / "shared" / "save_reset.c").read_text(encoding="utf-8")
        self.assertIn(r'"%s\\Virtual Villagers Fun Patcher Data\\Deaths\\Virtual Villagers " n " Graves Logged - Save %d.dat"', reset)
        self.assertIn(r'"%s\\Virtual Villagers Fun Patcher Data\\Arrivals\\Virtual Villagers " n " Arrivals Recorded - Save %d.dat"', reset)
        xc = (ROOT / "native" / "vv1_parentage" / "vv1_crosscheck.inc").read_text(encoding="utf-8")
        self.assertIn('"Virtual Villagers Fun Patcher Data", "Cross-Check"', xc)
        self.assertIn(r'"\\Virtual Villagers 1 Cross-Check - Save %d.dat", slot', xc)
        self.assertIn(r'"%s\\Virtual Villagers Fun Patcher Data\\Births\\Virtual Villagers " n " Births Recorded - Save %d.dat"', reset)
        self.assertEqual(len(tools.REARM_MARKERS), 4)
        for number in range(1, 6):
            self.assertEqual(
                sorted(p.relative_to(Path("F")).as_posix().replace("\\", "/")
                       for _m, p in tools.marker_paths(Path("F"), number, 3)),
                sorted(markers_of(number, 3)),
            )

    def test_the_folder_is_backed_up_first_with_the_markers_in_it(self) -> None:
        folder = self.make_folder("huttest", 1, "Modded")
        result = tools.approve_repair(folder, 1, 1, FakeProcesses(), NOW)
        copy = result.backup.backup_folder
        self.assertEqual(copy.name, "Backup 2026-10-04 15-30-00 (before repair re-arm)")
        for name in markers_of(1, 1):
            self.assertEqual((copy / name).read_bytes(), b"marker 1 1")
        listed = backup.list_backups(folder)
        self.assertEqual(listed[0].path, copy)
        self.assertTrue(listed[0].before_rearm)
        self.assertEqual(listed[0].label, "2026-10-04 15:30:00 (before repair re-arm)")

    def test_a_failed_backup_clears_nothing(self) -> None:
        folder = self.make_folder("huttest", 2, "Modded")
        before = self.state(folder)
        with mock.patch.object(backup, "copy_save_folder", side_effect=backup.BackupError("disk full")):
            with self.assertRaises(tools.LogToolError):
                tools.approve_repair(folder, 2, 1, FakeProcesses(), NOW)
        self.assertEqual(self.state(folder), before)
        self.assertFalse(approval_pending(folder, 2, 1))

    def test_an_approval_that_cannot_be_written_leaves_none_behind(self) -> None:
        folder = self.make_folder("huttest", 3, "Modded")
        real = Path.write_bytes

        def failing(path, data):
            if path.name.endswith(".tmp"):
                real(path, data[:3])
                raise OSError("disk full")
            return real(path, data)

        with mock.patch.object(Path, "write_bytes", failing):
            with self.assertRaises(tools.LogToolError) as caught:
                tools.approve_repair(folder, 3, 1, FakeProcesses(), NOW)
        self.assertIn("will not repair anything", str(caught.exception))
        self.assertFalse((folder / approval_of(3, 1)).exists())
        self.assertFalse((folder / (approval_of(3, 1) + ".tmp")).exists())
        self.assertFalse(approval_pending(folder, 3, 1))

    def test_check_logs_shows_an_approval_not_yet_used(self) -> None:
        folder = self.make_folder("huttest", 2, "Modded")
        self.assertNotIn("Repair Logs approved", tools.check_logs(folder, 1, 2).text)
        tools.approve_repair(folder, 2, 1, FakeProcesses(), NOW)
        self.assertIn("NOTE", tools.check_logs(folder, 1, 2).text)
        self.assertIn("Repair Logs approved repairing this village: the game repairs it, without asking",
                      tools.check_logs(folder, 1, 2).text)

    def test_approving_again_is_one_approval(self) -> None:
        folder = self.make_folder("huttest", 4, "Modded")
        tools.approve_repair(folder, 4, 2, FakeProcesses(), NOW)
        tools.approve_repair(folder, 4, 2, FakeProcesses(), NOW)
        cross = folder / DATA / "Cross-Check"
        self.assertEqual(sorted(p.name for p in cross.iterdir() if "Approved" in p.name),
                         ["Virtual Villagers 4 Repair Approved - Save 2.dat"])

    def test_the_approval_is_the_games_own_format_and_start_over_deletes_it(self) -> None:
        bridge = (ROOT / "native" / "shared" / "crosscheck_bridge.h").read_text(encoding="utf-8")
        self.assertIn("#define VVFP_XC_APPROVAL_MAGIC   0x31415256u", bridge)
        self.assertIn("#define VVFP_XC_APPROVAL_VERSION 1u", bridge)
        self.assertEqual(tools.APPROVAL_MAGIC, 0x31415256)
        self.assertIn(r'L"%ls\\Virtual Villagers Fun Patcher Data\\Cross-Check\\Virtual Villagers %d Repair Approved - Save %d.dat"',
                      bridge)
        reset = (ROOT / "native" / "shared" / "save_reset.c").read_text(encoding="utf-8")
        self.assertIn(r'"%s\\Virtual Villagers Fun Patcher Data\\Cross-Check\\Virtual Villagers " n " Repair Approved - Save %d.dat"',
                      reset)
        table = reset.split("static const char *const SIDECAR_FORMATS", 1)[1].split("};", 1)[0]
        for number in range(1, 6):
            self.assertIn(f'APPROVAL_FORMAT("{number}")', table)

    def test_the_backup_is_made_before_any_marker_is_cleared(self) -> None:
        folder = self.make_folder("huttest", 4, "Modded")
        seen = []
        real = backup.copy_save_folder

        def copying(*args, **kwargs):
            seen.append(all((folder / n).is_file() for n in markers_of(4, 1)))
            return real(*args, **kwargs)

        with mock.patch.object(backup, "copy_save_folder", copying):
            tools.approve_repair(folder, 4, 1, FakeProcesses(), NOW)
        self.assertEqual(seen, [True])

    def test_a_running_game_is_refused_and_nothing_changes(self) -> None:
        folder = self.make_folder("huttest", 5, "Modded")
        before = self.state(folder)
        with self.assertRaises(tools.GameRunning) as caught:
            tools.approve_repair(folder, 5, 1, FakeProcesses(pids=[7]), NOW)
        self.assertIn("never pauses or closes", str(caught.exception))
        self.assertEqual(self.state(folder), before)
        self.assertFalse(approval_pending(folder, 5, 1))

    def test_the_game_checked_is_the_one_that_saves_here(self) -> None:
        folder = self.make_folder("huttest", 3, "Modded 256")
        asked = []

        class Recording(FakeProcesses):
            def find(self, exe_name):
                asked.append(exe_name)
                return []

        tools.approve_repair(folder, 3, 1, Recording(), NOW)
        self.assertEqual(set(asked), {"Virtual Villagers - The Secret City - Modded 256.exe"})

    def test_when_the_process_list_fails_nothing_changes(self) -> None:
        folder = self.make_folder("huttest", 1, "Modded")
        before = self.state(folder)
        with self.assertRaises(tools.LogToolError):
            tools.approve_repair(folder, 1, 1, FakeProcesses(error=OSError("denied")), NOW)
        self.assertEqual(self.state(folder), before)

    def test_a_game_started_during_the_backup_stops_the_clearing(self) -> None:
        folder = self.make_folder("huttest", 2, "Modded")
        with self.assertRaises(tools.GameRunning):
            tools.approve_repair(folder, 2, 1, FakeProcesses(start_after=1), NOW)
        for name in markers_of(2, 1):
            self.assertTrue((folder / name).is_file(), name)
        self.assertFalse(approval_pending(folder, 2, 1))

    def test_no_markers_is_not_an_error(self) -> None:
        folder = self.make_folder("huttest", 3, "Modded")
        for name in markers_of(3, 1):
            (folder / name).unlink()
        result = tools.approve_repair(folder, 3, 1, FakeProcesses(), NOW)
        self.assertEqual(result.cleared, [])
        self.assertTrue(approval_pending(folder, 3, 1))

    def test_the_module_never_pauses_closes_or_repairs(self) -> None:
        # It writes one file, the approval (through its own temporary file),
        # and removes only the markers (and that temporary file on a failure).
        source = (ROOT / "src" / "vv_log_tools.py").read_text(encoding="utf-8")
        for forbidden in ("paused_game", "back_up_save_folder", "suspend", "TerminateProcess",
                          "write_text", "rmtree", "rename("):
            self.assertNotIn(forbidden, source)
        self.assertEqual(source.count(".write_bytes("), 1)
        self.assertIn("temporary.write_bytes(approval_bytes(game, slot))", source)
        self.assertEqual(source.count("replace("), 1)
        self.assertIn("os.replace(temporary, approval)", source)
        self.assertEqual(source.count(".unlink("), 2)
        self.assertIn("temporary.unlink()", source)


# ---------------------------------------------------------------------------
# Discovery and the window
# ---------------------------------------------------------------------------


class DiscoveryTests(FolderTest):
    def test_every_games_modded_folders_and_their_tribes_are_offered(self) -> None:
        folders = {}
        for tag, number, suffix in CASES:
            folders[(number, suffix)] = self.make_folder(tag, number, suffix)
        for (number, suffix), folder in folders.items():
            title = rename.GAMES[number - 1].title
            found = backup.find_save_folders(title, self.documents)
            self.assertIn(folder, found)
            slots = rename.read_slots(rename.GAMES[number - 1], folder)
            self.assertIsNotNone(slots[0].name)
            self.assertTrue(all(info.name is None for info in slots[1:]))

    def test_documents_comes_from_the_known_folder_api(self) -> None:
        gui = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        body = gui[gui.index("    def _log_tool("):gui.index("    def _check_logs(")]
        self.assertIn("vv_save_backup.documents_folder()", body)
        self.assertIn("vv_save_backup.find_save_folders(game_var.get(), documents)", body)
        self.assertIn("vv_tribe_rename.read_slots(", body)
        self.assertNotIn("Documents\\\\LDW", body)


class GuiTests(unittest.TestCase):
    SOURCE = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")

    def test_the_links_sit_beside_rename_tribe(self) -> None:
        self.assertRegex(
            self.SOURCE,
            r'"Rename Tribe\.\.\.", self\._rename_single_tribe\s*\)\.pack\(side="left", padx=\(18, 0\)\)\s*'
            r'self\._help_button\(links, "rename_tribe"\)\.pack\(side="left", padx=\(3, 0\)\)\s*'
            r'self\._folder_link\(\s*links, "Check Logs\.\.\.", self\._check_single_logs\s*\)\.pack\(side="left", padx=\(18, 0\)\)\s*'
            r'self\._help_button\(links, "check_logs"\)\.pack\(side="left", padx=\(3, 0\)\)\s*'
            r'self\._folder_link\(\s*links, "Repair Logs\.\.\.", self\._repair_single_logs',
        )
        self.assertIn('"Check logs...",\n                lambda game=build: self._log_tool(game, repair=False)', self.SOURCE)
        self.assertIn('"Repair logs...",\n                lambda game=build: self._log_tool(game, repair=True)', self.SOURCE)
        self.assertIn('text="Check Logs...",\n            command=lambda: self._log_tool(None, repair=False)', self.SOURCE)
        self.assertIn('text="Repair Logs...",\n            command=lambda: self._log_tool(None, repair=True)', self.SOURCE)

    def test_both_run_off_the_main_thread_through_the_module(self) -> None:
        self.assertIn("import vv_log_tools", self.SOURCE)
        self.assertIn("lambda: vv_log_tools.check_logs(folder, info.slot, number)", self.SOURCE)
        self.assertIn("lambda: vv_log_tools.approve_repair(folder, number, info.slot)", self.SOURCE)
        self.assertRegex(self.SOURCE, r'self\._run_with_wait\(\s*"Checking the logs')

    def test_repair_refuses_a_running_game_and_confirms_first(self) -> None:
        body = self.SOURCE[self.SOURCE.index("    def _repair_logs("):self.SOURCE.index("    def _close(")]
        refuse = body.index("vv_save_backup.running_game_count(folder)")
        ask = body.index("messagebox.askyesno(")
        act = body.index("vv_log_tools.approve_repair(")
        self.assertLess(refuse, ask)
        self.assertLess(ask, act)
        self.assertIn("The next time you play {info.name}, the game will check", body)
        self.assertIn("repair everything confirmed wrong WITHOUT asking", body)
        self.assertIn("finds nothing confirmed wrong", body)
        self.assertNotIn("paused_game", body)

    def test_the_automatic_check_setting_is_off_by_default_remembered_and_built_in(self) -> None:
        self.assertIn("self.check_logs_var = tk.BooleanVar(value=False)", self.SOURCE)
        load = self.SOURCE[self.SOURCE.index("    def _load_settings("):self.SOURCE.index("    def _save_settings(")]
        self.assertIn('saved_check_logs = data.get("check_logs_automatically", False)', load)
        self.assertIn("self.check_logs_var.set(saved_check_logs is True)", load)
        save = self.SOURCE[self.SOURCE.index("    def _save_settings("):self.SOURCE.index("    def _browse_exe(")]
        self.assertIn('"check_logs_automatically": bool(self.check_logs_var.get()),', save)
        # Beside Check Logs / Repair Logs on both tabs.
        self.assertEqual(self.SOURCE.count("variable=self.check_logs_var,"), 2)
        self.assertRegex(self.SOURCE, r'"Repair Logs\.\.\.", self\._repair_single_logs\s*\)\.pack\(side="left", padx=\(18, 0\)\)\s*'
                                      r'self\._help_button\(links, "repair_logs"\)\.pack\(side="left", padx=\(3, 0\)\)\s*'
                                      r'check_logs_row = ttk\.Frame\(box\)\s*'
                                      r'check_logs_row\.grid\(.*\)\s*'
                                      r'ttk\.Checkbutton\(\s*check_logs_row,\s*text=CHECK_LOGS_LABEL')
        # Every game the window creates carries it.
        for call in ("lambda: apply_patch(", "lambda: apply_all("):
            at = self.SOURCE.index(call)
            self.assertIn("check_logs_automatically=check_logs,", self.SOURCE[at:at + 400])
        self.assertEqual(self.SOURCE.count("check_logs_automatically=check_logs,"), 6)

    def test_the_report_window_scrolls_and_is_read_only(self) -> None:
        body = self.SOURCE[self.SOURCE.index("    def _show_log_report("):self.SOURCE.index("    def _repair_logs(")]
        self.assertIn("ttk.Scrollbar(body", body)
        self.assertIn('text.configure(state="disabled")', body)
        self.assertIn("result.summary", body)
        self.assertIn("result.text.splitlines()", body)

    def test_the_checker_needs_no_third_party_package(self) -> None:
        import ast
        tree = ast.parse((ROOT / "scripts" / "vvfp_consistency_check.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module.split(".")[0])
        self.assertEqual(imported - set(sys.stdlib_module_names), set())

    def test_the_module_and_checker_ship_in_the_release(self) -> None:
        build = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('"src/vv_log_tools.py"', build)
        self.assertIn('"scripts/vvfp_consistency_check.py"', build)


if __name__ == "__main__":
    unittest.main()
