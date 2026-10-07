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
               "vv_genealogy", "vv_family_tree", "vv_gdiplus", "vv_genealogy_window", "vv_tree_editor_tools",
               "vv_number_names"}
        allowed = set(sys.stdlib_module_names) | own
        self.assertEqual(self._imported() - allowed, set())
        for module, may_import in (
            ("vv_save_backup", set()),
            ("vv_tribe_rename", {"vv_save_backup"}),
            ("vv_log_tools", {"vv_save_backup", "vv_log_additions"}),
            ("vv_log_additions", {"vv_log_tools", "vv_tribe_rename"}),
            # Giving last names re-keys the Family Tree Maker's edits (vv_family_tree.renamed_keys).
            ("vv_last_names", {"vv_log_tools", "vv_save_backup", "vv_log_additions", "vv_family_tree",
                               "vv_tribe_rename", "vv_genealogy"}),
            ("patcher_files", set()),
            ("vv_how_to_use", set()),
            # The Family Tree Maker and the Village Matchmaker.
            ("vv_genealogy", {"vv_log_tools", "vv_last_names", "vv_log_additions", "vv_tribe_rename"}),
            ("vv_family_tree", {"vv_genealogy", "vv_log_tools", "vv_gdiplus"}),
            ("vv_gdiplus", {"vv_family_tree"}),
            ("vv_genealogy_window", {"vv_family_tree", "vv_gdiplus", "vv_genealogy", "vv_save_backup",
                                     "vv_tribe_rename", "vv_tree_editor_tools", "vv_last_names", "vv_log_tools",
                                     "vv_number_names"}),
            # Number Duplicate Names renames through Last Names.
            ("vv_number_names", {"vv_genealogy", "vv_last_names", "vv_save_backup", "vv_log_additions"}),
            ("vv_tree_editor_tools", {"vv_family_tree", "vv_gdiplus"}),
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
