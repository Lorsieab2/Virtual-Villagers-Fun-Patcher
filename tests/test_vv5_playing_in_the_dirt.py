"""Move the "Playing in the dirt" Spot (New Believers).

The stock routine at 0x45ED40 registers say-event 504 ("Playing in the dirt",
the say table row at 0x4D64D0) and then, six times, sends the child to a
random point in a fixed strip through the go-to wrapper at 0x4745A0:

    push 0x22 ; call rand ; mov edi, eax ; add edi, 0x1BA     x = 442 + rand(34)
    push 0xDA ; call rand ;               add eax, 0xEC      y = 236 + rand(218)
    (the 0xDA range immediate is at 0x45ED7A, the two bases at 0x45ED80 / 0x45ED91)
    push 0 ; push 0x64 ; push edi ; push eax ; call 0x4745A0

The wrapper's first argument (eax, pushed last) is y and the second (edi) is
x: the same wrapper sends villagers to (edi 1131..1181, eax 932..996) where
ten of the owner's villagers stand at x 1140..1163, y 921..980, and to
(edi 507..543, eax 598..636) where the lab cluster stands at x 507..515,
y 594..608.  That strip runs from below the rainbow totem across the river
to the research shelves.  The owner dropped a villager where the spot should
be, and the record's position pair at +0x1C98/+0x1C9C read (349, 266); they
chose a compact patch there rather than the stock strip: the x range stays
34, the y range becomes 40, both centred on the drop: x 332..366, y 246..286.
"""
from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402

MANIFEST = ROOT / "data" / "vv5_playing_in_the_dirt_feature.json"
STOCK = ROOT / "research" / "stock-executables" / next(
    b for b in patcher.load_builds() if b.id == "vv5"
).input_name

STOCK_X, STOCK_Y = 442, 236      # 0x1BA, 0xEC
X_RANGE, STOCK_Y_RANGE = 34, 218 # rand(0x22) (kept), rand(0xDA) (the stock height)
NEW_Y_RANGE = 40                 # rand(0x28): the owner chose the compact patch
OWNER_SPOT = (349, 266)          # the dropped villager's +0x1C98/+0x1C9C


class PlayingInTheDirtTests(unittest.TestCase):
    def manifest(self) -> dict:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_two_immediates_move_the_strip_and_nothing_else(self):
        m = self.manifest()
        self.assertEqual(m["game_id"], "vv5")
        self.assertEqual(m["companion_files"], [])
        self.assertEqual(len(m["patches"]), 3)
        by_offset = {int(p["offset"], 16): p for p in m["patches"]}
        # `add edi, 0x1BA` at 0x45ED7E: opcode 81 C7 then the imm32 at +2.
        self.assertIn(0x5ED80, by_offset)
        # `add eax, 0xEC` at 0x45ED90: opcode 05 then the imm32 at +1.
        self.assertIn(0x5ED91, by_offset)
        # `push 0xDA` at 0x45ED79: opcode 68 then the imm32 at +1.
        self.assertIn(0x5ED7A, by_offset)
        r_before = struct.unpack("<I", bytes.fromhex(by_offset[0x5ED7A]["before"]))[0]
        r_after = struct.unpack("<I", bytes.fromhex(by_offset[0x5ED7A]["after"]))[0]
        self.assertEqual((r_before, r_after), (STOCK_Y_RANGE, NEW_Y_RANGE))
        x_before = struct.unpack("<I", bytes.fromhex(by_offset[0x5ED80]["before"]))[0]
        x_after = struct.unpack("<I", bytes.fromhex(by_offset[0x5ED80]["after"]))[0]
        y_before = struct.unpack("<I", bytes.fromhex(by_offset[0x5ED91]["before"]))[0]
        y_after = struct.unpack("<I", bytes.fromhex(by_offset[0x5ED91]["after"]))[0]
        self.assertEqual((x_before, y_before), (STOCK_X, STOCK_Y))
        # The patch is centred on the owner's spot: x keeps the stock width.
        self.assertEqual(x_after + X_RANGE // 2, OWNER_SPOT[0])
        self.assertEqual(y_after + NEW_Y_RANGE // 2, OWNER_SPOT[1])
        self.assertEqual((x_after, y_after), (332, 246))
        for p in m["patches"]:
            self.assertEqual(len(p["before"]), len(p["after"]), "in place: same length")

    def test_before_bytes_are_the_stock_routine(self):
        if not STOCK.is_file():
            self.skipTest("stock New Believers exe not present in this checkout")
        exe = STOCK.read_bytes()
        # The instructions around the two immediates, so a shifted build cannot
        # be patched at the wrong place.
        self.assertEqual(exe[0x5ED7E:0x5ED84], bytes.fromhex("81C7BA010000"))   # add edi, 0x1BA
        self.assertEqual(exe[0x5ED90:0x5ED95], bytes.fromhex("05EC000000"))     # add eax, 0xEC
        self.assertEqual(exe[0x5ED70:0x5ED72], bytes.fromhex("6A22"))           # push 0x22
        self.assertEqual(exe[0x5ED79:0x5ED7E], bytes.fromhex("68DA000000"))     # push 0xDA
        self.assertEqual(exe[0x5ED45:0x5ED4A], bytes.fromhex("68F8010000"))     # push 0x1F8 (say-event 504)
        for p in self.manifest()["patches"]:
            off = int(p["offset"], 16)
            self.assertEqual(exe[off: off + len(p["before"]) // 2].hex().upper(), p["before"].upper())
        # The say-table row: id 504, its sound name, its text.
        row = 0x4D64D0 - 0x4C6000 + 811008
        ident, sound, text = struct.unpack_from("<III", exe, row)
        self.assertEqual(ident, 504)
        def cstr(va):
            off = va - 0x495000 + 610304
            return exe[off: exe.index(b"\0", off)]
        self.assertEqual(cstr(sound), b"eSayPlayInDirt")
        self.assertEqual(cstr(text), b"Playing in the dirt")

    def test_the_patcher_applies_it_and_only_it(self):
        if not STOCK.is_file():
            self.skipTest("stock New Believers exe not present in this checkout")
        build = next(b for b in patcher.load_builds() if b.id == "vv5")
        rendered, applied = patcher.render_patched_bytes(
            STOCK, build, patcher.DEFAULT_PATCH_MODE, ["vv5_playing_in_the_dirt_spot"]
        )
        rendered = bytes(rendered)
        self.assertEqual(rendered[0x5ED79:0x5ED84], bytes.fromhex("6828000000") + bytes.fromhex("81C74C010000"))
        self.assertEqual(rendered[0x5ED90:0x5ED95], bytes.fromhex("05F6000000"))
        stock = STOCK.read_bytes()
        # Outside the three immediates the routine is byte-identical.
        self.assertEqual(rendered[0x5ED40:0x5ED7A], stock[0x5ED40:0x5ED7A])
        self.assertEqual(rendered[0x5ED7E:0x5ED80], stock[0x5ED7E:0x5ED80])
        self.assertEqual(rendered[0x5ED84:0x5ED91], stock[0x5ED84:0x5ED91])
        self.assertEqual(rendered[0x5ED95:0x5EE60], stock[0x5ED95:0x5EE60])
        self.assertTrue(any("vv5_playing_in_the_dirt_spot" in str(item.get("owner", "")) for item in applied))

    def test_registered_bundled_documented_and_no_other_patch_claims_the_bytes(self):
        ids = {p.id for p in patcher.load_public_fun_patches()}
        self.assertIn("vv5_playing_in_the_dirt_spot", ids)
        source = (ROOT / "src" / "vv_fun_patcher.py").read_text(encoding="utf-8")
        self.assertIn('PLAYING_IN_THE_DIRT_FEATURE_PATHS = (ROOT / "data" / "vv5_playing_in_the_dirt_feature.json",)', source)
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('"data/vv5_playing_in_the_dirt_feature.json"', release)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("- Patch ID: `vv5_playing_in_the_dirt_spot`", readme)
        howto = (ROOT / "How to Use.txt").read_text(encoding="utf-8")
        self.assertIn('MOVE THE "PLAYING IN THE DIRT" SPOT (NEW BELIEVERS)', howto)
        doc = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        self.assertIn("`vv5_playing_in_the_dirt_spot`", doc)
        # No other manifest touches the three immediates.
        mine = {0x5ED7A, 0x5ED80, 0x5ED91}
        for path in sorted((ROOT / "data").glob("*.json")):
            if path.name == MANIFEST.name:
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            items = data if isinstance(data, list) else [data] + list(data.get("features", []) if isinstance(data, dict) else [])
            for item in items:
                if not isinstance(item, dict):
                    continue
                for p in item.get("patches", []) or []:
                    try:
                        off = int(str(p.get("offset")), 16); n = len(p.get("before", "")) // 2
                    except (TypeError, ValueError):
                        continue
                    self.assertFalse(mine & set(range(off, off + n)), (path.name, item.get("id"), p.get("offset")))

    def test_the_requirement_sentence_says_it_needs_nothing(self):
        public = patcher.load_public_fun_patches()
        row = next(p for p in public if p.id == "vv5_playing_in_the_dirt_spot")
        self.assertEqual(patcher.patch_requirement_text(row, public), "Requires no other patch to be ticked.")


if __name__ == "__main__":
    unittest.main()
