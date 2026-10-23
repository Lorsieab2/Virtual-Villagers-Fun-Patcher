"""Repair Saves & Logs' Game Mechanics section (src/vv_game_mechanics.py) and The Secret City's fruit
trees and honey (src/vv_game_mechanics_vv3.py): read-only, real time only, the owner's line format.

Synthetic saves are built byte by byte at the offsets the stock save writer uses (the module's
docstring); the committed real Secret City saves (tests/fixtures/rename_tribe) are read too.
"""
from __future__ import annotations

import ast
import gzip
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_vv3 as vv3  # noqa: E402

BASE = "Virtual Villagers - The Secret City"
EPOCH = 1_790_000_000
FIXTURES = ROOT / "tests" / "fixtures" / "rename_tribe"


def make_save(*, size=0x12F1C, clock=(6, 0, 100_000, 50_000), speed=6, techs=(1, 1, 1, 1, 1, 0, 0),
              trees=(), honey=(49_000, 120), hive=True, points=7) -> bytes:
    buf = bytearray(size)
    struct.pack_into("<4i", buf, vv3.CLOCK, *clock)
    struct.pack_into("<i", buf, vv3.SPEED, speed)
    struct.pack_into("<7i", buf, vv3.TECHS, *techs)
    struct.pack_into("<i", buf, vv3.POINTS, points)
    struct.pack_into("<I", buf, vv3.PUZZLES, vv3.PUZZLES_MARK)
    struct.pack_into("<ii", buf, vv3.PUZZLES + 4 + 8 * vv3.BEE_HIVE, 1 if hive else 0, 0)
    struct.pack_into("<ii", buf, vv3.HONEY + 4, *honey)
    for n, (kind, planted, refilled, fruit) in enumerate(trees):
        struct.pack_into("<6i", buf, vv3.TREES + 0x14 + 0x18 * n, 1300 + 100 * n, 1200, planted, refilled, kind, fruit)
    struct.pack_into("<i", buf, vv3.TREES + 0x5C, len(trees))
    return b"ldwg" + struct.pack("<II", EPOCH, size) + bytes(buf)


def real(clock, game_seconds, speed=6):
    return EPOCH + clock[2] + (game_seconds - clock[3]) * speed / 6


class Folder:
    """A short temporary save folder (never the owner's: tests only ever write here)."""

    def __init__(self, test: unittest.TestCase, name: str = BASE + " - Modded"):
        self.root = Path(tempfile.mkdtemp(prefix="gm"))
        test.addCleanup(shutil.rmtree, self.root, True)
        self.path = self.root / name
        self.path.mkdir()

    def save(self, data: bytes, slot: int = 1) -> Path:
        path = self.path / f"{BASE}{slot}.ldw"
        path.write_bytes(data)
        return path

    def game(self, features: list[str]) -> Path:
        """A game folder of the save folder's name with a transparency report listing `features`."""
        game = self.root / "games" / self.path.name
        (game / "Virtual Villagers Fun Patcher Files").mkdir(parents=True)
        (game / f"{self.path.name}.exe").write_bytes(b"MZ")
        lines = ["Patcher version/commit: v1.35.81 / unavailable"]
        lines += [f"- Optional feature: Name of {fid} [{fid}]" for fid in features]
        (game / "Virtual Villagers Fun Patcher Files" / "VVFP Transparency Log.txt").write_text(
            "\n".join(lines) + "\n", encoding="utf-8")
        return game


def text_of(facts) -> str:
    return gm.render(facts)


def lines(facts, group=None) -> list[str]:
    return [f.text for f in facts if group is None or f.group == group]


class Words(unittest.TestCase):
    def test_durations_in_real_time(self) -> None:
        self.assertEqual(gm.duration(10_800), "3 hours")
        self.assertEqual(gm.duration(5_400), "1 hour 30 minutes")
        self.assertEqual(gm.duration(18_000), "5 hours")
        self.assertEqual(gm.duration(8_100), "2 hours 15 minutes")
        self.assertEqual(gm.duration(2_700), "45 minutes")
        self.assertEqual(gm.duration(20), "20 seconds")
        self.assertEqual(gm.duration(90_000), "1 day 1 hour")

    def test_every_at_each_speed(self) -> None:
        self.assertEqual(gm.every(10_800, 6), "every 3 hours on Normal speed")
        self.assertEqual(gm.every(10_800, 3), "every 1 hour 30 minutes on Fast speed")
        self.assertEqual(gm.every(10_800, 10), "every 5 hours on Slow speed")
        self.assertEqual(gm.every(10_800, 1005), "every 3 hours on Normal speed once unpaused")

    def test_when_reads_like_the_owner_wrote_it(self) -> None:
        self.assertRegex(gm.when(EPOCH), r"^\d{1,2} [A-Z][a-z]+ \d{4}, \d{1,2}:\d{2} (AM|PM)$")


class FruitTrees(unittest.TestCase):
    def read(self, data: bytes, features=None, now=None, folder=None, slot=1):
        folder = folder or Folder(self)
        folder.save(data, slot)
        games = [folder.game(features)] if features is not None else []
        return gm.read(folder.path, 3, slot, games, now=now)

    def test_the_owners_line_at_normal_speed(self) -> None:
        clock = (6, 0, 100_000, 50_000)
        facts = self.read(make_save(clock=clock, trees=[(1, 46_400, 49_000, 300)]),
                          now=real(clock, 50_000))
        first = lines(facts, "Food sources")[0]
        self.assertTrue(first.startswith(
            f"Tree 1: Mango, planted at {gm.when(real(clock, 46_400))}, refills every 3 hours on Normal speed. "
            "300 of 1000 fruit."), first)
        self.assertRegex(first, r"^Tree 1: Mango, planted at \d{1,2} [A-Z][a-z]+ \d{4}, \d{1,2}:\d{2} (AM|PM), "
                                r"refills every 3 hours on Normal speed\.")
        # Picked from 8 hours after planting; the next refill 3 hours after the last.
        self.assertIn(f"Ready to pick from {gm.when(real(clock, 46_400 + 28_800))}.", first)
        self.assertIn(f"Next refill due {gm.when(real(clock, 49_000 + 10_800))} (111 fruit).", first)

    def test_fruit_names_follow_the_kind(self) -> None:
        facts = self.read(make_save(trees=[(0, 1, 1, 0), (1, 1, 1, 0), (2, 1, 1, 0)]))
        names = [re.match(r"Tree \d: (\w+),", t).group(1) for t in lines(facts, "Food sources")[:3]]
        self.assertEqual(names, ["Banana", "Mango", "Papaya"])

    def test_fast_and_slow(self) -> None:
        fast = self.read(make_save(clock=(3, 0, 100_000, 50_000), speed=3, trees=[(0, 1, 49_000, 0)]),
                         now=EPOCH + 100_000)
        self.assertIn("refills every 1 hour 30 minutes on Fast speed.", lines(fast)[0])
        slow = self.read(make_save(clock=(10, 0, 100_000, 50_000), speed=10, trees=[(0, 1, 49_000, 0)]),
                         now=EPOCH + 100_000)
        self.assertIn("refills every 5 hours on Slow speed.", lines(slow)[0])
        # At Slow the planted time is worked back at Slow: 1 game second is 10/6 real ones.
        self.assertIn(f"planted at {gm.when(real((10, 0, 100_000, 50_000), 1, 10))}", lines(slow)[0])

    def test_paused_save_waits(self) -> None:
        facts = self.read(make_save(clock=(0, 6, 100_000, 50_000), speed=1005, trees=[(0, 1, 45_000, 10)]),
                          now=EPOCH + 999_999)
        text = text_of(facts)
        self.assertIn("refills every 3 hours on Normal speed once unpaused.", text)
        self.assertIn(gm.PAUSED_NOTE, text)
        # Paused: 5,000 of the 10,800 game seconds have passed, and nothing more while it waits.
        self.assertIn(f"Next refill (111 fruit) after {gm.duration(5_800)} more of play once unpaused.", text)

    def test_closed_game_catches_up(self) -> None:
        clock = (6, 0, 100_000, 50_000)
        now = real(clock, 50_000) + 20_000           # 20,000 s after the base: 30,000 since the refill
        facts = self.read(make_save(clock=clock, trees=[(0, 1, 40_000, 100)], techs=(1, 1, 1, 1, 1, 0, 0)),
                          now=now)
        gained = (30_000 * 37) // 3600
        self.assertIn(f"A refill was due at {gm.when(real(clock, 50_800))}: the next time the village is played it "
                      f"gets {gained} fruit.", lines(facts)[0])
        self.assertIn("Ready to pick since", lines(facts)[0])

    def test_full_tree(self) -> None:
        facts = self.read(make_save(trees=[(0, 1, 1, 1000)]))
        self.assertIn("Full: a refill adds nothing until fruit is picked.", lines(facts)[0])

    def test_nature_patch_installed(self) -> None:
        nature1 = (1, 1, 1, 1, 1, 1, 0)
        on = self.read(make_save(techs=nature1, trees=[(0, 1, 1, 0)]), features=[vv3.NATURE_PATCH])
        self.assertIn("refills every 2 hours 15 minutes on Normal speed.", lines(on)[0])
        self.assertIn("is in the game.", text_of(on))
        self.assertIn("Honey: gains 2 every 45 minutes on Normal speed", text_of(on))
        off = self.read(make_save(techs=nature1, trees=[(0, 1, 1, 0)]), features=["vv3_birth_control"])
        self.assertIn("refills every 3 hours on Normal speed.", lines(off)[0])
        self.assertIn("is not in the game.", text_of(off))
        self.assertIn("each gains 126 fruit", text_of(off))
        level0 = self.read(make_save(trees=[(0, 1, 1, 0)]), features=[vv3.NATURE_PATCH])
        self.assertIn("refills every 3 hours on Normal speed.", lines(level0)[0])
        self.assertIn("but needs Nature level 1.", text_of(level0))
        self.assertIn("each gains 111 fruit", text_of(level0))
        unknown = self.read(make_save(techs=nature1, trees=[(0, 1, 1, 0)]))
        self.assertIn("could not be told", text_of(unknown))

    def faction_file(self, data: bytes, secondary=5, level=1, primary=6, primary_level=1, fingerprint=None,
                     slot=1) -> bytes:
        buf = data[12:]
        fp = vv3._fnv(buf[:vv3.POINTS + 4]) if fingerprint is None else fingerprint
        entries = struct.pack("<IIBBBBIIB3x", fp & 0xFFFFFFFF, fp >> 32, secondary, level, primary, primary_level,
                              0, 0, 0)
        entries += bytes(24 * (vv3.FACTION_ENTRIES - 1))
        return struct.pack("<5I", vv3.FACTION_MAGIC, 2, 3, slot, 1) + entries

    def test_nature_as_the_second_faction(self) -> None:
        save = make_save(techs=(1, 1, 1, 1, 1, 0, 1), trees=[(0, 1, 1, 0)])
        for fingerprint, expect in ((None, True), (12345, False)):
            with self.subTest(matched=expect):
                folder = Folder(self)
                place = folder.path / "Virtual Villagers Fun Patcher" / "Save 1" / "Data" / "Factions"
                place.mkdir(parents=True)
                (place / "Virtual Villagers 3 Second Faction - Save 1.dat").write_bytes(
                    self.faction_file(save, fingerprint=fingerprint))
                facts = self.read(save, features=[vv3.NATURE_PATCH], folder=folder)
                if expect:
                    self.assertIn("Nature is level 1 (the second faction", text_of(facts))
                    self.assertIn("every 2 hours 15 minutes", lines(facts)[0])
                else:
                    self.assertIn("Nature is level 0", text_of(facts))
                    self.assertIn("every 3 hours", lines(facts)[0])

    def test_tree_timers_file_is_only_noted(self) -> None:
        folder = Folder(self)
        place = folder.path / "Virtual Villagers Fun Patcher" / "Save 1" / "Data" / "Fruit Trees"
        place.mkdir(parents=True)
        (place / "Virtual Villagers 3 Fruit Tree Timers - Save 1.dat").write_bytes(b"x" * 8)
        facts = self.read(make_save(trees=[(0, 1, 1, 0)]), folder=folder)
        self.assertIn("fruit-tree timers file is there", text_of(facts))

    def test_no_trees_and_256_villagers(self) -> None:
        facts = self.read(make_save(size=0x1A4B4))
        self.assertIn("Fruit trees: none is planted yet.", text_of(facts))
        self.assertIn("Honey: 120 of 3000 (The Bee Hive is solved).", text_of(facts))

    def test_not_a_save(self) -> None:
        facts = self.read(make_save()[:-4])
        self.assertEqual([f.group for f in facts], ["Other"])
        self.assertIn("could not be read", facts[0].text)
        missing = gm.read(Folder(self).path, 3, 2, [])
        self.assertIn("could not be read", missing[0].text)

    def test_real_time_only(self) -> None:
        """The owner, 2026-10-22: never game hours or any game-clock unit."""
        for speed, clock in ((6, (6, 0, 100_000, 50_000)), (3, (3, 0, 100_000, 50_000)),
                             (1009, (0, 10, 100_000, 50_000))):
            text = text_of(self.read(make_save(clock=clock, speed=speed, trees=[(2, 1, 49_000, 5)]),
                                     features=[vv3.NATURE_PATCH], now=EPOCH + 150_000))
            self.assertNotRegex(text.lower(), r"game (hour|minute|second|time|clock unit)")

    def test_groups_in_order(self) -> None:
        facts = self.read(make_save(trees=[(0, 1, 1, 0)]))
        order = [gm.GROUPS.index(f.group) for f in facts]
        self.assertEqual(order, sorted(order))

    def test_reads_only(self) -> None:
        folder = Folder(self)
        place = folder.path / "Virtual Villagers Fun Patcher" / "Save 1" / "Data" / "Factions"
        place.mkdir(parents=True)
        save = make_save(techs=(1, 1, 1, 1, 1, 0, 1), trees=[(0, 1, 1, 0)])
        (place / "Virtual Villagers 3 Second Faction - Save 1.dat").write_bytes(self.faction_file(save))
        folder.save(save)
        game = folder.game([vv3.NATURE_PATCH])

        def snapshot():
            return sorted((str(p), p.stat().st_mtime_ns, p.read_bytes() if p.is_file() else b"")
                          for p in folder.root.rglob("*"))

        before = snapshot()
        gm.read(folder.path, 3, 1, [game])
        self.assertEqual(snapshot(), before)


class SaveOffsets(unittest.TestCase):
    """The offsets follow from the stock save writer (vv_game_mechanics_vv3's docstring), so a synthetic
    save built with the module's own constants cannot catch a wrong one: pin them here."""

    def test_the_puzzle_blocks_lead_to_the_trees(self) -> None:
        # The puzzle manager writes 0x2AD and its 0xD0 bytes, then each puzzle object's block in the order
        # 0x4355E0 registers them: 0x594614 (1), honey 0x5945D0 (0x10), 0x593B40 (0x3C), 0x594B3C (1),
        # 0x594BF8 (1), 0x594AD8 (0xC), 0x594BA4 (1), 0x5945BC (1), 0x594870 (0x10), then the trees.
        blocks = [1, 0x10, 0x3C, 1, 1, 0xC, 1, 1, 0x10]
        self.assertEqual(vv3.PUZZLES, 0x11ED4 - 8)               # state +0x11ED4, the buffer is state+8
        self.assertEqual(vv3.HONEY, vv3.PUZZLES + 4 + 0xD0 + 1)
        self.assertEqual(vv3.TREES, vv3.PUZZLES + 4 + 0xD0 + sum(blocks))
        self.assertEqual((vv3.CLOCK, vv3.SPEED, vv3.TECHS, vv3.POINTS), (0x584 - 8, 0x12F18, 0x6CC8 - 8, 0x6CDC))
        self.assertEqual((vv3.READY, vv3.REFILL, vv3.REFILL_PATCHED), (28_800, 10_800, 8_100))


class RealSaves(unittest.TestCase):
    """The committed copies of real Secret City saves (stock and 256 Villagers)."""

    def test_real_saves_read(self) -> None:
        for name in ("vv3-huttest-1.ldw.gz", "vv3-256-1.ldw.gz"):
            with self.subTest(save=name):
                folder = Folder(self)
                folder.save(gzip.decompress((FIXTURES / name).read_bytes()))
                facts = gm.read(folder.path, 3, 1, [])
                text = text_of(facts)
                self.assertNotIn("could not be read", text)
                self.assertIn("Fruit trees: none is planted yet.", text)
                self.assertRegex(text, r"Honey: \d+ of 3000")
                self.assertRegex(text, r"Fruit trees: each gains 111 fruit every (3 hours on Normal|1 hour 30 minutes on Fast) speed")


class EveryGame(unittest.TestCase):
    """All five games: the committed real saves read, real time only, the secrets kept, and no time-away
    figure shown until it is verified."""

    SAVES = ("vv1-huttest-1", "vv2-huttest-1", "vv3-huttest-1", "vv3-256-1", "vv4-huttest-1", "vv4-256-1",
             "vv5-huttest-1", "vv5-256-1")

    def page(self, name: str, data: bytes | None = None, features=None):
        import vv_tribe_rename
        number, slot = int(name[2]), int(name[-1])
        base = next(item.base for item in vv_tribe_rename.GAMES if item.number == number)
        folder = Folder(self, base)
        (folder.path / f"{base}{slot}.ldw").write_bytes(
            data if data is not None else gzip.decompress((FIXTURES / f"{name}.ldw.gz").read_bytes()))
        games = [folder.game(features)] if features is not None else []
        return gm.read(folder.path, number, slot, games, now=EPOCH + 3_000_000)

    def test_every_game_has_a_module(self) -> None:
        for n in range(1, 6):
            module = __import__(f"vv_game_mechanics_vv{n}")
            self.assertTrue(callable(module.facts))

    def test_real_saves_read_in_every_group(self) -> None:
        for name in self.SAVES:
            with self.subTest(save=name):
                facts = self.page(name)
                text = text_of(facts)
                self.assertNotIn("could not be read:", text)
                for group in ("Food sources", "Refills", "Mushrooms", "Tech points and effects",
                              gm.TIME_AWAY, "Island events"):
                    self.assertIn(group, {f.group for f in facts}, group)
                self.assertRegex(text, r"Last saved: \d{1,2} [A-Z][a-z]+ \d{4}, \d{1,2}:\d{2} (AM|PM), ")
                self.assertRegex(text, r"Next island event: ")
                order = [gm.GROUPS.index(f.group) for f in facts]
                self.assertEqual(order, sorted(order))

    def test_real_time_only(self) -> None:
        for name in self.SAVES:
            with self.subTest(save=name):
                text = text_of(self.page(name)).lower()
                self.assertNotRegex(text, r"game (hours?|minutes?|seconds?|clock units?)\b")
                self.assertNotRegex(text, r"\bclock (seconds|units)\b")

    def test_time_away_is_the_verified_clamp(self) -> None:
        """Every game: in full up to 10 h 36 m 40 s / 8 h 36 m 40 s / 6 h 36 m 40 s, then 8 h 36 m 40 s up to
        and including 24 hours, then 24 hours (the coordinator's emulation of each game's own clamp)."""
        for game in range(1, 6):
            with self.subTest(game=game):
                self.assertEqual(gm.counted_away(game, 38_200, 3), 38_200)
                self.assertEqual(gm.counted_away(game, 38_201, 3), 31_000)
                self.assertEqual(gm.counted_away(game, 31_001, 6), 31_000)
                self.assertEqual(gm.counted_away(game, 23_800, 10), 23_800)
                self.assertEqual(gm.counted_away(game, 25_000, 10), 31_000)      # more than was away
                self.assertEqual(gm.counted_away(game, 86_400, 6), 31_000)       # exactly 24 hours: the band
                self.assertEqual(gm.counted_away(game, 86_401, 10), 86_400)
        for name in self.SAVES:
            with self.subTest(save=name):
                joined = " ".join(lines(self.page(name), gm.TIME_AWAY))
                self.assertIn("8 hours 36 minutes 40 seconds", joined)
                self.assertRegex(joined, r"If it were played now: .* away, of which 24 hours counts \((24|12|7\.2)\.0 "
                                         r"years|paused")
                self.assertRegex(joined, r"Time Warp \(the Origins upgrade\): each one gives the villagers (12|6|3) years")
                self.assertNotIn("not yet confirmed", joined)
    def test_time_away_uses_the_verified_table(self) -> None:
        table = {"full": {3: 38_200, 6: 31_000, 10: 23_800}, "band_end": 86_400, "band": 31_000, "over": 86_400}
        old = dict(gm.AWAY_LIMITS)
        gm.AWAY_LIMITS[5] = table
        self.addCleanup(lambda: (gm.AWAY_LIMITS.clear(), gm.AWAY_LIMITS.update(old)))
        self.assertEqual(gm.counted_away(5, 10_000, 6), 10_000)
        self.assertEqual(gm.counted_away(5, 40_000, 6), 31_000)
        self.assertEqual(gm.counted_away(5, 90_000, 10), 86_400)
        joined = " ".join(lines(self.page("vv5-huttest-1"), gm.TIME_AWAY))
        self.assertIn("of which", joined)
        self.assertIn("8 hours 36 minutes 40 seconds", joined)

    def test_unverified_lines_carry_the_label(self) -> None:
        """The owner, 2026-10-23: every figure or statement not verified by emulation carries UNCONFIRMED,
        in capitals, right beside it; verified ones (and values read straight from the save) carry nothing."""
        for name in self.SAVES:
            with self.subTest(save=name):
                facts = self.page(name)
                rendered = gm.render(facts).split("\n")
                body = [line for line in rendered if line.startswith("  ")]
                self.assertEqual(len(body), len(facts))
                for fact, line in zip(facts, body):
                    if fact.verified:
                        self.assertNotIn(gm.UNCONFIRMED, line)
                    else:
                        self.assertTrue(line.startswith(f"  {gm.UNCONFIRMED}  "), line)
                self.assertTrue(any(f.verified for f in facts))
                self.assertTrue(any(not f.verified for f in facts))
                for fact in facts:
                    if fact.group == gm.TIME_AWAY and fact.text.startswith(("Last saved", "If it were", "On ",
                                                                          "Time Warp")):
                        self.assertTrue(fact.verified, fact.text)
                text = gm.render(facts)
                self.assertNotIn("(uncertain)", text)
                self.assertNotIn("not yet confirmed in game", text)
                for line in body:
                    content = line.strip().removeprefix(f"{gm.UNCONFIRMED}  ")
                    self.assertNotRegex(content, r" [.;,]|  |\(\)", content)
    def test_golden_mushroom_stays_a_secret(self) -> None:
        for name, fid in (("vv1-huttest-1", "vv1_super_secret_golden_mushroom"),
                          ("vv2-huttest-1", "vv2_super_secret_golden_mushroom"),
                          ("vv3-huttest-1", "vv3_super_secret_golden_mushroom"),
                          ("vv4-huttest-1", "vv4_super_secret_golden_mushroom"),
                          ("vv5-huttest-1", "vv5_super_secret_golden_mushroom")):
            with self.subTest(save=name):
                text = text_of(self.page(name, features=[fid]))
                self.assertIn("there is a secret to find", text)
                self.assertNotRegex(text.lower(), r"golden mushroom(?!\x22 is in the game: there is a secret to find\.)")
                self.assertNotRegex(text.lower(), r"1,000,000|1 in 1,000\b")
                self.assertNotIn("secret", text_of(self.page(name, features=[])))

    def test_paused_saves_wait(self) -> None:
        import vv_save_backup
        for name in ("vv1-huttest-1", "vv2-huttest-1", "vv4-huttest-1", "vv5-huttest-1"):
            with self.subTest(save=name):
                data = gzip.decompress((FIXTURES / f"{name}.ldw.gz").read_bytes())
                paused = vv_save_backup.pause_save_bytes(int(name[2]), data)
                if paused is None:
                    paused = data
                text = text_of(self.page(name, data=paused))
                self.assertIn(", paused.", text)
                self.assertIn("after it is unpaused", text)
                self.assertIn(gm.PAUSED_NOTE, text)

    def test_vv1_values(self) -> None:
        data = bytearray(gzip.decompress((FIXTURES / "vv1-huttest-1.ldw.gz").read_bytes()))
        import vv_game_mechanics_vv1 as vv1
        struct.pack_into("<i", data, vv1.BUSH, 1300)
        struct.pack_into("<i", data, vv1.SPEED, 6)
        text = text_of(self.page("vv1-huttest-1", data=bytes(data)))
        self.assertIn("Berry bush: 1,300; a pick takes 10 from it now", text)
        self.assertIn("The berry bush grows 30 every 4 hours on Normal speed", text)
        self.assertIn("Each villager eats 2 food every 6 minutes on Normal speed (20 an hour).", text)
        self.assertNotIn("Collectibles\n  A New Home has collectibles", text)

    def test_vv2_values(self) -> None:
        import vv_game_mechanics_vv2 as vv2
        data = bytearray(gzip.decompress((FIXTURES / "vv2-huttest-1.ldw.gz").read_bytes()))
        struct.pack_into("<i", data, vv2.SPEED + vv2.S, 3)
        struct.pack_into("<i", data, vv2.COCONUTS + vv2.S, 1234)
        text = text_of(self.page("vv2-huttest-1", data=bytes(data)))
        self.assertIn("Coconuts: 1,234; a trip brings 8 on Fast speed", text)
        self.assertIn("every 2 hours on Fast speed: coconuts +30", text)
        self.assertIn("a lit fire burns 10 hours on Fast speed", text)
        totems = text_of(self.page("vv2-huttest-1", data=bytes(data), features=["vv2_totems_out_of_entries"]))
        self.assertIn("with no limit on how many", totems)
        self.assertIn("while there are fewer than 50 totems", text)

    def test_vv4_and_vv5_values(self) -> None:
        import vv_game_mechanics_vv4 as vv4
        import vv_game_mechanics_vv5 as vv5
        data = bytearray(gzip.decompress((FIXTURES / "vv4-huttest-1.ldw.gz").read_bytes()))
        struct.pack_into("<i", data, vv4.BERRIES, 500)
        struct.pack_into("<i", data, vv4.LEVELS + 4 * vv4.FOOD_MASTERY, 1)
        text = text_of(self.page("vv4-huttest-1", data=bytes(data)))
        self.assertIn("Blackberries: 500 of 1,000; a pick brings 5 food now", text)
        data = bytearray(gzip.decompress((FIXTURES / "vv5-huttest-1.ldw.gz").read_bytes()))
        struct.pack_into("<i", data, vv5.NONI, 640)
        struct.pack_into("<i", data, vv5.SPEED, 10)
        text = text_of(self.page("vv5-huttest-1", data=bytes(data)))
        self.assertIn("Noni bushes: 640 of 1,000; a pick gives 6 food now", text)
        self.assertIn("Noni: +2 every 10 minutes on Slow speed", text)
        self.assertNotIn("Stinging Wasps", text)            # never happens in New Believers

    def test_not_a_save(self) -> None:
        for name in ("vv1-huttest-1", "vv2-huttest-1", "vv4-huttest-1", "vv5-huttest-1"):
            with self.subTest(save=name):
                facts = self.page(name, data=b"ldwg" + bytes(40))
                self.assertEqual([f.group for f in facts], ["Other"])
                self.assertIn("could not be read", facts[0].text)

class InstalledPatches(unittest.TestCase):
    def test_report_lists_the_ids(self) -> None:
        folder = Folder(self)
        game = folder.game(["vv3_nature_honey_refill", "vv3_both_factions"])
        self.assertEqual(gm.installed_features(folder.path, [Path("elsewhere"), game]),
                         frozenset({"vv3_nature_honey_refill", "vv3_both_factions"}))
        self.assertIsNone(gm.installed_features(folder.path, []))
        other = folder.root / "games2" / "Some Other Game"
        other.mkdir(parents=True)
        self.assertIsNone(gm.installed_features(folder.path, [other]))


TK_CHILD = r"""
import sys, tkinter
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import vv_save_backup, vv_game_mechanics_window as w
folder, game_folder = Path(sys.argv[2]), Path(sys.argv[3])
vv_save_backup.documents_folder = lambda: folder.parent
vv_save_backup.find_save_folders = lambda title, documents: [folder]
try:
    root = tkinter.Tk()
except tkinter.TclError as exc:
    print(exc, file=sys.stderr)
    sys.exit(3)
root.withdraw()
class Build:
    title = "Virtual Villagers - The Secret City"
root.builds = [Build()]
root._game_folders_for = lambda save_folder: [game_folder]
window = w.open_game_mechanics(root, Build())
window.update()
page = window.mechanics_page
text = page.get("1.0", "end")
print(window.resizable() == (True, True), int(bool(page.cget("yscrollcommand"))))
# At its smallest the intro wraps at the window's width; the pickers, the buttons and the padding
# must leave the page at least 80 pixels (about four lines) -- nothing above or below it cut off.
pickers, intro, buttons, note = window.mechanics_parts
intro.configure(wraplength=w.MIN_WIDTH - 40)
note.configure(wraplength=w.MIN_WIDTH - 40)
window.update_idletasks()
fixed = pickers.winfo_reqheight() + buttons.winfo_reqheight() + 24 + 16
print(fixed + 80 <= w.MIN_HEIGHT, pickers.winfo_reqwidth() <= w.MIN_WIDTH - 24, fixed)
print(len(page.tag_ranges('unconfirmed')) > 0, 'UNCONFIRMED marks' in note.cget('text'))
print(repr(text))
root.destroy()
"""


class Window(unittest.TestCase):
    """Game Mechanics is a window of its own on the Tools tab (the owner, 2026-10-22), not part of
    Repair Saves & Logs; it is resizable, its page scrolls, and nothing is cut off."""

    def test_linked_from_the_tools_tab_only(self) -> None:
        source = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertIn('"Game Mechanics...", self._game_mechanics_single', source)
        self.assertIn("vv_game_mechanics_window.open_game_mechanics(self, game)", source)
        self.assertIn("vv_game_mechanics_window.open_game_mechanics(self, None)", source)
        tree = ast.parse(source)
        log_tool = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                        and node.name == "_log_tool")
        self.assertNotIn("mechanics", ast.get_source_segment(source, log_tool))

    def test_page_text_never_raises(self) -> None:
        import vv_game_mechanics_window as window
        folder = Folder(self)
        self.assertIn("could not be read", window.page_text(folder.path, 3, 1, []))
        folder.save(make_save(trees=[(1, 1, 1, 5)]))
        self.assertIn("Tree 1: Mango", window.page_text(folder.path, 3, 1, []))

    def test_real_window(self) -> None:
        """A real save (the committed Secret City save, with a mango tree written into its copy) in the
        real window: its page, its scroll bar, and the pickers and buttons on screen at its smallest."""
        folder = Folder(self, BASE)
        for slot in (0, 1):
            data = bytearray(gzip.decompress((FIXTURES / f"vv3-huttest-{slot}.ldw.gz").read_bytes()))
            if slot == 1:
                at = 12 + vv3.TREES
                struct.pack_into("<6i", data, at + 0x14, 1300, 1200, 100, 100, 1, 640)
                struct.pack_into("<i", data, at + 0x5C, 1)
            (folder.path / f"{BASE}{slot}.ldw").write_bytes(bytes(data))
        game = folder.game([vv3.NATURE_PATCH])
        done = subprocess.run([sys.executable, "-c", TK_CHILD, str(ROOT / "src"), str(folder.path), str(game)],
                              capture_output=True, text=True, timeout=120)
        if done.returncode == 3:
            self.skipTest("no Tk display: " + done.stderr.strip())
        self.assertEqual(done.returncode, 0, done.stderr)
        first, second, tags, text = done.stdout.strip().splitlines()[:4]
        self.assertEqual(first, "True 1")
        self.assertEqual(second.split()[:2], ["True", "True"], second)
        self.assertIn("Tree 1: Mango, planted at ", text)
        self.assertIn("640 of 1000 fruit", text)
        self.assertIn("is in the game", text)
        self.assertEqual(tags, "True True")


if __name__ == "__main__":
    unittest.main()