"""The VV5 Barrel of Babies must force the believer barrel, not its neighbours.

The purchase forces one event id into the scheduler's pick. Getting that id
from the string table is a trap, and the shipping build fell into it: the
player bought the barrel and got "The Stinging Wasps", with no children.

There are two different tables and they do not line up.

  * 0x004D7B24 is the STRING table, 0x20 bytes per entry, title pointer at
    +0x00 and description pointer at +0x10.
  * 0x004DC850 is the EVENT OBJECT table the scheduler actually indexes, at
    0x00418850..0x004188E3. It is built at runtime, so it is empty in the
    file image and can only be read through the constructor that fills it.

The string table has an entry for the Banyan Festival; the object table has no
object for it. Every id after that point is therefore shifted by one, which is
exactly how the believer barrel at string index 27 became the Stinging Wasps
at object index 25.

This test does not trust either restated number. It walks the constructor,
recovers each slot's vtable, and reads the MSVC RTTI class name, so the id is
derived from the binary every run.
"""
from __future__ import annotations

import re
import struct
import unittest
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
SELECTOR_SOURCE = ROOT / "scripts" / "build_vv5_origins_feature.py"

EVENT_OBJECT_TABLE = 0x004DC850
CONSTRUCTOR = 0x00417700
CONSTRUCTOR_END = 0x00417E00

BELIEVER_BARREL = ".?AVCEventBarrelOBabiesV@@"
HEATHEN_BARREL = ".?AVCEventBarrelOHeathenBabiesV@@"
STINGING_WASPS = ".?AVCEventTheStingingWasps@@"

# The population cap gate the scheduler calls as the barrel's eligibility test,
# and the villager-spawn call its effect method makes three times.
CAP_GATE = 0x00472BD0
SPAWN = 0x00471E20


class VV5Image:
    def __init__(self, path: Path) -> None:
        self.pe = pefile.PE(str(path), fast_load=True)
        self.base = self.pe.OPTIONAL_HEADER.ImageBase
        self.data = path.read_bytes()

    def offset(self, va: int):
        rva = va - self.base
        for section in self.pe.sections:
            size = max(section.Misc_VirtualSize, section.SizeOfRawData)
            if section.VirtualAddress <= rva < section.VirtualAddress + size:
                return section.PointerToRawData + (rva - section.VirtualAddress)
        return None

    def u32(self, va: int) -> int:
        offset = self.offset(va)
        return struct.unpack_from("<I", self.data, offset)[0] if offset is not None else 0

    def cstring(self, va: int):
        offset = self.offset(va)
        if offset is None:
            return None
        end = self.data.find(b"\0", offset)
        return self.data[offset:end].decode("ascii", "replace")

    def class_name(self, vtable: int):
        """MSVC RTTI: vtable[-1] -> complete object locator -> type descriptor."""
        locator = self.u32(vtable - 4)
        if not locator:
            return None
        descriptor = self.u32(locator + 12)
        if not descriptor:
            return None
        return self.cstring(descriptor + 8)


def _walk_constructor(image: VV5Image):
    """Pair each vtable store in the table constructor with its table slot.

    The constructor allocates an object, writes its vtable, and only then
    stores the POINTER of the object built just before it. So the vtable seen
    most recently belongs to the slot named by the next store.
    """
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.skipdata = True
    start = image.offset(CONSTRUCTOR)
    blob = image.data[start : start + (CONSTRUCTOR_END - CONSTRUCTOR)]
    pending = None
    slots = {}
    vtables = {}
    for insn in md.disasm(blob, CONSTRUCTOR):
        text = insn.op_str
        if insn.mnemonic == "mov" and text.startswith("dword ptr [eax], 0x"):
            pending = int(text.rsplit("0x", 1)[1], 16)
        elif insn.mnemonic == "mov" and re.match(
            r"^dword ptr \[0x[0-9a-f]+\], eax$", text
        ):
            target = int(text.split("[0x")[1].split("]")[0], 16)
            if pending is not None and target >= EVENT_OBJECT_TABLE:
                index, remainder = divmod(target - EVENT_OBJECT_TABLE, 4)
                if remainder == 0:
                    name = image.class_name(pending)
                    if name:
                        slots[index] = name
                        vtables[index] = pending
                pending = None
    return slots, vtables


@unittest.skipUnless(STOCK.is_file(), "stock VV5 executable is not checked in")
class VV5BarrelEventIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.image = VV5Image(STOCK)
        cls.slots, cls.vtables = _walk_constructor(cls.image)

    def test_the_constructor_yields_the_three_barrel_neighbours(self) -> None:
        """Guards the recovery itself, so a broken walk cannot pass vacuously."""
        for index in (25, 26, 27):
            self.assertIn(index, self.slots, f"no class recovered for slot {index}")

    def test_slot_25_is_the_stinging_wasps(self) -> None:
        """The id the shipping build forced, and what the player actually saw."""
        self.assertEqual(self.slots[25], STINGING_WASPS)

    def test_slot_26_is_the_believer_barrel(self) -> None:
        self.assertEqual(self.slots[26], BELIEVER_BARREL)

    def test_slot_27_is_the_heathen_barrel(self) -> None:
        """So a 'fix' matching the string-table index would pick the wrong one."""
        self.assertEqual(self.slots[27], HEATHEN_BARREL)

    def test_the_believer_barrel_is_gated_on_the_population_cap(self) -> None:
        """vtable slot 1 is the eligibility predicate the scheduler calls."""
        eligibility = self.image.u32(self._vtable_for(BELIEVER_BARREL) + 4)
        self.assertIn(CAP_GATE, self._calls_from(eligibility, 0x40))

    def test_the_believer_barrel_effect_spawns_three_children(self) -> None:
        """vtable slot 12 is the effect; it must call the spawn three times."""
        effect = self.image.u32(self._vtable_for(BELIEVER_BARREL) + 12 * 4)
        calls = self._calls_from(effect, 0x140)
        self.assertEqual(
            calls.count(SPAWN), 3, "the believer barrel must spawn three children"
        )
        # Two of the three sit behind a room check; the first one does not.
        self.assertEqual(calls.count(CAP_GATE), 2)

    def test_the_wasps_do_not_spawn_anyone(self) -> None:
        """Why the wrong id produced a pop-up and no children."""
        effect = self.image.u32(self._vtable_for(STINGING_WASPS) + 12 * 4)
        self.assertEqual(self._calls_from(effect, 0x140).count(SPAWN), 0)

    def test_the_shipping_selector_forces_the_believer_barrel(self) -> None:
        source = SELECTOR_SOURCE.read_text(encoding="utf-8")
        # Anchor on the routine body, not on the name: the name also appears in
        # the payload-offset table far above, which would slice an empty block.
        marker = "and dword ptr [0x51D388], 0xFFFFFFFB"
        start = source.index(marker)
        block = source[start : source.index("done:", start)]
        match = re.search(r"^\s*mov esi, (\d+)\s*$", block, re.M)
        self.assertIsNotNone(match, "the selector no longer forces a literal id")
        forced = int(match.group(1))
        self.assertEqual(
            self.slots.get(forced),
            BELIEVER_BARREL,
            f"the selector forces id {forced}, which is {self.slots.get(forced)}",
        )

    # -- helpers -----------------------------------------------------------
    def _vtable_for(self, class_name: str) -> int:
        for index, name in self.slots.items():
            if name == class_name:
                return self.vtables[index]
        self.fail(f"{class_name} is not in the event object table")

    def _calls_from(self, start: int, length: int) -> list:
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        md.skipdata = True
        offset = self.image.offset(start)
        out = []
        for insn in md.disasm(self.image.data[offset : offset + length], start):
            if insn.mnemonic == "call" and insn.op_str.startswith("0x"):
                out.append(int(insn.op_str, 16))
            if insn.mnemonic == "ret":
                break
        return out


if __name__ == "__main__":
    unittest.main()
