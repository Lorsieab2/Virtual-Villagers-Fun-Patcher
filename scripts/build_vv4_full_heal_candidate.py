"""Deterministically emit the disabled VV4 Full Heal audit candidate.

The generator renders the certified VV4 Full Mastery parents in memory, adds a
separate .vv4hc page, and owns exactly the first five bytes of the command-5
boundary.  It never changes tracked metadata and refuses Expanded modes or
unrecognized parent inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/candidates/vv4_full_heal_cure_all_candidate.json"
MAP = ROOT / "data/candidates/vv4_full_heal_cure_all_candidate_map.json"
DOC = ROOT / "docs/vv4-full-heal-candidate.md"
STOCK = ROOT / "research/stock-executables/Virtual Villagers - The Tree of Life.exe"
STOCK_SHA256 = "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220"
PARENT_HASHES = {
    "collection_progression": "CEBF0BC813059A13131CF75E4ECE11C8CCEE460CC98FB16BD87B03F5C20DB86B",
    "immediate_fixed": "6070D3244567815E8880168AEDCB9FF0E43F6720095AE67628089D492DA40133",
}
PARENT_SIZE = 0xE5000
PAGE_RAW = 0xE5000
PAGE_RVA = 0x341000
PAGE_VA = 0x741000
PAGE_SIZE = 0x1000
HOOK_RAW = 0x8960F
HOOK_VA = 0x48960F
HOOK_BEFORE = bytes.fromhex("E941FEFFFF")
HOOK_SUFFIX = bytes.fromhex("724C")
HOOK_AFTER = bytes.fromhex("E9EC792B00")
CONTINUATION_VA = 0x489455
ENTRY_VA = PAGE_VA + 0x100
STRINGS_OFFSET = 0xC00
PARENT_DLL = ROOT / "data/candidates/VVFP VV4 Full Mastery Candidate.dll"
PARENT_DLL_SHA256 = "4E1A83683A875EFE6F67116CDD862927BE1ABCB17DB7AE18143E58E98EAD01E7"
PARENT_DLL_SIZE = 282624

sys.path.insert(0, str(ROOT / ".tools" / "capstone"))
sys.path.insert(0, str(ROOT / ".tools" / "keystone-runtime"))
from capstone import CS_ARCH_X86, CS_MODE_32, Cs  # noqa: E402
from keystone import KS_ARCH_X86, KS_MODE_32, Ks  # noqa: E402


def _dll_rsrc_section(data: bytes) -> tuple[int, int, int]:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe : pe + 4] != b"PE\0\0":
        raise RuntimeError("VV4 companion is not a PE image")
    count = struct.unpack_from("<H", data, pe + 6)[0]
    opt = struct.unpack_from("<H", data, pe + 20)[0]
    table = pe + 24 + opt
    for i in range(count):
        off = table + i * 40
        name = data[off : off + 8].rstrip(b"\0")
        if name == b".rsrc":
            return (struct.unpack_from("<I", data, off + 20)[0],
                    struct.unpack_from("<I", data, off + 16)[0],
                    struct.unpack_from("<I", data, off + 12)[0])
    raise RuntimeError("VV4 companion has no .rsrc section")


def _dll_resource_leaves(data: bytes) -> tuple[int, int, int, list[dict[str, object]]]:
    raw, size, rva = _dll_rsrc_section(data)
    sec = data[raw : raw + size]
    leaves: list[dict[str, object]] = []

    def walk(directory: int, path: tuple[int, ...]) -> None:
        if directory + 16 > len(sec):
            raise RuntimeError("VV4 companion resource directory truncated")
        named, ids = struct.unpack_from("<HH", sec, directory + 12)
        for i in range(named + ids):
            ent = directory + 16 + i * 8
            name, child = struct.unpack_from("<II", sec, ent)
            if name & 0x80000000:
                raise RuntimeError("VV4 companion named resource node unsupported")
            if child & 0x80000000:
                walk(child & 0x7FFFFFFF, path + (name,))
                continue
            data_ent = child & 0x7FFFFFFF
            data_rva, data_len = struct.unpack_from("<II", sec, data_ent)
            data_raw = raw + data_rva - rva
            if data_raw < raw or data_raw + data_len > raw + size:
                raise RuntimeError("VV4 companion resource leaf escapes .rsrc")
            if len(path) != 2:
                raise RuntimeError("VV4 companion resource path is not type/id/language")
            leaves.append({"path": (path[0], path[1], name), "entry": data_ent,
                           "raw": data_raw, "size": data_len,
                           "blob": data[data_raw : data_raw + data_len]})

    walk(0, ())
    return raw, size, rva, leaves


def _dialog_title(blob: bytes, expected_items: int) -> tuple[int, int, str]:
    if len(blob) < 26 or blob[:4] != b"\x01\x00\xff\xff" or struct.unpack_from("<H", blob, 16)[0] != expected_items:
        raise RuntimeError("VV4 companion dialog is not the certified DIALOGEX shape")

    def skip(pos: int) -> tuple[int, bytes]:
        first = struct.unpack_from("<H", blob, pos)[0]
        if first == 0:
            return pos + 2, blob[pos : pos + 2]
        if first == 0xFFFF:
            return pos + 4, blob[pos : pos + 4]
        start = pos
        pos += 2
        while struct.unpack_from("<H", blob, pos)[0] != 0:
            pos += 2
        return pos + 2, blob[start : pos + 2]

    pos = 26
    dialog_title = b""
    for index in range(3):
        pos, token = skip(pos)
        if index == 2:
            dialog_title = token
    if dialog_title[:2] in (b"\0\0", b"\xff\xff"):
        raise RuntimeError("VV4 companion dialog has no string title")
    text = dialog_title[:-2].decode("utf-16le")
    title_start = pos - len(dialog_title)
    # The font tuple follows the title; its exact values are retained.
    pos += 6
    pos = (pos + 3) & ~3
    if not text:
        raise RuntimeError("VV4 companion dialog title is empty")
    return title_start, pos - 6, text
    for _ in range(expected_items):
        pos = (pos + 3) & ~3
        if pos + 24 > len(blob):
            raise RuntimeError("VV4 companion dialog item header truncated")
        pos += 24
        pos, _ = skip(pos)
        title_start = pos
        pos, title_bytes = skip(pos)
        words = struct.unpack_from("<H", blob, pos)[0]
        pos += 2 + words * 2
        pos = (pos + 3) & ~3
        if title_bytes[:2] not in (b"\0\0", b"\xff\xff"):
            return title_start, title_start + len(title_bytes), title_bytes[:-2].decode("utf-16le")
    raise RuntimeError("VV4 companion dialog title token not found")


def build_resource_only_companion(base: bytes) -> tuple[bytes, str]:
    """Repack only RT_DIALOG 201/203; no variable-length in-place overwrite."""
    if len(base) != PARENT_DLL_SIZE or sha(base) != PARENT_DLL_SHA256:
        raise RuntimeError("VV4 companion DLL preimage mismatch")
    raw, size, rva, leaves = _dll_resource_leaves(base)
    targets = {(5, 201, 1033): 41, (5, 203, 1033): 31, (5, 202, 1033): 21}
    replacements: dict[int, bytes] = {}
    for idx, leaf in enumerate(leaves):
        path = leaf["path"]
        if path not in targets:
            continue
        start, end, title = _dialog_title(leaf["blob"], targets[path])
        if path[1] == 202:
            if title != "Villager Upgrades":
                raise RuntimeError("VV4 companion dialog 202 title drift")
            continue
        if title != "Origins Upgrades":
            raise RuntimeError(f"VV4 companion dialog {path[1]} title drift")
        old = leaf["blob"][start:end]
        new = "Full Heal / Cure All".encode("utf-16le") + b"\0\0"
        replacements[idx] = leaf["blob"][:start] + new + leaf["blob"][end:]
    if len(replacements) != 2:
        raise RuntimeError("VV4 companion target dialog set is incomplete")

    # Preserve the resource directory and all unchanged leaves; repack each
    # distinct leaf in place order and update only data-entry RVA/size fields.
    groups: dict[tuple[int, int], list[int]] = {}
    for idx, leaf in enumerate(leaves):
        groups.setdefault((int(leaf["raw"]), int(leaf["size"])), []).append(idx)
    out = bytearray()
    first_data = min(int(leaf["raw"]) for leaf in leaves)
    out.extend(base[raw:first_data])
    cursor = first_data
    updates: dict[int, tuple[int, int]] = {}
    for key in sorted(groups):
        data_raw, old_size = key
        # Compact only certified resource data gaps; directory bytes and leaf
        # contents remain unchanged, while the two grown titles fit without
        # changing the PE section size.
        if data_raw < cursor:
            raise RuntimeError("VV4 companion resource leaves overlap")
        out.extend(b"\0" * ((4 - ((raw + len(out)) & 3)) & 3))
        new_raw = raw + len(out)
        inds = groups[key]
        blob = replacements.get(inds[0], leaves[inds[0]]["blob"])
        out.extend(blob)
        for idx in inds:
            updates[int(leaves[idx]["entry"])] = (new_raw, len(blob))
        cursor = data_raw + old_size
    out.extend(base[cursor : raw + size])
    if len(out) > size:
        raise RuntimeError("VV4 companion .rsrc repack exceeds section capacity")
    out.extend(b"\0" * (size - len(out)))
    for entry, (new_raw, new_size) in updates.items():
        struct.pack_into("<I", out, entry, rva + new_raw - raw)
        struct.pack_into("<I", out, entry + 4, new_size)
    result = bytearray(base)
    result[raw : raw + size] = out
    candidate = bytes(result)
    # Byte identity outside .rsrc is a hard guard.
    if candidate[:raw] != base[:raw] or candidate[raw + size :] != base[raw + size :]:
        raise RuntimeError("VV4 companion changed non-resource bytes")
    return candidate, sha(candidate)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def asm(source: str, address: int) -> bytes:
    encoding, count = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    if not encoding or count == 0:
        raise RuntimeError("Keystone emitted no instructions")
    return bytes(encoding)


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=2, ensure_ascii=False) + "\r\n").encode("utf-8"))


def _pe_checksum(data: bytearray) -> None:
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    checksum = pe + 24 + 64
    struct.pack_into("<I", data, checksum, 0)
    total = 0
    padded = data + (b"\0" if len(data) & 1 else b"")
    for offset in range(0, len(padded), 2):
        total += padded[offset] | (padded[offset + 1] << 8)
        total = (total & 0xFFFF) + (total >> 16)
    total = (total & 0xFFFF) + (total >> 16)
    struct.pack_into("<I", data, checksum, ((total & 0xFFFF) + len(data)) & 0xFFFFFFFF)


def _section_header() -> bytes:
    return (
        b".vv4hc\0\0"
        + struct.pack("<IIII", PAGE_SIZE, PAGE_RVA, PAGE_SIZE, PAGE_RAW)
        + b"\0" * 12
        + struct.pack("<I", 0x60000020)
    )


def _strings() -> tuple[dict[str, int], bytes]:
    values = {
        "user32": b"user32.dll\0",
        "message_box": b"MessageBoxA\0",
        "wsprintf": b"wsprintfA\0",
        "caption": b"Origins Upgrades\0",
        "prompt": b"Full Heal / Cure All will cure %u sick villager(s) and restore partial health for %u villager(s) for 30,000 tech points?\r\nPress OK to confirm, or Cancel.\0",
        "success": b"Full Heal / Cure All cured %u sick villager(s) and restored partial health for %u villager(s).\0",
        "noop": b"No eligible villager requires healing or sickness clearing.\r\nNo tech points have been deducted.\0",
        "cancel": b"Full Heal / Cure All was canceled.\r\nNo tech points have been deducted.\0",
        "insufficient": b"Not enough tech points for Full Heal / Cure All.\r\nNo tech points have been deducted.\0",
        "stale": b"The villager state changed before Full Heal / Cure All could commit.\r\nNo tech points have been deducted.\0",
        "dependency": b"Cure dependencies are unavailable.\r\nNo tech points have been deducted.\0",
        "invalid": b"No valid living villager state was available.\r\nNo tech points have been deducted.\0",
        "partial": b"Full Heal / Cure All stopped after %u sickness clear(s) and %u partial-health restore(s). Native effects may remain; complete rollback is not claimed.\r\nNo tech points have been deducted.\0",
    }
    cursor = STRINGS_OFFSET
    addresses: dict[str, int] = {}
    blob = bytearray(PAGE_SIZE - STRINGS_OFFSET)
    for key, value in values.items():
        addresses[key] = PAGE_VA + cursor
        rel = cursor - STRINGS_OFFSET
        blob[rel : rel + len(value)] = value
        cursor += len(value)
    if cursor > PAGE_SIZE:
        raise RuntimeError("VV4HC strings exceed page")
    return addresses, bytes(blob)


def _assemble_helper(strings: dict[str, int]) -> tuple[bytes, dict[str, object]]:
    shim = asm(
        f"cmp eax, 5; je 0x{ENTRY_VA:X}; jmp 0x{CONTINUATION_VA:X}", PAGE_VA
    )
    source = f"""
    entry:
        push ebp
        mov ebp, esp
        push ebx
        push esi
        push edi
        sub esp, 0x230
        push 0x{strings['user32']:X}
        call dword ptr [0x48A1E0]
        test eax, eax
        jz dependency_failure
        mov esi, eax
        push 0x{strings['message_box']:X}
        push esi
        call dword ptr [0x48A1DC]
        test eax, eax
        jz dependency_failure
        mov dword ptr [ebp-0x10], eax
        push 0x{strings['wsprintf']:X}
        push esi
        call dword ptr [0x48A1DC]
        test eax, eax
        jz dependency_failure
        mov dword ptr [ebp-0x14], eax
        mov dword ptr [ebp-0x18], 0
        mov dword ptr [ebp-0x1C], 0
        xor ebx, ebx
    initial_loop:
        cmp ebx, 150
        jae initial_done
        mov ecx, 0x50E568
        push ebx
        call 0x466040
        mov esi, eax
        test esi, esi
        jz invalid_failure
        cmp byte ptr [esi+0x1CC4], 0
        je initial_next
        cmp byte ptr [esi+0x1CC7], 0
        jne initial_next
        cmp dword ptr [esi+0x1C40], 0
        jle initial_next
        mov eax, dword ptr [esi+0x1C40]
        cmp eax, 100
        jg invalid_failure
        cmp byte ptr [esi+0x1C48], 0
        je initial_not_sick
        inc dword ptr [ebp-0x18]
    initial_not_sick:
        cmp eax, 100
        jae initial_next
        inc dword ptr [ebp-0x1C]
    initial_next:
        inc ebx
        jmp initial_loop
    initial_done:
        cmp dword ptr [ebp-0x18], 0
        jne prompt_ready
        cmp dword ptr [ebp-0x1C], 0
        je noop_failure
    prompt_ready:
        push 30000
        push dword ptr [ebp-0x1C]
        push dword ptr [ebp-0x18]
        push 0x{strings['prompt']:X}
        lea edi, [ebp-0x230]
        push edi
        call dword ptr [ebp-0x14]
        add esp, 20
        push 1
        push 0x{strings['caption']:X}
        push edi
        push 0
        call dword ptr [ebp-0x10]
        cmp eax, 1
        jne cancel_failure
        mov dword ptr [ebp-0x20], 0
        mov dword ptr [ebp-0x24], 0
        xor ebx, ebx
    recheck_loop:
        cmp ebx, 150
        jae recheck_done
        mov ecx, 0x50E568
        push ebx
        call 0x466040
        mov esi, eax
        test esi, esi
        jz stale_failure
        cmp byte ptr [esi+0x1CC4], 0
        je recheck_next
        cmp byte ptr [esi+0x1CC7], 0
        jne recheck_next
        cmp dword ptr [esi+0x1C40], 0
        jle recheck_next
        mov eax, dword ptr [esi+0x1C40]
        cmp eax, 100
        jg stale_failure
        cmp byte ptr [esi+0x1C48], 0
        je recheck_not_sick
        inc dword ptr [ebp-0x20]
    recheck_not_sick:
        cmp eax, 100
        jae recheck_next
        inc dword ptr [ebp-0x24]
    recheck_next:
        inc ebx
        jmp recheck_loop
    recheck_done:
        mov eax, dword ptr [ebp-0x20]
        cmp eax, dword ptr [ebp-0x18]
        jne stale_failure
        mov eax, dword ptr [ebp-0x24]
        cmp eax, dword ptr [ebp-0x1C]
        jne stale_failure
        cmp dword ptr [0x4D6F88], 30000
        jb insufficient_failure
        mov dword ptr [ebp-0x20], 0
        mov dword ptr [ebp-0x24], 0
        xor ebx, ebx
    mutate_loop:
        cmp ebx, 150
        jae postverify_start
        mov ecx, 0x50E568
        push ebx
        call 0x466040
        mov esi, eax
        test esi, esi
        jz partial_failure
        cmp byte ptr [esi+0x1CC4], 0
        je mutate_next
        cmp byte ptr [esi+0x1CC7], 0
        jne mutate_next
        cmp dword ptr [esi+0x1C40], 0
        jle mutate_next
        mov eax, dword ptr [esi+0x1C40]
        cmp eax, 100
        jg partial_failure
        cmp eax, 100
        jge mutate_health_done
        push -1
        push 100
        lea ecx, [esi+0x1C34]
        call 0x46AF00
        mov ecx, 0x50E568
        push ebx
        call 0x466040
        mov esi, eax
        test esi, esi
        jz partial_failure
        cmp dword ptr [esi+0x1C40], 100
        jne partial_failure
        inc dword ptr [ebp-0x24]
    mutate_health_done:
        cmp byte ptr [esi+0x1C48], 0
        je mutate_next
        mov byte ptr [esi+0x1C48], 0
        mov ecx, 0x50E568
        push ebx
        call 0x466040
        mov esi, eax
        test esi, esi
        jz partial_failure
        cmp byte ptr [esi+0x1C48], 0
        jne partial_failure
        inc dword ptr [0x4D6DF0]
        inc dword ptr [ebp-0x20]
    mutate_next:
        inc ebx
        jmp mutate_loop
    postverify_start:
        xor ebx, ebx
    postverify_loop:
        cmp ebx, 150
        jae postverify_done
        mov ecx, 0x50E568
        push ebx
        call 0x466040
        mov esi, eax
        test esi, esi
        jz partial_failure
        cmp byte ptr [esi+0x1CC4], 0
        je postverify_next
        cmp byte ptr [esi+0x1CC7], 0
        jne postverify_next
        cmp dword ptr [esi+0x1C40], 0
        jle postverify_next
        cmp dword ptr [esi+0x1C40], 100
        jne partial_failure
        cmp byte ptr [esi+0x1C48], 0
        jne partial_failure
    postverify_next:
        inc ebx
        jmp postverify_loop
    postverify_done:
        mov eax, dword ptr [ebp-0x20]
        cmp eax, dword ptr [ebp-0x18]
        jne partial_failure
        mov eax, dword ptr [ebp-0x24]
        cmp eax, dword ptr [ebp-0x1C]
        jne partial_failure
        mov ecx, 0x4D6F88
        push -30000
        call 0x41E300
        mov esi, 0x{strings['success']:X}
        jmp result_show
    dependency_failure:
        xor eax, eax
        xor edx, edx
        mov esi, 0x{strings['dependency']:X}
        jmp result_show
    invalid_failure:
        xor eax, eax
        xor edx, edx
        mov esi, 0x{strings['invalid']:X}
        jmp result_show
    noop_failure:
        xor eax, eax
        xor edx, edx
        mov esi, 0x{strings['noop']:X}
        jmp result_show
    cancel_failure:
        xor eax, eax
        xor edx, edx
        mov esi, 0x{strings['cancel']:X}
        jmp result_show
    insufficient_failure:
        xor eax, eax
        xor edx, edx
        mov esi, 0x{strings['insufficient']:X}
        jmp result_show
    stale_failure:
        xor eax, eax
        xor edx, edx
        mov esi, 0x{strings['stale']:X}
        jmp result_show
    partial_failure:
        mov eax, dword ptr [ebp-0x20]
        mov edx, dword ptr [ebp-0x24]
        mov esi, 0x{strings['partial']:X}
    result_show:
        mov dword ptr [ebp-0x30], esi
        mov dword ptr [ebp-0x34], eax
        mov dword ptr [ebp-0x38], edx
        push dword ptr [ebp-0x38]
        push dword ptr [ebp-0x34]
        push dword ptr [ebp-0x30]
        lea edi, [ebp-0x230]
        push edi
        call dword ptr [ebp-0x14]
        add esp, 16
        push 0
        push 0x{strings['caption']:X}
        push edi
        push 0
        call dword ptr [ebp-0x10]
        add esp, 0x230
        pop edi
        pop esi
        pop ebx
        pop ebp
        jmp 0x{CONTINUATION_VA:X}
    """
    body = asm(source, ENTRY_VA)
    if len(body) >= STRINGS_OFFSET - 0x100:
        raise RuntimeError(f"VV4HC helper overlaps strings: {len(body):#x}")
    blob = bytearray(0x100 + len(body))
    blob[: len(shim)] = shim
    blob[0x100:] = body
    return bytes(blob), {
        "helper_length": len(body),
        "helper_sha256": sha(body),
        "shim_bytes": shim.hex().upper(),
        "shim_sha256": sha(shim),
        "body_offset": "0x100",
    }


def _verify_code(page: bytes, helper_length: int) -> None:
    cs = Cs(CS_ARCH_X86, CS_MODE_32)
    cs.detail = True
    streams = [(page[:0x100], PAGE_VA), (page[0x100 : 0x100 + helper_length], ENTRY_VA)]
    seen = 0
    for stream, start in streams:
        for insn in cs.disasm(stream, start):
            seen += 1
            if insn.mnemonic.startswith("j") or insn.mnemonic == "call":
                if insn.op_str.startswith("0x"):
                    target = int(insn.op_str.split()[0], 16)
                    if PAGE_VA <= target < PAGE_VA + STRINGS_OFFSET:
                        continue
                    if target in {CONTINUATION_VA, 0x466040, 0x46AF00, 0x41E300}:
                        continue
                    if target in {0x48A1DC, 0x48A1E0}:
                        continue
                    raise RuntimeError(f"VV4HC branch target escapes certified code: {insn.mnemonic} {insn.op_str}")
    if not seen:
        raise RuntimeError("Capstone emitted no helper instructions")


def build_page() -> tuple[bytes, dict[str, object]]:
    strings, blob = _strings()
    helper, helper_meta = _assemble_helper(strings)
    page = bytearray(PAGE_SIZE)
    page[0x20:0x28] = b"VV4HCPG\0"
    page[0x28:0x2C] = struct.pack("<I", 1)
    page[: len(helper)] = helper
    page[STRINGS_OFFSET:] = blob
    _verify_code(bytes(page), len(helper))
    meta = {
        **helper_meta,
        "page_sha256": sha(bytes(page)),
        "strings_offset": f"0x{STRINGS_OFFSET:X}",
        "strings_sha256": sha(blob),
        "entry_va": f"0x{ENTRY_VA:X}",
        "shim_va": f"0x{PAGE_VA:X}",
        "hook_before": HOOK_BEFORE.hex().upper(),
        "hook_suffix_preserved": HOOK_SUFFIX.hex().upper(),
        "hook_after": HOOK_AFTER.hex().upper(),
        "abi": {
            "resolver": "ECX=0x50E568; push index; call 0x466040; ret 4",
            "health_setter": "ECX=record+0x1C34; push -1; push 100; call 0x46AF00; ret 8",
            "tech_deduction": "ECX=0x4D6F88; push -30000; call 0x41E300; ret 4",
            "people_cured": "inc [0x4D6DF0] after verified sickness clear",
        },
    }
    return bytes(page), meta


def _render_parents() -> dict[str, bytes]:
    if sha(STOCK.read_bytes()) != STOCK_SHA256:
        raise RuntimeError("VV4 stock fingerprint mismatch")
    sys.path.insert(0, str(ROOT / "src"))
    from vv_fun_patcher import identify, render_patched_bytes

    build = identify(STOCK)
    ids = [
        "vv4_complete_scales_golden_fish",
        "vv4_enable_origins_exclusive_features",
        "vv4_full_mastery_all_stage_a_candidate",
        "vv4_write_village_statistics",
    ]
    rendered: dict[str, bytes] = {}
    for mode in PARENT_HASHES:
        data, _ = render_patched_bytes(STOCK, build, mode, ids)
        data = bytes(data)
        if sha(data) != PARENT_HASHES[mode] or len(data) != PARENT_SIZE:
            raise RuntimeError(f"certified VV4 Full Mastery parent mismatch for {mode}")
        rendered[mode] = data
    return rendered


def _patch_parent(parent: bytes, page: bytes) -> bytes:
    if len(parent) != PARENT_SIZE:
        raise RuntimeError("VV4 Full Mastery parent size is not certified")
    if parent[HOOK_RAW : HOOK_RAW + 5] != HOOK_BEFORE or parent[HOOK_RAW + 5 : HOOK_RAW + 7] != HOOK_SUFFIX:
        raise RuntimeError("VV4 command-5 five-byte hook guard failed")
    data = bytearray(parent)
    data[HOOK_RAW : HOOK_RAW + 5] = HOOK_AFTER
    if len(data) != PAGE_RAW:
        raise RuntimeError("VV4HC append offset does not match certified parent")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if struct.unpack_from("<H", data, pe + 6)[0] != 6:
        raise RuntimeError("VV4 parent section count is not six")
    if struct.unpack_from("<I", data, pe + 0x50)[0] != 0x341000:
        raise RuntimeError("VV4 parent SizeOfImage is not 0x341000")
    if any(data[0x2E8 : 0x2E8 + 40]):
        raise RuntimeError("VV4HC section header area is not zero")
    struct.pack_into("<H", data, pe + 6, 7)
    struct.pack_into("<I", data, pe + 0x50, 0x342000)
    data[0x2E8 : 0x2E8 + 40] = _section_header()
    data.extend(page)
    _pe_checksum(data)
    return bytes(data)


def generate(output_root: Path) -> dict[str, object]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    artifact_map = json.loads(MAP.read_text(encoding="utf-8-sig"))
    if manifest["enabled"] or not manifest["catalog_hidden"] or manifest["catalog_enabled"]:
        raise RuntimeError("VV4 Full Heal must remain disabled and catalog-hidden")
    if manifest["source"]["stock_sha256"] != STOCK_SHA256 or artifact_map["source"]["sha256"] != STOCK_SHA256:
        raise RuntimeError("VV4 Full Heal stock fingerprint is not immutable")
    page, page_meta = build_page()
    companion, companion_sha = build_resource_only_companion(PARENT_DLL.read_bytes())
    parents = _render_parents()
    outputs: dict[str, object] = {
        "modes": {}, "page": page_meta,
        "companion": {
            "filename": "VVFP VV4 Full Heal Candidate.dll",
            "size": len(companion),
            "sha256": companion_sha,
            "parent_sha256": PARENT_DLL_SHA256,
            "resource_transform": "RT_DIALOG 201/203 title-only structural repack; 202 and non-.rsrc bytes unchanged",
        },
    }
    for mode, parent in parents.items():
        candidate = _patch_parent(parent, page)
        out = output_root / f"VV4 - {mode}.exe"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(candidate)
        outputs["modes"][mode] = {
            "parent_sha256": sha(parent),
            "candidate_sha256": sha(candidate),
            "size": len(candidate),
            "hook_after": HOOK_AFTER.hex().upper(),
            "preserved_suffix": HOOK_SUFFIX.hex().upper(),
            "section": {"name": ".vv4hc", "raw": "0xE5000", "rva": "0x341000", "va": "0x741000", "size": "0x1000"},
            "uninstall_parent_sha256": sha(parent),
        }
    (output_root / "vv4hc-page.bin").write_bytes(page)
    (output_root / "VVFP VV4 Full Heal Candidate.dll").write_bytes(companion)
    _write(output_root / MANIFEST.name, {**manifest, "emitted_audit": outputs})
    _write(output_root / MAP.name, {**artifact_map, "emitted_audit": outputs})
    (output_root / DOC.name).write_bytes(DOC.read_bytes())
    (output_root / "emission-audit.json").write_text(json.dumps(outputs, indent=2) + "\r\n", encoding="utf-8")
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    generate(args.output_root.resolve())


if __name__ == "__main__":
    main()
