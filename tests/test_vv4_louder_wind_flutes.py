"""The Tree of Life's "Louder Wind Flutes" (the owner, 2026-11-10: "make the sound volume for just the wind flutes a
bit louder so they're clearly heard above the game music"; after a preview of 2.5 times: "yes make the patch").

EMULATED, on the executable the patcher renders for the row, in each of the three public modes:

* "VVFP VV4 Louder Flutes.dll" is started as VVFP Startup.dll starts it (VvfpStartup(4, ...)), with a stand-in
  fmod.dll that behaves as the real fmod.dll 3.74 was seen to (a scratch 32-bit probe on 2026-11-10: each flute
  loads as mode 0x151 -- 16-bit, stereo, signed PCM -- and FSOUND_Sample_Lock hands back the whole sample);
* the game's own sound loader runs its call of FSOUND_Sample_Load (0x40C4DE..0x40C500, the one call every sound
  effect is loaded through), with the thunk 0x47099E stood in for.

Then Flute1.ogg, Flute3.ogg and Flute5.ogg come back 2.5 times louder (kept within the 16-bit range), and every
other sound, a sample that is not 16-bit signed PCM, and one FMOD will not hand back whole, exactly as loaded.
Without fmod.dll's functions, or in another game, nothing is installed.
"""
from __future__ import annotations

import json
import struct
import sys
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

ROW = "vv4_louder_wind_flutes"
DLL = ROOT / "assets" / "vv4_louder_flutes" / "VVFP VV4 Louder Flutes.dll"
FEATURE = ROOT / "data" / "vv4_louder_wind_flutes_feature.json"
MODES = ("stock", "collection_progression", "immediate_fixed")

LOAD_CALL, LOAD_THUNK = 0x40C4E1, 0x47099E
SITE_START, SITE_END = 0x40C4DE, 0x40C500          # push eax; push -2; call; test; mov [esi], eax; jne 0x40C500
FAKE_FMOD = 0x0C100000
FAKE_SAMPLE = 0x0C200000
FMOD_STUBS = API_STUBS + 0xF000 if HAVE_EMULATOR else 0
MODE_PCM16_STEREO = 0x151                          # LOOP_OFF | 16BITS | STEREO | SIGNED, as the real fmod.dll says
MODE_PCM8 = 0x0A9                                  # LOOP_OFF | 8BITS | STEREO | UNSIGNED

PCM = [0, 1, -1, 100, -100, 11474, -11474, 13107, 13108, -13107, -13108, -32768, 32767, 2, -2, 3, -3, 8497]


def louder(v: int) -> int:
    """5/2 with C's truncation toward zero, kept within 16 bits."""
    scaled = int(v * 5 / 2)
    return max(-32768, min(32767, scaled))


class FakeFmod:
    """fmod.dll's four sample functions, as the real 3.74 answered for the flutes."""

    NAMES = ("_FSOUND_Sample_GetLength@4", "_FSOUND_Sample_GetMode@4", "_FSOUND_Sample_Lock@28",
             "_FSOUND_Sample_Unlock@20")

    def __init__(self, m: "Machine", *, present: bool = True, missing: str | None = None):
        self.m = m
        self.mode = MODE_PCM16_STEREO
        self.lock_ok = True
        self.short_by = 0                       # bytes Lock leaves out
        self.split = 0                          # bytes Lock puts in its second piece
        self.locks: list[tuple[int, int]] = []
        self.unlocks: list[tuple[int, int, int, int]] = []
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

    def sample(self, values: list[int]) -> None:
        """The sample FMOD made: stereo 16-bit frames."""
        self.frames = len(values) // 2
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

    def test_the_three_flutes_load_two_and_a_half_times_louder(self) -> None:
        for mode in MODES:
            m, fake = self.machine(mode)
            m.export("VvfpStartup", 4, 0)
            self.assertEqual(m.export("VvfpLouderFlutesInstalled"), 1, mode)
            for n, path in enumerate(("Sounds/Flute1.ogg", "Sounds\\FLUTE3.OGG", "C:\\Games\\Tree\\Sounds\\flute5.ogg")):
                with self.subTest(mode=mode, path=path):
                    fake.sample(PCM)
                    self.assertEqual(self.load(m, path), FAKE_SAMPLE)
                    self.assertEqual(fake.pcm(len(PCM)), [louder(v) for v in PCM])
                    self.assertEqual(fake.locks[-1], (0, len(PCM) * 2), "the whole sample, from its start")
                    self.assertEqual(len(fake.unlocks), n + 1, "every lock is unlocked")
            self.assertEqual(m.export("VvfpLouderFlutesScaled"), 3)

    def test_the_numbers(self) -> None:
        self.assertEqual([louder(v) for v in (11474, 8497, 8787)], [28685, 21242, 21967])
        self.assertEqual(louder(13107), 32767)
        self.assertEqual(louder(13108), 32767)
        self.assertEqual(louder(-13108), -32768)
        self.assertEqual(louder(-3), -7)

    def test_every_other_sound_is_left_as_loaded(self) -> None:
        m, fake = self.machine()
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
        fake.split = 12
        fake.sample(PCM)
        self.load(m, "Sounds/Flute5.ogg")
        self.assertEqual(fake.pcm(len(PCM)), [louder(v) for v in PCM])

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


@unittest.skipUnless(HAVE_EMULATOR, "pefile/unicorn not installed")
class Defaults(unittest.TestCase):
    def test_on_by_default_and_in_owners_defaults(self) -> None:
        from vv_fun_patcher_gui import (default_fun_patch_selection, owners_default_fun_patch_selection,
                                        select_all_fun_patch_selection)
        self.assertTrue(default_fun_patch_selection(ROW))
        self.assertTrue(owners_default_fun_patch_selection(ROW))
        self.assertTrue(select_all_fun_patch_selection(ROW))


if __name__ == "__main__":
    unittest.main()
