"""Fun patches start at the default selection, and a fresh install keeps it.

The owner's rule was "from now on, all builds have all patches on by default.
even for the patcher. so we never have stupidity like missing features."

It was later narrowed, and the narrower form is what this now checks: "can you
exclude the 'learning never fails' patches for all 5 games from being selected?
otherwise it should select all patches." So the default is every patch except a
named deny-list, which `default_fun_patch_selection` owns and
tests/test_default_patch_selection.py covers. What matters here is unchanged --
that whatever the default is, a fresh install does not silently lose it.

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

    def test_every_checkbox_variable_starts_at_the_default(self) -> None:
        """The initial state must consult the shared rule, not a literal.

        This asserted `value=True` for every patch, which was right until the
        owner excluded Learning Skills Never Fails. Hard-coding True again
        would put those five back on; hard-coding False would turn everything
        off. Both are wrong, so the variable's initial value has to come from
        the same predicate the Default Patches button uses.
        """
        self.assertIn(
            "default_fun_patch_selection(patch.id)",
            self.source,
            "fun-patch checkboxes no longer start at the default selection",
        )
        self.assertNotIn(
            "patch.id: tk.BooleanVar(value=False) for patch in self.fun_patches",
            self.source,
        )
        self.assertNotIn(
            "patch.id: tk.BooleanVar(value=True) for patch in self.fun_patches",
            self.source,
            "a literal True ignores the deny-list",
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
