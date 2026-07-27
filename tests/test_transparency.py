from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from transparency import (  # noqa: E402
    TRANSPARENCY_FILENAME,
    directory_comparison,
    render_transparency_text,
)
from vv_fun_patcher import apply_all, apply_patch, load_builds  # noqa: E402


STOCK = ROOT / "research" / "stock-executables"


class TransparencyTests(unittest.TestCase):
    def test_tree_comparison_reports_hashes_and_proven_no_removals(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source"
            output = Path(temp) / "output"
            source.mkdir()
            output.mkdir()
            (source / "stock.exe").write_bytes(b"stock")
            (output / "stock.exe").write_bytes(b"stock")
            (output / "modded.exe").write_bytes(b"modified")
            comparison = directory_comparison(source, output)
            self.assertEqual(comparison["unchanged_count"], 1)
            self.assertTrue(comparison["no_removals_proven"])
            self.assertEqual(comparison["added"][0]["sha256"], hashlib.sha256(b"modified").hexdigest().upper())

    def test_text_render_is_deterministic_when_timestamp_is_fixed(self) -> None:
        data = {
            "game": "Virtual Villagers - Test",
            "stock_executable": {"filename": "stock.exe", "size": 5, "sha256": "A"},
            "modified_executable": {"filename": "modded.exe", "size": 7, "sha256": "B"},
            "patcher_version": "test",
            "patcher_commit": "commit",
            "population_mode": "test mode",
            "auto_applied": {"population": "test", "safety": True},
            "selected_features": [],
            "applied_edits": [{
                "owner": "feature:test",
                "offset": "0x10",
                "virtual_address": "0x401010",
                "before": "00",
                "after": "01",
                "purpose": "test edit",
            }],
            "source_output_comparison": {"added": [], "modified": [], "removed": [], "unchanged_count": 1, "no_removals_proven": True},
            "retained_untouched_stock_executable": True,
            "companion_results": [],
            "pe_structural_difference": {"before": {"file_size": 5, "size_of_image": 1, "checksum": "0x1"}, "after": {"file_size": 7, "size_of_image": 1, "checksum": "0x2"}, "section_changes": [], "added_or_expanded_sections": [], "relocated_pointers": []},
            "save_handling": {"status": "not_requested", "format_behavior": "stock save layout"},
            "validation": {"static_verification": ["guard"], "runtime_player_confirmation": "pending"},
            "transparency_log": {"path": TRANSPARENCY_FILENAME, "sha256": None},
        }
        first = render_transparency_text(data, timestamp="2026-01-01T00:00:00+00:00")
        second = render_transparency_text(data, timestamp="2026-01-01T00:00:00+00:00")
        self.assertEqual(first, second)
        self.assertNotIn(str(ROOT), first)
        self.assertIn("Runtime/player confirmation: pending", first)
        self.assertIn("[feature:test]", first)

    def test_single_output_records_transparency_hash_and_stock_retention(self) -> None:
        build = load_builds()[0]
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "game"
            folder.mkdir()
            source = folder / build.input_name
            shutil.copy2(STOCK / build.input_name, source)
            output, log_path = apply_patch(source, "immediate_fixed")
            text_path = output.parent / TRANSPARENCY_FILENAME
            self.assertTrue(text_path.is_file())
            log = json.loads(log_path.read_text(encoding="utf-8"))
            self.assertEqual(log["transparency_log"]["path"], TRANSPARENCY_FILENAME)
            self.assertEqual(log["transparency_log_path"], TRANSPARENCY_FILENAME)
            self.assertEqual(
                log["transparency_log"]["sha256"],
                hashlib.sha256(text_path.read_bytes()).hexdigest().upper(),
            )
            self.assertEqual(log["transparency_log_sha256"], log["transparency_log"]["sha256"])
            self.assertTrue(log["retained_untouched_stock_executable"])
            self.assertTrue(log["source_output_comparison"]["no_removals_proven"])
            report = text_path.read_text(encoding="utf-8")
            self.assertIn("Runtime/player confirmation", report)
            self.assertNotIn(str(folder), report)

    def test_bulk_outputs_each_receive_game_scoped_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sources = {}
            for build in load_builds():
                folder = root / build.id
                folder.mkdir()
                source = folder / build.input_name
                shutil.copy2(STOCK / build.input_name, source)
                sources[build.id] = folder
            results = apply_all(sources, "immediate_fixed")
            self.assertEqual(len(results), 5)
            for output, log_path in results:
                self.assertTrue((output.parent / TRANSPARENCY_FILENAME).is_file())
                self.assertEqual(json.loads(log_path.read_text())["game"], output.name.removesuffix(" - Modded.exe"))


if __name__ == "__main__":
    unittest.main()
