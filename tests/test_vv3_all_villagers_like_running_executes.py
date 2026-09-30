"""VV3 Village-wide "All Villagers Like Running", RUN from the rendered executable.

The optional Origins village-wide payload (vv3_origins_village_wide_upgrades)
is entered at 0x47B840 with EAX = command, ECX = the first villager record and
EDX = the record count.  Command 6 gives every active, living villager the
Running Like: the first free (-1) of its three Like slots at +0xFB4 is set to
the Running preference id and any Running Dislike in the three slots at +0xFC0
is cleared.  It returns full-Like skips in EAX, already-Running skips in EDX and
removed Dislikes in ECX.

The id is 38, read here from The Secret City's own preference list at file
offset 0x97488 (", "-separated, 0-based): entry 37 is "swimming", 38 "running".
A payload that wrote 37 would give the whole village Swimming.

Deliberately NOT asserted: what happens to a Running Dislike on a villager
whose Like slots are all full.  The manifest says it is cleared "whether or not
a Like was added"; the shipped VV3 payload skips it (only VV1 opts into
`always_clear_running_dislike` in scripts/build_village_wide_origins_features.py).
That disagreement is reported separately rather than pinned either way here.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI,
    UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402

EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Secret City.exe"
FEATURE = "vv3_origins_village_wide_upgrades"
ENTRY = 0x47B840
PREFERENCE_LIST = 0x97488
RUNNING = 38
STRIDE = 0x1F8C
ACTIVE, HEALTH, LIKES, DISLIKES = 0xF10, 0xE78, 0xFB4, 0xFC0
RECORDS = 0x20000000
RETURN = 0x0F000800
STACK_TOP = 0x10800000
KEPT = dict(ebx=UC_X86_REG_EBX, esi=UC_X86_REG_ESI, edi=UC_X86_REG_EDI, ebp=UC_X86_REG_EBP)

# (active, likes, dislikes) -> (likes after, dislikes after)
VILLAGERS = [
    ((1, [-1, -1, -1], [RUNNING, -1, -1]), ([RUNNING, -1, -1], [-1, -1, -1])),   # granted, dislike removed
    ((1, [5, -1, 7], [1, 2, 3]), ([5, RUNNING, 7], [1, 2, 3])),                 # first FREE slot
    ((1, [RUNNING - 1, -1, -1], [-1, 4, RUNNING]), ([RUNNING - 1, RUNNING, -1], [-1, 4, -1])),  # Swimming is not Running
    ((1, [9, RUNNING, -1], [-1, -1, -1]), ([9, RUNNING, -1], [-1, -1, -1])),    # already Running: unchanged
    ((1, [1, 2, 3], [4, 5, 6]), ([1, 2, 3], [4, 5, 6])),                         # full Likes, no Running Dislike
    ((0, [-1, -1, -1], [RUNNING, -1, -1]), ([-1, -1, -1], [RUNNING, -1, -1])),  # inactive: untouched
]
EXPECTED_COUNTS = dict(eax=1, edx=1, ecx=2)   # full-Like skips, already-Running, Dislikes removed


def _render() -> bytes:
    build = next(b for b in vfp.load_builds() if b.id == "vv3")
    ids = vfp.resolve_fun_patch_ids([FEATURE], game_id="vv3")
    rendered, applied = vfp.render_patched_bytes(EXE, build, "immediate_fixed", ids)
    assert f"feature:{FEATURE}" in {r["owner"] for r in applied}
    return bytes(rendered)


def _run(image: bytes, count: int) -> tuple[dict, list]:
    pe = pefile.PE(data=image)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(0x400000, (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF)
    mu.mem_write(0x400000, image[:pe.OPTIONAL_HEADER.SizeOfHeaders])
    for section in pe.sections:
        mu.mem_write(0x400000 + section.VirtualAddress, section.get_data())
    mu.mem_map(RETURN & ~0xFFF, 0x1000)
    mu.mem_map(RECORDS, 0x40000)
    mu.mem_map(STACK_TOP - 0x10000, 0x10000)
    mu.mem_write(RETURN, b"\xF4")
    for i, ((active, likes, dislikes), _) in enumerate(VILLAGERS):
        base = RECORDS + i * STRIDE
        mu.mem_write(base + ACTIVE, bytes([active]))
        mu.mem_write(base + HEALTH, struct.pack("<i", 50))
        mu.mem_write(base + LIKES, struct.pack("<3i", *likes))
        mu.mem_write(base + DISLIKES, struct.pack("<3i", *dislikes))
    esp = STACK_TOP - 0x100
    mu.mem_write(esp, struct.pack("<I", RETURN))
    mu.reg_write(UC_X86_REG_ESP, esp)
    sentinels = dict(ebx=0x11111111, esi=0x22222222, edi=0x33333333, ebp=0x44444444)
    for name, value in sentinels.items():
        mu.reg_write(KEPT[name], value)
    mu.reg_write(UC_X86_REG_EAX, 6)
    mu.reg_write(UC_X86_REG_ECX, RECORDS)
    mu.reg_write(UC_X86_REG_EDX, count)
    mu.emu_start(ENTRY, RETURN, count=20000)
    regs = {n: mu.reg_read(r) for n, r in (("eax", UC_X86_REG_EAX), ("edx", UC_X86_REG_EDX), ("ecx", UC_X86_REG_ECX))}
    regs["kept"] = {n: mu.reg_read(r) for n, r in KEPT.items()} == sentinels
    regs["esp"] = mu.reg_read(UC_X86_REG_ESP) - esp
    after = []
    for i in range(len(VILLAGERS)):
        base = RECORDS + i * STRIDE
        after.append((list(struct.unpack("<3i", mu.mem_read(base + LIKES, 12))),
                      list(struct.unpack("<3i", mu.mem_read(base + DISLIKES, 12)))))
    return regs, after


class VV3AllVillagersLikeRunningExecutes(unittest.TestCase):
    def test_the_stock_preference_list_names_id_38_running(self):
        data = EXE.read_bytes()
        text = data[PREFERENCE_LIST:data.index(b"\0", PREFERENCE_LIST)].decode("ascii")
        names = [name.strip() for name in text.split(",")]
        self.assertEqual(names[0], "ants")
        self.assertEqual(names[RUNNING], "running")
        self.assertEqual(names[RUNNING - 1], "swimming")
        raw = vfp.load_fun_patches()
        feature = next(p for p in raw if p.id == FEATURE).raw
        self.assertEqual(feature["running_preference_id"], RUNNING)
        self.assertEqual(feature["record_fields"]["running_preference_id"], RUNNING)

    def test_command_6_gives_every_active_villager_the_running_like(self):
        regs, after = _run(_render(), len(VILLAGERS))
        for i, (_, expected) in enumerate(VILLAGERS):
            with self.subTest(villager=i):
                self.assertEqual(after[i], expected)
        for name, value in EXPECTED_COUNTS.items():
            self.assertEqual(regs[name], value, name)
        self.assertTrue(regs["kept"], "EBX/ESI/EDI/EBP must be preserved")
        self.assertEqual(regs["esp"], 4, "near ret")

    def test_the_record_count_bounds_the_scan(self):
        # Only the first villager is in range; the second must stay as it was.
        _, after = _run(_render(), 1)
        self.assertEqual(after[0], VILLAGERS[0][1])
        self.assertEqual(after[1], (VILLAGERS[1][0][1], VILLAGERS[1][0][2]))


if __name__ == "__main__":
    unittest.main()
