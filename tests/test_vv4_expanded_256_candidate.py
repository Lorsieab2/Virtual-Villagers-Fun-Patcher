import hashlib
import unittest
from pathlib import Path

from scripts.build_vv4_expanded_256_candidate import (
    BASE_SHA256,
    FINAL_SIZE,
    render,
)


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "outputs/expanded-256-audit/vv4-renders/vv4-experimental_expanded_256_progression-all-current.exe"


class VV4Expanded256CandidateTests(unittest.TestCase):
    def test_latest_base_is_exact(self):
        self.assertTrue(BASE.is_file())
        self.assertEqual(hashlib.sha256(BASE.read_bytes()).hexdigest().upper(), BASE_SHA256)

    def test_composite_candidate_is_deterministic_and_structurally_bound(self):
        candidate, report = render(BASE.read_bytes())
        self.assertEqual(len(candidate), FINAL_SIZE)
        self.assertEqual(report["status"], "static_candidate_runtime_stop")
        self.assertFalse(report["publication_enabled"])
        self.assertFalse(report["runtime_go"])
        self.assertFalse(report["player_go"])
        self.assertEqual(candidate[0x1F125], 0xE8)
        self.assertEqual(candidate[0x1FD34], 0xE8)
        self.assertEqual(candidate[0x2C0:0x2C4], b".vv4")


if __name__ == "__main__":
    unittest.main()
