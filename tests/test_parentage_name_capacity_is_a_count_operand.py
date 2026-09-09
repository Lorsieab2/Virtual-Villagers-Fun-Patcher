"""Each pinned name capacity must be re-derivable from the game's own image.

`name_capacity` is how many bytes `find_record_by_name` compares. Too small and
two villagers differing only in the last character compare equal, so the
ambiguity guard refuses a father who was actually distinguishable -- a wrong
"(record not found)" on a birth that could have been resolved. Too large and it
reads past the field into whatever follows.

VV4 and VV5 shipped 0x18 against a real 0x19 for exactly the reason this test
exists: the value was argued from an adapter note rather than measured. The
note carried a `safe_write_limit: 24`, which is a WRITE bound and says nothing
about the read length, and that was mistaken for evidence about the read.

So this does not pin a number agreed between two documents. It disassembles the
copy site in each stock executable and reads the count operand the game itself
passes:

    VV3  0x455038  push 0x19 ; lea ecx,[ebp+0xDD4]  ; call 0x46F780
    VV4  0x45D4B2  push 0x19 ; lea eax,[edi+0x1B9C] ; call 0x4724E0
    VV5  0x464CB2  push 0x19 ; lea eax,[edi+0x1B9C] ; call 0x47D7C0

each followed by `mov byte [esi+0x19], 0`, the terminator at index 25.

VV1 and VV2 are deliberately absent. Neither writes names through a bounded
copy -- VV2's is an unbounded sprintf -- so there is no count operand to read
and their capacities rest on a different argument. A test that invented sites
for them would be asserting something it had not established.
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

# game -> stock executable, the copy site, and the field the copy targets.
MEASURED = {
    3: ("Virtual Villagers - The Secret City.exe", 0x455038, 0xDD4),
    4: ("Virtual Villagers - The Tree of Life.exe", 0x45D4B2, 0x1B9C),
    5: ("Virtual Villagers - New Believers.exe", 0x464CB2, 0x1B9C),
}


def _rows() -> dict[int, dict[str, str]]:
    source = EXPORTER.read_text(encoding="utf-8")
    body = source[source.index("struct game_layout {") :]
    body = body[: body.index("\n};")]
    fields = re.findall(
        r"^\s+(?:unsigned int|int|const wchar_t \*)\s+(\w+);", body, re.M
    ) + ["log_name"]
    table = source[source.index("GAME_LAYOUTS[6] = {") :]
    table = table[: table.index("\n};")]
    table = re.sub(r"/\*.*?\*/", "", table, flags=re.S)
    out: dict[int, dict[str, str]] = {}
    for index, entry in enumerate(re.findall(r"\{(.*?)\}", table, re.S)[1:], start=1):
        parts = [p.strip() for p in re.split(r',(?![^"]*"\s*$)', entry) if p.strip()]
        out[index] = dict(zip(fields, parts))
    return out


def _text(data: bytes) -> tuple[int, int]:
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    count = struct.unpack_from("<H", data, e_lfanew + 6)[0]
    optional = struct.unpack_from("<H", data, e_lfanew + 0x14)[0]
    table = e_lfanew + 0x18 + optional
    image_base = struct.unpack_from("<I", data, e_lfanew + 0x34)[0]
    for index in range(count):
        entry = table + index * 0x28
        if data[entry : entry + 8].rstrip(b"\0") == b".text":
            _, rva, _, raw = struct.unpack_from("<IIII", data, entry + 8)
            return image_base + rva, raw
    raise AssertionError("no .text section")


class ParentageNameCapacityIsACountOperandTests(unittest.TestCase):
    def test_the_declared_capacity_is_the_operand_the_game_passes(self):
        from capstone import CS_ARCH_X86, CS_MODE_32, Cs

        rows = _rows()
        md = Cs(CS_ARCH_X86, CS_MODE_32)
        checked = 0
        missing = []
        for game, (exe, site, field) in sorted(MEASURED.items()):
            if game not in rows:
                continue
            stock = ROOT / "research/stock-executables" / exe
            # Read INSIDE the loop and recorded rather than raised. Letting the
            # OSError escape would let conftest skip the whole method on the
            # first absent game, so a VV5-only installation would check nothing
            # while reporting skipped -- and a partial install that silently
            # checks less than it appears to is the failure shape this project
            # keeps hitting. The test still skips when NOTHING could be
            # measured, so it can never pass vacuously.
            try:
                data = stock.read_bytes()
            except OSError:
                missing.append(game)
                continue
            text_va, text_raw = _text(data)
            offset = text_raw + (site - text_va)
            listing = list(md.disasm(data[offset : offset + 0x20], site))
            self.assertTrue(listing, "VV%d site did not disassemble" % game)

            with self.subTest(game=game):
                checked += 1
                first = listing[0]
                self.assertEqual(
                    (first.mnemonic, first.op_str.startswith("0x")),
                    ("push", True),
                    "VV%d %#x is not a pushed immediate; the cited address is "
                    "wrong for this image" % (game, site),
                )
                operand = int(first.op_str, 16)

                # The copy must target the field the layout calls the name, or
                # the operand measured belongs to some other buffer. This is
                # what catches an address quoted from a different game's image.
                targets = [
                    item
                    for item in listing[:4]
                    if item.mnemonic == "lea" and hex(field) in item.op_str.lower()
                ]
                self.assertTrue(
                    targets,
                    "VV%d %#x does not address the name field %#x; the site "
                    "belongs to a different field or a different game"
                    % (game, site, field),
                )

                # And the terminator lands at the operand, proving it is a
                # length rather than an unrelated constant.
                terminators = [
                    item
                    for item in listing[:8]
                    if item.mnemonic == "mov"
                    and "byte ptr" in item.op_str
                    and hex(operand) in item.op_str.lower()
                ]
                self.assertTrue(
                    terminators,
                    "VV%d has no terminator written at index %#x, so %#x is "
                    "not the copy length" % (game, operand, operand),
                )

                self.assertEqual(
                    int(rows[game]["name_capacity"], 0),
                    operand,
                    "VV%d declares name_capacity %s but the game copies %#x "
                    "bytes; a short capacity truncates the comparison in "
                    "find_record_by_name and refuses fathers who differ only "
                    "in the last characters"
                    % (game, rows[game]["name_capacity"], operand),
                )
        # Coverage floor rather than "something ran": every measured game
        # whose executable is present must have contributed, so a partial
        # install cannot quietly reduce what this proves.
        present = len([game for game in MEASURED if game in rows]) - len(missing)
        if not present:
            self.skipTest(
                "no stock executable available for %s"
                % ", ".join("VV%d" % game for game in missing)
            )
        self.assertEqual(
            checked,
            present,
            "%d of %d available games were measured; coverage collapsed rather "
            "than the fixtures being absent" % (checked, present),
        )

    def test_unmeasured_games_are_not_silently_assumed(self):
        """VV1 and VV2 have no count operand, so they must not be listed here.

        Their capacities rest on a different argument -- VV2 writes names
        through an unbounded sprintf -- and inventing sites for them would make
        this test assert something it has not established.
        """
        self.assertNotIn(1, MEASURED)
        self.assertNotIn(2, MEASURED)
        rows = _rows()
        for game in (1, 2):
            with self.subTest(game=game):
                # Still required to be present and sane, just not pinned to an
                # operand this test can read.
                capacity = int(rows[game]["name_capacity"], 0)
                self.assertGreater(capacity, 0)
                self.assertLessEqual(capacity, 64)


if __name__ == "__main__":
    unittest.main()
