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
# Where the start time is set when the village begins (the Start / "?"
# scene's Start button in A New Home, the start-game step in the later two).
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
        # Home's Start / "?" scene (0x41F310) set the village's own scene.
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

    def test_a_new_homes_hidden_f1_key_never_sets_the_start_time(self):
        # 0x41F480 is the intro scene's command handler; command 0x3FA is the hidden F1 key on the
        # Start / "?" screen of a new village (there is no Skip button; apparently a leftover
        # developer shortcut). It hides the scene and sets the
        # village's scene without touching [manager+0x9E1C], so the village is never "started" and
        # the save-all (0x41BF70) skips its slot -- and the creation save is made another way.
        code = self._code(1, 0x41F480, 0x58)
        text = " ; ".join(code)
        self.assertIn("sub eax, 0x3fa", text)
        self.assertRegex(text, r"mov dword ptr \[eax \+ 0xacb4\], 1", text)
        self.assertNotIn("0x9e1c", text)

    def test_the_later_games_have_one_way_in_and_it_sets_the_start_time(self):
        # The Tree of Life and New Believers: the start-game step (VV4 0x41FEF0, VV5 0x4259D0) is
        # called from exactly two places, the founder screen's handler and one more, and each sets
        # the village's scene only after it: there is no way into the village that leaves the start
        # time at 0 (A New Home's hidden F1 key has no counterpart), so they need no direct save.
        for game, step, callers in ((4, 0x41FEF0, (0x43BD26, 0x43DBF9)), (5, 0x4259D0, (0x43E726, 0x4404D9))):
            with self.subTest(game=game):
                read = _image(game)
                found = []
                text = read(0x401000, 0x80000)
                for i in range(len(text) - 5):
                    if text[i] == 0xE8:
                        rel = struct.unpack_from("<i", text, i + 1)[0]
                        if (0x401000 + i + 5 + rel) & 0xFFFFFFFF == step:
                            found.append(0x401000 + i)
                self.assertEqual(tuple(found), callers)
                start_global = FIELDS[game][7][1]
                self.assertIn(f"dword ptr [{start_global:#x}], eax", " ; ".join(self._code(game, step, 0x80)))

    def test_the_save_all_skips_a_village_that_never_started(self):
        code = self._code(1, 0x41BF70, 0x30)
        text = " ; ".join(code)
        self.assertRegex(text, r"mov eax, dword ptr \[esi \+ 0x9e1c\] ; test eax, eax ; je ", text)

    def test_the_quit_saves_the_slot_through_the_managers_own_virtual_save(self):
        # The quit routine (0x41B230) pushes [manager+0xABE4] and calls virtual +0x38: the call the
        # companion makes for a village that never started (cod_creation_save.inc).
        code = self._code(1, 0x41B230, 0x2A)
        text = " ; ".join(code)
        self.assertRegex(text, r"mov edx, dword ptr \[ecx \+ 0xabe4\] ; mov eax, dword ptr \[ecx\] ; push edx ; "
                               r"call dword ptr \[eax \+ 0x38\]", text)
        # That virtual (the manager's vtable 0x459690, entry 0x41BF10) is a thiscall that takes the slot
        # and pops it ("ret 4"): a slot writes the village's 0xABDC bytes, 0 the settings.
        save = " ; ".join(self._code(1, 0x41BF10, 0x60))
        self.assertIn("mov edi, dword ptr [esp + 0xc]", save)
        self.assertIn("push 0xabdc", save)
        self.assertIn("ret 4", save)
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("vtable[0x38 / 4])(manager, NULL, slot)", source)
        self.assertIn("typedef int (__fastcall *creation_slot_save_fn)(void *self, void *unused_edx, int slot);", source)

    def test_the_founder_screen_is_scene_3_and_the_autosave_runs_on_it(self):
        # The live round 7 (2026-11-21, VV4 "R7 Test"): the game's autosave saved while "Select 5
        # villagers" was open, and the logs took the candidate on show for a founder.  Pinned here:
        #  - the screen is the manager's scene 3 (VV4 0x43DB45 / VV5 0x440425: `neg; sbb; and -3;
        #    add 3` of the new-village flag, so 3 when it is 0);
        #  - each candidate goes in record [screen+0x18], the number chosen so far, after that
        #    record's present byte is cleared (VV4 0x43B830 / VV5 0x43E220): a Reject replaces the
        #    candidate in the same record;
        #  - the autosave (0x41F1A0 / 0x424660) reads no scene: it saves on every screen;
        #  - the companion holds every save made in scene 3, and the History skips it.
        cases = {
            4: (0x43DB30, 0x43DB45, 0x43B830, 0x1CC4),
            5: (0x440410, 0x440425, 0x43E220, 0x1CD4),
        }
        for game, (scene_code, scene_store, candidate, present) in cases.items():
            scene = FIELDS[game][4]
            with self.subTest(game=game):
                code = " ; ".join(self._code(game, scene_code, scene_store - scene_code + 6))
                self.assertRegex(code, r"neg esi ; sbb esi, esi ; and esi, 0xfffffffd ; add esi, 3 ; call 0x[0-9a-f]+ ; "
                                       rf"mov dword ptr \[eax \+ {scene:#x}\], esi$", code)
                make = " ; ".join(self._code(game, candidate, 0x20))
                self.assertRegex(make, r"^sub esp, 0x10 ; mov eax, dword ptr \[ecx \+ 0x18\] ; mov dword ptr \[esp \+ 4\], ecx ; "
                                       rf"push eax ; mov ecx, 0x[0-9a-f]+ ; call 0x[0-9a-f]+ ; test eax, eax ; je 0x[0-9a-f]+ ; "
                                       rf"mov byte ptr \[eax \+ {present:#x}\], 0", make)
                autosave = " ; ".join(self._code(game, FIELDS[game][0], FIELDS[game][1]))
                self.assertNotIn(f"{scene:#x}", autosave)
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("#define FOUNDER_SCENE 3u", source)
        self.assertIn("CREATION_SAVE[g_game].state) == FOUNDER_SCENE", source)
        roster = (ROOT / "native/vvfp_cause_of_death/cod_roster.inc").read_text(encoding="utf-8")
        done = roster[roster.index("static void cod_save_done("):]
        done = done[:done.index("\n}\n")]
        self.assertLess(done.index("if (founder_screen_open()) {"), done.index("backfill_at_save(slot, save_buffer);"))
        population = (ROOT / "native/population_export/population_export.c").read_text(encoding="utf-8")
        self.assertIn("{ 0, 0, 0, 0, 0xCB51Cu, 0xDACE0u }", population)
        self.assertIn("{ 0, 0, 0, 0, 0x171A8u, 0x17E1Cu }", population)
        self.assertIn("if (!founder_screen_open(game_id, module)) {\n        (void)append_history(", population)

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
