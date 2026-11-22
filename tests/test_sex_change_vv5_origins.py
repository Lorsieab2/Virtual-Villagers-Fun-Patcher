"""A villager's sex changed (native/shared/sex_change.h): New Believers' masks ("VVFP Origins Icons.dll" for game 5,
native/vv5_task9_origins) stay theirs, through the DLL's own export VvfpVillagerSexChanged and through the save's
"Sex Changes" log -- and so does a converting Heathen's mask that waits (Heathens Keep Their Masks When Converted,
VvfpMaskKeep).

Each case runs the real DLL in tests/story_emulator.py on the stock executable, with an emulated disk and a village
in the game's own record table; the mask table is the game's own (0x7B1D20), the follow is Vv5MaskSync (the export
the head draws call) and the mask is the one VvfpMaskOf answers.  See tests/test_sex_change_vv4_origins.py for the
cases; the same ones are run here.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from test_sex_change_vv4_origins import (  # noqa: E402
    FATHER, FEMALE, MALE, MOTHER, NAMES, RED, SEXES, OriginsGame, fnv, have, have_compiler, run_button_harness,
    text)

TABLE, SLOT_SCRATCH = 0x7B1D20, 0x7B1D7C
BLUE = 1


class Vv5Game(OriginsGame):
    def __init__(self, disk_from=None):
        super().__init__(5, disk_from)

    def extra_pages(self):
        return [(TABLE, 0x100)]

    def identity(self, i: int) -> int:
        r = self.record(i)
        h = fnv(2166136261, text(self.p.read(r + self.g["name"], 25)) + b"\xff")
        h = fnv(h, self.p.read(r + self.g["sex"], 4))
        h = fnv(h, text(self.p.read(r + FATHER, 25)) + b"\xfe")
        h = fnv(h, text(self.p.read(r + MOTHER, 25)) + b"\xfd")
        return h or 1

    def sync(self) -> None:
        self.later()
        self.p.export("Vv5MaskSync")

    def settle(self) -> None:
        for _ in range(2):
            self.sync()

    def set_nibble(self, i: int, mask: int) -> None:
        at = TABLE + i // 2
        b = self.p.read(at, 1)[0]
        b = (b & 0x0F) | (mask << 4) if i & 1 else (b & 0xF0) | mask
        self.p.write(at, bytes([b]))

    def put_mask(self, i: int, mask: int) -> None:
        """As Change Appearance's OK does: the nibble, then WriteMaskSidecar."""
        self.set_nibble(i, mask)
        self.p.export("WriteMaskSidecar", TABLE)

    def file_roster(self, path: str) -> list[int]:
        data = self.disk.files[path]
        return list(struct.unpack_from("<150I", data, 4))


@unittest.skipUnless(have(5), "unicorn/pefile, the stock VV5 or the DLL is missing")
class Vv5MasksFollowASexChange(unittest.TestCase):
    def masked(self) -> Vv5Game:
        g = Vv5Game().village()
        g.settle()
        g.put_mask(1, RED)
        self.assertEqual(g.mask(1), RED)
        return g

    def test_the_mask_follows_a_sex_change_in_play(self):
        g = self.masked()
        self.assertEqual(g.change(1), 1)
        self.assertEqual(g.mask(1), RED)
        g.settle()
        self.assertEqual(g.mask(1), RED, "the next looks keep it")
        path = g.masks_file()
        self.assertEqual(g.file_roster(path)[1], g.identity(1), "the file names the new identity")
        later = Vv5Game(disk_from=g).village(sexes=(MALE, MALE, MALE, FEMALE))
        later.settle()
        self.assertEqual(later.mask(1), RED)

    def test_the_log_finds_them_when_the_save_was_not_saved(self):
        g = self.masked()
        g.change(1)
        g.settle()
        lost = Vv5Game(disk_from=g).village()
        lost.settle()
        self.assertEqual(lost.mask(1), 0, "without the log the mask is not found")
        g.log(b"F\tM\tLani\r\n")
        found = Vv5Game(disk_from=g).village()
        found.settle()
        self.assertEqual(found.mask(1), RED, "the log naming Lani finds it")
        self.assertEqual(found.file_roster(found.masks_file())[1], found.identity(1), "and the file is written so")

    def test_a_name_two_living_villagers_share_is_never_guessed(self):
        g = self.masked()
        g.change(1)
        g.settle()
        g.log(b"F\tM\tLani\r\n")
        twin = Vv5Game(disk_from=g).village(names=NAMES + ("Lani",), sexes=SEXES + (FEMALE,))
        twin.settle()
        self.assertEqual(twin.mask(1), 0)
        self.assertEqual(twin.mask(4), 0)

    def test_a_later_rename_is_still_one(self):
        g = self.masked()
        g.change(1)
        g.settle()
        g.p.write(g.record(1) + g.g["name"], b"Leilani".ljust(25, b"\0"))
        g.settle()
        self.assertEqual(g.mask(1), RED)

    def test_a_waiting_heathen_mask_goes_with_them(self):
        """Heathens Keep Their Masks When Converted: a mask handed over before the table is the village's waits
        (VvfpMaskKeep answers 2); a sex change meanwhile, then the load: the mask is put on them."""
        g = Vv5Game().village()
        self.assertEqual(g.p.export("VvfpMaskKeep", g.record(2), BLUE), 2)
        self.assertEqual(g.change(2), 1)
        g.settle()
        self.assertEqual(g.mask(2), BLUE)

    def test_another_game_or_nothing_kept_is_not_carried(self):
        g = Vv5Game().village()
        g.settle()
        r = g.record(0)
        self.assertEqual(g.p.export("VvfpVillagerSexChanged", 4, 1, r, r), 0)
        self.assertEqual(g.p.export("VvfpVillagerSexChanged", 5, 1, 0, r), 0)


@unittest.skipUnless(have_compiler(), "the MSVC x86 compiler or PowerShell is missing")
class Vv5ChangeSexButton(unittest.TestCase):
    """The button in the real dialog procedure and ShowAppearanceChooser (tests/test_sex_change_vv4_origins.py
    says what is checked); New Believers' story villagers (roles 12..17) are refused too."""

    def test_the_button_in_the_real_dialog(self):
        run_button_harness(self, 5)


if __name__ == "__main__":
    unittest.main()
