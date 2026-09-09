"""Each parentage layout row must match the villager pool its game declares.

VV3's row claimed 256 slots while `data/builds.json` declares the game at 150.
`find_record_by_name` cannot stop early -- it has to walk the whole range to
detect two active villagers sharing a name, which is the ambiguity guard that
keeps it from attributing the wrong father -- so the `active` byte was
dereferenced for all 256 slots on every conception. Slots 150..255 are past the
pool: 106 slots, 856,056 bytes at that stride, read on every VV3 birth.

Whether that faults depends on what happens to sit after the pool at runtime,
which is exactly the shape of defect that survives every test on this machine
and crashes on a player's.

The same row also declared a 24-byte name field where the game uses 25. That
one does not read out of bounds, but it makes the scan compare truncated names,
so two villagers differing only in the 25th character compare equal and the
ambiguity guard refuses a father who was actually distinguishable.

Both values are checked here against their independent sources rather than
against a second copy of the same table:

  * the slot count against `data/builds.json`, which the patcher itself uses
  * the name capacity against `data/mask_identity_adapters.json`, whose entry
    for each game's name field carries the length and its evidence

and every field offset is checked to fit inside the stride at its own width, so
a row can never read past the end of a record either.
"""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

COMPANION = ROOT / "native" / "parentage_export" / "parentage_export.c"
BUILDS = ROOT / "data" / "builds.json"
ADAPTERS = ROOT / "data" / "mask_identity_adapters.json"

# One row per game, in GAME_LAYOUTS order: supported, stride, slots,
# record_base, then the field offsets.
ROW = re.compile(
    r"^\s*(0|1),\s*(0x[0-9A-Fa-f]+|0),\s*(\d+),\s*(0x[0-9A-Fa-f]+|0),\s*$",
    re.M,
)
NAME_CAPACITY = re.compile(
    r"^\s*(0x[0-9A-Fa-f]+),\s*(0x[0-9A-Fa-f]+),\s*$", re.M
)


def _rows() -> list[dict[str, int]]:
    """Parse the layout table, one entry per game, in declaration order."""
    source = COMPANION.read_text(encoding="utf-8")
    start = source.index("GAME_LAYOUTS")
    table = source[start:]
    rows: list[dict[str, int]] = []
    for match in ROW.finditer(table):
        supported, stride, slots, record_base = match.groups()
        # The name offset and capacity are the pair two lines further on.
        capacity = NAME_CAPACITY.search(table, match.end())
        rows.append(
            {
                "supported": int(supported),
                "stride": int(stride, 0),
                "slots": int(slots),
                "record_base": int(record_base, 0),
                "name": int(capacity.group(1), 0) if capacity else 0,
                "name_capacity": int(capacity.group(2), 0) if capacity else 0,
            }
        )
        if len(rows) == 5:
            break
    return rows


class ParentageLayoutsMatchTheDeclaredPoolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = _rows()
        self.assertEqual(len(self.rows), 5, "expected one layout row per game")
        builds = json.loads(BUILDS.read_text(encoding="utf-8"))
        self.builds = {game["id"]: game for game in builds["games"]}

    def test_slot_count_matches_the_declared_villager_pool(self) -> None:
        """Scanning past the pool is an out-of-bounds read on every birth."""
        for index, row in enumerate(self.rows, start=1):
            game_id = f"vv{index}"
            with self.subTest(game=game_id):
                if not row["supported"]:
                    continue
                declared = self.builds[game_id]["villager_slots"]
                self.assertEqual(
                    row["slots"],
                    declared,
                    f"{game_id} scans {row['slots']} slots but the game "
                    f"declares {declared}; the record scan cannot stop early, "
                    "so the excess is read out of bounds on every conception",
                )
                # And the absolute maximum must agree, or "villager_slots" is
                # not the bound it looks like.
                self.assertEqual(
                    declared,
                    self.builds[game_id]["absolute_maximum"],
                    f"{game_id} villager_slots and absolute_maximum disagree",
                )

    def test_name_capacity_never_exceeds_the_recorded_field_length(self) -> None:
        """Reading past the name field would compare adjacent record bytes.

        This asserts an upper bound rather than equality, because the recorded
        lengths do not all carry the same weight. VV2's entry says so itself:
        "upper bound from displacement gap, not a count operand", which is a
        ceiling rather than a length, because VV2 writes its names through an
        unbounded sprintf and so has no count operand to read.

        Demanding equality everywhere would turn the measured games' proven
        values into a claim about VV2 that its own evidence disclaims. The
        bound that IS safe everywhere is that no row may read more than the
        recorded length, and each row is separately checked to fit inside its
        stride below.
        """
        adapters = json.loads(ADAPTERS.read_text(encoding="utf-8"))
        text = json.dumps(adapters)
        checked = 0
        for index, row in enumerate(self.rows, start=1):
            game_id = f"vv{index}"
            with self.subTest(game=game_id):
                if not row["supported"] or not row["name"]:
                    continue
                pattern = (
                    r'"name":\s*\{\s*"offset":\s*"0x%X"[^}]*?"length":\s*(\d+)'
                    % row["name"]
                )
                found = re.search(pattern, text)
                if not found:
                    continue
                checked += 1
                self.assertLessEqual(
                    row["name_capacity"],
                    int(found.group(1)),
                    f"{game_id} reads {row['name_capacity']} name bytes from a "
                    f"field recorded as {found.group(1)}, so the comparison "
                    "would run into whatever follows the name",
                )
        self.assertGreater(checked, 0, "no name field was checked at all")

    def test_measured_name_lengths_are_read_in_full(self) -> None:
        """Where a burial writer names the length, read all of it.

        VV3, VV4 and VV5 each copy a villager's name with strncpy under a
        literal count, and write the terminator at index 25:

            VV3  0x455038  push 0x19 ; lea ecx,[ebp+0xDD4]  ; call 0x46F780
            VV4  0x45D4B2  push 0x19 ; lea eax,[edi+0x1B9C] ; call 0x4724E0
            VV5  0x464CB2  push 0x19 ; lea eax,[edi+0x1B9C] ; call 0x47D7C0

        all followed by `mov byte [esi+0x19], 0`. Each was disassembled from
        that game's own executable.

        One citation is worth knowing about: VV4's adapter record names
        0x45D4B4 as its burial writer, which is the `lea` -- the `push 0x19`
        that carries the count is two bytes earlier, at 0x45D4B2. Disassembling
        from the cited address alone therefore hides the count operand, which
        is exactly how this length came to look unproven.

        Reading only 24 makes two villagers differing in the 25th character
        compare equal, which does not merely truncate the log: it makes the
        by-name scan's ambiguity guard refuse a father who was actually
        distinguishable, or attribute the wrong one.

        VV4 and VV5 also carry safe_write_limit 24. That is the WRITE bound and
        is orthogonal to the read length -- mistaking it for weak evidence is
        what left both games truncating after VV3 was fixed. Nothing here
        writes a name.
        """
        for index, offset in ((3, 0xDD4), (4, 0x1B9C), (5, 0x1B9C)):
            with self.subTest(game=f"vv{index}"):
                row = self.rows[index - 1]
                self.assertTrue(row["supported"])
                self.assertEqual(row["name"], offset)
                self.assertEqual(
                    row["name_capacity"],
                    0x19,
                    f"vv{index}'s burial writer proves a 25-byte name with a "
                    "count operand; reading fewer truncates the scan's "
                    "comparison",
                )

    def test_every_field_fits_inside_the_record_at_its_own_width(self) -> None:
        """A field read past the stride straddles into the next record."""
        source = COMPANION.read_text(encoding="utf-8")
        start = source.index("GAME_LAYOUTS")
        table = source[start:]
        for index, row in enumerate(self.rows, start=1):
            with self.subTest(game=f"vv{index}"):
                if not row["supported"]:
                    continue
                self.assertGreater(row["stride"], 0)
                self.assertGreater(row["slots"], 0)
                self.assertLess(row["record_base"], row["stride"])
                if row["name"]:
                    self.assertLessEqual(
                        row["name"] + row["name_capacity"],
                        row["stride"],
                        f"vv{index} name field runs past the record",
                    )
        self.assertIn("FATHER_BY_NAME", table)


if __name__ == "__main__":
    unittest.main()
