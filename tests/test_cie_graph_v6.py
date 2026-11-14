"""Branching Custom Island Events format version 6 (the Isola Grand Event Collection, v1.35.97).

Pinned here:
  * versions 1 to 5 compile, normalize and table their chances byte for byte as before version 6 existed
    (tests/data/cie_v1_v5_pins.json, taken at 98cd1b39 before any version 6 code);
"""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_cie_graph as cg  # noqa: E402
import test_cie_graph as t  # noqa: E402

PINS = json.loads((ROOT / "tests" / "data" / "cie_v1_v5_pins.json").read_text(encoding="utf-8"))


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def pinned_cases() -> dict:
    return {
        "the_aspiring_adventurer.json": json.loads((ROOT / "data/cie_graphs/the_aspiring_adventurer.json")
                                                   .read_text("utf-8")),
        "the_cave_explorers.json": json.loads((ROOT / "data/cie_graphs/the_cave_explorers.json").read_text("utf-8")),
        "tiny_v1": t.tiny(),
        "multi_v2": t.multi(),
        "v3": t.v3(),
        "four_doors_v4": t.four_doors(4),
        "four_doors_v5": t.four_doors(5),
        "per_game_v5": t.PerGameAmounts().graph(),
    }


class OlderVersionsUnchanged(unittest.TestCase):
    def test_every_pinned_graph_is_byte_identical(self):
        cases = pinned_cases()
        self.assertEqual(set(cases), set(PINS))
        for name, data in cases.items():
            with self.subTest(name):
                g = cg.load(data)
                pin = PINS[name]
                self.assertEqual(g["version"], pin["version"])
                blob = cg.compile_graph(g)
                self.assertEqual(sha(blob), pin["cieg_sha256"])
                self.assertEqual(sha(json.dumps(g, sort_keys=True).encode()), pin["normalized_sha256"])
                tables = "\n\n".join(cg.chances_table(g, n) for n in g["games"])
                self.assertEqual(sha(tables.encode()), pin["chances_sha256"])
                self.assertEqual(cg.compile_graph(cg.decompile_graph(blob)), blob)


if __name__ == "__main__":
    unittest.main()
