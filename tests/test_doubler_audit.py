from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs" / "doubler-composition-audit.md"
GENERATOR = ROOT / "scripts" / "generate_transparency_docs.py"
RELEASE = ROOT / "scripts" / "build_release.py"
VV2_EXE = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"
VV2_MANIFEST = ROOT / "data" / "vv2_origins_feature.json"

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
        self.assertIn("**Pending**", text)
        self.assertIn("**STOP**", text)
        self.assertIn("tail-jump", text)
        self.assertIn("collection-adjusted positive delta", text)

    def test_audit_states_both_composition_rules(self) -> None:
        text = AUDIT.read_text(encoding="utf-8")
        self.assertIn("Island Event results are never doubled", text)
        self.assertIn("twice the exact native", text)
        self.assertIn("positive, zero", text)
        self.assertIn("or negative", text)
        self.assertIn("collection plus doubler", text)

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
