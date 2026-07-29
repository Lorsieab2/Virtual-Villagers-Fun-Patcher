"""Generate the certified VV4 command-7 Full Mastery feature."""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
import sys
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"
ACTIVE_BASE = ROOT / "data" / "vv4_origins_feature.json"
OUT_DIR = ROOT / "data" / "candidates"
BASE_OUT = OUT_DIR / "vv4_origins_full_mastery_base_candidate.json"
FEATURE_OUT = OUT_DIR / "vv4_full_mastery_all_candidate.json"
MAP_OUT = OUT_DIR / "vv4_full_mastery_all_candidate_map.json"
DOC_OUT = ROOT / "docs" / "vv4-full-mastery-stage-a-candidate.md"
COMPANION = OUT_DIR / "VVFP VV4 Full Mastery Candidate.dll"
CANDIDATE_ROOT = ROOT / "assets" / "candidates" / "vv4_full_mastery"
PROVENANCE_DIR = CANDIDATE_ROOT / "provenance"
CANONICAL_MOCKUP = PROVENANCE_DIR / "VV4 mockup.jpg"
SECONDARY_MOCKUP = PROVENANCE_DIR / "VV4 mockup2.jpg"
STOCK_TROPHIES = PROVENANCE_DIR / "btn_trophies.png"
BUTTON_ASSET = CANDIDATE_ROOT / "Images" / "btn_upgrades_297x35.png"
BUTTON_DESTINATION = r"Images\btn_upgrades_297x35.png"
CANONICAL_MOCKUP_SHA256 = "B404465B960BE3875F4DF0BFE32796B8045A9E938A356FF33448331AB2840A24"
SECONDARY_MOCKUP_SHA256 = "AD1B6A8A61F13BBBA2C902E04AB8AD205167FC48034F4D0A7C078A76C756FA30"
STOCK_TROPHIES_SHA256 = "1D70B74ADA23EAC375858B7B6535BF3D7A97B663E48AC0664B79DC54C435E822"
CANONICAL_CROP_RGBA_SHA256 = "B8E9C4DB93F05450689528C5A04A532486771E53DDC23FCF63B0155C7949418B"
BUTTON_RGBA_SHA256 = "02B42DEAD3673BA5048160C2D337D284215336E39BCEAC52592432839ECB3AD4"
BUTTON_PNG_SHA256 = "F03D57038CA7745A99C0D7D58A2558A4411828BF3243D85C8BAFE2E04036BE4B"

sys.path.insert(0, str(ROOT / ".tools" / "keystone"))
sys.path.insert(0, str(ROOT / ".tools" / "keystone-runtime"))
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402


IMAGE_BASE = 0x400000
PAYLOAD_OFFSET = 0x89373
PAYLOAD_VA = 0x489373
PAYLOAD_SIZE = 0xC8D
SHOW_DIALOG_OFFSET = 0x1B0
SHOW_DIALOG_SIZE = 0x60
TECH_MENU_OFFSET = 0x260
TECH_MENU_SIZE = 0x2A0
CURE_OFFSET = 0xCC004
APPEND_OFFSET = 0xE3000
PAGE_SIZE = 0x2000
SLOT_OFFSET = 0x100
SLOT_SIZE = 0x1000
SLOT_ENTRY_OFFSET = 0x20
WALKER_OFFSET = 0x400
CONFIRM_OFFSET = 0x800
STRINGS_OFFSET = 0x1200
PRICE = 1_000_000
STRIDE = 0x2E3C

# Candidate-only UI locations in the existing active payload.  These values are
# derived from the clean active payload and are guarded before rewriting.
TECH_CONSTRUCTOR_OFFSET = 0x40
DETAIL_HANDLER_OFFSET = 0xC0
DETAIL_CONSTRUCTOR_OFFSET = 0x100
TECH_DESTRUCTOR_HELPER_OFFSET = 0xC0
DETAIL_HANDLER_RELOC_OFFSET = 0x235
DETAIL_MENU_OFFSET = 0x500
BUTTON_PATH_OFFSET = 0xBC4
TECH_DESTRUCTOR_CALL_OFFSET = 0x3E238
DETAIL_ROUTE_OFFSET = 0x48610

LAYOUTS = {
    "collection_progression": {
        "page_rva": 0x33F000,
        "page_va": 0x73F000,
        "bound": 150,
        "old_size_of_image": 0x33F000,
        "new_size_of_image": 0x341000,
    },
    "immediate_fixed": {
        "page_rva": 0x33F000,
        "page_va": 0x73F000,
        "bound": 150,
        "old_size_of_image": 0x33F000,
        "new_size_of_image": 0x341000,
    },
    "experimental_expanded_256": {
        "page_rva": 0x471000,
        "page_va": 0x871000,
        "bound": 256,
        "old_size_of_image": 0x471000,
        "new_size_of_image": 0x473000,
    },
    "experimental_expanded_256_progression": {
        "page_rva": 0x471000,
        "page_va": 0x871000,
        "bound": 256,
        "old_size_of_image": 0x471000,
        "new_size_of_image": 0x473000,
    },
}


def asm(source: str, address: int) -> bytes:
    encoding, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(encoding)


def rel32_jump(source_va: int, target_va: int) -> bytes:
    displacement = target_va - (source_va + 5)
    if not -(1 << 31) <= displacement < (1 << 31):
        raise RuntimeError("relative jump target is out of range")
    return b"\xE9" + struct.pack("<i", displacement)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def canonical_sha(value: object) -> str:
    return sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii"))


def build_button_asset() -> tuple[bytes, dict[str, object]]:
    """Rebuild the candidate strip from the repository-owned canonical mockup."""
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - environment gate
        raise RuntimeError("Pillow is required for deterministic candidate asset generation") from exc
    for path, expected in (
        (CANONICAL_MOCKUP, CANONICAL_MOCKUP_SHA256),
        (SECONDARY_MOCKUP, SECONDARY_MOCKUP_SHA256),
        (STOCK_TROPHIES, STOCK_TROPHIES_SHA256),
    ):
        if not path.is_file() or sha(path.read_bytes()) != expected:
            raise RuntimeError(f"candidate provenance hash mismatch: {path}")
    with Image.open(CANONICAL_MOCKUP) as image:
        crop = image.convert("RGBA").crop((72, 4, 171, 39))
    crop_bytes = bytes(crop.tobytes())
    if crop.size != (99, 35) or sha(crop_bytes) != CANONICAL_CROP_RGBA_SHA256:
        raise RuntimeError("canonical VV4 mockup crop guard mismatch")
    strip = Image.new("RGBA", (297, 35))
    for index in range(3):
        strip.paste(crop, (index * 99, 0))
    rgba = bytes(strip.tobytes())
    if sha(rgba) != BUTTON_RGBA_SHA256:
        raise RuntimeError("candidate strip RGBA hash mismatch")
    import io

    encoded = io.BytesIO()
    strip.save(encoded, format="PNG", compress_level=9, optimize=False)
    png = encoded.getvalue()
    if sha(png) != BUTTON_PNG_SHA256:
        raise RuntimeError("candidate strip PNG hash mismatch")
    BUTTON_ASSET.parent.mkdir(parents=True, exist_ok=True)
    BUTTON_ASSET.write_bytes(png)
    return png, {
        "path": str(BUTTON_ASSET.relative_to(ROOT)).replace("/", "\\"),
        "destination": BUTTON_DESTINATION,
        "dimensions": [297, 35],
        "format": "PNG RGBA8, lossless, zlib compress_level=9, optimize=false",
        "frame_width": 99,
        "frame_order": ["normal", "hover", "pressed"],
        "frame_count": 3,
        "source": {
            "mockup": str(CANONICAL_MOCKUP.relative_to(ROOT)).replace("/", "\\"),
            "mockup_sha256": CANONICAL_MOCKUP_SHA256,
            "crop_xywh": [72, 4, 99, 35],
            "crop_rgba_sha256": CANONICAL_CROP_RGBA_SHA256,
            "secondary_mockup_sha256": SECONDARY_MOCKUP_SHA256,
            "stock_btn_trophies_sha256": STOCK_TROPHIES_SHA256,
        },
        "rgba_sha256": BUTTON_RGBA_SHA256,
        "png_sha256": BUTTON_PNG_SHA256,
    }


def build_ui_payload(active_payload: bytes) -> tuple[bytes, dict[str, object]]:
    """Replace only the candidate UI blocks; preserve all other active bytes."""
    payload = bytearray(active_payload.ljust(PAYLOAD_SIZE, b"\0"))
    if len(payload) != PAYLOAD_SIZE:
        raise RuntimeError("active payload exceeds reserved candidate size")
    if payload[TECH_CONSTRUCTOR_OFFSET : TECH_CONSTRUCTOR_OFFSET + 7] != bytes.fromhex("6A14E8A278FEFF"):
        raise RuntimeError("Tech constructor payload guard mismatch")
    if payload[DETAIL_HANDLER_OFFSET : DETAIL_HANDLER_OFFSET + 8] != bytes.fromhex("837C240408751183"):
        raise RuntimeError("Detail handler payload guard mismatch")
    if payload[DETAIL_CONSTRUCTOR_OFFSET : DETAIL_CONSTRUCTOR_OFFSET + 7] != bytes.fromhex("6A14E8E277FEFF"):
        raise RuntimeError("Detail constructor payload guard mismatch")
    if any(payload[DETAIL_HANDLER_RELOC_OFFSET : DETAIL_HANDLER_RELOC_OFFSET + 0x2B]):
        raise RuntimeError("Detail handler relocation cave is not zero")
    path = b"Images\\btn_upgrades_297x35.png\0"
    if any(payload[BUTTON_PATH_OFFSET : BUTTON_PATH_OFFSET + len(path)]):
        raise RuntimeError("candidate asset path cave is not zero")
    payload[BUTTON_PATH_OFFSET : BUTTON_PATH_OFFSET + len(path)] = path
    path_va = PAYLOAD_VA + BUTTON_PATH_OFFSET
    tech_ctor_va = PAYLOAD_VA + TECH_CONSTRUCTOR_OFFSET
    detail_ctor_va = PAYLOAD_VA + DETAIL_CONSTRUCTOR_OFFSET
    helper_va = PAYLOAD_VA + TECH_DESTRUCTOR_HELPER_OFFSET
    relocated_handler_va = PAYLOAD_VA + DETAIL_HANDLER_RELOC_OFFSET
    detail_menu_va = PAYLOAD_VA + DETAIL_MENU_OFFSET
    tech_ctor = asm(
        f"""
            push 0x14
            call 0x470C5C
            add esp, 4
            test eax, eax
            je clear_slot
            push 13
            push 1
            push 3
            push 0x{path_va:X}
            push 72
            push 4
            mov ecx, eax
            call 0x401C20
            test eax, eax
            je clear_slot
            push eax
            mov ecx, [esp]
            mov edx, [ecx]
            call dword ptr [edx + 0x0C]
            cmp eax, 99
            jne reject_wrapper
            mov ecx, [esp]
            mov edx, [ecx]
            call dword ptr [edx + 0x10]
            cmp eax, 35
            jne reject_wrapper
            pop eax
            mov dword ptr [esi + 0x74], eax
            push eax
            mov ecx, esi
            call 0x40C190
            jmp continue
        reject_wrapper:
            pop ecx
            mov eax, [ecx]
            mov edx, [eax]
            push 1
            call edx
        clear_slot:
            mov dword ptr [esi + 0x74], 0
        continue:
            mov eax, esi
            mov ecx, dword ptr [esp + 0x4C]
            jmp 0x43E16B
        """,
        tech_ctor_va,
    )
    detail_ctor = asm(
        f"""
            push 0x14
            call 0x470C5C
            add esp, 4
            test eax, eax
            je cleanup
            push 2
            push 1
            push 3
            push 0x{path_va:X}
            push 72
            push 4
            mov ecx, eax
            call 0x401C20
            test eax, eax
            je cleanup
            push eax
            mov ecx, [esp]
            mov edx, [ecx]
            call dword ptr [edx + 0x0C]
            cmp eax, 99
            jne reject_wrapper
            mov ecx, [esp]
            mov edx, [ecx]
            call dword ptr [edx + 0x10]
            cmp eax, 35
            jne reject_wrapper
            pop eax
            push eax
            mov ecx, esi
            call 0x40C190
            jmp cleanup
        reject_wrapper:
            pop ecx
            mov eax, [ecx]
            mov edx, [eax]
            push 1
            call edx
        cleanup:
            mov dword ptr [0x4D905C], 0
            mov dword ptr [0x4D9058], 0
            mov eax, esi
            jmp 0x447A33
        """,
        detail_ctor_va,
    )
    helper = asm(
        """
            mov ecx, dword ptr [ebx + 0x74]
            test ecx, ecx
            jz no_wrapper
            mov eax, dword ptr [ecx]
            mov edx, dword ptr [eax]
            push 1
            call edx
            mov dword ptr [ebx + 0x74], 0
            mov ecx, ebx
        no_wrapper:
            call 0x40C340
            jmp 0x43E23D
        """,
        helper_va,
    )
    # Keystone may choose the equivalent 89 D9 encoding for mov ecx, ebx;
    # the certified helper contract requires the exact 8B CB bytes.
    helper_marker = bytes.fromhex("C743740000000089D9")
    if helper_marker not in helper:
        raise RuntimeError("Tech destructor ECX restore assembly marker missing")
    helper = helper.replace(
        helper_marker,
        bytes.fromhex("C74374000000008BCB"),
        1,
    )
    helper_call = helper.index(b"\xE8")
    helper_jump = helper.index(b"\xE9")
    helper_jz = helper.index(bytes.fromhex("7411"))
    helper_call_target = helper_va + helper_call + 5 + struct.unpack_from("<i", helper, helper_call + 1)[0]
    helper_jump_target = helper_va + helper_jump + 5 + struct.unpack_from("<i", helper, helper_jump + 1)[0]
    helper_jz_target = helper_va + helper_jz + 2 + struct.unpack_from("<b", helper, helper_jz + 1)[0]
    if helper_call_target != 0x40C340 or helper_jump_target != 0x43E23D or helper_jz_target != helper_va + 0x18:
        raise RuntimeError("Tech destructor helper call/continuation target guard mismatch")
    relocated_handler = asm(
        f"""
            cmp dword ptr [esp + 4], 8
            jne original
            cmp dword ptr [esp + 8], 2
            jne original
            call 0x{detail_menu_va:X}
            xor eax, eax
            ret 8
        original:
            sub esp, 0x18
            mov eax, dword ptr [0x4C9FBC]
            jmp 0x448618
        """,
        relocated_handler_va,
    )
    for offset, size, value, label in (
        (TECH_CONSTRUCTOR_OFFSET, 0x80, tech_ctor, "Tech constructor"),
        (DETAIL_HANDLER_OFFSET, 0x40, helper, "destructor helper"),
        (DETAIL_CONSTRUCTOR_OFFSET, 0x80, detail_ctor, "Detail constructor"),
        (DETAIL_HANDLER_RELOC_OFFSET, 0x2B, relocated_handler, "relocated Detail handler"),
    ):
        if len(value) > size:
            raise RuntimeError(f"{label} exceeds reserved payload window")
        payload[offset : offset + size] = value + b"\0" * (size - len(value))
    return bytes(payload), {
        "tech_constructor": {"offset": f"0x{TECH_CONSTRUCTOR_OFFSET:X}", "length": len(tech_ctor), "sha256": sha(tech_ctor)},
        "detail_constructor": {"offset": f"0x{DETAIL_CONSTRUCTOR_OFFSET:X}", "length": len(detail_ctor), "sha256": sha(detail_ctor)},
        "destructor_helper": {"offset": f"0x{TECH_DESTRUCTOR_HELPER_OFFSET:X}", "length": len(helper), "sha256": sha(helper), "va": f"0x{helper_va:X}", "scalar_destructor_flag": 1, "ecx_restore": "mov ecx, ebx", "continuation_va": "0x43E23D", "sub_40C340_call": "0x40C340", "no_wrapper_branch_va": f"0x{helper_jz_target:X}"},
        "runtime_dimension_guard": {
            "accessors": {
                "width": {"wrapper_vtable_offset": "0x0C", "va": "0x401470"},
                "height": {"wrapper_vtable_offset": "0x10", "va": "0x4014B0"},
            },
            "required_frame_dimensions": [99, 35],
            "static_strip_dimensions": [297, 35],
            "static_grid": [3, 1],
            "reject": {"scalar_destructor_flag": 1, "attach": False, "tech_slot": None},
            "tech_constructor_guarded": True,
            "detail_constructor_guarded": True,
        },
        "detail_handler_relocated": {"offset": f"0x{DETAIL_HANDLER_RELOC_OFFSET:X}", "length": len(relocated_handler), "sha256": sha(relocated_handler), "va": f"0x{relocated_handler_va:X}"},
        "direct_factory": "sub_401C20",
        "parent_insertion": "sub_40C190",
        "detail_cleanup": "list-owned sub_40C300",
        "forbidden_helpers": ["sub_40D8A0", "sub_401140", "sub_401600"],
        "path_va": f"0x{path_va:X}",
        "events": {"tech": 13, "detail": 2},
        "grid": [3, 1],
        "local": [72, 4],
    }


def export_map(data: bytes) -> dict[str, dict[str, int]]:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    coff = pe + 4
    sections = struct.unpack_from("<H", data, coff + 2)[0]
    optional_size = struct.unpack_from("<H", data, coff + 16)[0]
    optional = coff + 20
    section_table = optional + optional_size
    export_rva = struct.unpack_from("<I", data, optional + 96)[0]

    def raw(rva: int) -> int:
        for index in range(sections):
            entry = section_table + index * 40
            virtual_size, section_rva, raw_size, raw_offset = struct.unpack_from(
                "<IIII", data, entry + 8
            )
            if section_rva <= rva < section_rva + max(virtual_size, raw_size):
                return raw_offset + rva - section_rva
        raise RuntimeError(f"unmapped RVA 0x{rva:X}")

    directory = raw(export_rva)
    ordinal_base, function_count, name_count = struct.unpack_from(
        "<III", data, directory + 16
    )
    functions_rva, names_rva, ordinals_rva = struct.unpack_from(
        "<III", data, directory + 28
    )
    result: dict[str, dict[str, int]] = {}
    for index in range(name_count):
        name_rva = struct.unpack_from("<I", data, raw(names_rva) + index * 4)[0]
        cursor = raw(name_rva)
        end = data.index(0, cursor)
        name = data[cursor:end].decode("ascii")
        ordinal_index = struct.unpack_from("<H", data, raw(ordinals_rva) + index * 2)[0]
        if ordinal_index >= function_count:
            raise RuntimeError("export ordinal index out of range")
        function_rva = struct.unpack_from(
            "<I", data, raw(functions_rva) + ordinal_index * 4
        )[0]
        result[name] = {"ordinal": ordinal_base + ordinal_index, "rva": function_rva}
    return result


def _put(blob: bytearray, offset: int, size: int, payload: bytes, label: str) -> None:
    if len(payload) > size:
        raise RuntimeError(f"{label} exceeds reserved size: {len(payload):#x}/{size:#x}")
    if any(blob[offset : offset + size]):
        raise RuntimeError(f"{label} overlaps nonzero bytes")
    blob[offset : offset + size] = payload + b"\0" * (size - len(payload))


def _add_string(blob: bytearray, cursor: int, value: bytes, page_va: int) -> tuple[int, int]:
    if not value.endswith(b"\0"):
        value += b"\0"
    end = cursor + len(value)
    if end > SLOT_SIZE:
        raise RuntimeError("slot strings exceed reserved space")
    blob[cursor:end] = value
    return page_va + SLOT_OFFSET + cursor, end


def build_slot(page_va: int, installed: bool) -> tuple[bytes, dict[str, object]]:
    slot = bytearray(SLOT_SIZE)
    slot[0:8] = b"VVFMSLT\0"
    slot[8:12] = (1).to_bytes(4, "little")
    slot[12:16] = int(installed).to_bytes(4, "little")
    slot[16:20] = SLOT_ENTRY_OFFSET.to_bytes(4, "little")
    slot[20:24] = SLOT_SIZE.to_bytes(4, "little")
    entry_va = page_va + SLOT_OFFSET + SLOT_ENTRY_OFFSET
    if not installed:
        body = asm("mov eax, -1; xor edx, edx; ret", entry_va)
        slot[SLOT_ENTRY_OFFSET : SLOT_ENTRY_OFFSET + len(body)] = body
        return bytes(slot), {
            "entry_offset": SLOT_ENTRY_OFFSET,
            "entry_length": len(body),
            "entry_sha256": sha(body),
        }

    cursor = STRINGS_OFFSET
    strings: dict[str, int] = {}
    for key, value in (
        ("dll", b"VVFP Origins Icons.dll"),
        ("result", b"ShowVV4FullMasteryResult"),
        ("user32", b"user32.dll"),
        ("message_box", b"MessageBoxA"),
        (
            "warning",
            b"This upgrade makes permanent changes to your village. Are you sure "
            b"you want to purchase it? Press OK to confirm, or Cancel.",
        ),
        ("caption", b"Origins Upgrades"),
    ):
        if not value.endswith(b"\0"):
            value += b"\0"
        strings[key] = page_va + cursor
        cursor += len(value)
        if cursor > PAGE_SIZE:
            raise RuntimeError("page strings exceed reserved space")

    walker_va = page_va + SLOT_OFFSET + WALKER_OFFSET
    confirm_va = page_va + SLOT_OFFSET + CONFIRM_OFFSET
    entry = asm(
        f"""
            push ebp
            mov ebp, esp
            push ebx
            push esi
            mov esi, ecx
            push edi
            sub esp, 0x10
            mov dword ptr [ebp - 12], edx
            push 0x{strings['dll']:X}
            call dword ptr [0x48A1E0]
            test eax, eax
            jz done
            push 0x{strings['result']:X}
            push eax
            call dword ptr [0x48A1DC]
            test eax, eax
            jz done
            mov dword ptr [ebp - 16], eax
            cmp dword ptr [0x4D6F88], {PRICE}
            jb insufficient
            push 0
            push dword ptr [ebp - 12]
            push 0x50E5AC
            call 0x{walker_va:X}
            add esp, 12
            cmp edx, 1
            je invalid
            test eax, eax
            jz no_change
            call 0x{confirm_va:X}
            cmp eax, 1
            jne done
            cmp dword ptr [0x4D6F88], {PRICE}
            jb insufficient
            push 0
            push dword ptr [ebp - 12]
            push 0x50E5AC
            call 0x{walker_va:X}
            add esp, 12
            cmp edx, 1
            je invalid
            test eax, eax
            jz no_change
            push -1000000
            mov ecx, 0x4D6F88
            call 0x41E300
            push 1
            push dword ptr [ebp - 12]
            push 0x50E5AC
            call 0x{walker_va:X}
            add esp, 12
            mov dword ptr [ebp - 20], eax
            push dword ptr [ebp - 20]
            push 1
            call dword ptr [ebp - 16]
            jmp done
        no_change:
            push 0
            push 0
            call dword ptr [ebp - 16]
            jmp done
        insufficient:
            push 0
            push 2
            call dword ptr [ebp - 16]
            jmp done
        invalid:
            push 0
            push 3
            call dword ptr [ebp - 16]
        done:
            add esp, 0x10
            pop edi
            pop esi
            pop ebx
            mov esp, ebp
            pop ebp
            ret
        """,
        entry_va,
    )

    walker = asm(
        f"""
            push ebp
            mov ebp, esp
            push ebx
            push esi
            push edi
            mov esi, dword ptr [ebp + 8]
            xor ebx, ebx
            push dword ptr [ebp + 16]
            push 0
        next:
            cmp ebx, dword ptr [ebp + 12]
            jae walk_done
            cmp byte ptr [esi + 0x1CC4], 0
            je advance
            cmp byte ptr [esi + 0x1CC7], 0
            jne advance
            cmp dword ptr [esi + 0x1C40], 0
            jle advance
            mov edi, 5
            lea edx, [esi + 0x1C5C]
        validate:
            mov eax, dword ptr [edx]
            mov ecx, eax
            and ecx, 0x7FFFFFFF
            jz valid_value
            test eax, 0x80000000
            jne invalid
            cmp ecx, 0x42C80000
            ja invalid
        valid_value:
            add edx, 4
            dec edi
            jne validate
            mov edi, 5
            lea edx, [esi + 0x1C5C]
        change_scan:
            cmp dword ptr [edx], 0x42C80000
            jb changed
            add edx, 4
            dec edi
            jne change_scan
            jmp advance
        changed:
            inc dword ptr [esp]
            cmp dword ptr [esp + 4], 0
            je advance
            xor edi, edi
        skill_loop:
            mov eax, dword ptr [esi + edi*4 + 0x1C5C]
            cmp eax, 0x42C80000
            je skill_next
            push 0x42C80000
            fld dword ptr [esp]
            fsub dword ptr [esi + edi*4 + 0x1C5C]
            fstp dword ptr [esp]
            push edi
            lea ecx, [esi + 0x1C5C]
            call 0x46AD80
        skill_next:
            inc edi
            cmp edi, 5
            jb skill_loop
        advance:
            add esi, {STRIDE}
            inc ebx
            jmp next
        invalid:
            add esp, 8
            xor eax, eax
            mov edx, 1
            jmp walker_exit
        walk_done:
            mov eax, dword ptr [esp]
            add esp, 8
            xor edx, edx
        walker_exit:
            pop edi
            pop esi
            pop ebx
            mov esp, ebp
            pop ebp
            ret
        """,
        walker_va,
    )

    confirm = asm(
        f"""
            push ebp
            mov ebp, esp
            push ebx
            push esi
            push edi
            push 0x{strings['user32']:X}
            call dword ptr [0x48A1E0]
            test eax, eax
            jz cancel
            push 0x{strings['message_box']:X}
            push eax
            call dword ptr [0x48A1DC]
            test eax, eax
            jz cancel
            push 1
            push 0x{strings['caption']:X}
            push 0x{strings['warning']:X}
            push 0
            call eax
            cmp eax, 1
            sete al
            movzx eax, al
            jmp confirm_done
        cancel:
            xor eax, eax
        confirm_done:
            pop edi
            pop esi
            pop ebx
            mov esp, ebp
            pop ebp
            ret
        """,
        confirm_va,
    )
    _put(slot, SLOT_ENTRY_OFFSET, WALKER_OFFSET - SLOT_ENTRY_OFFSET, entry, "entry")
    _put(slot, WALKER_OFFSET, CONFIRM_OFFSET - WALKER_OFFSET, walker, "walker")
    _put(slot, CONFIRM_OFFSET, SLOT_SIZE - CONFIRM_OFFSET, confirm, "confirmation")
    return bytes(slot), {
        "entry_offset": SLOT_ENTRY_OFFSET,
        "entry_length": len(entry),
        "entry_sha256": sha(entry),
        "walker_offset": WALKER_OFFSET,
        "walker_length": len(walker),
        "walker_sha256": sha(walker),
        "confirmation_offset": CONFIRM_OFFSET,
        "confirmation_length": len(confirm),
        "confirmation_sha256": sha(confirm),
        "strings": {key: f"0x{value:X}" for key, value in strings.items()},
    }


def build_dispatcher(page_va: int, bound: int) -> bytes:
    slot_va = page_va + SLOT_OFFSET
    entry_va = slot_va + SLOT_ENTRY_OFFSET
    return asm(
        f"""
            push ebp
            push ebx
            push esi
            push edi
            cmp dword ptr [0x{page_va:X}], 0x344D4656
            jne unavailable
            cmp dword ptr [0x{page_va + 8:X}], 1
            jne unavailable
            cmp dword ptr [0x{slot_va:X}], 0x4D465656
            jne unavailable
            cmp dword ptr [0x{slot_va + 8:X}], 1
            jne unavailable
            cmp dword ptr [0x{slot_va + 12:X}], 1
            jne unavailable
            mov edx, {bound}
            call 0x{entry_va:X}
            jmp done
        unavailable:
            mov eax, -1
        done:
            pop edi
            pop esi
            pop ebx
            pop ebp
            ret
        """,
        page_va + 0x40,
    )


def build_page(page_va: int, slot: bytes, dispatcher: bytes) -> bytes:
    page = bytearray(PAGE_SIZE)
    page[0:8] = b"VFM4PG\0\0"
    page[8:12] = (1).to_bytes(4, "little")
    page[12:16] = PAGE_SIZE.to_bytes(4, "little")
    page[16:20] = SLOT_OFFSET.to_bytes(4, "little")
    page[20:24] = SLOT_SIZE.to_bytes(4, "little")
    page[24:28] = (SLOT_OFFSET + SLOT_ENTRY_OFFSET).to_bytes(4, "little")
    page[28:32] = page_va.to_bytes(4, "little")
    if 0x40 + len(dispatcher) > SLOT_OFFSET:
        raise RuntimeError("base dispatcher overlaps command-7 slot")
    page[0x40 : 0x40 + len(dispatcher)] = dispatcher
    page[SLOT_OFFSET : SLOT_OFFSET + SLOT_SIZE] = slot
    cursor = STRINGS_OFFSET
    for value in (
        b"VVFP Origins Icons.dll\0",
        b"ShowVV4FullMasteryResult\0",
        b"user32.dll\0",
        b"MessageBoxA\0",
        b"This upgrade makes permanent changes to your village. Are you sure "
        b"you want to purchase it? Press OK to confirm, or Cancel.\0",
        b"Origins Upgrades\0",
    ):
        page[cursor : cursor + len(value)] = value
        cursor += len(value)
    return bytes(page)


def section_header(rva: int) -> bytes:
    return (
        b".vv4fm\0\0"
        + PAGE_SIZE.to_bytes(4, "little")
        + rva.to_bytes(4, "little")
        + PAGE_SIZE.to_bytes(4, "little")
        + APPEND_OFFSET.to_bytes(4, "little")
        + b"\0" * 12
        + (0x60000020).to_bytes(4, "little")
    )


def append_layout(layout: dict[str, int], page: bytes) -> dict[str, object]:
    return {
        "original_file_size": f"0x{APPEND_OFFSET:X}",
        "append_offset": f"0x{APPEND_OFFSET:X}",
        "append_length": PAGE_SIZE,
        "append_bytes": page.hex().upper(),
        "virtual_address": f"0x{layout['page_va']:X}",
        "purpose": "append the certified base-owned VV4 command-7 extension page",
        "header_patches": [
            {
                "offset": "0x106",
                "before": "0500",
                "after": "0600",
                "purpose": "add the base-owned .vv4fm section",
            },
            {
                "offset": "0x150",
                "before": layout["old_size_of_image"].to_bytes(4, "little").hex().upper(),
                "after": layout["new_size_of_image"].to_bytes(4, "little").hex().upper(),
                "purpose": "extend SizeOfImage for .vv4fm",
            },
            {
                "offset": "0x2C0",
                "before": "00" * 40,
                "after": section_header(layout["page_rva"]).hex().upper(),
                "purpose": "install the guarded .vv4fm RX section header",
            },
        ],
    }


def build_base_payload(active_payload: bytes, page_va: int) -> bytes:
    payload = bytearray(active_payload)
    dll_offset = payload.find(b"VVFP Origins Icons.dll\0")
    menu_offset = payload.find(b"ShowOriginsUpgradeMenuState\0")
    if dll_offset < 0 or menu_offset < 0:
        raise RuntimeError("base companion strings missing")
    dll_va = PAYLOAD_VA + dll_offset
    menu_va = PAYLOAD_VA + menu_offset
    slot_va = page_va + SLOT_OFFSET
    page_dispatcher_va = page_va + 0x40
    show_dialog = asm(
        f"""
            push ebx
            push esi
            push 0x{dll_va:X}
            call dword ptr [0x48A1E0]
            test eax, eax
            je unavailable
            push 0x{menu_va:X}
            push eax
            call dword ptr [0x48A1DC]
            test eax, eax
            je unavailable
            cmp dword ptr [0x{slot_va:X}], 0x4D465656
            jne no_mastery
            cmp dword ptr [0x{slot_va + 12:X}], 1
            jne no_mastery
            or dword ptr [esp + 0x10], 0x80000
        no_mastery:
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
        PAYLOAD_VA + SHOW_DIALOG_OFFSET,
    )
    tech_menu = bytearray(payload[TECH_MENU_OFFSET : TECH_MENU_OFFSET + TECH_MENU_SIZE])
    village_start = tech_menu.find(bytes.fromhex("83FB0672"))
    legacy_start = tech_menu.find(bytes.fromhex("8B049D"))
    if village_start != 0xEA or legacy_start != 0x127:
        raise RuntimeError("base command block does not match certified layout")
    menu_loop_va = PAYLOAD_VA + TECH_MENU_OFFSET + 6
    legacy_va = PAYLOAD_VA + TECH_MENU_OFFSET + legacy_start
    replacement = asm(
        f"""
            cmp ebx, 6
            jb 0x{legacy_va:X}
            cmp ebx, 7
            jne 0x{menu_loop_va:X}
            mov ecx, esi
            call 0x{page_dispatcher_va:X}
            jmp 0x{menu_loop_va:X}
        """,
        PAYLOAD_VA + TECH_MENU_OFFSET + village_start,
    )
    if len(replacement) > legacy_start - village_start:
        raise RuntimeError("command-7-only dispatch does not fit base block")
    tech_menu[village_start:legacy_start] = replacement + b"\x90" * (
        legacy_start - village_start - len(replacement)
    )
    if len(show_dialog) > SHOW_DIALOG_SIZE:
        raise RuntimeError(
            f"show dialog exceeds reserved base payload block: {len(show_dialog):#x}"
        )
    payload[SHOW_DIALOG_OFFSET : SHOW_DIALOG_OFFSET + SHOW_DIALOG_SIZE] = (
        show_dialog + b"\0" * (SHOW_DIALOG_SIZE - len(show_dialog))
    )
    payload[TECH_MENU_OFFSET : TECH_MENU_OFFSET + TECH_MENU_SIZE] = tech_menu
    return bytes(payload)


def main() -> None:
    stock = STOCK.read_bytes()
    expected_sha = "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220"
    if len(stock) != 929_792 or sha(stock) != expected_sha:
        raise RuntimeError("VV4 stock fixture fingerprint mismatch")
    if not COMPANION.is_file():
        raise RuntimeError("build the certified companion DLL first")

    active = json.loads(ACTIVE_BASE.read_text(encoding="utf-8"))
    payload_patch = next(
        item for item in active["patches"] if int(item["offset"], 0) == PAYLOAD_OFFSET
    )
    active_payload = bytearray(
        bytes.fromhex(payload_patch["after"]).ljust(PAYLOAD_SIZE, b"\0")
    )
    button_png, asset_map = build_button_asset()
    ui_payload, ui_map = build_ui_payload(bytes(active_payload))
    noop_slots: dict[str, bytes] = {}
    installed_slots: dict[str, bytes] = {}
    slot_maps: dict[str, object] = {}
    dispatchers: dict[str, bytes] = {}
    pages: dict[str, bytes] = {}
    installed_pages: dict[str, bytes] = {}
    for mode, layout in LAYOUTS.items():
        noop, noop_map = build_slot(layout["page_va"], False)
        installed, installed_map = build_slot(layout["page_va"], True)
        dispatcher = build_dispatcher(layout["page_va"], layout["bound"])
        noop_slots[mode] = noop
        installed_slots[mode] = installed
        dispatchers[mode] = dispatcher
        pages[mode] = build_page(layout["page_va"], noop, dispatcher)
        installed_pages[mode] = build_page(layout["page_va"], installed, dispatcher)
        slot_maps[mode] = {"noop": noop_map, "installed": installed_map}

    stock_payload = build_base_payload(
        ui_payload, LAYOUTS["collection_progression"]["page_va"]
    )
    expanded_payload = build_base_payload(
        ui_payload, LAYOUTS["experimental_expanded_256"]["page_va"]
    )
    base = deepcopy(active)
    base["id"] = "vv4_enable_origins_exclusive_features_full_mastery_candidate"
    base["name"] = "DISABLED Candidate: VV4 Origins Full Mastery Extension Base"
    base["enabled"] = True
    base["certification_status"] = (
        "disabled corrected UI-geometry candidate awaiting independent recertification"
    )
    base["dependencies"] = []
    base["expanded_shr_relocations"]["patches"] = []
    base["companion_files"] = [
        {
            "source": "data/candidates/VVFP VV4 Full Mastery Candidate.dll",
            "destination": "VVFP Origins Icons.dll",
            "sha256": sha(COMPANION.read_bytes()),
        }
        ,
        {
            "source": str(BUTTON_ASSET.relative_to(ROOT)).replace("/", "/"),
            "destination": BUTTON_DESTINATION,
            "sha256": sha(button_png),
        },
    ]
    base["patches"].append(
        {
            "offset": f"0x{TECH_DESTRUCTOR_CALL_OFFSET:X}",
            "before": "E803E1FCFF",
            "after": rel32_jump(0x43E238, PAYLOAD_VA + TECH_DESTRUCTOR_HELPER_OFFSET).hex().upper(),
            "purpose": "replace the guarded Tech wrapper call with paired scalar-destructor cleanup",
        }
    )
    route_item = next(item for item in base["patches"] if int(item["offset"], 0) == DETAIL_ROUTE_OFFSET)
    route_item["before"] = "83EC18A1BC9F4C00"
    route_item["after"] = (
        rel32_jump(0x448610, PAYLOAD_VA + DETAIL_HANDLER_RELOC_OFFSET) + b"\x90" * 3
    ).hex().upper()
    route_item["purpose"] = "route Detail event 2 through the candidate direct-resource handler"
    base["patches"] = [
        item for item in base["patches"] if int(item["offset"], 0) != 0x7B7A0
    ]
    cure_item = next(item for item in base["patches"] if int(item["offset"], 0) == CURE_OFFSET)
    cure_bytes = bytes.fromhex(cure_item["after"])
    cure_start = cure_bytes.find(bytes.fromhex("53555152565731C0"))
    if cure_start < 0:
        raise RuntimeError("base Cure-only signature missing")
    cure_item["after"] = (b"\0" * cure_start + cure_bytes[cure_start:]).hex().upper()
    cure_item["purpose"] = "preserve Cure all Villagers without commands 6/7/8 router"
    payload_item = next(
        item for item in base["patches"] if int(item["offset"], 0) == PAYLOAD_OFFSET
    )
    payload_item["before"] = (b"\0" * PAYLOAD_SIZE).hex().upper()
    payload_item["after"] = stock_payload.hex().upper()
    payload_item["purpose"] = (
        "install the base Origins core plus candidate-only direct-resource Tech/Detail UI hooks and guarded command-7 slot"
    )
    base["patch_mode_overrides"] = {
        mode: [
            {
                "offset": f"0x{PAYLOAD_OFFSET:X}",
                "before": stock_payload.hex().upper(),
                "after": expanded_payload.hex().upper(),
                "purpose": "retarget only base-owned command-7 page references",
            },
            {
                "offset": "0xCC180",
                "before": (
                    "813D20827200565646507566813D248272004F575500755A"
                    "813D2882720001002000754E833D30827200037545833D34"
                    "82720000753C833D38827200007533833D3C82720000752A"
                    "68C69E480068939E4800FF15E0A1480085C0741668C69E48"
                    "0050FF15DCA1480085C07406B801000000C331C0C3"
                ),
                "after": (
                    "813D20A28500565646507566813D24A285004F575500755A"
                    "813D28A2850001002000754E833D30A28500037545833D34"
                    "82720000753C833D38827200007533833D3C82720000752A"
                    "68C69E480068939E4800FF15E0A1480085C0741668C69E48"
                    "0050FF15DCA1480085C07406B801000000C331C0C3"
                ),
                "purpose": "retarget the four certified expanded .shr header pointers",
            },
        ]
        for mode in (
            "experimental_expanded_256",
            "experimental_expanded_256_progression",
        )
    }
    base["pe_append_transaction"] = {
        "owner": base["id"],
        "section_name": ".vv4fm",
        "append_length": PAGE_SIZE,
        "slot_offset": f"0x{SLOT_OFFSET:X}",
        "slot_length": f"0x{SLOT_SIZE:X}",
        "removal_policy": (
            "dependent slot must equal exact no-op bytes before guarded base restore/truncate"
        ),
        "layouts": {
            mode: append_layout(layout, pages[mode])
            for mode, layout in LAYOUTS.items()
        },
    }

    stock_noop = noop_slots["collection_progression"]
    stock_installed = installed_slots["collection_progression"]
    existing_feature = (
        json.loads(FEATURE_OUT.read_text(encoding="utf-8"))
        if FEATURE_OUT.is_file()
        else {}
    )
    feature_enabled = bool(existing_feature.get("enabled", False))
    feature = {
        "id": "vv4_full_mastery_all_stage_a_candidate",
        "game_id": "vv4",
        "name": (
            "Grant Full Mastery to All Villagers"
            if feature_enabled
            else "DISABLED Candidate: Grant Full Mastery to All Villagers"
        ),
        "enabled": feature_enabled,
        "certification_status": (
            "corrected UI geometry certified by Sol commit 2a952a3; runtime playtest pending"
            if feature_enabled
            else "disabled candidate with baked canonical mockup asset; independent emitted-byte recertification required"
        ),
        "dependencies": [base["id"]],
        "description": (
            "Command-7-only repeatable Buy candidate using native Float32 skill "
            "writer sub_46AD80; commands 6/8 are absent."
        ),
        "companion_files": [],
        "patches": [
            {
                "offset": f"0x{APPEND_OFFSET + SLOT_OFFSET:X}",
                "before": stock_noop.hex().upper(),
                "after": stock_installed.hex().upper(),
                "purpose": "replace only the guarded base-owned no-op slot with command 7",
            }
        ],
        "patch_mode_overrides": {
            mode: [
                {
                    "offset": f"0x{APPEND_OFFSET + SLOT_OFFSET:X}",
                    "before": stock_installed.hex().upper(),
                    "after": installed_slots[mode].hex().upper(),
                    "purpose": "relocate only the dependent command-7 slot for expanded layout",
                }
            ]
            for mode in (
                "experimental_expanded_256",
                "experimental_expanded_256_progression",
            )
        },
        "transaction_contract": {
            "command": 7,
            "price": PRICE,
            "ownership": None,
            "record_bounds": {"stock": 150, "expanded": 256},
            "eligibility": [
                "byte +0x1CC4 != 0",
                "byte +0x1CC7 == 0",
                "signed dword +0x1C40 > 0",
            ],
            "skills": ["+0x1C5C", "+0x1C60", "+0x1C64", "+0x1C68", "+0x1C6C"],
            "target": 100,
            "native_writer": "sub_46AD80 once for each below-100 Float32 skill",
            "native_evaluator": None,
        },
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    BASE_OUT.write_text(json.dumps(base, indent=2) + "\n", encoding="utf-8")
    FEATURE_OUT.write_text(json.dumps(feature, indent=2) + "\n", encoding="utf-8")

    sys.path.insert(0, str(ROOT / "src"))
    from vv_fun_patcher import FunPatch, _pe_checksum_layout, load_builds, load_fun_patches, render_patched_bytes  # noqa: PLC0415

    build = next(item for item in load_builds() if item.id == "vv4")
    compatible = [
        item
        for item in load_fun_patches()
        if item.game_id == "vv4"
        and item.id
        not in {
            "vv4_enable_origins_exclusive_features",
            "vv4_full_mastery_all_stage_a_candidate",
        }
    ]
    renders: dict[str, object] = {}
    for mode in LAYOUTS:
        baseline, _ = render_patched_bytes(STOCK, build, mode)
        base_render, _ = render_patched_bytes(
            STOCK, build, mode, _fun_patches_override=[FunPatch(base)]
        )
        feature_render, applied = render_patched_bytes(
            STOCK, build, mode, _fun_patches_override=[FunPatch(base), FunPatch(feature)]
        )
        all_render, all_applied = render_patched_bytes(
            STOCK,
            build,
            mode,
            _fun_patches_override=[FunPatch(base), FunPatch(feature), *compatible],
        )
        checksum_offset, _ = _pe_checksum_layout(feature_render)
        renders[mode] = {
            "baseline_sha256": sha(bytes(baseline)),
            "base_only_sha256": sha(bytes(base_render)),
            "base_plus_mastery_sha256": sha(bytes(feature_render)),
            "all_current_compatible_sha256": sha(bytes(all_render)),
            "size": len(feature_render),
            "pe_checksum": f"0x{struct.unpack_from('<I', feature_render, checksum_offset)[0]:08X}",
            "owners": sorted({item["owner"] for item in applied}),
            "all_current_owners": sorted({item["owner"] for item in all_applied}),
        }

    artifact = {
        "acceptance_commit": "cd15e3b581df1e3020cfa022814119a97ba18af3",
        "ui_asset_gate": {
            **asset_map,
            "display": "800x600 at 96 DPI",
            "factory": ui_map["direct_factory"],
            "grid": ui_map["grid"],
            "local": ui_map["local"],
            "events": ui_map["events"],
            "add_child": ui_map["parent_insertion"],
            "tech_wrapper": {
                "slot": "this+0x74",
                "destructor_patch_offset": "0x3E238",
                "helper_va": ui_map["destructor_helper"]["va"],
                "helper_length": ui_map["destructor_helper"]["length"],
                "helper_sha256": ui_map["destructor_helper"]["sha256"],
                "scalar_destructor_flag": 1,
                "clear_slot_before_original": True,
                "ecx_restore": ui_map["destructor_helper"]["ecx_restore"],
                "original_cleanup": "sub_40C340",
            },
            "runtime_dimension_guard": ui_map["runtime_dimension_guard"],
            "detail_cleanup": ui_map["detail_cleanup"],
            "forbidden_helpers": ui_map["forbidden_helpers"],
            "route": {
                "tech_event": 13,
                "detail_event": 2,
                "detail_handler_relocated_va": ui_map["detail_handler_relocated"]["va"],
                "detail_route_patch_offset": "0x48610",
            },
            "status": "disabled pending independent emitted-byte recertification",
        },
        "source": {"size": len(stock), "sha256": expected_sha},
        "base_manifest_sha256": sha(BASE_OUT.read_bytes()),
        "feature_manifest_sha256": sha(FEATURE_OUT.read_bytes()),
        "base_stock_payload_sha256": sha(stock_payload),
        "base_expanded_payload_sha256": sha(expanded_payload),
        "companion": {
            "path": "data/candidates/VVFP VV4 Full Mastery Candidate.dll",
            "size": COMPANION.stat().st_size,
            "sha256": sha(COMPANION.read_bytes()),
            "exports": export_map(COMPANION.read_bytes()),
            "required_result": "ShowVV4FullMasteryResult stdcall(status,changed), ret 8",
        },
        "candidate_ui_payload": ui_map,
        "slot_layout": {
            "offset": f"0x{SLOT_OFFSET:X}",
            "length": f"0x{SLOT_SIZE:X}",
            "entry_offset": f"0x{SLOT_ENTRY_OFFSET:X}",
            "walker_offset": f"0x{WALKER_OFFSET:X}",
            "confirmation_offset": f"0x{CONFIRM_OFFSET:X}",
        },
        "layouts": {
            mode: {
                **layout,
                "noop_slot_sha256": sha(noop_slots[mode]),
                "installed_slot_sha256": sha(installed_slots[mode]),
                "dispatcher_sha256": sha(dispatchers[mode]),
                "base_page_sha256": sha(pages[mode]),
                "installed_page_sha256": sha(installed_pages[mode]),
                "slot_map": slot_maps[mode],
            }
            for mode, layout in LAYOUTS.items()
        },
        "references": {
            "absolute": [
                "0x4D6F88 unsigned Technology Points",
                "0x48A1E0 LoadLibraryA IAT",
                "0x48A1DC GetProcAddress IAT",
                "0x46AD80 native Float32 skill writer",
                "0x41E300 native Technology Points writer",
            ],
            "rel32": [
                "base Tech menu -> mode-specific page dispatcher",
                "dispatcher -> mode-specific slot entry",
                "entry -> walker/confirmation",
                "walker -> 0x46AD80",
            ],
            "base_relocations": [],
        },
        "runtime_freeze": {
            f"vv{game}_origins_feature.json": canonical_sha(
                {
                    key: json.loads(
                        (ROOT / "data" / f"vv{game}_origins_feature.json").read_text(
                            encoding="utf-8"
                        )
                    ).get(key)
                    for key in (
                        "patches",
                        "patch_mode_overrides",
                        "expanded_shr_relocations",
                        "dependencies",
                    )
                }
            )
            for game in range(1, 6)
        },
        "rendered_candidates": renders,
    }
    MAP_OUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    DOC_OUT.write_text(
        (
            "# VV4 Full Mastery certified corrected-geometry playtest feature\n\n"
            if feature_enabled
            else "# VV4 Full Mastery disabled baked-asset UI candidate\n\n"
        )
        + "Generated from acceptance contract "
        "`cd15e3b581df1e3020cfa022814119a97ba18af3` plus the repository-owned "
        "canonical mockup and direct-resource ABI gate. "
        + (
            "The exact corrected artifact received FINAL CERTIFIED GO under "
            "`2a952a3`; command 7 is available for isolated runtime playtesting.\n\n"
            if feature_enabled
            else "The command-7 record is disabled. Its candidate-only Tech and Detail "
            "buttons use the repository-owned canonical mockup crop as a deterministic "
            "297x35 RGBA strip; independent emitted-byte recertification is pending.\n\n"
        )
        + f"- Canonical mockup SHA-256: `{CANONICAL_MOCKUP_SHA256}`\n"
        f"- Secondary mockup SHA-256: `{SECONDARY_MOCKUP_SHA256}`\n"
        f"- Canonical crop RGBA SHA-256: `{CANONICAL_CROP_RGBA_SHA256}`\n"
        f"- Candidate button PNG SHA-256: `{BUTTON_PNG_SHA256}` (decoded RGBA `{BUTTON_RGBA_SHA256}`)\n"
        f"- Candidate button path: `{BUTTON_DESTINATION}`; frames: normal, hover, pressed (99x35 each)\n"
        "- Button construction: `sub_401C20`, grid 3x1, local 72,4; Tech event 13 and Detail event 2; parent `sub_40C190`.\n"
        "- Runtime text/style/font helpers and `sub_40D8A0` are absent; the Tech wrapper uses `this+0x74` and paired scalar-destructor cleanup, while Detail uses list-owned `sub_40C300`.\n"
        "- Runtime fail-closed guard calls wrapper vtable slots `+0x0C`/`+0x10` (native `0x401470`/`0x4014B0`) and requires a 99x35 frame before either `sub_40C190` attach; rejected wrappers receive scalar-destructor flag 1, and Tech leaves `this+0x74` null.\n"
        "- The Tech helper emits exact `8B CB` (`mov ecx, ebx`) after clearing `this+0x74` and before `sub_40C340`; its continuation remains `0x43E23D`.\n"
        + f"- Companion SHA-256: `{artifact['companion']['sha256']}`\n"
        f"- Stock installed slot SHA-256: `{artifact['layouts']['collection_progression']['installed_slot_sha256']}`\n"
        f"- Expanded installed slot SHA-256: `{artifact['layouts']['experimental_expanded_256']['installed_slot_sha256']}`\n"
        f"- Stock base+mastery render SHA-256: `{renders['collection_progression']['base_plus_mastery_sha256']}`\n"
        f"- Expanded base+mastery render SHA-256: `{renders['experimental_expanded_256']['base_plus_mastery_sha256']}`\n\n"
        "The feature exposes command 7 only inside its certified base dependency. "
        "Commands 6/8, village-wide Running/Age bytes, direct "
        "skill stores, ownership, Remove, and save-format changes are absent. "
        "The disabled candidate is fail-closed on missing or mismatched companion files, "
        "preserves stock executables, Cure bytes, certified VV3 stock-mode hashes, and "
        "the expanded-256 hold. Independent disassembler recertification is required "
        "before any enablement or player playtest.\n",
        encoding="utf-8",
    )
    output_dir = ROOT / "outputs" / "vv4_full_mastery_candidate"
    output_dir.mkdir(parents=True, exist_ok=True)
    for source_path in (BASE_OUT, FEATURE_OUT, MAP_OUT, DOC_OUT, COMPANION, BUTTON_ASSET):
        shutil.copy2(source_path, output_dir / source_path.name)
    checksum_records: dict[str, object] = {
        "status": "disabled candidate; outputs are for independent recertification only",
        "asset": asset_map,
        "source": {"path": str(STOCK.relative_to(ROOT)), "sha256": expected_sha},
        "artifacts": {},
    }
    for mode in LAYOUTS:
        feature_render, _ = render_patched_bytes(
            STOCK, build, mode, _fun_patches_override=[FunPatch(base), FunPatch(feature)]
        )
        exe_name = f"VV4 - {mode}.exe"
        exe_path = output_dir / exe_name
        exe_path.write_bytes(feature_render)
        checksum_records["artifacts"][mode] = {
            "exe": {"path": str(exe_path.relative_to(ROOT)), "sha256": sha(bytes(feature_render))},
            "png": {"path": str((output_dir / BUTTON_ASSET.name).relative_to(ROOT)), "sha256": BUTTON_PNG_SHA256},
        }
    (output_dir / "checksums.json").write_text(
        json.dumps(checksum_records, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
