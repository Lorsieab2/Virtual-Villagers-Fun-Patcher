"""Every VV4 GDI+ user must start GDI+ itself.

VV4's appearance previews are drawn with GDI+, which has to be initialised by
`GdiplusStartup` before any `Gdip*` call will succeed.  It cannot be started
from `DllMain` (unsupported under the loader lock), so the companion starts it
lazily via `vv4_ensure_gdiplus()`.

That call used to live only in `ShowOriginsAppearancePicker`, the per-villager
dialog.  "Change Appearance for All" is a separate dialog that never goes
through that path, so opening it first left GDI+ uninitialised: every
`GdipCreateBitmapFromFile` failed and the Head and Body cells rendered blank.
The Mask cells showed "No change" because that is an early return taken before
any GDI+ call.

The rule this pins: any function that loads a GDI+ bitmap must have ensured
GDI+ first, so no future dialog can reintroduce the same gap.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "native" / "vv4_origins_icons" / "vv4_origins_icons.c"

ENSURE = "vv4_ensure_gdiplus()"
LOADER = "GdipCreateBitmapFromFile"


def _strip_comments(text: str) -> str:
    """Blank out comments so prose mentioning a symbol is not read as code."""
    return re.sub(r"/\*.*?\*/", lambda m: " " * len(m.group(0)), text, flags=re.S)


def _function_spans(text: str):
    """Yield (name, body) for each top-level C function definition."""
    pattern = re.compile(
        r"^(?:static\s+|__declspec\([^)]*\)\s+)*[A-Za-z_][\w *]*?"
        r"(?P<name>[A-Za-z_]\w*)\s*\([^;{]*\)\s*\{",
        re.M,
    )
    for match in pattern.finditer(text):
        start = text.index("{", match.end() - 1)
        depth = 0
        for index in range(start, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    yield match.group("name"), text[start:index + 1]
                    break


class VV4AppearanceGdiplusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = SOURCE.read_text(encoding="utf-8")
        # Comments are blanked first: this file's own explanatory comments name
        # both symbols, and matching those would test the prose, not the code.
        cls.functions = dict(_function_spans(_strip_comments(cls.source)))

    def test_the_helper_exists_and_is_idempotent(self) -> None:
        body = self.functions.get("vv4_ensure_gdiplus")
        self.assertIsNotNone(body, "vv4_ensure_gdiplus is missing")
        self.assertIn("gdiplus_token == 0", body,
                      "the guard must make repeated calls free")
        self.assertIn("GdiplusStartup", body)

    def test_gdiplus_is_never_started_from_dllmain(self) -> None:
        """GdiplusStartup under the loader lock can deadlock."""
        body = self.functions.get("DllMain")
        self.assertIsNotNone(body)
        self.assertNotIn("GdiplusStartup", body)
        self.assertNotIn(ENSURE, body)

    def test_every_bitmap_loader_ensures_gdiplus_first(self) -> None:
        loaders = {
            name: body
            for name, body in self.functions.items()
            if LOADER in body
        }
        self.assertTrue(
            loaders,
            "no GDI+ bitmap loads found; this test would pass vacuously",
        )
        for name, body in loaders.items():
            with self.subTest(function=name):
                self.assertIn(
                    ENSURE, body,
                    f"{name}() loads a GDI+ bitmap without ensuring GDI+ is "
                    f"started. Reaching it from a dialog that has not already "
                    f"initialised GDI+ renders a blank cell -- this is the "
                    f"'no body, head or mask options' bug in Change "
                    f"Appearance for All.",
                )
                self.assertLess(
                    body.index(ENSURE), body.index(LOADER),
                    f"{name}() ensures GDI+ only after loading a bitmap",
                )

    def test_the_head_body_cell_draw_is_covered(self) -> None:
        """The specific function behind the reported blank cells."""
        body = self.functions.get("appearance_draw_cell")
        self.assertIsNotNone(body)
        self.assertIn(ENSURE, body)


if __name__ == "__main__":
    unittest.main()
