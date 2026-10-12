"""The Secret City: Villager Details upgrades refuse a dead villager.

The Villager Details screen acts on the record the stock click picker chose.
That picker (0x460D20) and the record check get_detail_record relies on
(0x45EE60) test only the active byte (+0xF10), and a body keeps it set -- with
health (+0xE78) at 0 or below -- until the tick removes it 240 units after
death (0x45F3F5..0x45F45B).  So Grant Youth, Grant Full Mastery, Grant Running
(including its free Running-Dislike clear) and Set Age to 18 charged for and
wrote to a corpse, while the Tech menu's "to All" rows skip the dead.

detail_menu now calls detail_living_check (payload +0x320) right after it
re-reads the record and goes to detail_status on "less or equal", showing
the existing "No changes were needed. No tech points have been deducted."
string before any charge.  These tests run the manifest's real bytes.
"""
from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path

from unicorn import UC_ARCH_X86, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDX,
    UC_X86_REG_EFLAGS, UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "vv3_origins_feature.json"

IMAGE_BASE = 0x400000
PAYLOAD_RAW = 0xA3180
PAYLOAD_VA = IMAGE_BASE + PAYLOAD_RAW
CHECK_VA = PAYLOAD_VA + 0x320
TECH_MENU_VA = PAYLOAD_VA + 0x340
SHOW_MESSAGE_VA = PAYLOAD_VA + 0x280
DETAIL_MENU_VA = PAYLOAD_VA + 0x650
TECH_INCREMENT_VA = PAYLOAD_VA + 0xA20
NO_CHANGE_TEXT = b"No changes were needed. No tech points have been deducted.\0"

STACK = 0x70000000
RECORD = 0x20000000
RECORD_SIZE = 0x1F8C
RETURN = 0x0BAD0000
HEALTH, ACTIVE = 0xE78, 0xF10
ROW_YOUTH, ROW_MASTERY, ROW_RUNNING, ROW_AGE18, ROW_APPEARANCE = range(5)


def manifest_patches() -> list[dict]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["patches"]


def bytes_at_va(va: int, patches=None) -> bytes:
    raw = va - IMAGE_BASE
    for patch in patches or manifest_patches():
        start = int(patch["offset"], 16)
        data = bytes.fromhex(patch["after"])
        if start <= raw < start + len(data):
            return data[raw - start:]
    raise AssertionError(f"no manifest patch covers VA 0x{va:X}")


def make_record(health: int) -> bytearray:
    record = bytearray(RECORD_SIZE)
    record[ACTIVE] = 1
    struct.pack_into("<i", record, HEALTH, health)
    return record


def run_check(record: bytearray, row: int):
    """Returns (refused, eax, record after) the way detail_menu's jle reads it."""
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    uc.mem_map(PAYLOAD_VA & ~0xFFF, 0x2000)
    uc.mem_write(CHECK_VA, bytes_at_va(CHECK_VA)[:0x20])
    uc.mem_map(RECORD, 0x2000)
    uc.mem_write(RECORD, bytes(record))
    uc.mem_map(STACK - 0x10000, 0x20000)
    uc.mem_map(RETURN, 0x1000)
    esp = STACK - 4
    uc.mem_write(esp, struct.pack("<I", RETURN))
    uc.reg_write(UC_X86_REG_ESP, esp)
    uc.reg_write(UC_X86_REG_EBX, row)
    uc.reg_write(UC_X86_REG_EDX, RECORD)
    uc.reg_write(UC_X86_REG_ECX, 0x1111)
    uc.reg_write(UC_X86_REG_ESI, 0x2222)
    uc.emu_start(CHECK_VA, RETURN, count=100)
    assert uc.reg_read(UC_X86_REG_ESP) == STACK
    assert (uc.reg_read(UC_X86_REG_EBX), uc.reg_read(UC_X86_REG_EDX),
            uc.reg_read(UC_X86_REG_ECX), uc.reg_read(UC_X86_REG_ESI)) == (
        row, RECORD, 0x1111, 0x2222)
    flags = uc.reg_read(UC_X86_REG_EFLAGS)
    zf, sf, of = (flags >> 6) & 1, (flags >> 7) & 1, (flags >> 11) & 1
    refused = bool(zf or sf != of)  # what `jle` takes
    after = bytearray(uc.mem_read(RECORD, RECORD_SIZE))
    return refused, uc.reg_read(UC_X86_REG_EAX), after


class Vv3DetailsRefuseDeadVillagerTests(unittest.TestCase):
    def test_check_returns_the_existing_no_change_string(self) -> None:
        _, eax, _ = run_check(make_record(0), ROW_MASTERY)
        text = bytes_at_va(eax)[:len(NO_CHANGE_TEXT)]
        self.assertEqual(text, NO_CHANGE_TEXT)

    def test_four_rows_refuse_a_dead_villager(self) -> None:
        for row in (ROW_YOUTH, ROW_MASTERY, ROW_RUNNING, ROW_AGE18):
            for health in (0, -5):
                with self.subTest(row=row, health=health):
                    record = make_record(health)
                    refused, _, after = run_check(record, row)
                    self.assertTrue(refused)
                    self.assertEqual(after, record)

    def test_living_villagers_and_change_appearance_pass(self) -> None:
        for row in (ROW_YOUTH, ROW_MASTERY, ROW_RUNNING, ROW_AGE18, ROW_APPEARANCE):
            with self.subTest(row=row):
                self.assertFalse(run_check(make_record(1), row)[0])
                self.assertFalse(run_check(make_record(80), row)[0])
        self.assertFalse(run_check(make_record(0), ROW_APPEARANCE)[0])

    def test_detail_menu_refuses_before_running_preflight_and_charge(self) -> None:
        code = bytes_at_va(DETAIL_MENU_VA)[:TECH_INCREMENT_VA - DETAIL_MENU_VA]
        sites = []
        for i in range(len(code) - 10):
            if code[i] != 0xE8:
                continue
            rel = struct.unpack_from("<i", code, i + 1)[0]
            if DETAIL_MENU_VA + i + 5 + rel == CHECK_VA:
                sites.append(i)
        self.assertEqual(len(sites), 1, "detail_menu must call detail_living_check once")
        i = sites[0] + 5
        self.assertEqual(code[i:i + 2], b"\x0F\x8E", "jle must follow the check")
        target = DETAIL_MENU_VA + i + 6 + struct.unpack_from("<i", code, i + 2)[0]
        # detail_status: push eax / push <title> / call show_message.
        t = target - DETAIL_MENU_VA
        self.assertEqual(code[t], 0x50)
        self.assertEqual(code[t + 1], 0x68)
        rel = struct.unpack_from("<i", code, t + 7)[0]
        self.assertEqual(code[t + 6], 0xE8)
        self.assertEqual(target + 11 + rel, SHOW_MESSAGE_VA)
        # The check sits right after the second get_detail_record and before
        # the Running preflight (cmp ebx, 2) and the charge.
        self.assertEqual(code[i + 6:i + 9], b"\x83\xFB\x02")

    def test_check_fits_its_slot(self) -> None:
        tail = bytes_at_va(CHECK_VA)[:TECH_MENU_VA - CHECK_VA]
        self.assertTrue(any(tail), "no code at detail_living_check")
        self.assertTrue(tail.rstrip(b"\0").endswith(b"\xC3"))


if __name__ == "__main__":
    unittest.main()
