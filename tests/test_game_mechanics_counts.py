"""Game Mechanics' Village counts group (src/vv_game_mechanics_counts.py), all five games: the Village Statistics rows
read from the save and from the patcher's log for that save (both shown when they disagree), the game-specific counts,
"not kept" where nothing records a count, and the Golden Mushroom's real-life estimates (only with its patch).

The committed real saves (tests/fixtures/rename_tribe) are read; every folder is a short private temporary one."""
from __future__ import annotations

import gzip
import hashlib
import math
import shutil
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import vv_game_mechanics as gm  # noqa: E402
import vv_game_mechanics_counts as counts  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "rename_tribe"
NOW = 1_800_000_000


def fixture(name: str) -> bytes:
    return gzip.decompress((FIXTURES / f"{name}.ldw.gz").read_bytes())


class Page:
    def __init__(self, test: unittest.TestCase, game: int, slot: int = 1):
        import vv_tribe_rename
        self.game, self.slot = game, slot
        self.base = next(item.base for item in vv_tribe_rename.GAMES if item.number == game)
        self.root = Path(tempfile.mkdtemp(prefix="gc"))
        test.addCleanup(shutil.rmtree, self.root, True)
        self.folder = self.root / self.base
        self.folder.mkdir()

    def save(self, data: bytes) -> Path:
        path = self.folder / f"{self.base}{self.slot}.ldw"
        path.write_bytes(data)
        return path

    def log(self, rows: list[str]) -> Path:
        place = self.folder / "Virtual Villagers Fun Patcher" / f"Save {self.slot}" / "Logs" / "Village Statistics"
        place.mkdir(parents=True, exist_ok=True)
        path = place / f"Village Statistics v2 - Save {self.slot}.txt"
        path.write_text("Virtual Villagers\nVillage Statistics\nVillage: Test (Save 1)\n" + "\n".join(rows) + "\n",
                        encoding="latin-1")
        return path

    def facts(self, features: list[str] | None = None):
        games = []
        if features is not None:
            game = self.root / "games" / self.base
            (game / "Virtual Villagers Fun Patcher Files").mkdir(parents=True, exist_ok=True)
            (game / f"{self.base}.exe").write_bytes(b"MZ")
            lines = [f"Modified EXE: x | size 2 | SHA-256 {hashlib.sha256(b'MZ').hexdigest()}"]
            lines += [f"- Optional feature: N [{f}]" for f in features]
            (game / "Virtual Villagers Fun Patcher Files" / "VVFP Transparency Log.txt").write_text(
                "\n".join(lines) + "\n", encoding="utf-8")
            games = [game]
        return gm.read(self.folder, self.game, self.slot, games, now=NOW)


def group(facts, name=counts.COUNTS) -> list[gm.Fact]:
    return [f for f in facts if f.group == name]


def texts(facts, name=counts.COUNTS) -> str:
    return "\n".join(f.text for f in group(facts, name))


SAVES = {1: "vv1-huttest-1", 2: "vv2-huttest-1", 3: "vv3-huttest-1", 4: "vv4-huttest-1", 5: "vv5-huttest-1"}


class VillageCounts(unittest.TestCase):

    def test_group_is_right_after_vital_statistics(self) -> None:
        self.assertEqual(gm.GROUPS[:2], ("Vital statistics", "Village counts"))
        for game, name in SAVES.items():
            with self.subTest(game=game):
                page = Page(self, game)
                page.save(fixture(name))
                facts = page.facts()
                seen = [f.group for f in facts]
                self.assertIn(counts.COUNTS, seen)
                firsts = list(dict.fromkeys(seen))
                self.assertEqual(firsts.index(counts.COUNTS), firsts.index("Vital statistics") + 1)

    def test_every_statistics_row_is_shown_from_the_save(self) -> None:
        for game, name in SAVES.items():
            with self.subTest(game=game):
                data = fixture(name)
                page = Page(self, game)
                page.save(data)
                body = texts(page.facts())
                for row in counts.COMMON + counts.EXTRA[game]:
                    self.assertIn(f"{row}: ", body)
                for row, at in counts.SAVE_ROWS[game].items():
                    value = struct.unpack_from("<i", data, at)[0]
                    self.assertIn(f"{row}: {value:,} (", body)
                self.assertIn("log for this save was not found", body)

    def test_save_rows_match_the_known_offsets(self) -> None:
        """The rows the game modules already read are at the same places: Mushrooms Found and Island Events Seen."""
        import vv_game_mechanics_vv1 as vv1
        import vv_game_mechanics_vv3 as vv3
        import vv_game_mechanics_vv4 as vv4
        import vv_game_mechanics_vv5 as vv5
        self.assertEqual(counts.SAVE_ROWS[1]["Mushrooms Found"], vv1.MUSHROOMS_FOUND)
        self.assertEqual(counts.SAVE_ROWS[1]["Island Events Seen"], vv1.EVENTS_SEEN)
        self.assertEqual(counts.SAVE_ROWS[3]["Mushrooms Found"], vv3.MUSHROOMS_FOUND + 12)
        self.assertEqual(counts.SAVE_ROWS[4]["Mushrooms Found"], vv4.MUSHROOMS_FOUND)
        self.assertEqual(counts.SAVE_ROWS[4]["Island Events Seen"], vv4.EVENTS_SEEN)
        self.assertEqual(counts.SAVE_ROWS[5]["Mushrooms Found"], vv5.MUSHROOMS_FOUND)
        self.assertEqual(counts.SAVE_ROWS[5]["Island Events Seen"], vv5.EVENTS_SEEN)

    def test_log_rows_agree_disagree_and_patcher_only(self) -> None:
        data = fixture(SAVES[3])
        page = Page(self, 3)
        page.save(data)
        mushrooms = struct.unpack_from("<i", data, counts.SAVE_ROWS[3]["Mushrooms Found"])[0]
        tech = struct.unpack_from("<i", data, counts.SAVE_ROWS[3]["Tech Points Earned"])[0]
        log = page.log([f"Real Hours Played: 41", f"Mushrooms Found: {mushrooms}", f"Tech Points Earned: {tech + 5}",
                        "Villagers Buried: 7", "Chiefs Robed: 2", "Stews Found: 9", "Puzzles Solved: 0 out of 16"])
        import os
        os.utime(log, (NOW, NOW))
        body = texts(page.facts())
        self.assertIn(f"Mushrooms Found: {mushrooms:,} (mushrooms picked; the save and the patcher's log agree).", body)
        self.assertIn(f"Tech Points Earned: the save holds {tech:,}; the patcher's Village Statistics log says "
                      f"{tech + 5:,}", body)
        self.assertIn("Real Hours Played: 41 (real-life hours since the village was founded", body)
        self.assertIn("Villagers Buried: 7 (", body)
        self.assertIn("Chiefs Robed: 2 (", body)
        self.assertIn("Stews Found: 9 (", body)
        self.assertIn("Puzzles Solved: 0 out of 16 (puzzles solved; the save and the patcher's log agree)", body)
        self.assertIn("Village Elders: not shown: only the patcher's Village Statistics log gives it, and its log for "
                      "this save has no such row.", body)
        self.assertIn(log.name, body)

    def test_counts_read_from_the_save_or_logs_carry_no_label(self) -> None:
        page = Page(self, 1)
        page.save(fixture(SAVES[1]))
        for fact in group(page.facts()):
            if ": " in fact.text and fact.text.split(": ")[0] in counts.COMMON:
                self.assertTrue(fact.confirmed, fact.text)

    def test_vv1_golden_child(self) -> None:
        data = bytearray(fixture(SAVES[1]))
        page = Page(self, 1)
        page.save(bytes(data))
        self.assertIn("The Golden Child: not born yet (The Golden Child puzzle is not solved).", texts(page.facts()))
        data[0xA008 + 4] = 1
        page.save(bytes(data))
        self.assertIn("The Golden Child: born (The Golden Child puzzle is solved), but he is not among the living",
                      texts(page.facts()))

    def test_vv2_recipes_and_elders(self) -> None:
        data = bytearray(fixture(SAVES[2]))
        data[counts.VV2_RECIPE_FLAGS + 3] = 1
        data[counts.VV2_RECIPE_FLAGS + 7] = 1
        page = Page(self, 2)
        page.save(bytes(data))
        body = texts(page.facts())
        self.assertIn("Stew recipes discovered: 2 of 18 (the game's recipe numbers 3, 7).", body)
        self.assertIn("Esteemed Elders living now: 0.", body)
        self.assertIn("Totems standing now: 0.", body)
        self.assertIn("Normal game: at most 50 totems", body)
        self.assertNotIn("With \"Esteemed Elders' Totems", body)
        with_patch = texts(page.facts(["vv2_totems_out_of_entries"]))
        self.assertIn("(in this game): totems take no record and there is no limit.", with_patch)

    def test_vv2_a_totem_in_the_save_and_the_file_is_one(self) -> None:
        """Codex (PR #628): a save restored after Move Totems Out holds the statue the file holds too; it is one
        totem (same_statue), while a different statue of the same name still counts."""
        sys.path.insert(0, str(ROOT / "tests"))
        import test_vv2_totem_repairs as rep
        import vv_vv2_totem_store as ts
        from datetime import datetime
        e1, t1 = rep.elder_and_totem("Hoto Kenobi", head=14, body=5)
        v = rep.Village(self, rep.crowd(4) + [e1, t1])
        ts.move_out(v.folder, 1, processes=rep.NoGame(), now=datetime(2026, 10, 20, 9, 0, 0))
        restored = rep.save_for(rep.crowd(4) + [e1, t1])
        v.save.write_bytes(restored)

        def line(data: bytes) -> str:
            village = gm.Village(v.folder, 2, 1, v.save, data, frozenset(), 0.0)
            return next(f.text for f in counts.vv2_lines(village) if f.text.startswith("Totems standing now"))

        self.assertEqual(line(restored), "Totems standing now: 1 (Hoto Kenobi).")
        _e2, t2 = rep.elder_and_totem("Hoto Kenobi", head=3, body=9)      # another statue, the same name
        other = rep.save_for(rep.crowd(4) + [e1, t2])
        self.assertEqual(line(other), "Totems standing now: 2 (Hoto Kenobi, Hoto Kenobi); 1 of them kept in the "
                                      "patcher's ElderTotems.dat, outside the save.")

    def test_vv3_chief(self) -> None:
        page = Page(self, 3)
        page.save(fixture(SAVES[3]))
        self.assertIn("Tribal Chief now: none.", texts(page.facts()))

    def test_vv4_tree_and_stores(self) -> None:
        data = bytearray(fixture(SAVES[4]))
        page = Page(self, 4)
        page.save(bytes(data))
        body = texts(page.facts())
        self.assertIn("The Tree of Life: stage 0 of 5", body)
        self.assertIn("Tech levels: Science 1; Medicine 1; Learning 1; Construction 1; Food Mastery 1; Dendrology 1", body)
        self.assertIn("The stream: 100% obstructed", body)
        struct.pack_into("<i", data, counts.VV4_PUZZLE_ENTRIES + 8 * 1, 1)       # The Stream solved
        struct.pack_into("<i", data, counts.VV4_PUZZLE_ENTRIES + 8 * 13, 1)      # Honoring solved
        page.save(bytes(data))
        self.assertIn("stage 2 of 5", texts(page.facts()))
        self.assertIn("solved: The Stream, Honoring.", texts(page.facts()))

    def test_vv5_heathens(self) -> None:
        page = Page(self, 5)
        page.save(fixture(SAVES[5]))
        facts = page.facts()
        body = texts(facts)
        self.assertIn("Heathens now: 29 outside the tribe, never counted", body)
        self.assertIn("Heathen Chief: Nui (Faith -94).", body)
        self.assertIn("Heathen Mommy: Java (Faith -25).", body)
        self.assertNotIn("male 16,400 times", body)
        self.assertNotIn("belief", texts(facts, "Villager timers").lower().replace("believer", ""))
        with_patch = texts(page.facts([counts.HEATHEN_MOMMY]))
        self.assertIn("male 16,400 times in 32,768 (50.05%)", with_patch)
        self.assertIn("not a fault", with_patch)

    def test_golden_mushroom_finds_and_secrecy(self) -> None:
        for game, name in SAVES.items():
            with self.subTest(game=game):
                page = Page(self, game)
                page.save(fixture(name))
                off = gm.render([f for f in page.facts([]) if f.group != gm.SOURCES]).lower()
                self.assertNotIn("golden mushroom", off)
                on = texts(page.facts([f"vv{game}_super_secret_golden_mushroom"]))
                self.assertIn("Golden Mushrooms found: not kept.", on)
                self.assertIn("a Golden Mushroom counting as one", on)

    def test_duplication_cheat_normal_value_first(self) -> None:
        page = Page(self, 4)
        page.save(fixture(SAVES[4]))
        plain = texts(page.facts([]))
        self.assertIn("Normal game: a mushroom or collectible is picked up by the one child dropped on it.", plain)
        self.assertNotIn("Duplication Cheat", plain)
        cheat = page.facts(["vv4_everyone_collects_like_vv1"])
        self.assertIn("Duplication Cheat\" (in this game)", texts(cheat))
        self.assertIn("Duplication Cheat\" (in this game)", texts(cheat, "Vital statistics"))
        page1 = Page(self, 1)
        page1.save(fixture(SAVES[1]))
        self.assertNotIn("Normal game: a mushroom", texts(page1.facts([])))

    def test_general_rules_page_has_no_counts(self) -> None:
        for game in range(1, 6):
            self.assertFalse([f for f in gm.general(game, NOW) if f.group == counts.COUNTS])


class GoldenEstimate(unittest.TestCase):

    def test_arithmetic(self) -> None:
        wait = gm.golden_wait(30.0)
        self.assertAlmostEqual(wait["hours"], 1_000_000 / 30)
        self.assertAlmostEqual(wait["years"], 1_000_000 / 30 / (365.25 * 24))
        self.assertAlmostEqual(wait["playthroughs"], 1_000_000 / 30 / 168)
        self.assertAlmostEqual(wait["half"], math.log(2) * wait["playthroughs"])
        self.assertAlmostEqual(wait["most"], math.log(20) * wait["playthroughs"])
        # The chance of at least one in n playthroughs is 1 - exp(-n / average): 50% and 95% at those counts.
        self.assertAlmostEqual(1 - math.exp(-wait["half"] / wait["playthroughs"]), 0.5)
        self.assertAlmostEqual(1 - math.exp(-wait["most"] / wait["playthroughs"]), 0.95)

    def test_rounding(self) -> None:
        self.assertEqual(gm.rounded(3.14), "3.1")
        self.assertEqual(gm.rounded(198.4), "198")
        self.assertEqual(gm.rounded(33_333.3), "33,300")
        self.assertEqual(gm.rounded(55_555.6), "55,600")

    def test_lines_say_real_life_time_and_are_estimates(self) -> None:
        facts = gm.golden_lines("vv5_super_secret_golden_mushroom", 18.0, gm.NORMAL, "a rate")
        self.assertTrue(facts[0].confirmed)
        self.assertIn("Golden Mushroom instead", facts[0].text)
        self.assertFalse(facts[1].confirmed)
        self.assertFalse(facts[2].confirmed)
        self.assertIn("about 6.3 real-life years of playing (the game open and running, not paused), at Normal speed",
                      facts[1].text)
        self.assertIn("about 55,600 real-life hours", facts[1].text)
        self.assertIn("7 real-life days of play", facts[2].text)
        self.assertIn("around 331 playthroughs on average", facts[2].text)
        self.assertIn("229 playthroughs give a 50% chance and 991 a 95% chance", facts[2].text)
        vv1 = gm.golden_lines("vv1_super_secret_golden_mushroom", 30.0, gm.FAST + gm.PAUSED, "a rate", even_paused=True)
        self.assertIn("paused or not", vv1[1].text)
        self.assertIn("at Fast speed", vv1[1].text)

    def test_every_game_uses_its_own_rate(self) -> None:
        for game, name, years in ((1, SAVES[1], "3.8"), (3, SAVES[3], "6.3"), (4, SAVES[4], "4.8"),
                                  (5, SAVES[5], "6.3")):
            with self.subTest(game=game):
                page = Page(self, game)
                page.save(fixture(name))
                text = texts(page.facts([f"vv{game}_super_secret_golden_mushroom"]), "Mushrooms")
                self.assertIn(f"about {years} real-life years of playing", text)


if __name__ == "__main__":
    unittest.main()
