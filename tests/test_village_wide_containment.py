from __future__ import annotations

import hashlib
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
BASELINE = "2b1fafdeddd98148911f8891077172e303e98a7c"
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
                base_current = json.loads(
                    (ROOT / base_path).read_text(encoding="utf-8")
                )
                base_prior = json.loads(
                    subprocess.check_output(
                        ["git", "show", f"{BASELINE}:{base_path}"], text=True
                    )
                )
                if game_id != "vv5":
                    self.assertEqual(base_current["patches"], base_prior["patches"])
                    self.assertEqual(
                        base_current.get("patch_mode_overrides"),
                        base_prior.get("patch_mode_overrides"),
                    )
                    self.assertEqual(
                        base_current.get("expanded_shr_relocations"),
                        base_prior.get("expanded_shr_relocations"),
                    )
                self.assertEqual(
                    base_current["companion_files"][0]["source"],
                    base_prior["companion_files"][0]["source"],
                )
                self.assertEqual(
                    base_current["companion_files"][0]["destination"],
                    base_prior["companion_files"][0]["destination"],
                )

        origins = ROOT / "assets/origins/VVFP Origins Icons.dll"
        self.assertEqual(
            base_current["companion_files"][0]["sha256"],
            hashlib.sha256(origins.read_bytes()).hexdigest().upper(),
        )
        statistics_path = "assets/statistics/VVFP Statistics Export.dll"
        self.assertEqual(
            (ROOT / statistics_path).read_bytes(),
            subprocess.check_output(["git", "show", f"{BASELINE}:{statistics_path}"]),
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
            game_ids = [
                patch.id
                for patch in catalog
                if patch.game_id == build.id
                and not (
                    build.id == "vv1"
                    and patch.id == "vv1_full_mastery_all_stage_a_candidate"
                )
            ]
            raw = raw_record(build.id)
            forbidden = []
            for item in raw["patches"]:
                start = int(item["offset"], 0)
                forbidden.append((start, start + len(bytes.fromhex(item["after"]))))
            for mode in load_patch_modes():
                with self.subTest(game=build.id, mode=mode.id):
                    if build.id == "vv3" and mode.id.startswith(
                        "experimental_expanded_256"
                    ):
                        with self.assertRaisesRegex(
                            PatcherError, "has no append layout"
                        ):
                            render_patched_bytes(
                                source, build, mode.id, game_ids
                        )
                        continue
                    if build.id == "vv4" and mode.id.startswith("experimental_expanded_256"):
                        with self.assertRaisesRegex(PatcherError, "ON HOLD"):
                            render_patched_bytes(source, build, mode.id, game_ids)
                        continue
                    if build.id == "vv5" and mode.id.startswith("experimental_expanded_256"):
                        with self.assertRaisesRegex(PatcherError, "(?:stock-mode only|no append layout)"):
                            render_patched_bytes(source, build, mode.id, game_ids)
                        continue
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
                if build.id == "vv3" and mode.id.startswith(
                    "experimental_expanded_256"
                ):
                    with self.assertRaisesRegex(PatcherError, "has no append layout"):
                        render_patched_bytes(
                            STOCK / build.input_name, build, mode.id, [base_id]
                        )
                    continue
                if build.id == "vv4" and mode.id.startswith(
                    "experimental_expanded_256"
                ):
                    with self.assertRaisesRegex(PatcherError, "ON HOLD"):
                        render_patched_bytes(
                            STOCK / build.input_name, build, mode.id, [base_id]
                        )
                    continue
                if build.id == "vv5" and mode.id.startswith("experimental_expanded_256"):
                    with self.assertRaisesRegex(PatcherError, "(?:stock-mode only|no append layout)"):
                        render_patched_bytes(
                            STOCK / build.input_name, build, mode.id, [base_id]
                        )
                    continue
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
            "295b5d1e228c501d0e14b1f869f11b0caa3a07bd",
            "831,488-byte",
            "8BC5DB382D02BC5C21AD5F607580D60FF44A6519CC7EB133F03113BAACAE6503",
            "+0xDC4",
            "sub_45F3E0",
            "sub_45C640",
            "0x45F5C6",
            "sub_45FFE0",
            "+0xE74",
            "372 to 360",
            "survived save/reload",
            "advanced natively to 361",
            "nursing/conception-age/lifecycle timestamp",
            "food, health, mortality, and reproduction",
            "pauses those steps",
            "not a final GO",
            "transaction/result bytes",
            "both-expanded PE manifests",
            "+0xE8C",
            "inherently invalid",
            "bd6ce555a9a197450aab7133c0a87b36fbfc6899",
            "724,992-byte",
            "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677",
            "+0x530",
            "+0x534",
            "sub_43B690",
            "0x43B8FD",
            "0x43C09A",
            "sub_44B980",
            "+0x540",
            "marker + 40 < processed age",
            "0xE48C",
            "+0x558",
            "state+0x2EADC",
            "0x422006",
            "0x44EB3E",
            "0x4217F9",
            "true native maximum 100",
            "five skills in VV1–VV4 and six in VV5",
            "0311443fbd078e3adcabaf7e693199989ddb9db8",
            "a67e05247dc822306e1d5a514524cba388ab4d69",
            "f1555e295e828af2165ab0b7ea9f051ac9736418",
            "581,632 bytes",
            "1EC790B927741081D5CE13A48FB76983A4FD4336EA08F89317872643760AF03D",
            "4 Likes + 4 Dislikes",
            "62 Likes + 62 Dislikes",
            "3 Likes + 3 Dislikes",
            "`-1` is not an early terminator",
            "duplicate Running Like",
            "0x420D22",
            "code-confirmed independently",
            "already-Running Like",
            "first physical slot equal to `-1`",
            "full Likes causes no mutation",
            "unrelated slots",
            "too few slots",
            "bounded four-counter",
            "stock plus expanded",
            "+0x1CEC != 0",
            "Skipped over X villagers. Reason: already likes running",
            "Removed running dislike from X villagers",
            "future-only",
            "Official LDW Cheat Tables",
            "current authoritative vanilla-table",
            "Official LDW Cheat Tables  (Backup!!)",
            "recovery/version comparison",
            "Official LDW Cheat Tables - Copy",
            "strong player-confirmed runtime evidence",
            "renamed/copied base-game executables",
            "fingerprinting the underlying executable",
            "process/module-name-dependent Cheat Engine script",
            "controls every claim",
            "531b0aca8d5bf051f87773e67d48b61c0ba02833",
            "1d9a39da078806aa940e4774a9068956e88347bc",
            "+0xFB4..+0xFC8",
            "stride `0x1F8C`",
            "150/256 physical bound",
            "Granted Running to %u villagers",
            "Skipped over %u villagers. Reason: already likes running",
            "Removed running dislike from %u villagers",
            "Skipped over %u villagers. Reason: all like slots are occupied",
            "granted == 0",
            "final unsigned funds recheck",
            "+0xE94",
            "944-byte atomic payload",
            "0x7B820",
            "0x7B840/0x47B840",
            "0x582644",
            "0x7B7A0",
            "three-counter 128-byte",
            "0x6547D",
            "0x65640",
            "0xA3180",
            "command-6-only UI guards",
            "relocation, uninstall",
            "d1cdeb67362487c1d577e3abae03c9424fd04fb9",
            "0x455993/0x55993",
            "0x4568A3/0x568A3",
            "0x45C9AA/0x5C9AA",
            "0x468D4C/0x68D4C",
            "0x469081/0x69081",
            "0x46915C/0x6915C",
            "0x4692C8/0x692C8",
            "0x4697EF/0x697EF",
            "0x45F2B1/0x5F2B1",
            "no direct nonzero writer",
            "do not label `+0xE94`",
            "Running-only seven-row",
            "ID 1006",
            "command == 6",
            "{granted, already_like, full_like, removed_dislike}",
            "Granted Running to %u villagers",
            "at most 201 bytes",
            "char[256]",
            "Removal costs 0, refunds 0",
            "does not reverse preferences",
            "permits repurchase",
            "ImageBase `0x400000`",
            "SectionAlignment/FileAlignment",
            "`0x2DF000`",
            "1,263 guarded patches",
            "b9c7a22eb1d7cceae25160ce4d360621e7485625",
            "dormant retained per-villager totem-render selector",
            "'s totem",
            "'s remains",
            "64 active",
            "125 active",
            "`+0xF10 != 0`",
            "signed health DWORD `+0xE78 > 0`",
            "VV2's `+0x558`",
            "VV5's Heathen totems",
            "disabled command-6-only",
            "Sol certifies those emitted bytes",
            "precharges, exposes",
            "callback ABI",
            "Persistence here means serialization and restoration",
            "refund",
        ):
            self.assertIn(phrase, docs)


if __name__ == "__main__":
    unittest.main()
