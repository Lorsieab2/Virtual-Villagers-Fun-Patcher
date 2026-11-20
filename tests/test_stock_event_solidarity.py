"""Village Solidarity moved by the games' OWN island events (the owner, 2026-11-20, v1.35.97): score only.

THE TABLE: data/stock_island_event_solidarity.txt is the one source; the companion carries it as
native/vvfp_island_events/stock_solidarity_table.inc (scripts/build_stock_solidarity_table.py), and the two agree.
Every stock island event of every game (the Game Mechanics event lists) is in it, every title and answer is the
game's own words (the stock executables), the same event in several games has the same tag, and the Gong of Wonder
(no island event, the owner) is not in it.

THE COMPANION (native/vvfp_island_events/stock_solidarity_harness.c, the shipped source whole): every row's result
moves the score by its tag exactly once; nothing without "VVFP Village Solidarity.dll"; nothing for an event the
table does not hold, a two-choice title with no answer, a constructor or answer click that is not the event's own
comparison; exactly once through the real brackets of each game.

STOCK ODDS UNTOUCHED (unicorn, the stock executables, the shipped "VVFP Island Events.dll"): installed with only the
Village Solidarity companion beside it, every byte of each executable's image is the stock one but the detoured
routines' first instructions -- each a jump to the companion, which runs the game's own instructions unchanged --
so every chooser, draw and result routine of every island event is byte-identical; with neither the log nor the
Village Solidarity companion, nothing is installed at all.  The companion only reads results after the game applied
them.

The live game is NOT exercised here (live pending).
"""
from __future__ import annotations

import json
import re
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_stock_event_solidarity as stock  # noqa: E402

NATIVE = ROOT / "native" / "vvfp_island_events"
DLL = ROOT / "assets" / "island_events" / "VVFP Island Events.dll"
VS_TOOLS = Path(r"C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.51.36231")
CL = VS_TOOLS / "bin" / "Hostx64" / "x86" / "cl.exe"
SDK = Path(r"C:\Program Files (x86)\Windows Kits\10")
SDK_VERSION = "10.0.26100.0"
EXES = {1: "Virtual Villagers - A New Home.exe", 2: "Virtual Villagers - The Lost Children.exe",
        3: "Virtual Villagers - The Secret City.exe", 4: "Virtual Villagers - The Tree of Life.exe",
        5: "Virtual Villagers - New Believers.exe"}
STOCK = {g: ROOT / "research" / "stock-executables" / n for g, n in EXES.items()}
HAVE_STOCK = all(p.is_file() for p in STOCK.values())
RESTORE = {1: "vv1_restore_missing_island_events", 2: "vv2_restore_missing_island_events"}


def base_title(title: str) -> str:
    """The Game Mechanics list's name without its " (which version)" part: the title the game shows."""
    return re.sub(r" \([^()]*\)$", "", title)


class TheTable(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = stock.parse()

    def test_the_companion_carries_the_one_source(self) -> None:
        self.assertEqual(stock.TABLE_INC.read_text(encoding="utf-8"), stock.render_c(self.rows),
                         "run scripts/build_stock_solidarity_table.py")
        self.assertIn('#include "stock_solidarity_table.inc"', (NATIVE / "stock_solidarity.inc").read_text())

    def test_every_stock_event_of_every_game_is_in_it(self) -> None:
        import vv_game_mechanics_events_vv1, vv_game_mechanics_events_vv2, vv_game_mechanics_events_vv3  # noqa
        import vv_game_mechanics_events_vv4, vv_game_mechanics_events_vv5  # noqa
        modules = {1: vv_game_mechanics_events_vv1, 2: vv_game_mechanics_events_vv2, 3: vv_game_mechanics_events_vv3,
                   4: vv_game_mechanics_events_vv4, 5: vv_game_mechanics_events_vv5}
        for game, module in modules.items():
            have = {" ".join(r.title.split()) for r in self.rows if r.game == game}
            for event in module.EVENTS:
                if event.only_with not in (None, RESTORE.get(game)):
                    continue                          # an event a patch adds (the new events tag their own pages)
                with self.subTest(game=game, event=event.title):
                    self.assertIn(base_title(event.title), have)

    def test_the_gong_is_left_out(self) -> None:
        self.assertFalse(any("Gong" in r.title for r in self.rows))

    def test_every_title_and_answer_is_the_games_own(self) -> None:
        if not HAVE_STOCK:
            self.skipTest("needs the stock executables")
        blobs = {g: STOCK[g].read_bytes() for g in STOCK}
        blobs[4] += (ROOT / "assets" / "text-changes" / "vv4-sm-base.xml").read_bytes()
        pronoun = {"him": rb"(?:him|\^|\+|&|=)", "her": rb"(?:her|\^|\+|&|=)", "he": rb"(?:he|\^)",
                   "she": rb"(?:she|\^)", "himself": rb"(?:himself|\^|\+|&|=|=self|\+self)",
                   "herself": rb"(?:herself|\^|\+|&|=|=self|\+self)"}
        for row in self.rows:
            for text in (row.title, row.answer):
                if not text:
                    continue
                words = [re.escape(w.encode("latin-1")) for w in text.split()]
                for i, w in enumerate(text.split()):
                    if w in pronoun:
                        words[i] = rb"(?:" + re.escape(w.encode()) + rb"|\S+)"
                pattern = rb"(?:^|[\x00\n>\"]| )" + rb" +".join(words) + rb"[ .]*(?:[\x00\n<\"\r])"
                with self.subTest(game=row.game, text=text):
                    self.assertRegex(blobs[row.game], re.compile(pattern))

    def test_the_same_event_in_several_games_has_the_same_tag(self) -> None:
        shared = ("Isola Day Celebration", "Blessings Day Celebration", "Day of Honor", "The Cold Snap",
                  "The Allergy Season", "The Salty Air", "The Heat Wave", "The Rainy Season", "The Creeping Mold",
                  "The Barrel O` Babies")
        for title in shared:
            tags = {(r.answer, r.when, r.tag) for r in self.rows if r.title == title}
            with self.subTest(title=title):
                self.assertEqual(len({t for _a, _w, t in tags}), 1, tags)
        for when, tag in (("food+", "RAISE"), ("food-", "LOWER"), ("tech+", "RAISE"), ("tech-", "LOWER")):
            for title in ("The Dense Fog", "The Mysterious Fog", "The Mysterious Footprints"):
                with self.subTest(title=title, when=when):
                    self.assertEqual(stock.tag_of(self.rows, {"The Dense Fog": 2, "The Mysterious Fog": 3}.get(
                        title, 4), title, "", {when}), tag)

    def test_hidden_rolls_are_told_by_the_result_shown(self) -> None:
        r = self.rows
        self.assertEqual(stock.tag_of(r, 1, "The Strange Berries", "Taste the strange berries", {"lost"}), "LOWER")
        self.assertEqual(stock.tag_of(r, 1, "The Strange Berries", "Taste the strange berries.", set()), "NEUTRAL")
        self.assertEqual(stock.tag_of(r, 1, "The Mysterious Face", "Get a closer look", {"joined"}), "RAISE")
        self.assertEqual(stock.tag_of(r, 1, "The Mysterious Face", "Get a closer look", set()), "LOWER")
        self.assertEqual(stock.tag_of(r, 2, "The  Foul Passing", "", set()), "LOWER")
        self.assertEqual(stock.tag_of(r, 2, "The Hole In The Sand", "Investigate the hole", {"sick", "sick2"}),
                         "LOWER")
        self.assertEqual(stock.tag_of(r, 2, "The Hole In The Sand", "Investigate the hole", {"sick"}), "NEUTRAL")
        self.assertEqual(stock.tag_of(r, 1, "A Mysterious Crate", "Open it", set(), "a rotting wooden crate"),
                         "LOWER")
        self.assertEqual(stock.tag_of(r, 1, "A Mysterious Crate", "Open it", set(), "a small wooden crate"), "RAISE")
        self.assertEqual(stock.tag_of(r, 3, "The Omen in the Clouds", "Warn the villagers", {"weather"}), "RAISE")
        self.assertEqual(stock.tag_of(r, 5, "Barrel O' Babies!", "", set()), "NEUTRAL")
        self.assertIsNone(stock.tag_of(r, 3, "The Aspiring Adventurer", "", set()))

    def test_the_counts(self) -> None:
        total = sum(sum(c.values()) for c in stock.counts(self.rows).values())
        self.assertEqual(total, len(self.rows))
        self.assertGreater(total, 350)


class TheGameMechanicsLine(unittest.TestCase):
    def test_each_game_says_its_own_counts(self) -> None:
        import vv_game_mechanics_solidarity as gms
        for game in range(1, 6):
            c = stock.counts()[game]
            line = gms.stock_rule(game)
            with self.subTest(game=game):
                self.assertIn(f"of this game's {sum(c.values())} results, {c['RAISE']} raise it", line)
                self.assertIn("stay exactly the game's own", line)


class TheRows(unittest.TestCase):
    def test_the_solidarity_row_ships_the_reader_and_both_pins_are_current(self) -> None:
        import hashlib
        digest = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        for game in range(1, 6):
            row = json.loads((ROOT / "data" / f"vv{game}_village_solidarity_feature.json").read_text(encoding="utf-8"))
            log = json.loads((ROOT / "data" / f"vv{game}_island_events_feature.json").read_text(encoding="utf-8"))
            ships = {f["destination"]: f["sha256"] for f in row["companion_files"]}
            with self.subTest(game=game):
                self.assertEqual(ships.get("VVFP Island Events.dll"), digest)
                self.assertEqual(log["companion_files"][0]["sha256"], digest)
                self.assertIn("The game's own island events move it too", row["description"])
                self.assertEqual(row["patches"], [])
                self.assertEqual({d["va"] for d in log["runtime_detours"]},
                                 {d["va"] for d in row["runtime_detours"]
                                  if d["installed_by"].startswith("VVFP Island Events.dll")})

    def test_installed_for_the_score_without_the_log(self) -> None:
        source = (NATIVE / "vvfp_island_events.c").read_text(encoding="utf-8")
        self.assertIn('writer() == NULL && !vvfp_patcher_file_exists("VVFP Village Solidarity.dll")', source)
        compare = source[source.index("static void compare(struct snapshot *s)"):]
        compare = compare[:compare.index("\n}\n")]
        self.assertLess(compare.index("stock_solidarity(s);"), compare.index("if (writer() == NULL)"))
        inc = (NATIVE / "stock_solidarity.inc").read_text(encoding="utf-8")
        self.assertIn('GetModuleHandleA("VVFP Village Solidarity.dll")', inc)   # never loads it
        self.assertNotIn("LoadLibrary", inc)


@unittest.skipUnless(CL.is_file(), "the 32-bit MSVC toolchain is not installed")
class TheCompanion(unittest.TestCase):
    def test_the_harness_passes_in_all_five_games(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vvfp_stock_solidarity_") as out:
            exe = Path(out) / "stock_solidarity_harness.exe"
            build = subprocess.run(
                [str(CL), "/nologo", f"/Fo{out}\\", "/O2", "/MT", "/W4",
                 "/I", str(VS_TOOLS / "include"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "um"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "shared"),
                 "/I", str(SDK / "Include" / SDK_VERSION / "ucrt"),
                 str(NATIVE / "stock_solidarity_harness.c"),
                 "/link",
                 f"/LIBPATH:{VS_TOOLS / 'lib' / 'x86'}",
                 f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'um' / 'x86'}",
                 f"/LIBPATH:{SDK / 'Lib' / SDK_VERSION / 'ucrt' / 'x86'}",
                 f"/OUT:{exe}", "kernel32.lib", "shell32.lib"],
                capture_output=True, text=True, cwd=out, timeout=600)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            self.assertNotIn("warning", build.stdout.lower())
            result = subprocess.run([str(exe)], capture_output=True, text=True, cwd=out, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("FAIL", result.stdout)
        for game in range(1, 6):
            self.assertIn(f"Virtual Villagers {game} (", result.stdout)
        rows = stock.counts()
        for game in range(1, 6):
            self.assertIn(f"every one of the {sum(rows[game].values())} rows moves the score by its own tag, "
                          "exactly once", result.stdout)
        self.assertIn("== ", result.stdout)


try:
    from story_emulator import Process  # noqa: E402
    HAVE_EMULATOR = True
except Exception:                              # unicorn or pefile missing
    HAVE_EMULATOR = False


@unittest.skipUnless(HAVE_EMULATOR and HAVE_STOCK and DLL.is_file(), "needs unicorn, pefile and the stock executables")
class StockOddsUntouched(unittest.TestCase):
    """The shipped companion in each stock executable (unicorn): only the routines' first instructions change."""

    def start(self, game: int, solidarity: bool) -> tuple[Process, bytes, bytes]:
        exe = STOCK[game].read_bytes()
        p = Process(exe, DLL)
        before = p.read(p.image_base, len(p._exe_pe.get_memory_mapped_image()))

        def attributes(pr):
            path = pr.wstring(pr.arg(0))
            there = solidarity and path.lower().endswith("vvfp village solidarity.dll")
            return (0x20 if there else 0xFFFFFFFF), 4
        p.api_handlers["GetFileAttributesW"] = attributes
        p.export("VvfpStartup", game, 0)
        after = p.read(p.image_base, len(before))
        return p, before, after

    def test_only_the_detoured_entries_change_and_every_draw_is_stock(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_island_events_features as island
        for game in range(1, 6):
            with self.subTest(game=game):
                p, before, after = self.start(game, solidarity=True)
                entries = {va - p.image_base: len(bytes.fromhex(stock_bytes))
                           for va, stock_bytes, _what in island.SITES[f"vv{game}"]}
                changed = [i for i in range(len(before)) if before[i] != after[i]]
                self.assertTrue(changed, "installed for the score alone (no log patch)")
                for i in changed:
                    self.assertTrue(any(e <= i < e + n for e, n in entries.items()),
                                    f"byte 0x{p.image_base + i:X} changed")
                for entry, n in entries.items():
                    self.assertEqual(after[entry], 0xE9)          # a jump to the companion, nothing else
                    self.assertEqual(after[entry + 5:entry + n], b"\x90" * (n - 5))   # the rest of what it re-runs
                    target = (entry + p.image_base + 5 + struct.unpack("<i", after[entry + 1:entry + 5])[0])
                    self.assertFalse(p.image_base <= target < p.image_base + len(before))

    def test_without_the_row_nothing_is_installed(self) -> None:
        for game in range(1, 6):
            with self.subTest(game=game):
                _p, before, after = self.start(game, solidarity=False)
                self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
