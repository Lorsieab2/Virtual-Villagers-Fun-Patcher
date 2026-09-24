"""Every per-slot sidecar must migrate the name an older build wrote.

The data files moved into "Virtual Villagers Fun Patcher Data" when the
folders were spelled out. A player upgrading still has valid persisted state
under the loose pre-move name, so a loader that looks only at the new path
clears it: the village comes back unmasked, or without its parents, even
though the file is sitting right there beside the saves.

Five of the six sidecars migrated; VV4's masks did not, and the gap was
invisible because every other test builds a fresh install where no legacy
file exists. So this asks the question per sidecar, and asks it of the
SHIPPED DLL as well as the source -- the companions are prebuilt binaries, so
a fix that lives only in the .c file changes nothing a player receives.

The DLL check looks for the legacy STEM rather than a whole format string:
VV1 and VV2 reach it through a shared helper formatting "%s%d.dat" from the
stem, while VV4 inlines the complete name. Both are correct; only the
presence of the stem and of MoveFileA is common to them.
"""
from __future__ import annotations

import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

# source file -> [(legacy stem it must migrate, shipped DLL or None)]
SIDECARS = {
    "native/vv1_origins_icons/vv1_origins_icons.c": [
        ("vv1_masks_", "assets/origins/VVFP VV1 Origins Icons.dll"),
        ("vv1_doublers_", "assets/origins/VVFP VV1 Origins Icons.dll"),
    ],
    "native/vv1_parentage/vv1_parentage.c": [
        ("vv1_parents_", None),
    ],
    "native/vv2_origins_icons/vv2_origins_icons.c": [
        ("vv2_masks_", "assets/origins/VVFP VV2 Origins Icons.dll"),
    ],
    "native/vv3_full_mastery_candidate/vv3_full_mastery_candidate.c": [
        ("vvfp_masks_", None),
    ],
    "native/vv4_origins_icons/vv4_origins_icons.c": [
        ("vvfp_masks_", "assets/origins/VVFP VV4 Origins Icons.dll"),
    ],
    "native/vv5_task9_origins/vv5_task9_origins.c": [
        ("vvfp_masks_", None),
    ],
}

# VV2 calls the helper defined in vv1_origins_icons.c, which it includes.
SHARED_MIGRATION_SOURCE = "native/vv1_origins_icons/vv1_origins_icons.c"


def moves_a_file(text: str) -> bool:
    return re.search(r"MoveFileA\s*\(", text) is not None


class EverySidecarMigratesItsLegacyNameTests(unittest.TestCase):
    def test_every_named_source_exists(self) -> None:
        """Guard the guard: a renamed file would pass everything vacuously."""
        for rel in SIDECARS:
            with self.subTest(source=rel):
                self.assertTrue((ROOT / rel).is_file(), rel)

    def test_every_sidecar_source_names_and_moves_its_legacy_file(self) -> None:
        shared = (ROOT / SHARED_MIGRATION_SOURCE).read_text(
            encoding="utf-8", errors="replace"
        )
        for rel, entries in sorted(SIDECARS.items()):
            text = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
            for legacy, _dll in entries:
                with self.subTest(source=rel, legacy=legacy):
                    self.assertIn(
                        legacy,
                        text,
                        f"{rel} no longer names the legacy sidecar {legacy!r}, "
                        "so a player upgrading silently loses that state",
                    )
                    # Either this file moves it, or it uses the shared helper.
                    self.assertTrue(
                        moves_a_file(text) or moves_a_file(shared),
                        f"{rel} names {legacy!r} but nothing moves it",
                    )

    def test_the_shipped_dlls_carry_the_migration(self) -> None:
        """The companions ship prebuilt; a source-only fix reaches nobody."""
        for rel, entries in sorted(SIDECARS.items()):
            for legacy, dll_rel in entries:
                if dll_rel is None:
                    continue
                dll = ROOT / dll_rel
                with self.subTest(dll=dll_rel, legacy=legacy):
                    self.assertTrue(dll.is_file(), dll_rel)
                    data = dll.read_bytes()
                    # Bounded assertions: never put DLL bytes in a message.
                    self.assertTrue(
                        legacy.encode("ascii") in data,
                        f"{dll_rel} does not contain the legacy stem "
                        f"{legacy!r} -- the DLL predates the migration fix "
                        "and needs rebuilding",
                    )
                    self.assertTrue(
                        b"MoveFileA" in data,
                        f"{dll_rel} does not import MoveFileA, so it cannot "
                        "migrate anything",
                    )


if __name__ == "__main__":
    unittest.main()
