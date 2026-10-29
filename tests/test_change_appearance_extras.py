"""Change Appearance's Undo changes, Reset to original and Random buttons, and Change Appearance for All's
per-sex Head look rows, in all five games (native/shared/appearance_extras.h; the owner, 2026-10-28).

native/shared/change_appearance_extras_harness.c compiles each game's Origins companion source unchanged
and drives its real dialog procedures and exports: Undo writes and charges nothing; Reset to original sets
the known original (and only that villager's) and otherwise says "Original look not known" and changes
nothing; the randoms stay in the villager's sex, the game's colour groups and the window's pools; Cancel
writes nothing; a look-only OK is charged (The Lost Children) or handed on as a change; and the For All
look rows reach that sex's covered villagers only, Leave as is changes nothing, Random is only Young or
Old.  A New Home's and The Tree of Life's per-villager buttons read the mask table in the game's own
memory, so the harness runs only the shared rows there; their wiring is checked from the source below.

The checks below cover what a harness cannot: every template carries the controls, the price text, and
the paths that charge a look-only change.
"""
from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build_change_appearance_extras_harness.ps1"
CL = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC"
          r"\14.51.36231\bin\Hostx64\x86\cl.exe")

GAMES = {
    1: ("native/vv1_origins_icons/vv1_origins_icons", (203, 208), 204),
    2: ("native/vv2_origins_icons/vv2_origins_icons", (213, 218), 214),
    3: ("native/vv3_full_mastery_candidate/vv3_full_mastery_candidate", (213, 208), 214),
    4: ("native/vv4_origins_icons/vv4_origins_icons", (203, 208), 214),
    5: ("native/vv5_task9_origins/vv5_task9_origins", (203, 208), 214),
}
PER_VILLAGER = (3500, 3501, 3502, 3503, 3504, 3510, 3511, 3512, 3513, 3514)
FOR_ALL = (3500, 3501) + tuple(range(3520, 3526)) + tuple(range(3530, 3536))


def _dialog(rc: str, number: int) -> str:
    start = re.search(rf"(?m)^{number} DIALOGEX\b", rc)
    end = re.search(r"(?m)^END\b", rc[start.end():])
    return rc[start.start(): start.end() + end.start()]


def _ids(dialog: str) -> set[int]:
    return {int(m.group(1)) for m in re.finditer(r'"[^"]*",\s*(-?\d+),', dialog)}


class TheTemplates(unittest.TestCase):
    def test_every_window_has_its_buttons(self) -> None:
        for game, (stem, villager, every) in GAMES.items():
            rc = (ROOT / f"{stem}.rc").read_text(encoding="utf-8")
            for number in villager:
                with self.subTest(game=game, dialog=number):
                    ids = _ids(_dialog(rc, number))
                    self.assertTrue(set(PER_VILLAGER) <= ids, sorted(set(PER_VILLAGER) - ids))
            with self.subTest(game=game, dialog=number, look=True):
                self.assertIn(3505, _ids(_dialog(rc, villager[1])), "Random in the Head look row")
            with self.subTest(game=game, dialog=every):
                ids = _ids(_dialog(rc, every))
                self.assertTrue(set(FOR_ALL) <= ids, sorted(set(FOR_ALL) - ids))

    def test_the_head_look_is_not_free_any_more(self) -> None:
        for game, (stem, villager, _) in GAMES.items():
            with self.subTest(game=game):
                rc = (ROOT / f"{stem}.rc").read_text(encoding="utf-8")
                self.assertNotIn("(free)", rc)
                self.assertIn("for the head look too", _dialog(rc, villager[1]))

    def test_the_look_rows_offer_leave_auto_young_old_random(self) -> None:
        for game, (stem, _, every) in GAMES.items():
            dialog = _dialog((ROOT / f"{stem}.rc").read_text(encoding="utf-8"), every)
            for sex in (0, 1):
                with self.subTest(game=game, sex=sex):
                    labels = [re.search(rf'"([^"]*)",\s*{3520 + 10 * sex + k},', dialog).group(1) for k in range(5)]
                    self.assertEqual(labels, ["Leave as is", "Auto (old from 55)", "Young", "Old", "Random"])


class ThePrice(unittest.TestCase):
    def test_a_look_only_change_is_charged_in_every_game(self) -> None:
        src = {g: (ROOT / f"{stem}.c").read_text(encoding="utf-8") for g, (stem, _, _) in GAMES.items()}
        # A New Home: the look alone counts as a change, so the exe's charge runs (1).
        self.assertIn("changed = 1;", src[1][src[1].index("appearance_look != appearance_look_was"):])
        # The Lost Children charges inside its DLL, a look alone too.
        vv2 = src[2][src[2].index("int __stdcall ShowVV2AppearanceChooser"):]
        self.assertIn("if (same && !look_changed)", vv2)
        self.assertLess(vv2.index("vv2_appearance_look_api.set(2, record"), vv2.index("*tech -= vvfp_story_price"))
        # The Secret City: the look alone returns 1, and the exe's cave charges 5,000 on 1.
        self.assertIn("vv3_appearance_mask == orig_mask && !look_changed", src[3])
        # The Tree of Life: the look alone ends the dialog with 1 when kept.
        self.assertIn("EndDialog(window, appearance_keep_look(window) ? 1 : 0);", src[4])
        # New Believers: the router sees no change, so the chooser charges through the game's own routine.
        vv5 = src[5][src[5].index("static int appearance_charge_look_only(void) {"):]
        vv5 = vv5[: vv5.index("\n}\n")]
        self.assertIn("vvfp_story_price(5, 5000)", vv5)
        self.assertLess(vv5.index("appearance_look_api.set(5"), vv5.index("caf_charge(-price)"))
        self.assertIn("(void)appearance_charge_look_only();", src[5])

    def test_vv1_and_vv4_wire_every_button(self) -> None:
        for game in (1, 4):
            src = (ROOT / f"{GAMES[game][0]}.c").read_text(encoding="utf-8")
            body = src[src.index("static int appearance_extra(HWND window, unsigned int command)"):]
            body = body[: body.index("\n}\n")]
            for name in ("VVFP_AX_UNDO", "VVFP_AX_RESET", "VVFP_AX_RANDOM_HEAD", "VVFP_AX_HAIR_FIRST",
                         "VVFP_AX_RANDOM_BODY", "VVFP_AX_RANDOM_MASK", "VVFP_AX_RANDOM_LOOK", "appearance_revert()"):
                with self.subTest(game=game, name=name):
                    self.assertIn(name, body)


@unittest.skipUnless(os.name == "nt" and CL.is_file(), "needs Windows and the Visual Studio x86 compiler")
class TheHarness(unittest.TestCase):
    def test_every_game(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                run = subprocess.run(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BUILD),
                     "-Games", str(game)],
                    capture_output=True, text=True, timeout=600)
                out = run.stdout + run.stderr
                self.assertEqual(run.returncode, 0, out)
                self.assertRegex(out, rf"game {game}: \d+ checks, 0 failures")


if __name__ == "__main__":
    unittest.main()
