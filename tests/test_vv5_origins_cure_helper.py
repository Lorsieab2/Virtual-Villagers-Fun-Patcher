"""VV5 Origins dispatch helper (0x494EA0): the withdrawn Cure command never
touches a villager.

The helper used to carry an inline "Cure All" loop for Tech row 5 that cleared
each sick Believer's +0x1C48 and then ran `inc dword ptr [0x55490C]` for every
one of them. 0x55490C is not a statistic: it is villager record 0 (0x554190,
stride 0x2F44) +0x77C, which is entry 21 (+0x44) of that villager's 80-entry
action queue at record+0x0..+0x1B80. People Cured is 0x51D368 (the stock cure
at 0x46E202 and the Task9 Full Heal/Cure All both credit it there).

In every public mode the shipped Tech handler leaves .shr at 0x7B22C0 for the
Task9 page, so the legacy row-5 call into this helper is unreachable; the loop
was removed rather than corrected. These tests run the RENDERED helper with a
sick village in an emulator and require the withdrawn command to return
without a single memory write outside its own stack, and they check the
manifests never again carry an absolute write into the villager array.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import capstone
from capstone import x86 as cs_x86
import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EBX, UC_X86_REG_EIP, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402

STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
FEATURE_ID = "vv5_enable_origins_exclusive_features"
MODES = ("stock", "collection_progression", "immediate_fixed")
MANIFESTS = ("data/vv5_origins_feature.json", "data/vv5_task9_native_actions.json")

HELPER_VA = 0x494EA0
HELPER_FILE_OFFSET = 0x94EA0
HELPER_SPAN = 0x130                       # the helper's original 304-byte claim
RECORDS = 0x554190
STRIDE = 0x2F44
RECORD_COUNT = 150
PEOPLE_CURED = 0x51D368
OLD_WRONG_COUNTER = 0x55490C            # record 0 +0x77C
ACTIVE, MASK, HEALTH, SICK, FACTION = 0x1CD4, 0x1CE1, 0x1C40, 0x1C48, 0x1CEC
STACK_BASE, STACK_SIZE = 0x10000000, 0x10000
RETURN_SENTINEL = 0x0BADF00D

_cache: dict[str, bytes] = {}


def render(mode: str) -> bytes:
    if mode not in _cache:
        build = next(b for b in vfp.load_builds() if b.id == "vv5")
        image, _ = vfp.render_patched_bytes(STOCK, build, mode, [FEATURE_ID])
        _cache[mode] = bytes(image)
    return _cache[mode]


def run_helper(image: bytes, command: int) -> dict:
    """Call the rendered helper with EBX=command over a sick village and
    return every non-stack write plus the final state."""
    pe = pefile.PE(data=image, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    uc.mem_map(base, size)
    uc.mem_write(base, image[: pe.OPTIONAL_HEADER.SizeOfHeaders])
    for section in pe.sections:
        raw = image[section.PointerToRawData: section.PointerToRawData + section.SizeOfRawData]
        uc.mem_write(base + section.VirtualAddress, raw[: max(section.Misc_VirtualSize, len(raw))])
    uc.mem_map(STACK_BASE, STACK_SIZE)
    uc.mem_map(RETURN_SENTINEL & ~0xFFF, 0x1000)

    # A village where every villager is a living, sick, unmasked Believer --
    # exactly what the withdrawn loop would have "cured".
    for index in range(RECORD_COUNT):
        record = RECORDS + index * STRIDE
        uc.mem_write(record + ACTIVE, b"\x01")
        uc.mem_write(record + MASK, b"\x00")
        uc.mem_write(record + HEALTH, (50).to_bytes(4, "little"))
        uc.mem_write(record + SICK, b"\x01")
        uc.mem_write(record + FACTION, b"\x00")
    uc.mem_write(OLD_WRONG_COUNTER, (0x11223344).to_bytes(4, "little"))
    uc.mem_write(PEOPLE_CURED, (7).to_bytes(4, "little"))
    before = bytes(uc.mem_read(RECORDS, RECORD_COUNT * STRIDE))

    writes: list[tuple[int, int]] = []

    def on_write(_uc, _access, address, length, _value, _data):
        if not STACK_BASE <= address < STACK_BASE + STACK_SIZE:
            writes.append((address, length))

    uc.hook_add(UC_HOOK_MEM_WRITE, on_write)
    esp = STACK_BASE + STACK_SIZE - 0x100
    uc.mem_write(esp, RETURN_SENTINEL.to_bytes(4, "little"))
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_EBX, command)
    executed = [0]
    left_helper: list[int] = []

    def on_code(_uc, address, _size, _data):
        # The withdrawn command must stay inside the helper and return. Any
        # call out (the old loop's result message, a native routine) is
        # recorded and stops the run, so no import has to be faked.
        executed[0] += 1
        if not HELPER_VA <= address < HELPER_VA + HELPER_SPAN:
            left_helper.append(address)
            _uc.emu_stop()

    uc.hook_add(UC_HOOK_CODE, on_code)
    uc.emu_start(HELPER_VA, RETURN_SENTINEL, count=200_000)
    return {
        "eip": uc.reg_read(UC_X86_REG_EIP),
        "esp": uc.reg_read(UC_X86_REG_ESP) - esp,
        "writes": writes,
        "records_unchanged": bytes(uc.mem_read(RECORDS, RECORD_COUNT * STRIDE)) == before,
        "old_counter": int.from_bytes(uc.mem_read(OLD_WRONG_COUNTER, 4), "little"),
        "people_cured": int.from_bytes(uc.mem_read(PEOPLE_CURED, 4), "little"),
        "executed": executed[0],
        "left_helper": left_helper,
    }


def absolute_writes_into_records(code: bytes, va: int) -> list[str]:
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    found = []
    for insn in md.disasm(code, va):
        if not insn.operands or insn.mnemonic.startswith(("cmp", "test", "push", "lea")):
            continue
        destination = insn.operands[0]
        if (
            destination.type == cs_x86.X86_OP_MEM
            and destination.mem.base == 0
            and destination.mem.index == 0
            and RECORDS <= destination.mem.disp < RECORDS + RECORD_COUNT * STRIDE
        ):
            found.append(f"{insn.address:#x} {insn.mnemonic} {insn.op_str}")
    return found


class WithdrawnCureCommandTouchesNothing(unittest.TestCase):
    def test_rendered_helper_command_5_writes_nothing_in_every_public_mode(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                image = render(mode)
                result = run_helper(image, 5)
                self.assertEqual(result["left_helper"], [], "the withdrawn Cure command called out")
                self.assertEqual(result["eip"], RETURN_SENTINEL, "helper must return to its caller")
                self.assertEqual(result["esp"], 4, "plain ret: stack balanced")
                self.assertEqual(result["writes"], [], "the withdrawn Cure command wrote memory")
                self.assertTrue(result["records_unchanged"], "a villager record changed")
                self.assertEqual(result["old_counter"], 0x11223344, "record 0 +0x77C changed")
                self.assertEqual(result["people_cured"], 7, "People Cured changed without a cure")

    def test_rendered_helper_carries_no_absolute_write_into_the_villager_array(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                image = render(mode)
                helper = image[HELPER_FILE_OFFSET:HELPER_FILE_OFFSET + HELPER_SPAN]
                self.assertEqual(absolute_writes_into_records(helper, HELPER_VA), [])
                self.assertNotIn(bytes.fromhex("FF050C495500"), image)

    def test_manifests_carry_no_absolute_write_into_the_villager_array(self) -> None:
        for relative in MANIFESTS:
            manifest = json.loads((ROOT / relative).read_text(encoding="utf-8"))
            row = next(p for p in manifest["patches"] if int(p["offset"], 0) == HELPER_FILE_OFFSET)
            with self.subTest(manifest=relative):
                self.assertEqual(
                    absolute_writes_into_records(bytes.fromhex(row["after"]), HELPER_VA), []
                )
                self.assertNotIn("FF050C495500", json.dumps(manifest).upper())

    def test_shipped_tech_handler_leaves_shr_for_the_task9_page(self) -> None:
        # Why the legacy row-5 call is unreachable: the Tech hook enters .shr
        # at 0x7B2000, which for control 13 calls 0x7B22C0, and 0x7B22C0 is an
        # absolute jump to the Task9 page's tech entry.
        for mode in MODES:
            with self.subTest(mode=mode):
                image = render(mode)
                self.assertEqual(image[0x415F0:0x415F5].hex().upper(), "E90B0A3700")
                self.assertEqual(image[0xDB00E:0xDB013].hex().upper(), "E8AD020000")
                self.assertEqual(image[0xDB2C0:0xDB2C7].hex().upper(), "B800917C00FFE0")


if __name__ == "__main__":
    unittest.main()
