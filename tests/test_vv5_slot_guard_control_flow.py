"""VV5 slot-safety guards must rejoin the stock function, not return from it.

The reported VV5 "Barrel of Babies crashes on purchase" bug lived here.

VV5 has automatic safety patches that stop child-creating events from running
past the 150 physical villager slots.  Each detours a stock creation site to a
small helper that counts occupied and reserved slots, then either replays the
displaced instructions and resumes, or skips the creation.

The skip path was written as a bare `ret`:

    00494560  call 0x4944C0     ; count occupied + reserved slots
    00494565  cmp  eax, 0x96    ; 150
    0049456A  jge  0x494576
    0049456C  push 0xC8         ; replay displaced instruction
    00494571  jmp  0x4151D5     ; resume stock event
    00494576  ret               ; <-- skip path

`0x4151D0` is a long stock function that creates several children in sequence,
not a callable entry.  Returning from it early hands the caller `EAX` = the slot
count, which the caller then uses as a villager record pointer: `[150 + 0x1CD4]`
is address `0x1D6A`.  The recorded crash is exactly that -- WER `c0000005`,
exception offset `0x66170` (VA `0x466170`), the villager predicate whose first
instruction is `cmp byte ptr [ecx + 0x1CD4], 0`.

The fix makes the skip path jump past just that one creation and continue the
stock function, so the stack stays balanced and no invented value is returned.

Not every guard was wrong.  The Abandoned Infants site at `0x4155E0` really is a
short standalone function -- six pushes, one call, `ret`, then `int3` padding --
so its guard returning is correct.  That difference is asserted here too,
because "fixing" it would break it.
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

ROOT = Path(__file__).resolve().parents[1]
BUILDS = ROOT / "data" / "builds.json"
IMAGE_BASE = 0x400000

# VV5 .text: code runs to 0x494339; beyond that is the tail padding the patch
# uses for caves, still mapped and executable because .text's raw size reaches
# 0x495000.
TEXT_CODE_END = 0x494339
TEXT_RAW_END = 0x495000

# Guards that detour a creation site inside a longer stock function.  Skipping
# must continue that function at the given address, never return from it.
RESUMING_GUARDS = {
    0x94560: {"resume": 0x415205, "site": 0x4151D0, "what": "Barrel O' Babies believer child"},
    0x94580: {"resume": 0x4152ED, "site": 0x4152B0, "what": "Barrel O' Babies Heathen child"},
    0x945A0: {"resume": 0x415445, "site": 0x415410, "what": "Chutes Without Ladders child"},
}

# Guards whose detoured site is a genuine standalone function, where returning
# is the correct way to skip.
RETURNING_GUARDS = {
    0x945E0: {"site": 0x4155E0, "what": "Abandoned Infants clamp"},
}


def _vv5_safety_patches() -> list[dict]:
    data = json.loads(BUILDS.read_text(encoding="utf-8"))
    game = next(g for g in data["games"] if g["id"] == "vv5")
    return game["safety_patches"]


def _row(offset: int) -> dict:
    for row in _vv5_safety_patches():
        if int(row["offset"], 16) == offset:
            return row
    raise AssertionError(f"no VV5 safety patch at {offset:#x}")


def _disasm(blob: bytes, va: int):
    return list(Cs(CS_ARCH_X86, CS_MODE_32).disasm(blob, va))


class SlotGuardControlFlowTests(unittest.TestCase):
    @unittest.skipUnless(HAVE_CAPSTONE, "requires Capstone")
    def test_resuming_guards_never_return_from_mid_function(self) -> None:
        for offset, spec in RESUMING_GUARDS.items():
            with self.subTest(guard=hex(IMAGE_BASE + offset), what=spec["what"]):
                blob = bytes.fromhex(_row(offset)["after"])
                insns = _disasm(blob, IMAGE_BASE + offset)
                self.assertTrue(insns, "guard did not disassemble")

                self.assertEqual(
                    [i.mnemonic for i in insns if i.mnemonic == "ret"], [],
                    f"the {spec['what']} guard returns from {spec['site']:#x}, "
                    f"which is a long stock function rather than a callable "
                    f"entry. The caller then uses the slot count in EAX as a "
                    f"villager pointer -- that is the crash at 0x466170.",
                )

                last = insns[-1]
                self.assertEqual(
                    last.mnemonic, "jmp",
                    f"the {spec['what']} guard must end by rejoining stock code",
                )
                self.assertEqual(
                    int(last.op_str, 16), spec["resume"],
                    f"the {spec['what']} guard must resume at "
                    f"{spec['resume']:#x}, immediately after the creation call "
                    f"it skips",
                )

    @unittest.skipUnless(HAVE_CAPSTONE, "requires Capstone")
    def test_every_guard_branch_stays_inside_real_code(self) -> None:
        """A skip or resume target must land in stock code or a written cave,
        never in zero-filled tail padding."""
        written = [
            (int(r["offset"], 16), len(r["after"]) // 2)
            for r in _vv5_safety_patches()
        ]
        for offset in list(RESUMING_GUARDS) + list(RETURNING_GUARDS):
            for insn in _disasm(
                bytes.fromhex(_row(offset)["after"]), IMAGE_BASE + offset
            ):
                if insn.mnemonic not in ("jmp", "call"):
                    continue
                operand = insn.op_str.strip()
                if not operand.startswith("0x"):
                    continue
                target = int(operand, 16)
                with self.subTest(
                    guard=hex(IMAGE_BASE + offset), target=hex(target)
                ):
                    if target < TEXT_CODE_END:
                        continue  # ordinary stock code
                    self.assertLess(
                        target, TEXT_RAW_END, "branch leaves the image entirely"
                    )
                    file_offset = target - IMAGE_BASE
                    self.assertTrue(
                        any(
                            start <= file_offset < start + length
                            for start, length in written
                        ),
                        f"{target:#x} is in .text tail padding but no safety "
                        f"patch writes it, so this branch would run zero bytes",
                    )

    @unittest.skipUnless(HAVE_CAPSTONE, "requires Capstone")
    def test_the_standalone_guard_still_returns(self) -> None:
        """Abandoned Infants detours a real function entry, so returning is
        correct there; rewriting it to jump would be a regression."""
        for offset, spec in RETURNING_GUARDS.items():
            with self.subTest(guard=hex(IMAGE_BASE + offset), what=spec["what"]):
                insns = _disasm(
                    bytes.fromhex(_row(offset)["after"]), IMAGE_BASE + offset
                )
                self.assertTrue(
                    any(i.mnemonic == "ret" for i in insns),
                    f"the {spec['what']} guard must still return",
                )

    @unittest.skipUnless(HAVE_CAPSTONE, "requires Capstone")
    def test_the_slot_counter_is_a_real_called_function(self) -> None:
        """The guards call a counter at 0x4944C0; it must be written, sweep the
        villager records, and return normally."""
        row = _row(0x944C0)
        blob = bytes.fromhex(row["after"])
        self.assertTrue(blob, "the slot counter is not written")
        insns = _disasm(blob, 0x4944C0)
        self.assertEqual(
            insns[-1].mnemonic, "ret",
            "the counter is reached by CALL, so it must return",
        )
        text = " ".join(f"{i.mnemonic} {i.op_str}" for i in insns)
        self.assertIn("0x554190", text, "record base")
        self.assertIn("0x2f44", text, "record stride")
        self.assertIn("0x1cd4", text, "active-slot offset")

    def test_guards_are_written_over_padding_only(self) -> None:
        for offset in list(RESUMING_GUARDS) + list(RETURNING_GUARDS) + [0x944C0]:
            with self.subTest(guard=hex(IMAGE_BASE + offset)):
                before = bytes.fromhex(_row(offset)["before"])
                self.assertEqual(
                    before, b"\0" * len(before),
                    "guard would overwrite real bytes rather than padding",
                )

    def test_guards_do_not_overrun_each_other(self) -> None:
        rows = sorted(
            (int(r["offset"], 16), len(r["after"]) // 2)
            for r in _vv5_safety_patches()
        )
        for (start, length), (next_start, _) in zip(rows, rows[1:]):
            with self.subTest(guard=hex(IMAGE_BASE + start)):
                self.assertLessEqual(
                    start + length, next_start,
                    "safety patches overlap; one guard is writing over another",
                )


if __name__ == "__main__":
    unittest.main()
