"""Checkout-independent hashing for repository-owned UTF-8 source text."""

from __future__ import annotations

from pathlib import Path

from source_text_hash import canonical_source_text_bytes, source_text_sha256


CANONICAL_SOURCE_HASH_RULE = "vvfp.source-text.v1: UTF-8 with optional BOM removed; CRLF and CR normalized to LF; SHA-256 uppercase"


def canonical_source_bytes(data: bytes) -> bytes:
    return canonical_source_text_bytes(data)


def canonical_source_sha256(path: Path) -> str:
    return source_text_sha256(path)
