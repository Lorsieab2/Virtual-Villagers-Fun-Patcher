"""Copy Player Slot: a village copied into an empty slot of the same save folder (src/vv_copy_slot.py).

Every game, from the real test saves of tests/fixtures/rename_tribe (the same ones Rename Tribe's tests
use), in a throwaway Documents folder with a fake process list: nothing here reads or writes outside it, no
game is started, and no stock exe or compiler is needed.
"""
from __future__ import annotations

import gzip
import json
import os
import re
import struct
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_copy_slot as cs  # noqa: E402
import vv_copy_slot_window as window  # noqa: E402
import vv_save_backup as backup  # noqa: E402
import vv_tribe_rename as rename  # noqa: E402
import vv_vv2_totem_store as totems  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "rename_tribe"
NOW = datetime(2026, 10, 31, 12, 0, 0)
CASES = [("huttest", n, "Modded") for n in range(1, 6)] + [("256", n, "Modded 256") for n in (3, 4, 5)]
OWN = "Virtual Villagers Fun Patcher"
OLD_LOGS = "Virtual Villagers Fun Patcher Logs"
OLD_DATA = "Virtual Villagers Fun Patcher Data"
TREES = "Virtual Villagers Fun Patcher Family Trees"
OLD_TIME = 1_700_000_000_000_000_000           # a fixed past time every source file is given


def fixture(name: str) -> bytes:
    return gzip.decompress((FIXTURES / f"{name}.ldw.gz").read_bytes())


class FakeProcesses:
    def __init__(self, pids=()):
        self.pids = list(pids)

    def find(self, exe_name):
        return list(self.pids)

    def suspend(self, pid, exe_name):  # pragma: no cover
        raise AssertionError("Copy Player Slot must never pause a game")

    def resume(self, handle):  # pragma: no cover
        raise AssertionError("Copy Player Slot must never pause a game")


def fnv(text: str) -> int:
    h = 2166136261
    for b in text.encode("latin-1"):
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.documents = Path(self._tmp.name) / "D"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def put(self, folder: Path, relative: str, data: bytes) -> Path:
        path = folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        os.utime(path, ns=(OLD_TIME, OLD_TIME))
        return path

    def make(self, tag: str, number: int, suffix: str):
        """Slot 1: the fixture village with every kind of patcher file; slot 2: another village's files;
        slots 3-5 empty."""
        game = rename.GAMES[number - 1]
        folder = self.documents / "LDW" / f"{game.title} - {suffix}"
        folder.mkdir(parents=True)
        save = fixture(f"vv{number}-{tag}-1")
        old = rename.save_name(game, save)
        self.put(folder, game.save_path(folder, 1).name, save)
        for generation in rename.GENERATIONS:
            self.put(folder, game.generation_path(folder, generation, 1).name, save)
        self.put(folder, game.index_path(folder).name, fixture(f"vv{number}-{tag}-0"))
        header = f"Village: {old} (Save 1)"
        births = (f"{OWN}\\Save 1\\Logs\\Births and Conceptions\\"
                  f"Virtual Villagers {number} Births and Conceptions Log 1.txt")
        log = (f"{header}\r\nConception 1\r\n  Mother: Ana\r\n\r\nVillage: Someone Else (Save 1)\r\n"
               f"Conception 2\r\n\r\n{header}\r\nBirth 3\r\n").encode("latin-1")
        self.put(folder, births, log)
        self.put(folder, f"{OWN}\\Save 1\\Data\\Graves\\Virtual Villagers {number} Graves - Save 1.dat",
                 b"VCD1" + struct.pack("<3I", 1, number, 0))
        self.put(folder, f"{OWN}\\Save 1\\Data\\Paid Purchases\\Virtual Villagers {number} Paid Purchases - Save 1.dat",
                 b"VPP1" + struct.pack("<7I", 1, number, 1, 7, 0, 0, 0) + bytes(1024))
        self.put(folder, f"{OWN}\\Save 1\\Data\\Arrivals\\Virtual Villagers {number} Arrivals Recorded - Save 1.dat",
                 b"VCA1" + struct.pack("<4I", 2, number, 1, fnv(header)))
        self.put(folder, f"{OWN}\\Save 1\\Data\\Log Checks\\Virtual Villagers {number} Log Decisions - Save 1.json",
                 json.dumps({"version": 1, "decisions": [
                     {"kind": "x", "village": header}, {"kind": "y", "village": "Village: Other (Save 1)"}]},
                     indent=1).encode())
        # The save's own Like and Dislike Words: a boundary after the first record of the Births log.
        boundary = log.index(b"Village: Someone")
        self.put(folder, f"{OWN}\\Save 1\\Data\\Like and Dislike Words\\Virtual Villagers {number} Log Words.dat",
                 f"{boundary}\t{births}\r\n".encode())
        # The older layout: a log in "...Logs\Save 1", its boundary in the shared words file, a data file.
        deaths = f"{OLD_LOGS}\\Save 1\\Deaths and Disappearances\\Virtual Villagers {number} Deaths Log 1.txt"
        self.put(folder, deaths, f"{header}\r\nDeath 1\r\n".encode("latin-1"))
        self.put(folder, f"{OLD_DATA}\\Like and Dislike Words\\Virtual Villagers {number} Log Words.dat",
                 f"0\t{deaths}\r\n".encode())
        self.put(folder, f"{OLD_DATA}\\Custom Titles\\Custom Titles - Save 1.dat", b"VCT1" + bytes(12))
        self.put(folder, f"vvfp_masks_1.dat", b"legacy")
        tree = {"format": 1, "game": number, "slot": 1, "tribe": old, "edits": {}}
        self.put(folder, f"{TREES}\\{old} (Save 1) Family Tree.vvtree", json.dumps(tree, indent=1).encode())
        if number == 2:
            self.put(folder, f"{OWN}\\Save 1\\Data\\Elder Totems\\ElderTotems.dat",
                     totems.serialize(totems.Store(1, [("Ana", 1, 2, 0)], [], old)))
        if number == 3:
            self.put(folder, f"{OWN}\\Save 1\\Data\\Factions\\Virtual Villagers 3 Second Faction - Save 1.dat",
                     b"VV2F" + struct.pack("<4I", 2, 3, 1, 0) + bytes(16 * 24))
        # Another slot's files, which nothing may touch.
        self.put(folder, f"{OWN}\\Save 2\\Data\\Graves\\Virtual Villagers {number} Graves - Save 2.dat", b"slot two")
        self.put(folder, f"{OLD_DATA}\\Graves\\Virtual Villagers {number} Graves - Save 2.dat", b"slot two old")
        self.put(folder, "ldwLog.txt", b"engine")
        return game, folder, old

    def snapshot(self, folder: Path) -> dict[str, bytes]:
        return {p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*"))
                if p.is_file() and "Backups" not in p.relative_to(folder).parts}

    def backups(self, folder: Path) -> list[str]:
        place = folder / "Backups"
        return sorted(p.name for p in place.iterdir()) if place.is_dir() else []

    def occupy(self, game, folder: Path, slot: int, name: str) -> dict[str, bytes]:
        """Slot ``slot`` given a village of its own (``name``) with its logs and patcher files, in both
        layouts; returns those files' bytes."""
        number = game.number
        save = bytearray(fixture(f"vv{number}-huttest-1"))
        at = rename._save_layout(game, bytes(save))[0] + game.name_offset
        save = rename._with_name(bytes(save), at, game.save_field, name)
        header = f"Village: {name} (Save {slot})"
        files = {
            game.save_path(folder, slot).name: save,
            game.generation_path(folder, "2", slot).name: save,
            f"{OWN}\\Save {slot}\\Logs\\Births and Conceptions\\Virtual Villagers {number} Births and "
            f"Conceptions Log 1.txt": f"{header}\r\nConception 50\r\n  Mother: Old\r\n".encode(),
            f"{OWN}\\Save {slot}\\Data\\Graves\\Virtual Villagers {number} Graves - Save {slot}.dat": b"old graves",
            f"{OLD_LOGS}\\Save {slot}\\Deaths and Disappearances\\Virtual Villagers {number} Deaths Log 1.txt":
                f"{header}\r\nDeath 60\r\n".encode(),
            f"{OLD_DATA}\\Graves\\Virtual Villagers {number} Graves - Save {slot}.dat": b"older graves",
            f"{TREES}\\{name} (Save {slot}) Family Tree.vvtree":
                json.dumps({"format": 1, "game": number, "slot": slot, "tribe": name}).encode(),
        }
        for rel, data in files.items():
            self.put(folder, rel, data)
        return {Path(rel).as_posix().replace("\\", "/"): data for rel, data in files.items()}


class CopyTests(Base):
    def test_every_game_copies_the_village_and_its_files(self) -> None:
        for tag, number, suffix in CASES:
            with self.subTest(game=number, build=tag):
                game, folder, old = self.make(tag, number, suffix)
                before = self.snapshot(folder)
                result = cs.copy_slot(game, folder, 1, 3, "Copied Tribe", processes=FakeProcesses(), now=NOW)
                after = self.snapshot(folder)
                # The source and every other slot's files are untouched, byte for byte; only the slot
                # list and the shared words file (one line appended) changed among the files there before.
                index_name = game.index_path(folder).name
                shared = f"{OLD_DATA}/Like and Dislike Words/Virtual Villagers {number} Log Words.dat"
                for name, data in before.items():
                    if name in (index_name, shared):
                        continue
                    self.assertEqual(after[name], data, name)
                self.assertTrue(after[shared].startswith(before[shared]))
                new_index = after[index_name]
                for slot in (1, 2, 4, 5):
                    at = game.index_offset(slot)
                    self.assertEqual(new_index[at:at + game.index_stride],
                                     before[index_name][at:at + game.index_stride])
                self.assertEqual(rename.index_name(game, new_index, 3), "Copied Tribe")
                self.assertEqual(new_index[cs.FLAG_OFFSET[number] + 2], 1)
                self.assertEqual(len(new_index), len(before[index_name]))
                # The save and its generations, with the new name, read by the patcher's own readers.
                copy = game.save_path(folder, 3)
                self.assertEqual(rename.save_name(game, copy.read_bytes()), "Copied Tribe")
                self.assertEqual(backup.read_village_name(number, copy), "Copied Tribe")
                self.assertEqual(os.stat(copy).st_mtime_ns, OLD_TIME)
                for generation in rename.GENERATIONS:
                    self.assertEqual(rename.save_name(game, game.generation_path(folder, generation, 3).read_bytes()),
                                     "Copied Tribe")
                # The patcher's files, under Save 3, with the slot and village inside made Save 3's.
                new_header = "Village: Copied Tribe (Save 3)"
                births = folder / OWN / "Save 3" / "Logs" / "Births and Conceptions" / \
                    f"Virtual Villagers {number} Births and Conceptions Log 1.txt"
                text = births.read_text(encoding="latin-1")
                self.assertEqual(text.count(new_header), 2)
                self.assertIn("Village: Someone Else (Save 1)", text)      # another village: as it was
                self.assertNotIn(f"Village: {old} (Save 1)", text)
                words = (folder / OWN / "Save 3" / "Data" / "Like and Dislike Words" /
                         f"Virtual Villagers {number} Log Words.dat").read_text()
                offset, _, key = words.strip().partition("\t")
                self.assertEqual(key, f"{OWN}\\Save 3\\Logs\\Births and Conceptions\\"
                                      f"Virtual Villagers {number} Births and Conceptions Log 1.txt")
                self.assertEqual(int(offset), births.read_bytes().index(b"Village: Someone"))
                deaths_key = (f"{OLD_LOGS}\\Save 3\\Deaths and Disappearances\\"
                              f"Virtual Villagers {number} Deaths Log 1.txt")
                self.assertTrue(after[shared].endswith(f"0\t{deaths_key}\r\n".encode()))
                # Renumbered after the game's highest of each kind (Death 1 was the only one): Death 2.
                self.assertEqual((folder / deaths_key).read_bytes(), f"{new_header}\r\nDeath 2\r\n".encode())
                self.assertIn("Conception 3", text)
                self.assertIn("Conception 4", text)
                self.assertIn("Birth 4", text)
                paid = (folder / OWN / "Save 3" / "Data" / "Paid Purchases" /
                        f"Virtual Villagers {number} Paid Purchases - Save 3.dat").read_bytes()
                self.assertEqual(struct.unpack_from("<I", paid, 12)[0], 3)
                marker = (folder / OWN / "Save 3" / "Data" / "Arrivals" /
                          f"Virtual Villagers {number} Arrivals Recorded - Save 3.dat").read_bytes()
                self.assertEqual(struct.unpack_from("<2I", marker, 12), (3, fnv(new_header)))
                graves = folder / OWN / "Save 3" / "Data" / "Graves" / f"Virtual Villagers {number} Graves - Save 3.dat"
                self.assertEqual(graves.read_bytes(), before[f"{OWN}/Save 1/Data/Graves/Virtual Villagers {number} Graves - Save 1.dat"])
                self.assertEqual(os.stat(graves).st_mtime_ns, OLD_TIME)
                decisions = json.loads((folder / OWN / "Save 3" / "Data" / "Log Checks" /
                                        f"Virtual Villagers {number} Log Decisions - Save 3.json").read_text())
                self.assertEqual([d["village"] for d in decisions["decisions"]],
                                 [new_header, "Village: Other (Save 1)"])
                self.assertTrue((folder / OLD_DATA / "Custom Titles" / "Custom Titles - Save 3.dat").is_file())
                self.assertEqual((folder / "vvfp_masks_3.dat").read_bytes(), b"legacy")
                tree = json.loads((folder / TREES / "Copied Tribe (Save 3) Family Tree.vvtree").read_text())
                self.assertEqual((tree["slot"], tree["tribe"]), (3, "Copied Tribe"))
                self.assertFalse((folder / OWN / "Save 3" / "Data" / "Graves" /
                                  f"Virtual Villagers {number} Graves - Save 2.dat").exists())
                if number == 2:
                    store = totems.parse((folder / OWN / "Save 3" / "Data" / "Elder Totems" / "ElderTotems.dat").read_bytes())
                    self.assertEqual((store.slot, store.village), (3, "Copied Tribe"))
                if number == 3:
                    faction = (folder / OWN / "Save 3" / "Data" / "Factions" /
                               "Virtual Villagers 3 Second Faction - Save 3.dat").read_bytes()
                    self.assertEqual(struct.unpack_from("<I", faction, 12)[0], 3)
                # Backed up first, labelled and listed as such.
                self.assertTrue(result.backup.backup_folder.name.endswith("(before copy)"))
                listed = backup.list_backups(folder)
                self.assertEqual(len(listed), 1)
                self.assertTrue(listed[0].before_copy)
                self.assertTrue(listed[0].label.endswith("(before copy)"))
                # Every file made is new: nothing that was there before is in the list.
                for path in result.created:
                    self.assertNotIn(path.relative_to(folder).as_posix(), before)
                # The copy shows as a slot of its own; the empty slots are 4 and 5.
                slots = cs.read_slots(game, folder)
                self.assertEqual([(s.slot, s.name) for s in slots.sources], [(1, old), (3, "Copied Tribe")])
                self.assertEqual(slots.targets, [2, 4, 5])
                self._tmp.cleanup()
                self._tmp = tempfile.TemporaryDirectory()
                self.documents = Path(self._tmp.name) / "D"

    def test_an_occupied_target_is_overwritten_and_its_files_set_aside(self) -> None:
        """The owner: "I want the Copy Player slot to be able to overwrite existing slots"."""
        for number in (1, 2, 3, 4, 5):
            with self.subTest(game=number):
                game, folder, old = self.make("huttest", number, f"Modded {number}")
                theirs = self.occupy(game, folder, 2, "Old Village")
                before = self.snapshot(folder)
                result = cs.copy_slot(game, folder, 1, 2, "Copied", processes=FakeProcesses(), now=NOW)
                self.assertEqual(result.overwritten, "Old Village")
                aside = folder / "Backups" / "Replaced by copy 2026-10-31 12-00-00 - Save 2 - Old Village"
                self.assertEqual(result.set_aside, aside)
                # Every file of the old village is in the set-aside folder, byte for byte, its path kept.
                for rel, data in theirs.items():
                    self.assertEqual((aside / rel).read_bytes(), data, rel)
                # ...and gone from the slot: the copy is the source's village.
                self.assertEqual(rename.save_name(game, game.save_path(folder, 2).read_bytes()), "Copied")
                after = self.snapshot(folder)
                self.assertNotIn(f"{OLD_DATA}/Graves/Virtual Villagers {number} Graves - Save 2.dat", after)
                deaths = after[f"{OLD_LOGS}/Save 2/Deaths and Disappearances/Virtual Villagers {number} "
                               f"Deaths Log 1.txt"]                     # the copy's own (the source has one)
                self.assertNotIn(b"Old Village", deaths)
                self.assertIn(b"Village: Copied (Save 2)\r\nDeath 61\r\n", deaths)
                self.assertNotIn(f"{TREES}/Old Village (Save 2) Family Tree.vvtree", after)
                births = after[f"{OWN}/Save 2/Logs/Births and Conceptions/Virtual Villagers {number} Births and "
                               f"Conceptions Log 1.txt"].decode("latin-1")
                self.assertNotIn("Old Village", births)
                # The numbers the overwritten village used stay retired: the copy's come after them.
                self.assertIn("Conception 51", births)
                # The source is untouched; no other slot is touched.
                index_name = game.index_path(folder).name
                shared = f"{OLD_DATA}/Like and Dislike Words/Virtual Villagers {number} Log Words.dat"
                for name, data in before.items():
                    if name in theirs or "Save 2" in name or name in (index_name, shared):
                        continue
                    self.assertEqual(after.get(name), data, name)
                # The set-aside folder is never offered as a backup, and nothing reads it.
                self.assertEqual([b.path.name for b in backup.list_backups(folder)],
                                 ["Backup 2026-10-31 12-00-00 (before copy)"])
                import vv3_second_faction as faction
                self.assertFalse(any(aside in p.parents for p in faction._candidates(
                    folder, 2, game.save_path(folder, 2).name[:-len("2.ldw")])))
                self.assertFalse([r for r in backup.files_to_back_up(folder) if "Replaced by copy" in str(r)])
                self.assertIn(game.save_path(folder, 2), cs.slot_files(game, folder, 2))
                self.assertFalse([p for p in cs.slot_files(game, folder, 2) if "Backups" in p.parts])
                self.put(aside, "sentinel.txt", b"Death 999\r\n")
                self.assertEqual(cs.highest_numbers(folder)["Death"], 61)     # the copy's; never the set-aside

    def test_a_failure_after_the_set_aside_brings_the_old_village_back(self) -> None:
        for fail in (0, 2, 6):
            with self.subTest(after=fail):
                game, folder, _old = self.make("huttest", 2, f"Modded {fail}")
                self.occupy(game, folder, 2, "Old Village")
                before = self.snapshot(folder)
                times = {p: os.stat(folder / p).st_mtime_ns for p in before}
                with self.assertRaisesRegex(cs.CopyError, "everything it made was removed"):
                    cs.copy_slot(game, folder, 1, 2, "Copied", processes=FakeProcesses(), now=NOW, _fail_after=fail)
                self.assertEqual(self.snapshot(folder), before)
                self.assertEqual({p: os.stat(folder / p).st_mtime_ns for p in before}, times)
                aside = folder / "Backups" / "Replaced by copy 2026-10-31 12-00-00 - Save 2 - Old Village"
                self.assertFalse(aside.exists())

    def test_leftovers_of_an_empty_slot_are_set_aside(self) -> None:
        """An empty slot (no "<stem>N.ldw") whose earlier village left files, the other layout's
        counterparts of the copy's data files among them: set aside, listed, then the copy is made."""
        game, folder, _old = self.make("huttest", 1, "Modded")
        left = {
            f"{OWN}\\Save 4\\Data\\Graves\\Virtual Villagers 1 Graves - Save 4.dat": b"old village",
            f"{OLD_DATA}\\Custom Titles\\Custom Titles - Save 4.dat": b"VCT1 leftover",
            f"{OLD_DATA}\\Graves\\Virtual Villagers 1 Graves - Save 4.dat": b"older layout counterpart",
            "Virtual Villagers44.ldw": b"an older generation",
        }
        for rel, data in left.items():
            self.put(folder, rel, data)
        listed = {str(p.relative_to(folder)) for p in cs.slot_files(game, folder, 4)}
        self.assertEqual(listed, set(left))
        result = cs.copy_slot(game, folder, 1, 4, "Copied", processes=FakeProcesses(), now=NOW)
        self.assertIsNone(result.overwritten)
        for rel, data in left.items():
            self.assertEqual((result.set_aside / rel).read_bytes(), data)
        self.assertFalse((folder / OLD_DATA / "Graves" / "Virtual Villagers 1 Graves - Save 4.dat").exists())
        self.assertEqual(rename.save_name(game, (folder / "Virtual Villagers44.ldw").read_bytes()), "Copied")

    def test_the_slot_list_never_decides_whether_a_slot_is_empty(self) -> None:
        """The owner: "the game sees (game name)1-5.ldw as player slots"."""
        game, folder, old = self.make("huttest", 3, "Modded")
        index = bytearray(game.index_path(folder).read_bytes())
        # The list says slot 4 is in use (a name, its byte 1) and slot 1 is a New Player (byte 0).
        index[:] = rename._with_name(bytes(index), game.index_offset(4), game.index_stride, "Ghost")
        index[cs.FLAG_OFFSET[3] + 3] = 1
        index[:] = rename._with_name(bytes(index), game.index_offset(1), game.index_stride, "NEW PLAYER")
        index[cs.FLAG_OFFSET[3]] = 0
        game.index_path(folder).write_bytes(bytes(index))
        slots = cs.read_slots(game, folder)
        self.assertIn(4, slots.targets)
        self.assertEqual([s.slot for s in slots.sources], [1])
        cs.copy_slot(game, folder, 1, 4, "Copied", processes=FakeProcesses(), now=NOW)
        self.assertEqual(rename.save_name(game, game.save_path(folder, 4).read_bytes()), "Copied")

    def test_a_running_game_is_refused_before_the_backup(self) -> None:
        game, folder, _old = self.make("huttest", 5, "Modded")
        before = self.snapshot(folder)
        with self.assertRaisesRegex(cs.GameRunning, "is running"):
            cs.copy_slot(game, folder, 1, 3, "Copied", processes=FakeProcesses([4242]), now=NOW)
        self.assertEqual(self.snapshot(folder), before)
        self.assertEqual(self.backups(folder), [])

    def test_the_name_rule_is_the_games(self) -> None:
        game, folder, _old = self.make("huttest", 3, "Modded")
        before = self.snapshot(folder)
        for name in ("", "x" * 20, "NEW PLAYER"):
            with self.subTest(name=name), self.assertRaises(cs.CopyError):
                cs.copy_slot(game, folder, 1, 3, name, processes=FakeProcesses(), now=NOW)
        cs.copy_slot(game, folder, 1, 3, "x" * 19, processes=FakeProcesses(), now=NOW)
        self.assertEqual(rename.save_name(game, game.save_path(folder, 3).read_bytes()), "x" * 19)
        self.assertEqual(self.snapshot(folder)[game.save_path(folder, 1).name], before[game.save_path(folder, 1).name])

    def test_a_name_windows_refuses_in_a_file_name_still_copies_the_tree(self) -> None:
        """Codex, #657: "A/B" made a sub-folder and "A:B" an invalid file name that rolled the whole copy
        back.  The copied tree is named as the Family Tree Maker names it; inside, the name is as typed."""
        import vv_genealogy_window as gw
        for number, name in ((3, "A/B"), (4, "A:B"), (5, 'C*?"<>|\\D')):
            with self.subTest(name=name):
                game, folder, _old = self.make("huttest", number, "Modded")
                self.assertIsNone(rename.name_problem(game, name))
                cs.copy_slot(game, folder, 1, 3, name, processes=FakeProcesses(), now=NOW)
                expected = folder / TREES / gw.tree_file_name(name, 3)
                self.assertEqual(expected.parent, folder / TREES)
                self.assertNotIn("/", expected.name)
                self.assertNotIn(":", expected.name)
                tree = json.loads(expected.read_text(encoding="utf-8"))
                self.assertEqual((tree["slot"], tree["tribe"]), (3, name))
                self.assertEqual([p for p in (folder / TREES).iterdir() if p.is_dir()], [])
                self.assertEqual(rename.save_name(game, game.save_path(folder, 3).read_bytes()), name)

    def test_a_failure_part_way_leaves_no_partial_target(self) -> None:
        for number in (1, 2, 3, 4, 5):
            for fail in (0, 1, 3, 8):
                with self.subTest(game=number, after=fail):
                    game, folder, _old = self.make("huttest", number, f"Modded {number}{fail}")
                    before = self.snapshot(folder)
                    with self.assertRaisesRegex(cs.CopyError, "everything it made was removed"):
                        cs.copy_slot(game, folder, 1, 3, "Copied", processes=FakeProcesses(), now=NOW,
                                     _fail_after=fail)
                    self.assertEqual(self.snapshot(folder), before)
                    self.assertFalse((folder / OWN / "Save 3").exists())
                    self.assertFalse((folder / OLD_LOGS / "Save 3").exists())

    def test_a_failed_check_at_the_end_puts_everything_back(self) -> None:
        game, folder, _old = self.make("huttest", 1, "Modded")
        before = self.snapshot(folder)
        with mock.patch.object(cs, "verify", side_effect=cs.CopyError("does not read back")):
            with self.assertRaisesRegex(cs.CopyError, "everything it made was removed"):
                cs.copy_slot(game, folder, 1, 3, "Copied", processes=FakeProcesses(), now=NOW)
        # The slot list and the shared words file are as they were, every new file and folder gone.
        self.assertEqual(self.snapshot(folder), before)
        self.assertEqual(len(self.backups(folder)), 1)            # the backup is kept

    def test_an_unreadable_source_or_the_same_slot_is_refused(self) -> None:
        game, folder, _old = self.make("huttest", 2, "Modded")
        with self.assertRaisesRegex(cs.CopyError, "different slots"):
            cs.copy_slot(game, folder, 1, 1, "Copied", processes=FakeProcesses(), now=NOW)
        with self.assertRaisesRegex(cs.CopyError, "has no tribe"):
            cs.copy_slot(game, folder, 4, 3, "Copied", processes=FakeProcesses(), now=NOW)
        self.put(folder, game.save_path(folder, 5).name, b"ldwg not a save")
        with self.assertRaisesRegex(cs.CopyError, "not a .* save"):
            cs.copy_slot(game, folder, 5, 3, "Copied", processes=FakeProcesses(), now=NOW)
        self.assertEqual(self.backups(folder), [])


class PathTests(unittest.TestCase):
    def test_only_the_source_slots_files_are_copied(self) -> None:
        def t(rel: str):
            out = cs.target_relative(Path(rel), 1, 3)
            return None if out is None else "\\".join(out.parts)
        self.assertEqual(t(f"{OWN}\\Save 1\\Data\\Graves\\Virtual Villagers 1 Graves - Save 1.dat"),
                         f"{OWN}\\Save 3\\Data\\Graves\\Virtual Villagers 1 Graves - Save 3.dat")
        self.assertEqual(t(f"{OWN}\\Save 1\\Data\\Elder Totems\\ElderTotems.dat"),
                         f"{OWN}\\Save 3\\Data\\Elder Totems\\ElderTotems.dat")
        self.assertEqual(t(f"{OLD_LOGS}\\Save 1\\Tribe History\\Village History 1.txt"),
                         f"{OLD_LOGS}\\Save 3\\Tribe History\\Village History 1.txt")
        self.assertEqual(t(f"{OLD_DATA}\\Graves\\Virtual Villagers 1 Graves - Save 1.dat"),
                         f"{OLD_DATA}\\Graves\\Virtual Villagers 1 Graves - Save 3.dat")
        self.assertEqual(t("vv1_parents_1.dat"), "vv1_parents_3.dat")
        for rel in (f"{OWN}\\Save 2\\Data\\x - Save 2.dat", f"{OLD_DATA}\\Graves\\x - Save 2.dat",
                    f"{OLD_LOGS}\\Births and Conceptions\\Virtual Villagers 1 Births and Conceptions Log 1.txt",
                    f"{OLD_DATA}\\Copies Made Before Repairs\\x - Save 1.dat", f"{OWN}\\Save 1\\Data\\x - Save 1.dat.tmp",
                    "Virtual Villagers1.ldw", "Virtual Villagers0.ldw", "ldwLog.txt", "vv1_parents_2.dat",
                    "Backups\\Backup 1\\x - Save 1.dat"):
            self.assertIsNone(t(rel), rel)

    def test_log_offsets_follow_a_rewritten_line(self) -> None:
        data = b"Village: Ab (Save 1)\r\nx\r\nVillage: Ab (Save 1)\r\ny\r\n"
        out, mapping = cs.rewrite_log(data, {"Village: Ab (Save 1)"}, "Village: Longer Name (Save 3)")
        self.assertEqual(out, b"Village: Longer Name (Save 3)\r\nx\r\nVillage: Longer Name (Save 3)\r\ny\r\n")
        for marker in (b"x", b"y"):
            self.assertEqual(out[mapping.offset(data.index(marker)):][:1], marker)
        self.assertEqual(mapping.offset(0), 0)
        self.assertEqual(mapping.offset(len(data)), len(out))


class ConfirmationTests(Base):
    """The owner: "All 'Copy Player Slot' should have a confirmation prompt too" -- No (the default)
    writes nothing, not even the backup."""

    def _ask(self, answer: bool):
        calls = []

        def ask(parent, title, message):
            calls.append((title, message))
            return answer
        return ask, calls

    def test_no_writes_nothing(self) -> None:
        for target, occupied in ((3, False), (2, True)):
            with self.subTest(target=target):
                game, folder, old = self.make("huttest", 1, f"Modded {target}")
                if occupied:
                    self.occupy(game, folder, 2, "Old Village")
                before = self.snapshot(folder)
                ask, calls = self._ask(False)
                ran = []
                source = cs.read_slots(game, folder).sources[0]
                result = window.confirm_and_copy(ask, lambda work: ran.append(work), game, folder, source, target,
                                                 "Copied", processes=FakeProcesses(), now=NOW)
                self.assertIsNone(result)
                self.assertEqual(ran, [])
                self.assertEqual(self.snapshot(folder), before)
                self.assertEqual(self.backups(folder), [])
                self.assertEqual(len(calls), 1)

    def test_yes_backs_up_and_copies(self) -> None:
        game, folder, _old = self.make("huttest", 2, "Modded")
        ask, calls = self._ask(True)
        source = cs.read_slots(game, folder).sources[0]
        result = window.confirm_and_copy(ask, lambda work: work(), game, folder, source, 3, "Copied",
                                         processes=FakeProcesses(), now=NOW)
        self.assertEqual(result.new_name, "Copied")
        self.assertEqual(rename.save_name(game, game.save_path(folder, 3).read_bytes()), "Copied")
        self.assertEqual(len(self.backups(folder)), 1)

    def test_the_shared_words_are_pinned(self) -> None:
        """The words every patcher's Copy Player Slot shares, exactly."""
        game, folder, old = self.make("huttest", 1, "Modded")
        source = cs.read_slots(game, folder).sources[0]
        self.assertEqual(
            window.replace_text(folder, source, 2, "Old Village", "Copied", NOW),
            f"Save 2 holds the Old Village village. It will be replaced by a copy of {old} (Save 1), named "
            f"Copied. The whole save folder ({folder}) is backed up first, and Old Village's files are kept in "
            "Backups\\Replaced by copy 2026-10-31 12-00-00. Replace it?")
        self.assertEqual(
            window.empty_text(folder, source, 3, "Copied", NOW),
            f"Save 3 is empty. It will get a copy of {old} (Save 1), named Copied. The whole save folder "
            f"({folder}) is backed up first. Copy it?")
        leftover = folder / OWN / "Save 3" / "Data" / "x - Save 3.dat"
        self.assertEqual(
            window.empty_text(folder, source, 3, "Copied", NOW, [leftover]),
            f"Save 3 is empty. It will get a copy of {old} (Save 1), named Copied. The whole save folder "
            f"({folder}) is backed up first. Leftover files from an earlier village in Save 3 are kept in "
            "Backups\\Replaced by copy 2026-10-31 12-00-00.\n\n"
            f"  {OWN}\\Save 3\\Data\\x - Save 3.dat\n\nCopy it?")
        self.assertEqual(cs.BACKUP_LABEL, "(before copy)")
        self.assertEqual(cs.set_aside_folder(folder, NOW, 2, "Old Village").name,
                         "Replaced by copy 2026-10-31 12-00-00 - Save 2 - Old Village")
        self.assertEqual(window.TITLE, "Copy Player Slot")

    def test_the_prompt_names_the_leftovers_it_sets_aside(self) -> None:
        game, folder, _old = self.make("huttest", 1, "Modded")
        self.put(folder, f"{OWN}\\Save 3\\Data\\Graves\\Virtual Villagers 1 Graves - Save 3.dat", b"old")
        ask, calls = self._ask(False)
        source = cs.read_slots(game, folder).sources[0]
        window.confirm_and_copy(ask, lambda work: work(), game, folder, source, 3, "Copied", now=NOW)
        self.assertIn(f"{OWN}\\Save 3\\Data\\Graves\\Virtual Villagers 1 Graves - Save 3.dat", calls[0][1])
        self.assertIn("Leftover files from an earlier village in Save 3", calls[0][1])

    def test_the_window_asks_through_the_yes_no_question(self) -> None:
        source = (ROOT / "src" / "vv_copy_slot_window.py").read_text(encoding="utf-8")
        self.assertIn("confirm_and_copy(\n                ask_yes_no,", source)
        self.assertNotIn("vv_copy_slot.copy_slot(", source[source.index("def open_copy_slot("):])


def _tk_root():
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        return root
    except Exception:  # noqa: BLE001 -- no display (CI): the question's keys are not tested here
        return None


class YesNoKeyTests(unittest.TestCase):
    """No is the default; Return and Escape answer No; only Yes copies."""

    def setUp(self) -> None:
        self.root = _tk_root()
        if self.root is None:
            self.skipTest("no Tk display")

    def tearDown(self) -> None:
        self.root.destroy()

    def answer(self, act) -> bool:
        top, answer = window.build_yes_no(self.root, "Copy Player Slot", "Replace it?")
        self.root.update()
        act(top)
        self.root.update()
        return answer["yes"]

    def test_return_escape_and_closing_answer_no(self) -> None:
        self.assertFalse(self.answer(lambda top: top.event_generate("<Return>")))
        self.assertFalse(self.answer(lambda top: top.event_generate("<Escape>")))
        self.assertFalse(self.answer(lambda top: top.tk.eval(top.protocol("WM_DELETE_WINDOW"))))
        self.assertFalse(self.answer(lambda top: top.no_button.invoke()))
        self.assertTrue(self.answer(lambda top: top.yes_button.invoke()))

    def test_no_is_the_default_button(self) -> None:
        top, _answer = window.build_yes_no(self.root, "Copy Player Slot", "Replace it?")
        self.root.update()
        self.assertEqual(str(top.no_button.cget("default")), "active")
        top.destroy()


class RecordTests(Base):
    """The owner chose "Renumber the copy"; the older shared logs' records come along; nothing pending."""

    def test_records_are_renumbered_after_the_games_highest_and_references_follow(self) -> None:
        game, folder, old = self.make("huttest", 1, "Modded")
        header = f"Village: {old} (Save 1)"
        # Another slot already used Birth 10 and Repair 7: the copy's numbers come after the game's highest.
        self.put(folder, f"{OWN}\\Save 2\\Logs\\Births and Conceptions\\Virtual Villagers 1 Births and Conceptions "
                         f"Log 1.txt", b"Village: Other (Save 2)\r\nBirth 10\r\n")
        repairs = (f"{header}\r\nRepair 7\r\n  Checked: Death 1's cause of death\r\n  Answered: Birth 3 says Ana\r\n"
                   f"  Dislikes:Conception 1\r\n").encode()
        self.put(folder, f"{OWN}\\Save 1\\Logs\\Repairs Made\\Virtual Villagers 1 Repairs Log 1.txt", repairs)
        self.put(folder, f"{OWN}\\Save 1\\Logs\\Reconciliation\\Virtual Villagers 1 Reconciliation - Save 1.txt",
                 f"Virtual Villagers 1 (A New Home) -- read-only reconciliation\r\nSave 1: {old}\r\n"
                 f"  - Birth 3 says Ana\r\n".encode())
        decisions = f"{OWN}\\Save 1\\Data\\Log Checks\\Virtual Villagers 1 Log Decisions - Save 1.json"
        self.put(folder, decisions, json.dumps({"version": 1, "decisions": [
            {"kind": "answered", "village": header, "fact": "Birth 3 says Ana", "who": [["Death 1", 2]]}]},
            indent=1).encode())
        before = self.snapshot(folder)
        result = cs.copy_slot(game, folder, 1, 3, "Copied", processes=FakeProcesses(), now=NOW)
        self.assertEqual(result.renumbered, {"Conception": 2, "Birth": 1, "Death": 1, "Repair": 1})
        text = (folder / OWN / "Save 3" / "Logs" / "Repairs Made" / "Virtual Villagers 1 Repairs Log 1.txt").read_bytes()
        # Death 1 -> 2, Birth 3 -> 11 (after Birth 10), Repair 7 -> 8; a like/dislike word is no reference.
        self.assertEqual(text, b"Village: Copied (Save 3)\r\nRepair 8\r\n  Checked: Death 2's cause of death\r\n"
                               b"  Answered: Birth 11 says Ana\r\n  Dislikes:Conception 1\r\n")
        births = (folder / OWN / "Save 3" / "Logs" / "Births and Conceptions" /
                  "Virtual Villagers 1 Births and Conceptions Log 1.txt").read_bytes()
        self.assertIn(b"Conception 3\r\n", births)          # its first record, then the second, in order
        self.assertLess(births.index(b"Conception 3"), births.index(b"Conception 4"))
        recon = (folder / OWN / "Save 3" / "Logs" / "Reconciliation" /
                 "Virtual Villagers 1 Reconciliation - Save 3.txt").read_bytes()
        self.assertIn(b"\r\nSave 3: Copied\r\n", recon)
        self.assertIn(b"Birth 11 says", recon)
        doc = json.loads((folder / OWN / "Save 3" / "Data" / "Log Checks" /
                          "Virtual Villagers 1 Log Decisions - Save 3.json").read_text())
        self.assertEqual(doc["decisions"][0]["fact"], "Birth 11 says Ana")
        self.assertEqual(doc["decisions"][0]["who"], [["Death 2", 2]])
        # The words boundary still falls where it did in the record it marks.
        words = (folder / OWN / "Save 3" / "Data" / "Like and Dislike Words" /
                 "Virtual Villagers 1 Log Words.dat").read_text()
        self.assertEqual(int(words.split("\t")[0]), births.index(b"Village: Someone"))
        # The source's files are exactly as they were.
        after = self.snapshot(folder)
        for name in before:
            if "Save 1" in name:
                self.assertEqual(after[name], before[name], name)

    def test_the_village_s_records_in_the_older_shared_logs_come_along(self) -> None:
        game, folder, old = self.make("huttest", 1, "Modded")
        mine, theirs = f"Village: {old} (Save 1)", "Village: Neighbours (Save 2)"
        shared = (f"{mine}\r\nConception 5\r\n  Mother: Ana\r\n\r\n{theirs}\r\nConception 6\r\n  Mother: Bo\r\n\r\n"
                  f"{mine}\r\nBirth 7\r\n  Child: Cy\r\n").encode()
        rel = f"{OLD_LOGS}\\Births and Conceptions\\Virtual Villagers 1 Births and Conceptions Log 1.txt"
        self.put(folder, rel, shared)
        history = (f"=== Virtual Villagers -- 2026-10-01 ===\r\n{mine}\r\nAna\r\n\r\n"
                   f"=== Virtual Villagers -- 2026-10-02 ===\r\n{theirs}\r\nBo\r\n\r\n").encode()
        self.put(folder, f"{OLD_LOGS}\\Tribe History\\Village History 1.txt", history)
        self.put(folder, f"{OLD_DATA}\\Like and Dislike Words\\Virtual Villagers 1 Log Words.dat",
                 f"0\t{OLD_LOGS}\\Save 1\\Deaths and Disappearances\\Virtual Villagers 1 Deaths Log 1.txt\r\n"
                 f"{shared.index(theirs.encode())}\t{rel}\r\n".encode())
        before = self.snapshot(folder)
        cs.copy_slot(game, folder, 1, 3, "Copied", processes=FakeProcesses(), now=NOW)
        after = self.snapshot(folder)
        self.assertEqual(after[rel.replace("\\", "/")], shared)               # the shared log: untouched
        copy = after[f"{OLD_LOGS}/Save 3/Births and Conceptions/Virtual Villagers 1 Births and Conceptions Log 1.txt"]
        # The copy's records (Conception 1, 2 and 5; Birth 3 and 7) numbered after the game's highest (Conception
        # 6, Birth 7), in their own order: Conception 5 -> 9, Birth 7 -> 9.
        self.assertEqual(copy, b"Village: Copied (Save 3)\r\nConception 9\r\n  Mother: Ana\r\n\r\n"
                               b"Village: Copied (Save 3)\r\nBirth 9\r\n  Child: Cy\r\n")
        snap = after[f"{OLD_LOGS}/Save 3/Tribe History/Village History 1.txt"]
        self.assertEqual(snap, b"=== Virtual Villagers -- 2026-10-01 ===\r\nVillage: Copied (Save 3)\r\nAna\r\n\r\n")
        words = after[f"{OLD_DATA}/Like and Dislike Words/Virtual Villagers 1 Log Words.dat"]
        key = f"{OLD_LOGS}\\Save 3\\Births and Conceptions\\Virtual Villagers 1 Births and Conceptions Log 1.txt"
        # The shared file's boundary fell after the village's first record: in the copy, the same place.
        self.assertIn(f"{copy.index(b'Village: Copied (Save 3)', 1)}\t{key}\r\n".encode(), words)
        self.assertTrue(words.startswith(before[f"{OLD_DATA}/Like and Dislike Words/Virtual Villagers 1 Log Words.dat"]))

    def test_the_copy_reads_exactly_like_the_source_after_a_rename(self) -> None:
        """The live check (The Secret City, renamed "KT N" -> "Kalahuna Tribe 3: N"): the save-time reconcile
        counts only records under the CURRENT header, exactly (statistics_reconcile.inc), so an older name's
        header keeps its name in the copy -- only its slot changes -- and the rename note ends at the copy's
        name, so every reader follows the same chain."""
        import vv_log_additions as additions
        game, folder, old = self.make("huttest", 3, "Modded")
        deaths = f"{OWN}\\Save 1\\Logs\\Deaths and Disappearances\\Virtual Villagers 3 Deaths Log 1.txt"
        self.put(folder, deaths, (f"Village: KT N (Save 1)\r\nDeath 1\r\n  Grave: yes\r\n\r\n"
                                  f"Tribe renamed from KT N to {old} on 2026-10-01\r\n\r\n"
                                  f"Village: {old} (Save 1)\r\nDeath 2\r\n  Grave: yes\r\n").encode())
        cs.copy_slot(game, folder, 1, 3, "Copied", processes=FakeProcesses(), now=NOW)
        copy = (folder / OWN / "Save 3" / "Logs" / "Deaths and Disappearances" /
                "Virtual Villagers 3 Deaths Log 1.txt").read_bytes()
        self.assertEqual(copy, b"Village: KT N (Save 3)\r\nDeath 3\r\n  Grave: yes\r\n\r\n"
                               b"Tribe renamed from KT N to Copied on 2026-10-01\r\n\r\n"
                               b"Village: Copied (Save 3)\r\nDeath 4\r\n  Grave: yes\r\n")

        def exact(slot: int, header: str) -> int:
            """statistics_reconcile.inc rc_visit_deaths: Death records under the current header, exactly."""
            text = (folder / OWN / f"Save {slot}" / "Logs" / "Deaths and Disappearances" /
                    "Virtual Villagers 3 Deaths Log 1.txt").read_text(encoding="latin-1")
            ours, count = False, 0
            for line in text.splitlines():
                if line.startswith("Village:"):
                    ours = line == header
                elif ours and re.match(r"Death \d", line):
                    count += 1
            return count
        self.assertEqual(exact(1, f"Village: {old} (Save 1)"), exact(3, "Village: Copied (Save 3)"))
        self.assertEqual(exact(3, "Village: Copied (Save 3)"), 1)
        # The rename chain: the same older name, for the copy's slot.
        self.assertEqual(additions.current_villages(folder, 3, 1), {f"Village: {old} (Save 1)", "Village: KT N (Save 1)"})
        self.assertEqual(additions.current_villages(folder, 3, 3), {"Village: Copied (Save 3)", "Village: KT N (Save 3)"})

    def test_a_name_the_replaced_village_keeps_in_the_shared_logs_is_refused(self) -> None:
        """The older shared logs are never changed, so an overwritten village's records there stay under
        "<old name> (Save T)"; the copy may not take that name (or one its rename chain gives it), only
        when such records are there."""
        game, folder, old = self.make("huttest", 1, "Modded")
        self.occupy(game, folder, 2, "Old Village")
        shared = f"{OLD_LOGS}\\Births and Conceptions\\Virtual Villagers 1 Births and Conceptions Log 1.txt"
        self.put(folder, shared, (f"Village: {old} (Save 1)\r\nConception 1\r\n\r\n"
                                  "Village: Old Village (Save 2)\r\nConception 2\r\n\r\n"
                                  "Tribe renamed from Old Village to Later Name on 2026-10-01\r\n\r\n"
                                  "Village: Not Recorded (Save 2)\r\n\r\n"
                                  "Village: Other Slot (Save 4)\r\nConception 3\r\n").encode())
        self.assertEqual(cs.shared_log_names(folder, 2), {"Old Village", "Later Name"})
        before = self.snapshot(folder)
        for name in ("Old Village", "Later Name"):
            with self.subTest(name=name):
                with self.assertRaises(cs.CopyError) as caught:
                    cs.copy_slot(game, folder, 1, 2, name, processes=FakeProcesses(), now=NOW)
                self.assertEqual(str(caught.exception),
                                 f"{name} was the name of the village being replaced in Save 2, and its old "
                                 "records still use it. Please choose another name.")
                self.assertEqual(self.snapshot(folder), before)
                self.assertEqual(self.backups(folder), [])
        # A header with no record, another slot's name, or a name the shared logs never used: allowed.
        for name in ("Not Recorded", "Other Slot", "Brand New"):
            self.assertNotIn(name, cs.shared_log_names(folder, 2))
        cs.copy_slot(game, folder, 1, 2, "Brand New", processes=FakeProcesses(), now=NOW)
        self.assertEqual(rename.save_name(game, game.save_path(folder, 2).read_bytes()), "Brand New")
        self.assertEqual((folder / shared).read_bytes(), before[shared.replace("\\", "/")])

    def test_pieces_with_different_word_states_are_put_right_before_they_are_merged(self) -> None:
        """Codex, #665: a shared-log piece whose words are all the game's own (boundary 0) and the slot's
        older-layout log with no boundary (all old words) merged into one file would have one boundary for
        both.  Each piece's old words are put right first (the checker's own list), and the file gets 0."""
        game, folder, old = self.make("huttest", 1, "Modded")
        header = f"Village: {old} (Save 1)"
        name = "Virtual Villagers 1 Births and Conceptions Log 1.txt"
        shared = f"{OLD_LOGS}\\Births and Conceptions\\{name}"
        slot_log = f"{OLD_LOGS}\\Save 1\\Births and Conceptions\\{name}"
        self.put(folder, shared, f"{header}\r\nBirth 5\r\n  Child: Ana\r\n    Likes: rough wood\r\n".encode())
        self.put(folder, slot_log, f"{header}\r\nBirth 6\r\n  Child: Bo\r\n    Likes: heights\r\n".encode())
        words = f"{OLD_DATA}\\Like and Dislike Words\\Virtual Villagers 1 Log Words.dat"
        # The shared log: all the game's own words.  The slot's log: no line, so all old words ("heights" in
        # the old list is the game's "rough wood").
        self.put(folder, words, f"0\t{shared}\r\n".encode())
        cs.copy_slot(game, folder, 1, 3, "Copied", processes=FakeProcesses(), now=NOW)
        merged = (folder / OLD_LOGS / "Save 3" / "Births and Conceptions" / name).read_bytes()
        self.assertEqual(merged.count(b"Likes: rough wood"), 2)
        self.assertNotIn(b"heights", merged)
        key = f"{OLD_LOGS}\\Save 3\\Births and Conceptions\\{name}"
        lines = [l for l in (folder / words).read_bytes().decode().splitlines() if l.endswith("\t" + key)]
        self.assertEqual(lines[-1], f"0\t{key}")
        # The source's logs are as they were.
        self.assertIn(b"heights", (folder / slot_log).read_bytes())

    def test_a_tribe_named_like_a_record_keeps_its_name(self) -> None:
        """Codex, #665: a new name like "Birth 3" is an identity, never a record reference -- in the
        decisions' village, the logs' headers, rename notes and the reconciliation report."""
        game, folder, old = self.make("huttest", 1, "Modded")
        header = f"Village: {old} (Save 1)"
        repairs = f"{OWN}\\Save 1\\Logs\\Repairs Made\\Virtual Villagers 1 Repairs Log 1.txt"
        self.put(folder, repairs, (f"{header}\r\nRepair 1\r\n  Checked: Birth 3\r\n\r\n"
                                   "Village: Death 1 (Save 1)\r\n").encode())
        decisions = f"{OWN}\\Save 1\\Data\\Log Checks\\Virtual Villagers 1 Log Decisions - Save 1.json"
        self.put(folder, decisions, json.dumps({"version": 1, "decisions": [
            {"kind": "answered", "village": header, "fact": "Birth 3 says Ana"}]}, indent=1).encode())
        cs.copy_slot(game, folder, 1, 3, "Birth 3", processes=FakeProcesses(), now=NOW)
        doc = json.loads((folder / OWN / "Save 3" / "Data" / "Log Checks" /
                          "Virtual Villagers 1 Log Decisions - Save 3.json").read_text())
        self.assertEqual(doc["decisions"][0]["village"], "Village: Birth 3 (Save 3)")
        self.assertEqual(doc["decisions"][0]["fact"], "Birth 4 says Ana")         # the record: renumbered
        text = (folder / OWN / "Save 3" / "Logs" / "Repairs Made" / "Virtual Villagers 1 Repairs Log 1.txt").read_bytes()
        self.assertEqual(text, b"Village: Birth 3 (Save 3)\r\nRepair 2\r\n  Checked: Birth 4\r\n\r\n"
                               b"Village: Death 1 (Save 1)\r\n")
        births = (folder / OWN / "Save 3" / "Logs" / "Births and Conceptions" /
                  "Virtual Villagers 1 Births and Conceptions Log 1.txt").read_bytes()
        self.assertEqual(births.count(b"Village: Birth 3 (Save 3)"), 2)
        self.assertEqual(cs.note_rewrite(f"Tribe renamed from Birth 3 to {old} on 2026-10-01", old, "Death 1", 1, 3),
                         "Tribe renamed from Birth 3 to Death 1 on 2026-10-01")
        out, _map = cs.rewrite_log(b"Tribe renamed from Birth 3 to Other on 2026-10-01\r\nSave 1: Birth 3\r\n",
                                   {}, "x", {"Birth": {3: 9}})
        self.assertEqual(out, b"Tribe renamed from Birth 3 to Other on 2026-10-01\r\nSave 1: Birth 3\r\n")

    def test_a_source_s_older_name_the_replaced_village_used_refuses_the_slot(self) -> None:
        """The source's older names keep their headers in the copy, as "(Save T)": when the target slot's
        earlier village has records in the shared logs under one of them, the copy cannot go there."""
        game, folder, old = self.make("huttest", 3, "Modded")
        self.put(folder, f"{OWN}\\Save 1\\Logs\\Deaths and Disappearances\\Virtual Villagers 3 Deaths Log 1.txt",
                 (f"Village: KT N (Save 1)\r\nDeath 1\r\n\r\n"
                  f"Tribe renamed from KT N to {old} on 2026-10-01\r\n").encode())
        self.occupy(game, folder, 2, "Old Village")
        shared = f"{OLD_LOGS}\\Deaths and Disappearances\\Virtual Villagers 3 Deaths Log 1.txt"
        self.put(folder, shared, b"Village: KT N (Save 2)\r\nDeath 9\r\n")
        before = self.snapshot(folder)
        with self.assertRaises(cs.CopyError) as caught:
            cs.copy_slot(game, folder, 1, 2, "Copied", processes=FakeProcesses(), now=NOW)
        self.assertEqual(str(caught.exception),
                         f"{old}'s older name KT N was also used by the village being replaced in Save 2, and its "
                         "old records still use it, so the copy can't go into Save 2. Choose another slot.")
        self.assertEqual(self.snapshot(folder), before)
        self.assertEqual(self.backups(folder), [])
        # Another slot, whose earlier villages never used that name: copied.
        cs.copy_slot(game, folder, 1, 3, "Copied", processes=FakeProcesses(), now=NOW)
        self.assertEqual(rename.save_name(game, game.save_path(folder, 3).read_bytes()), "Copied")

    def test_the_window_says_why_the_name_is_refused(self) -> None:
        source = (ROOT / "src" / "vv_copy_slot_window.py").read_text(encoding="utf-8")
        self.assertIn("name in taken_names(target)", source)
        self.assertIn("vv_copy_slot.name_taken_message(name, target)", source)

    def test_pending_repairs_and_set_aside_clutter_are_not_copied(self) -> None:
        game, folder, _old = self.make("huttest", 1, "Modded")
        for rel in (f"{OWN}\\Save 1\\Data\\Log Checks\\Virtual Villagers 1 Repair Approved - Save 1.dat",
                    f"{OLD_DATA}\\Cross-Check\\Virtual Villagers 1 Repair Approved - Save 1.dat",
                    f"{OWN}\\Save 1\\Data\\Graves\\Virtual Villagers 1 Graves - Save 1.dat.another-village-1-0",
                    f"{OWN}\\Save 1\\Data\\Graves\\Virtual Villagers 1 Graves - Save 1.dat.unreadable-2",
                    f"{OLD_DATA}\\Virtual Villagers 1 Parentage Records - Save 1.dat.before-repair",
                    f"{TREES}\\Reports\\Virtual Villagers 1 Genealogy - Save 1.txt",
                    f"{TREES}\\Virtual Villagers 1 Village Matchmaker - Save 1.txt"):
            self.put(folder, rel, b"VRA1" + struct.pack("<3I", 1, 1, 1))
        result = cs.copy_slot(game, folder, 1, 3, "Copied", processes=FakeProcesses(), now=NOW)
        made = [str(p.relative_to(folder)) for p in result.created]
        for word in ("Repair Approved", "another-village", "unreadable", "before-repair", "Genealogy",
                     "Matchmaker"):
            self.assertFalse([m for m in made if word in m], word)


class GuiWiringTests(unittest.TestCase):
    SOURCE = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")

    def test_the_tools_tab_has_the_button_and_its_question_mark(self) -> None:
        body = self.SOURCE[self.SOURCE.index("    def _build_tools_tab("):]
        body = body[:body.index("\n    def _mode(")]
        self.assertIn('"Copy Player Slot...", self._copy_single_slot', body)
        self.assertIn('text="Copy Player Slot...",', body)
        self.assertEqual(body.count('_help_button(slot_links, "copy_player_slot")'), 1)
        self.assertEqual(body.count('_help_button(slot_tools, "copy_player_slot")'), 1)
        self.assertIn("vv_copy_slot_window.open_copy_slot(self, None)", body)

    def test_the_window_follows_the_dialog_conventions(self) -> None:
        source = (ROOT / "src" / "vv_copy_slot_window.py").read_text(encoding="utf-8")
        self.assertIn("scrollable_frame(dialog", source)          # the page-height guard's scrolled page
        self.assertIn("dialog.grab_set()", source)                # _hold, the patcher's grab
        self.assertIn("_regrab(dialog)", source)
        self.assertIn("app._run_with_wait(", source)              # the copy runs off the main thread


if __name__ == "__main__":
    unittest.main()
