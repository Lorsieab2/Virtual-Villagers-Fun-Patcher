"""No Safeguards for Island Events (and Additional Events too) -- the games' OWN island events (the owner,
2026-11-15): "VVFP No Safeguards.dll" lifts each game's event conditions except the villagers an event casts, the
puzzle it is tied to and what keeps it safe; never a record that is not a living villager.

STATIC: every site of native/vvfp_no_safeguards/ns_vvN.inc holds its stock bytes in the stock executable, the stock
and the new bytes are whole instructions, no two sites overlap, and none shares a byte with the island timer
keeper's or More Frequent Island Events' sites.  EMULATED: started as VVFP Startup.dll starts it, the companion
writes every site of its game only when the installed-patches list names vvN_island_events_any_time, and nothing when
the list does not, when another game's row is named, or when one site is not stock.  The patcher ships the DLL with
the row only.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

try:
    import capstone
    from test_companion_installs_all_or_none import HAVE_EMULATOR, Machine, render, stock_path
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

import vv_fun_patcher as patcher

DLL = ROOT / "assets" / "no_safeguards" / "VVFP No Safeguards.dll"
NATIVE = ROOT / "native" / "vvfp_no_safeguards"
LIST = "VVFP Installed Patches.txt"
FAKE_FILE = 0x0000ABCD
GAMES = (1, 2, 3, 4, 5)
COUNTS = {1: 5, 2: 6, 3: 35, 4: 15, 5: 30}
SITE = re.compile(r"\{\s*0x([0-9A-Fa-f]+)u,\s*(\d+),\s*\{([^}]*)\},\s*\{([^}]*)\}\s*\}")
FREQUENCY = {1: (0x423883, 0x42390A, 0x423A61), 2: (0x42EF93, 0x42F01A, 0x42F171), 3: (0x4687FB, 0x468832, 0x4688C6),
             4: (0x43FAF7, 0x43FB35, 0x43FBC4), 5: (0x4427C1, 0x442828)}


def sites(game: int) -> list[tuple[int, bytes, bytes]]:
    text = (NATIVE / f"ns_vv{game}.inc").read_text("utf-8")
    body = text[text.index(f"NS_VV{game}_SITES[] = {{"):]
    out = []
    for m in SITE.finditer(body):
        nums = lambda t: bytes(int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{1,2})\b", t))  # noqa: E731
        va, n, old, new = int(m.group(1), 16), int(m.group(2)), nums(m.group(3)), nums(m.group(4))
        assert len(old) == n and len(new) == n, hex(va)
        out.append((va, old, new))
    return out


def row_id(game: int) -> str:
    return f"vv{game}_island_events_any_time"


@unittest.skipUnless(HAVE_EMULATOR, "capstone / unicorn / pefile not installed")
class Sites(unittest.TestCase):
    def setUp(self) -> None:
        if not all(stock_path(g).is_file() for g in GAMES):
            self.skipTest("stock executables not present")

    def test_every_site_is_stock_whole_and_alone(self) -> None:
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        for game in GAMES:
            data = stock_path(game).read_bytes()
            table = sites(game)
            self.assertEqual(len(table), COUNTS[game])
            for va, old, new in table:
                with self.subTest(game=game, va=hex(va)):
                    self.assertEqual(data[va - 0x400000:va - 0x400000 + len(old)], old)
                    self.assertNotEqual(old, new)
                    for code in (old, new):
                        self.assertEqual(sum(i.size for i in md.disasm(code, va)), len(code))
            spans = sorted((va, va + len(old)) for va, old, _ in table)
            for (_, end), (start, _) in zip(spans, spans[1:]):
                self.assertLessEqual(end, start)

    def test_no_byte_is_shared_with_the_timer_keeper_or_the_frequency_companion(self) -> None:
        for game in GAMES:
            keeper = (ROOT / "native" / "shared" / f"island_timer_vv{game}.inc").read_text("utf-8")
            others = [(int(va, 16), int(n)) for va, n in re.findall(r"\{ 0x([0-9A-F]+)u, (\d+),", keeper)]
            others += [(va, 9) for va in FREQUENCY[game]]
            for va, old, _ in sites(game):
                for at, length in others:
                    with self.subTest(game=game, site=hex(va), other=hex(at)):
                        self.assertTrue(va + len(old) <= at or at + length <= va)


@unittest.skipUnless(HAVE_EMULATOR, "pefile/unicorn not installed")
class Emulated(unittest.TestCase):
    def setUp(self) -> None:
        if not all(stock_path(g).is_file() for g in GAMES):
            self.skipTest("stock executables not present")
        if not DLL.is_file():
            self.skipTest("companion not built")

    def machine(self, game: int, listing: bytes | None, mode: str = "stock") -> "Machine":
        m = Machine(render(game, (), mode), DLL)

        def open_(p):
            ok = listing is not None and p.wstring(p.arg(0)).endswith(
                "\\Virtual Villagers Fun Patcher Files\\" + LIST)
            return (FAKE_FILE if ok else 0xFFFFFFFF), 28

        def read(p):
            if p.arg(0) != FAKE_FILE:
                return 0, 20
            data = (listing or b"")[:p.arg(2)]
            p.write(p.arg(1), data)
            p.put32(p.arg(3), len(data))
            return 1, 20

        m.api_handlers["CreateFileW"] = open_
        m.api_handlers["ReadFile"] = read
        m.api_handlers["CloseHandle"] = lambda p: (1, 4)
        return m

    def listing(self, *ids: str) -> bytes:
        return ("# The patches the Virtual Villagers Fun Patcher installed in this game, one id per line.\n"
                + "".join(f"{i}\n" for i in ids)).encode("ascii")

    def test_every_site_with_the_row(self) -> None:
        for game in GAMES:
            for mode in ("stock", "collection_progression", "immediate_fixed"):
                with self.subTest(game=game, mode=mode):
                    m = self.machine(game, self.listing(f"vv{game}", row_id(game), f"vv{game}_origins"), mode)
                    m.export("VvfpStartup", game, 0)
                    self.assertEqual(m.export("VvfpNoSafeguardsInstalled"), 1)
                    self.assertEqual(m.export("VvfpNoSafeguardsSites"), COUNTS[game])
                    for va, _, new in sites(game):
                        self.assertEqual(m.read(va, len(new)), new)

    def test_nothing_without_the_row(self) -> None:
        other = {1: 2, 2: 1, 3: 4, 4: 5, 5: 3}
        for game in GAMES:
            for name, listing in (("no list", None), ("not named", self.listing(f"vv{game}")),
                                  ("another game's", self.listing(row_id(other[game]))),
                                  ("a longer name", self.listing(row_id(game) + "_x")),
                                  ("a note", self.listing("# " + row_id(game)))):
                with self.subTest(game=game, case=name):
                    m = self.machine(game, listing)
                    before = [m.read(va, len(old)) for va, old, _ in sites(game)]
                    m.export("VvfpStartup", game, 0)
                    self.assertEqual(m.export("VvfpNoSafeguardsInstalled"), 0)
                    self.assertEqual([m.read(va, len(old)) for va, old, _ in sites(game)], before)

    def test_all_or_none(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                table = sites(game)
                m = self.machine(game, self.listing(row_id(game)))
                last = table[-1]
                m.write(last[0], bytes([last[1][0] ^ 0xFF]))
                m.export("VvfpStartup", game, 0)
                self.assertEqual(m.export("VvfpNoSafeguardsInstalled"), 0)
                for va, old, _ in table[:-1]:
                    self.assertEqual(m.read(va, len(old)), old)


class Patcher(unittest.TestCase):
    def test_shipped_with_the_row_only(self) -> None:
        if not patcher.NO_SAFEGUARDS_RECORD.is_file():
            self.skipTest("companion record not written yet (scripts/build_no_safeguards_feature.py)")
        record = patcher._no_safeguards_companion()
        self.assertEqual(record["destination"], "VVFP No Safeguards.dll")
        for game in GAMES:
            row = patcher.Record({"id": row_id(game), "game_id": f"vv{game}", "companion_files": []})
            other = patcher.Record({"id": f"vv{game}_something_else", "game_id": f"vv{game}", "companion_files": []})
            with self.subTest(game=game):
                self.assertEqual([f.raw.get("companion_files") for f in patcher._attach_no_safeguards(
                    f"vv{game}", [other])], [[]])
                attached = patcher._attach_no_safeguards(f"vv{game}", [other, row])
                self.assertEqual(attached[1].raw["companion_files"], [record])
                self.assertEqual(row.raw["companion_files"], [])          # the catalog record is not changed
                again = patcher._attach_no_safeguards(f"vv{game}", attached)
                self.assertEqual(again[1].raw["companion_files"], [record])
                # Another game's row never ships it here.
                self.assertEqual(patcher._attach_no_safeguards(f"vv{game % 5 + 1}", [row])[0].raw["companion_files"],
                                 [])

    def test_started_from_the_second_word_after_island_frequency(self) -> None:
        names = list(patcher.STARTUP_LOADER_COMPANIONS_2)
        self.assertEqual(names.index("VVFP No Safeguards.dll"), names.index("VVFP Island Frequency.dll") + 1)
        self.assertLessEqual(len(names), 32)
        header = (ROOT / "native" / "shared" / "startup_companions_2.h").read_text("utf-8")
        self.assertLess(header.index('"VVFP Island Frequency.dll",'), header.index('"VVFP No Safeguards.dll",'))


class GameMechanics(unittest.TestCase):
    class Village:
        def __init__(self, game: int, has: bool | None):
            self.game, self._has = game, has

        def has(self, feature: str):
            return self._has if feature.endswith("_island_events_any_time") else False

    def test_shown_only_with_the_row(self) -> None:
        import vv_game_mechanics_no_safeguards as ns
        for game in GAMES:
            with self.subTest(game=game):
                texts = [f.text for f in ns.facts(self.Village(game, True))]
                self.assertEqual(len(texts), 3)
                self.assertTrue(texts[0].startswith(
                    'With the patcher\'s "No Safeguards for Island Events (and Additional Events too)" (in this game)'))
                self.assertTrue(texts[1].startswith("Lifted: "))
                self.assertTrue(texts[2].startswith("Kept: "))
                self.assertEqual(ns.facts(self.Village(game, False)), [])
                self.assertEqual(ns.facts(self.Village(game, None)), [])
        self.assertIn("totem statues", ns.facts(self.Village(2, True))[0].text)


if __name__ == "__main__":
    unittest.main()
