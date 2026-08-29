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
VV5_SOURCE = (ROOT / "native/vv5_task9_origins/vv5_task9_origins.c").read_text(encoding="utf-8")

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
    # choice now comes from the side-table via mask_get, never from a record byte
    assert f"call 0x{STOCK_PAGE_VA + t9.OFF['mask_get']:x}" in text
    assert "0x1bc0" not in text                              # never touches the villager record
    assert "mov byte ptr [esi + 0x1cec], 1" in text          # transient heathen flip
    assert "mov byte ptr [esi + 0x1ced], 1" in text          # orange
    assert "mov byte ptr [esi + 0x1cee], 1" in text          # red
    assert "mov byte ptr [esi + 0x1cfc], 0xc" in text        # purple
    assert "mov byte ptr [esi + 0x1cfc], 0xd" in text        # chief
    assert "mov dword ptr [0x7b1d10], esi" in text           # saves villager pointer
    # replays the displaced mov ecx,[esp+0xbc] and returns into the render fn
    assert ins[-2].mnemonic == "mov" and ins[-2].op_str == "ecx, dword ptr [esp + 0xbc]"
    assert ins[-1].mnemonic == "jmp" and int(ins[-1].op_str, 16) == 0x472488


def test_bighead_routine_replays_head_then_blits_mask_atlas():
    page, rmap = t9.build_page(STOCK_PAGE_VA)
    ins = _routine(page, rmap, "bighead_mask")
    text = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in ins)
    # replays the real head draw AND blits the mask via the same draw thunk
    assert text.count("call 0x409ca0") == 2
    # choice comes from the side-table via mask_get, never a villager record field
    assert f"call 0x{STOCK_PAGE_VA + t9.OFF['mask_get']:x}" in text
    assert "0x1bc0" not in text
    # fetches the DEDICATED bighead mask atlas by its registered sprite id 0x155;
    # both the atlas getter and the draw thunk are thiscall thunks -> ecx primed
    assert "call 0x44fbb0" in text and "mov ecx, eax" in text  # atlas mgr this
    assert "push 0x155" in text and "call 0x44fa30" in text
    assert "mov ecx, dword ptr [esi + 0x2f2c]" in text         # drawlist this for the mask draw
    # scale boost + a base vertical lift (values tunable)
    assert "imul ecx" in text
    assert "sub eax," in text
    # bigheads_masks.png has 3 facing columns; the mask atlas COLUMN is selected
    # from the portrait head's OWN facing index (record+0x2F3C mod 3) so the mask
    # tracks the head regardless of age (the old frame&7 read broke for aged heads
    # whose frame carries an age offset).
    assert "mov eax, dword ptr [esi + 0x2f3c]" in text          # read the portrait facing field
    assert "idiv" in text                                       # mod 3 -> facing index (0/1/2)
    assert "movzx ecx, byte ptr [edx" in text                  # facing -> column table read
    # transient scratch stays in proven-free .data BSS, never a record write
    assert "mov dword ptr [0x7b1d14], eax" in text            # saved portrait X
    # cleans the caller's seven stdcall args exactly as the stock call would
    assert ins[-1].mnemonic == "ret" and ins[-1].op_str in ("0x1c", "0x1C")


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


def test_scratch_and_table_are_in_proven_free_data_bss():
    # Scratch (0x7B1D00..) and the nibble-packed mask side-table (0x7B1D20..0x7B1D6B)
    # live in free .data BSS: clear of the stock globals that begin at 0x7B1D80 and
    # inside .data's virtual end 0x7B1DA4.
    for slot in (0x7B1D00, 0x7B1D04, 0x7B1D08, 0x7B1D0C, 0x7B1D10):
        assert 0x7B1D00 <= slot < 0x7B1D20              # scratch, before the table
    table_lo, table_hi = t9.MASK_TABLE, t9.MASK_TABLE + (t9.BOUND + 1) // 2
    assert 0x7B1D20 <= table_lo and table_hi <= 0x7B1D80   # clear of stock globals @0x7B1D80
    assert table_hi <= 0x7B1DA4                            # inside .data virtual end


def test_mask_get_set_use_indexed_side_table_not_the_record():
    page, rmap = t9.build_page(STOCK_PAGE_VA)
    for name in ("mask_get", "mask_set"):
        text = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in _routine(page, rmap, name))
        assert "sub eax, 0x554190" in text                 # record -> offset from array base
        assert "div ecx" in text and "0x2f44" in text      # / record stride = index
        assert hex(t9.MASK_TABLE)[2:] in text.replace("0x", "")  # nibble in the side-table
        assert "0x1bc0" not in text                        # never the villager record
    # mask_set must actually store a byte into the table; mask_get must not store
    set_text = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in _routine(page, rmap, "mask_set"))
    assert f"mov byte ptr [eax + 0x{t9.MASK_TABLE:x}], dl" in set_text


def test_no_routine_writes_the_villager_record_mask_byte():
    # Safety guarantee: nothing in the page stores into [reg+0x1BC0] (the live
    # 24-byte string field the shipped build used to corrupt).
    import struct
    page, _ = t9.build_page(STOCK_PAGE_VA)
    assert struct.pack("<i", 0x1BC0) not in bytes(page)


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
        # Details-portrait head-draw detour at 0x466E05 -> bighead_mask
        bighead = by_off[0x66E05]
        assert bighead["before"] == "E8962EFAFF"             # call 0x409CA0
        assert bighead["after"].startswith("E8")             # call rel32 (no nops)
        rel = int.from_bytes(bytes.fromhex(bighead["after"])[1:5], "little", signed=True)
        assert 0x400000 + 0x66E05 + 5 + rel == page_va + t9.OFF["bighead_mask"]
    # expanded (disabled) modes must NOT carry the render detours
    for mode in ("experimental_expanded_256", "experimental_expanded_256_progression"):
        offs = {int(p["offset"], 0) for p in manifest["patch_mode_overrides"].get(mode, [])}
        assert 0x72481 not in offs and 0x72B0F not in offs and 0x66E05 not in offs
        assert 0x3600 not in offs                              # no slot_capture detour either


def test_slot_capture_routine_records_current_save_slot():
    page, rmap = t9.build_page(STOCK_PAGE_VA)
    ins = _routine(page, rmap, "slot_capture")
    text = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in ins)
    # reads the slot arg (a2 at [esp+4], return addr at [esp]) on buildSavePath entry
    assert "mov eax, dword ptr [esp + 4]" in text
    # stores it only when non-zero, so the meta file's slot 0 never clobbers a village slot
    assert "test eax, eax" in text
    assert f"mov dword ptr [0x{t9.SLOT_SCRATCH:x}], eax" in text
    # replays the displaced prologue and returns just past it
    assert "sub esp, 0x104" in text
    assert ins[-1].mnemonic == "jmp" and int(ins[-1].op_str, 16) == 0x403606
    # the capture scratch is the last free .data BSS dword, before the stock globals
    assert t9.SLOT_SCRATCH == 0x7B1D7C
    assert t9.BH_SCOL < t9.SLOT_SCRATCH < 0x7B1D80


def test_birth_clear_zeroes_newborn_mask_and_replays_prologue():
    page, rmap = t9.build_page(STOCK_PAGE_VA)
    ins = _routine(page, rmap, "mask_birth_clear")
    text = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in ins)
    # clears the newborn's nibble via mask_set(esi=record, bl=0)
    assert "mov esi, ecx" in text                            # esi = newborn record
    assert "xor ebx, ebx" in text                            # bl = 0 (clear)
    assert f"call 0x{STOCK_PAGE_VA + t9.OFF['mask_set']:x}" in text
    # preserves ecx (this) across the mask_set call
    assert ins[0].mnemonic == "push" and ins[0].op_str == "ecx"
    # replays the displaced 6-byte prologue and returns just past it
    assert ins[-1].mnemonic == "jmp" and int(ins[-1].op_str, 16) == 0x4687F6


def test_stock_modes_declare_the_birth_clear_detour():
    import json
    manifest = json.loads((ROOT / "data/vv5_task9_native_actions.json").read_text(encoding="utf-8"))
    for mode in ("collection_progression", "immediate_fixed"):
        by_off = {int(p["offset"], 0): p for p in manifest["patch_mode_overrides"][mode]}
        page_va = t9.LAYOUTS[mode]["page_va"]
        cap = by_off[0x687F0]
        assert cap["before"] == "53568BF133DB"               # push ebx;push esi;mov esi,ecx;xor ebx,ebx
        assert cap["after"].startswith("E9") and cap["after"].endswith("90")
        assert len(bytes.fromhex(cap["after"])) == 6
        rel = int.from_bytes(bytes.fromhex(cap["after"])[1:5], "little", signed=True)
        assert 0x400000 + 0x687F0 + 5 + rel == page_va + t9.OFF["mask_birth_clear"]
    # expanded (disabled) modes must NOT carry the birth-clear detour
    for mode in ("experimental_expanded_256", "experimental_expanded_256_progression"):
        offs = {int(p["offset"], 0) for p in manifest["patch_mode_overrides"].get(mode, [])}
        assert 0x687F0 not in offs


def test_stock_modes_declare_the_slot_capture_detour():
    import json
    manifest = json.loads((ROOT / "data/vv5_task9_native_actions.json").read_text(encoding="utf-8"))
    for mode in ("collection_progression", "immediate_fixed"):
        by_off = {int(p["offset"], 0): p for p in manifest["patch_mode_overrides"][mode]}
        page_va = t9.LAYOUTS[mode]["page_va"]
        cap = by_off[0x3600]
        assert cap["before"] == "81EC04010000"               # sub esp, 0x104 (6 bytes)
        assert cap["after"].startswith("E9")                 # jmp rel32 ...
        assert cap["after"].endswith("90")                   # ... + 1 nop = 6 bytes
        assert len(bytes.fromhex(cap["after"])) == 6         # exactly overwrites the stolen 6 bytes
        rel = int.from_bytes(bytes.fromhex(cap["after"])[1:5], "little", signed=True)
        assert 0x400000 + 0x3600 + 5 + rel == page_va + t9.OFF["slot_capture"]


def test_mask_sidecar_path_is_fail_closed_and_budgeted():
    # Slot zero is the pre-load legacy namespace; numbered saves are exactly
    # 1..5.  The complete longest output, including NUL, must fit before the
    # first unbounded wsprintfA call.
    assert "if (slot < 0 || slot > 5)" in VV5_SOURCE
    assert "n == 0 || n >= MAX_PATH" in VV5_SOURCE
    assert "sizeof(\"\\\\vvfp_masks_5.dat\")" in VV5_SOURCE
    assert "docs_len + 5 + base_len" in VV5_SOURCE
