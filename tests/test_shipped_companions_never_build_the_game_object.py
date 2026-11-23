"""The SHIPPED Story DLL and Origins companions hold no call to a getter that can build the game object.

The New Believers start-up crash came back in the owner's v1.35.97 test build (2026-11-19): c00000fd in _chkstk at
0x47EBB7, the stack full of the same round -- the getter 0x425950 building the game object, its constructor's
settings read 0x425640 (a 0x17E04-byte frame), buildSavePath's detour, Vv5InstallCompanions, the Story DLL's
install, and the Story DLL calling 0x425950 again (VVFP Story Upgrades.dll+0x3ADEF: mov eax, 0x425950; call eax).

The SOURCE was fixed (e84f510e7, #808: every callback reads the object's word instead), but a branch that rebuilt
VVFP Story Upgrades.dll before that fix was merged after it, and the merge kept that branch's binary.  The DLL in
the build was therefore older than its source.  The emulation in tests/test_vv5_story_startup_no_recursion.py
catches that too when it runs.  This test is quick and needs no game executable, so it runs everywhere (CI included).
It reads the binaries that ship: no startup-reachable companion may load a game-object getter's address into a
register or push it (the way MSVC calls a fixed address from a DLL).
"""
from __future__ import annotations

import re
import struct
import unittest
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
STOCK_DIR = ROOT / "research" / "stock-executables"

# Each game's lazily-building game-object getter -> the word it keeps the object in (read that word instead), and
# VV2's preferences object, whose init hook also runs inside its constructor (e84f510e7).
GETTERS = {
    1: {0x41D500: 0x48AEDC},
    2: {0x426D40: 0x4997BC, 0x44F4E0: 0x499F24},
    3: {0x428B60: 0x4B309C},
    4: {0x41FE70: 0x4CB51C},
    5: {0x425950: 0x4DACE0},
}
EXES = {1: "Virtual Villagers - A New Home.exe", 2: "Virtual Villagers - The Lost Children.exe",
        3: "Virtual Villagers - The Secret City.exe", 4: "Virtual Villagers - The Tree of Life.exe",
        5: "Virtual Villagers - New Believers.exe"}
STORY = ROOT / "assets" / "story_upgrades" / "VVFP Story Upgrades.dll"
# The companions that host the Story DLL and run from start-up hooks, each for its own game.
HOSTS = {
    1: ROOT / "assets" / "origins" / "VVFP VV1 Origins Icons.dll",
    2: ROOT / "assets" / "origins" / "VVFP VV2 Origins Icons.dll",
    3: ROOT / "data" / "candidates" / "VVFP VV3 Full Mastery Candidate.dll",
    4: ROOT / "assets" / "origins" / "VVFP VV4 Origins Icons.dll",
    5: ROOT / "data" / "candidates" / "VVFP VV5 Task9 Origins Icons.dll",
}
# Other single-game companions, held to the same rule (the owner, 2026-11-18: no companion calls a getter that can
# build the game object) though their hooks run only in play.  A file a branch does not have yet is skipped.
OTHERS = {
    4: (ROOT / "assets" / "cloth_sacks" / "VVFP VV4 Cloth Sacks.dll",
        ROOT / "assets" / "empty_sources" / "VVFP VV4 Empty Sources.dll"),
    5: (ROOT / "assets" / "devotion_faith" / "VVFP Devotion Faith.dll",
        ROOT / "assets" / "heathen_aging" / "VVFP Heathen Aging.dll"),
}
LOADS = {0xB8, 0xB9, 0xBA, 0xBB, 0xBD, 0xBE, 0xBF, 0x68}   # mov r32, imm32 (not esp) / push imm32


def code_of(dll: Path) -> bytes:
    pe = pefile.PE(str(dll), fast_load=True)
    return b"".join(s.get_data() for s in pe.sections if s.Characteristics & 0x20000000)   # executable sections


def getter_loads(code: bytes, getter: int) -> list[int]:
    imm = struct.pack("<I", getter)
    return [m.start() - 1 for m in re.finditer(re.escape(imm), code) if m.start() and code[m.start() - 1] in LOADS]


class ShippedCompanionsNeverBuildTheGameObject(unittest.TestCase):

    def test_the_story_dll_calls_no_game_object_getter(self):
        code = code_of(STORY)
        for game, getters in GETTERS.items():
            for getter, word in getters.items():
                with self.subTest(game=game, getter=hex(getter)):
                    self.assertEqual(getter_loads(code, getter), [],
                                     f"{STORY.name} calls VV{game}'s getter 0x{getter:X}: read 0x{word:X} instead "
                                     "(and rebuild the DLL from its source)")

    def test_each_host_companion_calls_no_game_object_getter_of_its_game(self):
        for game, dll in HOSTS.items():
            code = code_of(dll)
            for getter, word in GETTERS[game].items():
                with self.subTest(dll=dll.name, getter=hex(getter)):
                    self.assertEqual(getter_loads(code, getter), [],
                                     f"{dll.name} calls the getter 0x{getter:X}: read 0x{word:X} instead")

    def test_other_single_game_companions_call_no_game_object_getter_of_their_game(self):
        for game, dlls in OTHERS.items():
            for dll in dlls:
                if not dll.is_file():
                    continue
                code = code_of(dll)
                for getter, word in GETTERS[game].items():
                    with self.subTest(dll=dll.name, getter=hex(getter)):
                        self.assertEqual(getter_loads(code, getter), [],
                                         f"{dll.name} calls the getter 0x{getter:X}: read 0x{word:X} instead")

    @unittest.skipUnless(all((STOCK_DIR / n).is_file() for n in EXES.values()), "the stock executables are absent")
    def test_each_address_is_that_games_building_getter_of_that_word(self):
        from test_story_host_callbacks_never_build import building_getters
        for game, getters in GETTERS.items():
            found = building_getters(STOCK_DIR / EXES[game])
            for getter, word in getters.items():
                with self.subTest(game=game, getter=hex(getter)):
                    self.assertEqual(found.get(getter), word)


if __name__ == "__main__":
    unittest.main()
