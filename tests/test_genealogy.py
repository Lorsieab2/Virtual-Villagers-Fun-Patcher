"""The Family Tree Maker and the Village Matchmaker: the family read into generations, how two villagers are related, the
pairing rules, and the family tree (its layout, edits, backgrounds and pictures).

The owner (2026-10): "THE GENEALOGY HELPER: A log that tells you exactly who's descended from
whom, what generation they're in.  Helps you pair up villagers according to the rules the player
sets and generates a family tree for the current save file!"

The village here is built by hand, so every relation is known:

    founders  A (m) x B (f)        C (m) x D (f)
    gen II    E (m), F (f)         G (m), H (f)
    gen III   I (m), J (f): twins of E x H       K (m): G x F
              -> I and K are double first cousins (each of K's parents is a sibling of one of I's)
    X (f): arrived when generation II was the newest in the village; X is in generation II.
"""
from __future__ import annotations

import json
import math
import struct
import sys
import tempfile
import unittest
import xml.dom.minidom
import zlib
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_family_tree as ft  # noqa: E402
import vv_gdiplus  # noqa: E402
import vv_genealogy as gen  # noqa: E402
import vv_genealogy_window as gw  # noqa: E402
import vv_tree_editor_tools as tools  # noqa: E402

Y = gen.UNITS_PER_YEAR
FIRST = "2026-01-01 10:00:00"
# The rule tests start from these, the Matchmaker's first defaults, and switch on what they test.
BASE = dict(close_in_age=False, no_shared_ancestors=False, max_relatedness=False, different_last_name=False,
            prefer_fresh_blood=False, one_family_per_partner=False)


def R(**rules) -> gen.Rules:
    return gen.Rules(**{**BASE, **rules})


LATER = "2026-03-01 10:00:00"


def village() -> gen.Village:
    people: dict[int, gen.Person] = {}

    def add(pid, name, sex, years, father=None, mother=None, **extra):
        people[pid] = gen.Person(pid, name, pid, pid, sex=sex, age=years * Y, alive=True, father=father,
                                 mother=mother, first_seen=FIRST, **extra)

    add(1, "A", "Male", 70, arrived=True, how="Founder")
    add(2, "B", "Female", 69, arrived=True, how="Founder")
    add(3, "C", "Male", 68, arrived=True, how="Founder")
    add(4, "D", "Female", 67, arrived=True, how="Founder")
    add(5, "E", "Male", 45, 1, 2, family=1)
    add(6, "F", "Female", 44, 1, 2, family=1)
    add(7, "G", "Male", 43, 3, 4, family=2)
    add(8, "H", "Female", 42, 3, 4, family=2)
    add(9, "I", "Male", 20, 5, 8, litter=1, birth_record=0)
    add(10, "J", "Female", 20, 5, 8, litter=1, birth_record=1)
    add(11, "K", "Male", 19, 7, 6, birth_record=2)
    add(12, "X", "Female", 30, arrived=True, how="Custom Island Event")
    people[12].first_seen = LATER
    v = gen.Village(1, 1, "Test Tribe", people)
    snapshots = {FIRST: set(range(1, 12)), LATER: set(range(1, 13))}
    gen._generations(v, snapshots)
    gen.number_people(v)
    return v


class GenerationTests(unittest.TestCase):
    def test_founders_children_and_grandchildren(self) -> None:
        v = village()
        self.assertEqual([v.people[q].generation for q in (1, 2, 3, 4)], [1, 1, 1, 1])
        self.assertEqual([v.people[q].generation for q in (5, 6, 7, 8)], [2, 2, 2, 2])
        self.assertEqual([v.people[q].generation for q in (9, 10, 11)], [3, 3, 3])

    def test_an_arrival_joins_the_newest_generation_present_not_the_founders(self) -> None:
        # The owner: "do not put arrivals in the same generation with the founders.  put them in
        # the same generation as when they appear first in the logs."
        self.assertEqual(village().people[12].generation, 3)

    def test_numbers_never_restart_and_go_generation_by_generation(self) -> None:
        v = village()
        numbers = sorted((p.number, p.generation) for p in v.known())
        self.assertEqual([n for n, _g in numbers], list(range(1, 13)))
        self.assertEqual([g for _n, g in numbers], sorted(g for _n, g in numbers))

    def test_every_sort_numbers_everyone_once(self) -> None:
        v = village()
        for sort in gen.SORTS:
            gen.number_people(v, sort)
            self.assertEqual(sorted(p.number for p in v.known()), list(range(1, 13)), sort)
        gen.number_people(v, "age")
        self.assertLess(v.people[1].number, v.people[4].number)     # 70 before 67 years old


class KinshipTests(unittest.TestCase):
    def test_relationships(self) -> None:
        v = village()
        cases = {
            (5, 6): "full siblings",
            (9, 10): "twins",
            (1, 9): "grandparent and grandchild",
            (1, 5): "parent and child",
            (6, 9): "aunt or uncle and niece or nephew",
            (9, 11): "double first cousins",
            (5, 8): "no recorded common ancestor",
        }
        for (a, b), words in cases.items():
            self.assertEqual(gen.relationship(v, a, b), words, (a, b))

    def test_relatedness(self) -> None:
        kin = gen.Kinship(village())
        self.assertEqual(kin.relatedness(5, 6), Fraction(1, 2))
        self.assertEqual(kin.relatedness(9, 11), Fraction(1, 4))       # double first cousins
        self.assertEqual(kin.relatedness(5, 8), 0)


class RuleTests(unittest.TestCase):
    def pairs(self, **rules) -> set[tuple[str, str]]:
        one, per_woman, _fallback = gen.suggest(village(), R(**rules))
        return {(p.man.name, p.woman.name) for pairs in per_woman.values() for p in pairs}

    def test_the_age_window_and_its_toggles(self) -> None:
        self.assertNotIn(("A", "B"), self.pairs())                       # 50 and older: off
        self.assertIn(("A", "B"), self.pairs(allow_50_plus=True))
        self.assertIn(("A", "B"), self.pairs(plan_ahead=True))

    def test_close_family_is_a_toggle_too(self) -> None:
        # The owner: "allow rules for close family. It's a small island ... All these should be
        # optional toggles."
        self.assertNotIn(("E", "F"), self.pairs())
        self.assertIn(("E", "F"), self.pairs(block_full_siblings=False))
        self.assertIn(("K", "J"), self.pairs())
        self.assertNotIn(("K", "J"), self.pairs(block_first_cousins=True))

    def test_shared_ancestors_and_relatedness_limits(self) -> None:
        self.assertNotIn(("K", "J"), self.pairs(no_shared_ancestors=True))
        self.assertIn(("E", "H"), self.pairs(no_shared_ancestors=True))
        self.assertNotIn(("K", "J"), self.pairs(max_relatedness=True, max_relatedness_percent=12.5))
        self.assertIn(("K", "J"), self.pairs(max_relatedness=True, max_relatedness_percent=25))

    def test_closeness_in_age_and_last_names(self) -> None:
        self.assertIn(("G", "X"), self.pairs())
        self.assertNotIn(("G", "X"), self.pairs(close_in_age=True, max_age_gap_years=10))
        self.assertIn(("G", "H"), self.pairs(block_full_siblings=False))
        self.assertNotIn(("G", "H"), self.pairs(block_full_siblings=False, different_last_name=True))
        # The owner: "NEWCOMERS/ARRIVALS/FOUNDERS ARE SEPARATE UNRELATED INDIVIDUALS. for all intents and
        # purposes!" -- a family number an arrival shares by chance does not block her.
        v = village()
        v.people[12].family = 2
        _pairs, per_woman, _least = gen.suggest(v, R(different_last_name=True))
        every = {(p.man.name, p.woman.name) for ps in per_woman.values() for p in ps}
        self.assertIn(("G", "X"), every)

    @staticmethod
    def small(*rows) -> gen.Village:
        """A village from (pid, name, sex, years, father, mother) rows."""
        people = {pid: gen.Person(pid, name, pid, pid, sex=sex, age=years * Y, alive=True, father=father,
                                  mother=mother, first_seen=FIRST)
                  for pid, name, sex, years, father, mother in rows}
        v = gen.Village(1, 1, "Test Tribe", people)
        gen._generations(v, {FIRST: set(people)})
        gen.number_people(v)
        return v

    def test_born_as_lines_decide_which_births_came_together(self) -> None:
        # Codex, #555: Repair Saves & Logs' "Born as:" answer is believed over the records' order.
        def birth(child: str, head: int, born_as: str = "") -> str:
            return (f"Birth\n  Child: {child}\n    Head: {head}\n    Body: {head}\n"
                    f"  Mother: Ann\n    Head: 1\n    Body: 1\n  Father: Bob\n    Head: 2\n    Body: 2\n"
                    + (f"  Born as: {born_as}\n" if born_as else ""))
        records = [birth("Cy", 3, "Single birth"), birth("Di", 4, "Single birth"),     # two singles in a row
                   birth("Ed", 5, "Twin"), birth("Fa", 6, "Twin"), birth("Gu", 7, "Twin"),
                   birth("Ha", 8, "Twin")]                                        # two pairs of twins
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp) / "Virtual Villagers Fun Patcher Logs" / "Births and Conceptions"
            logs.mkdir(parents=True)
            (logs / "Virtual Villagers 1 Births and Conceptions Log 1.txt").write_text(
                "Village: Test Tribe (Save 1)\n\n" + "\n".join(records), encoding="utf-8")
            reg = gen._Registry()
            gen._births(reg, Path(tmp), 1, 1)
        litter = {p.name: p.litter for p in reg.people.values() if p.name not in ("Ann", "Bob")}
        self.assertIsNone(litter["Cy"])
        self.assertIsNone(litter["Di"])
        self.assertEqual(litter["Ed"], litter["Fa"])
        self.assertEqual(litter["Gu"], litter["Ha"])
        self.assertNotEqual(litter["Fa"], litter["Gu"])

    def test_relatedness_ignores_the_trees_display_generations(self) -> None:
        # Codex, #555: "Move to generation" only moves where a villager is drawn.
        v = village()
        kin = gen.Kinship(v)
        before = kin.relatedness(9, 5)                  # child and father
        v.people[9].generation = 1                      # drawn among the founders
        self.assertEqual(gen.Kinship(v).relatedness(9, 5), before)
        self.assertEqual(before, Fraction(1, 2))

    def test_the_nearest_common_ancestor_is_the_nearest_all_told(self) -> None:
        # Codex, #555: two up and two down (first cousins) is nearer than one up and three down.
        v = self.small((1, "G", "Male", 80, None, None), (2, "P", "Male", 60, 1, None),
                       (3, "Q", "Male", 58, 1, None), (4, "A", "Male", 30, 2, None),
                       (5, "N", "Female", 45, 2, None), (6, "M", "Female", 28, None, 5),
                       (7, "B", "Female", 20, 3, 6))
        self.assertEqual(gen.relationship(v, 4, 7), "first cousins")

    def test_one_partner_each_for_as_many_as_the_rules_allow(self) -> None:
        # Codex, #555: the best pair first (W2 with M1) would leave W1 alone; W2 with M2 pairs both.
        v = self.small((1, "M1", "Male", 30, None, None), (2, "M2", "Male", 45, None, None),
                       (3, "W1", "Female", 20, None, None), (4, "W2", "Female", 30, None, None))
        pairs, _per, _least = gen.suggest(v, R(close_in_age=True, max_age_gap_years=15))
        self.assertEqual({(p.man.name, p.woman.name) for p in pairs}, {("M1", "W1"), ("M2", "W2")})

    def test_last_names_carried_are_compared_and_no_number_is_none(self) -> None:
        v = self.small((1, "Bob Lee", "Male", 30, None, None), (2, "Ann Lee", "Female", 28, None, None),
                       (3, "Cy Kay", "Male", 31, None, None))
        for p in v.people.values():
            p.family = 7                                # one family number, by chance
        allowed = {(p.man.name, p.woman.name) for ps in gen.suggest(v, R(different_last_name=True))[1].values()
                   for p in ps}
        self.assertEqual(allowed, {("Cy Kay", "Ann Lee")})
        v.people[1].number = None                       # taken off the tree
        self.assertEqual(gen.numbered(v.people[1]), "Bob Lee")
        self.assertNotIn("#None", gen.pair_report(v, R(), "A New Home"))

    def test_numbers_never_make_a_new_family_and_one_family_per_partner(self) -> None:
        # The owner: "Roman Numerals after last names ARE NOT a different last name (Wanjiko is the same
        # as Wanjiko II)" -- "Hoani has already fathered a child with a Wanjiko but now he's suggested
        # for a Wanjiko II".
        v = self.small((1, "Hoani Chuchip", "Male", 31, None, None), (2, "Meka Wanjiko", "Female", 36, None, None),
                       (3, "Suki Wanjiko II", "Female", 32, None, None), (4, "Kaula Akikai II", "Female", 32, None, None),
                       (5, "Uan Wanjiko I", "Male", 33, None, None), (6, "Tia Chuchip", "Female", 1, 1, 2))

        def allowed(**rules):
            return {(p.man.name, p.woman.name) for ps in gen.suggest(v, R(**rules))[1].values() for p in ps}

        self.assertNotIn(("Uan Wanjiko I", "Suki Wanjiko II"), allowed(different_last_name=True))
        self.assertIn(("Uan Wanjiko I", "Suki Wanjiko II"), allowed())
        self.assertIn(("Hoani Chuchip", "Suki Wanjiko II"), allowed())
        self.assertNotIn(("Hoani Chuchip", "Suki Wanjiko II"), allowed(one_family_per_partner=True))
        # ... but the same partner again is always fine (the owner: "stop him only from moving on to a second person from the same family").
        self.assertIn(("Hoani Chuchip", "Meka Wanjiko"), allowed(one_family_per_partner=True))
        self.assertIn(("Hoani Chuchip", "Kaula Akikai II"), allowed(one_family_per_partner=True))
        self.assertTrue(gen.Rules().one_family_per_partner)        # on by default

    def test_an_expecting_mother_is_left_out_unless_the_player_says(self) -> None:
        v = village()
        v.people[8].expecting = True
        names = {w.name for w in gen.candidates(v, R())[1]}
        self.assertNotIn("H", names)
        self.assertIn("H", {w.name for w in gen.candidates(v, R(not_expecting=False))[1]})

    def test_the_window_offers_every_rule(self) -> None:
        self.assertEqual({name for name, _w, _k in gw.RULE_FIELDS}, set(gen.Rules.__dataclass_fields__))
        rules = gw.rules_from({"close_in_age": True, "max_age_gap_years": "7", "max_relatedness_percent": "x"})
        self.assertTrue(rules.close_in_age)
        self.assertEqual(rules.max_age_gap_years, 7)
        self.assertEqual(rules.max_relatedness_percent, R().max_relatedness_percent)


def png(path: Path, width: int, height: int, alpha) -> None:
    """An 8-bit RGBA PNG whose pixel (x, y) has alpha(x, y)."""
    rows = b"".join(b"\0" + b"".join(bytes((0, 0, 0, alpha(x, y))) for x in range(width)) for y in range(height))

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))

    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def png_alpha_at(path: Path, x: int, y: int) -> int:
    """The alpha of pixel (x, y) in an 8-bit RGBA PNG (as GDI+ saves one), its rows unfiltered."""
    data = path.read_bytes()
    at, idat, width = 8, b"", 0
    while at < len(data):
        size, kind = struct.unpack(">I4s", data[at:at + 8])
        body = data[at + 8:at + 8 + size]
        if kind == b"IHDR":
            width, _h, depth, colour = struct.unpack(">IIBB", body[:10])
            assert (depth, colour) == (8, 6)
        elif kind == b"IDAT":
            idat += body
        at += 12 + size
    raw, stride, prev = zlib.decompress(idat), width * 4, bytes(width * 4)
    for r in range(y + 1):
        kind, line = raw[r * (stride + 1)], bytearray(raw[r * (stride + 1) + 1:(r + 1) * (stride + 1)])
        for i in range(stride):
            a, b, c = (line[i - 4] if i >= 4 else 0), prev[i], (prev[i - 4] if i >= 4 else 0)
            if kind == 1:
                line[i] = (line[i] + a) & 255
            elif kind == 2:
                line[i] = (line[i] + b) & 255
            elif kind == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        prev = bytes(line)
    return prev[x * 4 + 3]


class TreeTests(unittest.TestCase):
    def test_colours_typed_as_hex_or_red_green_blue(self) -> None:
        for text in ("#D4A017", "d4a017", "212, 160, 23", "rgb(212,160,23)"):
            self.assertEqual(ft.parse_colour(text), "#d4a017", text)
        for text in ("", "#12345", "300,0,0", "orange-ish"):
            self.assertIsNone(ft.parse_colour(text), text)

    def test_typed_text_wraps_instead_of_being_cut(self) -> None:
        self.assertEqual(ft._wrap("Typed by the player, who types a lot"),
                         ["Typed by the", "player, who types", "a lot"])
        self.assertEqual(ft._wrap("x" * 20), ["x" * 17, "xxx"])
        self.assertTrue(all(len(line) <= ft.WRAP for line in ft._wrap("a " * 40)))

    def test_edits_round_trip_and_a_bad_file_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "edits.json"
            edits = ft.Edits(title="Ours", marks={"Tribal Chief": "#d4a017"}, background_opacity=35,
                             entries={"I|9|9": {"mark": "Tribal Chief", "lines": ["One", "Two"]}})
            edits.save(path)
            back = ft.Edits.load(path)
            self.assertEqual((back.title, back.marks, back.entries, back.background_opacity),
                             (edits.title, edits.marks, edits.entries, 35))
            data = json.loads(path.read_text(encoding="utf-8"))
            data["background_opacity"] = 400
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(ft.Edits.load(path).background_opacity, 100)
            path.write_text("{not json", encoding="utf-8")
            with self.assertRaises(ValueError):
                ft.Edits.load(path)

    def test_the_games_pictures_are_found_in_each_games_folder(self) -> None:
        # The games' logos come from each game's own folder.
        with tempfile.TemporaryDirectory() as tmp:
            vv1, vv4 = Path(tmp) / "vv1", Path(tmp) / "vv4"
            vv1.mkdir()
            vv4.mkdir()
            (vv1 / "logo1.png").write_bytes(b"x")
            (vv4 / "logo1.png").write_bytes(b"x")
            library = {1: vv1, 4: vv4}
            self.assertEqual(ft.picture_path("game:logo1.png", vv1), vv1 / "logo1.png")
            self.assertEqual(ft.picture_path("vv4:logo1.png", vv1, library), vv4 / "logo1.png")
            self.assertIsNone(ft.picture_path("vv5:logo1.png", vv1, library))

    def test_the_owners_backgrounds_ship_with_the_patcher(self) -> None:
        # The owner: "I want these and only these backgrounds as defaults: along with your plain
        # gradient ones" -- ten pictures of their own, then the starry night ("add this for a background
        # too!"), always offered, every one a PNG.
        pictures = [p[3] for p in ft.PRESETS if p[3]]
        self.assertEqual(len(pictures), 11)
        self.assertEqual(set(ft.PRESET_FITS) - set(pictures), set())
        self.assertTrue(set(ft.PRESET_FITS.values()) <= set(ft.FITS))
        self.assertTrue(all(p.startswith("asset:") for p in pictures))
        for ref in pictures:
            path = ft.picture_path(ref, None)
            self.assertIsNotNone(path, ref)
            self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(ft.presets_available(None, {}), ft.PRESETS)
        release = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        for ref in pictures:
            self.assertIn(f'"assets/genealogy/backgrounds/{ref[6:]}"', release)

    def test_presets_are_named_once_and_name_real_colours(self) -> None:
        names = [p[0] for p in ft.PRESETS]
        self.assertEqual(len(names), len(set(names)))
        for _name, colour, colour2, _picture in ft.PRESETS:
            self.assertTrue(ft.is_colour(colour))
            self.assertTrue(colour2 == "" or colour2 in ft.RAINBOWS or ft.is_colour(colour2))

    def test_words_on_a_dark_background_turn_light(self) -> None:
        lay = ft.layout(village(), ft.Edits(background="#16302f"))
        self.assertEqual(lay.ink, ft.LIGHT_INK)
        self.assertEqual(lay.portrait_ink, ft.INK)                      # the portraits are white
        self.assertEqual(ft.layout(village(), ft.Edits()).ink, ft.INK)

    def test_the_scene_draws_everyone_twins_by_a_triangle_and_parses_as_svg(self) -> None:
        v = village()
        v.people[8].expecting = True
        v.people[13] = gen.Person(13, "Upcoming child", -1, -1, upcoming=True, mother=8, father=5, generation=3)
        lay = ft.layout(v, ft.Edits(marks={"Tribal Chief": "#d4a017"},
                                    entries={ft.entry_key(v, v.people[1]): {"mark": "Tribal Chief"}}))
        sc = ft.scene(lay, "Virtual Villagers - A New Home", {})
        self.assertEqual(set(sc.boxes), set(v.people))
        self.assertTrue(any(isinstance(i, ft.Shape) and i.kind == "diamond" for i in sc.items))
        self.assertTrue(any(isinstance(i, ft.Shape) and i.stroke == "#d4a017" and i.pid == 1 for i in sc.items))
        texts = [i.text for i in sc.items if isinstance(i, ft.Text)]
        self.assertIn("Tribal Chief", texts)
        self.assertIn("1400 game units", texts)
        self.assertIn("70 years old", texts)
        # The twins hang from one point that opens into a triangle: two legs from one apex, each
        # down to a twin, and a bar between the legs.
        connectors = ft.lines(lay)
        twins = {lay.x[q] + ft.NODE_W / 2 for q in (9, 10)}
        legs = [pts for _c, pts, _f, _p in connectors if len(pts) == 3 and pts[1][0] in twins]
        self.assertEqual(len(legs), 2)
        self.assertEqual(legs[0][0], legs[1][0])
        base = legs[0][1][1]
        bars = [pts for _c, pts, _f, _p in connectors if pts[0] == (min(twins), base) and pts[-1] == (max(twins), base)]
        self.assertEqual(len(bars), 1)
        svg = ft.to_svg(sc, {})
        xml.dom.minidom.parseString(svg)

    def test_every_age_shows_the_young_head_in_every_game(self) -> None:
        young = {1: "male_heads.png", 2: "male_heads.png", 3: "male_heads.png", 4: "male_heads00.png",
                 5: "male_heads00.png"}
        for game, sheet in young.items():
            for age in (0, 1099, 1100, 5000):
                with self.subTest(game=game, age=age):
                    man = gen.Person(1, "Ann", 3, 4, sex="Male", age=age, alive=True)
                    woman = gen.Person(2, "Bea", 3, 4, sex="Female", age=age, alive=True)
                    self.assertEqual(ft.sheet_name(game, man), sheet)
                    self.assertEqual(ft.sheet_name(game, woman), sheet.replace("male", "female"))
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("male_heads.png", "female_heads.png", "male_heads_old.png", "female_heads_old.png"):
                (Path(tmp) / name).write_bytes(b"")
            self.assertEqual(set(ft.sheets_present(3, Path(tmp))), {"male_heads.png", "female_heads.png"})

    def test_head_boxes_read_the_visible_pixels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "heads.png"
            x0 = ft.HEAD_FRAME * ft.HEAD_W
            png(path, x0 + ft.HEAD_W, ft.HEAD_H * 2,
                lambda x, y: 255 if x0 + 10 <= x < x0 + 30 and ft.HEAD_H + 5 <= y < ft.HEAD_H + 25 else 0)
            boxes = ft.head_boxes(path)
            self.assertEqual(boxes.get(1), (10, 5, 30, 25))
            self.assertNotIn(0, boxes)

    @unittest.skipUnless(vv_gdiplus.available(), "Windows' own graphics")
    def test_the_picture_saves_as_png_and_jpg(self) -> None:
        sc = ft.scene(ft.layout(village(), ft.Edits(background2="#7fa86f")), "Virtual Villagers - A New Home", {})
        with tempfile.TemporaryDirectory() as tmp:
            for name, magic in (("tree.png", b"\x89PNG"), ("tree.jpg", b"\xff\xd8")):
                path = Path(tmp) / name
                self.assertTrue(vv_gdiplus.save_scene(sc, {}, path))
                self.assertEqual(path.read_bytes()[:len(magic)], magic)


class ColourTests(unittest.TestCase):
    """The owner: "distinct colors for every single individual unrelated person, siblings that
    share both parents to have the same color.  Each pairing has a single-color connector.  Each
    set of full siblings has a single-color connector that's different from their parents"."""

    def test_unrelated_people_full_siblings_and_pairings_each_have_their_own(self) -> None:
        lay = ft.layout(village())
        frame = lay.birth_colour
        founders = [frame[q] for q in (1, 2, 3, 4)]
        self.assertEqual(len(set(founders)), 4)
        self.assertEqual(frame[5], frame[6])                    # E and F: full siblings
        self.assertEqual(frame[9], frame[10])                   # the twins
        self.assertNotEqual(frame[9], frame[11])                # cousins
        used = founders + [frame[12]]
        for fam in lay.families:
            used.append(fam.colour)
            self.assertNotIn(fam.colour, {frame[fam.father], frame[fam.mother]})
        self.assertEqual(len(used), len(set(used)))
        # A pairing's whole connector -- the parents' line, the line down, the children's line --
        # is its one colour (the owner: "those should be the same color").
        for colour, _pts, fid, _piece in ft.lines(lay):
            self.assertEqual(colour, next(f.colour for f in lay.families if f.id == fid))

    def test_the_colours_are_far_apart_and_off_the_background(self) -> None:
        colours = ft.distinct_colours(40)
        self.assertEqual(len(set(colours)), 40)
        background = ft._lab(ft.BACKGROUND)
        labs = [ft._lab(c) for c in colours]
        self.assertGreater(min(math.dist(a, background) for a in labs), 20)
        self.assertGreater(min(math.dist(a, b) for i, a in enumerate(labs) for b in labs[i + 1:]), 15)
        self.assertNotIn("#000000", ft.distinct_colours(10, "#101010"))

    def test_the_players_colours_win(self) -> None:
        v = village()
        fam = next(f for f in ft.layout(v).families if f.father == 1)
        e = ft.Edits(person_colours={ft.entry_key(v, v.people[1]): "#123456"},
                     family_colours={ft.family_key(v, fam): "#abcdef"})
        lay = ft.layout(v, e)
        self.assertEqual(lay.birth_colour[1], "#123456")
        self.assertEqual(lay.birth_colour[5], "#abcdef")


class LineTests(unittest.TestCase):
    def test_no_line_runs_through_a_portrait(self) -> None:
        # S's parents are a generation apart: the older one's line goes round the frames between.
        v = village()
        v.people[14] = gen.Person(14, "S", 14, 14, sex="Female", age=300, alive=True, father=11, mother=6,
                                  first_seen=LATER)
        gen._generations(v, {FIRST: set(range(1, 12)), LATER: set(range(1, 13)) | {14}})
        gen.number_people(v)
        lay = ft.layout(v)
        frames = {q: (lay.x[q], lay.y[q], lay.x[q] + ft.NODE_W, lay.y[q] + ft.NODE_H) for q in lay.x}
        for _colour, pts, _fid, _piece in ft.lines(lay):
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                if x0 != x1:
                    continue
                for q, (fx0, fy0, fx1, fy1) in frames.items():
                    through = fx0 < x0 < fx1 and max(min(y0, y1), fy0 + 1) < min(max(y0, y1), fy1 - 1)
                    self.assertFalse(through, f"a line runs through {v.people[q].name}")

    def test_each_family_leaves_a_parent_at_its_own_point(self) -> None:
        lay = ft.layout(village())
        for q in lay.x:
            points = [f.drops[q] for f in lay.families if q in f.drops]
            self.assertEqual(len(points), len(set(points)))

    def test_no_two_families_lines_lie_on_each_other(self) -> None:
        # The owner: lines "can be as close as possible but not overlapping".
        for positioning in ft.POSITIONING:
            lay = ft.layout(village(), ft.Edits(positioning=positioning))
            assert_apart(self, ft.lines(lay))

    def test_a_moved_line_carries_the_lines_hanging_from_it(self) -> None:
        # The owner: "the vertical lines should move down/up if the horizontal line above them is
        # moved up/down".
        v = village()
        lay = ft.layout(v)
        fam = next(f for f in lay.families if 9 in f.children)          # the twins and their line
        key = ft.family_key(v, fam)
        lay.edits.line_moves[f"{key}|lane"] = [0.0, 9.0]
        drawn = [d for d in ft.lines(lay) if d[2] == fam.id]
        lane = next(pts for _c, pts, _f, piece in drawn if piece == "lane")
        y = lane[0][1]
        self.assertEqual(y, fam.lane_y + 9.0)
        lo, hi = sorted((lane[0][0], lane[1][0]))
        hanging = [pts for _c, pts, _f, piece in drawn if piece.startswith("to ") and pts[0][1] in (y, fam.lane_y)]
        self.assertTrue(hanging)
        for pts in hanging:
            self.assertEqual(pts[0][1], y)                              # each starts on the moved line
            self.assertTrue(lo <= pts[0][0] <= hi)
        stem = next(pts for _c, pts, _f, piece in drawn if piece == "stem")
        self.assertEqual(max(stem[0][1], stem[1][1]), y)                # the line from the parents too

    def test_a_line_moved_sideways_takes_its_hanging_lines_diagonally(self) -> None:
        # The owner: "move lines left/right and have them auto-adjust", "diagonal is ok" -- with
        # "Allow diagonal lines" ticked (it is off unless the player ticks it).
        v = village()
        lay = ft.layout(v, ft.Edits(diagonal_lines=True))
        fam = next(f for f in lay.families if 11 in f.children)
        key = ft.family_key(v, fam)
        before = {piece: pts for _c, pts, fid, piece in ft.lines(lay) if fid == fam.id}
        lay.edits.line_moves[f"{key}|lane"] = [30.0, 0.0]
        after = {piece: pts for _c, pts, fid, piece in ft.lines(lay) if fid == fam.id}
        self.assertEqual(after["lane"][0][0], before["lane"][0][0] + 30)
        hang = next(p for p in after if p.startswith("to "))
        self.assertEqual(after[hang][0][0], before[hang][0][0] + 30)        # its top went with the line
        self.assertEqual(after[hang][-1], before[hang][-1])                 # its foot stayed on the child
        self.assertTrue(on_line(after["stem"][-1], *after["lane"]))           # the line down still meets it

    def test_without_diagonals_a_dragged_line_moves_only_across_itself(self) -> None:
        v = village()
        lay = ft.layout(v)
        self.assertFalse(lay.edits.diagonal_lines)
        fam = next(f for f in lay.families if 11 in f.children)
        key = ft.family_key(v, fam)
        lay.edits.line_moves[f"{key}|lane"] = [30.0, 25.0]
        lay.edits.line_moves[f"{key}|stem"] = [15.0, 40.0]
        for _c, pts, _fid, piece in ft.lines(lay):
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                if piece.startswith(("leg ", "bar ")):
                    continue                    # a triplet's legs fan out by design
                self.assertTrue(x0 == x1 or y0 == y1, (piece, pts))
        assert_connected(self, lay, ft.lines(lay))

    def test_a_line_dragged_onto_another_is_not_carried_off_by_it(self) -> None:
        # The owner's pink line: the couple's line dragged down onto the children's line, then the
        # children's line dragged up -- the couple's line stays level and the line down joins them.
        v = village()
        lay = ft.layout(v)
        fam = next(f for f in lay.families if 9 in f.children)
        key = ft.family_key(v, fam)
        gap = fam.lane_y - fam.couple_y
        lay.edits.line_moves = {f"{key}|couple": [0.0, gap], f"{key}|lane": [0.0, -20.0]}
        mine = {piece: pts for _c, pts, fid, piece in ft.lines(lay) if fid == fam.id}
        couple, stem, lane = mine["couple"], mine["stem"], mine["lane"]
        self.assertEqual(couple[0][1], couple[1][1])                    # still level
        self.assertEqual(couple[0][1], fam.couple_y + gap)
        self.assertTrue(on_line(stem[0], *couple))                       # the line down starts on it
        self.assertTrue(on_line(stem[1], *lane))                         # and ends on the children's line
        self.assertEqual(lane[0][1], fam.lane_y - 20.0)

    def test_every_line_stays_connected_however_its_pieces_are_dragged(self) -> None:
        # The owner: "Please. Keep. The. Lines. Connected. No. matter. How. they. are. moved."
        import random
        pick = random.Random(7)
        for positioning in ft.POSITIONING:
            v = village()
            lay = ft.layout(v, ft.Edits(positioning=positioning))
            keys = {f.id: ft.family_key(v, f) for f in lay.families}
            pieces = [f"{keys[fid]}|{piece}" for _c, pts, fid, piece in ft.lines(lay) if len(pts) == 2]
            for _trial in range(25):
                lay.edits.line_moves = {piece: [pick.uniform(-80, 80), pick.uniform(-80, 80)]
                                        for piece in pick.sample(pieces, min(len(pieces), 6))}
                assert_connected(self, lay, ft.lines(lay))

    def test_a_line_moved_off_another_stays_whole(self) -> None:
        # [colour, points, family, piece, portrait ends, {end: the piece it is attached to}]
        drawn = [["#111111", [(10.0, 0.0), (10.0, 100.0)], 1, "a", {}, {}],
                 ["#222222", [(0.0, 50.0), (10.0, 50.0)], 2, "b", {}, {1: "c"}],
                 ["#222222", [(10.0, 50.0), (10.0, 150.0)], 2, "c", {}, {0: "b", 1: "d"}],
                 ["#222222", [(10.0, 150.0), (40.0, 150.0)], 2, "d", {}, {0: "c"}]]
        ft._separate(drawn)
        assert_apart(self, drawn)
        moved = drawn[2][1]
        self.assertNotEqual(moved[0][0], 10.0)
        self.assertEqual(drawn[1][1][1], moved[0])          # the level run before it follows
        self.assertEqual(drawn[3][1][0], moved[1])          # and the one after


def on_line(pt: tuple, a: tuple, b: tuple) -> bool:
    """Whether pt lies on the straight piece from a to b (within half a pixel)."""
    (px, py), (ax, ay), (bx, by) = pt, a, b
    if not (min(ax, bx) - 0.5 <= px <= max(ax, bx) + 0.5 and min(ay, by) - 0.5 <= py <= max(ay, by) + 0.5):
        return False
    length = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
    return length < 1e-9 or abs((bx - ax) * (py - ay) - (by - ay) * (px - ax)) / length < 0.5


def assert_connected(test: unittest.TestCase, lay, drawn: list) -> None:
    """Every end of every piece of a family's line lies on another piece of that line or on a
    portrait (the owner: "Keep. The. Lines. Connected.")."""
    frames = [(min(xs) - 1, min(ys) - 1, max(xs) + 1, max(ys) + 1) for xs, ys in (zip(*lay.frame_points(q)) for q in lay.x)]
    # A family whose children are on a later page ends at its "continued on page N" words: its lowest end.
    words = {max((pt for s in drawn if s[2] == f.id for pt in s[1]), key=lambda pt: (pt[1], pt[0]))
             for f in lay.families if getattr(f, "onward", None) and any(s[2] == f.id for s in drawn)}
    drawn = list(drawn) + [(None, [pt, pt], f.id, "words") for f in lay.families if getattr(f, "onward", None)
                           for pt in words if any(s[2] == f.id and pt in s[1] for s in drawn)]
    for colour, pts, fid, piece in drawn:
        mine = [o for o in drawn if o[2] == fid and o[1] is not pts]
        for pt in (pts[0], pts[-1]):
            joined = any(pt in o[1] or any(on_line(pt, a, b) for a, b in zip(o[1], o[1][1:])) for o in mine)
            framed = any(x0 <= pt[0] <= x1 and y0 <= pt[1] <= y1 for x0, y0, x1, y1 in frames)
            test.assertTrue(joined or framed, f"{piece} of family {fid} has a loose end at {pt}")


def assert_apart(test: unittest.TestCase, drawn: list) -> None:
    """No straight run of one family's line lies along another family's."""
    runs = [(s[2], s[1]) for s in drawn if len(s[1]) == 2]
    for i, (fa, a) in enumerate(runs):
        for fb, b in runs[:i]:
            if fa == fb:
                continue
            for axis in (0, 1):
                if a[0][axis] == a[1][axis] and b[0][axis] == b[1][axis] and abs(a[0][axis] - b[0][axis]) < 1:
                    lo = max(min(a[0][1 - axis], a[1][1 - axis]), min(b[0][1 - axis], b[1][1 - axis]))
                    hi = min(max(a[0][1 - axis], a[1][1 - axis]), max(b[0][1 - axis], b[1][1 - axis]))
                    test.assertLessEqual(hi - lo, 1, f"families {fa} and {fb} overlap: {a} {b}")


class StickerTests(unittest.TestCase):
    def test_a_sticker_is_kept_in_range(self) -> None:
        raw = ft.clean_sticker({"picture": "x.png", "cx": 1, "cy": 2, "w": -5, "h": 1e9, "angle": 725,
                                "opacity": 300, "flip_h": "yes"})
        self.assertEqual((raw["w"], raw["h"], raw["angle"], raw["opacity"], raw["flip_h"]),
                         (ft.STICKER_MIN, ft.STICKER_MAX, 5.0, 100.0, False))
        self.assertIsNone(ft.clean_sticker({"kind": "picture"}))
        box = ft.clean_sticker({"kind": "text", "text": "Hi", "align": "sideways", "colour": "red"})
        self.assertEqual((box["align"], box["colour"]), ("centre", ft.INK))

    def test_corners_keep_the_shape_and_edges_stretch(self) -> None:
        raw = ft.clean_sticker({"picture": "x.png", "cx": 100, "cy": 100, "w": 200, "h": 100})
        bigger = tools.resized(raw, "se", 300, 160)
        self.assertAlmostEqual(bigger["w"] / bigger["h"], 2.0)
        self.assertAlmostEqual(bigger["cx"] - bigger["w"] / 2, 0.0)            # the top left stays
        self.assertAlmostEqual(bigger["cy"] - bigger["h"] / 2, 50.0)
        free = tools.resized(raw, "se", 300, 160, free=True)
        self.assertEqual((round(free["w"]), round(free["h"])), (300, 110))
        wide = tools.resized(raw, "e", 260, 999)
        self.assertEqual((round(wide["w"]), round(wide["h"]), round(wide["cx"])), (260, 100, 130))
        turned = dict(raw, angle=90.0)
        self.assertAlmostEqual(tools.resized(turned, "e", 100, 260)["w"], 260.0)   # its right edge is at the bottom

    def test_a_turned_sticker_is_hit_inside_its_turned_box(self) -> None:
        st = ft.Sticker(0, None, 100, 100, 200, 20, angle=90)
        self.assertTrue(st.contains(100, 180))
        self.assertFalse(st.contains(180, 100))

    def test_a_copied_picture_becomes_a_png(self) -> None:
        header = struct.pack("<IiiHHIIiiII", 40, 2, 2, 1, 24, 0, 0, 0, 0, 0, 0)
        rows = b"".join(bytes((0, 0, 255) * 2) + b"\0\0" for _ in range(2))
        self.assertEqual(tools.png_from_dib(header + rows)[:8], b"\x89PNG\r\n\x1a\n")
        self.assertIsNone(tools.png_from_dib(b"short"))

    def test_stickers_and_text_boxes_draw_on_the_page(self) -> None:
        v = village()
        with tempfile.TemporaryDirectory() as tmp:
            picture = Path(tmp) / "star.png"
            png(picture, 4, 4, lambda x, y: 255)
            e = ft.Edits(stickers=[ft.new_sticker(str(picture), picture, 200, 200),
                                   ft.new_text_box(400, 100, "Kalahuna <family> & friends", "Georgia")])
            sc = ft.scene(ft.layout(v, e), "Virtual Villagers - A New Home", {})
            self.assertEqual(len(sc.stickers), 2)
            svg = ft.to_svg(sc, {})
            xml.dom.minidom.parseString(svg)
            self.assertIn("Kalahuna &lt;family&gt; &amp; friends", svg)
            if vv_gdiplus.available():
                self.assertTrue(vv_gdiplus.save_scene(sc, {}, Path(tmp) / "tree.png"))
                self.assertIsNotNone(vv_gdiplus.render_sticker(sc.stickers[1], Path(tmp) / "box.png", 2.0))

    def test_edits_keep_stickers_fonts_and_colours(self) -> None:
        e = ft.Edits(font="Georgia", styles={"title": {"font": "Papyrus", "scale": 130}},
                     stickers=[ft.new_text_box(1, 2, "x")], person_colours={"A|1|1": "#123456"})
        back = ft.Edits.from_data(json.loads(json.dumps(e.to_data())))
        self.assertEqual((back.font, back.styles, back.stickers, back.person_colours),
                         (e.font, e.styles, e.stickers, e.person_colours))

    def test_the_key_names_the_portrait_shapes_in_use(self) -> None:
        self.assertTrue(ft.footer(ft.layout(village(), ft.Edits())).startswith(
            "Males: squares; Females: circles; Babies on the way: diamonds."))
        e = ft.Edits()
        e.shapes["Female"], e.shapes["Male"] = "heart", "cross"
        self.assertIn("Males: crosses; Females: hearts;", ft.footer(ft.layout(village(), e)))

    def test_shapes_keep_their_own_proportions_and_can_be_resized_and_turned(self) -> None:
        # The owner: "i want the shapes to not look so squashed"; "drag their corners to resize
        # them and rotate them with a little rotator thing at the top".
        v = village()
        for kind in ft.PORTRAIT_SHAPES:
            e = ft.Edits()
            e.shapes = {g: kind for g in ft.GROUPS}
            lay = ft.layout(v, e)
            boxes = []
            for q in lay.x:
                x, y, w, h, angle = lay.frame(q)
                # A portrait tall -- a shape drawn turned (SHAPE_BAKES) as tall as it reached turned so.
                self.assertEqual((w, h, angle), (ft.natural_width(kind), ft.natural_height(kind), 0.0))
                if kind not in ft.SHAPE_BAKES:
                    self.assertEqual(h, ft.NODE_H)
                xs, ys = zip(*lay.frame_points(q))
                boxes.append((min(xs), min(ys), max(xs), max(ys)))
            for i, a in enumerate(boxes):           # spaced so no two frames overlap
                for b in boxes[i + 1:]:
                    self.assertTrue(a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1], kind)
            assert_connected(self, lay, ft.lines(lay))
        box = (100.0, 100.0, 50.0, 80.0, 0.0)
        self.assertEqual(tools.frame_dragged(box, "size", "se", 150, 180, False, False)[2:4], (100.0, 160.0))
        self.assertEqual(tools.frame_dragged(box, "size", "e", 150, 999, False, False)[2:4], (100.0, 80.0))
        self.assertEqual(tools.frame_dragged(box, "turn", "rotate", 140, 101, True, False)[4], 90)
        e = ft.Edits()
        p = next(iter(v.people.values()))
        e.entries[ft.entry_key(v, p)] = {"w": 5000, "h": 3, "angle": 450}
        back = ft.Edits.from_data(json.loads(json.dumps(e.to_data()))).entries[ft.entry_key(v, p)]
        self.assertEqual(back, {"w": ft.FRAME_MAX, "h": ft.FRAME_MIN})          # 450 is clamped to 360: none
        lay = ft.layout(v, ft.Edits(entries={ft.entry_key(v, p): {"w": 300.0, "angle": 30.0}}))
        assert_connected(self, lay, ft.lines(lay))
        sc = ft.scene(lay, "A New Home", {})
        self.assertIn("rotate(30 ", ft.to_svg(sc, {}))

    def test_a_resized_portraits_face_and_words_go_with_it_upright(self) -> None:
        # The owner, on Codex's #555 note: "shrink/grow with the frame, stay upright".
        v = village()
        p = v.people[9]
        e = ft.Edits()
        plain = [i for i in ft.scene(ft.layout(v, e), "A New Home", {}).items
                 if isinstance(i, ft.Text) and i.pid == 9]
        w0, h0 = ft.frame_size(e, v, p, own=False)
        e.entries[ft.entry_key(v, p)] = {"w": w0 / 2, "h": h0 / 2, "angle": 40.0}
        half = [i for i in ft.scene(ft.layout(v, e), "A New Home", {}).items if isinstance(i, ft.Text) and i.pid == 9]
        self.assertEqual([round(i.size * 2, 3) for i in half], [round(i.size, 3) for i in plain])
        lay = ft.layout(v, e)
        x, y, w, h, _a = lay.frame(9)
        self.assertTrue(all(x <= i.x <= x + w and y <= i.y <= y + h for i in half))     # inside the frame

    def test_a_square_portrait_has_its_frame_in_the_picture(self) -> None:
        # A square's corners have no rounding: GDI+ drew nothing for arcs of no size.
        if not vv_gdiplus.available():
            self.skipTest("Windows only")
        sc = ft.Scene(60, 60, ft.TRANSPARENT, [ft.Backdrop(ft.TRANSPARENT),
                                               ft.Shape("rect", 10, 10, 40, 40, "#000000", width=4, fill=None, radius=0)])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "square.png"
            self.assertTrue(vv_gdiplus.save_scene(sc, {}, out))
            self.assertEqual(png_alpha_at(out, 10, 30), 255)

    def test_a_childs_lines_follow_them_when_dragged_down(self) -> None:
        # The owner: lines "neat and not overlapping when moved to a new position".
        v = village()
        lay = ft.layout(v)
        fam = next(f for f in lay.families if len(f.children) == 1)
        child = fam.children[0]
        before = fam.lane_y
        e = ft.Edits()
        e.entries[ft.entry_key(v, v.people[child])] = {"dy": 200.0}
        lay = ft.layout(v, e)
        fam = next(f for f in lay.families if f.children == [child])
        self.assertEqual(fam.lane_y, before + 200)
        assert_connected(self, lay, ft.lines(lay))
        # Rows dragged by different amounts (with room left): a couple's line stays under the parents, above the
        # children's line -- never running along the parents' own row.
        e = ft.Edits()
        for p in v.people.values():
            if p.generation == 2:
                e.entries[ft.entry_key(v, p)] = {"dy": 40.0}
        lay = ft.layout(v, e)
        for fam in lay.families:
            parents = [q for q in (fam.father, fam.mother) if q in lay.x]
            if fam.couple_y and parents:
                self.assertGreater(fam.couple_y, max(lay.y[q] for q in parents) + ft.NODE_H - 1)
                self.assertLess(fam.couple_y, fam.lane_y)

    def test_a_click_counts_only_inside_the_shape(self) -> None:
        # The owner: "make the click area for things limited to the object themselves".
        circle = ft.shape_points("circle", 0, 0, 100, 100)
        self.assertTrue(ft.inside(circle, 50, 50))
        self.assertFalse(ft.inside(circle, 4, 4))                      # the empty corner
        heart = ft.shape_points("heart", 0, 0, 110, 100)
        self.assertFalse(ft.inside(heart, 55, 3))                      # the dip between the lobes
        self.assertTrue(ft.inside(heart, 55, 50))
        turned = ft.shape_points("rect", 0, 0, 100, 20, angle=90)
        self.assertTrue(ft.inside(turned, 50, 50))                     # turned upright about its middle
        self.assertFalse(ft.inside(turned, 90, 10))                    # where its end was before turning

    def test_lines_stay_on_portraits_resized_in_batch(self) -> None:
        # The owner: "when I batch change the portrait sizes, the lines should stay connected to them".
        v = village()
        for size in ([72.0, 72.0], [220.0, 220.0], [90.0, 40.0]):
            for kind in ("circle", "rect", "heart"):
                e = ft.Edits(sizes={g: size for g in ft.GROUPS}, shapes={g: kind for g in ft.GROUPS})
                lay = ft.layout(v, e)
                drawn = ft.lines(lay)
                assert_connected(self, lay, drawn)
                # The owner: "I said no bumps!" -- nothing in the way, so no line steps aside.
                self.assertFalse([piece for _c, _p, _f, piece in drawn
                                  if piece.startswith("to ") and not piece.endswith(" 0")], (size, kind))
                ends = [pt for _c, pts, _fid, _piece in drawn for pt in (pts[0], pts[-1])]
                for q in lay.x:                 # a line ending at a portrait (not at another piece) ends on its edge
                    xs, ys = zip(*lay.frame_points(q))
                    for _c, pts, _fid, _piece in drawn:
                        for x, y in (pt for pt in (pts[0], pts[-1]) if ends.count(pt) == 1):
                            if min(xs) + 1 < x < max(xs) - 1 and lay.y[q] - 5 <= y <= lay.y[q] + ft.NODE_H + 5:
                                self.assertTrue(any(abs(y - ft._edge_y(lay, q, x, b)) < 0.5 for b in (True, False)),
                                                (size, kind, q, (x, y)))

    def test_a_villager_given_a_last_name_keeps_their_tree_edits(self) -> None:
        # Codex, #555: Repair Saves & Logs' last names re-key the Family Tree Maker's edits.
        e = ft.Edits()
        e.entries["Ann|3|4"] = {"mark": "Chief"}
        e.entries["Joann|3|4"] = {"mark": "x"}
        e.entries["Ann|3|45"] = {"mark": "y"}
        e.family_colours["Bob|1|2||Ann|3|4"] = "#ff0000"
        e.line_moves["Bob|1|2||Ann|3|4|to Ann|3|4 0"] = [1.0, 2.0]
        e.hidden.append("line:Bob|1|2||Ann|3|4|lane")
        back = ft.Edits.from_data(json.loads(ft.renamed_keys(json.dumps(e.to_data()), {("Ann", 3, 4): "Ann Lee"})))
        self.assertEqual(sorted(back.entries), ["Ann Lee|3|4", "Ann|3|45", "Joann|3|4"])
        self.assertEqual(list(back.family_colours), ["Bob|1|2||Ann Lee|3|4"])
        self.assertEqual(list(back.line_moves), ["Bob|1|2||Ann Lee|3|4|to Ann Lee|3|4 0"])
        self.assertEqual(back.hidden, ["line:Bob|1|2||Ann Lee|3|4|lane"])

    def test_the_trees_own_words_can_be_retyped(self) -> None:
        # The owner: "I wanna rename "unrelated individuals" to something else".
        v = village()
        e = ft.Edits(words={"others": "Outsiders", "footer": "Our family"})
        lay = ft.layout(v, e)
        texts = {i.edit: i.text for i in ft.scene(lay, "A New Home", {}).items if isinstance(i, ft.Text) and i.edit}
        self.assertEqual(texts.get("word:others"), "Outsiders")
        self.assertEqual(texts["word:footer"], "Our family")
        self.assertIn("title", texts)
        self.assertTrue(any(k.startswith("person:") for k in texts) and any(k.startswith("label:") for k in texts))
        back = ft.Edits.from_data(json.loads(json.dumps(e.to_data())))
        self.assertEqual(back.words, e.words)
        self.assertEqual(ft.Edits.from_data({"words": {"others": 3, "nonsense": "x"}}).words, {})
        # The owner: "And default: "Other Members"".
        self.assertEqual(ft.words(ft.layout(v, ft.Edits()), "others"), "Other Members")
        # The owner: "I want headers to be separate from subheaders so I can delete "no recorded parent
        # or child"" -- the heading stays.
        e.hidden = ["word:others_note"]
        kept = {i.edit for i in ft.scene(ft.layout(v, e), "A New Home", {}).items if isinstance(i, ft.Text)}
        self.assertIn("word:others", kept)
        self.assertNotIn("word:others_note", kept)

    def test_a_long_family_on_several_unjoined_pages(self) -> None:
        # The owner: "MULTIPLE PAGES of the family tree ... the new pages are not connected to
        # previous pages".
        v = village()
        e = ft.Edits()
        ft.arrange(v, e)
        whole = ft.layout(v, e)
        gens = sorted({v.people[q].generation for q in whole.x})
        self.assertGreater(len(gens), 1)
        e.pages = [gens[1]]
        ft.arrange(v, e)
        first, second = ft.layout(v, e, 0), ft.layout(v, e, 1)
        self.assertEqual((first.pages, second.page), (2, 1))
        self.assertEqual(set(first.x) | set(second.x), set(whole.x))
        # The owner: "page 1 has generations 1-6.  The second page should have generations 6-12, with
        # the 6th generation on the second page being treated as "founders"": the generation the
        # second page starts at is on both, at the top of the second with no line up to a parent.
        shared = {q for q in whole.x if v.people[q].generation == gens[1]}
        self.assertEqual(set(first.x) & set(second.x), shared)
        self.assertEqual(ft.page_spans(e, v)[:2], [(gens[0], gens[1]), (gens[1], ft.page_spans(e, v)[1][1])])
        self.assertEqual(min(second.rows), gens[1])
        self.assertFalse(any(c in shared for fam in second.families for c in fam.children))
        self.assertTrue(all(q in second.birth_colour for q in shared), "coloured as founders")
        self.assertEqual(ft.generation_label(second, gens[1])[0], f"{gen.roman(gens[1])}. Generation {gens[1]}")
        self.assertEqual(set(first.others) | set(second.others), set(whole.others))
        for lay in (first, second):
            for fam in lay.families:
                self.assertTrue(all(c in lay.x for c in fam.children))
                self.assertTrue(any(q in lay.x for q in (fam.father, fam.mother) if q is not None))
            assert_connected(self, lay, ft.lines(lay))
        self.assertTrue(ft.title_lines(second, "A New Home")[0].endswith("Page 2 of 2"))
        self.assertEqual(ft.Edits.from_data({"pages": [3, 3, 1, "x", 7]}).pages, [3, 7])

    def test_batch_sizes_line_styles_and_glowing_marks(self) -> None:
        # The owner: "batch-changing portrait shape sizes ... line weights, types, absolutely
        # everything in batch!", "can marks be a "glow" around the portrait instead?", and the
        # defaults: males square, females circle, babies on the way a diamond with the same line.
        v = village()
        lay = ft.layout(v)
        man = next(q for q in lay.x if v.people[q].sex == "Male" and not v.people[q].upcoming)
        self.assertEqual(lay.frame(man)[2:4], (ft.NODE_H, ft.NODE_H))                 # a real square
        self.assertEqual(ft.DEFAULT_SHAPES, {"Male": "rect", "Female": "circle", "Upcoming": "diamond"})
        self.assertEqual(set(ft.DEFAULT_BORDERS.values()), {"thick"})
        e = ft.Edits(sizes={"Male": [120.0, 130.0]}, line_width=5.0, line_dash="dashed",
                     marks={"Chief": "#ff0000"}, mark_style="glow", mark_glow=20.0, mark_opacity=50)
        child = next(p for p in v.people.values() if p.father is not None and not p.upcoming)
        key = ft.family_key(v, ft.Family(0, child.father, child.mother, []))
        e.family_lines[key] = {"width": 9.0, "dash": "dotted"}
        e.entries[ft.entry_key(v, v.people[man])] = {"mark": "Chief"}
        back = ft.Edits.from_data(json.loads(json.dumps(e.to_data())))
        self.assertEqual(back.to_data(), e.to_data())
        lay = ft.layout(v, back)
        self.assertEqual(lay.frame(man)[2:4], (120.0, 130.0))
        sc = ft.scene(lay, "A New Home", {})
        for line in (i for i in sc.items if isinstance(i, ft.Line) and i.piece):
            mine = line.piece.startswith(key + "|")
            self.assertEqual((line.width, line.dash), (9.0, "dotted") if mine else (5.0, "dashed"))
        rings = [i for i in sc.items if isinstance(i, ft.Shape) and i.pid == man and i.target == ("mark", "Chief")]
        self.assertEqual(len(rings), ft.GLOW_RINGS)
        self.assertTrue(all(r.opacity <= 0.5 for r in rings))
        # The owner, 2026-10-08: "if I set the glow to be red, I'm expecting a vibrant red halo" -- the
        # chosen colour itself, at the mark's full opacity against the portrait, fading outward.
        self.assertTrue(all(r.stroke == "#ff0000" for r in rings))
        nearest = min(rings, key=lambda r: r.w)
        self.assertAlmostEqual(nearest.opacity, 0.5)
        self.assertEqual([r.opacity for r in sorted(rings, key=lambda r: r.w)],
                         sorted((r.opacity for r in rings), reverse=True))
        self.assertIn('stroke-dasharray="1.5 4"', ft.to_svg(sc, {}))
        self.assertEqual(ft.PORTRAIT_SHAPES["cross"], "Cross")
        self.assertIn((0.35, 1), ft.OUTLINES["cross"])        # upright, like a plus with a longer foot
        self.assertEqual(ft.PORTRAIT_SHAPES["x"], "X")

    def test_every_part_of_the_tree_has_its_own_opacity(self) -> None:
        # The owner: "there should be opacity settings for everything".
        e = ft.Edits(background_image="asset:green-tree.png", opacity={"words": 40, "portraits": 50, "lines": 30})
        sc = ft.scene(ft.layout(village(), e), "A New Home", {})
        seen = {}
        for i in sc.items:
            if isinstance(i, ft.Line) and i.piece:
                seen.setdefault("lines", set()).add(i.opacity)
            elif isinstance(i, ft.Shape) and i.target == ("plate",):
                seen.setdefault("plates", set()).add(i.opacity)
            elif getattr(i, "pid", None) is not None:
                seen.setdefault("portraits", set()).add(i.opacity)
            elif isinstance(i, ft.Text):
                seen.setdefault("words", set()).add(i.opacity)
        self.assertEqual(seen, {"lines": {0.3}, "plates": {0.8}, "portraits": {0.5}, "words": {0.4}})
        svg = ft.to_svg(sc, {})
        self.assertIn('opacity="0.3"', svg)
        self.assertIn('opacity="0.4"', svg)
        back = ft.Edits.from_data({"opacity": {"words": 500, "nonsense": 3}})
        self.assertEqual(back.opacity, {"words": 100})

    def test_generation_label_lines_delete_one_by_one_and_number_either_way(self) -> None:
        v = village()
        e = ft.Edits()
        lay = ft.layout(v, e)
        full = ft.generation_label(lay, 1)
        self.assertTrue(full[0].startswith("I. Generation 1"))
        e.hidden = ["label:1:number", "label:*:living"]
        lay = ft.layout(v, e)
        self.assertEqual(ft.generation_label(lay, 1), ["Generation 1"] + [t for t in full[1:] if "living" not in t])
        self.assertFalse(any("living" in t for g in lay.tops for t in ft.generation_label(lay, g)))
        self.assertEqual(ft.default_generation_label(lay, 1), ft.generation_label(lay, 1))
        e.numbering = "numbers"
        lay = ft.layout(v, e)
        self.assertTrue(ft.generation_label(lay, 2)[0].startswith("2. Generation 2"))
        back = ft.Edits.from_data(json.loads(json.dumps(e.to_data())))
        self.assertEqual((back.numbering, back.hidden), ("numbers", e.hidden))
        parts = [i.part for i in ft.scene(lay, "A New Home", {}).items if isinstance(i, ft.Text) and i.part]
        self.assertIn("1|first", parts)
        self.assertNotIn("1|living", parts)

    def test_picture_opacity_works_on_a_transparent_colour(self) -> None:
        # The owner: "picture opacity no longer works if the background color is transparent".
        pic = ft.picture_path("asset:mountains-and-sea.png", None)
        for fit in ("stretch", "tile"):
            sc = ft.Scene(40, 30, ft.TRANSPARENT, [ft.Backdrop(ft.TRANSPARENT, "", pic, fit, 71)])
            self.assertIn('opacity="0.29"', ft.to_svg(sc, {}))
            if vv_gdiplus.available():
                with tempfile.TemporaryDirectory() as tmp:
                    # Drawn see-through only when asked (a sticker's own picture)...
                    out = Path(tmp) / "faded.png"
                    self.assertTrue(vv_gdiplus.save_scene(sc, {}, out, transparent=True))
                    self.assertTrue(60 <= png_alpha_at(out, 20, 15) <= 90)
                    # ...while an exported tree is never see-through: a transparent background is
                    # white there, as the Family Tree Maker shows it (the owner, 2026-10-08: the
                    # see-through export looked dark in Photos), and the faded picture fades into it.
                    exported = Path(tmp) / "exported.png"
                    self.assertTrue(vv_gdiplus.save_scene(sc, {}, exported))
                    self.assertEqual(png_alpha_at(exported, 20, 15), 255)

    def test_the_rainbow_backgrounds_run_across_and_down(self) -> None:
        for key, end in (("rainbow-across", 'x2="1" y2="0"'), ("rainbow-down", 'x2="0" y2="1"')):
            sc = ft.Scene(70, 40, "#ffffff", [ft.Backdrop("#ffffff", key)])
            svg = ft.to_svg(sc, {})
            self.assertIn(end, svg)
            self.assertEqual(svg.count("<stop "), len(ft.RAINBOW))
            if vv_gdiplus.available():
                with tempfile.TemporaryDirectory() as tmp:
                    self.assertTrue(vv_gdiplus.save_scene(sc, {}, Path(tmp) / "rainbow.png"))
        back = ft.Edits.from_data(json.loads(json.dumps(ft.Edits(rainbow="rainbow-down").to_data())))
        self.assertEqual(back.rainbow, "rainbow-down")
        self.assertEqual(ft.Edits.from_data({"rainbow": "plaid"}).rainbow, "")


if __name__ == "__main__":
    unittest.main()
