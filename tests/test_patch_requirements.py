"""Every patch description says, in bold, which other patches must be on.

The owner's rule: "put in the patch descriptions which patches need to be on
for other patches to work! (All games and all patches) (in Bold!!)".  The
sentence is derived from the manifests (``dependencies``, ``needs_on`` and
their reverse), shown under every description in the patcher in a bold font,
and written in bold into the transparency log, so a dependency cannot ship
without its sentence and the three places cannot disagree.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402


class PatchRequirementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public = patcher.load_public_fun_patches()
        cls.by_id = {p.id: p for p in cls.public}

    def text(self, patch_id: str) -> str:
        return patcher.patch_requirement_text(self.by_id[patch_id], self.public)

    def test_every_public_patch_in_every_game_has_a_requirement_sentence(self):
        games = {p.game_id for p in self.public}
        self.assertEqual(games, {"vv1", "vv2", "vv3", "vv4", "vv5"})
        for patch in self.public:
            text = self.text(patch.id)
            self.assertTrue(text.endswith("."), (patch.id, text))
            self.assertTrue(
                text.startswith(("Requires ", "Needs ")), (patch.id, text)
            )

    def test_needs_on_names_only_public_patches_of_the_same_game(self):
        for patch in self.public:
            for dependency_id, purpose in patcher._needs_on(patch):
                self.assertIn(dependency_id, self.by_id, (patch.id, dependency_id))
                self.assertEqual(self.by_id[dependency_id].game_id, patch.game_id)
                self.assertTrue(purpose.strip())

    def test_the_functional_links_between_the_vv1_rows_are_stated_both_ways(self):
        parents = self.text("vv1_show_parents")
        self.assertIn("Needs Write Births and Conceptions Log to Text File on for the father", parents)
        self.assertIn('"Birth" records', parents)
        log = self.text("vv1_write_parentage_log")
        self.assertIn("Needs Show Parents in Details Screen on for the \"Birth\" records", log)
        # The reverse is declared on both sides, so it is not repeated.
        self.assertEqual(log.count("Show Parents in Details Screen"), 1)
        self.assertEqual(parents.count("Write Births and Conceptions Log to Text File"), 1)
        stats = self.text("vv1_write_village_statistics")
        self.assertIn("Needs Show Parents in Details Screen on for the \"Parents:\" lines", stats)
        # ...and Show Parents tells the player the roster needs it.
        self.assertIn("Needed by Write Village Statistics to Text File for the \"Parents:\" lines", parents)

    def test_the_origins_base_is_never_presented_as_a_patch_to_tick(self):
        for patch_id in ("vv1_sort_by", "vv1_number_keys",
                         "vv3_origins_village_wide_upgrades", "vv5_origins_village_wide_upgrades"):
            text = self.text(patch_id)
            self.assertIn("Requires no other patch to be ticked; the Origins-exclusive base it runs on is included automatically.", text)
            self.assertNotIn("Requires Enable Origins", text)
        # VV2's parentage log now also carries the header caveat, so the
        # Origins base is a trailing sentence rather than a standalone one.
        vv2_log = self.text("vv2_write_parentage_log")
        self.assertIn(
            "The Origins-exclusive base it runs on is included automatically.", vv2_log
        )
        self.assertNotIn("Requires Enable Origins", vv2_log)
        for patch in self.public:
            self.assertNotRegex(self.text(patch.id), r"\bvv[1-5]_", (patch.id, self.text(patch.id)))

    def test_a_patch_with_no_links_says_so(self):
        self.assertEqual(self.text("vv3_rare_collectible_retry"), "Requires no other patch to be ticked.")
        self.assertEqual(self.text("vv1_write_parentage_log").count("Requires no other"), 0)

    def test_hard_dependencies_between_public_rows_are_stated_both_ways(self):
        # No public row hard-depends on another today; the wording is pinned
        # through a synthetic pair so the day one does, the sentence is right.
        a = patcher.FunPatch({"id": "x_a", "game_id": "vv1", "name": "Alpha", "description": ""})
        b = patcher.FunPatch({"id": "x_b", "game_id": "vv1", "name": "Beta", "description": "", "dependencies": ["x_a"]})
        catalog = [a, b]
        self.assertEqual(
            patcher.patch_requirements(b, catalog),
            ("Requires Alpha: ticking this ticks it, and unticking it unticks this.",),
        )
        self.assertEqual(
            patcher.patch_requirements(a, catalog),
            ("Requires no other patch to be ticked.", "Needed by Beta: unticking this unticks it."),
        )

    def test_a_needs_on_entry_naming_an_unknown_or_foreign_patch_fails_closed(self):
        a = patcher.FunPatch({"id": "x_a", "game_id": "vv1", "name": "Alpha", "description": "",
                              "needs_on": [{"id": "nope", "for": "anything"}]})
        with self.assertRaises(patcher.PatcherError):
            patcher.patch_requirements(a, [a])
        c = patcher.FunPatch({"id": "x_c", "game_id": "vv2", "name": "Gamma", "description": ""})
        a2 = patcher.FunPatch({"id": "x_a", "game_id": "vv1", "name": "Alpha", "description": "",
                               "needs_on": [{"id": "x_c", "for": "anything"}]})
        with self.assertRaises(patcher.PatcherError):
            patcher.patch_requirements(a2, [a2, c])
        bad = patcher.FunPatch({"id": "x_a", "game_id": "vv1", "name": "Alpha", "description": "",
                                "needs_on": [{"id": "x_c"}]})
        with self.assertRaises(patcher.PatcherError):
            patcher._needs_on(bad)

    def test_the_patcher_shows_the_sentence_under_every_description_in_bold(self):
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertIn("patch_requirement_text,", source)
        self.assertIn('requirement_font.configure(weight="bold")', source)
        # Both chooser loops (shared rows and per-game rows) render it.
        self.assertEqual(source.count("text=patch_requirement_text(patch, self.fun_patches)"), 2)
        self.assertEqual(source.count("font=requirement_font,"), 2)
        # ...right after each description label.
        for match in re.finditer(r"text=patch\.description, wraplength=620\)", source):
            after = source[match.end(): match.end() + 400]
            self.assertIn("patch_requirement_text(patch, self.fun_patches)", after)

    def test_the_transparency_log_carries_the_same_sentence_in_bold(self):
        doc = (ROOT / "docs" / "transparency-log.md").read_text(encoding="utf-8")
        catalog = patcher.load_fun_patches()
        for patch in self.public:
            sentence = "**" + patcher.patch_requirement_text(patch, catalog) + "**"
            self.assertIn(sentence, doc, patch.id)
        generator = (ROOT / "scripts" / "generate_transparency_docs.py").read_text(encoding="utf-8")
        self.assertIn('lines.append("**" + patch_requirement_text(patch, patches) + "**")', generator)

    def test_the_manifests_carry_the_needs_on_entries(self):
        parents = json.loads((ROOT / "data" / "vv1_show_parents_feature.json").read_text(encoding="utf-8"))
        self.assertEqual([e["id"] for e in parents["needs_on"]], ["vv1_write_parentage_log"])
        log = json.loads((ROOT / "data" / "vv1_parentage_feature.json").read_text(encoding="utf-8"))
        vv1 = [f for f in log["features"] if f["id"] == "vv1_write_parentage_log"][0]
        # The header caveat is stated in the patcher for every game, in bold:
        # the records are correct without Village Statistics, but the village
        # and savegame header at the top of the log is published by it.
        self.assertEqual(
            [e["id"] for e in vv1["needs_on"]],
            ["vv1_write_village_statistics", "vv1_show_parents"],
        )
        for game in ("vv2", "vv3", "vv4", "vv5"):
            other = json.loads(
                (ROOT / "data" / (game + "_parentage_feature.json")).read_text(encoding="utf-8")
            )
            row = [f for f in other["features"] if f["id"] == game + "_write_parentage_log"][0]
            self.assertEqual(
                [e["id"] for e in row["needs_on"]], [game + "_write_village_statistics"]
            )
        stats = json.loads((ROOT / "data" / "statistics_features.json").read_text(encoding="utf-8"))
        by = {f["id"]: f for f in stats["features"]}
        self.assertEqual([e["id"] for e in by["vv1_write_village_statistics"]["needs_on"]], ["vv1_show_parents"])
        for game in ("vv2", "vv3", "vv4", "vv5"):
            self.assertEqual(by[f"{game}_write_village_statistics"].get("needs_on", []), [])

    def test_the_readme_rows_state_the_links_in_bold(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("**Needs Write Births and Conceptions Log to Text File on for the father", readme)
        self.assertIn("**Needs Show Parents in Details Screen on for the \"Parents:\" lines", readme)


if __name__ == "__main__":
    unittest.main()
