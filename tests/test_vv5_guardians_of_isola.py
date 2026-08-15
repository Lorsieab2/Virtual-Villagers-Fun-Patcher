from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402


PATCH_ID = "vv5_guardians_of_isola_rewrite"
EXPECTED_DESTINATIONS = {
    "Assets/sm.xml",
    "Images/BlinkyEyes.png",
    "Images/BlinkyEyesSm.png",
    "Images/BuildingTotemStrip.png",
    "Images/ChildrensTotemStrip.png",
    "Images/FoodTotemStrip.png",
    "Images/MedicineTotemStrip.png",
    "Images/RainbowTotemStrip.png",
    "Images/ResearchTotemStrip.png",
    "Images/blinkEyesMaskStrip.png",
    "Images/blinkEyesMaskStripSm.png",
    "Images/idol_states.png",
    "Images/mainmenu.jpg",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class GuardiansOfIsolaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        catalog = {item.id: item for item in patcher.load_fun_patches()}
        assert PATCH_ID in catalog, f"{PATCH_ID} is not a selectable fun patch"
        cls.patch = catalog[PATCH_ID]
        cls.companions = cls.patch.raw.get("companion_files", [])

    def test_patch_is_vv5_presentation_only_companion_swap(self) -> None:
        self.assertEqual(self.patch.game_id, "vv5")
        # Presentation-only: it must not alter executable bytes.
        self.assertEqual(self.patch.raw.get("patches", []), [])
        self.assertEqual(len(self.companions), 13)
        self.assertEqual(
            {item["destination"] for item in self.companions}, EXPECTED_DESTINATIONS
        )

    def test_every_companion_source_and_restore_original_are_present_and_pinned(self) -> None:
        root = ROOT.resolve()
        for item in self.companions:
            source = (ROOT / item["source"]).resolve()
            restore = (ROOT / item["restore_source"]).resolve()
            # Both bundled files must live inside the patcher folder.
            source.relative_to(root)
            restore.relative_to(root)
            self.assertTrue(source.is_file(), item["source"])
            self.assertTrue(restore.is_file(), item["restore_source"])
            # Source (Guardians asset) hash + size are pinned exactly.
            self.assertEqual(sha(source), item["sha256"].upper())
            self.assertEqual(source.stat().st_size, item["size"])
            # Restore original hash is pinned and equals the replacement preimage.
            self.assertEqual(sha(restore), item["restore_sha256"].upper())
            self.assertEqual(item["preimage_sha256"].upper(), item["restore_sha256"].upper())
            # A rewrite must actually change the file.
            self.assertNotEqual(item["sha256"].upper(), item["restore_sha256"].upper())
            # Destinations stay inside Assets/ or Images/.
            self.assertRegex(item["destination"], r"^(Assets|Images)/[^\\/]+$")

    def test_enable_swaps_in_and_disable_restores_exact_base_bytes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vv5-guardians-") as td:
            root = Path(td)
            # Seed the folder with the exact base-game originals.
            for item in self.companions:
                dest = root / item["destination"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes((ROOT / item["restore_source"]).read_bytes())
            # Enable: every destination becomes the Guardians asset.
            patcher._copy_companion_files(root, [self.patch])
            for item in self.companions:
                self.assertEqual(sha(root / item["destination"]), item["sha256"].upper())
            # Disable: every destination returns to the exact base-game bytes.
            removed = patcher._remove_companion_files(root, [self.patch])
            self.assertEqual(len(removed), 13)
            self.assertTrue(all(entry.get("action") == "restore" for entry in removed))
            for item in self.companions:
                self.assertEqual(sha(root / item["destination"]), item["restore_sha256"].upper())


if __name__ == "__main__":
    unittest.main()
