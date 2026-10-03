"""The release zip ships every feature manifest the patcher loads.

scripts/build_release.py packages an explicit list of data files. v1.35.56's
first build left out the three 256 Villagers (Experimental) manifests: the
patcher in the zip then offered no 256 option at all, although every test run
from the repository passed. This guard ties the release list to the patcher's
own manifest paths, so a new patch whose manifest is not packaged fails here
instead of shipping without it.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402


def packaged() -> set[str]:
    text = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
    return set(re.findall(r'"(data/[^"]+)"', text))


def feature_manifests() -> set[str]:
    """Every data/*_feature.json path the patcher module names."""
    found: set[str] = set()

    def add(value) -> None:
        if isinstance(value, Path):
            try:
                rel = value.resolve().relative_to(ROOT / "data")
            except ValueError:
                return
            if rel.name.endswith("_feature.json") and (ROOT / "data" / rel).exists():
                found.add("data/" + rel.as_posix())
        elif isinstance(value, (tuple, list, set, frozenset)):
            for item in value:
                add(item)

    for value in vars(patcher).values():
        add(value)
    return found


class ReleaseShipsEveryFeatureManifest(unittest.TestCase):
    def test_every_feature_manifest_is_packaged(self) -> None:
        manifests = feature_manifests()
        self.assertGreater(len(manifests), 40)
        missing = sorted(manifests - packaged())
        self.assertEqual(missing, [], "manifests the patcher loads but the release leaves out")

    def test_the_256_manifests_are_packaged(self) -> None:
        for game in (3, 4, 5):
            self.assertIn(f"data/vv{game}_population_256_feature.json", packaged())


if __name__ == "__main__":
    unittest.main()
