"""A villager's sex changed (native/shared/sex_change.h): "VVFP Original Look.dll" keeps their original look.

The store's own code (native/vvfp_original_look/original_look_harness.c, real files, New Believers' layout) proves:
the change in play is carried (no new villager, no first sight) and written at once, so a reload with the new sex
finds the original; a later rename is still one (the stable part was carried); the save not saved after the change
loses the original without the slot's "Sex Changes" log and finds it with it; two living villagers of that name
are never guessed.  The DLL exports VvfpVillagerSexChanged.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import test_original_look as ol  # noqa: E402

PROVEN = (
    "the change is carried",
    "in play the original stays theirs (no new villager, no first sight)",
    "written at once: a reload with the new sex finds it",
    "a later rename in play is still one (the stable part was carried)",
    "without the log the original is not found",
    "with the slot's log naming them, it is",
    "a namesake: the log is not used, nobody guessed",
)


class OriginalLookSexChange(unittest.TestCase):
    def test_the_store_follows_a_sex_change(self):
        out = ol.harness()
        section = out.split("a sex change (VvfpVillagerSexChanged", 1)[1].split("\nno village", 1)[0]
        self.assertNotIn("[FAIL]", section)
        for proven in PROVEN:
            self.assertIn(f"[PASS] {proven}", section)

    def test_the_dll_exports_it(self):
        try:
            import pefile
        except ImportError:  # pragma: no cover - environment dependent
            self.skipTest("pefile is not installed")
        pe = pefile.PE(str(ol.DLL), fast_load=True)
        pe.parse_data_directories([pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
        names = {e.name for e in pe.DIRECTORY_ENTRY_EXPORT.symbols}
        self.assertIn(b"VvfpVillagerSexChanged", names)


if __name__ == "__main__":
    unittest.main()
