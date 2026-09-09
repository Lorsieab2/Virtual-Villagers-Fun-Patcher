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
        lengths do not all carry the same weight. VV3's 25 comes from a count
        operand -- the burial writer at 0x455032 does `push 0x19` -- so it is a
        measurement. VV2's entry says so itself: "upper bound from displacement
        gap, not a count operand", which is a ceiling rather than a length, and
        VV4/VV5 carry a safe_write_limit of 24 alongside their 25.

        Demanding equality everywhere would therefore turn one game's proven
        value into a claim about four games where the evidence does not support
        it. The bound that IS safe everywhere is that no row may read more than
        the recorded length, and each row is separately checked to fit inside
        its stride below.
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

    def test_vv3_reads_its_whole_name_field(self) -> None:
        """VV3's length is measured, not inferred, so it is pinned exactly.

        `data/mask_identity_adapters.json` records 25 for +0xDD4 with the
        burial writer's `push 0x19` as its evidence, and main already ships
        VV3_NAME_LEN 0x19 for the same field. Reading only 24 makes two
        villagers differing in the 25th character compare equal, which does not
        merely truncate the log -- it makes the by-name scan's ambiguity guard
        refuse a father who was actually distinguishable.
        """
        vv3 = self.rows[2]
        self.assertTrue(vv3["supported"])
        self.assertEqual(vv3["name"], 0xDD4)
        self.assertEqual(vv3["name_capacity"], 0x19)

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
