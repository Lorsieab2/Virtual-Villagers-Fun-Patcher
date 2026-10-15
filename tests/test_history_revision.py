"""Repair Saves & Logs: removing a restarted tribe's villagers from the history (src/vv_history_revision.py),
all five games (the owner, v1.35.73).

The owner: "please implement this history revision in Repair logs for .73, with player confirmation, to
account for the player starting the game over with the same tribe name. yes, I confirm 2" -- remove ONLY
the villagers PROVEN gone and list the rest.  "several villagers are still present but renamed": on the
owner's The Lost Children copy the History snapshots list Lupa Tangaroa (head 24, body 28, likes running),
who is Coral Tangaroa in the save now, and Tamil Makawee (head 23, body 16), who is Mahalo Makawee -- both
must be kept and listed as renamed, never removed.

Every village here is built from the repository's own fixture saves (tests/test_reconcile.py Village).
"""
from __future__ import annotations

import hashlib
import re
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_history_revision as hr  # noqa: E402
import vv_log_tools as tools  # noqa: E402
from test_reconcile import FakeProcesses, Village, aged, fixture, words  # noqa: E402

GAMES = (1, 2, 3, 4, 5)
OLD = "2026-01-01 10:00:00"       # the tribe started over came first
MID = "2026-01-15 10:00:00"       # the tribe being played: its first snapshot
NOW = "2026-02-01 10:00:00"       # ...and its latest


def entry(k: int, name: str, sex: str, head: int, body: int, age: int, likes=(), dislikes=()) -> str:
    return (f"Villager {k}\n  Name: {name}\n  Age: {age}\n  Sex: {sex}\n  Head: {head}\n  Body: {body}\n"
            f"  Likes: {words(likes)}\n  Dislikes: {words(dislikes)}\n")


class Scene:
    """One game's village: the fixture save (two of its villagers renamed and relooked to the owner's Coral
    Tangaroa and Mahalo Makawee), a History file with a restarted tribe's snapshot before this tribe's own,
    and Births, Deaths and Island Events logs."""

    def __init__(self, root: Path, game: int):
        v = Village(root, game, fixture(f"vv{game}-huttest-1"))
        data = v.save_path(1).read_bytes()
        data = v.relooked(v.renamed(data, 0, "Coral Tangaroa"), 0, 24, 28)
        data = v.relooked(v.renamed(data, 1, "Mahalo Makawee"), 1, 23, 16)
        v.write_save(1, data)
        self.v, self.game = v, game
        self.living = v.people(data)
        coral, mahalo = self.living[0], self.living[1]
        self.coral, self.mahalo = coral, mahalo
        self.other = self.living[2]
        hdr = v.header
        # The tribe started over: one villager proven gone, and one sharing a living villager's name with
        # other looks.
        old = [entry(1, "Gonea Testa", "Female", 99, 98, 120),
               entry(2, self.other.name, self.other.sex, 97, 96, 100)]
        # This tribe's first snapshot (the owner's 21:31:58): the owner's two renamed villagers under their
        # old names, beside everyone else living.
        first = [entry(1, "Lupa Tangaroa", coral.sex, 24, 28, max(0, (coral.age or 0) - 6), coral.likes,
                       coral.dislikes),
                 entry(2, "Tamil Makawee", mahalo.sex, 23, 16, max(0, (mahalo.age or 0) - 6), mahalo.likes,
                       mahalo.dislikes)]
        first += [entry(k, s.name, s.sex, s.head, s.body, s.age or 0, s.likes, s.dislikes)
                  for k, s in enumerate(self.living[2:], 3)]
        # This tribe now: everyone living, and one of its own dead (never in the save now, never removed).
        now = [entry(k, s.name, s.sex, s.head, s.body, s.age or 0, s.likes, s.dislikes)
               for k, s in enumerate(self.living, 1)]
        now.append(entry(len(now) + 1, "Kept Ancestor", "Male", 95, 94, 600))
        text = (f"=== Virtual Villagers {game} -- {OLD} ===\n{hdr}\n\n" + "\n".join(old) + "\n\n"
                f"=== Virtual Villagers {game} -- {MID} ===\n{hdr}\n\n" + "\n".join(first) + "\n\n"
                f"=== Virtual Villagers {game} -- {NOW} ===\n{hdr}\n\n" + "\n".join(now) + "\n")
        self.history = v.folder / "Virtual Villagers Fun Patcher Logs" / "Save 1" / "Tribe History" / "Village History 1.txt"
        self.history.parent.mkdir(parents=True, exist_ok=True)
        self.history.write_bytes(text.replace("\n", "\r\n").encode("latin-1"))
        self.deaths = v.deaths("Death 1\n  Name: Gonea Testa\n  Age at death: 130\n  Sex: Female\n  Head: 99\n"
                               "  Body: 98\n\n"
                               "Death 2\n  Name: Kept Ancestor\n  Age at death: 610\n  Sex: Male\n  Head: 95\n"
                               "  Body: 94\n\n")
        self.events = v.log("Island Events", f"Virtual Villagers {game} Island Events Log 1.txt",
                            "Island event 1\n  Name: Gonea Testa\n  Event: The Fastest Runner\n"
                            "  Likes: (none) -> running\n\n"
                            f"Island event 2\n  Name: {coral.name}\n  Event: The Fastest Runner\n"
                            "  Likes: (none) -> running\n\n")

    def plan(self) -> hr.Plan:
        return hr.plan(self.v.folder, self.game, 1)

    def revise(self, plan: hr.Plan | None = None) -> hr.Result:
        return hr.revise(self.v.folder, self.game, 1, plan or self.plan(), FakeProcesses(),
                         datetime(2026, 10, 14, 12, 0, 0), confirm=True)


class Base(unittest.TestCase):
    def scene(self, game: int) -> Scene:
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        return Scene(root, game)

    def text(self, path: Path) -> str:
        return path.read_bytes().decode("latin-1")


class ProofOfGone(Base):
    def test_a_proven_gone_villager_is_removed_in_every_game(self):
        for game in GAMES:
            with self.subTest(game=game):
                s = self.scene(game)
                plan = s.plan()
                self.assertEqual([v.person.name for v in plan.gone], ["Gonea Testa"])
                s.revise(plan)
                history, deaths, events = self.text(s.history), self.text(s.deaths), self.text(s.events)
                self.assertNotIn("Gonea Testa", history)
                self.assertNotIn("Gonea Testa", deaths)
                self.assertNotIn("Gonea Testa", events)
                # Only that record went from the Deaths and Island Events logs.
                self.assertIn("Kept Ancestor", deaths)
                self.assertIn(f"Name: {s.coral.name}", events)

    def test_the_same_name_with_other_looks_is_kept_and_listed(self):
        for game in GAMES:
            with self.subTest(game=game):
                s = self.scene(game)
                plan = s.plan()
                kept = {v.person.key: v.reason for v in plan.kept}
                key = (s.other.name, 97, 96)
                self.assertIn(key, kept)
                self.assertIn("shares the name", kept[key])
                self.assertIn(s.other.name, plan.describe())
                s.revise(plan)
                self.assertIn("Head: 97", self.text(s.history))

    def test_a_possible_match_is_not_sure_and_kept_until_the_player_ticks_it(self):
        for game in GAMES:
            with self.subTest(game=game):
                s = self.scene(game)
                key = (s.other.name, 97, 96)
                plan = s.plan()
                self.assertIn(key, {v.person.key for v in plan.unsure})
                self.assertNotIn(key, plan.gone_keys)
                self.assertIn("Not sure", plan.describe())
                ticked = hr.plan(s.v.folder, game, 1, also_remove=frozenset({key}))
                self.assertIn(key, ticked.gone_keys)
                self.assertFalse(ticked.unsure)
                s.revise(ticked)
                self.assertNotIn("Head: 97", self.text(s.history))

    def test_the_owners_renamed_villagers_are_kept_and_never_removed(self):
        """Lupa Tangaroa is Coral Tangaroa now, Tamil Makawee is Mahalo Makawee (the owner's The Lost
        Children copy): kept, listed as renamed, and still in the history after the revision."""
        for game in GAMES:
            with self.subTest(game=game):
                s = self.scene(game)
                plan = s.plan()
                kept = {v.person.name: v.reason for v in plan.kept}
                self.assertIn("renamed", kept["Lupa Tangaroa"])
                self.assertIn("Coral Tangaroa", kept["Lupa Tangaroa"])
                self.assertIn("renamed", kept["Tamil Makawee"])
                self.assertIn("Mahalo Makawee", kept["Tamil Makawee"])
                self.assertNotIn("Lupa Tangaroa", {v.person.name for v in plan.gone})
                s.revise(plan)
                history = self.text(s.history)
                self.assertIn("Name: Lupa Tangaroa", history)
                self.assertIn("Name: Tamil Makawee", history)

    def test_current_villagers_and_this_tribes_own_dead_are_never_removed(self):
        for game in GAMES:
            with self.subTest(game=game):
                s = self.scene(game)
                save_before = s.v.save_path(1).read_bytes()
                plan = s.plan()
                living = {x.key for x in s.living}
                self.assertFalse(living & plan.gone_keys)
                self.assertFalse({c.who for c in plan.cuts} & living)
                kept = {v.person.name: v.reason for v in plan.kept}
                self.assertIn("lived in this tribe", kept["Kept Ancestor"])
                s.revise(plan)
                history = self.text(s.history)
                for x in s.living:
                    self.assertIn(f"Name: {x.name}", history)
                self.assertIn("Name: Kept Ancestor", history)
                self.assertEqual(s.v.save_path(1).read_bytes(), save_before)      # never the save

    def test_name_alone_is_never_proof_and_doubt_keeps(self):
        """A villager no snapshot places in a tribe (a Death record only) is kept; with no snapshot of the
        tribe being played, nothing is proven gone."""
        s = self.scene(2)
        s.v.deaths("Death 1\n  Name: Nowhere Seen\n  Age at death: 300\n  Sex: Male\n  Head: 90\n  Body: 91\n\n")
        kept = {v.person.name: v.reason for v in s.plan().kept}
        self.assertIn("no Village History snapshot", kept["Nowhere Seen"])
        s.history.write_bytes(s.history.read_bytes().split(b"=== Virtual Villagers 2 -- " + MID.encode())[0])
        plan = s.plan()
        self.assertEqual(plan.gone, [])
        self.assertTrue(plan.notes)


class EveryLog(Base):
    def test_births_conceptions_arrivals_and_unaccounted_records_of_the_gone_go_too(self):
        for game in GAMES:
            with self.subTest(game=game):
                s = self.scene(game)
                c = s.coral
                births = s.v.births(
                    "Arrived 1\n  Name: Gonea Testa\n  Age at arrival: 100\n  Sex: Female\n  Head: 99\n  Body: 98\n"
                    "  How: Founder\n\n"
                    "Conception 1\n  Mother: Gonea Testa\n    Age at conception: 110\n    Head: 99\n    Body: 98\n"
                    "  Father: (unknown)\n\n"
                    "Birth 1\n  Child: Gonea Testa\n    Sex: Female\n    Head: 99\n    Body: 98\n"
                    "  Mother: (unknown)\n  Father: (unknown)\n\n"
                    f"Arrived 2\n  Name: Lupa Tangaroa\n  Age at arrival: 1\n  Sex: {c.sex}\n  Head: 24\n  Body: 28\n"
                    "  How: Founder\n\n"
                    f"Conception 2\n  Mother: Lupa Tangaroa\n    Age at conception: 2\n    Head: 24\n    Body: 28\n"
                    "  Father: (unknown)\n\n")
                unaccounted = s.v.log("Unaccounted Villagers", f"Virtual Villagers {game} Unaccounted Villagers Log 1.txt",
                                      "Unaccounted 1\n  Name: Gonea Testa\n  Sex: Female\n  Head: 99\n  Body: 98\n\n")
                plan = s.plan()
                self.assertEqual(sum(1 for x in plan.cuts if x.path == births), 3)
                s.revise(plan)
                text = self.text(births)
                self.assertNotIn("Arrived 1\r\n", text)
                self.assertNotIn("Conception 1\r\n", text)
                self.assertNotIn("Birth 1\r\n", text)
                # The renamed villager's own records stay.
                self.assertIn("Arrived 2\r\n  Name: Lupa Tangaroa", text)
                self.assertIn("Conception 2\r\n  Mother: Lupa Tangaroa", text)
                self.assertTrue(text.startswith(s.v.header + "\r\nArrived 2\r\n"))
                self.assertNotIn("Gonea Testa", self.text(unaccounted))

    def test_a_parent_of_this_tribe_is_never_proven_gone(self):
        """A Conception that names a villager of this tribe with one only an older snapshot lists joins
        that snapshot to this tribe: nobody in it is proven gone."""
        s = self.scene(3)
        s.v.births("Conception 1\n  Mother: Lupa Tangaroa\n    Age at conception: 2\n    Head: 24\n    Body: 28\n"
                   "  Father: Gonea Testa\n    Head: 99\n    Body: 98\n\n")
        plan = s.plan()
        self.assertEqual(plan.gone, [])
        self.assertIn("Gonea Testa", {v.person.name for v in plan.kept})


class Safety(Base):
    def test_each_log_is_copied_first_and_a_failed_write_puts_everything_back(self):
        for game in GAMES:
            with self.subTest(game=game):
                s = self.scene(game)
                plan = s.plan()
                before = {p: p.read_bytes() for p in (s.history, s.deaths, s.events)}
                real = hr._write
                calls = []

                def failing(path, data):
                    calls.append(path)
                    if len(calls) == 2:
                        raise OSError("disk full (test)")
                    real(path, data)
                hr._write = failing
                try:
                    with self.assertRaises(hr.HistoryRevisionError):
                        s.revise(plan)
                finally:
                    hr._write = real
                for path, data in before.items():
                    self.assertEqual(path.read_bytes(), data, path.name)
                copies = list((s.v.folder / "Virtual Villagers Fun Patcher Data" / "Copies Made Before Repairs")
                              .rglob("*" + hr.BACKUP_SUFFIX))
                self.assertTrue(copies)
                # ...and a successful run copies each log it changes first, byte for byte.
                s.revise(plan)
                copies = {c.name: c for c in (s.v.folder / "Virtual Villagers Fun Patcher Data" /
                                              "Copies Made Before Repairs").rglob("*" + hr.BACKUP_SUFFIX + "*")}
                for path, data in before.items():
                    self.assertTrue(any(c.read_bytes() == data for n, c in copies.items()
                                        if n.startswith(path.name)), path.name)

    def test_a_log_replaced_before_its_read_back_fails_is_put_back_too(self):
        for game in GAMES:
            with self.subTest(game=game):
                s = self.scene(game)
                plan = s.plan()
                before = {p: p.read_bytes() for p in (s.history, s.deaths, s.events)}
                real = hr._write
                calls = []

                def replaced_then_failing(path, data):
                    calls.append(path)
                    real(path, data)
                    if len(calls) == 2:
                        raise OSError("read-back failed (test)")
                hr._write = replaced_then_failing
                try:
                    with self.assertRaises(hr.HistoryRevisionError):
                        s.revise(plan)
                finally:
                    hr._write = real
                for path, data in before.items():
                    self.assertEqual(path.read_bytes(), data, path.name)

    def test_repairs_made_lists_each_villager_removed(self):
        for game in GAMES:
            with self.subTest(game=game):
                s = self.scene(game)
                s.revise()
                repairs = list((s.v.folder / "Virtual Villagers Fun Patcher Logs").rglob(
                    f"Virtual Villagers {game} Repairs Log *.txt"))
                self.assertEqual(len(repairs), 1)
                text = self.text(repairs[0])
                self.assertIn("Removed: Gonea Testa (Female, head 99, body 98) -- from ", text)
                self.assertIn(f"Village History snapshots of {OLD}", text)
                self.assertIn("Village History 1.txt", text)
                self.assertNotIn("Lupa Tangaroa", text)
                self.assertEqual(len(re.findall(r"^  Removed: ", text, re.M)), 1)

    def test_it_is_never_ticked_by_default_and_needs_the_confirmation(self):
        self.assertFalse(hr.DEFAULT_TICKED)
        s = self.scene(3)
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in s.v.folder.rglob("*") if p.is_file()}
        with self.assertRaises(hr.HistoryRevisionError):
            hr.revise(s.v.folder, 3, 1, s.plan(), FakeProcesses())
        after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in s.v.folder.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        gui = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertIn("history_var = tk.BooleanVar(value=vv_history_revision.DEFAULT_TICKED)", gui)
        self.assertIn("self._history_list_dialog(window, history_plan, ask=True)", gui)

    def test_the_confirmation_lists_each_log_with_a_count_and_the_kept_with_reasons(self):
        s = self.scene(4)
        text = s.plan().describe()
        self.assertIn("Village History 1.txt: 1 block(s)", text)
        self.assertIn("Deaths Log 1.txt: 1 block(s)", text)
        self.assertIn("Island Events Log 1.txt: 1 block(s)", text)
        self.assertIn("Kept (still in the save under another name, or unproven):", text)
        self.assertIn("Lupa Tangaroa", text)

    def test_the_game_running_refuses(self):
        class Running(FakeProcesses):
            def find(self, exe_name):
                return [1234]
        s = self.scene(5)
        before = s.history.read_bytes()
        with self.assertRaises(tools.GameRunning):
            hr.revise(s.v.folder, 5, 1, s.plan(), Running(), confirm=True)
        self.assertEqual(s.history.read_bytes(), before)


class WholeSnapshot(Base):
    def test_a_snapshot_whose_villagers_all_go_takes_its_heading(self):
        s = self.scene(1)
        text = s.history.read_bytes().decode("latin-1")
        # Only the gone villager in the restarted tribe's snapshot.
        hdr = s.v.header
        old = f"=== Virtual Villagers 1 -- {OLD} ===\r\n{hdr}\r\n\r\n" + entry(1, "Gonea Testa", "Female", 99, 98, 120
                                                                                ).replace("\n", "\r\n") + "\r\n\r\n"
        rest = text[text.index(f"=== Virtual Villagers 1 -- {MID}"):]
        s.history.write_bytes((old + rest).encode("latin-1"))
        s.revise()
        self.assertEqual(s.history.read_bytes().decode("latin-1"), rest)


class FamilyTree(Base):
    def test_hide_villagers_not_in_the_current_save(self):
        import vv_genealogy as gen
        s = self.scene(2)
        village = gen.load_village(s.v.folder, 2, 1)
        hidden = hr.hidden_in_tree(s.v.folder, 2, 1)
        self.assertEqual({k[0] for k in hidden}, {"Gonea Testa"})
        shown = hr.without(village, hidden)
        names = {p.name for p in shown.people.values()}
        self.assertNotIn("Gonea Testa", names)
        self.assertIn("Gonea Testa", {p.name for p in village.people.values()})     # the tree read them
        self.assertEqual({p.name for p in village.people.values()} - names, {"Gonea Testa"})
        self.assertEqual({p.name for p in shown.people.values() if p.alive},
                         {p.name for p in village.people.values() if p.alive})
        window = (ROOT / "src" / "vv_genealogy_window.py").read_text(encoding="utf-8")
        self.assertIn('self.window.get("hide_not_in_save", True)', window)       # on by default
        self.assertIn('text="Hide villagers not in the current save"', window)


if __name__ == "__main__":
    unittest.main()
