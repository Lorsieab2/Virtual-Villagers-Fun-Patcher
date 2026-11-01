"""Restore Saves offers EVERY backup the patcher makes, whichever tool made it.

Each tool that changes a save folder backs it up first as "Backup <date> (before <what it did>)"
(vv_save_backup.copy_save_folder's suffix).  Restore Saves recognised only four of those labels, so the
backups of Last Names, Number Duplicate Names, the Elder Totems tools, Graves, Lost Titles and the rest were
never listed and could not be restored.  This test collects every label the source uses, so a new tool's
label can never be missed again.
"""
from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_save_backup as backup  # noqa: E402

# A label written as its own string literal: BACKUP_LABEL = "(before last names)", a call's argument...
_LITERAL = re.compile(r'"(\(before [^"()\\\n<>]+\))"')
# A label passed straight to the copier.
_SUFFIX = re.compile(r'copy_save_folder\([^)]*?suffix\s*=\s*"([^"]*)"', re.S)
STAMP = "Backup 2026-01-0{day} 09-00-00"


def sources() -> list[Path]:
    files = sorted((ROOT / "src").rglob("*.py"))
    for pattern in ("*.c", "*.h", "*.inc"):
        files += sorted((ROOT / "native").rglob(pattern))
    return files


def labels() -> dict[str, list[str]]:
    """Every backup label in the source, with where it is."""
    found: dict[str, list[str]] = {}
    for path in sources():
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in (_LITERAL, _SUFFIX):
            for match in pattern.finditer(text):
                found.setdefault(match.group(1), []).append(path.relative_to(ROOT).as_posix())
    return found


class LabelTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self._tmp.name) / "Virtual Villagers - A New Home - Modded"
        (self.folder / "Backups").mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def backup_named(self, name: str) -> Path:
        place = self.folder / "Backups" / name
        place.mkdir()
        (place / "Virtual Villagers0.ldw").write_bytes(b"x")
        return place

    def test_the_source_has_the_labels_this_test_is_about(self) -> None:
        found = labels()
        for label in ("(before restore)", "(before rename)", "(before repair re-arm)", "(before copy)",
                      "(before last names)", "(before numbering names)", "(before taking off numbers)",
                      "(before restoring cut names)", "(before parents restore)",
                      "(before giving elders totems)", "(before moving totems out of the save)"):
            self.assertIn(label, found)

    def test_every_label_the_patcher_uses_is_listed_and_restorable(self) -> None:
        found = labels()
        for day, (label, where) in enumerate(sorted(found.items())):
            with self.subTest(label=label, used_in=where):
                # Every label passed to the copier is "(before <what>)", as the list reads them.
                self.assertRegex(label, r"^\(before [^()]+\)$")
                name = f"Backup 2026-01-01 09-{day // 60:02d}-{day % 60:02d} {label}"
                place = self.backup_named(name)
                listed = {info.path.name: info for info in backup.list_backups(self.folder)}
                self.assertIn(name, listed)
                self.assertEqual(listed[name].suffix, label)
                self.assertTrue(listed[name].label.endswith(" " + label))
                backup._require_backup_of(self.folder, place)      # Restore Saves accepts it

    def test_a_second_backup_of_the_same_second_is_listed_too(self) -> None:
        self.backup_named("Backup 2026-01-01 09-00-00 (before last names)")
        self.backup_named("Backup 2026-01-01 09-00-00 (2) (before last names)")
        names = [info.path.name for info in backup.list_backups(self.folder)]
        self.assertEqual(names, ["Backup 2026-01-01 09-00-00 (2) (before last names)",
                                 "Backup 2026-01-01 09-00-00 (before last names)"])

    def test_the_older_label_without_brackets_is_listed(self) -> None:
        self.backup_named("Backup 2026-01-01 09-00-00 before parents restore")
        (info,) = backup.list_backups(self.folder)
        self.assertEqual(info.suffix, "(before parents restore)")
        self.assertEqual(info.label, "2026-01-01 09:00:00 (before parents restore)")

    def test_a_failed_copy_is_never_offered(self) -> None:
        for name in ("Backup 2026-01-01 09-00-00 INCOMPLETE",
                     "Backup 2026-01-01 09-00-01 (before last names) INCOMPLETE",
                     "Backup 2026-01-01 09-00-02 (before last names) INCOMPLETE (2)",
                     "Backup 2026-01-01 09-00-03 (before copy) (in progress)",
                     "Backup 2026-01-01 09-00-04 (in progress)",
                     "Backup 2026-01-01 09-00-05 before parents restore INCOMPLETE",
                     "Backup 2026-01-01 09-00-06 before parents restore (in progress)",
                     "Backup 2026-01-01 09-00-07 (my own)",
                     "My stuff"):
            self.backup_named(name)
        self.assertEqual(backup.list_backups(self.folder), [])

    def test_a_plain_backup_has_no_label(self) -> None:
        self.backup_named("Backup 2026-01-01 09-00-00")
        (info,) = backup.list_backups(self.folder)
        self.assertEqual((info.suffix, info.label), ("", "2026-01-01 09:00:00"))


if __name__ == "__main__":
    unittest.main()
