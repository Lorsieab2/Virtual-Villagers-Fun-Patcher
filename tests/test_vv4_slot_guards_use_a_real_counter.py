"""VV4's five slot guards must decide from a counter, not a dead address.

They originally compared against `0x4D6DE8`, which nothing in the game or in
any manifest ever wrote. Its `.data` value stayed 0, so every guard evaluated
`0 >= 150` and always took the resume path: VV4's physical-slot protection did
nothing at all. `docs/vv4-slot-guards-are-inert.md` recorded that, and it has
since been fixed -- all five now call a record-counting helper.

The failure this pins is regression by reversion: a guard quietly going back to
a static compare would restore a silent no-op that no gameplay test notices,
because an inert guard looks exactly like a guard that had no reason to fire.

Asserted against a RENDERED executable rather than the generator source, since
what matters is the instruction the game executes.
"""

import struct
import unittest
from pathlib import Path
import sys

try:
    import capstone
except ImportError:  # pragma: no cover - exercised only without capstone
    capstone = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.vv_fun_patcher import load_builds, render_patched_bytes  # noqa: E402

STOCK = ROOT / "inputs" / "vv4-stock-copy" / "Virtual Villagers - The Tree of Life.exe"

COUNTER_VA = 0x4890F0
GUARD_VAS = (0x489020, 0x489040, 0x489060, 0x489080, 0x4890C0)
# The address the guards used to read and nothing ever wrote.
DEAD_ADDRESS = 0x4D6DE8
# Record sweep the counter must perform.
RECORD_BASE = 0x50E5AC
RECORD_STRIDE = 0x2E3C
ACTIVE_BYTE = 0x1CC4
SLOT_COUNT = 0x96


def _sections(image):
    pe = struct.unpack_from("<I", image, 0x3C)[0]
    count = struct.unpack_from("<H", image, pe + 6)[0]
    opt = struct.unpack_from("<H", image, pe + 20)[0]
    base = struct.unpack_from("<I", image, pe + 24 + 28)[0]
    out = []
    for i in range(count):
        o = pe + 24 + opt + i * 40
        out.append(
            (
                base + struct.unpack_from("<I", image, o + 12)[0],
                struct.unpack_from("<I", image, o + 8)[0],
                struct.unpack_from("<I", image, o + 20)[0],
                struct.unpack_from("<I", image, o + 16)[0],
            )
        )
    return out


@unittest.skipIf(capstone is None, "requires capstone")
@unittest.skipUnless(STOCK.is_file(), "requires the VV4 stock executable")
class VV4SlotGuardCounterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        builds = {b.id: b for b in load_builds()}
        # No optional patches: these are automatic safety edits, always applied.
        cls.image, _ = render_patched_bytes(STOCK, builds["vv4"], "stock", [])
        cls.sections = _sections(cls.image)
        cls.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

    def _offset(self, va):
        for start, vsize, raw, rsize in self.sections:
            if start <= va < start + max(vsize, rsize):
                return raw + (va - start)
        return None

    def _disasm(self, va, length):
        offset = self._offset(va)
        self.assertIsNotNone(offset, f"{va:#x} is not mapped")
        return list(self.md.disasm(self.image[offset : offset + length], va))

    def test_every_guard_calls_the_counter_first(self):
        for va in GUARD_VAS:
            with self.subTest(guard=hex(va)):
                first = self._disasm(va, 16)[0]
                self.assertEqual(first.mnemonic, "call", "guard does not start with a call")
                self.assertEqual(
                    int(first.op_str, 16),
                    COUNTER_VA,
                    "guard decides from something other than the record counter",
                )

    def test_no_guard_reads_the_dead_address(self):
        """The exact regression: back to a static compare nothing writes."""
        for va in GUARD_VAS:
            with self.subTest(guard=hex(va)):
                text = " ; ".join(
                    f"{i.mnemonic} {i.op_str}" for i in self._disasm(va, 32)
                )
                self.assertNotIn(hex(DEAD_ADDRESS), text.lower())

    def test_dead_address_is_referenced_nowhere_in_the_image(self):
        """If a future edit starts writing it, this documents the change."""
        needle = struct.pack("<I", DEAD_ADDRESS)
        # The lone stock match is an immediate inside `or eax, 0x4d6de8`.
        self.assertLessEqual(
            self.image.count(needle),
            1,
            "something now references the formerly dead guard address",
        )

    def test_counter_sweeps_the_record_array(self):
        text = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in self._disasm(COUNTER_VA, 64))
        self.assertIn(hex(RECORD_BASE), text.lower(), "counter does not start at the pool")
        self.assertIn(hex(RECORD_STRIDE), text.lower(), "counter does not use the record stride")
        self.assertIn(hex(ACTIVE_BYTE), text.lower(), "counter does not test the active byte")
        self.assertIn(hex(SLOT_COUNT), text.lower(), "counter does not bound at 150 slots")

    def test_counter_returns_rather_than_falling_through(self):
        """VV5's mirror bug was a guard returning from mid-function."""
        instructions = self._disasm(COUNTER_VA, 64)
        self.assertTrue(
            any(i.mnemonic == "ret" for i in instructions),
            "the counter never returns to its caller",
        )

    def test_doc_no_longer_claims_the_guards_are_inert(self):
        doc = (ROOT / "docs" / "vv4-slot-guards-are-inert.md").read_text(encoding="utf-8")
        self.assertNotIn(
            "# VV4's 150-slot safety guards never fire",
            doc,
            "the doc's title again asserts a defect the image disproves",
        )


if __name__ == "__main__":
    unittest.main()
