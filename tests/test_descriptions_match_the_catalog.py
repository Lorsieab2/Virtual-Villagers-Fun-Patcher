"""Patch descriptions must describe the patcher the player actually has.

Three defects of this kind were found in one audit:

* Twenty-one descriptions said "**Requires Enable Origins-Exclusive
  Features**, whose companion loads this one; without it ... runs unchanged".
  That base is internal: it has no tickbox (load_public_fun_patches leaves it
  out) and resolve_fun_patch_ids adds it whenever a selected patch depends on
  it. So the player was told about a checkbox that does not exist and a
  "without it" case that cannot happen, and was not told the visible side
  effect -- selecting one of these patches alone installs the whole base,
  Upgrades buttons included.
* The five Births and Conceptions logs were each described differently, and
  said the log sat "beside the game executable" when it is written beside the
  saves; VV3-VV5 also said parentage "cannot be recovered" from a child whose
  own record holds both parents, and none of VV2-VV5 mentioned the Birth
  records they write. The owner's rule is that all five games ship the same
  log format, so the player-facing part is now one shared text.
* Show Parents named a sidecar file and folder that no build writes.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_fun_patcher as patcher  # noqa: E402
from origins_base_text import ORIGINS_BASE_SENTENCE  # noqa: E402
from parentage_log_text import PLAYER_LOG_DESCRIPTION  # noqa: E402


class DescriptionsMatchTheCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.public = patcher.load_public_fun_patches()

    def test_no_description_names_the_hidden_origins_base_as_a_tickbox(self) -> None:
        public_names = {patch.name for patch in self.public}
        base_names = {
            patch.name
            for patch in patcher.load_fun_patches()
            if patch.id in patcher.INTERNAL_ORIGINS_BASE_FEATURE_ID_SET
        }
        # The internal base really is absent from the tickable catalog...
        self.assertTrue(base_names)
        self.assertFalse(public_names & base_names)
        # ...so no public description may send the player looking for it.
        offenders = [
            patch.id
            for patch in self.public
            if "Enable Origins-Exclusive Features" in patch.raw.get("description", "")
        ]
        self.assertEqual(offenders, [])

    def test_every_patch_that_pulls_in_the_base_says_so_and_names_the_side_effect(self) -> None:
        for patch in self.public:
            if patch.id in patcher.PUBLIC_ORIGINS_VILLAGE_WIDE_PATCH_ID_SET:
                continue            # these ARE the Origins upgrades rows
            dependencies = patch.raw.get("dependencies") or []
            if not set(dependencies) & patcher.INTERNAL_ORIGINS_BASE_FEATURE_ID_SET:
                continue
            with self.subTest(patch=patch.id):
                description = patch.raw["description"]
                self.assertIn("Origins-exclusive base", description)
                self.assertIn("adds the Origins Upgrades buttons", description)

    def test_the_shared_origins_sentence_is_used_verbatim(self) -> None:
        users = [
            patch.id for patch in self.public
            if ORIGINS_BASE_SENTENCE in patch.raw.get("description", "")
        ]
        # Builders Fix Huts x5, Healers Study x2, Pathfinding x2, the three
        # lesson caps, Number Keys, Sort By, Watering and Show Parents.
        self.assertGreaterEqual(len(users), 16, users)

    def test_all_five_parentage_logs_are_described_the_same_way(self) -> None:
        for game in range(1, 6):
            manifest = json.loads(
                (ROOT / "data" / f"vv{game}_parentage_feature.json").read_text(encoding="utf-8")
            )
            row = next(
                feature for feature in manifest["features"]
                if feature["id"] == f"vv{game}_write_parentage_log"
            )
            description = row["description"]
            with self.subTest(game=game):
                self.assertTrue(
                    description.startswith(PLAYER_LOG_DESCRIPTION.format(game_number=game)),
                    description[:200],
                )
                self.assertIn(
                    "Virtual Villagers Fun Patcher Logs\\Births and Conceptions", description
                )
                self.assertIn("Each Birth record", description)
                self.assertIn("256 Conception records", description)
                self.assertNotIn("beside the game executable", description)
                if game > 1:
                    # VV2-VV5 keep both parents on the child's own record.
                    self.assertNotIn("cannot be recovered", description)
                    self.assertIn("both parents on the child's own record", description)
                # The unlabelled-log caveat without Village Statistics.
                statistics = next(
                    entry for entry in row["needs_on"]
                    if entry["id"] == f"vv{game}_write_village_statistics"
                )
                self.assertIn("the log first appears with its first record", statistics["for"])

    def test_the_log_folder_is_the_one_the_companion_writes(self) -> None:
        source = (ROOT / "native" / "parentage_export" / "parentage_export.c").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'L"Virtual Villagers Fun Patcher Logs\\\\Births and Conceptions"', source
        )
        self.assertIn("RECORDS_PER_FILE = 256", source)

    def test_show_parents_names_the_sidecar_the_companion_writes(self) -> None:
        manifest = json.loads(
            (ROOT / "data" / "vv1_show_parents_feature.json").read_text(encoding="utf-8")
        )
        source = (ROOT / "native" / "vv1_parentage" / "vv1_parentage.c").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'wsprintfA(name, "Virtual Villagers 1 Parentage Records - Save %u.dat"',
            source,
        )
        self.assertIn("VV_DATA_SUB_PARENTAGE", source)
        # The folder the companion writes to since the save folders' new names (save_layout.h).
        layout = (ROOT / "native" / "shared" / "save_layout.h").read_text(encoding="utf-8")
        self.assertIn('#define VV_PARENTS_VV1_DIR VV_DATA_DIR L"\\\\Parents (A New Home)"', layout)
        self.assertIn(
            "'Virtual Villagers 1 Parentage Records - Save <slot>.dat' in the "
            "'Virtual Villagers Fun Patcher Data\\Parents (A New Home)' folder",
            manifest["description"],
        )
        self.assertNotIn("vv1_parents_", manifest["description"])


if __name__ == "__main__":
    unittest.main()
