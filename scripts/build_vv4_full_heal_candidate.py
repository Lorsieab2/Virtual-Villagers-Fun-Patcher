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
import os
import shutil
import struct
import sys
import uuid
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
# Raw source-of-truth pins are checked before any candidate output is built.
SOURCE_MANIFEST_SHA256 = "2B67B6289DCA031409AD7CDC6488A7B57C95955E7C0E7037E2A13690702F0611"
SOURCE_MAP_SHA256 = "ADBD25BD7BE681D81EE432F012D9F088FEE6A5227E2AA5E1D14932F4CC12C237"

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
    # The font tuple is followed by a variable UTF-16 typeface string before
    # the first DWORD-aligned item.  Skipping only six bytes misaligns every
    # subsequent item on these dialogs.
    pos += 6
    pos, _ = skip(pos)
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
    # D232 fixes the resource layout at a 0x33800 raw/virtual .rsrc span;
    # retain the deterministic zero tail even when the corrected row serializer
    # uses less than that capacity.
    new_size = max(size, 0x33800) if blob_cursor <= size else max((blob_cursor + 0x1FF) & ~0x1FF, 0x33800)
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
    pos += 6; pos, _ = skip(pos); pos = (pos + 3) & ~3
    spans: list[tuple[int, int]] = []
    for _ in range(expected_items):
        pos = (pos + 3) & ~3; start = pos; pos += 24; pos, _ = skip(pos); pos, title = skip(pos)
        words = struct.unpack_from("<H", blob, pos)[0]; pos += 2 + words * 2; end = (pos + 3) & ~3
        spans.append((start, end)); pos = end
    if pos != len(blob): raise RuntimeError("VV4 dialog does not close exactly")
    # Command 4 is the certified five-item group at physical item offsets
    # 20..24 (primary icon, secondary icon, label, price, Buy).  Clone those
    # records exactly, changing only the command-5 title/class/id and Y
    # fields required by the native layout.
    # Insert the new command-5 group immediately before the original item 25
    # (the first item after the command-4 group), preserving all following
    # native rows and their order.
    if len(spans) < 28:
        raise RuntimeError("VV4 dialog has no command-4 insertion boundary")
    rows = [blob[a:b] for a, b in spans[20:25]]
    # DIALOGEX ordinal/class tokens.  Every cloned style/exStyle/x/cx/cy and
    # creation-data tail remains byte-identical to its command-4 source.
    ordinal = lambda n: b"\xff\xff" + struct.pack("<H", n)
    specs = [
        (ordinal(130), ordinal(110), 0xFFFF, 168),
        (ordinal(130), ordinal(109), 1105, 180),
        (ordinal(130), "Full Heal / Cure All".encode("utf-16le") + b"\0\0", 0xFFFF, 170),
        (ordinal(130), "30,000 tech points".encode("utf-16le") + b"\0\0", 0xFFFF, 182),
        (ordinal(128), "Buy".encode("utf-16le") + b"\0\0", 1005, 171),
    ]
    insert_at = spans[25][0]
    out = bytearray(blob[:insert_at])
    for row, (class_token, title_token, control_id, y) in zip(rows, specs):
        def skip_row(pos: int) -> tuple[int, bytes]:
            first = struct.unpack_from("<H", row, pos)[0]
            if first == 0:
                return pos + 2, row[pos:pos + 2]
            if first == 0xFFFF:
                return pos + 4, row[pos:pos + 4]
            start = pos
            pos += 2
            while struct.unpack_from("<H", row, pos)[0] != 0:
                pos += 2
            return pos + 2, row[start:pos + 2]
        pos = 24
        pos, _ = skip_row(pos)
        pos, _ = skip_row(pos)
        # Retain only the creation-data WORD and payload.  The source slice
        # also contains its old end-padding; carrying that padding into a row
        # whose title length changed would shift the next item off its native
        # DWORD boundary.  The outer loop supplies fresh alignment.
        words = struct.unpack_from("<H", row, pos)[0]
        creation_end = pos + 2 + words * 2
        tail = row[pos:creation_end]
        rebuilt = bytearray(row[:24])
        struct.pack_into("<h", rebuilt, 14, y)
        struct.pack_into("<H", rebuilt, 20, control_id)
        rebuilt.extend(class_token)
        rebuilt.extend(title_token)
        rebuilt.extend(tail)
        row = rebuilt
        out.extend(b"\0" * ((4 - (len(out) & 3)) & 3)); out.extend(row)
    out.extend(b"\0" * ((4 - (len(out) & 3)) & 3))
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
    # Embed the authenticated ICO's four image leaves as unique RT_ICON IDs
    # 46..49 and build a real RT_GROUP_ICON 110 that references those leaves.
    artwork = (ROOT / "assets/origins/110-cure-all.ico").read_bytes()
    if sha(artwork) != "83552374DFD7AC1AACC57D371C01C26BA1A438ADF34B904609A72165EB73C5A0":
        raise RuntimeError("VV4 ID 110 artwork source hash mismatch")
    reserved, ico_type, ico_count = struct.unpack_from("<HHH", artwork, 0)
    if (reserved, ico_type, ico_count) != (0, 1, 4):
        raise RuntimeError("VV4 cure-all artwork is not a four-image ICO")
    icon_entries: list[tuple[int, int, int, int, int, int, bytes]] = []
    for i in range(ico_count):
        off = 6 + i * 16
        width, height, colors, reserved8, planes, bpp, size_image, image_off = struct.unpack_from("<BBBBHHII", artwork, off)
        image = artwork[image_off:image_off + size_image]
        if len(image) != size_image:
            raise RuntimeError("VV4 cure-all ICO image escapes source")
        icon_entries.append((width, height, colors, reserved8, planes, bpp, size_image, image))
    icon_type_node = next((child for name, child in tree["entries"] if name == 3), None)
    if icon_type_node is None:
        icon_type_node = {"entries": []}; tree["entries"].append((3, icon_type_node))
    group_type_node = next(child for name, child in tree["entries"] if name == 14)
    # Refuse collisions instead of overwriting an unrelated native icon.
    if any(name in {46, 47, 48, 49} for name, _ in icon_type_node["entries"]):
        raise RuntimeError("VV4 cure-all RT_ICON IDs collide with parent resources")
    icon_leafs: list[tuple[int, dict[str, object]]] = []
    for icon_id, (width, height, colors, reserved8, planes, bpp, size_image, image) in zip(range(46, 50), icon_entries):
        leaf = {"leaf": True, "blob": image, "codepage": 0, "reserved": 0}
        icon_leafs.append((icon_id, leaf))
        icon_type_node["entries"].append((icon_id, {"entries": [(1033, leaf)]}))
    group = bytearray(struct.pack("<HHH", 0, 1, 4))
    for icon_id, (width, height, colors, reserved8, planes, bpp, size_image, image) in zip(range(46, 50), icon_entries):
        group.extend(struct.pack("<BBBBHHIH", width, height, colors, reserved8, planes, bpp, size_image, icon_id))
    group_leaf = {"leaf": True, "blob": bytes(group), "codepage": 0, "reserved": 0}
    group_type_node["entries"] = [(name, child) for name, child in group_type_node["entries"] if name != 110]
    group_type_node["entries"].append((110, {"entries": [(1033, group_leaf)]}))
    candidate = _serialize_resource_tree(base, tree)
    new_size = size + (len(candidate) - len(base))
    # A structural resource repack may need one aligned block of additional
    # .rsrc storage.  The only PE-header fields allowed to change are the
    # .rsrc raw-size and the following .reloc raw-pointer; every other header
    # and every pre-resource byte remains identical.
    if new_size != size:
        # The rebuilt resource block now crosses the old virtual reloc
        # boundary.  Move .reloc by one aligned 0x4000 RVA block while keeping
        # its raw bytes unchanged, and recalculate SizeOfImage/data-directory
        # fields from the resulting layout.
        pe = struct.unpack_from("<I", candidate, 0x3C)[0]
        table = pe + 24 + struct.unpack_from("<H", candidate, pe + 20)[0]
        count = struct.unpack_from("<H", candidate, pe + 6)[0]
        rsrc_header = reloc_header = None
        for i in range(count):
            off = table + i * 40
            name = candidate[off:off + 8].rstrip(b"\0")
            if name == b".rsrc": rsrc_header = off
            elif name == b".reloc": reloc_header = off
        if rsrc_header is None or reloc_header is None:
            raise RuntimeError("VV4 companion section headers are incomplete")
        candidate_mut = bytearray(candidate)
        struct.pack_into("<I", candidate_mut, rsrc_header + 8, new_size)
        old_reloc_rva = struct.unpack_from("<I", base, reloc_header + 12)[0]
        new_reloc_rva = old_reloc_rva + ((new_size - size + 0xFFF) & ~0xFFF)
        struct.pack_into("<I", candidate_mut, reloc_header + 12, new_reloc_rva)
        reloc_virtual_size = struct.unpack_from("<I", candidate_mut, reloc_header + 8)[0]
        struct.pack_into("<I", candidate_mut, pe + 0x50, (new_reloc_rva + reloc_virtual_size + 0xFFF) & ~0xFFF)
        # Relocation directory RVA follows the section move; its size and raw
        # relocation bytes remain unchanged.
        struct.pack_into("<I", candidate_mut, pe + 24 + 96 + 5 * 8, new_reloc_rva)
        _pe_checksum(candidate_mut)
        candidate = bytes(candidate_mut)
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
        normalized_candidate[rsrc_header + 8:rsrc_header + 12] = normalized_base[rsrc_header + 8:rsrc_header + 12]
        normalized_candidate[reloc_header + 20:reloc_header + 24] = normalized_base[reloc_header + 20:reloc_header + 24]
        normalized_candidate[reloc_header + 12:reloc_header + 16] = normalized_base[reloc_header + 12:reloc_header + 16]
        normalized_candidate[pe + 0x50:pe + 0x54] = normalized_base[pe + 0x50:pe + 0x54]
        normalized_candidate[pe + 24 + 96 + 5 * 8:pe + 24 + 96 + 5 * 8 + 4] = normalized_base[pe + 24 + 96 + 5 * 8:pe + 24 + 96 + 5 * 8 + 4]
        normalized_candidate[pe + 24 + 64:pe + 24 + 68] = normalized_base[pe + 24 + 64:pe + 24 + 68]
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
        sub esp, 0x1200
        push 0x{strings['user32']:X}
        call dword ptr [0x48A1E0]
        test eax, eax
        jz dependency_silent
        mov esi, eax
        push 0x{strings['message_box']:X}
        push esi
        call dword ptr [0x48A1DC]
        test eax, eax
        jz dependency_silent
        mov dword ptr [ebp-0x10], eax
        push 0x{strings['wsprintf']:X}
        push esi
        call dword ptr [0x48A1DC]
        test eax, eax
        jz dependency_result
        mov dword ptr [ebp-0x14], eax
        mov dword ptr [ebp-0x18], 0
        mov dword ptr [ebp-0x1C], 0
        lea edi, [ebp-0xA00]
        xor eax, eax
        mov ecx, 600
        rep stosd
        lea edi, [ebp-0xA00]
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
        lea edx, [ebx*4]
        shl edx, 2
        add edx, edi
        mov dword ptr [edx], esi
        mov al, byte ptr [esi+0x1CC4]
        mov byte ptr [edx+9], al
        mov al, byte ptr [esi+0x1CC7]
        mov byte ptr [edx+10], al
        cmp byte ptr [esi+0x1CC4], 0
        je initial_next
        cmp byte ptr [esi+0x1CC7], 0
        jne initial_next
        cmp dword ptr [esi+0x1C40], 0
        jle initial_next
        mov eax, dword ptr [esi+0x1C40]
        mov dword ptr [edx+4], eax
        mov al, byte ptr [esi+0x1C48]
        mov byte ptr [edx+11], al
        cmp eax, 100
        jae initial_health_high
        jmp initial_health_in_range
    initial_health_high:
        mov dword ptr [edx+4], eax
        xor ecx, ecx
        cmp byte ptr [esi+0x1C48], 0
        je initial_store_snapshot
        or cl, 1
        inc dword ptr [ebp-0x18]
        jmp initial_store_snapshot
    initial_health_in_range:
        mov dword ptr [edx+4], eax
        xor ecx, ecx
        cmp byte ptr [esi+0x1C48], 0
        je initial_not_sick
        or cl, 1
        inc dword ptr [ebp-0x18]
    initial_not_sick:
        cmp eax, 100
        jae initial_store_snapshot
        or cl, 2
        inc dword ptr [ebp-0x1C]
    initial_store_snapshot:
        mov byte ptr [edx+8], cl
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
        lea edi, [ebp-0x1100]
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
        lea edi, [ebp-0xA00]
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
        lea edx, [ebx*4]
        shl edx, 2
        add edx, edi
        cmp dword ptr [edx], esi
        jne stale_failure
        mov al, byte ptr [esi+0x1CC4]
        cmp al, byte ptr [edx+9]
        jne stale_failure
        mov al, byte ptr [esi+0x1CC7]
        cmp al, byte ptr [edx+10]
        jne stale_failure
        cmp byte ptr [esi+0x1CC4], 0
        je recheck_zero_snapshot
        cmp byte ptr [esi+0x1CC7], 0
        jne recheck_zero_snapshot
        cmp dword ptr [esi+0x1C40], 0
        jle recheck_zero_snapshot
        mov eax, dword ptr [esi+0x1C40]
        cmp eax, dword ptr [edx+4]
        jne stale_failure
        mov al, byte ptr [esi+0x1C48]
        cmp al, byte ptr [edx+11]
        jne stale_failure
        mov eax, dword ptr [esi+0x1C40]
        xor ecx, ecx
        cmp eax, 100
        jae recheck_health_high
        jmp recheck_health_in_range
    recheck_health_high:
        cmp byte ptr [esi+0x1C48], 0
        je recheck_store_snapshot
        or cl, 1
        inc dword ptr [ebp-0x20]
        jmp recheck_store_snapshot
    recheck_health_in_range:
        xor ecx, ecx
        cmp byte ptr [esi+0x1C48], 0
        je recheck_not_sick
        or cl, 1
        inc dword ptr [ebp-0x20]
    recheck_not_sick:
        cmp eax, 100
        jae recheck_store_snapshot
        or cl, 2
        inc dword ptr [ebp-0x24]
    recheck_store_snapshot:
        cmp cl, byte ptr [edx+8]
        jne stale_failure
        jmp recheck_next
    recheck_zero_snapshot:
        cmp byte ptr [edx+8], 0
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
        lea edx, [ebx*4]
        shl edx, 2
        add edx, edi
        cmp dword ptr [edx], esi
        jne stale_failure
        mov al, byte ptr [esi+0x1CC4]
        cmp al, byte ptr [edx+9]
        jne stale_failure
        mov al, byte ptr [esi+0x1CC7]
        cmp al, byte ptr [edx+10]
        jne stale_failure
        cmp byte ptr [esi+0x1CC4], 0
        je mutate_zero_snapshot
        cmp byte ptr [esi+0x1CC7], 0
        jne mutate_zero_snapshot
        cmp dword ptr [esi+0x1C40], 0
        jle mutate_zero_snapshot
        mov eax, dword ptr [esi+0x1C40]
        cmp eax, dword ptr [edx+4]
        jne stale_failure
        mov al, byte ptr [esi+0x1C48]
        cmp al, byte ptr [edx+11]
        jne stale_failure
        xor ecx, ecx
        cmp eax, 100
        jae mutate_bits_health_done
        cmp eax, 1
        jl mutate_zero_snapshot
        or cl, 2
    mutate_bits_health_done:
        mov eax, dword ptr [esi+0x1C40]
        cmp byte ptr [esi+0x1C48], 0
        je mutate_bits_compare
        or cl, 1
    mutate_bits_compare:
        cmp cl, byte ptr [edx+8]
        jne stale_failure
        test cl, 2
        jz mutate_health_done
        cmp dword ptr [0x4D6F88], 30000
        jb insufficient_failure
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
        lea edx, [ebx*4]
        shl edx, 2
        add edx, edi
        cmp dword ptr [edx], esi
        jne stale_failure
        mov al, byte ptr [esi+0x1CC4]
        cmp al, byte ptr [edx+9]
        jne stale_failure
        mov al, byte ptr [esi+0x1CC7]
        cmp al, byte ptr [edx+10]
        jne stale_failure
        cmp byte ptr [esi+0x1CC4], 0
        je partial_failure
        cmp byte ptr [esi+0x1CC7], 0
        jne partial_failure
        cmp dword ptr [esi+0x1C40], 100
        jne partial_failure
        lea edx, [ebx*4]
        shl edx, 2
        add edx, edi
        mov cl, byte ptr [edx+8]
        test cl, 2
        jz sickness_prestate_exact
        cmp dword ptr [esi+0x1C40], 100
        jne stale_failure
        jmp sickness_prestate_sick
    sickness_prestate_exact:
        mov eax, dword ptr [esi+0x1C40]
        cmp eax, dword ptr [edx+4]
        jne stale_failure
    sickness_prestate_sick:
        cmp byte ptr [edx+8], 1
        jb stale_failure
        inc dword ptr [ebp-0x24]
    mutate_health_done:
        lea edx, [ebx*4]
        shl edx, 2
        add edx, edi
        mov cl, byte ptr [edx+8]
        test cl, 1
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
        lea edx, [ebx*4]
        shl edx, 2
        add edx, edi
        cmp dword ptr [edx], esi
        jne stale_failure
        mov al, byte ptr [esi+0x1CC4]
        cmp al, byte ptr [edx+9]
        jne stale_failure
        mov al, byte ptr [esi+0x1CC7]
        cmp al, byte ptr [edx+10]
        jne stale_failure
        mov cl, byte ptr [edx+8]
        test cl, 1
        jz stale_failure
        test cl, 2
        jz sickness_preclear_health_exact
        cmp dword ptr [esi+0x1C40], 100
        jne stale_failure
        jmp sickness_preclear_ready
    sickness_preclear_health_exact:
        mov eax, dword ptr [esi+0x1C40]
        cmp eax, dword ptr [edx+4]
        jne stale_failure
    sickness_preclear_ready:
        cmp dword ptr [0x4D6F88], 30000
        jb insufficient_failure
        mov byte ptr [esi+0x1C48], 0
        mov ecx, 0x50E568
        push ebx
        call 0x466040
        mov esi, eax
        test esi, esi
        jz partial_failure
        lea edx, [ebx*4]
        shl edx, 2
        add edx, edi
        cmp dword ptr [edx], esi
        jne stale_failure
        mov al, byte ptr [esi+0x1CC4]
        cmp al, byte ptr [edx+9]
        jne stale_failure
        mov al, byte ptr [esi+0x1CC7]
        cmp al, byte ptr [edx+10]
        jne stale_failure
        cmp byte ptr [esi+0x1C48], 0
        jne partial_failure
        cmp byte ptr [edx+8], 1
        jb stale_failure
        mov cl, byte ptr [edx+8]
        test cl, 2
        jz sickness_postclear_health_original
        cmp dword ptr [esi+0x1C40], 100
        jne partial_failure
        jmp sickness_postclear_health_done
    sickness_postclear_health_original:
        mov eax, dword ptr [esi+0x1C40]
        cmp eax, dword ptr [edx+4]
        jne partial_failure
    sickness_postclear_health_done:
        cmp dword ptr [esi+0x1C40], 0
        jle partial_failure
        inc dword ptr [0x4D6DF0]
        inc dword ptr [ebp-0x20]
    mutate_next:
        inc ebx
        jmp mutate_loop
    mutate_zero_snapshot:
        cmp byte ptr [edx+8], 0
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
        lea edx, [ebx*4]
        shl edx, 2
        add edx, edi
        cmp dword ptr [edx], esi
        jne partial_failure
        mov al, byte ptr [esi+0x1CC4]
        cmp al, byte ptr [edx+9]
        jne partial_failure
        mov al, byte ptr [esi+0x1CC7]
        cmp al, byte ptr [edx+10]
        jne partial_failure
        cmp byte ptr [esi+0x1CC4], 0
        je postverify_zero_snapshot
        cmp byte ptr [esi+0x1CC7], 0
        jne postverify_zero_snapshot
        cmp dword ptr [esi+0x1C40], 0
        jle postverify_zero_snapshot
        mov cl, byte ptr [edx+8]
        test cl, 2
        jz postverify_health_done
        cmp dword ptr [esi+0x1C40], 100
        jne partial_failure
    postverify_health_done:
        test cl, 0x2
        jnz postverify_health_exact100
        mov eax, dword ptr [esi+0x1C40]
        cmp eax, dword ptr [edx+4]
        jne partial_failure
        jmp postverify_sickness
    postverify_health_exact100:
        cmp dword ptr [esi+0x1C40], 100
        jne partial_failure
    postverify_sickness:
        test cl, 1
        jz postverify_sickness_original
        cmp byte ptr [esi+0x1C48], 0
        jne partial_failure
        jmp postverify_next
    postverify_sickness_original:
        mov al, byte ptr [esi+0x1C48]
        cmp al, byte ptr [edx+11]
        jne partial_failure
    postverify_zero_snapshot:
        cmp byte ptr [edx+8], 0
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
        cmp dword ptr [0x4D6F88], 30000
        jb insufficient_failure
        mov ecx, 0x4D6F88
        push -30000
        call 0x41E300
        mov eax, dword ptr [ebp-0x20]
        mov edx, dword ptr [ebp-0x24]
        mov esi, 0x{strings['success']:X}
        jmp result_show
    dependency_silent:
        add esp, 0x1200
        pop edi
        pop esi
        pop ebx
        pop ebp
        jmp 0x{RESULT_CONTINUATION_VA:X}
    dependency_result:
        push 0
        push 0x{strings['caption']:X}
        push 0x{strings['dependency']:X}
        push 0
        call dword ptr [ebp-0x10]
        add esp, 16
        add esp, 0x1200
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
        lea edi, [ebp-0x1100]
        push edi
        call dword ptr [ebp-0x14]
        add esp, 16
        push 0
        push 0x{strings['caption']:X}
        push edi
        push 0
        call dword ptr [ebp-0x10]
        add esp, 0x1200
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
    decoded = [insn for stream, start in streams for insn in cs.disasm(stream, start)]
    seen = len(decoded)
    boundaries = {insn.address for insn in decoded}
    external = {CONTINUATION_VA, RESULT_CONTINUATION_VA, 0x466040, 0x46AF00, 0x41E300, 0x48A1DC, 0x48A1E0}
    for insn in decoded:
        if not (insn.mnemonic.startswith("j") or insn.mnemonic == "call"):
            continue
        if not insn.op_str.startswith("0x"):
            continue
        target = int(insn.op_str.split()[0], 16)
        if target in external:
            continue
        if PAGE_VA <= target < PAGE_VA + STRINGS_OFFSET:
            if target not in boundaries:
                raise RuntimeError(f"VV4HC branch target is not an instruction boundary: {insn.mnemonic} {insn.op_str}")
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
            "snapshot": "[ebp-0xA00..ebp-0xA1] (0x960 bytes; 150 independent 16-byte slots: pointer, health, bits, active/status, sickness)",
            "format_buffer": "[ebp-0x1100..ebp-0xF01] (512 bytes)",
            "frame_allocation": "sub esp,0x1200; epilogue add esp,0x1200 then pop edi/esi/ebx/ebp",
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


def _generate_into(output_root: Path) -> dict[str, object]:
    manifest_bytes = MANIFEST.read_bytes()
    map_bytes = MAP.read_bytes()
    if sha(manifest_bytes) != SOURCE_MANIFEST_SHA256 or sha(map_bytes) != SOURCE_MAP_SHA256:
        raise RuntimeError("VV4 source manifest/map raw hash pin failed before output")
    manifest = json.loads(manifest_bytes.decode("utf-8-sig"))
    artifact_map = json.loads(map_bytes.decode("utf-8-sig"))
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


def generate(output_root: Path) -> dict[str, object]:
    """Build into a unique sibling staging directory, then publish once."""
    output_root = Path(output_root)
    if os.path.lexists(output_root):
        raise RuntimeError("VV4 output destination already exists")
    parent = output_root.parent
    parent.mkdir(parents=True, exist_ok=True)
    stage = parent / f".{output_root.name}.staging-{uuid.uuid4().hex}"
    if os.path.lexists(stage):
        raise RuntimeError("VV4 staging collision")
    try:
        result = _generate_into(stage)
        required = [stage / "vv4hc-page.bin", stage / "VVFP Origins Icons.dll", stage / MANIFEST.name, stage / MAP.name, stage / "emission-audit.json"]
        required.extend(stage.glob("VV4 - *.exe"))
        if not required or any(not p.is_file() or p.stat().st_size == 0 for p in required):
            raise RuntimeError("VV4 staged output verification failed")
        if os.path.lexists(output_root):
            raise RuntimeError("VV4 destination appeared before atomic publish")
        os.replace(stage, output_root)
        return result
    except Exception:
        if os.path.lexists(stage):
            shutil.rmtree(stage)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    generate(args.output_root.resolve())


if __name__ == "__main__":
    main()
