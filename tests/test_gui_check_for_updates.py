"""The "Check for Updates" link sits at the top and opens the releases page.

This replaces a much larger file that tested a version-comparison machine: the
patcher used to query GitHub's API for the newest tag, parse both versions,
order prereleases below their final release, and handle every way a network
call can fail. The owner asked for the link to go straight to the releases
page instead, which deletes all of that -- the page already shows what is
newest, and the build version is printed under the link so the comparison is
the player's to make.

What still matters, and is checked here:

  * The link is at the TOP, beside the description, not in a footer.
  * It opens the real releases page for this repository.
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

EXPECTED_RELEASES_PAGE = (
    "https://github.com/Lorsieab2/Virtual-Villagers-Fun-Patcher/releases"
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

    def test_it_points_at_the_releases_page_exactly(self) -> None:
        """The owner supplied this URL directly; a near-miss is not good enough."""
        self.assertEqual(RELEASES_PAGE, EXPECTED_RELEASES_PAGE)

    def test_the_link_exists_and_opens_that_page(self) -> None:
        self.assertIn('"Check for Updates", self._open_releases_page', self.source)
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
        link = self.source.find('"Check for Updates"')
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
        allowed = set(sys.stdlib_module_names) | {"vv_fun_patcher", "transparency"}
        self.assertEqual(self._imported() - allowed, set())


if __name__ == "__main__":
    unittest.main()
