"""Assemble the exact-build VV5 Origins-exclusive feature patch."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research/stock-executables/Virtual Villagers - New Believers.exe"
OUT_DIR = ROOT / "research/vv5-origins"
OUT_EXE = OUT_DIR / "Virtual Villagers - New Believers - Origins Research.exe"
OUT_JSON = OUT_DIR / "vv5-origins-feature-patches.json"
MANIFEST_JSON = ROOT / "data/vv5_origins_feature.json"
COMPANION = ROOT / "assets/origins/VVFP Origins Icons.dll"
VV5_PROVENANCE_DIR = ROOT / "assets/candidates/vv5_full_mastery/provenance"
VV5_PROVENANCE = {
    "VV5Mockup.jpg": "4EF2DFC0DAE6C733C452CCB4BEA4023C0E2601EEF2396A1A38D75A4DCD57B00F",
    "VV5Mockup2.jpg": "104B1BE5873B1660EE4BC2E02A886C6EBB99B06CB6F0D723D20638C2B0949144",
}

sys.path.insert(0, str(ROOT / ".tools/keystone"))
sys.path.insert(0, str(ROOT / ".tools/keystone-runtime"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402

IMAGE_BASE = 0x400000
PAYLOAD_FILE_OFFSET = 0xDB000
PAYLOAD_VA = 0x7B2000
EXPANDED_PAYLOAD_VA = 0x8EB000
PAYLOAD_SIZE = 0x1000
STRINGS_OFFSET = 0xD00
STRINGS_VA = PAYLOAD_VA + STRINGS_OFFSET
RUNNING_PREFERENCE_ID = 38  # exact-build preference-table evidence: 0xAEF60
TECH_BUTTON_EVENT = 13
DETAIL_BUTTON_EVENT = 13  # native VV5 Detail constructor/handler event

# The VV5 IDA relocation ledger used to live here: three hand-recorded tables
# exported from IDA Pro 9.4, pinning exact bytes at fixed payload offsets, plus
# a guard that aborted the build when the rendered payload no longer matched.
#
# Every row's own purpose string said what it was for -- "relocate ... for
# expanded 256 mode".  That was its only job: rewriting payload pointers when
# the payload moves from 0x7B2000 to 0x8EB000 in expanded-256.
#
# Expanded-256 is dead.  It is not a declared patch mode, no game offers it as
# a variant, all fifteen shipping variants set `expanded_records` False, and
# _expanded_patches() returns [] outside expanded modes -- so these rows could
# never be applied.  Meanwhile the guard blocked every legitimate payload edit,
# because changing the payload is exactly what invalidates hand-recorded byte
# snapshots.  It blocked the VV5 Time Warp speed normalisation.
#
# Removed rather than kept as dead weight.  If expanded-256 is ever revived it
# needs a fresh IDA export against that build anyway; a stale ledger would be
# worse than none.

# D37 VV5 selector repair.  The hook remains the existing seven-byte detour;
# only the owned body is corrected so both marker branches call the native
# selector and return after the complete stock call instruction.
BARREL_SELECTOR_HOOK_FILE_OFFSET = 0x1890F
BARREL_SELECTOR_HOOK_VA = IMAGE_BASE + BARREL_SELECTOR_HOOK_FILE_OFFSET
BARREL_SELECTOR_BODY_FILE_OFFSET = PAYLOAD_FILE_OFFSET + 0x180
BARREL_SELECTOR_BODY_VA = PAYLOAD_VA + 0x180
BARREL_SELECTOR_HOOK_STOCK = bytes.fromhex("8B7484146A64E8")
BARREL_SELECTOR_HOOK_REPAIRED = bytes.fromhex("E96C9839009090")
BARREL_SELECTOR_BODY_STOCK = b"\0" * 0x39
# BE1A000000 is `mov esi, 26` -- the believer barrel in the EVENT OBJECT table
# at 0x4DC850, verified by RTTI on the constructed object. It was BE19000000
# (`mov esi, 25`), which is CEventTheStingingWasps: the player bought the barrel
# and got a wasp swarm and no children. See tests/test_vv5_barrel_event_index.py,
# which re-derives the id from the stock binary rather than trusting this byte.
# The purchased barrel then jumps straight to the presenter at 0x41895B, past
# the stock Chutes Without Ladders override (see the routine below).
BARREL_SELECTOR_BODY_REPAIRED = bytes.fromhex(
    "8B748414F70588D3510004000000741D832588D35100FBBE1A000000"
    "6A64E8BD14C5FF83C40889C7E9AE67C6FF"
    "6A64E8AC14C5FFE96167C6FF"
)
BARREL_SELECTOR_BODY_SHA256 = hashlib.sha256(BARREL_SELECTOR_BODY_REPAIRED).hexdigest().upper()


# THE TRIBE-DELETE HOOK, owned here rather than by the parentage log.
#
# Origins is what writes the per-slot mask files, so a build with Origins and
# no parentage log would persist masks with nothing to clean them: a new tribe
# started in a reused slot inherits them, which is the bleed the reset exists
# to stop. The feature that creates the state owns the cleanup.
#
# The cave sits in the free .text tail, measured against a RENDERED image with
# every fun patch applied and every VV5 manifest's claims overlaid, not
# against the stock file. Content ends at 0x49472F and resumes at 0x494840 in
# both catalog modes, and no Origins cave is hardcoded inside that window.
RESET_CAVE_FILE_OFFSET = 0x00094730
RESET_CAVE_VA = 0x00494730
RESET_CAVE_SIZE = 0x62
RESET_DLL_NAME = b"VVFP Save Reset.dll\0"
RESET_EXPORT_NAME = b"ResetDeletedTribe\0"
RESET_DLL_NAME_OFFSET = 0x00
RESET_EXPORT_NAME_OFFSET = 0x14
RESET_CODE_OFFSET = 0x28
RESET_HOOK_VA = 0x004193F5
RESET_HOOK_FILE = 0x000193F5
RESET_HOOK_STOLEN = bytes.fromhex("e896b20000")
RESET_THUNK_VA = 0x00424690
RESET_GET_MODULE_HANDLE_IAT = 0x004951D8
RESET_GET_PROC_ADDRESS_IAT = 0x004951DC
RESET_LOAD_LIBRARY_IAT = 0x004951E0
RESET_COMPANION_SOURCE = "assets/save_reset/VVFP Save Reset.dll"


def assemble(source: str, address: int) -> bytes:
    encoded, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoded)


def rel32_jump(source_va: int, target_va: int, size: int = 5) -> bytes:
    result = b"\xE9" + int(target_va - source_va - 5).to_bytes(
        4, "little", signed=True
    )
    return result + b"\x90" * (size - 5)


def add_c_string(
    blob: bytearray, labels: dict[str, int], name: str, value: str
) -> None:
    labels[name] = STRINGS_VA + len(blob)
    blob.extend(value.encode("ascii") + b"\0")


def main() -> None:
    original = STOCK.read_bytes()
    expected = "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D"
    actual = hashlib.sha256(original).hexdigest().upper()
    if actual != expected:
        raise RuntimeError(f"stock SHA-256 mismatch: expected {expected}, got {actual}")
    if not COMPANION.is_file():
        raise RuntimeError(f"missing companion DLL: {COMPANION}")
    for name, expected_hash in VV5_PROVENANCE.items():
        provenance_path = VV5_PROVENANCE_DIR / name
        if not provenance_path.is_file():
            raise RuntimeError(f"missing VV5 provenance reference: {provenance_path}")
        actual_hash = hashlib.sha256(provenance_path.read_bytes()).hexdigest().upper()
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"VV5 provenance hash mismatch for {name}: expected {expected_hash}, got {actual_hash}"
            )
    if any(original[PAYLOAD_FILE_OFFSET : PAYLOAD_FILE_OFFSET + PAYLOAD_SIZE]):
        raise RuntimeError("VV5 Origins .shr payload region is not stock zero padding")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    strings = bytearray()
    s: dict[str, int] = {}
    # Only the Upgrades button label is read by live code (the two
    # constructors). Every other string, and the old Tech/Detail price
    # tables, belonged to the legacy .shr menus, which never run: Task9
    # replaces both menu entries with absolute jumps to its own page.
    add_c_string(strings, s, "button", "Upgrades")
    if len(strings) > PAYLOAD_SIZE - STRINGS_OFFSET:
        raise RuntimeError("VV5 Origins strings exceed payload allowance")

    entry = {
        "tech_handler": PAYLOAD_VA + 0x000,
        "tech_ctor": PAYLOAD_VA + 0x040,
        "detail_handler": PAYLOAD_VA + 0x0C0,
        "detail_ctor": PAYLOAD_VA + 0x100,
        "barrel_selector": PAYLOAD_VA + 0x180,
        "tech_menu": PAYLOAD_VA + 0x2C0,
        "detail_menu": PAYLOAD_VA + 0x600,
        "tech_increment": PAYLOAD_VA + 0xA00,
        "food_increment": PAYLOAD_VA + 0xB00,
    }
    code = bytearray(STRINGS_OFFSET)
    occupied = bytearray(STRINGS_OFFSET)

    def put(name: str, source: str) -> None:
        va = entry[name]
        payload = assemble(source, va)
        start = va - PAYLOAD_VA
        end = start + len(payload)
        if start < 0 or end > len(code):
            raise RuntimeError(f"{name} exceeds VV5 Origins code block")
        if any(occupied[start:end]):
            raise RuntimeError(f"{name} overlaps another payload routine")
        code[start:end] = payload
        occupied[start:end] = b"\1" * len(payload)

    put(
        "tech_handler",
        f"""
            cmp dword ptr [esp + 4], 8
            jne original
            cmp dword ptr [esp + 8], {TECH_BUTTON_EVENT}
            jne original
            call 0x{entry['tech_menu']:X}
            xor eax, eax
            ret 8
        original:
            push edi
            mov edi, ecx
            call 0x450D40
            jmp 0x4415F8
        """,
    )
    put(
        "tech_ctor",
        f"""
            push 0x14
            call 0x47BBDC
            add esp, 4
            test eax, eax
            je done
            mov edi, eax
            mov ecx, edi
            push 72
            call 0x44FA20
            push 0
            push esi
            push 722
            push 180
            push eax
            push {TECH_BUTTON_EVENT}
            mov ecx, edi
            call 0x401BD0
            mov edi, eax
            push 0
            push dword ptr [0x4CD2A8]
            push dword ptr [0x4CD2A4]
            push dword ptr [0x4CD2A0]
            push 0x{s['button']:X}
            mov ecx, edi
            call 0x4015D0
            push edi
            mov ecx, esi
            call 0x40C680
        done:
            mov eax, esi
            mov ecx, dword ptr [esp + 0x4C]
            mov dword ptr fs:[0], ecx
            pop ecx
            pop edi
            pop esi
            pop ebp
            pop ebx
            add esp, 0x44
            ret
        """,
    )
    put(
        "detail_handler",
        f"""
            cmp dword ptr [esp + 4], 8
            jne original
            cmp dword ptr [esp + 8], {DETAIL_BUTTON_EVENT}
            jne original
            call 0x{entry['detail_menu']:X}
            xor eax, eax
            ret 8
        original:
            sub esp, 0x18
            mov eax, dword ptr [0x4D97A8]
            jmp 0x44BC28
        """,
    )
    put(
        "detail_ctor",
        f"""
            push 0x14
            call 0x47BBDC
            add esp, 4
            test eax, eax
            je no_button
            mov edi, eax
            mov ecx, edi
            push 72
            call 0x44FA20
            push 0
            push esi
            push 700
            push 180
            push eax
            push {DETAIL_BUTTON_EVENT}
            mov ecx, edi
            call 0x401BD0
            mov edi, eax
            push 0
            push dword ptr [0x4CD2A8]
            push dword ptr [0x4CD2A4]
            push dword ptr [0x4CD2A0]
            push 0x{s['button']:X}
            mov ecx, edi
            call 0x4015D0
            push edi
            mov ecx, esi
            call 0x40C680
            jmp done
        no_button:
        done:
            mov eax, esi
            mov ecx, dword ptr [esp + 0x24]
            mov dword ptr fs:[0], ecx
            pop ecx
            pop edi
            pop esi
            pop ebp
            pop ebx
            add esp, 0x1C
            ret
        """,
    )
    put(
        "barrel_selector",
        """
            mov esi, dword ptr [esp + eax*4 + 0x14]
            test dword ptr [0x51D388], 4
            jz done
            and dword ptr [0x51D388], 0xFFFFFFFB
            # 26, not 25.  The scheduler indexes the EVENT OBJECT table at
            # 0x4DC850, which is NOT the string table at 0x4D7B24 -- the string
            # table has an entry for the Banyan Festival that the object table
            # does not, so every id after it is shifted by one.  RTTI on the
            # constructed objects (0x00417B3C..0x00417B82 store their vtables)
            # settles it with no guessing:
            #   25 -> 0x497AF4 .?AVCEventTheStingingWasps@@
            #   26 -> 0x497B3C .?AVCEventBarrelOBabiesV@@        <-- believers
            #   27 -> 0x497B84 .?AVCEventBarrelOHeathenBabiesV@@
            # Forcing 25 presented "The Stinging Wasps" -- exactly what the
            # player saw -- and of course spawned nothing.  Forcing 27 would
            # present the HEATHEN barrel, which is the wrong flavour for a
            # believer village, so the off-by-one must not be "fixed" by
            # matching the string-table index.
            # Object 26 is the right one on both halves of its vtable:
            #   slot[1] (the eligibility the scheduler calls at 0x004188D0) is
            #     0x004151C0 = the population cap gate 0x472BD0, and
            #   slot[12] (the effect) is 0x004151D0, which spawns three
            #     children -- one unconditional 0x471E20, then two more each
            #     gated on 0x472BD0.
            mov esi, 26
            # The purchased barrel goes straight to the presenter (0x41895B).
            # Falling back into the stock code at 0x41891A ran the Chutes
            # Without Ladders override (0x41891D..0x418956), which in a very
            # small village replaces whatever was chosen -- the paid barrel
            # included -- with index 30.  The stock rand(100) is still drawn
            # and lands in edi exactly as 0x41891A..0x418922 would leave it;
            # nothing after 0x41895B reads edi before restoring it.
            push 100
            call 0x403660
            add esp, 8
            mov edi, eax
            jmp 0x41895B
        done:
            push 100
            call 0x403660
            jmp 0x41891A
        """,
    )
    # The Tech and Detail menu entries. Task9 owns both menus: its generator
    # overwrites each of these entries with an absolute jump into the
    # appended .vv5t9 page (`mov eax, page; jmp eax`), and the shipped
    # manifest is Task9's. Here they are bare returns, so this base payload
    # carries no second, unreachable copy of the menus.
    put("tech_menu", "ret")
    put("detail_menu", "ret")
    tech_wrapper_expected = bytes.fromhex(
        "8B44240485C07E2BF70588D3510001000000741F"
        "813C244DDE46007412813C247CDE46007409813C24A5DE46007504"
        "D1642404568B7424080131E9780DC7FF"
    )
    put(
        "tech_increment",
        f"""
            mov eax, dword ptr [esp + 4]
            test eax, eax
            jle native
            test dword ptr [0x51D388], 1
            jz native
            cmp dword ptr [esp], 0x46DE4D
            je matched
            cmp dword ptr [esp], 0x46DE7C
            je matched
            cmp dword ptr [esp], 0x46DEA5
            jne native
        matched:
            shl dword ptr [esp + 4], 1
        native:
            push esi
            mov esi, dword ptr [esp + 8]
            add dword ptr [ecx], esi
            jmp 0x4237B7
        """,
    )
    tech_wrapper = bytes(code[entry["tech_increment"] - PAYLOAD_VA : entry["tech_increment"] - PAYLOAD_VA + len(tech_wrapper_expected)])
    if tech_wrapper != tech_wrapper_expected:
        raise RuntimeError(
            "VV5 Tech Doubler wrapper bytes drifted from the exact stock whitelist"
        )
    put(
        "food_increment",
        f"""
            test esi, esi
            jle native
            test dword ptr [0x51D388], 2
            jz native
            cmp dword ptr [esp + 8], 0x414970
            jne native
            add esi, esi
        native:
            test esi, esi
            jle nonpositive
            push esi
            jmp 0x41EB74
        nonpositive:
            jmp 0x41EBA7
        """,
    )

    payload = code + strings
    expanded_shr_relocations: list[dict[str, str]] = []
    patches: list[dict[str, str | int]] = []

    def patch(offset: int, before: bytes, after: bytes, purpose: str) -> None:
        actual_bytes = original[offset : offset + len(before)]
        if actual_bytes != before:
            raise RuntimeError(
                f"guard mismatch at {offset:#x}: expected {before.hex()}, "
                f"got {actual_bytes.hex()}"
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

    patch(0x28C, bytes.fromhex("400000D0"), bytes.fromhex("400000F0"),
          "make the stock shared payload section executable")
    patch(BARREL_SELECTOR_HOOK_FILE_OFFSET, BARREL_SELECTOR_HOOK_STOCK,
          BARREL_SELECTOR_HOOK_REPAIRED,
          "consume the one-shot purchase marker and force native event index 26")
    stock_food_hook = bytes.fromhex("85F67E3456")
    detoured_food_hook = rel32_jump(0x41EB6F, entry["food_increment"])
    stock_tech_hook = bytes.fromhex("568B742408")
    detoured_tech_hook = rel32_jump(0x4237B0, entry["tech_increment"])
    patch(0x1EB6F, stock_food_hook,
          detoured_food_hook,
          "double eligible positive food-source deltas")
    patch(0x237B0, stock_tech_hook,
          detoured_tech_hook,
          "double three exact positive-whitelist tech awards for the current save")
    patch(0x40A24, bytes.fromhex("8BC68B4C244C"),
          rel32_jump(0x440A24, entry["tech_ctor"], 6),
          "append the stock-styled Upgrades control to the Tech screen")
    patch(0x415F0, bytes.fromhex("578BF9E848F70000"),
          rel32_jump(0x4415F0, entry["tech_handler"], 8),
          "route Tech-screen control 13 through the Origins menu")
    patch(0x4AF12, bytes.fromhex("8BC68B4C2424"),
          rel32_jump(0x44AF12, entry["detail_ctor"], 6),
          "append the stock-styled Upgrades control to Villager Detail")
    patch(0x4BC20, bytes.fromhex("83EC18A1A8974D00"),
          rel32_jump(0x44BC20, entry["detail_handler"], 8),
          "route the added Detail control through the villager-upgrade menu")
    if bytes(payload[0x180:0x180 + len(BARREL_SELECTOR_BODY_REPAIRED)]) != BARREL_SELECTOR_BODY_REPAIRED:
        raise RuntimeError(
            "D37 VV5 selector body assembly drifted from the exact repaired bytes: "
            + bytes(payload[0x180:0x180 + len(BARREL_SELECTOR_BODY_REPAIRED)]).hex().upper()
        )
    patch(PAYLOAD_FILE_OFFSET, b"\0" * len(payload), bytes(payload),
          "install the VV5 Origins Upgrades buttons, menu entries, Barrel selector and doubler wrappers in the unused .shr section")

    # THE TRIBE-DELETE STUB AND ITS HOOK.
    #
    # Origins writes the per-slot mask files, so a build with Origins and no
    # parentage log would persist masks with nothing to clean them: a new tribe
    # started in the same slot inherits them. The feature that creates the
    # state owns the cleanup, and claiming these bytes in BOTH features would
    # make uninstalling the parentage log strip a stub Origins still needs.
    #
    # The stub preserves every register -- it runs inside the menu handler's
    # own frame -- and falls through to the game's delete on EVERY failure: a
    # missing companion or an unresolved export costs the sweep, never the
    # player's save.
    #
    # EDI holds the RAW slot the menu handler loaded. The game's other caller
    # of deleteSave rotates backup generations and passes slot + 0x14, so
    # hooking the handler's own call reaches the reset and never ordinary play.
    reset_payload = bytearray(RESET_CAVE_SIZE)
    reset_code = assemble(
        f"""
            pushad
            push 0x{RESET_CAVE_VA + RESET_DLL_NAME_OFFSET:X}
            call dword ptr [0x{RESET_GET_MODULE_HANDLE_IAT:X}]
            test eax, eax
            jnz reset_have_module
            push 0x{RESET_CAVE_VA + RESET_DLL_NAME_OFFSET:X}
            call dword ptr [0x{RESET_LOAD_LIBRARY_IAT:X}]
            test eax, eax
            jz reset_done
        reset_have_module:
            push 0x{RESET_CAVE_VA + RESET_EXPORT_NAME_OFFSET:X}
            push eax
            call dword ptr [0x{RESET_GET_PROC_ADDRESS_IAT:X}]
            test eax, eax
            jz reset_done
            # ResetDeletedTribe(game, slot)
            push edi
            push 5
            call eax
        reset_done:
            popad
            jmp 0x{RESET_THUNK_VA:X}
        """,
        RESET_CAVE_VA + RESET_CODE_OFFSET,
    )
    if RESET_CODE_OFFSET + len(reset_code) > RESET_CAVE_SIZE:
        raise RuntimeError("the reset stub runs past its measured cave")
    reset_payload[RESET_CODE_OFFSET : RESET_CODE_OFFSET + len(reset_code)] = reset_code
    reset_payload[RESET_DLL_NAME_OFFSET : RESET_DLL_NAME_OFFSET + len(RESET_DLL_NAME)] = RESET_DLL_NAME
    reset_payload[
        RESET_EXPORT_NAME_OFFSET : RESET_EXPORT_NAME_OFFSET + len(RESET_EXPORT_NAME)
    ] = RESET_EXPORT_NAME
    patch(RESET_CAVE_FILE_OFFSET, b"\0" * RESET_CAVE_SIZE, bytes(reset_payload),
          "install the tribe-delete reset stub in the free .text tail")
    patch(RESET_HOOK_FILE, RESET_HOOK_STOLEN,
          assemble(f"call 0x{RESET_CAVE_VA + RESET_CODE_OFFSET:X}", RESET_HOOK_VA),
          "route the save-slot menu's tribe delete through the reset stub, so a "
          "new tribe started in the same slot does not inherit the old one's masks")

    patch_mode_overrides = {
        "experimental_expanded_256": [
            {
                "offset": "0x237B0",
                "before": detoured_tech_hook.hex().upper(),
                "after": stock_tech_hook.hex().upper(),
                "purpose": "restore the exact stock VV5 tech-writer bytes in expanded mode; no expanded Tech Doubler detour is emitted",
            },
            {
                "offset": "0x1EB6F",
                "before": detoured_food_hook.hex().upper(),
                "after": stock_food_hook.hex().upper(),
                "purpose": "restore the exact stock VV5 food-writer bytes in expanded mode; no expanded Food Doubler detour is emitted",
            }
        ],
        "experimental_expanded_256_progression": [
            {
                "offset": "0x237B0",
                "before": detoured_tech_hook.hex().upper(),
                "after": stock_tech_hook.hex().upper(),
                "purpose": "restore the exact stock VV5 tech-writer bytes in expanded mode; no expanded Tech Doubler detour is emitted",
            },
            {
                "offset": "0x1EB6F",
                "before": detoured_food_hook.hex().upper(),
                "after": stock_food_hook.hex().upper(),
                "purpose": "restore the exact stock VV5 food-writer bytes in expanded mode; no expanded Food Doubler detour is emitted",
            }
        ],
    }

    rendered = bytearray(original)
    for item in patches:
        offset = int(str(item["offset"]), 16)
        replacement = bytes.fromhex(str(item["after"]))
        rendered[offset : offset + len(replacement)] = replacement
    OUT_EXE.write_bytes(rendered)
    OUT_JSON.write_text(json.dumps(patches, indent=2) + "\n", encoding="utf-8", newline="")
    manifest = {
        "id": "vv5_enable_origins_exclusive_features",
        "game_id": "vv5",
        "running_preference_id": RUNNING_PREFERENCE_ID,
        "running_preference_evidence": {"source": "exact stock executable embedded preference table", "table_file_offset": "0xAEF60", "entry_name": "running"},
        "name": "Enable Origins-Exclusive Features",
        "description": "Base layer of the VV5 Origins upgrades: adds the Upgrades buttons to the Tech and Villager Details screens, the Barrel of Babies event selector, and the Tech and Food Point Doubler wrappers. The menus behind the buttons are supplied by the Task9 page (data/vv5_task9_native_actions.json), which is the record the patcher ships for this feature.",
        "output_tag": "Origins Exclusive Features",
        "companion_files": [
            {
                "source": "assets/origins/VVFP Origins Icons.dll",
                "destination": "VVFP Origins Icons.dll",
                "sha256": hashlib.sha256(COMPANION.read_bytes()).hexdigest().upper(),
            },
            {
                # The tribe-delete stub resolves this by name at runtime.
                "source": RESET_COMPANION_SOURCE,
                "destination": "VVFP Save Reset.dll",
                "sha256": hashlib.sha256(
                    (ROOT / RESET_COMPANION_SOURCE).read_bytes()
                ).hexdigest().upper(),
            },
        ],
        "doubler_evidence": {
            "build": {
                "filename": STOCK.name,
                "size": 991232,
                "sha256": "92946781980220E9D1A2E6C573925519934608F5215F4A0F8CE3B90088C5C65D",
            },
            "positive_tech_writer": "0x4237B0",
            "tech_positive_returns": ["0x46DE4D", "0x46DE7C", "0x46DEA5"],
            "tech_excluded_refund_return": "0x419EA3",
            "tech_exclusions": [
                "all 16 Island Event outcomes",
                "Duplicate Collectibles (returns 0x4147BE, 0x4147DD, and 0x4147F9)",
                "all eight writer tail paths",
                "technology purchase/spending/deduction paths",
                "zero and negative deltas",
                "unknown caller returns",
            ],
            "positive_food_writer": "0x41EB40 before storage/statistics channels",
            "food_mastery": {
                "technology_id": 4,
                "levels": {"1": "A", "2": "A+floor(A/2)", "3": "2A"},
                "costs": {"level_1_to_2": 3000, "level_2_to_3": 40000},
                "zero_negative_inputs": "bypass mastery",
                "collection_return": "0x414970",
                "collection_base_to_native": {"6": [6, 9, 12], "35": [35, 52, 70]},
            },
            "collection_adjustment": "Food-source return 0x414970 supplies the base delta; native Food Mastery completes before the Food Point Doubler doubles the final positive source delta once.",
            "island_event_producers": ["Island Event, startup, consumption, and unknown callers remain native; unknown callers cannot match return 0x414970"],
            "tech_writer_hook": {
                "virtual_address": "0x4237B0",
                "file_offset": "0x237B0",
                "before": "568B742408",
                "after": "E94BF23800",
                "wrapper_virtual_address": "0x7B2A00",
                "wrapper_file_offset": "0xDBA00",
                "wrapper_bytes": "8B44240485C07E2BF70588D3510001000000741F813C244DDE46007412813C247CDE46007409813C24A5DE46007504D1642404568B7424080131E9780DC7FF",
                "ownership_address": "0x51D388",
                "ownership_mask": "0x1",
                "eligible_returns": ["0x46DE4D", "0x46DE7C", "0x46DEA5"],
                "excluded_refund_return": "0x419EA3",
                "branch_destinations": ["0x7B2A4A", "0x7B2A4E", "0x4237B7"]
            },
            "stock_hook": {
                "virtual_address": "0x41EB6F",
                "file_offset": "0x1EB6F",
                "before": "85F67E3456",
                "after": "E98C3F3900",
                "wrapper_virtual_address": "0x7B2B00",
                "wrapper_file_offset": "0xDBB00",
                "wrapper_bytes": "85F67E18F70588D3510002000000740C817C240870494100750201F685F67E0656E94EC0C6FFE97CC0C6FF",
                "ownership_address": "0x51D388",
                "ownership_mask": "0x2",
                "eligible_return": "0x414970",
                "branch_destinations": ["0x41EB74", "0x41EBA7"]
            },
            "hook_status": "stock-layout implemented: exact Tech three-return and Food positive-whitelist wrappers; expanded-256 restores both exact stock hooks and remains native for doubler runtime.",
        },
        "doubler_composition_contract": {
            "stacking": [
                "positive earned tech deltas only",
                "positive food-source deltas only",
            ],
            "exclusions": ["Island Event tech-point gain", "Duplicate Collectibles tech-point gain"],
            "food_mastery_status": "confirmed in exact-build disassembly; technology ID 4 and separate level 1 to 2 / level 2 to 3 native transforms documented",
            "status": "stock-layout implemented: only eligible earned/source deltas are doubled once; native writers continue storage/statistics updates for the doubled amount; expanded-256 keeps both native writers and disables only new doubler purchases.",
        },
        "doubler_purchase_status": {
            "status": "stock-layout Tech and Food Doubler purchase/remove/repurchase implemented; expanded-256 new purchases are marker-gated unavailable",
            "new_purchase": "Tech and Food available in stock layout at 500,000 tech points after their exact positive-whitelist wrappers; both unavailable in expanded-256",
            "existing_owned": "removable at zero cost with zero refund",
            "repurchase": "full-price repurchase after zero-cost/no-refund removal in stock layout for both doublers; expanded-256 remains unavailable for new purchases",
        },
        "provenance": {"vv5_mockups": VV5_PROVENANCE},
        "patches": patches,
        "selector_repair": {
            "status": "candidate-only; base and individual Full Mastery records remain disabled",
            "stock_fingerprint": {
                "filename": "Virtual Villagers - New Believers.exe",
                "size": len(original),
                "sha256": expected,
            },
            "hook": {
                "file_offset": f"0x{BARREL_SELECTOR_HOOK_FILE_OFFSET:X}",
                "virtual_address": f"0x{BARREL_SELECTOR_HOOK_VA:X}",
                "before": BARREL_SELECTOR_HOOK_STOCK.hex().upper(),
                "after": BARREL_SELECTOR_HOOK_REPAIRED.hex().upper(),
                "uninstall_after": BARREL_SELECTOR_HOOK_STOCK.hex().upper(),
                "length": len(BARREL_SELECTOR_HOOK_STOCK),
            },
            "body": {
                "file_offset": f"0x{BARREL_SELECTOR_BODY_FILE_OFFSET:X}",
                "virtual_address": f"0x{BARREL_SELECTOR_BODY_VA:X}",
                "before": BARREL_SELECTOR_BODY_STOCK.hex().upper(),
                "after": BARREL_SELECTOR_BODY_REPAIRED.hex().upper(),
                "uninstall_after": BARREL_SELECTOR_BODY_STOCK.hex().upper(),
                "length": len(BARREL_SELECTOR_BODY_REPAIRED),
                "sha256": BARREL_SELECTOR_BODY_SHA256,
            },
            "native_call_virtual_address": "0x403660",
            "continuation_virtual_address": "0x41891A",
            "forbidden_branch_targets": ["0x418916", "0x418917", "0x418918", "0x418919"],
            "shr_guard": {
                "name": ".shr",
                "raw_range": "0xDB000..0xDBFFF",
                "virtual_address": "0x7B2000",
                "stock_characteristics": "0xD0000040",
                "candidate_characteristics": "0xF0000040",
                "header_patch": {"file_offset": "0x28C", "before": "400000D0", "after": "400000F0"},
                "payload_zero_preimage_required": True,
            },
            "atomic_install_uninstall": True,
        },
        "patch_mode_overrides": patch_mode_overrides,
        # Expanded-256 is never applied, so no relocation rows are emitted.
        # See the note where the IDA ledger used to live, above.
        "expanded_shr_relocations": {
            "stock_virtual_address": f"0x{PAYLOAD_VA:X}",
            "expanded_virtual_address": f"0x{EXPANDED_PAYLOAD_VA:X}",
            "status": "not emitted: expanded-256 is not a selectable patch mode and no variant applies expanded patches",
            "patches": [],
        },
    }
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="")
    used = max(i for i, value in enumerate(code) if value) + 1
    print(f"code bytes used: {used:#x}/{STRINGS_OFFSET:#x}")
    print(f"string bytes used: {len(strings):#x}/{PAYLOAD_SIZE - STRINGS_OFFSET:#x}")
    print(OUT_EXE)
    print(MANIFEST_JSON)


if __name__ == "__main__":
    main()
