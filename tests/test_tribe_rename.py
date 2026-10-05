"""Rename Tribe: change a tribe's name inside a closed game's saves.

The owner's request: "a 'Rename Tribe' feature to the patcher. Just renames
the savefile internally. (Conforming to the natural character limit)", for all
five games and every Modded variant, including "- Modded 256".

The fixture saves in tests/fixtures/rename_tribe are real saves from the test
villages (gzip-compressed): each game's slot 1 and slot list, the 256
Villagers builds of The Secret City, The Tree of Life and New Believers, and
an older Tree of Life save with the 12-byte header. Every test copies them
into a throwaway Documents folder; nothing here reads or writes outside it,
and no game is ever started (the process list is a fake).
"""
from __future__ import annotations

import gzip
import os
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_save_backup as backup  # noqa: E402
import vv_tribe_rename as rename  # noqa: E402
from vv_fun_patcher import load_builds  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "rename_tribe"
NOW = datetime(2026, 10, 4, 15, 30, 0)

# (fixture tag, game number, folder suffix, slot the fixture save is copied to)
CASES = [
    ("huttest", 1, "Modded", 1),
    ("huttest", 2, "Modded", 1),
    ("huttest", 3, "Modded", 1),
    ("huttest", 4, "Modded", 1),
    ("huttest", 5, "Modded", 1),
    ("256", 3, "Modded 256", 1),
    ("256", 4, "Modded 256", 1),
    ("256", 5, "Modded 256", 1),
]


def fixture(name: str) -> bytes:
    return gzip.decompress((FIXTURES / f"{name}.ldw.gz").read_bytes())


class FakeProcesses:
    def __init__(self, pids=(), error=None, start_after=None):
        self.pids = list(pids)
        self.error = error
        self.calls = 0
        self.start_after = start_after   # the game "starts" after this many checks

    def find(self, exe_name):
        self.calls += 1
        if self.error is not None:
            raise self.error
        if self.start_after is not None and self.calls > self.start_after:
            return [4242]
        return list(self.pids)

    def suspend(self, pid, exe_name):  # pragma: no cover - never used
        raise AssertionError("Rename Tribe must never pause a game")

    def resume(self, handle):  # pragma: no cover - never used
        raise AssertionError("Rename Tribe must never pause a game")


class SaveFolderTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.documents = Path(self._tmp.name) / "Documents"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def make_folder(self, tag: str, number: int, suffix: str, slot: int = 1,
                    generations: bool = True) -> tuple[rename.GameSaves, Path]:
        game = rename.GAMES[number - 1]
        folder = self.documents / "LDW" / f"{game.title} - {suffix}"
        folder.mkdir(parents=True)
        save = fixture(f"vv{number}-{tag}-1")
        game.save_path(folder, slot).write_bytes(save)
        if generations:
            for generation in rename.GENERATIONS:
                game.generation_path(folder, generation, slot).write_bytes(save)
        index = bytearray(fixture(f"vv{number}-{tag}-0"))
        if slot != 1:
            # Put the fixture's slot-1 entry where this test's slot is.
            one = game.index_offset(1)
            other = game.index_offset(slot)
            stride = game.index_stride
            index[other:other + stride] = index[one:one + stride]
            empty = rename.EMPTY_SLOT.encode() + b"\0" * (stride - len(rename.EMPTY_SLOT))
            index[one:one + stride] = empty
        game.index_path(folder).write_bytes(bytes(index))
        return game, folder

    def snapshot(self, folder: Path) -> dict[str, bytes]:
        return {
            path.relative_to(folder).as_posix(): path.read_bytes()
            for path in sorted(folder.rglob("*"))
            if path.is_file() and "Backups" not in path.relative_to(folder).parts
        }


# ---------------------------------------------------------------------------
# The fixtures and the table
# ---------------------------------------------------------------------------


class LayoutTests(unittest.TestCase):
    def test_the_table_covers_every_game_the_patcher_builds(self) -> None:
        self.assertEqual(
            [game.title for game in rename.GAMES],
            [build.title for build in load_builds()],
        )

    def test_the_name_offsets_are_the_log_headers_own(self) -> None:
        source = (ROOT / "native" / "shared" / "village_identity.c").read_text(encoding="utf-8")
        table = re.search(r"NAME_OFFSETS\[5\] = \{(.*?)\};", source, re.S).group(1)
        offsets = [int(value, 16) for value in re.findall(r"0x([0-9A-F]+)u", table)]
        self.assertEqual(offsets, [game.name_offset for game in rename.GAMES])

    def test_the_buffer_lengths_are_the_save_resets_own(self) -> None:
        source = (ROOT / "native" / "save_reset_export" / "save_reset_export.c").read_text(encoding="utf-8")
        stock = re.search(r"SAVE_BUFFER_BYTES\[5\] = \{(.*?)\};", source, re.S).group(1)
        stock_lengths = [int(value, 16) for value in re.findall(r"0x([0-9A-F]+)u", stock)]
        self.assertEqual(stock_lengths, [game.buffers[0] for game in rename.GAMES])
        for number in (3, 4, 5):
            long = int(re.search(rf"#define VV{number}_256_SAVE_BUFFER_BYTES 0x([0-9A-F]+)u", source).group(1), 16)
            self.assertIn(long, rename.GAMES[number - 1].buffers)

    def test_every_fixture_save_reads_its_tribe(self) -> None:
        for tag, number, _suffix, _slot in CASES:
            with self.subTest(game=number, fixture=tag):
                game = rename.GAMES[number - 1]
                self.assertEqual(
                    rename.save_name(game, fixture(f"vv{number}-{tag}-1")),
                    rename.index_name(game, fixture(f"vv{number}-{tag}-0"), 1),
                )
                self.assertTrue(rename.save_name(game, fixture(f"vv{number}-{tag}-1")).startswith("Kalahuna Tribe"))

    def test_an_older_tree_of_life_save_with_a_12_byte_header_reads(self) -> None:
        game = rename.GAMES[3]
        data = fixture("vv4-legacy-2")
        self.assertEqual(len(data), 12 + 0x1710C)
        self.assertEqual(rename.save_name(game, data), "KFT 4")

    def test_another_games_save_is_not_read_as_this_ones(self) -> None:
        for tag, number, _suffix, _slot in CASES:
            data = fixture(f"vv{number}-{tag}-1")
            for other in rename.GAMES:
                if other.number != number:
                    with self.subTest(save=number, read_as=other.number, fixture=tag):
                        self.assertIsNone(rename.save_name(other, data))

    def test_a_damaged_save_is_not_read(self) -> None:
        game = rename.GAMES[0]
        data = fixture("vv1-huttest-1")
        self.assertIsNone(rename.save_name(game, b"XXXX" + data[4:]))
        self.assertIsNone(rename.save_name(game, data[:-1]))
        self.assertIsNone(rename.save_name(game, data + b"\0"))


# ---------------------------------------------------------------------------
# The name rule
# ---------------------------------------------------------------------------


class NameRuleTests(unittest.TestCase):
    def test_the_limits_are_each_games_own(self) -> None:
        # What each game's own name entry stores: GetText(buffer, 32 or 20)
        # keeps one character fewer than the entry lets you type.
        self.assertEqual([game.max_length for game in rename.GAMES], [31, 31, 19, 19, 19])
        for game in rename.GAMES:
            with self.subTest(game=game.number):
                # The name and its terminator fit both fields it is written to.
                self.assertLessEqual(game.max_length + 1, game.index_stride)
                self.assertLessEqual(game.max_length + 1, game.save_field)

    def test_the_longest_allowed_name_is_accepted_and_one_more_refused(self) -> None:
        for game in rename.GAMES:
            with self.subTest(game=game.number):
                self.assertIsNone(rename.name_problem(game, "N" * game.max_length))
                problem = rename.name_problem(game, "N" * (game.max_length + 1))
                self.assertIsNotNone(problem)
                self.assertIn(str(game.max_length), problem)

    def test_characters_the_game_cannot_take_are_refused(self) -> None:
        game = rename.GAMES[0]
        for name in ("Tab\tTribe", "Caf\u00e9", "Line\nBreak", "\u4e00", "Nul\0"):
            with self.subTest(name=name):
                self.assertIsNotNone(rename.name_problem(game, name))

    def test_printable_punctuation_and_digits_are_allowed(self) -> None:
        game = rename.GAMES[4]
        for name in ("Testificate!!!", "HeathenParentSave1", "Poop", "A-B_C (2) #~"):
            with self.subTest(name=name):
                self.assertIsNone(rename.name_problem(game, name))

    def test_characters_the_first_two_games_cannot_draw_are_refused_there_only(self) -> None:
        for character in "#$%&()*+;<=>@[\\]^_{}|~":
            with self.subTest(character=character):
                for game in rename.GAMES[:2]:
                    self.assertIsNotNone(rename.name_problem(game, f"Tribe {character}"))
                for game in rename.GAMES[2:]:
                    self.assertIsNone(rename.name_problem(game, f"Tribe {character}"))
        for game in rename.GAMES[:2]:
            self.assertIsNone(rename.name_problem(game, "Test!!! 1.0, 'B' - \"C\"?/:"))

    def test_spaces_are_kept_as_the_game_keeps_them(self) -> None:
        game = rename.GAMES[2]
        for name in (" Lead", "Trail ", "Two  Spaces"):
            with self.subTest(name=name):
                self.assertIsNone(rename.name_problem(game, name))

    def test_empty_blank_and_empty_slot_names_are_refused(self) -> None:
        game = rename.GAMES[2]
        for name in ("", " ", "   ", "NEW PLAYER"):
            with self.subTest(name=name):
                self.assertIsNotNone(rename.name_problem(game, name))
        # The game compares with "NEW PLAYER" exactly; other casings are names.
        self.assertIsNone(rename.name_problem(game, "New Player"))

    def test_a_too_long_name_is_refused_and_never_truncated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "LDW" / "Virtual Villagers - The Secret City - Modded"
            folder.mkdir(parents=True)
            game = rename.GAMES[2]
            game.save_path(folder, 1).write_bytes(fixture("vv3-huttest-1"))
            game.index_path(folder).write_bytes(fixture("vv3-huttest-0"))
            before = {p.name: p.read_bytes() for p in folder.iterdir()}
            with self.assertRaises(rename.RenameError):
                rename.rename_tribe(game, folder, 1, "X" * 21, FakeProcesses(), NOW)
            self.assertEqual({p.name: p.read_bytes() for p in folder.iterdir()}, before)


class SlotButtonWidthTests(unittest.TestCase):
    """The Change Tribe slot buttons cut long names short on screen.

    Measured live on test copies: A New Home's button kept the typed
    "abcdefghijklmnopqrt" (180 px) and dropped the "s" of "...qrs" (182 px);
    The Secret City's kept "abcdefghijklmr" (130 px) and dropped the "n" of
    "...lmn" (134 px). Both games' first-tribe dialogs stored 31 and 19
    characters with no width cap, so a wide name is one the games make
    themselves: it is allowed, and the window only notes the shortened display.
    """

    def test_the_buttons_are_181_and_130_pixels(self) -> None:
        self.assertEqual([rename.slot_button_width(game) for game in rename.GAMES], [181, 181, 130, 130, 130])

    def test_the_live_measurements(self) -> None:
        vv1, vv3 = rename.GAMES[0], rename.GAMES[2]
        self.assertEqual(rename.text_width(vv1, "abcdefghijklmnopqrt"), 180)
        self.assertEqual(rename.text_width(vv1, "abcdefghijklmnopqrs"), 182)
        self.assertFalse(rename.shown_shortened(vv1, "abcdefghijklmnopqrt"))
        self.assertTrue(rename.shown_shortened(vv1, "abcdefghijklmnopqrs"))
        self.assertEqual(rename.text_width(vv3, "abcdefghijklmr"), 130)
        self.assertFalse(rename.shown_shortened(vv3, "abcdefghijklmr"))
        self.assertTrue(rename.shown_shortened(vv3, "abcdefghijklmn"))
        # What the screens showed for the renamed tribes.
        self.assertFalse(rename.shown_shortened(vv1, "Live Rename Test T"))
        self.assertTrue(rename.shown_shortened(vv1, "Live Rename Test Tr"))
        self.assertFalse(rename.shown_shortened(vv3, "Secret City Re"))
        self.assertTrue(rename.shown_shortened(vv3, "Secret City Ren"))

    def test_a_wide_name_is_still_allowed(self) -> None:
        for game in rename.GAMES:
            with self.subTest(game=game.number):
                name = "W" * game.max_length
                self.assertTrue(rename.shown_shortened(game, name))
                self.assertIsNone(rename.name_problem(game, name))

    STOCK = ROOT / "research" / "stock-executables"
    TABLES = {1: ("A New Home", 0x486888, 1), 2: ("The Lost Children", 0x4958A8, 1),
              3: ("The Secret City", 0x4A6A80, 0), 4: ("The Tree of Life", 0x4BA140, 0),
              5: ("New Believers", 0x4C7FE0, 0)}

    @unittest.skipUnless((ROOT / "research" / "stock-executables").is_dir(), "stock executables not present")
    def test_the_widths_are_the_executables_glyph_tables(self) -> None:
        import struct
        for number, (short, va, spacing) in self.TABLES.items():
            with self.subTest(game=number):
                exe = (self.STOCK / f"Virtual Villagers - {short}.exe").read_bytes()
                pe = struct.unpack_from("<I", exe, 0x3C)[0]
                sections = struct.unpack_from("<H", exe, pe + 6)[0]
                optional = struct.unpack_from("<H", exe, pe + 20)[0]
                base = struct.unpack_from("<I", exe, pe + 24 + 28)[0]
                table = pe + 24 + optional
                offset = None
                for index in range(sections):
                    vsize, vaddr, rsize, raw = struct.unpack_from("<IIII", exe, table + 40 * index + 8)
                    if vaddr <= va - base < vaddr + max(vsize, rsize):
                        offset = va - base - vaddr + raw
                self.assertIsNotNone(offset)
                glyphs = {}
                first = None
                while True:
                    code, left, _top, right, _bottom = struct.unpack_from("<5i", exe, offset)
                    if code == 0:
                        break
                    first = right - left if first is None else first
                    glyphs.setdefault(code & 0xFF if code < 0 else code, right - left)
                    offset += 20
                game = rename.GAMES[number - 1]
                for code in range(0x20, 0x7F):
                    self.assertEqual(
                        rename.text_width(game, chr(code)), glyphs.get(code, first), repr(chr(code))
                    )
                self.assertEqual(rename._font(game)[1], spacing)


# ---------------------------------------------------------------------------
# Round trips on every game
# ---------------------------------------------------------------------------


class RoundTripTests(SaveFolderTest):
    def test_every_game_and_variant_renames_only_the_name(self) -> None:
        for tag, number, suffix, slot in CASES + [("huttest", 1, "Modded", 3), ("huttest", 5, "Modded", 5)]:
            with self.subTest(game=number, fixture=tag, slot=slot):
                self.tearDown()
                self.setUp()
                game, folder = self.make_folder(tag, number, suffix, slot)
                before = self.snapshot(folder)
                old = rename.save_name(game, before[game.save_path(folder, slot).name])
                new = "R" * game.max_length
                result = rename.rename_tribe(game, folder, slot, new, FakeProcesses(), NOW)
                self.assertEqual((result.old_name, result.new_name), (old, new))
                after = self.snapshot(folder)
                self.assertEqual(set(after), set(before), "no file added or removed")
                for name in (
                    game.save_path(folder, slot).name,
                    *(game.generation_path(folder, g, slot).name for g in rename.GENERATIONS),
                ):
                    old_bytes, new_bytes = before[name], after[name]
                    self.assertEqual(len(new_bytes), len(old_bytes))
                    self.assertEqual(rename.save_name(game, new_bytes), new)
                    header = len(old_bytes) - next(
                        length for length in game.buffers if len(old_bytes) - length in game.headers
                    )
                    start = header + game.name_offset
                    end = start + game.save_field
                    self.assertEqual(new_bytes[:start], old_bytes[:start], "nothing before the name")
                    self.assertEqual(new_bytes[end:], old_bytes[end:], "nothing after the name field")
                    self.assertEqual(new_bytes[start:end], new.encode() + b"\0" * (game.save_field - len(new)))
                index_old = before[game.index_path(folder).name]
                index_new = after[game.index_path(folder).name]
                for other in rename.SLOTS:
                    expected = new if other == slot else rename.index_name(game, index_old, other)
                    self.assertEqual(rename.index_name(game, index_new, other), expected)
                start = game.index_offset(slot)
                end = start + game.index_stride
                self.assertEqual(index_new[:start], index_old[:start])
                self.assertEqual(index_new[end:], index_old[end:])
                self.assertEqual([info.name for info in rename.read_slots(game, folder) if info.slot == slot], [new])

    def test_renaming_back_gives_the_original_name_and_every_other_byte(self) -> None:
        game, folder = self.make_folder("huttest", 2, "Modded")
        save = game.save_path(folder, 1)
        original = save.read_bytes()
        rename.rename_tribe(game, folder, 1, "Short", FakeProcesses(), NOW)
        rename.rename_tribe(game, folder, 1, "Kalahuna Tribe 2", FakeProcesses(), NOW)
        renamed = save.read_bytes()
        self.assertEqual(rename.save_name(game, renamed), "Kalahuna Tribe 2")
        start = 12 + game.name_offset
        self.assertEqual(renamed[:start], original[:start])
        self.assertEqual(renamed[start + game.save_field:], original[start + game.save_field:])

    def test_a_generation_holding_another_village_is_left_alone(self) -> None:
        game, folder = self.make_folder("huttest", 1, "Modded")
        other = rename._with_name(fixture("vv1-huttest-1"), 12 + 8, 33, "Someone Else")
        game.generation_path(folder, "4", 1).write_bytes(other)
        rename.rename_tribe(game, folder, 1, "New Name", FakeProcesses(), NOW)
        self.assertEqual(game.generation_path(folder, "4", 1).read_bytes(), other)
        self.assertEqual(rename.save_name(game, game.generation_path(folder, "2", 1).read_bytes()), "New Name")

    def test_an_older_tree_of_life_save_renames_in_place(self) -> None:
        game = rename.GAMES[3]
        folder = self.documents / "LDW" / f"{game.title}"
        folder.mkdir(parents=True)
        data = fixture("vv4-legacy-2")
        game.save_path(folder, 2).write_bytes(data)
        index = bytearray(fixture("vv4-huttest-0"))
        start = game.index_offset(2)
        index[start:start + 21] = b"KFT 4".ljust(21, b"\0")
        game.index_path(folder).write_bytes(bytes(index))
        rename.rename_tribe(game, folder, 2, "Older Save", FakeProcesses(), NOW)
        renamed = game.save_path(folder, 2).read_bytes()
        self.assertEqual(rename.save_name(game, renamed), "Older Save")
        self.assertEqual(renamed[: 12 + game.name_offset], data[: 12 + game.name_offset])

    def test_a_slot_with_no_save_is_refused(self) -> None:
        game, folder = self.make_folder("huttest", 3, "Modded")
        before = self.snapshot(folder)
        with self.assertRaises(rename.RenameError):
            rename.rename_tribe(game, folder, 2, "Nobody", FakeProcesses(), NOW)
        self.assertEqual(self.snapshot(folder), before)
        self.assertFalse((folder / "Backups").exists(), "a refusal makes no backup")

    def test_a_save_the_slot_list_still_calls_empty_is_a_tribe(self) -> None:
        # The game refills the slot list from the saves at startup, so a save
        # whose list entry still reads NEW PLAYER is shown under its own name.
        game, folder = self.make_folder("huttest", 3, "Modded")
        game.save_path(folder, 2).write_bytes(fixture("vv3-huttest-1"))
        self.assertEqual(rename.read_slots(game, folder)[1].label, "Save 2: Kalahuna Tribe 3 N")
        self.assertIsNone(rename.read_slots(game, folder)[1].problem)
        rename.rename_tribe(game, folder, 2, "Second", FakeProcesses(), NOW)
        index = game.index_path(folder).read_bytes()
        self.assertEqual(rename.index_name(game, index, 2), "Second")
        self.assertEqual(rename.index_name(game, index, 1), "Kalahuna Tribe 3 N")

    def test_the_slot_list_shows_every_slot(self) -> None:
        game, folder = self.make_folder("huttest", 5, "Modded")
        slots = rename.read_slots(game, folder)
        self.assertEqual([info.slot for info in slots], [1, 2, 3, 4, 5])
        self.assertEqual(slots[0].name, "Kalahuna Tribe 5")
        self.assertIsNone(slots[0].problem)
        self.assertEqual(slots[0].label, "Save 1: Kalahuna Tribe 5")
        self.assertTrue(all(info.problem for info in slots[1:]))
        self.assertEqual(slots[1].label, "Save 2: (empty)")

    def test_a_slot_list_name_that_differs_is_brought_into_line(self) -> None:
        game, folder = self.make_folder("huttest", 3, "Modded")
        index = bytearray(game.index_path(folder).read_bytes())
        start = game.index_offset(1)
        index[start:start + 21] = b"Kalahuna Tribe 3 M".ljust(21, b"\0")
        game.index_path(folder).write_bytes(bytes(index))
        info = rename.read_slots(game, folder)[0]
        self.assertEqual(info.label, "Save 1: Kalahuna Tribe 3 N", "the save's name, as the game shows")
        rename.rename_tribe(game, folder, 1, "One Name", FakeProcesses(), NOW)
        self.assertEqual(rename.index_name(game, game.index_path(folder).read_bytes(), 1), "One Name")


# ---------------------------------------------------------------------------
# The game must be closed
# ---------------------------------------------------------------------------


class RunningGameTests(SaveFolderTest):
    def test_a_running_game_is_refused_and_nothing_changes(self) -> None:
        game, folder = self.make_folder("huttest", 4, "Modded")
        before = self.snapshot(folder)
        processes = FakeProcesses(pids=[1234])
        with self.assertRaises(rename.GameRunning) as caught:
            rename.rename_tribe(game, folder, 1, "New Name", processes, NOW)
        self.assertIn(f"{game.title} - Modded.exe is running", str(caught.exception))
        self.assertEqual(self.snapshot(folder), before)
        self.assertFalse((folder / "Backups").exists())

    def test_the_game_checked_is_the_one_that_saves_here(self) -> None:
        game, folder = self.make_folder("256", 5, "Modded 256")
        seen = []

        class Recording(FakeProcesses):
            def find(self, exe_name):
                seen.append(exe_name)
                return []

        rename.rename_tribe(game, folder, 1, "New Name", Recording(), NOW)
        self.assertTrue(seen)
        self.assertEqual(set(seen), {f"{game.title} - Modded 256.exe"})

    def test_when_the_process_list_fails_nothing_changes(self) -> None:
        game, folder = self.make_folder("huttest", 1, "Modded")
        before = self.snapshot(folder)
        with self.assertRaises(rename.RenameError):
            rename.rename_tribe(
                game, folder, 1, "New Name", FakeProcesses(error=OSError("denied")), NOW
            )
        self.assertEqual(self.snapshot(folder), before)

    def test_a_game_started_during_the_backup_stops_the_rename(self) -> None:
        game, folder = self.make_folder("huttest", 2, "Modded")
        before = self.snapshot(folder)
        with self.assertRaises(rename.GameRunning):
            rename.rename_tribe(game, folder, 1, "New Name", FakeProcesses(start_after=1), NOW)
        self.assertEqual(self.snapshot(folder), before)

    def test_the_module_never_pauses_or_closes_a_game(self) -> None:
        source = (ROOT / "src" / "vv_tribe_rename.py").read_text(encoding="utf-8")
        for forbidden in ("suspend(", "paused_game", "TerminateProcess", "taskkill", "resume("):
            with self.subTest(call=forbidden):
                self.assertNotIn(forbidden, source)


# ---------------------------------------------------------------------------
# Backup, atomic writes, verification and restore
# ---------------------------------------------------------------------------


class SafetyTests(SaveFolderTest):
    def test_the_folder_is_backed_up_first_and_labelled(self) -> None:
        game, folder = self.make_folder("huttest", 3, "Modded")
        logs = folder / rename.LOGS_FOLDER / "Births and Conceptions"
        logs.mkdir(parents=True)
        (logs / "Virtual Villagers 3 Births and Conceptions Log 1.txt").write_bytes(
            b"Village: Kalahuna Tribe 3 N (Save 1)\r\nConception 1\r\n\r\n"
        )
        before = self.snapshot(folder)
        result = rename.rename_tribe(game, folder, 1, "New Name", FakeProcesses(), NOW)
        self.assertEqual(result.backup.backup_folder.name, "Backup 2026-10-04 15-30-00 (before rename)")
        self.assertEqual(result.backup.backup_folder.parent, folder / "Backups")
        copied = {
            path.relative_to(result.backup.backup_folder).as_posix(): path.read_bytes()
            for path in result.backup.backup_folder.rglob("*")
            if path.is_file()
        }
        self.assertEqual(copied, before, "the backup holds every file as it was before the rename")

    def test_the_before_rename_backup_is_offered_by_restore_saves(self) -> None:
        game, folder = self.make_folder("huttest", 5, "Modded")
        original = game.save_path(folder, 1).read_bytes()
        result = rename.rename_tribe(game, folder, 1, "New Name", FakeProcesses(), NOW)
        listed = backup.list_backups(folder)
        self.assertEqual([info.path for info in listed], [result.backup.backup_folder])
        self.assertTrue(listed[0].before_rename)
        self.assertFalse(listed[0].before_restore)
        self.assertEqual(listed[0].label, "2026-10-04 15:30:00 (before rename)")
        self.assertEqual(listed[0].villages, {1: "Kalahuna Tribe 5"})
        self.assertEqual((result.backup.backup_folder / game.save_path(folder, 1).name).read_bytes(), original)

    def test_a_failed_backup_changes_nothing(self) -> None:
        game, folder = self.make_folder("huttest", 1, "Modded")
        before = self.snapshot(folder)
        with mock.patch.object(backup, "_copy_one", side_effect=backup.BackupError("disk full")):
            with self.assertRaises(rename.RenameError) as caught:
                rename.rename_tribe(game, folder, 1, "New Name", FakeProcesses(), NOW)
        self.assertIn("nothing was changed", str(caught.exception))
        self.assertEqual(self.snapshot(folder), before)

    def test_files_are_replaced_through_a_temporary_file(self) -> None:
        game, folder = self.make_folder("huttest", 1, "Modded")
        replaced = []
        real_replace = os.replace

        def spy(source, destination):
            replaced.append((Path(source).name, Path(destination).name))
            return real_replace(source, destination)

        with mock.patch.object(rename.os, "replace", side_effect=spy):
            rename.rename_tribe(game, folder, 1, "New Name", FakeProcesses(), NOW)
        names = {destination for _source, destination in replaced}
        self.assertEqual(
            names,
            {"Virtual Villagers1.ldw", "Virtual Villagers21.ldw", "Virtual Villagers41.ldw", "Virtual Villagers0.ldw"},
        )
        for source, destination in replaced:
            self.assertEqual(source, destination + ".rename-tmp")
        self.assertEqual(list(folder.glob("*.rename-tmp")), [])

    def test_a_failure_part_way_puts_every_file_back(self) -> None:
        game, folder = self.make_folder("huttest", 5, "Modded")
        logs = folder / rename.LOGS_FOLDER / "Deaths"
        logs.mkdir(parents=True)
        log = logs / "Virtual Villagers 5 Deaths Log 1.txt"
        log.write_bytes(b"Village: Kalahuna Tribe 5 (Save 1)\r\n")
        before = self.snapshot(folder)
        real = rename._write_atomically

        def fail_on_index(path, data):
            if path.name.endswith("0.ldw"):
                raise OSError("the disk went away")
            return real(path, data)

        with mock.patch.object(rename, "_write_atomically", side_effect=fail_on_index):
            with self.assertRaises(rename.RenameError) as caught:
                rename.rename_tribe(game, folder, 1, "New Name", FakeProcesses(), NOW)
        self.assertIn("every file was put back", str(caught.exception))
        self.assertEqual(self.snapshot(folder), before)
        self.assertEqual(list(folder.glob("*.rename-tmp")), [])

    def test_a_log_note_that_fails_puts_the_saves_and_logs_back(self) -> None:
        game, folder = self.make_folder("huttest", 2, "Modded")
        logs = folder / rename.LOGS_FOLDER / "Births and Conceptions"
        logs.mkdir(parents=True)
        for number in (1, 2):
            (logs / f"Virtual Villagers 2 Births and Conceptions Log {number}.txt").write_bytes(
                b"Village: Kalahuna Tribe 2 (Save 1)\r\nConception 1\r\n\r\n"
            )
        before = self.snapshot(folder)
        real_open = Path.open
        real_copy = backup.copy_save_folder
        armed = []

        def copy_then_arm(*args, **kwargs):
            result = real_copy(*args, **kwargs)
            armed.append(True)       # from here on the saves are being written
            return result

        def flaky(self_path, mode="r", *args, **kwargs):
            if armed and mode == "rb" and self_path.name.endswith("Log 2.txt"):
                raise OSError("read failed")     # the second note's read-back
            return real_open(self_path, mode, *args, **kwargs)

        with mock.patch.object(backup, "copy_save_folder", side_effect=copy_then_arm), \
                mock.patch.object(Path, "open", flaky):
            with self.assertRaises(rename.RenameError) as caught:
                rename.rename_tribe(game, folder, 1, "New Name", FakeProcesses(), NOW)
        self.assertIn("every file was put back", str(caught.exception))
        self.assertTrue(armed, "the failure came after the backup, while writing")
        self.assertEqual(self.snapshot(folder), before)

    def test_a_write_that_does_not_read_back_is_undone(self) -> None:
        game, folder = self.make_folder("huttest", 4, "Modded")
        before = self.snapshot(folder)
        real = rename._write_atomically

        def corrupting(path, data):
            real(path, data)
            if path.name.endswith("21.ldw") and b"New Name" in data:
                path.write_bytes(data[:-1] + b"\x01")
                raise rename.RenameError(f"{path.name} did not read back as written.")

        with mock.patch.object(rename, "_write_atomically", side_effect=corrupting):
            with self.assertRaises(rename.RenameError):
                rename.rename_tribe(game, folder, 1, "New Name", FakeProcesses(), NOW)
        self.assertEqual(self.snapshot(folder), before)

    def test_write_atomically_verifies_by_reading_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.ldw"
            path.write_bytes(b"old")
            real_read = Path.read_bytes
            with mock.patch.object(Path, "read_bytes", lambda self: b"other" if self == path else real_read(self)):
                with self.assertRaises(rename.RenameError):
                    rename._write_atomically(path, b"new")


# ---------------------------------------------------------------------------
# The patcher's logs: the renamed village is the same village
# ---------------------------------------------------------------------------


def write_log(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\n", "\r\n").encode("ascii"))
    return path


class LogTests(SaveFolderTest):
    def make_logs(self, folder: Path, number: int, old: str) -> dict[str, Path]:
        logs = folder / rename.LOGS_FOLDER
        header = f"Village: {old} (Save 1)\n"
        return {
            "births": write_log(logs / "Births and Conceptions" / f"Virtual Villagers {number} Births and Conceptions Log 1.txt",
                                header + "Conception 1\n  Mother: A\n\n"),
            "births2": write_log(logs / "Births and Conceptions" / f"Virtual Villagers {number} Births and Conceptions Log 2.txt",
                                 header + "Conception 257\n  Mother: A\n\nBirth\n  Child: B\n"),
            "other": write_log(logs / "Births and Conceptions" / f"Virtual Villagers {number} Births and Conceptions Log 3.txt",
                               "Village: Another Tribe (Save 2)\nConception 1\n\n"),
            "same_name_other_slot": write_log(
                logs / "Deaths" / f"Virtual Villagers {number} Deaths Log 2.txt",
                f"Village: {old} (Save 2)\nDeath 1\n\n"),
            "deaths": write_log(logs / "Deaths" / f"Virtual Villagers {number} Deaths Log 1.txt",
                                header + "Death 1\n  Name: C\n\n"),
            "unaccounted": write_log(logs / "Unaccounted Villagers" / f"Virtual Villagers {number} Unaccounted Villagers Log 1.txt",
                                     header),
            "population": write_log(logs / "Tribe Population" / "Village Population 1.txt",
                                    f"Virtual Villagers {number} Village Population\n" + header + "\nVillager 1\n"),
            "statistics": write_log(logs / "Village Statistics" / "Village Statistics v2 - Save 1.txt",
                                    "Virtual Villagers\nVillage Statistics\n" + header + "\nFood Gathered: 1\n"),
            "history": write_log(logs / "Tribe History" / "Village History 1.txt",
                                 "=== Virtual Villagers -- 2026-09-26 14:30:48 ===\n" + header + "\nVillager 1\n\n"),
            "legacy": write_log(folder / "VVFP Logs" / "Tribe Parental Records" / f"Virtual Villagers {number} Parentage Log 1.txt",
                                header + "Conception 1\n\n"),
            "unheaded": write_log(logs / "Deaths" / f"Virtual Villagers {number} Deaths Log 3.txt",
                                  "Death 1\n  Name: D\n\n"),
            "other_game": write_log(logs / "Births and Conceptions" / f"Virtual Villagers {number % 5 + 1} Births and Conceptions Log 1.txt",
                                    header + "Conception 1\n\n"),
        }

    def test_each_of_the_villages_logs_gets_one_note_and_nothing_else_changes(self) -> None:
        game, folder = self.make_folder("huttest", 1, "Modded")
        logs = self.make_logs(folder, 1, "Kalahuna Tribe 1")
        before = {key: path.read_bytes() for key, path in logs.items()}
        result = rename.rename_tribe(game, folder, 1, "New Name", FakeProcesses(), NOW)
        note = b"Tribe renamed from Kalahuna Tribe 1 to New Name on 2026-10-04\r\n\r\n"
        for key in ("births", "births2", "deaths", "unaccounted", "population", "statistics", "legacy"):
            with self.subTest(log=key):
                after = logs[key].read_bytes()
                self.assertTrue(after.startswith(before[key]), "nothing already written is rewritten")
                tail = after[len(before[key]):]
                self.assertEqual(tail.lstrip(b"\r\n"), note)
                self.assertEqual(after.count(b"Tribe renamed"), 1)
        history = logs["history"].read_bytes()
        self.assertEqual(
            history[len(before["history"]):],
            b"Tribe renamed from Kalahuna Tribe 1 to New Name on 2026-10-04 (Save 1)\r\n\r\n",
        )
        for key in ("other", "same_name_other_slot", "unheaded", "other_game"):
            with self.subTest(untouched=key):
                self.assertEqual(logs[key].read_bytes(), before[key])
        self.assertEqual(set(result.notes), {logs[key] for key in (
            "births", "births2", "deaths", "unaccounted", "population", "statistics", "legacy", "history")})

    def test_after_the_rename_the_logs_stand_for_the_new_village(self) -> None:
        game, folder = self.make_folder("huttest", 4, "Modded")
        logs = self.make_logs(folder, 4, "Kalahuna Tribe 4")
        rename.rename_tribe(game, folder, 1, "New Name", FakeProcesses(), NOW)
        self.assertEqual(
            rename.effective_header(logs["births"].read_bytes().decode(), 0),
            "Village: New Name (Save 1)",
        )
        self.assertEqual(
            rename.effective_header(logs["population"].read_bytes().decode(), 1),
            "Village: New Name (Save 1)",
        )
        # A second rename chains from the new name.
        rename.rename_tribe(game, folder, 1, "Third Name", FakeProcesses(), datetime(2026, 10, 5))
        text = logs["births"].read_bytes().decode()
        self.assertEqual(rename.effective_header(text, 0), "Village: Third Name (Save 1)")
        self.assertIn("Tribe renamed from New Name to Third Name on 2026-10-05", text)
        self.assertEqual(text.count("Tribe renamed"), 2)

    def test_the_backups_logs_are_never_touched(self) -> None:
        game, folder = self.make_folder("huttest", 3, "Modded")
        self.make_logs(folder, 3, "Kalahuna Tribe 3 N")
        backup.copy_save_folder(folder, datetime(2026, 10, 1))
        old_backup = folder / "Backups" / "Backup 2026-10-01 00-00-00"
        before = {p: p.read_bytes() for p in old_backup.rglob("*") if p.is_file()}
        rename.rename_tribe(game, folder, 1, "New Name", FakeProcesses(), NOW)
        self.assertEqual({p: p.read_bytes() for p in old_backup.rglob("*") if p.is_file()}, before)

    def test_no_data_file_is_touched(self) -> None:
        game, folder = self.make_folder("huttest", 2, "Modded")
        data = folder / "Virtual Villagers Fun Patcher Data"
        files = [
            data / "Village Statistics" / "Village Statistics - Save 1.dat",
            data / "Village Statistics" / "Village Roster - Save 1.dat",
            data / "Stew Discoveries" / "Stew Discoveries - Save 1.dat",
            data / "Village Elders" / "Village Elders - Save 1.dat",
            data / "Virtual Villagers 2 Graves - Save 1.dat",
            data / "Virtual Villagers 2 Village Roster - Save 1.dat",
        ]
        for path in files:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"Kalahuna Tribe 2\0" + bytes(range(64)))
        before = {path: path.read_bytes() for path in files}
        rename.rename_tribe(game, folder, 1, "New Name", FakeProcesses(), NOW)
        self.assertEqual({path: path.read_bytes() for path in files}, before)
        self.assertEqual(sorted(p.name for p in data.rglob("*") if p.is_file()), sorted(p.name for p in files))

    def test_the_rename_note_parser_matches_the_native_one(self) -> None:
        cases = [
            ("Village: Old (Save 1)", "Tribe renamed from Old to New on 2026-10-04", "Village: New (Save 1)"),
            ("Village: Old (Save 1)", "Tribe renamed from Other to New on 2026-10-04", "Village: Old (Save 1)"),
            ("Village: Old (Save 1)", "  Tribe renamed from Old to New on 2026-10-04", "Village: Old (Save 1)"),
            ("Village: Old (Save 1)", "Tribe renamed from Old to New on 2026-10-4", "Village: Old (Save 1)"),
            ("Village: Old (Save 1)", "Tribe renamed from Old to  on 2026-10-04", "Village: Old (Save 1)"),
            ("Village: Old (Save 1)", "Tribe renamed from Old to New on 2026-10-04 (Save 1)", "Village: Old (Save 1)"),
            ("Village: Old to Me (Save 2)", "Tribe renamed from Old to Me to on on 2026-10-04", "Village: on (Save 2)"),
            ("Village: A (Save 2) (Save 3)", "Tribe renamed from A (Save 2) to B on 2026-10-04", "Village: B (Save 3)"),
            ("Village: Old", "Tribe renamed from Old to New on 2026-10-04", "Village: New"),
        ]
        for header, line, expected in cases:
            with self.subTest(header=header, line=line):
                self.assertEqual(rename.apply_rename_note(header, line), expected)
        source = (ROOT / "native" / "shared" / "village_rename.h").read_text(encoding="utf-8")
        self.assertIn('#define VV_RENAME_PREFIX "Tribe renamed from "', source)
        self.assertEqual(rename.RENAME_PREFIX, "Tribe renamed from ")


class NativeReadersFollowTheNoteTests(unittest.TestCase):
    def test_both_header_readers_apply_the_note(self) -> None:
        parentage = (ROOT / "native" / "parentage_export" / "parentage_export.c").read_text(encoding="utf-8")
        reset = (ROOT / "native" / "shared" / "save_reset.c").read_text(encoding="utf-8")
        self.assertIn('#include "village_rename.h"', parentage)
        self.assertIn("(void)vv_rename_apply(out, size, line);", parentage)
        self.assertIn('#include "village_rename.h"', reset)
        self.assertIn("(void)vv_rename_apply(header, sizeof(header), line);", reset)

    CL = Path(
        r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC"
        r"\14.51.36231\bin\Hostx64\x86\cl.exe"
    )

    @unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
    def test_the_log_selection_harness_keeps_a_renamed_village_in_its_file(self) -> None:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             str(ROOT / "scripts" / "build_select_holes_harness.ps1")],
            capture_output=True, text=True, timeout=300,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK (0 failures)", result.stdout)
        for case in (
            "[PASS] A CONCEPTION AFTER A RENAME STAYS IN THE VILLAGE'S FILE 1",
            "[PASS] A BIRTH AFTER A RENAME STAYS IN FILE 1 beside its conception",
            "[PASS] THE SAVE AFTER A RENAME CREATES NO NEW LOG (no rollover)",
            "[PASS] A SECOND RENAME CHAINS: the newest name selects file 1",
        ):
            with self.subTest(case=case):
                self.assertIn(case, result.stdout)


# ---------------------------------------------------------------------------
# Where the save folders are, and the window
# ---------------------------------------------------------------------------


class FolderTests(unittest.TestCase):
    def test_the_modded_folders_back_up_and_restore_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            documents = Path(tmp)
            title = rename.GAMES[2].title
            for name in (title, f"{title} - Modded 256", f"{title} - Modded", "Virtual Villagers - A New Home - Modded"):
                (documents / "LDW" / name).mkdir(parents=True)
            self.assertEqual(
                [path.name for path in rename.rename_folders(title, documents)],
                [f"{title} - Modded", f"{title} - Modded 256"],
            )
            self.assertEqual(
                rename.rename_folders(title, documents),
                backup.find_save_folders(title, documents),
            )
            self.assertEqual(rename.rename_folders(title, None), [])


class GuiTests(unittest.TestCase):
    SOURCE = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")

    def test_the_link_sits_beside_back_up_and_restore_saves(self) -> None:
        self.assertRegex(
            self.SOURCE,
            r'"Restore Saves\.\.\.", self\._restore_single_saves\s*\)\.pack\(side="left", padx=\(18, 0\)\)\s*'
            r'self\._help_button\(links, "restore_saves"\)\.pack\(side="left", padx=\(3, 0\)\)\s*'
            r'self\._folder_link\(\s*links, "Rename Tribe\.\.\.", self\._rename_single_tribe',
        )
        self.assertIn('"Rename tribe...",\n                lambda game=build: self._rename_tribe(game)', self.SOURCE)
        self.assertIn('text="Rename Tribe...",\n            command=lambda: self._rename_tribe(None)', self.SOURCE)

    def test_the_rename_runs_off_the_main_thread_through_the_module(self) -> None:
        self.assertIn("import vv_tribe_rename", self.SOURCE)
        self.assertRegex(self.SOURCE, r"self\._run_with_wait\(\s*\"Renaming the tribe")
        self.assertIn("vv_tribe_rename.rename_tribe(", self.SOURCE)

    def test_the_counter_and_the_refusals_come_from_the_module(self) -> None:
        self.assertIn("vv_tribe_rename.name_problem(", self.SOURCE)
        self.assertIn("saves.max_length", self.SOURCE)

    def test_the_module_ships_in_the_release(self) -> None:
        build = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn("vv_tribe_rename", build)


if __name__ == "__main__":
    unittest.main()
