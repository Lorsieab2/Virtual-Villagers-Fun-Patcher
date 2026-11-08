"""Science Collectibles Only Count When Complete (The Tree of Life, New Believers): a research step's collectible
bonus counts only a complete set.  The traces are in scripts/build_science_collectibles_complete_features.py.

The research step's bonus is run stock and patched in unicorn from the count's return to the fire's check, for
every piece count, with the game's own rand helper (the C runtime's rand stubbed to its lowest and highest result)
and the tech-point adder recorded.  Tests that need the stock executables skip when they are absent.
"""
from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher_gui import (default_fun_patch_selection, owners_default_fun_patch_selection,  # noqa: E402
                                select_all_fun_patch_selection)
import vv_fun_patcher as patcher  # noqa: E402

try:
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_EIP, UC_X86_REG_ESP
    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

STOCK_DIR = ROOT / "research" / "stock-executables"
GAMES = {
    # game: exe, start (the count's return), end (the fire's check), the tech-point adder, the C runtime's rand,
    # the pieces in the set
    "vv4": ("Virtual Villagers - The Tree of Life.exe", 0x464E6F, 0x464E87, 0x41E300, 0x471CF8, 12),
    "vv5": ("Virtual Villagers - New Believers.exe", 0x46DE5F, 0x46DE7C, 0x4237B0, 0x47CFD8, 24),
}
CRT_LOW, CRT_HIGH = 0, 0x7FFF


def feature(game: str) -> dict:
    return json.loads((ROOT / "data" / f"{game}_science_collectibles_complete_feature.json").read_text("utf-8"))


def image(game: str, patched: bool) -> tuple[bytes, "pefile.PE"]:
    exe = STOCK_DIR / GAMES[game][0]
    data = bytearray(exe.read_bytes())
    if patched:
        for p in feature(game)["patches"]:
            at, before, after = int(p["offset"], 16), bytes.fromhex(p["before"]), bytes.fromhex(p["after"])
            assert data[at:at + len(before)] == before
            data[at:at + len(after)] = after
    return bytes(data), pefile.PE(data=bytes(data), fast_load=True)


STACK = 0x0100_0000
_EMULATORS: dict = {}


def emulator(game: str, patched: bool):
    """One emulator per game and build (stock or patched): the code section mapped once, with a hook that stubs
    the C runtime's rand and records the tech-point adder's argument; `state` holds the run's rand result and
    what was added."""
    key = (game, patched)
    if key not in _EMULATORS:
        _, _, _, adder, crt_rand, _ = GAMES[game]
        data, pe = image(game, patched)
        base = pe.OPTIONAL_HEADER.ImageBase
        text = next(s for s in pe.sections if s.Name.startswith(b".text"))
        start = (base + text.VirtualAddress) & ~0xFFF
        end = (base + text.VirtualAddress + text.Misc_VirtualSize + 0xFFF) & ~0xFFF
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        uc.mem_map(start, end - start)
        uc.mem_write(base + text.VirtualAddress, data[text.PointerToRawData:text.PointerToRawData + text.SizeOfRawData]
                     [:text.Misc_VirtualSize])
        uc.mem_map(STACK, 0x10000)
        state = {"crt": 0, "added": []}

        def hook(uc, address, size, _):
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret = struct.unpack("<I", uc.mem_read(esp, 4))[0]
            if address == crt_rand:                     # cdecl, no arguments
                uc.reg_write(UC_X86_REG_EAX, state["crt"])
                uc.reg_write(UC_X86_REG_ESP, esp + 4)
                uc.reg_write(UC_X86_REG_EIP, ret)
            elif address == adder:                      # thiscall, one argument
                state["added"].append(struct.unpack("<i", uc.mem_read(esp + 4, 4))[0])
                uc.reg_write(UC_X86_REG_ESP, esp + 8)
                uc.reg_write(UC_X86_REG_EIP, ret)

        uc.hook_add(UC_HOOK_CODE, hook)
        _EMULATORS[key] = (uc, state)
    return _EMULATORS[key]


def bonus(game: str, patched: bool, pieces: int, crt: int) -> list[int]:
    """The tech points the bonus adds (each call of the adder) with `pieces` of the set found."""
    _, start, end, _, _, _ = GAMES[game]
    uc, state = emulator(game, patched)
    state["crt"], state["added"] = crt, []
    uc.reg_write(UC_X86_REG_ESP, STACK + 0x8000)
    uc.reg_write(UC_X86_REG_EAX, pieces)
    uc.emu_start(start, end, count=10_000)
    return list(state["added"])


@unittest.skipUnless(HAVE_EMULATOR, "unicorn / pefile not installed")
class ResearchBonus(unittest.TestCase):
    def setUp(self) -> None:
        if not all((STOCK_DIR / g[0]).is_file() for g in GAMES.values()):
            self.skipTest("stock executables not present")

    def test_stock_counts_every_piece(self) -> None:
        for pieces in range(1, 13):
            self.assertEqual(bonus("vv4", False, pieces, CRT_HIGH), [CRT_HIGH % pieces])
        self.assertEqual(bonus("vv4", False, 0, CRT_HIGH), [])
        for pieces in range(25):
            self.assertEqual(sum(bonus("vv5", False, pieces, CRT_HIGH)),
                             CRT_HIGH % (pieces // 2) if pieces >= 2 else 0, pieces)

    def test_patched_counts_only_the_complete_set(self) -> None:
        for game in GAMES:
            full = GAMES[game][5]
            for pieces in range(full):
                for crt in (CRT_LOW, CRT_HIGH):
                    self.assertEqual(sum(bonus(game, True, pieces, crt)), 0, (game, pieces, crt))
            for crt in (CRT_LOW, CRT_HIGH):
                self.assertEqual(bonus(game, True, full, crt), bonus(game, False, full, crt), (game, crt))
            self.assertEqual(sum(bonus(game, True, full, CRT_HIGH)), CRT_HIGH % 12)

    def test_the_bonus_never_goes_below_zero_or_above_eleven(self) -> None:
        for game in GAMES:
            for pieces in range(GAMES[game][5] + 1):
                for crt in range(0, 0x8000, 0x7FF):
                    for amount in bonus(game, True, pieces, crt):
                        self.assertTrue(0 <= amount <= 11, (game, pieces, crt, amount))


class Catalog(unittest.TestCase):
    def test_both_games_list_it_off_by_default(self) -> None:
        for game in GAMES:
            patch_id = f"{game}_science_collectibles_complete"
            self.assertIn(patch_id, {p.id for p in patcher.load_public_fun_patches()})
            self.assertFalse(default_fun_patch_selection(patch_id))
            self.assertTrue(owners_default_fun_patch_selection(patch_id))
            self.assertTrue(select_all_fun_patch_selection(patch_id))

    def test_one_guarded_edit_each(self) -> None:
        for game in GAMES:
            patches = feature(game)["patches"]
            self.assertEqual(len(patches), 1)
            self.assertEqual(len(patches[0]["before"]), len(patches[0]["after"]))


if __name__ == "__main__":
    unittest.main()
