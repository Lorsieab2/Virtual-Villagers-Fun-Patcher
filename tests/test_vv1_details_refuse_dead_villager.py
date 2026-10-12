"""A New Home: Villager Details upgrades refuse a dead villager.

The Villager Details screen acts on the record the stock click picker chose.
That picker (0x43CAF0) tests only the record's occupied byte (+0x28) and the
hit box, and a body keeps that byte set -- with health (+0x344) at 0 or below
-- until the village tick removes it 240 units after death (0x42E96D..
0x42E9C3, which is also where the stock code drops the selection).
detail_menu checked the same occupied byte only, so Grant Youth, Grant Full
Mastery, Grant Running and Set Age to 18 charged for and wrote to a corpse,
while the Tech menu's "to All" rows skip the dead.

detail_menu now calls DETAIL_LIVING_GATE (.shr raw 0x8BBE0) instead of
DETAIL_PREFLIGHT (raw 0x8BC00).  A body gets ShowOriginsRowMessage status 7
(VV1_ROWMSG_NOT_LIVING, no charge): "No valid living villager is selected. No
tech points have been deducted.", the wording The Lost Children and The Tree
of Life use; a living villager goes on to DETAIL_PREFLIGHT exactly as
before.  These tests run the manifest's real
bytes in an emulator.
"""
from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path

from unicorn import UC_ARCH_X86, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_EDX, UC_X86_REG_ESI,
    UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "vv1_origins_feature.json"

# .shr is stored at raw 0x8B000 and mapped at RVA 0x8D000.
SHR_RAW, SHR_VA = 0x8B000, 0x48D000
GATE_RAW, PREFLIGHT_RAW, DISLIKE_CLEAR_RAW = 0x8BBE0, 0x8BC00, 0x8BE80
GATE_VA = SHR_VA + (GATE_RAW - SHR_RAW)
PREFLIGHT_VA = SHR_VA + (PREFLIGHT_RAW - SHR_RAW)
# The main code cave is mapped 1:1 (VA = 0x400000 + raw); detail_menu is
# CODE_VA + 0x521.
CODE_RAW = 0x56900
DETAIL_MENU_RAW = CODE_RAW + 0x521

STACK = 0x70000000
RECORD = 0x20000000
RECORD_SIZE = 0x3D8
RETURN = 0x0BAD0000

OCCUPIED, HEALTH, AGE, AGE2, PREGNANT = 0x28, 0x344, 0x348, 0x34C, 0x358
GOLDEN_FLAG = 0x36C
LIKES, DISLIKES, SKILLS = 0x398, 0x3A8, 0x3BC
RUNNING = 38
ROW_YOUTH, ROW_MASTERY, ROW_RUNNING, ROW_AGE18 = 0, 1, 2, 3
PROCEED, NO_CHANGE, NOT_LIVING = 100, 1, 7


def manifest_patches() -> list[dict]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["patches"]


def bytes_at(raw: int, patches=None) -> bytes:
    for patch in patches or manifest_patches():
        start = int(patch["offset"], 16)
        data = bytes.fromhex(patch["after"])
        if start <= raw < start + len(data):
            return data[raw - start:]
    raise AssertionError(f"no manifest patch covers raw 0x{raw:X}")


def make_record(*, health=80, age=500, mastered=False, likes_running=False,
                full_likes=False, dislikes_running=False) -> bytearray:
    record = bytearray(RECORD_SIZE)
    record[OCCUPIED] = 1
    struct.pack_into("<i", record, HEALTH, health)
    struct.pack_into("<i", record, AGE, age)
    struct.pack_into("<i", record, AGE2, age)
    for slot in range(4):
        struct.pack_into("<i", record, LIKES + slot * 4, 7 if full_likes else -1)
        struct.pack_into("<i", record, DISLIKES + slot * 4, -1)
    if likes_running:
        struct.pack_into("<i", record, LIKES, RUNNING)
    if dislikes_running:
        struct.pack_into("<i", record, DISLIKES, RUNNING)
    for skill in range(5):
        struct.pack_into("<i", record, SKILLS + skill * 4, 100 if mastered else 20)
    return record


def run_gate(record: bytearray, row: int):
    """Call the gate as detail_menu does (ebx = row, edx = record).

    Returns (eax, ebx, record bytes after)."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    uc.mem_map(SHR_VA, 0x1000)
    patches = manifest_patches()
    for raw in (GATE_RAW, PREFLIGHT_RAW, DISLIKE_CLEAR_RAW):
        code = bytes_at(raw, patches)[:0x100]
        uc.mem_write(SHR_VA + (raw - SHR_RAW), code)
    uc.mem_map(RECORD, 0x1000)
    uc.mem_write(RECORD, bytes(record))
    uc.mem_map(STACK - 0x10000, 0x20000)
    uc.mem_map(RETURN, 0x1000)
    esp = STACK - 4
    uc.mem_write(esp, struct.pack("<I", RETURN))
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_EBX, row)
    uc.reg_write(UC_X86_REG_EDX, RECORD)
    uc.reg_write(UC_X86_REG_ESI, 0x2222)
    uc.emu_start(GATE_VA, RETURN, count=5000)
    assert uc.reg_read(UC_X86_REG_ESP) == STACK
    assert uc.reg_read(UC_X86_REG_ESI) == 0x2222
    after = bytearray(uc.mem_read(RECORD, RECORD_SIZE))
    return uc.reg_read(UC_X86_REG_EAX), uc.reg_read(UC_X86_REG_EBX), after


class Vv1DetailsRefuseDeadVillagerTests(unittest.TestCase):
    def test_detail_menu_calls_the_gate_not_the_preflight(self) -> None:
        code = bytes_at(DETAIL_MENU_RAW)[:0x200]
        targets = []
        for i in range(len(code) - 4):
            if code[i] == 0xE8:
                rel = struct.unpack_from("<i", code, i + 1)[0]
                targets.append(0x400000 + DETAIL_MENU_RAW + i + 5 + rel)
        self.assertIn(GATE_VA, targets, "detail_menu must route rows 0-3 through the gate")
        self.assertNotIn(PREFLIGHT_VA, targets, "detail_menu must not skip the gate")

    def test_gate_fits_before_the_preflight(self) -> None:
        for patch in manifest_patches():
            if int(patch["offset"], 16) == GATE_RAW:
                # 0x8BB70..0x8BBDB is the patcher's Start Over stub
                # (MAIN_MENU_START_OVER_CAVE in src/vv_fun_patcher.py).
                self.assertGreaterEqual(GATE_RAW, 0x8BB70 + 0x6B)
                self.assertLessEqual(GATE_RAW + len(patch["after"]) // 2, PREFLIGHT_RAW)
                return
        self.fail("no living-villager gate patch at raw 0x8BBE0")

    def test_every_row_refuses_a_dead_villager_with_no_charge_or_change(self) -> None:
        for row in (ROW_YOUTH, ROW_MASTERY, ROW_RUNNING, ROW_AGE18):
            for health in (0, -5):
                with self.subTest(row=row, health=health):
                    # Full Likes plus a Running Dislike: the living path would
                    # clear that Dislike for free; a body must stay untouched.
                    record = make_record(health=health, full_likes=True,
                                         dislikes_running=True)
                    eax, ebx, after = run_gate(record, row)
                    self.assertEqual(eax, NOT_LIVING, "a body must not be charged")
                    self.assertEqual(ebx, row, "the row is kept for the message")
                    self.assertEqual(after, record)

    def test_living_villager_behaves_as_before(self) -> None:
        for row in (ROW_YOUTH, ROW_MASTERY, ROW_RUNNING, ROW_AGE18):
            with self.subTest(row=row):
                eax, ebx, _ = run_gate(make_record(), row)
                self.assertEqual((eax, ebx), (PROCEED, row))
        eax, ebx, _ = run_gate(make_record(mastered=True), ROW_MASTERY)
        self.assertEqual((eax, ebx), (NO_CHANGE, ROW_MASTERY))
        eax, ebx, _ = run_gate(make_record(age=360), ROW_AGE18)
        self.assertEqual((eax, ebx), (NO_CHANGE, ROW_AGE18))
        eax, ebx, _ = run_gate(make_record(likes_running=True), ROW_RUNNING)
        self.assertEqual((eax, ebx), (NO_CHANGE, ROW_RUNNING))
        golden = make_record()
        struct.pack_into("<i", golden, GOLDEN_FLAG, 0xC7)
        eax, ebx, _ = run_gate(golden, ROW_AGE18)
        self.assertEqual((eax, ebx), (6, ROW_AGE18))


if __name__ == "__main__":
    unittest.main()
