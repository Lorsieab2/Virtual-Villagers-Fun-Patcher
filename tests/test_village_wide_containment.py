from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    PatcherError,
    get_fun_patch,
    load_builds,
    load_fun_patches,
    load_patch_modes,
    render_patched_bytes,
    resolve_fun_patch_ids,
)
from vv_fun_patcher_gui import group_fun_patches  # noqa: E402

STOCK = ROOT / "research" / "stock-executables"
BASELINE = "6df57ea5aa56dc8d4253172d9610eecf8dd34a75"
DISABLED = {f"vv{game}_origins_village_wide_upgrades" for game in range(1, 6)}


def raw_record(game_id: str) -> dict:
    return json.loads(
        (ROOT / "data" / f"{game_id}_origins_village_wide_upgrades.json").read_text(
            encoding="utf-8"
        )
    )


class VillageWideContainmentTests(unittest.TestCase):
    def test_all_five_records_are_fail_closed_and_payloads_are_frozen(self) -> None:
        for game_id in ("vv1", "vv2", "vv3", "vv4", "vv5"):
            with self.subTest(game=game_id):
                current = raw_record(game_id)
                self.assertIs(current["enabled"], False)
                self.assertTrue(current["patches"])
                prior = json.loads(
                    subprocess.check_output(
                        [
                            "git",
                            "show",
                            f"{BASELINE}:data/{game_id}_origins_village_wide_upgrades.json",
                        ],
                        cwd=ROOT,
                        text=True,
                    )
                )
                current_without_gate = dict(current)
                prior_without_gate = dict(prior)
                current_without_gate.pop("enabled", None)
                prior_without_gate.pop("enabled", None)
                self.assertEqual(current_without_gate, prior_without_gate)
                base_path = f"data/{game_id}_origins_feature.json"
                self.assertEqual(
                    json.loads((ROOT / base_path).read_text(encoding="utf-8")),
                    json.loads(
                        subprocess.check_output(
                            ["git", "show", f"{BASELINE}:{base_path}"], text=True
                        )
                    ),
                )

        for companion_path in (
            "assets/origins/VVFP Origins Icons.dll",
            "assets/statistics/VVFP Statistics Export.dll",
        ):
            self.assertEqual(
                (ROOT / companion_path).read_bytes(),
                subprocess.check_output(
                    ["git", "show", f"{BASELINE}:{companion_path}"]
                ),
            )

        generator = (ROOT / "scripts" / "build_village_wide_origins_features.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('feature["enabled"] = False', generator)
        self.assertNotIn('if game_id == "vv2":\n            feature["enabled"] = False', generator)
        loader = (ROOT / "src" / "vv_fun_patcher.py").read_text(encoding="utf-8")
        village_loop = loader.split(
            "for feature_path in ORIGINS_VILLAGE_WIDE_FEATURE_PATHS:", 1
        )[1]
        self.assertIn('if record.get("enabled", True):', village_loop)

    def test_catalog_gui_cli_and_resolution_cannot_select_disabled_records(self) -> None:
        catalog = load_fun_patches()
        ids = {patch.id for patch in catalog}
        self.assertTrue(DISABLED.isdisjoint(ids))
        grouped = group_fun_patches(load_builds(), catalog)
        grouped_ids = {patch.id for _, patches in grouped for patch in patches}
        self.assertTrue(DISABLED.isdisjoint(grouped_ids))

        help_text = subprocess.check_output(
            [sys.executable, str(ROOT / "src" / "vv_fun_patcher.py"), "--help"],
            cwd=ROOT,
            text=True,
        )
        for patch_id in DISABLED:
            self.assertNotIn(patch_id, help_text)
            with self.assertRaisesRegex(PatcherError, "Unknown fun patch"):
                get_fun_patch(patch_id)
            with self.assertRaisesRegex(PatcherError, "Unknown optional patch"):
                resolve_fun_patch_ids([patch_id], game_id=patch_id[:3])

    def test_no_mode_renders_disabled_owners_or_payload_ranges(self) -> None:
        catalog = load_fun_patches()
        for build in load_builds():
            source = STOCK / build.input_name
            source_bytes = source.read_bytes()
            game_ids = [patch.id for patch in catalog if patch.game_id == build.id]
            raw = raw_record(build.id)
            forbidden = []
            for item in raw["patches"]:
                start = int(item["offset"], 0)
                forbidden.append((start, start + len(bytes.fromhex(item["after"]))))
            for mode in load_patch_modes():
                with self.subTest(game=build.id, mode=mode.id):
                    rendered, applied = render_patched_bytes(
                        source, build, mode.id, game_ids
                    )
                    owners = {item["owner"] for item in applied}
                    self.assertNotIn(
                        f"feature:{build.id}_origins_village_wide_upgrades", owners
                    )
                    for edit in applied:
                        edit_start = int(edit["offset"], 0)
                        edit_end = edit_start + len(bytes.fromhex(edit["after"]))
                        self.assertFalse(
                            any(edit_start < end and start < edit_end for start, end in forbidden)
                        )
                    for start, end in forbidden:
                        self.assertEqual(rendered[start:end], source_bytes[start:end])

    def test_base_origins_remains_independently_composable_except_contained_vv2(self) -> None:
        catalog_ids = {patch.id for patch in load_fun_patches()}
        for build in load_builds():
            base_id = f"{build.id}_enable_origins_exclusive_features"
            if build.id == "vv2":
                self.assertNotIn(base_id, catalog_ids)
                continue
            self.assertIn(base_id, catalog_ids)
            for mode in load_patch_modes():
                _, applied = render_patched_bytes(
                    STOCK / build.input_name, build, mode.id, [base_id]
                )
                owners = {item["owner"] for item in applied}
                self.assertIn(f"feature:{base_id}", owners)
                self.assertNotIn(
                    f"feature:{build.id}_origins_village_wide_upgrades", owners
                )

    def test_containment_documents_save_and_atomic_payload_boundaries(self) -> None:
        docs = "\n".join(
            (ROOT / name).read_text(encoding="utf-8")
            for name in (
                "README.md",
                "How to Use.txt",
                "docs/origins-village-wide-upgrades.md",
                "docs/origins-playtest-readiness.md",
                "docs/origins-player-runtime-checklist.md",
            )
        )
        for phrase in (
            "atomic payload",
            "628e0d9217b92b9cd695655842b09d74689a0238",
            "02581c8f518e27ebd5fc7d2972db5597ab08ed35",
            "089957227c0db6a4c3128045519ffa27b201a00e",
            "+0xEAC..+0xEBC",
            "mastery begins at 88",
            "native maximum is 100",
            "award ID 4",
            "direct 90 stores",
            "zero-change/no-charge",
            "creation/inheritance",
            "60f649bf90b55dea3a6856d949e123bd79808782",
            "+0x7E4..+0x7F4",
            "job preference",
            "+0x7F8",
            "Master threshold 88",
            "native award paths cap at 100",
            "stride `0xE48C`",
            "signed health",
            "Silver Mirror",
            "Gong and every Island Event",
            "e0bed87ce17dca5331afed1abc2d753ec3d8f0aa",
            "+0x3BC..+0x3CC",
            "+0x3D0",
            "Master threshold 90",
            "native cap 100",
            "32 records",
            "stride `0x3D8`",
            "+0x28",
            "+0x344",
            "state+0xA2FC",
            "preference/title",
            "Golden Child/Event bypass",
            "aaddf71797c28f37b0cc1f5728e567c0601a05aa",
            "+0x1B8C",
            "20 units per year",
            "360",
            "0x46F7F0",
            "oldest-villager statistic",
            "+0x1C3C",
            "+0x1C4C",
            "+0x1CE1",
            "+0x1CEC",
            "no-op/already-18",
            "Nursing timer",
            "43 missing relocations",
            "ab404b0c5e80cab4d327de9a51069e6e3529df27",
            "929,792-byte",
            "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220",
            "sub_43BA80",
            "sub_465F10",
            "0x46663B",
            "dword_4D6E00",
            "sub_45DB30",
            "sub_45DBE0",
            "stride `0x2E3C`",
            "150/256 bound",
            "+0x1CC4",
            "+0x1CC7",
            "0x4D6F88",
            "sub_41E300",
            "pending baby count",
            "stock-plus-expanded",
            "refund",
        ):
            self.assertIn(phrase, docs)


if __name__ == "__main__":
    unittest.main()
