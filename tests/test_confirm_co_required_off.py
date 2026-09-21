"""The confirmation shown when a co-required patch is switched off.

The owner's rule: clicking Patch Games with a co-required patch off must TELL
them and then LET THEM PROCEED.  Confirm, not hard-block.

``needs_on`` is the functional relationship -- the selected patch still applies
and still works, it just does less.  ``dependencies`` is the hard one and the
GUI ticks those together, so it is deliberately not reported here.
"""

from __future__ import annotations

import ast
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from vv_fun_patcher import (  # noqa: E402
    PatcherError,
    load_public_fun_patches,
    unmet_needs_on,
    unmet_needs_on_text,
)

GUI_SOURCE = (SRC / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")


class UnmetNeedsOnTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = load_public_fun_patches()
        self.by_id = {patch.id: patch for patch in self.catalog}

    def _pairs(self):
        """Every (patch, needed patch, purpose) the catalog declares."""
        for patch in self.catalog:
            for entry in patch.raw.get("needs_on", ()) or ():
                yield patch, self.by_id[entry["id"]], entry["for"]

    def test_the_catalog_actually_declares_co_required_patches(self):
        """Guard the denominator: an empty catalog would make this file vacuous."""
        pairs = list(self._pairs())
        self.assertTrue(pairs, "no needs_on in the catalog; these tests prove nothing")

    def test_every_declared_pair_is_reported_when_the_other_is_off(self):
        """Each site independently: selecting one alone must report it."""
        for patch, needed, purpose in self._pairs():
            with self.subTest(patch=patch.id, needs=needed.id):
                unmet = unmet_needs_on([patch.id], self.catalog)
                self.assertIn(
                    (patch.name, needed.name, purpose),
                    unmet,
                    f"{patch.id} alone must report {needed.id} as off",
                )

    def test_nothing_is_reported_once_the_other_is_ticked(self):
        for patch, needed, _ in self._pairs():
            with self.subTest(patch=patch.id, needs=needed.id):
                unmet = unmet_needs_on([patch.id, needed.id], self.catalog)
                names = [(row[0], row[1]) for row in unmet]
                self.assertNotIn(
                    (patch.name, needed.name),
                    names,
                    f"{needed.id} is ticked; it must not be reported as off",
                )

    def test_an_unselected_patch_never_reports_its_own_needs(self):
        """Only what the player actually ticked is reported."""
        for patch, needed, _ in self._pairs():
            with self.subTest(patch=patch.id):
                unmet = unmet_needs_on([], self.catalog)
                self.assertEqual(unmet, (), "nothing selected reports nothing")

    def test_hard_dependencies_are_not_reported(self):
        """``dependencies`` are ticked together by the GUI, so they are not unmet.

        Reporting them here would nag about something the player cannot switch
        off independently.
        """
        for patch in self.catalog:
            raw = patch.raw.get("dependencies", ()) or ()
            if isinstance(raw, str):
                raw = (raw,)
            for dependency_id in raw:
                other = self.by_id.get(dependency_id)
                if other is None:
                    continue
                with self.subTest(patch=patch.id, depends=dependency_id):
                    unmet = unmet_needs_on([patch.id], self.catalog)
                    self.assertNotIn(
                        (patch.name, other.name),
                        [(row[0], row[1]) for row in unmet],
                        "a hard dependency must not be reported as co-required",
                    )

    def test_the_text_names_both_patches_and_the_purpose(self):
        for patch, needed, purpose in self._pairs():
            with self.subTest(patch=patch.id):
                body = unmet_needs_on_text([patch.id], self.catalog)
                self.assertIn(patch.name, body)
                self.assertIn(needed.name, body)
                self.assertIn(purpose, body)

    def test_the_text_says_the_patch_still_works(self):
        """Confirm, not hard-block: the wording must not read as a refusal."""
        patch, needed, _ = next(iter(self._pairs()))
        body = unmet_needs_on_text([patch.id], self.catalog)
        self.assertIn("still", body.lower())
        self.assertIn("anyway?", body.lower())
        for refusal in ("cannot", "must tick", "not allowed", "aborted"):
            self.assertNotIn(refusal, body.lower(), "this is a confirmation, not a block")

    def test_the_text_is_empty_when_there_is_nothing_to_say(self):
        self.assertEqual(unmet_needs_on_text([], self.catalog), "")

    def test_the_text_is_ascii_so_the_dialog_renders_everywhere(self):
        patch, _, _ = next(iter(self._pairs()))
        body = unmet_needs_on_text([patch.id], self.catalog)
        body.encode("ascii")  # raises if a stray glyph creeps back in

    def test_an_unknown_needs_on_target_is_an_error_not_a_silent_pass(self):
        class Fake:
            id = "fake_patch"
            name = "Fake"
            game_id = "vv1"
            raw = {"needs_on": [{"id": "no_such_patch", "for": "nothing"}]}

        with self.assertRaises(PatcherError):
            unmet_needs_on(["fake_patch"], [Fake()])


class GuiWiringTests(unittest.TestCase):
    """Both patch paths must ask, and must honour a No."""

    def _apply_body(self, name: str) -> str:
        tree = ast.parse(GUI_SOURCE)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return ast.get_source_segment(GUI_SOURCE, node) or ""
        self.fail(f"{name} not found in the GUI")

    def test_both_patch_paths_confirm(self):
        for name in ("_apply", "_apply_all"):
            with self.subTest(path=name):
                body = self._apply_body(name)
                self.assertIn(
                    "_confirm_unmet_needs_on",
                    body,
                    f"{name} must confirm before patching",
                )

    def test_a_no_stops_the_patch(self):
        for name in ("_apply", "_apply_all"):
            with self.subTest(path=name):
                body = self._apply_body(name)
                match = re.search(
                    r"if not self\._confirm_unmet_needs_on\([^)]*\):\s*\n\s*return",
                    body,
                )
                self.assertIsNotNone(
                    match, f"{name} must return when the player declines"
                )

    def test_the_confirmation_asks_rather_than_informs(self):
        """askyesno, not showwarning: the player gets a real choice."""
        tree = ast.parse(GUI_SOURCE)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == "_confirm_unmet_needs_on"
            ):
                body = ast.get_source_segment(GUI_SOURCE, node) or ""
                self.assertIn("askyesno", body)
                return
        self.fail("_confirm_unmet_needs_on not found in the GUI")

    def test_the_confirmation_runs_before_any_work(self):
        """Asking after the copy has started would waste the player's time."""
        for name in ("_apply", "_apply_all"):
            with self.subTest(path=name):
                body = self._apply_body(name)
                confirm_at = body.index("_confirm_unmet_needs_on")
                work_at = body.index("_run_with_wait")
                self.assertLess(
                    confirm_at, work_at, f"{name} must ask before it starts working"
                )


if __name__ == "__main__":
    unittest.main()
