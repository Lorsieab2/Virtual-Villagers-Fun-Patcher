"""Procedural pieces (VPCB v1) and the composer twin: the file round trip, the refusals, the roll order and the
shipped files' tags (docs/event-collection/procedural-pieces.md, procedural-pieces-data.md)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_procedural as vp  # noqa: E402
from vv_procedural import Link, Piece, Slot  # noqa: E402

PIECES = ROOT / "assets" / "event_collection" / "pieces"


def tiny() -> list[Piece]:
    s = Piece("s1", vp.KIND_SETUP, text="(subject) finds a shell.", label="A Shell", family=1,
              slots=[Slot("subject", min_age=14)])
    a1 = Piece("a1", vp.KIND_APPROACH, label="Keep It", family=1)
    a2 = Piece("a2", vp.KIND_APPROACH, label="Give It Away", family=1)
    a3 = Piece("a3", vp.KIND_APPROACH, label="Bury It", family=2)
    o1 = Piece("o1", vp.KIND_OUTCOME, text="It shines.", links=[Link("a1"), Link("a2", 3)])
    o2 = Piece("o2", vp.KIND_OUTCOME, text="(friend) smiles.", links=[Link("a2")], slots=[Slot("friend")])
    o3 = Piece("o3", vp.KIND_OUTCOME, text="Nothing.", links=[Link("a3")])
    return [s, a1, a2, a3, o1, o2, o3]


class Rolls:
    def __init__(self, values):
        self.values = list(values)
        self.asked = []

    def __call__(self, n):
        if n <= 1:
            return 0
        self.asked.append(n)
        return self.values.pop(0) % n if self.values else 0


class FileFormat(unittest.TestCase):
    def test_round_trip(self):
        data = vp.write_pcb(tiny())
        pf = vp.read_pcb(data)
        self.assertEqual([p.id for p in pf.pieces], [p.id for p in tiny()])
        self.assertEqual(pf.pieces[5].links[0].approach, "a2")
        self.assertEqual(vp.write_pcb(pf.pieces), data)

    def test_damaged_is_refused(self):
        data = bytearray(vp.write_pcb(tiny()))
        data[70] ^= 1
        with self.assertRaises(vp.PcbError):
            vp.read_pcb(bytes(data))

    def test_required_texts(self):
        with self.assertRaises(ValueError):
            vp.write_pcb([Piece("s", vp.KIND_SETUP, text="x")])


class RollOrder(unittest.TestCase):
    def test_rolls_in_spec_order(self):
        pf = vp.read_pcb(vp.write_pcb(tiny()))
        r = Rolls([0, 0, 0, 2, 0, 99, 99])
        comp = vp.compose(pf, vp.Settings(1), r)
        # roll 2 (n: 3 choices), approach picks (a1 alone weighs 1 with a2: total 2), outcomes, flavour, frame
        self.assertEqual(r.asked[0], 3)
        self.assertEqual([a.id for a in comp.approaches], ["a1", "a2"])
        self.assertEqual(r.asked[-2:], [100, 100])
        # o2's friend is an outcome's own role: optional
        self.assertTrue(all(m.optional for n, m in comp.roles.items() if n == "friend"))

    def test_family_must_equal(self):
        pf = vp.read_pcb(vp.write_pcb(tiny()))
        comp = vp.compose(pf, vp.Settings(1), Rolls([2] * 20))
        self.assertNotIn("a3", [a.id for a in comp.approaches])

    def test_never_with(self):
        ps = tiny()
        ps[1].never = 1 << 9
        ps[0].tags = 1 << 9
        pf = vp.read_pcb(vp.write_pcb(ps))
        self.assertIsNone(vp.compose(pf, vp.Settings(1), Rolls([0] * 40)))


class TitleCase(unittest.TestCase):
    def test_owner_rule(self):
        self.assertEqual(vp.title_case("ask the elders for advice."), "Ask the Elders for Advice.")
        self.assertEqual(vp.title_case("A DOG SEEMS TO HAVE CHOSEN THE BEST SEAT AT COUNCIL"),
                         "A Dog Seems to Have Chosen the Best Seat at Council")
        self.assertEqual(vp.title_case("what is it for"), "What Is It For")


@unittest.skipUnless(PIECES.is_dir(), "the piece files are not built")
class ShippedFiles(unittest.TestCase):
    def test_every_file_reads_and_fits(self):
        for f in sorted(PIECES.glob("pieces-*.pcb")):
            data = f.read_bytes()
            self.assertLessEqual(len(data), vp.FILE_MAX, f.name)
            pf = vp.read_pcb(data, f.stem[7:])
            for p in pf.pieces:
                if p.tags & vp.TAG_ROMANCE and p.age_band == vp.AGE_BAND_ADULT:
                    self.assertTrue(p.never & vp.TAG_MINOR, p.id)
                if p.kind == vp.KIND_SETUP:
                    self.assertTrue(vp.title_case_ok(p.label), p.id)
                if p.kind == vp.KIND_APPROACH:
                    self.assertTrue(vp.title_case_ok(p.label), p.id)


if __name__ == "__main__":
    unittest.main()
