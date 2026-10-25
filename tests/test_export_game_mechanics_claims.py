"""scripts/export_game_mechanics_claims.py: one claims file per game that covers every line the Game Mechanics
window can render, each with its status, evidence and patches."""
from __future__ import annotations

import gzip
import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_game_mechanics as gm  # noqa: E402
import vv_tribe_rename  # noqa: E402
import test_game_mechanics as t  # noqa: E402

spec = importlib.util.spec_from_file_location("export_claims", ROOT / "scripts" / "export_game_mechanics_claims.py")
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)

_CLAIMS: dict[int, dict] = {}


def claims(game: int) -> dict:
    if game not in _CLAIMS:
        _CLAIMS[game] = export.claims(game)
    return _CLAIMS[game]


class Coverage(unittest.TestCase):
    def page(self, game: int, data: bytes, now: float, features=None) -> list[gm.Fact]:
        base = next(item.base for item in vv_tribe_rename.GAMES if item.number == game)
        root = Path(tempfile.mkdtemp(prefix="gmc"))
        self.addCleanup(shutil.rmtree, root, True)
        folder = root / base
        folder.mkdir()
        (folder / f"{base}1.ldw").write_bytes(data)
        games = []
        if features is not None:
            game_folder = root / "g" / base
            (game_folder / "Virtual Villagers Fun Patcher Files").mkdir(parents=True)
            (game_folder / f"{base}.exe").write_bytes(b"MZ")
            (game_folder / "Virtual Villagers Fun Patcher Files" / "VVFP Transparency Log.txt").write_text(
                export.HASH_LINE.format(name=base) + "".join(f"- Optional feature: x [{fid}]\n" for fid in features),
                encoding="utf-8")
            games = [game_folder]
        return gm.read(folder, game, 1, games, now=now)

    def assert_covered(self, game: int, facts: list[gm.Fact]) -> None:
        known = claims(game)
        for fact in facts:
            if fact.group == gm.SOURCES:
                continue
            self.assertIn(export.template(fact.text), known.get(fact.group, {}), f"{fact.group}: {fact.text}")

    def test_every_fixture_line_at_another_moment(self) -> None:
        for game in range(1, 6):
            for path in export.fixture_saves(game):
                with self.subTest(save=path.name):
                    data = gzip.decompress(path.read_bytes())
                    for now in (1_785_000_000.0, 1_791_000_000.0, 1_850_000_000.0):
                        self.assert_covered(game, self.page(game, data, now))

    def test_the_lost_childrens_fish(self) -> None:
        import struct
        import vv_game_mechanics_vv2 as vv2
        data = gzip.decompress((t.FIXTURES / "vv2-huttest-1.ldw.gz").read_bytes())
        for fish, solved, farming in ((700, 0, 3), (0, 0, 3), (-40, 1, 1), (-1_162_256, 1, 3), (5, 1, 2)):
            buf = bytearray(data)
            struct.pack_into("<i", buf, vv2.FISH + vv2.S, fish)
            struct.pack_into("<i", buf, vv2.LEVELS + 8 * vv2.FARMING_LEVEL + vv2.S, farming)
            buf[vv2.SUSTAINABLE_FISHING + vv2.S] = solved
            with self.subTest(fish=fish, solved=solved, farming=farming):
                self.assert_covered(2, self.page(2, bytes(buf), 1_791_000_000.0))

    def test_the_secret_citys_trees_and_patches(self) -> None:
        clock = (6, 0, 100_000, 50_000)
        for speed, c in ((6, clock), (3, (3, 0, 100_000, 50_000)), (1009, (0, 10, 100_000, 50_000))):
            for trees in ([(1, 46_400, 49_000, 300)], [(0, 1, 40_000, 100)], [(2, 1, 1, 1000)],
                          [(0, 49_000, 45_000, 10)]):
                for techs in ((1, 1, 1, 1, 1, 0, 0), (3, 3, 3, 3, 3, 3, 0)):
                    data = t.make_save(clock=c, speed=speed, trees=trees, techs=techs)
                    for features in (None, [], ["vv3_nature_honey_refill"]):
                        with self.subTest(speed=speed, trees=trees, techs=techs, features=features):
                            self.assert_covered(3, self.page(3, data, t.EPOCH + 100_000 + 20_000, features))

    def test_the_tree_timing_patches_schedule(self) -> None:
        clock = (6, 0, 100_000, 50_000)
        for speed, c in ((6, clock), (1005, (0, 6, 100_000, 50_000))):
            data = t.make_save(clock=c, speed=speed, trees=[(1, 46_400, 49_000, 300), (0, 1_000, 40_000, 1000)])
            for mode in (1, 2):
                with self.subTest(speed=speed, mode=mode):
                    timers = export._tree_timer_file(data, mode)
                    base = next(item.base for item in vv_tribe_rename.GAMES if item.number == 3)
                    root = Path(tempfile.mkdtemp(prefix="gmt"))
                    self.addCleanup(shutil.rmtree, root, True)
                    folder = root / base
                    place = folder / "Virtual Villagers Fun Patcher" / "Save 1" / "Data" / "Fruit Trees"
                    place.mkdir(parents=True)
                    (place / "Virtual Villagers 3 Fruit Tree Timers - Save 1.dat").write_bytes(timers)
                    (folder / f"{base}1.ldw").write_bytes(data)
                    facts = gm.read(folder, 3, 1, [], now=t.EPOCH + 120_000)
                    self.assertTrue(any("schedule, read from its file" in f.text for f in facts))
                    self.assert_covered(3, facts)

    def test_files_name_status_and_evidence(self) -> None:
        out = Path(tempfile.mkdtemp(prefix="gmo"))
        self.addCleanup(shutil.rmtree, out, True)
        self.assertEqual(export.main([str(out)]), 0)
        names = sorted(p.name for p in out.iterdir())
        self.assertEqual(names, sorted(export.file_name(n) for n in range(1, 6)))
        text = (out / export.file_name(3)).read_text(encoding="utf-8")
        self.assertIn("Virtual Villagers 3 - The Secret City - Game Mechanics Claims.txt", export.file_name(3))
        for status in ("UNCONFIRMED", "READ FROM THE SAVE", "VERIFIED FROM RUNNING CODE"):
            self.assertIn(f"Status: {status}", text)
        self.assertIn("- Honey: # of 3000", text)                 # a rule's own number kept, the save's not
        self.assertIn("- Tree #: Mango\n", text)
        self.assertIn("- Planted at <date>; refills every ", text)
        self.assertRegex(text, r"- Planted when the village was <time> old, counted on Normal speed \(started [^;]+; the "
                               r"save keeps no real date before [^)]+\); refills every ")
        self.assertIn("Patches: Nature Level 1 Actually Replenishes Food Sources Faster", text)
        owner = (out / export.file_name(5)).read_text(encoding="utf-8")
        self.assertIn("Status: CONFIRMED BY OWNER", owner)


if __name__ == "__main__":
    unittest.main()
