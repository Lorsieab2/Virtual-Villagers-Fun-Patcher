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
RESULT_CONTINUATION_VA = 0x4895D9
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
    # Walk every original item and require an exact close.  This catches
    # malformed DIALOGEX blobs before any candidate bytes are emitted.
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
    if pos != len(blob):
        raise RuntimeError("VV4 companion dialog does not close exactly")
    return title_start, pos - 6, text


def _parse_resource_tree(data: bytes) -> tuple[int, int, int, dict[str, object]]:
    raw, size, rva = _dll_rsrc_section(data)
    sec = data[raw : raw + size]
    def directory(off: int) -> dict[str, object]:
        named, ids = struct.unpack_from("<HH", sec, off + 12)
        entries: list[tuple[int, object]] = []
        for i in range(named + ids):
            ent = off + 16 + i * 8
            name, child = struct.unpack_from("<II", sec, ent)
            if name & 0x80000000:
                raise RuntimeError("VV4 companion named resource is unsupported")
            if child & 0x80000000:
                entries.append((name, directory(child & 0x7FFFFFFF)))
            else:
                de = child & 0x7FFFFFFF
                data_rva, length, cp, reserved = struct.unpack_from("<IIII", sec, de)
                start = raw + data_rva - rva
                if start < raw or start + length > raw + size:
                    raise RuntimeError("VV4 companion resource leaf escapes section")
                entries.append((name, {"leaf": True, "blob": data[start:start + length], "codepage": cp, "reserved": reserved}))
        return {"entries": entries}
    return raw, size, rva, directory(0)


def _serialize_resource_tree(data: bytes, tree: dict[str, object]) -> bytes:
    raw, size, rva = _dll_rsrc_section(data)
    directories: list[tuple[dict[str, object], int]] = []
    def reserve(node: dict[str, object]) -> None:
        off = sum(16 + 8 * len(n["entries"]) for n, _ in directories)
        directories.append((node, off))
        for _, child in node["entries"]:
            if not child.get("leaf"):
                reserve(child)
    reserve(tree)
    directory_offsets = {id(node): off for node, off in directories}
    data_entries: list[tuple[dict[str, object], int]] = []
    seen_leaves: set[int] = set()
    def collect(node: dict[str, object]) -> None:
        for _, child in node["entries"]:
            if child.get("leaf"):
                if id(child) not in seen_leaves:
                    data_entries.append((child, 0)); seen_leaves.add(id(child))
            else:
                collect(child)
    collect(tree)
    directory_end = sum(16 + 8 * len(node["entries"]) for node, _ in directories)
    data_entry_start = (directory_end + 3) & ~3
    blob_cursor = (data_entry_start + 16 * len(data_entries) + 3) & ~3
    blobs: list[tuple[dict[str, object], int]] = []
    for leaf, _ in data_entries:
        blob_cursor = (blob_cursor + 3) & ~3
        blobs.append((leaf, blob_cursor))
        blob_cursor += len(leaf["blob"])
    new_size = size if blob_cursor <= size else (blob_cursor + 0x1FF) & ~0x1FF
    sec = bytearray(new_size)
    for node, off in directories:
        entries = node["entries"]
        struct.pack_into("<HH", sec, off + 12, 0, len(entries))
        for i, (name, child) in enumerate(entries):
            ent = off + 16 + i * 8
            struct.pack_into("<I", sec, ent, name)
            target = directory_offsets[id(child)] | 0x80000000 if not child.get("leaf") else 0
            if child.get("leaf"):
                target = 0
            struct.pack_into("<I", sec, ent + 4, target)
    # Allocate data-entry records after directories, then point directory
    # entries at them.  This keeps every data blob structurally aligned.
    data_entry_offsets = {id(leaf): data_entry_start + i * 16 for i, (leaf, _) in enumerate(data_entries)}
    blob_offsets = {id(leaf): off for leaf, off in blobs}
    for node, off in directories:
        for i, (name, child) in enumerate(node["entries"]):
            if not child.get("leaf"):
                continue
            de_off = data_entry_offsets[id(child)]
            blob_off = blob_offsets[id(child)]
            struct.pack_into("<I", sec, off + 16 + i * 8 + 4, de_off)
            struct.pack_into("<IIII", sec, de_off, rva + blob_off, len(child["blob"]), child.get("codepage", 0), child.get("reserved", 0))
    for leaf, blob_off in blobs:
        sec[blob_off:blob_off + len(leaf["blob"])] = leaf["blob"]
    result = bytearray(data)
    if new_size > size:
        delta = new_size - size
        result[raw:raw + size] = sec
        pe = struct.unpack_from("<I", result, 0x3C)[0]
        table = pe + 24 + struct.unpack_from("<H", result, pe + 20)[0]
        count = struct.unpack_from("<H", result, pe + 6)[0]
        for i in range(count):
            off = table + i * 40
            name = result[off:off + 8].rstrip(b"\0")
            if name == b".rsrc":
                struct.pack_into("<I", result, off + 16, new_size)
            elif name == b".reloc":
                ptr = struct.unpack_from("<I", result, off + 20)[0]
                struct.pack_into("<I", result, off + 20, ptr + delta)
    else:
        result[raw:raw + size] = sec
    return bytes(result)


def _append_dialog_row(blob: bytes, expected_items: int) -> bytes:
    # Strictly parse item boundaries and duplicate a five-control native row.
    if struct.unpack_from("<H", blob, 16)[0] != expected_items:
        raise RuntimeError("VV4 dialog item count drift")
    def skip(pos: int) -> tuple[int, bytes]:
        first = struct.unpack_from("<H", blob, pos)[0]
        if first == 0: return pos + 2, blob[pos:pos + 2]
        if first == 0xFFFF: return pos + 4, blob[pos:pos + 4]
        start = pos; pos += 2
        while struct.unpack_from("<H", blob, pos)[0] != 0: pos += 2
        return pos + 2, blob[start:pos + 2]
    pos = 26
    for _ in range(3): pos, _ = skip(pos)
    pos += 6; pos = (pos + 3) & ~3
    spans: list[tuple[int, int]] = []
    for _ in range(expected_items):
        pos = (pos + 3) & ~3; start = pos; pos += 24; pos, _ = skip(pos); pos, title = skip(pos)
        words = struct.unpack_from("<H", blob, pos)[0]; pos += 2 + words * 2; end = (pos + 3) & ~3
        spans.append((start, end)); pos = end
    if pos != len(blob): raise RuntimeError("VV4 dialog does not close exactly")
    # Command 4 is the fifth five-item group (title/price/Buy/icon/static).
    # Insert the new command-5 group immediately before the existing next
    # group, preserving all following native rows and their order.
    if len(spans) < 28:
        raise RuntimeError("VV4 dialog has no command-4 insertion boundary")
    rows = [blob[a:b] for a, b in spans[22:27]]
    label = "Full Heal / Cure All".encode("utf-16le") + b"\0\0"
    price = "30,000 tech points".encode("utf-16le") + b"\0\0"
    buy = "Buy".encode("utf-16le") + b"\0\0"
    insert_at = spans[27][0]
    out = bytearray(blob[:insert_at])
    for index, row in enumerate(rows):
        token = label if index == 0 else price if index == 1 else buy if index == 2 else b"\0\0"
        # Rebuild a bounded native control from its certified header/class;
        # this avoids carrying unrelated creation data into the inserted row.
        pos = 24
        pos, class_token = skip(pos)
        row = bytearray(row[:24] + class_token + token + b"\0\0")
        if index == 2 and len(row) >= 22:
            row = row[:20] + struct.pack("<H", 1005) + row[22:]
        out.extend(b"\0" * ((4 - (len(out) & 3)) & 3)); out.extend(row)
    out.extend(blob[insert_at:])
    struct.pack_into("<H", out, 16, expected_items + 5)
    return bytes(out)


def build_resource_only_companion(base: bytes) -> tuple[bytes, str]:
    """Rebuild dialogs 201/203 with the native five-item command row."""
    if len(base) != PARENT_DLL_SIZE or sha(base) != PARENT_DLL_SHA256:
        raise RuntimeError("VV4 companion DLL preimage mismatch")
    raw, size, rva, tree = _parse_resource_tree(base)
    def leaf_for(path: tuple[int, int, int]) -> dict[str, object]:
        node = tree
        for key in path:
            node = next(child for name, child in node["entries"] if name == key)
        return node
    for ident, count in ((201, 41), (203, 31)):
        leaf = leaf_for((5, ident, 1033)); start, end, title = _dialog_title(leaf["blob"], count)
        if title != "Origins Upgrades": raise RuntimeError("VV4 dialog caption drift")
        leaf["blob"] = _append_dialog_row(leaf["blob"], count)
    untouched = leaf_for((5, 202, 1033))["blob"]
    # Existing icon group IDs 101..109 are preserved; ID 110 is added from the
    # authenticated repository artwork source as a deterministic RT_GROUP_ICON leaf.
    icons = next(child for name, child in tree["entries"] if name == 14)
    if not any(name == 110 for name, _ in icons["entries"]):
        artwork = (ROOT / "assets/origins/110-cure-all.ico").read_bytes()
        if sha(artwork) != "83552374DFD7AC1AACC57D371C01C26BA1A438ADF34B904609A72165EB73C5A0":
            raise RuntimeError("VV4 ID 110 artwork source hash mismatch")
        # RT_GROUP_ICON references the existing native icon payload; the
        # authenticated artwork remains separately hash-pinned.
        template = next(child for name, child in icons["entries"] if name == 109)
        lang = next(child for name, child in template["entries"])
        icons["entries"].append((110, {"entries": [(1033, lang)]}))
    candidate = _serialize_resource_tree(base, tree)
    new_size = size + (len(candidate) - len(base))
    # A structural resource repack may need one aligned block of additional
    # .rsrc storage.  The only PE-header fields allowed to change are the
    # .rsrc raw-size and the following .reloc raw-pointer; every other header
    # and every pre-resource byte remains identical.
    if new_size != size:
        normalized_candidate = bytearray(candidate[:raw])
        normalized_base = bytearray(base[:raw])
        pe = struct.unpack_from("<I", base, 0x3C)[0]
        table = pe + 24 + struct.unpack_from("<H", base, pe + 20)[0]
        count = struct.unpack_from("<H", base, pe + 6)[0]
        rsrc_header = reloc_header = None
        for i in range(count):
            off = table + i * 40
            name = base[off:off + 8].rstrip(b"\0")
            if name == b".rsrc":
                rsrc_header = off
            elif name == b".reloc":
                reloc_header = off
        if rsrc_header is None or reloc_header is None:
            raise RuntimeError("VV4 companion section headers are incomplete")
        normalized_candidate[rsrc_header + 16:rsrc_header + 20] = normalized_base[rsrc_header + 16:rsrc_header + 20]
        normalized_candidate[reloc_header + 20:reloc_header + 24] = normalized_base[reloc_header + 20:reloc_header + 24]
        if normalized_candidate != normalized_base:
            raise RuntimeError("VV4 companion changed non-resource header bytes")
    elif candidate[:raw] != base[:raw]:
        raise RuntimeError("VV4 companion changed non-resource section bytes")
    if new_size == size:
        if candidate[raw + size:] != base[raw + size:]:
            raise RuntimeError("VV4 companion changed non-resource bytes")
    else:
        old_reloc = raw + size
        new_reloc = raw + new_size
        if candidate[new_reloc:] != base[old_reloc:]:
            raise RuntimeError("VV4 companion changed bytes after structural resource growth")
    # 202 must remain byte-identical and dialogs must expose the exact row.
    _, _, _, leaves = _dll_resource_leaves(candidate)
    for ident, expected in ((201, 46), (203, 36)):
        blob = next(x["blob"] for x in leaves if x["path"] == (5, ident, 1033))
        if struct.unpack_from("<H", blob, 16)[0] != expected:
            raise RuntimeError("VV4 command-5 dialog item count is not certified")
        text = blob.decode("utf-16le", errors="ignore")
        if "Full Heal / Cure All" not in text or "30,000 tech points" not in text or "Buy" not in text:
            raise RuntimeError("VV4 command-5 dialog text is incomplete")
        if struct.pack("<H", 1005) not in blob:
            raise RuntimeError("VV4 command-5 Buy control ID is missing")
    if next(x["blob"] for x in leaves if x["path"] == (5, 202, 1033)) != untouched:
        raise RuntimeError("VV4 dialog 202 changed")
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
        sub esp, 0x400
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
        lea edi, [ebp-0x130]
        xor eax, eax
        mov ecx, 150
        rep stosb
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
        xor edx, edx
        cmp eax, 100
        jle initial_health_in_range
        jmp initial_store_snapshot
    initial_health_in_range:
        xor edx, edx
        cmp byte ptr [esi+0x1C48], 0
        je initial_not_sick
        or dl, 1
        inc dword ptr [ebp-0x18]
    initial_not_sick:
        cmp eax, 100
        jae initial_store_snapshot
        or dl, 2
        inc dword ptr [ebp-0x1C]
    initial_store_snapshot:
        mov byte ptr [edi+ebx], dl
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
        lea edi, [ebp-0x3F0]
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
        je recheck_zero_snapshot
        cmp byte ptr [esi+0x1CC7], 0
        jne recheck_zero_snapshot
        cmp dword ptr [esi+0x1C40], 0
        jle recheck_zero_snapshot
        mov eax, dword ptr [esi+0x1C40]
        xor edx, edx
        cmp eax, 100
        jle recheck_health_in_range
        jmp recheck_store_snapshot
    recheck_health_in_range:
        xor edx, edx
        cmp byte ptr [esi+0x1C48], 0
        je recheck_not_sick
        or dl, 1
        inc dword ptr [ebp-0x20]
    recheck_not_sick:
        cmp eax, 100
        jae recheck_store_snapshot
        or dl, 2
        inc dword ptr [ebp-0x24]
    recheck_store_snapshot:
        cmp dl, byte ptr [edi+ebx]
        jne stale_failure
        jmp recheck_next
    recheck_zero_snapshot:
        cmp byte ptr [edi+ebx], 0
        jne stale_failure
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
        je mutate_zero_snapshot
        cmp byte ptr [esi+0x1CC7], 0
        jne mutate_zero_snapshot
        cmp dword ptr [esi+0x1C40], 0
        jle mutate_zero_snapshot
        mov eax, dword ptr [esi+0x1C40]
        xor edx, edx
        cmp eax, 100
        jae mutate_bits_health_done
        cmp eax, 1
        jl mutate_zero_snapshot
        or dl, 2
    mutate_bits_health_done:
        cmp byte ptr [esi+0x1C48], 0
        je mutate_bits_compare
        or dl, 1
    mutate_bits_compare:
        cmp dl, byte ptr [edi+ebx]
        jne stale_failure
        test dl, 2
        jz mutate_health_done
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
        cmp byte ptr [esi+0x1CC4], 0
        je partial_failure
        cmp byte ptr [esi+0x1CC7], 0
        jne partial_failure
        cmp dword ptr [esi+0x1C40], 100
        jne partial_failure
        inc dword ptr [ebp-0x24]
    mutate_health_done:
        mov dl, byte ptr [edi+ebx]
        test dl, 1
        jz mutate_next
        mov ecx, 0x50E568
        push ebx
        call 0x466040
        mov esi, eax
        test esi, esi
        jz partial_failure
        cmp byte ptr [esi+0x1CC4], 0
        je partial_failure
        cmp byte ptr [esi+0x1CC7], 0
        jne partial_failure
        cmp dword ptr [esi+0x1C40], 0
        jle partial_failure
        cmp byte ptr [esi+0x1C48], 0
        je partial_failure
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
    mutate_zero_snapshot:
        cmp byte ptr [edi+ebx], 0
        jne stale_failure
        jmp mutate_next
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
        je partial_failure
        cmp byte ptr [esi+0x1CC7], 0
        jne partial_failure
        cmp dword ptr [esi+0x1C40], 0
        jle partial_failure
        mov dl, byte ptr [edi+ebx]
        test dl, 2
        jz postverify_health_done
        cmp dword ptr [esi+0x1C40], 100
        jne partial_failure
    postverify_health_done:
        test dl, 1
        jz postverify_next
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
        mov eax, dword ptr [ebp-0x20]
        mov edx, dword ptr [ebp-0x24]
        mov esi, 0x{strings['success']:X}
        jmp result_show
    dependency_failure:
        add esp, 0x400
        pop edi
        pop esi
        pop ebx
        pop ebp
        jmp 0x{RESULT_CONTINUATION_VA:X}
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
        lea edi, [ebp-0x3F0]
        push edi
        call dword ptr [ebp-0x14]
        add esp, 16
        push 0
        push 0x{strings['caption']:X}
        push edi
        push 0
        call dword ptr [ebp-0x10]
        add esp, 0x400
        pop edi
        pop esi
        pop ebx
        pop ebp
        jmp 0x{RESULT_CONTINUATION_VA:X}
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
                    if target in {CONTINUATION_VA, RESULT_CONTINUATION_VA, 0x466040, 0x46AF00, 0x41E300}:
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
            "result_continuation": "0x4895D9 menu loop; non-command-5 shim replay continues at 0x489455",
        },
        "stack_map": {
            "saved_registers": ["[ebp-0x04]", "[ebp-0x08]", "[ebp-0x0C]"],
            "message_box": "[ebp-0x10]",
            "formatter": "[ebp-0x14]",
            "counts": {"sick": "[ebp-0x18]", "partial": "[ebp-0x1C]", "actual_sick": "[ebp-0x20]", "actual_partial": "[ebp-0x24]"},
            "result_locals": ["[ebp-0x30]", "[ebp-0x34]", "[ebp-0x38]"],
            "snapshot": "[ebp-0x130..ebp-0x039] (150 independent bytes)",
            "format_buffer": "[ebp-0x3F0..ebp-0x1F1] (512 bytes)",
            "frame_allocation": "sub esp,0x400; epilogue add esp,0x400 then pop edi/esi/ebx/ebp",
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
            "filename": "VVFP Origins Icons.dll",
            "size": len(companion),
            "sha256": companion_sha,
            "parent_sha256": PARENT_DLL_SHA256,
            "resource_transform": "RT_DIALOG 201/203 structural five-item command-5 row; caption Origins Upgrades; 202 and non-.rsrc bytes unchanged",
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
    (output_root / "VVFP Origins Icons.dll").write_bytes(companion)
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
