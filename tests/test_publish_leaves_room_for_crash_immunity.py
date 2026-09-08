"""Every game must still publish with all of its features selected.

`_require_name_crash_immunity` runs at the end of `apply_patch` and needs a run
of free bytes in an executable section to hold the wrapper that makes a renamed
build boot. It raises rather than degrading, deliberately: its own docstring
says a missing cave "is not a harmless omission: it leaves the exact crash class
this finalizer is responsible for in the build."

That makes cave space a shared resource with a reserved share, and a feature can
consume it without ever overlapping another feature's claim. The overlap check
does not notice, because there is no overlap -- the space is simply gone by the
time the finalizer looks.

Only VV2 was covered before this, incidentally, through
test_vv2_origins_containment. A feature that displaced the reserve in any of the
other four games would have shipped with a green suite.

Two details make this hard to catch by hand, and both are why the test drives
`apply_patch` rather than anything cheaper:

  * the finalizer sizes its cave from the PUBLISHED basename, and `apply_patch`
    renames its output. A probe through `render_patched_bytes` keeps the input
    name, comes out shorter, and passes where the real path fails.
  * the reserve MOVES as features are applied. Asked about a stock image it
    reports a comfortable address that no feature wants; asked about the
    composed image it can report none at all.

So the only question worth asking is the one a player's build asks: with
everything selected, does it publish?
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    apply_patch,
    load_builds,
    load_fun_patches,
)

STOCK = ROOT / "research" / "stock-executables"

# Candidate payloads are research artefacts rather than shipped selections, and
# several are mutually exclusive by construction, so selecting them together
# proves nothing about a build a player can make.
EXCLUDED_SUFFIX = "_candidate"


class PublishLeavesRoomForCrashImmunityTests(unittest.TestCase):
    def _selectable(self, game_id: str) -> list[str]:
        """Every feature that patches the executable, and only those.

        Asset-swap features replace files that live beside the game rather than
        bytes inside it, so they need an installed game directory and fail on a
        bare copy of the executable with a preimage mismatch. Including them
        made this test fail for a reason that has nothing to do with cave space,
        which would have hidden the thing it exists to measure. They also
        consume no cave, so excluding them costs the measurement nothing.

        The marker is `preimage_sha256` on a companion entry, not the presence
        of companion files: a DLL that is merely ADDED alongside the executable
        carries destination, source and sha256, while a file being REPLACED also
        pins the bytes it expects to find. Only the latter needs the game
        installed. An earlier version of this filter guessed at manifest keys
        that do not exist, which excluded nothing and left the test still
        failing for the wrong reason.
        """
        selectable = []
        for patch in load_fun_patches():
            if patch.game_id != game_id or patch.id.endswith(EXCLUDED_SUFFIX):
                continue
            raw = patch.raw if hasattr(patch, "raw") else {}
            companions = raw.get("companion_files") or []
            if any(entry.get("preimage_sha256") for entry in companions):
                continue
            selectable.append(patch.id)
        return selectable

    def _publish(self, build, source: Path, selected: list[str]) -> None:
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / build.title
            folder.mkdir()
            copied = folder / build.input_name
            shutil.copyfile(source, copied)
            # apply_patch, not render_patched_bytes: the finalizer sizes its
            # cave from the renamed output, so a path that does not rename
            # cannot reproduce a real failure here.
            apply_patch(copied, "collection_progression", fun_patch_ids=selected)

    def test_every_game_publishes_with_all_features_selected(self) -> None:
        builds = {build.id: build for build in load_builds()}
        for game_id in ("vv1", "vv2", "vv3", "vv4", "vv5"):
            with self.subTest(game=game_id):
                build = builds.get(game_id)
                self.assertIsNotNone(build, f"{game_id} is missing from builds")
                source = STOCK / build.input_name
                if not source.is_file():
                    self.skipTest(f"stock executable not available: {source.name}")
                selected = self._selectable(game_id)
                self.assertTrue(
                    selected, f"{game_id} has no selectable features to compose"
                )
                self._publish(build, source, selected)

    def test_every_game_publishes_without_the_origins_features(self) -> None:
        """Selecting everything is the EASIEST case, not the hardest.

        The Origins features append a PE section, and the finalizer will happily
        put its wrapper there, so a build that includes them can absorb a new
        cave-resident feature without noticing. Deselect them and the reserve
        must come out of the stock executable's own cave, which is where the
        contention actually is.

        This is not hypothetical. A parentage hook drafted for VV2 published
        cleanly with everything selected and failed the moment Origins was
        deselected -- so the all-features test above passed while the feature it
        was written to catch went straight through it.
        """
        builds = {build.id: build for build in load_builds()}
        for game_id in ("vv1", "vv2", "vv3", "vv4", "vv5"):
            with self.subTest(game=game_id):
                build = builds.get(game_id)
                self.assertIsNotNone(build, f"{game_id} is missing from builds")
                source = STOCK / build.input_name
                if not source.is_file():
                    self.skipTest(f"stock executable not available: {source.name}")
                selected = [
                    feature_id
                    for feature_id in self._selectable(game_id)
                    if "origins" not in feature_id
                ]
                self.assertTrue(
                    selected, f"{game_id} has no non-Origins features to compose"
                )
                self._publish(build, source, selected)


if __name__ == "__main__":
    unittest.main()
