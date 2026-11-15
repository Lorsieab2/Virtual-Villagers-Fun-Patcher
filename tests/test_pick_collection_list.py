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
import json
import re
import struct
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
    """The manifest's rows with a .cieg of their own: the Living Event Engine's rows (id living_...) are variants
    in living.pak, listed and checked by tests/test_living_runtime.py."""
    path = ROOT / "assets" / "event_collection" / f"vv{game}" / "manifest.txt"
    return [line.split("\t") for line in path.read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#") and not line.startswith("living_")]


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


def _role_ids() -> set[str]:
    """Every role id of every shipped collection event (code labels: the player never sees them)."""
    ids = set()
    for path in (ROOT / "data" / "event_collection").glob("*/*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("roles"), dict):
            ids |= set(data["roles"])
    return ids


def _companion_words() -> set[str]:
    """The words the companion's own reason texts use ("child", "elder" ... are words there, not role ids)."""
    words = set()
    for name in ("story_graph.inc", "story_collection.inc"):
        text = (ROOT / "native" / "vvfp_story_upgrades" / name).read_text(encoding="latin-1")
        for literal in re.findall(r'"((?:[^"\\\n]|\\.)*)"', text):
            words |= set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", literal))
    return words


ROLE_IDS = _role_ids() | {"zz_helper9"}
CODE_LABELS = sorted(ROLE_IDS - _companion_words())


def no_role_id(test: unittest.TestCase, text: str) -> None:
    words = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text))
    test.assertEqual(sorted(words & set(CODE_LABELS)), [], f"a role id in {text!r}")


def plain(test: unittest.TestCase, title: str, needs: str, refusal: str) -> None:
    """A reason in plain words: it says what the event needs, with no code words or role ids, and the refusal says
    it too."""
    test.assertIn("needs ", needs)
    test.assertNotIn("can not happen in this village right now.", needs)       # the old reason-less words
    for word in ("0x", "{", "}", "CGC_", "min_eligible", "Nothing has been queued"):
        test.assertNotIn(word, needs)
    test.assertTrue(refusal.startswith(f"{title} can not happen right now: "), refusal)
    test.assertIn(needs, refusal)
    no_role_id(test, needs)
    no_role_id(test, refusal[len(title):])


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


GENERIC = "An event of the Isola Grand Event Collection."
GUARDIANS_WORDS = re.compile(r"heathen|convert", re.I)


def full_entry(picker: Picker, row: list[str], cieg: bytes) -> tuple[str, str, str, str]:
    """(title, description, needs, refusal) of the list's only entry, from the manifest's WHOLE line `row`."""
    picker.p.write(picker.text, ("\t".join(row) + "\n").encode("cp1252") + b"\0")
    picker.p.write(picker.blob, cieg)
    picker.p.export("VvfpStoryProbeCollectionManifest", picker.text, 0, 0)
    picker.p.export("VvfpStoryProbeCollectionCieg", picker.blob, len(cieg))
    k = picker.p.call(picker.p.exports["VvfpStoryProbeMoreEntry"], [picker.n, 0, *picker.bufs, 1200], limit=LIMIT)
    assert k == 0x4000, k
    title, needs, refusal = (picker.p.cstring(b, 1200) for b in picker.bufs)
    desc = picker.p.alloc(400)
    picker.p.export("VvfpStoryProbeMoreDescription", 0, desc, 400)
    return title, picker.p.cstring(desc, 400), needs, refusal


def install(picker: Picker, text: str) -> None:
    """The installed patches' list the patcher writes beside the game (story_graph.inc cg_installed_has)."""
    buf = picker.p.alloc(len(text) + 1)
    picker.p.write(buf, text.encode("ascii") + b"\0")
    picker.p.export("VvfpStoryProbeInstalledPatches", picker.n, buf)


@unittest.skipUnless(GAMES, "needs unicorn, pefile, the stock executables and the Story TEST build")
class TheDescriptions(unittest.TestCase):
    """The owner (2026-11-14): every collection event says in one sentence what happens (collection.description),
    in place of the generic line; New Believers with Guardians of Isola Rewrite says neither Heathen nor convert
    (docs/event-collection/guardians-wording.md), and without it nothing changes."""

    def test_every_event_shows_its_own_sentence(self) -> None:
        for game in GAMES:
            picker = Picker(game, 4)
            seen = set()
            for row in manifest_rows(picker.n):
                cieg = (ROOT / "assets" / "event_collection" / f"{row[0]}.cieg").read_bytes()
                with self.subTest(game=game, event=row[0]):
                    self.assertEqual(len(row), 9, "id, title, games, weight, series, credit, description, and the "
                                                  "two Guardians fields")
                    title, desc, _needs, _refusal = full_entry(picker, row, cieg)
                    self.assertEqual(title, row[1])
                    self.assertEqual(desc, row[6])
                    self.assertNotEqual(desc, GENERIC)
                    self.assertRegex(desc, r"^[A-Z][A-Za-z0-9 .,!?:;'-]*[.!?]$")   # no placeholder, brace, role id
                    # no code label: a role id with a digit or "_" (gardener1, zz_helper9); plain words such as
                    # "inventor" or "cook" are English the sentence may use
                    labels = {r for r in CODE_LABELS if re.search(r"[0-9_]", r)}
                    self.assertEqual(sorted(set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", desc)) & labels), [], desc)
                    seen.add(desc)
            self.assertGreater(len(seen), 1)

    def test_new_believers_with_and_without_guardians_of_isola(self) -> None:
        if "vv5" not in GAMES:
            self.skipTest("needs New Believers' stock executable")
        rows = manifest_rows(5)
        varied = [r for r in rows if r[7] or r[8]]
        self.assertEqual(sorted(r[0] for r in varied), ["vv5_convert_who_missed_home"])
        for guardians in (False, True):
            for adults in (4, 1):
                picker = Picker("vv5", adults)
                if guardians:
                    install(picker, "vv5\nvv5_guardians_of_isola_rewrite\n")
                for row in rows:
                    cieg = (ROOT / "assets" / "event_collection" / f"{row[0]}.cieg").read_bytes()
                    with self.subTest(guardians=guardians, adults=adults, event=row[0]):
                        title, desc, needs, refusal = full_entry(picker, row, cieg)
                        if guardians:
                            self.assertEqual(title, row[7] or row[1])
                            self.assertEqual(desc, row[8] or row[6])
                            for words in (title, desc, needs, refusal):
                                self.assertIsNone(GUARDIANS_WORDS.search(words), words)
                        else:
                            self.assertEqual((title, desc), (row[1], row[6]))
                            if needs and "not a chief" in needs:
                                self.assertIn("a puzzle's Heathen", needs)
        picker = Picker("vv5", 4)
        row = varied[0]
        cieg = (ROOT / "assets" / "event_collection" / f"{row[0]}.cieg").read_bytes()
        self.assertEqual(full_entry(picker, row, cieg)[:2], ("The Homesick Convert", row[6]))
        install(picker, "vv5\nvv5_guardians_of_isola_rewrite\n")
        self.assertEqual(full_entry(picker, row, cieg)[:2], ("The Homesick Newcomer", row[8]))


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
                           "Nobody in the village can take part now: it needs a villager of 60 or more")

    def test_no_role_id_in_any_reason(self) -> None:
        """Role ids are code labels (the owner: never shown): a role named zz_helper9, in every kind of reason."""
        self.assertIn("builder1", CODE_LABELS)
        self.assertIn("zz_helper9", CODE_LABELS)
        for game in GAMES:
            picker = Picker(game, 2)
            cases = (
                ({"min_age": 60}, {"min_eligible": 1}, "it needs a villager of 60 or more"),
                ({"min_age": 14}, {"min_eligible": 3}, "it needs 3, each a villager of 14 or more"),
                ({"min_age": 14}, {"min_eligible": 1, "if": {"min_population": 9}}, "it needs at least 9 "),
            )
            for role, requirement, want in cases:
                with self.subTest(game=game, requirement=requirement):
                    data = copy.deepcopy(SMALL)
                    data["roles"] = {"zz_helper9": dict(role, kind="villager")}
                    data["nodes"]["p"]["text"] = "(zz_helper9.Name) smiles at the sea."
                    data["title"] = "The Test Day"
                    data["requirement"] = requirement
                    self.check(picker, data, want)

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



FILL_BUDGET = 400_000_000      # instructions for 1,000 entries (measured: more than 100 million, under 400 million)


@unittest.skipUnless(GAMES, "needs the emulator, the Story TEST build and the stock executables")
class AThousandEntries(unittest.TestCase):
    """cie-v6-binary.md 26: the list holds about 1,000 events a game (the Isola Grand Event Collection, the Companion
    Anthology, More Island Events): SM_MAX and SC_MAX 2,048.  The fill -- each entry's event loaded and its strict
    cast and requirement checked -- finishes within FILL_BUDGET instructions in the emulator (a fraction of a second
    on a real computer), and the list keeps every entry, the last one's title included."""

    def test_a_thousand_entries_fill_in_time(self) -> None:
        cieg = cie.compile_graph(cie.load(copy.deepcopy(SMALL), scrolling=True))
        for game in [g for g in GAMES if g in ("vv1", "vv5")] or GAMES[:1]:
            with self.subTest(game=game):
                picker = Picker(game, 12)
                text = "".join(f"e{i}\tThe Event Number {i}\t1,2,3,4,5\t1\t\ttest\n" for i in range(1000))
                buf = picker.p.alloc(len(text) + 16)
                picker.p.write(buf, text.encode("cp1252") + b"\0")
                picker.p.write(picker.blob, cieg)
                picker.p.export("VvfpStoryProbeCollectionManifest", buf, 0, 0)
                picker.p.export("VvfpStoryProbeCollectionCieg", picker.blob, len(cieg))
                k, possible = picker.p.alloc(4 * 2048), picker.p.alloc(4 * 2048)
                count = picker.p.call(picker.p.exports["VvfpStoryProbeMoreList"], [picker.n, k, possible, 2048],
                                      limit=FILL_BUDGET)
                self.assertEqual(count, 1000, "every entry listed")
                ks = struct.unpack("<1000i", picker.p.read(k, 4000))
                self.assertEqual(list(ks), [0x4000 + i for i in range(1000)])
                self.assertEqual(struct.unpack("<1000i", picker.p.read(possible, 4000)), (1,) * 1000)
                last = picker.p.call(picker.p.exports["VvfpStoryProbeMoreEntry"],
                                     [picker.n, 999, *picker.bufs, 1200], limit=FILL_BUDGET)
                self.assertEqual(last, 0x4000 + 999)
                self.assertEqual(picker.p.cstring(picker.bufs[0], 1200), "The Event Number 999")

    def test_the_sizes(self) -> None:
        native = ROOT / "native" / "vvfp_story_upgrades"
        self.assertIn("#define SM_MAX 2048", (native / "story_more_events.inc").read_text(encoding="utf-8"))
        coll = (native / "story_collection.inc").read_text(encoding="utf-8")
        self.assertIn("#define SC_MAX 2048", coll)
        self.assertIn("#define SC_MANIFEST_BYTES 1048576", coll)


if __name__ == "__main__":
    unittest.main()
