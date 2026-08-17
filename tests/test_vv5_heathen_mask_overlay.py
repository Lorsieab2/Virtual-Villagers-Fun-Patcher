"""Static-structure guard for the VV5 Heathen-mask SHIPPING render overlay.

Verifies the *shape* of the bracketed per-villager render hook: the flip site
(0x472481, just past the selection-ring block), both epilogue restore sites
(0x472B0F / 0x472B57), the +0x1BC0 choice gate, the colour-field save/set, the
faction flip held from after-the-ring through the epilogue (so the head + mask
draw heathen while the ring stays believer-white), the restore using the saved
villager pointer (esi is popped by the epilogue), the untouched ring gate, scratch
in .data (NOT .shr), the caves fitting the free slice, and a valid PE checksum.
A render hook can only be *proven* in-game; this only guards its structure.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "vv5_heathen_mask_overlay", ROOT / "scripts/build_vv5_heathen_mask_overlay.py"
)
assert SPEC and SPEC.loader
mask = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mask)

STOCK = ROOT / "research/stock-executables/Virtual Villagers - New Believers.exe"


def _need_stock() -> bytes:
    if not STOCK.exists():
        import unittest

        raise unittest.SkipTest("stock VV5 exe not present in this checkout")
    return STOCK.read_bytes()


def _disasm_at(raw: bytes, va: int, n: int):
    pe = pefile.PE(data=raw, fast_load=True)
    ib = pe.OPTIONAL_HEADER.ImageBase
    text = next(s for s in pe.sections if s.Name.rstrip(b"\x00") == b".text")
    off = text.PointerToRawData + (va - (ib + text.VirtualAddress))
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    return list(md.disasm(pe.__data__[off:off + n], va))


def test_scratch_lives_in_data_not_shr():
    for slot in (mask.SLOT_ACTIVE, mask.SLOT_SCED, mask.SLOT_SCEE, mask.SLOT_SCFC, mask.SLOT_REC):
        assert 0x7B1000 <= slot < 0x7B2000, f"slot 0x{slot:X} collides with .shr"


def test_caves_fit_free_slice():
    assert mask.CAVE_FLIP == 0x4949B0
    assert 0x4949B0 <= mask.CAVE_RESTORE < 0x494B37


def test_flip_hook_is_jmp_then_nops():
    raw = mask.build(_need_stock())
    ins = _disasm_at(raw, mask.FLIP_SITE, 8)
    assert ins[0].mnemonic == "jmp" and int(ins[0].op_str, 16) == mask.CAVE_FLIP
    assert ins[1].mnemonic == "nop" and ins[2].mnemonic == "nop"


def test_both_epilogues_hook_to_shared_restore_cave():
    raw = mask.build(_need_stock())
    for ep in mask.EPILOGUES:
        ins = _disasm_at(raw, ep, 6)
        assert ins[0].mnemonic == "jmp" and int(ins[0].op_str, 16) == mask.CAVE_RESTORE


def test_ring_gate_is_untouched():
    # the selection-ring faction gate at 0x47244B must NOT be patched -> white ring
    raw = mask.build(_need_stock())
    ins = _disasm_at(raw, 0x47244B, 8)
    assert ins[0].mnemonic == "cmp" and "0x1cec" in ins[0].op_str


def test_flip_cave_saves_pointer_sets_colour_and_faction():
    raw = mask.build(_need_stock())
    cave = " ".join(f"{i.mnemonic} {i.op_str}" for i in _disasm_at(raw, mask.CAVE_FLIP, 0xBE))
    assert f"movzx eax, byte ptr [esi + 0x{mask.CHOICE:x}]" in cave      # reads +0x1BC0
    assert f"mov dword ptr [0x{mask.SLOT_REC:x}], esi" in cave           # saves villager ptr
    assert f"mov byte ptr [esi + 0x{mask.ORANGE:x}], 1" in cave          # orange
    assert f"mov byte ptr [esi + 0x{mask.RED:x}], 1" in cave             # red
    assert f"mov byte ptr [esi + 0x{mask.COLORFIELD:x}], 0xc" in cave    # purple
    assert f"mov byte ptr [esi + 0x{mask.COLORFIELD:x}], 0xd" in cave    # chief
    assert f"mov byte ptr [esi + 0x{mask.FACTION:x}], 1" in cave         # transient heathen
    assert "mov ecx, dword ptr [esp + 0xbc]" in cave                     # displaced insn replayed
    assert f"jmp 0x{mask.FLIP_RETURN:x}" in cave


def test_restore_cave_uses_saved_pointer_and_replays_epilogue():
    raw = mask.build(_need_stock())
    cave = " ".join(f"{i.mnemonic} {i.op_str}" for i in _disasm_at(raw, mask.CAVE_RESTORE, 0x50))
    assert f"cmp byte ptr [0x{mask.SLOT_ACTIVE:x}], 0" in cave           # guard check
    assert f"mov eax, dword ptr [0x{mask.SLOT_REC:x}]" in cave           # villager ptr (NOT esi)
    assert f"mov byte ptr [eax + 0x{mask.FACTION:x}], 0" in cave         # faction -> believer
    assert f"mov byte ptr [eax + 0x{mask.COLORFIELD:x}], dl" in cave     # colorfield restored
    assert f"mov byte ptr [0x{mask.SLOT_ACTIVE:x}], 0" in cave           # guard cleared
    assert "add esp, 0xa8" in cave and "ret 8" in cave                   # displaced epilogue


def test_checksum_valid():
    raw = mask.build(_need_stock())
    pe = pefile.PE(data=raw, fast_load=True)
    assert pe.OPTIONAL_HEADER.CheckSum == pe.generate_checksum()
