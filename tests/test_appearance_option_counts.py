"""Every appearance chooser must offer all the options that game's ART holds.

The authoritative counts, per sex:

    game   heads   bodies
    VV1      20      20
    VV2      30      30
    VV3      30      30
    VV4      30      30
    VV5      30      30

CREATION RNG IS NOT THE CRITERION, and an earlier version of this file used it,
which is exactly how options stayed hidden. The engine only ever hands out a
SUBSET of the art it ships:

  * VV4 and VV5 roll `rand(29)` into the body field, so body 29 is never
    assigned at creation -- but the art holds thirty bodies and the chooser has
    to reach all of them.
  * VV1 rolls 19 for males and 20 for females, so male index 19 is never
    assigned -- but it exists.

Sizing a chooser to the RNG range therefore *looks* well-sourced and silently
drops the last option. Size it to the art.

The art is unambiguous. Head atlases are 65px rows: VV1's are 280x1300 (20 rows)
and the rest are 1950px tall (30). Body sheets are 640x650 grids of 64x65, i.e.
100 cells each, at 20 animation frames per body: VV1 ships four sheets per sex
(400 cells -> 20 bodies) and the rest ship six (600 -> 30).
"""
from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Optional: the read-only vanilla installs, used to re-derive the table below.
VANILLA = Path(
    os.environ.get(
        "VVFP_VANILLA_GAMES",
        r"C:\Users\Owner\Downloads\Read-Only Vanilla LDW Games",
    )
)
INSTALL_NAME = {
    "vv1": "Virtual Villagers - A New Home",
    "vv2": "Virtual Villagers - The Lost Children",
    "vv3": "Virtual Villagers - The Secret City",
    "vv4": "Virtual Villagers - The Tree of Life",
    "vv5": "Virtual Villagers - New Believers",
}

HEAD_ROW_PX = 65
BODY_CELLS_PER_SHEET = (640 // 64) * (650 // 65)   # 100
BODY_ANIMATION_FRAMES = 20

EXPECTED = {
    "vv1": {"heads": 20, "bodies": 20},
    "vv2": {"heads": 30, "bodies": 30},
    "vv3": {"heads": 30, "bodies": 30},
    "vv4": {"heads": 30, "bodies": 30},
    "vv5": {"heads": 30, "bodies": 30},
}

# Where each game declares its counts. VV1 is per sex; VV2 uses one macro for
# heads and bodies alike.
DECLARED = {
    "vv1": {
        "source": "native/vv1_origins_icons/vv1_origins_icons.c",
        "heads": ("VV_HEAD_COUNT_M", "VV_HEAD_COUNT_F"),
        "bodies": ("VV_BODY_COUNT_M", "VV_BODY_COUNT_F"),
    },
    "vv2": {
        "source": "native/vv2_origins_icons/vv2_origins_icons.c",
        "heads": ("VV2_APPEARANCE_COUNT",),
        "bodies": ("VV2_APPEARANCE_COUNT",),
    },
    "vv3": {
        "source": "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c",
        "heads": ("VV3_HEAD_COUNT",),
        "bodies": ("VV3_BODY_COUNT",),
    },
    "vv4": {
        "source": "native/vv4_origins_icons/vv4_origins_icons.c",
        "heads": ("VV_HEAD_COUNT",),
        "bodies": ("VV_BODY_COUNT",),
    },
    "vv5": {
        "source": "native/vv5_task9_origins/vv5_task9_origins.c",
        "heads": ("APPEARANCE_HEAD_COUNT",),
        "bodies": ("APPEARANCE_BODY_COUNT",),
    },
}


def _macro(source: str, name: str) -> int | None:
    text = (ROOT / source).read_text(encoding="utf-8")
    match = re.search(rf"^#define {re.escape(name)} (\d+)$", text, re.M)
    return int(match.group(1)) if match else None


class AppearanceOptionCountTests(unittest.TestCase):
    """Reads committed sources, so it runs in a clean checkout."""

    def test_every_chooser_offers_every_option_the_art_holds(self) -> None:
        for game, wanted in EXPECTED.items():
            spec = DECLARED[game]
            for kind in ("heads", "bodies"):
                for macro in spec[kind]:
                    with self.subTest(game=game, kind=kind, macro=macro):
                        value = _macro(spec["source"], macro)
                        self.assertIsNotNone(
                            value, f"{macro} not found in {spec['source']}"
                        )
                        self.assertEqual(
                            value, wanted[kind],
                            f"{game} offers {value} {kind}; the art holds "
                            f"{wanted[kind]}, so a player cannot reach every "
                            f"appearance the game ships",
                        )

    def test_both_sexes_get_the_same_number_of_options(self) -> None:
        """VV1 is the only per-sex declaration, and both sexes are 20."""
        spec = DECLARED["vv1"]
        for kind in ("heads", "bodies"):
            male, female = (_macro(spec["source"], m) for m in spec[kind])
            with self.subTest(kind=kind):
                self.assertEqual(
                    (male, female), (20, 20),
                    "VV1's male count was 19 because creation rolls rand(19) "
                    "for males; the art holds twenty and both sexes must be "
                    "able to reach all of them",
                )

    @unittest.skipUnless(VANILLA.is_dir(), "vanilla game installs are not present")
    def test_the_expected_table_is_re_derived_from_the_art(self) -> None:
        """Anti-vacuity: the table above is checked against the real files."""
        from PIL import Image

        checked = 0
        for game, wanted in EXPECTED.items():
            images = VANILLA / INSTALL_NAME[game] / "Images"
            if not images.is_dir():
                continue
            heads = sorted(images.glob("male_heads*.png"))
            bodies = sorted(images.glob("male_bodies*.png"))
            if not heads or not bodies:
                continue
            checked += 1
            with self.subTest(game=game):
                rows = Image.open(heads[0]).size[1] // HEAD_ROW_PX
                self.assertEqual(
                    rows, wanted["heads"],
                    f"{game}: head atlas holds {rows} rows, table says "
                    f"{wanted['heads']}",
                )
                cells = len(bodies) * BODY_CELLS_PER_SHEET
                self.assertEqual(
                    cells // BODY_ANIMATION_FRAMES, wanted["bodies"],
                    f"{game}: {len(bodies)} body sheets give "
                    f"{cells // BODY_ANIMATION_FRAMES} bodies, table says "
                    f"{wanted['bodies']}",
                )
        self.assertGreaterEqual(checked, 5, "expected all five installs")

    def test_creation_rng_is_not_used_as_the_criterion(self) -> None:
        """The specific regression this file exists to prevent.

        Each of these is a value some game's creation RNG rolls. If a chooser is
        ever resized to one, the last option disappears again -- silently,
        because the number looks well-sourced.
        """
        rng_subsets = {"vv1": 19, "vv4": 29, "vv5": 29}
        for game, subset in rng_subsets.items():
            spec = DECLARED[game]
            for kind in ("heads", "bodies"):
                for macro in spec[kind]:
                    value = _macro(spec["source"], macro)
                    with self.subTest(game=game, macro=macro):
                        self.assertNotEqual(
                            value, subset,
                            f"{game}'s {macro} is {subset}, the creation RNG "
                            f"range -- not the number of options in the art",
                        )


if __name__ == "__main__":
    unittest.main()
