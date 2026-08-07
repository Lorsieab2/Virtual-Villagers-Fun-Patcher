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
    patches = game.get("patches", ())
    if game.get("patch_count") != len(patches):
        errors.append("vv3 patch_count does not match the manifest")
    by_offset = _patch_map(game)
    for offset, expected in {**VV3_STOCK_SAVE_PATCHES, **VV3_RECORD_BOUND_PATCHES}.items():
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
    return tuple(errors)


def publication_ready() -> bool:
    """Return the conservative publication decision for this static contract."""

    return not VV3_PUBLICATION_BLOCKERS and VV3_STORED_INDEX_AUDIT["status"] == "complete"
