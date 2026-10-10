"""Write Island Events Log: more of what an event changes (the owner's v1.35.66 order).

native/vvfp_island_events/island_events_more_harness.c includes the companion's source whole and
runs its comparison in all five games (see its header): a "New villager" record says the
newcomer's Sex and Age; the Custom Island Event's parents, custom title, mask, Special villager
title and The Lost Children's totem are lines of the villager's record; and what an event changes
in the village -- food, tech points, the food stores, the puzzles, the weather -- is one village
record.  The addresses are the Story / Cheat Upgrades' Custom Island Event's own, and checked here
against its source so the two can never drift apart.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native" / "vvfp_island_events"
STORY = ROOT / "native" / "vvfp_story_upgrades"
VS_TOOLS = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231")
CL = VS_TOOLS / "bin" / "Hostx64" / "x86" / "cl.exe"
SDK = Path(r"C:\Program Files (x86)\Windows Kits\10")
SDK_VERSION = "10.0.26100.0"
# Per game: nothing changed, the newcomer, the parents, the title set and removed, the Special
# villager title, the whole likes list, no same-reading line, the village, the weather (or\n# none), a food store = 11; New Believers' Heathen
# mask and The Lost Children's totem one more each.
CHECKS = 5 * 14 + 2 + 3   # and the weather with no word, in the three games that have weather
# Labels the games have no word for, approved by the owner on 2026-10-09 (the coordinator's message:
# "The owner approved all of your proposals"); every other village label must be the exe's own words.
APPROVED = {
    1: ("Small hut 2", "Small hut 3"),
    2: ("Field protection from birds",),
    5: ("Small hut 1", "Small hut 2", "Small hut 3", "The nursery school (building)", "Weather"),
}



def table(source: str, head: str) -> str:
    text = source[source.index(head):]
    return text[:text.index("\n};")]


class IslandEventsMoreSource(unittest.TestCase):
    def setUp(self) -> None:
        self.more = (NATIVE / "island_event_more.inc").read_text(encoding="utf-8")
        self.games = (NATIVE / "island_event_games.inc").read_text(encoding="utf-8")
        self.companion = (NATIVE / "vvfp_island_events.c").read_text(encoding="utf-8")

    def test_the_companion_calls_the_additions_at_each_step(self):
        self.assertIn('#include "island_event_more.inc"', self.companion)
        self.assertIn("more_take(s);", self.companion)
        self.assertIn("used = more_villager_changes(i, live, changes, used, sizeof changes);", self.companion)
        self.assertIn("more_arrival(now[i], arrival, sizeof arrival);", self.companion)
        self.assertIn("more_village(before);", self.companion)

    def test_the_parents_are_the_custom_island_events_offsets(self):
        # story_cN.inc: ce_set_record_parents(record, father, mother, ..., father head, father body,
        # mother head, mother body, ...)
        for game, name in ((2, "VV2_FIELDS"), (3, "VV3_FIELDS"), (4, "VV4_FIELDS"), (5, "VV5_FIELDS")):
            story = (STORY / f"story_c{game}.inc").read_text(encoding="utf-8")
            call = re.search(r"ce_set_record_parents\(c\d_record\(index\), (0x[0-9A-F]+), (0x[0-9A-F]+), 0x19, 23,"
                             r"\s*(0x[0-9A-F]+), (0x[0-9A-F]+), (0x[0-9A-F]+),\s*(0x[0-9A-F]+)", story)
            self.assertIsNotNone(call, game)
            father, mother, fh, fb, mh, mb = call.groups()
            text = table(self.games, f"static const struct field {name}[] = {{")
            with self.subTest(game=game):
                self.assertIn(f'{{ "Father", {father}, F_NAME,', text)
                self.assertIn(f'{{ "Mother", {mother}, F_NAME,', text)
                self.assertIn(f'{{ "Father\'s head", {fh}, F_INT, 0 }}', text)
                self.assertIn(f'{{ "Father\'s body", {fb}, F_INT, 0 }}', text)
                self.assertIn(f'{{ "Mother\'s head", {mh}, F_INT, 0 }}', text)
                self.assertIn(f'{{ "Mother\'s body", {mb}, F_INT, 0 }}', text)

    def test_the_village_stores_are_the_custom_island_events(self):
        c1 = (STORY / "story_c1.inc").read_text(encoding="utf-8")
        c2 = (STORY / "story_c2.inc").read_text(encoding="utf-8")
        c3 = (STORY / "story_c3.inc").read_text(encoding="utf-8")
        c4 = (STORY / "story_c4.inc").read_text(encoding="utf-8")
        c5 = (STORY / "story_c5.inc").read_text(encoding="utf-8")
        self.assertIn("static int c1_food(void) { return *(int *)(VV1_WORLD() + 0xA2EC); }", c1)
        self.assertIn("static int c1_tech(void) { return *(int *)(VV1_WORLD() + 0xA2FC); }", c1)
        self.assertIn('{ "Food", W1, 0xA2EC, VF_INT, 0 }', self.more)
        self.assertIn('{ "Tech points", W1, 0xA2FC, VF_INT, 0 }', self.more)
        self.assertIn("static int c2_food(void) { return *(int *)(VV2_WORLD() + 0x2EAA4); }", c2)
        self.assertIn("static int c2_tech(void) { return *(int *)(VV2_WORLD() + 0x2EADC); }", c2)
        self.assertIn('{ "Food", W2, 0x2EAA4, VF_INT, 0 }', self.more)
        self.assertIn('{ "Tech points", W2, 0x2EADC, VF_INT, 0 }', self.more)
        for source, food, tech in ((c3, "0x582490u", "0x582644u"), (c4, "0x4D6DD0u", "0x4D6F88u"),
                                   (c5, "0x51D34Cu", "0x51D5F8u")):
            self.assertIn(food, source)
            self.assertIn(tech, source)
            self.assertIn(f'{{ "Food", 0, {food}, VF_INT, 0 }}', self.more)
            self.assertIn(f'{{ "Tech points", 0, {tech}, VF_INT, 0 }}', self.more)
        # The worlds the stores are in.
        self.assertIn("#define VV1_WORLD() (*(unsigned char **)(uintptr_t)0x48AEDCu)", c1)
        self.assertIn("#define W1 0x48AEDCu", self.more)
        self.assertIn("#define W2 0x4997BCu", self.more)
        # A New Home's and The Lost Children's puzzle flags, in the Custom Island Event's order.
        flags1 = re.findall(r"\{ (0x[0-9A-F]+), (?:0x[0-9A-F]+|0), \d+, \d+, 0x[0-9A-F]+, [^}]*\}",
                            table(c1, "static const c1_puzzle C1_PUZZLES[] = {"))
        mine1 = re.findall(r"W1, (0x[0-9A-F]+), VF_SOLVED_BYTE", self.more)
        self.assertEqual([int(f, 16) for f in flags1], [int(f, 16) for f in mine1])
        flags2 = re.findall(r"\{ (0x[0-9A-F]+), (?:0x[0-9A-F]+|0), \d+, 0x[0-9A-F]+, 0x[0-9A-F]+, [^}]*\}",
                            table(c2, "static const c2_puzzle C2_PUZZLES[] = {"))
        mine2 = re.findall(r"W2, (0x[0-9A-F]+), VF_SOLVED_BYTE", self.more)
        self.assertEqual([int(f, 16) for f in flags2], [int(f, 16) for f in mine2])
        # The Secret City's thresholds, The Tree of Life's and New Believers' tables.
        thresholds3 = [int(t) for t in re.findall(r"\{ \d+, (\d+), [^}]*\}",
                                                    table(c3, "static const c3_puzzle C3_PUZZLES[] = {"))]
        mine3 = [int(t) for t in re.findall(r"P3\(\d+\), VF_SOLVED_AT, (\d+) \}", self.more)]
        self.assertEqual(thresholds3, mine3)
        self.assertIn("0x4D8BF8u + 8u * (unsigned int)(id)", c4)
        self.assertIn("0x4D8B20u + 4u * (unsigned int)(id)", c4)
        self.assertIn("0x51E008u + 8u * (unsigned int)(id)", c5)
        self.assertIn("0x51DF30u + 4u * (unsigned int)(id)", c5)
        ids5 = [int(i) for i in re.findall(r"\{ (\d+), [^}]*\}", table(c5, "static const c5_puzzle C5_PUZZLES[] = {"))]
        mine5 = [int(i) for i in re.findall(r"P5\((\d+)\) \}", self.more)]
        self.assertEqual(ids5, mine5)

    def test_every_village_label_is_the_games_own_words(self):
        # The owner: every printed word comes from the game's exe or save data.  A label is one of
        # the executable's own strings, or two of them joined (The Secret City's "Tree 1" object
        # and its "Fruit on tree" / "Fruit Tree" words); the tree kinds print "Banana", "Mango",
        # "Papaya" as the exe spells them.  The only other words are the owner's (APPROVED).
        stock = ROOT / "research" / "stock-executables"
        if not stock.is_dir():
            self.skipTest("the stock executables are not here")
        names = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life",
                 5: "New Believers"}
        for game, title in names.items():
            data = (stock / f"Virtual Villagers - {title}.exe").read_bytes().lower()
            labels = re.findall(r'\{ "([^"]+)"', table(self.more, f"static const struct village_field VV{game}_VILLAGE[] = {{"))
            self.assertTrue(labels, game)
            for label in labels:
                with self.subTest(game=game, label=label):
                    if label in APPROVED.get(game, ()):
                        continue
                    parts = label.split(", ")
                    for part in parts:
                        self.assertIn(part.lower().encode(), data)
        # The weather's words: each in its own game's executable, but "clear" (the owner's, 2026-10-09).
        words = re.findall(r'\{ ("[^"]*"|NULL|WEATHER_TYPE_4), ("[^"]*"|NULL|WEATHER_TYPE_4), ("[^"]*"|NULL|WEATHER_TYPE_4), '
                           r'("[^"]*"|NULL|WEATHER_TYPE_4), ("[^"]*"|NULL|WEATHER_TYPE_4), ("[^"]*"|NULL|WEATHER_TYPE_4) \}',
                           self.more[self.more.index("static const char *weather_word("):])
        self.assertEqual(len(words), 3)
        for game, row in zip((3, 4, 5), words):
            data = (stock / f"Virtual Villagers - {names[game]}.exe").read_bytes().lower()
            for word in row:
                if word not in ("NULL", '"clear"', "WEATHER_TYPE_4"):
                    with self.subTest(game=game, weather=word):
                        self.assertIn(word.strip('"').encode(), data)
        data3 = (stock / "Virtual Villagers - The Secret City.exe").read_bytes()
        for word in (b"Banana\x00", b"Mango\x00", b"Papaya\x00"):
            self.assertIn(word, data3)

@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
class IslandEventsMoreHarness(unittest.TestCase):
    def test_the_harness_passes_in_all_five_games(self):
        with tempfile.TemporaryDirectory(prefix="vvfp_island_events_more_") as out:
            exe = Path(out) / "island_events_more_harness.exe"
            build = subprocess.run(
                [str(CL), "/nologo", f"/Fo{out}\\", "/O2", "/MT", "/W4",
                 "/I", str(VS_TOOLS / "include"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "um"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "shared"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "ucrt"),
                 str(NATIVE / "island_events_more_harness.c"),
                 "/link",
                 f"/LIBPATH:{VS_TOOLS / 'lib' / 'x86'}",
                 f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'um' / 'x86'}",
                 f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'ucrt' / 'x86'}",
                 f"/OUT:{exe}", "kernel32.lib", "shell32.lib"],
                capture_output=True, text=True, cwd=out, timeout=600,
            )
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            self.assertNotIn("warning", build.stdout.lower())
            result = subprocess.run([str(exe)], capture_output=True, text=True, cwd=out, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"== {CHECKS} check(s), 0 failure(s) ==", result.stdout)
        self.assertEqual(len(re.findall(r"^  ok ", result.stdout, re.M)), CHECKS, result.stdout)
        for game in range(1, 6):
            self.assertIn(f"Virtual Villagers {game} (", result.stdout)


if __name__ == "__main__":
    unittest.main()
