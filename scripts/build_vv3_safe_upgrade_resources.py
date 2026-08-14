"""Build the stock-only truthful VV3 Tech and Villager Upgrade resources.

The public VV3 Origins base loads the command-7 Full Mastery companion.  This
builder changes only its RT_DIALOG leaves:

* Origins-only Tech dialog 201 retains commands 0..4.
* Origins+village-FM Tech dialog 203 retains commands 0..4 plus 7.
* The foundation Villager Detail dialog 202 retains its background and Cancel
  control but no command rows.
* The public selected-villager projection retains the background, command 1,
  and Cancel while removing legacy commands 0, 2, and 3.

Every other resource leaf and every non-resource byte stays byte-identical.
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
SOURCE_SHA256 = "35FB96199E745C7D8054FF6A12851B9E09225E3E41D0CE04012604E74968C0D5"
SOURCE_SIZE = 298_496
TARGET_COUNTS = {201: 26, 202: 2, 203: 31}
PUBLIC_TARGET_COUNTS = {201: 46, 202: 21, 203: 31}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


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
    transformed = bytes(result)
    if transformed[:raw_offset] != base[:raw_offset] or transformed[raw_offset + raw_size :] != base[raw_offset + raw_size :]:
        raise RuntimeError("VV3 safe-upgrade transform changed non-resource bytes")
    return transformed


def main() -> None:
    source = SOURCE.read_bytes()
    foundation = build_resource_only_companion(
        source, include_individual_full_mastery=False
    )
    transformed = build_resource_only_companion(
        source, include_individual_full_mastery=True
    )
    FOUNDATION_OUTPUT.write_bytes(foundation)
    OUTPUT.write_bytes(transformed)
    print(
        f"{FOUNDATION_OUTPUT.relative_to(ROOT)} {len(foundation)} {sha(foundation)}"
    )
    print(f"{OUTPUT.relative_to(ROOT)} {len(transformed)} {sha(transformed)}")


if __name__ == "__main__":
    main()
