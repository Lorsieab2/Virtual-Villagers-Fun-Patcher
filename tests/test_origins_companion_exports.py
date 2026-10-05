"""A New Home's and The Tree of Life's Origins companions export only what
something resolves.  (The Lost Children's has its own pin in
test_vv2_companion_exports.py.)

Both used to ship a decorated "_Name@N" twin of every export, which came from
__declspec(dllexport) on top of the .def and that nothing ever resolved.  They
also exported functions that only the DLL itself calls, and VV4 exported four
names that no stub ever asked for.  Each export table is pinned here to exactly
what the executable's stubs ask for -- and VvfpStartup, which "VVFP
Startup.dll" asks for at game start: names passed to GetProcAddress, plus, for
VV4, the explicit ordinals its stubs pass (100-104, 110 and 114).  With the stock
executable present, every public patch is rendered in every public mode, and
each test checks that every by-name export is resolved and no removed name
appears.

The sourceless legacy assets/origins/VVFP Origins Icons.dll was installed by no
public patch (VV3 and VV5 install their own companions under that name). It is
gone, and nothing may ship or list it again.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

STOCK = ROOT / "research" / "stock-executables"

CASES = {
    "vv1": {
        "dll": ROOT / "assets" / "origins" / "VVFP VV1 Origins Icons.dll",
        "exe": STOCK / "Virtual Villagers - A New Home.exe",
        "by_name": {
            "ShowOriginsAgeResult", "ShowOriginsAppearanceForAll",
            "ShowOriginsAppearancePicker", "ShowOriginsCureResult",
            "ShowOriginsEqualDivisionResult", "ShowOriginsMasteryResult",
            "ShowOriginsPermanentChangeConfirm", "ShowOriginsRowMessage",
            "ShowOriginsTimeWarp", "ShowOriginsUpgradeMenu",
            "ShowOriginsUpgradeMenuState", "ShowOriginsVillageWideResult",
            "Vv1Born", "Vv1DoublerRestore", "Vv1DoublerSave",
            "Vv1DrawPortraitMask", "Vv1GetMaskSprite", "Vv1MaskRestore",
            "Vv1MaskTick", "Vv1NumberKeysUpdate", "Vv1SortStep",
        },
        "by_ordinal": {},
        # Only Change Appearance for All calls it, inside the DLL.
        "removed": {"Vv1MaskApplyDistribution"},
    },
    "vv4": {
        "dll": ROOT / "assets" / "origins" / "VVFP VV4 Origins Icons.dll",
        "exe": STOCK / "Virtual Villagers - The Tree of Life.exe",
        "by_name": {
            "ShowOriginsAppearancePicker", "ShowOriginsCureResult",
            "ShowOriginsUpgradeMenuState", "ShowOriginsUpgradeMessage",
            "ShowOriginsVillageWideResult", "ShowVv4TimeWarp",
        },
        # ConfirmOriginsVillageWide (100); the Tech-menu stub's ebx+92 for rows
        # 9-12 (101-104); the mask resolve cave's 110 and 114.
        "by_ordinal": {
            100: "ConfirmOriginsVillageWide",
            101: "ApplyVV4CompleteCollections",
            102: "ApplyVV4ResetCollections",
            103: "ApplyVV4EqualDivisionParenting",
            104: "ApplyVV4EqualDivisionNoParenting",
            110: "Vv4MaskCacheSurface",
            114: "Vv4MaskGetForRecord",
        },
        "removed": {
            "ShowOriginsUpgradeMenu", "ShowOriginsVillageWideResult@20",
            "Vv4MaskDraw", "Vv4MaskDrawRecord", "ShowVv4AppearanceForAll",
        },
    },
}


# Resolved by "VVFP Startup.dll" at game start (native/vvfp_startup), not by
# the executable, so it is in no render.
BY_STARTUP_LOADER = {"VvfpStartup"}


def _exports(path: Path) -> dict[str, int]:
    pe = pefile.PE(str(path), fast_load=True)
    pe.parse_data_directories(
        directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]]
    )
    return {e.name.decode(): e.ordinal for e in pe.DIRECTORY_ENTRY_EXPORT.symbols}


class OriginsCompanionExportTests(unittest.TestCase):
    def test_export_tables_are_exactly_what_the_executables_resolve(self) -> None:
        for game, case in CASES.items():
            with self.subTest(game=game):
                exports = _exports(case["dll"])
                self.assertEqual(
                    set(exports),
                    case["by_name"] | set(case["by_ordinal"].values()) | BY_STARTUP_LOADER,
                )
                for ordinal, name in case["by_ordinal"].items():
                    self.assertEqual(exports[name], ordinal, name)
                self.assertFalse(
                    [n for n in exports if n.startswith("_") or "@" in n],
                    "a decorated twin is back: something is __declspec(dllexport) again",
                )

    def test_every_render_resolves_each_name_and_none_removed(self) -> None:
        import vv_fun_patcher as vfp

        for game, case in CASES.items():
            if not case["exe"].is_file():
                self.skipTest(f"stock executable not present: {case['exe']}")
            build = next(b for b in vfp.load_builds() if b.id == game)
            patches = tuple(
                p.id for p in vfp.load_public_fun_patches() if p.game_id == game
            )
            for mode in sorted(vfp._PUBLIC_PATCH_MODES):
                with self.subTest(game=game, mode=mode):
                    image = bytes(
                        vfp.render_patched_bytes(case["exe"], build, mode, patches)[0]
                    )
                    for name in case["by_name"]:
                        self.assertIn(name.encode() + b"\0", image, name)
                    for name in case["removed"] | set(case["by_ordinal"].values()):
                        self.assertNotIn(name.encode() + b"\0", image, name)
                    self.assertIsNone(
                        re.search(rb"_(?:ShowOrigins|Vv[14]|ApplyVV4|ShowVv4|ConfirmOrigins)\w*@\d", image)
                    )

    def test_the_sourceless_legacy_companion_is_gone(self) -> None:
        self.assertFalse((ROOT / "assets" / "origins" / "VVFP Origins Icons.dll").exists())
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertNotIn("assets/origins/VVFP Origins Icons.dll", release)
        for path in sorted((ROOT / "data").glob("*.json")):
            with self.subTest(manifest=path.name):
                self.assertNotIn(
                    '"source": "assets/origins/VVFP Origins Icons.dll"',
                    path.read_text(encoding="utf-8"),
                )


if __name__ == "__main__":
    unittest.main()
