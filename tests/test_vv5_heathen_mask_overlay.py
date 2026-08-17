"""Static-structure guard for the VV5 Heathen-mask SHIPPING render overlay.

Verifies the *shape* of the per-villager render hook: hook wiring, the
per-villager ``+0x1BC0`` choice gate, the transient faction-flip + colour-field
save/restore trampoline, the re-entrancy guard, that scratch lives in ``.data``
(NOT ``.shr``, which belongs to the Origins payload), and a valid PE checksum.
It does NOT — and cannot — verify the mask renders in-game; a render hook is only
proven live. See the builder module docstring.
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

# in-repo stock copy (present in a full checkout)
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


def test_field_disps_match_esi_bias():
    assert mask.CHOICE_DISP == 0x48 + 0x1BC0 == 0x1C08
    assert mask.FACTION_DISP == 0x48 + 0x1CEC == 0x1D34
    assert mask.COLORFIELD_DISP == 0x48 + 0x1CFC == 0x1D44


def test_scratch_lives_in_data_not_shr():
    # .shr starts at 0x7B2000 and belongs entirely to the Origins payload;
    # every scratch slot must sit below it, in free .data BSS.
    for slot in (mask.SLOT_ACTIVE, mask.SLOT_REC, mask.SLOT_RET,
                 mask.SLOT_SCED, mask.SLOT_SCEE, mask.SLOT_SCFC):
        assert 0x7B1000 <= slot < 0x7B2000, f"slot 0x{slot:X} collides with .shr"


def test_hook_is_e9_jump_to_cave_then_nop():
    raw = mask.build(_need_stock())
    ins = _disasm_at(raw, mask.HOOK, 8)
    assert ins[0].mnemonic == "jmp" and int(ins[0].op_str, 16) == mask.CAVE
    assert ins[1].mnemonic == "nop"


def test_wrap_gates_on_choice_and_flips_with_guard():
    raw = mask.build(_need_stock())
    wrap = " ".join(f"{i.mnemonic} {i.op_str}" for i in _disasm_at(raw, mask.CAVE, 0xE6))
    assert f"cmp byte ptr [0x{mask.SLOT_ACTIVE:x}], 0" in wrap          # re-entrancy guard
    assert f"movzx edx, byte ptr [eax + 0x{mask.CHOICE_DISP:x}]" in wrap  # reads +0x1BC0
    assert f"mov byte ptr [eax + 0x{mask.FACTION_DISP:x}], 1" in wrap   # transient heathen
    assert f"mov byte ptr [eax + 0x{mask.ORANGE_DISP:x}], 1" in wrap    # orange colour
    assert f"mov byte ptr [eax + 0x{mask.RED_DISP:x}], 1" in wrap       # red colour
    assert f"mov byte ptr [eax + 0x{mask.COLORFIELD_DISP:x}], 0xc" in wrap  # purple
    assert f"mov byte ptr [eax + 0x{mask.COLORFIELD_DISP:x}], 0xd" in wrap  # chief
    assert f"mov dword ptr [esp], 0x{mask.RESTORE:x}" in wrap           # return redirect
    assert "sub esp, 0xa8" in wrap                                      # displaced insn


def test_restore_reverts_all_fields_and_clears_guard():
    raw = mask.build(_need_stock())
    restore = " ".join(f"{i.mnemonic} {i.op_str}" for i in _disasm_at(raw, mask.RESTORE, 0x40))
    assert f"mov byte ptr [eax + 0x{mask.FACTION_DISP:x}], 0" in restore   # faction back to believer
    assert f"mov byte ptr [eax + 0x{mask.ORANGE_DISP:x}], dl" in restore   # orange restored
    assert f"mov byte ptr [eax + 0x{mask.RED_DISP:x}], dl" in restore      # red restored
    assert f"mov byte ptr [eax + 0x{mask.COLORFIELD_DISP:x}], dl" in restore  # colorfield restored
    assert f"mov byte ptr [0x{mask.SLOT_ACTIVE:x}], 0" in restore          # guard cleared


def test_checksum_valid():
    raw = mask.build(_need_stock())
    pe = pefile.PE(data=raw, fast_load=True)
    assert pe.OPTIONAL_HEADER.CheckSum == pe.generate_checksum()
