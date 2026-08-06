"""Production VV3 individual Full Mastery PE append/install helpers.

This module owns only the disabled/catalog-hidden ``.vv3im`` candidate.  It
operates on the already-composed Fullscreen Collection/Immediate parents and
derives the final section/header/checksum bytes from their exact 0xCE000 PE
layout.  Unknown parents and malformed candidate metadata fail closed.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import struct
import uuid
from pathlib import Path

from vv_fun_patcher import PatcherError, _pe_checksum_layout, pe_checksum, _validate_vv3_individual_full_mastery_candidate

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_vv3_individual_mastery_candidate.py"
HOOK_OFFSET = 0xA38C3
HOOK_BEFORE = bytes.fromhex("E938C02300")
HOOK_AFTER = bytes.fromhex("E938E72300")
APPEND_OFFSET = 0xCE000
APPEND_SIZE = 0x1000
SECTION_HEADER_OFFSET = 0x340
PARENT_HASHES = {
    "collection_progression": "8DD1CE07C885DDA3DD038D0B2F5C4F019D8C5BAC5DCA29F9799CE0C7909D2CEA",
    "immediate_fixed": "78758FD0003842AEFAC092A47874329C9C103F9AD46483E6ECA71291EFD3E382",
}
OUTPUT_HASHES = {
    "collection_progression": "912C6D70518AE55CC7396E2AB3317356E814A4E7F4975150C3BD0263A4ECA174",
    "immediate_fixed": "C18FEF7F5111B8A8B33940F73F2549E882C6BECDCF3FF4F8904AFC01F0204B4E",
}
COMPANION_DLL_SHA256 = "9F866CB6F92C745CD2AA7009AEC4EB70FA5521EFF0C8F7BABE2058BB4D2F8533"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def _page() -> bytes:
    spec = importlib.util.spec_from_file_location("vv3_individual_mastery_builder", BUILDER)
    if spec is None or spec.loader is None:
        raise PatcherError("VV3 individual Full Mastery builder is unavailable.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    page, details = module.build_page()
    expected = str(details.get("page_sha256", "")).upper()
    if len(page) != APPEND_SIZE or _sha(page) != expected:
        raise PatcherError("VV3 individual Full Mastery page hash/size mismatch.")
    return bytes(page)


def _header_patches() -> list[tuple[int, bytes, bytes]]:
    return [
        (0x10E, bytes.fromhex("0800"), bytes.fromhex("0900")),
        (0x158, bytes.fromhex("00202E00"), bytes.fromhex("00302E00")),
        (
            SECTION_HEADER_OFFSET,
            bytes(40),
            bytes.fromhex("2E767633696D00000010000000202E000010000000E00C0000000000000000000000000020000060"),
        ),
    ]


def render_parent(source: bytes, mode: str) -> bytes:
    _validate_vv3_individual_full_mastery_candidate()
    if mode not in PARENT_HASHES:
        raise PatcherError("VV3 individual Full Mastery supports stock modes only.")
    if len(source) != APPEND_OFFSET or _sha(source) != PARENT_HASHES[mode]:
        raise PatcherError("VV3 individual Full Mastery parent fingerprint mismatch.")
    if source[HOOK_OFFSET : HOOK_OFFSET + len(HOOK_BEFORE)] != HOOK_BEFORE:
        raise PatcherError("VV3 individual Full Mastery composed hook preimage mismatch.")
    page = _page()
    work = bytearray(source)
    for offset, before, after in _header_patches():
        if bytes(work[offset : offset + len(before)]) != before:
            raise PatcherError(f"VV3 individual Full Mastery header guard failed at 0x{offset:X}.")
        work[offset : offset + len(after)] = after
    work[HOOK_OFFSET : HOOK_OFFSET + len(HOOK_AFTER)] = HOOK_AFTER
    work.extend(page)
    checksum_offset, _ = _pe_checksum_layout(work)
    struct.pack_into("<I", work, checksum_offset, 0)
    struct.pack_into("<I", work, checksum_offset, pe_checksum(work))
    result = bytes(work)
    if _sha(result) != OUTPUT_HASHES[mode]:
        raise PatcherError("VV3 individual Full Mastery emitted output hash mismatch.")
    return result


def remove_candidate(candidate: bytes, mode: str) -> bytes:
    _validate_vv3_individual_full_mastery_candidate()
    if mode not in PARENT_HASHES:
        raise PatcherError("VV3 individual Full Mastery supports stock modes only.")
    if len(candidate) != APPEND_OFFSET + APPEND_SIZE:
        raise PatcherError("VV3 individual Full Mastery candidate size mismatch.")
    page = _page()
    if bytes(candidate[APPEND_OFFSET:]) != page:
        raise PatcherError("VV3 individual Full Mastery owned page guard mismatch.")
    work = bytearray(candidate[:APPEND_OFFSET])
    if bytes(work[HOOK_OFFSET : HOOK_OFFSET + len(HOOK_AFTER)]) != HOOK_AFTER:
        raise PatcherError("VV3 individual Full Mastery removal hook guard mismatch.")
    work[HOOK_OFFSET : HOOK_OFFSET + len(HOOK_BEFORE)] = HOOK_BEFORE
    for offset, before, after in reversed(_header_patches()):
        if bytes(work[offset : offset + len(after)]) != after:
            raise PatcherError(f"VV3 individual Full Mastery removal header guard failed at 0x{offset:X}.")
        work[offset : offset + len(before)] = before
    checksum_offset, _ = _pe_checksum_layout(work)
    struct.pack_into("<I", work, checksum_offset, 0)
    struct.pack_into("<I", work, checksum_offset, pe_checksum(work))
    if _sha(work) != PARENT_HASHES[mode]:
        raise PatcherError("VV3 individual Full Mastery removal did not restore the parent.")
    return bytes(work)


def install_atomic(source: Path, destination: Path, mode: str, *, companion_source: Path | None = None, companion_destination: Path | None = None) -> None:
    """Install EXE and optional unchanged certified companion atomically."""
    source_bytes = source.read_bytes()
    candidate = render_parent(source_bytes, mode)
    if (companion_source is None) != (companion_destination is None):
        raise PatcherError("VV3 individual Full Mastery companion arguments must be paired.")
    companion_bytes = None
    if companion_source is not None:
        companion_bytes = companion_source.read_bytes()
        if len(companion_bytes) != 298496 or _sha(companion_bytes) != COMPANION_DLL_SHA256:
            raise PatcherError("VV3 individual Full Mastery companion hash mismatch.")
    destinations = [destination] + ([companion_destination] if companion_destination is not None else [])
    if any(os.path.lexists(path) for path in destinations):
        raise PatcherError("VV3 individual Full Mastery destination already exists.")
    stage = destination.parent / f".{destination.name}.vv3im-{uuid.uuid4().hex}.stage"
    if os.path.lexists(stage) or (companion_destination is not None and stage.parent != companion_destination.parent):
        raise PatcherError("VV3 individual Full Mastery staging collision.")
    try:
        stage.write_bytes(candidate)
        if stage.read_bytes() != candidate:
            raise PatcherError("VV3 individual Full Mastery staged verification failed.")
        companion_stage = None
        if companion_destination is not None and companion_bytes is not None:
            companion_stage = stage.with_name(stage.name + ".dll")
            companion_stage.write_bytes(companion_bytes)
            if companion_stage.read_bytes() != companion_bytes:
                raise PatcherError("VV3 individual Full Mastery staged companion verification failed.")
        os.replace(stage, destination)
        if companion_destination is not None and companion_stage is not None:
            os.replace(companion_stage, companion_destination)
        if not destination.is_file() or destination.read_bytes() != candidate or (companion_destination is not None and (not companion_destination.is_file() or _sha(companion_destination.read_bytes()) != COMPANION_DLL_SHA256)):
            raise PatcherError("VV3 individual Full Mastery publication verification failed.")
    except Exception:
        if stage.is_file():
            stage.unlink()
        if 'companion_stage' in locals() and companion_stage is not None and companion_stage.is_file():
            companion_stage.unlink()
        if destination.is_file() and destination.read_bytes() == candidate:
            destination.unlink()
        if companion_destination is not None and companion_destination.is_file() and _sha(companion_destination.read_bytes()) == COMPANION_DLL_SHA256:
            companion_destination.unlink()
        raise


def remove_atomic(destination: Path, mode: str) -> None:
    """Replace a published candidate with its exact parent, fail-closed."""
    candidate = destination.read_bytes()
    parent = remove_candidate(candidate, mode)
    stage = destination.with_name(f".{destination.name}.vv3im-remove-{uuid.uuid4().hex}.stage")
    backup = destination.with_name(f".{destination.name}.vv3im-remove-{uuid.uuid4().hex}.backup")
    if os.path.lexists(stage) or os.path.lexists(backup):
        raise PatcherError("VV3 individual Full Mastery removal staging collision.")
    try:
        stage.write_bytes(parent)
        backup.write_bytes(candidate)
        if stage.read_bytes() != parent or backup.read_bytes() != candidate:
            raise PatcherError("VV3 individual Full Mastery removal staging verification failed.")
        os.replace(stage, destination)
        if destination.read_bytes() != parent:
            raise PatcherError("VV3 individual Full Mastery removal postverify failed.")
        backup.unlink()
    except Exception:
        if stage.is_file():
            stage.unlink()
        if backup.is_file():
            try:
                os.replace(backup, destination)
            except OSError:
                pass
        raise
