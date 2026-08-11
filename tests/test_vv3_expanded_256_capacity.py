import hashlib
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import build_vv3_expanded_256_capacity as candidate  # noqa: E402
import pefile  # noqa: E402


EXPECTED = {
    "experimental_expanded_256": "E0B0418AEEE2782B6FDA7362D97F799CFDFBAC13E4F5B65EFF9611058109148D",
    "experimental_expanded_256_progression": "61CA54294740A0F091886FE63FA5BEE4D76A18370F9915C81A9BB3BAA44671A7",
}


class VV3Expanded256CapacityTests(unittest.TestCase):
    def test_exact_build_identity_and_neutral_page(self):
        for mode, expected_sha in EXPECTED.items():
            with self.subTest(mode=mode):
                data, report = candidate.build_candidate(mode)
                self.assertEqual(hashlib.sha256(data).hexdigest().upper(), expected_sha)
                self.assertEqual(len(data), 0xCE000)
                self.assertEqual(
                    data[candidate.CAPACITY_SECTION_RAW : candidate.CAPACITY_SECTION_RAW + 0x1000],
                    bytes(0x1000),
                )
                self.assertEqual(report["gates"]["runtime_go"], False)
                self.assertEqual(report["gates"]["player_go"], False)

    def test_pe_layout_and_time_warp_non_changes(self):
        data, _ = candidate.build_candidate("experimental_expanded_256")
        pe = pefile.PE(data=data, fast_load=True)
        self.assertEqual(pe.FILE_HEADER.NumberOfSections, 8)
        self.assertEqual(pe.OPTIONAL_HEADER.SizeOfImage, 0x3BB000)
        names = [section.Name.rstrip(b"\0") for section in pe.sections]
        self.assertEqual(names[-3:], [b".vv3rs", b".vv3sv", b".vv3i"])
        reserved = next(section for section in pe.sections if section.Name.startswith(b".vv3rs"))
        self.assertEqual(reserved.Characteristics & 0x20000000, 0)
        self.assertEqual(data[0x6547D : 0x6547D + 5], bytes.fromhex("8B4C243C5F"))
        self.assertEqual(data[0x65640 : 0x65640 + 8], bytes.fromhex("6AFF64A100000000"))
        self.assertEqual(data[0xD1A0 : 0xD1A0 + 8], bytes.fromhex("8B4910E928FDFFFF"))


if __name__ == "__main__":
    unittest.main()
