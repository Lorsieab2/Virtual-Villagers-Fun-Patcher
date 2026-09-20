"""Move the "Playing in the dirt" Spot (New Believers).

The stock routine at 0x45ED40 registers say-event 504 ("Playing in the dirt",
the say table row at 0x4D64D0) and then, six times, queues a go-to (command
type 4 through the wrapper at 0x4745A0) to a random point:

    6A 22              push 0x22          edi spread (imm8)
    E8 rel32           call rand
    8B F8              mov edi, eax
    68 DA 00 00 00     push 0xDA          eax spread (imm32)
    81 C7 BA 01 00 00  add edi, 0x1BA     edi = 442 + rand(34)
    E8 rel32           call rand
    83 C4 08           add esp, 8
    6A 00 6A 64        push 0 ; push 0x64
    05 EC 00 00 00     add eax, 0xEC      eax = 236 + rand(218)
    57 50 8B CE E8 ..  push edi ; push eax ; mov ecx, esi ; call 0x4745A0

The game's rand(n) returns 0..n-1.  WHICH VALUE IS WHICH AXIS was measured on
the owner's running village, not inferred: children queued by a patched
routine carried commands (eax a, edi b) and came to rest at position pairs
(+0x1C98 ~a, +0x1C9C ~b); eax is the first position field, edi the second.
Three placements were confirmed live (the children arrived each time) before
the owner outlined the flower patch east of the dirt path (the worn ground
with the flowers, west of the flower rock) and asked for the children to stay
strictly inside it.  The record-to-screen mapping was calibrated from a crowd
of 22 villagers captured together with their record positions (an earlier
two-villager estimate was ~110 units off in y): the outline is about 285 wide
and 253 tall in record units.

A one-byte push cannot hold a spread over 127, so the block is recoded in
place, same 46 bytes: rand(127) doubled by `lea edi, [eax+eax]` (one byte
longer than `mov edi, eax`), paid for by `pop ecx ; pop ecx` in place of
`add esp, 8` (ecx is dead there: `mov ecx, esi` follows before the call).  The
second rand call moves one byte, so its rel32 is recomputed.  Result:
x = 1843 + rand(285) -> 1843..2127, y = 1431 + 2*rand(127) -> 1431..1683.
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

RAND = 0x403660
X_BASE, X_SPREAD = 1843, 285
Y_BASE, Y_HALF = 1431, 127
OUTLINE = (1843, 2127, 1431, 1687)   # the owner stood a villager on each corner: Tiki (1843,1431), Bua (2127,1687)


def expected_block() -> bytes:
    return (
        bytes([0x6A, Y_HALF])
        + b"\xE8" + struct.pack("<i", RAND - (0x45ED72 + 5))
        + bytes.fromhex("8D3C00")
        + b"\x68" + struct.pack("<I", X_SPREAD)
        + bytes.fromhex("81C7") + struct.pack("<I", Y_BASE)
        + b"\xE8" + struct.pack("<i", RAND - (0x45ED85 + 5))
        + bytes.fromhex("5959")
        + bytes.fromhex("6A006A64")
    )


def stock_block() -> bytes:
    return (
        bytes.fromhex("6A22")
        + b"\xE8" + struct.pack("<i", RAND - (0x45ED72 + 5))
        + bytes.fromhex("8BF8")
        + bytes.fromhex("68DA000000")
        + bytes.fromhex("81C7BA010000")
        + b"\xE8" + struct.pack("<i", RAND - (0x45ED84 + 5))
        + bytes.fromhex("83C408")
        + bytes.fromhex("6A006A64")
    )


class PlayingInTheDirtTests(unittest.TestCase):
    def manifest(self) -> dict:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_the_block_is_recoded_in_place_and_the_base_moved(self):
        m = self.manifest()
        self.assertEqual(m["game_id"], "vv5")
        self.assertEqual(m["companion_files"], [])
        by_offset = {int(p["offset"], 16): p for p in m["patches"]}
        self.assertEqual(sorted(by_offset), [0x5ED70, 0x5ED91])
        blk = by_offset[0x5ED70]
        self.assertEqual(bytes.fromhex(blk["before"]), stock_block())
        self.assertEqual(bytes.fromhex(blk["after"]), expected_block())
        self.assertEqual(len(blk["before"]), len(blk["after"]), "in place: same length")
        base = by_offset[0x5ED91]
        self.assertEqual(base["before"], "EC000000")
        self.assertEqual(struct.unpack("<I", bytes.fromhex(base["after"]))[0], X_BASE)
        for p in m["patches"]:
            self.assertEqual(len(p["before"]), len(p["after"]))

    def test_the_recoded_block_decodes_to_the_intended_instructions(self):
        try:
            import capstone  # noqa: PLC0415
        except ImportError:
            self.skipTest("capstone not installed")
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        tail = bytes.fromhex("05") + struct.pack("<I", X_BASE) + bytes.fromhex("57508BCE")
        got = [f"{i.mnemonic} {i.op_str}".strip() for i in md.disasm(expected_block() + tail, 0x45ED70)]
        self.assertEqual(got, [
            "push 0x7f", "call 0x403660", "lea edi, [eax + eax]", "push 0x11d",
            "add edi, 0x597", "call 0x403660", "pop ecx", "pop ecx", "push 0",
            "push 0x64", "add eax, 0x733", "push edi", "push eax", "mov ecx, esi",
        ])

    def test_the_ranges_fill_the_owners_outline_and_are_what_rand_can_produce(self):
        x_lo, x_hi = X_BASE, X_BASE + X_SPREAD - 1                 # rand(503): 0..502
        y_lo, y_hi = Y_BASE, Y_BASE + 2 * (Y_HALF - 1)            # 2*rand(127): 0..252
        self.assertEqual((x_lo, x_hi, y_lo, y_hi), (1843, 2127, 1431, 1683))
        # The owner marked the box by standing a villager on each corner, so the
        # patch must match it: inside it, and within a step of filling it (the
        # second coordinate moves in twos, so its top may fall one short).
        ox0, ox1, oy0, oy1 = OUTLINE
        self.assertTrue(ox0 <= x_lo and x_hi <= ox1, (x_lo, x_hi, OUTLINE))
        self.assertTrue(oy0 <= y_lo and y_hi <= oy1, (y_lo, y_hi, OUTLINE))
        self.assertEqual((x_lo, y_lo), (ox0, oy0))
        self.assertLessEqual(ox1 - x_hi, 1)
        # The second coordinate's spread is a one-byte push, so it cannot
        # exceed 127 and, doubled, cannot reach more than 254 above its base;
        # the top may therefore fall short of the owner's corner.  Staying
        # inside the box is the requirement ("make sure it's strict"), so the
        # shortfall is bounded by that hardware limit, never by a guess.
        self.assertLessEqual(oy1 - y_hi, max(2, (oy1 - oy0) - 2 * (0x7F - 1)))
        self.assertLessEqual(Y_HALF, 0x7F)
        text = " ".join(self.manifest()["behavior_changes"])
        self.assertIn("%d..%d by %d..%d" % (x_lo, x_hi, y_lo, y_hi), text)
        self.assertIn("236..453 by 442..475", text)
        self.assertNotIn("442..476", text)

    def test_before_bytes_are_the_stock_routine(self):
        if not STOCK.is_file():
            self.skipTest("stock New Believers exe not present in this checkout")
        exe = STOCK.read_bytes()
        self.assertEqual(exe[0x5ED70:0x5ED90], stock_block())
        self.assertEqual(exe[0x5ED90:0x5ED95], bytes.fromhex("05EC000000"))
        self.assertEqual(exe[0x5ED45:0x5ED4A], bytes.fromhex("68F8010000"))     # push 0x1F8 (say-event 504)
        for p in self.manifest()["patches"]:
            off = int(p["offset"], 16)
            self.assertEqual(exe[off: off + len(p["before"]) // 2].hex().upper(), p["before"].upper())
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
        stock = STOCK.read_bytes()
        self.assertEqual(rendered[0x5ED70:0x5ED90], expected_block())
        self.assertEqual(rendered[0x5ED90:0x5ED95], bytes.fromhex("05") + struct.pack("<I", X_BASE))
        self.assertEqual(rendered[0x5ED40:0x5ED70], stock[0x5ED40:0x5ED70])
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
        mine = set(range(0x5ED70, 0x5ED90)) | set(range(0x5ED91, 0x5ED95))
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
