"""Repair Saves & Logs rewrites old '?' names to the real ones (v1.35.89; the owner: "Yes you can rewrite
old ? Names").

Up to v1.35.88 the parentage exporter wrote each name byte 0x80-0xFF as '?': "Zoe Nunez" with her accents
is "Zo? ???ez" in that build's logs (src/vv_legacy_names.py).  The repair rewrites a record's name only
when the masked name belongs to exactly one save villager and the record's Head, Body (and Sex) are
hers; records keep their numbers and places, none is added, removed or moved, the folder is backed up
first, nothing is written without the repair, and a second repair finds nothing.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_genealogy as gen  # noqa: E402
import vv_last_names as ln  # noqa: E402
import vv_legacy_names as legacy  # noqa: E402
from vv_game_text import GAME_TEXT  # noqa: E402
from test_last_names_rename import DATA, LOGS, NOW, TABLE, NoGame, Running, entry  # noqa: E402

ZOE = "Zoë Ñúñez"
ZOE_ACUTE = "Zoé Ñúñez"           # the same mask: "Zo? ???ez"
VILLAGE = "Village: Tribe (Save 1)\n"
BIRTHS = Path(LOGS) / "Births and Conceptions" / "Virtual Villagers 3 Births and Conceptions Log 1.txt"


def _entry(name: str, *args, **kwargs) -> bytes:
    e = bytearray(entry("X" * 12, *args, **kwargs))
    raw = name.encode(GAME_TEXT)
    e[0x14:0x14 + 12] = bytes(12)
    e[0x14:0x14 + len(raw)] = raw
    return bytes(e)


def _birth(number: int, child: str, head: int, body: int) -> str:
    return (f"Birth {number}\n  Child: {child}\n    Sex: Female\n    Head: {head}\n    Body: {body}\n"
            "  Mother: Ma\n    Head: 4\n    Body: 4\n  Father: Pa\n    Head: 2\n    Body: 2\n\n")


class OldQuestionMarkNames(unittest.TestCase):
    def _village(self, save_people: list[bytes], log: str) -> Path:
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        people = [entry("Ma", 1, 7, 4, 4), entry("Pa", 0, 7, 2, 2)] + save_people
        (folder / "Virtual Villagers - The Secret City1.ldw").write_bytes(
            bytes(bytearray(b"ldwg" + bytes(TABLE - 4)) + b"".join(people) + bytes(64)))
        (folder / DATA).mkdir(parents=True)
        (folder / BIRTHS).parent.mkdir(parents=True)
        (folder / BIRTHS).write_bytes((VILLAGE + log).replace("\n", "\r\n").encode("ascii"))
        return folder

    def test_one_masked_villager_is_rewritten_in_place(self):
        log = _birth(1, "Kai", 1, 1) + _birth(2, "Zo? ???ez", 3, 5) + _birth(3, "Lea", 6, 6)
        folder = self._village([entry("Kai", 1, 7, 1, 1), _entry(ZOE, 1, 7, 3, 5), entry("Lea", 1, 7, 6, 6)], log)
        found = legacy.survey(folder, 3, 1)
        self.assertEqual([(f.masked, f.real, f.record) for f in found.found], [("Zo? ???ez", ZOE, "Birth 2")])
        self.assertIn("\"Zo? ???ez\" → \"" + ZOE + "\"", legacy.describe(found.found))
        self.assertIn("Birth 2", legacy.describe(found.found))
        before = (folder / BIRTHS).read_bytes()
        legacy.repair(folder, 3, 1, NoGame(), NOW)
        after = (folder / BIRTHS).read_bytes()
        expected = before.replace(b"  Child: Zo? ???ez\r\n", b"  Child: " + ZOE.encode(GAME_TEXT) + b"\r\n")
        self.assertEqual(after, expected, "only the name, in place: every record keeps its number and place")
        # The save folder was backed up first.
        self.assertTrue(any("before rewriting old question-mark names" in p.name for p in folder.parent.rglob("*")
                            if p.is_dir()) or any("before rewriting old question-mark names" in str(p) for p in folder.rglob("*")))
        # A second repair finds nothing and changes nothing.
        self.assertEqual(legacy.survey(folder, 3, 1).found, [])
        with self.assertRaises(ln.LastNamesError):
            legacy.repair(folder, 3, 1, NoGame(), NOW)
        self.assertEqual((folder / BIRTHS).read_bytes(), after)
        # One villager, by her real name.
        village = gen.load_village(folder, 3, 1)
        self.assertEqual(sorted(p.name for p in village.people.values() if p.name.startswith("Zo")), [ZOE])

    def test_a_mask_two_villagers_share_is_left_alone_and_reported(self):
        log = _birth(1, "Zo? ???ez", 3, 5)
        folder = self._village([_entry(ZOE, 1, 7, 3, 5), _entry(ZOE_ACUTE, 1, 7, 6, 6)], log)
        found = legacy.survey(folder, 3, 1)
        self.assertEqual(found.found, [])
        self.assertEqual(found.shared, {"Zo? ???ez": sorted([ZOE, ZOE_ACUTE])})

    def test_other_looks_are_somebody_else(self):
        folder = self._village([_entry(ZOE, 1, 7, 3, 5)], _birth(1, "Zo? ???ez", 9, 9))
        self.assertEqual(legacy.survey(folder, 3, 1).found, [])

    def test_nothing_is_written_without_the_repair_or_while_the_game_runs(self):
        folder = self._village([_entry(ZOE, 1, 7, 3, 5)], _birth(1, "Zo? ???ez", 3, 5))
        before = {p: p.read_bytes() for p in folder.rglob("*") if p.is_file()}
        legacy.survey(folder, 3, 1)
        legacy.plan(folder, 3, 1)
        with self.assertRaises(Exception):
            legacy.repair(folder, 3, 1, Running(), NOW)
        self.assertEqual({p: p.read_bytes() for p in folder.rglob("*") if p.is_file()}, before)


class RepairWiring(unittest.TestCase):
    def test_check_and_repair_offer_it(self):
        tools = (ROOT / "src" / "vv_log_tools.py").read_text(encoding="utf-8")
        self.assertIn("vv_legacy_names.survey(", tools)
        gui = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertIn("vv_legacy_names.repair(folder, number, info.slot)", gui)
        self.assertIn("vv_legacy_names.survey(folder, number, info.slot)", gui)


if __name__ == "__main__":
    unittest.main()
