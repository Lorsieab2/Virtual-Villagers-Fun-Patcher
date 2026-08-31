"""A slot guard's population source must be something that really exists.

VV4's five 150-slot saturation guards all decided using a static address:

    00489080  cmp dword ptr [0x4D6DE8], 0x96

**Nothing ever wrote `0x4D6DE8`.** Its only appearance in the stock image is a
coincidental byte match inside the immediate operand of `or eax, 0x4d6de8`, and
its `.data` initial value is 0.  Whatever that address happened to hold at
runtime decided whether children were allowed to spawn, which is why the
Barrel of Babies presented its event and then delivered nobody.

VV3's equivalent address is real -- `add dword ptr [0x5824A8], ecx` at
`0x455BF3` maintains it -- and VV5 calls a helper that sweeps the villager
records.  Both are fine.  VV4 was the odd one out.

This test pins the rule rather than the incident: every absolute address a
guard reads to decide capacity must be written somewhere in the stock
executable.  A guard that reads an address nothing maintains is comparing
against garbage.
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
    def test_every_guard_data_read_is_written_somewhere_in_the_stock_image(self) -> None:
        checked = 0
        for game, exe_name in EXES.items():
            exe = STOCK / exe_name
            if not exe.is_file():
                continue
            image = pefile.PE(str(exe)).get_memory_mapped_image(ImageBase=IMAGE_BASE)
            md = Cs(CS_ARCH_X86, CS_MODE_32)
            md.detail = True

            reads: set[int] = set()
            for row in _safety_patches(game):
                offset = int(row["offset"], 16)
                reads |= _guard_data_reads(
                    bytes.fromhex(row["after"]), IMAGE_BASE + offset
                )

            for address in sorted(reads):
                checked += 1
                needle = address.to_bytes(4, "little")
                written = False
                for position in range(0x1000, len(image) - 4):
                    if image[position:position + 4] != needle:
                        continue
                    # Decode a short window ending at this operand and check
                    # whether the instruction covering it stores to memory.
                    start = max(0x1000, position - 12)
                    for insn in md.disasm(image[start:position + 8],
                                          IMAGE_BASE + start):
                        if not (insn.address <= IMAGE_BASE + position
                                < insn.address + insn.size):
                            continue
                        if insn.mnemonic in WRITERS and insn.operands \
                                and insn.operands[0].type == X86_OP_MEM \
                                and insn.operands[0].mem.base == 0 \
                                and insn.operands[0].mem.index == 0 \
                                and (insn.operands[0].mem.disp & 0xFFFFFFFF) == address:
                            written = True
                        break
                    if written:
                        break

                with self.subTest(game=game, address=hex(address)):
                    self.assertTrue(
                        written,
                        f"{game}: a slot guard decides capacity from "
                        f"{address:#x}, but no instruction in the stock "
                        f"executable ever writes it. The guard is comparing "
                        f"against whatever happens to be there -- this is the "
                        f"VV4 Barrel of Babies bug, where the event presented "
                        f"and no children spawned.",
                    )

        self.assertTrue(
            checked or not any((STOCK / name).is_file() for name in EXES.values()),
            "no guard data reads were examined; this test would pass vacuously",
        )

    def test_vv4_counts_records_rather_than_reading_a_static(self) -> None:
        """VV4's guards must call the counter, like VV5's do."""
        rows = {int(r["offset"], 16): r["after"].upper()
                for r in _safety_patches("vv4")}
        self.assertTrue(rows, "VV4 has no safety patches")
        self.assertIn(0x890F0, rows, "the VV4 record counter is not written")
        for offset in (0x89020, 0x89040, 0x89060, 0x89080, 0x890C0):
            with self.subTest(guard=hex(IMAGE_BASE + offset)):
                self.assertIn(offset, rows)
                self.assertNotIn(
                    "E86D4D00", rows[offset],
                    "guard still reads the unwritten 0x4D6DE8",
                )
                self.assertTrue(
                    rows[offset].startswith("E8"),
                    "guard must begin by calling the record counter",
                )


if __name__ == "__main__":
    unittest.main()
