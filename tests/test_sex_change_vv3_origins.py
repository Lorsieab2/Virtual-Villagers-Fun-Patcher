"""A villager's sex changed (native/shared/sex_change.h): The Secret City's masks ("VVFP Origins Icons.dll" for game 3,
built from native/vv3_full_mastery_candidate) stay theirs.  The Secret City finds a mask by the fingerprint stored
with it (gender, likes, dislikes, name), wherever its villager is: the DLL's export VvfpVillagerSexChanged stores
the mask again under the fingerprint the villager has now, and at the first look after a load the save's "Sex
Changes" log finds a villager the save does not show changed.

Each case runs the real DLL in tests/story_emulator.py on the stock executable, with an emulated disk and a village
in the game's own record table; the mask is put on through VV3_SetMaskForRecord (Change Appearance's commit) and
read through VvfpMaskOf (the render getter VV3_GetMaskForRecord).  The cases are those of
tests/test_sex_change_vv4_origins.py (a rename is not followed by The Secret City's masks at all, so it is not one
of them here).
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from test_sex_change_vv4_origins import (  # noqa: E402
    FEMALE, MALE, NAMES, RED, SEXES, OriginsGame, fnv, have, have_compiler, run_button_harness, text)

LIKES, DISLIKES, HEALTH = 0xFB4, 0xFC0, 0xE78
SLOT_CAPTURE = 0x6E0044


class Vv3Game(OriginsGame):
    def __init__(self, disk_from=None):
        super().__init__(3, disk_from)

    def extra_pages(self):
        return [(SLOT_CAPTURE, 4)]

    def live(self, r: int) -> None:
        self.p.put32(r + HEALTH, 100)
        for k in range(3):
            self.p.put32(r + LIKES + 4 * k, 0xFFFFFFFF)
            self.p.put32(r + DISLIKES + 4 * k, 0xFFFFFFFF)

    def identity(self, i: int) -> int:
        r = self.record(i)
        h = fnv(2166136261, self.p.read(r + self.g["sex"], 1))
        h = fnv(h, self.p.read(r + LIKES, 12) + self.p.read(r + DISLIKES, 12))
        h = fnv(h, text(self.p.read(r + self.g["name"], 25)) + b"\xff")
        return h or 1

    def put_mask(self, i: int, mask: int) -> int:
        self.later()
        return self.p.export("VV3_SetMaskForRecord", self.record(i), mask)

    def file_ids(self, path: str) -> list[int]:
        return list(struct.unpack_from("<256I", self.disk.files[path], 4 + 256))


@unittest.skipUnless(have(3), "unicorn/pefile, the stock VV3 or the DLL is missing")
class Vv3MasksFollowASexChange(unittest.TestCase):
    def masked(self) -> Vv3Game:
        g = Vv3Game().village()
        self.assertEqual(g.put_mask(1, RED), 1)
        self.assertEqual(g.mask(1), RED)
        return g

    def test_the_mask_follows_a_sex_change_in_play(self):
        g = self.masked()
        self.assertEqual(g.change(1), 1)
        self.assertEqual(g.mask(1), RED)
        self.assertIn(g.identity(1), g.file_ids(g.masks_file()), "the file names the new fingerprint")
        later = Vv3Game(disk_from=g).village(sexes=(MALE, MALE, MALE, FEMALE))
        self.assertEqual(later.mask(1), RED)

    def test_the_log_finds_them_when_the_save_was_not_saved(self):
        g = self.masked()
        g.change(1)
        lost = Vv3Game(disk_from=g).village()
        self.assertEqual(lost.mask(1), 0, "without the log the mask is not found")
        g.log(b"F\tM\tLani\r\n")
        found = Vv3Game(disk_from=g).village()
        self.assertEqual(found.mask(1), RED, "the log naming Lani finds it")
        self.assertIn(found.identity(1), found.file_ids(found.masks_file()), "and the file is written so")

    def test_a_name_two_living_villagers_share_is_never_guessed(self):
        g = self.masked()
        g.change(1)
        g.log(b"F\tM\tLani\r\n")
        twin = Vv3Game(disk_from=g).village(names=NAMES + ("Lani",), sexes=SEXES + (FEMALE,))
        self.assertEqual(twin.mask(1), 0)
        self.assertEqual(twin.mask(4), 0)

    def test_a_fingerprint_another_villager_carries_is_never_shared(self):
        """A second living Lani, male, with the same likes: Lani (female, masked) changing to male would carry
        his fingerprint too, so the mask is not moved to it -- he never gets it."""
        g = Vv3Game().village(names=NAMES + ("Lani",), sexes=SEXES + (MALE,))
        self.assertEqual(g.put_mask(1, RED), 1)
        self.assertEqual(g.change(1), 0)
        self.assertEqual(g.mask(4), 0)
        self.assertEqual(g.mask(1), 0)

    def test_another_game_or_nothing_kept_is_not_carried(self):
        g = Vv3Game().village()
        r = g.record(0)
        self.assertEqual(g.change(0), 0, "no mask stored: nothing to carry")
        self.assertEqual(g.p.export("VvfpVillagerSexChanged", 4, 1, r, r), 0)
        self.assertEqual(g.p.export("VvfpVillagerSexChanged", 3, 1, 0, r), 0)


@unittest.skipUnless(have_compiler(), "the MSVC x86 compiler or PowerShell is missing")
class Vv3ChangeSexButton(unittest.TestCase):
    """The button in the real dialog procedure and ShowVV3AppearanceChooser (tests/test_sex_change_vv4_origins.py
    says what is checked); The Secret City's Tribal Chief and the stand-in are refused too."""

    def test_the_button_in_the_real_dialog(self):
        run_button_harness(self, 3)


if __name__ == "__main__":
    unittest.main()
