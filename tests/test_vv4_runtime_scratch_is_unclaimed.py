"""VV4 runtime scratch never lands on bytes a manifest claims.

The VV4 Origins caves keep runtime state (mask slots, Details row/column,
world-blit arguments, Barrel/Island flags) in the RWX .shr page. The build's
overlap check only covers static patches, so a scratch dword placed on top of
code goes unnoticed: MASK_DETAILS_ROW/COL once sat at 0x728A50, the first
bytes of the Barrel/Island requeue routine, and every masked Details portrait
overwrote that code so the next purchased Barrel executed garbage.

This pins every runtime scratch address the builder declares against every
byte range claimed by any VV4 manifest in data/.
"""
from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts" / "build_vv4_origins_feature.py"
SHR_FILE = 0xCC000
SHR_VA = 0x728000
SHR_END_VA = 0x729000

# Runtime-written scratch: (name, width in bytes). Every one is written at run
# time by a cave or the companion DLL, never by the patcher.
SCRATCH = {
    "BARREL_UPGRADE_FLAG_VA": 1,
    "BARREL_ARMED_VA": 1,
    "ISLAND_PURCHASED_VA": 1,
    "ISLAND_DUE_STAMP_VA": 4,
    "MASK_SLOT_HMOD": 4,
    "MASK_SLOT_CACHE_PTR": 4,
    "MASK_SLOT_GET_PTR": 4,
    "MASK_SLOT_RESOLVED": 1,
    "MASK_SLOT_ATLAS": 4,
    "MASK_DETAILS_ROW": 4,
    "MASK_DETAILS_COL": 4,
    "MASK_S_ECX": 4,
    "MASK_S_ESI": 4,
    "MASK_S_X": 4,
    "MASK_S_Y": 4,
    "MASK_S_FACING": 4,
    "MASK_S_TRANSFORM": 4,
    "MASK_S_RET": 4,
    "MASK_S_DY": 4,
    "MASK_W_MGR": 4,
    "MASK_W_REC": 4,
    "MASK_W_RET": 4,
    "MASK_W_A1": 4,
    "MASK_W_A2": 4,
    "MASK_W_A3": 4,
    "MASK_W_A4": 4,
    "MASK_W_A5": 4,
    "MASK_W_A6": 4,
    "MASK_W_A7": 4,
}
# Slots that are themselves a declared manifest patch (zero-initialised data),
# so their only claim is their own.
SELF_CLAIMED = {"VV4_DETAIL_RECORD_VA": 4}


def _constants() -> dict[str, int]:
    text = BUILDER.read_text(encoding="utf-8")
    found = {}
    for name in list(SCRATCH) + list(SELF_CLAIMED):
        m = re.search(rf"^{name} = (0x[0-9A-Fa-f]+|\w+)", text, re.M)
        assert m, name
        value = m.group(1)
        if not value.startswith("0x"):
            value = re.search(rf"^{value} = (0x[0-9A-Fa-f]+)", text, re.M).group(1)
        found[name] = int(value, 16)
    return found


def _vv4_claims() -> list[tuple[int, int, str]]:
    claims = []
    for path in sorted((ROOT / "data").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict) or data.get("game_id") not in ("vv4", 4, "VV4"):
            continue
        for patch in data.get("patches", []):
            if not isinstance(patch, dict) or "offset" not in patch or "after" not in patch:
                continue
            start = int(str(patch["offset"]), 16)
            size = len(re.sub(r"\s+", "", str(patch["after"]))) // 2
            if SHR_FILE <= start < SHR_FILE + 0x1000:
                claims.append((SHR_VA + start - SHR_FILE, SHR_VA + start - SHR_FILE + size, path.name))
    return claims


class Vv4RuntimeScratchIsUnclaimedTests(unittest.TestCase):
    def test_the_origins_manifest_is_found(self) -> None:
        names = {name for _, _, name in _vv4_claims()}
        self.assertIn("vv4_origins_feature.json", names)

    def test_no_scratch_slot_overlaps_a_claimed_range(self) -> None:
        constants = _constants()
        claims = _vv4_claims()
        for name, width in SCRATCH.items():
            start = constants[name]
            with self.subTest(name=name, va=hex(start)):
                self.assertTrue(SHR_VA <= start and start + width <= SHR_END_VA)
                for lo, hi, source in claims:
                    self.assertFalse(start < hi and lo < start + width,
                                     f"{name} {start:#x} is inside {source} claim {lo:#x}..{hi:#x}")
        for name, width in SELF_CLAIMED.items():
            start = constants[name]
            with self.subTest(name=name):
                owners = [(lo, hi) for lo, hi, _ in claims if start < hi and lo < start + width]
                self.assertEqual(owners, [(start, start + width)])

    def test_no_two_scratch_slots_overlap(self) -> None:
        constants = _constants()
        spans = sorted((constants[n], constants[n] + w, n) for n, w in SCRATCH.items())
        for (a_lo, a_hi, a), (b_lo, _b_hi, b) in zip(spans, spans[1:]):
            self.assertLessEqual(a_hi, b_lo, f"{a} overlaps {b}")

    def test_the_details_scratch_is_not_the_requeue_routine(self) -> None:
        text = BUILDER.read_text(encoding="utf-8")
        requeue = int(re.search(r"^BARREL_ISLAND_REQUEUE_VA = (0x[0-9A-Fa-f]+)", text, re.M).group(1), 16)
        constants = _constants()
        for name in ("MASK_DETAILS_ROW", "MASK_DETAILS_COL"):
            self.assertFalse(requeue <= constants[name] < requeue + 0x28, name)


if __name__ == "__main__":
    unittest.main()
