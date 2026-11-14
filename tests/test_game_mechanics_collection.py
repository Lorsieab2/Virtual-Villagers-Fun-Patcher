"""The Isola Grand Event Collection on the Game Mechanics pages (src/vv_game_mechanics_collection.py).

The page's event list must be the collection the patcher ships for each game (assets/event_collection/vvN/
manifest.txt, the file "VVFP Story Upgrades.dll" reads), and its sections and deadly events must be the source
graphs' (data/event_collection/<section>/<id>.json, through the shipped data/event_collection_index.json).
No emulator or stock executable needed.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics_collection as gc  # noqa: E402
import vv_game_mechanics_events as events  # noqa: E402

GAMES = (1, 2, 3, 4, 5)


class FakeVillage:
    def __init__(self, game: int, installed: set[str]):
        self.game = game
        self.installed = installed

    def has(self, feature: str) -> bool:
        return feature in self.installed


class TheIndex(unittest.TestCase):
    def test_the_shipped_index_is_the_sources(self) -> None:
        import json
        shipped = json.loads(gc.INDEX_PATH.read_text(encoding="utf-8"))
        self.assertEqual(shipped, gc.build_index(), "run: python src/vv_game_mechanics_collection.py")

    def test_the_index_ships_with_the_release(self) -> None:
        text = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('"data/event_collection_index.json"', text)
        self.assertIn('"src/vv_game_mechanics_collection.py"', text)


class ThePage(unittest.TestCase):
    def test_the_list_is_each_games_shipped_manifest(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                rows = gc.manifest(game)
                self.assertTrue(rows)
                for event_id, _title, _series in rows:
                    self.assertIn(event_id, gc.index())
                    self.assertTrue((ROOT / "assets" / "event_collection" / f"{event_id}.cieg").is_file(), event_id)
                listed = [title for _words, titles in gc.sections(game) for title in titles]
                self.assertEqual(sorted(listed), sorted(title for _id, title, _s in rows))
                text = " ".join(t for t, _ in gc.lines(game))
                self.assertIn(f"{len(rows)} events in this game", text)
                for words, titles in gc.sections(game):
                    self.assertIn(f"{words} ({len(titles)}): " + ", ".join(titles) + ".", text)

    def test_the_deadly_events_are_the_graphs(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                kill, vanish = gc.deadly(game)
                rows = gc.manifest(game)
                self.assertEqual(kill, [t for i, t, _ in rows if "kill" in gc.index()[i]["harm"]])
                self.assertEqual(vanish, [t for i, t, _ in rows if "vanish" in gc.index()[i]["harm"]])
                text = " ".join(t for t, _ in gc.lines(game))
                for title in kill + vanish:
                    self.assertIn(title, text)

    def test_the_rules_in_plain_words(self) -> None:
        for game in GAMES:
            text = " ".join(t for t, _ in gc.lines(game))
            with self.subTest(game=game):
                for words in ("never take a share of the game's own draw", f"{gc.RARE_ROLL_PERCENT[game]}% of the "
                              "time", "once the village has seen two", "in trouble", "half the time",
                              "a series counts as one event", "Story / Cheat Upgrades", "Scrolling Popups",
                              "nursing mother or father", gc.PROTECTED[game]):
                    self.assertIn(words, text)
                self.assertNotRegex(text, r"0x[0-9A-Fa-f]{4,}")      # no exe addresses in visible text

    def test_shown_only_with_the_patch(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                self.assertEqual(events.collection_facts(FakeVillage(game, set())), [])
                shown = events.collection_facts(FakeVillage(game, {f"vv{game}_isola_grand_event_collection"}))
                self.assertEqual([f.text for f in shown], [t for t, _ in gc.lines(game)])
                self.assertTrue(all(f.confirmed for f in shown))


if __name__ == "__main__":
    unittest.main()
