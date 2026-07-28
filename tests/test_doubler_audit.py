from __future__ import annotations

import json
import hashlib
import struct
import unittest
from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from vv_fun_patcher import load_builds, load_fun_patches  # noqa: E402
AUDIT = ROOT / "docs" / "doubler-composition-audit.md"
GENERATOR = ROOT / "scripts" / "generate_transparency_docs.py"
TRANSPARENCY = ROOT / "docs" / "transparency-log.md"
README = ROOT / "README.md"
HOW_TO_USE = ROOT / "How to Use.txt"
RELEASE = ROOT / "scripts" / "build_release.py"
VV2_EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"
VV2_MANIFEST = ROOT / "data" / "vv2_origins_feature.json"
ORIGINS_MANIFESTS = tuple(ROOT / "data" / f"vv{game}_origins_feature.json" for game in range(1, 6))

VV2_TECH_CALLS = (
    (0x4205A7, 0x4205AC), (0x43434C, 0x434351), (0x4385E1, 0x4385E6),
    (0x438741, 0x438746), (0x4388A1, 0x4388A6), (0x438A9B, 0x438AA0),
    (0x438C7B, 0x438C80), (0x438E5B, 0x438E60), (0x44EA2D, 0x44EA32),
    (0x44ED4D, 0x44ED52), (0x44F1FD, 0x44F202), (0x46345C, 0x463461),
    (0x463468, 0x46346D), (0x463474, 0x463479), (0x463737, 0x46373C),
    (0x4637C0, 0x4637C5), (0x463809, 0x46380E),
)
VV2_FOOD_CALLS = (
    (0x420AE4, 0x420AE9), (0x433FC1, 0x433FC6), (0x438293, 0x438298),
    (0x438371, 0x438376), (0x438445, 0x43844A), (0x44E9BE, 0x44E9C3),
    (0x44EDB4, 0x44EDB9), (0x44F0D4, 0x44F0D9), (0x463198, 0x46319D),
    (0x463259, 0x46325E), (0x463312, 0x463317), (0x463364, 0x463369),
    (0x4633CD, 0x4633D2),
)


def _call_target(image: bytes, va: int) -> int:
    """Decode an exact-build near CALL at an image-base-relative VA."""
    offset = va - 0x400000
    if image[offset] != 0xE8:
        raise AssertionError(f"expected CALL at {va:#x}")
    return va + 5 + struct.unpack_from("<i", image, offset + 1)[0]


class DoublerAuditDocumentationTests(unittest.TestCase):
    def test_transparency_document_matches_generator_and_is_deterministic(self) -> None:
        from scripts import generate_transparency_docs

        first = generate_transparency_docs.build_document()
        second = generate_transparency_docs.build_document()
        self.assertEqual(first, second)
        self.assertEqual(first, TRANSPARENCY.read_text(encoding="utf-8"))

    def test_transparency_catalog_has_unique_ordered_patch_headings(self) -> None:
        from scripts import generate_transparency_docs

        text = generate_transparency_docs.build_document()
        headings = [line for line in text.splitlines() if line.startswith("#### ")]
        expected = []
        for build in load_builds():
            patches = sorted(
                (patch for patch in load_fun_patches() if patch.game_id == build.id),
                key=lambda patch: (patch.name.casefold(), patch.id),
            )
            expected.extend(f"#### {patch.name} (`{patch.id}`)" for patch in patches)
        self.assertEqual(headings, expected)
        self.assertEqual(len(headings), len(set(headings)))
        self.assertEqual(text.count("## Virtual Villagers - A New Home"), 1)
        self.assertEqual(text.count("## Virtual Villagers - The Lost Children"), 1)
        self.assertEqual(text.count("## Virtual Villagers - The Secret City"), 1)
        self.assertEqual(text.count("## Virtual Villagers - The Tree of Life"), 1)
        self.assertEqual(text.count("## Virtual Villagers - New Believers"), 1)

    def test_matrix_covers_all_games_and_unresolved_statuses_are_explicit(self) -> None:
        text = AUDIT.read_text(encoding="utf-8")
        for title in (
            "VV1 A New Home",
            "VV2 The Lost Children",
            "VV3 The Secret City",
            "VV4 The Tree of Life",
            "VV5 New Believers",
        ):
            self.assertIn(title, text)
        self.assertIn("**STOP**", text)
        self.assertIn("tail-jump", text)
        self.assertIn("collection-adjusted positive delta", text)
        self.assertIn("Food Mastery status by exact build", text)
        self.assertIn("VV1, VV2, and VV3 are code-confirmed absent", text)
        self.assertIn("code-confirmed for VV4 and VV5", text)
        self.assertIn("VV5 stock-layout Tech and Food corrections are implemented", text)
        self.assertIn("VV5 expanded-256 composition remains ON HOLD", text)
        self.assertIn("**STOCK GO; EXPANDED ON HOLD**", text)
        self.assertIn("8dfccbd1b31e55f5168bb1c5ff23890bb98d9fdb", text)
        self.assertIn("covers 32 of 75 references", text)
        self.assertIn("36 cross-section rel32 and 7 external absolute", text)

    def test_audit_states_both_composition_rules(self) -> None:
        text = AUDIT.read_text(encoding="utf-8")
        self.assertIn("Island Event results are never doubled", text)
        self.assertIn("every proven collection effect that increases tech gain", text)
        self.assertIn("Food Mastery only where that exact build proves the", text)
        self.assertIn("Golden Child is a VV1-only exclusion", text)
        self.assertIn("Gong of Wonder is a VV2-only", text)
        self.assertIn("twice the exact native", text)
        self.assertIn("positive, zero", text)
        self.assertIn("or negative", text)
        self.assertIn("collection plus doubler", text)

    def test_all_origins_manifests_declare_composition_contract(self) -> None:
        for path in ORIGINS_MANIFESTS:
            with self.subTest(manifest=path.name):
                contract = json.loads(path.read_text(encoding="utf-8"))["doubler_composition_contract"]
                self.assertTrue(any("collectible" in item for item in contract["stacking"]))
                game = path.stem[2]
                expected_exclusions = {
                    "1": ("Golden Child behavior", "Island Event outcomes"),
                    "2": ("Island Event outcomes", "Gong of Wonder outcomes"),
                    "3": ("Island Event outcomes",),
                    "4": ("Island Event outcomes",),
                    "5": ("Island Event outcomes",),
                }[game]
                self.assertEqual(tuple(contract["exclusions"]), expected_exclusions)
                expected_food_status = {
                    "1": "confirmed absent",
                    "2": "confirmed absent",
                    "3": "confirmed absent",
                    "4": "confirmed",
                    "5": "confirmed",
                }[game]
                self.assertIn(expected_food_status, contract["food_mastery_status"].lower())
                status = contract["status"].lower()
                self.assertTrue(
                    "pending" in status
                    or "go:" in status
                    or "go specification" in status
                    or "implemented" in status
                    or "stop" in status
                )

    def test_origins_status_tiers_match_evidence_and_purchase_gate(self) -> None:
        expected = {
            "1": "stop",
            "2": "go",
            "3": "stop",
            "4": "stop",
            "5": "stock-layout implemented",
        }
        for path in ORIGINS_MANIFESTS:
            game = path.stem[2]
            manifest = json.loads(path.read_text(encoding="utf-8"))
            evidence = manifest["doubler_evidence"]["hook_status"].lower()
            contract = manifest["doubler_composition_contract"]["status"].lower()
            tier = expected[game]
            self.assertIn(tier, evidence)
            self.assertIn(tier, contract)
            if game in {"1", "3", "4"}:
                purchase = manifest["doubler_purchase_status"]
                self.assertIn("unavailable", purchase["new_purchase"])
                self.assertIn("disabled", purchase["repurchase"])

    def test_vv1_f6_documentation_matches_exact_manifest_behavior(self) -> None:
        patch = next(
            patch for patch in load_fun_patches()
            if patch.id == "vv1_f6_clothing_change_cheat"
        )
        description = patch.description.lower()
        self.assertIn("5,000", patch.description)
        self.assertIn("fewer than 5,000", description)
        self.assertIn("5,000 tech points", README.read_text(encoding="utf-8"))
        self.assertIn("5,000 tech points", HOW_TO_USE.read_text(encoding="utf-8"))

    def test_vv3_exact_build_doubler_stop_inventory(self) -> None:
        manifest = json.loads((ROOT / "data" / "vv3_origins_feature.json").read_text(encoding="utf-8"))
        evidence = manifest["doubler_evidence"]
        self.assertEqual(evidence["positive_tech_writer"], "0x427130")
        self.assertEqual(evidence["positive_food_writer"], "0x4263F0")
        self.assertEqual(evidence["writer_inventory"], {"food": {"rows": 33, "calls": 29, "e9_tails": 4}, "tech": {"rows": 16, "calls": 13, "e9_tails": 3}})
        self.assertEqual(evidence["tail_sites"]["food"], ["0x415EF1", "0x416983", "0x416BAB", "0x417A3A"])
        self.assertEqual(evidence["tail_sites"]["tech"], ["0x415D44", "0x41673E", "0x418452"])
        self.assertIn("sub_42DEB0", evidence["collection_adjustment"]["dispatcher"])
        self.assertEqual(evidence["collection_adjustment"]["tech_writer"], "0x42DF79")
        self.assertEqual(evidence["collection_adjustment"]["food_writer"], "0x42E079")
        self.assertIn("no resolved caller", evidence["collection_adjustment"]["caller_status"])
        self.assertIn("STOP", evidence["hook_status"])
        contract = manifest["doubler_composition_contract"]
        self.assertIn("confirmed absent", contract["food_mastery_status"])
        self.assertIn("STOP", contract["status"])
        self.assertIn("unavailable", manifest["doubler_purchase_status"]["new_purchase"])
        self.assertIn("disabled", manifest["doubler_purchase_status"]["repurchase"])

    def test_vv3_magic_level_one_composition_is_exact_and_still_on_hold(self) -> None:
        audit = AUDIT.read_text(encoding="utf-8")
        research = (ROOT / "docs" / "vv3-origins-exclusive-features-research.md").read_text(
            encoding="utf-8"
        )
        readme = README.read_text(encoding="utf-8")
        transparency = TRANSPARENCY.read_text(encoding="utf-8")
        combined = "\n".join((audit, research, readme, transparency))

        for required in (
            "4c588ffd36765d750533fe9694f8fda5c8e82736",
            "0x4593DC",
            "B + (Q ? floor(B/4) : 0) + M + T + G",
            "deterministic flat `+1`",
            "Collection duplicates and Island Events are separate producers",
            "provenance-safe post-sum hook or source tag",
        ):
            self.assertIn(required, combined)

        folded = " ".join(combined.casefold().split())
        self.assertIn("no research speed", folded)
        self.assertIn("rng probability", folded)
        self.assertIn("research-skill gain", folded)
        self.assertIn("double the complete eligible positive native", folded)
        self.assertIn("vv3 tech doubler remains unavailable", folded)
        self.assertNotIn("magic increases research speed", folded)
        self.assertNotIn("magic increases research skill", folded)

    def test_vv4_provenance_inventory_is_explicit_but_not_marked_go(self) -> None:
        manifest = json.loads((ROOT / "data" / "vv4_origins_feature.json").read_text(encoding="utf-8"))
        evidence = manifest["doubler_evidence"]
        self.assertEqual(evidence["build"]["size"], 929792)
        self.assertEqual(
            evidence["build"]["sha256"],
            "6D27A429FFCA5F1F71FDD7ECA761ED1BB67E85F976494BA178B3D7BE01F1B220",
        )
        self.assertEqual(evidence["external_xref_inventory"], {"tech": 21, "food": 23})
        self.assertIn("0x4156F8", evidence["tail_jump_sites"])
        self.assertIn("0x41520E", evidence["tail_jump_sites"])
        self.assertIn("0x414660", evidence["ordinary_positive_sites"]["food"])
        self.assertIn("STOP", evidence["hook_status"])
        self.assertIn("Food Mastery", evidence["collection_adjustment"])

    def test_vv2_exact_build_inventory_and_provenance_are_go(self) -> None:
        manifest = json.loads(VV2_MANIFEST.read_text(encoding="utf-8"))
        evidence = manifest["doubler_evidence"]
        self.assertEqual(evidence["build"]["filename"], VV2_EXE.name)
        self.assertEqual(evidence["build"]["size"], 724_992)
        self.assertEqual(
            evidence["build"]["sha256"],
            "46C1503C209255C9CDEFA941DB2F449C8CF8E2CDD5C7D13CD975326E377ED677",
        )
        self.assertIn("GO", evidence["hook_status"])
        self.assertEqual(
            tuple(evidence["tech_blacklist_returns"]),
            ("0x4205AC", "0x434351", "0x44EA32", "0x44ED52", "0x44F202"),
        )
        self.assertEqual(
            tuple(evidence["food_blacklist_returns"]),
            ("0x420AE9", "0x433FC6", "0x44E9C3", "0x44EDB9", "0x44F0D9"),
        )
        inventory = evidence["direct_call_inventory"]
        self.assertEqual(len(inventory["tech"]), 17)
        self.assertEqual(len(inventory["food"]), 13)
        self.assertEqual(
            tuple(inventory["tech"]),
            tuple(f"0x{call:X}/0x{ret:X}" for call, ret in VV2_TECH_CALLS),
        )
        self.assertEqual(
            tuple(inventory["food"]),
            tuple(f"0x{call:X}/0x{ret:X}" for call, ret in VV2_FOOD_CALLS),
        )
        contract = manifest["doubler_composition_contract"]
        self.assertIn("confirmed absent", contract["food_mastery_status"])
        self.assertIn("Farming", contract["food_mastery_status"])
        self.assertIn("Herb Mastery", contract["food_mastery_status"])
        runtime = {"patches": manifest["patches"]}
        self.assertEqual(
            hashlib.sha256(
                json.dumps(runtime, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest().upper(),
            "966C1B25B30BC5D20E892B3BA0940BC8170FE2171179355279AB65CA1656D3DC",
        )
        self.assertEqual(
            manifest["companion_files"][0]["sha256"],
            "2ED1100E7F2EA5B8E522C2DE11F6B00CA8A02B968319C251365E9EFD634BCAF9",
        )
        self.assertEqual(inventory["e9_tail_jumps_to_writers"], 0)

        image = VV2_EXE.read_bytes()
        for calls, destination in ((VV2_TECH_CALLS, 0x426290), (VV2_FOOD_CALLS, 0x4262B0)):
            for call_va, return_va in calls:
                self.assertEqual(_call_target(image, call_va), destination)
                self.assertEqual(call_va + 5, return_va)

        # No E9 tail-jump in the exact image may target either positive writer.
        for offset in range(len(image) - 4):
            if image[offset] != 0xE9:
                continue
            va = offset + 0x400000
            target = va + 5 + struct.unpack_from("<i", image, offset + 1)[0]
            self.assertNotIn(target, (0x426290, 0x4262B0))
        self.assertIn("17 tech and 13 food", AUDIT.read_text(encoding="utf-8"))
        self.assertIn("**GO (static exact-build proof; runtime pending)**", AUDIT.read_text(encoding="utf-8"))

    def test_vv2_generated_wrappers_encode_every_exact_exclusion(self) -> None:
        manifest = json.loads(VV2_MANIFEST.read_text(encoding="utf-8"))
        payload = bytes.fromhex(
            next(item["after"] for item in manifest["patches"] if item["offset"] == "0x943A8")
        )
        tech = payload[0x800:0x880]
        food = payload[0x880:0x940]
        for target, wrapper, label in (
            (manifest["doubler_evidence"]["tech_blacklist_returns"], tech, "tech"),
            (manifest["doubler_evidence"]["food_blacklist_returns"], food, "food"),
        ):
            for return_va in target:
                immediate = struct.pack("<I", int(return_va, 16))
                needle = b"\x81\x7C\x24\x04" + immediate
                self.assertIn(needle, wrapper, f"missing {label} exclusion {return_va}")
            self.assertIn(b"\x8B\x44\x24\x08", wrapper)  # signed caller delta
            ownership = b"\xF7\x83\xE8\xEA\x02\x00\x01" if label == "tech" else b"\xF7\x83\xE8\xEA\x02\x00\x02"
            self.assertIn(ownership, wrapper)

    def test_vv2_doubler_reference_model_matrix(self) -> None:
        tech_excluded = {0x4205AC, 0x434351, 0x44EA32, 0x44ED52, 0x44F202}
        food_excluded = {0x420AE9, 0x433FC6, 0x44E9C3, 0x44EDB9, 0x44F0D9}

        def result(delta: int, caller: int, owned: bool, excluded: set[int]) -> int:
            if delta <= 0 or not owned or caller in excluded:
                return delta
            return delta * 2

        for excluded in (tech_excluded, food_excluded):
            for caller in excluded | {0x4385E6, 0x4633D2}:
                for owned in (False, True):
                    for delta in (-1, 0, 1, 12345):
                        expected = delta if (not owned or caller in excluded or delta <= 0) else delta * 2
                        self.assertEqual(result(delta, caller, owned, excluded), expected)

    def test_project_transparency_and_release_include_audit_boundary(self) -> None:
        self.assertIn("docs/doubler-composition-audit.md", RELEASE.read_text(encoding="utf-8"))
        self.assertIn("docs/doubler-composition-audit.md", GENERATOR.read_text(encoding="utf-8"))
        self.assertIn("return-address checks alone", GENERATOR.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
