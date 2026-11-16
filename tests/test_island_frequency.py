"""More Frequent Island Events (all five games; the owner, 2026-11-15: a slider like the other multiplier sliders, 2x
to 100x; at N x the game's own island events come N times as often; the opening events' timing and the rescue rule
as in the stock game; off by default, on in Owner's Defaults, the slider 2 unless moved).

EMULATED, on the executable the patcher renders for the row, in each of the three public modes: "VVFP Island
Frequency.dll" is started as VVFP Startup.dll starts it (VvfpStartup(game, ...)), with the slider's number in
"VVFP Island Frequency.txt" in the patcher's folder; then each of the game's own draws of the next wait (`add eax,
K; imul eax, eax, 0xE10`, eax the game's rand(K)) is run, and eax comes out as (roll + K) x 3600 / N with every other
register as the game left it -- at x 2, x 10 and x 100.  The 30 minutes before the next event while a village has
seen none, and the trigger's own write that the Origins companions' island timer keeper hooks, are other bytes.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

try:
    from test_companion_installs_all_or_none import HAVE_EMULATOR, Machine, render, stock_path, with_requirements
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

import vv_fun_patcher as patcher

DLL = ROOT / "assets" / "island_frequency" / "VVFP Island Frequency.dll"
CHOICE = "VVFP Island Frequency.txt"
MODES = ("stock", "collection_progression", "immediate_fixed")
FAKE_FILE = 0x0000F00D
HOURS = {1: 12, 2: 10, 3: 8, 4: 8, 5: 8}
SITES = {1: (0x423883, 0x42390A, 0x423A61), 2: (0x42EF93, 0x42F01A, 0x42F171), 3: (0x4687FB, 0x468832, 0x4688C6),
         4: (0x43FAF7, 0x43FB35, 0x43FBC4), 5: (0x4427C1, 0x442828)}
REGS = ("ebx", "ecx", "edx", "esi", "edi", "ebp")


def row_id(game: int) -> str:
    return f"vv{game}_more_frequent_island_events"


def site_bytes(game: int) -> bytes:
    return bytes([0x83, 0xC0, HOURS[game], 0x69, 0xC0, 0x10, 0x0E, 0x00, 0x00])


@unittest.skipUnless(HAVE_EMULATOR, "pefile/unicorn not installed")
class Stock(unittest.TestCase):
    def setUp(self) -> None:
        if not all(stock_path(g).is_file() for g in HOURS):
            self.skipTest("stock executables not present")

    def test_the_sites_are_every_draw_of_the_wait(self) -> None:
        for game in HOURS:
            data = stock_path(game).read_bytes()
            found = [0x400000 + m.start() for m in re.finditer(rb"\x83\xC0(.)\x69\xC0\x10\x0E\x00\x00", data, re.S)]
            with self.subTest(game=game):
                self.assertEqual(tuple(found), SITES[game])
                for va in SITES[game]:
                    self.assertEqual(data[va - 0x400000:va - 0x400000 + 9], site_bytes(game))
                    # The draw right before: push K; call rand.
                    self.assertIn(bytes([0x6A, HOURS[game], 0xE8]), data[va - 0x400000 - 16:va - 0x400000])

    def test_no_byte_is_shared_with_the_timer_keeper(self) -> None:
        for game in HOURS:
            text = (ROOT / "native" / "shared" / f"island_timer_vv{game}.inc").read_text("utf-8")
            keeper = [(int(va, 16), int(n)) for va, n in re.findall(r"\{ 0x([0-9A-F]+)u, (\d+),", text)]
            self.assertTrue(keeper)
            for va in SITES[game]:
                for at, length in keeper:
                    with self.subTest(game=game, site=hex(va), keeper=hex(at)):
                        self.assertTrue(va + 9 <= at or at + length <= va)


@unittest.skipUnless(HAVE_EMULATOR, "pefile/unicorn not installed")
class Emulated(unittest.TestCase):
    def setUp(self) -> None:
        if not all(stock_path(g).is_file() for g in HOURS):
            self.skipTest("stock executables not present")
        if not DLL.is_file():
            self.skipTest("companion not built")

    def machine(self, game: int, setting: bytes | None, mode: str = "stock") -> "Machine":
        m = Machine(render(game, with_requirements(game, [row_id(game)]), mode), DLL)
        opened: list[str] = []

        def open_(p):
            path = p.wstring(p.arg(0))
            opened.append(path)
            ok = setting is not None and path.endswith("\\Virtual Villagers Fun Patcher Files\\" + CHOICE)
            return (FAKE_FILE if ok else 0xFFFFFFFF), 28

        def read(p):
            if p.arg(0) != FAKE_FILE:
                return 0, 20
            data = (setting or b"")[:p.arg(2)]
            p.write(p.arg(1), data)
            p.put32(p.arg(3), len(data))
            return 1, 20

        m.api_handlers["CreateFileW"] = open_
        m.api_handlers["ReadFile"] = read
        m.api_handlers["CloseHandle"] = lambda p: (1, 4)
        m.opened = opened
        return m

    def wait(self, m: "Machine", va: int, roll: int) -> tuple[int, dict]:
        """The site run with eax = the game's roll: eax after, and the other registers before and after."""
        values = {"ebx": 0x11111111, "ecx": 0x22222222, "edx": 0x33333333, "esi": 0x44444444, "edi": 0x55555555,
                  "ebp": 0x66666666}
        for name, value in values.items():
            m.set_reg(name, value)
        m.set_reg("eax", roll)
        esp = m.reg("esp")
        m.run(va, va + 9)
        self.assertEqual(m.reg("esp"), esp)
        return m.reg("eax"), {name: m.reg(name) for name in REGS}

    def test_the_wait_follows_the_slider(self) -> None:
        for game in HOURS:
            k = HOURS[game]
            for n in (2, 10, 100):
                for mode in (MODES if n == 10 else MODES[:1]):
                    with self.subTest(game=game, n=n, mode=mode):
                        m = self.machine(game, f"{n}\n".encode(), mode)
                        m.export("VvfpStartup", game, 0)
                        self.assertEqual(m.export("VvfpIslandFrequencyInstalled"), 1)
                        self.assertEqual(m.export("VvfpIslandFrequencyDivisor"), n)
                        self.assertTrue(m.opened[-1].endswith(CHOICE))
                        for va in SITES[game]:
                            for roll in (0, 1, k - 1):
                                eax, regs = self.wait(m, va, roll)
                                self.assertEqual(eax, (roll + k) * 3600 // n)
                                self.assertEqual(regs, {"ebx": 0x11111111, "ecx": 0x22222222, "edx": 0x33333333,
                                                        "esi": 0x44444444, "edi": 0x55555555, "ebp": 0x66666666})

    def test_the_numbers_at_the_ends(self) -> None:
        # A New Home at x 2: 6 to 11.5 hours; The Secret City at x 100: 4 minutes 48 seconds to 9 minutes.
        self.assertEqual((12 * 3600 // 2, 23 * 3600 // 2), (21_600, 41_400))
        self.assertEqual((8 * 3600 // 100, 15 * 3600 // 100), (288, 540))

    def test_the_setting_file(self) -> None:
        cases = ((b"2", 2), (b"10\n", 10), (b"100\r\n", 100), (b" 42 ", 42), (b"0", 2), (b"1", 2), (b"101", 100),
                 (b"99999999999", 100), (b"abc", 2), (b"", 2), (None, 2))
        for setting, wanted in cases:
            with self.subTest(setting=setting):
                m = self.machine(3, setting)
                m.export("VvfpStartup", 3, 0)
                self.assertEqual(m.export("VvfpIslandFrequencyDivisor"), wanted)
                eax, _ = self.wait(m, SITES[3][0], 7)
                self.assertEqual(eax, 15 * 3600 // wanted)

    def test_nothing_in_another_game_or_when_a_site_is_not_stock(self) -> None:
        m = self.machine(4, b"10")
        before = [m.read(va, 9) for va in SITES[4]]
        m.export("VvfpStartup", 6, 0)
        self.assertEqual(m.export("VvfpIslandFrequencyInstalled"), 0)
        self.assertEqual([m.read(va, 9) for va in SITES[4]], before)
        m = self.machine(4, b"10")
        m.write(SITES[4][2], b"\x90")
        m.export("VvfpStartup", 4, 0)
        self.assertEqual(m.export("VvfpIslandFrequencyInstalled"), 0)
        self.assertEqual([m.read(va, 9) for va in SITES[4][:2]], before[:2])


class Rows(unittest.TestCase):
    def test_five_rows_off_by_default_on_in_owners_defaults(self) -> None:
        from vv_fun_patcher_gui import (default_fun_patch_selection, owners_default_fun_patch_selection,
                                        select_all_fun_patch_selection)
        public = {p.id: p for p in patcher.load_public_fun_patches()}
        for game in HOURS:
            with self.subTest(game=game):
                row = public[row_id(game)]
                self.assertEqual(row.name, "More Frequent Island Events")
                self.assertEqual(row.raw["dependencies"], [])
                self.assertEqual(row.raw["patches"], [])
                self.assertIn("**Needs no other patch.**", row.raw["description"])
                self.assertIn("2 to 100 times as often", row.raw["description"])
                self.assertEqual([d["va"] for d in row.raw["runtime_detours"]],
                                 [f"0x{va:X}" for va in SITES[game]])
                self.assertEqual({d["stock_bytes"] for d in row.raw["runtime_detours"]},
                                 {site_bytes(game).hex().upper()})
                self.assertFalse(default_fun_patch_selection(row_id(game)))
                self.assertTrue(owners_default_fun_patch_selection(row_id(game)))
                self.assertFalse(select_all_fun_patch_selection(row_id(game)))

    def test_each_row_is_what_the_generator_writes(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_island_frequency_features as gen
        if not DLL.is_file():
            self.skipTest("companion not built")
        for game in HOURS:
            with self.subTest(game=game):
                record = json.loads((ROOT / "data" / f"{row_id(game)}_feature.json").read_text("utf-8"))
                self.assertEqual(record, gen.row(game, gen.sha(DLL)))

    def test_started_from_the_second_word(self) -> None:
        self.assertIn("VVFP Island Frequency.dll", patcher.STARTUP_LOADER_COMPANIONS_2)
        header = (ROOT / "native" / "shared" / "startup_companions_2.h").read_text("utf-8")
        self.assertIn('"VVFP Island Frequency.dll",', header)


class Setting(unittest.TestCase):
    def setUp(self) -> None:
        self.addCleanup(patcher.set_island_frequency_multiplier, patcher.island_frequency_multiplier())

    def test_whole_numbers_2_to_100_default_2(self) -> None:
        self.assertEqual(patcher.ISLAND_FREQUENCY_MULTIPLIER_DEFAULT, 2)
        self.assertEqual(list(patcher.ISLAND_FREQUENCY_MULTIPLIER_RANGE), list(range(2, 101)))
        for good in (2, 10, 100):
            self.assertEqual(patcher.set_island_frequency_multiplier(good), good)
        for bad in (1, 101, 0, 2.5, "5", True, None):
            with self.subTest(bad=bad), self.assertRaises(patcher.PatcherError):
                patcher.set_island_frequency_multiplier(bad)
        self.assertEqual(patcher.island_frequency_multiplier(), 100)

    def test_written_beside_the_companion_only_with_the_row(self) -> None:
        public = {p.id: p for p in patcher.load_public_fun_patches()}
        for n in (2, 10, 100):
            with tempfile.TemporaryDirectory() as out, self.subTest(n=n):
                patcher.set_island_frequency_multiplier(n)
                patcher._write_island_frequency_choice(Path(out), [public["vv3_children_play"]])
                self.assertEqual(list(Path(out).rglob(CHOICE)), [])
                patcher._write_island_frequency_choice(Path(out), [public[row_id(3)]])
                beside = Path(out) / Path(*patcher.patcher_files.installed_relative_path(
                    "VVFP Island Frequency.dll").parts).parent / CHOICE
                self.assertEqual(list(Path(out).rglob(CHOICE)), [beside])
                self.assertEqual(beside.read_bytes(), f"{n}\n".encode())

    def test_the_command_line(self) -> None:
        import argparse
        parser = argparse.ArgumentParser()
        patcher._add_check_logs_arg(parser)
        self.assertIsNone(parser.parse_args([]).island_frequency_multiplier)
        for n in ("2", "10", "100"):
            self.assertEqual(parser.parse_args(["--island-frequency-multiplier", n]).island_frequency_multiplier,
                             int(n))
        for bad in ("1", "101"):
            with self.subTest(value=bad), self.assertRaises(SystemExit):
                parser.parse_args(["--island-frequency-multiplier", bad])

    def test_the_log_and_kept_files_name_it(self) -> None:
        source = (ROOT / "src" / "vv_fun_patcher.py").read_text("utf-8")
        self.assertEqual(source.count('**({"island_frequency_multiplier": _island_frequency_multiplier}'), 2)
        self.assertIn("relatives.append(str(installed.parent / ISLAND_FREQUENCY_CHOICE_FILE))", source)
        self.assertIn("    _write_island_frequency_choice(output_folder, fun_patches)\n", source)
        self.assertIn("(the More Frequent Island Events \"\n", (ROOT / "src" / "transparency.py").read_text("utf-8"))


class GameMechanics(unittest.TestCase):
    """With the row in the game, the timing line is followed by the shortened wait, at the game's own N."""

    class Village:
        def __init__(self, game: int, has: bool | None, exe: Path | None):
            self.game, self._has, self.exe = game, has, exe

        def has(self, feature: str):
            return self._has if feature.endswith("_more_frequent_island_events") else False

    def facts(self, game: int, has: bool | None, setting: bytes | None) -> list[str]:
        import vv_game_mechanics_events as ev
        folder = Path(tempfile.mkdtemp(prefix="vvif"))
        self.addCleanup(__import__("shutil").rmtree, folder, True)
        exe = folder / "game.exe"
        exe.write_bytes(b"")
        if setting is not None:
            (folder / "Virtual Villagers Fun Patcher Files").mkdir()
            (folder / "Virtual Villagers Fun Patcher Files" / CHOICE).write_bytes(setting)
        rules = (ev.Line("Timing: the game's own wait."), ev.Line("Which event: one is drawn."))
        return [f.text for f in ev.event_facts(self.Village(game, has, exe), rules)]

    def test_the_shortened_wait_is_shown_only_with_the_row(self) -> None:
        texts = self.facts(3, True, b"10")
        self.assertEqual(len(texts), 3)
        self.assertTrue(texts[1].startswith('With the patcher\'s "More Frequent Island Events" (in this game): '))
        self.assertIn("10 times as often", texts[1])
        self.assertIn("48 minutes to 1 hour 30 minutes of real-life time instead of 8 to 15 hours", texts[1])
        self.assertEqual(len(self.facts(3, False, b"10")), 2)
        self.assertEqual(len(self.facts(3, None, b"10")), 2)

    def test_every_game_and_setting(self) -> None:
        import vv_game_mechanics_events as ev
        expected = {(1, b"2"): "6 hours to 11 hours 30 minutes", (2, b"2"): "5 hours to 9 hours 30 minutes",
                    (4, b"100"): "4 minutes 48 seconds to 9 minutes", (5, b"100"): "4 minutes 48 seconds to 9 minutes",
                    (1, b"100"): "7 minutes 12 seconds to 13 minutes 48 seconds"}
        for (game, setting), words in expected.items():
            with self.subTest(game=game, setting=setting):
                self.assertIn(words, self.facts(game, True, setting)[1])
        # No file: the number set on its slider.
        self.assertIn("divided by the number set on its slider (2 to 100)", self.facts(4, True, None)[1])
        self.assertEqual(set(ev.FREQUENCY_HOURS), set(HOURS))
        self.assertEqual(ev.FREQUENCY_HOURS, HOURS)


if __name__ == "__main__":
    unittest.main()
