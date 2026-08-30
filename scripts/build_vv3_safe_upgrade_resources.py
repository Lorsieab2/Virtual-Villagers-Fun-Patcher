"""Synchronize the public VV3 companion with the canonical mask build.

The Origins manifest deploys the implementation compiled as
``VVFP VV3 Full Mastery Candidate.dll`` under the historical ``Safe Upgrades``
filename.  The synchronization path below is the active builder.  The older
resource-only helpers remain below for historical artifact analysis, but are
not used to produce the deployed companion.
"""
from __future__ import annotations

import hashlib
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "candidates" / "VVFP VV3 Full Mastery Candidate.dll"
OUTPUT = ROOT / "data" / "candidates" / "VVFP VV3 Safe Upgrades.dll"
FOUNDATION_OUTPUT = (
    ROOT / "data" / "candidates" / "VVFP VV3 Safe Upgrade Foundation.dll"
)
SOURCE_SHA256 = "9DAFDB3B38D02BB642A243C2FDDB68CE0B7DEBA3A013F6A5F9A3FAEA116E3031"
SOURCE_SIZE = 1_895_936
TARGET_COUNTS = {201: 26, 202: 2, 203: 31}
PUBLIC_TARGET_COUNTS = {201: 46, 202: 26, 203: 31}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


REQUIRED_MASK_EXPORTS = frozenset(
    {
        "VV3DrawMaskOnHead",
        "VV3GetMaskAtlas",
        "VV3WorldMaskDrawAt",
        "VV3_GetMaskForRecord",
        "VV3_SetMaskForRecord",
    }
)
REQUIRED_RUNNING_EXPORTS = frozenset({"VV3RunningMaskBoundary"})


def _rva_to_raw(data: bytes, rva: int) -> int:
    """Translate a PE32 RVA to a raw file offset, failing closed."""
    if data[:2] != b"MZ" or len(data) < 0x40:
        raise RuntimeError("VV3 canonical companion is not a PE image")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if pe < 0x40 or pe + 24 > len(data) or data[pe : pe + 4] != b"PE\0\0":
        raise RuntimeError("VV3 canonical companion PE signature is invalid")
    sections = struct.unpack_from("<H", data, pe + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    table = pe + 24 + optional_size
    if table + sections * 40 > len(data):
        raise RuntimeError("VV3 canonical companion section table is truncated")
    for index in range(sections):
        entry = table + index * 40
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from(
            "<IIII", data, entry + 8
        )
        span = max(virtual_size, raw_size)
        if virtual_address <= rva < virtual_address + span:
            raw = raw_offset + (rva - virtual_address)
            if raw_offset <= raw < len(data):
                return raw
            break
    raise RuntimeError(f"VV3 canonical companion RVA {rva:#x} is outside sections")


def export_names(data: bytes) -> frozenset[str]:
    """Read named PE exports without relying on a platform tool."""
    if data[:2] != b"MZ" or len(data) < 0x40:
        raise RuntimeError("VV3 canonical companion is not a PE image")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if pe + 24 > len(data) or data[pe : pe + 4] != b"PE\0\0":
        raise RuntimeError("VV3 canonical companion PE signature is invalid")
    optional = pe + 24
    if struct.unpack_from("<H", data, optional)[0] != 0x10B:
        raise RuntimeError("VV3 canonical companion is not a PE32 DLL")
    export_rva, export_size = struct.unpack_from("<II", data, optional + 96)
    if not export_rva or export_size < 40:
        raise RuntimeError("VV3 canonical companion has no export directory")
    directory = _rva_to_raw(data, export_rva)
    if directory + 40 > len(data):
        raise RuntimeError("VV3 canonical companion export directory is truncated")
    name_count = struct.unpack_from("<I", data, directory + 24)[0]
    names_rva = struct.unpack_from("<I", data, directory + 32)[0]
    names = _rva_to_raw(data, names_rva)
    result: set[str] = set()
    for index in range(name_count):
        entry = names + index * 4
        if entry + 4 > len(data):
            raise RuntimeError("VV3 canonical companion export name table is truncated")
        name_raw = _rva_to_raw(data, struct.unpack_from("<I", data, entry)[0])
        end = data.find(b"\0", name_raw)
        if end < 0:
            raise RuntimeError("VV3 canonical companion export name is unterminated")
        result.add(data[name_raw:end].decode("ascii"))
    return frozenset(result)


def synchronize() -> tuple[int, str, frozenset[str]]:
    """Copy the checked canonical build to the deployed companion path."""
    if not SOURCE.is_file():
        raise RuntimeError(f"missing canonical VV3 companion: {SOURCE}")
    canonical = SOURCE.read_bytes()
    if len(canonical) != SOURCE_SIZE or sha(canonical) != SOURCE_SHA256:
        raise RuntimeError("VV3 canonical companion source fingerprint mismatch")
    exports = export_names(canonical)
    missing = REQUIRED_MASK_EXPORTS - exports
    if missing:
        raise RuntimeError(
            "canonical VV3 companion is missing mask exports: "
            + ", ".join(sorted(missing))
        )
    missing_running = REQUIRED_RUNNING_EXPORTS - exports
    if missing_running:
        raise RuntimeError(
            "canonical VV3 companion is missing Running-boundary exports: "
            + ", ".join(sorted(missing_running))
        )
    OUTPUT.write_bytes(canonical)
    deployed = OUTPUT.read_bytes()
    if deployed != canonical:
        raise RuntimeError("VV3 deployed companion differs from canonical build")
    return len(deployed), sha(deployed), exports


def _resource_section(data: bytes) -> tuple[int, int, int, int]:
    if data[:2] != b"MZ":
        raise RuntimeError("VV3 safe-upgrade companion is not a PE image")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe : pe + 4] != b"PE\0\0":
        raise RuntimeError("VV3 safe-upgrade companion PE signature is invalid")
    count = struct.unpack_from("<H", data, pe + 6)[0]
    optional_size = struct.unpack_from("<H", data, pe + 20)[0]
    table = pe + 24 + optional_size
    for index in range(count):
        entry = table + index * 40
        if data[entry : entry + 8].rstrip(b"\0") == b".rsrc":
            return (
                struct.unpack_from("<I", data, entry + 20)[0],
                struct.unpack_from("<I", data, entry + 16)[0],
                struct.unpack_from("<I", data, entry + 12)[0],
                struct.unpack_from("<I", data, entry + 8)[0],
            )
    raise RuntimeError("VV3 safe-upgrade companion has no .rsrc section")


def resource_leaves(
    data: bytes,
) -> tuple[tuple[tuple[int, int, int], int, int, int, bytes], ...]:
    """Return numeric type/id/language leaves and their data-entry metadata."""
    raw_offset, raw_size, section_rva, _ = _resource_section(data)
    section = data[raw_offset : raw_offset + raw_size]
    leaves: list[tuple[tuple[int, int, int], int, int, int, bytes]] = []

    def walk(directory: int, path: tuple[int, ...]) -> None:
        if directory + 16 > len(section):
            raise RuntimeError("VV3 safe-upgrade resource directory is truncated")
        named, ids = struct.unpack_from("<HH", section, directory + 12)
        if named:
            raise RuntimeError("VV3 safe-upgrade resource tree contains named nodes")
        for index in range(ids):
            entry = directory + 16 + index * 8
            name, child = struct.unpack_from("<II", section, entry)
            if name & 0x80000000:
                raise RuntimeError("VV3 safe-upgrade resource name is not numeric")
            if child & 0x80000000:
                walk(child & 0x7FFFFFFF, path + (name,))
                continue
            leaf_path = path + (name,)
            if len(leaf_path) != 3:
                raise RuntimeError("VV3 safe-upgrade resource leaf is not type/id/language")
            data_entry = child
            data_rva, size = struct.unpack_from("<II", section, data_entry)
            data_raw = raw_offset + data_rva - section_rva
            if data_raw < raw_offset or data_raw + size > raw_offset + raw_size:
                raise RuntimeError("VV3 safe-upgrade resource data escapes .rsrc")
            leaves.append(
                (leaf_path, data_entry, data_raw, size, data[data_raw : data_raw + size])
            )

    walk(0, ())
    return tuple(leaves)


def _skip_dialog_value(blob: bytes, cursor: int) -> int:
    if cursor + 2 > len(blob):
        raise RuntimeError("VV3 safe-upgrade DIALOGEX value is truncated")
    first = struct.unpack_from("<H", blob, cursor)[0]
    if first == 0:
        return cursor + 2
    if first == 0xFFFF:
        if cursor + 4 > len(blob):
            raise RuntimeError("VV3 safe-upgrade DIALOGEX ordinal is truncated")
        return cursor + 4
    cursor += 2
    while cursor + 2 <= len(blob) and blob[cursor : cursor + 2] != b"\0\0":
        cursor += 2
    if cursor + 2 > len(blob):
        raise RuntimeError("VV3 safe-upgrade DIALOGEX string is unterminated")
    return cursor + 2


def dialog_item_spans(
    blob: bytes, *, expected_count: int, exact_end: int | None = None
) -> tuple[tuple[int, int], ...]:
    """Walk the exact DIALOGEX layout used by the authenticated companion."""
    if len(blob) < 26 or blob[:4] != b"\x01\x00\xff\xff":
        raise RuntimeError("VV3 safe-upgrade target is not DIALOGEX")
    count = struct.unpack_from("<H", blob, 16)[0]
    if count != expected_count:
        raise RuntimeError(
            f"VV3 safe-upgrade DIALOGEX count {count} != {expected_count}"
        )
    cursor = 26
    for _ in range(3):
        cursor = _skip_dialog_value(blob, cursor)
    # DIALOGEX font metadata is point size, weight, italic, charset, followed
    # by a UTF-16 face name.  The authenticated dialogs use "Segoe UI".
    cursor += 6
    cursor = _skip_dialog_value(blob, cursor)
    cursor = (cursor + 3) & ~3
    spans: list[tuple[int, int]] = []
    for _ in range(count):
        cursor = (cursor + 3) & ~3
        start = cursor
        if cursor + 24 > len(blob):
            raise RuntimeError("VV3 safe-upgrade DIALOGEX item header is truncated")
        cursor += 24
        cursor = _skip_dialog_value(blob, cursor)
        cursor = _skip_dialog_value(blob, cursor)
        if cursor + 2 > len(blob):
            raise RuntimeError("VV3 safe-upgrade DIALOGEX creation data is truncated")
        words = struct.unpack_from("<H", blob, cursor)[0]
        cursor += 2 + words * 2
        cursor = (cursor + 3) & ~3
        if cursor > len(blob):
            raise RuntimeError("VV3 safe-upgrade DIALOGEX item alignment is truncated")
        spans.append((start, cursor))
    required_end = len(blob) if exact_end is None else exact_end
    if cursor != required_end:
        raise RuntimeError(
            f"VV3 safe-upgrade DIALOGEX end {cursor:#x} != {required_end:#x}"
        )
    return tuple(spans)


# Villager row_count is a hardcoded `mov ebx, 4` immediate in the companion's
# WM_INITDIALOG handler (VA 0x10001412 / file offset 0x812).  The public
# projection carries a fifth Villager Upgrades row (Change Appearance), so its
# output patches this one byte 0x04 -> 0x05 while the shared base DLL and the
# foundation projection keep four rows.  This is the only non-resource byte the
# public transform touches.
VILLAGER_ROW_COUNT_OFFSET = 0x812


def _insert_change_appearance_row(blob: bytes) -> bytes:
    """Insert the Change Appearance row (button 1004) into the 21-item public
    Villager Upgrades dialog (202) by cloning the Set Age to 18 row (items
    15..19), then move Cancel down and grow the dialog height.  The shared base
    DLL is never modified -- only this resource-swap output carries the row."""
    spans = dialog_item_spans(blob, expected_count=21)
    template = [blob[a:b] for a, b in spans[15:20]]
    ordinal = lambda n: b"\xff\xff" + struct.pack("<H", n)
    specs = [
        (ordinal(130), ordinal(106), 0xFFFF, 136),  # primary icon (reuse 106)
        (ordinal(130), ordinal(109), 1104, 148),     # per-row checkmark slot
        (ordinal(130), "Change Appearance".encode("utf-16le") + b"\0\0", 0xFFFF, 138),
        (ordinal(130), "5,000 tech points".encode("utf-16le") + b"\0\0", 0xFFFF, 150),
        (ordinal(128), "Buy".encode("utf-16le") + b"\0\0", 1004, 139),
    ]

    def _creation_tail(row: bytes) -> bytes:
        pos = 24

        def skip(pos: int) -> int:
            first = struct.unpack_from("<H", row, pos)[0]
            if first == 0:
                return pos + 2
            if first == 0xFFFF:
                return pos + 4
            pos += 2
            while struct.unpack_from("<H", row, pos)[0] != 0:
                pos += 2
            return pos + 2

        pos = skip(pos)  # class
        pos = skip(pos)  # title
        words = struct.unpack_from("<H", row, pos)[0]
        return row[pos : pos + 2 + words * 2]

    insert_at = spans[20][0]  # immediately before Cancel
    out = bytearray(blob[:insert_at])
    for row, (class_token, title_token, control_id, y) in zip(template, specs):
        rebuilt = bytearray(row[:24])
        struct.pack_into("<h", rebuilt, 14, y)
        struct.pack_into("<H", rebuilt, 20, control_id)
        rebuilt.extend(class_token)
        rebuilt.extend(title_token)
        rebuilt.extend(_creation_tail(row))
        out.extend(b"\0" * ((4 - (len(out) & 3)) & 3))
        out.extend(rebuilt)
    out.extend(b"\0" * ((4 - (len(out) & 3)) & 3))
    out.extend(blob[insert_at:])
    struct.pack_into("<H", out, 16, 26)
    # Cancel is now item 25; move it below the new row and grow the dialog.
    new_spans = dialog_item_spans(bytes(out), expected_count=26)
    struct.pack_into("<h", out, new_spans[25][0] + 14, 169)
    struct.pack_into("<H", out, 24, 190)
    return bytes(out)


def _filter_dialog(
    blob: bytes, resource_id: int, *, include_individual_full_mastery: bool
) -> bytes:
    source_counts = {201: 46, 202: 21, 203: 36}
    spans = dialog_item_spans(
        blob,
        expected_count=source_counts[resource_id],
    )
    if resource_id == 201:
        if include_individual_full_mastery:
            # Public projection: keep every Tech row.  The payload's row_count
            # gates which are shown -- 6 without the village-wide payload
            # (Time Warp..Cure) and 9 with it -- so the base menu still stops
            # at Cure while the village-wide menu exposes All Villagers Like
            # Running (6), Grant Full Mastery to All (7), and All Villagers
            # are 18 (8).
            keep = set(range(46))
        else:
            # Foundation projection stays base-only (commands 0..4 + Cancel).
            keep = set(range(25)) | {45}
    elif resource_id == 203:
        # Items 25..29 are command 5: icon, icon control, label, price, button.
        keep = set(range(source_counts[resource_id])) - set(range(25, 30))
    else:
        # The foundation keeps only background + Cancel.  The public
        # selected-villager projection restores every individual Villager
        # Upgrades row -- Grant Youth (0), Grant Full Mastery (1), Grant
        # Running (2), and Set Age to 18 (3) -- so all four are visible.  The
        # payload's per-row eligibility bits still gate each Buy/disabled
        # state, and the button ordinals already match the detail dispatch
        # (1000->Youth, 1001->Mastery, 1002->Running, 1003->Age 18).
        keep = {0, 20}
        if include_individual_full_mastery:
            keep.update(range(1, 20))
    first = spans[0][0]
    end = spans[-1][1]
    changed = bytearray(blob[:first])
    for index in sorted(keep):
        start, stop = spans[index]
        changed.extend(blob[start:stop])
    changed.extend(blob[end:])
    if resource_id == 202 and include_individual_full_mastery:
        # The public projection keeps all four base rows (21 items) and then
        # inserts the fifth Change Appearance row (-> 26 items).
        struct.pack_into("<H", changed, 16, 21)
        changed = bytearray(_insert_change_appearance_row(bytes(changed)))
    target_counts = (
        PUBLIC_TARGET_COUNTS if include_individual_full_mastery else TARGET_COUNTS
    )
    struct.pack_into("<H", changed, 16, target_counts[resource_id])
    # A fresh structural walk is the acceptance check.
    dialog_item_spans(
        changed,
        expected_count=target_counts[resource_id],
    )
    return bytes(changed)


def build_resource_only_companion(
    base: bytes, *, include_individual_full_mastery: bool = True
) -> bytes:
    if len(base) != SOURCE_SIZE or sha(base) != SOURCE_SHA256:
        raise RuntimeError("VV3 safe-upgrade companion base fingerprint mismatch")
    raw_offset, raw_size, section_rva, _ = _resource_section(base)
    leaves = list(resource_leaves(base))
    targets: dict[int, bytes] = {}
    for index, (path, _, _, _, blob) in enumerate(leaves):
        if path[0] == 5 and path[1] in TARGET_COUNTS and path[2] == 1033:
            if path[1] in targets:
                raise RuntimeError("VV3 safe-upgrade target dialog is not unique")
            targets[path[1]] = _filter_dialog(
                blob,
                path[1],
                include_individual_full_mastery=include_individual_full_mastery,
            )
            leaves[index] = (path, leaves[index][1], leaves[index][2], leaves[index][3], targets[path[1]])
    if set(targets) != set(TARGET_COUNTS):
        raise RuntimeError("VV3 safe-upgrade target dialog set is incomplete")

    original_leaves = list(resource_leaves(base))
    groups: dict[tuple[int, int], list[int]] = {}
    for index, leaf in enumerate(original_leaves):
        groups.setdefault((leaf[2], leaf[3]), []).append(index)
    output = bytearray()
    cursor = raw_offset
    updated: dict[int, tuple[int, int]] = {}
    for data_raw, size in sorted(groups):
        output.extend(base[cursor:data_raw])
        new_raw = raw_offset + len(output)
        indices = groups[(data_raw, size)]
        replacement = leaves[indices[0]][4]
        if any(leaves[index][4] != replacement for index in indices):
            raise RuntimeError("VV3 safe-upgrade shared resource leaf diverged")
        output.extend(replacement)
        for index in indices:
            updated[original_leaves[index][1]] = (new_raw, len(replacement))
        cursor = data_raw + size
    output.extend(base[cursor : raw_offset + raw_size])
    if len(output) > raw_size:
        raise RuntimeError("VV3 safe-upgrade .rsrc repack exceeds its raw section")
    output.extend(b"\0" * (raw_size - len(output)))
    for entry, (new_raw, size) in updated.items():
        struct.pack_into("<II", output, entry, section_rva + new_raw - raw_offset, size)
    result = bytearray(base)
    result[raw_offset : raw_offset + raw_size] = output
    if include_individual_full_mastery:
        # Public projection carries a fifth Villager Upgrades row, so bump the
        # villager row_count immediate (mov ebx, 4 -> 5) in the companion code.
        if base[VILLAGER_ROW_COUNT_OFFSET] != 0x04:
            raise RuntimeError(
                "VV3 safe-upgrade villager row_count immediate is not 0x04"
            )
        result[VILLAGER_ROW_COUNT_OFFSET] = 0x05
        expected_prefix = bytearray(base[:raw_offset])
        expected_prefix[VILLAGER_ROW_COUNT_OFFSET] = 0x05
        transformed = bytes(result)
        if (
            transformed[:raw_offset] != bytes(expected_prefix)
            or transformed[raw_offset + raw_size :] != base[raw_offset + raw_size :]
        ):
            raise RuntimeError(
                "VV3 safe-upgrade public transform changed unexpected non-resource bytes"
            )
        return transformed
    transformed = bytes(result)
    if transformed[:raw_offset] != base[:raw_offset] or transformed[raw_offset + raw_size :] != base[raw_offset + raw_size :]:
        raise RuntimeError("VV3 safe-upgrade transform changed non-resource bytes")
    return transformed


def main() -> None:
    size, digest, exports = synchronize()
    print(f"{OUTPUT.relative_to(ROOT)} {size} {digest}")
    print("mask exports: " + ", ".join(sorted(REQUIRED_MASK_EXPORTS)))
    print(f"named exports: {len(exports)}")


if __name__ == "__main__":
    main()
