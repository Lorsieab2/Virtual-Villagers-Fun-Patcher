"""The "Check for Updates" link sits at the top and opens the project's GitHub page.

This replaces a much larger file that tested a version-comparison machine: the
patcher used to query GitHub's API for the newest tag, parse both versions,
order prereleases below their final release, and handle every way a network
call can fail. The owner asked for the link to simply open a page instead,
which deletes all of that -- first the releases page, and now (the owner's
later request) the base GitHub repository, whose page shows the latest
release. The build version is printed under the link so the comparison is the
player's to make.

What still matters, and is checked here:

  * The link is at the TOP, beside the description, not in a footer.
  * It opens this repository's base GitHub page, exactly the owner's URL.
  * The build version is visible next to it, or the link tells the player
    nothing actionable.
  * Nothing in the module reaches the network any more, so the patcher cannot
    hang or fail on a check it no longer performs.
"""
from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "src" / "vv_fun_patcher_gui.py"

sys.path.insert(0, str(ROOT / "src"))

from transparency import PATCHER_VERSION  # noqa: E402
from vv_fun_patcher_gui import RELEASES_PAGE  # noqa: E402

# The owner: the link goes to the base repository, not the releases page.
EXPECTED_RELEASES_PAGE = (
    "https://github.com/Lorsieab2/Virtual-Villagers-Fun-Patcher/"
)


class ReleasesLinkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = GUI.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)

    def _imported(self) -> set[str]:
        names: set[str] = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names.add(node.module.split(".")[0])
        return names

    def test_it_points_at_the_repository_page_exactly(self) -> None:
        """The owner supplied this URL directly; a near-miss is not good enough."""
        self.assertEqual(RELEASES_PAGE, EXPECTED_RELEASES_PAGE)

    def test_the_link_exists_and_opens_that_page(self) -> None:
        self.assertIn('"Check for updates", self._open_releases_page', self.source)
        handler = next(
            node
            for node in ast.walk(self.tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "_open_releases_page"
        )
        opens = [
            node
            for node in ast.walk(handler)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "open"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "webbrowser"
        ]
        self.assertEqual(len(opens), 1, "the link must open exactly one page")
        self.assertIsInstance(opens[0].args[0], ast.Name)
        self.assertEqual(opens[0].args[0].id, "RELEASES_PAGE")

    def test_the_link_is_at_the_top_beside_the_description(self) -> None:
        """Not in a footer under the status box, which is where it started."""
        blurb = self.source.find("blurb_row = ttk.Frame(outer)")
        self.assertNotEqual(blurb, -1, "the description row is gone")
        link = self.source.find('"Check for updates"')
        self.assertNotEqual(link, -1, "the link is gone")
        status = self.source.find("status_box = ttk.LabelFrame(")
        self.assertNotEqual(status, -1, "the status box is gone")
        self.assertLess(
            link, status,
            "the link must be built before the status box, i.e. at the top",
        )
        self.assertLess(
            abs(link - blurb), 900,
            "the link must sit with the description, not elsewhere",
        )

    def test_the_link_is_underlined_at_the_users_own_font_size(self) -> None:
        """Adopted from the VF2 patcher, which hit both of these.

        Without the underline the link reads as static text beside the version
        number and gets reported as missing while it is on screen and working.
        And a hardcoded point size shrinks it on any setup where TkDefaultFont
        has been enlarged for readability, while every label around it stays
        large -- the opposite of making it noticeable. So the font must be a
        copy of TkDefaultFont with underline turned on.
        """
        start = self.source.find("def _folder_link(")
        self.assertNotEqual(start, -1, "the link helper is gone")
        end = self.source.find("\n    def ", start + 1)
        helper = self.source[start:end]
        self.assertIn('tkfont.nametofont("TkDefaultFont").copy()', helper)
        self.assertIn("link_font.configure(underline=True)", helper)
        # Scoped to the link helper on purpose: headings elsewhere pick a
        # deliberate size, and that is a separate question from links, which
        # must track whatever size the user reads at.
        self.assertNotRegex(
            helper,
            r"font=\(\s*[\"']",
            "the link must not hardcode a font family or point size",
        )

    def test_the_link_is_packed_to_the_right(self) -> None:
        self.assertIn('update_box.pack(side="right"', self.source)

    def test_the_build_version_is_shown_next_to_the_link(self) -> None:
        """Without it the link cannot tell the player anything useful."""
        self.assertIn("ttk.Label(update_box, text=PATCHER_VERSION)", self.source)
        self.assertNotEqual(PATCHER_VERSION.strip(), "")

    def test_the_old_footer_is_gone(self) -> None:
        self.assertNotIn("footer = ttk.Frame(outer)", self.source)

    def test_nothing_reaches_the_network_any_more(self) -> None:
        """A link cannot hang; a version check could.

        The point of going direct is that there is no request left to time
        out, be rate limited, or return malformed JSON.
        """
        self.assertNotIn("urllib", self._imported())
        for gone in (
            "LATEST_RELEASE_API",
            "fetch_latest_release_tag",
            "parse_version",
            "UPDATE_CHECK_TIMEOUT_SECONDS",
        ):
            with self.subTest(symbol=gone):
                self.assertNotIn(gone, self.source)

    def test_no_third_party_package_is_imported(self) -> None:
        """The README promises the patcher needs no third-party packages."""
        # The patcher's own modules; vv_save_backup (Back Up Saves) and
        # vv_tribe_rename (Rename Tribe) and vv_log_tools (Check / Repair
        # Logs) and vv_how_to_use (the "?" guides) are held to the same
        # promise below; patcher_files (where the patcher's own files go)
        # imports only the standard library.
        own = {"vv_fun_patcher", "transparency", "vv_save_backup", "vv_tribe_rename", "vv_log_tools",
               "vv_log_additions", "vv_last_names", "vv_how_to_use", "patcher_files",
               "vv_genealogy", "vv_family_tree", "vv_gdiplus", "vv_line_colours", "vv_genealogy_window", "vv_tree_editor_tools",
               "vv_number_names", "vv_cut_names", "vv_save_layout", "vv_move_old_names", "vv_move_to_save_folders", "vv_villager_info",
               "vv_log_decisions", "vv_log_contradictions", "vv_answered_questions",
               "vv_startup_questions", "vv_graves", "vv_lost_titles", "vv1_parents_restore",
               "vv_corrupt_skills", "vv_reconcile", "vv_reconcile_view", "vv_titles_file", "vv_history_revision",
               "vv_vv2_totems", "vv_vv2_totem_store"}
        allowed = set(sys.stdlib_module_names) | own
        self.assertEqual(self._imported() - allowed, set())
        # Every one of them ships in the release zip: a module the patcher imports but the zip leaves
        # out stops it the moment that feature is opened (vv_save_layout, the v1.35.64 previews).
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        for module in sorted(own):
            with self.subTest(ships=module):
                self.assertIn(f'"src/{module}.py"', release)
        for module, may_import in (
            ("vv_save_backup", set()),
            # The patcher's data that names the village moves with a rename (function-level imports):
            # the answered questions' decisions, and The Lost Children's ElderTotems.dat.
            ("vv_tribe_rename", {"vv_save_backup", "vv_log_additions", "vv_log_decisions", "vv_vv2_totem_store"}),
            ("vv_log_tools", {"vv_save_backup", "vv_log_additions", "vv_last_names", "vv_genealogy",
                              "vv_cut_names", "vv_save_layout", "vv_log_decisions",
                              "vv_log_contradictions",
                              # Check Saves & Logs' NOTE for corrupted skill values (v1.35.70).
                              "vv_corrupt_skills",
                              "vv_reconcile",          # the read-only reconciliation (2026-10-11)
                              "vv_answered_questions",  # a real answer is never asked again (v1.35.80)
                              "vv_number_names",       # numbers a looks change gave, taken off (v1.35.80 update)
                              # PATCHER_VERSION: the repair copies are named for the running build.
                              "transparency"}),
            # The player's "Retroactively edit records?" No answers (vv_log_decisions).
            # ...and the save slot's own log folders (vv_save_layout).
            ("vv_log_additions", {"vv_log_tools", "vv_tribe_rename", "vv_genealogy", "vv_log_decisions",
                                  "vv_log_contradictions", "vv_save_layout", "vv_reconcile",
                                  "vv_answered_questions",     # answered questions held back (v1.35.80)
                                  "vv_number_names"}),         # numbers a looks change gave (v1.35.80 update)
            # The always-on read-only reconciliation of records, logs and files (the owner, 2026-10-11), and
            # the pickers' background run of it.
            ("vv_reconcile", {"vv_save_layout", "vv_log_tools", "vv_last_names", "vv_lost_titles",
                              "vv_log_additions", "vv_genealogy", "vv_tribe_rename", "vv_log_decisions",
                              "vv1_parents_restore", "vv_titles_file",
                              "vv_save_backup",        # a backup first, when an answer settles a custom title (v1.35.71)
                              "vv_answered_questions"}),   # the tree's "the same villager?" answers (v1.35.80 update)
            ("vv_reconcile_view", {"vv_reconcile"}),
            ("vv_log_decisions", {"vv_save_layout"}),
            # Answered questions (the owner, v1.35.80): kept in the Log Decisions file; the village header
            # and the questions they are matched with (function-level imports).
            ("vv_answered_questions", {"vv_log_decisions", "vv_log_additions", "vv_log_tools", "vv_tribe_rename",
                                       "vv_reconcile"}),
            # Records that contradict each other (Check / Repair Saves & Logs).
            ("vv_log_contradictions", {"vv_log_tools", "vv_save_layout", "vv_log_additions", "vv_last_names",
                                       "vv_log_decisions",     # the answers kept for the readers (audit66)
                                       "vv_answered_questions"}),   # ...and kept by their fact (v1.35.80)
            # Giving last names re-keys the Family Tree Maker's edits (vv_family_tree.renamed_keys).
            ("vv_last_names", {"vv_log_tools", "vv_save_backup", "vv_log_additions", "vv_family_tree",
                               "vv_tribe_rename", "vv_genealogy", "vv_save_layout",
                               "vv_startup_questions",
                               "vv_log_decisions",     # its renames kept for the answers (v1.35.80)
                               "vv_titles_file",       # two villagers of one title identity, told apart by the looks it keeps (v1.35.72)
                               "vv1_parents_restore"}),  # A New Home's parents file's departed list (v1.35.79)
            # The queue of questions the patcher asks when it opens (the owner, v1.35.66).
            ("vv_startup_questions", set()),
            ("patcher_files", set()),
            ("vv_how_to_use", set()),
            # The Family Tree Maker and the Village Matchmaker.
            # The tree shows a name the Villager Details screen cut by the logs' full name.
            # ...and A New Home's parents file under either folder name (vv_save_layout).
            ("vv_genealogy", {"vv_log_tools", "vv_last_names", "vv_log_additions", "vv_tribe_rename",
                              "vv_cut_names", "vv_save_layout", "vv_log_decisions", "vv_lost_titles", "vv_family_tree",
                              # An answered "I renamed them" joins the two records (v1.35.77); a
                              # function-level import, as vv_reconcile imports vv_genealogy.
                              "vv_reconcile",
                              # A New Home's parents file's departed list, read as Restore reads it (v1.35.79).
                              "vv1_parents_restore",
                              # "The same villager?" answers kept in Answered questions (v1.35.80 update).
                              "vv_answered_questions",
                              # The Family Tree's automatic marks: the graves' titles and each living villager's
                              # Custom title as the Villager Info tab reads them (function-level, 2026-10-22).
                              "vv_graves", "vv_villager_info"}),
            # Restoring cut names renames through Last Names; likes compare as vv_log_tools says (v1.35.68).
            ("vv_cut_names", {"vv_last_names", "vv_save_backup", "vv_log_additions", "vv_log_tools"}),
            # Fix grave information: the graves' fingerprints and writes through Last Names.
            ("vv_graves", {"vv_last_names", "vv_log_tools", "vv_save_backup", "vv_log_additions",
                           "vv_log_decisions"}),
            # Restoring titles a likes / dislikes change took away (the owner, v1.35.68).
            ("vv_lost_titles", {"vv_last_names", "vv_log_tools", "vv_save_backup", "vv_save_layout",
                                "vv_log_additions", "vv_titles_file"}),
            # The Custom Titles file, version 3 and 2 (native/shared/custom_titles.h; v1.35.70).
            ("vv_titles_file", set()),
            # Restore A New Home Parents: the copies of the parents file, the Repairs Made note.
            ("vv1_parents_restore", {"vv_log_tools", "vv_save_backup", "vv_save_layout"}),
            # Reset corrupted skill values (the owner, v1.35.70): the save through Last Names' reader and writer.
            ("vv_corrupt_skills", {"vv_last_names", "vv_log_tools", "vv_save_backup", "vv_tribe_rename",
                                   "vv_save_layout"}),
            # The Lost Children's Esteemed Elders' totems (the owner, 2026-10-19): the save through Last
            # Names' reader and writer, the Deaths log's elders, the village header as Reset corrupted
            # skill values reads it.
            ("vv_vv2_totems", {"vv_last_names", "vv_log_tools", "vv_save_backup", "vv_log_additions",
                               "vv_corrupt_skills", "vv_save_layout",
                               # Its renamed-answer check reads the reconciliation answers, as a
                               # function-level import (the same as vv_genealogy's).
                               "vv_reconcile",
                               # the patcher's own renames kept in the Log Decisions file (v1.35.80)
                               "vv_log_decisions",
                               # ElderTotems.dat, when the save keeps its totems there (function-level).
                               "vv_vv2_totem_store"}),
            ("vv_vv2_totem_store", {"vv_last_names", "vv_log_tools", "vv_save_backup", "vv_save_layout",
                                    "vv_vv2_totems",
                                    # the tribe's name binds a file of a village with no villager left
                                    # (function-level, as vv_corrupt_skills's)
                                    "vv_tribe_rename"}),
            ("vv_family_tree", {"vv_genealogy", "vv_log_tools", "vv_gdiplus", "vv_save_layout", "vv_line_colours"}),
            ("vv_gdiplus", {"vv_family_tree"}),
            ("vv_line_colours", {"vv_family_tree", "vv_gdiplus"}),
            ("vv_genealogy_window", {"vv_family_tree", "vv_gdiplus", "vv_line_colours", "vv_genealogy", "vv_save_backup",
                                     "vv_tribe_rename", "vv_tree_editor_tools", "vv_last_names", "vv_log_tools",
                                     "vv_number_names", "vv_villager_info", "vv_reconcile_view",
                                     "vv_history_revision",      # Hide villagers not in the current save (v1.35.73)
                                     "vv_answered_questions"}),  # "the same villager?" asked in the tree (v1.35.80 update)
            # Remove a restarted tribe's villagers from the history (the owner, v1.35.73).
            ("vv_history_revision", {"vv_log_tools", "vv_log_additions", "vv_reconcile", "vv_save_backup"}),
            # The Family Tree Maker's Villager Info tab (the owner, 2026-10-10).
            ("vv_villager_info", {"vv_family_tree", "vv_genealogy", "vv_last_names",
                                 "vv_save_layout", "vv_log_additions", "vv_titles_file"}),
            # Number Duplicate Names renames through Last Names; its Repairs Made record names the tribe
            # as the save does (vv_tribe_rename).
            ("vv_number_names", {"vv_genealogy", "vv_last_names", "vv_save_backup", "vv_log_additions",
                                 "vv_save_layout", "vv_tribe_rename"}),
            ("vv_tree_editor_tools", {"vv_family_tree", "vv_gdiplus"}),
            # The save folder's folder and file names, old and new (the owner, 2026-10-09).
            ("vv_save_layout", set()),
        ):
            tree = ast.parse((ROOT / "src" / f"{module}.py").read_text(encoding="utf-8"))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                    imported.add(node.module.split(".")[0])
            with self.subTest(module=module):
                self.assertEqual(imported - set(sys.stdlib_module_names) - may_import, set())


if __name__ == "__main__":
    unittest.main()
