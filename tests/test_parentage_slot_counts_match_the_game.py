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
#
# Only VV4 and VV5 are here, and the omissions are deliberate rather than
# unfinished work.
#
# VV3's accessor cannot be pinned this way because it does not bound anything:
#
#     0x45C840  mov  eax, [esp+4]
#     0x45C844  imul eax, eax, 0x1F8C
#     0x45C84A  lea  eax, [eax+ecx+0x14]
#     0x45C84E  ret  4
#
# The check lives in its callers -- 0x45EE68 does `cmp eax, 0x96 ; jge <skip>`
# before `call 0x45C840` -- so there is no bound inside the accessor to read.
# Note the convention differs: VV3's 0x96 with `jge` is EXCLUSIVE while
# VV4/VV5's 0x95 with `ja` is INCLUSIVE, and both mean 150. Reading VV3's
# literal the way this test reads VV4's would give 151 and be wrong.
#
# VV1 and VV2 are absent for the same reason in a weaker form: a scan for their
# strides found bounds that do not belong to the villager pool, so pinning them
# would assert a number that has not been established.
#
# Those three are still covered by the weaker check below that the count is
# positive and not absurd, and by the separate test that compares the companion
# against builds.json. The two are complementary: this one proves the accessor
# agrees with the layout wherever an accessor states a bound, the other proves
# the layout agrees with the declared pool for every game.
#
# The bound is DECODED with capstone from a known address rather than located
# by byte pattern. That matters: the encoding here is `3D 95 00 00 00`
# (cmp eax, imm32), not the `83 F8 95` (imm8) short form, so a byte search for
# the obvious pattern finds nothing in any of the five games.
ACCESSORS = {
    4: ("Virtual Villagers - The Tree of Life.exe", 0x466040, None),
    5: ("Virtual Villagers - New Believers.exe", 0x46F950, None),
    # VV3's accessor states the stride and base but no bound, so the count is
    # read from the call site that gates it. `cmp eax, 0x96 ; jge` is EXCLUSIVE
    # where VV4/VV5's `cmp eax, 0x95 ; ja` is inclusive, and both mean 150.
    3: ("Virtual Villagers - The Secret City.exe", 0x45C840, 0x45EE68),
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


def _gate_bound(data: bytes, gate_va: int) -> int | None:
    """The slot count stated by a call site that guards the accessor.

    Used where the accessor itself carries no bound. The comparison is decoded
    rather than pattern-matched, and the branch decides the convention:
    `jge`/`jae` skip when the index is >= the literal, so the literal IS the
    count; `ja`/`jg` skip when it is >, so the count is literal + 1. Reading one
    convention as the other is a silent off-by-one -- it is how VV3 got read as
    151 once.
    """
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs

    text_va, text_raw, _ = _text_section(data)
    offset = text_raw + (gate_va - text_va)
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    limit = None
    for insn in md.disasm(data[offset : offset + 0x20], gate_va):
        if insn.mnemonic == "cmp" and limit is None:
            argument = insn.op_str.split(",")[-1].strip()
            if argument.startswith("0x"):
                limit = int(argument, 16)
        elif insn.mnemonic in ("jge", "jae", "jnb") and limit is not None:
            return limit
        elif insn.mnemonic in ("ja", "jg", "jnbe") and limit is not None:
            return limit + 1
        elif insn.mnemonic == "call":
            break
    return None


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
        missing = []
        for game, (exe, accessor_va, gate_va) in sorted(ACCESSORS.items()):
            stock = ROOT / "research/stock-executables" / exe
            # Read INSIDE the loop and recorded rather than raised, so one
            # absent game does not abort the others. A test that skips
            # wholesale on a partial install reports green while checking
            # nothing, which is the failure shape this project keeps hitting.
            try:
                data = stock.read_bytes()
            except OSError:
                missing.append(game)
                continue

            slots, stride, base = _accessor_bound(data, accessor_va)
            if gate_va is not None:
                # The accessor carries no bound of its own; the count comes
                # from the call site that guards it.
                slots = _gate_bound(data, gate_va)
            row = self.rows[game]
            with self.subTest(game=game):
                self.assertIsNotNone(
                    slots, "VV%d bound was not decoded" % game
                )
                checked += 1
                # EQUALITY, not an upper bound. The accessor states the exact
                # count, and an under-count is a different defect rather than a
                # milder one: find_record_by_name stops early so fathers in the
                # omitted tail are never found, and is_record_slot rejects
                # mothers there so their births are never logged at all --
                # silent loss rather than an out-of-bounds read.
                self.assertEqual(
                    int(row["slots"], 0),
                    slots,
                    "VV%d declares %s slots but the game allows exactly %d; "
                    "too many reads past the pool on every conception, too few "
                    "silently drops the records in the tail"
                    % (game, row["slots"], slots),
                )
                # Stride and base come from the accessor's own instructions, so
                # pinning them proves the routine decoded really is the record
                # accessor rather than something else that happens to decode.
                self.assertEqual(int(row["stride"], 0), stride)
                self.assertEqual(int(row["record_base"], 0), base)

        # Coverage floor, not merely "something ran". Every game whose
        # executable is present must have contributed, so a partial install
        # cannot quietly shrink what this proves while still reporting green.
        # Borrowed from a peer session's removal test, which had the stronger
        # shape than the one I wrote.
        present = len(ACCESSORS) - len(missing)
        if not present:
            self.skipTest(
                "no stock executable available for %s"
                % ", ".join("VV%d" % game for game in missing)
            )
        self.assertEqual(
            checked,
            present,
            "%d of %d available games were checked; coverage collapsed rather "
            "than the fixtures being absent" % (checked, present),
        )


if __name__ == "__main__":
    unittest.main()
