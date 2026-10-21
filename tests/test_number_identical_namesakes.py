"""Namesakes with the same looks are numbered too (src/vv_number_names.py, src/vv_last_names.py
plan_renames `ordered`; all five games).

The owner (2026-10-20), Repair Saves & Logs in The Lost Children showing a red "The duplicate names were
not numbered. 2 living villagers are called Goby Kalama and look the same, so the records cannot tell
them apart: they keep their name." (and Hoya, Malo, Tomil Kalama): "fix this too!!!".  (Those four turned
out to be stale records the save reader should skip -- fixed on its own branch; these tests use genuine
namesakes.)  Genuine namesakes of the same name and looks may differ in age.  So: the oldest
is I (the owner's oldest-first rule), villagers of one age (identical twins) go in the game's own order
-- the save's record order, the Births log's order of the delivery -- and every record that can be tied
to one of them is renamed by the same rule; one that cannot is left and said, never guessed.  Such a
pair never stops the rest from being numbered, and is never an error.
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

import vv_genealogy as gen  # noqa: E402
import vv_last_names as ln  # noqa: E402
import vv_number_names as nn  # noqa: E402
import vv_save_layout as layout  # noqa: E402
import test_last_names_rename as fixture  # noqa: E402
from test_last_names_rename import NOW, STRIDE, TABLE, NoGame, entry  # noqa: E402


def aged(e: bytes, age: int) -> bytes:
    """A fixture villager (The Secret City's made-up save) of this age."""
    out = bytearray(e)
    struct.pack_into("<i", out, 0x14 - 0x10, age)
    return bytes(out)


def births(*children: str) -> str:
    return "Village: Tribe (Save 1)\n" + "".join(
        f"Birth {k}\n  Child: {child}\n    Head: 5\n    Body: 6\n  Mother: Aipi\n    Head: 7\n    Body: 8\n"
        f"  Father: Pa\n    Head: 1\n    Body: 1\n\n" for k, child in enumerate(children, 1))


class InTheSaveAndTheLogs(unittest.TestCase):
    _log = fixture.GiveLastNames._log
    tearDown = fixture.GiveLastNames.tearDown

    def setUp(self):
        fixture.GiveLastNames.setUp(self)
        named = mock.patch("vv_log_additions.current_villages", return_value={"Village: Tribe (Save 1)"})
        named.start()
        self.addCleanup(named.stop)
        for path in (self.history, self.births, self.deaths):
            path.unlink()

    def write(self, *people: bytes) -> None:
        self.save.write_bytes(b"ldwg" + bytes(TABLE - 4) + b"".join(people) + bytes(64))

    def names_in_save(self) -> list[tuple[str, int | None]]:
        return [(v.name, v.age) for v in ln.living(self.folder, 3, 1)]

    def repairs(self) -> str:
        folder = layout.slot_log_folder(self.folder, layout.REPAIRS_LOGS, 1)
        return "".join(p.read_bytes().decode("latin-1") for p in sorted(folder.glob("*.txt")))

    def test_same_looks_different_ages_the_oldest_is_i(self):
        # The owner's Kalamas: the younger first in the save, the older second.
        self.write(aged(entry("Goby Kalama", 0, 7, 5, 6), 129), aged(entry("Goby Kalama", 0, 7, 5, 6), 202),
                   entry("Aipi", 1, 50, 7, 8), entry("Mai", 1, 3, 2, 2), entry("Mai", 1, 3, 9, 9))
        self.assertEqual([a for _n, a in self.names_in_save()][:2], [129, 202], "the fixture's ages are read")
        want = nn.pending(self.folder, 3, 1)
        self.assertEqual(want.ordered, {("Goby Kalama", 5, 6): ["Goby Kalama I", "Goby Kalama II"]})
        self.assertFalse(any("look the same" in n for n in want.notes))
        result, wanted = nn.number_names(self.folder, 3, 1, processes=NoGame(), now=NOW, automatic=True)
        self.assertEqual(self.names_in_save()[:2], [("Goby Kalama II", 129), ("Goby Kalama I", 202)])
        # The other namesakes, numbered in the same run.
        self.assertEqual(sorted(n for n, _a in self.names_in_save()[3:]), ["Mai I", "Mai II"])
        self.assertEqual(nn.renamed_count(result, wanted), 4)
        record = self.repairs()
        self.assertIn("  Renamed: Goby Kalama (head 5, body 6, age 202) -> Goby Kalama I\r\n", record)
        self.assertIn("  Renamed: Goby Kalama (head 5, body 6, age 129) -> Goby Kalama II\r\n", record)
        self.assertEqual(nn.pending(self.folder, 3, 1).ordered, {}, "nothing left to number")

    def test_identical_twins_get_i_and_ii_by_birth_order_and_their_records_follow(self):
        self.write(entry("Tomil Kalama", 0, 7, 5, 6), entry("Tomil Kalama", 0, 7, 5, 6),
                   entry("Aipi", 1, 50, 7, 8),
                   entry("Kid", 0, 50, 3, 3, father=("Tomil Kalama", 5, 6), mother=("Aipi", 7, 8)))
        log = self._log("Births and Conceptions/Virtual Villagers 3 Births and Conceptions Log 1.txt",
                        births("Tomil Kalama", "Tomil Kalama"))
        history = self._log("Tribe History/Village History 1.txt",
                            "=== Virtual Villagers 3 -- 2026-10-01 ===\nVillage: Tribe (Save 1)\n"
                            "Villager 1\n  Name: Tomil Kalama\n  Head: 5\n  Body: 6\n\n"
                            "Villager 2\n  Name: Tomil Kalama\n  Head: 5\n  Body: 6\n\n"
                            "=== Virtual Villagers 3 -- 2026-09-01 ===\nVillage: Tribe (Save 1)\n"
                            "Villager 1\n  Name: Tomil Kalama\n  Head: 5\n  Body: 6\n\n")
        result, wanted = nn.number_names(self.folder, 3, 1, processes=NoGame(), now=NOW)
        self.assertEqual([n for n, _a in self.names_in_save()][:2], ["Tomil Kalama I", "Tomil Kalama II"],
                         "one age: the save's record order")
        text = log.read_bytes().decode()
        self.assertLess(text.index("Birth 1\r\n  Child: Tomil Kalama I\r\n"),
                        text.index("Birth 2\r\n  Child: Tomil Kalama II\r\n"), "the delivery's first child is I")
        snap = history.read_bytes().decode()
        self.assertIn("Villager 1\r\n  Name: Tomil Kalama I\r\n", snap)
        self.assertIn("Villager 2\r\n  Name: Tomil Kalama II\r\n", snap)
        # The earlier snapshot names one of them only: it cannot be tied, so it keeps the name, and says so.
        self.assertIn("2026-09-01 ===\r\nVillage: Tribe (Save 1)\r\nVillager 1\r\n  Name: Tomil Kalama\r\n", snap)
        # A child's father kept by name and looks only cannot be tied either: kept, and said.
        kid = TABLE + 3 * STRIDE + 0x14
        self.assertEqual(self.save.read_bytes()[kid + 0x24:kid + 0x24 + 13], b"Tomil Kalama\0")
        said = " ".join(wanted.notes)
        self.assertIn("cannot be tied to which", said)
        self.assertIn("Kid's father Tomil Kalama", said)
        self.assertIn("2026-09-01", said)
        self.assertIn("Left as it was:", self.repairs())
        # The record left under the old name is one of the twins, never a third villager to number: a second
        # Repair changes nothing (the Repair audit, 2026-10-20).
        again = nn.pending(self.folder, 3, 1)
        self.assertEqual((again.renames, again.ordered), ({}, {}))
        with self.assertRaises(nn.NothingToNumber):
            nn.number_names(self.folder, 3, 1, processes=NoGame(), now=NOW)

    def test_a_pair_alone_is_no_error_and_never_stops_the_others(self):
        # A pair a custom title cannot tell apart (the same name and likes): the titles file holds it.
        self.write(entry("Malo Kalama", 0, 7, 5, 6), entry("Malo Kalama", 0, 7, 5, 6),
                   entry("Hoya", 1, 3, 2, 2), entry("Hoya", 1, 3, 9, 9))
        titles = self.folder / fixture.DATA / "Custom Titles" / "Custom Titles - Save 1.dat"
        fp = fixture.title_identity("Malo Kalama", (1, 2, 3), (4, 5, 6))
        titles.write_bytes(struct.pack("<4I", 0x31544356, 2, 3, 1) + struct.pack("<II", 0, fp)
                           + b"Seer".ljust(32, b"\0"))
        result, wanted = nn.number_names(self.folder, 3, 1, processes=NoGame(), now=NOW)
        self.assertEqual(sorted(n for n, _a in self.names_in_save()), ["Hoya I", "Hoya II", "Malo Kalama", "Malo Kalama"])
        self.assertTrue(any("Malo Kalama keep their names" in n for n in wanted.notes), wanted.notes)
        # Only such a pair: nothing to number, which is not an error.
        self.write(entry("Malo Kalama", 0, 7, 5, 6), entry("Malo Kalama", 0, 7, 5, 6))
        with self.assertRaises(nn.NothingToNumber) as caught:
            nn.number_names(self.folder, 3, 1, processes=NoGame(), now=NOW)
        self.assertTrue(caught.exception.notes)

    def test_a_namesake_the_save_no_longer_holds_keeps_the_pair_as_it_is(self):
        # A Death record of the same name and looks: which of them died cannot be told.
        self.write(entry("Goby Kalama", 0, 7, 5, 6), entry("Goby Kalama", 0, 7, 5, 6))
        self._log("Deaths/Virtual Villagers 3 Deaths Log 1.txt",
                  "Village: Tribe (Save 1)\nDeath 1\n  Name: Goby Kalama\n  Age at death: 1400\n"
                  "  Head: 5\n  Body: 6\n\n")
        want = nn.pending(self.folder, 3, 1)
        self.assertEqual(want.ordered, {})
        self.assertTrue(any("not all of them are in the save" in n for n in want.notes))
        with self.assertRaises(nn.NothingToNumber):
            nn.number_names(self.folder, 3, 1, processes=NoGame(), now=NOW)

    def test_a_second_repair_changes_nothing(self):
        # Twins, aged namesakes, another pair, and an Island Events line naming a Gata Sirikit II without
        # looks (the Repair audit's oscillation).
        self.write(entry("Tomil Kalama", 0, 7, 5, 6), entry("Tomil Kalama", 0, 7, 5, 6),
                   aged(entry("Goby", 0, 7, 3, 3), 300), aged(entry("Goby", 0, 7, 3, 3), 100),
                   entry("Gata Sirikit II", 1, 9, 11, 20), entry("Mai", 1, 3, 2, 2), entry("Mai", 1, 3, 9, 9))
        self._log("Island Events/Virtual Villagers 3 Island Events Log 1.txt",
                  "Village: Tribe (Save 1)\nIsland event 1\n  Name: Gata Sirikit II\n\n")
        nn.number_names(self.folder, 3, 1, processes=NoGame(), now=NOW)
        once = {p: p.read_bytes() for p in self.folder.rglob("*") if p.is_file() and "Backups" not in p.parts}
        with self.assertRaises(nn.NothingToNumber):
            nn.number_names(self.folder, 3, 1, processes=NoGame(), now=NOW)
        twice = {p: p.read_bytes() for p in self.folder.rglob("*") if p.is_file() and "Backups" not in p.parts}
        self.assertEqual(once, twice, "a second Repair changes nothing")
        self.assertEqual(nn.pending(self.folder, 3, 1).renames, {})

    def test_the_repair_window_shows_it_as_information(self):
        gui = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        repair = gui[gui.index("    def _repair_logs("):gui.index("    def _repair_checklist(")]
        info = repair.index("except vv_number_names.NothingToNumber as exc:")
        self.assertLess(info, repair.index('f"The duplicate names were not numbered. {exc}"'),
                        "caught before the red error")
        self.assertIn("misnumbered = vv_number_names.wanted_names(wanted)", repair)
        tree = (ROOT / "src" / "vv_genealogy_window.py").read_text(encoding="utf-8")
        offer = tree[tree.index("    def _number_names(self)"):tree.index("    def _reset_frames(self)")]
        self.assertLess(offer.index("except vv_number_names.NothingToNumber as exc:"),
                        offer.index("messagebox.showerror("))


class EveryGame(unittest.TestCase):
    """The save's renaming in each game's own record layout (vv_last_names.FIELDS): two villagers of the
    same name and looks, ages 129 (first in the save) and 202, and a pair of one age."""

    def test_each_game_numbers_them_oldest_first_in_its_own_layout(self):
        for game in range(1, 6):
            with self.subTest(game=game), tempfile.TemporaryDirectory(prefix="vvfp_nt_") as tmp:
                folder = Path(tmp)
                f = ln.FIELDS[game]
                stride = 0x400
                data = bytearray(16 * stride)
                people = []
                for k, (name, age) in enumerate((("Goby Kalama", 129), ("Goby Kalama", 202),
                                                 ("Tomil Kalama", 300), ("Tomil Kalama", 300))):
                    at = (k + 1) * stride
                    data[at:at + len(name)] = name.encode()
                    people.append(ln.Living(at, name, "Male", 5, 6, 7, "", age=age))
                save = ln.save_path(folder, game, 1)
                save.write_bytes(bytes(data))
                with mock.patch.object(ln, "living", return_value=people), \
                        mock.patch("vv_log_additions.current_villages", return_value={"Village: Tribe (Save 1)"}):
                    plan = ln.plan_renames(folder, game, 1, {}, dead=True, ordered={
                        ("Goby Kalama", 5, 6): ["Goby Kalama I", "Goby Kalama II"],
                        ("Tomil Kalama", 5, 6): ["Tomil Kalama I", "Tomil Kalama II"]})
                after = next(c.updated for c in plan.changes if c.path == save)
                got = [after[p.at:p.at + f.name_cap].split(b"\0")[0].decode() for p in people]
                self.assertEqual(got, ["Goby Kalama II", "Goby Kalama I", "Tomil Kalama I", "Tomil Kalama II"])
                self.assertEqual(sorted(plan.numbered), sorted([
                    (("Goby Kalama", 5, 6, 202), "Goby Kalama I"), (("Goby Kalama", 5, 6, 129), "Goby Kalama II"),
                    (("Tomil Kalama", 5, 6, 300), "Tomil Kalama I"), (("Tomil Kalama", 5, 6, 300), "Tomil Kalama II")]))

    def test_a_second_numbering_changes_nothing(self):
        # The Repair audit (2026-10-20): every Repair renamed Gata Sirikit II to III and back, because an
        # older record without looks took a number.  Each game: number, apply, number again -- nothing.
        def cases():
            return [
                # A living Gata Sirikit II and an older name-only record of that name.
                [gen.Person(1, "Gata Sirikit II", 11, 20, alive=True, birth_record=5, age=300),
                 gen.Person(2, "Gata Sirikit II", None, None, birth_record=1)],
                # ... of the plain name, with two living namesakes.
                [gen.Person(1, "Gata Sirikit", None, None, birth_record=0),
                 gen.Person(2, "Gata Sirikit", 11, 20, alive=True, birth_record=2, age=300),
                 gen.Person(3, "Gata Sirikit", 4, 4, alive=True, birth_record=3, age=200)],
                # Same looks, different ages, and a dead namesake of other looks.
                [gen.Person(1, "Soda", 5, 6, alive=True, birth_record=4, age=100),
                 gen.Person(2, "Soda", 1, 1, gone="died", birth_record=0, age=900)],
            ]
        for game in range(1, 6):
            for k, people in enumerate(cases()):
                with self.subTest(game=game, case=k):
                    v = gen.Village(game, 1, "Tribe", {p.id: p for p in people})
                    alike = {("Soda", 5, 6): 2} if k == 2 else {}
                    first = nn.numbering(v, alike=alike, nameless={p.name for p in people if p.head is None},
                                         bodies=set(), orderable=set(alike))
                    for p in people:                    # as the save and the logs are after the rename
                        if p.key in first.renames:
                            p.name = first.renames[p.key]
                        elif p.key in first.ordered:
                            p.name = first.ordered[p.key][0]
                    nameless = {p.name for p in people if p.head is None}
                    if k == 2:                          # the two Sodas now carry different names
                        people.append(gen.Person(9, first.ordered[("Soda", 5, 6)][1], 5, 6, alive=True,
                                                 birth_record=6, age=50))
                        v = gen.Village(game, 1, "Tribe", {p.id: p for p in people})
                    second = nn.numbering(v, nameless=nameless, bodies=set())
                    self.assertEqual(second.renames, {}, (first.renames, first.ordered))
                    self.assertEqual(second.ordered, {})

    def test_the_numbers_skip_one_in_use(self):
        v = gen.Village(2, 1, "Tribe", {1: gen.Person(1, "Goby Kalama", 5, 6, alive=True, birth_record=1)})
        out = nn.numbering(v, alike={("Goby Kalama", 5, 6): 2}, taken={"Goby Kalama II"},
                           orderable={("Goby Kalama", 5, 6)})
        self.assertEqual(out.ordered, {("Goby Kalama", 5, 6): ["Goby Kalama I", "Goby Kalama III"]})
        self.assertEqual(out.renames, {})


if __name__ == "__main__":
    unittest.main()
