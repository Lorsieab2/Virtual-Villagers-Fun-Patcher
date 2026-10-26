"""The Game Mechanics window's Genetics group (src/vv_game_mechanics_genetics.py): each game's head and body rules,
the patches that change a head (only when in the game), each child's head beside its recorded parents', and the
stock code the rules were read from."""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_genetics as genetics  # noqa: E402
import vv_last_names  # noqa: E402

STOCK = {1: "Virtual Villagers - A New Home.exe", 2: "Virtual Villagers - The Lost Children.exe",
         3: "Virtual Villagers - The Secret City.exe", 4: "Virtual Villagers - The Tree of Life.exe",
         5: "Virtual Villagers - New Believers.exe"}


def stock(game: int) -> Path | None:
    for folder in (ROOT / "inputs" / f"vv{game}-stock-copy", ROOT / "research" / "stock-executables"):
        path = folder / STOCK[game]
        if path.is_file():
            return path
    return None


def at_va(data: bytes, va: int, length: int) -> bytes:
    """`length` bytes of a PE image at virtual address `va` (its sections read from its own headers)."""
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    sections = struct.unpack_from("<H", data, pe + 6)[0]
    optional = struct.unpack_from("<H", data, pe + 20)[0]
    base = struct.unpack_from("<I", data, pe + 24 + 28)[0]
    table = pe + 24 + optional
    for n in range(sections):
        size, rva, _raw_size, raw = struct.unpack_from("<4I", data, table + n * 40 + 8)
        if rva <= va - base < rva + size:
            start = raw + va - base - rva
            return data[start:start + length]
    raise AssertionError(f"{va:#x} is in no section")


def genetics_text(game: int) -> str:
    return gm.render([f for f in gm.general(game, now=1_700_000_000) if f.group == gm.GENETICS])


class Groups(unittest.TestCase):
    def test_genetics_follows_the_hidden_stats(self) -> None:
        self.assertEqual(gm.GROUPS.index(gm.GENETICS), gm.GROUPS.index(gm.HIDDEN) + 1)
        self.assertEqual(gm.GROUPS.count(gm.GENETICS), 1)

    def test_every_rule_is_confirmed_from_reachable_code(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                facts = [f for f in gm.general(game, now=1_700_000_000) if f.group == gm.GENETICS]
                self.assertGreaterEqual(len(facts), 5)
                self.assertTrue(all(f.verified == gm.RUNNING for f in facts))
                self.assertNotIn(gm.UNCONFIRMED, gm.render(facts))


class Rules(unittest.TestCase):
    def test_a_new_home_has_no_inheritance(self) -> None:
        text = genetics_text(1)
        self.assertIn("no head genetics", text)
        self.assertIn("A boy gets any head 0 to 18", text)
        self.assertIn("a girl any head 0 to 19", text)
        self.assertIn("head 19 and body 19", text)                  # the Golden Child
        self.assertIn("copy the first baby's sex, body and head", text)
        self.assertIn("\"A Mysterious Vial\"", text)
        self.assertNotIn("average", text)

    def test_the_later_games_average_the_parents(self) -> None:
        for game in (2, 3, 4, 5):
            with self.subTest(game=game):
                text = genetics_text(game)
                self.assertIn("adds the father's head and the mother's head, halves it", text)
                self.assertIn("adds -1, 0 or +1, one chance in 3 each", text)
                self.assertIn("On 5 births in 100 it instead picks any head 0 to 29", text)
                self.assertIn("31.83%", text)
                self.assertIn("0.17%", text)
                self.assertIn("63.5%", text)
                self.assertIn(genetics._LATER[game]["creator"], text)
                self.assertIn("30 heads (0 to 29) and 30 bodies (0 to 29)", text)

    def test_the_odds_add_up(self) -> None:
        self.assertAlmostEqual(3 * genetics.NEAR + 27 * genetics.FAR, 1.0)

    def test_bodies_per_game(self) -> None:
        self.assertIn("any body 0 to 29, 1 chance in 30 each", genetics_text(2))
        for game in (3, 4, 5):
            with self.subTest(game=game):
                self.assertIn("any body 0 to 28, 1 chance in 29 each", genetics_text(game))
                self.assertIn("body 29 is never given at birth", genetics_text(game))

    def test_game_specific_lines(self) -> None:
        self.assertIn("The Gong of Wonder", genetics_text(2))
        self.assertIn("fixed lists", genetics_text(2))
        self.assertIn("obsidian", genetics_text(3))
        self.assertIn("33 times in 100 their looks change", genetics_text(3))
        for game in (4, 5):
            with self.subTest(game=game):
                if game == 4:
                    self.assertIn("Joey, who has head 2 and body 2", genetics_text(game))
                else:
                    # New Believers: Joey's only event is inherited and never drawn (0x415B10), so never named; the
                    # Heathen Mommy's father "Unknown" is a name the patch's new-village code passes, head 2 body 2.
                    self.assertNotIn("Joey", genetics_text(game))
                    self.assertIn("father \"Unknown\" (the owner). He is a name only, not a villager",
                                  genetics_text(game))
                    self.assertIn("head 2 and body 2 (0x465E00)", genetics_text(game))
                self.assertIn("changes a villager's head after it is made", genetics_text(game))
        for game in (1, 3, 4, 5):
            self.assertNotIn("fixed lists", genetics_text(game))

    def test_the_general_page_keeps_every_rule(self) -> None:
        """No rule is mistaken for a value of the empty save by the general page's filters."""
        for game in range(1, 6):
            with self.subTest(game=game):
                village = gm.Village(Path("."), game, 1, Path("x.ldw"), gm.blank_save(game, 1_700_000_000), None,
                                     1_700_000_000, general=True)
                self.assertEqual(len([f for f in gm.general(game, now=1_700_000_000) if f.group == gm.GENETICS]),
                                 len(genetics.facts(village)))


class Patches(unittest.TestCase):
    def village(self, game: int, installed) -> gm.Village:
        return gm.Village(Path("."), game, 1, Path("x.ldw"), b"", installed, 1_700_000_000, general=True)

    def test_a_patch_is_named_only_when_in_the_game(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                none = gm.render(genetics.facts(self.village(game, frozenset())))
                self.assertNotIn("With the patcher's", none)
                unknown = gm.render(genetics.facts(self.village(game, None)))
                self.assertNotIn("With the patcher's", unknown)
                both = frozenset({genetics.ORIGINS.format(game), genetics.STORY.format(game)})
                text = gm.render(genetics.facts(self.village(game, both)))
                self.assertIn("Change Appearance on the Villager Details screen", text)
                self.assertEqual("Pick Island Event" in text, game in (1, 2, 3))
                rows = 20 if game == 1 else 30
                self.assertIn(f"every one of the game's {rows} heads and {rows} bodies, for a man or a woman "
                              "of any age", text)
                self.assertEqual("the Golden Child's head 19 and body 19 included" in text, game == 1)
                self.assertEqual("the Tribal Chief's body 29 included" in text, game == 3)


class Villagers(unittest.TestCase):
    """Each child's head beside the heads its parents passed at its birth, read from the save's own fields."""

    def make(self, game: int, people) -> tuple[bytes, list]:
        f = vv_last_names.FIELDS[game]
        fh, _fb, mh, _mb = f.looks[:4]
        data = bytearray(0x4000)
        roster = []
        for n, (name, head, mother, mhead, father, fhead) in enumerate(people):
            at = 0x200 + n * 0x400
            data[at + f.mother:at + f.mother + len(mother)] = mother.encode()
            data[at + f.father:at + f.father + len(father)] = father.encode()
            struct.pack_into("<i", data, at + mh, mhead)
            struct.pack_into("<i", data, at + fh, fhead)
            roster.append(vv_last_names.Living(at, name, "Female", head, 0, 1, ""))
        return bytes(data), roster

    def lines(self, game: int, people) -> list[str]:
        data, roster = self.make(game, people)
        village = gm.Village(Path("."), game, 1, Path("x.ldw"), data, frozenset(), 1_700_000_000)
        with mock.patch.object(vv_last_names, "living", return_value=roster):
            return [f.text for f in genetics.facts(village) if f.verified == gm.SAVE]

    def test_each_later_game(self) -> None:
        for game in (2, 3, 4, 5):
            with self.subTest(game=game):
                lines = self.lines(game, [("Kolea", 25, "Manaka", 22, "Vinapu", 27),
                                          ("Tepoto", 20, "Jem", 19, "Nuku", 20),
                                          ("Aba", 3, "Bindi", 18, "Azizi", 27),
                                          ("Founder", 9, "", 0, "", 0)])
                self.assertEqual(len(lines), 4)                       # the founder has no parents recorded
                self.assertIn("2 of the 3 living villagers", lines[0])
                self.assertIn("Kolea: head 25; mother Manaka passed head 22 and father Vinapu head 27 at the birth "
                              "-- the same as neither.", lines[1])
                self.assertIn("the same as the father's", lines[2])
                self.assertIn("Aba: head 3", lines[3])

    def test_head_zero_is_a_real_head(self) -> None:
        lines = self.lines(4, [("Zero", 0, "Mum", 0, "Dad", 0)])
        self.assertIn("1 of the 1 living villagers", lines[0])
        self.assertIn("the same as the mother's and the father's", lines[1])

    def test_a_new_home_shows_no_parents(self) -> None:
        village = gm.Village(Path("."), 1, 1, Path("x.ldw"), b"\0" * 64, frozenset(), 1_700_000_000)
        with mock.patch.object(vv_last_names, "living", side_effect=AssertionError("not read")):
            self.assertEqual([f for f in genetics.facts(village) if f.verified == gm.SAVE], [])


class PatchLines(unittest.TestCase):
    """The normal game's rule first; Fix Vanilla Bugs' line only when the exe has the row ("VVFP Appearance
    Rolls.dll": The Lost Children's green vial for a man, The Tree of Life's and New Believers' body roll)."""

    def text(self, game: int, patches: frozenset) -> list[str]:
        village = gm.Village(Path("."), game, 1, Path("x.ldw"), b"\0" * 64, patches, 1_700_000_000)
        with mock.patch.object(vv_last_names, "living", return_value=[]):
            return [f.text for f in genetics.facts(village)]

    def test_the_fix_line_follows_the_normal_rule_only_with_the_row(self) -> None:
        wanted = {2: "a man who drinks \"A Mysterious Vial\" (the green liquid) gets any head 0 to 29",
                  4: "a new villager's body is any of 0 to 29, 1 chance in 30 each, so body 29 is given too",
                  5: "a new villager's body is any of 0 to 29, 1 chance in 30 each, so body 29 is given too"}
        normal = {2: "a man any of 0 to 28", 4: "body 29 is never given at birth", 5: "body 29 is never given at birth"}
        for game, line in wanted.items():
            with self.subTest(game=game):
                fix = f"vv{game}_fix_vanilla_bugs"
                self.assertFalse(any(line in t for t in self.text(game, frozenset())))
                lines = self.text(game, frozenset({fix}))
                at = [i for i, t in enumerate(lines) if line in t]
                self.assertEqual(len(at), 1)
                self.assertTrue(lines[at[0]].startswith("With the patcher's \"Fix Vanilla Bugs\" (in this game): "))
                self.assertLess(next(i for i, t in enumerate(lines) if normal[game] in t), at[0])

    def test_a_new_home_and_the_secret_city_have_no_fix_line(self) -> None:
        for game in (1, 3):
            with self.subTest(game=game):
                lines = self.text(game, frozenset({f"vv{game}_fix_vanilla_bugs"}))
                self.assertFalse(any("Appearance Rolls" in t for t in lines))


class StockCode(unittest.TestCase):
    """The instructions each rule was read from, in each game's stock executable."""

    def code(self, game: int):
        path = stock(game)
        if path is None:
            self.skipTest(f"no stock VV{game} executable in inputs\\ or research\\stock-executables")
        return path.read_bytes()

    def test_the_later_games_head_roll(self) -> None:
        # push 0x64 / call rand ... cmp eax,5 / jl random; push 3 / call rand ... sar eax,1 / lea eax,[ecx+eax-1];
        # push 0x1e / call rand (the random head); push 0x1d or 0x1e / call rand (the body).
        sites = {2: (0x44CBAB, 0x44CBE6, 0x44CBF5, 0x44CC25, 0x44CC35, 0x1E),
                 3: (0x4564A7, 0x4564DA, 0x4564F6, 0x4564FE, 0x456520, 0x1D),
                 4: (0x45F235, 0x45F268, 0x45F284, 0x45F28C, 0x45F2AE, 0x1D),
                 5: (0x46853A, 0x46856D, 0x468589, 0x468591, 0x4685B3, 0x1D)}
        for game, (hundred, three, halve, thirty, body, body_n) in sites.items():
            with self.subTest(game=game):
                data = self.code(game)
                self.assertEqual(at_va(data, hundred, 2), b"\x6a\x64")
                self.assertEqual(at_va(data, three, 2), b"\x6a\x03")
                self.assertEqual(at_va(data, halve, 6), b"\xd1\xf8\x8d\x44\x01\xff")   # sar eax,1; lea eax,[ecx+eax-1]
                self.assertEqual(at_va(data, thirty, 2), b"\x6a\x1e")
                self.assertEqual(at_va(data, body, 2), bytes([0x6A, body_n]))

    def test_the_birth_passes_both_parents_heads(self) -> None:
        # The later games' first child: the mother's head is the last value pushed before the father's looks.
        data = self.code(4)
        self.assertEqual(at_va(data, 0x468819, 6), b"\x8b\x86\x7c\xff\xff\xff")       # mov eax,[esi-0x84] (+0x1BB8)
        self.assertEqual(at_va(data, 0x468822, 3), b"\x8b\x56\xf4")                   # mov edx,[esi-0xC] (+0x1C30)

    def test_a_new_home_rolls_at_random(self) -> None:
        data = self.code(1)
        self.assertEqual(at_va(data, 0x43C61F, 2), b"\x6a\x13")                       # a boy: rand(19)
        self.assertEqual(at_va(data, 0x43C62A, 2), b"\x6a\x14")                       # a girl: rand(20)
        self.assertEqual(at_va(data, 0x43C7AF, 10), b"\x81\xbe\x6c\x03\x00\x00\xc7\x00\x00\x00")  # family 199
        self.assertEqual(at_va(data, 0x43C7EA, 5), b"\xb8\x13\x00\x00\x00")           # head and body 19

    def test_the_twins_copy(self) -> None:
        data = self.code(4)
        self.assertEqual(at_va(data, 0x465CE8, 7), b"\xb9\x2a\x00\x00\x00\xf3\xa5")   # mov ecx,0x2A; rep movsd

    def test_the_vials(self) -> None:
        self.assertEqual(at_va(self.code(1), 0x42C92D, 2), b"\x6a\x13")
        self.assertEqual(at_va(self.code(2), 0x4395ED, 2), b"\x6a\x1d")
        data = self.code(3)
        self.assertEqual(at_va(data, 0x4175C5, 3), b"\x83\xf8\x21")                   # cmp eax,33
        self.assertEqual(at_va(data, 0x417634, 2), b"\x6a\x1e")


if __name__ == "__main__":
    unittest.main()
