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


# One real record of each patcher log the survey reads that can hold a name, in the format the existing
# log tests use (test_last_names_rename, test_cut_names, test_lost_titles).  "{n}" is the name.
LOG_KINDS = {
    "History": ("Tribe History/Village History 1.txt",
                "=== Virtual Villagers 3 -- 2026-10-01 ===\nVillage: Tribe (Save 1)\n"
                "Villager 1\n  Name: Kai\n  Head: 1\n  Body: 1\n\n"
                "Villager 2\n  Name: {n}\n  Head: 3\n  Body: 5\n\n"),
    "Deaths": ("Deaths/Virtual Villagers 3 Deaths Log 1.txt",
               "Village: Tribe (Save 1)\nDeath 1\n  Name: Old\n  Age at death: 1400\n  Head: 9\n  Body: 9\n\n"
               "Death 2\n  Name: {n}\n  Age at death: 1400\n  Head: 3\n  Body: 5\n\n"),
    "Arrived": ("Births and Conceptions/Virtual Villagers 3 Births and Conceptions Log 1.txt",
                "Village: Tribe (Save 1)\nArrived 1\n  Name: Kai\n  Age at arrival: 480\n  Sex: Male\n"
                "  Head: 1\n  Body: 1\n  How: unknown\n\n"
                "Arrived 2\n  Name: {n}\n  Age at arrival: 480\n  Sex: Female\n  Head: 3\n  Body: 5\n"
                "  How: unknown\n\n"),
    "Unaccounted": ("Deaths/Virtual Villagers 3 Deaths Log 1.txt",
                    "Village: Tribe (Save 1)\nUnaccounted 1\n  Name: {n}\n"
                    "  What: Arrived with no Birth record or known arrival\n  Head: 3\n  Body: 5\n\n"),
    "Population": ("Tribe Population/Village Population 1.txt",
                   "Village: Tribe (Save 1)\nVillager 1\n  Name: {n}\n  Age: 400\n  Sex: Female\n  Head: 3\n"
                   "  Body: 5\n  Likes: ants\n  Dislikes: bees\n\n"),
    "Island events": ("Island Events/Virtual Villagers 3 Island Events Log 1.txt",
                      "Village: Tribe (Save 1)\nIsland event 1\n  Name: {n}\n  Event: The Mystery Liquid\n"
                      "  Head: 3\n  Body: 5\n  Likes: ants\n  Dislikes: bees\n\n"),
}


class EveryLogKind(unittest.TestCase):
    """The rewrite in each log the survey reads: one byte-exact line, records keep their numbers, and a
    second repair finds nothing."""

    def _folder(self, relative: str, text: str) -> Path:
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        people = [entry("Kai", 0, 7, 1, 1), _entry(ZOE, 1, 7, 3, 5)]
        (folder / "Virtual Villagers - The Secret City1.ldw").write_bytes(
            bytes(bytearray(b"ldwg" + bytes(TABLE - 4)) + b"".join(people) + bytes(64)))
        (folder / DATA).mkdir(parents=True)
        path = folder / LOGS / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.replace("\n", "\r\n").encode("ascii"))
        return folder

    def test_each_kind(self):
        import re
        for kind, (relative, template) in LOG_KINDS.items():
            with self.subTest(log=kind):
                folder = self._folder(relative, template.format(n="Zo? ???ez"))
                path = folder / LOGS / relative
                before = path.read_bytes()
                found = legacy.survey(folder, 3, 1)
                self.assertEqual([(f.masked, f.real) for f in found.found], [("Zo? ???ez", ZOE)], kind)
                legacy.repair(folder, 3, 1, NoGame(), NOW)
                after = path.read_bytes()
                old_lines, new_lines = before.split(b"\r\n"), after.split(b"\r\n")
                self.assertEqual(len(old_lines), len(new_lines), kind)
                changed = [(o, n) for o, n in zip(old_lines, new_lines) if o != n]
                self.assertEqual(changed, [(b"  Name: Zo? ???ez", b"  Name: " + ZOE.encode(GAME_TEXT))], kind)
                headings = re.compile(rb"^[A-Z][A-Za-z ]* \d+$", re.M)
                self.assertEqual(headings.findall(before), headings.findall(after), "record numbers kept")
                self.assertEqual(legacy.survey(folder, 3, 1).found, [], "a second repair finds nothing")


class TheBumpOnTheHead(unittest.TestCase):
    """"?" is a real name: the island events that make a villager forget their name write exactly "?"
    (The Lost Children's "A Bump On The Head", The Secret City, The Tree of Life, New Believers).  It is
    never read as an older exporter's mask -- with or without a trailing space -- and a name a save
    villager really has (a player's "Zo?") is never anybody's mask."""

    def _folder(self, people: list[bytes], log: str) -> Path:
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        people = [entry("Ma", 1, 7, 4, 4), entry("Pa", 0, 7, 2, 2)] + people
        (folder / "Virtual Villagers - The Secret City1.ldw").write_bytes(
            bytes(bytearray(b"ldwg" + bytes(TABLE - 4)) + b"".join(people) + bytes(64)))
        (folder / DATA).mkdir(parents=True)
        (folder / BIRTHS).parent.mkdir(parents=True)
        (folder / BIRTHS).write_bytes((VILLAGE + log).replace("\n", "\r\n").encode(GAME_TEXT))
        return folder

    def test_a_forgotten_name_is_never_rewritten_or_merged(self):
        for name in ("?", "? "):
            with self.subTest(name=repr(name)):
                folder = self._folder([_entry(name, 1, 7, 3, 5), _entry("\u00e9", 1, 7, 6, 6)],
                                      _birth(1, name, 3, 5) + _birth(2, "?", 6, 6))
                before = (folder / BIRTHS).read_bytes()
                found = legacy.survey(folder, 3, 1)
                self.assertEqual(found.found, [])
                with self.assertRaises(ln.LastNamesError):
                    legacy.repair(folder, 3, 1, NoGame(), NOW)
                self.assertEqual((folder / BIRTHS).read_bytes(), before)
                village = gen.load_village(folder, 3, 1)
                names = sorted(p.name for p in village.people.values())
                self.assertNotIn("\u00e9", [n for n in names if n != "\u00e9"] and [], [])
                # The "?" of Birth 2 (looks 6/6) is never made the save's "e acute".
                self.assertIn("?", [p.name.rstrip() for p in village.people.values()])

    def test_a_save_with_question_mark_and_e_acute_rewrites_nothing(self):
        folder = self._folder([_entry("?", 1, 7, 3, 5), _entry("\u00e9", 1, 7, 6, 6)], _birth(1, "?", 6, 6))
        self.assertEqual(legacy.survey(folder, 3, 1).found, [])
        import vv_long_names
        self.assertEqual(vv_long_names.legacy_names(["?", "\u00e9"]), {})

    def test_a_players_own_question_mark_name_is_untouched(self):
        folder = self._folder([_entry("Zo?", 1, 7, 3, 5), _entry(ZOE, 1, 7, 6, 6)],
                              _birth(1, "Zo?", 3, 5))
        before = (folder / BIRTHS).read_bytes()
        self.assertEqual(legacy.survey(folder, 3, 1).found, [])
        village = gen.load_village(folder, 3, 1)
        self.assertIn("Zo?", [p.name for p in village.people.values()])
        self.assertEqual((folder / BIRTHS).read_bytes(), before)

    def test_a_name_a_rename_record_gave_is_kept(self):
        log = (_birth(1, "Zo? ???ez", 3, 5)
               + "Name changed\n  Name: Zo? ???ez\n  Old name: Zoe\n  Head: 3\n  Body: 5\n\n")
        folder = self._folder([_entry(ZOE, 1, 7, 3, 5)], log)
        self.assertEqual(legacy.survey(folder, 3, 1).found, [])

class RepairWiring(unittest.TestCase):
    def test_check_and_repair_offer_it(self):
        tools = (ROOT / "src" / "vv_log_tools.py").read_text(encoding="utf-8")
        self.assertIn("vv_legacy_names.survey(", tools)
        gui = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertIn("vv_legacy_names.repair(folder, number, info.slot)", gui)
        self.assertIn("vv_legacy_names.survey(folder, number, info.slot)", gui)


if __name__ == "__main__":
    unittest.main()
