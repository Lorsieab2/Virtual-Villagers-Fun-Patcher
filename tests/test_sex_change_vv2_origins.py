"""A villager's sex changed (native/shared/sex_change.h): "VVFP VV2 Origins Icons.dll" keeps their mask, through
its own export VvfpVillagerSexChanged and through the save's "Sex Changes" log.

The Lost Children's mask file names each record's villager by an identity that holds the sex (name, sex and the
parents' names), and the village sync, every frame, moves each mask to the villager that identity names -- so
without the export a sex change in play would read as a new occupant of the record and drop the mask.  The same
cases as A New Home's (tests/test_sex_change_vv1_origins.py), run on the DLL itself in tests/story_emulator.py on
the stock executable, the exe patch's .mtab mapped and an emulated disk (tests/sex_change_origins_emulation.py),
and one more: a later rename is still told as one (the record's stable part was carried too).
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

import test_sex_change_vv1_origins as v1  # noqa: E402

try:
    import test_head_look as hl  # noqa: E402
    from sex_change_origins_emulation import GAMES  # noqa: E402
    from test_sex_change_vv1_origins import RED, F, M, MaskSexChangeCases  # noqa: E402
    HAVE = hl.HAVE_EMULATOR and hl.stock_path(2).is_file() and GAMES[2]["dll"].is_file()
except ImportError:  # pragma: no cover - environment dependent
    HAVE = False
    MaskSexChangeCases = object


class VV2ChangeSexButtonSource(v1.ChangeSexButtonSource):
    GAME = 2
    RC = ROOT / "native" / "vv2_origins_icons" / "vv2_origins_icons.rc"
    WINDOWS = (213, 218)
    FOR_ALL = 214


@unittest.skipUnless(os.name == "nt" and v1.CL.is_file(), "needs Windows and the Visual Studio x86 compiler")
class VV2ChangeSexDialog(unittest.TestCase):
    def test_the_real_dialog(self):
        v1.run_dialog_harness(self, 2)


@unittest.skipUnless(HAVE, "unicorn/pefile, the stock The Lost Children or the DLL is missing")
class VV2MaskFollowsSexChange(MaskSexChangeCases, unittest.TestCase):
    GAME = 2

    def test_without_the_export_the_sync_would_drop_it(self):
        """The control: the field flipped and the DLL NOT told -- the next frame's sync takes the record for a
        new occupant.  So the export is what keeps the mask in play."""
        v = self.village([M, F, M, F])
        v.load()
        v.put_mask(1, RED)
        v.p.put32(v.record(1) + v.g["sex"], M)
        v.frame()
        self.assertEqual(v.mask(1), 0)

    def test_a_later_rename_is_still_one(self):
        v = self.masked_then_changed()
        v.p.write(v.record(1) + v.g["name"], b"Leilani\0")
        v.frame()
        self.assertEqual(v.mask(1), RED)
        self.assertEqual(v.file_roster()[1], v.identity(1))


if __name__ == "__main__":
    unittest.main()
