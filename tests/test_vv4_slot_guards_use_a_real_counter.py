"""VV4's five slot guards must count live demand, not read a running total.

They originally compared against `0x4D6DE8`, which IS written -- by
`add dword ptr [0x4d6de8], ecx` at 0x45E91C, where ecx is the babies a
pregnancy still owes. Nothing decrements it, so it is a lifetime total of
babies ever conceived. Once it passes 150 the guards suppress twins, triplets
and event children permanently, however empty the village is. (An earlier
account called the address unwritten; that came from decoding one byte late,
which turns the writer into `or eax, 0x4d6de8`. See
tests/test_slot_guard_population_source.py.)

Two regressions are pinned here, because neither is visible in play:

* a guard reverting to a static compare -- indistinguishable from a guard with
  no reason to fire;
* the counter reverting to occupied-records-only -- which preserves the base,
  stride, active byte, slot count, return and every guard call, so geometry
  checks alone still pass while unborn babies stop being counted and events can
  over-reserve the 150 physical slots.

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
# The running lifetime-conception total the guards used to read.
RUNNING_TOTAL_ADDRESS = 0x4D6DE8
# Record sweep the counter must perform.
RECORD_BASE = 0x50E5AC
RECORD_STRIDE = 0x2E3C
ACTIVE_BYTE = 0x1CC4
PREGNANT_FIELD = 0x1C4C
PENDING_BABIES = 0x1C50
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

    def test_no_guard_reads_the_running_total(self):
        """The exact regression: back to the lifetime-conception total."""
        for va in GUARD_VAS:
            with self.subTest(guard=hex(va)):
                text = " ; ".join(
                    f"{i.mnemonic} {i.op_str}" for i in self._disasm(va, 32)
                )
                self.assertNotIn(hex(RUNNING_TOTAL_ADDRESS), text.lower())

    def test_running_total_is_still_written_but_no_longer_consulted(self):
        """The stock writer stays; only the guards' dependence on it is gone."""
        needle = struct.pack("<I", RUNNING_TOTAL_ADDRESS)
        self.assertEqual(
            self.image.count(needle),
            1,
            "expected exactly the stock `add [0x4d6de8], ecx` writer",
        )

    def test_counter_sweeps_the_record_array(self):
        text = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in self._disasm(COUNTER_VA, 64))
        self.assertIn(hex(RECORD_BASE), text.lower(), "counter does not start at the pool")
        self.assertIn(hex(RECORD_STRIDE), text.lower(), "counter does not use the record stride")
        self.assertIn(hex(ACTIVE_BYTE), text.lower(), "counter does not test the active byte")
        self.assertIn(hex(SLOT_COUNT), text.lower(), "counter does not bound at 150 slots")

    def test_counter_adds_pending_babies_behind_a_pregnancy_gate(self):
        """Geometry alone is not enough.

        Reverting the helper to an occupied-records-only sweep keeps the base,
        stride, active byte, slot count, return and every guard call intact --
        so every other test here still passes while unborn babies stop being
        counted and events can reserve past the 150 physical slots. That is the
        regression the document's "physical demand" claim rests on, so assert it
        directly: the pregnancy field must be TESTED, the pending count ADDED,
        and the add must sit behind the test.
        """
        instructions = self._disasm(COUNTER_VA, 64)
        text = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in instructions).lower()
        self.assertIn(hex(PREGNANT_FIELD), text, "counter never tests the pregnancy field")
        self.assertIn(hex(PENDING_BABIES), text, "counter never adds the pending babies")

        gate = next(
            (i for i in instructions if hex(PREGNANT_FIELD) in i.op_str.lower()), None
        )
        add = next(
            (i for i in instructions if hex(PENDING_BABIES) in i.op_str.lower()), None
        )
        self.assertIsNotNone(gate)
        self.assertIsNotNone(add)
        self.assertEqual(gate.mnemonic, "cmp", "the pregnancy field is not tested")
        self.assertEqual(add.mnemonic, "add", "pending babies are not accumulated")
        self.assertLess(
            gate.address,
            add.address,
            "pending babies are added without first testing for a pregnancy",
        )
        between = [
            i
            for i in instructions
            if gate.address < i.address < add.address and i.mnemonic.startswith("j")
        ]
        self.assertTrue(
            between,
            "no branch between the pregnancy test and the add: the count would "
            "include babies for villagers who are not pregnant",
        )

    def test_counter_skips_unoccupied_records(self):
        """The active-byte test must gate the increment, not merely appear."""
        instructions = self._disasm(COUNTER_VA, 64)
        gate = next(
            (i for i in instructions if hex(ACTIVE_BYTE) in i.op_str.lower()), None
        )
        self.assertIsNotNone(gate, "counter never tests the active byte")
        self.assertEqual(gate.mnemonic, "cmp")
        following = [i for i in instructions if i.address > gate.address][:1]
        self.assertTrue(
            following and following[0].mnemonic.startswith("j"),
            "the occupancy test is not followed by a branch, so every record "
            "would be counted whether occupied or not",
        )

    def test_counter_returns_rather_than_falling_through(self):
        """VV5's mirror bug was a guard returning from mid-function."""
        instructions = self._disasm(COUNTER_VA, 64)
        self.assertTrue(
            any(i.mnemonic == "ret" for i in instructions),
            "the counter never returns to its caller",
        )


class VV4SlotGuardDocTests(unittest.TestCase):
    """Deliberately OUTSIDE the binary-dependent class.

    Both skip decorators there (capstone, and the gitignored stock exe) would
    otherwise skip this too -- so in exactly the dependency-free runs that are
    most common, the title regression would have no coverage at all.
    """

    def test_doc_does_not_claim_the_guards_are_inert(self):
        doc = (ROOT / "docs" / "vv4-slot-guards-are-inert.md").read_text(encoding="utf-8")
        self.assertNotIn(
            "# VV4's 150-slot safety guards never fire",
            doc,
            "the doc's title again asserts a defect the image disproves",
        )

    def test_doc_does_not_claim_nothing_writes_the_address(self):
        """The error this file has carried twice: 0x4D6DE8 IS written by
        `add dword ptr [0x4d6de8], ecx` at 0x45E91C. Decoding one byte late
        hides the writer."""
        doc = (ROOT / "docs" / "vv4-slot-guards-are-inert.md").read_text(encoding="utf-8")
        self.assertNotIn("**Nothing ever wrote `0x4D6DE8`.**", doc)
        self.assertIn("add dword ptr [0x4d6de8], ecx", doc.lower())

    def test_doc_does_not_claim_the_playtest_is_done(self):
        """Static disassembly is not runtime evidence."""
        doc = (ROOT / "docs" / "vv4-slot-guards-are-inert.md").read_text(encoding="utf-8")
        self.assertNotIn("All four were completed", doc)


if __name__ == "__main__":
    unittest.main()
