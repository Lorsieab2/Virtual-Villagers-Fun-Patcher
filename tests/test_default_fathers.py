"""The fathers that stand in when there is no man to name, in all five games.

The owner's rules (2026-09-21, 2026-10-10), reconciled in docs/known-behaviours-and-non-bugs.md:

- Where the GAME writes its own default father, the logs, the Family Tree and the Matchmaker show
  exactly that: The Lost Children's Gong of Wonder "?" (head 0, body 0); The Tree of Life's and New
  Believers' island-event babies "Joey" (2, 2) -- "Joey Joerson" once Villagers Have Last Names
  has given him one.  Each is a string literal in the executable, verified below.
- Where the game provides nothing (A New Home keeps no father anywhere), a genuine birth gets the
  patcher's fallback "Unknown" (0, 0) -- native/vv1_parentage, exercised by its harness.
- Neither is a villager: a default father is nobody's kin, so two children of the Gong are not
  half siblings, and a living villager who happens to be called Joey is not his namesake's double.
- Children spawned by an island event or a Barrel of Babies have no parents at all.
"""
from __future__ import annotations

import re
import struct
import sys
import unittest
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_genealogy as gen  # noqa: E402

Y = gen.UNITS_PER_YEAR
FIRST = "2026-01-01 10:00:00"
EXPORT_C = ROOT / "native" / "parentage_export" / "parentage_export.c"
VV1_C = ROOT / "native" / "vv1_parentage" / "vv1_parentage.c"
STOCK = {n: ROOT / "inputs" / f"vv{n}-stock-copy" for n in range(1, 6)}


def village(game: int, father: tuple, living_namesake: bool = False) -> gen.Village:
    """Mother M (2) has two children by the default father `father` (1); another woman W (6) has a
    son S (7) by the same default father; N (8) is a living man.  With `living_namesake`, N carries
    the default father's own name and looks."""
    people: dict[int, gen.Person] = {}

    def add(pid, name, head, body, sex, years, alive=True, father=None, mother=None, **extra):
        people[pid] = gen.Person(pid, name, head, body, sex=sex, age=None if years is None else years * Y,
                                 alive=alive, father=father, mother=mother, first_seen=FIRST, **extra)

    add(1, father[0], father[1], father[2], "Male", None, alive=False)
    add(2, "M", 10, 10, "Female", 40, arrived=True, how="Founder")
    add(3, "C1", 11, 11, "Male", 20, father=1, mother=2, birth_record=0)
    add(4, "C2", 12, 12, "Female", 18, father=1, mother=2, birth_record=1)
    add(6, "W", 13, 13, "Female", 40, arrived=True, how="Founder")
    add(7, "S", 14, 14, "Male", 19, father=1, mother=6, birth_record=2)
    if living_namesake:
        add(8, father[0], father[1], father[2] + 1, "Male", 30, arrived=True, how="Founder")
    v = gen.Village(game, 1, "Test Tribe", people)
    for p in people.values():
        p.placeholder = gen.is_placeholder_father(game, p)
    gen._generations(v, {FIRST: set(people)})
    gen.number_people(v)
    return v


DEFAULTS = {2: ("?", 0, 0), 4: ("Joey", 2, 2), 5: ("Joey Joerson", 2, 2), 1: ("Unknown", 0, 0),
            3: ("Unknown", 0, 0)}


class PlaceholderKinTests(unittest.TestCase):
    def test_each_games_default_father_is_a_placeholder(self) -> None:
        for game, father in DEFAULTS.items():
            v = village(game, father)
            self.assertTrue(v.people[1].placeholder, (game, father))

    def test_a_default_father_is_shown_as_the_father(self) -> None:
        # The tree, Villager Info and the Matchmaker still name him: he is what the records say.
        for game, father in DEFAULTS.items():
            v = village(game, father)
            self.assertEqual([c.id for c in v.children_of(1)], [3, 4, 7], game)
            self.assertEqual(v.people[3].father, 1)

    def test_children_of_a_default_father_are_not_kin_through_him(self) -> None:
        for game, father in DEFAULTS.items():
            v = village(game, father)
            kin = gen.Kinship(v)
            self.assertEqual(kin.relatedness(3, 7), 0, game)                    # different mothers
            self.assertEqual(gen.relationship(v, 3, 7), "no recorded common ancestor", game)
            self.assertEqual(kin.relatedness(3, 4), Fraction(1, 4), game)       # the mother is real
            self.assertEqual(gen.relationship(v, 3, 4), "half siblings", game)
            self.assertNotIn(1, gen.ancestors(v, 3), game)

    def test_the_matchmaker_does_not_block_a_pair_over_a_default_father(self) -> None:
        for game, father in DEFAULTS.items():
            v = village(game, father)
            rules = gen.Rules(close_in_age=False, no_shared_ancestors=True, max_relatedness=True,
                              different_last_name=False, prefer_fresh_blood=False,
                              one_family_per_partner=True, block_half_siblings=True)
            _one, per_woman, _fallback = gen.suggest(v, rules)
            pairs = {(p.man.id, p.woman.id) for ps in per_woman.values() for p in ps}
            self.assertIn((7, 4), pairs, game)             # only the default father in common
            self.assertNotIn((3, 4), pairs, game)          # still half siblings through M

    def test_a_living_villager_is_never_a_placeholder(self) -> None:
        for game in (4, 5):
            p = gen.Person(9, "Joey", 2, 2, sex="Male", age=30 * Y, alive=True)
            self.assertFalse(gen.is_placeholder_father(game, p))
        p = gen.Person(9, "Unknown", 0, 0, sex="Male", alive=False, gone="died")
        self.assertFalse(gen.is_placeholder_father(1, p), "a dead villager with a Death record is real")
        p = gen.Person(9, "?", 0, 0, sex="Male", alive=False, father=1)
        self.assertFalse(gen.is_placeholder_father(2, p), "a villager with parents is real")

    def test_a_living_namesake_is_not_related_to_the_events_babies(self) -> None:
        v = village(4, ("Joey", 2, 2), living_namesake=True)
        self.assertFalse(v.people[8].placeholder)
        self.assertEqual(gen.relationship(v, 8, 3), "no recorded common ancestor")

    def test_only_games_with_the_default_have_it(self) -> None:
        # VV1 and VV3 conception callers never pass "?" or "Joey"; there they are ordinary names.
        p = gen.Person(1, "Joey", 2, 2, sex="Male", alive=False)
        self.assertFalse(gen.is_placeholder_father(3, p))
        self.assertFalse(gen.is_placeholder_father(1, p))
        p = gen.Person(1, "?", 0, 0, sex="Male", alive=False)
        self.assertFalse(gen.is_placeholder_father(4, p))


class ExportWordingTests(unittest.TestCase):
    """The Conception record of a default father: his name, head and body as the game wrote them on
    the mother; no age, sex, likes or dislikes, said as such -- never "(not captured)", which reads
    as a capture that failed, and never a by-name scan, which would find a living namesake."""

    def test_the_export_names_each_games_default(self) -> None:
        src = EXPORT_C.read_text(encoding="utf-8")
        fn = src[src.index("static int is_game_default_father"):]
        fn = fn[:fn.index("\n}\n")]
        self.assertIn('game_id == GAME_VV2', fn)
        self.assertIn('strcmp(name, "?") == 0', fn)
        self.assertIn('game_id == GAME_VV4 || game_id == GAME_VV5', fn)
        self.assertIn('strcmp(name, "Joey") == 0 || strcmp(name, "Joey Joerson") == 0', fn)
        self.assertIn('#define DEFAULT_FATHER_NONE "(none: game\'s default father)"', src)
        # No scan for a default father: the lookup is skipped when it is one.
        self.assertRegex(src, r"if \(father == NULL && !default_father\) \{\s+father = find_record_by_name")
        self.assertLess(len("(none: game's default father)") + 1, 32, "fits the father_age buffer")

    def test_vv1_fallback_is_unknown_zero_zero(self) -> None:
        src = VV1_C.read_text(encoding="utf-8")
        self.assertIn('#define VV1_FALLBACK_FATHER "Unknown"', src)
        body = src[src.index("static void vv1_set_father"):]
        body = body[:body.index("\n}\n")]
        self.assertIn("vv1_father_capture_on()", body)
        self.assertIn("vv1_plus_one(0)", body)


class StockExecutableTests(unittest.TestCase):
    """The defaults are the games' own: each literal and the conception call that passes it."""

    def setUp(self) -> None:
        if not all(any(STOCK[n].glob("*.exe")) for n in (2, 4, 5)):
            self.skipTest("the stock executables are not in inputs/")

    @staticmethod
    def image(n: int) -> tuple[bytes, int, list]:
        exe = next(STOCK[n].glob("*.exe"))
        data = exe.read_bytes()
        pe = struct.unpack_from("<I", data, 0x3C)[0]
        sections = struct.unpack_from("<H", data, pe + 6)[0]
        opt = struct.unpack_from("<H", data, pe + 20)[0]
        base = struct.unpack_from("<I", data, pe + 24 + 28)[0]
        table = []
        for k in range(sections):
            at = pe + 24 + opt + 40 * k
            vsize, va, rsize, raw = struct.unpack_from("<IIII", data, at + 8)
            table.append((va, max(vsize, rsize), raw))
        return data, base, table

    @staticmethod
    def at_va(img, va: int, length: int) -> bytes:
        data, base, table = img
        for sva, size, raw in table:
            if base + sva <= va < base + sva + size:
                o = raw + va - base - sva
                return data[o:o + length]
        raise AssertionError(hex(va))

    def test_vv2_gong_passes_question_mark_with_zero_looks(self) -> None:
        img = self.image(2)
        self.assertEqual(self.at_va(img, 0x476290, 2), b"?\0")
        # push ebx; push ebx; push 0x476290 ... call 0x44B980 (the conception routine), ebx = 0
        code = self.at_va(img, 0x44EB1D, 0x26)
        self.assertEqual(code[:7], bytes.fromhex("5353" "6890624700"))
        call = 0x44EB3E
        rel = struct.unpack_from("<i", self.at_va(img, call + 1, 4))[0]
        self.assertEqual(call + 5 + rel, 0x44B980)

    def test_vv4_and_vv5_events_pass_joey_with_looks_two_two(self) -> None:
        for n, joey, push, call, routine in ((4, 0x4AB360, 0x467C00, 0x467C15, 0x45E7B0),
                                             (5, 0x4B8E1C, 0x471B58, 0x471B6D, 0x465E00)):
            img = self.image(n)
            self.assertEqual(self.at_va(img, joey, 5), b"Joey\0", n)
            # push 2 (body); push 2 (head); push "Joey"
            self.assertEqual(self.at_va(img, push, 9), bytes.fromhex("6a02" "6a02" "68") + struct.pack("<I", joey), n)
            rel = struct.unpack_from("<i", self.at_va(img, call + 1, 4))[0]
            self.assertEqual(call + 5 + rel, routine, n)

    def test_vv1_and_vv3_have_no_default_father(self) -> None:
        for n in (1, 3):
            if not any(STOCK[n].glob("*.exe")):
                self.skipTest("stock executable missing")
            data = next(STOCK[n].glob("*.exe")).read_bytes()
            self.assertNotIn(b"\0Joey\0", data, n)


if __name__ == "__main__":
    unittest.main()
