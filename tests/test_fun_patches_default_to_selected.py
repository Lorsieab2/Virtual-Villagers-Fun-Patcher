"""Every fun patch starts selected, and a fresh install cannot undo that.

The owner's rule: "from now on, all builds have all patches on by default.
even for the patcher. so we never have stupidity like missing features."

Two facts have to hold together, and the first is worthless without the
second. Review caught that on #350: setting every checkbox to True is
silently reversed by `_load_settings`, which read a MISSING `fun_patches`
key as a saved empty selection and set every variable back to False. A
fresh install has no settings file at all, so `data` is `{}` -- meaning the
default was defeated in exactly the case it exists for, and nothing in the
suite would have noticed.

These assertions read the GUI source rather than constructing the window,
because the suite runs headless and a Tk root is not available. That is a
real limitation: it pins the code that decides the default, not an observed
checkbox. It is still enough to catch both regressions, since each is a
single visible line.
"""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "src" / "vv_fun_patcher_gui.py"


class FunPatchesDefaultToSelectedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = GUI.read_text(encoding="utf-8")

    def test_every_checkbox_variable_starts_true(self) -> None:
        self.assertIn(
            "patch.id: tk.BooleanVar(value=True) for patch in self.fun_patches",
            self.source,
            "fun-patch checkboxes no longer default to selected",
        )
        self.assertNotIn(
            "patch.id: tk.BooleanVar(value=False) for patch in self.fun_patches",
            self.source,
        )

    def test_a_missing_saved_selection_does_not_clear_the_default(self) -> None:
        """`data.get("fun_patches", [])` would turn every patch off.

        A fresh install has no settings file, so `_load_settings` falls back
        to `{}`. With a `[]` default the restore loop runs and sets every
        variable to False. Reading the key with no default leaves it None,
        the `isinstance(..., list)` guard is skipped, and the all-selected
        initial state survives.
        """
        self.assertIn('selected_fun = data.get("fun_patches")', self.source)
        self.assertNotIn('data.get("fun_patches", [])', self.source)

    def test_the_restore_loop_is_still_guarded_by_the_list_check(self) -> None:
        """A present-but-malformed setting must not be applied either."""
        index = self.source.index('selected_fun = data.get("fun_patches")')
        following = self.source[index : index + 200]
        self.assertIn("if isinstance(selected_fun, list):", following)


if __name__ == "__main__":
    unittest.main()
