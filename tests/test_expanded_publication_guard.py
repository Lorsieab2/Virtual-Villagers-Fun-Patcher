from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import vv_fun_patcher
from vv_fun_patcher import PatcherError
from vv_fun_patcher_gui import App


class ExpandedPublicationGuardTests(unittest.TestCase):
    def test_constant_and_exact_modes_are_pinned(self):
        self.assertFalse(vv_fun_patcher.EXPANDED_256_PUBLICATION_ENABLED)
        self.assertEqual(
            vv_fun_patcher.EXPANDED_PATCH_MODES,
            {"experimental_expanded_256", "experimental_expanded_256_progression"},
        )

    def test_apply_patch_rejects_before_source_or_catalog_io(self):
        source = Path("unreadable-source.exe")
        with mock.patch.object(vv_fun_patcher.Path, "resolve", side_effect=AssertionError("resolve")), \
             mock.patch.object(vv_fun_patcher, "identify", side_effect=AssertionError("identify")), \
             mock.patch.object(vv_fun_patcher, "load_fun_patches", side_effect=AssertionError("catalog")):
            for mode in sorted(vv_fun_patcher.EXPANDED_PATCH_MODES):
                with self.subTest(mode=mode), self.assertRaisesRegex(PatcherError, "Expanded-256 publication is disabled"):
                    vv_fun_patcher.apply_patch(source, mode)

    def test_apply_all_rejects_before_validation_or_filesystem_io(self):
        with mock.patch.object(vv_fun_patcher, "validate_all_sources", side_effect=AssertionError("validate")), \
             mock.patch.object(vv_fun_patcher, "load_builds", side_effect=AssertionError("builds")):
            for mode in sorted(vv_fun_patcher.EXPANDED_PATCH_MODES):
                with self.subTest(mode=mode), self.assertRaisesRegex(PatcherError, "Expanded-256 publication is disabled"):
                    vv_fun_patcher.apply_all({}, mode)

    def test_cli_apply_rejects_before_dispatch(self):
        with mock.patch.object(sys, "argv", ["vv", "apply", "missing.exe", "--patch-mode", "experimental_expanded_256"]), \
             mock.patch.object(vv_fun_patcher, "apply_patch", side_effect=AssertionError("dispatch")):
            self.assertEqual(vv_fun_patcher.main(), 1)

    def test_cli_apply_all_rejects_before_dispatch(self):
        args = ["vv", "apply-all", "--patch-mode", "experimental_expanded_256"]
        for build in vv_fun_patcher.load_builds():
            args.extend([f"--{build.id}", "missing-folder"])
        with mock.patch.object(sys, "argv", args), \
             mock.patch.object(vv_fun_patcher, "apply_all", side_effect=AssertionError("dispatch")):
            self.assertEqual(vv_fun_patcher.main(), 1)

    def test_gui_single_apply_rejects_before_source_discovery(self):
        app = App.__new__(App)
        app._mode = lambda: "experimental_expanded_256"
        app._source = mock.Mock(side_effect=AssertionError("source"))
        app.status_var = SimpleNamespace(set=mock.Mock())
        with mock.patch.object(vv_fun_patcher_gui.messagebox, "showerror"):
            app._apply()
        app._source.assert_not_called()

    def test_gui_bulk_apply_rejects_before_source_discovery(self):
        app = App.__new__(App)
        app._mode = lambda: "experimental_expanded_256_progression"
        app._all_sources = mock.Mock(side_effect=AssertionError("sources"))
        app.status_var = SimpleNamespace(set=mock.Mock())
        with mock.patch.object(vv_fun_patcher_gui.messagebox, "showerror"):
            app._apply_all()
        app._all_sources.assert_not_called()


import vv_fun_patcher_gui


if __name__ == "__main__":
    unittest.main()
