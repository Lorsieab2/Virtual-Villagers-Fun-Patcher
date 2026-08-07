#!/usr/bin/env python3
"""Portable vvfp.source-text.v1 hashing for authenticated tracked text."""
from __future__ import annotations

import hashlib
from pathlib import Path

TEXT_SUFFIXES = frozenset({".json", ".md", ".py", ".txt", ".csv", ".toml", ".yaml", ".yml"})


class SourceTextHashError(ValueError):
    pass


def canonical_source_text_bytes(payload: bytes) -> bytes:
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SourceTextHashError("authenticated source text is not valid UTF-8") from exc
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def source_text_sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(canonical_source_text_bytes(payload)).hexdigest().upper()


def source_text_sha256(path: Path) -> str:
    return source_text_sha256_bytes(path.read_bytes())


def raw_file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def authenticated_file_sha256(path: Path) -> str:
    return source_text_sha256(path) if path.suffix.lower() in TEXT_SUFFIXES else raw_file_sha256(path)
