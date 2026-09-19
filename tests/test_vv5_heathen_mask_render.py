"""Structure guard for the VV5 Heathen-mask cosmetic render, shipped inside the
Task9 native-actions page (the appended .vv5t9 section).

The mechanism is a FLIP, not an overlay. For the duration of one villager's
head draw, mask_flip makes a masked Believer look like a Heathen of the chosen
colour, and mask_restore puts the record back on the way out of the render
function. The stock renderer then selects the mask sprite itself.

That is not a stylistic choice. The stock heathen branch at 0x472732 does not
accept a mask number: it PICKS its sprite argument from one of three caller
stack slots according to the villager's own colour flags, so nothing supplied
from outside can substitute for it. An overlay that called the heathen head
draw with a forwarded argument tuple shipped in three releases and rendered no
village mask in any of them; diffing against v1.34.38, which the owner
confirmed working, showed that build leaves the believer draw at 0x47279C
completely unpatched.

So the guards here are:

  * the believer head draw at 0x47279C is NOT detoured, in any mode;
  * mask_flip only ever touches a BELIEVER, and refuses to nest, so no
    player-observable faction ever changes;
  * mask_restore RESTORES THE SAVED COLOUR BYTES. v1.34.38 saved +0x1CED and
    +0x1CEE into scratch and then wrote literal zero back, silently clearing an
    orange or red villager's colour. That is fixed here and guarded below;
  * both epilogues of the render function are detoured, so the flip window
    closes on every path out.

tests/test_vv5_mask_overlay_argument_order.py was deleted with the overlay. Its
assertions were all about that routine's argument tuple and its frame -- the
startup crash it guarded (#371) was caused by the overlay wrapping the call it
replaced, and the flip replaces no call at all. There is no frame to get wrong.
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
    _, exp_map = t9.build_page(0x904000)
    _, srmap = t9.build_page(STOCK_PAGE_VA)
    assert "mask_flip" in srmap["routine_length"]
    assert "mask_restore" in srmap["routine_length"]
    # the expanded (disabled) page carries neither
    assert "mask_flip" not in exp_map["routine_length"]
    assert "mask_restore" not in exp_map["routine_length"]
    # and the overlay that never rendered is gone for good
    assert "mask_overlay" not in srmap["routine_length"]


def test_flip_only_touches_a_believer_and_refuses_to_nest():
    """The flip may only ever be armed on a Believer, and only one at a time.

    Both conditions are what keep the faction change invisible to the player: a
    real Heathen is never touched, and a second villager cannot be armed while
    the first is still flipped and waiting to be restored.
    """
    page, rmap = t9.build_page(STOCK_PAGE_VA)
    ins = _routine(page, rmap, "mask_flip")
    text = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in ins)
    # the shared exit label: pop edx / pop eax / mov ecx,[esp+0xbc] / jmp
    done = ins[-4].address
    assert ins[-4].mnemonic == "pop" and ins[-4].op_str == "edx"

    # choice comes from the side-table via mask_get, never a record byte
    assert f"call 0x{STOCK_PAGE_VA + t9.OFF['mask_get']:x}" in text
    assert "0x1bc0" not in text

    # BELIEVERS ONLY: a non-zero faction byte must branch to the exit
    fac = [i for i in ins if i.mnemonic == "cmp" and i.op_str == "byte ptr [esi + 0x1cec], 0"]
    assert fac, "flip must test the faction byte"
    guard = ins[ins.index(fac[0]) + 1]
    assert guard.mnemonic == "jne" and int(guard.op_str, 16) == done, (
        "a non-Believer must skip the whole flip"
    )

    # NO NESTING: an already-armed flip must also branch to the exit
    armed = [i for i in ins if i.mnemonic == "cmp" and i.op_str == "byte ptr [0x7b1d00], 0"]
    assert armed, "flip must test the armed guard"
    guard = ins[ins.index(armed[0]) + 1]
    assert guard.mnemonic == "jne" and int(guard.op_str, 16) == done

    # the three colour bytes are SAVED before they are overwritten
    for scratch, field in ((0x7B1D04, 0x1CED), (0x7B1D08, 0x1CEE), (0x7B1D0C, 0x1CFC)):
        assert f"movzx edx, byte ptr [esi + 0x{field:x}]" in text
        assert f"mov dword ptr [0x{scratch:x}], edx" in text
    # and the villager itself is remembered, because esi is gone by the epilogue
    assert "mov dword ptr [0x7b1d10], esi" in text

    # every masked path ends by setting the faction byte exactly once
    assert text.count("mov byte ptr [esi + 0x1cec], 1") == 1

    # replays the displaced mov ecx,[esp+0xbc] and returns into the render fn
    assert ins[-2].mnemonic == "mov" and ins[-2].op_str == "ecx, dword ptr [esp + 0xbc]"
    assert ins[-1].mnemonic == "jmp" and int(ins[-1].op_str, 16) == 0x472488


def test_flip_maps_each_mask_colour_to_exactly_one_field():
    """1 blue / 2 orange / 3 red / 4 purple / 5 chief, and nothing else."""
    page, rmap = t9.build_page(STOCK_PAGE_VA)
    ins = _routine(page, rmap, "mask_flip")
    text = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in ins)
    # out-of-range choices are rejected before anything is written
    assert "cmp eax, 5" in text and any(i.mnemonic == "ja" for i in ins)
    # all three colour fields are cleared first, so blue leaves all three at 0
    for field in (0x1CED, 0x1CEE, 0x1CFC):
        assert f"mov byte ptr [esi + 0x{field:x}], 0" in text
    # then exactly one is set per colour
    assert "mov byte ptr [esi + 0x1ced], 1" in text      # 2 orange
    assert "mov byte ptr [esi + 0x1cee], 1" in text      # 3 red
    assert "mov byte ptr [esi + 0x1cfc], 0xc" in text    # 4 purple
    assert "mov byte ptr [esi + 0x1cfc], 0xd" in text    # 5 chief


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


def test_purple_details_mask_is_exactly_five_pixels_lower_than_prior_registration():
    # Purple is row 3. Its Details-only signed Y nudge moved from -3 (up 3)
    # to +2 (down 2): exactly +5px. The village renderer never reads this table.
    assert t9.BH_ROWDY_TABLE == [0, 2, 0, 2, 0]
    page, _ = t9.build_page(STOCK_PAGE_VA)
    start = t9.OFF["bighead_offsets"] + 11
    assert list(page[start:start + 5]) == [0, 2, 0, 2, 0]


def test_restore_writes_back_the_saved_colours_not_zero():
    """The v1.34.38 latent bug must not come back with the mechanism.

    That build saved +0x1CED and +0x1CEE into 0x7B1D04 / 0x7B1D08 and then wrote
    literal zero to both, restoring only +0x1CFC. A mask on an orange or red
    villager therefore cleared that villager's colour permanently. Each of the
    three fields must be restored from its own scratch dword.
    """
    page, rmap = t9.build_page(STOCK_PAGE_VA)
    ins = _routine(page, rmap, "mask_restore")
    text = " ; ".join(f"{i.mnemonic} {i.op_str}" for i in ins)

    # unarmed villagers are a no-op: the guard jumps straight to the epilogue
    assert ins[0].mnemonic == "cmp" and ins[0].op_str == "byte ptr [0x7b1d00], 0"
    assert ins[1].mnemonic == "je"

    # the flipped villager is reached through the saved pointer, not esi
    assert "mov eax, dword ptr [0x7b1d10]" in text
    # faction goes back to Believer
    assert "mov byte ptr [eax + 0x1cec], 0" in text

    # EACH colour field is loaded from ITS OWN scratch slot and written back.
    for scratch, field in ((0x7B1D04, 0x1CED), (0x7B1D08, 0x1CEE), (0x7B1D0C, 0x1CFC)):
        load = f"mov edx, dword ptr [0x{scratch:x}]"
        store = f"mov byte ptr [eax + 0x{field:x}], dl"
        assert load in text, f"+0x{field:X} is not reloaded from 0x{scratch:X}"
        assert store in text, f"+0x{field:X} is not written back from the load"
        assert text.index(load) < text.index(store)
        # and it must NOT be the literal-zero store the working build shipped
        assert f"mov byte ptr [eax + 0x{field:x}], 0" not in text, (
            f"+0x{field:X} restored as literal zero, the v1.34.38 defect"
        )

    # the guard is cleared, so the next villager can arm
    assert "mov byte ptr [0x7b1d00], 0" in text
    # and the displaced epilogue is replayed exactly
    assert ins[-2].mnemonic == "add" and ins[-2].op_str == "esp, 0xa8"
    assert ins[-1].mnemonic == "ret" and ins[-1].op_str == "8"


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


def test_stock_modes_declare_the_render_detours():
    import json
    manifest = json.loads((ROOT / "data/vv5_task9_native_actions.json").read_text(encoding="utf-8"))
    for mode in ("collection_progression", "immediate_fixed"):
        overrides = manifest["patch_mode_overrides"][mode]
        by_off = {int(p["offset"], 0): p for p in overrides}
        page_va = t9.LAYOUTS[mode]["page_va"]
        # arm detour at 0x472481 -> mask_flip
        arm = by_off[0x72481]
        assert arm["before"] == "8B8C24BC000000"
        assert arm["after"].endswith("9090")                # E9 rel32 + 2 nops
        rel = int.from_bytes(bytes.fromhex(arm["after"])[1:5], "little", signed=True)
        assert 0x400000 + 0x72481 + 5 + rel == page_va + t9.OFF["mask_flip"]

        # THE BELIEVER HEAD DRAW IS NOT TOUCHED. Detouring it is what three
        # releases did while rendering no village mask at all; v1.34.38, the
        # build the owner confirmed working, leaves these five bytes stock.
        assert 0x7279C not in by_off, "0x47279C must stay unpatched"

        # BOTH epilogues restore, so the flip window closes on every path out
        for off in (0x72B0F, 0x72B57):
            ep = by_off[off]
            assert ep["before"] == "81C4A8000000"            # add esp, 0xA8
            assert ep["after"].startswith("E9") and ep["after"].endswith("90")
            assert len(bytes.fromhex(ep["after"])) == 6      # exactly the stolen bytes
            rel = int.from_bytes(bytes.fromhex(ep["after"])[1:5], "little", signed=True)
            assert 0x400000 + off + 5 + rel == page_va + t9.OFF["mask_restore"]

        # Details-portrait head-draw detour at 0x466E05 -> bighead_mask
        bighead = by_off[0x66E05]
        assert bighead["before"] == "E8962EFAFF"             # call 0x409CA0
        assert bighead["after"].startswith("E8")             # call rel32 (no nops)
        rel = int.from_bytes(bytes.fromhex(bighead["after"])[1:5], "little", signed=True)
        assert 0x400000 + 0x66E05 + 5 + rel == page_va + t9.OFF["bighead_mask"]
    # expanded (disabled) modes must NOT carry the render detours
    for mode in ("experimental_expanded_256", "experimental_expanded_256_progression"):
        offs = {int(p["offset"], 0) for p in manifest["patch_mode_overrides"].get(mode, [])}
        assert 0x72481 not in offs and 0x7279C not in offs and 0x66E05 not in offs
        assert 0x72B0F not in offs and 0x72B57 not in offs
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
