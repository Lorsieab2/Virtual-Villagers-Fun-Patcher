"""The logs at village creation: the save the Cause of Death companion asks for.

Live, v1.35.66: A New Home's first village wrote no log until the first quit,
and The Tree of Life created its logs empty -- its creation save runs before
the five founders are picked -- and logged the founders only at the quit.
New Believers makes its new village the same way.  Once a new village's
founders are made and it has started, the companion sets the game's own
next-autosave time to 0 (native/vvfp_cause_of_death/cod_creation_save.inc),
so the game's normal save-all runs on its next frame and every save hook
writes the logs.

This pins, in the stock executables, every field that decision reads and
writes: the autosave routine compares the field with the clock and re-arms it
600 s on, the save manager singleton, the slot, the scene and the start time,
and the routines that set the village's own scene and its start time.
"""
from __future__ import annotations

import re
import struct
import unittest
from pathlib import Path

try:
    import capstone
except ImportError:  # pragma: no cover
    capstone = None

ROOT = Path(__file__).resolve().parents[1]
STOCK = {
    1: ROOT / "research/stock-executables/Virtual Villagers - A New Home.exe",
    4: ROOT / "research/stock-executables/Virtual Villagers - The Tree of Life.exe",
    5: ROOT / "research/stock-executables/Virtual Villagers - New Believers.exe",
}
SOURCE = ROOT / "native/vvfp_cause_of_death/cod_creation_save.inc"

# game: (autosave routine, its length to read, manager, slot, scene, main scene, autosave field, start)
FIELDS = {
    1: (0x41BFC0, 0x40, 0x48AEDC, 0xABE4, 0xACB4, 1, 0xADEC, ("field", 0x9E1C)),
    4: (0x41F1A0, 0x40, 0x4CB51C, 0x17114, 0x171A8, 0, 0x171C0, ("global", 0x4D6DE0)),
    5: (0x424660, 0x40, 0x4DACE0, 0x17D80, 0x17E1C, 0, 0x17E34, ("global", 0x51D358)),
}
# Where the start time is set when the village begins (the start-or-skip
# scene's button in A New Home, the start-game step in the later two).
START_WRITERS = {1: (0x41EC40, 0x200), 4: (0x41FEF0, 0x80), 5: (0x4259D0, 0x80)}


def _image(game):
    data = STOCK[game].read_bytes()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, pe + 6)[0]
    opt = struct.unpack_from("<H", data, pe + 20)[0]
    sections = []
    for i in range(count):
        e = pe + 24 + opt + i * 40
        sections.append((0x400000 + struct.unpack_from("<I", data, e + 12)[0],
                         struct.unpack_from("<I", data, e + 8)[0],
                         struct.unpack_from("<I", data, e + 20)[0]))

    def read(va, n):
        for base, size, raw in sections:
            if base <= va < base + size:
                return data[raw + va - base: raw + va - base + n]
        raise AssertionError(f"{va:#x} is in no section")
    return read


@unittest.skipIf(capstone is None, "capstone is not installed")
class CreationSaveFields(unittest.TestCase):
    def _code(self, game, va, n):
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        return [f"{i.mnemonic} {i.op_str}" for i in md.disasm(_image(game)(va, n), va)]

    def test_the_autosave_compares_the_field_and_rearms_it_600_seconds_on(self):
        for game, (routine, length, manager, _slot, _scene, _main, field, _start) in FIELDS.items():
            with self.subTest(game=game):
                code = " ; ".join(self._code(game, routine, length))
                self.assertRegex(code, rf"cmp dword ptr \[\w+ \+ {field:#x}\], eax", code)
                self.assertRegex(code, r"add eax, 0x258", code)
                self.assertRegex(code, rf"mov dword ptr \[\w+ \+ {field:#x}\], eax", code)

    def test_the_start_time_is_set_when_the_village_begins(self):
        for game, (va, n) in START_WRITERS.items():
            kind, where = FIELDS[game][7]
            with self.subTest(game=game):
                code = " ; ".join(self._code(game, va, n))
                if kind == "field":
                    self.assertRegex(code, rf"mov dword ptr \[\w+ \+ {where:#x}\], \w+", code)
                else:
                    self.assertIn(f"dword ptr [{where:#x}]", code)

    def test_the_scene_field_turns_to_the_village_after_the_founders(self):
        # The founder screen's handler (VV4 0x43BC00, VV5 0x43E600) and A New
        # Home's start-or-skip scene (0x41F310) set the village's own scene.
        for game, va, at in ((4, 0x43BC00, 0x43BD2F), (5, 0x43E600, 0x43E72F), (1, 0x41F310, 0x41F455)):
            _r, _l, _m, _slot, scene, main, *_rest = FIELDS[game]
            with self.subTest(game=game):
                md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
                code = {i.address: f"{i.mnemonic} {i.op_str}" for i in md.disasm(_image(game)(va, 0x200), va)}
                self.assertRegex(code.get(at, ""), rf"mov dword ptr \[\w+ \+ {scene:#x}\], {main}$")

    def test_the_slot_field_is_the_one_every_save_uses(self):
        # The same managers and slot fields native/shared/game_save_slot.h reads.
        header = (ROOT / "native/shared/game_save_slot.h").read_text(encoding="utf-8")
        for game, (_r, _l, manager, slot, *_rest) in FIELDS.items():
            with self.subTest(game=game):
                self.assertIn(f"0x{manager:08X}u", header)
                self.assertIn(f"0x{slot:X}u", header)

    def test_the_companion_uses_these_fields(self):
        text = SOURCE.read_text(encoding="utf-8")
        for game, (_r, _l, manager, slot, scene, main, field, start) in FIELDS.items():
            kind, where = start
            row = (f"{{ 0x{manager:X}u, 0x{slot:X}u, 0x{scene:X}u, {main}u, 0x{field:X}u, "
                   + (f"0x{where:X}u, 0u }}" if kind == "field" else f"0u, 0x{where:X}u }}"))
            with self.subTest(game=game):
                self.assertIn(row, text)
        self.assertIn("CREATION_SAVE[g_game].autosave) = 0u;", text)


if __name__ == "__main__":
    unittest.main()
