"""Structure guard for the VV5 Heathen-mask cosmetic render, now shipped inside
the Task9 native-actions page (the appended .vv5t9 section) rather than a
standalone .text-cave overlay.

Verifies the two page routines (mask_flip / mask_restore) and the three
stock-only render-fn detours that drive them, so the picker's persistent +0x1BC0
choice is actually rendered when Change-Appearance / Origins is applied. A render
hook can only be *proven* in-game; this guards its shape and wiring.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "vv5_task9_native_actions", ROOT / "scripts/build_vv5_task9_native_actions.py"
)
assert SPEC and SPEC.loader
t9 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(t9)

STOCK_PAGE_VA = 0x7C9000
MD = Cs(CS_ARCH_X86, CS_MODE_32)


def _routine(page: bytes, rmap, name: str) -> list:
    off = t9.OFF[name]
    ln = rmap["routine_length"][name]
    return list(MD.disasm(bytes(page[off:off + ln]), STOCK_PAGE_VA + off))


def test_mask_routines_only_in_stock_page():
    stock_page, _ = t9.build_page(STOCK_PAGE_VA)
    expanded_page, exp_map = t9.build_page(0x904000)
    # stock page carries both routines; the expanded (disabled) page does not
    _, srmap = t9.build_page(STOCK_PAGE_VA)
    assert "mask_flip" in srmap["routine_length"]
    assert "mask_restore" in srmap["routine_length"]
    assert "mask_flip" not in exp_map["routine_length"]


def test_flip_routine_reads_choice_flips_faction_and_replays_displaced():
    page, rmap = t9.build_page(STOCK_PAGE_VA)
    ins = _routine(page, rmap, "mask_flip")
    text = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in ins)
    assert "movzx eax, byte ptr [esi + 0x1bc0]" in text     # persistent mask choice
    assert "mov byte ptr [esi + 0x1cec], 1" in text          # transient heathen flip
    assert "mov byte ptr [esi + 0x1ced], 1" in text          # orange
    assert "mov byte ptr [esi + 0x1cee], 1" in text          # red
    assert "mov byte ptr [esi + 0x1cfc], 0xc" in text        # purple
    assert "mov byte ptr [esi + 0x1cfc], 0xd" in text        # chief
    assert "mov dword ptr [0x7b1d10], esi" in text           # saves villager pointer
    # replays the displaced mov ecx,[esp+0xbc] and returns into the render fn
    assert ins[-2].mnemonic == "mov" and ins[-2].op_str == "ecx, dword ptr [esp + 0xbc]"
    assert ins[-1].mnemonic == "jmp" and int(ins[-1].op_str, 16) == 0x472488


def test_restore_routine_reverts_via_saved_pointer_and_runs_epilogue():
    page, rmap = t9.build_page(STOCK_PAGE_VA)
    ins = _routine(page, rmap, "mask_restore")
    text = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in ins)
    assert "cmp byte ptr [0x7b1d00], 0" in text               # guard
    assert "mov eax, dword ptr [0x7b1d10]" in text            # saved villager ptr (esi popped)
    assert "mov byte ptr [eax + 0x1cec], 0" in text           # faction back to believer
    # replays the displaced epilogue add esp,0xA8 ; ret 8
    assert ins[-2].mnemonic == "add" and ins[-2].op_str == "esp, 0xa8"
    assert ins[-1].mnemonic == "ret"


def test_scratch_is_in_data_not_shr_or_text_caves():
    # 0x7B1D00.. is free .data BSS: below the Origins .shr payload (0x7B2000) and
    # nowhere near the crowded .text cave region (0x494339..0x495000).
    for slot in (0x7B1D00, 0x7B1D04, 0x7B1D08, 0x7B1D0C, 0x7B1D10):
        assert 0x7B1000 <= slot < 0x7B2000


def test_stock_modes_declare_the_three_render_detours():
    import json
    manifest = json.loads((ROOT / "data/vv5_task9_native_actions.json").read_text(encoding="utf-8"))
    for mode in ("collection_progression", "immediate_fixed"):
        overrides = manifest["patch_mode_overrides"][mode]
        by_off = {int(p["offset"], 0): p for p in overrides}
        page_va = t9.LAYOUTS[mode]["page_va"]
        # flip detour at 0x472481 -> mask_flip
        flip = by_off[0x72481]
        assert flip["before"] == "8B8C24BC000000"
        assert flip["after"].endswith("9090")               # E9 rel32 + 2 nops
        rel = int.from_bytes(bytes.fromhex(flip["after"])[1:5], "little", signed=True)
        assert 0x400000 + 0x72481 + 5 + rel == page_va + t9.OFF["mask_flip"]
        # both epilogues -> mask_restore
        for site in (0x72B0F, 0x72B57):
            r = by_off[site]
            assert r["before"] == "81C4A80000"
            rel = int.from_bytes(bytes.fromhex(r["after"])[1:5], "little", signed=True)
            assert 0x400000 + site + 5 + rel == page_va + t9.OFF["mask_restore"]
    # expanded (disabled) modes must NOT carry the render detours
    for mode in ("experimental_expanded_256", "experimental_expanded_256_progression"):
        offs = {int(p["offset"], 0) for p in manifest["patch_mode_overrides"].get(mode, [])}
        assert 0x72481 not in offs and 0x72B0F not in offs
