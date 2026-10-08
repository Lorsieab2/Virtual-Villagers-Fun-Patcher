"""Write data/tree_shapes.json: the Family Tree Maker's traced portrait shapes (Flower, Butterfly,
Clover, Spade, Leaf), each fitted to a 1 x 1 box, so the window never traces them while the player
waits (Codex, #575).  Re-run after changing vv_family_tree._drawn_outlines;
tests/test_tree_new_shapes.py checks the file still matches the tracing."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_family_tree as ft  # noqa: E402


def main() -> None:
    shapes = {kind: [[round(x, 5), round(y, 5)] for x, y in points]
              for kind, points in ft.traced_unit_outlines().items()}
    ft.TREE_SHAPES_FILE.write_text(json.dumps(shapes, separators=(",", ":")) + "\n", encoding="utf-8")
    print("wrote", ft.TREE_SHAPES_FILE.relative_to(ROOT), {k: len(v) for k, v in shapes.items()})


if __name__ == "__main__":
    main()
