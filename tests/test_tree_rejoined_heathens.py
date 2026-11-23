"""New Believers: a villager who leaves the tribe for the Heathens and comes back is the SAME person on the tree.

The owner (2026-11-22): "converted villagers turned heathens reconverted into villagers should keep their original
positions in the family tree".  A founder, an island event's villager, a villager born in the tribe or one the logs
knew before any Arrived record, who leaves ("Disappeared / What happened: Left the tribe: became a Heathen") and
comes back ("Arrived / How: Converted from the Heathens"), keeps the one node they had: the same generation, the same
parents, partners and children, the same place on the page and the same words ("Founder" for a founder, never
"Arrived: Converted from the Heathens").  While they are a Heathen they keep their place too (marked "Heathen", and
never hidden by "Hide unconverted Heathens").  A change of looks while they were a Heathen that no record gives
(a Heathen's mask) never splits them into a "disappeared" founder and a converted newcomer.

Unchanged (the owner, 2026-11-21): one of the island's own Heathens who converts is never a founder and goes in the
generation the tribe was on when they converted -- also when a Heathen's own record (the coming Heathen logging:
"Faction: Heathen") says "How: Founder".  A namesake who was never a Heathen is never joined to the one who left.

Each case is checked against a CONTROL village: the same logs without the leaving and the return.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_family_tree as ft  # noqa: E402
import vv_genealogy as gen  # noqa: E402
import vv_reconcile as rc  # noqa: E402
import vv_villager_info as info  # noqa: E402
from test_identity_through_looks import arrived, history_text  # noqa: E402
from test_reconcile import Base, aged  # noqa: E402

T1, T2, T3 = "2026-11-19 23:33:16", "2026-11-20 10:00:00", "2026-11-22 19:15:57"
SUBJECT, DAD, MOM, OTHER = "Nobu", "Sakou", "Raiatea", "Pai"     # the fixture save's villagers
KID = rc.Seen("Kidlo", 1, 1, "Male", 300, frozenset(), frozenset())          # logs only: born to Sakou and Raiatea
GRANDKID = rc.Seen("Grandlo", 2, 2, "Female", 100, frozenset(), frozenset())   # logs only: born to Kidlo and Pai
LEFT = "Left the tribe: became a Heathen"


def birth(child, mother, father) -> str:
    return (f"Birth\n  Child: {child.name}\n    Sex: {child.sex}\n    Head: {child.head}\n    Body: {child.body}\n"
            f"  Mother: {mother.name}\n    Head: {mother.head}\n    Body: {mother.body}\n"
            f"  Father: {father.name}\n    Head: {father.head}\n    Body: {father.body}\n  Born as: Single birth\n\n")


def came_back(s, head: int, body: int) -> str:
    return (f"Arrived 90\n  Name: {s.name}\n  Special villager: Former Heathen (blue mask)\n  Age at arrival: {s.age}\n"
            f"  Sex: {s.sex}\n  Head: {head}\n  Body: {body}\n  How: Converted from the Heathens\n\n")


def left(s, head: int, body: int) -> str:
    return (f"Disappeared\n  Name: {s.name}\n  Age: {max(0, s.age - 40)}\n  Sex: {s.sex}\n  What happened: {LEFT}\n"
            f"  Head: {head}\n  Body: {body}\n  Likes: (none)\n  Dislikes: (none)\n\n")


def by_name(village: gen.Village, name: str) -> gen.Person:
    found = [p for p in village.people.values() if p.name == name]
    assert len(found) == 1, [(p.key, p.alive, p.gone) for p in found]
    return found[0]


class RejoinedKeepTheirPlace(Base):
    def build(self, kind: str, rejoined: bool, heathen_now: bool = False, new_looks: bool = False) -> gen.Village:
        """The fixture village with a family over three generations and the subject (Nobu): `kind` says how he
        first came -- "founder", "event" (a barrel), "born" (to Sakou and Raiatea) or "prelog" (no Arrived record;
        the first snapshot lists him).  `rejoined`: he left for the Heathens (a Heathen in the middle snapshot) and
        -- unless `heathen_now` -- came back.  `new_looks`: his head changed while he was a Heathen and no record
        says so."""
        v = self.village("huttest", 5)
        data = bytearray(v.save_path(1).read_bytes())
        entries = v.entries(bytes(data))
        people = v.people(bytes(data))
        for at, s in zip(entries, people):
            data[at + gen.VV5_FACTION_FROM_NAME] = 1 if (heathen_now and s.name == SUBJECT) else 0
        v.write_save(1, bytes(data))
        who = {s.name: s for s in people}
        subject, dad, mom, other = who[SUBJECT], who[DAD], who[MOM], who[OTHER]
        old = aged(subject, 0, head=subject.head + 3) if new_looks else subject    # the look he left with
        logs = arrived(1, dad, dad.head, dad.body) + arrived(2, mom, mom.head, mom.body)
        if kind == "founder":
            logs += arrived(3, old, old.head, old.body)
        elif kind == "event":
            logs += arrived(3, old, old.head, old.body, "Barrel of Babies")
        elif kind == "born":
            logs += birth(old, mom, dad)
        logs += birth(KID, mom, dad) + birth(GRANDKID, other, KID)
        if rejoined and not heathen_now:
            logs += came_back(subject, subject.head, subject.body)
        v.births(logs)
        if rejoined:
            v.deaths(left(old, old.head, old.body))
        first = [old if s.name == SUBJECT else s for s in people]
        faction = {(T, SUBJECT): ["Faction: Believer"] for T in (T1, T2, T3)}
        if rejoined:
            faction[(T2, SUBJECT)] = ["Faction: Heathen"]
            faction[(T3, SUBJECT)] = ["Faction: Heathen"] if heathen_now else \
                ["Faction: Believer", "Special villager: Former Heathen (blue mask)"]
        history_text(v, [(T1, first + [KID]), (T2, people + [KID]), (T3, people + [KID, GRANDKID])], faction)
        return gen.load_village(v.folder, 5, 1)

    def picture(self, village: gen.Village) -> dict:
        """Everyone as the tree shows them: generation, parents, founder, arrival words, place on the page."""
        lay = ft.layout(village, ft.Edits())
        people = village.people
        out = {}
        for pid, p in people.items():
            out[p.name, p.head, p.body] = (
                p.generation, people[p.father].name if p.father is not None else None,
                people[p.mother].name if p.mother is not None else None, ft.is_founder(village, p),
                ft.arrival_words(village, p), lay.x.get(pid), lay.y.get(pid))
        return out

    def check_same_place(self, kind: str, **how) -> gen.Village:
        control = self.build(kind, rejoined=False)
        back = self.build(kind, rejoined=True, **how)
        self.assertEqual(len(back.people), len(control.people), "one node: never a duplicate")
        self.assertEqual(self.picture(back), self.picture(control))
        nobu = by_name(back, SUBJECT)
        self.assertIn("Heathen", nobu.statuses, "a Heathen once: marked as one")
        self.assertFalse(gen.is_converted_newcomer(nobu))
        return back

    def test_a_founder_who_came_back_is_still_the_founder_in_the_founders_row(self) -> None:
        back = self.check_same_place("founder")
        nobu = by_name(back, SUBJECT)
        self.assertEqual(nobu.generation, 1)
        self.assertTrue(ft.is_founder(back, nobu))
        self.assertEqual(ft.arrival_words(back, nobu), "", "never 'Arrived: Converted from the Heathens'")
        self.assertIn("Converted Blue Mask Heathen", nobu.statuses)
        text = info.plain_text(info.info_lines(back, ft.Edits(), nobu.id))
        self.assertIn("Founder", text)
        self.assertNotIn("Converted from the Heathens", text)
        self.assertRegex(gen.report(back, "New Believers"), rf"\d+\. {SUBJECT}, Male, [^\n]* -- generation I, founder,")

    def test_an_island_event_villager_who_came_back_keeps_the_events_generation_and_words(self) -> None:
        back = self.check_same_place("event")
        nobu = by_name(back, SUBJECT)
        self.assertEqual(nobu.generation, 2, "the generation of their arrival, not of their return (III)")
        self.assertEqual(ft.arrival_words(back, nobu), "Arrived: Barrel of Babies")
        self.assertIn("arrived (Barrel of Babies)", gen.report(back, "New Believers"))

    def test_a_villager_born_in_the_tribe_who_came_back_keeps_their_parents_and_no_arrival_words(self) -> None:
        back = self.check_same_place("born")
        nobu = by_name(back, SUBJECT)
        self.assertEqual((back.people[nobu.father].name, back.people[nobu.mother].name), (DAD, MOM))
        self.assertEqual(ft.arrival_words(back, nobu), "")

    def test_a_villager_from_before_the_logs_who_came_back_is_still_a_founder(self) -> None:
        back = self.check_same_place("prelog")
        self.assertTrue(ft.is_founder(back, by_name(back, SUBJECT)))

    def test_a_look_changed_while_a_heathen_with_no_record_is_still_one_villager(self) -> None:
        """One of the owner's founders left with one body and came back with another: without the Appearance changed
        records the tree drew a "disappeared" founder AND a converted newcomer generations down."""
        back = self.check_same_place("founder", new_looks=True)
        nobu = by_name(back, SUBJECT)
        self.assertTrue(nobu.alive and nobu.founder_record and ft.is_founder(back, nobu))
        self.assertIn((nobu.head + 3, nobu.body), nobu.old_looks, "the look he left with is his old look")

    def test_while_a_heathen_they_keep_their_place_and_hide_unconverted_heathens_keeps_them(self) -> None:
        for kind in ("founder", "event", "born"):
            with self.subTest(kind=kind):
                control = self.build(kind, rejoined=False)
                away = self.build(kind, rejoined=True, heathen_now=True)
                self.assertEqual(self.picture(away), self.picture(control))
                nobu = by_name(away, SUBJECT)
                self.assertTrue(nobu.heathen)
                lay = ft.layout(away, ft.Edits())
                self.assertIn("Heathen", ft.default_text(lay, nobu))
                self.assertIn(nobu.id, gen.without_heathens(away).people, "one of the tribe: never hidden")


class IslandHeathensStillJoin(Base):
    def test_a_heathens_own_founder_record_is_no_founder_and_their_conversion_still_places_them(self) -> None:
        """The coming Heathen logging may write an island Heathen's own record with "How: Founder" and "Faction:
        Heathen": they were never one of the tribe, so their conversion is a joining (the owner, 2026-11-21)."""
        v = self.village("huttest", 5)
        people = v.people(v.save_path(1).read_bytes())
        who = {s.name: s for s in people}
        dad, mom, other, w = who[DAD], who[MOM], who[OTHER], who[SUBJECT]
        heathen_founder = arrived(3, w, w.head, w.body).replace("  How: Founder", "  Faction: Heathen\n  How: Founder")
        v.births(arrived(1, dad, dad.head, dad.body) + arrived(2, mom, mom.head, mom.body) + heathen_founder
                 + birth(KID, mom, dad) + birth(GRANDKID, other, KID) + came_back(w, w.head, w.body))
        history_text(v, [(T1, people + [KID]), (T2, people + [KID]), (T3, people + [KID, GRANDKID])],
                     {(T1, w.name): ["Faction: Heathen"], (T2, w.name): ["Faction: Heathen"],
                      (T3, w.name): ["Faction: Believer", "Special villager: Former Heathen (blue mask)"]})
        village = gen.load_village(v.folder, 5, 1)
        convert = by_name(village, SUBJECT)
        self.assertFalse(convert.founder_record)
        self.assertTrue(gen.is_converted_newcomer(convert))
        self.assertEqual(convert.generation, 3, "the newest believer generation when they converted")
        self.assertFalse(ft.is_founder(village, convert))

    def test_a_namesake_who_was_never_a_heathen_is_never_joined_to_the_one_who_left(self) -> None:
        v = self.village("huttest", 5)
        data = bytearray(v.save_path(1).read_bytes())
        for at in v.entries(bytes(data)):
            data[at + gen.VV5_FACTION_FROM_NAME] = 0       # everyone a believer: the living Nobu never a Heathen
        v.write_save(1, bytes(data))
        people = v.people(bytes(data))
        who = {s.name: s for s in people}
        w = who[SUBJECT]
        # Someone else called Nobu (another look, younger) left for the Heathens and is gone from the save; the
        # living Nobu, first listed in the very next snapshot, was never a Heathen: two villagers, though the
        # History alone would tie them (an unbroken History, the age only moving on).
        gone = aged(w, -100, head=w.head + 5)
        v.deaths(left(gone, gone.head, gone.body))
        history_text(v, [(T1, [s for s in people if s.name != SUBJECT] + [gone]), (T2, people)],
                     {(T1, gone.name): ["Faction: Believer"]})
        village = gen.load_village(v.folder, 5, 1)
        both = [p for p in village.people.values() if p.name == SUBJECT]
        self.assertEqual(len(both), 2, [(p.key, p.alive, p.gone) for p in both])
        self.assertEqual(sorted(p.alive for p in both), [False, True])
        self.assertEqual(village.identity_questions, [], "nothing to ask: the living Nobu was never a Heathen")


class ConvertsNeverPushEachOtherDown(unittest.TestCase):
    """The owner's 256 village (2026-11-22, "WHY ARE THERE 41 GENERATIONS"): generations I-VII, then XLI-XLV.  Two
    converts, each with a believer child the other's conversion snapshot lists (a Heathen father's child), set each
    other's generation: every round of _generations pushed both one further down, up to the round limit."""

    def village(self) -> gen.Village:
        P = gen.Person
        heathen_then, a_back, b_back = (T1, "Heathen"), (T2, "Believer"), (T3, "Believer")
        people = {1: P(1, "F1", 1, 1, sex="Male", alive=True, first_seen=T1, arrived=True, how="Founder",
                       founder_record=True),
                  2: P(2, "F2", 2, 2, sex="Female", alive=True, first_seen=T1, arrived=True, how="Founder",
                       founder_record=True),
                  3: P(3, "K1", 3, 3, sex="Female", alive=True, first_seen=T1, father=1, mother=2),
                  4: P(4, "A", 4, 4, sex="Male", alive=True, first_seen=T1, converted=True, arrived=True,
                       how=gen.CONVERTED_HOW, factions=[heathen_then, a_back]),
                  5: P(5, "B", 5, 5, sex="Male", alive=True, first_seen=T1, converted=True, arrived=True,
                       how=gen.CONVERTED_HOW, factions=[heathen_then, (T2, "Heathen"), b_back]),
                  6: P(6, "CB", 6, 6, sex="Female", alive=True, first_seen=T2, father=5, mother=2),   # B's, a Heathen then
                  7: P(7, "CA", 7, 7, sex="Female", alive=True, first_seen=T3, father=4, mother=3)}   # A's, after converting
        v = gen.Village(5, 1, "Test Tribe", people)
        gen._generations(v, {T1: {1, 2, 3, 4, 5}, T2: {1, 2, 3, 4, 5, 6}, T3: {1, 2, 3, 4, 5, 6, 7}})
        return v

    def test_each_convert_rests_only_on_the_tribe_before_them(self) -> None:
        v = self.village()
        gens = {p.name: p.generation for p in v.people.values()}
        self.assertEqual(gens, {"F1": 1, "F2": 1, "K1": 2, "A": 2, "B": 3, "CB": 4, "CA": 3})
        for p in v.people.values():             # a child one below the later parent, always
            parents = [v.people[q].generation for q in (p.father, p.mother) if q is not None]
            if parents:
                self.assertEqual(p.generation, 1 + max(parents), p.name)


class HeathenEvidence(unittest.TestCase):
    def test_what_says_they_were_of_the_tribe_first(self) -> None:
        P = gen.Person
        self.assertTrue(gen.joined_the_tribe_first(P(1, "F", 1, 1, founder_record=True)))
        self.assertTrue(gen.joined_the_tribe_first(P(2, "E", 1, 1, joined_how="Barrel of Babies")))
        self.assertTrue(gen.joined_the_tribe_first(P(3, "B", 1, 1, birth_record=4)))
        self.assertFalse(gen.joined_the_tribe_first(P(4, "H", 1, 1, birth_record=4, factions=[(T1, "Heathen")])),
                         "a Heathen's baby")
        self.assertTrue(gen.joined_the_tribe_first(P(5, "S", 1, 1, factions=[(T1, "Believer"), (T2, "Heathen")])))
        self.assertTrue(gen.joined_the_tribe_first(P(6, "L", 1, 1, factions=[(T1, "Believer")], left_heathen=True)))
        self.assertFalse(gen.joined_the_tribe_first(P(7, "C", 1, 1, factions=[(T1, "Believer")], converted=True)),
                         "a convert from before the logs: never a Heathen after a believer")
        self.assertFalse(gen.joined_the_tribe_first(P(8, "T", 1, 1, factions=[(T1, "Believer"), (T2, "Heathen")],
                                                      former_seen=[T1])), "a former Heathen's title then")
        self.assertFalse(gen.joined_the_tribe_first(P(9, "I", 1, 1, factions=[(T1, "Heathen"), (T2, "Believer")])))
        self.assertEqual(gen.arrival_how(P(10, "F", 1, 1, founder_record=True, joined_how="Founder", converted=True,
                                           arrived=True, how=gen.CONVERTED_HOW)), "Founder")
        self.assertEqual(gen.arrival_how(P(11, "I", 1, 1, converted=True, arrived=True, how=gen.CONVERTED_HOW)),
                         gen.CONVERTED_HOW)


if __name__ == "__main__":
    unittest.main()
