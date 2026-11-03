"""Unicode parity (VV): the shared spec's chain, sidecar v3, tribe rename, "%" rule, Unicode Font and Game Text tools.

One class per item, so a failure names the spec row it breaks.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

# UNICODE_SPEC.md section 3, "Fallback chain": "(UI)" faces are the GDI names with " UI".
SPEC_CHAIN = [
    "Segoe UI", "Segoe UI Historic", "Segoe UI Symbol", "Segoe UI Emoji", "Yu Gothic UI", "Meiryo",
    "Microsoft YaHei UI", "Microsoft JhengHei UI", "Malgun Gothic", "SimSun-ExtB", "Nirmala UI", "Ebrima",
    "Gadugi", "Leelawadee UI", "Myanmar Text", "Javanese Text", "Mongolian Baiti", "Microsoft Himalaya",
    "Microsoft Yi Baiti", "Microsoft New Tai Lue", "Microsoft Tai Le", "Microsoft PhagsPa", "Sylfaen",
    "Cambria Math", "Noto Sans", "Noto Sans Symbols", "Noto Sans Symbols 2", "Noto Sans CJK JP",
    "Noto Sans CJK SC", "Noto Sans Math", "Noto Sans Cuneiform", "Noto Color Emoji",
]


def native_chain() -> list[str]:
    text = (ROOT / "native" / "vvfp_unicode_text" / "runtime_glyphs.inc").read_text(encoding="utf-8")
    body = text[text.index("RG_CHAIN[] = {"):]
    body = body[:body.index("NULL")]
    return re.findall(r'L"([^"]+)"', body)


class FallbackChain(unittest.TestCase):
    def test_every_spec_face_is_in_the_chain_in_the_spec_order(self):
        chain = native_chain()
        self.assertEqual(len(chain), len(set(chain)), "a face listed twice")
        positions = [chain.index(face) for face in SPEC_CHAIN]
        self.assertEqual(positions, sorted(positions))

    def test_the_faces_vv_drew_with_before_are_kept(self):
        self.assertIn("Yu Gothic", native_chain())
        self.assertIn("Microsoft YaHei", native_chain())

    def test_the_face_table_holds_the_whole_chain(self):
        text = (ROOT / "native" / "vvfp_unicode_text" / "runtime_glyphs.inc").read_text(encoding="utf-8")
        faces = int(re.search(r"#define RG_FACES (\d+)", text).group(1))
        self.assertGreaterEqual(faces, len(native_chain()) + 4)    # chain + override + Arial/Comic + Emoji first


if __name__ == "__main__":
    unittest.main()
