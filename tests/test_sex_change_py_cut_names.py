"""Names the Details screen cut (src/vv_cut_names.py) across a change of sex: the full name logged under
the old sex is still theirs once the save's "Sex Changes" log names them (src/vv_sex_changes.py)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_save_layout as layout  # noqa: E402
import test_cut_names as base  # noqa: E402


class CutNameAcrossASexChange(unittest.TestCase):
    # test_cut_names' own village (a The Secret City save and its logs), without its tests.
    setUp = base.CutNames.setUp
    write_save = base.CutNames.write_save
    log = base.CutNames.log
    found = base.CutNames.found

    def test_another_sex_is_them_only_when_the_log_says_their_sex_changed(self):
        self.history.write_bytes(self.history.read_bytes().replace(
            f"  Name: {base.FULL}\r\n  Age: 400\r\n  Sex: Male".encode(),
            f"  Name: {base.FULL}\r\n  Age: 400\r\n  Sex: Female".encode()))
        self.assertEqual(self.found(), ({}, []))
        path = self.folder / layout.save_root(1) / layout.SAVE_DATA / "Sex Changes" / "Sex Changes - Save 1.txt"
        path.parent.mkdir(parents=True)
        path.write_bytes(f"F\tM\t{base.CUT}\r\n".encode("cp1252"))
        self.assertEqual(self.found(), ({base.CUT: base.FULL}, []))


if __name__ == "__main__":
    unittest.main()
