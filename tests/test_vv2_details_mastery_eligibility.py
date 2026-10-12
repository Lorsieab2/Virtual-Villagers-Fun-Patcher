"""The Lost Children: Villager Details upgrades refuse a dead villager or a statue.

The Villager Details screen acts on the record the stock click picker chose.
That picker (0x44D580) tests only the record's active byte (+0x30) and the
hit box, so an Esteemed Elder statue (+0x558 != 0) or a dead villager
(+0x52C health <= 0) can be the selected record.  The Tech-menu "to All" rows
skip both (vv2_record_eligible in native/vv2_origins_icons), but the Details
rows' per-row check (DETAIL_NOCHANGE, .shr raw 0x9A380) only asked whether the
row was already satisfied, so Grant Full Mastery, Grant Youth, Grant Running
and Set Age to 18 charged and wrote to a statue or a corpse.

The helper now refuses both before the per-row check: it shows the existing
"No valid living villager is selected" result (status 3) and returns 1, which
makes the payload skip the charge.  These tests run the manifest's real helper
bytes in an emulator against a statue, a dead villager and living villagers.
"""
from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path

from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_EDI, UC_X86_REG_ESI,
    UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "vv2_origins_feature.json"

# .shr is stored at raw 0x9A000 and mapped at RVA 0x9C000.
SHR_RAW, SHR_VA = 0x9A000, 0x49C000
NOCHANGE_RAW = 0x9A380
NOCHANGE_VA = SHR_VA + (NOCHANGE_RAW - SHR_RAW)       # 0x49C380
NOCHANGE_LIMIT_RAW = 0x9A4A0                          # Barrel silent gate stub
RESULT_HELPER_VA = SHR_VA + (0x9A240 - SHR_RAW)       # 0x49C240, stdcall(action, status)

STACK = 0x70000000
RECORD = 0x20000000
RECORD_SIZE = 0xE48C
RETURN = 0x0BAD0000

ACTIVE, HEALTH, AGE, AGE2, PREGNANT = 0x30, 0x52C, 0x530, 0x534, 0x540
SPECIAL = 0x558
LIKES, DISLIKES, SKILLS = 0x5F0, 0x6E8, 0x7E4
RUNNING = 38
ROW_YOUTH, ROW_MASTERY, ROW_RUNNING, ROW_AGE18 = 0, 1, 2, 3
RES_NO_CHANGE, RES_INVALID = 1, 3


def nochange_bytes(manifest_path: Path = MANIFEST) -> bytes:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for patch in manifest["patches"]:
        if int(patch["offset"], 16) == NOCHANGE_RAW:
            return bytes.fromhex(patch["after"])
    raise AssertionError("no Detail no-change helper patch at raw 0x9A380")


def make_record(*, health=80, statue=0, mastered=False, age=500,
                likes_running=False) -> bytearray:
    record = bytearray(RECORD_SIZE)
    record[ACTIVE] = 1
    struct.pack_into("<i", record, HEALTH, health)
    record[SPECIAL] = statue
    struct.pack_into("<i", record, AGE, age)
    struct.pack_into("<i", record, AGE2, age)
    for slot in range(62):
        struct.pack_into("<i", record, LIKES + slot * 4, -1)
        struct.pack_into("<i", record, DISLIKES + slot * 4, -1)
    if likes_running:
        struct.pack_into("<i", record, LIKES, RUNNING)
    for skill in range(5):
        struct.pack_into("<i", record, SKILLS + skill * 4, 100 if mastered else 20)
    return record


def run_helper(code: bytes, record: bytearray, row: int):
    """Call the helper as the payload does: push row; push record; call.

    Returns (eax, results shown, record bytes after)."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    uc.mem_map(SHR_VA, 0x1000)
    uc.mem_write(NOCHANGE_VA, code)
    uc.mem_write(RESULT_HELPER_VA, b"\xC2\x08\x00")       # ret 8
    uc.mem_map(RECORD, 0x10000)
    uc.mem_write(RECORD, bytes(record))
    uc.mem_map(STACK - 0x10000, 0x20000)
    uc.mem_map(RETURN, 0x1000)
    esp = STACK
    for value in (row, RECORD, RETURN):
        esp -= 4
        uc.mem_write(esp, struct.pack("<I", value))
    uc.reg_write(UC_X86_REG_ESP, esp)
    for reg, value in ((UC_X86_REG_EBX, 0x1111), (UC_X86_REG_ESI, 0x2222),
                       (UC_X86_REG_EDI, 0x3333)):
        uc.reg_write(reg, value)

    shown: list[tuple[int, int]] = []

    def on_result(uc_, address, size, user):
        sp = uc_.reg_read(UC_X86_REG_ESP)
        action, status = struct.unpack("<II", uc_.mem_read(sp + 4, 8))
        shown.append((action, status))

    uc.hook_add(UC_HOOK_CODE, on_result, begin=RESULT_HELPER_VA,
                end=RESULT_HELPER_VA)
    uc.emu_start(NOCHANGE_VA, RETURN, count=20000)
    # stdcall ret 8 and the callee-saved registers survive.
    assert uc.reg_read(UC_X86_REG_ESP) == STACK
    assert (uc.reg_read(UC_X86_REG_EBX), uc.reg_read(UC_X86_REG_ESI),
            uc.reg_read(UC_X86_REG_EDI)) == (0x1111, 0x2222, 0x3333)
    after = bytearray(uc.mem_read(RECORD, RECORD_SIZE))
    return uc.reg_read(UC_X86_REG_EAX), shown, after


class Vv2DetailsMasteryEligibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.code = nochange_bytes()

    def test_helper_fits_its_slot(self) -> None:
        self.assertLessEqual(NOCHANGE_RAW + len(self.code), NOCHANGE_LIMIT_RAW)
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        end = NOCHANGE_RAW + len(self.code)
        for patch in manifest["patches"]:
            start = int(patch["offset"], 16)
            if start == NOCHANGE_RAW:
                continue
            stop = start + len(patch["after"]) // 2
            self.assertFalse(
                start < end and NOCHANGE_RAW < stop,
                f"helper 0x{NOCHANGE_RAW:X}..0x{end:X} overlaps {patch['offset']}",
            )

    def test_mastery_refuses_an_esteemed_elder_statue(self) -> None:
        eax, shown, after = run_helper(self.code, make_record(statue=1), ROW_MASTERY)
        self.assertEqual(eax, 1, "a statue must not be charged")
        self.assertEqual(shown, [(100 + ROW_MASTERY, RES_INVALID)])
        self.assertEqual(after, make_record(statue=1))

    def test_mastery_refuses_a_dead_villager(self) -> None:
        for health in (0, -5):
            with self.subTest(health=health):
                eax, shown, after = run_helper(
                    self.code, make_record(health=health), ROW_MASTERY
                )
                self.assertEqual(eax, 1, "a dead villager must not be charged")
                self.assertEqual(shown, [(100 + ROW_MASTERY, RES_INVALID)])
                self.assertEqual(after, make_record(health=health))

    def test_every_record_changing_row_refuses_statues_and_the_dead(self) -> None:
        # Youth, Running and Age 18 have the same gap: their village-wide
        # counterparts skip both through vv2_record_eligible.  A statue whose
        # Running dislike would otherwise be cleared for free stays untouched.
        for row in (ROW_YOUTH, ROW_MASTERY, ROW_RUNNING, ROW_AGE18):
            for kwargs in ({"statue": 1}, {"health": 0}):
                with self.subTest(row=row, **kwargs):
                    record = make_record(**kwargs)
                    for slot in range(62):
                        struct.pack_into("<i", record, LIKES + slot * 4, 7)
                    struct.pack_into("<i", record, DISLIKES, RUNNING)
                    eax, shown, after = run_helper(self.code, record, row)
                    self.assertEqual(eax, 1)
                    self.assertEqual(shown, [(100 + row, RES_INVALID)])
                    self.assertEqual(after, record)

    def test_living_villager_still_charges_or_reports_no_change(self) -> None:
        eax, shown, _ = run_helper(self.code, make_record(), ROW_MASTERY)
        self.assertEqual((eax, shown), (0, []))
        eax, shown, _ = run_helper(self.code, make_record(mastered=True), ROW_MASTERY)
        self.assertEqual((eax, shown), (1, [(100 + ROW_MASTERY, RES_NO_CHANGE)]))
        for skill in range(5):
            with self.subTest(unmastered_skill=skill):
                record = make_record(mastered=True)
                struct.pack_into("<i", record, SKILLS + skill * 4, 99)
                eax, shown, _ = run_helper(self.code, record, ROW_MASTERY)
                self.assertEqual((eax, shown), (0, []))
        eax, shown, _ = run_helper(self.code, make_record(age=500), ROW_AGE18)
        self.assertEqual((eax, shown), (0, []))
        eax, shown, _ = run_helper(self.code, make_record(age=360), ROW_AGE18)
        self.assertEqual((eax, shown), (1, [(100 + ROW_AGE18, RES_NO_CHANGE)]))
        eax, shown, _ = run_helper(self.code, make_record(), ROW_RUNNING)
        self.assertEqual((eax, shown), (0, []))
        eax, shown, _ = run_helper(self.code, make_record(age=500), ROW_YOUTH)
        self.assertEqual((eax, shown), (0, []))

    def test_dead_preflight_block_is_gone_from_the_builder(self) -> None:
        source = (ROOT / "scripts" / "build_vv2_origins_feature.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("DETAIL_PREFLIGHT", source)
        self.assertNotIn("detail_preflight_code", source)


if __name__ == "__main__":
    unittest.main()
