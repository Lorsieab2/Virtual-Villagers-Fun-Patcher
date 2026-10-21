"""A villager is the same villager through any change of looks or title (all five games).

The owner (v1.35.80 update), after The Secret City's new Tribal Chiefs -- the game gives a chief the chief's
robe, a new body, with no record of it -- were shown "left the village" in the Family Tree Maker and again
under a Roman numeral: "A change in body, head and mask does not mean they disappeared.  A change in title or
special villager status does not mean they disappeared."  And: "Please add prompts in the Family Tree Maker
to ask if a villager that's changed is the same or different."

Covered here, on the repository's own fixture saves of all five games (tests/fixtures/rename_tribe):
  * a change of looks the Village History shows unbroken (a chief's robe in The Secret City, any head or
    body elsewhere) keeps ONE villager: never "left the village", never asked, never numbered, and the
    reconciliation only notes it;
  * a change of title or mask alone changes nothing;
  * a change the records cannot settle is asked once; Same joins them, Different keeps them apart everywhere
    (the tree and the reconciliation), Don't know asks again, and an answer changed in Answered questions
    takes effect;
  * Repair Saves & Logs takes off a number a looks change gave (with the evidence, a backup and a Repairs Made
    record), and never one a genuine namesake explains.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_answered_questions as aq  # noqa: E402
import vv_genealogy as gen  # noqa: E402
import vv_number_names as nn  # noqa: E402
import vv_reconcile as rc  # noqa: E402
from test_reconcile import CASES, Base, FakeProcesses, words  # noqa: E402

T1, T2 = "2026-10-21 11:28:45", "2026-10-21 11:32:11"


def history_text(v, snapshots, extra: dict | None = None) -> None:
    """The Village History log: `snapshots` [(date, [Seen])]; `extra` {(date, name): [lines]} added under that
    villager in that snapshot (a title, a mask)."""
    out = []
    for date, people in snapshots:
        out.append(f"=== Virtual Villagers {v.game} -- {date} ===\n{v.header}\n")
        for k, s in enumerate(people, 1):
            more = "".join(f"  {line}\n" for line in (extra or {}).get((date, s.name), []))
            out.append(f"Villager {k}\n  Name: {s.name}\n{more}  Age: {s.age}\n  Sex: {s.sex}\n  Head: {s.head}\n"
                       f"  Body: {s.body}\n  Likes: {words(s.likes)}\n  Dislikes: {words(s.dislikes)}\n")
    path = v.folder / "Virtual Villagers Fun Patcher Logs" / "Save 1" / "Tribe History" / "Village History 1.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes("\n".join(out).replace("\n", "\r\n").encode("latin-1"))


def arrived(n: int, s, head: int, body: int, how: str = "Founder") -> str:
    return (f"Arrived {n}\n  Name: {s.name}\n  Age at arrival: {max(0, (s.age or 0) - 2)}\n  Sex: {s.sex}\n"
            f"  Head: {head}\n  Body: {body}\n  Likes: {words(s.likes)}\n  Dislikes: {words(s.dislikes)}\n"
            f"  How: {how}\n\n")


class Changed(Base):
    def setup_game(self, tag: str, game: int):
        """A village of the game's fixture save, and the villager whose looks change: the first whose name
        nobody else has; their new looks (the chief's robe, body 29, in The Secret City)."""
        v = self.village(tag, game)
        data = v.save_path(1).read_bytes()
        people = v.people(data)
        names = [s.name for s in people]
        rank, x = next((k, s) for k, s in enumerate(people) if names.count(s.name) == 1 and s.sex)
        new_body = 29 if game == 3 and x.body != 29 else (x.body + 7) % 20
        if new_body == x.body:
            new_body = (x.body + 1) % 20
        now = v.relooked(data, rank, x.head, new_body)
        v.write_save(1, now)
        return v, data, now, x, new_body

    def one_of(self, village, name):
        return [p for p in village.known() if gen.unnumbered(p.name) == name]


class LooksChangeKeepsOneVillager(Changed):
    def test_an_unbroken_history_through_a_change_of_looks_is_one_villager_in_every_game(self):
        for tag, game in CASES:
            with self.subTest(game=game, tag=tag):
                v, old, now, x, new_body = self.setup_game(tag, game)
                history_text(v, [(T1, v.people(old)), (T2, v.people(now))])
                v.births(arrived(1, x, x.head, x.body))
                village = gen.load_village(v.folder, game, 1)
                mine = self.one_of(village, x.name)
                self.assertEqual(len(mine), 1, [(p.key, p.alive, p.gone) for p in mine])
                self.assertTrue(mine[0].alive)
                self.assertEqual(mine[0].key, (x.name, x.head, new_body))
                self.assertIn((x.head, x.body), mine[0].old_looks)
                self.assertEqual(village.relooked[(x.name, x.head, x.body)], (x.name, x.head, new_body))
                self.assertFalse([q for q in village.identity_questions if x.name in (q.older[0], q.newer[0])])
                # ...never "left the village", never a namesake to number:
                self.assertFalse([p for p in village.known() if p.name == x.name and not p.alive and not p.gone])
                pending = nn.pending(v.folder, game, 1)
                self.assertFalse([k for k in nn.wanted_names(pending) if k[0] == x.name], nn.wanted_names(pending))
                # ...and the reconciliation only notes it.
                rec = rc.reconcile(v.folder, game, 1)
                self.assertFalse([f for f in rec.questions if x.name in f.text and f.topic in ("looks", "lost")],
                                 [f.text for f in rec.questions])

    def test_a_title_or_mask_change_alone_changes_nothing(self):
        for tag, game in CASES[:5]:
            with self.subTest(game=game):
                v = self.village(tag, game)
                data = v.save_path(1).read_bytes()
                people = v.people(data)
                x = people[0]
                title = {3: "Special villager: Tribal Chief", 5: "Special villager: Former Heathen (red mask)"}.get(
                    game, "Special villager: Esteemed Elder")
                history_text(v, [(T1, people), (T2, people)], {(T2, x.name): [title, "Mask: Red Mask"]})
                village = gen.load_village(v.folder, game, 1)
                self.assertFalse([q for q in village.identity_questions if x.name in (q.older[0], q.newer[0])])
                self.assertFalse([p for p in village.known() if p.name == x.name and not p.alive and not p.gone])


class UncertainIsAsked(Changed):
    """Only an Arrived record under the older looks, no History: nothing ties them for certain -- asked."""

    def test_asked_once_same_different_dont_know_and_a_changed_answer(self):
        for tag, game in CASES[:5]:
            with self.subTest(game=game):
                v, _old, _now, x, new_body = self.setup_game(tag, game)
                v.births(arrived(1, x, x.head, x.body))
                village = gen.load_village(v.folder, game, 1)
                asked = [q for q in village.identity_questions if q.newer[0] == x.name]
                self.assertEqual(len(asked), 1, [q.text for q in village.identity_questions])
                q = asked[0]
                self.assertEqual((q.older, q.newer), ((x.name, x.head, x.body), (x.name, x.head, new_body)))
                self.assertIn("never means a villager left", q.text)
                self.assertEqual(len(self.one_of(village, x.name)), 2, "unanswered: nothing joined on a guess")
                self.assertFalse([pid for pid in gen.duplicate_names(village)
                                  if village.people[pid].name == x.name], "...and no numeral while it is asked")
                # Same: one villager everywhere; not asked again.
                aq.keep_identity(v.folder, game, 1, q.older, q.newer, aq.SAME, q.text)
                village = gen.load_village(v.folder, game, 1)
                self.assertEqual(len(self.one_of(village, x.name)), 1)
                self.assertFalse([a for a in village.identity_questions if a.newer[0] == x.name])
                # Answered questions lists it, and a changed answer there takes effect: Different.
                rows = [r for r in aq.listing(v.folder, game, 1, []) if r.group == aq.IDENTITY_LABEL]
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0].options, aq.IDENTITY_OPTIONS)
                aq.change(v.folder, game, 1, {rows[0].ident: aq.DIFFERENT}, set())
                village = gen.load_village(v.folder, game, 1)
                self.assertEqual(len(self.one_of(village, x.name)), 2, "Different keeps them apart")
                self.assertFalse([a for a in village.identity_questions if a.newer[0] == x.name], "...and not asked")
                # Cleared (or Don't know): asked again.
                rows = [r for r in aq.listing(v.folder, game, 1, []) if r.group == aq.IDENTITY_LABEL]
                aq.change(v.folder, game, 1, {}, {rows[0].ident})
                village = gen.load_village(v.folder, game, 1)
                self.assertEqual(len([a for a in village.identity_questions if a.newer[0] == x.name]), 1)
                aq.keep_identity(v.folder, game, 1, q.older, q.newer, aq.SAME, q.text)
                aq.keep_identity(v.folder, game, 1, q.older, q.newer, None, q.text)     # Don't know
                village = gen.load_village(v.folder, game, 1)
                self.assertEqual(len([a for a in village.identity_questions if a.newer[0] == x.name]), 1)

    def test_different_keeps_them_apart_in_the_reconciliation_too(self):
        v, old, now, x, new_body = self.setup_game("huttest", 3)
        history_text(v, [(T1, v.people(old)), (T2, v.people(now))])
        self.assertFalse([f for f in rc.reconcile(v.folder, 3, 1).questions if x.name in f.text])
        aq.keep_identity(v.folder, 3, 1, (x.name, x.head, x.body), (x.name, x.head, new_body), aq.DIFFERENT, "?")
        rec = rc.reconcile(v.folder, 3, 1)
        self.assertTrue([f for f in rec.questions if f.topic == "lost" and x.name in f.text],
                        [f.text for f in rec.questions])
        self.assertEqual(len(self.one_of(gen.load_village(v.folder, 3, 1), x.name)), 2)

    def test_a_genuinely_older_namesake_is_never_joined(self):
        """A record older than the villager now (its age above theirs) is somebody else: never joined, never asked."""
        v, _old, _now, x, new_body = self.setup_game("huttest", 3)
        older = (x.age or 0) + 500
        v.births(f"Arrived 1\n  Name: {x.name}\n  Age at arrival: {older}\n  Sex: {x.sex}\n  Head: {x.head}\n"
                 f"  Body: {x.body}\n  How: Founder\n\n")
        history_text(v, [(T1, [rc.Seen(x.name, x.head, x.body, x.sex, older)])])
        village = gen.load_village(v.folder, 3, 1)
        self.assertEqual(len(self.one_of(village, x.name)), 2)
        self.assertFalse([q for q in village.identity_questions if q.newer[0] == x.name])


class NumbersALooksChangeGave(Changed):
    def numbered_village(self):
        """The Secret City: a new chief numbered "<name> II" by a Repair that took their older look for a
        namesake; the older look's records keep the plain name (numbering renames by name AND looks)."""
        v, old, now, x, new_body = self.setup_game("huttest", 3)
        numbered = f"{x.name} II"
        rank = [s.name for s in v.people(now)].index(x.name)
        now = v.renamed(now, rank, numbered)
        v.write_save(1, now)
        history_text(v, [(T1, v.people(old)), (T2, v.people(now))])
        v.log("Repairs Made", "Virtual Villagers 3 Repairs Log 1.txt",
              f"Repair 1\n  Date: 2026-10-21 12:00:00\n  Checked: villagers who share a full name\n"
              f"  Renamed: {x.name} (head {x.head}, body {new_body}) -> {numbered}\n\n")
        return v, x, new_body, numbered

    def test_found_with_the_evidence_and_taken_off_through_repair(self):
        import vv_log_tools as tools
        v, x, new_body, numbered = self.numbered_village()
        cases = nn.misnumbered_by_looks(v.folder, 3, 1)
        self.assertEqual([(c.name, c.base) for c in cases], [(numbered, x.name)])
        self.assertIn(f"head {x.head}, body {x.body}", cases[0].evidence())
        self.assertTrue(cases[0].renamed_lines)
        kind = nn.plan_unnumber(v.folder, 3, 1)
        self.assertEqual(list(kind.questions), [cases[0].key])
        self.assertEqual(kind.questions[cases[0].key].default, nn.KEEP_NUMBER, "never taken off unasked")
        tools.approve_repair(v.folder, 3, 1, processes=FakeProcesses(), chosen={nn.UNNUMBER_KIND},
                             answers={cases[0].key: nn.TAKE_OFF}, kinds=[kind], rearm=False)
        names = [s.name for s in v.people(v.save_path(1).read_bytes())]
        self.assertIn(x.name, names)
        self.assertNotIn(numbered, names)
        repairs = (v.folder / "Virtual Villagers Fun Patcher Logs" / "Save 1" / "Repairs Made"
                   / "Virtual Villagers 3 Repairs Log 1.txt").read_bytes().decode("latin-1")
        self.assertIn(f"Number taken off: {numbered} (head {x.head}, body {new_body}) -> {x.name}", repairs)
        self.assertIn("Evidence:", repairs)
        backups = [p for p in v.folder.parent.rglob("*") if p.is_dir() and "taking off numbers" in p.name]
        self.assertTrue(backups, "the save folder was backed up first")
        self.assertEqual(nn.misnumbered_by_looks(v.folder, 3, 1), [])
        village = gen.load_village(v.folder, 3, 1)
        self.assertEqual(len(self.one_of(village, x.name)), 1)

    def test_kept_when_the_answer_is_keep(self):
        import vv_log_tools as tools
        v, x, _new_body, numbered = self.numbered_village()
        kind = nn.plan_unnumber(v.folder, 3, 1)
        tools.approve_repair(v.folder, 3, 1, processes=FakeProcesses(), chosen={nn.UNNUMBER_KIND},
                             answers={}, kinds=[kind], rearm=False)
        self.assertIn(numbered, [s.name for s in v.people(v.save_path(1).read_bytes())])

    def test_a_genuine_namesake_keeps_the_number(self):
        v, x, new_body, numbered = self.numbered_village()
        other_sex = "Male" if x.sex == "Female" else "Female"
        v.deaths(f"Death 1\n  Name: {x.name}\n  Age at death: 1500\n  Sex: {other_sex}\n  Head: {(x.head + 3) % 20}\n"
                 f"  Body: {(x.body + 3) % 20}\n\n")
        self.assertEqual(nn.misnumbered_by_looks(v.folder, 3, 1), [])


class CodexReview602(Changed):
    def test_a_same_answer_settles_which_of_two_candidates_it_is(self):
        """Codex, #602: two new villagers of the name could be the one gone; the player's Same for one of them
        settles it (the other unanswered) -- never "lost", never tied to the other."""
        v, old, now, x, new_body = self.setup_game("huttest", 3)
        import dataclasses
        later = v.people(now)
        mine = next(s for s in later if s.name == x.name)
        twin = dataclasses.replace(mine, head=(x.head + 5) % 20, body=(x.body + 9) % 20)
        history_text(v, [(T1, v.people(old)), (T2, later + [twin])])
        aq.keep_identity(v.folder, 3, 1, (x.name, x.head, x.body), (x.name, x.head, new_body), aq.SAME, "?")
        rec = rc.reconcile(v.folder, 3, 1)
        old_key = str((x.name, x.head, x.body))
        self.assertFalse([f for f in rec.questions if old_key in f.qid], [f.text for f in rec.questions])
        looks = [f for f in rec.notes if f.topic == "looks" and old_key in f.qid]
        self.assertEqual(len(looks), 1)
        self.assertIn(f"body {new_body}", looks[0].text)

    def test_an_expecting_mothers_conception_follows_her_change_of_looks(self):
        """Codex, #602: joining an older look moves what is kept under it -- her Conception (the father, the
        babies) -- so her baby on the way keeps its father."""
        reg = gen._Registry()
        older = reg.get("Mama", 22, 13)
        now = reg.get("Mama", 22, 29)
        now.alive = True
        reg.conceptions[older.key] = (("Taro", 18, 12), 2)
        reg.lost.append((older.key, 1))
        gen._merge_into(reg, older, now)
        self.assertEqual(reg.conceptions.get(now.key), (("Taro", 18, 12), 2))
        self.assertNotIn(older.key, reg.conceptions)
        self.assertEqual(reg.lost, [(now.key, 1)])
        now.expecting = True
        gen._upcoming(reg)
        babies = [p for p in reg.people.values() if p.upcoming]
        self.assertEqual(len(babies), 2)
        self.assertTrue(all(reg.people[b.father].name == "Taro" and b.mother == now.id for b in babies))

class GenuineNamesakesAreStillNumbered(Changed):
    def test_two_living_villagers_of_one_name_are_still_numbered_in_every_game(self):
        for tag, game in CASES[:5]:
            with self.subTest(game=game):
                v = self.village(tag, game)
                data = v.save_path(1).read_bytes()
                people = v.people(data)
                names = [s.name for s in people]
                a = next(k for k, s in enumerate(people) if names.count(s.name) == 1)
                b = next(k for k, s in enumerate(people) if k != a and names.count(s.name) == 1
                         and (s.head, s.body) != (people[a].head, people[a].body))
                v.write_save(1, v.renamed(data, b, people[a].name))
                village = gen.load_village(v.folder, game, 1)
                numbered = {village.people[pid].key: n for pid, n in gen.duplicate_names(village).items()}
                mine = {k: n for k, n in numbered.items() if k[0] == people[a].name}
                self.assertEqual(sorted(mine.values()), [f"{people[a].name} I", f"{people[a].name} II"], numbered)
                pending = nn.wanted_names(nn.pending(v.folder, game, 1))
                self.assertEqual(len([k for k in pending if k[0] == people[a].name]), 2, pending)


class TreeWindowAsks(Changed):
    def test_the_batch_window_lists_every_question_and_keeps_the_answers(self):
        try:
            import tkinter as tk
            root = tk.Tk()
        except Exception as exc:                         # pragma: no cover - no display
            self.skipTest(f"no Tk: {exc}")
        root.withdraw()
        self.addCleanup(root.destroy)
        import vv_genealogy_window as gw
        v, _old, _now, x, new_body = self.setup_game("huttest", 3)
        v.births(arrived(1, x, x.head, x.body))
        village = gen.load_village(v.folder, 3, 1)
        self.assertTrue(village.identity_questions)

        class Editor(tk.Toplevel):
            pass
        editor = Editor(root)
        editor.withdraw()
        editor.folder, editor.game, editor.slot = v.folder, 3, 1
        editor.village = editor.full_village = village
        editor.edits, editor.present = None, {}
        reloaded = []
        editor._update_from_game = lambda ask=True: reloaded.append(ask)
        window = gw.ask_identities(editor, village.identity_questions)
        self.assertIsNotNone(window)
        self.assertFalse(window.grab_current(), "never modal: the tree stays usable")
        radios = [w for w in _all(window) if isinstance(w, gw.ttk.Radiobutton) and w.cget("text") == aq.SAME]
        self.assertEqual(len(radios), len(village.identity_questions))
        for r in radios:
            r.invoke()
        save = next(w for w in _all(window) if isinstance(w, gw.ttk.Button) and w.cget("text") == "Save answers")
        save.invoke()
        self.assertEqual(reloaded, [False])
        self.assertFalse([q for q in gen.load_village(v.folder, 3, 1).identity_questions if q.newer[0] == x.name])


def _all(widget):
    out = [widget]
    for child in widget.winfo_children():
        out += _all(child)
    return out


if __name__ == "__main__":
    unittest.main()
