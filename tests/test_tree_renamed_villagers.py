"""Family Tree Maker: a villager the player renamed (the owner, 2026-10-13: Lupa Tangaroa is now Coral
Tangaroa, Tamil Makawee is now Mahalo Makawee).  A logged name no living villager has, with exactly one living
villager's sex, head, body and likes (that villager no younger than the record), is ASKED about -- "Keep
<current> or <old>?" -- never merged unasked; the answer is kept in the tree's edits; "current" makes them one
person under the current name with the old name in the notes.  The same in all five games, each reading its own
save fields (vv_last_names.FIELDS) and like words (vv_lost_titles.PREFERENCES)."""
import json
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
import vv_genealogy as gen  # noqa: E402
import vv_last_names as ln  # noqa: E402
import vv_log_tools as tools  # noqa: E402
import vv_lost_titles as lost  # noqa: E402
import vv_villager_info as info  # noqa: E402

GAMES = (1, 2, 3, 4, 5)
SPACING = 0x800


def words_to_ids(game: int, words: str) -> list[int]:
    table = lost.PREFERENCES[game]
    return [table.index(w.strip()) for w in words.split(",")]


def build_save(game: int, people: list) -> tuple[bytes, list[int]]:
    """A save holding `people` = (name, sex "Male"/"Female", head, body, likes words, age), written at the
    fields game `game` keeps them (vv_last_names.FIELDS, the checker's age offset)."""
    f = ln.FIELDS[game]
    age_at = -0x28 if game == 1 else tools.load_checker().LAYOUTS[game].age
    data = bytearray(0x100 + SPACING * (len(people) + 1))
    offsets = []
    for k, (name, sex, head, body, likes, age) in enumerate(people):
        at = 0x100 + SPACING * k + 0x40
        offsets.append(at)
        data[at:at + len(name)] = name.encode("latin-1")
        struct.pack_into("<i", data, at + f.head, head)
        struct.pack_into("<i", data, at + f.body, body)
        struct.pack_into("<i", data, at + f.sex, f.male if sex == "Male" else f.male ^ 3)
        struct.pack_into("<i", data, at + f.family, 1)
        struct.pack_into("<i", data, at + age_at, age)
        ids = words_to_ids(game, likes)
        ids += [-1] * (f.slots - len(ids))
        struct.pack_into(f"<{f.slots}i", data, at + f.likes, *ids)
    return bytes(data), offsets


def block(name, head, body, likes, sex="Female", age="290", heading="Villager 1", date="2026-10-13 21:31"):
    values = {"Likes": likes, "Sex": sex, "Age": age, "Name": name}
    return SimpleNamespace(identity=(name, head, body), heading=heading, date=date, lines=[], path=Path("x"),
                           value=lambda key: values.get(key))


class Village(unittest.TestCase):
    """load_village over a made-up save and made-up History records, once per game."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def load(self, game, living, logged, **kw):
        data, offsets = build_save(game, living)
        ln.save_path(self.folder, game, 1).write_bytes(data)
        with mock.patch("vv_last_names._entries", return_value=offsets), \
                mock.patch("vv_cut_names.find_cut", return_value=([], [])), \
                mock.patch("vv_log_additions.person_blocks", return_value=logged):
            return gen.load_village(self.folder, game, 1, **kw)

    def names(self, v):
        return sorted(p.name for p in v.known())

    COR = ("Coral Tangaroa", "Female", 24, 28, "running", 300)
    MAH = ("Mahalo Makawee", "Male", 23, 16, "ants, crowds", 400)

    def test_a_renamed_villager_is_asked_about_and_not_merged(self):
        for game in GAMES:
            with self.subTest(game=game):
                v = self.load(game, [self.COR, self.MAH],
                              [block("Lupa Tangaroa", 24, 28, "running"),
                               block("Tamil Makawee", 23, 16, "ants, crowds", sex="Male", age="380")])
                self.assertEqual(self.names(v), ["Coral Tangaroa", "Lupa Tangaroa", "Mahalo Makawee", "Tamil Makawee"])
                self.assertEqual(sorted((q.old, q.current) for q in v.rename_questions),
                                 [("Lupa Tangaroa", "Coral Tangaroa"), ("Tamil Makawee", "Mahalo Makawee")])

    def test_an_answer_merges_as_chosen(self):
        for game in GAMES:
            with self.subTest(game=game):
                logged = [block("Lupa Tangaroa", 24, 28, "running"),
                          block("Tamil Makawee", 23, 16, "ants, crowds", sex="Male", age="380")]
                v = self.load(game, [self.COR, self.MAH], logged, rename_answers={
                    gen.rename_key("Lupa Tangaroa", 24, 28): "current", gen.rename_key("Tamil Makawee", 23, 16): "old"})
                self.assertEqual(self.names(v), ["Coral Tangaroa", "Mahalo Makawee", "Tamil Makawee"])
                self.assertEqual(v.rename_questions, [])
                coral = next(p for p in v.known() if p.name == "Coral Tangaroa")
                self.assertEqual(coral.former, ["Lupa Tangaroa"])
                self.assertTrue(coral.alive)
                shown = [text for line in info.info_lines(v, ft.Edits(), coral.id) for text, _s, _t in line]
                self.assertIn("formerly Lupa Tangaroa", shown)

    def test_unrelated_names_are_never_asked(self):
        for game in GAMES:
            with self.subTest(game=game):
                v = self.load(game, [self.COR], [
                    block("Coral Tangara", 25, 28, "running"),              # a similar name, other head
                    block("Lupa Tangaroa", 24, 28, "ants"),                  # other likes
                    block("Lupa Tangaroa", 24, 28, "running", sex="Male"),   # other sex
                    block("Lupa Tangaroa", 24, 29, "running"),               # other body
                    block("Lupa Tangaroa", 24, 28, "running", age="900")])   # younger than the record
                self.assertEqual(v.rename_questions, [])
                self.assertEqual(sorted(set(self.names(v))), ["Coral Tangara", "Coral Tangaroa", "Lupa Tangaroa"])
                self.assertEqual([p.former for p in v.known() if p.former], [])

    def test_a_dead_villager_is_never_asked(self):
        for game in GAMES:
            with self.subTest(game=game):
                v = self.load(game, [self.COR], [block("Lupa Tangaroa", 24, 28, "running"),
                                                 block("Lupa Tangaroa", 24, 28, "running", heading="Death")])
                self.assertEqual(v.rename_questions, [])

    def test_two_candidates_for_one_look_are_not_merged(self):
        twin = ("Coral Tangaro", "Female", 24, 28, "running", 310)
        for game in GAMES:
            with self.subTest(game=game):
                v = self.load(game, [self.COR, twin], [block("Lupa Tangaroa", 24, 28, "running")],
                              rename_answers={gen.rename_key("Lupa Tangaroa", 24, 28): "current"})
                self.assertEqual(v.rename_questions, [])
                self.assertIn("Lupa Tangaroa", self.names(v))
                self.assertTrue(any("Lupa Tangaroa" in n and "not joined" in n for n in v.notes))

    def test_two_records_for_one_villager_are_not_merged(self):
        for game in GAMES:
            with self.subTest(game=game):
                v = self.load(game, [self.COR], [block("Lupa Tangaroa", 24, 28, "running"),
                                                 block("Lapu Tangaroa", 24, 28, "running")])
                self.assertEqual(v.rename_questions, [])
                self.assertEqual(self.names(v), ["Coral Tangaroa", "Lapu Tangaroa", "Lupa Tangaroa"])


def arrived(name, head, body, how, sex="Male", n=1):
    values = {"Name": name, "Sex": sex, "How": how, "Likes": "(none)", "Dislikes": "(none)"}
    return SimpleNamespace(identity=(name, head, body), heading=f"Arrived {n}", date=None, lines=[], path=Path("x"),
                           value=lambda key: values.get(key))


class LoggedRename(unittest.TestCase):
    """The owner's VV2 save (2026-10-18): the founder Tamil Makawee (Arrived, How: Founder) was renamed Mahalo
    Makawee ("Name changed" record), the arrival backfill then wrote "Arrived / Mahalo Makawee / How: unknown",
    and a son was later named Tamil Makawee -- so the rename was never asked (the old name is a living
    villager's) and the last-names window labelled the founder "-- arrived".  The logged rename makes them one
    person under the new name, still a founder."""

    MAH = ("Mahalo Makawee", "Male", 23, 16, "ants", 400)
    SON = ("Tamil Makawee", "Male", 24, 4, "ants", 60)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def write_rename(self, game, old="Tamil Makawee", new="Mahalo Makawee", head=23, body=16):
        logs = self.folder / "Virtual Villagers Fun Patcher Logs" / "Save 1" / "Births and Conceptions"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / f"Virtual Villagers {game} Births and Conceptions Log 1.txt").write_bytes(
            (f"Village: Kalahuna (Save 1)\r\nName changed\r\n  Name: {new}\r\n  Old name: {old}\r\n  Age: 278\r\n"
             f"  Head: {head}\r\n  Body: {body}\r\n  Likes:\r\n  Dislikes:\r\n\r\n").encode("latin-1"))

    def run_both(self, game, logged):
        data, offsets = build_save(game, [self.MAH, self.SON])
        ln.save_path(self.folder, game, 1).write_bytes(data)
        with mock.patch("vv_last_names._entries", return_value=offsets), \
                mock.patch("vv_cut_names.find_cut", return_value=([], [])), \
                mock.patch("vv_log_additions.current_villages", return_value=None), \
                mock.patch("vv_log_additions.person_blocks", return_value=logged):
            return gen.load_village(self.folder, game, 1, full_names=False), ln.everyone(self.folder, game, 1)

    def test_a_renamed_founder_is_one_person_and_no_arrival(self):
        logged = [arrived("Tamil Makawee", 23, 16, "Founder", n=4),
                  arrived("Mahalo Makawee", 23, 16, "unknown", n=9)]
        for game in GAMES:
            with self.subTest(game=game):
                self.write_rename(game)
                village, (people, _parents) = self.run_both(game, logged)
                mahalo = [p for p in village.known() if p.key == ("Mahalo Makawee", 23, 16)]
                self.assertEqual(len(mahalo), 1)
                self.assertEqual(mahalo[0].how, "Founder")
                self.assertEqual(mahalo[0].former, ["Tamil Makawee"])
                self.assertNotIn(("Tamil Makawee", 23, 16), {p.key for p in village.known()})
                self.assertIn(("Tamil Makawee", 24, 4), {p.key for p in village.known()})   # the son stays
                self.assertEqual({v.name: v.arrived for v in people},
                                 {"Mahalo Makawee": False, "Tamil Makawee": False})

    def test_without_the_rename_record_the_backfill_is_still_an_arrival(self):
        logged = [arrived("Tamil Makawee", 23, 16, "Founder", n=4),
                  arrived("Mahalo Makawee", 23, 16, "unknown", n=9)]
        for game in GAMES:
            with self.subTest(game=game):
                _village, (people, _parents) = self.run_both(game, logged)
                self.assertTrue(next(v for v in people if v.name == "Mahalo Makawee").arrived)

    def test_a_dead_old_name_is_never_joined(self):
        logged = [arrived("Tamil Makawee", 23, 16, "Founder", n=4),
                  SimpleNamespace(identity=("Tamil Makawee", 23, 16), heading="Death 1", date=None, lines=[],
                                  path=Path("x"), value=lambda key: {"Name": "Tamil Makawee"}.get(key)),
                  arrived("Mahalo Makawee", 23, 16, "unknown", n=9)]
        for game in GAMES:
            with self.subTest(game=game):
                self.write_rename(game)
                village, _everyone = self.run_both(game, logged)
                self.assertIn(("Tamil Makawee", 23, 16), {p.key for p in village.known()})


class Remembered(unittest.TestCase):
    def test_the_answer_is_kept_in_the_edits_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "edits.json"
            e = ft.Edits()
            e.renames[gen.rename_key("Lupa Tangaroa", 24, 28)] = "current"
            e.save(path)
            again = ft.Edits.load(path)
            self.assertEqual(again.renames, {"Lupa Tangaroa|24|28": "current"})
            data = json.loads(path.read_text(encoding="utf-8"))
            data["renames"]["x|1|2"] = "maybe"
            self.assertEqual(ft.Edits.from_data(data).renames, {"Lupa Tangaroa|24|28": "current"})

    def test_the_window_asks_and_remembers(self):
        import vv_genealogy_window as gw
        q = gen.RenameQuestion("Lupa Tangaroa", "Coral Tangaroa", 24, 28, 1, 2)
        village = SimpleNamespace(rename_questions=[q])
        edits = ft.Edits()
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(gw.messagebox, "askyesnocancel", return_value=True) as ask, \
                mock.patch("vv_genealogy.load_village", return_value="reloaded") as load:
            got = gw.ask_renames(None, Path(tmp), 2, 1, village, edits)
            self.assertEqual(got, "reloaded")
            self.assertIn("Keep Coral Tangaroa or Lupa Tangaroa?", ask.call_args[0][1])
            self.assertEqual(edits.renames, {q.key: "current"})
            self.assertEqual(load.call_args.kwargs["rename_answers"], {q.key: "current"})
            self.assertEqual(ft.Edits.load(ft.Edits.path(Path(tmp), 2, 1)).renames, {q.key: "current"})
        with mock.patch.object(gw.messagebox, "askyesnocancel", return_value=None):
            later = ft.Edits()
            self.assertIs(gw.ask_renames(None, Path("."), 2, 1, village, later), village)
            self.assertEqual(later.renames, {})        # Cancel: asked again next time


class OwnerCopyTests(unittest.TestCase):
    """The owner's VV2 tribe (Kalahuna Tribe 2, Save 1), a copy of its folder (REAL_VV2 environment: the path
    of the copy, saves and logs; never the owner's own folder)."""

    def test_the_owners_pairs_are_asked_then_one_person_each(self):
        import os
        copy = os.environ.get("VVFP_OWNER_VV2_COPY")
        if not copy or not Path(copy).is_dir():
            self.skipTest("VVFP_OWNER_VV2_COPY names no copy of the owner's VV2 folder")
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp) / "vv2"
            shutil.copytree(copy, work, ignore=shutil.ignore_patterns("Backups"))
            v = gen.load_village(work, 2, 1)
            asked = sorted((q.old, q.current) for q in v.rename_questions)
            self.assertEqual(asked, [("Lupa Tangaroa", "Coral Tangaroa"), ("Tamil Makawee", "Mahalo Makawee")])
            self.assertIn("Lupa Tangaroa", {p.name for p in v.known()})            # unanswered: as it showed them
            answers = {q.key: "current" for q in v.rename_questions}
            v = gen.load_village(work, 2, 1, rename_answers=answers)
            names = {p.name for p in v.known()}
            self.assertNotIn("Lupa Tangaroa", names)
            self.assertNotIn("Tamil Makawee", names)
            formers = {p.name: p.former for p in v.known() if p.former}
            self.assertEqual(formers, {"Coral Tangaroa": ["Lupa Tangaroa"], "Mahalo Makawee": ["Tamil Makawee"]})


if __name__ == "__main__":
    unittest.main()
