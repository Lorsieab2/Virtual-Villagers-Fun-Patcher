"""Checkout-independent hashing for repository-owned UTF-8 source text."""

from __future__ import annotations

import hashlib
from pathlib import Path


CANONICAL_SOURCE_HASH_RULE = "vvfp.source-text.v1: UTF-8 with optional BOM removed; CRLF and CR normalized to LF; SHA-256 uppercase"


def canonical_source_bytes(data: bytes) -> bytes:
    text = data.decode("utf-8-sig")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def canonical_source_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_source_bytes(path.read_bytes())).hexdigest().upper()
