"""Test helper: what the patched game blits for the Golden Mushroom, from what the stock draw blits.

"VVFP Golden Mushroom.dll" (native/vvfp_golden_mushroom/vvfp_golden_mushroom.c) changes one thing in a
draw call: when the call draws the golden frame of its sheet (A New Home: frame 15 of the 15 x 1
carrying.png; the others: frame 50 of the collectables sheet), it draws frame 0 of golden_mushroom.png
instead, moved by the companion's (DX, DY), with the call's own scale and alpha.  So the patched game's
blits are the stock game's blits with those calls swapped -- which is what this helper builds, for the
renderers' golden plans to be compared with.
"""
from __future__ import annotations

import re
from pathlib import Path

import vv_picture_image as pi
import vv_pictures_carried as carried

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "native" / "vvfp_golden_mushroom" / "vvfp_golden_mushroom.c"


def swapped(stock: list, game: int, is_golden) -> list[tuple]:
    """The keys of `stock` (pi.Draw list, the stock game's own blits) with every golden-frame draw swapped."""
    dx, dy = carried.GOLDEN_SHIFT[game]
    w, h = carried.GOLDEN_SIZE
    out = []
    for d in stock:
        if is_golden(d):
            out.append(pi.Draw(carried.GOLDEN_FILE, (0, 0, w, h), d.x + dx, d.y + dy, d.scale, d.alpha).key())
        else:
            out.append(d.key())
    return out


def source_shifts() -> dict[int, tuple[int, int]] | None:
    """The companion's own offsets, read from its source: {game: (DX, DY)}; None without the source."""
    try:
        text = SOURCE.read_text(encoding="utf-8")
    except OSError:
        return None
    out = {}
    dx = re.search(r"#define VV1_DX\s+(-?\d+)", text)
    dy = re.search(r"#define VV1_DY\s+(-?\d+)", text)
    if dx and dy:
        out[1] = (int(dx.group(1)), int(dy.group(1)))
    for m in re.finditer(r"LATER_STUB\(vv(\d), 0x[0-9A-Fa-f]+, 0x[0-9A-Fa-f]+u, (-?\d+), (-?\d+)\)", text):
        out[int(m.group(1))] = (int(m.group(2)), int(m.group(3)))
    return out
