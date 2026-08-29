"""Assemble the exact-build VV2 Origins-exclusive feature patch."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from source_text_hash import source_text_sha256  # noqa: E402

STOCK = (
    ROOT
    / "research"
    / "stock-executables"
    / "Virtual Villagers - The Lost Children.exe"
)
OUT_DIR = ROOT / "research" / "vv2-origins"
OUT_EXE = OUT_DIR / "Virtual Villagers - The Lost Children - Origins Research.exe"
OUT_JSON = OUT_DIR / "vv2-origins-feature-patches.json"
MANIFEST_JSON = ROOT / "data" / "vv2_origins_feature.json"

sys.path.insert(0, str(ROOT / ".tools" / "keystone"))
sys.path.insert(0, str(ROOT / ".tools" / "keystone-runtime"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402


IMAGE_BASE = 0x400000
PAYLOAD_FILE_OFFSET = 0x943A8
# The Origins payload occupies the final 0xC58 bytes of .rdata.  Its raw
# offset and RVA are equal, but the stock .rdata VirtualSize stops exactly at
# this payload start; the PE-header patches below extend that mapped range and
# mark it executable.
PAYLOAD_VA = IMAGE_BASE + PAYLOAD_FILE_OFFSET
PAYLOAD_SIZE = 0xC58
STRINGS_OFFSET = 0x9E0
STRINGS_VA = PAYLOAD_VA + STRINGS_OFFSET
# .shr is stored at raw 0x9A000 but is mapped at RVA 0x9C000.  Never derive a
# runtime VA by adding IMAGE_BASE to a raw file offset: that was the cause of
# the Tech-screen preflight access violation at raw 0x9A009.
SHR_FILE_OFFSET = 0x9A000
SHR_RVA = 0x9C000
HEAL_CAVE_FILE_OFFSET = 0x9A004
CURE_PREFLIGHT_FILE_OFFSET = 0x9A300
CURE_PREFLIGHT_VA = IMAGE_BASE + SHR_RVA + (
    CURE_PREFLIGHT_FILE_OFFSET - SHR_FILE_OFFSET
)
DETAIL_PREFLIGHT_FILE_OFFSET = 0x9A380
DETAIL_PREFLIGHT_VA = IMAGE_BASE + SHR_RVA + (
    DETAIL_PREFLIGHT_FILE_OFFSET - SHR_FILE_OFFSET
)
CURE_ENTRY_FILE_OFFSET = 0x9A530
CURE_ENTRY_VA = IMAGE_BASE + SHR_RVA + (CURE_ENTRY_FILE_OFFSET - SHR_FILE_OFFSET)
HEAL_CAVE_VA = CURE_ENTRY_VA
# The Full Heal result-export name string trails the Cure code in its reserve.
CURE_STRING_VA = CURE_ENTRY_VA + 0x1A0
# The optional village-wide payload follows the base VV2 Origins helpers in
# the .shr reserve at raw 0x9A800.  Its runtime address must use the mapped
# .shr RVA, not IMAGE_BASE + raw file offset.
VILLAGE_WIDE_SIGNATURE_VA = IMAGE_BASE + SHR_RVA + 0x800
VILLAGE_WIDE_ENTRY_VA = IMAGE_BASE + SHR_RVA + 0x820
# Fixed scratch dword in the confirmed-unused gap between the optional
# village-wide payload's entry dispatch and its own running_va (see
# scripts/build_village_wide_origins_features.py's report_running_granted,
# which now writes this for VV2 too -- mirrors VV1's own
# RUNNING_GRANTED_VA). ShowOriginsVillageWideResult's shared C body
# (native/vv1_origins_icons/vv1_origins_icons.c, #included by VV2's own
# .c) always displays a "Granted Running to %d villagers." headline, so
# this can no longer be left unset now that the function takes it.
RUNNING_GRANTED_VA = VILLAGE_WIDE_ENTRY_VA + 0x30
VILLAGE_PREFLIGHT_FILE_OFFSET = 0x9A009
VILLAGE_PREFLIGHT_VA = IMAGE_BASE + SHR_RVA + (VILLAGE_PREFLIGHT_FILE_OFFSET - SHR_FILE_OFFSET)
BARREL_PENDING_FILE_OFFSET = 0x9A700
BARREL_PENDING_VA = IMAGE_BASE + SHR_RVA + (BARREL_PENDING_FILE_OFFSET - SHR_FILE_OFFSET)
BARREL_CLOSE_HELPER_FILE_OFFSET = 0x9A710
BARREL_CLOSE_HELPER_VA = IMAGE_BASE + SHR_RVA + (
    BARREL_CLOSE_HELPER_FILE_OFFSET - SHR_FILE_OFFSET
)
BARREL_CLOSE_HELPER_CODE = bytes.fromhex(
    "8B4E146A4BE8F628FAFF6A0089F1E8CDF0F6FF8B460C"
    "C7807004030001000000803D00C74900017507C60500C7490002"
    "E9B570FAFF"
)
BARREL_MAIN_HELPER_FILE_OFFSET = 0x9A780
BARREL_MAIN_HELPER_VA = IMAGE_BASE + SHR_RVA + (
    BARREL_MAIN_HELPER_FILE_OFFSET - SHR_FILE_OFFSET
)
# The Barrel of Babies event is a normal queued village event (enqueued through
# the stock 0x401AD0 pipeline, exactly like the Island Event).  It used to be
# marked "ready" the instant the Tech screen closed, so it played during the
# menu-close transition and flashed by unreadably.  Instead the main-village
# helper now counts down BARREL_CUE_FRAMES ticks of the per-frame village update
# after the screen closes before enqueuing, so it plays cued during normal
# gameplay.  The countdown lives in the reserved Barrel token region.
BARREL_CUE_COUNTER_FILE_OFFSET = 0x9A708
BARREL_CUE_COUNTER_VA = IMAGE_BASE + SHR_RVA + (
    BARREL_CUE_COUNTER_FILE_OFFSET - SHR_FILE_OFFSET
)
BARREL_CUE_FRAMES = 90
# Change Appearance helper: placed after the optional village-wide payload in
# the .shr reserve (village-wide occupies 0x9A800..0x9AD20). The first 0x100
# bytes hold the helper code; the export name string follows at +0x100.
APPEARANCE_FILE_OFFSET = 0x9AD20
APPEARANCE_VA = IMAGE_BASE + SHR_RVA + (APPEARANCE_FILE_OFFSET - SHR_FILE_OFFSET)
# The appearance handler MUST stay within its 0x100 byte box — the next Origins
# handler ("All 18") begins right after the string that follows this block, so
# growing it corrupts that handler. The mask read/write fits; the sidecar SAVE is
# done DLL-side (not here) to avoid growing this box.
APPEARANCE_CODE_MAX = 0x100
APPEARANCE_STRING_VA = APPEARANCE_VA + APPEARANCE_CODE_MAX

# Whole-village Tech-screen upgrades (Running / Full Mastery / Age 18 for all
# villagers). Placed after the Change Appearance helper in the .shr reserve.
WHOLE_VILLAGE_FILE_OFFSET = 0x9AE40
WHOLE_VILLAGE_VA = IMAGE_BASE + SHR_RVA + (
    WHOLE_VILLAGE_FILE_OFFSET - SHR_FILE_OFFSET
)
COLLECTION_TECH_COST = 1000000
# Single DLL-dispatch stub for the four village-wide upgrades that delegate to
# the companion DLL: Grant Running (6) and Grant Full Mastery (7) hand the
# certified record array (sub_44F4E0) to their counting/reporting exports, while
# Complete (9) / Reset (10) all Collections hand the Tech-menu player object to
# ApplyVV2Collections.  Placed in the free .shr tail after the whole-village
# helper so it stays clear of the separate signed village-wide API block
# (0x9A800..0x9AD20).  The 1,000,000 charge is done by the Tech menu.
# Placed in the (now-dead) whole-village helper slot: Running/Mastery/Age/
# Collections all run in the DLL now, so the old .shr whole-village writer is
# unused and its 0x1C0-byte slot hosts the dispatch stub + its export strings.
DISPATCH_FILE_OFFSET = 0x9AE40
DISPATCH_VA = IMAGE_BASE + SHR_RVA + (DISPATCH_FILE_OFFSET - SHR_FILE_OFFSET)
# The Task9-style OK/Cancel purchase confirm lives in the DLL (ConfirmVV2Upgrade).
# Its export-name string can't fit the full payload string cave, so it sits in
# the free .shr gap between the village-wide preflight and the Cure preflight.
CONFIRM_EXPORT_FILE_OFFSET = 0x9A204
CONFIRM_EXPORT_VA = IMAGE_BASE + SHR_RVA + (
    CONFIRM_EXPORT_FILE_OFFSET - SHR_FILE_OFFSET
)
CONFIRM_EXPORT_BYTES = b"ConfirmVV2Upgrade\0"
# Result-string export + a tiny .shr trampoline so the payload's simple success
# and doubler paths can render Task9 result text ("<Action> completed.", etc.)
# from the DLL instead of the old flat "Purchased." string.
RESULT_EXPORT_FILE_OFFSET = 0x9A218
RESULT_EXPORT_VA = IMAGE_BASE + SHR_RVA + (
    RESULT_EXPORT_FILE_OFFSET - SHR_FILE_OFFSET
)
RESULT_EXPORT_BYTES = b"ShowVV2UpgradeResult\0"
RESULT_HELPER_FILE_OFFSET = 0x9A240
RESULT_HELPER_VA = IMAGE_BASE + SHR_RVA + (
    RESULT_HELPER_FILE_OFFSET - SHR_FILE_OFFSET
)
# Per-row Detail no-change check.  Given (record, row) it decides whether the
# purchase would change anything; if not it shows the row-specific no-change
# message (via the result trampoline) and tells the payload to charge nothing.
# Placed in the (now-dead) Detail preflight slot: the payload no longer calls
# that generic preflight, so its 0x9A380..0x9A530 region hosts this helper.
DETAIL_NOCHANGE_FILE_OFFSET = 0x9A380
DETAIL_NOCHANGE_VA = IMAGE_BASE + SHR_RVA + (
    DETAIL_NOCHANGE_FILE_OFFSET - SHR_FILE_OFFSET
)
# Barrel of Babies capacity gate.  Before the Barrel is cued (and before any
# charge), the Tech menu hands the player object to the companion DLL's
# GateVV2Barrel, which reads the current population demand (sub_425860) and the
# real, mode-dependent cap the game's own predicate at 0x44B310 enforces.  That
# cap is dynamic: the DLL reads the population-mode edits live (Stock base 90 +
# 0-25 collections, Collection Progression base 231 + collections, Immediate
# Fixed a flat 256), so it stays correct under whichever population mode the
# player installed.  When fewer than 3 slots remain for the Barrel's 3 children
# it shows the "close to maximum" notice and reports no room so the payload
# charges nothing.  A tiny .shr stub does the LoadLibrary / GetProcAddress
# handshake; it lives in the free tail of the dispatch slot (the dispatch
# stub's old 0x9AF58 home).
BARREL_GATE_FILE_OFFSET = 0x9AF58
BARREL_GATE_VA = IMAGE_BASE + SHR_RVA + (
    BARREL_GATE_FILE_OFFSET - SHR_FILE_OFFSET
)
BARREL_GATE_EXPORT_BYTES = b"GateVV2Barrel\0"

# VV2 villager record fields (exact-build appearance audit).
VV2_HEAD_FIELD = 0x548
VV2_BODY_FIELD = 0x54C
VV2_SEX_FIELD = 0x538
VV2_APPEARANCE_COST = 5000
# Patch-owned per-villager mask table appended to the exe (.mtab section), indexed
# by record index (0=none, 1..5). The appearance handler reads/writes it alongside
# head/body; the mask render stubs (in .vvmk) read it. NOT a villager-record byte.
VV2_MASK_TABLE_VA = 0x004B3000

RUNNING_PREFERENCE_ID = 38  # exact-build preference-table evidence: 0x8B808

# The mask stage owns these five fixed-build detours.  Store only their stock
# guards and purposes here: each replacement is sliced from the authoritative
# stage-2 builder output below.  Freezing replacement JMP literals here caused
# four hooks to drift when the adult/child stubs grew while the append page was
# regenerated, including a compositor jump into the middle of init code.
VV2_MASK_STAGE2_PATCH_SPECS = (
    {
        "offset": "0x3160",
        "before": "8B4424048B11",
        "purpose": "route the exact VV2 save-path builder through the mask sidecar slot publisher",
    },
    {
        "offset": "0x95B0",
        "before": "8B09E989F3FFFF",
        "purpose": "route the exact VV2 adult head draw through the mask overlay",
    },
    {
        "offset": "0x9600",
        "before": "8B09E9E9F6FFFF",
        "purpose": "route the exact VV2 child and portrait head draw through the mask overlay",
    },
    {
        "offset": "0x45B50",
        "before": "5355568BF1",
        "purpose": "run the mask table sweep at the exact VV2 village compositor entry",
    },
    {
        "offset": "0x4C5E6",
        "before": "8986D874E500",
        "purpose": "load the embedded mask atlas and companion exports at the exact VV2 asset-load tail",
    },
)
VV2_MASK_STAGE2_APPEND_SHA256 = (
    "C8C03CABBD574F0697E89528D61B79BB1E58DECD0BAC6371D7EF9BA1B47E2C54"
)


def build_vv2_mask_stage2_output(source_bytes: bytes) -> bytes:
    """Run the authoritative mask-stage builder during manifest generation."""
    builder_path = ROOT / "scripts" / "build_vv2_mask_stage2.py"
    spec = importlib.util.spec_from_file_location(
        "vv2_mask_stage2_manifest_builder", builder_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("VV2 mask stage-2 builder is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="vv2-origins-mask-") as temp_dir:
        temp_root = Path(temp_dir)
        source = temp_root / "stock.exe"
        output = temp_root / "stage2.exe"
        source.write_bytes(source_bytes)
        module.build(output, src_exe=source)
        return output.read_bytes()

# Exact caller-return addresses proven by the VV2 stock executable audit.  The
# wrappers compare the immediate caller return address so Island Event, Gong,
# and duplicate-collectible tech awards remain byte-for-byte native while
# ordinary positive awards can still use the save-scoped doubler.
TECH_DOUBLER_EXCLUDED_RETURNS = (
    0x4205AC,
    0x434351,
    0x44EA32,
    0x44ED52,
    0x44F202,
    0x463461,
    0x46346D,
    0x463479,
)
FOOD_DOUBLER_EXCLUDED_RETURNS = (
    0x420AE9,
    0x433FC6,
    0x44E9C3,
    0x44EDB9,
    0x44F0D9,
)


def caller_blacklist_asm(addresses: tuple[int, ...]) -> str:
    return "\n".join(
        f"cmp dword ptr [esp + 4], 0x{address:X}\n            je apply"
        for address in addresses
    )


def assemble(source: str, address: int) -> bytes:
    encoding, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoding)


def rel32_jump(source_va: int, target_va: int) -> bytes:
    return b"\xE9" + int(target_va - source_va - 5).to_bytes(
        4, "little", signed=True
    )


def add_c_string(blob: bytearray, labels: dict[str, int], name: str, value: str) -> None:
    labels[name] = STRINGS_VA + len(blob)
    blob.extend(value.encode("ascii") + b"\0")


def main() -> None:
    original = STOCK.read_bytes()
    expected_sha256 = (
        "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677"
    )
    actual_sha256 = hashlib.sha256(original).hexdigest().upper()
    if actual_sha256 != expected_sha256:
        raise RuntimeError(
            f"stock SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256}"
        )
    mask_stage2_output = build_vv2_mask_stage2_output(original)
    mask_append = mask_stage2_output[len(original) :]
    if (
        len(mask_append) != 0x2000
        or hashlib.sha256(mask_append).hexdigest().upper()
        != VV2_MASK_STAGE2_APPEND_SHA256
    ):
        raise RuntimeError("VV2 mask stage-2 append identity mismatch")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    strings = bytearray()
    s: dict[str, int] = {}
    for name, value in (
        ("button_label", "Upgrades"),
        ("tech_title", "Origins Upgrades"),
        ("detail_title", "Villager Upgrades"),
        ("purchased", "Purchased."),
        ("removed", "Removed."),
        ("not_enough", "Not enough tech points."),
        ("mastery_failed", "Full Mastery could not be completed."),
        ("paused", "Time Warp is unavailable while the game is paused."),
        (
            "population_capacity",
            "The village population is already close to its max. No tech points have been deducted.",
        ),
        (
            "permanent_warning",
            "This upgrade makes permanent changes to your village. Do you still want to purchase this?",
        ),
        ("running_unavailable", "Running cannot be added."),
        ("running_granted", "All villagers like running."),
        (
            "running_no_change",
            "No changes were needed. No tech points have been deducted.",
        ),
        ("icons_dll", "VVFP VV2 Origins Icons.dll"),
        ("show_dialog_export", "ShowVV2UpgradeMenuState"),
        ("show_result_export", "ShowOriginsVillageWideResult"),
        ("user32_dll", "USER32.dll"),
        ("message_box_export", "MessageBoxA"),
    ):
        add_c_string(strings, s, name, value)

    while len(strings) % 4:
        strings.append(0)
    s["tech_costs"] = STRINGS_VA + len(strings)
    for value in (50000, 30000, 75000, 500000, 500000, 30000):
        strings.extend(value.to_bytes(4, "little"))
    s["detail_costs"] = STRINGS_VA + len(strings)
    for value in (50000, 100000, 40000, 50000):
        strings.extend(value.to_bytes(4, "little"))
    s["vv2_skill_codes"] = STRINGS_VA + len(strings)
    for value in (2, 5, 1, 3, 4):
        strings.extend(value.to_bytes(4, "little"))
    if len(strings) > PAYLOAD_SIZE - STRINGS_OFFSET:
        raise RuntimeError(
            f"string/data block is too large: {len(strings):#x}/"
            f"{PAYLOAD_SIZE - STRINGS_OFFSET:#x}"
        )

    tech_handler = PAYLOAD_VA + 0x000
    tech_constructor = PAYLOAD_VA + 0x030
    detail_handler = PAYLOAD_VA + 0x0C0
    detail_constructor = PAYLOAD_VA + 0x0F0
    show_dialog = PAYLOAD_VA + 0x180
    show_message = PAYLOAD_VA + 0x1D0
    confirm_dialog = PAYLOAD_VA + 0x210
    # Keep a full gap after the confirmation helper (0x210..0x251).
    tech_menu = PAYLOAD_VA + 0x260
    detail_menu = PAYLOAD_VA + 0x500
    tech_increment = PAYLOAD_VA + 0x820
    food_increment = PAYLOAD_VA + 0x8A0
    event_dispatch = PAYLOAD_VA + 0x960

    code = bytearray(b"\0" * STRINGS_OFFSET)
    occupied = bytearray(b"\0" * STRINGS_OFFSET)

    def put(va: int, source: str) -> None:
        payload = assemble(source, va)
        start = va - PAYLOAD_VA
        end = start + len(payload)
        if start < 0 or end > len(code):
            raise RuntimeError(
                f"code at {va:#x} ({len(payload):#x} bytes) exceeds code block"
            )
        if any(occupied[start:end]):
            raise RuntimeError(f"code overlap at {va:#x}, size {len(payload):#x}")
        code[start:end] = payload
        occupied[start:end] = b"\1" * len(payload)

    put(
        tech_handler,
        f"""
            cmp dword ptr [esp + 4], 8
            jne original_handler
            cmp dword ptr [esp + 8], 2
            jne original_handler
            call 0x{tech_menu:X}
            xor eax, eax
            ret 8
        original_handler:
            cmp dword ptr [esp + 4], 8
            jmp 0x4437C5
        """,
    )

    put(
        tech_constructor,
        f"""
            push 0x14
            call 0x467F83
            add esp, 4
            test eax, eax
            je constructor_done
            push 0
            push esi
            push 563
            push 138
            push 0x4763E8
            push 2
            mov ecx, eax
            call 0x4019D0
            mov edi, eax
            push 0
            push 0xFF555555
            push 0xFF555555
            push 0xFF000000
            push 0x{s['button_label']:X}
            mov ecx, edi
            call 0x4015D0
            push edi
            mov ecx, esi
            call 0x40B560
        constructor_done:
            mov ecx, dword ptr [esp + 0x20]
            pop edi
            mov eax, esi
            pop esi
            pop ebp
            pop ebx
            mov dword ptr fs:[0], ecx
            add esp, 0x1C
            ret
        """,
    )

    put(
        detail_handler,
        f"""
            cmp dword ptr [esp + 4], 8
            jne original_handler
            cmp dword ptr [esp + 8], 6
            jne original_handler
            call 0x{detail_menu:X}
            xor eax, eax
            ret 8
        original_handler:
            cmp dword ptr [esp + 4], 8
            jmp 0x467725
        """,
    )

    put(
        detail_constructor,
        f"""
            push 0x14
            call 0x467F83
            add esp, 4
            test eax, eax
            je constructor_done
            push 0
            push esi
            push 563
            push 140
            push 0x4763E8
            push 6
            mov ecx, eax
            call 0x4019D0
            mov edi, eax
            push 0
            push 0xFF555555
            push 0xFF555555
            push 0xFF000000
            push 0x{s['button_label']:X}
            mov ecx, edi
            call 0x4015D0
            push edi
            mov ecx, esi
            call 0x40B560
        constructor_done:
            mov ecx, dword ptr [esp + 0x20]
            mov byte ptr [esi + 0x26], bl
            mov byte ptr [esi + 0x27], bl
            pop edi
            mov byte ptr [esi + 0x25], 1
            mov eax, esi
            pop esi
            pop ebx
            mov dword ptr fs:[0], ecx
            add esp, 0x20
            ret
        """,
    )

    put(
        show_dialog,
        f"""
            push ebx
            push esi
            push 0x{s['icons_dll']:X}
            call dword ptr [0x474010]
            test eax, eax
            je unavailable
            push 0x{s['show_dialog_export']:X}
            push eax
            call dword ptr [0x4740D4]
            test eax, eax
            je unavailable
            push dword ptr [esp + 0x10]
            push dword ptr [esp + 0x10]
            call eax
            pop esi
            pop ebx
            ret 8
        unavailable:
            mov eax, -1
            pop esi
            pop ebx
            ret 8
        """,
    )

    put(
        show_message,
        f"""
            push ebx
            push esi
            mov ebx, dword ptr [esp + 0x0C]
            mov esi, dword ptr [esp + 0x10]
            push 0x{s['user32_dll']:X}
            call dword ptr [0x474010]
            test eax, eax
            je message_done
            push 0x{s['message_box_export']:X}
            push eax
            call dword ptr [0x4740D4]
            test eax, eax
            je message_done
            push 0
            push ebx
            push esi
            push 0
            call eax
        message_done:
            pop esi
            pop ebx
            ret 8
        """,
    )

    # Task9-style OK/Cancel purchase confirm.  Takes the action id (tech rows
    # 0..10, detail rows 100..104) as its one stack argument and hands it to the
    # DLL's ConfirmVV2Upgrade, which builds the "<Action> for N tech points?"
    # box.  Returns 1 on OK, 0 on Cancel.
    put(
        confirm_dialog,
        f"""
            push ebx
            push esi
            push 0x{s['icons_dll']:X}
            call dword ptr [0x474010]
            test eax, eax
            je confirm_done
            push 0x{CONFIRM_EXPORT_VA:X}
            push eax
            call dword ptr [0x4740D4]
            test eax, eax
            je confirm_done
            push dword ptr [esp + 0x0C]
            call eax
            pop esi
            pop ebx
            ret 4
        confirm_done:
            xor eax, eax
            pop esi
            pop ebx
            ret 4
        """,
    )

    put(
        tech_menu,
        f"""
            push ebx
            push esi
            push edi
            push ebp
            mov esi, ecx
        menu_loop:
            mov edi, dword ptr [esi + 0x0C]
            xor eax, eax
            test dword ptr [edi + 0x2EAE8], 1
            jz tech_not_owned
            or eax, 8
        tech_not_owned:
            test dword ptr [edi + 0x2EAE8], 2
            jz food_not_owned
            or eax, 16
        food_not_owned:
            push eax
            push 0
            call 0x{show_dialog:X}
            cmp eax, -1
            je menu_done
            mov ebx, eax

            # An owned Tech/Food Doubler is an explicit Remove action.  Verify
            # ownership at click time and go straight to the existing removal
            # path; only an unowned row reaches the purchase confirmation.
            mov edi, dword ptr [esi + 0x0C]
            cmp ebx, 3
            je maybe_remove_tech
            cmp ebx, 4
            jne cure_preflight_before_confirm
            test dword ptr [edi + 0x2EAE8], 2
            jz cure_preflight_before_confirm
            jmp tech_purchase_ready
        maybe_remove_tech:
            test dword ptr [edi + 0x2EAE8], 1
            jz cure_preflight_before_confirm
            jmp tech_purchase_ready

            # Cure All is the only legacy row whose apply helper mutates a
            # 256-record village.  Dry-scan it before asking for confirmation:
            # no-change and invalid villages get the status-based Origins
            # result immediately, with no prompt and no charge.
        cure_preflight_before_confirm:
            cmp ebx, 5
            jne confirm_purchase
            call 0x{CURE_PREFLIGHT_VA:X}
            cmp eax, 0
            je confirm_purchase
            push eax
            push ebx
            call 0x{RESULT_HELPER_VA:X}
            jmp menu_done
        confirm_purchase:
            push ebx
            call 0x{confirm_dialog:X}
            test eax, eax
            jz menu_loop
        tech_purchase_ready:
            # The menu/confirmation helpers may use EDI internally.  The
            # stock handler reacquires its village object from [ESI+0x0C]
            # before each native read/write; do the same before any command
            # reaches the capacity, charge, or removal paths.
            mov edi, dword ptr [esi + 0x0C]

            cmp ebx, 3
            jb preflight
            cmp ebx, 5
            jae preflight
            cmp ebx, 4
            je maybe_remove_food
            test dword ptr [edi + 0x2EAE8], 1
            jz preflight
            and dword ptr [edi + 0x2EAE8], 0xFFFFFFFE
            push 5
            push ebx
            call 0x{RESULT_HELPER_VA:X}
            jmp menu_done
        maybe_remove_food:
            test dword ptr [edi + 0x2EAE8], 2
            jz preflight
            and dword ptr [edi + 0x2EAE8], 0xFFFFFFFD
            push 5
            push ebx
            call 0x{RESULT_HELPER_VA:X}
            jmp menu_done

        preflight:
            cmp ebx, 0
            jne maybe_barrel
            cmp dword ptr [edi + 0x2EB08], 999
            jne charge
            mov eax, 0x{s['paused']:X}
            jmp show_status
        maybe_barrel:
            cmp ebx, 2
            jne charge
            jmp barrel_capacity_preflight

        charge:
            cmp ebx, 6
            jb legacy_charge
            # Change Appearance for All (row 13): the companion DLL runs the
            # popup, does its OWN 450,000 charge (given the tech-balance pointer)
            # and applies to every villager, so the Tech menu neither confirms
            # nor charges here -- just hand off to the dispatch stub.
            cmp ebx, 13
            je caf_dispatch
            # ebx = 6 (Running), 7 (Full Mastery), 8 (Set All 18),
            # 9 (Complete Collections), 10 (Reset Collections): require the
            # 1,000,000, hand off to the DLL dispatch stub (it applies and shows
            # its own result), then charge ONLY if it reports a real change in
            # EAX.  No-change rows leave the balance untouched.
            cmp dword ptr [edi + 0x2EADC], 1000000
            jb insufficient
            call 0x{DISPATCH_VA:X}
            mov edi, dword ptr [esi + 0x0C]
            test eax, eax
            jz menu_done
            sub dword ptr [edi + 0x2EADC], 1000000
            jmp menu_done
        caf_dispatch:
            call 0x{DISPATCH_VA:X}
            jmp menu_done
        legacy_charge:
            cmp ebx, 5
            je do_cure
        legacy_charge_ready:
            mov eax, dword ptr [0x{s['tech_costs']:X} + ebx*4]
            cmp ebx, 2
            je barrel_capacity_preflight
            cmp dword ptr [edi + 0x2EADC], eax
            jb insufficient
            sub dword ptr [edi + 0x2EADC], eax
            cmp ebx, 0
            je do_time_warp
            cmp ebx, 1
            je do_island_event
            cmp ebx, 2
            je barrel_capacity_preflight
            cmp ebx, 3
            je do_tech_doubler
            cmp ebx, 4
            je do_food_doubler
            cmp ebx, 5
            je do_cure
            call 0x{HEAL_CAVE_VA:X}
            nop
            jmp success

        barrel_capacity_preflight:
            cmp byte ptr [0x{BARREL_PENDING_VA:X}], 0
            jne menu_done
            # The Tech menu's EDI is the VV2 player object loaded from [ESI+0x0C].
            # Its first dereference is [ECX+0x305A4], so reject an uninitialized
            # record-pool chain before the DLL reads population.
            mov ecx, edi
            test ecx, ecx
            jz barrel_capacity_unavailable
            cmp dword ptr [ecx + 0x305A4], 0
            jz barrel_capacity_unavailable
            # Ask the companion DLL whether the village can hold 3 more villagers
            # (it reads current demand and the real, collection-dependent cap).
            # EAX = 0 means full: it already showed the "close to maximum" notice,
            # so charge nothing.  EAX = 1 means there is room for all 3 children.
            push edi
            call 0x{BARREL_GATE_VA:X}
            test eax, eax
            jz menu_done
            mov eax, dword ptr [0x{s['tech_costs']:X} + ebx*4]
            cmp dword ptr [edi + 0x2EADC], eax
            jb barrel_insufficient
            sub dword ptr [edi + 0x2EADC], eax
            mov byte ptr [0x{BARREL_PENDING_VA:X}], 1
            push 0
            push ebx
            call 0x{RESULT_HELPER_VA:X}
            jmp menu_done
        barrel_insufficient:
            mov eax, 0x{s['not_enough']:X}
            jmp show_status
        barrel_capacity_unavailable:
            mov eax, 0x{s['population_capacity']:X}
            jmp show_status

        do_cure:
            call 0x{HEAL_CAVE_VA:X}
            jmp menu_done

        do_village_wide:
            call 0x{HEAL_CAVE_VA:X}
            jmp menu_done

        do_time_warp:
            mov eax, dword ptr [edi + 0x2EB08]
            cmp eax, 3
            je time_apply
            cmp eax, 10
            je time_apply
            mov eax, 6
        time_apply:
            imul eax, eax, 3600
            sub dword ptr [0x4950F0], eax
            jmp success

        do_island_event:
            mov dword ptr [edi + 0x2EAE0], 0
            jmp success

        do_tech_doubler:
            or dword ptr [edi + 0x2EAE8], 1
            jmp success
        do_food_doubler:
            or dword ptr [edi + 0x2EAE8], 2
        success:
            push 0
            push ebx
            call 0x{RESULT_HELPER_VA:X}
            jmp menu_done
        insufficient:
            mov eax, 0x{s['not_enough']:X}
        show_status:
            push eax
            push 0x{s['tech_title']:X}
            call 0x{show_message:X}
            jmp menu_done
        menu_done:
            pop ebp
            pop edi
            pop esi
            pop ebx
            ret
        """,
    )

    put(
        detail_menu,
        f"""
            push ebx
            push esi
            push edi
            push ebp
            mov esi, ecx
        detail_loop:
            mov eax, dword ptr [esi + 0x0C]
            mov ecx, dword ptr [eax + 0x304F0]
            cmp ecx, 0x100
            jae detail_done
            imul ecx, ecx, 0xE48C
            mov edx, dword ptr [esi + 0x10]
            add edx, ecx
            cmp byte ptr [edx + 0x30], 0
            je detail_done
            xor edi, edi
            cmp dword ptr [edx + 0x530], 100
            ja youth_not_done
            or edi, 1
        youth_not_done:
            cmp dword ptr [edx + 0x7E4], 100
            jne mastery_not_done
            cmp dword ptr [edx + 0x7E8], 100
            jne mastery_not_done
            cmp dword ptr [edx + 0x7EC], 100
            jne mastery_not_done
            cmp dword ptr [edx + 0x7F0], 100
            jne mastery_not_done
            cmp dword ptr [edx + 0x7F4], 100
            jne mastery_not_done
            or edi, 2
        mastery_not_done:
            xor ebp, ebp
            lea eax, [edx + 0x5F0]
            mov ecx, 62
        running_like_scan:
            cmp dword ptr [eax], {RUNNING_PREFERENCE_ID}
            je running_like_found
            cmp dword ptr [eax], -1
            jne running_like_next
            or ebp, 1
        running_like_next:
            add eax, 4
            dec ecx
            jne running_like_scan
            test ebp, 1
            jnz running_state_done
            or edi, 0x400
            jmp running_state_done
        running_like_found:
            or ebp, 2
        running_state_done:
            lea eax, [edx + 0x6E8]
            mov ecx, 62
        running_dislike_scan:
            cmp dword ptr [eax], {RUNNING_PREFERENCE_ID}
            jne running_dislike_next
            or ebp, 4
        running_dislike_next:
            add eax, 4
            dec ecx
            jne running_dislike_scan
            test ebp, 2
            jz running_no_like
            test ebp, 4
            jnz running_check_done
            or edi, 4
            jmp running_check_done
        running_no_like:
            test ebp, 1
            jnz running_check_done
            or edi, 0x400
        running_check_done:
            cmp dword ptr [edx + 0x530], 360
            jne age_not_done
            or edi, 8
        age_not_done:
            push edi
            push 1
            call 0x{show_dialog:X}
            cmp eax, -1
            je detail_done
            mov ebx, eax

            lea eax, [ebx + 100]
            push eax
            call 0x{confirm_dialog:X}
            test eax, eax
            jz detail_loop

            cmp ebx, 4
            jne detail_purchase_ready
            call 0x{APPEARANCE_VA:X}
            jmp detail_loop
        detail_purchase_ready:

            mov edi, dword ptr [esi + 0x0C]
            mov ecx, dword ptr [edi + 0x304F0]
            cmp ecx, 0x100
            jae detail_done
            imul ecx, ecx, 0xE48C
            mov edx, dword ptr [esi + 0x10]
            add edx, ecx
            cmp byte ptr [edx + 0x30], 0
            je detail_done
            # Per-row no-change check (in .shr).  Returns 1 and shows the
            # row-specific message when the purchase would change nothing (so we
            # charge nothing); returns 0 to proceed to the charge.  EDX (the
            # record) is preserved on the charge path.
            push ebx
            push edx
            call 0x{DETAIL_NOCHANGE_VA:X}
            test eax, eax
            jnz detail_loop

        detail_charge:
            mov eax, dword ptr [0x{s['detail_costs']:X} + ebx*4]
            cmp dword ptr [edi + 0x2EADC], eax
            jb detail_insufficient
            sub dword ptr [edi + 0x2EADC], eax
            cmp ebx, 0
            je detail_youth
            cmp ebx, 1
            je detail_mastery
            cmp ebx, 2
            je detail_running
            mov dword ptr [edx + 0x530], 360
            mov dword ptr [edx + 0x534], 360
            cmp dword ptr [edx + 0x540], 0
            je detail_success
            mov dword ptr [edx + 0x540], 318
            jmp detail_success

        detail_youth:
            mov eax, dword ptr [edx + 0x530]
            sub eax, 700
            cmp eax, 100
            jge youth_ready
            mov eax, 100
        youth_ready:
            mov dword ptr [edx + 0x530], eax
            cmp dword ptr [edx + 0x540], 0
            je youth_not_pregnant
            lea ecx, [eax - 1]
            mov dword ptr [edx + 0x534], ecx
            sub eax, 42
            mov dword ptr [edx + 0x540], eax
            jmp detail_success
        youth_not_pregnant:
            mov dword ptr [edx + 0x534], eax
            jmp detail_success

        detail_mastery:
            mov dword ptr [edx + 0x7E4], 100
            mov dword ptr [edx + 0x7E8], 100
            mov dword ptr [edx + 0x7EC], 100
            mov dword ptr [edx + 0x7F0], 100
            mov dword ptr [edx + 0x7F4], 100
            jmp detail_success

        detail_running:
            xor ebp, ebp
            xor edi, edi
            lea ecx, [edx + 0x5F0]
            mov eax, 62
        running_find_like:
            cmp dword ptr [ecx], {RUNNING_PREFERENCE_ID}
            jne running_check_empty
            or ebp, 1
        running_check_empty:
            cmp dword ptr [ecx], -1
            jne running_next_like
            test edi, edi
            jnz running_next_like
            mov edi, ecx
        running_next_like:
            add ecx, 4
            dec eax
            jne running_find_like
            test ebp, 1
            jnz detail_success
            test edi, edi
            jz detail_success
            mov dword ptr [edi], {RUNNING_PREFERENCE_ID}
        running_remove_dislikes:
            lea ecx, [edx + 0x6E8]
            mov eax, 62
        running_dislike_loop:
            cmp dword ptr [ecx], {RUNNING_PREFERENCE_ID}
            jne running_next_dislike
            mov dword ptr [ecx], -1
        running_next_dislike:
            add ecx, 4
            dec eax
            jne running_dislike_loop
        detail_success:
            lea eax, [ebx + 100]
            push 0
            push eax
            call 0x{RESULT_HELPER_VA:X}
            jmp detail_loop
        detail_insufficient:
            mov eax, 0x{s['not_enough']:X}
        detail_status:
            push eax
            push 0x{s['detail_title']:X}
            call 0x{show_message:X}
            jmp detail_loop
        detail_done:
            pop ebp
            pop edi
            pop esi
            pop ebx
            ret
        """,
    )

    put(
        tech_increment,
        f"""
            push ebx
            mov ebx, ecx
            mov eax, dword ptr [esp + 8]
            test eax, eax
            jle apply
            {caller_blacklist_asm(TECH_DOUBLER_EXCLUDED_RETURNS)}
            test dword ptr [ebx + 0x2EAE8], 1
            jz apply
            shl dword ptr [esp + 8], 1
        apply:
            mov eax, dword ptr [esp + 8]
            add dword ptr [ebx + 0x2EADC], eax
            add dword ptr [ebx + 0x2E4FC], eax
            pop ebx
            ret 4
        """,
    )

    put(
        food_increment,
        f"""
            push ebx
            mov ebx, ecx
            mov eax, dword ptr [esp + 8]
            test eax, eax
            jle apply
            {caller_blacklist_asm(FOOD_DOUBLER_EXCLUDED_RETURNS)}
            test dword ptr [ebx + 0x2EAE8], 2
            jz apply
            shl dword ptr [esp + 8], 1
        apply:
            mov eax, dword ptr [esp + 8]
            add dword ptr [ebx + 0x2EAA4], eax
            add dword ptr [ebx + 0x2E504], eax
            pop ebx
            ret 4
        """,
    )

    put(
        event_dispatch,
        """
            cmp dword ptr [esp + 8], 0x7F4B1A2C
            jne original
            push 10
            push 21
            call 0x433600
            ret 8
        original:
            sub esp, 8
            mov eax, dword ptr [esp + 0x0C]
            jmp 0x434577
        """,
    )

    payload = code + strings
    patches: list[dict[str, str]] = []

    def patch(offset: int, before: bytes, after: bytes, purpose: str) -> None:
        actual = original[offset : offset + len(before)]
        if actual != before:
            raise RuntimeError(
                f"guard mismatch at {offset:#x}: expected {before.hex()}, "
                f"got {actual.hex()}"
            )
        if len(before) != len(after):
            raise RuntimeError(f"length mismatch at {offset:#x}")
        patches.append(
            {
                "offset": f"0x{offset:X}",
                "before": before.hex().upper(),
                "after": after.hex().upper(),
                "purpose": purpose,
            }
        )

    for mask_patch in VV2_MASK_STAGE2_PATCH_SPECS:
        offset = int(mask_patch["offset"], 16)
        before = bytes.fromhex(mask_patch["before"])
        patch(
            offset,
            before,
            mask_stage2_output[offset : offset + len(before)],
            mask_patch["purpose"],
        )

    cure_code = assemble(
        f"""
            cmp ebx, 5
            je cure_all
            cmp ebx, 6
            jb unsupported_village
            cmp ebx, 8
            ja unsupported_village
            jmp running_village
        unsupported_village:
            mov eax, 0x{s['running_unavailable']:X}
            push eax
            push 0x{s['tech_title']:X}
            call 0x{show_message:X}
            ret
        running_village:
            push ebx
            push ebp
            push ecx
            push edx
            push esi
            push edi
            mov eax, ebx
            call 0x44F4E0
            test eax, eax
            je village_wide_done
            lea ecx, [eax + 0x52C]
            mov eax, ebx
            mov edx, 256
            call 0x{VILLAGE_WIDE_ENTRY_VA:X}
            mov ebp, eax
            mov edi, edx
            mov esi, ecx
            cmp ebx, 6
            jne village_wide_status
            mov eax, 0x{s['show_result_export']:X}
            push 0x{s['icons_dll']:X}
            call dword ptr [0x474010]
            test eax, eax
            je village_wide_status
            push 0x{s['show_result_export']:X}
            push eax
            call dword ptr [0x4740D4]
            test eax, eax
            je village_wide_status
            push esi
            push edi
            push ebp
            push dword ptr [0x{RUNNING_GRANTED_VA:X}]
            push ebx
            call eax
            jmp village_wide_done
        village_wide_status:
            mov eax, 0x{s['purchased']:X}
            push eax
            push 0x{s['tech_title']:X}
            call 0x{show_message:X}
        village_wide_done:
            pop edi
            pop esi
            pop edx
            pop ecx
            pop ebp
            pop ebx
            ret
        cure_all:
            push ebx
            push ebp
            push ecx
            push edx
            push esi
            push edi
            xor ebx, ebx
            xor ebp, ebp
            # The helper's dry scan returns the existing result status model:
            # 0 = a real change is available, 1 = no change, 3 = invalid.
            # It performs no health, sickness, or statistics writes.
            call 0x{CURE_PREFLIGHT_VA:X}
            test eax, eax
            jnz cure_status_result

            # Reacquire the record base, then perform the balance gate
            # immediately before the first health/sickness/statistics write.
            # The final charge remains below the apply loop, so an unexpected
            # no-change race is not charged.
            call 0x44F4E0
            test eax, eax
            je cure_invalid_after_recheck
            mov edx, eax
            cmp dword ptr [edi + 0x2EADC], 30000
            jb cure_insufficient
            mov ecx, 256
        cure_loop:
            cmp byte ptr [edx + 0x30], 0
            je cure_next
            cmp dword ptr [edx + 0x52C], 0
            jle cure_next
            cmp byte ptr [edx + 0x558], 0
            jne cure_next
            cmp dword ptr [edx + 0x52C], 100
            jge cure_health_done
            mov dword ptr [edx + 0x52C], 100
            inc ebp
        cure_health_done:
            cmp dword ptr [edx + 0x53C], 0
            je cure_next
            mov dword ptr [edx + 0x53C], 0
            inc dword ptr [edi + 0x2E508]
            inc ebx
        cure_next:
            add edx, 0xE48C
            dec ecx
            jne cure_loop
            mov eax, ebx
            or eax, ebp
            jz cure_no_change_after_recheck
            sub dword ptr [edi + 0x2EADC], 30000
            jmp cure_report
        cure_insufficient:
            mov eax, 2
            jmp cure_status_result
        cure_invalid_after_recheck:
            mov eax, 3
            jmp cure_status_result
        cure_no_change_after_recheck:
            mov eax, 1
        cure_status_result:
            push eax
            push 5
            call 0x{RESULT_HELPER_VA:X}
            jmp cure_ret
        cure_report:
            push 0x{s['icons_dll']:X}
            call dword ptr [0x474010]
            test eax, eax
            je cure_ret
            push 0x{CURE_STRING_VA:X}
            push eax
            call dword ptr [0x4740D4]
            test eax, eax
            je cure_ret
            push ebp
            push ebx
            call eax
        cure_ret:
            pop edi
            pop esi
            pop edx
            pop ecx
            pop ebp
            pop ebx
            ret
        """,
        HEAL_CAVE_VA,
    )
    if len(cure_code) > 0x1A0:
        raise RuntimeError(
            f"cure code is too large: {len(cure_code):#x}/0x1A0"
        )
    cure_block = (
        cure_code
        + b"\0" * (0x1A0 - len(cure_code))
        + b"ShowVV2CureResult\0"
    )
    preflight_code = assemble(
        f"""
            cmp dword ptr [0x{VILLAGE_WIDE_SIGNATURE_VA:X}], 0x50465656
            jne preflight_invalid
            cmp dword ptr [0x{VILLAGE_WIDE_SIGNATURE_VA + 4:X}], 0x0055574F
            jne preflight_invalid
            cmp dword ptr [0x{VILLAGE_WIDE_SIGNATURE_VA + 8:X}], 0x00200001
            jne preflight_invalid
            cmp dword ptr [0x{VILLAGE_WIDE_SIGNATURE_VA + 0x10:X}], 3
            jne preflight_invalid
            cmp dword ptr [0x{VILLAGE_WIDE_SIGNATURE_VA + 0x14:X}], 0
            jne preflight_invalid
            cmp dword ptr [0x{VILLAGE_WIDE_SIGNATURE_VA + 0x18:X}], 0
            jne preflight_invalid
            cmp dword ptr [0x{VILLAGE_WIDE_SIGNATURE_VA + 0x1C:X}], 0
            jne preflight_invalid
            mov eax, 0x{s['show_result_export']:X}
            push 0x{s['icons_dll']:X}
            call dword ptr [0x474010]
            test eax, eax
            je preflight_invalid
            push 0x{s['show_result_export']:X}
            push eax
            call dword ptr [0x4740D4]
            test eax, eax
            je preflight_invalid
            call 0x44F4E0
            test eax, eax
            je preflight_invalid
            lea edx, [eax + 0x52C]
            push ebx
            push ebp
            push ecx
            push edx
            push edi
            cmp ebx, 7
            je preflight_mastery
            cmp ebx, 8
            je preflight_age
            mov ecx, 256
        preflight_record:
            cmp byte ptr [edx + 0x30], 0
            je preflight_next_record
            cmp dword ptr [edx + 0x52C], 0
            jle preflight_next_record
            cmp byte ptr [edx + 0x558], 0
            jne preflight_next_record
            xor ebp, ebp
            lea edi, [edx + 0x5F0]
            mov ebx, 62
        preflight_likes:
            cmp dword ptr [edi], {RUNNING_PREFERENCE_ID}
            jne preflight_like_empty
            or ebp, 1
        preflight_like_empty:
            cmp dword ptr [edi], -1
            jne preflight_like_next
            or ebp, 2
        preflight_like_next:
            add edi, 4
            dec ebx
            jne preflight_likes
            lea edi, [edx + 0x6E8]
            mov ebx, 62
            test ebp, 1
            jnz preflight_dislike_scan
            test ebp, 2
            jz preflight_next_record
        preflight_dislike_scan:
            cmp dword ptr [edi], {RUNNING_PREFERENCE_ID}
            je preflight_change
            add edi, 4
            dec ebx
            jne preflight_dislike_scan
            test ebp, 1
            jnz preflight_next_record
            test ebp, 2
            jnz preflight_change
        preflight_mastery:
            mov ecx, 256
        preflight_mastery_record:
            cmp byte ptr [edx + 0x30], 0
            je preflight_mastery_next
            cmp dword ptr [edx + 0x52C], 0
            jle preflight_mastery_next
            cmp byte ptr [edx + 0x558], 0
            jne preflight_mastery_next
            cmp dword ptr [edx + 0x7E4], 100
            jne preflight_change
            cmp dword ptr [edx + 0x7E8], 100
            jne preflight_change
            cmp dword ptr [edx + 0x7EC], 100
            jne preflight_change
            cmp dword ptr [edx + 0x7F0], 100
            jne preflight_change
            cmp dword ptr [edx + 0x7F4], 100
            jne preflight_change
        preflight_mastery_next:
            add edx, 0xE48C
            dec ecx
            jne preflight_mastery_record
            jmp preflight_no_change
        preflight_age:
            mov ecx, 256
        preflight_age_record:
            cmp byte ptr [edx + 0x30], 0
            je preflight_age_next
            cmp dword ptr [edx + 0x52C], 0
            jle preflight_age_next
            cmp byte ptr [edx + 0x558], 0
            jne preflight_age_next
            cmp dword ptr [edx + 0x530], 360
            jne preflight_change
        preflight_age_next:
            add edx, 0xE48C
            dec ecx
            jne preflight_age_record
            jmp preflight_no_change
        preflight_next_record:
            add edx, 0xE48C
            dec ecx
            jne preflight_record
        preflight_no_change:
            pop edi
            pop edx
            pop ecx
            pop ebp
            pop ebx
            mov eax, 2
            ret
        preflight_change:
            pop edi
            pop edx
            pop ecx
            pop ebp
            pop ebx
            mov eax, 1
            ret
        preflight_invalid:
            xor eax, eax
            ret
        """,
        VILLAGE_PREFLIGHT_VA,
    )
    cure_preflight_code = assemble(
        """
            # Return the existing ShowVV2UpgradeResult status values directly:
            # 0 = real change, 1 = no change, 3 = no valid living villager.
            push ebx
            push ecx
            push edx
            xor ebx, ebx
            call 0x44F4E0
            test eax, eax
            je cure_preflight_invalid
            mov edx, eax
            mov ecx, 256
        cure_preflight_record:
            cmp byte ptr [edx + 0x30], 0
            je cure_preflight_next
            cmp dword ptr [edx + 0x52C], 0
            jle cure_preflight_next
            cmp byte ptr [edx + 0x558], 0
            jne cure_preflight_next
            mov ebx, 1
            cmp dword ptr [edx + 0x52C], 100
            jl cure_preflight_change
            cmp dword ptr [edx + 0x53C], 0
            jne cure_preflight_change
        cure_preflight_next:
            add edx, 0xE48C
            dec ecx
            jne cure_preflight_record
            test ebx, ebx
            jz cure_preflight_invalid
        cure_preflight_no_change:
            pop edx
            pop ecx
            pop ebx
            mov eax, 1
            ret
        cure_preflight_change:
            pop edx
            pop ecx
            pop ebx
            xor eax, eax
            ret
        cure_preflight_invalid:
            pop edx
            pop ecx
            pop ebx
            mov eax, 3
            ret
        """,
        CURE_PREFLIGHT_VA,
    )
    detail_preflight_code = assemble(
        f"""
            push ecx
            push edx
            push edi
            push ebp
            cmp ebx, 0
            je detail_preflight_youth
            cmp ebx, 1
            je detail_preflight_mastery
            cmp ebx, 2
            je detail_preflight_running
            cmp ebx, 3
            je detail_preflight_age
            jmp detail_preflight_no_change

        detail_preflight_youth:
            mov ecx, dword ptr [edx + 0x530]
            mov eax, ecx
            sub eax, 700
            cmp eax, 100
            jge detail_preflight_youth_target
            mov eax, 100
        detail_preflight_youth_target:
            cmp ecx, eax
            jne detail_preflight_change
            cmp dword ptr [edx + 0x540], 0
            jne detail_preflight_youth_pregnant
            cmp dword ptr [edx + 0x534], eax
            jne detail_preflight_change
            jmp detail_preflight_no_change
        detail_preflight_youth_pregnant:
            lea ecx, [eax - 1]
            cmp dword ptr [edx + 0x534], ecx
            jne detail_preflight_change
            sub eax, 42
            cmp dword ptr [edx + 0x540], eax
            jne detail_preflight_change
            jmp detail_preflight_no_change

        detail_preflight_mastery:
            cmp dword ptr [edx + 0x52C], 0
            jle detail_preflight_no_change
            cmp byte ptr [edx + 0x558], 0
            jne detail_preflight_no_change
            cmp dword ptr [edx + 0x7E4], 100
            jne detail_preflight_change
            cmp dword ptr [edx + 0x7E8], 100
            jne detail_preflight_change
            cmp dword ptr [edx + 0x7EC], 100
            jne detail_preflight_change
            cmp dword ptr [edx + 0x7F0], 100
            jne detail_preflight_change
            cmp dword ptr [edx + 0x7F4], 100
            jne detail_preflight_change
            jmp detail_preflight_no_change

        detail_preflight_running:
            xor ebp, ebp
            lea edi, [edx + 0x5F0]
            mov ecx, 62
        detail_preflight_likes:
            cmp dword ptr [edi], {RUNNING_PREFERENCE_ID}
            jne detail_preflight_like_empty
            or ebp, 1
        detail_preflight_like_empty:
            cmp dword ptr [edi], -1
            jne detail_preflight_like_next
            or ebp, 2
        detail_preflight_like_next:
            add edi, 4
            dec ecx
            jne detail_preflight_likes
            test ebp, 1
            jnz detail_preflight_no_change
            test ebp, 2
            jz detail_preflight_no_change
            lea edi, [edx + 0x6E8]
            mov ecx, 62
        detail_preflight_dislike_scan:
            cmp dword ptr [edi], {RUNNING_PREFERENCE_ID}
            je detail_preflight_change
            add edi, 4
            dec ecx
            jne detail_preflight_dislike_scan
            jmp detail_preflight_change

        detail_preflight_age:
            cmp dword ptr [edx + 0x530], 360
            jne detail_preflight_change
            cmp dword ptr [edx + 0x534], 360
            jne detail_preflight_change
            mov eax, dword ptr [edx + 0x540]
            test eax, eax
            je detail_preflight_no_change
            cmp eax, 318
            jne detail_preflight_change
        detail_preflight_no_change:
            pop ebp
            pop edi
            pop edx
            pop ecx
            xor eax, eax
            ret
        detail_preflight_change:
            pop ebp
            pop edi
            pop edx
            pop ecx
            mov eax, 1
            ret
        """,
        DETAIL_PREFLIGHT_VA,
    )
    # The DLL now owns the ENTIRE per-villager Change Appearance commit (chooser
    # dialog + 5,000 charge + record head/body & .mtab mask writes + sidecar
    # SAVE), so this handler is a trivial one-call bridge: resolve the villager
    # record + index and hand (player, record, idx) to ShowVV2AppearanceChooser.
    # Keeping it tiny is what guarantees it can never overrun its fixed 0x100 box
    # (a past version that did the sidecar save exe-side overran the neighbour).
    appearance_helper_code = assemble(
        f"""
            push ebp
            mov ebp, esp
            sub esp, 4
            push ebx
            push esi
            push edi
            mov edi, dword ptr [esi + 0x0C]      /* player object */
            mov eax, dword ptr [edi + 0x304F0]   /* selected villager index */
            cmp eax, 0x100
            jae appearance_done
            mov dword ptr [ebp - 4], eax         /* stash idx (edi/ebx survive the calls) */
            imul eax, eax, 0xE48C
            mov ebx, dword ptr [esi + 0x10]
            add ebx, eax                         /* record base */
            cmp byte ptr [ebx + 0x30], 0
            je appearance_done
            cmp dword ptr [ebx + 0x52C], 0
            jle appearance_done
            push 0x{s['icons_dll']:X}
            call dword ptr [0x474010]
            test eax, eax
            je appearance_done
            push 0x{APPEARANCE_STRING_VA:X}
            push eax
            call dword ptr [0x4740D4]
            test eax, eax
            je appearance_done
            push dword ptr [ebp - 4]             /* idx */
            push ebx                             /* record */
            push edi                             /* player */
            call eax                             /* ShowVV2AppearanceChooser(player, record, idx) @12 */
        appearance_done:
            pop edi
            pop esi
            pop ebx
            mov esp, ebp
            pop ebp
            ret
        """,
        APPEARANCE_VA,
    )
    if len(appearance_helper_code) > APPEARANCE_CODE_MAX:
        raise RuntimeError(
            f"appearance helper is too large: {len(appearance_helper_code):#x}/0x100"
        )
    appearance_block = (
        appearance_helper_code
        + b"\0" * (APPEARANCE_CODE_MAX - len(appearance_helper_code))
        + b"ShowVV2AppearanceChooser\0"
    )
    # Whole-village Tech upgrades applied directly (like Cure All): fetch the
    # record array through the certified manager (0x44F4E0 -> base-0x52C) and
    # write the proven fields for every active, living, non-special villager.
    # ebx carries the command (6 = Running, 7 = Full Mastery, 8 = Age 18).
    whole_village_code = assemble(
        f"""
            push ebp
            push esi
            push edi
            push ebx
            call 0x44F4E0
            test eax, eax
            je wv_done
            mov edx, eax
            mov ecx, 256
            mov ebx, dword ptr [esp]
        wv_loop:
            cmp byte ptr [edx + 0x30], 0
            je wv_next
            cmp dword ptr [edx + 0x52C], 0
            jle wv_next
            cmp byte ptr [edx + 0x558], 0
            jne wv_next
            cmp ebx, 8
            je wv_age
            cmp ebx, 7
            je wv_mastery
            push ecx
            xor ebp, ebp
            mov esi, -1
            lea edi, [edx + 0x5F0]
            mov ecx, 62
        wv_run_like:
            cmp dword ptr [edi], {RUNNING_PREFERENCE_ID}
            jne wv_run_notfound
            mov ebp, 1
        wv_run_notfound:
            cmp dword ptr [edi], -1
            jne wv_run_nextlike
            cmp esi, -1
            jne wv_run_nextlike
            mov esi, edi
        wv_run_nextlike:
            add edi, 4
            dec ecx
            jne wv_run_like
            test ebp, ebp
            jnz wv_run_dislikes
            cmp esi, -1
            je wv_run_end
            mov dword ptr [esi], {RUNNING_PREFERENCE_ID}
        wv_run_dislikes:
            lea edi, [edx + 0x6E8]
            mov ecx, 62
        wv_run_dis:
            cmp dword ptr [edi], {RUNNING_PREFERENCE_ID}
            jne wv_run_nextdis
            mov dword ptr [edi], -1
        wv_run_nextdis:
            add edi, 4
            dec ecx
            jne wv_run_dis
        wv_run_end:
            pop ecx
            jmp wv_next
        wv_mastery:
            mov dword ptr [edx + 0x7E4], 100
            mov dword ptr [edx + 0x7E8], 100
            mov dword ptr [edx + 0x7EC], 100
            mov dword ptr [edx + 0x7F0], 100
            mov dword ptr [edx + 0x7F4], 100
            jmp wv_next
        wv_age:
            mov dword ptr [edx + 0x530], 360
            mov dword ptr [edx + 0x534], 360
            cmp dword ptr [edx + 0x540], 0
            je wv_next
            mov dword ptr [edx + 0x540], 318
        wv_next:
            add edx, 0xE48C
            dec ecx
            jne wv_loop
        wv_done:
            pop ebx
            pop edi
            pop esi
            pop ebp
            ret
        """,
        WHOLE_VILLAGE_VA,
    )
    if len(whole_village_code) > 0x1C0:
        raise RuntimeError(
            f"whole-village helper is too large: {len(whole_village_code):#x}/0x1C0"
        )
    # One DLL-dispatch stub shared by the four village-wide upgrades that
    # delegate to the companion DLL.  Entered with EBX = command (6 Grant
    # Running, 7 Grant Full Mastery, 9 Complete Collections, 10 Reset
    # Collections) and EDI = the Tech-menu player object.  Running/Mastery pass
    # the certified record array (sub_44F4E0) to their reporting exports;
    # Collections pass the player object and the command as the mode.  The 1M
    # charge is done by the Tech menu before this is called.  Export-name strings
    # are packed tightly right after the code so the whole stub fits the .shr
    # tail; because every `push imm32` is a fixed five bytes, assembling once
    # with placeholder string VAs yields the final code length, which then fixes
    # the real string addresses for a second, identical-length assembly.
    def _dispatch_src(running_va: int, mastery_va: int, age_va: int,
                      collections_va: int, division_va: int, caf_ord: int) -> str:
        return f"""
            push ebp
            push esi
            push edi
            mov ebp, ebx
            push 0x{s['icons_dll']:X}
            call dword ptr [0x474010]
            test eax, eax
            je disp_done
            mov esi, eax
            cmp ebp, 13
            je disp_caf
            cmp ebp, 11
            jae disp_division
            cmp ebp, 9
            jae disp_collections
            mov eax, 0x{running_va:X}
            cmp ebp, 6
            je disp_name_ready
            mov eax, 0x{mastery_va:X}
            cmp ebp, 7
            je disp_name_ready
            mov eax, 0x{age_va:X}
        disp_name_ready:
            push eax
            push esi
            call dword ptr [0x4740D4]
            test eax, eax
            je disp_done
            mov edi, eax
            call 0x44F4E0
            push eax
            call edi
            jmp disp_done
        disp_collections:
            mov eax, 0x{collections_va:X}
            push eax
            push esi
            call dword ptr [0x4740D4]
            test eax, eax
            je disp_done
            push ebp
            push edi
            call eax
            jmp disp_done
        disp_division:
            # Equal Division of Labor: 11 = includes Parenting, 12 = no Parenting.
            # ApplyVV2EqualDivision(base = sub_44F4E0, parenting).
            mov eax, 0x{division_va:X}
            push eax
            push esi
            call dword ptr [0x4740D4]
            test eax, eax
            je disp_done
            mov edi, eax
            call 0x44F4E0
            xor ecx, ecx
            cmp ebp, 11
            jne disp_division_charge
            inc ecx
        disp_division_charge:
            push ecx
            push eax
            call edi
            jmp disp_done
        disp_caf:
            # Change Appearance for All.  EDI (from the caller) = Tech-menu player
            # object.  Resolve ShowVV2AppearanceForAll BY ORDINAL (no name string,
            # to fit the .shr slot) and call it with the player object; the DLL
            # computes the tech balance (+0x2EADC) and record array itself, runs
            # the popup, charges 450k and applies to every villager.
            push {caf_ord}
            push esi
            call dword ptr [0x4740D4]
            test eax, eax
            je disp_done
            push edi
            call eax
            jmp disp_done
        disp_done:
            pop edi
            pop esi
            pop ebp
            ret
        """

    # ShowVV2AppearanceForAll is resolved by ORDINAL (pinned @100 in the .def),
    # so the dispatch stub needs no name string for it -- keeps it inside the
    # tight .shr slot ahead of the Barrel gate.
    CAF_ORDINAL = 100
    _placeholder = DISPATCH_VA + 0x100
    dispatch_len = len(
        assemble(
            _dispatch_src(
                _placeholder, _placeholder, _placeholder, _placeholder,
                _placeholder, CAF_ORDINAL
            ),
            DISPATCH_VA,
        )
    )
    running_export_bytes = b"ApplyVV2RunningToAll\0"
    mastery_export_bytes = b"ApplyVV2MasteryToAll\0"
    age_export_bytes = b"ApplyVV2AgeToAll\0"
    collections_export_bytes = b"ApplyVV2Collections\0"
    division_export_bytes = b"ApplyVV2EqualDivision\0"
    running_export_va = DISPATCH_VA + dispatch_len
    mastery_export_va = running_export_va + len(running_export_bytes)
    age_export_va = mastery_export_va + len(mastery_export_bytes)
    collections_export_va = age_export_va + len(age_export_bytes)
    division_export_va = collections_export_va + len(collections_export_bytes)
    dispatch_code = assemble(
        _dispatch_src(
            running_export_va, mastery_export_va, age_export_va,
            collections_export_va, division_export_va, CAF_ORDINAL
        ),
        DISPATCH_VA,
    )
    assert len(dispatch_code) == dispatch_len
    dispatch_block = (
        dispatch_code
        + running_export_bytes
        + mastery_export_bytes
        + age_export_bytes
        + collections_export_bytes
        + division_export_bytes
    )
    if DISPATCH_FILE_OFFSET + len(dispatch_block) > BARREL_GATE_FILE_OFFSET:
        raise RuntimeError(
            f"dispatch stub overruns the Barrel-gate slot: "
            f"0x{DISPATCH_FILE_OFFSET + len(dispatch_block):X} > "
            f"0x{BARREL_GATE_FILE_OFFSET:X}"
        )
    # Barrel capacity-gate stub: entered as (pool) -> EAX 1 = room for the
    # Barrel's 3 children, 0 = full (the DLL already showed the "close to
    # maximum" notice) or the companion DLL is missing.  Mirrors the dispatch /
    # result stubs' LoadLibrary + GetProcAddress handshake, then calls the
    # GateVV2Barrel export (which does the population read and cap math).  The
    # export-name string is packed right after the code; assembling once with a
    # placeholder VA fixes the code length, then the real string VA.
    def _barrel_gate_src(export_va: int) -> str:
        return f"""
            push esi
            mov esi, dword ptr [esp + 8]
            push 0x{s['icons_dll']:X}
            call dword ptr [0x474010]
            test eax, eax
            je bg_block
            push 0x{export_va:X}
            push eax
            call dword ptr [0x4740D4]
            test eax, eax
            je bg_block
            push esi
            call eax
            pop esi
            ret 4
        bg_block:
            xor eax, eax
            pop esi
            ret 4
        """

    _bg_placeholder = BARREL_GATE_VA + 0x100
    barrel_gate_len = len(
        assemble(_barrel_gate_src(_bg_placeholder), BARREL_GATE_VA)
    )
    barrel_gate_export_va = BARREL_GATE_VA + barrel_gate_len
    barrel_gate_code = assemble(
        _barrel_gate_src(barrel_gate_export_va), BARREL_GATE_VA
    )
    assert len(barrel_gate_code) == barrel_gate_len
    barrel_gate_block = barrel_gate_code + BARREL_GATE_EXPORT_BYTES
    if BARREL_GATE_FILE_OFFSET + len(barrel_gate_block) > 0x9B000:
        raise RuntimeError(
            f"Barrel-gate stub overruns the .shr reserve: "
            f"0x{BARREL_GATE_FILE_OFFSET + len(barrel_gate_block):X} > 0x9B000"
        )
    # Result trampoline: payload success/doubler paths call this with
    # (action, status); it forwards to the DLL's ShowVV2UpgradeResult so the
    # simple rows render "<Action> completed." / doubler text instead of the old
    # flat "Purchased."  Counts are zero here (the counted rows report from the
    # DLL directly).
    result_helper_code = assemble(
        f"""
            push ebx
            push esi
            mov ebx, dword ptr [esp + 0x0C]
            mov esi, dword ptr [esp + 0x10]
            push 0x{s['icons_dll']:X}
            call dword ptr [0x474010]
            test eax, eax
            je rh_done
            push 0x{RESULT_EXPORT_VA:X}
            push eax
            call dword ptr [0x4740D4]
            test eax, eax
            je rh_done
            push 0
            push 0
            push 0
            push 0
            push esi
            push ebx
            call eax
        rh_done:
            pop esi
            pop ebx
            ret 8
        """,
        RESULT_HELPER_VA,
    )
    if RESULT_HELPER_FILE_OFFSET + len(result_helper_code) > 0x9A280:
        raise RuntimeError(
            f"result helper overruns its .shr gap: "
            f"0x{RESULT_HELPER_FILE_OFFSET + len(result_helper_code):X} > 0x9A280"
        )
    # Detail per-row no-change check.  Args (record, row).  Returns 1 (charge
    # nothing; message already shown) when the row is already satisfied, else 0.
    # EDX is only read, so on the return-0 path the caller's record pointer
    # survives for the charge/apply code.
    detail_nochange_code = assemble(
        f"""
            push ebx
            push esi
            push edi
            mov edx, dword ptr [esp + 0x10]
            mov ebx, dword ptr [esp + 0x14]
            cmp ebx, 0
            je dnc_youth
            cmp ebx, 1
            je dnc_mastery
            cmp ebx, 2
            je dnc_running
            cmp dword ptr [edx + 0x530], 360
            jne dnc_charge
            mov esi, 1
            jmp dnc_show
        dnc_youth:
            cmp dword ptr [edx + 0x530], 100
            jg dnc_charge
            mov esi, 1
            jmp dnc_show
        dnc_mastery:
            cmp dword ptr [edx + 0x7E4], 100
            jne dnc_charge
            cmp dword ptr [edx + 0x7E8], 100
            jne dnc_charge
            cmp dword ptr [edx + 0x7EC], 100
            jne dnc_charge
            cmp dword ptr [edx + 0x7F0], 100
            jne dnc_charge
            cmp dword ptr [edx + 0x7F4], 100
            jne dnc_charge
            mov esi, 1
            jmp dnc_show
        dnc_running:
            xor edi, edi
            lea ecx, [edx + 0x5F0]
            mov eax, 62
        dnc_run_scan:
            cmp dword ptr [ecx], {RUNNING_PREFERENCE_ID}
            jne dnc_run_notrun
            or edi, 1
        dnc_run_notrun:
            cmp dword ptr [ecx], -1
            jne dnc_run_next
            or edi, 2
        dnc_run_next:
            add ecx, 4
            dec eax
            jne dnc_run_scan
            test edi, 1
            jz dnc_run_notliked
            mov esi, 1
            jmp dnc_show
        dnc_run_notliked:
            test edi, 2
            jnz dnc_charge
            # Likes are full: Running can't be added.  Match Grant Running to
            # All -- still clear any Running dislike (for free, since the Like
            # couldn't be added) and report it.  If there is no Running dislike
            # either, it's a true no-op ("full Likes slots").
            lea ecx, [edx + 0x6E8]
            mov eax, 62
            xor edi, edi
        dnc_dislike_scan:
            cmp dword ptr [ecx], {RUNNING_PREFERENCE_ID}
            jne dnc_dislike_next
            mov dword ptr [ecx], -1
            mov edi, 1
        dnc_dislike_next:
            add ecx, 4
            dec eax
            jne dnc_dislike_scan
            test edi, edi
            jz dnc_run_full
            mov esi, 8
            jmp dnc_show
        dnc_run_full:
            mov esi, 4
        dnc_show:
            push esi
            lea eax, [ebx + 100]
            push eax
            call 0x{RESULT_HELPER_VA:X}
            mov eax, 1
            jmp dnc_ret
        dnc_charge:
            xor eax, eax
        dnc_ret:
            pop edi
            pop esi
            pop ebx
            ret 8
        """,
        DETAIL_NOCHANGE_VA,
    )
    if DETAIL_NOCHANGE_FILE_OFFSET + len(detail_nochange_code) > 0x9A530:
        raise RuntimeError(
            f"detail no-change helper overruns its .shr gap: "
            f"0x{DETAIL_NOCHANGE_FILE_OFFSET + len(detail_nochange_code):X} > 0x9A530"
        )
    # Barrel main-village helper: defer the queued Barrel event by counting down
    # BARREL_CUE_FRAMES ticks of the per-frame update after the Tech screen
    # closes, so it plays cued during gameplay instead of flashing by during the
    # menu-close transition.  Token 0x49C700: 1 = purchased, 2 = screen closed,
    # 3 = counting down, 0 = idle.
    barrel_main_code = assemble(
        f"""
            cmp byte ptr [0x{BARREL_PENDING_VA:X}], 3
            je barrel_ticking
            cmp byte ptr [0x{BARREL_PENDING_VA:X}], 2
            jne barrel_resume
            mov byte ptr [0x{BARREL_PENDING_VA:X}], 3
            mov dword ptr [0x{BARREL_CUE_COUNTER_VA:X}], {BARREL_CUE_FRAMES}
            jmp barrel_resume
        barrel_ticking:
            dec dword ptr [0x{BARREL_CUE_COUNTER_VA:X}]
            jnz barrel_resume
            mov byte ptr [0x{BARREL_PENDING_VA:X}], 0
            sub esp, 0x50D8
            push 0x7F4B1A2C
            push 2
            lea ecx, [esp + 8]
            call 0x4348E0
            push 0
            push esi
            lea ecx, [esp + 8]
            call 0x401AD0
            mov ecx, esp
            call 0x433190
            add esp, 0x50D8
        barrel_resume:
            mov ecx, edi
            call 0x403200
            jmp 0x42E9F5
        """,
        BARREL_MAIN_HELPER_VA,
    )
    if len(barrel_main_code) > 0x80:
        raise RuntimeError(
            f"barrel main helper is too large: {len(barrel_main_code):#x}/0x80"
        )
    patch(
        HEAL_CAVE_FILE_OFFSET,
        b"\0" * 5,
        rel32_jump(
            IMAGE_BASE + SHR_RVA + (HEAL_CAVE_FILE_OFFSET - SHR_FILE_OFFSET),
            CURE_ENTRY_VA,
        ),
        "redirect the shared VV2 Cure/village-wide dispatch stub to its certified helper after the optional Origins reserve",
    )
    patch(
        CURE_ENTRY_FILE_OFFSET,
        b"\0" * len(cure_block),
        cure_block,
        "recheck the active Cure preflight and 30,000-tech balance before any health, sickness, or statistics write; apply only a real change, charge once, and report through the VV2 Origins result/status model",
    )
    patch(
        VILLAGE_PREFLIGHT_FILE_OFFSET,
        b"\0" * len(preflight_code),
        preflight_code,
        "validate the optional Origins dependency and dry-scan all 256 living records and all 62 Like and Dislike slots before any village-wide Running charge",
    )
    patch(
        CURE_PREFLIGHT_FILE_OFFSET,
        b"\0" * len(cure_preflight_code),
        cure_preflight_code,
        "active Cure-row dry-scan of all 256 records before confirmation; return VV2 no-change/invalid status before prompting and gate the final apply on funds",
    )
    patch(
        BARREL_PENDING_FILE_OFFSET,
        b"\0",
        b"\0",
        "reserve the process-local one-shot VV2 Barrel event token",
    )
    patch(
        BARREL_CLOSE_HELPER_FILE_OFFSET,
        b"\0" * len(BARREL_CLOSE_HELPER_CODE),
        BARREL_CLOSE_HELPER_CODE,
        "advance the purchased Barrel token only after the stock Technologies screen closes",
    )
    patch(
        BARREL_MAIN_HELPER_FILE_OFFSET,
        b"\0" * len(barrel_main_code),
        barrel_main_code,
        "count down the cue delay after the Tech screen closes, then enqueue the Barrel event through the stock village event pipeline so it plays cued during gameplay",
    )
    patch(
        APPEARANCE_FILE_OFFSET,
        b"\0" * len(appearance_block),
        appearance_block,
        "open the Change Appearance chooser for the selected active living villager and, on OK, charge 5,000 tech and write only the proven head and body fields",
    )
    patch(
        CONFIRM_EXPORT_FILE_OFFSET,
        b"\0" * len(CONFIRM_EXPORT_BYTES),
        CONFIRM_EXPORT_BYTES,
        "store the DLL export name for the Task9-style OK/Cancel purchase confirm",
    )
    patch(
        RESULT_EXPORT_FILE_OFFSET,
        b"\0" * len(RESULT_EXPORT_BYTES),
        RESULT_EXPORT_BYTES,
        "store the DLL export name for the Task9-style upgrade result renderer",
    )
    patch(
        RESULT_HELPER_FILE_OFFSET,
        b"\0" * len(result_helper_code),
        result_helper_code,
        "forward the payload's simple success and doubler results to the DLL result renderer",
    )
    patch(
        DETAIL_NOCHANGE_FILE_OFFSET,
        b"\0" * len(detail_nochange_code),
        detail_nochange_code,
        "check whether a Detail-row purchase would change anything and, if not, show the row-specific no-change message and charge nothing",
    )
    patch(
        DISPATCH_FILE_OFFSET,
        b"\0" * len(dispatch_block),
        dispatch_block,
        "route Grant Running, Grant Full Mastery, Complete/Reset Collections, and the two Equal Division of Labor rows to their companion-DLL exports (the DLL counts, applies, and reports; Collections also fires or re-arms the group goals; Equal Division cyclically assigns balanced job preferences)",
    )
    patch(
        BARREL_GATE_FILE_OFFSET,
        b"\0" * len(barrel_gate_block),
        barrel_gate_block,
        "gate the Barrel of Babies on real village capacity by handing the player object to the companion DLL's GateVV2Barrel, which refuses (message, no charge) when fewer than 3 population slots remain",
    )

    patch(
        0x218,
        bytes.fromhex("A8030200"),
        bytes.fromhex("00100200"),
        "extend the mapped .rdata VirtualSize to cover the Origins payload at its raw end",
    )
    patch(
        0x234,
        bytes.fromhex("40000040"),
        bytes.fromhex("20000060"),
        "make the mapped .rdata Origins payload executable code",
    )
    patch(
        0x268,
        bytes.fromhex("04000000"),
        bytes.fromhex("00100000"),
        "extend the mapped .shr VirtualSize to cover the preflight and Cure helpers",
    )
    patch(
        0x284,
        bytes.fromhex("400000D0"),
        bytes.fromhex("600000F0"),
        "make the mapped .shr preflight and Cure helpers executable code",
    )
    patch(
        0x26290,
        bytes.fromhex("8B44240401"),
        rel32_jump(0x426290, tech_increment),
        "double eligible positive earned tech deltas",
    )
    patch(
        0x262B0,
        bytes.fromhex("8B44240401"),
        rel32_jump(0x4262B0, food_increment),
        "double eligible positive food-source deltas",
    )
    patch(
        0x34570,
        bytes.fromhex("83EC088B44"),
        rel32_jump(0x434570, event_dispatch),
        "route the marked request to the native three-child Barrel of Babies result",
    )
    patch(
        0x435EF,
        bytes.fromhex("8B4C24205F"),
        rel32_jump(0x4435EF, tech_constructor),
        "append the stock-styled Origins Upgrades button to the Tech screen",
    )
    patch(
        0x437C0,
        bytes.fromhex("837C240408"),
        rel32_jump(0x4437C0, tech_handler),
        "route Tech-screen messages through the guarded Origins Upgrades handler",
    )
    patch(
        0x437DA,
        bytes.fromhex("8B4E146A4B"),
        rel32_jump(0x4437DA, BARREL_CLOSE_HELPER_VA),
        "advance a purchased Barrel only after the stock Technologies screen closes",
    )
    patch(
        0x2E9F0,
        bytes.fromhex("E80B48FDFF"),
        rel32_jump(0x42E9F0, BARREL_MAIN_HELPER_VA),
        "present the pending native Barrel event from the stock main-village update owner",
    )
    patch(
        0x67624,
        bytes.fromhex("8B4C242088"),
        rel32_jump(0x467624, detail_constructor),
        "append the stock-styled Upgrades button to Villager Detail",
    )
    patch(
        0x67720,
        bytes.fromhex("837C240408"),
        rel32_jump(0x467720, detail_handler),
        "route Detail-screen messages through the guarded villager-upgrade handler",
    )
    patch(
        PAYLOAD_FILE_OFFSET,
        b"\0" * len(payload),
        bytes(payload),
        "install the VV2 Origins Tech and Villager upgrade menus and mechanics",
    )

    # The research executable is deliberately composed from the same exact
    # stock image as the patcher: the mask stage owns the appended sections and
    # five detours, then the Origins payload is applied over that result.
    rendered = bytearray(mask_stage2_output)
    for item in patches:
        offset = int(item["offset"], 16)
        replacement = bytes.fromhex(item["after"])
        rendered[offset : offset + len(replacement)] = replacement
    OUT_EXE.write_bytes(rendered)
    OUT_JSON.write_text(json.dumps(patches, indent=2) + "\n", encoding="utf-8")

    mask_header_patches = [
        {
            "offset": "0xF6",
            "before": "0500",
            "after": "0700",
            "purpose": "add the patch-owned .mtab and .vvmk sections",
        },
        {
            "offset": "0x140",
            "before": "00300B00",
            "after": "00500B00",
            "purpose": "extend SizeOfImage over the patch-owned sections",
        },
        {
            "offset": "0x2B0",
            "before": bytes(40).hex().upper(),
            "after": mask_stage2_output[0x2B0 : 0x2B0 + 40].hex().upper(),
            "purpose": "install the patch-owned writable .mtab section header",
        },
        {
            "offset": "0x2D8",
            "before": bytes(40).hex().upper(),
            "after": mask_stage2_output[0x2D8 : 0x2D8 + 40].hex().upper(),
            "purpose": "install the patch-owned executable .vvmk section header",
        },
    ]
    mask_layout = {
        "original_file_size": "0xB1000",
        "append_offset": "0xB1000",
        "append_length": len(mask_append),
        "append_bytes": mask_append.hex().upper(),
        "virtual_address": "0x4B3000",
        "section_name": ".mtab/.vvmk",
        "page_sha256": hashlib.sha256(mask_append).hexdigest().upper(),
        "purpose": "append the patch-owned VV2 mask table and RX renderer sections",
        "header_patches": mask_header_patches,
    }
    mask_append_transaction = {
        "owner": "vv2_enable_origins_exclusive_features",
        "builder_sha256": source_text_sha256(
            ROOT / "scripts" / "build_vv2_mask_stage2.py"
        ),
        "section_name": ".mtab/.vvmk",
        "append_length": len(mask_append),
        "append_offset": "0xB1000",
        "page_sha256": hashlib.sha256(mask_append).hexdigest().upper(),
        "source_sha256": actual_sha256,
        "removal_policy": "restore the five exact mask detours, guarded PE section headers, and truncate only the owned .mtab/.vvmk pages",
        "layouts": {
            "collection_progression": mask_layout,
            "immediate_fixed": dict(mask_layout),
        },
    }

    manifest = {
        "id": "vv2_enable_origins_exclusive_features",
        "enabled": True,
        "catalog_enabled": True,
        "catalog_hidden": False,
        "game_id": "vv2",
        "running_preference_id": RUNNING_PREFERENCE_ID,
        "running_preference_evidence": {"source": "exact stock executable embedded preference table", "table_file_offset": "0x8B808", "entry_name": "running"},
        "name": "Enable Origins-Exclusive Features and Heathen Masks",
        "description": "Adds Origins-style Upgrades buttons to the Tech and Villager Details screens. The Tech menu offers Time Warp, Island Event, Barrel of Babies, Tech and Food Point Doublers, and Cure All Villagers; eligible positive gains are doubled, while Island Events, Duplicate Collectibles, and Gong of Wonder tech gains remain unchanged. The Villager Details menu grants Youth, Full Mastery, Running, and Set Age to 18 to the selected villager. Also includes the Heathen mask mod: a cosmetic mask (Blue, Orange, Red, Purple, or Chief) can be given to any villager from the Change Appearance picker on the Villager Details screen, or to the whole village at once from the Change Appearance for All tech upgrade. Masks render on villagers in the village view and on the Details screen portrait, and persist across save and reload. The mask artwork ships inside the companion DLL and is written out automatically on first run, including migration of an exact obsolete bundled 320x440 atlas while preserving current/custom art.",
        "output_tag": "Origins Exclusive Features",
        "companion_files": [
            {
                "source": "assets/origins/VVFP VV2 Origins Icons.dll",
                "destination": "VVFP VV2 Origins Icons.dll",
                "sha256": hashlib.sha256(
                    (ROOT / "assets" / "origins" / "VVFP VV2 Origins Icons.dll").read_bytes()
                ).hexdigest().upper(),
            }
        ],
        "pe_append_transaction": mask_append_transaction,
        "doubler_evidence": {
            "build": {
                "filename": "Virtual Villagers - The Lost Children.exe",
                "size": 724992,
                "sha256": "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677",
            },
            "positive_tech_writer": "0x426290",
            "positive_food_writer": "0x4262B0",
            "collection_adjustment": "No separate global collection multiplier exists in either final writer; every eligible caller passes the final native signed delta, so the wrapper doubles that positive delta after all caller-side collection arithmetic.",
            "island_event_handlers": {
                "two_choice_handler": {
                    "function": "0x4204B0",
                    "tech_returns": ["0x4205AC"],
                    "food_returns": ["0x420AE9"],
                    "direct_resource_paths": ["direct +3000 tech result and deductions/caps bypass the positive writers"],
                },
                "single_result_dispatcher": {
                    "function": "0x433600",
                    "tech_returns": ["0x434351"],
                    "food_returns": ["0x433FC6"],
                    "direct_resource_paths": ["losses, caps, halves, resets, and unrelated resources bypass positive writers"],
                },
            },
            "gong_of_wonder": {
                "function": "0x44E8A0",
                "registered_action": 164,
                "invoked_by": "0x461B10",
                "tech_returns": ["0x44EA32", "0x44ED52", "0x44F202"],
                "food_returns": ["0x44E9C3", "0x44EDB9", "0x44F0D9"],
                "direct_resource_paths": ["negative tech and reset/zero outcomes bypass positive writers"],
            },
            "duplicate_collectibles": {
                "function": "0x463426",
                "tech_returns": ["0x463461", "0x46346D", "0x463479"],
                "behavior": "an already-completed collectible routes to the tech writer",
            },
            "tech_blacklist_returns": [
                "0x4205AC", "0x434351", "0x44EA32", "0x44ED52", "0x44F202",
                "0x463461", "0x46346D", "0x463479"
            ],
            "food_blacklist_returns": [
                "0x420AE9", "0x433FC6", "0x44E9C3", "0x44EDB9", "0x44F0D9"
            ],
            "direct_call_inventory": {
                "tech": [
                    "0x4205A7/0x4205AC", "0x43434C/0x434351", "0x4385E1/0x4385E6",
                    "0x438741/0x438746", "0x4388A1/0x4388A6", "0x438A9B/0x438AA0",
                    "0x438C7B/0x438C80", "0x438E5B/0x438E60", "0x44EA2D/0x44EA32",
                    "0x44ED4D/0x44ED52", "0x44F1FD/0x44F202", "0x46345C/0x463461",
                    "0x463468/0x46346D", "0x463474/0x463479", "0x463737/0x46373C",
                    "0x4637C0/0x4637C5", "0x463809/0x46380E"
                ],
                "food": [
                    "0x420AE4/0x420AE9", "0x433FC1/0x433FC6", "0x438293/0x438298",
                    "0x438371/0x438376", "0x438445/0x43844A", "0x44E9BE/0x44E9C3",
                    "0x44EDB4/0x44EDB9", "0x44F0D4/0x44F0D9", "0x463198/0x46319D",
                    "0x463259/0x46325E", "0x463312/0x463317", "0x463364/0x463369",
                    "0x4633CD/0x4633D2"
                ],
                "e9_tail_jumps_to_writers": 0,
            },
            "hook_status": "GO: exact-build static provenance proof covers the positive writer callsites and excludes Island Event, Gong, and duplicate-collectible tech awards; runtime/player confirmation pending",
        },
        "doubler_composition_contract": {
            "stacking": [
                "positive earned tech deltas only",
                "positive food-source deltas only",
            ],
            "exclusions": [
                "Island Event tech-point gain",
                "Gong of Wonder tech-point gain",
                "Duplicate Collectibles tech-point gain",
            ],
            "food_mastery_status": "confirmed absent in exact-build audit: enumerated technology definitions, resource strings, direct writer calls, and food-source call chains; Farming gates/unlocks sources only; Herb Mastery is unrelated",
            "status": "GO: exact-build static provenance covers the certified positive delta boundaries; native writers still perform storage/statistics updates for the doubled amount; runtime/player confirmation pending",
        },
        "doubler_purchase_status": {
            "status": "Tech and Food Doublers are available at 500,000 tech points; owned upgrades can be removed for no refund and bought again.",
            "new_purchase": "available at 500,000 tech points for each doubler",
            "existing_owned": "removable at zero cost with zero refund",
            "repurchase": "available again at 500,000 tech points after removal",
        },
        "patches": patches,
    }
    MANIFEST_JSON.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    used = max(index for index, value in enumerate(code) if value) + 1
    print(f"code bytes used: {used:#x}/{STRINGS_OFFSET:#x}")
    print(f"string bytes used: {len(strings):#x}/{PAYLOAD_SIZE - STRINGS_OFFSET:#x}")
    print(OUT_JSON)
    print(MANIFEST_JSON)
    print(OUT_EXE)


if __name__ == "__main__":
    main()
