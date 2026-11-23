"""Repair Saves & Logs, "Give the Esteemed Elder title retroactively" (the owner, 2026-11-22: "a repair logs thing to
retroactively give villagers and graves that title/epitaph/skill however it's represented on a grave"):
src/vv_log_additions.py plan_esteemed, src/vv_graves.py plan_elders / write_elders.

Each village (A New Home, The Lost Children, The Tree of Life) has three graves, all made before the row:
  Anna, adult, died with three mastered skills, her record still in the save -> her grave's epitaph and her Death
                                                                                record get the title
  Ben, adult, died with one mastered skill, his record in the save            -> left
  Dan, adult, best skill mastered, record no longer in the save               -> left, and listed as unknown
and one living villager, Eve, whose older History snapshot shows three mastered skills -> that snapshot gets the line.
Without the row in the exe nothing is planned (the stock game gives no such title).
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_graves  # noqa: E402
import vv_log_additions as additions  # noqa: E402
import vv_log_tools as tools  # noqa: E402
import preferred_repair_fixtures as fx  # noqa: E402

GAMES = (1, 2, 4)
JOB_EPITAPH = "Strong Arms, Big Heart"
# Record order (A New Home and The Lost Children: Parenting, Building, Farming, Healing, Research; The Tree of Life:
# Farming, Parenting, Healing, Research, Building): three mastered, Building 95 the highest.
ELDER = {1: [92, 95, 91, 5, 30], 2: [90, 95, 88, 5, 30], 4: [90.0, 88.5, 5.0, 30.0, 95.5]}
ONE = {1: [10, 95, 60, 5, 30], 2: [10, 95, 60, 5, 30], 4: [60.5, 10.0, 5.0, 30.0, 95.5]}
SNAPSHOT = {1: ("Parenting", "Building", "Farming", "Healing", "Research"),
            2: ("Parenting", "Building", "Farming", "Healing", "Research"),
            4: ("Farming", "Parenting", "Healing", "Research", "Building")}


def village(game: int, row: bool) -> fx.Village:
    v = fx.Village(game)
    for place, name in enumerate(("Anna", "Ben", "Dan")):
        fx.write_grave(v.buf, game, place, name, 900, fx.BUILDER[game], 95, JOB_EPITAPH)
        v.death(place + 1, name, 900, "Master Builder", JOB_EPITAPH)
    fx.write_entry(v.buf, game, 0, "Eve", 500, 80, fx.NONE[game], True)
    fx.write_entry(v.buf, game, 1, "Anna", 900, 0, fx.NONE[game], False, ELDER[game])
    fx.write_entry(v.buf, game, 2, "Ben", 900, 0, fx.NONE[game], False, ONE[game])
    v.save()
    skills = "".join(f"    {name:<10} {int(value)}\n" for name, value in zip(SNAPSHOT[game], ELDER[game]))
    v.log_text += (f"Villager 1\n  Name: Eve\n  Head: 1\n  Body: 1\n  Likes: (none)\n  Dislikes: (none)\n"
                   f"  Skills:\n{skills}\n")
    v.log()
    if game == 1:
        fx.sidecar_vv1(v, 0, "Anna", 900, JOB_EPITAPH)          # A New Home keeps the epitaph in its Graves file
    v.rows([f"vv{game}_cause_of_death"] + ([f"vv{game}_esteemed_elders"] if row else []))
    return v


def plan(v: fx.Village, game: int) -> additions.Kind:
    people = additions.person_blocks(v.folder, 1, game)
    _page, current = additions.population_page(v.folder, 1, game)
    return additions.plan_esteemed(v.folder, game, 1, people, current, v.game_folders)


class Plan(unittest.TestCase):
    def test_without_the_row_nothing(self):
        for game in GAMES:
            with self.subTest(game=game):
                v = village(game, row=False)
                try:
                    kind = plan(v, game)
                    self.assertEqual((kind.inserts, kind.replaces, kind.context.get("graves")), ([], [], None))
                finally:
                    v.close()

    def test_with_the_row_the_elders_and_their_graves(self):
        for game in GAMES:
            with self.subTest(game=game):
                v = village(game, row=True)
                try:
                    kind = plan(v, game)
                    lines = sorted(i.line for i in kind.inserts)
                    self.assertEqual(lines, ["  Special villager: Esteemed Elder"] * 2, "Eve's snapshot, Anna's Death")
                    self.assertEqual([text for _p, _i, text in kind.replaces], ["  Epitaph: Esteemed Elder"])
                    planned = kind.context["graves"]
                    self.assertEqual([(p.grave.name, p.epitaph) for p in planned.in_save],
                                     [("Anna", (JOB_EPITAPH, "Esteemed Elder"))])
                    self.assertEqual([g.name for g in planned.unknown], ["Dan"])
                    self.assertTrue(any(n.startswith("Dan") and "not known" in n for n in kind.notes))
                    self.assertEqual(kind.context["preview"], ["Anna: grave and its epitaph", "Eve: records"])
                finally:
                    v.close()


class Apply(unittest.TestCase):
    def test_the_save_the_graves_file_and_the_log(self):
        for game in GAMES:
            with self.subTest(game=game):
                v = village(game, row=True)
                try:
                    kind = plan(v, game)
                    additions.apply(v.folder, [kind], {"esteemed"}, {})
                    self.assertEqual(additions.write_elder_graves(v.folder, game, 1, [kind], {"esteemed"}), 1)
                    data = (v.folder / f"{tools.load_checker().SAVE_STEMS[game]}1.ldw").read_bytes()
                    graves = {g.name: g for g in vv_graves.read_graves(game, data)}
                    if game == 1:
                        path = vv_graves.graves_file(v.folder, 1, 1)
                        raw = path.read_bytes()
                        self.assertEqual(struct.unpack_from("<I", raw, 4)[0], 4, "version 4: epitaph 14")
                        vv_graves._load_sidecar(v.folder, 1, 1, list(graves.values()))
                        self.assertEqual(graves["Anna"].sidecar.get("epitaph"), "Esteemed Elder")
                    else:
                        self.assertEqual(graves["Anna"].values["epitaph"], "Esteemed Elder")
                        self.assertEqual(graves["Ben"].values["epitaph"], JOB_EPITAPH)
                        self.assertEqual(graves["Dan"].values["epitaph"], JOB_EPITAPH)
                    text = (v.folder / fx.LOGS / "Deaths and Disappearances"
                            / f"Virtual Villagers {game} Deaths Log 1.txt").read_bytes().decode("cp1252")
                    anna = text.split("Death 1\n", 1)[1].split("\n\n", 1)[0]
                    self.assertIn("  Special villager: Esteemed Elder", anna)
                    self.assertIn("  Epitaph: Esteemed Elder", anna)
                    ben = text.split("Death 2\n", 1)[1].split("\n\n", 1)[0]
                    self.assertNotIn("Esteemed Elder", ben)
                    eve = text.split("Villager 1\n", 1)[1].split("\n\n", 1)[0]
                    self.assertIn("  Special villager: Esteemed Elder", eve)
                    index = "".join(p.read_text(encoding="utf-8", errors="replace")
                                    for p in v.folder.rglob("Copies Index.txt"))
                    self.assertIn(vv_graves.ELDER_COPY_SUFFIX.lstrip("."), index, "a copy of the changed file was kept first")
                finally:
                    v.close()

    def test_a_second_special_villager_line_is_never_added(self):
        """The Special villager kind may add the same line to a record: one stands."""
        v = village(2, row=True)
        try:
            kind = plan(v, 2)
            twin = additions.Kind("special", "x")
            for ins in kind.inserts:
                twin.inserts.append(additions.Insert(ins.path, ins.after, ins.rank, line=ins.line))
            out = additions.resolve([twin, kind], {"special", "esteemed"}, {})
            for adds in out.values():
                self.assertEqual(len(adds), len({a[0] for a in adds}))
                self.assertTrue(all(a[3] == "special" for a in adds))
        finally:
            v.close()


class Graves(unittest.TestCase):
    def test_the_tree_of_lifes_grave_byte_is_the_scholars(self):
        lay = vv_graves.LAYOUTS[4]
        data = bytearray(lay.base + lay.places * lay.stride)
        at = lay.base
        data[at:at + 5] = b"Kai\0\0"
        struct.pack_into("<i", data, at + lay.age, 900)
        data[at + lay.elder] = 1
        self.assertEqual(vv_graves.read_graves(4, bytes(data))[0].values["title"], "Scholar")
        self.assertFalse(vv_graves._title_differs(4, "Scholar", "Scholar"))
        self.assertFalse(vv_graves._title_differs(4, "", "Esteemed Elder"))
        self.assertTrue(vv_graves._title_differs(4, "", "Scholar"))

    def test_a_version_4_graves_file_reads_and_an_older_never_holds_14(self):
        e = bytearray(44)
        struct.pack_into("<HHIbB", e, 0, 0, 0, 1234, vv_graves.CAUSE_NONE, vv_graves.EPITAPH_ELDER)
        raw = vv_graves._vcd1_bytes(1, [e])
        self.assertEqual(struct.unpack_from("<I", raw, 4)[0], 4)
        self.assertIsNotNone(vv_graves._vcd1_entries(raw, 1))
        older = raw[:4] + struct.pack("<I", 3) + raw[8:]
        self.assertIsNone(vv_graves._vcd1_entries(older, 1), "a version 3 file never holds epitaph 14")


if __name__ == "__main__":
    unittest.main()
