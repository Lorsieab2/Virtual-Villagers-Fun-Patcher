"""A slot guard's population source must be something that really exists.

VV4's five 150-slot saturation guards all decided using a static address:

    00489080  cmp dword ptr [0x4D6DE8], 0x96

**Nothing ever wrote `0x4D6DE8`.** Its only appearance in the stock image is a
coincidental byte match inside the immediate operand of `or eax, 0x4d6de8`, and
its `.data` initial value is 0.  Whatever that address happened to hold at
runtime decided whether children were allowed to spawn, which is why the
Barrel of Babies presented its event and then delivered nobody.

VV3 looked fine at first because its address IS written -- `add dword ptr
[0x5824A8], ecx` at `0x455BF3`.  But nothing in stock ever READS it, and it only
ever accumulates: each birth adds 2 or 3.  Once that running tally passes the
threshold, VV3's guards fire forever and quietly suppress twins, triplets and
event children for the rest of the save.  So "written somewhere" was too weak a
rule -- it passed VV3.

Only VV5 was right: it CALLS a helper that sweeps the villager records.

The rule these tests now pin is the strong one: a slot guard must count live
records.  No guard may decide capacity from an absolute data address at all,
whether or not something writes it.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

try:
    import pefile
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    from capstone.x86 import X86_OP_MEM
    HAVE_TOOLS = True
except ImportError:  # pragma: no cover - dev dependencies
    HAVE_TOOLS = False

ROOT = Path(__file__).resolve().parents[1]
BUILDS = ROOT / "data" / "builds.json"
STOCK = ROOT / "research" / "stock-executables"
IMAGE_BASE = 0x400000

EXES = {
    "vv3": "Virtual Villagers - The Secret City.exe",
    "vv4": "Virtual Villagers - The Tree of Life.exe",
    "vv5": "Virtual Villagers - New Believers.exe",
}

# Instructions that store to their first (memory) operand.
WRITERS = {"mov", "add", "sub", "inc", "dec", "and", "or", "xor", "adc", "sbb"}


def _safety_patches(game: str) -> list[dict]:
    data = json.loads(BUILDS.read_text(encoding="utf-8"))
    entry = next((g for g in data["games"] if g["id"] == game), None)
    return (entry or {}).get("safety_patches", []) or []


def _guard_data_reads(blob: bytes, va: int) -> set[int]:
    """Absolute data addresses the guard READS to make its decision."""
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    found = set()
    for insn in md.disasm(blob, va):
        if insn.mnemonic not in ("cmp", "mov", "sub", "add"):
            continue
        for operand in insn.operands:
            if operand.type != X86_OP_MEM:
                continue
            # An absolute [disp] with no base or index register.
            if operand.mem.base == 0 and operand.mem.index == 0:
                target = operand.mem.disp & 0xFFFFFFFF
                if target > IMAGE_BASE:
                    found.add(target)
    return found


class SlotGuardPopulationSourceTests(unittest.TestCase):
    @unittest.skipUnless(HAVE_TOOLS, "requires Capstone and pefile")
    def test_no_guard_decides_capacity_from_an_absolute_address(self) -> None:
        """The strong rule: guards count, they never read a static.

        This cannot pass vacuously -- the companion test below proves each
        game still has guards and a counter, so an empty result here means
        "they all count", not "there is nothing to check".
        """
        for game in EXES:
            for row in _safety_patches(game):
                offset = int(row["offset"], 16)
                reads = _guard_data_reads(
                    bytes.fromhex(row["after"]), IMAGE_BASE + offset
                )
                with self.subTest(game=game, guard=hex(IMAGE_BASE + offset)):
                    self.assertEqual(
                        sorted(hex(r) for r in reads), [],
                        f"{game} guard at {IMAGE_BASE + offset:#x} decides "
                        f"capacity from an absolute address. VV4's was never "
                        f"written; VV3's was a running tally nothing reads. "
                        f"Count live records instead.",
                    )

    # Both VV3 and VV4 turned out to decide capacity from a static address that
    # is not a live population count.  VV4's 0x4D6DE8 is never written at all.
    # VV3's 0x5824A8 IS written -- `add [0x5824A8], ecx` at 0x455BF3 -- but
    # nothing in stock ever READS it, and it only accumulates: each birth adds
    # 2 or 3, so once the tally passes the threshold the guards fire forever.
    # "Written somewhere" is therefore too weak a rule.  A guard must COUNT.
    COUNTING_GAMES = {
        "vv3": {"counter": 0x7B318,
                "guards": (0x7B260, 0x7B280, 0x7B2E0, 0x7B300),
                "stale": "A824580 0".replace(" ", "")},
        "vv4": {"counter": 0x890F0,
                "guards": (0x89020, 0x89040, 0x89060, 0x89080, 0x890C0),
                "stale": "E86D4D00"},
    }

    def test_guards_count_records_rather_than_reading_a_static(self) -> None:
        """Every guard must begin by CALLING a record counter."""
        for game, spec in self.COUNTING_GAMES.items():
            rows = {int(r["offset"], 16): r["after"].upper()
                    for r in _safety_patches(game)}
            self.assertTrue(rows, f"{game} has no safety patches")
            self.assertIn(
                spec["counter"], rows,
                f"{game}'s record counter is not written",
            )
            for offset in spec["guards"]:
                with self.subTest(game=game, guard=hex(IMAGE_BASE + offset)):
                    self.assertIn(offset, rows)
                    self.assertNotIn(
                        spec["stale"], rows[offset],
                        f"{game} guard still reads its stale static address",
                    )
                    self.assertTrue(
                        rows[offset].startswith("E8"),
                        "guard must begin by calling the record counter",
                    )

    def test_each_counter_sweeps_that_game_s_record_array(self) -> None:
        """The counter must walk records, not read a variable."""
        geometry = {
            "vv3": (0x7B318, "24E15900", "8C1F0000", "100F0000"),
            "vv4": (0x890F0, "ACE55000", "3C2E0000", "C41C0000"),
        }
        for game, (offset, base, stride, active) in geometry.items():
            with self.subTest(game=game):
                blob = {int(r["offset"], 16): r["after"].upper()
                        for r in _safety_patches(game)}[offset]
                for label, needle in (("record base", base),
                                      ("record stride", stride),
                                      ("active offset", active)):
                    self.assertIn(needle, blob, f"{game} counter lacks its {label}")
                self.assertTrue(blob.endswith("C3"), "counter must return")


if __name__ == "__main__":
    unittest.main()
