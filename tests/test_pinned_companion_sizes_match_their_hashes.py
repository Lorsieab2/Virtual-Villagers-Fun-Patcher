"""A pinned size must describe the same file its pinned hash does.

Several companion pins carry a sha256 AND a byte size. Re-pinning after a
rebuild is done by substituting digests -- that is what every sweep in this
repo looks for -- so a size sitting beside a digest is silently left behind
when the file changes length.

That happened: the Save Reset companion was rebuilt, every digest in the tree
was updated, and one `..._SIZE = 129536` was not. The file was 130048 bytes,
the certification refused to load the record, and 235 tests failed several
layers away from the cause with a message about "companion ownership metadata"
that named neither the file nor the size.

So check the pairs directly, against the files on disk.
"""
from __future__ import annotations

import hashlib
import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_fun_patcher as patcher  # noqa: E402

# constant stem -> the file the pair describes
PINNED_PAIRS = {
    "VV5_TASK9_SAVE_RESET": "assets/save_reset/VVFP Save Reset.dll",
    "VV5_TASK9_BIGHEAD_ATLAS": "assets/vv5_bighead_masks/bigheads_masks.png",
}


class PinnedCompanionSizesMatchTheirHashesTests(unittest.TestCase):
    def test_the_pairs_are_still_declared(self) -> None:
        """Guard the guard: a renamed constant would pass everything below."""
        for stem in PINNED_PAIRS:
            with self.subTest(stem=stem):
                self.assertTrue(
                    hasattr(patcher, stem + "_SHA256"), stem + "_SHA256"
                )
                self.assertTrue(hasattr(patcher, stem + "_SIZE"), stem + "_SIZE")

    def test_every_pinned_size_and_hash_describe_the_same_file(self) -> None:
        for stem, relative in sorted(PINNED_PAIRS.items()):
            path = ROOT / relative
            with self.subTest(stem=stem, file=relative):
                self.assertTrue(path.is_file(), relative)
                data = path.read_bytes()
                self.assertEqual(
                    getattr(patcher, stem + "_SHA256"),
                    hashlib.sha256(data).hexdigest().upper(),
                    f"{stem}_SHA256 does not match {relative}",
                )
                self.assertEqual(
                    getattr(patcher, stem + "_SIZE"),
                    len(data),
                    f"{stem}_SIZE is stale: re-pinning replaces digests, so a "
                    f"size beside one is left behind when {relative} changes "
                    "length",
                )

    def test_no_other_size_constant_has_drifted(self) -> None:
        """Sweep for the same shape anywhere else in the patcher.

        Any `X_SHA256` with a matching `X_SIZE` is this pattern, whether or
        not it is listed above; if the digest matches a file somewhere under
        assets/, the size must match that same file.
        """
        source = (ROOT / "src" / "vv_fun_patcher.py").read_text(encoding="utf-8")
        stems = set(re.findall(r"^(\w+)_SHA256 = \"[0-9A-F]{64}\"", source, re.M))
        paired = sorted(
            stem
            for stem in stems
            if re.search(r"^" + stem + r"_SIZE = \d+", source, re.M)
        )
        self.assertGreaterEqual(len(paired), 2, f"found only {paired}")

        by_digest = {}
        for asset in (ROOT / "assets").rglob("*"):
            if asset.is_file():
                by_digest.setdefault(
                    hashlib.sha256(asset.read_bytes()).hexdigest().upper(), asset
                )

        for stem in paired:
            digest = getattr(patcher, stem + "_SHA256")
            asset = by_digest.get(digest)
            if asset is None:
                continue        # pins a generated artifact, not a shipped file
            with self.subTest(stem=stem, file=asset.name):
                self.assertEqual(
                    getattr(patcher, stem + "_SIZE"),
                    asset.stat().st_size,
                    f"{stem}_SIZE does not match the file its hash names",
                )


if __name__ == "__main__":
    unittest.main()
