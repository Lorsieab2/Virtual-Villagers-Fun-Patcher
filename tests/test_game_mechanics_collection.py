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
        import vv_living_mixer as living
        seeds = [(v.manifest_id, v.graph) for v in living.generate()]
        self.assertEqual(shipped, gc.build_index(seeds), "run: python scripts/build_event_collection_features.py")

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
                    # A Living Event Engine seed's event is in the game's living.pak (living-pack.md 1), never a .cieg.
                    shipped = (f"vv{game}/living.pak" if event_id.startswith("living_") else f"{event_id}.cieg")
                    self.assertTrue((ROOT / "assets" / "event_collection" / shipped).is_file(), event_id)
                listed = [title for _words, titles in gc.sections(game) for title in titles]
                living = {title for event_id, title, _s in rows if event_id.startswith("living_")}
                self.assertEqual(sorted(listed), sorted([title for event_id, title, _s in rows
                                                         if not event_id.startswith("living_")] + list(living)))
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

    def test_the_v28_lines_only_when_an_event_makes_them(self) -> None:
        """cie-v6-binary.md 7, 22: a death with no body, a lost baby and an author's "allow" are each said on the
        page, with the events that make them, once an event of the game does."""
        from unittest import mock
        game = 3
        first, title, _s = gc.manifest(game)[0]
        # Without any such event (real events now make them: The Sudden Fever's lost baby), the lines are absent.
        plain = {k: dict(v, harm=[h for h in v["harm"] if h not in ("die_unrecovered", "baby_lost")], allow=False)
                 for k, v in gc.index().items()}
        with mock.patch.object(gc, "index", lambda: plain):
            before = gc.lines(game)
        self.assertFalse([t for t, _ in before if "body is never found" in t or "lose the baby" in t])
        changed = {k: dict(v) for k, v in plain.items()}
        changed[first] = dict(changed[first], harm=sorted(set(changed[first]["harm"]) | {"die_unrecovered",
                                                                                       "baby_lost"}), allow=True)
        with mock.patch.object(gc, "index", lambda: changed):
            text = " ".join(t for t, _ in gc.lines(game))
        self.assertIn(f"the Deaths log records the death, \"Unknown causes\"): {title}.", text)
        self.assertIn(f"Can make a nursing mother or father lose the baby: {title}.", text)
        self.assertIn(f"may harm a nursing mother or father, the Tribal Chief: {title}.", text)

    def test_the_rules_in_plain_words(self) -> None:
        for game in GAMES:
            text = " ".join(t for t, _ in gc.lines(game))
            with self.subTest(game=game):
                for words in ("never take a share of the game's own draw", f"{gc.REPLACE_PERCENT[0]}-{gc.REPLACE_PERCENT[1]}% chance", f"{gc.REPLACE_MIN_POPULATION} or more villagers",
                              "two opening events are never replaced", "in trouble", "rescue event is never replaced",
                              "every event that can happen is equally likely",     # the owner, 2026-11-14
                              "a series counts as one event", "Story / Cheat Upgrades", "Scrolling Popups",
                              "nursing mother or father", gc.PROTECTED[game]):
                    self.assertIn(words, text)
                self.assertNotIn("half the time", text)              # no 1:1 split between the sources any more
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
