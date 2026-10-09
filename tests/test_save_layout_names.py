"""The save folder's new names, and the names older builds used (the owner, 2026-10-09: "from now on
use the new renaming, but it also recognizes the old renaming").

Nothing is ever moved or renamed -- a v1.35.64 preview's Repair Saves & Logs moved the files while A
New Home was still patched by v1.35.63, whose companion then found "Parentage Records" empty.  Every
reader and writer, here (src/vv_save_layout.py, scripts/vvfp_consistency_check.py) and in the game
(native/shared/save_layout.h, log_words.h; native/shared/save_layout_harness.c run below), picks:
new name only -> the new one; old name only -> the old one, read AND written; neither -> the new
one; both -> a whole file the one written last, a log folder written in the new one and read from
both, the Like and Dislike Words read from both with the smaller boundary of each log file, and a
Repair approval acted on under neither.  The owner's own A New Home - Modded folder is rebuilt here
from its inventory."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_save_layout as layout  # noqa: E402
import vv_log_tools as tools  # noqa: E402

DATA, LOGS, TREES = layout.DATA, layout.LOGS, layout.TREES
OLD_TIME = 1_700_000_000 * 10**9          # 2023: the file written first
NEW_TIME = 1_800_000_000 * 10**9          # 2027: the file written last

# (the new name, the older builds' name, a whole file?) for every renamed place.
PLACES = [
    (f"{LOGS}\\Deaths and Disappearances\\Virtual Villagers 1 Deaths Log 1.txt",
     f"{LOGS}\\Deaths\\Virtual Villagers 1 Deaths Log 1.txt", False),
    (f"{LOGS}\\Repairs Made\\Virtual Villagers 1 Repairs Log 1.txt",
     f"{LOGS}\\Repairs\\Virtual Villagers 1 Repairs Log 1.txt", False),
    (f"{TREES}\\Reports\\Kalahuna Tribe 1 (Save 1) Genealogy.txt", f"{LOGS}\\Genealogy\\Kalahuna Tribe 1 (Save 1) Genealogy.txt", True),
    (f"{DATA}\\Family Tree Edits\\Virtual Villagers 1 Family Tree Edits - Save 1.json",
     f"{DATA}\\Genealogy\\Virtual Villagers 1 Genealogy Edits - Save 1.json", True),
    (f"{DATA}\\Like and Dislike Words\\Virtual Villagers 1 Log Words.dat",
     f"{DATA}\\Log Words\\Virtual Villagers 1 Log Words.dat", False),
    (f"{DATA}\\Log Checks\\Virtual Villagers 1 Repair Approved - Save 1.dat",
     f"{DATA}\\Cross-Check\\Virtual Villagers 1 Repair Approved - Save 1.dat", True),
    (f"{DATA}\\Parents (A New Home)\\Virtual Villagers 1 Parentage Records - Save 1.dat",
     f"{DATA}\\Parentage Records\\Virtual Villagers 1 Parentage Records - Save 1.dat", True),
    (f"{DATA}\\Unaccounted Villagers\\Virtual Villagers 1 Villagers at Last Save - Save 1.dat",
     f"{DATA}\\Unaccounted Villagers\\Virtual Villagers 1 Village Roster - Save 1.dat", True),
    (f"{DATA}\\Village Statistics\\Villagers Counted - Save 1.dat",
     f"{DATA}\\Village Statistics\\Village Roster - Save 1.dat", True),
]


def write(path: Path, text: str, when: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    if when is not None:
        os.utime(path, ns=(when, when))


def tree(folder: Path) -> dict[str, bytes | None]:
    return {p.relative_to(folder).as_posix(): (p.read_bytes() if p.is_file() else None)
            for p in sorted(folder.rglob("*"))}


class EveryPlaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_nothing_in_the_tools_moves_or_renames(self) -> None:
        self.assertFalse(hasattr(layout, "migrate"))
        for path in sorted((ROOT / "src").glob("*.py")) + sorted((ROOT / "scripts").glob("*.py")):
            with self.subTest(path=path.name):
                self.assertNotRegex(path.read_text(encoding="utf-8"), r"layout\.migrate\b")
        for path in sorted((ROOT / "native").rglob("*.[ch]")) + sorted((ROOT / "native").rglob("*.inc")):
            with self.subTest(path=path.name):
                self.assertNotIn("vv_layout_move", path.read_text(encoding="utf-8", errors="replace"))

    def test_each_place_under_each_of_the_four_states(self) -> None:
        for new, old, whole in PLACES:
            with self.subTest(place=new):
                self.assertEqual(layout.old_name(new), old)
                f = self.folder / new.replace("\\", "/")
                o = self.folder / old.replace("\\", "/")
                # neither: the new name, nothing made
                self.assertEqual(layout.find(self.folder, new), f)
                self.assertEqual(layout.writable(self.folder, new), f)
                self.assertEqual(layout.places(self.folder, new), [])
                # the older build's only: used where it is, for reading and writing
                write(o, "old", OLD_TIME)
                self.assertEqual(layout.find(self.folder, new), o)
                self.assertEqual(layout.writable(self.folder, new), o)
                self.assertEqual(layout.places(self.folder, new), [o])
                # both: a whole file the one written last; a log or the words written in the new one
                write(f, "new", NEW_TIME)
                self.assertEqual(layout.find(self.folder, new), f)
                self.assertEqual(layout.places(self.folder, new), [o, f])
                self.assertEqual(layout.writable(self.folder, new), f)
                os.utime(o, ns=(NEW_TIME + 10**9, NEW_TIME + 10**9))
                self.assertEqual(layout.find(self.folder, new), o)                # the older build's, written last
                # the new one only
                o.unlink()
                self.assertEqual(layout.find(self.folder, new), f)
                self.assertEqual(layout.writable(self.folder, new), f)
                self.assertEqual(f.read_text(encoding="utf-8"), "new")
                f.unlink()

    def test_a_folder_under_both_names_is_written_in_the_new_one(self) -> None:
        (self.folder / LOGS / "Deaths").mkdir(parents=True)
        self.assertEqual(layout.find(self.folder, f"{LOGS}\\Deaths and Disappearances"), self.folder / LOGS / "Deaths")
        (self.folder / LOGS / "Deaths and Disappearances").mkdir()
        self.assertEqual(layout.find(self.folder, f"{LOGS}\\Deaths and Disappearances"),
                         self.folder / LOGS / "Deaths and Disappearances")


class OwnersFolderTests(unittest.TestCase):
    """The owner's A New Home - Modded folder on 2026-10-09, from its inventory."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self._tmp.name) / "Virtual Villagers - A New Home - Modded"
        f = self.folder
        t = lambda hh, mm: (1_791_590_400 + hh * 3600 + mm * 60) * 10**9      # 2026-10-09 hh:mm (UTC)
        write(f / LOGS / "Deaths and Disappearances" / "Virtual Villagers 1 Deaths Log 1.txt",
              "Village: Kalahuna Tribe 1 (Save 1)\nDeath 1\n  Name: Ana\n\nDeath 2\n  Name: Bo\n\n", t(14, 11))
        write(f / LOGS / "Deaths" / "Virtual Villagers 1 Deaths Log 1.txt",
              "Village: Kalahuna Tribe 1 (Save 1)\nDeath 1\n  Name: Cy\n\n", t(15, 21))
        history = f"{LOGS}\\Tribe History\\Village History 1.txt"
        write(f / DATA / "Like and Dislike Words" / "Virtual Villagers 1 Log Words.dat", f"0\t{history}\r\n",
              t(0, 0) - 2 * 86400 * 10**9)
        write(f / DATA / "Log Words" / "Virtual Villagers 1 Log Words.dat", f"1763792\t{history}\r\n", t(14, 23))
        u = f / DATA / "Unaccounted Villagers"
        write(u / "Virtual Villagers 1 Village Roster - Save 1.dat", "15:21 roster", t(15, 21))
        write(u / "Virtual Villagers 1 Villagers at Last Save - Save 1.dat", "14:13 roster", t(14, 13))
        s = f / DATA / "Village Statistics"
        write(s / "Village Roster - Save 1.dat", "15:21 counted", t(15, 21))
        write(s / "Villagers Counted - Save 1.dat", "14:13 counted", t(14, 13))
        write(f / DATA / "Parents (A New Home)" / "Virtual Villagers 1 Parentage Records - Save 1.dat", "parents",
              t(14, 13))
        (f / DATA / "Parentage Records").mkdir(parents=True)
        write(f / DATA / "Log Checks" / "Virtual Villagers 1 Repair Approved - Save 1.dat", "approval", t(14, 12))
        (f / DATA / "Cross-Check").mkdir()
        write(f / DATA / "Family Tree Edits" / "Virtual Villagers 1 Family Tree Edits - Save 1.json", "{}", t(15, 32))
        (f / DATA / "Genealogy").mkdir()
        write(f / TREES / "Reports" / "Kalahuna Tribe 1 (Save 1) Genealogy.txt", "report", t(15, 32))
        (f / LOGS / "Genealogy").mkdir()
        write(f / LOGS / "Repairs Made" / "Virtual Villagers 1 Repairs Log 1.txt", "Repair 1\n", t(0, 19))
        (f / LOGS / "Repairs").mkdir()
        self.before = tree(f)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_every_choice(self) -> None:
        f = self.folder
        find = lambda rel: layout.find(f, rel)
        # Whole files under one name only: that one.
        self.assertEqual(find(f"{DATA}\\Parents (A New Home)\\Virtual Villagers 1 Parentage Records - Save 1.dat"),
                         f / DATA / "Parents (A New Home)" / "Virtual Villagers 1 Parentage Records - Save 1.dat")
        self.assertEqual(find(f"{DATA}\\Log Checks\\Virtual Villagers 1 Repair Approved - Save 1.dat"),
                         f / DATA / "Log Checks" / "Virtual Villagers 1 Repair Approved - Save 1.dat")
        self.assertEqual(find(f"{DATA}\\Family Tree Edits\\Virtual Villagers 1 Family Tree Edits - Save 1.json"),
                         f / DATA / "Family Tree Edits" / "Virtual Villagers 1 Family Tree Edits - Save 1.json")
        self.assertEqual(find(f"{TREES}\\Reports"), f / TREES / "Reports")
        self.assertEqual(find(f"{LOGS}\\Repairs Made"), f / LOGS / "Repairs Made")
        # Both rosters under both names: the older build's, written last (15:21 over 14:13).
        self.assertEqual(find(f"{DATA}\\Unaccounted Villagers\\Virtual Villagers 1 Villagers at Last Save - Save 1.dat"),
                         f / DATA / "Unaccounted Villagers" / "Virtual Villagers 1 Village Roster - Save 1.dat")
        self.assertEqual(find(f"{DATA}\\Village Statistics\\Villagers Counted - Save 1.dat"),
                         f / DATA / "Village Statistics" / "Village Roster - Save 1.dat")
        checker = tools.load_checker()
        # The Deaths log under both folders: every record read, new ones written in the new folder.
        names = sorted(r.split("\n")[1] for r in checker.deaths_records(f, 1, 1))
        self.assertEqual(names, ["  Name: Ana", "  Name: Bo", "  Name: Cy"])
        self.assertEqual(checker.DEATHS_FOLDER(f), "Deaths and Disappearances")
        # The words: the smaller boundary (0, not the older build's 1763792).
        self.assertEqual(checker.word_boundaries(f, 1),
                         {f"{LOGS}\\Tribe History\\Village History 1.txt".lower(): 0})
        # Nothing was moved, renamed, made or changed by any of it.
        self.assertEqual(tree(f), self.before)


class NativeHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_vv1_crosscheck as xc
        cls.work = Path(tempfile.mkdtemp())
        vs, sdk, ver = xc._toolchain()
        cl = vs / "bin" / "Hostx64" / "x86" / "cl.exe"
        if not cl.exists():
            raise unittest.SkipTest("MSVC x86 toolchain not installed")
        exe = cls.work / "save_layout_harness.exe"
        shared = ROOT / "native" / "shared"
        cmd = [str(cl), "/nologo", "/W3", "/MT",
               "/I", str(vs / "include"), "/I", str(sdk / "Include" / ver / "um"),
               "/I", str(sdk / "Include" / ver / "shared"), "/I", str(sdk / "Include" / ver / "ucrt"),
               "/I", str(shared), str(shared / "save_layout_harness.c"), f"/Fe{exe}", f"/Fo{cls.work}\\",
               "/link", f"/LIBPATH:{vs / 'lib' / 'x86'}", f"/LIBPATH:{sdk / 'Lib' / ver / 'um' / 'x86'}",
               f"/LIBPATH:{sdk / 'Lib' / ver / 'ucrt' / 'x86'}", "kernel32.lib", "user32.lib"]
        build = subprocess.run(cmd, capture_output=True, text=True, cwd=cls.work)
        if build.returncode != 0:
            raise AssertionError(build.stdout[-3000:] + build.stderr[-3000:])
        save = cls.work / "save"
        save.mkdir()
        cls.result = subprocess.run([str(exe), str(save)], capture_output=True, text=True, timeout=120)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(getattr(cls, "work", ""), ignore_errors=True)

    def test_every_check_passes(self):
        out = self.result.stdout
        self.assertIn("== 0 failure(s) ==", out, out)
        self.assertNotIn("FAIL", out, out)
        self.assertEqual(self.result.returncode, 0, out)

    def test_the_cases_are_all_run(self):
        for case in (
            "a whole file under neither name: the new name",
            "only under the older build's name: used where it is",
            "under both, the one written last: the owner's rosters (the older build's 15:21 over the new 14:13)",
            "... or the new one when it was written last",
            "only under the new name: the new one",
            "... and nothing is moved or made",
            "a log folder under neither name: written in the new one, nothing made to look",
            "only the older build's Deaths: written where it is, never moved",
            "both: new records go to Deaths and Disappearances, the older folder kept",
            "the words: no boundary file under either name, the whole file is old",
            "only the older build's Log Words: read where it is",
            "... and written where it is, no new folder made",
            "both (the owner's: 1763792 in the older one, 0 in the new): the smaller, so correct words stay correct",
            "... read from both files",
            "... and new boundaries are written to the new one",
            "a file only one of them records: that one's boundary",
            "only the new one: read and written there",
        ):
            with self.subTest(case=case):
                self.assertIn("PASS " + case, self.result.stdout)


if __name__ == "__main__":
    unittest.main()
