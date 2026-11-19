"""The Isola Grand Event Collection's rows and files (scripts/build_event_collection_features.py).

  * the five rows: right after More Island Events in each game, off by default, on in Owner's Defaults, off in
    Select All, not in Classic VV Difficulty, needing Story / Cheat Upgrades and Scrolling Popups -- each said in
    bold, both ticked by Owner's Defaults and by ticking the row -- and pinning every file
    it ships (the shipped rows are what the build makes now);
  * the files: "<game folder>\\Virtual Villagers Fun Patcher Files\\Island Event Collection\\" (src/patcher_files.py),
    each game's own manifest.txt and .cieg files, and the credits;
  * the credits: the source's ledger (lines 1-91) and every section's credit block, byte for byte the frozen source's;
  * the build on a fixture event (tests/data/cie_v6_gardening.json, The Gardening Contest): compiled, listed only in
    its own game's manifest, pinned in that game's row;
  * More Island Events now needs Story / Cheat Upgrades too, says so in bold, and no longer says its events take a
    share of the game's draw.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import build_event_collection_features as build  # noqa: E402
import patcher_files  # noqa: E402
import vv_fun_patcher as patcher  # noqa: E402
import vv_fun_patcher_gui as gui  # noqa: E402

GAMES = (1, 2, 3, 4, 5)
BOLD_NEEDS = "**Needs Story / Cheat Upgrades (on by default)"
BOLD_NEEDS_SCROLLING = ("**Needs Scrolling Popups, which keeps every page of these events on the screen; ticking this ticks it.**")


def rid(game: int) -> str:
    return f"vv{game}_isola_grand_event_collection"


class TheRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = patcher.load_fun_patches()
        cls.rows = {p.id: p.raw for p in cls.catalog}

    def test_right_after_more_island_events(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                ids = [p.id for p in self.catalog if p.id.startswith(f"vv{game}_")]
                self.assertEqual(ids[ids.index(f"vv{game}_more_island_events") + 1], rid(game))

    def test_defaults(self) -> None:
        classic = set()
        for game in (4, 5):
            classic |= set(self.rows[f"vv{game}_classic_vv_difficulty"]["dependencies"])
        for game in GAMES:
            with self.subTest(game=game):
                self.assertIn(rid(game), gui.DEFAULT_OFF_FUN_PATCH_IDS)              # off by default
                self.assertNotIn(rid(game), gui.OWNERS_DEFAULT_OFF_FUN_PATCH_IDS)    # Owner's Defaults ticks it
                self.assertIn(rid(game), gui.SELECT_ALL_OFF_FUN_PATCH_IDS)           # off in Select All
                self.assertNotIn(rid(game), classic)                                 # not Classic VV Difficulty

    def test_needs_story_cheat_upgrades_in_bold(self) -> None:
        for game in GAMES:
            for ident in (rid(game), f"vv{game}_more_island_events"):
                with self.subTest(ident=ident):
                    row = self.rows[ident]
                    expected = [f"vv{game}_story_cheat_upgrades"]
                    if ident == rid(game):   # the collection also needs Scrolling Popups (lead, 2026-11-14)
                        expected.append(f"vv{game}_scrolling_popups")
                    self.assertEqual(row["dependencies"], expected)
                    self.assertIn(BOLD_NEEDS, row["description"])
                    self.assertNotIn("**Needs no other patch.**", row["description"])

    def test_needs_scrolling_popups_in_bold(self) -> None:
        """The collection's popups are fit-checked with scrolling on, so its rows require Scrolling Popups, wired as
        the Story / Cheat Upgrades prerequisite is: a dependency, said in bold."""
        for game in GAMES:
            with self.subTest(game=game):
                row = self.rows[rid(game)]
                self.assertIn(f"vv{game}_scrolling_popups", row["dependencies"])
                self.assertIn(f"vv{game}_scrolling_popups", self.rows)
                self.assertIn(BOLD_NEEDS_SCROLLING, row["description"])

    def test_owners_defaults_tick_both_prerequisites(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                self.assertTrue(gui.owners_default_fun_patch_selection(rid(game)))
                for need in self.rows[rid(game)]["dependencies"]:
                    self.assertTrue(gui.owners_default_fun_patch_selection(need), need)

    def test_ticking_the_collection_ticks_both_prerequisites(self) -> None:
        import types

        class Var:
            def __init__(self, value=False):
                self.value = value

            def get(self):
                return self.value

            def set(self, value):
                self.value = value

        for game in GAMES:
            with self.subTest(game=game):
                public = [p for p in self.catalog if p.id.startswith(f"vv{game}_")]
                win = types.SimpleNamespace(fun_patches=public, fun_patch_vars={p.id: Var() for p in public},
                                            _last_fun_selection=set())
                win._patch_dependency_map = lambda w=win: gui.App._patch_dependency_map(w)
                win.fun_patch_vars[rid(game)].set(True)
                gui.App._apply_gui_dependency_selection(win, cotick=False)
                ticked = {pid for pid, var in win.fun_patch_vars.items() if var.get()}
                self.assertIn(rid(game), ticked)
                self.assertIn(f"vv{game}_story_cheat_upgrades", ticked)
                self.assertIn(f"vv{game}_scrolling_popups", ticked)
                # ...and unticking Scrolling Popups unticks the collection, never Story / Cheat Upgrades.
                win.fun_patch_vars[f"vv{game}_scrolling_popups"].set(False)
                gui.App._apply_gui_dependency_selection(win, cotick=False)
                self.assertFalse(win.fun_patch_vars[rid(game)].get())
                self.assertTrue(win.fun_patch_vars[f"vv{game}_story_cheat_upgrades"].get())

    def test_more_island_events_never_takes_a_share(self) -> None:
        for game in GAMES:
            with self.subTest(game=game):
                row = self.rows[f"vv{game}_more_island_events"]
                text = json.dumps(row)
                for stale in ("its own share of the draw", "1 in 23", "1 in the number listed", "rand(23)",
                              "drawn like any listed event", "one wider"):
                    self.assertNotIn(stale, text)
                self.assertIn("never takes a share of the game's own draw", row["description"])
                self.assertIn("Each natural island event has a 30-50% chance to be one of these instead (never a "
                              "rescue event or the two opening events). Events that can kill a villager, make one "
                              "disappear or lose a pregnancy only happen once the village has 61 or more villagers.",
                              row["description"])

    def test_the_shipped_rows_are_what_the_build_makes(self) -> None:
        made = build.build(write=False)
        for game in GAMES:
            with self.subTest(game=game):
                shipped = json.loads((ROOT / "data" / f"{rid(game)}_feature.json").read_text(encoding="utf-8"))
                self.assertEqual(shipped, made[game])

    def test_every_file_pinned_and_in_the_patchers_folder(self) -> None:
        for game in GAMES:
            row = self.rows[rid(game)]
            self.assertEqual(row["runtime_detours"], [])
            self.assertEqual(row["patches"], [])
            names = [item["destination"] for item in row["companion_files"]]
            # one manifest per source section and per living series (living-pack.md 1)
            self.assertTrue(any(n.startswith("Island Event Collection/manifest-") and n.endswith(".txt") for n in names))
            self.assertIn(f"Island Event Collection/{build.CREDITS_NAME}", names)
            for item in row["companion_files"]:
                with self.subTest(game=game, file=item["destination"]):
                    data = (ROOT / item["source"]).read_bytes()
                    self.assertEqual(hashlib.sha256(data).hexdigest().upper(), item["sha256"])
                    self.assertEqual(patcher_files.installed_relative_path(item["destination"]).as_posix(),
                                     f"{patcher_files.PATCHER_FILES_FOLDER}/{item['destination']}")


class TheCredits(unittest.TestCase):
    def test_the_source_is_the_frozen_one(self) -> None:
        raw = build.SOURCE.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest().upper(), build.SOURCE_SHA256)

    def test_ledger_and_section_blocks_byte_for_byte(self) -> None:
        raw = build.SOURCE.read_bytes()
        lines = raw.split(b"\n")
        credits = (ROOT / "assets" / "event_collection" / build.CREDITS_NAME).read_bytes()
        self.assertEqual(credits, (build.CREDITS_MD).read_bytes())
        # the ledger, but for the three handwritten events credited to the owner alone (L22-28, the owner 2026-11-16)
        ledger = build.ledger_text(build.source_lines()).encode("utf-8")
        self.assertTrue(ledger.startswith(b"VIRTUAL VILLAGERS"))
        self.assertIn(ledger, credits)
        self.assertEqual(b"\n".join(lines[0:21]) + b"\n", ledger[:len(b"\n".join(lines[0:21]) + b"\n")])
        self.assertIn(b"* The Child of Legend (VV1): written by Lorsieab2.\n", credits)
        for first, last, _what in build.CREDIT_BLOCKS:
            with self.subTest(lines=(first, last)):
                block = b"\n".join(lines[first - 1:last]) + b"\n"
                self.assertIn(block, credits)

    def test_each_block_is_a_credit_text(self) -> None:
        lines = build.source_lines()
        for first, last, _what in build.CREDIT_BLOCKS:
            with self.subTest(lines=(first, last)):
                text = build.span(lines, first, last)
                self.assertTrue("Lorsieab2" in text and "ChatGPT" in text, text[:120])


class TheBuild(unittest.TestCase):
    """The build on a fixture event: The Gardening Contest (The Secret City; the design's worked example)."""

    def test_a_fixture_event(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as tmp:
            tmp = Path(tmp)
            src = tmp / "data" / "event_collection" / "v6"
            src.mkdir(parents=True)
            shutil.copy(ROOT / "tests" / "data" / "cie_v6_gardening.json", src / "vv3_gardening_contest.json")
            assets = tmp / "assets" / "event_collection"
            data_dir = tmp / "data"
            docs = tmp / "credits.md"
            rows = build.build(src=src.parent, assets=assets, data_dir=data_dir, docs=docs, write=True)
            cieg = assets / "vv3_gardening_contest.cieg"
            self.assertTrue(cieg.is_file())
            # its section's file (one manifest per source section; this fixture's section is "V6 additions")
            files = sorted((assets / "vv3").glob("manifest-*.txt"))
            self.assertEqual(len(files), 1)
            manifest = files[0].read_text(encoding="utf-8")
            line = [r for r in manifest.splitlines() if not r.startswith("#")]
            self.assertEqual(len(line), 1)
            self.assertEqual(line[0].split("\t")[:5], ["vv3_gardening_contest", "The Gardening Contest", "3", "1", ""])
            for game in (1, 2, 4, 5):
                self.assertEqual(list((assets / f"vv{game}").glob("manifest-*.txt")), [])   # no event: no manifest
                self.assertEqual(len(rows[game]["companion_files"]), 1)                    # the credits
            files = {i["destination"]: i for i in rows[3]["companion_files"]}
            item = files["Island Event Collection/vv3_gardening_contest.cieg"]
            self.assertEqual(item["sha256"], hashlib.sha256(cieg.read_bytes()).hexdigest().upper())
            self.assertIn("1 events in this game", rows[3]["description"])
            self.assertIn(b"The Gardening Contest (source lines 3043-3096):", docs.read_bytes())
            stored = json.loads((data_dir / "vv3_isola_grand_event_collection_feature.json").read_text(encoding="utf-8"))
            self.assertEqual(stored, rows[3])


if __name__ == "__main__":
    unittest.main()
