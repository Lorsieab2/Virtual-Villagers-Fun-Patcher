"""Pick Island Event's list of the Isola Grand Event Collection (story_collection.inc sc_pick_fill), all five games.

Found live in v1.35.97 (A New Home): the list showed some events as only "can not happen in this village right now",
with no reason.  The owner: every event that can not happen says WHY, in plain words.  And a title is shown as
written before anyone is cast -- "(Name1)'s No Good, Very Bad Day" (the owner: the "(Name1)" is intentional; the
event's own popup fills it with the cast villager's name: tests/test_story_cie_graph_runtime_v6.py
test_placeholders_in_titles, which also checks the log's "Event:" line has the real name).

EMULATED (the Story TEST build, each game's executable):
  * every event of the collection the patcher ships for the game (assets/event_collection/vvN/manifest.txt and the
    .cieg beside it), one at a time, in a small village: its title exactly as the manifest has it (no "{" token);
    each that can not happen now says what it needs, and the refusal shown when it is chosen anyway says the same;
  * the reasons for each kind of requirement, on small events made here: the event's own condition (population,
    children, the Golden Child, "any", "not"), too few villagers who could take part (min_eligible), a role nobody
    can be, and an event with no villager role (it needs only that many villagers: it was never possible before).
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))

import test_story_custom_island_event as sci  # noqa: E402
import vv_cie_graph as cie  # noqa: E402

LIMIT = 400_000_000          # the biggest events take more than the emulator's default count to load and check
GAMES = [g for g in sci.GAMES if sci.HAVE_EMULATOR and sci.TEST_DLL.is_file() and sci.have_stock(g)]

SMALL = {
    "format": "vvfp-cie-graph", "version": 6, "title": "(Name1)'s Test Day", "games": [1, 2, 3, 4, 5],
    "roles": {"subject": {"kind": "villager", "min_age": 14}},
    "start": "p",
    "nodes": {"p": {"text": "(Name) smiles at the sea."}},
}
ROLELESS = {
    "format": "vvfp-cie-graph", "version": 6, "title": "The Quiet Wind", "games": [1, 2, 3, 4, 5],
    "roles": {},
    "start": "p",
    "nodes": {"p": {"text": "A quiet wind blows over the island."}},
}


def manifest_rows(game: int) -> list[list[str]]:
    path = ROOT / "assets" / "event_collection" / f"vv{game}" / "manifest.txt"
    return [line.split("\t") for line in path.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#")]


class Picker:
    """One game's Story companion with a village of `adults` villagers of 25; `entry` lists one event at a time."""

    def __init__(self, game: str, adults: int):
        self.n = int(game[2])
        self.st = sci.Story(game)
        self.p = self.st.proc
        for i in range(adults):
            self.st.village.put(i, sex="m" if i % 2 else "f", years=25, name=f"V{i}")
        self.text = self.p.alloc(4096)
        self.blob = self.p.alloc(0x40000)
        self.bufs = [self.p.alloc(1200) for _ in range(3)]

    def entry(self, row: list[str], cieg: bytes) -> tuple[int, str, str, str]:
        """(k, title, needs, refusal) of the list's only entry: `row` (the manifest's cells), `cieg` its event."""
        line = "\t".join(row[:5] + ["test"]) + "\n"
        self.p.write(self.text, line.encode("cp1252") + b"\0")
        self.p.write(self.blob, cieg)
        self.p.export("VvfpStoryProbeCollectionManifest", self.text, 0, 0)
        self.p.export("VvfpStoryProbeCollectionCieg", self.blob, len(cieg))
        k = self.p.call(self.p.exports["VvfpStoryProbeMoreEntry"], [self.n, 0, *self.bufs, 1200], limit=LIMIT)
        title, needs, refusal = (self.p.cstring(b, 1200) for b in self.bufs)
        return k, title, needs, refusal

    def made(self, data: dict) -> tuple[int, str, str, str]:
        g, problems = cie.validate(copy.deepcopy(data))
        assert problems == [], problems
        return self.entry(["test_event", data["title"], "1,2,3,4,5", "1", ""], cie.compile_graph(g))


def plain(test: unittest.TestCase, title: str, needs: str, refusal: str) -> None:
    """A reason in plain words: it says what the event needs, with no code words, and the refusal says it too."""
    test.assertIn("needs ", needs)
    test.assertNotIn("can not happen in this village right now.", needs)       # the old reason-less words
    for word in ("0x", "{", "}", "CGC_", "min_eligible", "Nothing has been queued"):
        test.assertNotIn(word, needs)
    test.assertTrue(refusal.startswith(f"{title} can not happen right now: "), refusal)
    test.assertIn(needs, refusal)


@unittest.skipUnless(GAMES, "needs unicorn, pefile, the stock executables and the Story TEST build")
class TheWholeCollection(unittest.TestCase):
    def test_every_title_as_written_and_every_refusal_with_its_reason(self) -> None:
        for game in GAMES:
            for adults in (4, 1):
                picker = Picker(game, adults)
                shown = refused = 0
                for row in manifest_rows(picker.n):
                    cieg = (ROOT / "assets" / "event_collection" / f"{row[0]}.cieg").read_bytes()
                    with self.subTest(game=game, adults=adults, event=row[0]):
                        k, title, needs, refusal = picker.entry(row, cieg)
                        self.assertEqual(k, 0x4000)
                        self.assertEqual(title, row[1], "the title as written")
                        self.assertNotIn("{", title)
                        shown += 1
                        if needs:
                            refused += 1
                            plain(self, title, needs, refusal)
                self.assertGreater(shown, 0)
                self.assertGreater(refused, 0, "a small village can not have every event")

    def test_the_very_bad_day_keeps_its_name_placeholder_in_the_list(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                picker = Picker(game, 4)
                row = [r for r in manifest_rows(picker.n) if r[0] == "all_very_bad_day"][0]
                cieg = (ROOT / "assets" / "event_collection" / "all_very_bad_day.cieg").read_bytes()
                self.assertEqual(picker.entry(row, cieg)[1], "(Name1)'s No Good, Very Bad Day")


@unittest.skipUnless(GAMES, "needs unicorn, pefile, the stock executables and the Story TEST build")
class TheReasons(unittest.TestCase):
    def check(self, picker: Picker, data: dict, want: str) -> None:
        _k, title, needs, refusal = picker.made(data)
        self.assertEqual(title, data["title"])
        plain(self, title, needs, refusal)
        self.assertIn(want, needs)

    def test_the_events_own_condition(self) -> None:
        for game in GAMES:
            picker = Picker(game, 2)
            people = "believers" if game == "vv5" else "villagers"
            for cond, want in (
                    ({"min_population": 10}, f"it needs at least 10 {people}."),
                    ({"min_children": 3}, "it needs at least 3 children under 14."),
                    ({"special_present": "golden_child"}, "it needs the Golden Child in the village."),
                    ({"special_present": "tribal_chief"}, "it needs the Tribal Chief in the village."),
                    ({"any": [{"min_population": 10}, {"min_children": 3}]},
                     f"it needs at least 10 {people} or at least 3 children under 14."),
                    ({"all": [{"min_population": 1}, {"min_children": 1}]}, "it needs at least 1 child under 14."),
                    ({"not": {"min_population": 2}}, f"it needs fewer than 2 {people}.")):
                with self.subTest(game=game, cond=cond):
                    data = copy.deepcopy(SMALL)
                    data["requirement"] = {"min_eligible": 1, "if": cond}
                    self.check(picker, data, want)

    def test_too_few_villagers_who_could_take_part(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                data = copy.deepcopy(SMALL)
                data["requirement"] = {"min_eligible": 3}
                self.check(Picker(game, 2), data,
                           "Too few villagers can take part in \"(Name1)'s Test Day\" now: it needs 3, each a "
                           "villager of 14 or more")

    def test_a_role_nobody_can_be(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                data = copy.deepcopy(SMALL)
                data["roles"]["subject"]["min_age"] = 60
                data["requirement"] = {"min_eligible": 1}
                self.check(Picker(game, 2), data,
                           "Nobody in the village can be the event's subject now: it needs a villager of 60 or more")

    def test_an_event_with_no_villager_role(self) -> None:
        """min_eligible counts the villagers when the event casts nobody (28 shipped events were never possible)."""
        for game in GAMES:
            with self.subTest(game=game):
                picker = Picker(game, 2)
                data = copy.deepcopy(ROLELESS)
                data["requirement"] = {"min_eligible": 1}
                self.assertEqual(picker.made(data)[2], "", "possible with one villager or more")
                data["requirement"] = {"min_eligible": 5}
                people = "believers" if game == "vv5" else "villagers"
                self.check(picker, data, f"it needs at least 5 {people}.")


if __name__ == "__main__":
    unittest.main()
