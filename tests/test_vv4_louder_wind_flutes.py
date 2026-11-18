"""The Tree of Life's "Louder Wind Flutes" (the owner, 2026-11-10: "make the sound volume for just the wind flutes a
bit louder so they're clearly heard above the game music"; after a preview of 2.5 times: "yes make the patch"; then,
2026-11-15: "Also add an option to control how loud the wind flutes are too! (same slider)" -- a 2x to 100x slider
like Classic VV Difficulty's, 5 unless moved, loud and clear above the music, never distorted).

EMULATED, on the executable the patcher renders for the row, in each of the three public modes:

* "VVFP VV4 Louder Flutes.dll" is started as VVFP Startup.dll starts it (VvfpStartup(4, ...)), with a stand-in
  fmod.dll that behaves as the real fmod.dll 3.74 was seen to (a scratch 32-bit probe on 2026-11-10: each flute
  loads as mode 0x151 -- 16-bit, stereo, signed PCM -- and FSOUND_Sample_Lock hands back the whole sample), and the
  slider's number in "VVFP VV4 Louder Flutes.txt" beside the DLL;
* the game's own sound loader runs its call of FSOUND_Sample_Load (0x40C4DE..0x40C500, the one call every sound
  effect is loaded through), with the thunk 0x47099E stood in for.

Then Flute1.ogg, Flute3.ogg and Flute5.ogg come back N times louder through the limiter -- exactly louder() below,
never over -1 dBFS -- at x 2, x 5 and x 10 (the slider's top since 2026-11-17), and (the owner, 2026-11-17: every slider goes less as well
as more) quieter at x 0.5 and x 0.1 -- and every other sound, a sample that is not 16-bit signed PCM,
and one FMOD will not hand back whole, exactly as loaded.  Without fmod.dll's functions, or in another game, nothing
is installed.  The setting file: 0.1 to 10 in tenths as written, above 10 is 10, below 0.1 is 0.1, no number or
no file is 5.
"""
from __future__ import annotations

import json
import math
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

try:
    from test_companion_installs_all_or_none import HAVE_EMULATOR, Machine, render, stock_path, with_requirements
    from story_emulator import API_STUBS, HEAP, STACK_TOP
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

import vv_fun_patcher as patcher

ROW = "vv4_louder_wind_flutes"
DLL = ROOT / "assets" / "vv4_louder_flutes" / "VVFP VV4 Louder Flutes.dll"
FEATURE = ROOT / "data" / "vv4_louder_wind_flutes_feature.json"
MODES = ("stock", "collection_progression", "immediate_fixed")
CHOICE = "VVFP VV4 Louder Flutes.txt"

LOAD_CALL, LOAD_THUNK = 0x40C4E1, 0x47099E
SITE_START, SITE_END = 0x40C4DE, 0x40C500          # push eax; push -2; call; test; mov [esi], eax; jne 0x40C500
FAKE_FMOD = 0x0C100000
FAKE_SAMPLE = 0x0C200000
FAKE_FILE = 0x0000C0DE
FAKE_HEAP = 0x0000BEEF
FMOD_STUBS = API_STUBS + 0xF000 if HAVE_EMULATOR else 0
MODE_PCM16_STEREO = 0x151                          # LOOP_OFF | 16BITS | STEREO | SIGNED, as the real fmod.dll says
MODE_PCM16_MONO = 0x111                            # LOOP_OFF | 16BITS | SIGNED
MODE_PCM8 = 0x0A9                                  # LOOP_OFF | 8BITS | STEREO | UNSIGNED

PCM = [0, 1, -1, 100, -100, 11474, -11474, 13107, 13108, -13107, -13108, -32768, 32767, 2, -2, 3, -3, 8497]
# A quiet note, a loud burst and a quiet tail (stereo): the limiter's ramps ahead of and after the burst.
BURST = [v for i in range(240) for v in
         (int((1500 if i < 80 or i >= 120 else 16000) * math.sin(i / 3.0)),
          int((1200 if i < 80 or i >= 120 else 15000) * math.cos(i / 5.0)))]

# The limiter, as native/vvfp_vv4_louder_flutes/vvfp_vv4_louder_flutes.c has it (24-bit fixed point).
ONE, CEILING, ATTACK, RELEASE = 1 << 24, 29204, 17312359, 16803516


def louder(values: list[int], n, channels: int = 2) -> list[int]:
    """The sample N x louder through the companion's limiter, exactly (N in tenths there: 5 is 50)."""
    tenths = round(n * 10)
    frames = len(values) // channels
    gain = []
    for f in range(frames):
        loud = max(abs(v) for v in values[f * channels:(f + 1) * channels]) * tenths // 10
        gain.append((CEILING << 24) // loud if loud > CEILING else ONE)
    for f in range(frames - 2, -1, -1):
        gain[f] = min(gain[f], (gain[f + 1] * ATTACK) >> 24)
    for f in range(1, frames):
        gain[f] = min(gain[f], (gain[f - 1] * RELEASE) >> 24)
    return [max(-32768, min(32767, (v * (tenths * gain[k // channels] // 10)) >> 24)) for k, v in enumerate(values)]


def rms(values: list[int]) -> float:
    return math.sqrt(sum(v * v for v in values) / len(values))


class Limiter(unittest.TestCase):
    """The limiter's arithmetic (the same in the companion, emulated below)."""

    def test_the_constants(self) -> None:
        self.assertEqual(CEILING, int(32768 * 10 ** (-1 / 20)))            # -1 dBFS
        self.assertEqual(ATTACK, round(ONE * 10 ** (3 / 220)))             # 3 dB per 220 frames
        self.assertEqual(RELEASE, round(ONE * 10 ** (3 / 4410)))           # 3 dB per 4,410 frames
        source = (ROOT / "native" / "vvfp_vv4_louder_flutes" / "vvfp_vv4_louder_flutes.c").read_text("utf-8")
        for name, value in (("LF_CEILING", CEILING), ("LF_ATTACK", ATTACK), ("LF_RELEASE", RELEASE),
                            ("LF_ONE", ONE)):
            self.assertIn(f"#define {name} {value}u", source)

    def test_never_over_the_ceiling_and_quiet_parts_get_all_of_it(self) -> None:
        for n in (2, 5, 10):
            with self.subTest(n=n):
                out = louder(BURST, n)
                self.assertLessEqual(max(abs(v) for v in out), CEILING)
                self.assertLessEqual(max(abs(v) for v in louder(PCM, n)), CEILING)
        # x 2 of a quiet sound is exactly twice it: nothing reaches the ceiling, nothing is limited.
        quiet = [v // 4 for v in BURST]
        self.assertEqual(louder(quiet, 2), [2 * v for v in quiet])

    def test_every_higher_setting_is_louder(self) -> None:
        levels = [rms(louder(BURST, n)) for n in (1, 2, 5, 10)]
        self.assertEqual(levels, sorted(levels))
        self.assertEqual(len(set(levels)), len(levels))

    def test_the_gain_changes_only_gradually(self) -> None:
        """No step: between neighbouring frames the gain moves by at most 3 dB / 220 frames (falling, ahead of a
        peak) -- what keeps the limiting clear rather than clipped."""
        n = 10
        out, src = louder(BURST, n), BURST
        ratios = [o / (n * s) for o, s in zip(out[::2], src[::2]) if abs(s) > 200]
        step = 10 ** (3 / 220 / 20) * 1.02
        for a, b in zip(ratios, ratios[1:]):
            self.assertLess(max(a, b) / min(a, b), step * 1.5)


class FakeFmod:
    """fmod.dll's four sample functions, as the real 3.74 answered for the flutes, and the setting file."""

    NAMES = ("_FSOUND_Sample_GetLength@4", "_FSOUND_Sample_GetMode@4", "_FSOUND_Sample_Lock@28",
             "_FSOUND_Sample_Unlock@20")

    def __init__(self, m: "Machine", *, present: bool = True, missing: str | None = None,
                 setting: bytes | None = None):
        self.m = m
        self.mode = MODE_PCM16_STEREO
        self.lock_ok = True
        self.short_by = 0                       # bytes Lock leaves out
        self.split = 0                          # bytes Lock puts in its second piece
        self.locks: list[tuple[int, int]] = []
        self.unlocks: list[tuple[int, int, int, int]] = []
        self.opened: list[str] = []
        self.setting = setting                  # the file's bytes (None: no file)
        self.buffer = 0
        self.frames = 0
        self.address = {}
        for i, name in enumerate(self.NAMES):
            at = FMOD_STUBS + 16 * i
            m.mu.mem_write(at, b"\xC3")
            if name != missing:
                self.address[name] = at
        m.stub(self.address.get(self.NAMES[0], 0) or 1, lambda p: (self.frames, 4))
        m.stub(self.address.get(self.NAMES[1], 0) or 2, lambda p: (self.mode, 4))
        m.stub(self.address.get(self.NAMES[2], 0) or 3, self._lock)
        m.stub(self.address.get(self.NAMES[3], 0) or 4, self._unlock)
        m.api_handlers["GetModuleHandleA"] = (
            lambda p: ((FAKE_FMOD if present and p.cstring(p.arg(0)).lower() == "fmod.dll" else 0), 4))
        m.api_handlers["GetProcAddress"] = (
            lambda p: ((self.address.get(p.cstring(p.arg(1)), 0) if p.arg(0) == FAKE_FMOD else 0), 8))
        m.api_handlers["CreateFileW"] = self._open
        m.api_handlers["ReadFile"] = self._read
        m.api_handlers["CloseHandle"] = lambda p: (1, 4)
        m.api_handlers["GetProcessHeap"] = lambda p: (FAKE_HEAP, 0)
        m.api_handlers["HeapAlloc"] = lambda p: (p.alloc(p.arg(2) + 16), 12)
        m.api_handlers["HeapFree"] = lambda p: (1, 12)

    def _open(self, p):
        path = p.wstring(p.arg(0))
        self.opened.append(path)
        if self.setting is None or not path.endswith("\\" + CHOICE):
            return 0xFFFFFFFF, 28
        return FAKE_FILE, 28

    def _read(self, p):
        handle, buffer, size, got = p.arg(0), p.arg(1), p.arg(2), p.arg(3)
        if handle != FAKE_FILE:
            return 0, 20
        data = (self.setting or b"")[:size]
        p.write(buffer, data)
        p.put32(got, len(data))
        return 1, 20

    def sample(self, values: list[int], channels: int = 2) -> None:
        """The sample FMOD made: 16-bit frames."""
        self.frames = len(values) // channels
        self.buffer = self.m.alloc(len(values) * 2 + 16)
        self.m.write(self.buffer, struct.pack(f"<{len(values)}h", *values))

    def pcm(self, n: int) -> list[int]:
        return list(struct.unpack(f"<{n}h", self.m.read(self.buffer, 2 * n)))

    def _lock(self, p):
        sample, offset, length, pp1, pp2, pl1, pl2 = (p.arg(i) for i in range(7))
        self.locks.append((offset, length))
        if not self.lock_ok or sample != FAKE_SAMPLE:
            return 0, 28
        whole = length - self.short_by
        first = whole - self.split
        p.put32(pp1, self.buffer)
        p.put32(pp2, self.buffer + first if self.split else 0)
        p.put32(pl1, first)
        p.put32(pl2, self.split)
        return 1, 28

    def _unlock(self, p):
        self.unlocks.append(tuple(p.arg(i) for i in range(1, 5)))
        return 1, 20


@unittest.skipUnless(HAVE_EMULATOR, "pefile/unicorn not installed")
class LouderWindFlutes(unittest.TestCase):
    def setUp(self) -> None:
        if not stock_path(4).is_file():
            self.skipTest("stock executable not present")
        if not DLL.is_file():
            self.skipTest("companion not built")

    def machine(self, mode: str = "stock", **fmod) -> tuple["Machine", FakeFmod]:
        exe = render(4, with_requirements(4, [ROW]), mode)
        m = Machine(exe, DLL)
        fake = FakeFmod(m, **fmod)
        self.loads: list[tuple[int, ...]] = []

        def load(p):
            self.loads.append(tuple(p.arg(i) for i in range(5)))
            return FAKE_SAMPLE, 20
        m.stub(LOAD_THUNK, load)
        return m, fake

    def load(self, m: "Machine", path: str) -> int:
        """The game's own loader at its FSOUND_Sample_Load call: `push eax` (the path) and `push -2` on the three
        zeros already pushed, the call, then the sample kept at [esi]."""
        text = m.alloc(len(path) + 1)
        m.write(text, path.encode("latin-1") + b"\0")
        holder = m.alloc(16)
        esp = STACK_TOP - 0x2000
        for _ in range(3):
            esp -= 4
            m.put32(esp, 0)
        m.set_reg("esp", esp)
        m.set_reg("eax", text)
        m.set_reg("esi", holder)
        m.run(SITE_START, SITE_END)
        self.assertEqual(m.reg("esp"), esp + 12,
                         "the call pops its five arguments (the three zeros the loader pushed first too), as stock")
        self.assertEqual(self.loads[-1], (0xFFFFFFFE, text, 0, 0, 0), "the same FSOUND_Sample_Load call")
        return m.u32(holder)

    def test_the_three_flutes_follow_the_slider(self) -> None:
        for n in (2, 5, 10, 0.5, 0.1, 1):
            for mode in (MODES if n == 5 else MODES[:1]):
                m, fake = self.machine(mode, setting=f"{n}\n".encode())
                m.export("VvfpStartup", 4, 0)
                self.assertEqual(m.export("VvfpLouderFlutesInstalled"), 1, mode)
                self.assertEqual(m.export("VvfpLouderFlutesMultiplier"), round(n * 10))
                self.assertTrue(fake.opened and fake.opened[-1].endswith("\\" + CHOICE), fake.opened)
                for k, path in enumerate(("Sounds/Flute1.ogg", "Sounds\\FLUTE3.OGG",
                                          "C:\\Games\\Tree\\Sounds\\flute5.ogg")):
                    with self.subTest(n=n, mode=mode, path=path):
                        fake.sample(PCM)
                        self.assertEqual(self.load(m, path), FAKE_SAMPLE)
                        self.assertEqual(fake.pcm(len(PCM)), louder(PCM, n))
                        self.assertEqual(fake.locks[-1], (0, len(PCM) * 2), "the whole sample, from its start")
                        self.assertEqual(len(fake.unlocks), k + 1, "every lock is unlocked")
                self.assertEqual(m.export("VvfpLouderFlutesScaled"), 3)

    def test_a_loud_burst_is_held_under_the_ceiling_with_gradual_gain(self) -> None:
        for n in (2, 5, 10):
            with self.subTest(n=n):
                m, fake = self.machine(setting=str(n).encode())
                m.export("VvfpStartup", 4, 0)
                fake.sample(BURST)
                self.load(m, "Sounds/Flute1.ogg")
                out = fake.pcm(len(BURST))
                self.assertEqual(out, louder(BURST, n))
                self.assertLessEqual(max(abs(v) for v in out), CEILING)

    def test_a_mono_sample_is_made_louder_too(self) -> None:
        m, fake = self.machine(setting=b"10")
        m.export("VvfpStartup", 4, 0)
        fake.mode = MODE_PCM16_MONO
        fake.sample(PCM, channels=1)
        self.load(m, "Sounds/Flute3.ogg")
        self.assertEqual(fake.pcm(len(PCM)), louder(PCM, 10, channels=1))

    def test_the_setting_file(self) -> None:
        # In tenths: 50 is 5.
        cases = ((b"2", 20), (b"10\n", 100), (b"100\r\n", 100), (b" 42 ", 100), (b"\t7", 70), (b"0", 1), (b"1", 10),
                 (b"101", 100), (b"99999999999999", 100), (b"abc", 50), (b"", 50), (b"-3", 50), (None, 50),
                 (b"0.5", 5), (b"0.1", 1), (b".3\n", 3), (b"2.5", 25))
        for setting, wanted in cases:
            with self.subTest(setting=setting):
                m, fake = self.machine(setting=setting)
                m.export("VvfpStartup", 4, 0)
                self.assertEqual(m.export("VvfpLouderFlutesMultiplier"), wanted)

    def test_every_other_sound_is_left_as_loaded(self) -> None:
        m, fake = self.machine(setting=b"10")
        m.export("VvfpStartup", 4, 0)
        for path in ("Sounds/song1.ogg", "Sounds/wind1.wav", "Sounds/chimes1.ogg", "Sounds/Flute2.ogg",
                     "Sounds/Flute1.ogg.bak", "Sounds/myFlute1.ogg", "Flute1"):
            with self.subTest(path=path):
                fake.sample(PCM)
                self.assertEqual(self.load(m, path), FAKE_SAMPLE)
                self.assertEqual(fake.pcm(len(PCM)), PCM)
        self.assertEqual(fake.locks, [])
        self.assertEqual(m.export("VvfpLouderFlutesScaled"), 0)

    def test_a_sample_that_is_not_whole_16_bit_pcm_is_left_alone(self) -> None:
        cases = (("8-bit", {"mode": MODE_PCM8}, False), ("lock refused", {"lock_ok": False}, False),
                 ("handed back short", {"short_by": 4}, True))
        for name, setting, locked in cases:
            with self.subTest(name):
                m, fake = self.machine()
                m.export("VvfpStartup", 4, 0)
                for key, value in setting.items():
                    setattr(fake, key, value)
                fake.sample(PCM)
                self.assertEqual(self.load(m, "Sounds/Flute1.ogg"), FAKE_SAMPLE)
                self.assertEqual(fake.pcm(len(PCM)), PCM)
                self.assertEqual(len(fake.unlocks), 1 if locked else 0)
                self.assertEqual(m.export("VvfpLouderFlutesScaled"), 0)

    def test_a_sample_handed_back_in_two_pieces_is_all_made_louder(self) -> None:
        m, fake = self.machine()
        m.export("VvfpStartup", 4, 0)
        fake.split = 14                         # the second piece starts inside a stereo frame
        fake.sample(PCM)
        self.load(m, "Sounds/Flute5.ogg")
        self.assertEqual(fake.pcm(len(PCM)), louder(PCM, 5))

    def test_nothing_is_installed_without_fmod_or_in_another_game(self) -> None:
        for name, kwargs, game in (("no fmod.dll", {"present": False}, 4),
                                   ("no Sample_Lock", {"missing": "_FSOUND_Sample_Lock@28"}, 4),
                                   ("another game", {}, 3)):
            with self.subTest(name):
                m, fake = self.machine(**kwargs)
                before = m.read(LOAD_CALL, 5)
                m.export("VvfpStartup", game, 0)
                self.assertEqual(m.export("VvfpLouderFlutesInstalled"), 0)
                self.assertEqual(m.read(LOAD_CALL, 5), before)
                fake.sample(PCM)
                self.load(m, "Sounds/Flute1.ogg")
                self.assertEqual(fake.pcm(len(PCM)), PCM)

    def test_the_row(self) -> None:
        row = json.loads(FEATURE.read_text("utf-8"))
        self.assertEqual(row["game_id"], "vv4")
        self.assertEqual(row["patches"], [])
        self.assertEqual(row["dependencies"], [])
        self.assertEqual([d["va"] for d in row["runtime_detours"]], ["0x40C4E1"])
        stock = stock_path(4).read_bytes()
        self.assertEqual(stock[LOAD_CALL - 0x400000:LOAD_CALL - 0x400000 + 5].hex().upper(),
                         row["runtime_detours"][0]["stock_bytes"])
        # The stock call goes to the Sample_Load thunk, the only call of it in the game.
        rel = struct.unpack_from("<i", stock, LOAD_CALL - 0x400000 + 1)[0]
        self.assertEqual(LOAD_CALL + 5 + rel, LOAD_THUNK)
        text = stock[0x1000:0x8A000]
        callers = [0x401000 + i for i in range(len(text) - 5) if text[i] == 0xE8
                   and (0x401000 + i + 5 + struct.unpack_from("<i", text, i + 1)[0]) & 0xFFFFFFFF == LOAD_THUNK]
        self.assertEqual(callers, [LOAD_CALL])
        self.assertIn("0.1 to 10 times", row["description"])
        self.assertIn("5 unless you move it", row["description"])
        self.assertIn(CHOICE, row["description"])


class Setting(unittest.TestCase):
    """The patcher's side: the slider's number, 0.1 to 10 in tenths (5 by default), written beside the companion."""

    def setUp(self) -> None:
        self.saved = patcher.louder_flutes_multiplier()
        self.addCleanup(patcher.set_louder_flutes_multiplier, self.saved)

    def test_tenths_from_a_tenth_to_100_default_5(self) -> None:
        self.assertEqual(patcher.LOUDER_FLUTES_MULTIPLIER_DEFAULT, 5)
        r = patcher.LOUDER_FLUTES_MULTIPLIER_RANGE
        self.assertEqual((r[0], r[-1], len(r)), (0.1, 10, 100))
        for good in (1, 0.1, 2.5, 2, 5, 10):
            self.assertEqual(patcher.set_louder_flutes_multiplier(good), good)
            self.assertEqual(patcher.louder_flutes_multiplier(), good)
        for bad in (0, 10.1, 100, 101, -5, 0.05, "5", True, None):
            with self.subTest(bad=bad), self.assertRaises(patcher.PatcherError):
                patcher.set_louder_flutes_multiplier(bad)
        self.assertEqual(patcher.louder_flutes_multiplier(), 10)       # a refused number changes nothing

    def test_written_beside_the_companion_only_with_the_row(self) -> None:
        row = next(p for p in patcher.load_public_fun_patches() if p.id == ROW)
        other = next(p for p in patcher.load_public_fun_patches() if p.id == "vv4_children_play")
        for n in (2, 10, 0.5):
            with tempfile.TemporaryDirectory() as out, self.subTest(n=n):
                patcher.set_louder_flutes_multiplier(n)
                patcher._write_louder_flutes_choice(Path(out), [other])
                self.assertEqual(list(Path(out).rglob(CHOICE)), [])
                patcher._write_louder_flutes_choice(Path(out), [row])
                beside = Path(out) / Path(*patcher.patcher_files.installed_relative_path(
                    "VVFP VV4 Louder Flutes.dll").parts).parent / CHOICE
                self.assertEqual(list(Path(out).rglob(CHOICE)), [beside])
                self.assertEqual(beside.read_bytes(), f"{n}\n".encode())

    def test_the_command_line(self) -> None:
        import argparse
        parser = argparse.ArgumentParser()
        patcher._add_check_logs_arg(parser)
        self.assertIsNone(parser.parse_args([]).louder_flutes_multiplier)
        for n in ("2", "10", "1", "0.5"):
            self.assertEqual(parser.parse_args(["--louder-flutes-multiplier", n]).louder_flutes_multiplier, float(n))
        for bad in ("0", "10.1", "101", "x"):
            with self.subTest(value=bad), self.assertRaises(SystemExit):
                parser.parse_args(["--louder-flutes-multiplier", bad])

    def test_the_patch_log_and_kept_files_name_it(self) -> None:
        source = (ROOT / "src" / "vv_fun_patcher.py").read_text("utf-8")
        self.assertEqual(source.count('**({"louder_flutes_multiplier": _louder_flutes_multiplier}'), 2)
        self.assertIn("relatives.append(str(installed.parent / LOUDER_FLUTES_CHOICE_FILE))", source)
        self.assertRegex(source, r"    _write_louder_flutes_choice\(output_folder, fun_patches\)\n"
                                 r"(    _write_\w+\(output_folder, fun_patches\)\n)*    return copied")
        report = (ROOT / "src" / "transparency.py").read_text("utf-8")
        self.assertIn("(the Louder Wind Flutes slider)", report)


class Defaults(unittest.TestCase):
    def test_on_by_default_and_in_owners_defaults(self) -> None:
        from vv_fun_patcher_gui import (default_fun_patch_selection, owners_default_fun_patch_selection,
                                        select_all_fun_patch_selection)
        self.assertTrue(default_fun_patch_selection(ROW))
        self.assertTrue(owners_default_fun_patch_selection(ROW))
        self.assertTrue(select_all_fun_patch_selection(ROW))


if __name__ == "__main__":
    unittest.main()
