import copy
import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_vv3_full256_serializer_evidence import DATA, ROOT, SCHEMA, validate


class VV3Full256SerializerEvidenceTests(unittest.TestCase):
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

    def test_checked_in_evidence_is_static_go_but_overall_stop(self) -> None:
        data = validate()
        self.assertEqual(data["status"], "static_serializer_reader_go_writer_rollback_stop")
        self.assertFalse(data["enabled"])
        self.assertFalse(data["native_output"])
        self.assertEqual(data["atomic_writer"]["status"], "STOP")
        self.assertEqual(data["whole_load_rollback"]["status"], "STOP")

    def test_schema_is_closed_and_pinned(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(schema["$id"], "vvfp.vv3_full256_serializer_evidence.v1")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(set(schema["required"]), set(self.data))

    def test_extra_top_level_field_rejected(self) -> None:
        self.bad(lambda data: data.update(unreviewed=True))

    def test_manifest_count_rejected(self) -> None:
        self.bad(lambda data: data["bindings"]["expanded_manifest"].update(row_count=1262))

    def test_parent_rebind_rejected(self) -> None:
        self.bad(lambda data: data["bindings"]["parents"][0].update(sha256="0" * 64))

    def test_page_digest_rejected(self) -> None:
        self.bad(lambda data: data["replacement"].update(section_sha256="0" * 64))

    def test_hook_target_rejected(self) -> None:
        self.bad(lambda data: data["replacement"]["serializer_hook"].update(target="0x7B9000"))

    def test_result_digest_rejected(self) -> None:
        self.bad(lambda data: data["replacement"]["results"][1].update(sha256="0" * 64))

    def test_atomic_writer_claim_rejected(self) -> None:
        self.bad(lambda data: data["atomic_writer"].update(status="GO"))

    def test_atomic_writer_bytes_rejected(self) -> None:
        self.bad(lambda data: data["atomic_writer"].update(wrapper_bytes="90"))

    def test_whole_load_rollback_claim_rejected(self) -> None:
        self.bad(lambda data: data["whole_load_rollback"].update(status="GO"))

    def test_whole_load_rollback_bytes_rejected(self) -> None:
        self.bad(lambda data: data["whole_load_rollback"].update(snapshot_bytes="90"))

    def test_synthetic_runtime_receipt_rejected(self) -> None:
        self.bad(lambda data: data["runtime_evidence"]["receipts"].append({"synthetic": True}))

    def test_publication_rejected(self) -> None:
        self.bad(lambda data: data.update(publication_ready=True))


if __name__ == "__main__":
    unittest.main()
