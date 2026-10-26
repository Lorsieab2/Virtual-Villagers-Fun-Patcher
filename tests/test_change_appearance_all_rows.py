"""Change Appearance offers every head and every outfit, in all five games.

The owner: "all outfits and heads should be selectable in Change Appearance
regardless."  Regardless of sex and of age, and including the rows no villager
is born with -- A New Home's Golden Child head and body 19, The Secret City's
Tribal Chief body 29, and body 29 in The Tree of Life and New Believers, whose
creation rolls only rand(29).

native/shared/change_appearance_harness.c compiles each game's Origins
companion source unchanged and drives its real Change Appearance dialog
procedure with the arrow buttons' own commands: from row 0 the left arrows
choose the last head and body rows, from the second-to-last the right arrows
reach them, and past them the arrows wrap to 0 -- for a man and a woman, a
child, an adult and an elder.  For The Lost Children and New Believers the
chooser export itself runs, so the written record (VV2) and the values handed
back to the exe (VV5) are checked; A New Home and The Tree of Life write the
record from the dialog on every arrow press.  The static checks below cover
what the harness cannot run without the game's memory: The Secret City's
export and the exe caves that write what the choosers return.
"""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build_change_appearance_harness.ps1"
HARNESS = ROOT / "native" / "shared" / "change_appearance_harness.c"
CL = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC"
          r"\14.51.36231\bin\Hostx64\x86\cl.exe")

ROWS = {1: 20, 2: 30, 3: 30, 4: 30, 5: 30}
SOURCES = {
    1: "native/vv1_origins_icons/vv1_origins_icons.c",
    2: "native/vv2_origins_icons/vv2_origins_icons.c",
    3: "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c",
    4: "native/vv4_origins_icons/vv4_origins_icons.c",
    5: "native/vv5_task9_origins/vv5_task9_origins.c",
}


def _source(game: int) -> str:
    return (ROOT / SOURCES[game]).read_text(encoding="utf-8")


def _between(text: str, start: str, end: str) -> str:
    body = text[text.index(start):]
    return body[:body.index(end)]


class TheHarness(unittest.TestCase):
    def test_it_compiles_each_game_source_unchanged(self) -> None:
        text = HARNESS.read_text(encoding="utf-8")
        for game, source in SOURCES.items():
            with self.subTest(game=game):
                self.assertIn(f'#include "../{source.removeprefix("native/")}"', text)
                self.assertIn(f"#if HARNESS_GAME == {game}" if game == 1 else
                              f"#elif HARNESS_GAME == {game}", text)
        # The last rows are the art's, written down here, not read from the macros under test.
        self.assertIn("#define H_HEADS 20\n#define H_BODIES 20", text)
        self.assertEqual(text.count("#define H_HEADS 30\n#define H_BODIES 30"), 4)
        self.assertIn("static const int H_AGES[3] = { 100, 600, 1200 };", text)

    @unittest.skipUnless(CL.exists(), "the 32-bit MSVC toolchain is not installed")
    def test_every_game_chooses_and_writes_the_last_rows(self) -> None:
        # One game at a time, one process at a time.
        for game, rows in ROWS.items():
            with self.subTest(game=game):
                run = subprocess.run(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(BUILD),
                     "-Games", str(game)],
                    capture_output=True, text=True, timeout=600,
                )
                out = run.stdout + run.stderr
                self.assertEqual(run.returncode, 0, out)
                self.assertIn(f"game {game}: {rows} heads, {rows} bodies; 24 checks, 0 failures", out)
                self.assertNotIn("FAIL", out)


class TheWritesAreNotClamped(unittest.TestCase):
    def test_vv1_and_vv4_size_the_chooser_to_the_art_for_everyone(self) -> None:
        vv1 = _between(_source(1), "int __stdcall ShowOriginsAppearancePicker(", "\n}\n")
        self.assertIn("appearance_state.valid_count = 20;", vv1)
        vv4 = _between(_source(4), "int __stdcall ShowOriginsAppearancePicker(", "\n}\n")
        self.assertIn("appearance_state.head_count = VV_HEAD_COUNT;", vv4)
        self.assertIn("appearance_state.body_count = VV_BODY_COUNT;", vv4)

    def test_vv3_hands_the_chosen_rows_back_and_the_exe_writes_them(self) -> None:
        export = _between(_source(3), "__declspec(dllexport) int __stdcall ShowVV3AppearanceChooser(",
                          "\n}\n")
        self.assertIn("vv3_appearance_head = (head && *head >= 0 && *head < VV3_HEAD_COUNT) ? *head : 0;",
                      export)
        self.assertIn("vv3_appearance_body = (body && *body >= 0 && *body < VV3_BODY_COUNT) ? *body : 0;",
                      export)
        self.assertIn("*head = vv3_appearance_head;", export)
        self.assertIn("*body = vv3_appearance_body;", export)
        builder = (ROOT / "scripts" / "build_vv3_origins_feature.py").read_text(encoding="utf-8")
        cave = _between(builder, "change_appearance_code = assemble(", "CHANGE_APPEARANCE_VA,")
        after_call = cave[cave.index("call ebx"):]
        self.assertNotRegex(after_call, r"cmp\s+(dword ptr \[esp[^\]]*\]|eax),")
        self.assertIn("mov eax, dword ptr [esp]\n            mov dword ptr [esi + 0xDF0], eax", after_call)
        self.assertIn("mov eax, dword ptr [esp + 4]\n            mov dword ptr [esi + 0xDF4], eax", after_call)

    def test_vv5_writes_the_rows_the_chooser_returns(self) -> None:
        builder = (ROOT / "scripts" / "build_vv5_task9_native_actions.py").read_text(encoding="utf-8")
        route = _between(builder, "def build_appearance(", "def build_appearance_all(")
        writes = route[route.index("appearance_changed:"):]
        self.assertIn("mov eax, dword ptr [ebp-0x1C]\n        mov dword ptr [esi+0x1BB8], eax", writes)
        self.assertIn("mov eax, dword ptr [ebp-0x20]\n        mov dword ptr [esi+0x1BBC], eax", writes)
        # Nothing in the router compares a head or body with a row limit.
        self.assertIsNone(re.search(r"cmp eax, (0x1[cdeCDE]|2[89]|30)\b", route))


if __name__ == "__main__":
    unittest.main()
