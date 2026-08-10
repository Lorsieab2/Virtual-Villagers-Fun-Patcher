from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_vv5_post_prototype_overlay import DATA, ROOT, SCHEMA, validate


class VV5PostPrototypeOverlayEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = json.loads(DATA.read_text(encoding="utf-8"))

    def bad(self, mutate) -> None:
        data = copy.deepcopy(self.data)
        mutate(data)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "evidence.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                validate(path, ROOT)

    def test_checked_in_evidence_validates_but_remains_stop(self) -> None:
        data = validate()
        self.assertEqual(data["status"], "static_overlay_go_runtime_stop")
        for key in ("enabled", "catalog_visible", "native_output", "runtime_go", "player_go", "publication_ready"):
            self.assertFalse(data[key], key)
        self.assertEqual(data["runtime_evidence"], {"status": "absent_stop", "receipts": []})
        self.assertEqual(data["player_evidence"], {"status": "absent_stop", "receipts": []})

    def test_evidence_schema_is_closed(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(schema["$id"], self.data["schema"])
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), set(self.data))

    def test_source_bound_prototype_validation(self) -> None:
        prototype = ROOT / "research" / "vv5-expanded-prototype.exe"
        if not prototype.is_file():
            self.skipTest("exact VV5 prototype is not present")
        self.assertEqual(validate(prototype=prototype), self.data)

    def test_candidate_or_binding_rebind_is_rejected(self) -> None:
        self.bad(lambda data: data["candidate"].update(canonical_sha256="0" * 64))
        self.bad(lambda data: data["bindings"].update(c342_ledger_sha256="0" * 64))
        self.bad(lambda data: data["bindings"].update(save_geometry_sha256="0" * 64))

    def test_overlay_drift_is_rejected(self) -> None:
        self.bad(lambda data: data["overlay"].update(row_count=15))
        self.bad(lambda data: data["overlay"].update(rows_sha256="0" * 64))
        self.bad(lambda data: data["overlay"].update(result_sha256="0" * 64))

    def test_receipts_and_publication_claims_are_rejected(self) -> None:
        self.bad(lambda data: data.update(publication_ready=True))
        self.bad(lambda data: data["runtime_evidence"]["receipts"].append({"synthetic": True}))
        self.bad(lambda data: data["player_evidence"]["receipts"].append({"synthetic": True}))

    def test_extra_field_is_rejected(self) -> None:
        self.bad(lambda data: data.update(unreviewed=True))


if __name__ == "__main__":
    unittest.main()
