from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    import tkinter as tk
except ImportError:  # pragma: no cover - platform without Tk
    tk = None

if tk is not None:
    import vv_fun_patcher_gui as gui


def _tk_available() -> bool:
    if tk is None:
        return False
    try:
        probe = tk.Tk()
    except tk.TclError:
        return False
    probe.destroy()
    return True


@unittest.skipUnless(tk is not None and _tk_available(), "Tk display is not available")
class AllFiveCompletionDialogTests(unittest.TestCase):
    """Regression test for the "all five" completion dialog silently
    truncating to a single row.

    The bug: `_show_folder_confirmation` called
    `get_patch_variant(build, mode).output_name`, but `get_patch_variant`
    returns a plain dict, not an attribute-access object. That raised
    AttributeError on the first game's row, which Tk's default mainloop
    exception handler silently swallowed -- leaving a half-built dialog
    on screen (first game's folder links only, no artifact lines, and no
    rows at all for the remaining four games) while the app still
    reported success.
    """

    @classmethod
    def setUpClass(cls) -> None:
        # The class-level skip check above runs at collection/import time,
        # before test-runner output capturing is active. Some capture modes
        # interfere with Tcl's own file I/O once a test is actually running,
        # so re-check here and skip gracefully rather than erroring.
        try:
            cls.app = gui.App()
        except tk.TclError as exc:
            raise unittest.SkipTest(f"Tk display is not available: {exc}") from None
        cls.app.withdraw()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.app.destroy()

    def test_all_five_rows_render_with_artifact_lines_and_no_exception(self) -> None:
        rows = [
            (build.title, Path(f"C:/vanilla/{build.id}"), Path(f"C:/modded/{build.id}"))
            for build in self.app.builds
        ]
        self.assertEqual(len(rows), 5)

        # Must not raise -- this reproduces the exact call site and
        # arguments used by _apply_all() after a successful five-game run.
        self.app._show_folder_confirmation("All five modified games created", rows)

        dialog = self.app.winfo_children()[-1]
        self.assertIsInstance(dialog, tk.Toplevel)

        texts: list[str] = []

        def collect(widget) -> None:
            cget = getattr(widget, "cget", None)
            if cget is not None:
                try:
                    texts.append(str(widget.cget("text")))
                except tk.TclError:
                    pass
            for child in widget.winfo_children():
                collect(child)

        collect(dialog)
        combined = "\n".join(texts)

        for build in self.app.builds:
            self.assertIn(
                build.title,
                combined,
                f"{build.title} row is missing from the completion dialog",
            )
        self.assertEqual(
            combined.count("Patch audit:"),
            5,
            "expected one 'Patch audit' artifact line per game, "
            "got fewer -- the row loop stopped early",
        )
        dialog.destroy()


if __name__ == "__main__":
    unittest.main()
