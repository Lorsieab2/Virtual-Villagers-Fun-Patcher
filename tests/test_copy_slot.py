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
                self.assertEqual((folder / deaths_key).read_bytes(), f"{new_header}\r\nDeath 1\r\n".encode())
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

    def test_an_occupied_target_is_refused_and_nothing_is_written(self) -> None:
        game, folder, _old = self.make("huttest", 4, "Modded")
        self.put(folder, game.save_path(folder, 2).name, fixture("vv4-huttest-1"))
        before = self.snapshot(folder)
        with self.assertRaisesRegex(cs.CopyError, "Save 2 is in use"):
            cs.copy_slot(game, folder, 1, 2, "Copied", processes=FakeProcesses(), now=NOW)
        self.assertEqual(self.snapshot(folder), before)
        self.assertEqual(self.backups(folder), [])

    def test_a_target_whose_patcher_files_are_there_is_refused(self) -> None:
        game, folder, _old = self.make("huttest", 1, "Modded")
        self.put(folder, f"{OWN}\\Save 4\\Data\\Graves\\Virtual Villagers 1 Graves - Save 4.dat", b"old village")
        before = self.snapshot(folder)
        with self.assertRaisesRegex(cs.CopyError, "already keeps files for it"):
            cs.copy_slot(game, folder, 1, 4, "Copied", processes=FakeProcesses(), now=NOW)
        self.assertEqual(self.snapshot(folder), before)
        self.assertEqual(self.backups(folder), [])

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

        def ask(title, message, **kwargs):
            calls.append((title, message, kwargs))
            return answer
        return ask, calls

    def test_no_writes_nothing_and_is_the_default(self) -> None:
        game, folder, old = self.make("huttest", 1, "Modded")
        before = self.snapshot(folder)
        ask, calls = self._ask(False)
        ran = []
        source = cs.read_slots(game, folder).sources[0]
        result = window.confirm_and_copy(ask, lambda work: ran.append(work), game, folder, source, 3, "Copied",
                                         processes=FakeProcesses())
        self.assertIsNone(result)
        self.assertEqual(ran, [])
        self.assertEqual(self.snapshot(folder), before)
        self.assertEqual(self.backups(folder), [])
        title, message, kwargs = calls[0]
        self.assertEqual(kwargs["default"], "no")       # Enter never copies
        for part in (old, "Save 1", "Save 3", "Copied", folder.name, "(before copy)", "backed up first"):
            self.assertIn(part, message)

    def test_yes_backs_up_and_copies(self) -> None:
        game, folder, _old = self.make("huttest", 2, "Modded")
        ask, calls = self._ask(True)
        source = cs.read_slots(game, folder).sources[0]
        result = window.confirm_and_copy(ask, lambda work: work(), game, folder, source, 3, "Copied",
                                         processes=FakeProcesses())
        self.assertEqual(result.new_name, "Copied")
        self.assertEqual(calls[0][2]["default"], "no")
        self.assertEqual(rename.save_name(game, game.save_path(folder, 3).read_bytes()), "Copied")
        self.assertEqual(len(self.backups(folder)), 1)

    def test_the_window_asks_through_the_confirmation_with_no_as_default(self) -> None:
        source = (ROOT / "src" / "vv_copy_slot_window.py").read_text(encoding="utf-8")
        self.assertIn('default="no"', source)
        self.assertIn("confirm_and_copy(\n                messagebox.askyesno,", source)
        self.assertNotIn("vv_copy_slot.copy_slot(", source[source.index("def open_copy_slot("):])


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
