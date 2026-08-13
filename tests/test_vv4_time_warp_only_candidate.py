import hashlib
import unittest
from pathlib import Path

from scripts.build_vv4_time_warp_only_candidate import (
    BASE,
    BASE_SHA256,
    FINAL_SHA256,
    FINAL_SIZE,
    render,
)


class VV4TimeWarpOnlyCandidateTests(unittest.TestCase):
    def test_clean_expanded_base_is_exact(self) -> None:
        self.assertTrue(BASE.is_file())
        self.assertEqual(hashlib.sha256(BASE.read_bytes()).hexdigest().upper(), BASE_SHA256)

    def test_candidate_is_time_warp_only_and_deterministic(self) -> None:
        candidate, report = render(BASE.read_bytes())
        self.assertEqual(len(candidate), FINAL_SIZE)
        self.assertEqual(hashlib.sha256(candidate).hexdigest().upper(), FINAL_SHA256)
        self.assertEqual(report["feature_id"], "vv4_expanded_256_time_warp")
        self.assertEqual(report["tech_screen"]["button"], "Upgrades")
        self.assertEqual(report["tech_screen"]["enabled_rows"], ["Time Warp"])
        self.assertFalse(report["tech_screen"]["other_origins_rows_enabled"])
        self.assertFalse(report["runtime_go"])
        self.assertFalse(report["player_go"])

    def test_candidate_keeps_the_256_serializer_section(self) -> None:
        candidate, _ = render(BASE.read_bytes())
        self.assertEqual(candidate[0x2C0:0x2C4], b".vv4")
        self.assertEqual(candidate[0x1F125:0x1F12A].hex().upper(), "E8D61E4500")
        self.assertEqual(candidate[0x1FD34:0x1FD39].hex().upper(), "E8C7134500")


if __name__ == "__main__":
    unittest.main()
