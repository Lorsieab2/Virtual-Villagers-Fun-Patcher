"""Every Origins feature must SHIP the tribe-delete stub's companion DLL.

Origins owns the tribe-delete reset in all five games, because Origins is what
writes the per-slot mask files: without the sweep, a new tribe started in a
reused slot inherits the old one's masks.

The stub resolves `VVFP Save Reset.dll` by name at runtime and falls through to
the game's own delete on every failure. That fallback is deliberate -- a
missing companion costs the sweep, never the player's save -- but it also means
a build that forgets the DLL looks perfect: the hook is present, the stub
disassembles correctly, and every byte guard passes while the feature quietly
does nothing.

That is not hypothetical. VV5's certified Task9 record SUBSTITUTES its
companion list for the base manifest's, so the entry added to
`data/vv5_origins_feature.json` never reached the copier and the shipped folder
had no DLL at all. The manifest was right; the record the patcher actually
loads was not. So this test asks the question against the LOADED feature -- the
record the copier really sees -- rather than against any manifest on disk.
"""
from __future__ import annotations

import hashlib
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402

RESET_DLL = "VVFP Save Reset.dll"
RESET_SOURCE = "assets/save_reset/VVFP Save Reset.dll"


def origins_features() -> dict[str, patcher.FunPatch]:
    return {
        item.id: item
        for item in patcher.load_fun_patches()
        if item.id.endswith("_enable_origins_exclusive_features")
    }


class OriginsShipsTheResetCompanionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.features = origins_features()

    def test_all_five_games_have_an_origins_feature(self) -> None:
        """Guard the guard: an empty set would pass everything below."""
        self.assertEqual(
            sorted(self.features),
            [f"vv{n}_enable_origins_exclusive_features" for n in range(1, 6)],
        )

    def test_every_origins_feature_ships_the_reset_companion(self) -> None:
        for feature_id, feature in sorted(self.features.items()):
            with self.subTest(feature=feature_id):
                destinations = [
                    item["destination"]
                    for item in feature.raw.get("companion_files", [])
                ]
                self.assertIn(
                    RESET_DLL,
                    destinations,
                    f"{feature_id} does not ship {RESET_DLL}, so its "
                    "tribe-delete stub resolves nothing and the sweep is "
                    "silently lost",
                )

    def test_the_shipped_companion_is_the_file_on_disk(self) -> None:
        """A pinned hash that names a file which is not there ships nothing."""
        source = ROOT / RESET_SOURCE
        self.assertTrue(source.is_file(), f"{RESET_SOURCE} is missing")
        actual = hashlib.sha256(source.read_bytes()).hexdigest().upper()
        for feature_id, feature in sorted(self.features.items()):
            entry = next(
                (
                    item
                    for item in feature.raw.get("companion_files", [])
                    if item["destination"] == RESET_DLL
                ),
                None,
            )
            with self.subTest(feature=feature_id):
                self.assertIsNotNone(entry)
                assert entry is not None
                self.assertEqual(
                    entry["sha256"].upper(),
                    actual,
                    f"{feature_id} pins a different build of {RESET_DLL} than "
                    "the one in the tree",
                )
                self.assertEqual(
                    (ROOT / entry["source"]).resolve(),
                    source.resolve(),
                    f"{feature_id} ships {RESET_DLL} from an unexpected source",
                )

    def test_the_export_the_stub_resolves_is_present(self) -> None:
        """The stub calls GetProcAddress by name; a rename disables it."""
        companion = (ROOT / RESET_SOURCE).read_bytes()
        exported = {
            name.decode("ascii", "replace") if isinstance(name, bytes) else name
            for name in patcher._pe_export_names(companion)
        }
        self.assertIn(
            "ResetDeletedTribe",
            exported,
            "the stub resolves ResetDeletedTribe by name, so the DLL must "
            "export it undecorated",
        )


if __name__ == "__main__":
    unittest.main()
