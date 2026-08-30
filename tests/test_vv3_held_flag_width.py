import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.c"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"


class VV3HeldFlagWidthTests(unittest.TestCase):
    def test_native_held_owner_reads_only_the_byte_at_f12(self) -> None:
        source = NATIVE.read_text(encoding="utf-8")

        # The stock held branch rejoins the authoritative head tuple, so the
        # inline callback must not suppress it or widen the byte into a dword.
        self.assertIn("held (`+0xF12`) branch rejoins", source)
        self.assertNotIn(
            "if (*(unsigned char *)((unsigned char *)record + 0xF12) != 0) return;",
            source,
        )
        self.assertNotIn(
            "*(int *)((unsigned char *)record + 0xF12)",
            source,
        )

    def test_exact_stock_set_and_clear_instructions_are_byte_stores(self) -> None:
        stock = STOCK.read_bytes()
        self.assertEqual(
            hashlib.sha256(stock).hexdigest().upper(),
            "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503",
        )

        # The exact stock image has the set instruction at 0x5835A.  The
        # following byte at 0x5835B is its ModRM byte (86), not an opcode.
        set_instruction = bytes.fromhex("C6 86 12 0F 00 00 01")
        clear_instruction = bytes.fromhex("C6 86 12 0F 00 00 00")
        self.assertEqual(stock[0x5835A : 0x5835A + len(set_instruction)], set_instruction)
        self.assertEqual(stock[0x5599B : 0x5599B + len(clear_instruction)], clear_instruction)

        # C6 /0 with a disp32 and imm8 is a byte-sized memory store, so the
        # adjacent +0xF13/+0xF14 bytes are not part of this flag write.
        self.assertEqual(set_instruction[:2], bytes.fromhex("C6 86"))
        self.assertEqual(clear_instruction[:2], bytes.fromhex("C6 86"))
        self.assertEqual(set_instruction[-1], 1)
        self.assertEqual(clear_instruction[-1], 0)


if __name__ == "__main__":
    unittest.main()
