from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "scripts" / "ida_diagnostic_probe.py"
RUNBOOK = ROOT / "docs" / "ida-attended-native-export-runbook.md"


class IdaDiagnosticProbeTests(unittest.TestCase):
    def test_runbook_points_to_tracked_probe(self) -> None:
        runbook = RUNBOOK.read_text(encoding="utf-8")
        self.assertTrue(PROBE.is_file())
        self.assertIn("scripts\\ida_diagnostic_probe.py", runbook)
        self.assertIn("-A", runbook)
        self.assertIn("-S<workspace-root>\\scripts\\ida_diagnostic_probe.py", runbook)

    def test_probe_is_stdout_only_status_and_not_native_exporter(self) -> None:
        source = PROBE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
        ]
        call_names = {
            node.func.id
            for node in calls
            if isinstance(node.func, ast.Name)
        }
        attribute_calls = {
            node.func.attr
            for node in calls
            if isinstance(node.func, ast.Attribute)
        }

        self.assertIn("print", call_names)
        self.assertIn("dumps", attribute_calls)
        self.assertIn("auto_wait", attribute_calls)
        self.assertIn("get_func_qty", attribute_calls)
        self.assertIn("qexit", attribute_calls)
        self.assertNotIn("open", call_names)
        self.assertNotIn("write_text", attribute_calls)
        self.assertNotIn("write_bytes", attribute_calls)
        self.assertNotIn("dump", attribute_calls)

        forbidden_native_terms = (
            "RESOLVED_EAS",
            "raw_bytes",
            "call_convention",
            "stack_cleanup",
            "ida_bytes",
            "idautils",
        )
        for term in forbidden_native_terms:
            with self.subTest(term=term):
                self.assertNotIn(term, source)


if __name__ == "__main__":
    unittest.main()
