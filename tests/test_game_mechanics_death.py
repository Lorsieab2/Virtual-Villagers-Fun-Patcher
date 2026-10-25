"""The Game Mechanics window's "Death and graves" group (src/vv_game_mechanics_death.py): every game has it, its
lines follow the window's rules, its save-read lines match the save, and the stock code it cites says what the
lines say (the stock executables are absent on GitHub CI: those checks skip)."""
from __future__ import annotations

import gzip
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_death as death  # noqa: E402
import vv_graves  # noqa: E402
import vv_tribe_rename  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "rename_tribe"
INPUTS = ROOT / "inputs"
NOW = 1_800_000_000.0


def page(name: str, data: bytes | None = None) -> list[gm.Fact]:
    number, slot = int(name[2]), int(name[-1])
    base = next(item.base for item in vv_tribe_rename.GAMES if item.number == number)
    root = Path(tempfile.mkdtemp(prefix="gmd"))
    try:
        folder = root / base
        folder.mkdir()
        (folder / f"{base}{slot}.ldw").write_bytes(
            data if data is not None else gzip.decompress((FIXTURES / f"{name}.ldw.gz").read_bytes()))
        return gm.read(folder, number, slot, [], now=NOW)
    finally:
        shutil.rmtree(root, True)


def stock(game: int) -> tuple[bytes, int] | None:
    """The stock exe's memory image and image base, or None when it is not here."""
    exes = sorted((INPUTS / f"vv{game}-stock-copy").glob("*.exe")) if INPUTS.is_dir() else []
    if not exes:
        return None
    try:
        import pefile
    except ImportError:
        return None
    pe = pefile.PE(str(exes[0]), fast_load=True)
    return pe.get_memory_mapped_image(), pe.OPTIONAL_HEADER.ImageBase


class Group(unittest.TestCase):
    GAMES = {5: ("vv5-huttest-1", "vv5-256-1"), 4: ("vv4-huttest-1", "vv4-256-1"), 3: ("vv3-huttest-1", "vv3-256-1")}

    def test_every_game_has_the_group_in_order(self) -> None:
        self.assertIn(gm.DEATH, gm.GROUPS)
        for game, names in self.GAMES.items():
            for name in names:
                with self.subTest(save=name):
                    facts = page(name)
                    mine = [f for f in facts if f.group == gm.DEATH]
                    self.assertGreater(len(mine), 10)
                    self.assertEqual(sum(f.text.startswith("Old age:") for f in mine), 1)
                    self.assertTrue(any(f.text.startswith("Graves in this village: ") for f in mine))
                    text = gm.render(mine)
                    self.assertNotRegex(text.lower(), r"some effect|not worked out|etc\.|probabl|perhaps")
                    self.assertNotRegex(text.lower(), r"game (hours?|minutes?|seconds?)\b")
                    self.assertNotIn("certain at", text)

    def test_graves_count_matches_the_save(self) -> None:
        for game, names in self.GAMES.items():
            for name in names:
                with self.subTest(save=name):
                    data = gzip.decompress((FIXTURES / f"{name}.ldw.gz").read_bytes())
                    graves = vv_graves.read_graves(game, data)
                    facts = page(name)
                    line = next(f for f in facts if f.text.startswith("Graves in this village: "))
                    self.assertIn(f": {len(graves)} of ", line.text)
                    self.assertEqual(line.verified, gm.SAVE)

    def test_general_page_reads_nothing_from_a_save(self) -> None:
        for game in self.GAMES:
            facts = [f for f in gm.general(game, now=NOW) if f.group == gm.DEATH]
            self.assertTrue(facts)
            self.assertFalse(any(f.verified == gm.SAVE for f in facts))

    def test_an_unburied_body_gets_its_removal_time(self) -> None:
        import vv_game_mechanics_life as life
        import vv_last_names as ln
        data = gzip.decompress((FIXTURES / "vv5-huttest-1.ldw.gz").read_bytes())
        at = ln._entries(5, data)[0]
        name = ln._cstr(data, at, ln.FIELDS[5].name_cap)
        buf = bytearray(data)
        struct.pack_into("<i", buf, at + life.LAYOUTS[5].health, 0)
        base = struct.unpack_from("<q", data, 8)[0]
        stamp = int(NOW - base) - 3600                       # died an hour before "now"
        struct.pack_into("<i", buf, at + death.VV_STAMP, stamp)
        speed = struct.unpack_from("<i", data, 0x17D8C)[0]
        facts = page("vv5-huttest-1", bytes(buf))
        mine = [f for f in facts if f.text.startswith(f"{name}'s body is unburied")]
        self.assertEqual(len(mine), 1, [f.text for f in facts if f.group == gm.DEATH])
        if speed < gm.PAUSED:
            self.assertEqual(mine[0].due, base + stamp + 240 * 60 * speed)


class StockCode(unittest.TestCase):
    """The stock bytes behind New Believers' lines (addresses in src/vv_game_mechanics_death.py)."""

    def setUp(self) -> None:
        found = stock(5)
        if found is None:
            self.skipTest("the stock New Believers executable is not here")
        self.img, self.base = found

    def at(self, va: int, n: int) -> bytes:
        return bytes(self.img[va - self.base:va - self.base + n])

    def test_the_rules_bytes(self) -> None:
        self.assertEqual(self.at(0x46FEE9, 5), bytes.fromhex("3DF0000000"))      # cmp eax, 240 age units
        self.assertEqual(self.at(0x464D27, 10), bytes.fromhex("81BF8C1B000068010000"))  # cmp age, 360
        self.assertEqual(self.at(0x473043, 4), bytes.fromhex("6A026A00"))        # old age: health 0, cause 2
        self.assertEqual(self.at(0x46DC71, 3), bytes.fromhex("83F802"))          # research: rand(100) < 2
        self.assertEqual(self.at(0x46DC76, 4), bytes.fromhex("6A036A0A"))        # cause 3, rand(10)
        self.assertEqual(self.at(0x46F131, 2), bytes.fromhex("6A06"))            # The Buried Mausoleum
        self.assertEqual(self.at(0x46F15C, 3), bytes.fromhex("83F819"))          # 25%
        self.assertEqual(self.at(0x46F182, 3), bytes.fromhex("83F846"))          # 70%
        self.assertEqual(self.at(0x46F0D9, 3), bytes.fromhex("83F841"))          # 34% of picks
        self.assertEqual(self.at(0x464C8B, 6), bytes.fromhex("81FDF4010000"))    # 500 graves
        self.assertEqual(self.at(0x4156BB, 4), bytes.fromhex("6AFF6AF1"))        # The Bed Bugs: -15, cause -1


class StockCodeVV4(StockCode):
    """The stock bytes behind The Tree of Life's lines."""

    def setUp(self) -> None:
        found = stock(4)
        if found is None:
            self.skipTest("the stock Tree of Life executable is not here")
        self.img, self.base = found

    def test_the_rules_bytes(self) -> None:
        self.assertEqual(self.at(0x4664AD, 5), bytes.fromhex("3DF0000000"))      # 240 age units
        self.assertEqual(self.at(0x45D527, 10), bytes.fromhex("81BF8C1B000068010000"))  # under 360: child lines
        self.assertEqual(self.at(0x46ACBA, 3), bytes.fromhex("83FA05"))          # Scholar: all five skills
        self.assertEqual(self.at(0x415425, 4), bytes.fromhex("6AFF6A03"))        # the Fungi: health 0, cause 3
        self.assertEqual(self.at(0x4658FD, 3), bytes.fromhex("83F819"))          # 25%
        self.assertEqual(self.at(0x465889, 3), bytes.fromhex("83F841"))          # 34% of picks
        self.assertEqual(self.at(0x414221, 5)[:1], b"\xE8")                      # ghost: rand(graves)
        self.assertEqual(self.at(0x466401, 7), bytes.fromhex("C686C71C000001"))  # the ghost byte

class StockCodeVV3(StockCode):
    """The stock bytes behind The Secret City's lines."""

    def setUp(self) -> None:
        found = stock(3)
        if found is None:
            self.skipTest("the stock Secret City executable is not here")
        self.img, self.base = found

    def test_the_rules_bytes(self) -> None:
        self.assertEqual(self.at(0x45F43D, 5), bytes.fromhex("3DF0000000"))      # 240 age units
        self.assertEqual(self.at(0x455072, 3), bytes.fromhex("83FF32"))          # a gravestone under 50
        self.assertEqual(self.at(0x4550E3, 5), bytes.fromhex("B8E4020000"))      # the Chief's epitaph
        self.assertEqual(self.at(0x45C0C4, 3), bytes.fromhex("83F841"))          # 34% of picks
        self.assertEqual(self.at(0x45C191, 3), bytes.fromhex("83F819"))          # 25%
        self.assertEqual(self.at(0x45D9CD, 4), bytes.fromhex("3BC57D03"))        # the Tsunami's roll
        self.assertEqual(self.at(0x45D9D1, 3), bytes.fromhex("C60600"))          # ...clears presence


if __name__ == "__main__":
    unittest.main()
