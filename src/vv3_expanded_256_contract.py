"""Evidence-bound static contract for the VV3 Expanded-256 candidate.

This module models only the byte layout and reviewed manifest facts.  It is
not a game loader and does not claim runtime or player validation.  The
publication gate must remain closed while the unresolved blockers below are
present.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


VV3_SOURCE_SHA256 = (
    "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503"
)
VV3_PROTOTYPE_SHA256 = (
    "6EE3361A7AC35F441763647C1E2FC9EC49569DE5EF372BDB41D243D03002D601"
)
VV3_PATCH_COUNT = 1263


@dataclass(frozen=True)
class VV3Expanded256Layout:
    """Reviewed VV3 geometry, expressed without executable-side assumptions."""

    stock_record_count: int = 150
    logical_record_count: int = 256
    padding_record_count: int = 4
    compact_record_stride: int = 284
    live_record_stride: int = 0x1F8C
    stock_save_size: int = 0x12F1C
    inserted_record_count: int = 106
    gap_offset: int = 0x11ECC
    tail_dword_count: int = 0x414
    expanded_post_load_dword_count: int = 0x692D
    loader_zero_dword_count: int = 0x1D66

    @property
    def physical_record_count(self) -> int:
        return self.logical_record_count + self.padding_record_count

    @property
    def inserted_bytes(self) -> int:
        return self.inserted_record_count * self.compact_record_stride

    @property
    def expanded_save_size(self) -> int:
        return self.stock_save_size + self.inserted_bytes

    @property
    def tail_bytes(self) -> int:
        return self.tail_dword_count * 4


VV3_LAYOUT = VV3Expanded256Layout()


VV3_STOCK_SAVE_PATCHES: Mapping[int, Mapping[str, str]] = {
    0x28949: {"before": "E852AAFDFF", "after": "E8632A0500"},
    0x28961: {"before": "B9C74B0000", "after": "B92D690000"},
    0x7B3B1: {
        "before": "00" * 102,
        "after": (
            "5589E551FF7510FF750CFF75088B4DFCE8DA7FF8FF84C07547"
            "FF7510681C2F0100FF75088B4DFCE8C37FF8FF84C0743056578B"
            "750881C6182F01008DBE98750000B914040000FDF3A5FC8B7D08"
            "81C7CC1E010031C0B9661D0000F3AB5F5EB00189EC5DC20C00"
        ),
    },
}


VV3_RECORD_BOUND_PATCHES: Mapping[int, Mapping[str, str]] = {
    0x60D46: {"before": "95000000", "after": "FF000000"},
    0x60D4C: {"before": "706B1200", "after": "687B1F00"},
    0x5F975: {"before": "746B1200", "after": "6C7B1F00"},
    0x5FA46: {"before": "905C1200", "after": "807B1F00"},
    0x35A5A: {"before": "96000000", "after": "00010000"},
    0x5EE69: {"before": "96000000", "after": "00010000"},
}


VV3_PHYSICAL_POOL_PATCHES: Mapping[int, Mapping[str, str]] = {
    # 0x2FC340 - 0x223518 == (260 - 150) * 0x1F8C.
    0x258: {"before": "18352200", "after": "40C32F00"},
}


VV3_REVIEWED_PURPOSE_COUNTS: Mapping[str, int] = {
    "expand candidate-array stack frame": 12,
    "move expanded candidate-array stack reference": 44,
    "restore expanded candidate-array stack frame": 20,
    "expand saved-state tail offset": 416,
    "relocate absolute .data tail reference": 638,
    "relocate manager-relative tail reference": 32,
    "relocate decoded absolute .data tail reference": 18,
    "expand record loop bound": 57,
    "move absolute .shr reference": 4,
    "expand .data virtual size": 1,
    "move .shr RVA": 1,
    "move .rsrc RVA": 1,
    "expand SizeOfImage": 1,
    "move resource directory RVA": 1,
    "move resource data RVA": 8,
}


VV3_BOUND_OR_INDEX_PURPOSES = frozenset(
    {
        "expand record loop bound",
        "expand the VV3 main-world villager hit-test reverse scan through record 255",
        "expand the serialized villager-index validator from 150 to 256 records",
        "expand the active-record lookup validator from 150 to 256 records",
    }
)


VV3_REVERSE_ENDPOINT_PURPOSES = frozenset(
    {
        "move the VV3 main-world villager hit-test endpoint from record 149 to record 255",
        "move the VV3 mating spatial scan endpoint from record 149 to record 255",
        "move the VV3 nearby-villager helper endpoint from record 149 to record 255",
    }
)


VV3_CANDIDATE_ARRAY_PURPOSES = frozenset(
    {
        "expand candidate-array stack frame",
        "move expanded candidate-array stack reference",
        "restore expanded candidate-array stack frame",
    }
)


# No VV3 native sentinel or complete stored-index width audit is certified.
# Keeping this explicit prevents a byte-sized 0xFF from being treated as both
# record 255 and a no-record marker by a future publication change.
VV3_STORED_INDEX_AUDIT: Mapping[str, Any] = {
    "status": "incomplete",
    "sentinel": "unresolved",
    "required_paths": (
        "selection",
        "sorted_roster",
        "detail_navigation",
        "planner_action_queue",
        "pairing_pregnancy",
        "birth_death",
        "skeleton_memorial",
        "event_puzzle",
        "statistics",
        "callbacks",
    ),
}


VV3_PUBLICATION_BLOCKERS = (
    "runtime load hang lacks an exact faulting instruction and call-state capture",
    "stock-import to expanded-save to reload and offline-catch-up round trip is absent",
    "stored-index width and native sentinel audit is incomplete",
    "runtime/player validation is not authorized or present",
)


def _bytes(value: bytes | bytearray | memoryview) -> bytes:
    return bytes(value)


def migrate_stock_save(stock_save: bytes | bytearray | memoryview) -> bytes:
    """Model the reviewed VV3 stock-save insertion without touching disk."""

    source = _bytes(stock_save)
    layout = VV3_LAYOUT
    if len(source) != layout.stock_save_size:
        raise ValueError(
            f"VV3 stock save must be exactly {layout.stock_save_size:#x} bytes; "
            f"got {len(source):#x}"
        )
    prefix = source[: layout.gap_offset]
    tail = source[layout.gap_offset :]
    if len(tail) != layout.tail_bytes:
        raise ValueError("VV3 stock-save tail is not the reviewed aligned length")
    return prefix + (b"\0" * layout.inserted_bytes) + tail


def accept_save_layout(save: bytes | bytearray | memoryview) -> bytes:
    """Model exact-size loader acceptance and stock-to-expanded conversion."""

    payload = _bytes(save)
    if len(payload) == VV3_LAYOUT.expanded_save_size:
        return payload
    if len(payload) == VV3_LAYOUT.stock_save_size:
        return migrate_stock_save(payload)
    raise ValueError(
        "VV3 loader accepts only the exact expanded or exact stock save size; "
        f"got {len(payload):#x} bytes"
    )


def build_physical_record_pool(records: Sequence[bytes]) -> bytes:
    """Build a logical-256 plus zero-padding pool for boundary tests."""

    layout = VV3_LAYOUT
    if len(records) != layout.logical_record_count:
        raise ValueError("VV3 pool construction requires exactly 256 logical records")
    normalized: list[bytes] = []
    for index, record in enumerate(records):
        payload = _bytes(record)
        if len(payload) != layout.live_record_stride:
            raise ValueError(
                f"record {index} must be exactly {layout.live_record_stride:#x} bytes"
            )
        normalized.append(payload)
    return b"".join(normalized) + (
        b"\0" * layout.padding_record_count * layout.live_record_stride
    )


def record_from_pool(pool: bytes | bytearray | memoryview, index: int) -> bytes:
    """Return only a logical record; padding indices are never exposed."""

    if not isinstance(index, int) or not 0 <= index < VV3_LAYOUT.logical_record_count:
        raise IndexError(f"VV3 logical record index is outside 0..255: {index!r}")
    payload = _bytes(pool)
    expected = VV3_LAYOUT.physical_record_count * VV3_LAYOUT.live_record_stride
    if len(payload) != expected:
        raise ValueError(f"VV3 physical pool must be exactly {expected:#x} bytes")
    start = index * VV3_LAYOUT.live_record_stride
    end = start + VV3_LAYOUT.live_record_stride
    return payload[start:end]


def classify_index(value: int, *, sentinel: int | None = None) -> str:
    """Classify an index only when its sentinel is supplied by native evidence."""

    if not isinstance(value, int):
        return "invalid"
    if sentinel is not None and value == sentinel:
        return "sentinel"
    if 0 <= value < VV3_LAYOUT.logical_record_count:
        return "record"
    return "invalid"


def _patch_map(game: Mapping[str, Any]) -> dict[int, list[Mapping[str, Any]]]:
    result: dict[int, list[Mapping[str, Any]]] = {}
    for patch in game.get("patches", ()):
        try:
            offset = int(str(patch["offset"]), 0)
        except (KeyError, TypeError, ValueError):
            continue
        result.setdefault(offset, []).append(patch)
    return result


def validate_vv3_manifest(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    """Validate only the reviewed VV3 static facts used by this contract."""

    errors: list[str] = []
    games = manifest.get("games")
    game = games.get("vv3") if isinstance(games, Mapping) else None
    if not isinstance(game, Mapping):
        return ("expanded manifest has no vv3 game record",)
    if game.get("source_sha256") != VV3_SOURCE_SHA256:
        errors.append("vv3 source hash is not the exact reviewed build")
    if game.get("prototype_sha256") != VV3_PROTOTYPE_SHA256:
        errors.append("vv3 prototype hash is not the exact reviewed source")
    patches = game.get("patches", ())
    if not isinstance(patches, Sequence) or isinstance(patches, (str, bytes)):
        return (*errors, "vv3 patches are not a sequence")
    if game.get("patch_count") != VV3_PATCH_COUNT or len(patches) != VV3_PATCH_COUNT:
        errors.append("vv3 patch_count is not the exact reviewed count")
    by_offset = _patch_map(game)
    if len(by_offset) != len(patches):
        errors.append("vv3 manifest offsets are malformed or not unique")
    for offset, expected in {
        **VV3_STOCK_SAVE_PATCHES,
        **VV3_RECORD_BOUND_PATCHES,
        **VV3_PHYSICAL_POOL_PATCHES,
    }.items():
        matches = by_offset.get(offset, ())
        if len(matches) != 1:
            errors.append(f"vv3 manifest offset {offset:#x} is not unique")
            continue
        actual = matches[0]
        for key in ("before", "after"):
            if str(actual.get(key, "")).upper() != expected[key].upper():
                errors.append(f"vv3 manifest offset {offset:#x} has wrong {key} bytes")
    fallback = by_offset.get(0x7B3B1, ())
    if fallback and len(str(fallback[0].get("after", ""))) // 2 != 102:
        errors.append("vv3 loader fallback body is not exactly 102 bytes")
    if VV3_LAYOUT.loader_zero_dword_count * 4 != VV3_LAYOUT.inserted_bytes:
        errors.append("vv3 loader zero count does not match the inserted save gap")
    if VV3_LAYOUT.tail_dword_count * 4 != VV3_LAYOUT.tail_bytes:
        errors.append("vv3 loader tail count is not aligned to the reviewed tail")
    physical_pool = by_offset.get(0x258, ())
    if len(physical_pool) == 1:
        try:
            before_size = int.from_bytes(
                bytes.fromhex(str(physical_pool[0]["before"])), "little"
            )
            after_size = int.from_bytes(
                bytes.fromhex(str(physical_pool[0]["after"])), "little"
            )
        except (KeyError, TypeError, ValueError):
            errors.append("vv3 physical pool size patch is malformed")
        else:
            expected_growth = (
                VV3_LAYOUT.physical_record_count - VV3_LAYOUT.stock_record_count
            ) * VV3_LAYOUT.live_record_stride
            if after_size - before_size != expected_growth:
                errors.append("vv3 physical pool does not reserve exactly 260 records")

    purposes = [
        patch.get("purpose") if isinstance(patch, Mapping) else None
        for patch in patches
    ]
    for purpose, expected_count in VV3_REVIEWED_PURPOSE_COUNTS.items():
        if purposes.count(purpose) != expected_count:
            errors.append(
                f"vv3 {purpose!r} count is not the reviewed {expected_count}"
            )
    if sum(purpose in VV3_BOUND_OR_INDEX_PURPOSES for purpose in purposes) != 60:
        errors.append("vv3 bound/index operand count is not the reviewed 60")
    if sum(purpose in VV3_REVERSE_ENDPOINT_PURPOSES for purpose in purposes) != 3:
        errors.append("vv3 reverse endpoint count is not the reviewed 3")

    candidate_rows = [
        patch
        for patch in patches
        if isinstance(patch, Mapping)
        and patch.get("purpose") in VV3_CANDIDATE_ARRAY_PURPOSES
    ]
    frame_positions = [
        index
        for index, patch in enumerate(candidate_rows)
        if patch.get("purpose") == "expand candidate-array stack frame"
    ]
    if len(frame_positions) == 12:
        for group_index, start in enumerate(frame_positions):
            end = (
                frame_positions[group_index + 1]
                if group_index + 1 < len(frame_positions)
                else len(candidate_rows)
            )
            group_purposes = [patch.get("purpose") for patch in candidate_rows[start:end]]
            if (
                group_purposes.count("expand candidate-array stack frame") != 1
                or "move expanded candidate-array stack reference" not in group_purposes
                or "restore expanded candidate-array stack frame" not in group_purposes
            ):
                errors.append(
                    f"vv3 candidate-array group {group_index + 1} is not atomic"
                )
    else:
        errors.append("vv3 candidate-array frame count is not the reviewed 12")
    return tuple(errors)


def publication_ready() -> bool:
    """Return the conservative publication decision for this static contract."""

    return not VV3_PUBLICATION_BLOCKERS and VV3_STORED_INDEX_AUDIT["status"] == "complete"
