from __future__ import annotations

import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    _pe_checksum_layout,
    PatcherError,
    load_builds,
    load_fun_patches,
    load_patch_modes,
    pe_checksum,
    render_patched_bytes,
    resolve_fun_patch_ids,
)


STOCK = ROOT / "research" / "stock-executables"
READINESS_DOC = ROOT / "docs" / "origins-playtest-readiness.md"


class OriginsPlaytestReadinessTests(unittest.TestCase):
    def test_all_games_and_modes_compose_complete_catalog_without_mutating_stock(self) -> None:
        catalog = load_fun_patches()
        modes = load_patch_modes()
        self.assertEqual(
            [mode.id for mode in modes],
            [
                "collection_progression",
                "immediate_fixed",
                "experimental_expanded_256",
                "experimental_expanded_256_progression",
            ],
        )
        for build in load_builds():
            with self.subTest(game=build.id):
                source = STOCK / build.input_name
                before = source.read_bytes()
                game_patches = [patch for patch in catalog if patch.game_id == build.id]
                ids = [patch.id for patch in game_patches]
                base_id = f"{build.id}_enable_origins_exclusive_features"
                wide_id = f"{build.id}_origins_village_wide_upgrades"
                self.assertNotIn(wide_id, ids)
                if build.id == "vv2":
                    self.assertNotIn(base_id, ids)
                else:
                    self.assertIn(base_id, ids)
                selected_ids = resolve_fun_patch_ids(ids, game_id=build.id, patches=game_patches)
                self.assertEqual(set(selected_ids), set(ids))
                for patch in game_patches:
                    self.assertIn(patch.id, selected_ids)
                    self.assertEqual(patch.game_id, build.id)
                    for companion in patch.raw.get("companion_files", []):
                        companion_path = ROOT / companion["source"]
                        self.assertTrue(companion_path.is_file())
                        self.assertEqual(
                            hashlib.sha256(companion_path.read_bytes()).hexdigest().upper(),
                            companion["sha256"],
                        )
                for mode in modes:
                    with self.subTest(mode=mode.id):
                        if build.id == "vv3" and mode.id.startswith(
                            "experimental_expanded_256"
                        ):
                            with self.assertRaisesRegex(
                                PatcherError, "has no append layout"
                            ):
                                render_patched_bytes(
                                    source, build, mode.id, selected_ids
                                )
                            self.assertEqual(source.read_bytes(), before)
                            continue
                        if build.id == "vv4" and mode.id.startswith(
                            "experimental_expanded_256"
                        ):
                            with self.assertRaisesRegex(PatcherError, "ON HOLD"):
                                render_patched_bytes(
                                    source, build, mode.id, selected_ids
                                )
                            self.assertEqual(source.read_bytes(), before)
                            continue
                        rendered, applied = render_patched_bytes(
                            source, build, mode.id, selected_ids
                        )
                        self.assertEqual(source.read_bytes(), before)
                        owners = {item["owner"] for item in applied}
                        self.assertNotIn(f"feature:{wide_id}", owners)
                        for patch_id in selected_ids:
                            self.assertIn(f"feature:{patch_id}", owners)
                        checksum_offset, _ = _pe_checksum_layout(rendered)
                        stored = struct.unpack_from("<I", rendered, checksum_offset)[0]
                        self.assertNotEqual(stored, 0)
                        self.assertEqual(stored, pe_checksum(rendered))
                        self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), hashlib.sha256(before).digest())

    def test_readiness_document_states_static_only_boundary(self) -> None:
        text = READINESS_DOC.read_text(encoding="utf-8")
        folded = " ".join(text.split())
        self.assertIn("static composition/readiness only", text)
        self.assertIn("does not prove player-visible\nruntime behavior", text)
        self.assertIn("never launches a game", text)
        self.assertIn("VV1, VV3, and VV4 doubler new purchases and repurchases remain unavailable", text)
        self.assertIn("VV5 stock-layout Tech and\nFood Doublers support purchase", text)
        self.assertIn("expanded-256 modes, both writer hooks are restored to native", text)
        self.assertIn("75-row relocation ledger covers\n32 rows and leaves 43 references", text)
        self.assertIn("36 cross-section rel32 and 7 external", text)
        self.assertIn("8dfccbd1b31e55f5168bb1c5ff23890bb98d9fdb", text)
        self.assertIn("VV5 native Time Warp, Island Event, and Barrel rows remain unavailable", folded)
        self.assertIn("36f14702b938a6235230a3fd3e0c34328d3ac745", text)
        self.assertIn("VV3Run2 is hard-withdrawn", text)
        self.assertIn("crashed on the status-2 no-change route", text)
        self.assertIn("fault instruction remains unknown", text)
        self.assertIn("Do not package or test this feature", text)
        self.assertIn("D81FB967C9DDE2448C40744356AE08BBADFA78930ABA004CEE5BE4025C65FBD0", text)
        self.assertIn("2ED1100E7F2EA5B8E522C2DE11F6B00CA8A02B968319C251365E9EFD634BCAF9", text)
        for address in (
            "0x6DF040", "0x6DF120", "0x6DF206", "0x6DF091",
            "0x6DF0D7", "0x4A3400", "0x6DF3D7", "0x7B8040",
            "0x7B8120", "0x7B8206", "0x7B8091", "0x7B80D7",
            "0x7B83D7",
        ):
            self.assertIn(address, text)
        self.assertIn("exception code/fault RVA", text)
        self.assertIn("all four counters", text)
        self.assertIn("`[EBX]` must be `FFFFFFFF`", text)
        self.assertIn("f1555e295e828af2165ab0b7ea9f051ac9736418", text)
        self.assertIn("VV1 four Likes plus four Dislikes", text)
        self.assertIn("VV2 62 plus 62", text)
        self.assertIn("VV3/VV4/VV5 three plus three", text)
        self.assertIn("rather than\ntreating `-1` as a terminator", text)
        self.assertIn("preserve duplicate Running\nLikes and every Dislike", text)
        self.assertIn("0x420D22", text)
        self.assertIn("4c588ffd36765d750533fe9694f8fda5c8e82736", text)
        self.assertIn("deterministic flat `+1`", text)
        self.assertIn("changes no research speed", text)
        self.assertIn("Collection duplicates and Island Events are separate producers", text)
        self.assertIn("provenance-safe post-sum hook or source tag", text)


if __name__ == "__main__":
    unittest.main()
