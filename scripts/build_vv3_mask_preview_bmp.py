"""Install the VV3 Change Appearance *mask* preview strip (mask_strip.bmp).

CROSS-GAME PARITY (owner, 2026-08-23): every game's Change Appearance picker must
show the SAME mask sprites, so the preview is pixel-identical in all five games.
The masks are the same VV5 art everywhere, so instead of each game deriving its own
strip from its own render atlas (which drifts by a pixel or two per game), we vendor
VV2's canonical strip and use it verbatim as VV3's IDB_MASK_STRIP (resource 3021).

Canonical source: VV2's `native/vv2_origins_icons/appearance/mask_preview.bmp`
(branch codex/vv2-heathen-mask, PR #97) -- a 240x65 BMP of six 40x65 cells:
cell 0 BLANK (the "(none)" text is drawn at runtime by the owner-draw handler,
not baked in), cells 1..5 = Blue / Orange / Red / Purple / Chief front frames,
each autocropped and fit into (40-4)x(65-4) (PAD=2, ~90% cell fill).

Vendored copy lives at assets/vv3_heathen_masks/mask_preview_canonical.bmp; this
script just copies it into the DLL resource tree so a rebuild embeds it.  The
in-game RENDERED mask still uses VV3's own heathen_masks.png atlas -- only the
dialog PREVIEW comes from this shared canonical strip.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "assets" / "vv3_heathen_masks" / "mask_preview_canonical.bmp"
RESOURCE = ROOT / "native" / "vv3_full_mastery_candidate" / "appearance" / "mask_strip.bmp"


def build() -> Path:
    if not CANONICAL.exists():
        raise SystemExit(
            f"canonical strip missing: {CANONICAL}\n"
            "Re-vendor it from VV2:\n"
            "  git show origin/codex/vv2-heathen-mask:"
            "native/vv2_origins_icons/appearance/mask_preview.bmp > "
            f'"{CANONICAL}"'
        )
    RESOURCE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(CANONICAL, RESOURCE)
    print(f"mask_strip.bmp <- VV2 canonical ({RESOURCE.stat().st_size} bytes)")
    return RESOURCE


def main() -> int:
    build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
