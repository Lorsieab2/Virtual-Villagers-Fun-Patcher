"""One-Time Collectibles Appear Again (The Secret City, The Tree of Life; the owner, 2026-11-17: on in Owner's
Defaults, off everywhere else).  The traces are in scripts/build_one_time_collectibles_features.py.

EMULATED on the executable the patcher renders (stock, and with the row in every public mode): the game's
owned-piece test, for every collectible id with its count 0 and 1.  Stock, it refuses exactly the found Tablet pieces
(The Secret City) or the found Mausoleum Mural pieces (The Tree of Life); patched, it refuses nothing, and returns as
the stock routine does (ret 4).  Its two callers test al and skip the piece when it is not 0."""
from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    from unicorn import UC_ARCH_X86, UC_MODE_32, Uc
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_ESP

    from test_companion_installs_all_or_none import render, stock_path
    HAVE = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE = False

SITES = {3: 0x42D830, 4: 0x413C90}
CALLERS = {3: (0x42DAF7, 0x42DC57), 4: (0x4140B4, 0x4141DF)}
ONCE = {3: range(0x4C, 0x58), 4: range(0x5E, 0x6A)}
# Where each test reads a piece's count: The Secret City [ecx + id x 4 + 0x10], The Tree of Life [ecx + id x 4 - 0x38].
COUNT_AT = {3: 0x10, 4: -0x38}
MODES = ("stock", "collection_progression", "immediate_fixed")


def row_id(game: int) -> str:
    return f"vv{game}_one_time_collectibles_again"


@unittest.skipUnless(HAVE, "unicorn not installed")
class Emulated(unittest.TestCase):
    def setUp(self) -> None:
        if not all(stock_path(g).is_file() for g in SITES):
            self.skipTest("stock executables not present")

    def refused(self, data: bytes, game: int, piece: int, count: int) -> bool:
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        page = SITES[game] & ~0xFFF
        mu.mem_map(page, 0x2000)
        mu.mem_write(page, data[page - 0x400000:page - 0x400000 + 0x2000])
        mu.mem_map(0x100000, 0x10000)        # the stack
        mu.mem_map(0x200000, 0x1000)         # the item manager's counts
        table = 0x200100
        mu.mem_write(table + piece * 4 + COUNT_AT[game], struct.pack("<I", count))
        esp = 0x108000
        mu.mem_write(esp, struct.pack("<II", 0xDEAD0000, piece))
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_ECX, table)
        mu.reg_write(UC_X86_REG_EAX, 0xFFFFFFFF)
        mu.mem_map(0xDEAD0000, 0x1000)
        mu.emu_start(SITES[game], 0xDEAD0000, count=100)
        self.assertEqual(mu.reg_read(UC_X86_REG_ESP), esp + 8, "ret 4")
        return mu.reg_read(UC_X86_REG_EAX) & 0xFF != 0

    def test_stock_refuses_only_the_found_once_only_pieces(self) -> None:
        for game in SITES:
            data = stock_path(game).read_bytes()
            for piece in range(0x40, 0x80):
                for count in (0, 1, 3):
                    with self.subTest(game=game, piece=hex(piece), count=count):
                        self.assertEqual(self.refused(data, game, piece, count),
                                         count > 0 and piece in ONCE[game] or (game == 4 and count > 0 and not (
                                             0x46 <= piece <= 0x5D or 0x6A <= piece <= 0x75)))

    def test_patched_refuses_nothing(self) -> None:
        for game in SITES:
            for mode in MODES:
                data = render(game, (row_id(game),), mode)
                for piece in range(0x40, 0x80):
                    with self.subTest(game=game, mode=mode, piece=hex(piece)):
                        self.assertFalse(self.refused(data, game, piece, 1))

    def test_the_callers_skip_a_refused_piece(self) -> None:
        for game in SITES:
            data = stock_path(game).read_bytes()
            for va in CALLERS[game]:
                o = va - 0x400000
                with self.subTest(game=game, caller=hex(va)):
                    self.assertEqual(data[o], 0xE8)
                    self.assertEqual(va + 5 + struct.unpack_from("<i", data, o + 1)[0], SITES[game])
                    self.assertEqual(data[o + 5:o + 8], b"\x84\xC0\x75")    # test al, al; jne skip


class Rows(unittest.TestCase):
    def test_two_rows_off_by_default_on_in_owners_defaults(self) -> None:
        from vv_fun_patcher_gui import (default_fun_patch_selection, owners_default_fun_patch_selection,
                                        select_all_fun_patch_selection)
        public = {p.id: p for p in patcher.load_public_fun_patches()}
        for game in SITES:
            row = public[row_id(game)]
            with self.subTest(game=game):
                self.assertEqual(row.name, "One-Time Collectibles Appear Again")
                self.assertEqual(row.raw["patches"][0]["after"], "32C0C20400")
                self.assertEqual(int(row.raw["patches"][0]["offset"], 16) + 0x400000, SITES[game])
                self.assertIn("**Needs no other patch.**", row.raw["description"])
                self.assertFalse(default_fun_patch_selection(row.id))
                self.assertTrue(owners_default_fun_patch_selection(row.id))
                self.assertFalse(select_all_fun_patch_selection(row.id))
        self.assertFalse([p for p in public if p.endswith("_one_time_collectibles_again")
                          and p not in (row_id(3), row_id(4))])

    def test_each_row_is_what_the_generator_writes(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        if not (ROOT / "research" / "stock-executables").is_dir():
            self.skipTest("stock executables not present")
        import build_one_time_collectibles_features as gen
        for game, g in gen.GAMES.items():
            record = json.loads((ROOT / "data" / f"{game}_one_time_collectibles_again_feature.json").read_text("utf-8"))
            self.assertEqual(record, gen.feature(game, g))

    def test_no_other_row_writes_the_test(self) -> None:
        for feature in patcher.load_fun_patches():
            if feature.id.endswith("_one_time_collectibles_again"):
                continue
            for game, va in SITES.items():
                if not feature.id.startswith(f"vv{game}_"):
                    continue
                for p in feature.raw.get("patches", []):
                    start = int(p["offset"], 16) + 0x400000
                    with self.subTest(row=feature.id):
                        self.assertTrue(start + len(p["after"]) // 2 <= va or va + 5 <= start)


if __name__ == "__main__":
    unittest.main()
