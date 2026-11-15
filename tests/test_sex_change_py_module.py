"""src/vv_sex_changes.py: the save's "Sex Changes - Save S.txt" (native/shared/sex_change.h), read in both
places, the Appearance changed records' Old sex / New sex lines, and the one rule (same_villager_sex)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_save_layout as layout  # noqa: E402
import vv_sex_changes as sexes  # noqa: E402


class Block:
    def __init__(self, text: str):
        self.lines = text.split("\n")

    @property
    def heading(self) -> str:
        return self.lines[0].strip()


SEX_RECORD = ("Appearance changed\n  Name: Ann\n  Old head: 3\n  Old body: 4\n  New head: 3\n  New body: 4\n"
              "  Old sex: Male\n  New sex: Female")


class TheLog(unittest.TestCase):
    def folder(self) -> Path:
        return Path(self.enterContext(tempfile.TemporaryDirectory()))

    def test_the_older_place_is_read(self):
        folder = self.folder()
        path = folder / layout.DATA / "Sex Changes" / "Sex Changes - Save 2.txt"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"M\tF\tAnn\r\nF\tM\tB\xe9a\r\n")
        self.assertEqual(sexes.read(folder, 2), [sexes.SexChange("M", "F", "Ann"), sexes.SexChange("F", "M", "Béa")])
        self.assertEqual(sexes.changed_names(folder, 2), {"Ann", "Béa"})
        self.assertEqual(sexes.changed_names(folder, 1), set())        # another save's log is not this one's

    def test_the_save_s_own_folder_is_read_and_the_longer_log_wins(self):
        folder = self.folder()
        old = folder / layout.DATA / "Sex Changes" / "Sex Changes - Save 1.txt"
        new = folder / layout.save_root(1) / layout.SAVE_DATA / "Sex Changes" / "Sex Changes - Save 1.txt"
        for p in (old, new):
            p.parent.mkdir(parents=True)
        old.write_bytes(b"M\tF\tAnn\r\n")
        new.write_bytes(b"M\tF\tAnn\r\nF\tM\tAnn\r\n")
        self.assertEqual(len(sexes.read(folder, 1)), 2)
        self.assertEqual(sexes.changed_names(folder, 1), {"Ann"})

    def test_lines_that_are_not_changes_are_skipped(self):
        self.assertEqual(sexes.parse(b"M\tM\tAnn\r\nX\tF\tBo\r\nMale\tF\tCy\r\njunk\r\nF\tM\t\r\n"), [])

    def test_no_log_is_no_changes(self):
        self.assertEqual(sexes.read(self.folder(), 3), [])


class TheRule(unittest.TestCase):
    def test_the_same_sex_or_one_unsaid_agrees(self):
        self.assertTrue(sexes.same_villager_sex("Ann", "Male", "male"))
        self.assertTrue(sexes.same_villager_sex("Ann", "M", "Male"))
        self.assertTrue(sexes.same_villager_sex("Ann", None, "Female"))
        self.assertTrue(sexes.same_villager_sex("Ann", "", "Female"))

    def test_another_sex_agrees_only_for_a_name_the_logs_name(self):
        self.assertFalse(sexes.same_villager_sex("Ann", "Male", "Female"))
        self.assertFalse(sexes.same_villager_sex("Ann", "Male", "Female", {"Bo"}))
        self.assertTrue(sexes.same_villager_sex("Ann", "Male", "Female", {"Ann"}))
        self.assertTrue(sexes.same_villager_sex(("Ann Kai", "Ann"), "Male", "Female", {"Ann"}))


class TheHistoryRecord(unittest.TestCase):
    def test_the_appearance_changed_record_with_sex_lines_names_the_villager(self):
        self.assertEqual(sexes.history_names([Block(SEX_RECORD)]), {"Ann"})
        self.assertTrue(sexes.is_sex_line("  Old sex: Male"))
        self.assertTrue(sexes.is_sex_line("  New sex: Female"))

    def test_a_look_change_alone_names_nobody(self):
        plain = "Appearance changed\n  Name: Ann\n  Old head: 3\n  Old body: 4\n  New head: 5\n  New body: 4"
        self.assertEqual(sexes.history_names([Block(plain)]), set())
        self.assertEqual(sexes.history_names([Block(SEX_RECORD.replace("New sex: Female", "New sex: Male"))]), set())

    def test_the_checker_reads_the_same_record_and_log(self):
        import vvfp_consistency_check as checker
        self.assertEqual(checker.sex_change_record_name(SEX_RECORD.split("\n")), "Ann")
        self.assertEqual(checker.sex_change_record_name(["Village: X (Save 1)"] + SEX_RECORD.split("\n")), "Ann")
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        path = folder / layout.DATA / "Sex Changes" / "Sex Changes - Save 1.txt"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"M\tF\tAnn\r\n")
        self.assertEqual(checker.sex_changed_names(folder, 1), {"Ann"})

    def test_the_checker_never_guesses_an_older_record_s_sex(self):
        """A Sex line missing from an older record of a villager whose sex changed: asked, never taken from
        the save or the name lists (scripts/vvfp_consistency_check.py sex_for)."""
        import vvfp_consistency_check as checker
        person = {"name": "Ann", "head": 3, "body": 4}
        self.assertEqual(checker.sex_for(2, person, {("Ann", 3, 4): {"Female"}}, {"Ann": {"Female"}})[0], "Female")
        self.assertEqual(checker.sex_for(2, person, {("Ann", 3, 4): {"Female", checker.SEX_CHANGED}},
                                         {"Ann": {"Female", checker.SEX_CHANGED}}), (None, ""))


if __name__ == "__main__":
    unittest.main()
