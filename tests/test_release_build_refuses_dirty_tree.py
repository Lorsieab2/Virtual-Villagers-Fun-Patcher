"""A dirty tree must leave no release ZIP behind.

scripts/build_release.py packs the patcher ZIP from the WORKING TREE and the
source ZIP from HEAD, and refuses a tree with uncommitted tracked changes so
the two cannot disagree. The refusal used to happen only inside the source
step, which main() reached after it had already published the patcher ZIP
under its final release name -- so the script exited 1 ("refusing to build a
source archive from a dirty tree") while leaving
outputs/Virtual-Villagers-Fun-Patcher-vX.zip full of the uncommitted content,
where it reads as a valid release.

These tests run the real main() against a throwaway git repository in a
temporary directory (never this checkout), with ROOT, OUTPUTS and FILES
pointed at it.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_release_module():
    path = ROOT / "scripts" / "build_release.py"
    spec = importlib.util.spec_from_file_location("vvfp_build_release_dirty", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.invalid",
         "-c", "core.autocrlf=false", *args],
        cwd=repo, check=True, capture_output=True,
    )


@unittest.skipIf(shutil.which("git") is None, "git is not available")
class DirtyTreeLeavesNoReleaseZipTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.repo = Path(self._temp.name) / "repo"
        self.repo.mkdir()
        (self.repo / "README.md").write_text("committed\n", encoding="utf-8")
        (self.repo / "data").mkdir()
        (self.repo / "data" / "builds.json").write_text("{}\n", encoding="utf-8")
        _git(self.repo, "init", "-q")
        _git(self.repo, "add", "README.md", "data/builds.json")
        _git(self.repo, "commit", "-q", "-m", "initial")
        self.release = load_release_module()
        self.release.ROOT = self.repo
        self.release.OUTPUTS = self.repo / "outputs"
        self.release.FILES = ["README.md", "data/builds.json"]

    def tearDown(self) -> None:
        self._temp.cleanup()

    def _outputs(self) -> list[str]:
        outputs = self.repo / "outputs"
        if not outputs.exists():
            return []
        return sorted(path.name for path in outputs.iterdir())

    def test_a_dirty_tree_is_refused_and_writes_no_release_zip(self) -> None:
        (self.repo / "README.md").write_text("uncommitted edit\n", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "dirty tree"):
            self.release.main()
        self.assertEqual(self._outputs(), [], "a refused build must write nothing")

    def test_a_clean_tree_still_publishes_both_archives(self) -> None:
        # The guard must not have broken the ordinary release: the same repo,
        # committed, yields the patcher ZIP, its source ZIP and the manifest.
        self.assertEqual(self.release.main(), 0)
        self.assertEqual(
            self._outputs(),
            sorted([
                self.release.NAME,
                self.release.SOURCE_NAME,
                Path(self.release.NAME).stem + ".manifest.json",
            ]),
        )

    def test_a_rejected_source_archive_unpublishes_the_patcher_zip(self) -> None:
        def reject() -> dict:
            raise RuntimeError("source archive CRC failure: simulated")

        self.release._build_source_archive = reject
        with self.assertRaisesRegex(RuntimeError, "simulated"):
            self.release.main()
        self.assertNotIn(self.release.NAME, self._outputs())

    def test_a_failed_build_leaves_no_stale_manifest(self) -> None:
        # A good build first, so a manifest from it is on disk; then a build
        # that fails must not leave that manifest describing a ZIP it removed.
        self.assertEqual(self.release.main(), 0)
        manifest = Path(self.release.NAME).stem + ".manifest.json"
        self.assertIn(manifest, self._outputs())

        def reject() -> dict:
            raise RuntimeError("source archive CRC failure: simulated")

        self.release._build_source_archive = reject
        with self.assertRaisesRegex(RuntimeError, "simulated"):
            self.release.main()
        self.assertNotIn(self.release.NAME, self._outputs())
        self.assertNotIn(manifest, self._outputs())


if __name__ == "__main__":
    unittest.main()
