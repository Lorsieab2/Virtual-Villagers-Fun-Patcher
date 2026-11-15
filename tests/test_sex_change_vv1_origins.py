"""A villager's sex changed (native/shared/sex_change.h): "VVFP VV1 Origins Icons.dll" keeps their mask, through
its own export VvfpVillagerSexChanged and through the save's "Sex Changes" log.

A New Home's mask file names each record's villager by an identity that holds the sex (name, sex and the family
scalar +0x36C), and the load moves each mask to the villager the file names.  Each case runs the DLL itself in
tests/story_emulator.py on the stock executable, with the exe patch's mask scratch mapped and an emulated disk
(tests/sex_change_origins_emulation.py):
  * the change in play, the export told: the mask stays on the villager, and the file written now names them by
    the new identity -- a reload with the new sex finds the mask;
  * the save not saved after the change (the owner Alt-F4s; a backup restored): the file names the new identity,
    the save the old sex.  With the slot's log naming the villager the mask is found; without it, it is not;
  * a name two living villagers share is never guessed: the log naming it moves no mask to either.

And Change Appearance's "Change sex..." button (native/shared/sex_change_ui.h): the real dialog procedure and
templates, built with the game's own .rc into native/vv1_origins_icons/sex_change_dialog_harness.c
(scripts/build_sex_change_origins_harness.ps1; -Shots makes the screenshots).
"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

try:
    import test_head_look as hl  # noqa: E402
    from sex_change_origins_emulation import GAMES, Village, log_path, masks_path  # noqa: E402
    HAVE = hl.HAVE_EMULATOR and hl.stock_path(1).is_file() and GAMES[1]["dll"].is_file()
except ImportError:  # pragma: no cover - environment dependent
    HAVE = False

M, F = 1, 2
RED = 3


class MaskSexChangeCases:
    """The cases, for A New Home here and The Lost Children (tests/test_sex_change_vv2_origins.py)."""
    GAME = 0

    def village(self, sexes, *, disk=None, names=("Kai", "Lani", "Moku", "Nalu")):
        v = Village(self.GAME, hl.stock_exe(self.GAME), disk=disk)
        for i, (name, sex) in enumerate(zip(names, sexes)):
            v.villager(i, name, sex, family=10 + i, parents=(f"Pa{i}", f"Ma{i}"))
        return v

    def masked_then_changed(self):
        """Lani (female) wears the red mask; her sex is changed in play and the DLL told."""
        v = self.village([M, F, M, F])
        v.load()
        v.put_mask(1, RED)
        self.assertEqual(v.mask(1), RED)
        self.assertEqual(v.change(1), 1)
        v.frame()
        return v

    def test_the_mask_follows_a_sex_change_in_play(self):
        v = self.masked_then_changed()
        self.assertEqual(v.mask(1), RED)
        # The file was written at once, under Lani's new identity.
        self.assertIn(masks_path(self.GAME, 1), v.disk.files)
        self.assertEqual(v.file_roster()[1], v.identity(1))
        # A reload of the save with the new sex finds the mask on her.
        later = self.village([M, M, M, F], disk=v.disk)
        later.load()
        self.assertEqual(later.mask(1), RED)
        self.assertEqual([later.mask(i) for i in (0, 2, 3)], [0, 0, 0])

    def test_the_log_finds_them_when_the_save_was_not_saved(self):
        v = self.masked_then_changed()
        # The save still holds the old sex.  Without the log the mask is not found...
        lost = self.village([M, F, M, F], disk=v.disk)
        lost.load()
        self.assertEqual(lost.mask(1), 0)
        # ...with the slot's log naming Lani, it is -- and only on her.
        v.disk.files[log_path(1)] = b"F\tM\tLani\r\n"
        found = self.village([M, F, M, F], disk=v.disk)
        found.load()
        self.assertEqual(found.mask(1), RED)
        self.assertEqual([found.mask(i) for i in (0, 2, 3)], [0, 0, 0])

    def test_a_name_two_living_villagers_share_is_never_guessed(self):
        v = Village(self.GAME, hl.stock_exe(self.GAME))
        for i, (name, sex) in enumerate((("Kai", M), ("Lani", F), ("Moku", M), ("Nalu", F), ("Lani", M))):
            v.villager(i, name, sex, family=10 + i, parents=(f"Pa{i}", f"Ma{i}"))
        v.load()
        v.put_mask(1, RED)
        v.change(1)
        v.frame()
        self.assertEqual(v.mask(1), RED)            # in play the record is the villager: kept
        v.disk.files[log_path(1)] = b"F\tM\tLani\r\n"
        # The save not saved after the change: the log names "Lani", whom two living villagers are called.
        twin = Village(self.GAME, hl.stock_exe(self.GAME), disk=v.disk)
        for i, (name, sex) in enumerate((("Kai", M), ("Lani", F), ("Moku", M), ("Nalu", F), ("Lani", M))):
            twin.villager(i, name, sex, family=10 + i, parents=(f"Pa{i}", f"Ma{i}"))
        twin.load()
        self.assertEqual(twin.mask(1), 0)
        self.assertEqual(twin.mask(4), 0)

    def test_nothing_to_carry_is_not_an_error(self):
        v = self.village([M, F, M, F])
        v.load()
        self.assertEqual(v.change(0), 1)            # the pair is kept
        if self.GAME == 1:
            self.assertNotIn(masks_path(self.GAME, 1), v.disk.files)   # no mask: nothing to write
        else:
            # The Lost Children writes its roster with every change of it (births, deaths): under Kai's new
            # identity.
            self.assertEqual(v.file_roster()[0], v.identity(0))
        self.assertEqual(v.p.export("VvfpVillagerSexChanged", 9, 1, v.record(0), v.record(0)), 0)
        self.assertEqual(v.p.export("VvfpVillagerSexChanged", self.GAME, 1, 0, 0), 0)


@unittest.skipUnless(HAVE, "unicorn/pefile, the stock A New Home or the DLL is missing")
class VV1MaskFollowsSexChange(MaskSexChangeCases, unittest.TestCase):
    GAME = 1


BUILD = ROOT / "scripts" / "build_sex_change_origins_harness.ps1"
CL = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC"
          r"\14.51.36231\bin\Hostx64\x86\cl.exe")


# Every check the harness makes, by game: A New Home adds the Golden Child's (the button hidden, its command doing
# nothing, no box); both have the carrying villager's (asked with the carrying sentence, the pregnancy kept).
DIALOG_CHECKS = {1: 60, 2: 53}


def run_dialog_harness(test: unittest.TestCase, game: int) -> str:
    """native/vv1_origins_icons/sex_change_dialog_harness.c for `game`: the real dialog procedure pressed (Change
    sex answered Yes and No, Undo changes, Cancel, pressed twice, the hair colours after it, a carrying villager, the Golden Child) and
    the real templates measured (the button inside the window, over no other control, its text inside it)."""
    run = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BUILD),
                          "-Games", str(game)], capture_output=True, text=True, timeout=900)
    out = run.stdout + run.stderr
    test.assertEqual(run.returncode, 0, out)
    test.assertIn(f"game {game}: {DIALOG_CHECKS[game]} checks, 0 failures", out)
    return out


class ChangeSexButtonSource(unittest.TestCase):
    """The button is in both per-villager windows, after Reset to original; not in Change Appearance for All."""
    GAME = 1
    RC = ROOT / "native" / "vv1_origins_icons" / "vv1_origins_icons.rc"
    WINDOWS = (203, 208)
    FOR_ALL = 204

    def dialog(self, text: str, number: int) -> str:
        return text.split(f"\n{number} DIALOGEX", 1)[1].split("\nEND", 1)[0]

    def test_the_button_is_in_each_per_villager_window_only(self):
        text = self.RC.read_text(encoding="utf-8")
        for number in self.WINDOWS:
            body = self.dialog(text, number)
            self.assertEqual(body.count('PUSHBUTTON  "Change sex...", 3506,'), 1, number)
            self.assertLess(body.index('"Reset to original", 3501'), body.index('"Change sex...", 3506'))
            self.assertLess(body.index('"Change sex...", 3506'), body.index('"OK", 1,'))
        self.assertNotIn("3506", self.dialog(text, self.FOR_ALL))

    def test_the_export_is_listed(self):
        name = "vv1_origins_icons" if self.GAME == 1 else "vv2_origins_icons"
        exports = (ROOT / "native" / name / f"{name}.def").read_text(encoding="utf-8")
        self.assertIn("VvfpVillagerSexChanged=_VvfpVillagerSexChanged@16", exports)


@unittest.skipUnless(os.name == "nt" and CL.is_file(), "needs Windows and the Visual Studio x86 compiler")
class VV1ChangeSexDialog(unittest.TestCase):
    def test_the_real_dialog(self):
        run_dialog_harness(self, 1)


class GoldenChildNeverOffered(unittest.TestCase):
    """The Golden Child (family 0xC7) never sees the button: the window hides it when it opens."""

    def test_the_window_hides_the_button_for_him(self):
        source = (ROOT / "native" / "vv1_origins_icons" / "vv1_origins_icons.c").read_text(encoding="utf-8")
        hide = source.split("static void appearance_offer_sex(HWND window) {", 1)[1].split("\n}", 1)[0]
        self.assertIn("vvfp_ax_change_sex_offered(1, appearance_state.villager)", hide)
        self.assertIn("SW_HIDE", hide)
        init = source.split("static INT_PTR CALLBACK appearance_dialog(", 1)[1].split("} else if (message == WM_DRAWITEM)", 1)[0]
        self.assertIn("appearance_offer_sex(window);", init)


if __name__ == "__main__":
    unittest.main()
