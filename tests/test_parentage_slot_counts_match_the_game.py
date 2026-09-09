"""A layout's slot count must not exceed what the game's own accessor allows.

`slots` is not a formatting detail: `find_record_by_name` and the ambiguity
guard both walk the whole array and cannot exit early, because "did exactly one
active record match?" is only answerable after the full pass. So a count larger
than the pool dereferences the `active` byte past the end of the array on every
conception -- a read of `(claimed - real) * stride` bytes of whatever follows
it, per birth, with no crash and nothing in the log to show for it.

A peer session found exactly that: VV3's row claimed 256 against a real 150,
walking 106 slots and 856,056 bytes past the pool.

The bound is derived from each game's own record accessor rather than from a
table written alongside the one being checked. The accessor computes
`index * stride + base` and refuses an index above a literal, so that literal
is the game's own statement of how many slots exist.
"""

from __future__ import annotations

import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

EXPORTER = ROOT / "native/parentage_export/parentage_export.c"

# game -> stock executable, and the accessor whose bound is authoritative.
# Only the games whose accessor has been identified are pinned; the rest are
# still checked for the weaker property that the count is positive and sane.
ACCESSORS = {
    4: ("Virtual Villagers - The Tree of Life.exe", 0x466040),
    5: ("Virtual Villagers - New Believers.exe", 0x46F950),
}


def _rows():
    source = EXPORTER.read_text(encoding="utf-8")
    body = source[source.index("struct game_layout {") :]
    body = body[: body.index("\n};")]
    fields = re.findall(
        r"^\s+(?:unsigned int|int|const wchar_t \*)\s+(\w+);", body, re.M
    ) + ["log_name"]
    table = source[source.index("GAME_LAYOUTS[6] = {") :]
    table = table[: table.index("\n};")]
    table = re.sub(r"/\*.*?\*/", "", table, flags=re.S)
    out = {}
    for index, entry in enumerate(re.findall(r"\{(.*?)\}", table, re.S)[1:], start=1):
        parts = [p.strip() for p in re.split(r',(?![^"]*"\s*$)', entry) if p.strip()]
        out[index] = dict(zip(fields, parts))
    return out


def _text_section(data: bytes):
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, e_lfanew + 6)[0]
    optional = struct.unpack_from("<H", data, e_lfanew + 0x14)[0]
    table = e_lfanew + 0x18 + optional
    image_base = struct.unpack_from("<I", data, e_lfanew + 0x34)[0]
    for index in range(count):
        entry = table + index * 0x28
        if data[entry : entry + 8].rstrip(b"\0") == b".text":
            _, rva, raw_size, raw = struct.unpack_from("<IIII", data, entry + 8)
            return image_base + rva, raw, raw_size
    raise AssertionError("no .text section")


def _accessor_bound(data: bytes, accessor_va: int):
    """(slots, stride, base) as the game's own accessor states them."""
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs

    text_va, text_raw, _ = _text_section(data)
    offset = text_raw + (accessor_va - text_va)
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    limit = stride = base = None
    for insn in md.disasm(data[offset : offset + 0x40], accessor_va):
        if insn.mnemonic == "cmp" and limit is None:
            argument = insn.op_str.split(",")[-1].strip()
            if argument.startswith("0x"):
                limit = int(argument, 16)
        elif insn.mnemonic == "imul":
            argument = insn.op_str.split(",")[-1].strip()
            if argument.startswith("0x"):
                stride = int(argument, 16)
        elif insn.mnemonic == "lea" and "+" in insn.op_str:
            match = re.search(r"\+ (0x[0-9a-f]+)\]", insn.op_str)
            if match:
                base = int(match.group(1), 16)
        elif insn.mnemonic == "ret":
            break
    return (None if limit is None else limit + 1), stride, base


class ParentageSlotCountsMatchTheGameTests(unittest.TestCase):
    def setUp(self):
        self.rows = _rows()

    def test_every_row_has_a_sane_positive_count(self):
        for game, row in self.rows.items():
            with self.subTest(game=game):
                slots = int(row["slots"], 0)
                self.assertGreater(slots, 0, "VV%d claims no slots at all" % game)
                # The walk is O(slots) per conception and dereferences each
                # record, so an absurd count is a defect even without knowing
                # the exact bound.
                self.assertLessEqual(
                    slots, 1024, "VV%d claims an implausible slot count" % game
                )

    def test_the_count_matches_the_accessor_where_it_is_known(self):
        checked = 0
        for game, (exe, accessor_va) in ACCESSORS.items():
            stock = ROOT / "research/stock-executables" / exe
            # Opened, not probed, so a checkout without the games skips rather
            # than passing having verified nothing.
            data = stock.read_bytes()
            slots, stride, base = _accessor_bound(data, accessor_va)
            row = self.rows[game]
            with self.subTest(game=game):
                self.assertIsNotNone(
                    slots, "VV%d accessor bound was not decoded" % game
                )
                checked += 1
                # The walk must not run past what the game itself permits.
                self.assertLessEqual(
                    int(row["slots"], 0),
                    slots,
                    "VV%d walks %s slots but the game bounds the index at %d; "
                    "the difference is read out of bounds on every conception"
                    % (game, row["slots"], slots - 1),
                )
                # Stride and base come from the same instructions, so pinning
                # them here proves the accessor really is the record accessor
                # rather than some other routine that happens to decode.
                self.assertEqual(int(row["stride"], 0), stride)
                self.assertEqual(int(row["record_base"], 0), base)
        self.assertGreater(checked, 0, "no accessor bound was checked")


if __name__ == "__main__":
    unittest.main()
