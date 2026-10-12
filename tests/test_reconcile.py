"""The always-on read-only reconciliation of records, logs and files (src/vv_reconcile.py), all five
games and the 256 Villagers builds.

The owner (2026-10-11): "Iruwa Okelani" (Birth 252, head 12, body 18) became a second living "Tiki
Alosaka" with no record, and she never renamed anyone; a checker that called that "renamed since
birth: OK" hid it.  "FOR ALL 5 GAMES: THE PATCHER SHOULD ALWAYS DO A READ-ONLY RECONCILIATION OF
RECORDS, LOGS, AND FILES TO MAKE SURE ABSOLUTELY NOTHING IS LOST. IF THERE ARE CONTRADICTIONS ASK THE
PLAYER." -- and, at her village's 256 cap, record slots are reused: never a contradiction.

Every village here is built from the repository's own fixture saves (every game, and The Secret City
to New Believers' 256 Villagers builds at 254-255 villagers) or, for A New Home at the full 256, from
the save's own record layout.
"""
from __future__ import annotations

import gzip
import hashlib
import os
import struct
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_last_names as ln  # noqa: E402
import vv_log_tools as tools  # noqa: E402
import vv_reconcile as rc  # noqa: E402
import vv_tribe_rename as rename  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "rename_tribe"
LOGS = "Virtual Villagers Fun Patcher Logs"
DATA = "Virtual Villagers Fun Patcher Data"
CASES = [("huttest", 1), ("huttest", 2), ("huttest", 3), ("huttest", 4), ("huttest", 5),
         ("256", 3), ("256", 4), ("256", 5)]


def fixture(name: str) -> bytes:
    return gzip.decompress((FIXTURES / f"{name}.ldw.gz").read_bytes())


class FakeProcesses:
    def find(self, exe_name):
        return []

    def suspend(self, pid, exe_name):  # pragma: no cover
        raise AssertionError("never paused")

    def resume(self, handle):  # pragma: no cover
        raise AssertionError("never paused")


def vv1_save(villagers) -> bytes:
    """An A New Home save of `villagers` (name, male, head, body, age) in record order: the records the
    game loads from +0x184, 0x9C apart, each flagged at +0x3D4, likes and dislikes empty (-1)."""
    data = bytearray(0x184 + 256 * 0x9C)
    for i, (name, male, head, body, age) in enumerate(villagers):
        base = 0x184 + i * 0x9C - 0x33C
        struct.pack_into("<i", data, base + 0x344, 90)
        struct.pack_into("<i", data, base + 0x348, age)
        struct.pack_into("<i", data, base + 0x350, 1 if male else 2)
        struct.pack_into("<i", data, base + 0x360, head)
        struct.pack_into("<i", data, base + 0x364, body)
        struct.pack_into("<8i", data, base + 0x398, *([-1] * 8))
        data[base + 0x3D4] = 1
        data[base + 0x370:base + 0x370 + len(name)] = name.encode()
    return bytes(data)


class Village:
    """A save folder for one game's Save 1, and the logs written beside it."""

    def __init__(self, root: Path, game: int, data: bytes):
        self.game = game
        saves = rename.GAMES[game - 1]
        self.folder = root / "LDW" / f"{saves.title} - Test"
        self.folder.mkdir(parents=True)
        self.stem = tools.load_checker().SAVE_STEMS[game]
        self.write_save(1, data)
        try:
            name = rename.save_name(saves, data)
        except (ValueError, KeyError):
            name = ""
        self.header = rename.village_header(name, 1) if name else "Village: Test Tribe (Save 1)"
        self.f = ln.FIELDS[game]
        self.age_at = -0x28 if game == 1 else tools.load_checker().LAYOUTS[game].age

    # -- the save ----------------------------------------------------------------------------------
    def save_path(self, n: int) -> Path:
        return self.folder / f"{self.stem}{n}.ldw"

    def write_save(self, n: int, data: bytes, when: float | None = None) -> None:
        path = self.save_path(n)
        path.write_bytes(data)
        if when is not None:
            os.utime(path, (when, when))

    def entries(self, data: bytes) -> list[int]:
        return ln._entries(self.game, data)

    def renamed(self, data: bytes, rank: int, name: str) -> bytes:
        buf = bytearray(data)
        at = self.entries(data)[rank]
        buf[at:at + self.f.name_cap] = name.encode() + b"\0" * (self.f.name_cap - len(name))
        return bytes(buf)

    def relooked(self, data: bytes, rank: int, head: int, body: int) -> bytes:
        buf = bytearray(data)
        at = self.entries(data)[rank]
        struct.pack_into("<i", buf, at + self.f.head, head)
        struct.pack_into("<i", buf, at + self.f.body, body)
        return bytes(buf)

    def aged(self, data: bytes, by: int) -> bytes:
        buf = bytearray(data)
        for at in self.entries(data):
            age = struct.unpack_from("<i", buf, at + self.age_at)[0]
            struct.pack_into("<i", buf, at + self.age_at, age + by)
        return bytes(buf)

    def people(self, data: bytes) -> list[rc.Seen]:
        path = self.folder / "probe.ldw"
        path.write_bytes(data)
        try:
            return rc.read_save(path, self.game)[0]
        finally:
            path.unlink()

    # -- the logs ----------------------------------------------------------------------------------
    def log(self, sub: str, name: str, text: str, newline: bool = True) -> Path:
        path = self.folder / LOGS / "Save 1" / sub / name
        path.parent.mkdir(parents=True, exist_ok=True)
        body = f"{self.header}\n{text}"
        if not newline:
            body = body.rstrip("\n")
        path.write_bytes(body.replace("\n", "\r\n").encode("latin-1"))
        return path

    def history(self, snapshots: list[tuple[str, list[rc.Seen]]]) -> None:
        out = []
        for date, people in snapshots:
            out.append(f"=== Virtual Villagers {self.game} -- {date} ===\n{self.header}\n")
            for k, s in enumerate(people, 1):
                out.append(f"Villager {k}\n  Name: {s.name}\n  Age: {s.age}\n  Sex: {s.sex}\n  Head: {s.head}\n"
                           f"  Body: {s.body}\n  Likes: {words(s.likes)}\n  Dislikes: {words(s.dislikes)}\n")
        path = self.folder / LOGS / "Save 1" / "Tribe History" / "Village History 1.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes("\n".join(out).replace("\n", "\r\n").encode("latin-1"))

    def birth(self, number: int, s: rc.Seen, name: str | None = None) -> str:
        mother = f"  Mother: {s.mother}\n    Head: 1\n    Body: 1\n" if s.mother else "  Mother: (unknown)\n"
        father = f"  Father: {s.father}\n    Head: 2\n    Body: 2\n" if s.father else "  Father: (unknown)\n"
        return (f"Birth {number}\n  Child: {name or s.name}\n    Sex: {s.sex}\n    Head: {s.head}\n    Body: {s.body}\n"
                f"    Likes: {words(s.likes)}\n    Dislikes: {words(s.dislikes)}\n{mother}{father}\n")

    def births(self, text: str) -> Path:
        return self.log("Births and Conceptions", f"Virtual Villagers {self.game} Births and Conceptions Log 1.txt", text)

    def deaths(self, text: str, newline: bool = True) -> Path:
        return self.log("Deaths and Disappearances", f"Virtual Villagers {self.game} Deaths Log 1.txt", text, newline)

    def state(self) -> dict:
        return {str(p.relative_to(self.folder)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(self.folder.rglob("*")) if p.is_file()}


def words(values) -> str:
    return ", ".join(sorted(values)) if values else "(none)"


def aged(s: rc.Seen, by: int, **change) -> rc.Seen:
    out = rc.Seen(**{**s.__dict__})
    out.age = (s.age or 0) + by
    for k, v in change.items():
        setattr(out, k, v)
    return out


def death(number: int, name: str, head: int, body: int, sex: str = "Male", age: int = 900) -> str:
    return f"Death {number}\n  Name: {name}\n  Age at death: {age}\n  Sex: {sex}\n  Head: {head}\n  Body: {body}\n\n"


class Base(unittest.TestCase):
    def village(self, tag: str, game: int, data: bytes | None = None) -> Village:
        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        return Village(root, game, data if data is not None else fixture(f"vv{game}-{tag}-1"))

    def topics(self, rec: rc.Reconciliation) -> list[str]:
        return [f.topic for f in rec.questions]


class NameChanges(Base):
    def test_a_name_changed_with_no_record_is_asked_in_every_game(self):
        """The owner's case in every game: the Birth record and an earlier History snapshot say one name,
        the save another, nobody alive carries the first with those looks: a question, never accepted."""
        for tag, game in CASES:
            with self.subTest(game=game, tag=tag):
                v = self.village(tag, game)
                original = v.save_path(1).read_bytes()
                people = v.people(original)
                x = people[1]
                now = v.renamed(original, 1, "Zuri")
                v.write_save(1, now)
                later = v.people(now)
                v.history([("2026-10-11 20:00:00", [aged(s, -5) for s in people]),
                           ("2026-10-11 21:00:00", later)])
                v.births(v.birth(252, x))
                before = v.state()
                rec = rc.reconcile(v.folder, game, 1)
                self.assertEqual(v.state(), before, "the reconciliation never writes")
                asked = [f for f in rec.questions if f.topic == "rename"]
                self.assertEqual(len(asked), 1, [f.text for f in rec.questions])
                # The Birth record leads -- unless a look-alike with the same parents is alive too (the 256
                # builds' fixtures hold copies of one villager), when the Birth record cannot say which of
                # them it is and the History snapshots' own words are the question.
                twins = [s for s in later if (s.head, s.body, s.father, s.mother) == (x.head, x.body, x.father, x.mother)]
                if len(twins) == 1:
                    self.assertTrue(asked[0].text.startswith(f"Birth 252 says {x.name}; the save "), asked[0].text)
                self.assertIn(f"says {x.name}; ", asked[0].text)
                self.assertIn("says Zuri", asked[0].text)
                self.assertIn("No log records a rename. Which is right?", asked[0].text)
                self.assertIn(f"{x.name} is right (give the name back)", asked[0].options)
                self.assertEqual(asked[0].rename, (("Zuri", x.head, x.body), x.name))
                # Nobody else is asked about: the rest of the village followed through by identity.
                self.assertEqual([f.topic for f in rec.questions], ["rename"], [f.text for f in rec.questions])

    def test_a_last_name_given_is_a_note_not_a_question(self):
        for tag, game in CASES[:5]:
            with self.subTest(game=game):
                v = self.village(tag, game)
                original = v.save_path(1).read_bytes()
                people = v.people(original)
                x = people[0]
                given = f"{x.name} Kai"[:ln.ROOM[game]]
                now = v.renamed(original, 0, given)
                v.write_save(1, now)
                v.history([("2026-10-11 20:00:00", people), ("2026-10-11 21:00:00", v.people(now))])
                rec = rc.reconcile(v.folder, game, 1)
                self.assertEqual(rec.questions, [], [f.text for f in rec.questions])
                self.assertTrue(any(f.topic == "name" for f in rec.notes), [f.text for f in rec.notes])

    def test_a_name_changed_record_is_still_asked(self):
        """A New Home's parentage companion records every name that changes in play ("Name changed"):
        recorded, never hidden -- and the player is still asked whether it was theirs."""
        v = self.village("huttest", 1)
        original = v.save_path(1).read_bytes()
        x = v.people(original)[2]
        v.write_save(1, v.renamed(original, 2, "Zuri"))
        v.births(f"Name changed\n  Name: Zuri\n  Old name: {x.name}\n  Age: {x.age}\n  Head: {x.head}\n"
                 f"  Body: {x.body}\n  Likes: (none)\n  Dislikes: (none)\n\n")
        rec = rc.reconcile(v.folder, 1, 1)
        asked = [f for f in rec.questions if f.topic == "rename"]
        self.assertEqual(len(asked), 1, [f.text for f in rec.questions])
        self.assertIn("A \"Name changed\" record", asked[0].text)
        self.assertIn("did you rename this villager?", asked[0].text)

    def test_an_answer_is_remembered_and_turns_the_question_into_a_note(self):
        v = self.village("huttest", 3)
        original = v.save_path(1).read_bytes()
        x = v.people(original)[1]
        v.write_save(1, v.renamed(original, 1, "Zuri"))
        v.births(v.birth(7, x))
        kind = rc.kind(v.folder, 3, 1)
        (qid, question), = kind.questions.items()
        self.assertEqual(question.default, rc.DONT_KNOW)
        # "Don't know" changes nothing and is asked again.
        self.assertEqual(rc.remember(v.folder, 3, 1, [kind], {qid: rc.DONT_KNOW}), ([], {}))
        self.assertEqual(len(rc.reconcile(v.folder, 3, 1).questions), 1)
        keep = question.options[0]
        lines, renames = rc.remember(v.folder, 3, 1, [kind], {qid: keep})
        self.assertEqual(renames, {})
        self.assertEqual(len(lines), 1)
        rec = rc.reconcile(v.folder, 3, 1)
        self.assertEqual(rec.questions, [])
        self.assertTrue(any(f.answer == keep for f in rec.notes))

    def test_give_the_name_back_renames_only_with_the_answer(self):
        for game in (1, 2, 5):
            with self.subTest(game=game):
                v = self.village("huttest", game)
                original = v.save_path(1).read_bytes()
                x = v.people(original)[1]
                v.write_save(1, v.renamed(original, 1, "Zuri"))
                v.births(v.birth(9, x))
                kind = rc.kind(v.folder, game, 1)
                (qid, question), = kind.questions.items()
                back = next(o for o in question.options if o.endswith("(give the name back)"))
                _lines, renames = rc.remember(v.folder, game, 1, [kind], {qid: back})
                self.assertEqual(renames, {("Zuri", x.head, x.body): x.name})
                done = rc.give_names_back(v.folder, game, 1, renames, FakeProcesses())
                self.assertEqual(done, renames)
                self.assertEqual(v.people(v.save_path(1).read_bytes())[1].name, x.name)
                self.assertEqual(rc.reconcile(v.folder, game, 1).questions, [])

    def test_a_failed_give_back_keeps_no_answer_so_it_can_be_retried(self):
        """Review (#585): the answer was kept before the rename ran, so a rename that failed (a file
        locked or changed) left the wrong name with its question already turned into an answered note."""
        v = self.village("huttest", 3)
        original = v.save_path(1).read_bytes()
        x = v.people(original)[1]
        v.write_save(1, v.renamed(original, 1, "Zuri"))
        v.births(v.birth(9, x))
        kind = rc.kind(v.folder, 3, 1)
        (qid, question), = kind.questions.items()
        back = next(o for o in question.options if o.endswith("(give the name back)"))

        def fails(wanted):
            raise tools.LogToolError("the save is locked")

        with self.assertRaises(tools.LogToolError):
            rc.remember(v.folder, 3, 1, [kind], {qid: back}, give_back=fails)
        self.assertEqual(len(rc.reconcile(v.folder, 3, 1).questions), 1, "still asked: it can be retried")
        # Once the rename succeeds, the answer is kept and the question becomes a note.
        lines, renamed = rc.remember(v.folder, 3, 1, [kind], {qid: back},
                                     give_back=lambda wanted: rc.give_names_back(v.folder, 3, 1, wanted,
                                                                                 FakeProcesses()))
        self.assertEqual(renamed, {("Zuri", x.head, x.body): x.name})
        self.assertEqual(len(lines), 1)
        self.assertEqual(v.people(v.save_path(1).read_bytes())[1].name, x.name)
        self.assertEqual(rc.reconcile(v.folder, 3, 1).questions, [])


class Losses(Base):
    def test_a_villager_gone_with_no_record_is_possibly_lost(self):
        for tag, game in CASES:
            with self.subTest(game=game, tag=tag):
                v = self.village(tag, game)
                people = v.people(v.save_path(1).read_bytes())
                ghost = rc.Seen("Ghosty", 1, 2, "Male", 300, frozenset(), frozenset())
                gone = rc.Seen("Departa", 2, 1, "Female", 800, frozenset(), frozenset())
                v.history([("2026-10-11 20:00:00", people + [ghost, gone]), ("2026-10-11 21:00:00", people)])
                v.deaths(death(1, "Departa", 2, 1, "Female", 810))
                rec = rc.reconcile(v.folder, game, 1)
                lost = [f for f in rec.questions if f.topic == "lost"]
                self.assertEqual(len(lost), 1, [f.text for f in rec.questions])
                self.assertIn("Ghosty", lost[0].text)
                self.assertIn("possibly lost", lost[0].text)
                self.assertFalse(any("Departa" in f.text for f in rec.questions))

    def test_many_gone_at_once_is_one_question_naming_each(self):
        v = self.village("huttest", 2)
        people = v.people(v.save_path(1).read_bytes())
        ghosts = [rc.Seen(f"Ghost{k}", k, k + 1, "Male", 300 + k, frozenset(), frozenset()) for k in range(6)]
        v.history([("2026-10-11 20:00:00", people + ghosts), ("2026-10-11 21:00:00", people)])
        rec = rc.reconcile(v.folder, 2, 1)
        self.assertEqual(self.topics(rec), ["lost"], [f.text for f in rec.questions])
        for g in ghosts:
            self.assertIn(g.name, rec.questions[0].text)

    def test_an_island_event_rename_is_a_note(self):
        v = self.village("huttest", 4)
        original = v.save_path(1).read_bytes()
        people = v.people(original)
        x = people[0]
        now = v.renamed(original, 0, "Zuri")
        v.write_save(1, now)
        v.history([("2026-10-11 20:00:00", people), ("2026-10-11 21:00:00", v.people(now))])
        v.log("Island Events", "Virtual Villagers 4 Island Events Log 1.txt",
              f"Island event 1\n  Name: {x.name} -> Zuri\n  Event: A Custom Island Event\n\n")
        rec = rc.reconcile(v.folder, 4, 1)
        self.assertEqual(rec.questions, [], [f.text for f in rec.questions])
        self.assertTrue(any("an island event renamed them" in f.text for f in rec.notes))

    def test_looks_changed_with_no_record_are_asked_and_a_recorded_change_is_not(self):
        for game in (1, 3):
            with self.subTest(game=game):
                v = self.village("huttest", game)
                original = v.save_path(1).read_bytes()
                people = v.people(original)
                x = people[0]
                now = v.relooked(original, 0, (x.head + 1) % 20, x.body)
                v.write_save(1, now)
                v.history([("2026-10-11 20:00:00", people), ("2026-10-11 21:00:00", v.people(now))])
                self.assertEqual([f.topic for f in rc.reconcile(v.folder, game, 1).questions], ["looks"])
                v.births(f"Appearance changed\n  Name: {x.name}\n  Old head: {x.head}\n  Old body: {x.body}\n"
                         f"  New head: {(x.head + 1) % 20}\n  New body: {x.body}\n\n")
                self.assertEqual(rc.reconcile(v.folder, game, 1).questions, [])

    def test_a_village_gone_back_in_time_is_one_question(self):
        v = self.village("huttest", 5)
        people = v.people(v.save_path(1).read_bytes())
        v.history([("2026-10-11 20:00:00", [aged(s, 100) for s in people]), ("2026-10-11 21:00:00", people)])
        rec = rc.reconcile(v.folder, 5, 1)
        self.assertEqual(self.topics(rec), ["age"], [f.text for f in rec.questions])
        self.assertIn("went back in time", rec.questions[0].text)


class ChangesBetweenCopies(Base):
    """Review of #585: likes and dislikes, parents and looks between two looks at one villager."""

    def with_prefs(self, v: Village, data: bytes, rank: int, likes: list[int], dislikes: list[int]) -> bytes:
        buf = bytearray(data)
        at = v.entries(data)[rank]
        struct.pack_into(f"<{v.f.slots}i", buf, at + v.f.likes, *(likes + [-1] * v.f.slots)[:v.f.slots])
        struct.pack_into(f"<{v.f.slots}i", buf, at + v.f.dislikes, *(dislikes + [-1] * v.f.slots)[:v.f.slots])
        return bytes(buf)

    def with_father(self, v: Village, data: bytes, rank: int, name: str) -> bytes:
        buf = bytearray(data)
        at = v.entries(data)[rank]
        cap = v.f.parent_cap
        buf[at + v.f.father:at + v.f.father + cap] = name.encode() + b"\0" * (cap - len(name))
        return bytes(buf)

    def two_generations(self, v: Village, older: bytes, current: bytes) -> None:
        now = time.time()
        v.write_save(21, older, now - 600)
        v.write_save(1, current, now)

    def test_a_like_lost_or_gained_between_save_copies_is_asked(self):
        for tag, game in CASES[:5]:
            with self.subTest(game=game):
                v = self.village(tag, game)
                data = v.save_path(1).read_bytes()
                two = self.with_prefs(v, data, 0, [0, 1], [2])
                one = self.with_prefs(v, data, 0, [0], [2])
                self.two_generations(v, two, one)                  # a like lost
                asked = [f for f in rc.reconcile(v.folder, game, 1).questions if f.topic == "likes"]
                self.assertEqual(len(asked), 1, [f.text for f in rc.reconcile(v.folder, game, 1).questions])
                self.two_generations(v, one, self.with_prefs(v, data, 0, [0], [2, 3]))   # a dislike gained
                asked = [f for f in rc.reconcile(v.folder, game, 1).questions if f.topic == "dislikes"]
                self.assertEqual(len(asked), 1)
                self.two_generations(v, two, two)                  # unchanged: nothing
                self.assertFalse([f for f in rc.reconcile(v.folder, game, 1).questions
                                  if f.topic in ("likes", "dislikes")])

    def test_a_one_word_snapshot_is_a_note_about_the_snapshot(self):
        """The History writer listed only the first like before 2026-10-11 20:19 (the owner's A New Home
        village): one word then and two now is that snapshot's omission, not a change -- one note."""
        v = self.village("huttest", 1)
        people = v.people(v.save_path(1).read_bytes())
        full = [rc.Seen(**{**s.__dict__, "likes": frozenset({"fish", "herbs"}),
                           "dislikes": frozenset({"rain"})}) for s in people]
        short = [rc.Seen(**{**s.__dict__, "likes": frozenset({"fish"}), "dislikes": frozenset({"rain"})})
                 for s in people]
        v.history([("2026-10-10 12:50:39", short), ("2026-10-11 20:19:48", full)])
        # (The latest snapshot against the save is a separate comparison; only snapshot to snapshot here.)
        rec = rc.reconcile(v.folder, 1, 1)
        self.assertFalse([f for f in rec.questions if f.topic == "likes" and f.qid.endswith("2026-10-10 12:50:39")],
                         [f.text for f in rec.questions])
        notes = [f for f in rec.notes if f.topic == "one-word"]
        self.assertEqual(len(notes), 1, "one note for the snapshot, none per villager")
        self.assertIn("2026-10-10 12:50:39", notes[0].text)
        # The same omission between two full-list snapshots is a lost like: asked, for every villager.
        v.history([("2026-10-11 20:30:00", full), ("2026-10-11 21:00:00", short)])
        lost = [f for f in rc.reconcile(v.folder, 1, 1).questions
                if f.topic == "likes" and f.qid.endswith("2026-10-11 20:30:00")]
        self.assertEqual(len(lost), len(people))

    def test_a_known_parent_becoming_blank_or_another_is_asked(self):
        for game in (2, 3, 4, 5):
            with self.subTest(game=game):
                v = self.village("huttest", game)
                data = v.save_path(1).read_bytes()
                known = self.with_father(v, data, 0, "Kalani")
                self.two_generations(v, known, self.with_father(v, data, 0, ""))
                asked = [f for f in rc.reconcile(v.folder, game, 1).questions if f.topic == "parents"]
                self.assertEqual(len(asked), 1, [f.text for f in rc.reconcile(v.folder, game, 1).questions])
                self.assertIn("father Kalani", asked[0].text)
                self.assertIn("none in", asked[0].text)
                self.two_generations(v, known, self.with_father(v, data, 0, "Makoa"))
                asked = [f for f in rc.reconcile(v.folder, game, 1).questions if f.topic == "parents"]
                self.assertEqual(len(asked), 1)
                self.assertIn("Makoa", asked[0].text)
                # A blank becoming known is a parent recorded later, not a loss.
                self.two_generations(v, self.with_father(v, data, 0, ""), known)
                self.assertFalse([f for f in rc.reconcile(v.folder, game, 1).questions if f.topic == "parents"])

    def test_an_island_event_explains_only_the_change_it_records(self):
        for game in (1, 4):
            with self.subTest(game=game):
                v = self.village("huttest", game)
                original = v.save_path(1).read_bytes()
                people = v.people(original)
                x = people[0]
                head2 = (x.head + 1) % 20
                body2 = (x.body + 1) % 20
                events = v.log("Island Events", f"Virtual Villagers {game} Island Events Log 1.txt",
                               f"Island event 1\n  Name: {x.name}\n  Head: {x.head} -> {head2}\n\n")
                # Exactly the recorded change: nothing asked.
                now = v.relooked(original, 0, head2, x.body)
                v.write_save(1, now)
                v.history([("2026-10-11 20:30:00", people), ("2026-10-11 21:00:00", v.people(now))])
                self.assertFalse([f for f in rc.reconcile(v.folder, game, 1).questions if f.topic == "looks"])
                # The head as recorded AND a body nobody recorded: asked.
                now = v.relooked(original, 0, head2, body2)
                v.write_save(1, now)
                v.history([("2026-10-11 20:30:00", people), ("2026-10-11 21:00:00", v.people(now))])
                self.assertEqual(len([f for f in rc.reconcile(v.folder, game, 1).questions
                                      if f.topic == "looks"]), 1)
                # A head other than the one recorded: asked.
                now = v.relooked(original, 0, (x.head + 2) % 20, x.body)
                v.write_save(1, now)
                v.history([("2026-10-11 20:30:00", people), ("2026-10-11 21:00:00", v.people(now))])
                self.assertEqual(len([f for f in rc.reconcile(v.folder, game, 1).questions
                                      if f.topic == "looks"]), 1)
                events.unlink()


class SlotReuseAtTheCap(Base):
    """Record slots are reused at max population: a death frees one, the next birth takes it, a load
    packs the records.  Never a contradiction: villagers are followed by who they are."""

    def check_reuse(self, v: Village, data: bytes, k: int) -> None:
        people = v.people(data)
        x = people[k]
        f = v.f
        old = v.relooked(v.renamed(data, k, "Goneone"), k, (x.head + 3) % 20, (x.body + 3) % 20)
        now = time.time()
        v.write_save(21, old, now - 600)                  # the game's older generation of Save 1
        v.write_save(1, data, now)
        dead = v.people(old)[k]
        v.deaths(death(1, dead.name, dead.head, dead.body, dead.sex or "Male"))
        v.births(v.birth(300, x))                         # the newborn in the freed slot
        rec = rc.reconcile(v.folder, v.game, 1)
        self.assertEqual(rec.questions, [], [q.text for q in rec.questions])
        self.assertTrue(any(n.topic == "slots" for n in rec.notes), [n.text for n in rec.notes])
        del f

    def test_slot_reuse_in_every_game_and_the_256_builds(self):
        for tag, game in CASES:
            with self.subTest(game=game, tag=tag):
                v = self.village(tag, game)
                self.check_reuse(v, v.save_path(1).read_bytes(), 3)

    def test_a_new_home_at_256(self):
        villagers = [(f"Vil{i:03d}", i % 2 == 0, i % 20, (i * 7) % 20, 400 + i) for i in range(256)]
        data = vv1_save(villagers)
        v = self.village("", 1, data)
        self.assertEqual(len(v.people(data)), 256)
        self.check_reuse(v, data, 200)

    def test_a_packed_save_is_no_question(self):
        """A load packs the records after deaths: everyone after the dead moves down one slot."""
        villagers = [(f"Vil{i:03d}", i % 2 == 0, i % 20, (i * 7) % 20, 400 + i) for i in range(256)]
        older = vv1_save(villagers)
        newer = vv1_save(villagers[:10] + villagers[11:])
        v = self.village("", 1, newer)
        now = time.time()
        v.write_save(21, older, now - 600)
        v.write_save(1, newer, now)
        v.deaths(death(1, "Vil010", 10, 70 % 20, "Male", 900))
        rec = rc.reconcile(v.folder, 1, 1)
        self.assertEqual(rec.questions, [], [q.text for q in rec.questions])
        self.assertTrue(any(n.topic == "slots" and "245 villager(s) are in another slot" in n.text
                            for n in rec.notes), [n.text for n in rec.notes])


class FileLevelLoss(Base):
    def test_the_save_older_than_its_previous_generation(self):
        for tag, game in CASES:
            with self.subTest(game=game, tag=tag):
                v = self.village(tag, game)
                data = v.save_path(1).read_bytes()
                now = time.time()
                v.write_save(21, v.aged(data, 60), now - 600)
                v.write_save(1, data, now)
                rec = rc.reconcile(v.folder, game, 1)
                self.assertTrue(any(f.topic == "file" and "older than the game's earlier copy" in f.text
                                    for f in rec.questions), [f.text for f in rec.questions])

    def test_a_restored_save_with_its_old_time_is_still_the_current_save(self):
        """Review (#585): the generations were ordered by time alone, so a save restored from an older copy
        WITH ITS TIME KEPT (as the patcher's backups keep it) sorted before the game's newer generation,
        was compared as an old copy, and the checks of the current save ran on no villagers."""
        for tag, game in CASES:
            with self.subTest(game=game, tag=tag):
                v = self.village(tag, game)
                data = v.save_path(1).read_bytes()
                x = v.people(data)[1]
                restored = v.renamed(data, 1, "Zuri")
                now = time.time()
                v.write_save(21, v.aged(data, 60), now)
                v.write_save(1, restored, now - 600)
                v.births(v.birth(9, x))
                self.assertEqual(rc.save_generations(v.folder, game, 1)[-1], v.save_path(1))
                rec = rc.reconcile(v.folder, game, 1)
                texts = [f.text for f in rec.questions]
                self.assertTrue(any(f.topic == "file" and "older than the game's earlier copy" in f.text
                                    for f in rec.questions), texts)
                # The Birth record is checked against the CURRENT save's villagers (none, before the fix) --
                # where it can tell who it is: the 256 builds' fixtures hold look-alikes of one villager.
                people = v.people(restored)
                twins = [s for s in people if (s.head, s.body, s.father, s.mother) == (x.head, x.body, x.father, x.mother)]
                if len(twins) == 1:
                    self.assertTrue(any(f.topic == "rename" and "says Zuri" in f.text for f in rec.questions), texts)

    def test_a_log_shrunk_below_its_copy_a_missing_file_and_a_cut_record(self):
        for tag, game in CASES[:5]:
            with self.subTest(game=game):
                v = self.village(tag, game)
                x = v.people(v.save_path(1).read_bytes())[0]
                path = v.births(v.birth(1, x))
                copy = path.with_name(path.name + ".before-v1.35.69-repair")
                copy.write_bytes(path.read_bytes() + "\r\n".join(
                    v.birth(n, x, f"Lostchild{n}") for n in (2, 3)).replace("\n", "\r\n").encode("latin-1"))
                titles = v.folder / DATA / "Custom Titles"
                titles.mkdir(parents=True)
                (titles / "Custom Titles - Save 1.dat.before-v1.35.60-repair").write_bytes(b"VCT1")
                v.deaths(death(1, "Somebody", 1, 1), newline=False)
                rec = rc.reconcile(v.folder, game, 1)
                texts = [f.text for f in rec.questions if f.topic == "file"]
                self.assertTrue(any("holds 1 record(s), but the copy" in t and "2 record(s) may be lost" in t
                                    for t in texts), texts)
                self.assertTrue(any(t.startswith("Custom Titles - Save 1.dat is missing") for t in texts), texts)
                self.assertTrue(any("ends in the middle of a line" in t for t in texts), texts)

    def test_a_repair_that_took_records_out_is_a_note(self):
        v = self.village("huttest", 2)
        x = v.people(v.save_path(1).read_bytes())[0]
        path = v.births(v.birth(1, x))
        copy = path.with_name(path.name + ".before-v1.35.69-repair")
        copy.write_bytes(path.read_bytes() + v.birth(2, x, "Dupe").replace("\n", "\r\n").encode("latin-1"))
        v.log("Repairs Made", "Virtual Villagers 2 Repairs Log 1.txt",
              "Repair 1\n  Date: 2026-10-11 20:06:21\n  Duplicate backfilled Arrived record removed: "
              f"{LOGS}\\Births and Conceptions\\{path.name} -- 1 villager(s)\n\n")
        rec = rc.reconcile(v.folder, 2, 1)
        self.assertFalse(any(f.topic == "file" for f in rec.questions), [f.text for f in rec.questions])
        self.assertTrue(any("the Repairs log says repairs took 1 out" in f.text for f in rec.notes))

    def test_a_custom_title_the_file_no_longer_holds(self):
        v = self.village("huttest", 4)
        people = v.people(v.save_path(1).read_bytes())
        titled = [aged(s, 0, title="Helpful Spirit") if i == 0 else s for i, s in enumerate(people)]
        v.history([("2026-10-11 21:00:00", titled)])
        path = v.folder / LOGS / "Save 1" / "Tribe History" / "Village History 1.txt"
        text = path.read_bytes().decode("latin-1").replace(
            f"  Name: {people[0].name}\r\n", f"  Name: {people[0].name}\r\n  Custom title: Helpful Spirit\r\n", 1)
        path.write_bytes(text.encode("latin-1"))
        rec = rc.reconcile(v.folder, 4, 1)
        self.assertEqual([f.topic for f in rec.questions], ["titles"], [f.text for f in rec.questions])
        entry = struct.pack("<II", 0, people[0].title_id) + b"Helpful Spirit".ljust(32, b"\0")
        titles = v.folder / DATA / "Custom Titles"
        titles.mkdir(parents=True)
        (titles / "Custom Titles - Save 1.dat").write_bytes(b"VCT1" + struct.pack("<III", 2, 4, 1) + entry)
        self.assertEqual(rc.reconcile(v.folder, 4, 1).questions, [])


class EverywhereTheVillageIsOpened(Base):
    def test_check_saves_and_logs_shows_every_question_and_writes_nothing(self):
        v = self.village("huttest", 2)
        original = v.save_path(1).read_bytes()
        x = v.people(original)[1]
        v.write_save(1, v.renamed(original, 1, "Zuri"))
        v.births(v.birth(4, x))
        before = v.state()
        result = tools.check_logs(v.folder, 1, 2)
        self.assertEqual(v.state(), before)
        self.assertGreaterEqual(result.asked, 1)
        self.assertIn("ASK       Question 1: Birth 4 says", result.text)
        self.assertIn("contradiction(s) only you can settle", result.summary)
        path = rc.export(result.reconciliation)
        self.assertEqual(path, v.folder / LOGS / "Save 1" / "Reconciliation" / "Virtual Villagers 2 Reconciliation - Save 1.txt")
        self.assertIn("1. Birth 4 says", path.read_text(encoding="latin-1"))
        # The report is never read as a log.
        self.assertTrue(tools.load_checker().not_a_log(v.folder, path))

    def test_repair_asks_the_same_questions_before_anything(self):
        import vv_log_additions as additions
        v = self.village("huttest", 3)
        original = v.save_path(1).read_bytes()
        x = v.people(original)[1]
        v.write_save(1, v.renamed(original, 1, "Zuri"))
        v.births(v.birth(4, x))
        kinds = additions.plan(v.folder, 3, 1)
        kind = next(k for k in kinds if k.id == "reconcile")
        self.assertEqual(len(kind.questions), 1)
        self.assertTrue(kind.notes)

    def test_the_pickers_run_it_when_a_tribe_is_chosen(self):
        gui = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        self.assertEqual(gui.count("vv_reconcile_view.watch("), 2)       # Check / Repair, Rename Tribe
        window = (ROOT / "src" / "vv_genealogy_window.py").read_text(encoding="utf-8")
        self.assertIn("vv_reconcile_view.watch(", window)                  # every village window's picker


if __name__ == "__main__":
    unittest.main()
