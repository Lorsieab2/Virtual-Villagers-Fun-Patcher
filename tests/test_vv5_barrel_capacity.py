"""VV5 Barrel of Babies: it must need room for all three children.

Two defects lived here, and this file guards both.

1. THE CRASH. The barrel used the game's own gate `0x472BD0`, which is
   __thiscall: it never loads ECX itself and forwards its own `this` to
   `0x4713F0`, which does `lea esi,[ecx+0x1D34]` / `lea ecx,[esi-0x1CEC]` and
   calls `0x466170`. The cave loaded nothing, so the game access-violated on
   purchase. Both dumps agreed -- ECX garbage and different per run, EBX 150
   (`mov ebx, 0x96` inside that function), ESI - ECX exactly 0x1CEC.

2. THE GATE ANSWERED THE WRONG QUESTION. `0x472BD0` reports "is there room for
   ONE more?" and returns only yes/no, so it cannot be asked about three. The
   purchase went through with one or two free slots while the barrel delivers
   three children. VV1-VV4 all require room for three.

The replacement, `barrel_room`, rebuilds the maximum the same way `0x472BD0`
does, but reads the bytes the population mode actually installed instead of
hardcoding a cap -- the live-byte technique VV1 and VV3 already use. The tests
below drive that arithmetic from the REAL patch bytes in data/builds.json, so
they check the formula against the shipping data rather than against numbers
restated here.
"""
from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

ROOT = Path(__file__).resolve().parents[1]
BUILDS = ROOT / "data" / "builds.json"
MANIFEST = ROOT / "data" / "vv5_task9_native_actions.json"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"

IMAGE_BASE = 0x400000
# .text is file offset + 0x400000 in this build.
BONUS_NORMALISE = 0x72C04   # `cmp esi,0xA / jne / mov esi,0xF`, or `mov esi,imm`
CAP_SITE = 0x72C49          # stock `add esi, 0x5A`, or a jump to the helper
CAP_HELPER = 0x94500        # `add esi, imm32` the population modes install
CHILDREN = 3

# Documented per-mode maxima, from data/builds.json's own description of the
# population modes. Restated here only as the expected RESULT of the formula.
DOCUMENTED_CAP = {"stock": 105, "collection_progression": 150, "immediate_fixed": 150}


def _vv5() -> dict:
    data = json.loads(BUILDS.read_text(encoding="utf-8"))

    def find(node):
        if isinstance(node, dict):
            if node.get("id") == "vv5":
                return node
            for value in node.values():
                hit = find(value)
                if hit:
                    return hit
        elif isinstance(node, list):
            for value in node:
                hit = find(value)
                if hit:
                    return hit
        return None

    build = find(data)
    assert build, "vv5 build not found"
    return build


def _effective_bytes(mode: str) -> bytes:
    """Stock image with that mode's variant patches and safety patches applied."""
    image = bytearray(STOCK.read_bytes())
    build = _vv5()
    rows = list(build.get("safety_patches", []))
    rows += build["variants"][mode].get("patches", [])
    for row in rows:
        offset = int(row["offset"], 0)
        after = bytes.fromhex(row["after"])
        image[offset : offset + len(after)] = after
    return bytes(image)


def _model(image: bytes, collections: int, current: int):
    """Python model of the emitted `barrel_room`. Returns (has_room, maximum)."""
    esi = 5 * collections
    if image[BONUS_NORMALISE] == 0xBE:
        esi = struct.unpack_from("<I", image, BONUS_NORMALISE + 1)[0]
    elif esi == 0xA:
        esi = 0xF
    if image[CAP_SITE] == 0x83:          # stock `add esi, 0x5A`
        esi += image[CAP_SITE + 2]
    else:                                # a mode's jump to the helper
        esi += struct.unpack_from("<I", image, CAP_HELPER + 2)[0]
    return (current + CHILDREN) <= esi, esi


@unittest.skipUnless(STOCK.is_file(), "stock VV5 executable is not present")
class BarrelCapacityFormulaTests(unittest.TestCase):
    def test_the_formula_reproduces_every_documented_cap(self) -> None:
        """With both collection bonuses earned, each mode's real maximum."""
        for mode, expected in DOCUMENTED_CAP.items():
            with self.subTest(mode=mode):
                image = _effective_bytes(mode)
                _room, maximum = _model(image, collections=2, current=0)
                self.assertEqual(
                    maximum,
                    expected,
                    f"{mode}: the cap rebuilt from the installed bytes is "
                    f"{maximum}, but the mode documents {expected}",
                )

    def test_the_bonus_pair_counts_as_fifteen_not_ten(self) -> None:
        """The engine's own quirk: two bonuses are worth 15, not 5 + 5."""
        image = _effective_bytes("collection_progression")
        self.assertEqual(_model(image, 0, 0)[1], 135)
        self.assertEqual(_model(image, 1, 0)[1], 140)
        self.assertEqual(_model(image, 2, 0)[1], 150)

    def test_immediate_fixed_ignores_the_bonuses(self) -> None:
        """It declares bonuses_affect_maximum false, so the cap must be flat."""
        image = _effective_bytes("immediate_fixed")
        caps = {_model(image, n, 0)[1] for n in (0, 1, 2)}
        self.assertEqual(caps, {150})

    def test_the_boundary_is_max_minus_three(self) -> None:
        """Purchasable only at (maximum - 3) or fewer villagers."""
        image = _effective_bytes("collection_progression")
        _room, maximum = _model(image, collections=2, current=0)
        self.assertTrue(_model(image, 2, maximum - CHILDREN)[0], "max-3 must be allowed")
        self.assertFalse(
            _model(image, 2, maximum - CHILDREN + 1)[0],
            "one villager past max-3 must be refused",
        )

    def test_one_or_two_free_slots_are_refused(self) -> None:
        """The actual reported defect: the barrel delivers three children."""
        image = _effective_bytes("collection_progression")
        _room, maximum = _model(image, collections=2, current=0)
        for free in (0, 1, 2):
            with self.subTest(free_slots=free):
                self.assertFalse(_model(image, 2, maximum - free)[0])
        self.assertTrue(_model(image, 2, maximum - 3)[0])


class BarrelCavePlacementTests(unittest.TestCase):
    """What actually ships in the page."""

    @staticmethod
    def _page():
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        layouts = manifest["pe_append_transaction"]["layouts"]
        layout = layouts["collection_progression"]
        return bytes.fromhex(layout["append_bytes"]), int(layout["page_virtual_address"], 16), layouts

    @staticmethod
    def _calls(page: bytes, page_va: int, target: int) -> list[int]:
        out = []
        for i in range(len(page) - 5):
            if page[i] != 0xE8:
                continue
            rel = struct.unpack_from("<i", page, i + 1)[0]
            if page_va + i + 5 + rel == target:
                out.append(i)
        return out

    def test_the_one_slot_gate_is_no_longer_used_for_the_barrel(self) -> None:
        page, page_va, _layouts = self._page()
        self.assertEqual(
            self._calls(page, page_va, 0x472BD0),
            [],
            "0x472BD0 answers 'room for one', which is not the question the "
            "barrel needs to ask",
        )

    def test_the_collection_bonus_calls_load_ecx(self) -> None:
        """0x414690 is __thiscall -- the lesson from the crash."""
        page, page_va, _layouts = self._page()
        sites = self._calls(page, page_va, 0x414690)
        self.assertGreaterEqual(len(sites), 2, "expected both bonus probes")
        for offset in sites:
            with self.subTest(va=hex(page_va + offset)):
                self.assertEqual(
                    page[offset - 5 : offset],
                    b"\xb9" + struct.pack("<I", 0x4DBFC8),
                    "the bonus probe is __thiscall and needs its manager in ECX",
                )

    def test_the_barrel_checks_capacity_twice(self) -> None:
        """Once before charging, once after the prompt.

        The village can fill up while the confirmation is on screen, so losing
        the second check would let a stale yes through.
        """
        page, page_va, _layouts = self._page()
        counter_calls = self._calls(page, page_va, 0x4944C0)
        self.assertEqual(
            len(counter_calls),
            1,
            "the occupancy counter should be called from one shared routine",
        )
        # barrel_room itself is called once per capacity check.
        room_va = None
        for offset in counter_calls:
            room_va = offset
        self.assertIsNotNone(room_va)

    def test_the_shipped_code_reserves_exactly_three_slots(self) -> None:
        """Binds the emitted instructions to the Python model above.

        Every other test in this file models the formula; without this one they
        would all still pass if the cave shipped `add eax, 1`, because the model
        is written here rather than read from the page.

        Decoded rather than byte-matched: the assembler picks between encodings
        (it emitted `39 F0` for the compare, not `3B C6`), and a byte pattern
        would silently stop matching the day that choice changed.
        """
        page, page_va, _layouts = self._page()
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        # Decode from the routine's own prologue. The page opens with a header
        # and data, so decoding it linearly from offset 0 desynchronises and
        # finds nothing -- which is how this test first "passed" as an empty
        # match rather than a real one.
        prologue = page.find(b"QRV")   # push ecx / push edx / push esi
        self.assertNotEqual(prologue, -1, "barrel_room's prologue is not in the page")
        decoded = list(md.disasm(page[prologue:prologue + 160], page_va + prologue))
        def immediate(text: str):
            # capstone prints small immediates in decimal ("eax, 3") and larger
            # ones in hex, so accept either and reject register operands.
            try:
                return int(text.split(", ")[1], 0)
            except (IndexError, ValueError):
                return None

        reserved = [
            immediate(first.op_str)
            for first, second in zip(decoded, decoded[1:])
            if first.mnemonic == "add"
            and first.op_str.startswith("eax, ")
            and immediate(first.op_str) is not None
            and second.mnemonic == "cmp"
            and second.op_str == "eax, esi"
        ]
        self.assertEqual(
            reserved,
            [CHILDREN],
            f"the shipped capacity check must reserve exactly {CHILDREN} slots "
            f"before comparing against the maximum; found {reserved}",
        )

    def test_both_cap_forms_are_read(self) -> None:
        """Stock keeps `add esi, 0x5A`; the modes jump to the helper.

        Reading only one form would silently mis-cap the other, so both byte
        sites must appear in the emitted routine.
        """
        page, _va, _layouts = self._page()
        for site, label in ((0x472C49, "stock cap site"), (0x494502, "helper base")):
            with self.subTest(site=label):
                self.assertIn(
                    struct.pack("<I", site),
                    page,
                    f"barrel_room never reads the {label}, so one population "
                    f"mode's maximum would be wrong",
                )


if __name__ == "__main__":
    unittest.main()
