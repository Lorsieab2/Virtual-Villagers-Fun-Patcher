"""The generated head-hair buckets (vv1_head_buckets.h) must be current and
sane: every villager head is bucketed exactly once per gender, and no colour
bucket is empty (an empty bucket makes its "All <colour> Hair" option a silent
no-op)."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:
    from PIL import Image  # noqa: F401

    HAVE_PIL = True
except ImportError:  # pragma: no cover
    HAVE_PIL = False


def _load():
    spec = importlib.util.spec_from_file_location(
        "hairbuckets", ROOT / "scripts" / "build_vv1_head_hair_buckets.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@unittest.skipUnless(HAVE_PIL, "requires Pillow")
class VV1HeadHairBucketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load()

    def test_committed_header_is_current(self):
        header = self.m.build_header()
        self.assertEqual(
            self.m.HEADER.read_text(encoding="utf-8"),
            header,
            "vv1_head_buckets.h is stale; re-run scripts/build_vv1_head_hair_buckets.py",
        )

    def test_every_head_bucketed_once_and_no_empty_bucket(self):
        for fname in ("head_m.bmp", "head_f.bmp"):
            buckets, _ = self.m._bucket_file(self.m.APPEARANCE / fname)
            with self.subTest(sheet=fname):
                flat = [v for bucket in buckets for v in bucket]
                # every variant appears exactly once across the five buckets
                self.assertEqual(sorted(flat), list(range(len(flat))))
                # no colour bucket is empty
                for c, bucket in enumerate(buckets):
                    self.assertTrue(
                        bucket, f"{fname} bucket {self.m.COLOUR_NAMES[c]} is empty"
                    )


if __name__ == "__main__":
    unittest.main()
