"""Misc Text Fixes (A New Home): the owner's corrections, read back through
the game's own string table from an executable the patcher actually renders.

Every edit is in place, so the table's pointers are unchanged; each text is
read from the rendered image at its table pointer and compared with the
owner's wording, and every other string in the table is byte-identical.
"""
from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402

STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
TABLE_VA = 0x487208
EXPECTED = {
    3: "This villager improved at farming.",
    15: "The villager has improved at parenting.",
    21: "Food available to villagers:",
    218: "Parenting",
    477: "parenting",
}


def _table(image: bytes, pe) -> dict[int, str]:
    base = pe.OPTIONAL_HEADER.ImageBase
    off = lambda va: pe.get_offset_from_rva(va - base)
    out = {}
    for i in range(0x275):
        sid, english = struct.unpack_from("<2I", image, off(TABLE_VA + i * 20))
        o = off(english)
        out[sid] = image[o:image.index(b"\0", o)].decode("latin-1")
    return out


class MiscTextFixesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build = next(b for b in patcher.load_builds() if b.id == "vv1")
        rendered, applied = patcher.render_patched_bytes(
            STOCK, build, "immediate_fixed", ["vv1_misc_text_fixes"])
        cls.rendered = bytes(rendered)
        cls.applied = applied
        pe = pefile.PE(str(STOCK), fast_load=True)
        cls.before = _table(STOCK.read_bytes(), pe)
        cls.after = _table(cls.rendered, pe)

    def test_the_owners_wording_is_what_the_game_reads(self):
        for sid, text in EXPECTED.items():
            self.assertEqual(self.after[sid], text, sid)
        self.assertIn("success at parenting!", self.after[319])
        self.assertNotIn("breeding", self.after[319])
        self.assertEqual(self.after[319].replace("parenting!", "breeding!"), self.before[319])

    def test_nothing_else_in_the_table_changes(self):
        changed = {sid for sid in self.before if self.before[sid] != self.after[sid]}
        self.assertEqual(changed, set(EXPECTED) | {319})

    def test_the_row_is_six_guarded_in_place_edits(self):
        manifest = json.loads((ROOT / "data" / "vv1_misc_text_fixes_feature.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["patches"]), 6)
        for p in manifest["patches"]:
            self.assertEqual(len(p["before"]), len(p["after"]), p["purpose"])
        owners = {edit["owner"] for edit in self.applied}
        self.assertIn("feature:vv1_misc_text_fixes", owners)


if __name__ == "__main__":
    unittest.main()
