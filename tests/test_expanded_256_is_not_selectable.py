"""Expanded-256 must never be a patch mode a player can pick.

The expanded-256 population modes for VV3, VV4 and VV5 are dead: they crash and
break the game.  They are already unreachable -- `data/builds.json` declares only
`stock`, `collection_progression` and `immediate_fixed` -- and this locks that
in so no future change can re-expose them.

The constants still exist in the patcher because live features
(`collection_progression` and `immediate_fixed`) share guard scaffolding with
them, so deleting the constants outright is not safe today.  What matters for a
player is that no expanded mode is ever offered, which is what this file proves:

  - the declared patch-mode list contains no expanded mode;
  - every game's per-mode variants offer no expanded mode;
  - nothing a player selects resolves to one.

See docs/expanded-256-is-not-selectable.md for why the remaining internal
scaffolding is left in place.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

import vv_fun_patcher as patcher  # noqa: E402

BUILDS = ROOT / "data" / "builds.json"
EXPANDED_MARKERS = ("expanded_256", "expanded-256")


def _is_expanded(name: str) -> bool:
    lowered = str(name).lower()
    return any(marker in lowered for marker in EXPANDED_MARKERS)


class ExpandedModeIsNotSelectableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads(BUILDS.read_text(encoding="utf-8"))

    def test_the_constant_still_names_the_dead_modes(self) -> None:
        """Guards the rest of this file against passing vacuously.

        If the expanded constants are ever genuinely removed, these tests would
        otherwise start proving nothing.
        """
        expanded = getattr(patcher, "EXPANDED_PATCH_MODES", None)
        self.assertTrue(
            expanded,
            "EXPANDED_PATCH_MODES is gone; if the scaffolding was removed for "
            "real, delete this file rather than letting it pass vacuously",
        )
        for mode in expanded:
            self.assertTrue(_is_expanded(mode))

    def test_no_expanded_mode_is_declared_as_a_patch_mode(self) -> None:
        declared = []
        for entry in self.data.get("patch_modes", []):
            declared.append(entry.get("id") if isinstance(entry, dict) else entry)
        self.assertTrue(declared, "no patch modes are declared at all")
        for mode in declared:
            with self.subTest(mode=mode):
                self.assertFalse(
                    _is_expanded(mode),
                    f"{mode} is selectable; the expanded-256 modes crash VV3, "
                    f"VV4 and VV5 and must never be offered",
                )

    def test_the_declared_modes_are_exactly_the_three_safe_ones(self) -> None:
        declared = [
            entry.get("id") if isinstance(entry, dict) else entry
            for entry in self.data.get("patch_modes", [])
        ]
        self.assertEqual(
            sorted(declared),
            ["collection_progression", "immediate_fixed", "stock"],
        )

    def test_no_game_offers_an_expanded_variant(self) -> None:
        """Reads `variants`, the attribute Build actually has.

        This looked at `patch_variants`, which does not exist, so every game's
        variant map defaulted to {} and the loop body never ran once -- the
        guard passed on exactly the mutation it advertises.
        """
        examined = 0
        for build in patcher.load_builds():
            variants = getattr(build, "variants", None) or {}
            self.assertTrue(variants, f"{build.id} exposes no variants at all")
            for mode in variants:
                examined += 1
                with self.subTest(game=build.id, mode=mode):
                    self.assertFalse(
                        _is_expanded(mode),
                        f"{build.id} exposes {mode}",
                    )
        self.assertGreaterEqual(
            examined, 15, "expected three modes for each of the five games"
        )

    def test_no_selectable_variant_applies_the_expanded_patches(self) -> None:
        """The stronger guarantee: not merely unlisted, but never applied.

        `_expanded_patches` returns nothing unless a variant sets
        `expanded_records`, and the data it used to load rewrote live code --
        including VV5's 0x4713F0, which appears in crash dumps, and the
        `mov ebx, 0x96` record-loop bound inside it.  That data is now removed
        entirely; this keeps the flag itself pinned off.
        """
        for game in self.data["games"]:
            variants = game.get("patch_variants") or game.get("variants") or {}
            if not isinstance(variants, dict):
                continue
            for mode, variant in variants.items():
                if not isinstance(variant, dict):
                    continue
                with self.subTest(game=game["id"], mode=mode):
                    self.assertFalse(
                        variant.get("expanded_records", False),
                        f"{game['id']}/{mode} would apply the dead "
                        f"expanded-256 patch set",
                    )

    def test_the_expanded_patch_data_is_gone(self) -> None:
        """900 KB of VV3/VV4/VV5 rows that rewrote live code for a dead mode.

        Nothing selectable could apply them, and they included the rewrite of
        VV5's 0x4713F0 -- the function in both crash dumps. Removed outright.
        """
        self.assertFalse(
            (ROOT / "data" / "expanded_256.json").exists(),
            "the expanded-256 patch data is back; it rewrites live code for "
            "modes that crash the games and cannot be selected",
        )

    def test_requesting_expanded_records_now_fails_closed(self) -> None:
        """A revival must fail loudly rather than silently patch nothing."""
        build = next(b for b in patcher.load_builds() if b.id == "vv5")
        with self.assertRaises(patcher.PatcherError):
            patcher._expanded_patches(build, {"expanded_records": True})
        self.assertEqual(patcher._expanded_patches(build, {}), [])

    def test_expanded_modes_are_disjoint_from_the_declared_modes(self) -> None:
        declared = {
            entry.get("id") if isinstance(entry, dict) else entry
            for entry in self.data.get("patch_modes", [])
        }
        self.assertEqual(
            declared & set(patcher.EXPANDED_PATCH_MODES),
            set(),
            "a dead expanded mode has been declared as a real patch mode",
        )


if __name__ == "__main__":
    unittest.main()
