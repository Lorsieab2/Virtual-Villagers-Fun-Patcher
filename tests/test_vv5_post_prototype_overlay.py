from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

from scripts import build_vv5_post_prototype_overlay as B


ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "research" / "vv5-expanded-prototype.exe"


class VV5PostPrototypeOverlayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.value = B.build()

    def bad(self, mutate) -> None:
        value = copy.deepcopy(self.value)
        mutate(value)
        with self.assertRaises(ValueError):
            B.validate(value)

    def test_checked_in_candidate_is_deterministic(self) -> None:
        self.assertEqual(self.value, json.loads(B.OUTPUT.read_text(encoding="utf-8")))
        self.assertEqual(B.validate(), self.value)

    def test_candidate_schema_is_closed(self) -> None:
        schema = json.loads(B.SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(schema["$id"], self.value["schema"])
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["properties"]["bindings"]["additionalProperties"])
        self.assertFalse(schema["$defs"]["row"]["additionalProperties"])

    def test_all_routes_remain_disabled(self) -> None:
        self.assertEqual(self.value["status"], "static_overlay_go_runtime_stop")
        for key in ("enabled", "catalog_visible", "native_output", "runtime_go", "player_go", "publication_ready"):
            self.assertFalse(self.value[key], key)
        self.assertEqual(self.value["evidence"]["runtime_receipts"], [])
        self.assertEqual(self.value["evidence"]["player_receipts"], [])

    def test_exact_parent_and_result(self) -> None:
        bindings = self.value["bindings"]
        overlay = self.value["overlay"]
        self.assertEqual(bindings["prototype_sha256"], B.PROTOTYPE_SHA256)
        self.assertEqual(bindings["prototype_size"], 991232)
        self.assertEqual(bindings["prototype_checksum"], "98F10F00")
        self.assertEqual(overlay["result_size"], 991232)
        self.assertEqual(overlay["checksum_after"], "6E3B0F00")
        self.assertEqual(overlay["result_sha256"], B.RESULT_SHA256)

    def test_manifest_and_c342_bindings_are_immutable(self) -> None:
        bindings = self.value["bindings"]
        self.assertEqual(
            bindings["expanded_manifest"],
            {"path": "data/expanded_256.json", "game": "vv5", "row_count": 1951, "rows_sha256": B.MANIFEST_ROWS_SHA256, "immutable": True},
        )
        self.assertEqual(bindings["c342_relocation_ledger"]["count"], 66)
        self.assertEqual(bindings["c342_relocation_ledger"]["rows_sha256"], B.LEDGER_SHA256)
        self.assertEqual(bindings["c342_relocation_ledger"]["source_text_sha256"], B.LEDGER_SOURCE_SHA256)
        self.assertTrue(bindings["c342_relocation_ledger"]["immutable"])

    def test_exact_sixteen_same_width_rows(self) -> None:
        rows = self.value["overlay"]["rows"]
        self.assertEqual(len(rows), 16)
        self.assertEqual([row["write_raw"] for row in rows], [f"0x{row[3]:X}" for row in B.PATCH_ROWS])
        for row in rows:
            self.assertEqual(len(bytes.fromhex(row["before"])), row["width"])
            self.assertEqual(len(bytes.fromhex(row["after"])), row["width"])

    def test_stack_locator_and_instruction_starts_are_distinct_and_exact(self) -> None:
        rows = {row["id"]: row for row in self.value["overlay"]["rows"]}
        self.assertEqual((rows["candidate_frame"]["reviewed_locator_raw"], rows["candidate_frame"]["write_raw"]), ("0x71EB8", "0x71EB6"))
        self.assertEqual((rows["candidate_capacity"]["reviewed_locator_raw"], rows["candidate_capacity"]["write_raw"]), ("0x71EC3", "0x71EC2"))
        self.assertEqual((rows["candidate_store"]["reviewed_locator_raw"], rows["candidate_store"]["write_raw"]), ("0x7203C", "0x72039"))
        self.assertEqual((rows["candidate_load"]["reviewed_locator_raw"], rows["candidate_load"]["write_raw"]), ("0x720B3", "0x720B0"))

    def test_overlay_does_not_overlap_dbxxx_ledger_or_index_gates(self) -> None:
        self.assertEqual(self.value["overlay"]["dbxxx_range"]["overlap_count"], 0)
        self.assertEqual(self.value["overlay"]["relocation_ledger_overlap_count"], 0)
        self.assertEqual(self.value["bindings"]["central_index_gate"]["overlap_count"], 0)
        self.assertEqual(self.value["bindings"]["save_geometry"]["overlap_count"], 0)
        B._validate_repo_bindings(ROOT)

    def test_exact_source_bound_render(self) -> None:
        if not PROTOTYPE.is_file():
            self.skipTest("exact VV5 prototype is not present")
        parent = PROTOTYPE.read_bytes()
        result = B.render_candidate(parent)
        self.assertEqual(hashlib.sha256(parent).hexdigest().upper(), B.PROTOTYPE_SHA256)
        self.assertEqual(hashlib.sha256(result).hexdigest().upper(), B.RESULT_SHA256)
        self.assertEqual(result[0x150:0x154].hex().upper(), B.RESULT_CHECKSUM)
        expected_changed = {
            0x150 + index
            for index, pair in enumerate(zip(parent[0x150:0x154], result[0x150:0x154]))
            if pair[0] != pair[1]
        }
        for _, _, _, raw, before, after in B.PATCH_ROWS:
            expected_changed.update(
                raw + index
                for index, pair in enumerate(zip(bytes.fromhex(before), bytes.fromhex(after)))
                if pair[0] != pair[1]
            )
        self.assertEqual(
            {index for index, pair in enumerate(zip(parent, result)) if pair[0] != pair[1]},
            expected_changed,
        )

    def test_wrong_parent_and_stale_preimage_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "prototype fingerprint"):
            B.render_candidate(bytes(B.PROTOTYPE_SIZE))
        if PROTOTYPE.is_file():
            changed = bytearray(PROTOTYPE.read_bytes())
            changed[0x6F830] ^= 1
            with self.assertRaisesRegex(ValueError, "prototype fingerprint"):
                B.render_candidate(changed)

    def test_rebinding_or_enablement_is_rejected(self) -> None:
        self.bad(lambda value: value.update(enabled=True))
        self.bad(lambda value: value["bindings"]["expanded_manifest"].update(row_count=1950))
        self.bad(lambda value: value["overlay"]["rows"][0].update(after="00000000"))
        self.bad(lambda value: value["overlay"].update(result_sha256="0" * 64))

    def test_cli_check_and_dry_run(self) -> None:
        script = ROOT / "scripts" / "build_vv5_post_prototype_overlay.py"
        check = subprocess.run([sys.executable, str(script), "--check"], capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)
        dry = subprocess.run([sys.executable, str(script), "--dry-run"], capture_output=True, text=True)
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertIn("STOP", dry.stdout)
        if PROTOTYPE.is_file():
            bound = subprocess.run([sys.executable, str(script), "--dry-run", "--parent", str(PROTOTYPE)], capture_output=True, text=True)
            self.assertEqual(bound.returncode, 0, bound.stderr)
            self.assertIn(B.RESULT_SHA256, bound.stdout)


if __name__ == "__main__":
    unittest.main()
