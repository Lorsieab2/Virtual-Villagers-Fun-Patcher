"""The patcher's offline renames carry New Believers' Masks Worn file (Heathens Keep Their Masks When Converted;
Codex, #843): a villager renamed by Last Names, Number Duplicate Names or any rename the patcher makes keeps the
mask they wore as a Heathen, exactly as the companion follows a rename in play (native/vvfp_heathens_keep_masks,
the Head Looks' store: name, sex and parents).

The save folder is made by hand (tests/test_lost_titles.py's save), with a Masks Worn file naming two villagers.
"""
from __future__ import annotations

import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_last_names as ln  # noqa: E402
from test_lost_titles import VILLAGE, person, save_for  # noqa: E402

COUNT = 150


def worn_file(roster: list[int], ids: list[int], masks: list[int]) -> bytes:
    pad = lambda xs, n: list(xs) + [0] * (n - len(xs))  # noqa: E731
    return (b"VKM1" + struct.pack("<II", 5, COUNT) + struct.pack(f"<{COUNT}I", *pad(roster, COUNT))
            + struct.pack(f"<{COUNT}I", *pad(ids, COUNT)) + bytes(pad(masks, COUNT)))


class OfflineRenamesCarryTheMasksWorn(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        named = mock.patch("vv_log_additions.current_villages", return_value={VILLAGE})
        named.start()
        self.addCleanup(named.stop)
        self.folder = Path(tmp.name)
        self.save = ln.save_path(self.folder, 5, 1)
        self.save.write_bytes(save_for(5, [person("Nobu", 5, 5, male=True), person("Kai", 4, 4, male=True)]))
        data = self.save.read_bytes()
        f = ln.FIELDS[5]
        self.at = ln._entries(5, data)
        self.ids = [ln._worn_identity(data, p, f) for p in self.at]
        self.path = ln._data_file(self.folder, "Heathens Keep Masks", "Masks Worn - Save 1.dat")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(worn_file(self.ids, [self.ids[0], 0], [4, 0]))   # Nobu wore purple

    def test_the_identity_is_the_companions(self):
        """The companion's hl_identity, worked by hand for "Nobu", male (sex 0), no parents."""
        def fnv(h, b):
            for x in b:
                h = ((h ^ x) * 16777619) & 0xFFFFFFFF
            return h
        stable = fnv(fnv(fnv(2166136261, bytes(4)), b"\xfe"), b"\xfd")
        expected = ((fnv(fnv(2166136261, b"Nobu"), b"\xff") ^ stable) * 16777619) & 0xFFFFFFFF
        self.assertEqual(self.ids[0], expected)

    def test_a_rename_carries_the_mask_worn(self):
        plan = ln.plan_renames(self.folder, 5, 1, {("Nobu", 5, 5): "Nobu Akana"})
        changed = [c for c in plan.changes if c.path == self.path]
        self.assertEqual(len(changed), 1, "the Masks Worn file is in the plan")
        after = next(c.updated for c in plan.changes if c.path == self.save)
        new = ln._worn_identity(bytes(after), self.at[0], ln.FIELDS[5])
        data = changed[0].updated
        roster = struct.unpack_from(f"<{COUNT}I", data, 12)
        ids = struct.unpack_from(f"<{COUNT}I", data, 12 + 4 * COUNT)
        self.assertEqual((roster[0], ids[0], data[12 + 8 * COUNT]), (new, new, 4), "Nobu keeps his purple")
        self.assertEqual(roster[1], self.ids[1], "Kai, not renamed, is untouched")
        self.assertEqual(data[12 + 8 * COUNT:], self.path.read_bytes()[12 + 8 * COUNT:], "the masks as they were")

    def test_nobody_renamed_changes_nothing(self):
        plan = ln.plan_renames(self.folder, 5, 1, {("Kai", 4, 4): "Kai Akana"})
        changed = [c for c in plan.changes if c.path == self.path]
        self.assertEqual(len(changed), 1)
        roster = struct.unpack_from(f"<{COUNT}I", changed[0].updated, 12)
        self.assertEqual(roster[0], self.ids[0], "Nobu's entry is as it was")


def store_file(magic: bytes, game: int, count: int, roster: list[int], ids: list[int] | None, values: list[int]) -> bytes:
    pad = lambda xs, n: list(xs) + [0] * (n - len(xs))  # noqa: E731
    body = struct.pack(f"<{count}I", *pad(roster, count))
    if ids is not None:
        body += struct.pack(f"<{count}I", *pad(ids, count))
    return magic + struct.pack("<II", game, count) + body + bytes(pad(values, count))


class OfflineRenamesCarryHeadLooksAndGenderPresentation(unittest.TestCase):
    """The Head Looks' and Gender Presentation's files (the same store, each its own magic, all five games) are
    carried the same way (Codex, #843: fix along the way)."""

    def village(self, game: int):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        named = mock.patch("vv_log_additions.current_villages", return_value={VILLAGE})
        named.start()
        self.addCleanup(named.stop)
        folder = Path(tmp.name)
        save = ln.save_path(folder, game, 1)
        save.write_bytes(save_for(game, [person("Nobu", 5, 5, male=True), person("Kai", 4, 4, male=True)]))
        data = save.read_bytes()
        at = ln._entries(game, data)
        ids = [ln._store_identity(game, data, p, ln.FIELDS[game]) for p in at]
        return folder, save, at, ids

    def carried(self, game: int, kind: str, name: str, magic: bytes, first_layout: bool = False) -> None:
        folder, save, at, ids = self.village(game)
        count = 256 if game in (1, 2) else 150
        path = ln._data_file(folder, kind, f"{name} - Save 1.dat")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(store_file(magic, game, count, ids, None if first_layout else [ids[0], 0], [2, 0]))
        plan = ln.plan_renames(folder, game, 1, {("Nobu", 5, 5): "Nobu Akana"})
        changed = [c for c in plan.changes if c.path == path]
        self.assertEqual(len(changed), 1, f"{name} is in the plan")
        after = next(c.updated for c in plan.changes if c.path == save)
        new = ln._store_identity(game, after, at[0], ln.FIELDS[game])
        self.assertNotEqual(new, ids[0])
        roster = struct.unpack_from(f"<{count}I", changed[0].updated, 12)
        self.assertEqual((roster[0], roster[1]), (new, ids[1]), "Nobu's carried, Kai's as it was")
        if not first_layout:
            self.assertEqual(struct.unpack_from("<I", changed[0].updated, 12 + 4 * count)[0], new)
        self.assertEqual(changed[0].updated[-count:], path.read_bytes()[-count:], "every value as it was")

    def test_head_looks_in_every_game(self):
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                self.carried(game, "Head Looks", "Head Looks", b"VHL2")

    def test_head_looks_first_layout(self):
        self.carried(4, "Head Looks", "Head Looks", b"VHL1", first_layout=True)

    def test_gender_presentation_in_every_game(self):
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                self.carried(game, "Gender Presentation", "Gender Presentation", b"VGP1")


if __name__ == "__main__":
    unittest.main()
