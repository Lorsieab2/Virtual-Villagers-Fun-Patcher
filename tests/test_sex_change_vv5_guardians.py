"""New Believers with and without "Guardians of Isola Rewrite" (vv5_guardians_of_isola_rewrite, where the Heathens are
called Isolans): a sex change behaves the same.

The patch is presentational only -- it replaces Assets/sm.xml and twelve images, no executable or save byte -- so a
Heathen's record is an Isolan's record.  Checked with the patch ON (the rewrite's sm.xml in the game folder) and OFF
(the base sm.xml), the same results both ways:
  * the companions a sex change goes through never read the game's text (sm.xml): nothing in them can follow the
    patch's words;
  * a believer's mask follows the change ("VVFP Origins Icons.dll" for game 5, VvfpVillagerSexChanged), and so does
    the mask a converting Heathen waits for (Heathens Keep Their Masks When Converted, VvfpMaskKeep);
  * a Heathen's (an Isolan's) mask, drawn from the record's own faith fields, is the same after the change;
  * the faith fields (the faction byte, the mask selectors, the faith, the role) are untouched by the change.
And the "Change sex..." button in the real dialog procedure (native/vv4_origins_icons/sex_change_ui_harness.c):
offered for a Heathen and a believer, Yes changes the sex, the faith fields byte for byte as they were.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

from test_sex_change_vv4_origins import (  # noqa: E402
    FEMALE, MALE, RED, have, have_compiler, run_button_harness)
from test_sex_change_vv5_origins import BLUE, Vv5Game  # noqa: E402

PATCH_ID = "vv5_guardians_of_isola_rewrite"
GUARDIANS = ROOT / "data" / "guardians_of_isola"
SM_XML = "c:\\games\\village\\assets\\sm.xml"     # the emulated game folder (tests/story_emulator.py)
FAITH = (0x1CE0, 0x20)                            # 0x1CEC faction, 0x1CED/E selectors, 0x1CF0 faith, 0x1CFC role

# The companions a VV5 sex change goes through (native/shared/sex_change.h tells every one of them).
SEX_CHANGE_SOURCES = [
    "native/shared/sex_change.h", "native/shared/sex_change_ui.h", "native/vv5_task9_origins/vv5_task9_origins.c",
    "native/vvfp_heathens_keep_masks/vvfp_heathens_keep_masks.c", "native/vvfp_faith_loss/vvfp_faith_loss.c",
    "native/vvfp_head_look/vvfp_head_look.c", "native/vvfp_original_look/vvfp_original_look.c",
    "native/vvfp_last_names/vvfp_last_names.c", "native/vvfp_cause_of_death/vvfp_cause_of_death.c",
]


class GuardiansIsPresentational(unittest.TestCase):
    def test_the_patch_changes_only_the_text_and_images(self):
        data = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))
        rows = [p for p in data["fun_patches"] if p.get("id") == PATCH_ID]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["patches"], [], "no executable byte")
        self.assertTrue(all(f["destination"] == "Assets/sm.xml" or f["destination"].startswith("Images/")
                            for f in rows[0]["companion_files"]))

    def test_no_sex_change_companion_reads_the_game_text(self):
        for rel in SEX_CHANGE_SOURCES:
            text = (ROOT / rel).read_text(encoding="utf-8", errors="replace").lower()
            with self.subTest(rel):
                self.assertNotIn("sm.xml", text)
                self.assertNotIn("isolan", text)


class GuardiansCases:
    """Each case, with the patch's sm.xml (ON) or the base one (OFF) in the game folder."""
    ON = True

    def game(self, disk_from=None) -> Vv5Game:
        g = Vv5Game(disk_from=disk_from)
        side = "new" if self.ON else "base"
        g.disk.files[SM_XML] = (GUARDIANS / side / "Assets" / "sm.xml").read_bytes()
        return g

    def faith(self, g: Vv5Game, i: int) -> bytes:
        return g.p.read(g.record(i) + FAITH[0], FAITH[1])

    def make_heathen(self, g: Vv5Game, i: int, faith: int = -25) -> None:
        r = g.record(i)
        g.p.write(r + 0x1CEC, b"\x01\x01\x00")    # a Heathen, the orange selector
        g.p.put32(r + 0x1CF0, faith & 0xFFFFFFFF)
        g.p.put32(r + 0x1CFC, 3)                  # an ordinary role, not 12..17

    def tearDown(self):
        g = getattr(self, "g", None)
        if g is not None:
            self.assertFalse([p for p in g.opened if p.endswith("sm.xml")], "the game text is never read")

    def test_a_believers_mask_follows_and_the_faith_stays(self):
        self.g = g = self.game().village()
        g.p.put32(g.record(1) + 0x1CF0, 60)
        g.settle()
        g.put_mask(1, RED)
        before = self.faith(g, 1)
        self.assertEqual(g.change(1), 1)
        g.settle()
        self.assertEqual(g.mask(1), RED)
        self.assertEqual(g.p.u32(g.record(1) + g.g["sex"]), MALE)
        self.assertEqual(self.faith(g, 1), before)

    def test_a_heathens_mask_and_faith_are_the_same_after_the_change(self):
        self.g = g = self.game().village()
        self.make_heathen(g, 3)
        g.settle()
        mask = g.mask(3)
        before = self.faith(g, 3)
        self.assertEqual(g.change(3), 1)
        g.settle()
        self.assertEqual(g.mask(3), mask)
        self.assertEqual(g.p.u32(g.record(3) + g.g["sex"]), MALE)
        self.assertEqual(self.faith(g, 3), before, "the faction, selectors, faith and role untouched")

    def test_a_waiting_kept_mask_goes_with_them(self):
        """Heathens Keep Their Masks When Converted: the mask handed over waits (VvfpMaskKeep answers 2); a sex
        change meanwhile, then the load puts it on them."""
        self.g = g = self.game().village()
        g.p.put32(g.record(2) + 0x1CF0, 10)
        before = self.faith(g, 2)
        self.assertEqual(g.p.export("VvfpMaskKeep", g.record(2), BLUE), 2)
        self.assertEqual(g.change(2), 1)
        g.settle()
        self.assertEqual(g.mask(2), BLUE)
        self.assertEqual(g.p.u32(g.record(2) + g.g["sex"]), FEMALE)
        self.assertEqual(self.faith(g, 2), before)


@unittest.skipUnless(have(5), "unicorn/pefile, the stock VV5 or the DLL is missing")
class GuardiansOn(GuardiansCases, unittest.TestCase):
    ON = True


@unittest.skipUnless(have(5), "unicorn/pefile, the stock VV5 or the DLL is missing")
class GuardiansOff(GuardiansCases, unittest.TestCase):
    ON = False


@unittest.skipUnless(have(5), "unicorn/pefile, the stock VV5 or the DLL is missing")
class OnAndOffAlike(unittest.TestCase):
    def test_the_same_records_and_masks_either_way(self):
        results = []
        for on in (True, False):
            case = GuardiansCases()
            case.ON = on
            g = case.game().village()
            case.make_heathen(g, 3)
            g.settle()
            g.put_mask(1, RED)
            g.change(1)
            g.change(3)
            g.settle()
            results.append(([g.mask(i) for i in range(4)],
                            [g.p.read(g.record(i), g.g["stride"]) for i in range(4)]))
        self.assertEqual(results[0], results[1])


@unittest.skipUnless(have_compiler(), "the MSVC x86 compiler or PowerShell is missing")
class GuardiansChangeSexButton(unittest.TestCase):
    def test_offered_for_a_heathen_and_a_believer_faith_untouched(self):
        run_button_harness(self, 5)


if __name__ == "__main__":
    unittest.main()
