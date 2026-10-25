"""Repair Saves & Logs' Game Mechanics section (src/vv_game_mechanics.py) and The Secret City's fruit
trees and honey (src/vv_game_mechanics_vv3.py): read-only, real time only, the owner's line format.

Synthetic saves are built byte by byte at the offsets the stock save writer uses (the module's
docstring); the committed real Secret City saves (tests/fixtures/rename_tribe) are read too.
"""
from __future__ import annotations

import ast
import gzip
import hashlib
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
              trees=(), honey=(49_000, 120), hive=True, points=7, created=0) -> bytes:
    buf = bytearray(size)
    struct.pack_into("<4i", buf, vv3.CLOCK, *clock)
    struct.pack_into("<i", buf, vv3.STATS, created)          # the village's start (wall seconds; 0: none)
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
        # The report the patcher writes beside the exe it made, with that exe's hash (vv_game_mechanics.patch_source
        # uses a log only when its hash is the exe's as it is now).
        lines = ["Patcher version/commit: v1.35.81 / unavailable", f"Modified EXE: {self.path.name}.exe | size 2 | SHA-256 "
                 f"{hashlib.sha256(b'MZ').hexdigest()}", "Timestamp (UTC): 2026-10-23T00:00:00+00:00"]
        lines += [f"- Optional feature: Name of {fid} [{fid}]" for fid in features]
        (game / "Virtual Villagers Fun Patcher Files" / "VVFP Transparency Log.txt").write_text(
            "\n".join(lines) + "\n", encoding="utf-8")
        return game


def text_of(facts) -> str:
    return gm.render(facts)


def lines(facts, group=None) -> list[str]:
    return [f.text for f in facts if group is None or f.group == group]


def tree(facts, number=1) -> list[str]:
    """A tree's parent bullet and its sub-bullets."""
    out, inside = [], False
    for f in facts:
        if f.group != "Food sources":
            continue
        if not f.sub:
            inside = f.text.startswith(f"Tree {number}: ")
            if inside:
                out.append(f.text)
        elif inside:
            out.append(f.text)
    return out


def planted(facts, number=1) -> str:
    return next(t for t in tree(facts, number) if t.startswith("Planted "))


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
        # Planted after the clock's base: the save dates it.
        clock = (6, 0, 100_000, 50_000)
        facts = self.read(make_save(clock=clock, trees=[(1, 50_400, 51_000, 300)]), now=real(clock, 52_000))
        lines_ = tree(facts)
        self.assertEqual(lines_[0], "Tree 1: Mango")
        self.assertEqual(lines_[1], f"Planted at {gm.when(real(clock, 50_400))}; refills every 3 hours on Normal speed.")
        self.assertRegex(lines_[1], r"^Planted at \d{1,2} [A-Z][a-z]+ \d{4}, \d{1,2}:\d{2} (AM|PM); "
                                    r"refills every 3 hours on Normal speed\.$")
        self.assertEqual(lines_[2], "300 of 1000 fruit.")
        # Picked from 8 hours after planting; the next refill 3 hours after the last.
        self.assertEqual(lines_[3], f"Ready to pick from {gm.when(real(clock, 50_400 + 28_800))}.")
        self.assertEqual(lines_[4], f"Next refill due {gm.when(real(clock, 51_000 + 10_800))} (111 fruit).")
        self.assertTrue(all(f.sub for f in facts if f.group == "Food sources" and f.text in lines_[1:]))

    def test_planted_before_the_clocks_base_is_not_dated(self) -> None:
        """The owner's Secret City save (2026-10-23): Tree 1 planted 147 game seconds after the village was made,
        the clock's base at 144,871 -- the old line worked the date back at today's speed and printed a moment 19
        hours too late.  Before the base the save keeps no real date: the line gives the village's age then."""
        clock = (6, 0, 782_113, 144_871)
        created = 567_237
        facts = self.read(make_save(clock=clock, created=created, trees=[(1, 147, 144_434, 1)]),
                          now=EPOCH + 782_113 + 60)
        line = planted(facts)
        restarted = gm.when(EPOCH + 782_113)
        self.assertEqual(line, f"Planted when the village was 2 minutes 27 seconds old, counted on Normal speed (started "
                               f"{gm.when(EPOCH + created)}; the save keeps no real date before {restarted}); refills "
                               "every 3 hours on Normal speed.")
        self.assertNotIn(gm.when(EPOCH + 782_113 + (147 - 144_871)), text_of(facts))     # the old, wrong date
        self.assertIn("Ready to pick since the village was 8 hours 2 minutes 27 seconds old", text_of(facts))
        self.assertIn(f"The village was started at {gm.when(EPOCH + created)}.", lines(facts, "Other"))

    def test_a_speed_change_after_planting_does_not_move_its_date(self) -> None:
        """Two saves of the same village, the second after a spell on Fast speed: the base moved, so the old line's
        date for the same planting moved too.  Now neither dates it, and both give the same age."""
        before = self.read(make_save(clock=(6, 0, 100_000, 50_000), trees=[(0, 40_000, 49_000, 0)]),
                           now=EPOCH + 100_000)
        after = self.read(make_save(clock=(3, 6, 110_000, 70_000), speed=3, trees=[(0, 40_000, 49_000, 0)]),
                          now=EPOCH + 110_000)
        age = "the village was 11 hours 6 minutes 40 seconds old, counted on Normal speed"
        self.assertIn(age, planted(before))
        self.assertIn(age, planted(after))
        self.assertNotIn(" at ", planted(before).split(";")[0])
        self.assertNotIn(" at ", planted(after).split(";")[0])

    def test_fruit_names_follow_the_kind(self) -> None:
        facts = self.read(make_save(trees=[(0, 1, 1, 0), (1, 1, 1, 0), (2, 1, 1, 0)]))
        names = [re.match(r"Tree \d: (\w+)$", t).group(1) for t in lines(facts, "Food sources")
                 if re.match(r"Tree \d: \w+$", t)]
        self.assertEqual(names, ["Banana", "Mango", "Papaya"])

    def test_fast_and_slow(self) -> None:
        fast = self.read(make_save(clock=(3, 0, 100_000, 50_000), speed=3, trees=[(0, 1, 49_000, 0)]),
                         now=EPOCH + 100_000)
        self.assertIn("refills every 1 hour 30 minutes on Fast speed.", planted(fast))
        slow = self.read(make_save(clock=(10, 0, 100_000, 50_000), speed=10, trees=[(0, 50_001, 49_000, 0)]),
                         now=EPOCH + 100_000)
        self.assertIn("refills every 5 hours on Slow speed.", planted(slow))
        # After the base at Slow a game second is 10/6 real ones.
        self.assertIn(f"Planted at {gm.when(real((10, 0, 100_000, 50_000), 50_001, 10))}", planted(slow))

    def test_paused_save_waits(self) -> None:
        facts = self.read(make_save(clock=(0, 6, 100_000, 50_000), speed=1005, trees=[(0, 1, 45_000, 10)]),
                          now=EPOCH + 999_999)
        text = text_of(facts)
        self.assertIn("refills every 3 hours on Normal speed once unpaused.", text)
        self.assertIn(gm.PAUSED_NOTE, text)
        # Paused: 5,000 of the 10,800 game seconds have passed, and nothing more while it waits.
        self.assertIn(f"Next refill (111 fruit) after {gm.duration(5_800)} more of play once unpaused.", tree(facts))

    def test_closed_game_catches_up(self) -> None:
        clock = (6, 0, 100_000, 50_000)
        now = real(clock, 50_000) + 20_000           # 20,000 s after the base: 30,000 since the refill
        facts = self.read(make_save(clock=clock, trees=[(0, 1, 40_000, 100)], techs=(1, 1, 1, 1, 1, 0, 0)),
                          now=now)
        gained = (30_000 * 37) // 3600
        lines_ = tree(facts)
        # The refill was due at 50,800, after the base: dated.
        self.assertIn(f"The next time the village is played it gets {gained} fruit: a refill was due at "
                      f"{gm.when(real(clock, 50_800))}.", lines_)
        self.assertTrue(any(line.startswith("Ready to pick since the village was") for line in lines_))

    def test_full_tree(self) -> None:
        facts = self.read(make_save(trees=[(0, 1, 1, 1000)]))
        self.assertIn("Full; a refill adds nothing until fruit is picked.", tree(facts))
    def test_nature_patch_installed(self) -> None:
        nature1 = (1, 1, 1, 1, 1, 1, 0)
        on = self.read(make_save(techs=nature1, trees=[(0, 1, 1, 0)]), features=[vv3.NATURE_PATCH])
        self.assertIn("refills every 2 hours 15 minutes on Normal speed.", planted(on))
        self.assertIn("is in the game.", text_of(on))
        self.assertIn("Honey: gains 2 every 45 minutes on Normal speed", text_of(on))
        off = self.read(make_save(techs=nature1, trees=[(0, 1, 1, 0)]), features=["vv3_birth_control"])
        self.assertIn("refills every 3 hours on Normal speed.", planted(off))
        self.assertIn("is not in the game.", text_of(off))
        self.assertIn("each gains 126 fruit", text_of(off))
        level0 = self.read(make_save(trees=[(0, 1, 1, 0)]), features=[vv3.NATURE_PATCH])
        self.assertIn("refills every 3 hours on Normal speed.", planted(level0))
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
                    self.assertIn("every 2 hours 15 minutes", planted(facts))
                else:
                    self.assertIn("Nature is level 0", text_of(facts))
                    self.assertIn("every 3 hours", planted(facts))

    def test_patch_tree_schedule(self) -> None:
        """The Refill Together / Take Turns patches' file (native/shared/vv3_fruit_timers.h): a tree shows the
        patch's schedule when an entry matches this save's trees, the save's own timers otherwise."""
        clock = (6, 0, 100_000, 50_000)
        data = make_save(clock=clock, trees=[(1, 1_000, 49_000, 300), (0, 2_000, 48_000, 200)])
        buf = data[12:]
        fp = vv3._trees_fingerprint(buf)
        entries = bytearray(20 * 0 + vv3.TIMER_ENTRIES * vv3.TIMER_ENTRY)
        struct.pack_into("<IIBBBBI3I3I", entries, 0, fp & 0xFFFFFFFF, fp >> 32, 1, 2, 0, 0, 10_800,
                         49_500, 49_500, 0, 55_000, 55_000, 0)
        for matched, fingerprint in ((True, fp), (False, fp ^ 1)):
            with self.subTest(matched=matched):
                body = bytearray(entries)
                struct.pack_into("<II", body, 0, fingerprint & 0xFFFFFFFF, fingerprint >> 32)
                folder = Folder(self)
                place = folder.path / "Virtual Villagers Fun Patcher" / "Save 1" / "Data" / "Fruit Trees"
                place.mkdir(parents=True)
                (place / "Virtual Villagers 3 Fruit Tree Timers - Save 1.dat").write_bytes(
                    struct.pack("<5I", vv3.TIMER_MAGIC, 1, 3, 1, 1) + bytes(body))
                facts = self.read(data, folder=folder, now=real(clock, 50_000))
                tree1, tree2 = tree(facts, 1), tree(facts, 2)
                if matched:
                    self.assertIn('On the patcher\'s "All Fruit Trees Refill at the Same Time" schedule, read '
                                  'from its file for this save.', tree1)
                    self.assertIn(f"Next refill due {gm.when(real(clock, 55_000))} (111 fruit).", tree1)
                    self.assertIn(f"Next refill due {gm.when(real(clock, 55_000))} (111 fruit).", tree2)
                else:
                    self.assertFalse(any("schedule" in line for line in tree1 + tree2))
                    self.assertIn(f"Next refill due {gm.when(real(clock, 49_000 + 10_800))} (111 fruit).", tree1)
                    self.assertIn("has no schedule for this save", text_of(facts))
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
        self.assertEqual([f.group for f in facts if f.group != gm.SOURCES], ["Other"])
        self.assertIn("could not be read", facts[-1].text)
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


class BrewedPotion(unittest.TestCase):
    """The owner, 2026-10-24: a brewed potion's time changes with the game speed -- the old "5 minutes, at any
    speed and even while paused" was wrong.  The pot's countdown (0x469B53) is the time left x rate / 6."""

    def read(self, speed: int):
        folder = Folder(self)
        folder.save(make_save(clock=(speed, 0, 100_000, 50_000), speed=speed))
        return gm.read(folder.path, 3, 1, [])

    def test_the_line_is_given_at_the_saves_speed(self) -> None:
        for speed, shows in ((gm.NORMAL, "5:00"), (gm.FAST, "2:30"), (gm.SLOW, "8:20")):
            with self.subTest(speed=speed):
                facts = self.read(speed)
                # Once, under Tech points and effects (the audit, 2026-10-25: no line repeated in another group).
                potion = [f for f in facts if f.text.startswith("A brewed potion:")]
                self.assertEqual(len(potion), 1)
                self.assertEqual(potion[0].text, (
                    f"A brewed potion: the pot's on-screen countdown starts at {shows} on {gm.speed_name(speed)} "
                    "speed (5:00 on Normal, 2:30 on Fast, 8:20 on Slow: what it shows changes with the speed), and "
                    "the potion is gone when it reaches 0:00."))
                # Traced on the game's live code and seen by the owner: no UNCONFIRMED.
                self.assertTrue(all(f.confirmed for f in potion))
                text = gm.render(facts)
                self.assertNotIn("at any speed and even while paused", text)
                self.assertNotIn("a potion keeps 5 minutes", text)
                self.assertNotIn("A brewed potion keeps", text)

    def test_the_per_speed_values_are_the_countdowns(self) -> None:
        # 300 seconds left x rate / 6 (0x426580), shown as m:ss.
        for speed, shows in vv3.POTION_COUNTDOWN.items():
            minutes, rest = divmod(300 * speed // 6, 60)
            self.assertEqual(shows, f"{minutes}:{rest:02d}")

    def test_the_cant_drink_answer_and_the_owner_confirmed_lines(self) -> None:
        facts = self.read(gm.NORMAL)
        other = {f.text: f for f in facts if f.group == "Other"}
        herbs = next(f for t, f in other.items() if t.startswith("Herbs never run out"))
        self.assertEqual(herbs.text, vv3.HERBS_LINE)              # the owner's confirmed wording, unchanged
        self.assertIn("A villager cannot drink a potion whose effect they already have, or any potion while they "
                      "already have 4 effects.", herbs.text)
        self.assertTrue(herbs.confirmed)
        cant = other[vv3.CANT_DRINK_LINE]
        self.assertTrue(cant.confirmed)
        self.assertTrue(cant.text.startswith("\"That villager can't drink another potion so soon.\" is the game's "
                                             "answer when the rule above refuses a potion"))
        self.assertIn("10 or 5 real-life minutes", cant.text)
        self.assertIn("a save holds none to count down", cant.text)
        names = [f.text for f in facts]
        self.assertEqual(names.index(cant.text), names.index(herbs.text) + 1)   # right after the rule it explains


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


class StewPots(unittest.TestCase):
    """The owner, 2026-10-24: when stews and their effects end, and what empties the pot, in VV2 to VV4."""

    page = lambda self, name: EveryGame.page(self, name)  # noqa: E731

    def facts(self, name):
        return {f.text: f for f in self.page(name)}

    def test_lost_children_pot_and_effects(self) -> None:
        import vv_game_mechanics_vv2 as vv2
        facts = self.facts("vv2-huttest-1")
        pot = facts[vv2.STEW_POT_LINE]
        self.assertTrue(pot.confirmed)
        self.assertIn("15 real-life minutes at every speed, then empties itself", pot.text)
        self.assertIn("Eating does not empty it", pot.text)
        self.assertIn("no countdown", pot.text)
        effect = facts[vv2.STEW_EFFECT_LINE]
        self.assertTrue(effect.confirmed)       # the 75 routines reached from 0x461040 read no clock (2026-10-25)
        text = gm.render(list(facts.values()))
        self.assertNotIn("A stew is ready 15 minutes after it starts", text)
        self.assertIn("the fire and the stew pot (Other)", text)

    def test_secret_city_table_empties_the_pot(self) -> None:
        facts = self.facts("vv3-huttest-1")
        line = facts[vv3.POT_EMPTIED_LINE]
        self.assertTrue(line.confirmed)                       # the owner's word, and 0x430D90 -> 0x430D00
        self.assertTrue(line.text.startswith("The pot can be emptied by dropping a villager on the table with 3 "
                                             "herbs"))

    def test_tree_of_life_pot_grate_reheat_and_answer(self) -> None:
        import vv_game_mechanics_vv4 as vv4
        facts = self.facts("vv4-huttest-1")
        pot = [f for t, f in facts.items() if t.startswith("A ready stew: the pot's on-screen countdown starts at ")]
        self.assertEqual(len(pot), 1)
        self.assertTrue(pot[0].confirmed)
        for speed, shows in ((gm.NORMAL, "5:00"), (gm.FAST, "2:30"), (gm.SLOW, "8:20")):
            self.assertIn(f"starts at {shows} on {gm.speed_name(speed)} speed", vv4.stew_pot_line(speed))
        for speed, shows in vv4.STEW_COUNTDOWN.items():            # 300 real seconds x rate / 6, as m:ss
            minutes, rest = divmod(300 * speed // 6, 60)
            self.assertEqual(shows, f"{minutes}:{rest:02d}")
        self.assertTrue(facts[vv4.GRATE_LINE].confirmed)
        self.assertEqual(vv4.GRATE_LINE, "The pot can be emptied by dropping a villager on the grate.")
        self.assertTrue(facts[vv4.REHEAT_LINE].confirmed)     # the owner's word
        code = facts[vv4.REHEAT_CODE_LINE]
        self.assertTrue(code.confirmed)                       # 0x42EAA7, 0x42DC80, 0x42EA61, 0x42EE1D, 0x42F240
        for words in ("each hot rock adds 10 heat", "the Grand Feast at 20 with its 4 feast items",
                      "the two salt-water mixes (soapy x3, pulpy vines x3) need no heat",
                      "stays hot for 10 real-life minutes on Normal speed (5 on Fast, 16 minutes 40 seconds on Slow)",
                      "starts its 5 real-life minutes over; nothing limits how often"):
            self.assertIn(words, code.text)
        self.assertTrue(facts[vv4.CANT_EAT_LINE].confirmed)
        text = gm.render(list(facts.values()))
        self.assertIn("5 real-life minutes after the stew was made at every speed", text)
        # The lock-out is that stew only, for that villager (0x45EB40); soapy x3 sets no sickness (0x41E0BC).
        self.assertIn("that villager cannot eat that stew again for 10 real-life minutes", text)
        self.assertNotIn("then no stew for 10 real-life minutes", text)
        self.assertIn("(it does not make the villager sick)", text)
        self.assertIn("spicy, soapy, soapy: \"Burping up soap bubbles\"", text)
        self.assertNotIn("the soapy-stew reaction", text)
        self.assertNotIn("a stew keeps 5 minutes", text)


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
                # The next natural island event: one full copy, under Village timers; Island events points there.
                self.assertEqual(len([f for f in facts if f.text.startswith("Next natural island event:")]), 1)
                self.assertTrue(all(f.group == "Village timers" for f in facts
                                    if f.text.startswith("Next natural island event:")))
                self.assertIn("When the next natural island event comes: under Village timers.", text)
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
                if name.startswith("vv5"):
                    # New Believers' Time Warp upgrade is the patcher's Origins patch: shown only when the exe has
                    # it (the audit of 2026-10-25), and these test saves have no game folder to tell.
                    self.assertNotIn("Origins upgrade", joined)
                else:
                    # The Origins Time Warp is the patcher's, shown only with it in the current exe; these saves
                    # have no game folder to tell, so the stock value is given (the clean-up of 2026-10-25).
                    self.assertNotIn("Origins upgrade", joined)
                    self.assertIn("Time Warp: the stock game has none; whether the patcher's", joined)
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
                body = [line for line in rendered if line.startswith((gm.BULLET, gm.SUB_BULLET))]
                self.assertEqual(len(body), len(facts))
                for fact, line in zip(facts, body):
                    mark = gm.SUB_BULLET if fact.sub else gm.BULLET
                    if fact.confirmed:
                        self.assertNotIn(gm.UNCONFIRMED, line)
                        self.assertTrue(line.startswith(mark), line)
                    else:
                        self.assertTrue(line.startswith(f"{mark}{gm.UNCONFIRMED}  "), line)
                self.assertTrue(any(f.confirmed for f in facts))
                self.assertTrue(any(not f.confirmed for f in facts))
                for fact in facts:
                    if fact.group == gm.TIME_AWAY and fact.text.startswith(("Last saved", "If it were", "On ",
                                                                          "Time Warp")):
                        self.assertTrue(fact.confirmed, fact.text)
                text = gm.render(facts)
                self.assertNotIn("(uncertain)", text)
                self.assertNotIn("not yet confirmed in game", text)
                for line in body:
                    content = line.removeprefix(gm.SUB_BULLET).removeprefix(gm.BULLET).removeprefix(f"{gm.UNCONFIRMED}  ")
                    self.assertNotRegex(content, r" [.;,]|  |\(\)", content)
    def test_old_age_rule(self) -> None:
        """The verified old-age rule (all five games): a death roll by the hidden processed age, never "certain
        at" an age, with the shown-age difference explained."""
        for name in self.SAVES:
            with self.subTest(save=name):
                facts = self.page(name)
                text = gm.render(facts)
                self.assertNotIn("certain at", text)
                self.assertNotIn("lives past", text)
                old = [f for f in facts if f.text.startswith("Old age:")]
                self.assertEqual(len(old), 1)
                self.assertTrue(old[0].confirmed)
                self.assertIn("so the chance is 10% for each year over", old[0].text)
                self.assertIn("10.01%", old[0].text)                  # the exact odds, once (Chances points here)
                self.assertIn("The old-age death roll: its timing and exact odds are under Death and graves",
                              text)
                self.assertNotIn("a villager dies with a chance of 10% for each year past it", text)
                self.assertIn("processed age", old[0].text)
    def test_nothing_inferred(self) -> None:
        """The owner: DO NOT INFER -- no guessing words, no names chosen from a theme (The Tree of Life's Mausoleum
        and Wind Flute sets are named by the owner)."""
        for name in self.SAVES:
            with self.subTest(save=name):
                text = gm.render(self.page(name)).lower()
                self.assertNotRegex(text, r"probabl|(?<!equally )likely|perhaps|presumab|relic")
    def test_golden_mushroom_facts_only_with_its_patch(self) -> None:
        """The owner, 2026-10-23: with the patch in the game the page gives the Golden Mushroom's facts (100 food, 1 in
        1,000,000 random brown or red mushrooms); without it nothing about it at all."""
        for name, fid in (("vv1-huttest-1", "vv1_super_secret_golden_mushroom"),
                          ("vv2-huttest-1", "vv2_super_secret_golden_mushroom"),
                          ("vv3-huttest-1", "vv3_super_secret_golden_mushroom"),
                          ("vv4-huttest-1", "vv4_super_secret_golden_mushroom"),
                          ("vv5-huttest-1", "vv5_super_secret_golden_mushroom")):
            with self.subTest(save=name):
                line = next(f for f in self.page(name, features=[fid]) if "Golden Mushroom instead" in f.text)
                self.assertIn("1 in 1,000,000 of the random brown or red mushrooms", line.text)
                self.assertIn("worth 100 food", line.text)
                self.assertIn("counts as a mushroom", line.text)
                self.assertEqual(line.group, "Mushrooms")
                for features in ([], None):
                    off = text_of([f for f in self.page(name, features=features) if f.group != gm.SOURCES]).lower()
                    self.assertNotIn("golden mushroom", off)
                    self.assertNotIn("secret", off)
                    self.assertNotIn("1,000,000", off)

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
        self.assertIn("Berry bush: 1,300; a pick brings 10 food now and takes as much from the bush", text)
        self.assertIn("The berry bush grows 30 every 4 hours of real-life play on Normal speed", text)
        self.assertIn("Each villager eats 2 food every age unit (6 minutes of real-life play on Normal speed, 20 food "
                      "per real-life hour)", text)
        self.assertNotIn("Collectibles\n  A New Home has collectibles", text)

    def test_vv1_audit(self) -> None:
        """The A New Home audit (2026-10-25, the stock exe): the skill gain is (50 - skill) x 2 / 10, / 9 for Healing
        (0x43D814); research never lacks Science (every technology starts at 1, 0x41C43E); the Golden Child regains
        health on the food store and from The Black Pearl, which also lifts bodies (0x41A050); a crab is 21.02%
        (0x43F4C3); the crop field never stays past 800 (0x42F2C5); duplicates of other groups are gone."""
        data = bytearray(gzip.decompress((FIXTURES / "vv1-huttest-1.ldw.gz").read_bytes()))
        import vv_game_mechanics_vv1 as vv1
        struct.pack_into("<i", data, vv1.SPEED, 6)
        facts = self.page("vv1-huttest-1", data=bytes(data))
        text = text_of(facts)
        self.assertIn("and by (50 - skill) x 2 ÷ 9 for Healing: 10 at skill 0 (Healing 11)", text)
        self.assertNotIn("Research gives no tech points", text)
        self.assertIn("Health does come back two ways", text)
        self.assertIn("instead catches a crab worth 55 food 21.02% of the time", text)
        self.assertIn("which the game cuts back to 800 within 2 real-life seconds", text)
        self.assertIn("a body at 0 health (old age, sickness, hunger", text)
        self.assertNotIn("not yet worked out", text)
        self.assertNotIn("save every 10 minutes", text)
        # The autosave (the owner, 2026-10-25; 0x41BFC0 -> 0x41BF70), and the Sources line agrees with it.
        self.assertIn("once 10 real-life minutes have passed since the program started or since its last autosave",
                      text)
        self.assertIn("checks the computer's clock on every frame", text)
        self.assertNotIn("switches from one of its screens", text)     # the check is per frame, not per switch
        self.assertIn("The game writes it when it is closed normally and every 10 real-life minutes by its "
                      "autosave", text)
        self.assertNotIn("never regains. See", text)
        groups = {(f.group, f.text.split(":")[0]) for f in facts}
        self.assertNotIn(("Food sources", "Food in storage"), groups)
        self.assertNotIn(("Tech points and effects", "Tech points"), groups)
        self.assertNotIn(("Mushrooms", "Mushrooms found in this village"), groups)
        self.assertNotIn(("Island events", "Island events seen in this village"), groups)
        golden = [f.text for f in facts if f.group == "Hidden villager stats" and f.text.startswith("The Golden Child")]
        self.assertEqual(len(golden), 1)              # the owner's line; the rest is under Golden Child
        self.assertFalse([f for f in facts if f.group == "Puzzles" and "solved" in f.text and not f.confirmed])

    def test_vv2_values(self) -> None:
        import vv_game_mechanics_vv2 as vv2
        data = bytearray(gzip.decompress((FIXTURES / "vv2-huttest-1.ldw.gz").read_bytes()))
        struct.pack_into("<i", data, vv2.SPEED + vv2.S, 3)
        struct.pack_into("<i", data, vv2.COCONUTS + vv2.S, 1234)
        text = text_of(self.page("vv2-huttest-1", data=bytes(data)))
        self.assertIn("Coconuts: 1,234; a trip brings 8 on Fast speed", text)
        self.assertIn("every 2 hours on Fast speed: coconuts +30", text)
        self.assertIn("a lit fire burns 10 hours of real-life time on Fast speed", text)
        totems = text_of(self.page("vv2-huttest-1", data=bytes(data), features=["vv2_totems_out_of_entries"]))
        self.assertIn("totems take no record and there is no limit", totems)
        self.assertIn("Normal game: at most 50 totems", text)

    def test_vv2_fish_below_zero(self) -> None:
        """The fish count is a signed dword the game keeps subtracting from with no floor once Sustainable Fishing
        is solved (0x463305, 0x425B00); the window says fishing has no limit then, not "they never grow back"."""
        import vv_game_mechanics_vv2 as vv2
        base = bytearray(gzip.decompress((FIXTURES / "vv2-huttest-1.ldw.gz").read_bytes()))
        struct.pack_into("<i", base, vv2.SPEED + vv2.S, 6)

        def render(fish: int, solved: int, farming: int) -> str:
            data = bytearray(base)
            struct.pack_into("<i", data, vv2.FISH + vv2.S, fish)
            data[vv2.SUSTAINABLE_FISHING + vv2.S] = solved
            struct.pack_into("<i", data, vv2.LEVELS + 8 * vv2.FARMING_LEVEL + vv2.S, farming)
            return text_of(self.page("vv2-huttest-1", data=bytes(data)))

        text = render(-1_162_256, 1, 3)
        self.assertIn("Fish: no limit, as Sustainable Fishing is solved; a trip brings 8 on Normal speed", text)
        self.assertIn("The game's own fish count is -1,162,256", text)
        self.assertNotIn("-1,162,256 (they never grow back)", text)
        self.assertIn("fishing adds without limit", text)
        self.assertIn("fishing trips per real-life hour", text)
        level1 = render(-40, 1, 1)
        self.assertIn("Fish: -40; Sustainable Fishing is solved, but at Farming level 1", level1)
        self.assertNotIn("fishing trips per real-life hour", level1)
        stock = render(700, 0, 3)
        self.assertIn("Fish: 700 (they never grow back); a trip brings 8 on Normal speed", stock)
        self.assertNotIn("fishing adds without limit", stock)
        self.assertNotIn("fishing trips per real-life hour", render(0, 0, 3))

    def test_vv4_and_vv5_values(self) -> None:
        import vv_game_mechanics_vv4 as vv4
        import vv_game_mechanics_vv5 as vv5
        data = bytearray(gzip.decompress((FIXTURES / "vv4-huttest-1.ldw.gz").read_bytes()))
        struct.pack_into("<i", data, vv4.BERRIES, 500)
        struct.pack_into("<i", data, vv4.LEVELS + 4 * vv4.FOOD_MASTERY, 1)
        text = text_of(self.page("vv4-huttest-1", data=bytes(data)))
        self.assertIn("Blackberries: 500 of 1,000; picking brings 5 food now", text)
        data = bytearray(gzip.decompress((FIXTURES / "vv5-huttest-1.ldw.gz").read_bytes()))
        struct.pack_into("<i", data, vv5.NONI, 640)
        struct.pack_into("<i", data, vv5.SPEED, 10)
        text = text_of(self.page("vv5-huttest-1", data=bytes(data)))
        self.assertIn("Noni bushes: 640 of 1,000; a pick gives 6 food now", text)
        self.assertIn("Noni: +2 every 10 minutes of real-life time on Slow speed", text)
        self.assertNotIn("Stinging Wasps", text)            # never happens in New Believers

    def test_vv5_divine_energy_cap_collectibles(self) -> None:
        """The cap's first-set term, pinned to the stock exe (0x4250A4): below 24 pieces 3 x the count, at 24 a flat
        90 -- so the page says 69 with 23 and +90 for all 24, never "+3 each" adding to 90."""
        exe = next((p for p in (ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe",
                                ROOT / "inputs" / "vv5-stock-copy" / "Virtual Villagers - New Believers.exe")
                    if p.is_file()), None)
        if exe is not None:
            code = exe.read_bytes()[151716:151716 + 16]          # file offset of 0x4250A4
            # cmp eax,24; jl +5; add esi,90; jmp +6; lea ecx,[eax+esi]; lea esi,[ecx+eax*2]
            self.assertEqual(code.hex(), "83f8187c0583c65aeb068d0c308d3441")
        for facts in (gm.general(5), self.page("vv5-huttest-1")):
            text = text_of(facts)
            self.assertIn("+3 for each piece of the first collectible set owned while it is incomplete (69 with 23 "
                          "pieces), then a flat +90 once all 24 are owned", text)
            self.assertNotIn("90 for all 24", text)

    def test_not_a_save(self) -> None:
        for name in ("vv1-huttest-1", "vv2-huttest-1", "vv4-huttest-1", "vv5-huttest-1"):
            with self.subTest(save=name):
                facts = self.page(name, data=b"ldwg" + bytes(40))
                self.assertEqual([f.group for f in facts if f.group != gm.SOURCES], ["Other"])
                self.assertIn("could not be read", facts[-1].text)

VV2_STOCK = ROOT / "inputs" / "vv2-stock-copy" / "Virtual Villagers - The Lost Children.exe"


class LostChildrenAudit(unittest.TestCase):
    """The Lost Children's Game Mechanics lines audited against the stock exe (2026-10-25)."""

    page = lambda self, name, **kw: EveryGame.page(self, name, **kw)  # noqa: E731

    def code(self, at: int, count: int = 3) -> list[str]:
        try:
            import pefile
            from capstone import CS_ARCH_X86, CS_MODE_32, Cs
        except ImportError:
            self.skipTest("pefile and capstone are needed")
        if not VV2_STOCK.is_file():
            self.skipTest("the stock Lost Children exe is not in inputs (tests/README: copy inputs\\)")
        pe = pefile.PE(str(VV2_STOCK), fast_load=True)
        image = pe.get_memory_mapped_image()
        start = at - pe.OPTIONAL_HEADER.ImageBase
        return [f"{i.mnemonic} {i.op_str}" for i in Cs(CS_ARCH_X86, CS_MODE_32).disasm(image[start:start + 48], at)][:count]

    def test_skill_gain_divisors(self) -> None:
        # (50 - skill) x 2 x magic: 0x66666667 >> 2 is / 10, 0x92492493 (+ x) >> 2 is / 7 (Building).
        for at in (0x44E2C1, 0x44E428, 0x44E52B, 0x44E7F7):
            self.assertEqual(self.code(at, 2), ["mov eax, 0x66666667", "imul ecx"])
        self.assertEqual(self.code(0x44E62E, 2), ["mov eax, 0x92492493", "imul ecx"])
        self.assertEqual(self.code(0x44E19B, 1), ["mov ebp, 0x42"])          # + 66 liking learning
        text = text_of(self.page("vv2-huttest-1"))
        self.assertIn("(100 - 2 x skill) / 10, rounded down (Building: / 7)", text)
        self.assertNotIn("passes at skill + 66%", text)

    def test_building_points_and_injuries(self) -> None:
        self.assertEqual(self.code(0x4629C8, 1), ["cmp eax, 0x58"])          # the Ancient Mosaic's Building 88
        self.assertEqual(self.code(0x462BD8, 1), ["mov cl, byte ptr [eax + 0x3046c]"])   # huts: the catch-up test
        text = text_of(self.page("vv2-huttest-1"))
        self.assertIn("the Ancient Mosaic +1, or +2 at Building 88; the broken starting hut and the Sewing Hut +1",
                      text)
        self.assertIn("the Ancient Mosaic, the broken starting hut and the Sewing Hut add the same as in live play",
                      text)
        for gone in ("adds half as much (1 instead of 2)", "33.9%, 50.5% or 67.1%", "0.52% / 0.28%",
                     "not individually worked out", "Ã"):
            self.assertNotIn(gone, text)

    def test_starvation_regain_is_any_odd_number(self) -> None:
        self.assertEqual(self.code(0x43BBB3, 2), ["mov ecx, 6", "idiv ecx"])
        text = text_of(self.page("vv2-huttest-1"))
        self.assertIn("whose hidden number is odd regains the 1 health", text)
        self.assertNotIn("not a multiple of 3", text)

    def test_collections_and_the_gong(self) -> None:
        self.assertEqual(self.code(0x426130, 1), ["mov bl, byte ptr [ecx + eax + 0x2e720]"])
        self.assertEqual(self.code(0x44B378, 3), ["cmp edi, 0x14", "jne 0x44b382", "mov edi, 0x19"])
        self.assertEqual(self.code(0x42FE12, 1), ["mov al, byte ptr [ebx + 0x2e7f0]"])
        self.assertEqual(self.code(0x44E8C1, 1), ["cmp byte ptr [eax + 0x2e910], bl"])
        data = bytearray(gzip.decompress((FIXTURES / "vv2-huttest-1.ldw.gz").read_bytes()))
        import vv_game_mechanics_vv2 as vv2
        data[vv2.COLLECTION_FLAGS + 4:vv2.COLLECTION_FLAGS + 4 + 48] = bytes([1] * 12 + [1, 0] * 6 + [0] * 24)
        data[vv2.GONG_WHOLE + 4] = 0
        text = text_of(self.page("vv2-huttest-1", data=bytes(data)))
        self.assertIn("Collectibles found: 18 of the 48 pieces (Butterflies 12 of 12, Shells 6 of 12, Beetles 0 of 12, "
                      "Pebbles 0 of 12); 1 of the 4 collections complete.", text)
        self.assertIn("The Gong of Wonder is not rebuilt yet", text)
        self.assertNotIn("has not been traced", text)

    def test_baby_skill_and_the_fire(self) -> None:
        self.assertEqual(self.code(0x44F846, 2), ["push 3", "call 0x4031a0"])
        self.assertEqual(self.code(0x46252F, 2), ["call 0x403200", "add eax, 0x8ca0"])
        text = text_of(self.page("vv2-huttest-1"))
        self.assertIn("4 to 5, 5 to 8 or 7 to 11 at Culture level 1, 2 or 3", text)
        self.assertIn("fuel does not light a cold pit", text)

    def test_elder_rules_once_on_each_page(self) -> None:
        # The general page has no Village counts, so the rules stand under Tech points; a save's page has them
        # once, under Village counts (the Codex review of #640).
        general = text_of(gm.general(2, EPOCH))
        self.assertIn("has 3 of the 5 skills at 88 or more becomes one and gets a totem", general)
        self.assertIn("Normal game: at most 50 totems", general)
        self.assertNotIn("see Village counts.", general)
        text = text_of(self.page("vv2-huttest-1"))
        self.assertEqual(text.count("has 3 of the 5 skills at 88 or more becomes one and gets a totem"), 1)
        self.assertEqual(text.count("Normal game: at most 50 totems"), 1)
        self.assertIn("Esteemed Elders and their totems: see Village counts.", text)


VV4_STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Tree of Life.exe"


class TreeOfLifeAudit(unittest.TestCase):
    """The Tree of Life's Game Mechanics lines audited against the stock exe (2026-10-25)."""

    page = lambda self, name: EveryGame.page(self, name)  # noqa: E731

    def code(self, at: int, count: int = 3) -> list[str]:
        try:
            import pefile
            from capstone import CS_ARCH_X86, CS_MODE_32, Cs
        except ImportError:
            self.skipTest("pefile and capstone are needed")
        if not VV4_STOCK.is_file():
            self.skipTest("the stock Tree of Life exe is not in research/stock-executables")
        pe = pefile.PE(str(VV4_STOCK), fast_load=True)
        image = pe.get_memory_mapped_image()
        start = at - pe.OPTIONAL_HEADER.ImageBase
        return [f"{i.mnemonic} {i.op_str}" for i in Cs(CS_ARCH_X86, CS_MODE_32).disasm(image[start:start + 32], at)][:count]

    def test_skill_gain_divisors(self) -> None:
        # (70 - skill) x magic >> 32 >> k: 0x38E38E39 >> 2 is ÷ 18, 0x66666667 >> 2 ÷ 10, 0x2AAAAAAB >> 1 ÷ 12.
        for at, magic, shift, divisor in ((0x462CB7, 0x38E38E39, 2, 18), (0x4631C7, 0x38E38E39, 2, 18),
                                          (0x4633F0, 0x38E38E39, 2, 18), (0x462EC2, 0x66666667, 2, 10),
                                          (0x46304F, 0x2AAAAAAB, 1, 12)):
            with self.subTest(at=hex(at)):
                self.assertEqual(self.code(at), [f"mov eax, {magic:#x}", "imul ecx", f"sar edx, {shift}"])
                for skill in range(0, 71):
                    self.assertEqual(((70 - skill) * magic >> 32) >> shift, (70 - skill) // divisor)
        text = text_of(self.page("vv4-huttest-1"))
        self.assertIn("(70 - skill) ÷ 18 for Farming, Research and Building, ÷ 10 for Parenting and ÷ 12 for Healing",
                      text)
        self.assertNotIn("(70 - skill) ÷ 9", text)

    def test_food_amounts_and_the_room(self) -> None:
        self.assertEqual(self.code(0x464A3F, 2), ["push 0x37", "mov ecx, 0x4d6dd0"])      # a crab found: 55
        self.assertEqual(self.code(0x436F0E, 2), ["push 0x23", "mov ecx, 0x4d6dd0"])      # the Mossy Rocks: 35
        self.assertEqual(self.code(0x4683AA, 3), ["cmp esi, 0x14", "jne 0x4683b4", "mov esi, 0x19"])
        self.assertEqual(self.code(0x464E63, 2), ["push 0x52", "mov ecx, 0x4cc838"])      # Lab Equipment pieces
        self.assertEqual(self.code(0x4686DC, 1), ["mov byte ptr [esi + 0xc], al"])         # Easy cures
        text = text_of(self.page("vv4-huttest-1"))
        for words in ("A crab a villager finds (\"This villager found a crab!\") brings 55.",
                      "A crab caught at the Mossy Rocks (\"Catching a crab\") brings 35.",
                      "5 for each complete collection, 25 with all four",
                      "0 to (Lab Equipment pieces found - 1) more",
                      "Sickness never ends by itself, except on Easy: there a sick villager is cured on 25% of age units."):
            self.assertIn(words, text)
        for gone in ("Village & Tree Malaise", "Some effect", "not individually worked out", "the soapy-stew reaction"):
            self.assertNotIn(gone, text)


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
# Only The Secret City has a save folder; the other games show their general rules.
vv_save_backup.find_save_folders = lambda title, documents: [folder] if "Secret City" in title else []
try:
    root = tkinter.Tk()
except tkinter.TclError as exc:
    print(exc, file=sys.stderr)
    sys.exit(3)
root.withdraw()
class Build:
    def __init__(self, title):
        self.title = title
titles = ["Virtual Villagers - A New Home", "Virtual Villagers - The Lost Children",
          "Virtual Villagers - The Secret City", "Virtual Villagers - The Tree of Life",
          "Virtual Villagers - New Believers"]
root.builds = [Build(t) for t in titles]
root._game_folders_for = lambda save_folder: [game_folder]
window = w.open_game_mechanics(root, root.builds[2])
window.update()
tabs, notebook = window.mechanics_tabs, window.mechanics_notebook
print(window.resizable() == (True, True), len(tabs), notebook.index("end"))
top, intro, buttons, note = window.mechanics_parts
intro.configure(wraplength=w.MIN_WIDTH - 40)
note.configure(wraplength=w.MIN_WIDTH - 40)
results = []
for number in sorted(tabs):
    notebook.select(sorted(tabs).index(number))
    window.update()
    tab = tabs[number]
    page = tab["page"]
    # At its smallest: the intro, the tab header, the pickers, the links and the buttons must leave the page
    # at least 80 pixels (about four lines) -- nothing above or below it cut off.
    window.update_idletasks()
    fixed = (top.winfo_reqheight() + 30 + tab["pickers"].winfo_reqheight() + tab["links"].winfo_reqheight()
             + tab["status"].winfo_reqheight() + buttons.winfo_reqheight() + 24 + 40)
    text = page.get("1.0", "end")
    tab["jump"](tab["groups"][-1])
    window.update()
    results.append((number, fixed + 80 <= w.MIN_HEIGHT, bool(page.cget("yscrollcommand")), len(tab["groups"]),
                    page.yview()[0] > 0.0, "No save was found" in text, len(page.tag_ranges("unconfirmed")) > 0,
                    len(page.tag_ranges("bullet")) > 0, page.tag_cget("bullet", "lmargin2") not in ("", "0")))
    if number == 3:
        secret = text
for row in results:
    print(*row)
print(ascii(secret))
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
        out = done.stdout.strip().splitlines()
        self.assertEqual(out[0], "True 5 5")
        rows = [line.split() for line in out[1:6]]
        for number, fits, bar, groups, jumped, general, labelled, bullets, hanging in rows:
            with self.subTest(game=number):
                self.assertEqual((fits, bar, jumped, labelled), ("True", "True", "True", "True"))
                # Bullets, wrapped lines continuing under the bullet's text (the owner, 2026-10-23).
                self.assertEqual((bullets, hanging), ("True", "True"))
                self.assertGreaterEqual(int(groups), 6)
                self.assertEqual(general, "False" if number == "3" else "True")
        text = out[6]
        self.assertIn(ascii(gm.BULLET + "Tree 1: Mango")[1:-1], text)
        self.assertIn(ascii(gm.SUB_BULLET + "640 of 1000 fruit")[1:-1], text)
        self.assertIn("Planted when the village was 1 minute 40 seconds old", text)
        self.assertIn("is in the game", text)


class Autosave(unittest.TestCase):
    """The owner, 2026-10-25: "Games autosave".  Every game's page gives the same autosave line once, under Chance
    and timers, and each stock exe has the 600-second check gm.autosave_line describes."""
    # game: (exe, the check, the save writer, the field the next autosave time is kept in)
    CHECKS = {1: ("vv1-stock-copy/Virtual Villagers - A New Home.exe", 0x41BFC0, 0x41BF70, 0xADEC),
              2: ("vv2-stock-copy/Virtual Villagers - The Lost Children.exe", 0x424C40, 0x424C00, 0x305AC),
              3: ("vv3-stock-copy/Virtual Villagers - The Secret City.exe", 0x427DD0, 0x427D90, 0x12FD0),
              4: ("vv4-stock-copy/Virtual Villagers - The Tree of Life.exe", 0x41F1A0, 0x41F160, 0x171C0),
              5: ("vv5-stock-copy/Virtual Villagers - New Believers.exe", 0x424660, 0x424620, 0x17E34)}

    def test_every_game_gives_it_once(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                facts = gm.general(game, EPOCH)
                lines = [f for f in facts if f.text.startswith("Autosave:")]
                self.assertEqual(len(lines), 1)
                self.assertEqual(lines[0].group, "Chance and timers")
                self.assertTrue(lines[0].confirmed)
                self.assertIn("once 10 real-life minutes have passed since the program started or since its last "
                              "autosave", lines[0].text)
                self.assertIn("count while the game is paused too", lines[0].text)

    def test_the_stock_exes_check(self) -> None:
        for game, (name, check, writer, field) in self.CHECKS.items():
            exe = ROOT / "inputs" / name
            if not exe.is_file():
                self.skipTest("the stock executables are not here")
            with self.subTest(game=game):
                import pefile
                pe = pefile.PE(str(exe), fast_load=True)
                code = pe.get_data(check - pe.OPTIONAL_HEADER.ImageBase, 0x2C)
                self.assertEqual(code[3], 0xE8)                                 # call time()
                self.assertEqual(code[8:10], b"\x39\x86")                       # cmp [esi + field], eax
                self.assertEqual(struct.unpack_from("<I", code, 10)[0], field)
                at = code.index(b"\x05\x58\x02\x00\x00")                        # add eax, 600
                self.assertLess(at, 0x20)
                jump = code.index(b"\xE9" if game <= 3 else b"\xE8", at)        # on to the save writer
                self.assertEqual(check + jump + 5 + struct.unpack_from("<i", code, jump + 1)[0], writer)


if __name__ == "__main__":
    unittest.main()
