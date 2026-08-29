"""Build VV4's Details mask atlas from VV5's approved atlas recipe.

VV4 FUN_0045F550 and VV5 FUN_00466C40 use the same three-state Details
portrait compositor. The VV4 patch therefore ships the exact VV5 Details
atlas geometry and frames under VV4's loader name instead of repacking an
external image or enlarging the eight-facing village atlas.
"""
from __future__ import annotations

from pathlib import Path

from build_vv5_bighead_mask_atlas import build as build_vv5_bighead_atlas


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "vv4_masks" / "vvfp_bighead_mask_atlas.png"


def main() -> None:
    image = build_vv5_bighead_atlas(OUT)
    print(f"wrote {OUT} {image.size} (byte-identical VV5 Details atlas recipe)")


if __name__ == "__main__":
    main()
