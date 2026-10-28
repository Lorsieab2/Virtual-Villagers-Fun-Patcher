"""The VV5 God powers group (src/vv_game_mechanics_powers_vv5.py): its table matches the stock exe, and it shows."""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_powers_vv5 as powers  # noqa: E402

STOCK = ROOT / "inputs" / "vv5-stock-copy" / "Virtual Villagers - New Believers.exe"
BASE = 0x400000


def _image():
    try:
        import pefile
    except ImportError:
        return None
    if not STOCK.exists():
        return None
    return pefile.PE(str(STOCK)).get_memory_mapped_image()


class GodPowers(unittest.TestCase):
    def test_group_is_shown_in_order(self) -> None:
        facts = gm.general(5)
        mine = [f for f in facts if f.group == powers.POWERS]
        self.assertTrue(mine)
        self.assertIn(powers.POWERS, gm.GROUPS)
        text = " ".join(f.text for f in mine)
        for name, cost, _ in powers.TABLE:
            self.assertIn(f"{name} ({cost}):", text)
        self.assertIn("Spirituality", text)
        self.assertNotIn("belief", text.lower())
        # Stock vs patched, its own line (the owner, 2026-10-27): CODE, from the patcher's catalog; Revive names 256.
        patched = [f for f in mine if f.text == powers.PATCHED]
        self.assertEqual(len(patched), 1)
        self.assertEqual(patched[0].verified, gm.CODE)
        self.assertIn("256 Villagers (Experimental)", gm.feature_name("vv5_population_256"))

    def test_only_revive_is_touched_by_a_patch(self) -> None:
        """No row of the patcher's catalog names a God Power, its handler, table or costs, or Divine Energy, except
        Revive's (the game's Reanimate) record rows -- what the "Stock or patched" line says."""
        import json

        def strings(node):
            if isinstance(node, dict):
                for value in node.values():
                    yield from strings(value)
            elif isinstance(node, list):
                for value in node:
                    yield from strings(value)
            elif isinstance(node, str):
                yield node
        # Sunshine, Tempest, Time Warp and Grant Youth are also the names of Origins upgrades and island events.
        words = [name for name, _, _ in powers.TABLE
                 if name not in ("Revive", "Sunshine", "Tempest", "Time Warp", "Grant Youth")]
        words += ["0x422EB0", "0x4234A0", "0x498840", "0x4CA000", "Divine Energy", "Spell"]
        data = ROOT / "data"
        for path in [data / "builds.json"] + sorted(data.glob("vv5_*_feature.json")):
            for row in strings(json.loads(path.read_text(encoding="utf-8"))):
                for word in words:
                    if word.lower() not in row.lower():
                        continue
                    self.assertIn("Reanimate", row, f"{path.name}: {word}: {row[:160]}")

    def test_table_matches_the_stock_exe(self) -> None:
        img = _image()
        if img is None:
            self.skipTest("the stock VV5 exe (inputs/vv5-stock-copy) or pefile is missing")
        costs = struct.unpack_from("<11i", img, 0x498840 - BASE)
        self.assertEqual(costs, tuple(cost for _, cost, _ in powers.TABLE))
        for name, _, hint in powers.TABLE:
            self.assertIn(hint.encode("latin1"), img)
        # the ranges in pixels the lines quote: Bees 150, Lightning 300, Hand of Bloom 104 (table +0x08)
        ranges = [struct.unpack_from("<i", img, 0x4CA008 - BASE + 24 * k)[0] for k in range(11)]
        self.assertEqual((ranges[1], ranges[3], ranges[4]), (150, 300, 104))
        # the spells' own timers: Butterflies 126 s, Fog 120,000 ms, Time Warp 300,000 ms, Revive 4,000 ms,
        # Earthquake 10,000 ms, the fire 72,000 game-clock seconds, the Pain Totem window 75 s
        for at, value in ((0x422A4F, b"\x83\xc0\x7e"), (0x41FBAB + 2, struct.pack("<I", 120_000)),
                          (0x41FC9B + 2, struct.pack("<I", 300_000)), (0x42009F + 2, struct.pack("<I", 4_000)),
                          (0x41F832 + 2, struct.pack("<I", 10_000)), (0x439097 + 1, struct.pack("<I", 72_000)),
                          (0x43A0CF + 2, b"\x4b")):
            self.assertEqual(bytes(img[at - BASE:at - BASE + len(value)]), value, hex(at))


if __name__ == "__main__":
    unittest.main()
