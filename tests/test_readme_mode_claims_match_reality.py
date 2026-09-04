"""The README's population-mode claims must match what the patcher accepts.

The README told users to use `collection_progression` or `immediate_fixed` for
the Origins-style routes "because their certified append layouts do not include
`stock` for VV3-VV5".  That was true when written and had since stopped being
true: all five games render those routes in `stock` mode.  A reader following
that sentence would have avoided a mode that works.

Documentation claims of the form "X is not supported" rot silently, because
nothing fails when the support arrives.  This test makes the README's claim an
executable one: if a mode ever genuinely stops working, this fails and the
sentence has to be rewritten deliberately rather than left misleading.
"""

import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from src.vv_fun_patcher import (  # noqa: E402
    load_builds,
    load_fun_patches,
    render_patched_bytes,
)

MODES = ("stock", "collection_progression", "immediate_fixed")

STOCK_EXES = {
    "vv1": "inputs/vv1-stock-copy/Virtual Villagers - A New Home.exe",
    "vv2": "inputs/vv2-stock-copy/Virtual Villagers - The Lost Children.exe",
    "vv3": "inputs/vv3-stock-copy/Virtual Villagers - The Secret City.exe",
    "vv4": "inputs/vv4-stock-copy/Virtual Villagers - The Tree of Life.exe",
    "vv5": "inputs/vv5-stock-copy/Virtual Villagers - New Believers.exe",
}


def _available(game):
    path = ROOT / STOCK_EXES[game]
    return path if path.exists() else None


class ReadmeModeClaimsTests(unittest.TestCase):
    def test_origins_routes_render_in_every_mode_for_every_game(self):
        builds = {b.id: b for b in load_builds()}
        catalog = {p.id for p in load_fun_patches()}
        checked = 0
        for game in STOCK_EXES:
            path = _available(game)
            if path is None:
                continue
            patch_id = f"{game}_origins_village_wide_upgrades"
            if patch_id not in catalog:
                continue
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    rendered, _ = render_patched_bytes(
                        path, builds[game], mode, [patch_id]
                    )
                    self.assertTrue(rendered)
                    checked += 1
        self.assertGreater(
            checked,
            0,
            "no stock executables available; this test proved nothing",
        )

    def test_readme_does_not_claim_stock_is_unsupported(self):
        """The specific stale sentence, so it cannot come back unnoticed."""
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn(
            "certified append layouts do not include `stock` for VV3-VV5",
            readme,
            "README again claims stock mode is unsupported for VV3-VV5; "
            "the renders in this file show otherwise",
        )


if __name__ == "__main__":
    unittest.main()
