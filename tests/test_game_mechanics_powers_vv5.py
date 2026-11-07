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

    def _effect(self, name: str) -> str:
        index = [n for n, _, _ in powers.TABLE].index(name)
        _, text, subs = next(e for e in powers.EFFECTS if e[0] == index)
        return " ".join([text] + [s[0] if isinstance(s, tuple) else s for s in subs])

    def test_time_warp_factor(self) -> None:
        """The owner (2026-11-06): by what units and how much Time Warp speeds a villager up.  The factor +0x1CC8 is
        10 (0x41FC4E), the age credit doubles it (0x470051: add edi, edi) and pays floor(whole minutes x 20 / speed)
        age units, emptying the count; the step loop (0x471EF9) and the action length divisor (0x4735AB) read it."""
        text = self._effect("Time Warp")
        per_minute = [20 // speed for speed in (3, 6, 10)]                 # Fast, Normal, Slow
        self.assertEqual(per_minute, [6, 3, 2])
        self.assertIn("6, 3 or 2 age units each real-life minute", text)
        self.assertIn("18, 18 or 20 times as fast", text)                   # vs 1 unit per 3, 6 or 10 minutes
        upfront = [20 * ((60 * speed - 1) // 60) // speed for speed in (3, 6, 10)]
        self.assertEqual(upfront, [13, 16, 18])
        low = [4 * m for m in per_minute]
        high = [u + 5 * m for u, m in zip(upfront, per_minute)]
        self.assertIn(f"{low[0]} to {high[0]}, {low[1]} to {high[1]} or {low[2]} to {high[2]} age units", text)
        self.assertIn("Waaay Too Much Sugar", text)
        img = _image()
        if img is None:
            self.skipTest("the stock VV5 exe (inputs/vv5-stock-copy) or pefile is missing")
        for at, value in ((0x41FC4E, bytes.fromhex("c780c81c00000a000000")), (0x470051, b"\x03\xff"),
                          (0x471EF9, bytes.fromhex("39b7c81c0000")), (0x4735AB, bytes.fromhex("f7b1c81c0000")),
                          (0x41FCB3 + 6, b"\x01")):
            self.assertEqual(bytes(img[at - BASE:at - BASE + len(value)]), value, hex(at))
        self.assertIn(b"You used time warp on a child\0", img)

    def test_fog_of_doom_blinds_heathens(self) -> None:
        """The owner (2026-11-06): Heathens cannot see, chase or scare believers in the Fog of Doom.  The spell sets
        the fog's thickness to 4.0 (0x41FB51 -> 0x476250) and the believers' drawing value to 0.6 (0x41FB65); the
        Heathen's check (0x46E2E0) returns at once when 0x476260 finds the thickness at 2.0 or more."""
        text = self._effect("Fog of Doom")
        for words in ("do not see believers", "Chasing the intruder", "Running to safety",
                      "Running from the scary heathen", "0.6", "4 times as thick", "1 cast in 3 on Fast"):
            self.assertIn(words, text)
        img = _image()
        if img is None:
            self.skipTest("the stock VV5 exe (inputs/vv5-stock-copy) or pefile is missing")

        def f32(at):
            return struct.unpack_from("<f", img, at - BASE)[0]
        self.assertEqual((f32(0x49893C), round(f32(0x498938), 6), f32(0x4B8E90)), (4.0, 0.6, 2.0))
        self.assertEqual(struct.unpack_from("<I", img, 0x41FB51 + 2 - BASE)[0], 0x49893C)
        self.assertEqual(struct.unpack_from("<I", img, 0x476269 + 2 - BASE)[0], 0x4B8E90)
        call = struct.unpack_from("<i", img, 0x46E2E8 + 1 - BASE)[0] + 0x46E2E8 + 5
        self.assertEqual(call, 0x476260)
        # the fog's own weather change: 180 + rand(180) game-clock seconds; below 240 (2 minutes on Fast) 1 in 3
        self.assertEqual(bytes(img[0x4771B7 - BASE:0x4771B7 - BASE + 10]), bytes.fromhex("bfb4000000b868010000"))

    def test_earthquake_special_roles(self) -> None:
        """The owner (2026-11-06): name the six special roles the Earthquake skips (0x41F76B: role 12 to 17), as
        the game names them on a Heathen (0x443102: the jump table 0x443270 pushes say strings 0xD4-0xD9)."""
        text = self._effect("Earthquake")
        names = {12: "Heathen Doctor", 13: "Heathen Chief", 14: "Heathen Master Scientist",
                 15: "Heathen Master Builder", 16: "Heathen Master Farmer", 17: "Heathen Mommy"}
        for role, name in names.items():
            self.assertIn(f'{role} "{name}"', text)
        self.assertIn("Retired Chief", text)
        self.assertNotIn("loses some", text)
        img = _image()
        if img is None:
            self.skipTest("the stock VV5 exe (inputs/vv5-stock-copy) or pefile is missing")
        roles = [img[at - BASE] for at in range(0x41F773, 0x41F773 + 30, 5)]
        self.assertEqual(sorted(roles), list(names))
        targets = struct.unpack_from("<6I", img, 0x443270 - BASE)
        say = {0xD4: "Heathen Chief", 0xD5: "Heathen Master Builder", 0xD6: "Heathen Master Scientist",
               0xD7: "Heathen Master Farmer", 0xD8: "Heathen Doctor", 0xD9: "Heathen Mommy"}
        for role, target in zip(range(12, 18), targets):
            window = bytes(img[target - BASE:target - BASE + 8])
            at = window.index(b"\x68")                                    # push imm32
            self.assertEqual(say[struct.unpack_from("<I", window, at + 1)[0]], names[role], hex(target))
        for name in names.values():
            self.assertIn(name.encode() + b"\0", img)


if __name__ == "__main__":
    unittest.main()
