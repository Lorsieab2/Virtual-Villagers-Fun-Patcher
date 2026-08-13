"""Build per-candidate runtime freezes without cross-game regeneration drift."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


_FROZEN_FIELDS = (
    "patches",
    "patch_mode_overrides",
    "expanded_shr_relocations",
    "dependencies",
)


def _canonical_sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    ).hexdigest().upper()


def isolated_runtime_freeze(
    *,
    game_id: str,
    map_path: Path,
    data_root: Path,
    section: str = "runtime_freeze",
) -> dict[str, str]:
    """Freeze unrelated game records from the existing map.

    Candidate maps historically embedded all five Origins manifests.  That made
    a VV5 manifest correction rewrite certified VV3 maps even though VV3's own
    payload was unchanged.  The candidate being generated remains authoritative
    for its own record; unrelated records stay at their already-certified map
    values.  A missing/invalid map falls back to computing every record, which
    keeps first generation deterministic.
    """

    existing: dict[str, str] = {}
    try:
        value = json.loads(map_path.read_text(encoding="utf-8"))
        candidate = value.get(section, {})
        if isinstance(candidate, dict):
            existing = {
                str(key): str(hash_value)
                for key, hash_value in candidate.items()
                if isinstance(key, str) and isinstance(hash_value, str)
            }
    except (OSError, json.JSONDecodeError):
        existing = {}

    result: dict[str, str] = {}
    for game in range(1, 6):
        key = f"vv{game}_origins_feature.json"
        if game != int(game_id.removeprefix("vv")) and key in existing:
            result[key] = existing[key]
            continue
        manifest = json.loads((data_root / key).read_text(encoding="utf-8"))
        result[key] = _canonical_sha({field: manifest.get(field) for field in _FROZEN_FIELDS})
    return result
