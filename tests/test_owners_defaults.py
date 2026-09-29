"""The Owner's Defaults button.

The owner: "can you add a new button to the patcher? Owner's Defaults: Every
patch EXCEPT FOR LEARNING NEVER FAILS is on. (makes my life easier)" -- so it
ticks the other default-off patches too (e.g. Everyone Collects Like A New
Home), unlike Default Patches.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as vfp  # noqa: E402
from vv_fun_patcher_gui import (  # noqa: E402
    DEFAULT_OFF_FUN_PATCH_IDS,
    owners_default_fun_patch_selection,
)

GUI = ROOT / "src" / "vv_fun_patcher_gui.py"


def _ids():
    return {p.id for p in vfp.load_public_fun_patches()}


class OwnersDefaultsTests(unittest.TestCase):
    def test_everything_but_learning_never_fails_is_ticked(self):
        for patch_id in sorted(_ids()):
            with self.subTest(patch=patch_id):
                self.assertEqual(owners_default_fun_patch_selection(patch_id),
                                 "learning_never_fails" not in patch_id)

    def test_it_ticks_the_other_default_off_patches(self):
        others = {p for p in DEFAULT_OFF_FUN_PATCH_IDS if "learning_never_fails" not in p}
        self.assertTrue(others, "there is at least one other default-off patch to cover")
        for patch_id in sorted(others):
            with self.subTest(patch=patch_id):
                self.assertTrue(owners_default_fun_patch_selection(patch_id))

    def test_no_ticked_patch_needs_a_learning_patch(self):
        # Otherwise the GUI's dependency closure would tick it straight back.
        for patch in vfp.load_public_fun_patches():
            if not owners_default_fun_patch_selection(patch.id):
                continue
            for dep in patch.raw.get("dependencies") or ():
                with self.subTest(patch=patch.id, dependency=dep):
                    self.assertNotIn("learning_never_fails", dep)

    def test_the_button_exists_and_uses_its_rule(self):
        source = GUI.read_text(encoding="utf-8")
        self.assertIn('text="Owner\'s Defaults"', source)
        self.assertIn("command=self._owners_default_fun_patches", source)
        body = source[source.index("def _owners_default_fun_patches("):]
        body = body[:body.index("\n    def ")]
        self.assertIn("owners_default_fun_patch_selection(patch_id)", body)
        self.assertIn("self._fun_patch_changed()", body)


if __name__ == "__main__":
    unittest.main()
