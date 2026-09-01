"""VV5 slot-safety guards must RETURN when the village is full.

VV5 has automatic safety patches that stop child-creating events from running
past the 150 physical villager slots.  Each detours a stock creation site to a
helper that counts occupied and reserved slots, then either replays the
displaced instructions and resumes, or skips the creation by returning.

I briefly changed those returns into jumps that continued the stock function,
on the theory that the detoured sites were mid-function.  **That was wrong, and
it was dangerous.**  The sites are function entries reached indirectly through
a handler table in `.rdata`:

    0x00497B6C: 0x004151D0     believer child handler
    0x00497BB4: 0x004152B0     Heathen child handler
    0x00497C44: 0x00415410     Chutes child handler

Each sits in a slot beside other handlers (`0x437D30`, `0x421FC0`, `0x4271C0`),
and the structure repeats per variant.  None has a direct `call` or `jmp` in
`.text`, which is why an "is it int3-padded / does anything call it" check
misread them as fall-through code.

Because they are entries, `ret` is the correct way to skip: it returns to the
dispatcher and the whole creation is abandoned.  Continuing into the function
instead skips only the FIRST child and then goes on to create the second and
third -- exactly the record-array overflow the guard exists to prevent, and the
overflow that corrupted saves before.

So: these guards must return, and this file exists to stop that mistake being
repeated.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

try:
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    HAVE_CAPSTONE = True
except ImportError:  # pragma: no cover - capstone is a dev dependency
    HAVE_CAPSTONE = False

try:
    import pefile
    HAVE_PEFILE = True
except ImportError:  # pragma: no cover
    HAVE_PEFILE = False

ROOT = Path(__file__).resolve().parents[1]
BUILDS = ROOT / "data" / "builds.json"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
IMAGE_BASE = 0x400000

# guard cave -> (detoured site, handler-table slot holding that site, label)
GUARDS = {
    0x94560: (0x4151D0, 0x497B6C, "Barrel O' Babies believer child"),
    0x94580: (0x4152B0, 0x497BB4, "Barrel O' Babies Heathen child"),
    0x945A0: (0x415410, 0x497C44, "Chutes Without Ladders child"),
    0x945E0: (0x4155E0, None,     "Abandoned Infants clamp"),
}


def _vv5_safety_patches() -> list[dict]:
    data = json.loads(BUILDS.read_text(encoding="utf-8"))
    return next(g for g in data["games"] if g["id"] == "vv5")["safety_patches"]


def _row(offset: int) -> dict:
    for row in _vv5_safety_patches():
        if int(row["offset"], 16) == offset:
            return row
    raise AssertionError(f"no VV5 safety patch at {offset:#x}")


def _disasm(blob: bytes, va: int):
    return list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(blob, va))


class SlotGuardControlFlowTests(unittest.TestCase):
    @unittest.skipUnless(HAVE_CAPSTONE, "requires Capstone")
    def test_every_guard_skips_by_returning(self) -> None:
        for offset, (site, _slot, label) in GUARDS.items():
            with self.subTest(guard=hex(IMAGE_BASE + offset), what=label):
                insns = _disasm(bytes.fromhex(_row(offset)["after"]),
                                IMAGE_BASE + offset)
                self.assertTrue(insns, "guard did not disassemble")
                self.assertEqual(
                    insns[-1].mnemonic, "ret",
                    f"the {label} guard must skip by returning from "
                    f"{site:#x}, which is a handler-table entry. Continuing "
                    f"into the function instead skips only the first child and "
                    f"then creates the second and third -- the record-array "
                    f"overflow this guard exists to prevent.",
                )

    @unittest.skipUnless(HAVE_CAPSTONE, "requires Capstone")
    def test_the_resume_path_replays_and_rejoins_the_stock_site(self) -> None:
        """The not-full path must put back the displaced bytes and continue."""
        for offset, (site, _slot, label) in GUARDS.items():
            row = _row(offset)
            insns = _disasm(bytes.fromhex(row["after"]), IMAGE_BASE + offset)
            jumps = [i for i in insns if i.mnemonic == "jmp"]
            if not jumps:
                continue      # Abandoned Infants replays inline and returns
            with self.subTest(guard=hex(IMAGE_BASE + offset), what=label):
                target = int(jumps[-1].op_str, 16)
                self.assertGreater(
                    target, site,
                    f"the {label} guard must resume INSIDE its detoured site",
                )
                self.assertLess(target, site + 0x40)

    @unittest.skipUnless(HAVE_CAPSTONE and HAVE_PEFILE, "requires Capstone and pefile")
    @unittest.skipUnless(STOCK.is_file(), "stock VV5 executable not present")
    def test_the_detoured_sites_really_are_handler_table_entries(self) -> None:
        """The evidence for why `ret` is correct.

        If these ever stop being table entries the reasoning above collapses,
        so the claim is checked rather than trusted.
        """
        image = pefile.PE(str(STOCK)).get_memory_mapped_image(ImageBase=IMAGE_BASE)
        for offset, (site, slot, label) in GUARDS.items():
            if slot is None:
                continue
            with self.subTest(site=hex(site), what=label):
                stored = int.from_bytes(
                    image[slot - IMAGE_BASE:slot - IMAGE_BASE + 4], "little"
                )
                self.assertEqual(
                    stored, site,
                    f"{slot:#x} no longer holds {site:#x}; the handler-table "
                    f"evidence for returning is gone",
                )

    @unittest.skipUnless(HAVE_CAPSTONE, "requires Capstone")
    def test_the_slot_counter_is_a_real_called_function(self) -> None:
        row = _row(0x944C0)
        insns = _disasm(bytes.fromhex(row["after"]), 0x4944C0)
        self.assertEqual(insns[-1].mnemonic, "ret")
        text = " ".join(f"{i.mnemonic} {i.op_str}" for i in insns)
        self.assertIn("0x554190", text, "record base")
        self.assertIn("0x2f44", text, "record stride")
        self.assertIn("0x1cd4", text, "active-slot offset")

    def test_guards_are_written_over_padding_only(self) -> None:
        for offset in list(GUARDS) + [0x944C0]:
            with self.subTest(guard=hex(IMAGE_BASE + offset)):
                before = bytes.fromhex(_row(offset)["before"])
                self.assertEqual(before, b"\0" * len(before))

    def test_guards_do_not_overrun_each_other(self) -> None:
        rows = sorted(
            (int(r["offset"], 16), len(r["after"]) // 2)
            for r in _vv5_safety_patches()
        )
        for (start, length), (next_start, _) in zip(rows, rows[1:]):
            with self.subTest(guard=hex(IMAGE_BASE + start)):
                self.assertLessEqual(start + length, next_start)


if __name__ == "__main__":
    unittest.main()
