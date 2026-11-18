"""The Tree of Life's frogs after The Frog Rescue: every place a frog may leap, traced from the game's own art.

After The Frog Rescue (puzzle 5) the world refresh 0x46D090 places 1 to 3 frog leaps on the river round the Tree of
Life's island (effect 0x1B, frogstrip1.png, leaps right; effect 0x1C, frogstrip2.png, leaps left).  Each leap is a
60 x 35 frame drawn with its top left corner at the point given (the effect draw 0x41D2B0, not centred): the frog
sits, leaps, lands and its ripple spreads inside that frame.  The base game placed them in two small fixed boxes on
the right of the river's bottom stretch.

This script finds every top left corner at which a whole leap -- every pixel of every one of its 12 frames -- lies
on the river's blue water, as the game draws it:

  * the water: the river picture the game draws for the stream's flow (the draw 0x43A07E: flow 1,
    stream_section-2-reduced.png at (0x278, 0x12C); flow 2, stream_section-2-strong.png at (0x27F, 0x127)), where
    the picture covers the map (alpha 128 or more) and is not the waterfall's white foam;
  * not under the tree: every growth of the Tree of Life (tree-state-00..05.png at (0x1FE, -0x5A), drawn over the
    river) is cut out, whatever its size;
  * only the river round the island: the water reached from the bottom stretch without crossing the waterfall (the
    stream above the waterfall is left out).

It writes native/vvfp_vv4_frogs/frog_water.h: for each flow and each frog, the rows of top left corners as
(y, x first, x last) runs, which "VVFP VV4 Frogs.dll" picks from with the game's own rand.  The art is read from
research/game-images (copied from the game's Images folder; never committed).  Run it again after a change and
rebuild the companion (scripts/build_vvfp_vv4_frogs.ps1).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "research" / "game-images" / "Virtual Villagers - The Tree of Life" / "Images"
HEADER = ROOT / "native" / "vvfp_vv4_frogs" / "frog_water.h"

WORLD = 2048
FRAME_W, FRAME_H, FRAMES = 60, 35, 12
# The river pictures and where the game draws them (0x43A08F..0x43A0C5), by the stream's flow (0x4396E0: 2 when
# its level is 0x4B or less, 1 up to 0x5F, else 0 and nothing is drawn -- and no frogs, the gate 0x46D3F1).
RIVER = {
    1: ("stream_section-2-reduced.png", (0x278, 0x12C)),
    2: ("stream_section-2-strong.png", (0x27F, 0x127)),
}
TREE = [f"tree-state-0{i}.png" for i in range(6)]
TREE_AT = (0x1FE, -0x5A)
FROGS = {0x1B: "frogstrip1.png", 0x1C: "frogstrip2.png"}
# The bottom stretch of the river (the column x 1000, y 560..700, below the island): the river round the island is
# the water connected to its first water pixel there, for either flow.
SEED = (1000, (560, 700))
WATER_ALPHA = 128
FOAM_RED = 170          # the waterfall's foam is near white; the river's blue has red well below this
TREE_ALPHA = 64         # the tree picture's own faint shading over the water does not hide it
# The waterfall's face and the stream above it (x from 1230, above y 540): not the river round the island.  The
# pool under the waterfall, by the ladder, stays.
UPSTREAM = (1230, 540)


def _paste_alpha(name: str, at: tuple[int, int]) -> np.ndarray:
    im = np.array(Image.open(IMAGES / name).convert("RGBA"))
    out = np.zeros((WORLD, WORLD, 4), dtype=np.uint8)
    x, y = at
    h, w = im.shape[:2]
    sy, sx = max(0, -y), max(0, -x)
    out[y + sy:y + h, x + sx:x + w] = im[sy:, sx:]
    return out


def water_mask(flow: int) -> np.ndarray:
    name, at = RIVER[flow]
    river = _paste_alpha(name, at)
    water = (river[..., 3] >= WATER_ALPHA) & (river[..., 0] < FOAM_RED)
    for tree in TREE:
        water &= _paste_alpha(tree, TREE_AT)[..., 3] < TREE_ALPHA
    x0, y1 = UPSTREAM
    water[:y1, x0:] = False
    labels, _ = ndimage.label(water)
    x, (y0, y1) = SEED
    column = labels[y0:y1, x]
    assert column.any(), "the bottom stretch is not water"
    return labels == column[column > 0][0]


def footprint(frog: int, frames=range(FRAMES)) -> np.ndarray:
    strip = np.array(Image.open(IMAGES / FROGS[frog]).convert("RGBA"))[..., 3]
    assert strip.shape == (FRAME_H, FRAME_W * 13), strip.shape
    mask = np.zeros((FRAME_H, FRAME_W), dtype=bool)
    for f in frames:
        mask |= strip[:, f * FRAME_W:(f + 1) * FRAME_W] > 0
    return mask


def corners(water: np.ndarray, foot: np.ndarray) -> np.ndarray:
    """valid[y, x]: the frame with its top left corner at (x, y) has every footprint pixel on water."""
    ok = np.ones_like(water)
    ys, xs = np.nonzero(foot)
    for dy, dx in zip(ys, xs):
        shifted = np.zeros_like(water)
        shifted[:WORLD - dy, :WORLD - dx] = water[dy:, dx:]
        ok &= shifted
    return ok


def runs(valid: np.ndarray) -> list[tuple[int, int, int]]:
    out = []
    for y in range(WORLD):
        row = valid[y]
        if not row.any():
            continue
        padded = np.concatenate(([False], row, [False]))
        edges = np.flatnonzero(padded[1:] != padded[:-1])
        for a, b in zip(edges[::2], edges[1::2]):
            out.append((y, int(a), int(b - 1)))
    return out


def tables() -> dict[tuple[int, int], list[tuple[int, int, int]]]:
    result = {}
    for flow in RIVER:
        water = water_mask(flow)
        for frog in FROGS:
            result[(flow, frog)] = runs(corners(water, footprint(frog)))
    return result


def render_header(result) -> str:
    lines = [
        "/* frog_water.h -- GENERATED by scripts/build_vv4_frog_water.py from the game's own art; do not edit.",
        "   Every top left corner at which a whole frog leap (all 12 frames) lies on the river's blue water, as rows",
        "   of runs {y, first x, last x}, for each flow of the stream (1 reduced, 2 strong) and each frog (0x1B leaps",
        "   right, 0x1C leaps left).  A flow and frog with no such corner has no set (the reduced stream is narrower",
        "   than a leap). */",
        "#ifndef VVFP_VV4_FROG_WATER_H",
        "#define VVFP_VV4_FROG_WATER_H",
        "",
        "typedef struct frog_run { short y, x0, x1; } frog_run;",
        "typedef struct frog_set { int flow, frog, first, count, total; } frog_set;",
        "",
    ]
    sets, all_runs = [], []
    for (flow, frog), rs in sorted(result.items()):
        total = sum(b - a + 1 for _, a, b in rs)
        lines.append(f"/* flow {flow}, frog 0x{frog:02X}: {len(rs)} runs, {total} corners */")
        if rs:
            sets.append((flow, frog, len(all_runs), len(rs), total))
            all_runs.extend(rs)
    lines.append("")
    lines.append(f"static const frog_run FROG_RUNS[{len(all_runs)}] = {{")
    for i in range(0, len(all_runs), 6):
        chunk = ", ".join(f"{{{y}, {a}, {b}}}" for y, a, b in all_runs[i:i + 6])
        lines.append(f"    {chunk},")
    lines.append("};")
    lines.append("")
    lines.append(f"static const frog_set FROG_SETS[{len(sets)}] = {{")
    for flow, frog, first, count, total in sets:
        lines.append(f"    {{{flow}, 0x{frog:02X}, {first}, {count}, {total}}},")
    lines.append("};")
    lines.append("")
    lines.append("#endif /* VVFP_VV4_FROG_WATER_H */")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail when the header is out of date")
    args = parser.parse_args(argv)
    text = render_header(tables())
    if args.check:
        if HEADER.read_text(encoding="utf-8") != text:
            print("native/vvfp_vv4_frogs/frog_water.h is out of date", file=sys.stderr)
            return 1
        return 0
    HEADER.parent.mkdir(parents=True, exist_ok=True)
    HEADER.write_text(text, encoding="utf-8", newline="\n")
    for line in text.splitlines():
        if line.startswith("/* flow"):
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
