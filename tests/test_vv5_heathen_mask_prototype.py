"""Static-structure guard for the VV5 Heathen-mask Step-1 prototype builder.

This verifies the *shape* of the render-hook (hook wiring, the transient
faction-flip + restore trampoline + re-entrancy guard, correct faction offset,
valid PE checksum). It does NOT — and cannot — verify the mask renders in-game;
a render hook is only proven live. See the builder module docstring.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "vv5_heathen_mask_prototype", ROOT / "scripts/build_vv5_heathen_mask_prototype.py"
)
assert SPEC and SPEC.loader
mask = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mask)

STOCK = Path(
    r"C:/Users/Owner/Downloads/Vanilla Games/Virtual Villagers - New Believers/Virtual Villagers - New Believers.exe"
)


def _disasm_at(raw: bytes, va: int, n: int):
    pe = pefile.PE(data=raw, fast_load=True)
    ib = pe.OPTIONAL_HEADER.ImageBase
    text = next(s for s in pe.sections if s.Name.rstrip(b"\x00") == b".text")
    off = text.PointerToRawData + (va - (ib + text.VirtualAddress))
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    return list(md.disasm(pe.__data__[off:off + n], va))


def _need_stock():
    if not STOCK.exists():
        import unittest

        raise unittest.SkipTest("stock VV5 exe not present in this checkout")
    return STOCK.read_bytes()


def test_faction_disp_matches_esi_bias_plus_faction():
    # esi = record + 0x48; faction byte is +0x1CEC => hook offset 0x48+0x1CEC
    assert mask.FACTION_DISP == 0x48 + 0x1CEC == 0x1D34


def test_hook_is_e9_jump_to_cave_then_nop():
    raw = mask.build(_need_stock())
    ins = _disasm_at(raw, mask.HOOK, 8)
    assert ins[0].mnemonic == "jmp" and int(ins[0].op_str, 16) == mask.CAVE
    assert ins[1].mnemonic == "nop"  # 6th displaced byte preserved as nop


def test_wrap_flips_and_restores_faction_with_guard():
    raw = mask.build(_need_stock())
    wrap = " ".join(f"{i.mnemonic} {i.op_str}" for i in _disasm_at(raw, mask.CAVE, 0x80))
    # re-entrancy guard on the active flag
    assert f"cmp byte ptr [0x{mask.ACTIVE:x}], 0" in wrap
    # sets faction=1 and marks active
    assert f"mov byte ptr [eax + 0x{mask.FACTION_DISP:x}], 1" in wrap
    assert f"mov byte ptr [0x{mask.ACTIVE:x}], 1" in wrap
    # redirects the return address to the restore stub and runs displaced sub esp
    assert f"mov dword ptr [esp], 0x{mask.RESTORE:x}" in wrap
    assert "sub esp, 0xa8" in wrap
    restore = " ".join(f"{i.mnemonic} {i.op_str}" for i in _disasm_at(raw, mask.RESTORE, 0x20))
    assert f"mov byte ptr [eax + 0x{mask.FACTION_DISP:x}], 0" in restore  # faction restored
    assert f"mov byte ptr [0x{mask.ACTIVE:x}], 0" in restore  # guard cleared


def test_checksum_valid():
    raw = mask.build(_need_stock())
    pe = pefile.PE(data=raw, fast_load=True)
    assert pe.OPTIONAL_HEADER.CheckSum == pe.generate_checksum()
