"""The patcher tells you which build you have and whether a newer one exists.

Three things matter here and each is easy to get subtly wrong.

1. The comparison is by VERSION, not by string. "v1.34.9" is newer than
   "v1.34.10" alphabetically and older numerically, and the patcher has been
   past .9 for a while, so a string compare would announce the wrong answer.

2. A PRERELEASE is newer than the newest *published* release. The check must
   say so rather than claiming the build is out of date, because prereleases
   are exactly what the owner hands out for testing.

3. The check must never be able to break patching. It is a network call in a
   tool whose actual job needs no network at all, so it runs off the main
   thread and every failure -- offline, timeout, rate limit, garbage payload --
   has to land on one handler that leaves the window alive.
"""
from __future__ import annotations

import ast
import json
import unittest
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "src" / "vv_fun_patcher_gui.py"

import sys

sys.path.insert(0, str(ROOT / "src"))

from transparency import PATCHER_VERSION  # noqa: E402
from vv_fun_patcher_gui import (  # noqa: E402
    LATEST_RELEASE_API,
    RELEASES_PAGE,
    UPDATE_CHECK_TIMEOUT_SECONDS,
    fetch_latest_release_tag,
    parse_version,
)


class VersionParsingTests(unittest.TestCase):
    def test_a_normal_tag_becomes_ordered_numbers(self) -> None:
        self.assertEqual(parse_version("v1.34.23"), (1, 34, 23))
        self.assertEqual(parse_version("1.34.23"), (1, 34, 23))

    def test_ordering_is_numeric_not_alphabetical(self) -> None:
        """The trap: "v1.34.9" sorts after "v1.34.10" as a string."""
        self.assertGreater(parse_version("v1.34.10"), parse_version("v1.34.9"))
        self.assertGreater(parse_version("v1.35.0"), parse_version("v1.34.99"))
        self.assertGreater(parse_version("v2.0.0"), parse_version("v1.99.99"))

    def test_an_unparseable_tag_can_never_look_like_an_upgrade(self) -> None:
        """() compares less than every real version, so it is never "newer"."""
        for junk in ("", "latest", "v", "nightly-build", "v1.x.3"):
            with self.subTest(tag=junk):
                self.assertEqual(parse_version(junk), ())
                self.assertLess(parse_version(junk), parse_version(PATCHER_VERSION))

    def test_the_shipped_version_parses(self) -> None:
        """Guards the whole file: an unparseable own version breaks every path."""
        self.assertNotEqual(parse_version(PATCHER_VERSION), ())


class FetchTests(unittest.TestCase):
    @staticmethod
    def _response(payload: bytes):
        handle = BytesIO(payload)
        handle.__enter__ = lambda self=handle: self
        handle.__exit__ = lambda *args: False
        return handle

    def test_it_reads_the_tag_from_the_api(self) -> None:
        body = json.dumps({"tag_name": "v9.9.9", "name": "ignored"}).encode()
        with mock.patch("urllib.request.urlopen", return_value=self._response(body)):
            self.assertEqual(fetch_latest_release_tag(), "v9.9.9")

    def test_it_asks_the_release_api_with_a_timeout(self) -> None:
        """A hung request must not sit forever behind the wait window."""
        body = json.dumps({"tag_name": "v1.0.0"}).encode()
        with mock.patch(
            "urllib.request.urlopen", return_value=self._response(body)
        ) as opened:
            fetch_latest_release_tag()
        request, = opened.call_args.args
        self.assertEqual(request.full_url, LATEST_RELEASE_API)
        self.assertEqual(opened.call_args.kwargs["timeout"], UPDATE_CHECK_TIMEOUT_SECONDS)

    def test_every_failure_raises_one_catchable_type(self) -> None:
        """urllib's errors subclass OSError; the missing-tag case must too."""
        failures = [
            urllib.error.URLError("offline"),
            urllib.error.HTTPError(LATEST_RELEASE_API, 403, "rate limited", {}, None),
            TimeoutError("timed out"),
        ]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                with mock.patch("urllib.request.urlopen", side_effect=failure):
                    with self.assertRaises(OSError):
                        fetch_latest_release_tag()

    def test_a_payload_with_no_tag_is_a_failure_not_a_silent_pass(self) -> None:
        for payload in (b"{}", json.dumps({"tag_name": "   "}).encode()):
            with self.subTest(payload=payload):
                with mock.patch(
                    "urllib.request.urlopen", return_value=self._response(payload)
                ):
                    with self.assertRaises(OSError):
                        fetch_latest_release_tag()


class UpdateCheckWiringTests(unittest.TestCase):
    """Source-level checks for the parts a headless test cannot click."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.source = GUI.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.handler = next(
            node
            for node in ast.walk(cls.tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_check_for_updates"
        )

    def test_the_link_exists_and_is_wired_to_the_handler(self) -> None:
        self.assertIn('"Check for Updates", self._check_for_updates', self.source)

    def test_the_version_is_shown_next_to_it(self) -> None:
        self.assertIn(
            'text=f"Virtual Villagers Fun Patcher {PATCHER_VERSION}"', self.source
        )

    def test_the_request_runs_off_the_main_thread(self) -> None:
        """Reusing _run_with_wait is what keeps the window painting."""
        calls = [
            node
            for node in ast.walk(self.handler)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_run_with_wait"
        ]
        self.assertEqual(len(calls), 1, "the update check must use the wait window")

    def test_the_failure_path_is_handled_in_the_handler(self) -> None:
        """Not left to crash the callback and take the window with it."""
        handlers = [
            node for node in ast.walk(self.handler) if isinstance(node, ast.ExceptHandler)
        ]
        self.assertTrue(handlers, "the update check has no failure handling")
        caught = {
            name.id
            for handler in handlers
            if isinstance(handler.type, ast.Name)
            for name in [handler.type]
        }
        self.assertIn("OSError", caught)

    def test_a_browser_is_only_opened_after_the_player_agrees(self) -> None:
        """Every webbrowser.open sits inside an askyesno branch."""
        opens = [
            node
            for node in ast.walk(self.handler)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "open"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "webbrowser"
        ]
        self.assertTrue(opens, "the update check never offers the releases page")
        guarded = []
        for branch in ast.walk(self.handler):
            if not isinstance(branch, ast.If):
                continue
            asks = [
                node
                for node in ast.walk(branch.test)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "askyesno"
            ]
            if asks:
                guarded.extend(
                    node
                    for statement in branch.body
                    for node in ast.walk(statement)
                    if node in opens
                )
        self.assertEqual(
            len(guarded), len(opens), "a browser is opened without asking first"
        )

    def test_the_comparison_goes_through_parse_version(self) -> None:
        """Otherwise the tags are compared as strings.

        parse_version being correct in isolation proves nothing if the handler
        never calls it: "v1.34.9" > "v1.34.10" as a string, so a build past .9
        would announce the wrong answer while every unit test still passed.
        """
        parsed = {
            node.targets[0].id
            for node in ast.walk(self.handler)
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == "parse_version"
        }
        self.assertEqual(
            parsed,
            {"current_version", "latest_version"},
            "both sides of the version comparison must go through parse_version",
        )
        compared = set()
        for node in ast.walk(self.handler):
            if isinstance(node, ast.Compare):
                operands = [node.left, *node.comparators]
                names = {n.id for n in operands if isinstance(n, ast.Name)}
                if names & parsed:
                    compared |= names
        self.assertEqual(
            compared,
            parsed,
            "the handler compares something other than the parsed versions",
        )

    def test_it_points_at_this_repository(self) -> None:
        for url in (RELEASES_PAGE, LATEST_RELEASE_API):
            with self.subTest(url=url):
                self.assertIn("Lorsieab2/Virtual-Villagers-Fun-Patcher", url)
                self.assertTrue(url.startswith("https://"))

    def test_a_newer_local_build_is_not_called_out_of_date(self) -> None:
        """Prereleases are handed out for testing; they are ahead, not behind.

        Checked on the syntax tree, not by grepping for the wording: the
        message survives in the file even if the branch that reaches it is
        disabled, so a text search would pass over a dead code path.
        """
        directions = set()
        for node in ast.walk(self.handler):
            if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
                continue
            names = {node.test.left.id} if isinstance(node.test.left, ast.Name) else set()
            names |= {
                operand.id
                for operand in node.test.comparators
                if isinstance(operand, ast.Name)
            }
            if names != {"current_version", "latest_version"}:
                continue
            for operator in node.test.ops:
                directions.add(type(operator).__name__)
        self.assertEqual(
            directions,
            {"Gt", "Lt"},
            "the handler must branch on BOTH a newer release and a newer local build",
        )
        self.assertIn("is newer than the latest", self.source)

    def test_no_third_party_package_is_imported(self) -> None:
        """The README promises the patcher needs no third-party packages."""
        imported = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module.split(".")[0])
        allowed = set(sys.stdlib_module_names) | {
            "vv_fun_patcher",
            "transparency",
        }
        self.assertEqual(imported - allowed, set())


if __name__ == "__main__":
    unittest.main()
