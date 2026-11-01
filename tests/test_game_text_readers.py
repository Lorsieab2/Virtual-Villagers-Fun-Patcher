"""The games' own text bytes are read one way everywhere: Windows-1252, every byte kept (src/vv_game_text.py).

With Render Unicode with In-Game Fonts a player can type "Šárka" (0x8A 0xE1 ...).  Every reader -- the save,
the logs, the cross-check script the Family Tree Maker and Check / Repair read Births through -- must decode
those bytes to the same text, or one villager becomes two (Codex, PR #670: a living "Šárka" with no parents
and a non-living "\\x8aárka" carrying her Birth).
"""
from __future__ import annotations

import ast
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_genealogy as gen  # noqa: E402
from vv_game_text import DECODING_TABLE, GAME_TEXT, printable  # noqa: E402
from test_last_names_rename import DATA, LOGS, TABLE, entry  # noqa: E402

VILLAGE = "Village: Tribe (Save 1)\n"
NAME = "Šárka"                 # Šárka: 0x8A is Windows-1252 only


def _entry(name: str, *args, **kwargs) -> bytes:
    """test_last_names_rename.entry with the name written as the game writes it (one Windows-1252 byte each)."""
    e = bytearray(entry("X" * len(name), *args, **kwargs))
    raw = name.encode(GAME_TEXT)
    e[0x14:0x14 + len(raw)] = raw
    return bytes(e)


class TheCodec(unittest.TestCase):
    def test_every_byte_round_trips(self):
        data = bytes(range(256))
        self.assertEqual(data.decode(GAME_TEXT).encode(GAME_TEXT), data)
        self.assertEqual(b"\x8a\x80\x93\x94".decode(GAME_TEXT), "Š€“”")

    def test_text_an_older_patcher_read_as_latin_1_keeps_its_bytes(self):
        for b in range(0x80, 0xA0):
            self.assertEqual(chr(b).encode(GAME_TEXT), bytes([b]))

    def test_printable(self):
        self.assertTrue(all(printable(c) for c in "Šárka €“”—"))
        self.assertTrue(all(printable(c) for c in ("日", "\U0001F4A9", "\U0001208D")))      # v1.35.89: any character
        self.assertFalse(any(printable(c) for c in ("\x81", "\x7f", "\n", "\ue000")))
        self.assertEqual(len(DECODING_TABLE), 256)

    def test_no_reader_of_game_text_is_left_on_latin_1(self):
        """Every src/ module and the cross-check script decode the games' bytes with GAME_TEXT.  Only two
        latin-1 reads remain, neither of game text: vv_save_layout counts ASCII record markers (it must stay
        stdlib-only), and vv_font_glyphs and Picture Studio's vv_glyph_maker read a font file's Macintosh name
        record."""
        allowed = {("vv_save_layout.py", 1), ("vv_font_glyphs.py", 1), ("vv_glyph_maker.py", 1)}
        found = set()
        for path in sorted((ROOT / "src").glob("*.py")) + [ROOT / "scripts" / "vvfp_consistency_check.py"]:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            n = sum(1 for node in ast.walk(tree) if isinstance(node, ast.Constant)
                    and isinstance(node.value, str) and node.value.lower() in ("latin-1", "latin1", "iso-8859-1"))
            if n:
                found.add((path.name, n))
        self.assertEqual(found, allowed)


class OneVillagerInTheSaveAndTheLogs(unittest.TestCase):
    def test_a_windows_1252_name_in_the_save_and_a_birth_is_one_person_with_parents(self):
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        people = [
            entry("Ma", 1, 7, 4, 4), entry("Pa", 0, 7, 2, 2),
            _entry(NAME, 1, 7, 3, 5, father=("Pa", 2, 2), mother=("Ma", 4, 4)),
        ]
        (folder / "Virtual Villagers - The Secret City1.ldw").write_bytes(
            bytes(bytearray(b"ldwg" + bytes(TABLE - 4)) + b"".join(people) + bytes(64)))
        (folder / DATA).mkdir(parents=True)
        births = folder / LOGS / "Births and Conceptions" / "Virtual Villagers 3 Births and Conceptions Log 1.txt"
        births.parent.mkdir(parents=True)
        births.write_bytes((VILLAGE + f"Birth\n  Child: {NAME}\n    Head: 3\n    Body: 5\n"
                            "  Mother: Ma\n    Head: 4\n    Body: 4\n  Father: Pa\n    Head: 2\n    Body: 2\n\n")
                           .replace("\n", "\r\n").encode(GAME_TEXT))
        village = gen.load_village(folder, 3, 1)
        named = [p for p in village.people.values() if p.name.endswith("rka")]
        self.assertEqual([p.name for p in named], [NAME], "one villager, read the same from the save and the log")
        sarka = named[0]
        self.assertTrue(sarka.alive)
        self.assertEqual((village.people[sarka.mother].name, village.people[sarka.father].name), ("Ma", "Pa"))


if __name__ == "__main__":
    unittest.main()
