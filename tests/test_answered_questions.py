"""Answered questions (src/vv_answered_questions.py), all five games.

The owner (v1.35.80): "once I answer a question it shouldn't be asked again (goes to an answered
questions section where I can change the answer)".  A real answer is kept by the FACT the question
is about -- what the record says and whose it is, followed through the patcher's renames -- never
by a line number, a file name that rolls or moves, a record number or a count; "Don't know" is the
only answer asked again.  And the patcher's own renames are never a question in the read-only
reconciliation (the Repair Saves & Logs audit: after numbering, "mother Java in the save copy, Java I
in the save"; after last names, "Bora / Upawa possibly lost").
"""
from __future__ import annotations

import json
import os
import sys
import time
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_answered_questions as aq  # noqa: E402
import vv_last_names as ln  # noqa: E402
import vv_log_additions as additions  # noqa: E402
import vv_log_contradictions as contra  # noqa: E402
import vv_log_decisions as decisions  # noqa: E402
import vv_log_tools as tools  # noqa: E402
import vv_reconcile as rc  # noqa: E402
import vv_save_layout as layout  # noqa: E402
from test_log_contradictions import Folder, arrived, birth  # noqa: E402
from test_reconcile import Base, FakeProcesses, aged  # noqa: E402

LOGS = "Virtual Villagers Fun Patcher Logs"
BIRTHS = "Births and Conceptions"
NOW = datetime(2026, 10, 20, 12, 0, 0)


def cheop(folder: Folder, where: str | None = None, number: int = 11, name: str = "Cheop Bahati",
          before: str = "", log: int = 1) -> Path:
    """Cheop's Birth record and a backfilled Arrived record of him (a contradiction): at `where` (the
    older shared folder by default), "Arrived <number>", in Births and Conceptions Log <log>."""
    text = before + birth(name, 4, 15) + arrived(number, name, 4, 15, how="Founder")
    rel = where or f"{LOGS}\\{BIRTHS}"
    return folder.write(f"{rel}\\Virtual Villagers {folder.game} Births and Conceptions Log {log}.txt",
                        "Village: Kalahuna Tribe (Save 1)\n" + text)


def plan(folder: Folder) -> list:
    kinds = [contra.plan(folder.path, folder.game, 1)]
    aq.hold_back(folder.path, folder.game, 1, kinds)
    return kinds


def answer(kinds: list, main: str, retro: str = contra.RETRO_YES) -> dict:
    return {k: (retro if k.startswith("retro|") else main) for kind in kinds for k in kind.questions}


class NotAskedAgain(unittest.TestCase):
    """Every kind of answer that leaves the records as they are -- the ones asked again before."""

    def keep(self, game: int) -> Folder:
        f = Folder(game)
        cheop(f)
        kinds = plan(f)
        self.assertEqual(len(kinds[0].questions), 2, "the contradiction and its Retroactively edit records?")
        lines = aq.record(f.path, game, 1, kinds, {"contradictions"}, answer(kinds, contra.KEEP), NOW)
        self.assertEqual(len(lines), 2, lines)
        return f

    def assert_held(self, f: Folder, verdict: str = contra.KEEP) -> None:
        kinds = plan(f)
        self.assertEqual(kinds[0].questions, {}, "not asked again")
        held = [d.get("applied", d.get("verdict")) for _q, d in kinds[0].remembered.values()]
        self.assertIn(verdict, held)
        self.assertIn(verdict, aq.remembered_answers(kinds).values())

    def test_an_answer_is_not_asked_again_in_every_game(self):
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                f = self.keep(game)
                self.assert_held(f)
                # Check Saves & Logs follows it too: a note, never WRONG again.
                self.assertEqual([x for x in contra.find(f.path, game, 1) if x.wrong], [])

    def test_renumbered_records_moved_lines_a_rolled_file_and_the_save_folders(self):
        for game in (1, 3, 5):
            with self.subTest(game=game):
                f = self.keep(game)
                # The record renumbered ("Arrived 11" -> "Arrived 4") and moved down by records above it.
                cheop(f, number=4, before=birth("Kai Bahati", 2, 2) + birth("Lulu Bahati", 3, 3))
                self.assert_held(f)
                # The log rolled into a new numbered file (the first one gone).
                (f.path / LOGS / BIRTHS / f"Virtual Villagers {game} Births and Conceptions Log 1.txt").unlink()
                cheop(f, number=4, log=2)
                self.assert_held(f)
                # Moved into the save's own folder (Move Files to Save Folders).
                (f.path / LOGS / BIRTHS / f"Virtual Villagers {game} Births and Conceptions Log 2.txt").unlink()
                own = layout.own_slot_log_folder(f.path, BIRTHS, 1).relative_to(f.path)
                cheop(f, where=str(own), number=4)
                self.assert_held(f)

    def test_a_rename_by_the_patcher_is_followed(self):
        f = self.keep(2)
        # Last Names renamed him everywhere, and kept the rename (vv_last_names _plan_answers).
        work = ln.Plan({("Cheop Bahati", 4, 15): "Cheop Kai"})
        ln._plan_answers(work, f.path, 2, 1, {("Cheop Bahati", 4, 15): "Cheop Kai"})
        (change,) = work.changes
        decisions.path(f.path, 2, 1).write_bytes(change.updated)
        cheop(f, name="Cheop Kai")
        self.assert_held(f)
        # Without the rename kept, the same records under the new name are a new question.
        kept = [d for d in decisions.load(f.path, 2, 1) if d["kind"] != decisions.ALIAS_KIND]
        decisions.path(f.path, 2, 1).write_bytes(decisions.encode(kept))
        self.assertEqual(len(plan(f)[0].questions), 2)

    def test_dont_know_is_asked_again(self):
        f = Folder(4)
        cheop(f)
        kinds = plan(f)
        self.assertEqual(aq.record(f.path, 4, 1, kinds, {"contradictions"}, answer(kinds, contra.LEAVE), NOW), [],
                         "\"Don't know\" -- and the Retroactively edit records? that goes with it -- is never kept")
        self.assertEqual(len(plan(f)[0].questions), 2)

    def test_an_unticked_kind_keeps_no_answer(self):
        f = Folder(1)
        cheop(f)
        kinds = plan(f)
        self.assertEqual(aq.record(f.path, 1, 1, kinds, set(), answer(kinds, contra.KEEP), NOW), [])

    def test_alike_questions_are_told_apart_by_their_order(self):
        """Two questions alike in every way: an answer given while there were two is taken only while
        there are two (one taken out since must not hand its answer to the other)."""
        k = additions.Kind("born_arrived", "x")
        for n in (1, 2):
            k.questions[f"q{n}"] = additions.Question(f"q{n}", "Remove?", [additions.REMOVE_IT, additions.KEEP_IT],
                                                      additions.REMOVE_IT, "same", (("Hoani", 11, 2),))
        f = Folder(1)
        aq.record(f.path, 1, 1, [k], {"born_arrived"}, {"q1": additions.REMOVE_IT, "q2": additions.KEEP_IT}, NOW)
        both = additions.Kind("born_arrived", "x", questions=dict(k.questions))
        aq.hold_back(f.path, 1, 1, [both])
        self.assertEqual({key: d["verdict"] for key, (_q, d) in both.remembered.items()},
                         {"q1": additions.REMOVE_IT, "q2": additions.KEEP_IT})
        one = additions.Kind("born_arrived", "x", questions={"q2": k.questions["q2"]})
        aq.hold_back(f.path, 1, 1, [one])
        self.assertIn("q2", one.questions, "one left of two: asked again, never given the other's answer")

    def test_a_title_from_a_date_already_added_is_not_asked_again(self):
        """"From <date>" added the title from that snapshot on; the older ones still lack it, so the
        question came back with only their dates: the answer now means "Only from now on"."""
        f = Folder(3)
        q = additions.Question("custom|x", "?", ["From 2026-10-01", "From 2026-10-05", additions.FROM_NOW],
                               additions.FROM_NOW, "Custom title=Sky", (("Pua", 1, 2),))
        k = additions.Kind("custom", "Custom titles", questions={"custom|x": q})
        aq.record(f.path, 3, 1, [k], {"custom"}, {"custom|x": "From 2026-10-05"}, NOW)
        again = additions.Kind("custom", "Custom titles", questions={"custom|x": additions.Question(
            "custom|x", "?", ["From 2026-10-01", additions.FROM_NOW], additions.FROM_NOW, "Custom title=Sky",
            (("Pua", 1, 2),))})
        aq.hold_back(f.path, 3, 1, [again])
        self.assertEqual(again.questions, {})
        self.assertEqual(aq.remembered_answers([again]), {"custom|x": additions.FROM_NOW})


class Helpers(Base):
    def village_with_cheop(self, game: int):
        v = self.village("huttest", game)
        births = v.births(birth("Cheop Bahati", 4, 15) + arrived(11, "Cheop Bahati", 4, 15, how="Founder"))
        return v, births

    def repair(self, v, game: int, answers: dict, kinds=None, changes=None):
        return tools.approve_repair(v.folder, game, 1, FakeProcesses(), NOW, chosen={"contradictions"},
                                    answers=answers, kinds=kinds, rearm=False, answered_changes=changes)

    def repairs_log(self, v) -> str:
        return "".join(p.read_bytes().decode("latin-1") for p in v.folder.rglob("*Repairs Log*.txt")
                       if "Backups" not in p.parts)

    def kinds(self, v, game: int) -> list:
        return additions.plan(v.folder, game, 1)

    def contradictions(self, kinds: list):
        return next(k for k in kinds if k.id == "contradictions")


class ChangeAndClear(Helpers):
    """The Answered questions section: a change is applied as a first answer is (backup first, Repairs
    Made record), and a cleared answer is asked again."""

    def test_change_a_kept_answer_is_applied_with_a_backup_and_a_repairs_record(self):
        for game in (1, 2, 3, 4, 5):
            with self.subTest(game=game):
                v, births = self.village_with_cheop(game)
                kinds = self.kinds(v, game)
                ck = self.contradictions(kinds)
                first = self.repair(v, game, answer([ck], contra.KEEP), kinds)
                self.assertIn("Arrived 11", births.read_bytes().decode("latin-1"), "Keep both changes nothing")
                self.assertTrue(first.kept_answers)
                self.assertIn("Answered:", self.repairs_log(v))
                kinds = self.kinds(v, game)
                ck = self.contradictions(kinds)
                self.assertEqual(ck.questions, {}, "not asked again")
                rows = [r for r in aq.listing(v.folder, game, 1, kinds) if r.group.startswith(aq.LISTED[aq.KIND])]
                self.assertEqual(len(rows), 2)
                self.assertTrue(all(r.matches and r.live for r in rows))
                # The section: "Take it out" now -- the question is asked again in this Repair with it chosen.
                answers = aq.remembered_answers(kinds)
                for r in rows:
                    kind, key, q = r.live
                    kind.questions[key] = q
                    del kind.remembered[key]
                    answers[key] = contra.RETRO_YES if key.startswith("retro|") else contra.TAKE_OUT
                backups = len(list((v.folder / "Backups").iterdir()))
                second = self.repair(v, game, answers, kinds)
                self.assertEqual(len(list((v.folder / "Backups").iterdir())), backups + 1, "backed up first")
                self.assertNotIn("Arrived 11", births.read_bytes().decode("latin-1"), "the new answer is applied")
                self.assertIn("Answer changed:", self.repairs_log(v))
                self.assertTrue(any("Answer changed" in line for line in second.kept_answers))
                kept = {d["verdict"] for d in decisions.load(v.folder, game, 1) if d["kind"] == aq.KIND}
                self.assertEqual(kept, {contra.TAKE_OUT, contra.RETRO_YES})

    def test_clear_asks_again_and_a_change_with_no_question_now_is_kept(self):
        v, _births = self.village_with_cheop(3)
        kinds = self.kinds(v, 3)
        self.repair(v, 3, answer([self.contradictions(kinds)], contra.KEEP), kinds)
        rows = aq.listing(v.folder, 3, 1, self.kinds(v, 3))
        main = next(r for r in rows if r.answer == contra.KEEP)
        retro = next(r for r in rows if r.answer == contra.RETRO_YES)
        # Changed while no question matches it (only kept), and cleared.
        self.repair(v, 3, {}, None, {"changed": {retro.ident: contra.RETRO_NO}, "cleared": {main.ident}})
        log = self.repairs_log(v)
        self.assertIn("Answer cleared (asked again):", log)
        self.assertIn("Answer changed:", log)
        ck = self.contradictions(self.kinds(v, 3))
        self.assertTrue(any(k.startswith("contradiction|") for k in ck.questions), "cleared: asked again")
        verdicts = {d["verdict"] for d in decisions.load(v.folder, 3, 1) if d["kind"] == aq.KIND}
        self.assertEqual(verdicts, {contra.RETRO_NO})

    def test_an_answer_that_no_longer_matches_is_shown_never_dropped(self):
        v, births = self.village_with_cheop(5)
        kinds = self.kinds(v, 5)
        self.repair(v, 5, answer([self.contradictions(kinds)], contra.KEEP), kinds)
        births.write_bytes(births.read_bytes().replace(b"Arrived 11", b"Death 1"))   # the records changed
        rows = [r for r in aq.listing(v.folder, 5, 1, self.kinds(v, 5)) if r.group.startswith(aq.LISTED[aq.KIND])]
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(not r.matches for r in rows))
        self.assertTrue(all("No longer matches" in r.status for r in rows))

    def test_a_yes_no_question_asked_on_its_own_is_kept(self):
        v = self.village("huttest", 2)
        who = (("Mosi", 3, 4),)
        self.assertIsNone(aq.asked_before(v.folder, 2, 1, "totem_elder", "statue|Mosi", who))
        aq.keep_yes_no(v.folder, 2, 1, "totem_elder", "Totems", "statue|Mosi", who, "Is it Mosi's?", False, NOW)
        self.assertEqual(aq.asked_before(v.folder, 2, 1, "totem_elder", "statue|Mosi", who), aq.NO)
        (row,) = aq.listing(v.folder, 2, 1, [])
        self.assertIsNone(row.matches)
        self.assertIn("Asked on its own", row.status)


class TheSectionWindow(Helpers):
    """The Answered questions window itself: a change made there puts the question back in this Repair
    with the new answer chosen; a clear is kept for Repair."""

    def test_the_window_changes_and_clears(self):
        import types
        try:
            import tkinter as tk
            from tkinter import ttk
            root = tk.Tk()
        except Exception as exc:                      # no display (CI without a desktop)
            self.skipTest(f"no Tk display ({exc})")
        self.addCleanup(root.destroy)
        root.withdraw()
        import vv_fun_patcher_gui as gui
        v, _births = self.village_with_cheop(2)
        kinds = self.kinds(v, 2)
        self.repair(v, 2, answer([self.contradictions(kinds)], contra.KEEP), kinds)
        kinds = self.kinds(v, 2)
        answers = aq.remembered_answers(kinds)
        questions: list = []
        state = {"changed": {}, "cleared": set()}
        stub = types.SimpleNamespace(_run_with_wait=lambda _message, work: work(), ANSWERED_PAGE=40,
                                     ASKED_AGAIN=gui.App.ASKED_AGAIN)
        info = types.SimpleNamespace(name="Kalahuna Tribe", slot=1)
        seen: dict = {}

        def walk(widget):
            yield widget
            for child in widget.winfo_children():
                yield from walk(child)

        def press() -> None:
            (window,) = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
            widgets = list(walk(window))
            boxes = [w for w in widgets if isinstance(w, ttk.Combobox)]
            seen["boxes"] = len(boxes)
            take = next(b for b in boxes if contra.TAKE_OUT in b.cget("values"))
            take.set(contra.TAKE_OUT)
            clears = [w for w in widgets if isinstance(w, ttk.Checkbutton)]
            retro_box = next(b for b in boxes if contra.RETRO_NO in b.cget("values"))
            # The retro question's row: its Clear tick is the one after its box.
            row = retro_box.master
            next(w for w in row.winfo_children() if isinstance(w, ttk.Checkbutton)).invoke()
            seen["clears"] = len(clears)
            next(w for w in widgets if isinstance(w, ttk.Button) and w.cget("text") == "Keep these changes").invoke()

        root.after(300, press)
        gui.App._answered_questions_dialog(stub, root, v.folder, 2, info, kinds, answers, questions, state)
        self.assertEqual(seen["boxes"], 2)
        ck = self.contradictions(kinds)
        main = next(k for k in ck.questions if k.startswith("contradiction|"))
        retro = next(k for k in ck.questions if k.startswith("retro|"))
        self.assertEqual(answers[main], contra.TAKE_OUT, "asked again in this Repair, the new answer chosen")
        self.assertEqual(answers[retro], gui.App.ASKED_AGAIN, "cleared: Don't know, so nothing is applied")
        self.assertEqual(len(questions), 2)
        self.assertEqual(len(state["cleared"]), 1)


class OldAnswers(Base):
    """Answers kept before v1.35.80 keep working, under their old ids."""

    def test_a_cut_file_answer_kept_by_its_length_still_holds_and_is_moved_to_the_new_id(self):
        for game in (1, 4):
            with self.subTest(game=game):
                v = self.village("huttest", game)
                path = v.deaths("Death 1\n  Name: Kai\n", newline=False)
                (q,) = [f for f in rc.reconcile(v.folder, game, 1).questions if f.topic == "file"]
                old = f"cut|{rc._answer_place(v.folder, rc._rel(v.folder, path))}|{len(path.read_bytes())}"
                self.assertNotEqual(q.qid, old, "the new id holds no length")
                decisions.record(v.folder, game, 1, [{"kind": rc.DECISION_KIND, "village": v.header, "field": old,
                                                      "verdict": q.options[0], "edited": False}], NOW)
                rec = rc.reconcile(v.folder, game, 1)
                self.assertEqual([f for f in rec.questions if f.topic == "file"], [], "the old answer holds")
                self.assertEqual(rec.migrated[q.qid][1], q.options[0])
                # The file grows (records appended above the cut end are not the cut): still the same cut.
                kind = rc.kind(v.folder, game, 1)
                rc.remember(v.folder, game, 1, [kind], {}, NOW)
                (d,) = [d for d in decisions.load(v.folder, game, 1) if d["kind"] == rc.DECISION_KIND]
                self.assertEqual((d["field"], d["was"], d["verdict"]), (q.qid, old, q.options[0]))
                self.assertEqual([f for f in rc.reconcile(v.folder, game, 1).questions if f.topic == "file"], [])

    def test_an_answer_about_the_save_holds_after_the_next_save(self):
        """The save's file time was in the id: every save made the answer a new question."""
        v = self.village("huttest", 3)
        people = v.people(v.save_path(1).read_bytes())
        v.history([("2026-10-11 20:00:00", [aged(people[0], 50)] + people[1:])])
        rec = rc.reconcile(v.folder, 3, 1)
        (q,) = [f for f in rec.questions if f.topic == "age"]
        self.assertNotIn(rc._when(v.save_path(1)), q.qid)
        kind = rc.kind(v.folder, 3, 1, rec)
        rc.remember(v.folder, 3, 1, [kind], {q.qid: q.options[0]}, NOW)
        later = time.time() + 3600
        os.utime(v.save_path(1), (later, later))         # the game saved again
        self.assertEqual([f for f in rc.reconcile(v.folder, 3, 1).questions if f.topic == "age"], [])

    def test_an_old_born_arrived_decision_follows_a_rename(self):
        f = Folder(1)
        decisions.record(f.path, 1, 1, [{"kind": "born_arrived", "village": None, "name": "Cheop", "head": 4,
                                         "body": 15, "verdict": "remove", "edited": False},
                                        {"kind": decisions.ALIAS_KIND, "village": None, "name": "Cheop", "head": 4,
                                         "body": 15, "field": "Cheop Bahati", "verdict": "renamed",
                                         "edited": False}], NOW)
        self.assertIn(("Cheop Bahati", 4, 15), decisions.decided(f.path, 1, 1, "born_arrived", "remove"))


class PatcherRenamesAreNoQuestion(Base):
    """The Repair Saves & Logs audit (VV4, VV5): a rename the patcher made rewrites the save and the logs
    but never the game's older copies of the save, so the next Check asked about the villagers renamed."""

    def test_a_parent_renamed_is_no_question(self):
        """The audit's VV5: "Upawa: mother Java in the save copy, Java I in the save. Which is right?"."""
        for game in (2, 3, 4, 5):
            with self.subTest(game=game):
                v = self.village("huttest", game)
                original = v.save_path(1).read_bytes()
                people = v.people(original)
                mother = next(p for p in people if any(c.mother == p.name for c in people)
                              and sum(q.name == p.name for q in people) == 1)
                v.write_save(21, original, when=time.time() - 7200)
                ln.give_last_names(v.folder, game, 1, {mother.key: "I"}, processes=FakeProcesses())
                f = ln.FIELDS[game]
                data = bytearray(v.save_path(1).read_bytes())
                for at in ln._entries(game, data):
                    if ln._cstr(data, at + f.mother, f.parent_cap) == mother.name:
                        ln._put_name(data, at + f.mother, f.parent_cap, f"{mother.name} I")
                v.write_save(1, bytes(data))
                self.assertEqual([t for t in self.asked(v, game, mother.name) if "mother" in t], [])
                decisions.path(v.folder, game, 1).unlink()          # the rename forgotten: asked, as before
                self.assertTrue([t for t in self.asked(v, game, mother.name) if "mother" in t])

    def renamed_village(self, game: int):
        v = self.village("huttest", game)
        original = v.save_path(1).read_bytes()
        people = v.people(original)
        # A mother whose name nobody else has (so her children's records carry the new name too).
        mother = next(p for p in people if any(c.mother == p.name for c in people)
                      and sum(q.name == p.name for q in people) == 1)
        child = next(c for c in people if c.mother == mother.name)
        # The game's older copy of the save, before the rename.
        v.write_save(21, original, when=time.time() - 7200)
        ln.give_last_names(v.folder, game, 1, {mother.key: "Kai", child.key: "Kai"}, processes=FakeProcesses())
        # The child's record names the mother by her new name, as the owner's did (Last Names renames a parent
        # reference whose looks are the parent's; the fixture's are not, so it is written here).
        f = ln.FIELDS[game]
        data = bytearray(v.save_path(1).read_bytes())
        for at in ln._entries(game, data):
            if ln._cstr(data, at, f.name_cap) == f"{child.name} Kai":
                ln._put_name(data, at + f.mother, f.parent_cap, f"{mother.name} Kai")
        v.write_save(1, bytes(data))
        return v, mother, child

    def asked(self, v, game: int, *names: str) -> list[str]:
        return [f.text for f in rc.reconcile(v.folder, game, 1).questions if any(n in f.text for n in names)]

    def test_last_names_given_are_no_question(self):
        for game in (2, 3, 4, 5):
            with self.subTest(game=game):
                v, mother, child = self.renamed_village(game)
                self.assertEqual(self.asked(v, game, mother.name, child.name), [])

    def test_without_the_rename_kept_they_were_asked(self):
        """The test can fail: the renames taken out of the Log Decisions file, the old questions come back."""
        v, mother, child = self.renamed_village(5)
        decisions.path(v.folder, 5, 1).unlink()
        self.assertTrue(self.asked(v, 5, mother.name, child.name))

    def test_numbering_listed_in_the_repairs_made_log_is_no_question(self):
        """Renames before v1.35.80 were kept nowhere but Number Duplicate Names' "Renamed:" lines."""
        for game in (2, 5):
            with self.subTest(game=game):
                v, mother, child = self.renamed_village(game)
                decisions.path(v.folder, game, 1).unlink()
                path, text = tools.repair_record_start(v.folder, game, v.header, 1, NOW)
                for who in (mother, child):
                    text += f"  Renamed: {who.name} (head {who.head}, body {who.body}) -> {who.name} Kai\r\n"
                with open(path, "ab") as log:
                    log.write((text + "\r\n").encode("latin-1"))
                self.assertEqual(self.asked(v, game, mother.name, child.name), [])

    def test_the_rename_is_kept_even_with_no_answers_yet(self):
        v, mother, _child = self.renamed_village(3)
        kept = [d for d in decisions.load(v.folder, 3, 1) if d["kind"] == decisions.ALIAS_KIND]
        self.assertIn((mother.name, mother.head, mother.body, f"{mother.name} Kai"),
                      {(d["name"], d["head"], d["body"], d["field"]) for d in kept})
        self.assertTrue(all(d["village"] == v.header for d in kept))
        json.loads(decisions.path(v.folder, 3, 1).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
