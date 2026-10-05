"""The Lost Children's Origins companion exports only what something resolves.

"VVFP VV2 Origins Icons.dll" is built from its own source plus the shared A New
Home source (native/vv1_origins_icons/vv1_origins_icons.c).  It used to ship
the shared file's A New Home exports, the decorated "_Name@N" twin of every
export, and Vv2MaskSyncVillage, which only Vv2MaskSweep calls -- none of which
the VV2 executable, another companion or a test ever resolves.  This pins the
export table to exactly the names the executable's stubs pass to
GetProcAddress, plus ShowVV2AppearanceForAll, which the Tech-menu dispatch
resolves by ordinal 100.  With the stock executable present it also renders
every public VV2 patch in every public mode and checks that each exported
name is really there, and that no removed name is.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

import pefile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DLL = ROOT / "assets" / "origins" / "VVFP VV2 Origins Icons.dll"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"

BY_NAME = {
    "ApplyVV2AgeToAll", "ApplyVV2Collections", "ApplyVV2EqualDivision",
    "ApplyVV2MasteryToAll", "ApplyVV2RunningToAll", "ConfirmVV2Upgrade",
    "GateVV2Barrel", "GateVV2BarrelSilent", "ShowVV2AppearanceChooser",
    "ShowVV2CureResult", "ShowVV2TimeWarp", "ShowVV2UpgradeMenuState",
    "ShowVV2UpgradeResult", "Vv2ExtractAtlas", "Vv2MaskRestore",
    "Vv2MaskSaveSidecar", "Vv2MaskSweep",
}
BY_ORDINAL = {100: "ShowVV2AppearanceForAll"}
# Resolved by "VVFP Startup.dll" at game start, not by the executable.
BY_STARTUP_LOADER = {"VvfpStartup"}
# Names the companion no longer exports; the executable must not ask for them.
REMOVED = {
    "ShowOriginsAgeResult", "ShowOriginsAppearanceForAll",
    "ShowOriginsAppearancePicker", "ShowOriginsCureResult",
    "ShowOriginsEqualDivisionResult", "ShowOriginsMasteryResult",
    "ShowOriginsPermanentChangeConfirm", "ShowOriginsRowMessage",
    "ShowOriginsTimeWarp", "ShowOriginsUpgradeMenu",
    "ShowOriginsUpgradeMenuState", "ShowOriginsVillageWideResult",
    "Vv1Born", "Vv1DoublerRestore", "Vv1DoublerSave", "Vv1DrawPortraitMask",
    "Vv1GetMaskSprite", "Vv1MaskApplyDistribution", "Vv1MaskRestore",
    "Vv1MaskTick", "Vv1NumberKeysUpdate", "Vv1SortStep", "Vv2MaskSyncVillage",
}


def _exports() -> dict[str, int]:
    pe = pefile.PE(str(DLL), fast_load=True)
    pe.parse_data_directories(
        directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]]
    )
    return {e.name.decode(): e.ordinal for e in pe.DIRECTORY_ENTRY_EXPORT.symbols}


class Vv2CompanionExportTests(unittest.TestCase):
    def test_export_table_is_exactly_what_the_executable_resolves(self) -> None:
        exports = _exports()
        self.assertEqual(set(exports), BY_NAME | set(BY_ORDINAL.values()) | BY_STARTUP_LOADER)
        for ordinal, name in BY_ORDINAL.items():
            self.assertEqual(exports[name], ordinal)
        self.assertFalse(
            [name for name in exports if name.startswith("_") or "@" in name],
            "a decorated twin is back: something is __declspec(dllexport) again",
        )

    def test_every_render_resolves_each_name_and_none_removed(self) -> None:
        if not STOCK.is_file():
            self.skipTest(f"stock executable not present: {STOCK}")
        import vv_fun_patcher as vfp

        build = next(b for b in vfp.load_builds() if b.id == "vv2")
        patches = tuple(
            p.id for p in vfp.load_public_fun_patches() if p.game_id == "vv2"
        )
        for mode in sorted(vfp._PUBLIC_PATCH_MODES):
            with self.subTest(mode=mode):
                image = bytes(vfp.render_patched_bytes(STOCK, build, mode, patches)[0])
                for name in BY_NAME:
                    self.assertIn(name.encode() + b"\0", image, name)
                for name in REMOVED | {"ShowVV2AppearanceForAll"}:
                    self.assertNotIn(name.encode(), image, name)
                self.assertIsNone(re.search(
                    rb"_(?:ShowVV2|ApplyVV2|GateVV2|ConfirmVV2|Vv2)\w*@\d", image
                ))


if __name__ == "__main__":
    unittest.main()
