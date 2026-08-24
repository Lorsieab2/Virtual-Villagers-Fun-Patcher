"""Build the active VV5 Task9 owner-safe native action extension.

This generator treats ``data/vv5_origins_feature.json`` as an immutable input.
It clones its exact patch/relocation ledger, replaces only the active menu entry
paths and guarded constructor geometry, and appends one generated RX section.
"""

from __future__ import annotations

import hashlib
import json
import struct
import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research/stock-executables/Virtual Villagers - New Believers.exe"
ACTIVE = ROOT / "data/vv5_origins_feature.json"
COMPANION = ROOT / "data/candidates/VVFP VV5 Task9 Origins Icons.dll"
OUT = ROOT / "data/vv5_task9_native_actions.json"
MAP_OUT = ROOT / "data/candidates/vv5_task9_native_actions_map.json"
SOURCE_PATHS = {
    "task9_builder": "scripts/build_vv5_task9_native_actions.py",
    "companion_c": "native/vv5_task9_origins/vv5_task9_origins.c",
    "companion_def": "native/vv5_task9_origins/vv5_task9_origins.def",
    "companion_rc": "native/vv5_task9_origins/vv5_task9_origins.rc",
    "companion_builder": "scripts/build_vv5_task9_origins_dll.ps1",
    "individual_reference": "src/vv5_individual_transactions.py",
    "full_heal_reference": "src/vv5_full_heal.py",
    "active_base": "data/vv5_origins_feature.json",
    "task8_overlay": "data/candidates/vv5_post_prototype_overlay.json",
    "atomic_generator": "src/expanded_atomic_writer.py",
    "atomic_contract": "data/expanded_atomic_writer_integration.json",
}
ATOMIC_CORE_COMMIT = "c4e5fe76d1de258d5d4baeac77cbea842b206cd7"
ATOMIC_SOURCE_TEXT_SHA256 = {
    "atomic_generator": "0424B3B56CB4093176A8B429472FCDF04043CBFC22424EBBDE37058EA1A8F72E",
    "atomic_contract": "1B7068D0679CA896706AA201D27726AF612FD167C0406C5D509774E40728F6A6",
}

STOCK_SHA256 = "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D"
ACTIVE_SHA256 = "98DF5E199449F8818C06ACA56131215E509C0236895AC63DF21C9194CC814A57"
ACTIVE_SOURCE_TEXT_SHA256 = "E08F9284B21B4855CCF94663C7C7054898DBFE73BB14DC06311B498A3B6779B3"
C342_COUNT = 66
C342_ROWS_SHA256 = "7A95D8CCC6477777E9A3AA4C3EFEB30D8AF0D50434C910C1ADE9A645C7DBDDCA"
TASK8_SOURCE_TEXT_SHA256 = "090ED9CA074F02F9321B2F8E0C470FD0AF18B235231DA94B6D38293360BC9510"

sys.path.insert(0, str(ROOT / ".tools/keystone-runtime"))
sys.path.insert(1, str(ROOT / ".tools/keystone"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402


IMAGE_BASE = 0x400000
PAYLOAD_OFFSET = 0xDB000
PAYLOAD_VA = 0x7B2000
EXPANDED_PAYLOAD_VA = 0x8EB000
PAGE_SIZE = 0x8000
STRIDE = 0x2F44
BOUND = 150
# Heathen-mask side-table: the per-villager mask choice (0-5) is stored OUTSIDE
# the villager record -- record byte +0x1BC0 turned out to be a live 24-byte
# string field (stock cmp/strncpy at 0x44B7E3/0x4686B8), so writing it was
# unsafe. It lives nibble-packed (4 bits x 150 villagers = 75 bytes) in
# proven-free .data BSS at 0x7B1D20..0x7B1D6B -- clear of the 0x7B1D00 scratch
# and of the stock globals that begin at 0x7B1D80, inside .data's virtual end
# 0x7B1DA4. Keyed by villager record index = (record - 0x554190) / 0x2F44.
MASK_TABLE = 0x7B1D20
# One-shot "the side-table has been loaded from the sidecar this session" flag,
# in the same proven-free R/W .data BSS (0x7B1D6C, just past the 75-byte table,
# before stock globals at 0x7B1D80). Zero at launch (BSS); the render hook loads
# the sidecar into MASK_TABLE on the first village frame, then sets this. All
# runtime-written state stays in non-exec .data (W^X-clean; code stays R+X).
MASK_LOADED = 0x7B1D6C
# Bighead (Details-screen villager portrait) mask render scratch: five R/W .data
# BSS dwords in the same proven-free window as the flip scratch -- 0x7B1D14..0x1F
# (just past the flip scratch, before MASK_TABLE) and 0x7B1D70..0x77 (past the
# loaded flag, before the stock globals at 0x7B1D80). BSS (zero at launch),
# non-exec, so it stays W^X-clean and never contends with .text caves.
BH_SX = 0x7B1D14
BH_SY = 0x7B1D18
BH_SF = 0x7B1D1C
BH_SS = 0x7B1D70
BH_SROW = 0x7B1D74
BH_SCOL = 0x7B1D78   # resolved mask atlas column (facing) for the draw
# Bighead mask atlas sprite id. A DEDICATED front-facing bighead mask atlas
# (bigheads_masks.png, 1 col x 5 mask rows, bottom-aligned) is registered at the
# free sprite-table slot 0x155 (record patched into .data at 0x4D2FA8) so the
# Details portrait uses purpose-built art rather than the tiny 8-way village
# atlas. sub_44FA30(0x155) -> sub_44F870 lazily loads+caches bigheads_masks.png.
MASK_HANDLE = 0x155
BIGHEAD_ATLAS_ID = 0x155
BIGHEAD_ATLAS_REC_VA = 0x4CEFB8 + BIGHEAD_ATLAS_ID * 0x30   # 0x4D2FA8 (free slot)
BIGHEAD_ATLAS_COLS = 3
BIGHEAD_ATLAS_ROWS = 5
# Portrait-mask tuning (all emitted as patchable immediates so they can be
# dialed in live). BH_LIFT = pre-scale vertical lift (imm8, sub edx,LIFT).
# BH_SCALE_MUL = integer multiple of the head's draw scale (the Details head is
# drawn large, so the village-scale mask atlas needs boosting). BH_FRAME = fixed
# mask atlas column: the Details portrait is front-facing and the 8-col heathen
# atlas front frame is col 5 (the head atlas is 16-col, so its frame index maps
# to the wrong mask column — use the known front column instead).
BH_SCALE_MUL = 3
BH_SCALE_SHIFT = 1   # scale = headScale * MUL >> SHIFT  (3>>1 = x1.5)
BH_XOFF = 0x00       # base horizontal nudge (mask X = headX + XOFF; signed imm8)
BH_LIFT = 0x2D       # base vertical lift  (mask Y = headY - LIFT)
# bigheads_masks.png is 3 columns = 3 head FACINGS (owner: col0=RIGHT turn,
# col1=front, col2=LEFT turn), each pre-aligned to its facing's face-within-the-
# sprite. So follow-the-face = pick the atlas COLUMN from the head's facing frame
# (the mask then rotates AND tracks for free, VV2's atlas-baked method). The
# Details idle head uses facings 3(turn)/4(front)/5(turn); map each frame&7 to a
# column via this table (8 signed-byte entries, in the R+X page, live-tunable so
# the left/right swap can be corrected without a rebuild).
BH_COL_TABLE = [1, 1, 1, 0, 1, 2, 1, 1]   # head frame&7 -> mask column (front=1); frame3->col0, frame5->col2 (swapped)
TASK9_EXPANDED_HOOK = {
    "offset": "0x415F0",
    "before": "E90B0A3700909090",
    "after": "E90B9A4A00909090",
    "purpose": "post-relocation: bind the Task9 Tech-screen command-13 hook to relocated Expanded .shr without changing C342",
}
TASK9_CROSS_SECTION_HOOKS = {
    "0x1890F": {"stock_target": "0x7B2180", "expanded_target": "0x8EB180", "expanded_policy": "frozen_c342"},
    "0x1EB6F": {"stock_target": "0x7B2B00", "expanded_target": "0x8EBB00", "expanded_policy": "native_override_preserved"},
    "0x237B0": {"stock_target": "0x7B2A00", "expanded_target": "0x8EBA00", "expanded_policy": "native_override_preserved"},
    "0x40A24": {"stock_target": "0x7B2040", "expanded_target": "0x8EB040", "expanded_policy": "frozen_c342"},
    "0x415F0": {"stock_target": "0x7B2000", "expanded_target": "0x8EB000", "expanded_policy": "task9_post_relocation"},
    "0x4AF12": {"stock_target": "0x7B2100", "expanded_target": "0x8EB100", "expanded_policy": "frozen_c342"},
    "0x4BC20": {"stock_target": "0x7B20C0", "expanded_target": "0x8EB0C0", "expanded_policy": "frozen_c342"},
}

LAYOUTS = {
    "collection_progression": {
        "append_offset": 0xF2000,
        "page_rva": 0x3C9000,
        "page_va": 0x7C9000,
        "section_count_offset": 0xFE,
        "section_count_before": 5,
        "size_of_image_offset": 0x148,
        "size_of_image_before": 0x3C9000,
        "section_header_offset": 0x2B8,
    },
    "immediate_fixed": {
        "append_offset": 0xF2000,
        "page_rva": 0x3C9000,
        "page_va": 0x7C9000,
        "section_count_offset": 0xFE,
        "section_count_before": 5,
        "size_of_image_offset": 0x148,
        "size_of_image_before": 0x3C9000,
        "section_header_offset": 0x2B8,
    },
    "experimental_expanded_256": {
        "append_offset": 0xF4000,
        "page_rva": 0x504000,
        "page_va": 0x904000,
        "section_count_offset": 0xFE,
        "section_count_before": 7,
        "size_of_image_offset": 0x148,
        "size_of_image_before": 0x504000,
        "section_header_offset": 0x308,
    },
    "experimental_expanded_256_progression": {
        "append_offset": 0xF4000,
        "page_rva": 0x504000,
        "page_va": 0x904000,
        "section_count_offset": 0xFE,
        "section_count_before": 7,
        "size_of_image_offset": 0x148,
        "size_of_image_before": 0x504000,
        "section_header_offset": 0x308,
    },
}

OFF = {
    "constructor_resource": 0x40,
    "tech_entry": 0x100,
    "detail_entry": 0x120,
    "modal_common": 0x140,
    "resolve_current": 0x580,
    "resolve_index": 0x5C0,
    "eligible": 0x620,
    "show_menu": 0x670,
    "confirm": 0x6D0,
    "status": 0x740,
    "resolve_manager": 0x7A0,
    "tech_menu": 0x840,
    "detail_menu": 0xB40,
    "age": 0xD40,
    "time_warp": 0x1040,
    "mastery": 0x1540,
    "running": 0x2240,
    "heal": 0x3400,
    "island": 0x3C00,
    "barrel": 0x3F00,
    "appearance": 0x4300,
    "complete_collections": 0x4600,
    "reset_collections": 0x4900,
    "running_all": 0x4C00,
    "mastery_all": 0x5200,
    "age18_all": 0x5800,
    "barrel_close_arm": 0x5E00,
    "division_parenting": 0x6000,
    "division_no_parenting": 0x6200,
    "apply_division": 0x6400,
    "mask_flip": 0x6800,
    "mask_restore": 0x6A00,
    "mask_get": 0x6C00,
    "mask_set": 0x6C80,
    "mask_load_once": 0x6D00,
    "bighead_mask": 0x6D80,
    "bighead_offsets": 0x6F00,
    "strings": 0x7000,
}

SIZES = {
    "constructor_resource": 0x20,
    "tech_entry": 0x20,
    "detail_entry": 0x20,
    "modal_common": 0x440,
    "resolve_current": 0x40,
    "resolve_index": 0x60,
    "eligible": 0x40,
    "show_menu": 0x60,
    "confirm": 0x70,
    "status": 0x50,
    "resolve_manager": 0xA0,
    "tech_menu": 0x300,
    "detail_menu": 0x200,
    "age": 0x300,
    "time_warp": 0x500,
    "mastery": 0xD00,
    "running": 0x11C0,
    "heal": 0x800,
    "island": 0x300,
    "barrel": 0x340,
    "appearance": 0x300,
    "complete_collections": 0x300,
    "reset_collections": 0x300,
    "running_all": 0x600,
    "mastery_all": 0x600,
    "age18_all": 0x600,
    "barrel_close_arm": 0x80,
    "division_parenting": 0x200,
    "division_no_parenting": 0x200,
    "apply_division": 0x80,
    "mask_flip": 0x200,
    "mask_restore": 0x200,
    "mask_get": 0x80,
    "mask_set": 0x80,
    "mask_load_once": 0x80,
    "bighead_mask": 0x100,
    "bighead_offsets": 0x10,
}


def asm(source: str, address: int) -> bytes:
    encoded, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoded)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def canonical_sha(value: object) -> str:
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii"))


def source_text_sha(data: bytes) -> str:
    text = data.decode("utf-8-sig").replace("\r\n", "\n")
    if not text.endswith("\n"):
        text += "\n"
    return sha(text.encode("utf-8"))


def source_bindings() -> dict[str, dict[str, str]]:
    bindings = {
        name: {
            "path": path,
            "source_text_sha256": source_text_sha((ROOT / path).read_bytes()),
        }
        for name, path in SOURCE_PATHS.items()
    }
    for name, expected in ATOMIC_SOURCE_TEXT_SHA256.items():
        if bindings[name]["source_text_sha256"] != expected:
            raise RuntimeError(f"pinned {name} source drift")
    return bindings


def section_header(rva: int, raw: int) -> bytes:
    return (
        b".vv5t9\0\0"
        + PAGE_SIZE.to_bytes(4, "little")
        + rva.to_bytes(4, "little")
        + PAGE_SIZE.to_bytes(4, "little")
        + raw.to_bytes(4, "little")
        + b"\0" * 12
        + (0x60000020).to_bytes(4, "little")
    )


def build_strings(page: bytearray, page_va: int) -> dict[str, int]:
    values = (
        ("dll", b"VVFP Origins Icons.dll\0"),
        ("begin", b"BeginOriginsOwner\0"),
        ("end", b"EndOriginsOwner\0"),
        ("menu", b"ShowOriginsUpgradeMenuState\0"),
        ("confirm_export", b"ConfirmVV5Task9Action\0"),
        ("status_export", b"ShowVV5Task9Result\0"),
        ("sdl", b"SDL2.dll\0"),
        ("flags", b"SDL_GetWindowFlags\0"),
        ("sethint", b"SDL_SetHint\0"),
        ("min_hint", b"SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS\0"),
        ("hint_zero", b"0\0"),
    )
    # These self-contained event strings live in the stock layout only, so the
    # expanded-256 baseline string region stays byte-identical for its overlay.
    time_warp_values = (
        ("appearance_export", b"ShowAppearanceChooser\0"),
        ("genetics_export", b"ShowVV5Task9GeneticsWarning\0"),
        ("writemask_export", b"WriteMaskSidecar\0"),
        ("readmask_export", b"ReadMaskSidecar\0"),
        ("bighead_atlas", b"bigheads_masks.png\0"),
        ("division_export", b"ApplyVV5EqualDivision\0"),
        ("perm_warning", b"This upgrade makes permanent changes to your village. Do you still want to purchase this?\0"),
        ("tw_get", b"GetOriginsOwner\0"),
        ("tw_user32", b"USER32.dll\0"),
        ("tw_messagebox", b"MessageBoxA\0"),
        ("tw_title", b"Origins Upgrades\0"),
        ("tw_warning", b"Do you want to buy Time Warp for 50,000 tech points?\r\nPress OK to confirm, or Cancel.\0"),
        ("tw_paused", b"Time Warp is unavailable while the game is paused.\r\nNo tech points have been deducted.\0"),
        ("tw_insufficient", b"Not enough tech points.\0"),
        ("tw_cancelled", b"Time Warp was canceled.\r\nNo tech points have been deducted.\0"),
        ("tw_recheck", b"The game speed, village clock, or tech-point balance changed during confirmation.\r\nNo tech points have been deducted.\0"),
        ("tw_unavailable", b"Time Warp is unavailable.\r\nNo tech points have been deducted.\0"),
        ("tw_success", b"Time Warp completed.\0"),
        ("tw_charge_unknown", b"The final tech-point balance did not match the exact 50,000-point deduction. The charge outcome is unknown; the village clock was not changed.\0"),
        ("tw_clock_unknown", b"The 50,000-point deduction was verified, but the village clock update could not be verified.\0"),
        ("iv_warning", b"Do you want to buy Island Event for 30,000 tech points?\r\nPress OK to confirm, or Cancel.\0"),
        ("iv_cancelled", b"Island Event was canceled.\r\nNo tech points have been deducted.\0"),
        ("iv_recheck", b"The village or tech-point balance changed during confirmation.\r\nNo tech points have been deducted.\0"),
        ("iv_unavailable", b"Island Event is unavailable.\r\nNo tech points have been deducted.\0"),
        ("iv_success", b"Island Event completed.\0"),
        ("iv_charge_unknown", b"The final tech-point balance did not match the exact 30,000-point deduction. The charge outcome is unknown; no event was queued.\0"),
        ("iv_queue_unknown", b"The 30,000-point deduction was verified, but the event could not be queued.\0"),
        ("bb_warning", b"Do you want to buy Barrel of Babies for 75,000 tech points?\r\nPress OK to confirm, or Cancel.\0"),
        ("bb_full", b"Village population is close to its maximum. The Barrel of Babies needs room for 3 children. No tech points have been deducted.\0"),
        ("bb_cancelled", b"Barrel of Babies was canceled.\r\nNo tech points have been deducted.\0"),
        ("bb_recheck", b"The village population or tech-point balance changed during confirmation.\r\nNo tech points have been deducted.\0"),
        ("bb_unavailable", b"Barrel of Babies is unavailable.\r\nNo tech points have been deducted.\0"),
        ("bb_success", b"Barrel of Babies completed.\0"),
        ("bb_charge_unknown", b"The final tech-point balance did not match the exact 75,000-point deduction. The charge outcome is unknown; no barrel was queued.\0"),
        ("bb_queue_unknown", b"The 75,000-point deduction was verified, but the barrel could not be queued.\0"),
    )
    if page_va == 0x7C9000:
        values = values + time_warp_values
    cursor = OFF["strings"]
    result: dict[str, int] = {}
    for name, value in values:
        result[name] = page_va + cursor
        page[cursor : cursor + len(value)] = value
        cursor += len(value)
    if cursor > PAGE_SIZE:
        raise RuntimeError("Task9 strings overflow")
    return result


def put(page: bytearray, page_va: int, name: str, source: str) -> bytes:
    payload = asm(source, page_va + OFF[name])
    if len(payload) > SIZES[name]:
        raise RuntimeError(f"{name} exceeds reserve: {len(payload):#x}/{SIZES[name]:#x}")
    start = OFF[name]
    if any(page[start : start + SIZES[name]]):
        raise RuntimeError(f"{name} overlaps generated data")
    page[start : start + len(payload)] = payload
    return payload


def build_modal(page: bytearray, page_va: int, s: dict[str, int]) -> dict[str, bytes]:
    tech = put(page, page_va, "tech_entry", f"mov eax, 0x{page_va + OFF['tech_menu']:X}; jmp 0x{page_va + OFF['modal_common']:X}")
    detail = put(page, page_va, "detail_entry", f"mov eax, 0x{page_va + OFF['detail_menu']:X}; jmp 0x{page_va + OFF['modal_common']:X}")
    common = put(
        page,
        page_va,
        "modal_common",
        f"""
            push ebp
            mov ebp, esp
            push ebx
            push esi
            push edi
            sub esp, 0x40
            mov dword ptr [ebp-0x10], eax
            mov dword ptr [ebp-0x14], ecx
            mov dword ptr [ebp-0x2C], -1
            mov dword ptr [ebp-0x34], 0
            mov dword ptr [ebp-0x38], 0
            test ecx, ecx
            jz done
            push 0x{s['dll']:X}
            call dword ptr [0x4951E0]
            test eax, eax
            jz done
            mov dword ptr [ebp-0x3C], eax
            push 0x{s['end']:X}
            push eax
            call dword ptr [0x4951DC]
            test eax, eax
            jz done
            mov dword ptr [ebp-0x34], eax
            push 0x{s['begin']:X}
            push dword ptr [ebp-0x3C]
            call dword ptr [0x4951DC]
            test eax, eax
            jz done
            mov dword ptr [ebp-0x38], 1
            call eax
            test eax, eax
            jz end_owner
            push 0x{s['sdl']:X}
            call dword ptr [0x4951D8]
            test eax, eax
            jz invoke
            push 0x{s['sethint']:X}
            push eax
            call dword ptr [0x4951DC]
            test eax, eax
            jz invoke
            push 0x{s['hint_zero']:X}
            push 0x{s['min_hint']:X}
            call eax
            add esp, 8
        invoke:
            mov ecx, dword ptr [ebp-0x14]
            call dword ptr [ebp-0x10]
            mov dword ptr [ebp-0x2C], eax
        end_owner:
            cmp dword ptr [ebp-0x38], 0
            je done
            mov eax, dword ptr [ebp-0x34]
            test eax, eax
            jz done
            call eax
        done:
            mov eax, dword ptr [ebp-0x2C]
            add esp, 0x40
            pop edi
            pop esi
            pop ebx
            pop ebp
            ret
        """,
    )
    return {"tech_entry": tech, "detail_entry": detail, "modal_common": common}


def build_helpers(page: bytearray, page_va: int, s: dict[str, int]) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    result["constructor_resource"] = put(page, page_va, "constructor_resource", """
        call 0x44FBB0
        mov ecx, eax
        pop edx
        push 0x6A
        jmp edx
    """)
    result["resolve_current"] = put(page, page_va, "resolve_current", f"""
        push ebx
        call 0x425950
        test eax, eax
        jz invalid
        mov ebx, dword ptr [eax+0x17E24]
        cmp ebx, {BOUND}
        jae invalid
        push ebx
        call 0x{page_va + OFF['resolve_index']:X}
        mov edx, ebx
        pop ebx
        ret
    invalid:
        xor eax, eax
        xor edx, edx
        pop ebx
        ret
    """)
    result["resolve_index"] = put(page, page_va, "resolve_index", f"""
        push ebp
        mov ebp, esp
        push ebx
        mov ebx, dword ptr [ebp+8]
        cmp ebx, {BOUND}
        jae invalid
        push ebx
        mov ecx, 0x554148
        call 0x46F950
        test eax, eax
        jz invalid
        cmp byte ptr [eax+0x1CD4], 0
        je invalid
        cmp byte ptr [eax+0x1CE1], 0
        jne invalid
        cmp byte ptr [eax+0x1CEC], 0
        jne invalid
        cmp dword ptr [eax+0x1C40], 0
        jle invalid
        mov edx, ebx
        pop ebx
        pop ebp
        ret 4
    invalid:
        xor eax, eax
        xor edx, edx
        pop ebx
        pop ebp
        ret 4
    """)
    result["resolve_manager"] = put(page, page_va, "resolve_manager", """
        test eax, eax
        jz invalid
        mov ebx, dword ptr [eax+0x17E24]
        cmp ebx, 150
        jae invalid
        push ebx
        mov ecx, 0x554148
        call 0x46F950
        test eax, eax
        jz invalid
        cmp byte ptr [eax+0x1CD4], 0
        je invalid
        cmp byte ptr [eax+0x1CE1], 0
        jne invalid
        cmp byte ptr [eax+0x1CEC], 0
        jne invalid
        cmp dword ptr [eax+0x1C40], 0
        jle invalid
        pop ebx
        ret
    invalid:
        xor eax, eax
        pop ebx
        ret
    """)
    result["eligible"] = put(page, page_va, "eligible", """
        mov edx, dword ptr [esp+4]
        xor eax, eax
        test edx, edx
        jz done
        cmp byte ptr [edx+0x1CD4], 0
        je done
        cmp byte ptr [edx+0x1CE1], 0
        jne done
        cmp byte ptr [edx+0x1CEC], 0
        jne done
        cmp dword ptr [edx+0x1C40], 0
        jle done
        inc eax
    done:
        ret 4
    """)
    helper_specs = [
        ("show_menu", "menu", 2),
        ("confirm", "confirm_export", 3),
        ("status", "status_export", 4),
    ]
    # apply_division forwards to the companion DLL's ApplyVV5EqualDivision(base,
    # parenting); its export string lives only in the stock string table, so the
    # helper is emitted only there (the expanded-256 baseline page stays byte-
    # identical for its overlay).
    if page_va == 0x7C9000:
        helper_specs.append(("apply_division", "division_export", 2))
    for name, export, argc in helper_specs:
        pushes = "\n".join(
            f"push dword ptr [ebp+{8 + index * 4:#x}]"
            for index in range(argc - 1, -1, -1)
        )
        result[name] = put(page, page_va, name, f"""
            push ebp
            mov ebp, esp
            push ebx
            push 0x{s['dll']:X}
            call dword ptr [0x4951E0]
            test eax, eax
            jz unavailable
            push 0x{s[export]:X}
            push eax
            call dword ptr [0x4951DC]
            test eax, eax
            jz unavailable
            {pushes}
            call eax
            jmp done
        unavailable:
            mov eax, -1
        done:
            pop ebx
            pop ebp
            ret {argc * 4}
        """)
    return result


def status_call(page_va: int, action: str, status: int, a: str = "0", b: str = "0") -> str:
    return f"push {b}; push {a}; push {status}; push {action}; call 0x{page_va + OFF['status']:X}"


def build_menus(page: bytearray, page_va: int) -> dict[str, bytes]:
    # Time Warp (row 0), Island Event (row 1), and Barrel of Babies (row 2) are
    # enabled only in the stock page layout (0x7C9000). The expanded-256 baseline
    # (0x904000) is left byte-identical so the separate vv5_expanded_256_time_warp
    # overlay continues to own Time Warp there.
    native_stock = page_va == 0x7C9000
    # The expanded-256 baseline page is kept byte-identical to its pre-Collections
    # form so the separate vv5_expanded_256_time_warp overlay (which surgically
    # patches fixed offsets in this tech_menu) keeps working. Every Collections /
    # doubler-confirm addition below is therefore gated to the stock layout; in
    # expanded the two Collections rows render but are bounded out as no-ops.
    menu_state = 0x000 if native_stock else 0x700
    # Command upper bound: 0..12 in stock (Collections rows 9/10 plus the two
    # Equal Division of Labor rows 11/12), 0..5 in expanded (original), so the
    # expanded router bytes stay identical.
    command_bound = 12 if native_stock else 5
    collections_guard = (
        "cmp ebx, 6\n        jae unavailable\n        " if native_stock else ""
    )
    # Name the point doublers correctly in their result (action 18/19) in stock;
    # the expanded baseline keeps the original ebx form so its page stays
    # byte-identical for the vv5_expanded_256_time_warp overlay.
    doubler_action = "lea eax, [edi+17]\n        " if native_stock else ""
    doubler_reg = "eax" if native_stock else "ebx"
    doubler_confirm = (
        "lea eax, [edi+17]\n"
        "        push 0\n"
        "        push 0\n"
        "        push eax\n"
        f"        call 0x{page_va + OFF['confirm']:X}\n"
        "        cmp eax, 1\n"
        "        jne done\n"
        "        cmp dword ptr [0x41F1E6], 0x96\n"
        "        jne unavailable\n"
        "        mov esi, dword ptr [0x51D5F8]\n"
        "        cmp esi, 500000\n"
        "        jb insufficient\n        "
        if native_stock
        else ""
    )
    tw_dispatch = (
        "test ebx, ebx\n        jz time_warp_row\n"
        "        cmp ebx, 1\n        je island_row\n"
        "        cmp ebx, 2\n        je barrel_row\n"
        "        cmp ebx, 6\n        je running_all_row\n"
        "        cmp ebx, 7\n        je mastery_all_row\n"
        "        cmp ebx, 8\n        je age18_all_row\n"
        "        cmp ebx, 9\n        je complete_collections_row\n"
        "        cmp ebx, 10\n        je reset_collections_row\n"
        "        cmp ebx, 11\n        je division_parenting_row\n"
        "        cmp ebx, 12\n        je division_no_parenting_row\n        "
        if native_stock
        else ""
    )
    tw_row = (
        f"time_warp_row:\n        call 0x{page_va + OFF['time_warp']:X}\n"
        "        jmp done\n        nop\n        nop\n        nop\n"
        f"    island_row:\n        call 0x{page_va + OFF['island']:X}\n"
        "        jmp done\n        nop\n        nop\n        nop\n"
        f"    barrel_row:\n        call 0x{page_va + OFF['barrel']:X}\n"
        "        jmp done\n        nop\n        nop\n        nop\n"
        f"    complete_collections_row:\n        call 0x{page_va + OFF['complete_collections']:X}\n"
        "        jmp done\n        nop\n        nop\n        nop\n"
        f"    reset_collections_row:\n        call 0x{page_va + OFF['reset_collections']:X}\n"
        "        jmp done\n        nop\n        nop\n        nop\n"
        f"    running_all_row:\n        call 0x{page_va + OFF['running_all']:X}\n"
        "        jmp done\n        nop\n        nop\n        nop\n"
        f"    mastery_all_row:\n        call 0x{page_va + OFF['mastery_all']:X}\n"
        "        jmp done\n        nop\n        nop\n        nop\n"
        f"    age18_all_row:\n        call 0x{page_va + OFF['age18_all']:X}\n"
        "        jmp done\n        nop\n        nop\n        nop\n"
        f"    division_parenting_row:\n        call 0x{page_va + OFF['division_parenting']:X}\n"
        "        jmp done\n        nop\n        nop\n        nop\n"
        f"    division_no_parenting_row:\n        call 0x{page_va + OFF['division_no_parenting']:X}\n"
        "        jmp done\n        nop\n        nop\n        nop\n    "
        if native_stock
        else ""
    )
    # Change Appearance is a per-villager (detail) row. The companion DLL shows
    # its row in every layout, but the router is gated to the stock layout so
    # the expanded-256 baseline page stays byte-identical for its overlay; in
    # expanded modes the row is a harmless no-op.
    detail_max = 4 if native_stock else 3
    appearance_dispatch = "cmp ebx, 4\n        je appearance_row\n        " if native_stock else ""
    appearance_row = (
        f"appearance_row:\n        call 0x{page_va + OFF['appearance']:X}\n        jmp menu\n    "
        if native_stock
        else ""
    )
    tech = put(page, page_va, "tech_menu", f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
    menu:
        mov eax, 0x{menu_state:X}
        test dword ptr [0x51D388], 1
        jz tech_not_owned
        or eax, 8
        jmp food_state
    tech_not_owned:
        cmp dword ptr [0x41F1E6], 0x96
        je food_state
        or eax, 0x800
    food_state:
        test dword ptr [0x51D388], 2
        jz food_not_owned
        or eax, 16
        jmp show
    food_not_owned:
        cmp dword ptr [0x41F1E6], 0x96
        je show
        or eax, 0x1000
    show:
        push eax
        push 0
        call 0x{page_va + OFF['show_menu']:X}
        cmp eax, -1
        je done
        mov ebx, eax
        cmp ebx, {command_bound}
        ja done
        {tw_dispatch}cmp ebx, 3
        jb unavailable
        cmp ebx, 5
        je heal
        {collections_guard}mov edi, 1
        cmp ebx, 3
        je have_mask
        mov edi, 2
    have_mask:
        test dword ptr [0x51D388], edi
        jz purchase
        mov eax, edi
        not eax
        and dword ptr [0x51D388], eax
        test dword ptr [0x51D388], edi
        jnz retained
        {doubler_action}{status_call(page_va, doubler_reg, 11)}
        jmp done
        nop
        nop
        nop
    purchase:
        cmp dword ptr [0x41F1E6], 0x96
        jne unavailable
        mov esi, dword ptr [0x51D5F8]
        cmp esi, 500000
        jb insufficient
        {doubler_confirm}or dword ptr [0x51D388], edi
        test dword ptr [0x51D388], edi
        jz retained
        cmp dword ptr [0x51D5F8], esi
        jne retained
        push -500000
        mov ecx, 0x51D5F8
        call 0x4237B0
        mov eax, esi
        sub eax, 500000
        cmp dword ptr [0x51D5F8], eax
        jne charge_unknown
        {doubler_action}{status_call(page_va, doubler_reg, 12)}
        jmp done
        nop
        nop
        nop
    heal:
        call 0x{page_va + OFF['heal']:X}
        jmp done
        nop
        nop
        nop
    {tw_row}unavailable:
        {status_call(page_va, 'ebx', 10)}
        jmp done
        nop
        nop
        nop
    insufficient:
        {status_call(page_va, 'ebx', 3)}
        jmp done
        nop
        nop
        nop
    retained:
        {status_call(page_va, 'ebx', 6)}
        jmp done
        nop
        nop
        nop
    charge_unknown:
        {status_call(page_va, 'ebx', 7)}
        jmp done
        nop
        nop
        nop
    done:
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """)
    detail = put(page, page_va, "detail_menu", f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
    menu:
        push 0
        push 1
        call 0x{page_va + OFF['show_menu']:X}
        cmp eax, -1
        je done
        mov ebx, eax
        cmp ebx, {detail_max}
        ja done
        {appearance_dispatch}cmp ebx, 0
        je age
        cmp ebx, 1
        je mastery
        cmp ebx, 2
        je running
        mov eax, 3
    age:
        call 0x{page_va + OFF['age']:X}
        jmp menu
    mastery:
        call 0x{page_va + OFF['mastery']:X}
        jmp menu
    running:
        call 0x{page_va + OFF['running']:X}
        jmp menu
    {appearance_row}done:
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """)
    return {"tech_menu": tech, "detail_menu": detail}


def build_age(page: bytearray, page_va: int) -> bytes:
    return put(page, page_va, "age", f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x50
        mov dword ptr [ebp-0x10], eax
        call 0x{page_va + OFF['resolve_current']:X}
        test eax, eax
        jz invalid
        mov dword ptr [ebp-0x18], eax
        mov dword ptr [ebp-0x14], edx
        push eax
        call 0x{page_va + OFF['eligible']:X}
        test eax, eax
        jz invalid
        mov esi, dword ptr [ebp-0x18]
        mov eax, dword ptr [esi+0x1B8C]
        mov dword ptr [ebp-0x1C], eax
        mov eax, dword ptr [esi+0x1C3C]
        mov dword ptr [ebp-0x20], eax
        mov eax, dword ptr [esi+0x1C4C]
        mov dword ptr [ebp-0x24], eax
        mov eax, dword ptr [0x51D5F8]
        mov dword ptr [ebp-0x28], eax
        cmp dword ptr [ebp-0x10], 3
        je age18
        mov eax, dword ptr [ebp-0x1C]
        sub eax, 700
        jo invalid
        cmp eax, 100
        jge target_ready
        mov eax, 100
        jmp target_ready
    age18:
        mov eax, 360
    target_ready:
        mov dword ptr [ebp-0x2C], eax
        sub eax, dword ptr [ebp-0x1C]
        jo invalid
        mov dword ptr [ebp-0x30], eax
        test eax, eax
        jz no_change
        cmp dword ptr [ebp-0x28], 50000
        jb insufficient
        push 0
        push 0
        push dword ptr [ebp-0x10]
        call 0x{page_va + OFF['confirm']:X}
        cmp eax, 1
        jne cancelled
        push dword ptr [ebp-0x14]
        call 0x{page_va + OFF['resolve_index']:X}
        test eax, eax
        jz recheck
        cmp eax, dword ptr [ebp-0x18]
        jne recheck
        mov esi, eax
        push eax
        call 0x{page_va + OFF['eligible']:X}
        test eax, eax
        jz recheck
        mov eax, dword ptr [esi+0x1B8C]
        cmp eax, dword ptr [ebp-0x1C]
        jne recheck
        mov eax, dword ptr [esi+0x1C3C]
        cmp eax, dword ptr [ebp-0x20]
        jne recheck
        mov eax, dword ptr [esi+0x1C4C]
        cmp eax, dword ptr [ebp-0x24]
        jne recheck
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x28]
        jne recheck
        cmp eax, 50000
        jb insufficient
        mov eax, dword ptr [ebp-0x20]
        add eax, dword ptr [ebp-0x30]
        jo recheck
        mov dword ptr [ebp-0x34], eax
        mov eax, dword ptr [ebp-0x24]
        test eax, eax
        jz timer_ready
        add eax, dword ptr [ebp-0x30]
        jo recheck
    timer_ready:
        mov dword ptr [ebp-0x38], eax
        push dword ptr [ebp-0x30]
        lea ecx, [esi+0x1B8C]
        call 0x46F7F0
        mov eax, dword ptr [esi+0x1B8C]
        cmp eax, dword ptr [ebp-0x2C]
        jne retained
        mov eax, dword ptr [ebp-0x34]
        mov dword ptr [esi+0x1C3C], eax
        cmp dword ptr [esi+0x1C3C], eax
        jne retained
        cmp dword ptr [ebp-0x24], 0
        je postverify
        mov eax, dword ptr [ebp-0x38]
        mov dword ptr [esi+0x1C4C], eax
        cmp dword ptr [esi+0x1C4C], eax
        jne retained
    postverify:
        push dword ptr [ebp-0x14]
        call 0x{page_va + OFF['resolve_index']:X}
        cmp eax, dword ptr [ebp-0x18]
        jne retained
        mov esi, eax
        push eax
        call 0x{page_va + OFF['eligible']:X}
        test eax, eax
        jz retained
        mov eax, dword ptr [esi+0x1B8C]
        cmp eax, dword ptr [ebp-0x2C]
        jne retained
        mov eax, dword ptr [esi+0x1C3C]
        cmp eax, dword ptr [ebp-0x34]
        jne retained
        mov eax, dword ptr [esi+0x1C4C]
        cmp eax, dword ptr [ebp-0x38]
        jne retained
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x28]
        jne retained
        push -50000
        mov ecx, 0x51D5F8
        call 0x4237B0
        mov eax, dword ptr [ebp-0x28]
        sub eax, 50000
        cmp dword ptr [0x51D5F8], eax
        jne charge_unknown
        {status_call(page_va, 'dword ptr [ebp-0x10]', 0)}
        jmp done
    invalid:
        {status_call(page_va, 'dword ptr [ebp-0x10]', 2)}
        jmp done
    no_change:
        {status_call(page_va, 'dword ptr [ebp-0x10]', 1)}
        jmp done
    insufficient:
        {status_call(page_va, 'dword ptr [ebp-0x10]', 3)}
        jmp done
    cancelled:
        {status_call(page_va, 'dword ptr [ebp-0x10]', 4)}
        jmp done
    recheck:
        {status_call(page_va, 'dword ptr [ebp-0x10]', 5)}
        jmp done
    retained:
        {status_call(page_va, 'dword ptr [ebp-0x10]', 6)}
        jmp done
    charge_unknown:
        {status_call(page_va, 'dword ptr [ebp-0x10]', 7)}
    done:
        add esp, 0x50
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """)


def build_mastery(page: bytearray, page_va: int) -> bytes:
    return put(page, page_va, "mastery", f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x60
        mov dword ptr [ebp-0x20], 0
        call 0x{page_va + OFF['resolve_current']:X}
        test eax, eax
        jz invalid
        mov dword ptr [ebp-0x14], eax
        mov dword ptr [ebp-0x10], edx
        push eax
        call 0x{page_va + OFF['eligible']:X}
        test eax, eax
        jz invalid
        mov esi, dword ptr [ebp-0x14]
        xor edi, edi
        xor ebx, ebx
    snapshot:
        mov eax, dword ptr [esi+edi*4+0x1C5C]
        mov dword ptr [ebp+edi*4-0x40], eax
        mov edx, eax
        and edx, 0x7FFFFFFF
        cmp edx, 0x7F800000
        jae invalid_skill
        test edx, edx
        jz finite
        test eax, 0x80000000
        jne invalid_skill
    finite:
        cmp edx, 0x42C80000
        ja invalid_skill
        cmp eax, 0x42C80000
        je snapshot_next
        inc ebx
    snapshot_next:
        inc edi
        cmp edi, 6
        jb snapshot
        test ebx, ebx
        jz no_change
        mov eax, dword ptr [0x51D5F8]
        mov dword ptr [ebp-0x18], eax
        cmp eax, 100000
        jb insufficient
        push 0
        push 0
        push 1
        call 0x{page_va + OFF['confirm']:X}
        cmp eax, 1
        jne cancelled
        push dword ptr [ebp-0x10]
        call 0x{page_va + OFF['resolve_index']:X}
        cmp eax, dword ptr [ebp-0x14]
        jne recheck
        mov esi, eax
        push eax
        call 0x{page_va + OFF['eligible']:X}
        test eax, eax
        jz recheck
        xor edi, edi
    initial_compare:
        mov eax, dword ptr [esi+edi*4+0x1C5C]
        cmp eax, dword ptr [ebp+edi*4-0x40]
        jne recheck
        inc edi
        cmp edi, 6
        jb initial_compare
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x18]
        jne recheck
        cmp eax, 100000
        jb insufficient
        xor edi, edi
    writer_loop:
        push dword ptr [ebp-0x10]
        call 0x{page_va + OFF['resolve_index']:X}
        cmp eax, dword ptr [ebp-0x14]
        jne write_failure
        mov esi, eax
        push eax
        call 0x{page_va + OFF['eligible']:X}
        test eax, eax
        jz write_failure
        xor ecx, ecx
    evolving_compare:
        mov eax, dword ptr [esi+ecx*4+0x1C5C]
        cmp ecx, edi
        jb expect_mastered
        cmp eax, dword ptr [ebp+ecx*4-0x40]
        jne write_failure
        jmp evolving_next
    expect_mastered:
        cmp eax, 0x42C80000
        jne write_failure
    evolving_next:
        inc ecx
        cmp ecx, 6
        jb evolving_compare
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x18]
        jne write_failure
        cmp dword ptr [esi+edi*4+0x1C5C], 0x42C80000
        je writer_next
        mov dword ptr [ebp-0x20], 1
        push 0x42C80000
        fld dword ptr [esp]
        fsub dword ptr [esi+edi*4+0x1C5C]
        fstp dword ptr [esp]
        push edi
        lea ecx, [esi+0x1C5C]
        call 0x475730
        cmp dword ptr [esi+edi*4+0x1C5C], 0x42C80000
        jne retained
    writer_next:
        inc edi
        cmp edi, 6
        jb writer_loop
        push dword ptr [ebp-0x10]
        call 0x{page_va + OFF['resolve_index']:X}
        cmp eax, dword ptr [ebp-0x14]
        jne retained
        mov esi, eax
        push eax
        call 0x{page_va + OFF['eligible']:X}
        test eax, eax
        jz retained
        xor edi, edi
    final_verify:
        cmp dword ptr [esi+edi*4+0x1C5C], 0x42C80000
        jne retained
        inc edi
        cmp edi, 6
        jb final_verify
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x18]
        jne retained
        push -100000
        mov ecx, 0x51D5F8
        call 0x4237B0
        mov eax, dword ptr [ebp-0x18]
        sub eax, 100000
        cmp dword ptr [0x51D5F8], eax
        jne charge_unknown
        {status_call(page_va, '1', 0)}
        jmp done
    write_failure:
        cmp dword ptr [ebp-0x20], 0
        jne retained
        jmp recheck
    invalid:
        {status_call(page_va, '1', 2)}
        jmp done
    invalid_skill:
        {status_call(page_va, '1', 9)}
        jmp done
    no_change:
        {status_call(page_va, '1', 1)}
        jmp done
    insufficient:
        {status_call(page_va, '1', 3)}
        jmp done
    cancelled:
        {status_call(page_va, '1', 4)}
        jmp done
    recheck:
        {status_call(page_va, '1', 5)}
        jmp done
    retained:
        {status_call(page_va, '1', 6)}
        jmp done
    charge_unknown:
        {status_call(page_va, '1', 7)}
    done:
        add esp, 0x60
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """)


def build_running(page: bytearray, page_va: int) -> bytes:
    """Grant Running to the selected Believer (40,000 tech points). Inserts
    preference 38 into the first empty Like slot (0x464AD0) and clears any
    Running dislike (0x4649E0), charging only when the Like is actually added.
    If all three Like slots are full: when the villager also has a Running
    dislike, that dislike is removed for free (no charge) and reported as
    RESULT 14; with no Running dislike it is a true no-op (RESULT 8). This
    mirrors the Grant-Running-to-All edge behavior."""
    return put(page, page_va, "running", f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x70
        mov dword ptr [ebp-0x1C], -1
        mov dword ptr [ebp-0x44], 0
        mov dword ptr [ebp-0x48], 0
        call 0x{page_va + OFF['resolve_current']:X}
        test eax, eax
        jz invalid
        mov dword ptr [ebp-0x14], eax
        mov dword ptr [ebp-0x10], edx
        push eax
        call 0x{page_va + OFF['eligible']:X}
        test eax, eax
        jz invalid
        mov esi, dword ptr [ebp-0x14]
        xor edi, edi
    snapshot_likes:
        mov eax, dword ptr [esi+edi*4+0x1F5C]
        mov dword ptr [ebp+edi*4-0x30], eax
        inc edi
        cmp edi, 3
        jb snapshot_likes
        xor edi, edi
    snapshot_dislikes:
        mov eax, dword ptr [esi+edi*4+0x1F68]
        mov dword ptr [ebp+edi*4-0x40], eax
        inc edi
        cmp edi, 3
        jb snapshot_dislikes
        mov eax, dword ptr [0x51D5F8]
        mov dword ptr [ebp-0x18], eax
        push 38
        lea ecx, [esi+0x1F5C]
        call 0x464F90
        test al, al
        jnz no_change
        xor edi, edi
    find_empty:
        cmp dword ptr [ebp+edi*4-0x30], -1
        je found_empty
        inc edi
        cmp edi, 3
        jb find_empty
        jmp no_slot
    found_empty:
        mov dword ptr [ebp-0x1C], edi
        cmp dword ptr [ebp-0x18], 40000
        jb insufficient
        push 0
        push 0
        push 2
        call 0x{page_va + OFF['confirm']:X}
        cmp eax, 1
        jne cancelled
        call running_reacquire_exact
        test eax, eax
        jz recheck
        push 38
        lea ecx, [esi+0x1F5C]
        call 0x464AD0
        mov dword ptr [ebp-0x48], 1
        xor edi, edi
    verify_insert_likes:
        mov eax, dword ptr [ebp+edi*4-0x30]
        cmp edi, dword ptr [ebp-0x1C]
        jne verify_insert_like
        mov eax, 38
    verify_insert_like:
        cmp dword ptr [esi+edi*4+0x1F5C], eax
        jne rollback
        inc edi
        cmp edi, 3
        jb verify_insert_likes
        xor edi, edi
    verify_insert_dislikes:
        mov eax, dword ptr [ebp+edi*4-0x40]
        cmp dword ptr [esi+edi*4+0x1F68], eax
        jne rollback
        inc edi
        cmp edi, 3
        jb verify_insert_dislikes
        xor edi, edi
    removal_loop:
        cmp dword ptr [ebp+edi*4-0x40], 38
        jne removal_next
        push edi
        call running_reacquire_evolving
        pop edi
        test eax, eax
        jz rollback
        push 38
        lea ecx, [esi+0x1F68]
        call 0x4649E0
        mov eax, 2
        mov ecx, edi
        shl eax, cl
        or dword ptr [ebp-0x48], eax
        cmp dword ptr [esi+edi*4+0x1F68], -1
        jne rollback
    removal_next:
        inc edi
        cmp edi, 3
        jb removal_loop
        call running_reacquire_evolving
        test eax, eax
        jz rollback
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x18]
        jne rollback
        push -40000
        mov ecx, 0x51D5F8
        call 0x4237B0
        mov eax, dword ptr [ebp-0x18]
        sub eax, 40000
        cmp dword ptr [0x51D5F8], eax
        jne charge_unknown
        {status_call(page_va, '2', 0)}
        jmp done
    running_reacquire_exact:
        push dword ptr [ebp-0x10]
        call 0x{page_va + OFF['resolve_index']:X}
        cmp eax, dword ptr [ebp-0x14]
        jne running_exact_fail
        mov esi, eax
        push eax
        call 0x{page_va + OFF['eligible']:X}
        test eax, eax
        jz running_exact_fail
        xor ecx, ecx
    running_exact_likes:
        mov eax, dword ptr [ebp+ecx*4-0x30]
        cmp dword ptr [esi+ecx*4+0x1F5C], eax
        jne running_exact_fail
        inc ecx
        cmp ecx, 3
        jb running_exact_likes
        xor ecx, ecx
    running_exact_dislikes:
        mov eax, dword ptr [ebp+ecx*4-0x40]
        cmp dword ptr [esi+ecx*4+0x1F68], eax
        jne running_exact_fail
        inc ecx
        cmp ecx, 3
        jb running_exact_dislikes
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x18]
        jne running_exact_fail
        mov eax, 1
        ret
    running_exact_fail:
        xor eax, eax
        ret
    running_reacquire_evolving:
        push dword ptr [ebp-0x10]
        call 0x{page_va + OFF['resolve_index']:X}
        cmp eax, dword ptr [ebp-0x14]
        jne running_evolving_fail
        mov esi, eax
        push eax
        call 0x{page_va + OFF['eligible']:X}
        test eax, eax
        jz running_evolving_fail
        xor ecx, ecx
    evolving_likes:
        mov eax, dword ptr [ebp+ecx*4-0x30]
        cmp ecx, dword ptr [ebp-0x1C]
        jne evolving_like_compare
        mov eax, 38
    evolving_like_compare:
        cmp dword ptr [esi+ecx*4+0x1F5C], eax
        jne running_evolving_fail
        inc ecx
        cmp ecx, 3
        jb evolving_likes
        xor ecx, ecx
    evolving_dislikes:
        mov eax, dword ptr [ebp+ecx*4-0x40]
        mov edx, 2
        shl edx, cl
        test dword ptr [ebp-0x48], edx
        jz evolving_dislike_compare
        mov eax, -1
    evolving_dislike_compare:
        cmp dword ptr [esi+ecx*4+0x1F68], eax
        jne running_evolving_fail
        inc ecx
        cmp ecx, 3
        jb evolving_dislikes
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x18]
        jne running_evolving_fail
        mov eax, 1
        ret
    running_evolving_fail:
        xor eax, eax
        ret
    rollback:
        mov edi, 2
    rollback_dislikes:
        mov eax, 2
        mov ecx, edi
        shl eax, cl
        test dword ptr [ebp-0x48], eax
        jz rollback_dislike_next
        push edi
        call running_reacquire_evolving
        pop edi
        test eax, eax
        jz rollback_dislike_next
        cmp dword ptr [esi+edi*4+0x1F68], -1
        jne rollback_dislike_next
        mov dword ptr [esi+edi*4+0x1F68], 38
        cmp dword ptr [esi+edi*4+0x1F68], 38
        jne rollback_dislike_next
        mov eax, 2
        mov ecx, edi
        shl eax, cl
        not eax
        and dword ptr [ebp-0x48], eax
    rollback_dislike_next:
        dec edi
        jns rollback_dislikes
        test dword ptr [ebp-0x48], 1
        jz retained
        call running_reacquire_evolving
        test eax, eax
        jz retained
        mov edi, dword ptr [ebp-0x1C]
        cmp dword ptr [esi+edi*4+0x1F5C], 38
        jne retained
        mov dword ptr [esi+edi*4+0x1F5C], -1
        cmp dword ptr [esi+edi*4+0x1F5C], -1
        jne retained
        and dword ptr [ebp-0x48], 0xFFFFFFFE
        jmp retained
    invalid:
        {status_call(page_va, '2', 2)}
        jmp done
    no_change:
        {status_call(page_va, '2', 1)}
        jmp done
    no_slot:
        xor edi, edi
    no_slot_find_dislike:
        cmp dword ptr [ebp+edi*4-0x40], 38
        je no_slot_remove_dislike
        inc edi
        cmp edi, 3
        jb no_slot_find_dislike
        {status_call(page_va, '2', 8)}
        jmp done
    no_slot_remove_dislike:
        call running_reacquire_exact
        test eax, eax
        jz recheck
        push 38
        lea ecx, [esi+0x1F68]
        call 0x4649E0
        xor edi, edi
    no_slot_verify_gone:
        cmp dword ptr [esi+edi*4+0x1F68], 38
        je retained
        inc edi
        cmp edi, 3
        jb no_slot_verify_gone
        {status_call(page_va, '2', 14)}
        jmp done
    insufficient:
        {status_call(page_va, '2', 3)}
        jmp done
    cancelled:
        {status_call(page_va, '2', 4)}
        jmp done
    recheck:
        {status_call(page_va, '2', 5)}
        jmp done
    retained:
        {status_call(page_va, '2', 6)}
        jmp done
    charge_unknown:
        {status_call(page_va, '2', 7)}
    done:
        add esp, 0x70
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """)


def build_heal(page: bytearray, page_va: int) -> bytes:
    """Full Heal / Cure All (village-wide, 30,000 tech points). Clean single-pass
    design (mirrors the VV2 cure): a count pass tallies eligible sick + partial-
    health Believers for the confirm dialog and refuses if any eligible Believer
    carries the unsupported sickness type 12; then, after the shared confirm and a
    verified 30,000 charge, a single heal pass restores each eligible living
    Believer's health to 100 via the native writer 0x4758B0 and clears sickness
    (+0x1C48), crediting the people-cured statistic. Believer gate only (never
    masked Heathens or off-faction). No per-villager before/after snapshot: each
    pass re-reads the live record, so there is no stale-snapshot comparison."""
    # The expanded-256 baseline page must stay byte-identical for the separate
    # vv5_expanded_256_time_warp overlay, so the clean rewrite is applied only to
    # the stock layout; expanded keeps the original (unused, experimental) heal.
    if page_va != 0x7C9000:
        return put(page, page_va, "heal", f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x1000
        mov dword ptr [ebp-0x18], 0
        mov dword ptr [ebp-0x1C], 0
        mov dword ptr [ebp-0x20], 0
        mov dword ptr [ebp-0x24], 0
        mov eax, dword ptr [0x51D5F8]
        mov dword ptr [ebp-0x10], eax
        mov eax, dword ptr [0x51D368]
        mov dword ptr [ebp-0x14], eax
        mov esi, 0x554190
        lea edi, [ebp-0xF00]
        mov ebx, {BOUND}
    dry_loop:
        movzx eax, byte ptr [esi+0x1CD4]
        mov dword ptr [edi], eax
        movzx eax, byte ptr [esi+0x1CE1]
        mov dword ptr [edi+20], eax
        cmp dword ptr [edi], 0
        je dry_next
        cmp dword ptr [edi+20], 0
        jne dry_next
        movzx eax, byte ptr [esi+0x1CEC]
        mov dword ptr [edi+8], eax
        cmp dword ptr [edi+8], 0
        jne dry_next
        mov eax, dword ptr [esi+0x1C40]
        mov dword ptr [edi+4], eax
        cmp dword ptr [edi+4], 0
        jle dry_next
        movzx eax, byte ptr [esi+0x1C48]
        mov dword ptr [edi+12], eax
        mov eax, dword ptr [esi+0x1CFC]
        mov dword ptr [edi+16], eax
        cmp dword ptr [edi+12], 0
        je dry_health
        cmp dword ptr [edi+16], 12
        je unsupported
        inc dword ptr [ebp-0x18]
    dry_health:
        cmp dword ptr [edi+4], 100
        jae dry_next
        inc dword ptr [ebp-0x1C]
    dry_next:
        add esi, {STRIDE}
        add edi, 24
        dec ebx
        jne dry_loop
        mov eax, dword ptr [ebp-0x18]
        or eax, dword ptr [ebp-0x1C]
        jz no_change
        cmp dword ptr [ebp-0x10], 30000
        jb insufficient
        push dword ptr [ebp-0x1C]
        push dword ptr [ebp-0x18]
        push 4
        call 0x{page_va + OFF['confirm']:X}
        cmp eax, 1
        jne cancelled
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x10]
        jne recheck
        mov eax, dword ptr [0x51D368]
        cmp eax, dword ptr [ebp-0x14]
        jne recheck
        mov esi, 0x554190
        lea edi, [ebp-0xF00]
        mov ebx, {BOUND}
    fresh_loop:
        cmp dword ptr [edi], 0
        je fresh_next
        cmp dword ptr [edi+20], 0
        jne fresh_next
        movzx eax, byte ptr [esi+0x1CD4]
        cmp eax, dword ptr [edi]
        jne recheck
        movzx eax, byte ptr [esi+0x1CE1]
        cmp eax, dword ptr [edi+20]
        jne recheck
        movzx eax, byte ptr [esi+0x1CEC]
        cmp eax, dword ptr [edi+8]
        jne recheck
        mov eax, dword ptr [esi+0x1C40]
        cmp eax, dword ptr [edi+4]
        jne recheck
        movzx eax, byte ptr [esi+0x1C48]
        cmp eax, dword ptr [edi+12]
        jne recheck
        mov eax, dword ptr [esi+0x1CFC]
        cmp eax, dword ptr [edi+16]
        jne recheck
    fresh_next:
        add esi, {STRIDE}
        add edi, 24
        dec ebx
        jne fresh_loop
        mov esi, 0x554190
        lea edi, [ebp-0xF00]
        mov ebx, {BOUND}
    write_loop:
        cmp dword ptr [edi], 0
        je write_next
        cmp dword ptr [edi+20], 0
        jne write_next
        movzx eax, byte ptr [esi+0x1CEC]
        cmp eax, dword ptr [edi+8]
        jne write_next
        cmp dword ptr [edi+4], 0
        jle write_next
        cmp dword ptr [edi+4], 100
        jae sickness_write
        call heal_record_guard
        test eax, eax
        jz retained
        mov dword ptr [ebp-0x20], 1
        push -1
        push 100
        lea ecx, [esi+0x1C34]
        call 0x4758B0
        cmp dword ptr [esi+0x1C40], 100
        jne retained
    sickness_write:
        cmp dword ptr [edi+12], 0
        je write_next
        call heal_record_guard_evolving
        test eax, eax
        jz retained
        mov dword ptr [ebp-0x20], 1
        mov byte ptr [esi+0x1C48], 0
        cmp byte ptr [esi+0x1C48], 0
        jne retained
        inc dword ptr [0x51D368]
        inc dword ptr [ebp-0x24]
        mov eax, dword ptr [ebp-0x14]
        add eax, dword ptr [ebp-0x24]
        cmp dword ptr [0x51D368], eax
        jne retained
        push 1
        push 52
        mov ecx, 0x4DB358
        call 0x413450
        push 1
        push 53
        mov ecx, 0x4DB358
        call 0x413450
        push 1
        push 54
        mov ecx, 0x4DB358
        call 0x413450
        jmp write_next
    write_next:
        add esi, {STRIDE}
        add edi, 24
        dec ebx
        jne write_loop
        mov esi, 0x554190
        lea edi, [ebp-0xF00]
        mov ebx, {BOUND}
    post_loop:
        movzx eax, byte ptr [esi+0x1CD4]
        cmp eax, dword ptr [edi]
        jne retained
        movzx eax, byte ptr [esi+0x1CE1]
        cmp eax, dword ptr [edi+20]
        jne retained
        cmp dword ptr [edi+20], 0
        jne post_next
        cmp dword ptr [edi], 0
        je post_next
        movzx eax, byte ptr [esi+0x1CEC]
        cmp eax, dword ptr [edi+8]
        jne retained
        mov eax, dword ptr [esi+0x1CFC]
        cmp eax, dword ptr [edi+16]
        jne retained
        cmp dword ptr [edi], 0
        je post_ineligible
        cmp dword ptr [edi+4], 0
        jle post_ineligible
        cmp dword ptr [edi+8], 0
        jne post_ineligible
        cmp dword ptr [edi+4], 100
        jae post_health_unchanged
        cmp dword ptr [esi+0x1C40], 100
        jne retained
        jmp post_health_done
    post_health_unchanged:
        mov eax, dword ptr [esi+0x1C40]
        cmp eax, dword ptr [edi+4]
        jne retained
    post_health_done:
        cmp byte ptr [esi+0x1C48], 0
        jne retained
        jmp post_next
    post_ineligible:
        mov eax, dword ptr [esi+0x1C40]
        cmp eax, dword ptr [edi+4]
        jne retained
        movzx eax, byte ptr [esi+0x1C48]
        cmp eax, dword ptr [edi+12]
        jne retained
    post_next:
        add esi, {STRIDE}
        add edi, 24
        dec ebx
        jne post_loop
        mov eax, dword ptr [ebp-0x14]
        add eax, dword ptr [ebp-0x18]
        cmp dword ptr [0x51D368], eax
        jne retained
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x10]
        jne retained
        push -30000
        mov ecx, 0x51D5F8
        call 0x4237B0
        mov eax, dword ptr [ebp-0x10]
        sub eax, 30000
        cmp dword ptr [0x51D5F8], eax
        jne charge_unknown
        {status_call(page_va, '4', 0, 'dword ptr [ebp-0x18]', 'dword ptr [ebp-0x1C]')}
        jmp done
    heal_record_guard:
        movzx eax, byte ptr [esi+0x1CD4]
        cmp eax, dword ptr [edi]
        jne heal_guard_fail
        movzx eax, byte ptr [esi+0x1CE1]
        cmp eax, dword ptr [edi+20]
        jne heal_guard_fail
        movzx eax, byte ptr [esi+0x1CEC]
        cmp eax, dword ptr [edi+8]
        jne heal_guard_fail
        mov eax, dword ptr [esi+0x1C40]
        cmp eax, dword ptr [edi+4]
        jne heal_guard_fail
        jmp heal_guard_common
    heal_record_guard_evolving:
        movzx eax, byte ptr [esi+0x1CD4]
        cmp eax, dword ptr [edi]
        jne heal_guard_fail
        movzx eax, byte ptr [esi+0x1CE1]
        cmp eax, dword ptr [edi+20]
        jne heal_guard_fail
        movzx eax, byte ptr [esi+0x1CEC]
        cmp eax, dword ptr [edi+8]
        jne heal_guard_fail
        mov eax, dword ptr [edi+4]
        cmp eax, 100
        jae heal_guard_health_original
        mov eax, 100
    heal_guard_health_original:
        cmp dword ptr [esi+0x1C40], eax
        jne heal_guard_fail
    heal_guard_common:
        movzx eax, byte ptr [esi+0x1CEC]
        cmp eax, dword ptr [edi+8]
        jne heal_guard_fail
        movzx eax, byte ptr [esi+0x1CE1]
        cmp eax, dword ptr [edi+20]
        jne heal_guard_fail
        movzx eax, byte ptr [esi+0x1C48]
        cmp eax, dword ptr [edi+12]
        jne heal_guard_fail
        mov eax, dword ptr [esi+0x1CFC]
        cmp eax, dword ptr [edi+16]
        jne heal_guard_fail
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x10]
        jne heal_guard_fail
        mov eax, dword ptr [ebp-0x14]
        add eax, dword ptr [ebp-0x24]
        cmp dword ptr [0x51D368], eax
        jne heal_guard_fail
        mov eax, 1
        ret
    heal_guard_fail:
        xor eax, eax
        ret
    unsupported:
        {status_call(page_va, '4', 13)}
        jmp done
    no_change:
        {status_call(page_va, '4', 1)}
        jmp done
    insufficient:
        {status_call(page_va, '4', 3)}
        jmp done
    cancelled:
        {status_call(page_va, '4', 4)}
        jmp done
    recheck:
        {status_call(page_va, '4', 5)}
        jmp done
    retained:
        cmp dword ptr [ebp-0x20], 0
        jne retained_status
        {status_call(page_va, '4', 5)}
        jmp done
    retained_status:
        {status_call(page_va, '4', 6, 'dword ptr [ebp-0x24]', '0')}
        jmp done
    charge_unknown:
        {status_call(page_va, '4', 7, 'dword ptr [ebp-0x18]', 'dword ptr [ebp-0x1C]')}
    done:
        add esp, 0x1000
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """)
    return put(page, page_va, "heal", f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x20
        mov dword ptr [ebp-0x18], 0
        mov dword ptr [ebp-0x1C], 0
        mov esi, 0x554190
        mov ebx, {BOUND}
    count_loop:
        cmp byte ptr [esi+0x1CD4], 0
        je count_next
        cmp byte ptr [esi+0x1CE1], 0
        jne count_next
        cmp byte ptr [esi+0x1CEC], 0
        jne count_next
        cmp dword ptr [esi+0x1C40], 0
        jle count_next
        cmp byte ptr [esi+0x1C48], 0
        je count_health
        cmp dword ptr [esi+0x1CFC], 12
        je unsupported
        inc dword ptr [ebp-0x18]
    count_health:
        cmp dword ptr [esi+0x1C40], 100
        jae count_next
        inc dword ptr [ebp-0x1C]
    count_next:
        add esi, {STRIDE}
        dec ebx
        jne count_loop
        mov eax, dword ptr [ebp-0x18]
        or eax, dword ptr [ebp-0x1C]
        jz no_change
        mov eax, dword ptr [0x51D5F8]
        mov dword ptr [ebp-0x10], eax
        cmp eax, 30000
        jb insufficient
        push dword ptr [ebp-0x1C]
        push dword ptr [ebp-0x18]
        push 4
        call 0x{page_va + OFF['confirm']:X}
        cmp eax, 1
        jne cancelled
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x10]
        jne recheck
        cmp eax, 30000
        jb insufficient
        push -30000
        mov ecx, 0x51D5F8
        call 0x4237B0
        mov eax, dword ptr [ebp-0x10]
        sub eax, 30000
        cmp dword ptr [0x51D5F8], eax
        jne charge_unknown
        mov dword ptr [ebp-0x20], 0
        mov dword ptr [ebp-0x24], 0
        mov esi, 0x554190
        mov ebx, {BOUND}
    heal_loop:
        cmp byte ptr [esi+0x1CD4], 0
        je heal_next
        cmp byte ptr [esi+0x1CE1], 0
        jne heal_next
        cmp byte ptr [esi+0x1CEC], 0
        jne heal_next
        cmp dword ptr [esi+0x1C40], 0
        jle heal_next
        cmp dword ptr [esi+0x1C40], 100
        jae heal_sick
        push -1
        push 100
        lea ecx, [esi+0x1C34]
        call 0x4758B0
        inc dword ptr [ebp-0x24]
    heal_sick:
        cmp byte ptr [esi+0x1C48], 0
        je heal_next
        cmp dword ptr [esi+0x1CFC], 12
        je heal_next
        mov byte ptr [esi+0x1C48], 0
        inc dword ptr [0x51D368]
        inc dword ptr [ebp-0x20]
        push 1
        push 52
        mov ecx, 0x4DB358
        call 0x413450
        push 1
        push 53
        mov ecx, 0x4DB358
        call 0x413450
        push 1
        push 54
        mov ecx, 0x4DB358
        call 0x413450
    heal_next:
        add esi, {STRIDE}
        dec ebx
        jne heal_loop
        {status_call(page_va, '4', 0, 'dword ptr [ebp-0x20]', 'dword ptr [ebp-0x24]')}
        jmp done
    no_change:
        {status_call(page_va, '4', 1)}
        jmp done
    insufficient:
        {status_call(page_va, '4', 3)}
        jmp done
    cancelled:
        {status_call(page_va, '4', 4)}
        jmp done
    recheck:
        {status_call(page_va, '4', 5)}
        jmp done
    unsupported:
        {status_call(page_va, '4', 13)}
        jmp done
    charge_unknown:
        {status_call(page_va, '4', 7)}
    done:
        add esp, 0x20
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """)

def build_time_warp(page: bytearray, page_va: int, s: dict[str, int]) -> bytes:
    """Village-clock Time Warp: advance exactly three displayed villager years
    at any speed for one verified 50,000 tech-point charge. Self-contained
    (inline MessageBoxA via the page's existing import thunks); no companion
    DLL change. Ported from the statically-reviewed dispatcher in
    build_expanded_time_warp.py as a ret-terminated subroutine so tech_menu can
    call it for command 0."""
    return put(page, page_va, "time_warp", f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x50
        mov dword ptr [ebp-0x10], 0
        mov dword ptr [ebp-0x14], 0
        push 0x{s['dll']:X}
        call dword ptr [0x4951E0]
        test eax, eax
        jz unavailable
        push 0x{s['tw_get']:X}
        push eax
        call dword ptr [0x4951DC]
        test eax, eax
        jz unavailable
        mov dword ptr [ebp-0x10], eax
        push 0x{s['tw_user32']:X}
        call dword ptr [0x4951E0]
        test eax, eax
        jz unavailable
        push 0x{s['tw_messagebox']:X}
        push eax
        call dword ptr [0x4951DC]
        test eax, eax
        jz unavailable
        mov dword ptr [ebp-0x14], eax
        call 0x425950
        test eax, eax
        jz unavailable
        mov edi, eax
        mov eax, dword ptr [edi+0x17D7C]
        test eax, eax
        jle unavailable
        cmp eax, 999
        je paused
        mov dword ptr [ebp-0x1C], eax
        mov dword ptr [ebp-0x18], edi
        mov eax, dword ptr [0x51D5F8]
        mov dword ptr [ebp-0x20], eax
        cmp eax, 50000
        jb insufficient
        mov eax, dword ptr [0x4C6250]
        mov dword ptr [ebp-0x24], eax
        mov eax, dword ptr [0x4C6254]
        mov dword ptr [ebp-0x28], eax
        mov eax, 0x{s['tw_warning']:X}
        mov edx, 1
        call show_message
        cmp eax, 1
        jne cancelled
        call 0x425950
        cmp eax, dword ptr [ebp-0x18]
        jne recheck
        mov edi, eax
        mov eax, dword ptr [edi+0x17D7C]
        test eax, eax
        jle recheck
        cmp eax, 999
        je recheck
        cmp eax, dword ptr [ebp-0x1C]
        jne recheck
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x20]
        jne recheck
        cmp eax, 50000
        jb insufficient
        mov eax, dword ptr [0x4C6250]
        cmp eax, dword ptr [ebp-0x24]
        jne recheck
        mov eax, dword ptr [0x4C6254]
        cmp eax, dword ptr [ebp-0x28]
        jne recheck
        push -50000
        mov ecx, 0x51D5F8
        call 0x4237B0
        mov eax, dword ptr [ebp-0x20]
        sub eax, 50000
        mov dword ptr [ebp-0x2C], eax
        cmp dword ptr [0x51D5F8], eax
        jne charge_unknown
        mov eax, 129600
        xor edx, edx
        div dword ptr [ebp-0x1C]
        mov dword ptr [ebp-0x30], eax
        mov ecx, dword ptr [ebp-0x24]
        mov edx, dword ptr [ebp-0x28]
        sub ecx, eax
        sbb edx, 0
        mov dword ptr [ebp-0x34], ecx
        mov dword ptr [ebp-0x38], edx
        sub dword ptr [0x4C6250], eax
        sbb dword ptr [0x4C6254], 0
        cmp dword ptr [0x4C6250], ecx
        jne clock_unknown
        cmp dword ptr [0x4C6254], edx
        jne clock_unknown
        mov eax, 0x{s['tw_success']:X}
        mov edx, 0x40
        call show_message
        jmp done
    paused:
        mov eax, 0x{s['tw_paused']:X}
        jmp warning_status
    insufficient:
        mov eax, 0x{s['tw_insufficient']:X}
        jmp warning_status
    cancelled:
        mov eax, 0x{s['tw_cancelled']:X}
        jmp warning_status
    recheck:
        mov eax, 0x{s['tw_recheck']:X}
        jmp warning_status
    unavailable:
        mov eax, 0x{s['tw_unavailable']:X}
        jmp warning_status
    charge_unknown:
        mov eax, 0x{s['tw_charge_unknown']:X}
        jmp warning_status
    clock_unknown:
        mov eax, 0x{s['tw_clock_unknown']:X}
    warning_status:
        mov edx, 0x30
        call show_message
    done:
        add esp, 0x50
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    show_message:
        mov dword ptr [ebp-0x3C], eax
        mov dword ptr [ebp-0x40], edx
        cmp dword ptr [ebp-0x10], 0
        je message_unavailable
        cmp dword ptr [ebp-0x14], 0
        je message_unavailable
        call dword ptr [ebp-0x10]
        test eax, eax
        jz message_unavailable
        push dword ptr [ebp-0x40]
        push 0x{s['tw_title']:X}
        push dword ptr [ebp-0x3C]
        push eax
        call dword ptr [ebp-0x14]
        ret
    message_unavailable:
        xor eax, eax
        ret
    """)


def build_island(page: bytearray, page_va: int, s: dict[str, int]) -> bytes:
    """Island Event: for one verified 30,000 tech-point charge, make the
    next-event timer due (manager+0x17D3C = 0) so the native scheduler runs a
    random island event. Self-contained inline MessageBoxA (no companion DLL
    change); modeled on build_time_warp minus the clock math."""
    return put(page, page_va, "island", f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x50
        mov dword ptr [ebp-0x10], 0
        mov dword ptr [ebp-0x14], 0
        push 0x{s['dll']:X}
        call dword ptr [0x4951E0]
        test eax, eax
        jz unavailable
        push 0x{s['tw_get']:X}
        push eax
        call dword ptr [0x4951DC]
        test eax, eax
        jz unavailable
        mov dword ptr [ebp-0x10], eax
        push 0x{s['tw_user32']:X}
        call dword ptr [0x4951E0]
        test eax, eax
        jz unavailable
        push 0x{s['tw_messagebox']:X}
        push eax
        call dword ptr [0x4951DC]
        test eax, eax
        jz unavailable
        mov dword ptr [ebp-0x14], eax
        call 0x425950
        test eax, eax
        jz unavailable
        mov edi, eax
        mov dword ptr [ebp-0x18], edi
        mov eax, dword ptr [0x51D5F8]
        mov dword ptr [ebp-0x20], eax
        cmp eax, 30000
        jb insufficient
        mov eax, 0x{s['iv_warning']:X}
        mov edx, 1
        call show_message
        cmp eax, 1
        jne cancelled
        call 0x425950
        cmp eax, dword ptr [ebp-0x18]
        jne recheck
        mov edi, eax
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x20]
        jne recheck
        cmp eax, 30000
        jb insufficient
        push -30000
        mov ecx, 0x51D5F8
        call 0x4237B0
        mov eax, dword ptr [ebp-0x20]
        sub eax, 30000
        cmp dword ptr [0x51D5F8], eax
        jne charge_unknown
        mov dword ptr [edi+0x17D3C], 0
        cmp dword ptr [edi+0x17D3C], 0
        jne queue_unknown
        mov eax, 0x{s['iv_success']:X}
        mov edx, 0x40
        call show_message
        jmp done
    insufficient:
        mov eax, 0x{s['tw_insufficient']:X}
        jmp warning_status
    cancelled:
        mov eax, 0x{s['iv_cancelled']:X}
        jmp warning_status
    recheck:
        mov eax, 0x{s['iv_recheck']:X}
        jmp warning_status
    unavailable:
        mov eax, 0x{s['iv_unavailable']:X}
        jmp warning_status
    charge_unknown:
        mov eax, 0x{s['iv_charge_unknown']:X}
        jmp warning_status
    queue_unknown:
        mov eax, 0x{s['iv_queue_unknown']:X}
    warning_status:
        mov edx, 0x30
        call show_message
    done:
        add esp, 0x50
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    show_message:
        mov dword ptr [ebp-0x3C], eax
        mov dword ptr [ebp-0x40], edx
        cmp dword ptr [ebp-0x10], 0
        je message_unavailable
        cmp dword ptr [ebp-0x14], 0
        je message_unavailable
        call dword ptr [ebp-0x10]
        test eax, eax
        jz message_unavailable
        push dword ptr [ebp-0x40]
        push 0x{s['tw_title']:X}
        push dword ptr [ebp-0x3C]
        push eax
        call dword ptr [ebp-0x14]
        ret
    message_unavailable:
        xor eax, eax
        ret
    """)


def build_barrel(page: bytearray, page_va: int, s: dict[str, int]) -> bytes:
    """Barrel of Babies (VV2 general approach): for one verified 75,000
    tech-point charge, set only the one-shot pending token (bit 3 = value 8 at
    0x51D388). The event scheduler is deliberately not armed while the Upgrades
    menu is open. The origins-base Tech-screen handler routes stock command 0
    (Technologies screen close) to barrel_close_arm, which consumes the token,
    sets the forced-Barrel marker (bit 2 = value 4), and makes the next village
    event due, so the native index-25 Barrel event (its three-child spawn) is
    presented by the main-village owner only after the screen closes -- never
    under the menu. The origins-base selector detour at 0x41890F (preserved in
    this payload) forces the chosen index to 25 and clears the marker. Before any
    charge, both capacity checks call the game's own per-villager cap gate 0x472bd0
    -- which each population mode patches to its live cap (stock 105, collection
    150, immediate-fixed 150, expanded-256 256) via the 0x72C49/0x94500 helper --
    so the room test is fully mode-dynamic and the purchase is refused with no
    deduction when the village is at its cap. Self-contained MessageBoxA; the
    Island Event upgrade is untouched."""
    return put(page, page_va, "barrel", f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x50
        mov dword ptr [ebp-0x10], 0
        mov dword ptr [ebp-0x14], 0
        push 0x{s['dll']:X}
        call dword ptr [0x4951E0]
        test eax, eax
        jz unavailable
        push 0x{s['tw_get']:X}
        push eax
        call dword ptr [0x4951DC]
        test eax, eax
        jz unavailable
        mov dword ptr [ebp-0x10], eax
        push 0x{s['tw_user32']:X}
        call dword ptr [0x4951E0]
        test eax, eax
        jz unavailable
        push 0x{s['tw_messagebox']:X}
        push eax
        call dword ptr [0x4951DC]
        test eax, eax
        jz unavailable
        mov dword ptr [ebp-0x14], eax
        call 0x425950
        test eax, eax
        jz unavailable
        mov edi, eax
        mov dword ptr [ebp-0x18], edi
        call 0x472BD0
        test al, al
        jz full
        mov eax, dword ptr [0x51D5F8]
        mov dword ptr [ebp-0x20], eax
        cmp eax, 75000
        jb insufficient
        mov eax, 0x{s['bb_warning']:X}
        mov edx, 1
        call show_message
        cmp eax, 1
        jne cancelled
        call 0x425950
        cmp eax, dword ptr [ebp-0x18]
        jne recheck
        mov edi, eax
        call 0x472BD0
        test al, al
        jz full
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x20]
        jne recheck
        cmp eax, 75000
        jb insufficient
        push -75000
        mov ecx, 0x51D5F8
        call 0x4237B0
        mov eax, dword ptr [ebp-0x20]
        sub eax, 75000
        cmp dword ptr [0x51D5F8], eax
        jne charge_unknown
        or dword ptr [0x51D388], 8
        test dword ptr [0x51D388], 8
        jz queue_unknown
        mov eax, 0x{s['bb_success']:X}
        mov edx, 0x40
        call show_message
        jmp done
    full:
        mov eax, 0x{s['bb_full']:X}
        jmp warning_status
    insufficient:
        mov eax, 0x{s['tw_insufficient']:X}
        jmp warning_status
    cancelled:
        mov eax, 0x{s['bb_cancelled']:X}
        jmp warning_status
    recheck:
        mov eax, 0x{s['bb_recheck']:X}
        jmp warning_status
    unavailable:
        mov eax, 0x{s['bb_unavailable']:X}
        jmp warning_status
    charge_unknown:
        mov eax, 0x{s['bb_charge_unknown']:X}
        jmp warning_status
    queue_unknown:
        mov eax, 0x{s['bb_queue_unknown']:X}
    warning_status:
        mov edx, 0x30
        call show_message
    done:
        add esp, 0x50
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    show_message:
        mov dword ptr [ebp-0x3C], eax
        mov dword ptr [ebp-0x40], edx
        cmp dword ptr [ebp-0x10], 0
        je message_unavailable
        cmp dword ptr [ebp-0x14], 0
        je message_unavailable
        call dword ptr [ebp-0x10]
        test eax, eax
        jz message_unavailable
        push dword ptr [ebp-0x40]
        push 0x{s['tw_title']:X}
        push dword ptr [ebp-0x3C]
        push eax
        call dword ptr [ebp-0x14]
        ret
    message_unavailable:
        xor eax, eax
        ret
    """)


def build_appearance(page: bytearray, page_va: int, s: dict[str, int]) -> bytes:
    """Change Appearance (per-villager). Resolve the selected villager, enforce
    the believer/active/living gate (shared `eligible` helper), require 5,000
    tech points, then open the companion DLL's ShowAppearanceChooser, passing
    the villager's sex (record+0x1B90) and age (record+0x1B8C) and pointers to
    local copies of the head (0..29) and body (0..28) indices. The chooser shows
    the stock head/body sprites with arrows and, on OK (return 1), reports the
    chosen indices back through the pointers -- it never touches the record. On
    OK this router re-checks eligibility and funds, writes the chosen indices
    into record+0x1BB8/+0x1BBC, and charges exactly 5,000 once. If the chosen
    head differs from the original, it first shows the companion DLL's
    ShowVV5Task9GeneticsWarning (OK/Cancel); Cancel backs out with no write and
    no charge. Cancel changes nothing silently; an OK with an unchanged
    selection changes nothing, charges nothing, and reports RESULT 15 (the
    "appearance is unchanged" line)."""
    return put(page, page_va, "appearance", f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x50
        push 0x{s['dll']:X}
        call dword ptr [0x4951E0]
        test eax, eax
        jz invalid
        mov ebx, eax
        push 0x{s['appearance_export']:X}
        push ebx
        call dword ptr [0x4951DC]
        test eax, eax
        jz invalid
        mov dword ptr [ebp-0x10], eax
        push 0x{s['genetics_export']:X}
        push ebx
        call dword ptr [0x4951DC]
        mov dword ptr [ebp-0x34], eax
        call 0x{page_va + OFF['resolve_current']:X}
        test eax, eax
        jz invalid
        mov dword ptr [ebp-0x18], eax
        push eax
        call 0x{page_va + OFF['eligible']:X}
        test eax, eax
        jz invalid
        mov esi, dword ptr [ebp-0x18]
        mov eax, dword ptr [esi+0x1BB8]
        mov dword ptr [ebp-0x1C], eax
        mov dword ptr [ebp-0x2C], eax
        mov eax, dword ptr [esi+0x1BBC]
        mov dword ptr [ebp-0x20], eax
        mov dword ptr [ebp-0x30], eax
        call 0x{page_va + OFF['mask_get']:X}
        mov dword ptr [ebp-0x24], eax
        mov dword ptr [ebp-0x14], eax
        mov eax, dword ptr [0x51D5F8]
        cmp eax, 5000
        jb insufficient
        push 0
        push 0
        push 5
        call 0x{page_va + OFF['confirm']:X}
        cmp eax, 1
        jne cancelled
        mov esi, dword ptr [ebp-0x18]
        lea eax, [ebp-0x24]
        push eax
        lea eax, [ebp-0x20]
        push eax
        lea eax, [ebp-0x1C]
        push eax
        mov eax, dword ptr [esi+0x1B8C]
        push eax
        mov eax, dword ptr [esi+0x1B90]
        push eax
        call dword ptr [ebp-0x10]
        cmp eax, 1
        jne cancelled
        mov eax, dword ptr [ebp-0x1C]
        cmp eax, dword ptr [ebp-0x2C]
        jne head_changed
        mov eax, dword ptr [ebp-0x20]
        cmp eax, dword ptr [ebp-0x30]
        jne appearance_changed
        mov eax, dword ptr [ebp-0x24]
        cmp eax, dword ptr [ebp-0x14]
        je no_change
        jmp appearance_changed
    head_changed:
        mov eax, dword ptr [ebp-0x34]
        test eax, eax
        jz appearance_changed
        call eax
        cmp eax, 1
        jne cancelled
    appearance_changed:
        mov esi, dword ptr [ebp-0x18]
        push esi
        call 0x{page_va + OFF['eligible']:X}
        test eax, eax
        jz recheck
        mov eax, dword ptr [0x51D5F8]
        cmp eax, 5000
        jb insufficient
        mov esi, dword ptr [ebp-0x18]
        mov eax, dword ptr [ebp-0x1C]
        mov dword ptr [esi+0x1BB8], eax
        mov eax, dword ptr [ebp-0x20]
        mov dword ptr [esi+0x1BBC], eax
        mov eax, dword ptr [ebp-0x24]
        push ebx
        mov ebx, eax
        call 0x{page_va + OFF['mask_set']:X}
        pop ebx
        push 0x{s['writemask_export']:X}
        push ebx
        call dword ptr [0x4951DC]
        test eax, eax
        jz ws_skip
        push 0x{MASK_TABLE:X}
        call eax
    ws_skip:
        mov eax, dword ptr [0x51D5F8]
        mov dword ptr [ebp-0x28], eax
        push -5000
        mov ecx, 0x51D5F8
        call 0x4237B0
        mov eax, dword ptr [ebp-0x28]
        sub eax, 5000
        cmp dword ptr [0x51D5F8], eax
        jne charge_unknown
        jmp done
    no_change:
        {status_call(page_va, '5', 15)}
        jmp done
    insufficient:
        {status_call(page_va, '5', 3)}
        jmp done
    invalid:
        {status_call(page_va, '5', 2)}
        jmp done
    cancelled:
        jmp done
    recheck:
        {status_call(page_va, '5', 5)}
        jmp done
    charge_unknown:
        {status_call(page_va, '5', 7)}
    done:
        add esp, 0x50
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """)


def build_barrel_close_arm(page: bytearray, page_va: int) -> bytes:
    """Barrel of Babies deferral (VV2 general approach). Installed only in stock
    layouts as a five-byte detour over the tech-screen close handler's
    `mov ecx, 0x51F440` at 0x441617 (stock command 0 = Technologies screen
    close). When the Barrel purchase token (bit 3 = value 8 at 0x51D388) is set,
    this consumes it, arms the forced-Barrel selector marker (bit 2 = value 4),
    and makes the next village event due ([manager+0x17D3C]=0 via 0x425950), so
    the native index-25 Barrel event (its three-child spawn) is presented by the
    main-village owner only after the screen closes -- never under the Upgrades
    menu. All registers are preserved (pushad/popad); the routine then replays
    the exact overwritten instruction and returns to 0x44161C. With no token
    pending it is a register-clean passthrough, so ordinary tech-screen closes
    are byte-for-byte native. The origins-base selector detour at 0x41890F then
    forces the chosen event index to 25 and clears the marker."""
    return put(page, page_va, "barrel_close_arm", """
        pushad
        test dword ptr [0x51D388], 8
        jz arm_done
        and dword ptr [0x51D388], 0xFFFFFFF7
        or dword ptr [0x51D388], 4
        call 0x425950
        test eax, eax
        jz arm_done
        mov dword ptr [eax+0x17D3C], 0
    arm_done:
        popad
        mov ecx, 0x51F440
        jmp 0x44161C
    """)


def build_complete_collections(page: bytearray, page_va: int) -> bytes:
    """Complete all Collections (village-wide, 1,000,000 tech points). Covers the
    two collectible sets -- Relics (slots 0x68..0x7F, stat 0xE) and Science Items
    (slots 0x50..0x67, stat 0xF), 48 items total. For every slot not yet found it
    marks the found-flag in the collectible manager (0x4DBFC8 + item*4 + 0x630),
    then deterministically *earns* each set's trophy by driving its native
    statistic across the completion threshold: the statistic record lives at
    0x4DB358 + id*12 (byte0 = earned/locked flag, +4 = value, +8 = handle) and the
    completion threshold is 24 (table 0x4C6544). When a set is not already earned
    we force its value to 23 and call the game's own stat writer 0x413450
    (ECX=0x4DB358, id, +1) so the value crosses 24; that fires the native earn
    cascade 0x4133f0 -- it sets byte0, queues the on-screen "Trophy earned" popup
    (pending list at 0x4DB670) and bumps the Master Collector counter (stat 0x10,
    threshold 2), which auto-earns once both sets are done. We then raise the
    native "collection completed" toasts 0x2FF (relics) / 0x300 (science) / 0x301
    (all) through the message manager 0x520220 -> 0x44E730 (self-deduping). Driving
    the real stat writer (rather than poking byte0) is what makes the star fill,
    the popup show, and Master Collector count -- filling the bar value alone does
    not earn. Charges one verified 1,000,000 deduction after the shared confirm."""
    return put(page, page_va, "complete_collections", f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x20
        mov eax, dword ptr [0x51D5F8]
        mov dword ptr [ebp-0x10], eax
        cmp eax, 1000000
        jb insufficient
        push 0
        push 0
        push 16
        call 0x{page_va + OFF['confirm']:X}
        cmp eax, 1
        jne cancelled
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x10]
        jne recheck
        cmp eax, 1000000
        jb insufficient
        mov dword ptr [ebp-0x14], 0
        mov dword ptr [ebp-0x18], 0
        mov dword ptr [ebp-0x1C], 0
        movzx eax, byte ptr [0x4DB418]
        mov dword ptr [ebp-0x20], eax
        mov edi, 0x4DBFC8
        mov esi, 0x50
    grant_loop:
        cmp dword ptr [edi+esi*4+0x630], 0
        jne grant_next
        mov dword ptr [edi+esi*4+0x630], 1
        inc dword ptr [ebp-0x14]
        mov dword ptr [ebp-0x18], 1
    grant_next:
        inc esi
        cmp esi, 0x80
        jl grant_loop
        cmp byte ptr [0x4DB400], 0
        jne earn_science
        mov dword ptr [ebp-0x18], 1
        mov dword ptr [0x4DB404], 23
        push 1
        push 0xE
        mov ecx, 0x4DB358
        call 0x413450
        inc dword ptr [ebp-0x1C]
    earn_science:
        cmp byte ptr [0x4DB40C], 0
        jne earn_master_count
        mov dword ptr [ebp-0x18], 1
        mov dword ptr [0x4DB410], 23
        push 1
        push 0xF
        mov ecx, 0x4DB358
        call 0x413450
        inc dword ptr [ebp-0x1C]
    earn_master_count:
        movzx eax, byte ptr [0x4DB418]
        cmp eax, dword ptr [ebp-0x20]
        je after_earn
        inc dword ptr [ebp-0x1C]
    after_earn:
        cmp dword ptr [ebp-0x18], 0
        je no_change
        push 0
        push 0
        push 0x2FF
        mov ecx, 0x520220
        call 0x44E730
        push 0
        push 0
        push 0x300
        mov ecx, 0x520220
        call 0x44E730
        push 0
        push 0
        push 0x301
        mov ecx, 0x520220
        call 0x44E730
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x10]
        jne charge_unknown
        push -1000000
        mov ecx, 0x51D5F8
        call 0x4237B0
        mov eax, dword ptr [ebp-0x10]
        sub eax, 1000000
        cmp dword ptr [0x51D5F8], eax
        jne charge_unknown
        {status_call(page_va, '16', 0, 'dword ptr [ebp-0x14]', 'dword ptr [ebp-0x1C]')}
        jmp done
    no_change:
        {status_call(page_va, '16', 1)}
        jmp done
    insufficient:
        {status_call(page_va, '16', 3)}
        jmp done
    cancelled:
        {status_call(page_va, '16', 4)}
        jmp done
    recheck:
        {status_call(page_va, '16', 5)}
        jmp done
    charge_unknown:
        {status_call(page_va, '16', 7)}
    done:
        add esp, 0x20
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """)


def build_reset_collections(page: bytearray, page_va: int) -> bytes:
    """Reset all Collections (village-wide, 1,000,000 tech points). Reverses only
    the collection-exclusive state for the two sets (slots 0x50..0x7F, 48 items):
    clears every found-flag (0x4DBFC8 + item*4 + 0x630) and un-earns the three
    collection trophies by zeroing their statistic records at 0x4DB358 + id*12 --
    Relics (0xE, record 0x4DB400), Science Items (0xF, record 0x4DB40C) and Master
    Collector (0x10, record 0x4DB418) -- writing byte0 (earned flag), +4 (value)
    and +8 (handle) all to zero so the star empties and the counter drops. It then
    re-arms the completion toasts by clearing their message "already-shown" latch
    (byte0 of 0x520220 + (id-0x29c)*32: 0x2FF->0x520E80, 0x300->0x520EA0,
    0x301->0x520EC0) so a later Complete re-shows them. These statistic ids and
    found-flags are collection-exclusive, so clearing them cannot disturb other
    progress; the shared meta counters (0x40/0x41) bumped by the earn cascade are
    left alone since they aggregate unrelated trophies too. Charges one verified
    1,000,000 deduction after the shared confirm."""
    return put(page, page_va, "reset_collections", f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x20
        mov eax, dword ptr [0x51D5F8]
        mov dword ptr [ebp-0x10], eax
        cmp eax, 1000000
        jb insufficient
        push 0
        push 0
        push 17
        call 0x{page_va + OFF['confirm']:X}
        cmp eax, 1
        jne cancelled
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x10]
        jne recheck
        cmp eax, 1000000
        jb insufficient
        mov dword ptr [ebp-0x14], 0
        mov dword ptr [ebp-0x18], 0
        mov edi, 0x4DBFC8
        mov esi, 0x50
    clear_loop:
        cmp dword ptr [edi+esi*4+0x630], 0
        je clear_next
        mov dword ptr [edi+esi*4+0x630], 0
        inc dword ptr [ebp-0x14]
        mov dword ptr [ebp-0x18], 1
    clear_next:
        inc esi
        cmp esi, 0x80
        jl clear_loop
        cmp byte ptr [0x4DB400], 0
        jne mark_change
        cmp byte ptr [0x4DB40C], 0
        jne mark_change
        cmp byte ptr [0x4DB418], 0
        jne mark_change
        jmp after_change
    mark_change:
        mov dword ptr [ebp-0x18], 1
    after_change:
        cmp dword ptr [ebp-0x18], 0
        je no_change
        mov byte ptr [0x4DB400], 0
        mov dword ptr [0x4DB404], 0
        mov dword ptr [0x4DB408], 0
        mov byte ptr [0x4DB40C], 0
        mov dword ptr [0x4DB410], 0
        mov dword ptr [0x4DB414], 0
        mov byte ptr [0x4DB418], 0
        mov dword ptr [0x4DB41C], 0
        mov dword ptr [0x4DB420], 0
        mov byte ptr [0x520E80], 0
        mov byte ptr [0x520EA0], 0
        mov byte ptr [0x520EC0], 0
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x10]
        jne charge_unknown
        push -1000000
        mov ecx, 0x51D5F8
        call 0x4237B0
        mov eax, dword ptr [ebp-0x10]
        sub eax, 1000000
        cmp dword ptr [0x51D5F8], eax
        jne charge_unknown
        {status_call(page_va, '17', 0, 'dword ptr [ebp-0x14]')}
        jmp done
    no_change:
        {status_call(page_va, '17', 1)}
        jmp done
    insufficient:
        {status_call(page_va, '17', 3)}
        jmp done
    cancelled:
        {status_call(page_va, '17', 4)}
        jmp done
    recheck:
        {status_call(page_va, '17', 5)}
        jmp done
    charge_unknown:
        {status_call(page_va, '17', 7)}
    done:
        add esp, 0x20
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """)


def build_running_all(page: bytearray, page_va: int) -> bytes:
    """Grant Running to All Villagers (village-wide, 150,000 tech points). Walks
    all 150 villager records (0x554190 + i*STRIDE), acts only on eligible living
    Believers (active +0x1CD4, Heathen mask +0x1CE1 == 0, faction +0x1CEC == 0,
    signed health +0x1C40 > 0 -- never masked Heathens), and applies the native
    Running preference (id 38): membership 0x464F90, insert into the likes array
    0x464AD0, remove from the dislikes array 0x4649E0. Counts four outcomes and
    reports them via two 16-bit-packed amounts. Charges one verified 150,000
    deduction after the shared confirm."""
    return put(page, page_va, "running_all", f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x40
        mov dword ptr [ebp-0x10], 0
        mov dword ptr [ebp-0x14], 0
        mov dword ptr [ebp-0x18], 0
        mov dword ptr [ebp-0x1C], 0
        mov eax, dword ptr [0x51D5F8]
        mov dword ptr [ebp-0x20], eax
        cmp eax, 1000000
        jb insufficient
        push 0
        push 0
        push 20
        call 0x{page_va + OFF['confirm']:X}
        cmp eax, 1
        jne cancelled
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x20]
        jne recheck
        cmp eax, 1000000
        jb insufficient
        mov esi, 0x554190
        mov ebx, {BOUND}
    run_loop:
        cmp byte ptr [esi+0x1CD4], 0
        je run_next
        cmp byte ptr [esi+0x1CE1], 0
        jne run_next
        cmp byte ptr [esi+0x1CEC], 0
        jne run_next
        cmp dword ptr [esi+0x1C40], 0
        jle run_next
        push 38
        lea ecx, [esi+0x1F5C]
        call 0x464F90
        test al, al
        jnz run_already
        cmp dword ptr [esi+0x1F5C], -1
        je run_grant
        cmp dword ptr [esi+0x1F60], -1
        je run_grant
        cmp dword ptr [esi+0x1F64], -1
        je run_grant
        inc dword ptr [ebp-0x14]
        jmp run_next
    run_grant:
        push 38
        lea ecx, [esi+0x1F5C]
        call 0x464AD0
        inc dword ptr [ebp-0x18]
        cmp dword ptr [esi+0x1F68], 38
        je run_remove
        cmp dword ptr [esi+0x1F6C], 38
        je run_remove
        cmp dword ptr [esi+0x1F70], 38
        je run_remove
        jmp run_next
    run_remove:
        push 38
        lea ecx, [esi+0x1F68]
        call 0x4649E0
        inc dword ptr [ebp-0x1C]
        jmp run_next
    run_already:
        inc dword ptr [ebp-0x10]
    run_next:
        add esi, {STRIDE}
        dec ebx
        jnz run_loop
        mov eax, dword ptr [ebp-0x18]
        or eax, dword ptr [ebp-0x1C]
        jz no_change
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x20]
        jne charge_unknown
        push -1000000
        mov ecx, 0x51D5F8
        call 0x4237B0
        mov eax, dword ptr [ebp-0x20]
        sub eax, 1000000
        cmp dword ptr [0x51D5F8], eax
        jne charge_unknown
        mov eax, dword ptr [ebp-0x10]
        shl eax, 16
        or eax, dword ptr [ebp-0x14]
        mov dword ptr [ebp-0x24], eax
        mov eax, dword ptr [ebp-0x18]
        shl eax, 16
        or eax, dword ptr [ebp-0x1C]
        mov dword ptr [ebp-0x28], eax
        {status_call(page_va, '20', 0, 'dword ptr [ebp-0x24]', 'dword ptr [ebp-0x28]')}
        jmp done
    no_change:
        {status_call(page_va, '20', 1)}
        jmp done
    insufficient:
        {status_call(page_va, '20', 3)}
        jmp done
    cancelled:
        {status_call(page_va, '20', 4)}
        jmp done
    recheck:
        {status_call(page_va, '20', 5)}
        jmp done
    charge_unknown:
        {status_call(page_va, '20', 7)}
    done:
        add esp, 0x40
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """)


def build_mastery_all(page: bytearray, page_va: int) -> bytes:
    """Grant Full Mastery to All Villagers (village-wide, 300,000 tech points).
    Walks all 150 villager records, acts only on eligible living Believers (never
    masked Heathens), and for each of the six skills (+0x1C5C..+0x1C70) that is a
    finite value in [0, 100) raises it to exactly 100.0 (0x42C80000) through the
    native skill writer 0x475730 (push 100.0 - current, push index). Skills that
    are already >= 100, negative, infinite, or NaN are left untouched. A villager
    with at least one raised skill counts as granted; one with none counts as
    already fully mastered. Charges one verified 300,000 deduction after the
    shared confirm."""
    return put(page, page_va, "mastery_all", f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x30
        mov dword ptr [ebp-0x10], 0
        mov dword ptr [ebp-0x14], 0
        mov eax, dword ptr [0x51D5F8]
        mov dword ptr [ebp-0x18], eax
        cmp eax, 1000000
        jb insufficient
        push 0
        push 0
        push 21
        call 0x{page_va + OFF['confirm']:X}
        cmp eax, 1
        jne cancelled
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x18]
        jne recheck
        cmp eax, 1000000
        jb insufficient
        mov esi, 0x554190
        mov ebx, {BOUND}
    mas_loop:
        cmp byte ptr [esi+0x1CD4], 0
        je mas_next
        cmp byte ptr [esi+0x1CE1], 0
        jne mas_next
        cmp byte ptr [esi+0x1CEC], 0
        jne mas_next
        cmp dword ptr [esi+0x1C40], 0
        jle mas_next
        mov dword ptr [ebp-0x1C], 0
        xor edi, edi
    mas_skill:
        mov eax, dword ptr [esi+edi*4+0x1C5C]
        test eax, eax
        js mas_skill_next
        cmp eax, 0x42C80000
        jae mas_skill_next
        mov dword ptr [ebp-0x1C], 1
        push 0x42C80000
        fld dword ptr [esp]
        fsub dword ptr [esi+edi*4+0x1C5C]
        fstp dword ptr [esp]
        push edi
        lea ecx, [esi+0x1C5C]
        call 0x475730
    mas_skill_next:
        inc edi
        cmp edi, 6
        jb mas_skill
        cmp dword ptr [ebp-0x1C], 0
        je mas_already
        inc dword ptr [ebp-0x10]
        jmp mas_next
    mas_already:
        inc dword ptr [ebp-0x14]
    mas_next:
        add esi, {STRIDE}
        dec ebx
        jnz mas_loop
        cmp dword ptr [ebp-0x10], 0
        je no_change
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x18]
        jne charge_unknown
        push -1000000
        mov ecx, 0x51D5F8
        call 0x4237B0
        mov eax, dword ptr [ebp-0x18]
        sub eax, 1000000
        cmp dword ptr [0x51D5F8], eax
        jne charge_unknown
        {status_call(page_va, '21', 0, 'dword ptr [ebp-0x10]', 'dword ptr [ebp-0x14]')}
        jmp done
    no_change:
        {status_call(page_va, '21', 1)}
        jmp done
    insufficient:
        {status_call(page_va, '21', 3)}
        jmp done
    cancelled:
        {status_call(page_va, '21', 4)}
        jmp done
    recheck:
        {status_call(page_va, '21', 5)}
        jmp done
    charge_unknown:
        {status_call(page_va, '21', 7)}
    done:
        add esp, 0x30
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """)


def build_age18_all(page: bytearray, page_va: int) -> bytes:
    """Set all Villagers to 18 (village-wide, 200,000 tech points). Walks all 150
    villager records, acts only on eligible living Believers (never masked
    Heathens), and sets each villager's age to exactly 360 units (18 years)
    regardless of the current value: it applies the signed delta (360 - age)
    through the native age writer 0x46F7F0, mirroring the per-villager Set Age to
    18 -- the age at +0x1B8C is moved by the delta, the +0x1C3C companion field
    is shifted by the same delta, and +0x1C4C is shifted only when it is nonzero.
    Villagers already at exactly 360 are left untouched. Charges one verified
    200,000 deduction after the shared confirm; if no villager needed changing it
    deducts nothing."""
    return put(page, page_va, "age18_all", f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x30
        mov dword ptr [ebp-0x10], 0
        mov dword ptr [ebp-0x14], 0
        mov eax, dword ptr [0x51D5F8]
        mov dword ptr [ebp-0x18], eax
        cmp eax, 1000000
        jb insufficient
        push 0
        push 0
        push 22
        call 0x{page_va + OFF['confirm']:X}
        cmp eax, 1
        jne cancelled
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x18]
        jne recheck
        cmp eax, 1000000
        jb insufficient
        mov esi, 0x554190
        mov ebx, {BOUND}
    age_loop:
        cmp byte ptr [esi+0x1CD4], 0
        je age_next
        cmp byte ptr [esi+0x1CE1], 0
        jne age_next
        cmp byte ptr [esi+0x1CEC], 0
        jne age_next
        cmp dword ptr [esi+0x1C40], 0
        jle age_next
        mov eax, 360
        sub eax, dword ptr [esi+0x1B8C]
        jz age_already
        push eax
        lea ecx, [esi+0x1B8C]
        call 0x46F7F0
        inc dword ptr [ebp-0x10]
        jmp age_next
    age_already:
        inc dword ptr [ebp-0x14]
    age_next:
        add esi, {STRIDE}
        dec ebx
        jnz age_loop
        cmp dword ptr [ebp-0x10], 0
        je no_change
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x18]
        jne charge_unknown
        push -1000000
        mov ecx, 0x51D5F8
        call 0x4237B0
        mov eax, dword ptr [ebp-0x18]
        sub eax, 1000000
        cmp dword ptr [0x51D5F8], eax
        jne charge_unknown
        {status_call(page_va, '22', 0, 'dword ptr [ebp-0x10]', 'dword ptr [ebp-0x14]')}
        jmp done
    no_change:
        {status_call(page_va, '22', 1)}
        jmp done
    insufficient:
        {status_call(page_va, '22', 3)}
        jmp done
    cancelled:
        {status_call(page_va, '22', 4)}
        jmp done
    recheck:
        {status_call(page_va, '22', 5)}
        jmp done
    charge_unknown:
        {status_call(page_va, '22', 7)}
    done:
        add esp, 0x30
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """)


def build_division(
    page: bytearray, page_va: int, name: str, parenting: int, action: int
) -> bytes:
    """Equal Division of Labor (village-wide, 1,000,000 tech points). The whole
    round-robin assignment lives in the companion DLL export
    ApplyVV5EqualDivision(base, parenting): it walks all 150 villager records,
    acts only on eligible living Believers (never masked Heathens or off-faction
    villagers), assigns each one's job-preference index at +0x1C74 cyclically so
    the professions are split evenly (males and females cycle independently for a
    balanced split), and shows its own per-profession, per-sex result box because
    that breakdown does not fit ShowVV5Task9Result's two counts. `parenting`
    selects the 6-way cycle (Farming, Building, Research, Healing, Parenting,
    Devotion) or the 5-way cycle without Parenting. Preferences are overwritten
    unconditionally, so N is simply the eligible count. This native routine owns
    only the purchase gate: it confirms, re-checks the tech balance, calls the
    DLL, and charges one 1,000,000 deduction ONLY when the DLL reports a real
    change (return value 1); a 0 return (no eligible villagers, the DLL showed
    its own no-charge notice) or a -1 (companion unavailable) deducts nothing."""
    return put(page, page_va, name, f"""
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x30
        mov eax, dword ptr [0x51D5F8]
        mov dword ptr [ebp-0x18], eax
        cmp eax, 1000000
        jb insufficient
        push 0
        push 0
        push {action}
        call 0x{page_va + OFF['confirm']:X}
        cmp eax, 1
        jne cancelled
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x18]
        jne recheck
        cmp eax, 1000000
        jb insufficient
        push {parenting}
        push 0x554190
        call 0x{page_va + OFF['apply_division']:X}
        cmp eax, 1
        jne done
        mov eax, dword ptr [0x51D5F8]
        cmp eax, dword ptr [ebp-0x18]
        jne done
        push -1000000
        mov ecx, 0x51D5F8
        call 0x4237B0
        jmp done
        nop
        nop
        nop
    insufficient:
        {status_call(page_va, str(action), 3)}
        jmp done
    cancelled:
        {status_call(page_va, str(action), 4)}
        jmp done
    recheck:
        {status_call(page_va, str(action), 5)}
    done:
        add esp, 0x30
        pop edi
        pop esi
        pop ebx
        pop ebp
        ret
    """)


def build_mask_render(page: bytearray, page_va: int, s: dict[str, int]) -> dict[str, bytes]:
    """Heathen-mask cosmetic render (stock layouts only).

    Renders the mask chosen by the Change-Appearance picker (persistent choice in
    the nibble-packed side-table MASK_TABLE, keyed by villager record index,
    0=none / 1-5 = Blue/Orange/Red/Purple/Chief) on a Believer, by a transient
    faction flip bracketed to the head+mask draw of the per-villager render fn
    0x4720E0. The choice is read via mask_get (never the villager record). Three
    stock-only .text detours drive it:

      * mask_flip is entered from 0x472481 (just past the selection-ring block).
        For a Believer with a mask choice it saves the colour fields + villager
        pointer, sets the chosen colour, flips faction +0x1CEC to heathen, and
        marks a guard; the ring already drew with the real faction so it stays
        white. It replays the displaced `mov ecx,[esp+0xbc]` and returns.
      * mask_restore is entered from BOTH function epilogues (0x472B0F, 0x472B57
        = add esp,0xA8; ret 8). esi is popped by then, so it reverts faction +
        colours through the saved villager pointer, clears the guard, and runs
        the displaced epilogue. Non-masked villagers hit a guard-clear no-op.

    Scratch lives in free .data BSS 0x7B1D00 (guard / saved orange,red,colorfield
    / villager pointer), never in .text caves, so it never contends with the
    population, statistics, or other .text-cave features."""
    flip = put(page, page_va, "mask_flip", f"""
        push eax
        push edx
        cmp byte ptr [0x{MASK_LOADED:X}], 0
        jne mf_loaded
        call 0x{page_va + OFF['mask_load_once']:X}
    mf_loaded:
        call 0x{page_va + OFF['mask_get']:X}
        test eax, eax
        je mf_done
        cmp eax, 5
        ja mf_done
        cmp byte ptr [esi+0x1CEC], 0
        jne mf_done
        mov byte ptr [0x7B1D00], 1
        mov [0x7B1D10], esi
        movzx edx, byte ptr [esi+0x1CED]
        mov [0x7B1D04], edx
        movzx edx, byte ptr [esi+0x1CEE]
        mov [0x7B1D08], edx
        movzx edx, byte ptr [esi+0x1CFC]
        mov [0x7B1D0C], edx
        mov byte ptr [esi+0x1CED], 0
        mov byte ptr [esi+0x1CEE], 0
        mov byte ptr [esi+0x1CFC], 0
        cmp eax, 2
        je mf_orange
        cmp eax, 3
        je mf_red
        cmp eax, 4
        je mf_purple
        cmp eax, 5
        je mf_chief
        jmp mf_setf
    mf_orange:
        mov byte ptr [esi+0x1CED], 1
        jmp mf_setf
    mf_red:
        mov byte ptr [esi+0x1CEE], 1
        jmp mf_setf
    mf_purple:
        mov byte ptr [esi+0x1CFC], 12
        jmp mf_setf
    mf_chief:
        mov byte ptr [esi+0x1CFC], 13
    mf_setf:
        mov byte ptr [esi+0x1CEC], 1
    mf_done:
        pop edx
        pop eax
        mov ecx, [esp+0xBC]
        jmp 0x472488
    """)
    restore = put(page, page_va, "mask_restore", """
        cmp byte ptr [0x7B1D00], 0
        je mr_done
        push eax
        push edx
        mov eax, [0x7B1D10]
        mov byte ptr [eax+0x1CEC], 0
        mov edx, [0x7B1D04]
        mov byte ptr [eax+0x1CED], dl
        mov edx, [0x7B1D08]
        mov byte ptr [eax+0x1CEE], dl
        mov edx, [0x7B1D0C]
        mov byte ptr [eax+0x1CFC], dl
        mov byte ptr [0x7B1D00], 0
        pop edx
        pop eax
    mr_done:
        add esp, 0xA8
        ret 8
    """)
    # mask_get: esi = villager record -> eax = mask choice (0-5), 0 if none or
    # esi is not a valid record. Keyed by index = (esi-0x554190)/0x2F44, then a
    # nibble read from MASK_TABLE. Clobbers eax/ecx/edx; preserves esi.
    get = put(page, page_va, "mask_get", f"""
        mov eax, esi
        sub eax, 0x554190
        jb mg_none
        xor edx, edx
        mov ecx, 0x{STRIDE:X}
        div ecx
        test edx, edx
        jne mg_none
        cmp eax, {BOUND}
        jae mg_none
        mov ecx, eax
        shr eax, 1
        movzx eax, byte ptr [eax + 0x{MASK_TABLE:X}]
        test cl, 1
        je mg_low
        shr eax, 4
        ret
    mg_low:
        and eax, 0x0F
        ret
    mg_none:
        xor eax, eax
        ret
    """)
    # mask_set: esi = villager record, bl = choice (0-5) -> writes the villager's
    # nibble in MASK_TABLE. No-op if esi is not a valid record. Clobbers
    # eax/ecx/edx; preserves ebx (choice source) and esi.
    set_ = put(page, page_va, "mask_set", f"""
        mov eax, esi
        sub eax, 0x554190
        jb ms_ret
        xor edx, edx
        mov ecx, 0x{STRIDE:X}
        div ecx
        test edx, edx
        jne ms_ret
        cmp eax, {BOUND}
        jae ms_ret
        mov ecx, eax
        shr eax, 1
        movzx edx, byte ptr [eax + 0x{MASK_TABLE:X}]
        test cl, 1
        je ms_low
        and edx, 0x0F
        movzx ecx, bl
        and ecx, 0x0F
        shl ecx, 4
        or edx, ecx
        mov byte ptr [eax + 0x{MASK_TABLE:X}], dl
        ret
    ms_low:
        and edx, 0xF0
        movzx ecx, bl
        and ecx, 0x0F
        or edx, ecx
        mov byte ptr [eax + 0x{MASK_TABLE:X}], dl
        ret
    ms_ret:
        ret
    """)
    # mask_load_once: on the first village frame, restore the side-table from the
    # sidecar via the companion DLL's ReadMaskSidecar(table). LoadLibraryA is
    # idempotent (returns the already-loaded handle if the chooser opened it). The
    # loaded flag is set FIRST so a failed load never retries every frame. All
    # results null-guarded. esi (villager record) is preserved by the stdcall/DLL
    # calls, so the caller (mask_flip) can proceed. No villager-record or save write.
    load_once = put(page, page_va, "mask_load_once", f"""
        mov byte ptr [0x{MASK_LOADED:X}], 1
        push 0x{s['dll']:X}
        call dword ptr [0x4951E0]
        test eax, eax
        je mlo_ret
        push 0x{s['readmask_export']:X}
        push eax
        call dword ptr [0x4951DC]
        test eax, eax
        je mlo_ret
        push 0x{MASK_TABLE:X}
        call eax
    mlo_ret:
        ret
    """)
    # bighead_mask: detour for the Details-screen villager-portrait head draw
    # (`call 0x409CA0` at 0x466E05 inside sub_466C40). The portrait compositor
    # reads no faction/mask field, so it never draws the mask. This routine
    # replays the real head draw with the caller's own seven stdcall arguments
    # (re-pushed so 0x409CA0's `ret 0x1C` cleans the copies and the originals are
    # left intact on the stack), then -- if the villager has a chosen mask --
    # blits the heathen mask atlas (id 0x101) over the head at the SAME
    # position/facing/scale, lifted, before returning through `ret 0x1C` (which
    # cleans the caller's original seven arguments, exactly as the stock stdcall
    # call would have). esi (villager record) is preserved across both draws, so
    # mask_get keys the side-table correctly and the caller sees esi unchanged.
    # All transient values live in non-exec .data BSS scratch (W^X-clean).
    bighead = put(page, page_va, "bighead_mask", f"""
        push dword ptr [esp+0x1C]
        push dword ptr [esp+0x1C]
        push dword ptr [esp+0x1C]
        push dword ptr [esp+0x1C]
        push dword ptr [esp+0x1C]
        push dword ptr [esp+0x1C]
        push dword ptr [esp+0x1C]
        call 0x409CA0
        mov eax, [esp+0x08]
        add eax, 0x{BH_XOFF:X}
        mov dword ptr [0x{BH_SX:X}], eax
        mov eax, [esp+0x0C]
        sub eax, 0x{BH_LIFT:X}
        mov dword ptr [0x{BH_SY:X}], eax
        mov eax, [esp+0x14]
        mov dword ptr [0x{BH_SF:X}], eax
        mov eax, [esp+0x18]
        mov dword ptr [0x{BH_SS:X}], eax
        call 0x{page_va + OFF['mask_get']:X}
        test eax, eax
        je bh_ret
        cmp eax, 5
        ja bh_ret
        dec eax
        mov dword ptr [0x{BH_SROW:X}], eax
        mov ecx, dword ptr [0x{BH_SF:X}]
        and ecx, 7
        movzx ecx, byte ptr [ecx + 0x{page_va + OFF['bighead_offsets']:X}]
        mov dword ptr [0x{BH_SCOL:X}], ecx
        call 0x44FBB0
        mov ecx, eax
        push 0x{MASK_HANDLE:X}
        call 0x44FA30
        imul ecx, dword ptr [0x{BH_SS:X}], 0x{BH_SCALE_MUL:X}
        shr ecx, 0x{BH_SCALE_SHIFT:X}
        push 0
        push ecx
        push dword ptr [0x{BH_SCOL:X}]
        push dword ptr [0x{BH_SROW:X}]
        push dword ptr [0x{BH_SY:X}]
        push dword ptr [0x{BH_SX:X}]
        push eax
        mov ecx, dword ptr [esi + 0x2F2C]
        call 0x409CA0
    bh_ret:
        ret 0x1C
    """)
    # Head-facing-frame -> mask-column table (8 bytes) in the R+X page, read-only
    # and live-tunable. bigheads_masks.png is 3 facing columns; the head's own
    # facing frame selects the aligned column so the mask rotates + tracks.
    tbl_off = OFF["bighead_offsets"]
    if any(page[tbl_off : tbl_off + SIZES["bighead_offsets"]]):
        raise RuntimeError("bighead_offsets overlaps generated data")
    for i, col in enumerate(BH_COL_TABLE):
        page[tbl_off + i] = col & 0xFF
    return {
        "mask_flip": flip, "mask_restore": restore, "mask_get": get, "mask_set": set_,
        "mask_load_once": load_once, "bighead_mask": bighead,
    }


def build_page(page_va: int) -> tuple[bytes, dict[str, object]]:
    page = bytearray(PAGE_SIZE)
    page[0:8] = b"VVT9PG\0\0"
    page[8:12] = (1).to_bytes(4, "little")
    page[12:16] = PAGE_SIZE.to_bytes(4, "little")
    page[16:20] = BOUND.to_bytes(4, "little")
    page[20:24] = STRIDE.to_bytes(4, "little")
    page[24:28] = page_va.to_bytes(4, "little")
    strings = build_strings(page, page_va)
    routines: dict[str, bytes] = {}
    routines.update(build_modal(page, page_va, strings))
    routines.update(build_helpers(page, page_va, strings))
    routines.update(build_menus(page, page_va))
    routines["age"] = build_age(page, page_va)
    routines["mastery"] = build_mastery(page, page_va)
    routines["running"] = build_running(page, page_va)
    routines["heal"] = build_heal(page, page_va)
    if page_va == 0x7C9000:
        # Stock layout only; the expanded baseline keeps its empty reserves for
        # the separate vv5_expanded_256_time_warp overlay.
        routines["time_warp"] = build_time_warp(page, page_va, strings)
        routines["island"] = build_island(page, page_va, strings)
        routines["barrel"] = build_barrel(page, page_va, strings)
        routines["appearance"] = build_appearance(page, page_va, strings)
        routines["complete_collections"] = build_complete_collections(page, page_va)
        routines["reset_collections"] = build_reset_collections(page, page_va)
        routines["running_all"] = build_running_all(page, page_va)
        routines["mastery_all"] = build_mastery_all(page, page_va)
        routines["age18_all"] = build_age18_all(page, page_va)
        routines["barrel_close_arm"] = build_barrel_close_arm(page, page_va)
        routines["division_parenting"] = build_division(
            page, page_va, "division_parenting", parenting=1, action=23
        )
        routines["division_no_parenting"] = build_division(
            page, page_va, "division_no_parenting", parenting=0, action=24
        )
        routines.update(build_mask_render(page, page_va, strings))
    result = {
        "page_sha256": sha(bytes(page)),
        "routine_sha256": {name: sha(value) for name, value in routines.items()},
        "routine_length": {name: len(value) for name, value in routines.items()},
        "entry_virtual_addresses": {
            name: f"0x{page_va + OFF[name]:X}"
            for name in ("tech_entry", "detail_entry", "age", "mastery", "running", "heal")
        },
        "string_virtual_addresses": {name: f"0x{value:X}" for name, value in strings.items()},
    }
    return bytes(page), result


def patch_payload(active: dict[str, object], stock_page_va: int) -> tuple[bytes, dict[str, object]]:
    payload_patch = next(
        item for item in active["patches"] if int(str(item["offset"]), 0) == PAYLOAD_OFFSET
    )
    active_payload = bytes.fromhex(str(payload_patch["after"]))
    patch_length = len(active_payload)
    payload = bytearray(active_payload.ljust(0x1000, b"\0"))
    if len(payload) != 0x1000:
        raise RuntimeError("active VV5 payload length drift")
    geometry: dict[str, dict[str, str]] = {}
    for label, start, end, old_y in (
        ("tech", 0x40, 0xC0, bytes.fromhex("68D2020000")),
        ("detail", 0x100, 0x180, bytes.fromhex("68BC020000")),
    ):
        ctor = bytearray(payload[start:end])
        for before, after in (
            (bytes.fromhex("6A48"), bytes.fromhex("6A6A")),
            (old_y, bytes.fromhex("6802000000")),
            (bytes.fromhex("68B4000000"), bytes.fromhex("6889000000")),
        ):
            if ctor.count(before) != 1:
                raise RuntimeError(f"{label} geometry preimage drift: {before.hex().upper()}")
            ctor = ctor.replace(before, after)
        receiver = ctor.find(bytes.fromhex("89C789F96A6AE8"))
        if receiver < 0:
            raise RuntimeError(f"{label} constructor allocation/resource ABI drift")
        native_lookup = bytes(ctor[receiver + 6 : receiver + 11])
        if len(native_lookup) != 5 or native_lookup[0] != 0xE8:
            raise RuntimeError(f"{label} native resource lookup call drift")
        bridge = asm(
            f"xchg eax, edi; call 0x{stock_page_va + OFF['constructor_resource']:X}",
            PAYLOAD_VA + start + receiver,
        )
        if len(bridge) != 6:
            raise RuntimeError(f"{label} constructor resource bridge length drift")
        ctor[receiver : receiver + 11] = bridge + native_lookup
        payload[start:end] = ctor
        geometry[label] = {
            "allocation_bridge_bytes": (bridge + native_lookup).hex().upper(),
            "allocation_bridge_operand_offset": f"0x{PAYLOAD_OFFSET + start + receiver + 2:X}",
            "resource_manager": "0x44FBB0",
            "resource_lookup": "0x44FA20",
            "resource_lookup_receiver": "EAX returned by 0x44FBB0 copied to ECX",
            "control_constructor_receiver": "EDI allocation preserved by xchg EAX,EDI before constructor_resource helper",
            "resource_id": "0x6A",
            "dimensions": "96x39",
            "local_x": "137",
            "local_y": "2",
        }
    old_guard = bytes(payload[0x270:0x2C0])
    resolver_transfer = asm(
        f"push 0x{stock_page_va + OFF['resolve_manager']:X}; ret",
        PAYLOAD_VA + 0x276,
    )
    if len(resolver_transfer) != 6:
        raise RuntimeError("safe resolver transfer length drift")
    payload[0x276:0x27C] = resolver_transfer
    tech_stub = asm(f"mov eax, 0x{stock_page_va + OFF['tech_entry']:X}; jmp eax", PAYLOAD_VA + 0x2C0)
    detail_stub = asm(f"mov eax, 0x{stock_page_va + OFF['detail_entry']:X}; jmp eax", PAYLOAD_VA + 0x600)
    if len(tech_stub) != 7 or len(detail_stub) != 7:
        raise RuntimeError("Task9 absolute menu stub length drift")
    payload[0x2C0:0x2C7] = tech_stub
    payload[0x600:0x607] = detail_stub
    forbidden = bytes.fromhex("E11C0000")
    forbidden_count = payload.count(forbidden)
    payload = bytearray(bytes(payload).replace(forbidden, bytes.fromhex("EC1C0000")))
    if forbidden in payload:
        raise RuntimeError("withdrawn legacy eligibility read remains")
    return bytes(payload[:patch_length]), {
        "geometry": geometry,
        "safe_resolver_before_sha256": sha(old_guard),
        "safe_resolver_transfer_bytes": resolver_transfer.hex().upper(),
        "safe_resolver_transfer_sha256": sha(resolver_transfer),
        "tech_entry_stub": tech_stub.hex().upper(),
        "detail_entry_stub": detail_stub.hex().upper(),
        "withdrawn_legacy_eligibility_immediates_rebound_to_faction": forbidden_count,
    }


def append_layout(layout: dict[str, int], page: bytes) -> dict[str, object]:
    new_size = layout["size_of_image_before"] + PAGE_SIZE
    header = section_header(layout["page_rva"], layout["append_offset"])
    return {
        "original_file_size": f"0x{layout['append_offset']:X}",
        "append_offset": f"0x{layout['append_offset']:X}",
        "append_length": PAGE_SIZE,
        "append_bytes": page.hex().upper(),
        "append_source": "generated:vv5_task9_native_actions_page",
        "page_virtual_address": f"0x{layout['page_va']:X}",
        "page_sha256": sha(page),
        "purpose": "append the guarded VV5 Task9 native action and owner-safe UI page",
        "header_patches": [
            {
                "offset": f"0x{layout['section_count_offset']:X}",
                "before": layout["section_count_before"].to_bytes(2, "little").hex().upper(),
                "after": (layout["section_count_before"] + 1).to_bytes(2, "little").hex().upper(),
                "purpose": "add the generated Task9 RX section",
            },
            {
                "offset": f"0x{layout['size_of_image_offset']:X}",
                "before": layout["size_of_image_before"].to_bytes(4, "little").hex().upper(),
                "after": new_size.to_bytes(4, "little").hex().upper(),
                "purpose": "extend SizeOfImage for Task9",
            },
            {
                "offset": f"0x{layout['section_header_offset']:X}",
                "before": "00" * 40,
                "after": header.hex().upper(),
                "purpose": "install the guarded .vv5t9 section header",
            },
        ],
    }


def main() -> None:
    stock = STOCK.read_bytes()
    if len(stock) != 991232 or sha(stock) != STOCK_SHA256:
        raise RuntimeError("VV5 stock identity drift")
    active_bytes = ACTIVE.read_bytes()
    if sha(active_bytes) != ACTIVE_SHA256 or source_text_sha(active_bytes) != ACTIVE_SOURCE_TEXT_SHA256:
        raise RuntimeError("pinned active VV5 Origins source drift")
    active = json.loads(active_bytes.decode("utf-8"))
    relocations = active["expanded_shr_relocations"]["patches"]
    if len(relocations) != C342_COUNT or canonical_sha(relocations) != C342_ROWS_SHA256:
        raise RuntimeError("frozen C342 66-row ledger drift")
    companion = COMPANION.read_bytes()
    bindings = source_bindings()
    pages: dict[str, bytes] = {}
    page_maps: dict[str, object] = {}
    for mode, layout in LAYOUTS.items():
        page, page_map = build_page(layout["page_va"])
        pages[mode] = page
        page_maps[mode] = page_map
    payload, payload_map = patch_payload(active, LAYOUTS["collection_progression"]["page_va"])
    result = deepcopy(active)
    result.update({
        "schema": "vvfp.vv5_task9_native_actions.v1",
        "id": "vv5_enable_origins_exclusive_features",
        "name": "Enable Origins-Exclusive Features (Task9 native actions)",
        "description": "Adds Origins-style upgrade menus to Tech and Villager Details. The menus offer Full Mastery, Running, Make Villagers Young Adults, and Full Heal/Cure All for Believers; Heathens are skipped. Time Warp advances the village by three displayed villager years (speed-independent) for a single 50,000 tech-point charge. Island Event queues a random native island event by making the next-event timer due. Barrel of Babies queues the native Barrel event (a barrel with three children) after confirming the village has room. Exact costs are shown in each confirmation.",
        "enabled": True,
        "catalog_hidden": False,
        "catalog_enabled": True,
        "supported_modes": list(LAYOUTS),
        "runtime_player_status": "pending",
        "base_source_text_sha256": ACTIVE_SOURCE_TEXT_SHA256,
        "base_file_sha256": ACTIVE_SHA256,
        "task8_overlay_source_text_sha256": TASK8_SOURCE_TEXT_SHA256,
        "atomic_core": {
            "commit": ATOMIC_CORE_COMMIT,
            "generator_source_text_sha256": ATOMIC_SOURCE_TEXT_SHA256["atomic_generator"],
            "contract_source_text_sha256": ATOMIC_SOURCE_TEXT_SHA256["atomic_contract"],
        },
        "source_bindings": bindings,
        "frozen_c342": {"count": C342_COUNT, "rows_sha256": C342_ROWS_SHA256, "unchanged": True},
        "task9_contract": {
            "owner": "BeginOriginsOwner/GetOriginsOwner/EndOriginsOwner; same-process HWND only; capture before fullscreen leave; no foreground fallback; centralized restore then End",
            "sequence": "complete dry-run -> IDOK -> fresh identity/snapshot/funds -> mutation -> postverify -> one native charge -> exact balance readback",
            "selection": "resolver 0x425950 null-guarded before +0x17E24; unsigned command 0..3 before resolver or price access",
            "eligibility": "active +0x1CD4, Heathen mask/status +0x1CE1 == 0, current-Believer faction +0x1CEC == 0, signed living health +0x1C40 > 0",
            "eligibility_schema": "both the VV5 Heathen mask/status byte and current faction must identify an active living Believer; masked records are rejected before action-specific reads or writes",
            "actions": {
                "youth": {"price": 50000, "target": "max(raw_age-700,100)", "writer": "0x46F7F0 ECX=record+0x1B8C signed delta", "companions": ["+0x1C3C same delta", "+0x1C4C same delta only when nonzero"]},
                "age18": {"price": 50000, "target": 360, "writer": "0x46F7F0 ECX=record+0x1B8C signed delta", "companions": ["+0x1C3C same delta", "+0x1C4C same delta only when nonzero"]},
                "full_mastery": {"price": 100000, "fields": ["0x1C5C", "0x1C60", "0x1C64", "0x1C68", "0x1C6C", "0x1C70"], "writer": "0x475730 ECX=record+0x1C5C push Float32 delta then push index", "target_bits": "0x42C80000"},
                "running": {"price": 40000, "preference_id": 38, "likes": ["0x1F5C", "0x1F60", "0x1F64"], "dislikes": ["0x1F68", "0x1F6C", "0x1F70"], "native": {"membership": "0x464F90", "insertion": "0x464AD0", "first_removal": "0x4649E0"}},
                "barrel_of_babies": {"price": 75000, "scope": "village event scheduler (presents the native Barrel event, index 25, after the Tech screen closes)", "room_check": "both capacity checks call the game's own per-villager cap gate 0x472bd0, which every population mode patches (0x72C49 -> 0x94500 helper) to its live cap (stock 105, collection_progression 150, immediate_fixed 150, expanded-256 256); the barrel is refused with no deduction when the village is at its current mode's cap", "mechanism": "VV2 general approach: charge -75000 via 0x4237B0, set one-shot pending token (or [0x51D388],8) only; the origins-base Tech handler routes stock command 0 (screen close) to barrel_close_arm, which consumes the token, sets the forced-Barrel marker (or [0x51D388],4), and makes the next event due ([manager+0x17D3C]=0); the selector detour at 0x41890F forces the next chosen index to 25 and clears the marker so the native three-child Barrel presents with the main-village owner after the menu closes", "children": 3, "dialog": "self-contained MessageBoxA (no companion DLL change)"},
                "island_event": {"price": 30000, "scope": "village next-event scheduler (not a per-record write)", "mechanism": "resolve manager 0x425950, verify snapshot, charge -30000 via 0x4237B0, set next-event timer [manager+0x17D3C]=0 so the native scheduler (0x442850 -> sub_418870) runs a random eligible island event", "dialog": "self-contained MessageBoxA (no companion DLL change)"},
                "time_warp": {"price": 50000, "scope": "village clock (not a per-record write; faction-blind like normal time passing)", "speed": "[manager+0x17D7C] signed positive and not 999 (paused)", "delta": "129600 / speed subtracted from the 64-bit village clock 0x4C6250/0x4C6254", "effect": "advances exactly three displayed villager years regardless of listed game speed", "writer": "inline: verify snapshot, charge -50000 via 0x4237B0, div 129600 by speed, sub/sbb into clock, postverify", "dialog": "self-contained MessageBoxA (no companion DLL change)"},
                "full_heal": {"price": 30000, "health_rule": "every eligible Believer with health < 100 is raised to exactly 100; health already at 100 is unchanged and uncounted", "health_writer": "0x4758B0 ECX=record+0x1C34 push -1 then push 100", "sickness": "+0x1C48 byte", "masked_heathen_policy": "skip before sickness/type reads; includes the sick Heathen puzzle record", "unsupported_type": "+0x1CFC == 12 when sick on an otherwise eligible Believer", "people_cured": "0x51D368", "statistic_writer": "0x413450 ECX=0x4DB358 IDs 52/53/54 amount 1"},
            },
        },
        "companion_files": [{
            "source": "data/candidates/VVFP VV5 Task9 Origins Icons.dll",
            "destination": "VVFP Origins Icons.dll",
            "sha256": sha(companion),
            "size": len(companion),
        }],
        "pe_append_transaction": {
            "section": ".vv5t9",
            "append_source": "generated:vv5_task9_native_actions_page",
            "layouts": {mode: append_layout(LAYOUTS[mode], pages[mode]) for mode in LAYOUTS},
        },
        "task9_expanded_post_relocation_patches": {
            mode: [deepcopy(TASK9_EXPANDED_HOOK)]
            for mode in (
                "experimental_expanded_256",
                "experimental_expanded_256_progression",
            )
        },
    })
    for item in result["patches"]:
        after = bytes.fromhex(str(item["after"]))
        if int(str(item["offset"]), 0) == PAYLOAD_OFFSET:
            item["after"] = payload.hex().upper()
            item["purpose"] = "install pinned VV5 Origins payload with Task9 geometry, safe resolver, and absolute native-action entries"
        elif bytes.fromhex("E11C0000") in after:
            item["after"] = after.replace(bytes.fromhex("E11C0000"), bytes.fromhex("EC1C0000")).hex().upper()
            item["purpose"] = str(item["purpose"]) + "; remove the withdrawn synthetic eligibility read"
    expanded_overrides = [
        {
            "offset": f"0x{PAYLOAD_OFFSET + 0x2C1:X}",
            "before": (LAYOUTS["collection_progression"]["page_va"] + OFF["tech_entry"]).to_bytes(4, "little").hex().upper(),
            "after": (LAYOUTS["experimental_expanded_256"]["page_va"] + OFF["tech_entry"]).to_bytes(4, "little").hex().upper(),
            "purpose": "bind relocated .shr Tech entry to the fixed Expanded Task9 page",
        },
        {
            "offset": f"0x{PAYLOAD_OFFSET + 0x601:X}",
            "before": (LAYOUTS["collection_progression"]["page_va"] + OFF["detail_entry"]).to_bytes(4, "little").hex().upper(),
            "after": (LAYOUTS["experimental_expanded_256"]["page_va"] + OFF["detail_entry"]).to_bytes(4, "little").hex().upper(),
            "purpose": "bind relocated .shr Detail entry to the fixed Expanded Task9 page",
        },
        {
            "offset": f"0x{PAYLOAD_OFFSET + 0x277:X}",
            "before": (LAYOUTS["collection_progression"]["page_va"] + OFF["resolve_manager"]).to_bytes(4, "little").hex().upper(),
            "after": (LAYOUTS["experimental_expanded_256"]["page_va"] + OFF["resolve_manager"]).to_bytes(4, "little").hex().upper(),
            "purpose": "bind the preserved legacy resolver entry to its Expanded null-guard continuation without changing any C342 row",
        },
    ]
    for label in ("tech", "detail"):
        operand_offset = int(payload_map["geometry"][label]["allocation_bridge_operand_offset"], 0)
        stock_opcode_va = PAYLOAD_VA + (operand_offset - PAYLOAD_OFFSET) - 1
        expanded_opcode_va = EXPANDED_PAYLOAD_VA + (operand_offset - PAYLOAD_OFFSET) - 1
        stock_target = LAYOUTS["collection_progression"]["page_va"] + OFF["constructor_resource"]
        expanded_target = LAYOUTS["experimental_expanded_256"]["page_va"] + OFF["constructor_resource"]
        expanded_overrides.append({
            "offset": f"0x{operand_offset:X}",
            "before": (stock_target - (stock_opcode_va + 5)).to_bytes(4, "little", signed=True).hex().upper(),
            "after": (expanded_target - (expanded_opcode_va + 5)).to_bytes(4, "little", signed=True).hex().upper(),
            "purpose": f"bind the relocated .shr {label} constructor resource-manager bridge to the Expanded Task9 page",
        })
    for mode in ("experimental_expanded_256", "experimental_expanded_256_progression"):
        result["patch_mode_overrides"].setdefault(mode, []).extend(deepcopy(expanded_overrides))
    # Barrel of Babies deferral (VV2 general approach): a stock-only five-byte
    # detour over the Technologies screen close handler (command 0) at 0x441617,
    # routing to the stock Task9 page's barrel_close_arm routine. The Barrel row,
    # its purchase token, and this routine all live only in the stock layouts, so
    # the hook is added only to the stock modes; the Expanded-256 baseline page
    # stays byte-identical for the separate vv5_expanded_256_time_warp overlay.
    barrel_close_site = 0x441617
    barrel_close_preimage = "B940F45100"
    if stock[barrel_close_site - 0x400000 : barrel_close_site - 0x400000 + 5].hex().upper() != barrel_close_preimage:
        raise RuntimeError("Barrel close-handler preimage drift at 0x441617")
    for mode in ("collection_progression", "immediate_fixed"):
        page_va = LAYOUTS[mode]["page_va"]
        rel = (page_va + OFF["barrel_close_arm"]) - (barrel_close_site + 5)
        result["patch_mode_overrides"].setdefault(mode, []).append({
            "offset": f"0x{barrel_close_site - 0x400000:X}",
            "before": barrel_close_preimage,
            "after": "E9" + rel.to_bytes(4, "little", signed=True).hex().upper(),
            "purpose": "Barrel of Babies (VV2 approach): on Technologies screen close (command 0) arm the deferred native three-child Barrel so it presents with the main-village owner after the menu closes",
        })
    # Heathen-mask cosmetic render (stock only): three detours into the Task9
    # page's mask_flip / mask_restore routines so the +0x1BC0 picker choice is
    # actually rendered. The render hook lives in the appended .vv5t9 page (never
    # a .text cave), so it cannot contend with the population / statistics / other
    # cave features. mask_flip enters after the selection-ring block (0x472481,
    # 7-byte `mov ecx,[esp+0xbc]` replayed inside the routine); mask_restore
    # enters from both epilogues (0x472B0F / 0x472B57 = add esp,0xA8; ret 8).
    mask_flip_site = 0x472481
    mask_flip_preimage = "8B8C24BC000000"      # mov ecx, [esp+0xBC] (7 bytes)
    mask_restore_sites = (0x472B0F, 0x472B57)
    mask_restore_preimage = "81C4A80000"       # add esp, 0xA8 (first 5 of 6 bytes)
    if stock[mask_flip_site - 0x400000 : mask_flip_site - 0x400000 + 7].hex().upper() != mask_flip_preimage:
        raise RuntimeError("Heathen-mask flip-site preimage drift at 0x472481")
    for site in mask_restore_sites:
        if stock[site - 0x400000 : site - 0x400000 + 5].hex().upper() != mask_restore_preimage:
            raise RuntimeError(f"Heathen-mask epilogue preimage drift at 0x{site:X}")
    for mode in ("collection_progression", "immediate_fixed"):
        page_va = LAYOUTS[mode]["page_va"]
        overrides = result["patch_mode_overrides"].setdefault(mode, [])
        rel = (page_va + OFF["mask_flip"]) - (mask_flip_site + 5)
        overrides.append({
            "offset": f"0x{mask_flip_site - 0x400000:X}",
            "before": mask_flip_preimage,
            "after": "E9" + rel.to_bytes(4, "little", signed=True).hex().upper() + "9090",
            "purpose": "Heathen mask: after the selection-ring block, flip a chosen-mask Believer to its heathen head+mask for the head draw (the ring keeps believer-white)",
        })
        for site in mask_restore_sites:
            rel = (page_va + OFF["mask_restore"]) - (site + 5)
            overrides.append({
                "offset": f"0x{site - 0x400000:X}",
                "before": mask_restore_preimage,
                "after": "E9" + rel.to_bytes(4, "little", signed=True).hex().upper(),
                "purpose": "Heathen mask: at the render-fn epilogue, revert the transient faction+colour flip via the saved villager pointer, then run the displaced add esp,0xA8; ret 8",
            })
    # Heathen mask on the Details villager portrait (the "bigheads" render): the
    # portrait compositor sub_466C40 draws the head via `call 0x409ca0` at
    # 0x466E05 but never draws the mask (it reads no faction/mask field, unlike
    # the village render's faction-flip path). Detour that head-draw call to the
    # page's bighead_mask routine, which replays the head then blits the chosen
    # mask atlas (id 0x101) over it. sub_466C40 is the shared portrait compositor,
    # so the mask shows consistently on every villager-portrait screen.
    bighead_site = 0x466E05
    bighead_preimage = "E8962EFAFF"            # call 0x409CA0 (5 bytes)
    if stock[bighead_site - 0x400000 : bighead_site - 0x400000 + 5].hex().upper() != bighead_preimage:
        raise RuntimeError("Heathen-mask bighead head-draw preimage drift at 0x466E05")
    for mode in ("collection_progression", "immediate_fixed"):
        page_va = LAYOUTS[mode]["page_va"]
        overrides = result["patch_mode_overrides"].setdefault(mode, [])
        rel = (page_va + OFF["bighead_mask"]) - (bighead_site + 5)
        overrides.append({
            "offset": f"0x{bighead_site - 0x400000:X}",
            "before": bighead_preimage,
            "after": "E8" + rel.to_bytes(4, "little", signed=True).hex().upper(),
            "purpose": "Heathen mask: on the Details villager portrait, replay the head draw then blit the chosen mask atlas over it (the portrait compositor draws no mask natively)",
        })
    # Register the dedicated bighead mask atlas (bigheads_masks.png) as a new
    # sprite-table record in the free slot 0x155 (0x4D2FA8 in .data). The stock
    # slot is unused (all-zero); write {id, filename_ptr, cols=1, rows=5}. The
    # filename string lives in the Task9 page, and bigheads_masks.png ships in the
    # game Images/ folder; sub_44FA30(0x155) lazily loads it for the portrait blit.
    atlas_rec_off = BIGHEAD_ATLAS_REC_VA - 0x400000
    if any(stock[atlas_rec_off : atlas_rec_off + 0x30]):
        raise RuntimeError(f"bighead atlas sprite slot 0x{BIGHEAD_ATLAS_ID:X} not free at 0x{BIGHEAD_ATLAS_REC_VA:X}")
    for mode in ("collection_progression", "immediate_fixed"):
        str_va = int(page_maps[mode]["string_virtual_addresses"]["bighead_atlas"], 16)
        rec = (
            BIGHEAD_ATLAS_ID.to_bytes(4, "little")
            + str_va.to_bytes(4, "little")
            + BIGHEAD_ATLAS_COLS.to_bytes(4, "little")
            + BIGHEAD_ATLAS_ROWS.to_bytes(4, "little")
            + b"\0" * 0x20
        )
        result["patch_mode_overrides"].setdefault(mode, []).append({
            "offset": f"0x{atlas_rec_off:X}",
            "before": "00" * 0x30,
            "after": rec.hex().upper(),
            "purpose": "Register bigheads_masks.png as sprite id 0x155 (free slot) so the Details portrait mask blit uses the dedicated bighead atlas",
        })
    if any(bytes.fromhex("E11C0000") in bytes.fromhex(str(item["after"])) for item in result["patches"]):
        raise RuntimeError("Task9 emitted patch set retains a withdrawn eligibility read")
    map_record = {
        "schema": "vvfp.vv5_task9_native_actions_map.v1",
        "source": {"size": len(stock), "sha256": sha(stock)},
        "active_base": {"size": len(active_bytes), "file_sha256": sha(active_bytes), "source_text_sha256": source_text_sha(active_bytes)},
        "task8_overlay_source_text_sha256": TASK8_SOURCE_TEXT_SHA256,
        "atomic_core": {
            "commit": ATOMIC_CORE_COMMIT,
            "generator_source_text_sha256": ATOMIC_SOURCE_TEXT_SHA256["atomic_generator"],
            "contract_source_text_sha256": ATOMIC_SOURCE_TEXT_SHA256["atomic_contract"],
        },
        "source_bindings": bindings,
        "c342": {"count": len(relocations), "rows_sha256": canonical_sha(relocations), "unchanged": True},
        "companion": {"size": len(companion), "sha256": sha(companion)},
        "payload": {"sha256": sha(payload), **payload_map},
        "layouts": {mode: page_maps[mode] | {"append_offset": f"0x{LAYOUTS[mode]['append_offset']:X}", "page_virtual_address": f"0x{LAYOUTS[mode]['page_va']:X}"} for mode in LAYOUTS},
        "nonoverlap": {
            "task8_dbxxx_range": ["0xDB000", "0xDC000"],
            "task9_stock_append_range": ["0xF2000", "0xFA000"],
            "task9_expanded_append_range": ["0xF4000", "0xFC000"],
            "c342_new_row_count": 0,
            "absolute_entry_stubs_require_c342_relocation": False,
        },
        "resolver_contract": {
            "record_pointer_resolver": "0x46F950",
            "forbidden_transitive_helpers": ["0x466170", "0x471840"],
            "eligibility_order": ["+0x1CD4 != 0", "+0x1CE1 == 0", "+0x1CEC == 0", "+0x1C40 signed > 0"],
        },
        "expanded_cross_section_hook_audit": {
            "hook_count": len(TASK9_CROSS_SECTION_HOOKS),
            "hooks": TASK9_CROSS_SECTION_HOOKS,
            "frozen_c342_operand_offsets": [
                "0x18910", "0x1EB70", "0x237B1", "0x40A25", "0x4AF13", "0x4BC21"
            ],
            "task9_post_relocation_hook_offset": "0x415F0",
            "task9_post_relocation_operand_offset": "0x415F1",
            "c342_changed": False,
        },
    }
    result["task9_map_canonical_sha256"] = canonical_sha(map_record)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    MAP_OUT.write_text(json.dumps(map_record, indent=2) + "\n", encoding="utf-8")
    print(f"manifest {OUT} {sha(OUT.read_bytes())}")
    print(f"map {MAP_OUT} {sha(MAP_OUT.read_bytes())}")
    for mode in LAYOUTS:
        print(f"{mode} page {sha(pages[mode])}")


if __name__ == "__main__":
    main()
