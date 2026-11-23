"""Repair Saves & Logs gives a New Believers villager back the mask they wore when they rejoined the tribe
(src/vv5_rejoined_masks.py; the owner, 2026-11-22: Caia and Nobu rejoined as "Former Heathen (blue mask)" and
have no mask now).  On the repository's fixture save, with logs and a Village Masks file written beside it."""
from __future__ import annotations

import shutil
import struct
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_log_tools as tools  # noqa: E402
import vv5_rejoined_masks as rm  # noqa: E402
from test_original_look import Village, arrived, change  # noqa: E402


def converted(number: int, name: str, sex: str, looks: tuple[int, int], title: str | None) -> str:
    extra = (f"  Special villager: {title}\n" if title else "") + "  How: Converted from the Heathens\n"
    return arrived(number, name, sex, looks).replace("\n\n", "\n" + extra + "\n")


class RejoinedMasks(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.v = Village(self.root / "g5", 5)
        self.save = self.v.folder / f"{tools.load_checker().SAVE_STEMS[5]}1.ldw"
        self.p = [x.seen for x in self.v.people]
        data = bytearray(self.save.read_bytes())
        for s in self.p[:5]:
            data[s.at + rm.FACTION] = 0             # believers now
        self.save.write_bytes(bytes(data))

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def masks_file(self, values: dict[int, int]) -> Path:
        checker = tools.load_checker()
        data = self.save.read_bytes()
        roster = [0] * 150
        for s in self.p:
            roster[s.record] = checker._villager(data, s.at, checker.LAYOUTS[5], s.record, 5).ident
        nibbles = bytearray(75)
        for index, mask in values.items():
            nibbles[index >> 1] |= (mask << 4) if index & 1 else mask
        path = rm._masks_path(self.v.folder, 1)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"VM06" + struct.pack("<150I", *roster) + bytes(nibbles))
        return path

    def nibble(self, path: Path, index: int) -> int:
        return tools.load_checker().read_mask_file(5, path.read_bytes()).values[index]

    def test_the_mask_they_rejoined_with_is_given_back_only_when_proven(self):
        p = self.p
        a, b, c, d = p[0], p[1], p[2], p[3]
        path = self.masks_file({b.record: 3})
        self.v.births(
            # a (the owner's Caia): a founder, rejoined in a blue mask, a Reset since took it off.
            arrived(1, a.name, a.sex, (a.head, a.body)) + converted(2, a.name, a.sex, (a.head, a.body), None)
            + change(a.name, (a.head, a.body), (a.head, a.body), ("Blue Mask", "none"))
            + converted(3, a.name, a.sex, (a.head, a.body), "Former Heathen (blue mask)")
            # b rejoined in an orange mask and wears a red one now: theirs, untouched.
            + converted(4, b.name, b.sex, (b.head, b.body), "Former Heathen (orange mask)")
            # c rejoined, but the record names no mask: listed, never guessed.
            + converted(5, c.name, c.sex, (c.head, c.body), None)
            # d never left the tribe: not theirs to change.
            + arrived(6, d.name, d.sex, (d.head, d.body)))
        survey = rm.survey(self.v.folder, 1)
        self.assertEqual([(f.name, f.mask) for f in survey.restore], [(a.name, 1)])
        self.assertEqual([f.name for f in survey.listed], [c.name])
        before = path.read_bytes()
        result = rm.restore(self.v.folder, 1, "Backup test", datetime(2026, 11, 22, 21, 0))
        self.assertEqual([f.name for f in result.restored], [a.name])
        self.assertEqual(self.nibble(path, a.record), 1, "the blue mask they rejoined with is theirs again")
        self.assertEqual(self.nibble(path, b.record), 3)
        self.assertEqual(self.nibble(path, c.record), 0)
        after = path.read_bytes()
        changed = [k for k in range(len(before)) if before[k] != after[k]]
        self.assertEqual(changed, [4 + 150 * 4 + (a.record >> 1)], "only their nibble's byte is written")
        repairs = list(self.v.folder.rglob("*Repairs Log*.txt"))
        self.assertTrue(repairs and a.name in repairs[0].read_text(encoding="cp1252"))
        copies = [q for q in self.v.folder.rglob("*") if q.is_file() and q.read_bytes() == before]
        self.assertTrue(copies, "a copy of the file is kept before the repair")
        self.assertEqual(rm.restore(self.v.folder, 1).restored, [], "running it again changes nothing")

    def test_a_heathen_now_or_a_file_that_does_not_name_them_is_left_alone(self):
        a = self.p[0]
        self.v.births(converted(1, a.name, a.sex, (a.head, a.body), "Former Heathen (red mask)"))
        path = self.masks_file({})
        data = bytearray(self.save.read_bytes())
        data[a.at + rm.FACTION] = 1
        self.save.write_bytes(bytes(data))
        self.assertEqual(rm.survey(self.v.folder, 1).restore, [], "a Heathen now: not this repair's")
        data[a.at + rm.FACTION] = 0
        self.save.write_bytes(bytes(data))
        raw = bytearray(path.read_bytes())
        struct.pack_into("<I", raw, 4 + a.record * 4, 0x1234)
        path.write_bytes(bytes(raw))
        survey = rm.survey(self.v.folder, 1)
        self.assertEqual(survey.restore, [])
        self.assertEqual([f.name for f in survey.listed], [a.name])

    def test_a_namesakes_conversion_is_never_given_to_the_living_villager(self):
        """Codex, #841: a converted villager died, and a later villager of the same name and sex lives now.  The
        dead one's conversion is not the living one's: nothing is given back, and they are listed."""
        a, b = self.p[0], self.p[1]
        self.masks_file({})
        self.v.births(
            # a: the conversion was an earlier namesake's; the living a was born after it.
            converted(1, a.name, a.sex, (1, 1), "Former Heathen (blue mask)")
            + arrived(2, a.name, a.sex, (a.head, a.body))
            # b: rejoined, but a villager of their name died since.
            + converted(3, b.name, b.sex, (b.head, b.body), "Former Heathen (red mask)"))
        self.v.log("Deaths and Disappearances", "Virtual Villagers 5 Deaths Log 1.txt",
                   f"Died\n  Name: {b.name}\n  Sex: {b.sex}\n  What happened: Old age\n\n")
        survey = rm.survey(self.v.folder, 1)
        self.assertEqual(survey.restore, [])
        self.assertEqual(sorted(f.name for f in survey.listed), sorted([a.name, b.name]))

    def test_repair_saves_and_logs_runs_it(self):
        source = (ROOT / "src" / "vv_log_tools.py").read_text(encoding="utf-8")
        self.assertIn("vv5_rejoined_masks.restore(folder, slot, backup.backup_folder.name, now)", source)
        self.assertIn('"src/vv5_rejoined_masks.py"', (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
