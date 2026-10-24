"""Repair Saves & Logs, The Lost Children: "Give Esteemed Elders Totems Retroactively" and "Fix Rare Villager
Turning Into Totem" (src/vv_vv2_totems.py).

The owner (2026-10-19): an Esteemed Elder without a totem is given one of a random colour; a villager who
turned into a totem (a normal Details screen, an immortal moveable totem in the game) is reverted to a
normal villager.  The village may be full (256 records): then nobody is deleted or overwritten and the
elders left without a totem are listed with the reason.

Each test builds a save folder by hand (a temporary folder) with the villager table where the game keeps
it, as the game's own writer 0x44B5A0 packs it -- never the owner's saves.
"""
from __future__ import annotations

import random
import struct
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_last_names as ln  # noqa: E402
import vv_log_tools as tools  # noqa: E402
import vv_vv2_totems as vt  # noqa: E402

LOGS = "Virtual Villagers Fun Patcher Logs"
DATA = "Virtual Villagers Fun Patcher Data"
NOW = datetime(2026, 10, 19, 12, 0, 0)
FIRST_NAME_AT = 0x25C              # where the owner's saves keep entry 0's name (file = world + 4)
SAVE_LENGTH = 197500               # the game's save size


class NoGame:
    def find(self, exe_name):
        return []


class Running:
    def find(self, exe_name):
        return [1]


# Record offsets, independent of the module: the entry holds record +0x524..+0x7FF, the name (+0x564) at
# entry +0x40, the "in use" byte at entry +0x2DC (the writer 0x44B5A0, the loader 0x44B640).
def rel(record_offset: int) -> int:
    return record_offset - 0x564


def person(name, sex=1, head=3, body=4, age=600, health=100, elder=False, totem=False, lineage=7,
           father="Papa", mother="Mama", skills=(20, 20, 20, 20, 20), carrying=0, litter=0, x=0, y=0,
           kind=9) -> dict:
    return dict(name=name, sex=sex, head=head, body=body, age=age, health=health, elder=elder, totem=totem,
                lineage=lineage, father=father, mother=mother, skills=skills, carrying=carrying, litter=litter,
                x=x, y=y, kind=kind)


def save_for(people: list[dict]) -> bytes:
    data = bytearray(SAVE_LENGTH)
    for k, p in enumerate(people):
        at = FIRST_NAME_AT + k * 0x2E0
        data[at:at + len(p["name"])] = p["name"].encode()
        struct.pack_into("<iii", data, at + rel(0x528), 935109, p["health"], p["age"])
        struct.pack_into("<ii", data, at + rel(0x534), p["age"], p["sex"])
        struct.pack_into("<ii", data, at + rel(0x540), p["carrying"], p["litter"])
        struct.pack_into("<iiii", data, at + rel(0x548), p["head"], p["body"], p["kind"], p["lineage"])
        data[at + rel(0x558)] = 1 if p["totem"] else 0
        struct.pack_into("<ii", data, at + rel(0x55C), p["x"], p["y"])
        data[at + rel(0x57D):at + rel(0x57D) + len(p["father"])] = p["father"].encode()
        data[at + rel(0x596):at + rel(0x596) + len(p["mother"])] = p["mother"].encode()
        struct.pack_into("<5i", data, at + rel(0x7E4), *p["skills"])
        data[at + rel(0x7FC)] = 1 if p["elder"] else 0
        data[at + rel(0x524) + 0x2DC] = 1
    return bytes(data)


def death(n: int, name: str, head: int, body: int, age: int = 1400, sex: str = "Female",
          special: str = "Esteemed Elder") -> str:
    return (f"Death {n}\n  Name: {name}\n  Special villager: {special}\n  Age at death: {age}\n  Sex: {sex}\n"
            f"  Cause of death: Old age\n  Grave: Master Farmer\n  Epitaph: Esteemed Elder\n  Head: {head}\n"
            f"  Body: {body}\n  Likes: (none)\n  Dislikes: (none)\n\n")


class Village:
    def __init__(self, case: unittest.TestCase, people: list[dict], deaths: str = ""):
        tmp = tempfile.TemporaryDirectory()
        case.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.save = ln.save_path(self.folder, 2, 1)
        self.save.write_bytes(save_for(people))
        if deaths:
            path = self.folder / LOGS / "Deaths" / "Virtual Villagers 2 Deaths Log 1.txt"
            path.parent.mkdir(parents=True)
            path.write_bytes(("Village: Tribe (Save 1)\n" + deaths).replace("\n", "\r\n").encode("latin-1"))

    def repairs(self) -> str:
        found = sorted(p for root in (self.folder / LOGS, self.folder / "Virtual Villagers Fun Patcher")
                       for p in root.rglob("Virtual Villagers * Repairs Log *.txt"))
        return found[0].read_bytes().decode("latin-1") if found else ""

    def backups(self) -> list[Path]:
        root = self.folder / "Backups"
        return sorted(root.iterdir()) if root.is_dir() else []

    def entries(self) -> list[int]:
        return tools.load_checker().villager_offsets(2, self.save.read_bytes(), [])


def crowd(n: int, start: int = 0) -> list[dict]:
    """`n` ordinary villagers with names the game could give."""
    return [person(f"Villager{chr(65 + (k // 26) % 26)}{chr(65 + k % 26)}", head=k % 30, body=(k * 7) % 30)
            for k in range(start, start + n)]


def elder_and_totem(name="Azizi Kalama", **kw) -> tuple[dict, dict]:
    e = person(name, elder=True, **kw)
    t = dict(e, elder=False, totem=True, health=0, x=400, y=900)
    return e, t


class TheLayout(unittest.TestCase):
    def test_offsets_agree_with_the_checker_and_the_record_reference(self):
        checker = tools.load_checker()
        self.assertEqual(vt.HEALTH, checker.HEALTH[2])
        self.assertEqual(vt.IS_TOTEM, checker.LOOKALIKE[2])
        self.assertEqual(vt.SKILLS, checker.LAYOUTS[2].skills)
        self.assertEqual(vt.SEX, ln.FIELDS[2].sex)
        self.assertEqual((vt.HEAD, vt.BODY), (ln.FIELDS[2].head, ln.FIELDS[2].body))
        self.assertEqual((vt.TYPE, vt.IS_TOTEM, vt.X, vt.Y, vt.ELDER, vt.FLAG),
                         (rel(0x550), rel(0x558), rel(0x55C), rel(0x560), rel(0x7FC), 0x29C))
        self.assertEqual(vt.STRIDE, checker.LAYOUTS[2].stride)

    def test_the_faces_are_the_eight_frames(self):
        self.assertEqual(len(vt.FACES), 8)
        self.assertEqual(vt.face(8), vt.face(0))
        self.assertEqual(vt.face(41), vt.FACES[1])


class TheSurvey(unittest.TestCase):
    def test_a_living_elder_with_and_without_a_totem(self):
        e1, t1 = elder_and_totem("Hoto Kenobi", head=14, body=5)
        e2 = person("Azizi Kalama", elder=True, head=27, body=16)
        v = Village(self, crowd(5) + [e1, e2, t1])
        s = vt.survey(v.folder, 1)
        self.assertEqual([e.name for e in s.missing], ["Azizi Kalama"])
        self.assertEqual(s.elder_questions, [])
        self.assertEqual(s.villagers, [])
        self.assertEqual((s.entries, s.free), (8, 248))

    def test_a_dead_elder_from_the_deaths_log(self):
        _e, t = elder_and_totem("Luna Kaikala", head=22, body=22, sex=2)
        v = Village(self, crowd(3) + [t], deaths=death(1, "Luna Kaikala", 22, 22) + death(2, "Nina Jumapili", 10, 21)
                    + death(3, "Plain Person", 1, 1, special="Golden Child"))
        s = vt.survey(v.folder, 1)
        self.assertEqual([(e.name, e.living) for e in s.missing], [("Nina Jumapili", False)])
        self.assertEqual(s.villagers, [])

    def test_a_living_totem_is_certain(self):
        weird = person("Kele Wambui", totem=True, health=80, head=9, body=9)
        v = Village(self, crowd(4) + [weird])
        s = vt.survey(v.folder, 1)
        self.assertEqual(len(s.certain_villagers), 1)
        self.assertIn("Kele Wambui", s.certain_villagers[0].describe())
        self.assertIn("alive", s.certain_villagers[0].reason)
        self.assertEqual(s.asked_villagers, [])

    def test_a_totem_no_elder_matches_is_asked(self):
        stray = person("Mystery Statue", totem=True, health=0)
        v = Village(self, crowd(4) + [stray])
        s = vt.survey(v.folder, 1)
        self.assertEqual(s.certain_villagers, [])
        self.assertEqual([x.totem.name for x in s.asked_villagers], ["Mystery Statue"])
        self.assertIn("Is this a villager who turned into a totem?", s.asked_villagers[0].question())

    def test_a_renamed_elder_is_asked_not_given_a_second_totem(self):
        e, t = elder_and_totem("Kaki")
        e["name"] = "Kaki Jumapili"            # given a last name after the totem was made
        v = Village(self, crowd(3) + [e, t])
        s = vt.survey(v.folder, 1)
        self.assertEqual(s.missing, [])
        self.assertEqual([q.elder.name for q in s.elder_questions], ["Kaki Jumapili"])
        self.assertEqual(s.villagers, [])       # the statue matches an elder by first name: never asked as a villager
        go, left = vt.plan_give(s, kept={s.elder_questions[0].key})
        self.assertEqual((go, left), ([], []))
        go, _ = vt.plan_give(s)
        self.assertEqual([x.name for x in go], ["Kaki Jumapili"])

    def test_a_fully_renamed_elder_is_asked_by_looks_never_duplicated_or_cleared(self):
        # Codex, #596: the totem kept the old name; the elder's first name changed too.  A renamed
        # villager is the same person, so the statue (same head, body, sex and family line) is asked.
        e, t = elder_and_totem("Kaki", head=12, body=19, sex=2, lineage=5)
        e["name"] = "Zola Jumapili"
        v = Village(self, crowd(3) + [e, t])
        before = v.save.read_bytes()
        s = vt.survey(v.folder, 1)
        self.assertEqual(s.missing, [])
        self.assertEqual([(q.elder.name, q.totem.name) for q in s.elder_questions], [("Zola Jumapili", "Kaki")])
        self.assertIn("the same head, body, sex and family line", s.elder_questions[0].question())
        # Never offered as a villager turned into a totem: the mark is never taken off.
        self.assertEqual(s.villagers, [])
        with self.assertRaises(vt.TotemError):
            vt.fix_totem_villagers(v.folder, 1, processes=NoGame(), now=NOW)
        self.assertEqual(v.save.read_bytes(), before)
        # A yes keeps it and gives nothing new; nothing is given without the player's answer.
        self.assertEqual(vt.plan_give(s, kept={s.elder_questions[0].key}), ([], []))
        with self.assertRaises(vt.TotemError):
            vt.give_totems(v.folder, 1, kept={s.elder_questions[0].key}, processes=NoGame(), now=NOW)
        self.assertEqual(v.save.read_bytes(), before)

    def test_another_family_line_is_not_a_candidate(self):
        e, t = elder_and_totem("Kaki", head=12, body=19, sex=2, lineage=5)
        e.update(name="Zola Jumapili", lineage=6)
        s = vt.survey(Village(self, crowd(3) + [e, t]).folder, 1)
        self.assertEqual([x.name for x in s.missing], ["Zola Jumapili"])
        self.assertEqual([x.totem.name for x in s.asked_villagers], ["Kaki"])

    def test_a_recorded_rename_is_certain(self):
        e, t = elder_and_totem("Kaki", head=12, body=19, sex=2, lineage=5)
        e["name"] = "Zola Jumapili"
        v = Village(self, crowd(3) + [e, t])
        path = v.folder / LOGS / "Births and Conceptions" / "Virtual Villagers 2 Births and Conceptions Log 1.txt"
        path.parent.mkdir(parents=True)
        path.write_bytes("Village: Tribe (Save 1)\nName changed\n  Name: Zola Jumapili\n  Old name: Kaki\n"
                         "  Age: 900\n  Head: 12\n  Body: 19\n\n".replace("\n", "\r\n").encode("latin-1"))
        s = vt.survey(v.folder, 1)
        self.assertEqual((s.missing, s.elder_questions, s.villagers), ([], [], []))

    def test_one_statue_is_never_accepted_for_two_elders(self):
        # Codex, #596: two elders of the same name and family, one statue matching both exactly.
        e1, t = elder_and_totem("Kaki Jumapili", head=3, body=4)
        e2 = dict(e1, head=8, body=9)
        v = Village(self, crowd(3) + [e1, e2, t])
        s = vt.survey(v.folder, 1)
        self.assertEqual([q.elder.head for q in s.elder_questions], [3, 8])
        self.assertEqual({q.totem.record for q in s.elder_questions}, {5})
        self.assertIn("could also be Kaki Jumapili's", s.elder_questions[0].question())
        asked = []
        kept = vt.ask(s, lambda q: asked.append(q.elder.head) or True)
        self.assertEqual(asked, [3])                 # accepted for the first: never asked for the second
        go, left = vt.plan_give(s, kept)
        self.assertEqual(([x.head for x in go], left), ([8], []))
        # Even with a yes for both, the statue stands for one elder only.
        both = {q.key for q in s.elder_questions}
        go, _ = vt.plan_give(s, both)
        self.assertEqual([x.head for x in go], [8])
        result = vt.give_totems(v.folder, 1, kept=both, processes=NoGame(), now=NOW, rng=random.Random(1))
        self.assertEqual([g.elder.head for g in result.given], [8])
        # A no for the first asks the second.
        asked.clear()
        vt.ask(s, lambda q: asked.append(q.elder.head) or q.elder.head == 8)
        self.assertEqual(asked, [3, 8])

    def test_a_first_name_statue_two_elders_could_own_is_asked_once(self):
        e1 = person("Kaki Jumapili", elder=True, head=3, body=4)
        e2 = person("Kaki Wambui", elder=True, head=5, body=6)
        t = person("Kaki", totem=True, health=0, head=1, body=1)
        s = vt.survey(Village(self, crowd(3) + [e1, e2, t]).folder, 1)
        self.assertEqual([q.elder.name for q in s.elder_questions], ["Kaki Jumapili", "Kaki Wambui"])
        asked = []
        kept = vt.ask(s, lambda q: asked.append(q.elder.name) or True)
        self.assertEqual(asked, ["Kaki Jumapili"])
        self.assertEqual([x.name for x in vt.plan_give(s, kept)[0]], ["Kaki Wambui"])

    def test_babies_owed_take_records_first(self):
        mothers = [person(f"Mother{chr(65 + k)}", sex=2, carrying=500, litter=lit) for k, lit in enumerate((0, 2, 3))]
        e = person("Azizi Kalama", elder=True)
        v = Village(self, crowd(250) + mothers + [e])
        s = vt.survey(v.folder, 1)
        self.assertEqual((s.entries, s.owed, s.free), (254, 6, 0))


class GiveTotems(unittest.TestCase):
    def test_a_missing_totem_is_made_as_the_game_makes_one(self):
        e1, t1 = elder_and_totem("Hoto Kenobi", head=14, body=5)
        e2 = person("Azizi Kalama", elder=True, head=27, body=16, age=848, sex=1, lineage=12,
                    father="Kalama", mother="Zuri", skills=(95, 90, 88, 12, 3))
        people = crowd(5) + [e1, e2, t1]
        v = Village(self, people)
        before = v.save.read_bytes()
        result = vt.give_totems(v.folder, 1, processes=NoGame(), now=NOW, rng=random.Random(4))
        after = v.save.read_bytes()
        self.assertEqual(len(after), len(before))
        self.assertEqual([g.elder.name for g in result.given], ["Azizi Kalama"])
        self.assertEqual(result.not_given, [])
        entries = v.entries()
        self.assertEqual(len(entries), 9)
        new = entries[8]
        self.assertEqual(new, FIRST_NAME_AT + 8 * 0x2E0)
        i32 = lambda off: struct.unpack_from("<i", after, new + off)[0]  # noqa: E731
        self.assertEqual(after[new:new + 13], b"Azizi Kalama\0")
        self.assertEqual(after[new + rel(0x558)], 1)
        self.assertEqual(i32(rel(0x52C)), 0)                         # health 0, as 0x44D467
        self.assertEqual((i32(rel(0x530)), i32(rel(0x534))), (848, 848))
        self.assertEqual((i32(rel(0x538)), i32(rel(0x548)), i32(rel(0x54C)), i32(rel(0x554))), (1, 27, 16, 12))
        self.assertTrue(1 <= i32(rel(0x550)) <= 123)
        self.assertEqual(result.given[0].type, i32(rel(0x550)))
        self.assertEqual((i32(rel(0x55C)), i32(rel(0x560))), (750, 860))
        self.assertEqual(struct.unpack_from("<5i", after, new + rel(0x7E4)), (95, 90, 88, 12, 3))
        self.assertEqual(after[new + rel(0x7FC)], 0)                 # the totem is no elder
        self.assertEqual(after[new + rel(0x57D):new + rel(0x57D) + 7], b"Kalama\0")
        self.assertEqual(after[new + rel(0x524) + 0x2DC], 1)
        self.assertEqual(after[new + rel(0x524) + 0x2E0 + 0x2DC], 0)  # the loader stops after it
        # The elder keeps being the elder; every other entry is byte for byte the same.
        self.assertEqual(after[:new + rel(0x524)], before[:new + rel(0x524)])
        self.assertEqual(after[new + rel(0x524) + 0x2E0 + 1:], before[new + rel(0x524) + 0x2E0 + 1:])
        self.assertEqual(vt.survey(v.folder, 1).missing, [])
        text = v.repairs()
        self.assertIn("Repair 1\r\n  Date: 2026-10-19 12:00:00\r\n", text)
        self.assertIn("  Totem given: Azizi Kalama (head 27, body 16), a living Esteemed Elder: a totem (", text)
        self.assertIn(", record 9\r\n", text)
        backup = Path(result.backup.backup_folder)
        self.assertIn(vt.BACKUP_GIVE, backup.name)
        self.assertEqual((backup / v.save.name).read_bytes(), before)
        copy = v.folder / DATA / "Copies Made Before Repairs" / (v.save.name + vt.COPY_GIVE)
        self.assertEqual(copy.read_bytes(), before)

    def test_the_colour_is_random(self):
        types = set()
        for seed in range(12):
            v = Village(self, crowd(3) + [person("Azizi Kalama", elder=True)])
            types.add(vt.give_totems(v.folder, 1, processes=NoGame(), now=NOW, rng=random.Random(seed)).given[0].type % 8)
        self.assertGreater(len(types), 3)

    def test_a_dead_elder_gets_one_from_the_deaths_log(self):
        v = Village(self, crowd(3), deaths=death(1, "Nina Jumapili", 10, 21, age=1523, sex="Female"))
        result = vt.give_totems(v.folder, 1, processes=NoGame(), now=NOW, rng=random.Random(1))
        self.assertEqual([g.elder.name for g in result.given], ["Nina Jumapili"])
        after = v.save.read_bytes()
        new = v.entries()[3]
        self.assertEqual(after[new:new + 14], b"Nina Jumapili\0")
        self.assertEqual(struct.unpack_from("<iii", after, new + rel(0x52C)), (0, 1523, 1523))
        self.assertEqual(struct.unpack_from("<i", after, new + rel(0x538))[0], 2)
        self.assertEqual(struct.unpack_from("<ii", after, new + rel(0x548)), (10, 21))
        self.assertEqual(after[new + rel(0x558)], 1)

    def test_several_totems_stand_apart_and_on_the_map(self):
        elders = [person(f"Elder{chr(65 + k)}", elder=True, head=k) for k in range(6)]
        standing = dict(person("Other", totem=True, health=0, x=750, y=860))
        v = Village(self, crowd(3) + [standing] + elders,
                    deaths=death(1, "Other", 3, 4, sex="Male"))
        result = vt.give_totems(v.folder, 1, processes=NoGame(), now=NOW, rng=random.Random(2))
        spots = [(g.x, g.y) for g in result.given] + [(750, 860)]
        self.assertEqual(len(result.given), 6)
        for i, a in enumerate(spots):
            self.assertTrue(vt.MAP_X[0] <= a[0] <= vt.MAP_X[1] and vt.MAP_Y[0] <= a[1] <= vt.MAP_Y[1])
            for b in spots[i + 1:]:
                self.assertTrue(abs(a[0] - b[0]) >= 30 or abs(a[1] - b[1]) >= 30, (a, b))

    def test_a_full_village_overwrites_nobody(self):
        e = person("Azizi Kalama", elder=True, head=27, body=16)
        v = Village(self, crowd(255) + [e])
        self.assertEqual(len(v.entries()), 256)
        before = v.save.read_bytes()
        s = vt.survey(v.folder, 1)
        go, left = vt.plan_give(s)
        self.assertEqual(go, [])
        self.assertEqual([x.name for x, _ in left], ["Azizi Kalama"])
        self.assertIn("256 of 256 villager records are in use", left[0][1])
        result = vt.give_totems(v.folder, 1, processes=NoGame(), now=NOW, rng=random.Random(3))
        self.assertEqual(result.given, [])
        self.assertEqual(v.save.read_bytes(), before)
        self.assertEqual(v.backups(), [])
        self.assertIsNone(result.backup)
        text = v.repairs()
        self.assertIn("  Not given: Azizi Kalama (head 27, body 16), a living Esteemed Elder -- the village is full", text)
        self.assertIn("  Nothing was changed in the save.\r\n", text)

    def test_some_fit_and_the_rest_are_listed(self):
        elders = [person(f"Elder{chr(65 + k)}", elder=True, head=k) for k in range(3)]
        v = Village(self, crowd(251) + elders)            # 254 records: room for two
        result = vt.give_totems(v.folder, 1, processes=NoGame(), now=NOW, rng=random.Random(5))
        self.assertEqual([g.elder.name for g in result.given], ["ElderA", "ElderB"])
        self.assertEqual([e.name for e, _ in result.not_given], ["ElderC"])
        self.assertEqual(len(v.entries()), 256)
        # With 256 entries the byte after the last (the writer's own end-of-list 0) is 0.
        after = v.save.read_bytes()
        self.assertEqual(after[FIRST_NAME_AT + rel(0x524) + 256 * 0x2E0 + 0x2DC], 0)
        text = v.repairs()
        self.assertIn("  Totem given: ElderA", text)
        self.assertIn("  Not given: ElderC", text)

    def test_refused_while_the_game_runs(self):
        v = Village(self, crowd(3) + [person("Azizi Kalama", elder=True)])
        before = v.save.read_bytes()
        with self.assertRaises(tools.GameRunning):
            vt.give_totems(v.folder, 1, processes=Running(), now=NOW)
        self.assertEqual(v.save.read_bytes(), before)
        self.assertEqual(v.backups(), [])

    def test_nothing_to_do(self):
        e, t = elder_and_totem()
        v = Village(self, crowd(3) + [e, t])
        with self.assertRaises(vt.TotemError):
            vt.give_totems(v.folder, 1, processes=NoGame(), now=NOW)
        self.assertEqual(v.repairs(), "")


class FixTotemVillagers(unittest.TestCase):
    def test_a_living_totem_loses_only_the_mark(self):
        weird = person("Kele Wambui", totem=True, health=80, head=9, body=9, x=331, y=839)
        v = Village(self, crowd(4) + [weird])
        before = v.save.read_bytes()
        result = vt.fix_totem_villagers(v.folder, 1, processes=NoGame(), now=NOW)
        after = v.save.read_bytes()
        at = v.entries()[4]
        self.assertEqual([i for i in range(len(before)) if before[i] != after[i]], [at + rel(0x558)])
        self.assertEqual(after[at + rel(0x558)], 0)
        self.assertEqual(len(result.fixed), 1)
        self.assertEqual(vt.survey(v.folder, 1).villagers, [])
        text = v.repairs()
        self.assertIn("  Reverted to a villager (certain): Kele Wambui (record 5, head 9, body 9): alive", text)
        copy = v.folder / DATA / "Copies Made Before Repairs" / (v.save.name + vt.COPY_FIX)
        self.assertEqual(copy.read_bytes(), before)

    def test_an_asked_one_changes_only_when_the_player_says_so(self):
        stray = person("Mystery Statue", totem=True, health=0)
        v = Village(self, crowd(4) + [stray])
        before = v.save.read_bytes()
        with self.assertRaises(vt.TotemError):
            vt.fix_totem_villagers(v.folder, 1, processes=NoGame(), now=NOW)        # not confirmed
        self.assertEqual(v.save.read_bytes(), before)
        key = vt.survey(v.folder, 1).asked_villagers[0].key
        vt.fix_totem_villagers(v.folder, 1, confirmed={key}, processes=NoGame(), now=NOW)
        after = v.save.read_bytes()
        at = v.entries()[4]
        self.assertEqual([i for i in range(len(before)) if before[i] != after[i]], [at + rel(0x558)])
        self.assertIn("the player said it is a villager", v.repairs())

    def test_a_real_totem_is_never_touched(self):
        e, t = elder_and_totem()
        v = Village(self, crowd(3) + [e, t])
        self.assertEqual(vt.survey(v.folder, 1).villagers, [])
        with self.assertRaises(vt.TotemError):
            vt.fix_totem_villagers(v.folder, 1, processes=NoGame(), now=NOW)

    def test_in_a_full_village_too(self):
        weird = person("Kele Wambui", totem=True, health=80)
        v = Village(self, crowd(255) + [weird])
        result = vt.fix_totem_villagers(v.folder, 1, processes=NoGame(), now=NOW)
        self.assertEqual(len(result.fixed), 1)
        self.assertEqual(len(v.entries()), 256)

    def test_refused_while_the_game_runs(self):
        v = Village(self, crowd(3) + [person("Kele Wambui", totem=True, health=80)])
        before = v.save.read_bytes()
        with self.assertRaises(tools.GameRunning):
            vt.fix_totem_villagers(v.folder, 1, processes=Running(), now=NOW)
        self.assertEqual(v.save.read_bytes(), before)


class TheReportedCases(unittest.TestCase):
    """Two players' reports (2026-10): "a kid will age out of nursing to age 2 but they are a totem and
    don't grow up or die" ("Amago`s totem"), and "my villager had twins but one of them is showing up as a
    totem" ("Mucha`s totem").  As the stock game leaves them (tests/test_vv2_fix_vanilla_bugs.py,
    TotemTickTests): the copy creator 0x44CEC0 made the second (or third) baby in a record still marked
    as a totem, with health 90 (0x44D15C), the first baby's parents, family line and looks, its +0x550
    plus one, and the age it was born at (40, two years), which never changes again."""

    @staticmethod
    def litter(n: int, now_age: int = 300) -> list[dict]:
        first = person("Kaya Wambui", age=now_age, health=88, father="Hoto", mother="Nia", lineage=12, kind=40)
        out = [first]
        for k, name in enumerate(("Mucha Wambui", "Amago Wambui")[:n - 1], start=1):
            out.append(person(name, age=40, health=90, father="Hoto", mother="Nia", lineage=12, kind=40 + k,
                              totem=True))
        return out

    def test_a_twin_born_as_a_totem_is_certain_with_its_litter_shown(self):
        v = Village(self, crowd(4) + self.litter(2) + [person("Other Child", age=300, father="Hoto",
                                                              mother="Nia", lineage=12, kind=70)])
        s = vt.survey(v.folder, 1)
        self.assertEqual([x.totem.name for x in s.certain_villagers], ["Mucha Wambui"])
        self.assertEqual(s.asked_villagers, [])
        why = s.certain_villagers[0].describe()
        self.assertIn("alive (health 90) and marked as a totem, aged 2 years", why)
        self.assertIn("never ages or dies", why)
        self.assertIn("born in one litter with Kaya Wambui (now 15 years) (parents Hoto and Nia)", why)
        self.assertNotIn("Other Child", why)

    def test_triplets_both_copies_are_found(self):
        v = Village(self, crowd(3) + self.litter(3))
        s = vt.survey(v.folder, 1)
        self.assertEqual(sorted(x.totem.name for x in s.certain_villagers), ["Amago Wambui", "Mucha Wambui"])
        amago = next(x for x in s.certain_villagers if x.totem.name == "Amago Wambui")
        self.assertIn("born in one litter with Kaya Wambui", amago.reason)

    def test_a_copy_with_a_random_mark_names_its_brothers_and_sisters(self):
        people = self.litter(2)
        people[1]["kind"] = 5                   # past 123 the copy creator rolls a new +0x550
        v = Village(self, crowd(2) + people)
        why = vt.survey(v.folder, 1).certain_villagers[0].reason
        self.assertIn("brother or sister of Kaya Wambui (now 15 years)", why)

    def test_fixed_only_the_mark_and_the_evidence_is_logged(self):
        v = Village(self, crowd(4) + self.litter(2))
        before = v.save.read_bytes()
        vt.fix_totem_villagers(v.folder, 1, processes=NoGame(), now=NOW)
        after = v.save.read_bytes()
        at = v.entries()[5]
        self.assertEqual([i for i in range(len(before)) if before[i] != after[i]], [at + rel(0x558)])
        text = v.repairs()
        self.assertIn("Reverted to a villager (certain): Mucha Wambui (record 6", text)
        self.assertIn("born in one litter with Kaya Wambui", text)
        self.assertTrue(v.backups())

    def test_an_elders_real_totem_beside_them_is_never_touched(self):
        e, t = elder_and_totem("Hoto Wambui", head=14, body=5)
        v = Village(self, crowd(3) + [e, t] + self.litter(2))
        s = vt.survey(v.folder, 1)
        self.assertEqual([x.totem.name for x in s.villagers], ["Mucha Wambui"])
        vt.fix_totem_villagers(v.folder, 1, processes=NoGame(), now=NOW)
        data = v.save.read_bytes()
        statue = v.entries()[4]
        self.assertEqual(data[statue + rel(0x558)], 1)


class TheChecklist(unittest.TestCase):
    def test_the_rows_are_wired_into_repair(self):
        gui = (ROOT / "src" / "vv_fun_patcher_gui.py").read_text(encoding="utf-8")
        checklist = gui[gui.index("    def _repair_checklist("):gui.index("    def _last_names_dialog(")]
        self.assertIn("vv_vv2_totems.LABEL_GIVE", checklist)
        self.assertIn("vv_vv2_totems.LABEL_FIX", checklist)
        self.assertIn('totems["give"] = totem_survey is not None and give_var.get()', checklist)
        repair = gui[gui.index("    def _repair_logs("):gui.index("    def _repair_checklist(")]
        self.assertIn('totems["survey"] = vv_vv2_totems.survey(folder, info.slot)', repair)
        self.assertLess(repair.index("vv_log_tools.approve_repair("), repair.index("self._vv2_totems("))
        self.assertLess(repair.index("self._vv2_totems("), repair.index("vv_cut_names.restore("))
        method = gui[gui.index("    def _vv2_totems("):gui.index("    def _restore_lost_titles(")]
        # The villagers first, then the elders; every unsure case asked on its own.
        self.assertLess(method.index("fix_totem_villagers("), method.index("give_totems("))
        self.assertIn("v.question()", method)
        self.assertIn("q.question()", method)

    def test_the_labels_are_the_owners_words(self):
        self.assertEqual(vt.LABEL_GIVE, "Give Esteemed Elders Totems Retroactively")
        self.assertEqual(vt.LABEL_FIX, "Fix Rare Villager Turning Into Totem")


if __name__ == "__main__":
    unittest.main()
