"""Structural parity checks for the authenticated native-export schema."""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AuthenticatedNativeExportSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(
            (ROOT / "data/authenticated_native_export.schema.json").read_text(
                encoding="utf-8"
            )
        )

    def test_function_schema_is_closed_and_complete(self) -> None:
        function = self.schema["$defs"]["function"]
        required = {
            "query_id",
            "status",
            "function_start_ea",
            "function_end_ea",
            "file_offset",
            "raw_bytes",
            "instructions",
            "callers",
            "xrefs",
            "registers",
            "stack_cleanup",
            "call_convention",
        }
        self.assertEqual(set(function["required"]), required)
        self.assertFalse(function["additionalProperties"])
        self.assertEqual(function["properties"]["status"]["const"], "resolved")

    def test_instruction_schema_is_closed_and_requires_text(self) -> None:
        instruction = self.schema["$defs"]["instruction"]
        self.assertEqual(set(instruction["required"]), {"ea", "text"})
        self.assertFalse(instruction["additionalProperties"])

    def test_root_references_closed_function_items(self) -> None:
        functions = self.schema["properties"]["functions"]
        self.assertEqual(functions["minItems"], 10)
        self.assertEqual(functions["maxItems"], 10)
        self.assertEqual(functions["items"]["$ref"], "#/$defs/function")


if __name__ == "__main__":
    unittest.main()
