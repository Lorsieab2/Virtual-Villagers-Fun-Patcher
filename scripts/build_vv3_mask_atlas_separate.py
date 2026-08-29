"""Retired VV3 dedicated-atlas entry point.

The active route embeds the tracked dedicated 520x725 RGBA atlas as RCDATA
5000. This compatibility entry point validates that canonical geometry and
intentionally performs no image writes, row assembly, or atlas replacement.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image


CANONICAL_SIZE = (520, 725)
CANONICAL = (
    Path(__file__).resolve().parents[1]
    / "assets"
    / "vv3_heathen_masks"
    / "heathen_masks.png"
)


def build() -> Path:
    """Validate and return the tracked atlas without writing any file."""
    if not CANONICAL.is_file():
        raise RuntimeError(f"canonical VV3 atlas is missing: {CANONICAL}")
    with Image.open(CANONICAL) as atlas:
        if atlas.size != CANONICAL_SIZE:
            raise RuntimeError(
                f"refusing to replace canonical VV3 atlas: expected 520x725, got "
                f"{atlas.size[0]}x{atlas.size[1]}"
            )
    print(f"canonical VV3 atlas validated: {CANONICAL} (520x725); no file written")
    return CANONICAL


if __name__ == "__main__":
    build()
